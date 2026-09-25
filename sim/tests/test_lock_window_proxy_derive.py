#!/usr/bin/env python3
"""`sim/lock-window-proxy`'s reduction is what decides the campaign's verdict.

The campaign (issue #501) asks whether a quantity the pads expose can stand in
for `t_win`, the internal measurand of `spec/pll.md`'s normative
[Lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule).
Every point of that question is answered inside `derive.py`: which code the
rule picks, which code each pad-referred candidate picks, and whether the
candidate's code still holds the ratified [1, 2] ns band.

A reduction that silently agreed with itself would produce a confident,
meaningless record, and the run that feeds it costs hours of ngspice. So the
selection logic is exercised here against SYNTHETIC points whose right answer
is known in closed form:

- a candidate constructed to track the window perfectly must score zero code
  error and a residual spread of exactly 1;
- a candidate constructed to track it BACKWARDS must be caught -- this is not
  a hypothetical, it is what the free-running ring period actually does across
  the MOS bundles, and a reduction that scored it as "fine" would be the one
  way this campaign could reach a wrong conclusion;
- "nearest" must be nearest in the LOG sense, which the rule says explicitly
  and which differs from linear-nearest for a multiplicative ladder.

    python3 -m unittest discover -s sim/tests -t sim/tests

No PDK and no ngspice required.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness.derived import PointView, RunView  # noqa: E402

DERIVE = SIM_DIR / "lock-window-proxy" / "testbench" / "derive.py"


def _load_derive():
    spec = importlib.util.spec_from_file_location("lock_window_proxy_derive", DERIVE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


derive = _load_derive()

#: One trim step, as a ratio. Close to the measured 2.7-4.7 % of
#: `sim/lock-window-trim/records/20260917-185928-8adff3d.md`, so the synthetic
#: ladder has the same resolution the real one does.
STEP = 1.035

#: typical's window at code 0, in seconds.
BASE_S = 1.02e-9

#: Ring period at the calibration bundle, in seconds.
BASE_PERIOD_S = 20e-9

#: Retiming-flop clock-to-Q at the calibration bundle, in seconds.
BASE_SKEW_S = 0.27e-9

#: How much slower than typical each synthetic bundle's 3.3 V logic is.
BUNDLES = {"typical": 1.0, "slow": 1.16, "fast": 0.88}

TEMPS = (-40.0, 27.0, 125.0)

#: Window scaling with temperature, applied on top of the bundle's own factor
#: so each bundle has a PVT box to run the band test over.
TEMP_FACTOR = {-40.0: 0.86, 27.0: 1.0, 125.0: 1.22}


def _points(observables):
    """Synthetic run points.

    ``observables(bundle_factor) -> (period_s, skew_s)`` decides what the
    pad-referred candidates do as a function of the bundle's true logic speed,
    which is how a "perfect" and a "backwards" candidate are expressed.
    """
    points = []
    for bundle, factor in BUNDLES.items():
        period_s, skew_s = observables(factor)
        for temp in TEMPS:
            scale = factor * TEMP_FACTOR[temp]
            measurements = {
                f"twin_c{code}": BASE_S * scale * STEP**code for code in range(16)
            }
            # The deck measures eight periods, and the two skews come back
            # plus an unknown whole number of periods -- the reduction has to
            # take the remainder. Adding 3 and 2 periods here is what makes
            # that recovery a tested property rather than an assumption.
            measurements["t8p_a"] = 8.0 * period_s
            measurements["t8p_b"] = 8.0 * period_s * 0.13
            measurements["tcq_raw"] = skew_s + 3.0 * period_s
            measurements["tdo_raw"] = 1.3e-9 * factor + 2.0 * period_s
            points.append(
                PointView(
                    corner=bundle,
                    corner_id=f"{bundle}_{temp:g}c_3.30v",
                    temp_c=temp,
                    vdd=3.3,
                    measurements=measurements,
                )
            )
    return tuple(points)


def _run(observables):
    return RunView(
        experiment="lock-window-proxy",
        measure_names=(),
        points=_points(observables),
    )


def _tables(observables):
    return {t.name: t for t in derive.derive_tables(_run(observables))}


def _rows_by_first_column(table):
    return {row[0]: row for row in table.rows}


#: A candidate that tracks the window exactly: both observables scale with the
#: bundle's logic speed, which is what a pad-referred stand-in has to do.
def _perfect(factor):
    return BASE_PERIOD_S * factor, BASE_SKEW_S * factor


#: A candidate that tracks it BACKWARDS -- the free-running ring's real
#: behaviour across the MOS bundles, where the starved ring runs FASTER at the
#: slow-logic corner.
def _backwards(factor):
    return BASE_PERIOD_S / factor, BASE_SKEW_S * factor


class NearestCodeIsLogarithmic(unittest.TestCase):
    """The rule says "nearest ... in the logarithmic sense"; so must the code."""

    def test_log_nearest_differs_from_linear_nearest_and_the_code_follows_log(self):
        # Two codes straddling a 1.00 target. Linear: 0.70 is 0.30 below, 1.32
        # is 0.32 above, so LINEAR-nearest is c0. Log: |ln 0.70| = 0.357,
        # ln 1.32 = 0.278, so LOG-nearest is c1. A multiplicative ladder
        # penalises the low side harder, which is the whole reason the rule
        # says "in the logarithmic sense" -- and the two answers differ here.
        table = {0: 0.70, 1: 1.32}
        target = 1.00
        self.assertLess(abs(0.70 - target), abs(1.32 - target))  # linear picks c0
        self.assertLess(
            abs(math.log(1.32 / target)), abs(math.log(0.70 / target))
        )  # log picks c1
        self.assertEqual(derive._nearest_code(table, target), 1)

    def test_a_code_with_no_value_is_skipped_not_treated_as_zero(self):
        self.assertEqual(derive._nearest_code({0: None, 1: 1.34, 2: 0.0}, 1.343), 1)

    def test_no_usable_code_returns_none(self):
        self.assertIsNone(derive._nearest_code({0: None}, 1.343))
        self.assertIsNone(derive._nearest_code({0: 1.3}, 0.0))


class SkewRecoveryIsModuloThePeriod(unittest.TestCase):
    """FB and DIVOUT only move on a CLK edge, so the raw trig/targ is skew + kT."""

    def test_whole_periods_are_removed_exactly(self):
        point = PointView(
            corner="typical",
            corner_id="typical_27c_3.30v",
            temp_c=27.0,
            vdd=3.3,
            measurements={"t8p_a": 8.0 * 20e-9, "tcq_raw": 0.27e-9 + 5.0 * 20e-9},
        )
        self.assertAlmostEqual(derive._skew_ns(point, "tcq_raw"), 0.27, places=9)

    def test_a_missing_period_yields_no_skew_rather_than_a_wrong_one(self):
        point = PointView(
            corner="typical",
            corner_id="typical_27c_3.30v",
            temp_c=27.0,
            vdd=3.3,
            measurements={"tcq_raw": 0.27e-9},
        )
        self.assertIsNone(derive._skew_ns(point, "tcq_raw"))


class APerfectCandidateScoresPerfectly(unittest.TestCase):
    """The control that proves the scorecard can say yes."""

    def setUp(self):
        self.tables = _tables(_perfect)

    def test_every_candidate_selects_the_rules_own_code(self):
        rows = _rows_by_first_column(self.tables["proxy_candidates"])
        for name, _ in derive.CANDIDATES:
            with self.subTest(candidate=name):
                self.assertEqual(rows[name][3], 0, f"{name} should have no code error")
                self.assertAlmostEqual(float(rows[name][2]), 1.0, places=9)

    def test_the_rule_row_and_the_untrimmed_control_are_both_reported(self):
        rows = _rows_by_first_column(self.tables["proxy_candidates"])
        self.assertIn("RULE (internal t_win)", rows)
        self.assertIn(f"NONE (untrimmed, c{derive.UNTRIMMED_CODE})", rows)

    def test_the_rule_holds_the_band_on_this_synthetic_ladder(self):
        rows = _rows_by_first_column(self.tables["proxy_candidates"])
        self.assertEqual(rows["RULE (internal t_win)"][10], "all in-band")

    def test_the_per_bundle_table_names_the_calibration_bundle_as_such(self):
        verdicts = {
            row[0]: row[-1] for row in self.tables["proxy_code_table"].rows
        }
        self.assertIn("(calibration)", verdicts[derive.CALIBRATION_BUNDLE])
        for bundle in BUNDLES:
            if bundle != derive.CALIBRATION_BUNDLE:
                self.assertNotIn("(calibration)", verdicts[bundle])


class ABackwardsCandidateIsCaught(unittest.TestCase):
    """The failure mode this campaign exists to be able to detect."""

    def setUp(self):
        self.tables = _tables(_backwards)
        self.rows = _rows_by_first_column(self.tables["proxy_candidates"])

    def test_the_inverted_ring_period_lands_many_codes_away(self):
        # The bundles are 1.16x and 0.88x typical. An inverted observable asks
        # for the correction twice over and in the wrong direction, so the
        # error is ~2 x log(factor) / log(step) codes.
        expected = round(2.0 * math.log(1.16) / math.log(STEP))
        self.assertGreaterEqual(int(self.rows["ring_a"][3]), expected - 1)

    def test_its_residual_spread_is_worse_than_the_process_spread_it_removes(self):
        tracking = _rows_by_first_column(self.tables["proxy_tracking"])
        process_spread = max(
            float(tracking[b][1]) for b in BUNDLES
        ) / min(float(tracking[b][1]) for b in BUNDLES)
        self.assertGreater(float(self.rows["ring_a"][2]), process_spread)

    def test_the_skew_candidate_is_unaffected_and_still_scores_perfectly(self):
        # _backwards only inverts the ring; the CLK -> FB skew still tracks.
        self.assertEqual(self.rows["clk_fb"][3], 0)


class TheCrosscheckReportsItsOwnAbsence(unittest.TestCase):
    """An unjoined run must say so, not silently omit the cross-check."""

    def test_no_join_is_a_reported_state_rather_than_a_missing_table(self):
        table = _tables(_perfect)["twin_crosscheck"]
        self.assertEqual(table.columns, ("note",))
        self.assertIn("no 'trim' join supplied", table.rows[0][0])


class AMissingCalibrationPointIsFatalNotSilent(unittest.TestCase):
    """Every candidate's only fitted constant comes from one point."""

    def test_every_table_says_why_it_is_not_derivable(self):
        points = tuple(p for p in _points(_perfect) if p.corner != "typical")
        run = RunView(experiment="lock-window-proxy", measure_names=(), points=points)
        tables = {t.name: t for t in derive.derive_tables(run)}
        self.assertEqual(len(tables), 4)
        for name, table in tables.items():
            with self.subTest(table=name):
                self.assertEqual(table.columns, ("note",))
                self.assertIn("calibration", table.rows[0][0])


if __name__ == "__main__":
    unittest.main()
