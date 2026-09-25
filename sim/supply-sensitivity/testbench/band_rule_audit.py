#!/usr/bin/env python3
"""Where does the normative band-selection rule put each corner on the control
window, and is that where the Lock criterion's only closed-loop evidence was
taken? (issue #511)

DR-012 Decision 3 establishes, by measurement, that the loop settles outside
`spec/pll.md`'s ratified <= 1 ns static-phase Lock criterion at two of the 45
mandated PVT corners -- 1.227 ns at `ff`/27 C/3.63 V and 1.049 ns at
`typical`/-40 C/3.63 V. Decision 4b locates the axis: the charge pump's
residual per-cycle charge grows steeply toward the bottom of the control
window, and at Vctrl = 0.90 V the open-loop systematic term alone exceeds the
whole criterion at 36 of 45 corners. Decision 7 then says, in as many words,
that where a given `(f_out, band code, N, trim code)` cell lands on that window
is set by the [band-selection rule](../../../spec/pll.md#band-selection-rule),
"which this record does not re-derive".

**This script re-derives it.** It is the arithmetic DR-012 named and left
undone, and it answers three questions the Verification-owed Lock-criterion row
turns on:

1. **Is the committed grid at the band the rule selects?** `run.sh`'s
   `derive_op_points` picks, per (bundle, temperature), the band whose control
   voltage is *closest to mid-window* -- a heuristic, not the normative rule,
   and the only band selector in `sim/` that is not the rule. Where the two
   selectors differ, the committed evidence describes a configuration no
   compliant part carries.
2. **How much does the band choice move the static-phase term?** Joined
   against `sim/pfd-deadzone`'s 405-point open-loop grid at the closed loop's
   own f_ref, the same corner measures a several-fold different systematic
   offset at the two selectors' control voltages. That difference is the
   band-selection axis' entire leverage on this criterion, quantified.
3. **Can the rule fix the gap?** The rule is swept over the ratified
   10-200 MHz output band. If some corner is parked at the bottom of the
   window at *every* output frequency even under the rule, then no
   band-selection policy on this band map keeps the loop out of the region
   DR-012 measured the criterion is lost in -- and the resolution has to act
   on `q_zero`, exactly as Decision 7 says.

NO SIMULATION IS RUN and no committed record is modified. Every number is
arithmetic on three frozen artifacts:

  * `sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv`
    -- #8's open-loop f(Vctrl, vdd) table per band. The same file `run.sh`
    derives its own operating points from, so the comparison is against the
    campaign's own evidence rather than a different campaign's.
  * `sim/pfd-deadzone/corners/20260916-051356-8cedbba/pfd_static_offset.csv`
    -- DR-012's own 135-cell systematic static-offset grid, measured at the
    closed loop's f_ref = 12.5 MHz and Icp code b1b0 = 10 across the ratified
    control window.
  * `sim/supply-sensitivity/corners/20260916-051708-8cedbba/static_phase_widened.csv`
    -- DR-012's settled/unsettled grading of the 45-point closed-loop grid.

Usage:

    python3 sim/supply-sensitivity/testbench/band_rule_audit.py [--outdir DIR]

Pure functions below are unit-tested in
`sim/tests/test_supply_sensitivity_band_rule_audit.py` against inputs whose
right answer is known analytically. None of the judgements a decision record
rests on is allowed to be only spot-checked by eye.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ratified constants. Every one is a spec or decision-record value, cited where
# it is defined so a reader can check it rather than trust it.
# ---------------------------------------------------------------------------

#: `spec/pll.md` "Lock criterion": static phase error at the PFD inputs
#: <= 1 ns. An ABSOLUTE bound, independent of f_ref (DR-012 Decision 5).
ACC_PHI_RATIFIED_S = 1e-9

#: DR-001 Decision 2 -- the PREDICTED usable control window ("roughly
#: 0.9-2.4 V"). Carried separately from the measured one below because the
#: band the rule selects DIFFERS between them at `ff`/27 C / 100 MHz, which is
#: one of the two corners carrying a settled violation.
DR001_WINDOW_V = (0.9, 2.4)

#: DR-003 Decision 5 -- the MEASURED usable control window, monotonic on all
#: 504 measured curves, which `spec/pll.md` (Interfaces, "Vctrl operating
#: window 0.9 - 2.7 V") carries as the operative one.
DR003_WINDOW_V = (0.9, 2.7)

#: What `run.sh`'s `derive_op_points` actually searches over. Neither ratified
#: window: it is 50 mV wider at the bottom than either. Pinned here rather
#: than imported because this script reads a FROZEN grid and the runner is
#: mutable -- if the two ever diverge, the divergence is the finding.
CAMPAIGN_SEARCH_WINDOW_V = (0.85, 2.70)

#: `spec/pll.md` row 18 (Supply range): 3.3 V +/- 10 %, the three graded
#: points. Band select is a static input with no calibration FSM (DR-001
#: Decision 2), so one band code must reach the target at all three.
SUPPLIES_V = (2.97, 3.30, 3.63)

#: `spec/pll.md` row 1 (Output band): the ratified v1 range, DR-002
#: Decision 2. The rule is swept across it in question 3 above.
OUTPUT_BAND_HZ = (10e6, 200e6)

#: The campaign's own operating point (`run.sh` KFOUT/KN/KFREF/KTRIM), and the
#: one cell any closed-loop Lock-criterion evidence exists at.
CAMPAIGN_FOUT_HZ = 100e6

#: DR-012 Decision 4a's other two static-phase-offset budget terms, in ns:
#: `mc-cp-mismatch`'s statistical term and the divider retiming term. They add
#: ON TOP of the systematic term, not instead of it, so the systematic
#: headroom the band rule can buy is only ever part of the answer.
BUDGET_STATISTICAL_NS = 0.576
BUDGET_RETIMING_NS = 0.239

#: Step of the output-band sweep. 5 MHz resolves the band boundaries (the
#: band map's 1.65x per-code ratio puts them ~50 MHz apart up here) without
#: pretending to a precision the 0.3 V-step f(Vctrl) table does not carry.
SWEEP_STEP_HZ = 5e6

#: The five MOS corner bundles of the 45-point grid. The composite
#: `all-slow` / `all-fast` bundles are in the VCO table but are NOT on the
#: mandated grid, and are excluded exactly as `run.sh` excludes them.
BUNDLES = ("typical", "ff", "ss", "fs", "sf")
TEMPS_C = ("-40", "27", "125")

#: #8's open-loop f(Vctrl, vdd) table -- the source of both the band code and
#: the warm-start control voltage for every corner `run.sh` runs.
VCO_RECORD_ID = "20260731-175947-0a12e6c"

#: DR-012's open-loop systematic static-offset grid, measured at the closed
#: loop's own f_ref and Icp code. 45 corners x 3 control voltages.
PFD_RECORD_ID = "20260916-051356-8cedbba"

#: DR-012's settled/unsettled grading of the 45-point closed-loop grid.
DR012_RECORD_ID = "20260916-051708-8cedbba"


# ---------------------------------------------------------------------------
# Pure functions.
# ---------------------------------------------------------------------------


def vctrl_at_target(
    curve: list[tuple[float, float]], target_hz: float
) -> float | None:
    """Vctrl at which a measured f(Vctrl) curve reaches ``target_hz``.

    Linear interpolation inside the one bracketing interval, and **no
    extrapolation**: a curve that never reaches the target has no answer, and
    inventing one is how a band that cannot reach `f` gets selected anyway.
    Returns ``None`` when the target is not bracketed.
    """
    points = sorted(curve)
    for (v1, f1), (v2, f2) in zip(points, points[1:]):
        if (f1 - target_hz) * (f2 - target_hz) <= 0 and f1 != f2:
            return v1 + (target_hz - f1) * (v2 - v1) / (f2 - f1)
    return None


def _fits(vctrl_by_supply: dict[float, float], window: tuple[float, float]) -> bool:
    """Does one band hold the target at all three supplies inside ``window``?"""
    lo, hi = window
    if any(supply not in vctrl_by_supply for supply in SUPPLIES_V):
        return False
    return all(lo <= vctrl_by_supply[supply] <= hi for supply in SUPPLIES_V)


def rule_band(
    cell: dict[int, dict[float, float]], window: tuple[float, float]
) -> int | None:
    """`spec/pll.md`'s normative rule: the LOWEST band code that reaches `f`.

    ``cell`` maps band code -> supply -> the Vctrl that band needs to reach
    the target at that supply (absent supplies mean the band cannot reach it
    there at all). ``window`` is the control window "reaches" is evaluated
    over -- an argument, not a constant, because the spec states the rule
    without naming a window and the answer changes with the choice.

    Returns ``None`` when no single static band code holds the target across
    the ratified supply range inside the window.
    """
    for band in sorted(cell):
        if _fits(cell[band], window):
            return band
    return None


def midwindow_band(
    cell: dict[int, dict[float, float]], window: tuple[float, float]
) -> int | None:
    """`run.sh`'s selector: the band with the lowest max-|Vctrl - mid| cost.

    Reimplemented rather than imported, and kept rather than deleted, because
    the finding IS the difference between the two selectors on committed data
    and a difference cannot be computed from one side of it. Ties go to the
    lower band code, which is the order `derive_op_points` scans in.
    """
    lo, hi = window
    mid = 0.5 * (lo + hi)
    best: tuple[float, int] | None = None
    for band in sorted(cell):
        if not _fits(cell[band], window):
            continue
        cost = max(abs(cell[band][supply] - mid) for supply in SUPPLIES_V)
        if best is None or cost < best[0]:
            best = (cost, band)
    return None if best is None else best[1]


def interp_offset(
    grid_ns: dict[float, float], vctrl_v: float
) -> tuple[float, bool] | None:
    """Measured systematic static-phase term (ns) at an arbitrary Vctrl.

    ``grid_ns`` is one corner's row of `sim/pfd-deadzone`'s three-point
    (0.90 / 1.65 / 2.40 V) measured grid. Returns ``(value_ns, is_exact)``, or
    ``None`` outside the measured grid -- **the rule parks some cells past
    2.40 V, and a silently-extrapolated number there would be read as a
    measurement of a region nobody has simulated.**
    """
    points = sorted(grid_ns.items())
    if vctrl_v < points[0][0] or vctrl_v > points[-1][0]:
        return None
    for (v1, t1), (v2, t2) in zip(points, points[1:]):
        if v1 <= vctrl_v <= v2:
            if vctrl_v == v1:
                return (t1, True)
            if vctrl_v == v2:
                return (t2, True)
            return (t1 + (vctrl_v - v1) * (t2 - t1) / (v2 - v1), False)
    return None


def over_ratified_ns(t_ns: float) -> bool:
    """Is a static-phase term outside the ratified absolute 1 ns bound?"""
    return abs(t_ns) > ACC_PHI_RATIFIED_S * 1e9


def budget_sum_ns(t_sys_ns: float) -> float:
    """DR-012 Decision 4a's summed static-phase-offset budget at one point.

    The systematic term measured here plus the statistical and divider-retiming
    terms the budget adds on top of it. Stated as the budget states it -- a
    worst-case linear sum, which is conservative against the nominal-skew
    closed-loop grid and is deliberately not re-derived here.
    """
    return abs(t_sys_ns) + BUDGET_STATISTICAL_NS + BUDGET_RETIMING_NS


# ---------------------------------------------------------------------------
# Readers.
# ---------------------------------------------------------------------------


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        sys.exit(f"ERROR: {path} not found")
    with path.open() as handle:
        lines = [line for line in handle if not line.startswith("#")]
    return list(csv.DictReader(lines))


def read_vco_table(path: Path) -> dict[tuple[str, str], dict[int, dict[float, list]]]:
    """(bundle, temp) -> band -> supply -> [(vctrl, fosc), ...]."""
    table: dict[tuple[str, str], dict[int, dict[float, list]]] = {}
    for row in _rows(path):
        bundle = row["bundle"]
        if bundle not in BUNDLES:
            continue  # composite bundles are not on the mandated 45-point grid
        key = (bundle, row["temp_c"])
        band = int(row["band"])
        supply = float(row["vdd_v"])
        table.setdefault(key, {}).setdefault(band, {}).setdefault(supply, []).append(
            (float(row["vctrl_v"]), float(row["fosc_hz"]))
        )
    return table


def cell_at(
    table: dict[tuple[str, str], dict[int, dict[float, list]]],
    key: tuple[str, str],
    target_hz: float,
) -> dict[int, dict[float, float]]:
    """Reduce the f(Vctrl) curves of one (bundle, temp) to band -> supply -> Vctrl."""
    cell: dict[int, dict[float, float]] = {}
    for band, by_supply in table.get(key, {}).items():
        for supply, curve in by_supply.items():
            vctrl = vctrl_at_target(curve, target_hz)
            if vctrl is not None:
                cell.setdefault(band, {})[supply] = vctrl
    return cell


def read_offset_grid(path: Path) -> dict[str, dict[float, float]]:
    """`ff/27C/3.63V` -> {0.90: t_ns, 1.65: t_ns, 2.40: t_ns}."""
    grid: dict[str, dict[float, float]] = {}
    for row in _rows(path):
        grid.setdefault(row["corner"], {})[float(row["vctrl_v"])] = float(
            row["t_offset_abs_ns"]
        )
    return grid


def read_closed_loop(path: Path) -> dict[tuple[str, str, float], dict[str, str]]:
    """DR-012's graded 45-point grid, keyed (bundle, temp, supply)."""
    return {
        (row["bundle"], row["temp_c"], float(row["vdd_v"])): row
        for row in _rows(path)
    }


