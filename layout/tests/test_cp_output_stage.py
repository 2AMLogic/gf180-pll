#!/usr/bin/env python3
"""Tests for ``cp_output_stage`` -- the assembled charge-pump output stage:
Part 3b's N/P arrays plus the glue inverters and steering/dump switches
(issue #321, Part 3c of #294, the last of #301's three decomposition steps).

Same convention as ``test_cp_array.py``/``test_cp_leg_devgen.py``: the
``klayout.db``-dependent tests are skipped, not failed, when ``klayout.db``
is unavailable, so a PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the DRC-clean claim (which additionally needs the PDK's own signoff
deck) see ``layout/evidence/cp-layout/PROOF.md``. What this file checks is
(a) the device/instance tables really do match ``design/cp.sch``, (b) the
hand-placed riser-column scheme this module's correctness depends on holds
arithmetically, and (c) -- where ``klayout.db`` is importable -- the
finished GDS's own extracted Metal1-3 connectivity, which is the only thing
that can see a short or an open (a DRC deck cannot; see ``netcheck.py``).
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

from pfd_cp import cp_output_stage as cos  # noqa: E402
from pfd_cp import cp_array, devgen, netcheck  # noqa: E402


def _by_name(devices, name):
    return next(d for d in devices if d.name == name)


class SwitchDeviceTableTests(unittest.TestCase):
    """SWITCH_DEVICES_N/SWITCH_DEVICES_P match design/cp.sch's own MSWDN/
    MDMPDN/MDUMN/MSWUP/MDMPUP/MDUMP instances -- sizes and all four terminal
    nets (the schematic's D/G/S/B lab_pin labels)."""

    def test_mswdn_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_N, "MSWDN")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("nfet", 6.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("DN", "VOUT", "DNT"))

    def test_mdmpdn_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_N, "MDMPDN")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("nfet", 6.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("DNB", "VDUMP", "DNT"))

    def test_mdumn_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_N, "MDUMN")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("nfet", 3.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("DNB", "VOUT", "VOUT"))

    def test_mswup_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_P, "MSWUP")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("pfet", 6.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("UPB", "UPT", "VOUT"))

    def test_mdmpup_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_P, "MDMPUP")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("pfet", 6.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("UP", "UPT", "VDUMP"))

    def test_mdump_matches_schematic(self):
        d = _by_name(cos.SWITCH_DEVICES_P, "MDUMP")
        self.assertEqual((d.kind, d.w_um, d.l_um), ("pfet", 3.0, 0.3))
        self.assertEqual((d.gate_net, d.top_net, d.bottom_net), ("UP", "VOUT", "VOUT"))

    def test_steering_switches_are_equal_width_not_mobility_scaled(self):
        # design/cp.sch's own "Switch sizing" note: equal widths, not equal
        # strengths -- a mobility-ratio-scaled P device injected a net charge
        # residue at every switching event.
        widths = {d.name: d.w_um for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P)}
        self.assertEqual(widths["MSWDN"], widths["MSWUP"])
        self.assertEqual(widths["MDMPDN"], widths["MDMPUP"])

    def test_dummies_are_half_width_with_both_diffusions_on_vout(self):
        for name, table in (("MDUMN", cos.SWITCH_DEVICES_N), ("MDUMP", cos.SWITCH_DEVICES_P)):
            d = _by_name(table, name)
            self.assertEqual(d.w_um, cos.SWITCH_W_UM / 2.0)
            self.assertEqual(d.top_net, "VOUT")
            self.assertEqual(d.bottom_net, "VOUT")


