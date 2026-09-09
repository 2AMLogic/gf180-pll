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

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import ClassVar, Iterable, Iterator

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
# never happen regardless of how wide any one net's bus runs.
#
# What that safety argument does NOT cover -- and issue #322 found landed in
# 114 real cross-net Metal3 overlaps, 75 of them VDD/VSS -- is riser-to-riser:
# two risers on the same layer at the same x DO short, and mosfet()'s own S/D
# pad x is a pure function of the device's own x0/x3 (not of which net it
# carries), so a PMOS row and NMOS row instance drawn at the same x0 (every
# inv/nand2/schmitt column in this package) puts two different nets' pads at
# the exact same x. Every riser then runs the *full* pad-to-track_y span, so
# those two risers' Y ranges overlap almost everywhere (track_y always sits
# above the whole block). route_net()/_riser() below fix this with RiserLanes:
# a Metal3 riser only keeps its own pad's natural x if that clears every
# *other* riser already placed anywhere in the same build; otherwise it moves
# to the nearest clear lane. See RiserLanes' own docstring for why a simpler
# fixed per-row shift was tried and rejected. ---
VIA1_SIZE_UM = 0.26  # V1.1 min/max
VIA2_SIZE_UM = 0.26  # V2.1 min/max
VIA_ENCLOSURE_UM = 0.09  # V1.3a/V2.3b min is ~0 um; headroom for the enclosing metal pad
METAL2_WIRE_WIDTH_UM = 0.34  # > M2.1's 0.28 min
METAL3_WIRE_WIDTH_UM = 0.34  # > M3.1's 0.28 min
METAL2_TRACK_PITCH_UM = 0.75  # (pitch - width) = 0.41 > M2.2a's 0.28 min, between two tracks
#: Two Metal3 risers whose x differs by this amount clear M3.2a's 0.28 um
#: min Metal3 spacing with headroom: 0.7 - METAL3_WIRE_WIDTH_UM(0.34) = 0.36
#: > 0.28. See RiserLanes (issue #322).
ROW_LANE_OFFSET_UM = 0.7
#: A Metal2 jog wire (RiserLanes, issue #322) is ``METAL2_WIRE_WIDTH_UM``
#: wide, and another riser's own Via1/Via2 landing square extends roughly
#: ``VIA2_SIZE_UM/2 + VIA_ENCLOSURE_UM`` beyond its own y_pad/track_y in
#: every direction (see ``_riser()``) -- both shapes have real width, not
#: just the point at their own y. This is that headroom, added to both ends
#: of a placed riser's [y_pad, track_y] range before checking whether a new
#: jog's height falls inside it.
_JOG_Y_MARGIN_UM = METAL2_WIRE_WIDTH_UM / 2.0 + VIA2_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM
#: Numerical-precision-only headroom added to *each* of two compared Metal2
#: shapes (``RiserLanes._metal2_boxes()``) -- this class's job is only to
#: rule out a genuine same-layer *overlap* (the electrical short issue #322
#: reports), the same strict-overlap test ``checks.shorted_pairs()`` runs
#: as this fix's own ground truth, not to additionally re-derive M2.2a's
#: full DRC minimum spacing for a router that never ran DRC in the first
#: place. An earlier version used a much larger, DRC-sized margin here and
#: it made real, already-DRC-clean geometry in ``inv``'s own dense column
#: (see ``layout/evidence/lock-detector-layout/``) look unplaceable, since
#: some already-legal pad pairs in this design sit closer together than
#: that margin allowed. A full KLayout DRC pass over the fixed GDS (not run
#: by this pure-Python model) remains the authoritative spacing signoff,
#: same as before this fix.
_M2_SPACING_HALF_UM = 1e-6
#: When a riser has to move lanes, ``RiserLanes._safe_jog_height()`` starts
#: searching for a safe jog height this far *above* its own pad -- 0 means
#: "try the pad's own exact height first". A riser's own Via1 landing at
#: that exact height is always same-net-exempt (see ``_metal2_apparatus_safe``),
#: so starting at 0 costs nothing; a nonzero value only shrinks the search
#: space, and (see issue #322's PR) *any* nonzero base forces every moved
#: riser's own vertical stub through whatever height band that base value
#: picks, with no way to search around an obstacle that happens to sit
#: there -- exactly the failure this fix's own first attempt hit in
#: ``nand2``'s ``VDD``/``Y`` pair.
JOG_HEIGHT_BASE_UM = 0.0
#: Two different nets that both need to move lanes from the exact same row
#: height (every pad sharing one row's own characteristic y -- e.g. every
#: PMOS-row source in a design this wide) get *different* jog heights,
#: staggered by this much, so two same-height Metal2 jog wires can never
#: collide just because they both needed to travel past a shared, densely
#: packed stretch of pads. > METAL2_WIRE_WIDTH_UM so two staggered jogs'
#: own Y half-widths never touch.
JOG_HEIGHT_STEP_UM = 0.5

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

    @contextmanager
    def net(self, name: str) -> Iterator[None]:
        """No-op on the real (KLayout-backed) canvas -- drawing is unaffected.

        ``checks.RecordingCanvas`` overrides this to actually tag every
        Metal1/Metal2/Metal3 shape drawn inside the ``with`` block with
        ``name``, which is what its short/open checks (issue #322) run on.
        Every metal-drawing call below in this module runs inside a
        ``with canvas.net(some_net): ...`` block for exactly that reason,
        even though it costs nothing here.
        """
        yield

    def via(self, net: str, kind: str, x: float, y: float) -> None:
        """No-op on the real canvas; ``checks.RecordingCanvas`` records it.

        Marks a layer transition (``kind`` is ``"via1"`` or ``"via2"``) for
        ``net`` at ``(x, y)`` -- the input ``checks.disconnected_nets()``
        needs to know two same-net shapes on adjacent layers are actually
        connected, not just touching by coincidence.
        """


