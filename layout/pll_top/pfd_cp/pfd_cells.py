"""``pfdcp_inv_3v3`` / ``pfdcp_nand2_3v3`` as row-style cells (issue #300).

Device sizes are read directly off the schematics -- ``design/pfdcp_inv_3v3.sch``
(one ``pfet_03v3`` W=1.5u/L=0.3u + one ``nfet_03v3`` W=0.5u/L=0.3u) and
``design/pfdcp_nand2_3v3.sch`` (two parallel ``pfet_03v3`` W=1.5u/L=0.3u over
two series ``nfet_03v3`` W=1u/L=0.3u; the NMOS stack is deliberately widened
to 1u so the NAND's pull-down tracks the inverter's, per that schematic's own
note) -- not re-derived. ``layout/tests/test_pfd_layout.py`` re-checks both
tables against those files' stated W/L.

PLACEMENT IS PURE
-----------------
Every function here returns plain-Python placement records; nothing is drawn
and no y coordinate is resolved until ``draw_cell()`` is handed a
:class:`~pfd_cp.pfd.RowGeom`. That split is what lets the block's channel
router pack tracks (an x-only problem) *before* the routing band's height --
and therefore every y in the design -- is known, and it is what lets the
whole placement/mirror/no-overlap test suite run with no KLayout at all.

CELL INTERNAL ORDER (why these particular left/right terminal assignments)
-------------------------------------------------------------------------
Each cell is laid out so that **no two nets ever need the same x lane in the
routing band** -- the property ``rowgen.py``'s routing model relies on:

``inv`` (one column)::

      VDD rail  ────────────────────────
                 [VDD]  MP  [Y]              gate tab points down
      band            A│      Y│             two lanes: gate, drain
                 [VSS]  MN  [Y]              gate tab points up
      VSS rail  ────────────────────────

``nand2`` (two columns, MP1/MN1 then MP2/MN2)::

      VDD rail  ─────────────────────────────────────
                 [VDD] MP1 [Y]══[Y] MP2 [VDD]
      band          A│     Y│(top)      B│
                    Y│(bottom)
                 [Y]  MN1 [NI]══[NI] MN2 [VSS]
      VSS rail  ─────────────────────────────────────

The two ``══`` runs are local Metal1 wires drawn on the row centerline, in
the gap between the two devices' comp islands: the PMOS pair's shared drain
(``Y``) and the NMOS series node (``NI``). Drawing those two nets locally is
what keeps ``NI`` out of the routing band entirely and leaves ``Y`` with
exactly two lanes (``MP1``'s drain from above, ``MN1``'s drain from below) --
so the busiest lane in the cell still carries one net.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rowgen
from .rowgen import Fet, device_width_um, gate_cx, gate_pad_reach, left_pad_cx, right_pad_cx, sd_pad_reach

L_UM = 0.3  # every PFD leaf device: L=0.3u (both schematics)
W_PFET_UM = 1.5
W_NFET_INV_UM = 0.5
W_NFET_NAND_UM = 1.0

#: x offset from a NAND2's first column to its second. 2.6 um leaves a
#: 0.3 um comp gap (DF.3a_LV=0.28 min) and a 0.26 um Metal1 pad gap
#: (M1.2a=0.23 min) between the two columns -- the same in-cell pitch
#: ``lock_detector/primitives.py``'s own nand2 uses and proved clean.
NAND2_COLUMN_PITCH_UM = 2.6

#: Metal1 overlap a strap makes into the pad it lands on, so the two shapes
#: share real area rather than meeting on a bare edge.
PAD_BITE_UM = 0.2

INV_WIDTH_UM = device_width_um(L_UM)
NAND2_WIDTH_UM = NAND2_COLUMN_PITCH_UM + device_width_um(L_UM)


@dataclass(frozen=True)
class PlacedFet:
    fet: Fet
    x0: float
    side: str  # "p" (PMOS row) | "n" (NMOS row)


@dataclass(frozen=True)
class LocalWire:
    """A Metal1 run on a row centerline, joining two adjacent pads in one cell."""

    side: str
    x0: float
    x1: float


@dataclass(frozen=True)
class Port:
    """One net's Metal1 strap lane inside a cell.

    ``kind`` is ``"full"`` (the strap spans the whole band, tying a PMOS-row
    pad to the NMOS-row pad directly below it), ``"top"`` (it starts at a
    PMOS-row pad and reaches down to the net's track) or ``"bottom"`` (it
    starts at an NMOS-row pad and reaches up). ``off_lo``/``off_hi`` are the
    strap's start offsets from the NMOS/PMOS row centerlines.
    """

    net: str
    lane: float
    kind: str
    off_lo: float
    off_hi: float


@dataclass(frozen=True)
class Stub:
    """A short Metal1 run from a supply pad to that row's supply rail."""

    net: str
    lane: float
    side: str  # "up" (PMOS pad -> VDD rail) | "down" (NMOS pad -> VSS rail)
    reach: float  # distance from the row centerline to the pad's outer edge


