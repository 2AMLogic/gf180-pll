#!/usr/bin/env python3
"""Unit tests for the manifest extensions issues #67, #78 and #81 add.

No PDK and no ngspice (and, for #78's ``dut_export``, no xschem) required:
ngspice's output and ``design/netlist.sh`` are both stubbed, so these run
headless like the rest of ``sim/tests/``. The one exception is the end-to-end
``raw_files`` demonstration at the bottom, which drives a *real* ngspice over a
stub model library (still no PDK) and skips itself when ngspice is absent.

    python3 -m unittest discover -s sim/tests -v

The capabilities under test, each of which the ``sim/lib/simenv.sh`` campaigns
need and the manifest could not previously express:

1. ``sweeps`` / ``grid`` -- an extra independent axis with per-point derived
   parameters, over a deliberately **non-rectangular** grid.
2. ``optional`` -- an expected ``.measure`` failure recorded as data, never
   discarding the point's successful measurements.
3. ``derived`` -- the campaign's own reduction over the per-point table,
   including a cross-record join.
4. ``dut`` -- a committed netlist export composed into the snapshot, so the
   committed fragment never becomes a generated artefact.
5. ``dut_export`` (#78) -- the per-record (non-committed) counterpart of
   ``dut``, for a block (``pfd_cp``) ``design/netlist.sh`` deliberately does
   not commit. Resolved lazily -- never at ``load()``/``--list`` time -- and
   composed into the same snapshot/provenance/deck machinery ``dut`` uses.
6. ``raw_files`` (#81) -- a file the point's OWN deck wrote (``wrdata``),
   captured per point and handed to the campaign's reduction as a parsed
   ``RawFile``. This is what makes a *sequence* claim (jitter/TIE, an I-V
   curve) expressible at all: ``.measure`` reports scalars.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
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


class DerivedSpecConcurrencyTests(unittest.TestCase):
    """#73: DerivedSpec.module() must not double-import under a thread race.

    ``run_grid()`` (harness/runner.py) dispatches PVT points across a
    ``ThreadPoolExecutor`` whenever ``-j``/``jobs > 1``, and every point in a
    run shares the *same* ``DerivedSpec`` instance (the manifest is loaded
    once). A check-then-set lazy import with no synchronization lets two
    worker threads both observe ``_module is None`` and both import -- wasted
    work at best, and silently wrong for a derive module with import-time
    side effects. These tests drive ``module()`` from many threads at once
    and assert the import ran exactly once.
    """

    N_THREADS = 8

    def _spec(self):
        return derived.DerivedSpec(module_path=Path("derive.py"), measures=("x",))

    def test_concurrent_module_calls_import_exactly_once(self):
        calls = []
        calls_lock = threading.Lock()
        # Every worker reaches spec.module() at (as close to) the same
        # instant, so an unsynchronized check-then-set has its widest
        # possible window to let more than one thread past the `is None`
        # check.
        start = threading.Barrier(self.N_THREADS)
        sentinel = object()

        def fake_load_module(path):
            with calls_lock:
                calls.append(path)
            time.sleep(0.02)  # widen the window further once inside
            return sentinel

        spec = self._spec()

        def worker(_):
            start.wait(timeout=5)
            return spec.module()

        with mock.patch.object(derived, "load_module", side_effect=fake_load_module):
            with ThreadPoolExecutor(max_workers=self.N_THREADS) as pool:
                results = list(pool.map(worker, range(self.N_THREADS)))

        self.assertEqual(len(calls), 1, "derive module was imported more than once")
        self.assertTrue(all(r is sentinel for r in results))

    def test_sequential_jobs1_behavior_is_unchanged(self):
        """The default, sequential (``jobs=1``) path: no lock contention, one import."""
        calls = []

        def fake_load_module(path):
            calls.append(path)
            return object()

        spec = self._spec()
        with mock.patch.object(derived, "load_module", side_effect=fake_load_module):
            first = spec.module()
            second = spec.module()

        self.assertIs(first, second)
        self.assertEqual(len(calls), 1)

    def test_a_load_error_still_propagates_through_the_synchronized_path(self):
        spec = self._spec()
        with mock.patch.object(
            derived, "load_module", side_effect=derived.DerivedError("boom")
        ):
            with self.assertRaises(derived.DerivedError):
                spec.module()


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

    def test_cells_containing_commas_are_quoted_not_split_into_columns(self):
        """A reduction's cells are prose -- worst-corner citations, check text.

        Emitting them with a bare ``",".join(...)`` silently turns one cell
        into several, so the committed evidence file has rows whose column
        count disagrees with its header. Records are append-only, so such a
        file cannot be repaired -- only the whole record re-minted.
        """
        table = derived.DerivedTable(
            name="retiming_margin",
            columns=("check", "worst corner", "verdict"),
            rows=(
                ("f(Vctrl) monotonic on every (corner, band) curve", "ss/-40C, B5, Vctrl 2.1 V", "PASS"),
                ('quote "inside" a cell', "no comma here", "PASS"),
            ),
            description="commas in cells",
        )
        out = self.root / "corners" / "20260101-000000-abcdef0"
        written = derived.write_derived_tables([table], out)
        body = [
            line
            for line in written[0].read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        parsed = list(csv.reader(body))
        self.assertEqual({len(r) for r in parsed}, {3})
        self.assertEqual(parsed[1][1], "ss/-40C, B5, Vctrl 2.1 V")
        self.assertEqual(parsed[2][0], 'quote "inside" a cell')
        # And the harness's own reader round-trips it.
        rows = derived.read_join_csv("x", written[0]).rows
        self.assertEqual(rows[0]["worst corner"], "ss/-40C, B5, Vctrl 2.1 V")


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
# 4b. dut_export -- #78's per-record (non-committed) counterpart of dut
# ===========================================================================

class DutExportCompositionTests(ManifestFixture):
    """#78: composes ``design/netlist.sh --top pfd_cp <outdir>`` as the DUT.

    No xschem required: ``design/netlist.sh`` is stubbed via
    ``testbench.subprocess.run``, exactly the way ``_stub_ngspice`` stubs
    ngspice for the rest of this file.
    """

    DUT_SPICE = (
        "* gf180-pll :: pfd_cp -- generated by design/netlist.sh (fake, for tests)\n"
        ".subckt pfd_cp a b\n"
        ".ends\n"
    )

    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        # Unpatched on purpose: load() must never shell out (see
        # test_loading_the_manifest_never_shells_out below), so if it ever
        # does, this setUp fails loudly for every test in the class instead
        # of silently succeeding.
        self.tb = testbench.load(
            self.write({"dut_export": {"top": "pfd_cp"}}, netlist="XDUT a b pfd_cp\n")
        )

    def _stub(self, content=None, returncode=0, stderr=""):
        content = self.DUT_SPICE if content is None else content
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if returncode == 0:
                outdir = Path(cmd[-1])
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / "dut.spice").write_text(content)
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout="", stderr=stderr
            )

        self._calls = calls
        return mock.patch.object(testbench.subprocess, "run", side_effect=fake_run)

    def test_loading_the_manifest_never_shells_out(self):
        """Mirrors the ``derived`` module's "never during --list" guarantee."""
        with mock.patch.object(testbench.subprocess, "run") as run:
            tb = testbench.load(
                self.write({"dut_export": {"top": "pfd_cp"}}, netlist="XDUT a b pfd_cp\n")
            )
        run.assert_not_called()
        self.assertIsNotNone(tb.dut_export)
        self.assertEqual(tb.dut_export.top, "pfd_cp")

    def test_resolving_runs_the_exporter_exactly_once_and_caches(self):
        with self._stub():
            first = self.tb.resolved_dut
            second = self.tb.resolved_dut
        self.assertEqual(len(self._calls), 1)
        self.assertEqual(first, second)
        self.assertTrue(first[0].is_file())
        self.assertEqual(first[0].name, "dut.spice")
        # sim/<slug>/work/dut-export/<top>/dut.spice -- the existing
        # sim/*/work/ gitignore convention, namespaced by top.
        parts = first[0].parts
        self.assertIn("work", parts)
        self.assertIn("dut-export", parts)
        self.assertIn("pfd_cp", parts)

    def test_the_exporter_is_invoked_with_top_and_an_outdir(self):
        with self._stub():
            self.tb.resolved_dut
        self.assertEqual(len(self._calls), 1)
        cmd = self._calls[0]
        self.assertTrue(str(cmd[0]).endswith("design/netlist.sh"))
        self.assertIn("--top", cmd)
        self.assertEqual(cmd[cmd.index("--top") + 1], "pfd_cp")

    def test_the_deck_includes_the_export_before_the_stimulus(self):
        point = corners.build_grid(corners.resolve_corners(["typical"]), (27,), [3.3])[0]
        with self._stub():
            deck = runner.compose_deck(self.tb, self.pdk, point)
            export_path = str(self.tb.resolved_dut[0])
        self.assertIn("pfd_cp", deck)
        self.assertLess(deck.index(export_path), deck.index(str(self.tb.netlist)))

    def test_the_snapshot_is_self_contained_and_freezes_the_export(self):
        with self._stub():
            path = report.write_netlist_snapshot(
                self.tb, self.tb.experiment_dir, "20260101-000000-abcdef0"
            )
        text = path.read_text()
        self.assertIn(".subckt pfd_cp", text)
        self.assertIn("XDUT a b pfd_cp", text)
        self.assertIn(self.tb.netlist_sha256, text)
        self.assertIn(self.tb.composed_sha256, text)
        self.assertLess(text.index(".subckt"), text.index("XDUT"))
        self.assertEqual(len(self._calls), 1)

    def test_provenance_names_the_export_with_its_own_sha(self):
        with self._stub():
            provenance = self.tb.provenance()
        self.assertEqual(len(provenance["dut"]), 1)
        self.assertIn("composed_sha256", provenance)
        self.assertIn("dut-export", provenance["dut"][0]["path"])
        self.assertNotEqual(provenance["composed_sha256"], provenance["netlist_sha256"])

    def test_concurrent_resolution_exports_exactly_once(self):
        """Same double-checked-locking guarantee ``DerivedSpec.module()`` has (#76)."""
        n_threads = 8
        start = threading.Barrier(n_threads)
        calls = []
        calls_lock = threading.Lock()

        def fake_run(cmd, **kwargs):
            with calls_lock:
                calls.append(cmd)
            time.sleep(0.02)  # widen the race window once inside
            outdir = Path(cmd[-1])
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "dut.spice").write_text(self.DUT_SPICE)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        def worker(_):
            # Every worker reaches resolved_dut at (as close to) the same
            # instant, so an unsynchronized check-then-set has its widest
            # possible window to let more than one thread past the
            # `_path is None` check -- same setup DerivedSpecConcurrencyTests
            # uses for DerivedSpec.module() (#76).
            start.wait(timeout=5)
            return self.tb.resolved_dut

        with mock.patch.object(testbench.subprocess, "run", side_effect=fake_run):
            with ThreadPoolExecutor(max_workers=n_threads) as pool:
                results = list(pool.map(worker, range(n_threads)))

        self.assertEqual(len(calls), 1, "design/netlist.sh was invoked more than once")
        self.assertTrue(all(r == results[0] for r in results))

    def test_a_nonzero_exit_surfaces_the_scripts_stderr(self):
        with self._stub(returncode=1, stderr="ERROR: xschem not found on PATH\n"):
            with self.assertRaises(RuntimeError) as ctx:
                self.tb.resolved_dut
        self.assertIn("design/netlist.sh", str(ctx.exception))
        self.assertIn("xschem not found", str(ctx.exception))

    def test_a_successful_exit_with_no_output_file_is_reported(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with mock.patch.object(testbench.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(FileNotFoundError) as ctx:
                self.tb.resolved_dut
        self.assertIn("dut.spice", str(ctx.exception))

    def test_the_exported_netlist_is_held_to_the_same_directive_rule_as_dut(self):
        """Checked lazily (at resolve time), not at load() -- the file does
        not exist yet when load() runs."""
        with self._stub(content='.lib "models" typical\n.subckt pfd_cp a b\n.ends\n'):
            with self.assertRaises(ValueError) as ctx:
                self.tb.resolved_dut
        self.assertIn("dut netlists", str(ctx.exception))

    def test_dut_and_dut_export_together_is_a_load_error(self):
        export = self.root / "netlist" / "div23_cell.spice"
        export.parent.mkdir(parents=True)
        export.write_text(".subckt div23_cell a b\n.ends\n")
        with self.assertRaises(ValueError) as ctx:
            self.write({"dut": [str(export)], "dut_export": {"top": "pfd_cp"}})
            testbench.load(self.tb_dir)
        self.assertIn("not both", str(ctx.exception))

    def test_dut_export_requires_a_top(self):
        with self.assertRaises(ValueError) as ctx:
            self.write({"dut_export": {}})
            testbench.load(self.tb_dir)
        self.assertIn("top", str(ctx.exception))

    def test_dut_export_rejects_unknown_keys(self):
        with self.assertRaises(ValueError) as ctx:
            self.write({"dut_export": {"top": "pfd_cp", "outdir": "x"}})
            testbench.load(self.tb_dir)
        self.assertIn("unknown key", str(ctx.exception))

    def test_no_dut_export_key_leaves_resolved_dut_untouched(self):
        """A manifest that uses neither key behaves exactly as before #78."""
        with mock.patch.object(testbench.subprocess, "run") as run:
            tb = testbench.load(self.write({}))
            self.assertEqual(tb.resolved_dut, ())
        run.assert_not_called()


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

    def test_the_parser_accepts_supersedes_note(self):
        args = cli.build_parser().parse_args(
            [
                "cp-compliance",
                "--supersedes",
                "20260731-194124-afa338c",
                "--supersedes-note",
                "switching-timing half only",
            ]
        )
        self.assertEqual(args.supersedes, "20260731-194124-afa338c")
        self.assertEqual(args.supersedes_note, "switching-timing half only")

    def test_supersedes_note_defaults_to_empty_when_absent(self):
        args = cli.build_parser().parse_args(["cp-compliance"])
        self.assertEqual(args.supersedes_note, "")


# ===========================================================================
# 6. raw_files -- the point's own waveform, reduced by the campaign
# ===========================================================================

#: A reduction in the exact shape sim/vco-tuning-range's jitter_extract.py has:
#: interpolated half-supply rising crossings -> a period *sequence* -> the
#: peak-to-peak time interval error. `.measure` cannot report any of it.
TIE_MODULE = '''
"""Period / TIE extraction from a wrdata-written waveform."""

from harness.derived import DerivedTable


def _crossings(t, y, threshold):
    out = []
    for i in range(1, len(t)):
        if y[i - 1] < threshold <= y[i]:
            span = y[i] - y[i - 1]
            frac = 0.0 if span == 0 else (threshold - y[i - 1]) / span
            out.append(t[i - 1] + frac * (t[i] - t[i - 1]))
    return out


def _periods(point):
    raw = point.raw("jit.dat")
    if not raw.exists():
        return []          # the deck never wrote it -- nothing to reduce
    times = raw.column("t")
    values = raw.column("clk")
    edges = _crossings(times, values, point.vdd / 2.0)
    return [b - a for a, b in zip(edges, edges[1:])]


def derive_point(point):
    periods = _periods(point)
    if len(periods) < 2:
        return {}
    return {
        "t_period": sum(periods) / len(periods),
        "tj_pp": max(periods) - min(periods),
    }


def derive_tables(run):
    rows = []
    for point in run.points:
        for index, period in enumerate(_periods(point)):
            rows.append((point.corner_id, index, "%.12g" % period))
    return [
        DerivedTable(
            name="period_sequence",
            description="every extracted period, per point",
            columns=("corner_id", "cycle", "period_s"),
            rows=tuple(rows),
        )
    ]
'''

#: Four rows of `wrdata`-shaped output: a triangle crossing 1.65 V three times
#: on the way up, giving two periods of 2 ns and 3 ns.
JIT_DAT = "\n".join(
    [
        "0.000000000000e+00  0.000000000000e+00",
        "1.000000000000e-09  3.300000000000e+00",
        "2.000000000000e-09  0.000000000000e+00",
        "3.000000000000e-09  3.300000000000e+00",
        "4.000000000000e-09  0.000000000000e+00",
        "5.000000000000e-09  0.000000000000e+00",
        "6.000000000000e-09  3.300000000000e+00",
    ]
) + "\n"


def _stub_ngspice_writing(files: dict, output: str = ""):
    """Stub ngspice so it also *writes* into whatever cwd it was handed.

    That cwd is the whole point of the mechanism under test: the harness gives
    each point its own directory precisely so two concurrent points writing the
    same ``wrdata`` filename cannot clobber one another.
    """

    def _run(cmd, **kwargs):
        cwd = Path(kwargs["cwd"])
        for name, content in files.items():
            cwd.mkdir(parents=True, exist_ok=True)
            (cwd / name).write_text(content(cwd) if callable(content) else content)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=output, stderr=""
        )

    return mock.patch.object(runner.subprocess, "run", side_effect=_run)


class RawFileManifestTests(ManifestFixture):
    """The manifest half: declaring what the deck writes."""

    def test_the_list_form_declares_a_filename_with_no_options(self):
        tb = testbench.load(self.write({"raw_files": ["jit.dat"]}))
        self.assertEqual(tb.raw_file_names, ["jit.dat"])
        self.assertEqual(tb.raw_files[0].columns, ())
        self.assertFalse(tb.raw_files[0].retain)

    def test_the_object_form_carries_columns_description_and_retain(self):
        tb = testbench.load(
            self.write(
                {
                    "raw_files": {
                        "jit.dat": {
                            "description": "three buffered clocks",
                            "columns": ["t", "clkq", "clks", "clkr"],
                            "retain": True,
                        }
                    }
                }
            )
        )
        spec = tb.raw_files[0]
        self.assertEqual(spec.columns, ("t", "clkq", "clks", "clkr"))
        self.assertEqual(spec.description, "three buffered clocks")
        self.assertTrue(spec.retain)

    def test_no_raw_files_key_leaves_the_testbench_exactly_as_before(self):
        tb = testbench.load(self.write({}))
        self.assertEqual(tb.raw_files, ())
        self.assertEqual(tb.raw_file_names, [])

    def test_a_filename_with_a_directory_part_is_rejected(self):
        for bad in ("../jit.dat", "sub/jit.dat", "/tmp/jit.dat"):
            with self.assertRaises(ValueError) as ctx:
                testbench.load(self.write({"raw_files": [bad]}))
            self.assertIn("plain filename", str(ctx.exception))

    def test_an_unknown_option_key_is_rejected_rather_than_ignored(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self.write({"raw_files": {"jit.dat": {"retian": True}}}))
        self.assertIn("retian", str(ctx.exception))

    def test_repeated_column_names_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self.write({"raw_files": {"j.dat": {"columns": ["t", "t"]}}})
            )
        self.assertIn("repeats a name", str(ctx.exception))

    def test_an_empty_declaration_is_rejected(self):
        for bad in ([], {}):
            with self.assertRaises(ValueError) as ctx:
                testbench.load(self.write({"raw_files": bad}))
            self.assertIn("omit the key", str(ctx.exception))

    def test_retaining_a_gitignored_name_is_rejected(self):
        """The evidence decision, enforced: no evidence-looking scratch file.

        `.gitignore` drops *.raw / *.log tree-wide, so retaining under one of
        those names would put a file in corners/<record-id>/ that looks like
        committed evidence and never gets committed.
        """
        for bad in ("wave.raw", "trace.LOG"):
            with self.assertRaises(ValueError) as ctx:
                testbench.load(self.write({"raw_files": {bad: {"retain": True}}}))
            self.assertIn(".gitignore", str(ctx.exception))
        # ... and the same names are fine as pure scratch.
        tb = testbench.load(self.write({"raw_files": ["wave.raw"]}))
        self.assertEqual(tb.raw_file_names, ["wave.raw"])


