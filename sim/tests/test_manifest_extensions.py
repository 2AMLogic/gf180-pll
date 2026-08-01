#!/usr/bin/env python3
"""Unit tests for the four manifest extensions issue #67 adds.

No PDK and no ngspice required: ngspice's output is stubbed, so these run
headless like the rest of ``sim/tests/``.

    python3 -m unittest discover -s sim/tests -v

The four capabilities under test, each of which the ``sim/lib/simenv.sh``
campaigns need and the manifest could not previously express:

1. ``sweeps`` / ``grid`` -- an extra independent axis with per-point derived
   parameters, over a deliberately **non-rectangular** grid.
2. ``optional`` -- an expected ``.measure`` failure recorded as data, never
   discarding the point's successful measurements.
3. ``derived`` -- the campaign's own reduction over the per-point table,
   including a cross-record join.
4. ``dut`` -- a committed netlist export composed into the snapshot, so the
   committed fragment never becomes a generated artefact.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import cli, corners, derived, report, runner, testbench  # noqa: E402
from harness.pdk import Pdk  # noqa: E402


def fake_pdk(root: Path) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text("open_pdks deadbeef\n")
    return Pdk(path=root, variant=root.name, source="test")


class ManifestFixture(unittest.TestCase):
    """Lays out ``sim/<slug>/testbench/`` the way ``sim/README.md`` specifies."""

    slug = "an-experiment"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tb_dir = self.root / self.slug / "testbench"
        self.tb_dir.mkdir(parents=True)

    def write(self, manifest: dict, netlist: str = "v1 out 0 dc {vdd_val}\n") -> Path:
        (self.tb_dir / "x.spice").write_text(netlist)
        base = {"name": self.slug, "netlist": "x.spice", "measure": {"vout": "v(out)"}}
        base.update(manifest)
        (self.tb_dir / "tb.json").write_text(json.dumps(base))
        return self.tb_dir

    def write_module(self, source: str, name: str = "derive.py") -> str:
        (self.tb_dir / name).write_text(source)
        return name


# ===========================================================================
# 1. sweeps / grid -- the extra parameter axis
# ===========================================================================

RATE_AXIS = {
    "rate": {
        "description": "input rate",
        "points": {
            # Per-point *derived* parameters: the timestep and the stop time
            # are functions of the rate, which is exactly what one fixed
            # 'params' map cannot express.
            "f200": {"params": {"kf": "200e6", "ktstep": "2e-11", "ktstop": "6e-08"}},
            "f010": {"params": {"kf": "10e6", "ktstep": "4e-10", "ktstop": "1.2e-06"}},
        },
    }
}

N_AXIS = {
    "n": {
        "description": "divide ratio",
        "points": {
            "n04": {"params": {"kn": "4", "ksel1": "1"}},
            "n33": {"params": {"kn": "33", "ksel5": "1", "kp0": "1"}},
            "n64": {"params": {"kn": "64", "ksel5": "1", "ktstep": "5e-12"}},
        },
    }
}


class SweepAxisTests(ManifestFixture):
    def test_axis_and_its_points_load_in_manifest_order(self):
        tb = testbench.load(self.write({"sweeps": RATE_AXIS}))
        self.assertEqual([a.name for a in tb.sweeps], ["rate"])
        self.assertEqual(tb.sweeps[0].ids, ("f200", "f010"))
        self.assertEqual(tb.sweeps[0].description, "input rate")
        self.assertEqual(
            tb.sweeps[0].points[0].param_map,
            {"kf": "200e6", "ktstep": "2e-11", "ktstop": "6e-08"},
        )

    def test_no_sweeps_key_leaves_the_grid_exactly_as_before(self):
        tb = testbench.load(self.write({}))
        self.assertEqual(tb.sweeps, ())
        plain = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), [2.97, 3.3, 3.63]
        )
        swept = corners.build_sweep_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), [2.97, 3.3, 3.63], axes=tb.sweeps
        )
        self.assertEqual([p.corner_id for p in swept], [p.corner_id for p in plain])

    def test_corner_id_appends_one_field_per_axis_in_declaration_order(self):
        """sim/README.md: [<kind>_]<bundle>_<temp>c_<supply>v[_<extra>...]."""
        tb = testbench.load(self.write({"sweeps": {**RATE_AXIS, **N_AXIS}}))
        points = corners.build_sweep_grid(
            corners.resolve_corners(["ss"]), (125,), [2.97], axes=tb.sweeps
        )
        ids = {p.corner_id for p in points}
        self.assertIn("ss_125c_2.97v_f200_n64", ids)
        self.assertIn("ss_125c_2.97v_f010_n04", ids)
        # The three fixed fields keep their meaning and position.
        for point in points:
            head = point.corner_id.split("_")[:3]
            self.assertEqual(head, ["ss", "125c", "2.97v"])

    def test_a_point_id_may_not_contain_the_field_separator(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self.write({"sweeps": {"rate": {"points": {"f_200": {"params": {}}}}}})
            )
        self.assertIn("corner-id", str(ctx.exception))

    def test_axis_params_reach_the_deck_after_the_fixed_params(self):
        tb = testbench.load(self.write({"sweeps": RATE_AXIS, "params": {"ktstep": "1e-9"}}))
        point = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3], axes=tb.sweeps
        )[0]
        deck = runner.compose_deck(tb, fake_pdk(self.root / "gf180mcuD"), point)
        self.assertIn(".param kf=200e6", deck)
        # The axis wins over the manifest default, which is what lets a fine
        # axis override a coarse one instead of naming a disjoint parameter set.
        self.assertLess(deck.index(".param ktstep=1e-9"), deck.index(".param ktstep=2e-11"))

    def test_the_analysis_line_is_filled_in_from_the_points_parameters(self):
        """ngspice's .control block does NOT resolve .param braces itself.

        A top-level `.tran {ktstep} {ktstop}` is substituted by ngspice; the
        same text as a control-block command is not, and fails with "TSTEP is
        invalid". Every campaign whose timestep is a function of a swept rate
        needs the number spliced in per point.
        """
        tb = testbench.load(
            self.write({"sweeps": RATE_AXIS, "analyses": ["tran {ktstep} {ktstop}"]})
        )
        points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3], axes=tb.sweeps
        )
        pdk = fake_pdk(self.root / "gf180mcuD")
        self.assertIn("tran 2e-11 6e-08", runner.compose_deck(tb, pdk, points[0]))
        self.assertIn("tran 4e-10 1.2e-06", runner.compose_deck(tb, pdk, points[1]))

    def test_substitution_leaves_an_unknown_placeholder_alone(self):
        self.assertEqual(
            runner.substitute_params("tran {ktstep} {mystery}", {"ktstep": "1n"}),
            "tran 1n {mystery}",
        )
        self.assertEqual(runner.substitute_params("op", {}), "op")

    def test_pvt_values_are_substitutable_too(self):
        tb = testbench.load(self.write({"analyses": ["tran 1n {temp_c}n"]}))
        point = corners.build_grid(corners.resolve_corners(["ss"]), (125,), [3.63])[0]
        deck = runner.compose_deck(tb, fake_pdk(self.root / "gf180mcuD"), point)
        self.assertIn("tran 1n 125.0n", deck)

    def test_a_full_cross_product_is_the_default_when_no_grid_is_declared(self):
        tb = testbench.load(self.write({"sweeps": RATE_AXIS}))
        points = corners.build_sweep_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), [2.97, 3.3, 3.63], axes=tb.sweeps
        )
        self.assertEqual(len(points), 45 * 2)

    def test_axis_filter_narrows_an_axis_without_editing_the_manifest(self):
        tb = testbench.load(self.write({"sweeps": RATE_AXIS}))
        points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]),
            (27,),
            [3.3],
            axes=tb.sweeps,
            axis_filter={"rate": ["f010"]},
        )
        self.assertEqual([p.corner_id for p in points], ["typical_27c_3.30v_f010"])

    def test_axis_filter_rejects_an_unknown_axis_or_point(self):
        tb = testbench.load(self.write({"sweeps": RATE_AXIS}))
        with self.assertRaises(KeyError):
            corners.build_sweep_grid(
                corners.resolve_corners(["typical"]), (27,), [3.3],
                axes=tb.sweeps, axis_filter={"nope": ["x"]},
            )
        with self.assertRaises(KeyError):
            corners.build_sweep_grid(
                corners.resolve_corners(["typical"]), (27,), [3.3],
                axes=tb.sweeps, axis_filter={"rate": ["f999"]},
            )


class NonRectangularGridTests(ManifestFixture):
    """The shape sim/divider-ratio/chain needs: a union of justified slices."""

    GRID = [
        {
            "description": "every N at the two stress corners",
            "corners": ["ss", "ff"],
            "temperatures_c": [125],
            "supplies": ["low"],
            "axes": {"rate": ["f200"], "n": ["n04", "n33", "n64"]},
        },
        {
            "description": "three N over the full grid",
            "axes": {"rate": ["f200"], "n": ["n04", "n33"]},
        },
        {
            "description": "N=64 only at the binding (low) supply",
            "supplies": ["low"],
            "axes": {"rate": ["f200"], "n": ["n64"]},
        },
        {
            "description": "bottom-of-band rate check, hot only",
            "temperatures_c": [125],
            "supplies": ["low"],
            "axes": {"rate": ["f010"], "n": ["n04", "n64"]},
        },
    ]

    def setUp(self):
        super().setUp()
        self.tb = testbench.load(
            self.write({"sweeps": {**RATE_AXIS, **N_AXIS}, "grid": self.GRID})
        )
        self.points = corners.build_sweep_grid(
            corners.resolve_corners(["mos"]),
            (-40, 27, 125),
            [2.97, 3.3, 3.63],
            axes=self.tb.sweeps,
            blocks=self.tb.grid_blocks,
        )

    def test_the_point_set_is_the_union_of_the_blocks_not_the_cross_product(self):
        rectangular = 45 * 2 * 3
        self.assertLess(len(self.points), rectangular)
        # Full grid at N in {4, 33} at 200 MHz.
        self.assertEqual(sum(1 for p in self.points if p.axes["n"] in ("n04", "n33")
                             and p.axes["rate"] == "f200"), 90)
        # N=64 at 200 MHz only at 2.97 V.
        n64 = [p for p in self.points if p.axes["n"] == "n64" and p.axes["rate"] == "f200"]
        self.assertEqual({p.vdd for p in n64}, {2.97})
        # 10 MHz only at 125 C / 2.97 V, and only for two N.
        f010 = [p for p in self.points if p.axes["rate"] == "f010"]
        self.assertEqual({p.temp_c for p in f010}, {125.0})
        self.assertEqual({p.axes["n"] for p in f010}, {"n04", "n64"})

    def test_overlapping_blocks_simulate_a_point_once(self):
        ids = [p.corner_id for p in self.points]
        self.assertEqual(len(ids), len(set(ids)))
        # Block 1 and block 2 both ask for ss/125C/2.97V/f200/n04.
        self.assertEqual(ids.count("ss_125c_2.97v_f200_n04"), 1)

    def test_a_point_is_attributed_to_the_block_that_first_asked_for_it(self):
        point = next(p for p in self.points if p.corner_id == "ss_125c_2.97v_f200_n04")
        self.assertEqual(point.block, "every N at the two stress corners")

    def test_indexes_stay_contiguous_after_de_duplication(self):
        self.assertEqual([p.index for p in self.points], list(range(len(self.points))))

    def test_conformance_reports_the_thinning_and_still_sees_a_full_pvt_matrix(self):
        conformance = report.matrix_conformance(self.tb, self.points)
        # The union still covers the mandated P x V x T matrix ...
        self.assertTrue(conformance["full"], conformance["missing"])
        # ... and says, explicitly, that the extra-axis grid is not a rectangle.
        self.assertTrue(conformance["thinned"])
        self.assertEqual(conformance["rectangular_points"], 45 * 2 * 3)
        self.assertEqual(
            [b["description"] for b in conformance["blocks"]],
            [b["description"] for b in self.GRID],
        )
        self.assertTrue(all(b["points"] for b in conformance["blocks"]))
        self.assertEqual(conformance["empty_blocks"], [])

    def test_a_block_the_cli_starved_is_reported_rather_than_silently_dropped(self):
        """--corners typical starves the stress-corner block; that must show."""
        points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]),
            (-40, 27, 125),
            [2.97, 3.3, 3.63],
            axes=self.tb.sweeps,
            blocks=self.tb.grid_blocks,
        )
        self.assertEqual(
            corners.empty_blocks(self.tb.grid_blocks, points),
            ["every N at the two stress corners"],
        )
        conformance = report.matrix_conformance(self.tb, points)
        self.assertEqual(
            conformance["empty_blocks"], ["every N at the two stress corners"]
        )

    def test_supply_aliases_track_the_resolved_rails(self):
        """'low' must follow --supply/--supply-tol, not a hardcoded 2.97."""
        points = corners.build_sweep_grid(
            corners.resolve_corners(["mos"]),
            (-40, 27, 125),
            corners.supply_points(5.0, 0.10),
            axes=self.tb.sweeps,
            blocks=self.tb.grid_blocks,
        )
        n64 = [p for p in points if p.axes["n"] == "n64" and p.axes["rate"] == "f200"]
        self.assertEqual({p.vdd for p in n64}, {4.5})

    def test_a_numeric_supply_that_matches_nothing_contributes_nothing(self):
        block = corners.GridBlock(description="x", supplies=(1.8,))
        self.assertEqual(corners.resolve_block_supplies(block.supplies, [2.97, 3.3]), [])

    def test_grid_blocks_must_each_carry_a_justification(self):
        with self.assertRaises(ValueError) as ctx:
            self.write({"sweeps": RATE_AXIS, "grid": [{"axes": {"rate": ["f200"]}}]})
            testbench.load(self.tb_dir)
        self.assertIn("description", str(ctx.exception))

    def test_grid_blocks_reject_an_undeclared_axis_point(self):
        with self.assertRaises(ValueError) as ctx:
            self.write(
                {
                    "sweeps": RATE_AXIS,
                    "grid": [{"description": "typo", "axes": {"rate": ["f999"]}}],
                }
            )
            testbench.load(self.tb_dir)
        self.assertIn("f999", str(ctx.exception))

    def test_a_grid_without_sweeps_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.write({"grid": [{"description": "nothing to thin"}]})
            testbench.load(self.tb_dir)
        self.assertIn("sweeps", str(ctx.exception))

    def test_duplicate_block_descriptions_are_rejected(self):
        with self.assertRaises(ValueError):
            self.write(
                {
                    "sweeps": RATE_AXIS,
                    "grid": [
                        {"description": "same", "axes": {"rate": ["f200"]}},
                        {"description": "same", "axes": {"rate": ["f010"]}},
                    ],
                }
            )
            testbench.load(self.tb_dir)


# ===========================================================================
# 2. optional measurements -- an expected .measure failure is data
# ===========================================================================

def _stub_ngspice(output: str):
    """Patch ``subprocess.run`` so ``run_point`` sees a canned ngspice log."""
    return mock.patch.object(
        runner.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=output, stderr=""),
    )


class OptionalMeasureTests(ManifestFixture):
    """sim/lock-detector's shape: a copy that must NEVER assert."""

    MANIFEST = {
        "measure": {},
        "analyses": ["tran 1n 10n"],
        "raw_measures": {
            "twin_r": {"analysis": "tran", "expr": "trig v(a) val=1 targ v(b) val=1"},
            "tb_asrt": {"analysis": "tran", "expr": "when v(lb)=1.65 rise=1"},
            "tc_asrt": {
                "analysis": "tran",
                "expr": "when v(lc)=1.65 rise=1",
                "optional": True,
            },
            "td_asrt": {
                "analysis": "tran",
                "expr": "when v(ld)=1.65 rise=1",
                "optional": True,
            },
        },
    }

    # Exactly the failure transcript issue #67 quotes: the deep-out-of-lock
    # copy never asserts, so its .meas fails -- while three other measurements
    # in the same run succeeded.
    LOG = "\n".join(
        [
            "twin_r  =  1.20000e-09 targ=  2.0e-07 trig=  1.9e-07",
            "tb_asrt =  4.50000e-07",
            "Error: measure  tc_asrt  when(WHEN) : out of interval",
            "Error: measure  td_asrt  when(WHEN) : out of interval",
        ]
    )

    def setUp(self):
        super().setUp()
        self.tb = testbench.load(self.write(self.MANIFEST))
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.point = corners.build_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3]
        )[0]

    def _run(self, log: str) -> runner.PointResult:
        with _stub_ngspice(log):
            return runner.run_point(self.tb, self.pdk, self.point, self.root / "work")

    def test_the_flag_loads_and_only_optional_names_are_droppable(self):
        self.assertEqual(self.tb.optional_measures, frozenset({"tc_asrt", "td_asrt"}))
        self.assertEqual(self.tb.required_measure_names, ["twin_r", "tb_asrt"])
        self.assertTrue(self.tb.is_optional("tc_asrt"))
        self.assertFalse(self.tb.is_optional("tb_asrt"))

    def test_an_absent_optional_measure_does_not_fail_the_point(self):
        result = self._run(self.LOG)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.missing, [])

    def test_the_points_successful_measurements_survive(self):
        """The second-order damage issue #67 names: good data thrown away."""
        result = self._run(self.LOG)
        self.assertEqual(result.measurements["twin_r"], 1.2e-09)
        self.assertEqual(result.measurements["tb_asrt"], 4.5e-07)

    def test_the_absence_is_recorded_as_data(self):
        result = self._run(self.LOG)
        self.assertEqual(sorted(result.not_measured), ["tc_asrt", "td_asrt"])
        self.assertIn("not_measured", result.as_dict())

    def test_a_missing_required_measure_still_fails_the_point(self):
        result = self._run("tb_asrt = 4.5e-07\n")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.missing, ["twin_r"])
        # ... and the optional absences are still reported alongside.
        self.assertEqual(sorted(result.not_measured), ["tc_asrt", "td_asrt"])

    def test_a_point_where_every_measurement_is_optional_and_fails_is_still_recorded(self):
        tb = testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "raw_measures": {
                        "a": {"analysis": "tran", "expr": "when v(a)=1", "optional": True},
                        "b": {"analysis": "tran", "expr": "when v(b)=1", "optional": True},
                    },
                }
            )
        )
        with _stub_ngspice("Error: measure  a  when(WHEN) : out of interval\n"):
            result = runner.run_point(tb, self.pdk, self.point, self.root / "work2")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.measurements, {})
        self.assertEqual(sorted(result.not_measured), ["a", "b"])

    def test_optional_let_expression_measures_use_the_object_form(self):
        tb = testbench.load(
            self.write({"measure": {"vout": {"expr": "v(out)", "optional": True}}})
        )
        self.assertEqual(tb.measure, {"vout": "v(out)"})
        self.assertEqual(tb.optional_measures, frozenset({"vout"}))

    def test_a_misspelled_optional_key_is_rejected_rather_than_ignored(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self.write({"measure": {"vout": {"expr": "v(out)", "optionnal": True}}})
            )
        self.assertIn("optionnal", str(ctx.exception))

    def test_a_non_boolean_optional_is_rejected(self):
        with self.assertRaises(ValueError):
            testbench.load(
                self.write({"measure": {"vout": {"expr": "v(out)", "optional": "yes"}}})
            )


