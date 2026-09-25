#!/usr/bin/env python3
"""Unit tests for `band_rule_audit.py` (issue #511).

That script answers the question DR-012 Decision 4b explicitly did **not**
answer: *where on the control window does `spec/pll.md`'s normative
[band-selection rule](../../spec/pll.md#band-selection-rule) actually put each
PVT corner*, and is that the cell the ratified Lock criterion's only
closed-loop evidence was taken at? It re-simulates nothing; every number is
arithmetic on committed artifacts.

Four of its judgements are load-bearing enough that a silent arithmetic bug in
them would change a decision record's conclusion, so each is tested against an
input whose right answer is known analytically:

1. **`vctrl_at_target`** — the control voltage a band needs to reach a target
   frequency, by linear interpolation inside the one bracketing interval of a
   measured `f(Vctrl)` curve. It must **never extrapolate**: a curve that does
   not bracket the target has no answer, and inventing one is how a band that
   cannot reach `f` gets selected anyway.
2. **`rule_band`** — "the lowest 3-bit band code that reaches `f`", evaluated
   over a *stated* control window at *all three* supplies. The window is an
   argument because the answer changes with it: DR-001 Decision 2 predicted
   0.9-2.4 V and DR-003 Decision 5 measured 0.9-2.7 V, and at
   `ff`/27 C / 100 MHz those two readings select different bands.
3. **`midwindow_band`** — the selector `sim/supply-sensitivity`'s own
   `run.sh` applied instead (lowest max-|Vctrl - mid| cost). It is
   reimplemented here, not deleted, because the finding is the *difference*
   between the two selectors on committed data, and a difference cannot be
   computed from only one side of it.
4. **`interp_offset`** — the measured open-loop systematic static-phase term
   at an arbitrary control voltage, interpolated on `sim/pfd-deadzone`'s
   three-point (0.90 / 1.65 / 2.40 V) grid. It must refuse to extrapolate
   above the grid's top, because the rule parks some cells past 2.40 V and a
   silently-extrapolated number there would be read as a measurement.

No PDK, no ngspice, and no committed evidence is read by these tests: every
input is built analytically.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SIM_DIR / "supply-sensitivity" / "testbench" / "band_rule_audit.py"


def _load_module():
    assert SCRIPT.is_file(), f"{SCRIPT} not found"
    spec = importlib.util.spec_from_file_location("band_rule_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()


class TestRatifiedConstants(unittest.TestCase):
    """The constants this analysis grades against are the ratified ones."""

    def test_both_control_windows_are_carried_separately(self):
        """DR-001 predicted; DR-003 measured. Both, never silently merged."""
        self.assertEqual(M.DR001_WINDOW_V, (0.9, 2.4))
        self.assertEqual(M.DR003_WINDOW_V, (0.9, 2.7))

    def test_lock_criterion_is_the_ratified_absolute_bound(self):
        self.assertEqual(M.ACC_PHI_RATIFIED_S, 1e-9)

    def test_supply_points_are_the_ratified_three(self):
        self.assertEqual(M.SUPPLIES_V, (2.97, 3.30, 3.63))

    def test_campaign_search_window_is_the_one_run_sh_applied(self):
        """Not the ratified window -- the wider one `run.sh` actually used."""
        self.assertEqual(M.CAMPAIGN_SEARCH_WINDOW_V, (0.85, 2.70))

    def test_output_band_is_the_ratified_v1_range(self):
        self.assertEqual(M.OUTPUT_BAND_HZ, (10e6, 200e6))


class TestVctrlAtTarget(unittest.TestCase):
    """Linear interpolation inside the bracketing interval, and nowhere else."""

    #: f = 100 MHz at 1.5 V by construction, on a straight 50 MHz/V curve.
    CURVE = [(0.9, 70e6), (1.2, 85e6), (1.5, 100e6), (1.8, 115e6)]

    def test_exact_knot(self):
        self.assertAlmostEqual(M.vctrl_at_target(self.CURVE, 100e6), 1.5, places=9)

    def test_midpoint_of_an_interval(self):
        # Halfway between 85 and 100 MHz is halfway between 1.2 and 1.5 V.
        self.assertAlmostEqual(M.vctrl_at_target(self.CURVE, 92.5e6), 1.35, places=9)

    def test_no_extrapolation_below(self):
        self.assertIsNone(M.vctrl_at_target(self.CURVE, 50e6))

    def test_no_extrapolation_above(self):
        self.assertIsNone(M.vctrl_at_target(self.CURVE, 200e6))

    def test_flat_segment_is_not_divided_by_zero(self):
        flat = [(0.9, 100e6), (1.2, 100e6), (1.5, 130e6)]
        # The target is bracketed by a zero-slope segment; the routine must
        # skip it and still find the answer at a knot rather than raise.
        self.assertAlmostEqual(M.vctrl_at_target(flat, 100e6), 1.2, places=9)

    def test_unsorted_input_is_sorted_by_vctrl(self):
        shuffled = list(reversed(self.CURVE))
        self.assertAlmostEqual(M.vctrl_at_target(shuffled, 92.5e6), 1.35, places=9)


class TestRuleBand(unittest.TestCase):
    """`the lowest 3-bit band code that reaches f`, over a stated window."""

    #: band -> supply -> Vctrl needed for the target. Band 4 cannot reach the
    #: target at all (no entry); band 5 reaches it high in the window; band 6
    #: reaches it low. This is the real shape at `ff`/27 C, 100 MHz.
    CELL = {
        5: {2.97: 1.967, 3.30: 2.295, 3.63: 2.595},
        6: {2.97: 1.008, 3.30: 1.215, 3.63: 1.394},
    }

    def test_measured_window_selects_the_lower_band(self):
        """0.9-2.7 V: band 5's 2.595 V fits, so the rule takes band 5."""
        got = M.rule_band(self.CELL, M.DR003_WINDOW_V)
        self.assertEqual(got, 5)

    def test_predicted_window_forces_the_higher_band(self):
        """0.9-2.4 V: band 5's 2.595 V does not fit, so only band 6 is legal."""
        got = M.rule_band(self.CELL, M.DR001_WINDOW_V)
        self.assertEqual(got, 6)

    def test_a_band_missing_one_supply_is_not_selected(self):
        """Band select is static (DR-001 Decision 2) -- it must hold at all three."""
        cell = {
            4: {2.97: 1.5, 3.30: 1.8},  # no 3.63 V entry: cannot reach f there
            5: {2.97: 1.967, 3.30: 2.295, 3.63: 2.595},
        }
        self.assertEqual(M.rule_band(cell, M.DR003_WINDOW_V), 5)

    def test_no_feasible_band_returns_none(self):
        cell = {5: {2.97: 2.8, 3.30: 2.9, 3.63: 3.0}}
        self.assertIsNone(M.rule_band(cell, M.DR003_WINDOW_V))

    def test_window_edges_are_inclusive(self):
        cell = {5: {2.97: 0.9, 3.30: 1.5, 3.63: 2.7}}
        self.assertEqual(M.rule_band(cell, M.DR003_WINDOW_V), 5)


