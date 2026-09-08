#!/usr/bin/env python3
"""Unit tests for the VCO ring's real transistor-level layout (issue #293).

No PDK and no KLayout required -- ``layout/pll_top/vco/primitives.py`` and
``ring.py`` only import ``klayout.db`` lazily inside functions that actually
draw geometry (same convention as ``layout/floorplan/skeleton.py`` /
``layout/harness/cell.py``), so every number this file checks
(``devices.py``'s schematic-sourced device table, ``ring.py``'s pure-Python
footprint/tap-distance helpers) is importable and checkable without a PV
environment.

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC-clean claim (which *does* need KLayout + the PDK), see
``layout/evidence/vco-layout/PROOF.md`` -- this file checks the geometry
this generator *claims* to build, not a substitute for running the deck.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

from floorplan import skeleton  # noqa: E402
from vco import devices as dev  # noqa: E402
from vco import primitives as prim  # noqa: E402
from vco import ring  # noqa: E402


def _contains(outer, inner) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and inner.x + inner.w <= outer.x + outer.w
        and inner.y + inner.h <= outer.y + outer.h
    )


class DeviceTableTests(unittest.TestCase):
    """devices.STAGE_FETS matches design/netlist/vco.spice's XMPH/XMP/XMN/XMNT."""

    def test_stage_count_is_five_per_dr003(self):
        self.assertEqual(dev.STAGE_COUNT, 5)

    def test_four_fets_per_stage(self):
        self.assertEqual(len(dev.STAGE_FETS), 4)

    def test_fet_sizes_match_the_frozen_netlist(self):
        sizes = {f.name: (f.w_um, f.l_um) for f in dev.STAGE_FETS}
        self.assertEqual(sizes["MPH"], (10.0, 0.5))
        self.assertEqual(sizes["MP"], (5.0, 0.28))
        self.assertEqual(sizes["MN"], (2.0, 0.28))
        self.assertEqual(sizes["MNT"], (4.0, 0.5))

    def test_stack_order_is_vdd_to_gnd(self):
        # MPH.top=VDD, MPH.bottom=NH=MP.top, MP.bottom=Y=MN.top,
        # MN.bottom=NT=MNT.top, MNT.bottom=VSS -- see devices.py docstring.
        fets = {f.name: f for f in dev.STAGE_FETS}
        self.assertEqual(fets["MPH"].top_net, "VDD")
        self.assertEqual(fets["MPH"].bottom_net, fets["MP"].top_net)
        self.assertEqual(fets["MP"].bottom_net, fets["MN"].top_net)
        self.assertEqual(fets["MN"].bottom_net, fets["MNT"].top_net)
        self.assertEqual(fets["MNT"].bottom_net, "VSS")

    def test_decap_matches_vco_sch(self):
        self.assertEqual(dev.DECAP_COUNT, 2)
        self.assertAlmostEqual(dev.DECAP_SIZE_UM, 50.0)


class FootprintConsistencyTests(unittest.TestCase):
    """ring.footprint_um()'s pure-Python prediction vs. this module's own
    generator constants -- catches the formula drifting out of sync with
    primitives.py's actual margins without needing a KLayout run."""

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = ring.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_stage_pitch_clears_the_widest_device(self):
        widest_w = max(f.w_um for f in dev.STAGE_FETS)
        self.assertGreater(ring.STAGE_PITCH_UM, widest_w)

    def test_pmos_x_range_spans_all_five_stages(self):
        x0, x1 = ring.pmos_x_range()
        self.assertEqual(x0, 0.0)
        self.assertAlmostEqual(x1, (dev.STAGE_COUNT - 1) * ring.STAGE_PITCH_UM + 10.0)

    def test_pmos_band_sits_above_the_nmos_band_with_dr16_clearance(self):
        # DF.16_LV: nwell edge to NMOS comp outside it >= 0.43 um -- see
        # primitives.py's NWELL_TO_NMOS_GAP_UM docstring for why the actual
        # gap is much larger (room for the inner tap band too).
        y0, y1 = ring.pmos_y_range()
        self.assertGreater(y0, 0.0)
        self.assertGreater(y1, y0)
        self.assertGreaterEqual(prim.NWELL_TO_NMOS_GAP_UM, dev.DRC_NWELL_TO_NCOMP_OUT_UM)


class TapPitchTests(unittest.TestCase):
    """Test plan edge case: guard-ring tap pitch <= 15 um *everywhere*
    inside the block, not just at the block perimeter (DF.13_MV/DF.14_MV,
    PLL-FLOORPLAN.md section 1)."""

    def test_pmos_devices_are_within_the_drc_tap_pitch_bound(self):
        self.assertLessEqual(ring.max_pmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM)

    def test_nmos_devices_are_within_the_drc_tap_pitch_bound(self):
        self.assertLessEqual(ring.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM)

    def test_tap_pitch_has_real_margin_not_just_barely_under(self):
        # A generator that DRC-passes today but sits within a rounding error
        # of the 15 um bound is one schematic tweak away from failing --
        # assert real headroom, not just "<=".
        self.assertLess(ring.max_pmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)
        self.assertLess(ring.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)


class FloorplanIntegrationTests(unittest.TestCase):
    """layout/floorplan/skeleton.py's VCO_CORE/VCO_RING (issue #293's
    "replace/augment the VCO_CORE placeholder" acceptance criterion)."""

    def test_vco_ring_matches_the_real_generator_footprint(self):
        x0, y0, x1, y1 = ring.footprint_um()
        self.assertAlmostEqual(skeleton.VCO_RING.w, x1 - x0)
        self.assertAlmostEqual(skeleton.VCO_RING.h, y1 - y0)

    def test_vco_ring_sits_inside_the_widened_vco_core(self):
        # VCO_RING.x/y == VCO_CORE.x/y by construction (skeleton.py places
        # the ring at the block's own origin); the containment check that
        # actually matters is width/height, i.e. VCO_CORE was widened to
        # fit the real ring rather than left stale at 140 um.
        self.assertTrue(_contains(skeleton.VCO_CORE, skeleton.VCO_RING))

    def test_vco_core_width_deviates_from_the_stale_140um_rom_estimate(self):
        # Explicit, disclosed deviation (issue #293 AC) -- the real ring is
        # wider than the original square ROM guess (one row of 5 stages,
        # full-custom -- see ring.py's module docstring).
        self.assertGreater(skeleton.VCO_CORE.w, 140.0)

    def test_vco_decap_sub_blocks_are_unchanged_by_the_real_ring(self):
        # The pre-existing decap markers (#17) keep their own committed
        # geometry regardless of VCO_RING being added alongside them.
        for decap in (skeleton.VCO_DECAP_0, skeleton.VCO_DECAP_1):
            self.assertAlmostEqual(decap.w, 50.0)
            self.assertAlmostEqual(decap.h, 50.0)


if __name__ == "__main__":
    unittest.main()
