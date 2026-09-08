"""KLayout geometry primitives for full-custom ``nfet_03v3``/``pfet_03v3`` layout.

Every numeric margin in this module is derived from the gf180mcuD open-PDK's
own KLayout DRC deck (``$PDK_ROOT/libs.tech/klayout/drc/rule_decks/*.drc``),
read directly rather than assumed, and always used with margin on top of the
deck's stated minimum:

* ``comp.drc`` / ``poly2.drc`` / ``contact.drc`` / ``nplus.drc`` /
  ``pplus.drc`` / ``nwell.drc`` / ``metal1.drc`` -- the FEOL/BEOL rules a
  full-custom ``nfet_03v3``/``pfet_03v3`` transistor is checked against.
* ``lvs/rule_decks/mos_extraction.lvs`` -- confirms which layer combination
  the deck's *own LVS* recognizes as ``nfet_03v3``/``pfet_03v3`` (the "_LV"
  rule class in the DRC deck's own naming: comp/poly *not* overlapping the
  ``dualgate``/``v5_xtor`` marker layers used by the 5V/6V device flavours).
  That is why this module never draws a ``dualgate`` shape -- adding one
  would silently turn every device into a different SPICE model.

Layout convention used throughout this package (see ``mosfet()``): **current
flows vertically**. A transistor's ``w`` (device width) is its *horizontal*
extent; its ``l`` (gate length) is its *vertical* extent. This is the
opposite of the row-of-standard-cells convention `layout/harness/cell.py`
draws (gates as vertical bars, current flowing left-to-right) -- chosen here
because ``vco_stage.sch``'s four devices (``MPH``-``MP``-``MN``-``MNT``) form
a literal top-to-bottom current-starved chain from ``VDD_VCO`` to
``GND_VCO`` (see ``devices.py``'s module docstring), so drawing them as a
vertical stack keeps the physical layout's shape legible against the
schematic it has to match for LVS.

Each transistor is its own self-contained comp/poly/implant island (no
shared diffusion between adjacent devices, even when the schematic stacks
them in series) connected to its neighbours only through Metal1 + contacts.
This costs some area against a "real" dense standard-cell stack, but every
electrical node this pass has to get right (``NH``, ``Y``, ``NT``, the
band-select mirror's future common-centroid legs) is a Metal1 net between
independently-DRC-safe islands rather than a shared-diffusion width
transition, which is the failure mode most likely to eat this issue's
worktree budget in DRC iteration. See ``ring.py``'s docstring for why that
trade was made explicit rather than silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

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
    # Second routing layer, used only by mirror.py: an interdigitated
    # common-centroid array has three nets (source bus, drain bus, two gate
    # buses) that all have to cross the array, which is provably not planar
    # in a single metal. via1/metal2's own rules are as simple as metal1's --
    # V1.1 (via exactly 0.26 um square), V1.2a (0.26 um space), V1.3a/V1.4a
    # (metal overlap of via >= 0), M2.1/M2.2a (0.28 um width/space), M2.3
    # (0.1444 um^2 area) -- read from the same deck as everything else in
    # this module (via1.drc, metal2.drc).
    "via1": (35, 0),
    "metal2": (36, 0),
    # DIEAREA -- no rule in this PDK's DRC deck references it (confirmed the
    # same way layout/floorplan/skeleton.py's own docstring documents: grep
    # against every rule_decks/*.drc file). Used only for the carried-forward
    # 22 pF decap placeholder -- see ring.py.
    "boundary": (0, 0),
}

# --- Derived generator margins (deck minimum + explicit headroom) ---
SD_OVERHANG_UM = 0.5  # DF.6_LV=0.24 min; also carries CO.7+contact+CO.4 (0.15+0.22+0.07=0.44)
COMP_GAP_UM = 0.6  # DF.3a_LV=0.28 min, between two separate transistors' comp islands
NWELL_TO_NMOS_GAP_UM = 4.0  # DF.16_LV=0.43 min, PMOS-band-to-NMOS-band clearance;
# sized generously because ring.py's inner n-well tap band (its own
# TAP_GAP_UM + TAP_RING_WIDTH_UM) has to fit inside this same gap, between
# the NMOS band and the n-well's own edge -- see ring.py's DRC-iteration
# notes for the arithmetic (2.0 um was DF.16_LV-legal for the transistors
# alone, but left ~0 clearance once the tap band's own footprint was added).
POLY_ENDCAP_UM = 0.65  # PL.4_LV=0.22 min; sized to also keep the gate contact's
# Metal1 pad M1.2a-legal (>= 0.23 um) away from the S/D pads' Metal1, not just
# to satisfy the poly rule itself (see mosfet()'s module-level DRC iteration
# notes -- a tighter endcap DRC-passes PL.4 alone but not M1.2a once the gate
# contact tab's own pad is added).
GATE_TAB_W_UM = 0.4
GATE_TAB_H_UM = 0.4
GATE_TAB_OVERLAP_UM = 0.05  # guarantees the tab and gate bar share real area, not a bare edge
CONTACT_SIZE_UM = dev.DRC_CONTACT_SIZE_UM
CONTACT_PITCH_UM = 0.5  # 0.22 contact + 0.28 pitch gap > CO.2a's 0.25 min
CONTACT_ROW_MARGIN_UM = 0.1  # inset from the terminal's outer comp edge
IMPLANT_MARGIN_UM = 0.3  # NP.5a/PP.5a=0.23, NP.5b/PP.5b=0.16 min
NWELL_MARGIN_UM = 0.5  # DF.4c_LV=0.43 min (PMOS comp -> nwell edge)
METAL1_PAD_MARGIN_UM = 0.12  # metal1 pad grown around a contact/contact-row
VIA1_SIZE_UM = dev.DRC_VIA1_SIZE_UM  # V1.1: min *and* max -- exactly 0.26 um
VIA1_METAL_ENCLOSE_UM = 0.09  # V1.3a/V1.4a need only >= 0; 0.09 also keeps the
# landing pad 0.26 + 2*0.09 = 0.44 um wide, i.e. >= V1.3c/V1.4b's 0.34 um
# threshold, so the deck's end-of-line-overlap special cases (which apply only
# to metal lines narrower than 0.34 um) never engage at all.
METAL2_WIRE_WIDTH_UM = 0.44  # >= M2.1's 0.28 min AND >= the 0.34 um V1.4b
# threshold, so every metal2 track is wide enough to land a via1 anywhere
# along it without a separately-grown pad.
METAL1_WIRE_WIDTH_UM = 0.28  # > M1.1's 0.23 min; also narrow enough that the
# VDD_VCO/GND_VCO and VBP/VBN rail pair (each stage's own S/D-to-gate
# spacing apart -- see stage.py) stay M1.2a-legal (>= 0.23 um) from each
# other once both are drawn full-width across the whole row (see ring.py's
# DRC-iteration notes -- 0.32 was 0.01 um short).


def _r(v: float) -> float:
    return round(v, 6)


@dataclass
class Canvas:
    """A thin ``klayout.db`` layout/cell wrapper, float-micron coordinates in.

    Mirrors ``layout/floorplan/skeleton.py``/``layout/harness/cell.py``'s own
    convention: ``klayout.db`` is imported lazily (inside ``__post_init__``),
    so anything in this package that only touches ``devices.py``'s constants
    stays importable with no PV environment.
    """

    top_name: str
    dbu: float = 0.001  # 1 nm/dbu, matches the PDK's stdcell GDS convention

    def __post_init__(self) -> None:
        import klayout.db as db  # noqa: PLC0415

        self._db = db
        self.layout = db.Layout()
        self.layout.dbu = self.dbu
        self._dbu_per_um = int(round(1.0 / self.dbu))
        self._grid_dbu = int(round(dev.LAYOUT_GRID_UM / self.dbu))
        self.top = self.layout.create_cell(self.top_name)
        self._layer_index = {name: self.layout.layer(*gds) for name, gds in LAYER.items()}
        self.pins: dict[str, list[tuple[float, float, float, float]]] = {}

    def _u(self, v: float) -> int:
        """Micron -> database units, snapped to the manufacturing grid.

        Snapping happens here rather than at each call site because *derived*
        coordinates -- a pad midpoint, a bus centreline, a device width
        divided by its finger count -- go off-grid routinely, and the PDK's
        own ``geom.drc`` OFFGRID section (``ongrid(0.005)`` per layer) fails
        every one of them. Snapping is a monotone function of the coordinate,
        so shapes that shared an exact edge before still share it after, and
        geometry that was already on-grid (the ring block, ``ring.py``) is
        unchanged.
        """
        return int(round(v * self._dbu_per_um / self._grid_dbu)) * self._grid_dbu

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

    def pin(self, net: str, x0: float, y0: float, x1: float, y1: float, layer: str = "metal1") -> None:
        """Record a Metal1 (or Metal2) landing pad as a named net pin."""
        self.pins.setdefault(net, []).append((_r(x0), _r(y0), _r(x1), _r(y1)))
        self.label(layer, net, (x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def write_gds(self, path) -> None:
        options = self._db.SaveLayoutOptions()
        options.select_cell(self.top.cell_index())
        options.format = "GDS2"
        self.layout.write(str(path), options)


def _contact_positions(lo: float, hi: float) -> list[float]:
    """Left-edge x (or y) positions for a row of contacts spanning [lo, hi].

    Snapped to the manufacturing grid at the *origin*, not left to
    ``Canvas._u`` -- ``CO.1`` makes 0.22 um the contact's min **and** max
    size, so an off-grid origin whose far edge rounds the other way is a
    0.215/0.225 um contact and a hard violation, not a cosmetic nudge.
    """
    usable_lo = lo + CONTACT_ROW_MARGIN_UM
    usable_hi = hi - CONTACT_ROW_MARGIN_UM
    span = usable_hi - usable_lo
    if span < CONTACT_SIZE_UM:
        center = (lo + hi) / 2.0
        return [dev.snap_um(center - CONTACT_SIZE_UM / 2.0)]
    n = int((span - CONTACT_SIZE_UM) // CONTACT_PITCH_UM) + 1
    n = max(n, 1)
    total = CONTACT_SIZE_UM + (n - 1) * CONTACT_PITCH_UM
    start = dev.snap_um(usable_lo + (span - total) / 2.0)
    return [dev.snap_um(start + i * CONTACT_PITCH_UM) for i in range(n)]


@dataclass
class MosfetPorts:
    """Metal1 landing pads + key coordinates for a drawn ``mosfet()`` instance."""

    name: str
    kind: str
    x0: float  # comp left edge (= column left edge, all four stage fets share this)
    x1: float  # comp right edge (= x0 + w)
    y0: float  # bottom terminal comp bottom edge
    y3: float  # top terminal comp top edge
    bottom_pad: tuple[float, float, float, float]
    top_pad: tuple[float, float, float, float]
    gate_pad: tuple[float, float, float, float]
    gate_y_center: float
    gate_tab_x1: float  # right edge of the gate contact tab (== gate bar's left endcap start)
    gate_tab_x_center: float = 0.0  # x of the gate contact tab's own centreline


def mosfet(
    canvas: Canvas,
    fet: dev.Fet,
    x0: float,
    y_bottom: float,
    *,
    w_um: float | None = None,
    sd_overhang: float | None = None,
) -> MosfetPorts:
    """Draw one vertical-current-flow ``nfet_03v3``/``pfet_03v3`` instance.

    ``x0`` is the transistor's comp left edge (column-left-aligned, so every
    stage fet's gate contact tab lands at the same x regardless of ``w`` --
    see the module docstring). ``y_bottom`` is the bottom terminal comp's
    bottom edge. Returns the Metal1 pad geometry the caller wires up.

    ``w_um`` overrides ``fet.w_um`` -- used to draw **one finger** of a
    multi-finger device (``fet.finger_w_um``); the caller is responsible for
    drawing ``fet.fingers`` of them and tying their pads together.

    ``sd_overhang`` overrides the module's default source/drain comp overhang.
    Widening it does not change the device (W and L are untouched) but moves
    the S/D contact rows further from the gate, which opens a Metal1 routing
    corridor beside the gate contact tab -- ``mirror.py`` needs exactly that
    to get two gate buses across a common-centroid array without shorting
    them to the array's own source/drain buses.
    """
    w = fet.w_um if w_um is None else w_um
    l = fet.l_um
    sd = SD_OVERHANG_UM if sd_overhang is None else sd_overhang
    comp_layer = "comp"
    implant_layer = "pplus" if fet.kind == "pfet" else "nplus"

    x1 = x0 + w

    y1 = y_bottom + sd  # bottom terminal comp top edge / gate bottom edge
    y2 = y1 + l  # gate top edge / top terminal comp bottom edge
    y3 = y2 + sd  # top terminal comp top edge

    # --- comp: ONE continuous active rectangle from the bottom terminal to
    # the top terminal -- the channel region (y1..y2, under the gate) has to
    # be real comp too, or the gate poly there is not "tgate" (poly-over-comp)
    # at all, just isolated field poly next to the S/D islands (which is
    # exactly the PL.5a/PL.5b violation this generator hit on its first DRC
    # pass -- see the module docstring's DRC-iteration note). ---
    canvas.rect(comp_layer, x0, y_bottom, x1, y3)

    # --- poly2 gate bar + contact tab ---
    gate_x0 = x0 - POLY_ENDCAP_UM
    gate_x1 = x1 + POLY_ENDCAP_UM
    canvas.rect("poly2", gate_x0, y1, gate_x1, y2)

    gate_y_center = (y1 + y2) / 2.0
    tab_x1 = gate_x0 + GATE_TAB_OVERLAP_UM
    tab_x0 = tab_x1 - GATE_TAB_W_UM
    tab_y0 = gate_y_center - GATE_TAB_H_UM / 2.0
    tab_y1 = gate_y_center + GATE_TAB_H_UM / 2.0
    canvas.rect("poly2", tab_x0, tab_y0, tab_x1, tab_y1)

    # Snapped for the same CO.1 min/max reason as _contact_positions().
    gate_contact_x0 = dev.snap_um(tab_x0 + (GATE_TAB_W_UM - CONTACT_SIZE_UM) / 2.0)
    gate_contact_y0 = dev.snap_um(tab_y0 + (GATE_TAB_H_UM - CONTACT_SIZE_UM) / 2.0)
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

    # --- S/D contacts: bottom terminal row hugs the outer (away-from-gate)
    # edge, so CO.7's 0.15 um contact-to-gate-poly space is satisfied by
    # SD_OVERHANG_UM (0.5) - CONTACT_ROW_MARGIN_UM (0.1) - CONTACT_SIZE_UM (0.22). ---
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

    # --- implant covers the whole comp footprint with margin (satisfies
    # NP.5a/PP.5a's gate enclosure and NP.5b/PP.5b's comp extension at once,
    # see devices.py's DRC_IMPLANT_* constants) ---
    canvas.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y_bottom - IMPLANT_MARGIN_UM,
        x1 + IMPLANT_MARGIN_UM,
        y3 + IMPLANT_MARGIN_UM,
    )

    return MosfetPorts(
        name=fet.name,
        kind=fet.kind,
        x0=x0,
        x1=x1,
        y0=y_bottom,
        y3=y3,
        bottom_pad=bottom_pad,
        top_pad=top_pad,
        gate_pad=gate_pad,
        gate_y_center=gate_y_center,
        gate_tab_x1=tab_x1,
        gate_tab_x_center=(tab_x0 + tab_x1) / 2.0,
    )


def h_wire(canvas: Canvas, x0: float, x1: float, y: float, width: float = METAL1_WIRE_WIDTH_UM) -> tuple:
    y0, y1 = y - width / 2.0, y + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (min(x0, x1), y0, max(x0, x1), y1)


def v_wire(canvas: Canvas, x: float, y0: float, y1: float, width: float = METAL1_WIRE_WIDTH_UM) -> tuple:
    x0, x1 = x - width / 2.0, x + width / 2.0
    canvas.rect("metal1", x0, y0, x1, y1)
    return (x0, min(y0, y1), x1, max(y0, y1))


def route_pads(canvas: Canvas, pad_a: tuple, pad_b: tuple, via_y: float) -> None:
    """Connect two Metal1 pads with an H-then-V-then-H dogleg through ``via_y``.

    Picks whichever edge of each pad (top or bottom) is nearer ``via_y`` as
    the stub's landing edge, so the route never doubles back through the
    pad itself.
    """
    ax = (pad_a[0] + pad_a[2]) / 2.0
    ay = pad_a[3] if via_y >= (pad_a[1] + pad_a[3]) / 2.0 else pad_a[1]
    bx = (pad_b[0] + pad_b[2]) / 2.0
    by = pad_b[3] if via_y >= (pad_b[1] + pad_b[3]) / 2.0 else pad_b[1]
    v_wire(canvas, ax, ay, via_y)
    v_wire(canvas, bx, via_y, by)
    # The H segment is drawn last and extended half a wire-width past each
    # vertical stub's centerline, so the two corners are a full-width
    # overlap rather than a half-width butt joint (a butt joint here is a
    # real M1.1/M1.2a-legal-width violation, not just a cosmetic notch --
    # see ring.py's DRC-iteration notes).
    half = METAL1_WIRE_WIDTH_UM / 2.0
    h_wire(canvas, min(ax, bx) - half, max(ax, bx) + half, via_y)


def m2_wire(canvas: Canvas, x0: float, x1: float, y: float, width: float = METAL2_WIRE_WIDTH_UM) -> tuple:
    """A horizontal Metal2 track centred on ``y``."""
    y0, y1 = y - width / 2.0, y + width / 2.0
    canvas.rect("metal2", min(x0, x1), y0, max(x0, x1), y1)
    return (min(x0, x1), y0, max(x0, x1), y1)


def via1_stack(canvas: Canvas, x: float, y: float) -> tuple:
    """One via1 at ``(x, y)`` with its own Metal1 and Metal2 landing pads.

    Both pads are ``VIA1_SIZE_UM + 2*VIA1_METAL_ENCLOSE_UM`` = 0.44 um square,
    which satisfies V1.3a/V1.4a (metal overlap of via1 >= 0) with real margin
    and stays at or above the 0.34 um width threshold below which the deck's
    V1.3c/V1.4b end-of-line-overlap rules would apply. Returns the pad box.
    """
    # V1.1 makes 0.26 um the via's min *and* max size, so the corner is
    # snapped explicitly -- same reasoning as _contact_positions()/CO.1.
    x, y = dev.snap_um(x), dev.snap_um(y)
    half_v = VIA1_SIZE_UM / 2.0  # 0.13 um -- itself a grid multiple
    canvas.rect("via1", x - half_v, y - half_v, x + half_v, y + half_v)
    half_p = half_v + VIA1_METAL_ENCLOSE_UM
    pad = (x - half_p, y - half_p, x + half_p, y + half_p)
    canvas.rect("metal1", *pad)
    canvas.rect("metal2", *pad)
    return pad


def bbox_union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def tap_strip(canvas: Canvas, kind: str, x0: float, y0: float, x1: float, y1: float, net: str) -> None:
    """A substrate (``kind='p'``) or n-well (``kind='n'``) tap strip.

    ``kind='p'``: pcomp + pplus, tied to the substrate/``GND_VCO`` net.
    ``kind='n'``: ncomp + nplus, tied to the local n-well/``VDD_VCO`` net.
    Both are simple rectangular comp + matching implant + a full contact row
    + a Metal1 pad, wide enough (>= NP.1/PP.1's 0.4 um) to be a legal implant
    shape on its own.
    """
    canvas.rect("comp", x0, y0, x1, y1)
    implant_layer = "nplus" if kind == "n" else "pplus"
    canvas.rect(
        implant_layer,
        x0 - IMPLANT_MARGIN_UM,
        y0 - IMPLANT_MARGIN_UM,
        x1 + IMPLANT_MARGIN_UM,
        y1 + IMPLANT_MARGIN_UM,
    )
    # Full 2-D contact grid, not just a single row -- a guard-ring band can be
    # long in *either* axis (a top/bottom band is wide-in-x, a left/right
    # band is tall-in-y), and both need a contact every <= CONTACT_PITCH_UM
    # along their long axis for a low-resistance, DRC-legal tie.
    xs = _contact_positions(x0, x1)
    ys = _contact_positions(y0, y1)
    for cx in xs:
        for cy in ys:
            canvas.rect("contact", cx, cy, cx + CONTACT_SIZE_UM, cy + CONTACT_SIZE_UM)
    canvas.rect(
        "metal1",
        x0 - METAL1_PAD_MARGIN_UM,
        y0 - METAL1_PAD_MARGIN_UM,
        x1 + METAL1_PAD_MARGIN_UM,
        y1 + METAL1_PAD_MARGIN_UM,
    )
    canvas.pin(net, x0, y0, x1, y1)


def guard_ring(
    canvas: Canvas,
    kind: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: float,
    net: str,
) -> None:
    """A closed rectangular tap ring (4 bands) around ``[x0,y0,x1,y1]``.

    ``kind='p'``: substrate ring (``GND_VCO``). ``kind='n'``: n-well tap ring
    (``VDD_VCO`` -- the caller is responsible for also drawing the ``nwell``
    shape this ring's ``ncomp`` sits inside; see ``ring.py``). The four bands
    are each a ``tap_strip()``, corner-overlapping (top/bottom bands span the
    full width, left/right bands fill only the gap between them), so the
    ring is one DRC-continuous shape per layer, not four islands that
    happen to touch.
    """
    tap_strip(canvas, kind, x0, y1 - width, x1, y1, net)  # top
    tap_strip(canvas, kind, x0, y0, x1, y0 + width, net)  # bottom
    tap_strip(canvas, kind, x0, y0 + width, x0 + width, y1 - width, net)  # left
    tap_strip(canvas, kind, x1 - width, y0 + width, x1, y1 - width, net)  # right
