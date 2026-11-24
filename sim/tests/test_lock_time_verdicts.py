#!/usr/bin/env python3
"""``sim/lock-time/testbench/tb.json`` row verdicts against run.sh's rules.

The manifest is a port of the legacy runner, whose per-row decisions must not
change at the same measured values:

- a row is a lock PASS only if a LOCK rising edge was measured AND LOCK ended
  high; a missing edge is FAIL,
- the DN guard floor is ``3e-4 * VDD`` of each point, with the legacy
  PASS / FAIL (lock PASS, DN low) / SUSPECT (not a lock PASS, DN low)
  dispositions kept apart.

No PDK, no ngspice.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "lock-time" / "testbench"
sys.path.insert(0, str(SIM_DIR))

from harness import corners, derived, report, runner, testbench  # noqa: E402

FLOOR_FRAC = 3e-4


def _result(vdd, rise=1.0e-6, end=None, dn=0.05, vfin=1.2):
    """A PointResult at one supply, run through the manifest's own reduction."""
    tb = testbench.load(TESTBENCH)
    point = next(
        p
        for p in corners.build_grid(
            corners.resolve_corners(["typical"]), (27.0,),
            corners.supply_points(3.3, 0.10),
        )
        if abs(p.vdd - vdd) < 1e-9
    )
    meas = {
        "lock_at_end": vdd if end is None else end,
        "vctrl_final": vfin,
        "dn_lvl": dn,
    }
    not_measured = []
    if rise is None:
        not_measured.append("t_lock_last_rise")
    else:
        meas["t_lock_last_rise"] = rise
    view = derived.PointView(
        corner=point.corner.name, corner_id=point.corner_id, temp_c=point.temp_c,
        vdd=point.vdd, measurements=dict(meas),
    )
    meas.update(derived.derive_point_measures(tb.derived, view))
    return tb, runner.PointResult(
        point=point, status="ok", measurements=meas, not_measured=not_measured
    )


def _verdict(**kw):
    tb, result = _result(**kw)
    return report.point_verdicts(tb, [result])[result.point.corner_id], result


class LockEdgeRequired(unittest.TestCase):
    def test_complete_row_with_edge_passes(self):
        verdict, _ = _verdict(vdd=3.63)
        self.assertEqual(verdict, "PASS")

    def test_missing_rise_with_final_lock_high_fails(self):
        # the Judge's constructed row: lock_at_end=3.63, dn_lvl=0.01, no rise
        verdict, result = _verdict(vdd=3.63, rise=None, end=3.63, dn=0.01)
        self.assertTrue(verdict.startswith("FAIL"), verdict)
        self.assertIn("lock_pass", verdict)
        # the other measurements of the row are kept
        self.assertEqual(result.measurements["lock_at_end"], 3.63)
        self.assertEqual(result.measurements["dn_lvl"], 0.01)

    def test_final_lock_low_fails_even_with_edge(self):
        verdict, _ = _verdict(vdd=3.30, end=0.1)
        self.assertTrue(verdict.startswith("FAIL"), verdict)


class DnGuardIsSupplyRelative(unittest.TestCase):
    def test_floor_scales_with_each_supply(self):
        for vdd in (2.97, 3.30, 3.63):
            floor = FLOOR_FRAC * vdd
            ok, _ = _verdict(vdd=vdd, dn=floor)
            self.assertEqual(ok, "PASS", vdd)
            low, result = _verdict(vdd=vdd, dn=floor * 0.99)
            self.assertTrue(low.startswith("FAIL"), (vdd, low))
            self.assertEqual(result.measurements["dn_guard"], 0.0)

    def test_between_the_old_fixed_floor_and_the_3v63_floor_fails(self):
        # 0.001 V cleared the fixed 0.00089 V floor but not 3e-4 * 3.63
        verdict, result = _verdict(vdd=3.63, dn=0.001)
        self.assertTrue(verdict.startswith("FAIL"), verdict)
        self.assertIn("dn_guard", verdict)
        self.assertEqual(result.measurements["dn_guard"], 0.0)

    def test_the_lowest_supply_keeps_its_lower_floor(self):
        verdict, _ = _verdict(vdd=2.97, dn=0.00090)
        self.assertEqual(verdict, "PASS")

    def test_unlocked_row_with_low_dn_is_suspect_not_fail(self):
        verdict, result = _verdict(vdd=3.63, end=0.1, dn=0.001)
        self.assertTrue(verdict.startswith("FAIL"), verdict)
        self.assertEqual(result.measurements["dn_guard"], 1.0)

    def test_unlocked_row_with_asserting_dn_passes_the_guard(self):
        _, result = _verdict(vdd=3.30, end=0.1, dn=0.05)
        self.assertEqual(result.measurements["dn_guard"], 2.0)

    def test_missing_edge_with_low_dn_is_suspect(self):
        _, result = _verdict(vdd=3.63, rise=None, end=3.63, dn=0.001)
        self.assertEqual(result.measurements["dn_guard"], 1.0)

    def test_raw_dn_voltage_is_retained(self):
        _, result = _verdict(vdd=3.30, dn=0.0123)
        self.assertEqual(result.measurements["dn_lvl"], 0.0123)


if __name__ == "__main__":
    unittest.main()
