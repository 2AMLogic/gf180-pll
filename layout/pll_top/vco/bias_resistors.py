"""``vco_bias.sch``'s three ``ppolyf_u_3k`` poly resistors (``RCG``/``ROFF``/``RDEG``).

WHY THIS IS ITS OWN BLOCK, NOT PART OF A FULL V-TO-I CORE ASSEMBLY
--------------------------------------------------------------------
Issue #293's earlier increments (PR #305: the ring; PR #313: the band-select
mirror + output buffer) both named the same deferral boundary: the bias
generator's V-to-I core (``MP1``/``MP2``/``MN1``/``MN2``/``MSU1``-``MSU3``/
``MPR``/``MD1``/``MD2``/``MOFF``/``MVI``/``MSUM``, plus ``RCG``/``ROFF``/
``RDEG``) stayed undrawn because three of its elements are ``ppolyf_u_3k``
poly resistors and ``primitives.py`` had no generator for that device class.
This increment adds that generator (``primitives.poly_resistor()``) and
draws the three resistors it was missing -- but stops there, deliberately,
rather than also drawing the V-to-I core's dozen-odd transistors and their
own internal routing (the constant-gm core with its beta-multiplier startup
loop, the 2*Vgs reference stack, the offset branch, and the summing node) in
the same pass. That is real, independent scope on top of "does the new
primitive actually work" -- proving the primitive against the exact three
devices that motivated it is this increment's own coherent, independently
DRC-provable slice, per this issue's own established "a real, DRC-clean
sub-portion beats a placeholder for the full scope" convention (see
``ring.py``'s and ``mirror.py``'s module docstrings for the same call made
twice already). The V-to-I core's transistors landed next
(``vtoi_core.py``), and ``block.py`` has since wired this block to it -- and
to the ring, mirror and output buffer -- under one block-level guard ring.

WHY NO PER-RESISTOR SUBSTRATE TAP
-----------------------------------
See ``primitives.poly_resistor()``'s own docstring for the full reasoning:
the PDK's own pcell draws a local comp/pplus tap per resistor instance, but
this block instead relies entirely on its own dedicated guard ring (same
"provable standalone" convention ``ring.py``/``mirror.py``/``buffer.py``
already use). Unlike those three blocks (wide rows, PMOS+n-well involved),
this one is narrow and tall (``ROFF``/``RDEG`` are each 33 um long, but the
whole row of three resistors is under 10 um wide) -- so the guard ring's own
**left and right** bands, which run the block's full height, are what keeps
every point along even the longest resistor within
``DRC_TAP_PITCH_MAX_UM`` of a tap, the same way ``ring.py``'s/``mirror.py``'s
**top and bottom** bands do for their own wide-and-short rows. No PMOS or
n-well exists in this block at all (poly resistors sit directly in the
p-substrate), so the guard ring here is p-only -- no inner n-well tap band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices as dev
from . import primitives as prim

TOP_CELL = "vco_bias_resistors"

GND_NET = "GND_VCO"

RESISTOR_GAP_UM = 2.0  # comfortably above both PRES.2 (0.4 um, resistor-to-
# resistor isolation) and PRES.4 (0.6 um, resistor poly to unrelated poly2)
RING_WIDTH_UM = 1.2
OUTER_MARGIN_LEFT_UM = 3.0
OUTER_MARGIN_RIGHT_UM = 3.0
OUTER_MARGIN_BELOW_UM = 3.0
OUTER_MARGIN_ABOVE_UM = 3.0


def column_x0_um() -> tuple[float, ...]:
    """Pure-Python (no KLayout): each resistor's width-column left edge."""
    xs = []
    x = 0.0
    for r in dev.BIAS_RESISTORS:
        xs.append(x)
        x += r.w_um + RESISTOR_GAP_UM
    return tuple(xs)


def row_extent_um() -> tuple[float, float]:
    xs = column_x0_um()
    x1 = xs[-1] + dev.BIAS_RESISTORS[-1].w_um
    return (xs[0], x1)


def poly_y_extent_um() -> tuple[float, float]:
    """Pure-Python: the (y0, y1) every resistor's own poly2 footprint spans.

    Every resistor is bottom-aligned at ``y_bottom=0`` (see ``build()``), so
    ``y0`` is the same for all three; ``y1`` is set by the *longest*
    resistor (``ROFF``/``RDEG``, ``l_um=33``).
    """
    ext = prim.POLY_RES_EXT_UM
    y1 = max(r.l_um for r in dev.BIAS_RESISTORS) + ext
    return (-ext, y1)


def footprint_um() -> tuple:
    """Pure-Python (no KLayout) footprint, mirroring ``build()``'s own math."""
    row_x0, row_x1 = row_extent_um()
    poly_y0, poly_y1 = poly_y_extent_um()
    outer_x0 = row_x0 - OUTER_MARGIN_LEFT_UM
    outer_x1 = row_x1 + OUTER_MARGIN_RIGHT_UM
    outer_y0 = poly_y0 - OUTER_MARGIN_BELOW_UM
    outer_y1 = poly_y1 + OUTER_MARGIN_ABOVE_UM
    return (outer_x0, outer_y0, outer_x1, outer_y1)


