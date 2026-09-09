"""``div23_cell`` -- the divide-by-2/3 composite macro every ``divider_chain``
top-level instance (Part 5, not built here) places six times, identically
(issue #309, Part 4 of #295's device-layout methodology proof).

WHAT THIS BUILDS
-----------------
All 8 sub-cell instances of ``design/div23_cell.sch`` -- 1x ``nand3_3v3``
(``XN3``), 2x ``nand2_3v3`` (``XN2Q``, ``XN2M``), 2x ``inv_3v3`` (``XIQ``,
``XIM``), 2x ``dff_tg_3v3`` (``XFQ``, ``XFMO``), 1x ``inv2x_3v3``
(``XICKO``) -- 60 transistors total, wired exactly per
``design/netlist/div23_cell.spice``'s own ``div23_cell`` subckt::

    XN3   MODIN P    MODOUT SB  VDD VSS nand3_3v3
    XN2Q  QB    SB   DQN        VDD VSS nand2_3v3
    XIQ   DQN   DQ            VDD VSS inv_3v3
    XFQ   DQ    CKIN Q      QB VDD VSS dff_tg_3v3
    XICKO QB    CKOUT           VDD VSS inv2x_3v3
    XN2M  MODIN Q    NMO       VDD VSS nand2_3v3
    XIM   NMO   DMO            VDD VSS inv_3v3
    XFMO  DMO   CKIN MODOUT MOB VDD VSS dff_tg_3v3

WHY A COMPOSITE MACRO, NOT 8 SEPARATE GDS FILES / GDS-LEVEL PLACEMENT
-----------------------------------------------------------------------
Same rationale as ``dff_tg_3v3.py`` (issue #308): every net here except each
instance's own supply pins fans out *across* instances (``QB`` alone reaches
``XN2Q``, ``XICKO`` and both flops' own ``QB``/``Q`` naming is per-instance),
outside what any one leaf cell's own local net resolver can wire. So this
module places every one of the 8 instances' own devices -- flattening
``dff_tg_3v3``'s own 10-instance internal structure too, rather than
instancing its already-built GDS -- as bare columns in one shared ``Canvas``
and resolves every net itself, composite-wide, with the same
``devgen.route_net()``/``devgen.NetTracks`` Metal2/3 fabric ``dff_tg_3v3.py``
already proved out. This is flat macro-composition, not GDS-level
``CellInstArray`` placement of 8 already-built leaf/composite cells -- see
``dff_tg_3v3.py``'s own module docstring and ``layout/pll_top/lock_detector/``
for the style precedent this generalizes.

ONE FRAME FOR EVERY COLUMN: THE ROW-CELL BASELINES, NOT draw_column()'S OWN
------------------------------------------------------------------------------
``dff_tg_3v3.py`` drew its 10 columns with ``devgen.draw_column()`` starting
every column at ``y0=0.0`` -- correct there because every one of its columns
is exactly one nfet then one pfet (``inv_3v3``/``tgate_3v3``'s own device
tables), so "start the whole column's device list at y=0" and "put the
nfet at a fixed baseline, the pfet at a fixed baseline" are the same thing.

This composite also includes ``nand3_3v3``/``nand2_3v3``/``inv2x_3v3``
instances, whose own device tables are not always "one nfet then one pfet in
that order" -- ``nand3_3v3``'s column 0 is three series nfets *then* one
pfet, and its columns 1/2 are a single pfet each with **no** nfet below it.
Naively feeding ``col.pulldown + col.pullup`` to ``draw_column()`` would
stack a lone pullup-only column's single pfet starting at ``y=0`` -- the
*nfet* baseline -- physically colliding with every neighbouring column's own
nfet row instead of sitting in the pfet band above it.

So every column here is drawn with its own pulldown branch (if any) starting
at :data:`devgen.ROW_PD_Y0` and its own pullup branch (if any) starting at
:data:`devgen.ROW_PU_Y0` -- the *same* two fixed baselines
``devgen.build_row_cell()`` already uses and already proved DRC-clean for
exactly this family's tallest branch (``nand3_3v3``'s three-high series
pull-down, which is what sizes ``ROW_PU_Y0``'s own clearance -- see that
constant's docstring in ``devgen.py``). This module does **not** call
``build_row_cell()`` itself (that function draws its own per-cell Metal1
strap/Metal2 track routing and rails, sized for one *standalone* cell) --
only its two baseline constants are reused, exactly as ``inv2x_3v3.py``
already reuses them for its own single-column case. Every ``dff_tg_3v3``
sub-instance's own ``inv_3v3``/``tgate_3v3`` columns are drawn the same way
(split into a one-device pulldown branch + a one-device pullup branch),
so the *entire* composite -- all 30 columns across all 8 instances -- shares
one nwell band and one periodic tap-pair convention, not two incompatible
frames glued together.

NET-COLLISION FIX, GENERALIZED: ONE SHARED REFERENCE X PER ROLE
----------------------------------------------------------------------
``dff_tg_3v3.py``'s own ``_TOP_PAD_OFFSET_UM``/``_PFET_GATE_OFFSET_UM`` fixed
exactly the collision its own columns could have: at most 2 distinct nets
ever landing at the same natural x (a device's own top vs. bottom pad, or a
``tgate_3v3`` pass-device pair's two independent gate pads) -- see
``devgen.offset_pad_x()``'s own docstring for the concrete LVS-merged-node
failure this class of bug caused there.

``nand3_3v3``'s three-high series pulldown branch introduces a case that
2-way scheme does not cover: ``mosfet()`` places every device's own gate pad
at the same x *regardless of that device's y position in the stack* (the gate
poly sits at a fixed offset left of the shared column ``x0``, independent of
height) -- so a 3-series branch's three independent gate nets (``A``, ``B``,
``C``) all land at the *same* natural gate-pad x, not just 2. And every
column's own top/bottom ("channel") terminal pads span *two* natural x
values, not one -- the nfet branch's own comp-width-driven centre and the
pfet branch's own (generally different) one -- so a first attempt at this
module bucketed strictly by each pad's own unmodified natural x and offset
distinct nets within each such bucket independently. That is *not* enough:
two *different* buckets (the nfet-side and pfet-side channel centres) are
often less than one :data:`NET_OFFSET_STEP_UM` apart on their own (e.g.
``tgate_3v3``'s own 1 um nfet / 2.5 um pfet gives centres only 0.75 um
apart), so a net whose own bucket-relative offset happens to point *toward*
the other bucket can still land within a fraction of a micron of a
different net's own similarly-inward-pointing offset from the neighbouring
bucket -- concretely observed on this module's own first attempt: two
different nets' Metal3 risers only 0.05 um apart, a real M3.2a violation
(the same class of failure ``devgen.offset_pad_x()``'s own docstring
describes for a single device's own top/bottom pads, just one level up:
*inter*-bucket rather than *intra*-bucket).

The fix used here: group every pad in a column by its **role** --
``"gate"`` or ``"channel"`` (every top/bottom S/D pad, from *either* branch)
-- not by its own raw natural x. Within a role, pick *one* shared reference
x, and route every pad belonging to a given net to the *same absolute*
target x (``reference + net's own offset``), independent of which physical
device that pad happens to sit on. Two pads of the *same* net landing at the
exact same x regardless of source device is the harmless case this
package's own composite fabric already documents ("two risers for the same
net at the same x is not a problem" -- ``devgen.py``'s "Composite-macro
routing fabric" section); two pads of *different* nets in the *same* role
are now guaranteed at least :data:`NET_OFFSET_STEP_UM` apart by
construction, because they resolve to the same two absolute target values
regardless of which bucket their own *natural* pad happened to start in --
eliminating the inter-bucket drift the per-natural-x bucketing above could
not rule out.

That reference x is itself a **fixed** anchor per role
(:data:`GATE_REF_DX_UM`/:data:`CHANNEL_REF_DX_UM`, both relative to a
column's own ``x0``), not each role's own natural pad mean -- a first
attempt anchored "gate" at its own natural pad centre (identical for every
device in a column already, so this seemed harmless) and only "channel" at a
fixed anchor; that resolved the failure above but introduced a second,
related one -- see :data:`GATE_REF_DX_UM`'s own docstring for the concrete
follow-up collision (the "gate" role's own worst-case reach creeping back
towards a *different* role's always-present natural geometry) and why both
roles need a fixed anchor, not just one.

REFERENCE NETLIST
------------------
:func:`reference_netlist` is hand-written and independently stated (same
discipline ``inv_3v3.py``/``dff_tg_3v3.py`` document), fully flattened to 60
individual ``M`` device lines rather than 8 ``X`` instance calls -- matching
this module's own flat (non-hierarchical) GDS, so LVS compares device-for-
device against what was actually drawn. Each instance's own internal-only
nets (``nand3_3v3``'s ``NM1``/``NM2``, each ``nand2_3v3``'s ``NMID``, each
``dff_tg_3v3``'s ``CKB``/``CKBB``/``NM``/``NMA``/``NMB``/``NS``) are
instance-name-prefixed (e.g. ``XFQ_CKB``) so the two ``dff_tg_3v3`` instances'
internal nodes stay electrically distinct -- device connectivity/sizes are
derived by hand-expanding ``design/netlist/div23_cell.spice``'s own
``X``-instance list against its own (also flattened, in that same generated
file) sub-cell subckt bodies, not re-derived from the schematic in isolation
or generated from this module's own ``INSTANCES`` table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import devgen, dff_tg_3v3, inv2x_3v3, inv_3v3, nand2_3v3, nand3_3v3
from .devgen import Canvas, Column, Device, NetTracks, nwell_over, offset_pad_x, pad_center, route_net, well_tap

TOP_CELL = "div23_cell"

#: This cell's own top-level I/O (``design/div23_cell.sch``'s subckt ports),
#: per ``design/netlist/div23_cell.spice``'s own
#: ``.subckt div23_cell CKIN MODIN P CKOUT MODOUT VDD VSS`` header.
BOUNDARY_NETS: tuple[str, ...] = ("CKIN", "MODIN", "P", "CKOUT", "MODOUT", "VDD", "VSS")

#: Minimum clear horizontal gap between one column's own rightmost drawn edge
#: and the next column's own ``x0`` -- generous headroom (well past
#: ``dff_tg_3v3.py``'s own proven 6.5 um clearance for its narrower, at-most-
#: 2.5 um-wide columns) to comfortably fit a periodic tap pair plus this
#: module's own per-bucket net offsets even for this composite's widest
#: columns (``inv2x_3v3``'s 5 um pfet, ``nand3_3v3``'s 3 um series nfets).
COLUMN_CLEAR_GAP_UM = 8.0

#: Offset step between two distinct nets sharing one column's own natural
#: pad x (see module docstring's "NET-COLLISION FIX" section). > (Metal3
#: wire width (0.34) + M3.2a's 0.28 um minimum Metal3 spacing) = 0.62, with
#: margin -- the same order of magnitude as ``dff_tg_3v3.py``'s own proven
#: 0.75 um offset.
NET_OFFSET_STEP_UM = 0.7

#: Each role's own shared reference x, relative to a column's own ``x0`` --
#: *fixed* anchors, not each role's own natural pad mean/centre, so the two
#: roles' own offset spreads (up to 5 distinct nets on "channel" for
#: ``nand3_3v3``'s own column 0 -- ``NM1``/``NM2``/``VSS``/``VDD``/``Y``; up
#: to 3 on "gate" for the same column -- ``A``/``B``/``C``) never drift close
#: to each other, or close to the *other* role's own always-drawn, always-
#: unmodified (``target_dx == 0.0``) natural pad geometry, regardless of a
#: given column's own device widths.
#:
#: A first attempt anchored "gate" at its own natural pad centre (identical
#: for every device in a column, independent of kind/width -- see
#: :func:`devgen.mosfet`) and only "channel" at a fixed anchor. That was
#: *not* enough: with 3 gate nets the worst-case rightmost gate target
#: (``natural_centre + NET_OFFSET_STEP_UM`` = ``x0 - 0.1``) lands only a
#: fraction of a micron from a *channel* pad's own natural, un-offset left
#: edge -- which sits at ``x0`` itself (a device's own comp island starts
#: exactly at the column's ``x0``) regardless of how far right this
#: module's own ``CHANNEL_REF_DX_UM`` anchor is -- a real, concretely-
#: observed M1.1 violation on ``nand3_3v3``'s own column 0 (this composite's
#: only 3-series-gate column). Anchoring "gate" at a fixed offset too (not
#: its own natural centre) fixes it: -1.7 keeps the gate role's own worst-
#: case rightmost target (``-1.7 + NET_OFFSET_STEP_UM`` = ``x0 - 1.0``) a
#: full 1 um clear of ``x0`` itself, comfortably past M3.2a's 0.28 um
#: minimum spacing (and M1.1's 0.23 um minimum width) with margin to spare.
GATE_REF_DX_UM = -1.7
CHANNEL_REF_DX_UM = 2.5

#: How far a tap pair's own ntap sits past the *left* column's rightmost
#: reach -- identical value/rationale to ``dff_tg_3v3.py``'s own
#: ``_TAP_LEFT_MARGIN_UM``.
TAP_LEFT_MARGIN_UM = 1.5

#: Same same-x-different-net fix as ``dff_tg_3v3.py``'s own ``_TAP_OFFSET_UM``,
#: applied to one periodic tap pair's own ptap (offset) against its ntap
#: (natural).
TAP_OFFSET_UM = 0.8

#: y0 of each periodic tap, centred inside the pulldown/pullup baselines'
#: own bottom margin -- identical relative offset (0.34 um above each row's
#: own baseline) to ``dff_tg_3v3.py``'s own ``_PTAP_Y0_UM``/``_NTAP_Y0_UM``,
#: re-based onto this module's ``ROW_PD_Y0``/``ROW_PU_Y0`` baselines (0.0 and
#: 10.0, vs. that module's own tighter 0.0/5.28).
PTAP_Y0_UM = devgen.ROW_PD_Y0 + 0.34
NTAP_Y0_UM = devgen.ROW_PU_Y0 + 0.34


def _split_branches(devices: Sequence[Device]) -> Column:
    """A :class:`Column` built from an unordered device list, split by kind.

    ``nfet`` devices become the pulldown branch, ``pfet`` the pullup branch,
    each keeping the input list's own relative order (already bottom-to-top
    per every device table this module draws from -- ``inv_3v3.INV_DEVICES``,
    ``tgate_3v3.TGATE_DEVICES`` (via ``dff_tg_3v3.INSTANCES``), and
    ``nand3_3v3``/``nand2_3v3``/``inv2x_3v3``'s own already-``Column`` tables,
    which need no split at all -- see :func:`_leaf_columns`/:func:`_dff_columns`
    for which path each instance takes).
    """
    return Column(
        pulldown=tuple(d for d in devices if d.kind == "nfet"),
        pullup=tuple(d for d in devices if d.kind == "pfet"),
    )


#: Placement entry: one column (a pulldown/pullup branch pair, either half
#: possibly empty) plus the device-local -> composite-global net map for
#: every device this column draws.
_Placement = tuple[Column, dict[str, str]]


def _leaf_columns(module_columns: Sequence[Column], port_map: dict[str, str]) -> list[_Placement]:
    """Every leaf cell here (``nand3_3v3``, ``nand2_3v3``, ``inv2x_3v3``)
    already exports a ``COLUMNS: tuple[devgen.Column, ...]`` table -- reused
    as-is, one composite placement per column, all sharing the same
    (single-instance) ``port_map``.
    """
    return [(col, port_map) for col in module_columns]


_DFF_INTERNAL_NETS: tuple[str, ...] = ("CKB", "CKBB", "NM", "NMA", "NMB", "NS")


def _dff_columns(instance_name: str, boundary_map: dict[str, str]) -> list[_Placement]:
    """The 10 columns one ``dff_tg_3v3`` instance draws, translated straight
    through ``dff_tg_3v3.INSTANCES`` (issue #308) -- reusing that module's own
    device tables and its own device-local -> ``dff_tg_3v3``-local port maps
    unchanged, composed with one more translation layer
    (``dff_tg_3v3``-local -> this composite's own global net names).

    Boundary nets (``D``, ``CK``, ``Q``, ``QB``, ``VDD``, ``VSS``) map to
    ``boundary_map``'s own global names (this instance's own div23_cell-level
    wiring); ``dff_tg_3v3``'s six internal-only nets
    (:data:`_DFF_INTERNAL_NETS`) are prefixed with ``instance_name`` so the
    two ``dff_tg_3v3`` instances' own internal nodes stay electrically
    distinct.
    """
    outer_map = dict(boundary_map)
    for net in _DFF_INTERNAL_NETS:
        outer_map[net] = f"{instance_name}_{net}"

    placements: list[_Placement] = []
    for _name, _kind, devices, local_port_map in dff_tg_3v3.INSTANCES:
        col = _split_branches(devices)
        global_port_map = {device_local: outer_map[dff_local] for device_local, dff_local in local_port_map.items()}
        placements.append((col, global_port_map))
    return placements


#: The full, ordered placement list -- 30 columns across 8 sub-cell
#: instances, in ``design/netlist/div23_cell.spice``'s own X-instance order.
#: Built lazily (a function, not a module-level constant) so importing this
#: module never touches ``dff_tg_3v3.INSTANCES``' own dataclasses before
#: ``devgen``'s lazy ``klayout.db`` import would be needed anyway -- kept
#: consistent with how every device-table constant elsewhere in this package
#: is plain, side-effect-free data.
def placements() -> list[_Placement]:
    result: list[_Placement] = []
    result += _leaf_columns(
        nand3_3v3.COLUMNS,
        {"A": "MODIN", "B": "P", "C": "MODOUT", "Y": "SB", "VDD": "VDD", "VSS": "VSS", "NM1": "XN3_NM1", "NM2": "XN3_NM2"},
    )
    result += _leaf_columns(
        nand2_3v3.COLUMNS,
        {"A": "QB", "B": "SB", "Y": "DQN", "VDD": "VDD", "VSS": "VSS", "NMID": "XN2Q_NMID"},
    )
    result.append((_split_branches(inv_3v3.INV_DEVICES), {"A": "DQN", "Y": "DQ", "VDD": "VDD", "VSS": "VSS"}))
    result += _dff_columns("XFQ", {"D": "DQ", "CK": "CKIN", "Q": "Q", "QB": "QB", "VDD": "VDD", "VSS": "VSS"})
    result += _leaf_columns(inv2x_3v3.COLUMNS, {"A": "QB", "Y": "CKOUT", "VDD": "VDD", "VSS": "VSS"})
    result += _leaf_columns(
        nand2_3v3.COLUMNS,
        {"A": "MODIN", "B": "Q", "Y": "NMO", "VDD": "VDD", "VSS": "VSS", "NMID": "XN2M_NMID"},
    )
    result.append((_split_branches(inv_3v3.INV_DEVICES), {"A": "NMO", "Y": "DMO", "VDD": "VDD", "VSS": "VSS"}))
    result += _dff_columns("XFMO", {"D": "DMO", "CK": "CKIN", "Q": "MODOUT", "QB": "MOB", "VDD": "VDD", "VSS": "VSS"})
    return result


def _draw_branch(canvas: Canvas, devices: Sequence[Device], x0: float, y_base: float) -> list[devgen.MosfetPorts]:
    """One branch (all-nfet or all-pfet, bottom-to-top), left-aligned at
    ``x0``, starting at the fixed baseline ``y_base`` -- the same drawing
    step ``devgen.build_row_cell()``'s own internal ``_draw_branch`` helper
    performs, standalone here so this module can draw a pulldown/pullup pair
    without also triggering that function's own per-cell strap/rail/track
    routing (see module docstring's "ONE FRAME FOR EVERY COLUMN" section).
    """
    ports: list[devgen.MosfetPorts] = []
    y = y_base
    for i, d in enumerate(devices):
        if i > 0:
            y += devgen.COMP_GAP_UM
        p = devgen.mosfet(canvas, d, x0, y)
        ports.append(p)
        y = p.y3
    return ports


@dataclass
class Div23Layout:
    canvas: Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, tuple[float, float]] = field(default_factory=dict)
    nwell_box: tuple[float, float, float, float] | None = None

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def build(outdir: Path | None = None) -> Div23Layout:
    canvas = Canvas(TOP_CELL)
    nets: dict[str, list[tuple[float, float]]] = {}
    #: every drawn PMOS comp box (device + ntap) -- feeds nwell_over() below;
    #: the footprint itself is read back off the canvas's own drawn bbox
    #: (see ``build_row_cell()``'s own precedent), not hand-tracked here.
    pfet_boxes: list[tuple[float, float, float, float]] = []

    def _add_point(net: str, point: tuple[float, float]) -> None:
        nets.setdefault(net, []).append(point)

    x_cursor = 0.0
    for col, port_map in placements():
        devices = col.pulldown + col.pullup
        pd_ports = _draw_branch(canvas, col.pulldown, x_cursor, devgen.ROW_PD_Y0)
        pu_ports = _draw_branch(canvas, col.pullup, x_cursor, devgen.ROW_PU_Y0)
        ports = pd_ports + pu_ports

        for p in ports:
            if p.kind == "pfet":
                pfet_boxes.append((p.x0, p.y0, p.x1, p.y3))

        # --- per-column, per-role (gate / channel) net-offset groups -- see
        # module docstring's "NET-COLLISION FIX" section for why grouping by
        # role (not by each pad's own raw natural x), and why each role's own
        # reference x is a *fixed* anchor (not that role's own natural pad
        # mean), is what actually guarantees a minimum inter-net separation
        # both within and between the two roles. ---
        roles: dict[str, list[tuple[str, tuple[float, float, float, float]]]] = {"gate": [], "channel": []}
        for d, p in zip(devices, ports):
            roles["gate"].append((port_map[d.gate_net], p.gate_pad))
            roles["channel"].append((port_map[d.top_net], p.top_pad))
            roles["channel"].append((port_map[d.bottom_net], p.bottom_pad))
        role_reference = {
            "gate": x_cursor + GATE_REF_DX_UM,
            "channel": x_cursor + CHANNEL_REF_DX_UM,
        }
        channel_max_reach = x_cursor
        for role, items in roles.items():
            if not items:
                continue
            reference_x = role_reference[role]
            nets_here = sorted({n for n, _ in items})
            n = len(nets_here)
            offsets = {net: (i - (n - 1) / 2.0) * NET_OFFSET_STEP_UM for i, net in enumerate(nets_here)}
            if role == "channel":
                channel_max_reach = reference_x + max(offsets.values())
            for net, pad in items:
                target_dx = reference_x + offsets[net] - pad_center(pad)[0]
                point = pad_center(pad) if target_dx == 0.0 else offset_pad_x(canvas, pad, target_dx)
                _add_point(net, point)

        # --- periodic n/p tap pair, past this column's own rightmost reach
        # (the drawn device edge, or the "channel" role's own furthest-right
        # net offset target, whichever reaches further -- see
        # CHANNEL_REF_DX_UM's own docstring for why the latter can exceed a
        # narrow column's own drawn comp width). ---
        col_right = max([p.x1 for p in ports] + [channel_max_reach], default=x_cursor)
        half_tap = devgen.TAP_SIZE_UM / 2.0
        gx = col_right + TAP_LEFT_MARGIN_UM
        ntap_pad = well_tap(canvas, "n", gx - half_tap, NTAP_Y0_UM, "VDD")
        _add_point("VDD", pad_center(ntap_pad))
        ntap_box = (gx - half_tap, NTAP_Y0_UM, gx + half_tap, NTAP_Y0_UM + devgen.TAP_SIZE_UM)
        pfet_boxes.append(ntap_box)
        ptap_pad = well_tap(canvas, "p", gx - half_tap, PTAP_Y0_UM, "VSS")
        _add_point("VSS", offset_pad_x(canvas, ptap_pad, TAP_OFFSET_UM))

        x_cursor = col_right + COLUMN_CLEAR_GAP_UM

    # --- one shared nwell enclosing every PMOS comp box + every ntap's own
    # comp box (not just its net -- see devgen.py's "WELL/SUBSTRATE TIES"). ---
    nwell_box = nwell_over(canvas, pfet_boxes)

    # --- route every net once, each on its own Metal2 track. ---
    tracks = NetTracks(base_y=nwell_box[3] + 3.0)
    for net, pads in nets.items():
        route_net(canvas, net, pads, tracks.get(net))

    # --- boundary pin labels (Metal1, purpose 10), one per top-level I/O
    # net, dropped on that net's own first device pad. ---
    pins: dict[str, tuple[float, float]] = {}
    for net in BOUNDARY_NETS:
        x, y = nets[net][0]
        canvas.label("metal1_label", net, x, y)
        pins[net] = (x, y)

    drawn = canvas.top.bbox()
    dbu = canvas.dbu
    footprint = (
        round(drawn.left * dbu, 6),
        round(drawn.bottom * dbu, 6),
        round(drawn.right * dbu, 6),
        round(drawn.top * dbu, 6),
    )

    layout = Div23Layout(canvas=canvas, footprint=footprint, pins=pins, nwell_box=nwell_box)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def reference_netlist() -> str:
    """Hand-written, independently-stated, fully-flattened LVS reference
    netlist -- see this module's own docstring ("REFERENCE NETLIST") for why
    flat (60 ``M`` lines) rather than 8 ``X`` calls, and why instance-name-
    prefixed internal nets.
    """
    pfet = "pfet_03v3 L=0.28u"
    nfet = "nfet_03v3 L=0.28u"

    def _dff_body(prefix: str, d: str, ck: str, q: str, qb: str) -> str:
        ckb, ckbb, nm, nma, nmb, ns = (f"{prefix}_{n}" for n in ("CKB", "CKBB", "NM", "NMA", "NMB", "NS"))

        def _inv(tag: str, a: str, y: str) -> str:
            return f"M_{prefix}_{tag}_P {y} {a} VDD VDD {pfet} W=2.5u\nM_{prefix}_{tag}_N {y} {a} VSS VSS {nfet} W=1u\n"

        def _tg(tag: str, a: str, y: str, gn: str, gp: str) -> str:
            return (
                f"M_{prefix}_{tag}_P {y} {gp} {a} VDD {pfet} W=2.5u\n"
                f"M_{prefix}_{tag}_N {a} {gn} {y} VSS {nfet} W=1u\n"
            )

        return (
            _inv("ICKB", ck, ckb)
            + _inv("ICKBB", ckb, ckbb)
            + _tg("TGMI", d, nm, ckb, ckbb)
            + _inv("IA", nm, nma)
            + _inv("IB", nma, nmb)
            + _tg("TGMF", nmb, nm, ckbb, ckb)
            + _tg("TGSI", nma, ns, ckbb, ckb)
            + _inv("IC", ns, q)
            + _inv("ID", q, qb)
            + _tg("TGSF", qb, ns, ckb, ckbb)
        )

    def _nand3(prefix: str, a: str, b: str, c: str, y: str) -> str:
        nm1, nm2 = f"{prefix}_NM1", f"{prefix}_NM2"
        return (
            f"M_{prefix}_MPA {y} {a} VDD VDD {pfet} W=2.5u\n"
            f"M_{prefix}_MPB {y} {b} VDD VDD {pfet} W=2.5u\n"
            f"M_{prefix}_MPC {y} {c} VDD VDD {pfet} W=2.5u\n"
            f"M_{prefix}_MNA {y} {a} {nm1} VSS {nfet} W=3u\n"
            f"M_{prefix}_MNB {nm1} {b} {nm2} VSS {nfet} W=3u\n"
            f"M_{prefix}_MNC {nm2} {c} VSS VSS {nfet} W=3u\n"
        )

    def _nand2(prefix: str, a: str, b: str, y: str) -> str:
        nmid = f"{prefix}_NMID"
        return (
            f"M_{prefix}_MPA {y} {a} VDD VDD {pfet} W=2.5u\n"
            f"M_{prefix}_MPB {y} {b} VDD VDD {pfet} W=2.5u\n"
            f"M_{prefix}_MNA {y} {a} {nmid} VSS {nfet} W=2u\n"
            f"M_{prefix}_MNB {nmid} {b} VSS VSS {nfet} W=2u\n"
        )

    def _inv(prefix: str, a: str, y: str) -> str:
        return f"M_{prefix}_MP {y} {a} VDD VDD {pfet} W=2.5u\nM_{prefix}_MN {y} {a} VSS VSS {nfet} W=1u\n"

    def _inv2x(prefix: str, a: str, y: str) -> str:
        return f"M_{prefix}_MP {y} {a} VDD VDD {pfet} W=5u\nM_{prefix}_MN {y} {a} VSS VSS {nfet} W=2u\n"

    body = (
        _nand3("XN3", "MODIN", "P", "MODOUT", "SB")
        + _nand2("XN2Q", "QB", "SB", "DQN")
        + _inv("XIQ", "DQN", "DQ")
        + _dff_body("XFQ", "DQ", "CKIN", "Q", "QB")
        + _inv2x("XICKO", "QB", "CKOUT")
        + _nand2("XN2M", "MODIN", "Q", "NMO")
        + _inv("XIM", "NMO", "DMO")
        + _dff_body("XFMO", "DMO", "CKIN", "MODOUT", "MOB")
    )
    return (
        "* Reference schematic for div23_cell (issue #309).\n"
        "*\n"
        "* Hand-written independently of the layout, fully flattened to 60 M\n"
        "* device lines (not 8 X-instance calls into nand3_3v3/nand2_3v3/inv_3v3/\n"
        "* dff_tg_3v3/inv2x_3v3) -- see this module's own docstring\n"
        '* ("REFERENCE NETLIST") for why, and layout/harness/cell.py\'s docstring\n'
        "* for the general discipline. Connectivity/sizes derived by\n"
        "* hand-expanding design/netlist/div23_cell.spice's own X-instance list\n"
        "* against its own inlined sub-cell subckt bodies. Each instance's own\n"
        "* internal-only nets are instance-name-prefixed (e.g. XFQ_CKB) so the\n"
        "* two dff_tg_3v3 instances' own internal nodes stay distinct.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        f".subckt {TOP_CELL} CKIN MODIN P CKOUT MODOUT VDD VSS\n"
        f"{body}"
        ".ends\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "divider-div23-proof" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"wrote {netlist_path}")
    print("instances : 8 (1 nand3_3v3 + 2 nand2_3v3 + 2 inv_3v3 + 2 dff_tg_3v3 + 1 inv2x_3v3)")
    print("devices   : 60")
    print(f"footprint : {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    print(f"pins      : {sorted(layout.pins)}")
    for net in BOUNDARY_NETS:
        print(f"  {net:8s} @ {layout.pins[net]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
