#!/usr/bin/env python3
"""Unit tests for the PLL floorplan skeleton's block geometry (issue #17).

No PDK and no KLayout required -- ``floorplan/skeleton.py`` only imports
``klayout.db`` lazily inside ``build()`` (same convention as
``harness/cell.py``), so the placement data itself (the ``Block`` constants
and ``total_extent_um2``) is plain-Python and importable without a PV
environment. These tests check the floorplan-level invariants
``PLL-FLOORPLAN.md`` claims -- no two domains overlap, and the sub-block
geometry (loop-filter caps, VCO decap) sits inside the block that is
supposed to contain it -- not KLayout/DRC behavior.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))

from floorplan import skeleton  # noqa: E402


def _overlaps(a: skeleton.Block, b: skeleton.Block) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def _contains(outer: skeleton.Block, inner: skeleton.Block) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and inner.x + inner.w <= outer.x + outer.w
        and inner.y + inner.h <= outer.y + outer.h
    )


class BlockPlacementTests(unittest.TestCase):
    def test_top_level_blocks_do_not_overlap(self):
        blocks = skeleton.BLOCKS
        for i, a in enumerate(blocks):
            for b in blocks[i + 1 :]:
                self.assertFalse(
                    _overlaps(a, b), f"{a.name} overlaps {b.name}: {a} vs {b}"
                )

    def test_all_blocks_have_positive_area(self):
        for block in skeleton.BLOCKS + skeleton.SUB_BLOCKS:
            self.assertGreater(block.w, 0, block.name)
            self.assertGreater(block.h, 0, block.name)

    def test_loop_filter_c1_array_matches_dr006_footprint(self):
        # DR-006: C1 = 4x cap_nmos_03v3_b, 87x87 um each, arrayed 2x2 here.
        self.assertAlmostEqual(skeleton.C1_ARRAY.w, 2 * 87.0)
        self.assertAlmostEqual(skeleton.C1_ARRAY.h, 2 * 87.0)
        self.assertAlmostEqual(skeleton.C1_ARRAY.w * skeleton.C1_ARRAY.h, 4 * 87.0 * 87.0)

    def test_loop_filter_c2_matches_dr006_footprint(self):
        # DR-006: C2 = 1x cap_mim_2f0_m2m3_noshield, 31.4x31.4 um.
        self.assertAlmostEqual(skeleton.C2_CAP.w, 31.4)
        self.assertAlmostEqual(skeleton.C2_CAP.h, 31.4)

    def test_vco_decap_matches_committed_schematic_devices(self):
        # vco.sch: 2x cap_nmos_03v3, 50x50 um each.
        for decap in (skeleton.VCO_DECAP_0, skeleton.VCO_DECAP_1):
            self.assertAlmostEqual(decap.w, 50.0)
            self.assertAlmostEqual(decap.h, 50.0)

    def test_loop_filter_sub_blocks_sit_inside_the_loop_filter_block(self):
        for sub in (skeleton.C1_ARRAY, skeleton.C2_CAP):
            self.assertTrue(
                _contains(skeleton.LOOP_FILTER, sub),
                f"{sub.name} escapes the loop_filter block: {sub} vs {skeleton.LOOP_FILTER}",
            )

    def test_vco_decap_sub_blocks_sit_inside_the_vco_block(self):
        for sub in (skeleton.VCO_DECAP_0, skeleton.VCO_DECAP_1):
            self.assertTrue(
                _contains(skeleton.VCO_CORE, sub),
                f"{sub.name} escapes the vco block: {sub} vs {skeleton.VCO_CORE}",
            )

    def test_vco_decap_sub_blocks_do_not_overlap_each_other(self):
        self.assertFalse(_overlaps(skeleton.VCO_DECAP_0, skeleton.VCO_DECAP_1))

    def test_total_extent_is_under_the_draft_area_budget(self):
        # PLL-FLOORPLAN.md section 5: draft target < 0.15 mm^2 = 150_000 um^2.
        self.assertLess(skeleton.total_extent_um2(), 150_000.0)

    def test_vco_guard_ring_margin_matches_the_drc_tap_pitch_bound(self):
        # layout/README.md / PLL-FLOORPLAN.md section 1: DF.13_MV/DF.14_MV
        # cap NCOMP-in-nwell / PCOMP-outside-nwell to a well/substrate tap at
        # 15 um -- the guard ring margin must not exceed the rule it is
        # sized against.
        self.assertLessEqual(skeleton.VCO_GUARD_MARGIN, 15.0)


if __name__ == "__main__":
    unittest.main()