class RawFileCaptureTests(ManifestFixture):
    """The runner half: isolation, capture, retention, absence."""

    MANIFEST = {
        "measure": {},
        "analyses": ["tran 1n 10n", "set wr_singlescale", "wrdata jit.dat v(clk)"],
        "raw_measures": {"vavg": {"analysis": "tran", "expr": "avg v(clk)"}},
        "raw_files": {"jit.dat": {"columns": ["t", "clk"]}},
    }
    LOG = "vavg = 1.65000e+00\n"

    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.point = corners.build_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3]
        )[0]

    def _tb(self, **overrides):
        manifest = dict(self.MANIFEST)
        manifest.update(overrides)
        return testbench.load(self.write(manifest))

    def _run(self, tb, files=None, workdir="work", log_dir=None):
        with _stub_ngspice_writing(
            {"jit.dat": JIT_DAT} if files is None else files, self.LOG
        ):
            return runner.run_point(
                tb, self.pdk, self.point, self.root / workdir, log_dir=log_dir
            )

    def test_the_deck_runs_in_its_own_directory_when_raw_files_are_declared(self):
        result = self._run(self._tb())
        rundir = self.root / "work" / f"{self.point.corner_id}.d"
        self.assertTrue((rundir / "jit.dat").is_file())
        # The generated deck stays where sim/harness/README.md says it does, so
        # the documented reproduce-by-hand invocation is unchanged.
        self.assertEqual(result.deck, f"{self.point.corner_id}.spice")
        self.assertTrue((self.root / "work" / result.deck).is_file())

    def test_a_manifest_without_raw_files_still_runs_in_the_shared_workdir(self):
        seen = {}

        def _run(cmd, **kwargs):
            seen["cwd"] = Path(kwargs["cwd"])
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=self.LOG, stderr=""
            )

        tb = testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "raw_measures": {"vavg": {"analysis": "tran", "expr": "avg v(clk)"}},
                }
            )
        )
        with mock.patch.object(runner.subprocess, "run", side_effect=_run):
            runner.run_point(tb, self.pdk, self.point, self.root / "plain")
        self.assertEqual(seen["cwd"], self.root / "plain")

    def test_the_written_file_reaches_the_result_parsed_and_addressable(self):
        result = self._run(self._tb())
        raw = result.raw_files["jit.dat"]
        self.assertTrue(raw.exists())
        self.assertEqual(len(raw.rows()), 7)
        self.assertEqual(raw.column("t")[1], 1e-9)
        self.assertEqual(raw.column("clk")[1], 3.3)
        # by position as well, for a manifest that named no columns
        self.assertEqual(raw.column(0), raw.column("t"))
        self.assertEqual(result.raw_files_missing, [])

    def test_the_reduction_reads_the_waveform_back_and_produces_a_sequence_metric(self):
        """The whole point of #81: a value `.measure` cannot report."""
        self.write_module(TIE_MODULE)
        tb = self._tb(
            derived={
                "module": "derive.py",
                "measures": ["t_period", "tj_pp"],
                "tables": ["period_sequence"],
            }
        )
        result = self._run(tb)
        self.assertEqual(result.status, "ok")
        # Crossings of 1.65 V at 0.5 ns, 2.5 ns, 5.5 ns -> periods 2 ns and 3 ns.
        self.assertAlmostEqual(result.measurements["t_period"], 2.5e-9)
        self.assertAlmostEqual(result.measurements["tj_pp"], 1.0e-9)

    def test_a_raw_file_the_deck_never_wrote_is_data_not_a_crash(self):
        """The acceptance case: an early convergence failure writes nothing."""
        self.write_module(TIE_MODULE)
        tb = self._tb(
            derived={"module": "derive.py", "measures": ["t_period", "tj_pp"]}
        )
        result = self._run(tb, files={})
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.raw_files_missing, ["jit.dat"])
        self.assertFalse(result.raw_files["jit.dat"].exists())
        self.assertEqual(result.raw_files["jit.dat"].rows(), ())
        # The measurement the deck DID take survives ...
        self.assertEqual(result.measurements["vavg"], 1.65)
        # ... and the reduction that found nothing to reduce is not-measured.
        self.assertIn("t_period", result.not_measured)
        self.assertIn("tj_pp", result.not_measured)
        self.assertIn("raw_files_missing", result.as_dict())

    def test_an_undeclared_raw_file_names_the_manifest_key(self):
        self.write_module(
            'def derive_point(point):\n'
            '    return {"t_period": point.raw("other.dat").rows() and 1.0}\n'
        )
        tb = self._tb(derived={"module": "derive.py", "measures": ["t_period"]})
        result = self._run(tb)
        self.assertEqual(result.status, "error")
        self.assertIn("raw_files", result.message)
        self.assertIn("other.dat", result.message)

    def test_retain_copies_the_file_into_the_evidence_directory(self):
        tb = self._tb(raw_files={"jit.dat": {"columns": ["t", "clk"], "retain": True}})
        log_dir = self.root / "corners" / "rec-1"
        result = self._run(tb, log_dir=log_dir)
        kept = log_dir / f"{self.point.corner_id}-jit.dat"
        self.assertTrue(kept.is_file())
        self.assertEqual(kept.read_text(), JIT_DAT)
        # The reduction reads the retained copy, so a later reader of the
        # evidence tree and the recorded number came from the same bytes.
        self.assertEqual(result.raw_files["jit.dat"].path, kept)
        self.assertEqual(result.as_dict()["raw_files"], {"jit.dat": kept.name})

    def test_without_retain_nothing_lands_in_the_evidence_directory(self):
        log_dir = self.root / "corners" / "rec-2"
        result = self._run(self._tb(), log_dir=log_dir)
        self.assertEqual(
            sorted(p.name for p in log_dir.iterdir()), [f"{self.point.corner_id}.log"]
        )
        self.assertEqual(
            result.raw_files["jit.dat"].path.parent,
            self.root / "work" / f"{self.point.corner_id}.d",
        )

    def test_a_retained_file_is_banked_even_when_the_point_fails(self):
        """Evidence is captured before the required-measurement verdict."""
        tb = self._tb(raw_files={"jit.dat": {"retain": True}})
        log_dir = self.root / "corners" / "rec-3"
        with _stub_ngspice_writing({"jit.dat": JIT_DAT}, "nothing parseable here\n"):
            result = runner.run_point(
                tb, self.pdk, self.point, self.root / "workf", log_dir=log_dir
            )
        self.assertEqual(result.status, "failed")
        self.assertTrue((log_dir / f"{self.point.corner_id}-jit.dat").is_file())

    def test_concurrent_points_do_not_overwrite_each_others_output(self):
        """The hazard the per-point directory exists to remove.

        Every point's deck writes the same `wrdata` filename into its cwd; a
        shared cwd under `-j` would leave every reduction reading whichever
        point happened to finish last.
        """
        tb = self._tb()
        points = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), [3.0, 3.3]
        )
        self.assertGreater(len(points), 8)

        def content(cwd: Path) -> str:
            time.sleep(0.005)          # widen the window a shared cwd would lose
            return f"0 {len(cwd.name)}.0\n1 {abs(hash(cwd.name)) % 97}.0\n"

        with _stub_ngspice_writing({"jit.dat": content}, self.LOG):
            results = runner.run_grid(
                tb, self.pdk, points, self.root / "wgrid", jobs=6
            )
        self.assertEqual(len(results), len(points))
        for result in results:
            expected = f"{result.point.corner_id}.d"
            self.assertEqual(result.raw_files["jit.dat"].path.parent.name, expected)
            rows = result.raw_files["jit.dat"].rows()
            self.assertEqual(rows[0][1], float(len(expected)))
            self.assertEqual(rows[1][1], float(abs(hash(expected)) % 97))


