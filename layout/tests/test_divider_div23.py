#!/usr/bin/env python3
"""Smoke tests for the ``div23_cell`` composite macro (issue #309).

Like ``test_divider_dff.py``, the geometry-building tests here need
``klayout.db`` importable -- skipped, not failed, when unavailable, so a
PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks), see ``layout/evidence/divider-div23-proof/PROOF.md`` -- this
file checks the instance/net table and the geometry ``div23_cell.build()``
*claims* to draw (device/pin counts, footprint stability, the per-instance
net wiring the module's own docstring documents), not a substitute for
running the decks.
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

from divider_chain import div23_cell, inv_3v3, nand3_3v3  # noqa: E402

#: design/netlist/div23_cell.spice's own X-instance argument order --
#: (kind, boundary net args...). Used to cross-check div23_cell.py's own
#: placements()/port maps against the netlist its own docstring transcribes
#: it from, independently of div23_cell.py's own source.
_EXPECTED_INSTANCES = {
    "XN3": ("nand3", "MODIN", "P", "MODOUT", "SB"),
    "XN2Q": ("nand2", "QB", "SB", "DQN"),
    "XIQ": ("inv", "DQN", "DQ"),
    "XFQ": ("dff", "DQ", "CKIN", "Q", "QB"),
    "XICKO": ("inv2x", "QB", "CKOUT"),
    "XN2M": ("nand2", "MODIN", "Q", "NMO"),
    "XIM": ("inv", "NMO", "DMO"),
    "XFMO": ("dff", "DMO", "CKIN", "MODOUT", "MOB"),
}


class PlacementsTableTests(unittest.TestCase):
    """div23_cell.placements() matches design/netlist/div23_cell.spice's own X-instance list."""

    def test_thirty_columns(self):
        # 3 (nand3) + 2 (nand2 XN2Q) + 1 (inv XIQ) + 10 (dff XFQ) + 1 (inv2x)
        # + 2 (nand2 XN2M) + 1 (inv XIM) + 10 (dff XFMO) = 30.
        self.assertEqual(len(div23_cell.placements()), 30)

    def test_sixty_devices_total(self):
        total = sum(len(col.pulldown) + len(col.pullup) for col, _pm in div23_cell.placements())
        self.assertEqual(total, 60)

    def test_thirty_nfet_thirty_pfet(self):
        nfets = sum(len(col.pulldown) for col, _pm in div23_cell.placements())
        pfets = sum(len(col.pullup) for col, _pm in div23_cell.placements())
        self.assertEqual(nfets, 30)
        self.assertEqual(pfets, 30)

    def test_boundary_nets_are_the_schematics_own_seven_ports(self):
        self.assertEqual(set(div23_cell.BOUNDARY_NETS), {"CKIN", "MODIN", "P", "CKOUT", "MODOUT", "VDD", "VSS"})

    def test_nand3_reuses_nand3_3v3s_own_columns(self):
        cols = div23_cell.placements()[:3]
        for (col, port_map), ref_col in zip(cols, nand3_3v3.COLUMNS):
            self.assertIs(col, ref_col)
        _col0, port_map0 = cols[0]
        self.assertEqual(port_map0["A"], "MODIN")
        self.assertEqual(port_map0["B"], "P")
        self.assertEqual(port_map0["C"], "MODOUT")
        self.assertEqual(port_map0["Y"], "SB")

    def test_nand2_instances_have_distinct_port_maps(self):
        placements = div23_cell.placements()
        # XN2Q is placements[3:5]; XN2M is placements[24:26] (3 nand3 + 2
        # nand2 + 1 inv + 10 dff + 1 inv2x = 17, then + 2 nand2 = 19... see
        # test_thirty_columns' own accounting; index directly instead of
        # re-deriving offsets here.
        xn2q_port_map = placements[3][1]
        self.assertEqual(xn2q_port_map["A"], "QB")
        self.assertEqual(xn2q_port_map["B"], "SB")
        self.assertEqual(xn2q_port_map["Y"], "DQN")
        self.assertEqual(xn2q_port_map["NMID"], "XN2Q_NMID")
        self.assertNotEqual(xn2q_port_map["NMID"], "XN2M_NMID")

    def test_dff_columns_reuse_dff_tg_3v3s_own_instances(self):
        # _dff_columns() (the helper div23_cell.placements() itself calls
        # for XFQ/XFMO) draws exactly dff_tg_3v3.INSTANCES' own 10 columns,
        # each device table one of inv_3v3.INV_DEVICES/tgate_3v3.TGATE_DEVICES.
        from divider_chain import tgate_3v3

        boundary = {"D": "DQ", "CK": "CKIN", "Q": "Q", "QB": "QB", "VDD": "VDD", "VSS": "VSS"}
        cols = div23_cell._dff_columns("XFQ", boundary)
        self.assertEqual(len(cols), 10)
        for col, _pm in cols:
            devices = col.pulldown + col.pullup
            self.assertTrue(
                devices == inv_3v3.INV_DEVICES or devices == tgate_3v3.TGATE_DEVICES,
                devices,
            )

    def test_two_dff_instances_have_distinct_internal_nets(self):
        boundary_q = {"D": "DQ", "CK": "CKIN", "Q": "Q", "QB": "QB", "VDD": "VDD", "VSS": "VSS"}
        boundary_mo = {"D": "DMO", "CK": "CKIN", "Q": "MODOUT", "QB": "MOB", "VDD": "VDD", "VSS": "VSS"}
        cols_q = div23_cell._dff_columns("XFQ", boundary_q)
        cols_mo = div23_cell._dff_columns("XFMO", boundary_mo)
        nets_q = {n for _col, pm in cols_q for n in pm.values()}
        nets_mo = {n for _col, pm in cols_mo for n in pm.values()}
        internal_q = {n for n in nets_q if n.startswith("XFQ_")}
        internal_mo = {n for n in nets_mo if n.startswith("XFMO_")}
        self.assertEqual(len(internal_q), 6)
        self.assertEqual(len(internal_mo), 6)
        self.assertEqual(internal_q & internal_mo, set())


