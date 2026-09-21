#!/usr/bin/env python3
"""Tests for ``layout/pll_top/_canvas.Canvas.clear_inherited_labels()``
(issue #440) -- the shared "the assembling level owns the net names" tool.

WHY THIS IS A SEPARATE, GENERIC TEST FILE
------------------------------------------
The bug this method exists to prevent is not a ``pfd_cp`` bug, it is a
property of the composition pattern *every* block in this package uses: a
sub-block written for its own standalone LVS claim labels its own boundary
nets with its own local port names, and ``read()`` + ``top.flatten(-1,
True)`` carries those label shapes into the parent, where they name the
wrong net. gf180mcu's LVS deck reads top-level net names straight off them.

The severity is easy to under-rate, so it is worth stating here too: a net
that inherits a second name extracts under a *merged* name (``ENB,VSS``),
and the deck's synthesized global substrate net -- named by ``--lvs_sub``
-- only merges into the drawn net whose name matches it **exactly**. So one
stray label on the ground rail silently disconnects every n-channel bulk
terminal in the block from ground. ``pfd_cp``'s own first block-level LVS
run failed exactly and only this way (see
``layout/evidence/pfd-cp-layout/PROOF.md``).

These tests use a throwaway ``Canvas`` subclass with a two-entry layer
table, so they exercise the method itself rather than any one block's
geometry, and need no PDK.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

try:
    import klayout.db  # noqa: F401

    _HAVE_KLAYOUT = True
except ImportError:
    _HAVE_KLAYOUT = False

import _canvas  # noqa: E402


class _ToyCanvas(_canvas.Canvas):
    """Two drawing layers and two label purposes -- the smallest table that
    can express "labels on one purpose, geometry on another"."""

    LAYER = {
        "metal1": (34, 0),
        "metal1_label": (34, 10),
        "metal2": (36, 0),
        "metal2_label": (36, 10),
    }
    PIN_LAYER = "metal1_label"


def _texts(canvas, layer: str) -> list[str]:
    index = canvas.layout.layer(*canvas.LAYER[layer])
    return sorted(
        shape.text.string for shape in canvas.top.shapes(index).each() if shape.is_text()
    )


def _boxes(canvas, layer: str) -> int:
    index = canvas.layout.layer(*canvas.LAYER[layer])
    return sum(1 for shape in canvas.top.shapes(index).each() if not shape.is_text())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not available")
class ClearInheritedLabelsTests(unittest.TestCase):
    def _canvas_with_pins(self) -> "_ToyCanvas":
        canvas = _ToyCanvas("toy")
        canvas.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        canvas.rect("metal2", 0.0, 2.0, 1.0, 3.0)
        canvas.pin("EN", 0.0, 0.0, 1.0, 1.0)
        canvas.pin("ENB", 0.0, 0.0, 1.0, 1.0)
        canvas.pin("UP", 0.0, 2.0, 1.0, 3.0, layer="metal2_label")
        return canvas

    def test_removes_every_text_on_the_default_pin_layer(self):
        canvas = self._canvas_with_pins()
        self.assertEqual(_texts(canvas, "metal1_label"), ["EN", "ENB"])
        removed = canvas.clear_inherited_labels()
        self.assertEqual(removed, 2)
        self.assertEqual(_texts(canvas, "metal1_label"), [])

    def test_leaves_other_label_purposes_alone_by_default(self):
        canvas = self._canvas_with_pins()
        canvas.clear_inherited_labels()
        self.assertEqual(_texts(canvas, "metal2_label"), ["UP"])

    def test_clears_named_layers_when_asked(self):
        canvas = self._canvas_with_pins()
        removed = canvas.clear_inherited_labels(("metal1_label", "metal2_label"))
        self.assertEqual(removed, 3)
        self.assertEqual(_texts(canvas, "metal1_label"), [])
        self.assertEqual(_texts(canvas, "metal2_label"), [])

    def test_never_touches_geometry(self):
        canvas = self._canvas_with_pins()
        canvas.clear_inherited_labels(("metal1_label", "metal2_label"))
        self.assertEqual(_boxes(canvas, "metal1"), 1)
        self.assertEqual(_boxes(canvas, "metal2"), 1)

    def test_is_idempotent(self):
        canvas = self._canvas_with_pins()
        canvas.clear_inherited_labels()
        self.assertEqual(canvas.clear_inherited_labels(), 0)

    def test_unknown_layer_name_is_a_no_op_not_a_crash(self):
        # A subclass whose LAYER table has no such purpose (devgen's did not
        # have "metal2_label" before issue #440) must not blow up an
        # assembler that asks for it defensively.
        canvas = self._canvas_with_pins()
        self.assertEqual(canvas.clear_inherited_labels(("metal3_label",)), 0)
        self.assertEqual(_texts(canvas, "metal1_label"), ["EN", "ENB"])

    def test_clears_labels_that_arrived_by_flattening_a_read_sub_cell(self):
        # The real path: a sub-block's own GDS is read in and flattened, so
        # its label shapes land in the parent's own top cell. Build the
        # sub-block in one canvas, write it, read it back into another.
        import tempfile

        import klayout.db as db

        sub = _ToyCanvas("sub")
        sub.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        sub.pin("ENB", 0.0, 0.0, 1.0, 1.0)

        parent = _ToyCanvas("parent")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub.gds"
            sub.write_gds(path)
            parent.layout.read(str(path))
        index = parent.layout.cell_by_name("sub")
        parent.top.insert(db.CellInstArray(index, db.Trans(db.Vector(0, 0))))
        parent.top.flatten(-1, True)

        self.assertEqual(_texts(parent, "metal1_label"), ["ENB"])
        self.assertEqual(parent.clear_inherited_labels(), 1)
        self.assertEqual(_texts(parent, "metal1_label"), [])
        # The parent then names the net itself, and that name survives.
        parent.pin("VSS", 0.0, 0.0, 1.0, 1.0)
        self.assertEqual(_texts(parent, "metal1_label"), ["VSS"])


if __name__ == "__main__":
    unittest.main()
