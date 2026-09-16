#!/usr/bin/env python3
"""Tests for the ``cp_dumpbuf`` layout (issue #302, Part 4 of #294).

Like ``test_pfdcp_devgen.py``, the ``klayout.db``-dependent tests (anything
that calls ``cp_dumpbuf.build()``) are skipped, not failed, when
``klayout.db`` is unavailable, so a PDK/PV-less checkout still collects this
file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC-clean claim (which additionally needs the PDK's own
signoff deck), see ``layout/evidence/cp-dumpbuf-layout/PROOF.md`` -- this
file checks the geometry/connectivity ``cp_dumpbuf`` *claims* to build
(device table fidelity, common-centroid placement, well separation), not a
substitute for running the deck. CONNECTIVITY IS CHECKED, NOT ASSUMED --
same convention as ``test_cp_output_stage.py``'s own ``ConnectivityTests``
(issue #391): a DRC-clean geometry claim cannot see a short or an open (a
signoff deck has no concept of "which net" a shape belongs to -- see
``netcheck.py``'s own docstring), so ``ConnectivityTests`` below extracts
the finished GDS's own Metal1-3 connectivity and proves every net this
module claims to route is exactly one component, not merged with another.
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

from pfd_cp import cp_dumpbuf, netcheck  # noqa: E402


class DeviceTableTests(unittest.TestCase):
    """N_DEVICES/P_DEVICES match design/cp_dumpbuf.sch's own instances."""

    def test_device_counts(self):
        # MTP and each of MP1/MP2 are split into two fingers (see module
        # docstring) -- the PMOS-input OTA's 5 schematic devices (MTP, MP1,
        # MP2, MP3, MP4) become 8 drawn devices (MTPa/MTPb, MP1a/MP1b,
        # MP2a/MP2b, MP3, MP4); the NMOS-input OTA is drawn 1:1 (5 devices).
        self.assertEqual(len(cp_dumpbuf.N_DEVICES), 5)
        self.assertEqual(len(cp_dumpbuf.P_DEVICES), 8)

    def test_mp1_mp2_fingers_preserve_total_width(self):
        by_name = {d.name: d for d, _g in cp_dumpbuf.P_DEVICES}
        mp1_total = by_name["MP1a"].w_um + by_name["MP1b"].w_um
        mp2_total = by_name["MP2a"].w_um + by_name["MP2b"].w_um
        self.assertEqual(mp1_total, 48.0)  # design/cp_dumpbuf.sch's own MP1.W
        self.assertEqual(mp2_total, 48.0)  # design/cp_dumpbuf.sch's own MP2.W

    def test_mtp_fingers_preserve_total_width(self):
        by_name = {d.name: d for d, _g in cp_dumpbuf.P_DEVICES}
        mtp_total = by_name["MTPa"].w_um + by_name["MTPb"].w_um
        self.assertEqual(mtp_total, 48.0)  # design/cp_dumpbuf.sch's own MTP.W

    def test_mp1_mp2_bulk_is_their_own_common_source(self):
        # DR-005: "MP1/MP2 have their bulk tied to their common source PSRC
        # rather than VDD" -- this module ties the *body* via the isolated
        # well's own tap net (see build()), but every MP1/MP2 finger's own
        # bottom_net (source) must already be PSRC for that well tap to be
        # electrically correct.
        by_name = {d.name: d for d, _g in cp_dumpbuf.P_DEVICES}
        for name in cp_dumpbuf.MP12_NAMES:
            self.assertEqual(by_name[name].bottom_net, "PSRC")

    def test_mn1_mp1_share_vref_gate(self):
        n_by_name = {d.name: d for d, _g in cp_dumpbuf.N_DEVICES}
        p_by_name = {d.name: d for d, _g in cp_dumpbuf.P_DEVICES}
        self.assertEqual(n_by_name["MN1"].gate_net, "VREF")
        self.assertEqual(p_by_name["MP1a"].gate_net, "VREF")
        self.assertEqual(p_by_name["MP1b"].gate_net, "VREF")

    def test_unity_gain_feedback_devices_are_diode_connected_onto_vdump(self):
        # MN2/MP2's own gate == drain == VDUMP is what closes each OTA's
        # unity-gain loop onto the shared dump node (per the schematic's own
        # text annotation).
        n_by_name = {d.name: d for d, _g in cp_dumpbuf.N_DEVICES}
        p_by_name = {d.name: d for d, _g in cp_dumpbuf.P_DEVICES}
        self.assertEqual(n_by_name["MN2"].gate_net, n_by_name["MN2"].top_net)
        self.assertEqual(n_by_name["MN2"].gate_net, "VDUMP")
        for name in ("MP2a", "MP2b"):
            self.assertEqual(p_by_name[name].gate_net, p_by_name[name].top_net)
            self.assertEqual(p_by_name[name].gate_net, "VDUMP")

    def test_external_nets_match_schematic_pins(self):
        self.assertEqual(set(cp_dumpbuf.EXTERNAL_NETS), {"VREF", "VBN", "VBP", "VDUMP", "VDD", "VSS"})