class OptionalSummaryTests(unittest.TestCase):
    """An optional measurement's absence must read as a result, not a gap."""

    def setUp(self):
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (-40, 27, 125), [3.3]
        )
        self.results = [
            runner.PointResult(
                point=p,
                status="ok",
                measurements={"tb_asrt": 1e-6},
                not_measured=["tc_asrt"],
            )
            for p in self.points
        ]

    def test_summary_marks_the_optional_measure_and_counts_its_absences(self):
        summary = report.summarize(
            self.results, ["tb_asrt", "tc_asrt"], optional_names={"tc_asrt"}
        )
        self.assertEqual(summary["tc_asrt"], {"n": 0, "optional": True, "n_absent": 3})
        self.assertEqual(summary["tb_asrt"]["n"], 3)
        self.assertNotIn("optional", summary["tb_asrt"])

    def test_spread_checks_do_not_punish_a_measure_that_correctly_never_fired(self):
        summary = report.summarize(self.results, ["tc_asrt"], optional_names={"tc_asrt"})
        failures = report.evaluate_checks(
            {"tc_asrt": {"max_spread_pct": 5.0}}, self.results, summary
        )
        self.assertEqual(failures, [])

    def test_max_measured_points_expresses_must_never_assert(self):
        summary = report.summarize(self.results, ["tc_asrt"], optional_names={"tc_asrt"})
        self.assertEqual(
            report.evaluate_checks(
                {"tc_asrt": {"max_measured_points": 0}}, self.results, summary
            ),
            [],
        )
        asserted = list(self.results)
        asserted[1] = runner.PointResult(
            point=self.points[1], status="ok", measurements={"tc_asrt": 2e-6}
        )
        summary = report.summarize(asserted, ["tc_asrt"], optional_names={"tc_asrt"})
        failures = report.evaluate_checks(
            {"tc_asrt": {"max_measured_points": 0}}, asserted, summary
        )
        self.assertEqual(
            (failures[0]["kind"], failures[0]["value"], failures[0]["at"]),
            ("max_measured_points", 1, "grid"),
        )

    def test_min_measured_points_expresses_must_always_assert(self):
        summary = report.summarize(
            self.results, ["tb_asrt", "tc_asrt"], optional_names={"tc_asrt"}
        )
        self.assertEqual(
            report.evaluate_checks(
                {"tb_asrt": {"min_measured_points": 3}}, self.results, summary
            ),
            [],
        )
        failures = report.evaluate_checks(
            {"tc_asrt": {"min_measured_points": 1}}, self.results, summary
        )
        self.assertEqual(failures[0]["kind"], "min_measured_points")


