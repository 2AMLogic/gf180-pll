#!/usr/bin/env python3
"""Unit tests for the ``lock_detector`` block's device transcription (issue #296).

No PDK and no KLayout required -- ``pll_top/lock_detector/devices.py`` and
``primitives.py`` only import ``klayout.db`` lazily, inside
``primitives.Canvas.__post_init__`` (same convention as
``floorplan/skeleton.py``/``harness/cell.py``), so the transistor parameter
tables and the package's DRC-margin constants are plain-Python and
importable with no PV environment. These tests cross-check
``devices.py``'s ``Fet`` transcription against
``design/netlist/lock_detector.spice`` (the generated netlist every ``Fet``
below is meant to match line for line) and the "narrow device needs a
dog-bone S/D terminal" structural invariant ``primitives.mosfet()`` relies
on -- not KLayout/DRC behavior.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))

from pll_top.lock_detector import devices as dev  # noqa: E402
from pll_top.lock_detector import primitives  # noqa: E402

REPO_ROOT = LAYOUT_DIR.parent
NETLIST_PATH = REPO_ROOT / "design" / "netlist" / "lock_detector.spice"


class DeviceTranscriptionTests(unittest.TestCase):
    """Cross-checks every ``devices.py`` generator's ``Fet`` output against
    its own docstring-quoted SPICE line (a change to either without the
    other should fail here, not first show up as a DRC/LVS surprise)."""

    def test_inv_fets_matches_inv_3v3_sch(self):
        mp, mn = dev.inv_fets("", "A", "Y", "VDD", "VSS")
        self.assertEqual((mp.kind, mp.w_um, mp.l_um, mp.d, mp.g, mp.s, mp.b), ("pfet", 2.5, 0.28, "Y", "A", "VDD", "VDD"))
        self.assertEqual((mn.kind, mn.w_um, mn.l_um, mn.d, mn.g, mn.s, mn.b), ("nfet", 1.0, 0.28, "Y", "A", "VSS", "VSS"))

    def test_nand2_fets_matches_nand2_3v3_sch(self):
        mpa, mpb, mna, mnb = dev.nand2_fets("", "A", "B", "Y", "VDD", "VSS")
        self.assertEqual(mpa.w_um, 2.5)
        self.assertEqual(mpb.w_um, 2.5)
        self.assertEqual(mna.w_um, 2.0)
        self.assertEqual(mnb.w_um, 2.0)
        # Series NMOS stack: MNA drain=Y, MNA source=NMID=MNB drain, MNB source=VSS.
        self.assertEqual(mna.d, "Y")
        self.assertEqual(mna.s, mnb.d)
        self.assertEqual(mnb.s, "VSS")

    def test_schmitt_fets_matches_schmitt_3v3_sch(self):
        mp1, mp2, mp3, mn1, mn2, mn3 = dev.schmitt_fets("", "A", "Y", "VDD", "VSS")
        self.assertEqual([f.w_um for f in (mp1, mp2, mp3)], [2.5, 2.5, 1.2])
        self.assertEqual([f.w_um for f in (mn1, mn2, mn3)], [1.0, 1.0, 0.5])
        # Feedback devices: MP3 gated by Y, taps P1; MN3 gated by Y, taps N1.
        self.assertEqual(mp3.g, "Y")
        self.assertEqual(mp3.s, mp1.d)
        self.assertEqual(mn3.g, "Y")
        self.assertEqual(mn3.s, mn1.d)

    def test_lock_detector_own_devices_match_lock_detector_sch(self):
        # XMDNW VWIN WIDE VSS VSS nfet_03v3 L=0.5u W=2u
        mdnw = dev.mdnw_fet("VWIN", "WIDE", "VSS")
        self.assertEqual((mdnw.kind, mdnw.w_um, mdnw.l_um), ("nfet", 2.0, 0.5))
        self.assertEqual((mdnw.d, mdnw.g, mdnw.s), ("VWIN", "WIDE", "VSS"))

        # XMUPW VWIN VSS VDD VDD pfet_03v3 L=20u W=0.22u
        mupw = dev.mupw_fet("VWIN", "VDD", "VSS")
        self.assertEqual((mupw.kind, mupw.w_um, mupw.l_um), ("pfet", 0.22, 20.0))
        self.assertEqual((mupw.d, mupw.g, mupw.s), ("VWIN", "VSS", "VDD"))

        # XMCW VSS VWIN VSS VSS nfet_03v3 L=6u W=30u
        mcw = dev.mcw_fet("VWIN", "VSS")
        self.assertEqual((mcw.kind, mcw.w_um, mcw.l_um), ("nfet", 30.0, 6.0))
        self.assertEqual((mcw.g,), ("VWIN",))

    def test_all_devices_are_the_3v3_thick_oxide_flavour(self):
        # DR-002 Decision 3: only nfet_03v3/pfet_03v3 anywhere in this design.
        fets = [
            *dev.inv_fets("", "A", "Y", "VDD", "VSS"),
            *dev.nand2_fets("", "A", "B", "Y", "VDD", "VSS"),
            *dev.schmitt_fets("", "A", "Y", "VDD", "VSS"),
            dev.moscap_fet("MC", 8.0, 2.0, "D1", "VSS"),
            dev.mdnw_fet("VWIN", "WIDE", "VSS"),
            dev.mupw_fet("VWIN", "VDD", "VSS"),
            dev.mcw_fet("VWIN", "VSS"),
        ]
        for fet in fets:
            self.assertIn(fet.kind, ("nfet", "pfet"), fet.name)
            self.assertGreater(fet.w_um, 0, fet.name)
            self.assertGreater(fet.l_um, 0, fet.name)


@unittest.skipUnless(NETLIST_PATH.exists(), "design/netlist/lock_detector.spice not generated")
class NetlistCrossCheckTests(unittest.TestCase):
    """Confirms the committed netlist export still contains the exact SPICE
    lines ``devices.py``'s docstrings quote -- catches the netlist silently
    drifting out from under this hand-transcribed table."""

    def setUp(self):
        self.netlist = NETLIST_PATH.read_text()

    def test_mupw_line_present(self):
        self.assertIn("XMUPW VWIN VSS VDD VDD pfet_03v3 L=20u W=0.22u", self.netlist)

    def test_mdnw_line_present(self):
        self.assertIn("XMDNW VWIN WIDE VSS VSS nfet_03v3 L=0.5u W=2u", self.netlist)

    def test_mcw_line_present(self):
        self.assertIn("XMCW VSS VWIN VSS VSS nfet_03v3 L=6u W=30u", self.netlist)

    def test_top_level_lock_detector_subckt_present(self):
        self.assertIn(".subckt lock_detector UP DN LOCK VWIN VDD VSS", self.netlist)


class NarrowDeviceDogboneTests(unittest.TestCase):
    """``MUPW`` (W=0.22u) is narrower than a S/D contact can legally fit
    inside at uniform comp height -- see ``primitives.mosfet()``'s
    ``term_w``/dog-bone handling and klayout-tools#1574."""

    def test_mupw_width_is_below_the_uniform_contact_fit_floor(self):
        mupw = dev.mupw_fet("VWIN", "VDD", "VSS")
        self.assertLess(mupw.w_um, primitives.MIN_UNIFORM_TERM_W_UM)

    def test_min_uniform_term_w_matches_its_own_derivation(self):
        expected = primitives.CONTACT_SIZE_UM + 2 * primitives.CONTACT_ROW_MARGIN_UM
        self.assertAlmostEqual(primitives.MIN_UNIFORM_TERM_W_UM, expected)

    def test_narrow_term_w_clears_the_uniform_floor(self):
        self.assertGreaterEqual(primitives.NARROW_TERM_W_UM, primitives.MIN_UNIFORM_TERM_W_UM)

    def test_every_other_device_in_this_design_clears_the_uniform_floor(self):
        # MUPW is the *only* sub-floor device in this design -- every other
        # generator's own devices must stay >= the floor, or the dog-bone
        # path (currently only exercised by MUPW) would be silently doing
        # more work than this evidence's DRC run actually proves.
        fets = [
            *dev.inv_fets("", "A", "Y", "VDD", "VSS"),
            *dev.nand2_fets("", "A", "B", "Y", "VDD", "VSS"),
            *dev.schmitt_fets("", "A", "Y", "VDD", "VSS"),
            dev.moscap_fet("MC", 8.0, 2.0, "D1", "VSS"),
            dev.mdnw_fet("VWIN", "WIDE", "VSS"),
            dev.mcw_fet("VWIN", "VSS"),
        ]
        for fet in fets:
            self.assertGreaterEqual(fet.w_um, primitives.MIN_UNIFORM_TERM_W_UM, fet.name)


if __name__ == "__main__":
    unittest.main()