class CheckCommonCentroidTests(unittest.TestCase):
    """check_common_centroid() -- the arithmetic MP1/MP2 placement proof."""

    def test_abba_pattern_passes(self):
        cp_dumpbuf.check_common_centroid(("A", "B", "B", "A"), [0.0, 10.0, 20.0, 30.0])  # centre=15, A=15, B=15

    def test_row_placed_pattern_raises(self):
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_common_centroid(("A", "A", "B", "B"), [0.0, 10.0, 20.0, 30.0])

    def test_off_center_leg_raises(self):
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_common_centroid(("A", "B", "B", "A"), [0.0, 10.0, 20.0, 31.0])

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_common_centroid(("A", "B"), [0.0, 10.0, 20.0])

    def test_this_module_s_own_mp12_pattern_is_interdigitated(self):
        cp_dumpbuf.check_common_centroid(cp_dumpbuf.MP12_PATTERN, [0.0, 24.0, 48.0, 72.0])


class CheckWellSeparationTests(unittest.TestCase):
    """well_separation_um()/check_well_separation() -- the isolated-well
    disjointness proof, including against a synthetic stand-in for Part 3's
    (#301) not-yet-landed CP-array wells (see this issue's own soft
    dependency note).
    """

    def test_separated_boxes_pass(self):
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (12.0, 0.0, 20.0, 10.0)  # 2.0 um gap
        gap = cp_dumpbuf.check_well_separation(box_a, box_b)
        self.assertAlmostEqual(gap, 2.0)

    def test_touching_boxes_raise(self):
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (10.0, 0.0, 20.0, 10.0)  # 0 um gap
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_well_separation(box_a, box_b)

    def test_diagonal_gap_is_euclidian(self):
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (13.0, 14.0, 20.0, 20.0)  # dx=3, dy=4 -> 5.0 um
        gap = cp_dumpbuf.well_separation_um(box_a, box_b)
        self.assertAlmostEqual(gap, 5.0)

    def test_below_minimum_gap_raises_with_the_pdk_rule_value(self):
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (11.0, 0.0, 20.0, 10.0)  # 1.0 um gap < 1.4 um NW.2b minimum
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_well_separation(box_a, box_b)

    def test_synthetic_cp_array_well_stand_in(self):
        # Part 3 (#301) has not landed as of this issue -- this stands in
        # for "a hypothetical adjacent CP-array well", per this issue's own
        # Dependencies note ("state the well-separation requirement
        # explicitly ... verify it once Part 3's geometry exists"), and
        # proves check_well_separation() actually rejects an
        # insufficiently-separated foreign well rather than only ever being
        # called with already-safe coordinates.
        isolated_well = (55.5, 19.5, 108.3, 22.5)
        hypothetical_cp_array_well_too_close = (109.0, 19.5, 140.0, 22.5)  # 0.7 um gap
        with self.assertRaises(ValueError):
            cp_dumpbuf.check_well_separation(isolated_well, hypothetical_cp_array_well_too_close)
        hypothetical_cp_array_well_safe = (112.0, 19.5, 140.0, 22.5)  # 3.7 um gap
        cp_dumpbuf.check_well_separation(isolated_well, hypothetical_cp_array_well_safe)


