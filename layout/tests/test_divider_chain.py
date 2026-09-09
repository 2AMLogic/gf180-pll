#!/usr/bin/env python3
"""Smoke tests for the assembled ``divider_chain`` block (issue #310, Part 5/final of #295).

Same convention as ``test_divider_div23.py``: the geometry-building tests need
``klayout.db`` importable and are skipped (not failed) without it, so a
PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks) see ``layout/evidence/divider-chain-layout/PROOF.md``. What this
file checks is the set of structural properties #295/#310's acceptance criteria
name, which the decks do *not* check on their own:

* the six ``div23_cell`` instances are laid out **identically** -- #295's
  "one-symbol substitution point for a future TSPC/E-TSPC single-cell swap";
* the block's supply domain is ``VDD_DIV`` **only**, never sharing a net with
  ``VDD``/``VDD_VCO``;
* the instance/net wiring matches ``design/netlist/divider_chain.spice``'s own
  X-instance list, independently of ``divider_chain.py``'s own source.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

try:
    import klayout.db as db

    _HAVE_KLAYOUT = True
except ImportError:
    _HAVE_KLAYOUT = False

from divider_chain import devgen, div23_cell, divider_chain  # noqa: E402

#: design/netlist/divider_chain.spice's own XD0..XD5 argument order --
#: (CKIN, MODIN, P, CKOUT, MODOUT), transcribed here independently of
#: divider_chain.py's own _DIV23_NET_MAP so the two can be cross-checked.
_EXPECTED_DIV23_WIRING = (
    ("VCO", "MI0", "P0", "CK1", "MO0"),
    ("CK1", "MI1", "P1", "CK2", "MO1"),
    ("CK2", "MI2", "P2", "CK3", "MO2"),
    ("CK3", "MI3", "P3", "CK4", "MO3"),
    ("CK4", "MI4", "P4", "CK5", "MO4"),
    ("CK5", "SEL5", "P5", "CK6", "MO5"),
)

#: Device layers -- the ones a div23_cell instance's own geometry lands on.
#: The block's top-level routing fabric adds only metal2/via1/via2/metal3
#: (see divider_chain.py's "ROUTING THE SIX INSTANCES' BOUNDARY PINS"), so
#: these layers inside an instance's own window are untouched by it and can be
#: compared instance-to-instance directly.
_DEVICE_LAYERS = ("comp", "poly2", "nplus", "pplus", "nwell", "contact", "metal1")


class WiringTableTests(unittest.TestCase):
    """No KLayout needed -- the instance/net tables are plain data."""

    def test_div23_net_map_matches_the_generated_netlist(self):
        self.assertEqual(len(divider_chain._DIV23_NET_MAP), 6)
        for i, expected in enumerate(_EXPECTED_DIV23_WIRING):
            m = divider_chain._DIV23_NET_MAP[i]
            got = (m["CKIN"], m["MODIN"], m["P"], m["CKOUT"], m["MODOUT"])
            self.assertEqual(got, expected, f"XD{i} wiring")

    def test_chain_is_serial_vco_to_ck6(self):
        """VCO -> CK1 -> ... -> CK6: each instance's CKOUT is the next's CKIN."""
        maps = divider_chain._DIV23_NET_MAP
        self.assertEqual(maps[0]["CKIN"], "VCO")
        for i in range(5):
            self.assertEqual(maps[i]["CKOUT"], maps[i + 1]["CKIN"], f"XD{i} -> XD{i+1}")
        self.assertEqual(maps[5]["CKOUT"], "CK6")

    def test_boundary_nets_match_the_subckt_header(self):
        # .subckt divider_chain VCO P0..P5 SEL0..SEL5 DIVOUT FB VDD_DIV VSS
        self.assertEqual(
            divider_chain.BOUNDARY_NETS,
            ("VCO",)
            + tuple(f"P{i}" for i in range(6))
            + tuple(f"SEL{i}" for i in range(6))
            + ("DIVOUT", "FB", "VDD_DIV", "VSS"),
        )


class ReferenceNetlistTests(unittest.TestCase):
    """The flattened LVS reference -- device counts and supply-domain purity."""

    def setUp(self):
        self.devices = [
            line for line in divider_chain.reference_netlist().splitlines() if line.startswith("M_")
        ]

    def test_total_device_count_is_452(self):
        # 6 x 60 (div23_cell) + 92 glue = 452, per #310's own scope statement.
        self.assertEqual(len(self.devices), 452)

    def test_each_div23_instance_contributes_exactly_sixty_devices(self):
        for i in range(6):
            n = sum(1 for line in self.devices if line.startswith(f"M_XD{i}_"))
            self.assertEqual(n, 60, f"XD{i} device count")

    def test_glue_logic_contributes_ninety_two_devices(self):
        n = sum(1 for line in self.devices if not line.startswith(("M_XD0_", "M_XD1_", "M_XD2_", "M_XD3_", "M_XD4_", "M_XD5_")))
        self.assertEqual(n, 92)

    def test_the_only_supply_net_is_vdd_div(self):
        """#310 AC: own VDD_DIV domain, never sharing a segment with VDD/VDD_VCO.

        Enforced here by construction rather than by inspection: if the block
        contains no VDD/VDD_VCO net at all, no routing of its can merge with
        one. Every device terminal in the flattened reference is checked.
        """
        nets = set()
        for line in self.devices:
            nets.update(line.split()[1:5])  # D G S B
        supplies = {n for n in nets if n.startswith("VDD") or n.startswith("GND")}
        self.assertEqual(supplies, {"VDD_DIV"}, f"unexpected supply nets: {sorted(supplies)}")
        self.assertNotIn("VDD", nets)
        self.assertNotIn("VDD_VCO", nets)

    def test_retiming_flop_is_clocked_on_vco_and_drives_fb(self):
        # XFRT: dff_tg_3v3(D=DIVOUT, CK=VCO, Q=FB) -- PLL-FLOORPLAN.md section 4.
        frt = [line for line in self.devices if line.startswith("M_XFRT_")]
        self.assertTrue(frt, "no XFRT devices in the reference netlist")
        nets = set()
        for line in frt:
            nets.update(line.split()[1:5])
        for net in ("DIVOUT", "VCO", "FB"):
            self.assertIn(net, nets, f"XFRT does not touch {net}")


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.div23 = div23_cell.build()
        cls.layout = divider_chain.build()

    def test_footprint_is_stable_and_positive(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0)
        self.assertGreater(y1 - y0, 0)
        # The number layout/floorplan/skeleton.py records for DIVIDER_LOCK and
        # layout/evidence/divider-chain-layout/PROOF-track-packing.md states
        # (issue #341: devgen.pack_tracks() reused this block's own top-level
        # Metal2 tracks across non-colliding nets instead of #310's original
        # one-track-per-net devgen.NetTracks scheme, cutting the block's
        # height -- the width is unchanged, still one row of 6 div23_cell
        # instances + 46 glue columns).
        self.assertAlmostEqual(x1 - x0, 2634.28, places=2)
        self.assertAlmostEqual(y1 - y0, 57.07, places=2)

    def test_every_boundary_net_has_a_pin(self):
        self.assertEqual(set(self.layout.pins), set(divider_chain.BOUNDARY_NETS))

    def test_six_div23_instances_are_laid_out_identically(self):
        """#295 AC: the six instances must be one placed cell, not six redraws.

        Checked geometrically rather than by trusting build()'s use of
        ``CellInstArray``: the top cell is flattened immediately after
        placement (so the hierarchy is gone by the time anything can inspect
        it), and what the acceptance criterion actually cares about is that
        the six *drawn results* cannot drift from each other. Each instance's
        own window is clipped out, translated back to a common origin, and
        XOR'd against the first instance's -- on every device layer. An empty
        XOR on all of them is exact geometric equality.
        """
        ly = self.layout.canvas.layout
        top = self.layout.canvas.top
        dbu_per_um = int(round(1.0 / ly.dbu))
        width_um = self.div23.footprint[2] - self.div23.footprint[0]
        step = int(round((width_um + divider_chain.DIV23_GAP_X_UM) * dbu_per_um))
        window_w = int(round(width_um * dbu_per_um))
        tall = 10**7  # comfortably past the block's own y extent, in dbu

        for name in _DEVICE_LAYERS:
            li = ly.layer(*devgen.LAYER[name])
            full = db.Region(top.begin_shapes_rec(li))
            reference = None
            for i in range(6):
                clip = db.Region(db.Box(i * step, -tall, i * step + window_w, tall))
                region = (full & clip).transformed(db.Trans(db.Vector(-i * step, 0)))
                region.merge()
                if reference is None:
                    reference = region
                    self.assertFalse(
                        reference.is_empty(), f"instance 0 drew nothing on layer {name}"
                    )
                else:
                    self.assertTrue(
                        (region ^ reference).is_empty(),
                        f"div23_cell instance {i} differs from instance 0 on layer {name}",
                    )

    def test_glue_logic_sits_clear_of_the_last_div23_instance(self):
        width_um = self.div23.footprint[2] - self.div23.footprint[0]
        last_instance_right = 5 * (width_um + divider_chain.DIV23_GAP_X_UM) + width_um
        self.assertGreaterEqual(divider_chain.GLUE_GAP_X_UM, 1.4)  # NW.2b nwell-to-nwell
        self.assertLess(last_instance_right, self.layout.footprint[2])


if __name__ == "__main__":
    unittest.main()
