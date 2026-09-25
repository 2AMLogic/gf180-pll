#!/usr/bin/env python3
"""gf180-pll :: supply-sensitivity :: what the three FAILing criteria are, read
against the *ratified* spec lines rather than against the deck's own proxies
(issue #506).

    python3 fail_criteria_reexamination.py [source-record-id] [--outdir DIR]

`sim/supply-sensitivity/records/20260901-155456-46b92f8.md` records FAIL on
three criteria and routes each class of finding, by name, to #9, #10 and #11.
All three of those issues are closed, so the findings are recorded and unowned
-- which is issue #506. Giving them an owner needs the findings said precisely
first, and two of the three turn out not to say what the record's headline
says. This script RE-SIMULATES NOTHING: every number it emits is arithmetic on
artifacts already committed under prior records, read and never modified
(`sim/README.md`'s append-only rule).

Three questions, one CSV each.

CRITERION 1 -- "output frequency vs. supply: FAIL, 10 of 45 corners"
    The verdict column is the LOCK CRITERION, five checks against three
    blocks, and the record's own breakdown attributes 0 of the 10 to either
    frequency check. This script tallies the classes from the committed
    verdict column (so the "0" is read, not quoted) and reports each row's
    headroom against both frequency criteria. It then JOINS the verdict class
    to DR-012's committed `settled` flag for the same row -- a join nobody has
    made -- because the record routed 2 corners to the charge pump and 8 to
    the lock detector, and DR-012 later measured that neither of the charge
    pump's 2 was settled while both settled violations of the ratified 1 ns
    bound sit inside the lock detector's 8.

CRITERION 1b -- "control voltage inside DR-001's usable window: FAIL, 4 of 45"
    Two independent re-readings.
      (a) The window. The check was applied against DR-001 Decision 2's
          PREDICTED 0.9-2.4 V window. DR-003 Decision 5 later MEASURED the
          usable window at 0.9-2.7 V on 504 f(Vctrl) curves and supersedes
          that prediction. Both gradings are emitted side by side, with the
          signed margin to each window's binding edge.
      (b) The budget. `spec/pll.md` row 12's normative Budget 2 -- "a DC rail
          excursion over 2.97-3.63 V must consume <= 0.6 V of the Vctrl
          window" -- is not the check the record ran, and nothing has ever
          graded the grid against it. The consumption is emitted under BOTH
          excursions, because the row states 0.66 V while the derivation
          beneath it prices 0.33 V (`%/V x 0.33 V`, which is how its own
          pushing table computes "worst frequency shift over a +/-10 % rail"),
          and the two readings do not agree on whether the row is met.
    A per-cell cross-check against #8's committed open-loop f(Vctrl, vdd)
    table asks whether the measured consumption is anomalous or is exactly
    what the selected band requires: the control voltage at which the SAME
    band reaches the SAME frequency at 3.63 V as it does at 2.97 V, by linear
    interpolation inside the one bracketing interval of the measured curve --
    never extrapolated, the same rule the source record's own warm start used.

CRITERION 3 -- "stays locked through a supply step and a ramp: FAIL, 1 of 3"
    Section 3c classifies `ss`/-40 C `under-damped` from the ratio of two
    frequency-residual samples 28 us apart against `exp(-dt/tau)`. That
    discriminant assumes the recovery IS an exponential at the loop's own
    pole. This script asks the retained END-plateau waveform whether it is:
    for each corner it finds the instant the ripple-averaged control node
    arrives at its final value, fits BOTH a straight line and a single
    exponential to the samples before that instant, and compares their
    residuals IN VOLTS on the same samples. It also reports the phase still
    outstanding at the extended hold's own end and how long the hold's own
    measured slip rate needs to close it.

Reads, and never modifies:
    sim/supply-sensitivity/corners/<src>/supply_steady.csv
    sim/supply-sensitivity/corners/<src>/supply_dynamic.csv
    sim/supply-sensitivity/corners/<src>/dyn_end_settling_rerun.csv
    sim/supply-sensitivity/corners/<src>/supply_transient_<corner>_3.30v_end.csv
    sim/supply-sensitivity/corners/20260916-051708-8cedbba/static_phase_widened.csv
        (DR-012 / #394: the per-row `settled` flag and `over_ratified` grading)
    sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv
        (#8: the same open-loop table the source record derived its band and
        warm-start control voltage from)

WHAT THIS SCRIPT DOES NOT DO. It does not re-judge a committed verdict. The
source record stands as the evidence it was; `sim/README.md` is append-only,
and the CSVs here are a separate record's columns, not an edit of its own. It
also decides nothing: which excursion Budget 2 governs is a ratification
question, and the decision record that cites this file routes it rather than
answering it.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ratified constants. Every one of these is a spec or decision-record value,
# cited where it is defined so a reader can check it rather than trust it.
# ---------------------------------------------------------------------------

#: `spec/pll.md` "Supply sensitivity" Budget 2, and row 12 of the summary table.
BUDGET2_V = 0.6

#: `spec/pll.md` row 18 (Supply range): 3.3 V +/- 10 %, the three graded points.
RAIL_LO_V, RAIL_NOM_V, RAIL_HI_V = 2.97, 3.30, 3.63

#: DR-001 Decision 2 -- the PREDICTED usable control window ("roughly
#: 0.9-2.4 V"). The source record's criterion 1b grades against this.
DR001_WINDOW_V = (0.9, 2.4)

#: DR-003 Decision 5 -- the MEASURED usable control window, "wider than the
#: 0.9-2.4 V DR-001 predicted", monotonic on all 504 measured curves. This
#: supersedes the prediction above and is the current ratified window
#: (`spec/pll.md` "Band-selection rule" and the Budget 2 derivation both
#: state 0.9-2.7 V).
DR003_WINDOW_V = (0.9, 2.7)

#: `spec/pll.md` "Lock time": the dominant closed-loop pole,
#: 1/(2 pi R C1) = 17.09 kHz. The same KTAU `run.sh`'s settling escalations
#: and section 3c's `decay_expected` column are built on.
POLE_HZ = 17.09e3
KTAU_S = 1.0 / (2.0 * math.pi * POLE_HZ)

#: The source record's criterion 1 thresholds, restated from its Methodology
#: so the headroom columns below are graded rather than eyeballed.
FDEV_PPM_LIMIT = 1000.0
FERR_LIMIT = 1e-3

#: DR-012 / #394's own record id -- the committed `settled` grading joined in
#: for criterion 1. Named rather than globbed so a reader knows which record's
#: conclusion this analysis is resting on.
DR012_RECORD_ID = "20260916-051708-8cedbba"

#: #8's open-loop f(Vctrl, vdd) table. The source record's Methodology names
#: this exact file as where its band choice and warm start come from, so the
#: cross-check below is against the same evidence, not a different campaign's.
VCO_RECORD_ID = "20260731-175947-0a12e6c"

#: The source record's step/ramp sample, and the profile instant the END
#: plateau is measured from. `t_rend` is read off each waveform's own header
#: comment rather than assumed -- see `read_transient`.
DYN_CORNERS = (("ff", "125"), ("ss", "-40"), ("typical", "27"))

#: Ripple-averaging bin for the control-node trajectory, and the tolerance
#: that defines "arrived". Both are stated here rather than buried: the trace
#: is decimated at 20 ns and carries the loop filter's own ripple, so a
#: single sample is not a position.
BIN_S = 0.5e-6
ARRIVED_TOL_V = 0.020
#: The window at the end of the hold whose mean is taken as the final value.
FINAL_WINDOW_S = 5.0e-6


# ---------------------------------------------------------------------------
# Pure functions. Unit-tested in
# sim/tests/test_supply_sensitivity_fail_reexamination.py against inputs whose
# right answer is known analytically -- these are the judgements a decision
# record rests on, so none of them is allowed to be only spot-checked by eye.
# ---------------------------------------------------------------------------


def vctrl_consumption(vctrl_by_supply: dict[float, float]) -> dict[str, object]:
    """Budget-2 consumption for one (bundle, temperature) cell, both readings.

    `vctrl_by_supply` maps each of the three graded rail points to the control
    voltage the loop settled at there. Raises `KeyError` if a point is
    missing -- a cell measured at two supplies has no full-range span, and
    quietly reporting one would be worse than failing.

    * ``span_full_v``   -- the excursion `spec/pll.md` row 12 names:
      2.97 -> 3.63 V, 0.66 V of rail.
    * ``span_half_v``   -- the worse of the two 0.33 V half-excursions, which
      is the excursion the Budget-2 derivation actually prices (its pushing
      table computes "worst frequency shift over a +/-10 % rail" as %/V x
      0.33 V).
    * ``dvctrl_dvdd``   -- the full span over the full rail, comparable with
      the source record's own `dVctrl/dVdd` column.
    """
    lo = vctrl_by_supply[RAIL_LO_V]
    nom = vctrl_by_supply[RAIL_NOM_V]
    hi = vctrl_by_supply[RAIL_HI_V]
    span_full = abs(hi - lo)
    span_half = max(abs(nom - lo), abs(hi - nom))
    return {
        "vctrl_lo_v": lo,
        "vctrl_nom_v": nom,
        "vctrl_hi_v": hi,
        "span_full_v": span_full,
        "span_half_v": span_half,
        "dvctrl_dvdd": span_full / (RAIL_HI_V - RAIL_LO_V),
        "over_budget_full": span_full > BUDGET2_V,
        "over_budget_half": span_half > BUDGET2_V,
    }


def leaves_window(vmin: float, vmax: float, window: tuple[float, float]) -> bool:
    """Does the control node's RIPPLE PEAK leave `window`?

    Peaks, not the average, deliberately: headroom is lost at the peak of the
    ripple, and a corner whose average sits inside the window while its peak
    leaves it has left it. That is the source record's own rule for criterion
    1b and it is kept here so the two gradings are comparable.
    """
    low, high = window
    return vmin < low or vmax > high


def window_margin_v(vmin: float, vmax: float, window: tuple[float, float]) -> float:
    """Signed margin to the binding edge of `window`; positive means inside."""
    low, high = window
    return min(vmin - low, high - vmax)


def _least_squares(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Slope and intercept of the least-squares line through (xs, ys)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0.0:
        raise ValueError("degenerate fit: every sample is at the same instant")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def recovery_law(
    samples: list[tuple[float, float]], target_v: float
) -> dict[str, object]:
    """Is this recovery a straight line or a single exponential?

    `samples` are (t, v) pairs of the control node over one recovery segment
    and `target_v` is the value it is recovering TO. Both models are fitted to
    the same samples and both residuals are reported **in volts**, so the
    comparison is not an artefact of fitting one model in log space:

    * the line is a least-squares fit of `v` against `t`;
    * the exponential is a least-squares fit of `ln|v - target|` against `t`,
      then evaluated back in volts.

    ``better_fit`` is whichever has the smaller RMS residual in volts. This is
    the discriminant section 3c's `decay_ratio` column cannot make: that ratio
    compares two samples against `exp(-dt/tau)` and therefore ASSUMES the
    second model. Raises `ValueError` on fewer than 4 samples -- a two-point
    "fit" of a two-parameter model has no residual to report.
    """
    if len(samples) < 4:
        raise ValueError(
            f"need >= 4 samples to compare a 2-parameter line against a "
            f"2-parameter exponential; got {len(samples)}"
        )
    ts = [t for t, _ in samples]
    vs = [v for _, v in samples]
    t0 = ts[0]
    xs = [t - t0 for t in ts]

    slope, intercept = _least_squares(xs, vs)
    lin = [intercept + slope * x for x in xs]
    rms_lin = math.sqrt(sum((a - b) ** 2 for a, b in zip(vs, lin)) / len(vs))

    errs = [v - target_v for v in vs]
    if any(e == 0.0 for e in errs) or not (
        all(e > 0.0 for e in errs) or all(e < 0.0 for e in errs)
    ):
        # The samples straddle (or touch) the target, so ln|v - target| is not
        # defined over the whole segment: no exponential about `target_v` can
        # be fitted to them at all. Report the line's residual and say so.
        return {
            "n_samples": len(samples),
            "slope_v_per_s": slope,
            "slope_mv_per_us": slope * 1e-3,
            "rms_linear_v": rms_lin,
            "rms_exponential_v": None,
            "tau_fit_s": None,
            "better_fit": "linear",
        }

    sign = 1.0 if errs[0] > 0.0 else -1.0
    dslope, dintercept = _least_squares(xs, [math.log(abs(e)) for e in errs])
    tau_fit = -1.0 / dslope if dslope != 0.0 else None
    exp_fit = [target_v + sign * math.exp(dintercept + dslope * x) for x in xs]
    rms_exp = math.sqrt(sum((a - b) ** 2 for a, b in zip(vs, exp_fit)) / len(vs))

    return {
        "n_samples": len(samples),
        "slope_v_per_s": slope,
        "slope_mv_per_us": slope * 1e-3,
        "rms_linear_v": rms_lin,
        "rms_exponential_v": rms_exp,
        "tau_fit_s": tau_fit,
        "better_fit": "linear" if rms_lin <= rms_exp else "exponential",
    }


def monotonicity(
    trace: list[tuple[float, float]], final_v: float, tol_v: float = ARRIVED_TOL_V
) -> dict[str, object]:
    """Model-free test of under-damping: does the recovery overshoot and reverse?

    An under-damped second-order recovery goes past its final value and comes
    back, repeatedly; a current-limited slew approaches it from one side and
    stops. `overshoot_v` is the furthest the ripple-averaged trace goes BEYOND
    `final_v` (0 if it never does), and `reversals` counts direction changes
    whose excursion exceeds `tol_v` -- so the loop filter's own ripple, which
    reverses every reference cycle, is not counted as ringing.

    This costs no model at all, which is the point: it is the one statement
    about damping here that does not depend on a fit.
    """
    if not trace:
        return {"overshoot_v": 0.0, "reversals": 0}
    approach_from_above = trace[0][1] > final_v
    overshoot = 0.0
    for _, v in trace:
        past = (final_v - v) if approach_from_above else (v - final_v)
        overshoot = max(overshoot, past)

    reversals = 0
    direction = 0
    anchor = trace[0][1]
    for _, v in trace:
        delta = v - anchor
        if abs(delta) <= tol_v:
            continue
        step = 1 if delta > 0 else -1
        if direction != 0 and step != direction:
            reversals += 1
        direction = step
        anchor = v
    return {"overshoot_v": overshoot, "reversals": reversals}


def time_to_close_phase_s(phi_s: float, ferr: float) -> float | None:
    """How long `ferr` needs to close `phi_s`, at the rate actually measured.

    In a type-II loop a residual fractional frequency error slips the REF->FB
    phase linearly at exactly df/f seconds per second, which is the identity
    the source record's own `ferr` column is defined by. So the remaining
    phase divided by the measured slip rate is the time to close it AT THAT
    RATE -- the optimistic end of a bracket, not a settling-time prediction: a
    decaying response slows as it converges.

    Returns `None` when the residual is not closing at all (same-signed phase
    and slip rate walk it further out) or when the rate is zero.
    """
    if ferr == 0.0:
        return None
    # `ferr` is defined as -(phi_b - phi_a)/(tb - ta): a NEGATIVE ferr walks
    # the phase upward. The residual is closing only when the two have the
    # same sign, i.e. the phase is being driven back toward zero.
    if (phi_s > 0.0) != (ferr > 0.0):
        return None
    return abs(phi_s) / abs(ferr)


def single_pole_decay(dt_s: float, tau_s: float = KTAU_S) -> float:
    """`exp(-dt/tau)` -- the expectation section 3c's `decay_ratio` is read against."""
    return math.exp(-dt_s / tau_s)


