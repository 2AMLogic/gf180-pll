"""Block-placement GDS skeleton for the PLL floorplan (issue #17).

WHAT IT IS
----------
A single top cell, ``pll_floorplan_skeleton``, containing one boundary
rectangle per block plus the two sub-block geometries this floorplan record
can state exactly (the loop-filter cap array and the VCO's committed on-chip
decap) -- see ``PLL-FLOORPLAN.md`` for the placement rationale and the area
budget every rectangle below is sized from.

WHY GDS LAYER (0, 0)
---------------------
Every rectangle is drawn on GDS layer 0, datatype 0 -- the ``DIEAREA``
layer in this PDK's KLayout layer map
(``$PDK_ROOT/libs.tech/klayout/tech/gf180mcu.map``). Confirmed by grepping
every rule file under ``$PDK_ROOT/libs.tech/klayout/drc/rule_decks/*.drc``:
no rule in this deck references layer (0, 0) at all. That makes it a
boundary/reference marker, never a device or routing layer -- exactly what a
block-placement *skeleton* should be drawn on, since none of these blocks
have real transistor-level layout yet (see the scope note at the top of
``PLL-FLOORPLAN.md``). Running this skeleton through the DRC deck is
therefore trivially clean by construction; the value is exercising #16's
multi-shape/multi-cell flow, not a claim about device-level correctness of
geometry that does not exist yet.

Positions and sizes below are float micron coordinates from
``PLL-FLOORPLAN.md`` sections 1-5; only the loop-filter C1 array (4x
87x87 um, DR-006) and the VCO decap (2x 50x50 um, ``vco.sch``) are real,
as-drawn device footprints. Everything else is the ROM block-footprint
estimate from that record's area-budget table, midpoint of the stated range.

VCO real geometry (issues #293, #324)
--------------------------------------
``VCO_CORE`` is no longer a placeholder rectangle. ``layout/pll_top/vco/
block.py`` assembles all five VCO sub-blocks -- the 5-stage ring, the
common-centroid band-select mirror, the 3-stage output buffer, the
``RCG``/``ROFF``/``RDEG`` poly resistors and the V-to-I core -- into one
wired, DRC-clean layout under a two-sided block-level guard ring
(``GND_VCO`` substrate ring, ``VDD_VCO`` n-well tap ring concentric outside
it), and ``VCO_CORE`` below is *that block's own outer guard-ring box*, not
an estimate. Every sub-block rectangle in ``SUB_BLOCKS`` is likewise its real
drawn extent, translated out of the block's own coordinates. All of it comes
from plain-Python ``footprint_um()``/``placement()`` calls, so this file
still imports no KLayout.

**The real block is 172.5 x 183.5 um = 31,654 um^2, against
PLL-FLOORPLAN.md section 5's ROM row of 0.011-0.017 mm^2 for the whole VCO
-- a 1.9-2.9x overrun.** That record's own section 5 names this case in
advance ("if real per-block layout pushes the conservative estimate's ~34 %
margin below zero ... the next floorplan revision should state the overrun
explicitly rather than silently rounding the total down"), so it is stated
here rather than absorbed:

* Re-running section 5's own arithmetic with the measured VCO number in
  place of its ROM row gives a conservative block subtotal of
  0.0369 (loop filter) + 0.031654 (VCO) + 0.020 (PFD/CP) + 0.0052
  (divider+lock) = **0.093754 mm^2**, i.e. **0.117 mm^2** after that
  section's x1.25 top-level overhead -- inside the 0.15 mm^2 budget with
  ~22 % margin (section 5's own ROM-only conservative estimate had ~34 %).
* ``total_extent_um2()`` (this skeleton's whole bounding box, a deliberately
  looser number than the budget table -- see that function's own docstring)
  lands at ~124,300 um^2, i.e. ~17 % under the 150,000 um^2 target.

Both numbers improved sharply at issue #324 (see below) and then moved only
marginally at issue #336, which is stated explicitly rather than folded
silently into the #324 numbers: #336 gave the band-select mirror sub-block a
**2-D** common-centroid fold (cascade A 1x4 -> 2x2, cascade C 1x9 -> 3x3;
``vco/mirror.py``'s ``draw_cc_array()``), narrowing it from 152.6 to 115.9 um
-- the width lever #324's own row fold could not reach, because cascade C
alone (115.18 um) was already alone in its bank's PMOS row, so no further
*row* split could shrink it. That narrower-but-taller mirror shrinks
``VCO_CORE``'s width (183.2 -> 172.5 um, -5.8 %) but grows its height by the
same 13.2 um the mirror's own footprint grew (170.3 -> 183.5 um, +7.8 %) --
comfortably inside ``LOOP_FILTER``'s 195 um height budget, but *not* a free
trade at the block level the way #324's own height-for-width trade was: the
mirror's new height has nothing else in its own row of sub-blocks to absorb
it into, so ``VCO_CORE``'s own area moves from 31,192 to 31,654 um^2 (+1.5 %)
and the budget-table margin from ~22 % to ~22 % -- unchanged within rounding.
**Recorded as what it is: #336 is a real, DRC-clean width reduction and it
retires the "cascade C sets the mirror's width, and a row split can't go
below it" architectural dead-end #324 disclosed, but it is not, on its own,
an area win for the assembled block** -- see
``evidence/vco-layout/PROOF-2d-fold.md`` for the full accounting, including
why the mirror is very likely no longer the block's own width bottleneck
(the V-to-I core + bias-resistors row, 140.7 um combined, now exceeds the
mirror's 115.9 um).

Both numbers **improved** at issue #324, which is the same increment that
added the block's second (n-well) guard-ring band. Before it, the assembled
block was 294.8 x 148.2 um = 43,680 um^2 with a substrate-only block ring: a
2.6-4.0x ROM overrun, a ~148,200 um^2 whole-skeleton extent (~1.2 % under
target), and the same budget-table arithmetic giving 0.0369 + 0.0437 + 0.020
+ 0.0052 = 0.1058 mm^2, 0.1323 mm^2 after x1.25, ~12 % margin. (The earlier
revision of this docstring, and ``evidence/vco-layout/PROOF-block.md``,
quoted that subtotal as ~0.111 mm^2 / ~0.139 mm^2 / ~7 % -- the four terms
sum to 0.1058, not 0.111. The ~12 % figure above is the corrected
before-number; the conclusion it supported, that the margin had dropped
sharply and folding was the fix, is unchanged.) The cause of the overrun was
structural and recorded per sub-block: every device is drawn as its own
diffusion island wired by metal (see ``vco/primitives.py``'s module
docstring) and every sub-block was a *single row*, so the band-select mirror
alone was 266 um wide and set the whole block's width. #324 folded that
mirror into two stacked banks (see ``vco/mirror.py``'s ``BANKS``), trading
+16 um of block height -- which is free, the skeleton's height is set by
``LOOP_FILTER``'s 195 um, not by the VCO -- for -118 um of block width, and
spent 6.2 um of that back on the n-well ring. The remaining overrun (after
#324) was the same diffusion-island convention plus the mirror's own
still-flat cascades; #336 (above) closed the cascade-C-specific piece of
that. The other three sub-blocks (ring, buffer, resistors) are still single
rows, narrower than the mirror even after #336, and folding any one of them
alone would not reduce the block's own width -- the V-to-I core is now the
practical floor.

Divider/lock real geometry, and a budget overrun -- 2.9x, now 2.0x (issues
#296, #310, #341)
--------------------------------------------------------------------------
``DIVIDER_LOCK`` is likewise no longer a placeholder: both of its occupants
now have real, DRC-clean layout (``lock_detector``, #296; ``divider_chain``,
#310, additionally LVS-clean), and the region below is sized to contain the
two blocks' measured footprints rather than the 90x50 um placement-plan
estimate both were nominally sized against. **That reconciliation was the
headline result of #310, and it was a failure against the area budget,
recorded rather than absorbed**: the two real blocks measured 0.2546 mm^2
against PLL-FLOORPLAN.md section 5's 0.0038-0.0052 mm^2 ROM row for the same
pair, and the divider chain alone (0.2471 mm^2, drawn 2634.28 x 93.82 um) was
1.7x the entire 0.15 mm^2 die target.

Issue #341 then reduced the divider chain's height (not its width) by
reusing this block's own top-level Metal2 routing tracks across nets that do
not collide, instead of handing every net its own never-reused track --
93.82 um down to **57.07 um**, a 39 % footprint cut with no DRC/LVS change.
The two real blocks now measure 0.1578 mm^2, and the divider chain alone
(0.1503 mm^2, drawn 2634.28 x 57.07 um) is still just over the entire
0.15 mm^2 die target on its own. The full arithmetic, the (now one, not two)
remaining structural cause, and the reasoning for why folding the row is a
separate follow-up rather than attempted in the same pass are stated at the
``DIVIDER_LOCK`` definition below. This skeleton is still a floorplan record
of a design that does not fit its budget -- which is precisely what section
5's own "fail-loud condition for a future pass" asked for, and is tracked for
further reduction separately from #310's/#341's own DRC/LVS-clean geometry
claims.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_PLL_TOP_DIR = Path(__file__).resolve().parents[1] / "pll_top"
if str(_PLL_TOP_DIR) not in sys.path:
    sys.path.insert(0, str(_PLL_TOP_DIR))

# noqa: E402 below -- block.py's footprint_um()/placement()/decap_boxes_um()
# are plain Python; klayout.db is imported lazily inside the drawing functions
# only (see vco/primitives.py).
from vco import block as vco_block  # noqa: E402

TOP_CELL = "pll_floorplan_skeleton"
BOUNDARY_LAYER = (0, 0)  # DIEAREA -- no DRC rule references this layer.


@dataclass(frozen=True)
class Block:
    name: str
    x: float
    y: float
    w: float
    h: float


# Block placements (um), per PLL-FLOORPLAN.md section 1/2 (isolation +
# supply-domain separation) and section 5 (area budget, midpoint estimates).
# Signal-flow left to right: PFD/CP -> loop filter -> VCO, with the
# divider+lock-detector digital domain set apart (its own VDD_DIV trunk,
# PLL-FLOORPLAN.md section 2) rather than adjacent to the VCO.
DOMAIN_SPACING = 40.0  # um between domain guard rings/trunks (section 2)

PFD_CP = Block("pfd_cp", x=0.0, y=0.0, w=150.0, h=100.0)
# Width/height sized to actually contain its two real sub-block geometries
# below (C1 array + C2, each with margin) -- see the containment check in
# layout/tests/test_floorplan_skeleton.py.
LOOP_FILTER = Block(
    "loop_filter",
    x=PFD_CP.x + PFD_CP.w + DOMAIN_SPACING,
    y=0.0,
    w=235.0,
    h=195.0,
)
# Real VCO geometry (issues #293, #324). ``block.footprint_um()`` is the
# assembled block's own *outer* guard-ring box -- the VDD_VCO n-well ring, with
# the GND_VCO substrate ring concentric inside it -- in that block's own
# coordinates; everything the block draws is placed relative to the same
# origin, so one translation maps all of it into this skeleton's frame.
VCO_BLOCK_BOX = vco_block.footprint_um()
VCO_BLOCK_W = VCO_BLOCK_BOX[2] - VCO_BLOCK_BOX[0]
VCO_BLOCK_H = VCO_BLOCK_BOX[3] - VCO_BLOCK_BOX[1]

VCO_CORE = Block(
    "vco",
    x=LOOP_FILTER.x + LOOP_FILTER.w + DOMAIN_SPACING,
    y=0.0,
    w=VCO_BLOCK_W,
    h=VCO_BLOCK_H,
)


def _from_vco_block(name: str, box: tuple) -> Block:
    """Translate a box in ``vco/block.py``'s coordinates into this skeleton."""
    dx = VCO_CORE.x - VCO_BLOCK_BOX[0]
    dy = VCO_CORE.y - VCO_BLOCK_BOX[1]
    return Block(name, x=box[0] + dx, y=box[1] + dy, w=box[2] - box[0], h=box[3] - box[1])


