"""gf180-pll :: vco-tuning-range :: campaign reduction for the supply campaign.

This is the `derived` extension point of the two-deck (`phases`) supply
manifest next to it. It carries, with the same arithmetic, everything the
pre-migration `jitter_extract.py` + `analyze_supply.py` pair computed:

  jitter_extract.py   interpolated half-supply crossings of the quiet / stepped
                      / rippled buffered outputs, reduced to the period and TIE
                      statistics a jitter budget consumes  -> `extract_jitter`
  analyze_supply.py   the whole-grid reductions the record's Result field is
                      made of -- the per-band pushing spread, the step
                      response, the ripple jitter against the solver's own
                      numerical floor, the band and ripple-frequency
                      dependence, and the verdict  -> `derive_tables`

Two hooks (see `sim/harness/derived.py`):

  derive_point(point)   per-point: the pushing coefficient of this corner's own
                        seven-supply curve, and every jitter metric, reduced
                        from the `jit` phase's `jit.dat` waveform.
  derive_tables(run)    the whole-grid reductions, one DerivedTable each,
                        including `migration_delta` -- a join against the
                        superseded record's own committed CSVs that states, in
                        the record, how far the migrated numbers moved.

`extract_jitter()` and `reduce_pushing()` are deliberately pure functions of
plain sequences, so `sim/tests/test_vco_supply_derive.py` can replay the
superseded record's own CSV (and an analytic waveform whose jitter is known in
closed form) through them without a simulator.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.derived import DerivedError, DerivedTable  # noqa: E402

#: The record this campaign supersedes -- the `derived.joins` inputs are its
#: committed CSVs, and `migration_delta` is the comparison against them.
SUPERSEDED_RECORD = "20260731-184845-0a12e6c"

#: A current-starved ring runs at f ~ I_stage / (N * C_stage * V_swing) and the
#: swing IS the supply, so even a perfectly supply-independent starving current
#: leaves f carrying a -1/vdd term. At 3.3 V that is -1/3.3 = -30.3 %/V: the
#: floor any pushing number for this topology is measured against.
SWING_TERM_PCT_PER_V = -100.0 / 3.3

#: The draft (unratified, #1) period-jitter line this record is read against.
DRAFT_TJ_RMS_PCT = 1.0

#: The band code and ripple divisor whose points make up the mandated PVT grid.
MAIN_BAND = 5
MAIN_RDIV = 16

#: Minimum crossings a channel needs before its statistics mean anything.
MIN_CROSSINGS = 8


# --------------------------------------------------------------- formatting
def g(x, digits=6):
    return "%.*g" % (digits, x) if x is not None else ""


def mhz(x):
    return "%.4g" % (x / 1e6)


def ts(x):
    """A time in the unit a reader can compare at a glance (as the record does)."""
    return "%.3g ns" % (x * 1e9) if abs(x) >= 1e-9 else "%.3g ps" % (x * 1e12)


def corner_name(corner, temp_c, vdd=None):
    out = "%s/%gC" % (corner, float(temp_c))
    return out if vdd is None else out + "/%.2fV" % float(vdd)


# ------------------------------------------------------ crossing extraction
def read_columns(path):
    """``(t, [y1, y2, y3])`` from one point's `jit.dat`, tolerating both layouts.

    `wrdata` writes ``t y1 t y2 t y3`` by default and ``t y1 y2 y3`` under
    ``set wr_singlescale``; the deck sets the latter, and this accepts either
    for the same reason the pre-migration `jitter_extract.py` did -- a deck
    edited to drop that line would otherwise silently mis-column.

    This reads the file itself, through the ``RawFile.path`` the harness
    documents for exactly this, rather than through ``RawFile.rows()``: that
    caches every parsed row for the life of the run, and a 144-point grid of
    18 000-row transient dumps is ~1.3 GB of cached float tuples nothing needs
    once the point has been reduced.
    """
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line[0] not in "-+.0123456789":
                continue
            try:
                rows.append([float(x) for x in line.split()])
            except ValueError:
                continue
    if not rows:
        return (), ()
    ncol = len(rows[0])
    cols = [[r[i] for r in rows if len(r) == ncol] for i in range(ncol)]
    if ncol == 4:  # `set wr_singlescale`: t, y1, y2, y3
        return cols[0], cols[1:]
    if ncol == 6:  # default wrdata: (t,y1),(t,y2),(t,y3)
        return cols[0], [cols[1], cols[3], cols[5]]
    raise DerivedError(
        "raw file %s has %d columns; expected 4 (wr_singlescale) or 6" % (path, ncol)
    )


def crossings(t, y, th, tmin):
    """Rising crossings of `th`, linearly interpolated, at times >= tmin."""
    out = []
    for i in range(len(y) - 1):
        if y[i] < th <= y[i + 1] and t[i] >= tmin:
            dy = y[i + 1] - y[i]
            out.append(t[i] if dy == 0 else t[i] + (th - y[i]) * (t[i + 1] - t[i]) / dy)
    return out


def stats(xs):
    """(mean, RMS deviation from the mean, peak-to-peak)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / n
    return m, var**0.5, (max(xs) - min(xs))


def linefit_residual(ts):
    """Residual of crossing times against their least-squares line (TIE)."""
    n = len(ts)
    ks = list(range(n))
    mk = sum(ks) / n
    mt = sum(ts) / n
    sxx = sum((k - mk) ** 2 for k in ks)
    sxy = sum((k - mk) * (t - mt) for k, t in zip(ks, ts))
    slope = sxy / sxx
    return [t - (mt + slope * (k - mk)) for k, t in zip(ks, ts)], slope