class GlueInverterTableTests(unittest.TestCase):
    """GLUE_INVERTERS match design/cp.sch's own xi_b0/xi_b1/xi_up/xi_dn."""

    def test_all_four_instances_present(self):
        self.assertEqual(
            [s.name for s in cos.GLUE_INVERTERS], ["xi_b0", "xi_b1", "xi_up", "xi_dn"]
        )

    def test_each_inverter_maps_its_input_to_the_matching_bar_net(self):
        for spec in cos.GLUE_INVERTERS:
            self.assertEqual(spec.y_net, spec.a_net + "B", f"{spec.name}: {spec}")

    def test_trim_and_steering_inputs_are_covered(self):
        self.assertEqual({s.a_net for s in cos.GLUE_INVERTERS}, {"B0", "B1", "UP", "DN"})


class NetNamingTests(unittest.TestCase):
    """The block's boundary/internal net split, per design/cp.sch's own
    ipin/iopin declarations plus VDUMP (a real boundary net here only because
    cp_dumpbuf is out of scope -- issue #302/#303)."""

    def test_boundary_pins_are_the_twelve_expected(self):
        self.assertEqual(
            set(cos.BOUNDARY_PINS),
            {"UP", "DN", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "VDD", "VSS", "VDUMP"},
        )

    def test_boundary_and_internal_nets_are_disjoint(self):
        self.assertEqual(set(cos.BOUNDARY_PINS) & set(cos.INTERNAL_NETS), set())

    def test_every_device_terminal_net_is_declared(self):
        declared = set(cos.BOUNDARY_PINS) | set(cos.INTERNAL_NETS)
        for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P):
            for net in (d.gate_net, d.top_net, d.bottom_net):
                self.assertIn(net, declared, f"{d.name} terminal net {net!r} is undeclared")
        for spec in cos.GLUE_INVERTERS:
            self.assertIn(spec.a_net, declared)
            self.assertIn(spec.y_net, declared)

    def test_vdump_is_a_stub_reached_only_by_the_two_dump_switches(self):
        drivers = [
            d.name
            for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P)
            if "VDUMP" in (d.gate_net, d.top_net, d.bottom_net)
        ]
        self.assertEqual(sorted(drivers), ["MDMPDN", "MDMPUP"])


