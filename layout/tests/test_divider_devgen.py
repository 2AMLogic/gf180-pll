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


if __name__ == "__main__":
    unittest.main()
