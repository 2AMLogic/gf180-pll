"""``cp_dumpbuf`` -- the charge pump's dump-node tracking buffer, Part 4 of
issue #294 (depends on Part 1, #299's ``devgen.py``).

``design/cp_dumpbuf.sch`` is two complementary 5-transistor OTAs in
unity-gain feedback on the shared ``VDUMP`` node (see that schematic's own
text annotation for the circuit rationale -- DR-005's tail-node-tracking
fix for the charge pump's dominant systematic error):

* ``MTN``/``MN1``/``MN2``/``MN3``/``MN4`` -- NMOS-input pair, PMOS mirror
  load. Not matching-critical (no isolated-well requirement).
* ``MTP``/``MP1``/``MP2``/``MP3``/``MP4`` -- PMOS-input pair, NMOS mirror
  load. ``MP1``/``MP2`` (the input pair, common source ``PSRC``) have their
  bulk tied to ``PSRC`` rather than ``VDD`` (see the schematic's own
  comment), which means they need their **own isolated n-well**, separate
  from every other n-well in this cell (and, per this issue's own
  Dependencies note, from the charge pump's own wide-swing cascode wells
  once Part 3, #301, lands) -- a different-potential n-well/n-well spacing
  requirement, not merely a device-to-device one.

WHY THIS ISN'T A ``devgen.build_stack_cell()`` CALL
----------------------------------------------------
``build_stack_cell()`` (issue #299) draws one left-aligned *vertical*
column and only resolves nets that appear on exactly one or two device
terminals in that column -- by design (see its own module docstring:
"deliberately narrower than a general place-and-route engine"). Two things
about this schematic don't fit that shape:

1. ``MP1``/``MP2`` need to be laid out **common-centroid** (this issue's
   own acceptance criterion) -- an interdigitated *row* of split fingers,
   not a column.
2. Several internal nets have **more than two** device terminals (counting
   only device terminals, before this module's own external pin pads are
   added -- see ``build()``): ``NSRC`` (``MTN`` top + ``MN1``/``MN2``
   bottom = 3), ``NDA`` (``MN1`` top + ``MN3`` gate + ``MN3`` top + ``MN4``
   gate = 4), ``PDA`` (``MP1a``/``MP1b`` top + ``MP3`` gate + ``MP3`` top +
   ``MP4`` gate = 5), ``PSRC`` (``MTPa``/``MTPb`` top + all 4 ``MP1``/
   ``MP2`` fingers' bottom = 6), and ``VDUMP`` (``MN2`` top+gate, ``MN4``
   top, ``MP4`` top, both ``MP2`` fingers' top+gate = 8, plus the external
   pin).

So, per ``devgen.py``'s own guidance ("out of this module's scope --
compose several ``build_stack_cell`` columns side by side and wire between
them by hand, the way ``ring.py`` wires five ``stage.py`` columns
together"), this module calls ``devgen.mosfet()``/``devgen.Device``/
``devgen.Canvas`` directly (the same primitives ``build_stack_cell()``
itself is built from) and does its own placement + wiring, rather than
extending ``build_stack_cell()`` into a general N-terminal router.

ROUTING: A DEDICATED METAL2/METAL3 RISER PER NET, NOT METAL1 T-JUNCTIONS
--------------------------------------------------------------------------
Every device in both OTAs shares one ``L=1u`` (so every device in a given
row has the exact same top/bottom Y band regardless of its own ``W``), and
this module places all 5 NMOS-OTA devices in one row and all 8 PMOS-OTA
devices (``MTPa``/``MTPb`` + 4 ``MP1``/``MP2`` fingers + ``MP3``/``MP4``) in
a second row above it. A same-layer (Metal1) T-junction between an N-terminal net's
several pads (e.g. ``NSRC``'s 3, or ``VDUMP``'s 6, some of which sit in the
row *below* and some in the row *above*) risks exactly the failure
``layout/pll_top/vco/mirror.py``'s own docstring names for its
interdigitated array: two unrelated nets' Metal1 runs crossing and merging
into one net by accident, or one net's own vertical run having to route
*through* a device it does not belong to.

This module sidesteps the planarity puzzle entirely by reusing
``layout/pll_top/lock_detector/primitives.py``'s own proven riser pattern
(issue #296, merged): every pad, regardless of which row it is in, rises
via a private Via1/Metal2/Via2 stack onto a dedicated **Metal3** vertical
run that free-crosses any unrelated geometry underneath it (different
layer, no via = no connection = no DRC spacing rule between Metal3 and
Comp/Poly2/Metal1), landing on that net's own **Metal2** bus at a track_y
that is unique per net (``NetTracks``, monotonically increasing by one
track pitch) -- so two different nets' buses can never collide regardless
of how many terminals either one has, and no manual crossing-order analysis
is needed. This is a second, independent implementation of the same
riser/track idea (not an import across block families -- see
``devgen.py``'s own "each full-custom leaf-cell family owns its own
generator" convention), using ``devgen.py``'s own DRC-proven Metal1/device
geometry underneath it. Via/Metal2/Metal3 sizes are the identical
gf180mcuD signoff-deck minimums (+ headroom) ``lock_detector/primitives.py``
already cites and proved DRC-clean (``V1.1``/``V2.1``/``M2.1``/``M3.1``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from . import devgen

TOP_CELL = "cp_dumpbuf"

# --- extra GDS layers this module needs beyond devgen.Canvas's own
# comp/poly2/contact/nplus/pplus/nwell/metal1 set -- confirmed against the
# same libs.tech/klayout/drc/rule_decks/layers_def.drc citation
# lock_detector/primitives.py's own LAYER table uses. ---
_EXTRA_LAYER = {
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

# --- Metal2/Metal3/Via routing margins -- identical values (and citation)
# to layout/pll_top/lock_detector/primitives.py's own riser constants. ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b min is ~0 um; headroom for the enclosing metal pad
METAL2_WIRE_WIDTH_UM = 0.34  # > M2.1's 0.28 min
METAL3_WIRE_WIDTH_UM = 0.34  # > M3.1's 0.28 min
METAL2_TRACK_PITCH_UM = 0.75  # (pitch - width) = 0.41 > M2.2a's 0.28 min, between two tracks

# --- Row/device placement margins (um). ---
DEVICE_GAP_UM = 2.0  # same-kind devices, same row -- clears each device's own
# gate-tab poly (extends ~1.0 um left of its comp) from its left neighbour's
# rightmost Metal1 S/D pad/poly with headroom (devgen's own COMP_GAP_UM=0.6
# is sized for *stacked*, not *side-by-side*, devices -- see module docstring)
ROW_HEIGHT_UM = 2.0 * devgen.SD_OVERHANG_UM + 1.0  # every device in this design is L=1u
WELL_GAP_UM = devgen.NWELL_TO_NMOS_GAP_UM  # standard n-well boundary within one row (reuse
# devgen's own DF.16_LV-derived clearance -- direction-agnostic, see its own comment)
ISO_WELL_GAP_UM = 8.0  # MP1/MP2's isolated (PSRC) well <-> the nearest *other* n-well
# (MTP's own VDD well) in the same row. Wells are inset NWELL_MARGIN_UM (0.5)
# within this device-to-device gap on each side, so the actual well-to-well
# clearance is 8.0 - 2*0.5 = 7.0 um -- 5x DIFFERENT_POTENTIAL_WELL_MIN_UM's
# 1.4 um NW.2b minimum (see that constant's own citation, below).
TAP_SIZE_UM = devgen.TAP_SIZE_UM
TAP_GAP_UM = 1.2  # device comp -> tap comp clearance, same row (> devgen's own
# TAP_GAP_UM used for a *stacked* tap; sized here for a *row-adjacent* one)

ROW_Y_N = 0.0
ROW_Y_P = 20.0  # generous separation: N-row's own top-of-well tap and P-row's
# own below-row tap both fit comfortably within this gap with room to spare,
# and it trivially clears every well-separation requirement between the two
# rows (Euclidean distance across a ~18 um gap is never the binding case here
# -- the binding case is the *same-row* MTP<->isolated-well pair ISO_WELL_GAP_UM
# governs).

#: Minimum spacing (um) between two n-well regions held at *different*
#: potentials -- gf180mcuD DRM 7.4 Nwell rule ``NW.2b`` ("Min. Nwell Space
#: (Outside DNWELL) [Different potential]", 3.3V column). Not invented here:
#: this is the same number 2AMLogic/klayout-tools's ``well_island`` generator
#: uses as its own ``separation_um`` default for exactly this "two groups of
#: same-flavour devices need two different body potentials" case (see that
#: generator's ``--list`` description and ``klayout_tools.gen`` module's
#: ``_PDK_WELL_ISOLATION_UM["gf180mcu"] = 1.4`` citation). Per this issue's
#: own Dependencies note, Part 3 (#301, the CP output-stage arrays) has not
#: landed as of this module's own build, so its wells cannot be checked
#: against real coordinates yet -- ``check_well_separation()`` below is the
#: general-purpose function that check will use once Part 3's geometry
#: exists (see ``layout/tests/test_cp_dumpbuf_layout.py`` for a synthetic
#: stand-in exercising it today).
DIFFERENT_POTENTIAL_WELL_MIN_UM = 1.4


def _rect_extra(canvas: devgen.Canvas, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
    """Draw a rectangle on one of this module's own extra layers (not one of
    ``devgen.Canvas``'s built-in named layers) directly against the
    underlying ``klayout.db`` objects ``devgen.Canvas`` already exposes
    (``.layout``, ``.top``) -- lazy-imports ``klayout.db`` itself, so this
    module stays importable with no PV environment, same convention as
    ``devgen.Canvas``.
    """
    import klayout.db as db  # noqa: PLC0415

    idx = canvas.layout.layer(*_EXTRA_LAYER[layer])
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    u = lambda v: int(round(v * 1000))  # noqa: E731 -- devgen.Canvas's own dbu=0.001 is fixed
    box = db.Box(u(x0), u(y0), u(x1), u(y1))
    canvas.top.shapes(idx).insert(box)


def _riser(canvas: devgen.Canvas, x: float, y_pad: float, track_y: float) -> None:
    """Metal1 pad -> Via1 -> Metal2 landing -> Via2 -> Metal3 riser -> Via2 ->
    Metal2 bus landing. See this module's own docstring ("ROUTING") for why;
    identical structure to ``lock_detector/primitives.py``'s own ``_riser()``.
    """
    half_v1 = VIA1_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM
    _rect_extra(canvas, "via1", x - VIA1_SIZE_UM / 2.0, y_pad - VIA1_SIZE_UM / 2.0, x + VIA1_SIZE_UM / 2.0, y_pad + VIA1_SIZE_UM / 2.0)
    _rect_extra(canvas, "metal2", x - half_v1, y_pad - half_v1, x + half_v1, y_pad + half_v1)

    half_v2 = VIA2_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM
    _rect_extra(canvas, "via2", x - VIA2_SIZE_UM / 2.0, y_pad - VIA2_SIZE_UM / 2.0, x + VIA2_SIZE_UM / 2.0, y_pad + VIA2_SIZE_UM / 2.0)
    _rect_extra(canvas, "metal3", x - half_v2, y_pad - half_v2, x + half_v2, y_pad + half_v2)

    half_w = METAL3_WIRE_WIDTH_UM / 2.0
    _rect_extra(canvas, "metal3", x - half_w, min(y_pad, track_y), x + half_w, max(y_pad, track_y))

    _rect_extra(canvas, "via2", x - VIA2_SIZE_UM / 2.0, track_y - VIA2_SIZE_UM / 2.0, x + VIA2_SIZE_UM / 2.0, track_y + VIA2_SIZE_UM / 2.0)
    _rect_extra(canvas, "metal3", x - half_v2, track_y - half_v2, x + half_v2, track_y + half_v2)
    _rect_extra(canvas, "metal2", x - half_v2, track_y - half_v2, x + half_v2, track_y + half_v2)


def _route_net(
    canvas: devgen.Canvas,
    net: str,
    pad_centers: Iterable[tuple[float, float]],
    track_y: float,
    width: float = METAL2_WIRE_WIDTH_UM,
) -> None:
    """Tie every ``pad_centers`` Metal1 landing point to one shared Metal2 bus
    at ``track_y`` via its own Metal3 riser -- see this module's docstring.
    Two of this same net's own pads within one riser-width of each other in
    X are snapped onto a single riser position first (grid = one riser
    pitch), same reasoning as ``lock_detector.primitives.route_net()``'s own
    docstring: two overlapping-but-not-identical via squares would merge
    into an illegal shape.
    """
    pad_centers = list(pad_centers)
    grid = METAL2_TRACK_PITCH_UM
    # Bucket by (x, a coarse y-band) -- x alone is not enough here: unlike
    # lock_detector's single-row cells, this module's pads span *two* rows
    # (Y_N and Y_P, ~20 um apart) plus a pin column, so two *different* rows'
    # pads can share a nearby X purely by coincidence. Averaging their (x, y)
    # into one fake riser point would land the via stack in the empty
    # channel between rows, on top of no Metal1 pad at all -- a real,
    # reproduced failure (V1.3a: "metal1 overlap of via1 >= 0") caught by
    # this module's own DRC pass before this fix. The row pitch (~20 um)
    # comfortably exceeds one grid cell, so bucketing y at a coarse 10 um
    # grid separates rows while still merging genuinely-adjacent same-row
    # pads (e.g. a device's own gate pad and a facing neighbour's S/D pad).
    y_grid = 10.0
    merged: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for x, y in pad_centers:
        merged.setdefault((round(x / grid), round(y / y_grid)), []).append((x, y))
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
        _rect_extra(canvas, "metal2", x_lo - width / 2.0, track_y - width / 2.0, x_hi + width / 2.0, track_y + width / 2.0)


class NetTracks:
    """Hands out a fresh, never-reused Metal2 track_y per net name -- see
    ``lock_detector.primitives.NetTracks``, whose docstring this class's
    behaviour is identical to.
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


