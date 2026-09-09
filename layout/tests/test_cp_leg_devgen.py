#!/usr/bin/env python3
"""Smoke tests for the ``cp_leg_n``/``cp_leg_p`` composite device layout
(issue #319, Part 3a of #294, a decomposition of #301).

Unlike ``test_pfdcp_devgen.py`` (a single ``devgen.build_stack_cell()``
column), ``cp_leg.build_leg()`` hand-routes a 3-way net (``BG``) across two
independent columns -- skipped, not failed, when ``klayout.db`` is
unavailable, so a PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks), see ``layout/evidence/cp-leg-proof/PROOF.md`` -- this file
checks the geometry ``cp_leg``/``cp_leg_n``/``cp_leg_p`` *claim* to build
(device-table sizes/nets match the schematics, the hand-routed BG tap's own
geometric precondition, boundary-pin promotion, footprint sanity), not a
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

from pfd_cp import cp_leg, cp_leg_n, cp_leg_p  # noqa: E402


class DeviceTableTests(unittest.TestCase):
    """cp_leg_n.SPEC/cp_leg_p.SPEC match their own schematics' device sizes/nets."""

    def test_cp_leg_n_matches_schematic(self):
        spec = cp_leg_n.SPEC
        self.assertEqual(spec.kind, "nfet")
        self.assertEqual((spec.w_steer_um, spec.l_steer_um), (1.0, 0.3))
        self.assertEqual((spec.w_mirror_um, spec.l_mirror_um), (4.0, 1.0))
        self.assertEqual(spec.rail_net, "VSS")
        self.assertEqual(spec.bias_net, "VBN")
        self.assertEqual(spec.cascode_net, "VCASCN")
        self.assertEqual(spec.mdis_gate_net, "ENB")
        self.assertEqual(spec.men_gate_net, "EN")
        self.assertEqual(spec.mirror_bottom_name, "MBOT")

    def test_cp_leg_p_matches_schematic(self):
        spec = cp_leg_p.SPEC
        self.assertEqual(spec.kind, "pfet")
        self.assertEqual((spec.w_steer_um, spec.l_steer_um), (1.0, 0.3))
        # W is 3x the NMOS unit (see design/cp_leg_p.sch's own comment).
        self.assertEqual((spec.w_mirror_um, spec.l_mirror_um), (12.0, 1.0))
        self.assertEqual(spec.rail_net, "VDD")
        self.assertEqual(spec.bias_net, "VBP")
        self.assertEqual(spec.cascode_net, "VCASCP")
        # EN/ENB are swapped relative to cp_leg_n's own MDIS/MEN gates.
        self.assertEqual(spec.mdis_gate_net, "EN")
        self.assertEqual(spec.men_gate_net, "ENB")
        self.assertEqual(spec.mirror_bottom_name, "MTOP")


