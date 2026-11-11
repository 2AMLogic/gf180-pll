"""`sim/output-range` harness form: manifest vs. run.sh, and derive.py's scoring.

Rot this catches without a simulator run:

- tb.json drifting from `run.sh --plan` (seeds) / pll_top_dut.sh (static codes),
- the grid ceasing to be the 90-row baseline grid, or losing a rail-seeded row,
- the baseline union (two read-only records) failing to parse to 90 rows,
- derive.py's status / DN-guard scoring diverging from run.sh's `run_one`, and
  the marginal ff/27C/3.30V `hi` row handling.

Runs in the harness unit-test suite: no PDK, no ngspice, no network.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "output-range" / "testbench"

sys.path.insert(0, str(SIM_DIR))
from harness import corners as corners_mod  # noqa: E402
from harness import testbench as tb_mod  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTBENCH / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


derive = _load("derive")


class Manifest(unittest.TestCase):
    def test_tb_json_matches_generator(self):
        r = subprocess.run([sys.executable, str(TESTBENCH / "gen_tb_json.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_grid_is_the_90_row_baseline_grid(self):
        tb = tb_mod.load(TESTBENCH)
        corners = corners_mod.resolve_corners(tb.corners)
        points = corners_mod.build_sweep_grid(
            corners, tb.temperatures_c,
            corners_mod.supply_points(tb.nominal_supply_v, tb.supply_tolerance),
            axes=tb.sweeps, blocks=tb.grid_blocks)
        self.assertEqual(len(points), 90)
        self.assertEqual(len({p.corner_id for p in points}), 90)
        rail = [p for p in points if "below" in p.corner_id or "above" in p.corner_id]
        self.assertEqual(len(rail), 4)  # the four OUT-OF-WINDOW baseline rows

    def test_baseline_union_is_90_rows_with_marginal_row_capped(self):
        base, control = derive.load_baseline()
        self.assertEqual(len(base), 90)
        self.assertEqual(base[derive.MARGINAL]["status"], "CAPPED")
        self.assertEqual(control["status"], "FAIL")
        self.assertAlmostEqual(control["vctrl"], 1.4565)


class Scoring(unittest.TestCase):
    full = {"t_lock_last_rise": 1e-6, "lock_at_end": 3.3, "vctrl_final": 1.5, "dn_lvl": 0.03}

    def test_pass_and_guard(self):
        self.assertEqual(derive.score(self.full, 3.3, "in"), ("PASS", "PASS"))

    def test_fail_guard_is_suspect_when_dn_unresolved(self):
        v = dict(self.full, t_lock_last_rise=None, dn_lvl=1e-6)
        self.assertEqual(derive.score(v, 3.3, "in"), ("FAIL", "SUSPECT"))

    def test_locked_with_unresolved_dn_is_guard_fail(self):
        v = dict(self.full, dn_lvl=1e-6)
        self.assertEqual(derive.score(v, 3.3, "in"), ("PASS", "FAIL"))

    def test_rail_seed_is_out_of_window(self):
        self.assertEqual(derive.score(self.full, 3.3, "below")[0], "OUT-OF-WINDOW")

    def test_no_vctrl_is_error(self):
        self.assertEqual(derive.score({}, 3.3, "in"), ("ERROR", "ERROR"))


class Comparison(unittest.TestCase):
    base = {"status": "FAIL", "vctrl": 1.500, "dn": 0.03, "guard": "PASS"}
    control = {"status": "FAIL", "vctrl": 1.4565, "dn": 0.0339, "guard": "PASS"}
    key = ("typical", "27", "3.30", "hi")

    def test_within_tolerance_passes(self):
        new = dict(self.base, vctrl=1.504)
        self.assertEqual(derive._cmp(self.base, new, self.key, self.control)[0], "pass")

    def test_5mv_boundary_is_not_widened(self):
        new = dict(self.base, vctrl=1.5061)
        v, note = derive._cmp(self.base, new, self.key, self.control)
        self.assertEqual(v, "FAIL")
        self.assertIn("vctrl_final", note)

    def test_status_flip_fails(self):
        new = dict(self.base, status="PASS")
        self.assertEqual(derive._cmp(self.base, new, self.key, self.control)[0], "FAIL")

    def test_missing_new_row_fails_unless_baseline_also_errored(self):
        self.assertEqual(derive._cmp(self.base, None, self.key, self.control)[0], "FAIL")
        err = {"status": "ERROR", "vctrl": None, "dn": None, "guard": "ERROR"}
        self.assertEqual(derive._cmp(err, None, self.key, self.control)[0], "pass")

    def test_marginal_row_judged_against_control(self):
        capped = {"status": "CAPPED", "vctrl": None, "dn": None, "guard": "ERROR"}
        new = {"status": "FAIL", "vctrl": 1.4570, "dn": 0.033, "guard": "PASS"}
        v, note = derive._cmp(capped, new, derive.MARGINAL, self.control)
        self.assertEqual(v, "documented")
        self.assertIn("control", note)
        far = dict(new, vctrl=1.40)
        self.assertEqual(derive._cmp(capped, far, derive.MARGINAL, self.control)[0], "FAIL")


class EndToEnd(unittest.TestCase):
    """derive_tables over a synthetic run that replays the baseline's own numbers."""

    def test_replaying_the_baseline_is_a_go(self):
        from harness.derived import PointView, RunView

        base, control = derive.load_baseline()
        tb = tb_mod.load(TESTBENCH)
        corners = corners_mod.resolve_corners(tb.corners)
        grid = corners_mod.build_sweep_grid(
            corners, tb.temperatures_c,
            corners_mod.supply_points(tb.nominal_supply_v, tb.supply_tolerance),
            axes=tb.sweeps, blocks=tb.grid_blocks)
        views = []
        for p in grid:
            op = p.axes["op"]
            edge = op[:2]
            cname = getattr(p.corner, "name", p.corner)
            key = derive._key(cname, p.temp_c, p.vdd, edge)
            row = control if key == derive.MARGINAL else base[key]
            meas = {}
            if row["vctrl"] is not None:
                meas = {"vctrl_final": row["vctrl"], "dn_lvl": row["dn"], "lock_at_end": 0.0}
            views.append(PointView(corner=cname, corner_id=p.corner_id, temp_c=p.temp_c,
                                   vdd=p.vdd, axes=dict(p.axes), params={}, measurements=meas))
        tables = derive.derive_tables(RunView("output-range", (), tuple(views)))
        names = [t.name for t in tables]
        self.assertEqual(names, ["output_range_rows", "row_comparison", "baseline_comparison"])
        self.assertEqual(len(tables[0].rows), 90)
        self.assertEqual(len(tables[1].rows), 90)
        self.assertIn("= GO", tables[2].description)
        verdicts = [r[14] for r in tables[1].rows]
        self.assertEqual(verdicts.count("documented"), 1)
        self.assertEqual(verdicts.count("FAIL"), 0)

    def test_a_shifted_row_is_no_go(self):
        from harness.derived import PointView, RunView

        base, _ = derive.load_baseline()
        key = ("typical", "27", "3.30", "lo")
        pv = PointView(corner="typical", corner_id="x", temp_c=27.0, vdd=3.30,
                       axes={"op": "loin1p679"},
                       measurements={"vctrl_final": base[key]["vctrl"] + 0.02, "dn_lvl": base[key]["dn"]})
        tables = derive.derive_tables(RunView("output-range", (), (pv,)))
        self.assertIn("NO-GO", tables[2].description)


if __name__ == "__main__":
    unittest.main()
