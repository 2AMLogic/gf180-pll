#!/usr/bin/env python3
"""Shared test fixtures for ``sim/tests/``.

Not itself a ``test_*.py`` module, so ``unittest discover`` never collects it
directly -- it exists purely to be imported by the ``test_*.py`` files that
need ``ManifestFixture``, ``fake_pdk``, ``TreeWriter`` or ``TreeTestCase``.

Two unrelated families live here, one per kind of test in this directory:

* ``ManifestFixture`` / ``fake_pdk`` -- for the tests that exercise the Python
  harness directly against a manifest and a stand-in PDK.
* ``TreeWriter`` / ``TreeTestCase`` -- for the tests that build a throwaway
  miniature repository and run a real ``sim/lib/check-*.sh`` inside it.
  Both are defined once in ``lib/testtree.py`` and re-exported here (#871).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

sys.path.insert(0, str(SIM_DIR.parent / "lib"))

from harness.pdk import Pdk, pinned_open_pdks  # noqa: E402
from testtree import TreeTestCase, TreeWriter, install_checklib  # noqa: E402,F401  (re-exported)


def fake_pdk(root: Path) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text(f"open_pdks {pinned_open_pdks()}\n")
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