class SwitchRowTests(unittest.TestCase):
    """row_x() -- the single-row placement the riser-column scheme depends on
    (see cp_output_stage.py's own docstring). Since issue #473 the row holds
    the four glue inverters as well as the six switches, interleaved."""

    def setUp(self):
        self.row, self.inv = cos.row_x()
        self.order = list(cos.ROW_ORDER)

    def test_every_switch_and_inverter_is_placed_exactly_once(self):
        self.assertEqual(
            sorted([*self.row, *self.inv]),
            sorted([d.name for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P)]
                   + [s.name for s in cos.GLUE_INVERTERS]),
        )

    def test_row_items_are_monotonic_left_to_right_and_never_overlap(self):
        prev_x1 = None
        for name in self.order:
            x0, x1 = self.row[name] if name in self.row else (self.inv[name], self.inv[name])
            self.assertGreaterEqual(x1, x0)
            if prev_x1 is not None:
                self.assertGreaterEqual(x0, prev_x1)
            prev_x1 = x1

    def test_device_widths_match_the_schematic_table(self):
        for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P):
            x0, x1 = self.row[d.name]
            self.assertAlmostEqual(x1 - x0, d.w_um)

    def test_the_two_switch_groups_are_contiguous_and_well_separated(self):
        # Contiguity is what lets each group carry ONE tap strip and the P
        # group ONE n-well (check_row_groups()); the gap between the two
        # groups is the well-boundary clearance.
        cos.check_row_groups()  # must not raise
        n_x1 = max(self.row[d.name][1] for d in cos.SWITCH_DEVICES_N)
        p_x0 = min(self.row[d.name][0] for d in cos.SWITCH_DEVICES_P)
        first_p_in_row = next(n for n in self.order if n in {d.name for d in cos.SWITCH_DEVICES_P})
        prev = self.order[self.order.index(first_p_in_row) - 1]
        if prev in self.row:
            self.assertAlmostEqual(p_x0 - self.row[prev][1], cos.SWITCH_WELL_GAP_UM)
        else:
            self.assertGreater(p_x0, n_x1)

    def test_a_glue_inverter_inside_a_switch_group_is_rejected(self):
        bad = ("MSWDN", "xi_dn", "MDMPDN", "MDUMN", "xi_up", "MSWUP", "MDMPUP",
               "MDUMP", "xi_b0", "xi_b1")
        with self.assertRaises(ValueError) as ctx:
            cos.check_row_groups(bad)
        self.assertIn("not contiguous", str(ctx.exception))

    def test_a_row_order_that_drops_or_duplicates_an_item_is_rejected(self):
        with self.assertRaises(ValueError):
            cos.check_row_groups(cos.ROW_ORDER[:-1])
        with self.assertRaises(ValueError):
            cos.check_row_groups((*cos.ROW_ORDER[:-1], cos.ROW_ORDER[-2]))

    def test_each_steering_inverter_is_adjacent_to_the_group_it_drives(self):
        # The whole point of issue #473: xi_dn immediately before the N
        # group, xi_up immediately before the P group.
        self.assertEqual(self.order[self.order.index("xi_dn") + 1],
                         cos.SWITCH_DEVICES_N[0].name)
        self.assertEqual(self.order[self.order.index("xi_up") + 1],
                         cos.SWITCH_DEVICES_P[0].name)

    def test_escape_landings_clear_the_next_row_item_gate_pad(self):
        worst = cos.check_escape_clearance(
            cos.row_metal1_extents(self.row, self.inv), self.order
        )  # must not raise
        self.assertGreater(worst, 0.0)

    def test_escape_clearance_raises_when_the_row_is_packed_too_tightly(self):
        row, inv = cos.row_x(
            device_gap_um=0.5, well_gap_um=0.5, inv_gap_um=0.5,
            inv_to_switch_gap_um=0.5, inv_pitch_um=0.5,
        )
        with self.assertRaises(ValueError):
            cos.check_escape_clearance(cos.row_metal1_extents(row, inv), cos.ROW_ORDER)

    def test_an_inverter_reaches_further_right_of_its_origin_than_a_switch(self):
        # Why INV_TO_SWITCH_GAP_UM is bigger than INV_GROUP_GAP_UM: an
        # inverter's escape columns all run rightward from its origin.
        extents = cos.row_metal1_extents(self.row, self.inv)
        self.assertAlmostEqual(
            extents["xi_dn"][1] - self.inv["xi_dn"],
            max(cos.INV_ESCAPE_UM) + cos.LANDING_HALF_UM,
        )
        self.assertGreater(cos.INV_TO_SWITCH_GAP_UM, cos.INV_GROUP_GAP_UM)

    def test_gate_pad_center_is_derived_from_devgen_constants(self):
        # Re-derived independently here, so a devgen geometry change that
        # invalidates the escape arithmetic fails loudly rather than silently.
        expected = 0.0 - devgen.POLY_ENDCAP_UM + devgen.GATE_TAB_OVERLAP_UM - devgen.GATE_TAB_W_UM / 2.0
        self.assertAlmostEqual(cos.gate_pad_center_x(0.0), expected)
        self.assertLess(cos.gate_pad_center_x(0.0), 0.0, "the gate tab hangs to the LEFT of the comp")


