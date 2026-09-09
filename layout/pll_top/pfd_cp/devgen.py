"""Reusable full-custom ``nfet_03v3``/``pfet_03v3`` leaf-cell generator for
the PFD/CP block family (issue #299, Part 1 of #294's device-layout
methodology proof).

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
``x0`` (so every device's gate-contact tab lands at the same x regardless of
its own ``w`` -- see :func:`mosfet`'s docstring), and it only resolves 1- and
2-terminal nets automatically. That is exactly the topology every gf180mcu
CMOS leaf cell in this family reduces to -- a static inverter (this issue's
own proof cell), a NAND2/NOR2 pull-up-pull-down pair, a transmission-gate
switch pair -- so Parts 2-4 of issue #294 (the PFD chain, the CP arrays, the
dump-buffer isolated well) can call this module directly instead of
re-deriving the wiring pattern below. A block that genuinely needs a 2-D
placement (more than one column) is out of this module's scope -- compose
several :func:`build_stack_cell` columns side by side and wire between them
by hand, the way ``layout/pll_top/vco/ring.py`` wires five
``vco/stage.py`` columns together.

WHY THIS IS DIRECT ``klayout.db`` GEOMETRY, NOT ``klt gen``/``klt gen-compose``
--------------------------------------------------------------------------
Issue #299 first tried the `klt gen mos_array` -> `klt gen-compose` round
trip its own acceptance criteria named as the primary path. Concretely, for
this design's own ``pfet_03v3`` (W=1.5 um/L=0.3 um) + ``nfet_03v3``
(W=0.5 um/L=0.3 um):

* ``klt gen mos_array`` (``rows=1 cols=1``, one call per device, each with
  ``gate_contact: true`` so the gate is metal and therefore routable) +
  ``klt gen-compose`` (``placement.strategy: "row"``, the second block's
  ``orientation: "mirror_x"`` so the two drains face each other -- exactly
  the worked "CMOS inverter" example ``docs/cli/gen-compose.md`` ships) DOES
  compose and route both the gate (``A``) and drain (``Y``) nets cleanly:
  exit 0, both nets ``status: "routed"``. The composed output also passes
  ``klt drc --deck gf180mcu`` (the curated, ~10-rule subset) clean.
* It does **not** pass gf180mcu's own foundry-authored signoff DRC deck --
  the same ``main`` table ``layout/run_pv.py drc`` runs. Even the single
  simplest possible ``mos_array`` request (one unit device, ``dummy: 0``, no
  ``gate_contact``) fails six real rule families on that deck (``DF.6_LV``
  comp/gate overhang, ``PL.4_LV`` poly endcap, ``PL.5a_LV``/``PL.5b_LV``
  field-poly spacing, ``CO.7`` contact-to-poly spacing, ``DF.12``
  comp/implant coverage), and the violation count scales with the number of
  unit devices drawn (27 items at ``mos_array``'s own default ``dummy: 1``,
  9 at ``dummy: 0`` -- a structural property of the generated geometry, not
  an edge effect of either setting). This is a genuine, reproduced
  capability gap, filed generically (no design details) at
  2AMLogic/klayout-tools#1575, with the exact reproduction and the six
  rules' real minimums quoted there.
* ``voltage_flavor="medium_voltage"`` does not help, and is not even the
  right marker for this design: ``nfet_03v3``/``pfet_03v3`` are gf180mcu's
  **``_LV``**-class 3.3 V devices with *no* ``Dualgate`` marker at all --
  confirmed directly against the PDK's own
  ``libs.tech/klayout/lvs/rule_decks/mos_extraction.lvs``
  (``extract_devices(mos4('pfet_03v3'), {'G' => pgate_3p3v, ...})``, and
  ``pgate_3p3v``/``ngate_3p3v`` are themselves derived with no ``dualgate``
  term in ``mos_derivations.lvs`` -- the identical citation
  ``layout/pll_top/vco/primitives.py``'s own module docstring already gives
  for this exact device class). Setting it draws the marker over a device
  the extraction flow does not expect one on, and additionally fails that
  marker's own (larger) ``_MV``-class version of the same six rule families.

So this module draws geometry the same way ``layout/pll_top/vco/primitives.py``
already does for the VCO ring (issue #293): directly against ``klayout.db``,
with margins read from, and exceeding, the PDK's own DRC deck minimums
(cited rule-by-rule below), generalized into a device-list-driven API.
Nothing here is opposed to using `klt gen`/`klt gen-compose` -- this module
would happily be replaced by a call into a fixed generator once
2AMLogic/klayout-tools#1575 is addressed.

MOSFET GEOMETRY CONVENTION
---------------------------
Identical to ``vco/primitives.py`` (deliberately -- this is a second,
independent leaf-cell family, not a fork of the VCO's own geometry, and
duplicating a handful of proven constants is cheaper than a shared-module
refactor this issue was not scoped to do): **current flows vertically**. A
device's ``w_um`` is its horizontal extent; ``l_um`` is its vertical extent
(the gate length). Every device is its own self-contained comp/poly/implant
island, wired to its neighbours only through Metal1 + contacts -- no shared
diffusion, even between two adjacent devices in the same stack.

WELL/SUBSTRATE TIES (why only the n-well gets one drawn here)
----------------------------------------------------------
Reading ``general_connections.lvs`` directly: gf180mcu's own official LVS
deck globally ties every NMOS body to the synthesized substrate net
(``connect_global(sub, substrate_name)``) regardless of whether a local
p-type tap is drawn nearby -- exactly what ``layout/README.md``'s "The
substrate-net gotcha" section already documents and what
``layout/run_pv.py lvs``'s ``--lvs-sub`` default (``VSS``) exists for. A
PMOS body's n-well (``nwell_con = nwell.not(res_mk)``) gets **no** such
global tie -- an n-well that touches no labelled/connected net extracts as
an anonymous internal node, which will not LVS-match a reference netlist
that (correctly) ties the PMOS bulk to ``VDD``. So this module always draws
one small n-well tap (comp + ``nplus`` + contact + Metal1, wired to the same
net as the top-of-stack PMOS device's own source pad) when the device list
contains a ``"pfet"``, and one small p-substrate tap (the same shape on
``pplus``, wired to the bottom-of-stack NMOS device's own source pad) when
it contains an ``"nfet"`` -- the latter is not required for LVS by the
citation above, but is drawn anyway for DRC hygiene (a real device is never
this close to *no* substrate tap in a real row) and because a caller
composing several :func:`build_stack_cell` outputs side by side may not
otherwise get one for free.
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

# --- GDS layers, gf180mcuD (confirmed against
# libs.tech/klayout/drc/rule_decks/layers_def.drc's get_polygons() calls --
# identical citation to vco/primitives.py's own LAYER table). ---
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
# identical to vco/primitives.py's own proven-DRC-clean constants; see that
# module's docstring/comments for the full per-rule derivation. Repeated
# (not imported) so this package does not depend on the VCO block's own
# module -- each full-custom leaf-cell family owns its own generator. ---
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
    convention as ``vco/primitives.py``/``layout/harness/cell.py``. This is
    the shared ``layout/pll_top/_canvas.Canvas`` (see issue #317) with this
    module's own ``LAYER`` table and ``pin()`` labelling on
    ``"metal1_label"`` (34/10) -- the *purpose* layer gf180mcu's own official
    LVS deck actually reads net names from (see module docstring), *not* the
    drawing layer a purely-visual label would use.
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
    """

    name: str
    kind: str  # "nfet" or "pfet"
    w_um: float
    l_um: float
    gate_net: str
    top_net: str
    bottom_net: str


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

    Identical geometry/margins to ``vco/primitives.py``'s ``mosfet()`` --
    see that function's docstring for the full per-shape DRC citation. ``x0``
    is the device's comp left edge; ``y_bottom`` is the bottom terminal
    comp's bottom edge.
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


