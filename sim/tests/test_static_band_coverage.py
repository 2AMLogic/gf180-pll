"""Known-answer test for sim/vco-tuning-range/testbench/static_band_coverage.py (#534).

Pins the per-bundle static-code coverage table, the derated ceiling that
DR-038 quotes and the binding point `spec/pll.md` states behind it, against the
committed VCO record. No simulator, no PDK.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

M = load_module(SIM_DIR / "vco-tuning-range" / "testbench" / "static_band_coverage.py")


class StaticBandCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = M.curves()

    def reach(self, bundle, band):
        ks = M.keys_of(self.c, bundle)
        return M.reach_count(self.c, band, ks, 200e6)

    def test_grid_is_the_45_point_matrix(self):
        self.assertEqual(len(M.keys_of(self.c)), 45)

    def test_per_bundle_coverage_of_200mhz(self):
        want = {"typical": (7, 8), "ff": (6, 9), "ss": (8, 8), "fs": (7, 8), "sf": (6, 8)}
        for bu, (n6, n7) in want.items():
            self.assertEqual((self.reach(bu, 6), self.reach(bu, 7)), (n6, n7), bu)

    def test_only_ff_has_a_single_code_at_200mhz(self):
        for bu in M.BUNDLES:
            full = [b for b in M.BANDS if self.reach(bu, b) == 9]
            self.assertEqual(full, [7] if bu == "ff" else [], bu)

    def held_and_common(self):
        """Per-bundle static-code windows, and the set held in every bundle."""
        held = {}
        for bu in M.BUNDLES:
            ks = M.keys_of(self.c, bu)
            held[bu] = M.merge(
                [w[::2] for w in (M.window(self.c, b, ks) for b in M.BANDS) if w[0] <= w[2]]
            )
        common = held["typical"]
        for bu in M.BUNDLES[1:]:
            common = M.intersect(common, held[bu])
        return held, common

    def test_derated_ceiling(self):
        held, common = self.held_and_common()
        self.assertAlmostEqual(M.ceiling(common) / 1e6, 166.261, places=3)
        self.assertAlmostEqual(M.ceiling(held["sf"]) / 1e6, 169.811, places=3)
        self.assertEqual(M.ceiling(held["ff"]), 200e6)

    def test_derated_ceiling_binding_point(self):
        """spec/pll.md states the figure as "band 6, `ff`/-40 C/3.63 V ceiling"."""
        _, common = self.held_and_common()
        self.assertEqual(
            M.ceiling_binding(self.c, M.ceiling(common)), [(6, ("ff", -40.0, 3.63))]
        )
        self.assertEqual(M.fmt(("ff", -40.0, 3.63)), "ff/-40 C/3.63 V")

    def test_binding_point_is_empty_when_the_cap_binds(self):
        """`ff` alone tops out at the 200 MHz cap, which no band ceiling supplies."""
        held, _ = self.held_and_common()
        self.assertEqual(M.ceiling_binding(self.c, M.ceiling(held["ff"])), [])

    def test_check_flag_passes(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(M.main(["--check"]), 0)
        self.assertIn("Binding point: band 6, ff/-40 C/3.63 V ceiling", out.getvalue())


if __name__ == "__main__":
    unittest.main()
