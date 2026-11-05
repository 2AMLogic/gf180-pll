#!/usr/bin/env python3
"""Tests for the physical loop filter, ``layout/pll_top/loop_filter/`` (issue #748).

What is pinned, and against what:

* **The device table is the committed netlist.** ``devices.py`` is parsed
  against ``design/netlist/loop_filter.spice`` (DR-006, with C2's device per
  DR-042): four plain ``ppolyf_u`` 2 x 107 um, four ``cap_nmos_03v3_b``
  87 x 87 um, one ``cap_mim_2f0_m4m5_noshield`` (MIM option B on gf180mcuD)
  31.4 x 31.4 um, and their terminal nets. The schematic, the committed
  netlists (loop filter and ``pll_top``) and the generator agree on that model.
* **The exported GDS draws exactly those devices** -- read back from the file
  with the LVS deck's own recognition expressions (``netcheck.census``), not
  from the generator's bookkeeping. A forbidden marker (the high-Rs ``(62, 0)``,
  ``dualgate``) or a ``(0, 0)`` boundary box is a failure, and a mutated copy
  carrying one must be reported (negative controls).
* **The exported GDS connects them as the netlist does** (``netcheck``): the
  series chain, both capacitor groups, every substrate/body tie to ``VSS``, the
  two port labels. An opened link, a shorted pair of chain nodes and a Via2
  joining the MIM's two plates, each injected into a temporary copy, must all
  be detected. A metal-only extraction that ignores the MIM top-plate layer
  must report the plates shorted on the *correct* layout -- the checker
  boundary the plate-aware extraction exists for.
* **Option B's stack rules that the generator can pre-check** (no Via3 under
  ``FuseTop`` -- MIMTM.10; Via4 sea enclosed 0.4 um by both plates and 0.5 um
  apart -- MIMTM.2/4/9). These are cheap pre-checks of the drawing, **not** a
  DRC result: the unmodified variant-D foundry runs are pending (DR-042).
* **The historical option-A path** (``mim_option="A"``) still draws and
  extracts correctly, because the committed #748 / ``pll_top`` evidence is
  reproduced from it.
* **Two builds are the same geometry**, and every vertex is on the 5 nm grid.

The KLayout-dependent classes skip (never error) without the ``klayout`` pip
wheel. The foundry DRC/LVS runs are recorded in
``layout/evidence/loop-filter-layout/PROOF.md``, not re-run here.

    python3 -m unittest discover -s layout/tests -t layout/tests -p test_loop_filter_layout.py -v
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from _env import HAVE_KLAYOUT, LAYOUT_DIR  # noqa: F401

from floorplan import skeleton  # noqa: E402
from harness import reproduce  # noqa: E402
from loop_filter import block, devices as dev, netcheck, primitives as prim  # noqa: E402

COMMITTED_GDS = LAYOUT_DIR / "evidence" / "loop-filter-layout" / "loop_filter.gds"


class DeviceTableIsTheNetlistTests(unittest.TestCase):
    """No KLayout needed."""

    def test_table_matches_committed_netlist(self):
        res, mos, mim = dev.table_from_netlist()
        self.assertEqual(res, dev.RESISTORS)
        self.assertEqual(mos, dev.MOS_CAPS)
        self.assertEqual(mim, dev.MIM_CAPS)
        ports, _ = dev.parse_netlist()
        self.assertEqual(ports, dev.PORTS)

    def test_dr006_values_pinned_literally(self):
        # Independent of both the table and the parser: DR-006's own numbers, with
        # C2's device as DR-042 re-ratifies it (option B, same 31.4 x 31.4 um).
        self.assertEqual([(r.model, r.w_um, r.l_um) for r in dev.RESISTORS], [("ppolyf_u", 2.0, 107.0)] * 4)
        self.assertEqual([(c.model, c.w_um, c.l_um) for c in dev.MOS_CAPS], [("cap_nmos_03v3_b", 87.0, 87.0)] * 4)
        self.assertEqual([(c.model, c.w_um, c.l_um) for c in dev.MIM_CAPS], [("cap_mim_2f0_m4m5_noshield", 31.4, 31.4)])
        self.assertEqual(dev.MIM_CAPS[0].option, "B")
        self.assertAlmostEqual(dev.device_area_um2(), 4 * 2 * 107 + 4 * 87 * 87 + 31.4 * 31.4)

    def test_option_a_is_the_same_drawn_size_on_the_historical_model(self):
        (a,) = dev.mim_caps("A")
        (b,) = dev.mim_caps("B")
        self.assertEqual((a.model, b.model), ("cap_mim_2f0_m2m3_noshield", "cap_mim_2f0_m4m5_noshield"))
        self.assertEqual((a.name, a.bottom_net, a.top_net, a.w_um, a.l_um), (b.name, b.bottom_net, b.top_net, b.w_um, b.l_um))
        self.assertEqual(dev.RATIFIED_MIM_OPTION, "B")

    def test_schematic_and_both_committed_netlists_name_the_option_b_device(self):
        """The schematic is the source; the loop-filter and pll_top exports must follow it (DR-042)."""
        repo = dev.REPO_ROOT
        sch = (repo / "design" / "loop_filter.sch").read_text()
        self.assertIn("name=CF5 model=cap_mim_2f0_m4m5_noshield W=31.4u L=31.4u", sch)
        self.assertNotIn("m2m3", sch)
        for name in ("loop_filter.spice", "pll_top.spice"):
            text = (repo / "design" / "netlist" / name).read_text()
            self.assertRegex(text, r"(?m)^XCF5 VCTRL VSS cap_mim_2f0_m4m5_noshield c_width=31.4u c_length=31.4u m=1$", name)
            self.assertNotIn("m2m3", text, name)

    def test_series_chain_topology(self):
        chain = [(r.net_b, r.net_a) for r in dev.RESISTORS]
        self.assertEqual(chain, [("VCTRL", "NR1"), ("NR1", "NR2"), ("NR2", "NR3"), ("NR3", "NZ")])
        self.assertTrue(all(r.sub_net == "VSS" for r in dev.RESISTORS))
        self.assertTrue(all((c.gate_net, c.body_net) == ("NZ", "VSS") for c in dev.MOS_CAPS))
        self.assertEqual([(c.bottom_net, c.top_net) for c in dev.MIM_CAPS], [("VCTRL", "VSS")])

    def test_parser_rejects_what_it_cannot_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.spice"
            bad.write_text(".subckt loop_filter A B\nXR1 A B VSS ppolyf_u r_width=2u\n+ r_length=107u\n.ends\n")
            with self.assertRaises(ValueError):
                dev.parse_netlist(bad)

    def test_placement_chain_is_consistent(self):
        block.check_chain()
        self.assertEqual(set(block.RES_ORDER), {r.name for r in dev.RESISTORS})
        self.assertEqual(block.bottom_net("XRF1"), "NR1")
        self.assertEqual(block.bottom_net("XRF4"), "NR3")

    def test_reference_netlist_restates_the_table(self):
        text = block.reference_netlist()
        r_cards = re.findall(r"^R_(\S+) (\S+) (\S+) (\S+) ppolyf_u W=(\S+)u L=(\S+)u$", text, re.M)
        self.assertEqual(
            [(n, a, b, s, float(w), float(l)) for n, a, b, s, w, l in r_cards],
            [(r.name, r.net_a, r.net_b, r.sub_net, r.w_um, r.l_um) for r in dev.RESISTORS],
        )
        mos = re.findall(r"^C_\S+ NZ VSS cap_nmos_03v3_b W=87.0u L=87.0u M=(\d+)$", text, re.M)
        self.assertEqual(mos, ["4"])
        self.assertRegex(text, r"(?m)^C_XCF5 VCTRL VSS cap_mim_2f0_m4m5_noshield W=31.4u L=31.4u$")
        self.assertIn(".SUBCKT loop_filter VCTRL VSS", text)
        # the historical option-A card, for the committed #748 evidence
        self.assertRegex(block.reference_netlist("A"), r"(?m)^C_XCF5 VCTRL VSS cap_mim_2f0_m2m3_noshield W=31.4u L=31.4u$")

    def test_drc_derived_margins(self):
        self.assertGreaterEqual(prim.PRES_CONTACT_TO_SAB_UM, 0.22)  # PRES.7
        self.assertGreaterEqual(prim.PRES_IMPLANT_ENC_UM, 0.3)  # PRES.5
        self.assertGreaterEqual(prim.PRES_SAB_EXT_UM, 0.28)  # PRES.6
        self.assertGreaterEqual(block.RES_TO_TAP_UM, 0.6)  # PRES.3
        self.assertGreaterEqual(prim.MOSCAP_SD_EXT_UM - prim.CONTACT_ENC_UM - prim.CONTACT_UM, 0.15)  # CO.7
        self.assertGreaterEqual(prim.MOSCAP_POLY_CONTACT_GAP_UM, 0.17)  # CO.8
        self.assertGreaterEqual(prim.MOSCAP_IMPLANT_MARGIN_UM, 0.23)  # NP.5a
        self.assertGreaterEqual(prim.MIM_BOTTOM_ENC_UM, 0.6)  # MIM.3
        self.assertGreaterEqual(prim.MIM_VIA_ENC_UM, 0.4)  # MIM.4
        self.assertGreaterEqual(prim.MIM_VIA_SPACE_UM, 0.5)  # MIM.9
        self.assertLess(prim.STACK_VIA_PITCH_UM - prim.VIA_UM, 0.6)  # one MT30.8 location
        self.assertGreaterEqual(prim.STACK_TOP_METAL_UM, 2.5)  # MT30.6 threshold (A); MT.1 is 0.44 (B)
        self.assertGreaterEqual(block.VCTRL_LANDING_BELOW_PLATE_UM, 1.2)  # MIMTM.1: clear of the virtual-plate band

    def test_footprint_fits_floorplan_reservation(self):
        x0, y0, x1, y1 = block.footprint_um()
        self.assertLessEqual(x1 - x0, skeleton.LOOP_FILTER.w)
        self.assertLessEqual(y1 - y0, skeleton.LOOP_FILTER.h)


def _write(layout, top, path: Path) -> Path:
    import klayout.db as db

    options = db.SaveLayoutOptions()
    options.select_cell(top.cell_index())
    options.format = "GDS2"
    layout.write(str(path), options)
    return path


def _mutate(src: Path, dst: Path, fn) -> Path:
    import klayout.db as db

    layout = db.Layout()
    layout.read(str(src))
    top = layout.top_cells()[0]
    fn(layout, top, db)
    return _write(layout, top, dst)


def _box(db, x0, y0, x1, y1):
    return db.Box(*(int(round(v * 1000)) for v in (x0, y0, x1, y1)))


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class ExportedGdsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.result = block.build(cls.tmp / "a")
        cls.gds = cls.result.gds
        cls.census = netcheck.census(cls.gds)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _problems(self, census):
        return netcheck.device_problems(census, resistors=dev.RESISTORS, mos_caps=dev.MOS_CAPS, mim_caps=dev.MIM_CAPS)

    # --- devices --------------------------------------------------------

    def test_device_census_matches_dr006(self):
        self.assertEqual(self._problems(self.census), [])

    def test_each_device_extent_is_the_ratified_size(self):
        c = self.census
        self.assertEqual(len(c.mos_gates), 4)
        for g in c.mos_gates:
            self.assertAlmostEqual(g[2] - g[0], 87.0, places=6)
            self.assertAlmostEqual(g[3] - g[1], 87.0, places=6)
        self.assertEqual(len(c.resistor_bodies), 4)
        for b in c.resistor_bodies:
            self.assertAlmostEqual(b[2] - b[0], 2.0, places=6)
            self.assertAlmostEqual(b[3] - b[1], 107.0, places=6)
        self.assertEqual(len(c.mim_tops), 1)
        t = c.mim_tops[0]
        self.assertAlmostEqual(t[2] - t[0], 31.4, places=6)
        self.assertAlmostEqual(t[3] - t[1], 31.4, places=6)

    def test_real_device_layers_present_and_forbidden_absent(self):
        shapes = self.census.layer_shapes
        for name in (
            "mos_cap_mk", "fusetop", "cap_mk", "mim_l_mk", "res_mk", "sab", "nwell", "nplus", "pplus",
            "via2", "metal3", "via3", "metal4", "via4", "metal5",
        ):
            self.assertGreater(shapes.get(prim.LAYER[name], 0), 0, name)
        self.assertEqual(shapes.get(prim.LAYER["mos_cap_mk"]), 4)
        self.assertEqual(shapes.get(prim.LAYER["res_mk"]), 4)
        self.assertEqual(self.census.forbidden, {"resistor": 0, "dualgate": 0, "boundary": 0})

    def test_every_vertex_on_manufacturing_grid(self):
        import klayout.db as db

        layout = db.Layout()
        layout.read(str(self.gds))
        top = layout.top_cells()[0]
        grid = int(round(dev.LAYOUT_GRID_UM / layout.dbu))
        off = []
        for li in layout.layer_indexes():
            it = top.begin_shapes_rec(li)
            while not it.at_end():
                s = it.shape()
                if s.is_box() or s.is_polygon():
                    for p in s.polygon.each_point_hull():
                        if p.x % grid or p.y % grid:
                            off.append((layout.get_info(li).to_s(), p.x, p.y))
                it.next()
        self.assertEqual(off[:5], [])

    def test_census_rejects_high_rs_marker_and_boundary_substitute(self):
        r0 = self.census.resistor_bodies[0]
        g0 = self.census.mos_gates[0]

        def corrupt(layout, top, db):
            top.shapes(layout.layer(62, 0)).insert(_box(db, r0[0] - 1, r0[1] - 1, r0[2] + 1, r0[3] + 1))
            mk = layout.layer(*prim.LAYER["mos_cap_mk"])
            doomed = [s for s in top.shapes(mk).each() if s.bbox().contains(_box(db, *g0).center())]
            for s in doomed:
                top.shapes(mk).erase(s)
            top.shapes(layout.layer(0, 0)).insert(_box(db, *g0))

        bad = _mutate(self.gds, self.tmp / "corrupt.gds", corrupt)
        problems = self._problems(netcheck.census(bad))
        joined = "\n".join(problems)
        self.assertIn("forbidden layer resistor", joined)
        self.assertIn("forbidden layer boundary", joined)
        self.assertIn("3 MOS-cap gate(s) found", joined)

    def test_declared_footprint_matches_gds_bounds(self):
        """``footprint_um()`` must equal the exported GDS's real geometry bounds (implants included)."""
        import klayout.db as db

        for gds in (self.gds, COMMITTED_GDS):
            layout = db.Layout()
            layout.read(str(gds))
            bb = layout.top_cells()[0].dbbox()
            got = (bb.left, bb.bottom, bb.right, bb.top)
            for want, have in zip(block.footprint_um(), got):
                self.assertAlmostEqual(want, have, places=3, msg=f"{gds.name}: {block.footprint_um()} vs {got}")
        self.assertEqual(self.result.footprint, block.footprint_um())

    # --- connectivity -----------------------------------------------------

    def test_topology_from_gds_alone(self):
        rep = netcheck.check_topology(self.gds)
        self.assertTrue(rep.ok, rep.summary())
        # 8 resistor ends + 8 gate rows + 12 body terminals + taps + 2 MIM plates
        self.assertGreaterEqual(rep.checked, 8 + 8 + 12 + 2)

    def test_named_terminal_probes(self):
        rep = netcheck.check_probes(self.gds, self.result.probes)
        self.assertTrue(rep.ok, rep.summary())
        whats = " ".join(p.what for p in self.result.probes)
        for name in [r.name for r in dev.RESISTORS] + [c.name for c in dev.MOS_CAPS + dev.MIM_CAPS]:
            self.assertIn(name, whats)

    def test_metal_only_flood_shorts_the_mim_plates(self):
        """The checker boundary: without FuseTop-aware Via2 the correct layout reads as VCTRL=VSS."""
        rep = netcheck.check_topology(self.gds, plate_aware=False)
        self.assertFalse(rep.ok)
        self.assertIn(("VCTRL", "VSS"), rep.shorts)

    def _link_bar(self, layout, top, db, net):
        """The metal1 link carrying ``net``'s label."""
        x, y = next((x, y) for t, ln, x, y in self.census.labels if t == net and ln == "metal1_label")
        m1 = layout.layer(*prim.LAYER["metal1"])
        p = db.Point(int(round(x * 1000)), int(round(y * 1000)))
        hits = [s for s in top.shapes(m1).each() if s.bbox().contains(p) and s.bbox().width() > 4000]
        self.assertEqual(len(hits), 1, f"expected one link bar under {net}")
        return m1, hits[0]

    def test_negative_control_open_link(self):
        def open_nr2(layout, top, db):
            m1, bar = self._link_bar(layout, top, db, "NR2")
            top.shapes(m1).erase(bar)

        bad = _mutate(self.gds, self.tmp / "open.gds", open_nr2)
        topo = netcheck.check_topology(bad)
        self.assertFalse(topo.ok)
        probes = netcheck.check_probes(bad, self.result.probes)
        self.assertIn("NR2", probes.opens)

    def test_negative_control_short_between_chain_nodes(self):
        nz_pad = next(r for r in self.result.resistors if r.name == "XRF4").top_pad
        nr2_pad = next(r for r in self.result.resistors if r.name == "XRF3").top_pad

        def short(layout, top, db):
            top.shapes(layout.layer(*prim.LAYER["metal1"])).insert(
                _box(db, nz_pad[0], nz_pad[1], nr2_pad[2], nz_pad[3])
            )

        bad = _mutate(self.gds, self.tmp / "short.gds", short)
        self.assertFalse(netcheck.check_topology(bad).ok)
        self.assertIn(("NR2", "NZ"), netcheck.check_probes(bad, self.result.probes).shorts)

    def test_negative_control_via4_joining_the_mim_plates(self):
        """A Via4 *outside* FuseTop, where the VSS Metal5 strap crosses the Metal4 bottom plate."""
        mp = self.result.mim
        self.assertEqual(mp.option, "B")
        x = block.VSS_STACK_X_UM
        y = (mp.bottom_plate[1] + mp.fusetop[1]) / 2.0
        h = prim.VIA_UM / 2

        def bridge(layout, top, db):
            top.shapes(layout.layer(*prim.LAYER["via4"])).insert(_box(db, x - h, y - h, x + h, y + h))

        bad = _mutate(self.gds, self.tmp / "mimshort.gds", bridge)
        topo = netcheck.check_topology(bad)
        self.assertIn(("VCTRL", "VSS"), topo.shorts)

    def test_negative_control_open_vctrl_landing(self):
        """Removing the Via3 that carries VCTRL up into the Metal4 bottom-plate stub opens VCTRL."""

        def drop_via3(layout, top, db):
            idx = layout.layer(*prim.LAYER["via3"])
            vias = list(top.shapes(idx).each())
            # the VCTRL landing's Via3: the one nearest below the plate (the VSS stack's are far lower)
            keep_y = max(v.bbox().center().y for v in vias)
            for v in vias:
                if v.bbox().center().y == keep_y:
                    top.shapes(idx).erase(v)

        bad = _mutate(self.gds, self.tmp / "openvctrl.gds", drop_via3)
        self.assertFalse(netcheck.check_topology(bad).ok)
        self.assertTrue(netcheck.check_probes(bad, self.result.probes).opens)

    # --- option B's stack rules the generator can pre-check (NOT a DRC result) ---

    def _regions(self):
        import klayout.db as db

        layout = db.Layout()
        layout.read(str(self.gds))
        top = layout.top_cells()[0]
        R = {n: db.Region(top.begin_shapes_rec(layout.layer(*gl))) for n, gl in prim.LAYER.items()}
        self._keepalive = layout  # the Regions read shapes lazily from the layout
        return db, layout.dbu, R

    def test_option_b_stack_prechecks(self):
        db, dbu, R = self._regions()
        um = lambda v: int(round(v / dbu))  # noqa: E731
        ft = R["fusetop"]
        # MIMTM.10: no Via3 touches the bottom plate under FuseTop
        self.assertTrue((R["via3"] & ft).is_empty(), "Via3 under FuseTop")
        # the plate-crossing vias exist only inside FuseTop within the 1.06 um virtual-plate band (MIMTM.2/4)
        band = ft.sized(um(1.06))
        v4_band = R["via4"] & band
        self.assertFalse(v4_band.is_empty())
        self.assertTrue((v4_band - ft).is_empty(), "a Via4 in the virtual-plate band lies outside FuseTop")
        self.assertTrue((v4_band.sized(um(prim.MIM_VIA_ENC_UM)) - ft).is_empty(), "MIMTM.4: FuseTop overlap of Via4 < 0.4 um")
        self.assertTrue((v4_band.sized(um(0.4)) - R["metal4"]).is_empty(), "MIMTM.2: bottom plate overlap of Via4 < 0.4 um")
        # MIMTM.9: Via4 sea spacing
        self.assertEqual(v4_band.space_check(um(prim.MIM_VIA_SPACE_UM)).count(), 0)
        # the top plate metal is FuseTop's own footprint, the bottom plate is cap_mk
        self.assertTrue((ft - R["metal5"]).is_empty())
        self.assertTrue((R["cap_mk"] - R["metal4"]).is_empty())
        self.assertEqual(self.result.mim.via_count, v4_band.count())
        # option A's metals are absent from C2 (no Metal2/Metal3 plate rectangles of C2's size)
        self.assertTrue((R["metal3"] & ft).is_empty(), "Metal3 under FuseTop (that is option A's top plate)")

    # --- reproducibility ----------------------------------------------------

    def test_two_builds_are_the_same_geometry(self):
        second = block.build(self.tmp / "b")
        self.assertEqual(reproduce.layer_differences(self.gds, second.gds), {})

    def test_committed_gds_is_registered_for_reproduction(self):
        """The committed #748 GDS is option A; its registration must say so (DR-042)."""
        entries = {(b.gds, b.module): b for b in reproduce.BLOCKS}
        block_ = entries[("evidence/loop-filter-layout/loop_filter.gds", "pll_top.loop_filter.block")]
        self.assertEqual(block_.args, ("--mim-option", "A"))


