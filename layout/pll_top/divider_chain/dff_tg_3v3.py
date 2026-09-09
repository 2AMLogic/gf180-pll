"""``dff_tg_3v3`` -- the transmission-gate master-slave D flip-flop every
``div23_cell`` instance uses twice (and ``divider_chain``'s own retiming
flop ``XFRT`` uses once), assembled as a flat macro composition of six
``inv_3v3`` + four ``tgate_3v3`` instances (issue #308, Part 3 of #295's
device-layout methodology proof).

WHAT THIS BUILDS
-----------------
All 10 leaf-cell instances of ``design/dff_tg_3v3.sch`` -- 6x ``inv_3v3`` +
4x ``tgate_3v3``, 20 transistors total -- wired exactly per
``design/netlist/dff_tg_3v3.spice``'s own ``dff_tg_3v3`` subckt (a classic
master-slave latch: clock/clock-bar generation, then two transmission-gate
latches each built from a feedback inverter pair)::

    XICKB  CK  CKB   VDD VSS inv_3v3      -- clock inverter
    XICKBB CKB CKBB  VDD VSS inv_3v3      -- clock-bar inverter
    XTGMI  D   NM    CKB CKBB VDD VSS tgate_3v3   -- master pass gate
    XIA    NM  NMA   VDD VSS inv_3v3      -- master latch fwd inverter
    XIB    NMA NMB   VDD VSS inv_3v3      -- master latch feedback inverter
    XTGMF  NMB NM    CKBB CKB VDD VSS tgate_3v3   -- master latch feedback gate
    XTGSI  NMA NS    CKBB CKB VDD VSS tgate_3v3   -- slave pass gate
    XIC    NS  Q     VDD VSS inv_3v3      -- slave latch fwd inverter
    XID    Q   QB    VDD VSS inv_3v3      -- slave latch feedback inverter
    XTGSF  QB  NS    CKB CKBB VDD VSS tgate_3v3   -- slave latch feedback gate

WHY A COMPOSITE MACRO, NOT 10 ``build_stack_cell()`` CALLS
-------------------------------------------------------------
``devgen.build_stack_cell()`` (issue #306) resolves a net by counting how
many of *that one column's own* 1-2 device terminals share its name --
correct for a standalone leaf cell, where every net genuinely is local to
that column. Every net in this composite except each instance's own
supply pins fans out *across* instances (``CKB``/``CKBB`` alone each reach
four separate transmission-gate instances) -- outside what a per-column,
Metal1-only, at-most-2-terminal resolver can wire.

So this module places 10 columns side by side in one shared ``Canvas``
(:func:`devgen.draw_column` -- the bare drawing step ``build_stack_cell()``
performs internally, with its own per-column net resolution skipped) and
resolves every net itself, composite-wide, with
:func:`devgen.route_net` / :class:`devgen.NetTracks`: each device pad rides
its own dedicated Metal3 riser up to a Metal2 bus unique to that net,
exactly the fabric ``lock_detector/build.py`` already proved out for its
own (horizontal-flow) multi-gate composite -- see this repo's own
``layout/pll_top/lock_detector/`` package for that precedent and
``devgen.py``'s own "Composite-macro routing fabric" docstring section for
why this package's *vertical*-flow columns need one riser per pad rather
than lock_detector's own close-pad merge optimization.

This is flat macro-composition, not GDS-level ``CellInstArray`` placement
of 10 already-built leaf cells: ``lock_detector/cells.py``'s own module
docstring states the rationale (every PMOS comp box collected into one
shared list so exactly one nwell rectangle is ever drawn, instead of 10
separate per-instance nwells that would need their own NW.2a/NW.2b
minimum-spacing clearance from each other) -- the same reasoning applies
here unchanged. A per-instance nwell/tap (what ``build_stack_cell()``
draws for a *standalone* ``inv_3v3``/``tgate_3v3``) is deliberately not
reused for this composite: instead, one shared nwell encloses every PMOS
comp box across all 10 instances, with periodic ntap/ptap pairs dropped in
the gaps between columns (see ``_tap_positions()`` below) -- so
``Device.body_net``
(the field ``tgate_3v3.py``'s *standalone* leaf cell needs to keep its own
n-well tap off the ``A``/``Y`` diffusion nets) is not needed here either:
this composite's shared well ties every PMOS body through the well/tap
network alone, never through a per-device Metal1 short onto a diffusion
net.

ROW HEIGHT / PITCH
-------------------
Every column is drawn from the *same* two device tables
(``inv_3v3.INV_DEVICES`` / ``tgate_3v3.TGATE_DEVICES``, issue #306/#307),
stacked bottom-to-top in the same order (NMOS then PMOS) with the same
gaps -- so every instance's own NMOS/PMOS y-bands land at the identical y
regardless of which of the two device tables it uses, satisfying this
issue's own acceptance criterion that this cell's row height/pitch stay
consistent with #306/#307's leaf cells (needed for Part 4's ``div23_cell``
composite, which places two of these).

REFERENCE NETLIST
------------------
:func:`reference_netlist` is hand-written and independently stated (same
discipline ``inv_3v3.py``/``tgate_3v3.py`` document, citing
``layout/harness/cell.py``'s own convention), *fully flattened* to 20
individual ``M`` device lines rather than 10 ``X`` instance calls into
``inv_3v3``/``tgate_3v3`` subckt definitions -- matching this module's own
flat (non-hierarchical) GDS, so LVS compares device-for-device against
what was actually drawn. Device connectivity/sizes are derived directly by
hand-expanding ``design/netlist/dff_tg_3v3.spice``'s own ``X``-instance
list against its own (also flattened, in that same generated file)
``inv_3v3``/``tgate_3v3`` subckt bodies -- not re-derived from the
schematic in isolation. ``design/netlist/dff_tg_3v3.spice`` itself (already
self-contained -- it carries both subckt bodies inline, generated by
``design/netlist.sh``) is also usable as an LVS reference directly (its
``X``-instance hierarchy resolves against its own inlined subckt bodies);
this module's own hand-written, independently-stated flat netlist is used
instead for the same "layout and reference are stated independently, not
literally copy-derived from the same source" discipline
``inv_3v3.py``/``tgate_3v3.py`` already established.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import devgen, inv_3v3, tgate_3v3
from .devgen import Canvas, Device, NetTracks, draw_column, nwell_over, offset_pad_x, pad_center, route_net, well_tap

TOP_CELL = "dff_tg_3v3"

#: x pitch between two adjacent instance columns' own ``x0``. Every column's
#: rightmost drawn Metal1 (the PMOS device's own top/bottom pad, neither of
#: which needs ``offset_pad_x()`` to extend beyond its own W=2.5u footprint
#: -- see ``_TOP_PAD_OFFSET_UM``'s own docstring) sits at ``x0 + 2.5``;
#: every column's own gate-pad Metal1, *including* the pfet gate's own
#: ``offset_pad_x()`` extension (``_PFET_GATE_OFFSET_UM``), reaches back to
#: ``x0 - 1.8`` (see that constant's own derivation). This pitch (9.0)
#: leaves >= 4.7 um of clear Metal1 gap between one column's rightmost pad
#: and the next column's own gate-pad reach -- comfortably past M1.2a's
#: 0.23 um minimum and wide enough for a periodic n/p tap pair placed well
#: inside it with margin on both sides (see ``_tap_positions()``). An
#: earlier, tighter pitch (7.0, sized only for the *un-offset* gate-pad
#: reach) passed DRC clean right up until the periodic tap pair's own
#: ``offset_pad_x()`` reach and the *next* column's own offset gate-pad
#: reach turned out to close within 0.24 um of each other -- under M3.2a's
#: 0.28 um Metal3 spacing floor -- a real, concretely-observed violation
#: this wider pitch fixes with margin to spare, not merely "enough."
COLUMN_PITCH_UM = 9.0

#: Instance table: ``(name, kind, device_table, port_map)``. ``port_map``
#: translates each device's *local* role -- ``inv_3v3``'s own ``"A"``/``"Y"``/
#: ``"VDD"``/``"VSS"``, or ``tgate_3v3``'s own ``"A"``/``"Y"``/``"GN"``/
#: ``"GP"`` (see those modules' own ``INV_DEVICES``/``TGATE_DEVICES``) --
#: into this composite's own net name, exactly per
#: ``design/netlist/dff_tg_3v3.spice``'s ``X``-instance argument order.


def _inv(name: str, a: str, y: str) -> tuple[str, str, tuple[Device, ...], dict[str, str]]:
    return (name, "inv", inv_3v3.INV_DEVICES, {"A": a, "Y": y, "VDD": "VDD", "VSS": "VSS"})


def _tgate(name: str, a: str, y: str, gn: str, gp: str) -> tuple[str, str, tuple[Device, ...], dict[str, str]]:
    return (name, "tgate", tgate_3v3.TGATE_DEVICES, {"A": a, "Y": y, "GN": gn, "GP": gp})


INSTANCES: tuple[tuple[str, str, tuple[Device, ...], dict[str, str]], ...] = (
    _inv("XICKB", "CK", "CKB"),
    _inv("XICKBB", "CKB", "CKBB"),
    _tgate("XTGMI", "D", "NM", "CKB", "CKBB"),
    _inv("XIA", "NM", "NMA"),
    _inv("XIB", "NMA", "NMB"),
    _tgate("XTGMF", "NMB", "NM", "CKBB", "CKB"),
    _tgate("XTGSI", "NMA", "NS", "CKBB", "CKB"),
    _inv("XIC", "NS", "Q"),
    _inv("XID", "Q", "QB"),
    _tgate("XTGSF", "QB", "NS", "CKB", "CKBB"),
)

#: This cell's own top-level I/O (``design/dff_tg_3v3.sch``'s subckt ports).
#: The other six nets this composite carries (``CKB``, ``CKBB``, ``NM``,
#: ``NMA``, ``NMB``, ``NS``) are internal-only -- wired (via the shared
#: Metal2/3 bus fabric) but not pin-labelled, the same convention
#: ``inv_3v3``/``tgate_3v3`` already use for their own internal 2-terminal
#: nets (see ``devgen.py``'s docstring).
BOUNDARY_NETS: tuple[str, ...] = ("D", "CK", "Q", "QB", "VDD", "VSS")

#: A column's own rightmost drawn PMOS edge, relative to its own ``x0`` --
#: both ``inv_3v3``/``tgate_3v3`` device tables put a W=2.5u pfet at the top
#: of the stack (see their own ``INV_DEVICES``/``TGATE_DEVICES``).
_COLUMN_RIGHT_EDGE_UM = 2.5

#: A column's own gate-pad left reach, relative to its own ``x0``, *after*
#: ``_PFET_GATE_OFFSET_UM``'s own ``offset_pad_x()`` extension (natural
#: reach 1.12 + 0.75 offset + 0.22 via half-width, rounded up) -- see
#: ``COLUMN_PITCH_UM``'s own derivation above.
_COLUMN_GATE_REACH_UM = 1.8

#: :func:`devgen.offset_pad_x` deltas applied when collecting a device's
#: pads for composite-level routing -- see that function's own docstring
#: for the concrete LVS-merged-node failure this fixes: a device's own top
#: and bottom terminal pads (and, for ``tgate_3v3``'s independent-gate
#: devices, its own gate pad vs. its column-mate's) sit at the *same* x by
#: construction, and an unoffset composite riser at that shared x collapses
#: two different nets' Metal3 paths into one polygon. ``_TOP_PAD_OFFSET_UM``
#: moves every device's *top* pad's riser well clear of its own *bottom*
#: pad's (natural, unmodified) riser; ``_PFET_GATE_OFFSET_UM`` (negative --
#: further left, away from every column's own devices, which are
#: exclusively at x >= 0) does the same for a pfet's gate pad against its
#: nfet column-mate's (natural) one. 0.75 um center-to-center clears
#: M3.2a's 0.28 um minimum Metal3 spacing against the natural (unmodified)
#: riser it must not collide with (0.75 - METAL3_WIRE_WIDTH_UM(0.34) = 0.41
#: um clear, well past the 0.28 um floor) while staying small enough that
#: ``offset_pad_x()`` needs *no* extra Metal1 reach at all for every
#: ``pfet`` pad (whose own W=2.5u footprint already encloses a via this far
#: off-center) and only a small one for the narrower ``nfet`` pads/gates --
#: see that function's own docstring for the earlier, larger-offset attempt
#: that reached far enough to nearly short a periodic n-well tap instead.
_TOP_PAD_OFFSET_UM = 0.75
_PFET_GATE_OFFSET_UM = -0.75

#: Same fix, applied to one periodic tap pair's own ptap (offset) against
#: its ntap (natural) -- see the same-x collision note where the tap pair
#: is placed, below.
_TAP_OFFSET_UM = 0.8

#: y0 of each periodic tap, centred in that instance's own NMOS/PMOS y-band
#: (``devgen.draw_column()``'s fixed stacking: NMOS at y in [0, 1.28], PMOS
#: at y in [5.28, 6.56] -- see ``devgen.mosfet()``'s
#: ``SD_OVERHANG_UM``/``NWELL_TO_NMOS_GAP_UM`` derivation for those exact
#: bounds), so each tap sits well clear of both bands' own comp/poly (>=
#: ``devgen.TAP_GAP_UM`` in y as well as x).
_PTAP_Y0_UM = 0.34
_NTAP_Y0_UM = 5.62


@dataclass
class DffLayout:
    canvas: Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, tuple[float, float]] = field(default_factory=dict)
    nwell_box: tuple[float, float, float, float] | None = None

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def _place() -> list[float]:
    """x0 for each of the 10 instances, in ``INSTANCES`` order."""
    return [i * COLUMN_PITCH_UM for i in range(len(INSTANCES))]


#: How far a tap pair's own ntap sits past the *left* column's rightmost
#: Metal1 reach -- clear of both ``devgen.TAP_GAP_UM``'s comp/poly floor
#: and (with ``_TAP_OFFSET_UM`` added on top for the ptap side) M3.2a's
#: Metal3 spacing floor against the *right* column's own offset gate-pad
#: reach. See ``COLUMN_PITCH_UM``'s own docstring for the concrete
#: violation an earlier, tighter placement hit.
_TAP_LEFT_MARGIN_UM = 1.5


def _tap_positions(xs: Sequence[float]) -> list[float]:
    """The ntap x position for every inter-column gap's own tap pair --
    ``_TAP_LEFT_MARGIN_UM`` past the left column's own rightmost Metal1
    reach, not the gap's geometric midpoint (see ``_TAP_LEFT_MARGIN_UM``'s
    own docstring for why a fixed left-anchored offset, not a midpoint,
    is what actually keeps clear of the *right* column's own reach once
    the ptap's own :func:`devgen.offset_pad_x` extension is accounted for).
    """
    return [x0_prev + _COLUMN_RIGHT_EDGE_UM + _TAP_LEFT_MARGIN_UM for x0_prev in xs[:-1]]


def build(outdir: Path | None = None) -> DffLayout:
    canvas = Canvas(TOP_CELL)
    nets: dict[str, list[tuple[float, float]]] = {}
    pfet_boxes: list[tuple[float, float, float, float]] = []
    #: every drawn comp-bearing box (device + tap) -- used only for the
    #: reported footprint's own bounds, not for any DRC-relevant drawing.
    device_boxes: list[tuple[float, float, float, float]] = []

    def _add(net: str, pad: tuple[float, float, float, float]) -> None:
        nets.setdefault(net, []).append(pad_center(pad))

    def _add_point(net: str, point: tuple[float, float]) -> None:
        nets.setdefault(net, []).append(point)

    xs = _place()
    for x0, (_name, _kind, devices, port_map) in zip(xs, INSTANCES):
        ports = draw_column(canvas, devices, x0)
        for d, p in zip(devices, ports):
            # See _TOP_PAD_OFFSET_UM/_PFET_GATE_OFFSET_UM's own docstring
            # comment above: bottom pads stay at their natural center;
            # every top pad and every pfet's gate pad get an extra Metal1
            # reach so their composite-level riser lands at a different x
            # than their own column-mate's (same device's bottom pad, or --
            # for tgate_3v3 -- the other device's independent gate pad).
            gate_point = (
                offset_pad_x(canvas, p.gate_pad, _PFET_GATE_OFFSET_UM)
                if p.kind == "pfet"
                else pad_center(p.gate_pad)
            )
            top_point = offset_pad_x(canvas, p.top_pad, _TOP_PAD_OFFSET_UM)
            _add_point(port_map[d.gate_net], gate_point)
            _add_point(port_map[d.top_net], top_point)
            _add(port_map[d.bottom_net], p.bottom_pad)
            box = (p.x0, p.y0, p.x1, p.y3)
            device_boxes.append(box)
            if p.kind == "pfet":
                pfet_boxes.append(box)

    # --- periodic n/p tap pairs, one per inter-column gap, at
    # _tap_positions()'s own left-anchored x (see that function's own
    # docstring for why not the gap's geometric midpoint). Tied into the
    # same VDD/VSS nets every device's own supply pad already feeds, so
    # they ride the same composite-level Metal2 bus. The ntap and ptap of
    # one pair sit at the *same* x but very different y (PMOS band vs. NMOS
    # band) -- exactly the same same-x, different-net riser collision
    # offset_pad_x()'s own docstring documents for a device's own top/
    # bottom pads, concretely observed here too (VDD/VSS merged into one
    # node on a first, unoffset attempt at this tap pair). ntap's own riser
    # stays at the tap's natural center; ptap's is offset -- same fix, same
    # rationale, applied to the tap fabric instead of a device's own
    # pads. ---
    ntap_boxes: list[tuple[float, float, float, float]] = []
    half_tap = devgen.TAP_SIZE_UM / 2.0
    for gx in _tap_positions(xs):
        ntap_pad = well_tap(canvas, "n", gx - half_tap, _NTAP_Y0_UM, "VDD")
        _add("VDD", ntap_pad)
        ntap_box = (gx - half_tap, _NTAP_Y0_UM, gx + half_tap, _NTAP_Y0_UM + devgen.TAP_SIZE_UM)
        ntap_boxes.append(ntap_box)
        device_boxes.append(ntap_box)
        ptap_pad = well_tap(canvas, "p", gx - half_tap, _PTAP_Y0_UM, "VSS")
        _add_point("VSS", offset_pad_x(canvas, ptap_pad, _TAP_OFFSET_UM))
        device_boxes.append((gx - half_tap, _PTAP_Y0_UM, gx + half_tap, _PTAP_Y0_UM + devgen.TAP_SIZE_UM))

    # --- one shared nwell enclosing every PMOS comp box + every ntap's own
    # comp box (not just its net -- see devgen.py's "WELL/SUBSTRATE TIES"). ---
    nwell_box = nwell_over(canvas, pfet_boxes + ntap_boxes)

    # --- route every net once, each on its own Metal2 track, well clear of
    # every device/tap/nwell shape (see NetTracks' monotonic-track-per-net
    # guarantee). ---
    tracks = NetTracks(base_y=nwell_box[3] + 3.0)
    for net, pads in nets.items():
        route_net(canvas, net, pads, tracks.get(net))

    # --- boundary pin labels (Metal1, purpose 10 -- the purpose gf180mcu's
    # own LVS deck actually reads, see devgen.py's docstring), one per
    # top-level I/O net, dropped on that net's own first device pad (not the
    # Metal2 bus) so the label sits on real Metal1 the LVS deck's
    # ``metal1_con`` extraction already covers. ---
    pins: dict[str, tuple[float, float]] = {}
    for net in BOUNDARY_NETS:
        x, y = nets[net][0]
        canvas.label("metal1_label", net, x, y)
        pins[net] = (x, y)

    last_track_y = max(tracks.get(net) for net in nets)
    footprint = (
        min(b[0] for b in device_boxes) - _COLUMN_GATE_REACH_UM,
        min(b[1] for b in device_boxes),
        max(b[2] for b in device_boxes),
        last_track_y + devgen.METAL2_WIRE_WIDTH_UM,
    )

    layout = DffLayout(canvas=canvas, footprint=footprint, pins=pins, nwell_box=nwell_box)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def reference_netlist() -> str:
    """Hand-written, independently-stated, fully-flattened LVS reference
    netlist -- see this module's own docstring ("REFERENCE NETLIST") for why
    flat (20 ``M`` lines) rather than hierarchical (10 ``X`` calls into
    ``inv_3v3``/``tgate_3v3``).
    """
    pfet = "pfet_03v3 W=2.5u L=0.28u"
    nfet = "nfet_03v3 W=1u L=0.28u"

    def _inv_lines(tag: str, a: str, y: str) -> str:
        return f"M_{tag}_P {y} {a} VDD VDD {pfet}\nM_{tag}_N {y} {a} VSS VSS {nfet}\n"

    def _tgate_lines(tag: str, a: str, y: str, gn: str, gp: str) -> str:
        return f"M_{tag}_P {y} {gp} {a} VDD {pfet}\nM_{tag}_N {a} {gn} {y} VSS {nfet}\n"

    body = (
        _inv_lines("ICKB", "CK", "CKB")
        + _inv_lines("ICKBB", "CKB", "CKBB")
        + _tgate_lines("TGMI", "D", "NM", "CKB", "CKBB")
        + _inv_lines("IA", "NM", "NMA")
        + _inv_lines("IB", "NMA", "NMB")
        + _tgate_lines("TGMF", "NMB", "NM", "CKBB", "CKB")
        + _tgate_lines("TGSI", "NMA", "NS", "CKBB", "CKB")
        + _inv_lines("IC", "NS", "Q")
        + _inv_lines("ID", "Q", "QB")
        + _tgate_lines("TGSF", "QB", "NS", "CKB", "CKBB")
    )
    return (
        "* Reference schematic for dff_tg_3v3 (issue #308).\n"
        "*\n"
        "* Hand-written independently of the layout, fully flattened to 20 M\n"
        "* device lines (not X-instance calls into inv_3v3/tgate_3v3) -- see\n"
        "* this module's own docstring (\"REFERENCE NETLIST\") for why, and\n"
        "* layout/harness/cell.py's docstring for the general discipline.\n"
        "* Connectivity/sizes derived by hand-expanding\n"
        "* design/netlist/dff_tg_3v3.spice's own X-instance list against its\n"
        "* own inlined inv_3v3/tgate_3v3 subckt bodies.\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        f".subckt {TOP_CELL} D CK Q QB VDD VSS\n"
        f"{body}"
        ".ends\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "divider-dff-proof" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"wrote {netlist_path}")
    print(f"instances : {len(INSTANCES)} (6 inv_3v3 + 4 tgate_3v3)")
    print("devices   : 20")
    print(f"footprint : {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    print(f"pins      : {sorted(layout.pins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
