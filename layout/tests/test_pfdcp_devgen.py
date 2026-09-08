#!/usr/bin/env python3
"""Smoke tests for the PFD/CP device-layout helper (issue #299).

Unlike ``test_vco_layout.py``, this module *does* need ``klayout.db``
importable (``devgen.build_stack_cell()`` is exercised directly, not just
its pure-Python device table) -- skipped, not failed, when unavailable, so
a PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks), see ``layout/evidence/pfdcp-inv-proof/PROOF.md`` -- this
file checks the geometry ``devgen``/``pfdcp_inv`` *claim* to build (net
resolution, pin promotion, footprint sanity), not a substitute for running
the decks.
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

from pfd_cp import devgen  # noqa: E402
from pfd_cp import pfdcp_inv  # noqa: E402


class DeviceTableTests(unittest.TestCase):
    """pfdcp_inv.INV_DEVICES matches design/pfdcp_inv_3v3.sch's own MP/MN."""

    def test_two_devices(self):
        self.assertEqual(len(pfdcp_inv.INV_DEVICES), 2)

    def test_sizes_match_the_schematic(self):
        sizes = {d.name: (d.kind, d.w_um, d.l_um) for d in pfdcp_inv.INV_DEVICES}
        self.assertEqual(sizes["MP"], ("pfet", 1.5, 0.3))
        self.assertEqual(sizes["MN"], ("nfet", 0.5, 0.3))

    def test_gate_and_drain_are_shared_nets(self):
        by_name = {d.name: d for d in pfdcp_inv.INV_DEVICES}
        self.assertEqual(by_name["MP"].gate_net, by_name["MN"].gate_net)
        self.assertEqual(by_name["MP"].gate_net, "A")
        self.assertEqual(by_name["MP"].bottom_net, by_name["MN"].top_net)
        self.assertEqual(by_name["MP"].bottom_net, "Y")

    def test_supplies_are_distinct_boundary_nets(self):
        by_name = {d.name: d for d in pfdcp_inv.INV_DEVICES}
        self.assertEqual(by_name["MP"].top_net, "VDD")
        self.assertEqual(by_name["MN"].bottom_net, "VSS")


class ReferenceNetlistTests(unittest.TestCase):
    """The hand-written LVS reference netlist matches the device table."""

    def test_declares_both_devices_with_matching_sizes(self):
        netlist = pfdcp_inv.reference_netlist()
        self.assertIn("pfet_03v3 W=1.5u L=0.3u", netlist)
        self.assertIn("nfet_03v3 W=0.5u L=0.3u", netlist)

    def test_subckt_name_matches_top_cell(self):
        netlist = pfdcp_inv.reference_netlist()
        self.assertIn(f".subckt {pfdcp_inv.TOP_CELL} ", netlist)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildStackCellTests(unittest.TestCase):
    """devgen.build_stack_cell() on the representative inverter device list."""

    @classmethod
    def setUpClass(cls):
        cls.leaf = devgen.build_stack_cell("pfdcp_inv_3v3_test", pfdcp_inv.INV_DEVICES)

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

    def test_pfet_sits_above_the_nfet_with_well_clearance(self):
        nfet_port = next(p for p in self.leaf.ports if p.kind == "nfet")
        pfet_port = next(p for p in self.leaf.ports if p.kind == "pfet")
        self.assertGreaterEqual(pfet_port.y0 - nfet_port.y3, devgen.NWELL_TO_NMOS_GAP_UM)

    def test_single_device_stack_raises_on_unresolvable_net(self):
        # A lone pfet's gate net has exactly one terminal (fine, promoted),
        # but this asserts build_stack_cell() actually raises rather than
        # silently dropping a net with an unsupported terminal count -- a
        # 3-terminal net (three devices sharing one gate_net) is out of this
        # module's supported topology (see devgen.py's module docstring).
        three_way = (
            devgen.Device(name="U0", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="A", bottom_net="VSS"),
            devgen.Device(name="U1", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="B", bottom_net="A"),
            devgen.Device(name="U2", kind="nfet", w_um=0.5, l_um=0.3, gate_net="SHARED", top_net="VDD", bottom_net="B"),
        )
        with self.assertRaises(ValueError):
            devgen.build_stack_cell("bad_stack_test", three_way)


if __name__ == "__main__":
    unittest.main()
