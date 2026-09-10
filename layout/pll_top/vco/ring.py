"""Assembles the VCO's 5-stage current-starved ring into one standalone block.

WHAT THIS PASS DRAWS (issue #293, scoped down -- see below)
-------------------------------------------------------------
Real, DRC-clean transistor-level layout for:

* the 5-stage ring itself (``vco_stage.sch`` x5, ``devices.STAGE_FETS``),
  wired ``Y_i -> A_(i+1)`` including the wraparound ``Y5 -> A1``, per
  ``vco.sch``'s ``XS1..XS5`` instantiation order;
* a dedicated VCO guard ring: an outer substrate (``p``) ring tied
  ``GND_VCO``, and an inner n-well tap ring (``n``) tied ``VDD_VCO`` hugging
  the shared n-well that houses every stage's ``MPH``/``MP`` (PMOS) devices
  -- PLL-FLOORPLAN.md section 1;
* the carried-forward 22 pF decap footprint (2x 50x50 um, ``vco.sch``),
  positioned adjacent to the ``VDD_VCO`` pin/ring-tap junction.

WHAT THIS MODULE DEFERRED (and where all of it has since landed)
-----------------------------------------------------------------
Everything this module originally deferred now exists: ``buffer.py`` (output
buffer), ``mirror.py`` (band-select mirror), ``bias_resistors.py`` +
``vtoi_core.py`` (the bias generator), and ``block.py``, which wires all
five under one block-level guard ring and lands the ``VBP``/``VBN`` and
``Y5_CLK_IN`` pins this module exposes. The paragraph below is this module's
own original scope statement, kept as written:

The bias generator (``vco_bias.sch``), the 3-cascade band-select mirror, and
the 3-stage output buffer are **not** drawn here. Issue #293's own dispatch
explicitly allows scoping down to "a coherent, real, DRC-clean sub-portion"
with follow-up issues for the rest rather than shipping placeholder
geometry for a full-scope claim -- this is that scope-down. The ring is the
layout-critical path PLL-FLOORPLAN.md section 1 names explicitly ("the
5-stage ring... is the layout-critical path here... an under-tapped ring
that trips DRC or adds asymmetric parasitic loading to one stage eats
directly into [DR-003's] margin"), and its own guard ring + decap are two of
the acceptance criteria's other bullets, so this is the biggest coherent,
independently-provable slice of the issue's full scope. ``VBP``/``VBN``
(bias inputs) and the ring's own pre-buffer output (``Y5``, i.e. what
``vco.sch`` calls the buffer's input node) are left as Metal1 pins at the
block boundary for the follow-up issue(s) to land the bias generator,
band-select mirror, and output buffer against -- see the tracking issue
filed alongside this PR.

The carried-forward decap keeps the same representation
``layout/floorplan/skeleton.py`` already uses (two 50x50 um boundary
rectangles on GDS layer (0,0) -- no DRC rule in this deck references that
layer, see ``primitives.LAYER``'s docstring): AC's own wording is "carried
forward **unchanged**", not "re-drawn as a real MOS-cap device" -- turning
it into real ``cap_nmos_03v3`` device geometry (comp/poly/mos_cap_mk) is
follow-up-issue scope alongside the bias generator, not implied by "carried
forward unchanged".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim
from . import stage as stage_mod

TOP_CELL = "vco_ring"

STAGE_PITCH_UM = 14.0  # column x0 spacing -- clears the widest device (MPH, 10 um)
                          # plus room for the gate-contact tab (~1.2 um) and a
                          # routing gap to the next stage's tab.

# Guard-ring / routing-channel geometry (um).
OUTER_MARGIN_LEFT_UM = 3.0  # from the leftmost stage's gate tab to the outer p-ring
OUTER_MARGIN_RIGHT_UM = 3.0  # from the rightmost stage's comp edge to the outer p-ring
OUTER_MARGIN_BELOW_UM = 2.5  # from MNT's bottom pad to the outer p-ring's inner edge
OUTER_MARGIN_ABOVE_NWELL_UM = 2.5  # from the n-well top edge to the outer p-ring
RING_WIDTH_UM = 1.2
TAP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, PMOS comp to the inner tap ring's own comp
TAP_RING_WIDTH_UM = 0.6  # inner (VDD_VCO) n-well tap ring band thickness
WRAP_ROUTE_Y_OFFSET_UM = 1.2  # Y5->A1 wraparound route, below the NMOS band

DECAP_SIZE_UM = dev.DECAP_SIZE_UM
DECAP_GAP_UM = 1.0


def pmos_y_range() -> tuple[float, float]:
    """Pure-Python (no KLayout): the shared PMOS band's (y0, y1), column-local.

    Single source of truth for the MNT-MN-(gap)-MP-MPH vertical stack math --
    both ``build()`` (indirectly, via the stages it actually draws) and
    ``footprint_um()``/the tap-pitch tests use this, so there is exactly one
    place that formula can drift from the real generator.
    """
    fets = {f.name: f for f in dev.STAGE_FETS}
    sd = prim.SD_OVERHANG_UM
    comp_gap = prim.COMP_GAP_UM
    mnt_h = 2 * sd + fets["MNT"].l_um
    mn_h = 2 * sd + fets["MN"].l_um
    mp_h = 2 * sd + fets["MP"].l_um
    mph_h = 2 * sd + fets["MPH"].l_um
    y0 = mnt_h + comp_gap + mn_h + prim.NWELL_TO_NMOS_GAP_UM
    y1 = y0 + mp_h + comp_gap + mph_h
    return (y0, y1)


def pmos_x_range() -> tuple[float, float]:
    """Pure-Python: the shared PMOS band's (x0, x1) across all 5 stages."""
    mph_w = next(f for f in dev.STAGE_FETS if f.name == "MPH").w_um
    return (0.0, (dev.STAGE_COUNT - 1) * STAGE_PITCH_UM + mph_w)


