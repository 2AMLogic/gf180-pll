#!/usr/bin/env python3
"""A rendered evidence record carries no host-specific path (issue #844).

    python3 -m unittest discover -s sim/tests -v

``layout/lib/check-evidence-host-paths.sh`` rejects host-absolute paths in
committed evidence. The record writer used to interpolate the PDK's absolute
path (and the ``search_root:~/.volare`` discovery note) into the PDK line; the
host/python/klt facts now come from ``klt env-provenance emit`` instead. klt is
stubbed here, so these tests need no installed klt, PDK or ngspice.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _fixtures import fake_pdk, pinned_open_pdks  # noqa: E402
from harness import corners, report, runner, testbench  # noqa: E402

SIM_DIR = Path(__file__).resolve().parents[1]

KLT_LINES = [
    "host: host-0123abcd (Linux x86_64, release 6.0)",
    "python: 3.13.1",
    "klt: 0.8.0 (klayout 0.30.0)",
]


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(["klt"], returncode, stdout, stderr)


class RecordHostPaths(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        tb_dir = root / "harness-selftest" / "testbench"
        tb_dir.mkdir(parents=True)
        (tb_dir / "x.spice").write_text("v1 out 0 dc {vdd_val}\n")
        (tb_dir / "tb.json").write_text(
            json.dumps(
                {
                    "name": "harness-selftest",
                    "netlist": "x.spice",
                    "measure": {"vout": "v(out)"},
                    "methodology": ["plumbing only."],
                    "checks": {"vout": {"min": 0.0, "max": 10.0}},
                }
            )
        )
        self.pdk_path = root / "some-home" / "gf180mcuD"
        self.pdk = fake_pdk(self.pdk_path)
        points = corners.build_grid(
            corners.resolve_corners(["mos"]), (27,), corners.supply_points(3.3, 0.10)
        )
        results = [
            runner.PointResult(point=p, status="ok", measurements={"vout": 1.0})
            for p in points
        ]
        self.record = report.build_record(
            tb=testbench.load(tb_dir),
            pdk=self.pdk,
            points=points,
            results=results,
            ngspice="ngspice-46",
            repo_root=SIM_DIR,
            record_id="20260729-153000-1a7ef75",
            started_utc="2026-07-29T15:30:00+00:00",
            wall_seconds=1.0,
            env_provenance_lines=KLT_LINES,
        )

    def test_record_text_has_no_host_path_and_keeps_pdk_revision(self):
        text = report.render_record(self.record, "harness-selftest")
        for leak in ("/home/", "/Users/", ".loom/worktrees", str(self.pdk_path),
                     "found via", "search_root"):
            self.assertNotIn(leak, text)
        self.assertIn(pinned_open_pdks(), text)

    def test_environment_block_uses_klt_lines(self):
        text = report.render_record(self.record, "harness-selftest")
        for line in KLT_LINES:
            self.assertIn(f"  - {line}", text)

    def test_klt_lines_come_from_the_subprocess(self):
        with mock.patch.object(
            report.subprocess, "run", return_value=_completed("\n".join(KLT_LINES) + "\n")
        ) as run:
            self.assertEqual(report.klt_env_provenance_lines(), KLT_LINES)
        self.assertEqual(run.call_args.args[0][:3], ["klt", "env-provenance", "emit"])

    def test_missing_klt_is_an_error_not_a_fallback(self):
        with mock.patch.object(report.subprocess, "run", side_effect=FileNotFoundError("klt")):
            with self.assertRaises(report.EnvProvenanceError):
                report.klt_env_provenance_lines()

    def test_failing_or_empty_klt_is_an_error(self):
        for bad in (_completed(returncode=2, stderr="boom"), _completed(stdout="")):
            with mock.patch.object(report.subprocess, "run", return_value=bad):
                with self.assertRaises(report.EnvProvenanceError):
                    report.klt_env_provenance_lines()


if __name__ == "__main__":
    unittest.main()