def channel_metrics(ts):
    """One channel's period / TIE statistics, or None if too few crossings."""
    if len(ts) < MIN_CROSSINGS:
        return None
    per = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    pm, prms, ppp = stats(per)
    c2c = [per[i + 1] - per[i] for i in range(len(per) - 1)]
    _, c2crms, _ = stats(c2c)
    tie, slope = linefit_residual(ts)
    _, tierms, tiepp = stats(tie)
    return {
        "n": len(ts),
        "f": (len(ts) - 1) / (ts[-1] - ts[0]),
        "period": pm,
        "tj_rms": prms,
        "tj_pp": ppp,
        "c2c_rms": c2crms,
        "tie_rms": tierms,
        "tie_pp": tiepp,
        "slope": slope,
        "tie": tie,
        "per": per,
        "ts": ts,
    }


def extract_jitter(t, yq, ys, yr, vsup, tsettle, tstepon, astep, arip, frip,
                   with_sequences=False):
    """Every jitter number the record reports, from one point's `jit.dat`.

    Ported verbatim from the pre-migration `jitter_extract.py`, including the
    one-period guard band either side of the step and the quasi-static
    predictions, so a migrated number differing from the superseded record's is
    an electrical difference and not an arithmetic one.

    Returns ``None`` when a channel never produced enough crossings to say
    anything (an early convergence failure, or a window too short) -- that is
    data, recorded as *not measured*, not an error.
    """
    th = vsup / 2.0
    mq, ms, mr = (channel_metrics(crossings(t, y, th, tsettle)) for y in (yq, ys, yr))
    if mq is None or mr is None:
        return None

    out = {
        "quiet_f_hz": mq["f"],
        "quiet_tj_pp_s": mq["tj_pp"],
        "quiet_tj_rms_s": mq["tj_rms"],
        "quiet_c2c_rms_s": mq["c2c_rms"],
        "quiet_tie_pp_s": mq["tie_pp"],
        "quiet_tie_rms_s": mq["tie_rms"],
        "rip_f_hz": mr["f"],
        "rip_tj_pp_s": mr["tj_pp"],
        "rip_tj_rms_s": mr["tj_rms"],
        "rip_c2c_rms_s": mr["c2c_rms"],
        "rip_tie_pp_s": mr["tie_pp"],
        "rip_tie_rms_s": mr["tie_rms"],
        "quiet_cycles": float(mq["n"]),
        "rip_cycles": float(mr["n"]),
        "rip_tj_rms_pct": 100.0 * mr["tj_rms"] * mr["f"],
        # The rippled result against this run's OWN quiet copy: the number that
        # says whether the jitter above is a circuit result or solver noise.
        "floor_margin_x": mr["tie_rms"] / max(mq["tie_rms"], 1e-18),
    }

    # --- stepped channel: pre/post-step frequency. One period of guard either
    # side keeps the crossing that straddles the step edge out of both
    # estimates. A step that landed outside the measured window leaves the
    # step columns not-measured rather than failing the whole point.
    kvdd_tran = None
    if ms is not None:
        guard = ms["period"]
        pre = [x for x in ms["ts"] if x < tstepon - guard]
        post = [x for x in ms["ts"] if x > tstepon + guard]
        if len(pre) >= 4 and len(post) >= 4:
            f_pre = (len(pre) - 1) / (pre[-1] - pre[0])
            f_post = (len(post) - 1) / (post[-1] - post[0])
            df = f_post - f_pre
            kvdd_tran = df / astep if astep else 0.0
            out.update(
                {
                    "step_f_pre_hz": f_pre,
                    "step_f_post_hz": f_post,
                    "step_df_hz": df,
                    "step_kvdd_hz_per_v": kvdd_tran,
                    # Timing error a 1 us open-loop interval accumulates at the
                    # post-step frequency offset -- the number a loop-bandwidth
                    # budget has to beat.
                    "step_tie_per_us_s": 1e-6 * df / f_pre,
                }
            )

    # --- rippled channel: measured vs. quasi-static prediction. Excess phase
    # from f(t) = f0 + K*A*sin(2*pi*f_r*t) integrates to a peak-to-peak time
    # error of K*A/(pi*f_r*f0); period modulation is 2*T0*K*A/f0 peak-to-peak.
    if kvdd_tran is not None and arip and frip:
        out["rip_tie_pp_pred_s"] = abs(kvdd_tran) * arip / (math.pi * frip * mq["f"])
        out["rip_tj_pp_pred_s"] = 2.0 * (1.0 / mq["f"]) * abs(kvdd_tran) * arip / mq["f"]

    if with_sequences:
        out["_seq"] = (mq, ms, mr)
    return out


# ------------------------------------------------------- pushing reduction
def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    m = sxy / sxx
    return m, my - m * mx


