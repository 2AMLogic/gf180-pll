#!/usr/bin/env python3
"""Unit tests for `fail_criteria_reexamination.py` (issue #506).

That script re-reads the three FAILing criteria of
`sim/supply-sensitivity/records/20260901-155456-46b92f8.md` against the
*ratified* spec lines, using arithmetic on committed artifacts and no new
simulation. Three of its judgements are load-bearing enough that a silent
arithmetic bug in them would change a decision record's conclusion:

1. **Budget-2 consumption.** `spec/pll.md` row 12 states the budget over a
   `2.97 - 3.63 V` excursion (0.66 V) while the derivation beneath it prices a
   `+/-10 %` one (0.33 V). The script must report BOTH readings from the same
   data, because which one is normative is the question the finding hands to
   the operator -- so a test has to pin which span each column is.
2. **Control-window excursions.** DR-001 Decision 2 predicted a 0.9-2.4 V
   usable window; DR-003 Decision 5 measured 0.9-2.7 V and supersedes it. The
   same grid FAILs against the first and PASSes against the second, so the
   grading function must take the window as an argument and must test the
   RIPPLE PEAKS rather than the average (the source record's own rule).
3. **Linear vs. exponential recovery.** The campaign's END-plateau escalation
   classifies a corner `under-damped` from the ratio of two frequency-residual
   samples against `exp(-dt/tau)` -- a discriminant that assumes an
   exponential. If the measured control-node recovery is a straight line
   instead, that discriminant cannot separate under-damping from a
   current-limited slew, and the classification does not mean what it says.
   The comparison is therefore made in volts, against synthetic traces where
   the right answer is known by construction.

Every test builds its own inputs analytically. No PDK, no ngspice, no
committed evidence is read.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SIM_DIR / "supply-sensitivity" / "testbench" / "fail_criteria_reexamination.py"


def _load_module():
    assert SCRIPT.is_file(), f"{SCRIPT} not found"
    spec = importlib.util.spec_from_file_location("fail_criteria_reexamination", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()


class TestSpecConstants(unittest.TestCase):
    """The constants this analysis grades against are the ratified ones."""

    def test_budget2_and_rail_points(self):
        self.assertEqual(M.BUDGET2_V, 0.6)
        self.assertEqual((M.RAIL_LO_V, M.RAIL_NOM_V, M.RAIL_HI_V), (2.97, 3.30, 3.63))

    def test_full_range_is_twice_the_derivations_excursion(self):
        """The whole point of the finding: 0.66 V vs. 0.33 V."""
        self.assertAlmostEqual(M.RAIL_HI_V - M.RAIL_LO_V, 0.66, places=9)
        self.assertAlmostEqual(M.RAIL_HI_V - M.RAIL_NOM_V, 0.33, places=9)

    def test_both_control_windows_are_carried_separately(self):
        self.assertEqual(M.DR001_WINDOW_V, (0.9, 2.4))
        self.assertEqual(M.DR003_WINDOW_V, (0.9, 2.7))

    def test_ktau_is_the_dominant_closed_loop_pole(self):
        """tau = 1/(2 pi f_p), f_p = 17.09 kHz -- spec/pll.md's Lock time pole."""
        self.assertAlmostEqual(M.KTAU_S, 1.0 / (2.0 * math.pi * 17.09e3), places=12)
        self.assertAlmostEqual(M.KTAU_S * 1e6, 9.313, places=3)


