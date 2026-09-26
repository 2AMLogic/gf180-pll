#!/usr/bin/env python3
"""Tests for ``cp`` -- the complete charge pump: ``cp_output_stage``
(#321) assembled with ``cp_dumpbuf`` (#302) per ``design/cp.sch``'s own
``xbuf`` instance (issue #385, Part 5a of #294/#303).

Same convention as ``test_cp_output_stage.py``: the ``klayout.db``-dependent
tests are skipped, not failed, when ``klayout.db`` is unavailable, so a
PDK/PV-less checkout still collects this file cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the DRC-clean claim (which additionally needs the PDK's own signoff
deck) see ``layout/evidence/cp-block-layout/PROOF.md``. What this file
checks is (a) the net map and boundary-pin set really do match
``design/cp.sch``, and (b) -- where ``klayout.db`` is importable -- the
finished GDS's own extracted Metal1-3 connectivity, which is the only thing
that can see a short or an open (a DRC deck cannot; see ``netcheck.py``).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _env import HAVE_KLAYOUT, LAYOUT_DIR  # noqa: F401

from pfd_cp import cp  # noqa: E402
from pfd_cp import cp_dumpbuf, netcheck  # noqa: E402
from pfd_cp import cp_output_stage as cos  # noqa: E402


class NetMapTests(unittest.TestCase):
    """NET_MAP/BOUNDARY_PINS match design/cp.sch's own xbuf instance
    (lines ~275-281) and ipin/iopin declarations (lines 24-35)."""

    def test_boundary_pins_are_the_eleven_expected(self):
        self.assertEqual(
            set(cp.BOUNDARY_PINS),
            {"UP", "DN", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "VDD", "VSS"},
        )

    def test_vdump_is_not_a_boundary_pin(self):
        self.assertNotIn("VDUMP", cp.BOUNDARY_PINS)

    def test_boundary_pins_are_cp_output_stages_own_minus_vdump(self):
        self.assertEqual(set(cp.BOUNDARY_PINS), set(cos.BOUNDARY_PINS) - {"VDUMP"})

    def test_net_map_covers_every_cp_dumpbuf_external_net_exactly_once(self):
        dumpbuf_nets = [b for _a, b in cp.NET_MAP]
        self.assertEqual(sorted(dumpbuf_nets), sorted(cp_dumpbuf.EXTERNAL_NETS))
        self.assertEqual(len(dumpbuf_nets), len(set(dumpbuf_nets)))

    def test_net_map_stage_side_nets_are_all_real_cp_output_stage_pins(self):
        for stage_net, _dumpbuf_net in cp.NET_MAP:
            self.assertIn(stage_net, cos.BOUNDARY_PINS)

    def test_vdump_maps_to_vdump_on_both_sides(self):
        self.assertIn(("VDUMP", "VDUMP"), cp.NET_MAP)

    def test_the_four_nets_that_stay_external_are_named_in_the_net_map(self):
        stage_nets = {a for a, _b in cp.NET_MAP}
        for net in ("IBN", "IBP", "VOUT", "VDD", "VSS"):
            self.assertIn(net, stage_nets)


class NetcheckReportTests(unittest.TestCase):
    """netcheck's own plain-Python surface, re-checked here so this file
    collects cleanly even without klayout.db (same convention as
    test_cp_output_stage.py's own copy of these)."""

    def test_pad_probe_points_takes_box_centres(self):
        pts = netcheck.pad_probe_points({"A": [(0.0, 0.0, 2.0, 1.0)]})
        self.assertEqual(pts, {"A": [(1.0, 0.5)]})


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildTests(unittest.TestCase):
    """cp.build() on the real, assembled cp_output_stage + cp_dumpbuf
    geometry."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cp.build()

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = self.layout.footprint
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_encloses_both_sub_blocks(self):
        fx0, fy0, fx1, fy1 = self.layout.footprint
        dx, dy = self.layout.dumpbuf_offset
        stage_box = self.layout.stage.footprint
        from pfd_cp import cp_array

        dumpbuf_box = cp_array._translate_box(self.layout.dumpbuf.footprint, dx, dy)
        for box in (stage_box, dumpbuf_box):
            self.assertLessEqual(fx0, box[0])
            self.assertLessEqual(fy0, box[1])
            self.assertGreaterEqual(fx1, box[2])
            self.assertGreaterEqual(fy1, box[3])

    def test_the_two_sub_blocks_footprints_do_not_overlap(self):
        from pfd_cp import cp_array

        dx, dy = self.layout.dumpbuf_offset
        stage_box = self.layout.stage.footprint
        dumpbuf_box = cp_array._translate_box(self.layout.dumpbuf.footprint, dx, dy)
        self.assertLessEqual(stage_box[2], dumpbuf_box[0])

    def test_boundary_pin_set_is_exactly_the_eleven_declared(self):
        self.assertEqual(set(self.layout.pins), set(cp.BOUNDARY_PINS))

    def test_no_internal_net_is_promoted_as_a_pin(self):
        self.assertNotIn("VDUMP", self.layout.pins)
        for net in cos.INTERNAL_NETS:
            self.assertNotIn(net, self.layout.pins)

    def test_every_boundary_pin_has_exactly_one_landing_pad(self):
        for net in cp.BOUNDARY_PINS:
            self.assertEqual(len(self.layout.pins[net]), 1, f"{net}: {self.layout.pins[net]}")

    def test_every_boundary_pin_is_cp_output_stages_own_unmodified_pad(self):
        # cp_output_stage sits at a zero offset in this block's own frame
        # (module docstring), so every promoted pin must be byte-identical
        # to that sub-block's own pad.
        for net in cp.BOUNDARY_PINS:
            self.assertEqual(self.layout.pins[net], self.layout.stage.pins[net])

    def test_one_trunk_row_per_net_all_distinct(self):
        self.assertEqual(set(self.layout.backbone_rows), {a for a, _b in cp.NET_MAP})
        ys = sorted(self.layout.backbone_rows.values())
        for a, b in zip(ys, ys[1:]):
            self.assertGreaterEqual(b - a, cp.BACKBONE_PITCH_UM - 1e-9)

    def test_trunk_rows_sit_above_both_placed_footprints(self):
        from pfd_cp import cp_array

        dx, dy = self.layout.dumpbuf_offset
        dumpbuf_box = cp_array._translate_box(self.layout.dumpbuf.footprint, dx, dy)
        top = max(self.layout.stage.footprint[3], dumpbuf_box[3])
        for trunk_y in self.layout.backbone_rows.values():
            self.assertGreater(trunk_y, top)


@unittest.skipUnless(HAVE_KLAYOUT, "klayout.db not importable in this environment")
class ConnectivityTests(unittest.TestCase):
    """The finished GDS's own extracted Metal1-3 connectivity -- the only
    check that can see a short or an open (``layout/run_pv.py drc`` cannot;
    see ``netcheck.py``'s own docstring)."""

    @classmethod
    def setUpClass(cls):
        cls.layout = cp.build()
        cls._tmp = tempfile.TemporaryDirectory()
        gds = Path(cls._tmp.name) / f"{cp.TOP_CELL}.gds"
        cls.layout.write_gds(gds)
        cls.report = netcheck.check_gds(
            gds, cp.TOP_CELL, netcheck.pad_probe_points(cls.layout.probe_pads())
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

    def test_vdump_forms_exactly_one_connected_island(self):
        self.assertIn("VDUMP", self.report.components)
        self.assertEqual(len(self.report.components["VDUMP"]), 1)

    def test_vdump_does_not_reach_any_other_net(self):
        others = {net: ids for net, ids in self.report.components.items() if net != "VDUMP"}
        vdump = next(iter(self.report.components["VDUMP"]))
        for net, ids in others.items():
            self.assertNotIn(vdump, ids, f"VDUMP is shorted to {net}")

    def test_every_net_bridged_by_the_net_map_is_now_one_component(self):
        # e.g. VOUT (cp_output_stage) and VREF (cp_dumpbuf) are the same
        # physical net post-bridge -- probe_pads() already aliases
        # cp_dumpbuf's own net name onto cp_output_stage's, so this just
        # confirms every canonical net in the report resolved to metal.
        for stage_net, _dumpbuf_net in cp.NET_MAP:
            self.assertIn(stage_net, self.report.components)
            self.assertEqual(len(self.report.components[stage_net]), 1, stage_net)


if __name__ == "__main__":
    unittest.main()
