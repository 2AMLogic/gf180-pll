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
from typing import Sequence

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


def _r(v: float) -> float:
    return round(v, 6)


@dataclass
class Canvas:
    """A thin ``klayout.db`` layout/cell wrapper, float-micron coordinates in.

    ``klayout.db`` is imported lazily (inside ``__post_init__``), so any
    caller that only touches this module's pure-Python dataclasses
    (:class:`Device`) stays importable with no PV environment -- same
    convention as ``pfd_cp/devgen.py``/``vco/primitives.py``/
    ``layout/harness/cell.py``.
    """

    top_name: str
    dbu: float = 0.001

    def __post_init__(self) -> None:
        import klayout.db as db  # noqa: PLC0415

        self._db = db
        self.layout = db.Layout()
        self.layout.dbu = self.dbu
        self._dbu_per_um = int(round(1.0 / self.dbu))
        self.top = self.layout.create_cell(self.top_name)
        self._layer_index = {name: self.layout.layer(*gds) for name, gds in LAYER.items()}
        self.pins: dict[str, list[tuple[float, float, float, float]]] = {}

    def _u(self, v: float) -> int:
        return int(round(v * self._dbu_per_um))

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        box = self._db.Box(self._u(x0), self._u(y0), self._u(x1), self._u(y1))
        self.top.shapes(self._layer_index[layer]).insert(box)

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        self.top.shapes(self._layer_index[layer]).insert(
            self._db.Text(text, self._db.Trans(self._db.Vector(self._u(x), self._u(y))))
        )

    def pin(self, net: str, x0: float, y0: float, x1: float, y1: float) -> None:
        """Record + label a Metal1 pad as a top-level net pin.

        Labels on ``"metal1_label"`` (34/10), the purpose gf180mcu's own
        official LVS deck actually reads (see module docstring) -- *not*
        the drawing layer a purely-visual label would use.
        """
        self.pins.setdefault(net, []).append((_r(x0), _r(y0), _r(x1), _r(y1)))
        self.label("metal1_label", net, (x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def write_gds(self, path) -> None:
        options = self._db.SaveLayoutOptions()
        options.select_cell(self.top.cell_index())
        options.format = "GDS2"
        self.layout.write(str(path), options)


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


def _contact_positions(lo: float, hi: float) -> list[float]:
    usable_lo = lo + CONTACT_ROW_MARGIN_UM
    usable_hi = hi - CONTACT_ROW_MARGIN_UM
    span = usable_hi - usable_lo
    if span < CONTACT_SIZE_UM:
        center = (lo + hi) / 2.0
        return [center - CONTACT_SIZE_UM / 2.0]
    n = int((span - CONTACT_SIZE_UM) // CONTACT_PITCH_UM) + 1
    n = max(n, 1)
    total = CONTACT_SIZE_UM + (n - 1) * CONTACT_PITCH_UM
    start = usable_lo + (span - total) / 2.0
    return [start + i * CONTACT_PITCH_UM for i in range(n)]


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


def v_wire(canvas: Canvas, x: float, y0: float, y1: float, width: float = METAL1_WIRE_WIDTH_UM) -> tuple:
    x0, x1 = x - width / 2.0, x + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (x0, min(y0, y1), x1, max(y0, y1))


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


def _well_tap(canvas: Canvas, kind: str, x0: float, y0: float, net: str) -> tuple[float, float, float, float]:
    """A small square substrate/n-well tie: comp + implant + contact + Metal1 pad.

    ``kind='n'``: n-well tie (comp + ``nplus``), tied to the PMOS body net.
    ``kind='p'``: substrate tie (comp + ``pplus``), tied to the NMOS body net.
    Returns the drawn Metal1 pad, for the caller to wire to the rest of that
    net.
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
    ports: list[MosfetPorts] = []
    y_cursor = 0.0
    for i, d in enumerate(devices):
        if i > 0:
            gap = NWELL_TO_NMOS_GAP_UM if d.kind != devices[i - 1].kind else COMP_GAP_UM
            y_cursor += gap
        p = mosfet(canvas, d, x0, y_cursor)
        ports.append(p)
        y_cursor = p.y3

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
            tap_pad = _well_tap(canvas, "n", tap_x0, tap_y0, net)
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
            # _well_tap() already independently labels `net` on the tap's
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
            tap_pad = _well_tap(canvas, "p", tap_x0, tap_y0, net)
            if net == d_bot.bottom_net:
                _connect_pads(canvas, nfet_ports_bottom.bottom_pad, tap_pad)
            footprint_y0 = min(footprint_y0, tap_y0 - COMP_GAP_UM)

    footprint = (footprint_x0, footprint_y0, footprint_x1, footprint_y1)

    return LeafCell(canvas=canvas, ports=ports, pins=pins, nwell_box=nwell_box, footprint=footprint)
