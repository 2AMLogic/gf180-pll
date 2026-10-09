"""Assemble ``pll_top.gds`` from the five real block layouts (issue #297).

    python3 -m pll_top.top_level.assemble --outdir DIR [--check]

(run from ``layout/``). Writes ``DIR/pll_top.gds`` (top cell ``pll_top``) and
``DIR/pll_top-assembly.json`` (placements, access points, routes, area).

SOURCES
-------
Each block is produced by its own generator through the same ``python3 -m
<module> --outdir`` entry point ``layout/harness/reproduce.py`` uses to check
the committed block GDS files, so the assembly is rebuilt from committed
generator source rather than from whatever GDS happens to be on disk. The
generators return different Python types; this module only ever reads the GDS
each one writes. Each block's single flat cell is copied into the new layout
under its own name -- ``lock_detector``, ``pfd_cp``, ``loop_filter``,
``vco_block``, ``divider_chain`` -- and the import refuses a source with more
than one top cell, a subcell, a cell-name collision, or no geometry on the
device layers (a placement box cannot stand in for a block).

FLOORPLAN
---------
::

    y
       +--------------------------------------------------------------------+  top pins
       | divider_chain (R180: its clock input and FB end sit above the VCO)  |  P*, SEL*, DIVOUT,
       +--------------------------------------------------------------------+  VDD_DIV, CLK, FB
         middle channel: UP, DN, FB, CLK, VSS->divider     (40 um + the VCO's 15 um keep-out)
       +-------------+    +-----------------+    +-----------+    +-------+
       |lock_detector|    | pfd_cp (M90)    |    |loop_filter|    |  vco  |
       |   (M90)     |    | VOUT on the     |    |  C1  R C2 |    | block |
       +-------------+    | loop-filter side|    +-----------+    +-------+
         bottom channel: VCTRL, VDD/VSS star branches
       +--+-----+--------+--+--------+------------------+----+--------+---+  bottom pins
          |     |  VSS VDD pads in the lock_detector|pfd_cp gap

* Signal flow left to right is PFD/CP -> loop filter -> VCO, as
  ``PLL-FLOORPLAN.md`` section 3 places it (the loop filter at the PFD/CP-VCO
  boundary), with the domain spacing ``floorplan/skeleton.py`` uses
  (``DOMAIN_SPACING``, 40 um) between neighbours and the VCO's 15 um keep-out
  (``VCO_GUARD_MARGIN``) kept clear of every non-VCO wire.
* **Deviation from the skeleton, disclosed:** the skeleton stacks
  ``lock_detector`` above ``divider_chain`` in one ``DIVIDER_LOCK`` region.
  Here ``lock_detector`` sits in the bottom row beside ``pfd_cp`` instead. Both
  are on the ``VDD`` domain (``divider_chain`` is ``VDD_DIV``), the ``UP``/``DN``
  runs between them become short, and the stacked arrangement would add a
  full-width ~144 um band (lock-detector height + one domain spacing) to a
  layout that is already over its area row -- see the evidence record.
* ``lock_detector`` and ``pfd_cp`` are mirrored about the y axis (``M90``) and
  ``divider_chain`` is rotated 180 degrees: each puts the ports that face a
  neighbour on that neighbour's side. Mirroring and 90-degree rotation are
  exact on the manufacturing grid and do not change a single rule check.

ROUTING
-------
Top-level wires are Metal4 (horizontal tracks in the two channels) and Metal5
(vertical columns from a port to its channel or to the chip edge); no block
draws either layer. A wire reaches a port through a via stack placed by
:mod:`access` on that port's own net. Supplies are **star-routed**: every
(supply, block) pair is its own branch from its own pad slot, and the branches
of one supply touch only at its pad (``route.compatible`` refuses anything
else at drawing time), per ``PLL-FLOORPLAN.md`` section 2's "four physically
separate trunks ... star-connected at the pads, never sharing a segment".
``VWIN`` is internal to ``lock_detector`` and is not routed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import access as A
from . import extract as X
from . import netlist as NL
from . import route as R
from .extract import db

LAYOUT_DIR = Path(__file__).resolve().parents[2]
TOP_CELL = "pll_top"
GDS_NAME = f"{TOP_CELL}.gds"
REPORT_NAME = f"{TOP_CELL}-assembly.json"

DOMAIN_SPACING_UM = 40.0  # floorplan/skeleton.py DOMAIN_SPACING
VCO_GUARD_MARGIN_UM = 15.0  # floorplan/skeleton.py VCO_GUARD_MARGIN
CHANNEL_CLEAR_UM = 2.0  # a channel's first track edge to the nearest block bbox
EDGE_UM = 6.0  # outermost track / block edge to the chip edge (pins end here)
PAD_H_UM = 4.0  # supply pad bar height
SLOT_PITCH_UM = 4.0  # star branch slot pitch inside a pad bar
INF_UM = 5000.0

#: the layers a block must carry drawn geometry on to count as a block at all
DEVICE_LAYERS = ("comp", "poly2", "contact", "metal1")


@dataclass(frozen=True)
class BlockSpec:
    subckt: str  # name in design/netlist/pll_top.spice
    module: str  # generator, run as python3 -m <module> --outdir <dir>
    gds: str  # file the generator writes
    cell: str  # its top cell
    orient: str  # "R0", "M90" (mirror x), "R180"
    evidence: str  # committed copy, relative to layout/ (registered in harness/reproduce.py)


BLOCKS: tuple[BlockSpec, ...] = (
    BlockSpec("lock_detector", "pll_top.lock_detector.build", "lock_detector.gds", "lock_detector", "M90",
              "evidence/lock-detector-layout/lock_detector.gds"),
    BlockSpec("pfd_cp", "pll_top.pfd_cp.block", "pfd_cp.gds", "pfd_cp", "M90",
              "evidence/pfd-cp-layout/pfd_cp.gds"),
    BlockSpec("loop_filter", "pll_top.loop_filter.block", "loop_filter.gds", "loop_filter", "R0",
              "evidence/loop-filter-layout/loop_filter.gds"),
    BlockSpec("vco", "pll_top.vco.block", "vco_block.gds", "vco_block", "R0",
              "evidence/vco-layout/vco_block.gds"),
    BlockSpec("divider_chain", "pll_top.divider_chain.divider_chain", "divider_chain.gds", "divider_chain", "R180",
              "evidence/divider-chain-layout/divider_chain.gds"),
)
ROW = ("lock_detector", "pfd_cp", "loop_filter", "vco")  # bottom row, left to right


class AssemblyError(RuntimeError):
    pass


def _orient(name: str):
    T = db().Trans
    return {"R0": T.R0, "M90": T.M90, "R180": T.R180}[name]


# ---------------------------------------------------------------------------
# block import
# ---------------------------------------------------------------------------


def generate_blocks(workdir: Path) -> dict[str, Path]:
    """Run every block generator into ``workdir``; ``{subckt: gds path}``."""
    sys.path.insert(0, str(LAYOUT_DIR))
    from harness import reproduce  # noqa: PLC0415

    out = {}
    for spec in BLOCKS:
        out[spec.subckt] = reproduce.rebuild(reproduce.Block(spec.evidence, spec.module), workdir / spec.subckt)
    return out


def import_block(target, spec: BlockSpec, gds: Path):
    """Copy ``gds``'s single flat top cell into ``target`` as ``spec.cell``."""
    _db = db()
    src = _db.Layout()
    src.read(str(gds))
    tops = list(src.top_cells())
    if len(tops) != 1:
        raise AssemblyError(f"{spec.subckt}: {gds} has {len(tops)} top cells, expected 1")
    top = tops[0]
    if top.name != spec.cell:
        raise AssemblyError(f"{spec.subckt}: {gds} top cell is {top.name!r}, expected {spec.cell!r}")
    if src.cells() != 1:
        raise AssemblyError(f"{spec.subckt}: {gds} has {src.cells()} cells; the blocks are flat, so a subcell is unexpected")
    if target.has_cell(spec.cell):
        raise AssemblyError(f"{spec.subckt}: cell name {spec.cell!r} already used by another block")
    for lname in DEVICE_LAYERS:
        idx = src.find_layer(*X.LAYER[lname])
        if idx is None or top.bbox_per_layer(idx).empty():
            raise AssemblyError(
                f"{spec.subckt}: {gds} draws nothing on {lname} {X.LAYER[lname]} -- not a block layout "
                "(a placement box cannot stand in for one)"
            )
    cell = target.create_cell(spec.cell)
    cell.copy_tree(top)  # scales to target.dbu if the source differs
    return cell


