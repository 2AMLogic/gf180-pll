#!/usr/bin/env python3
"""Smoke tests for the ``divider_chain`` device-layout helper (issue #306).

Unlike ``test_vco_layout.py``, this module *does* need ``klayout.db``
importable (``devgen.build_stack_cell()`` is exercised directly, not just
its pure-Python device table) -- skipped, not failed, when unavailable, so
a PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks), see ``layout/evidence/divider-inv-proof/PROOF.md`` and
``layout/evidence/divider-tgate-proof/PROOF.md`` -- this file checks the
geometry ``devgen``/``inv_3v3``/``tgate_3v3`` *claim* to build (net
resolution, pin promotion, footprint sanity, the facing-vs-outer net
assignment ``tgate_3v3``'s own bypass-lane routing depends on), not a
substitute for running the decks.
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

from divider_chain import devgen  # noqa: E402
from divider_chain import inv_3v3  # noqa: E402
from divider_chain import tgate_3v3  # noqa: E402


class InvDeviceTableTests(unittest.TestCase):
    """inv_3v3.INV_DEVICES matches design/inv_3v3.sch's own MP/MN."""

    def test_two_devices(self):
        self.assertEqual(len(inv_3v3.INV_DEVICES), 2)

    def test_sizes_match_the_schematic(self):
        sizes = {d.name: (d.kind, d.w_um, d.l_um) for d in inv_3v3.INV_DEVICES}
        self.assertEqual(sizes["MP"], ("pfet", 2.5, 0.28))
        self.assertEqual(sizes["MN"], ("nfet", 1.0, 0.28))

    def test_gate_and_drain_are_shared_nets(self):
        by_name = {d.name: d for d in inv_3v3.INV_DEVICES}
        self.assertEqual(by_name["MP"].gate_net, by_name["MN"].gate_net)
        self.assertEqual(by_name["MP"].gate_net, "A")
        self.assertEqual(by_name["MP"].bottom_net, by_name["MN"].top_net)
        self.assertEqual(by_name["MP"].bottom_net, "Y")

    def test_supplies_are_distinct_boundary_nets(self):
        by_name = {d.name: d for d in inv_3v3.INV_DEVICES}
        self.assertEqual(by_name["MP"].top_net, "VDD")
        self.assertEqual(by_name["MN"].bottom_net, "VSS")

    def test_neither_device_needs_an_explicit_body_net(self):
        # Each device's own supply-facing terminal already *is* the net its
        # body should tie to (MP.top_net=VDD, MN.bottom_net=VSS) -- see
        # devgen.py's docstring for the case (tgate_3v3) that does need one.
        for d in inv_3v3.INV_DEVICES:
            self.assertIsNone(d.body_net)


class TgateDeviceTableTests(unittest.TestCase):
    """tgate_3v3.TGATE_DEVICES matches design/tgate_3v3.sch's own MP/MN."""

    def test_two_devices(self):
        self.assertEqual(len(tgate_3v3.TGATE_DEVICES), 2)

    def test_sizes_match_the_schematic(self):
        sizes = {d.name: (d.kind, d.w_um, d.l_um) for d in tgate_3v3.TGATE_DEVICES}
        self.assertEqual(sizes["MP"], ("pfet", 2.5, 0.28))
        self.assertEqual(sizes["MN"], ("nfet", 1.0, 0.28))

    def test_gates_are_independent(self):
        by_name = {d.name: d for d in tgate_3v3.TGATE_DEVICES}
        self.assertNotEqual(by_name["MP"].gate_net, by_name["MN"].gate_net)
        self.assertEqual(by_name["MP"].gate_net, "GP")
        self.assertEqual(by_name["MN"].gate_net, "GN")

    def test_diffusion_terminals_are_shared_ab_nets(self):
        by_name = {d.name: d for d in tgate_3v3.TGATE_DEVICES}
        terms_mn = {by_name["MN"].top_net, by_name["MN"].bottom_net}
        terms_mp = {by_name["MP"].top_net, by_name["MP"].bottom_net}
        self.assertEqual(terms_mn, {"A", "Y"})
        self.assertEqual(terms_mp, {"A", "Y"})

    def test_facing_pads_share_a_net_not_the_outer_pads(self):
        # MN is stacked below MP (bottom-to-top device list order), so the
        # *facing* pair is MN's top terminal and MP's bottom terminal -- see
        # devgen.py's "TRANSMISSION-GATE TOPOLOGY" docstring section for why
        # only this assignment lets build_stack_cell()'s default connector
        # wire one of the two nets safely, and why the other net needs the
        # bypass-lane router. A wrong assignment here is exactly the bug
        # that produced a real, concretely-observed LVS merged-node failure
        # during this issue's own development (see that same docstring
        # section, and PROOF.md).
        by_name = {d.name: d for d in tgate_3v3.TGATE_DEVICES}
        self.assertEqual(by_name["MN"].top_net, by_name["MP"].bottom_net)
        self.assertNotEqual(by_name["MN"].bottom_net, by_name["MP"].bottom_net)

    def test_bodies_tie_to_the_supplies_not_the_diffusion_terminals(self):
        by_name = {d.name: d for d in tgate_3v3.TGATE_DEVICES}
        self.assertEqual(by_name["MP"].body_net, "VDD")
        self.assertEqual(by_name["MN"].body_net, "VSS")
        # Neither device's body_net matches either of its own diffusion
        # terminals -- the case devgen.py's Device.body_net field exists
        # for (see that module's docstring, "Failure 1").
        for d in tgate_3v3.TGATE_DEVICES:
            self.assertNotIn(d.body_net, (d.top_net, d.bottom_net))


