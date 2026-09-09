#!/usr/bin/env python3
"""Tests for the ``cp_array`` common-centroid N/P array + bias branch layout
(issue #320, Part 3b of #294, a decomposition of #301).

Like ``test_cp_leg_devgen.py``/``test_cp_dumpbuf_layout.py``, the
``klayout.db``-dependent tests (anything that calls ``cp_array.build()``) are
skipped, not failed, when ``klayout.db`` is unavailable, so a PDK/PV-less
checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC-clean claim (which additionally needs the PDK's own
signoff deck), see ``layout/evidence/cp-array-proof/PROOF.md`` -- this file
checks the geometry/placement math ``cp_array`` *claims* to build (common-
centroid placement, N/P non-overlap, bias-branch device table, net mapping),
not a substitute for running the deck. Where ``klayout.db`` is importable,
``ConnectivityTests`` additionally extracts the finished GDS's own Metal1-3
connectivity with ``netcheck.py`` -- the only check that can see a short or
an open (a DRC deck cannot; issue #359).
"""

from __future__ import annotations

import sys
import tempfile
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

from pfd_cp import cp_array, netcheck  # noqa: E402


class LegOffsetsTests(unittest.TestCase):
    """leg_offsets() -- the tripod placement satisfies the centroid equation
    for arbitrary leg dimensions, and clears every pairwise overlap."""

    def test_offsets_satisfy_centroid_equation(self):
        for w, h, gap in ((8.77, 4.6, 3.0), (17.27, 6.23, 3.0), (1.0, 1.0, 0.5), (50.0, 2.0, 10.0)):
            offsets = cp_array.leg_offsets(w, h, gap)
            base = offsets["base"]
            others = [offsets[k] for k in ("t0", "t1a", "t1b")]
            cp_array.check_common_centroid(base, others)  # must not raise

    def test_base_is_the_origin(self):
        offsets = cp_array.leg_offsets(10.0, 5.0, 2.0)
        self.assertEqual(offsets["base"], (0.0, 0.0))

    def test_t0_t1a_are_mirrored_left_right(self):
        offsets = cp_array.leg_offsets(10.0, 5.0, 2.0)
        t0, t1a = offsets["t0"], offsets["t1a"]
        self.assertEqual(t0[0], -t1a[0])
        self.assertEqual(t0[1], t1a[1])

    def test_t1b_is_directly_above_base(self):
        offsets = cp_array.leg_offsets(10.0, 5.0, 2.0)
        t1b = offsets["t1b"]
        self.assertEqual(t1b[0], 0.0)
        self.assertGreater(t1b[1], 0.0)

    def test_pairwise_boxes_do_not_overlap(self):
        w, h, gap = 8.77, 4.6, 3.0
        offsets = cp_array.leg_offsets(w, h, gap)
        footprint = (-0.5, 0.0, w - 0.5, h)  # an arbitrary footprint of the right size
        boxes = {name: cp_array._translate_box(footprint, *off) for name, off in offsets.items()}
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                self.assertFalse(
                    cp_array.boxes_overlap(boxes[a], boxes[b]), f"{a} and {b} overlap: {boxes[a]} {boxes[b]}"
                )


class CentroidCheckTests(unittest.TestCase):
    """centroid_um()/check_common_centroid() -- the 2-D analog of
    vco/mirror.py's own leg_centroid_um()/check_common_centroid()."""

    def test_centroid_of_symmetric_points(self):
        c = cp_array.centroid_um([(-1.0, 0.0), (1.0, 0.0), (0.0, 0.0)])
        self.assertAlmostEqual(c[0], 0.0)
        self.assertAlmostEqual(c[1], 0.0)

    def test_check_passes_when_base_is_the_mean(self):
        cp_array.check_common_centroid((0.0, 0.0), [(-2.0, -1.0), (2.0, -1.0), (0.0, 2.0)])

    def test_check_raises_when_base_is_off_centre(self):
        with self.assertRaises(ValueError):
            cp_array.check_common_centroid((0.1, 0.0), [(-2.0, -1.0), (2.0, -1.0), (0.0, 2.0)])

    def test_centroid_um_needs_at_least_one_point(self):
        with self.assertRaises(ValueError):
            cp_array.centroid_um([])