@dataclass(frozen=True)
class CellInst:
    """One placed leaf-cell instance. All x are *local* (pre-mirror)."""

    name: str
    kind: str
    row: int
    x0: float
    width: float
    mirror: bool
    fets: tuple[PlacedFet, ...]
    wires: tuple[LocalWire, ...]
    ports: tuple[Port, ...]
    stubs: tuple[Stub, ...]
    #: schematic port name -> net, for checking the placement against
    #: ``design/*.sch`` (``layout/tests/test_pfd_layout.py``).
    roles: dict[str, str] = field(default_factory=dict)

    @property
    def x1(self) -> float:
        return self.x0 + self.width


def _gate_port(net: str, lane: float, w_n: float) -> Port:
    return Port(
        net=net,
        lane=lane,
        kind="full",
        off_lo=gate_pad_reach(w_n) - PAD_BITE_UM,
        off_hi=gate_pad_reach(W_PFET_UM) - PAD_BITE_UM,
    )


def inv(name: str, x0: float, row: int, a: str, y: str, *, mirror: bool = False) -> CellInst:
    """``pfdcp_inv_3v3``: one PMOS over one NMOS, gates and drains tied."""
    mp = Fet(f"{name}.MP", "pfet", W_PFET_UM, L_UM, g=a, left="VDD", right=y)
    mn = Fet(f"{name}.MN", "nfet", W_NFET_INV_UM, L_UM, g=a, left="VSS", right=y)
    ports = (
        _gate_port(a, gate_cx(x0, L_UM), W_NFET_INV_UM),
        Port(
            net=y,
            lane=right_pad_cx(x0, L_UM),
            kind="full",
            off_lo=sd_pad_reach(W_NFET_INV_UM) - PAD_BITE_UM,
            off_hi=sd_pad_reach(W_PFET_UM) - PAD_BITE_UM,
        ),
    )
    stubs = (
        Stub("VDD", left_pad_cx(x0), "up", sd_pad_reach(W_PFET_UM)),
        Stub("VSS", left_pad_cx(x0), "down", sd_pad_reach(W_NFET_INV_UM)),
    )
    return CellInst(
        name=name,
        kind="inv",
        row=row,
        x0=x0,
        width=INV_WIDTH_UM,
        mirror=mirror,
        fets=(PlacedFet(mp, x0, "p"), PlacedFet(mn, x0, "n")),
        wires=(),
        ports=ports,
        stubs=stubs,
        roles={"A": a, "Y": y, "VDD": "VDD", "VSS": "VSS"},
    )


def nand2(name: str, x0: float, row: int, a: str, b: str, y: str, *, mirror: bool = False) -> CellInst:
    """``pfdcp_nand2_3v3``: two parallel PMOS over two series NMOS."""
    c1 = x0
    c2 = x0 + NAND2_COLUMN_PITCH_UM
    ni = f"{name}.NI"

    mp1 = Fet(f"{name}.MP1", "pfet", W_PFET_UM, L_UM, g=a, left="VDD", right=y)
    mp2 = Fet(f"{name}.MP2", "pfet", W_PFET_UM, L_UM, g=b, left=y, right="VDD")
    mn1 = Fet(f"{name}.MN1", "nfet", W_NFET_NAND_UM, L_UM, g=a, left=y, right=ni)
    mn2 = Fet(f"{name}.MN2", "nfet", W_NFET_NAND_UM, L_UM, g=b, left=ni, right="VSS")

    wires = (
        LocalWire("p", right_pad_cx(c1, L_UM), left_pad_cx(c2)),  # Y across the PMOS pair
        LocalWire("n", right_pad_cx(c1, L_UM), left_pad_cx(c2)),  # NI across the NMOS series node
    )
    ports = (
        _gate_port(a, gate_cx(c1, L_UM), W_NFET_NAND_UM),
        _gate_port(b, gate_cx(c2, L_UM), W_NFET_NAND_UM),
        Port(
            net=y,
            lane=right_pad_cx(c1, L_UM),
            kind="top",
            off_lo=0.0,
            off_hi=sd_pad_reach(W_PFET_UM) - PAD_BITE_UM,
        ),
        Port(
            net=y,
            lane=left_pad_cx(c1),
            kind="bottom",
            off_lo=sd_pad_reach(W_NFET_NAND_UM) - PAD_BITE_UM,
            off_hi=0.0,
        ),
    )
    stubs = (
        Stub("VDD", left_pad_cx(c1), "up", sd_pad_reach(W_PFET_UM)),
        Stub("VDD", right_pad_cx(c2, L_UM), "up", sd_pad_reach(W_PFET_UM)),
        Stub("VSS", right_pad_cx(c2, L_UM), "down", sd_pad_reach(W_NFET_NAND_UM)),
    )
    return CellInst(
        name=name,
        kind="nand2",
        row=row,
        x0=x0,
        width=NAND2_WIDTH_UM,
        mirror=mirror,
        fets=(
            PlacedFet(mp1, c1, "p"),
            PlacedFet(mp2, c2, "p"),
            PlacedFet(mn1, c1, "n"),
            PlacedFet(mn2, c2, "n"),
        ),
        wires=wires,
        ports=ports,
        stubs=stubs,
        roles={"A": a, "B": b, "Y": y, "VDD": "VDD", "VSS": "VSS"},
    )