# ---------------------------------------------------------------------------
# Readers. Each one names the committed file it reads and fails loudly rather
# than defaulting, because a silently-skipped input would turn a missing
# artifact into a smaller-looking finding.
# ---------------------------------------------------------------------------


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        sys.exit(f"ERROR: {path} not found -- this analysis reads committed evidence only")
    with path.open() as handle:
        body = [line for line in handle if not line.startswith("#")]
    return list(csv.DictReader(body))


def read_transient(path: Path) -> tuple[list[tuple[float, float]], float]:
    """The retained END-plateau waveform, plus the ramp-end instant `t_rend`.

    `t_rend` is parsed out of the waveform's own `# profile:` header line
    ("ramp <a>u..<b>u -> 2.97 V") so the instant the post-ramp hold starts is
    read off the deck that produced the trace rather than restated here.
    """
    if not path.is_file():
        sys.exit(f"ERROR: {path} not found")
    t_rend: float | None = None
    samples: list[tuple[float, float]] = []
    with path.open() as handle:
        reader = csv.reader(handle)
        header: list[str] | None = None
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                text = ",".join(row)
                if "ramp" in text and ".." in text:
                    span = text.split("ramp", 1)[1].split("->", 1)[0].strip()
                    t_rend = _spice_seconds(span.split("..", 1)[1].strip())
                continue
            if header is None:
                header = row
                continue
            rec = dict(zip(header, row))
            samples.append((float(rec["t_s"]), float(rec["vctrl_v"])))
    if t_rend is None:
        sys.exit(f"ERROR: could not read the ramp-end instant from {path}'s own header")
    return samples, t_rend


