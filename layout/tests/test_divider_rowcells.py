#!/usr/bin/env python3
"""Smoke tests for the ``divider_chain`` row-cell leaf set (issue #307).

Companion to ``test_divider_devgen.py`` (issue #306, ``build_stack_cell()``
and its two single-column proof cells); this module covers the four cells
issue #307 adds -- ``nand2_3v3``, ``nand3_3v3``, ``nor2_3v3``,
``inv2x_3v3`` -- and the ``devgen.build_row_cell()`` generator they share.

Same conventions as that file: ``klayout.db`` is *required* for the geometry
classes below (``build_row_cell()`` is exercised directly) but its absence
skips rather than fails, so a PDK/PV-less checkout still collects this file
cleanly:

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC/LVS-clean claim (which additionally needs the PDK's own
signoff decks) see ``layout/evidence/divider-rowcells-proof/PROOF.md``. What
this file checks is the geometry these modules *claim* to build: that each
device table matches its schematic, that all four cells share one row-cell
frame, and -- the one that is not a restatement of the generator's own code
-- that no Metal1 island in any of the four cells carries two different
nets' device pads. That last check is a real short detector: the first
attempt at this issue drew each supply rail as one rectangle spanning every
pad of that net, which silently swallowed the gate pad of every column to
its right. It was DRC-clean (two same-layer shapes overlapping is not a DRC
error) and only LVS caught it. ``Metal1IslandTests`` catches that class of
bug without needing the PDK.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

try:
    import klayout.db as kdb  # noqa: F401

    _HAVE_KLAYOUT = True
except ImportError:
    _HAVE_KLAYOUT = False

from divider_chain import devgen  # noqa: E402
from divider_chain import inv2x_3v3, inv_3v3, nand2_3v3, nand3_3v3, nor2_3v3  # noqa: E402

CELLS = (nand2_3v3, nand3_3v3, nor2_3v3, inv2x_3v3)


def _devices(module) -> dict[str, devgen.Device]:
    out: dict[str, devgen.Device] = {}
    for col in module.COLUMNS:
        for d in col.pulldown + col.pullup:
            out[d.name] = d
    return out


class DeviceTableTests(unittest.TestCase):
    """Each COLUMNS table matches its own design/*.sch instance list."""

    def test_nand2_matches_the_schematic(self):
        d = _devices(nand2_3v3)
        self.assertEqual(sorted(d), ["MNA", "MNB", "MPA", "MPB"])
        for name in ("MPA", "MPB"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("pfet", 2.5, 0.28))
        for name in ("MNA", "MNB"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("nfet", 2.0, 0.28))

    def test_nand3_matches_the_schematic(self):
        d = _devices(nand3_3v3)
        self.assertEqual(sorted(d), ["MNA", "MNB", "MNC", "MPA", "MPB", "MPC"])
        for name in ("MPA", "MPB", "MPC"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("pfet", 2.5, 0.28))
        for name in ("MNA", "MNB", "MNC"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("nfet", 3.0, 0.28))

    def test_nor2_matches_the_schematic(self):
        d = _devices(nor2_3v3)
        self.assertEqual(sorted(d), ["MNA", "MNB", "MPA", "MPB"])
        for name in ("MPA", "MPB"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("pfet", 5.0, 0.28))
        for name in ("MNA", "MNB"):
            self.assertEqual((d[name].kind, d[name].w_um, d[name].l_um), ("nfet", 1.0, 0.28))

    def test_nand_pulldowns_are_series_and_pullups_parallel(self):
        # A NAND's series pull-down is one multi-device branch; its parallel
        # pull-up is one single-device branch per input.
        for mod, n in ((nand2_3v3, 2), (nand3_3v3, 3)):
            with self.subTest(cell=mod.TOP_CELL):
                pulldowns = [c.pulldown for c in mod.COLUMNS if c.pulldown]
                pullups = [c.pullup for c in mod.COLUMNS if c.pullup]
                self.assertEqual(len(pulldowns), 1)
                self.assertEqual(len(pulldowns[0]), n)
                self.assertEqual(len(pullups), n)
                self.assertTrue(all(len(b) == 1 for b in pullups))

    def test_nor2_is_the_mirror_image_of_a_nand(self):
        # nor2 is the only cell here whose *pull-up* is the series stack.
        pulldowns = [c.pulldown for c in nor2_3v3.COLUMNS if c.pulldown]
        pullups = [c.pullup for c in nor2_3v3.COLUMNS if c.pullup]
        self.assertEqual(len(pullups), 1)
        self.assertEqual(len(pullups[0]), 2)
        self.assertEqual(len(pulldowns), 2)
        self.assertTrue(all(len(b) == 1 for b in pulldowns))

    def test_series_branches_share_their_internal_nodes(self):
        # Every multi-device branch must be a real series stack: device i's
        # top_net is device i+1's bottom_net. build_row_cell() resolves that
        # pair locally and would otherwise reject the terminal outright.
        expected = {
            "nand2_3v3": ["NMID"],
            "nand3_3v3": ["NM1", "NM2"],
            "nor2_3v3": ["PMID"],
            "inv2x_3v3": [],
        }
        for mod in CELLS:
            with self.subTest(cell=mod.TOP_CELL):
                internal = []
                for col in mod.COLUMNS:
                    for branch in (col.pulldown, col.pullup):
                        for i in range(len(branch) - 1):
                            self.assertEqual(branch[i].top_net, branch[i + 1].bottom_net)
                            internal.append(branch[i].top_net)
                self.assertEqual(sorted(internal), expected[mod.TOP_CELL])

    def test_no_cell_needs_an_explicit_body_net(self):
        # Every device here has a supply net on its own outward-facing
        # terminal, or ties through the shared well -- the tgate_3v3 case
        # (devgen.Device.body_net) does not arise in this family.
        for mod in CELLS:
            for d in _devices(mod).values():
                with self.subTest(cell=mod.TOP_CELL, device=d.name):
                    self.assertIsNone(d.body_net)


class Inv2xVersusInv1xTests(unittest.TestCase):
    """inv2x_3v3 differs from issue #306's inv_3v3 *only* in device width."""

    def setUp(self):
        self.inv2x = _devices(inv2x_3v3)
        self.inv1x = {d.name: d for d in inv_3v3.INV_DEVICES}

    def test_same_device_names_and_kinds(self):
        self.assertEqual(sorted(self.inv2x), sorted(self.inv1x))
        for name, d in self.inv2x.items():
            self.assertEqual(d.kind, self.inv1x[name].kind)

    def test_same_topology_same_nets_on_the_same_terminals(self):
        for name, d in self.inv2x.items():
            ref = self.inv1x[name]
            with self.subTest(device=name):
                self.assertEqual(d.gate_net, ref.gate_net)
                self.assertEqual(d.top_net, ref.top_net)
                self.assertEqual(d.bottom_net, ref.bottom_net)
                self.assertEqual(d.l_um, ref.l_um)

    def test_widths_are_exactly_2x(self):
        for name, d in self.inv2x.items():
            with self.subTest(device=name):
                self.assertAlmostEqual(d.w_um, 2.0 * self.inv1x[name].w_um)


class ReferenceNetlistTests(unittest.TestCase):
    """Each hand-written LVS reference netlist matches its device table."""

    def test_subckt_name_matches_top_cell(self):
        for mod in CELLS:
            with self.subTest(cell=mod.TOP_CELL):
                self.assertIn(f".subckt {mod.TOP_CELL} ", mod.reference_netlist())

    def test_every_device_appears_with_its_own_size(self):
        for mod in CELLS:
            netlist = mod.reference_netlist()
            for d in _devices(mod).values():
                model = "pfet_03v3" if d.kind == "pfet" else "nfet_03v3"
                w = f"{d.w_um:g}u"
                with self.subTest(cell=mod.TOP_CELL, device=d.name):
                    self.assertIn(f"M_{d.name} ", netlist)
                    self.assertIn(f"{model} W={w} L={d.l_um:g}u", netlist)

    def test_device_count_matches_the_device_table(self):
        for mod in CELLS:
            netlist = mod.reference_netlist()
            lines = [ln for ln in netlist.splitlines() if ln.startswith("M_")]
            with self.subTest(cell=mod.TOP_CELL):
                self.assertEqual(len(lines), len(_devices(mod)))

    def test_subckt_header_declares_every_boundary_net(self):
        for mod in CELLS:
            netlist = mod.reference_netlist()
            header = next(ln for ln in netlist.splitlines() if ln.startswith(".subckt"))
            devs = _devices(mod).values()
            internal = {b[i].top_net for c in mod.COLUMNS for b in (c.pulldown, c.pullup) for i in range(len(b) - 1)}
            boundary = {n for d in devs for n in (d.gate_net, d.top_net, d.bottom_net)} - internal
            with self.subTest(cell=mod.TOP_CELL):
                for net in sorted(boundary):
                    self.assertIn(net, header.split())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class RowCellFrameTests(unittest.TestCase):
    """All four cells share one row-cell frame (the abutment contract).

    This is the acceptance criterion Parts 3/4 (#308's ``dff_tg_3v3``,
    #309's ``div23_cell``) depend on: identical cell height and identical
    ``VDD``/``VSS`` rail y-bands, so the cells can be placed side by side in
    a row with their rails lining up.
    """

    @classmethod
    def setUpClass(cls):
        cls.leaves = {m.TOP_CELL: m.build() for m in CELLS}

    def test_every_cell_has_the_same_height(self):
        heights = {name: leaf.footprint[3] - leaf.footprint[1] for name, leaf in self.leaves.items()}
        self.assertEqual(len(set(round(h, 6) for h in heights.values())), 1, heights)
        self.assertAlmostEqual(next(iter(heights.values())), devgen.ROW_CELL_H_UM)

    def test_every_cell_spans_the_frame_exactly(self):
        for name, leaf in self.leaves.items():
            with self.subTest(cell=name):
                self.assertAlmostEqual(leaf.footprint[0], 0.0)
                self.assertAlmostEqual(leaf.footprint[1], devgen.ROW_CELL_Y0)
                self.assertAlmostEqual(leaf.footprint[3], devgen.ROW_CELL_Y1)
                self.assertGreater(leaf.footprint[2], leaf.footprint[0])

    def test_supply_rails_span_the_full_cell_width_at_the_frame_y(self):
        half = devgen.ROW_RAIL_H_UM / 2.0
        for name, leaf in self.leaves.items():
            with self.subTest(cell=name):
                for net, cy in (("VSS", devgen.ROW_VSS_RAIL_CY), ("VDD", devgen.ROW_VDD_RAIL_CY)):
                    pad = leaf.pins[net]
                    self.assertAlmostEqual(pad[0], leaf.footprint[0])
                    self.assertAlmostEqual(pad[2], leaf.footprint[2])
                    self.assertAlmostEqual(pad[1], cy - half)
                    self.assertAlmostEqual(pad[3], cy + half)

    def test_device_rows_sit_on_the_shared_baselines(self):
        for name, leaf in self.leaves.items():
            with self.subTest(cell=name):
                nfet_y0 = min(p.y0 for p in leaf.ports if p.kind == "nfet")
                pfet_y0 = min(p.y0 for p in leaf.ports if p.kind == "pfet")
                self.assertAlmostEqual(nfet_y0, devgen.ROW_PD_Y0)
                self.assertAlmostEqual(pfet_y0, devgen.ROW_PU_Y0)

    def test_nwell_encloses_every_pfet_and_the_tap_row(self):
        for name, leaf in self.leaves.items():
            with self.subTest(cell=name):
                self.assertIsNotNone(leaf.nwell_box)
                wx0, wy0, wx1, wy1 = leaf.nwell_box
                for p in (p for p in leaf.ports if p.kind == "pfet"):
                    self.assertLessEqual(wx0, p.x0)
                    self.assertGreaterEqual(wx1, p.x1)
                    self.assertLessEqual(wy0, p.y0)
                    self.assertGreaterEqual(wy1, p.y3)
                # the n-well tap row lives inside the same well
                self.assertGreaterEqual(wy1, devgen.ROW_NTAP_Y0 + devgen.TAP_SIZE_UM)

    def test_every_boundary_net_is_a_labelled_pin(self):
        expected = {
            "nand2_3v3": {"A", "B", "Y", "VDD", "VSS"},
            "nand3_3v3": {"A", "B", "C", "Y", "VDD", "VSS"},
            "nor2_3v3": {"A", "B", "Y", "VDD", "VSS"},
            "inv2x_3v3": {"A", "Y", "VDD", "VSS"},
        }
        for name, leaf in self.leaves.items():
            with self.subTest(cell=name):
                self.assertEqual(set(leaf.pins), expected[name])


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class Metal1IslandTests(unittest.TestCase):
    """No merged Metal1 island carries two different nets' device pads.

    See this module's docstring for the concrete short this catches. Only
    *device pads* are probed (gate/source/drain, from the device tables), so
    the check needs no knowledge of how the generator routes between them --
    it fails whenever two pads that should be separate nets end up on one
    physically-connected Metal1 shape, whatever drew them that way.

    The converse (a net wrongly *split* into two islands, an open) is not
    checkable here, because this generator deliberately joins some of a
    net's own islands through Metal2 -- that direction is what the LVS run
    recorded in ``layout/evidence/divider-rowcells-proof/PROOF.md`` proves.
    """

    def _islands(self, leaf):
        layout = leaf.canvas.layout
        layer = layout.layer(*devgen.LAYER["metal1"])
        return list(kdb.Region(leaf.canvas.top.shapes(layer)).merged().each())

    def _net_of_pad(self, mod, leaf):
        """[(net, pad)] for every device terminal, from the device tables."""
        by_name = {p.name: p for p in leaf.ports}
        out = []
        for d in _devices(mod).values():
            p = by_name[d.name]
            out.append((d.gate_net, p.gate_pad))
            out.append((d.top_net, p.top_pad))
            out.append((d.bottom_net, p.bottom_pad))
        return out

    def test_no_metal1_island_mixes_two_nets(self):
        for mod in CELLS:
            leaf = mod.build()
            dbu = leaf.canvas.dbu
            islands = self._islands(leaf)
            seen: dict[int, str] = {}
            for net, pad in self._net_of_pad(mod, leaf):
                cx = int(round((pad[0] + pad[2]) / 2.0 / dbu))
                cy = int(round((pad[1] + pad[3]) / 2.0 / dbu))
                pt = kdb.Point(cx, cy)
                hits = [i for i, poly in enumerate(islands) if poly.inside(pt)]
                with self.subTest(cell=mod.TOP_CELL, net=net, pad=pad):
                    self.assertEqual(len(hits), 1, "pad centre is not on exactly one Metal1 island")
                    idx = hits[0]
                    if idx in seen:
                        self.assertEqual(
                            seen[idx], net,
                            f"{mod.TOP_CELL}: Metal1 island {idx} carries both "
                            f"{seen[idx]!r} and {net!r}",
                        )
                    seen[idx] = net


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class BuildRowCellValidationTests(unittest.TestCase):
    """build_row_cell() refuses what it cannot draw, rather than drawing it wrong."""

    def _dev(self, name, kind, **kw):
        base = dict(w_um=1.0, l_um=0.28, gate_net="G", top_net="T", bottom_net="B")
        base.update(kw)
        return devgen.Device(name=name, kind=kind, **base)

    def test_no_columns_raises(self):
        with self.assertRaises(ValueError):
            devgen.build_row_cell("empty_test", ())

    def test_empty_column_raises(self):
        with self.assertRaises(ValueError):
            devgen.build_row_cell("empty_col_test", (devgen.Column(),))

    def test_pfet_in_the_pulldown_row_raises(self):
        with self.assertRaises(ValueError):
            devgen.build_row_cell(
                "wrong_kind_test",
                (devgen.Column(pulldown=(self._dev("MX", "pfet"),), pullup=(self._dev("MP", "pfet"),)),),
            )

    def test_nfet_in_the_pullup_row_raises(self):
        with self.assertRaises(ValueError):
            devgen.build_row_cell(
                "wrong_kind_test2",
                (devgen.Column(pulldown=(self._dev("MN", "nfet"),), pullup=(self._dev("MY", "nfet"),)),),
            )

    def test_one_net_rail_facing_in_both_rows_raises(self):
        # Each row gets exactly one supply rail, so a net cannot be the
        # rail-facing net of both: here the pull-up's source shares the
        # pull-down's own source net.
        with self.assertRaises(NotImplementedError):
            devgen.build_row_cell(
                "no_rail_test",
                (
                    devgen.Column(
                        pulldown=(self._dev("MN", "nfet", gate_net="A", top_net="Y", bottom_net="VSS"),),
                        pullup=(self._dev("MP", "pfet", gate_net="A", top_net="VSS", bottom_net="Y"),),
                    ),
                ),
            )

    def test_two_rail_nets_in_one_row_raises(self):
        # Two pull-down branches sourcing different supply nets would need
        # two VSS rails; build_row_cell() draws exactly one per row.
        with self.assertRaises(ValueError):
            devgen.build_row_cell(
                "two_rails_test",
                (
                    devgen.Column(
                        pulldown=(self._dev("MNA", "nfet", gate_net="A", top_net="Y", bottom_net="VSS"),),
                        pullup=(self._dev("MP", "pfet", gate_net="A", top_net="VDD", bottom_net="Y"),),
                    ),
                    devgen.Column(
                        pulldown=(self._dev("MNB", "nfet", gate_net="B", top_net="Y", bottom_net="VSSB"),),
                    ),
                ),
            )

    def test_unroutable_interior_terminal_raises(self):
        # A three-high branch whose middle device does not series-connect to
        # its neighbours leaves interior S/D pads with nowhere to go.
        with self.assertRaises(NotImplementedError):
            devgen.build_row_cell(
                "interior_test",
                (
                    devgen.Column(
                        pulldown=(
                            self._dev("M0", "nfet", gate_net="A", top_net="N0", bottom_net="VSS"),
                            self._dev("M1", "nfet", gate_net="B", top_net="N2", bottom_net="N1"),
                            self._dev("M2", "nfet", gate_net="C", top_net="Y", bottom_net="N3"),
                        ),
                        pullup=(self._dev("MP", "pfet", gate_net="A", top_net="VDD", bottom_net="Y"),),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