# ===========================================================================
# 3. derived metrics -- the reduction that IS the claim
# ===========================================================================

LADDER_MODULE = '''
"""A setup-ladder reduction, in the shape sim/divider-ratio/dff needs."""

LADDER = [1.00e-9, 0.20e-9, 0.10e-9, 0.05e-9, 0.02e-9]


def derive_point(point):
    # The smallest ladder step whose clk->Q has not degraded >10% against the
    # relaxed reference. A step whose .meas FAILED never captured, and is a
    # violated point -- which is only expressible because an absent optional
    # measurement reaches this function as None rather than as a dead point.
    reference = point.get("cq0")
    if reference is None:
        return {}
    tsetup = LADDER[-1]
    for i in range(1, len(LADDER)):
        value = point.get(f"cq{i}")
        if value is None or value > 1.1 * reference:
            tsetup = LADDER[i - 1]
            break
    return {"tsetup": tsetup}
'''

JOIN_MODULE = '''
"""A cross-record join, in the shape retiming_margin.csv needs."""

from harness.derived import DerivedTable


def derive_tables(run):
    dff = run.join("dff").index_by("process", "temp_c", "vdd_v")
    rows = []
    for point in run.points:
        key = (point.corner, f"{point.temp_c:g}", f"{point.vdd:.2f}")
        prior = dff.get(key)
        if prior is None:
            continue
        t_arr = point.get("t_arr")
        tvco = 1.0 / float(point.params["kf"])
        margin = tvco - t_arr - float(prior["tsetup_s"])
        rows.append(
            (point.corner, point.temp_c, point.vdd, t_arr,
             prior["tsetup_s"], f"{margin:.6g}", "CLOSES" if margin > 0 else "FAILS")
        )
    return [
        DerivedTable(
            name="retiming_margin",
            description="T_vco - t_arr - tsetup, joined against the dff record",
            columns=("process", "temp_c", "vdd_v", "t_arr_s", "tsetup_s",
                     "setup_margin_s", "verdict"),
            rows=tuple(rows),
        )
    ]
'''