def _spice_seconds(token: str) -> float:
    """`47.5u` -> 4.75e-05. Only the suffixes this campaign's decks emit."""
    suffixes = {"u": 1e-6, "n": 1e-9, "p": 1e-12, "m": 1e-3}
    token = token.strip()
    factor = suffixes.get(token[-1].lower(), 1.0)
    if factor != 1.0:
        token = token[:-1]
    return float(token) * factor


def bin_mean(
    samples: list[tuple[float, float]], t_from: float, t_to: float, bin_s: float = BIN_S
) -> list[tuple[float, float]]:
    """Ripple-averaged trajectory: the mean of every `bin_s` bin, at its centre."""
    out: list[tuple[float, float]] = []
    edge = t_from
    while edge < t_to:
        chunk = [v for t, v in samples if edge <= t < edge + bin_s]
        if chunk:
            out.append((edge + bin_s / 2.0, sum(chunk) / len(chunk)))
        edge += bin_s
    return out


# ---------------------------------------------------------------------------
# The three analyses.
# ---------------------------------------------------------------------------


def criterion1(src: Path, dr012: Path, out: Path) -> dict[str, object]:
    """Which check failed, per corner, and was the sample settled when taken?"""
    steady = _rows(src / "supply_steady.csv")
    settled = {
        (r["bundle"], r["temp_c"], f"{float(r['vdd_v']):.2f}"): r
        for r in _rows(dr012 / "static_phase_widened.csv")
    }

    classes: dict[str, int] = {}
    written = []
    for r in steady:
        key = (r["bundle"], r["temp_c"], f"{float(r['vdd_v']):.2f}")
        verdict = r["verdict"]
        klass = "PASS" if verdict == "PASS" else verdict.split(":", 1)[1]
        classes[klass] = classes.get(klass, 0) + 1
        dr = settled.get(key)
        if dr is None:
            sys.exit(f"ERROR: DR-012's grading has no row for {key}")
        written.append(
            {
                "bundle": r["bundle"],
                "temp_c": r["temp_c"],
                "vdd_v": r["vdd_v"],
                "verdict": verdict,
                "failing_check": "" if verdict == "PASS" else klass,
                "fdev_ppm": r["fdev_ppm"],
                "fdev_headroom_x": f"{FDEV_PPM_LIMIT / max(abs(float(r['fdev_ppm'])), 1e-9):.1f}",
                "ferr": r["ferr"],
                "ferr_headroom_x": f"{FERR_LIMIT / max(abs(float(r['ferr'])), 1e-12):.1f}",
                "phi_b_ns": dr["phi_b_ns"],
                "d_phi_window_ns": dr["d_phi_window_ns"],
                "settled_dr012": dr["settled"],
                "over_ratified_1ns_dr012": dr["over_ratified"],
            }
        )

    freq_fails = classes.get("ferr", 0) + classes.get("fabs", 0) + classes.get("ndiv", 0)
    over_and_settled = [
        w
        for w in written
        if w["over_ratified_1ns_dr012"] == "yes" and w["settled_dr012"] == "yes"
    ]
    phi_class = [w for w in written if w["failing_check"] == "phi"]

    _write(
        out / "criterion1_verdict_classes.csv",
        [
            "# criterion 1 of 20260901-155456-46b92f8, by FAILING CHECK rather than by count.",
            "# failing_check: the lock criterion is five checks against three blocks; the",
            "#   verdict column names the one that failed. 'phi' = static phase error over the",
            "#   DECK's 0.02-of-a-period threshold (1.6 ns at 12.5 MHz, 1.6x looser than the",
            "#   ratified 1 ns -- DR-012 Decision 5); 'lock' = the block's own LOCK flag did",
            "#   not assert; 'ferr'/'fabs'/'ndiv' = the frequency and divide-ratio checks.",
            "# fdev_headroom_x / ferr_headroom_x: the criterion divided by the measured value.",
            f"#   Criteria: |fdev| <= {FDEV_PPM_LIMIT:.0f} ppm, |ferr| <= {FERR_LIMIT:g}.",
            "# settled_dr012 / over_ratified_1ns_dr012 / phi_b_ns / d_phi_window_ns are read",
            f"#   from DR-012's committed grading ({DR012_RECORD_ID}/static_phase_widened.csv),",
            "#   not recomputed here. The join of that grading to the verdict class is the",
            "#   only new column set in this file.",
        ],
        written,
    )
    return {
        "classes": classes,
        "freq_fails": freq_fails,
        "n_rows": len(written),
        "phi_class": [(w["bundle"], w["temp_c"], w["vdd_v"], w["settled_dr012"]) for w in phi_class],
        "over_and_settled": [
            (w["bundle"], w["temp_c"], w["vdd_v"], w["phi_b_ns"], w["failing_check"])
            for w in over_and_settled
        ],
        "worst_fdev_ppm": max(abs(float(r["fdev_ppm"])) for r in steady),
        "worst_ferr": max(abs(float(r["ferr"])) for r in steady),
    }