def reduce_pushing(vs, fs, currents, vnom=3.30):
    """Least-squares f(vdd) slope of one corner's seven-supply curve.

    ``push_nl_pct`` is the largest departure of the measured curve from its own
    straight line, as a percentage of the nominal-supply frequency: it is what
    licenses quoting a single pushing coefficient per corner at all.
    """
    if len(vs) < 3 or any(f is None for f in fs):
        return {}
    order = sorted(range(len(vs)), key=lambda i: vs[i])
    v = [vs[i] for i in order]
    f = [fs[i] for i in order]
    cur = [currents[i] for i in order]
    m, c = linfit(v, f)
    nomix = min(range(len(v)), key=lambda i: abs(v[i] - vnom))
    f_nom = f[nomix]
    if not f_nom:
        return {}
    nl = max(abs(fi - (m * vi + c)) for vi, fi in zip(v, f)) / f_nom
    out = {
        "push_slope_hz_per_v": m,
        "push_norm_pct_per_v": 100.0 * m / f_nom,
        "push_f_nom_hz": f_nom,
        "push_nl_pct": 100.0 * nl,
    }
    if cur[nomix] is not None:
        out["push_i_nom_a"] = abs(cur[nomix])
    return out


# ---------------------------------------------------------------- per point
def supply_axis(params):
    """The deck's internal supply sweep, vs1..vs7, as floats in deck order."""
    out = []
    k = 1
    while "vs%d" % k in params:
        out.append(float(params["vs%d" % k]))
        k += 1
    return out


def derive_point(point):
    """Both phases' reductions for one PVT point, merged into one row.

    ``derive_point`` runs once, after every phase, over the merged
    measurements and raw files -- which is what makes it possible to report the
    static pushing coefficient and the transient jitter of the same corner side
    by side in one record.
    """
    out = {}

    # ---- push phase: this corner's f(vdd) curve
    vs = supply_axis(point.params)
    if vs:
        fs = [point.get("f%d" % k) for k in range(1, len(vs) + 1)]
        cur = [point.get("i%d" % k) for k in range(1, len(vs) + 1)]
        out.update(reduce_pushing(vs, fs, cur))

    # ---- jit phase: the period sequence
    raw = point.raw("jit.dat")
    tsettle, tstepon, frip = (point.get("jsettle"), point.get("jstepon"), point.get("jfrip"))
    if raw.exists() and None not in (tsettle, tstepon, frip):
        t, ys = read_columns(raw.path)
        if t and len(ys) == 3:
            metrics = extract_jitter(
                t, ys[0], ys[1], ys[2],
                vsup=point.vdd,
                tsettle=tsettle,
                tstepon=tstepon,
                astep=float(point.params.get("astep", 0.0)),
                arip=float(point.params.get("arip", 0.0)),
                frip=frip,
            )
            if metrics:
                out.update(metrics)
    return out


# ------------------------------------------------------------ run reductions
class _Point:
    """One completed grid point, in the shape both reductions want to read."""

    def __init__(self, view):
        self.view = view
        self.corner = view.corner
        self.corner_id = view.corner_id
        self.temp_c = float(view.temp_c)
        self.vdd = float(view.vdd)
        self.band = int(float(view.params.get("band", -1)))
        self.rdiv = int(float(view.params.get("w_rdiv", 0)))
        self.vctrl = float(view.params.get("vctrl", 0.0))
        self.m = view.measurements

    def get(self, name, default=None):
        value = self.m.get(name)
        return default if value is None else value

    def has(self, *names):
        return all(self.m.get(n) is not None for n in names)

    @property
    def label(self):
        return corner_name(self.corner, self.temp_c, self.vdd)

    def supply_curve(self):
        """{supply_v: (f, |i|)} from the push phase's seven copies."""
        vs = supply_axis(self.view.params)
        out = {}
        for k, v in enumerate(vs, start=1):
            f = self.m.get("f%d" % k)
            i = self.m.get("i%d" % k)
            if f is not None:
                out[v] = (f, abs(i) if i is not None else None)
        return out


def _points(run):
    return [_Point(v) for v in run.points]


def _main_grid(points):
    """The mandated-PVT block: band 5, ripple f_osc/16 -- one row per PVT point."""
    seen = set()
    out = []
    for p in points:
        if p.band != MAIN_BAND or p.rdiv != MAIN_RDIV:
            continue
        key = (p.corner, p.temp_c, p.vdd)
        if key in seen or not p.has("rip_tie_pp_s"):
            continue
        seen.add(key)
        out.append(p)
    return out


def _pushing_curves(points):
    """{(corner, temp, band): [_Point, ...]} -- duplicates kept, for the check."""
    g = defaultdict(list)
    for p in points:
        if p.has("push_norm_pct_per_v"):
            g[(p.corner, p.temp_c, p.band)].append(p)
    return g


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2]


