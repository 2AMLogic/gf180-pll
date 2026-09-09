"""``cp_output_stage`` -- the charge pump's complete output-stage block:
Part 3b's N/P common-centroid arrays plus the trim/steer glue inverters and
the steering/dump switches, wired per ``design/cp.sch`` (issue #321, Part 3c
of #294's device-layout methodology, the last of #301's three decomposition
steps).

WHAT THIS BUILDS
-----------------
One flat, standalone-DRC-clean GDS containing:

* ``cp_array`` (issue #320, Part 3b) -- the 4x ``cp_leg_n`` / 4x ``cp_leg_p``
  common-centroid arrays and their 4x-scaled bias branches, placed
  unmodified at this block's own origin.
* The four glue inverters ``xi_b0``/``xi_b1``/``xi_up``/``xi_dn`` -- four
  placements of issue #299's already-proven ``pfdcp_inv_3v3`` leaf cell
  (:data:`GLUE_INVERTERS`), producing ``B0B``/``B1B``/``UPB``/``DNB`` from
  ``B0``/``B1``/``UP``/``DN``.
* The six steering/dump switches ``MSWDN``/``MDMPDN``/``MSWUP``/``MDMPUP``/
  ``MDUMN``/``MDUMP`` -- single ``nfet_03v3``/``pfet_03v3`` devices drawn
  with ``devgen.mosfet()`` (:data:`SWITCH_DEVICES_N`/
  :data:`SWITCH_DEVICES_P`), sizes and terminal nets read directly off
  ``design/cp.sch``'s own instance parameters and ``lab_pin`` labels.

``VDUMP`` is deliberately left a **stub pin**: ``MDMPDN``'s and ``MDMPUP``'s
drains meet on it and nothing else drives it. ``cp_dumpbuf`` (``xbuf``) is
Part 4 (#302, already built as its own standalone cell) and its
instantiation into this block is Part 5 (#303) -- see this issue's own "Out
of scope" section. Everything else ``design/cp.sch`` draws *is* here, so the
block's twelve boundary nets are exactly :data:`BOUNDARY_PINS`.

WHAT THIS BLOCK IS NOT YET: A COMPLETE-CIRCUIT LVS CLAIM
------------------------------------------------------------
This block is DRC-clean, and its own wiring -- both what this increment
adds and the ``cp_array`` sub-block it assembles -- is verified short-free
and fully connected by :mod:`netcheck` (see below). Earlier revisions of
this module (issue #321's own first landing) shipped alongside a
pre-existing cross-net short defect inherited from ``cp_array``'s own
routing, recorded as :data:`INHERITED_ARRAY_SHORTS`; that defect is fixed
(issue #359, ``cp_array.py``'s own module docstring, "EN/ENB SHARE ONE
GATE-TAB COLUMN") and the constant is now the empty tuple its own docstring
always said it would become. This block still makes **no LVS claim**, for
the same reason ``cp_array``'s own proof states:
this block is a strict *subset* of ``cp.sch`` (``xbuf`` excluded), so an LVS
run against that schematic's own netlist would legitimately mismatch on the
dump buffer's devices. The complete-circuit LVS belongs to Part 5 (#303),
where ``xbuf`` lands and the block finally corresponds 1:1 to ``cp.sch``.

REACHING THE ARRAY BLOCK'S NETS: EXTEND ITS BUS, DON'T RE-RISE ON ITS PADS
--------------------------------------------------------------------------
``cp_array`` has already mesh-routed every one of its own nets: each net's
Metal1 pads carry a Via1/Metal2/Via2/Metal3 riser up to that net's own
dedicated Metal2 track. Landing a *second* via stack on one of those same
Metal1 pads -- the obvious way to "connect to a pin" -- puts two Via1/Via2
squares and two Metal2 landing pads a fraction of a micron apart, which is a
hard ``V1.1``/``V2.1``/``M2.2a`` violation (an overlapping-but-not-identical
pair of via squares merges into one oversized shape; ``CO.1``-class rules
make the via size a min *and* a max). Spacing rules in this deck are purely
geometric -- being the same net buys nothing.

So this module reaches each array net through the *end of its Metal2 bus*
instead, which ``cp_array`` now reports as ``CpArrayLayout.n_bus``/``p_bus``
(``net -> (track_y, x_lo, x_hi)``; the one additive change this increment
makes to Part 3b -- it draws no geometry and leaves that block's own GDS
byte-identical). For each net shared between the array and this block's own
glue mesh, :func:`build` extends that bus sideways into empty space
(:func:`_extend_bus`), extends this block's own glue-mesh track to the same
column, and links the two with a plain Metal3 vertical
(:func:`_link_tracks`). The N side's buses extend **left** and the P side's
**right** -- never across each other, since an N net's track and a P net's
track can coincide in Y by coincidence (the two sides get independent
channels, each based on its own side's height) and two same-Y Metal2 runs
that overlapped in X would be a silent short between different nets.

That column region is also what ties the two polarities' trim nets together
for the first time: ``cp_array`` deliberately leaves ``B0``/``B0B``/``B1``/
``B1B`` (and ``VDD``/``VSS``) disconnected between its N and P sides,
because joining them is glue-level wiring -- this module's job.

ONE ROW, HAND-PLACED RISER COLUMNS: WHY NOT JUST DECLUTTER
------------------------------------------------------------
``cp_array.declutter_riser_x()`` is safe there because of an invariant that
module's own docstring states explicitly: two risers land on the *literal
same* X only when they belong to the same net. That invariant is **false**
here. A three-terminal switch's source and drain pads share one X by
construction (both are centred on the same comp), and they are different
nets on four of the six switches; two glue inverters' pin pads cluster
within ~2 um of each other; and two device rows stacked in Y would put two
different nets' pads at identical X wholesale. Any of those, fed to a
nudge-based declutterer, either shorts two nets onto one Metal3 column or
drags a Metal1 stub off its pad into a neighbour.

This module therefore places every device in **one row** (so X is
monotonic), and gives every riser an explicitly chosen X:

* a device's gate pad and top (drain/source) pad already sit >1 um apart in
  X, so they rise where they are;
* a device whose top and bottom terminals are *different* nets gets its
  bottom pad escaped sideways on Metal1 (:func:`_escape`) to a column past
  its own comp -- :data:`SWITCH_DEVICE_GAP_UM` is sized so that landing
  clears the next device's own gate pad;
* a device whose top and bottom terminals are the *same* net (``MDUMN``/
  ``MDUMP``, the half-width injection dummies with both diffusions on
  ``VOUT``) needs no escape -- two risers at one X on one net is exactly the
  case ``cp_array`` already proves safe;
* each glue inverter's ``Y``/``VSS``/``VDD`` pins escape right to
  :data:`INV_ESCAPE_UM`'s three columns (its ``A`` pin's own gate-tab pad is
  already clear to the left).

:func:`check_riser_columns` then asserts, arithmetically, that the resulting
column set needs no decluttering at all (running ``declutter_riser_x()``
over it is the identity) -- so the invariant this placement depends on is
checked on every build and in ``layout/tests/test_cp_output_stage.py``,
rather than being a comment that could go stale the next time a device size
changes.

MESH ROUTING
-------------
The glue block's own nets are routed by ``cp_array._route_side()`` -- the
same Metal1/Via1/Metal2/Via2/Metal3 riser fabric Part 3b already proved
DRC-clean, *imported* rather than re-authored, because this is the same
block family and the same module's own routing channel convention (see
``devgen.py``'s "each full-custom leaf-cell family owns its own generator"
note -- ``cp_array`` and ``cp_output_stage`` are one family). It is called
with ``promote_pins=False``: this block promotes its own twelve boundary
pins explicitly (:data:`BOUNDARY_PINS`), rather than exposing every internal
node (``DNT``, ``UPT``, ``B0B``, ``B1B``, ``UPB``, ``DNB``) as a pin.

CONNECTIVITY IS CHECKED, NOT ASSUMED
--------------------------------------
:meth:`CpOutputStageLayout.probe_pads` hands every Metal1 landing pad this
block believes is on each net -- the array's own promoted pins on *both*
polarities, plus every riser landing of the glue mesh -- to
:func:`netcheck.check_gds`, which extracts the finished GDS's own Metal1-3
connectivity with KLayout and reports which nets actually share a component.
That is what proves the link columns really did tie the two polarities'
trim bits and rails together (an *open* there would be as invisible to DRC
as a short), and it is what found :data:`INHERITED_ARRAY_SHORTS`. It runs
from this module's own ``main()`` and from
``layout/tests/test_cp_output_stage.py``.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import cp_array, devgen, netcheck, pfdcp_inv

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention -- see
    # cp_array.py's own identical try/except for the full citation.
    import _canvas

TOP_CELL = "cp_output_stage"

Device = devgen.Device

# ---------------------------------------------------------------------------
# design/cp.sch's own device/instance tables. Nothing here is re-derived:
# every W/L is that schematic's own instance parameter and every net name is
# one of its own lab_pin labels.
# ---------------------------------------------------------------------------

SWITCH_L_UM = 0.3
"""``design/cp.sch``: every steering/dump switch is ``L=0.3u``."""

SWITCH_W_UM = 6.0
"""``design/cp.sch``: ``MSWDN``/``MDMPDN``/``MSWUP``/``MDMPUP`` are all
``W=6u`` -- equal *widths*, not equal strengths, per that schematic's own
"Switch sizing" note (these pass microamps, so they are sized for charge
symmetry, and a mobility-ratio-scaled P device would inject a net residue
onto the control node at every switching event)."""

DUMMY_W_UM = 3.0
"""``design/cp.sch``: ``MDUMN``/``MDUMP`` are the half-width injection
dummies (``W=3u``), both diffusions tied to ``VOUT`` and gated by the
complementary control."""

#: ``design/cp.sch``'s N-side switches, in this module's own left-to-right
#: placement order. ``top_net``/``bottom_net`` follow ``devgen``'s
#: vertical-stack convention (``top_net`` nearer the top of the drawn
#: device): for these NMOS devices the schematic's drain is drawn on top.
SWITCH_DEVICES_N: tuple[Device, ...] = (
    # MSWDN: D=VOUT G=DN  S=DNT B=VSS -- steers the N tail into VOUT on DN.
    Device(name="MSWDN", kind="nfet", w_um=SWITCH_W_UM, l_um=SWITCH_L_UM, gate_net="DN", top_net="VOUT", bottom_net="DNT"),
    # MDMPDN: D=VDUMP G=DNB S=DNT B=VSS -- parks the same tail on VDUMP otherwise.
    Device(name="MDMPDN", kind="nfet", w_um=SWITCH_W_UM, l_um=SWITCH_L_UM, gate_net="DNB", top_net="VDUMP", bottom_net="DNT"),
    # MDUMN: D=S=VOUT G=DNB B=VSS -- charge-injection dummy.
    Device(name="MDUMN", kind="nfet", w_um=DUMMY_W_UM, l_um=SWITCH_L_UM, gate_net="DNB", top_net="VOUT", bottom_net="VOUT"),
)

#: ``design/cp.sch``'s P-side switches. For these PMOS devices the
#: schematic's *source* is drawn on top (toward ``VDD``), matching
#: ``pfdcp_inv.py``'s own ``MP`` record and ``devgen``'s convention.
SWITCH_DEVICES_P: tuple[Device, ...] = (
    # MSWUP: S=UPT G=UPB D=VOUT B=VDD.
    Device(name="MSWUP", kind="pfet", w_um=SWITCH_W_UM, l_um=SWITCH_L_UM, gate_net="UPB", top_net="UPT", bottom_net="VOUT"),
    # MDMPUP: S=UPT G=UP D=VDUMP B=VDD.
    Device(name="MDMPUP", kind="pfet", w_um=SWITCH_W_UM, l_um=SWITCH_L_UM, gate_net="UP", top_net="UPT", bottom_net="VDUMP"),
    # MDUMP: D=S=VOUT G=UP B=VDD -- charge-injection dummy.
    Device(name="MDUMP", kind="pfet", w_um=DUMMY_W_UM, l_um=SWITCH_L_UM, gate_net="UP", top_net="VOUT", bottom_net="VOUT"),
)


@dataclass(frozen=True)
class InverterSpec:
    """One ``pfdcp_inv_3v3`` glue-inverter instance from ``design/cp.sch``."""

    name: str
    a_net: str
    y_net: str


#: ``design/cp.sch``'s own ``xi_b0``/``xi_b1``/``xi_up``/``xi_dn`` instances,
#: in this module's own left-to-right placement order.
GLUE_INVERTERS: tuple[InverterSpec, ...] = (
    InverterSpec(name="xi_b0", a_net="B0", y_net="B0B"),
    InverterSpec(name="xi_b1", a_net="B1", y_net="B1B"),
    InverterSpec(name="xi_up", a_net="UP", y_net="UPB"),
    InverterSpec(name="xi_dn", a_net="DN", y_net="DNB"),
)

#: ``design/cp.sch``'s own ``ipin``/``iopin`` declarations (``P0``-``P10``)
#: plus ``VDUMP``, which is a real boundary net of *this* block because the
#: buffer that would otherwise terminate it (``xbuf``) is out of scope here.
BOUNDARY_PINS: tuple[str, ...] = (
    "UP", "DN", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "VDD", "VSS", "VDUMP",
)

#: Nets ``design/cp.sch`` creates inside this block and does not export --
#: asserted absent from :data:`BOUNDARY_PINS` (and from ``build()``'s own
#: promoted pin set) so a wiring slip cannot silently publish one.
INTERNAL_NETS: tuple[str, ...] = ("B0B", "B1B", "UPB", "DNB", "DNT", "UPT")

INHERITED_ARRAY_SHORTS: tuple[frozenset[str], ...] = ()
"""Cross-net shorts this block once **inherited** from ``cp_array`` (issue
#320, merged via PR #351) -- ``B0``/``B0B`` and ``B1``/``B1B``/``VDD``/
``VSS``, reproducible against ``cp_array``'s own standalone GDS with
:func:`netcheck.check_gds`. Fixed by issue #359: ``cp_array.declutter_riser_x()``
used to collapse any two riser candidates sharing an *exact* natural X onto
one shared column, reasoning that this could only happen for two pads of
the *same* net -- false twice over (``cp_leg_n``'s/``cp_leg_p``'s own
``EN``/``ENB`` gate-tab pads always share one local X, and every leg maps
them to two *different* nets; and the tripod places ``t1b`` directly above
``base``, so their own ``EN``/``ENB`` pins collide too). See
``cp_array.py``'s own module docstring, "EN/ENB SHARE ONE GATE-TAB COLUMN",
for the fix: an explicitly-allocated riser column per net, reached by a
checked Metal1 escape -- the same scheme this module already used for its
own glue block, now ported to the array's own pads too.

This tuple is asserted **exactly** by ``layout/tests/test_cp_output_stage.py``
(now asserting it is empty) so a regression here can neither grow silently
nor be quietly forgotten.
"""


# ---------------------------------------------------------------------------
# Placement margins (um). See the module docstring for what each one buys.
# ---------------------------------------------------------------------------

GLUE_GAP_UM = 6.0
"""``cp_array``'s own topmost Metal2 routing track -> this block's own
lowest drawn edge (the switch row's substrate tap strip). Metal-only
clearance in practice -- the array's nearest *device* geometry is a further
``cp_array.CHANNEL_MARGIN_UM`` plus a full routing channel below that -- so
this is design margin, not a DRC minimum."""

SWITCH_DEVICE_GAP_UM = 5.0
"""Side-by-side clearance between two switch devices in the row. Larger
than ``cp_array.BIAS_DEVICE_GAP_UM`` (2.0) on purpose: it has to fit a
device's own :func:`_escape` landing (:data:`SWITCH_ESCAPE_UM` past its comp,
plus the landing pad's own half-width) clear of the *next* device's own
gate-tab Metal1 pad, which hangs ~1.1 um to the left of that device's comp.
:func:`check_escape_clearance` proves the arithmetic on every build."""

SWITCH_ESCAPE_UM = 1.5
"""How far past its own comp's right edge a switch's bottom-terminal Metal1
escape runs, when that terminal is a different net from the top one."""

SWITCH_WELL_GAP_UM = devgen.NWELL_TO_NMOS_GAP_UM
"""N group's rightmost comp -> P group's leftmost comp, in the shared row --
the same ``DF.16_LV``-derived clearance ``devgen.build_stack_cell()`` uses
across a well boundary in its own column (direction-agnostic)."""

INV_GROUP_GAP_UM = 4.0
"""P switch group's rightmost comp -> first glue inverter's own comp."""

INV_PITCH_UM = 8.0
"""Glue-inverter instance pitch. The leaf cell is only ~2.8 um wide; the
pitch is set by its own three right-hand escape columns
(:data:`INV_ESCAPE_UM`) plus a clear gap to the next instance's gate pad."""

INV_ESCAPE_UM: tuple[float, float, float] = (2.0, 3.5, 5.0)
"""Escape columns for one glue inverter's ``Y``/``VSS``/``VDD`` pins,
relative to that instance's own origin. Its ``A`` pin needs none -- the
shared gate-tab pad already sits ~0.8 um to the *left* of the comp, further
from every other pad of that instance than one column pitch."""

CONN_COLUMN_MARGIN_UM = 2.0
"""Whole-block bounding box -> the first array<->glue link column."""

CONN_COLUMN_PITCH_UM = cp_array.RISER_MIN_PITCH_UM
"""Centre-to-centre X between two link columns. Same value (and the same
``M3.2a`` headroom argument) as ``cp_array``'s own riser pitch."""

RISER_MIN_PITCH_UM = cp_array.RISER_MIN_PITCH_UM

LANDING_HALF_UM = cp_array.VIA1_SIZE_UM / 2.0 + cp_array.VIA_ENCLOSURE_UM
"""Half-width of a Metal1/Metal2 via landing pad -- ``V1.3a``/``V2.3b``
enclosure, identical derivation to ``cp_array._riser()``'s own."""

SWITCH_ROW_H_UM = 2.0 * devgen.SD_OVERHANG_UM + SWITCH_L_UM


# ---------------------------------------------------------------------------
# Pure-Python placement math -- no klayout import, testable with no PV
# environment (same convention as cp_array.py's own leg_offsets()/
# check_common_centroid()).
# ---------------------------------------------------------------------------


def switch_row_x(
    devices_n: Sequence[Device] = SWITCH_DEVICES_N,
    devices_p: Sequence[Device] = SWITCH_DEVICES_P,
    x0: float = 0.0,
    device_gap_um: float = SWITCH_DEVICE_GAP_UM,
    well_gap_um: float = SWITCH_WELL_GAP_UM,
) -> dict[str, tuple[float, float]]:
    """``device name -> (comp x0, comp x1)`` for the single switch row.

    The N group is placed left-to-right at ``device_gap_um`` spacing, then
    the P group after a ``well_gap_um`` well-boundary gap. Pure arithmetic:
    no geometry is drawn, so a test can check the row's own spacing
    invariants with no PV environment.
    """
    placed: dict[str, tuple[float, float]] = {}
    x = x0
    for i, dev in enumerate(devices_n):
        if i:
            x += device_gap_um
        placed[dev.name] = (x, x + dev.w_um)
        x += dev.w_um
    x += well_gap_um
    for i, dev in enumerate(devices_p):
        if i:
            x += device_gap_um
        placed[dev.name] = (x, x + dev.w_um)
        x += dev.w_um
    return placed


def gate_pad_center_x(comp_x0: float) -> float:
    """X of a ``devgen.mosfet()`` gate-tab Metal1 pad's own centre, for a
    device whose comp starts at ``comp_x0``.

    Re-derived from ``devgen``'s own constants rather than hardcoded: the tab
    hangs off the poly end-cap (``gate_x0 = comp_x0 - POLY_ENDCAP_UM``),
    overlaps it by ``GATE_TAB_OVERLAP_UM``, and is ``GATE_TAB_W_UM`` wide.
    """
    tab_x1 = comp_x0 - devgen.POLY_ENDCAP_UM + devgen.GATE_TAB_OVERLAP_UM
    return tab_x1 - devgen.GATE_TAB_W_UM / 2.0


def check_escape_clearance(
    row: dict[str, tuple[float, float]],
    order: Sequence[str],
    escape_um: float = SWITCH_ESCAPE_UM,
    landing_half_um: float = LANDING_HALF_UM,
    min_gap_um: float = devgen.METAL1_PAD_MARGIN_UM,
) -> float:
    """Raise unless every switch's Metal1 escape landing clears the *next*
    device's own gate-tab pad in X. Returns the tightest clearance found.

    This is the one thing :data:`SWITCH_DEVICE_GAP_UM` has to buy, stated as
    arithmetic rather than as a comment: an escape landing that reached into
    the neighbour's gate pad would merge two unrelated nets on Metal1 -- a
    short the DRC deck cannot see (nothing is spaced too closely; the two
    shapes simply become one polygon).
    """
    worst = float("inf")
    for name, nxt in zip(order, order[1:]):
        landing_x1 = row[name][1] + escape_um + landing_half_um
        gate_pad_x0 = gate_pad_center_x(row[nxt][0]) - devgen.GATE_TAB_W_UM / 2.0 - devgen.METAL1_PAD_MARGIN_UM
        gap = gate_pad_x0 - landing_x1
        worst = min(worst, gap)
        if gap < min_gap_um:
            raise ValueError(
                f"{name}'s escape landing (x1={landing_x1:.3f}) is only {gap:.3f} um "
                f"from {nxt}'s gate pad (x0={gate_pad_x0:.3f}); needs >= {min_gap_um}"
            )
    return worst


def check_riser_columns(
    points: Sequence[tuple[str, float, float]], min_pitch: float = RISER_MIN_PITCH_UM
) -> None:
    """Raise unless ``points`` (``(net, x, y)`` riser candidates) already
    satisfy ``cp_array.declutter_riser_x()``'s own separation rule *without*
    being decluttered -- i.e. running it is the identity.

    Two distinct X closer than ``min_pitch`` would be nudged (dragging a
    Metal1 stub off its pad), and two *equal* X belonging to two *different*
    nets would be left co-located, putting two nets on one Metal3 column: a
    real short, and one the DRC deck cannot report (the two runs merge into a
    single legal polygon). This module's placement is designed so neither
    ever happens -- see the module docstring -- and this is that design's
    proof, re-checked on every build.
    """
    by_x: dict[float, set[str]] = {}
    for net, x, _y in points:
        by_x.setdefault(round(x, 6), set()).add(net)
    for x, nets in sorted(by_x.items()):
        if len(nets) > 1:
            raise ValueError(f"riser column x={x} carries more than one net: {sorted(nets)}")
    xs = sorted(by_x)
    for a, b in zip(xs, xs[1:]):
        if b - a < min_pitch:
            raise ValueError(
                f"riser columns x={a} ({sorted(by_x[a])}) and x={b} ({sorted(by_x[b])}) "
                f"are {b - a:.3f} um apart; needs >= {min_pitch}"
            )
    if cp_array.declutter_riser_x(list(points), min_pitch) != list(points):
        raise ValueError("riser columns would be perturbed by declutter_riser_x() -- placement bug")


def link_columns(
    nets: Sequence[str], base_x: float, direction: int, pitch: float = CONN_COLUMN_PITCH_UM
) -> dict[str, float]:
    """One clear Metal3 column per net, marching away from the block
    (``direction`` is ``-1`` for the N side's own left-hand columns, ``+1``
    for the P side's right-hand ones). Deterministic in ``nets``' own order
    so a rebuild is byte-stable.
    """
    return {net: base_x + direction * i * pitch for i, net in enumerate(nets)}


# ---------------------------------------------------------------------------
# klayout-dependent geometry helpers.
# ---------------------------------------------------------------------------


def _escape(
    canvas: devgen.Canvas,
    pad: tuple[float, float, float, float],
    x_target: float,
    width: float = devgen.METAL1_WIRE_WIDTH_UM,
    landing_half: float = LANDING_HALF_UM,
) -> tuple[float, float, float, float]:
    """Run a short horizontal Metal1 wire from ``pad``'s own centre out to
    ``x_target``, ending in a via-sized landing pad, and return that landing
    pad's box (the box to hand the router in place of ``pad``).

    Same technique as ``cp_array._stub()`` -- a single horizontal segment at
    the pad's own Y, so it can never cross a shape that pad does not already
    abut -- but *deliberately placed* rather than a repair for a decluttering
    nudge: this is how a terminal whose natural riser X is already taken (a
    switch's bottom pad, which shares its top pad's X by construction) gets a
    column of its own. The landing pad is drawn explicitly, wide enough to
    enclose Via1 (``V1.3a``), because the wire itself is narrower than that
    enclosure requires -- the identical reason ``cp_array._riser()`` draws its
    own.
    """
    cx, cy = cp_array.pad_center(pad)
    half = width / 2.0
    x_lo, x_hi = sorted((cx, x_target))
    canvas.rect("metal1", x_lo, cy - half, x_hi, cy + half)
    box = (x_target - landing_half, cy - landing_half, x_target + landing_half, cy + landing_half)
    canvas.rect("metal1", *box)
    return box


def _riser_box(x: float, y: float, half: float = LANDING_HALF_UM) -> tuple[float, float, float, float]:
    """A synthetic 'pad' box centred on ``(x, y)`` -- what to hand the router
    when the real Metal1 shape underneath is a long strip (a substrate/n-well
    tap) and the riser should land at a chosen point on it rather than at its
    own midpoint."""
    return (x - half, y - half, x + half, y + half)


def _extend_bus(
    canvas: devgen.Canvas,
    track_y: float,
    x_a: float,
    x_b: float,
    width: float = cp_array.METAL2_WIRE_WIDTH_UM,
) -> None:
    """Extend a Metal2 track from ``x_a`` to ``x_b`` at ``track_y``.

    Overlaps (and therefore merges with) the existing bus/landing geometry at
    whichever end already carries it -- the reason this is drawn into the
    same flat cell the sub-block was flattened into, per ``_canvas.at()``'s
    own docstring ("two shapes that merge into one polygon for DRC must be in
    the same cell").
    """
    half = width / 2.0
    x_lo, x_hi = sorted((x_a, x_b))
    cp_array._rect_extra(canvas, "metal2", x_lo - half, track_y - half, x_hi + half, track_y + half)


def _link_tracks(canvas: devgen.Canvas, x: float, y_a: float, y_b: float) -> None:
    """A bare Metal3 vertical between two Metal2 tracks, with a Via2 landing
    at each end -- the array<->glue link (see module docstring). No Via1 and
    no Metal1 anywhere: both ends are already Metal2, and the column sits in
    empty space beside the block, so the run free-crosses every intervening
    track without a via."""
    half_v2 = cp_array.VIA2_SIZE_UM / 2.0
    half_pad = half_v2 + cp_array.VIA_ENCLOSURE_UM
    for y in (y_a, y_b):
        cp_array._rect_extra(canvas, "metal2", x - half_pad, y - half_pad, x + half_pad, y + half_pad)
        cp_array._rect_extra(canvas, "via2", x - half_v2, y - half_v2, x + half_v2, y + half_v2)
        cp_array._rect_extra(canvas, "metal3", x - half_pad, y - half_pad, x + half_pad, y + half_pad)
    half_w = cp_array.METAL3_WIRE_WIDTH_UM / 2.0
    cp_array._rect_extra(canvas, "metal3", x - half_w, min(y_a, y_b), x + half_w, max(y_a, y_b))


# ---------------------------------------------------------------------------
# build()
# ---------------------------------------------------------------------------


@dataclass
class CpOutputStageLayout:
    canvas: devgen.Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, list[tuple[float, float, float, float]]]
    array: cp_array.CpArrayLayout | None = None
    switch_ports: dict[str, devgen.MosfetPorts] = field(default_factory=dict)
    inverter_origins: dict[str, tuple[float, float]] = field(default_factory=dict)
    glue_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    glue_bus: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    riser_points: list[tuple[str, float, float]] = field(default_factory=list)
    link_columns: dict[str, float] = field(default_factory=dict)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)

    def probe_pads(self) -> dict[str, list[tuple[float, float, float, float]]]:
        """``net -> [Metal1 landing box, ...]`` for every point this block
        believes is on that net -- the array block's own promoted pin pads
        *plus* every riser landing of this block's own glue mesh.

        This is what :func:`netcheck.check_gds` is handed: probing **every**
        pad (not one representative per net) is what makes the check catch an
        *open* as well as a short, and including the array's own pins on both
        polarities is what proves the link columns actually tied the two
        sides' ``B0``/``B0B``/``B1``/``B1B``/``VDD``/``VSS`` together.
        """
        pads: dict[str, list[tuple[float, float, float, float]]] = {}
        assert self.array is not None
        for net, boxes in self.array.pins.items():
            pads.setdefault(net, []).extend(boxes)
        half = LANDING_HALF_UM
        for net, x, y in self.riser_points:
            pads.setdefault(net, []).append((x - half, y - half, x + half, y + half))
        return pads