_VCO_SUB_BOXES = vco_block.placement().boxes()
VCO_VTOI_CORE = _from_vco_block("vco.vtoi_core", _VCO_SUB_BOXES["vtoi_core"])
VCO_BIAS_RESISTORS = _from_vco_block("vco.bias_resistors", _VCO_SUB_BOXES["bias_resistors"])
VCO_MIRROR = _from_vco_block("vco.bandsel_mirror", _VCO_SUB_BOXES["mirror"])
VCO_RING = _from_vco_block("vco.ring", _VCO_SUB_BOXES["ring"])
VCO_BUFFER = _from_vco_block("vco.out_buffer", _VCO_SUB_BOXES["buffer"])

# VCO isolation keep-out. VCO_CORE's own boundary is now the *real* drawn
# two-sided guard ring (vco/block.py: GND_VCO substrate ring inside, VDD_VCO
# n-well tap ring outside), so this rectangle no longer stands in for that
# ring -- it is the PLL-FLOORPLAN.md section 1 keep-out around it, still sized
# at the same 15 um DF.13_MV/DF.14_MV tap-pitch bound. 15 um is also
# comfortably above NW.2b_LV's 1.4 um n-well-to-n-well spacing, which the
# outer ring now makes a real constraint on whatever abuts this block.
# (Defined here rather than below BLOCKS, as it was through #324, because
# DIVIDER_LOCK's placement now clears this keep-out -- see below.)
VCO_GUARD_MARGIN = 15.0