class DerivedPointTests(ManifestFixture):
    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.point = corners.build_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3]
        )[0]
        self.module = self.write_module(LADDER_MODULE)

    def _tb(self):
        return testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "raw_measures": {
                        f"cq{i}": {
                            "analysis": "tran",
                            "expr": f"trig v(ck) val=1.65 targ v(q{i}) val=1.65",
                            "optional": True,
                        }
                        for i in range(5)
                    },
                    "derived": {"module": self.module, "measures": ["tsetup"]},
                }
            )
        )

    def test_derived_measures_join_the_records_measurement_set(self):
        tb = self._tb()
        self.assertEqual(tb.derived_measure_names, ["tsetup"])
        self.assertEqual(tb.measure_names[-1], "tsetup")
        # ... but are never treated as a required simulated measurement.
        self.assertNotIn("tsetup", tb.required_measure_names)
        self.assertTrue(tb.is_optional("tsetup"))

    def test_the_reduction_runs_per_point_and_lands_in_measurements(self):
        log = "\n".join(
            ["cq0 = 1.00e-10", "cq1 = 1.02e-10", "cq2 = 1.05e-10",
             "cq3 = 2.00e-10", "cq4 = 3.00e-10"]
        )
        with _stub_ngspice(log):
            result = runner.run_point(self._tb(), self.pdk, self.point, self.root / "w")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.measurements["tsetup"], 0.10e-9)

    def test_a_failed_ladder_step_is_what_makes_the_scan_work(self):
        """The step whose .meas failed is 'violated', not 'missing data'."""
        log = "\n".join(["cq0 = 1.00e-10", "cq1 = 1.02e-10",
                         "Error: measure  cq2  when(WHEN) : out of interval"])
        with _stub_ngspice(log):
            result = runner.run_point(self._tb(), self.pdk, self.point, self.root / "w2")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.measurements["tsetup"], 0.20e-9)
        self.assertIn("cq2", result.not_measured)

    def test_a_reduction_that_finds_nothing_records_not_measured_not_an_error(self):
        with _stub_ngspice("Error: measure  cq0  when(WHEN) : out of interval\n"):
            result = runner.run_point(self._tb(), self.pdk, self.point, self.root / "w3")
        self.assertEqual(result.status, "ok")
        self.assertNotIn("tsetup", result.measurements)
        self.assertIn("tsetup", result.not_measured)

    def test_an_undeclared_derived_name_is_an_error_not_a_dropped_column(self):
        self.write_module(
            "def derive_point(point):\n    return {'typo_here': 1.0}\n", name="bad.py"
        )
        tb = testbench.load(
            self.write(
                {
                    "measure": {"vout": "v(out)"},
                    "derived": {"module": "bad.py", "measures": ["tsetup"]},
                }
            )
        )
        with _stub_ngspice("m_vout = 1.0\n"):
            result = runner.run_point(tb, self.pdk, self.point, self.root / "w4")
        self.assertEqual(result.status, "error")
        self.assertIn("typo_here", result.message)

    def test_a_derived_measure_may_not_shadow_a_simulated_one(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self.write(
                    {
                        "measure": {"vout": "v(out)"},
                        "derived": {"module": self.module, "measures": ["vout"]},
                    }
                )
            )
        self.assertIn("collides", str(ctx.exception))

    def test_a_derived_block_must_declare_something(self):
        with self.assertRaises(ValueError):
            testbench.load(
                self.write({"derived": {"module": self.module}})
            )

    def test_the_derive_module_must_live_inside_the_testbench_directory(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self.write(
                    {"derived": {"module": "../../escape.py", "measures": ["tsetup"]}}
                )
            )
        self.assertIn("testbench directory", str(ctx.exception))

    def test_declaring_measures_without_the_hook_is_a_load_time_shaped_error(self):
        self.write_module("def derive_tables(run):\n    return []\n", name="only_tables.py")
        tb = testbench.load(
            self.write(
                {
                    "measure": {"vout": "v(out)"},
                    "derived": {"module": "only_tables.py", "measures": ["tsetup"]},
                }
            )
        )
        with self.assertRaises(derived.DerivedError) as ctx:
            derived.derive_point_measures(
                tb.derived,
                derived.PointView(corner="typical", corner_id="x", temp_c=27, vdd=3.3),
            )
        self.assertIn("derive_point", str(ctx.exception))