class BoxesOverlapTests(unittest.TestCase):
    def test_disjoint_boxes(self):
        self.assertFalse(cp_array.boxes_overlap((0, 0, 1, 1), (2, 0, 3, 1)))

    def test_overlapping_boxes(self):
        self.assertTrue(cp_array.boxes_overlap((0, 0, 2, 2), (1, 1, 3, 3)))

    def test_touching_boxes_do_not_overlap(self):
        # Sharing only an edge (zero-area intersection) is not an overlap.
        self.assertFalse(cp_array.boxes_overlap((0, 0, 1, 1), (1, 0, 2, 1)))


class DeclutterRiserXTests(unittest.TestCase):
    """declutter_riser_x() -- the global-across-nets riser X separation this
    module's own mesh routing relies on for M3.2a safety."""

    def test_well_separated_points_are_unchanged(self):
        pts = [("A", 0.0, 0.0), ("B", 10.0, 0.0), ("C", 20.0, 0.0)]
        out = cp_array.declutter_riser_x(pts, 1.0)
        self.assertEqual(out, pts)

    def test_close_different_nets_are_pushed_apart(self):
        pts = [("A", 0.0, 0.0), ("B", 0.3, 5.0)]
        out = cp_array.declutter_riser_x(pts, 1.0)
        xs = {net: x for net, x, _y in out}
        self.assertGreaterEqual(abs(xs["B"] - xs["A"]), 1.0)

    def test_exact_same_net_tie_stays_tied_even_after_a_cascading_nudge(self):
        # Regression test for a real bug hit during this module's own
        # development: two ICN pads at an identical natural X, with an
        # intervening VSS point close enough to push the first ICN forward.
        # Both ICN points must end up at the SAME final X (see
        # declutter_riser_x()'s own docstring).
        pts = [
            ("VSS", 2.5, -0.21),
            ("VSS", 2.5, 7.39),
            ("ICN", 3.2, 11.2),
            ("ICN", 3.2, 3.6),
        ]
        out = cp_array.declutter_riser_x(pts, 1.0)
        icn_xs = {x for net, x, _y in out if net == "ICN"}
        self.assertEqual(len(icn_xs), 1, f"ICN points diverged: {out}")

    def test_declutter_never_changes_y(self):
        pts = [("A", 0.0, 1.0), ("B", 0.1, 2.0), ("C", 0.15, 3.0)]
        out = cp_array.declutter_riser_x(pts, 1.0)
        for (net, _x0, y0), (net2, _x1, y1) in zip(pts, out):
            self.assertEqual(net, net2)
            self.assertEqual(y0, y1)

    def test_output_is_pairwise_safe(self):
        # A denser, more adversarial case: many points within a couple of um
        # of each other, several sharing exact natural X.
        pts = [
            ("N0", 0.0, 0.0),
            ("N1", 0.05, 1.0),
            ("N2", 0.05, 2.0),
            ("N3", 0.12, 3.0),
            ("N4", 0.2, 4.0),
            ("N5", 5.0, 5.0),
            ("N6", 5.02, 6.0),
        ]
        out = cp_array.declutter_riser_x(pts, 1.0)
        by_x = sorted(out, key=lambda t: t[1])
        for (net_a, xa, _ya), (net_b, xb, _yb) in zip(by_x, by_x[1:]):
            gap = xb - xa
            self.assertTrue(gap == 0.0 or gap >= 1.0, f"{net_a}@{xa} vs {net_b}@{xb}: gap {gap}")

    def test_exact_tie_different_nets_are_pushed_apart_not_collapsed(self):
        # Regression test for issue #359: an earlier version of this
        # function treated *any* exact natural-X tie as safe to collapse
        # onto one shared riser column, reasoning that two risers at the
        # same natural X could only ever be the same net. That is false --
        # cp_leg's own EN/ENB gate-tab pads share one local X on every leg,
        # and every leg maps them to two different nets -- so an exact tie
        # between different nets must now be pushed apart, exactly like a
        # near-miss, not silently merged into one Metal3 column (a real
        # short that DRC cannot see).
        pts = [("VDD", -0.8, 2.55), ("VSS", -0.8, 0.65)]
        out = cp_array.declutter_riser_x(pts, 1.0)
        xs = {net: x for net, x, _y in out}
        self.assertNotEqual(xs["VDD"], xs["VSS"])
        self.assertGreaterEqual(abs(xs["VDD"] - xs["VSS"]), 1.0)

    def test_exact_tie_same_net_still_collapses(self):
        # The one case the original invariant does hold for: two pads of
        # the *same* net sharing an identical natural X (e.g. two legs
        # translated onto the same dx) are still safe -- and correct -- to
        # collapse onto one shared riser column.
        pts = [("IBN", 0.5, 2.99), ("IBN", 0.5, 10.59)]
        out = cp_array.declutter_riser_x(pts, 1.0)
        xs = [x for _net, x, _y in out]
        self.assertEqual(xs[0], xs[1])