# ---------------------------------------------------------------------------
# routing plan
# ---------------------------------------------------------------------------


@dataclass
class Terminal:
    block: str
    port: str


@dataclass
class NetPlan:
    net: str
    kind: str  # "pin_down", "pin_up", "trunk", "star", "power_down", "power_up"
    terminals: list[Terminal]
    channel: str = ""  # trunk: "bottom" | "middle"
    pin: str = ""  # trunk: "" | "bottom" | "top" -- which edge carries the net's pin
    pin_at: str = ""  # trunk: block whose terminal column carries the pin


def plan(nl: NL.TopNetlist) -> list[NetPlan]:
    """The routing plan, checked against the netlist (every port, every pin)."""
    def T(block, port):
        return Terminal(block, port)

    plans: list[NetPlan] = [
        NetPlan("VSS", "star", [T("lock_detector", "VSS"), T("pfd_cp", "VSS"), T("loop_filter", "VSS"), T("divider_chain", "VSS")]),
        NetPlan("VDD", "star", [T("lock_detector", "VDD"), T("pfd_cp", "VDD")]),
        NetPlan("VDD_VCO", "power_down", [T("vco", "VDD_VCO")]),
        NetPlan("GND_VCO", "power_down", [T("vco", "GND_VCO")]),
        NetPlan("VDD_DIV", "power_up", [T("divider_chain", "VDD_DIV")]),
        NetPlan("VCTRL", "trunk", [T("pfd_cp", "VOUT"), T("loop_filter", "VCTRL"), T("vco", "VCTRL")],
                channel="bottom", pin="bottom", pin_at="loop_filter"),
        NetPlan("UP", "trunk", [T("lock_detector", "UP"), T("pfd_cp", "UP")], channel="middle"),
        NetPlan("DN", "trunk", [T("lock_detector", "DN"), T("pfd_cp", "DN")], channel="middle"),
        NetPlan("CLK", "trunk", [T("vco", "CLK"), T("divider_chain", "VCO")], channel="middle", pin="top",
                pin_at="divider_chain"),
        NetPlan("FB", "trunk", [T("divider_chain", "FB"), T("pfd_cp", "FB")], channel="middle", pin="top",
                pin_at="divider_chain"),
    ]
    planned = {p.net for p in plans}
    terms = nl.terminals()
    for net, ports in terms.items():
        if net in planned:
            continue
        if len(ports) != 1:
            raise AssemblyError(f"net {net} joins {ports} but has no routing plan")
        (block, port), = ports
        if net not in nl.pins:
            continue  # block-internal at the top level (VWIN): nothing to route
        kind = "pin_up" if block == "divider_chain" else "pin_down"
        plans.append(NetPlan(net, kind, [T(block, port)]))
    # cross-check every plan against the netlist, both ways
    for p in plans:
        want = sorted(terms.get(p.net, []))
        got = sorted((t.block, t.port) for t in p.terminals)
        if want != got:
            raise AssemblyError(f"plan for {p.net} terminals {got} != netlist {want}")
    routed_pins = {p.net for p in plans if p.kind != "trunk" or p.pin}
    missing = [pin for pin in nl.pins if pin not in routed_pins]
    if missing:
        raise AssemblyError(f"top-level pins with no route to the chip edge: {missing}")
    return plans


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