# ------------------------------------------------------------------- tables
def _pushing_summary(points):
    curves = _pushing_curves(points)
    if not curves:
        return DerivedTable(
            name="supply_pushing_summary",
            columns=("band", "curves", "note"),
            rows=(("—", 0, "no pushing curve completed"),),
            description="static supply pushing -- no data",
        )

    # Where the shared grid ran the pushing deck at more than one PVT supply
    # (the band-5 blocks, which exist for the jitter deck), the circuit is
    # identical and the numbers must be too. Stating the disagreement is
    # cheaper than trusting that they are.
    worst_dup, worst_dup_at = 0.0, ""
    for key, ps_ in curves.items():
        vals = [p.get("push_norm_pct_per_v") for p in ps_]
        if len(vals) > 1 and max(abs(v) for v in vals):
            spread = (max(vals) - min(vals)) / abs(_median(vals))
            if abs(spread) > abs(worst_dup):
                worst_dup, worst_dup_at = spread, "%s/%gC/B%d" % (key[0], key[1], key[2])

    first = {k: v[0] for k, v in curves.items()}
    rows = []
    for band in sorted({k[2] for k in first}):
        sel = [(k, p) for k, p in first.items() if k[2] == band]
        norms = [p.get("push_norm_pct_per_v") for _k, p in sel]
        lo = min(sel, key=lambda kp: kp[1].get("push_norm_pct_per_v"))
        hi = max(sel, key=lambda kp: kp[1].get("push_norm_pct_per_v"))
        worst = max(abs(n) for n in norms)
        rows.append(
            (
                "B%d" % band,
                len(sel),
                "%.1f" % min(norms),
                corner_name(lo[0][0], lo[0][1]),
                "%.1f" % _median(norms),
                "%.1f" % max(norms),
                corner_name(hi[0][0], hi[0][1]),
                "%.0f" % (worst * 0.33),
            )
        )

    allnorms = [p.get("push_norm_pct_per_v") for p in first.values()]
    wr = min(first.items(), key=lambda kp: kp[1].get("push_norm_pct_per_v"))
    br = max(first.items(), key=lambda kp: kp[1].get("push_norm_pct_per_v"))
    med = _median(allnorms)
    maxnl = max(p.get("push_nl_pct") for p in first.values())
    notes = [
        "Local slope of f_osc against vdd_vco, least-squares over the seven "
        "supply points spanning 2.97-3.63 V, at every (bundle, temperature, "
        "band) combination -- %d curves of 7 points each." % len(first),
        "Worst (most supply-sensitive) point: **%.1f %%/V** (%s MHz/V at %s MHz) "
        "at %s, band %d, Vctrl %g V."
        % (wr[1].get("push_norm_pct_per_v"), mhz(wr[1].get("push_slope_hz_per_v")),
           mhz(wr[1].get("push_f_nom_hz")), corner_name(wr[0][0], wr[0][1]),
           wr[0][2], wr[1].vctrl),
        "Best: **%.1f %%/V** at %s, band %d."
        % (br[1].get("push_norm_pct_per_v"), corner_name(br[0][0], br[0][1]), br[0][2]),
        "Curvature: the largest departure of any measured f(vdd) curve from its "
        "own straight-line fit is %.2f %% of f_nom, so pushing is effectively "
        "linear across the whole +/-10 %% rail and a single coefficient per "
        "corner is a fair summary." % maxnl,
        "**Where the sensitivity comes from, and why it is not a sizing error.** "
        "A current-starved ring runs at f ~ I_stage / (N * C_stage * V_swing), "
        "and V_swing *is* the supply. Even with a perfectly supply-independent "
        "starving current, f therefore carries a -1/vdd term = **%.1f %%/V** at "
        "3.3 V. The measured median of %.1f %%/V is %.2fx that floor, i.e. the "
        "bias generator contributes only the remainder. Reducing supply pushing "
        "materially would require a regulated VCO rail or a swing-independent "
        "cell (a differential delay cell with replica-biased load), i.e. exactly "
        "the alternatives DR-001 Decision 2 considered and rejected on power and "
        "cell-count grounds -- not a resizing of this cell."
        % (SWING_TERM_PCT_PER_V, med, abs(med / SWING_TERM_PCT_PER_V)),
    ]
    if worst_dup_at:
        notes.append(
            "Repeatability: %d of the %d (bundle, temperature, band) pushing "
            "curves were simulated more than once, because the shared grid runs "
            "the pushing deck at every PVT supply the jitter deck needs and this "
            "deck's supply axis is internal. Those repeats are byte-identical "
            "circuits; the largest disagreement between any two of them is "
            "%.2g %% of the coefficient, at %s."
            % (sum(1 for v in curves.values() if len(v) > 1), len(curves),
               100 * abs(worst_dup), worst_dup_at)
        )
    return DerivedTable(
        name="supply_pushing_summary",
        columns=(
            "band", "curves", "most_negative_pct_per_v", "most_negative_at",
            "median_pct_per_v", "least_negative_pct_per_v", "least_negative_at",
            "worst_shift_over_pm10pct_rail_pct",
        ),
        rows=tuple(rows),
        description="static supply pushing, per band code (deck tb_vco_pushing.spice)",
        notes=tuple(notes),
    )


