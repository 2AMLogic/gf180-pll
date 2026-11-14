#!/usr/bin/env python3
"""Focused regression coverage for the shared drawing helpers in
``pll_top/_canvas.py`` that issue #776 consolidated: ``h_wire()``,
``snap_um()``, ``via1_stack()`` and ``tap_strip()`` -- plus
``Canvas.place_cell()``, consolidated the same way by issue #940.

Before #776 each of these existed as two-to-four per-module copies
(``vco``/``lock_detector``/``pfd_cp``/``loop_filter``) whose DRC constants
were baked in. The shared bodies take those constants as explicit keyword
arguments, and each submodule binds its own via ``functools.partial`` (the
#353/#690 pattern). The consolidation is geometry-preserving -- the full
block builds diff empty against the pre-#776 generators -- but that
property is only as good as its testbench, so this file pins, per helper:

* the shared body's exact drawn rectangles, layer names and bounds, for at
  least two different block-specific configurations each;
* the bindings' preserved public contracts (VCO pins the tap's *comp* box,
  lock detector pins the *pad* and tags the Metal1 through
  ``canvas.net()``, PFD/CP returns the comp box, loop filter returns the
  Metal1 pad);
* the edge cases the former copies already handled: reversed
  ``h_wire()`` endpoints, off-grid ``via1_stack()`` centres, single-row vs
  full-grid tap contacts, and horizontal vs vertical tap bands.

A ``test_canvas_labels.py``-style two-layer toy canvas cannot express comp/
implant/contact/metal1 stacks, so these tests draw on the real submodule
``Canvas`` classes. They need only the ``klayout`` pip wheel -- no PDK, no
PV environment (``_canvas`` imports ``klayout.db`` lazily and the
generators are pure Python).

``place_cell()``'s cases follow the same rule for the same reason: they use
``pfd_cp/devgen.Canvas`` (a real cell-placing subclass, ``GRID_UM`` unset)
and a local subclass of it with the snap turned on, rather than an abstract
toy -- the grid-vs-no-grid distinction is the whole point of the method, and
it is a property of which real subclass you hold.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import unittest

from _env import HAVE_KLAYOUT, LAYOUT_DIR  # noqa: F401

from pll_top import _canvas  # noqa: E402
from pll_top.lock_detector import checks as lock_checks  # noqa: E402
from pll_top.lock_detector import primitives as lock_prim  # noqa: E402
from pll_top.loop_filter import devices as lf_dev  # noqa: E402
from pll_top.loop_filter import primitives as lf_prim  # noqa: E402
from pll_top.pfd_cp import devgen as pfd_devgen  # noqa: E402
from pll_top.pfd_cp import rowgen  # noqa: E402
from pll_top.vco import devices as vco_dev  # noqa: E402
from pll_top.vco import primitives as vco_prim  # noqa: E402


def _layer_boxes(canvas, layer: str) -> list[tuple[float, float, float, float]]:
    """Every non-text shape on ``layer``, as sorted ``(x0, y0, x1, y1)`` um boxes."""
    index = canvas.layout.layer(*canvas.LAYER[layer])
    per_um = round(1.0 / canvas.dbu)
    return sorted(
        (
            shape.box.left / per_um,
            shape.box.bottom / per_um,
            shape.box.right / per_um,
            shape.box.top / per_um,
        )
        for shape in canvas.top.shapes(index).each()
        if not shape.is_text()
    )


def _single_box(canvas, layer: str) -> tuple[float, float, float, float]:
    """The one shape on ``layer`` -- fails when there are none or several."""
    boxes = _layer_boxes(canvas, layer)
    assert len(boxes) == 1, f"expected exactly one {layer} box, got {boxes}"
    return boxes[0]


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not available")
class HWireTests(unittest.TestCase):
    """``_canvas.h_wire()`` and the two width bindings built on it."""

    def test_draws_a_centered_metal1_wire_and_returns_its_normalized_box(self):
        canvas = vco_prim.Canvas("h_wire_probe")
        box = vco_prim.h_wire(canvas, 1.0, 5.0, 2.0)  # binding default: 0.28 um
        self.assertEqual(_layer_boxes(canvas, "metal1"), [(1.0, 1.86, 5.0, 2.14)])
        # The return is the raw wire box (not dbu-rounded) -- exactly what
        # the pre-#776 per-module copies handed back.
        self.assertEqual(box, (1.0, 2.0 - 0.28 / 2.0, 5.0, 2.0 + 0.28 / 2.0))

    def test_reversed_endpoints_draw_the_same_wire_and_return_the_same_box(self):
        forward = vco_prim.Canvas("h_wire_fwd")
        backward = vco_prim.Canvas("h_wire_rev")
        box_forward = vco_prim.h_wire(forward, 1.0, 5.0, 2.0)
        box_backward = vco_prim.h_wire(backward, 5.0, 1.0, 2.0)
        self.assertEqual(
            _layer_boxes(forward, "metal1"),
            _layer_boxes(backward, "metal1"),
            "Canvas.rect normalizes endpoints, so drawing order must not matter",
        )
        self.assertEqual(box_backward, box_forward)

    def test_each_family_binds_its_own_wire_width(self):
        lock = lock_prim.Canvas("h_wire_lock")
        lock_prim.h_wire(lock, 0.0, 2.0, 1.0)  # lock detector default: 0.32 um
        self.assertEqual(_layer_boxes(lock, "metal1"), [(0.0, 0.84, 2.0, 1.16)])

    def test_positional_and_keyword_width_both_work_on_every_binding(self):
        # Pre-#776 contract: ``h_wire(canvas, x0, x1, y, width)`` -- the fifth
        # positional argument must keep working, not only ``width=``.
        for mod in (vco_prim, lock_prim):
            positional = mod.h_wire(mod.Canvas("hw_pos"), 0.0, 2.0, 1.0, 0.4)
            keyword = mod.h_wire(mod.Canvas("hw_kw"), 0.0, 2.0, 1.0, width=0.4)
            self.assertEqual(positional, (0.0, 0.8, 2.0, 1.2))
            self.assertEqual(keyword, positional)

    def test_pfd_h_wire_keeps_view_name_width_forms_and_returns_none(self):
        # PFD's original returned None and named its first parameter ``view``.
        positional = rowgen.Canvas("hw")
        keyword = rowgen.Canvas("hw")
        self.assertIsNone(rowgen.h_wire(positional, 0.0, 2.0, 1.0, 0.4))
        self.assertIsNone(rowgen.h_wire(view=keyword, x0=0.0, x1=2.0, y=1.0, width=0.4))
        self.assertIsNone(rowgen.h_wire(rowgen.Canvas("hw"), 0.0, 2.0, 1.0))  # default width


class SnapUmTests(unittest.TestCase):
    """``_canvas.snap_um()``: pure rounding, no canvas needed."""

    def test_rounds_to_the_nearest_grid_point(self):
        self.assertEqual(_canvas.snap_um(0.1234567, grid_um=0.005), 0.125)
        self.assertEqual(_canvas.snap_um(0.1225, grid_um=0.005), 0.12)
        self.assertEqual(_canvas.snap_um(-0.1234567, grid_um=0.005), -0.125)
        self.assertEqual(_canvas.snap_um(1.2, grid_um=0.005), 1.2)

    def test_both_device_bindings_share_the_manufacturing_grid(self):
        # The two former per-module copies were byte-identical over the same
        # 0.005 um grid; after #776 both are partials of the shared one, and
        # this pins that neither binding drifted.
        for v in (0.1234567, 2.7775, -0.0049):
            self.assertEqual(vco_dev.snap_um(v), lf_dev.snap_um(v))
            self.assertAlmostEqual(vco_dev.snap_um(v) / 0.005, round(vco_dev.snap_um(v) / 0.005))


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not available")
class Via1StackTests(unittest.TestCase):
    """``_canvas.via1_stack()``: one via + Metal1/Metal2 landing squares."""

    def test_vco_binding_draws_the_0p26_via_and_0p44_pads(self):
        canvas = vco_prim.Canvas("via1_stack_probe")
        pad = vco_prim.via1_stack(canvas, 2.0, 3.0)
        self.assertEqual(_single_box(canvas, "via1"), (1.87, 2.87, 2.13, 3.13))
        self.assertEqual(_single_box(canvas, "metal1"), (1.78, 2.78, 2.22, 3.22))
        self.assertEqual(_single_box(canvas, "metal2"), (1.78, 2.78, 2.22, 3.22))
        self.assertEqual(pad, (1.78, 2.78, 2.22, 3.22))

    def test_loop_filter_binding_draws_the_same_via_with_its_own_pad(self):
        canvas = lf_prim.Canvas("via1_stack_lf_probe")
        pad = lf_prim.via1_stack(canvas, 2.0, 3.0)
        self.assertEqual(_single_box(canvas, "via1"), (1.87, 2.87, 2.13, 3.13))
        self.assertEqual(_single_box(canvas, "metal1"), (1.77, 2.77, 2.23, 3.23))  # METAL_PAD_UM = 0.46
        self.assertEqual(_single_box(canvas, "metal2"), (1.77, 2.77, 2.23, 3.23))
        self.assertEqual(pad, (1.77, 2.77, 2.23, 3.23))

    def test_off_grid_centre_is_snapped_before_drawing(self):
        canvas = vco_prim.Canvas("via1_stack_snap_probe")
        pad = vco_prim.via1_stack(canvas, 2.0004, 3.0)  # 2.0004 is off the 5 nm grid
        self.assertEqual(_single_box(canvas, "via1"), (1.87, 2.87, 2.13, 3.13))
        self.assertEqual(pad, (1.78, 2.78, 2.22, 3.22))


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not available")
class TapStripTests(unittest.TestCase):
    """``_canvas.tap_strip()`` plus the four per-module contract adapters."""

    def test_vco_binding_draws_a_full_contact_grid_and_pins_the_comp_box(self):
        canvas = vco_prim.Canvas("tap_strip_vco_probe")
        comp = (2.0, 1.0, 4.6, 1.6)
        result = vco_prim.tap_strip(canvas, "n", 2.0, 1.0, 4.6, 1.6, "VDD_VCO")
        self.assertIsNone(result, "the VCO contract pins the tap but returns nothing")
        self.assertEqual(_single_box(canvas, "comp"), comp)
        self.assertEqual(_single_box(canvas, "nplus"), (1.7, 0.7, 4.9, 1.9))
        # 5 contacts along x (pitch 0.5 from 2.19: usable span 2.1..4.5,
        # total row 2.22, centred), one row along y (the band is one contact
        # tall after its margins): hand-computed expectation, not a re-run
        # of the placer.
        expected_contacts = [(x, 1.19, x + 0.22, 1.41) for x in (2.19, 2.69, 3.19, 3.69, 4.19)]
        self.assertEqual(_layer_boxes(canvas, "contact"), expected_contacts)
        # Drawn Metal1 pad = comp grown by METAL1_PAD_MARGIN_UM (dbu-snapped).
        self.assertEqual(_single_box(canvas, "metal1"), (1.88, 0.88, 4.72, 1.72))
        # The VCO contract: the pin is labelled over the *comp*, not the pad.
        self.assertEqual(canvas.pins["VDD_VCO"], [comp])

    def test_vco_binding_p_kind_switches_the_implant_layer(self):
        canvas = vco_prim.Canvas("tap_strip_vco_p_probe")
        vco_prim.tap_strip(canvas, "p", 0.0, 0.0, 0.6, 0.6, "GND_VCO")
        self.assertEqual(_layer_boxes(canvas, "pplus"), [(-0.3, -0.3, 0.9, 0.9)])
        self.assertEqual(_layer_boxes(canvas, "nplus"), [])

    def test_lock_detector_binding_draws_a_single_row_and_pins_the_pad(self):
        canvas = lock_prim.Canvas("tap_strip_lock_probe")
        comp, pad = lock_prim.tap_strip(canvas, "p", 3.0, 2.0, "VSS")
        self.assertEqual(comp, (3.0, 1.75, 3.6, 2.25))
        self.assertEqual(pad, (2.88, 1.63, 3.72, 2.37))
        self.assertEqual(_single_box(canvas, "comp"), comp)
        self.assertEqual(_single_box(canvas, "pplus"), (2.7, 1.45, 3.9, 2.55))
        # Single centred contact row: one contact, hung from the strip's
        # centreline (cy = 2.0 - 0.11), not a 2-D grid.
        self.assertEqual(_layer_boxes(canvas, "contact"), [(3.19, 1.89, 3.41, 2.11)])
        self.assertEqual(_single_box(canvas, "metal1"), pad)
        # The lock-detector contract: pin over the *pad*, Metal1 tagged with
        # the net through ``canvas.net()``.
        self.assertEqual(canvas.pins["VSS"], [pad])

    def test_lock_detector_metal1_is_tagged_with_its_net_for_the_connectivity_checks(self):
        canvas = lock_checks.RecordingCanvas("tap_strip_lock_recording")
        comp, pad = lock_prim.tap_strip(canvas, "n", 3.0, 2.0, "VDD")
        self.assertEqual(
            [(net, layer, x0, y0, x1, y1) for net, layer, x0, y0, x1, y1 in canvas.conductors],
            [("VDD", "metal1", *pad)],
            "RecordingCanvas must see the tap's Metal1 inside the net context -- "
            "comp/implant/contacts are not conductors it records",
        )
        self.assertEqual(canvas.pins["VDD"], [pad])

    def test_pfd_binding_is_centred_returns_the_comp_box_and_pins_nothing(self):
        view = rowgen.Canvas("tap_strip_pfd_probe")
        comp = rowgen.tap_strip(view, "n", 2.0, 1.0)
        self.assertEqual(comp, (1.7, 0.75, 2.3, 1.25))
        self.assertEqual(
            [s for s in view.shapes if s[0] == "comp"],
            [("comp", 1.7, 0.75, 2.3, 1.25)],
        )
        self.assertEqual([s for s in view.shapes if s[0] == "nplus"], [("nplus", 1.4, 0.45, 2.6, 1.55)])
        self.assertEqual([s for s in view.shapes if s[0] == "contact"], [("contact", 1.89, 0.89, 2.11, 1.11)])
        self.assertEqual([s for s in view.shapes if s[0] == "metal1"], [("metal1", 1.58, 0.63, 2.42, 1.37)])
        self.assertEqual(view.labels, [], "the PFD/CP tap merges into the row rail; it declares no pin")

    def test_loop_filter_binding_draws_a_full_grid_on_both_band_shapes(self):
        # Horizontal band (wide in x) ...
        canvas = lf_prim.Canvas("tap_strip_lf_probe")
        m1 = lf_prim.tap_strip(canvas, 1.0, 1.0, 3.4, 2.2)
        self.assertEqual(m1, (1.0 - 0.12, 1.0 - 0.12, 3.4 + 0.12, 2.2 + 0.12))  # TAP_M1_MARGIN_UM = 0.12
        self.assertEqual(_single_box(canvas, "pplus"), (0.7, 0.7, 3.7, 2.5))
        expected_contacts = [
            (x, y, x + 0.22, y + 0.22) for x in (1.34, 1.84, 2.34, 2.84) for y in (1.24, 1.74)
        ]
        self.assertEqual(_layer_boxes(canvas, "contact"), expected_contacts)
        self.assertEqual(canvas.pins, {}, "loop-filter bands are wired by their caller, no pin")

        # ... and a vertical one (tall in y): the grid must fill both axes.
        tall = lf_prim.Canvas("tap_strip_lf_tall_probe")
        lf_prim.tap_strip(tall, 1.0, 1.0, 2.2, 3.4)
        expected_tall = [
            (x, y, x + 0.22, y + 0.22) for x in (1.24, 1.74) for y in (1.34, 1.84, 2.34, 2.84)
        ]
        self.assertEqual(_layer_boxes(tall, "contact"), expected_tall)

    def test_loop_filter_band_is_always_p_substrate(self):
        canvas = lf_prim.Canvas("tap_strip_lf_p_probe")
        lf_prim.tap_strip(canvas, 0.0, 0.0, 0.6, 0.6)
        self.assertEqual(_layer_boxes(canvas, "nplus"), [])
        self.assertEqual(_layer_boxes(canvas, "pplus"), [(-0.3, -0.3, 0.9, 0.9)])


class _SnappedPfdCpCanvas(pfd_devgen.Canvas):
    """``pfd_cp``'s own Canvas, but with a manufacturing-grid snap.

    Not hypothetical scaffolding: ``vco/primitives.py`` and
    ``loop_filter/primitives.py`` already set ``GRID_UM`` this way, and the
    two Canvas subclasses that place cells (``pfd_cp/devgen``,
    ``divider_chain/devgen``) are the ones that do not. This subclass is
    exactly the state ``pfd_cp`` would be in if it adopted the snap the way
    those two already have -- the case issue #940's five hand-rolled
    conversions would have silently kept opting out of.
    """

    GRID_UM = 0.005  # the PDK's 5 nm manufacturing grid, as devices.LAYOUT_GRID_UM


def _instances(canvas) -> list[tuple[int, int]]:
    """Every cell instance's placement offset in the top cell, in dbu."""
    return sorted((inst.trans.disp.x, inst.trans.disp.y) for inst in canvas.top.each_inst())


