#!/usr/bin/env python3
"""Unit tests for the harness's ``--artifact-store`` step (issue #832).

The writer is stubbed by a fake script, so no broker, klt or ngspice is needed.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import contextlib
import io
import shutil
import stat
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness import artifacts, cli  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="artifact-store-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        stage = self.root / "stage"
        patcher = unittest.mock.patch.object(artifacts, "STAGE_DIR", stage)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = self.root / "calls.txt"
        self.log_dir = self.root / "corners" / "rid"
        self.log_dir.mkdir(parents=True)
        self.files = []
        for name in ("a.log", "raw_measures.csv"):
            f = self.log_dir / name
            f.write_text(name)
            self.files.append(f)

    def fake_writer(self, exit_code: int, stderr: str = "") -> Path:
        script = self.root / "put.sh"
        script.write_text(
            f'#!/usr/bin/env bash\necho "$@" >> "{self.calls}"\n'
            f'echo "{stderr}" >&2\nexit {exit_code}\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def run_store(self, script, files=None):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = artifacts.store("bench", "rid", self.files if files is None else files, script)
        return rc, err.getvalue()

    def test_success_calls_writer_once_and_removes_stored_files(self):
        rc, _ = self.run_store(self.fake_writer(0))
        self.assertEqual(rc, 0)
        lines = self.calls.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("bench rid "))
        self.assertIn("a.log", lines[0])
        self.assertIn("raw_measures.csv", lines[0])
        self.assertEqual(list(self.log_dir.iterdir()), [])

    def test_nonzero_writer_exit_propagates_and_keeps_files(self):
        rc, err = self.run_store(self.fake_writer(3, "broker unset"))
        self.assertEqual(rc, 3)
        self.assertIn("broker unset", err)
        self.assertTrue(all(f.exists() for f in self.files))

    def test_no_raw_output_fails_closed(self):
        rc, _ = self.run_store(self.fake_writer(0), files=[])
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.calls.exists())


class ParserTests(unittest.TestCase):
    def test_flag_is_opt_in(self):
        parser = cli.build_parser()
        self.assertFalse(parser.parse_args(["tb"]).artifact_store)
        self.assertTrue(parser.parse_args(["tb", "--artifact-store"]).artifact_store)


if __name__ == "__main__":
    import unittest.mock  # noqa: F401
    unittest.main()