class CheckRiserColumnsTests(unittest.TestCase):
    """check_riser_columns() -- the build-time proof (issue #359) that a
    two-nets-on-one-column allocation cannot be reintroduced silently."""

    def test_well_separated_distinct_nets_pass(self):
        points = [("A", 0.0, 0.0), ("B", 1.5, 3.0), ("C", 3.0, -2.0)]
        cp_array.check_riser_columns(points)  # must not raise

    def test_same_net_sharing_a_column_passes(self):
        points = [("VSS", 0.0, 0.2), ("VSS", 0.0, 1.1), ("B0B", 1.5, 0.6)]
        cp_array.check_riser_columns(points)  # must not raise

    def test_returns_the_decluttered_plan(self):
        points = [("A", 0.0, 0.0), ("B", 0.3, 1.0)]
        planned = cp_array.check_riser_columns(points)
        self.assertEqual(planned, cp_array.declutter_riser_x(points))

    def test_verify_raises_on_a_synthetic_two_nets_one_column_plan(self):
        # Synthetic two-nets-one-column input, as issue #359's own test plan
        # asks for -- the exact defect this whole mechanism exists to catch,
        # fed directly to the verification half (declutter_riser_x() itself
        # can no longer produce this from any real input -- see
        # DeclutterRiserXTests -- so this proves the *check* still fires if
        # that invariant were ever broken again).
        with self.assertRaises(ValueError):
            cp_array._verify_riser_plan([("A", 0.0, 0.0), ("B", 0.0, 1.0)], 1.0)

    def test_verify_raises_on_too_close_distinct_columns(self):
        with self.assertRaises(ValueError):
            cp_array._verify_riser_plan([("A", 0.0, 0.0), ("B", 0.4, 0.0)], 1.0)


class BiasDeviceTableTests(unittest.TestCase):
    """BIAS_DEVICES_N/BIAS_DEVICES_P match design/cp.sch's own MBN/MCN/MBP/MCP
    instances (sizes and diode-connected nets)."""

    def test_mbn_matches_schematic(self):
        mbn = BiasDeviceTableTests._by_name(cp_array.BIAS_DEVICES_N, "MBN")
        self.assertEqual(mbn.kind, "nfet")
        self.assertEqual((mbn.w_um, mbn.l_um), (16.0, 1.0))
        self.assertEqual(mbn.gate_net, "IBN")
        self.assertEqual(mbn.top_net, "IBN")  # diode-connected: D == G
        self.assertEqual(mbn.bottom_net, "VSS")

    def test_mcn_matches_schematic(self):
        mcn = BiasDeviceTableTests._by_name(cp_array.BIAS_DEVICES_N, "MCN")
        self.assertEqual(mcn.kind, "nfet")
        self.assertEqual((mcn.w_um, mcn.l_um), (4.0, 1.0))
        self.assertEqual(mcn.gate_net, "ICN")
        self.assertEqual(mcn.top_net, "ICN")
        self.assertEqual(mcn.bottom_net, "VSS")

    def test_mbp_matches_schematic(self):
        mbp = BiasDeviceTableTests._by_name(cp_array.BIAS_DEVICES_P, "MBP")
        self.assertEqual(mbp.kind, "pfet")
        self.assertEqual((mbp.w_um, mbp.l_um), (48.0, 1.0))
        self.assertEqual(mbp.gate_net, "IBP")
        self.assertEqual(mbp.top_net, "IBP")
        self.assertEqual(mbp.bottom_net, "VDD")

    def test_mcp_matches_schematic(self):
        mcp = BiasDeviceTableTests._by_name(cp_array.BIAS_DEVICES_P, "MCP")
        self.assertEqual(mcp.kind, "pfet")
        self.assertEqual((mcp.w_um, mcp.l_um), (12.0, 1.0))
        self.assertEqual(mcp.gate_net, "ICP")
        self.assertEqual(mcp.top_net, "ICP")
        self.assertEqual(mcp.bottom_net, "VDD")

    @staticmethod
    def _by_name(devices, name):
        return next(d for d in devices if d.name == name)


