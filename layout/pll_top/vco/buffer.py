"""The VCO's 3-stage tapered output buffer (``vco.sch``: Y5 -> NB1 -> NB2 -> CLK).

Three CMOS inverters, ``devices.BUFFER_STAGES``, drawn with exactly the
construction ``ring.py``/``stage.py`` already proved DRC-clean: every
transistor is its own comp/poly/implant island (``primitives.mosfet()``),
current flows vertically, the NMOS band sits at the bottom in the substrate
and the PMOS band above it inside one shared n-well, and the two are wired
to each other only through Metal1.

Placement is not free choice -- ``layout/floorplan/PLL-FLOORPLAN.md`` section 1
fixes it: *"The output buffer's 3-stage taper (1.25/0.5 -> 3.75/1.5 ->
11.25/4.5 um) sits at the VCO-block boundary, closest to the ``CLK`` pin, so
the largest, fastest-switching stage (which sinks the most crowbar/switching
current) is physically nearest the pin it drives and farthest from the ring's
own starved internal nodes."* So the three stages are placed left to right
smallest-first, the ring-facing ``Y5`` input pin is on the **left** edge and
the ``CLK`` output pin is on the **right** edge -- i.e. the 11.25/4.5 um
stage is the one abutting ``CLK`` and the 1.25/0.5 um stage is the one
abutting the ring. ``max_stage_distance_to_clk_pin_um()`` /
``layout/tests/test_vco_layout.py`` assert that ordering rather than trusting
the tuple's own order.

Standalone-DRC scope: this block draws its own dedicated guard ring (outer
substrate ``p`` ring tied ``GND_VCO``, inner n-well tap ring tied
``VDD_VCO``) so it is provable on its own, exactly as ``ring.py``'s block is.
Merging the VCO's sub-blocks under one shared guard ring is integration work
for a later increment of issue #293.

SUPPLY DISTRIBUTION (issue #372, root-caused in
``layout/evidence/vco-layout/PROOF-368-rootcause.md``)
-------------------------------------------------------------------------
Two rules this module now holds itself to, both of them things the first
version of this generator got wrong in a way no DRC run could report (two
Metal1 shapes that *touch* merge into one polygon before any spacing rule
runs, so a short is never a violation):

1. **A supply rail is drawn in the clear channel outside its own device
   row's pads, never across them.** ``primitives.mosfet()``'s gate-contact
   pad and its adjacent terminal pad overlap in *y* by ``0.26 - l/2`` um
   (0.12 um for these 0.28 um-long inverter fets) -- harmless per device,
   because the gate tab sits at a different *x* than the terminal pad, but
   fatal the moment a rail is stretched across the whole row at the
   terminal pad's own y: it then reaches every *other* stage's gate tab
   too. Each rail here is a full-row-width band in the empty channel
   *beyond* its row's pads (below the NMOS ``GND_VCO`` pads, above the PMOS
   ``VDD_VCO`` pads), and ``build()`` asserts at draw time that every gate
   pad clears it by at least ``devices.DRC_METAL1_MIN_SPACE_UM``.

2. **Every supply rail is deliberately strapped to the ring that biases the
   same net.** Each rail band runs from its own row's pads all the way into
   the corresponding ring's Metal1 (the outer p guard ring for ``GND_VCO``,
   the inner n-well tap ring for ``VDD_VCO``), overlapping it by a real
   ``primitives.METAL1_PAD_MARGIN_UM`` of area rather than meeting it at a
   coincident edge -- the same deliberate device-to-ring tie ``mirror.py``
   draws per fet with its own ``rail_stub()``. Before this, the rails, the
   tap bands and the guard ring were three separately-labelled Metal1
   islands that were never connected by any drawn metal; they only ever
   *looked* connected because of the accidental short in (1).

The NMOS-to-PMOS channel is crossed on **Metal2**, not Metal1, for the same
class of reason: the inner n-well tap ring's bottom band lies directly
across that channel, so a Metal1 drain/gate bridge would short every stage's
own internal node to ``VDD_VCO``. ``_channel_hop()`` lands a ``via1_stack()``
inside each of the two Metal1 pads it joins and jumps the band on Metal2,
which has no spacing relationship with Metal1 at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim

TOP_CELL = "vco_out_buffer"

# Column gap: comp right edge of one stage to comp left edge of the next.
# Has to clear the next column's gate contact tab (which sticks ~1.12 um to
# the left of its own comp edge, see primitives.mosfet()) plus a Metal1
# routing gap for the inter-stage NB1/NB2 dogleg.
COL_GAP_UM = 3.0

# Guard-ring / routing-channel geometry (um), same roles as ring.py's.
OUTER_MARGIN_LEFT_UM = 3.0
OUTER_MARGIN_RIGHT_UM = 3.0
OUTER_MARGIN_BELOW_UM = 2.5
OUTER_MARGIN_ABOVE_NWELL_UM = 2.5
RING_WIDTH_UM = 1.2
TAP_GAP_UM = 0.6
TAP_RING_WIDTH_UM = 0.6

CLK_STUB_UM = 1.5  # Metal1 run from the last stage's output pad to the CLK pin


def _box_gap_um(a: tuple, b: tuple) -> float:
    """Euclidean gap between two axis-aligned boxes (0.0 if they touch/overlap).

    Euclidean rather than projected, because that is the metric the gf180mcu
    DRC deck's own ``metal1.space()`` check uses by default -- so a number
    from this helper is directly comparable against
    ``devices.DRC_METAL1_MIN_SPACE_UM`` (M1.2a).
    """
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


def _channel_hop(canvas: prim.Canvas, pad_lo: tuple, pad_hi: tuple, y_jog: float) -> None:
    """Bridge two Metal1 pads across the NMOS/PMOS channel on Metal2.

    The inner n-well tap ring's bottom band (``VDD_VCO``) spans the whole
    row *inside* this channel, so the plain Metal1 riser this used to be
    shorted every stage's own drain and gate node to ``VDD_VCO`` -- see the
    module docstring and ``PROOF-368-rootcause.md``. Metal2 has no spacing
    relationship with Metal1, so the band is simply jumped over.

    Each ``via1_stack()`` is centred on its own pad, whose 0.46 x 0.46 um
    minimum footprint (one contact plus ``METAL1_PAD_MARGIN_UM`` on each
    side) strictly contains the 0.44 um square via landing pad -- so this
    adds **no** new Metal1 geometry at all, only via1/Metal2. The two pads
    are rarely at the same x (an inverter's pfet is wider than its nfet, and
    both are left-aligned), hence the Metal2 jog at ``y_jog`` rather than one
    straight column.
    """
    x_lo, y_lo = (pad_lo[0] + pad_lo[2]) / 2.0, (pad_lo[1] + pad_lo[3]) / 2.0
    x_hi, y_hi = (pad_hi[0] + pad_hi[2]) / 2.0, (pad_hi[1] + pad_hi[3]) / 2.0
    prim.via1_stack(canvas, x_lo, y_lo)
    prim.via1_stack(canvas, x_hi, y_hi)
    if abs(x_hi - x_lo) < 1e-9:
        prim.m2_route(canvas, [(x_lo, y_lo), (x_lo, y_hi)])
    else:
        prim.m2_route(
            canvas,
            [(x_lo, y_lo), (x_lo, y_jog), (x_hi, y_jog), (x_hi, y_hi)],
        )


@dataclass
class BufferStagePorts:
    index: int
    x0: float
    x1: float
    out_pad: tuple  # the nfet drain pad (this stage's own output landing pad)
    gate_pad_bottom: tuple  # nfet gate pad -- the inter-stage route's landing edge
    gate_pad_top: tuple  # pfet gate pad
    vdd_pad: tuple
    gnd_pad: tuple
    pmos_x0: float
    pmos_x1: float
    pmos_y0: float
    pmos_y1: float


@dataclass
class BufferResult:
    canvas: prim.Canvas
    stage_ports: list = field(default_factory=list)
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    nwell_box: tuple = (0.0, 0.0, 0.0, 0.0)
    clk_pin: tuple = (0.0, 0.0, 0.0, 0.0)
    # The two full-row-width supply bands actually drawn, and the worst-case
    # Euclidean Metal1 gap between either of them and any stage's own gate
    # pad -- the number issue #372's short was a *negative* value of. Carried
    # on the result (rather than re-derived in a test) so the assertion runs
    # against what ``build()`` drew, not against a second copy of its math.
    rail_bands: dict = field(default_factory=dict)
    rail_gate_clearance_um: float = 0.0


def column_x0_um() -> tuple[float, ...]:
    """Pure-Python (no KLayout): each stage's comp left edge, x0 of stage 1 = 0."""
    xs = []
    x = 0.0
    for st in dev.BUFFER_STAGES:
        xs.append(x)
        x += st.max_w_um + COL_GAP_UM
    return tuple(xs)


