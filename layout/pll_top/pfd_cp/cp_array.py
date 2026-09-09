"""``cp_array`` -- common-centroid N/P unit-leg arrays + 4x-scaled bias branch
for the charge pump's output stage (issue #320, Part 3b of #294's
device-layout methodology, a decomposition of #301).

WHAT THIS BUILDS
-----------------
Two independent common-centroid arrays, each built from Part 3a's already-
built composite leaf cells (``cp_leg_n``/``cp_leg_p``, issue #319):

* N (sink) array: 4x ``cp_leg_n`` -- ``xn_base`` (always-on, ``EN=VDD``/
  ``ENB=VSS`` directly), ``xn_t0`` (``EN/ENB=B0/B0B``), ``xn_t1a``/``xn_t1b``
  (``EN/ENB=B1/B1B``) -- plus ``MBN``/``MCN`` (4x-scaled bias-branch
  ``nfet_03v3`` diodes, ``IBN``/``ICN``).
* P (source) array: 4x ``cp_leg_p`` (``xp_base``/``xp_t0``/``xp_t1a``/
  ``xp_t1b``, same trim wiring) plus ``MBP``/``MCP`` (``pfet_03v3`` diodes,
  ``IBP``/``ICP``).

Every net name and device size below is read directly off
``design/cp.sch``'s own ``lab_pin`` labels and ``MBN``/``MCN``/``MBP``/
``MCP`` instances (not re-derived) -- see :data:`BIAS_DEVICES_N`/
:data:`BIAS_DEVICES_P` and :data:`N_NET_MAP`/:data:`P_NET_MAP`.

Out of scope (per this issue's own text, deferred to sibling issues): the
glue inverters/steering/dump switches that wire this array into the full
charge pump (#321, Part 3c) and ``cp_dumpbuf``/the combined ``pfd_cp``
assembly (#302/#303, Parts 4-5). This module's own standalone DRC proof
covers only the N+P array block drawn here -- no LVS claim (no reference
netlist is stated) since the full circuit function is not complete until
Part 3c's glue logic closes the loop; see ``layout/evidence/cp-array-proof/
PROOF.md``.

GDS-LEVEL PLACEMENT, NOT FOUR-TIMES REDRAWN GEOMETRY
------------------------------------------------------
Each of the 4 legs in one polarity's array is an *identical* copy of the one
``cp_leg_n``/``cp_leg_p`` cell Part 3a already built and proved DRC/LVS-clean
(same ``LegSpec`` regardless of which trim bit ends up driving its ``EN``/
``ENB`` -- that wiring happens entirely *outside* the leg, at this module's
own assembly level). Per ``divider_chain.py``'s own precedent (issue #310,
"SIX IDENTICAL ``div23_cell`` INSTANCES: GDS-LEVEL PLACEMENT, NOT SIX
REDRAWS"), this module builds ``cp_leg_n``/``cp_leg_p`` exactly once each,
writes each to a scratch GDS, and places four ``klayout.db.CellInstArray``
references per polarity, translated into this module's own common-centroid
pattern, then flattens (``top.flatten(-1, True)``) -- same reason that
module gives: the four placements are geometrically identical copies of one
proven-clean cell, not four independent code paths that could drift, and a
flat top cell needs no sub-circuit correspondence for the DRC deck to run
against (no LVS claim is made here, but the same flattening keeps this
module's own drawing conventions -- Metal2/3 risers that must "free-cross"
sub-cell geometry -- consistent with every other composite in this package).
``cp_leg_n.py``/``cp_leg_p.py`` are not modified by this module, only
consumed, exactly as issue #320's own Affected Files section specifies.

COMMON-CENTROID PLACEMENT: A "TRIPOD", NOT A ROW OR A 2x2 GRID
-------------------------------------------------------------------
Per ``PLL-FLOORPLAN.md`` and this issue's own text, each array's geometric
centre -- defined as the arithmetic mean of its own 4 leg-instance centres
-- must coincide with the always-on leg's own centre (``xn_base``/
``xp_base``). Unlike ``vco/mirror.py``'s own interdigitated finger arrays
(1-D, many identical-width fingers in a row, so "the array's centre" and "a
finger's own position" can coincide at the row's midpoint), this array's 4
"legs" are whole composite *cells* -- 2-D, and there are exactly 4 of them,
an even count. A row of 4 identical-footprint cells has no cell sitting at
its own arithmetic centre (the mean of 4 evenly-spaced positions falls
*between* the 2nd and 3rd), and neither does a non-overlapping 2x2 grid (the
grid's own centre point sits in the gap between all four cells, not at any
one cell's own position) -- so no plain row or grid placement can ever
satisfy "the always-on leg sits exactly at the array's own centroid"
for 4 identical-size whole cells, regardless of spacing.

:func:`leg_offsets` instead places the 3 switched legs at the vertices of an
isosceles triangle centred on the always-on leg (``t0``/``t1a`` mirrored
left/right and below; ``t1b`` directly above, twice as far, so the three
offsets' vector sum -- and therefore their mean -- is exactly zero)::

               t1b
                |
      t0 ---- base ---- t1a

This is exactly the "hand-picked coordinates satisfying the same centroid
equation, not finger interdigitation" this issue's own text anticipates.
:func:`check_common_centroid` is the pure-arithmetic proof, generalized to
2-D points -- the analog of ``vco/mirror.py``'s own ``leg_centroid_um()``/
``check_common_centroid()`` this issue's own text asks for (reference only;
``mirror.py`` itself is not modified). The two horizontal legs (``t0``,
``t1a``) clear the always-on leg by construction (offset magnitude
``leg_w + gap`` along X alone, independent of Y); ``t1b`` clears it along Y
alone (offset magnitude ``leg_h + gap``) -- see :func:`leg_offsets`'s own
docstring for the exact clearance arithmetic.

N/P SEPARATION: A COMPUTED, NOT HAND-PICKED, SHIFT
-----------------------------------------------------
The N and P arrays are placed side by side with the P array's own local
origin shifted right by exactly enough to clear the N side's own rightmost
extent (array + bias branch) plus :data:`N_P_GAP_UM` -- computed from each
side's own real geometry (:func:`build`'s own ``shift_x``), not a hand-tuned
constant that could silently go stale if either leg's own footprint changes.
:func:`build` asserts the resulting non-overlap explicitly (belt-and-
suspenders on top of the by-construction guarantee) rather than only
relying on the arithmetic being correct.

BIAS BRANCH: ADJACENT, NOT INSIDE
------------------------------------
``MBN``/``MCN`` (``design/cp.sch``'s own 4x-scaled diode-connected bias
devices, single ``nfet_03v3`` instances -- see :data:`BIAS_DEVICES_N`) are
drawn directly with ``devgen.mosfet()`` (the same primitive
``cp_leg.py``/``cp_dumpbuf.py`` already use) in a row *below* the N array's
own footprint, clear of every one of its 4 legs by
:data:`BIAS_ROW_GAP_UM`; ``MBP``/``MCP`` (:data:`BIAS_DEVICES_P`) are placed
the same way below the P array. Each device's own drain is diode-connected
to its own gate with :func:`_diode_connect` (a two-segment Metal1 jog,
generalizing ``cp_leg.py``'s own ``_route_bg_tap()`` technique to an
arbitrary device width -- see that function's own docstring for why a
straight run cannot reach), matching ``design/cp.sch``'s own ``MBN``/
``MCN``/``MBP``/``MCP`` instances (each one's drain *and* gate both labelled
the same bias net -- ``IBN``, ``ICN``, ``IBP``, ``ICP`` respectively).

MESH ROUTING: A THIRD, INDEPENDENT Via1/Metal2/Via2/Metal3 RISER FABRIC
----------------------------------------------------------------------------
Per this package's own established convention ("each full-custom leaf-cell
family owns its own generator" -- ``devgen.py``'s module docstring;
``cp_dumpbuf.py``'s own docstring makes the same choice against
``lock_detector/primitives.py``'s otherwise-identical riser), this module
draws its own copy of the Via1-Metal2-Via2-Metal3-Via2-Metal2 riser/bus
fabric (:func:`_riser`/:func:`_route_side`/:class:`NetTracks`), structurally
identical to ``cp_dumpbuf.py``'s own (same margins/citations) plus one
addition ``cp_dumpbuf.py`` did not need (:func:`declutter_riser_x`, see its
own docstring) -- rather than importing it. Metal3 is the one layer with no
DRC spacing relationship to
Metal1/comp/poly2/nwell in this deck, so a net's riser can run straight from
any leg instance's own pin -- however far below the routing channel that
instance happens to sit (``xn_t0``'s own pins are ~12 um below ``xn_t1b``'s,
after this module's own tripod placement) -- up to its own dedicated
Metal2 track with no risk of shorting to any of the other 3 legs' own
already-proven-clean internal Metal1/comp/poly2 geometry underneath it.

Every net this module routes is a genuine top-level pin of this array block
(promoted with ``canvas.pin()``, which -- see ``layout/pll_top/_canvas.py``'s
own docstring -- only labels and records, drawing no extra shape, so it
composes cleanly with the pad already placed by routing): ``IBN``/``ICN``/
``DNT``/``VSS`` (all 4 N legs + ``MBN``/``MCN``), ``B0``/``B0B`` (``xn_t0``
only), ``B1``/``B1B`` (``xn_t1a``+``xn_t1b``), and the P-polarity
equivalents (``IBP``/``ICP``/``UPT``/``VDD``, plus ``B0``/``B0B``/``B1``/
``B1B`` again -- disconnected from the N-side pins of the same name; tying
the two polarities' trim bits together electrically is glue-logic-level
wiring, Part 3c's own job, not this module's). ``xn_base``'s own ``EN``
(``VDD``) and ``xp_base``'s own ``ENB`` (``VSS``) are each the *only* pad on
their own net within this block, so each is promoted as its own standalone
pin rather than merged into any trim net -- exactly the "ties directly to
VDD/VSS, not a trim net" acceptance criterion. ``xn_base``'s own ``ENB``
(``VSS``) and ``xp_base``'s own ``EN`` (``VDD``), by contrast, join the
*real* multi-pad rail mesh already present on their own side (every leg's
own rail pin + the bias branch's own source pads).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import cp_leg_n, cp_leg_p, devgen

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention -- see
    # cp_dumpbuf.py's own identical try/except for the full citation.
    import _canvas

TOP_CELL = "cp_array"

# --- extra GDS layers this module needs beyond devgen.Canvas's own
# comp/poly2/contact/nplus/pplus/nwell/metal1 set -- identical citation/
# values to cp_dumpbuf.py's own _EXTRA_LAYER. ---
_EXTRA_LAYER = {
    "via1": (35, 0),
    "metal2": (36, 0),
    "via2": (38, 0),
    "metal3": (42, 0),
}

# --- Metal2/Metal3/Via routing margins -- identical values/citation to
# cp_dumpbuf.py's own (in turn from lock_detector/primitives.py). ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b min is ~0 um; headroom for the enclosing metal pad
METAL2_WIRE_WIDTH_UM = 0.34  # > M2.1's 0.28 min
METAL3_WIRE_WIDTH_UM = 0.34  # > M3.1's 0.28 min
METAL2_TRACK_PITCH_UM = 0.75  # (pitch - width) = 0.41 > M2.2a's 0.28 min, between two tracks

# --- Array/placement margins (um). ---
LEG_GAP_UM = 3.0
"""Clearance between two leg footprints along whichever axis separates them
-- see :func:`leg_offsets`'s own docstring for the exact pairwise clearance
arithmetic this drives. Matches ``cp_leg.py``'s own ``COLUMN_GAP_UM``
(3.0 um), itself well past this deck's real comp/implant minimums.
"""

N_P_GAP_UM = 5.0
"""N side's own rightmost extent (array + bias branch) -> P array's own
leftmost extent, after :func:`build`'s own computed ``shift_x``. Generous
headroom past this deck's real spacing minimums -- the two arrays are
different device geometries (per this issue's own text) that must never
interdigitate, so this gap is a real design margin, not a DRC-minimum-sized
one.
"""

BIAS_ROW_GAP_UM = 4.0  # array's own bottom edge -> bias-branch row's own top edge
BIAS_DEVICE_GAP_UM = 2.0  # MBN<->MCN / MBP<->MCP side-by-side clearance;
# same value/rationale as cp_dumpbuf.py's own DEVICE_GAP_UM (clears a
# device's own left-hanging gate tab from its left neighbour's rightmost
# Metal1 pad, for this same device-margin family).
CHANNEL_MARGIN_UM = 3.0  # one side's own topmost drawn edge -> its own routing channel base_y

BIAS_L_UM = 1.0  # design/cp.sch's own MBN/MCN/MBP/MCP -- all L=1u
BIAS_DEVICE_H_UM = 2.0 * devgen.SD_OVERHANG_UM + BIAS_L_UM


# ---------------------------------------------------------------------------
# Pure-Python placement/centroid math -- no klayout import, testable with no
# PV environment (same convention as cp_dumpbuf.py's own
# check_common_centroid()/check_well_separation()).
# ---------------------------------------------------------------------------


def leg_offsets(leg_w_um: float, leg_h_um: float, gap_um: float) -> dict[str, tuple[float, float]]:
    """The tripod placement offsets (see module docstring) for one polarity's
    4-leg array, relative to the always-on leg (``"base"``) at ``(0, 0)``.

    ``a = leg_w_um + gap_um`` is ``t0``'s/``t1a``'s own X offset magnitude:
    since the always-on leg and ``t0``/``t1a`` all share the same footprint
    size, an X separation of ``leg_w_um + gap_um`` alone clears the pair
    regardless of their (possibly nonzero) Y separation -- two same-size
    axis-aligned boxes never overlap if they clear on *either* axis alone.
    ``b = (leg_h_um + gap_um) / 2`` is chosen so ``t1b``'s own Y offset
    (``2*b = leg_h_um + gap_um``) clears the always-on leg the same way,
    along Y alone. Every other pair among the 4 legs clears via whichever of
    those two already-guaranteed separations applies to it (``t0``<->``t1a``:
    ``2a`` in X; ``t0``/``t1a``<->``t1b``: ``a`` in X, already sufficient) --
    see the module docstring's ASCII diagram.
    """
    a = leg_w_um + gap_um
    b = (leg_h_um + gap_um) / 2.0
    return {
        "base": (0.0, 0.0),
        "t0": (-a, -b),
        "t1a": (a, -b),
        "t1b": (0.0, 2.0 * b),
    }


def centroid_um(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Arithmetic mean of ``points`` -- the 2-D analog of ``vco/mirror.py``'s
    own ``leg_centroid_um()`` (that function averages 1-D finger centres
    along a single row; this array's own "legs" are 2-D whole cells, so the
    mean is taken over both axes -- see module docstring).
    """
    pts = list(points)
    if not pts:
        raise ValueError("centroid_um() needs at least one point")
    n = len(pts)
    return (sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n)


def check_common_centroid(
    base_point: tuple[float, float], other_points: Sequence[tuple[float, float]], tol_um: float = 1e-9
) -> None:
    """Raise unless ``base_point`` (the always-on leg's own centre) coincides
    with the arithmetic mean of itself and every point in ``other_points``
    (the switched legs' own centres) -- the 2-D analog of ``vco/mirror.py``'s
    own ``check_common_centroid()`` (reference only; that module is not
    modified -- see issue #320's own Affected Files section).
    """
    centre = centroid_um([base_point, *other_points])
    dx = abs(centre[0] - base_point[0])
    dy = abs(centre[1] - base_point[1])
    if dx > tol_um or dy > tol_um:
        raise ValueError(
            f"array centroid {centre} != always-on leg centre {base_point} (dx={dx:.6g}, dy={dy:.6g})"
        )


def _translate_box(
    box: tuple[float, float, float, float], dx: float, dy: float
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def boxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """``True`` iff two axis-aligned boxes share any positive-area overlap
    (touching edges alone -- zero-width/height intersection -- do not
    count as overlap)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def box_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


# ---------------------------------------------------------------------------
# design/cp.sch's own device table for MBN/MCN/MBP/MCP (all single
# nfet_03v3/pfet_03v3 instances, diode-connected -- drain and gate both the
# device's own bias net) and the per-leg-instance local-pin -> this block's
# own top-level net map (design/cp.sch's own lab_pin labels on each
# cp_leg_n/cp_leg_p instance -- xn_base/xn_t0/xn_t1a/xn_t1b and
# xp_base/xp_t0/xp_t1a/xp_t1b).
# ---------------------------------------------------------------------------

Device = devgen.Device

#: design/cp.sch: MBN (nfet_03v3, W=16u L=1u, D=G=IBN, S=B=VSS), MCN
#: (nfet_03v3, W=4u L=1u, D=G=ICN, S=B=VSS).
BIAS_DEVICES_N: tuple[Device, Device] = (
    Device(name="MBN", kind="nfet", w_um=16.0, l_um=BIAS_L_UM, gate_net="IBN", top_net="IBN", bottom_net="VSS"),
    Device(name="MCN", kind="nfet", w_um=4.0, l_um=BIAS_L_UM, gate_net="ICN", top_net="ICN", bottom_net="VSS"),
)

#: design/cp.sch: MBP (pfet_03v3, W=48u L=1u, D=G=IBP, S=B=VDD), MCP
#: (pfet_03v3, W=12u L=1u, D=G=ICP, S=B=VDD).
BIAS_DEVICES_P: tuple[Device, Device] = (
    Device(name="MBP", kind="pfet", w_um=48.0, l_um=BIAS_L_UM, gate_net="IBP", top_net="IBP", bottom_net="VDD"),
    Device(name="MCP", kind="pfet", w_um=12.0, l_um=BIAS_L_UM, gate_net="ICP", top_net="ICP", bottom_net="VDD"),
)

LEG_NAMES: tuple[str, str, str, str] = ("base", "t0", "t1a", "t1b")

#: cp_leg_n's own local pin name -> this block's own top-level net, per
#: instance (design/cp.sch's own lab_pin labels on xn_base/xn_t0/xn_t1a/
#: xn_t1b). xn_base's own EN/ENB tie directly to VDD/VSS -- not B0/B0B or
#: B1/B1B -- per this issue's own acceptance criterion.
N_NET_MAP: dict[str, dict[str, str]] = {
    "base": {"VBN": "IBN", "VCASCN": "ICN", "EN": "VDD", "ENB": "VSS", "TAIL": "DNT", "VSS": "VSS"},
    "t0": {"VBN": "IBN", "VCASCN": "ICN", "EN": "B0", "ENB": "B0B", "TAIL": "DNT", "VSS": "VSS"},
    "t1a": {"VBN": "IBN", "VCASCN": "ICN", "EN": "B1", "ENB": "B1B", "TAIL": "DNT", "VSS": "VSS"},
    "t1b": {"VBN": "IBN", "VCASCN": "ICN", "EN": "B1", "ENB": "B1B", "TAIL": "DNT", "VSS": "VSS"},
}

#: cp_leg_p's own local pin name -> this block's own top-level net, per
#: instance. xp_base's own EN/ENB tie directly to VDD/VSS.
P_NET_MAP: dict[str, dict[str, str]] = {
    "base": {"VBP": "IBP", "VCASCP": "ICP", "EN": "VDD", "ENB": "VSS", "TAIL": "UPT", "VDD": "VDD"},
    "t0": {"VBP": "IBP", "VCASCP": "ICP", "EN": "B0", "ENB": "B0B", "TAIL": "UPT", "VDD": "VDD"},
    "t1a": {"VBP": "IBP", "VCASCP": "ICP", "EN": "B1", "ENB": "B1B", "TAIL": "UPT", "VDD": "VDD"},
    "t1b": {"VBP": "IBP", "VCASCP": "ICP", "EN": "B1", "ENB": "B1B", "TAIL": "UPT", "VDD": "VDD"},
}


# ---------------------------------------------------------------------------
# klayout-dependent geometry helpers (lazy import via devgen.Canvas already
# handled; this module's own extra layers need their own lazy import).
# ---------------------------------------------------------------------------


def _rect_extra(canvas: devgen.Canvas, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
    """Draw a rectangle on one of this module's own extra layers -- identical
    technique to ``cp_dumpbuf.py``'s own ``_rect_extra()``."""
    import klayout.db as db  # noqa: PLC0415

    idx = canvas.layout.layer(*_EXTRA_LAYER[layer])
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    u = lambda v: int(round(v * 1000))  # noqa: E731 -- devgen.Canvas's own dbu=0.001 is fixed
    canvas.top.shapes(idx).insert(db.Box(u(x0), u(y0), u(x1), u(y1)))


def _riser(canvas: devgen.Canvas, x: float, y_pad: float, track_y: float) -> None:
    """Metal1 pad -> Via1 -> Metal2 landing -> Via2 -> Metal3 riser -> Via2 ->
    Metal2 bus landing -- structurally identical to ``cp_dumpbuf.py``'s own
    ``_riser()`` (see this module's own docstring, "MESH ROUTING"), plus one
    addition that module did not need: an explicit Metal1 landing square
    under the Via1, sized to fully enclose it (``V1.3a``). ``cp_dumpbuf.py``
    always rises directly off an already-real, already-sizable device pad;
    this module's own :func:`declutter_riser_x` can move a riser's own X a
    short distance off its pad's natural centre, onto a plain
    :func:`_stub` jog that is only ``METAL1_WIRE_WIDTH_UM`` (0.28 um) wide --
    narrower than Via1's own required enclosure (0.44 um) -- so this cannot
    rely on the incoming Metal1 already being wide enough (a real,
    reproduced ``V1.3a`` failure during this module's own development).
    """
    half_v1 = VIA1_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM
    canvas.rect("metal1", x - half_v1, y_pad - half_v1, x + half_v1, y_pad + half_v1)
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


def pad_center(pad: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((pad[0] + pad[2]) / 2.0, (pad[1] + pad[3]) / 2.0)


RISER_MIN_PITCH_UM = 1.0
"""Minimum centre-to-centre X separation this module ever allows between two
*different* Metal3 riser positions on one side (N or P), enforced by
:func:`declutter_riser_x`. Comfortably above the real DRC-minimum pitch
(``METAL3_WIRE_WIDTH_UM`` (0.34) + ``M3.2a``'s 0.28 um minimum space =
0.62 um) -- see that function's own docstring for why a plain natural-X
riser placement is not safe here on its own.
"""


def declutter_riser_x(
    points: Sequence[tuple[str, float, float]], min_pitch: float = RISER_MIN_PITCH_UM
) -> list[tuple[str, float, float]]:
    """Given ``(net, x, y)`` riser candidates -- one per pad this module needs
    to rise from -- return the same points with ``x`` nudged rightward (never
    ``y``) so that no two points end up less than ``min_pitch`` apart in X,
    sweeping left to right by natural X.

    WHY THIS IS NEEDED: a plain "rise at each pad's own natural X" approach
    (this module's own first attempt) hit a real, reproduced failure --
    ``xp_base``'s own ``VCASCP`` pin (mapped to ``ICP``) landed only ~0.24 um
    from ``MBP``'s own source pad centre (mapped to ``VDD``), a real M3.2a
    violation between two genuinely *different* nets whose natural positions
    happened to coincide by simple bad luck (a wide 48 um bias device's own
    pad centre landing inside a much narrower leg's own tightly-spaced pin
    cluster) -- not a systemic density problem this module's own hand-picked
    tripod placement could see coming. Decluttering by X, globally across
    every net on one side, fixes this the same way regardless of *which*
    two nets happen to collide, rather than special-casing the one pair
    this module's own development run happened to hit.

    Exact ties (a point whose own *natural* X exactly equals the
    immediately preceding point's own *natural* X, in sorted order) are
    assigned that preceding point's own *final* X, whatever it ended up
    being -- rather than left at their own unperturbed natural X. Two risers
    at the literal same natural X only ever occur here when two pads of the
    *same* net share an identical local-X translation (this module's own
    tripod places ``t1b`` directly above ``base``, so every one of
    ``t1b``'s own pins lands at exactly ``base``'s own X for that pin), and
    :func:`_riser` always runs each riser from its own pad up to that net's
    own shared track, so two same-X same-net risers always fully overlap in
    Y along the way -- already DRC-safe by construction. Snapping the tied
    point to its sibling's own *final* X (not its own unperturbed natural X)
    is required, not merely tidy: a naive "leave ties alone" rule -- comparing
    each point only against the running *assigned* ``x`` -- breaks the moment
    an earlier point in the sweep gets nudged past a later point that shares
    its *own* natural X (a real, reproduced failure during this module's own
    development: two ``ICN`` pads at an identical natural X, sorted stably
    adjacent, where the first got nudged rightward by an intervening
    different-net point and the second -- still comparing its own
    unperturbed natural X against the now-larger running ``x`` -- computed a
    *negative* delta and was left behind, only 0.3 um from its own nudged
    sibling). Comparing each point's own *natural* X against the
    *preceding* point's own natural X (not the running assigned one) finds
    the tie correctly regardless of any nudging that happened earlier in the
    sweep.
    """
    order = sorted(range(len(points)), key=lambda i: points[i][1])
    result = list(points)
    prev_natural_x: float | None = None
    prev_assigned_x: float | None = None
    for i in order:
        net, natural_x, y = points[i]
        if prev_assigned_x is None:
            assigned_x = natural_x
        elif natural_x == prev_natural_x:
            assigned_x = prev_assigned_x
        elif natural_x - prev_assigned_x < min_pitch:
            assigned_x = prev_assigned_x + min_pitch
        else:
            assigned_x = natural_x
        result[i] = (net, assigned_x, y)
        prev_natural_x = natural_x
        prev_assigned_x = assigned_x
    return result


def _stub(canvas: devgen.Canvas, a: tuple[float, float], b: tuple[float, float], width: float = devgen.METAL1_WIRE_WIDTH_UM) -> None:
    """A short Metal1 jog from an original pad centre ``a`` to its own
    (possibly X-nudged) assigned riser point ``b``. :func:`declutter_riser_x`
    only ever changes X, never Y, so this is always a single horizontal
    segment at the pad's own Y -- short (bounded by a handful of
    :data:`RISER_MIN_PITCH_UM`), so it stays well clear of any other drawn
    geometry the same way every other short same-cell jog in this package
    does (``cp_leg.py``'s own ``_route_bg_tap()``, this module's own
    ``_diode_connect()``).
    """
    half = width / 2.0
    x0, x1 = sorted((a[0], b[0]))
    canvas.rect("metal1", x0, a[1] - half, x1, a[1] + half)


def _route_side(
    canvas: devgen.Canvas,
    nets: dict[str, list[tuple[float, float, float, float]]],
    side_bbox: tuple[float, float, float, float],
    channel_margin_um: float = CHANNEL_MARGIN_UM,
    min_pitch: float = RISER_MIN_PITCH_UM,
) -> NetTracks:
    """Mesh-route every net in ``nets`` (dict of net -> its own Metal1 pad
    boxes) to its own dedicated Metal2 track in one channel above
    ``side_bbox``'s own topmost drawn edge, then promote each as a top-level
    pin -- see module docstring's "MESH ROUTING" section. Declutters every
    net's own riser X *together* (:func:`declutter_riser_x`, not per net in
    isolation) so nets that happen to land close in X by coincidence (not
    just the same net's own multiple pads) never violate M3.2a.
    """
    tracks = NetTracks(base_y=side_bbox[3] + channel_margin_um)

    flat_nets: list[str] = []
    flat_boxes: list[tuple[float, float, float, float]] = []
    for net, boxes in nets.items():
        for box in boxes:
            flat_nets.append(net)
            flat_boxes.append(box)
    flat_points = [(flat_nets[i], *pad_center(flat_boxes[i])) for i in range(len(flat_boxes))]
    planned = declutter_riser_x(flat_points, min_pitch)

    bus_x: dict[str, list[float]] = {}
    seen_riser: set[tuple[str, float, float]] = set()
    for i, (net, rx, ry) in enumerate(planned):
        ox, oy = pad_center(flat_boxes[i])
        if (round(ox, 6), round(oy, 6)) != (round(rx, 6), round(ry, 6)):
            _stub(canvas, (ox, oy), (rx, ry))
        key = (net, round(rx, 6), round(ry, 6))
        if key not in seen_riser:
            _riser(canvas, rx, ry, tracks.get(net))
            seen_riser.add(key)
        bus_x.setdefault(net, []).append(rx)

    for net, xs in bus_x.items():
        track_y = tracks.get(net)
        x_lo, x_hi = min(xs), max(xs)
        if x_hi > x_lo:
            half = METAL2_WIRE_WIDTH_UM / 2.0
            _rect_extra(canvas, "metal2", x_lo - half, track_y - half, x_hi + half, track_y + half)
        canvas.pin(net, *nets[net][0])

    return tracks


class NetTracks:
    """Hands out a fresh, never-reused Metal2 track_y per net name -- see
    ``cp_dumpbuf.NetTracks``, whose behaviour is identical."""

    def __init__(self, base_y: float, pitch: float = METAL2_TRACK_PITCH_UM) -> None:
        self._next_y = base_y
        self._pitch = pitch
        self._assigned: dict[str, float] = {}

    def get(self, net: str) -> float:
        if net not in self._assigned:
            self._assigned[net] = self._next_y
            self._next_y += self._pitch
        return self._assigned[net]


def _diode_connect(canvas: devgen.Canvas, gate_pad: tuple, top_pad: tuple, wire_w: float = devgen.METAL1_WIRE_WIDTH_UM) -> None:
    """Short a single device's own gate pad to its own top (drain) pad -- the
    diode connection every one of ``MBN``/``MCN``/``MBP``/``MCP`` needs
    (``design/cp.sch`` labels each one's drain *and* gate with the same bias
    net -- e.g. ``MBN``'s ``D``/``G`` both ``IBN``).

    A straight ``devgen._connect_pads()`` run does not apply: a device's own
    gate pad sits to the *left* of its comp (``POLY_ENDCAP_UM`` past its
    ``x0``, at a fixed height near the gate's own vertical centre), while its
    own top (drain) pad spans across the *top* of that same comp, near its
    ``y3`` -- for any device wide enough that the gate tab is not directly
    below the drain pad's own left edge (every device this module places),
    the two share no X *or* Y overlap a single straight run could bridge.
    This draws the two-segment jog every width needs -- vertical at the
    gate's own X up to the drain pad's own Y band, then horizontal into that
    pad's own X range -- the same general "L-route" technique
    ``cp_leg.py``'s own ``_route_bg_tap()`` uses for its one fixed-geometry
    case, generalized here to any ``(gate_pad, top_pad)`` pair from
    ``devgen.mosfet()``.
    """
    gx, gy = pad_center(gate_pad)
    ty = pad_center(top_pad)[1]
    tx0 = top_pad[0]
    half = wire_w / 2.0
    # Extend each segment half a wire-width *past* the elbow's own centreline
    # (rather than stopping exactly at it) so the two segments overlap in a
    # full wire_w x wire_w square at the corner, not just a partial sliver --
    # a plain "stop exactly at the joint" L only guarantees the two segments
    # *touch*, and a corner where one segment's own far edge lands exactly on
    # the other's own centreline leaves a notch narrower than M1.1's minimum
    # width on the outside of the turn.
    y_far = ty + half if ty >= gy else ty - half
    y0, y1 = sorted((gy, y_far))
    canvas.rect("metal1", gx - half, y0, gx + half, y1)
    x_near = gx - half if (tx0 + wire_w) >= gx else gx + half
    x0, x1 = sorted((x_near, tx0 + wire_w))
    canvas.rect("metal1", x0, ty - half, x1, ty + half)


def _tap_strip(
    canvas: devgen.Canvas,
    kind: str,
    x0: float,
    x1: float,
    y_center: float,
    net: str,
    height: float = devgen.TAP_SIZE_UM,
    contact_pitch: float = 2.0,
) -> tuple[tuple, tuple]:
    """A substrate (``kind='p'``) or n-well tap (``kind='n'``) drawn as one
    long strip spanning ``[x0, x1]`` -- identical technique/citation to
    ``cp_dumpbuf.py``'s own ``_tap_strip()`` (this module's own bias-branch
    rows, up to 62 um wide for ``MBP``+``MCP``, exceed ``DF.13_LV``/
    ``DF.14_LV``'s 20 um max-distance-to-tap the same way that module's own
    isolated-well row does).
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


# ---------------------------------------------------------------------------
# build()
# ---------------------------------------------------------------------------


@dataclass
class CpArrayLayout:
    canvas: devgen.Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, list[tuple[float, float, float, float]]]
    n_leg_boxes: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    p_leg_boxes: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    n_leg_centers: dict[str, tuple[float, float]] = field(default_factory=dict)
    p_leg_centers: dict[str, tuple[float, float]] = field(default_factory=dict)
    n_side_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    p_side_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    n_bias_ports: dict[str, devgen.MosfetPorts] = field(default_factory=dict)
    p_bias_ports: dict[str, devgen.MosfetPorts] = field(default_factory=dict)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def build(outdir: Path | None = None) -> CpArrayLayout:
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package

    ln = cp_leg_n.build()
    lp = cp_leg_p.build()

    n_w, n_h = ln.footprint[2] - ln.footprint[0], ln.footprint[3] - ln.footprint[1]
    p_w, p_h = lp.footprint[2] - lp.footprint[0], lp.footprint[3] - lp.footprint[1]

    # --- N array placement (local, always-on leg at (0, 0)) ---
    offsets_n = leg_offsets(n_w, n_h, LEG_GAP_UM)
    check_common_centroid(offsets_n["base"], [offsets_n[k] for k in LEG_NAMES[1:]])
    n_leg_boxes = {name: _translate_box(ln.footprint, *off) for name, off in offsets_n.items()}
    n_array_bbox = _canvas.bbox_union(n_leg_boxes.values())

    n_bias_row_w = BIAS_DEVICES_N[0].w_um + BIAS_DEVICE_GAP_UM + BIAS_DEVICES_N[1].w_um
    n_side_x1 = max(n_array_bbox[2], n_array_bbox[0] + n_bias_row_w)

    # --- P array placement (local), then shifted clear of the N side ---
    offsets_p_local = leg_offsets(p_w, p_h, LEG_GAP_UM)
    check_common_centroid(offsets_p_local["base"], [offsets_p_local[k] for k in LEG_NAMES[1:]])
    p_local_boxes = {name: _translate_box(lp.footprint, *off) for name, off in offsets_p_local.items()}
    p_local_bbox = _canvas.bbox_union(p_local_boxes.values())

    shift_x = (n_side_x1 + N_P_GAP_UM) - p_local_bbox[0]
    offsets_p = {name: (dx + shift_x, dy) for name, (dx, dy) in offsets_p_local.items()}
    p_leg_boxes = {name: _translate_box(lp.footprint, *off) for name, off in offsets_p.items()}
    p_array_bbox = _canvas.bbox_union(p_leg_boxes.values())

    if p_array_bbox[0] < n_side_x1:
        raise ValueError("cp_array: computed P-array shift does not clear the N side -- placement bug")

    # --- GDS-level placement: build each leg once, place 4 copies per
    # polarity via CellInstArray, then flatten -- see module docstring. ---
    canvas = devgen.Canvas(TOP_CELL)
    with tempfile.TemporaryDirectory() as tmp:
        n_gds = Path(tmp) / "cp_leg_n.gds"
        p_gds = Path(tmp) / "cp_leg_p.gds"
        ln.write_gds(n_gds)
        lp.write_gds(p_gds)
        canvas.layout.read(str(n_gds))
        canvas.layout.read(str(p_gds))
    n_index = canvas.layout.cell_by_name("cp_leg_n")
    p_index = canvas.layout.cell_by_name("cp_leg_p")

    dbu_per_um = int(round(1.0 / canvas.dbu))

    def _place(index, dx: float, dy: float) -> None:
        trans = db.Trans(db.Vector(int(round(dx * dbu_per_um)), int(round(dy * dbu_per_um))))
        canvas.top.insert(db.CellInstArray(index, trans))

    for off in offsets_n.values():
        _place(n_index, *off)
    for off in offsets_p.values():
        _place(p_index, *off)
    canvas.top.flatten(-1, True)

    # --- N bias branch (MBN/MCN), adjacent below the N array ---
    bias_n_y_top = n_array_bbox[1] - BIAS_ROW_GAP_UM
    bias_n_y0 = bias_n_y_top - BIAS_DEVICE_H_UM
    mbn_dev, mcn_dev = BIAS_DEVICES_N
    mbn = devgen.mosfet(canvas, mbn_dev, n_array_bbox[0], bias_n_y0)
    mcn = devgen.mosfet(canvas, mcn_dev, mbn.x1 + BIAS_DEVICE_GAP_UM, bias_n_y0)
    _diode_connect(canvas, mbn.gate_pad, mbn.top_pad)
    _diode_connect(canvas, mcn.gate_pad, mcn.top_pad)
    n_sub_tap_y = bias_n_y0 - devgen.TAP_GAP_UM - devgen.TAP_SIZE_UM / 2.0
    n_sub_box, n_sub_pad = _tap_strip(canvas, "p", mbn.x0, mcn.x1, n_sub_tap_y, "VSS")

    n_bias_boxes = [(mbn.x0, mbn.y0, mbn.x1, mbn.y3), (mcn.x0, mcn.y0, mcn.x1, mcn.y3), n_sub_box]
    n_side_bbox = _canvas.bbox_union(list(n_leg_boxes.values()) + n_bias_boxes)

    # --- P bias branch (MBP/MCP), adjacent below the P array ---
    bias_p_y_top = p_array_bbox[1] - BIAS_ROW_GAP_UM
    bias_p_y0 = bias_p_y_top - BIAS_DEVICE_H_UM
    mbp_dev, mcp_dev = BIAS_DEVICES_P
    mbp = devgen.mosfet(canvas, mbp_dev, p_array_bbox[0], bias_p_y0)
    mcp = devgen.mosfet(canvas, mcp_dev, mbp.x1 + BIAS_DEVICE_GAP_UM, bias_p_y0)
    _diode_connect(canvas, mbp.gate_pad, mbp.top_pad)
    _diode_connect(canvas, mcp.gate_pad, mcp.top_pad)
    p_tap_y = bias_p_y0 + BIAS_DEVICE_H_UM + devgen.TAP_GAP_UM + devgen.TAP_SIZE_UM / 2.0
    p_tap_box, p_tap_pad = _tap_strip(canvas, "n", mbp.x0, mcp.x1, p_tap_y, "VDD")
    p_nwell_box = (
        min(mbp.x0, p_tap_box[0]) - devgen.NWELL_MARGIN_UM,
        min(mbp.y0, p_tap_box[1]) - devgen.NWELL_MARGIN_UM,
        max(mcp.x1, p_tap_box[2]) + devgen.NWELL_MARGIN_UM,
        max(mbp.y3, mcp.y3, p_tap_box[3]) + devgen.NWELL_MARGIN_UM,
    )
    canvas.rect("nwell", *p_nwell_box)

    p_bias_boxes = [(mbp.x0, mbp.y0, mbp.x1, mbp.y3), (mcp.x0, mcp.y0, mcp.x1, mcp.y3), p_nwell_box]
    p_side_bbox = _canvas.bbox_union(list(p_leg_boxes.values()) + p_bias_boxes)

    if boxes_overlap(n_side_bbox, p_side_bbox):
        raise ValueError("cp_array: N-side and P-side bounding boxes overlap -- placement invariant violated")
    for leg_box in n_leg_boxes.values():
        if boxes_overlap(leg_box, (mbn.x0, mbn.y0, mbn.x1, mbn.y3)) or boxes_overlap(leg_box, (mcn.x0, mcn.y0, mcn.x1, mcn.y3)):
            raise ValueError("cp_array: N bias branch overlaps a leg -- must be adjacent, not inside")
    for leg_box in p_leg_boxes.values():
        if boxes_overlap(leg_box, (mbp.x0, mbp.y0, mbp.x1, mbp.y3)) or boxes_overlap(leg_box, (mcp.x0, mcp.y0, mcp.x1, mcp.y3)):
            raise ValueError("cp_array: P bias branch overlaps a leg -- must be adjacent, not inside")

    # --- gather every net's own pad list (leg pins, per this module's own
    # N_NET_MAP/P_NET_MAP, plus the bias branch's own pads) ---
    n_nets: dict[str, list[tuple[float, float, float, float]]] = {}

    def _add_n(net: str, pad: tuple[float, float, float, float]) -> None:
        n_nets.setdefault(net, []).append(pad)

    for name, (dx, dy) in offsets_n.items():
        net_map = N_NET_MAP[name]
        for local_net, pad in ln.pins.items():
            _add_n(net_map[local_net], _translate_box(pad, dx, dy))

    _add_n("IBN", mbn.gate_pad)
    _add_n("VSS", mbn.bottom_pad)
    _add_n("ICN", mcn.gate_pad)
    _add_n("VSS", mcn.bottom_pad)
    _add_n("VSS", n_sub_pad)

    p_nets: dict[str, list[tuple[float, float, float, float]]] = {}

    def _add_p(net: str, pad: tuple[float, float, float, float]) -> None:
        p_nets.setdefault(net, []).append(pad)

    for name, (dx, dy) in offsets_p.items():
        net_map = P_NET_MAP[name]
        for local_net, pad in lp.pins.items():
            _add_p(net_map[local_net], _translate_box(pad, dx, dy))

    _add_p("IBP", mbp.gate_pad)
    _add_p("VDD", mbp.bottom_pad)
    _add_p("ICP", mcp.gate_pad)
    _add_p("VDD", mcp.bottom_pad)
    _add_p("VDD", p_tap_pad)

    # --- mesh-route every net, each in its own side's own channel above
    # that side's own topmost drawn edge, decluttered so no two risers on
    # one side ever land closer than RISER_MIN_PITCH_UM apart in X (see
    # module docstring, "MESH ROUTING", and declutter_riser_x()'s own
    # docstring) -- and promote each as a top-level pin (canvas.pin() draws
    # no shape of its own, see _canvas.py's docstring, so this composes
    # cleanly with the pad(s) routing already placed). ---
    n_tracks = _route_side(canvas, n_nets, n_side_bbox)
    p_tracks = _route_side(canvas, p_nets, p_side_bbox)

    n_leg_centers = {name: box_center(box) for name, box in n_leg_boxes.items()}
    p_leg_centers = {name: box_center(box) for name, box in p_leg_boxes.items()}

    footprint = (
        min(n_side_bbox[0], p_side_bbox[0]),
        min(n_side_bbox[1], p_side_bbox[1]),
        max(n_side_bbox[2], p_side_bbox[2]),
        max(n_tracks._next_y, p_tracks._next_y, n_side_bbox[3], p_side_bbox[3]),  # noqa: SLF001
    )

    layout = CpArrayLayout(
        canvas=canvas,
        footprint=footprint,
        pins=canvas.pins,
        n_leg_boxes=n_leg_boxes,
        p_leg_boxes=p_leg_boxes,
        n_leg_centers=n_leg_centers,
        p_leg_centers=p_leg_centers,
        n_side_bbox=n_side_bbox,
        p_side_bbox=p_side_bbox,
        n_bias_ports={"MBN": mbn, "MCN": mcn},
        p_bias_ports={"MBP": mbp, "MCP": mcp},
    )
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "cp-array-proof" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"N array leg centres: {layout.n_leg_centers}")
    print(f"P array leg centres: {layout.p_leg_centers}")
    print(f"N side bbox: {layout.n_side_bbox}")
    print(f"P side bbox: {layout.p_side_bbox}")
    print(f"pins: {sorted(layout.pins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