def _open_loop_travel(
    tuning: list[dict[str, str]], bundle: str, temp: str, band: str, vctrl_lo: float
) -> float | None:
    """Control voltage the SAME band needs at 3.63 V to hold the frequency it
    makes at 2.97 V with `vctrl_lo` -- by interpolation inside the measured
    curve, never extrapolation."""

    def curve(vdd: float) -> list[tuple[float, float]]:
        pts = [
            (float(r["vctrl_v"]), float(r["fosc_hz"]))
            for r in tuning
            if r["bundle"] == bundle
            and r["temp_c"] == temp
            and abs(float(r["vdd_v"]) - vdd) < 1e-9
            and r["band"] == band
        ]
        return sorted(pts)

    lo_curve, hi_curve = curve(RAIL_LO_V), curve(RAIL_HI_V)
    if len(lo_curve) < 2 or len(hi_curve) < 2:
        return None

    def interp(pts: list[tuple[float, float]], x: float, fwd: bool) -> float | None:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            a, b = (x0, x1) if fwd else (y0, y1)
            if min(a, b) <= x <= max(a, b):
                if fwd:
                    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                return x0 + (x1 - x0) * (x - y0) / (y1 - y0)
        return None

    target = interp(lo_curve, vctrl_lo, fwd=True)
    if target is None:
        return None
    needed = interp(hi_curve, target, fwd=False)
    if needed is None:
        return None
    return needed - vctrl_lo


