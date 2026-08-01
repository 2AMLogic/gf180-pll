#!/usr/bin/env python3
"""Unit tests for the PVT harness. No PDK and no ngspice required.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import corners, report, runner, testbench  # noqa: E402
from harness.pdk import Pdk  # noqa: E402


def fake_pdk(root: Path) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text("open_pdks deadbeef\n")
    return Pdk(path=root, variant=root.name, source="test")


class CornerTests(unittest.TestCase):
    def test_pvt_axes_match_the_mandated_grid(self):
        self.assertEqual(corners.DEFAULT_TEMPERATURES_C, (-40.0, 27.0, 125.0))
        self.assertAlmostEqual(corners.DEFAULT_SUPPLY_TOLERANCE, 0.10)

    def test_supply_points_are_nominal_plus_minus_ten_percent(self):
        self.assertEqual(corners.supply_points(3.3, 0.10), [2.97, 3.3, 3.63])

    def test_zero_tolerance_collapses_the_voltage_axis(self):
        self.assertEqual(corners.supply_points(3.3, 0.0), [3.3])

    def test_every_corner_names_one_section_per_device_family(self):
        for name, corner in corners.CORNERS.items():
            with self.subTest(corner=name):
                self.assertEqual(len(corner.sections), 4, corner.sections)
                # MOS + resistor + MOS-cap + MIM-cap: no requirement that all
                # four differ (most bundles skew exactly one family).

    def test_no_bjt_or_diode_axis(self):
        """This repo's device menu has no BJT/diode -- unlike gf180-bandgap."""
        for corner in corners.CORNERS.values():
            for section in corner.sections:
                self.assertNotIn("bjt", section)
                self.assertNotIn("diode", section)

    def test_corner_sets_expand_and_deduplicate(self):
        resolved = corners.resolve_corners(["mos", "typical"])
        self.assertEqual([c.name for c in resolved], ["typical", "ff", "ss", "fs", "sf"])

    def test_full_set_includes_every_bundle(self):
        resolved = corners.resolve_corners(["full"])
        self.assertEqual(len(resolved), len(corners.CORNERS))

    def test_unknown_corner_is_rejected(self):
        with self.assertRaises(KeyError):
            corners.resolve_corners(["nope"])

    def test_grid_is_full_factorial_and_ordered(self):
        grid = corners.build_grid(corners.resolve_corners(["mos"]), (-40, 27, 125), [2.97, 3.3, 3.63])
        self.assertEqual(len(grid), 5 * 3 * 3)
        self.assertEqual(len({p.corner_id for p in grid}), 45)

    def test_corner_id_matches_the_ratified_naming(self):
        """sim/README.md: <corner-id> is <process>_<temp>c_<supply>v."""
        grid = corners.build_grid(
            corners.resolve_corners(["typical", "ss", "ff"]), (-40, 27, 125), [2.97, 3.3, 3.63]
        )
        ids = {p.corner_id for p in grid}
        self.assertIn("typical_27c_3.30v", ids)
        self.assertIn("ss_-40c_2.97v", ids)
        self.assertIn("ff_125c_3.63v", ids)

    def test_passive_only_bundles_hold_mos_at_typical(self):
        for name in ("res_ff", "res_ss", "moscap_ff", "moscap_ss", "mimcap_ff", "mimcap_ss"):
            with self.subTest(corner=name):
                self.assertEqual(corners.CORNERS[name].sections[0], "typical")

    def test_all_slow_and_all_fast_skew_every_family(self):
        slow = corners.CORNERS["all-slow"]
        self.assertEqual(slow.sections, ("ss", "res_ss", "moscap_ss", "mimcap_ss"))
        fast = corners.CORNERS["all-fast"]
        self.assertEqual(fast.sections, ("ff", "res_ff", "moscap_ff", "mimcap_ff"))


class TestbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _write(self, netlist: str, manifest: dict | None = None) -> Path:
        """Lay out sim/<slug>/testbench/ the way sim/README.md specifies."""
        tb_dir = self.dir / "an-experiment" / "testbench"
        tb_dir.mkdir(parents=True, exist_ok=True)
        (tb_dir / "x.spice").write_text(netlist)
        base = {"name": "x", "netlist": "x.spice", "measure": {"vout": "v(out)"}}
        base.update(manifest or {})
        (tb_dir / "tb.json").write_text(json.dumps(base))
        return tb_dir

    def test_loads_a_valid_manifest(self):
        tb = testbench.load(self._write("v1 out 0 dc {vdd_val}\n"))
        self.assertEqual(tb.name, "x")
        self.assertEqual(tb.measure, {"vout": "v(out)"})
        self.assertEqual(tb.temperatures_c, (-40.0, 27.0, 125.0))
        self.assertEqual(tb.measure_names, ["vout"])

    def test_experiment_slug_comes_from_the_directory_layout(self):
        tb_dir = self._write("v1 out 0 dc {vdd_val}\n")
        # Loadable by testbench dir *and* by experiment dir.
        for target in (tb_dir, tb_dir.parent):
            with self.subTest(target=target.name):
                tb = testbench.load(target)
                self.assertEqual(tb.experiment, "an-experiment")
                self.assertEqual(tb.experiment_dir.name, "an-experiment")

    def test_discover_finds_experiments_not_bare_manifest_dirs(self):
        self._write("v1 out 0 dc {vdd_val}\n")
        found = testbench.discover(self.dir)
        self.assertEqual([p.name for p in found], ["an-experiment"])

    def test_rejects_netlists_that_pin_the_temperature(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._write("v1 out 0 dc 3.3\n.temp 27\n"))
        self.assertIn(".temp", str(ctx.exception))

    def test_rejects_netlists_that_include_models_themselves(self):
        with self.assertRaises(ValueError):
            testbench.load(self._write('.lib "models" typical\nv1 out 0 dc 3.3\n'))

    def test_rejects_netlists_that_embed_a_measure(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._write(".measure tran t1 when v(out)=1.0\nv1 out 0 dc 3.3\n"))
        self.assertIn(".measure", str(ctx.exception))

    def test_rejects_a_manifest_without_measurements(self):
        with self.assertRaises(ValueError):
            testbench.load(self._write("v1 out 0 dc 3.3\n", {"measure": {}}))

    def test_raw_measures_load(self):
        tb = testbench.load(
            self._write(
                "v1 out 0 dc {vdd_val}\n",
                {
                    "measure": {},
                    "analyses": ["tran 1n 10n"],
                    "raw_measures": {
                        "tpd": {"analysis": "tran", "expr": "when v(out)=1.0 rise=1"}
                    },
                },
            )
        )
        self.assertIn("tpd", tb.raw_measures)
        self.assertEqual(tb.raw_measures["tpd"].analysis, "tran")
        self.assertEqual(tb.measure_names, ["tpd"])

    def test_raw_measures_require_a_matching_analysis(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self._write(
                    "v1 out 0 dc {vdd_val}\n",
                    {
                        "measure": {},
                        "analyses": ["op"],
                        "raw_measures": {
                            "tpd": {"analysis": "tran", "expr": "when v(out)=1.0 rise=1"}
                        },
                    },
                )
            )
        self.assertIn("tran", str(ctx.exception))

    def test_measure_and_raw_measures_cannot_share_a_name(self):
        with self.assertRaises(ValueError):
            testbench.load(
                self._write(
                    "v1 out 0 dc {vdd_val}\n",
                    {
                        "measure": {"x": "v(out)"},
                        "analyses": ["op", "tran 1n 10n"],
                        "raw_measures": {"x": {"analysis": "tran", "expr": "when v(out)=1.0"}},
                    },
                )
            )

    def test_no_topology_groups_by_default(self):
        """Single-topology manifests stay flat -- '()' is the renderer's signal."""
        tb = testbench.load(self._write("v1 out 0 dc {vdd_val}\n"))
        self.assertEqual(tb.topology_groups, ())
        self.assertEqual(tb.measure_groups, ())

    def _multi_topology(self, groups) -> Path:
        return self._write(
            "v1 out 0 dc {vdd_val}\n",
            {
                "measure": {"ring_f": "v(a)", "ring_i": "v(b)", "chain_tpd": "v(c)"},
                "topology_groups": groups,
            },
        )

    def test_topology_groups_load_in_manifest_order(self):
        tb = testbench.load(
            self._multi_topology(
                {"ring": ["ring_f", "ring_i"], "chain": ["chain_tpd"]}
            )
        )
        self.assertEqual([g.name for g in tb.topology_groups], ["ring", "chain"])
        self.assertEqual(tb.topology_groups[0].measures, ("ring_f", "ring_i"))
        self.assertEqual(tb.topology_groups[0].description, "")
        # No leftovers -> measure_groups is exactly what the manifest declared.
        self.assertEqual([g.name for g in tb.measure_groups], ["ring", "chain"])

    def test_topology_group_object_form_carries_a_description(self):
        tb = testbench.load(
            self._multi_topology(
                {
                    "ring": {
                        "description": "5-stage current-starved ring",
                        "measures": ["ring_f", "ring_i"],
                    },
                    "chain": ["chain_tpd"],
                }
            )
        )
        self.assertEqual(tb.topology_groups[0].description, "5-stage current-starved ring")
        self.assertEqual(tb.topology_groups[0].measures, ("ring_f", "ring_i"))
        self.assertEqual(tb.topology_groups[1].description, "")

    def test_partial_grouping_collects_the_rest_into_an_ungrouped_group(self):
        """A group set covering only SOME names must not drop the others."""
        tb = testbench.load(self._multi_topology({"ring": ["ring_f", "ring_i"]}))
        groups = tb.measure_groups
        self.assertEqual([g.name for g in groups], ["ring", testbench.UNGROUPED_TOPOLOGY])
        self.assertEqual(groups[-1].measures, ("chain_tpd",))
        # Every measurement is still accounted for exactly once.
        self.assertEqual(
            sorted(n for g in groups for n in g.measures), sorted(tb.measure_names)
        )

    def test_topology_groups_reject_an_unknown_measurement_name(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._multi_topology({"ring": ["ring_f", "typo_here"]}))
        self.assertIn("typo_here", str(ctx.exception))

    def test_topology_groups_reject_a_misspelled_key(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._multi_topology({"ring": {"measure": ["ring_f"]}}))
        self.assertIn("measures", str(ctx.exception))

    def test_topology_groups_reject_the_reserved_ungrouped_name(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(
                self._multi_topology({testbench.UNGROUPED_TOPOLOGY: ["ring_f"]})
            )
        self.assertIn("reserved", str(ctx.exception))

    def test_topology_groups_reject_an_empty_group(self):
        with self.assertRaises(ValueError):
            testbench.load(self._multi_topology({"ring": []}))

    def test_topology_groups_must_be_an_object(self):
        with self.assertRaises(ValueError) as ctx:
            testbench.load(self._multi_topology([["ring_f"]]))
        self.assertIn("topology_groups", str(ctx.exception))

    def test_the_repo_selftest_testbench_is_valid(self):
        tb = testbench.load(SIM_DIR / "harness-selftest")
        self.assertEqual(tb.nominal_supply_v, 3.3)
        self.assertEqual(tb.experiment, "harness-selftest")
        self.assertIn("idsat_n", tb.raw_measures)
        self.assertIn("idsat_n", tb.checks)


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "tb").mkdir()
        (root / "tb" / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (root / "tb" / "tb.json").write_text(
            json.dumps(
                {
                    "name": "x",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)", "iq": "-i(v1)"},
                    "analyses": ["op", "tran 1n 10n"],
                    "raw_measures": {
                        "tpd": {"analysis": "tran", "expr": "when v(out)=1.0 rise=1"}
                    },
                    "params": {"cload": "1p"},
                    "options": ["reltol=1e-5"],
                }
            )
        )
        self.tb = testbench.load(root / "tb")
        self.pdk = fake_pdk(root / "gf180mcuD")
        self.point = corners.build_grid(corners.resolve_corners(["ss"]), (125,), [3.63])[0]
        self.deck = runner.compose_deck(self.tb, self.pdk, self.point)

    def test_deck_sets_the_pvt_point(self):
        self.assertIn(".param vdd_val=3.63", self.deck)
        self.assertIn(".param vdd_nom=3.3", self.deck)
        self.assertIn(".temp 125", self.deck)

    def test_deck_includes_design_switches_before_model_sections(self):
        design_at = self.deck.index("design.ngspice")
        lib_at = self.deck.index("sm141064.ngspice")
        self.assertLess(design_at, lib_at)

    def test_deck_selects_every_section_of_the_corner(self):
        for section in self.point.corner.sections:
            self.assertIn(f'sm141064.ngspice" {section}', self.deck)

    def test_deck_has_no_extra_lib_sections_by_default(self):
        """Omitting the key must compose exactly the deck it always did."""
        self.assertEqual(self.tb.extra_lib_sections, ())
        self.assertEqual(
            self.deck.count('sm141064.ngspice"'), len(self.point.corner.sections)
        )

    def test_deck_appends_extra_lib_sections_after_the_corner_bundle(self):
        """A section no bundle carries (e.g. cap_mim) is added at every point."""
        root = Path(self.tmp.name)
        (root / "tb2").mkdir()
        (root / "tb2" / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (root / "tb2" / "tb.json").write_text(
            json.dumps(
                {
                    "name": "x",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "extra_lib_sections": ["cap_mim", "cap_mim"],
                }
            )
        )
        tb = testbench.load(root / "tb2")
        self.assertEqual(tb.extra_lib_sections, ("cap_mim",))  # de-duplicated
        deck = runner.compose_deck(tb, self.pdk, self.point)
        self.assertIn('sm141064.ngspice" cap_mim', deck)
        last_bundle = self.point.corner.sections[-1]
        self.assertLess(
            deck.index(f'sm141064.ngspice" {last_bundle}'),
            deck.index('sm141064.ngspice" cap_mim'),
        )

    def test_extra_lib_sections_must_be_a_list_of_names(self):
        root = Path(self.tmp.name)
        (root / "tb3").mkdir()
        (root / "tb3" / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (root / "tb3" / "tb.json").write_text(
            json.dumps(
                {
                    "name": "x",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "extra_lib_sections": "cap_mim",
                }
            )
        )
        with self.assertRaises(ValueError) as ctx:
            testbench.load(root / "tb3")
        self.assertIn("extra_lib_sections", str(ctx.exception))

    def test_deck_carries_manifest_params_and_options(self):
        self.assertIn(".param cload=1p", self.deck)
        self.assertIn(".options reltol=1e-5", self.deck)

    def test_deck_emits_one_measurement_vector_per_measure_entry(self):
        self.assertIn("let m_vout = v(out)", self.deck)
        self.assertIn("let m_iq = -i(v1)", self.deck)
        self.assertIn("print m_vout", self.deck)
        self.assertTrue(self.deck.rstrip().endswith(".end"))

    def test_deck_emits_a_literal_measure_statement_for_raw_measures(self):
        self.assertIn(".measure tran tpd when v(out)=1.0 rise=1", self.deck)
        # Raw measures are declared before .control, not inside it -- ngspice
        # evaluates them per-analysis regardless of what runs afterward.
        self.assertLess(self.deck.index(".measure tran tpd"), self.deck.index(".control"))

    def test_deck_quits_after_raw_measures_to_skip_ngspice_s_redundant_rerun(self):
        """See #86: with a netlist-level `.measure` card in the deck, ngspice
        batch mode re-runs every `.analyses` line a second time after the
        `.control` block finishes, purely to service that card -- doubling
        wall clock for identical numbers. A `quit` at the end of the
        `.control` block (after the `let`/`print` lines it must not precede)
        ends the session before that second pass starts."""
        control_at = self.deck.index(".control")
        endc_at = self.deck.index(".endc")
        quit_at = self.deck.index("\n  quit\n")
        print_at = self.deck.rindex("print m_")
        self.assertLess(control_at, quit_at)
        self.assertLess(print_at, quit_at)
        self.assertLess(quit_at, endc_at)

    def test_deck_omits_quit_when_no_raw_measures_are_declared(self):
        root = Path(self.tmp.name)
        (root / "tb4").mkdir()
        (root / "tb4" / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (root / "tb4" / "tb.json").write_text(
            json.dumps(
                {
                    "name": "x",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "analyses": ["op"],
                }
            )
        )
        tb = testbench.load(root / "tb4")
        deck = runner.compose_deck(tb, self.pdk, self.point)
        # No netlist `.measure` card means ngspice never re-runs the
        # analyses, so there is nothing for `quit` to pre-empt. (The
        # `set noaskquit` line legitimately contains the substring "quit" --
        # check for the standalone control-block command, not the substring.)
        self.assertNotIn("\n  quit\n", deck)


class ParseTests(unittest.TestCase):
    def test_parses_let_expression_output(self):
        text = "\n".join(
            [
                "Circuit: * x",
                "m_vout = 1.2003456789e+00",
                "m_iq = -4.5e-05",
                "v(other) = 9.9",
                "m_bad = not_a_number",
            ]
        )
        self.assertEqual(
            runner.parse_measurements(text), {"vout": 1.2003456789, "iq": -4.5e-05}
        )

    def test_parses_raw_measure_output_with_trailing_fields(self):
        """A trig/targ .measure prints extra fields after the value on the
        same line (e.g. 'res_tau = 3.8e-09 targ= 2.0e-07 trig= 1.9e-07')."""
        text = "res_tau             =  3.82724e-09 targ=  2.03827e-07 trig=  2.00000e-07"
        self.assertEqual(
            runner.parse_measurements(text, raw_names=["res_tau"]), {"res_tau": 3.82724e-09}
        )

    def test_raw_measure_name_does_not_false_positive_on_a_longer_name(self):
        text = "res_tau2 = 1.0e-06\n"
        self.assertEqual(runner.parse_measurements(text, raw_names=["res_tau"]), {})

    def test_a_failed_raw_measure_is_simply_absent(self):
        text = "Error: measure  ttest  when(WHEN) : out of interval\n .measure tran ttest when v(b)=0.5 rise=1 failed!\n"
        self.assertEqual(runner.parse_measurements(text, raw_names=["ttest"]), {})


class _StubPoint:
    def __init__(self, corner_id):
        self.corner_id = corner_id


class _StubResult:
    def __init__(self, corner_id, measurements, status="ok"):
        self.point = _StubPoint(corner_id)
        self.measurements = measurements
        self.status = status


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            _StubResult("a", {"v": 1.0}),
            _StubResult("b", {"v": 1.2}),
            _StubResult("c", {"v": 0.8}),
        ]
        self.summary = report.summarize(self.results, ["v"])

    def test_summary_finds_the_extremes(self):
        stats = self.summary["v"]
        self.assertEqual((stats["min"], stats["min_at"]), (0.8, "c"))
        self.assertEqual((stats["max"], stats["max_at"]), (1.2, "b"))
        self.assertAlmostEqual(stats["spread_pct"], 40.0)

    def test_min_max_violations_are_reported_with_their_corner(self):
        failures = report.evaluate_checks({"v": {"min": 0.9}}, self.results, self.summary)
        self.assertEqual(len(failures), 1)
        self.assertEqual((failures[0]["kind"], failures[0]["at"]), ("min", "c"))

    def test_max_spread_violation(self):
        failures = report.evaluate_checks(
            {"v": {"max_spread_pct": 10.0}}, self.results, self.summary
        )
        self.assertEqual(failures[0]["kind"], "max_spread_pct")

    def test_min_spread_catches_a_grid_that_never_moved(self):
        flat = [_StubResult("a", {"v": 1.0}), _StubResult("b", {"v": 1.0})]
        summary = report.summarize(flat, ["v"])
        failures = report.evaluate_checks({"v": {"min_spread_pct": 5.0}}, flat, summary)
        self.assertEqual(failures[0]["kind"], "min_spread_pct")

    def test_min_spread_does_not_apply_to_a_singleton_grid(self):
        """A single-point debugging run (e.g. --corners typical --temps 27
        --supply-tol 0) has zero spread by construction -- indistinguishable
        from a broken sweep by value alone, so min_spread_pct is not
        enforced rather than spuriously failing every quick/debug run."""
        one = [_StubResult("a", {"v": 1.0})]
        summary = report.summarize(one, ["v"])
        failures = report.evaluate_checks({"v": {"min_spread_pct": 5.0}}, one, summary)
        self.assertEqual(failures, [])

    def test_passing_checks_produce_no_failures(self):
        self.assertEqual(
            report.evaluate_checks(
                {"v": {"min": 0.5, "max": 1.5, "max_spread_pct": 50.0}},
                self.results,
                self.summary,
            ),
            [],
        )


class RecordIdTests(unittest.TestCase):
    def test_record_id_matches_the_ratified_shape(self):
        """sim/README.md: <record-id> is <YYYYMMDD>-<HHMMSS>-<short-git-sha>."""
        when = datetime.datetime(2026, 7, 29, 15, 30, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(report.format_record_id("1a7ef75", when), "20260729-153000-1a7ef75")
        self.assertRegex(
            report.format_record_id("1a7ef75", when), r"^\d{8}-\d{6}-[0-9a-f]{7}$"
        )

    def test_allocation_never_reuses_an_existing_record_id(self):
        when = datetime.datetime(2026, 7, 29, 15, 30, 0, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp)
            first = report.allocate_record_id(SIM_DIR, records, when)
            (records / f"{first}.md").write_text("# first\n")
            second = report.allocate_record_id(SIM_DIR, records, when)
            self.assertNotEqual(first, second)
            self.assertRegex(second, r"^\d{8}-\d{6}-")
            # the existing record was not touched
            self.assertEqual((records / f"{first}.md").read_text(), "# first\n")

    def test_write_record_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            experiment = Path(tmp) / "an-experiment"
            (experiment / report.RECORDS_DIR).mkdir(parents=True)
            (experiment / report.RECORDS_DIR / "20260729-153000-abc1234.md").write_text("keep\n")
            with self.assertRaises(report.RecordExists):
                report.write_record(
                    {"record_id": "20260729-153000-abc1234"}, experiment
                )


class MatrixConformanceTests(unittest.TestCase):
    """sim/README.md requires the full mandated matrix, or a stated reason."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tb_dir = Path(self.tmp.name) / "an-experiment" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps({"name": "x", "netlist": "x.spice", "measure": {"vout": "v(out)"}})
        )
        self.tb = testbench.load(tb_dir)

    def _grid(self, corner_names, temps, supplies):
        return corners.build_grid(corners.resolve_corners(corner_names), temps, supplies)

    def test_full_matrix_is_recognised(self):
        grid = self._grid(["mos"], (-40, 27, 125), corners.supply_points(3.3, 0.10))
        self.assertEqual(report.matrix_conformance(self.tb, grid), {"full": True, "missing": []})

    def test_missing_temperature_is_flagged(self):
        grid = self._grid(["mos"], (27,), corners.supply_points(3.3, 0.10))
        result = report.matrix_conformance(self.tb, grid)
        self.assertFalse(result["full"])
        self.assertTrue(any("temperature" in m for m in result["missing"]))

    def test_missing_supply_and_process_are_flagged(self):
        grid = self._grid(["typical"], (-40, 27, 125), [3.3])
        result = report.matrix_conformance(self.tb, grid)
        self.assertFalse(result["full"])
        self.assertTrue(any("supply" in m for m in result["missing"]))
        self.assertTrue(any("process" in m for m in result["missing"]))

    def test_passive_only_corners_do_not_satisfy_the_process_axis(self):
        """MOS bundles are required; passive-only bundles don't substitute."""
        grid = self._grid(["passives"], (-40, 27, 125), corners.supply_points(3.3, 0.10))
        result = report.matrix_conformance(self.tb, grid)
        self.assertFalse(result["full"])
        self.assertTrue(any("process" in m for m in result["missing"]))


class RecordRenderingTests(unittest.TestCase):
    """The rendered record carries exactly the fields sim/README.md lists."""

    RATIFIED_FIELDS = (
        "Record ID",
        "Claim",
        "Netlist provenance",
        "Environment provenance",
        "Corner matrix run",
        "Methodology / criteria / limitations",
        "Statistical convention",
        "Result",
        "Links",
        "Timestamp / author",
        "Supersedes",
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        tb_dir = root / "harness-selftest" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps(
                {
                    "name": "harness-selftest",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "methodology": ["op-point read of an ideal source, for plumbing only."],
                    "checks": {"vout": {"min": 0.0, "max": 10.0}},
                }
            )
        )
        self.tb = testbench.load(tb_dir)
        self.pdk = fake_pdk(root / "gf180mcuD")
        self.points = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), corners.supply_points(3.3, 0.10)
        )
        self.results = [
            runner.PointResult(point=p, status="ok", measurements={"vout": 1.0 + i * 0.01})
            for i, p in enumerate(self.points)
        ]
        self.record = report.build_record(
            tb=self.tb,
            pdk=self.pdk,
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260729-153000-1a7ef75",
            started_utc="2026-07-29T15:30:00+00:00",
            wall_seconds=9.5,
            claim="spec/pll.md#example",
        )

    def test_every_ratified_field_is_present_and_in_order(self):
        text = report.render_record(self.record, "harness-selftest")
        positions = []
        for field in self.RATIFIED_FIELDS:
            marker = f"**{field}**"
            self.assertIn(marker, text, f"missing ratified field {field!r}")
            positions.append(text.index(marker))
        self.assertEqual(positions, sorted(positions), "fields are out of ratified order")

    def test_links_point_at_the_ratified_paths(self):
        text = report.render_record(self.record, "harness-selftest")
        self.assertIn("sim/harness-selftest/testbench/x.spice", text)
        self.assertIn("sim/harness-selftest/netlist-snapshots/20260729-153000-1a7ef75.spice", text)
        self.assertIn("sim/harness-selftest/corners/20260729-153000-1a7ef75/", text)

    def test_links_cite_a_second_testbench_dir_not_the_default_name(self):
        """An experiment may carry more than one deck (devchar-passives does).

        A record must cite the directory ITS OWN manifest came from, or the
        capacitor record and the resistor record of the same experiment would
        both claim to have come from ``testbench/``.
        """
        root = Path(self.tmp.name)
        alt = root / "harness-selftest" / "testbench-alt"
        alt.mkdir(parents=True)
        (alt / "y.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (alt / "tb.json").write_text(
            json.dumps({"name": "alt", "netlist": "y.spice", "measure": {"vout": "v(out)"}})
        )
        tb = testbench.load(alt)
        record = report.build_record(
            tb=tb,
            pdk=self.pdk,
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260729-153000-1a7ef75",
            started_utc="2026-07-29T15:30:00+00:00",
            wall_seconds=9.5,
        )
        text = report.render_record(record, "harness-selftest")
        self.assertIn("sim/harness-selftest/testbench-alt/y.spice", text)
        self.assertIn("sim/harness-selftest/testbench-alt/tb.json", text)
        self.assertNotIn("sim/harness-selftest/testbench/y.spice", text)

    def test_rendering_tolerates_a_record_written_before_the_directory_key(self):
        """Records are append-only; the oldest ones carry no testbench dir."""
        legacy = dict(self.record)
        legacy["testbench"] = {
            k: v for k, v in self.record["testbench"].items() if k != "directory"
        }
        text = report.render_record(legacy, "harness-selftest")
        self.assertIn("sim/harness-selftest/testbench/x.spice", text)

    def test_result_table_uses_corner_ids_and_reports_overall_verdict(self):
        text = report.render_record(self.record, "harness-selftest")
        self.assertIn("`typical_-40c_2.97v`", text)
        self.assertIn("`ff_125c_3.63v`", text)
        self.assertIn("**Overall: PASS**", text)

    def test_a_full_matrix_run_says_so(self):
        text = report.render_record(self.record, "harness-selftest")
        self.assertIn("Full PVT matrix per CLAUDE.md", text)

    def test_methodology_bullets_are_rendered(self):
        text = report.render_record(self.record, "harness-selftest")
        self.assertIn("op-point read of an ideal source, for plumbing only.", text)

    def test_environment_section_names_the_real_pdk_provenance(self):
        text = report.render_record(self.record, "harness-selftest")
        provenance = self.pdk.provenance()
        self.assertIn(str(provenance["open_pdks_version"]), text)
        self.assertIn(provenance["variant"], text)
        self.assertNotIn("open_pdks `None`", text)

    def test_git_state_is_taken_from_the_caller_not_resampled(self):
        """The harness dirties the tree by writing logs; provenance is pre-run."""
        pre_run = {"commit": "f" * 40, "short": "fffffff", "branch": "main", "dirty": False}
        env = report.environment(self.pdk, "ngspice-46", SIM_DIR, pre_run)
        self.assertEqual(env["git"], pre_run)

    def test_a_dirty_tree_is_called_out_in_netlist_provenance(self):
        dirty = dict(self.record)
        dirty["environment"] = dict(self.record["environment"])
        dirty["environment"]["git"] = {
            "commit": "f" * 40, "short": "fffffff", "branch": "main", "dirty": True,
        }
        text = report.render_record(dirty, "harness-selftest")
        self.assertIn("dirty working tree", text)

    def test_a_single_topology_record_renders_one_flat_table(self):
        """No topology_groups -> exactly the table this harness always wrote."""
        self.assertEqual(self.record["topology_groups"], [])
        text = report.render_record(self.record, "harness-selftest")
        self.assertIn("| corner-id | vout | pass/fail |", text)
        self.assertIn("| measurement | min | max | mean | spread % | limits |", text)
        self.assertNotIn("| topology |", text)

    def test_rendering_tolerates_a_record_written_before_topology_groups(self):
        """Records are append-only; older ones have no topology_groups key."""
        legacy = dict(self.record)
        legacy.pop("topology_groups")
        self.assertEqual(
            report.render_record(legacy, "harness-selftest"),
            report.render_record(self.record, "harness-selftest"),
        )

    def test_netlist_snapshot_is_frozen_and_append_only(self):
        experiment = self.tb.experiment_dir
        path = report.write_netlist_snapshot(self.tb, experiment, "20260729-153000-1a7ef75")
        self.assertEqual(path.parent.name, report.SNAPSHOT_DIR)
        self.assertIn("v1 out 0 dc {vdd_val}", path.read_text())
        self.assertIn(self.tb.netlist_sha256, path.read_text())
        with self.assertRaises(report.RecordExists):
            report.write_netlist_snapshot(self.tb, experiment, "20260729-153000-1a7ef75")


class MultiTopologyRenderingTests(unittest.TestCase):
    """A deck with several sub-circuits renders one sub-table per topology.

    Mirrors the shape sim/devchar-delay needs: unstarved ring metrics, an
    inverter-chain delay, and a bare-device drive current that the manifest
    deliberately leaves ungrouped.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        tb_dir = root / "devchar-example" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps(
                {
                    "name": "devchar-example",
                    "netlist": "x.spice",
                    "measure": {
                        "r1_fosc": "v(a)",
                        "r1_tstage": "v(b)",
                        "ch_tpd": "v(c)",
                        "dc_idn": "v(d)",
                    },
                    "topology_groups": {
                        "ring1x": {
                            "description": "unstarved 5-stage ring, 1x sizing",
                            "measures": ["r1_fosc", "r1_tstage"],
                        },
                        "chain": ["ch_tpd"],
                    },
                    "checks": {"ch_tpd": {"max": 1.0e-9}},
                }
            )
        )
        self.tb = testbench.load(tb_dir)
        self.pdk = fake_pdk(root / "gf180mcuD")
        self.points = corners.build_grid(
            corners.resolve_corners(["mos"]), (-40, 27, 125), corners.supply_points(3.3, 0.10)
        )
        self.results = [
            runner.PointResult(
                point=p,
                status="ok",
                measurements={
                    "r1_fosc": 1.0e9 + i * 1.0e6,
                    "r1_tstage": 1.0e-11,
                    "ch_tpd": 2.0e-9,  # violates the max check, in 'chain' only
                    "dc_idn": 1.0e-3,
                },
            )
            for i, p in enumerate(self.points)
        ]
        self.record = report.build_record(
            tb=self.tb,
            pdk=self.pdk,
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260729-153000-1a7ef75",
            started_utc="2026-07-29T15:30:00+00:00",
            wall_seconds=9.5,
        )
        self.text = report.render_record(self.record, "devchar-example")

    def _block(self, topology: str) -> str:
        """The rendered lines belonging to one topology's sub-table."""
        captions = [f"  **{g['name']}**" for g in self.record["topology_groups"]]
        marker = f"  **{topology}**"
        start = self.text.index(marker)
        ends = [self.text.index(c) for c in captions if self.text.index(c) > start]
        return self.text[start : min(ends)] if ends else self.text[start:]

    def test_the_record_carries_the_grouping_with_an_ungrouped_fallback(self):
        self.assertEqual(
            [g["name"] for g in self.record["topology_groups"]],
            ["ring1x", "chain", testbench.UNGROUPED_TOPOLOGY],
        )

    def test_one_sub_table_per_topology_instead_of_one_flat_table(self):
        self.assertIn("| corner-id | r1_fosc | r1_tstage | pass/fail |", self.text)
        self.assertIn("| corner-id | ch_tpd | pass/fail |", self.text)
        self.assertIn("| corner-id | dc_idn | pass/fail |", self.text)
        self.assertNotIn(
            "| corner-id | r1_fosc | r1_tstage | ch_tpd | dc_idn | pass/fail |", self.text
        )

    def test_group_captions_carry_the_description_when_given(self):
        self.assertIn("**ring1x** — unstarved 5-stage ring, 1x sizing", self.text)
        self.assertIn("**chain**\n", self.text)  # no description declared

    def test_an_ungrouped_measurement_still_gets_a_table(self):
        self.assertIn(f"**{testbench.UNGROUPED_TOPOLOGY}**", self.text)
        self.assertIn("dc_idn", self._block(testbench.UNGROUPED_TOPOLOGY))

    def test_a_failure_appears_only_in_its_own_topology_table(self):
        chain = self._block("chain")
        ring = self._block("ring1x")
        self.assertIn("FAIL — ch_tpd max=", chain)
        self.assertNotIn("FAIL", ring)
        self.assertIn("| PASS |", ring)
        self.assertIn("**Overall: FAIL**", self.text)

    def test_every_point_appears_in_every_sub_table(self):
        for topology in ("ring1x", "chain", testbench.UNGROUPED_TOPOLOGY):
            block = self._block(topology)
            for point in self.points:
                self.assertIn(f"`{point.corner_id}`", block, topology)

    def test_the_spread_table_names_each_measurement_s_topology(self):
        self.assertIn(
            "| topology | measurement | min | max | mean | spread % | limits |", self.text
        )
        self.assertIn("| `ring1x` | `r1_fosc` |", self.text)
        self.assertIn("| `chain` | `ch_tpd` |", self.text)
        self.assertIn(f"| `{testbench.UNGROUPED_TOPOLOGY}` | `dc_idn` |", self.text)

    def test_grid_level_failures_are_reported_once_for_the_whole_record(self):
        summary = report.summarize(self.results, self.tb.measure_names)
        failures = report.evaluate_checks(
            {"r1_fosc": {"max_spread_pct": 0.1}}, self.results, summary
        )
        self.assertEqual([f["at"] for f in failures], ["grid"])
        record = dict(self.record)
        record["checks"] = dict(self.record["checks"])
        record["checks"]["failures"] = failures
        record["checks"]["spec"] = {"r1_fosc": {"max_spread_pct": 0.1}}
        record["status"] = "fail"
        text = report.render_record(record, "devchar-example")
        self.assertEqual(text.count("Grid-level check failures:"), 1)

    def test_every_ratified_field_survives_the_grouped_layout(self):
        for field in RecordRenderingTests.RATIFIED_FIELDS:
            self.assertIn(f"**{field}**", self.text, f"missing ratified field {field!r}")


if __name__ == "__main__":
    unittest.main()