def pmos_y_range() -> tuple[float, float]:
    """Pure-Python: the shared PMOS band's (y0, y1), column-local.

    Single source of truth for the nfet-(gap)-pfet vertical stack math, so
    ``footprint_um()`` and the tap-pitch tests never re-derive it separately
    from what ``build()`` actually draws.
    """
    sd = prim.SD_OVERHANG_UM
    nfet_h = 2 * sd + dev.BUFFER_STAGES[0].nfet.l_um
    pfet_h = 2 * sd + dev.BUFFER_STAGES[0].pfet.l_um
    y0 = nfet_h + prim.NWELL_TO_NMOS_GAP_UM
    return (y0, y0 + pfet_h)


def max_pmos_tap_distance_um() -> float:
    """Worst-case pfet-to-nearest-n-well-tap distance (DF.13_MV/DF.14_MV)."""
    y0, y1 = pmos_y_range()
    return (y1 - y0) / 2.0 + TAP_GAP_UM


def max_nmos_tap_distance_um() -> float:
    """Worst-case nfet-to-nearest-substrate-tap (outer p-ring) distance."""
    sd = prim.SD_OVERHANG_UM
    nfet_h = 2 * sd + dev.BUFFER_STAGES[0].nfet.l_um
    return nfet_h + OUTER_MARGIN_BELOW_UM