class RiserColumnTests(unittest.TestCase):
    """check_riser_columns() -- the invariant that replaces cp_array's own
    nudge-based declutterer here (see cp_output_stage.py's docstring)."""

    def test_well_separated_distinct_nets_pass(self):
        cos.check_riser_columns([("A", 0.0, 0.0), ("B", 1.5, 3.0), ("C", 3.0, -2.0)])

    def test_same_net_may_share_a_column(self):
        # MDUMN/MDUMP's two VOUT diffusions land on one X by construction.
        cos.check_riser_columns([("VOUT", 0.0, 0.2), ("VOUT", 0.0, 1.1), ("DNB", 1.5, 0.6)])

    def test_two_different_nets_on_one_column_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cos.check_riser_columns([("EN", 0.0, 2.5), ("ENB", 0.0, 0.6)])
        self.assertIn("more than one net", str(ctx.exception))

    def test_columns_closer_than_the_pitch_are_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cos.check_riser_columns([("A", 0.0, 0.0), ("B", 0.4, 0.0)])
        self.assertIn("apart", str(ctx.exception))

    def test_the_real_switch_row_and_inverter_columns_need_no_declutter(self):
        # The same arithmetic build() runs, re-derived here from the module's
        # own placement functions rather than from a built layout, so it also
        # covers a no-klayout checkout.
        row, inv = cos.row_x()
        points: list[tuple[str, float, float]] = []
        for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P):
            x0, x1 = row[d.name]
            points.append((d.gate_net, cos.gate_pad_center_x(x0), 0.65))
            points.append((d.top_net, (x0 + x1) / 2.0, 1.09))
            if d.bottom_net == d.top_net:
                points.append((d.bottom_net, (x0 + x1) / 2.0, 0.21))
            else:
                points.append((d.bottom_net, x1 + cos.SWITCH_ESCAPE_UM, 0.21))
        for spec in cos.GLUE_INVERTERS:
            ix = inv[spec.name]
            points.append((spec.a_net, cos.gate_pad_center_x(ix), 0.65))
            y_esc, vss_esc, vdd_esc = (ix + o for o in cos.INV_ESCAPE_UM)
            points.append((spec.y_net, y_esc, 1.09))
            points.append(("VSS", vss_esc, 0.21))
            points.append(("VDD", vdd_esc, 6.39))
        cos.check_riser_columns(points)  # must not raise


class LinkColumnTests(unittest.TestCase):
    def test_columns_march_away_from_the_block(self):
        left = cos.link_columns(["A", "B", "C"], base_x=-2.0, direction=-1, pitch=1.0)
        self.assertEqual(left, {"A": -2.0, "B": -3.0, "C": -4.0})
        right = cos.link_columns(["A", "B"], base_x=5.0, direction=+1, pitch=1.0)
        self.assertEqual(right, {"A": 5.0, "B": 6.0})

    def test_columns_are_unique_per_net(self):
        cols = cos.link_columns(["A", "B", "C", "D"], base_x=0.0, direction=-1)
        self.assertEqual(len(set(cols.values())), 4)


class GlueBusReachTests(unittest.TestCase):
    """glue_bus_reach() -- the declaration cp_array._route_side()'s packing
    rests on (issue #469). An x this block extends a glue bus to and does not
    declare is a cross-net Metal2 merge no DRC deck can report.
    """

    def test_every_glue_net_appears_even_with_no_reach(self):
        reach = cos.glue_bus_reach(["A", "B", "C"], {"A": -1.0}, {})
        self.assertEqual(sorted(reach), ["A", "B", "C"])
        self.assertEqual(reach["B"], [])

    def test_a_net_shared_on_both_sides_declares_both_columns(self):
        reach = cos.glue_bus_reach(["VDD", "DNT"], {"VDD": -20.0, "DNT": -21.0}, {"VDD": 95.0})
        self.assertEqual(reach["VDD"], [-20.0, 95.0])
        self.assertEqual(reach["DNT"], [-21.0])


class InheritedShortsConstantTests(unittest.TestCase):
    """INHERITED_ARRAY_SHORTS: cp_array's own former B0/B0B and
    B1/B1B/VDD/VSS shorts are fixed (issue #359); this constant is asserted
    empty so a regression here fails loudly rather than silently."""

    def test_the_inherited_defect_is_fixed(self):
        self.assertEqual(cos.INHERITED_ARRAY_SHORTS, ())


