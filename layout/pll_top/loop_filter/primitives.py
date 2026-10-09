"""Device generators for the loop filter: MOS cap, MIM cap, plain poly resistor, tap strip.

None of these three device classes had a generator in this repository before
issue #748 (the VCO's ``poly_resistor()`` draws ``ppolyf_u_3k``, a different
device; the VCO's decap is a disclosed placeholder). Every structural choice
below is taken from the gf180mcuD PDK's *own* device generators,
``$PDK_ROOT/libs.tech/klayout/tech/pymacros/cells/``:

* ``draw_cap_mos.py`` (``cap_mos_inst``, ``type="cap_nmos_b"``) -- comp slab
  marked by ``mos_cap_mk``, a single poly gate across it, contact columns on
  the two comp strips beyond the gate, contact rows on the two poly ends,
  ``nplus`` over the comp, ``nwell`` around it;
* ``draw_cap_mim.py`` (``mim_option="MIM-A"``) -- ``FuseTop`` = Metal3 =
  ``wc x lc``, Metal2 bottom plate 0.6 um larger on every side, ``cap_mk`` =
  the bottom plate, a 0.1 um ``mim_l_mk`` strip on the top plate's bottom
  edge, a sea of Via2 on the top plate at 0.4 um enclosure / 0.5 um space;
* ``draw_res.py`` (``draw_ppolyf_res(res_type="ppolyf_u")`` ->
  ``polyf_res_inst``) -- ``res_mk`` = the resistor body, ``sab`` = the body
  widened 0.28 um across the current flow, ``poly2`` = the body plus a
  0.66 um contact land at each end, ``pplus`` over all of it at 0.3 um, and
  **no** ``(62, 0)`` "resistor" marker (that marker is what makes the
  high-Rs ``ppolyf_u_1k/2k/3k`` family -- ``res_derivations.lvs``:
  ``ppolyf_u_layer = pplus.and(poly2).and(sab).and(res_mk).not_interacting(resistor)``).

Deviations from those pcells are all *margin* (a contact land or a gap made
larger than the pcell's, never smaller), each named at its constant. The
generators draw vertical current flow, like ``vco/primitives.py``.

``klayout.db`` is imported lazily by :class:`Canvas`, so the constants and
the pure-Python placement helpers import without a PV environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import ClassVar

try:
    from .. import _canvas
except ImportError:  # layout/tests puts "pll_top" itself on sys.path (see vco/primitives.py)
    import _canvas
from . import devices as dev

#: GDS layers, gf180mcuD (``libs.tech/klayout/lvs/rule_decks/layers_definitions.lvs``).
LAYER: dict[str, tuple[int, int]] = {
    "comp": (22, 0),
    "nwell": (21, 0),
    "poly2": (30, 0),
    "nplus": (32, 0),
    "pplus": (31, 0),
    "contact": (33, 0),
    "metal1": (34, 0),
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
    "metal1_label": (34, 10),
    "metal2_label": (36, 10),
    "metal3_label": (42, 10),
    "sab": (49, 0),
    "res_mk": (110, 5),
    "mos_cap_mk": (166, 5),
    "fusetop": (75, 0),
    "cap_mk": (117, 5),
    "mim_l_mk": (117, 10),
}

#: Layers this block must never carry, with the reason (checked by the tests).
FORBIDDEN_LAYERS: dict[str, tuple[int, int]] = {
    # the high-Rs marker: would turn every ppolyf_u into ppolyf_u_1k/2k/3k
    "resistor": (62, 0),
    # the 5/6 V gate-oxide marker: would turn cap_nmos_03v3_b into cap_nmos_06v0_b
    "dualgate": (55, 0),
    # a boundary box standing in for a device (issue #748's own exclusion)
    "boundary": (0, 0),
}

# --- shared contact / via constants -----------------------------------------
CONTACT_UM = 0.22  # CO.1: min *and* max
CONTACT_PITCH_UM = 0.5  # CO.2a/CO.2b: 0.28 um space >= 0.25 (0.28 in a 4x4+ array)
CONTACT_ENC_UM = 0.1  # CO.3/CO.4 need 0.07 (poly/comp enclosure of contact)
M1_ENC_CONTACT_UM = 0.1  # metal1 grown around a contact row; keeps every pad >= 0.42 um,
# i.e. above CO.6a's 0.34 um end-of-line threshold
VIA_UM = 0.26  # V1.1 / V2.1: min *and* max
VIA_PITCH_UM = 0.7  # 0.44 um space >= V1.2b/V2.2b's 0.36 um 4x4-array rule
VIA_ENC_UM = 0.1  # V1.3a/V1.4a/V2.3b/V2.4a need 0.0 (0.04 avoids V*.3d); 0.1 is margin
METAL_PAD_UM = VIA_UM + 2 * VIA_ENC_UM  # 0.46 -- one via's landing square
IMPLANT_MARGIN_UM = 0.3  # NP.5b/PP.5b (0.16) and PRES.5 (0.3): implant grown around comp/poly

# --- tap strips --------------------------------------------------------------
TAP_WIDTH_UM = 1.2  # comp width of every substrate-tap band (>= DF.1a 0.22, PP.1 via margin)
TAP_M1_MARGIN_UM = 0.12

# --- cap_nmos_03v3_b ----------------------------------------------------------
MOSCAP_SD_EXT_UM = 0.6  # comp beyond the gate, each side. Pcell: 0.44 (0.36 land + 0.08).
# Holds one contact column at CONTACT_ENC_UM from the comp edge and leaves
# 0.6 - 0.1 - 0.22 = 0.28 um to the gate (CO.7 needs 0.15).
MOSCAP_POLY_EXT_UM = 0.62  # poly beyond the comp, each end. Pcell: 0.46.
# 0.30 to the contact (CO.8 needs 0.17), 0.22 contact, 0.10 poly enclosure (CO.3 0.07).
MOSCAP_POLY_CONTACT_GAP_UM = 0.30
MOSCAP_ROW_INSET_UM = 0.2  # gate-row metal1 starts this far inside the poly's x edge,
# keeping it 0.6 - 0.42 + 0.2 = 0.38 um from the diffusion column's metal1 (M1.2a 0.23)
MOSCAP_IMPLANT_MARGIN_UM = 0.25  # nplus around comp: NP.5a (gate overlap 0.23), NP.5b 0.16
MOSCAP_NWELL_ENC_UM = 0.6  # nwell around comp: DF.4d_LV needs 0.12; the pcell uses 0.16/0.23

# --- cap_mim_2f0_m2m3_noshield (MIM option A) -------------------------------------
MIM_BOTTOM_ENC_UM = 0.6  # MIM.3: bottom plate overlap of top plate, exactly the pcell's value
MIM_VIA_ENC_UM = 0.4  # MIM.4: FuseTop overlap of Via2 (pcell value; also MIM.2's 0.4)
MIM_VIA_SPACE_UM = 0.5  # MIM.9: via2 sea space (pcell value)
MIM_L_MK_UM = 0.1  # mim_l_mk strip height (pcell's l_mk_w)

# --- ppolyf_u (plain, unmarked) -------------------------------------------------
PRES_LAND_UM = 0.8  # poly2 contact land beyond res_mk at each end. Pcell: 0.66.
PRES_CONTACT_END_ENC_UM = 0.12  # contact inset from the poly end (CO.3 0.07)
PRES_SAB_EXT_UM = 0.28  # PRES.6: sab beyond the body across the current flow (pcell value)
PRES_IMPLANT_ENC_UM = 0.3  # PRES.5: pplus overlap of the resistor poly (pcell value)
PRES_CONTACT_EDGE_UM = 0.12  # contact inset from the resistor's long edges
# distance from a contact to the sab/res_mk boundary:
PRES_CONTACT_TO_SAB_UM = PRES_LAND_UM - PRES_CONTACT_END_ENC_UM - CONTACT_UM  # 0.46 (PRES.7: 0.22)

_r = _canvas._r


@dataclass
class Canvas(_canvas.Canvas):
    """The shared ``_canvas.Canvas``, with this module's layer table and grid snap."""

    LAYER: ClassVar[dict[str, tuple[int, int]]] = LAYER
    GRID_UM: ClassVar[float] = dev.LAYOUT_GRID_UM
    PIN_LAYER: ClassVar[str] = "metal1_label"


