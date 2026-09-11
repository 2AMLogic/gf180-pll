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

SUPPLY/BIAS RAIL GEOMETRY (issue #371, root-caused in
``layout/evidence/vco-layout/PROOF-368-rootcause.md``)
-------------------------------------------------------------------------
The first version of this generator got four things wrong here, none of
which any DRC run could report (touching same-layer shapes merge into one
polygon before any spacing rule runs, so a short is never a violation) --
the analogous fix in ``buffer.py`` (issue #372) is the sibling of this one,
drawn against that block's own (different) geometry, and its own status
update is what found the fourth item below:

1. **``VDD_VCO``/``GND_VCO`` are full-row Metal1 rails that structurally
   overlapped their own device's bias-gate pad.** ``primitives.mosfet()``'s
   gate-contact pad and its adjacent terminal pad overlap in y by
   ``0.26 - l_um/2`` (0.01 um at this block's ``l_um=0.5`` ``MPH``/``MNT``)
   -- harmless per device (the gate tab sits at a different x than the
   terminal pad's own comp column), but a real short once the terminal pad
   is stretched into a full-row-width rail that reaches every *other*
   stage's own bias-gate pad too. ``build()`` relocates each supply rail's
   near edge into the clear channel beyond ``VBP``/``VBN``'s own natural
   pad (not merely clipped in place -- see the "moved wholesale" note in
   ``buffer.py``'s own fix) by at least ``devices.DRC_METAL1_MIN_SPACE_UM``.
2. **Every supply rail is deliberately strapped to the ring that biases the
   same net.** The internal ``VDD_VCO``/``GND_VCO`` rail, the inner n-well
   tap ring and the outer p guard ring were three separately-labelled
   Metal1 islands never joined by any drawn metal -- the same
   device-to-ring tie ``mirror.py`` draws per fet with its own
   ``rail_stub()`` and ``buffer.py`` draws per rail. Each strap runs from
   the internal rail's own edge to the ring's own comp edge, a real
   ``primitives.METAL1_PAD_MARGIN_UM`` overlap into the ring's own Metal1
   pad rather than a coincident edge.
3. **The Y5->A1 wraparound route's own vertical risers cross other nets'
   Metal1 on the way down to ``wrap_y``.** Both risers start above the
   whole lower stack and end below it, so each necessarily passes through
   every other net's own per-stage Metal1 in that column -- ``GND_VCO``'s
   rail *and* ``MNT``'s own ``NT`` (drain) pad under the Y5 riser's own
   column, ``VBN``'s own natural gate pad under the A1 riser's column.
   Enumerating that obstruction set precisely is fragile (an earlier
   version of this fix computed one explicit band and missed ``NT``, which
   cost a real short even after items 1/2/4 were otherwise fixed); instead
   ``build()`` hops each riser's *entire* descent on Metal2
   (``via1_stack()`` + ``m2_route()``, the same "Metal2 has no spacing
   relationship with Metal1" escape ``buffer.py``'s own ``_channel_hop()``
   and ``block.py``'s routing already rely on) rather than trying to duck
   under a computed window.
4. **``VBP``/``VBN`` cannot be a full-row Metal1 rail at all.** Unlike
   ``VDD_VCO``/``GND_VCO`` (which have open channel on their *outer* side,
   away from the device stack, to relocate into -- item 1), each bias-gate
   pad sits *between* two different terminal pads of its own device
   (``MNT``: ``GND_VCO`` below, ``NT`` above; ``MPH``: ``NH`` below,
   ``VDD_VCO`` above) and overlaps *both* by the same structural ~0.01 um,
   symmetrically. The clear room between those two neighbours (~0.6 um) is
   narrower than one legal-width Metal1 rail plus M1.2a clearance on both
   sides (>= 0.23 + 0.23 + 0.23 um). ``build()`` instead leaves every
   stage's own natural bias-gate pad untouched (still safe, still per-device
   -- item 1's problem was only ever the *rail*, never the natural pad) and
   ties all five to one shared Metal2 trunk via ``via1_stack()`` per stage,
   the same "Metal2 has no spacing relationship with Metal1" property item 3
   uses. The trunk itself is routed clear of every other net's own Metal2 in
   this generator (the wraparound risers, item 3; ``stage.py``'s own
   NMOS/PMOS channel hops) -- ``VBN``'s trunk runs below ``wrap_y`` (where
   both risers stop), ``VBP``'s runs above the inner tap ring (where nothing
   else on Metal2 ever reaches). One exception: the A1 riser's own natural
   landing column is ``VBN``'s stage-1 gate-tab column too (both are the
   gate-contact-tab x, shared by every device in a column -- see
   ``stage.py``'s own docstring), so the A1 riser jogs sideways to a clear
   column immediately after leaving its pad, before descending -- freeing
   that column for ``VBN``'s own stage-1 tap to use straight.
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
OUTER_MARGIN_BELOW_UM = 3.5  # from MNT's bottom pad to the outer p-ring's inner edge --
                                # also has to leave room for VBN_TRUNK_Y_UM's own via1_stack
                                # pads to clear the ring's own Metal1 by M1.2a (issue #371)
OUTER_MARGIN_ABOVE_NWELL_UM = 2.5  # from the n-well top edge to the outer p-ring
RING_WIDTH_UM = 1.2
TAP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, PMOS comp to the inner tap ring's own comp
TAP_RING_WIDTH_UM = 0.6  # inner (VDD_VCO) n-well tap ring band thickness
WRAP_ROUTE_Y_OFFSET_UM = 1.2  # Y5->A1 wraparound route, below the NMOS band

DECAP_SIZE_UM = dev.DECAP_SIZE_UM
DECAP_GAP_UM = 1.0

# Metal1/Metal2 landing pad half-footprint a via1_stack() call grows around
# its own via -- see primitives.via1_stack()'s own "half_p" local.
VIA1_PAD_HALF_UM = prim.VIA1_SIZE_UM / 2.0 + prim.VIA1_METAL_ENCLOSE_UM

# Y5->A1 wraparound Metal2 hop (issue #371, item 3): the x the A1 riser
# jogs sideways to immediately after leaving its own pad, clear of every
# gate-tab column (including its own -- see item 4) and of the outer guard
# ring's own left margin.
A1_RISER_JOG_X_UM = -2.0

# VBN's Metal2 trunk (issue #371, item 4) sits below wrap_y -- both
# wraparound risers stop *at* wrap_y (their own via1_stack lands there), so
# anything below it clears them in y regardless of x. Two independent
# clearances bound where exactly: M2.2a's own min-spacing rule (0.28 um)
# from those risers' own bottom via1_stack pads (bounds this from above),
# and M1.2a's (0.23 um) from the outer guard ring's own bottom Metal1 band
# (every via1_stack -- including block.py's own, landing on this trunk to
# reach it from the mirror block below -- draws a Metal1 pad too, not just
# Metal2; bounds this from below). 1.4 um clears both with real margin
# (``OUTER_MARGIN_BELOW_UM`` is sized to leave room for it).
VBN_TRUNK_Y_UM = -WRAP_ROUTE_Y_OFFSET_UM - 1.4

# VBP's Metal2 trunk sits above the inner tap ring's own top band -- nothing
# else in this generator ever reaches that high on Metal2 (the wraparound
# risers and stage.py's own NMOS/PMOS channel hops both live far below it).
VBP_TRUNK_CLEARANCE_UM = 0.6


def _route_wraparound_hop(
    canvas: prim.Canvas,
    pad_a: tuple,
    pad_b: tuple,
    via_y: float,
    *,
    jog_b_to_x: float | None = None,
) -> None:
    """Connect two Metal1 pads via an all-Metal2 descent to ``via_y`` (the
    Y5->A1 wraparound route -- issue #371, item 3; see the module
    docstring's "SUPPLY/BIAS RAIL GEOMETRY" section for why this hops the
    *entire* descent rather than trying to duck under a computed
    obstruction window). ``jog_b_to_x``, when given, routes ``pad_b``'s own
    riser sideways to a clear column immediately after leaving its pad,
    before descending -- used for the A1 side, whose landing column is
    ``VBN``'s own stage-1 gate-tab column too (issue #371, item 4).

    Each riser's own pad-side ``via1_stack()`` lands at the pad's *centre*
    (not the nearer edge ``primitives.route_pads()`` itself would pick):
    ``stage.py``'s own NMOS/PMOS channel hop already places a same-net via
    at that exact centre point for both ``src.y_pad`` (stage 5's own drain
    pad) and ``dst.a_gate_pad_bottom`` (stage 1's own gate pad) -- landing
    here too lands directly on top of it (same net, same point) instead of
    a few tenths of a micron away, which a first version of this fix did
    and tripped V1.1/V1.2a/M1.2a (adjacent, same-net vias close enough to
    violate via/Metal1 spacing without ever touching).
    """

    def _riser(pad: tuple, jog_to: float | None) -> float:
        x = (pad[0] + pad[2]) / 2.0
        y = (pad[1] + pad[3]) / 2.0
        prim.via1_stack(canvas, x, y)
        if jog_to is not None:
            prim.via1_stack(canvas, jog_to, y)
            prim.m2_route(canvas, [(x, y), (jog_to, y)])
            x = jog_to
        prim.via1_stack(canvas, x, via_y)
        prim.m2_route(canvas, [(x, y), (x, via_y)])
        return x

    ax = _riser(pad_a, None)
    bx = _riser(pad_b, jog_b_to_x)
    half = prim.METAL1_WIRE_WIDTH_UM / 2.0
    prim.h_wire(canvas, min(ax, bx) - half, max(ax, bx) + half, via_y)


def _bias_trunk(
    canvas: prim.Canvas,
    stage_ports: list,
    pad_attr: str,
    net: str,
    trunk_y: float,
    *,
    extra_x: list[float],
    pin_x: float,
) -> None:
    """Tie every stage's own natural ``pad_attr`` gate pad (``VBP``/``VBN``)
    to one shared Metal2 trunk at ``trunk_y`` instead of a full-row Metal1
    rail -- issue #371, item 4 (see the module docstring). Each stage's own
    natural pad is left completely alone -- still a safe, per-device
    Metal1 shape, still electrically its own transistor's gate -- and gets
    exactly **one** ``via1_stack()`` (the M1<->M2 transition at the pad
    itself) plus a pure-Metal2 run down/up to the trunk. A second via at
    the trunk itself is deliberately *not* drawn: an M2-to-M2 corner needs
    no via at all, and a first version of this fix placed one there anyway
    -- its own incidental Metal1 pad (every ``via1_stack()`` call draws
    both layers) came within M1.2a spacing of the outer guard ring's own
    Metal1 for every stage at once, a violation invisible until a real DRC
    run rather than the reproduction script (which only checks Metal1
    *connectivity*, not spacing). ``extra_x`` extends the trunk's own drawn
    Metal2 past the last stage to wherever ``block.py``'s own assembly
    expects to land a via on this net (it reads only this pin's own *y*,
    via ``_center()``, and computes its own x independently -- so the
    trunk merely needs to physically reach that x, not know its value
    symbolically).
    """
    xs = list(extra_x)
    for p in stage_ports:
        pad = getattr(p, pad_attr)
        x = (pad[0] + pad[2]) / 2.0
        y = (pad[1] + pad[3]) / 2.0
        prim.via1_stack(canvas, x, y)
        prim.m2_route(canvas, [(x, y), (x, trunk_y)])
        xs.append(x)
    prim.m2_route(canvas, [(min(xs), trunk_y), (max(xs), trunk_y)])
    half = 0.3
    canvas.pin(net, pin_x - half, trunk_y - half, pin_x + half, trunk_y + half, layer="metal2_label")


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

    # --- 1b. VDD_VCO/GND_VCO rail geometry (issue #371, items 1+2 -- see
    # the module docstring's "SUPPLY/BIAS RAIL GEOMETRY" section). Computed
    # here so it is in scope for the rects drawn at step 4/5 below; nothing
    # draws yet.
    #
    # Every stage's own natural VDD_VCO/GND_VCO terminal pad and VBP/VBN
    # gate pad is ALREADY drawn -- unconditionally, at that stage's own
    # local x -- by primitives.mosfet() inside stage.py's own
    # build_stage() call at step 1, above. That per-device geometry cannot
    # be clipped or moved (it IS the transistor terminal); only the *extra*
    # full-row rail this module draws on top of it can be, and item 4 (see
    # the module docstring) is why VBP/VBN no longer get one at all -- only
    # VDD_VCO/GND_VCO's own rails are computed here, each relocated into the
    # clear channel beyond the *natural* (opposite net's) bias-gate pad
    # instead of sitting exactly on their own device's terminal -- the same
    # "moved wholesale" conclusion ``buffer.py``'s own fix (issue #372)
    # reached, since simply clipping a rail this narrow left it under
    # M1.1's own 0.23 um minimum width. ---
    row_x0 = min(p.x0 for p in stage_ports)
    row_x1 = max(p.x1 for p in stage_ports)

    ref = stage_ports[0]
    clearance = dev.DRC_METAL1_MIN_SPACE_UM
    natural_pads: dict[str, tuple[float, float]] = {
        "VDD_VCO": (ref.vdd_pad[1], ref.vdd_pad[3]),
        "GND_VCO": (ref.gnd_pad[1], ref.gnd_pad[3]),
        "VBP": (ref.vbp_pad[1], ref.vbp_pad[3]),
        "VBN": (ref.vbn_pad[1], ref.vbn_pad[3]),
    }
    # VDD_VCO's own rail relocates ABOVE VBP's *natural* gate pad: its near
    # (bottom) edge clears VBP's own pad by ``clearance``, while its far
    # (top) edge reaches all the way to the n-well tap ring's own comp edge
    # (set once that geometry exists, at step 4/5) -- a real overlap into
    # the ring's own Metal1, so no separate strap is needed on this side at
    # all.
    vdd_rail_y0 = dev.snap_um(max(natural_pads["VDD_VCO"][0], natural_pads["VBP"][1] + clearance))
    if vdd_rail_y0 >= natural_pads["VDD_VCO"][1]:
        raise ValueError(
            f"VDD_VCO rail's clearance-clipped y0={vdd_rail_y0:.3f} leaves no overlap with "
            f"its own natural pad {natural_pads['VDD_VCO']} -- issue #371 clip fix"
        )
    # GND_VCO's own rail relocates BELOW VBN's *natural* gate pad: its near
    # (top) edge clears VBN's own pad by ``clearance``, and its own height
    # matches the natural GND_VCO pad's own height (a known-legal Metal1
    # width, comfortably above M1.1's 0.23 um minimum, rather than the
    # tightest clip that would fit -- the Y5->A1 wraparound route's own
    # Metal1 h_wire (``wrap_y``, step 2) sits close enough below that a
    # too-tight clip leaves no room for it). This rail's far (bottom) edge
    # still cannot reach the outer guard ring directly without crossing
    # that h_wire across most of the row, so a single narrow strap (step
    # 7b, at an x clear of the h_wire) makes that last hop instead, same as
    # buffer.py's own rail-to-ring strap.
    gnd_rail_y1 = dev.snap_um(min(natural_pads["GND_VCO"][1], natural_pads["VBN"][0] - clearance))
    gnd_rail_y0 = dev.snap_um(gnd_rail_y1 - (natural_pads["GND_VCO"][1] - natural_pads["GND_VCO"][0]))
    h_wire_y1 = -WRAP_ROUTE_Y_OFFSET_UM + prim.METAL1_WIRE_WIDTH_UM / 2.0
    if gnd_rail_y1 <= natural_pads["GND_VCO"][0] or gnd_rail_y0 >= gnd_rail_y1:
        raise ValueError(
            f"GND_VCO rail's clearance-clipped range ({gnd_rail_y0:.3f}, {gnd_rail_y1:.3f}) "
            f"leaves no overlap with its own natural pad {natural_pads['GND_VCO']}, or no "
            "positive height -- issue #371 clip fix"
        )
    if gnd_rail_y0 < h_wire_y1 + clearance:
        raise ValueError(
            f"GND_VCO rail's own y0={gnd_rail_y0:.3f} leaves less than {clearance} um "
            f"clearance from the wraparound route's own Metal1 h_wire (top edge "
            f"{h_wire_y1:.3f}) -- issue #371 clip fix"
        )

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
            # stage's own comp/poly, then up into stage 1's A gate pad --
            # hopping the *entire* descent on Metal2 (issue #371, item 3),
            # with the A1-side riser jogged clear of stage 1's own VBN
            # gate-tab column first (item 4).
            wrap_y = -WRAP_ROUTE_Y_OFFSET_UM
            _route_wraparound_hop(
                canvas, src.y_pad, dst.a_gate_pad_bottom, wrap_y, jog_b_to_x=A1_RISER_JOG_X_UM
            )
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

    # --- 4/5. VDD_VCO/GND_VCO rails (issue #371, items 1+2 -- see the
    # module docstring and step 1b's own derivation of ``vdd_rail_y0``/
    # ``gnd_rail_y0``/``gnd_rail_y1``). VDD_VCO's rail runs all the way to
    # the n-well tap ring's own comp edge -- a real overlap into the ring's
    # Metal1, the device-to-ring strap for this net, no separate strap
    # rect needed. GND_VCO's rail stops short of the outer p-ring (it
    # cannot reach it directly without crossing the wraparound route's own
    # Metal1 h_wire below); step 7b makes that last hop. ---
    vdd_rail_y1 = tap_ring_outer[3] - TAP_RING_WIDTH_UM
    canvas.rect("metal1", row_x0, vdd_rail_y0, row_x1, vdd_rail_y1)
    canvas.pin("VDD_VCO", row_x0, vdd_rail_y0, row_x0 + 1.0, vdd_rail_y1)
    canvas.rect("metal1", row_x0, gnd_rail_y0, row_x1, gnd_rail_y1)
    canvas.pin("GND_VCO", row_x0, gnd_rail_y0, row_x0 + 1.0, gnd_rail_y1)

    # --- VBP/VBN: Metal2 trunks tying every stage's own natural bias-gate
    # pad together, not full-row Metal1 rails -- issue #371, item 4 (see
    # ``_bias_trunk()`` and the module docstring). VBP's trunk sits above
    # the inner tap ring's own top band (clear of everything else this
    # generator ever puts on Metal2); VBN's sits below ``wrap_y`` (clear of
    # both wraparound risers, which stop there). VBN's trunk additionally
    # reaches ``block.py``'s own expected landing x past stage 5's own
    # column -- see ``_bias_trunk()``'s own docstring on ``extra_x``. ---
    vbp_trunk_y = tap_ring_outer[3] + VBP_TRUNK_CLEARANCE_UM
    vbp_pin_x = dev.snap_um(min(p.a_gate_pad_bottom[0] for p in stage_ports) + 0.5)
    _bias_trunk(canvas, stage_ports, "vbp_pad", "VBP", vbp_trunk_y, extra_x=[], pin_x=vbp_pin_x)

    vbn_extra_x = dev.snap_um((dev.STAGE_COUNT - 1) * STAGE_PITCH_UM + 4.0)
    _bias_trunk(
        canvas,
        stage_ports,
        "vbn_pad",
        "VBN",
        VBN_TRUNK_Y_UM,
        extra_x=[vbn_extra_x],
        pin_x=vbn_extra_x,
    )

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

    # --- 7a2. Metal1 strap down the n-well's right-hand edge, tying the top
    # and bottom n-well tap bands together (issue #371, item 5 -- found by
    # running the reproduction script against *this* fix rather than
    # assumed from the issue text, same as ``buffer.py``'s own analogous
    # strap for issue #372). The two ``tap_strip()`` calls just above draw
    # top+bottom bands only (no left/right band -- see this step's own
    # docstring above), so with the NMOS/PMOS-channel-crossing bridges now
    # correctly hopped onto Metal2 (``stage.py``'s own ``_channel_hop()``,
    # issue #371's fourth defect beyond the three the issue names), nothing
    # else on Metal1 legally touches the *bottom* band at all -- it would
    # otherwise be a genuinely floating ``VDD_VCO`` island, which the
    # reproduction script (``layout/evidence/vco-layout/
    # PROOF-368-rootcause.md``) reports as a second disconnected polygon for
    # the same label, not a multi-label short, but is exactly as wrong.
    # Metal1, not a third ``tap_strip()``: a comp band on this edge would
    # land on stage 5's own gate-poly endcap (``buffer.py``'s identical
    # note), and Metal1 has no spacing relationship with poly it does not
    # already own. ---
    canvas.rect(
        "metal1",
        tap_ring_outer[2] - TAP_RING_WIDTH_UM,
        tap_ring_outer[1] + TAP_RING_WIDTH_UM,
        tap_ring_outer[2],
        tap_ring_outer[3] - TAP_RING_WIDTH_UM,
    )

    # --- 7b. Deliberate device-to-ring strap for GND_VCO (issue #371, item
    # 1). VDD_VCO's own rail already runs directly into the n-well tap
    # ring's own comp edge (step 4/5) -- a real overlap, no separate strap
    # needed. GND_VCO's rail stops short of the outer p-ring on purpose
    # (its far edge cannot reach the ring directly without crossing the
    # wraparound route's own Metal1 h_wire, which spans nearly the whole
    # row): one narrow strap makes that last hop, at an x clear of the
    # h_wire (and the via1 pads item 3's hop lands there), running INTO the
    # ring's own comp edge -- not a coincident edge, so it lands
    # ``METAL1_PAD_MARGIN_UM`` inside the ring's own Metal1 by construction
    # (see ``tap_strip()``'s own pad-growth math) -- the same convention
    # ``mirror.py``'s own ``rail_stub()`` and ``buffer.py``'s rail-to-ring
    # strap (issue #372) both use. ---
    wrap_hi = (
        max(
            (stage_ports[-1].y_pad[0] + stage_ports[-1].y_pad[2]) / 2.0,
            (stage_ports[0].a_gate_pad_bottom[0] + stage_ports[0].a_gate_pad_bottom[2]) / 2.0,
        )
        + prim.METAL1_WIRE_WIDTH_UM / 2.0
        + VIA1_PAD_HALF_UM
    )
    strap_x = dev.snap_um((wrap_hi + row_x1) / 2.0)
    strap_half_w = 0.5
    if strap_x - strap_half_w <= wrap_hi or strap_x + strap_half_w > row_x1:
        raise ValueError(
            f"no clear x={strap_x} left in the row [{row_x0},{row_x1}] for the issue #371 "
            f"GND_VCO ring strap, clear of the wraparound route's own Metal1 "
            f"(x <= {wrap_hi:.3f})"
        )
    canvas.rect(
        "metal1",
        strap_x - strap_half_w,
        outer_y0 + RING_WIDTH_UM,
        strap_x + strap_half_w,
        gnd_rail_y0,
    )

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


def reference_netlist() -> str:
    """Standalone LVS reference for :data:`TOP_CELL` (``vco_ring``).

    ``block.py``'s own :func:`~block.reference_netlist` covers this same
    ring as part of the *assembled* block; this one exists so ``ring.py``
    is provable on its own, the same reasoning ``buffer.py``'s own
    :func:`~buffer.reference_netlist` (issue #372) already gives -- a
    block-level LVS mismatch cannot say *which* sub-block's geometry is
    wrong, and issue #368's own short took a full root-cause investigation
    partly because no sub-block had an LVS testbench of its own yet.

    Device lines and node ordering mirror ``block.py``'s own per-stage
    translation of ``devices.STAGE_FETS`` exactly (``A``/``Y`` renamed to
    this ring's own chain nets, ``VDD``/``VSS`` to ``VDD_VCO``/``GND_VCO``,
    ``NH``/``NT`` to per-stage-local names) -- not re-derived independently,
    so the two references cannot drift apart in convention.

    Run it (from the repo root, with the PDK/KLayout environment
    ``layout/run_pv.py check-env`` reports)::

        python3 -m layout.pll_top.vco.ring --outdir <workdir>
        python3 -c "from layout.pll_top.vco import ring; \\
          open('<workdir>/vco_ring.spice','w').write(ring.reference_netlist())"
        python3 layout/run_pv.py lvs <workdir>/vco_ring.gds \\
          <workdir>/vco_ring.spice --top vco_ring \\
          --lvs-sub GND_VCO --run-dir <rundir>
    """
    y_nets = [f"Y{i + 1}" for i in range(dev.STAGE_COUNT)]
    lines = [
        f"* Standalone LVS reference for {TOP_CELL} (issue #371).",
        "*",
        "* The 5-stage current-starved ring (vco.sch's XS1..XS5), chained",
        "* Y_i -> A_(i+1) with the Y5 -> A1 wraparound, expressed against",
        "* this block's own boundary nets. Every W/L traces to devices.py's",
        "* STAGE_FETS (itself read off design/netlist/vco.spice).",
        "*",
        "* Run LVS with --lvs-sub=GND_VCO (this block's own substrate net --",
        "* NOT layout/run_pv.py's own VSS default; see layout/README.md's",
        '* "substrate-net gotcha").',
        "",
        f".subckt {TOP_CELL} VBP VBN VDD_VCO GND_VCO {' '.join(y_nets)}",
    ]
    for i in range(dev.STAGE_COUNT):
        stage_num = i + 1
        a_net = y_nets[-1] if i == 0 else y_nets[i - 1]
        y_net = y_nets[i]
        net_map = {
            "A": a_net,
            "Y": y_net,
            "VDD": "VDD_VCO",
            "VSS": "GND_VCO",
            "VBP": "VBP",
            "VBN": "VBN",
            "NH": f"S{stage_num}_NH",
            "NT": f"S{stage_num}_NT",
        }
        for f in dev.STAGE_FETS:
            bulk = "VDD_VCO" if f.kind == "pfet" else "GND_VCO"

            def n(net: str, _map=net_map) -> str:
                return _map.get(net, net)

            lines.append(
                f"M_S{stage_num}_{f.name} {n(f.top_net)} {n(f.gate_net)} {n(f.bottom_net)} {bulk} "
                f"{f.kind}_03v3 W={f.drawn_w_um}u L={f.l_um}u"
            )
    lines += [".ends", ""]
    return "\n".join(lines)


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
