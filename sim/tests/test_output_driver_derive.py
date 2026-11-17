"""Unit test for sim/output-driver's trise/tfall pairing (issue #969).

The failing shape: `tsettle` falls inside an edge, so the in-progress edge's
first-crossed threshold precedes the window and the "1st" crossing of that
threshold belongs to the NEXT edge. Pairing the two 1st crossings (what
trig/targ did) yields a negative time; the derivation must pair or reject.

No PDK, no ngspice.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module

derive = load_module(SIM_DIR / "output-driver" / "testbench" / "derive.py")

# Measured crossings at typical / -40 C / 3.30 V / hi (seconds), from the
# #969 instrumentation run.
MEASURED = {
    "t_r1": 1.75435e-08,
    "t_r2": 2.04131e-08,
    "t_f1": 1.60672e-08,
    "t_f2": 1.89371e-08,
    "t_r10_1": 1.74981e-08,
    "t_r10_2": 2.03676e-08,
    "t_r90_1": 1.75968e-08,
    "t_r90_2": 2.04658e-08,
    "t_f90_1": 1.88870e-08,
    "t_f90_2": 2.17578e-08,
    "t_f10_1": 1.61184e-08,
    "t_f10_2": 1.89873e-08,
}


class EdgeTimes(unittest.TestCase):
    def test_late_tsettle_fall_is_paired_not_negative(self):
        # 90 % fall=1 (18.887 ns) FOLLOWS 10 % fall=1 (16.118 ns): the failing shape.
        out = derive.derive_point(dict(MEASURED))
        self.assertAlmostEqual(out["trise"], 9.867e-11, delta=1e-13)
        self.assertGreater(out["tfall"], 0)
        # Edge 2: 90 % fall=1 (18.887) -> 10 % fall=2 (18.9873).
        self.assertAlmostEqual(out["tfall"], 1.0030e-10, delta=1e-13)

    def test_ordinary_point_unchanged(self):
        p = {
            "t_r1": 5.0,
            "t_r2": 15.0,
            "t_f1": 10.0,
            "t_f2": 20.0,
            "t_r10_1": 4.9,
            "t_r10_2": 14.9,
            "t_r90_1": 5.1,
            "t_r90_2": 15.1,
            "t_f90_1": 9.9,
            "t_f90_2": 19.9,
            "t_f10_1": 10.1,
            "t_f10_2": 20.1,
        }
        out = derive.derive_point(p)
        self.assertAlmostEqual(out["trise"], 0.2)
        self.assertAlmostEqual(out["tfall"], 0.2)

    def test_no_same_edge_pair_is_not_measured(self):
        p = dict(MEASURED)
        for k in ("t_f90_1", "t_f90_2"):
            p[k] = 3.0e-8  # both after every 10 % fall: no bracketing 50 % crossing
        out = derive.derive_point(p)
        self.assertNotIn("tfall", out)
        self.assertIn("duty_pct", out)

    def test_never_negative(self):
        for drop in list(MEASURED):
            p = {k: v for k, v in MEASURED.items() if k != drop}
            out = derive.derive_point(p)
            for name in ("trise", "tfall"):
                if name in out:
                    self.assertGreater(out[name], 0, (drop, name))


if __name__ == "__main__":
    unittest.main()
