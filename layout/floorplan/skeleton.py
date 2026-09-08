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

VCO sub-block real geometry (issue #293)
-----------------------------------------
``layout/pll_top/vco/`` now draws real, DRC-clean transistor-level layout for
all four of the VCO's sub-blocks, each with its own dedicated guard ring and
each provable standalone:

===================  ==============================  ====================
Block                Generator                       Real footprint (um)
===================  ==============================  ====================
``VCO_RING``         ``vco/ring.py``                 177.4 x 18.7
``VCO_MIRROR``       ``vco/mirror.py``               269.9 x 37.1
``VCO_BUFFER``       ``vco/buffer.py``               31.7 x 13.3
``VCO_VTOI_CORE``    ``vco/vtoi_core.py``            121.2 x 50.7
===================  ==============================  ====================

(``vco/bias_resistors.py``'s ``RCG``/``ROFF``/``RDEG`` trio, 13.0 x 40.3 um,
is drawn as a fifth standalone block but not yet folded into this skeleton --
see that module's own docstring for why: it is one piece of the bias
generator, not a complete sub-block, until it is wired to ``VCO_VTOI_CORE``'s
own ``NC``/``NOFF``/``NVI`` pins.)

Each footprint comes from that module's plain-Python ``footprint_um()``, so
this file still imports no KLayout. They **augment** ``VCO_CORE`` rather than
replacing it: the inter-sub-block wiring that will merge all of these (plus
``bias_resistors.py``) under one shared guard ring, and the combined block's
own standalone DRC run, are issue #293's own remaining scope.

**Real footprints deviate from the 140x100 um ROM estimate, disclosed
explicitly rather than silently absorbed.** Every one of the four is much
*wider* than the square ROM guess, for the same reason: these are
single-row full-custom layouts, each transistor its own diffusion island
wired by Metal1 (see ``vco/primitives.py``'s module docstring), so a block
that the ROM budget imagined as a compact square comes out as a long thin
band. ``VCO_CORE.w`` is widened here to the widest of them plus clearance --
140 -> ~280 um, still driven by the band-select mirror -- while
``VCO_CORE.h`` grows past the ROM's 100 um value for the first time: four
real sub-blocks stacked with margin no longer fit in it (the V-to-I core's
own 50.7 um height, driven by ``MSU1``'s deliberately long L=20 um channel,
is the largest single addition -- see ``vtoi_core.py``'s own module
docstring).

**Consequence worth stating plainly**: ``VCO_CORE``'s *own* rectangle grows
from 27,986 um^2 (279.86 x 100 um, three sub-blocks) to 40,514 um^2
(279.86 x 144.78 um, four), a ~45% increase driven almost entirely by the
V-to-I core's height. ``total_extent_um2()`` itself does **not** move
(145,247.7 um^2 either way) -- the whole-skeleton bounding box this
function reports is dominated by ``LOOP_FILTER``'s own 195 um height, not
``VCO_CORE``'s, so this growth has not yet crossed PLL-FLOORPLAN.md
section 5's 0.15 mm^2 draft target at the *skeleton* level. It is real
headroom being consumed at the *block* level, though: folding these
single-row blocks into multiple rows (the previously identified next area
optimization) becomes relevant sooner, since ``VCO_CORE``'s own height has
room only up to ``LOOP_FILTER.h`` (195 um) before it, rather than
``LOOP_FILTER``, becomes the skeleton's own height driver.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_PLL_TOP_DIR = Path(__file__).resolve().parents[1] / "pll_top"
if str(_PLL_TOP_DIR) not in sys.path:
    sys.path.insert(0, str(_PLL_TOP_DIR))

# noqa: E402 below -- each module's footprint_um() is plain Python; klayout.db
# is imported lazily inside the drawing functions only (see vco/primitives.py).
from vco import buffer as vco_buffer  # noqa: E402
from vco import mirror as vco_mirror  # noqa: E402
from vco import ring as vco_ring  # noqa: E402
from vco import vtoi_core as vco_vtoi_core  # noqa: E402

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
# Real VCO sub-block footprints (issue #293) -- see this module's docstring
# for why VCO_CORE.w is widened to them rather than left at the stale 140 um
# ROM guess. Each footprint_um() returns (x0, y0, x1, y1) relative to that
# block's own origin; only the extents are used here.
def _extent(footprint) -> tuple[float, float]:
    x0, y0, x1, y1 = footprint
    return (x1 - x0, y1 - y0)


VCO_RING_W, VCO_RING_H = _extent(vco_ring.footprint_um())
VCO_MIRROR_W, VCO_MIRROR_H = _extent(vco_mirror.footprint_um())
VCO_BUFFER_W, VCO_BUFFER_H = _extent(vco_buffer.footprint_um())
VCO_VTOI_CORE_W, VCO_VTOI_CORE_H = _extent(vco_vtoi_core.footprint_um())

VCO_SUB_MARGIN = 5.0  # clearance from the VCO block edge, and between sub-blocks

VCO_CORE = Block(
    "vco",
    x=LOOP_FILTER.x + LOOP_FILTER.w + DOMAIN_SPACING,
    y=0.0,
    w=max(140.0, max(VCO_RING_W, VCO_MIRROR_W, VCO_BUFFER_W, VCO_VTOI_CORE_W) + 2 * VCO_SUB_MARGIN),
    # Four real sub-blocks stacked with margin no longer fit the ROM's
    # 100 um height -- see this module's own docstring for the disclosed
    # deviation (VCO_VTOI_CORE_H's own 50.7 um, driven by MSU1's L=20 um
    # channel, is the largest single addition).
    h=max(
        100.0,
        VCO_MIRROR_H + VCO_RING_H + VCO_BUFFER_H + VCO_VTOI_CORE_H + 5 * VCO_SUB_MARGIN,
    ),
)
# Stacked bottom to top in signal order: the V-to-I core feeds the
# band-select mirror's VBP0 input, the mirror feeds the ring's VBP/VBN, and
# the ring's own Y5 feeds the output buffer. Each is a separately
# guard-ringed, standalone-DRC-clean block today; merging them under one
# ring is a later increment of #293.
VCO_VTOI_CORE = Block(
    "vco.vtoi_core",
    x=VCO_CORE.x + VCO_SUB_MARGIN,
    y=VCO_CORE.y + VCO_SUB_MARGIN,
    w=VCO_VTOI_CORE_W,
    h=VCO_VTOI_CORE_H,
)
VCO_MIRROR = Block(
    "vco.bandsel_mirror",
    x=VCO_CORE.x + VCO_SUB_MARGIN,
    y=VCO_VTOI_CORE.y + VCO_VTOI_CORE.h + VCO_SUB_MARGIN,
    w=VCO_MIRROR_W,
    h=VCO_MIRROR_H,
)
VCO_RING = Block(
    "vco.ring",
    x=VCO_CORE.x + VCO_SUB_MARGIN,
    y=VCO_MIRROR.y + VCO_MIRROR.h + VCO_SUB_MARGIN,
    w=VCO_RING_W,
    h=VCO_RING_H,
)
VCO_BUFFER = Block(
    "vco.out_buffer",
    x=VCO_CORE.x + VCO_SUB_MARGIN,
    y=VCO_RING.y + VCO_RING.h + VCO_SUB_MARGIN,
    w=VCO_BUFFER_W,
    h=VCO_BUFFER_H,
)
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

# The real VCO sub-block footprints are drawn in addition to (not instead of)
# VCO_DECAP_0/1 above: VCO_DECAP_0/1 are this skeleton's own long-standing
# decap markers (#17), left untouched so the tests that already pin their
# exact geometry keep passing; VCO_RING/VCO_MIRROR/VCO_BUFFER (#293) are the
# newer, more detailed real footprints, which happen to spatially overlap
# them within this reference-only boundary-layer drawing -- harmless, since
# layer (0, 0) carries no DRC rule and this file has never claimed sub-blocks
# are mutually disjoint (only that C1_ARRAY/C2_CAP sit inside LOOP_FILTER and
# VCO_DECAP_0/1 don't overlap *each other* -- see
# layout/tests/test_floorplan_skeleton.py). The real, non-overlapping,
# DRC-checked geometry lives in each generator's own GDS, not here. (The
# ring block's GDS carries the 22 pF decap itself, so VCO_DECAP_0/1 are a
# duplicate marker of it at this reference level, not a second pair of caps.)
SUB_BLOCKS = (
    C1_ARRAY,
    C2_CAP,
    VCO_DECAP_0,
    VCO_DECAP_1,
    VCO_MIRROR,
    VCO_RING,
    VCO_BUFFER,
    VCO_VTOI_CORE,
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
