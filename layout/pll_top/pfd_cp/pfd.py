"""Mirror-symmetric transistor-level layout of ``design/pfd.sch`` (issue #300).

WHAT THIS BUILDS
----------------
All 47 leaf-cell instances of the tri-state PFD -- 40 ``pfdcp_inv_3v3`` +
7 ``pfdcp_nand2_3v3``, i.e. **108 transistors** -- as real geometry on the
gf180mcuD device layers, in two standard-cell-style row pairs:

* **Row 0** carries the two matched branches and the reset NAND:

      [ UP branch: xed_ref + xinv_sr + xlat_ref ] [xnand_rst] [ DN branch ]
                                                       ^
                                                  mirror axis

  The DN branch (``xed_fb``/``xinv_sf``/``xlat_fb``) is drawn from the *same*
  local coordinates as the UP branch through a :class:`rowgen.MirrorView`, so
  the two are literal reflections about ``x = axis`` by construction, not by
  arithmetic that could drift. ``xnand_rst`` straddles the axis: placing a
  ``pfdcp_nand2_3v3`` centred on the axis puts its ``A`` and ``B`` gate lanes
  at ``axis -/+ 1.3 um``, so ``UP`` (from the left latch into ``A``) and
  ``DN`` (from the right latch into ``B``) are exact mirror images too.

* **Row 1** carries the shared reset path -- ``xinv_r0``, the 24-inverter
  delay chain ``xd1..xd24``, and ``xinv_rb`` -- placed once, centred on the
  same axis, above row 0.

WHY THE TWO BRANCHES ARE MIRRORED RATHER THAN REPEATED
------------------------------------------------------
``layout/floorplan/PLL-FLOORPLAN.md`` section 4: "the two ``srlatch`` +
``edgedet`` chains (UP and DN paths) are laid out as **mirror-symmetric
twins** about a central axis, not independently placed ... the layout should
not introduce an asymmetry (e.g. one path routed longer than the other) that
the schematic-level number doesn't already include." The mismatch budget
this protects is term 1 of that section's table (DC UP/DN charge-pump
mismatch, the term with the least margin at 8.479 % of a +/-12 % line).

MATCHED FAN-OUT OF THE SHARED RESET (and the one deliberately unmatched run)
----------------------------------------------------------------------------
``RB`` leaves ``xinv_rb`` in row 1, runs along a row-1 Metal2 bus to
``x = axis`` exactly, and drops to row 0 on a **Metal3 link placed on the
axis itself**. From that link the row-0 ``RB`` bus fans out left and right to
the two latches' ``xn2.A`` gate lanes, which are mirror images -- so the two
fan-out arms are equal by construction, and the test suite asserts it on the
drawn geometry (``test_rb_fanout_is_matched``).

The run *feeding* that link -- ``xinv_rb``'s output to the axis, and
symmetrically ``NRST`` from ``xnand_rst`` up to ``xinv_r0`` at the far left
of row 1 -- is **not** matched to anything and does not need to be: it is
common to both branches, so it adds a constant to the reset delay rather
than a difference between UP and DN. That is the whole distinction
PLL-FLOORPLAN.md section 4 draws. Its cost is a few tens of femtoseconds of
extra RC on a reset path deliberately built from 24 inverter delays
(``design/pfd.sch``'s own note), i.e. nothing.

SCOPE
-----
The PFD only. The charge pump, the dump buffer (#301/#302) and the assembly
of this block into ``pfd_cp``/the floorplan skeleton (#303) are out of scope
-- this module writes one standalone, standalone-DRC-clean ``pfd`` GDS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import pfd_cells as cells
from . import rowgen
from .rowgen import (
    BAND_MARGIN_UM,
    METAL2_TRACK_PITCH_UM,
    METAL2_WIRE_WIDTH_UM,
    NWELL_TO_SUBSTRATE_GAP_UM,
    STRAP_TO_TRACK_MARGIN_UM,
    TAP_STRIP_H_UM,
    TAP_TO_ROW_GAP_UM,
    Canvas,
    _r,
)

TOP_CELL = "pfd"

#: x gap between two adjacent cells' comp islands within a row. 0.5 um is
#: above DF.3a_LV's 0.28 comp-space minimum and, more tightly, small
#: enough that two neighbouring cells' own IMPLANT_MARGIN_UM (0.3) halos
#: overlap by 0.1 um -- so a row's nplus (and pplus) merges into a single
#: polygon instead of leaving 0.4 um-class gaps that NP.2/PP.2 (min. nplus
#: / pplus spacing, 0.4 um) would reject.
CELL_GAP_UM = 0.5
#: Extra clearance either side of the axis-straddling ``xnand_rst``. Wide
#: enough (1.2 um -> 0.6 um implant gap) that the reset NAND's implant
#: island stays a separate, NP.2/PP.2-legal polygon from each branch's.
CENTER_GAP_UM = 1.2
#: Periodic well/substrate tap spacing along each supply rail. DF.13_LV /
#: DF.14_LV cap the distance from any PMOS/NMOS to its nearest tap at 20 um;
#: 10 um pitch keeps the worst case at ~5 um in x.
TAP_PITCH_UM = 10.0
#: Rail overhang past the outermost device of the widest row.
RAIL_MARGIN_UM = 1.5
#: Inset, from each end of the supply rails, of the Metal3 stitches that tie
#: row 0's rails to row 1's. Both are placed at both signs, so the two branch
#: regions stay identical; both land in the rails' own overhang past the
#: outermost device, so a stitch never runs over a signal strap; and they are
#: 1.0 um apart, which is (1.0 - METAL3_WIRE_WIDTH) = 0.56 um of Metal3 space,
#: past M3.2a's 0.28 um minimum.
SUPPLY_LINK_INSET_UM = {"VSS": 0.6, "VDD": 1.6}

#: The axis is the origin of this block's coordinate system.
AXIS_X = 0.0

#: Distance from a row's NMOS centerline down to the bottom edge of that
#: row's substrate-tap comp -- what the next row up has to clear (by
#: ``NWELL_TO_SUBSTRATE_GAP_UM``) past the row below's nwell.
_ROW_TAP_COMP_DROP_UM = 0.5 + TAP_TO_ROW_GAP_UM + TAP_STRIP_H_UM

# --- Nets, transcribed from design/pfd.sch + design/edgedet.sch +
# design/srlatch.sch. Branch-local nets are prefixed with the instance path
# the schematic gives them, so the UP and DN copies stay distinct. ---


def _branch_nets(tag: str) -> dict[str, str]:
    """Net names for one ``edgedet`` + ``inv`` + ``srlatch`` branch.

    ``tag`` is ``"ref"`` (the UP branch, driven by ``REF``) or ``"fb"`` (the
    DN branch, driven by ``FB``) -- exactly ``pfd.sch``'s own ``xed_ref``/
    ``xed_fb``, ``xinv_sr``/``xinv_sf``, ``xlat_ref``/``xlat_fb`` split.
    """
    up = tag == "ref"
    return {
        "X": "REF" if up else "FB",
        "D1": f"xed_{tag}.D1",
        "D2": f"xed_{tag}.D2",
        "D3": f"xed_{tag}.D3",
        "D4": f"xed_{tag}.D4",
        "D5": f"xed_{tag}.D5",
        "NN": f"xed_{tag}.NN",
        "PULSE": "PR" if up else "PF",
        "SB": "SBR" if up else "SBF",
        "Q": "UP" if up else "DN",
        "QB": "UPB" if up else "DNB",
    }


UP_NETS = _branch_nets("ref")
DN_NETS = _branch_nets("fb")
#: UP-branch net -> its DN-branch counterpart. Every entry is a pair the
#: router must place on one shared Metal2 track, because a horizontal bus is
#: only invariant under reflection about a vertical axis if both halves sit
#: at the same y.
MIRROR_NET_PAIRS = {UP_NETS[k]: DN_NETS[k] for k in UP_NETS}


@dataclass(frozen=True)
class RowGeom:
    """Resolved y geometry of one row pair."""

    y_n: float  # NMOS row centerline
    y_p: float  # PMOS row centerline
    y_vss_rail: float
    y_vdd_rail: float
    tracks: tuple[float, ...]

    @property
    def y_bottom(self) -> float:
        return self.y_vss_rail - TAP_STRIP_H_UM / 2.0 - rowgen.IMPLANT_MARGIN_UM

    @property
    def y_top(self) -> float:
        return self.y_vdd_rail + TAP_STRIP_H_UM / 2.0 + rowgen.NWELL_MARGIN_UM


def row_geometry(y_n: float, n_tracks: int) -> RowGeom:
    """Stack a row pair upward from ``y_n``, sized for ``n_tracks`` tracks.

    The routing band lives between the two rows' gate-contact tabs: its floor
    clears the tallest NMOS tab pad (``w=1u``, the NAND2 pull-down) and its
    ceiling clears the PMOS tab pad (``w=1.5u``), both by
    ``BAND_MARGIN_UM``.
    """
    n_tracks = max(n_tracks, 1)
    band_lo = y_n + rowgen.gate_pad_reach(cells.W_NFET_NAND_UM) + BAND_MARGIN_UM
    tracks = tuple(_r(band_lo + i * METAL2_TRACK_PITCH_UM) for i in range(n_tracks))
    y_p = _r(tracks[-1] + BAND_MARGIN_UM + rowgen.gate_pad_reach(cells.W_PFET_UM))
    y_vdd = _r(y_p + cells.W_PFET_UM / 2.0 + TAP_TO_ROW_GAP_UM + TAP_STRIP_H_UM / 2.0)
    y_vss = _r(y_n - cells.W_NFET_NAND_UM / 2.0 - TAP_TO_ROW_GAP_UM - TAP_STRIP_H_UM / 2.0)
    return RowGeom(y_n=_r(y_n), y_p=y_p, y_vss_rail=y_vss, y_vdd_rail=y_vdd, tracks=tracks)


# ---------------------------------------------------------------------------
# Placement (pure)
# ---------------------------------------------------------------------------


@dataclass
class Placement:
    """Every cell instance, plus the derived net/lane tables. No y, no drawing."""

    cells: list[cells.CellInst] = field(default_factory=list)
    #: (row, net) -> ordered list of (real lane x, port)
    lanes: dict[tuple[int, str], list[tuple[float, cells.Port]]] = field(default_factory=dict)
    #: (row, net) -> real lane x of a Metal3 row-to-row link, if any
    links: dict[tuple[int, str], float] = field(default_factory=dict)
    #: net -> (real lane x, side, reach, row) supply stubs
    stubs: list[tuple[str, float, str, float, int]] = field(default_factory=list)

    def add(self, cell: cells.CellInst) -> cells.CellInst:
        self.cells.append(cell)
        for port in cell.ports:
            lane = cells.real_lane(cell, port.lane, AXIS_X)
            self.lanes.setdefault((cell.row, port.net), []).append((lane, port))
        for stub in cell.stubs:
            lane = cells.real_lane(cell, stub.lane, AXIS_X)
            self.stubs.append((stub.net, lane, stub.side, stub.reach, cell.row))
        return cell

    def row_span(self, row: int) -> tuple[float, float]:
        spans = [cells.real_span(c, AXIS_X) for c in self.cells if c.row == row]
        return (min(s[0] for s in spans), max(s[1] for s in spans))


def _place_branch(place: Placement, tag: str, x_right_edge: float, *, mirror: bool) -> None:
    """One ``edgedet`` + ``xinv_s*`` + ``srlatch`` branch, right-edge anchored.

    Cell order left to right is signal order, so the latch -- the end that
    talks to ``xnand_rst`` and to the shared ``RB`` -- lands nearest the
    axis. ``x_right_edge`` is the local (pre-mirror) right edge; the DN copy
    passes the identical value with ``mirror=True``.
    """
    n = _branch_nets(tag)
    prefix = f"xed_{tag}"
    # (cell kind, name, ports...) in left-to-right order
    seq: list[tuple[str, str, tuple]] = [
        ("inv", f"{prefix}.xi1", (n["X"], n["D1"])),
        ("inv", f"{prefix}.xi2", (n["D1"], n["D2"])),
        ("inv", f"{prefix}.xi3", (n["D2"], n["D3"])),
        ("inv", f"{prefix}.xi4", (n["D3"], n["D4"])),
        ("inv", f"{prefix}.xi5", (n["D4"], n["D5"])),
        ("nand2", f"{prefix}.xnd", (n["X"], n["D5"], n["NN"])),
        ("inv", f"{prefix}.xi6", (n["NN"], n["PULSE"])),
        ("inv", "xinv_sr" if tag == "ref" else "xinv_sf", (n["PULSE"], n["SB"])),
        ("nand2", f"xlat_{tag}.xn1", (n["SB"], n["QB"], n["Q"])),
        ("nand2", f"xlat_{tag}.xn2", ("RB", n["Q"], n["QB"])),
    ]
    widths = [cells.INV_WIDTH_UM if k == "inv" else cells.NAND2_WIDTH_UM for k, _, _ in seq]
    total = sum(widths) + CELL_GAP_UM * (len(seq) - 1)
    x = x_right_edge - total
    for (kind, name, ports), width in zip(seq, widths):
        if kind == "inv":
            place.add(cells.inv(name, x, 0, ports[0], ports[1], mirror=mirror))
        else:
            place.add(cells.nand2(name, x, 0, ports[0], ports[1], ports[2], mirror=mirror))
        x += width + CELL_GAP_UM


def _place_delay_row(place: Placement) -> None:
    """``xinv_r0`` + ``xd1..xd24`` + ``xinv_rb``: the shared reset path, row 1.

    26 inverters in signal order, centred on the axis. ``xinv_r0`` (fed by
    ``NRST`` from row 0) is leftmost and ``xinv_rb`` (whose ``RB`` output
    goes back down to both latches) rightmost, so neither of the two
    row-to-row links has to reach across the other.
    """
    names = ["xinv_r0"] + [f"xd{i}" for i in range(1, 25)] + ["xinv_rb"]
    nets = ["NRST", "RST_RAW"] + [f"RD{i}" for i in range(1, 24)] + ["RST_DLY", "RB"]
    assert len(names) == 26 and len(nets) == 27
    total = 26 * cells.INV_WIDTH_UM + 25 * CELL_GAP_UM
    x = AXIS_X - total / 2.0
    for i, name in enumerate(names):
        place.add(cells.inv(name, x, 1, nets[i], nets[i + 1], mirror=False))
        x += cells.INV_WIDTH_UM + CELL_GAP_UM


def build_placement() -> Placement:
    """Place all 47 leaf cells and derive the net/lane tables."""
    place = Placement()

    # xnand_rst straddles the axis: a nand2 centred on the axis puts its A/B
    # gate lanes at axis -/+ NAND2_COLUMN_PITCH/2, which is what makes the
    # UP and DN routes into it mirror images.
    rst_x0 = AXIS_X - cells.NAND2_WIDTH_UM / 2.0
    place.add(cells.nand2("xnand_rst", rst_x0, 0, "UP", "DN", "NRST"))

    branch_right_edge = rst_x0 - CENTER_GAP_UM
    _place_branch(place, "ref", branch_right_edge, mirror=False)
    _place_branch(place, "fb", branch_right_edge, mirror=True)

    _place_delay_row(place)

    # --- row-to-row Metal3 links --------------------------------------------
    # RB drops to row 0 *on the axis*, so its fan-out to the two latches is
    # symmetric (see the module docstring). NRST climbs to row 1 one NAND2
    # column-pitch away, inside xnand_rst's own footprint -- clear of the RB
    # link in x, and clear of both branch regions, so it cannot perturb the
    # mirror symmetry the two branches are tested for.
    place.links[(0, "RB")] = AXIS_X
    place.links[(1, "RB")] = AXIS_X
    nrst_link_x = _r(AXIS_X - cells.NAND2_COLUMN_PITCH_UM / 2.0)
    place.links[(0, "NRST")] = nrst_link_x
    place.links[(1, "NRST")] = nrst_link_x
    return place


def net_interval(place: Placement, row: int, net: str) -> tuple[float, float] | None:
    """x extent of a net's Metal2 bus in one row, or ``None`` if it needs none."""
    lanes = [lane for lane, _ in place.lanes.get((row, net), [])]
    link = place.links.get((row, net))
    if link is not None:
        lanes = lanes + [link]
    if len(lanes) < 2:
        return None
    return (min(lanes), max(lanes))


