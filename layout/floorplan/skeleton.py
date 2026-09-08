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

VCO ring real geometry (issue #293)
------------------------------------
``layout/pll_top/vco/ring.py`` now draws real, DRC-clean transistor-level
layout for the VCO's 5-stage current-starved ring, its own dedicated guard
ring, and the carried-forward decap -- see that module's docstring for the
full scope (the bias generator, band-select mirror, and output buffer are
deferred to follow-up issues). ``VCO_RING`` below is that real footprint
(``ring.footprint_um()``, plain-Python, no KLayout import needed), placed at
``VCO_CORE``'s own origin -- **augmenting**, not replacing, ``VCO_CORE``:
the ring alone does not need the full block, and the bias
generator/mirror/buffer this pass defers still have to land somewhere
inside (or beside) it.

**Real footprint deviates from the 140x100 um ROM estimate, disclosed
explicitly rather than silently absorbed**: the ring's real layout is
~177 x 19 um -- much *wider* (5 stages placed in one row, full-custom, each
its own diffusion island wired by Metal1 -- see ``primitives.py``'s module
docstring for why) and much *shorter* (the ring alone is a thin horizontal
band; the ROM box's 100 um height assumed room for every VCO sub-block
stacked together, not the ring in isolation) than the original square
guess. ``VCO_CORE.w`` is widened here to stay a real (not stale) bound on
the ring's own width; its height is left at the ROM value since the
bias generator/mirror/buffer (not yet real geometry) are what the
remaining vertical room is reserved for. Whether the eventual full VCO
block folds the ring into more than one row to recover width is a
follow-up layout decision, not a placeholder-vs-real correctness question
this record has to resolve.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_PLL_TOP_DIR = Path(__file__).resolve().parents[1] / "pll_top"
if str(_PLL_TOP_DIR) not in sys.path:
    sys.path.insert(0, str(_PLL_TOP_DIR))

from vco import ring as vco_ring  # noqa: E402 -- plain-Python footprint_um(), no KLayout needed

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
# Real ring footprint (issue #293) -- see this module's docstring for why
# VCO_CORE.w is widened to it rather than left at the stale 140 um ROM
# guess. footprint_um() returns (x0, y0, x1, y1) relative to the ring's own
# origin; VCO_RING places that at VCO_CORE's own (x, y).
_ring_x0, _ring_y0, _ring_x1, _ring_y1 = vco_ring.footprint_um()
VCO_RING_W = _ring_x1 - _ring_x0
VCO_RING_H = _ring_y1 - _ring_y0

VCO_CORE = Block(
    "vco",
    x=LOOP_FILTER.x + LOOP_FILTER.w + DOMAIN_SPACING,
    y=0.0,
    w=max(140.0, VCO_RING_W + 2 * 5.0),  # +5 um clearance margin each side
    h=100.0,
)
VCO_RING = Block(
    "vco.ring",
    x=VCO_CORE.x,
    y=VCO_CORE.y,
    w=VCO_RING_W,
    h=VCO_RING_H,
)
DIVIDER_LOCK = Block(
    "divider_lock",
    x=0.0,
    y=PFD_CP.h + DOMAIN_SPACING,
    w=90.0,
    h=50.0,
)

BLOCKS = (PFD_CP, LOOP_FILTER, VCO_CORE, DIVIDER_LOCK)

# VCO guard ring: a 15 um ring (PLL-FLOORPLAN.md section 1's tap-pitch bound)
# drawn as the VCO block's own boundary rectangle expanded outward.
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
# 50x50 um), placed at the VDD_VCO entry point inside the guard ring
# (PLL-FLOORPLAN.md section 1) -- here taken as the block edge nearest the
# loop-filter/VCTRL boundary, i.e. the block's own left edge. Side by side
# (not stacked) so both fit within the VCO block's 100 um height.
DECAP_DEVICE_UM = 50.0
DECAP_MARGIN = 5.0
VCO_DECAP_0 = Block(
    "vco.decap0",
    x=VCO_CORE.x + DECAP_MARGIN,
    y=VCO_CORE.y + DECAP_MARGIN,
    w=DECAP_DEVICE_UM,
    h=DECAP_DEVICE_UM,
)
VCO_DECAP_1 = Block(
    "vco.decap1",
    x=VCO_DECAP_0.x + VCO_DECAP_0.w + 2.0,
    y=VCO_CORE.y + DECAP_MARGIN,
    w=DECAP_DEVICE_UM,
    h=DECAP_DEVICE_UM,
)

# VCO_RING is drawn in addition to (not instead of) VCO_DECAP_0/1 above:
# VCO_DECAP_0/1 are this skeleton's own long-standing decap markers (#17),
# left untouched so the tests that already pin their exact geometry keep
# passing; VCO_RING (#293) is the newer, more detailed real-ring footprint,
# which happens to spatially overlap them within this reference-only
# boundary-layer drawing -- harmless, since layer (0, 0) carries no DRC rule
# and this file has never claimed sub-blocks are mutually disjoint (only
# that C1_ARRAY/C2_CAP sit inside LOOP_FILTER and VCO_DECAP_0/1 don't
# overlap *each other* -- see layout/tests/test_floorplan_skeleton.py). The
# real, non-overlapping, DRC-checked version of both lives in
# layout/pll_top/vco/ring.py's own GDS, not here.
SUB_BLOCKS = (C1_ARRAY, C2_CAP, VCO_DECAP_0, VCO_DECAP_1, VCO_RING)


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