# --- DIVIDER_LOCK: both blocks now real, and the region reconciled (#310) ---
#
# Both occupants of this shared region now have real, DRC-clean
# transistor-level layout, so DIVIDER_LOCK below is no longer the 90x50 um
# placement-plan estimate it was through #17: it is sized to contain the two
# blocks' actual as-drawn footprints. Recorded as plain floats rather than
# computed from the generators, because this module must stay importable
# without KLayout (see the module docstring and
# layout/tests/test_floorplan_skeleton.py); the numbers come from each
# block's own committed evidence record, and
# test_divider_chain_recorded_footprint_matches_the_generator rebuilds the
# divider chain and asserts the match whenever klayout.db *is* importable, so
# the two views cannot drift silently.
#
# lock_detector (issue #296, layout/evidence/lock-detector-layout/PROOF.md):
LOCK_DETECTOR_STANDALONE_W_UM = 119.3
LOCK_DETECTOR_STANDALONE_H_UM = 62.6
# divider_chain (issue #310, layout/evidence/divider-chain-layout/PROOF.md;
# height reduced by issue #341's routing-track packing, layout/evidence/
# divider-chain-layout/PROOF-track-packing.md -- width unchanged, still one
# row of 6 div23_cell instances + 46 glue columns):
DIVIDER_CHAIN_STANDALONE_W_UM = 2634.28
DIVIDER_CHAIN_STANDALONE_H_UM = 57.07

