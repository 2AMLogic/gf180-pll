"""The whole VCO block: five sub-blocks wired together under one guard ring.

WHAT THIS MODULE IS
--------------------
Issue #293's final increment. Four earlier increments each drew one piece of
``vco.sch``/``vco_bias.sch`` as its own standalone, DRC-clean block:

======================  ==========================  =========================
Sub-block               Generator                   Landed in
======================  ==========================  =========================
5-stage ring            ``ring.py``                 PR #305
band-select mirror      ``mirror.py``               PR #313
3-stage output buffer   ``buffer.py``               PR #313
``RCG``/``ROFF``/       ``bias_resistors.py``       PR #314
``RDEG``
V-to-I core             ``vtoi_core.py``            PR #316
======================  ==========================  =========================

Each of those five carries its own dedicated guard ring and proves clean on
its own -- but five separately-clean blocks are not one clean block, and none
of the *inter*-sub-block nets (``NC``/``NOFF``/``NVI`` from the resistors to
the V-to-I core, ``VBP0`` from the core to the mirror, ``VBP``/``VBN`` from
the mirror to the ring, ``Y5`` from the ring to the buffer, and the
``VDD_VCO``/``GND_VCO`` distribution that has to reach all five) existed as
drawn geometry anywhere. This module draws them, wraps the result in the
block-level ``GND_VCO`` substrate ring PLL-FLOORPLAN.md section 1 asks for,
carries the 22 pF decap forward against *this* block's own ``VDD_VCO``
pin/ring-tap junction, and is DRC-clean as one layout.

FLAT, NOT HIERARCHICAL
-----------------------
``primitives.Canvas.at()`` translates a sub-block generator's own local
coordinates into this block's frame, so every sub-block is drawn into one
flat top cell instead of being instanced. That is a deliberate trade (see
``Canvas.at()``'s own docstring): this block's routing has to *merge* with
sub-block shapes -- a via1 landing inside a sub-block's own Metal1 rail, a
Metal2 track extended past a sub-block's boundary -- and shapes that must
merge into one polygon for DRC have to live in one cell. Every sub-block
generator is unchanged when built standalone (offset ``(0, 0)``), which is
what keeps the five standalone DRC proofs on ``main`` still valid.

ROUTING DISCIPLINE (why this is checkable by hand)
---------------------------------------------------
Two of the five sub-blocks (``mirror.py``, ``vtoi_core.py``) already use
Metal2, as horizontal per-net tracks on a ``TRACK_PITCH_UM`` = 0.8 um pitch
inside their own device channel; the other three use Metal1 only. So:

* **Every top-level signal route is Metal2.** Metal2 has no spacing
  relationship with Metal1, comp, poly or implant in this deck, so a route
  may cross any sub-block's guard ring, rails, devices and taps freely. The
  only geometry a top-level route can collide with is *other Metal2*.
* **A route into a mesh-block pin is that pin's own track, extended.** Both
  mesh blocks pin a net by stubbing its track past the device row; extending
  that same track further (in the same direction, at the same y) adds no new
  neighbour relationship -- the extension's nearest other-net Metal2 is still
  the adjacent track, 0.8 - 0.44 = 0.36 um away, above ``M2.2a``'s 0.28 um.
* **Every other route runs in an inter-row channel or a side column**, whose
  widths are the ``*_GAP_UM``/``*_X`` constants below. ``_Router.reserve()``
  records every segment and raises if two different nets' Metal2 come within
  ``M2.2a`` -- the same "a spacing bug is cheaper as a Python exception than
  as a DRC marker" check ``mirror.py``'s ``Plan.reserve()`` makes on Metal1.

THE ONE NET THAT IS NOT METAL2: ``VDD_VCO``
---------------------------------------------
The supply trunk cannot be Metal2 without crossing every Metal2 signal that
escapes to the same side, and it cannot be a plain Metal1 run into a
sub-block either -- a Metal1 wire entering any of these blocks crosses that
block's own Metal1-covered ``GND_VCO`` guard ring band, i.e. shorts to
ground. So ``VDD_VCO`` is a **Metal1 vertical trunk** in the right-hand
channel (signals cross over it on Metal2, no rule between the layers), and
each sub-block is fed by a short Metal2 hop from the trunk to a via1 landing
on that block's own n-well tap band -- hopping over its guard ring on the
layer that is allowed to. ``GND_VCO`` needs no trunk at all: it is the
substrate, and the block-level ring is tied to each sub-block's own ring by a
Metal1 strap in the left-hand channel.

THE GUARD RING IS NOW A REAL TWO-SIDED RING (issue #324)
-----------------------------------------------------------
PLL-FLOORPLAN.md section 1 asks for the VCO's ring to be "a real two-sided
ring, not a substrate-only one" -- ``GND_VCO`` on the substrate side and a
``VDD_VCO``-tied n-well tap ring on the well side. PR #325 (this module's own
first increment) left the block-level ring ``GND_VCO`` substrate only,
recording the missing n-well band's cost (~4.4 um/side, +8.8 um of block
width) and noting there was no width budget for it at the time. Issue #324
funds it: folding ``mirror.py`` from one row into two tiers recovered ~80 um
of block width, which is far more than the ring costs, so
``NWELL_RING_WIDTH_UM``/``NWELL_RING_INNER_GAP_UM``/``NWELL_RING_OUTER_GAP_UM``
below draw it concentric with the ``GND_VCO`` ring, tied to the real
``VDD_VCO`` supply trunk (not left floating), and it fits inside the
pre-existing ``SHARED_MARGIN_UM`` gap rather than growing the block further.
See ``layout/evidence/vco-layout/PROOF-mirror-fold.md``.

One real design conflict this surfaced: the block's own pre-existing
``GND_VCO`` straps (block ring -> each sub-block's own ring) run radially
through the exact annulus the new n-well ring now occupies, and a Metal1
strap crossing a Metal1 ring merges into it -- a real short
(``block.connectivity_report()`` caught it; DRC did not, since same-layer
shapes touching is not a width/spacing violation). Each strap now hops onto
Metal2 for exactly the width of that crossing
(``strap_across_nwell_ring()``), the same "Metal2 has no spacing
relationship to Metal1" principle this module's own inter-sub-block routing
already uses (see "ROUTING DISCIPLINE" above).

DEVIATION FROM THE ROM FLOORPLAN, STATED PLAINLY
--------------------------------------------------
``footprint_um()`` reports the assembled block at 214.82 x 162.88 um
(34,990 um^2 = 0.0350 mm^2) against PLL-FLOORPLAN.md section 5's
0.011-0.017 mm^2 ROM row for the whole VCO -- still an overrun, though a
smaller one than PR #325's own 294.78 x 148.18 um (43,680 um^2) figure. That
record's section 5 names this case in advance and prescribes the response
("the next floorplan revision should state the overrun explicitly rather
than silently rounding the total down"), so it is stated here, in
``layout/floorplan/skeleton.py``'s docstring, and in
``layout/evidence/vco-layout/PROOF-mirror-fold.md`` with the re-run budget
arithmetic.

The cause is the one already recorded per sub-block: every device is drawn
as its own diffusion island wired by metal (``primitives.py``'s module
docstring). PR #325 packed the resistor trio into the V-to-I core row's own
leftover width and trimmed the boundary-pin channels (294.8 -> 279.9 um
mirror-driven width before this increment's own further reduction); issue
#324 then folded the band-select mirror itself from one row into two tiers
(``mirror.py``), the real lever PR #325's own PROOF named -- worth ~80 um of
block width on its own. Every other sub-block is still a single row, so
folding those too remains the next area optimisation if a future budget
pass needs it, but is not this issue's scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import bias_resistors
from . import buffer as out_buffer
from . import devices as dev
from . import mirror
from . import primitives as prim
from . import ring
from . import vtoi_core

TOP_CELL = "vco_block"

VDD_NET = "VDD_VCO"
GND_NET = "GND_VCO"

# --- inter-row channels (um) ------------------------------------------------
ROW_GAP_BIAS_TO_MIRROR_UM = 8.0
ROW_GAP_MIRROR_TO_RING_UM = 6.0  # carries the VBP and VBN lanes
ROW_GAP_RING_TO_BUFFER_UM = 6.0  # carries the Y5 lane

# The resistor trio is only 13 x 40 um and the V-to-I core's own row is 51 um
# tall and stops at x = 117 while the band mirror below sets the block's full
# ~266 um width -- so the resistors go in *that row's own leftover space*,
# right of the core, rather than beside it on the left where they would widen
# the whole block by their own footprint plus a channel. Cost of doing so: the
# ``VBP0`` route can no longer leave the core on the right (its horizontal run
# would cross the two resistor riser columns), so it leaves on the left
# instead -- see ``VBP0_COL_OFFSET_UM``.
RES_CHANNEL_UM = 6.5  # V-to-I core right edge -> resistor block left edge
RES_COL_NVI_OFFSET_UM = 2.0  # ... and the two riser columns inside it. NVI is
RES_COL_NOFF_OFFSET_UM = 4.0  # the *inner* column even though its track is the
# outer one: that ordering is what keeps the two crossing-free (NOFF's own
# horizontal run then passes the NVI column at a y the NVI riser has not
# started at yet). ``_Router.reserve()`` proves it rather than trusting this.

BUFFER_DX_UM = 57.0  # puts the buffer's own Y5 input pin almost directly over
# the ring's stage-5 output pad, so the Y5 hop is a short vertical rather than
# a run across the block -- PLL-FLOORPLAN.md section 1's "farthest from the
# ring's own starved internal nodes" applies to the buffer's *last* stage,
# which buffer.py already places at its far right.

# --- right-hand channel: one Metal1 supply trunk + two Metal2 columns -------
VDD_TRUNK_CLEARANCE_UM = 1.5  # widest sub-block's right edge -> trunk centre
VDD_TRUNK_WIDTH_UM = 1.0
COL_PITCH_UM = 2.0  # Metal2 column pitch in the right-hand channel
CLK_PIN_OFFSET_UM = 3.0  # last Metal2 column -> the CLK output pin

# --- left-hand channel ------------------------------------------------------
# Two columns only, and their order matters: the ``VBP0`` riser (which spans
# the whole bias-row-to-mirror-row height) sits *outside* the input-pin
# column, so the four input routes -- which all run rightward from their pin
# to their own sub-block's track -- never cross it.
VBP0_COL_OFFSET_UM = 7.0  # leftmost sub-block edge -> the VBP0 riser column
LEFT_PIN_CHANNEL_UM = 3.0  # leftmost sub-block edge -> the input-pin column
PIN_STUB_UM = 0.6  # drawn length of a boundary pin's own landing pad

# --- block-level guard ring -------------------------------------------------
SHARED_RING_WIDTH_UM = 1.2
STRAP_WIDTH_UM = 1.2  # Metal1 tie, block ring <-> a sub-block's own ring

# Issue #324's own closing increment: PLL-FLOORPLAN.md section 1 asks for
# this block's own guard ring to be "a real two-sided ring ... tied to
# GND_VCO on the substrate side and to a local VDD_VCO-tied n-well tap ring
# on the p-well side", which PR #325 (issue #293's own final increment) left
# open -- every n-well *inside* this block is VDD_VCO-tied by its own
# sub-block's tap band, but there was no second, concentric n-well band at
# the block boundary. Folding the band-select mirror into two tiers
# (mirror.py) recovered ~80 um of block width, which funds this ring.
# ``kind="n"``, so ``guard_ring()`` draws n-well tap bands (ncomp + nplus)
# tied VDD_VCO; the caller (``build()``) also draws the ``nwell`` shape those
# tap bands sit inside, same convention every per-sub-block generator already
# uses.
NWELL_TAP_ENCLOSURE_MARGIN_UM = 0.3  # DF.4d_LV needs the nwell shape to
# enclose its own tap comp by >= 0.12 um on every side; this ring's own
# drawn ``nwell`` rect is grown by this much past its own tap band's outer
# edge (see build()), not flush with it.
NWELL_RING_WIDTH_UM = 0.9  # >= NW.1a_LV's 0.86 um min, with margin
NWELL_RING_INNER_GAP_UM = 1.3  # content's own comp -> this ring's own nwell
# edge: >= DF.16_LV's 0.43 um with margin, *and* wide enough that a via1
# landing pad (0.44 um) fits inside it with M1.2a's 0.23 um clearance on both
# sides -- the block's own GND_VCO straps have to jump onto Metal2 to cross
# this ring without shorting to it (see build()'s strap_across_nwell_ring()),
# and that jump's own via1 lands in this gap.
NWELL_RING_OUTER_GAP_UM = 1.3  # this ring's own outer edge -> the GND_VCO
# ring's own comp -- same >= DF.4c_LV-with-margin-and-via-room sizing as the
# inner gap, for the same strap jump's *other* via1.
SHARED_MARGIN_UM = NWELL_RING_INNER_GAP_UM + NWELL_RING_WIDTH_UM + NWELL_RING_OUTER_GAP_UM
# content bbox -> the GND_VCO ring's own inner edge -- sized to exactly fit
# the n-well ring plus both of its own via-jump clearances above, not an
# independent guess the way it was before this ring existed.

M2_HALF_UM = prim.METAL2_WIRE_WIDTH_UM / 2.0


# ---------------------------------------------------------------------------
# Placement -- pure Python (no KLayout import), same convention as every other
# module in this package: footprint_um() and layout/tests/ derive the block's
# extents from the same arithmetic build() draws from.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """Where each sub-block generator's own local origin lands in this block."""

    dx_res: float
    dy_res: float
    dx_vtoi: float
    dy_vtoi: float
    dx_mirror: float
    dy_mirror: float
    dx_ring: float
    dy_ring: float
    dx_buffer: float
    dy_buffer: float
    # derived channel geometry, absolute coordinates
    vdd_trunk_x: float
    col_vbp_x: float
    col_vbn_x: float
    col_vbp0_x: float
    clk_pin_x: float
    left_pin_x: float
    res_col_noff_x: float
    res_col_nvi_x: float
    content: tuple  # (x0, y0, x1, y1) of everything the guard ring encloses
    nwell_ring: tuple  # (x0, y0, x1, y1) of the block-level n-well tap ring
    outer: tuple  # (x0, y0, x1, y1) of the block-level GND_VCO guard ring itself

    def boxes(self) -> dict:
        """Each sub-block's own guard-ring box, translated into block coords."""
        return {
            "bias_resistors": _shift(bias_resistors.footprint_um(), self.dx_res, self.dy_res),
            "vtoi_core": _shift(vtoi_core.footprint_um(), self.dx_vtoi, self.dy_vtoi),
            "mirror": _shift(mirror.footprint_um(), self.dx_mirror, self.dy_mirror),
            "ring": _shift(ring.footprint_um(with_decap=False), self.dx_ring, self.dy_ring),
            "buffer": _shift(out_buffer.footprint_um(), self.dx_buffer, self.dy_buffer),
        }


