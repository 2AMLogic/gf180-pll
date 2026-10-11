#!/usr/bin/env python3
"""Focused regression coverage for the shared drawing helpers in
``pll_top/_canvas.py`` that issue #776 consolidated: ``h_wire()``,
``snap_um()``, ``via1_stack()`` and ``tap_strip()``.

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


if __name__ == "__main__":
    unittest.main()
