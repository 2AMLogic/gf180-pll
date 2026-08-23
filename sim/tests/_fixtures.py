#!/usr/bin/env python3
"""Shared test fixtures for ``sim/tests/``.

Not itself a ``test_*.py`` module, so ``unittest discover`` never collects it
directly -- it exists purely to be imported by the ``test_*.py`` files that
need ``ManifestFixture``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


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