def pad_center(pad: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((pad[0] + pad[2]) / 2.0, (pad[1] + pad[3]) / 2.0)


def bbox_union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def well_separation_um(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    """Euclidean clearance between two axis-aligned well boxes (0.0 if they
    touch or overlap). This is the general-purpose check both this module's
    own build (the isolated well vs. every other well *in this cell*) and
    the future integration increment (the isolated well vs. Part 3's real CP
    N/P array wells, once #301 lands) use.
    """
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    dx = max(bx0 - ax1, ax0 - bx1, 0.0)
    dy = max(by0 - ay1, ay0 - by1, 0.0)
    return (dx * dx + dy * dy) ** 0.5


def check_well_separation(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
    min_um: float = DIFFERENT_POTENTIAL_WELL_MIN_UM,
) -> float:
    """Raise unless ``box_a``/``box_b`` clear ``min_um`` (default: the gf180mcu
    different-potential n-well rule, see ``DIFFERENT_POTENTIAL_WELL_MIN_UM``).
    Returns the actual clearance on success.
    """
    gap = well_separation_um(box_a, box_b)
    if gap < min_um:
        raise ValueError(f"well separation {gap:.3f} um is below the required {min_um} um")
    return gap


def check_common_centroid(
    pattern: Sequence[str], x_centers: Sequence[float], tol_um: float = 1e-9
) -> None:
    """Raise unless every leg named in ``pattern`` has a finger-centroid that
    coincides with the array's own centre, and the pattern is genuinely
    interdigitated (not two same-leg blobs) -- the same two checks
    ``layout/pll_top/vco/mirror.py``'s own ``check_common_centroid()``
    performs, generalized from that module's fixed-width palindrome-pattern
    dataclass to a plain ``(pattern, x_centers)`` pair so this module does
    not need a copy of ``vco/devices.CascadePair``.
    """
    if len(pattern) != len(x_centers):
        raise ValueError(f"pattern has {len(pattern)} entries but x_centers has {len(x_centers)}")
    if not pattern:
        raise ValueError("check_common_centroid() needs at least one finger")
    centre = sum(x_centers) / len(x_centers)
    legs = sorted(set(pattern))
    for leg in legs:
        xs = [x for p, x in zip(pattern, x_centers) if p == leg]
        c = sum(xs) / len(xs)
        if abs(c - centre) > tol_um:
            raise ValueError(f"leg {leg!r} centroid {c:.6f} um != array centre {centre:.6f} um")
    runs = 1 + sum(1 for a, b in zip(pattern, pattern[1:]) if a != b)
    if runs < 3:
        raise ValueError(f"pattern {list(pattern)} is row-placed ({runs} runs), not interdigitated")


# --- device table -- design/cp_dumpbuf.sch's own instances, W/L only
# (nf=1, m=1 for every device). MP1/MP2 are each split into two half-width
# (24 um) fingers laid out ABBA (MP1a MP2a MP2b MP1b) for common-centroid
# matching -- total W (48 um) and device count are preserved; only the
# drawn finger count (nf, effectively) differs from the netlist's single
# nf=1 instance, the same recorded layout-vs-schematic difference
# ``vco/mirror.py``'s own "Cascade B" note documents for its own folded
# leg. ---
Device = devgen.Device

N_DEVICES: tuple[tuple[Device, float], ...] = (
    (Device(name="MTN", kind="nfet", w_um=16.0, l_um=1.0, gate_net="VBN", top_net="NSRC", bottom_net="VSS"), 0.0),
    (Device(name="MN1", kind="nfet", w_um=16.0, l_um=1.0, gate_net="VREF", top_net="NDA", bottom_net="NSRC"), DEVICE_GAP_UM),
    (Device(name="MN2", kind="nfet", w_um=16.0, l_um=1.0, gate_net="VDUMP", top_net="VDUMP", bottom_net="NSRC"), DEVICE_GAP_UM),
    (Device(name="MN3", kind="pfet", w_um=24.0, l_um=1.0, gate_net="NDA", top_net="NDA", bottom_net="VDD"), WELL_GAP_UM),
    (Device(name="MN4", kind="pfet", w_um=24.0, l_um=1.0, gate_net="NDA", top_net="VDUMP", bottom_net="VDD"), DEVICE_GAP_UM),
)

P_DEVICES: tuple[tuple[Device, float], ...] = (
    # MTP (schematic W=48u) is split into two 24 um fingers, same nets on
    # both -- purely a tap-pitch convenience (a lone 48 um-wide device is
    # itself wider than DF.13_LV's 20 um max-distance-to-tap span, so *no*
    # single tap placement could satisfy it; every other device in this
    # cell is already <=24 um). Not matching-critical (MTP is a tail current
    # source, not an input device), so no common-centroid requirement here
    # -- unlike MP1/MP2's split, which this module double-checks arithmetically.
    (Device(name="MTPa", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VBP", top_net="PSRC", bottom_net="VDD"), 0.0),
    (Device(name="MTPb", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VBP", top_net="PSRC", bottom_net="VDD"), DEVICE_GAP_UM),
    (Device(name="MP1a", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VREF", top_net="PDA", bottom_net="PSRC"), ISO_WELL_GAP_UM),
    (Device(name="MP2a", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VDUMP", top_net="VDUMP", bottom_net="PSRC"), DEVICE_GAP_UM),
    (Device(name="MP2b", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VDUMP", top_net="VDUMP", bottom_net="PSRC"), DEVICE_GAP_UM),
    (Device(name="MP1b", kind="pfet", w_um=24.0, l_um=1.0, gate_net="VREF", top_net="PDA", bottom_net="PSRC"), DEVICE_GAP_UM),
    (Device(name="MP3", kind="nfet", w_um=16.0, l_um=1.0, gate_net="PDA", top_net="PDA", bottom_net="VSS"), WELL_GAP_UM),
    (Device(name="MP4", kind="nfet", w_um=16.0, l_um=1.0, gate_net="PDA", top_net="VDUMP", bottom_net="VSS"), DEVICE_GAP_UM),
)

# The common-centroid pattern/order for MP1/MP2's 4 fingers, in P_DEVICES'
# own placement order (indices 1-4: MP1a MP2a MP2b MP1b).
MP12_PATTERN: tuple[str, ...] = ("A", "B", "B", "A")
MP12_NAMES: tuple[str, ...] = ("MP1a", "MP2a", "MP2b", "MP1b")

# External (schematic ipin/iopin) nets, per design/cp_dumpbuf.sch.
EXTERNAL_NETS: tuple[str, ...] = ("VREF", "VBN", "VBP", "VDUMP", "VDD", "VSS")

PIN_X_UM = -3.0
PIN_PITCH_UM = 1.5


def _place_row(canvas: devgen.Canvas, specs: Sequence[tuple[Device, float]], y_bottom: float) -> list:
    ports = []
    x_cursor = 0.0
    for i, (dev, gap) in enumerate(specs):
        if i > 0:
            x_cursor += gap
        p = devgen.mosfet(canvas, dev, x_cursor, y_bottom)
        ports.append(p)
        x_cursor = p.x1
    return ports


def _tap_strip(
    canvas: devgen.Canvas,
    kind: str,
    x0: float,
    x1: float,
    y_center: float,
    net: str,
    height: float = TAP_SIZE_UM,
    contact_pitch: float = 2.0,
) -> tuple[tuple, tuple]:
    """A substrate (``kind='p'``) or n-well tap (``kind='n'``) drawn as one
    long strip spanning ``[x0, x1]`` at a fixed Y, with a periodic row of
    contacts along its length -- not a single small square tap.

    gf180mcuD's ``DF.13_LV``/``DF.14_LV`` cap the distance from *any point*
    of a PMOS-in-nwell/NMOS-outside-nwell comp to its *nearest* tap at 20 um
    -- a hard ceiling a single tap at one end of a wide row (this module's
    isolated PMOS array alone spans over 100 um) cannot satisfy regardless
    of how the devices are gapped. A strip spanning the *entire* group's own
    X range, offset only a small, fixed amount in Y, keeps that distance
    equal to the Y offset (a couple of um) everywhere along the strip,
    independent of the group's total width -- reproduced directly: the
    single-small-tap version of this module failed ``DF.13_LV``/
    ``DF.14_LV`` (4 violations) on exactly the wide groups this fixes.
    """
    y0 = y_center - height / 2.0
    y1 = y_center + height / 2.0
    canvas.rect("comp", x0, y0, x1, y1)
    implant_layer = "nplus" if kind == "n" else "pplus"
    canvas.rect(
        implant_layer,
        x0 - devgen.IMPLANT_MARGIN_UM,
        y0 - devgen.IMPLANT_MARGIN_UM,
        x1 + devgen.IMPLANT_MARGIN_UM,
        y1 + devgen.IMPLANT_MARGIN_UM,
    )
    cy0 = y_center - devgen.CONTACT_SIZE_UM / 2.0
    cy1 = cy0 + devgen.CONTACT_SIZE_UM
    cx = x0 + devgen.CONTACT_ROW_MARGIN_UM
    placed = False
    while cx + devgen.CONTACT_SIZE_UM <= x1 - devgen.CONTACT_ROW_MARGIN_UM:
        canvas.rect("contact", cx, cy0, cx + devgen.CONTACT_SIZE_UM, cy1)
        placed = True
        cx += contact_pitch
    if not placed:
        cx = (x0 + x1) / 2.0 - devgen.CONTACT_SIZE_UM / 2.0
        canvas.rect("contact", cx, cy0, cx + devgen.CONTACT_SIZE_UM, cy1)
    pad = (
        x0 - devgen.METAL1_PAD_MARGIN_UM,
        y0 - devgen.METAL1_PAD_MARGIN_UM,
        x1 + devgen.METAL1_PAD_MARGIN_UM,
        y1 + devgen.METAL1_PAD_MARGIN_UM,
    )
    canvas.rect("metal1", *pad)
    return (x0, y0, x1, y1), pad


@dataclass
class DumpBufCell:
    canvas: devgen.Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, tuple[float, float, float, float]]
    isolated_well_box: tuple[float, float, float, float]
    other_well_boxes: list[tuple[float, float, float, float]]
    mp12_x_centers: list[float] = field(default_factory=list)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def build(outdir: Path | None = None) -> DumpBufCell:
    canvas = devgen.Canvas(TOP_CELL)

    nets: dict[str, list[tuple[float, float]]] = {}

    def add(net: str, pad: tuple[float, float, float, float]) -> None:
        nets.setdefault(net, []).append(pad_center(pad))

    n_ports = _place_row(canvas, N_DEVICES, ROW_Y_N)
    p_ports = _place_row(canvas, P_DEVICES, ROW_Y_P)

    for (dev, _gap), port in zip(N_DEVICES, n_ports):
        add(dev.gate_net, port.gate_pad)
        add(dev.top_net, port.top_pad)
        add(dev.bottom_net, port.bottom_pad)
    for (dev, _gap), port in zip(P_DEVICES, p_ports):
        add(dev.gate_net, port.gate_pad)
        add(dev.top_net, port.top_pad)
        add(dev.bottom_net, port.bottom_pad)

    by_name_n = {dev.name: port for (dev, _g), port in zip(N_DEVICES, n_ports)}
    by_name_p = {dev.name: port for (dev, _g), port in zip(P_DEVICES, p_ports)}

    other_well_boxes: list[tuple[float, float, float, float]] = []

    # N-well tap strips sit ABOVE their row (inside the well they tap);
    # substrate tap strips sit BELOW their row -- see _tap_strip()'s own
    # docstring for why a strip spanning the whole group's X range, not a
    # single small tap, is required here.
    n_tap_y = ROW_Y_N + ROW_HEIGHT_UM + TAP_GAP_UM + TAP_SIZE_UM / 2.0
    n_sub_y = ROW_Y_N - TAP_GAP_UM - TAP_SIZE_UM / 2.0
    p_tap_y = ROW_Y_P + ROW_HEIGHT_UM + TAP_GAP_UM + TAP_SIZE_UM / 2.0
    p_sub_y = ROW_Y_P - TAP_GAP_UM - TAP_SIZE_UM / 2.0

    # --- N-row standard n-well (MN3/MN4, tied VDD) ---
    mn34 = [by_name_n["MN3"], by_name_n["MN4"]]
    mn34_boxes = [(p.x0, p.y0, p.x1, p.y3) for p in mn34]
    tap_box, tap_pad = _tap_strip(canvas, "n", mn34[0].x0, mn34[-1].x1, n_tap_y, "VDD")
    n_std_well = tuple(
        v + s * devgen.NWELL_MARGIN_UM
        for v, s in zip(bbox_union([*mn34_boxes, tap_box]), (-1, -1, 1, 1))
    )
    canvas.rect("nwell", *n_std_well)
    other_well_boxes.append(n_std_well)
    add("VDD", tap_pad)

    # --- N-row substrate tap strip (MTN/MN1/MN2, tied VSS) -- DRC hygiene,
    # per devgen.py's own "WELL/SUBSTRATE TIES" convention (not required for
    # LVS, the deck globally ties every NMOS body to the substrate net). ---
    n_nfet_first, n_nfet_last = by_name_n["MTN"], by_name_n["MN2"]
    _sub_box, sub_pad = _tap_strip(canvas, "p", n_nfet_first.x0, n_nfet_last.x1, n_sub_y, "VSS")
    add("VSS", sub_pad)

    # --- P-row standard n-well (MTPa/MTPb, tied VDD) ---
    mtp = [by_name_p["MTPa"], by_name_p["MTPb"]]
    mtp_boxes = [(p.x0, p.y0, p.x1, p.y3) for p in mtp]
    mtp_tap_box, mtp_tap_pad = _tap_strip(canvas, "n", mtp[0].x0, mtp[-1].x1, p_tap_y, "VDD")
    mtp_well = tuple(
        v + s * devgen.NWELL_MARGIN_UM for v, s in zip(bbox_union([*mtp_boxes, mtp_tap_box]), (-1, -1, 1, 1))
    )
    canvas.rect("nwell", *mtp_well)
    other_well_boxes.append(mtp_well)
    add("VDD", mtp_tap_pad)

    # --- P-row isolated n-well (MP1a/MP2a/MP2b/MP1b, tied PSRC) -- the
    # matching-critical block this issue exists to draw. ---
    mp12_ports = [by_name_p[n] for n in MP12_NAMES]
    mp12_boxes = [(p.x0, p.y0, p.x1, p.y3) for p in mp12_ports]
    iso_tap_box, iso_tap_pad = _tap_strip(canvas, "n", mp12_ports[0].x0, mp12_ports[-1].x1, p_tap_y, "PSRC")
    isolated_well = tuple(
        v + s * devgen.NWELL_MARGIN_UM for v, s in zip(bbox_union([*mp12_boxes, iso_tap_box]), (-1, -1, 1, 1))
    )
    canvas.rect("nwell", *isolated_well)
    add("PSRC", iso_tap_pad)

    # --- P-row substrate tap strip (MP3/MP4, tied VSS) ---
    mp3, mp4 = by_name_p["MP3"], by_name_p["MP4"]
    _p2_box, p2_tap_pad = _tap_strip(canvas, "p", mp3.x0, mp4.x1, p_sub_y, "VSS")
    add("VSS", p2_tap_pad)

    # --- explicit well-separation proof: the isolated well vs. every other
    # n-well *this cell itself* draws (Part 3's real CP-array wells, once
    # #301 lands, are checked the same way -- see this module's docstring
    # and DIFFERENT_POTENTIAL_WELL_MIN_UM's own comment). ---
    for other in other_well_boxes:
        check_well_separation(isolated_well, other)

    # --- MP1/MP2 common-centroid proof (arithmetic, not visual) ---
    mp12_x_centers = [(p.x0 + p.x1) / 2.0 for p in mp12_ports]
    check_common_centroid(MP12_PATTERN, mp12_x_centers)

    # --- external pins: one Metal1 pad per schematic ipin/iopin, promoted
    # with devgen.Canvas.pin() (labels on the 34/10 purpose the official LVS
    # deck reads -- see devgen.py's own LAYER table comment), joining the
    # same net's routed bus like any other pad. ---
    pins: dict[str, tuple[float, float, float, float]] = {}
    for i, net in enumerate(EXTERNAL_NETS):
        y = ROW_Y_N + i * PIN_PITCH_UM
        pad = (PIN_X_UM - 0.3, y - 0.3, PIN_X_UM + 0.3, y + 0.3)
        canvas.rect("metal1", *pad)
        canvas.pin(net, *pad)
        add(net, pad)
        pins[net] = pad

    # --- route every net: one Metal2 bus + per-pad Metal3 risers, at a
    # track_y unique to that net, in a channel above the whole cell (see
    # this module's docstring, "ROUTING"). ---
    channel_base_y = ROW_Y_P + ROW_HEIGHT_UM + 6.0
    tracks = NetTracks(base_y=channel_base_y)
    for net, centers in nets.items():
        _route_net(canvas, net, centers, tracks.get(net))

    all_ports = n_ports + p_ports
    footprint_x0 = min(PIN_X_UM - 0.3, min(p.x0 for p in all_ports))
    footprint_x1 = max(p.x1 for p in all_ports) + TAP_GAP_UM + TAP_SIZE_UM + devgen.NWELL_MARGIN_UM
    footprint_y0 = ROW_Y_N - devgen.NWELL_MARGIN_UM
    footprint_y1 = tracks._next_y  # noqa: SLF001 -- top of the last routed track

    return DumpBufCell(
        canvas=canvas,
        footprint=(footprint_x0, footprint_y0, footprint_x1, footprint_y1),
        pins=pins,
        isolated_well_box=isolated_well,
        other_well_boxes=other_well_boxes,
        mp12_x_centers=mp12_x_centers,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "cp-dumpbuf-layout" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cell = build()
    gds_path = outdir / f"{TOP_CELL}.gds"
    cell.write_gds(gds_path)
    x0, y0, x1, y1 = cell.footprint
    print(f"wrote {gds_path}")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"isolated well box: {cell.isolated_well_box}")
    for other in cell.other_well_boxes:
        gap = well_separation_um(cell.isolated_well_box, other)
        print(f"  clearance from other well {other}: {gap:.3f} um")
    print(f"MP1/MP2 finger x-centers: {cell.mp12_x_centers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