def corner_id(bundle: str, temp_c: str, supply: float) -> str:
    """The key `sim/pfd-deadzone` writes, e.g. `ff/27C/3.63V`."""
    return f"{bundle}/{temp_c}C/{supply:.2f}V"


# ---------------------------------------------------------------------------
# Section 1 -- the committed 100 MHz grid, selector against selector.
# ---------------------------------------------------------------------------


def section1(vco: Path, pfd: Path, dr012: Path, out: Path) -> dict[str, object]:
    table = read_vco_table(vco)
    offsets = read_offset_grid(pfd)
    closed = read_closed_loop(dr012)

    rows: list[dict[str, object]] = []
    disagreements: list[str] = []
    settled_violations: list[dict[str, object]] = []

    for bundle in BUNDLES:
        for temp in TEMPS_C:
            cell = cell_at(table, (bundle, temp), CAMPAIGN_FOUT_HZ)
            campaign = midwindow_band(cell, CAMPAIGN_SEARCH_WINDOW_V)
            measured = rule_band(cell, DR003_WINDOW_V)
            predicted = rule_band(cell, DR001_WINDOW_V)
            if campaign is not None and measured is not None and campaign != measured:
                disagreements.append(f"{bundle}/{temp}C")
            for supply in SUPPLIES_V:
                run_row = closed.get((bundle, temp, supply))
                v_campaign = (
                    cell[campaign][supply] if campaign is not None else None
                )
                v_rule = cell[measured][supply] if measured is not None else None
                off_campaign = (
                    interp_offset(offsets[corner_id(bundle, temp, supply)], v_campaign)
                    if v_campaign is not None
                    else None
                )
                off_rule = (
                    interp_offset(offsets[corner_id(bundle, temp, supply)], v_rule)
                    if v_rule is not None
                    else None
                )
                entry = {
                    "bundle": bundle,
                    "temp_c": temp,
                    "vdd_v": f"{supply:.2f}",
                    "band_campaign": "" if campaign is None else campaign,
                    "band_rule_measured_window": "" if measured is None else measured,
                    "band_rule_predicted_window": (
                        "" if predicted is None else predicted
                    ),
                    "selectors_agree": (
                        "" if (campaign is None or measured is None)
                        else ("yes" if campaign == measured else "NO")
                    ),
                    "vctrl_campaign_v": (
                        "" if v_campaign is None else f"{v_campaign:.3f}"
                    ),
                    "vctrl_rule_v": "" if v_rule is None else f"{v_rule:.3f}",
                    "t_sys_campaign_ns": (
                        "" if off_campaign is None else f"{off_campaign[0]:.4f}"
                    ),
                    "t_sys_rule_ns": (
                        "unmeasured" if off_rule is None else f"{off_rule[0]:.4f}"
                    ),
                    "vctrl_run_v": "" if run_row is None else run_row["vctrl_avg_v"],
                    "phi_b_run_ns": "" if run_row is None else run_row["phi_b_ns"],
                    "settled": "" if run_row is None else run_row["settled"],
                    "over_ratified": (
                        "" if run_row is None else run_row["over_ratified"]
                    ),
                    "verdict": "" if run_row is None else run_row["verdict"],
                }
                rows.append(entry)
                if (
                    run_row is not None
                    and run_row["settled"] == "yes"
                    and run_row["over_ratified"] == "yes"
                ):
                    settled_violations.append(entry)

    _write(
        out / "band_rule_100mhz.csv",
        [
            "# campaign: supply-sensitivity (issue #511)",
            "# question: is the committed 45-point Lock-criterion grid at the band",
            "#   spec/pll.md's normative band-selection rule selects?",
            f"# f_out: {CAMPAIGN_FOUT_HZ / 1e6:.0f} MHz (run.sh KFOUT), N = 8, f_ref = 12.5 MHz,",
            "#   Icp code b1b0 = 10 -- the one cell any closed-loop evidence exists at",
            "# band_campaign: run.sh derive_op_points -- lowest max|Vctrl - mid| cost over",
            f"#   its own search window {CAMPAIGN_SEARCH_WINDOW_V[0]}-{CAMPAIGN_SEARCH_WINDOW_V[1]} V",
            "# band_rule_measured_window: the rule (lowest band reaching f at all three",
            f"#   supplies) over DR-003 Decision 5's measured {DR003_WINDOW_V[0]}-{DR003_WINDOW_V[1]} V window",
            "# band_rule_predicted_window: the same rule over DR-001 Decision 2's",
            f"#   predicted {DR001_WINDOW_V[0]}-{DR001_WINDOW_V[1]} V window; blank = the rule has NO answer there",
            "# t_sys_*_ns: sim/pfd-deadzone's MEASURED open-loop systematic term at that",
            f"#   control voltage (record {PFD_RECORD_ID}), interpolated on its 0.90/1.65/2.40 V",
            "#   grid; 'unmeasured' = the rule parks past 2.40 V, outside the measured grid",
            f"# vctrl_run_v / phi_b_run_ns / settled / over_ratified: DR-012's graded grid ({DR012_RECORD_ID})",
        ],
        rows,
    )

    return {
        "rows": rows,
        "disagreements": disagreements,
        "settled_violations": settled_violations,
        "no_rule_answer_predicted": sorted(
            {
                f"{r['bundle']}/{r['temp_c']}C"
                for r in rows
                if r["band_rule_predicted_window"] == ""
            }
        ),
    }