def max_pmos_tap_distance_um() -> float:
    """Worst-case distance from any PMOS device to the nearest n-well tap.

    The inner tap band sits ``TAP_GAP_UM`` clear of the PMOS band on both
    the top and bottom; the worst-case point is the MP/MPH boundary in the
    middle of the stack, equidistant from both bands.
    """
    y0, y1 = pmos_y_range()
    return (y1 - y0) / 2.0 + TAP_GAP_UM


def max_nmos_tap_distance_um() -> float:
    """Worst-case distance from any NMOS device to the outer p-ring's bottom band.

    Mirrors ``max_pmos_tap_distance_um()`` for the substrate side: the NMOS
    band runs from y=0 (``MNT``'s own bottom/``GND_VCO`` terminal, which is
    itself Metal1-tied into the outer ring's own net) up to the top of
    ``MN``, and the outer ring's bottom band sits ``OUTER_MARGIN_BELOW_UM``
    below y=0.
    """
    fets = {f.name: f for f in dev.STAGE_FETS}
    sd = prim.SD_OVERHANG_UM
    comp_gap = prim.COMP_GAP_UM
    mnt_h = 2 * sd + fets["MNT"].l_um
    mn_h = 2 * sd + fets["MN"].l_um
    nmos_top = mnt_h + comp_gap + mn_h
    return nmos_top + OUTER_MARGIN_BELOW_UM


@dataclass
class VcoRingResult:
    canvas: prim.Canvas
    stage_ports: list = field(default_factory=list)
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)  # x0, y0, x1, y1 of the outer p-ring
    nwell_box: tuple = (0.0, 0.0, 0.0, 0.0)


