#!/usr/bin/env python3
"""Unit tests for the VCO's real transistor-level layout (issue #293).

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
from vco import bias_resistors  # noqa: E402
from vco import buffer as buf  # noqa: E402
from vco import devices as dev  # noqa: E402
from vco import mirror  # noqa: E402
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
        # skeleton.py stacks the three real sub-blocks inside VCO_CORE with a
        # margin; the containment check that actually matters is that
        # VCO_CORE was widened to fit them rather than left stale at 140 um.
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


class OutputBufferTests(unittest.TestCase):
    """devices.BUFFER_STAGES / buffer.py -- vco.sch's XMBP1..XMBN3 taper."""

    def test_stage_sizes_match_the_frozen_netlist(self):
        sizes = [(s.pfet.w_um, s.nfet.w_um) for s in dev.BUFFER_STAGES]
        self.assertEqual(sizes, [(1.25, 0.5), (3.75, 1.5), (11.25, 4.5)])
        for s in dev.BUFFER_STAGES:
            self.assertAlmostEqual(s.pfet.l_um, 0.28)
            self.assertAlmostEqual(s.nfet.l_um, 0.28)

    def test_stage_chain_nets_match_vco_sch(self):
        # Y5 -> NB1 -> NB2 -> CLK, each stage's output feeding the next input.
        self.assertEqual(dev.BUFFER_STAGES[0].in_net, dev.BUFFER_IN_NET)
        for a, b in zip(dev.BUFFER_STAGES, dev.BUFFER_STAGES[1:]):
            self.assertEqual(a.out_net, b.in_net)
        self.assertEqual(dev.BUFFER_STAGES[-1].out_net, dev.BUFFER_OUT_NET)

    def test_taper_increases_monotonically(self):
        widths = [s.pfet.w_um for s in dev.BUFFER_STAGES]
        self.assertEqual(widths, sorted(widths))
        self.assertGreater(widths[-1], widths[0])

    def test_largest_stage_is_the_one_nearest_the_clk_pin(self):
        # PLL-FLOORPLAN.md section 1: the largest, fastest-switching stage
        # sits closest to the CLK pin and farthest from the ring's starved
        # internal nodes. The CLK pin is on the block's right edge, the Y5
        # input on its left, so this is checked against the drawn x's rather
        # than trusted from BUFFER_STAGES' own tuple order.
        centers = buf.stage_center_x_um()
        x_clk = buf.footprint_um()[2]
        by_distance = sorted(zip(centers, dev.BUFFER_STAGES), key=lambda t: abs(x_clk - t[0]))
        self.assertEqual(by_distance[0][1].pfet.w_um, max(s.pfet.w_um for s in dev.BUFFER_STAGES))
        self.assertEqual(by_distance[-1][1].pfet.w_um, min(s.pfet.w_um for s in dev.BUFFER_STAGES))

    def test_column_pitch_clears_each_stage_own_widest_device(self):
        xs = buf.column_x0_um()
        for x0, x1, st in zip(xs, xs[1:], dev.BUFFER_STAGES):
            self.assertGreaterEqual(x1 - x0, st.max_w_um + buf.COL_GAP_UM)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = buf.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_tap_pitch_bound_with_real_margin(self):
        for d in (buf.max_pmos_tap_distance_um(), buf.max_nmos_tap_distance_um()):
            self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM / 2.0)


