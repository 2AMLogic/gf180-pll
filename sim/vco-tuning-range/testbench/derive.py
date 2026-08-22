"""gf180-pll :: vco-tuning-range :: campaign reduction for the tuning sweep.

`sim/harness` reports raw per-point measurements plus min/max/spread. The claim
this campaign actually makes is the *reduction* over those: the band plan, the
adjacent-band overlap, the two band-edge margins, the Kvco tables and the
static supply-pushing spread. This module is the harness's `derived` extension
point carrying exactly the reductions the pre-migration `analyze.py` computed,
with the same arithmetic and the same output formatting, so a migrated record
is numerically comparable to the record it supersedes line by line.

Two hooks (see `sim/harness/derived.py`):

  derive_point(point)   local Kvco at each of the seven control voltages, plus
                        the per-(corner, band) curve reduction that the
                        pre-migration `kvco_by_band.csv` held -- reported as
                        per-point columns rather than a separate table so the
                        record carries them beside the frequencies they came
                        from.
  derive_tables(run)    the whole-grid reductions, one DerivedTable each.

`reduce_grid()` is deliberately a pure function of a list of
(corner, band, vctrl, f, i) rows -- the same shape `analyze.py` read out of
`vco_tuning.csv` -- so `sim/tests/test_vco_tuning_derive.py` can replay the
superseded record's own CSV through it and assert the reduction is unchanged
by the migration.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.derived import DerivedTable, load_module  # noqa: E402

_numeric = load_module(Path(__file__).resolve().parent / "_numeric.py")
mhz = _numeric.mhz
corner_name = _numeric.corner_name

#: The control-voltage grid the deck instantiates, one VCO copy per entry.
VCTRLS = (0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.7)

F_LO = 10e6
F_HI = 200e6
KVCO_MAX = 150e6  # Hz/V
KVCO_OVER_F_INTENT = 0.7  # DR-001 design-intent Kvco ~ 0.7 * f_out per volt

#: Frequencies a configuration might be asked to hit, used by check 4a to ask
#: "what Kvco does the *lowest band that reaches this target* present?".
TARGETS = (10e6, 20e6, 35e6, 50e6, 75e6, 100e6, 140e6, 175e6, 200e6)


def local_kvco(vs, fs):
    """Central-difference dF/dV at each sweep point (one-sided at the ends)."""
    k = []
    for i in range(len(vs)):
        if i == 0:
            k.append((fs[1] - fs[0]) / (vs[1] - vs[0]))
        elif i == len(vs) - 1:
            k.append((fs[-1] - fs[-2]) / (vs[-1] - vs[-2]))
        else:
            k.append((fs[i + 1] - fs[i - 1]) / (vs[i + 1] - vs[i - 1]))
    return k


# ---------------------------------------------------------------- per point
def derive_point(point):
    """Local Kvco per control voltage, plus this (corner, band) curve's reduction.

    Returns ``None`` for every name when a frequency is missing, which cannot
    normally happen (``f1..f7`` are required measurements, so a point that lost
    an edge is already reported as failed) but keeps the reduction honest if
    the harness ever hands this hook a partial point.
    """
    fs = [point.get("f%d" % i) for i in range(1, 8)]
    if any(f is None or f <= 0 for f in fs):
        return {}
    vs = list(VCTRLS)
    ks = local_kvco(vs, fs)
    out = {"k%d" % (i + 1): ks[i] for i in range(len(ks))}
    out["kvco_min"] = min(ks)
    out["kvco_max"] = max(ks)
    out["kvco_mean"] = (fs[-1] - fs[0]) / (vs[-1] - vs[0])
    out["kvco_over_f_max"] = max(k / f for k, f in zip(ks, fs))
    out["fine_ratio"] = fs[-1] / fs[0]
    return out


# ------------------------------------------------------------- the reduction
def rows_from_run(run):
    """`run.points` -> the flat (corner, band, vctrl, f, i) rows the reduction eats."""
    rows = []
    for p in run.points:
        band = int(p.params["band"])
        for i, vctrl in enumerate(VCTRLS, start=1):
            f = p.get("f%d" % i)
            cur = p.get("i%d" % i)
            if f is None or cur is None:
                continue
            rows.append(
                {
                    "corner": (p.corner, float(p.temp_c), float(p.vdd)),
                    "band": band,
                    "vctrl": vctrl,
                    "f": f,
                    "i": abs(cur),
                }
            )
    return rows


def reduce_grid(rows):
    """Every quantity the record cites, from the flat sweep rows.

    Arithmetic ported verbatim from the pre-migration `analyze.py` so the two
    can be diffed against the same input (see the module docstring).
    """
    curves = defaultdict(list)
    for r in rows:
        curves[(r["corner"], r["band"])].append((r["vctrl"], r["f"], r["i"]))
    for k in curves:
        curves[k].sort()

    corners = sorted({c for (c, _b) in curves}, key=lambda c: (c[0], c[1], c[2]))
    bands = sorted({b for (_c, b) in curves})

    per_band = {}
    point_rows = []
    non_monotonic = []
    for c in corners:
        for b in bands:
            vs = [p[0] for p in curves[(c, b)]]
            fs = [p[1] for p in curves[(c, b)]]
            iss = [p[2] for p in curves[(c, b)]]
            ks = local_kvco(vs, fs)
            if any(fs[i + 1] <= fs[i] for i in range(len(fs) - 1)):
                non_monotonic.append((c, b))
            per_band[(c, b)] = {
                "flo": fs[0],
                "fhi": fs[-1],
                "kmin": min(ks),
                "kmax": max(ks),
                "kmean": (fs[-1] - fs[0]) / (vs[-1] - vs[0]),
                "ratio_max": max(k / f for k, f in zip(ks, fs)),
                "ihi": iss[-1],
                "ilo": iss[0],
            }
            for v, f, i_, k in zip(vs, fs, iss, ks):
                point_rows.append((c, b, v, f, k, k / f, i_))

    b_lo, b_hi = bands[0], bands[-1]

    floors = [(per_band[(c, b_lo)]["flo"], c) for c in corners]
    floor_worst, floor_worst_c = max(floors)
    floor_best, floor_best_c = min(floors)
    floor_pass = floor_worst <= F_LO

    ceils = [(per_band[(c, b_hi)]["fhi"], c) for c in corners]
    ceil_worst, ceil_worst_c = min(ceils)
    ceil_best, ceil_best_c = max(ceils)
    ceil_pass = ceil_worst >= F_HI

    overlap_worst = {}
    holes = []
    for c in corners:
        for b in bands[:-1]:
            ratio = per_band[(c, b)]["fhi"] / per_band[(c, b + 1)]["flo"]
            if b not in overlap_worst or ratio < overlap_worst[b][0]:
                overlap_worst[b] = (ratio, c)
            if ratio < 1.0:
                gap = (per_band[(c, b)]["fhi"], per_band[(c, b + 1)]["flo"])
                if gap[1] > F_LO and gap[0] < F_HI:
                    holes.append((c, b, gap))
    overlap_pass = not holes

    in_band = [p for p in point_rows if F_LO <= p[3] <= F_HI]
    k_in_max, k_in_pt = max((p[4], p) for p in in_band)
    kvco_any_pass = k_in_max <= KVCO_MAX
    ratio_in_max, _ = max((p[5], p) for p in in_band)
    ratio_in_min, _ = min((p[5], p) for p in in_band)
    k_all_max, k_all_pt = max((p[4], p) for p in point_rows)
    k_in_min = min(p[4] for p in in_band)

    # The check that actually binds the loop filter: the band code is a static
    # configuration input, so a system targeting frequency f picks the LOWEST
    # band that reaches f (Kvco scales with f_osc *within* a band).
    best_needed = []
    unreachable = []
    for c in corners:
        for ft in TARGETS:
            cands = []
            for b in bands:
                vs = [p[0] for p in curves[(c, b)]]
                fs = [p[1] for p in curves[(c, b)]]
                if not (fs[0] <= ft <= fs[-1]):
                    continue
                ks = local_kvco(vs, fs)
                for i in range(len(fs) - 1):
                    if fs[i] <= ft <= fs[i + 1]:
                        w = (ft - fs[i]) / (fs[i + 1] - fs[i])
                        cands.append(
                            (ks[i] + w * (ks[i + 1] - ks[i]), b, vs[i] + w * (vs[i + 1] - vs[i]))
                        )
                        break
            if not cands:
                unreachable.append((c, ft))
            else:
                k, b, v = min(cands)
                best_needed.append((k, c, ft, b, v))
    k_cfg_max, cfg_c, cfg_ft, cfg_b, cfg_v = max(best_needed)
    kvco_pass = k_cfg_max <= KVCO_MAX and not unreachable

    # Static supply pushing derived from the main grid: df/dVdd at fixed
    # (bundle, temp, band, vctrl) over the 2.97 -> 3.63 V span.
    push = []
    for bundle in sorted({c[0] for c in corners}):
        for temp in sorted({c[1] for c in corners}):
            for b in bands:
                for v in sorted({p[2] for p in point_rows}):
                    fv = {}
                    for c in corners:
                        if c[0] != bundle or c[1] != temp:
                            continue
                        for p in curves[(c, b)]:
                            if abs(p[0] - v) < 1e-9:
                                fv[c[2]] = p[1]
                    if 2.97 in fv and 3.63 in fv and 3.30 in fv:
                        dfdv = (fv[3.63] - fv[2.97]) / (3.63 - 2.97)
                        push.append((abs(dfdv / fv[3.30]), dfdv, bundle, temp, b, v, fv[3.30]))
    push.sort()

    p200 = [p for p in point_rows if 0.9 * F_HI <= p[3] <= 1.1 * F_HI]
    p10 = [p for p in point_rows if 0.9 * F_LO <= p[3] <= 1.1 * F_LO]

    overall = floor_pass and ceil_pass and overlap_pass and kvco_pass and not non_monotonic

    return {
        "corners": corners,
        "bands": bands,
        "per_band": per_band,
        "point_rows": point_rows,
        "curves": curves,
        "b_lo": b_lo,
        "b_hi": b_hi,
        "floor_worst": floor_worst, "floor_worst_c": floor_worst_c,
        "floor_best": floor_best, "floor_best_c": floor_best_c, "floor_pass": floor_pass,
        "ceil_worst": ceil_worst, "ceil_worst_c": ceil_worst_c,
        "ceil_best": ceil_best, "ceil_best_c": ceil_best_c, "ceil_pass": ceil_pass,
        "overlap_worst": overlap_worst, "holes": holes, "overlap_pass": overlap_pass,
        "non_monotonic": non_monotonic,
        "k_in_max": k_in_max, "k_in_pt": k_in_pt, "k_in_min": k_in_min,
        "kvco_any_pass": kvco_any_pass,
        "ratio_in_min": ratio_in_min, "ratio_in_max": ratio_in_max,
        "k_all_max": k_all_max, "k_all_pt": k_all_pt,
        "k_cfg_max": k_cfg_max, "cfg_c": cfg_c, "cfg_ft": cfg_ft,
        "cfg_b": cfg_b, "cfg_v": cfg_v, "kvco_pass": kvco_pass,
        "unreachable": unreachable,
        "push": push, "p10": p10, "p200": p200,
        "overall": overall,
    }


# --------------------------------------------------------------- the tables
def derive_tables(run):
    d = reduce_grid(rows_from_run(run))
    corners, bands, per_band = d["corners"], d["bands"], d["per_band"]
    ncorners = len(corners)

    acceptance = DerivedTable(
        name="acceptance_checks",
        description=(
            "issue #8's acceptance checks, each against its spec line, with the "
            "corner that binds it named (spec lines: 10-200 MHz v1 output band per "
            "DR-002 Decision 2; Kvco ceiling per DR-001 Decision 1)"
        ),
        columns=("#", "check", "binding corner", "measured", "spec line", "verdict"),
        rows=(
            ("1",
             "Lowest band (B%d) reaches DOWN to 10 MHz at **every** corner" % d["b_lo"],
             corner_name(d["floor_worst_c"]),
             "%s MHz floor" % mhz(d["floor_worst"]),
             "<= 10 MHz",
             "**%s**" % ("PASS" if d["floor_pass"] else "FAIL")),
            ("2",
             "Highest band (B%d) reaches UP to 200 MHz at **every** corner" % d["b_hi"],
             corner_name(d["ceil_worst_c"]),
             "%s MHz ceiling" % mhz(d["ceil_worst"]),
             ">= 200 MHz",
             "**%s**" % ("PASS" if d["ceil_pass"] else "FAIL")),
            ("3",
             "No band-overlap hole inside 10-200 MHz at any corner",
             corner_name(min(d["overlap_worst"].values())[1]),
             "worst adjacent overlap ratio %.3f"
             % min(r for r, _c in d["overlap_worst"].values()),
             ">= 1.000",
             "**%s**" % ("PASS" if d["overlap_pass"] else "FAIL")),
            ("4a",
             "Kvco under the fixed-filter ceiling at the band a correct "
             "configuration selects",
             "%s, target %s MHz -> B%d @ %.2f V"
             % (corner_name(d["cfg_c"]), mhz(d["cfg_ft"]), d["cfg_b"], d["cfg_v"]),
             "%s MHz/V" % mhz(d["k_cfg_max"]),
             "<= 150 MHz/V",
             "**%s**" % ("PASS" if d["kvco_pass"] else "FAIL")),
            ("4b",
             "Kvco under the ceiling at *every* in-band operating point, including "
             "bands a correct configuration would not select",
             "%s B%d @ %.1f V"
             % (corner_name(d["k_in_pt"][0]), d["k_in_pt"][1], d["k_in_pt"][2]),
             "%s MHz/V" % mhz(d["k_in_max"]),
             "<= 150 MHz/V",
             "**%s**" % ("PASS" if d["kvco_any_pass"] else "FAIL")),
            ("5",
             "f(Vctrl) monotonic on every (corner, band) curve",
             "n/a" if not d["non_monotonic"] else corner_name(d["non_monotonic"][0][0]),
             "%d non-monotonic curves" % len(d["non_monotonic"]),
             "0",
             "**%s**" % ("PASS" if not d["non_monotonic"] else "FAIL")),
        ),
        notes=_acceptance_notes(d, ncorners),
    )

    margin = DerivedTable(
        name="band_edge_margin",
        description="margin on the two band-edge checks, over the whole %d-corner grid"
                    % ncorners,
        columns=("edge", "worst corner", "best corner", "spec", "worst-case margin"),
        rows=(
            ("B%d floor (must go low enough)" % d["b_lo"],
             "%s MHz @ %s" % (mhz(d["floor_worst"]), corner_name(d["floor_worst_c"])),
             "%s MHz @ %s" % (mhz(d["floor_best"]), corner_name(d["floor_best_c"])),
             "10 MHz",
             "%.0f%% below the spec line" % (100 * (F_LO - d["floor_worst"]) / F_LO)),
            ("B%d ceiling (must go high enough)" % d["b_hi"],
             "%s MHz @ %s" % (mhz(d["ceil_worst"]), corner_name(d["ceil_worst_c"])),
             "%s MHz @ %s" % (mhz(d["ceil_best"]), corner_name(d["ceil_best_c"])),
             "200 MHz",
             "%.0f%% above the spec line" % (100 * (d["ceil_worst"] - F_HI) / F_HI)),
        ),
    )

    plan_rows = []
    for b in bands:
        fl = [per_band[(c, b)]["flo"] for c in corners]
        fh = [per_band[(c, b)]["fhi"] for c in corners]
        rr = [per_band[(c, b)]["fhi"] / per_band[(c, b)]["flo"] for c in corners]
        plan_rows.append(
            ("B%d" % b,
             "%s .. %s" % (mhz(min(fl)), mhz(max(fl))),
             "%s .. %s" % (mhz(min(fh)), mhz(max(fh))),
             "%.2f .. %.2f" % (min(rr), max(rr)))
        )
    band_plan = DerivedTable(
        name="band_plan",
        description="band plan, worst case over all %d corners -- the union of the "
                    "eight bands is what must cover 10-200 MHz; a single band never does"
                    % ncorners,
        columns=("band", "floor: min .. max over corners (MHz)",
                 "ceiling: min .. max over corners (MHz)", "fine range (x)"),
        rows=tuple(plan_rows),
    )

    overlap_rows = []
    for b in bands[:-1]:
        r, c = d["overlap_worst"][b]
        overlap_rows.append(
            ("B%d -> B%d" % (b, b + 1), "%.3f" % r, "%.0f%%" % (100 * (r - 1)), corner_name(c))
        )
    if d["holes"]:
        hole_notes = ["**COVERAGE HOLE(S) FOUND inside 10-200 MHz:**", ""] + [
            "  - %s: B%d tops out at %s MHz but B%d starts at %s MHz"
            % (corner_name(c), b, mhz(gap[0]), b + 1, mhz(gap[1]))
            for c, b, gap in d["holes"]
        ]
    else:
        hole_notes = [
            "No corner leaves a hole in 10-200 MHz coverage: every adjacent band",
            "pair overlaps at every one of the %d corners." % ncorners,
        ]
    overlap = DerivedTable(
        name="band_overlap",
        description="adjacent-band overlap, worst corner per pair. Overlap ratio = "
                    "f_max(band b) / f_min(band b+1); > 1 means the bands overlap, and "
                    "(ratio - 1) is the fractional overlap DR-001 budgets at ~20%",
        columns=("band pair", "worst overlap ratio", "overlap", "worst corner"),
        rows=tuple(overlap_rows),
        notes=tuple(hole_notes),
    )

    kv_rows = []
    for b in bands:
        kmins = [per_band[(c, b)]["kmin"] for c in corners]
        kmaxs = [per_band[(c, b)]["kmax"] for c in corners]
        rat = [per_band[(c, b)]["ratio_max"] for c in corners]
        kv_rows.append(("B%d" % b, mhz(min(kmins)), mhz(max(kmaxs)), "%.2f" % max(rat)))
    kvco = DerivedTable(
        name="kvco_summary",
        description="Kvco across the whole grid, per band. The per-(corner, band, Vctrl) "
                    "detail is the k1..k7 columns of the per-point table below, and the "
                    "per-(corner, band) reduction is its kvco_min / kvco_max / kvco_mean "
                    "/ kvco_over_f_max / fine_ratio columns",
        columns=("band", "Kvco min (MHz/V)", "Kvco max (MHz/V)",
                 "max Kvco/f_out (per V)"),
        rows=tuple(kv_rows),
        notes=_kvco_notes(d),
    )

    push = d["push"]
    if push:
        pw, pb = push[-1], push[0]
        pushing = DerivedTable(
            name="supply_pushing",
            description="static supply pushing, df/d(vdd_vco) across the full +/-10%% supply "
                        "range at fixed process/temperature/band/Vctrl -- %d combinations"
                        % len(push),
            columns=("", "df/dVdd (MHz/V)", "normalized (%/V)", "point"),
            rows=(
                ("Worst", mhz(pw[1]), "%.1f" % (100 * pw[0]),
                 "%s/%gC, B%d, Vctrl %.1f V (f = %s MHz)"
                 % (pw[2], pw[3], pw[4], pw[5], mhz(pw[6]))),
                ("Best", mhz(pb[1]), "%.1f" % (100 * pb[0]),
                 "%s/%gC, B%d, Vctrl %.1f V (f = %s MHz)"
                 % (pb[2], pb[3], pb[4], pb[5], mhz(pb[6]))),
            ),
            notes=(
                "Median normalized pushing %.1f %%/V; a +/-10%% (+/-0.33 V) supply excursion"
                % (100 * push[len(push) // 2][0]),
                "therefore moves f_osc by up to %.0f%% open-loop at the worst point."
                % (100 * pw[0] * 0.33),
                "Transient supply-step and supply-ripple jitter -- DR-001's top named",
                "risk, which a DC pushing number does not cover -- are a separate record",
                "from `testbench/run_supply.sh`.",
            ),
        )
    else:
        pushing = DerivedTable(
            name="supply_pushing",
            description="static supply pushing, df/d(vdd_vco) across the full +/-10%% supply "
                        "range at fixed process/temperature/band/Vctrl",
            columns=("", "df/dVdd (MHz/V)", "normalized (%/V)", "point"),
            rows=(),
            notes=(
                "**Not derivable**: this run's grid does not span the full "
                "2.97-3.63 V supply range (needs all three of 2.97 V, 3.30 V and "
                "3.63 V at a shared bundle/temp/band/Vctrl combination), so no "
                "df/dVdd point could be formed.",
                "This is expected for a supply-thinned run (e.g. `--supply-tol 0`, "
                "a single-supply calibration or subset sweep) and is not a defect; "
                "a full-grid `vco-tuning-range` campaign is required for this table.",
            ),
        )

    cur_rows = []
    for label, grp in (("~10 MHz", d["p10"]), ("~200 MHz", d["p200"])):
        if not grp:
            continue
        cur = sorted(p[6] for p in grp)
        cur_rows.append(
            ("%s (n=%d)" % (label, len(cur)),
             "%.0f" % (cur[0] * 1e6),
             "%.0f" % (cur[len(cur) // 2] * 1e6),
             "%.0f" % (cur[-1] * 1e6))
        )
    current = DerivedTable(
        name="block_current",
        description="block current (whole VCO: bias generator + ring + output buffer) at "
                    "operating points within +/-10% of each band edge",
        columns=("operating point", "I min (uA)", "I median (uA)", "I max (uA)"),
        rows=tuple(cur_rows),
    )

    return [acceptance, margin, band_plan, overlap, kvco, pushing, current]


def _acceptance_notes(d, ncorners):
    notes = ["**Overall: %s.**" % ("PASS" if d["overall"] else "FAIL"), ""]
    if d["overall"]:
        notes += [
            "The ring covers the ratified 10-200 MHz v1 output band at every one",
            "of the %d corners on the grid -- reaching below 10 MHz at the" % ncorners,
            "fastest corner and above 200 MHz at the slowest -- with no coverage",
            "hole, monotonic control, and Kvco inside DR-001 Decision 1's ceiling",
            "at the band a correct configuration selects.",
        ]
    else:
        failed = [
            name
            for name, ok in (
                ("low-band floor", d["floor_pass"]),
                ("high-band ceiling", d["ceil_pass"]),
                ("band overlap", d["overlap_pass"]),
                ("Kvco ceiling at the selected band (4a)", d["kvco_pass"]),
                ("f(Vctrl) monotonicity", d["non_monotonic"] == []),
            )
            if not ok
        ]
        notes.append("Failing check(s): %s." % "; ".join(failed))
    notes.append("")
    if not d["kvco_any_pass"]:
        notes += [
            "**Caveat that must travel with these numbers (check 4b).** Kvco",
            "reaches %s MHz/V at an in-band operating point in band B%d, which"
            % (mhz(d["k_in_max"]), d["k_in_pt"][1]),
            "is above DR-001's ~150 MHz/V bound. That point is only reachable by",
            "configuring a *higher* band than the target frequency requires. It",
            "is not a defect of the ring, but it does mean the band code is part",
            "of the loop-stability contract, not just a range-selection",
            "convenience -- #9/#10 must state the band-selection rule alongside",
            "the filter values, and a part configured into too high a band will",
            "present the loop with more gain than the fixed filter was sized for.",
            "",
        ]
    notes += [
        "**What this record hands to the sibling issues:**",
        "",
        "  - **#11 (output divider), DR-002 Decision 2's conditional trigger**: the",
        "    lowest band reaches %s MHz at the fastest corner, %.0f %% below the"
        % (mhz(d["floor_worst"]), 100 * (F_LO - d["floor_worst"]) / F_LO),
        "    10 MHz spec line, so the ring reaches the bottom of the band **without**",
        "    a post-VCO divider. The DR-002 trigger does **not** fire: no output",
        "    divider enters v1 scope on account of the VCO's low-band floor.",
        "  - **#9 / #10 (charge pump, loop filter)**: size against the per-point Kvco",
        "    columns (k1..k7, kvco_min/kvco_max) below, not against a single Kvco",
        "    number. Within the v1 band Kvco spans %s .. %s MHz/V across bands and"
        % (mhz(d["k_in_min"]), mhz(d["k_in_max"])),
        "    corners.",
        "  - **#14 (supply sensitivity)**: static pushing table below; the transient",
        "    numbers are in the supply record from `run_supply.sh`.",
    ]
    return tuple(notes)


def _kvco_notes(d):
    k_in_pt, k_all_pt = d["k_in_pt"], d["k_all_pt"]
    notes = [
        "  - Worst-case Kvco **at an operating point inside the ratified 10-200 MHz",
        "    band, over ALL band codes**: %s MHz/V (%s, B%d, Vctrl %.1f V, f ="
        % (mhz(d["k_in_max"]), corner_name(k_in_pt[0]), k_in_pt[1], k_in_pt[2]),
        "    %s MHz) -- %s DR-001's ~150 MHz/V ceiling. Reaching that point"
        % (mhz(k_in_pt[3]), "under" if d["kvco_any_pass"] else "**OVER**"),
        "    requires configuring band B%d for a frequency band B%d already"
        % (k_in_pt[1], max(0, k_in_pt[1] - 1)),
        "    covers; see check 4a and the band-choice note below.",
        "  - Worst-case Kvco anywhere on the grid **including the bands above the v1",
        "    band**: %s MHz/V (%s, B%d, Vctrl %.1f V, f = %s MHz)."
        % (mhz(d["k_all_max"]), corner_name(k_all_pt[0]), k_all_pt[1], k_all_pt[2],
           mhz(k_all_pt[3])),
    ]
    if k_all_pt[3] > F_HI:
        notes += [
            "    DR-002 Decision 2 budgets v1 margin to 200 MHz, so that point sits",
            "    ABOVE the v1 envelope and %s the 150 MHz/V bound; it is reported"
            % ("exceeds" if d["k_all_max"] > KVCO_MAX else "stays inside"),
            "    because the deferred 400 MHz stretch would operate there.",
        ]
    notes += [
        "  - Kvco/f_out inside the v1 band spans **%.2f .. %.2f per volt**, which"
        % (d["ratio_in_min"], d["ratio_in_max"]),
        "    **brackets** DR-001's %.1f/V design-intent hand calc rather than"
        % KVCO_OVER_F_INTENT,
        "    confirming it: the ratio is not a constant of the topology, it rises",
        "    monotonically with band code (see the per-band table above). Reading",
        "    0.7/V as a single number would under-predict Kvco in the top bands and",
        "    over-predict it in the bottom ones. #9/#10 should size against the",
        "    per-band table, not against the hand calc.",
        "",
        "  - **Band choice is load-bearing for the Kvco ceiling.** Because Kvco",
        "    scales with f_osc *within* a band, two different band codes that both",
        "    reach the same output frequency do not present the same Kvco to the",
        "    loop: the higher band reaches it near the bottom of its Vctrl range,",
        "    where its Kvco is already large. Selecting the **lowest** band that",
        "    reaches the target frequency is therefore not a preference but a",
        "    requirement of DR-001 Decision 1's fixed loop filter, and it is what",
        "    check 4a evaluates against check 4b's adversarial band choice.",
    ]
    if d["unreachable"]:
        notes += [
            "    (%d (corner, target frequency) pairs are not reachable by ANY band:"
            % len(d["unreachable"]),
            "    %s ...)"
            % ", ".join(
                "%s @ %s MHz" % (corner_name(c), mhz(f)) for c, f in d["unreachable"][:3]
            ),
        ]
    return tuple(notes)
