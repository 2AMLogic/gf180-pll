#!/usr/bin/env python3
"""Tests for ``layout/lib/gen_layout_status_table.py`` (issue #812, stage 2).

Each test builds a throwaway tree (the generator plus a miniature evidence
directory) and runs the real script in it. No PDK, no KLayout.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _fixtures import install_checklib

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "layout" / "lib" / "gen_layout_status_table.py"
CHECKER = REPO / "layout" / "lib" / "check-layout-status-claims.sh"

BLOCKS = [
    ("VCO", "vco-layout", "vco_block.gds", "vco_block"),
    ("PFD + charge pump", "pfd-cp-layout", "pfd_cp.gds", "pfd_cp"),
    ("divider chain", "divider-chain-layout", "divider_chain.gds", "divider_chain"),
    ("lock detector", "lock-detector-layout", "lock_detector.gds", "lock_detector"),
]
MARKERS = "<!-- layout-status-table:begin -->\n<!-- layout-status-table:end -->\n"


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "layout" / "lib").mkdir(parents=True)
        (self.root / "layout" / "harness").mkdir()
        shutil.copy(GEN, self.root / "layout" / "lib" / GEN.name)
        # The generator imports its evidence extractors from lib/checklib,
        # resolved relative to its own location -- so the throwaway tree needs
        # the package beside the copied script, exactly as a clone has it.
        install_checklib(self.root)
        array = "".join('  "%s|%s|%s|%s"\n' % b for b in BLOCKS)
        (self.root / "layout" / "lib" / CHECKER.name).write_text("BLOCKS=(\n" + array + ")\n")
        (self.root / "layout" / "harness" / "env.py").write_text(
            'KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 9.9.9"\n'
        )
        (self.root / "layout" / "STATUS.md").write_text("# Status\n\n" + MARKERS)
        audit = self.root / "layout" / "evidence" / "area-audit"
        audit.mkdir(parents=True)
        rows = "".join(
            "| `%s` | 10.00 x 20.00 | 200 | 100 | 50.0 %% | 100 (50.0 %%) |\n" % b[3]
            for b in BLOCKS
        )
        (audit / "area-audit.md").write_text(
            "| Block | Footprint (um) | bbox (um2) | Drawn | Fill | WS |\n|---|---|---|---|---|---|\n" + rows
        )
        for _label, d, gds, _top in BLOCKS:
            self.block(d, gds)

    def tearDown(self):
        self._tmp.cleanup()

    def block(self, d, gds, *, lvs_match=True):
        ev = self.root / "layout" / "evidence" / d
        (ev / "drc-clean").mkdir(parents=True, exist_ok=True)
        (ev / "lvs-clean").mkdir(exist_ok=True)
        (ev / gds).write_bytes(b"")
        (ev / "drc-clean" / "drc.log").write_text("ok\n")
        (ev / "lvs-clean" / "lvs.log").write_text(
            "Congratulations! Netlists match.\n" if lvs_match else "mismatch\n"
        )

    def run_gen(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(self.root / "layout" / "lib" / GEN.name), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def status(self):
        return (self.root / "layout" / "STATUS.md").read_text()

    def test_generate_then_check_is_clean(self):
        self.assertEqual(self.run_gen().returncode, 0)
        text = self.status()
        self.assertIn("**4 of 4** sub-blocks. LVS-matched: **4 of 4**", text)
        self.assertIn("| VCO | `vco_block` | yes | yes | 10.00 × 20.00 | 0.0002 |", text)
        self.assertIn("`KLayout 9.9.9`", text)
        self.assertIn("pll_top` GDS committed under `layout/evidence/`: **no**", text)
        self.assertEqual(self.run_gen("--check").returncode, 0)

    def test_stale_count_in_the_table_fails_check(self):
        # The #237 failure mode, now on the table: evidence moves, the
        # committed copy does not.
        self.run_gen()
        (self.root / "layout" / "evidence" / "lock-detector-layout" / "lvs-clean" / "lvs.log").write_text("mismatch\n")
        result = self.run_gen("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is stale", result.stderr)
        self.assertIn("LVS-matched: **3 of 4**", result.stdout)

    def test_hand_edited_table_fails_check(self):
        self.run_gen()
        (self.root / "layout" / "STATUS.md").write_text(
            self.status().replace("**4 of 4**", "**2 of 4**")
        )
        self.assertEqual(self.run_gen("--check").returncode, 1)

    def test_assembled_top_flips_the_sentinel(self):
        self.run_gen()
        top = self.root / "layout" / "evidence" / "pll-top-layout"
        top.mkdir()
        (top / "pll_top.gds").write_bytes(b"")
        self.assertEqual(self.run_gen("--check").returncode, 1)
        self.run_gen()
        self.assertIn("pll_top` GDS committed under `layout/evidence/`: **yes**", self.status())

    def test_gds_without_drc_log_is_not_drawn(self):
        (self.root / "layout" / "evidence" / "vco-layout" / "drc-clean" / "drc.log").unlink()
        self.run_gen()
        self.assertIn("**3 of 4** sub-blocks", self.status())

    def test_missing_markers_fail(self):
        (self.root / "layout" / "STATUS.md").write_text("# Status\n")
        self.assertNotEqual(self.run_gen().returncode, 0)


class RealTreeTests(unittest.TestCase):
    def test_committed_table_matches_the_real_evidence_tree(self):
        result = subprocess.run(
            [sys.executable, "-I", str(GEN), "--root", str(REPO), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