def build(
    outdir: Path | None = None,
    canvas: prim.Canvas | None = None,
    *,
    draw_decap: bool = True,
) -> VcoRingResult:
    """Draw the ring block.

    ``canvas`` draws into a caller-supplied canvas (``block.py`` assembling
    every VCO sub-block into one flat top cell) instead of a private one.
    ``draw_decap=False`` suppresses this block's own carried-forward 22 pF
    decap markers -- the assembled block places that pair against *its* own
    ``VDD_VCO`` pin/ring-tap junction rather than the ring's, which is what
    issue #293's acceptance criterion actually asks for; drawing both would
    be two marker pairs for one physical pair of caps.
    """
    canvas = prim.Canvas(TOP_CELL) if canvas is None else canvas

    # --- 1. place the 5 stages ---
    stage_ports = []
    for i in range(dev.STAGE_COUNT):
        x0 = i * STAGE_PITCH_UM
        ports = stage_mod.build_stage(canvas, x0=x0, y_bottom=0.0, stage_name=f"S{i + 1}")
        stage_ports.append(ports)

    # --- 2. ring wiring: Y_i -> A_(i+1), wraparound Y5 -> A1 ---
    gap_mid_y = (stage_ports[0].y_pad[3] + stage_ports[0].a_gate_pad_top[1]) / 2.0
    # a_gate_pad_top sits ABOVE a_gate_pad_bottom (MP's gate vs MN's gate) --
    # the inter-stage route lands on the lower (MN-side) pad, which is the
    # one physically closer to the routing channel between stages.
    for i in range(dev.STAGE_COUNT):
        src = stage_ports[i]
        dst = stage_ports[(i + 1) % dev.STAGE_COUNT]
        if i < dev.STAGE_COUNT - 1:
            prim.route_pads(canvas, src.y_pad, dst.a_gate_pad_bottom, gap_mid_y)
        else:
            # Wraparound: route below the whole NMOS band, clear of every
            # stage's own comp/poly, then up into stage 1's A gate pad.
            wrap_y = -WRAP_ROUTE_Y_OFFSET_UM
            prim.route_pads(canvas, src.y_pad, dst.a_gate_pad_bottom, wrap_y)
        # Issue #367: label every ring-internal chain net with the exact name
        # design/netlist/vco.spice's own `.subckt vco` uses (Y1..Y5, per its
        # XS1..XS5 instance lines) -- not just this module's own
        # ``stage.py``-assigned "S<i>.Y" per-instance label. Five structurally
        # identical stages are exactly the kind of repeated macro
        # ``divider_chain.py``'s own PROOF documents defeating the LVS
        # comparer's topology-only matching when left unlabelled; naming each
        # chain net by its real schematic identity (rather than relying on
        # the per-instance "S<i>.Y" label alone, which has no counterpart in
        # ``block.reference_netlist()``) gives the comparer's name-based hint
        # matching the same anchor ``block.py``'s own top-level nets already
        # get. This is additive -- ``"S<i>.Y"`` stays, unchanged, alongside it.
        canvas.pin(f"Y{i + 1}", *src.y_pad)

    # --- 3. shared n-well over every stage's MP/MPH devices, sized with real
    # clearance (TAP_GAP_UM) for the inner n-well tap ring (step 7) to sit
    # in -- the PMOS cluster itself packs MP+MPH edge-to-edge across all 5
    # stages with no free interior room, so the tap ring has to live in a
    # band the well is deliberately over-sized to provide, not squeezed
    # into whatever margin NWELL_MARGIN_UM leaves for DRC enclosure alone. ---
    pmos_x0 = min(p.pmos_x0 for p in stage_ports)
    pmos_x1 = max(p.pmos_x1 for p in stage_ports)
    pmos_y0 = min(p.pmos_y0 for p in stage_ports)
    pmos_y1 = max(p.pmos_y1 for p in stage_ports)
    tap_ring_outer = (
        pmos_x0 - TAP_GAP_UM - TAP_RING_WIDTH_UM,
        pmos_y0 - TAP_GAP_UM - TAP_RING_WIDTH_UM,
        pmos_x1 + TAP_GAP_UM + TAP_RING_WIDTH_UM,
        pmos_y1 + TAP_GAP_UM + TAP_RING_WIDTH_UM,
    )
    nwell_box = (
        tap_ring_outer[0] - prim.NWELL_MARGIN_UM,
        tap_ring_outer[1] - prim.NWELL_MARGIN_UM,
        tap_ring_outer[2] + prim.NWELL_MARGIN_UM,
        tap_ring_outer[3] + prim.NWELL_MARGIN_UM,
    )
    canvas.rect("nwell", *nwell_box)

    # --- 4/5. VBP/VBN/VDD_VCO/GND_VCO rails: one Metal1 rectangle per net,
    # drawn at *exactly* the same y0/y1 as a representative stage's own pad
    # (every stage is identical, just x-shifted -- stage.py), not a
    # separately re-centered fixed-width wire. Reusing the pad's own y-range
    # verbatim means the rail is a superset of (not merely adjacent to) each
    # stage's local pad with **zero** notch -- a rail narrower than the pad
    # it grows out of leaves a step in the merged polygon shallower than
    # M1.2a's 0.23 um min, which is what the first DRC pass of this
    # generator hit (see the module docstring's iteration notes). ---
    rail_x0 = min(p.a_gate_pad_bottom[0] for p in stage_ports) - 1.0
    row_x0 = min(p.x0 for p in stage_ports)
    row_x1 = max(p.x1 for p in stage_ports)
    rail_x1 = max(row_x1, max(p.vbp_pad[2] for p in stage_ports))

    ref = stage_ports[0]
    for net, pad, x0, x1 in (
        ("VBP", ref.vbp_pad, rail_x0, rail_x1),
        ("VBN", ref.vbn_pad, rail_x0, rail_x1),
        ("VDD_VCO", ref.vdd_pad, row_x0, row_x1),
        ("GND_VCO", ref.gnd_pad, row_x0, row_x1),
    ):
        canvas.rect("metal1", x0, pad[1], x1, pad[3])
        canvas.pin(net, x0, pad[1], x0 + 1.0, pad[3])

    # --- 6. Y5 (pre-buffer output) pin, for the follow-up output-buffer issue ---
    canvas.pin("Y5_CLK_IN", *stage_ports[-1].y_pad)

    # --- 7. guard ring: outer p (GND_VCO) around the whole block, inner n
    # tap band (VDD_VCO) inside the shared n-well -- PLL-FLOORPLAN.md
    # section 1. The inner tap is drawn as top+bottom Metal1/comp bands only
    # (not a full 4-sided ring): the n-well is a long, thin horizontal band
    # with every PMOS device already packed edge-to-edge across its full
    # width, so there is no free interior room on the *sides* for a left/
    # right band without landing on a stage's own gate-contact tab -- see
    # this module's DRC-iteration notes. Top+bottom bands alone already put
    # every PMOS device within TAP_GAP_UM+TAP_RING_WIDTH_UM (well under the
    # DF.13_MV/DF.14_MV 15 um pitch bound) of a tap, which is the actual
    # requirement -- a closed 4-sided ring is a stronger shape than the rule
    # needs. ---
    outer_x0 = min(nwell_box[0], min(p.a_gate_pad_bottom[0] for p in stage_ports)) - OUTER_MARGIN_LEFT_UM
    outer_x1 = max(nwell_box[2], row_x1) + OUTER_MARGIN_RIGHT_UM
    outer_y0 = min(-WRAP_ROUTE_Y_OFFSET_UM, stage_ports[0].gnd_pad[1]) - OUTER_MARGIN_BELOW_UM
    outer_y1 = nwell_box[3] + OUTER_MARGIN_ABOVE_NWELL_UM
    prim.guard_ring(canvas, "p", outer_x0, outer_y0, outer_x1, outer_y1, RING_WIDTH_UM, "GND_VCO")

    prim.tap_strip(canvas, "n", tap_ring_outer[0], tap_ring_outer[3] - TAP_RING_WIDTH_UM, tap_ring_outer[2], tap_ring_outer[3], "VDD_VCO")
    prim.tap_strip(canvas, "n", tap_ring_outer[0], tap_ring_outer[1], tap_ring_outer[2], tap_ring_outer[1] + TAP_RING_WIDTH_UM, "VDD_VCO")

    # --- 8. carried-forward 22 pF decap (unchanged from
    # layout/floorplan/skeleton.py -- see module docstring), placed adjacent
    # to the VDD_VCO pin/ring-tap junction (the inner n-ring's right edge,
    # inside the outer guard ring). ---
    decap0_x0 = outer_x1 - OUTER_MARGIN_RIGHT_UM + DECAP_GAP_UM
    decap0_y0 = outer_y0 + DECAP_GAP_UM
    decap1_x0 = decap0_x0 + DECAP_SIZE_UM + DECAP_GAP_UM
    if draw_decap:
        canvas.rect("boundary", decap0_x0, decap0_y0, decap0_x0 + DECAP_SIZE_UM, decap0_y0 + DECAP_SIZE_UM)
        canvas.label("boundary", "vco.decap0", decap0_x0 + 1.0, decap0_y0 + 1.0)
        canvas.rect("boundary", decap1_x0, decap0_y0, decap1_x0 + DECAP_SIZE_UM, decap0_y0 + DECAP_SIZE_UM)
        canvas.label("boundary", "vco.decap1", decap1_x0 + 1.0, decap0_y0 + 1.0)
    outer_x1_with_decap = decap1_x0 + DECAP_SIZE_UM + OUTER_MARGIN_RIGHT_UM

    footprint = (
        outer_x0,
        outer_y0,
        max(outer_x1, outer_x1_with_decap) if draw_decap else outer_x1,
        outer_y1,
    )

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return VcoRingResult(canvas=canvas, stage_ports=stage_ports, footprint=footprint, nwell_box=nwell_box)