def criterion1b(src: Path, vco: Path, out: Path) -> dict[str, object]:
    """Budget 2, under both excursions, and both control windows."""
    steady = _rows(src / "supply_steady.csv")
    tuning = _rows(vco / "vco_tuning.csv")

    cells: dict[tuple[str, str], dict[float, dict[str, str]]] = {}
    for r in steady:
        cells.setdefault((r["bundle"], r["temp_c"]), {})[round(float(r["vdd_v"]), 2)] = r

    written = []
    for (bundle, temp), by_vdd in cells.items():
        cons = vctrl_consumption(
            {v: float(by_vdd[v]["vctrl_avg_v"]) for v in (RAIL_LO_V, RAIL_NOM_V, RAIL_HI_V)}
        )
        peaks_min = min(float(r["vctrl_min_v"]) for r in by_vdd.values())
        peaks_max = max(float(r["vctrl_max_v"]) for r in by_vdd.values())
        band = by_vdd[RAIL_NOM_V]["band"]
        predicted = _open_loop_travel(tuning, bundle, temp, band, cons["vctrl_lo_v"])
        written.append(
            {
                "bundle": bundle,
                "temp_c": temp,
                "band": band,
                "vctrl_lo_v": f"{cons['vctrl_lo_v']:.4f}",
                "vctrl_nom_v": f"{cons['vctrl_nom_v']:.4f}",
                "vctrl_hi_v": f"{cons['vctrl_hi_v']:.4f}",
                "peak_min_v": f"{peaks_min:.4f}",
                "peak_max_v": f"{peaks_max:.4f}",
                "span_full_v": f"{cons['span_full_v']:.4f}",
                "span_half_v": f"{cons['span_half_v']:.4f}",
                "dvctrl_dvdd": f"{cons['dvctrl_dvdd']:.4f}",
                "over_budget2_full_range": "yes" if cons["over_budget_full"] else "no",
                "over_budget2_half_range": "yes" if cons["over_budget_half"] else "no",
                "leaves_dr001_window": "yes" if leaves_window(peaks_min, peaks_max, DR001_WINDOW_V) else "no",
                "leaves_dr003_window": "yes" if leaves_window(peaks_min, peaks_max, DR003_WINDOW_V) else "no",
                "margin_dr001_v": f"{window_margin_v(peaks_min, peaks_max, DR001_WINDOW_V):+.4f}",
                "margin_dr003_v": f"{window_margin_v(peaks_min, peaks_max, DR003_WINDOW_V):+.4f}",
                "openloop_predicted_travel_v": "n/a" if predicted is None else f"{predicted:.4f}",
                "predicted_minus_measured_v": (
                    "n/a" if predicted is None else f"{predicted - cons['span_full_v']:+.4f}"
                ),
            }
        )
    written.sort(key=lambda w: float(w["span_full_v"]), reverse=True)

    _write(
        out / "criterion1b_vctrl_budget.csv",
        [
            "# criterion 1b of 20260901-155456-46b92f8, re-read against the RATIFIED lines.",
            f"# Budget 2 (spec/pll.md row 12): a DC rail excursion must consume <= {BUDGET2_V} V",
            "#   of the control window. span_full_v is that excursion as the ROW states it",
            f"#   ({RAIL_LO_V}-{RAIL_HI_V} V, {RAIL_HI_V - RAIL_LO_V:.2f} V of rail); span_half_v is the worse of the",
            f"#   two {RAIL_HI_V - RAIL_NOM_V:.2f} V half-excursions, which is the excursion the budget's own",
            "#   derivation prices (its pushing table computes 'worst frequency shift over a",
            "#   +/-10 % rail' as %/V x 0.33 V). The two do not agree on whether the row is met;",
            "#   that disagreement is the finding, and this file does not resolve it.",
            f"# leaves_dr001_window: DR-001 Decision 2's PREDICTED {DR001_WINDOW_V} V window -- what",
            "#   the source record's own 1b check graded against.",
            f"# leaves_dr003_window: DR-003 Decision 5's MEASURED {DR003_WINDOW_V} V window, which",
            "#   supersedes that prediction and is what spec/pll.md now states.",
            "# Both window columns test the RIPPLE PEAKS (peak_min_v/peak_max_v), not the",
            "#   average, because headroom is lost at the peak -- the source record's own rule.",
            "# openloop_predicted_travel_v: the control voltage the SAME band needs at 3.63 V",
            "#   to hold the frequency it makes at 2.97 V with vctrl_lo_v, from #8's committed",
            f"#   f(Vctrl, vdd) table ({VCO_RECORD_ID}/vco_tuning.csv) by interpolation inside the",
            "#   one bracketing interval -- never extrapolated. Agreement with span_full_v means",
            "#   the consumption is what the selected band requires, not an anomaly.",
        ],
        written,
    )

    over_full = [w for w in written if w["over_budget2_full_range"] == "yes"]
    over_half = [w for w in written if w["over_budget2_half_range"] == "yes"]
    return {
        "n_cells": len(written),
        "over_full": [(w["bundle"], w["temp_c"], w["span_full_v"]) for w in over_full],
        "over_half": [(w["bundle"], w["temp_c"], w["span_half_v"]) for w in over_half],
        "worst": written[0],
        "leaves_dr001": [w for w in written if w["leaves_dr001_window"] == "yes"],
        "leaves_dr003": [w for w in written if w["leaves_dr003_window"] == "yes"],
        "tightest_dr003_margin": min(written, key=lambda w: float(w["margin_dr003_v"])),
    }


