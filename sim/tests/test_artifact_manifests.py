#!/usr/bin/env python3
"""Tests for sim/lib/check_artifact_manifests.py and sim/lib/artifact-put.sh (issue #830).

    python3 -m unittest discover -s sim/tests -v

Each checker test builds a throwaway git repo with one manifest and runs the
real script in it. The writer tests run the real script with the broker unset
or `klt` shadowed, and assert it fails closed with no manifest written.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "sim/lib/check_artifact_manifests.py"
PUT = REPO_ROOT / "sim/lib/artifact-put.sh"

PAYLOAD = b"raw ngspice output\n" * 10
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def entry(**over):
    e = {
        "sha256": DIGEST,
        "size": len(PAYLOAD),
        "kind": "evidence",
        "producer": {"tool": "klt", "version": "0", "loom.repo": "o/n", "commit": None},
        "uri": f"artifact:evidence/o__n/{DIGEST}",
        "name": "run/out.raw",
    }
    e.update(over)
    return e


class CheckerTest(unittest.TestCase):
    def run_check(self, manifest=None, committed=None):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            if manifest is not None:
                d = root / "manifests/artifacts"
                d.mkdir(parents=True)
                (d / "b-1.manifest.json").write_text(json.dumps(manifest))
            for name, data in (committed or {}).items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            return subprocess.run(
                ["python3", "-I", str(CHECK), "--repo-root", str(root)],
                capture_output=True, text=True,
            )

    def test_passing_manifest(self):
        r = self.run_check({"schema_version": 1, "entries": [entry()]}, {"README.md": b"hi"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_manifests_is_clean(self):
        self.assertEqual(self.run_check().returncode, 0)

    def test_non_artifact_uri(self):
        for uri in ("s3://bucket/key", "file:///tmp/x", "https://h/x"):
            with self.subTest(uri=uri):
                r = self.run_check({"schema_version": 1, "entries": [entry(uri=uri)]})
                self.assertEqual(r.returncode, 1)
                self.assertIn("artifact:", r.stderr)

    def test_bad_schema(self):
        for bad in ({"entries": []}, {"schema_version": 2, "entries": []},
                    {"schema_version": 1, "entries": [entry(size=0)]},
                    {"schema_version": 1, "entries": [entry(sha256="XYZ")]},
                    {"schema_version": 1, "entries": [entry(bucket="b")]}):
            with self.subTest(bad=bad):
                self.assertEqual(self.run_check(bad).returncode, 1)

    def test_committed_bytes_matching_stored_object(self):
        r = self.run_check(
            {"schema_version": 1, "entries": [entry()]}, {"sim/x/out.raw": PAYLOAD}
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("committed bytes equal a stored object", r.stderr)


class WriterFailClosedTest(unittest.TestCase):
    def run_put(self, env_over, path_prefix=None):
        env = {k: v for k, v in os.environ.items() if k != "KLT_ARTIFACT_BROKER"}
        env.update(env_over)
        if path_prefix:
            env["PATH"] = f"{path_prefix}:{env['PATH']}"
        with tempfile.NamedTemporaryFile() as f:
            f.write(PAYLOAD); f.flush()
            return subprocess.run(
                ["bash", str(PUT), "tbtest", "fail-closed-probe", f.name],
                capture_output=True, text=True, env=env,
            )

    def manifest(self):
        return REPO_ROOT / "manifests/artifacts/tbtest-fail-closed-probe.manifest.json"

    def tearDown(self):
        self.manifest().unlink(missing_ok=True)

    def test_broker_unset(self):
        r = self.run_put({})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertFalse(self.manifest().exists())

    def test_klt_without_artifact_put(self):
        with tempfile.TemporaryDirectory() as td:
            klt = Path(td) / "klt"
            klt.write_text("#!/bin/sh\nexit 2\n")
            klt.chmod(0o755)
            r = self.run_put({"KLT_ARTIFACT_BROKER": "http://127.0.0.1:9"}, td)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertFalse(self.manifest().exists())

    def test_broker_unreachable(self):
        with tempfile.TemporaryDirectory() as td:
            klt = Path(td) / "klt"
            klt.write_text('#!/bin/sh\n[ "$3" = "--help" ] && exit 0\nexit 7\n')
            klt.chmod(0o755)
            r = self.run_put({"KLT_ARTIFACT_BROKER": "http://127.0.0.1:9"}, td)
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertFalse(self.manifest().exists())


if __name__ == "__main__":
    unittest.main()