def top_pad_center_um(res: dev.PolyResistor) -> tuple[float, float]:
    """Pure-Python (x, y) centre of ``res``'s own signal-terminal Metal1 pad.

    ``block.py`` needs this *before* any KLayout drawing happens: it chooses
    the whole resistor block's placement offset so that ``RCG``'s pad lands
    exactly on the V-to-I core's own ``NC`` Metal2 track, which turns a
    three-segment dogleg into a straight wire plus one via1. Mirrors
    ``primitives.poly_resistor()``'s own ``_end_pad()`` arithmetic; the tests
    check the two against each other, so a drift in either is a test failure
    rather than a silently-misplaced via.

    ``x`` is trivially the resistor's own column centre (its contact row is
    centred in the width). ``y`` reproduces ``_contact_positions()``'s
    single-contact fallback: the contact land between the ``PRES.7``
    clearance and the poly2 end is always narrower than one contact for a
    ``ppolyf_u_3k`` of this class, so the row degenerates to one centred
    contact -- asserted rather than assumed.
    """
    y_outer = res.l_um + prim.POLY_RES_CONTACT_TO_SAB_UM
    y_inner = res.l_um + prim.POLY_RES_EXT_UM - prim.CONTACT_ROW_MARGIN_UM
    span = (y_inner - prim.CONTACT_ROW_MARGIN_UM) - (y_outer + prim.CONTACT_ROW_MARGIN_UM)
    if span >= prim.CONTACT_SIZE_UM:
        raise NotImplementedError(
            "poly-resistor contact land is wide enough for a multi-contact row; "
            "this pure-Python mirror only covers the single-contact fallback"
        )
    y0 = dev.snap_um((y_outer + y_inner) / 2.0 - prim.CONTACT_SIZE_UM / 2.0)
    return (res.w_um / 2.0, y0 + prim.CONTACT_SIZE_UM / 2.0)


def max_tap_distance_um() -> float:
    """Worst-case in-plane distance from any resistor to the nearest guard-ring band.

    The guard ring's left/right bands run the block's full height, so the
    worst case is the *horizontal* midpoint between two resistors (or a
    resistor and the nearer side band) -- never a function of a resistor's
    own length, unlike ``ring.py``'s/``mirror.py``'s wide-row blocks.
    """
    row_x0, row_x1 = row_extent_um()
    outer_x0, _, outer_x1, _ = footprint_um()
    left_gap = row_x0 - outer_x0 - RING_WIDTH_UM
    right_gap = outer_x1 - RING_WIDTH_UM - row_x1
    inter_resistor_half_gap = RESISTOR_GAP_UM / 2.0
    return max(left_gap, right_gap, inter_resistor_half_gap)


@dataclass
class ResistorPorts:
    name: str
    bottom_pad: tuple  # GND_VCO terminal
    top_pad: tuple  # signal terminal (top_net)


@dataclass
class BiasResistorsResult:
    canvas: prim.Canvas
    ports: list = field(default_factory=list)
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)


def build(outdir: Path | None = None, canvas: prim.Canvas | None = None) -> BiasResistorsResult:
    """``canvas`` draws into a caller-supplied canvas -- see ``ring.build()``."""
    canvas = prim.Canvas(TOP_CELL) if canvas is None else canvas
    xs = column_x0_um()

    ports: list[ResistorPorts] = []
    for x0, res in zip(xs, dev.BIAS_RESISTORS):
        p = prim.poly_resistor(canvas, res, x0, 0.0)
        canvas.pin(res.top_net, *p.top_pad)
        ports.append(ResistorPorts(name=res.name, bottom_pad=p.bottom_pad, top_pad=p.top_pad))

    # --- GND_VCO rail: every resistor's own bottom_pad shares the identical
    # y-range (all three are bottom-aligned at y_bottom=0), so one Metal1
    # rectangle spanning the whole row's x-extent is a superset of (not
    # merely adjacent to) each pad with zero notch -- same construction
    # ring.py's/buffer.py's own VDD_VCO/GND_VCO rails use. ---
    row_x0, row_x1 = row_extent_um()
    ref_pad = ports[0].bottom_pad
    canvas.rect("metal1", row_x0, ref_pad[1], row_x1, ref_pad[3])

    # --- tie the rail down into the guard ring's own bottom band ---
    outer_x0, outer_y0, outer_x1, outer_y1 = footprint_um()
    rail_mid_x = (row_x0 + row_x1) / 2.0
    prim.v_wire(canvas, rail_mid_x, outer_y0 + RING_WIDTH_UM, ref_pad[1])
    canvas.pin(GND_NET, row_x0, ref_pad[1], row_x0 + 1.0, ref_pad[3])

    # --- guard ring: p-only (no PMOS/n-well in this block -- see module
    # docstring for why the left/right bands are what makes the tap-pitch
    # bound hold here, not top/bottom as in ring.py/mirror.py/buffer.py). ---
    prim.guard_ring(canvas, "p", outer_x0, outer_y0, outer_x1, outer_y1, RING_WIDTH_UM, GND_NET)

    footprint = (outer_x0, outer_y0, outer_x1, outer_y1)

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return BiasResistorsResult(canvas=canvas, ports=ports, footprint=footprint)


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