class BandSelectMirrorDeviceTests(unittest.TestCase):
    """devices.MIRROR_* matches design/netlist/vco.spice's .subckt vco_bias."""

    def test_cascade_sizes_match_the_floorplan_record(self):
        # PLL-FLOORPLAN.md section 1: "A: pfet 26.5 um / 17.225 um; B: nfet
        # 5 um / 8.6125 um; C: pfet 12.3 um / 78.87 um".
        expected = {
            "A": ("pfet", 26.5, 17.225),
            "B": ("nfet", 5.0, 8.6125),
            "C": ("pfet", 12.3, 78.87),
        }
        for c in dev.MIRROR_CASCADES:
            kind, w_on, w_sw = expected[c.name]
            self.assertEqual(c.kind, kind)
            self.assertAlmostEqual(c.always_on.w_um, w_on)
            self.assertAlmostEqual(c.switched.w_um, w_sw)

    def test_cascade_c_keeps_dr003s_6_4_to_1_largest_ratio(self):
        c = {x.name: x for x in dev.MIRROR_CASCADES}["C"]
        self.assertAlmostEqual(c.switched.w_um / c.always_on.w_um, 6.4, places=1)
        for cascade in dev.MIRROR_CASCADES:
            ratio = cascade.switched.w_um / cascade.always_on.w_um
            self.assertLess(ratio, 6.5, f"cascade {cascade.name} ratio exceeds DR-003's 6.4:1")

    def test_netlist_finger_counts(self):
        by_name = {}
        for c in dev.MIRROR_CASCADES:
            by_name[c.always_on.name] = c.always_on
            by_name[c.switched.name] = c.switched
        self.assertEqual((by_name["MA0"].nf, by_name["MA1"].nf), (2, 2))
        self.assertEqual((by_name["MB0"].nf, by_name["MB1"].nf), (1, 1))
        self.assertEqual((by_name["MC0"].nf, by_name["MC1"].nf), (1, 8))

    def test_only_cascade_b_folds_its_fingers(self):
        # Folding is a real layout-vs-netlist deviation; it must stay
        # confined to the one cascade that structurally requires it.
        folded = [
            leg.name
            for c in dev.MIRROR_CASCADES
            for leg in (c.always_on, c.switched)
            if leg.fingers != leg.nf
        ]
        self.assertEqual(sorted(folded), ["MB0", "MB1"])

    def test_drawn_width_tracks_the_schematic_within_one_grid_step(self):
        # Three legs' per-finger widths are not exact multiples of the 5 nm
        # manufacturing grid, so the drawn W is the nearest grid point.
        for c in dev.MIRROR_CASCADES:
            for leg in (c.always_on, c.switched):
                self.assertLess(
                    leg.w_deviation_frac,
                    5e-4,
                    f"{leg.name}: drawn {leg.drawn_w_um} um vs schematic {leg.w_um} um",
                )
                self.assertAlmostEqual(
                    leg.finger_w_um / dev.LAYOUT_GRID_UM,
                    round(leg.finger_w_um / dev.LAYOUT_GRID_UM),
                    places=6,
                    msg=f"{leg.name}'s finger width is off the manufacturing grid",
                )

    def test_switch_mux_and_load_devices_match_the_netlist(self):
        muxes = {m.cascade: m for m in dev.MIRROR_MUXES}
        self.assertEqual(muxes["A"].on.name, "MSWA0")
        self.assertEqual(muxes["A"].on.gate_net, "B0B")
        self.assertEqual(muxes["A"].off.gate_net, "B0")
        self.assertEqual(muxes["B"].on.kind, "nfet")
        self.assertEqual(muxes["C"].out_net, "GC")
        for mux in dev.MIRROR_MUXES:
            for f in (mux.on, mux.off):
                self.assertAlmostEqual(f.w_um, 2.0)
                self.assertAlmostEqual(f.l_um, 0.5)
        loads = {f.name: f for f in dev.MIRROR_LOADS}
        self.assertEqual(set(loads), {"MDA", "MDB", "MDN", "MMN", "MDP"})
        for name in ("MDA", "MDB", "MDN", "MDP"):
            f = loads[name]
            self.assertEqual(f.gate_net, f.top_net if f.kind == "nfet" else f.bottom_net)


