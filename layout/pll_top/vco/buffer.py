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
substrate ``p`` ring tied ``GND_VCO``, inner n-well tap bands tied
``VDD_VCO``) so it is provable on its own, exactly as ``ring.py``'s block is.
Merging the VCO's sub-blocks under one shared guard ring is integration work
for a later increment of issue #293.
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

    stage_ports: list[BufferStagePorts] = []
    for x0, st in zip(xs, dev.BUFFER_STAGES):
        # --- NMOS: source (GND_VCO) at the bottom, drain (this stage's
        # output) at the top, facing the routing channel. ---
        n_ports = prim.mosfet(canvas, st.nfet, x0, 0.0)
        # --- PMOS: drain at the bottom (facing the same channel), source
        # (VDD_VCO) at the top. ---
        p_ports = prim.mosfet(canvas, st.pfet, x0, pmos_y0)

        # --- output net: nfet drain <-> pfet drain, one vertical Metal1 run
        # across the NMOS/PMOS channel (stage.py's own "Y" bridge). ---
        out_x = (n_ports.top_pad[0] + n_ports.top_pad[2]) / 2.0
        prim.v_wire(canvas, out_x, n_ports.top_pad[3], p_ports.bottom_pad[1])
        canvas.pin(f"BUF{st.index}.{st.out_net}", *n_ports.top_pad)

        # --- input net: both gates, one vertical Metal1 run at the shared
        # gate-contact-tab x (both devices are left-aligned at x0). ---
        gate_x = (n_ports.gate_pad[0] + n_ports.gate_pad[2]) / 2.0
        prim.v_wire(canvas, gate_x, n_ports.gate_pad[3], p_ports.gate_pad[1])

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

    # --- VDD_VCO / GND_VCO rails: one Metal1 rectangle per net, drawn at
    # exactly a representative stage's own pad y0/y1 so the rail is a
    # superset of (not merely adjacent to) each stage's pad with no notch
    # shallower than M1.2a's 0.23 um -- see ring.py's iteration note. ---
    row_x0 = min(p.x0 for p in stage_ports)
    row_x1 = max(p.x1 for p in stage_ports)
    for net, pad_getter in (("VDD_VCO", lambda p: p.vdd_pad), ("GND_VCO", lambda p: p.gnd_pad)):
        for p in stage_ports:
            pad = pad_getter(p)
            canvas.rect("metal1", row_x0, pad[1], row_x1, pad[3])
        ref = pad_getter(stage_ports[0])
        canvas.pin(net, row_x0, ref[1], row_x0 + 1.0, ref[3])

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