def criterion3(src: Path, out: Path) -> dict[str, object]:
    """Is the post-ramp recovery an exponential or a straight line?"""
    dynamic = {(r["bundle"], r["temp_c"]): r for r in _rows(src / "supply_dynamic.csv")}
    rerun = {(r["bundle"], r["temp_c"]): r for r in _rows(src / "dyn_end_settling_rerun.csv")}
    steady = {
        (r["bundle"], r["temp_c"], round(float(r["vdd_v"]), 2)): r
        for r in _rows(src / "supply_steady.csv")
    }

    written = []
    for bundle, temp in DYN_CORNERS:
        wave = src / f"supply_transient_{bundle}_{temp}c_{RAIL_NOM_V:.2f}v_end.csv"
        samples, t_rend = read_transient(wave)
        t_last = samples[-1][0]
        final = [v for t, v in samples if t >= t_last - FINAL_WINDOW_S]
        final_v = sum(final) / len(final)
        # The loop filter's own control-line ripple, measured on the RAW trace
        # over the same settled window. It is the scale below which an
        # "overshoot" is not an overshoot.
        ripple_pp = max(final) - min(final)

        trace = bin_mean(samples, t_rend, t_last)
        arrived = next(
            (t for t, v in trace if abs(v - final_v) <= ARRIVED_TOL_V), None
        )
        if arrived is None:
            sys.exit(f"ERROR: {wave} never comes within {ARRIVED_TOL_V} V of its own final value")
        segment = [(t, v) for t, v in trace if t < arrived]
        law = recovery_law(segment, target_v=final_v) if len(segment) >= 4 else None
        mono = monotonicity(trace, final_v)
        seg_range = (
            abs(segment[-1][1] - segment[0][1]) if len(segment) >= 2 else 0.0
        )

        dyn = dynamic[(bundle, temp)]
        rer = rerun[(bundle, temp)]
        phi12 = float(dyn["phi12"])
        ferr_end = float(dyn["ferr_end"])
        close = time_to_close_phase_s(phi12, ferr_end)
        dt_rerun = float(rer["t_end_long"]) - float(rer["t_end_short"])
        travel = abs(
            float(steady[(bundle, temp, RAIL_HI_V)]["vctrl_avg_v"])
            - float(steady[(bundle, temp, RAIL_LO_V)]["vctrl_avg_v"])
        )
        written.append(
            {
                "bundle": bundle,
                "temp_c": temp,
                "band": dyn["band"],
                "t_rend_us": f"{t_rend * 1e6:.2f}",
                "t_hold_end_us": f"{t_last * 1e6:.2f}",
                "vctrl_final_v": f"{final_v:.4f}",
                "vctrl_at_t_rend_v": f"{trace[0][1]:.4f}",
                "required_travel_v": f"{travel:.4f}",
                "t_arrived_us": f"{arrived * 1e6:.2f}",
                "recovery_us": f"{(arrived - t_rend) * 1e6:.2f}",
                "n_fit_samples": "n/a" if law is None else str(law["n_samples"]),
                "segment_range_mv": f"{seg_range * 1e3:.1f}",
                "overshoot_mv": f"{mono['overshoot_v'] * 1e3:.1f}",
                "settled_ripple_pp_mv": f"{ripple_pp * 1e3:.1f}",
                "reversals": str(mono["reversals"]),
                "slope_mv_per_us": "n/a" if law is None else f"{law['slope_mv_per_us']:.2f}",
                "rms_linear_mv": "n/a" if law is None else f"{law['rms_linear_v'] * 1e3:.2f}",
                "rms_exponential_mv": (
                    "n/a"
                    if law is None or law["rms_exponential_v"] is None
                    else f"{law['rms_exponential_v'] * 1e3:.2f}"
                ),
                "tau_fit_us": (
                    "n/a" if law is None or law["tau_fit_s"] is None else f"{law['tau_fit_s'] * 1e6:.2f}"
                ),
                "better_fit": "n/a" if law is None else str(law["better_fit"]),
                "phi12_ns": f"{phi12 * 1e9:.3f}",
                "ferr_end": f"{ferr_end:.6g}",
                "t_to_close_phase_us": "n/a" if close is None else f"{close * 1e6:.2f}",
                "decay_ratio_recorded": rer["decay_ratio"],
                "decay_expected_recorded": rer["decay_expected"],
                "decay_expected_recheck": f"{single_pole_decay(dt_rerun):.5f}",
                "classification_recorded": rer["classification"],
            }
        )

    _write(
        out / "criterion3_end_recovery.csv",
        [
            "# criterion 3 / section 3c of 20260901-155456-46b92f8: the POST-RAMP (END-plateau)",
            "#   recovery, read off the retained waveform instead of from two samples.",
            "# The recorded classification is made from decay_ratio (the ratio of the",
            "#   frequency-residual samples at the short and long holds) against",
            "#   decay_expected = exp(-dt/tau) -- a discriminant that ASSUMES the recovery is",
            "#   an exponential at the loop's own pole. decay_expected_recheck recomputes that",
            "#   expectation from the two holds' own instants, so the comparison is verified",
            "#   rather than taken on trust.",
            "# better_fit answers the assumption: a straight line and a single exponential are",
            "#   both fitted to the SAME ripple-averaged control-node samples over the segment",
            f"#   from the ramp's end to the instant the node first comes within {ARRIVED_TOL_V * 1e3:.0f} mV of its",
            f"#   own final value (the mean of the last {FINAL_WINDOW_S * 1e6:.0f} us of the hold), and their residuals",
            f"#   are compared IN VOLTS. Ripple is averaged in {BIN_S * 1e6:.1f} us bins; the trace itself is",
            "#   decimated at 20 ns and carries the loop filter's own ripple, so one sample is",
            "#   not a position.",
            "# overshoot_mv / reversals: the model-free damping test -- how far the",
            "#   ripple-averaged node goes PAST its own final value, and how many direction",
            f"#   changes larger than {ARRIVED_TOL_V * 1e3:.0f} mV it makes over the whole post-ramp hold. An",
            "#   under-damped recovery overshoots and reverses; a current-limited slew",
            "#   approaches from one side and stops. This statement depends on no fit.",
            "# settled_ripple_pp_mv: the control line's own peak-to-peak ripple on the RAW",
            "#   trace over the same settled window. Read overshoot_mv against it -- an",
            "#   excursion at the ripple's own scale is not an overshoot, and the tolerance",
            f"#   the reversal count uses ({ARRIVED_TOL_V * 1e3:.0f} mV) is of that order by construction.",
            "# segment_range_mv: how far the node actually moved over the fitted segment. Read",
            "#   the two rms columns against THIS: where the segment is short, both models fit",
            "#   a nearly-straight piece of anything and better_fit does not discriminate.",
            "# required_travel_v: how far this cell's control node has to move across the",
            "#   2.97-3.63 V rail in the steady state (criterion 1b's own span_full_v). The ramp",
            "#   demands that travel in 6.4 us.",
            "# t_to_close_phase_us: the phase still outstanding at the extended hold's own end",
            "#   (phi12) divided by the slip rate measured there (ferr_end). At that rate, not a",
            "#   settling prediction: a decaying response slows as it converges, so this is the",
            "#   OPTIMISTIC end of a bracket -- the same shape DR-011 declined to promote to a",
            "#   spec bound for the high plateau.",
        ],
        written,
    )
    return {"rows": written}


