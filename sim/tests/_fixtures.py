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
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness.pdk import Pdk  # noqa: E402


def fake_pdk(root: Path) -> Pdk:
    (root / "libs.tech" / "ngspice").mkdir(parents=True, exist_ok=True)
    (root / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    (root / "libs.tech" / "ngspice" / "design.ngspice").write_text("* fake\n")
    (root / "SOURCES").write_text("open_pdks deadbeef\n")
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


class TreeWriter:
    """``write(rel, text)`` for a throwaway repo tree rooted at ``self.root``.

    Mixed into the per-file ``_Tree`` helpers that build a miniature repository
    and run a real ``sim/lib/check-*.sh`` in it. Only this generic
    relative-path writer is shared: each ``_Tree`` keeps its own ``__init__``
    (which script it installs, which documents must pre-exist so the check
    fails on what the test is about rather than on an absence) and its own
    campaign/deck/record conveniences layered on top of ``write``.
    """

    #: Set by the concrete ``_Tree.__init__``.
    root: Path

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class TreeTestCase(unittest.TestCase):
    """Gives every test its own freshly-built ``self.tree``.

    A subclass names its module-level ``_Tree`` in ``tree_cls``; ``setUp``
    builds one under a per-test ``tempfile.TemporaryDirectory`` whose cleanup
    is registered for teardown. A subclass needing a baseline tree (decks,
    records, documents) overrides ``setUp``, calls ``super().setUp()`` first,
    then populates ``self.tree``.
    """

    #: The ``_Tree`` class ``self.tree`` is instantiated from.
    tree_cls: type

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = self.tree_cls(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)