# The two blocks are on *different supply domains* -- divider_chain on
# VDD_DIV, lock_detector on VDD (PLL-FLOORPLAN.md section 2's four-domain
# split; confirmed in both blocks' generators: divider_chain.py draws no
# VDD/VDD_VCO net at all, lock_detector/build.py draws no VDD_DIV) -- so they
# are stacked inside this region with a full DOMAIN_SPACING gap between them,
# not abutted. Sharing the region buys physical adjacency for the DIVOUT/FB
# and UP/DN signal runs, never a shared supply segment.
DIVIDER_LOCK_MARGIN = 8.0  # um clearance from the region edge (LOOP_FILTER's convention)

DIVIDER_CHAIN = Block(
    "divider_lock.divider_chain",
    x=DIVIDER_LOCK_MARGIN,
    # Above every other block's top edge (LOOP_FILTER's 195 um is the tallest;
    # the VCO's guard ring reaches 185.3 um), by one DOMAIN_SPACING.
    y=max(
        PFD_CP.y + PFD_CP.h,
        LOOP_FILTER.y + LOOP_FILTER.h,
        VCO_CORE.y + VCO_CORE.h + VCO_GUARD_MARGIN,
    )
    + DOMAIN_SPACING
    + DIVIDER_LOCK_MARGIN,
    w=DIVIDER_CHAIN_STANDALONE_W_UM,
    h=DIVIDER_CHAIN_STANDALONE_H_UM,
)
LOCK_DETECTOR = Block(
    "divider_lock.lock_detector",
    x=DIVIDER_LOCK_MARGIN,
    y=DIVIDER_CHAIN.y + DIVIDER_CHAIN.h + DOMAIN_SPACING,
    w=LOCK_DETECTOR_STANDALONE_W_UM,
    h=LOCK_DETECTOR_STANDALONE_H_UM,
)
DIVIDER_LOCK = Block(
    "divider_lock",
    x=0.0,
    y=DIVIDER_CHAIN.y - DIVIDER_LOCK_MARGIN,
    w=max(DIVIDER_CHAIN.w, LOCK_DETECTOR.w) + 2 * DIVIDER_LOCK_MARGIN,
    h=(LOCK_DETECTOR.y + LOCK_DETECTOR.h) - DIVIDER_CHAIN.y + 2 * DIVIDER_LOCK_MARGIN,
)