class RiserLanes:
    """Hands out a Metal3 riser x lane clear of every riser already placed.

    A row-sign heuristic (shift every NMOS-row riser left by a fixed amount)
    was tried first and is *not* enough: it reliably separates the specific
    PMOS-row/NMOS-row pad pair issue #322 reported, but a flat, unconditional
    shift can just as easily slide one net's riser on top of some other,
    unrelated net's *unshifted* riser a fixed distance away -- observed
    directly building this package's own ``nand2``/``schmitt``/``xor2``
    sub-cells during this fix (a shifted gate-net riser landing on an
    adjacent, unshifted supply riser).

    A second attempt -- move a colliding riser to the nearest lane that
    clears every *other* riser's x by ``ROW_LANE_OFFSET_UM``, connected by a
    Metal2 jog at its own ``y_pad`` -- is also not enough on its own: the
    jog itself is a wide horizontal Metal2 run, and if it has to travel more
    than one lane pitch to find a free slot (dense columns, e.g. ``inv``'s
    own ``VDD``/``VSS``/``Y``/``A`` all within ~2 um of each other, force
    exactly this) it can cross straight through some *other*, unrelated
    net's own Via1/Via2 landing square that happens to sit between the old
    and new x -- also observed directly during this fix.

    A third attempt -- track each placed riser's full vertical extent
    (``y_pad`` to ``track_y``), not just its x, so two risers only need x
    separation where their Y ranges actually overlap, plus an explicit
    search over the jog's *height* (not just its target x) whenever a fixed
    per-row-height offset collided with some other, independently-staggered
    row -- is still not enough, for a reason specific to routing the lane
    change on **Metal2**: a moved riser's Via1 landing stays at its own
    natural x on the way up, so its vertical Metal2 stub is *pinned* to that
    x and can only grow taller, never sideways, to clear an obstacle. If
    some other, already-placed riser's own jog wire is wide enough to pass
    directly over that natural x at some fixed height (routine once more
    than a couple of nets in a dense row have already had to move -- see
    issue #322's PR building ``xor2``'s own ``XN2``), the stub is blocked at
    that height *permanently*: every taller jog height still has to pass
    through it on the way up, so no amount of height search ever escapes it,
    and every candidate lane hits the same wall since the stub's x never
    changes.

    The fix implemented below moves the lane change itself onto **Metal1**
    instead: a short vertical stub from the pad's own ``(x, y_pad)`` up to
    ``x``'s own jog height, then a short horizontal jog from ``x`` to the
    chosen lane, both still on Metal1, *before* Via1 ever runs (see
    ``_riser()``). This package draws Metal1 nowhere else as anything wider
    than one device pad, so the only things a Metal1 stub/jog can ever cross
    are some other net's own pad or its own Metal1 stub/jog -- never a
    Metal2 jog wire (different layer, no via, not a short -- the same
    top-of-file argument that makes a Metal3 riser safe to cross an
    unrelated Metal2 bus), so the permanent-block failure mode above cannot
    happen here. Via1 and Via2 are now co-located (both land at the chosen
    lane, at the chosen jog height) rather than split across two x
    positions, so the existing Metal3-column pitch check (see
    ``_overlapping_x_clear()``) already keeps them apart -- Metal1 is the
    only layer this class still needs its own, separate check for (see
    ``_metal1_apparatus_safe()``).

    One instance must be shared across every net routed in a build (see
    ``route_all_nets()``), and every riser in the whole build should be
    placed in one shared pass ordered by natural x (not net-by-net) --
    ``route_all_nets()`` does this -- so that a densely-packed net rarely
    needs more than a small nudge past its immediate neighbours, rather
    than a long jump past unrelated risers this class then has to
    separately prove safe.

    A riser's pad sits at its own natural x/y and *never* moves -- so a net
    placed early can pick a lane that looks clear against every
    *already-placed* riser and still route its own Metal1 stub/jog straight
    through some *later* net's pad, once that net is finally placed at its
    own, fixed, already-known position (observed directly building
    ``nand2``: ``Y`` moved to a lane 0.04 um from ``VDD``'s own,
    still-unplaced, natural pad x, since nothing yet considered pads that
    hadn't been routed yet). Every riser's natural x/y is known before
    routing starts at all (``route_all_nets()`` builds the full group list
    up front), so ``groups`` -- the complete set, not just what's been
    placed so far -- is required at construction and checked the same way a
    placed riser's own pad is (see ``_metal1_apparatus_safe()``).
    """

    #: How many of a riser's own most-recent lanes ``resolve_conflicts()``
    #: remembers and excludes -- enough to break a two-riser oscillation
    #: (see its own docstring), short enough that a lane freed up by some
    #: other riser's later move can still be tried again.
    _AVOID_HISTORY: ClassVar[int] = 4

    def __init__(
        self,
        groups: Iterable[tuple[str, float, float, float, float, float]],
        pitch: float = ROW_LANE_OFFSET_UM,
        max_tries: int = 24,
        max_height_tries: int = 24,
    ) -> None:
        self._pitch = pitch
        self._max_tries = max_tries
        self._max_height_tries = max_height_tries
        #: (net, natural_x, assigned_x, y_pad, track_y, jog_y, half_w,
        #: half_h) for every riser placed so far. jog_y == y_pad (no
        #: separate jog height) when assigned_x == natural_x -- no jog is
        #: ever drawn in that case. half_w/half_h are this riser's own pad
        #: footprint half-extent (see ``_riser_groups()``).
        self._placed: list[tuple[str, float, float, float, float, float, float, float]] = []
        #: (net, natural_x, y_pad, half_w, half_h) for *every* riser in the
        #: whole build, known up front -- every one of these pads is a fixed
        #: fact regardless of processing order (see this class's own
        #: docstring). Used only for the Metal1 pad-footprint check, since
        #: nothing else about an unplaced riser (its eventual lane, its jog
        #: height) is known yet.
        self._future_pads: list[tuple[str, float, float, float, float]] = [
            (net, x, y_pad, half_w, half_h) for net, x, y_pad, _t, half_w, half_h in groups
        ]

    def _safe_jog_height(
        self,
        net: str,
        natural_x: float,
        cand_x: float,
        y_pad: float,
        half_w: float,
        half_h: float,
        max_height_tries: int | None = None,
    ) -> float | None:
        """The nearest jog height to ``y_pad`` (stepping by
        ``JOG_HEIGHT_STEP_UM``, tried *both* above and below ``y_pad``)
        whose *entire* Metal1 apparatus (see ``_metal1_boxes()``) clears
        every already-placed riser's own, or ``None`` if none of the first
        ``max_height_tries`` (defaulting to ``self._max_height_tries``)
        steps in either direction do.

        Both directions matter because the vertical stub this riser draws
        (see ``_riser()``) always starts *at* ``y_pad`` and only ever grows
        towards whichever ``jog_y`` is chosen -- so once some fixed
        obstacle at this riser's own natural x sits *between* ``y_pad`` and
        a candidate height, no larger height in that same direction can
        ever un-cross it (the stub's far end only moves further away, never
        around). Only a genuinely different height, on the *other* side of
        ``y_pad``, or a shorter reach on the same side, can. Trying only
        upward (this fix's own first attempt) hit exactly this wall
        building ``xor2``'s own ``XN1``/NMOS instance: escalating upward
        could clear one nearby obstacle only by first permanently crossing
        another sitting closer to ``y_pad`` -- going downward instead (nothing
        else routes below the lowest row) cleared both at once.
        """
        max_height_tries = self._max_height_tries if max_height_tries is None else max_height_tries
        for j in range(max_height_tries):
            for jog_y in (
                y_pad + JOG_HEIGHT_BASE_UM + j * JOG_HEIGHT_STEP_UM,
                y_pad - JOG_HEIGHT_BASE_UM - j * JOG_HEIGHT_STEP_UM,
            ):
                if self._metal1_apparatus_safe(net, natural_x, cand_x, y_pad, jog_y, half_w, half_h):
                    return jog_y
        return None

    @staticmethod
    def _metal1_boxes(
        nat_x: float, asg_x: float, y_pad: float, jog_y: float, half_w: float, half_h: float
    ) -> list[tuple[float, float, float, float]]:
        """Every Metal1 box a riser's own pad-to-lane apparatus occupies.

        Always includes the pad footprint itself (every riser has one,
        whether or not it moved lanes -- drawn by ``mosfet()``/
        ``tap_strip()`` before ``_riser()`` ever runs; ``half_w``/``half_h``
        is that real, drawn pad's own half-extent -- see
        ``_riser_groups()`` -- not a fixed proxy, since some of this
        package's own S/D pads are far wider than a single Via1 landing
        (issue #322: assuming every pad was via-sized underestimated a real
        collision and let a short slip past this exact check building
        ``nand2``), and the Via1/Via2 landing's own Metal1 component (always
        at ``(asg_x, jog_y)`` -- see ``_riser()``): the Metal3-column pitch
        check in ``_overlapping_x_clear()`` only rules out two *lanes*
        landing too close together, not some *other* riser's Metal1
        stub/jog (which lives at that riser's own natural x, unrelated to
        any lane) sweeping past this landing's Metal1 side on its way
        somewhere else (also observed directly building ``nand2``: ``Y``'s
        own stub crossed straight through ``A``'s Via1 landing). If it moved
        (``asg_x != nat_x``), also its vertical stub (``nat_x``, from
        ``y_pad`` up to ``jog_y``) and its horizontal jog wire (at height
        ``jog_y``, from ``nat_x`` to ``asg_x``) -- see ``_riser()``.
        Deliberately excludes the Via2-top landing at ``track_y`` and the
        final Metal2 bus -- neither is Metal1.

        Every box is sized to the *exact* geometry ``_riser()`` actually
        draws (same formulas), padded by only ``_M2_SPACING_HALF_UM`` --
        half of M1.2a's minimum spacing -- on every side, so two boxes are
        flagged unsafe only when the real shapes they model would be closer
        than the deck allows.
        """
        half_wire = METAL1_WIRE_WIDTH_UM / 2.0
        half_via = VIA1_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM
        s = _M2_SPACING_HALF_UM
        boxes = [
            (nat_x - half_w - s, y_pad - half_h - s, nat_x + half_w + s, y_pad + half_h + s),
            (asg_x - half_via - s, jog_y - half_via - s, asg_x + half_via + s, jog_y + half_via + s),
        ]
        if asg_x != nat_x:
            stub_lo, stub_hi = (y_pad, jog_y) if y_pad <= jog_y else (jog_y, y_pad)
            boxes.append((nat_x - half_wire - s, stub_lo - s, nat_x + half_wire + s, stub_hi + s))  # stub
            jog_lo, jog_hi = (nat_x, asg_x) if nat_x <= asg_x else (asg_x, nat_x)
            boxes.append((jog_lo - s, jog_y - half_wire - s, jog_hi + s, jog_y + half_wire + s))  # jog wire
        return boxes

    @staticmethod
    def _boxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def _metal1_apparatus_safe(
        self, net: str, natural_x: float, cand_x: float, y_pad: float, jog_y: float, half_w: float, half_h: float
    ) -> bool:
        """Would this riser's own Metal1 apparatus (pad footprint, and, if
        it moves, its stub/jog wire -- see ``_metal1_boxes()``) collide with
        any *other* net's Metal1? Checked as plain box overlap in both
        directions (e.g. this riser's own new stub against an earlier
        riser's already-drawn jog wire, not just this riser's jog wire
        against earlier stubs).

        Checked against every *already-placed* riser's full apparatus, and
        separately against every *not yet placed* net's own pad footprint
        (``self._future_pads``, fixed at that net's own natural x/y
        regardless of processing order -- see this class's own docstring):
        a net placed early can otherwise pick a lane that looks clear
        against everything placed so far and still route its own Metal1
        stub/jog straight through some later net's own, already fully
        determined, pad position (observed directly building ``nand2``:
        ``Y`` moved 0.04 um from ``VDD``'s own not-yet-routed pad, back when
        this apparatus was still routed on Metal2).
        """
        my_boxes = self._metal1_boxes(natural_x, cand_x, y_pad, jog_y, half_w, half_h)
        for unet, nat_x, asg_x, uy_pad, _utrack_y, ujog, uhalf_w, uhalf_h in self._placed:
            if unet == net:
                continue  # same net: merging is safe, never a short
            for ob in self._metal1_boxes(nat_x, asg_x, uy_pad, ujog, uhalf_w, uhalf_h):
                for mb in my_boxes:
                    if self._boxes_overlap(mb, ob):
                        return False
        for unet, nat_x, u_y_pad, uhalf_w, uhalf_h in self._future_pads:
            if unet == net:
                continue
            # Only the raw pad footprint is a known, fixed fact for a net
            # that hasn't been placed yet -- _metal1_boxes()'s own Via1/Via2
            # landing box assumes an *unmoved* lane, which is not yet known
            # to be true, so using only boxes[0] here avoids over-rejecting
            # a placement against a landing position that may never exist.
            pad_box = self._metal1_boxes(nat_x, nat_x, u_y_pad, u_y_pad, uhalf_w, uhalf_h)[0]
            for mb in my_boxes:
                if self._boxes_overlap(mb, pad_box):
                    return False
        return True

    def _overlapping_x_clear(self, net: str, cand_x: float, y_pad: float, track_y: float) -> bool:
        """Is ``cand_x`` clear, as a Metal3 lane, of every other net's own
        Metal3 column (and its co-located Via1/Via2 landing, both well
        within one lane pitch of ``cand_x``)? Two columns only collide
        where their Y ranges actually overlap; Metal1 (pad footprints, jog
        wires, ...) is an entirely separate, more precise check -- see
        ``_metal1_apparatus_safe()`` -- since a Metal3 column crossing
        another net's Metal1/Metal2 is a different-layer crossing with no
        via, and so never a short by itself (the same top-of-file argument
        that makes a riser safe to cross an unrelated Metal2 bus).
        """
        lo, hi = min(y_pad, track_y), max(y_pad, track_y)
        for unet, _nat_x, asg_x, uy_pad, utrack_y, _ujog, _uhw, _uhh in self._placed:
            if unet == net:
                continue  # same net: merging is safe, never a short (see _riser_groups())
            ulo, uhi = min(uy_pad, utrack_y), max(uy_pad, utrack_y)
            if not (hi < ulo - 1e-9 or lo > uhi + 1e-9) and abs(cand_x - asg_x) < self._pitch - 1e-9:
                return False
        return True

    def place(
        self,
        net: str,
        x: float,
        y_pad: float,
        track_y: float,
        half_w: float = 0.0,
        half_h: float = 0.0,
        *,
        max_tries: int | None = None,
        max_height_tries: int | None = None,
        avoid_lanes: frozenset[float] = frozenset(),
    ) -> tuple[float, float]:
        """Return ``(assigned_x, jog_y)`` for a riser whose pad-natural x is ``x``.

        ``assigned_x`` is the Metal3 lane to use (equal to ``x`` when no
        move is needed, in which case ``jog_y`` is just ``y_pad`` and
        ``_riser()`` draws no separate jog at all). ``y_pad``/``track_y``
        are this riser's own vertical extent (see ``_riser()``) -- required
        so this instance can tell which other risers are actually a hazard,
        not just which ones happen to exist anywhere in the design.
        ``half_w``/``half_h`` are this riser's own pad's real half-extent
        (see ``_riser_groups()``) -- 0.0 defaults to
        ``RiserLanes._metal1_boxes()``'s own minimum, only safe for callers
        (e.g. this class's own tests) that don't care about the pad's exact
        footprint. ``net`` excludes this riser's *own* net from every
        clearance/jog-safety check -- two of the same net's own risers
        merging (even landing on the exact same lane) is never a short, only
        ``_riser_groups()``'s own merge distance (issue #322) needs it.
        ``max_tries``/``max_height_tries`` override this instance's own
        defaults for just this call -- ``resolve_conflicts()`` uses a much
        larger budget than the initial placement pass (see its own
        docstring for why). ``avoid_lanes`` skips specific candidate lanes
        outright -- also ``resolve_conflicts()`` only, to stop two risers
        oscillating forever between the same two mutually-conflicting lanes
        (observed directly building ``schmitt``).
        """
        max_tries = self._max_tries if max_tries is None else max_tries
        max_height_tries = self._max_height_tries if max_height_tries is None else max_height_tries
        half_w = max(half_w, _MIN_PAD_HALF_UM)
        half_h = max(half_h, _MIN_PAD_HALF_UM)
        if (
            x not in avoid_lanes
            and self._overlapping_x_clear(net, x, y_pad, track_y)
            and self._metal1_apparatus_safe(net, x, x, y_pad, y_pad, half_w, half_h)
        ):
            self._placed.append((net, x, x, y_pad, track_y, y_pad, half_w, half_h))
            return x, y_pad

        for k in range(1, max_tries):
            for cand in (x + k * self._pitch, x - k * self._pitch):
                if cand in avoid_lanes:
                    continue
                if not self._overlapping_x_clear(net, cand, y_pad, track_y):
                    continue
                jog_y = self._safe_jog_height(net, x, cand, y_pad, half_w, half_h, max_height_tries)
                if jog_y is None:
                    continue
                self._placed.append((net, x, cand, y_pad, track_y, jog_y, half_w, half_h))
                return cand, jog_y

        # No (lane, jog height) pair looked safe against everything known
        # so far -- can genuinely happen even for a solvable design, since
        # ``_future_pads`` only knows *other* nets' fixed pad positions, not
        # the dynamic stub/jog geometry they'll eventually choose (observed
        # directly building ``xor2``: ``VDD`` escalated to a jog height
        # that, by coincidence, landed right next to ``XN2``'s own natural x
        # only *after* ``XN2`` needed that exact height to clear a different,
        # unrelated obstacle -- neither net could have anticipated the
        # other's final choice in a single left-to-right pass). Fall back to
        # the nearest Metal3-lane-safe candidate with no lane change at all
        # if possible; `resolve_conflicts()` (called once every riser in the
        # build has an initial placement) re-places whichever side of any
        # resulting Metal1 conflict is easier to move, with full knowledge
        # of everyone's *actual* final geometry -- something no single-pass
        # placement can have.
        for k in range(max_tries):
            for cand in (x,) if k == 0 else (x + k * self._pitch, x - k * self._pitch):
                if cand in avoid_lanes:
                    continue
                if self._overlapping_x_clear(net, cand, y_pad, track_y):
                    self._placed.append((net, x, cand, y_pad, track_y, y_pad, half_w, half_h))
                    return cand, y_pad
        raise ValueError(f"no free Metal3 riser lane near x={x} -- widen ROW_LANE_OFFSET_UM or max_tries")

    def _find_metal1_conflict(self) -> tuple[int, int] | None:
        """``(i, j)`` indices into ``self._placed`` of one pair of risers
        (``i`` placed before ``j``) whose Metal1 apparatus collides, or
        ``None`` if none do.

        ``_future_pads`` (checked by every ``place()`` call) only knows a
        not-yet-placed net's fixed *pad* position, never the dynamic
        stub/jog extent it will eventually choose -- so a riser placed early
        can still end up in genuine conflict with a *later* riser's own
        stub/jog once that later riser is finally placed (observed directly
        building ``nand2``: ``Y``, placed at natural x=2.07 before ``VDD``'s
        own second instance at natural x=2.81, could not have known ``VDD``
        would eventually grow a tall Metal1 stub reaching right through
        ``Y``'s own, already-fixed, jog wire). ``resolve_conflicts()`` uses
        this to re-place both sides of each such conflict with full
        knowledge of every other riser's *actual* final geometry.
        """
        for j in range(1, len(self._placed)):
            net_j, nat_j, asg_j, y_j, _t_j, jog_j, hw_j, hh_j = self._placed[j]
            boxes_j = self._metal1_boxes(nat_j, asg_j, y_j, jog_j, hw_j, hh_j)
            for i in range(j):
                net_i, nat_i, asg_i, y_i, _t_i, jog_i, hw_i, hh_i = self._placed[i]
                if net_i == net_j:
                    continue
                for bi in self._metal1_boxes(nat_i, asg_i, y_i, jog_i, hw_i, hh_i):
                    for bj in boxes_j:
                        if self._boxes_overlap(bi, bj):
                            return i, j
        return None

    def resolve_conflicts(self, max_rounds: int = 32, max_tries: int = 32, max_height_tries: int = 32) -> None:
        """Re-place both sides of any Metal1 conflict (see
        ``_find_metal1_conflict()``), repeatedly, until none remain. Call
        once after every ``place()`` call for a build is done
        (``route_all_nets()`` does this before drawing anything).

        Re-placing only the *later* side of a conflict (this fix's own
        first attempt) can cycle forever: with every *other* riser's
        position unchanged, re-placing the same riser against the same
        ``_placed`` list just finds the same best-effort spot again every
        time (observed directly building ``schmitt``: the same riser
        flagged, popped, and re-placed at an identical position for over
        500 rounds straight). Popping *both* sides of the conflict before
        re-placing either -- the earlier one first, so the later one then
        competes for whatever space it left behind -- helps but is still
        not enough on its own: two risers can settle into a genuine
        2-cycle, each one's own presence being exactly what pushes the
        other back to a lane that re-creates the original conflict
        (observed directly building ``schmitt``: ``P1`` alternating between
        two lanes every other round, forever, as ``VSS`` stayed put). A
        larger per-call search budget alone does not fix either cycle
        (confirmed directly: 512 tries/height-steps just reproduces it
        slower).

        Remembering *every* lane a riser has ever tried and excluding all of
        them forever (this fix's own second attempt) breaks the 2-cycle but
        introduces a worse failure mode on a wider conflict graph (observed
        directly building ``xor2``, ~40 risers): once every nearby lane for
        a busy riser is exhausted, it is forced further and further away,
        which only ever *adds* new obstacles to cross (a farther lane's own
        wider jog), so assigned lanes drift outward without bound and the
        design never actually stabilizes even after hundreds of rounds.
        Remembering only each riser's own last ``_AVOID_HISTORY`` lanes --
        enough to break a short cycle, short enough that a lane doing
        another riser's move might free up gets tried again later -- keeps
        the cycle-breaking property without the runaway drift.
        """
        avoid: dict[tuple[str, float, float], deque[float]] = {}

        def _avoid_and_place(entry: tuple[str, float, float, float, float, float, float, float]) -> None:
            net, nat_x, asg_x, y_pad, track_y, _jog_y, half_w, half_h = entry
            key = (net, nat_x, y_pad)
            history = avoid.setdefault(key, deque(maxlen=self._AVOID_HISTORY))
            history.append(asg_x)
            self.place(
                net,
                nat_x,
                y_pad,
                track_y,
                half_w,
                half_h,
                max_tries=max_tries,
                max_height_tries=max_height_tries,
                avoid_lanes=frozenset(history),
            )

        for _ in range(max_rounds):
            pair = self._find_metal1_conflict()
            if pair is None:
                return
            i, j = pair
            # Pop the later index first so popping the earlier one doesn't
            # shift it out from under us.
            entry_j = self._placed.pop(j)
            entry_i = self._placed.pop(i)
            _avoid_and_place(entry_i)
            _avoid_and_place(entry_j)
        raise ValueError("could not resolve every Metal1 conflict after max_rounds -- widen ROW_LANE_OFFSET_UM or max_rounds")


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
    with canvas.net(fet.g):
        canvas.rect("metal1", *gate_pad)

    # --- S/D contacts: each terminal's row hugs the outer (away-from-gate)
    # edge, so CO.7's 0.15 um contact-to-gate space is satisfied by
    # SD_OVERHANG_UM (0.55) - CONTACT_ROW_MARGIN_UM (0.1) - CONTACT_SIZE_UM (0.22). ---
    def _terminal_pad(net: str, x_outer_edge: float, *, outer_is_min: bool) -> tuple[float, float, float, float]:
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
        with canvas.net(net):
            canvas.rect("metal1", pad_x0, pad_y0, pad_x1, pad_y1)
        return (pad_x0, pad_y0, pad_x1, pad_y1)

    left_pad = _terminal_pad(fet.s, x0, outer_is_min=True)
    right_pad = _terminal_pad(fet.d, x3, outer_is_min=False)

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
    with canvas.net(net):
        canvas.rect("metal1", *pad)
    canvas.pin(net, *pad)
    return (x0, y0, x1, y1), pad