def stage_center_x_um() -> tuple[float, ...]:
    xs = column_x0_um()
    return tuple(x + st.max_w_um / 2.0 for x, st in zip(xs, dev.BUFFER_STAGES))


def build(outdir: Path | None = None, canvas: prim.Canvas | None = None) -> BufferResult:
    """``canvas`` draws into a caller-supplied canvas -- see ``ring.build()``."""
    canvas = prim.Canvas(TOP_CELL) if canvas is None else canvas
    xs = column_x0_um()
    pmos_y0, _ = pmos_y_range()

    # Metal2 jog height for the drain/gate bridges: mid-channel, between the
    # NMOS band's top pads and the PMOS band's bottom pads. Nothing else in
    # this block is on Metal2, so one shared y is enough -- the jogs are
    # column-local and the stage pitch keeps them far apart in x.
    nfet_h = 2 * prim.SD_OVERHANG_UM + dev.BUFFER_STAGES[0].nfet.l_um
    channel_jog_y = dev.snap_um((nfet_h + pmos_y0) / 2.0)

    stage_ports: list[BufferStagePorts] = []
    for x0, st in zip(xs, dev.BUFFER_STAGES):
        # --- NMOS: source (GND_VCO) at the bottom, drain (this stage's
        # output) at the top, facing the routing channel. ---
        n_ports = prim.mosfet(canvas, st.nfet, x0, 0.0)
        # --- PMOS: drain at the bottom (facing the same channel), source
        # (VDD_VCO) at the top. ---
        p_ports = prim.mosfet(canvas, st.pfet, x0, pmos_y0)

        # --- output net: nfet drain <-> pfet drain, hopped across the
        # channel on Metal2 (see _channel_hop() -- the inner n-well tap
        # ring's bottom band lies right across this channel on Metal1). ---
        _channel_hop(canvas, n_ports.top_pad, p_ports.bottom_pad, channel_jog_y)
        # Labelled with the schematic's own net name (``NB1``/``NB2``), not a
        # ``BUF<i>.``-prefixed alias: unlike ring.py's per-stage ``S<i>.Y``,
        # these are top-level ``vco.sch`` nets, so the prefix invented a name
        # that no reference netlist has (see devices.py's own note on
        # BUFFER_STAGES). The last stage's output is ``CLK`` itself and is
        # already labelled at the end of its own output stub below -- a second
        # label for it here would put two different strings on one net, which
        # is the one thing an LVS deck reads labels *for*.
        if st.out_net != dev.BUFFER_OUT_NET:
            canvas.pin(st.out_net, *n_ports.top_pad)

        # --- input net: both gates, hopped the same way at the shared
        # gate-contact-tab x (both devices are left-aligned at x0, so this
        # one needs no jog). ---
        _channel_hop(canvas, n_ports.gate_pad, p_ports.gate_pad, channel_jog_y)

        stage_ports.append(
            BufferStagePorts(
                index=st.index,
                x0=x0,
                x1=x0 + st.max_w_um,
                out_pad=n_ports.top_pad,
                gate_pad_bottom=n_ports.gate_pad,
                gate_pad_top=p_ports.gate_pad,
                vdd_pad=p_ports.top_pad,
                gnd_pad=n_ports.bottom_pad,
                pmos_x0=x0,
                pmos_x1=x0 + st.pfet.w_um,
                pmos_y0=p_ports.y0,
                pmos_y1=p_ports.y3,
            )
        )

    # --- inter-stage routing: NB1 (stage 1 out -> stage 2 in), NB2 (stage 2
    # out -> stage 3 in), through the same NMOS/PMOS channel ring.py routes
    # its Y_i -> A_(i+1) hops in. ---
    gap_mid_y = (stage_ports[0].out_pad[3] + stage_ports[0].gate_pad_top[1]) / 2.0
    for src, dst in zip(stage_ports, stage_ports[1:]):
        prim.route_pads(canvas, src.out_pad, dst.gate_pad_bottom, gap_mid_y)

    # --- shared n-well over every stage's pfet, with real clearance for the
    # inner n-well tap bands to sit in (same construction as ring.py). ---
    pmos_x0 = min(p.pmos_x0 for p in stage_ports)
    pmos_x1 = max(p.pmos_x1 for p in stage_ports)
    band_y0 = min(p.pmos_y0 for p in stage_ports)
    band_y1 = max(p.pmos_y1 for p in stage_ports)
    tap_outer = (
        pmos_x0 - TAP_GAP_UM - TAP_RING_WIDTH_UM,
        band_y0 - TAP_GAP_UM - TAP_RING_WIDTH_UM,
        pmos_x1 + TAP_GAP_UM + TAP_RING_WIDTH_UM,
        band_y1 + TAP_GAP_UM + TAP_RING_WIDTH_UM,
    )
    nwell_box = (
        tap_outer[0] - prim.NWELL_MARGIN_UM,
        tap_outer[1] - prim.NWELL_MARGIN_UM,
        tap_outer[2] + prim.NWELL_MARGIN_UM,
        tap_outer[3] + prim.NWELL_MARGIN_UM,
    )
    canvas.rect("nwell", *nwell_box)

    row_x0 = min(p.x0 for p in stage_ports)
    row_x1 = max(p.x1 for p in stage_ports)

    # --- Y5 input pin (left edge, ring-facing) and CLK output pin (right
    # edge, buffer-facing) -- PLL-FLOORPLAN.md section 1's placement rule. ---
    canvas.pin(dev.BUFFER_IN_NET, *stage_ports[0].gate_pad_bottom)

    last = stage_ports[-1]
    clk_y = (last.out_pad[1] + last.out_pad[3]) / 2.0
    clk_x1 = last.out_pad[2] + CLK_STUB_UM
    prim.h_wire(canvas, last.out_pad[0], clk_x1, clk_y, width=last.out_pad[3] - last.out_pad[1])
    clk_pin = (clk_x1 - 0.6, last.out_pad[1], clk_x1, last.out_pad[3])
    canvas.pin(dev.BUFFER_OUT_NET, *clk_pin)

    # --- guard ring: outer p (GND_VCO) around everything, inner n-well tap
    # bands (VDD_VCO) top and bottom of the shared n-well. Top+bottom bands
    # only, for the same reason ring.py gives: the well is a long thin
    # horizontal band with the pfets packed across its full width, and
    # top+bottom already put every pfet well inside the 15 um tap bound. ---
    tab_x0 = min(p.gate_pad_bottom[0] for p in stage_ports)
    outer_x0 = min(nwell_box[0], tab_x0) - OUTER_MARGIN_LEFT_UM
    outer_x1 = max(nwell_box[2], row_x1, clk_x1) + OUTER_MARGIN_RIGHT_UM
    outer_y0 = stage_ports[0].gnd_pad[1] - OUTER_MARGIN_BELOW_UM
    outer_y1 = nwell_box[3] + OUTER_MARGIN_ABOVE_NWELL_UM
    prim.guard_ring(canvas, "p", outer_x0, outer_y0, outer_x1, outer_y1, RING_WIDTH_UM, "GND_VCO")

    prim.tap_strip(canvas, "n", tap_outer[0], tap_outer[3] - TAP_RING_WIDTH_UM, tap_outer[2], tap_outer[3], "VDD_VCO")
    prim.tap_strip(canvas, "n", tap_outer[0], tap_outer[1], tap_outer[2], tap_outer[1] + TAP_RING_WIDTH_UM, "VDD_VCO")

    # ...and a plain Metal1 strap down the right-hand edge of the well tying
    # those two bands together (issue #372). Without it the *bottom* band is
    # a Metal1 island of its own: it sits inside the NMOS/PMOS routing
    # channel, so nothing else on Metal1 may legally touch it, and the only
    # reason it ever looked connected was the short this issue removes.
    #
    # Metal1, not a third ``tap_strip()``: a real comp band here would land
    # on the last stage's own gate poly, whose endcap runs POLY_ENDCAP_UM
    # past the widest pfet's comp (to x = pmos_x1 + 0.65, i.e. *into*
    # tap_outer's right column). Drawn as comp that is a parasitic channel
    # -- DF.2a_LV (x2), CO.7 and NP.12, four violations the deck reported on
    # the first attempt at this. Metal1 crossing field poly has no such
    # rule, and this
    # band's job is purely electrical: the well taps themselves are already
    # drawn top and bottom. The left-hand edge is not available for the same
    # strap at all -- stage 1's gate-contact tabs and their Metal1 pads
    # occupy exactly that column, i.e. the Y5 input node.
    canvas.rect(
        "metal1",
        tap_outer[2] - TAP_RING_WIDTH_UM,
        tap_outer[1] + TAP_RING_WIDTH_UM,
        tap_outer[2],
        tap_outer[3] - TAP_RING_WIDTH_UM,
    )

    # --- VDD_VCO / GND_VCO rails + their deliberate straps to this block's
    # own rings (issue #372; root cause in PROOF-368-rootcause.md).
    #
    # Each rail is ONE full-row-width Metal1 band living in the empty channel
    # *outside* its own device row's supply pads, running from those pads all
    # the way into the ring that biases the same net:
    #
    #   GND_VCO: [gnd_pad y0] down to the outer p ring's own comp edge, which
    #            is METAL1_PAD_MARGIN_UM *inside* that ring's Metal1 pad.
    #   VDD_VCO: [vdd_pad y1] up to the n-well tap ring's top band comp edge,
    #            likewise inside its Metal1 pad.
    #
    # Overlapping the ring pad by real area (not meeting it at a coincident
    # edge) is deliberate: a butt joint is one grid-snap away from being no
    # joint at all. This band therefore does two jobs at once -- it is the
    # inter-stage rail AND the device-to-ring strap mirror.py draws per fet
    # with rail_stub(). Drawing it in the clear channel instead of across the
    # pads' own y is what keeps it off every other stage's gate pad; the
    # assertion below is the regression gate on that, since a Metal1 short is
    # structurally invisible to DRC (two touching shapes merge into one
    # polygon before any spacing rule runs). ---
    rail_bands = {
        "GND_VCO": (
            row_x0,
            outer_y0 + RING_WIDTH_UM,
            row_x1,
            min(p.gnd_pad[1] for p in stage_ports),
        ),
        "VDD_VCO": (
            row_x0,
            max(p.vdd_pad[3] for p in stage_ports),
            row_x1,
            tap_outer[3] - TAP_RING_WIDTH_UM,
        ),
    }
    gate_pads = [p.gate_pad_bottom for p in stage_ports] + [p.gate_pad_top for p in stage_ports]
    rail_gate_clearance_um = min(
        _box_gap_um(band, pad) for band in rail_bands.values() for pad in gate_pads
    )
    if rail_gate_clearance_um < dev.DRC_METAL1_MIN_SPACE_UM:
        raise ValueError(
            f"supply rail to gate-pad Metal1 clearance {rail_gate_clearance_um:.3f} um "
            f"< M1.2a's {dev.DRC_METAL1_MIN_SPACE_UM} um -- this is the issue #368/#372 "
            "short re-introduced (and DRC cannot report it: the two shapes merge)"
        )
    for net, band in rail_bands.items():
        canvas.rect("metal1", *band)
        canvas.pin(net, band[0], band[1], band[0] + 1.0, band[3])

    footprint = (outer_x0, outer_y0, outer_x1, outer_y1)

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return BufferResult(
        canvas=canvas,
        stage_ports=stage_ports,
        footprint=footprint,
        nwell_box=nwell_box,
        clk_pin=clk_pin,
        rail_bands=rail_bands,
        rail_gate_clearance_um=rail_gate_clearance_um,
    )


