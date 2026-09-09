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
  X-instance list, independently of ``divider_chain.py``'s own source;
* ``ROW_PLAN`` (issue #344's fold) places every instance and every glue group
  exactly once -- a typo there would silently drop devices, which the DRC deck
  alone would never notice.
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

    def test_row_plan_places_every_instance_and_glue_group_exactly_once(self):
        """#344's fold: ROW_PLAN is the single placement table, so a dropped or
        duplicated entry there is a dropped or duplicated *device*.

        Checked as plain data (no KLayout needed) because neither the DRC deck
        nor LVS would flag it usefully: a missing group would just make the
        generated layout and the (independently generated) reference netlist
        disagree in a way that reads as a generic mismatch.
        """
        instances = [key for row in divider_chain.ROW_PLAN for kind, key in row if kind == "div23"]
        groups = [key for row in divider_chain.ROW_PLAN for kind, key in row if kind == "glue"]
        self.assertEqual(sorted(instances), list(range(6)))
        self.assertEqual(sorted(groups), sorted(divider_chain.GLUE_GROUPS))
        self.assertTrue(all(kind in ("div23", "glue") for row in divider_chain.ROW_PLAN for kind, _ in row))

    def test_glue_groups_together_are_the_forty_six_glue_columns(self):
        """Regrouping the glue for placement (#344) must not change the set.

        ``_glue_placements()`` is the flat union of every ``GLUE_GROUPS``
        entry; #310's own scope statement fixes that union at 46 columns / 92
        transistors, and this asserts the regrouping preserved both.
        """
        columns = divider_chain._glue_placements()
        self.assertEqual(len(columns), 46)
        devices = sum(len(col.pulldown) + len(col.pullup) for col, _ in columns)
        self.assertEqual(devices, 92)

    def test_cross_row_nets_are_derived_from_the_net_tables(self):
        """The spine's own width is a function of the net tables alone (#344).

        Every net ``spine_columns()`` reserves a column for must genuinely
        appear in more than one ``ROW_PLAN`` row, and the two supply trunks
        must always be among them (they reach every column in the block).
        """
        rows = divider_chain._row_nets()
        self.assertEqual(len(rows), len(divider_chain.ROW_PLAN))
        spine = divider_chain.spine_columns()
        for net in spine:
            self.assertGreater(sum(net in r for r in rows), 1, f"{net} does not cross a row")
        for supply in ("VDD_DIV", "VSS"):
            self.assertIn(supply, spine)
        # Distinct, ordered columns, all clear of the rows' own content (x >= 0).
        xs = sorted(spine.values())
        self.assertEqual(len(set(xs)), len(xs))
        self.assertLessEqual(max(xs), -divider_chain.SPINE_GAP_X_UM)

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
        # layout/evidence/divider-chain-layout/PROOF-fold.md states (issue
        # #344: ROW_PLAN folds the block's one row of 6 div23_cell instances +
        # 46 glue columns into two rows, each with its own
        # devgen.pack_tracks() band, on top of #341's own track packing).
        self.assertAlmostEqual(x1 - x0, 1317.66, places=2)
        self.assertAlmostEqual(y1 - y0, 100.29, places=2)

    def test_the_fold_actually_reduced_area(self):
        """#344's own edge case: a fold must *reduce* area, not just move it.

        #341's record warned that a naive pre-track-packing fold trades width
        for height at roughly constant area. The two numbers below are this
        block's own measured footprints before the fold -- 2634.28 x 93.82 um
        at #310 and 2634.28 x 57.07 um at #341 -- so this asserts the fold
        beat the *already-packed* one, not merely the original.
        """
        x0, y0, x1, y1 = self.layout.footprint
        area = (x1 - x0) * (y1 - y0)
        self.assertLess(area, 2634.28 * 57.07, "the fold did not reduce area against #341")
        self.assertLess(area, 150_000.0, "the block no longer fits the 0.15 mm^2 whole-chip target")

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

        Since issue #344's fold the six instances no longer sit on one uniform
        x step, so the windows come from ``build()``'s own recorded
        ``div23_boxes`` (each instance's as-placed bounding box) and are
        clipped in **y** as well as x -- the row above/below and this row's own
        track band all sit outside the box and must not leak in.
        """
        ly = self.layout.canvas.layout
        top = self.layout.canvas.top
        dbu_per_um = int(round(1.0 / ly.dbu))
        boxes = self.layout.div23_boxes
        self.assertEqual(len(boxes), 6)
        width_um = self.div23.footprint[2] - self.div23.footprint[0]
        height_um = self.div23.footprint[3] - self.div23.footprint[1]
        for bx in boxes:
            self.assertAlmostEqual(bx[2] - bx[0], width_um, places=3)
            self.assertAlmostEqual(bx[3] - bx[1], height_um, places=3)

        def _dbu(v):
            return int(round(v * dbu_per_um))

        for name in _DEVICE_LAYERS:
            li = ly.layer(*devgen.LAYER[name])
            full = db.Region(top.begin_shapes_rec(li))
            reference = None
            for i, (bx0, by0, bx1, by1) in enumerate(boxes):
                clip = db.Region(db.Box(_dbu(bx0), _dbu(by0), _dbu(bx1), _dbu(by1)))
                region = (full & clip).transformed(db.Trans(db.Vector(-_dbu(bx0), -_dbu(by0))))
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

    def test_every_row_holds_div23_instances_and_glue(self):
        """#344 AC: the block really is folded, not a single row in disguise."""
        self.assertGreaterEqual(len(divider_chain.ROW_PLAN), 2)
        self.assertEqual(len(self.layout.rows), len(divider_chain.ROW_PLAN))
        for r, row in enumerate(divider_chain.ROW_PLAN):
            kinds = {kind for kind, _ in row}
            self.assertEqual(kinds, {"div23", "glue"}, f"row {r} is not a mixed row")

    def test_rows_are_stacked_without_overlapping(self):
        """Each row's own drawn band must clear the next row's own bottom."""
        for lower, upper in zip(self.layout.rows, self.layout.rows[1:]):
            gap = upper[0] - lower[1]
            self.assertAlmostEqual(gap, divider_chain.ROW_GAP_Y_UM, places=3)

    def test_instances_and_glue_keep_their_placement_clearances(self):
        """The re-derived placement grid (#344) still clears NW.2b by a mile.

        ``div23_cell``'s own nwell is inset 2.12 um from its instance box's
        left edge and 0.22 um from its right (see ``DIV23_GAP_X_UM``'s own
        derivation), so two instances ``DIV23_GAP_X_UM`` apart have
        ``DIV23_GAP_X_UM + 2.34`` um between their wells.
        """
        self.assertGreaterEqual(divider_chain.DIV23_GAP_X_UM + 2.34, 1.4)  # NW.2b
        self.assertGreaterEqual(divider_chain.GLUE_GAP_X_UM, 1.4)
        # No two instance boxes may overlap.
        for i, a in enumerate(self.layout.div23_boxes):
            for b in self.layout.div23_boxes[i + 1 :]:
                disjoint = a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
                self.assertTrue(disjoint, f"div23 instance boxes overlap: {a} vs {b}")


if __name__ == "__main__":
    unittest.main()