class TestMidWindowBand(unittest.TestCase):
    """`run.sh`'s selector: lowest max-|Vctrl - mid| cost over the supplies."""

    CELL = TestRuleBand.CELL

    def test_picks_band_6_at_the_campaigns_own_search_window(self):
        """The committed grid's choice at `ff`/27 C, reproduced from its rule.

        mid = (0.85 + 2.70)/2 = 1.775 V.
          band 5 cost = max(0.192, 0.520, 0.820) = 0.820
          band 6 cost = max(0.767, 0.560, 0.381) = 0.767  <- wins, narrowly
        """
        got = M.midwindow_band(self.CELL, M.CAMPAIGN_SEARCH_WINDOW_V)
        self.assertEqual(got, 6)

    def test_the_two_selectors_differ_on_this_cell(self):
        """The whole finding in one assertion."""
        self.assertNotEqual(
            M.midwindow_band(self.CELL, M.CAMPAIGN_SEARCH_WINDOW_V),
            M.rule_band(self.CELL, M.DR003_WINDOW_V),
        )

    def test_prefers_the_genuinely_central_band_when_one_exists(self):
        cell = {
            5: {2.97: 2.60, 3.30: 2.65, 3.63: 2.69},
            6: {2.97: 1.70, 3.30: 1.78, 3.63: 1.85},
        }
        self.assertEqual(M.midwindow_band(cell, M.CAMPAIGN_SEARCH_WINDOW_V), 6)

    def test_no_feasible_band_returns_none(self):
        cell = {5: {2.97: 0.1, 3.30: 0.2, 3.63: 0.3}}
        self.assertIsNone(M.midwindow_band(cell, M.CAMPAIGN_SEARCH_WINDOW_V))


class TestInterpOffset(unittest.TestCase):
    """The measured systematic term at a control voltage between grid points."""

    #: `ff`/27 C/3.63 V, from sim/pfd-deadzone's 405-point grid (ns).
    GRID = {0.90: 1.8229, 1.65: 0.6570, 2.40: 0.1750}

    def test_exact_grid_points_are_returned_unchanged(self):
        for vctrl, expected in self.GRID.items():
            value, exact = M.interp_offset(self.GRID, vctrl)
            self.assertAlmostEqual(value, expected, places=9)
            self.assertTrue(exact)

    def test_interpolates_linearly_between_grid_points(self):
        # Halfway from 0.90 to 1.65 V.
        value, exact = M.interp_offset(self.GRID, 1.275)
        self.assertAlmostEqual(value, (1.8229 + 0.6570) / 2.0, places=6)
        self.assertFalse(exact)

    def test_the_campaigns_own_operating_point(self):
        """Vctrl = 1.394 V at `ff`/27 C/3.63 V -- where 1.227 ns was measured."""
        value, _ = M.interp_offset(self.GRID, 1.394)
        self.assertAlmostEqual(value, 1.0549, places=3)

    def test_refuses_to_extrapolate_above_the_grid(self):
        """The rule parks cells past 2.40 V; that region is UNMEASURED."""
        self.assertIsNone(M.interp_offset(self.GRID, 2.595))

    def test_refuses_to_extrapolate_below_the_grid(self):
        self.assertIsNone(M.interp_offset(self.GRID, 0.85))


class TestOverRatified(unittest.TestCase):
    """Grading a systematic-only term against the ratified absolute bound."""

    def test_the_bound_is_absolute_not_a_fraction_of_a_period(self):
        # DR-012 Decision 5: a deck's acceptance on a ratified quantity IS the
        # ratified value. 1.0 ns is inside; 1.0001 ns is not.
        self.assertFalse(M.over_ratified_ns(1.0))
        self.assertTrue(M.over_ratified_ns(1.0001))

    def test_sign_does_not_matter(self):
        self.assertTrue(M.over_ratified_ns(-1.5))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