def _probe_cell(canvas, name: str = "place_cell_probe_sub") -> int:
    """A throwaway one-box sub-cell, returning its cell index to place."""
    sub = canvas.layout.create_cell(name)
    sub.shapes(canvas.layout.layer(*canvas.LAYER["metal1"])).insert(canvas._db.Box(0, 0, 100, 100))
    return sub.cell_index()


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not available")
class PlaceCellTests(unittest.TestCase):
    """``_canvas.Canvas.place_cell()``: micron -> dbu placement through ``_u()``.

    Issue #940 replaced five hand-rolled copies of this idiom (four
    ``_place()`` closures in ``pfd_cp/{block,cp,cp_array,cp_output_stage}.py``
    plus an inline pair in ``divider_chain/divider_chain.py``), each of which
    recomputed ``int(round(1.0 / canvas.dbu))`` and inlined the conversion
    rather than calling ``_u()``. Those copies were *equivalent* only because
    no cell-placing Canvas subclass sets ``GRID_UM``; the grid case below is
    the behaviour that had no coverage before, and is the reason the idiom
    belongs on the Canvas.
    """

    def test_without_a_grid_it_is_plain_rounding(self):
        # Pins the equivalence that made #940's refactor output-neutral: this
        # is exactly what the five deleted copies computed.
        canvas = pfd_devgen.Canvas("place_cell_plain_probe")
        self.assertIsNone(canvas.GRID_UM, "pfd_cp sets no grid -- the premise of the equivalence")
        index = _probe_cell(canvas)
        canvas.place_cell(index, 0.1234, -0.1234)
        self.assertEqual(_instances(canvas), [(123, -123)])

    def test_with_a_grid_the_offset_is_snapped(self):
        # The same off-grid offset, on a Canvas that snaps: 0.1234 um is
        # 123.4 dbu, which is not a multiple of the 5 dbu grid -- so the
        # placement lands on 125, where a hand-rolled conversion would have
        # left it at 123 and failed the PDK's geom.drc OFFGRID section.
        canvas = _SnappedPfdCpCanvas("place_cell_snapped_probe")
        self.assertEqual(canvas._grid_dbu, 5)
        index = _probe_cell(canvas)
        canvas.place_cell(index, 0.1234, -0.1234)
        self.assertEqual(_instances(canvas), [(125, -125)])

    def test_an_on_grid_offset_is_left_alone(self):
        canvas = _SnappedPfdCpCanvas("place_cell_ongrid_probe")
        index = _probe_cell(canvas)
        canvas.place_cell(index, 1.5, 2.25)  # both already multiples of 5 nm
        self.assertEqual(_instances(canvas), [(1500, 2250)])

    def test_it_composes_with_at_like_the_other_drawing_methods(self):
        # rect()/label()/pin() all add self._dx/_dy before converting; so does
        # place_cell(), so an assembler can place a sub-cell inside a
        # translated scope. No current call site does this (every one is at a
        # zero offset), which is why it is pinned here rather than by a block.
        canvas = pfd_devgen.Canvas("place_cell_at_probe")
        index = _probe_cell(canvas)
        with canvas.at(1.0, 2.0):
            canvas.place_cell(index, 0.5, 0.25)
        canvas.place_cell(index, 0.5, 0.25)  # same coords, outside the scope
        self.assertEqual(_instances(canvas), [(500, 250), (1500, 2250)])

    def test_at_translation_is_snapped_after_being_added_not_before(self):
        # The sum is what gets snapped (one _u() call on x + _dx), so two
        # separately-off-grid values that sum on-grid place exactly on it.
        canvas = _SnappedPfdCpCanvas("place_cell_at_snap_probe")
        index = _probe_cell(canvas)
        with canvas.at(0.0020, 0.0):
            canvas.place_cell(index, 0.0030, 0.1234)
        self.assertEqual(_instances(canvas), [(5, 125)])

    def test_several_instances_of_one_cell_each_get_their_own_transform(self):
        # cp_array places 8 instances of 2 cells, cp_output_stage 4 of one
        # inverter, divider_chain 6 of one div23_cell -- repeated placement of
        # a single cell index is the common case, not the exception.
        canvas = pfd_devgen.Canvas("place_cell_multi_probe")
        index = _probe_cell(canvas)
        for dx, dy in ((0.0, 0.0), (2.5, 0.0), (5.0, 1.25)):
            canvas.place_cell(index, dx, dy)
        self.assertEqual(_instances(canvas), [(0, 0), (2500, 0), (5000, 1250)])


if __name__ == "__main__":
    unittest.main()
