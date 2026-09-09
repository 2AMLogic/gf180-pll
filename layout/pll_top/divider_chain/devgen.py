"""Reusable full-custom ``nfet_03v3``/``pfet_03v3`` leaf-cell generator for
the ``divider_chain`` block family (issue #306, Part 1 of #295's
device-layout methodology proof).

This module is a **reuse of** ``layout/pll_top/pfd_cp/devgen.py`` (issue
#299, PR #312, landed on ``main``), not an independent re-derivation: the
``Canvas``/``Device``/``build_stack_cell()`` API and every drawing margin
below are byte-for-byte the values that module already proved DRC/LVS-clean
against gf180mcu's real signoff deck. Per that module's own docstring
("each full-custom leaf-cell family owns its own generator"), this is a
second, sibling copy for the ``divider_chain`` package rather than a shared
import across block families -- see that module's docstring for the
per-shape DRC-rule derivation this one repeats.

CONTRACT
--------
:func:`build_stack_cell` takes an ordered list of :class:`Device` records
(flavor, ``w_um``/``l_um``, and three terminal net names -- gate/top/bottom)
and returns a :class:`LeafCell`: a ready-to-write ``klayout.db`` canvas, laid
out as a single vertical column, standalone DRC-clean (its own n-well tie
and p-substrate tie are drawn and wired in), with every net that appears on
exactly one device terminal promoted to a labelled top-level Metal1 pin and
every net that appears on exactly two wired together with a Metal1 run.

This is deliberately narrower than a general place-and-route engine: it only
knows how to stack devices in one column, all left-aligned at the same
``x0``, and it only resolves 1- and 2-terminal nets automatically.

TRANSMISSION-GATE TOPOLOGY -- TWO REAL STRUCTURAL ADDITIONS THE CURATOR'S READ-ONLY PREDICTION MISSED
------------------------------------------------------------------------------------------------------------------------
Issue #299's own docstring named "a transmission-gate switch pair" as an
example topology this API should already cover, and issue #306's own
Curator update predicted why, reading the dataclass shape directly (not
running it): ``Device.gate_net`` is independent per device while
``top_net``/``bottom_net`` are matched purely by string equality across the
whole device list, so a transmission gate "should" need no change. That
prediction was **incomplete on two separate points**. Both are now fixed and
the fixed result is the LVS-clean GDS this module ships; this section
documents what needed to change and the concrete failure each fix resolves
-- and, honestly, how each one was actually found, since the two differ:

**1. The PMOS/NMOS body tie** was caught by design review while re-deriving
the tap-wiring code path for this cell -- *before* ever building/running it
-- not by an observed failing DRC/LVS run in isolation (this repo's own
proof cell never shipped the unfixed version). ``build_stack_cell()``'s inherited
well/substrate-tap wiring (see "WELL/SUBSTRATE TIES" below) assumed the
n-well tap always shares a net with the topmost pfet's own ``top_net`` (true
for ``inv_3v3``, where the PMOS source *is* ``VDD``) and wired the two pads
together with Metal1. For ``tgate_3v3`` the PMOS pass device's ``top_net``/
``bottom_net`` are the signal nets ``Y``/``A`` -- neither is ``VDD`` -- so
reusing that same fallback would have drawn a Metal1 wire physically
shorting the n-well tap (and therefore the PMOS body) onto a diffusion
signal net: DRC-legal, but a genuine LVS-incorrect short, not merely a
missing label. Fixed with a single new optional field,
:attr:`Device.body_net` (default ``None``): when set, it names the net the
device's *body* ties to, independent of its ``top_net``/``bottom_net``
diffusion terminals; when ``None`` (every existing call site, e.g.
``inv_3v3.py``), the tap-wiring fallback is exactly the old behaviour, so
the inverter's generated GDS is byte-for-byte unchanged.

**2. The two diffusion nets' own wiring.** This is the one the Curator
update's read-the-dataclass prediction missed entirely: a static inverter's
two devices only ever need *one* 2-terminal net resolved between them (``Y``
-- the two devices' facing pads), with the other two terminals (``A``, tied
to a shared *gate* net, and each supply rail) each 1-terminal. A
transmission gate's two devices instead have *two* signal nets (``A`` and
``Y``) that are each 2-terminal across the same two devices -- and only one
of the two possible net-to-terminal assignments lets both be wired with
:func:`_connect_pads`'s existing straight-line connector: the one where the
*facing* pads (the topmost nfet's top pad and the bottommost pfet's bottom
pad, i.e. the two pads actually adjacent across the inter-device well gap)
share a net. The *other* net necessarily ends up on the stack's two
*outermost*, non-facing pads (the bottommost device's bottom pad and the
topmost device's top pad) -- and a naive straight-line connect between those
two runs directly through the facing net's own connector and the
intervening gates, physically merging both nets into one. This is not a
theoretical concern: an earlier attempt at this cell's own device table
assigned the nets the wrong way round, drew DRC-clean, and then failed real
LVS with a visibly merged node (``A``/``Y`` both extracted onto one net) --
exactly the failure mode this note warns about. The fix is
:func:`build_stack_cell`'s new ``bypass_nets`` argument (see its own
docstring, and :func:`_bypass_wire`) -- a dedicated Metal1 lane routed
around every device's own footprint (to the right of the widest device's
own drawn edge, clear of every gate pad, which are exclusively on the left)
connecting a net's two outer pads without crossing the facing net's
connector or any gate. ``tgate_3v3.py`` selects it for its own ``"A"`` net
only, and states, in its own device-table comment, *why* ``"A"`` (not
``"Y"``) is the one that needs it: because of which pads physically face
each other in this cell's chosen stack order.

Net effect: ``build_stack_cell()``'s core net-*counting* logic (1-terminal
promotes, 2-terminal wires, anything else raises) needed no change --
that part of the Curator's prediction held. What needed adding was *how* a
2-terminal net gets wired when its two pads are not the facing pair, and a
way to keep the body tie separate from the diffusion terminals. Both are
opt-in (``body_net``, ``bypass_nets``) with the pre-existing default
behaviour preserved exactly for every caller that does not need them.

WHY THIS IS DIRECT ``klayout.db`` GEOMETRY, NOT ``klt gen``/``klt gen-compose``
--------------------------------------------------------------------------
Issue #299 already reproduced and filed this gap generically:
2AMLogic/klayout-tools#1575 -- ``klt gen mos_array`` -> ``klt gen-compose``
composes and routes cleanly and passes ``klt``'s own curated ~10-rule DRC
subset, but fails six real rule families on gf180mcu's actual signoff deck
(``DF.6_LV``, ``PL.4_LV``, ``PL.5a_LV``/``PL.5b_LV``, ``CO.7``, ``DF.12``),
scaling with device count, regardless of which leaf cell or block family is
drawn through it. Per issue #306's own acceptance criteria, that gap is not
re-filed here -- see ``layout/pll_top/pfd_cp/devgen.py``'s module docstring
for the full worked reproduction (device sizes, exact rule minimums, the
``voltage_flavor``/``Dualgate`` non-fix) this module's own choice inherits
without needing to re-run.

So this module draws geometry the same way ``layout/pll_top/pfd_cp/devgen.py``
and ``layout/pll_top/vco/primitives.py`` already do: directly against
``klayout.db``, with margins read from, and exceeding, the PDK's own DRC deck
minimums (cited rule-by-rule in ``pfd_cp/devgen.py``'s docstring; identical
values, not re-derived here), generalized into a device-list-driven API.

MOSFET GEOMETRY CONVENTION
---------------------------
Identical to ``pfd_cp/devgen.py``/``vco/primitives.py`` (deliberately --
this is a third, independent leaf-cell family, not a fork of either): current
flows vertically. A device's ``w_um`` is its horizontal extent; ``l_um`` is
its vertical extent (the gate length). Every device is its own self-contained
comp/poly/implant island, wired to its neighbours only through Metal1 +
contacts -- no shared diffusion, even between two adjacent devices in the
same stack (including the two pass-devices of a transmission gate: ``MN``
and ``MP`` in ``tgate_3v3`` each get their own comp island, wired together
on ``A``/``Y`` through Metal1, not a shared diffusion strap).

WELL/SUBSTRATE TIES (why only the n-well gets one drawn here)
----------------------------------------------------------
Identical rationale/citation to ``pfd_cp/devgen.py``'s docstring: gf180mcu's
own official LVS deck globally ties every NMOS body to the synthesized
substrate net (``general_connections.lvs``: ``connect_global(sub,
substrate_name)``) regardless of a local p-type tap, but draws **no**
equivalent global tie for a PMOS body's n-well -- so this module always
draws one small n-well tap (wired to the top-of-stack PMOS device's own
source/top net) when the device list contains a ``"pfet"``, and one small
p-substrate tap (wired to the bottom-of-stack NMOS device's own source/
bottom net) when it contains an ``"nfet"``, for the same DRC-hygiene/
LVS-correctness split that module's docstring documents. "Wired to ... own
source/bottom net" is the :attr:`Device.body_net` *fallback*, used when a
device does not set that field explicitly; see the "TRANSMISSION-GATE
TOPOLOGY" section above for the case (a pass-device whose diffusion
terminals are not supply nets) where a device must set ``body_net``
explicitly instead, and why the tap is then left electrically joined to
that net only through the well/substrate region itself, not a Metal1 wire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import ClassVar, Sequence

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention (see
    # floorplan/skeleton.py and every layout/tests/test_*.py's own
    # sys.path.insert(..., ".../pll_top") -- "vco"/"lock_detector"/"pfd_cp"
    # are then each their own top-level package, one level short of "..").
    import _canvas

# --- GDS layers, gf180mcuD (identical citation/values to
# pfd_cp/devgen.py's own LAYER table -- confirmed against
# libs.tech/klayout/drc/rule_decks/layers_def.drc's get_polygons() calls). ---
LAYER = {
    "comp": (22, 0),
    "poly2": (30, 0),
    "contact": (33, 0),
    "nplus": (32, 0),
    "pplus": (31, 0),
    "nwell": (21, 0),
    "metal1": (34, 0),
    # The *pin/label* purpose of Metal1 -- NOT the drawing datatype above.
    # gf180mcu's own official LVS deck reads top-level net names from here
    # (``libs.tech/klayout/lvs/rule_decks/layers_definitions.lvs``:
    # ``metal1_label = labels(34, 10)``, then
    # ``general_connections.lvs``: ``connect(metal1_con, metal1_label)``) --
    # a text dropped on (34, 0) instead (the mistake this module avoids) is
    # invisible to that connectivity step, so a net "labelled" there is
    # still extracted as an anonymous node under LVS.
    "metal1_label": (34, 10),
    # Metal2/Via1/Via2/Metal3. Via1/Metal2 are used by
    # :func:`build_row_cell`'s own strap/track routing (issue #307) and by
    # the composite-macro routing fabric (:func:`route_net`/
    # :class:`NetTracks`, issue #308's ``dff_tg_3v3``); Via2/Metal3 only by
    # the latter. No single-column ``build_stack_cell()`` leaf cell (issue
    # #306) draws on any of them, so those cells' generated GDS is unchanged
    # by either addition. Same (layer, datatype) values as
    # ``pfd_cp/rowgen.py``/``lock_detector/primitives.py``, both already
    # DRC-clean on this deck.
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

# --- Derived generator margins (deck minimum + explicit headroom) -- values
# identical to pfd_cp/devgen.py's/vco/primitives.py's own proven-DRC-clean
# constants; see those modules' docstrings for the full per-rule derivation.
# Repeated (not imported) so this package does not depend on either sibling
# block family's own module -- each full-custom leaf-cell family owns its
# own generator. ---
SD_OVERHANG_UM = 0.5  # DF.6_LV=0.24 min
COMP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, between two same-flavor devices' comp islands
NWELL_TO_NMOS_GAP_UM = 4.0  # DF.16_LV=0.43 min, PMOS-to-NMOS clearance across a well edge
POLY_ENDCAP_UM = 0.65  # PL.4_LV=0.22 min, sized so the gate contact tab's own Metal1
# pad also stays M1.2a-legal (>=0.23 um) from the S/D pads' Metal1
GATE_TAB_W_UM = 0.4
GATE_TAB_H_UM = 0.4
GATE_TAB_OVERLAP_UM = 0.05
CONTACT_SIZE_UM = 0.22  # CO.1
CONTACT_PITCH_UM = 0.5  # 0.22 contact + 0.28 pitch gap > CO.2a's 0.25 min
CONTACT_ROW_MARGIN_UM = 0.1
IMPLANT_MARGIN_UM = 0.3  # NP.5a/PP.5a=0.23, NP.5b/PP.5b=0.16 min
NWELL_MARGIN_UM = 0.5  # DF.4c_LV=0.43 min (PMOS comp -> nwell edge)
METAL1_PAD_MARGIN_UM = 0.12
METAL1_WIRE_WIDTH_UM = 0.28  # > M1.1's 0.23 min

# --- Metal2/Via1/Via2/Metal3 composite-routing margins (issue #308's
# ``dff_tg_3v3`` -- multiple leaf-cell instances placed side by side in one
# shared ``Canvas``, wired by :func:`route_net`, not by any single leaf
# cell's own Metal1-only ``build_stack_cell()`` wiring). Values/derivation
# identical to ``lock_detector/primitives.py``'s own proven-DRC-clean
# routing fabric (see that module's docstring for the full per-rule
# citation); repeated, not imported, per this package's "each full-custom
# leaf-cell family owns its own generator" convention. ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b min is ~0 um; headroom for the enclosing metal pad
METAL2_WIRE_WIDTH_UM = 0.34  # > M2.1's 0.28 min
METAL3_WIRE_WIDTH_UM = 0.34  # > M3.1's 0.28 min
METAL2_TRACK_PITCH_UM = 0.75  # (pitch - width) = 0.41 > M2.2a's 0.28 min, between two tracks

# --- Bypass-lane wiring (see module docstring's "TRANSMISSION-GATE
# TOPOLOGY" section, and build_stack_cell()'s own docstring, for why this
# exists): a dedicated vertical Metal1 lane for a 2-terminal net whose two
# pads are *not* the adjacent (facing) pair -- e.g. tgate_3v3's "A" net,
# whose two pads are the stack's outermost (non-facing) terminals.
#
# The lane sits to the *right* of every device's own widest drawn edge
# (comp/poly/pad), not to the left of the gate pads: an earlier version of
# this routed a left-side lane (clear of every gate *poly* tab, which is
# anchored at a fixed x regardless of device width) and hit two real,
# concretely-reproduced problems reaching pads on the *comp* side from
# there -- (1) a device's own S/D pad can vertically overlap that same
# device's own gate pad (they only avoid touching because they sit at
# different x, not different y -- see :func:`mosfet`), so a jog reaching
# in from the far left, at any y within that overlap, clips the gate pad;
# (2) gf180mcu's own two-device set here has genuinely different device
# widths (``tgate_3v3``'s nfet is 1 um, its pfet 2.5 um), so a single fixed
# left-side x offset anchored to the *narrower* device's own gate tab does
# not generalize to clearing the *wider* device's own comp/pad footprint at
# its own y-level. The right side has neither problem: nothing this module
# draws for any device extends past that device's own comp/pad right edge,
# so a lane clear of the single widest device's own right edge is clear of
# every device's own footprint at every y, and gate pads are exclusively on
# the *left*, so this side never risks the gate-pad-overlap issue at all. ---
BYPASS_LANE_CLEARANCE_UM = 0.3  # > M1.2a's 0.23 min metal-to-metal spacing

# --- Well/substrate tap geometry (see module docstring's "WELL/SUBSTRATE
# TIES" section). A tiny square tap: big enough for one contact plus
# CONTACT_ROW_MARGIN_UM on every side (>= NP.1/PP.1's 0.4 um min width). ---
TAP_SIZE_UM = 0.6
TAP_GAP_UM = 1.0  # clearance from the tap's own comp to the nearest device comp/poly;
# > 2*IMPLANT_MARGIN_UM so the tap's own (opposite-type) implant never touches
# the adjacent device's implant (NP.3/PP.3-class spacing, 0.16-0.43 um min)


_r = _canvas._r


@dataclass
class Canvas(_canvas.Canvas):
    """A thin ``klayout.db`` layout/cell wrapper, float-micron coordinates in.

    ``klayout.db`` is imported lazily (inside ``__post_init__``), so any
    caller that only touches this module's pure-Python dataclasses
    (:class:`Device`) stays importable with no PV environment -- same
    convention as ``pfd_cp/devgen.py``/``vco/primitives.py``/
    ``layout/harness/cell.py``. This is the shared
    ``layout/pll_top/_canvas.Canvas`` (see issue #317, applied to this module
    by issue #327) with this module's own ``LAYER`` table and ``pin()``
    labelling on ``"metal1_label"`` (34/10) -- the *purpose* layer gf180mcu's
    own official LVS deck actually reads net names from (see module
    docstring), *not* the drawing layer a purely-visual label would use.
    """

    LAYER: ClassVar[dict[str, tuple[int, int]]] = LAYER
    PIN_LAYER: ClassVar[str] = "metal1_label"


@dataclass(frozen=True)
class Device:
    """One ``nfet_03v3``/``pfet_03v3`` instance in a :func:`build_stack_cell` column.

    ``top_net``/``bottom_net`` are this device's two source/drain terminals,
    named for their position in the vertical stack (``top_net`` nearer the
    top of the column). ``gate_net``/``top_net``/``bottom_net`` are plain
    net names -- :func:`build_stack_cell` wires or promotes them purely by
    string equality across the whole device list, so a typo silently creates
    a spurious extra net rather than raising; callers are expected to keep
    ``layout/tests/``-level coverage on their own device tables the way
    ``vco/devices.py``'s own tests do.

    A static CMOS inverter (``inv_3v3``) ties both devices' ``gate_net`` to
    the same string (``"A"``). A transmission gate (``tgate_3v3``) instead
    gives each device its *own* ``gate_net`` (``"GN"``/``"GP"``) while both
    devices share ``top_net``/``bottom_net`` (``"Y"``/``"A"``) -- both are
    representable with these three fields exactly as-is; see the module
    docstring's "TRANSMISSION-GATE TOPOLOGY" section.

    ``body_net``, when set, names the net this device's body/bulk ties to,
    independent of ``top_net``/``bottom_net``. Leave it ``None`` (the
    default) when the body legitimately *is* the same net as the device's
    own supply-facing diffusion terminal (the common case: an inverter's
    PMOS source is ``VDD``) -- :func:`build_stack_cell` then falls back to
    the original convention (topmost pfet's ``top_net`` / bottommost nfet's
    ``bottom_net``). Set it explicitly when the device's diffusion terminals
    are *not* supply nets (a transmission gate's pass devices: body ties to
    ``VDD``/``VSS`` while ``top_net``/``bottom_net`` are signal nets) -- see
    the module docstring's "TRANSMISSION-GATE TOPOLOGY" section for why
    reusing the fallback there would be an LVS-incorrect short, not just a
    missing label.
    """

    name: str
    kind: str  # "nfet" or "pfet"
    w_um: float
    l_um: float
    gate_net: str
    top_net: str
    bottom_net: str
    body_net: str | None = None


@dataclass
class MosfetPorts:
    name: str
    kind: str
    x0: float
    x1: float
    y0: float
    y3: float
    bottom_pad: tuple[float, float, float, float]
    top_pad: tuple[float, float, float, float]
    gate_pad: tuple[float, float, float, float]
    gate_y_center: float


# Left-edge x (or y) positions for a row of contacts spanning [lo, hi] --
# shared with every other ``layout/pll_top/*`` submodule (issue #332,
# ``_canvas._contact_positions()``).
_contact_positions = partial(
    _canvas._contact_positions,
    size_um=CONTACT_SIZE_UM,
    pitch_um=CONTACT_PITCH_UM,
    margin_um=CONTACT_ROW_MARGIN_UM,
)


def mosfet(canvas: Canvas, device: Device, x0: float, y_bottom: float) -> MosfetPorts:
    """Draw one vertical-current-flow ``nfet_03v3``/``pfet_03v3`` instance.

    Identical geometry/margins to ``pfd_cp/devgen.py``'s/``vco/primitives.py``'s
    ``mosfet()`` -- see those modules' docstrings for the full per-shape DRC
    citation. ``x0`` is the device's comp left edge; ``y_bottom`` is the
    bottom terminal comp's bottom edge.
    """
    w, l = device.w_um, device.l_um
    implant_layer = "pplus" if device.kind == "pfet" else "nplus"

    x1 = x0 + w
    y1 = y_bottom + SD_OVERHANG_UM
    y2 = y1 + l
    y3 = y2 + SD_OVERHANG_UM

    canvas.rect("comp", x0, y_bottom, x1, y3)

    gate_x0 = x0 - POLY_ENDCAP_UM
    gate_x1 = x1 + POLY_ENDCAP_UM
    canvas.rect("poly2", gate_x0, y1, gate_x1, y2)

    gate_y_center = (y1 + y2) / 2.0
    tab_x1 = gate_x0 + GATE_TAB_OVERLAP_UM
    tab_x0 = tab_x1 - GATE_TAB_W_UM
    tab_y0 = gate_y_center - GATE_TAB_H_UM / 2.0
    tab_y1 = gate_y_center + GATE_TAB_H_UM / 2.0
    canvas.rect("poly2", tab_x0, tab_y0, tab_x1, tab_y1)

    gate_contact_x0 = tab_x0 + (GATE_TAB_W_UM - CONTACT_SIZE_UM) / 2.0
    gate_contact_y0 = tab_y0 + (GATE_TAB_H_UM - CONTACT_SIZE_UM) / 2.0
    canvas.rect(
        "contact",
        gate_contact_x0,
        gate_contact_y0,
        gate_contact_x0 + CONTACT_SIZE_UM,
        gate_contact_y0 + CONTACT_SIZE_UM,
    )
    gate_pad = (
        tab_x0 - METAL1_PAD_MARGIN_UM,
        tab_y0 - METAL1_PAD_MARGIN_UM,
        tab_x1 + METAL1_PAD_MARGIN_UM,
        tab_y1 + METAL1_PAD_MARGIN_UM,
    )
    canvas.rect("metal1", *gate_pad)

    def _terminal_pad(y_outer_edge: float, *, outer_is_max: bool) -> tuple[float, float, float, float]:
        xs = _contact_positions(x0, x1)
        if outer_is_max:
            cy1 = y_outer_edge - CONTACT_ROW_MARGIN_UM
            cy0 = cy1 - CONTACT_SIZE_UM
        else:
            cy0 = y_outer_edge + CONTACT_ROW_MARGIN_UM
            cy1 = cy0 + CONTACT_SIZE_UM
        for cx in xs:
            canvas.rect("contact", cx, cy0, cx + CONTACT_SIZE_UM, cy1)
        pad_x0 = min(xs) - METAL1_PAD_MARGIN_UM
        pad_x1 = max(xs) + CONTACT_SIZE_UM + METAL1_PAD_MARGIN_UM
        pad_y0 = cy0 - METAL1_PAD_MARGIN_UM
        pad_y1 = cy1 + METAL1_PAD_MARGIN_UM
        canvas.rect("metal1", pad_x0, pad_y0, pad_x1, pad_y1)
        return (pad_x0, pad_y0, pad_x1, pad_y1)

    bottom_pad = _terminal_pad(y_bottom, outer_is_max=False)
    top_pad = _terminal_pad(y3, outer_is_max=True)

    canvas.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y_bottom - IMPLANT_MARGIN_UM,
        x1 + IMPLANT_MARGIN_UM,
        y3 + IMPLANT_MARGIN_UM,
    )

    return MosfetPorts(
        name=device.name,
        kind=device.kind,
        x0=x0,
        x1=x1,
        y0=y_bottom,
        y3=y3,
        bottom_pad=bottom_pad,
        top_pad=top_pad,
        gate_pad=gate_pad,
        gate_y_center=gate_y_center,
    )


# Vertical Metal1 wire segment -- shared with every other
# ``layout/pll_top/*`` submodule (issue #353, ``_canvas.v_wire()``).
v_wire = partial(_canvas.v_wire, width=METAL1_WIRE_WIDTH_UM)


def _pad_overlap_x(pad_a: tuple, pad_b: tuple) -> float | None:
    lo = max(pad_a[0], pad_b[0])
    hi = min(pad_a[2], pad_b[2])
    return (lo + hi) / 2.0 if hi > lo else None


def _connect_pads(canvas: Canvas, pad_a: tuple, pad_b: tuple) -> None:
    """Wire two Metal1 pads that share an x-overlap with a straight vertical run.

    Every pad this module ever wires (gate tabs, or S/D pads of devices
    sharing the same left-aligned ``x0``) shares a real x-overlap by
    construction -- see the module docstring's "left-aligned at x0" note --
    so a single vertical run is always sufficient; no dogleg router is
    needed for the one-column topology this module supports.
    """
    x = _pad_overlap_x(pad_a, pad_b)
    if x is None:
        raise ValueError(
            f"pads {pad_a} and {pad_b} share no x-overlap -- build_stack_cell() "
            "only wires devices left-aligned at a common x0"
        )
    y0 = pad_a[3] if pad_a[3] <= pad_b[1] else pad_b[3]
    y1 = pad_b[1] if pad_a[3] <= pad_b[1] else pad_a[1]
    if y0 > y1:
        y0, y1 = y1, y0
    v_wire(canvas, x, y0, y1)


def _bypass_wire(
    canvas: Canvas, pad_a: tuple, pad_b: tuple, lane_x: float, width: float = METAL1_WIRE_WIDTH_UM
) -> None:
    """Wire two pads that do *not* share a safe direct x-overlap path (their
    straight-line run would cross unrelated interior geometry) via a
    dedicated vertical lane at ``lane_x`` (to the right of every device's
    own drawn extent -- see :data:`BYPASS_LANE_CLEARANCE_UM`'s derivation)
    plus two short horizontal jogs, one per pad, each drawn at that pad's
    own vertical center.

    Used for exactly one topology this module supports: a two-device stack
    where a single 2-terminal net's pads are the stack's two *outer*
    (non-facing) terminals -- ``tgate_3v3``'s ``A`` net is the motivating
    case (see the module docstring's "TRANSMISSION-GATE TOPOLOGY" section).
    Callers select this path per-net via :func:`build_stack_cell`'s
    ``bypass_nets`` argument; :func:`_connect_pads` remains the default for
    every net whose two pads *are* the adjacent (facing) pair.
    """
    half = width / 2.0
    y_a = (pad_a[1] + pad_a[3]) / 2.0
    y_b = (pad_b[1] + pad_b[3]) / 2.0
    # The vertical lane and each horizontal jog both extend to lane_x-half
    # (the lane's own far edge), not just to its centerline -- so the T
    # junction where a jog meets the lane is a single filled rectangle
    # union with no thin diagonal notch (an M1.1-width violation on the
    # merged polygon's corner, not a DRC issue with either piece alone).
    canvas.rect("metal1", lane_x - half, min(y_a, y_b) - half, lane_x + half, max(y_a, y_b) + half)
    canvas.rect("metal1", min(lane_x - half, pad_a[2]), y_a - half, max(lane_x + half, pad_a[2]), y_a + half)
    canvas.rect("metal1", min(lane_x - half, pad_b[2]), y_b - half, max(lane_x + half, pad_b[2]), y_b + half)


def well_tap(canvas: Canvas, kind: str, x0: float, y0: float, net: str) -> tuple[float, float, float, float]:
    """A small square substrate/n-well tie: comp + implant + contact + Metal1 pad.

    ``kind='n'``: n-well tie (comp + ``nplus``), tied to the PMOS body net.
    ``kind='p'``: substrate tie (comp + ``pplus``), tied to the NMOS body net.
    Returns the drawn Metal1 pad, for the caller to wire to the rest of that
    net.

    Public (not module-private) because a composite macro built from several
    :func:`draw_column` instances in one shared ``Canvas`` (issue #308's
    ``dff_tg_3v3``) draws its own periodic taps directly with this same
    function, rather than the one-tap-per-column placement
    :func:`build_stack_cell` does below -- see ``dff_tg_3v3.py``'s module
    docstring for why a composite needs periodic, not per-device, taps.
    """
    x1 = x0 + TAP_SIZE_UM
    y1 = y0 + TAP_SIZE_UM
    canvas.rect("comp", x0, y0, x1, y1)
    implant_layer = "nplus" if kind == "n" else "pplus"
    canvas.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y0 - IMPLANT_MARGIN_UM,
        x1 + IMPLANT_MARGIN_UM,
        y1 + IMPLANT_MARGIN_UM,
    )
    xs = _contact_positions(x0, x1)
    ys = _contact_positions(y0, y1)
    for cx in xs:
        for cy in ys:
            canvas.rect("contact", cx, cy, cx + CONTACT_SIZE_UM, cy + CONTACT_SIZE_UM)
    pad = (
        x0 - METAL1_PAD_MARGIN_UM,
        y0 - METAL1_PAD_MARGIN_UM,
        x1 + METAL1_PAD_MARGIN_UM,
        y1 + METAL1_PAD_MARGIN_UM,
    )
    canvas.rect("metal1", *pad)
    canvas.pin(net, *pad)
    return pad


@dataclass
class LeafCell:
    canvas: Canvas
    ports: list[MosfetPorts] = field(default_factory=list)
    pins: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    nwell_box: tuple[float, float, float, float] | None = None
    footprint: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def draw_column(canvas: Canvas, devices: Sequence[Device], x0: float, y0: float = 0.0) -> list[MosfetPorts]:
    """Draw ``devices`` as one left-aligned vertical column, bare -- no net
    wiring, no pin promotion, no well/substrate tap. This is exactly the
    drawing step :func:`build_stack_cell` performs internally (same stacking
    order/gaps), extracted so a composite macro assembling *several* such
    columns into one shared ``Canvas`` (e.g. ``dff_tg_3v3.py``, issue #308)
    can draw each instance's devices without also triggering
    :func:`build_stack_cell`'s own per-column net-count-based auto-wiring --
    which only ever sees that one column's own 1-2 device terminals and so
    cannot resolve a net that also has terminals in a *different* column of
    the same composite (see that module's docstring for why the composite
    resolves nets itself, via :func:`route_net`, instead).
    """
    ports: list[MosfetPorts] = []
    y_cursor = y0
    for i, d in enumerate(devices):
        if i > 0:
            gap = NWELL_TO_NMOS_GAP_UM if d.kind != devices[i - 1].kind else COMP_GAP_UM
            y_cursor += gap
        p = mosfet(canvas, d, x0, y_cursor)
        ports.append(p)
        y_cursor = p.y3
    return ports


def build_stack_cell(
    top_name: str,
    devices: Sequence[Device],
    *,
    x0: float = 0.0,
    add_taps: bool = True,
    bypass_nets: frozenset[str] = frozenset(),
) -> LeafCell:
    """Draw ``devices`` as a single left-aligned vertical column.

    ``devices`` is ordered bottom-to-top. Adjacent devices of the same
    ``kind`` get :data:`COMP_GAP_UM` of clearance; a ``kind`` change (an
    n-well boundary) gets :data:`NWELL_TO_NMOS_GAP_UM`. Every net named by
    exactly one device terminal (across the whole list) is promoted to a
    top-level pin; every net named by exactly two is wired together --
    normally with a straight Metal1 run (see :func:`_connect_pads`), or, for
    any net name listed in ``bypass_nets``, via the dedicated clear-lane
    router instead (see :func:`_bypass_wire`). A net named by zero or more
    than two terminals is a caller error (raises ``ValueError``) -- this
    module's wiring is intentionally not a general router; see the module
    docstring for the supported topology.

    ``bypass_nets`` exists for exactly one case this module supports beyond
    the "facing pads only" wiring :func:`_connect_pads` handles: a
    2-terminal net whose two pads are the stack's two *outer* (non-facing)
    terminals, which a straight vertical run would otherwise have to route
    directly through the *other* net's own facing connection -- physically
    merging the two nets into one (a real, silent LVS-incorrect short, not a
    DRC violation, since two overlapping same-layer shapes are not a DRC
    error). ``tgate_3v3``'s ``A`` net is the motivating case; see the module
    docstring's "TRANSMISSION-GATE TOPOLOGY" section for the full
    derivation and the concrete LVS mismatch this was caught by.
    """
    if not devices:
        raise ValueError("build_stack_cell() needs at least one device")

    canvas = Canvas(top_name)
    ports = draw_column(canvas, devices, x0)

    # --- net resolution: gate/top/bottom terminals only (well/substrate
    # ties are handled separately, below, and wired onto whichever pad
    # already carries their net). ---
    terminals: dict[str, list[tuple[float, float, float, float]]] = {}
    for d, p in zip(devices, ports):
        terminals.setdefault(d.gate_net, []).append(p.gate_pad)
        terminals.setdefault(d.top_net, []).append(p.top_pad)
        terminals.setdefault(d.bottom_net, []).append(p.bottom_pad)

    pins: dict[str, tuple[float, float, float, float]] = {}
    # The bypass lane sits to the right of every device's own widest drawn
    # Metal1 edge (gate pads included, though they never dominate this max --
    # they are always the leftmost feature in this module's geometry
    # convention) -- see :data:`BYPASS_LANE_CLEARANCE_UM`'s derivation for
    # why the right side, not a fixed offset from x0, generalizes safely
    # across devices of different width in the same stack.
    rightmost_edge_um = max(
        edge
        for p in ports
        for pad in (p.gate_pad, p.top_pad, p.bottom_pad)
        for edge in (pad[2],)
    )
    lane_x = rightmost_edge_um + BYPASS_LANE_CLEARANCE_UM + METAL1_WIRE_WIDTH_UM / 2.0
    used_bypass = False
    for net, pads in terminals.items():
        if len(pads) == 1:
            canvas.pin(net, *pads[0])
            pins[net] = pads[0]
        elif len(pads) == 2:
            if net in bypass_nets:
                _bypass_wire(canvas, pads[0], pads[1], lane_x)
                used_bypass = True
            else:
                _connect_pads(canvas, pads[0], pads[1])
        else:
            raise ValueError(
                f"net {net!r} has {len(pads)} device terminals in this stack; "
                "build_stack_cell() only resolves 1- or 2-terminal nets automatically"
            )

    # --- n-well: encloses every pfet device (+ its own tie, added below),
    # with NWELL_MARGIN_UM clearance past the outermost pfet comp edge. ---
    pfet_ports = [p for p in ports if p.kind == "pfet"]
    nwell_box = None
    if pfet_ports:
        pfet_y0 = min(p.y0 for p in pfet_ports)
        pfet_y1 = max(p.y3 for p in pfet_ports)
        pfet_x1 = max(p.x1 for p in pfet_ports)
        tap_extent = (TAP_GAP_UM + TAP_SIZE_UM) if add_taps else 0.0
        nwell_box = (
            x0 - NWELL_MARGIN_UM,
            pfet_y0 - NWELL_MARGIN_UM,
            pfet_x1 + NWELL_MARGIN_UM,
            pfet_y1 + tap_extent + NWELL_MARGIN_UM,
        )
        canvas.rect("nwell", *nwell_box)

    footprint_y0 = min(p.y0 for p in ports)
    footprint_y1 = max(p.y3 for p in ports)
    footprint_x0 = x0 - POLY_ENDCAP_UM - METAL1_PAD_MARGIN_UM
    footprint_x1 = max(p.x1 for p in ports)
    if nwell_box is not None:
        footprint_x0 = min(footprint_x0, nwell_box[0])
        footprint_x1 = max(footprint_x1, nwell_box[2])
        footprint_y1 = max(footprint_y1, nwell_box[3])
    if used_bypass:
        footprint_x1 = max(footprint_x1, lane_x + METAL1_WIRE_WIDTH_UM / 2.0)

    if add_taps:
        pfet_ports_top = max(pfet_ports, key=lambda p: p.y3, default=None)
        nfet_ports_bottom = min((p for p in ports if p.kind == "nfet"), key=lambda p: p.y0, default=None)

        if pfet_ports_top is not None:
            d_top = next(d for d, p in zip(devices, ports) if p is pfet_ports_top)
            net = d_top.body_net if d_top.body_net is not None else d_top.top_net
            tap_x0 = pfet_ports_top.x0
            tap_y0 = pfet_ports_top.y3 + TAP_GAP_UM
            tap_pad = well_tap(canvas, "n", tap_x0, tap_y0, net)
            if net == d_top.top_net:
                # Same net as the device's own S/D pad (the common case: an
                # inverter's PMOS source *is* VDD) -- merge them with a
                # Metal1 run so both labels land on one physically-joined
                # shape.
                _connect_pads(canvas, pfet_ports_top.top_pad, tap_pad)
            # else: an explicit body_net that differs from top_net (e.g. a
            # transmission gate's pass device, whose top_net is a signal
            # net) -- do NOT wire the tap's pad to the device's own S/D pad;
            # that would short the body-tie net onto the diffusion net.
            # well_tap() already independently labels `net` on the tap's
            # own pad, and the tap's comp sits inside the same continuous
            # n-well as the device (see nwell_box, above), so the body ties
            # correctly through the well itself with no Metal1 needed.
            footprint_y1 = max(footprint_y1, tap_y0 + TAP_SIZE_UM + NWELL_MARGIN_UM)

        if nfet_ports_bottom is not None:
            d_bot = next(d for d, p in zip(devices, ports) if p is nfet_ports_bottom)
            net = d_bot.body_net if d_bot.body_net is not None else d_bot.bottom_net
            tap_x0 = nfet_ports_bottom.x0
            tap_y1 = nfet_ports_bottom.y0 - TAP_GAP_UM
            tap_y0 = tap_y1 - TAP_SIZE_UM
            tap_pad = well_tap(canvas, "p", tap_x0, tap_y0, net)
            if net == d_bot.bottom_net:
                _connect_pads(canvas, nfet_ports_bottom.bottom_pad, tap_pad)
            footprint_y0 = min(footprint_y0, tap_y0 - COMP_GAP_UM)

    footprint = (footprint_x0, footprint_y0, footprint_x1, footprint_y1)

    return LeafCell(canvas=canvas, ports=ports, pins=pins, nwell_box=nwell_box, footprint=footprint)


# ---------------------------------------------------------------------------
# Composite-macro routing fabric (issue #308's ``dff_tg_3v3``)
# ---------------------------------------------------------------------------
#
# ``build_stack_cell()``'s Metal1-only wiring (above) resolves nets by
# counting *that one column's own* device terminals -- correct for a
# standalone leaf cell (``inv_3v3``/``tgate_3v3``), but not for a composite
# built from several such columns placed side by side in one shared
# ``Canvas``: most of a composite's nets fan out across columns (e.g.
# ``dff_tg_3v3``'s clock/clock-bar nets each reach four transmission-gate
# instances), which is outside what a same-layer, same-column straight-line
# connector can safely wire without risking a same-layer short against an
# unrelated intervening net or device (exactly the class of failure
# ``build_stack_cell()``'s own "TRANSMISSION-GATE TOPOLOGY" docstring section
# documents for a *single* column's two nets -- multiplied across many
# columns and nets here).
#
# The fix is the same one ``lock_detector/primitives.py`` already proved out
# for its own (horizontal-flow) composite macros: every net rides a
# dedicated Metal3 "riser" from each of its Metal1 pads up/down to one
# Metal2 "bus" at a track_y unique to that net (:class:`NetTracks`), so two
# unrelated nets can never risk a same-layer collision regardless of
# placement, and a net's own Metal3 risers may freely cross any other net's
# Metal2 bus (different layers, no via between them -- not a short, not a
# spacing violation). Repeated here (not imported) per this package's "each
# full-custom leaf-cell family owns its own generator" convention --
# identical values/derivation to ``lock_detector/primitives.py``'s own
# proven-DRC-clean routing fabric; see that module's docstring for the full
# per-rule citation.
#
# Unlike ``lock_detector``'s own ``route_net()``, this one does **not**
# snap same-net pads that are merely close in *x* onto a single shared
# riser: ``lock_detector``'s horizontal-flow cells only ever place two
# same-net pads that close together when they are *also* adjacent in y (a
# device's own pad right next to a periodic tap's), so collapsing them onto
# one averaged riser point stays on both pads' physical footprint. This
# package's vertical-flow columns instead routinely put a shared net's two
# pads at the *same x but far apart in y* -- an ``inv_3v3`` instance's own
# ``A`` gate net ties both devices' gate pads, which sit at the same x (both
# devices are left-aligned at the column's own ``x0``) several microns apart
# in y (the NMOS-PMOS well gap). Averaging those into one riser point would
# place the via where *neither* pad's own Metal1 actually is -- a broken
# connection, not a via-size DRC violation, so nothing would flag it short
# of an actual LVS run. This module instead draws one riser per pad,
# unconditionally: two risers for the same net at the same x is not a
# problem (their Metal3/Metal2 paths simply overlap, which is legal --
# same net, same layer), and it is correct regardless of how far apart in y
# a net's pads happen to be.


def pad_center(pad: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((pad[0] + pad[2]) / 2.0, (pad[1] + pad[3]) / 2.0)


# Smallest axis-aligned box enclosing every box given -- shared with every
# other ``layout/pll_top/*`` submodule (issue #332, ``_canvas.bbox_union()``).
bbox_union = _canvas.bbox_union


def nwell_over(canvas: Canvas, boxes: Sequence[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """Draw one nwell rectangle enclosing every PMOS comp box (+ any ntap
    box) given, with :data:`NWELL_MARGIN_UM` margin -- the one-shared-nwell
    convention a composite macro uses instead of :func:`build_stack_cell`'s
    per-column nwell (see ``dff_tg_3v3.py``'s module docstring).
    """
    x0, y0, x1, y1 = bbox_union(boxes)
    well = (x0 - NWELL_MARGIN_UM, y0 - NWELL_MARGIN_UM, x1 + NWELL_MARGIN_UM, y1 + NWELL_MARGIN_UM)
    canvas.rect("nwell", *well)
    return well


def offset_pad_x(
    canvas: Canvas,
    pad: tuple[float, float, float, float],
    target_dx: float,
    via_half_um: float = VIA1_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM,
) -> tuple[float, float]:
    """Return a routing point ``target_dx`` away (signed) from ``pad``'s own
    natural center in x, extending ``pad`` with extra Metal1 (same net --
    guaranteed overlap, since the extension shares the pad's own full
    y-range) only if the natural pad is not already wide enough to keep a
    via centred there fully enclosed.

    Exists because :func:`mosfet` places a device's *top* and *bottom*
    terminal pads (and, when a column's two devices' gates are on
    independent nets, their two *gate* pads) at the exact same x -- current
    flows through one vertical comp island, so a device's own drain/source
    terminals are necessarily the same comp's top and bottom, same x by
    construction. That is invisible to a *standalone* leaf cell (only ever
    one net per pad, wired same-column with a plain Metal1 run -- see
    :func:`build_stack_cell`), but a real, concretely-observed bug for a
    composite macro's :func:`route_net`-based fabric: two *different* nets'
    risers landing at the same x draw overlapping same-layer Metal3, which
    is not a DRC violation (no via, no spacing check trips) but silently
    shorts them -- exactly what a first, unoffset attempt at
    ``dff_tg_3v3.py`` hit (LVS extracted one node merging ``D``/``Q``/
    ``QB``/``VDD``/``VSS`` and several devices' widths summed together, from
    every device's own top/bottom pad pair colliding, and every
    ``tgate_3v3`` instance's independent ``GN``/``GP`` gate pads colliding
    too).

    A second attempt, offsetting by a large, fixed Metal1 extension
    regardless of whether the pad already had room, over-corrected into a
    *different* concretely-observed failure: the wide extension (drawn to
    reach well clear of the pad's own column-mate) reached far enough into
    the inter-column gap to nearly touch -- overlapping by a fraction of a
    micron, not clearing it -- the periodic n-well tap's own Metal1 pad
    placed at that gap's midpoint, leaving an M1.1-violating sliver where
    the two nearly-but-not-quite-aligned rectangles met. Extending only the
    minimum needed to enclose the *target* via position (usually nothing at
    all for a pad already wider than ``target_dx``, e.g. every ``pfet``'s
    own top/bottom pad -- only the narrower ``nfet``'s needs a small
    extension) keeps every reach well short of the gap's own midpoint,
    fixing both failures at once. ``dff_tg_3v3.py``'s ``build()`` calls this
    for every top pad (positive ``target_dx``) and every pfet gate pad
    (negative), leaving bottom pads and nfet gate pads at their natural
    center -- see that module's own docstring for the exact deltas and the
    clearance check against neighbouring columns/taps.
    """
    x0, y0, x1, y1 = pad
    y_c = (y0 + y1) / 2.0
    target_x = (x0 + x1) / 2.0 + target_dx
    need_x0 = min(x0, target_x - via_half_um)
    need_x1 = max(x1, target_x + via_half_um)
    if need_x0 < x0 or need_x1 > x1:
        canvas.rect("metal1", need_x0, y0, need_x1, y1)
    return (target_x, y_c)


# Draw one square via + a Metal1/2/3 riser landing it on a shared bus
# (issue #332, ``_canvas._via_square()``/``_canvas._riser()``). This module
# is now ``_canvas._riser()``'s only caller: ``lock_detector/primitives.py``
# shared it until issue #322, and ``pfd_cp/cp_dumpbuf.py`` never did -- both
# of those risers are structurally different and stay local; see each one's
# own docstring for why. ``_via_square()`` is still shared by all three.
_riser = partial(
    _canvas._riser,
    via1_size_um=VIA1_SIZE_UM,
    via2_size_um=VIA2_SIZE_UM,
    via_enclosure_um=VIA_ENCLOSURE_UM,
    metal3_width_um=METAL3_WIRE_WIDTH_UM,
)


def route_net(
    canvas: Canvas,
    net: str,
    pad_centers: Sequence[tuple[float, float]],
    track_y: float,
    width: float = METAL2_WIRE_WIDTH_UM,
    *,
    bus_to_x: float | None = None,
) -> None:
    """Tie every ``pad_centers`` Metal1 landing point to one shared Metal2 bus at ``track_y``.

    One riser per pad, unconditionally -- see this section's module-level
    docstring for why no "snap close pads together" merge is applied here
    (unlike ``lock_detector/primitives.py``'s own ``route_net()``).
    ``track_y`` must be unique per net *among nets whose x extents overlap*
    -- see :class:`NetTracks` (a fresh track per net) and :func:`pack_tracks`
    (one track shared by several non-colliding nets).

    ``bus_to_x`` extends the drawn Metal2 bus out to that x without drawing a
    riser there: the landing this net's own cross-row Metal3 :func:`route_spine`
    link comes down onto, for a caller assembling several stacked rows
    (``divider_chain.py``, issue #344). ``None`` (the default, and every
    single-row caller in this package) draws exactly the bus the pads
    themselves span, byte-for-byte as before.
    """
    pad_centers = list(pad_centers)
    if not pad_centers:
        raise ValueError(f"route_net(): net {net!r} has no pads to route")
    for x, y in pad_centers:
        _riser(canvas, x, y, track_y)
    xs = [x for x, _ in pad_centers]
    if bus_to_x is not None:
        xs.append(bus_to_x)
    x_lo, x_hi = min(xs), max(xs)
    half = width / 2.0
    if x_hi > x_lo:
        canvas.rect("metal2", x_lo - half, track_y - half, x_hi + half, track_y + half)
    else:
        # A single-pad net still needs a via/landing (drawn above by the
        # loop's one riser) but no bus run -- nothing to span.
        pass


def route_spine(
    canvas: Canvas,
    x: float,
    track_ys: Sequence[float],
    width: float = METAL3_WIRE_WIDTH_UM,
) -> None:
    """One net's vertical Metal3 link joining that net's per-row Metal2 buses.

    The cross-row counterpart of :func:`route_net` (issue #344). A folded
    block draws one *independent* packed track band per row
    (:func:`pack_tracks`, issue #341), so a net with pads in more than one row
    gets a separate bus per row and needs those buses tied together. This
    draws that tie: one continuous Metal3 run at ``x``, spanning
    ``min(track_ys) .. max(track_ys)``, with a Via2 + Metal3/Metal2 landing
    square at *every* ``track_ys`` entry (not only the two ends -- a net
    present in three or more rows lands on each).

    ``x`` must be a column reserved for this net alone and clear of every
    row's own drawn content, since the run crosses every intervening row's
    full height. ``divider_chain.py`` reserves those columns in a dedicated
    left-hand spine region at negative x, outside every row's own extent, so
    the only same-layer neighbours are the other spine columns (kept apart by
    that module's own ``SPINE_PITCH_UM``). Everything the run passes *over*
    is Metal2 (each row's own buses) or Metal1/device geometry -- different
    layers with no via between them, the same no-crossing-cost property
    :func:`_riser`'s own long Metal3 run already relies on.
    """
    ys = sorted(set(track_ys))
    if not ys:
        raise ValueError(f"route_spine(): no track_y values at x={x}")
    half_w = width / 2.0
    if ys[-1] > ys[0]:
        canvas.rect("metal3", x - half_w, ys[0], x + half_w, ys[-1])
    for y in ys:
        half = _canvas._via_square(canvas, "via2", x, y, VIA2_SIZE_UM, VIA_ENCLOSURE_UM)
        canvas.rect("metal3", x - half, y - half, x + half, y + half)
        canvas.rect("metal2", x - half, y - half, x + half, y + half)


class NetTracks:
    """Hands out a fresh, never-reused Metal2 track_y per net name.

    Because every track is unique (monotonically increasing by
    :data:`METAL2_TRACK_PITCH_UM`), two nets' buses can never be closer than
    the pitch on the Y axis -- eliminating same-layer Metal2 collisions
    between different nets by construction, independent of each net's own
    bus's x extent (see :func:`route_net`/:func:`_riser`'s docstrings).
    """

    def __init__(self, base_y: float, pitch: float = METAL2_TRACK_PITCH_UM) -> None:
        self._next_y = base_y
        self._pitch = pitch
        self._assigned: dict[str, float] = {}

    def get(self, net: str) -> float:
        if net not in self._assigned:
            self._assigned[net] = self._next_y
            self._next_y += self._pitch
        return self._assigned[net]


# --- track *reuse* for a large, mostly-local net population (issue #341) ---
#
# :class:`NetTracks` is the right tool for a composite with a handful of
# nets, most of which reach across the composite's *entire* width anyway
# (``dff_tg_3v3``'s clock nets, ``div23_cell``'s internal nets): giving every
# net its own track costs nothing extra there, because most tracks would end
# up nearly full-width regardless.
#
# ``divider_chain.py``'s own top-level assembly is a different regime: 71
# nets, many of which are genuinely *local* -- a one-hot-mux net whose two
# pads are both inside the glue-logic region, or a chain net whose only two
# far-apart uses still leave most of the block's width untouched by it.
# Handing every one of those its own :data:`METAL2_TRACK_PITCH_UM`-tall track
# regardless is exactly the "one global track per net, even though most nets
# are local" cost issue #341 measured: ~71 tracks x 0.75 um = ~53 um, more
# than half the block's total height, for a track band that (per net) is
# mostly empty in x.
#
# :func:`pack_tracks` is the fix: the same *track assignment* step a real
# channel router performs (not a channel router itself -- this package's
# per-net Metal1-pad-to-Metal2-bus wiring via :func:`route_net` is
# unchanged), reusing one track_y for every net whose drawn Metal2 bus
# extent -- x_lo .. x_hi across all its own pads, exactly the rectangle
# :func:`route_net` draws -- does not come within
# :data:`METAL2_TRACK_PITCH_UM` - :data:`METAL2_WIRE_WIDTH_UM` of another
# net's already on that track. This is the textbook "left-edge algorithm"
# for interval-graph track assignment: sorting by each interval's own left
# edge and greedily reusing the first track whose last-placed interval ends
# early enough is known to use the *minimum* number of tracks for an
# interval graph (the maximum number of nets whose extents mutually
# overlap at any single x) -- so this is not a heuristic that might miss a
# packing opportunity a smarter one would find, it is provably optimal for
# this 1-D placement problem.
#
# Two full-width nets (this block's own ``VDD_DIV``/``VSS`` supply trunks,
# whose pads span every column) can never share a track with anything, so
# they alone still cost two full tracks -- :func:`pack_tracks` cannot do
# better than :class:`NetTracks` there. The win is entirely on the nets
# whose extent leaves the rest of the block's width free for something
# else's bus.
def _net_x_extent(pad_centers: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """The physical x-range one net's drawn Metal2 geometry occupies at its
    own track_y -- not just :func:`route_net`'s own bus rectangle
    (``x_lo - METAL2_WIRE_WIDTH_UM/2 .. x_hi + METAL2_WIRE_WIDTH_UM/2``), but
    the wider of that and each end riser's own Via2/Metal2 landing square
    (:func:`_canvas._riser`'s ``half_m3_top = VIA2_SIZE_UM/2 + VIA_ENCLOSURE_UM``,
    which is wider than half the bus wire's own width) -- so a net's true
    left/rightmost drawn shape at ``track_y`` is never underestimated at the
    two extreme pads, where the landing square is what actually reaches
    furthest, not the bus wire.
    """
    xs = [x for x, _ in pad_centers]
    half = max(METAL2_WIRE_WIDTH_UM / 2.0, VIA2_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM)
    return (min(xs) - half, max(xs) + half)


def pack_tracks(
    nets: dict[str, Sequence[tuple[float, float]]],
    base_y: float,
    *,
    pitch: float = METAL2_TRACK_PITCH_UM,
    clearance: float = METAL2_TRACK_PITCH_UM - METAL2_WIRE_WIDTH_UM,
) -> dict[str, float]:
    """Assign every net in ``nets`` a track_y, reusing a track across any
    nets whose drawn extents (:func:`_net_x_extent`) do not come within
    ``clearance`` of each other -- see this section's own module-level
    comment for the algorithm and why it is optimal, not merely "good
    enough".

    ``clearance`` defaults to the same margin :class:`NetTracks` already
    uses *between* two tracks in y (``METAL2_TRACK_PITCH_UM -
    METAL2_WIRE_WIDTH_UM`` = 0.41 um, comfortably over M2.2a's 0.28 um
    minimum Metal2 spacing) -- reused here as the required x-direction gap
    between two different nets' bus rectangles sharing one track, rather
    than re-derived, since it is the same rule (minimum same-layer Metal2
    spacing) applying along the other axis.

    Requires every net to have at least one pad (same precondition
    :func:`route_net` already enforces); raises ``ValueError`` otherwise, one
    net at a time, naming it -- the same discipline
    :func:`build_stack_cell`/:func:`build_row_cell` already use for a caller
    error rather than a confusing downstream KeyError.
    """
    extents: dict[str, tuple[float, float]] = {}
    for net, pads in nets.items():
        pads = list(pads)
        if not pads:
            raise ValueError(f"pack_tracks(): net {net!r} has no pads to route")
        extents[net] = _net_x_extent(pads)

    # Left-edge algorithm: process nets in increasing left-edge order (ties
    # broken by name, for determinism), placing each on the first track
    # whose most-recent occupant ends early enough to clear this net's own
    # left edge by `clearance`; open a new track only when none does.
    order = sorted(extents, key=lambda n: (extents[n][0], n))
    track_right: list[float] = []
    track_of: dict[str, int] = {}
    for net in order:
        lo, hi = extents[net]
        for i, right in enumerate(track_right):
            if lo >= right + clearance:
                track_right[i] = hi
                track_of[net] = i
                break
        else:
            track_right.append(hi)
            track_of[net] = len(track_right) - 1

    return {net: base_y + i * pitch for net, i in track_of.items()}


# ===========================================================================
# ROW CELLS -- static-CMOS gates with real fan-in (issue #307, Part 2 of #295)
# ===========================================================================
#
# WHY build_stack_cell() IS NOT ENOUGH
# ------------------------------------
# :func:`build_stack_cell` draws exactly one vertical column and only
# resolves 1- and 2-terminal nets (it raises ``ValueError`` on anything
# else, by design). That covers ``inv_3v3``/``tgate_3v3`` -- issue #306's
# two proof cells, two devices each, no fan-in. It cannot draw this issue's
# NAND/NOR cells at all: ``design/nand3_3v3.sch``'s output ``Y`` has *four*
# device terminals (the series NMOS stack's top drain plus each of three
# parallel PMOS drains), and ``VDD`` has three.
#
# ``pfd_cp/rowgen.py`` (issue #300) hit the same wall for the PFD/CP block
# and solved it with a horizontal-current-flow row generator wired into a
# whole-block assembly. That module's cells are not standalone -- their
# rails, taps and routing band belong to the block, not the cell -- so it is
# not directly reusable for this issue's requirement (four *standalone*
# DRC/LVS-clean leaf cells). :func:`build_row_cell` below is the
# ``divider_chain`` package's own answer: it keeps ``devgen``'s
# vertical-current-flow :func:`mosfet` geometry byte-for-byte (so the leaf
# devices are the exact shapes #306 already proved clean) and adds a
# column/row placement model plus a two-layer routing model around it.
#
# PLACEMENT MODEL: COLUMNS, NOT A SINGLE STACK
# --------------------------------------------
# A cell is an ordered list of :class:`Column`\s, left to right. Each column
# holds at most one ``pulldown`` branch (nfet-only, bottom-to-top series
# devices) and at most one ``pullup`` branch (pfet-only, bottom-to-top). All
# pulldown branches share one baseline (:data:`ROW_PD_Y0`) and all pullup
# branches share another (:data:`ROW_PU_Y0`) -- these are *fixed module
# constants*, not derived per cell, which is what makes every cell this
# function draws share one row-cell frame (see "ROW-CELL FRAME" below).
#
# Mapping a schematic onto columns is mechanical: one column per parallel
# branch of whichever network has fan-in, with the *other* network's single
# series branch living in the first column. ``nand2_3v3`` is two columns
# (series NMOS pair + ``MPA`` | ``MPB``); ``nor2_3v3`` is two columns
# (``MNA`` + series PMOS pair | ``MNB``); ``inv2x_3v3`` is one column.
#
# ROUTING MODEL: METAL1 STRAPS + METAL2 TRACKS (no same-layer crossings)
# ----------------------------------------------------------------------
# This is the part that had to change from a first, Metal1-only attempt,
# and the reason is worth recording because it is a property of the
# topology, not of any particular cell:
#
#   With one routing layer there is no crossing-free assignment for
#   ``nand2_3v3``. Its output ``Y`` must reach *under* both pullup
#   branches, and its two input nets must each reach *across* the cell from
#   an NMOS gate to a PMOS gate. Whichever horizontal ordering the input
#   spines take in the inter-row channel, one pullup branch's own Y drop or
#   gate riser is left having to cross the other input's spine. Worked
#   through exhaustively for nand2's four possible orderings before
#   switching layers.
#
# So: **Metal1 carries only vertical straps, Metal2 only horizontal
# tracks**, joined by one via1 where a strap meets its own track. A strap
# crossing an unrelated track is two different layers with no via between
# them -- not a short and not a spacing violation. That is the same
# three-layer discipline ``pfd_cp/rowgen.py``'s docstring states, with
# Metal3 dropped (a leaf cell never has to cross a whole row pair).
#
#   * **Gate straps** run in per-device *lanes* reserved in each column's
#     own left margin, reached by a short horizontal jog at the gate pad's
#     own y-centre. Lanes are ranked by distance from the inter-row channel
#     -- the device *farthest* from the channel gets the *outermost* lane --
#     so an outer device's jog (drawn at its own gate y, beyond every inner
#     device's gate y) never crosses an inner device's strap (which only
#     ever spans from its own gate y *towards* the channel). Pulldown lanes
#     are the inner set and pullup lanes the outer set of the same margin;
#     they cannot collide because a pulldown strap lives entirely below the
#     channel and a pullup strap entirely above it.
#   * **Channel straps** are the S/D terminals facing the inter-row channel
#     (a pulldown branch's topmost drain, a pullup branch's bottommost
#     drain). Nothing is drawn between such a pad and the channel, so the
#     strap is a straight vertical run at the pad's own x-centre.
#   * **Rail straps** are the S/D terminals facing *away* from the channel
#     (a pulldown branch's bottom source, a pullup branch's top source).
#     They run straight out to the cell's own supply rail.
#   * Any *other* S/D terminal -- an interior device's pad that is not part
#     of a same-branch series connection -- raises ``NotImplementedError``
#     rather than being drawn wrong. None of this issue's four cells
#     produce one.
#
# Same-branch series nets (``NMID``, ``NM1``/``NM2``, ``PMID``) never reach
# any of that: they are resolved first and locally, with the same
# straight-line :func:`_connect_pads` :func:`build_stack_cell` already uses.
#
# ROW-CELL FRAME (the abutment contract)
# --------------------------------------
# Every cell :func:`build_row_cell` draws has the *same* height and the
# *same* rail y-bands, independent of how many columns it has or how tall
# its tallest branch is: the pulldown baseline, the pullup baseline, the tap
# rows and both rails are fixed module constants sized for the tallest cell
# in this family (``nand3_3v3``'s three-high NMOS stack, ``nor2_3v3``'s
# two-high PMOS stack). That is what lets Parts 3/4 (#308's ``dff_tg_3v3``,
# #309's ``div23_cell``) place these cells side by side in a row and have
# their ``VDD``/``VSS`` rails line up and touch.
#
# This is a *stricter* frame than issue #306's two cells have: those are
# drawn by :func:`build_stack_cell`, whose height follows its own device
# list, and are deliberately left untouched here so their landed evidence
# (``layout/evidence/divider-inv-proof/``,
# ``layout/evidence/divider-tgate-proof/``) still describes the GDS this
# module produces. Re-emitting ``inv_3v3``/``tgate_3v3`` into this frame is
# Part 3's problem, not this issue's -- see
# ``layout/evidence/divider-rowcells-proof/PROOF.md``'s "Known gap" section.

# --- Row-cell frame: fixed y coordinates shared by every cell
# build_row_cell() draws (see "ROW-CELL FRAME" above). Sized for the tallest
# member of this family; a cell with a shorter branch simply leaves more
# room in the inter-row channel, it does not move any of these. ---
ROW_PD_Y0 = 0.0  # pulldown (nfet) row comp baseline -- same origin build_stack_cell() uses
ROW_PU_Y0 = 10.0  # pullup (pfet) row comp baseline. The tallest pulldown branch in
# this family is nand3_3v3's three-high stack: 3*(2*SD_OVERHANG_UM + L) +
# 2*COMP_GAP_UM = 5.04 um, so the nfet-comp-to-nwell-edge clearance is
# 10.0 - 5.04 - NWELL_MARGIN_UM = 4.46 um -- more than build_stack_cell()'s
# own proven NWELL_TO_NMOS_GAP_UM (4.0), itself >> DF.16_LV's 0.43 min.
ROW_NTAP_Y0 = 14.4  # n-well tap comp bottom. The tallest pullup branch is nor2_3v3's
# two-high stack, topping out at ROW_PU_Y0 + 2*1.28 + COMP_GAP_UM = 13.16;
# 14.4 leaves >= TAP_GAP_UM (1.0) of tap-comp-to-device-comp clearance.
ROW_PTAP_Y1 = ROW_PD_Y0 - TAP_GAP_UM  # p-substrate tap comp top edge (-1.0)
ROW_PTAP_Y0 = ROW_PTAP_Y1 - TAP_SIZE_UM

# Both supply rails are drawn exactly over their own tap row's Metal1 pad,
# so rail and tap merge into one shape with no extra connector: the rail's
# height is the tap pad's height and its centreline is the tap pad's own
# centre.
ROW_RAIL_H_UM = TAP_SIZE_UM + 2 * METAL1_PAD_MARGIN_UM
ROW_VSS_RAIL_CY = ROW_PTAP_Y0 + TAP_SIZE_UM / 2.0
ROW_VDD_RAIL_CY = ROW_NTAP_Y0 + TAP_SIZE_UM / 2.0

# Fixed cell extent in y: the p-tap's own implant edge at the bottom, the
# n-well's own edge at the top. Identical for every cell this function
# draws -- layout/tests/test_divider_rowcells.py asserts it.
ROW_CELL_Y0 = ROW_PTAP_Y0 - IMPLANT_MARGIN_UM
ROW_CELL_Y1 = ROW_NTAP_Y0 + TAP_SIZE_UM + NWELL_MARGIN_UM
ROW_CELL_H_UM = ROW_CELL_Y1 - ROW_CELL_Y0

# --- Two-layer routing geometry. Reuses this module's own
# :data:`VIA1_SIZE_UM` / :data:`VIA_ENCLOSURE_UM` (0.26 / 0.09 -- V1.1's
# exact via1 size and V1.3a's enclosure, shared with issue #308's composite
# fabric above). The remaining values are restated from pfd_cp/rowgen.py,
# which proved them DRC-clean on this deck for a 108-transistor block; see
# that module's own per-constant citations. ---
ROW_STRAP_W_UM = VIA1_SIZE_UM + 2 * VIA_ENCLOSURE_UM  # 0.44
# 0.44, not this module's own METAL1_WIRE_WIDTH_UM (0.28): a via1 landing
# needs 0.44 of enclosing metal, and a 0.44 landing on a 0.28 strap leaves a
# concave notch that M1.2a reports as an intra-net space violation (the
# concrete failure rowgen.py's METAL1_WIRE_WIDTH_UM comment records). Making
# the whole strap 0.44 means a via never widens the wire it sits on. 0.44 is
# also >= 0.34, so the "narrow metal line" end-of-line via-overlap clauses
# (V1.3c/V1.4b) never apply.
ROW_TRACK_W_UM = ROW_STRAP_W_UM  # Metal2 track width; > M2.1's 0.28 min
ROW_LANE_PITCH_UM = 0.8  # (pitch - width) = 0.36 > M1.2a's 0.23 min
ROW_TRACK_PITCH_UM = 0.8  # (pitch - width) = 0.36 > M2.2a's 0.28 min
ROW_LANE_CLEARANCE_UM = 0.3  # innermost lane's outer edge to the gate pad's
# own left edge, before the half-pitch offset -- > M1.2a's 0.23 min
ROW_BAND_MARGIN_UM = 0.3  # pulldown row's top drawn comp edge to the first
# Metal2 track's centreline

# A gate pad's own left edge relative to its device's comp x0, derived from
# mosfet()'s own tab/pad construction (``gate_x0 = x0 - POLY_ENDCAP_UM``;
# ``tab_x1 = gate_x0 + GATE_TAB_OVERLAP_UM``; ``tab_x0 = tab_x1 -
# GATE_TAB_W_UM``; the Metal1 pad extends METAL1_PAD_MARGIN_UM further out)
# so lanes can be reserved to its left without re-deriving that geometry.
GATE_PAD_LEFT_UM = POLY_ENDCAP_UM + (GATE_TAB_W_UM - GATE_TAB_OVERLAP_UM) + METAL1_PAD_MARGIN_UM


@dataclass(frozen=True)
class Column:
    """One left-to-right slot of a :func:`build_row_cell` cell.

    ``pulldown`` is an all-``"nfet"`` branch and ``pullup`` an all-``"pfet"``
    branch, each ordered bottom-to-top and each a *series* sub-stack when it
    has more than one device (adjacent devices whose facing terminal nets
    match are wired directly, exactly as in :func:`build_stack_cell`). Either
    may be empty -- a column with only a pulldown branch (``nor2_3v3``'s
    second column) or only a pullup branch (``nand2_3v3``'s second column) is
    normal -- but not both.

    Both branches of a column are left-aligned at the same comp ``x0``, and
    the lanes reserved in that column's left margin are shared by both
    branches' gates (see the module's "ROUTING MODEL" note).
    """

    pulldown: tuple[Device, ...] = ()
    pullup: tuple[Device, ...] = ()


@dataclass
class _PlacedColumn:
    column: Column
    x0: float
    pulldown: list[MosfetPorts]
    pullup: list[MosfetPorts]
    lanes: dict[tuple[str, int], float]
    right: float


def _branch_ports(placed: _PlacedColumn, network: str) -> list[MosfetPorts]:
    return placed.pulldown if network == "pulldown" else placed.pullup


def _branch_devices(placed: _PlacedColumn, network: str) -> tuple[Device, ...]:
    return placed.column.pulldown if network == "pulldown" else placed.column.pullup


def _h_strap(canvas: Canvas, x_a: float, x_b: float, y_center: float) -> None:
    half = ROW_STRAP_W_UM / 2.0
    canvas.rect("metal1", min(x_a, x_b), y_center - half, max(x_a, x_b), y_center + half)


def _v_strap(canvas: Canvas, x_center: float, y_a: float, y_b: float) -> None:
    half = ROW_STRAP_W_UM / 2.0
    canvas.rect("metal1", x_center - half, min(y_a, y_b), x_center + half, max(y_a, y_b))


def _via1(canvas: Canvas, x: float, y: float) -> None:
    """One via1 plus the Metal1/Metal2 enclosure it needs.

    Both enclosing shapes are exactly :data:`ROW_STRAP_W_UM` square, i.e.
    exactly the width of the strap and the track that meet here -- so the
    landing never widens either wire and no notch is created (see
    :data:`ROW_STRAP_W_UM`'s own comment).
    """
    half_v = VIA1_SIZE_UM / 2.0
    half_p = ROW_STRAP_W_UM / 2.0
    canvas.rect("via1", x - half_v, y - half_v, x + half_v, y + half_v)
    canvas.rect("metal1", x - half_p, y - half_p, x + half_p, y + half_p)
    canvas.rect("metal2", x - half_p, y - half_p, x + half_p, y + half_p)


def _pad_cx(pad: tuple[float, float, float, float]) -> float:
    return (pad[0] + pad[2]) / 2.0


def _terminal_role(network: str, dev_idx: int, branch_len: int, kind: str) -> str:
    """Classify one non-gate device terminal, per the module's "ROUTING MODEL".

    ``kind`` is ``"top"`` or ``"bottom"``. Raises ``NotImplementedError`` for
    an interior pad that is not part of a same-branch series connection --
    the caller has already consumed every series pair before this is reached,
    so anything left over here genuinely has nowhere to go.
    """
    if network == "pulldown":
        if kind == "top" and dev_idx == branch_len - 1:
            return "channel"
        if kind == "bottom" and dev_idx == 0:
            return "rail"
    else:
        if kind == "bottom" and dev_idx == 0:
            return "channel"
        if kind == "top" and dev_idx == branch_len - 1:
            return "rail"
    raise NotImplementedError(
        f"{network} device {dev_idx} of {branch_len}: its {kind} terminal is an interior "
        "pad with no same-branch series partner -- build_row_cell() cannot route it "
        "(see this module's ROUTING MODEL note)"
    )


def build_row_cell(
    top_name: str,
    columns: Sequence[Column],
    *,
    x0: float = 0.0,
    add_taps: bool = True,
) -> LeafCell:
    """Draw a static-CMOS gate with fan-in as a fixed-frame row cell.

    See this module's "ROW CELLS" section for the placement model
    (:class:`Column`), the Metal1-strap/Metal2-track routing model, and the
    fixed row-cell frame every cell drawn here shares.

    Net resolution, in order:

    1. Same-branch series pairs (adjacent devices in one branch whose facing
       terminal nets match) are wired directly with :func:`_connect_pads` and
       removed from consideration.
    2. Every remaining terminal is classified: gates are ``"gate"``, S/D pads
       are ``"channel"`` or ``"rail"`` per :func:`_terminal_role`.
    3. Nets whose remaining terminals are *all* ``"rail"`` become the cell's
       supply nets -- exactly one such net per row is required (the pulldown
       row's is ``VSS``-like, the pullup row's ``VDD``-like), each drawn as a
       full-cell-width Metal1 rail carrying that row's own well/substrate tap.
    4. Every other multi-terminal net gets its own Metal2 track in the
       inter-row channel, with one Metal1 strap + via1 per terminal.
    5. A net with exactly one remaining terminal is promoted to a labelled
       Metal1 pin on that pad, unchanged from :func:`build_stack_cell`.

    Every net -- supply, track-routed, or single-terminal -- is additionally
    labelled as a top-level pin. That is a deliberate superset of
    :func:`build_stack_cell`'s behaviour (which labels only 1-terminal nets):
    gf180mcu's LVS deck matches by topology rather than by port name, so the
    extra labels change no verdict, but they let #308/#309's composite
    assembly find each cell's ``A``/``B``/``C``/``Y``/``VDD``/``VSS`` pin
    locations from :attr:`LeafCell.pins` instead of re-deriving them.
    """
    if not columns:
        raise ValueError("build_row_cell() needs at least one column")
    for i, col in enumerate(columns):
        if not col.pulldown and not col.pullup:
            raise ValueError(f"column {i} has neither a pulldown nor a pullup branch")
        if any(d.kind != "nfet" for d in col.pulldown):
            raise ValueError(f"column {i}: every pulldown device must be an nfet")
        if any(d.kind != "pfet" for d in col.pullup):
            raise ValueError(f"column {i}: every pullup device must be a pfet")

    canvas = Canvas(top_name)

    # --- placement ---------------------------------------------------------
    placed: list[_PlacedColumn] = []
    cursor = x0
    for col in columns:
        n_pd, n_pu = len(col.pulldown), len(col.pullup)
        lane_reserve = GATE_PAD_LEFT_UM + ROW_LANE_CLEARANCE_UM + (n_pd + n_pu) * ROW_LANE_PITCH_UM
        bx0 = cursor + lane_reserve

        def _draw_branch(devices: Sequence[Device], y_base: float) -> list[MosfetPorts]:
            out: list[MosfetPorts] = []
            y = y_base
            for i, d in enumerate(devices):
                if i > 0:
                    y += COMP_GAP_UM
                p = mosfet(canvas, d, bx0, y)
                out.append(p)
                y = p.y3
            return out

        pd_ports = _draw_branch(col.pulldown, ROW_PD_Y0)
        pu_ports = _draw_branch(col.pullup, ROW_PU_Y0)

        # Lane x, innermost first. Pulldown lanes occupy indices
        # [0, n_pd), pullup lanes [n_pd, n_pd + n_pu) -- see the module's
        # "ROUTING MODEL" note for why the two sets can share one margin, and
        # why within each set the device *farthest* from the channel takes
        # the *outermost* lane.
        lanes: dict[tuple[str, int], float] = {}
        for i in range(n_pd):
            lanes[("pulldown", i)] = bx0 - GATE_PAD_LEFT_UM - ROW_LANE_CLEARANCE_UM - (
                (n_pd - 1 - i) + 0.5
            ) * ROW_LANE_PITCH_UM
        for j in range(n_pu):
            lanes[("pullup", j)] = bx0 - GATE_PAD_LEFT_UM - ROW_LANE_CLEARANCE_UM - (
                n_pd + j + 0.5
            ) * ROW_LANE_PITCH_UM

        right = max(
            max(p.x1, p.top_pad[2], p.bottom_pad[2]) for p in (pd_ports + pu_ports)
        )
        placed.append(
            _PlacedColumn(column=col, x0=bx0, pulldown=pd_ports, pullup=pu_ports, lanes=lanes, right=right)
        )
        cursor = right + COMP_GAP_UM

    pd_top = max((p.y3 for c in placed for p in c.pulldown), default=ROW_PD_Y0)
    pu_top = max((p.y3 for c in placed for p in c.pullup), default=ROW_PU_Y0)
    if pd_top + NWELL_TO_NMOS_GAP_UM > ROW_PU_Y0:
        raise ValueError(
            f"pulldown row tops out at {pd_top} um; ROW_PU_Y0={ROW_PU_Y0} leaves less than "
            f"NWELL_TO_NMOS_GAP_UM ({NWELL_TO_NMOS_GAP_UM}) of clearance"
        )
    if pu_top + TAP_GAP_UM > ROW_NTAP_Y0:
        raise ValueError(
            f"pullup row tops out at {pu_top} um; ROW_NTAP_Y0={ROW_NTAP_Y0} leaves less than "
            f"TAP_GAP_UM ({TAP_GAP_UM}) of clearance"
        )

    # --- pass 1: same-branch series connections ----------------------------
    consumed: set[tuple[int, str, int, str]] = set()
    for ci, c in enumerate(placed):
        for network in ("pulldown", "pullup"):
            devices = _branch_devices(c, network)
            ports = _branch_ports(c, network)
            for i in range(len(devices) - 1):
                if devices[i].top_net != devices[i + 1].bottom_net:
                    continue
                _connect_pads(canvas, ports[i].top_pad, ports[i + 1].bottom_pad)
                consumed.add((ci, network, i, "top"))
                consumed.add((ci, network, i + 1, "bottom"))

    # --- pass 2: collect + classify every remaining terminal ---------------
    @dataclass
    class _Term:
        net: str
        role: str  # "gate" | "channel" | "rail"
        network: str
        column: _PlacedColumn
        dev_idx: int
        pad: tuple[float, float, float, float]
        lane_x: float | None
        strap_x: float | None = None

    terms: dict[str, list[_Term]] = {}

    def _add(t: _Term) -> None:
        terms.setdefault(t.net, []).append(t)

    for ci, c in enumerate(placed):
        for network in ("pulldown", "pullup"):
            devices = _branch_devices(c, network)
            ports = _branch_ports(c, network)
            for i, (d, p) in enumerate(zip(devices, ports)):
                _add(
                    _Term(
                        net=d.gate_net, role="gate", network=network, column=c, dev_idx=i,
                        pad=p.gate_pad, lane_x=c.lanes[(network, i)],
                    )
                )
                for kind, pad, net in (("top", p.top_pad, d.top_net), ("bottom", p.bottom_pad, d.bottom_net)):
                    if (ci, network, i, kind) in consumed:
                        continue
                    role = _terminal_role(network, i, len(devices), kind)
                    _add(
                        _Term(
                            net=net, role=role, network=network, column=c, dev_idx=i,
                            pad=pad, lane_x=None,
                        )
                    )

    # --- pass 3: split nets into rail / track / single-pad -----------------
    rail_nets: dict[str, list[_Term]] = {}
    track_nets: dict[str, list[_Term]] = {}
    single_nets: dict[str, _Term] = {}
    for net, tlist in terms.items():
        roles = {t.role for t in tlist}
        if roles == {"rail"}:
            networks = {t.network for t in tlist}
            if len(networks) != 1:
                raise NotImplementedError(
                    f"net {net!r} is rail-facing in both rows -- build_row_cell() draws one "
                    "supply rail per row, so a net cannot be both"
                )
            rail_nets[net] = tlist
        elif "rail" in roles:
            raise NotImplementedError(
                f"net {net!r} mixes a rail-facing terminal with {sorted(roles - {'rail'})} "
                "terminals -- build_row_cell() routes a supply net on its rail only"
            )
        elif len(tlist) == 1:
            single_nets[net] = tlist[0]
        else:
            track_nets[net] = tlist

    pd_rails = [n for n, ts in rail_nets.items() if ts[0].network == "pulldown"]
    pu_rails = [n for n, ts in rail_nets.items() if ts[0].network == "pullup"]
    if len(pd_rails) != 1 or len(pu_rails) != 1:
        raise ValueError(
            "build_row_cell() needs exactly one rail-facing net per row "
            f"(got pulldown={sorted(pd_rails)}, pullup={sorted(pu_rails)})"
        )
    vss_net, vdd_net = pd_rails[0], pu_rails[0]

    pins: dict[str, tuple[float, float, float, float]] = {}

    # --- pass 4: Metal2 tracks in the inter-row channel --------------------
    # Track order is by net name, purely for determinism: with straps on
    # Metal1 and tracks on Metal2 a crossing is not a short, so no ordering
    # heuristic is needed (that requirement is exactly what the single-layer
    # attempt could not satisfy -- see the module's "ROUTING MODEL" note).
    track_y0 = pd_top + ROW_BAND_MARGIN_UM
    track_top = track_y0 + max(len(track_nets) - 1, 0) * ROW_TRACK_PITCH_UM + ROW_TRACK_W_UM / 2.0
    if track_top > ROW_PU_Y0 - ROW_BAND_MARGIN_UM:
        raise ValueError(
            f"{len(track_nets)} nets need routing tracks but the channel "
            f"({pd_top} .. {ROW_PU_Y0} um) only fits "
            f"{int((ROW_PU_Y0 - ROW_BAND_MARGIN_UM - track_y0) // ROW_TRACK_PITCH_UM) + 1}"
        )

    # A gate terminal's strap x is its own reserved lane. A channel
    # terminal's would naturally be its pad's x-centre, but two channel pads
    # in the *same* column (a pulldown branch's drain and the pullup branch
    # stacked above it, both on the output net) have centres only a fraction
    # of a micron apart whenever the two devices' widths differ -- close
    # enough for their two via1 squares to merge into one oversized shape,
    # which V1.1 (via1 is exactly 0.26 um square, min *and* max) reports.
    # Reproduced on nand2_3v3's first build as 2 V1.1 items, at Y's own
    # W=2u NMOS drain / W=2.5u PMOS drain pair. So channel straps are
    # spread onto a ROW_LANE_PITCH_UM grid, sliding along the pad they land
    # on -- every S/D pad in this family is at least 0.96 um wide, so there
    # is always room.
    used_xs: list[float] = []

    def _pick_strap_x(pad: tuple[float, float, float, float]) -> float:
        half_s = ROW_STRAP_W_UM / 2.0
        lo, hi = pad[0] + half_s, pad[2] - half_s
        cand = _pad_cx(pad)
        options = [cand]
        for k in range(1, 9):
            options += [cand + k * ROW_LANE_PITCH_UM, cand - k * ROW_LANE_PITCH_UM]
        for opt in options:
            if opt < lo - 1e-9 or opt > hi + 1e-9:
                continue
            if all(abs(opt - u) >= ROW_LANE_PITCH_UM - 1e-9 for u in used_xs):
                return _r(opt)
        raise ValueError(
            f"no free strap lane on pad {pad} -- widen the device or raise ROW_LANE_PITCH_UM"
        )

    for t in (t for net in sorted(track_nets) for t in track_nets[net]):
        if t.role == "gate":
            assert t.lane_x is not None
            t.strap_x = _r(t.lane_x)
        else:
            t.strap_x = _pick_strap_x(t.pad)
        used_xs.append(t.strap_x)

    for k, net in enumerate(sorted(track_nets)):
        track_y = _r(track_y0 + k * ROW_TRACK_PITCH_UM)
        xs: list[float] = []
        for t in track_nets[net]:
            assert t.strap_x is not None
            if t.role == "gate":
                # Jog from the lane across to (and fully over) the gate pad,
                # at the pad's own y-centre; then a vertical strap from that
                # y down/up to the track.
                cy = (t.pad[1] + t.pad[3]) / 2.0
                _h_strap(canvas, t.strap_x - ROW_STRAP_W_UM / 2.0, t.pad[2], cy)
                _v_strap(canvas, t.strap_x, cy, track_y)
            else:  # "channel"
                _v_strap(canvas, t.strap_x, min(t.pad[1], track_y), max(t.pad[3], track_y))
            _via1(canvas, t.strap_x, track_y)
            xs.append(t.strap_x)
        half = ROW_TRACK_W_UM / 2.0
        canvas.rect("metal2", min(xs) - half, track_y - half, max(xs) + half, track_y + half)
        label_pad = track_nets[net][0].pad
        canvas.pin(net, *label_pad)
        pins[net] = label_pad

    for net, t in single_nets.items():
        canvas.pin(net, *t.pad)
        pins[net] = t.pad

    # --- n-well ------------------------------------------------------------
    pfet_ports = [p for c in placed for p in c.pullup]
    nwell_box = None
    ntap_x0 = None
    if pfet_ports:
        ntap_x0 = min(p.x0 for p in pfet_ports)
        nwell_box = (
            min(p.x0 for p in pfet_ports) - NWELL_MARGIN_UM,
            ROW_PU_Y0 - NWELL_MARGIN_UM,
            max(p.x1 for p in pfet_ports) + NWELL_MARGIN_UM,
            ROW_CELL_Y1,
        )
        canvas.rect("nwell", *nwell_box)

    # --- footprint + rails -------------------------------------------------
    # The rails span the whole cell so two abutted cells' rails touch. Take
    # the cell's right edge from what has actually been drawn so far (every
    # implant/poly/n-well overhang included) rather than re-deriving each
    # overhang by hand.
    drawn = canvas.top.bbox()
    footprint_x1 = _r(drawn.right * canvas.dbu)
    footprint = (x0, ROW_CELL_Y0, footprint_x1, ROW_CELL_Y1)

    half_rail = ROW_RAIL_H_UM / 2.0
    for net, rail_cy in ((vss_net, ROW_VSS_RAIL_CY), (vdd_net, ROW_VDD_RAIL_CY)):
        canvas.rect("metal1", x0, rail_cy - half_rail, footprint_x1, rail_cy + half_rail)
        for t in rail_nets[net]:
            cx = _pad_cx(t.pad)
            _v_strap(canvas, cx, min(t.pad[1], rail_cy), max(t.pad[3], rail_cy))

    if add_taps:
        # One tap per body type: every device of a given kind shares one
        # continuous well/substrate region regardless of column count, so one
        # tap per row suffices -- build_stack_cell()'s own convention. Each
        # tap sits directly under/over the first column's own devices, and
        # its Metal1 pad is exactly the rail's own band, so tap and rail
        # merge with no extra connector.
        well_tap(canvas, "p", placed[0].x0, ROW_PTAP_Y0, vss_net)
        if ntap_x0 is not None:
            well_tap(canvas, "n", ntap_x0, ROW_NTAP_Y0, vdd_net)

    for net, rail_cy in ((vss_net, ROW_VSS_RAIL_CY), (vdd_net, ROW_VDD_RAIL_CY)):
        pad = (x0, rail_cy - half_rail, footprint_x1, rail_cy + half_rail)
        pins[net] = pad
        if not add_taps:
            # well_tap() already labels the rail's net on its own pad; only
            # label it here when no tap was drawn, so the net never picks up
            # two labels (harmless under this deck, but noisy in the report).
            canvas.pin(net, *pad)

    ports = [p for c in placed for p in (c.pulldown + c.pullup)]
    return LeafCell(canvas=canvas, ports=ports, pins=pins, nwell_box=nwell_box, footprint=footprint)