class NetMapTests(unittest.TestCase):
    """N_NET_MAP/P_NET_MAP -- design/cp.sch's own per-instance lab_pin wiring,
    including the "always-on leg ties directly to VDD/VSS" acceptance
    criterion.
    """

    def test_n_base_ties_en_directly_to_vdd_and_enb_to_vss(self):
        self.assertEqual(cp_array.N_NET_MAP["base"]["EN"], "VDD")
        self.assertEqual(cp_array.N_NET_MAP["base"]["ENB"], "VSS")

    def test_p_base_ties_en_directly_to_vdd_and_enb_to_vss(self):
        self.assertEqual(cp_array.P_NET_MAP["base"]["EN"], "VDD")
        self.assertEqual(cp_array.P_NET_MAP["base"]["ENB"], "VSS")

    def test_no_trim_leg_uses_vdd_or_vss_on_en_enb(self):
        for leg in ("t0", "t1a", "t1b"):
            for net_map in (cp_array.N_NET_MAP, cp_array.P_NET_MAP):
                self.assertNotIn(net_map[leg]["EN"], ("VDD", "VSS"))
                self.assertNotIn(net_map[leg]["ENB"], ("VDD", "VSS"))

    def test_t0_uses_b0_b0b(self):
        for net_map in (cp_array.N_NET_MAP, cp_array.P_NET_MAP):
            self.assertEqual(net_map["t0"]["EN"], "B0")
            self.assertEqual(net_map["t0"]["ENB"], "B0B")

    def test_t1a_t1b_share_b1_b1b(self):
        for net_map in (cp_array.N_NET_MAP, cp_array.P_NET_MAP):
            self.assertEqual(net_map["t1a"]["EN"], net_map["t1b"]["EN"])
            self.assertEqual(net_map["t1a"]["ENB"], net_map["t1b"]["ENB"])
            self.assertEqual(net_map["t1a"]["EN"], "B1")
            self.assertEqual(net_map["t1a"]["ENB"], "B1B")

    def test_every_leg_shares_the_bias_and_tail_nets(self):
        for name in ("base", "t0", "t1a", "t1b"):
            self.assertEqual(cp_array.N_NET_MAP[name]["VBN"], "IBN")
            self.assertEqual(cp_array.N_NET_MAP[name]["VCASCN"], "ICN")
            self.assertEqual(cp_array.N_NET_MAP[name]["TAIL"], "DNT")
            self.assertEqual(cp_array.P_NET_MAP[name]["VBP"], "IBP")
            self.assertEqual(cp_array.P_NET_MAP[name]["VCASCP"], "ICP")
            self.assertEqual(cp_array.P_NET_MAP[name]["TAIL"], "UPT")


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTests(unittest.TestCase):
    """cp_array.build() on the real leg/bias-device geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cp_array.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_xn_base_at_n_array_centroid(self):
        centers = self.layout.n_leg_centers
        cp_array.check_common_centroid(centers["base"], [centers["t0"], centers["t1a"], centers["t1b"]])

    def test_xp_base_at_p_array_centroid(self):
        centers = self.layout.p_leg_centers
        cp_array.check_common_centroid(centers["base"], [centers["t0"], centers["t1a"], centers["t1b"]])

    def test_n_and_p_sides_do_not_overlap(self):
        self.assertFalse(cp_array.boxes_overlap(self.layout.n_side_bbox, self.layout.p_side_bbox))

    def test_n_legs_do_not_overlap_each_other(self):
        boxes = self.layout.n_leg_boxes
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                self.assertFalse(cp_array.boxes_overlap(boxes[a], boxes[b]), f"{a}/{b} overlap")

    def test_p_legs_do_not_overlap_each_other(self):
        boxes = self.layout.p_leg_boxes
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                self.assertFalse(cp_array.boxes_overlap(boxes[a], boxes[b]), f"{a}/{b} overlap")

    def test_n_bias_branch_is_adjacent_not_inside_any_n_leg(self):
        for port in self.layout.n_bias_ports.values():
            box = (port.x0, port.y0, port.x1, port.y3)
            for leg_box in self.layout.n_leg_boxes.values():
                self.assertFalse(cp_array.boxes_overlap(box, leg_box))

    def test_p_bias_branch_is_adjacent_not_inside_any_p_leg(self):
        for port in self.layout.p_bias_ports.values():
            box = (port.x0, port.y0, port.x1, port.y3)
            for leg_box in self.layout.p_leg_boxes.values():
                self.assertFalse(cp_array.boxes_overlap(box, leg_box))

    def test_n_bias_devices_are_correctly_sized(self):
        mbn, mcn = self.layout.n_bias_ports["MBN"], self.layout.n_bias_ports["MCN"]
        self.assertAlmostEqual(mbn.x1 - mbn.x0, 16.0)
        self.assertAlmostEqual(mcn.x1 - mcn.x0, 4.0)

    def test_p_bias_devices_are_correctly_sized(self):
        mbp, mcp = self.layout.p_bias_ports["MBP"], self.layout.p_bias_ports["MCP"]
        self.assertAlmostEqual(mbp.x1 - mbp.x0, 48.0)
        self.assertAlmostEqual(mcp.x1 - mcp.x0, 12.0)

    def test_expected_pins_present(self):
        expected = {
            "IBN", "ICN", "DNT", "B0", "B0B", "B1", "B1B", "VSS",
            "IBP", "ICP", "UPT", "VDD",
        }
        self.assertEqual(set(self.layout.pins), expected)

    def test_trim_nets_promoted_once_per_polarity(self):
        # canvas.pin() is called once per net per side (a single
        # representative landing point -- the physical mesh behind it may
        # carry more than one pad, e.g. B1/B1B's own two legs -- see
        # _route_side()'s own docstring); B0/B0B (xn_t0/xp_t0 only) and
        # B1/B1B (xn_t1a+xn_t1b / xp_t1a+xp_t1b) are each disconnected
        # between the two polarities, so each has exactly one N-side and one
        # P-side entry (2 total), same as VDD/VSS (each also present on both
        # sides -- the rail net on one side, xn_base's/xp_base's own
        # direct EN/ENB tie on the other).
        for net in ("B0", "B0B", "B1", "B1B", "VDD", "VSS"):
            self.assertEqual(len(self.layout.pins[net]), 2, f"{net}: {self.layout.pins[net]}")

    def test_polarity_exclusive_nets_promoted_once(self):
        # IBN/ICN/DNT exist only on the N side; IBP/ICP/UPT only on P.
        for net in ("IBN", "ICN", "DNT", "IBP", "ICP", "UPT"):
            self.assertEqual(len(self.layout.pins[net]), 1, f"{net}: {self.layout.pins[net]}")

    def test_each_side_reports_a_metal2_bus_span_per_routed_net(self):
        # n_bus/p_bus are the handle a parent block reaches this block's nets
        # through -- see cp_output_stage.py's "REACHING THIS BLOCK'S NETS".
        expected_n = {"IBN", "ICN", "DNT", "B0", "B0B", "B1", "B1B", "VSS", "VDD"}
        expected_p = {"IBP", "ICP", "UPT", "B0", "B0B", "B1", "B1B", "VDD", "VSS"}
        self.assertEqual(set(self.layout.n_bus), expected_n)
        self.assertEqual(set(self.layout.p_bus), expected_p)

    def test_bus_spans_are_well_formed_and_sit_in_their_own_side_channel(self):
        for bus, side_bbox in (
            (self.layout.n_bus, self.layout.n_side_bbox),
            (self.layout.p_bus, self.layout.p_side_bbox),
        ):
            for net, (track_y, x_lo, x_hi) in bus.items():
                self.assertLessEqual(x_lo, x_hi, net)
                self.assertGreaterEqual(track_y, side_bbox[3], f"{net} track is not above the block")

    def test_each_side_assigns_every_net_its_own_track(self):
        for bus in (self.layout.n_bus, self.layout.p_bus):
            track_ys = [ty for ty, _lo, _hi in bus.values()]
            self.assertEqual(len(set(track_ys)), len(track_ys), "two nets share a Metal2 track")

    def test_net_pads_cover_every_leg_and_bias_pad(self):
        # n_net_pads/p_net_pads (issue #359) are what probe_pads() -- and
        # therefore ConnectivityTests below -- are built from; every net
        # that got a Metal2 bus must have at least one recorded pad.
        for bus, net_pads in (
            (self.layout.n_bus, self.layout.n_net_pads),
            (self.layout.p_bus, self.layout.p_net_pads),
        ):
            for net in bus:
                self.assertGreater(len(net_pads.get(net, [])), 0, net)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class ConnectivityTests(unittest.TestCase):
    """The finished GDS's own extracted Metal1-3 connectivity -- the only
    check that can see a short or an open (``layout/run_pv.py drc`` cannot;
    see ``netcheck.py``'s own docstring, and issue #359)."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cp_array.build()
        cls._tmp = tempfile.TemporaryDirectory()
        gds = Path(cls._tmp.name) / f"{cp_array.TOP_CELL}.gds"
        cls.layout.write_gds(gds)
        # probe_pads() -- unlike layout.pins -- hands every pad of every net
        # on each side, "N:"/"P:"-prefixed so the two polarities' own
        # deliberately-unlinked same-named nets (B0/B0B/B1/B1B/VDD/VSS; see
        # module docstring) are never conflated into one probed key.
        cls.report = netcheck.check_gds(
            gds, cp_array.TOP_CELL, netcheck.pad_probe_points(cls.layout.probe_pads())
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_connectivity_is_fully_clean(self):
        # The regression test for issue #359 itself: cp_array's own
        # standalone GDS used to extract with shorts=B0+B0B;
        # B1+B1B+VDD+VSS. Probing every pad on each side (not just one
        # representative per net) additionally proves no net is open.
        self.assertTrue(self.report.ok, self.report.summary())

    def test_no_probe_point_is_unresolved(self):
        self.assertEqual(self.report.unresolved, (), "stale probe coordinates")

    def test_no_net_is_split(self):
        self.assertEqual(self.report.splits, ())

    def test_no_shorts(self):
        self.assertEqual(self.report.shorts, ())

    def test_n_and_p_trim_nets_are_genuinely_unlinked_at_this_level(self):
        # Not a regression to guard against -- the module docstring's own
        # stated design (Part 3c/#321 links them) -- but worth pinning: the
        # fix for issue #359 must not accidentally tie the two polarities
        # together at this level either.
        for net in ("B0", "B0B", "B1", "B1B"):
            n_ids = self.report.components[f"N:{net}"]
            p_ids = self.report.components[f"P:{net}"]
            self.assertEqual(n_ids & p_ids, set())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class LegPadsTests(unittest.TestCase):
    """_leg_pads() -- the per-leg EN/ENB gate-tab riser escape (issue #359)."""

    @classmethod
    def setUpClass(cls):
        from pfd_cp import cp_leg_n

        cls.ln = cp_leg_n.build()

    def test_non_t1b_legs_only_move_the_mdis_pin(self):
        import pfd_cp.devgen as devgen
        from pfd_cp import cp_leg_n

        canvas = devgen.Canvas("scratch")
        for name in ("base", "t0", "t1a"):
            pads = cp_array._leg_pads(canvas, self.ln.pins, cp_leg_n.SPEC, name, 5.0, 7.0)
            men_net = cp_leg_n.SPEC.men_gate_net
            mdis_net = cp_leg_n.SPEC.mdis_gate_net
            # men_gate_net is a plain translate -- unchanged natural X.
            self.assertEqual(
                cp_array.pad_center(pads[men_net])[0],
                cp_array.pad_center(cp_array._translate_box(self.ln.pins[men_net], 5.0, 7.0))[0],
            )
            # mdis_gate_net moved left of its own translated natural X.
            natural_x = cp_array.pad_center(cp_array._translate_box(self.ln.pins[mdis_net], 5.0, 7.0))[0]
            self.assertLess(cp_array.pad_center(pads[mdis_net])[0], natural_x)

    def test_t1b_moves_both_gate_tab_pins_left_and_keeps_them_apart(self):
        import pfd_cp.devgen as devgen
        from pfd_cp import cp_leg_n

        canvas = devgen.Canvas("scratch")
        t0_dx = -20.0  # an arbitrary t0 dx well clear of t1b's own natural X
        targets = cp_array._t1b_escape_targets(t0_dx, self.ln.pins, cp_leg_n.SPEC)
        pads = cp_array._leg_pads(canvas, self.ln.pins, cp_leg_n.SPEC, "t1b", 0.0, 7.6, targets)
        men_x = cp_array.pad_center(pads[cp_leg_n.SPEC.men_gate_net])[0]
        mdis_x = cp_array.pad_center(pads[cp_leg_n.SPEC.mdis_gate_net])[0]
        natural_x = cp_array.pad_center(
            cp_array._translate_box(self.ln.pins[cp_leg_n.SPEC.men_gate_net], 0.0, 7.6)
        )[0]
        self.assertLess(men_x, natural_x)
        self.assertLess(mdis_x, natural_x)
        self.assertGreaterEqual(abs(men_x - mdis_x), cp_array.RISER_MIN_PITCH_UM - 1e-9)

    def test_t1b_without_targets_raises(self):
        import pfd_cp.devgen as devgen
        from pfd_cp import cp_leg_n

        canvas = devgen.Canvas("scratch")
        with self.assertRaises(AssertionError):
            cp_array._leg_pads(canvas, self.ln.pins, cp_leg_n.SPEC, "t1b", 0.0, 7.6)

    def test_every_other_pin_is_a_plain_translate(self):
        import pfd_cp.devgen as devgen
        from pfd_cp import cp_leg_n

        canvas = devgen.Canvas("scratch")
        pads = cp_array._leg_pads(canvas, self.ln.pins, cp_leg_n.SPEC, "base", 3.0, -2.0)
        moved = {cp_leg_n.SPEC.mdis_gate_net}
        for net, pad in self.ln.pins.items():
            if net in moved:
                continue
            self.assertEqual(pads[net], cp_array._translate_box(pad, 3.0, -2.0), net)


class T1bEscapeTargetsTests(unittest.TestCase):
    """_t1b_escape_targets() -- t1b's own two explicit riser columns, both
    past t0's own already-escaped mdis_gate_net column (issue #359)."""

    def setUp(self):
        from pfd_cp import cp_leg_n

        self.pins = cp_leg_n.build().pins if _HAVE_KLAYOUT else None
        self.spec = cp_leg_n.SPEC

    @unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
    def test_both_targets_clear_t0s_own_escaped_column(self):
        t0_dx = -11.77
        men_x, mdis_x = cp_array._t1b_escape_targets(t0_dx, self.pins, self.spec)
        t0_mdis_natural_x = t0_dx + cp_array.pad_center(self.pins[self.spec.mdis_gate_net])[0]
        t0_mdis_escaped_x = t0_mdis_natural_x - cp_array.MDIS_LEFT_ESCAPE_UM
        self.assertLessEqual(men_x, t0_mdis_escaped_x - cp_array.T1B_CLEAR_PITCH_UM + 1e-9)
        self.assertLess(mdis_x, men_x)

    @unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
    def test_the_two_targets_are_pitch_separated(self):
        men_x, mdis_x = cp_array._t1b_escape_targets(-11.77, self.pins, self.spec)
        self.assertAlmostEqual(men_x - mdis_x, cp_array.T1B_CLEAR_PITCH_UM)

    @unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
    def test_result_shifts_with_t0s_own_dx(self):
        men_a, mdis_a = cp_array._t1b_escape_targets(-11.77, self.pins, self.spec)
        men_b, mdis_b = cp_array._t1b_escape_targets(-20.0, self.pins, self.spec)
        self.assertAlmostEqual(men_b - men_a, -20.0 - (-11.77))
        self.assertAlmostEqual(mdis_b - mdis_a, -20.0 - (-11.77))


if __name__ == "__main__":
    unittest.main()
