#!/usr/bin/env python3
"""Unit tests for ``raw_measures.write_raw_measures_csv`` (issue #110).

No PDK and no ngspice required: every fixture builds ``PointResult``/
``PvtPoint`` objects directly, the same pattern
``sim/tests/test_manifest_extensions.py`` uses for the derived-tables writer.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import corners, raw_measures, report, runner, testbench  # noqa: E402


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


class BasicWriterTests(ManifestFixture):
    """The common case: a bench with no ``derived.tables`` entry at all."""

    def setUp(self):
        super().setUp()
        self.tb = testbench.load(self.write({}))
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (27.0,), corners.supply_points(3.3, 0.10)
        )
        self.assertEqual(len(self.points), 3)  # one corner x one temp x 3 supplies
        self.results = [
            runner.PointResult(point=p, status="ok", measurements={"vout": 1.0 + i * 0.01})
            for i, p in enumerate(self.points)
        ]
        self.out_dir = self.root / "corners" / "20260101-000000-abcdef0"

    def test_a_bench_with_zero_derived_tables_still_gets_the_csv(self):
        """This is the exact gap the issue exists to close."""
        self.assertIsNone(self.tb.derived)
        path = raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        self.assertEqual(path, self.out_dir / "raw_measures.csv")
        self.assertTrue(path.is_file())

    def test_one_row_per_corner_point_with_expected_columns(self):
        path = raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header, body = rows[0], rows[1:]
        self.assertEqual(header, ["corner", "temp_c", "vdd", "corner_id", "vout", "verdict"])
        self.assertEqual(len(body), len(self.points))
        by_id = {r[3]: r for r in body}
        self.assertIn("typical_27c_2.97v", by_id)
        self.assertIn("typical_27c_3.63v", by_id)
        row = by_id["typical_27c_2.97v"]
        self.assertEqual(row[0], "typical")
        self.assertEqual(row[1], "27.0")
        self.assertEqual(row[2], "2.97")
        self.assertEqual(row[5], "PASS")

    def test_existing_derived_tables_csv_and_markdown_table_are_unaffected(self):
        """This adds an artifact -- it does not touch the other two."""
        record = report.build_record(
            tb=self.tb,
            pdk=_stub_pdk(),
            points=self.points,
            results=self.results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260101-000000-abcdef0",
            started_utc="2026-01-01T00:00:00+00:00",
            wall_seconds=1.0,
        )
        text = report.render_record(record, self.slug)
        self.assertIn("| corner-id | vout | pass/fail |", text)
        raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        text_after = report.render_record(record, self.slug)
        self.assertEqual(text, text_after)


class AppendOnlyTests(ManifestFixture):
    def setUp(self):
        super().setUp()
        self.tb = testbench.load(self.write({}))
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (27.0,), (3.3,)
        )
        self.results = [
            runner.PointResult(point=p, status="ok", measurements={"vout": 1.0}) for p in self.points
        ]
        self.out_dir = self.root / "corners" / "20260101-000000-abcdef0"

    def test_re_running_against_an_existing_file_raises_rather_than_overwrites(self):
        raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        original = (self.out_dir / "raw_measures.csv").read_text()
        with self.assertRaises(raw_measures.RawMeasuresError):
            raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        self.assertEqual((self.out_dir / "raw_measures.csv").read_text(), original)


class FailedAndErrorPointTests(ManifestFixture):
    def setUp(self):
        super().setUp()
        self.tb = testbench.load(
            self.write({"checks": {"vout": {"min": 0.0, "max": 2.0}}})
        )
        self.points = corners.build_grid(
            corners.resolve_corners(["typical"]), (27.0,), (3.3,) * 1
        )
        self.point = self.points[0]

    def test_a_failed_point_still_gets_a_row_with_an_error_verdict(self):
        results = [
            runner.PointResult(
                point=self.point,
                status="failed",
                measurements={},
                missing=["vout"],
                message="no measurements parsed",
            )
        ]
        out_dir = self.root / "corners" / "failed"
        path = raw_measures.write_raw_measures_csv(self.tb, results, out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(len(rows), 2, "the failed point must not be silently dropped")
        header, row = rows[0], rows[1]
        self.assertEqual(row[header.index("vout")], "")
        self.assertTrue(row[header.index("verdict")].startswith("ERROR"))
        self.assertIn("no measurements parsed", row[header.index("verdict")])

    def test_an_error_point_with_a_comma_bearing_message_round_trips_quoted(self):
        results = [
            runner.PointResult(
                point=self.point,
                status="error",
                measurements={},
                message="convergence failed, giving up",
            )
        ]
        out_dir = self.root / "corners" / "error"
        path = raw_measures.write_raw_measures_csv(self.tb, results, out_dir)
        raw_text = path.read_text()
        # A bare comma-splitting join would corrupt the row's column count.
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header = rows[0]
        self.assertEqual({len(r) for r in rows}, {len(header)})
        verdict = rows[1][header.index("verdict")]
        self.assertEqual(verdict, "ERROR — convergence failed, giving up")
        self.assertIn('"', raw_text)  # the comma-bearing cell was quoted

    def test_a_passing_check_still_reports_pass_for_an_ok_point(self):
        results = [
            runner.PointResult(point=self.point, status="ok", measurements={"vout": 1.0})
        ]
        out_dir = self.root / "corners" / "ok"
        path = raw_measures.write_raw_measures_csv(self.tb, results, out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header, row = rows[0], rows[1]
        self.assertEqual(row[header.index("verdict")], "PASS")

    def test_a_check_violation_produces_a_fail_verdict_matching_the_markdown_table(self):
        results = [
            runner.PointResult(point=self.point, status="ok", measurements={"vout": 5.0})
        ]
        record = report.build_record(
            tb=self.tb,
            pdk=_stub_pdk(),
            points=self.points[:1],
            results=results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260101-000000-abcdef0",
            started_utc="2026-01-01T00:00:00+00:00",
            wall_seconds=1.0,
        )
        text = report.render_record(record, self.slug)
        out_dir = self.root / "corners" / "fail"
        path = raw_measures.write_raw_measures_csv(self.tb, results, out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header, row = rows[0], rows[1]
        verdict = row[header.index("verdict")]
        self.assertTrue(verdict.startswith("FAIL"))
        self.assertIn(verdict, text)


class OptionalAndExtraAxisTests(ManifestFixture):
    slug = "divider-ratio"

    def setUp(self):
        super().setUp()
        self.tb = testbench.load(
            self.write(
                {
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
                    "sweeps": {
                        "rate": {
                            "description": "input rate",
                            "points": {
                                "f200": {"params": {"kf": "200e6"}},
                                "f010": {"params": {"kf": "10e6"}},
                            },
                        }
                    },
                }
            )
        )
        self.points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]),
            (27.0,),
            (3.3,),
            axes=self.tb.sweeps,
        )
        self.assertEqual(len(self.points), 2)  # one PVT point x 2 rate points
        self.results = [
            runner.PointResult(
                point=p,
                status="ok",
                measurements={"n_fb": 64.0},
                not_measured=["tc_asrt"],
            )
            for p in self.points
        ]
        self.out_dir = self.root / "corners" / "20260101-000000-abcdef0"

    def test_extra_sweep_axis_gets_its_own_column(self):
        path = raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header = rows[0]
        self.assertIn("rate", header)
        by_id = {r[header.index("corner_id")]: r for r in rows[1:]}
        self.assertEqual(by_id["typical_27c_3.30v_f200"][header.index("rate")], "f200")
        self.assertEqual(by_id["typical_27c_3.30v_f010"][header.index("rate")], "f010")

    def test_not_measured_optional_renders_as_an_explicit_label_not_blank(self):
        path = raw_measures.write_raw_measures_csv(self.tb, self.results, self.out_dir)
        with path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        header, row = rows[0], rows[1]
        cell = row[header.index("tc_asrt")]
        self.assertEqual(cell, raw_measures.NOT_MEASURED_LABEL)
        self.assertNotEqual(cell, "")


def _stub_pdk():
    from harness.pdk import Pdk

    return Pdk(path=Path("/nonexistent"), variant="gf180mcuD", source="test")


if __name__ == "__main__":
    unittest.main()