class CommonCentroidTests(unittest.TestCase):
    """The acceptance criterion this whole block exists for: each cascade is
    an interdigitated array whose two legs share a centroid."""

    def test_every_cascade_passes_the_generator_own_check(self):
        for c in dev.MIRROR_CASCADES:
            mirror.check_common_centroid(c)  # raises on failure

    def test_leg_centroids_coincide_with_the_array_centre(self):
        for c in dev.MIRROR_CASCADES:
            centre = mirror.array_width_um(c) / 2.0
            for leg in ("A", "S"):
                self.assertAlmostEqual(mirror.leg_centroid_um(c, leg), centre, places=9)

    def test_patterns_are_palindromes_with_the_netlist_finger_counts(self):
        for c in dev.MIRROR_CASCADES:
            self.assertEqual(tuple(c.pattern), tuple(reversed(c.pattern)))
            self.assertEqual(c.pattern.count("A"), c.always_on.fingers)
            self.assertEqual(c.pattern.count("S"), c.switched.fingers)

    def test_a_row_placed_pattern_is_rejected(self):
        # Negative control: the check has to actually reject the layout
        # PLL-FLOORPLAN.md section 1 rules out ("not three separate blobs"),
        # not merely pass on the patterns we happen to ship.
        c = {x.name: x for x in dev.MIRROR_CASCADES}["A"]
        row_placed = dev.CascadePair(
            name="A_rowplaced",
            always_on=c.always_on,
            switched=c.switched,
            pattern=("A", "A", "S", "S"),
        )
        with self.assertRaises(ValueError):
            mirror.check_common_centroid(row_placed)

    def test_an_asymmetric_pattern_is_rejected(self):
        c = {x.name: x for x in dev.MIRROR_CASCADES}["C"]
        skewed = dev.CascadePair(
            name="C_skewed",
            always_on=c.always_on,
            switched=c.switched,
            pattern=("A", "S", "S", "S", "S", "S", "S", "S", "S"),
        )
        with self.assertRaises(ValueError):
            mirror.check_common_centroid(skewed)

    def test_finger_positions_are_symmetric_about_the_array_centre(self):
        # Stronger than the centroid equality above: with a uniform finger
        # gap, a palindromic pattern must make the whole position sequence
        # mirror-symmetric, which is what actually cancels a linear gradient.
        for c in dev.MIRROR_CASCADES:
            xs = mirror.finger_x0_um(c)
            widths = c.finger_widths()
            total = mirror.array_width_um(c)
            centers = [x + w / 2.0 for x, w in zip(xs, widths)]
            for a, b in zip(centers, reversed(centers)):
                self.assertAlmostEqual(a + b, total, places=9)


class MirrorPlanTests(unittest.TestCase):
    """mirror.plan() -- the pure-Python placement the generator draws from."""

    def setUp(self):
        self.plan = mirror.plan()

    def test_every_inter_device_net_has_a_track(self):
        for net, rows in self.plan.net_rows.items():
            self.assertIn(net, mirror.NET_ORDER)
            for row in rows:
                self.assertIsInstance(self.plan.track_y(net, row), float)

    def test_nmos_and_pmos_track_groups_are_disjoint(self):
        # The invariant that makes a Metal1 escape column from one row
        # incapable of touching one from the other row, whatever their x --
        # see mirror.py's NET_ORDER comment.
        lo = [self.plan.track_lo[n] for n, r in self.plan.net_rows.items() if "nfet" in r]
        hi = [self.plan.track_hi[n] for n, r in self.plan.net_rows.items() if "pfet" in r]
        self.assertLess(max(lo), min(hi))
        self.assertGreaterEqual(min(hi) - max(lo), mirror.TRACK_PITCH_UM)

    def test_two_row_nets_get_a_link_column_and_one_row_nets_do_not(self):
        for net, rows in self.plan.net_rows.items():
            if rows == {"nfet", "pfet"}:
                self.assertIn(net, self.plan.link_x, f"{net} spans both rows but has no link")
            else:
                self.assertNotIn(net, self.plan.link_x)

    def test_link_columns_sit_clear_of_both_transistor_rows(self):
        rows_right = max(
            it.x0 + it.width for it in (self.plan.pmos + self.plan.nmos)
        )
        for net, x in self.plan.link_x.items():
            self.assertGreater(x, rows_right, f"{net}'s link column lands inside a device row")

    def test_metal2_tracks_meet_the_m2_spacing_rule(self):
        ys = sorted(set(list(self.plan.track_lo.values()) + list(self.plan.track_hi.values())))
        for a, b in zip(ys, ys[1:]):
            self.assertGreaterEqual(
                b - a - prim.METAL2_WIRE_WIDTH_UM, dev.DRC_METAL2_MIN_SPACE_UM
            )

    def test_reserve_rejects_two_nets_closer_than_m1_spacing(self):
        # Negative control for the guard that caught the real short in this
        # generator's first build (MDN's drain pad on MSWA0's gate tab).
        p = mirror.Plan()
        p.reserve("VBN", 10.0, 0.0, 10.44, 20.0)
        p.reserve("VBN", 10.0, 0.0, 10.44, 30.0)  # same net: allowed
        with self.assertRaises(ValueError):
            p.reserve("B0B", 10.5, 5.0, 10.94, 25.0)

    def test_two_gate_buses_fit_in_every_cascade_own_corridor(self):
        for c in dev.MIRROR_CASCADES:
            lo, hi = mirror.gate_bus_y_um(c.always_on.l_um, 0.0)
            self.assertLess(lo, hi)
            self.assertGreaterEqual(hi - lo - prim.METAL1_WIRE_WIDTH_UM, dev.DRC_METAL1_MIN_SPACE_UM)

    def test_tap_pitch_bound_with_real_margin(self):
        for d in (mirror.max_pmos_tap_distance_um(), mirror.max_nmos_tap_distance_um()):
            self.assertGreater(d, 0.0)
            self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM / 2.0)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = mirror.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)