class DeclutterRiserXTests(unittest.TestCase):
    """declutter_riser_x() -- the global-across-nets riser X separation this
    module's own mesh routing relies on for M3.2a safety (issue #391,
    ported from ``cp_array.py``'s own identical function, issue #359)."""

    def test_well_separated_points_are_unchanged(self):
        pts = [("A", 0.0, 0.0), ("B", 10.0, 0.0), ("C", 20.0, 0.0)]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        self.assertEqual(out, pts)

    def test_close_different_nets_are_pushed_apart(self):
        pts = [("A", 0.0, 0.0), ("B", 0.3, 5.0)]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        xs = {net: x for net, x, _y in out}
        self.assertGreaterEqual(abs(xs["B"] - xs["A"]), 1.0)

    def test_declutter_never_changes_y(self):
        pts = [("A", 0.0, 1.0), ("B", 0.1, 2.0), ("C", 0.15, 3.0)]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        for (net, _x0, y0), (net2, _x1, y1) in zip(pts, out):
            self.assertEqual(net, net2)
            self.assertEqual(y0, y1)

    def test_exact_tie_different_nets_are_pushed_apart_not_collapsed(self):
        # Regression test for the exact defect issue #391 found: this
        # module's own 6 external pins used to share one exact natural X
        # (PIN_X_UM) across 6 different nets -- an earlier version of this
        # module's own routing collapsed any same-X riser onto one shared
        # Metal3 column with no net check at all. An exact tie between
        # different nets must be pushed apart, exactly like a near-miss, not
        # silently merged into one column (a real short DRC cannot see).
        pts = [("VBN", -3.0, 1.0), ("VBP", -3.0, 3.0)]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        xs = {net: x for net, x, _y in out}
        self.assertNotEqual(xs["VBN"], xs["VBP"])
        self.assertGreaterEqual(abs(xs["VBN"] - xs["VBP"]), 1.0)

    def test_exact_tie_same_net_still_collapses(self):
        # The one case the original invariant does hold for: two pads of the
        # *same* net sharing an identical natural X are safe -- and
        # correct -- to collapse onto one shared riser column.
        pts = [("VSS", 8.0, 0.21), ("VSS", 8.0, 20.21)]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        xs = [x for _net, x, _y in out]
        self.assertEqual(xs[0], xs[1])

    def test_output_is_pairwise_safe(self):
        pts = [
            ("N0", 0.0, 0.0),
            ("N1", 0.05, 1.0),
            ("N2", 0.05, 2.0),
            ("N3", 0.12, 3.0),
            ("N4", 0.2, 4.0),
            ("N5", 5.0, 5.0),
            ("N6", 5.02, 6.0),
        ]
        out = cp_dumpbuf.declutter_riser_x(pts, 1.0)
        by_x = sorted(out, key=lambda t: t[1])
        for (net_a, xa, _ya), (net_b, xb, _yb) in zip(by_x, by_x[1:]):
            gap = xb - xa
            self.assertTrue(gap == 0.0 or gap >= 1.0, f"{net_a}@{xa} vs {net_b}@{xb}: gap {gap}")


