"""KLayout geometry primitives for full-custom ``nfet_03v3``/``pfet_03v3`` layout.

Every numeric margin below is read directly from the gf180mcuD open-PDK's own
KLayout DRC deck (``$PDK_ROOT/libs.tech/klayout/drc/rule_decks/*.drc``), not
assumed, and always used with headroom on top of the deck's stated minimum:

* ``comp.drc`` (``DF.*``) -- COMP width/space/extension-beyond-gate/nwell
  enclosure.
* ``poly2.drc`` (``PL.*``) -- gate length, poly endcap beyond COMP, poly
  field spacing.
* ``contact.drc`` (``CO.*``) -- contact size, spacing, poly/COMP/metal1
  enclosure, contact-to-gate clearance.
* ``nplus.drc`` / ``pplus.drc`` (``NP.*`` / ``PP.*``) -- implant gate overlap
  and COMP extension.
* ``nwell.drc`` (``NW.*``) -- nwell width and PMOS-comp enclosure.
* ``metal1.drc`` (``M1.*``) -- metal1 width/space/area.

Layout convention: **current flows horizontally.** A transistor's gate is a
*vertical* poly bar; ``w`` (device width) is the comp's *vertical* extent,
``l`` (gate length) is the comp's *horizontal* extent between the two S/D
terminals. This matches ``layout/harness/cell.py``'s row-of-standard-cells
convention (gates as vertical bars, current left-to-right), which is the
natural fit here since every custom cell in this package (``inv_3v3``,
``nand2_3v3``, ``schmitt_3v3``) is drawn as one or two horizontal
PMOS-row-over-NMOS-row gates, not a vertical current-steering stack.

Each transistor is its own self-contained comp/poly/implant island (no
shared diffusion between adjacent devices, even where the schematic chains
them in series/parallel -- e.g. ``nand2_3v3``'s NMOS stack or
``schmitt_3v3``'s ``P1``/``N1`` nodes) connected to its neighbours only
through Metal1 + contacts. This costs area against a dense shared-diffusion
standard-cell stack, but it turns every internal node into an
independently-DRC-safe Metal1 net instead of a shared-diffusion width/
enclosure transition -- the failure mode most likely to burn this issue's
worktree budget in DRC iteration for a first full-custom cell library with
no prior art in this repository to check against.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import ClassVar, Iterable

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention (see
    # floorplan/skeleton.py and every layout/tests/test_*.py's own
    # sys.path.insert(..., ".../pll_top") -- "vco"/"lock_detector"/"pfd_cp"
    # are then each their own top-level package, one level short of "..").
    import _canvas
from . import devices as dev

# --- GDS layers, gf180mcuD (confirmed against
# libs.tech/klayout/drc/rule_decks/layers_def.drc's get_polygons() calls) ---
LAYER = {
    "comp": (22, 0),
    "poly2": (30, 0),
    "contact": (33, 0),
    "nplus": (32, 0),
    "pplus": (31, 0),
    "nwell": (21, 0),
    "metal1": (34, 0),
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

# --- Metal2/Metal3/Via routing margins, used only by route_net()'s per-net
# bus so that two unrelated nets can never risk a same-layer crossing/short:
#
#   Metal1 pad --(Via1)--> small Metal2 landing --(Via2)--> Metal3 "riser"
#   (runs the full vertical distance from the pad up/down to the net's own
#   track_y, on a layer nothing else in this package ever draws a long run
#   on) --(Via2)--> the net's own Metal2 "bus" (horizontal, spans only that
#   net's own pad x-range, at a track_y unique to that net).
#
# A Metal3 riser crossing an unrelated Metal2 bus (different layer, no via
# between them) is not a short and is not a spacing violation -- only same-
# layer proximity is checked. Two different nets' Metal2 buses can only
# collide if their track_y values are closer than METAL2_TRACK_PITCH_UM
# (with their x-ranges overlapping); track_y is assigned by NetTracks below,
# once per net, monotonically increasing by exactly that pitch, so this can
# never happen regardless of how wide any one net's bus runs. ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b min is ~0 um; headroom for the enclosing metal pad
METAL2_WIRE_WIDTH_UM = 0.34  # > M2.1's 0.28 min
METAL3_WIRE_WIDTH_UM = 0.34  # > M3.1's 0.28 min
METAL2_TRACK_PITCH_UM = 0.75  # (pitch - width) = 0.41 > M2.2a's 0.28 min, between two tracks

# --- Derived generator margins (deck minimum + explicit headroom) ---
SD_OVERHANG_UM = 1.0  # DF.6_LV=0.24 min; sized so the S/D Metal1 pad clears the
# gate's own Metal1 contact-tab pad by >= M1.2a's 0.23 min with headroom
# (also carries CO.7+contact+CO.4 = 0.15+0.22+0.07 = 0.44)
COMP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, between two separate transistors' comp islands
POLY_FIELD_GAP_UM = 0.5  # PL.3a/PL.5a/PL.5b=0.1-0.24 min, between unrelated poly shapes
POLY_ENDCAP_UM = 0.3  # PL.4_LV=0.22 min
GATE_TAB_W_UM = 0.4
GATE_TAB_H_UM = 0.4
GATE_TAB_OVERLAP_UM = 0.05  # guarantees the tab and gate bar share real area, not a bare edge
CONTACT_SIZE_UM = dev.DRC_CONTACT_SIZE_UM
CONTACT_PITCH_UM = 0.5  # 0.22 contact + 0.28 pitch gap > CO.2a's 0.25 min
CONTACT_ROW_MARGIN_UM = 0.1  # inset from the terminal's outer comp edge
IMPLANT_MARGIN_UM = 0.3  # NP.5a/PP.5a=0.23, NP.5b/PP.5b=0.16 min
NWELL_MARGIN_UM = 0.5  # DF.4c_LV=0.43 min (PMOS comp -> nwell edge)
NWELL_TAP_MARGIN_UM = 0.3  # DF.4d_LV=0.12 min (ntap -> nwell edge)
NWELL_TO_NWELL_GAP_UM = 1.6  # NW.2b_LV=1.4 min (unconnected); safe regardless of net merge
NWELL_TO_SUBSTRATE_GAP_UM = 1.0  # DF.16_LV/DF.17_LV=0.43/0.12 min, nwell edge to unrelated comp
METAL1_PAD_MARGIN_UM = 0.12  # metal1 pad grown around a contact/contact-row
METAL1_WIRE_WIDTH_UM = 0.32  # > M1.1's 0.23 min
METAL1_WIRE_GAP_UM = 0.4  # > M1.2a's 0.23 min, between independently-routed tracks
TAP_STRIP_LEN_UM = 0.6  # >= NP.1/PP.1's 0.4 um implant-width floor after margin removal


_r = _canvas._r


@dataclass
class Canvas(_canvas.Canvas):
    """A thin ``klayout.db`` layout/cell wrapper, float-micron coordinates in.

    Mirrors ``layout/floorplan/skeleton.py``/``layout/harness/cell.py``'s own
    convention: ``klayout.db`` is imported lazily (inside ``__post_init__``),
    so anything in this package that only touches ``devices.py``'s constants
    or this module's plain-Python placement math stays importable with no PV
    environment. This is the plain baseline of the shared
    ``layout/pll_top/_canvas.Canvas`` (see issue #317): no grid snapping, no
    pin-layer override -- just this module's own ``LAYER`` table.
    """

    LAYER: ClassVar[dict[str, tuple[int, int]]] = LAYER


# Left-edge (or bottom-edge) positions for a row of contacts spanning
# [lo, hi] -- shared with every other ``layout/pll_top/*`` submodule (issue
# #332, ``_canvas._contact_positions()``).
_contact_positions = partial(
    _canvas._contact_positions,
    size_um=CONTACT_SIZE_UM,
    pitch_um=CONTACT_PITCH_UM,
    margin_um=CONTACT_ROW_MARGIN_UM,
)


@dataclass
class MosfetPorts:
    """Metal1 landing pads + key coordinates for a drawn ``mosfet()`` instance."""

    name: str
    kind: str
    net_left: str
    net_right: str
    net_gate: str
    x0: float  # comp left edge (left terminal's outer edge)
    x3: float  # comp right edge (right terminal's outer edge)
    y_center: float
    w: float
    left_pad: tuple[float, float, float, float]
    right_pad: tuple[float, float, float, float]
    gate_pad: tuple[float, float, float, float]
    comp_bbox: tuple[float, float, float, float]


#: Below this device width, a S/D contact sized ``CONTACT_SIZE_UM`` cannot
#: sit inside a comp strip of height ``w`` with ``CONTACT_ROW_MARGIN_UM`` of
#: enclosure on both sides without the two enclosures colliding -- i.e. any
#: ``w`` at or below this literally cannot satisfy CO.4 (0.07 um min COMP
#: overlap of contact) using a uniform-height comp strip. ``MUPW``
#: (``lock_detector.sch``'s always-on weak pull-up, ``L=20u W=0.22u`` --
#: narrow-and-long by design, for a high channel resistance) is exactly at
#: this floor. See ``mosfet()``'s ``term_w`` parameter.
MIN_UNIFORM_TERM_W_UM = CONTACT_SIZE_UM + 2 * CONTACT_ROW_MARGIN_UM

#: Local S/D terminal comp height used whenever a device's own ``w`` is
#: below ``MIN_UNIFORM_TERM_W_UM`` -- matches ``tap_strip()``'s own strip
#: height for one consistent "minimum legal comp strip" constant across this
#: package.
NARROW_TERM_W_UM = 0.5

#: A widened terminal (``NARROW_TERM_W_UM`` above the gate-crossing comp
#: height) cannot start right at the gate edge (``x1``/``x2``): the gate
#: poly bar's own field-poly slivers (the part of the gate's poly2 outside
#: the *unwidened* channel comp, in the endcap band) would then sit flush
#: against (0 um from) the wider comp, violating PL.5a_LV/PL.5b_LV's 0.1 um
#: field-poly-to-comp minimum. This is the length of unwidened "shoulder"
#: comp, still at the gate's own channel height, kept between the gate edge
#: and where the terminal actually widens.
GATE_TERM_CLEARANCE_UM = 0.25


def mosfet(
    canvas: Canvas, fet: dev.Fet, x0: float, y_center: float, *, tab_up: bool = True
) -> MosfetPorts:
    """Draw one horizontal-current-flow ``nfet_03v3``/``pfet_03v3`` instance.

    ``x0`` is the transistor's comp left edge; ``y_center`` is the vertical
    centerline shared by every device in the same row. ``tab_up`` selects
    whether the gate's Metal1 contact tab is grown above or below the row
    (PMOS rows use ``tab_up=True`` to reach up toward a routing channel above
    them; NMOS rows use ``tab_up=False`` to reach down).

    Source lands on the left terminal, drain on the right -- an arbitrary but
    fixed convention (the device is symmetric; ``fet.d``/``fet.s`` only
    label which net a schematic terminal carries, not a physical side).

    When ``fet.w_um < MIN_UNIFORM_TERM_W_UM`` (only ``MUPW`` in this design,
    ``W=0.22u`` -- exactly ``CONTACT_SIZE_UM``, leaving zero room for CO.4's
    contact-enclosure margin at uniform height), each S/D terminal's comp is
    locally widened to ``NARROW_TERM_W_UM`` -- a standard "dog-bone" terminal
    pad -- while the gate-crossing comp segment (``x1`` to ``x2``, the only
    part of comp a device's poly2 gate actually overlaps) stays at the
    schematic's own ``w``, so the electrically-relevant channel width the PV
    LVS deck extracts is unchanged.
    """
    w, l = fet.w_um, fet.l_um
    comp_layer = "comp"
    implant_layer = "pplus" if fet.kind == "pfet" else "nplus"

    x1 = x0 + SD_OVERHANG_UM  # left terminal right edge / gate left edge
    x2 = x1 + l  # gate right edge / right terminal left edge
    x3 = x2 + SD_OVERHANG_UM  # right terminal right edge

    y_lo = y_center - w / 2.0
    y_hi = y_center + w / 2.0

    w_term = NARROW_TERM_W_UM if w < MIN_UNIFORM_TERM_W_UM else w
    y_lo_term = y_center - w_term / 2.0
    y_hi_term = y_center + w_term / 2.0

    # --- comp: a continuous active shape from x0 to x3. The channel is not
    # a gap in comp -- comp runs underneath the gate too; poly2 is drawn *on
    # top of* (overlapping) the middle of this same comp, not abutting a
    # break in it (tgate = poly2.and(comp) must have real area, not a
    # zero-width touch, or no channel is ever actually formed). For a normal
    # (``w >= MIN_UNIFORM_TERM_W_UM``) device this is one rectangle at
    # uniform height ``w``; for a narrow device it is five abutting
    # rectangles -- widened left/right terminal pads at ``w_term``, each
    # separated from the gate-crossing segment (still ``w``-tall, so the
    # electrical channel width is unchanged) by an unwidened
    # ``GATE_TERM_CLEARANCE_UM`` shoulder -- so the terminal's own S/D
    # contact gets CO.4's enclosure margin without the widened comp sitting
    # flush against the gate's own field-poly slivers (PL.5a_LV/PL.5b_LV). ---
    if w_term > w:
        shoulder_lo = x1 - GATE_TERM_CLEARANCE_UM
        shoulder_hi = x2 + GATE_TERM_CLEARANCE_UM
        canvas.rect(comp_layer, x0, y_lo_term, shoulder_lo, y_hi_term)
        canvas.rect(comp_layer, shoulder_lo, y_lo, x1, y_hi)
        canvas.rect(comp_layer, x1, y_lo, x2, y_hi)
        canvas.rect(comp_layer, x2, y_lo, shoulder_hi, y_hi)
        canvas.rect(comp_layer, shoulder_hi, y_lo_term, x3, y_hi_term)
    else:
        canvas.rect(comp_layer, x0, y_lo, x3, y_hi)

    # --- poly2 gate bar (vertical) ---
    gate_y0 = y_lo - POLY_ENDCAP_UM
    gate_y1 = y_hi + POLY_ENDCAP_UM
    canvas.rect("poly2", x1, gate_y0, x2, gate_y1)

    # --- gate contact tab: a field-poly square, offset in Y beyond the gate
    # bar's near edge, wide/tall enough (0.4 > 0.22 + 2*0.07) to enclose a
    # contact regardless of the gate's own L. ---
    gate_x_center = (x1 + x2) / 2.0
    if tab_up:
        tab_y0 = gate_y1 - GATE_TAB_OVERLAP_UM
        tab_y1 = tab_y0 + GATE_TAB_H_UM
    else:
        tab_y1 = gate_y0 + GATE_TAB_OVERLAP_UM
        tab_y0 = tab_y1 - GATE_TAB_H_UM
    tab_x0 = gate_x_center - GATE_TAB_W_UM / 2.0
    tab_x1 = gate_x_center + GATE_TAB_W_UM / 2.0
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

    # --- S/D contacts: each terminal's row hugs the outer (away-from-gate)
    # edge, so CO.7's 0.15 um contact-to-gate space is satisfied by
    # SD_OVERHANG_UM (0.55) - CONTACT_ROW_MARGIN_UM (0.1) - CONTACT_SIZE_UM (0.22). ---
    def _terminal_pad(x_outer_edge: float, *, outer_is_min: bool) -> tuple[float, float, float, float]:
        ys = _contact_positions(y_lo_term, y_hi_term)
        if outer_is_min:
            cx0 = x_outer_edge + CONTACT_ROW_MARGIN_UM
            cx1 = cx0 + CONTACT_SIZE_UM
        else:
            cx1 = x_outer_edge - CONTACT_ROW_MARGIN_UM
            cx0 = cx1 - CONTACT_SIZE_UM
        for cy in ys:
            canvas.rect("contact", cx0, cy, cx1, cy + CONTACT_SIZE_UM)
        pad_x0 = cx0 - METAL1_PAD_MARGIN_UM
        pad_x1 = cx1 + METAL1_PAD_MARGIN_UM
        pad_y0 = min(ys) - METAL1_PAD_MARGIN_UM
        pad_y1 = max(ys) + CONTACT_SIZE_UM + METAL1_PAD_MARGIN_UM
        canvas.rect("metal1", pad_x0, pad_y0, pad_x1, pad_y1)
        return (pad_x0, pad_y0, pad_x1, pad_y1)

    left_pad = _terminal_pad(x0, outer_is_min=True)
    right_pad = _terminal_pad(x3, outer_is_min=False)

    # --- implant covers the whole comp footprint (the wider of the channel
    # and the terminal pads) with margin (satisfies NP.5a/PP.5a's gate
    # enclosure and NP.5b/PP.5b's comp extension at once) ---
    canvas.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y_lo_term - IMPLANT_MARGIN_UM,
        x3 + IMPLANT_MARGIN_UM,
        y_hi_term + IMPLANT_MARGIN_UM,
    )

    return MosfetPorts(
        name=fet.name,
        kind=fet.kind,
        net_left=fet.s,
        net_right=fet.d,
        net_gate=fet.g,
        x0=x0,
        x3=x3,
        y_center=y_center,
        w=w,
        left_pad=left_pad,
        right_pad=right_pad,
        gate_pad=gate_pad,
        comp_bbox=(x0, y_lo_term, x3, y_hi_term),
    )


def h_wire(canvas: Canvas, x0: float, x1: float, y: float, width: float = METAL1_WIRE_WIDTH_UM) -> tuple:
    y0, y1 = y - width / 2.0, y + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (min(x0, x1), y0, max(x0, x1), y1)


def v_wire(canvas: Canvas, x: float, y0: float, y1: float, width: float = METAL1_WIRE_WIDTH_UM) -> tuple:
    x0, x1 = x - width / 2.0, x + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (x0, min(y0, y1), x1, max(y0, y1))


def pad_center(pad: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((pad[0] + pad[2]) / 2.0, (pad[1] + pad[3]) / 2.0)


# Smallest axis-aligned box enclosing every box given -- shared with every
# other ``layout/pll_top/*`` submodule (issue #332, ``_canvas.bbox_union()``).
bbox_union = _canvas.bbox_union


def tap_strip(canvas: Canvas, kind: str, x0: float, y_center: float, net: str, length: float = TAP_STRIP_LEN_UM):
    """A substrate (``kind='p'``) or n-well tap (``kind='n'``) strip.

    ``kind='p'``: PCOMP + PPLUS, tied to the substrate/``VSS`` net (drawn
    *outside* any nwell). ``kind='n'``: NCOMP + NPLUS, tied to the local
    n-well/``VDD`` net (drawn *inside* the nwell it taps). Both are a simple
    rectangular comp + matching implant + a contact row + a Metal1 pad, wide
    enough (>= NP.1/PP.1's 0.4 um) to be a legal implant shape on its own.
    Returns the comp bbox and the Metal1 pad.
    """
    x1 = x0 + length
    height = 0.5
    y0 = y_center - height / 2.0
    y1 = y_center + height / 2.0
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
    cy0 = y_center - CONTACT_SIZE_UM / 2.0
    for cx in xs:
        canvas.rect("contact", cx, cy0, cx + CONTACT_SIZE_UM, cy0 + CONTACT_SIZE_UM)
    pad = (
        x0 - METAL1_PAD_MARGIN_UM,
        y0 - METAL1_PAD_MARGIN_UM,
        x1 + METAL1_PAD_MARGIN_UM,
        y1 + METAL1_PAD_MARGIN_UM,
    )
    canvas.rect("metal1", *pad)
    canvas.pin(net, *pad)
    return (x0, y0, x1, y1), pad


# Draw one square via + a Metal1/2/3 riser landing it on a shared bus --
# shared with ``divider_chain/devgen.py`` (issue #332,
# ``_canvas._via_square()``/``_canvas._riser()``). ``pfd_cp/cp_dumpbuf.py``'s
# own ``_riser()`` is structurally different and is not part of this
# consolidation -- see that function's own docstring.
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
    pad_centers: Iterable[tuple[float, float]],
    track_y: float,
    width: float = METAL2_WIRE_WIDTH_UM,
) -> None:
    """Tie every ``pad_centers`` Metal1 landing point to one shared Metal2 bus.

    Every long-haul connection in this package's cells rides a dedicated
    Metal3 riser (see ``_riser()``) up/down to its own Metal2 bus at
    ``track_y`` -- never a same-layer Metal1 or Metal2 run spanning past a
    single pad -- so two unrelated nets can never risk a same-layer
    crossing/short regardless of placement order or how far apart their pads
    are. ``track_y`` must be unique per net (see ``NetTracks``); the bus
    itself only spans this net's own pad x-range, never the full design.

    Two of *this same net's* own pads landing within one riser-width of each
    other in X (e.g. a device's own S/D pad and a nearby periodic well/
    substrate tap -- see ``build.py``'s ``_finish()``) is not a short (same
    net), but each would still draw its own overlapping Via1/Via2 stack at
    ``track_y`` -- and two *overlapping-but-not-identical* squares merge
    into a polygon whose edges are no longer exactly the legal via size,
    which *is* a real V1.1/V2.1 violation. So close pads are snapped onto a
    single riser position first (grid = one riser pitch).
    """
    pad_centers = list(pad_centers)
    grid = METAL2_TRACK_PITCH_UM
    merged: dict[int, list[tuple[float, float]]] = {}
    for x, y in pad_centers:
        merged.setdefault(round(x / grid), []).append((x, y))
    riser_points = []
    for group in merged.values():
        gx = sum(p[0] for p in group) / len(group)
        gy = sum(p[1] for p in group) / len(group)
        riser_points.append((gx, gy))

    for x, y in riser_points:
        _riser(canvas, x, y, track_y)
    xs = [x for x, _ in pad_centers]
    x_lo, x_hi = min(xs), max(xs)
    if x_hi > x_lo:
        canvas.rect(
            "metal2",
            x_lo - width / 2.0,
            track_y - width / 2.0,
            x_hi + width / 2.0,
            track_y + width / 2.0,
        )
    canvas.label("metal2", net, (x_lo + x_hi) / 2.0, track_y)


class NetTracks:
    """Hands out a fresh, never-reused Metal2 track_y per net name.

    Because every track is unique (monotonically increasing by
    ``METAL2_TRACK_PITCH_UM``), two nets' buses can never be closer than the
    pitch on the Y axis -- eliminating same-layer Metal2 collisions between
    different nets by construction, independent of each net's Metal2 bus's
    X extent (see ``route_net``/``_riser``'s docstrings).
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


def nwell_over(canvas: Canvas, boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """Draw one nwell rectangle enclosing every PMOS comp/ntap box given, with margin."""
    x0, y0, x1, y1 = bbox_union(boxes)
    well = (
        x0 - NWELL_MARGIN_UM,
        y0 - NWELL_MARGIN_UM,
        x1 + NWELL_MARGIN_UM,
        y1 + NWELL_MARGIN_UM,
    )
    canvas.rect("nwell", *well)
    return well