def footprint_um() -> tuple:
    """Pure-Python (no KLayout) footprint, mirroring ``build()``'s own math."""
    xs = column_x0_um()
    pmos_y0, pmos_y1 = pmos_y_range()
    pmos_x0 = xs[0]
    pmos_x1 = max(x + st.pfet.w_um for x, st in zip(xs, dev.BUFFER_STAGES))
    row_x1 = max(x + st.max_w_um for x, st in zip(xs, dev.BUFFER_STAGES))

    tap_margin = TAP_GAP_UM + TAP_RING_WIDTH_UM
    nwell_box = (
        pmos_x0 - tap_margin - prim.NWELL_MARGIN_UM,
        pmos_y0 - tap_margin - prim.NWELL_MARGIN_UM,
        pmos_x1 + tap_margin + prim.NWELL_MARGIN_UM,
        pmos_y1 + tap_margin + prim.NWELL_MARGIN_UM,
    )
    tab_x0 = -(
        prim.POLY_ENDCAP_UM - prim.GATE_TAB_OVERLAP_UM + prim.GATE_TAB_W_UM + prim.METAL1_PAD_MARGIN_UM
    )
    # The last stage's own output pad ends at its comp right edge + the pad
    # margin; the CLK stub then runs CLK_STUB_UM further right.
    clk_x1 = xs[-1] + dev.BUFFER_STAGES[-1].nfet.w_um + prim.METAL1_PAD_MARGIN_UM + CLK_STUB_UM

    outer_x0 = min(nwell_box[0], tab_x0) - OUTER_MARGIN_LEFT_UM
    outer_x1 = max(nwell_box[2], row_x1, clk_x1) + OUTER_MARGIN_RIGHT_UM
    # The bottom (GND_VCO) pad's own lower edge: the contact row is inset
    # CONTACT_ROW_MARGIN_UM from the comp edge, then grown METAL1_PAD_MARGIN_UM.
    gnd_pad_y0 = prim.CONTACT_ROW_MARGIN_UM - prim.METAL1_PAD_MARGIN_UM
    outer_y0 = gnd_pad_y0 - OUTER_MARGIN_BELOW_UM
    outer_y1 = nwell_box[3] + OUTER_MARGIN_ABOVE_NWELL_UM
    return (outer_x0, outer_y0, outer_x1, outer_y1)