def assign_tracks(place: Placement, row: int) -> dict[str, int]:
    """Channel-pack every net that needs a bus in ``row`` onto Metal2 tracks.

    Mirror-paired nets are packed as a single key, so the UP and DN copies of
    a net always land on the same track -- the condition for their buses to
    be reflections of each other. Packing order is by leftmost edge, then
    name, so the result is deterministic and (because every pair's interval
    set is itself mirror-symmetric) so is the whole channel.
    """
    keys: dict[str, list[str]] = {}
    for (r, net) in place.lanes:
        if r != row:
            continue
        partner = MIRROR_NET_PAIRS.get(net)
        if partner is not None:
            key = net  # UP-branch name is the pair's canonical key
        elif net in MIRROR_NET_PAIRS.values():
            key = next(k for k, v in MIRROR_NET_PAIRS.items() if v == net)
        else:
            key = net
        keys.setdefault(key, [])
        if net not in keys[key]:
            keys[key].append(net)

    entries: list[tuple[str, list[tuple[float, float]]]] = []
    for key, nets in keys.items():
        spans = [s for n in nets if (s := net_interval(place, row, n)) is not None]
        if spans:
            entries.append((key, spans))
    entries.sort(key=lambda e: (min(s[0] for s in e[1]), e[0]))

    packed = rowgen.pack_tracks(entries)
    per_net: dict[str, int] = {}
    for key, nets in keys.items():
        if key in packed:
            for n in nets:
                per_net[n] = packed[key]
    return per_net


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


