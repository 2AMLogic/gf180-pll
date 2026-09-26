#!/usr/bin/env python3
"""Unit tests for ``layout/harness/area.py`` -- the block area audit (issue #442).

An audit that only ever runs against the real tree, where its answers cannot
be checked by hand, proves nothing. So the geometric tests below drive
:func:`harness.area.audit_gds` against *synthetic* layouts whose decomposition
is known by construction -- a known bbox, a known diffusion band, a known
number of Metal2 tracks -- and only then assert the one property of the real
committed blocks that this issue's whole argument rests on:

    the divider chain's diffusion is a small share of its bounding box, so a
    shared-diffusion lever cannot be worth more than ~1 % of the block.

If a future geometry change falsifies that, the floorplan's §5.5 reasoning
needs re-deriving, and this test is what says so. (The share itself is a
moving number and deliberately not the assertion: it was ~1.46 % when #442
measured it and is 2.44 % since #458 took 40 % of the *bbox* out without
touching a device. What §5.5 rests on is that it is nowhere near the bulk of
the block.)

:func:`harness.area.series_junction_census` needs no KLayout at all (it reads
SPICE text), so its tests always run.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _env import HAVE_KLAYOUT, LAYOUT_DIR

if HAVE_KLAYOUT:
    import klayout.db as db

from floorplan import skeleton  # noqa: E402
from harness import area  # noqa: E402

EVIDENCE = LAYOUT_DIR / "evidence"


def _write_gds(path: Path, shapes: list[tuple[str, float, float, float, float]]) -> None:
    """Write a one-cell GDS containing ``(layer_name, x0, y0, x1, y1)`` boxes."""
    layout = db.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("synthetic")
    for lname, x0, y0, x1, y1 in shapes:
        li = layout.layer(*area.LAYERS[lname])
        top.shapes(li).insert(
            db.Box(
                int(round(x0 / layout.dbu)),
                int(round(y0 / layout.dbu)),
                int(round(x1 / layout.dbu)),
                int(round(y1 / layout.dbu)),
            )
        )
    layout.write(str(path))


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class SyntheticGeometryTests(unittest.TestCase):
    """Known-answer tests: every figure below is arithmetic on the boxes written."""

    def _audit(self, shapes):
        with tempfile.TemporaryDirectory() as tmp:
            gds = Path(tmp) / "synthetic.gds"
            _write_gds(gds, shapes)
            return area.audit_gds(gds)

    def test_fill_and_whitespace_are_the_bbox_minus_the_drawn_union(self):
        # A 100 x 10 bbox holding one 10 x 10 comp box: 100 um2 of 1000.
        a = self._audit([("comp", 0, 0, 10, 10), ("comp", 90, 0, 100, 10)])
        self.assertAlmostEqual(a.width_um, 100.0, places=6)
        self.assertAlmostEqual(a.height_um, 10.0, places=6)
        self.assertAlmostEqual(a.bbox_um2, 1000.0, places=6)
        self.assertAlmostEqual(a.drawn_um2, 200.0, places=6)
        self.assertAlmostEqual(a.fill_pct, 20.0, places=6)
        self.assertAlmostEqual(a.whitespace_um2, 800.0, places=6)

    def test_overlapping_shapes_on_one_layer_are_not_double_counted(self):
        # Two 10 x 10 boxes overlapping by 5 x 10 -> 150 um2, not 200.
        a = self._audit([("metal1", 0, 0, 10, 10), ("metal1", 5, 0, 15, 10)])
        self.assertAlmostEqual(a.layer_area_um2["metal1"], 150.0, places=6)
        self.assertAlmostEqual(a.drawn_um2, 150.0, places=6)

    def test_shapes_on_different_layers_are_not_double_counted_in_the_union(self):
        # comp and metal1 exactly coincident: 100 um2 each, 100 um2 of union.
        a = self._audit([("comp", 0, 0, 10, 10), ("metal1", 0, 0, 10, 10)])
        self.assertAlmostEqual(a.layer_area_um2["comp"], 100.0, places=6)
        self.assertAlmostEqual(a.layer_area_um2["metal1"], 100.0, places=6)
        self.assertAlmostEqual(a.drawn_um2, 100.0, places=6)

    def test_label_layers_are_not_counted_as_drawn_area(self):
        # A text label occupies no silicon. 34/10 is deliberately absent from
        # area.LAYERS, so a shape there must not move fill at all.
        with tempfile.TemporaryDirectory() as tmp:
            gds = Path(tmp) / "labelled.gds"
            layout = db.Layout()
            layout.dbu = 0.001
            top = layout.create_cell("synthetic")
            top.shapes(layout.layer(*area.LAYERS["comp"])).insert(db.Box(0, 0, 10000, 10000))
            top.shapes(layout.layer(34, 10)).insert(db.Box(0, 0, 10000, 10000))
            layout.write(str(gds))
            a = area.audit_gds(gds)
        self.assertAlmostEqual(a.drawn_um2, 100.0, places=6)

    def test_device_bands_coalesce_intra_cell_gaps_but_not_a_routing_band(self):
        # Two diffusion islands 4 um apart (the generators' own NMOS-PMOS gap)
        # must read as ONE device band; a third 30 um above must read as its own.
        a = self._audit(
            [
                ("comp", 0, 0.0, 10, 1.0),
                ("comp", 0, 5.0, 10, 6.0),
                ("comp", 0, 36.0, 10, 37.0),
            ]
        )
        self.assertEqual(
            [(round(lo, 3), round(hi, 3)) for lo, hi in a.device_bands],
            [(0.0, 6.0), (36.0, 37.0)],
        )
        self.assertAlmostEqual(a.device_band_um, 7.0, places=6)
        self.assertAlmostEqual(a.routing_band_um, 37.0 - 7.0, places=6)

    def test_metal2_track_census_counts_distinct_ys_of_horizontal_shapes_only(self):
        # Three horizontal strips, two of them at the same y (one track), plus a
        # tall riser pad that is not a track.
        a = self._audit(
            [
                ("comp", 0, 0, 100, 1),
                ("metal2", 0, 10.0, 40, 10.34),
                ("metal2", 60, 10.0, 100, 10.34),
                ("metal2", 0, 12.0, 100, 12.34),
                ("metal2", 50, 20.0, 50.34, 25.0),
            ]
        )
        self.assertEqual(a.metal2_tracks, 2)
        self.assertAlmostEqual(
            a.packed_track_floor_um, 2 * area.METAL2_TRACK_PITCH_UM, places=6
        )

    def test_metal2_over_devices_measures_only_metal2_inside_the_device_bands(self):
        # 10 um2 of Metal2 inside a 100 x 1 = 100 um2 device band -> 10 %.
        a = self._audit(
            [
                ("comp", 0, 0, 100, 1),
                ("metal2", 0, 0.0, 10, 1.0),
                ("metal2", 0, 50.0, 100, 51.0),  # in the routing band, must not count
            ]
        )
        self.assertAlmostEqual(a.device_band_area_um2, 100.0, places=6)
        self.assertAlmostEqual(a.metal2_in_device_bands_um2, 10.0, places=6)
        self.assertAlmostEqual(a.metal2_over_devices_pct, 10.0, places=6)


class SeriesJunctionCensusTests(unittest.TestCase):
    """No KLayout needed -- this reads SPICE text."""

    def _census(self, netlist: str, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ref.spice"
            path.write_text(netlist)
            return area.series_junction_census(path, **kw)

    def test_a_two_high_nmos_stack_is_one_shared_diffusion_candidate(self):
        c = self._census(
            "M_A OUT IN1 MID VSS nfet_03v3 L=0.28u W=3u\n"
            "M_B MID IN2 VSS VSS nfet_03v3 L=0.28u W=3u\n"
        )
        self.assertEqual(c.devices, 2)
        self.assertEqual(c.merges, 1)
        self.assertEqual(c.merges_by_kind, {"nfet_03v3": 1})
        # 2*(2*0.5 + 0.28) + 0.6 = 3.16 um unshared; 2*0.5 + 2*0.28 + 0.5 = 2.06
        # shared; 1.10 um saved over a 3 um device width.
        self.assertAlmostEqual(c.merge_saving_um2, 1.10 * 3.0, places=6)

    def test_a_node_that_also_drives_a_gate_is_not_a_candidate(self):
        # MID is the stack's internal node AND a third device's gate, so the
        # junction must stay contacted and the islands cannot merge.
        c = self._census(
            "M_A OUT IN1 MID VSS nfet_03v3 L=0.28u W=3u\n"
            "M_B MID IN2 VSS VSS nfet_03v3 L=0.28u W=3u\n"
            "M_C OUT2 MID VSS VSS nfet_03v3 L=0.28u W=1u\n"
            # A fourth VSS leg keeps the rail non-degenerate -- see
            # test_a_two_device_rail_is_reported_as_a_candidate_and_why below.
            "M_D OUT3 IN3 VSS VSS nfet_03v3 L=0.28u W=1u\n"
        )
        self.assertEqual(c.devices, 4)
        self.assertEqual(c.merges, 0)
        self.assertAlmostEqual(c.merge_saving_um2, 0.0, places=6)

    def test_opposite_flavour_devices_never_merge(self):
        # An nfet and a pfet cannot share a diffusion island: different implant.
        c = self._census(
            "M_A OUT IN MID VSS nfet_03v3 L=0.28u W=3u\n"
            "M_B MID IN VDD VDD pfet_03v3 L=0.28u W=5u\n"
        )
        self.assertEqual(c.merges, 0)

    def test_a_rail_shared_by_many_devices_is_not_a_candidate(self):
        c = self._census(
            "M_A O1 I1 VSS VSS nfet_03v3 L=0.28u W=1u\n"
            "M_B O2 I2 VSS VSS nfet_03v3 L=0.28u W=1u\n"
            "M_C O3 I3 VSS VSS nfet_03v3 L=0.28u W=1u\n"
        )
        self.assertEqual(c.merges, 0)

    def test_a_two_device_rail_is_reported_as_a_candidate_and_why(self):
        """The census's criterion is structural, not name-based. This pins the
        one consequence of that a reader could mistake for a defect.

        Two devices whose sources both land on the same net -- even a *supply*
        net -- really can share one diffusion island (abutted source sharing),
        so reporting it is correct rather than a false positive. It matters
        only in a toy netlist: in ``divider_chain.spice`` VSS and VDD_DIV each
        touch hundreds of terminals, so the "exactly two" test excludes them
        and every candidate found there is an internal series node.
        """
        c = self._census(
            "M_A O1 I1 VSS VSS nfet_03v3 L=0.28u W=1u\n"
            "M_B O2 I2 VSS VSS nfet_03v3 L=0.28u W=1u\n"
        )
        self.assertEqual(c.merges, 1)

    def test_w_before_l_and_l_before_w_parse_identically(self):
        # divider_chain.spice contains both orders (the div23_cell bodies write
        # L= first, the glue-logic bodies W= first) -- a parser that only
        # handled one would silently drop a fifth of the block's devices.
        a = self._census("M_A O I VSS VSS nfet_03v3 L=0.28u W=3u\n")
        b = self._census("M_A O I VSS VSS nfet_03v3 W=3u L=0.28u\n")
        self.assertEqual((a.devices, a.gate_area_um2), (b.devices, b.gate_area_um2))
        self.assertEqual(a.devices, 1)

    def test_comment_and_directive_lines_are_ignored(self):
        c = self._census(
            "* a comment mentioning nfet_03v3\n"
            ".subckt thing A B\n"
            "M_A O I VSS VSS nfet_03v3 L=0.28u W=3u\n"
            ".ends\n"
        )
        self.assertEqual(c.devices, 1)


class CommittedBlockTests(unittest.TestCase):
    """The load-bearing facts §5.5 of PLL-FLOORPLAN.md reasons from."""

    def test_the_divider_chains_reference_netlist_still_has_452_devices(self):
        c = area.series_junction_census(
            EVIDENCE / "divider-chain-layout" / "divider_chain.spice"
        )
        self.assertEqual(c.devices, 452)

    def test_shared_diffusion_cannot_be_worth_1_percent_of_the_divider_chain(self):
        """§5.5's falsification of §5.3's device-density hypothesis.

        This is the assertion the floorplan's reasoning rests on: merging every
        shared-diffusion candidate in the block's own reference netlist frees
        well under 1 % of the block. If a geometry change ever makes this fail,
        §5.5 needs re-deriving -- which is the point of failing here.
        """
        c = area.series_junction_census(
            EVIDENCE / "divider-chain-layout" / "divider_chain.spice"
        )
        self.assertGreater(c.merges, 0, "no candidates at all would mean a parser break")
        block_um2 = 1317.66 * 41.99  # divider_chain's committed footprint (#458)
        self.assertLess(c.merge_saving_um2, 0.01 * block_um2)

    @unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
    def test_the_divider_chains_diffusion_is_still_a_small_share_of_its_bbox(self):
        """§5.5's falsification of the device-density hypothesis, one lever on.

        The bound was ``< 2 %`` against #454's 1317.66 x 70.29 um footprint.
        Issue #458 took 40 % of the *bbox* out without touching a single
        device, so the same unchanged diffusion is now a larger share of a
        smaller box (1.46 % -> 2.44 %) -- which is the shape a real area win
        has, not a regression. The bound is re-derived, not relaxed: what §5.5
        actually rests on is that diffusion is nowhere near the bulk of the
        block, so this stays an order of magnitude below the ~25 % a
        device-density-bound block would show.
        """
        a = area.audit_gds(EVIDENCE / "divider-chain-layout" / "divider_chain.gds")
        comp_share = 100.0 * a.layer_area_um2["comp"] / a.bbox_um2
        self.assertLess(comp_share, 5.0, f"comp is {comp_share:.2f} % of the bbox")

    @unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
    def test_the_metal2_plane_over_the_divider_chains_cells_is_now_used(self):
        """§5.5's lever 3, spent in full (issue #458).

        This assertion is the inverse of the one it replaces. §5.5 observed
        that the track band sat above the cells by *generator convention*, not
        because the plane over them was occupied -- 1.0 % Metal2 fill there --
        and named putting tracks into it as the block's last sized lever (§5.5's
        "lever 3", which §5.8 took only the packing half of).
        ``devgen.pack_tracks_over_devices()`` spends it, and the same
        measurement is now the evidence that it was spent: the plane over the
        device rows carries most of both levels' Metal2, and the no-device
        routing band is no longer the taller of the two.
        """
        a = area.audit_gds(EVIDENCE / "divider-chain-layout" / "divider_chain.gds")
        self.assertGreater(a.metal2_over_devices_pct, 10.0)
        self.assertLess(a.routing_band_um, a.device_band_um)

    @unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
    def test_every_audited_block_gds_is_readable_and_renders(self):
        import run_pv  # noqa: PLC0415 -- CLI module, imported only for its table

        audits = [
            area.audit_gds(EVIDENCE / rel, name=name)
            for name, rel, _ in run_pv.AREA_AUDIT_BLOCKS
        ]
        self.assertEqual(len(audits), 4)
        for a in audits:
            self.assertGreater(a.bbox_um2, 0.0)
            self.assertGreater(a.drawn_um2, 0.0)
            self.assertLess(a.fill_pct, 100.0)
        rendered = area.render_markdown(audits, {})
        for a in audits:
            self.assertIn(f"`{a.name}`", rendered)

    @unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
    def test_the_committed_report_still_matches_the_committed_geometry(self):
        """``layout/evidence/area-audit/area-audit.md`` is machine-rendered, never
        hand-maintained -- the same discipline ``signoff/tier-report.json`` and
        ``sim/lib/check-readme-status.sh`` enforce on their own artifacts.

        This is not a style check. ``PLL-FLOORPLAN.md`` §5.5 documents the VCO
        row drifting 634 um^2 (+2.0 %) between #324 and #433 with three
        documents still quoting the old figure, because nothing re-derived it.
        A stale area report is the same failure, and this test is what turns it
        into a red build instead of a misleading number.
        """
        import run_pv  # noqa: PLC0415

        audits = [
            area.audit_gds(EVIDENCE / rel, name=name)
            for name, rel, _ in run_pv.AREA_AUDIT_BLOCKS
        ]
        censuses = {
            name: area.series_junction_census(EVIDENCE / spice)
            for name, _, spice in run_pv.AREA_AUDIT_BLOCKS
            if spice
        }
        committed = (EVIDENCE / "area-audit" / "area-audit.md").read_text()
        self.assertEqual(
            area.render_markdown(audits, censuses),
            committed,
            "layout/evidence/area-audit/area-audit.md is stale -- regenerate with "
            "`python3 layout/run_pv.py area --out layout/evidence/area-audit/area-audit.md` "
            "and re-read PLL-FLOORPLAN.md §5.5's arithmetic against the new figures",
        )


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class WholeChipAreaRowTests(unittest.TestCase):
    """``spec/pll.md#area``'s fail-loud clause, as a check rather than a sentence.

    ``PLL-FLOORPLAN.md`` §5 has carried a "fail-loud condition for a future
    pass" in prose since it was written, and it worked -- §5.1 through §5.11
    are that clause firing, pass after pass. It fired because a human (or an
    agent) re-read it each time, which is exactly the hand-maintenance §5.5
    switched the audit away from after the VCO row drifted 634 um^2 with three
    documents still quoting the old figure.

    DR-016 (#456) amended the row to 0.30 mm^2 on the measured total. These
    two tests make that number load-bearing: the whole-chip sum is re-derived
    from the committed GDS on every run, so geometry that grows past the
    amended row is a red build, and the historical claim that the *draft*
    target was missed cannot silently stop being true either.
    """

    def _total_um2(self) -> float:
        """Loop filter + every committed block bbox, as PLL-FLOORPLAN.md §5.11 sums them."""
        import run_pv  # noqa: PLC0415 -- CLI module, imported only for its block table

        blocks = sum(
            area.audit_gds(EVIDENCE / rel, name=name).bbox_um2
            for name, rel, _ in run_pv.AREA_AUDIT_BLOCKS
        )
        return blocks + skeleton.LOOP_FILTER_AREA_UM2

    def test_the_whole_chip_total_still_meets_the_amended_area_row(self):
        total = self._total_um2()
        self.assertLessEqual(
            total,
            skeleton.AREA_BUDGET_BLOCK_SUM_UM2,
            f"summed block footprint is {total:,.0f} um^2, past the "
            f"{skeleton.AREA_BUDGET_BLOCK_SUM_UM2:,.0f} um^2 that spec/pll.md#area's "
            f"{skeleton.AREA_BUDGET_UM2 / 1e6:.2f} mm^2 row allows before "
            f"PLL-FLOORPLAN.md §5's x{skeleton.TOP_LEVEL_OVERHEAD} overhead. "
            "State the overrun in a new PLL-FLOORPLAN.md §5 revision and amend the "
            "spec row through a decision record -- do not re-derive the budget to fit",
        )

    def test_the_draft_015_mm2_target_is_still_missed_as_DR_016_records(self):
        """The other direction: DR-016's whole argument is that 0.15 mm^2 is not
        reachable. If a future reduction pass ever gets there, that record is
        superseded and this test is where it says so.
        """
        total = self._total_um2() * skeleton.TOP_LEVEL_OVERHEAD
        self.assertGreater(
            total,
            skeleton.AREA_BUDGET_DRAFT_UM2,
            f"the whole-chip total is now {total:,.0f} um^2, inside the draft "
            "0.15 mm^2 target DR-016 amended away -- write the successor record "
            "amending spec/pll.md#area back down, and update PLL-FLOORPLAN.md §5.11",
        )


if __name__ == "__main__":
    unittest.main()