class GridSnapTests(unittest.TestCase):
    """geom.drc's OFFGRID section runs ongrid(0.005) on every drawn layer."""

    def test_snap_um_lands_on_the_manufacturing_grid(self):
        for v in (0.0, 4.30625, 9.85875, 8.6125, -1.234):
            snapped = dev.snap_um(v)
            self.assertAlmostEqual(snapped / dev.LAYOUT_GRID_UM, round(snapped / dev.LAYOUT_GRID_UM))
            self.assertLessEqual(abs(snapped - v), dev.LAYOUT_GRID_UM / 2.0 + 1e-9)

    def test_via_and_contact_sizes_are_grid_multiples(self):
        # CO.1 and V1.1 are min *and* max rules, so these two sizes have to
        # be exactly representable or every contact/via is a violation.
        for size in (dev.DRC_CONTACT_SIZE_UM, dev.DRC_VIA1_SIZE_UM):
            self.assertAlmostEqual(size / dev.LAYOUT_GRID_UM, round(size / dev.LAYOUT_GRID_UM))

    def test_via1_landing_pad_avoids_the_narrow_metal_special_rules(self):
        pad = dev.DRC_VIA1_SIZE_UM + 2 * prim.VIA1_METAL_ENCLOSE_UM
        self.assertGreaterEqual(pad, dev.DRC_VIA1_EOL_METAL_WIDTH_UM)
        self.assertGreaterEqual(prim.METAL2_WIRE_WIDTH_UM, dev.DRC_VIA1_EOL_METAL_WIDTH_UM)


class VcoSubBlockFloorplanTests(unittest.TestCase):
    """skeleton.py's VCO_RING/VCO_MIRROR/VCO_BUFFER vs. the real generators."""

    def test_sub_block_footprints_match_their_generators(self):
        for block, footprint in (
            (skeleton.VCO_RING, ring.footprint_um()),
            (skeleton.VCO_MIRROR, mirror.footprint_um()),
            (skeleton.VCO_BUFFER, buf.footprint_um()),
        ):
            x0, y0, x1, y1 = footprint
            self.assertAlmostEqual(block.w, x1 - x0)
            self.assertAlmostEqual(block.h, y1 - y0)

    def test_all_three_sub_blocks_sit_inside_vco_core(self):
        for block in (skeleton.VCO_RING, skeleton.VCO_MIRROR, skeleton.VCO_BUFFER):
            self.assertTrue(
                _contains(skeleton.VCO_CORE, block), f"{block.name} escapes VCO_CORE"
            )

    def test_the_three_real_sub_blocks_do_not_overlap_each_other(self):
        blocks = (skeleton.VCO_MIRROR, skeleton.VCO_RING, skeleton.VCO_BUFFER)
        for i, a in enumerate(blocks):
            for b in blocks[i + 1 :]:
                overlap = (
                    a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
                )
                self.assertFalse(overlap, f"{a.name} overlaps {b.name}")

    def test_vco_core_still_fits_the_rom_height(self):
        # The ROM box's 100 um height survives all three real sub-blocks
        # stacked; its 140 um width did not (see skeleton.py's docstring).
        self.assertEqual(skeleton.VCO_CORE.h, 100.0)
        self.assertGreater(skeleton.VCO_CORE.w, 140.0)

    def test_area_budget_headroom_is_reported_not_silently_exceeded(self):
        # PLL-FLOORPLAN.md section 5's draft target is 0.15 mm^2. The real
        # single-row sub-block widths eat most of it; this test pins the
        # number so a later increment cannot cross the line unnoticed.
        used = skeleton.total_extent_um2()
        self.assertLess(used, 150_000.0)
        self.assertGreater(used / 150_000.0, 0.9, "budget headroom changed -- re-read skeleton.py")


