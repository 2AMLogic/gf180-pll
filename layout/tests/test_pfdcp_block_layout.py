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

    @staticmethod
    def _placed(box, offset):
        dx, dy = offset
        return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)

    def test_footprint_encloses_both_pfd_and_cp(self):
        fx0, fy0, fx1, fy1 = self.layout.footprint
        boxes = (
            self._placed(self.layout.pfd.footprint(), self.layout.pfd_offset),
            self._placed(self.layout.cp.footprint, self.layout.cp_offset),
        )
        for box in boxes:
            self.assertLessEqual(fx0, box[0])
            self.assertLessEqual(fy0, box[1])
            self.assertGreaterEqual(fx1, box[2])
            self.assertGreaterEqual(fy1, box[3])

    def test_boundary_pin_set_is_exactly_the_thirteen_declared(self):
        self.assertEqual(set(self.layout.pins), set(block.BOUNDARY_PINS))

    def test_every_boundary_pin_has_exactly_one_landing_pad(self):
        for net in block.BOUNDARY_PINS:
            self.assertEqual(len(self.layout.pins[net]), 1, f"{net}: {self.layout.pins[net]}")

    def test_cp_placed_at_the_origin(self):
        # Since issue #455's fold it is `cp`, not `pfd`, that lands at a zero
        # offset -- so every coordinate cp.py itself records (footprint, pins,
        # backbone_rows, stage.glue_bus) stays valid unmodified in this
        # block's own frame. Same invariant cp.py's own build() holds for
        # cp_output_stage.
        self.assertEqual(self.layout.cp_offset, (0.0, 0.0))

    def test_the_fold_puts_pfd_inside_cps_own_extent(self):
        # Issue #455 lever 1: pfd is placed in the empty band above
        # cp_dumpbuf rather than beside cp, so the block's own bounding box
        # is cp's own bounding box (plus this block's four trunk rows). If
        # pfd ever stopped fitting there the fold would silently grow the
        # block instead of shrinking it -- build() raises in that case; this
        # asserts the property that makes the saving real.
        pfd_box = self._placed(self.layout.pfd.footprint(), self.layout.pfd_offset)
        cp_box = self._placed(self.layout.cp.footprint, self.layout.cp_offset)
        self.assertLessEqual(pfd_box[2], cp_box[2])
        self.assertLessEqual(pfd_box[3], cp_box[3])
        self.assertEqual(self.layout.footprint[2] - self.layout.footprint[0],
                         cp_box[2] - cp_box[0])

    def test_pfd_sits_clear_above_cp_dumpbuf(self):
        # The band pfd folds into is the one above cp_dumpbuf: pfd's own
        # bottom must clear cp_dumpbuf's own topmost drawn edge by at least
        # BLOCK_GAP_UM, and its left edge must clear everything cp itself
        # draws above that edge (its backbone trunk rows and their
        # dumpbuf-side Metal3 risers) by the same margin.
        pfd_box = self._placed(self.layout.pfd.footprint(), self.layout.pfd_offset)
        dumpbuf_top = self.layout.cp.dumpbuf.footprint[3] + self.layout.cp.dumpbuf_offset[1]
        self.assertGreaterEqual(pfd_box[1] - dumpbuf_top, block.BLOCK_GAP_UM - 1e-9)
        self.assertGreater(pfd_box[0], self.layout.cp.stage.footprint[2])

    def test_four_distinct_trunk_rows_are_used(self):
        rows = self.layout.trunk_rows
        self.assertEqual(set(rows), {"UP", "DN", "VDD", "VSS"})
        ys = sorted(rows.values())
        for a, b in zip(ys, ys[1:]):
            self.assertAlmostEqual(b - a, block.BACKBONE_PITCH_UM)

    def test_trunk_rows_continue_cps_own_backbone_band_at_cps_own_pitch(self):
        # Issue #455 lever 2, at the only level this block owns any track at
        # all: its four trunk rows are the next four rows of cp's own Metal2
        # backbone band, not a fresh band a full BACKBONE_MARGIN_UM above it.
        # Four rows still above every row cp drew (no two nets share a row),
        # and the lowest of them exactly one track pitch above cp's highest.
        cp_rows = sorted(y + self.layout.cp_offset[1] for y in self.layout.cp.backbone_rows.values())
        ours = sorted(self.layout.trunk_rows.values())
        self.assertGreater(ours[0], cp_rows[-1])
        self.assertAlmostEqual(ours[0] - cp_rows[-1], block.BACKBONE_PITCH_UM)

    def test_trunk_rows_sit_above_both_placed_blocks_drawn_geometry(self):
        pfd_top = self._placed(self.layout.pfd.footprint(), self.layout.pfd_offset)[3]
        for y in self.layout.trunk_rows.values():
            self.assertGreaterEqual(y, pfd_top + block.BACKBONE_MARGIN_UM - 1e-9)

    def test_the_trunk_band_uses_the_metal2_track_pitch_not_the_riser_column_pitch(self):
        # A trunk row is a horizontal Metal2 strip; the pitch two of them
        # need is the Metal2 track pitch (0.75 um), not cp_array's minimum
        # Metal3 *riser column* X pitch (1.0 um), which is what both this
        # module and cp.py used before issue #455. Asserted so the two
        # constants cannot silently drift back apart.
        from pfd_cp import cp_array  # noqa: PLC0415

        self.assertEqual(block.BACKBONE_PITCH_UM, cp_array.METAL2_TRACK_PITCH_UM)
        self.assertEqual(block.BACKBONE_PITCH_UM, block.cp.BACKBONE_PITCH_UM)


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