class NetcheckReportTests(unittest.TestCase):
    """netcheck's own plain-Python surface (no klayout needed)."""

    def test_clean_report_is_ok(self):
        r = netcheck.ConnectivityReport(components={"A": frozenset({"$1"})})
        self.assertTrue(r.ok)
        self.assertIn("connectivity clean", r.summary())

    def test_a_short_makes_the_report_fail(self):
        r = netcheck.ConnectivityReport(
            components={"A": frozenset({"$1"}), "B": frozenset({"$1"})},
            shorts=(frozenset({"A", "B"}),),
        )
        self.assertFalse(r.ok)
        self.assertIn("A+B", r.summary())

    def test_a_split_makes_the_report_fail(self):
        r = netcheck.ConnectivityReport(components={"A": frozenset({"$1", "$2"})}, splits=("A",))
        self.assertFalse(r.ok)
        self.assertIn("splits", r.summary())

    def test_pad_probe_points_takes_box_centres(self):
        pts = netcheck.pad_probe_points({"A": [(0.0, 0.0, 2.0, 1.0), (4.0, 4.0, 6.0, 6.0)]})
        self.assertEqual(pts, {"A": [(1.0, 0.5), (5.0, 5.0)]})

    def test_probe_layer_is_metal1(self):
        self.assertEqual(netcheck.PROBE_LAYER, "metal1")
        self.assertIn("metal1", netcheck.METAL_LAYERS)
        self.assertNotIn("comp", netcheck.METAL_LAYERS)  # see netcheck.py's docstring


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTests(unittest.TestCase):
    """cp_output_stage.build() on the real array/leaf-cell geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cos.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_encloses_both_the_array_and_the_glue_block(self):
        fx0, fy0, fx1, fy1 = self.layout.footprint
        for box in (self.layout.array.footprint, self.layout.glue_bbox):
            self.assertLessEqual(fx0, box[0])
            self.assertLessEqual(fy0, box[1])
            self.assertGreaterEqual(fx1, box[2])
            self.assertGreaterEqual(fy1, box[3])

    def test_glue_block_sits_clear_above_the_array_and_its_routing_channel(self):
        self.assertGreaterEqual(
            self.layout.glue_bbox[1] - self.layout.array.footprint[3], cos.GLUE_GAP_UM - 1e-9
        )

    def test_boundary_pin_set_is_exactly_the_twelve_declared(self):
        self.assertEqual(set(self.layout.pins), set(cos.BOUNDARY_PINS))

    def test_no_internal_net_is_promoted_as_a_pin(self):
        for net in cos.INTERNAL_NETS:
            self.assertNotIn(net, self.layout.pins)

    def test_every_boundary_pin_has_exactly_one_landing_pad(self):
        for net in cos.BOUNDARY_PINS:
            self.assertEqual(len(self.layout.pins[net]), 1, f"{net}: {self.layout.pins[net]}")

    def test_all_six_switches_are_drawn_at_their_schematic_widths(self):
        self.assertEqual(
            sorted(self.layout.switch_ports),
            sorted(d.name for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P)),
        )
        for d in (*cos.SWITCH_DEVICES_N, *cos.SWITCH_DEVICES_P):
            p = self.layout.switch_ports[d.name]
            self.assertAlmostEqual(p.x1 - p.x0, d.w_um, msg=d.name)
            self.assertAlmostEqual(p.y3 - p.y0, 2 * devgen.SD_OVERHANG_UM + d.l_um, msg=d.name)

    def test_all_four_glue_inverters_share_the_switches_own_row(self):
        origins = [self.layout.inverter_origins[s.name] for s in cos.GLUE_INVERTERS]
        self.assertEqual(len({y for _x, y in origins}), 1, "inverters must share one row")
        row_y = origins[0][1]
        for p in self.layout.switch_ports.values():
            self.assertAlmostEqual(p.y0, row_y)

    def test_the_built_row_matches_ROW_ORDER_left_to_right(self):
        # ROW_ORDER is the placement's single source of truth (issue #473);
        # this is the built geometry agreeing with it.
        anchors = {n: p.x0 for n, p in self.layout.switch_ports.items()}
        anchors.update({n: x for n, (x, _y) in self.layout.inverter_origins.items()})
        self.assertEqual(sorted(anchors, key=anchors.get), list(cos.ROW_ORDER))

    def test_each_steering_inverter_sits_beside_the_gates_it_drives(self):
        # The measured property issue #473 bought: every one of DN/DNB/UP/UPB
        # is now a local net, not a block-wide one. Before the interleave they
        # spanned 34.0-82.0 um; the longest structural net that remains (VOUT,
        # which ties the N and P groups together by definition) is 56.5 um.
        for net in ("DN", "DNB", "UP", "UPB"):
            _y, x_lo, x_hi = self.layout.glue_bus[net]
            self.assertLess(x_hi - x_lo, 30.0, f"{net} spans {x_hi - x_lo:.2f} um")

    def test_riser_columns_of_the_built_block_need_no_declutter(self):
        cos.check_riser_columns(self.layout.riser_points)  # must not raise

    def test_the_arithmetic_riser_model_matches_what_build_actually_drew(self):
        """``glue_riser_x()`` is what costed every candidate row order before
        issue #473 moved anything (see its docstring). A model that has
        drifted from ``build()`` would have chosen ROW_ORDER on fiction, so
        the two are pinned together here rather than merely believed."""
        row, inv = cos.row_x(x0=self.layout.array.footprint[0] + cos.CONN_COLUMN_MARGIN_UM)
        predicted = {net: [round(x, 6) for x in xs]
                     for net, xs in cos.glue_riser_x(row, inv).items()}
        drawn: dict[str, list[float]] = {}
        for net, x, _y in self.layout.riser_points:
            drawn.setdefault(net, []).append(round(x, 6))
        self.assertEqual(predicted, {net: sorted(xs) for net, xs in drawn.items()})

    def test_no_legal_row_order_packs_the_glue_band_below_ten_tracks(self):
        """The exhaustive sweep behind :data:`cos.ROW_ORDER` (issue #473), as
        a test rather than as a claim in a markdown file: all 25,920 orderings
        that keep both switch groups contiguous, costed with the same
        ``pack_tracks()`` the router uses. Ten is the floor, and ROW_ORDER
        reaches it.

        The link columns are held at the built block's own x. That is exact
        for any of these orderings: each keeps the row inside ``cp_array``'s
        own footprint (asserted below), and the columns are placed relative
        to whichever of the array and the glue row reaches further.
        """
        import itertools  # noqa: PLC0415

        arr = self.layout.array
        x0 = arr.footprint[0] + cos.CONN_COLUMN_MARGIN_UM
        link: dict[str, list[float]] = {}
        for key, x in self.layout.link_columns.items():
            link.setdefault(key.split(":", 1)[1], []).append(x)

        n_names = [d.name for d in cos.SWITCH_DEVICES_N]
        p_names = [d.name for d in cos.SWITCH_DEVICES_P]
        blocks = ("N", "P", "xi_up", "xi_dn", "xi_b0", "xi_b1")
        counted = 0
        best = None
        for n_perm in itertools.permutations(n_names):
            for p_perm in itertools.permutations(p_names):
                for arrangement in itertools.permutations(blocks):
                    order: list[str] = []
                    for b in arrangement:
                        order += list(n_perm) if b == "N" else list(p_perm) if b == "P" else [b]
                    cos.check_row_groups(order)
                    row, inv = cos.row_x(order, x0=x0)
                    self.assertLess(
                        max(max(x1 for _x, x1 in row.values()),
                            max(inv.values()) + max(cos.INV_ESCAPE_UM)),
                        arr.footprint[2],
                        f"{order} pushes the row past the array's own right edge",
                    )
                    reach = cos.glue_riser_x(row, inv)
                    for net, xs in link.items():
                        reach[net].extend(xs)
                    n_tracks = len(set(cp_array.pack_tracks(reach, 0.0).values()))
                    best = n_tracks if best is None else min(best, n_tracks)
                    counted += 1
        self.assertEqual(counted, 25920)
        self.assertEqual(best, 10)
        self.assertEqual(
            len({span[0] for span in self.layout.glue_bus.values()}), best,
            "ROW_ORDER no longer reaches the floor its own sweep found",
        )

    def test_link_columns_exist_for_every_shared_net_and_are_all_distinct(self):
        arr = self.layout.array
        expected = {f"N:{n}" for n in arr.n_bus if n in self.layout.glue_bus}
        expected |= {f"P:{n}" for n in arr.p_bus if n in self.layout.glue_bus}
        self.assertEqual(set(self.layout.link_columns), expected)
        xs = sorted(self.layout.link_columns.values())
        for a, b in zip(xs, xs[1:]):
            self.assertGreaterEqual(b - a, cos.CONN_COLUMN_PITCH_UM - 1e-9)

    def test_the_trim_and_rail_nets_are_linked_on_both_polarities(self):
        for net in ("B0", "B0B", "B1", "B1B", "VDD", "VSS"):
            self.assertIn(f"N:{net}", self.layout.link_columns)
            self.assertIn(f"P:{net}", self.layout.link_columns)

    def test_the_tail_nets_are_linked_on_their_own_polarity_only(self):
        self.assertIn("N:DNT", self.layout.link_columns)
        self.assertNotIn("P:DNT", self.layout.link_columns)
        self.assertIn("P:UPT", self.layout.link_columns)
        self.assertNotIn("N:UPT", self.layout.link_columns)

    def test_link_columns_stay_clear_of_the_block_itself(self):
        left = min(self.layout.link_columns.values())
        right = max(self.layout.link_columns.values())
        block_x0 = min(self.layout.array.footprint[0], self.layout.glue_bbox[0])
        block_x1 = max(self.layout.array.footprint[2], self.layout.glue_bbox[2])
        self.assertLessEqual(left, block_x0 - cos.CONN_COLUMN_MARGIN_UM + 1e-9)
        self.assertGreaterEqual(right, block_x1 + cos.CONN_COLUMN_MARGIN_UM - 1e-9)

    # --- the packed glue band (issue #469) ---

    def test_the_glue_band_is_packed_not_one_track_per_net(self):
        """14 nets, 10 tracks -- the band's own clique number, which for an
        interval graph is the provable minimum. 14 would mean the packing
        silently reverted to ``NetTracks`` (issue #469); 13 would mean the
        row had drifted back to grouping its glue inverters at the right-hand
        end instead of interleaving them (issue #473)."""
        self.assertEqual(len(self.layout.glue_bus), 14)
        self.assertEqual(len({span[0] for span in self.layout.glue_bus.values()}), 10)

    def test_the_band_top_matches_the_number_of_packed_tracks(self):
        base_y = self.layout.glue_bbox[3] + cp_array.CHANNEL_MARGIN_UM
        n_tracks = len({span[0] for span in self.layout.glue_bus.values()})
        self.assertAlmostEqual(
            self.layout.footprint[3], base_y + n_tracks * cp_array.METAL2_TRACK_PITCH_UM
        )

    def test_every_net_sharing_a_track_is_kept_apart_in_x(self):
        """The property the whole packing rests on, re-checked here against
        the *drawn* buses and this block's own link-column extensions -- the
        same arithmetic ``build()`` asserts, so a future edit that packs
        without declaring an extension fails the suite too (issue #469)."""
        arr = self.layout.array
        extents = {}
        for net, (_ty, x_lo, x_hi) in self.layout.glue_bus.items():
            xs = [x_lo, x_hi]
            for side, bus in (("N", arr.n_bus), ("P", arr.p_bus)):
                if net in bus:
                    xs.append(self.layout.link_columns[f"{side}:{net}"])
            extents[net] = cp_array._net_x_extent(xs)
        cp_array.check_track_separation(
            {net: span[0] for net, span in self.layout.glue_bus.items()}, extents
        )  # must not raise

    def test_the_six_both_sided_nets_are_each_alone_on_their_track(self):
        """VDD/VSS/B0/B0B/B1/B1B are extended to a left column *and* a right
        one, so each is live across the whole block and can share with
        nothing. This is why the band's floor is 13 and not the 9 #455 sized
        from the bus spans alone -- see PROOF-469-glue-bus-packing.md."""
        by_y = {}
        for net, (ty, _lo, _hi) in self.layout.glue_bus.items():
            by_y.setdefault(round(ty, 6), []).append(net)
        for net in ("VDD", "VSS", "B0", "B0B", "B1", "B1B"):
            ty = round(self.layout.glue_bus[net][0], 6)
            self.assertEqual(by_y[ty], [net], f"{net} unexpectedly shares a track")


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class ConnectivityTests(unittest.TestCase):
    """The finished GDS's own extracted Metal1-3 connectivity -- the only
    check that can see a short or an open (``layout/run_pv.py drc`` cannot;
    see ``netcheck.py``'s own docstring)."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cos.build()
        cls._tmp = tempfile.TemporaryDirectory()
        gds = Path(cls._tmp.name) / f"{cos.TOP_CELL}.gds"
        cls.layout.write_gds(gds)
        cls.report = netcheck.check_gds(
            gds, cos.TOP_CELL, netcheck.pad_probe_points(cls.layout.probe_pads())
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_probe_point_lands_on_real_metal(self):
        self.assertEqual(self.report.unresolved, (), "stale probe coordinates")

    def test_no_net_is_open(self):
        # Includes the array<->glue link columns: DNT's three pads (the N
        # array's own TAIL pin plus MSWDN's and MDMPDN's sources) landing on
        # one component is what proves that link actually connected.
        self.assertEqual(self.report.splits, ())

    def test_no_shorts_at_all(self):
        # cp_array's own former B0/B0B and B1/B1B/VDD/VSS shorts (recorded,
        # while they existed, as INHERITED_ARRAY_SHORTS) are fixed by issue
        # #359 -- this block's connectivity is now fully clean, not merely
        # "clean except for a known defect".
        self.assertEqual(self.report.shorts, ())
        self.assertEqual(self.report.shorts, cos.INHERITED_ARRAY_SHORTS)

    def test_this_increments_own_wiring_is_short_free(self):
        shorted = {net for group in self.report.shorts for net in group}
        for net in ("UP", "UPB", "DN", "DNB", "VOUT", "VDUMP", "DNT", "UPT", "IBN", "ICN", "IBP", "ICP"):
            self.assertNotIn(net, shorted, f"{net} is shorted -- this block's own wiring is wrong")

    def test_the_trim_and_rail_nets_are_no_longer_shorted(self):
        # The exact nets INHERITED_ARRAY_SHORTS used to name.
        for net in ("B0", "B0B", "B1", "B1B", "VDD", "VSS"):
            self.assertNotIn(net, {n for group in self.report.shorts for n in group}, net)

    def test_vdump_is_a_distinct_net_of_its_own(self):
        self.assertEqual(len(self.report.components["VDUMP"]), 1)
        others = {
            net: ids for net, ids in self.report.components.items() if net != "VDUMP"
        }
        vdump = next(iter(self.report.components["VDUMP"]))
        for net, ids in others.items():
            self.assertNotIn(vdump, ids, f"VDUMP is not a stub -- it reaches {net}")


if __name__ == "__main__":
    unittest.main()