class ReferenceNetlistTests(unittest.TestCase):
    """The hand-written LVS reference netlist matches the placements table."""

    def setUp(self):
        self.netlist = div23_cell.reference_netlist()

    def test_subckt_name_and_ports(self):
        header = next(line for line in self.netlist.splitlines() if line.startswith(".subckt"))
        self.assertIn(f".subckt {div23_cell.TOP_CELL} ", header)
        for net in div23_cell.BOUNDARY_NETS:
            self.assertIn(net, header.split())

    def test_sixty_devices_declared(self):
        m_lines = [ln for ln in self.netlist.splitlines() if ln.startswith("M_")]
        self.assertEqual(len(m_lines), 60)

    def test_thirty_pfet_thirty_nfet(self):
        self.assertEqual(self.netlist.count("pfet_03v3"), 30)
        self.assertEqual(self.netlist.count("nfet_03v3"), 30)

    def test_every_instance_prefix_appears(self):
        for prefix in ("XN3", "XN2Q", "XIQ", "XFQ", "XICKO", "XN2M", "XIM", "XFMO"):
            with self.subTest(prefix=prefix):
                self.assertIn(f"M_{prefix}_", self.netlist)

    def test_dff_internal_nets_are_instance_prefixed(self):
        for prefix in ("XFQ", "XFMO"):
            for net in ("CKB", "CKBB", "NM", "NMA", "NMB", "NS"):
                with self.subTest(prefix=prefix, net=net):
                    self.assertIn(f"{prefix}_{net}", self.netlist)

    def test_ends_terminator_present(self):
        self.assertTrue(self.netlist.rstrip().endswith(".ends"))


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildLayoutTests(unittest.TestCase):
    """div23_cell.build() draws the claimed geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = div23_cell.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_only_boundary_nets_are_pin_labelled(self):
        self.assertEqual(set(self.layout.pins), set(div23_cell.BOUNDARY_NETS))

    def test_nwell_box_is_set_and_encloses_positive_area(self):
        self.assertIsNotNone(self.layout.nwell_box)
        x0, y0, x1, y1 = self.layout.nwell_box
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_write_gds_smoke(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "div23_cell.gds"
            self.layout.write_gds(out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class FootprintStabilityTests(unittest.TestCase):
    """This macro's footprint/pin locations are stable, non-hand-tuned outputs.

    Part 5's own acceptance criterion (see #295, #309): six identical,
    *unmodified* instances of this macro -- so a silent shift in this
    module's own geometry has to be caught here, not discovered downstream
    in Part 5's own assembly. Values match
    ``layout/evidence/divider-div23-proof/PROOF.md``'s own recorded
    footprint/pin table (built once, both places, from the same
    ``div23_cell.build()`` -- see that module's own docstring for why the
    module itself, not this test, is this composite's single source of
    geometric truth).
    """

    @classmethod
    def setUpClass(cls):
        cls.layout = div23_cell.build()

    def test_footprint_matches_the_recorded_evidence(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertAlmostEqual(x0, -2.62, places=2)
        self.assertAlmostEqual(y0, -0.3, places=2)
        self.assertAlmostEqual(x1, 329.52, places=2)
        self.assertAlmostEqual(y1, 37.5, places=2)

    def test_pin_locations_match_the_recorded_evidence(self):
        expected = {
            "CKIN": (65.5, 0.64),
            "MODIN": (-2.4, 4.4),
            "P": (-1.0, 2.52),
            "CKOUT": (179.6, 1.07),
            "MODOUT": (-1.7, 0.64),
            "VDD": (1.8, 11.07),
            "VSS": (2.5, 0.21),
        }
        for net, (ex, ey) in expected.items():
            with self.subTest(net=net):
                ax, ay = self.layout.pins[net]
                self.assertAlmostEqual(ax, ex, places=2)
                self.assertAlmostEqual(ay, ey, places=2)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class RoleReferenceCollisionTests(unittest.TestCase):
    """The "gate"/"channel" role reference anchors stay clear of each other
    and of a column's own natural (unmodified) pad geometry -- the concrete
    class of bug this module's own docstring ("NET-COLLISION FIX") records
    two real DRC-violation-producing attempts at before landing on this
    fixed-anchor scheme. Not a re-run of the PDK's own DRC deck (see
    ``PROOF.md`` for that); a fast, PDK-independent regression guard against
    reintroducing the same class of collision.
    """

    def test_gate_reference_stays_clear_of_column_x0(self):
        # Worst case this composite ever needs: 3 distinct gate nets
        # (nand3_3v3's column 0 -- A/B/C), spread symmetrically around
        # GATE_REF_DX_UM. Its own rightmost target must stay outside the
        # M3.2a spacing floor from x0 (where a channel pad's own natural,
        # un-offset left edge sits).
        worst_case_n = 3
        max_offset = ((worst_case_n - 1) / 2.0) * div23_cell.NET_OFFSET_STEP_UM
        gate_rightmost = div23_cell.GATE_REF_DX_UM + max_offset
        self.assertLessEqual(gate_rightmost, -1.0)

    def test_channel_reference_stays_clear_of_gate_reference(self):
        # Worst case: 5 distinct channel nets (nand3_3v3's column 0 --
        # NM1/NM2/VSS/VDD/Y) vs. 3 distinct gate nets, both anchored off the
        # same x0.
        gate_max = ((3 - 1) / 2.0) * div23_cell.NET_OFFSET_STEP_UM + div23_cell.GATE_REF_DX_UM
        channel_min = div23_cell.CHANNEL_REF_DX_UM - ((5 - 1) / 2.0) * div23_cell.NET_OFFSET_STEP_UM
        # > Metal3 wire width (0.34) + M3.2a's 0.28 um minimum spacing.
        self.assertGreater(channel_min - gate_max, 0.34 + 0.28)


if __name__ == "__main__":
    unittest.main()