class CrossRecordJoinTests(ManifestFixture):
    """retiming_margin.csv: one record's table joined against another's."""

    slug = "divider-chain"

    def setUp(self):
        super().setUp()
        self.module = self.write_module(JOIN_MODULE)
        # A CSV in exactly the shape a prior record wrote it: a '#' provenance
        # preamble, then the header, then rows.
        self.prior = self.root / "dff_setup_hold.csv"
        self.prior.write_text(
            "# gf180-pll :: divider-ratio/dff :: record 20260101-000000-abcdef0\n"
            "# tsetup_s: worst of the two banks\n"
            "process,temp_c,vdd_v,tsetup_s\n"
            "typical,27,3.30,1.0e-10\n"
            "ss,125,2.97,3.0e-10\n"
        )
        self.tb = testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "sweeps": RATE_AXIS,
                    "raw_measures": {
                        "t_arr": {"analysis": "tran", "expr": "trig v(a) targ v(b)"}
                    },
                    "derived": {
                        "module": self.module,
                        "tables": ["retiming_margin"],
                        "joins": {"dff": "does-not-exist.csv"},
                    },
                }
            )
        )
        self.points = corners.build_sweep_grid(
            corners.resolve_corners(["typical", "ss"]),
            (27, 125),
            [2.97, 3.3],
            axes=self.tb.sweeps,
            axis_filter={"rate": ["f200"]},
        )
        self.results = [
            runner.PointResult(point=p, status="ok", measurements={"t_arr": 1.0e-9})
            for p in self.points
        ]

    def test_the_join_is_parsed_past_the_provenance_preamble(self):
        table = derived.read_join_csv("dff", self.prior)
        self.assertEqual(table.columns, ("process", "temp_c", "vdd_v", "tsetup_s"))
        self.assertEqual(len(table.rows), 2)
        indexed = table.index_by("process", "temp_c", "vdd_v")
        self.assertEqual(indexed[("typical", "27", "3.30")]["tsetup_s"], "1.0e-10")

    def test_indexing_on_a_missing_column_names_the_column(self):
        table = derived.read_join_csv("dff", self.prior)
        with self.assertRaises(derived.DerivedError) as ctx:
            table.index_by("process", "nope")
        self.assertIn("nope", str(ctx.exception))

    def test_the_cli_join_flag_overrides_the_manifests_placeholder(self):
        tables = cli.build_derived_tables(
            self.tb, self.results, [f"dff={self.prior}"]
        )
        self.assertEqual([t.name for t in tables], ["retiming_margin"])
        rows = {(r[0], r[1], r[2]): r for r in tables[0].rows}
        # Only the two PVT points the prior record covers are joined.
        self.assertEqual(sorted(rows), [("ss", 125.0, 2.97), ("typical", 27.0, 3.3)])
        # T_vco (5 ns at 200 MHz) - t_arr (1 ns) - tsetup (0.1 ns) = 3.9 ns.
        self.assertAlmostEqual(float(rows[("typical", 27.0, 3.3)][5]), 3.9e-9)
        self.assertEqual(rows[("typical", 27.0, 3.3)][6], "CLOSES")

    def test_a_missing_join_input_is_reported_by_alias_and_path(self):
        with self.assertRaises(derived.DerivedError) as ctx:
            cli.build_derived_tables(self.tb, self.results, [])
        self.assertIn("dff", str(ctx.exception))
        self.assertIn("does-not-exist.csv", str(ctx.exception))

    def test_a_declared_table_the_module_never_returns_is_an_error(self):
        self.write_module("def derive_tables(run):\n    return []\n", name="empty.py")
        tb = testbench.load(
            self.write(
                {
                    "measure": {"vout": "v(out)"},
                    "derived": {"module": "empty.py", "tables": ["retiming_margin"]},
                }
            )
        )
        with self.assertRaises(derived.DerivedError) as ctx:
            cli.build_derived_tables(tb, self.results, [])
        self.assertIn("retiming_margin", str(ctx.exception))

    def test_derived_tables_are_written_as_append_only_csv(self):
        tables = cli.build_derived_tables(self.tb, self.results, [f"dff={self.prior}"])
        out = self.root / "corners" / "20260101-000000-abcdef0"
        written = derived.write_derived_tables(tables, out)
        self.assertEqual([p.name for p in written], ["retiming_margin.csv"])
        text = written[0].read_text()
        self.assertTrue(text.startswith("# T_vco - t_arr - tsetup"))
        self.assertIn("process,temp_c,vdd_v,t_arr_s,tsetup_s,setup_margin_s,verdict", text)
        with self.assertRaises(derived.DerivedError):
            derived.write_derived_tables(tables, out)