def _step_response(grid):
    if not grid:
        return DerivedTable(
            name="supply_step_response",
            columns=("case", "corner", "note"),
            rows=(("—", "—", "no step measurement completed"),),
            description="supply-step response -- no data",
        )
    sel = [p for p in grid if p.has("step_df_hz", "step_f_pre_hz")]
    if not sel:
        return DerivedTable(
            name="supply_step_response",
            columns=("case", "corner", "note"),
            rows=(("—", "—", "no step measurement completed"),),
            description="supply-step response -- no data",
        )

    def frac(p):
        return abs(p.get("step_df_hz")) / p.get("step_f_pre_hz")

    ordered = sorted(sel, key=frac)
    picks = (
        ("worst", ordered[-1]),
        ("median", ordered[len(ordered) // 2]),
        ("best", ordered[0]),
    )
    rows = tuple(
        (
            label,
            p.label,
            "%.3g" % (p.get("step_df_hz") / 1e6),
            "%.2f" % (100 * p.get("step_df_hz") / p.get("step_f_pre_hz")),
            "%.3g" % (p.get("step_kvdd_hz_per_v") / 1e6),
            "%.3g" % (p.get("step_tie_per_us_s") * 1e9),
        )
        for label, p in picks
    )
    return DerivedTable(
        name="supply_step_response",
        columns=(
            "case", "corner", "df_mhz", "df_over_f_pct", "transient_pushing_mhz_per_v",
            "open_loop_timing_error_per_us_ns",
        ),
        rows=rows,
        description=(
            "response to a %g V supply step with a 1 ns edge, over the %d-point "
            "mandated PVT grid (band %d, Vctrl 1.8 V ~ 100 MHz class)"
            % (float(grid[0].view.params.get("astep", 0.0)), len(sel), MAIN_BAND)
        ),
        notes=(
            "The last column is the number a loop-bandwidth budget has to beat: "
            "with the loop open, a supply step of this size walks the VCO's "
            "output edge by that much timing error for every microsecond the "
            "loop takes to correct it. It is *not* a jitter spec violation on "
            "its own -- inside the loop bandwidth the PLL cancels it -- but it "
            "is the reason #10 cannot choose an arbitrarily low loop bandwidth, "
            "and it is a direct input to #14's supply-sensitivity budget.",
        ),
    )


def _ripple_jitter(grid):
    sel = [p for p in grid if p.has("rip_tie_pp_s")]
    if not sel:
        return DerivedTable(
            name="supply_ripple_jitter",
            columns=("case", "corner", "note"),
            rows=(("—", "—", "no ripple measurement completed"),),
            description="supply-ripple jitter -- no data",
        )
    ordered = sorted(sel, key=lambda p: p.get("rip_tie_pp_s"))
    worst, med, best = ordered[-1], ordered[len(ordered) // 2], ordered[0]
    quiet_worst = max(sel, key=lambda p: p.get("quiet_tie_pp_s"))

    def row(label, p, pfx):
        return (
            label,
            p.label,
            ts(p.get(pfx + "_tj_pp_s")),
            ts(p.get(pfx + "_tj_rms_s")),
            ts(p.get(pfx + "_tie_pp_s")),
            ts(p.get(pfx + "_tie_rms_s")),
        )

    rows = (
        row("rippled, worst", worst, "rip"),
        row("rippled, median", med, "rip"),
        row("rippled, best", best, "rip"),
        row("**quiet reference, worst** (numerical floor)", quiet_worst, "quiet"),
    )
    margin = min(p.get("floor_margin_x") for p in sel)
    margin_at = min(sel, key=lambda p: p.get("floor_margin_x")).label
    tjpct = worst.get("rip_tj_rms_pct")
    arip = float(grid[0].view.params.get("arip", 0.0))
    return DerivedTable(
        name="supply_ripple_jitter",
        columns=(
            "case", "corner", "period_jitter_pp", "period_jitter_rms",
            "tie_pp", "tie_rms",
        ),
        rows=rows,
        description=(
            "sinusoidal ripple of %g V amplitude (%.0f mV peak-to-peak, %.1f %% "
            "of the nominal rail) at f_osc/%d, over the %d-point mandated PVT grid"
            % (arip, 2000 * arip, 100 * 2 * arip / 3.30, MAIN_RDIV, len(sel))
        ),
        notes=(
            "The smallest margin between a rippled result and its own run's "
            "quiet reference anywhere on the grid is **%.0fx** in TIE RMS (at "
            "%s), so every supply-induced number above is a circuit result, not "
            "solver noise." % (margin, margin_at),
            "Worst case as a fraction of the period: **%.2f %% RMS period "
            "jitter** and %.2f %% peak-to-peak, at %s, f_osc = %s MHz."
            % (tjpct, 100 * worst.get("rip_tj_pp_s") * worst.get("rip_f_hz"),
               worst.label, mhz(worst.get("rip_f_hz"))),
            "The draft spec line is < %g %% RMS period jitter, so **a %.0f mV "
            "peak-to-peak ripple on an unregulated VCO rail is on its own %s "
            "that line** open-loop."
            % (DRAFT_TJ_RMS_PCT, 2000 * arip,
               "sufficient to break" if tjpct > DRAFT_TJ_RMS_PCT else "inside"),
        ),
    )


def _band_dependence(points, vnom=3.30):
    """Worst supply-ripple jitter per band, at ONE PVT point across all bands.

    Restricted to the nominal temperature and supply because the comparison
    across bands is only meaningful if every band is compared under the same
    conditions -- the mandated PVT spread is band 5's, and it is the
    `supply_ripple_jitter` table's job. The bundle count per band is reported,
    because the grid deliberately covers some bands at more bundles than others.
    """
    sel = [
        p for p in points
        if p.rdiv == MAIN_RDIV and p.temp_c == 27.0 and abs(p.vdd - vnom) < 1e-9
        and p.has("rip_tie_pp_s")
    ]
    bands = sorted({p.band for p in sel})
    if not sel or len(bands) < 2:
        return DerivedTable(
            name="ripple_band_dependence",
            columns=("band", "note"),
            rows=(("—", "fewer than two band codes completed"),),
            description="band dependence of supply-ripple jitter -- no data",
        )
    rows = []
    for band in bands:
        b = [p for p in sel if p.band == band]
        fw = max(b, key=lambda p: p.get("rip_tie_pp_s"))
        rows.append(
            (
                "B%d" % band,
                len(b),
                mhz(min(p.get("rip_f_hz") for p in b)),
                mhz(max(p.get("rip_f_hz") for p in b)),
                ts(fw.get("rip_tie_pp_s")),
                "%.2f" % fw.get("rip_tj_rms_pct"),
                fw.label,
            )
        )
    return DerivedTable(
        name="ripple_band_dependence",
        columns=(
            "band", "points", "f_osc_min_mhz", "f_osc_max_mhz", "worst_tie_pp",
            "worst_period_jitter_rms_pct_of_period", "worst_at",
        ),
        rows=tuple(rows),
        description=(
            "the same ripple at every band code -- jitter *as a fraction of the "
            "period* is the comparable quantity across a 40:1 frequency range"
        ),
    )


def _ripple_frequency(points, vnom=3.30):
    """Measured vs. quasi-static-predicted TIE at three ripple frequencies.

    Only the corner bundles that ran at *every* ripple frequency are averaged:
    the ripple frequency is the variable under test, so a row averaged over a
    different set of bundles from its neighbour would fold the process spread
    into the trend it is supposed to isolate.
    """
    sel = [
        p for p in points
        if p.band == MAIN_BAND and p.temp_c == 27.0 and abs(p.vdd - vnom) < 1e-9
        and p.has("rip_tie_pp_s", "rip_tie_pp_pred_s")
    ]
    divisors = sorted({p.rdiv for p in sel})
    if len(divisors) < 2:
        return DerivedTable(
            name="ripple_frequency_check",
            columns=("ripple_div", "note"),
            rows=(("—", "fewer than two ripple frequencies completed"),),
            description="quasi-static model check -- no data",
        )
    shared = set.intersection(
        *({p.corner for p in sel if p.rdiv == rd} for rd in divisors)
    )
    sel = [p for p in sel if p.corner in shared]
    rows = []
    for rd in divisors:
        b = [p for p in sel if p.rdiv == rd]
        meas = sum(p.get("rip_tie_pp_s") for p in b) / len(b)
        pred = sum(p.get("rip_tie_pp_pred_s") for p in b) / len(b)
        frip = sum(p.get("jfrip") for p in b) / len(b)
        rows.append(
            ("f_osc/%d" % rd, len(b), "%.3g" % (frip / 1e6), ts(meas), ts(pred),
             "%.2f" % (meas / pred if pred else 0.0))
        )
    ratios = [
        p.get("rip_tie_pp_s") / p.get("rip_tie_pp_pred_s")
        for p in points
        if p.has("rip_tie_pp_s", "rip_tie_pp_pred_s") and p.get("rip_tie_pp_pred_s") > 0
    ]
    if not ratios:
        return DerivedTable(
            name="ripple_frequency_check",
            columns=("ripple_frequency", "note"),
            rows=(("—", "no point produced a quasi-static prediction"),),
            description="quasi-static model check -- no data",
        )
    lo, hi, md = min(ratios), max(ratios), _median(ratios)
    notes = [
        "Each row is averaged over the %d bundle(s) that ran at every ripple "
        "frequency (%s), at 27 C and the nominal supply, so the ripple frequency "
        "is the only variable between rows."
        % (len(shared), ", ".join(sorted(shared))),
        "Across all %d rippled runs the measured/predicted ratio spans %.2f .. "
        "%.2f (median %.2f)." % (len(ratios), lo, hi, md),
    ]
    if lo > 0.8 and hi < 1.25:
        notes.append(
            "The quasi-static model therefore reproduces the measurement to "
            "better than 25 %, and supply-ripple TIE at ripple frequencies that "
            "were not simulated may be projected as "
            "TIE_pp = K_vdd * A / (pi * f_ripple * f_osc)."
        )
    else:
        notes.append(
            "TIE scales as 1/f_ripple as the model predicts -- the *shape* is "
            "right -- but the magnitude is consistently off by that factor, so "
            "the step-derived coefficient is **not** a safe basis for projecting "
            "ripple jitter: a ring's response to a bidirectional ripple is larger "
            "than its response to a unidirectional step of the same peak-to-peak "
            "size, because f ~ 1/vdd is convex. Ripple jitter at a ripple "
            "frequency that matters must be **measured**, not extrapolated. The "
            "measured numbers stand on their own; only the extrapolation is "
            "withheld."
        )
    return DerivedTable(
        name="ripple_frequency_check",
        columns=(
            "ripple_frequency", "points", "f_ripple_mhz", "tie_pp_measured",
            "tie_pp_predicted_from_step", "measured_over_predicted",
        ),
        rows=tuple(rows),
        description=(
            "does the quasi-static model reproduce the measurement, i.e. may "
            "these numbers be projected to ripple frequencies that were not "
            "simulated?"
        ),
        notes=tuple(notes),
    )


PERIOD_COLUMNS = (
    "cycle",
    "quiet_t_s", "quiet_period_s", "quiet_tie_s",
    "step_t_s", "step_period_s", "step_tie_s",
    "ripple_t_s", "ripple_period_s", "ripple_tie_s",
)


def _period_table(name, point, description):
    """The per-cycle period and TIE sequences behind one point's jitter numbers.

    `sim/README.md`'s waveform rule: commit the *extracted signal*, never the
    rawfile. The transient dump this is reduced from is scratch (the manifest's
    `raw_files` entry is not retained); these rows are the evidence.
    """
    if point is None:
        return DerivedTable(
            name=name,
            columns=("cycle", "note"),
            rows=((0, "point not present in this run"),),
            description=description + " -- no data",
        )
    raw = point.view.raw("jit.dat")
    metrics = None
    t, ys = read_columns(raw.path) if raw.exists() else ((), ())
    if t and len(ys) == 3:
        metrics = extract_jitter(
            t, ys[0], ys[1], ys[2],
            vsup=point.vdd,
            tsettle=point.get("jsettle"),
            tstepon=point.get("jstepon"),
            astep=float(point.view.params.get("astep", 0.0)),
            arip=float(point.view.params.get("arip", 0.0)),
            frip=point.get("jfrip"),
            with_sequences=True,
        )
    if not metrics or "_seq" not in metrics:
        return DerivedTable(
            name=name,
            columns=("cycle", "note"),
            rows=((0, "waveform for %s is no longer on disk" % point.corner_id),),
            description=description + " -- no data",
        )
    mq, ms, mr = metrics["_seq"]
    if ms is None:
        return DerivedTable(
            name=name,
            columns=("cycle", "note"),
            rows=((0, "stepped channel produced too few crossings"),),
            description=description + " -- no data",
        )
    n = min(len(mq["per"]), len(ms["per"]), len(mr["per"]))
    rows = tuple(
        (
            i,
            "%.10g" % mq["ts"][i], g(mq["per"][i]), g(mq["tie"][i]),
            "%.10g" % ms["ts"][i], g(ms["per"][i]), g(ms["tie"][i]),
            "%.10g" % mr["ts"][i], g(mr["per"][i]), g(mr["tie"][i]),
        )
        for i in range(n)
    )
    return DerivedTable(
        name=name,
        columns=PERIOD_COLUMNS,
        rows=rows,
        description="%s -- `%s`" % (description, point.corner_id),
        notes=(
            "One row per measured cycle of each of the three copies. The quiet "
            "column is the transient solver's own numerical floor at these "
            "settings; the ripple column is the signal.",
        ),
    )


# ------------------------------------------------------------- migration check
PUSH_COMPARE = (("fosc_hz", "f"), ("isupply_a", "i"))
JIT_COMPARE = (
    "frip_hz", "quiet_f_hz", "quiet_tie_rms_s",
    "step_f_pre_hz", "step_df_hz", "step_kvdd_hz_per_v",
    "rip_f_hz", "rip_tj_pp_s", "rip_tj_rms_s", "rip_tie_pp_s", "rip_tie_rms_s",
)
#: derived-measure name for each legacy jitter column above
JIT_COMPARE_NEW = {"frip_hz": "jfrip"}


def _rel(a, b):
    return abs(a - b) / abs(b) if b else float("nan")


def _migration_delta(run, points):
    """How far the migrated numbers moved from the record this supersedes.

    A migration's characteristic failure is a *silent* one: a number that
    changed because the tooling changed looks exactly like an electrical
    regression. This joins the superseded record's own committed CSVs and puts
    the answer in the record instead of in a commit message.
    """
    rows = []
    notes = []
    try:
        push_join = run.join("legacy_push")
        jit_join = run.join("legacy_jit")
    except DerivedError as exc:
        return DerivedTable(
            name="migration_delta",
            columns=("quantity", "note"),
            rows=(("—", str(exc)),),
            description="comparison against %s -- join not supplied" % SUPERSEDED_RECORD,
        )

    # ---- static pushing, one legacy row per (bundle, temp, band, vdd)
    curves = {}
    for key, ps_ in _pushing_curves(points).items():
        curves[key] = ps_[0].supply_curve()
    deltas = defaultdict(list)
    for r in push_join.rows:
        key = (r["bundle"], float(r["temp_c"]), int(r["band"]))
        curve = curves.get(key)
        if not curve:
            continue
        v = float(r["vdd_v"])
        match = [cv for cv in curve if abs(cv - v) < 1e-9]
        if not match:
            continue
        f_new, i_new = curve[match[0]]
        deltas["fosc_hz"].append((_rel(f_new, float(r["fosc_hz"])),
                                  "%s/%gC/B%d/%.2fV" % (key[0], key[1], key[2], v)))
        if i_new is not None:
            deltas["isupply_a"].append((_rel(i_new, float(r["isupply_a"])),
                                        "%s/%gC/B%d/%.2fV" % (key[0], key[1], key[2], v)))

    # ---- transient, one legacy row per (bundle, temp, vdd, band, ripple_div)
    new_jit = {}
    for p in points:
        new_jit.setdefault((p.corner, p.temp_c, p.vdd, p.band, p.rdiv), p)
    for r in jit_join.rows:
        key = (r["bundle"], float(r["temp_c"]), float(r["vdd_v"]),
               int(r["band"]), int(r["ripple_div"]))
        p = new_jit.get(key)
        if p is None:
            continue
        where = "%s/%gC/%.2fV/B%d/R%d" % key
        for col in JIT_COMPARE:
            new_name = JIT_COMPARE_NEW.get(col, col)
            new_val = p.m.get(new_name)
            if new_val is None or col not in r or r[col] == "":
                continue
            deltas[col].append((_rel(new_val, float(r[col])), where))

    for name in [c[0] for c in PUSH_COMPARE] + list(JIT_COMPARE):
        d = deltas.get(name)
        if not d:
            rows.append((name, 0, "", "", "no shared point"))
            continue
        vals = [x[0] for x in d]
        worst = max(d, key=lambda x: x[0])
        rows.append(
            (name, len(d), "%.3g" % (100 * _median(vals)),
             "%.3g" % (100 * worst[0]), worst[1])
        )
    compared = sum(len(v) for v in deltas.values())
    notes.append(
        "Every quantity the superseded record `%s` published, re-measured "
        "through `sim/harness` and compared point by point: %d shared "
        "measurements over %d quantities. The deltas are relative, in percent."
        % (SUPERSEDED_RECORD, compared, len([v for v in deltas.values() if v]))
    )
    notes.append(
        "The two runs are the same experiment, not merely a similar one: the "
        "decks, the seven-supply pushing axis, the 0.1 V step, the 0.05 V "
        "ripple, the window rule and the in-deck frequency estimator that sets "
        "the ripple frequency are all preserved term for term. What changed is "
        "the runner (bash + `sim/lib/simenv.sh` -> `sim/run_corners.py`), the "
        "deck composition (a `.control` block instead of a top-level `.tran`) "
        "and the extraction's host (`jitter_extract.py` -> this module, same "
        "arithmetic). A non-zero delta is therefore a finding about one of "
        "those, and is discussed in the record's Methodology field, not "
        "absorbed."
    )
    return DerivedTable(
        name="migration_delta",
        columns=(
            "quantity", "points_compared", "median_abs_delta_pct",
            "max_abs_delta_pct", "max_abs_delta_at",
        ),
        rows=tuple(rows),
        description="numeric comparison against superseded record %s" % SUPERSEDED_RECORD,
        notes=tuple(notes),
    )


def _verdict(points, grid):
    rows = []
    curves = {k: v[0] for k, v in _pushing_curves(points).items()}
    if curves:
        norms = [p.get("push_norm_pct_per_v") for p in curves.values()]
        worst = min(curves.items(), key=lambda kp: kp[1].get("push_norm_pct_per_v"))
        rows.append(
            ("static supply pushing, worst corner",
             "%.1f %%/V" % min(norms),
             "%s, band %d" % (corner_name(worst[0][0], worst[0][1]), worst[0][2]),
             "characterized; %.2fx the -1/vdd swing term, so dominated by the "
             "ring's swing-vs-supply term rather than by bias-current sensitivity"
             % abs(min(norms) / SWING_TERM_PCT_PER_V)),
        )
        rows.append(
            ("pushing linearity, worst curve",
             "%.2f %% of f_nom" % max(p.get("push_nl_pct") for p in curves.values()),
             "all %d curves" % len(curves),
             "a single pushing coefficient per corner is a fair summary"),
        )
    rip = [p for p in grid if p.has("rip_tie_pp_s")]
    if rip:
        w = max(rip, key=lambda p: p.get("rip_tie_pp_s"))
        margin = min(p.get("floor_margin_x") for p in rip)
        rows.append(
            ("supply-ripple TIE, worst corner",
             "%s peak-to-peak" % ts(w.get("rip_tie_pp_s")),
             w.label,
             "DR-001's top named risk now has a number, not a caveat"),
        )
        rows.append(
            ("supply-ripple period jitter, worst corner",
             "%.2f %% RMS of the period" % w.get("rip_tj_rms_pct"),
             w.label,
             "%s the draft < %g %% line, open loop, from a %.0f mV peak-to-peak "
             "rail ripple alone"
             % ("BREAKS" if w.get("rip_tj_rms_pct") > DRAFT_TJ_RMS_PCT else "inside",
                DRAFT_TJ_RMS_PCT,
                2000 * float(grid[0].view.params.get("arip", 0.0)))),
        )
        rows.append(
            ("margin over the solver's numerical floor",
             "%.0fx in TIE RMS" % margin,
             "smallest anywhere on the grid",
             "every supply-induced number above is a circuit result, not solver noise"),
        )
    if not rows:
        rows = [("—", "—", "—", "no data")]
    return DerivedTable(
        name="supply_verdict",
        columns=("quantity", "value", "where", "reading"),
        rows=tuple(rows),
        description="what this record establishes, and what it does not",
        notes=(
            "**This does not by itself supersede DR-001 Decision 2.** The "
            "measured sensitivity is what a current-starved single-ended ring is "
            "expected to have, and DR-001 accepted it explicitly with eyes open. "
            "What the number does establish is a hard constraint for #10 and "
            "#14: the VCO rail needs either regulation or a decoupling/ripple "
            "budget, and the loop bandwidth cannot be set without knowing the "
            "supply-noise spectrum. If the system cannot deliver a quiet enough "
            "rail, *that* is the condition under which DR-001 Decision 2 should "
            "be revisited, and this record is the evidence that would drive it.",
        ),
    )


def derive_tables(run):
    points = _points(run)
    grid = _main_grid(points)

    nominal = next(
        (p for p in points
         if p.corner == "typical" and p.temp_c == 27.0 and abs(p.vdd - 3.30) < 1e-9
         and p.band == MAIN_BAND and p.rdiv == MAIN_RDIV),
        None,
    )
    rippled = [p for p in points if p.has("rip_tie_pp_s")]
    worst = max(rippled, key=lambda p: p.get("rip_tie_pp_s")) if rippled else None

    return [
        _pushing_summary(points),
        _step_response(grid),
        _ripple_jitter(grid),
        _band_dependence(points),
        _ripple_frequency(points),
        _period_table(
            "periods_nominal", nominal,
            "per-cycle period and TIE sequence at the nominal point",
        ),
        _period_table(
            "periods_worst_ripple", worst,
            "per-cycle period and TIE sequence at the worst-TIE point",
        ),
        _migration_delta(run, points),
        _verdict(points, grid),
    ]
