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

Divider/lock real geometry, and a budget overrun -- 2.9x, then 2.0x, now
1.9x (issues #296, #310, #341, #344)
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
93.82 um down to 57.07 um, a 39 % footprint cut with no DRC/LVS change. That
left the block at 0.1503 mm^2, still just over the entire 0.15 mm^2 die
target on its own, with one structural cause outstanding: it was still a
single row, so its width was the sum of every sub-cell's width.

Issue #344 closed that one too, by folding the row in two -- three
``div23_cell`` instances per row, each row carrying its own #341-packed
routing band, with the glue logic interleaved next to the instances it wires
rather than parked at one end. That left the block at **1317.66 x 100.29 um
= 0.1321 mm^2**, a further 12 % cut, and for the first time it fit inside
the whole-chip 0.15 mm^2 target *on its own* -- which is a necessary, not a
sufficient, condition for the chip to fit. Issue #454 then packed the
``div23_cell`` macro's own Metal2 track band the same way #341 had packed
the top-level bands, taking the block to **1317.66 x 70.29 um = 0.0926
mm^2**, a further 30 %. Issue #458 took the last of that lever by making
both levels' track assignment *obstacle-aware*
(``devgen.pack_tracks_over_devices()``): a track is placed at the lowest
Metal2-free y rather than in a band stacked above the device rows, so most
of both bands now hide in the Metal2-free corridors those rows already
leave. **1317.66 x 41.99 um = 0.0553 mm^2**, a further 40 %. The full
arithmetic, and what is still structurally oversized, are stated at the
``DIVIDER_LOCK`` definition below -- it is **not** device density: that
hypothesis stood here through #344 and was falsified by measurement at #442
(the diffusion islands are ~1 % of the block's own bounding box, not the
bulk of it). This skeleton is still a floorplan record of a design that does
not fit its budget -- which is precisely what section 5's own "fail-loud
condition for a future pass" asked for, and is tracked for further reduction
separately from #310's/#341's/#344's/#454's/#458's own DRC/LVS-clean
geometry claims.
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

# Real pfd_cp geometry (issue #386): pfd (#300, mirror-symmetric PFD layout)
# assembled with the complete cp block (#385, cp_output_stage + cp_dumpbuf)
# into one flat, standalone-DRC-clean block matching design/pfd_cp.sch's
# top-level netlist -- layout/pll_top/pfd_cp/block.py,
# layout/evidence/pfd-cp-layout/PROOF.md. Recorded as plain floats rather
# than calling pfd_cp.block.build() (which needs klayout.db to place/flatten
# the two sub-blocks at the GDS level, unlike vco/block.py's own plain-Python
# footprint_um()) -- same convention as DIVIDER_CHAIN_STANDALONE_W_UM/H_UM
# below; layout/tests/test_floorplan_skeleton.py's own
# RecordedFootprintDriftTests rebuilds the block and asserts the match
# whenever klayout.db *is* importable, so the two views cannot drift
# silently.
#
# FAIL-LOUD: 347.41 x 75.48 um (26,220.77 um^2 = 0.0262 mm^2) against
# PLL-FLOORPLAN.md section 5's 0.010-0.020 mm^2 ROM estimate -- still a
# 1.31-2.62x overrun, stated here rather than silently absorbed, following
# the same "FAIL-LOUD condition for a future pass" convention the VCO/
# divider-chain docstrings above already use. See PLL-FLOORPLAN.md section
# 5's own revision notes for the re-run whole-chip arithmetic.
#
# Was 434.31 x 80.73 um (0.0351 mm^2) through issue #386. Issue #455 folded
# pfd into cp's own empty band above cp_dumpbuf (so the block is now exactly
# as wide as cp) and continued cp's own Metal2 trunk band rather than
# starting a fresh one above it: -86.90 um of width and -4.50 um of height,
# -8,578 um^2 (-24.5 %) on the footprint tuple this constant records. See
# layout/evidence/pfd-cp-layout/PROOF-455-fold.md.
#
# Issue #469 then packed cp_output_stage's own glue-bus track band (14 nets
# on 13 tracks instead of 14, cp_array.pack_tracks() in place of NetTracks),
# which is one track of cp_output_stage height and therefore one track of
# this block's: 76.23 -> 75.48 um, -261 um^2 (-1.0 %). The band's clique
# number is 13, not the 9 #455 sized from the bus spans alone, because this
# block's own array<->glue link extends six of the fourteen nets across its
# full width -- see layout/evidence/pfd-cp-layout/
# PROOF-469-glue-bus-packing.md.
PFD_CP_STANDALONE_W_UM = 347.41
PFD_CP_STANDALONE_H_UM = 75.48
PFD_CP = Block("pfd_cp", x=0.0, y=0.0, w=PFD_CP_STANDALONE_W_UM, h=PFD_CP_STANDALONE_H_UM)
# LOOP_FILTER's width/height are sized to actually contain its two real
# sub-block geometries below (C1 array + C2, each with margin) -- see the
# containment check in layout/tests/test_floorplan_skeleton.py.
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
# lock_detector (issue #296, layout/evidence/lock-detector-layout/PROOF.md;
# grown from 119.30 x 62.60 um by issue #449, which drew DR-014's 4-bit trim
# network into delaywin_3v3 -- 45 devices to 117, and with it the block's
# first LVS match against its own committed schematic. See that record's
# "Addendum 4" for the full before/after and PLL-FLOORPLAN.md section 5.7 for
# what it does to the area arithmetic: ~4.1x this block's own footprint, and
# the whole-chip overrun from 1.9x to 2.1x):
LOCK_DETECTOR_STANDALONE_W_UM = 294.80
LOCK_DETECTOR_STANDALONE_H_UM = 103.75
# divider_chain (issue #310, layout/evidence/divider-chain-layout/PROOF.md;
# height reduced by issue #341's routing-track packing, layout/evidence/
# divider-chain-layout/PROOF-track-packing.md; then folded from one row into
# two by issue #344, layout/evidence/divider-chain-layout/PROOF-fold.md --
# 2634.28 x 57.07 um before the fold, 1317.66 x 100.29 um after; then the
# same packing applied one level down, inside the div23_cell macro each row's
# height is gated by, at issue #454 -- 15.00 um off each of the two rows,
# 1317.66 x 70.29 um, layout/evidence/divider-chain-layout/
# PROOF-macro-track-packing.md; then both levels' track assignment made
# obstacle-aware at issue #458, so a track sits at the lowest Metal2-free y
# instead of in a band above the device rows -- 1317.66 x 41.99 um,
# layout/evidence/divider-chain-layout/PROOF-over-device-rows.md):
DIVIDER_CHAIN_STANDALONE_W_UM = 1317.66
DIVIDER_CHAIN_STANDALONE_H_UM = 41.99

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

# FAIL-LOUD: this region drove a whole-chip area overrun against the draft
# 0.15 mm^2 target -- 2.9x at its worst, 1.82x as drawn today -- which is why
# spec/pll.md#area is now **0.30 mm^2** (DR-016, issue #456).
# -----------------------------------------------------------------------------
# READ THE NEXT PARAGRAPHS AS HISTORICAL. Every "1.89x", "0.15 mm^2" and
# "0.2272 mm^2" figure below was correct against the target and the geometry in
# force when it was written, and is kept rather than rewritten, per
# PLL-FLOORPLAN.md's append-only revision convention. The current position, all
# of it measured off committed GDS by ``python3 layout/run_pv.py area``:
#
#   * loop filter 36,936 (a DR-006 calculation) + vco_block 31,826 + pfd_cp
#     26,406 (folded at #455, was 35,281; glue bus packed at #469, was 26,665)
#     + divider_chain 55,329 (tracks routed over the device rows at #458, was
#     92,618) + lock_detector 30,586 = **181,083 um^2**, i.e.
#     **226,354 um^2 (0.2264 mm^2)** after this section's x1.25 -- **1.51x** the
#     draft target and **75.5 %** of the amended 0.30 mm^2 row. PLL-FLOORPLAN.md
#     sections 5.11 (DR-016, on 218,631 um^2), 5.12 (#469, on 218,372 um^2) and
#     5.13 (#458, this figure) carry the derivation.
#   * The draft target was not reachable, and that is a measurement rather than
#     a projection: strike Metal2 routing entirely and each block's own drawn
#     device bands still sum (with the loop filter) to 136,141 um^2 ->
#     170,176 um^2, 1.13x the draft target. 57.2 % of what that target allowed
#     is the loop filter (capacitance-set, DR-006) plus vco_block's guard-ring
#     and tap spacing -- neither a layout lever.
#   * ``test_area_audit.py`` now re-derives that sum from the committed GDS on
#     every run and asserts it against ``AREA_BUDGET_BLOCK_SUM_UM2`` below, so
#     geometry growing past the amended row is a red build rather than a note
#     nobody re-read.
#
# The historical record follows.
#
# PLL-FLOORPLAN.md section 5 budgeted "divider chain + lock detector" at
# 0.0038-0.0052 mm^2 (a ROM std-cell-row estimate made when no physical view
# existed for either block). The two real blocks measure 0.0926 mm^2 +
# 0.0306 mm^2 = 0.1232 mm^2 -- a ~24-32x overrun on that row. Section 5's own
# "fail-loud condition for a future pass" instructs stating an overrun
# explicitly rather than silently rounding the total down, so:
#
#   * Re-running section 5's arithmetic with every measured number in place of
#     its ROM row gives 0.0369 (loop filter) + 0.0318 (VCO) + 0.0353 (PFD/CP,
#     real since #385/#386) + 0.1232 (divider+lock) = 0.2272 mm^2, i.e.
#     0.2840 mm^2 after that section's x1.25 top-level overhead -- 1.89x the
#     0.15 mm^2 budget (PLL-FLOORPLAN.md section 5.9), against the 1.70x
#     section 5.8 recorded (divider-chain packing lever alone, old
#     lock_detector footprint), the 2.03x section 5.5 re-derived from the
#     committed GDS, the 2.0x recorded through issue #341 and the 2.9x
#     through #310 (and the +22 % margin the VCO-only revision recorded
#     before those).
#   * total_extent_um2() (this skeleton's whole bounding box) is now
#     ~0.63e6 um^2 (was ~0.57e6 through #454 alone, ~0.61e6 through #344,
#     ~1.09e6 through #341, ~1.19e6 through #310). lock_detector's own growth
#     (119.30 x 62.60 um to 294.80 x 103.75 um) pushes this region's own
#     extent back up even though the divider chain's packing pulled it down;
#     the divider chain still does not swallow the floorplan on its own: at
#     1317.66 um it is ~2x the rest of the skeleton rather than ~4x.
#   * **This is not a placement regression.** Issue #449 drew DR-014's 4-bit
#     static process trim network into ``lock_detector``'s ``delaywin_3v3``
#     -- 45 drawn devices to 117 -- which is what finally let that block
#     match its own ratified schematic under the PDK's LVS deck. The block
#     went from 119.30 x 62.60 um to 294.80 x 103.75 um (~4.1x) for it.
#     Recorded here rather than absorbed, per the same instruction as every
#     line above; PLL-FLOORPLAN.md section 5.9 has the full arithmetic and
#     names which of the remaining levers sections 5.5/5.8 identified would
#     recover it.
#
# The cause was structural and measurable, not a sizing slip. #310 recorded two
# structural causes here; #341 closed one and #344 the other:
#
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
#     93.82 um to 57.07 um -- a 39 % footprint reduction with the width
#     unchanged. See layout/evidence/divider-chain-layout/
#     PROOF-track-packing.md for the full before/after and DRC/LVS re-proof.
#   * The block **was** one row: six div23_cell instances (332.14 um each)
#     plus 46 glue columns placed side by side, so its width was the sum of
#     every sub-cell's width -- the same "every sub-block is a single row"
#     lever the VCO docstring above already names, here at 6x the length.
#     Issue #344 folded it into two rows of three instances, each row with its
#     own packed band, and moved the glue logic in beside the instances it
#     wires instead of leaving it all at one end (which had made every chain
#     net run the block's full width). 2634.28 x 57.07 um became
#     **1317.66 x 100.29 um** -- 0.1503 mm^2 down to 0.1321 mm^2, a further
#     12 %. The fold pays off only *because* #341 landed first: with one
#     never-reused track per net, a second row would have wanted its own
#     full-width band and the fold would have traded width for height at
#     roughly constant area. See layout/evidence/divider-chain-layout/
#     PROOF-fold.md.
#   * #341's packing was never applied one level *down*, inside the
#     ``div23_cell`` macro each row's height is gated by. Measured at issue
#     #442 and fixed at issue #454: that macro's own band was 46.50 um of the
#     100.29 um (31 nets x 0.75 um, paid once per row), against only 16.50 um
#     for the already-packed top-level bands. ``pack_tracks()`` puts those 31
#     nets on 11 tracks -- the interval graph's clique number, so provably the
#     minimum -- for 15.00 um per instance, 30.00 um off the block.
#     **1317.66 x 100.29 um became 1317.66 x 70.29 um**, 0.1321 mm^2 down to
#     0.0926 mm^2, a further 30 %. See layout/evidence/divider-chain-layout/
#     PROOF-macro-track-packing.md.
#   * Both of those bands were still *bands* -- stacked on top of the device
#     rows, whose own Metal2 plane #442 measured 1.0 % occupied. Metal2 has no
#     DRC relationship to the diffusion/poly/well/Metal1 under it, so that
#     plane was unused, not reserved; what a track there must clear is other
#     Metal2, namely the Via1/Metal2 landing square every riser drops on every
#     pad plus each placed div23_cell instance's own interior. Issue #458
#     replaced both levels' ``pack_tracks()`` call with
#     ``pack_tracks_over_devices()``, which takes that obstacle map explicitly
#     and gives each net the lowest 0.75 um step whose drawn rectangle clears
#     it. On this package's fixed row-cell frame the widest free corridor is
#     the one between the pulldown and pullup device rows: 10 of div23_cell's
#     11 tracks land below its own topmost pad (footprint 332.14 x 22.80 ->
#     332.14 x 12.52 um) and the top level keeps only the nets whose extent
#     crosses an instance in a band above.
#     **1317.66 x 70.29 um became 1317.66 x 41.99 um**, 0.0926 mm^2 down to
#     0.0553 mm^2, a further 40 %. See layout/evidence/divider-chain-layout/
#     PROOF-over-device-rows.md.
#
# What is left is NOT device density. That hypothesis stood here through #344
# and was **falsified** by measurement at issue #442 (layout/evidence/
# area-audit/PROOF.md, PLL-FLOORPLAN.md section 5.5): the ~292 um^2/transistor
# ratio it rested on cannot distinguish "the diffusion islands are too big"
# from "the islands are 1 % of the block and the rest is empty", and the block
# measures the latter -- comp is 1.46 % of the bbox, and merging every one of
# the 40 shared-diffusion candidates in divider_chain.spice would free 125.4
# um^2, about 0.1 % of what has to come out. layout/tests/test_area_audit.py
# asserts that bound so this conclusion fails loudly if geometry ever changes
# it.
#
# What is actually left is the remaining Metal2 band: 43 distinct tracks still
# sitting in 43.97 um of no-diffusion band *above* 26.32 um of device rows,
# with the Metal2 plane over those rows 1.0 % occupied. Routing the band over
# the cells rather than above them is the next lever, and a riskier one (a bus
# at a device-band track_y can cross another net's own Metal2 riser landing
# square); it is tracked at issue #458, deliberately not folded into any of the
# passes above.
#
# Nothing here is a DRC/LVS claim change: the divider chain is signoff-clean on
# the PDK's own decks at this footprint (layout/evidence/divider-chain-layout/
# PROOF-macro-track-packing.md, which also adds an --offgrid DRC-clean run the
# block did not previously claim). It is the *area budget* that is still failing, loudly and on
# the record, which is what section 5 asked a pass like this one to do -- and
# it is now failing by less: the divider chain on its own finally fits inside
# the 0.15 mm^2 whole-chip target, which is necessary but not sufficient for
# the chip to.
DIVIDER_LOCK_AREA_UM2 = DIVIDER_LOCK.w * DIVIDER_LOCK.h

#: ``spec/pll.md#area``'s whole-block target, **amended by DR-016 (issue #456)**
#: from the draft 150,000 um^2 on the measured post-lever total. Every "0.15
#: mm^2" sentence in the comment block above and in PLL-FLOORPLAN.md sections
#: 5.1-5.10 predates that amendment and is kept as written; section 5.11 states
#: the amendment and section 5.13 the live measurement under it.
AREA_BUDGET_UM2 = 300_000.0

#: The draft target the overrun series above is written against. Kept as its own
#: name because several assertions are statements about *that* number ("the
#: divider chain alone no longer busts the whole-chip target") and mean nothing
#: if silently re-pointed at the amended one.
AREA_BUDGET_DRAFT_UM2 = 150_000.0

#: PLL-FLOORPLAN.md section 5's top-level overhead multiplier (guard ring,
#: four-domain supply trunk routing, block-to-block spacing). Still a ROM
#: estimate: no assembled pll_top GDS exists to measure it against (issue #17).
TOP_LEVEL_OVERHEAD = 1.25

#: What the amended row allows as a *sum of block footprints*, i.e. before the
#: overhead multiplier above. 240,000 um^2.
AREA_BUDGET_BLOCK_SUM_UM2 = AREA_BUDGET_UM2 / TOP_LEVEL_OVERHEAD

#: The loop filter's contribution to that sum: DR-006 / PLL-FLOORPLAN.md
#: section 3's 32,118 um^2 device sum (R 856 + C1 30,276 + C2 986) x1.15 for
#: bulk taps and interconnect. A **calculation, not a layout** -- the loop
#: filter has no drawn cell -- which is why it is a constant here rather than a
#: GDS the area audit measures.
LOOP_FILTER_AREA_UM2 = 36_936.0

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

#: ``BLOCKS_EXCLUDING_DIVIDER_LOCK`` further scoped to exclude ``PFD_CP`` --
#: the VCO fold-regression tripwires need a measurement immune to *any*
#: other block's own real-geometry growth, not just ``DIVIDER_LOCK``'s.
#: Issue #386's ``pfd_cp`` assembly grew ``PFD_CP.w`` from its 150 um
#: placement-plan placeholder to its own real 434.31 um footprint, which --
#: laid out left of ``LOOP_FILTER``/``VCO_CORE`` in one row -- shifted the
#: combined bounding box exactly the way ``DIVIDER_LOCK``'s own growth did
#: at #310. This scope is immune to that shift by construction:
#: ``LOOP_FILTER.x`` is defined as ``PFD_CP.x + PFD_CP.w + DOMAIN_SPACING``,
#: so ``LOOP_FILTER``/``VCO_CORE``'s own combined width
#: (``VCO_CORE.x + VCO_CORE.w - LOOP_FILTER.x``) cancels ``PFD_CP.w`` out
#: entirely and depends only on ``LOOP_FILTER``'s own fixed 235 um width,
#: ``DOMAIN_SPACING`` and ``VCO_CORE.w``. ``PFD_CP``'s own overrun is
#: tracked separately by ``test_floorplan_skeleton.py``, same as
#: ``DIVIDER_LOCK``'s.
VCO_FOLD_TRIPWIRE_BLOCKS = tuple(b for b in BLOCKS_EXCLUDING_DIVIDER_LOCK if b is not PFD_CP)


def main() -> int:
    """``python3 -m floorplan.skeleton --outdir <dir>`` -- write the skeleton.

    The same ``--outdir`` calling convention every other generator in this
    repository exposes (``pll_top/lock_detector/build.py``,
    ``pll_top/vco/block.py``, ...), and therefore the one
    ``harness/reproduce.py`` invokes as a subprocess to re-derive each
    committed artifact. Through issue #398 this module had ``build()`` but
    no CLI, so its evidence directory documented regeneration as an ad-hoc
    ``python3 -c`` one-liner that ``reproduce.py`` could not call -- which
    is why this was the one committed block GDS the reproducibility guard
    (issue #451) had to exclude by name rather than check. Added at issue
    #461 together with the regenerated artifact.
    """
    import argparse

    parser = argparse.ArgumentParser(description="write pll_floorplan_skeleton.gds")
    parser.add_argument("--outdir", default="/tmp/pll_floorplan_skeleton")
    args = parser.parse_args()

    gds_path = build(Path(args.outdir))
    print(f"wrote {gds_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