def _shift(box: tuple, dx: float, dy: float) -> tuple:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def placement() -> Placement:
    vt = vtoi_core.footprint_um()
    mi = mirror.footprint_um()
    rg = ring.footprint_um(with_decap=False)
    bf = out_buffer.footprint_um()
    rs = bias_resistors.footprint_um()

    snap = dev.snap_um

    # --- bias row: the V-to-I core sets the origin; the resistor block sits
    # one channel to its right, in that row's own leftover width, at the y
    # offset that lands RCG's own signal pad exactly on the core's NC Metal2
    # track (see bias_resistors.top_pad_center_um() for why that is worth
    # arranging). ---
    dx_vtoi = dy_vtoi = 0.0
    dx_res = snap(vt[2] + RES_CHANNEL_UM - rs[0])
    dy_res = snap(
        vtoi_core.plan().track_lo["NC"] - bias_resistors.top_pad_center_um(dev.BIAS_R_RCG)[1]
    )

    # --- rows stack bottom to top in signal order: bias -> mirror -> ring ->
    # buffer, each left-aligned on the V-to-I core's own x origin. ---
    dx_mirror = dx_ring = 0.0
    dy_mirror = snap(vt[3] + ROW_GAP_BIAS_TO_MIRROR_UM - mi[1])
    dy_ring = snap(dy_mirror + mi[3] + ROW_GAP_MIRROR_TO_RING_UM - rg[1])
    dx_buffer = BUFFER_DX_UM
    dy_buffer = snap(dy_ring + rg[3] + ROW_GAP_RING_TO_BUFFER_UM - bf[1])

    rows = (
        _shift(rs, dx_res, dy_res),
        _shift(vt, dx_vtoi, dy_vtoi),
        _shift(mi, dx_mirror, dy_mirror),
        _shift(rg, dx_ring, dy_ring),
        _shift(bf, dx_buffer, dy_buffer),
    )
    blocks_x1 = max(b[2] for b in rows)
    blocks_x0 = min(b[0] for b in rows)

    vdd_trunk_x = snap(blocks_x1 + VDD_TRUNK_CLEARANCE_UM)
    col_vbp_x = snap(vdd_trunk_x + COL_PITCH_UM)
    col_vbn_x = snap(vdd_trunk_x + 2 * COL_PITCH_UM)
    clk_pin_x = snap(col_vbn_x + CLK_PIN_OFFSET_UM)
    col_vbp0_x = snap(blocks_x0 - VBP0_COL_OFFSET_UM)
    left_pin_x = snap(blocks_x0 - LEFT_PIN_CHANNEL_UM)

    res_col_nvi_x = snap(vt[2] + RES_COL_NVI_OFFSET_UM)
    res_col_noff_x = snap(vt[2] + RES_COL_NOFF_OFFSET_UM)

    content = (
        col_vbp0_x - M2_HALF_UM,
        min(b[1] for b in rows),
        clk_pin_x + M2_HALF_UM,
        max(b[3] for b in rows),
    )
    m = SHARED_MARGIN_UM + SHARED_RING_WIDTH_UM
    outer = (content[0] - m, content[1] - m, content[2] + m, content[3] + m)

    # n-well ring: concentric with ``outer``, inside the same SHARED_MARGIN_UM
    # gap that already separated ``content`` from the GND_VCO ring's own inner
    # edge -- see NWELL_RING_*_UM's own comment for why this costs no extra
    # block width beyond what the mirror fold already recovered.
    nm = NWELL_RING_INNER_GAP_UM + NWELL_RING_WIDTH_UM
    nwell_ring = (content[0] - nm, content[1] - nm, content[2] + nm, content[3] + nm)

    return Placement(
        dx_res=dx_res,
        dy_res=dy_res,
        dx_vtoi=dx_vtoi,
        dy_vtoi=dy_vtoi,
        dx_mirror=dx_mirror,
        dy_mirror=dy_mirror,
        dx_ring=dx_ring,
        dy_ring=dy_ring,
        dx_buffer=dx_buffer,
        dy_buffer=dy_buffer,
        vdd_trunk_x=vdd_trunk_x,
        col_vbp_x=col_vbp_x,
        col_vbn_x=col_vbn_x,
        col_vbp0_x=col_vbp0_x,
        clk_pin_x=clk_pin_x,
        left_pin_x=left_pin_x,
        res_col_noff_x=res_col_noff_x,
        res_col_nvi_x=res_col_nvi_x,
        content=content,
        nwell_ring=nwell_ring,
        outer=outer,
    )