class RawFileParsingTests(unittest.TestCase):
    """`RawFile` is deliberately strict about what it will reduce over."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _raw(self, text: str, columns=("t", "y")) -> derived.RawFile:
        path = self.root / "jit.dat"
        path.write_text(text)
        return derived.RawFile(name="jit.dat", path=path, columns=columns)

    def test_blank_lines_and_comments_are_skipped(self):
        raw = self._raw("# ngspice\n\n0 1\n\n* note\n1e-9 2\n")
        self.assertEqual(raw.rows(), ((0.0, 1.0), (1e-9, 2.0)))

    def test_a_leading_header_line_is_tolerated(self):
        raw = self._raw("time v(clk)\n0 1\n1 2\n")
        self.assertEqual(raw.rows(), ((0.0, 1.0), (1.0, 2.0)))

    def test_garbage_after_real_data_is_an_error_not_a_dropped_sample(self):
        raw = self._raw("0 1\n1 2\nError: timestep too small\n3 4\n")
        with self.assertRaises(derived.DerivedError) as ctx:
            raw.rows()
        self.assertIn("line 3", str(ctx.exception))

    def test_a_ragged_row_is_an_error(self):
        raw = self._raw("0 1\n1 2 3\n")
        with self.assertRaises(derived.DerivedError) as ctx:
            raw.rows()
        self.assertIn("truncated or interleaved", str(ctx.exception))

    def test_an_unknown_column_name_lists_the_declared_ones(self):
        raw = self._raw("0 1\n1 2\n")
        with self.assertRaises(derived.DerivedError) as ctx:
            raw.column("clkr")
        self.assertIn("'t', 'y'", str(ctx.exception).replace('"', "'"))

    def test_a_column_index_past_the_files_width_is_reported(self):
        raw = self._raw("0 1\n1 2\n", columns=())
        with self.assertRaises(derived.DerivedError) as ctx:
            raw.column(5)
        self.assertIn("2 column(s)", str(ctx.exception))

    def test_a_file_that_was_never_written_reads_as_empty(self):
        raw = derived.RawFile(name="jit.dat", path=self.root / "nope.dat")
        self.assertFalse(raw.exists())
        self.assertEqual(raw.rows(), ())
        self.assertEqual(raw.text(), "")
        self.assertEqual(raw.column(0), ())

    def test_parsing_happens_once_and_only_on_demand(self):
        path = self.root / "jit.dat"
        path.write_text("0 1\n1 2\n")
        raw = derived.RawFile(name="jit.dat", path=path)
        first = raw.rows()
        path.write_text("9 9\n")            # a re-read would see this
        self.assertIs(raw.rows(), first)


class RawFileRunViewTests(ManifestFixture):
    """`derive_tables` reaches every point's raw file, like a join."""

    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "gf180mcuD")
        self.write_module(TIE_MODULE)
        self.tb = testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n", "wrdata jit.dat v(clk)"],
                    "raw_measures": {
                        "vavg": {"analysis": "tran", "expr": "avg v(clk)"}
                    },
                    "raw_files": {"jit.dat": {"columns": ["t", "clk"]}},
                    "derived": {
                        "module": "derive.py",
                        "measures": ["t_period", "tj_pp"],
                        "tables": ["period_sequence"],
                    },
                }
            )
        )
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (-40, 27), [3.3]
        )

    def test_the_whole_run_reduction_sees_each_points_own_waveform(self):
        with _stub_ngspice_writing({"jit.dat": JIT_DAT}, "vavg = 1.65e+00\n"):
            results = runner.run_grid(
                self.tb, self.pdk, self.points, self.root / "wrun"
            )
        tables = cli.build_derived_tables(self.tb, results, [])
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table.name, "period_sequence")
        # two points x two extracted periods each
        self.assertEqual(len(table.rows), 4)
        self.assertEqual(
            sorted({row[0] for row in table.rows}),
            sorted(p.corner_id for p in self.points),
        )
        self.assertEqual([row[2] for row in table.rows], ["2e-09", "3e-09"] * 2)

    def test_the_scratch_files_are_still_readable_after_every_point_has_run(self):
        """`derive_tables` runs after the grid; nothing deletes the work dir."""
        with _stub_ngspice_writing({"jit.dat": JIT_DAT}, "vavg = 1.65e+00\n"):
            results = runner.run_grid(
                self.tb, self.pdk, self.points, self.root / "wrun2"
            )
        for result in results:
            self.assertTrue(result.raw_files["jit.dat"].path.is_file())


