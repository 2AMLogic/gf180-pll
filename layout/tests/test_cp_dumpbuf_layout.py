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
substitute for running the deck.
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

from pfd_cp import cp_dumpbuf  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