# ===========================================================================
# 4. dut composition
# ===========================================================================

class DutCompositionTests(ManifestFixture):
    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.export = self.root / "netlist" / "div23_cell.spice"
        self.export.parent.mkdir(parents=True)
        self.export.write_text(
            "* generated by design/netlist.sh -- do not edit by hand\n"
            ".subckt div23_cell CKIN CKOUT VDD VSS\n"
            "XI CKIN CKOUT VDD VSS inv_3v3\n"
            ".ends\n"
        )
        self.tb = testbench.load(
            self.write(
                {"dut": [str(self.export)]},
                netlist="XDUT ck out {vdd_val} 0 div23_cell\n",
            )
        )

    def test_the_dut_export_is_composed_ahead_of_the_stimulus(self):
        self.assertEqual(self.tb.dut, (self.export,))
        self.assertEqual(self.tb.netlist_sources, (self.export, self.tb.netlist))

    def test_the_deck_includes_the_export_before_the_fragment(self):
        point = corners.build_grid(corners.resolve_corners(["typical"]), (27,), [3.3])[0]
        deck = runner.compose_deck(self.tb, self.pdk, point)
        self.assertLess(deck.index(str(self.export)), deck.index(str(self.tb.netlist)))

    def test_the_committed_fragment_never_contains_the_export(self):
        """The whole point: the fragment stays hand-written, not generated."""
        self.assertNotIn(".subckt", self.tb.netlist.read_text())

    def test_the_snapshot_is_self_contained_with_a_sha_per_source(self):
        experiment = self.tb.experiment_dir
        path = report.write_netlist_snapshot(self.tb, experiment, "20260101-000000-abcdef0")
        text = path.read_text()
        self.assertIn(".subckt div23_cell", text)          # the DUT
        self.assertIn("XDUT ck out", text)                  # the stimulus
        self.assertIn(self.tb.netlist_sha256, text)
        self.assertIn(self.tb.composed_sha256, text)
        self.assertLess(text.index(".subckt"), text.index("XDUT"))

    def test_provenance_names_every_source_with_its_own_sha(self):
        provenance = self.tb.provenance()
        self.assertEqual(len(provenance["dut"]), 1)
        self.assertIn("composed_sha256", provenance)
        self.assertNotEqual(provenance["composed_sha256"], provenance["netlist_sha256"])

    def test_a_dut_export_is_held_to_the_same_directive_rule_as_a_fragment(self):
        self.export.write_text('.lib "models" typical\n.subckt x a b\n.ends\n')
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self.tb_dir)
        self.assertIn("dut netlists", str(ctx.exception))

    def test_a_missing_export_points_at_the_exporter(self):
        self.export.unlink()
        with self.assertRaises(FileNotFoundError) as ctx:
            testbench.load(self.tb_dir)
        self.assertIn("design/netlist.sh", str(ctx.exception))

    def test_no_dut_key_leaves_the_snapshot_byte_for_byte_as_before(self):
        tb = testbench.load(self.write({}))
        path = report.write_netlist_snapshot(
            tb, tb.experiment_dir, "20260101-000001-abcdef0"
        )
        text = path.read_text()
        self.assertIn("* source     :", text)
        self.assertTrue(text.endswith("v1 out 0 dc {vdd_val}\n"))