class ReferenceNetlistTests(unittest.TestCase):
    """The hand-written LVS reference netlists match each device table."""

    def test_cp_leg_n_declares_all_four_devices_with_matching_sizes(self):
        netlist = cp_leg_n.reference_netlist()
        self.assertIn(".subckt cp_leg_n VBN VCASCN EN ENB TAIL VSS", netlist)
        self.assertIn("nfet_03v3 W=1u L=0.3u", netlist)
        self.assertIn("nfet_03v3 W=4u L=1u", netlist)
        self.assertEqual(netlist.count("nfet_03v3"), 4)

    def test_cp_leg_p_declares_all_four_devices_with_matching_sizes(self):
        netlist = cp_leg_p.reference_netlist()
        self.assertIn(".subckt cp_leg_p VBP VCASCP EN ENB TAIL VDD", netlist)
        self.assertIn("pfet_03v3 W=1u L=0.3u", netlist)
        self.assertIn("pfet_03v3 W=12u L=1u", netlist)
        self.assertEqual(netlist.count("pfet_03v3"), 4)

    def test_bg_and_mid_are_internal_not_boundary_pins_in_the_netlist(self):
        # BG/MID only ever appear as internal device-terminal nodes, never
        # in either .subckt's own port list.
        for netlist, top in ((cp_leg_n.reference_netlist(), "cp_leg_n"), (cp_leg_p.reference_netlist(), "cp_leg_p")):
            port_line = next(line for line in netlist.splitlines() if line.startswith(f".subckt {top} "))
            ports = port_line.split()[2:]
            self.assertNotIn("BG", ports)
            self.assertNotIn("MID", ports)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class HandRoutedBgTapGeometryTests(unittest.TestCase):
    """The precondition _route_bg_tap()/_route_rail_strap_and_tap() rely on
    (see cp_leg.py's own module docstring's "HAND-ROUTED BG TAP" section)
    actually holds for both legs' fixed device geometry.
    """

    def test_mirror_gate_y_center_is_fixed_regardless_of_width(self):
        # SD_OVERHANG_UM + l_mirror/2 = 0.5 + 0.5 = 1.0, independent of W.
        n_layout = cp_leg_n.build()
        p_layout = cp_leg_p.build()
        n_gate_y = n_layout.ports["MBOT"].gate_y_center
        p_gate_y = p_layout.ports["MTOP"].gate_y_center
        self.assertAlmostEqual(n_gate_y, 1.0)
        self.assertAlmostEqual(p_gate_y, n_gate_y)

    def test_mirror_gate_lands_inside_steer_bottom_drain_pad_y_range(self):
        for layout in (cp_leg_n.build(), cp_leg_p.build()):
            mirror_bottom_name = "MBOT" if "MBOT" in layout.ports else "MTOP"
            gate_y = layout.ports[mirror_bottom_name].gate_y_center
            pad_y0, pad_y1 = layout.ports["MDIS"].top_pad[1], layout.ports["MDIS"].top_pad[3]
            self.assertLessEqual(pad_y0, gate_y)
            self.assertLessEqual(gate_y, pad_y1)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildLegTests(unittest.TestCase):
    """cp_leg.build_leg() on both cp_leg_n/cp_leg_p device specs."""

    @classmethod
    def setUpClass(cls):
        cls.n = cp_leg_n.build()
        cls.p = cp_leg_p.build()

    def test_four_devices_drawn_each(self):
        self.assertEqual(len(self.n.ports), 4)
        self.assertEqual(len(self.p.ports), 4)

    def test_footprint_has_positive_extent(self):
        for layout in (self.n, self.p):
            x0, y0, x1, y1 = layout.footprint
            self.assertGreater(x1 - x0, 0.0)
            self.assertGreater(y1 - y0, 0.0)

    def test_cp_leg_n_boundary_pins(self):
        self.assertEqual(set(self.n.pins), {"VBN", "VCASCN", "EN", "ENB", "TAIL", "VSS"})

    def test_cp_leg_p_boundary_pins(self):
        self.assertEqual(set(self.p.pins), {"VBP", "VCASCP", "EN", "ENB", "TAIL", "VDD"})

    def test_bg_and_mid_are_not_promoted_as_boundary_pins(self):
        for layout in (self.n, self.p):
            self.assertNotIn("BG", layout.pins)
            self.assertNotIn("MID", layout.pins)

    def test_cp_leg_p_has_an_nwell_enclosing_every_pfet(self):
        self.assertIsNotNone(self.p.nwell_box)
        x0, y0, x1, y1 = self.p.nwell_box
        for port in self.p.ports.values():
            self.assertLessEqual(x0, port.x0)
            self.assertGreaterEqual(x1, port.x1)
            self.assertLessEqual(y0, port.y0)
            self.assertGreaterEqual(y1, port.y3)

    def test_cp_leg_n_has_no_nwell(self):
        self.assertIsNone(self.n.nwell_box)

    def test_mirror_device_is_wider_for_p_leg(self):
        # cp_leg_p's mirror devices (MTOP/MCASC) are 3x cp_leg_n's (MBOT/
        # MCASC), per design/cp_leg_p.sch's own comment.
        n_width = self.n.ports["MBOT"].x1 - self.n.ports["MBOT"].x0
        p_width = self.p.ports["MTOP"].x1 - self.p.ports["MTOP"].x0
        self.assertAlmostEqual(p_width, 3.0 * n_width)

    def test_unreachable_bg_tap_raises(self):
        # A LegSpec whose mirror L is small enough that gate_y_center falls
        # below steer_bottom's own drain pad Y-range must raise, not
        # silently draw a disconnected BG net.
        bad_spec = cp_leg.LegSpec(
            top_cell="cp_leg_bad_test",
            kind="nfet",
            rail_net="VSS",
            bias_net="VBN",
            cascode_net="VCASCN",
            mdis_gate_net="ENB",
            men_gate_net="EN",
            mirror_bottom_name="MBOT",
            w_mirror_um=4.0,
            l_mirror_um=0.05,
        )
        with self.assertRaises(ValueError):
            cp_leg.build_leg(bad_spec)


if __name__ == "__main__":
    unittest.main()