def reference_netlist() -> str:
    """Standalone LVS reference for :data:`TOP_CELL` (``vco_out_buffer``).

    ``block.py``'s own :func:`~block.reference_netlist` is the *assembled*
    block's reference; this one exists so this generator is provable on its
    own, for the same reason it draws its own guard ring: a block-level LVS
    mismatch cannot tell you *which* sub-block's geometry is wrong, and
    issue #368's short took a full root-cause investigation precisely
    because no sub-block had an LVS testbench of its own.

    Device lines use the same node order, model names and ``W=``/``L=``
    spelling ``block.py``'s reference does (gf180mcu's own
    ``SubcircuitModelsReader`` reads those parameter names specifically),
    and ``drawn_w_um`` rather than the schematic ``w_um`` -- identical for
    every buffer fet (none is folded), but stated the same way so the two
    references cannot drift apart in convention.

    Run it (from the repo root, with the PDK/KLayout environment
    ``layout/run_pv.py check-env`` reports)::

        python3 -m layout.pll_top.vco.buffer --outdir <workdir>
        python3 -c "from layout.pll_top.vco import buffer; \\
          open('<workdir>/vco_out_buffer.spice','w').write(buffer.reference_netlist())"
        python3 layout/run_pv.py lvs <workdir>/vco_out_buffer.gds \\
          <workdir>/vco_out_buffer.spice --top vco_out_buffer \\
          --lvs-sub GND_VCO --run-dir <rundir>
    """
    lines = [
        f"* Standalone LVS reference for {TOP_CELL} (issue #372).",
        "*",
        "* vco.sch's XMBP1..XMBN3 output-buffer taper, expressed against this",
        "* block's own boundary nets. Every W/L traces to devices.py's",
        "* BUFFER_STAGES (itself read off design/netlist/vco.spice).",
        "*",
        "* Run LVS with --lvs-sub=GND_VCO (this block's own substrate net --",
        "* NOT layout/run_pv.py's own VSS default; see layout/README.md's",
        '* "substrate-net gotcha").',
        "",
        f".subckt {TOP_CELL} {dev.BUFFER_IN_NET} {dev.BUFFER_OUT_NET} VDD_VCO GND_VCO",
    ]
    for st in dev.BUFFER_STAGES:
        for f in (st.pfet, st.nfet):
            bulk = "VDD_VCO" if f.kind == "pfet" else "GND_VCO"
            lines.append(
                f"M_{f.name} {f.top_net} {f.gate_net} {f.bottom_net} {bulk} "
                f"{f.kind}_03v3 W={f.drawn_w_um}u L={f.l_um}u"
            )
    lines += [".ends", ""]
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parents[2] / "evidence" / "vco-layout" / "work"),
    )
    args = parser.parse_args()
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {args.outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