class TestVctrlConsumption(unittest.TestCase):
    """Budget-2 consumption, both readings, from one set of per-supply samples."""

    def _cell(self, lo, nom, hi):
        return M.vctrl_consumption({M.RAIL_LO_V: lo, M.RAIL_NOM_V: nom, M.RAIL_HI_V: hi})

    def test_full_range_span_is_high_minus_low(self):
        got = self._cell(1.796, 2.227, 2.642)
        self.assertAlmostEqual(got["span_full_v"], 0.846, places=9)

    def test_half_range_span_is_the_worse_of_the_two_half_excursions(self):
        """0.431 V (2.97->3.30) beats 0.415 V (3.30->3.63); the worse one is reported."""
        got = self._cell(1.796, 2.227, 2.642)
        self.assertAlmostEqual(got["span_half_v"], 0.431, places=9)

    def test_slope_is_the_full_span_over_the_full_rail(self):
        got = self._cell(1.796, 2.227, 2.642)
        self.assertAlmostEqual(got["dvctrl_dvdd"], 0.846 / 0.66, places=6)

    def test_the_two_readings_can_straddle_the_budget(self):
        """The finding in one assertion: same cell, over under one reading, inside the other."""
        got = self._cell(1.796, 2.227, 2.642)
        self.assertTrue(got["over_budget_full"])
        self.assertFalse(got["over_budget_half"])

    def test_a_cell_inside_both_readings_grades_inside_both(self):
        got = self._cell(1.011, 1.215, 1.396)
        self.assertAlmostEqual(got["span_full_v"], 0.385, places=9)
        self.assertFalse(got["over_budget_full"])
        self.assertFalse(got["over_budget_half"])

    def test_the_budget_edge_is_strict(self):
        """`> 0.6 V` is over budget; `0.6 V` itself is not.

        Probed either side of the edge rather than at it, because a decimal
        0.6 V span is not representable exactly in binary and a test written
        at the edge would be testing float64, not the grading rule.
        """
        self.assertFalse(self._cell(1.0, 1.3, 1.0 + 0.6 - 1e-9)["over_budget_full"])
        self.assertTrue(self._cell(1.0, 1.3, 1.0 + 0.6 + 1e-9)["over_budget_full"])

    def test_a_missing_supply_point_is_an_error_not_a_silent_zero(self):
        with self.assertRaises(KeyError):
            M.vctrl_consumption({M.RAIL_LO_V: 1.0, M.RAIL_NOM_V: 1.3})


class TestWindowExcursion(unittest.TestCase):
    """Which points leave a control window -- peaks, not averages."""

    def test_peak_above_the_dr001_top_is_outside_it(self):
        self.assertTrue(M.leaves_window(0.9, 2.647, M.DR001_WINDOW_V))

    def test_the_same_peak_is_inside_the_dr003_window(self):
        self.assertFalse(M.leaves_window(0.9, 2.647, M.DR003_WINDOW_V))

    def test_margin_to_the_window_is_signed_and_read_off_the_binding_edge(self):
        """+ means inside. 2.647 V has 53 mV left of DR-003's top."""
        self.assertAlmostEqual(
            M.window_margin_v(0.978, 2.647, M.DR003_WINDOW_V), 0.053, places=9
        )
        self.assertAlmostEqual(
            M.window_margin_v(0.978, 2.647, M.DR001_WINDOW_V), -0.247, places=9
        )

    def test_the_bottom_edge_can_be_the_binding_one(self):
        self.assertAlmostEqual(
            M.window_margin_v(0.91, 1.50, M.DR003_WINDOW_V), 0.01, places=9
        )
        self.assertTrue(M.leaves_window(0.89, 1.50, M.DR003_WINDOW_V))

    def test_an_average_inside_a_window_whose_peak_is_outside_it_still_leaves(self):
        """The source record's own rule: headroom is lost at the peak of the ripple."""
        self.assertTrue(M.leaves_window(2.35, 2.41, M.DR001_WINDOW_V))


class TestRecoveryLaw(unittest.TestCase):
    """Straight line vs. one pole, compared in volts on the same samples."""

    @staticmethod
    def _linear(t0, v0, slope, n=40, dt=0.5e-6):
        return [(t0 + k * dt, v0 + slope * k * dt) for k in range(n)]

    @staticmethod
    def _exponential(t0, v_end, amp, tau, n=40, dt=0.5e-6):
        return [
            (t0 + k * dt, v_end + amp * math.exp(-(k * dt) / tau)) for k in range(n)
        ]

    def test_a_straight_line_is_called_linear(self):
        got = M.recovery_law(self._linear(0.0, 0.5, -20e3), target_v=0.0)
        self.assertEqual(got["better_fit"], "linear")
        self.assertLess(got["rms_linear_v"], 1e-9)
        self.assertGreater(got["rms_exponential_v"], 10 * got["rms_linear_v"])

    def test_the_fitted_slope_recovers_the_synthetic_one(self):
        got = M.recovery_law(self._linear(0.0, 0.5, -20e3), target_v=0.0)
        self.assertAlmostEqual(got["slope_v_per_s"], -20e3, delta=1.0)
        self.assertAlmostEqual(got["slope_mv_per_us"], -20.0, places=6)

    def test_a_single_pole_is_called_exponential(self):
        got = M.recovery_law(
            self._exponential(0.0, 0.0, 0.5, M.KTAU_S), target_v=0.0
        )
        self.assertEqual(got["better_fit"], "exponential")
        self.assertLess(got["rms_exponential_v"], got["rms_linear_v"])

    def test_the_fitted_time_constant_recovers_the_synthetic_one(self):
        got = M.recovery_law(
            self._exponential(0.0, 0.0, 0.4, 12.0e-6), target_v=0.0
        )
        self.assertAlmostEqual(got["tau_fit_s"] * 1e6, 12.0, places=3)

    def test_the_fit_is_taken_about_the_stated_target_not_about_zero(self):
        """A recovery toward 1.8 V is exponential about 1.8 V, not about 0 V."""
        samples = self._exponential(0.0, 1.8, 0.4, 10.0e-6)
        self.assertEqual(M.recovery_law(samples, target_v=1.8)["better_fit"], "exponential")

    def test_too_few_samples_is_an_error_not_a_degenerate_fit(self):
        with self.assertRaises(ValueError):
            M.recovery_law([(0.0, 1.0), (1e-6, 0.9)], target_v=0.0)