class ReferenceNetlistTests(unittest.TestCase):
    """The hand-written LVS reference netlists match their device tables."""

    def test_inv_declares_both_devices_with_matching_sizes(self):
        netlist = inv_3v3.reference_netlist()
        self.assertIn("pfet_03v3 W=2.5u L=0.28u", netlist)
        self.assertIn("nfet_03v3 W=1u L=0.28u", netlist)

    def test_inv_subckt_name_matches_top_cell(self):
        netlist = inv_3v3.reference_netlist()
        self.assertIn(f".subckt {inv_3v3.TOP_CELL} ", netlist)

    def test_tgate_declares_both_devices_with_matching_sizes(self):
        netlist = tgate_3v3.reference_netlist()
        self.assertIn("pfet_03v3 W=2.5u L=0.28u", netlist)
        self.assertIn("nfet_03v3 W=1u L=0.28u", netlist)

    def test_tgate_subckt_name_matches_top_cell(self):
        netlist = tgate_3v3.reference_netlist()
        self.assertIn(f".subckt {tgate_3v3.TOP_CELL} ", netlist)

    def test_tgate_subckt_declares_all_six_schematic_nets(self):
        netlist = tgate_3v3.reference_netlist()
        header = next(line for line in netlist.splitlines() if line.startswith(".subckt"))
        for net in ("A", "Y", "GN", "GP", "VDD", "VSS"):
            self.assertIn(net, header.split())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildInvStackCellTests(unittest.TestCase):
    """devgen.build_stack_cell() on inv_3v3's device list."""

    @classmethod
    def setUpClass(cls):
        cls.leaf = devgen.build_stack_cell("inv_3v3_test", inv_3v3.INV_DEVICES)

    def test_two_devices_drawn(self):
        self.assertEqual(len(self.leaf.ports), 2)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.leaf.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_only_supply_nets_are_promoted_as_boundary_pins(self):
        # A (gate) and Y (drain) are 2-terminal nets, wired internally, not
        # promoted -- only VDD/VSS (1-terminal in this device list) are.
        self.assertEqual(set(self.leaf.pins), {"VDD", "VSS"})

    def test_nwell_encloses_the_pfet(self):
        self.assertIsNotNone(self.leaf.nwell_box)
        pfet_port = next(p for p in self.leaf.ports if p.kind == "pfet")
        x0, y0, x1, y1 = self.leaf.nwell_box
        self.assertLessEqual(x0, pfet_port.x0)
        self.assertGreaterEqual(x1, pfet_port.x1)
        self.assertLessEqual(y0, pfet_port.y0)
        self.assertGreaterEqual(y1, pfet_port.y3)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTgateStackCellTests(unittest.TestCase):
    """devgen.build_stack_cell() on tgate_3v3's device list, bypass_nets in use."""

    @classmethod
    def setUpClass(cls):
        cls.leaf = devgen.build_stack_cell(
            "tgate_3v3_test", tgate_3v3.TGATE_DEVICES, bypass_nets=frozenset({"A"})
        )

    def test_two_devices_drawn(self):
        self.assertEqual(len(self.leaf.ports), 2)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.leaf.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_only_gate_nets_are_promoted_as_boundary_pins(self):
        # GN/GP are 1-terminal in this device list (independent gates);
        # A/Y are 2-terminal (one direct, one bypass-routed) and wired
        # internally, not promoted -- same convention inv_3v3/pfdcp_inv_3v3
        # already use for their own 2-terminal nets.
        self.assertEqual(set(self.leaf.pins), {"GN", "GP"})

    def test_footprint_is_wider_than_the_no_bypass_case(self):
        # The bypass lane sits to the right of the widest device's own
        # drawn edge, so a cell that uses it should measurably occupy more
        # x-extent than build_stack_cell() would draw for the same device
        # list with no bypass net requested.
        no_bypass = devgen.build_stack_cell("tgate_3v3_test_nobypass", tgate_3v3.TGATE_DEVICES)
        x0, _, x1, _ = self.leaf.footprint
        nx0, _, nx1, _ = no_bypass.footprint
        self.assertGreater(x1 - x0, nx1 - nx0)

    def test_nwell_encloses_the_pfet(self):
        self.assertIsNotNone(self.leaf.nwell_box)
        pfet_port = next(p for p in self.leaf.ports if p.kind == "pfet")
        x0, y0, x1, y1 = self.leaf.nwell_box
        self.assertLessEqual(x0, pfet_port.x0)
        self.assertGreaterEqual(x1, pfet_port.x1)
        self.assertLessEqual(y0, pfet_port.y0)
        self.assertGreaterEqual(y1, pfet_port.y3)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class NetResolutionEdgeCaseTests(unittest.TestCase):
    """build_stack_cell()'s net-count validation, generalized to this package."""

    def test_single_device_stack_raises_on_unresolvable_net(self):
        # A 3-terminal net (three devices sharing one gate_net) is out of
        # this module's supported topology (see devgen.py's module
        # docstring) -- asserts build_stack_cell() actually raises rather
        # than silently dropping it.
        three_way = (
            devgen.Device(name="U0", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="A", bottom_net="VSS"),
            devgen.Device(name="U1", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="B", bottom_net="A"),
            devgen.Device(name="U2", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="VDD", bottom_net="B"),
        )
        with self.assertRaises(ValueError):
            devgen.build_stack_cell("bad_stack_test", three_way)