# ---------------------------------------------------------------------------
# Section 2 -- can the rule fix it? The rule, swept over the ratified band.
# ---------------------------------------------------------------------------


def section2(vco: Path, pfd: Path, out: Path) -> dict[str, object]:
    table = read_vco_table(vco)
    offsets = read_offset_grid(pfd)

    rows: list[dict[str, object]] = []
    lo_hz, hi_hz = OUTPUT_BAND_HZ
    target = lo_hz
    n_points = 0
    n_over = 0
    n_over_budget = 0
    n_unmeasured = 0
    n_no_band = 0
    worst: dict[str, object] | None = None
    lowest: dict[str, object] | None = None
    freqs_with_a_bottom_cell = 0
    n_freqs = 0

    while target <= hi_hz + 1.0:
        n_freqs += 1
        bottom_here = False
        for bundle in BUNDLES:
            for temp in TEMPS_C:
                cell = cell_at(table, (bundle, temp), target)
                band = rule_band(cell, DR003_WINDOW_V)
                if band is None:
                    n_no_band += 1
                    rows.append(
                        {
                            "fout_mhz": f"{target / 1e6:.0f}",
                            "bundle": bundle,
                            "temp_c": temp,
                            "vdd_v": "",
                            "band_rule": "",
                            "vctrl_rule_v": "",
                            "t_sys_ns": "",
                            "budget_sum_ns": "",
                            "over_ratified": "",
                            "over_budget": "",
                            "note": "no single static band holds f across the supply range",
                        }
                    )
                    continue
                for supply in SUPPLIES_V:
                    vctrl = cell[band][supply]
                    got = interp_offset(
                        offsets[corner_id(bundle, temp, supply)], vctrl
                    )
                    over = "" if got is None else ("yes" if over_ratified_ns(got[0]) else "no")
                    budget = None if got is None else budget_sum_ns(got[0])
                    entry = {
                        "fout_mhz": f"{target / 1e6:.0f}",
                        "bundle": bundle,
                        "temp_c": temp,
                        "vdd_v": f"{supply:.2f}",
                        "band_rule": band,
                        "vctrl_rule_v": f"{vctrl:.3f}",
                        "t_sys_ns": "unmeasured" if got is None else f"{got[0]:.4f}",
                        "budget_sum_ns": "" if budget is None else f"{budget:.4f}",
                        "over_ratified": over,
                        "over_budget": (
                            "" if budget is None else ("yes" if over_ratified_ns(budget) else "no")
                        ),
                        "note": "" if got is not None else "Vctrl outside the measured 0.90-2.40 V offset grid",
                    }
                    rows.append(entry)
                    if got is None:
                        n_unmeasured += 1
                        continue
                    n_points += 1
                    if over == "yes":
                        n_over += 1
                    if budget is not None and over_ratified_ns(budget):
                        n_over_budget += 1
                    if worst is None or got[0] > float(worst["t_sys_ns"]):
                        worst = entry
                    if lowest is None or vctrl < float(lowest["vctrl_rule_v"]):
                        lowest = entry
                    if vctrl <= 1.05:
                        bottom_here = True
        if bottom_here:
            freqs_with_a_bottom_cell += 1
        target += SWEEP_STEP_HZ

    _write(
        out / "band_rule_output_band.csv",
        [
            "# campaign: supply-sensitivity (issue #511)",
            "# question: CAN the band-selection rule keep the loop off the bottom of the",
            "#   control window, where DR-012 Decision 4b measured the criterion is lost?",
            f"# sweep: f_out {lo_hz / 1e6:.0f}-{hi_hz / 1e6:.0f} MHz in {SWEEP_STEP_HZ / 1e6:.0f} MHz steps"
            f" x {len(BUNDLES)} bundles x {len(TEMPS_C)} temperatures x {len(SUPPLIES_V)} supplies",
            "# band_rule: the lowest band reaching f at all three supplies inside DR-003",
            f"#   Decision 5's measured {DR003_WINDOW_V[0]}-{DR003_WINDOW_V[1]} V window",
            "# t_sys_ns: sim/pfd-deadzone's MEASURED open-loop systematic term at that Vctrl,",
            f"#   interpolated on its 0.90/1.65/2.40 V grid (record {PFD_RECORD_ID})",
            "# over_ratified: |t_sys| > the ratified 1 ns Lock criterion, on the SYSTEMATIC",
            "#   term alone -- before mc-cp-mismatch's 0.576 ns statistical term and the",
            "#   0.239 ns divider retiming term are added",
            f"# budget_sum_ns / over_budget: DR-012 Decision 4a's summed budget at this point,",
            f"#   t_sys + {BUDGET_STATISTICAL_NS} statistical + {BUDGET_RETIMING_NS} retiming, graded against the",
            "#   same ratified 1 ns. A worst-case linear sum, as the budget states it.",
            "# NOTE: t_sys is measured OPEN LOOP at f_ref = 12.5 MHz. A cell at another f_out",
            "#   runs at another f_ref under the Icp trim-code rule; DR-012 measured f_ref",
            "#   moves this term by -6.4 % over a 2:1 change, so it is carried as the",
            "#   operating-point term it is, not as a closed-loop prediction.",
        ],
        rows,
    )

    return {
        "n_points": n_points,
        "n_over": n_over,
        "n_over_budget": n_over_budget,
        "n_unmeasured": n_unmeasured,
        "n_no_band": n_no_band,
        "worst": worst,
        "lowest": lowest,
        "n_freqs": n_freqs,
        "freqs_with_a_bottom_cell": freqs_with_a_bottom_cell,
    }


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
    parser.add_argument("--outdir", default=None, help="where to write the CSVs")
    args = parser.parse_args(argv)

    vco = repo / "sim/vco-tuning-range/corners" / VCO_RECORD_ID / "vco_tuning.csv"
    pfd = repo / "sim/pfd-deadzone/corners" / PFD_RECORD_ID / "pfd_static_offset.csv"
    dr012 = (
        repo
        / "sim/supply-sensitivity/corners"
        / DR012_RECORD_ID
        / "static_phase_widened.csv"
    )
    out = (
        Path(args.outdir)
        if args.outdir
        else repo / "sim/supply-sensitivity/corners/band-rule-audit"
    )

    s1 = section1(vco, pfd, dr012, out)
    s2 = section2(vco, pfd, out)

    lowest = s2["lowest"]
    worst = s2["worst"]
    lines: list[str] = []
    lines.append(f"SECTION 1 -- the committed {CAMPAIGN_FOUT_HZ / 1e6:.0f} MHz grid")
    lines.append(
        "  cells where run.sh's selector and the rule (measured window) disagree:"
        f" {len(s1['disagreements'])} of {len(BUNDLES) * len(TEMPS_C)}"
        f" -> {s1['disagreements']}"
    )
    lines.append(
        "  cells where the rule has NO answer inside DR-001's predicted window:"
        f" {len(s1['no_rule_answer_predicted'])} -> {s1['no_rule_answer_predicted']}"
    )
    for row in s1["settled_violations"]:
        lines.append(
            f"  settled violation {row['bundle']}/{row['temp_c']}C/{row['vdd_v']}V:"
            f" phi_b {row['phi_b_run_ns']} ns at Vctrl {row['vctrl_run_v']} V"
            f" | campaign band {row['band_campaign']} (Vctrl {row['vctrl_campaign_v']} V,"
            f" t_sys {row['t_sys_campaign_ns']} ns)"
            f" | rule band {row['band_rule_measured_window']} (Vctrl {row['vctrl_rule_v']} V,"
            f" t_sys {row['t_sys_rule_ns']} ns)"
            f" | selectors agree: {row['selectors_agree']}"
        )
    lines.append("")
    lines.append("SECTION 2 -- the rule swept over the ratified output band")
    lines.append(
        f"  graded points: {s2['n_points']}"
        f" (+{s2['n_unmeasured']} parked above the 2.40 V top of the measured offset grid,"
        f" +{s2['n_no_band']} (f_out, cell) with no feasible static band)"
    )
    lines.append(
        f"  systematic term alone over the ratified 1 ns: {s2['n_over']}"
        f" ({100.0 * s2['n_over'] / s2['n_points']:.1f} %)"
    )
    lines.append(
        f"  DR-012 4a budget (t_sys + {BUDGET_STATISTICAL_NS} + {BUDGET_RETIMING_NS})"
        f" over the ratified 1 ns: {s2['n_over_budget']}"
        f" ({100.0 * s2['n_over_budget'] / s2['n_points']:.1f} %)"
    )
    lines.append(
        "  output frequencies with at least one rule-selected cell at Vctrl <= 1.05 V:"
        f" {s2['freqs_with_a_bottom_cell']} of {s2['n_freqs']}"
    )
    lines.append(
        f"  lowest rule-selected Vctrl anywhere: {lowest['vctrl_rule_v']} V at"
        f" {lowest['bundle']}/{lowest['temp_c']}C/{lowest['vdd_v']}V,"
        f" f_out {lowest['fout_mhz']} MHz, band {lowest['band_rule']}"
        f" (t_sys {lowest['t_sys_ns']} ns, budget sum {lowest['budget_sum_ns']} ns)"
    )
    lines.append(
        f"  worst rule-selected systematic term: {worst['t_sys_ns']} ns at"
        f" {worst['bundle']}/{worst['temp_c']}C/{worst['vdd_v']}V,"
        f" f_out {worst['fout_mhz']} MHz, band {worst['band_rule']},"
        f" Vctrl {worst['vctrl_rule_v']} V"
    )

    report = "\n".join(lines)
    print()
    print(report)
    summary = out / "band_rule_summary.txt"
    summary.write_text(report + "\n")
    print(f"\nwrote {summary}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
