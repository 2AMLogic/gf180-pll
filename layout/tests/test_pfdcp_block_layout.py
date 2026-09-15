#!/usr/bin/env python3
"""Tests for ``pfd_cp`` -- the top-level PFD + charge-pump block: ``pfd``
(issue #300) assembled with the complete ``cp`` block (issue #385) into one
flat, standalone-DRC-clean block matching ``design/pfd_cp.sch``'s top-level
netlist (issue #386, Part 5b of #294/#303 -- the increment that actually
satisfies both issues' own acceptance criteria).

Same convention as ``test_cp_output_stage.py``: the ``klayout.db``-dependent
tests are skipped, not failed, when ``klayout.db`` is unavailable, so a
PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the DRC-clean claim (which additionally needs the PDK's own signoff
deck) see ``layout/evidence/pfd-cp-layout/PROOF.md``. What this file checks
is (a) this block's own net-map constants match ``design/pfd_cp.sch``, and
(b) -- where ``klayout.db`` is importable -- the finished GDS's own
extracted Metal1-3 connectivity, which is the only thing that can see a
short or an open (a DRC deck cannot; see ``netcheck.py``).
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

from pfd_cp import block, netcheck  # noqa: E402


class NetNamingTests(unittest.TestCase):
    """The block's own net-map constants, per design/pfd_cp.sch's own
    ipin/iopin/opin declarations (P0-P12) and its own xpfd/xcp wiring."""

    def test_boundary_pins_are_the_thirteen_expected(self):
        self.assertEqual(
            set(block.BOUNDARY_PINS),
            {
                "REF", "FB", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT",
                "UP", "DN", "VDD", "VSS",
            },
        )

    def test_boundary_pins_has_no_duplicates(self):
        self.assertEqual(len(block.BOUNDARY_PINS), len(set(block.BOUNDARY_PINS)))

    def test_bridged_nets_are_up_and_dn_only(self):
        self.assertEqual(set(block.BRIDGED_NETS), {"UP", "DN"})

    def test_rail_nets_are_vdd_and_vss_only(self):
        self.assertEqual(set(block.RAIL_NETS), {"VDD", "VSS"})

    def test_bridged_and_rail_nets_are_boundary_pins(self):
        for net in (*block.BRIDGED_NETS, *block.RAIL_NETS):
            self.assertIn(net, block.BOUNDARY_PINS)

    def test_shared_probe_net_names_matches_boundary_pins(self):
        # _SHARED_PROBE_NET_NAMES is what keeps pfd's own internal UPB/DNB
        # from merging with cp_output_stage's own unrelated internal
        # UPB/DNB under one probe key (see PfdCpLayout.probe_pads()'s own
        # docstring) -- it must be exactly this block's own boundary pins,
        # never more (a stray internal name would risk the same false-merge
        # bug) and never less (a real boundary net left out would risk a
        # false split on the two sub-blocks' own separately-drawn pads).
        self.assertEqual(block._SHARED_PROBE_NET_NAMES, frozenset(block.BOUNDARY_PINS))


class RailLandingInsetTests(unittest.TestCase):
    def test_vdd_and_vss_use_different_insets(self):
        # See RAIL_LANDING_INSET_UM's own docstring: two different pfd-side
        # landing points are required so the two nets' own Metal3 risers,
        # chosen independently, do not land on the same X column.
        self.assertNotEqual(
            block.RAIL_LANDING_INSET_UM["VDD"], block.RAIL_LANDING_INSET_UM["VSS"]
        )

    def test_insets_are_declared_for_both_rail_nets(self):
        self.assertEqual(set(block.RAIL_LANDING_INSET_UM), set(block.RAIL_NETS))


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTests(unittest.TestCase):
    """block.build() on the real pfd + cp geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = block.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_encloses_both_pfd_and_cp(self):
        fx0, fy0, fx1, fy1 = self.layout.footprint
        dx, dy = self.layout.cp_offset
        cp_box = (
            self.layout.cp.footprint[0] + dx,
            self.layout.cp.footprint[1] + dy,
            self.layout.cp.footprint[2] + dx,
            self.layout.cp.footprint[3] + dy,
        )
        for box in (self.layout.pfd.footprint(), cp_box):
            self.assertLessEqual(fx0, box[0])
            self.assertLessEqual(fy0, box[1])
            self.assertGreaterEqual(fx1, box[2])
            self.assertGreaterEqual(fy1, box[3])

    def test_boundary_pin_set_is_exactly_the_thirteen_declared(self):
        self.assertEqual(set(self.layout.pins), set(block.BOUNDARY_PINS))

    def test_every_boundary_pin_has_exactly_one_landing_pad(self):
        for net in block.BOUNDARY_PINS:
            self.assertEqual(len(self.layout.pins[net]), 1, f"{net}: {self.layout.pins[net]}")

    def test_pfd_placed_at_the_origin(self):
        # pfd's own drawn geometry is unmodified by this composition (placed
        # at a zero offset), so any coordinate pfd.py itself records stays
        # valid in this block's own frame -- same invariant cp.py's own
        # build() holds for cp_output_stage.
        self.assertEqual(self.layout.pfd.footprint(), block.pfd.build().footprint())

    def test_cp_is_placed_clear_of_pfd(self):
        dx, dy = self.layout.cp_offset
        self.assertGreater(dx, 0.0)
        cp_x0_g = self.layout.cp.footprint[0] + dx
        self.assertGreaterEqual(cp_x0_g, self.layout.pfd.footprint()[2])

    def test_four_distinct_trunk_rows_are_used(self):
        rows = self.layout.trunk_rows
        self.assertEqual(set(rows), {"UP", "DN", "VDD", "VSS"})
        ys = sorted(rows.values())
        for a, b in zip(ys, ys[1:]):
            self.assertGreaterEqual(b - a, block.BACKBONE_PITCH_UM - 1e-9)

    def test_trunk_rows_sit_above_both_placed_blocks(self):
        dx, dy = self.layout.cp_offset
        cp_top_g = self.layout.cp.footprint[3] + dy
        pfd_top = self.layout.pfd.footprint()[3]
        for y in self.layout.trunk_rows.values():
            self.assertGreaterEqual(y, max(pfd_top, cp_top_g) + block.BACKBONE_MARGIN_UM - 1e-9)


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class ConnectivityTests(unittest.TestCase):
    """The finished GDS's own extracted Metal1-3 connectivity -- the only
    check that can see a short or an open (``layout/run_pv.py drc`` cannot;
    see ``netcheck.py``'s own docstring)."""

    @classmethod
    def setUpClass(cls):
        cls.layout = block.build()
        cls._tmp = tempfile.TemporaryDirectory()
        gds = Path(cls._tmp.name) / f"{block.TOP_CELL}.gds"
        cls.layout.write_gds(gds)
        cls.report = netcheck.check_gds(
            gds, block.TOP_CELL, netcheck.pad_probe_points(cls.layout.probe_pads())
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

    def test_the_bridged_and_tied_nets_all_resolve(self):
        for net in (*block.BRIDGED_NETS, *block.RAIL_NETS):
            self.assertIn(net, self.report.components)
            self.assertEqual(len(self.report.components[net]), 1, net)

    def test_pfd_and_cp_private_internal_nets_stay_namespaced_and_distinct(self):
        # pfd's own UPB and cp_output_stage's own UPB are two unrelated
        # physical nets that happen to share a bare name -- proven distinct
        # here rather than merged into one probe key (see
        # PfdCpLayout.probe_pads()'s own docstring).
        self.assertIn("pfd.UPB", self.report.components)
        self.assertIn("cp.UPB", self.report.components)
        self.assertNotEqual(
            self.report.components["pfd.UPB"], self.report.components["cp.UPB"]
        )


if __name__ == "__main__":
    unittest.main()
