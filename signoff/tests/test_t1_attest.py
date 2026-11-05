#!/usr/bin/env python3
"""Negative controls for ``signoff/t1_attest.py`` (issue #798).

    python3 -m unittest discover -s signoff/tests -t signoff/tests -v

The klt grader re-hashes only the inventory a T1 citation pins, so an edit to
an inventoried file (a schematic, a testbench, a ``LICENSE``) is invisible to
``run-signoff.sh --check`` on its own.  ``t1_attest.py --check`` is what makes
that edit fail CI.  A check that is only ever run on a tree where it passes
proves nothing, so each test below copies the files the script reads out of the
real repository into a throwaway tree, damages one, and runs the real script.
No klt, PDK or simulator is needed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = "signoff/t1_attest.py"

#: Globs (relative to the repo root) the script reads.  Records are copied one
#: file per experiment: the script only needs one to exist.
COPY = [
    "design/*.sch", "design/*.sym", "design/xschemrc", "design/netlist.sh",
    "design/gen_delaywin.py", "design/netlist/*.spice",
    "sim/*/testbench*/*", "sim/CHARACTERIZATION.md", "sim/README.md", "sim/pdk.json",
    "sim/run_corners.py", "sim/selftest.sh", "sim/run-all.sh",
    "README.md", "CONTRIBUTING.md", "LICENSE", "spec/pll.md",
    ".github/workflows/ci.yml", "signoff/t1_attest.py", "signoff/block-manifest.json",
    "signoff/attest/*",
]


def build_tree(dst: Path) -> None:
    for pattern in COPY:
        for src in REPO.glob(pattern):
            if src.is_file():
                out = dst / src.relative_to(REPO)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)
    for rec in REPO.glob("sim/*/records"):
        first = next(iter(sorted(rec.glob("*.md"))), None)
        if first is not None:
            out = dst / first.relative_to(REPO)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(first, out)


def run(tree: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(tree / SCRIPT), *args],
                          capture_output=True, text=True, check=False)


class T1AttestNegativeControls(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = Path(self._tmp.name)
        build_tree(self.tree)

    def test_pristine_tree_is_current(self):
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_edited_schematic_makes_check_fail_until_regenerated(self):
        with (self.tree / "design/vco.sch").open("a") as f:
            f.write("* edited\n")
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("design-sources-analog.json", r.stderr)
        self.assertNotIn("design-sources-digital.json", r.stderr)
        self.assertEqual(run(self.tree).returncode, 0)
        self.assertEqual(run(self.tree, "--check").returncode, 0)

    def test_edited_testbench_names_the_partition_inventory(self):
        tb = next((self.tree / "sim/lock-detector/testbench").glob("tb_*.sp"))
        tb.write_text(tb.read_text() + "* edited\n")
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("testbench-inventory-digital.json", r.stderr)

    def test_edited_license_makes_check_fail(self):
        with (self.tree / "LICENSE").open("a") as f:
            f.write("\n")
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("repo-hygiene.json", r.stderr)

    def test_unassigned_schematic_is_refused(self):
        (self.tree / "design/new_block.sch").write_text("v {}\n")
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("new_block", r.stderr)

    def test_ci_dropping_the_netlist_drift_check_is_refused(self):
        ci = self.tree / ".github/workflows/ci.yml"
        ci.write_text(ci.read_text().replace("run: ./design/netlist.sh --check", "run: true"))
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("netlist.sh --check", r.stderr)

    def test_unpinned_manifest_is_reported_stale(self):
        (self.tree / "signoff/block-manifest.json").write_text(
            '{"block": "gf180-pll", "kind": "mixed-signal", "evidence": {}}\n')
        r = run(self.tree, "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("block-manifest.json", r.stderr)


if __name__ == "__main__":
    unittest.main()