def build(outdir: Path | None = None) -> CpOutputStageLayout:  # noqa: PLR0915 -- one linear assembly
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package

    arr = cp_array.build()
    inv = pfdcp_inv.build()

    canvas = devgen.Canvas(TOP_CELL)

    # --- place cp_array (unmodified, at this block's own origin) and the
    # four pfdcp_inv_3v3 glue instances, then flatten -- the same GDS-level
    # placement cp_array itself uses for its own 8 leg instances (see its
    # docstring, "GDS-LEVEL PLACEMENT"). ---
    with tempfile.TemporaryDirectory() as tmp:
        arr_gds = Path(tmp) / f"{cp_array.TOP_CELL}.gds"
        inv_gds = Path(tmp) / f"{pfdcp_inv.TOP_CELL}.gds"
        arr.write_gds(arr_gds)
        inv.write_gds(inv_gds)
        canvas.layout.read(str(arr_gds))
        canvas.layout.read(str(inv_gds))
    arr_index = canvas.layout.cell_by_name(cp_array.TOP_CELL)
    inv_index = canvas.layout.cell_by_name(pfdcp_inv.TOP_CELL)

    dbu_per_um = int(round(1.0 / canvas.dbu))

    def _place(index, dx: float, dy: float) -> None:
        trans = db.Trans(db.Vector(int(round(dx * dbu_per_um)), int(round(dy * dbu_per_um))))
        canvas.top.insert(db.CellInstArray(index, trans))

    # --- the glue row's own coordinate frame ---
    row_x0 = arr.footprint[0] + 2.0
    # GLUE_GAP_UM is measured to whichever of this block's own shapes hangs
    # lowest below the switch row's baseline -- the row's substrate tap strip,
    # or (as it happens) a glue inverter's own substrate tap, which sits a
    # little lower still. Derived from the leaf's own footprint rather than
    # assumed, so the clearance stays exact if that leaf ever changes.
    glue_drop = min(-(devgen.TAP_GAP_UM + devgen.TAP_SIZE_UM), inv.footprint[1])
    row_y0 = arr.footprint[3] + GLUE_GAP_UM - glue_drop
    sub_tap_y = row_y0 - devgen.TAP_GAP_UM - devgen.TAP_SIZE_UM / 2.0

    row = switch_row_x(x0=row_x0)
    switch_order = [d.name for d in (*SWITCH_DEVICES_N, *SWITCH_DEVICES_P)]
    check_escape_clearance(row, [d.name for d in SWITCH_DEVICES_N])
    check_escape_clearance(row, [d.name for d in SWITCH_DEVICES_P])

    inv_x0 = row[switch_order[-1]][1] + INV_GROUP_GAP_UM
    inv_origins = {spec.name: (inv_x0 + i * INV_PITCH_UM, row_y0) for i, spec in enumerate(GLUE_INVERTERS)}

    _place(arr_index, 0.0, 0.0)
    for dx, dy in inv_origins.values():
        _place(inv_index, dx, dy)
    canvas.top.flatten(-1, True)

    # --- draw the six switches into the same flat cell ---
    nets: dict[str, list[tuple[float, float, float, float]]] = {}

    def add(net: str, pad: tuple[float, float, float, float]) -> None:
        nets.setdefault(net, []).append(pad)

    ports: dict[str, devgen.MosfetPorts] = {}
    named_pad: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    for dev in (*SWITCH_DEVICES_N, *SWITCH_DEVICES_P):
        x0, _x1 = row[dev.name]
        p = devgen.mosfet(canvas, dev, x0, row_y0)
        ports[dev.name] = p
        add(dev.gate_net, p.gate_pad)
        add(dev.top_net, p.top_pad)
        named_pad[(dev.name, "G")] = p.gate_pad
        named_pad[(dev.name, "top")] = p.top_pad
        if dev.bottom_net == dev.top_net:
            # MDUMN/MDUMP: both diffusions on one net -- two risers at one X
            # on one net, exactly the case cp_array already proves safe.
            bottom = p.bottom_pad
        else:
            bottom = _escape(canvas, p.bottom_pad, p.x1 + SWITCH_ESCAPE_UM)
        add(dev.bottom_net, bottom)
        named_pad[(dev.name, "bottom")] = bottom

    n_group = [ports[d.name] for d in SWITCH_DEVICES_N]
    p_group = [ports[d.name] for d in SWITCH_DEVICES_P]

    # --- switch-row substrate tap strip (NMOS bodies -> VSS) and n-well tap
    # strip (PMOS bodies -> VDD), each spanning its own group's full X range
    # -- the DF.13_LV/DF.14_LV 20 um tap-distance argument cp_array's own
    # _tap_strip() docstring states. ---
    n_sub_box, n_sub_pad = cp_array._tap_strip(
        canvas, "p", n_group[0].x0, n_group[-1].x1, sub_tap_y, "VSS"
    )
    p_tap_y = row_y0 + SWITCH_ROW_H_UM + devgen.TAP_GAP_UM + devgen.TAP_SIZE_UM / 2.0
    p_tap_box, _p_tap_pad = cp_array._tap_strip(
        canvas, "n", p_group[0].x0, p_group[-1].x1, p_tap_y, "VDD"
    )
    p_nwell_box = (
        min(p_group[0].x0, p_tap_box[0]) - devgen.NWELL_MARGIN_UM,
        min(p_group[0].y0, p_tap_box[1]) - devgen.NWELL_MARGIN_UM,
        max(p_group[-1].x1, p_tap_box[2]) + devgen.NWELL_MARGIN_UM,
        max(max(p.y3 for p in p_group), p_tap_box[3]) + devgen.NWELL_MARGIN_UM,
    )
    canvas.rect("nwell", *p_nwell_box)

    # Rise from a chosen point on each strip (its own midpoint would collide
    # in X with a device pad), not from the strip pad's own centre -- the
    # strip's Metal1 is continuous, so any point on it is equivalent.
    n_sub_riser_x = (n_group[0].x1 + n_group[1].x0) / 2.0
    p_tap_riser_x = (p_group[0].x1 + p_group[1].x0) / 2.0
    add("VSS", _riser_box(n_sub_riser_x, sub_tap_y))
    add("VDD", _riser_box(p_tap_riser_x, p_tap_y))

    # --- glue inverters: their A/Y/VDD/VSS landing pads, escaped right onto
    # their own columns (see module docstring). pfdcp_inv_3v3's own build
    # only records 1-terminal nets in LeafCell.pins (VDD/VSS), so A and Y are
    # read off its ports -- MN's gate pad is A (shared with MP's, wired
    # inside the leaf) and MN's top pad is Y (shared with MP's bottom). ---
    mn, mp = inv.ports  # build_stack_cell places INV_DEVICES bottom-to-top: MN, MP
    for spec in GLUE_INVERTERS:
        dx, dy = inv_origins[spec.name]
        y_esc, vss_esc, vdd_esc = (dx + o for o in INV_ESCAPE_UM)
        a_pad = cp_array._translate_box(mn.gate_pad, dx, dy)
        add(spec.a_net, a_pad)
        named_pad[(spec.name, "A")] = a_pad
        named_pad[(spec.name, "Y")] = _escape(
            canvas, cp_array._translate_box(mn.top_pad, dx, dy), y_esc
        )
        add(spec.y_net, named_pad[(spec.name, "Y")])
        add("VSS", _escape(canvas, cp_array._translate_box(mn.bottom_pad, dx, dy), vss_esc))
        add("VDD", _escape(canvas, cp_array._translate_box(mp.top_pad, dx, dy), vdd_esc))

    # --- the glue block's own bounding box (everything drawn above) ---
    glue_boxes: list[tuple[float, float, float, float]] = [
        (p.x0, p.y0, p.x1, p.y3) for p in ports.values()
    ]
    glue_boxes.append(n_sub_box)
    glue_boxes.append(p_nwell_box)
    glue_boxes.extend(cp_array._translate_box(inv.footprint, dx, dy) for dx, dy in inv_origins.values())
    for pads in nets.values():
        glue_boxes.extend(pads)
    glue_bbox = _canvas.bbox_union(glue_boxes)

    # --- prove the hand-placed riser columns need no decluttering (see
    # check_riser_columns()'s own docstring) BEFORE routing with them. ---
    riser_points = [
        (net, *cp_array.pad_center(pad)) for net, pads in nets.items() for pad in pads
    ]
    check_riser_columns(riser_points)

    glue_tracks, glue_bus = cp_array._route_side(canvas, nets, glue_bbox, promote_pins=False)

    # --- link every net this block shares with the array block: extend that
    # side's Metal2 bus into a clear column, extend this block's own track to
    # the same column, join with a Metal3 vertical. N side goes left, P side
    # right -- never across each other (see module docstring). ---
    n_shared = [net for net in arr.n_bus if net in glue_bus]
    p_shared = [net for net in arr.p_bus if net in glue_bus]
    left_base = min(arr.footprint[0], glue_bbox[0]) - CONN_COLUMN_MARGIN_UM
    right_base = max(arr.footprint[2], glue_bbox[2]) + CONN_COLUMN_MARGIN_UM
    columns: dict[str, float] = {}
    for side, shared, bus, base, direction in (
        ("N", n_shared, arr.n_bus, left_base, -1),
        ("P", p_shared, arr.p_bus, right_base, +1),
    ):
        cols = link_columns(shared, base, direction)
        for net, x in cols.items():
            columns[f"{side}:{net}"] = x
            track_y, x_lo, x_hi = bus[net]
            glue_y, glue_lo, glue_hi = glue_bus[net]
            _extend_bus(canvas, track_y, x, x_lo if direction < 0 else x_hi)
            _extend_bus(canvas, glue_y, x, glue_lo if direction < 0 else glue_hi)
            _link_tracks(canvas, x, track_y, glue_y)

    # --- boundary pins. IBN/ICN/IBP/ICP are pure array nets (no glue
    # terminal), so their pin is the array's own already-routed landing pad;
    # everything else is promoted on a glue pad of this block's own. ---
    pin_pads: dict[str, tuple[float, float, float, float]] = {
        "UP": named_pad[("xi_up", "A")],
        "DN": named_pad[("xi_dn", "A")],
        "B0": named_pad[("xi_b0", "A")],
        "B1": named_pad[("xi_b1", "A")],
        "IBN": arr.pins["IBN"][0],
        "ICN": arr.pins["ICN"][0],
        "IBP": arr.pins["IBP"][0],
        "ICP": arr.pins["ICP"][0],
        "VOUT": named_pad[("MSWDN", "top")],
        "VDUMP": named_pad[("MDMPDN", "top")],
        # The two rails' pins are their own switch-row tap strips -- the one
        # place in this block where each rail is unambiguously the body
        # connection as well as the supply.
        "VDD": _riser_box(p_tap_riser_x, p_tap_y),
        "VSS": _riser_box(n_sub_riser_x, sub_tap_y),
    }
    for net in BOUNDARY_PINS:
        canvas.pin(net, *pin_pads[net])

    col_xs = list(columns.values())
    footprint = (
        min(arr.footprint[0], glue_bbox[0], min(col_xs) - CONN_COLUMN_PITCH_UM),
        min(arr.footprint[1], glue_bbox[1]),
        max(arr.footprint[2], glue_bbox[2], max(col_xs) + CONN_COLUMN_PITCH_UM),
        max(glue_tracks._next_y, glue_bbox[3]),  # noqa: SLF001 -- top of the last routed track
    )

    layout = CpOutputStageLayout(
        canvas=canvas,
        footprint=footprint,
        pins=canvas.pins,
        array=arr,
        switch_ports=ports,
        inverter_origins=inv_origins,
        glue_bbox=glue_bbox,
        glue_bus=glue_bus,
        riser_points=riser_points,
        link_columns=columns,
    )
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "cp-layout" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    parser.add_argument(
        "--no-netcheck",
        action="store_true",
        help="skip the Metal1-3 connectivity check (see netcheck.py)",
    )
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"glue bbox: {layout.glue_bbox}")
    print(f"switch row: { {n: (p.x0, p.x1) for n, p in layout.switch_ports.items()} }")
    print(f"inverter origins: {layout.inverter_origins}")
    print(f"link columns: {layout.link_columns}")
    print(f"boundary pins: {sorted(layout.pins)}")
    if args.no_netcheck:
        return 0
    report = netcheck.check_gds(
        outdir / f"{TOP_CELL}.gds", TOP_CELL, netcheck.pad_probe_points(layout.probe_pads())
    )
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