_contact_positions = partial(
    _canvas._contact_positions,
    size_um=CONTACT_UM,
    pitch_um=CONTACT_PITCH_UM,
    snap=dev.snap_um,
)


def via_positions(lo: float, hi: float, size: float, pitch: float, margin: float) -> list[float]:
    """Lower-left coordinates of a centred via/contact row spanning ``[lo, hi]`` with ``margin``."""
    return _canvas._contact_positions(lo, hi, size_um=size, pitch_um=pitch, margin_um=margin, snap=dev.snap_um)


def contact_grid(canvas: Canvas, x0: float, y0: float, x1: float, y1: float, margin: float) -> int:
    """Fill ``[x0,x1]x[y0,y1]`` with contacts ``margin`` inside its edges; returns the count."""
    xs = _contact_positions(x0, x1, margin_um=margin)
    ys = _contact_positions(y0, y1, margin_um=margin)
    for cx in xs:
        for cy in ys:
            canvas.rect("contact", cx, cy, cx + CONTACT_UM, cy + CONTACT_UM)
    return len(xs) * len(ys)


def via_grid(
    canvas: Canvas,
    layer: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    margin: float = VIA_ENC_UM,
    pitch: float = VIA_PITCH_UM,
) -> list[tuple[float, float]]:
    """Fill ``[x0,x1]x[y0,y1]`` with ``layer`` vias (``via1``/``via2``); returns their centres."""
    xs = via_positions(x0, x1, VIA_UM, pitch, margin)
    ys = via_positions(y0, y1, VIA_UM, pitch, margin)
    centres = []
    for vx in xs:
        for vy in ys:
            canvas.rect(layer, vx, vy, vx + VIA_UM, vy + VIA_UM)
            centres.append((_r(vx + VIA_UM / 2), _r(vy + VIA_UM / 2)))
    return centres