class TestMonotonicity(unittest.TestCase):
    """The one damping statement that depends on no fit at all."""

    def test_a_monotone_slew_never_overshoots_and_never_reverses(self):
        trace = [(k * 0.5e-6, 2.3 - 0.02 * k) for k in range(26)]  # 2.30 -> 1.80 V
        got = M.monotonicity(trace, final_v=1.80)
        self.assertAlmostEqual(got["overshoot_v"], 0.0, places=9)
        self.assertEqual(got["reversals"], 0)

    def test_a_ringing_recovery_overshoots_and_reverses(self):
        trace = [
            (k * 0.5e-6, 1.80 + 0.5 * math.exp(-k / 8.0) * math.cos(k / 2.0))
            for k in range(40)
        ]
        got = M.monotonicity(trace, final_v=1.80)
        self.assertGreater(got["overshoot_v"], 0.05)
        self.assertGreater(got["reversals"], 2)

    def test_ripple_below_the_tolerance_is_not_counted_as_ringing(self):
        trace = [
            (k * 0.5e-6, 1.80 + (0.005 if k % 2 else -0.005)) for k in range(40)
        ]
        self.assertEqual(M.monotonicity(trace, final_v=1.80)["reversals"], 0)

    def test_a_recovery_from_below_is_handled_the_same_way(self):
        trace = [(k * 0.5e-6, 1.30 + 0.02 * k) for k in range(26)]  # 1.30 -> 1.80 V
        got = M.monotonicity(trace, final_v=1.80)
        self.assertAlmostEqual(got["overshoot_v"], 0.0, places=9)
        self.assertEqual(got["reversals"], 0)

    def test_an_empty_trace_is_not_an_exception(self):
        self.assertEqual(M.monotonicity([], final_v=1.8)["reversals"], 0)


class TestPhaseArithmetic(unittest.TestCase):
    """How much longer the measured slip rate needs to close the measured phase."""

    def test_time_to_close_is_phase_over_rate(self):
        """13.11 ns closing at 1.70451e-3 s/s -> 7.69 us."""
        got = M.time_to_close_phase_s(phi_s=-13.1141e-9, ferr=-1.70451e-3)
        self.assertAlmostEqual(got * 1e6, 7.694, delta=0.002)

    def test_sign_does_not_matter_only_magnitudes_do(self):
        self.assertAlmostEqual(
            M.time_to_close_phase_s(phi_s=13.1141e-9, ferr=1.70451e-3),
            M.time_to_close_phase_s(phi_s=-13.1141e-9, ferr=-1.70451e-3),
            places=12,
        )

    def test_a_phase_walking_the_wrong_way_is_reported_as_such(self):
        """Opposite signs mean the residual is growing; no finite closing time."""
        self.assertIsNone(M.time_to_close_phase_s(phi_s=13.1141e-9, ferr=-1.70451e-3))

    def test_a_zero_rate_does_not_divide_by_zero(self):
        self.assertIsNone(M.time_to_close_phase_s(phi_s=1e-9, ferr=0.0))

    def test_single_pole_decay_factor_over_an_interval(self):
        """The discriminant the campaign's escalation uses: exp(-dt/tau).

        0.049458 at the exact pole, against the 0.04925 the committed
        `dyn_end_settling_rerun.csv` carries for the same 28 us interval --
        that column is computed at a rounded tau = 9.3 us. The difference is
        0.4 % of a quantity the classification compares against 0.809, so it
        changes no verdict, but it is checked here rather than assumed away.
        """
        self.assertAlmostEqual(M.single_pole_decay(28.0e-6), 0.049458, places=6)
        self.assertAlmostEqual(math.exp(-28.0 / 9.3), 0.04925, places=5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
