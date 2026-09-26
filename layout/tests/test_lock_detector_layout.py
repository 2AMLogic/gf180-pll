#!/usr/bin/env python3
"""Connectivity checks on the ``lock_detector`` block layout (issue #322).

No PDK and no KLayout required: ``lock_detector.checks.RecordingCanvas`` is a
duck-typed stand-in for ``lock_detector.primitives.Canvas`` that records
every Metal1/Metal2/Metal3 shape ``primitives.mosfet()``/``tap_strip()``/
``route_net()`` draw, tagged by net, instead of ever touching
``klayout.db`` -- see ``checks.py``'s module docstring (the same
"``klayout.db`` only touched by ``write_gds()``" convention
``pfd_cp/rowgen.py``'s own plain-Python ``Canvas`` uses for issue #300).

**Why this file exists**: a DRC deck cannot see a short (two different
nets' shapes overlapping on one layer merge into one legal polygon) or an
open (a net drawn as disconnected pieces is likewise geometrically legal).
Issue #322 found ``lock_detector``'s ``route_net()`` drawing 114 cross-net
Metal3 riser overlaps -- 75 of them ``VDD``/``VSS`` -- sitting undetected
through a DRC-clean, merged layout for exactly this reason. This file is
the check that would have caught it, run on every build.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import unittest

from _env import LAYOUT_DIR

from pll_top.lock_detector import build  # noqa: E402
from pll_top.lock_detector import checks  # noqa: E402
from pll_top.lock_detector import primitives as P  # noqa: E402


class RiserLanesTests(unittest.TestCase):
    """The riser lane assigner ``route_net()`` shares across every net."""

    def test_offset_clears_m3_2a_minimum_spacing(self):
        # Two risers ROW_LANE_OFFSET_UM apart must clear M3.2a's 0.28 um
        # minimum Metal3 spacing, edge to edge, with headroom.
        clearance = P.ROW_LANE_OFFSET_UM - P.METAL3_WIRE_WIDTH_UM
        self.assertGreater(clearance, 0.28)

    def test_offset_clears_every_shape_a_lane_actually_carries(self):
        # The Metal3 *wire* is not the widest thing on a lane -- the Via1/
        # Via2 metal landing is, and until issue #451 it was 0.44 um wide
        # against a 0.7 um pitch, i.e. 0.26 um apart where M2.2a wants 0.28.
        # The assertion above was true and the geometry still failed the
        # deck. Check every shape the lane carries, not the narrowest.
        landing_w = 2 * P.VIA_LANDING_HALF_UM
        self.assertGreaterEqual(landing_w, P.METAL3_WIRE_WIDTH_UM - 1e-9, "the landing is the widest shape on a lane")
        self.assertGreater(P.ROW_LANE_OFFSET_UM - landing_w, P.METAL2_MIN_SPACE_UM, "M2.2a between two landings")
        self.assertGreater(P.ROW_LANE_OFFSET_UM - landing_w, P.METAL3_MIN_SPACE_UM, "M3.2a between two landings")
        self.assertGreater(P.ROW_LANE_OFFSET_UM - landing_w, P.METAL1_MIN_SPACE_UM, "M1.2a between two landings")
        self.assertGreater(P.ROW_LANE_OFFSET_UM - P.VIA2_SIZE_UM, P.VIA_MIN_SPACE_UM, "V1.2a/V2.2a between two cuts")

    def test_a_via_landing_clears_the_metal_minimum_area(self):
        # M1.3/M2.3/M3.3: 0.1444 um^2. The Metal2 landing at a riser's jog
        # height is an isolated island -- Via1 below and Via2 above are
        # other layers -- so nothing merges with it to make up the area.
        # Shrinking the enclosure uniformly (issue #451's first attempt)
        # produced 161 M2.3 violations, one per riser.
        area = (2 * P.VIA_LANDING_HALF_UM) * (2 * P.VIA_LANDING_HALF_Y_UM)
        self.assertGreater(area, 0.1444)

    def test_a_via_enclosure_clears_the_adjacent_edge_escalation_threshold(self):
        # V1.3d/V1.4c/V2.3d/V2.4c escalate to a 0.06 um adjacent-edge
        # requirement once the metal overlaps the via by < 0.04 um anywhere.
        self.assertGreaterEqual(P.VIA_ENCLOSURE_UM, 0.04)
        self.assertGreaterEqual(P.VIA_ENCLOSURE_Y_UM, 0.04)

    def test_the_jog_wire_is_as_tall_as_the_landing_it_runs_into(self):
        # A narrower jog leaves the landing protruding above and below it,
        # and that protrusion faces whatever the jog was routed past --
        # 49 of issue #451's M1.2a items were that one notch, repeated.
        self.assertEqual(P.METAL1_JOG_HEIGHT_UM, 2 * P.VIA_LANDING_HALF_Y_UM)

    def test_first_riser_at_a_given_x_keeps_its_natural_position(self):
        lanes = P.RiserLanes([])
        x, jog_y = lanes.place("A", 1.0, y_pad=0.0, track_y=10.0)
        self.assertEqual(x, 1.0)
        self.assertEqual(jog_y, 0.0)  # no move -> no separate jog height

    def test_second_riser_at_the_same_x_moves_to_a_clear_lane(self):
        # The mechanism issue #322 identified: two different nets' pads can
        # land at the exact same natural x -- from *different* rows (their
        # own y_pad, e.g. a PMOS-row VDD pad and an NMOS-row VSS pad, is
        # never the same point in space; see mosfet()'s own docstring) --
        # with Metal3 columns that still overlap in Y (both run all the way
        # up to well above the block). The second one placed must not keep
        # that x -- it has to move far enough to clear M3.2a.
        lanes = P.RiserLanes([])
        first, _ = lanes.place("A", 1.0, y_pad=2.5, track_y=10.0)
        second, _jog_y = lanes.place("B", 1.0, y_pad=-2.5, track_y=10.0)
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(abs(second - first), P.ROW_LANE_OFFSET_UM - 1e-9)

    def test_a_third_riser_does_not_land_on_either_of_the_first_two(self):
        # Three different (hence never pad-coincident) rows sharing one x,
        # each with a Metal3 column reaching the same shared track region.
        lanes = P.RiserLanes([])
        rows = [("A", 2.5), ("B", -2.5), ("C", 6.0)]
        placed = [lanes.place(net, 1.0, y_pad=y_pad, track_y=10.0)[0] for net, y_pad in rows]
        for a, b in zip(placed, placed[1:]):
            self.assertGreaterEqual(abs(b - a), P.ROW_LANE_OFFSET_UM - 1e-9)
        self.assertEqual(len(set(placed)), 3)

    def test_a_riser_far_away_is_unaffected_by_earlier_placements(self):
        lanes = P.RiserLanes([])
        lanes.place("A", 1.0, y_pad=0.0, track_y=10.0)
        far = 1.0 + 10 * P.ROW_LANE_OFFSET_UM
        x, jog_y = lanes.place("B", far, y_pad=0.0, track_y=10.0)
        self.assertEqual(x, far)
        self.assertEqual(jog_y, 0.0)

    def test_non_overlapping_y_ranges_do_not_need_x_separation(self):
        # Two risers whose Y ranges never overlap at all can share (or come
        # arbitrarily close to) the same x -- only same-layer proximity
        # *and* Y overlap is ever a real short.
        lanes = P.RiserLanes([])
        lanes.place("A", 1.0, y_pad=0.0, track_y=5.0)
        x, _ = lanes.place("B", 1.0, y_pad=10.0, track_y=15.0)
        self.assertEqual(x, 1.0)

    def test_a_dense_cluster_still_finds_a_safe_lane(self):
        # A regression test for the exact mechanism issue #322 reported and
        # this fix's own first attempt still tripped over while building
        # ``nand2``: two supply nets (VDD/VSS) already occupy nearby lanes
        # with full-height columns, and a third net's pad sits close enough
        # that its nearest clear lanes' jog would otherwise have to cross
        # one of those columns. This must find a lane clear of both,
        # without raising (a Metal2 jog crossing a Metal3 column, on a
        # different layer with no via between them, is not a short -- only
        # crossing another net's own *Metal2* is; see ``_jog_is_safe()``).
        lanes = P.RiserLanes([])
        lanes.place("VDD", 2.81, y_pad=2.5, track_y=9.75)
        lanes.place("VSS", 2.81, y_pad=-2.5, track_y=13.5)
        moved, _ = lanes.place("B", 3.74, y_pad=0.8, track_y=12.0)
        self.assertGreaterEqual(abs(moved - 2.81), P.ROW_LANE_OFFSET_UM - 1e-9)

    def test_a_dense_row_of_same_height_nets_all_find_safe_lanes(self):
        # Regression for the exact sequence issue #322's PR found exhausted
        # RiserLanes building xor2's own PMOS-row (y_pad=2.5): several
        # different nets sharing one row's own characteristic height, close
        # enough together that multiple need to move, and some of those
        # moves need distinct jog heights so their own jog wires don't
        # collide with each other -- not just with the row's fixed Via1
        # landings. These are xor2's own real natural x / track_y values.
        y_pad = 2.5
        hw = hh = 0.23  # this package's own narrowest real pad half-extent
        groups = [
            ("VDD", 0.21, y_pad, 9.75, hw, hh),
            ("XN1a", 2.07, y_pad, 10.5, hw, hh),
            ("VDD", 2.81, y_pad, 9.75, hw, hh),
            ("XN1b", 4.67, y_pad, 10.5, hw, hh),
            ("VDD", 7.21, y_pad, 9.75, hw, hh),
            ("XN2", 9.07, y_pad, 14.25, hw, hh),
        ]
        lanes = P.RiserLanes(groups)
        placed = [
            lanes.place(net, x, y_pad=y_pad, track_y=track_y, half_w=hw, half_h=hh)[0]
            for net, x, _y, track_y, hw, hh in groups
        ]
        self.assertEqual(len(placed), len(groups))

    def test_avoids_a_not_yet_placed_nets_own_fixed_pad(self):
        # The mechanism issue #322's PR found building nand2: a net placed
        # early can pick a lane that looks clear against everything placed
        # so far and still route its own Metal1 stub/jog straight through
        # some *later* net's own pad, since that pad never moves once the
        # later net is finally routed at its own, already-known, natural
        # position ("Y" moved onto "VDD"'s own not-yet-routed pad by 0.04 um
        # in the real build). Seeding RiserLanes with every net's natural
        # position up front (as route_all_nets() does) must prevent this.
        #
        # "C" already occupies lane x=1.0 (from an earlier row, so its own
        # pad is at a different y and never coincides with "A"'s); "A"'s own
        # natural x is also 1.0, so it must move -- its nearest clear lane
        # one pitch away, 1.7, is exactly where "B" (not yet placed) has its
        # own fixed pad, at the same row height "A" is routing at. Landing
        # on lane 1.7 is still fine *if* "A"'s own jog height ends up clear
        # of "B"'s pad height -- what must never happen is landing there at
        # the *same* height as "B"'s own fixed pad.
        hw = hh = 0.23
        groups = [("A", 1.0, 0.0, 10.0, hw, hh), ("B", 1.7, 0.0, 10.0, hw, hh)]
        lanes = P.RiserLanes(groups)
        lanes._placed.append(("C", 1.0, 1.0, 5.0, 10.0, 5.0, hw, hh))
        x, jog_y = lanes.place("A", 1.0, y_pad=0.0, track_y=10.0, half_w=hw, half_h=hh)
        if abs(x - 1.7) < P.ROW_LANE_OFFSET_UM - 1e-9:
            self.assertGreater(abs(jog_y - 0.0), 1e-6)


class RiserLanesAreADrcModelTests(unittest.TestCase):
    """``RiserLanes`` must model *clearance*, not overlap (issue #451).

    Until #451 every hazard test in this class was a strict-overlap test
    with a 1e-6 um margin -- an electrical-short test, the same ground truth
    ``checks.shorted_pairs()`` uses -- and same-net pairs were skipped
    outright on the grounds that a net merging with itself is never a short.
    Both are true and neither is sufficient: the block it produced had zero
    shorts, zero opens, and 141 foundry-deck violations. Every case below is
    one of those 141, reduced to the placement decision behind it.
    """

    HW = HH = 0.23  # this package's own narrowest real pad half-extent

    def _lanes(self, groups=()):
        return P.RiserLanes(groups)

    def test_two_same_net_risers_may_share_a_lane_exactly(self):
        # The legal same-net case, and the reason sharing is allowed at all:
        # two collinear columns of one net union into a single legal Metal3
        # column, and via stacks a whole track pitch apart on it cannot
        # interact. This is how a 161-riser block fits in 168 lane slots.
        lanes = self._lanes()
        first, _ = lanes.place("VDD", 1.0, y_pad=2.5, track_y=10.0, half_w=self.HW, half_h=self.HH)
        second, _ = lanes.place("VDD", 1.0, y_pad=-2.5, track_y=10.0, half_w=self.HW, half_h=self.HH)
        self.assertEqual(first, second)

    def test_two_same_net_risers_never_land_a_fraction_of_a_pitch_apart(self):
        # The single largest source of issue #451's violations: every riser
        # of one net lands its top via stack on that net's own single
        # track_y, so two same-net lanes 0.2 um apart merge two 0.26 um via
        # cuts into one 0.46 um polygon (V2.1 wants exactly 0.26) and leave
        # a 0.18 um notch between two Metal2 landings (M2.2a wants 0.28).
        # 36 V2.1 + 7 V2.2a + 14 M2.2a items, all same-net, none a short.
        lanes = self._lanes()
        first, _ = lanes.place("VDD", 1.0, y_pad=2.5, track_y=10.0, half_w=self.HW, half_h=self.HH)
        second, _ = lanes.place("VDD", 1.2, y_pad=2.5, track_y=10.0, half_w=self.HW, half_h=self.HH)
        gap = abs(second - first)
        self.assertTrue(
            gap < 1e-9 or gap >= P.ROW_LANE_OFFSET_UM - 1e-9,
            f"same-net lanes {first} and {second} neither coincide nor clear the pitch",
        )

    def test_a_same_net_lane_pair_a_fraction_of_a_pitch_apart_is_a_conflict(self):
        # The predicate directly: resolve_conflicts() must see this pair as
        # something to repair, not as a same-net merge to wave through.
        lanes = self._lanes()
        lanes._placed.append(("VDD", 1.0, 1.0, 2.5, 10.0, 2.5, self.HW, self.HH))
        lanes._placed.append(("VDD", 1.2, 1.2, 2.5, 10.0, 2.5, self.HW, self.HH))
        self.assertIsNotNone(lanes._find_metal1_conflict())

    def test_two_shapes_a_tenth_of_a_micron_apart_are_a_conflict(self):
        # 0.07 um apart is not a short and is a plain M1.2a violation --
        # 40 of #451's items. The old strict-overlap predicate said "clear".
        gap = 0.07
        self.assertLess(gap, P.METAL1_MIN_SPACE_UM)
        a = (0.0, 0.0, 1.0, 1.0)
        b = (1.0 + gap, 0.0, 2.0, 1.0)
        self.assertTrue(P.RiserLanes._too_close(a, b, P.METAL1_MIN_SPACE_UM))
        self.assertFalse(P.RiserLanes._boxes_overlap(a, b), "not a short -- which is exactly the point")

    def test_two_shapes_touching_only_at_a_corner_are_a_conflict(self):
        # A staircase of two rectangles whose concave corners are 0.16 um
        # apart in each axis measures 0.226 um diagonally -- 0.004 um inside
        # M1.1's 0.23 um minimum *width*. 16 of #451's items. An axis-wise
        # test would call this clear; _too_close() deliberately does not.
        a = (0.0, 0.0, 1.0, 1.0)
        b = (1.1, 1.1, 2.0, 2.0)
        self.assertTrue(P.RiserLanes._too_close(a, b, P.METAL1_MIN_SPACE_UM))

    def test_two_device_pads_are_never_a_conflict_with_each_other(self):
        # The one exempt pair, and the reason the old epsilon existed:
        # mosfet()/tap_strip() draw device pads before any riser is placed,
        # so their mutual spacing is a fixed, already deck-clean fact this
        # router cannot improve. Rejecting a placement over one would only
        # refuse to route across a violation it has no way to fix.
        a = (0.0, 0.0, 1.0, 1.0)
        b = (1.05, 0.0, 2.0, 1.0)
        self.assertFalse(P.RiserLanes._pair_too_close(a, True, b, True))
        self.assertTrue(P.RiserLanes._pair_too_close(a, True, b, False))
        self.assertTrue(P.RiserLanes._pair_too_close(a, False, b, False))

    def test_a_riser_landing_never_sits_on_another_nets_metal2_bus(self):
        # A riser whose own pad sits inside the track band drops a Metal2
        # landing there; MCW's W=30u comp puts this block's VSS pads at
        # y~40, and one of them already landed within 0.0 um of XSCH_P1's
        # own bus -- a cross-net Metal2 short avoided only by the two
        # shapes' X ranges happening not to meet.
        lanes = P.RiserLanes([("VSS", 1.0, 40.0, 30.0, 0.23, 0.23)], bus_ys={"VSS": 30.0, "OTHER": 40.0})
        _x, jog_y = lanes.place("VSS", 1.0, y_pad=40.0, track_y=30.0, half_w=0.23, half_h=0.23)
        keepout = P.VIA_LANDING_HALF_Y_UM + P.METAL2_WIRE_WIDTH_UM / 2.0 + P.METAL2_MIN_SPACE_UM
        self.assertGreaterEqual(abs(jog_y - 40.0), keepout - 1e-9)

    def test_lanes_are_a_global_grid_not_a_per_riser_ladder(self):
        # A ladder anchored on each riser's own natural x plants lanes at
        # arbitrary real coordinates and strands up to a pitch of space on
        # either side of each. Measured on this block, that stranding left
        # VDD's riser at x=21.21 with no legal lane within 20 um. Every lane
        # must be a whole number of pitches from one shared origin.
        groups = [("A", 0.0, 0.0, 10.0, 0.23, 0.23), ("B", 1.11, 0.0, 10.0, 0.23, 0.23)]
        lanes = P.RiserLanes(groups)
        placed = [lanes.place(net, x, y_pad=0.0, track_y=10.0, half_w=0.23, half_h=0.23)[0] for net, x, *_ in groups]
        steps = (placed[1] - placed[0]) / P.ROW_LANE_OFFSET_UM
        self.assertAlmostEqual(steps, round(steps), places=9, msg=f"lanes {placed} are not on one grid")


class BuiltLayoutConnectivityTests(unittest.TestCase):
    """Checks on the full block's drawn geometry itself.

    ``build_lock_detector()`` embeds ``xor2`` (as ``XERR``) -- a dense-enough
    riser conflict graph that ``RiserLanes.resolve_conflicts()``'s pairwise
    repair pass could not converge on (issue #347); ``route_all_nets()``'s
    ``late_nets`` (used here via ``build.py``'s ``defer_supply_routing``)
    fixes that by placing ``VDD``/``VSS`` -- present on almost every column,
    the graph's own biggest source of interference -- only after every
    signal net already has a settled position (see that parameter's own
    docstring for why that converges where full natural-x interleaving does
    not).
    """

    @classmethod
    def setUpClass(cls):
        cls.canvas = build.build_lock_detector(canvas_cls=checks.RecordingCanvas)

    def test_no_two_nets_are_shorted(self):
        hits = checks.shorted_pairs(self.canvas.conductors)
        self.assertEqual(hits, [], f"{len(hits)} cross-net same-layer overlap(s): {hits[:10]}")

    def test_no_vdd_vss_short_in_particular(self):
        # The concrete pair issue #322 reported (a VDD via2 landing pad
        # overlapping a VSS Metal3 riser). Re-checked explicitly in addition
        # to the general shorted_pairs() sweep above.
        hits = checks.shorted_pairs(self.canvas.conductors)
        vdd_vss = [h for h in hits if {h[0], h[1]} == {"VDD", "VSS"}]
        self.assertEqual(vdd_vss, [])

    def test_every_net_is_one_connected_island(self):
        opens = checks.disconnected_nets(self.canvas.conductors, self.canvas.vias)
        self.assertEqual(opens, [], f"net(s) split into multiple islands: {opens}")

    def test_conductors_were_actually_recorded(self):
        # A regression guard on the test itself: if net-tagging silently
        # stopped working (e.g. a canvas.net() wrapper removed by a future
        # edit), shorted_pairs()/disconnected_nets() would both trivially
        # pass on an empty list. Both VDD and VSS must appear on Metal1 (a
        # device pad), Metal2 (a bus) and Metal3 (a riser) at minimum.
        by_net_layer = {(c[0], c[1]) for c in self.canvas.conductors}
        for net in ("VDD", "VSS"):
            for layer in ("metal1", "metal2", "metal3"):
                self.assertIn((net, layer), by_net_layer, f"{net}/{layer} never recorded")
        self.assertGreater(len(self.canvas.conductors), 100)


class StandaloneCellConnectivityTests(unittest.TestCase):
    """The same checks on every standalone sub-cell build (issue #322's own
    acceptance criteria: the fix must hold for every net, not just VDD/VSS,
    and every ``build_*`` in this package shares ``route_net()``)."""

    def _assert_clean(self, canvas: checks.RecordingCanvas) -> None:
        self.assertEqual(checks.shorted_pairs(canvas.conductors), [])
        self.assertEqual(checks.disconnected_nets(canvas.conductors, canvas.vias), [])

    def test_inv(self):
        self._assert_clean(build.build_inv_standalone(canvas_cls=checks.RecordingCanvas))

    def test_nand2(self):
        self._assert_clean(build.build_nand2_standalone(canvas_cls=checks.RecordingCanvas))

    def test_schmitt(self):
        self._assert_clean(build.build_schmitt_standalone(canvas_cls=checks.RecordingCanvas))

    def test_xor2(self):
        # xor2's own dense, 4-NAND2 composition produces a Metal1 riser
        # conflict graph (~40 risers, several mutually interfering) that
        # RiserLanes.resolve_conflicts()'s pairwise repair could not
        # converge on within its own try/round budget (issue #347) --
        # build_xor2_standalone() now opts into route_all_nets()'s
        # late_nets (via build.py's defer_supply_routing), which placing
        # VDD/VSS last resolves (see that parameter's own docstring).
        self._assert_clean(build.build_xor2_standalone(canvas_cls=checks.RecordingCanvas))

    def test_delaywin(self):
        self._assert_clean(build.build_delaywin_standalone(canvas_cls=checks.RecordingCanvas))


class ReferenceNetlistTests(unittest.TestCase):
    """``build.reference_netlist()`` (issue #440) -- pure Python, no
    ``klayout.db`` needed: it only reads and flattens the already-committed
    ``design/netlist/lock_detector.spice`` (``harness.spice_flatten``)."""

    def test_committed_netlist_exists(self):
        self.assertTrue(
            build.NETLIST_PATH.exists(),
            f"{build.NETLIST_PATH} -- regenerate with ./design/netlist.sh --top lock_detector",
        )

    def test_top_level_ports_are_the_full_schematic_pin_list(self):
        ref = build.reference_netlist()
        self.assertEqual(
            ref.splitlines()[0],
            ".subckt lock_detector UP DN LOCK VWIN LDT0 LDT1 LDT2 LDT3 VDD VSS",
        )

    def test_device_count_is_117_the_dr014_trimmed_delaywin_included(self):
        # xor2 (4x nand2 = 16) + delaywin (84, DR-014's trimmed cell -- see
        # design/gen_delaywin.py) + nand2 (4) + inv (2) + MDNW/MUPW/MCW (3,
        # standalone) + schmitt (6) + inv (2) = 117.
        ref = build.reference_netlist()
        device_lines = [l for l in ref.splitlines() if l.startswith("M_")]
        self.assertEqual(len(device_lines), 117)

    def test_reference_names_the_ldt_trim_pins(self):
        # DR-014's 4-bit static process trim (issue #411). Before issue #449,
        # build_lock_detector() drew no LDT0-3 pin and a 12-device (not
        # 84-device) delaywin load, so LVS against this reference mismatched
        # -- see this evidence directory's own PROOF.md addenda. #449 closed
        # that gap: build_lock_detector() now draws all four pins too (see
        # build.TRIM_PINS), and the block LVS-matches this same reference.
        ref = build.reference_netlist()
        for pin in ("LDT0", "LDT1", "LDT2", "LDT3"):
            self.assertIn(pin, ref.splitlines()[0])


#: This block's own evidence directory (DRC claim at #296, LVS claim at #440).
EVIDENCE_DIR = LAYOUT_DIR / "evidence" / "lock-detector-layout"

#: ``run_lvs.py``'s own match verdict, verbatim. The same substring
#: ``layout/lib/check-layout-status-claims.sh`` greps for when it decides
#: whether this block counts as LVS-matched in README.md / the Challenge #5
#: proposal -- asserted here too so the two cannot drift apart silently.
LVS_MATCH_VERDICT = "Congratulations! Netlists match."


class LvsEvidenceTests(unittest.TestCase):
    """The committed block-level LVS record (issue #440).

    Pure file inspection -- no PDK, no KLayout. Re-running the deck is
    ``layout/run_pv.py lvs``'s job and is recorded in ``PROOF.md``; what
    these tests defend is that the *recorded* verdict stays in the tree and
    stays a match, so a later change that quietly breaks this block's LVS
    cannot leave a stale "4 of the 4 are LVS-matched" claim standing in two
    status documents. This is the same guard
    ``test_pfdcp_block_layout.LvsEvidenceTests`` applies to ``pfd_cp``.
    """

    def test_lvs_clean_directory_exists(self):
        self.assertTrue(
            (EVIDENCE_DIR / "lvs-clean").is_dir(),
            f"{EVIDENCE_DIR / 'lvs-clean'} -- the deck output for this "
            "block's LVS claim; see PROOF.md for the exact invocation",
        )

    def test_the_recorded_deck_log_reports_a_match(self):
        log = EVIDENCE_DIR / "lvs-clean" / "lvs.stdout.log"
        self.assertTrue(log.is_file(), f"{log} missing")
        self.assertIn(LVS_MATCH_VERDICT, log.read_text())

    def test_the_recorded_deck_log_reports_no_mismatch(self):
        log = EVIDENCE_DIR / "lvs-clean" / "lvs.stdout.log"
        self.assertNotIn("Netlists don't match", log.read_text())

    def test_the_run_committed_its_reference_extracted_and_database_files(self):
        for name in ("lock_detector.spice", "lock_detector.cir", "lock_detector.lvsdb"):
            with self.subTest(name=name):
                self.assertTrue((EVIDENCE_DIR / "lvs-clean" / name).is_file())

    def test_the_committed_reference_is_what_reference_netlist_produces_today(self):
        # The claim is only as good as what it was compared against: if
        # design/netlist/lock_detector.spice or the flattener moves, the
        # committed match log is measuring a netlist that no longer exists.
        committed = (EVIDENCE_DIR / "lvs-clean" / "lock_detector.spice").read_text()
        self.assertEqual(committed, build.reference_netlist())

    def test_the_first_runs_recorded_mismatch_is_kept_not_deleted(self):
        # Evidence here is append-only: the mismatch this block's first
        # block-level LVS run actually found (issue #440's own first pass,
        # 117 reference devices vs. a 45-device pre-DR-014 layout) stays
        # committed under lvs-attempt/ beside the match that superseded it.
        attempt = EVIDENCE_DIR / "lvs-attempt" / "lvs.stdout.log"
        self.assertTrue(attempt.is_file(), f"{attempt} -- do not delete")
        self.assertIn("Netlists don't match", attempt.read_text())

    def test_the_independent_recheck_run_also_matched(self):
        # Issue #360: a KLayout newer than this repo's 0.28.16 pin has been
        # observed reporting a *false* LVS mismatch on an unchanged, clean
        # layout. The lvs-clean/ run above was captured on the pinned
        # 0.28.16; PROOF.md Addendum 5 records an independent re-run of the
        # same GDS + same reference on KLayout 0.30.10, which matched. Both
        # logs are committed, and both must keep saying so.
        log = EVIDENCE_DIR / "lvs-recheck-klayout-0.30.10" / "lvs.stdout.log"
        self.assertTrue(log.is_file(), f"{log} missing")
        text = log.read_text()
        self.assertIn(LVS_MATCH_VERDICT, text)
        self.assertNotIn("Netlists don't match", text)


class PinPurposeLayerTests(unittest.TestCase):
    """Net names must land on the *purpose* layers the LVS deck reads.

    Until issue #440 this package took ``_canvas.Canvas``'s ``PIN_LAYER =
    "metal1"`` default and labelled its Metal2 buses on ``"metal2"``, i.e.
    both on the **drawing** datatypes (34/0, 36/0). gf180mcu's LVS deck
    only reads ``labels(34, 10)`` / ``labels(36, 10)``
    (``layers_definitions.lvs``), so every net this block labelled was
    extracted as an anonymous node: its first LVS run extracted as
    ``.SUBCKT lock_detector VSS`` -- a single port, and that one the deck's
    own synthesized substrate net rather than anything drawn here.

    ``vco/primitives.py`` made exactly this correction for its own package
    at issue #367; this is the same correction for this one. Pure constant
    inspection -- no PDK, no KLayout.
    """

    def test_layer_table_declares_both_pin_purposes(self):
        self.assertEqual(P.LAYER["metal1_label"], (34, 10))
        self.assertEqual(P.LAYER["metal2_label"], (36, 10))

    def test_canvas_pins_on_the_metal1_pin_purpose_not_the_drawing_layer(self):
        self.assertEqual(P.Canvas.PIN_LAYER, "metal1_label")
        self.assertNotEqual(P.LAYER[P.Canvas.PIN_LAYER], P.LAYER["metal1"])

    def test_the_two_purpose_layers_are_not_the_drawing_layers(self):
        # A text on 34/0 or 36/0 is invisible to the deck's connectivity
        # step -- the defect this pair of entries exists to prevent.
        self.assertNotEqual(P.LAYER["metal1_label"], P.LAYER["metal1"])
        self.assertNotEqual(P.LAYER["metal2_label"], P.LAYER["metal2"])


if __name__ == "__main__":
    unittest.main()
