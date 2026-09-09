#!/usr/bin/env python3
"""Smoke tests for the ``dff_tg_3v3`` composite macro (issue #308).

Like ``test_divider_devgen.py``, the geometry-building tests here need
``klayout.db`` importable -- skipped, not failed, when unavailable, so a
PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks), see ``layout/evidence/divider-dff-proof/PROOF.md`` -- this
file checks the instance table and the geometry ``dff_tg_3v3.build()``
*claims* to draw (device/pin counts, footprint sanity, the internal-net
wiring the module's own docstring documents), not a substitute for running
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

from divider_chain import dff_tg_3v3, inv_3v3, tgate_3v3  # noqa: E402

#: design/netlist/dff_tg_3v3.spice's own X-instance argument order, name ->
#: (kind, D/A-side arg, CK-or-Y-side arg, ...gate args). Used to
#: cross-check INSTANCES against the netlist this module's own docstring
#: transcribes it from, independently of dff_tg_3v3.py's own source.
_EXPECTED_NET_WIRING = {
    "XICKB": ("inv", "CK", "CKB"),
    "XICKBB": ("inv", "CKB", "CKBB"),
    "XTGMI": ("tgate", "D", "NM", "CKB", "CKBB"),
    "XIA": ("inv", "NM", "NMA"),
    "XIB": ("inv", "NMA", "NMB"),
    "XTGMF": ("tgate", "NMB", "NM", "CKBB", "CKB"),
    "XTGSI": ("tgate", "NMA", "NS", "CKBB", "CKB"),
    "XIC": ("inv", "NS", "Q"),
    "XID": ("inv", "Q", "QB"),
    "XTGSF": ("tgate", "QB", "NS", "CKB", "CKBB"),
}

_INTERNAL_NETS = {"CKB", "CKBB", "NM", "NMA", "NMB", "NS"}


class InstanceTableTests(unittest.TestCase):
    """INSTANCES matches design/netlist/dff_tg_3v3.spice's own X-instance list."""

    def test_ten_instances(self):
        self.assertEqual(len(dff_tg_3v3.INSTANCES), 10)

    def test_six_inv_four_tgate(self):
        kinds = [kind for _name, kind, _devices, _port_map in dff_tg_3v3.INSTANCES]
        self.assertEqual(kinds.count("inv"), 6)
        self.assertEqual(kinds.count("tgate"), 4)

    def test_names_and_wiring_match_the_netlist(self):
        self.assertEqual({n for n, *_ in dff_tg_3v3.INSTANCES}, set(_EXPECTED_NET_WIRING))
        for name, kind, _devices, port_map in dff_tg_3v3.INSTANCES:
            expected = _EXPECTED_NET_WIRING[name]
            if kind == "inv":
                _, a, y = expected
                self.assertEqual(port_map["A"], a, name)
                self.assertEqual(port_map["Y"], y, name)
                self.assertEqual(port_map["VDD"], "VDD", name)
                self.assertEqual(port_map["VSS"], "VSS", name)
            else:
                _, a, y, gn, gp = expected
                self.assertEqual(port_map["A"], a, name)
                self.assertEqual(port_map["Y"], y, name)
                self.assertEqual(port_map["GN"], gn, name)
                self.assertEqual(port_map["GP"], gp, name)

    def test_inv_instances_reuse_inv_3v3s_own_device_table(self):
        for _name, kind, devices, _port_map in dff_tg_3v3.INSTANCES:
            if kind == "inv":
                self.assertIs(devices, inv_3v3.INV_DEVICES)

    def test_tgate_instances_reuse_tgate_3v3s_own_device_table(self):
        for _name, kind, devices, _port_map in dff_tg_3v3.INSTANCES:
            if kind == "tgate":
                self.assertIs(devices, tgate_3v3.TGATE_DEVICES)

    def test_boundary_nets_are_the_schematics_own_six_ports(self):
        self.assertEqual(set(dff_tg_3v3.BOUNDARY_NETS), {"D", "CK", "Q", "QB", "VDD", "VSS"})

    def test_every_internal_net_appears_in_some_instances_port_map(self):
        seen = set()
        for _name, _kind, _devices, port_map in dff_tg_3v3.INSTANCES:
            seen.update(port_map.values())
        for net in _INTERNAL_NETS:
            self.assertIn(net, seen)
        # and every net used is either a boundary net or an internal net --
        # no stray typo'd net name silently introduces an extra node.
        self.assertEqual(seen, _INTERNAL_NETS | set(dff_tg_3v3.BOUNDARY_NETS))