def _write(path: Path, comments: list[str], rows: list[dict[str, object]]) -> None:
    if not rows:
        sys.exit(f"ERROR: refusing to write an empty {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        for line in comments:
            handle.write(line + "\n")
        handle.write("# NO SIMULATION WAS RUN. Every column is arithmetic on committed data.\n")
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "record_id",
        nargs="?",
        default="20260901-155456-46b92f8",
        help="source record id under sim/supply-sensitivity/corners/ (default: %(default)s)",
    )
    parser.add_argument("--outdir", default=None, help="where to write the CSVs")
    args = parser.parse_args(argv)

    src = repo / "sim/supply-sensitivity/corners" / args.record_id
    dr012 = repo / "sim/supply-sensitivity/corners" / DR012_RECORD_ID
    vco = repo / "sim/vco-tuning-range/corners" / VCO_RECORD_ID
    out = Path(args.outdir) if args.outdir else src.parent / f"{args.record_id}-reexam"

    c1 = criterion1(src, dr012, out)
    c1b = criterion1b(src, vco, out)
    c3 = criterion3(src, out)

    print()
    print("CRITERION 1 -- which check failed")
    print(f"  verdict classes over {c1['n_rows']} rows: {c1['classes']}")
    print(f"  corners failing EITHER frequency check: {c1['freq_fails']}")
    print(f"  worst |fdev| {c1['worst_fdev_ppm']:.0f} ppm of {FDEV_PPM_LIMIT:.0f};"
          f" worst |ferr| {c1['worst_ferr']:.3g} of {FERR_LIMIT:g}")
    print(f"  the record's 'phi' class, with DR-012's settled flag: {c1['phi_class']}")
    print(f"  over the ratified 1 ns AND settled: {c1['over_and_settled']}")
    print()
    print("CRITERION 1b -- Budget 2 and the control window")
    print(f"  cells over {BUDGET2_V} V on the row's own 0.66 V excursion:"
          f" {len(c1b['over_full'])} of {c1b['n_cells']} -> {c1b['over_full']}")
    print(f"  cells over {BUDGET2_V} V on the derivation's 0.33 V excursion:"
          f" {len(c1b['over_half'])} of {c1b['n_cells']}")
    print(f"  worst cell: {c1b['worst']['bundle']}/{c1b['worst']['temp_c']} C,"
          f" {c1b['worst']['span_full_v']} V consumed"
          f" (open-loop table predicts {c1b['worst']['openloop_predicted_travel_v']} V)")
    print(f"  cells leaving DR-001's predicted 0.9-2.4 V window: {len(c1b['leaves_dr001'])}")
    print(f"  cells leaving DR-003's measured 0.9-2.7 V window: {len(c1b['leaves_dr003'])}")
    print(f"  tightest margin to DR-003's window:"
          f" {c1b['tightest_dr003_margin']['margin_dr003_v']} V at"
          f" {c1b['tightest_dr003_margin']['bundle']}/{c1b['tightest_dr003_margin']['temp_c']} C")
    print()
    print("CRITERION 3 -- the post-ramp recovery law")
    for row in c3["rows"]:
        print(
            f"  {row['bundle']}/{row['temp_c']} C: travel {row['required_travel_v']} V,"
            f" recovery {row['recovery_us']} us at {row['slope_mv_per_us']} mV/us"
            f" over {row['segment_range_mv']} mV ({row['n_fit_samples']} bins),"
            f" overshoot {row['overshoot_mv']} mV on {row['settled_ripple_pp_mv']} mV of"
            f" ripple / {row['reversals']} reversals,"
            f" better_fit={row['better_fit']}"
            f" (line {row['rms_linear_mv']} mV rms vs exp {row['rms_exponential_mv']} mV rms);"
            f" {row['phi12_ns']} ns left, closing in {row['t_to_close_phase_us']} us"
            f" [recorded: {row['classification_recorded']}]"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