# --- mirroring -------------------------------------------------------------


def real_lane(cell: CellInst, lane: float, axis: float) -> float:
    return rowgen.mirror_x(axis, lane) if cell.mirror else rowgen._r(lane)


def real_span(cell: CellInst, axis: float) -> tuple[float, float]:
    if not cell.mirror:
        return (cell.x0, cell.x1)
    return (rowgen.mirror_x(axis, cell.x1), rowgen.mirror_x(axis, cell.x0))


def draw_cell(
    canvas: rowgen.Canvas, cell: CellInst, y_n: float, y_p: float, axis: float
) -> list[tuple[str, str, float, float, float, float]]:
    """Draw one placed cell's devices and local Metal1 wires.

    A mirrored cell is drawn from the *same* local coordinates through a
    :class:`rowgen.MirrorView`, so the DN chain is a literal reflection of
    the UP chain rather than a separately computed placement.

    Returns every Metal1 shape the cell contributes, tagged with the net it
    carries -- the input the block-level connectivity/short checks in
    ``layout/tests/test_pfd_layout.py`` run on.
    """
    view = rowgen.MirrorView(canvas, axis) if cell.mirror else canvas
    tagged: list[tuple[str, str, float, float, float, float]] = []

    def _box(net: str, pad: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = pad
        if cell.mirror:
            x0, x1 = rowgen.mirror_x(axis, x1), rowgen.mirror_x(axis, x0)
        # Round to the same grid ``Canvas.rect`` snaps to, so a mirrored
        # cell's tagged boxes compare equal to their reflected twins.
        tagged.append((net, "metal1", rowgen._r(x0), rowgen._r(y0), rowgen._r(x1), rowgen._r(y1)))

    for placed in cell.fets:
        y_center = y_p if placed.side == "p" else y_n
        ports = rowgen.mosfet(view, placed.fet, placed.x0, y_center, tab_up=(placed.side == "n"))
        _box(placed.fet.left, ports.left_pad)
        _box(placed.fet.right, ports.right_pad)
        _box(placed.fet.g, ports.gate_pad)
    for wire in cell.wires:
        y = y_p if wire.side == "p" else y_n
        rowgen.h_wire(view, wire.x0, wire.x1, y)
        half = rowgen.METAL1_WIRE_WIDTH_UM / 2.0
        net = _local_wire_net(cell, wire)
        _box(net, (wire.x0, y - half, wire.x1, y + half))
    return tagged


def _local_wire_net(cell: CellInst, wire: LocalWire) -> str:
    """Which net a cell's own row-centerline Metal1 run carries.

    Only ``nand2`` has any: the PMOS pair's shared drain (``Y``, the cell's
    third port) on the ``p`` side, and the NMOS series node (``NI``, internal
    to the cell) on the ``n`` side.
    """
    if cell.kind != "nand2":
        raise AssertionError(f"{cell.name}: unexpected local wire in a {cell.kind}")
    if wire.side == "p":
        return next(f.fet.right for f in cell.fets if f.fet.name.endswith(".MP1"))
    return next(f.fet.right for f in cell.fets if f.fet.name.endswith(".MN1"))


def comp_boxes(cell: CellInst, y_n: float, y_p: float, axis: float, side: str) -> list[tuple[float, float, float, float]]:
    """Comp bounding boxes for one side of a cell, in real (post-mirror) x."""
    boxes = []
    for placed in cell.fets:
        if placed.side != side:
            continue
        y_center = y_p if side == "p" else y_n
        w = placed.fet.w_um
        x0, x1 = placed.x0, placed.x0 + device_width_um(placed.fet.l_um)
        if cell.mirror:
            x0, x1 = rowgen.mirror_x(axis, x1), rowgen.mirror_x(axis, x0)
        boxes.append((x0, y_center - w / 2.0, x1, y_center + w / 2.0))
    return boxes