# FAIL-LOUD: this region is a 2.0x whole-chip area overrun, stated not absorbed.
# -----------------------------------------------------------------------------
# PLL-FLOORPLAN.md section 5 budgeted "divider chain + lock detector" at
# 0.0038-0.0052 mm^2 (a ROM std-cell-row estimate made when no physical view
# existed for either block). The two real blocks measure 0.1503 mm^2 +
# 0.0075 mm^2 = 0.1578 mm^2 -- a ~30-42x overrun on that row, and (still) more
# than the entire 0.15 mm^2 die target on the divider chain alone. Section 5's
# own "fail-loud condition for a future pass" instructs stating an overrun
# explicitly rather than silently rounding the total down, so:
#
#   * Re-running section 5's arithmetic with every measured number in place of
#     its ROM row gives 0.0369 (loop filter) + 0.0312 (VCO) + 0.020 (PFD/CP,
#     still ROM) + 0.1578 (divider+lock) = 0.2459 mm^2, i.e. 0.3074 mm^2 after
#     that section's x1.25 top-level overhead -- 2.0x the 0.15 mm^2 budget,
#     against the 2.9x this docstring recorded through issue #310 (and the
#     +22 % margin the VCO-only revision recorded before that).
#   * total_extent_um2() (this skeleton's whole bounding box) is now
#     ~1.09e6 um^2 (was ~1.19e6 um^2), still dominated by empty space: the
#     divider chain is 2634.28 um wide, ~4x the rest of the skeleton put
#     together, so its bounding box still swallows the floorplan even after
#     issue #341's height reduction below.
#
# The cause was structural and measurable, not a sizing slip, and issue #341
# closed one of the two structural causes #310 originally recorded here:
#
#   * The block is (still) one row. Six div23_cell instances (332.14 um each)
#     plus 46 glue columns are placed side by side, so the block's width is
#     the sum of every sub-cell's width -- the same "every sub-block is a
#     single row" lever the VCO docstring above already names, here at 6x the
#     length. **Unchanged by #341** -- still the next lever, and now a more
#     promising one (see below).
#   * ~57 % of the block's *height* **was** the shared per-net Metal2 track
#     band (~71 top-level nets x 0.75 um pitch = ~53 um of the 93.82 um
#     total), spanning the block's full 2634 um width. Issue #341 fixed this:
#     ``divider_chain.py``'s own top-level routing pass now calls
#     ``devgen.pack_tracks()`` instead of ``devgen.NetTracks``, reusing one
#     track_y across every net whose drawn extent does not collide (the same
#     left-edge interval-packing algorithm a channel router's track
#     assignment step uses) instead of handing out one never-reused track per
#     net regardless of how local it is. That cut the routing band from 71
#     tracks to 22 (53.25 um to 16.5 um), taking the block's total height from
#     93.82 um to **57.07 um** -- a 39 % footprint reduction with the width
#     unchanged. See layout/evidence/divider-chain-layout/
#     PROOF-track-packing.md for the full before/after and DRC/LVS re-proof.
#   * Folding the row (like #324's VCO mirror) was explicitly *not* attempted
#     here before #341, because with one track per net it would have traded
#     width for height at roughly constant area (each new row wanting its own
#     full-width band). With #341's packing, a row's own track count now
#     scales with how many *locally-colliding* nets it introduces rather than
#     its total net count, which is the precondition a future fold would need
#     to actually pay off -- filed as a follow-up (#344) rather than attempted
#     in this same pass.
#
# Nothing here is a DRC/LVS claim change: the divider chain is signoff-clean on
# the PDK's own decks at this footprint (layout/evidence/divider-chain-layout/
# PROOF-track-packing.md). It is the *area budget* that is still failing,
# loudly and on the record, which is what section 5 asked a pass like this one
# to do.
DIVIDER_LOCK_AREA_UM2 = DIVIDER_LOCK.w * DIVIDER_LOCK.h
AREA_BUDGET_UM2 = 150_000.0

