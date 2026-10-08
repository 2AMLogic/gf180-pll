#!/usr/bin/env python3
"""Manifest ``checks`` validation at load time (issue #735).

Headless: no PDK, no ngspice, no backend.

    python3 -m unittest sim/tests/test_manifest_checks_validation.py -v
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from _fixtures import ManifestFixture  # noqa: E402
from harness import cli, corners, report, runner, testbench  # noqa: E402

MEASURE = {"delay": "v(out)", "vout": "v(out)"}


class RejectionTests(ManifestFixture):
    def load(self, checks, **extra):
        return testbench.load(self.write({"measure": MEASURE, "checks": checks, **extra}))

    def assertRejected(self, checks, *fragments, **extra):
        with self.assertRaises(ValueError) as ctx:
            self.load(checks, **extra)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def test_unknown_measurement_names_manifest_and_measurement(self):
        self.assertRejected({"dealy": {"max": 1}}, "tb.json", "'dealy'")

    def test_unknown_limit_key_names_manifest_measurement_and_key(self):
        self.assertRejected({"delay": {"maximum": 1}}, "tb.json", "'delay'", "'maximum'")

    def test_malformed_shapes(self):
        self.assertRejected([], "'checks' must be an object")
        self.assertRejected({"delay": 1}, "must be an object of limits")
        self.assertRejected({"delay": None}, "must be an object of limits")

    def test_empty_and_null_only_entries(self):
        self.assertRejected({"delay": {}}, "enforces nothing")
        self.assertRejected({"delay": {"max": None}}, "enforces nothing")

    def test_non_numeric_and_non_finite_thresholds(self):
        self.assertRejected({"delay": {"max": "1"}}, "finite number")
        self.assertRejected({"delay": {"max": True}}, "finite number")
        self.assertRejected({"delay": {"max_spread_pct": [1]}}, "finite number")
        # json.loads accepts these non-standard tokens.
        self.write({"measure": MEASURE})
        (self.tb_dir / "tb.json").write_text(
            '{"name": "x", "netlist": "x.spice", "measure": {"delay": "v(out)"},'
            ' "checks": {"delay": {"max": NaN}}}'
        )
        with self.assertRaisesRegex(ValueError, "finite number"):
            testbench.load(self.tb_dir)
        (self.tb_dir / "tb.json").write_text(
            '{"name": "x", "netlist": "x.spice", "measure": {"delay": "v(out)"},'
            ' "checks": {"delay": {"min": -Infinity}}}'
        )
        with self.assertRaisesRegex(ValueError, "finite number"):
            testbench.load(self.tb_dir)

    def test_coverage_limits_must_be_non_negative_integers(self):
        for bad in (True, 1.5, -1, "0", 1.0):
            with self.subTest(bad=bad):
                self.assertRejected(
                    {"delay": {"max_measured_points": bad}}, "non-negative integer"
                )

    def test_contradictory_bounds(self):
        self.assertRejected({"delay": {"min": 2, "max": 1}}, "contradictory")
        self.assertRejected(
            {"delay": {"min_measured_points": 3, "max_measured_points": 1}}, "contradictory"
        )
        self.assertRejected(
            {"delay": {"min_spread_pct": 5, "max_spread_pct": 1}}, "contradictory"
        )

    def test_derived_and_phased_names_are_known_but_misspellings_are_not(self):
        mod = self.write_module("def derive_point(*a, **k):\n    return {}\n")
        derived = {"module": mod, "measures": ["gain"]}
        tb = self.load({"gain": {"min": 0}}, derived=derived)
        self.assertIn("gain", tb.checks)
        self.assertRejected({"gian": {"min": 0}}, "'gian'", derived=derived)


class AcceptanceTests(ManifestFixture):
    def test_valid_checks_of_every_kind_load_unchanged(self):
        checks = {
            "delay": {"min": -1.5, "max": 3, "min_spread_pct": 0, "max_spread_pct": 2.5},
            "vout": {"min_measured_points": 0, "max_measured_points": 0, "max": None},
        }
        tb = testbench.load(
            self.write({"measure": MEASURE, "checks": checks})
        )
        self.assertEqual(tb.checks, checks)

    def test_no_checks_is_fine(self):
        self.assertEqual(testbench.load(self.write({})).checks, {})

    def test_optional_measurement_check_is_accepted(self):
        tb = testbench.load(
            self.write(
                {
                    "measure": {"vout": "v(out)", "flag": {"expr": "v(out)", "optional": True}},
                    "checks": {"flag": {"max_measured_points": 0, "max_spread_pct": 1}},
                }
            )
        )
        self.assertIn("flag", tb.checks)


class EvaluationStillFailsTests(ManifestFixture):
    def test_delay_2_against_max_1_is_a_violation_not_a_load_error(self):
        tb = testbench.load(
            self.write({"measure": MEASURE, "checks": {"delay": {"max": 1}}})
        )
        points = corners.build_grid(
            corners.resolve_corners(["typical"]), (27.0,), corners.supply_points(3.3, 0.0)
        )
        results = [
            runner.PointResult(point=p, status="ok", measurements={"delay": 2.0, "vout": 1.0})
            for p in points
        ]
        summary = report.summarize(results, ["delay", "vout"])
        failures = report.evaluate_checks(tb.checks, results, summary)
        self.assertEqual([f["kind"] for f in failures], ["max"])


class NoSideEffectTests(ManifestFixture):
    def test_cli_run_fails_before_any_reservation_or_backend(self):
        path = self.write({"measure": MEASURE, "checks": {"dealy": {"max": 1}}})
        with mock.patch.object(report, "reserve_record_id") as reserve, mock.patch.object(
            runner, "run_grid"
        ) as run_grid, mock.patch.object(cli, "find_pdk") as pdk, redirect_stderr(
            io.StringIO()
        ) as err:
            code = cli.main([str(path)])
        self.assertEqual(code, cli.EXIT_ENVIRONMENT)
        self.assertIn("dealy", err.getvalue())
        reserve.assert_not_called()
        run_grid.assert_not_called()
        pdk.assert_not_called()
        self.assertEqual(list(self.root.glob("**/corners")), [])


if __name__ == "__main__":
    unittest.main()