class BiasResistorDeviceTests(unittest.TestCase):
    """devices.BIAS_RESISTORS matches design/netlist/vco.spice's XRCG/XROFF/XRDEG."""

    def test_three_resistors_match_the_frozen_netlist(self):
        by_name = {r.name: r for r in dev.BIAS_RESISTORS}
        self.assertEqual(set(by_name), {"RCG", "ROFF", "RDEG"})
        self.assertEqual((by_name["RCG"].w_um, by_name["RCG"].l_um), (1.0, 5.6))
        self.assertEqual((by_name["ROFF"].w_um, by_name["ROFF"].l_um), (1.0, 33.0))
        self.assertEqual((by_name["RDEG"].w_um, by_name["RDEG"].l_um), (1.0, 33.0))

    def test_every_resistor_meets_pres1s_minimum_width(self):
        for r in dev.BIAS_RESISTORS:
            self.assertGreaterEqual(r.w_um, prim.POLY_RES_MIN_WIDTH_UM)

    def test_signal_nodes_match_the_schematic(self):
        by_name = {r.name: r for r in dev.BIAS_RESISTORS}
        self.assertEqual(by_name["RCG"].top_net, "NC")
        self.assertEqual(by_name["ROFF"].top_net, "NOFF")
        self.assertEqual(by_name["RDEG"].top_net, "NVI")
        for r in dev.BIAS_RESISTORS:
            self.assertEqual(r.bottom_net, "GND_VCO")


class BiasResistorsBlockTests(unittest.TestCase):
    """bias_resistors.py -- the standalone poly-resistor block."""

    def test_columns_are_ordered_and_non_overlapping(self):
        xs = bias_resistors.column_x0_um()
        self.assertEqual(len(xs), len(dev.BIAS_RESISTORS))
        for x0, x1, r in zip(xs, xs[1:], dev.BIAS_RESISTORS):
            self.assertGreaterEqual(x1 - x0, r.w_um + bias_resistors.RESISTOR_GAP_UM)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = bias_resistors.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_contains_the_longest_resistor(self):
        _, outer_y0, _, outer_y1 = bias_resistors.footprint_um()
        poly_y0, poly_y1 = bias_resistors.poly_y_extent_um()
        self.assertLess(outer_y0, poly_y0)
        self.assertGreater(outer_y1, poly_y1)
        self.assertAlmostEqual(poly_y1, max(r.l_um for r in dev.BIAS_RESISTORS) + prim.POLY_RES_EXT_UM)

    def test_tap_pitch_bound_with_real_margin(self):
        # This block's guard-ring bands are left/right (full block height),
        # not top/bottom -- see bias_resistors.py's own module docstring for
        # why that is the correct shape for a narrow, tall block.
        d = bias_resistors.max_tap_distance_um()
        self.assertGreater(d, 0.0)
        self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM / 2.0)


class PolyResistorPrimitiveTests(unittest.TestCase):
    """primitives.poly_resistor()'s pure-Python constants (PRES.* citations)."""

    def test_sab_extension_matches_pres6(self):
        self.assertAlmostEqual(prim.POLY_RES_SAB_EXT_UM, 0.28)

    def test_contact_to_sab_clearance_matches_pres7(self):
        self.assertAlmostEqual(prim.POLY_RES_CONTACT_TO_SAB_UM, 0.22)

    def test_implant_enclosure_meets_pres5(self):
        self.assertGreaterEqual(prim.POLY_RES_IMPLANT_ENC_UM, 0.3)

    def test_poly_extension_leaves_room_for_a_contact_clear_of_sab(self):
        # The contact-land region (POLY_RES_EXT_UM tall) has to fit both
        # CONTACT_ROW_MARGIN_UM (poly enclosure) and
        # POLY_RES_CONTACT_TO_SAB_UM (PRES.7 clearance) with a real contact
        # in between -- this is the arithmetic poly_resistor() relies on.
        usable = (
            prim.POLY_RES_EXT_UM
            - prim.CONTACT_ROW_MARGIN_UM
            - prim.POLY_RES_CONTACT_TO_SAB_UM
        )
        self.assertGreaterEqual(usable, prim.CONTACT_SIZE_UM)


if __name__ == "__main__":
    unittest.main()