@dataclass
class Assembly:
    layout: object
    top: object
    views: dict[str, A.BlockView]
    board: R.Board
    accesses: list[A.Access] = field(default_factory=list)
    pins: list[dict] = field(default_factory=list)  # {"net", "x", "y", "edge"} um
    placements: dict = field(default_factory=dict)
    boundary: tuple = ()  # (x0, y0, x1, y1) um
    gds: Path | None = None
    report: dict = field(default_factory=dict)


def _ux(v: int) -> float:
    return round(v * R.DBU, 4)


def assemble(block_gds: dict[str, Path], *, netlist: NL.TopNetlist | None = None) -> Assembly:
    """Place and route; returns an in-memory :class:`Assembly` (not yet written)."""
    _db = db()
    nl = netlist or NL.read()
    specs = {s.subckt: s for s in BLOCKS}
    if set(block_gds) != set(specs):
        missing = sorted(set(specs) - set(block_gds))
        extra = sorted(set(block_gds) - set(specs))
        raise AssemblyError(f"block set mismatch: missing {missing}, unexpected {extra}")
    for inst in nl.instances:
        if inst.subckt not in specs:
            raise AssemblyError(f"pll_top.spice instantiates {inst.subckt}, which has no layout")

    ly = _db.Layout()
    ly.dbu = R.DBU
    top = ly.create_cell(TOP_CELL)
    cells = {s.subckt: import_block(ly, s, block_gds[s.subckt]) for s in BLOCKS}

    # --- placement -----------------------------------------------------------
    sp = R.um(DOMAIN_SPACING_UM)
    trans: dict[str, object] = {}

    def place(name: str, x_ll: int, y_ll: int):
        o = _db.Trans(_orient(specs[name].orient))
        bb = cells[name].bbox().transformed(o)
        t = _db.Trans(_db.Vector(x_ll - bb.left, y_ll - bb.bottom)) * o
        trans[name] = t
        top.insert(_db.CellInstArray(cells[name].cell_index(), t))
        return cells[name].bbox().transformed(t)

    x = 0
    boxes = {}
    for name in ROW:
        boxes[name] = place(name, x, 0)
        x = boxes[name].right + sp
    row_top = max(boxes[n].top for n in ROW)
    mid_lo = max(row_top, boxes["vco"].top + R.um(VCO_GUARD_MARGIN_UM))
    boxes["divider_chain"] = place("divider_chain", 0, mid_lo + sp)
    div = boxes["divider_chain"]

    views = {n: A.make_view(n, ly, cells[n], trans[n]) for n in specs}
    for n, v in views.items():
        v.bbox = boxes[n]
    keepout = _db.Region()
    for v in views.values():
        keepout += v.layers["fusetop"]
    keepout = keepout.sized(R.um(R.FUSETOP_KEEPOUT_UM))

    board = R.Board()
    asm = Assembly(layout=ly, top=top, views=views, board=board)
    columns: list[R.Column] = []
    bottom = R.Channel("bottom", start=-R.um(CHANNEL_CLEAR_UM), limit=-R.um(400.0), direction=-1)
    middle = R.Channel("middle", start=mid_lo + R.um(CHANNEL_CLEAR_UM), limit=div.bottom - R.um(CHANNEL_CLEAR_UM),
                       direction=+1)
    channels = {"bottom": bottom, "middle": middle}
    INF = R.um(INF_UM)

    def label_xy(block: str, port: str):
        lab = views[block].label(port)
        p = trans[block].trans(_db.Point(R.um(lab.x), R.um(lab.y)))
        return p.x, p.y

    # Star pad slots, in the lock_detector | pfd_cp gap.
    gap_l = boxes["lock_detector"].right
    slots = {
        ("VSS", "divider_chain"): gap_l + R.um(6.0),
        ("VSS", "lock_detector"): gap_l + R.um(6.0 + SLOT_PITCH_UM),
        ("VSS", "pfd_cp"): gap_l + R.um(6.0 + 2 * SLOT_PITCH_UM),
        ("VSS", "loop_filter"): gap_l + R.um(6.0 + 3 * SLOT_PITCH_UM),
        ("VDD", "lock_detector"): gap_l + R.um(28.0),
        ("VDD", "pfd_cp"): gap_l + R.um(28.0 + SLOT_PITCH_UM),
    }
    if max(slots.values()) + R.um(R.POWER_W_UM) > boxes["pfd_cp"].left:
        raise AssemblyError("supply pad slots do not fit in the lock_detector | pfd_cp gap")
    pw, sw = R.um(R.POWER_W_UM), R.um(R.SIGNAL_W_UM)
    # reserve the pad bars and the divider's VSS riser before any port is chosen
    for (net, blk), sx in slots.items():
        top_y = middle.limit if blk == "divider_chain" else -R.um(CHANNEL_CLEAR_UM)
        columns.append(R.Column(f"{net}@{blk}", sx, -INF, top_y, pw))

    plans = plan(nl)
    order = {"star": 0, "power_down": 1, "power_up": 1, "trunk": 2, "pin_down": 3, "pin_up": 3}
    plans.sort(key=lambda p: order[p.kind])

    def block_side(block: str) -> str:
        return "divider" if block == "divider_chain" else "row"

    # Each entry: (plan, terminal, access, column-destination) collected, then drawn.
    chosen: list[tuple[NetPlan, Terminal, A.Access]] = []

    for p in plans:
        for t in p.terminals:
            inst = nl.instance(t.block)
            net = inst.port_net()[t.port]
            assert net == p.net
            v = views[t.block]
            bb = v.bbox
            power = p.kind in ("star", "power_down", "power_up")
            width = R.POWER_W_UM if power else R.SIGNAL_W_UM
            nvia = R.POWER_VIAS if power else R.SIGNAL_VIAS
            key = f"{p.net}@{t.block}" if p.kind == "star" else p.net
            others = [label_xy(o.block, o.port) for o in p.terminals if o is not t]
            x_pref = None
            if p.kind == "star":
                x_pref = slots[(p.net, t.block)]
            elif others:
                x_pref = sum(o[0] for o in others) / len(others)

            # direction of travel from the port, and how far the column is reserved
            if p.kind in ("pin_down", "power_down") or (p.kind == "star" and t.block != "divider_chain") or (
                p.kind == "trunk" and p.channel == "bottom"
            ):
                def span(x, y):
                    return (-INF, y)

                def score(x, y, bb=bb, x_pref=x_pref):
                    s = (y - bb.bottom) * R.DBU
                    return s + (0.2 * abs(x - x_pref) * R.DBU if x_pref is not None else 0.0)
            elif p.kind in ("pin_up", "power_up"):
                def span(x, y):
                    return (y, INF)

                def score(x, y, bb=bb):
                    return (bb.top - y) * R.DBU
            elif block_side(t.block) == "row":  # row block -> middle channel, upward
                def span(x, y):
                    return (y, middle.limit)

                def score(x, y, bb=bb, x_pref=x_pref):
                    return (bb.top - y) * R.DBU + 0.2 * abs(x - x_pref) * R.DBU
            else:  # divider -> middle channel, downward (and maybe on up to a top pin)
                carries_pin = p.kind == "trunk" and p.pin == "top" and p.pin_at == t.block

                def span(x, y, carries_pin=carries_pin):
                    return (middle.start, INF if carries_pin else y)

                def score(x, y, bb=bb, x_pref=x_pref):
                    return (y - bb.bottom) * R.DBU + (0.2 * abs(x - x_pref) * R.DBU if x_pref is not None else 0.0)

            # A supply riser is a 2x2 via array where the port net is wide enough
            # for one; otherwise a single via per cut layer (recorded per access).
            last: Exception | None = None
            for n in range(nvia, 0, -1):
                try:
                    acc, col = A.find(
                        v, t.port, p.net, key=key, n_via=n, score=score, column_span=span,
                        column_width_um=width, board=board, columns=columns, keepout=keepout,
                    )
                    break
                except A.NoAccess as exc:
                    last = exc
            else:
                raise AssemblyError(str(last))
            columns.append(col)
            _draw_stack(board, acc, width)
            chosen.append((p, t, acc))
            asm.accesses.append(acc)

    # --- tracks ----------------------------------------------------------------
    by_plan: dict[str, list[A.Access]] = {}
    for p, t, acc in chosen:
        by_plan.setdefault(p.net, []).append(acc)
    track_y: dict[str, int] = {}  # key -> track centre
    track_span: dict[str, tuple[int, int, int]] = {}  # key -> (x0, x1, width)
    for p in plans:
        accs = by_plan[p.net]
        if p.kind == "trunk":
            xs = [a.x for a in accs]
            ch = channels[p.channel]
            track_y[p.net] = ch.place(p.net, min(xs), max(xs), sw)
            track_span[p.net] = (min(xs), max(xs), sw)
        elif p.kind == "star":
            for a in accs:
                sx = slots[(p.net, a.block)]
                ch = middle if a.block == "divider_chain" else bottom
                x0, x1 = min(a.x, sx), max(a.x, sx)
                track_y[a.key] = ch.place(a.key, x0, x1, pw)
                track_span[a.key] = (x0, x1, pw)

    lo = bottom.extent()
    y_bot = (lo[0] if lo else 0) - R.um(EDGE_UM + PAD_H_UM)
    y_top = div.top + R.um(EDGE_UM)

    # --- draw wires --------------------------------------------------------------
    def vwire(key, net, x, ya, yb, w, branch=""):
        y0, y1 = min(ya, yb), max(ya, yb)
        h = w // 2
        board.add("metal5", _db.Box(x - h, y0 - h, x + h, y1 + h), net, "wire", branch)

    def hwire(key, net, x0, x1, y, w, branch=""):
        h = w // 2
        board.add("metal4", _db.Box(x0 - h, y - h, x1 + h, y + h), net, "wire", branch)

    def junction(net, x, y, n, w, branch=""):
        for vb in R.via_boxes(x, y, n):
            board.add("via4", vb, net, "via", branch)

    def pin(net, x, y, edge):
        asm.pins.append({"net": net, "x": _ux(x), "y": _ux(y), "edge": edge})

    for p in plans:
        accs = by_plan[p.net]
        if p.kind in ("pin_down", "power_down"):
            (a,) = accs
            w = pw if p.kind == "power_down" else sw
            vwire(p.net, p.net, a.x, a.y, y_bot, w)
            pin(p.net, a.x, y_bot + R.um(1.0), "bottom")
        elif p.kind in ("pin_up", "power_up"):
            (a,) = accs
            w = pw if p.kind == "power_up" else sw
            vwire(p.net, p.net, a.x, a.y, y_top, w)
            pin(p.net, a.x, y_top - R.um(1.0), "top")
        elif p.kind == "trunk":
            ty = track_y[p.net]
            x0, x1, _ = track_span[p.net]
            hwire(p.net, p.net, x0, x1, ty, sw)
            for a in accs:
                vwire(p.net, p.net, a.x, a.y, ty, sw)
                junction(p.net, a.x, ty, R.SIGNAL_VIAS, sw)
                if p.pin and a.block == p.pin_at:
                    if p.pin == "bottom":
                        vwire(p.net, p.net, a.x, ty, y_bot, sw)
                        pin(p.net, a.x, y_bot + R.um(1.0), "bottom")
                    else:
                        vwire(p.net, p.net, a.x, a.y, y_top, sw)
                        pin(p.net, a.x, y_top - R.um(1.0), "top")
        elif p.kind == "star":
            sxs = []
            for a in accs:
                sx = slots[(p.net, a.block)]
                sxs.append(sx)
                ty = track_y[a.key]
                x0, x1, _ = track_span[a.key]
                vwire(a.key, p.net, a.x, a.y, ty, pw, a.key)
                junction(p.net, a.x, ty, R.POWER_VIAS, pw, a.key)
                hwire(a.key, p.net, x0, x1, ty, pw, a.key)
                junction(p.net, sx, ty, R.POWER_VIAS, pw, a.key)
                vwire(a.key, p.net, sx, ty, y_bot + R.um(PAD_H_UM), pw, a.key)
            h = pw // 2
            board.add("metal5", _db.Box(min(sxs) - h, y_bot, max(sxs) + h, y_bot + R.um(PAD_H_UM)), p.net, "pin")
            pin(p.net, (min(sxs) + max(sxs)) // 2, y_bot + R.um(PAD_H_UM / 2), "bottom")

    # --- emit ------------------------------------------------------------------
    for s in board.shapes:
        top.shapes(ly.layer(*X.LAYER[s.layer])).insert(s.box)
    lab_li = ly.layer(*X.LABEL_LAYER["metal5"])
    for pn in asm.pins:
        top.shapes(lab_li).insert(_db.Text(pn["net"], _db.Trans(_db.Vector(R.um(pn["x"]), R.um(pn["y"])))))

    bb = top.bbox()
    asm.boundary = (_ux(bb.left), _ux(bb.bottom), _ux(bb.right), _ux(bb.top))
    asm.placements = {
        n: {
            "cell": specs[n].cell,
            "orient": specs[n].orient,
            "trans": str(trans[n]),
            "bbox_um": [_ux(boxes[n].left), _ux(boxes[n].bottom), _ux(boxes[n].right), _ux(boxes[n].top)],
        }
        for n in specs
    }
    asm.report = _report(asm, plans, track_y)
    return asm


def _draw_stack(board: R.Board, acc: A.Access, width_um: float) -> None:
    """Via(k)..Via3 + pads up to a Metal4 landing, then Via4: the port's riser."""
    _db = db()
    branch = acc.key if acc.key != acc.net else ""
    for vl in acc.stack_layers():
        for vb in R.via_boxes(acc.x, acc.y, acc.n_via):
            board.add(vl, vb, acc.net, "via", branch)
    for m in acc.pad_metals():
        board.add(m, R.pad_box(acc.x, acc.y, acc.n_via), acc.net, "pad", branch)
    pad = R.pad_box(acc.x, acc.y, acc.n_via)
    h = max(pad.width() // 2, R.um(width_um) // 2)
    board.add("metal4", _db.Box(acc.x - h, acc.y - h, acc.x + h, acc.y + h), acc.net, "pad", branch)
    for vb in R.via_boxes(acc.x, acc.y, acc.n_via):
        board.add("via4", vb, acc.net, "via", branch)


def _report(asm: Assembly, plans: list[NetPlan], track_y: dict) -> dict:
    x0, y0, x1, y1 = asm.boundary
    block_area = {n: round((b["bbox_um"][2] - b["bbox_um"][0]) * (b["bbox_um"][3] - b["bbox_um"][1]), 2)
                  for n, b in asm.placements.items()}
    total = round((x1 - x0) * (y1 - y0), 2)
    return {
        "top_cell": TOP_CELL,
        "boundary_um": [x0, y0, x1, y1],
        "area_um2": total,
        "block_bbox_area_um2": block_area,
        "block_sum_um2": round(sum(block_area.values()), 2),
        "placements": asm.placements,
        "accesses": [
            {"block": a.block, "port": a.port, "net": a.net, "key": a.key, "x": _ux(a.x), "y": _ux(a.y),
             "landing": a.landing, "vias": f"{a.n_via}x{a.n_via}"}
            for a in asm.accesses
        ],
        "pins": asm.pins,
        "tracks_um": {k: _ux(v) for k, v in sorted(track_y.items())},
        "plans": [{"net": p.net, "kind": p.kind, "channel": p.channel, "pin": p.pin,
                   "terminals": [f"{t.block}.{t.port}" for t in p.terminals]} for p in plans],
        "top_level_shapes": len(asm.board.shapes),
    }


def write(asm: Assembly, outdir: Path) -> Path:
    _db = db()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    gds = outdir / GDS_NAME
    opts = _db.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.select_cell(asm.top.cell_index())
    asm.layout.write(str(gds), opts)
    asm.gds = gds
    (outdir / REPORT_NAME).write_text(json.dumps(asm.report, indent=2, sort_keys=True) + "\n")
    return gds


def build(outdir: Path, block_gds: dict[str, Path] | None = None) -> Assembly:
    """Generate every block (unless given), assemble, write. Returns the assembly."""
    if block_gds is None:
        with tempfile.TemporaryDirectory() as tmp:
            block_gds = generate_blocks(Path(tmp))
            asm = assemble(block_gds)
            write(asm, outdir)
            return asm
    asm = assemble(block_gds)
    write(asm, outdir)
    return asm


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble pll_top.gds from the five block layouts (issue #297).")
    parser.add_argument("--outdir", default=str(LAYOUT_DIR / "evidence" / "work" / "pll-top"))
    parser.add_argument("--check", action="store_true", help="grade the written GDS with netcheck.py")
    args = parser.parse_args(argv)
    asm = build(Path(args.outdir))
    x0, y0, x1, y1 = asm.boundary
    print(f"wrote {asm.gds}")
    print(f"boundary: ({x0}, {y0})-({x1}, {y1}) um = {(x1 - x0):.2f} x {(y1 - y0):.2f} um "
          f"= {asm.report['area_um2']:.1f} um^2")
    print(f"block bbox sum: {asm.report['block_sum_um2']:.1f} um^2; "
          f"{len(asm.accesses)} port accesses; {asm.report['top_level_shapes']} top-level shapes")
    if args.check:
        from . import netcheck  # noqa: PLC0415

        rep = netcheck.check(asm.gds)
        print(rep.summary())
        return 0 if rep.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