BLOCKS = (PFD_CP, LOOP_FILTER, VCO_CORE, DIVIDER_LOCK)

# Loop-filter sub-geometry, real as-drawn DR-006 device footprints, placed
# inside the LOOP_FILTER block per PLL-FLOORPLAN.md section 3: the C1 2x2
# array closest to the PFD/CP boundary (charge-pump output side), C2 (MIM)
# closest to the VCO boundary (VCTRL side).
C1_DEVICE_UM = 87.0
C1_MARGIN = 8.0  # um clearance from the loop-filter block edge
C1_ARRAY = Block(
    "loop_filter.C1_array",
    x=LOOP_FILTER.x + C1_MARGIN,
    y=LOOP_FILTER.y + C1_MARGIN,
    w=2 * C1_DEVICE_UM,
    h=2 * C1_DEVICE_UM,
)
C2_DEVICE_UM = 31.4
C2_CAP = Block(
    "loop_filter.C2",
    x=C1_ARRAY.x + C1_ARRAY.w + 10.0,
    y=LOOP_FILTER.y + C1_MARGIN,
    w=C2_DEVICE_UM,
    h=C2_DEVICE_UM,
)

# VCO decap sub-geometry, real as-drawn vco.sch devices (2x cap_nmos_03v3,
# 50x50 um). These are no longer positioned by this file: vco/block.py places
# them against the assembled block's own VDD_VCO pin / n-well-tap junction
# (PLL-FLOORPLAN.md section 1) and this skeleton just translates that choice
# into its own frame, so the two views cannot drift apart. Exactly one marker
# pair exists now -- ring.py's own copy is suppressed when it is built as part
# of the block (``ring.build(draw_decap=False)``).
DECAP_DEVICE_UM = 50.0
VCO_DECAP_0, VCO_DECAP_1 = (
    _from_vco_block(f"vco.decap{i}", box) for i, box in enumerate(vco_block.decap_boxes_um())
)

