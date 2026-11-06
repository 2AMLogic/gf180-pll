"""`sim/loop-dynamics/testbench/tb.json` against the committed evidence it pins.

Three things can rot in this manifest without any simulator run noticing:

- the 18 whole-loop cross-check design points carry Icp / Kvco / N numbers that
  came out of other records (via `pick_xcheck.py`); a hand edit would silently
  cross-check a different loop,
- the grid blocks quietly ceasing to be the baseline grid (81 filter runs from
  the 27-bundle passive box x 3 temperatures, plus 18 cross-check points),
- the passive box drifting away from the 27 bundles the baseline swept.

Runs in the harness unit-test suite: no PDK, no ngspice, no network.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "loop-dynamics" / "testbench"
KVCO = SIM_DIR / "vco-tuning-range/corners/20260731-081628-239e73b/kvco_by_point.csv"
CPDC = SIM_DIR / "cp-compliance/corners/20260731-194124-afa338c/cp_dc.csv"

sys.path.insert(0, str(SIM_DIR))
from harness import corners as corners_mod  # noqa: E402
from harness import testbench as tb_mod  # noqa: E402


class LoopDynamicsManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((TESTBENCH / "tb.json").read_text())

    def test_passive_box_is_the_27_bundle_product(self):
        box = corners_mod.CORNER_SETS["passive-box"]
        self.assertEqual(len(box), 27)
        self.assertEqual(len(set(box)), 27)
        sections = {corners_mod.PASSIVE_BOX_CORNERS[n].sections for n in box}
        self.assertEqual(len(sections), 27)
        for n in box:
            mos, res, moscap, mimcap = corners_mod.PASSIVE_BOX_CORNERS[n].sections
            self.assertEqual(mos, "typical")
            self.assertTrue(res.startswith("res_") and moscap.startswith("moscap_")
                            and mimcap.startswith("mimcap_"))
        self.assertEqual(corners_mod.PASSIVE_BOX_CORNERS["rss-mss-xss"].sections,
                         ("typical", "res_ss", "moscap_ss", "mimcap_ss"))
        # the one-family-at-a-time registry and its "full" set are untouched
        self.assertEqual(len(corners_mod.CORNER_SETS["full"]), 13)
        self.assertEqual(len(corners_mod.CORNERS), 13)

    def test_grid_is_the_baseline_grid(self):
        tb = tb_mod.load(TESTBENCH)
        corners = corners_mod.resolve_corners(tb.corners)
        points = corners_mod.build_sweep_grid(
            corners, tb.temperatures_c, corners_mod.supply_points(tb.nominal_supply_v, tb.supply_tolerance),
            axes=tb.sweeps, blocks=tb.grid_blocks)
        runs = [p.axes["run"] for p in points]
        self.assertEqual(runs.count("z"), 81)
        self.assertEqual(len(runs) - runs.count("z"), 18)
        self.assertEqual(len(points), 99)
        z = {(p.corner.name, p.temp_c) for p in points if p.axes["run"] == "z"}
        self.assertEqual(len(z), 81)

    def test_cross_check_points_match_pick_xcheck_from_pinned_tables(self):
        out = subprocess.check_output(
            [sys.executable, str(TESTBENCH / "pick_xcheck.py"), str(KVCO), str(CPDC)], text=True)
        want = {}
        for line in out.splitlines():
            tag, bundle, _libs, temp, vctrl, icp, kvco, n = line.split()
            want[tag] = (bundle, float(temp), vctrl, icp, kvco, n)
        self.assertEqual(len(want), 18)
        tb = tb_mod.load(TESTBENCH)
        points = {pt.id: pt for ax in tb.sweeps for pt in ax.points}
        seen = set()
        for pid, pt in points.items():
            if pid == "z":
                continue
            p = pt.param_map
            # find the picked point with the same electrical content
            hits = [k for k, v in want.items()
                    if v[2] == p["vctrl"] and v[3] == p["icp"] and v[4] == p["kvco"] and v[5] == p["ndiv"]]
            self.assertEqual(len(hits), 1, pid)
            seen.add(hits[0])
        self.assertEqual(seen, set(want))
        # the corner/temperature each point is scheduled on is the picked one
        blocks = {b.description: b for b in tb.grid_blocks}
        scheduled = set()
        for b in blocks.values():
            for ids in dict(b.axes).values():
                for pid in ids:
                    if pid != "z":
                        scheduled.add((b.corners[0], b.temperatures_c[0], pid))
        for bundle, temp, pid in scheduled:
            p = points[pid].param_map
            hits = [v for v in want.values() if v[2] == p["vctrl"] and v[3] == p["icp"]
                    and v[4] == p["kvco"] and v[5] == p["ndiv"]]
            self.assertIn((bundle, float(temp)), {(h[0], h[1]) for h in hits}, pid)


if __name__ == "__main__":
    unittest.main()