# Draw one square via + its enclosing metal landing pad -- shared with every
# other ``layout/pll_top/*`` submodule (issue #332, ``_canvas._via_square()``).
_via_square = _canvas._via_square


def _riser(
    canvas: Canvas,
    net: str,
    x: float,
    y_pad: float,
    track_y: float,
    *,
    lane_dx: float = 0.0,
    jog_y: float | None = None,
) -> None:
    """Metal1 pad -> [Metal1 stub+jog] -> Via1 -> Metal2 landing -> Via2 -> Metal3 riser -> Via2 -> Metal2 bus landing.

    The long vertical run (from ``jog_y`` to ``track_y``) is drawn entirely
    on Metal3 -- a layer this package never uses for anything else -- so it
    can freely cross any other net's Metal2 bus without a via (no via, no
    connection, no short: metal on two different layers overlapping with no
    via between them is not a DRC violation in this deck).

    ``lane_dx`` (see ``RiserLanes``, issue #322) shifts everything from
    Via1 upward by that amount in x. Reaching the new x/height happens
    entirely on **Metal1** (a short vertical stub from the pad at ``(x,
    y_pad)`` up to ``(x, jog_y)``, then a short horizontal jog from ``x``
    to ``x + lane_dx``) *before* Via1 ever runs -- not Metal2. This module
    otherwise never draws a Metal1 shape wider than one device pad, so a
    Metal1 jog/stub can only ever collide with some other net's own pad or
    stub, never with the far more common hazard this fix (see
    ``RiserLanes``) originally hit doing this same move on Metal2: any
    other net's own *Metal2* jog wire is a different-layer crossing here,
    not a short, and (unlike a Metal2 jog immediately above the row, where
    most of this package's own nets already have their busiest Metal2
    activity) a tall Metal1 stub can rise as high as it needs to clear a
    crowded row without ever risking that crossing.

    ``jog_y`` (defaults to ``y_pad``, i.e. no separate jog height -- only
    meaningful when ``lane_dx`` is nonzero) is the height ``RiserLanes``
    assigned this riser's jog at, verified clear of every other riser's own
    Metal1 -- see ``RiserLanes.place()``.

    **Why this is not ``_canvas._riser()``** (issue #332's shared helper,
    which this module *did* call until issue #322). Two reasons, both about
    the shared helper's other callers rather than about this module:

    * The Metal1 stub/jog above is only safe under a *module-local*
      invariant -- "this package draws Metal1 nowhere else as anything
      wider than one device pad", which is what makes a Metal1 jog's only
      possible collision another riser's own pad/stub (a hazard
      ``RiserLanes`` then models exhaustively). That invariant does not
      hold for the shared helper's other caller:
      ``divider_chain/devgen.py`` routes long Metal1 wires of its own
      (``v_wire()``/``h_wire()``, plus its bypass-lane columns). Exposing
      ``lane_dx``/``jog_y`` on the shared helper would advertise, to a
      caller where the safety argument is false, a mechanism whose only
      proof is this module's. Cross-net metal that merges with no via is
      invisible to the DRC deck (exactly how issue #322's 114 overlaps
      survived), so "advertised but unproven" here means "silently
      shorted, undetected" there.
    * The lane change is inseparable from ``RiserLanes``' placement state
      and from this module's ``Canvas.net()``/``Canvas.via()`` net-tagging
      (which ``checks.py``'s short/open model is built on). Neither exists
      in the shared module, and neither is meaningful without the other.

    This follows the precedent ``_canvas.py``'s own module docstring
    already records for ``pfd_cp/cp_dumpbuf.py``'s ``_riser()``: a riser
    that is *structurally* different from the shared one stays local and
    says why. Everything about this function that is **not** structurally
    different does still come from the shared module -- ``_via_square()``,
    ``_contact_positions()`` and ``bbox_union()`` above are all
    ``_canvas``'s, so the divergence is confined to this one function.
    """
    if jog_y is None:
        jog_y = y_pad
    x_top = x + lane_dx
    with canvas.net(net):
        if lane_dx:
            # A short Metal1 stub from the pad (x, y_pad) up to this
            # riser's own jog height, then the horizontal jog itself, all
            # still on Metal1 -- same net as the pad it grows out of, so
            # merging is never a short, and safely below Via1 (drawn next).
            half_stub = METAL1_WIRE_WIDTH_UM / 2.0
            canvas.rect("metal1", x - half_stub, min(y_pad, jog_y), x + half_stub, max(y_pad, jog_y))
            half_jog = METAL1_WIRE_WIDTH_UM / 2.0
            jog_lo, jog_hi = (x, x_top) if x <= x_top else (x_top, x)
            canvas.rect("metal1", jog_lo, jog_y - half_jog, jog_hi, jog_y + half_jog)

        half_m2 = _via_square(canvas, "via1", x_top, jog_y, VIA1_SIZE_UM, VIA_ENCLOSURE_UM)
        canvas.rect("metal2", x_top - half_m2, jog_y - half_m2, x_top + half_m2, jog_y + half_m2)
        canvas.rect("metal1", x_top - half_m2, jog_y - half_m2, x_top + half_m2, jog_y + half_m2)
        canvas.via(net, "via1", x_top, jog_y)

        half_m3 = _via_square(canvas, "via2", x_top, jog_y, VIA2_SIZE_UM, VIA_ENCLOSURE_UM)
        canvas.rect("metal3", x_top - half_m3, jog_y - half_m3, x_top + half_m3, jog_y + half_m3)
        # Via1's own Metal2 landing (just above) already sits at this exact
        # (x_top, jog_y) point -- Via1 and Via2 are always co-located now
        # that the lane change happens on Metal1 before Via1 ever runs, so
        # no separate Metal2 enclosure is needed here.
        canvas.via(net, "via2", x_top, jog_y)

        half_w = METAL3_WIRE_WIDTH_UM / 2.0
        canvas.rect("metal3", x_top - half_w, min(jog_y, track_y), x_top + half_w, max(jog_y, track_y))

        half_m3_top = _via_square(canvas, "via2", x_top, track_y, VIA2_SIZE_UM, VIA_ENCLOSURE_UM)
        canvas.rect("metal3", x_top - half_m3_top, track_y - half_m3_top, x_top + half_m3_top, track_y + half_m3_top)
        canvas.rect("metal2", x_top - half_m3_top, track_y - half_m3_top, x_top + half_m3_top, track_y + half_m3_top)
        canvas.via(net, "via2", x_top, track_y)