# ---------------------------------------------------------------------------
# End-to-end: a real ngspice actually writing the file the harness captures.
# ---------------------------------------------------------------------------

#: Just enough of a model library for a passives-only deck to elaborate under
#: the corner bundles corners.py names. No PDK needed -- this test exists to
#: prove the composed deck, ngspice's `wrdata`, the harness's capture and the
#: campaign's reduction line up for real, not to characterize a device.
STUB_SECTIONS = ("typical", "res_typical", "moscap_typical", "mimcap_typical")

#: A relaxation oscillator would need devices; a pulse source through an RC
#: does not, and still produces exactly what the mechanism has to carry: a
#: waveform whose *crossing sequence* is the quantity, written by the deck's
#: own `wrdata` line and reduced outside `.measure`.
E2E_FRAGMENT = """vsup vdd 0 dc 'vdd_val'
vin in 0 pulse(0 'vdd_val' 0 20p 20p 480p 1n)
r1 in out 1k
c1 out 0 100f
"""


def _have_ngspice() -> bool:
    try:
        runner.ngspice_version()
    except runner.NgspiceMissing:
        return False
    return True


@unittest.skipUnless(_have_ngspice(), "ngspice is not on PATH")
class RawFileEndToEndTests(ManifestFixture):
    """The acceptance gate: a real deck writes a file, a reduction reads it."""

    def setUp(self):
        super().setUp()
        pdk_root = self.root / "gf180mcuD"
        self.pdk = fake_pdk(pdk_root)
        models = pdk_root / "libs.tech" / "ngspice" / "sm141064.ngspice"
        models.write_text(
            "".join(f".lib {name}\n.endl {name}\n" for name in STUB_SECTIONS)
        )
        self.write_module(TIE_MODULE)
        self.tb = testbench.load(
            self.write(
                {
                    "measure": {},
                    "analyses": [
                        "tran 2p 10n",
                        "set wr_singlescale",
                        "wrdata jit.dat v(out)",
                    ],
                    "raw_measures": {
                        "vavg": {"analysis": "tran", "expr": "avg v(out)"}
                    },
                    "raw_files": {
                        "jit.dat": {
                            "columns": ["t", "clk"],
                            "description": "RC-filtered clock, one row per print step",
                            "retain": True,
                        }
                    },
                    "derived": {
                        "module": "derive.py",
                        "measures": ["t_period", "tj_pp"],
                        "tables": ["period_sequence"],
                    },
                },
                netlist=E2E_FRAGMENT,
            )
        )
        self.point = corners.build_grid(
            corners.resolve_corners(["typical"]), (27,), [3.3]
        )[0]

    def test_ngspice_writes_it_the_harness_captures_it_the_campaign_reduces_it(self):
        log_dir = self.root / "corners" / "rec-e2e"
        result = runner.run_point(
            self.tb, self.pdk, self.point, self.root / "we2e", log_dir=log_dir
        )
        self.assertEqual(result.status, "ok", result.message)

        # 1. ngspice really wrote the file, into this point's own directory ...
        raw = result.raw_files["jit.dat"]
        self.assertTrue(raw.exists())
        self.assertGreater(len(raw.rows()), 100)
        self.assertEqual(len(raw.rows()[0]), 2)     # `set wr_singlescale`

        # 2. ... it was retained as evidence next to the point's own log ...
        self.assertEqual(raw.path, log_dir / f"{self.point.corner_id}-jit.dat")
        self.assertTrue((log_dir / f"{self.point.corner_id}.log").is_file())

        # 3. ... and the campaign reduced the crossing sequence into a value
        #    `.measure` cannot report. The source is a 1 ns pulse train, so the
        #    extracted period must land on 1 ns with a tiny numerical spread.
        self.assertAlmostEqual(result.measurements["t_period"], 1e-9, delta=2e-11)
        self.assertLess(result.measurements["tj_pp"], 5e-12)


if __name__ == "__main__":
    unittest.main()