def tap_strip(canvas: Canvas, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    """One p-substrate tap band: comp + pplus + a full contact grid + metal1. Returns its metal1 box."""
    canvas.rect("comp", x0, y0, x1, y1)
    canvas.rect("pplus", x0 - IMPLANT_MARGIN_UM, y0 - IMPLANT_MARGIN_UM, x1 + IMPLANT_MARGIN_UM, y1 + IMPLANT_MARGIN_UM)
    contact_grid(canvas, x0, y0, x1, y1, CONTACT_ENC_UM)
    m1 = (x0 - TAP_M1_MARGIN_UM, y0 - TAP_M1_MARGIN_UM, x1 + TAP_M1_MARGIN_UM, y1 + TAP_M1_MARGIN_UM)
    canvas.rect("metal1", *m1)
    return m1


# ---------------------------------------------------------------------------
# cap_nmos_03v3_b
# ---------------------------------------------------------------------------


@dataclass
class MosCapPorts:
    name: str
    comp: tuple[float, float, float, float]
    gate: tuple[float, float, float, float]  # poly2 AND comp: the device's own W x L
    poly: tuple[float, float, float, float]
    nwell: tuple[float, float, float, float]
    gate_rows: tuple[tuple, tuple]  # (bottom, top) metal1 over the poly contact rows -> gate net
    body_cols: tuple[tuple, tuple]  # (left, right) metal1 over the diffusion contacts -> body net


def mos_cap_extent(cap: dev.MosCap) -> tuple[float, float]:
    """Pure-Python ``(comp width, comp height)`` of :func:`mos_cap` -- the gate's ``l`` runs along x."""
    return (cap.l_um + 2 * MOSCAP_SD_EXT_UM, cap.w_um)


def mos_cap(canvas: Canvas, cap: dev.MosCap, x0: float, y0: float) -> MosCapPorts:
    """Draw one ``cap_nmos_03v3_b`` with its comp's lower-left corner at ``(x0, y0)``.

    The device is the gate region, ``poly2 AND comp``: ``cap.l_um`` along x
    (between the two diffusion strips, as a transistor's L) by ``cap.w_um``
    along y. That region is what the LVS deck extracts (``cap_nmos_03v3_b =
    ngate_lv_base.and(nwell).interacting(mos_cap_mk)``) and what its area/
    perimeter parameters are measured on -- not the comp, the marker, or the
    well, which are all larger.

    The body is the n-well, contacted through the n+ diffusion strips on both
    sides of the gate (``ntap``); the gate is contacted through a poly
    contact row on each end. The two terminals' metal1 never meet: the gate
    rows sit between the diffusion columns in x, and the caller leaves them
    by Via1/Metal2 only.
    """
    cw, ch = mos_cap_extent(cap)
    x1, y1 = x0 + cw, y0 + ch
    comp = (x0, y0, x1, y1)
    canvas.rect("comp", *comp)
    canvas.rect("mos_cap_mk", *comp)
    m = MOSCAP_IMPLANT_MARGIN_UM
    canvas.rect("nplus", x0 - m, y0 - m, x1 + m, y1 + m)
    e = MOSCAP_NWELL_ENC_UM
    nwell = (x0 - e, y0 - e, x1 + e, y1 + e)
    canvas.rect("nwell", *nwell)

    gx0, gx1 = x0 + MOSCAP_SD_EXT_UM, x1 - MOSCAP_SD_EXT_UM
    poly = (gx0, y0 - MOSCAP_POLY_EXT_UM, gx1, y1 + MOSCAP_POLY_EXT_UM)
    canvas.rect("poly2", *poly)

    # --- diffusion (body) contact columns, one per side ---
    cols = []
    for cx0 in (x0 + CONTACT_ENC_UM, x1 - CONTACT_ENC_UM - CONTACT_UM):
        for cy in _contact_positions(y0, y1, margin_um=CONTACT_ENC_UM):
            canvas.rect("contact", cx0, cy, cx0 + CONTACT_UM, cy + CONTACT_UM)
        col = (cx0 - M1_ENC_CONTACT_UM, y0, cx0 + CONTACT_UM + M1_ENC_CONTACT_UM, y1)
        canvas.rect("metal1", *col)
        cols.append(col)

    # --- gate contact rows, one per poly end ---
    rows = []
    row_x0, row_x1 = gx0 + MOSCAP_ROW_INSET_UM, gx1 - MOSCAP_ROW_INSET_UM
    for cy0 in (
        y0 - MOSCAP_POLY_CONTACT_GAP_UM - CONTACT_UM,
        y1 + MOSCAP_POLY_CONTACT_GAP_UM,
    ):
        for cx in _contact_positions(row_x0, row_x1, margin_um=M1_ENC_CONTACT_UM):
            canvas.rect("contact", cx, cy0, cx + CONTACT_UM, cy0 + CONTACT_UM)
        row = (row_x0, cy0 - M1_ENC_CONTACT_UM, row_x1, cy0 + CONTACT_UM + M1_ENC_CONTACT_UM)
        canvas.rect("metal1", *row)
        rows.append(row)

    return MosCapPorts(
        name=cap.name,
        comp=comp,
        gate=(gx0, y0, gx1, y1),
        poly=poly,
        nwell=nwell,
        gate_rows=(rows[0], rows[1]),
        body_cols=(cols[0], cols[1]),
    )


# ---------------------------------------------------------------------------
# cap_mim_2f0_m2m3_noshield
# ---------------------------------------------------------------------------


@dataclass
class MimCapPorts:
    name: str
    fusetop: tuple[float, float, float, float]  # the device's own W x L (= Metal3 top plate)
    bottom_plate: tuple[float, float, float, float]  # Metal2 (= cap_mk)
    via2_count: int


def mim_cap(canvas: Canvas, cap: dev.MimCap, x0: float, y0: float) -> MimCapPorts:
    """Draw one MIM-A capacitor with its ``FuseTop`` lower-left corner at ``(x0, y0)``.

    Follows ``draw_cap_mim.py``'s MIM-A branch shape for shape. The two
    plates are electrically distinct *only* because the deck treats Via2
    inside ``FuseTop`` as landing on the top plate, not on the Metal2 below
    it (``general_derivations.lvs``: ``via2_cap = via2.and(fusetop)``). A
    metal-only extraction that ignores ``FuseTop`` sees every one of the
    top plate's vias land on the bottom plate and reports a short -- see
    ``netcheck.py``.
    """
    w, l = cap.w_um, cap.l_um
    ft = (x0, y0, x0 + w, y0 + l)
    canvas.rect("fusetop", *ft)
    canvas.rect("metal3", *ft)
    canvas.rect("mim_l_mk", x0, y0, x0 + w, y0 + MIM_L_MK_UM)
    e = MIM_BOTTOM_ENC_UM
    bottom = (x0 - e, y0 - e, x0 + w + e, y0 + l + e)
    canvas.rect("metal2", *bottom)
    canvas.rect("cap_mk", *bottom)
    vias = via_grid(
        canvas,
        "via2",
        *ft,
        margin=MIM_VIA_ENC_UM,
        pitch=VIA_UM + MIM_VIA_SPACE_UM,
    )
    return MimCapPorts(name=cap.name, fusetop=ft, bottom_plate=bottom, via2_count=len(vias))


# ---------------------------------------------------------------------------
# ppolyf_u
# ---------------------------------------------------------------------------


@dataclass
class PolyResPorts:
    name: str
    body: tuple[float, float, float, float]  # res_mk == the device's own W x L
    poly: tuple[float, float, float, float]
    bottom_pad: tuple[float, float, float, float]  # metal1
    top_pad: tuple[float, float, float, float]  # metal1


def poly_res_extent(res: dev.PolyRes) -> tuple[float, float]:
    """Pure-Python ``(poly width, poly height)`` of :func:`poly_res`."""
    return (res.w_um, res.l_um + 2 * PRES_LAND_UM)


def poly_res(canvas: Canvas, res: dev.PolyRes, x0: float, y0: float) -> PolyResPorts:
    """Draw one plain ``ppolyf_u`` with its body (``res_mk``) lower-left corner at ``(x0, y0)``.

    Current flows along y. Unlike ``vco/primitives.poly_resistor()``
    (``ppolyf_u_3k``) there is no ``(62, 0)`` marker, ``pplus`` covers the
    *whole* poly including the body (PRES.5 -- the implant is what makes this
    the 350 ohm/sq device), and ``sab`` ends flush with ``res_mk`` along the
    length, exactly as ``polyf_res_inst()`` draws it. ``res_mk`` is the
    ``W x L`` the LVS extractor measures.
    """
    w, l = res.w_um, res.l_um
    x1 = x0 + w
    body = (x0, y0, x1, y0 + l)
    canvas.rect("res_mk", *body)
    canvas.rect("sab", x0 - PRES_SAB_EXT_UM, y0, x1 + PRES_SAB_EXT_UM, y0 + l)
    poly = (x0, y0 - PRES_LAND_UM, x1, y0 + l + PRES_LAND_UM)
    canvas.rect("poly2", *poly)
    e = PRES_IMPLANT_ENC_UM
    canvas.rect("pplus", poly[0] - e, poly[1] - e, poly[2] + e, poly[3] + e)

    xs = _contact_positions(x0, x1, margin_um=PRES_CONTACT_EDGE_UM)
    pads = []
    for cy0 in (poly[1] + PRES_CONTACT_END_ENC_UM, poly[3] - PRES_CONTACT_END_ENC_UM - CONTACT_UM):
        for cx in xs:
            canvas.rect("contact", cx, cy0, cx + CONTACT_UM, cy0 + CONTACT_UM)
        pad = (x0, cy0 - M1_ENC_CONTACT_UM - 0.02, x1, cy0 + CONTACT_UM + M1_ENC_CONTACT_UM + 0.02)
        canvas.rect("metal1", *pad)
        pads.append(pad)
    return PolyResPorts(name=res.name, body=body, poly=poly, bottom_pad=pads[0], top_pad=pads[1])


def via1_stack(canvas: Canvas, x: float, y: float) -> tuple[float, float, float, float]:
    """One Via1 centred at ``(x, y)`` with metal1 + metal2 landing squares; returns the square."""
    x, y = dev.snap_um(x), dev.snap_um(y)
    h = VIA_UM / 2
    canvas.rect("via1", x - h, y - h, x + h, y + h)
    p = METAL_PAD_UM / 2
    sq = (x - p, y - p, x + p, y + p)
    canvas.rect("metal1", *sq)
    canvas.rect("metal2", *sq)
    return sq


#: Via pitch inside a :func:`metal1_to_metal3_stack` 2 x 2 cluster: 0.40 um
#: space (V1.2a/V2.2a 0.26), and under 0.6 um so the four Via2 merge into one
#: "location" for MT30.8 (``sized(0.3)``) when Metal3 is a thick top metal.
STACK_VIA_PITCH_UM = 0.66
#: Metal3 landing square of that stack: >= MT30.1a's 1.8 um thick-top-metal
#: width and >= MT30.6's 2.5 um end-of-line threshold, so the 0.25 um
#: end-of-line via enclosure never engages (MT30.5's 0.12 um still holds).
STACK_METAL3_UM = 2.6


def metal1_to_metal3_stack(canvas: Canvas, x: float, y: float) -> tuple[float, float, float, float]:
    """A 2 x 2 Via1 + 2 x 2 Via2 cluster centred at ``(x, y)``; returns the Metal3 square.

    2 x 2, not one via, because when Metal3 is the stack's thick top metal
    (gf180mcu variant A, ``metal_top=30K``) MT30.8 requires at least a 2 x 2
    array of top vias at every Metal3 connection.
    """
    x, y = dev.snap_um(x), dev.snap_um(y)
    span = STACK_VIA_PITCH_UM + VIA_UM
    lo_x, lo_y = x - span / 2, y - span / 2
    for layer in ("via1", "via2"):
        for i in range(2):
            for j in range(2):
                vx, vy = lo_x + i * STACK_VIA_PITCH_UM, lo_y + j * STACK_VIA_PITCH_UM
                canvas.rect(layer, vx, vy, vx + VIA_UM, vy + VIA_UM)
    p = span / 2 + VIA_ENC_UM
    canvas.rect("metal1", x - p, y - p, x + p, y + p)
    canvas.rect("metal2", x - p, y - p, x + p, y + p)
    h = STACK_METAL3_UM / 2
    sq = (x - h, y - h, x + h, y + h)
    canvas.rect("metal3", *sq)
    return sq