class CheckRiserColumnsTests(unittest.TestCase):
    """check_riser_columns() -- the build-time proof (issue #391, following
    #359's own precedent in ``cp_array.py``) that a two-nets-on-one-column
    allocation cannot be reintroduced silently."""

    def test_well_separated_distinct_nets_pass(self):
        points = [("A", 0.0, 0.0), ("B", 1.5, 3.0), ("C", 3.0, -2.0)]
        cp_dumpbuf.check_riser_columns(points)  # must not raise

    def test_same_net_sharing_a_column_passes(self):
        points = [("VSS", 0.0, 0.2), ("VSS", 0.0, 1.1), ("VDD", 1.5, 0.6)]
        cp_dumpbuf.check_riser_columns(points)  # must not raise

    def test_returns_the_decluttered_plan(self):
        points = [("A", 0.0, 0.0), ("B", 0.3, 1.0)]
        planned = cp_dumpbuf.check_riser_columns(points)
        self.assertEqual(planned, cp_dumpbuf.declutter_riser_x(points))

    def test_verify_raises_on_a_synthetic_two_nets_one_column_plan(self):
        # Synthetic two-nets-one-column input -- the exact defect issue #391
        # found (this module's entire standalone GDS collapsing onto one
        # electrical net) -- fed directly to the verification half
        # (declutter_riser_x() itself can no longer produce this from any
        # real input -- see DeclutterRiserXTests -- so this proves the
        # *check* still fires if that invariant were ever broken again).
        with self.assertRaisesRegex(ValueError, r"^cp_dumpbuf: "):
            cp_dumpbuf._verify_riser_plan([("A", 0.0, 0.0), ("B", 0.0, 1.0)], 1.0)

    def test_verify_raises_on_too_close_distinct_columns(self):
        with self.assertRaisesRegex(ValueError, r"^cp_dumpbuf: "):
            cp_dumpbuf._verify_riser_plan([("A", 0.0, 0.0), ("B", 0.4, 0.0)], 1.0)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTests(unittest.TestCase):
    """cp_dumpbuf.build() on the real device table."""

    @classmethod
    def setUpClass(cls):
        cls.cell = cp_dumpbuf.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.cell.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_every_schematic_pin_is_promoted(self):
        self.assertEqual(set(self.cell.pins), set(cp_dumpbuf.EXTERNAL_NETS))

    def test_isolated_well_is_separated_from_every_other_well_in_this_cell(self):
        self.assertGreaterEqual(len(self.cell.other_well_boxes), 2)  # MTPa/MTPb's + MN3/MN4's
        for other in self.cell.other_well_boxes:
            gap = cp_dumpbuf.well_separation_um(self.cell.isolated_well_box, other)
            self.assertGreaterEqual(gap, cp_dumpbuf.DIFFERENT_POTENTIAL_WELL_MIN_UM)

    def test_mp1_mp2_fingers_are_common_centroid(self):
        # build() already calls check_common_centroid() internally and would
        # have raised; this re-derives the same arithmetic independently as
        # a belt-and-suspenders check on the recorded x-centers.
        centres = self.cell.mp12_x_centers
        self.assertEqual(len(centres), 4)
        array_centre = sum(centres) / len(centres)
        a_centre = (centres[0] + centres[3]) / 2.0  # MP1a, MP1b
        b_centre = (centres[1] + centres[2]) / 2.0  # MP2a, MP2b
        self.assertAlmostEqual(a_centre, array_centre, places=6)
        self.assertAlmostEqual(b_centre, array_centre, places=6)

    def test_mp1_mp2_fingers_are_ordered_abba_not_two_blobs(self):
        centres = self.cell.mp12_x_centers
        self.assertEqual(centres, sorted(centres))  # placed left-to-right in P_DEVICES order
        # ABBA: the two outer fingers (indices 0, 3) are one leg, the two
        # inner fingers (indices 1, 2) are the other -- not AABB.
        self.assertLess(centres[0], centres[1])
        self.assertLess(centres[1], centres[2])
        self.assertLess(centres[2], centres[3])


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class ConnectivityTests(unittest.TestCase):
    """The finished GDS's own extracted Metal1-3 connectivity -- the only
    check that can see a short or an open (``layout/run_pv.py drc`` cannot;
    see ``netcheck.py``'s own docstring). Regression coverage for issue
    #391: this module's own standalone GDS used to collapse onto one
    electrical net (``VBN+VBP+VDD+VDUMP+VREF+VSS`` and every internal net
    too), invisible to DRC, because every net's own Metal3 riser landed at
    its own pad's exact natural X with no cross-net collision check at all."""

    @classmethod
    def setUpClass(cls):
        cls.cell = cp_dumpbuf.build()
        cls._tmp = tempfile.TemporaryDirectory()
        gds = Path(cls._tmp.name) / f"{cp_dumpbuf.TOP_CELL}.gds"
        cls.cell.write_gds(gds)
        cls.report = netcheck.check_gds(
            gds, cp_dumpbuf.TOP_CELL, netcheck.pad_probe_points(cls.cell.probe_pads())
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_every_probe_point_lands_on_real_metal(self):
        self.assertEqual(self.report.unresolved, (), "stale probe coordinates")

    def test_no_net_is_open(self):
        self.assertEqual(self.report.splits, ())

    def test_no_shorts_at_all(self):
        self.assertEqual(self.report.shorts, ())

    def test_every_external_pin_is_its_own_net(self):
        # The exact nets issue #391's own reproduction reported shorted
        # together (all 6 external pins, collapsed onto one component via
        # the shared PIN_X_UM column).
        shorted = {net for group in self.report.shorts for net in group}
        for net in cp_dumpbuf.EXTERNAL_NETS:
            self.assertIn(net, self.report.components, net)
            self.assertEqual(len(self.report.components[net]), 1, f"{net} is split")
            self.assertNotIn(net, shorted, f"{net} is shorted")

    def test_internal_nets_are_not_shorted_either(self):
        # Issue #391 also recurred internally (e.g. a device's own top and
        # bottom pad sharing one Metal3 column) -- not just the external
        # pins -- so this probes every internal net this module's own
        # net_pads records, not only the promoted schematic pins.
        shorted = {net for group in self.report.shorts for net in group}
        for net in ("NSRC", "NDA", "PSRC", "PDA"):
            self.assertIn(net, self.report.components, net)
            self.assertNotIn(net, shorted, f"{net} is shorted")

    def test_vdump_is_a_distinct_net_of_its_own(self):
        # VDUMP is both the unity-gain feedback node and an external pin --
        # a real short here would merge it with VDD (issue #391's own
        # reported x=94.0 MN4 top/bottom collision).
        self.assertEqual(len(self.report.components["VDUMP"]), 1)
        vdump = next(iter(self.report.components["VDUMP"]))
        for net, ids in self.report.components.items():
            if net == "VDUMP":
                continue
            self.assertNotIn(vdump, ids, f"VDUMP is not a stub -- it reaches {net}")


if __name__ == "__main__":
    unittest.main()