PITCH = devgen.METAL2_TRACK_PITCH_UM          # 0.75
CLEAR = PITCH - devgen.METAL2_WIRE_WIDTH_UM   # 0.41
HALF = devgen.TRACK_HALF_HEIGHT_UM            # 0.22


class BoxesClearTests(unittest.TestCase):
    """devgen._boxes_clear(): the separating-axis spacing predicate
    pack_tracks_over_devices() is built on (issue #458).

    Every case below is arithmetic on the literal boxes, so the expected
    answer is checkable by hand rather than by running the router.
    """

    def test_far_apart_in_x_is_clear_however_much_they_overlap_in_y(self):
        self.assertTrue(devgen._boxes_clear((0, 0, 1, 1), (1.5, 0, 2.5, 1), 0.41))

    def test_far_apart_in_y_is_clear_however_much_they_overlap_in_x(self):
        self.assertTrue(devgen._boxes_clear((0, 0, 1, 1), (0, 1.5, 1, 2.5), 0.41))

    def test_close_on_both_axes_is_not_clear(self):
        # 0.4 um apart in x AND 0.4 um apart in y, against a 0.41 requirement.
        self.assertFalse(devgen._boxes_clear((0, 0, 1, 1), (1.4, 1.4, 2, 2), 0.41))

    def test_exactly_the_clearance_counts_as_clear(self):
        self.assertTrue(devgen._boxes_clear((0, 0, 1, 1), (1.41, 0, 2, 1), 0.41))

    def test_a_hair_under_the_clearance_does_not(self):
        self.assertFalse(devgen._boxes_clear((0, 0, 1, 1), (1.40, 0, 2, 1), 0.41))


class RiserLandingBoxesTests(unittest.TestCase):
    """The squares _riser() drops on each pad, stated up front so the track
    assignment can avoid them before route_net() has drawn anything."""

    def test_one_square_per_pad_sized_from_the_via1_constants(self):
        half = devgen.VIA1_SIZE_UM / 2.0 + devgen.VIA_ENCLOSURE_UM
        (box,) = devgen.riser_landing_boxes([(10.0, 4.0)])
        self.assertAlmostEqual(box[0], 10.0 - half, places=6)
        self.assertAlmostEqual(box[1], 4.0 - half, places=6)
        self.assertAlmostEqual(box[2], 10.0 + half, places=6)
        self.assertAlmostEqual(box[3], 4.0 + half, places=6)
        # 0.44 um square -- the number devgen's own docstrings quote.
        self.assertAlmostEqual(box[2] - box[0], 0.44, places=6)

    def test_the_landing_square_is_taller_than_the_bus_wire(self):
        """Why TRACK_HALF_HEIGHT_UM is 0.22 and not METAL2_WIRE_WIDTH_UM/2."""
        self.assertGreater(devgen.TRACK_HALF_HEIGHT_UM, devgen.METAL2_WIRE_WIDTH_UM / 2.0)
        self.assertAlmostEqual(devgen.TRACK_HALF_HEIGHT_UM, 0.22, places=6)