#: A pad box smaller than this (in either dimension) is treated as a point
#: for ``RiserLanes``' own Metal1 pad-footprint hazard model -- every real
#: pad this package draws is at least this big (``mosfet()``'s narrowest
#: terminal pad, ``tap_strip()``'s own strip), so this only ever *grows* the
#: hazard box, never shrinks it below a real pad's own size.
_MIN_PAD_HALF_UM = VIA1_SIZE_UM / 2.0 + VIA_ENCLOSURE_UM


def _riser_groups(pads: Iterable[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    """Merge same-net pads within one riser-width of each other in X *and* Y.

    Two of *this same net's* own pads landing within one riser-width of each
    other (e.g. a device's own S/D pad and a nearby periodic well/substrate
    tap -- see ``build.py``'s ``_finish()``) is not a short (same net), but
    each would still draw its own overlapping Via1/Via2 stack -- and two
    *overlapping-but-not-identical* squares merge into a polygon whose edges
    are no longer exactly the legal via size, which *is* a real V1.1/V2.1
    violation. So close pads are snapped onto a single riser position
    (average x/y) first (grid = one riser pitch).

    Requiring closeness in Y too, not just X (issue #322), matters for a
    gate net's own P-row and N-row pads (e.g. ``inv``'s own ``a``): both
    land at the *identical* x (``mosfet()``'s gate x only depends on the
    shared x0/l, not the row) but several microns apart in Y -- merging them
    anyway averaged their y into one point that could, after this fix's own
    x-lane assignment moved the group away from a same-x collision,
    coincidentally land inside some unrelated net's Via1 landing square at a
    *different* y that neither original pad was ever near. Two risers with
    real Y separation never risked an overlapping-via square in the first
    place, so there was never a reason to merge them.

    Returns ``(gx, gy, half_w, half_h)`` -- the merged riser position plus
    the *largest* half-width/half-height of any pad folded into it, so
    ``RiserLanes`` can build an accurate Metal1 footprint for it (issue
    #322: some of this package's own S/D pads are far wider than a single
    Via1 landing, e.g. ``nand2``'s own wide devices -- assuming every pad is
    via-sized underestimated a real collision and let a short slip past this
    exact check).
    """
    grid = METAL2_TRACK_PITCH_UM
    merged: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
    for pad in pads:
        gx, gy = pad_center(pad)
        merged.setdefault((round(gx / grid), round(gy / grid)), []).append(pad)
    groups = []
    for group in merged.values():
        centers = [pad_center(p) for p in group]
        gx = sum(c[0] for c in centers) / len(centers)
        gy = sum(c[1] for c in centers) / len(centers)
        half_w = max(_MIN_PAD_HALF_UM, *((p[2] - p[0]) / 2.0 for p in group))
        half_h = max(_MIN_PAD_HALF_UM, *((p[3] - p[1]) / 2.0 for p in group))
        groups.append((gx, gy, half_w, half_h))
    return groups


def route_all_nets(
    canvas: Canvas,
    nets: dict[str, list[tuple[float, float, float, float]]],
    tracks: "NetTracks",
    width: float = METAL2_WIRE_WIDTH_UM,
) -> None:
    """Tie every net's pads to its own Metal2 bus at ``tracks.get(net)``.

    Every long-haul connection in this package's cells rides a dedicated
    Metal3 riser (see ``_riser()``) up/down to its own Metal2 bus -- never a
    same-layer Metal1 or Metal2 run spanning past a single pad -- so two
    unrelated nets can never risk a same-layer crossing/short regardless of
    placement order or how far apart their pads are. ``track_y`` (assigned
    by ``NetTracks``, unique per net) is what keeps two different nets'
    *Metal2 buses* apart; ``RiserLanes`` (issue #322) is what keeps their
    *Metal3 risers* apart, since a riser's own x is otherwise a pure
    function of its pad's position, not of which net it carries -- two
    different nets' pads routinely land at the exact same natural x (every
    ``inv``/``nand2``/``schmitt`` column in this package does).

    Every net's riser groups are placed in **one shared pass, ordered by
    natural x across every net at once** -- not net-by-net -- and this
    matters: processing net-by-net, a net whose pads happen to be
    surrounded on both sides by already-placed neighbours can be forced into
    a large jump that crosses someone else's riser along the way (observed
    directly while building this package's own dense columns, e.g. ``inv``'s
    ``VDD``/``VSS``/``Y``/``A`` within about 2 um of each other). Processing
    in ascending natural-x order instead means each riser only ever has to
    step past its *immediate* neighbours, so ``RiserLanes`` only needs a
    small, provably jog-safe move rather than a long one -- confirmed by
    hand-tracing ``inv``'s own four nets through this exact algorithm during
    this fix.
    """
    per_net_track_y: dict[str, float] = {net: tracks.get(net) for net in nets}
    #: (x, net, y_pad, track_y, half_w, half_h) for every riser to place.
    all_groups: list[tuple[float, str, float, float, float, float]] = []
    for net, pads in nets.items():
        track_y = per_net_track_y[net]
        for gx, gy, half_w, half_h in _riser_groups(pads):
            all_groups.append((gx, net, gy, track_y, half_w, half_h))
    all_groups.sort(key=lambda g: g[0])

    lanes = RiserLanes((net, gx, gy, track_y, half_w, half_h) for gx, net, gy, track_y, half_w, half_h in all_groups)

    # Placement first, drawing second: a riser placed early only knows about
    # every *other* net's fixed pad position (RiserLanes' own "future pads"
    # check), never a later net's own eventual, dynamically-sized Metal1
    # stub/jog -- resolve_conflicts() re-places either side of any residual
    # conflict once every riser's *actual* final geometry is known, which
    # only makes sense once every riser has been placed at least once.
    results: dict[tuple[str, float, float], tuple[float, float]] = {}
    for gx, net, gy, track_y, half_w, half_h in all_groups:
        x_top, jog_y = lanes.place(net, gx, gy, track_y, half_w, half_h)
        results[(net, gx, gy)] = (x_top, jog_y)
    lanes.resolve_conflicts()
    for net, nat_x, asg_x, y_pad, _track_y, jog_y, _hw, _hh in lanes._placed:
        results[(net, nat_x, y_pad)] = (asg_x, jog_y)

    riser_top_xs: dict[str, list[float]] = {net: [] for net in nets}
    for gx, net, gy, track_y, _half_w, _half_h in all_groups:
        x_top, jog_y = results[(net, gx, gy)]
        _riser(canvas, net, gx, gy, track_y, lane_dx=x_top - gx, jog_y=jog_y)
        riser_top_xs[net].append(x_top)

    for net, pads in nets.items():
        track_y = per_net_track_y[net]
        xs = [pad_center(p)[0] for p in pads] + riser_top_xs[net]
        x_lo, x_hi = min(xs), max(xs)
        if x_hi > x_lo:
            with canvas.net(net):
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