@unittest.skipUnless(HAVE_KLAYOUT, "needs the klayout pip wheel (klayout.db)")
class HistoricalOptionATests(unittest.TestCase):
    """The option-A drawing the committed #748 / pll_top evidence was made from still works."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.result = block.build(cls.tmp / "a", mim_option="A")
        cls.census = netcheck.census(cls.result.gds)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_draws_the_option_a_device(self):
        self.assertEqual(self.census.mim_option, "A")
        self.assertEqual(self.result.mim.option, "A")
        problems = netcheck.device_problems(
            self.census, resistors=dev.RESISTORS, mos_caps=dev.MOS_CAPS, mim_caps=dev.mim_caps("A")
        )
        self.assertEqual(problems, [])

    def test_the_option_b_netlist_does_not_match_an_option_a_drawing(self):
        problems = netcheck.device_problems(
            self.census, resistors=dev.RESISTORS, mos_caps=dev.MOS_CAPS, mim_caps=dev.MIM_CAPS
        )
        self.assertTrue(any("option A" in p for p in problems), problems)

    def test_connectivity_and_plate_boundary(self):
        self.assertTrue(netcheck.check_topology(self.result.gds).ok)
        self.assertTrue(netcheck.check_probes(self.result.gds, self.result.probes).ok)
        rep = netcheck.check_topology(self.result.gds, plate_aware=False)
        self.assertIn(("VCTRL", "VSS"), rep.shorts)

    def test_matches_the_committed_evidence_geometry(self):
        self.assertEqual(reproduce.layer_differences(COMMITTED_GDS, self.result.gds), {})


if __name__ == "__main__":
    unittest.main()