# Sub-block rectangles are the assembled block's own drawn extents, so unlike
# the previous revision of this file they are genuinely disjoint -- the real,
# DRC-checked geometry is in vco/block.py's GDS, and these rectangles are its
# reference-level shadow rather than an independent estimate of it.
SUB_BLOCKS = (
    C1_ARRAY,
    C2_CAP,
    VCO_DECAP_0,
    VCO_DECAP_1,
    VCO_MIRROR,
    VCO_RING,
    VCO_BUFFER,
    VCO_VTOI_CORE,
    VCO_BIAS_RESISTORS,
    DIVIDER_CHAIN,
    LOCK_DETECTOR,
)


def build(outdir: Path) -> Path:
    """Assemble ``pll_floorplan_skeleton.gds`` under ``outdir``."""
    import klayout.db as db  # imported lazily, same convention as harness/cell.py

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    layout = db.Layout()
    layout.dbu = 0.001  # 1 nm/dbu, matches the PDK's stdcell GDS convention
    dbu_per_um = int(round(1.0 / layout.dbu))
    li = layout.layer(*BOUNDARY_LAYER)

    top = layout.create_cell(TOP_CELL)

    def add_block(block: Block) -> None:
        box = db.Box(
            int(round(block.x * dbu_per_um)),
            int(round(block.y * dbu_per_um)),
            int(round((block.x + block.w) * dbu_per_um)),
            int(round((block.y + block.h) * dbu_per_um)),
        )
        top.shapes(li).insert(box)
        label_x = int(round((block.x + 1.0) * dbu_per_um))
        label_y = int(round((block.y + 1.0) * dbu_per_um))
        top.shapes(li).insert(db.Text(block.name, db.Trans(db.Vector(label_x, label_y))))

    for block in BLOCKS:
        add_block(block)

    # VCO guard ring: outer boundary only (a hollow ring is four rectangles;
    # since this layer carries no DRC rule, an outer reference boundary
    # communicates the same floorplan intent without extra geometry).
    guard = Block(
        "vco.guard_ring",
        x=VCO_CORE.x - VCO_GUARD_MARGIN,
        y=VCO_CORE.y - VCO_GUARD_MARGIN,
        w=VCO_CORE.w + 2 * VCO_GUARD_MARGIN,
        h=VCO_CORE.h + 2 * VCO_GUARD_MARGIN,
    )
    add_block(guard)

    for block in SUB_BLOCKS:
        add_block(block)

    gds_path = outdir / f"{TOP_CELL}.gds"
    options = db.SaveLayoutOptions()
    options.select_cell(top.cell_index())
    options.format = "GDS2"
    layout.write(str(gds_path), options)

    return gds_path


def total_extent_um2(blocks: tuple[Block, ...] = BLOCKS) -> float:
    """Bounding-box area of the whole skeleton, for a sanity cross-check
    against PLL-FLOORPLAN.md's area-budget table (not the same number --
    this includes inter-domain spacing the budget's overhead multiplier
    accounts for separately, so it is expected to run larger).

    ``blocks`` defaults to every top-level block. It is a parameter so a
    caller can scope the measurement to a subset -- specifically, so the VCO's
    own fold-regression tripwires in ``layout/tests/test_vco_layout.py`` can
    keep measuring the pre-#310 extent (``BLOCKS`` minus ``DIVIDER_LOCK``)
    after the real divider chain came to dominate the full number by ~9x. The
    unscoped default is still the honest whole-skeleton figure, and is what
    ``test_floorplan_skeleton.py`` asserts the recorded overrun against.
    """
    xs = [b.x for b in blocks] + [b.x + b.w for b in blocks]
    ys = [b.y for b in blocks] + [b.y + b.h for b in blocks]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


#: ``BLOCKS`` minus the divider/lock region -- the scope the VCO's own
#: area tripwires measure, so they keep tracking the VCO row fold rather than
#: the divider chain's much larger footprint. See ``total_extent_um2()``.
BLOCKS_EXCLUDING_DIVIDER_LOCK = tuple(b for b in BLOCKS if b is not DIVIDER_LOCK)