class PackTracksOverDevicesTests(unittest.TestCase):
    """Known-answer tests for the obstacle-aware track assignment (issue #458).

    The synthetic nets below are pad lists, exactly what
    ``divider_chain.build()``/``div23_cell.build()`` hand it; every expected
    track_y is ``y_floor + k*0.75`` for a k derivable by hand from the
    obstacles given.
    """

    def test_with_no_obstacles_it_stacks_from_y_floor_like_pack_tracks(self):
        """The degenerate case must equal pack_tracks(base_y=y_floor), so the
        new function is a strict generalization rather than a different
        algorithm wearing the same name."""
        nets = {
            "A": [(0.0, 0.0), (10.0, 0.0)],
            "B": [(5.0, 0.0), (15.0, 0.0)],   # overlaps A
            "C": [(30.0, 0.0), (40.0, 0.0)],  # overlaps neither
        }
        got = devgen.pack_tracks_over_devices(nets, y_floor=100.0, obstacles=[])
        self.assertEqual(got, devgen.pack_tracks(nets, base_y=100.0))
        # and, concretely: A and C share the bottom track, B opens a second.
        self.assertEqual(got, {"A": 100.0, "C": 100.0, "B": 100.0 + PITCH})

    def test_y_floor_is_a_hard_lower_bound_even_with_the_plane_below_empty(self):
        got = devgen.pack_tracks_over_devices({"A": [(0.0, -50.0)]}, y_floor=7.0, obstacles=[])
        self.assertEqual(got["A"], 7.0)

    def test_a_track_steps_up_past_an_obstacle_band_in_its_own_x_range(self):
        # One obstacle spanning y = -1 .. 1 across the net's whole x range.
        # y = 0 and 0.75 are blocked (0.75 - 0.22 = 0.53 < 1 + 0.41); 1.50 is
        # the first legal step (1.50 - 0.22 = 1.28 >= 1 + 0.41 = 1.41? no) --
        # 2.25 - 0.22 = 2.03 >= 1.41, so 2.25 is the answer.
        got = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0), (10.0, 0.0)]},
            y_floor=0.0,
            obstacles=[(-5.0, -1.0, 15.0, 1.0)],
        )
        self.assertAlmostEqual(got["A"], 2.25, places=6)

    def test_an_obstacle_outside_a_nets_x_range_does_not_push_it_up(self):
        """The property the whole lever rests on: clearance is judged per net,
        against the obstacles that net's own drawn rectangle can actually
        reach -- which is why a glue-local net can use a y a block-wide supply
        trunk cannot."""
        obstacle = [(100.0, -1.0, 120.0, 1.0)]
        local = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0), (10.0, 0.0)]}, y_floor=0.0, obstacles=obstacle
        )
        spanning = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0), (200.0, 0.0)]}, y_floor=0.0, obstacles=obstacle
        )
        self.assertAlmostEqual(local["A"], 0.0, places=6)
        self.assertAlmostEqual(spanning["A"], 2.25, places=6)

    def test_a_free_corridor_between_two_obstacle_bands_is_used(self):
        """The inter-row channel, in miniature: two obstacle bands with a gap
        between them, and a net that fits in the gap rather than climbing over
        the upper band."""
        obstacles = [(-5.0, -1.0, 15.0, 0.20), (-5.0, 3.0, 15.0, 9.0)]
        got = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0), (10.0, 0.0)]}, y_floor=0.0, obstacles=obstacles
        )
        # Legal window: 0.20 + 0.41 + 0.22 = 0.83 up to 3.0 - 0.63 = 2.37.
        # On the 0.75 grid from 0.0 that is 1.50 (and 2.25); the lowest wins.
        self.assertAlmostEqual(got["A"], 1.50, places=6)
        self.assertLess(got["A"], 9.0, "the net climbed over the corridor instead of into it")

    def test_two_nets_that_overlap_in_x_never_share_a_track(self):
        got = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0), (10.0, 0.0)], "B": [(5.0, 0.0), (15.0, 0.0)]},
            y_floor=0.0,
            obstacles=[],
        )
        self.assertNotEqual(got["A"], got["B"])
        self.assertAlmostEqual(abs(got["A"] - got["B"]), PITCH, places=6)

    def test_two_nets_on_one_track_keep_pack_tracks_own_x_clearance(self):
        """Same-track separation is judged exactly as pack_tracks() judges it
        -- an x gap of at least `clearance` between the two drawn extents,
        landing squares included."""
        # Extents are pad-x +/- 0.22, so pads at 0 and 0.85 give a 0.41 gap.
        just_clear = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0)], "B": [(0.44 + CLEAR, 0.0)]}, y_floor=0.0, obstacles=[]
        )
        self.assertEqual(just_clear["A"], just_clear["B"])
        too_close = devgen.pack_tracks_over_devices(
            {"A": [(0.0, 0.0)], "B": [(0.44 + CLEAR - 0.01, 0.0)]}, y_floor=0.0, obstacles=[]
        )
        self.assertNotEqual(too_close["A"], too_close["B"])

    def test_a_nets_own_pad_square_is_an_obstacle_to_itself(self):
        """Deliberately conservative: M2.2a is a raw spacing check with no net
        awareness, so a track that lands a hair away from its *own* pad's
        landing square would leave exactly the notch that rule reports."""
        pads = [(0.0, 0.0)]
        got = devgen.pack_tracks_over_devices(
            {"A": pads}, y_floor=0.0, obstacles=devgen.riser_landing_boxes(pads)
        )
        self.assertGreaterEqual(got["A"] - HALF, 0.22 + CLEAR)

    def test_it_raises_by_name_on_a_net_with_no_pads(self):
        with self.assertRaises(ValueError) as cm:
            devgen.pack_tracks_over_devices({"EMPTY": []}, y_floor=0.0, obstacles=[])
        self.assertIn("EMPTY", str(cm.exception))

    def test_the_result_does_not_depend_on_dict_insertion_order(self):
        a = {"A": [(0.0, 0.0), (10.0, 0.0)], "B": [(5.0, 0.0), (15.0, 0.0)], "C": [(30.0, 0.0)]}
        b = {"C": [(30.0, 0.0)], "B": [(5.0, 0.0), (15.0, 0.0)], "A": [(0.0, 0.0), (10.0, 0.0)]}
        self.assertEqual(
            devgen.pack_tracks_over_devices(a, y_floor=0.0, obstacles=[]),
            devgen.pack_tracks_over_devices(b, y_floor=0.0, obstacles=[]),
        )