def build_stack_cell(top_name: str, devices: Sequence[Device], *, x0: float = 0.0, add_taps: bool = True) -> LeafCell:
    """Draw ``devices`` as a single left-aligned vertical column.

    ``devices`` is ordered bottom-to-top. Adjacent devices of the same
    ``kind`` get :data:`COMP_GAP_UM` of clearance; a ``kind`` change (an
    n-well boundary) gets :data:`NWELL_TO_NMOS_GAP_UM`. Every net named by
    exactly one device terminal (across the whole list) is promoted to a
    top-level pin; every net named by exactly two is wired together with a
    straight Metal1 run (see :func:`_connect_pads`). A net named by zero or
    more than two terminals is a caller error (raises ``ValueError``) --
    this module's wiring is intentionally not a general router; see the
    module docstring for the supported topology.
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
    for net, pads in terminals.items():
        if len(pads) == 1:
            canvas.pin(net, *pads[0])
            pins[net] = pads[0]
        elif len(pads) == 2:
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

    if add_taps:
        pfet_ports_top = max(pfet_ports, key=lambda p: p.y3, default=None)
        nfet_ports_bottom = min((p for p in ports if p.kind == "nfet"), key=lambda p: p.y0, default=None)

        if pfet_ports_top is not None:
            net = next(d.top_net for d, p in zip(devices, ports) if p is pfet_ports_top)
            tap_x0 = pfet_ports_top.x0
            tap_y0 = pfet_ports_top.y3 + TAP_GAP_UM
            tap_pad = _well_tap(canvas, "n", tap_x0, tap_y0, net)
            _connect_pads(canvas, pfet_ports_top.top_pad, tap_pad)
            footprint_y1 = max(footprint_y1, tap_y0 + TAP_SIZE_UM + NWELL_MARGIN_UM)

        if nfet_ports_bottom is not None:
            net = next(d.bottom_net for d, p in zip(devices, ports) if p is nfet_ports_bottom)
            tap_x0 = nfet_ports_bottom.x0
            tap_y1 = nfet_ports_bottom.y0 - TAP_GAP_UM
            tap_y0 = tap_y1 - TAP_SIZE_UM
            tap_pad = _well_tap(canvas, "p", tap_x0, tap_y0, net)
            _connect_pads(canvas, nfet_ports_bottom.bottom_pad, tap_pad)
            footprint_y0 = min(footprint_y0, tap_y0 - COMP_GAP_UM)

    footprint = (footprint_x0, footprint_y0, footprint_x1, footprint_y1)

    return LeafCell(canvas=canvas, ports=ports, pins=pins, nwell_box=nwell_box, footprint=footprint)