def footprint_um() -> tuple:
    """Pure-Python (no KLayout) footprint: the block-level guard ring's box."""
    return placement().outer


def decap_boxes_um() -> tuple:
    """The two carried-forward 22 pF decap footprints, absolute coordinates.

    Placed in the open area to the right of the V-to-I core, immediately left
    of this block's own ``VDD_VCO`` pin -- i.e. against the pin/ring-tap
    junction where the supply trunk meets the core's n-well tap band, which is
    what issue #293's acceptance criterion asks for. Carried forward as the
    same layer-(0, 0) boundary markers ``ring.py`` and
    ``layout/floorplan/skeleton.py`` have always used (no DRC rule in this
    deck references that layer); ``ring.build(draw_decap=False)`` suppresses
    the ring block's own copy so this is one marker pair for one physical
    pair of caps, not two.
    """
    p = placement()
    size = dev.DECAP_SIZE_UM
    gap = 2.0
    x1 = p.vdd_trunk_x - 5.0
    y0 = _shift(vtoi_core.footprint_um(), p.dx_vtoi, p.dy_vtoi)[3] - size
    first_x0 = x1 - 2 * size - gap
    return (
        (first_x0, y0, first_x0 + size, y0 + size),
        (first_x0 + size + gap, y0, x1, y0 + size),
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


@dataclass
class VcoBlockResult:
    canvas: prim.Canvas
    placement: Placement
    footprint: tuple = (0.0, 0.0, 0.0, 0.0)
    sub_pins: dict = field(default_factory=dict)
    nets: dict = field(default_factory=dict)


def _center(box: tuple) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


class _Router:
    """Draws top-level Metal2 routes and proves they never crowd each other.

    Same intent as ``mirror.Plan.reserve()``: a spacing bug in a generated
    300 um-wide block is much cheaper to find as a Python exception naming the
    two nets than as one of several thousand DRC markers. Every rectangle this
    class draws is recorded; a new rectangle that comes within ``M2.2a``'s
    0.28 um of a *different* net's recorded rectangle raises.
    """

    def __init__(self, canvas: prim.Canvas) -> None:
        self.canvas = canvas
        self._boxes: list[tuple[str, float, float, float, float]] = []

    def _reserve(self, net: str, box: tuple) -> None:
        s = dev.DRC_METAL2_MIN_SPACE_UM
        x0, y0, x1, y1 = box
        for other, ox0, oy0, ox1, oy1 in self._boxes:
            if other == net:
                continue
            if x0 - s < ox1 and ox0 < x1 + s and y0 - s < oy1 and oy0 < y1 + s:
                raise ValueError(
                    f"top-level Metal2 for {net!r} and {other!r} are closer than M2.2a's "
                    f"{s} um: ({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f}) vs "
                    f"({ox0:.3f},{oy0:.3f})-({ox1:.3f},{oy1:.3f})"
                )
        self._boxes.append((net, x0, y0, x1, y1))

    def route(self, net: str, points: list[tuple[float, float]]) -> None:
        half = M2_HALF_UM
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if abs(y1 - y0) < 1e-9:
                box = (min(x0, x1) - half, y0 - half, max(x0, x1) + half, y0 + half)
            elif abs(x1 - x0) < 1e-9:
                box = (x0 - half, min(y0, y1) - half, x0 + half, max(y0, y1) + half)
            else:
                raise ValueError(f"non-Manhattan segment for {net!r}")
            self._reserve(net, box)
        prim.m2_route(self.canvas, points)

    def via(self, net: str, x: float, y: float) -> None:
        pad = prim.via1_stack(self.canvas, x, y)
        self._reserve(net, pad)


def build(outdir: Path | None = None) -> VcoBlockResult:
    p = placement()
    canvas = prim.Canvas(TOP_CELL)

    # --- 1. place the five sub-blocks --------------------------------------
    with canvas.at(p.dx_res, p.dy_res) as res_pins:
        bias_resistors.build(canvas=canvas)
    with canvas.at(p.dx_vtoi, p.dy_vtoi) as vtoi_pins:
        vtoi_res = vtoi_core.build(canvas=canvas)
    with canvas.at(p.dx_mirror, p.dy_mirror) as mirror_pins:
        mirror.build(canvas=canvas)
    with canvas.at(p.dx_ring, p.dy_ring) as ring_pins:
        ring_res = ring.build(canvas=canvas, draw_decap=False)
    with canvas.at(p.dx_buffer, p.dy_buffer) as buffer_pins:
        out_buffer.build(canvas=canvas)

    sub_pins = {
        "bias_resistors": res_pins,
        "vtoi_core": vtoi_pins,
        "mirror": mirror_pins,
        "ring": ring_pins,
        "buffer": buffer_pins,
    }
    r = _Router(canvas)
    boxes = p.boxes()

    def track_in(pins: dict, net: str) -> tuple[float, float]:
        """A mesh block's *input*-side pin: (track left end x, track y)."""
        box = pins[net][0]
        return (box[2], _center(box)[1])

    def track_out(pins: dict, net: str) -> tuple[float, float]:
        """A mesh block's *output*-side pin: (track right end x, track y)."""
        box = pins[net][0]
        return (box[0], _center(box)[1])

    # --- 2. bias generator: RCG/ROFF/RDEG -> the V-to-I core ---------------
    # Each route starts at the core's own track (``track_in()`` returns that
    # track's far end, so the route redraws the whole track and cannot leave a
    # gap) and runs right to the resistor's pad. NC is a straight wire by
    # construction -- placement() picked the resistor block's y offset so
    # RCG's pad lands on that track. NOFF and NVI rise through their own
    # columns; see RES_COL_*_OFFSET_UM for why NVI takes the inner one.
    nc_x, nc_y = track_in(vtoi_pins, "NC")
    nc_pad_x, nc_pad_y = _center(res_pins["NC"][0])
    r.route("NC", [(nc_x, nc_y), (nc_pad_x, nc_y)])
    r.via("NC", nc_pad_x, nc_pad_y)

    noff_x, noff_y = track_in(vtoi_pins, "NOFF")
    noff_pad_x, noff_pad_y = _center(res_pins["NOFF"][0])
    nvi_x, nvi_y = track_in(vtoi_pins, "NVI")
    nvi_pad_x, nvi_pad_y = _center(res_pins["NVI"][0])
    nvi_lane_y = dev.snap_um(nvi_pad_y + 2.1)
    r.route(
        "NOFF",
        [
            (noff_x, noff_y),
            (p.res_col_noff_x, noff_y),
            (p.res_col_noff_x, noff_pad_y),
            (noff_pad_x, noff_pad_y),
        ],
    )
    r.via("NOFF", noff_pad_x, noff_pad_y)
    r.route(
        "NVI",
        [
            (nvi_x, nvi_y),
            (p.res_col_nvi_x, nvi_y),
            (p.res_col_nvi_x, nvi_lane_y),
            (nvi_pad_x, nvi_lane_y),
            (nvi_pad_x, nvi_pad_y),
        ],
    )
    r.via("NVI", nvi_pad_x, nvi_pad_y)

    # --- 3. VBP0: the V-to-I core's summing node -> the mirror's cascade A.
    # Out on the core's *left* (the right is where the resistor risers are),
    # up the left-hand riser column, back in on the mirror's own VBP0 track.
    # The riser cannot run up inside the mirror's own width -- it would cross
    # every one of that block's horizontal Metal2 tracks -- so it takes the
    # channel outside the mirror's left edge. ---
    vbp0_y = _center(vtoi_pins["VBP0"][0])[1]
    vbp0_track_x0 = min(vtoi_res.net_x[("VBP0", "pfet")]) - M2_HALF_UM + p.dx_vtoi
    vbp0_in_x, vbp0_in_y = track_in(mirror_pins, "VBP0")
    r.route(
        "VBP0",
        [
            (vbp0_track_x0, vbp0_y),
            (p.col_vbp0_x, vbp0_y),
            (p.col_vbp0_x, vbp0_in_y),
            (vbp0_in_x, vbp0_in_y),
        ],
    )

    # --- 4. VBP / VBN: the mirror's outputs -> the ring's own bias rails.
    # Both land on the ring's full-width Metal1 rails rather than on its
    # left-edge pin pads, which is what lets the two routes use *different*
    # x columns inside the ring and so never cross: VBP takes the rail's left
    # end, VBN a point two thirds along it. ---
    ring_ports = ring_res.stage_ports
    rail_x0 = min(q.a_gate_pad_bottom[0] for q in ring_ports) + p.dx_ring
    vbp_rail_y = _center(ring_pins["VBP"][0])[1]
    vbn_rail_y = _center(ring_pins["VBN"][0])[1]
    vbp_land_x = dev.snap_um(rail_x0 + 0.5)
    vbn_land_x = dev.snap_um(p.dx_ring + (dev.STAGE_COUNT - 1) * ring.STAGE_PITCH_UM + 4.0)

    channel_y0 = boxes["mirror"][3]
    lane_vbp_y = dev.snap_um(channel_y0 + ROW_GAP_MIRROR_TO_RING_UM * 0.32)
    lane_vbn_y = dev.snap_um(channel_y0 + ROW_GAP_MIRROR_TO_RING_UM * 0.58)

    vbp_out_x, vbp_out_y = track_out(mirror_pins, "VBP")
    r.route(
        "VBP",
        [
            (vbp_out_x, vbp_out_y),
            (p.col_vbp_x, vbp_out_y),
            (p.col_vbp_x, lane_vbp_y),
            (vbp_land_x, lane_vbp_y),
            (vbp_land_x, vbp_rail_y),
        ],
    )
    r.via("VBP", vbp_land_x, vbp_rail_y)

    vbn_out_x, vbn_out_y = track_out(mirror_pins, "VBN")
    r.route(
        "VBN",
        [
            (vbn_out_x, vbn_out_y),
            (p.col_vbn_x, vbn_out_y),
            (p.col_vbn_x, lane_vbn_y),
            (vbn_land_x, lane_vbn_y),
            (vbn_land_x, vbn_rail_y),
        ],
    )
    r.via("VBN", vbn_land_x, vbn_rail_y)

    # --- 5. Y5: the ring's stage-5 output -> the buffer's input gate ------
    y5_pad = ring_pins["Y5_CLK_IN"][0]
    y5_x, y5_y = _center(y5_pad)
    buf_in_x, buf_in_y = _center(buffer_pins[dev.BUFFER_IN_NET][0])
    lane_y5_y = dev.snap_um(boxes["ring"][3] + ROW_GAP_RING_TO_BUFFER_UM / 2.0)
    r.route(
        "Y5",
        [
            (y5_x, y5_y),
            (y5_x, lane_y5_y),
            (buf_in_x, lane_y5_y),
            (buf_in_x, buf_in_y),
        ],
    )
    r.via("Y5", y5_x, y5_y)
    r.via("Y5", buf_in_x, buf_in_y)

    # --- 6. VDD_VCO: Metal1 trunk + one Metal2 hop per sub-block onto that
    # block's own n-well tap band (see the module docstring for why the
    # supply is the one net that cannot be Metal2 all the way in). ---
    trunk_y0 = min(b[1] for b in boxes.values())
    trunk_y1 = max(b[3] for b in boxes.values())
    prim.v_wire(canvas, p.vdd_trunk_x, trunk_y0, trunk_y1, width=VDD_TRUNK_WIDTH_UM)

    def vdd_feed(pins: dict) -> float:
        """Hop from the trunk onto the topmost ``VDD_VCO`` tap band of a block."""
        band = max(pins[VDD_NET], key=lambda b: b[3])
        y = _center(band)[1]
        x = dev.snap_um(band[2] - 0.5)
        r.route(VDD_NET, [(x, y), (p.vdd_trunk_x, y)])
        r.via(VDD_NET, x, y)
        r.via(VDD_NET, p.vdd_trunk_x, y)
        return y

    vdd_pin_y = vdd_feed(vtoi_pins)
    for pins in (mirror_pins, ring_pins, buffer_pins):
        vdd_feed(pins)

    # --- 7. block boundary pins -------------------------------------------
    # Inputs stay on their own sub-block's track y and simply run out to the
    # left-hand pin column -- no risers, so nothing in the left channel can
    # cross anything else there.
    for pins, net in (
        (vtoi_pins, dev.VTOI_IN_NET),
        (mirror_pins, "B0"),
        (mirror_pins, "B1"),
        (mirror_pins, "B2"),
    ):
        x_in, y_in = track_in(pins, net)
        r.route(net, [(p.left_pin_x, y_in), (x_in, y_in)])
        canvas.pin(
            net,
            p.left_pin_x,
            y_in - M2_HALF_UM,
            p.left_pin_x + PIN_STUB_UM,
            y_in + M2_HALF_UM,
            layer="metal2",
        )

    clk_pad = buffer_pins[dev.BUFFER_OUT_NET][0]
    clk_x, clk_y = _center(clk_pad)
    r.route(dev.BUFFER_OUT_NET, [(clk_x, clk_y), (p.clk_pin_x, clk_y)])
    r.via(dev.BUFFER_OUT_NET, clk_x, clk_y)
    canvas.pin(
        dev.BUFFER_OUT_NET,
        p.clk_pin_x - PIN_STUB_UM,
        clk_y - M2_HALF_UM,
        p.clk_pin_x,
        clk_y + M2_HALF_UM,
        layer="metal2",
    )
    canvas.pin(
        VDD_NET,
        p.vdd_trunk_x - VDD_TRUNK_WIDTH_UM / 2.0,
        vdd_pin_y - 0.5,
        p.vdd_trunk_x + VDD_TRUNK_WIDTH_UM / 2.0,
        vdd_pin_y + 0.5,
    )

    # --- 8. the block-level n-well tap ring (issue #324): concentric with
    # the GND_VCO ring below, VDD_VCO-tied, closing PLL-FLOORPLAN.md section
    # 1's "real two-sided ring" acceptance criterion that PR #325 (#293's own
    # final increment) left open -- see NWELL_RING_*_UM's own comment for why
    # this fits inside the pre-existing SHARED_MARGIN_UM gap rather than
    # growing the block. A plain filled nwell rect, same convention every
    # per-sub-block generator already uses for its own tap band: nothing
    # else is ever placed in this annulus, so there is no reason to draw it
    # hollow -- grown NWELL_TAP_ENCLOSURE_MARGIN_UM past the ring's own tap
    # comp on every side (DF.4d_LV's own 0.12 um n-well-encloses-tap minimum,
    # with margin), not flush with it. ---
    nwell_shape = (
        p.nwell_ring[0] - NWELL_TAP_ENCLOSURE_MARGIN_UM,
        p.nwell_ring[1] - NWELL_TAP_ENCLOSURE_MARGIN_UM,
        p.nwell_ring[2] + NWELL_TAP_ENCLOSURE_MARGIN_UM,
        p.nwell_ring[3] + NWELL_TAP_ENCLOSURE_MARGIN_UM,
    )
    canvas.rect("nwell", *nwell_shape)
    prim.guard_ring(canvas, "n", *p.nwell_ring, NWELL_RING_WIDTH_UM, VDD_NET)
    prim.h_wire(canvas, p.vdd_trunk_x, p.nwell_ring[2], vdd_pin_y, width=STRAP_WIDTH_UM)

    # --- 9. block-level GND_VCO guard ring + Metal1 straps to each
    # sub-block's own ring. The bias row is strapped as a chain (block ring ->
    # resistors -> V-to-I core) because the resistor block sits between the
    # two; every other row is strapped straight to the block ring's left
    # band. Straps stay on the left, where the Metal1 supply trunk is not. ---
    prim.guard_ring(canvas, "p", *p.outer, SHARED_RING_WIDTH_UM, GND_NET)
    strap_x0 = p.outer[0] + SHARED_RING_WIDTH_UM

    def strap(x0: float, x1: float, y: float) -> None:
        """A plain Metal1 tie between two points already inside ``content`` --
        does not cross the n-well ring, so no jump is needed."""
        prim.h_wire(canvas, x0, x1, y, width=STRAP_WIDTH_UM)

    # The four straps below run from the block's own outer GND_VCO ring
    # (outside the n-well ring) in to a sub-block's own ring (inside it), so
    # each one physically crosses the n-well ring's own left band -- issue
    # #324's own new structure, not something these straps could route around.
    # Metal1 cannot cross Metal1 without merging (an M1.2a-legal gap is still
    # a short once two same-layer shapes touch), so each strap hops onto
    # Metal2 -- which has no spacing relationship to Metal1/comp/nwell in
    # this deck -- for exactly the width of that crossing, landing back on
    # Metal1 on the far side. Both jump points sit at the midpoint of their
    # own gap, symmetric clearance from the ring on both sides.
    ring_jump_out_x = dev.snap_um((strap_x0 + p.nwell_ring[0]) / 2.0)
    ring_jump_in_x = dev.snap_um(
        p.nwell_ring[0] + NWELL_RING_WIDTH_UM + NWELL_RING_INNER_GAP_UM / 2.0
    )

    def strap_across_nwell_ring(x0: float, x1: float, y: float) -> None:
        prim.h_wire(canvas, x0, ring_jump_out_x, y, width=STRAP_WIDTH_UM)
        prim.via1_stack(canvas, ring_jump_out_x, y)
        prim.m2_wire(canvas, ring_jump_out_x, ring_jump_in_x, y, width=STRAP_WIDTH_UM)
        prim.via1_stack(canvas, ring_jump_in_x, y)
        prim.h_wire(canvas, ring_jump_in_x, x1, y, width=STRAP_WIDTH_UM)

    res_box = boxes["bias_resistors"]
    vtoi_box = boxes["vtoi_core"]
    # The resistor block sits inboard of the V-to-I core, so it is strapped to
    # the core's own right band rather than to the block ring directly -- both
    # ends are already inside content, so this one stays plain Metal1.
    strap(
        vtoi_box[2] - vtoi_core.RING_WIDTH_UM,
        res_box[0] + bias_resistors.RING_WIDTH_UM,
        dev.snap_um((res_box[1] + res_box[3]) / 2.0 - 4.0),
    )
    for key, ring_w in (
        ("vtoi_core", vtoi_core.RING_WIDTH_UM),
        ("mirror", mirror.RING_WIDTH_UM),
        ("ring", ring.RING_WIDTH_UM),
        ("buffer", out_buffer.RING_WIDTH_UM),
    ):
        box = boxes[key]
        strap_across_nwell_ring(strap_x0, box[0] + ring_w, dev.snap_um((box[1] + box[3]) / 2.0))

    # --- 10. carried-forward 22 pF decap, against this block's VDD_VCO pin --
    for i, box in enumerate(decap_boxes_um()):
        canvas.rect("boundary", *box)
        canvas.label("boundary", f"vco.decap{i}", box[0] + 1.0, box[1] + 1.0)

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        canvas.write_gds(outdir / f"{TOP_CELL}.gds")

    return VcoBlockResult(
        canvas=canvas,
        placement=p,
        footprint=p.outer,
        sub_pins=sub_pins,
        nets={
            "VBP_land_x": vbp_land_x,
            "VBN_land_x": vbn_land_x,
            "vdd_pin_y": vdd_pin_y,
            "lane_vbp_y": lane_vbp_y,
            "lane_vbn_y": lane_vbn_y,
            "lane_y5_y": lane_y5_y,
        },
    )


# ---------------------------------------------------------------------------
# Connectivity proof
# ---------------------------------------------------------------------------
#
# DRC proves this block breaks no rule. It does *not* prove the inter-sub-block
# routes actually connect anything -- a Metal2 wire that stops 0.5 um short of
# its via1, or a via1 that lands beside a rail instead of on it, is perfectly
# DRC-clean and completely broken. Full LVS needs a block-level SPICE netlist
# and a device-recognition pass that is its own increment; what *is* available
# now, and is exactly the property this increment adds, is the metal
# connectivity: extract metal1/via1/metal2 as a connected graph and check that
# each pair of points the router claims to have joined really lands on one net
# (and that two nets which must stay apart did not merge).


CONNECTED_PROBES = (
    # (net, description, [(layer, x, y), ...]) -- every point must be one net
    ("NC", "RCG signal pad <-> V-to-I core's NC track"),
    ("NOFF", "ROFF signal pad <-> V-to-I core's NOFF track"),
    ("NVI", "RDEG signal pad <-> V-to-I core's NVI track"),
    ("VBP0", "V-to-I core summing node <-> band mirror cascade A"),
    ("VBP", "band mirror VBP output <-> ring VBP rail"),
    ("VBN", "band mirror VBN output <-> ring VBN rail"),
    ("Y5", "ring stage-5 output <-> output buffer input gate"),
    ("VDD_VCO", "supply trunk <-> all four n-well tap bands"),
    ("GND_VCO", "block guard ring <-> every sub-block guard ring"),
    ("CLK", "output buffer's last stage <-> the block's CLK pin"),
    ("VCTRL", "block VCTRL pin <-> V-to-I core's VCTRL track"),
    ("B0", "block B0 pin <-> band mirror's B0 track"),
    ("B1", "block B1 pin <-> band mirror's B1 track"),
    ("B2", "block B2 pin <-> band mirror's B2 track"),
)

DISTINCT_PROBES = (
    ("VDD_VCO", "GND_VCO"),
    ("VBP", "VBN"),
    ("NOFF", "NVI"),
    ("VBP0", "VBP"),
)


def _probe_points(result: VcoBlockResult) -> dict:
    """Two-or-more (layer, x, y) probe points per net the router claims to join."""
    p = result.placement
    sp = result.sub_pins
    boxes = p.boxes()

    def c(box: tuple) -> tuple[float, float]:
        return _center(box)

    pts: dict[str, list[tuple[str, float, float]]] = {}

    def add(net: str, layer: str, x: float, y: float) -> None:
        pts.setdefault(net, []).append((layer, x, y))

    for net in ("NC", "NOFF", "NVI"):
        add(net, "metal1", *c(sp["bias_resistors"][net][0]))
        add(net, "metal2", *c(sp["vtoi_core"][net][0]))
    add("VBP0", "metal2", *c(sp["vtoi_core"]["VBP0"][0]))
    add("VBP0", "metal2", *c(sp["mirror"]["VBP0"][0]))
    for net in ("VBP", "VBN"):
        add(net, "metal2", *c(sp["mirror"][net][0]))
        add(net, "metal1", *c(sp["ring"][net][0]))
    add("Y5", "metal1", *c(sp["ring"]["Y5_CLK_IN"][0]))
    add("Y5", "metal1", *c(sp["buffer"][dev.BUFFER_IN_NET][0]))
    add("VDD_VCO", "metal1", p.vdd_trunk_x, result.nets["vdd_pin_y"])
    for key in ("vtoi_core", "mirror", "ring", "buffer"):
        band = max(sp[key][VDD_NET], key=lambda b: b[3])
        add("VDD_VCO", "metal1", *c(band))
    add("GND_VCO", "metal1", (p.outer[0] + p.outer[2]) / 2.0, p.outer[1] + SHARED_RING_WIDTH_UM / 2.0)
    for key, ring_w in (
        ("bias_resistors", bias_resistors.RING_WIDTH_UM),
        ("vtoi_core", vtoi_core.RING_WIDTH_UM),
        ("mirror", mirror.RING_WIDTH_UM),
        ("ring", ring.RING_WIDTH_UM),
        ("buffer", out_buffer.RING_WIDTH_UM),
    ):
        box = boxes[key]
        add("GND_VCO", "metal1", (box[0] + box[2]) / 2.0, box[1] + ring_w / 2.0)
    add("CLK", "metal1", *c(sp["buffer"][dev.BUFFER_OUT_NET][0]))
    add("CLK", "metal2", *c(result.canvas.pins["CLK"][-1]))
    for net, key in (("VCTRL", "vtoi_core"), ("B0", "mirror"), ("B1", "mirror"), ("B2", "mirror")):
        add(net, "metal2", *c(sp[key][net][0]))
        add(net, "metal2", *c(result.canvas.pins[net][-1]))
    return pts


def connectivity_report(result: VcoBlockResult) -> list[tuple[str, bool, str]]:
    """Extract metal connectivity and check every routed net actually joins.

    Uses KLayout's own ``LayoutToNetlist`` connectivity extraction over
    metal1/via1/metal2 -- the same machinery the PDK's LVS deck builds on,
    restricted here to the interconnect layers (no device recognition), which
    is the part this increment is responsible for.
    """
    import klayout.db as db  # noqa: PLC0415

    layout = result.canvas.layout
    cell = result.canvas.top
    l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, cell, []))
    layers = {}
    for name in ("metal1", "via1", "metal2"):
        layers[name] = l2n.make_polygon_layer(layout.layer(*prim.LAYER[name]), name)
    l2n.connect(layers["metal1"])
    l2n.connect(layers["via1"])
    l2n.connect(layers["metal2"])
    l2n.connect(layers["metal1"], layers["via1"])
    l2n.connect(layers["via1"], layers["metal2"])
    l2n.extract_netlist()

    pts = _probe_points(result)
    net_of: dict[str, object] = {}
    out: list[tuple[str, bool, str]] = []
    for net, description in CONNECTED_PROBES:
        probes = pts[net]
        found = []
        for layer, x, y in probes:
            found.append(l2n.probe_net(layers[layer], db.DPoint(x, y)))
        missing = [p for p, n in zip(probes, found) if n is None]
        if missing:
            out.append((net, False, f"{description}: no metal found at {missing}"))
            continue
        ids = {n.cluster_id for n in found}
        ok = len(ids) == 1
        net_of[net] = found[0]
        out.append(
            (
                net,
                ok,
                f"{description}: {len(probes)} probe(s) -> "
                + ("one net" if ok else f"{len(ids)} separate nets {sorted(ids)}"),
            )
        )
    for a, b in DISTINCT_PROBES:
        if a in net_of and b in net_of:
            ok = net_of[a].cluster_id != net_of[b].cluster_id
            out.append((f"{a} != {b}", ok, "distinct nets" if ok else "SHORTED together"))
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        default=str(Path(__file__).resolve().parents[2] / "evidence" / "vco-layout" / "work"),
    )
    parser.add_argument(
        "--check-connectivity",
        action="store_true",
        help="extract metal connectivity and verify every routed net joins (needs klayout)",
    )
    args = parser.parse_args()
    result = build(Path(args.outdir))
    x0, y0, x1, y1 = result.footprint
    print(f"wrote {args.outdir}/{TOP_CELL}.gds")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    pl = result.placement
    for name, box in pl.boxes().items():
        print(f"  {name:<16} {box[0]:9.3f} {box[1]:9.3f} {box[2]:9.3f} {box[3]:9.3f}")
    if args.check_connectivity:
        print()
        failures = 0
        for name, ok, detail in connectivity_report(result):
            print(f"  {'ok  ' if ok else 'FAIL'} {name:<16} {detail}")
            failures += 0 if ok else 1
        print()
        print(f"connectivity: {'PASS' if failures == 0 else f'FAIL ({failures})'}")
        return 0 if failures == 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
