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

VCO real geometry (issue #293)
-------------------------------
``VCO_CORE`` is no longer a placeholder rectangle. ``layout/pll_top/vco/
block.py`` assembles all five VCO sub-blocks -- the 5-stage ring, the
common-centroid band-select mirror, the 3-stage output buffer, the
``RCG``/``ROFF``/``RDEG`` poly resistors and the V-to-I core -- into one
wired, DRC-clean layout under one block-level ``GND_VCO`` guard ring, and
``VCO_CORE`` below is *that block's own guard-ring box*, not an estimate.
Every sub-block rectangle in ``SUB_BLOCKS`` is likewise its real drawn
extent, translated out of the block's own coordinates. All of it comes from
plain-Python ``footprint_um()``/``placement()`` calls, so this file still
imports no KLayout.

**The real block is 294.8 x 148.2 um = 43,680 um^2, against PLL-FLOORPLAN.md
section 5's ROM row of 0.011-0.017 mm^2 for the whole VCO -- a 2.6-4.0x
overrun.** That record's own section 5 names this case in advance ("if real
per-block layout pushes the conservative estimate's ~34 % margin below zero
... the next floorplan revision should state the overrun explicitly rather
than silently rounding the total down"), so it is stated here rather than
absorbed:

* Re-running section 5's own arithmetic with the measured VCO number in
  place of its ROM row gives a block subtotal of ~0.111 mm^2 conservative
  (0.0369 loop filter + 0.0437 VCO + 0.020 PFD/CP + 0.0052 divider+lock),
  ~0.139 mm^2 after that section's x1.25 top-level overhead -- still inside
  the 0.15 mm^2 budget, but with the margin down from ~34 % to ~7 %.
* ``total_extent_um2()`` (this skeleton's whole bounding box, a deliberately
  looser number than the budget table -- see that function's own docstring)
  lands at ~148,000 um^2, i.e. ~1 % under the 150,000 um^2 target where it
  previously had ~3 %.

The cause is structural and already recorded per sub-block: every device is
drawn as its own diffusion island wired by metal (see
``vco/primitives.py``'s module docstring), and each sub-block is a single
row, so the band-select mirror alone is 266 um wide and sets the whole
block's width. Folding those rows is the identified next area optimisation
and is not issue #293's scope.
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
# Real VCO geometry (issue #293). ``block.footprint_um()`` is the assembled
# block's own guard-ring box, in that block's own coordinates; everything the
# block draws is placed relative to the same origin, so one translation maps
# all of it into this skeleton's frame.
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
DIVIDER_LOCK = Block(
    "divider_lock",
    x=0.0,
    y=PFD_CP.h + DOMAIN_SPACING,
    w=90.0,
    h=50.0,
)

# lock_detector (issue #296) now has a real, DRC-clean standalone
# transistor-level layout -- see layout/pll_top/lock_detector/build.py and
# layout/evidence/lock-detector-layout/PROOF.md. Its as-drawn standalone
# footprint (119.3 x 62.6 um, ~7,468 um^2) is *larger on its own* than
# DIVIDER_LOCK's 90x50 um placement-plan estimate above -- which
# divider_chain (#295, real layout not yet landed) also shares. Not
# reconciled into DIVIDER_LOCK's own rectangle here: per both issues'
# Acceptance Criteria, whichever of #295/#296 lands second is responsible
# for reconciling the region's real combined footprint against the other's
# actual layout. #296 landed first, so this reconciliation is still open --
# do not assume DIVIDER_LOCK's dimensions above reflect either block's real
# geometry yet.
LOCK_DETECTOR_STANDALONE_W_UM = 119.3
LOCK_DETECTOR_STANDALONE_H_UM = 62.6

BLOCKS = (PFD_CP, LOOP_FILTER, VCO_CORE, DIVIDER_LOCK)

# VCO isolation keep-out. VCO_CORE's own boundary is now the *real* drawn
# GND_VCO guard ring (vco/block.py), so this rectangle no longer stands in for
# that ring -- it is the PLL-FLOORPLAN.md section 1 keep-out around it, still
# sized at the same 15 um DF.13_MV/DF.14_MV tap-pitch bound.
VCO_GUARD_MARGIN = 15.0

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


def total_extent_um2() -> float:
    """Bounding-box area of the whole skeleton, for a sanity cross-check
    against PLL-FLOORPLAN.md's area-budget table (not the same number --
    this includes inter-domain spacing the budget's overhead multiplier
    accounts for separately, so it is expected to run larger)."""
    xs = [b.x for b in BLOCKS] + [b.x + b.w for b in BLOCKS]
    ys = [b.y for b in BLOCKS] + [b.y + b.h for b in BLOCKS]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))