def footprint_um(with_decap: bool = True) -> tuple:
    """Pure-Python (no KLayout) footprint estimate, for tests.

    Recomputes the same bounding geometry ``build()`` derives from the
    stages' drawn ports, but from ``devices.py``'s numbers directly, so
    ``layout/tests/test_vco_layout.py`` can check it without a PV
    environment. Mirrors ``build()``'s own math -- if the two ever
    disagree, that is a real bug in one of them, which is exactly what the
    test this function backs is for.
    """
    # --- vertical stack (step 1 in build()) ---
    pmos_y0, pmos_y1 = pmos_y_range()

    # --- n-well + inner tap band (step 3 in build()) ---
    pmos_x0, pmos_x1 = pmos_x_range()
    tap_margin = TAP_GAP_UM + TAP_RING_WIDTH_UM
    nwell_box = (
        pmos_x0 - tap_margin - prim.NWELL_MARGIN_UM,
        pmos_y0 - tap_margin - prim.NWELL_MARGIN_UM,
        pmos_x1 + tap_margin + prim.NWELL_MARGIN_UM,
        pmos_y1 + tap_margin + prim.NWELL_MARGIN_UM,
    )

    # --- gate-contact tab x offset (mosfet()'s left endcap + tab, column
    # x0=0 -- see primitives.mosfet()) ---
    tab_x0 = -(
        prim.POLY_ENDCAP_UM
        - prim.GATE_TAB_OVERLAP_UM
        + prim.GATE_TAB_W_UM
        + prim.METAL1_PAD_MARGIN_UM
    )

    # --- outer p-ring (step 7 in build()) ---
    outer_x0 = min(nwell_box[0], tab_x0) - OUTER_MARGIN_LEFT_UM
    outer_x1_devices = max(nwell_box[2], pmos_x1) + OUTER_MARGIN_RIGHT_UM
    outer_y0 = -WRAP_ROUTE_Y_OFFSET_UM - OUTER_MARGIN_BELOW_UM
    outer_y1 = nwell_box[3] + OUTER_MARGIN_ABOVE_NWELL_UM

    # --- carried-forward decap (step 8 in build()) ---
    decap0_x0 = outer_x1_devices - OUTER_MARGIN_RIGHT_UM + DECAP_GAP_UM
    decap1_x0 = decap0_x0 + DECAP_SIZE_UM + DECAP_GAP_UM
    outer_x1_with_decap = decap1_x0 + DECAP_SIZE_UM + OUTER_MARGIN_RIGHT_UM
    outer_x1 = max(outer_x1_devices, outer_x1_with_decap) if with_decap else outer_x1_devices

    return (outer_x0, outer_y0, outer_x1, outer_y1)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default=str(Path(__file__).resolve().parents[2] / "evidence" / "vco-layout" / "work"))
    args = parser.parse_args()
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {args.outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
