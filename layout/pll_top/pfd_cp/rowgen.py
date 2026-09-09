"""Row-style geometry primitives for multi-gate PFD/CP blocks (issue #300).

WHY THIS EXISTS ALONGSIDE ``devgen.py``
---------------------------------------
Part 1 of #294 (issue #299) landed ``devgen.py``: a *leaf-cell* generator
that draws an ordered device list as one left-aligned vertical column and
resolves 1- and 2-terminal nets automatically. That contract is exactly
right for a standalone ``pfdcp_inv_3v3`` and is what
``layout/evidence/pfdcp-inv-proof/`` proves DRC/LVS-clean. It does not
extend to Part 2's job -- a 47-instance, 108-transistor interconnected
block -- for two concrete, checkable reasons:

1. ``build_stack_cell()`` raises ``ValueError`` on any net with more than
   two device terminals, and ``pfdcp_nand2_3v3``'s output ``Y`` has three
   (``MP1``/``MP2`` drains + ``MN1`` drain -- see
   ``design/pfdcp_nand2_3v3.sch``). ``layout/tests/test_pfdcp_devgen.py``
   already asserts that raise. So the PFD's seven NAND2 instances cannot be
   drawn by it at all.
2. In ``devgen``'s vertical-current-flow convention a device's two S/D
   terminals sit at the *same* x (stacked in y). Any per-net vertical
   routing riser dropped on those pads would therefore land in the same x
   lane for two different nets. Routing 47 instances needs each net to own
   a distinct lane.

``devgen``'s own module docstring anticipates this ("A block that genuinely
needs a 2-D placement ... is out of this module's scope -- compose several
``build_stack_cell`` columns side by side and wire between them by hand").
This module is that composition layer for the PFD/CP block, and it keeps
``devgen`` untouched as the leaf-cell path.

LAYOUT CONVENTION: **current flows horizontally**, one standard-cell-style
row pair per band -- PMOS row above, NMOS row below, a routing band between
them, a ``VDD`` Metal1 rail above the PMOS row and a ``VSS`` Metal1 rail
below the NMOS row, each carrying the row's periodic well/substrate taps.
A device's ``w`` is its comp's vertical extent, ``l`` the horizontal extent
between its two S/D terminals. Every transistor is its own comp/poly/implant
island (no shared diffusion anywhere), wired only through Metal1 + contacts
-- the same island convention ``vco/primitives.py``,
``lock_detector/primitives.py`` and ``devgen.py`` all use, for the same
reason those modules give: it turns every internal node into an
independently DRC-safe Metal1 net instead of a shared-diffusion
width/enclosure transition.

The horizontal-flow ``mosfet()`` geometry below (and its per-rule margins)
is the one ``layout/pll_top/lock_detector/primitives.py`` already proved
DRC-clean on this PDK for a comparable digital block, restated here rather
than imported: each full-custom block in this repo owns its own generator
(``devgen.py``'s docstring states the same policy for the constants it
shares with ``vco/primitives.py``), and this module drops that module's
narrow-device "dog-bone" terminal path -- no PFD device is narrower than
``MIN_UNIFORM_TERM_W_UM`` -- while adding the rail/strap/track routing
model that module does not have.

ROUTING MODEL (three layers, no same-layer crossings by construction)
--------------------------------------------------------------------
* **Metal1** -- device pads, the two supply rails, and *vertical straps*:
  one per net per x lane, running from a pad into the routing band. A lane
  is the x of a device pad or gate-contact tab, so two different nets never
  share a lane (see ``pfd_cells.py``, which lays every cell out so this
  holds).
* **Metal2** -- *horizontal* buses inside the routing band, one segment per
  net, on a track assigned by ``pack_tracks()``. Two nets on the same track
  are kept apart in x by ``TRACK_CLEARANCE_UM``; nets on different tracks
  are kept apart in y by ``METAL2_TRACK_PITCH_UM``.
* **Metal3** -- *vertical* links only, used where a net has to cross a whole
  row pair (the PFD needs six: ``NRST``, ``RB``, and two ``VDD``/``VSS``
  row-to-row stitches). A Metal3 link crossing an unrelated Metal1 rail or
  Metal2 bus is not a short and not a spacing violation -- different layers,
  no via between them.

Every numeric margin below is the gf180mcuD deck's own minimum plus explicit
headroom; the citations are per-constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Iterable, Sequence

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
# the same table devgen.py/vco primitives.py/lock_detector primitives.py use). ---
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
    # The *pin/label* purpose of Metal1 -- the datatype gf180mcu's own LVS
    # deck reads top-level net names from (``metal1_label = labels(34, 10)``
    # in layers_definitions.lvs). See devgen.py's LAYER comment.
    "metal1_label": (34, 10),
}

# --- Device margins (deck minimum + headroom). Identical values to
# lock_detector/primitives.py, which proved them clean on this deck. ---
SD_OVERHANG_UM = 1.0  # DF.6_LV=0.24 min; sized so the S/D Metal1 pad clears the
# gate's own contact-tab pad by >= M1.2a's 0.23 min with headroom
COMP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, between two transistors' comp islands
POLY_ENDCAP_UM = 0.3  # PL.4_LV=0.22 min
GATE_TAB_W_UM = 0.4
GATE_TAB_H_UM = 0.4
GATE_TAB_OVERLAP_UM = 0.05  # tab and gate bar share real area, not a bare edge
CONTACT_SIZE_UM = 0.22  # CO.1
CONTACT_PITCH_UM = 0.5  # 0.22 contact + 0.28 gap > CO.2a's 0.25 min
CONTACT_ROW_MARGIN_UM = 0.1  # inset from the terminal's outer comp edge
IMPLANT_MARGIN_UM = 0.3  # NP.5a/PP.5a=0.23, NP.5b/PP.5b=0.16 min
NWELL_MARGIN_UM = 0.5  # DF.4c_LV=0.43 min (PMOS comp -> nwell edge)
NWELL_TAP_MARGIN_UM = 0.3  # DF.4d_LV=0.12 min (ntap -> nwell edge)
NWELL_TO_SUBSTRATE_GAP_UM = 1.5  # DF.16_LV/DF.17_LV=0.43/0.12 min, nwell edge to outside comp
METAL1_PAD_MARGIN_UM = 0.12  # Metal1 pad grown around a contact row
METAL1_WIRE_WIDTH_UM = 0.44  # > M1.1's 0.23 min; >= 0.34 so the "narrow metal
# line" end-of-line via-overlap clauses (V1.3c/V1.4b/V2.4b) never apply; and
# exactly VIA_PAD_UM, so a via landing never widens the wire it sits on. A
# wider landing on a narrower strap leaves a concave notch between the
# landing's outer edge and the device pad below it, which M1.2a (min. metal1
# spacing, 0.23 um) reports as a space violation *inside a single net* --
# reproduced during bring-up as 44 M1.2a items, all at a strap/landing step.
TAP_STRIP_LEN_UM = 0.6  # >= NP.1/PP.1's 0.4 um implant-width floor
TAP_STRIP_H_UM = 0.5
TAP_TO_ROW_GAP_UM = 1.5  # tap comp to the nearest device comp of the opposite
# implant type: > 2*IMPLANT_MARGIN_UM, so the two implants never touch
# (NP.3/PP.3-class spacing, 0.16-0.43 um min) -- devgen.TAP_GAP_UM's citation

#: Below this device width a contact cannot sit inside the comp strip with
#: CONTACT_ROW_MARGIN_UM on both sides (CO.4). Every PFD device is 0.5 um or
#: wider, so this module -- unlike lock_detector/primitives.py -- has no
#: narrow-device path; ``mosfet()`` asserts instead.
MIN_UNIFORM_TERM_W_UM = CONTACT_SIZE_UM + 2 * CONTACT_ROW_MARGIN_UM

# --- Routing margins ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b; headroom on the enclosing metal pad
VIA_PAD_UM = VIA1_SIZE_UM + 2 * VIA_ENCLOSURE_UM  # 0.44 -- also every wire's width
METAL2_WIRE_WIDTH_UM = 0.44  # > M2.1's 0.28 min; = VIA_PAD_UM (see METAL1_WIRE_WIDTH_UM)
METAL3_WIRE_WIDTH_UM = 0.44  # > M3.1's 0.28 min; = VIA_PAD_UM (see METAL1_WIRE_WIDTH_UM)
METAL2_TRACK_PITCH_UM = 0.8  # (pitch - width) = 0.36 > M2.2a's 0.28 min
TRACK_CLEARANCE_UM = 0.8  # x gap between two nets sharing one track,
# measured lane to lane: (0.8 - 2*half-landing 0.22) = 0.36 > M2.2a's 0.28 min
STRAP_TO_TRACK_MARGIN_UM = 0.3  # a strap always overshoots its own via by this
# much, so the via's landing pad is never at the bare end of a wire

#: Vertical clearance kept between the routing band's outermost track and the
#: gate-contact-tab Metal1 pads that bound the band above and below.
BAND_MARGIN_UM = 0.3


def _r(v: float) -> float:
    return round(v, 6)


# ---------------------------------------------------------------------------
# Canvas: a pure-Python shape recorder. klayout.db is only touched by
# write_gds(), so every placement/routing/geometry check in this package
# (and layout/tests/test_pfd_layout.py) runs with no PV environment at all.
# ---------------------------------------------------------------------------


@dataclass
class Canvas:
    top_name: str
    dbu: float = 0.001
    shapes: list[tuple[str, float, float, float, float]] = field(default_factory=list)
    labels: list[tuple[str, str, float, float]] = field(default_factory=list)

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        if layer not in LAYER:
            raise KeyError(f"unknown layer {layer!r}")
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        self.shapes.append((layer, _r(x0), _r(y0), _r(x1), _r(y1)))

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        self.labels.append((layer, text, _r(x), _r(y)))

    def bbox(self) -> tuple[float, float, float, float]:
        return (
            min(s[1] for s in self.shapes),
            min(s[2] for s in self.shapes),
            max(s[3] for s in self.shapes),
            max(s[4] for s in self.shapes),
        )

    def write_gds(self, path) -> None:
        import klayout.db as db  # noqa: PLC0415

        layout = db.Layout()
        layout.dbu = self.dbu
        per_um = int(round(1.0 / self.dbu))
        top = layout.create_cell(self.top_name)
        index = {name: layout.layer(*gds) for name, gds in LAYER.items()}

        def u(v: float) -> int:
            return int(round(v * per_um))

        for layer, x0, y0, x1, y1 in self.shapes:
            top.shapes(index[layer]).insert(db.Box(u(x0), u(y0), u(x1), u(y1)))
        for layer, text, x, y in self.labels:
            top.shapes(index[layer]).insert(db.Text(text, db.Trans(db.Vector(u(x), u(y)))))

        options = db.SaveLayoutOptions()
        options.select_cell(top.cell_index())
        options.format = "GDS2"
        layout.write(str(path), options)


@dataclass
class MirrorView:
    """A ``Canvas``-shaped proxy that reflects every shape about ``x = axis``.

    Drawing the DN chain through this proxy, from the *same* local
    coordinates the UP chain was drawn from, makes the two chains literal
    mirror images by construction rather than by careful arithmetic --
    ``layout/tests/test_pfd_layout.py`` then re-checks the property on the
    emitted geometry, so a later hand-placed shape cannot quietly break it.
    """

    canvas: Canvas
    axis: float

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        self.canvas.rect(layer, 2 * self.axis - x1, y0, 2 * self.axis - x0, y1)

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        self.canvas.label(layer, text, 2 * self.axis - x, y)


def mirror_x(axis: float, x: float) -> float:
    return _r(2 * axis - x)


# ---------------------------------------------------------------------------
# Device geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fet:
    """One ``nfet_03v3``/``pfet_03v3`` instance in a row.

    ``left``/``right`` name the nets on the two S/D terminals by their
    physical side (the device is symmetric; which one the schematic calls
    source is not a geometry property).
    """

    name: str
    kind: str  # "nfet" | "pfet"
    w_um: float
    l_um: float
    g: str
    left: str
    right: str


@dataclass(frozen=True)
class MosfetPorts:
    name: str
    kind: str
    left_pad: tuple[float, float, float, float]
    right_pad: tuple[float, float, float, float]
    gate_pad: tuple[float, float, float, float]
    comp_bbox: tuple[float, float, float, float]


def device_width_um(l_um: float) -> float:
    """Total x extent of one drawn device (comp left edge to comp right edge)."""
    return 2 * SD_OVERHANG_UM + l_um


def left_pad_cx(x0: float) -> float:
    return _r(x0 + CONTACT_ROW_MARGIN_UM + CONTACT_SIZE_UM / 2.0)


def right_pad_cx(x0: float, l_um: float) -> float:
    return _r(x0 + device_width_um(l_um) - CONTACT_ROW_MARGIN_UM - CONTACT_SIZE_UM / 2.0)


def gate_cx(x0: float, l_um: float) -> float:
    return _r(x0 + SD_OVERHANG_UM + l_um / 2.0)


def gate_pad_reach(w_um: float) -> float:
    """Distance from the row centerline to the outer edge of a gate tab pad."""
    return _r(w_um / 2.0 + POLY_ENDCAP_UM - GATE_TAB_OVERLAP_UM + GATE_TAB_H_UM + METAL1_PAD_MARGIN_UM)


def sd_pad_reach(w_um: float) -> float:
    """Distance from the row centerline to the outer edge of an S/D Metal1 pad."""
    return _r(w_um / 2.0 + METAL1_PAD_MARGIN_UM)


# Left-edge x (or y) positions for a row of contacts spanning [lo, hi] --
# shared with every other ``layout/pll_top/*`` submodule (issue #332,
# ``_canvas._contact_positions()``).
_contact_positions = partial(
    _canvas._contact_positions,
    size_um=CONTACT_SIZE_UM,
    pitch_um=CONTACT_PITCH_UM,
    margin_um=CONTACT_ROW_MARGIN_UM,
)


def mosfet(view, fet: Fet, x0: float, y_center: float, *, tab_up: bool) -> MosfetPorts:
    """Draw one horizontal-current-flow transistor.

    ``x0`` is the comp left edge, ``y_center`` the row centerline. ``tab_up``
    grows the gate's contact tab above the row (NMOS row, reaching up into
    the routing band) or below it (PMOS row, reaching down into the same
    band).
    """
    if fet.w_um <= MIN_UNIFORM_TERM_W_UM:
        raise ValueError(
            f"{fet.name}: w={fet.w_um} um is at or below the uniform-terminal floor "
            f"({MIN_UNIFORM_TERM_W_UM} um); this module has no dog-bone terminal path"
        )
    w, l = fet.w_um, fet.l_um
    implant_layer = "pplus" if fet.kind == "pfet" else "nplus"

    x1 = x0 + SD_OVERHANG_UM
    x2 = x1 + l
    x3 = x2 + SD_OVERHANG_UM
    y_lo = y_center - w / 2.0
    y_hi = y_center + w / 2.0

    # comp runs *under* the gate -- poly2 overlaps it, it is not a gap.
    view.rect("comp", x0, y_lo, x3, y_hi)

    gate_y0 = y_lo - POLY_ENDCAP_UM
    gate_y1 = y_hi + POLY_ENDCAP_UM
    view.rect("poly2", x1, gate_y0, x2, gate_y1)

    gx = (x1 + x2) / 2.0
    if tab_up:
        tab_y0 = gate_y1 - GATE_TAB_OVERLAP_UM
        tab_y1 = tab_y0 + GATE_TAB_H_UM
    else:
        tab_y1 = gate_y0 + GATE_TAB_OVERLAP_UM
        tab_y0 = tab_y1 - GATE_TAB_H_UM
    tab_x0 = gx - GATE_TAB_W_UM / 2.0
    tab_x1 = gx + GATE_TAB_W_UM / 2.0
    view.rect("poly2", tab_x0, tab_y0, tab_x1, tab_y1)

    cx = tab_x0 + (GATE_TAB_W_UM - CONTACT_SIZE_UM) / 2.0
    cy = tab_y0 + (GATE_TAB_H_UM - CONTACT_SIZE_UM) / 2.0
    view.rect("contact", cx, cy, cx + CONTACT_SIZE_UM, cy + CONTACT_SIZE_UM)
    gate_pad = (
        tab_x0 - METAL1_PAD_MARGIN_UM,
        tab_y0 - METAL1_PAD_MARGIN_UM,
        tab_x1 + METAL1_PAD_MARGIN_UM,
        tab_y1 + METAL1_PAD_MARGIN_UM,
    )
    view.rect("metal1", *gate_pad)

    def _terminal(x_outer: float, *, outer_is_min: bool) -> tuple[float, float, float, float]:
        ys = _contact_positions(y_lo, y_hi)
        if outer_is_min:
            cx0 = x_outer + CONTACT_ROW_MARGIN_UM
            cx1 = cx0 + CONTACT_SIZE_UM
        else:
            cx1 = x_outer - CONTACT_ROW_MARGIN_UM
            cx0 = cx1 - CONTACT_SIZE_UM
        for y in ys:
            view.rect("contact", cx0, y, cx1, y + CONTACT_SIZE_UM)
        pad = (
            cx0 - METAL1_PAD_MARGIN_UM,
            min(ys) - METAL1_PAD_MARGIN_UM,
            cx1 + METAL1_PAD_MARGIN_UM,
            max(ys) + CONTACT_SIZE_UM + METAL1_PAD_MARGIN_UM,
        )
        view.rect("metal1", *pad)
        return pad

    left_pad = _terminal(x0, outer_is_min=True)
    right_pad = _terminal(x3, outer_is_min=False)

    view.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y_lo - IMPLANT_MARGIN_UM,
        x3 + IMPLANT_MARGIN_UM,
        y_hi + IMPLANT_MARGIN_UM,
    )

    return MosfetPorts(
        name=fet.name,
        kind=fet.kind,
        left_pad=left_pad,
        right_pad=right_pad,
        gate_pad=gate_pad,
        comp_bbox=(x0, y_lo, x3, y_hi),
    )


def h_wire(view, x0: float, x1: float, y: float, width: float = METAL1_WIRE_WIDTH_UM) -> None:
    view.rect("metal1", x0, y - width / 2.0, x1, y + width / 2.0)


def v_wire(view, x: float, y0: float, y1: float, width: float = METAL1_WIRE_WIDTH_UM) -> None:
    view.rect("metal1", x - width / 2.0, y0, x + width / 2.0, y1)


def tap_strip(view, kind: str, x_center: float, y_center: float) -> tuple[float, float, float, float]:
    """A substrate (``'p'``) or n-well (``'n'``) tap: comp + implant + contacts + Metal1.

    Drawn on the row's own supply rail, so the tap's Metal1 pad merges into
    the rail it ties (same net) instead of needing its own connection.
    Returns the tap's comp bbox.
    """
    x0 = x_center - TAP_STRIP_LEN_UM / 2.0
    x1 = x_center + TAP_STRIP_LEN_UM / 2.0
    y0 = y_center - TAP_STRIP_H_UM / 2.0
    y1 = y_center + TAP_STRIP_H_UM / 2.0
    view.rect("comp", x0, y0, x1, y1)
    view.rect(
        "nplus" if kind == "n" else "pplus",
        x0 - IMPLANT_MARGIN_UM,
        y0 - IMPLANT_MARGIN_UM,
        x1 + IMPLANT_MARGIN_UM,
        y1 + IMPLANT_MARGIN_UM,
    )
    for cx in _contact_positions(x0, x1):
        cy = y_center - CONTACT_SIZE_UM / 2.0
        view.rect("contact", cx, cy, cx + CONTACT_SIZE_UM, cy + CONTACT_SIZE_UM)
    view.rect(
        "metal1",
        x0 - METAL1_PAD_MARGIN_UM,
        y0 - METAL1_PAD_MARGIN_UM,
        x1 + METAL1_PAD_MARGIN_UM,
        y1 + METAL1_PAD_MARGIN_UM,
    )
    return (x0, y0, x1, y1)


def nwell_over(view, boxes: Sequence[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """One nwell rectangle enclosing every PMOS comp / n-tap box, with margin.

    One well per row pair keeps the design free of NW.2a/NW.2b (min nwell
    space) by construction -- there is never a second nwell polygon close to
    the first within a row.
    """
    x0 = min(b[0] for b in boxes) - NWELL_MARGIN_UM
    y0 = min(b[1] for b in boxes) - NWELL_MARGIN_UM
    x1 = max(b[2] for b in boxes) + NWELL_MARGIN_UM
    y1 = max(b[3] for b in boxes) + NWELL_MARGIN_UM
    view.rect("nwell", x0, y0, x1, y1)
    return (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Vias / links
# ---------------------------------------------------------------------------


def via1_landing(view, x: float, y: float) -> None:
    """Metal1 <-> Metal2 via with both enclosing pads."""
    half_v = VIA1_SIZE_UM / 2.0
    half_p = half_v + VIA_ENCLOSURE_UM
    view.rect("via1", x - half_v, y - half_v, x + half_v, y + half_v)
    view.rect("metal1", x - half_p, y - half_p, x + half_p, y + half_p)
    view.rect("metal2", x - half_p, y - half_p, x + half_p, y + half_p)


def via2_landing(view, x: float, y: float) -> None:
    """Metal2 <-> Metal3 via with both enclosing pads."""
    half_v = VIA2_SIZE_UM / 2.0
    half_p = half_v + VIA_ENCLOSURE_UM
    view.rect("via2", x - half_v, y - half_v, x + half_v, y + half_v)
    view.rect("metal2", x - half_p, y - half_p, x + half_p, y + half_p)
    view.rect("metal3", x - half_p, y - half_p, x + half_p, y + half_p)


def m3_link(view, x: float, y_a: float, y_b: float) -> None:
    """A vertical Metal3 run between two Metal2 tracks at the same x.

    Used only for row-pair-to-row-pair crossings: Metal3 carries nothing else
    in this block, so such a link can cross any number of Metal1 rails and
    Metal2 buses without a via (different layers -- no connection, no short,
    no same-layer spacing check).
    """
    half = METAL3_WIRE_WIDTH_UM / 2.0
    view.rect("metal3", x - half, min(y_a, y_b), x + half, max(y_a, y_b))
    via2_landing(view, x, y_a)
    via2_landing(view, x, y_b)


# ---------------------------------------------------------------------------
# Track packing (pure)
# ---------------------------------------------------------------------------


def pack_tracks(
    intervals: Sequence[tuple[str, Sequence[tuple[float, float]]]],
    clearance: float = TRACK_CLEARANCE_UM,
) -> dict[str, int]:
    """Left-edge channel packing: assign each key the lowest conflict-free track.

    ``intervals`` is an ordered sequence of ``(key, [(x_lo, x_hi), ...])``.
    All of a key's x intervals land on one track, so a mirror-symmetric pair
    of nets can be packed as a single key and is guaranteed to share a track
    (which is what makes the UP and DN routing literal mirror images -- a
    horizontal bus is invariant under reflection about a vertical axis only
    if both halves sit at the same y).

    Deterministic: the input order is the tie-break, so the same placement
    always produces the same channel.
    """
    occupied: list[list[tuple[float, float]]] = []
    assignment: dict[str, int] = {}
    for key, spans in intervals:
        wanted = [(lo - clearance, hi + clearance) for lo, hi in spans]
        for track, used in enumerate(occupied):
            if all(w_hi <= u_lo or w_lo >= u_hi for w_lo, w_hi in wanted for u_lo, u_hi in used):
                used.extend(spans)
                assignment[key] = track
                break
        else:
            occupied.append(list(spans))
            assignment[key] = len(occupied) - 1
    return assignment


# ---------------------------------------------------------------------------
# Connectivity checks (pure) -- what a DRC deck structurally cannot do
# ---------------------------------------------------------------------------
#
# A DRC deck checks widths, spaces, enclosures and densities. It does not
# check *connectivity*, and the two failure modes below are both invisible to
# it:
#
#   * a short -- two different nets' shapes overlapping on one layer merge
#     into a single polygon that is perfectly legal by every geometric rule;
#   * an open -- a net drawn as two pieces that never touch is likewise
#     legal.
#
# Both are caught by LVS, but LVS needs an extracted netlist and a reference
# netlist. These two functions run on the plain-Python shape model instead,
# so every build of the block is checked for shorts and opens in the unit
# test suite with no PDK, no KLayout and no run_pv invocation.

#: Which two metal layers each via kind joins.
VIA_LAYERS = {"via1": ("metal1", "metal2"), "via2": ("metal2", "metal3")}

Conductor = tuple[str, str, float, float, float, float]  # (net, layer, x0, y0, x1, y1)
Via = tuple[str, str, float, float]  # (net, kind, x, y)

_TOUCH_EPS = 1e-6


def _boxes_touch(a: Conductor, b: Conductor) -> bool:
    return (
        a[4] >= b[2] - _TOUCH_EPS
        and b[4] >= a[2] - _TOUCH_EPS
        and a[5] >= b[3] - _TOUCH_EPS
        and b[5] >= a[3] - _TOUCH_EPS
    )


def shorted_pairs(conductors: Iterable[Conductor]) -> list[tuple[str, str, str]]:
    """Every ``(net_a, net_b, layer)`` where two different nets overlap."""
    items = sorted(conductors, key=lambda c: c[2])
    hits: list[tuple[str, str, str]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if b[2] >= a[4]:
                break
            if a[0] == b[0] or a[1] != b[1]:
                continue
            if a[4] > b[2] and b[4] > a[2] and a[5] > b[3] and b[5] > a[3]:
                hits.append((a[0], b[0], a[1]))
    return sorted(set(hits))


def disconnected_nets(
    conductors: Iterable[Conductor], vias: Iterable[Via]
) -> list[tuple[str, int]]:
    """Every ``(net, piece_count)`` whose shapes do not form one island.

    Two shapes on the same layer are connected when their boxes touch or
    overlap; a via connects a shape on its lower layer to one on its upper
    layer when both contain the via's centre.
    """
    items = list(conductors)
    parent = list(range(len(items)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_net: dict[str, list[int]] = {}
    for i, c in enumerate(items):
        by_net.setdefault(c[0], []).append(i)

    for idxs in by_net.values():
        ordered = sorted(idxs, key=lambda i: items[i][2])
        for n, i in enumerate(ordered):
            for j in ordered[n + 1 :]:
                if items[j][2] > items[i][4] + _TOUCH_EPS:
                    break
                if items[i][1] == items[j][1] and _boxes_touch(items[i], items[j]):
                    union(i, j)

    for net, kind, x, y in vias:
        lower, upper = VIA_LAYERS[kind]
        below = [i for i in by_net.get(net, []) if items[i][1] == lower and _contains(items[i], x, y)]
        above = [i for i in by_net.get(net, []) if items[i][1] == upper and _contains(items[i], x, y)]
        if not below or not above:
            raise ValueError(f"via {kind} for net {net!r} at ({x}, {y}) lands on no {lower}/{upper} shape")
        for i in below:
            for j in above:
                union(i, j)

    return sorted(
        (net, len({find(i) for i in idxs})) for net, idxs in by_net.items() if len({find(i) for i in idxs}) != 1
    )


def _contains(box: Conductor, x: float, y: float) -> bool:
    return box[2] - _TOUCH_EPS <= x <= box[4] + _TOUCH_EPS and box[3] - _TOUCH_EPS <= y <= box[5] + _TOUCH_EPS