class ReferenceNetlistTests(unittest.TestCase):
    """``block.reference_netlist()`` (issue #440) -- pure Python, no
    ``klayout.db`` needed: it only reads and flattens the frozen per-record
    schematic export text (``harness.spice_flatten``)."""

    def test_export_is_frozen_under_this_blocks_own_evidence_directory(self):
        self.assertTrue(
            block.SCHEMATIC_EXPORT_PATH.exists(),
            f"{block.SCHEMATIC_EXPORT_PATH} -- regenerate with "
            "`./design/netlist.sh --top pfd_cp <tmpdir>` and freeze "
            "<tmpdir>/dut.spice at this path",
        )

    def test_top_level_ports_match_boundary_pins_in_the_frozen_exports_own_order(self):
        ref = block.reference_netlist()
        self.assertEqual(
            ref.splitlines()[0],
            ".subckt pfd_cp REF FB B0 B1 IBN ICN IBP ICP VOUT UP DN VDD VSS",
        )
        self.assertEqual(set(block.BOUNDARY_PINS), {"REF", "FB", "B0", "B1", "IBN", "ICN", "IBP", "ICP", "VOUT", "UP", "DN", "VDD", "VSS"})

    def test_device_count_matches_the_nine_subckt_hierarchy(self):
        # pfd: 40 pfdcp_inv_3v3 (2 fets) + 7 pfdcp_nand2_3v3 (4 fets) = 108.
        # cp: 4 discrete bias fets + 4 pfdcp_inv_3v3 (8) + 4 cp_leg_n (16) +
        # 4 cp_leg_p (16) + 6 discrete switch/dump fets + cp_dumpbuf (10) =
        # 60. Total 168 -- see design/pfd_cp.sch's own hierarchy (frozen at
        # SCHEMATIC_EXPORT_PATH) and this module's own reference_netlist()
        # docstring.
        ref = block.reference_netlist()
        device_lines = [l for l in ref.splitlines() if l.startswith("M_")]
        self.assertEqual(len(device_lines), 168)

    def test_ends_the_subckt(self):
        ref = block.reference_netlist()
        self.assertEqual(ref.splitlines()[-1], ".ends")


#: This block's own evidence directory (issue #386, LVS claim at #440/#448).
EVIDENCE_DIR = LAYOUT_DIR / "evidence" / "pfd-cp-layout"

#: ``run_lvs.py``'s own match verdict, verbatim. The same substring
#: ``layout/lib/check-layout-status-claims.sh`` greps for when it decides
#: whether this block counts as LVS-matched in README.md / the Challenge #5
#: proposal -- asserted here too so the two cannot drift apart silently.
LVS_MATCH_VERDICT = "Congratulations! Netlists match."