@unittest.skipUnless(_HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class Metal2BoxesTests(unittest.TestCase):
    """metal2_boxes() must see through a placed instance, because that is the
    obstacle divider_chain.py actually has to route around."""

    def test_it_reads_back_shapes_drawn_directly_into_the_canvas(self):
        canvas = devgen.Canvas("metal2_boxes_direct_test")
        canvas.rect("metal2", 1.0, 2.0, 3.0, 4.0)
        self.assertEqual(
            [tuple(round(v, 6) for v in b) for b in devgen.metal2_boxes(canvas)],
            [(1.0, 2.0, 3.0, 4.0)],
        )

    def test_it_ignores_other_layers(self):
        canvas = devgen.Canvas("metal2_boxes_layers_test")
        canvas.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        canvas.rect("metal3", 0.0, 0.0, 1.0, 1.0)
        self.assertEqual(devgen.metal2_boxes(canvas), [])

    def test_it_sees_metal2_inside_an_unflattened_placed_instance(self):
        import klayout.db as db

        canvas = devgen.Canvas("metal2_boxes_instance_test")
        sub = canvas.layout.create_cell("sub")
        dbu_per_um = int(round(1.0 / canvas.dbu))
        sub.shapes(canvas.layout.layer(*devgen.LAYER["metal2"])).insert(
            db.Box(0, 0, 2 * dbu_per_um, 1 * dbu_per_um)
        )
        canvas.top.insert(
            db.CellInstArray(sub.cell_index(), db.Trans(db.Vector(10 * dbu_per_um, 20 * dbu_per_um)))
        )
        self.assertEqual(
            [tuple(round(v, 6) for v in b) for b in devgen.metal2_boxes(canvas)],
            [(10.0, 20.0, 12.0, 21.0)],
        )


if __name__ == "__main__":
    unittest.main()