class ReferenceNetlistTests(unittest.TestCase):
    """The hand-written LVS reference netlist matches the instance table."""

    def setUp(self):
        self.netlist = dff_tg_3v3.reference_netlist()

    def test_subckt_name_and_ports(self):
        header = next(line for line in self.netlist.splitlines() if line.startswith(".subckt"))
        self.assertIn(f".subckt {dff_tg_3v3.TOP_CELL} ", header)
        for net in ("D", "CK", "Q", "QB", "VDD", "VSS"):
            self.assertIn(net, header.split())

    def test_twenty_devices_declared(self):
        m_lines = [ln for ln in self.netlist.splitlines() if ln.startswith("M_")]
        self.assertEqual(len(m_lines), 20)

    def test_ten_pfet_ten_nfet(self):
        self.assertEqual(self.netlist.count("pfet_03v3 W=2.5u L=0.28u"), 10)
        self.assertEqual(self.netlist.count("nfet_03v3 W=1u L=0.28u"), 10)

    def test_every_internal_net_appears_in_the_body(self):
        for net in _INTERNAL_NETS:
            self.assertIn(net, self.netlist)

    def test_ends_terminator_present(self):
        self.assertTrue(self.netlist.rstrip().endswith(".ends"))


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildLayoutTests(unittest.TestCase):
    """dff_tg_3v3.build() draws the claimed geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = dff_tg_3v3.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_height_is_at_least_one_columns_own_row_height(self):
        # Row height/pitch consistency with #306/#307's leaf cells (this
        # issue's own acceptance criterion): a column is NMOS (y in
        # [0, 1.28]) + NWELL_TO_NMOS_GAP_UM (4.0) + PMOS (1.28 tall) = 6.56
        # um tall before any routing headroom is added above it.
        _x0, y0, _x1, y1 = self.layout.footprint
        self.assertGreaterEqual(y1 - y0, 6.56)

    def test_only_boundary_nets_are_pin_labelled(self):
        self.assertEqual(set(self.layout.pins), set(dff_tg_3v3.BOUNDARY_NETS))

    def test_nwell_box_is_set_and_encloses_positive_area(self):
        self.assertIsNotNone(self.layout.nwell_box)
        x0, y0, x1, y1 = self.layout.nwell_box
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_write_gds_smoke(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dff_tg_3v3.gds"
            self.layout.write_gds(out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class OffsetPadXTests(unittest.TestCase):
    """devgen.offset_pad_x() -- the same-x riser-collision fix this
    composite's own routing needed (see devgen.py's and dff_tg_3v3.py's own
    docstrings for the concrete LVS-merged-node failure it fixes)."""

    def test_no_extension_needed_when_pad_already_wide_enough(self):
        from divider_chain import devgen

        canvas = devgen.Canvas("offset_pad_x_test_wide")
        # A pad wide enough (2.0 um) that a target 0.5 um off-center still
        # keeps the via fully enclosed without any extra Metal1.
        wide_pad = (0.0, 0.0, 2.0, 1.0)
        before = canvas.layout.cell(canvas.top.cell_index()).bbox()
        point = devgen.offset_pad_x(canvas, wide_pad, 0.5)
        after = canvas.layout.cell(canvas.top.cell_index()).bbox()
        self.assertEqual(point, (1.5, 0.5))
        self.assertEqual(before, after)  # no shape was drawn

    def test_extension_drawn_when_pad_too_narrow(self):
        from divider_chain import devgen

        canvas = devgen.Canvas("offset_pad_x_test_narrow")
        narrow_pad = (0.0, 0.0, 0.5, 0.5)
        point = devgen.offset_pad_x(canvas, narrow_pad, 1.0)
        self.assertAlmostEqual(point[0], 1.25)
        self.assertAlmostEqual(point[1], 0.25)
        # Something was drawn on metal1 to reach that point.
        bbox = canvas.layout.cell(canvas.top.cell_index()).bbox()
        self.assertGreater(bbox.width(), 0)


if __name__ == "__main__":
    unittest.main()