class LvsEvidenceTests(unittest.TestCase):
    """The committed block-level LVS record (issue #440).

    Pure file inspection -- no PDK, no KLayout. Re-running the deck is
    ``layout/run_pv.py lvs``'s job and is recorded in ``PROOF.md``; what
    these tests defend is that the *recorded* verdict stays in the tree and
    stays a match, so a later change that quietly breaks this block's LVS
    cannot leave a stale "matched" claim standing in two status documents.
    """

    def test_lvs_clean_directory_exists(self):
        self.assertTrue(
            (EVIDENCE_DIR / "lvs-clean").is_dir(),
            f"{EVIDENCE_DIR / 'lvs-clean'} -- the deck output for this "
            "block's LVS claim; see PROOF.md for the exact invocation",
        )

    def test_the_recorded_deck_log_reports_a_match(self):
        log = EVIDENCE_DIR / "lvs-clean" / "lvs.stdout.log"
        self.assertTrue(log.is_file(), f"{log} missing")
        self.assertIn(LVS_MATCH_VERDICT, log.read_text())

    def test_the_recorded_deck_log_reports_no_mismatch(self):
        log = EVIDENCE_DIR / "lvs-clean" / "lvs.stdout.log"
        self.assertNotIn("Netlists don't match", log.read_text())

    def test_the_run_committed_its_reference_extracted_and_database_files(self):
        for name in ("pfd_cp.spice", "pfd_cp.cir", "pfd_cp.lvsdb"):
            with self.subTest(name=name):
                self.assertTrue((EVIDENCE_DIR / "lvs-clean" / name).is_file())

    def test_the_committed_reference_is_what_reference_netlist_produces_today(self):
        committed = (EVIDENCE_DIR / "lvs-clean" / "pfd_cp.spice").read_text()
        self.assertEqual(committed, block.reference_netlist())

    def test_the_first_runs_recorded_mismatch_is_kept_not_deleted(self):
        # Evidence here is append-only: the mismatch this block's first
        # block-level LVS run actually found stays committed under
        # lvs-attempt/ beside the match that superseded it.
        attempt = EVIDENCE_DIR / "lvs-attempt" / "lvs.stdout.log"
        self.assertTrue(attempt.is_file(), f"{attempt} -- do not delete")
        self.assertIn("Netlists don't match", attempt.read_text())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not available")
class PinLabelTests(unittest.TestCase):
    """Exactly one label per boundary net, on the right *purpose* layer.

    This is the class of defect issue #440's first LVS run exposed, and
    neither half of it is visible to DRC or to ``netcheck.py``:

    * a label inherited from a flattened sub-block names a net that the
      assembling level has since re-tied to something else (``ENB`` riding
      on this block's ground rail, which broke the deck's substrate global
      net merge and mismatched all 84 n-channel bulks); and
    * a Metal2-geometry pin labelled on Metal1's pin purpose (34/10)
      attaches to whatever unrelated Metal1 lies under it -- ``UP`` and
      ``DN`` both landed on ``pfd``'s ``RB`` bus that way.

    Both are *naming* faults on correct geometry, so they can only be
    caught by looking at the labels themselves.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.layout = block.build()
        cls.tmp = tempfile.TemporaryDirectory()
        gds = Path(cls.tmp.name) / "pfd_cp.gds"
        cls.layout.write_gds(gds)
        cls.ly = db.Layout()
        cls.ly.read(str(gds))
        cls.top = cls.ly.top_cell()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _texts(self, layer: int, datatype: int) -> list[str]:
        index = self.ly.find_layer(layer, datatype)
        if index is None:
            return []
        return sorted(
            it.shape().text.string
            for it in self.top.begin_shapes_rec(index)
            if it.shape().is_text()
        )

    def test_metal1_pin_labels_are_exactly_the_non_bridged_boundary_pins(self):
        expected = sorted(set(block.BOUNDARY_PINS) - set(block.BRIDGED_NETS))
        self.assertEqual(self._texts(34, 10), expected)

    def test_up_and_dn_are_labelled_on_the_metal2_pin_purpose(self):
        # Their pin geometry is pfd's own Metal2 bus, so 36/10 is the only
        # purpose that attaches the name to the right net.
        self.assertEqual(self._texts(36, 10), sorted(block.BRIDGED_NETS))

    def test_every_boundary_pin_is_labelled_exactly_once(self):
        all_texts = self._texts(34, 10) + self._texts(36, 10)
        self.assertEqual(sorted(all_texts), sorted(block.BOUNDARY_PINS))
        self.assertEqual(len(all_texts), len(set(all_texts)))

    def test_no_sub_block_local_port_name_survives_the_flattening(self):
        # A sample of names that are real ports one level down and are NOT
        # this block's own nets: every one of these was present in the drawn
        # GDS before issue #440, and `ENB` on the ground rail is the one
        # that actually broke LVS.
        inherited = {"EN", "ENB", "VBN", "VBP", "VCASCN", "VCASCP", "TAIL", "UPT", "DNT", "VREF", "B0B", "B1B"}
        present = set(self._texts(34, 10) + self._texts(36, 10))
        self.assertEqual(present & inherited, set())


if __name__ == "__main__":
    unittest.main()