# ===========================================================================
# End to end: one manifest that uses all four, rendered into a record
# ===========================================================================

class ExtendedRecordRenderingTests(ManifestFixture):
    slug = "divider-ratio"

    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.export = self.root / "netlist" / "divider_chain.spice"
        self.export.parent.mkdir(parents=True)
        self.export.write_text(".subckt divider_chain a b\n.ends\n")
        self.write_module(
            "from harness.derived import DerivedTable\n"
            "\n"
            "def derive_tables(run):\n"
            "    return [DerivedTable(name='window_edge',\n"
            "                         description='largest error that still asserted',\n"
            "                         notes=('one row per ladder corner',),\n"
            "                         columns=('corner', 'largest_asserting'),\n"
            "                         rows=(('typical/27C/3.30V', '1.2e-09'),))]\n"
        )
        self.tb = testbench.load(
            self.write(
                {
                    "dut": [str(self.export)],
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "raw_measures": {
                        "n_fb": {"analysis": "tran", "expr": "trig v(a) targ v(b)"},
                        "tc_asrt": {
                            "analysis": "tran",
                            "expr": "when v(lc)=1.65 rise=1",
                            "optional": True,
                        },
                    },
                    "sweeps": RATE_AXIS,
                    "grid": [
                        {
                            "description": "top of band over the full grid",
                            "axes": {"rate": ["f200"]},
                        },
                        {
                            "description": "bottom of band, hot and low only",
                            "temperatures_c": [125],
                            "supplies": ["low"],
                            "axes": {"rate": ["f010"]},
                        },
                    ],
                    "derived": {"module": "derive.py", "tables": ["window_edge"]},
                    "checks": {"tc_asrt": {"max_measured_points": 0}},
                },
                netlist="XDUT a b divider_chain\n",
            )
        )
        self.points = corners.build_sweep_grid(
            corners.resolve_corners(["mos"]),
            (-40, 27, 125),
            corners.supply_points(3.3, 0.10),
            axes=self.tb.sweeps,
            blocks=self.tb.grid_blocks,
        )
        self.results = [
            runner.PointResult(
                point=p,
                status="ok",
                measurements={"n_fb": 64.0},
                not_measured=["tc_asrt"],
            )
            for p in self.points
        ]
        self.tables = cli.build_derived_tables(self.tb, self.results, [])
        self.conformance = report.matrix_conformance(self.tb, self.points)
        self.record = report.build_record(
            tb=self.tb,
            pdk=self.pdk,
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260101-000000-abcdef0",
            started_utc="2026-01-01T00:00:00+00:00",
            wall_seconds=1.0,
            derived_tables=self.tables,
            conformance=self.conformance,
        )
        self.text = report.render_record(self.record, self.slug)

    def test_the_run_is_non_rectangular_but_still_a_full_pvt_matrix(self):
        self.assertEqual(len(self.points), 45 + 5)
        self.assertTrue(self.conformance["full"])
        self.assertTrue(self.conformance["thinned"])

    def test_every_ratified_field_survives_the_extended_schema(self):
        for field in (
            "Record ID", "Claim", "Netlist provenance", "Environment provenance",
            "Corner matrix run", "Methodology / criteria / limitations",
            "Statistical convention", "Result", "Links", "Timestamp / author",
            "Supersedes",
        ):
            self.assertIn(f"**{field}**", self.text, field)

    def test_the_corner_matrix_field_names_every_swept_variable_and_its_points(self):
        self.assertIn("Extra swept variables", self.text)
        self.assertIn("`rate` — input rate: `f200`, `f010`", self.text)

    def test_a_thinned_grid_states_itself_with_the_manifests_own_justifications(self):
        self.assertIn("Deliberately non-rectangular", self.text)
        self.assertIn("top of band over the full grid — 45 point(s)", self.text)
        self.assertIn("bottom of band, hot and low only — 5 point(s)", self.text)

    def test_corner_ids_carry_the_extra_field(self):
        self.assertIn("`ss_125c_2.97v_f010`", self.text)
        self.assertIn("`typical_-40c_2.97v_f200`", self.text)

    def test_an_absent_optional_measure_renders_as_data_not_as_a_gap(self):
        self.assertIn("| not measured |", self.text)
        self.assertIn("not measured at all 50 completed point(s)", self.text)
        self.assertNotIn("| `tc_asrt` | no data", self.text)

    def test_the_never_asserted_check_passes_and_the_record_says_pass(self):
        self.assertEqual(self.record["checks"]["failures"], [])
        self.assertIn("**Overall: PASS**", self.text)

    def test_the_derived_table_is_rendered_and_linked(self):
        self.assertIn("**window_edge** (derived) — largest error that still asserted", self.text)
        self.assertIn("one row per ladder corner", self.text)
        self.assertIn("| corner | largest_asserting |", self.text)
        self.assertIn(
            f"`sim/{self.slug}/corners/20260101-000000-abcdef0/window_edge.csv`", self.text
        )

    def test_netlist_provenance_names_the_composed_export(self):
        self.assertIn("composed with stimulus", self.text)
        self.assertIn(self.tb.composed_sha256, self.text)

    def test_the_record_declares_which_measurements_were_optional(self):
        self.assertEqual(self.record["optional_measures"], ["tc_asrt"])
        self.assertIn("optional: an absent result is data", self.record["measure"]["tc_asrt"])


class CliArgumentTests(unittest.TestCase):
    def test_axis_flag_parses_into_a_per_axis_id_list(self):
        self.assertEqual(
            cli.parse_axis_filters(["n=n04,n64", "rate=f200"]),
            {"n": ["n04", "n64"], "rate": ["f200"]},
        )

    def test_join_flag_parses_into_alias_paths(self):
        self.assertEqual(
            cli.parse_key_value(["dff=divider-ratio/corners/x/dff.csv"], "--join"),
            {"dff": "divider-ratio/corners/x/dff.csv"},
        )

    def test_a_malformed_flag_is_rejected_with_the_flag_name(self):
        for bad in (["n"], ["=n04"], ["n="]):
            with self.assertRaises(ValueError) as ctx:
                cli.parse_key_value(bad, "--axis")
            self.assertIn("--axis", str(ctx.exception))

    def test_the_parser_accepts_the_new_flags(self):
        args = cli.build_parser().parse_args(
            ["divider-ratio", "--axis", "n=n64", "--join", "dff=x.csv"]
        )
        self.assertEqual(args.axis, ["n=n64"])
        self.assertEqual(args.join, ["dff=x.csv"])


if __name__ == "__main__":
    unittest.main()
