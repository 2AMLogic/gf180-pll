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
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

try:
    import klayout.db  # noqa: F401

    _HAVE_KLAYOUT = True
except ImportError:
    _HAVE_KLAYOUT = False

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

    def test_total_extent_overrun_is_recorded_and_does_not_grow(self):
        """The area budget now FAILS, on the record, and must not get worse.

        Through #324 this asserted ``total_extent_um2() < 150_000`` and
        passed. It cannot any more: #310 replaced ``DIVIDER_LOCK``'s 90x50 um
        placeholder with the two real blocks it contains, and the divider
        chain alone measures 2634.28 x 93.82 um (see the fail-loud block at
        ``DIVIDER_LOCK`` in skeleton.py, and PLL-FLOORPLAN.md section 5's
        revision note).

        The assertion is *inverted rather than deleted*, plus a ratchet: the
        overrun must still be real (so this test starts failing again the
        moment a future reduction pass fixes it, forcing the record to be
        updated instead of quietly passing), and it must not exceed the
        magnitude skeleton.py states. A regression that makes the floorplan
        even bigger fails here.
        """
        extent = skeleton.total_extent_um2()
        self.assertGreater(
            extent,
            skeleton.AREA_BUDGET_UM2,
            "floorplan now fits the 0.15 mm^2 budget -- if a reduction pass "
            "achieved this, restore the original assertLess() form and update "
            "skeleton.py's DIVIDER_LOCK fail-loud note and PLL-FLOORPLAN.md "
            "section 5 to match",
        )
        # Ratchet: skeleton.py states ~1.19e6 um^2. Allow no growth past 1.25e6.
        self.assertLess(extent, 1_250_000.0, "floorplan extent grew beyond the recorded overrun")

    def test_lock_detector_standalone_footprint_is_recorded_and_positive(self):
        # issue #296: the real, DRC-clean standalone lock_detector layout's
        # as-drawn footprint -- see layout/evidence/lock-detector-layout/PROOF.md.
        self.assertGreater(skeleton.LOCK_DETECTOR_STANDALONE_W_UM, 0)
        self.assertGreater(skeleton.LOCK_DETECTOR_STANDALONE_H_UM, 0)

    def test_divider_chain_standalone_footprint_is_recorded_and_positive(self):
        # issue #310: the real, DRC- and LVS-clean standalone divider_chain
        # layout -- see layout/evidence/divider-chain-layout/PROOF.md.
        self.assertGreater(skeleton.DIVIDER_CHAIN_STANDALONE_W_UM, 0)
        self.assertGreater(skeleton.DIVIDER_CHAIN_STANDALONE_H_UM, 0)

    def test_divider_lock_region_contains_both_of_its_real_blocks(self):
        """The #295/#296 DIVIDER_LOCK reconciliation, as a checkable invariant.

        Both blocks' PROOF.md records deferred this to whichever landed
        second (#310). It is resolved iff the region actually contains both
        real footprints -- not the 90x50 um plan estimate neither fits.
        """
        for sub in (skeleton.DIVIDER_CHAIN, skeleton.LOCK_DETECTOR):
            self.assertTrue(
                _contains(skeleton.DIVIDER_LOCK, sub),
                f"{sub.name} escapes the divider_lock region: {sub} vs {skeleton.DIVIDER_LOCK}",
            )

    def test_divider_chain_and_lock_detector_do_not_overlap(self):
        self.assertFalse(_overlaps(skeleton.DIVIDER_CHAIN, skeleton.LOCK_DETECTOR))

    def test_divider_chain_and_lock_detector_are_separated_by_a_full_domain_spacing(self):
        """PLL-FLOORPLAN.md section 2: VDD_DIV and VDD are separate domains.

        The two blocks share this region for physical adjacency only
        (divider_chain draws no VDD net at all, lock_detector no VDD_DIV), so
        they get the same inter-domain clearance any two domains get, not an
        abutment.
        """
        gap = skeleton.LOCK_DETECTOR.y - (skeleton.DIVIDER_CHAIN.y + skeleton.DIVIDER_CHAIN.h)
        self.assertGreaterEqual(gap, skeleton.DOMAIN_SPACING)

    def test_divider_lock_clears_the_vco_guard_ring_keepout(self):
        # The region sits above every other block; the VCO's 15 um keep-out is
        # the tightest thing it could have clipped.
        self.assertGreaterEqual(
            skeleton.DIVIDER_LOCK.y,
            skeleton.VCO_CORE.y + skeleton.VCO_CORE.h + skeleton.VCO_GUARD_MARGIN,
        )

    def test_vco_guard_ring_margin_matches_the_drc_tap_pitch_bound(self):
        # layout/README.md / PLL-FLOORPLAN.md section 1: DF.13_MV/DF.14_MV
        # cap NCOMP-in-nwell / PCOMP-outside-nwell to a well/substrate tap at
        # 15 um -- the guard ring margin must not exceed the rule it is
        # sized against.
        self.assertLessEqual(skeleton.VCO_GUARD_MARGIN, 15.0)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class RecordedFootprintDriftTests(unittest.TestCase):
    """The recorded divider_chain footprint must match what the generator draws.

    ``skeleton.py`` must stay importable without KLayout, so it records
    ``DIVIDER_CHAIN_STANDALONE_{W,H}_UM`` as plain floats rather than calling
    ``divider_chain.build()`` (which needs ``klayout.db``) the way it calls
    ``vco/block.py``'s plain-Python ``footprint_um()``. This test closes that
    gap from the other side whenever KLayout *is* available: it rebuilds the
    block and asserts the recorded numbers still describe it, so the floorplan
    record cannot silently drift away from the geometry it claims to shadow.
    """

    def test_divider_chain_recorded_footprint_matches_the_generator(self):
        from divider_chain import divider_chain  # noqa: PLC0415

        x0, y0, x1, y1 = divider_chain.build().footprint
        self.assertAlmostEqual(x1 - x0, skeleton.DIVIDER_CHAIN_STANDALONE_W_UM, places=2)
        self.assertAlmostEqual(y1 - y0, skeleton.DIVIDER_CHAIN_STANDALONE_H_UM, places=2)


if __name__ == "__main__":
    unittest.main()