@dataclass
class PfdLayout:
    canvas: Canvas
    placement: Placement
    rows: tuple[RowGeom, ...]
    tracks: tuple[dict[str, int], ...]
    #: (net, layer, x0, y0, x1, y1) for every *conductor* shape in the block --
    #: device Metal1 pads, rails, straps, buses and links alike. This is the
    #: model ``layout/tests/test_pfd_layout.py`` runs its connectivity and
    #: no-short checks on: a DRC deck cannot see a short, because two
    #: overlapping shapes on one layer merge into a single legal polygon.
    conductors: list[tuple[str, str, float, float, float, float]] = field(default_factory=list)
    #: (net, "via1"|"via2", x, y) -- where a net changes layer.
    vias: list[tuple[str, str, float, float]] = field(default_factory=list)

    def footprint(self) -> tuple[float, float, float, float]:
        return self.canvas.bbox()

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def _record(layout: PfdLayout, net: str, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
    layout.conductors.append((net, layer, _r(min(x0, x1)), _r(min(y0, y1)), _r(max(x0, x1)), _r(max(y0, y1))))


def _via(layout: PfdLayout, net: str, kind: str, x: float, y: float) -> None:
    """Draw a via + both enclosing metal pads, and record all three."""
    half = rowgen.VIA_PAD_UM / 2.0
    if kind == "via1":
        rowgen.via1_landing(layout.canvas, x, y)
        upper, lower = "metal2", "metal1"
    else:
        rowgen.via2_landing(layout.canvas, x, y)
        upper, lower = "metal3", "metal2"
    layout.vias.append((net, kind, _r(x), _r(y)))
    _record(layout, net, lower, x - half, y - half, x + half, y + half)
    _record(layout, net, upper, x - half, y - half, x + half, y + half)


def _draw_rails(layout: PfdLayout, row: int, geom: RowGeom, x0: float, x1: float) -> list[tuple]:
    """The row's VDD/VSS Metal1 rails plus their periodic taps. Returns ntap boxes."""
    canvas = layout.canvas
    half = TAP_STRIP_H_UM / 2.0 + rowgen.METAL1_PAD_MARGIN_UM
    canvas.rect("metal1", x0, geom.y_vdd_rail - half, x1, geom.y_vdd_rail + half)
    canvas.rect("metal1", x0, geom.y_vss_rail - half, x1, geom.y_vss_rail + half)
    _record(layout, "VDD", "metal1", x0, geom.y_vdd_rail - half, x1, geom.y_vdd_rail + half)
    _record(layout, "VSS", "metal1", x0, geom.y_vss_rail - half, x1, geom.y_vss_rail + half)
    canvas.label("metal1_label", "VDD", (x0 + x1) / 2.0, geom.y_vdd_rail)
    canvas.label("metal1_label", "VSS", (x0 + x1) / 2.0, geom.y_vss_rail)

    ntap_boxes = []
    n = int((x1 - x0) / 2.0 // TAP_PITCH_UM)
    xs = [_r(AXIS_X + k * TAP_PITCH_UM) for k in range(-n, n + 1)]
    for x in xs:
        if not (x0 + 1.0 <= x <= x1 - 1.0):
            continue
        ntap_boxes.append(rowgen.tap_strip(canvas, "n", x, geom.y_vdd_rail))
        rowgen.tap_strip(canvas, "p", x, geom.y_vss_rail)
        tap_half = rowgen.TAP_STRIP_LEN_UM / 2.0 + rowgen.METAL1_PAD_MARGIN_UM
        _record(layout, "VDD", "metal1", x - tap_half, geom.y_vdd_rail - half, x + tap_half, geom.y_vdd_rail + half)
        _record(layout, "VSS", "metal1", x - tap_half, geom.y_vss_rail - half, x + tap_half, geom.y_vss_rail + half)
    return ntap_boxes


def _draw_stubs(layout: PfdLayout, geom: RowGeom, row: int) -> None:
    """Every supply pad's short Metal1 run out to its rail."""
    half = TAP_STRIP_H_UM / 2.0 + rowgen.METAL1_PAD_MARGIN_UM
    for net, lane, side, reach, r in layout.placement.stubs:
        if r != row:
            continue
        if side == "up":
            y_a = geom.y_p + reach - cells.PAD_BITE_UM
            y_b = geom.y_vdd_rail - half + cells.PAD_BITE_UM
        else:
            y_a = geom.y_vss_rail + half - cells.PAD_BITE_UM
            y_b = geom.y_n - reach + cells.PAD_BITE_UM
        rowgen.v_wire(layout.canvas, lane, min(y_a, y_b), max(y_a, y_b))
        _record(
            layout,
            net,
            "metal1",
            lane - rowgen.METAL1_WIRE_WIDTH_UM / 2.0,
            min(y_a, y_b),
            lane + rowgen.METAL1_WIRE_WIDTH_UM / 2.0,
            max(y_a, y_b),
        )


def _draw_net(layout: PfdLayout, row: int, geom: RowGeom, net: str, track_index: int | None) -> None:
    """Straps, via landings and the Metal2 bus for one net in one row."""
    place = layout.placement
    entries = place.lanes.get((row, net), [])
    link_x = place.links.get((row, net))
    by_lane: dict[float, list[cells.Port]] = {}
    for lane, port in entries:
        by_lane.setdefault(lane, []).append(port)

    track_y = geom.tracks[track_index] if track_index is not None else None
    canvas = layout.canvas
    half_w = rowgen.METAL1_WIRE_WIDTH_UM / 2.0

    for lane, ports in sorted(by_lane.items()):
        kinds = {p.kind for p in ports}
        if "full" in kinds:
            port = next(p for p in ports if p.kind == "full")
            y_lo = geom.y_n + port.off_lo
            y_hi = geom.y_p - port.off_hi
        elif "bottom" in kinds:
            port = next(p for p in ports if p.kind == "bottom")
            assert track_y is not None, f"{net}: bottom-only lane with no bus"
            y_lo = geom.y_n + port.off_lo
            y_hi = track_y + STRAP_TO_TRACK_MARGIN_UM
        else:
            port = next(p for p in ports if p.kind == "top")
            assert track_y is not None, f"{net}: top-only lane with no bus"
            y_lo = track_y - STRAP_TO_TRACK_MARGIN_UM
            y_hi = geom.y_p - port.off_hi
        rowgen.v_wire(canvas, lane, y_lo, y_hi)
        _record(layout, net, "metal1", lane - half_w, y_lo, lane + half_w, y_hi)

    if track_y is None:
        return

    xs = sorted(by_lane)
    for lane in xs:
        _via(layout, net, "via1", lane, track_y)
    lo, hi = min(xs), max(xs)
    if link_x is not None:
        lo, hi = min(lo, link_x), max(hi, link_x)
    pad = METAL2_WIRE_WIDTH_UM / 2.0
    canvas.rect("metal2", lo - pad, track_y - pad, hi + pad, track_y + pad)
    _record(layout, net, "metal2", lo - pad, track_y - pad, hi + pad, track_y + pad)
    canvas.label("metal2", net, (lo + hi) / 2.0, track_y)


def _draw_link(layout: PfdLayout, net: str, x: float, y_a: float, y_b: float) -> None:
    half = rowgen.METAL3_WIRE_WIDTH_UM / 2.0
    layout.canvas.rect("metal3", x - half, min(y_a, y_b), x + half, max(y_a, y_b))
    _record(layout, net, "metal3", x - half, min(y_a, y_b), x + half, max(y_a, y_b))
    _via(layout, net, "via2", x, y_a)
    _via(layout, net, "via2", x, y_b)


def _draw_links(layout: PfdLayout, rail_hi: float) -> None:
    """The Metal3 row-to-row links (``RB``, ``NRST``) and the supply stitches."""
    place = layout.placement
    for net in ("RB", "NRST"):
        x = place.links[(0, net)]
        y_a = layout.rows[0].tracks[layout.tracks[0][net]]
        y_b = layout.rows[1].tracks[layout.tracks[1][net]]
        _draw_link(layout, net, x, y_a, y_b)

    # VDD/VSS row-to-row stitches, placed symmetrically about the axis so the
    # two branch regions see identical geometry, and in x lanes clear of the
    # two signal links above. These land on Metal1 rails rather than Metal2
    # buses, so they need a via1 as well as the link's own via2.
    for sign in (-1.0, 1.0):
        for net, y_a, y_b, dx in (
            ("VDD", layout.rows[0].y_vdd_rail, layout.rows[1].y_vdd_rail, rail_hi - SUPPLY_LINK_INSET_UM["VDD"]),
            ("VSS", layout.rows[0].y_vss_rail, layout.rows[1].y_vss_rail, rail_hi - SUPPLY_LINK_INSET_UM["VSS"]),
        ):
            x = _r(AXIS_X + sign * dx)
            _via(layout, net, "via1", x, y_a)
            _via(layout, net, "via1", x, y_b)
            _draw_link(layout, net, x, y_a, y_b)


def build(y_row_base: float = 0.0) -> PfdLayout:
    """Place, route and draw the whole PFD block."""
    place = build_placement()
    tracks = tuple(assign_tracks(place, row) for row in (0, 1))
    n_tracks = tuple(max(t.values(), default=0) + 1 for t in tracks)

    row0 = row_geometry(y_row_base, n_tracks[0])
    row1 = row_geometry(row0.y_top + NWELL_TO_SUBSTRATE_GAP_UM + _ROW_TAP_COMP_DROP_UM, n_tracks[1])
    canvas = Canvas(TOP_CELL)
    layout = PfdLayout(canvas=canvas, placement=place, rows=(row0, row1), tracks=tracks)

    x_lo, x_hi = place.row_span(0)
    rail_lo = _r(min(x_lo, -x_hi) - RAIL_MARGIN_UM)
    rail_hi = _r(-rail_lo)

    for row, geom in enumerate(layout.rows):
        for cell in place.cells:
            if cell.row == row:
                layout.conductors.extend(cells.draw_cell(canvas, cell, geom.y_n, geom.y_p, AXIS_X))
        ntaps = _draw_rails(layout, row, geom, rail_lo, rail_hi)
        _draw_stubs(layout, geom, row)
        pcomps = [
            box
            for cell in place.cells
            if cell.row == row
            for box in cells.comp_boxes(cell, geom.y_n, geom.y_p, AXIS_X, "p")
        ]
        rowgen.nwell_over(canvas, pcomps + ntaps)
        for (r, net) in sorted(place.lanes):
            if r == row:
                _draw_net(layout, row, geom, net, tracks[row].get(net))

    _draw_links(layout, rail_hi)
    _draw_pin_labels(layout)
    return layout


def _draw_pin_labels(layout: PfdLayout) -> None:
    """Metal1 pin labels (34/10) for the block's own boundary nets."""
    geom = layout.rows[0]
    for net in ("REF", "FB", "UP", "DN"):
        entries = layout.placement.lanes.get((0, net))
        if not entries:
            continue
        lane, port = entries[0]
        y = geom.y_n + port.off_lo + 0.3
        layout.canvas.label("metal1_label", net, lane, y)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def footprint_um() -> tuple[float, float]:
    x0, y0, x1, y1 = build().footprint()
    return (_r(x1 - x0), _r(y1 - y0))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[2] / "evidence" / "pfd-layout" / "work"
    parser.add_argument("--outdir", default=str(default))
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    layout = build()
    gds = outdir / f"{TOP_CELL}.gds"
    layout.write_gds(gds)
    x0, y0, x1, y1 = layout.footprint()
    n_inv = sum(1 for c in layout.placement.cells if c.kind == "inv")
    n_nand = sum(1 for c in layout.placement.cells if c.kind == "nand2")
    print(f"wrote {gds}")
    print(f"instances : {n_inv} pfdcp_inv_3v3 + {n_nand} pfdcp_nand2_3v3 = {n_inv + n_nand}")
    print(f"devices   : {n_inv * 2 + n_nand * 4}")
    print(f"footprint : {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    print(f"tracks    : row0={len(layout.rows[0].tracks)}  row1={len(layout.rows[1].tracks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
