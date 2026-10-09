#!/usr/bin/env python3
"""Tests for the assembled top level, ``layout/pll_top/top_level/`` (issue #297).

What is pinned, and against what:

* **The routing plan is the committed netlist.** Every ``pll_top`` instance
  port in ``design/netlist/pll_top.spice`` is a terminal of exactly one routed
  net (``VWIN``, internal to ``lock_detector``, excepted), and every
  ``pll_top`` pin reaches the chip edge. No KLayout needed.
* **The five blocks are imported, not redrawn.** Each child cell of the
  assembled GDS is geometrically identical (per-layer XOR) to its own
  generator's output; the placement transforms (two mirrored, one rotated)
  land each block's labels where the transform says; a block written at a
  different database unit imports to the same micron geometry.
* **A block that is missing, or a box standing in for one, is refused** -- by
  the assembler, and independently by ``netcheck`` reading a GDS.
* **The written GDS connects what the netlist says** (``netcheck``), and the
  check is not vacuous: a cut trunk is reported as an open, a Metal5 bridge
  between two pins as a short, a riser dropped onto a block-internal net as a
  short, a bridge between two branches of the ``VSS`` star as a star failure
  (though it is electrically the same net), a non-VCO wire in the VCO
  keep-out and a top-level shape over the MIM capacitor as keep-out failures.
* **The committed GDS** passes the same check, matches the committed
  assembly report, and the evidence record states its measured area.

The foundry DRC run is recorded in ``layout/evidence/pll-top-layout/PROOF.md``,
not re-run here. Reproducibility of the committed GDS from its generator is
``test_gds_reproducibility.py``'s job (it is registered in
``harness/reproduce.py``).

    python3 -m unittest discover -s layout/tests -t layout/tests -p test_pll_top_assembly.py -v
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from _env import HAVE_KLAYOUT, LAYOUT_DIR  # noqa: F401

from pll_top.top_level import netlist as NL  # noqa: E402

EVIDENCE = LAYOUT_DIR / "evidence" / "pll-top-layout"
COMMITTED_GDS = EVIDENCE / "pll_top.gds"
COMMITTED_REPORT = EVIDENCE / "pll_top-assembly.json"
PROOF = EVIDENCE / "PROOF.md"


class PlanIsTheNetlistTests(unittest.TestCase):
    """No KLayout needed."""

    def setUp(self):
        from pll_top.top_level import assemble

        self.assemble = assemble
        self.nl = NL.read()

    def test_netlist_instances(self):
        self.assertEqual(
            sorted(i.subckt for i in self.nl.instances),
            ["divider_chain", "lock_detector", "loop_filter", "pfd_cp", "vco"],
        )
        self.assertEqual(self.nl.instance("pfd_cp").port_net()["VOUT"], "VCTRL")
        self.assertEqual(self.nl.instance("divider_chain").port_net()["VCO"], "CLK")
        self.assertEqual(self.nl.instance("pfd_cp").port_net()["B0"], "CPB0")

    def test_every_port_is_planned_once(self):
        plans = self.assemble.plan(self.nl)
        seen = [(t.block, t.port) for p in plans for t in p.terminals]
        self.assertEqual(len(seen), len(set(seen)))
        every = {(b, port) for net, ports in self.nl.terminals().items() for b, port in ports}
        self.assertEqual(every - set(seen), {("lock_detector", "VWIN")})

    def test_every_pin_reaches_an_edge(self):
        plans = self.assemble.plan(self.nl)
        edged = {p.net for p in plans if p.kind != "trunk" or p.pin}
        self.assertEqual(set(self.nl.pins) - edged, set())

    def test_star_supplies_cover_every_user(self):
        plans = {p.net: p for p in self.assemble.plan(self.nl)}
        for net in ("VDD", "VSS"):
            self.assertEqual(plans[net].kind, "star")
            self.assertEqual(
                sorted(t.block for t in plans[net].terminals),
                sorted(b for b, _ in self.nl.terminals()[net]),
            )

    def test_plan_rejects_a_netlist_it_does_not_cover(self):
        text = NL.NETLIST.read_text().replace(
            "XLD UP DN LOCK VWIN", "XLD UP DN LOCK FB"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pll_top.spice"
            p.write_text(text)
            with self.assertRaises(self.assemble.AssemblyError):
                self.assemble.plan(NL.read(p))


def _decap_gate_regions(db, gds_path):
    """Merged ``poly2 AND comp AND mos_cap_mk`` regions of one 50 x 50 um size, plus
    the layer-(0, 0) shape count -- the physical VCO decap pair, wherever it sits."""
    ly = db.Layout()
    ly.read(str(gds_path))
    top = ly.top_cell()

    def region(layer, datatype):
        return db.Region(top.begin_shapes_rec(ly.layer(layer, datatype))).merged()

    gates = region(30, 0) & region(22, 0) & region(166, 5)
    pair = [g for g in gates.each() if (g.bbox().width(), g.bbox().height()) == (50_000, 50_000)]
    placeholders = region(0, 0).count()
    return pair, placeholders


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel")
class AssembledLayoutTests(unittest.TestCase):
    """One fresh build from the generators, shared by every test below."""

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        from pll_top.top_level import assemble, netcheck

        cls.db, cls.assemble, cls.netcheck = db, assemble, netcheck
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.blocks = assemble.generate_blocks(root / "blocks")
        cls.asm = assemble.build(root / "out", block_gds=cls.blocks)
        cls.gds = cls.asm.gds
        cls.report = netcheck.check(cls.gds)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- helpers -------------------------------------------------------------

    def _mutated(self, edit) -> Path:
        """Copy of the built GDS with ``edit(layout, top)`` applied."""
        db = self.db
        ly = db.Layout()
        ly.read(str(self.gds))
        edit(ly, ly.top_cell())
        out = Path(self.tmp.name) / f"mut-{self.id().rsplit('.', 1)[-1]}.gds"
        ly.write(str(out))
        return out

    def _layer(self, ly, name):
        from pll_top.top_level import extract as X

        return ly.layer(*X.LAYER[name])

    def _top_shapes(self, ly, top, name, pred):
        return [s for s in top.shapes(self._layer(ly, name)).each() if pred(s.box)]

    def _access(self, block, port):
        return next(a for a in self.asm.accesses if a.block == block and a.port == port)

    # -- positive ------------------------------------------------------------

    def test_netcheck_ok(self):
        self.assertTrue(self.report.ok, self.report.summary())
        self.assertEqual(self.report.nets_checked, len(set(self.netcheck.NL.read().pins) | {"UP", "DN", "VWIN"}))
        # 36 pins + UP + DN reach a block pin; VWIN stays inside lock_detector
        self.assertEqual(self.report.pin_nets, 38)
        self.assertEqual(sorted(self.report.star["VSS"]), ["divider_chain", "lock_detector", "loop_filter", "pfd_cp"])
        self.assertEqual(sorted(self.report.star["VDD"]), ["lock_detector", "pfd_cp"])

    def test_child_cells_are_the_generator_output(self):
        db = self.db
        top_ly = db.Layout()
        top_ly.read(str(self.gds))
        for spec in self.assemble.BLOCKS:
            src = db.Layout()
            src.read(str(self.blocks[spec.subckt]))
            child = top_ly.cell(spec.cell)
            self.assertIsNotNone(child, spec.cell)
            for idx in src.layer_indexes():
                info = src.get_info(idx)
                a = db.Region(src.top_cell().begin_shapes_rec(idx))
                tidx = top_ly.find_layer(info.layer, info.datatype)
                b = db.Region(child.begin_shapes_rec(tidx)) if tidx is not None else db.Region()
                self.assertTrue((a ^ b).is_empty(), f"{spec.cell} layer {info} differs after import")

    def test_transforms_move_labels_where_expected(self):
        db = self.db
        for spec in self.assemble.BLOCKS:
            view = self.asm.views[spec.subckt]
            src = db.Layout()
            src.read(str(self.blocks[spec.subckt]))
            sbb = src.top_cell().bbox()
            pbb = view.bbox
            self.assertEqual((pbb.width(), pbb.height()), (sbb.width(), sbb.height()), spec.subckt)
            lab = view.ex.labels[0]
            got = view.trans.trans(db.Point(round(lab.x * 1000), round(lab.y * 1000)))
            dx = round(lab.x * 1000) - sbb.left
            dy = round(lab.y * 1000) - sbb.bottom
            want = {
                "R0": (pbb.left + dx, pbb.bottom + dy),
                "M90": (pbb.right - dx, pbb.bottom + dy),  # mirrored about the y axis
                "R180": (pbb.right - dx, pbb.top - dy),
            }[spec.orient]
            self.assertEqual((got.x, got.y), want, f"{spec.subckt} ({spec.orient})")

    def test_orientations_are_the_documented_ones(self):
        got = {s.subckt: s.orient for s in self.assemble.BLOCKS}
        self.assertEqual(got, {"lock_detector": "M90", "pfd_cp": "M90", "loop_filter": "R0", "vco": "R0",
                               "divider_chain": "R180"})

    def test_unit_conversion_on_import(self):
        db = self.db
        src = db.Layout()
        src.read(str(self.blocks["loop_filter"]))
        scaled = db.Layout()
        scaled.dbu = 0.0005
        c = scaled.create_cell("loop_filter")
        c.copy_tree(src.top_cell())
        p = Path(self.tmp.name) / "loop_filter_halfnm.gds"
        scaled.write(str(p))
        ly = db.Layout()
        ly.dbu = 0.001
        spec = next(s for s in self.assemble.BLOCKS if s.subckt == "loop_filter")
        cell = self.assemble.import_block(ly, spec, p)
        self.assertEqual(cell.dbbox(), src.top_cell().dbbox())
        for idx in src.layer_indexes():
            info = src.get_info(idx)
            a = db.Region(src.top_cell().begin_shapes_rec(idx))
            b = db.Region(cell.begin_shapes_rec(ly.find_layer(info.layer, info.datatype)))
            self.assertTrue((a ^ b).is_empty(), f"layer {info} changed on a dbu round trip")

    def test_two_builds_are_the_same_geometry(self):
        from harness import reproduce

        again = self.assemble.build(Path(self.tmp.name) / "again", block_gds=self.blocks)
        self.assertEqual(reproduce.layer_differences(self.gds, again.gds), {})

    def test_wiring_uses_only_metal4_metal5_and_risers(self):
        layers = {s.layer for s in self.asm.board.shapes}
        self.assertLessEqual(layers, {"via1", "via2", "via3", "via4", "metal1", "metal2", "metal3", "metal4", "metal5"})
        for s in self.asm.board.shapes:
            if s.layer in ("metal1", "metal2", "metal3", "via1", "via2", "via3"):
                self.assertIn(s.role, ("pad", "via"), s)

    def test_area_is_recorded_and_over_the_row(self):
        # The fail-loud condition (PLL-FLOORPLAN.md section 5): the measured
        # top level is over the ratified 0.30 mm^2 row, and the overhead factor
        # is over the x1.664 the row holds to. Stated, not rounded away.
        rep = self.asm.report
        self.assertGreater(rep["area_um2"], 300_000.0)
        self.assertGreater(rep["area_um2"] / rep["block_sum_um2"], 1.664)

    def test_vco_decap_pair_is_physical_and_present_exactly_once(self):
        # Issue #759: the 22 pF decap is two real cap_nmos_03v3 devices, not
        # layer-(0, 0) markers, and the assembly carries them through once.
        pair, placeholders = _decap_gate_regions(self.db, self.gds)
        self.assertEqual(len(pair), 2)
        self.assertEqual(placeholders, 0)
        x0, y0, x1, y1 = self.asm.placements["vco"]["bbox_um"]
        for g in pair:
            b = g.bbox()
            self.assertTrue(
                x0 * 1000 <= b.left and b.right <= x1 * 1000 and y0 * 1000 <= b.bottom and b.top <= y1 * 1000,
                "a decap gate lies outside the placed VCO block",
            )

    def test_a_missing_decap_device_changes_the_count(self):
        # The count above is a real gate: delete one capacitor marker and it moves.
        db = self.db

        def edit(ly, top):
            li = ly.layer(166, 5)
            cell = ly.cell("vco_block")
            # the decap markers are the two 51.2 x 50 um ones (the loop filter's are 88.2 x 87)
            target = next(s for s in cell.shapes(li).each() if s.bbox().width() == 51_200)
            cell.shapes(li).erase(target)

        pair, _ = _decap_gate_regions(db, self._mutated(edit))
        self.assertEqual(len(pair), 1)

    # -- negative controls: blocks -------------------------------------------

    def test_assembler_refuses_a_missing_block(self):
        partial = {k: v for k, v in self.blocks.items() if k != "vco"}
        with self.assertRaisesRegex(self.assemble.AssemblyError, "missing \\['vco'\\]"):
            self.assemble.assemble(partial)

    def test_assembler_refuses_a_boundary_only_stand_in(self):
        db = self.db
        src = db.Layout()
        src.read(str(self.blocks["pfd_cp"]))
        stub = db.Layout()
        c = stub.create_cell("pfd_cp")
        c.shapes(stub.layer(0, 0)).insert(src.top_cell().bbox())
        p = Path(self.tmp.name) / "pfd_cp_box.gds"
        stub.write(str(p))
        blocks = dict(self.blocks, pfd_cp=p)
        with self.assertRaisesRegex(self.assemble.AssemblyError, "not a block layout"):
            self.assemble.assemble(blocks)

    def test_netcheck_reports_a_deleted_block(self):
        def edit(ly, top):
            for inst in list(top.each_inst()):
                if ly.cell(inst.cell_index).name == "lock_detector":
                    inst.delete()
            ly.delete_cell(ly.cell("lock_detector").cell_index())

        rep = self.netcheck.check(self._mutated(edit))
        self.assertFalse(rep.ok)
        self.assertTrue(any("lock_detector" in p and "0 instance" in p for p in rep.problems), rep.summary())

    def test_netcheck_reports_a_box_in_place_of_a_block(self):
        def edit(ly, top):
            cell = ly.cell("divider_chain")
            bb = cell.bbox()
            cell.clear()
            cell.shapes(ly.layer(0, 0)).insert(bb)

        rep = self.netcheck.check(self._mutated(edit))
        self.assertFalse(rep.ok)
        self.assertTrue(any("divider_chain" in p and "not a block layout" in p for p in rep.problems), rep.summary())

    # -- negative controls: connectivity -------------------------------------

    def test_cut_trunk_is_an_open(self):
        y = round(self.asm.report["tracks_um"]["VCTRL"] * 1000)

        def edit(ly, top):
            for s in self._top_shapes(ly, top, "metal4", lambda b: b.bottom < y < b.top and b.width() > 50_000):
                s.delete()

        rep = self.netcheck.check(self._mutated(edit))
        self.assertIn("VCTRL", rep.opens, rep.summary())

    def test_bridge_between_two_pins_is_a_short(self):
        a, b = self._access("pfd_cp", "REF"), self._access("pfd_cp", "B0")
        x0, x1 = sorted((a.x, b.x))
        ybot = round(self.asm.boundary[1] * 1000)

        def edit(ly, top):
            top.shapes(self._layer(ly, "metal5")).insert(self.db.Box(x0, ybot + 2000, x1, ybot + 2600))

        rep = self.netcheck.check(self._mutated(edit))
        self.assertTrue(any({"REF", "CPB0"} <= set(s) for s in rep.shorts), rep.summary())

    def test_riser_onto_an_internal_net_is_a_short(self):
        # Drop a Via3 + Metal4 pad onto a lock_detector-internal Metal3 net and
        # tie it to the UP track: no label is involved, so only the pin audit
        # (walking the chip netlist) can see it.
        db = self.db
        view = self.asm.views["lock_detector"]
        lab = next(l for l in view.ex.labels if l.text == "ERR")
        net = view.ex.net_at(lab.layer, lab.x, lab.y)
        m3 = view.ex.shapes(net, "metal3").transformed(view.trans)
        poly = max(m3.each(), key=lambda p: p.area())
        bb = poly.bbox()
        cx, cy = bb.center().x, bb.center().y
        cx = (cx // 5) * 5
        cy = (cy // 5) * 5
        up_y = round(self.asm.report["tracks_um"]["UP"] * 1000)
        up_x = self._access("lock_detector", "UP").x

        def edit(ly, top):
            top.shapes(self._layer(ly, "via3")).insert(db.Box(cx - 130, cy - 130, cx + 130, cy + 130))
            top.shapes(self._layer(ly, "metal4")).insert(db.Box(cx - 300, cy - 300, cx + 300, up_y + 300))
            top.shapes(self._layer(ly, "metal4")).insert(db.Box(min(cx, up_x) - 300, up_y - 300, max(cx, up_x) + 300, up_y + 300))

        rep = self.netcheck.check(self._mutated(edit))
        self.assertTrue(any("UP" in s and any(i.startswith("lock_detector:") for i in s) for s in rep.shorts),
                        rep.summary())

    def test_bridge_between_star_branches_is_reported(self):
        tr = self.asm.report["tracks_um"]
        # pfd_cp's branch runs from its port left to its slot; loop_filter's runs
        # from further right, past the same x, to its own slot -- bridge them there.
        ya, yb = round(tr["VSS@pfd_cp"] * 1000), round(tr["VSS@loop_filter"] * 1000)
        self.assertNotEqual(ya, yb)
        acc = self._access("pfd_cp", "VSS")

        def edit(ly, top):
            x = acc.x - 5_000
            top.shapes(self._layer(ly, "metal4")).insert(self.db.Box(x - 1000, min(ya, yb), x + 1000, max(ya, yb)))

        rep = self.netcheck.check(self._mutated(edit))
        self.assertFalse(rep.shorts, "a same-net bridge is not an electrical short")
        self.assertTrue(any(p.startswith("star VSS") for p in rep.problems), rep.summary())

    def test_non_vco_wire_in_the_vco_keepout_is_reported(self):
        vco = self.asm.views["vco"].bbox
        fb_y = round(self.asm.report["tracks_um"]["FB"] * 1000)

        def edit(ly, top):
            x = vco.center().x
            top.shapes(self._layer(ly, "metal4")).insert(self.db.Box(x - 300, vco.top - 5000, x + 300, fb_y + 300))

        rep = self.netcheck.check(self._mutated(edit))
        self.assertTrue(any("keep-out" in p and "FB" in p for p in rep.problems), rep.summary())

    def test_top_level_shape_over_the_mim_is_reported(self):
        lf = self.asm.views["loop_filter"]
        ft = lf.layers["fusetop"].bbox()

        def edit(ly, top):
            top.shapes(self._layer(ly, "metal4")).insert(ft)

        rep = self.netcheck.check(self._mutated(edit))
        self.assertTrue(any("MIM keep-out" in p for p in rep.problems), rep.summary())


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel")
class CommittedEvidenceTests(unittest.TestCase):
    def test_committed_gds_passes_netcheck(self):
        from pll_top.top_level import netcheck

        rep = netcheck.check(COMMITTED_GDS)
        self.assertTrue(rep.ok, rep.summary())

    def test_committed_report_matches_committed_gds(self):
        from pll_top.top_level import extract as X

        rep = json.loads(COMMITTED_REPORT.read_text())
        ly, top = X.read_top(COMMITTED_GDS)
        bb = top.dbbox()
        self.assertEqual(rep["boundary_um"], [round(bb.left, 4), round(bb.bottom, 4), round(bb.right, 4), round(bb.top, 4)])

    def test_committed_gds_carries_the_physical_decap_pair_once(self):
        import klayout.db as db

        pair, placeholders = _decap_gate_regions(db, COMMITTED_GDS)
        self.assertEqual(len(pair), 2)
        self.assertEqual(placeholders, 0)

    def test_proof_states_the_measured_area(self):
        rep = json.loads(COMMITTED_REPORT.read_text())
        text = re.sub(r"\s+", " ", PROOF.read_text())
        self.assertIn(f"{rep['area_um2']:,.1f}", text)
        self.assertIn(f"{rep['block_sum_um2']:,.1f}", text)
        self.assertIn("MIMTM.3", text)


if __name__ == "__main__":
    unittest.main()
