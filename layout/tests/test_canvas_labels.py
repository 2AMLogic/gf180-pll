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


class _NoLabelSuffixCanvas(_canvas.Canvas):
    """A ``LAYER`` table with no ``"*_label"``-suffixed key at all -- the
    defensive fallback case (issue #453): no submodule's table looks like
    this today, but the default must not silently clear nothing for one that
    somehow does, so it falls back to the pre-#453 ``(PIN_LAYER,)`` default
    instead."""

    LAYER = {
        "metal1": (34, 0),
        "metal1pin": (34, 10),
    }
    PIN_LAYER = "metal1pin"


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
        self.assertEqual(removed, 3)
        self.assertEqual(_texts(canvas, "metal1_label"), [])

    def test_default_also_clears_every_other_label_purpose_the_canvas_defines(self):
        # issue #453 -- the narrow issue-#440 default (PIN_LAYER only, here
        # "metal1_label") missed a purpose-layer label on any *other*
        # "*_label" entry in the canvas's own LAYER table, e.g. a
        # Metal2-bus pin labelled on "metal2_label" (36/10) the way
        # pfd_cp/block.py's own UP/DN pins are. A future assembler composing
        # such a block by the same read-GDS-and-flatten pattern and calling
        # the bare clear_inherited_labels() must not inherit that text.
        canvas = self._canvas_with_pins()
        removed = canvas.clear_inherited_labels()
        self.assertEqual(removed, 3)
        self.assertEqual(_texts(canvas, "metal1_label"), [])
        self.assertEqual(_texts(canvas, "metal2_label"), [])

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

    def test_clears_a_metal2_label_pin_inherited_by_flattening_a_read_sub_cell(self):
        # issue #453's concrete scenario: a sub-block's boundary pin is
        # Metal2 geometry (pfd_cp's own UP/DN), labelled with an explicit
        # ``layer="metal2_label"`` override -- correct for that sub-block's
        # own standalone LVS claim. A parent composing it by the same
        # read-GDS-and-flatten pattern must not inherit that 36/10 text: the
        # bare, no-argument ``clear_inherited_labels()`` call has to reach it
        # too, not only the narrow "metal1_label"-only default issue #440
        # left in place.
        import tempfile

        import klayout.db as db

        sub = _ToyCanvas("sub")
        sub.rect("metal2", 0.0, 2.0, 1.0, 3.0)
        sub.pin("UP", 0.0, 2.0, 1.0, 3.0, layer="metal2_label")

        parent = _ToyCanvas("parent")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub.gds"
            sub.write_gds(path)
            parent.layout.read(str(path))
        index = parent.layout.cell_by_name("sub")
        parent.top.insert(db.CellInstArray(index, db.Trans(db.Vector(0, 0))))
        parent.top.flatten(-1, True)

        self.assertEqual(_texts(parent, "metal2_label"), ["UP"])
        self.assertEqual(parent.clear_inherited_labels(), 1)
        self.assertEqual(_texts(parent, "metal2_label"), [])
        # The parent then names its own boundary net, and that survives.
        parent.pin("VOUT_MIRROR", 0.0, 2.0, 1.0, 3.0, layer="metal2_label")
        self.assertEqual(_texts(parent, "metal2_label"), ["VOUT_MIRROR"])

    def test_default_falls_back_to_pin_layer_when_layer_table_has_no_label_suffix(self):
        canvas = _NoLabelSuffixCanvas("toy")
        canvas.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        canvas.pin("EN", 0.0, 0.0, 1.0, 1.0)
        index = canvas.layout.layer(*canvas.LAYER["metal1pin"])
        self.assertEqual(
            sorted(s.text.string for s in canvas.top.shapes(index).each() if s.is_text()),
            ["EN"],
        )
        removed = canvas.clear_inherited_labels()
        self.assertEqual(removed, 1)
        self.assertEqual(
            [s.text.string for s in canvas.top.shapes(index).each() if s.is_text()], []
        )


if __name__ == "__main__":
    unittest.main()
