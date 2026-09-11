#!/usr/bin/env python3
"""Unit tests for the VCO's real transistor-level layout (issue #293).

No PDK and no KLayout required -- ``layout/pll_top/vco/primitives.py`` and
``ring.py`` only import ``klayout.db`` lazily inside functions that actually
draw geometry (same convention as ``layout/floorplan/skeleton.py`` /
``layout/harness/cell.py``), so every number this file checks
(``devices.py``'s schematic-sourced device table, ``ring.py``'s pure-Python
footprint/tap-distance helpers) is importable and checkable without a PV
environment.

The one exception is ``DogBoneMosfetTests``, which exercises the geometry
``primitives.mosfet()`` actually *draws* and therefore does need
``klayout.db``. It is gated behind ``@unittest.skipUnless(_HAVE_KLAYOUT, ...)``
-- the same convention ``test_pfdcp_devgen.py`` uses -- so it skips (never
errors) in the headless CI job, and this file as a whole keeps its "runs
without KLayout" contract.

    python3 -m unittest discover -s layout/tests -t layout/tests -v

For the actual DRC-clean claim (which *does* need KLayout + the PDK), see
``layout/evidence/vco-layout/PROOF.md`` -- this file checks the geometry
this generator *claims* to build, not a substitute for running the deck.
"""

from __future__ import annotations

import sys
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

from floorplan import skeleton  # noqa: E402
from vco import bias_resistors  # noqa: E402
from vco import block as vco_block  # noqa: E402
from vco import buffer as buf  # noqa: E402
from vco import devices as dev  # noqa: E402
from vco import mirror  # noqa: E402
from vco import primitives as prim  # noqa: E402
from vco import ring  # noqa: E402
from vco import vtoi_core  # noqa: E402


def _contains(outer, inner) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and inner.x + inner.w <= outer.x + outer.w
        and inner.y + inner.h <= outer.y + outer.h
    )


def _box(x0: float, y0: float, x1: float, y1: float):
    """A ``klayout.db.Box`` from float microns, on the same 1 nm/dbu grid and
    with the same ``primitives.Canvas._u()`` grid snap the generators draw on
    -- so a box built here compares exactly against a drawn shape's bbox."""
    import klayout.db as db

    grid_dbu = int(round(dev.LAYOUT_GRID_UM * 1000))  # Canvas' own dbu = 1 nm

    def u(v: float) -> int:
        return int(round(v * 1000 / grid_dbu)) * grid_dbu

    return db.Box(u(x0), u(y0), u(x1), u(y1))


class DeviceTableTests(unittest.TestCase):
    """devices.STAGE_FETS matches design/netlist/vco.spice's XMPH/XMP/XMN/XMNT."""

    def test_stage_count_is_five_per_dr003(self):
        self.assertEqual(dev.STAGE_COUNT, 5)

    def test_four_fets_per_stage(self):
        self.assertEqual(len(dev.STAGE_FETS), 4)

    def test_fet_sizes_match_the_frozen_netlist(self):
        sizes = {f.name: (f.w_um, f.l_um) for f in dev.STAGE_FETS}
        self.assertEqual(sizes["MPH"], (10.0, 0.5))
        self.assertEqual(sizes["MP"], (5.0, 0.28))
        self.assertEqual(sizes["MN"], (2.0, 0.28))
        self.assertEqual(sizes["MNT"], (4.0, 0.5))

    def test_stack_order_is_vdd_to_gnd(self):
        # MPH.top=VDD, MPH.bottom=NH=MP.top, MP.bottom=Y=MN.top,
        # MN.bottom=NT=MNT.top, MNT.bottom=VSS -- see devices.py docstring.
        fets = {f.name: f for f in dev.STAGE_FETS}
        self.assertEqual(fets["MPH"].top_net, "VDD")
        self.assertEqual(fets["MPH"].bottom_net, fets["MP"].top_net)
        self.assertEqual(fets["MP"].bottom_net, fets["MN"].top_net)
        self.assertEqual(fets["MN"].bottom_net, fets["MNT"].top_net)
        self.assertEqual(fets["MNT"].bottom_net, "VSS")

    def test_decap_matches_vco_sch(self):
        self.assertEqual(dev.DECAP_COUNT, 2)
        self.assertAlmostEqual(dev.DECAP_SIZE_UM, 50.0)


class FootprintConsistencyTests(unittest.TestCase):
    """ring.footprint_um()'s pure-Python prediction vs. this module's own
    generator constants -- catches the formula drifting out of sync with
    primitives.py's actual margins without needing a KLayout run."""

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = ring.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_stage_pitch_clears_the_widest_device(self):
        widest_w = max(f.w_um for f in dev.STAGE_FETS)
        self.assertGreater(ring.STAGE_PITCH_UM, widest_w)

    def test_pmos_x_range_spans_all_five_stages(self):
        x0, x1 = ring.pmos_x_range()
        self.assertEqual(x0, 0.0)
        self.assertAlmostEqual(x1, (dev.STAGE_COUNT - 1) * ring.STAGE_PITCH_UM + 10.0)

    def test_pmos_band_sits_above_the_nmos_band_with_dr16_clearance(self):
        # DF.16_LV: nwell edge to NMOS comp outside it >= 0.43 um -- see
        # primitives.py's NWELL_TO_NMOS_GAP_UM docstring for why the actual
        # gap is much larger (room for the inner tap band too).
        y0, y1 = ring.pmos_y_range()
        self.assertGreater(y0, 0.0)
        self.assertGreater(y1, y0)
        self.assertGreaterEqual(prim.NWELL_TO_NMOS_GAP_UM, dev.DRC_NWELL_TO_NCOMP_OUT_UM)


class TapPitchTests(unittest.TestCase):
    """Test plan edge case: guard-ring tap pitch <= 15 um *everywhere*
    inside the block, not just at the block perimeter (DF.13_MV/DF.14_MV,
    PLL-FLOORPLAN.md section 1)."""

    def test_pmos_devices_are_within_the_drc_tap_pitch_bound(self):
        self.assertLessEqual(ring.max_pmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM)

    def test_nmos_devices_are_within_the_drc_tap_pitch_bound(self):
        self.assertLessEqual(ring.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM)

    def test_tap_pitch_has_real_margin_not_just_barely_under(self):
        # A generator that DRC-passes today but sits within a rounding error
        # of the 15 um bound is one schematic tweak away from failing --
        # assert real headroom, not just "<=".
        self.assertLess(ring.max_pmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)
        self.assertLess(ring.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)


class FloorplanIntegrationTests(unittest.TestCase):
    """layout/floorplan/skeleton.py's VCO_CORE/VCO_RING (issue #293's
    "replace/augment the VCO_CORE placeholder" acceptance criterion)."""

    def test_vco_ring_matches_the_real_generator_footprint(self):
        # ``with_decap=False``: inside the assembled block the 22 pF decap is
        # placed once, by block.py, against the *block's* own VDD_VCO
        # pin/ring-tap junction -- so the ring rectangle here is the ring's
        # own devices-and-guard-ring extent, not its standalone
        # decap-inflated one (block.py's docstring, ring.build(draw_decap=)).
        x0, y0, x1, y1 = ring.footprint_um(with_decap=False)
        self.assertAlmostEqual(skeleton.VCO_RING.w, x1 - x0)
        self.assertAlmostEqual(skeleton.VCO_RING.h, y1 - y0)

    def test_vco_ring_sits_inside_the_widened_vco_core(self):
        # skeleton.py stacks the three real sub-blocks inside VCO_CORE with a
        # margin; the containment check that actually matters is that
        # VCO_CORE was widened to fit them rather than left stale at 140 um.
        self.assertTrue(_contains(skeleton.VCO_CORE, skeleton.VCO_RING))

    def test_vco_core_width_deviates_from_the_stale_140um_rom_estimate(self):
        # Explicit, disclosed deviation (issue #293 AC) -- the real ring is
        # wider than the original square ROM guess (one row of 5 stages,
        # full-custom -- see ring.py's module docstring).
        self.assertGreater(skeleton.VCO_CORE.w, 140.0)

    def test_vco_decap_sub_blocks_are_unchanged_by_the_real_ring(self):
        # The pre-existing decap markers (#17) keep their own committed
        # geometry regardless of VCO_RING being added alongside them.
        for decap in (skeleton.VCO_DECAP_0, skeleton.VCO_DECAP_1):
            self.assertAlmostEqual(decap.w, 50.0)
            self.assertAlmostEqual(decap.h, 50.0)


class RingReferenceNetlistTests(unittest.TestCase):
    """ring.reference_netlist() -- ring.py's own standalone LVS testbench
    (issue #371), the same role buffer.reference_netlist() plays for
    buffer.py (issue #372)."""

    def test_subckt_ports_and_device_count(self):
        text = ring.reference_netlist()
        y_ports = " ".join(f"Y{i + 1}" for i in range(dev.STAGE_COUNT))
        self.assertIn(f".subckt {ring.TOP_CELL} VBP VBN VDD_VCO GND_VCO {y_ports}", text)
        self.assertIn(".ends", text)
        # 4 fets/stage * STAGE_COUNT stages, one M_ line each.
        self.assertEqual(text.count("\nM_"), 4 * dev.STAGE_COUNT)

    def test_every_stage_uses_the_frozen_stage_fets_sizes(self):
        text = ring.reference_netlist()
        for i in range(dev.STAGE_COUNT):
            for f in dev.STAGE_FETS:
                self.assertIn(f"W={f.drawn_w_um}u L={f.l_um}u", text)
                self.assertIn(f"M_S{i + 1}_{f.name} ", text)

    def test_wraparound_chain_topology(self):
        # Y5 -> A1 (stage 1's own gate net is Y5, not "Y0"); every other
        # stage's A is the previous stage's own Y.
        text = ring.reference_netlist()
        lines = [ln for ln in text.splitlines() if ln.startswith("M_S1_MN ")]
        self.assertEqual(len(lines), 1)
        self.assertIn(" Y5 ", lines[0])  # MN's own gate net (A) for stage 1


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class RingMetal1NetSeparationTests(unittest.TestCase):
    """No Metal1 polygon in ring.py carries two nets (issues #368/#371).

    The reproduction script from
    ``layout/evidence/vco-layout/PROOF-368-rootcause.md`` run as a unit
    test, same construction as ``OutputBufferMetal1NetSeparationTests``.
    On ``main`` before this fix, ring.py's own standalone GDS had two
    merged polygons: one carrying ``GND_VCO``/``VBN``/every chain net at
    once, another carrying ``VBP``/``VDD_VCO``.

    ``VBP``/``VBN`` are deliberately absent from this check -- issue #371
    moved them off Metal1 entirely (onto a shared Metal2 trunk, labelled
    with ``metal2_label`` -- see ring.py's own "SUPPLY/BIAS RAIL GEOMETRY"
    module docstring section on why a full-row Metal1 rail cannot work for
    either), so they carry no Metal1 label to check here at all.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.result = ring.build(draw_decap=False)
        canvas = cls.result.canvas
        cls.layout = canvas.layout
        m1 = db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal1"]))).merged()
        cls.polys = list(m1.each_merged())
        cls.labels = [
            (s.text.string, s.text.x, s.text.y)
            for s in canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal1_label"])).each()
            if s.is_text()
        ]
        cls.nets_on_poly = {}
        cls.unplaced = []
        for name, x, y in cls.labels:
            pt = db.Point(x, y)
            hit = None
            for i, p in enumerate(cls.polys):
                if p.bbox().contains(pt) and not (
                    db.Region(p) & db.Region(db.Box(pt.x - 1, pt.y - 1, pt.x + 1, pt.y + 1))
                ).is_empty():
                    hit = i
                    break
            if hit is None:
                cls.unplaced.append(name)
            else:
                cls.nets_on_poly.setdefault(hit, set()).add(name)

    def test_every_pin_label_actually_lands_on_metal1(self):
        self.assertEqual(self.unplaced, [])
        self.assertTrue(self.labels)

    def test_no_merged_metal1_polygon_carries_two_different_nets(self):
        # "Different nets" -- S<i>.Y / Y<i> (and, for stage 5, Y5_CLK_IN)
        # are deliberate aliases of the *same* physical net (issue #367),
        # not a short; strip the "S<i>." instance prefix and the
        # "_CLK_IN" suffix before comparing.
        def canon(name: str) -> str:
            # "S<i>.Y" -> "Y<i>" (its own per-instance alias of the chain
            # net -- issue #367); "Y5_CLK_IN" -> "Y5" (the pre-buffer output
            # pin, same physical pad as stage 5's own Y).
            if name.startswith("S") and name.endswith(".Y"):
                return "Y" + name[1:-2]
            return "Y5" if name == "Y5_CLK_IN" else name

        shorted = {
            str(self.polys[i].bbox()): sorted(names)
            for i, names in self.nets_on_poly.items()
            if len({canon(n) for n in names}) > 1
        }
        self.assertEqual(shorted, {})

    def test_vdd_vco_and_gnd_vco_are_each_exactly_one_merged_polygon(self):
        per_net = {}
        for i, names in self.nets_on_poly.items():
            for name in names:
                per_net.setdefault(name, set()).add(i)
        for net in ("VDD_VCO", "GND_VCO"):
            self.assertEqual(len(per_net[net]), 1, f"{net}: {per_net[net]}")


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class RingBiasTrunkTests(unittest.TestCase):
    """VBP/VBN's own Metal2 trunks (issue #371, item 4): every stage's
    natural bias-gate pad reaches the trunk, the trunk carries no other
    net's Metal2 (no ``via1_stack()`` sneaking a foreign net onto it), and
    a fresh reproduction against a *combined* ``vco_block`` (issue #368's
    own connectivity_report()) no longer reports ``VBP``/``VBN`` shorted to
    anything -- covered by ``AssembledVcoBlockConnectivityTests`` already;
    this class checks ring.py's own standalone Metal2 in isolation.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.result = ring.build(draw_decap=False)
        canvas = cls.result.canvas
        m2 = db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal2"]))).merged()
        cls.polys = list(m2.each_merged())
        cls.labels = [
            (s.text.string, s.text.x, s.text.y)
            for s in canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal2_label"])).each()
            if s.is_text()
        ]

    def _poly_index_for(self, name: str) -> int:
        for label_name, x, y in self.labels:
            if label_name != name:
                continue
            pt = self.db.Point(x, y)
            for i, p in enumerate(self.polys):
                if p.bbox().contains(pt) and not (
                    self.db.Region(p) & self.db.Region(self.db.Box(pt.x - 1, pt.y - 1, pt.x + 1, pt.y + 1))
                ).is_empty():
                    return i
        raise AssertionError(f"no Metal2 polygon found for {name!r} pin label")

    def test_vbp_and_vbn_each_have_a_metal2_pin(self):
        names = {n for n, _, _ in self.labels}
        self.assertEqual(names, {"VBP", "VBN"})

    def test_vbp_and_vbn_are_on_different_metal2_polygons(self):
        self.assertNotEqual(self._poly_index_for("VBP"), self._poly_index_for("VBN"))

    def test_vbn_trunk_stays_below_wrap_y(self):
        # Both wraparound risers stop *at* wrap_y (issue #371, item 3) --
        # VBN's own trunk (item 4) has to stay below that unconditionally.
        # The merged VBN polygon also includes each stage's own vertical
        # riser up to its natural pad (well above wrap_y), so this checks
        # the trunk's own *bottom* edge -- the polygon's lowest point,
        # necessarily on the horizontal trunk itself -- rather than the
        # whole shape's bbox top.
        i = self._poly_index_for("VBN")
        self.assertAlmostEqual(self.polys[i].bbox().bottom / 1000.0, ring.VBN_TRUNK_Y_UM - prim.METAL2_WIRE_WIDTH_UM / 2.0)
        self.assertLess(ring.VBN_TRUNK_Y_UM, -ring.WRAP_ROUTE_Y_OFFSET_UM)

    def test_vbp_trunk_stays_above_the_tap_ring(self):
        # Mirrors the VBN check above: VBP's merged polygon also reaches
        # down to every stage's own natural pad, so this checks the
        # trunk's own *top* edge (its highest point) against the tap
        # ring's own top band.
        pmos_x0, pmos_x1 = ring.pmos_x_range()
        pmos_y0, pmos_y1 = ring.pmos_y_range()
        tap_ring_top = pmos_y1 + ring.TAP_GAP_UM + ring.TAP_RING_WIDTH_UM
        vbp_trunk_y = tap_ring_top + ring.VBP_TRUNK_CLEARANCE_UM
        i = self._poly_index_for("VBP")
        self.assertAlmostEqual(self.polys[i].bbox().top / 1000.0, vbp_trunk_y + prim.METAL2_WIRE_WIDTH_UM / 2.0)
        self.assertGreater(vbp_trunk_y, tap_ring_top)


class OutputBufferTests(unittest.TestCase):
    """devices.BUFFER_STAGES / buffer.py -- vco.sch's XMBP1..XMBN3 taper."""

    def test_stage_sizes_match_the_frozen_netlist(self):
        sizes = [(s.pfet.w_um, s.nfet.w_um) for s in dev.BUFFER_STAGES]
        self.assertEqual(sizes, [(1.25, 0.5), (3.75, 1.5), (11.25, 4.5)])
        for s in dev.BUFFER_STAGES:
            self.assertAlmostEqual(s.pfet.l_um, 0.28)
            self.assertAlmostEqual(s.nfet.l_um, 0.28)

    def test_stage_chain_nets_match_vco_sch(self):
        # Y5 -> NB1 -> NB2 -> CLK, each stage's output feeding the next input.
        self.assertEqual(dev.BUFFER_STAGES[0].in_net, dev.BUFFER_IN_NET)
        for a, b in zip(dev.BUFFER_STAGES, dev.BUFFER_STAGES[1:]):
            self.assertEqual(a.out_net, b.in_net)
        self.assertEqual(dev.BUFFER_STAGES[-1].out_net, dev.BUFFER_OUT_NET)

    def test_taper_increases_monotonically(self):
        widths = [s.pfet.w_um for s in dev.BUFFER_STAGES]
        self.assertEqual(widths, sorted(widths))
        self.assertGreater(widths[-1], widths[0])

    def test_largest_stage_is_the_one_nearest_the_clk_pin(self):
        # PLL-FLOORPLAN.md section 1: the largest, fastest-switching stage
        # sits closest to the CLK pin and farthest from the ring's starved
        # internal nodes. The CLK pin is on the block's right edge, the Y5
        # input on its left, so this is checked against the drawn x's rather
        # than trusted from BUFFER_STAGES' own tuple order.
        centers = buf.stage_center_x_um()
        x_clk = buf.footprint_um()[2]
        by_distance = sorted(zip(centers, dev.BUFFER_STAGES), key=lambda t: abs(x_clk - t[0]))
        self.assertEqual(by_distance[0][1].pfet.w_um, max(s.pfet.w_um for s in dev.BUFFER_STAGES))
        self.assertEqual(by_distance[-1][1].pfet.w_um, min(s.pfet.w_um for s in dev.BUFFER_STAGES))

    def test_column_pitch_clears_each_stage_own_widest_device(self):
        xs = buf.column_x0_um()
        for x0, x1, st in zip(xs, xs[1:], dev.BUFFER_STAGES):
            self.assertGreaterEqual(x1 - x0, st.max_w_um + buf.COL_GAP_UM)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = buf.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_tap_pitch_bound_with_real_margin(self):
        for d in (buf.max_pmos_tap_distance_um(), buf.max_nmos_tap_distance_um()):
            self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM / 2.0)

    def test_reference_netlist_covers_every_stage_against_the_frozen_sizes(self):
        # buffer.py's own standalone LVS testbench (issue #372). Checked
        # against BUFFER_STAGES rather than a golden string so it cannot
        # drift from the device table the layout is drawn from.
        text = buf.reference_netlist()
        self.assertIn(f".subckt {buf.TOP_CELL} {dev.BUFFER_IN_NET} {dev.BUFFER_OUT_NET} VDD_VCO GND_VCO", text)
        self.assertIn(".ends", text)
        for st in dev.BUFFER_STAGES:
            for f, bulk in ((st.pfet, "VDD_VCO"), (st.nfet, "GND_VCO")):
                self.assertIn(
                    f"M_{f.name} {f.top_net} {f.gate_net} {f.bottom_net} {bulk} "
                    f"{f.kind}_03v3 W={f.drawn_w_um}u L={f.l_um}u",
                    text,
                )


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class OutputBufferMetal1NetSeparationTests(unittest.TestCase):
    """No Metal1 polygon in buffer.py carries two nets (issues #368/#372).

    This is the reproduction script from
    ``layout/evidence/vco-layout/PROOF-368-rootcause.md`` run as a unit
    test: merge every Metal1 shape, drop each Metal1 *label* (datatype 10 --
    the purpose gf180mcu's own LVS deck reads net names from) onto the
    polygon under it, and assert no polygon ends up carrying more than one
    name. On ``main`` before this fix, one polygon carried all seven of
    ``BUF1.NB1``/``BUF2.NB2``/``BUF3.CLK``/``CLK``/``GND_VCO``/``VDD_VCO``/
    ``Y5``.

    Why it is a test and not just a proof document: this failure mode is
    structurally invisible to DRC -- two Metal1 shapes that touch merge into
    one polygon *before* any spacing rule runs, so a short is never a
    violation -- and invisible to ``block.connectivity_report()``, whose
    probe list only asks whether same-net conductors reach each other, never
    whether different-net ones stay apart.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.result = buf.build()
        canvas = cls.result.canvas
        cls.layout = canvas.layout
        m1 = db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal1"]))).merged()
        cls.polys = list(m1.each_merged())
        cls.labels = [
            (s.text.string, s.text.x, s.text.y)
            for s in canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal1_label"])).each()
            if s.is_text()
        ]
        # label -> indices of the merged polygons it lands on
        cls.nets_on_poly = {}
        cls.unplaced = []
        for name, x, y in cls.labels:
            pt = db.Point(x, y)
            hit = None
            for i, p in enumerate(cls.polys):
                if p.bbox().contains(pt) and not (
                    db.Region(p) & db.Region(db.Box(pt.x - 1, pt.y - 1, pt.x + 1, pt.y + 1))
                ).is_empty():
                    hit = i
                    break
            if hit is None:
                cls.unplaced.append(name)
            else:
                cls.nets_on_poly.setdefault(hit, set()).add(name)

    def test_every_pin_label_actually_lands_on_metal1(self):
        self.assertEqual(self.unplaced, [])
        self.assertTrue(self.labels)

    def test_no_merged_metal1_polygon_carries_two_net_names(self):
        shorted = {
            str(self.polys[i].bbox()): sorted(names)
            for i, names in self.nets_on_poly.items()
            if len(names) > 1
        }
        self.assertEqual(shorted, {})

    def test_each_net_is_exactly_one_merged_polygon(self):
        # The other half of the #368 root cause: the rails, the n-well tap
        # bands and the guard ring were *four separately-labelled Metal1
        # islands never joined by any drawn metal*. A net spread across more
        # than one merged polygon is that bug -- which the short above used
        # to hide, and which removing the short alone would have exposed as
        # genuinely floating device terminals.
        per_net = {}
        for i, names in self.nets_on_poly.items():
            for name in names:
                per_net.setdefault(name, set()).add(i)
        self.assertEqual({n: len(v) for n, v in per_net.items()}, {n: 1 for n in per_net})
        self.assertEqual(
            set(per_net),
            {"VDD_VCO", "GND_VCO", dev.BUFFER_IN_NET, dev.BUFFER_OUT_NET, "NB1", "NB2"},
        )


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class OutputBufferSupplyRailTests(unittest.TestCase):
    """The supply rails clear every gate pad, and reach their own rings.

    The gate-pad overlap is structural, not incidental: ``mosfet()``'s gate
    pad and its adjacent terminal pad overlap in y by ``0.26 - l/2`` um
    (0.12 um at these 0.28 um-long inverter fets), so *any* rail drawn at a
    terminal pad's own y and stretched across the row necessarily lands on
    the other stages' gate tabs. These assertions run against the boxes
    ``build()`` actually drew.
    """

    @classmethod
    def setUpClass(cls):
        cls.result = buf.build()
        cls.taps = (
            min(p.pmos_y0 for p in cls.result.stage_ports) - buf.TAP_GAP_UM - buf.TAP_RING_WIDTH_UM,
            max(p.pmos_y1 for p in cls.result.stage_ports) + buf.TAP_GAP_UM + buf.TAP_RING_WIDTH_UM,
        )

    def test_rails_clear_every_gate_pad_by_m1_2a(self):
        self.assertGreaterEqual(self.result.rail_gate_clearance_um, dev.DRC_METAL1_MIN_SPACE_UM)

    def test_the_clearance_guard_actually_refuses_a_short(self):
        # Negative control for the assertion above, in the same spirit as
        # layout/harness/faults.py's DRC negative controls: a check that has
        # never been seen to fail is not yet evidence of anything. Raising
        # the required spacing past what the layout can give must make
        # build() refuse to draw, not silently emit a shorted layout.
        from unittest import mock

        with mock.patch.object(dev, "DRC_METAL1_MIN_SPACE_UM", 5.0):
            with self.assertRaises(ValueError):
                buf.build()

    def test_each_rail_overlaps_the_ring_that_biases_the_same_net(self):
        # GND_VCO's rail runs into the outer p ring's own Metal1 pad, VDD_VCO's
        # into the n-well tap band's -- by real area (METAL1_PAD_MARGIN_UM of
        # it), not a coincident edge one grid snap away from being no joint.
        margin = prim.METAL1_PAD_MARGIN_UM
        ring_pad_top = self.result.footprint[1] + buf.RING_WIDTH_UM + margin
        gnd = self.result.rail_bands["GND_VCO"]
        self.assertAlmostEqual(ring_pad_top - gnd[1], margin)

        tap_band_pad_bottom = self.taps[1] - buf.TAP_RING_WIDTH_UM - margin
        vdd = self.result.rail_bands["VDD_VCO"]
        self.assertAlmostEqual(vdd[3] - tap_band_pad_bottom, margin)

    def test_rails_span_every_stage_and_meet_their_own_pads(self):
        for net, pad_attr, rail_edge, pad_edge in (
            ("GND_VCO", "gnd_pad", 3, 1),  # rail's top edge == the pad's bottom
            ("VDD_VCO", "vdd_pad", 1, 3),  # rail's bottom edge == the pad's top
        ):
            band = self.result.rail_bands[net]
            for p in self.result.stage_ports:
                pad = getattr(p, pad_attr)
                self.assertLessEqual(band[0], pad[0] + 1e-9)
                self.assertGreaterEqual(band[2], pad[2] - 1e-9)
                self.assertAlmostEqual(band[rail_edge], pad[pad_edge])


class BandSelectMirrorDeviceTests(unittest.TestCase):
    """devices.MIRROR_* matches design/netlist/vco.spice's .subckt vco_bias."""

    def test_cascade_sizes_match_the_floorplan_record(self):
        # PLL-FLOORPLAN.md section 1: "A: pfet 26.5 um / 17.225 um; B: nfet
        # 5 um / 8.6125 um; C: pfet 12.3 um / 78.87 um".
        expected = {
            "A": ("pfet", 26.5, 17.225),
            "B": ("nfet", 5.0, 8.6125),
            "C": ("pfet", 12.3, 78.87),
        }
        for c in dev.MIRROR_CASCADES:
            kind, w_on, w_sw = expected[c.name]
            self.assertEqual(c.kind, kind)
            self.assertAlmostEqual(c.always_on.w_um, w_on)
            self.assertAlmostEqual(c.switched.w_um, w_sw)

    def test_cascade_c_keeps_dr003s_6_4_to_1_largest_ratio(self):
        c = {x.name: x for x in dev.MIRROR_CASCADES}["C"]
        self.assertAlmostEqual(c.switched.w_um / c.always_on.w_um, 6.4, places=1)
        for cascade in dev.MIRROR_CASCADES:
            ratio = cascade.switched.w_um / cascade.always_on.w_um
            self.assertLess(ratio, 6.5, f"cascade {cascade.name} ratio exceeds DR-003's 6.4:1")

    def test_netlist_finger_counts(self):
        by_name = {}
        for c in dev.MIRROR_CASCADES:
            by_name[c.always_on.name] = c.always_on
            by_name[c.switched.name] = c.switched
        self.assertEqual((by_name["MA0"].nf, by_name["MA1"].nf), (2, 2))
        self.assertEqual((by_name["MB0"].nf, by_name["MB1"].nf), (1, 1))
        self.assertEqual((by_name["MC0"].nf, by_name["MC1"].nf), (1, 8))

    def test_only_cascade_b_folds_its_fingers(self):
        # Folding is a real layout-vs-netlist deviation; it must stay
        # confined to the one cascade that structurally requires it.
        folded = [
            leg.name
            for c in dev.MIRROR_CASCADES
            for leg in (c.always_on, c.switched)
            if leg.fingers != leg.nf
        ]
        self.assertEqual(sorted(folded), ["MB0", "MB1"])

    def test_drawn_width_tracks_the_schematic_within_one_grid_step(self):
        # Three legs' per-finger widths are not exact multiples of the 5 nm
        # manufacturing grid, so the drawn W is the nearest grid point.
        for c in dev.MIRROR_CASCADES:
            for leg in (c.always_on, c.switched):
                self.assertLess(
                    leg.w_deviation_frac,
                    5e-4,
                    f"{leg.name}: drawn {leg.drawn_w_um} um vs schematic {leg.w_um} um",
                )
                self.assertAlmostEqual(
                    leg.finger_w_um / dev.LAYOUT_GRID_UM,
                    round(leg.finger_w_um / dev.LAYOUT_GRID_UM),
                    places=6,
                    msg=f"{leg.name}'s finger width is off the manufacturing grid",
                )

    def test_switch_mux_and_load_devices_match_the_netlist(self):
        muxes = {m.cascade: m for m in dev.MIRROR_MUXES}
        self.assertEqual(muxes["A"].on.name, "MSWA0")
        self.assertEqual(muxes["A"].on.gate_net, "B0B")
        self.assertEqual(muxes["A"].off.gate_net, "B0")
        self.assertEqual(muxes["B"].on.kind, "nfet")
        self.assertEqual(muxes["C"].out_net, "GC")
        for mux in dev.MIRROR_MUXES:
            for f in (mux.on, mux.off):
                self.assertAlmostEqual(f.w_um, 2.0)
                self.assertAlmostEqual(f.l_um, 0.5)
        loads = {f.name: f for f in dev.MIRROR_LOADS}
        self.assertEqual(set(loads), {"MDA", "MDB", "MDN", "MMN", "MDP"})
        for name in ("MDA", "MDB", "MDN", "MDP"):
            f = loads[name]
            self.assertEqual(f.gate_net, f.top_net if f.kind == "nfet" else f.bottom_net)


class CommonCentroidTests(unittest.TestCase):
    """The acceptance criterion this whole block exists for: each cascade is
    an interdigitated array whose two legs share a centroid -- generalised
    (issue #336) to a 2-D R x C grid, both x *and* y. Cascade A (2x2) and
    cascade B (1x4) are the R == 1 and "no individual row is a palindrome"
    special cases; cascade C (3x3) is the fully general one."""

    def test_every_cascade_passes_the_generator_own_check(self):
        for c in dev.MIRROR_CASCADES:
            mirror.check_common_centroid(c)  # raises on failure

    def test_leg_centroids_coincide_with_the_array_centre(self):
        for c in dev.MIRROR_CASCADES:
            centre = (mirror.array_width_um(c) / 2.0, mirror.array_height_um(c) / 2.0)
            for leg in ("A", "S"):
                cx, cy = mirror.leg_centroid_um(c, leg)
                self.assertAlmostEqual(cx, centre[0], places=9)
                self.assertAlmostEqual(cy, centre[1], places=9)

    def test_patterns_are_symmetric_under_180_degree_rotation(self):
        for c in dev.MIRROR_CASCADES:
            grid = c.pattern
            rows, cols = len(grid), len(grid[0])
            for r in range(rows):
                self.assertEqual(len(grid[r]), cols, f"cascade {c.name}: ragged row {r}")
                for col in range(cols):
                    self.assertEqual(
                        grid[r][col],
                        grid[rows - 1 - r][cols - 1 - col],
                        f"cascade {c.name}: cell ({r},{col}) breaks 180-degree symmetry",
                    )
            flat = [tag for row in grid for tag in row]
            self.assertEqual(flat.count("A"), c.always_on.fingers)
            self.assertEqual(flat.count("S"), c.switched.fingers)

    def test_a_row_placed_pattern_is_rejected(self):
        # Negative control: the check has to actually reject the layout
        # PLL-FLOORPLAN.md section 1 rules out ("not three separate blobs"),
        # not merely pass on the patterns we happen to ship. Two rows, one
        # leg per row -- the 2-D analogue of the flat "A A S S" this test
        # used before #336's grid generalisation.
        c = {x.name: x for x in dev.MIRROR_CASCADES}["C"]
        row_placed = dev.CascadePair(
            name="C_rowplaced",
            always_on=c.always_on,
            switched=c.switched,
            pattern=(("A", "A"), ("S", "S")),
        )
        with self.assertRaises(ValueError):
            mirror.check_common_centroid(row_placed)

    def test_an_asymmetric_pattern_is_rejected(self):
        # The always-on finger nudged one cell off the grid's own centre --
        # still a single finger surrounded by the switched leg, but no longer
        # 180-degree-symmetric, so the centroid-coincidence proof this check
        # exists for would be false.
        c = {x.name: x for x in dev.MIRROR_CASCADES}["C"]
        skewed = dev.CascadePair(
            name="C_skewed",
            always_on=c.always_on,
            switched=c.switched,
            pattern=(
                ("S", "S", "S"),
                ("A", "S", "S"),
                ("S", "S", "S"),
            ),
        )
        with self.assertRaises(ValueError):
            mirror.check_common_centroid(skewed)

    def test_finger_positions_are_symmetric_about_the_array_centre(self):
        # Stronger than the centroid equality above: 180-degree rotation
        # symmetry with a uniform per-column/per-row pitch must make every
        # finger's own (row, col) position mirror its rotational partner's,
        # which is what actually cancels a linear gradient in either axis.
        for c in dev.MIRROR_CASCADES:
            xs = mirror.finger_x0_um(c)
            ys = mirror.row_y0_um(c)
            widths = c.finger_widths()
            row_h = mirror.device_height_um(c.always_on.l_um)
            total_w = mirror.array_width_um(c)
            total_h = mirror.array_height_um(c)
            rows, cols = len(c.pattern), len(c.pattern[0])
            for r in range(rows):
                for col in range(cols):
                    r2, c2 = rows - 1 - r, cols - 1 - col
                    cx = xs[r][col] + widths[r][col] / 2.0
                    cy = ys[r] + row_h / 2.0
                    cx2 = xs[r2][c2] + widths[r2][c2] / 2.0
                    cy2 = ys[r2] + row_h / 2.0
                    self.assertAlmostEqual(cx + cx2, total_w, places=9)
                    self.assertAlmostEqual(cy + cy2, total_h, places=9)


class MirrorPlanTests(unittest.TestCase):
    """mirror.plan() -- the pure-Python placement the generator draws from."""

    def setUp(self):
        self.plan = mirror.plan()

    def test_every_inter_device_net_has_a_track(self):
        for bank in self.plan.banks:
            for net, rows in bank.net_rows.items():
                self.assertIn(net, mirror.NET_ORDER)
                for row in rows:
                    self.assertIsInstance(bank.track_y(net, row), float)

    def test_nmos_and_pmos_track_groups_are_disjoint_within_every_bank(self):
        # The invariant that makes a Metal1 escape column from one row
        # incapable of touching one from the other row, whatever their x --
        # see mirror.py's NET_ORDER comment. Asserted per bank: after the
        # issue-#324 fold it is deliberately false *globally* (bank 1's lo
        # tracks sit above bank 0's hi tracks), and the cross-bank case is
        # covered by test_banks_do_not_overlap_in_y below instead.
        for bank in self.plan.banks:
            lo = [bank.track_lo[n] for n, r in bank.net_rows.items() if "nfet" in r]
            hi = [bank.track_hi[n] for n, r in bank.net_rows.items() if "pfet" in r]
            self.assertLess(max(lo), min(hi), bank.name)
            # round(): a bank whose own y origin is not 0 accumulates float
            # error in its track y's; the geometry itself is snapped on the
            # way out by Canvas._u (devices.LAYOUT_GRID_UM = 0.005 um), which
            # is three orders of magnitude coarser than this rounding.
            self.assertGreaterEqual(
                round(min(hi) - max(lo), 6), mirror.TRACK_PITCH_UM, bank.name
            )

    def test_multi_group_nets_get_a_link_column_and_single_group_nets_do_not(self):
        # Pre-fold "more than one group" meant "escaped from both rows"; with
        # banks it also means "escaped from more than one bank".
        for net in mirror.NET_ORDER:
            groups = self.plan.net_groups.get(net, set())
            if len(groups) > 1:
                self.assertIn(net, self.plan.link_x, f"{net} spans {groups} but has no link")
            else:
                self.assertNotIn(net, self.plan.link_x)

    def test_link_columns_sit_clear_of_every_banks_transistor_rows(self):
        rows_right = max(
            it.x0 + it.width for it in (self.plan.pmos + self.plan.nmos)
        )
        for net, x in self.plan.link_x.items():
            self.assertGreater(x, rows_right, f"{net}'s link column lands inside a device row")

    def test_metal2_tracks_meet_the_m2_spacing_rule(self):
        for bank in self.plan.banks:
            ys = sorted(set(list(bank.track_lo.values()) + list(bank.track_hi.values())))
            for a, b in zip(ys, ys[1:]):
                self.assertGreaterEqual(
                    b - a - prim.METAL2_WIRE_WIDTH_UM, dev.DRC_METAL2_MIN_SPACE_UM, bank.name
                )

    def test_reserve_rejects_two_nets_closer_than_m1_spacing(self):
        # Negative control for the guard that caught the real short in this
        # generator's first build (MDN's drain pad on MSWA0's gate tab).
        p = mirror.Plan()
        p.reserve("VBN", 10.0, 0.0, 10.44, 20.0)
        p.reserve("VBN", 10.0, 0.0, 10.44, 30.0)  # same net: allowed
        with self.assertRaises(ValueError):
            p.reserve("B0B", 10.5, 5.0, 10.94, 25.0)

    def test_two_gate_buses_fit_in_every_cascade_own_corridor(self):
        for c in dev.MIRROR_CASCADES:
            lo, hi = mirror.gate_bus_y_um(c.always_on.l_um, 0.0)
            self.assertLess(lo, hi)
            self.assertGreaterEqual(hi - lo - prim.METAL1_WIRE_WIDTH_UM, dev.DRC_METAL1_MIN_SPACE_UM)

    def test_tap_pitch_bound_with_real_margin(self):
        # Issue #336's 2-D fold of cascades A and C makes the PMOS bound the
        # mirror's own new worst case: a 3-row array's own farthest (bottom)
        # row is 12.8 um of comp + CC_ROW_GAP_UM-separated rows away from the
        # bank's single top-of-bank VDD_VCO tap band, +TAP_GAP_UM = 13.4 um --
        # a real number this test states rather than a blanket "half the
        # rule" bound that a folded array can no longer meet (same pattern
        # AssembledVcoBlockPlacementTests.test_tap_pitch_bound_holds_for_every_sub_block
        # already uses for the V-to-I core's own worst case, 12.1 um).
        self.assertGreater(mirror.max_pmos_tap_distance_um(), 0.0)
        self.assertLess(mirror.max_pmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM - 1.5)
        self.assertGreater(mirror.max_nmos_tap_distance_um(), 0.0)
        self.assertLess(mirror.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = mirror.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)


class MirrorRowFoldTests(unittest.TestCase):
    """The issue-#324 fold: two banks instead of one row pair.

    The point of the fold is width, so these tests assert the fold is real
    (every device still drawn, exactly once, in a bank that is genuinely
    narrower than the flat row would be) and that the new inter-bank geometry
    -- the substrate tap strip each bank above the first needs -- clears the
    bank below it by the rules it has to clear.
    """

    def setUp(self):
        self.plan = mirror.plan()

    def test_the_fold_draws_every_device_exactly_once(self):
        drawn = [it.name for it in self.plan.pmos] + [it.name for it in self.plan.nmos]
        self.assertEqual(len(drawn), len(set(drawn)), "a device is drawn twice")
        expected = set(mirror.DEVICES) | set(mirror.CASCADES)
        # The cascades' own legs are drawn as the array item, not as fets.
        legs = {c.always_on.name for c in dev.MIRROR_CASCADES} | {
            c.switched.name for c in dev.MIRROR_CASCADES
        }
        self.assertEqual(set(drawn), expected - legs)

    def test_more_than_one_bank_and_each_row_is_left_aligned(self):
        self.assertGreater(len(self.plan.banks), 1, "the rows are not folded at all")
        for bank in self.plan.banks:
            self.assertEqual(bank.pmos[0].x0, 0.0)
            self.assertEqual(bank.nmos[0].x0, 0.0)

    def test_the_widest_bank_is_much_narrower_than_one_flat_row_would_be(self):
        # What the #324 bank fold buys on its own, stated as a number a
        # regression would trip -- independent of issue #336's later 2-D fold
        # of cascades A and C, which is why ``flat_pmos`` uses each item's own
        # (possibly already-folded) width rather than re-deriving a
        # pre-#336 number: #336 narrows both sides of this ratio (a folded
        # cascade is narrower whether it sits alone in a flat row or in a
        # bank), so ~0.63 is the post-#336 ratio the #324 bank fold alone is
        # responsible for, down from ~0.47 pre-#336 -- still comfortably
        # under one flat row, just less dramatically since #336 already did
        # much of the work #324's bank fold used to be the only lever for.
        flat_pmos = sum(it.width for it in self.plan.pmos) + mirror.DEVICE_GAP_UM * (
            len(self.plan.pmos) - 1
        )
        widest = max(bank.row_x1() for bank in self.plan.banks)
        self.assertLess(widest, 0.65 * flat_pmos)

    def test_banks_do_not_overlap_in_y(self):
        # The reason a bank's own lo/hi track invariant is enough: bank k's
        # NMOS row starts above everything bank k-1 draws.
        for lower, upper in zip(self.plan.banks, self.plan.banks[1:]):
            self.assertGreater(upper.nmos_bottom, lower.nwell[3])
            self.assertGreater(min(upper.track_lo.values()), max(lower.track_hi.values()))

    def test_every_bank_above_the_first_carries_its_own_substrate_tap_strip(self):
        self.assertIsNone(self.plan.banks[0].sub_tap, "bank 0 uses the outer ring's own band")
        for bank in self.plan.banks[1:]:
            self.assertIsNotNone(bank.sub_tap, f"{bank.name} has no GND_VCO tap of its own")

    def test_substrate_tap_strips_clear_the_bank_below_and_the_row_above(self):
        for lower, upper in zip(self.plan.banks, self.plan.banks[1:]):
            tap = upper.sub_tap
            # DF.16_LV: n-well to comp outside it.
            self.assertGreaterEqual(tap[1] - lower.nwell[3], dev.DRC_NWELL_TO_NCOMP_OUT_UM)
            # DF.3a_LV: comp to comp -- and enough that the two islands'
            # implants clear each other too (PP.2/NP.2's own 0.4 um).
            self.assertGreaterEqual(upper.nmos_bottom - tap[3], dev.DRC_COMP_MIN_SPACE_UM)
            self.assertGreaterEqual(
                round(
                    (upper.nmos_bottom - prim.IMPLANT_MARGIN_UM)
                    - (tap[3] + prim.IMPLANT_MARGIN_UM),
                    6,
                ),
                dev.DRC_NPLUS_MIN_WIDTH_UM,
            )

    def test_substrate_tap_strips_butt_into_the_blocks_own_guard_ring(self):
        # Drawn as one continuous pcomp shape with the ring's left band, so
        # the extraction sees one GND_VCO net rather than an island tied only
        # through the substrate -- block.connectivity_report() probes this.
        for bank in self.plan.banks[1:]:
            self.assertAlmostEqual(
                bank.sub_tap[0], self.plan.outer[0] + mirror.RING_WIDTH_UM
            )

    def test_only_two_nets_cross_a_bank_boundary(self):
        # Not a rule, a design property the split was chosen for: it is what
        # keeps the link strip the same size it was before the fold.
        crossing = {
            net
            for net, groups in self.plan.net_groups.items()
            if len({bank for bank, _ in groups}) > 1
        }
        self.assertEqual(crossing, {"VBP2", "GC"})

    def test_cascades_a_and_c_are_2d_arrays_and_b_is_not(self):
        # Issue #336: cascade A folds 1x4 -> 2x2, cascade C folds 1x9 -> 3x3;
        # cascade B is untouched (its own single-row layout was never the
        # width bottleneck -- see mirror.py's module docstring).
        shapes = {c.name: (len(c.pattern), len(c.pattern[0])) for c in dev.MIRROR_CASCADES}
        self.assertEqual(shapes["A"], (2, 2))
        self.assertEqual(shapes["B"], (1, 4))
        self.assertEqual(shapes["C"], (3, 3))

    def test_the_2d_fold_narrows_cascade_c_below_its_own_flat_width(self):
        # The number issue #336 exists to move: cascade C alone was 115.18 um
        # wide (PROOF-fold.md), which is why "another row split" (#324's own
        # lever) could not go below it. Folded 3x3, it is well under half.
        self.assertLess(mirror.array_width_um(dev.CASCADE_C), 50.0)
        self.assertGreater(mirror.array_width_um(dev.CASCADE_C), 30.0)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class MirrorConnectivityTests(unittest.TestCase):
    """A 2-D common-centroid array's own internal row-to-row tie (issue
    #336) is a genuinely new electrical-topology claim DRC cannot see: a
    Metal2 riser that stops short of one row's own via1 is DRC-clean and
    completely broken. ``mirror.connectivity_report()`` probes every row of
    every multi-row array's own S/D and gate ties, not just the two end rows
    a weaker probe set could pass with a broken interior row (see that
    function's own docstring)."""

    @classmethod
    def setUpClass(cls):
        cls.result = mirror.build()
        cls.report = mirror.connectivity_report(cls.result)

    def test_every_2d_array_internal_tie_is_one_connected_net(self):
        for name, ok, detail in self.report:
            self.assertTrue(ok, f"{name}: {detail}")

    def test_both_2d_cascades_are_covered(self):
        names = {name for name, _, _ in self.report}
        for cascade_name in ("A", "C"):
            self.assertTrue(
                any(f"({cascade_name})" in n for n in names),
                f"cascade {cascade_name}: no internal-tie probe recorded",
            )

    def test_cascade_c_middle_row_is_probed_not_just_the_two_ends(self):
        # The property a first/last-row-only probe set would silently miss
        # (see connectivity_report()'s own docstring): cascade C is 3 rows,
        # so its escape/rail nets should carry 3 probes each, not 2.
        by_name = {name: detail for name, _, detail in self.report}
        for net in ("VBN (C)", "VDD_VCO (C)"):
            self.assertIn("3 probe(s)", by_name[net], by_name[net])


class GridSnapTests(unittest.TestCase):
    """geom.drc's OFFGRID section runs ongrid(0.005) on every drawn layer."""

    def test_snap_um_lands_on_the_manufacturing_grid(self):
        for v in (0.0, 4.30625, 9.85875, 8.6125, -1.234):
            snapped = dev.snap_um(v)
            self.assertAlmostEqual(snapped / dev.LAYOUT_GRID_UM, round(snapped / dev.LAYOUT_GRID_UM))
            self.assertLessEqual(abs(snapped - v), dev.LAYOUT_GRID_UM / 2.0 + 1e-9)

    def test_via_and_contact_sizes_are_grid_multiples(self):
        # CO.1 and V1.1 are min *and* max rules, so these two sizes have to
        # be exactly representable or every contact/via is a violation.
        for size in (dev.DRC_CONTACT_SIZE_UM, dev.DRC_VIA1_SIZE_UM):
            self.assertAlmostEqual(size / dev.LAYOUT_GRID_UM, round(size / dev.LAYOUT_GRID_UM))

    def test_via1_landing_pad_avoids_the_narrow_metal_special_rules(self):
        pad = dev.DRC_VIA1_SIZE_UM + 2 * prim.VIA1_METAL_ENCLOSE_UM
        self.assertGreaterEqual(pad, dev.DRC_VIA1_EOL_METAL_WIDTH_UM)
        self.assertGreaterEqual(prim.METAL2_WIRE_WIDTH_UM, dev.DRC_VIA1_EOL_METAL_WIDTH_UM)


class VcoSubBlockFloorplanTests(unittest.TestCase):
    """skeleton.py's VCO_RING/VCO_MIRROR/VCO_BUFFER/VCO_VTOI_CORE vs. the
    real generators."""

    def test_sub_block_footprints_match_their_generators(self):
        for block, footprint in (
            (skeleton.VCO_RING, ring.footprint_um(with_decap=False)),
            (skeleton.VCO_MIRROR, mirror.footprint_um()),
            (skeleton.VCO_BUFFER, buf.footprint_um()),
            (skeleton.VCO_VTOI_CORE, vtoi_core.footprint_um()),
        ):
            x0, y0, x1, y1 = footprint
            self.assertAlmostEqual(block.w, x1 - x0)
            self.assertAlmostEqual(block.h, y1 - y0)

    def test_all_four_sub_blocks_sit_inside_vco_core(self):
        for block in (skeleton.VCO_RING, skeleton.VCO_MIRROR, skeleton.VCO_BUFFER, skeleton.VCO_VTOI_CORE):
            self.assertTrue(
                _contains(skeleton.VCO_CORE, block), f"{block.name} escapes VCO_CORE"
            )

    def test_the_four_real_sub_blocks_do_not_overlap_each_other(self):
        blocks = (skeleton.VCO_MIRROR, skeleton.VCO_RING, skeleton.VCO_BUFFER, skeleton.VCO_VTOI_CORE)
        for i, a in enumerate(blocks):
            for b in blocks[i + 1 :]:
                overlap = (
                    a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
                )
                self.assertFalse(overlap, f"{a.name} overlaps {b.name}")

    def test_vco_core_height_now_exceeds_the_rom_estimate(self):
        # Adding the V-to-I core as a fourth real sub-block is the first
        # increment where VCO_CORE.h itself has to grow past the 100 um ROM
        # value -- disclosed explicitly, not silently absorbed (see
        # skeleton.py's own docstring for the exact before/after numbers).
        self.assertGreater(skeleton.VCO_CORE.h, 100.0)
        self.assertGreater(skeleton.VCO_CORE.w, 140.0)

    def test_area_budget_headroom_is_reported_not_silently_exceeded(self):
        # PLL-FLOORPLAN.md section 5's draft target is 0.15 mm^2, measured
        # against the skeleton bounding box -- which was dominated by
        # LOOP_FILTER's own 195 um height, not VCO_CORE's, so VCO_CORE.h
        # growing past 100 um (previous test) does not move this number
        # (see skeleton.py's own docstring for the arithmetic).
        #
        # The lower bound moved from 0.9 to 0.8 of the target when issue
        # #324's row fold cut VCO_CORE's width: it is a "this number changed,
        # go re-read skeleton.py" tripwire, not a floor anything wants to sit
        # against. Both bounds are asserted so a *regression* (the fold being
        # undone) trips it too.
        #
        # SCOPE (issue #310): measured over BLOCKS *excluding* DIVIDER_LOCK.
        # This tripwire's own comment predicted "the next block to land real
        # geometry ... find out here rather than in review", and that is
        # exactly what happened -- the real divider chain (2634.28 x 93.82 um)
        # took the unscoped whole-skeleton extent to ~1.19e6 um^2, ~9x this
        # bound. That overrun is a real finding, stated at skeleton.py's
        # DIVIDER_LOCK definition and asserted by
        # test_floorplan_skeleton.py's own
        # test_total_extent_overrun_is_recorded_and_does_not_grow. It is not
        # re-asserted here, because a VCO-fold regression would then be
        # invisible underneath it; scoping this to the pre-#310 blocks keeps
        # *this* test measuring what it was written to measure.
        used = skeleton.total_extent_um2(skeleton.BLOCKS_EXCLUDING_DIVIDER_LOCK)
        self.assertLess(used, 150_000.0)
        self.assertGreater(used / 150_000.0, 0.8, "budget headroom changed -- re-read skeleton.py")
        self.assertLess(used / 150_000.0, 0.9, "budget headroom changed -- re-read skeleton.py")


class BiasResistorDeviceTests(unittest.TestCase):
    """devices.BIAS_RESISTORS matches design/netlist/vco.spice's XRCG/XROFF/XRDEG."""

    def test_three_resistors_match_the_frozen_netlist(self):
        by_name = {r.name: r for r in dev.BIAS_RESISTORS}
        self.assertEqual(set(by_name), {"RCG", "ROFF", "RDEG"})
        self.assertEqual((by_name["RCG"].w_um, by_name["RCG"].l_um), (1.0, 5.6))
        self.assertEqual((by_name["ROFF"].w_um, by_name["ROFF"].l_um), (1.0, 33.0))
        self.assertEqual((by_name["RDEG"].w_um, by_name["RDEG"].l_um), (1.0, 33.0))

    def test_every_resistor_meets_pres1s_minimum_width(self):
        for r in dev.BIAS_RESISTORS:
            self.assertGreaterEqual(r.w_um, prim.POLY_RES_MIN_WIDTH_UM)

    def test_signal_nodes_match_the_schematic(self):
        by_name = {r.name: r for r in dev.BIAS_RESISTORS}
        self.assertEqual(by_name["RCG"].top_net, "NC")
        self.assertEqual(by_name["ROFF"].top_net, "NOFF")
        self.assertEqual(by_name["RDEG"].top_net, "NVI")
        for r in dev.BIAS_RESISTORS:
            self.assertEqual(r.bottom_net, "GND_VCO")


class BiasResistorsBlockTests(unittest.TestCase):
    """bias_resistors.py -- the standalone poly-resistor block."""

    def test_columns_are_ordered_and_non_overlapping(self):
        xs = bias_resistors.column_x0_um()
        self.assertEqual(len(xs), len(dev.BIAS_RESISTORS))
        for x0, x1, r in zip(xs, xs[1:], dev.BIAS_RESISTORS):
            self.assertGreaterEqual(x1 - x0, r.w_um + bias_resistors.RESISTOR_GAP_UM)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = bias_resistors.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_footprint_contains_the_longest_resistor(self):
        _, outer_y0, _, outer_y1 = bias_resistors.footprint_um()
        poly_y0, poly_y1 = bias_resistors.poly_y_extent_um()
        self.assertLess(outer_y0, poly_y0)
        self.assertGreater(outer_y1, poly_y1)
        self.assertAlmostEqual(poly_y1, max(r.l_um for r in dev.BIAS_RESISTORS) + prim.POLY_RES_EXT_UM)

    def test_tap_pitch_bound_with_real_margin(self):
        # This block's guard-ring bands are left/right (full block height),
        # not top/bottom -- see bias_resistors.py's own module docstring for
        # why that is the correct shape for a narrow, tall block.
        d = bias_resistors.max_tap_distance_um()
        self.assertGreater(d, 0.0)
        self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM / 2.0)


class PolyResistorPrimitiveTests(unittest.TestCase):
    """primitives.poly_resistor()'s pure-Python constants (PRES.* citations)."""

    def test_sab_extension_matches_pres6(self):
        self.assertAlmostEqual(prim.POLY_RES_SAB_EXT_UM, 0.28)

    def test_contact_to_sab_clearance_matches_pres7(self):
        self.assertAlmostEqual(prim.POLY_RES_CONTACT_TO_SAB_UM, 0.22)

    def test_implant_enclosure_meets_pres5(self):
        self.assertGreaterEqual(prim.POLY_RES_IMPLANT_ENC_UM, 0.3)

    def test_poly_extension_leaves_room_for_a_contact_clear_of_sab(self):
        # The contact-land region (POLY_RES_EXT_UM tall) has to fit both
        # CONTACT_ROW_MARGIN_UM (poly enclosure) and
        # POLY_RES_CONTACT_TO_SAB_UM (PRES.7 clearance) with a real contact
        # in between -- this is the arithmetic poly_resistor() relies on.
        usable = (
            prim.POLY_RES_EXT_UM
            - prim.CONTACT_ROW_MARGIN_UM
            - prim.POLY_RES_CONTACT_TO_SAB_UM
        )
        self.assertGreaterEqual(usable, prim.CONTACT_SIZE_UM)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class PolyResistorMarkerLayerTests(unittest.TestCase):
    """Direct geometric confirmation of ``block.RESISTOR_LVS_MODEL``'s own
    docstring claim (issue #378): ``primitives.poly_resistor()`` never draws
    GDS layer ``(62, 0)``.

    gf180mcu's own ``rule_decks/res_derivations.lvs`` uses that layer (an
    unrelated derived layer the deck calls ``resistor``, defined as a plain
    ``get_polygons(62, 0)`` in ``layers_definitions.lvs`` -- nothing to do
    with any layer this repo's own ``primitives.LAYER`` table names, a bare
    GDS-layer-number coincidence) to split every ``poly2``+``sab``+``res_mk``
    shape into exactly two buckets: ``ppolyf_u_h`` (overlaps ``(62, 0)`` --
    then further split into ``ppolyf_u_1k``/``_2k``/``_3k`` by the deck's own
    ``$poly_res`` switch) or plain ``ppolyf_u`` (does not overlap it,
    unconditional, no switch). This test draws one resistor with
    ``primitives.poly_resistor()`` directly and confirms no shape lands on
    ``(62, 0)`` anywhere in the produced layout -- the geometric fact that
    makes ``block.RESISTOR_LVS_MODEL = "ppolyf_u"`` (not ``"ppolyf_u_1k"``)
    correct, independent of any PV/LVS-deck run.
    """

    def test_no_shapes_on_the_switch_controlled_marker_layer(self):
        import klayout.db as db

        canvas = prim.Canvas("poly_resistor_marker_probe")
        prim.poly_resistor(canvas, dev.BIAS_R_RCG, 0.0, 0.0)
        marker_layer_index = canvas.layout.layer(62, 0)
        region = db.Region(canvas.top.begin_shapes_rec(marker_layer_index))
        self.assertTrue(
            region.is_empty(),
            "poly_resistor() drew a shape on GDS layer (62, 0) -- the "
            "res_derivations.lvs 'resistor' marker that would move this "
            "device into the switch-controlled ppolyf_u_h/_1k/_2k/_3k "
            "bucket instead of the plain, unconditional ppolyf_u one",
        )


class VtoiCoreDeviceTests(unittest.TestCase):
    """devices.VTOI_* matches design/vco_bias.sch's V-to-I core transistors."""

    def test_thirteen_devices_match_the_frozen_netlist(self):
        self.assertEqual(len(dev.VTOI_ALL_FETS), 13)
        by_name = {f.name: f for f in dev.VTOI_ALL_FETS}
        self.assertEqual(
            set(by_name),
            {
                "MP1", "MP2", "MN1", "MN2", "MSU1", "MSU2", "MSU3",
                "MPR", "MD1", "MD2", "MOFF", "MVI", "MSUM",
            },
        )

    def test_sizes_match_the_frozen_netlist(self):
        by_name = {f.name: f for f in dev.VTOI_ALL_FETS}
        expected = {
            "MP1": ("pfet", 10.0, 1.0),
            "MP2": ("pfet", 10.0, 1.0),
            "MN1": ("nfet", 1.4, 1.0),
            "MN2": ("nfet", 5.6, 1.0),
            "MSU1": ("pfet", 0.22, 20.0),
            "MSU2": ("nfet", 2.0, 1.0),
            "MSU3": ("nfet", 1.0, 1.0),
            "MPR": ("pfet", 2.5, 1.0),
            "MD1": ("nfet", 2.0, 1.0),
            "MD2": ("nfet", 2.0, 1.0),
            "MOFF": ("nfet", 10.0, 1.0),
            "MVI": ("nfet", 10.0, 1.0),
            "MSUM": ("pfet", 60.0, 1.0),
        }
        for name, (kind, w, l) in expected.items():
            f = by_name[name]
            self.assertEqual(f.kind, kind, name)
            self.assertAlmostEqual(f.w_um, w, msg=name)
            self.assertAlmostEqual(f.l_um, l, msg=name)

    def test_msum_is_the_only_multi_finger_device(self):
        folded = [f.name for f in dev.VTOI_ALL_FETS if f.fingers != 1]
        self.assertEqual(folded, ["MSUM"])
        self.assertEqual(dev.VTOI_MSUM.fingers, 4)

    def test_diode_connections_match_the_schematic(self):
        # MN1, MP2, MD1, MD2, MSUM are all diode-connected (gate == one of
        # their own S/D terminals).
        for name in ("MN1", "MP2", "MD1", "MD2", "MSUM"):
            f = {f.name: f for f in dev.VTOI_ALL_FETS}[name]
            self.assertIn(f.gate_net, (f.top_net, f.bottom_net), name)

    def test_msu1_gate_ties_to_gnd_and_is_last_in_its_row(self):
        self.assertEqual(dev.VTOI_MSU1.gate_net, "GND_VCO")
        self.assertEqual(dev.VTOI_PMOS_ROW[-1].name, "MSU1")

    def test_vbp0_is_the_output_and_feeds_the_mirrors_cascade_a(self):
        self.assertEqual(dev.VTOI_OUT_NET, "VBP0")
        self.assertEqual(dev.CASCADE_A.always_on.gate_net, "VBP0")

    def test_resistor_nets_match_bias_resistors_top_nets(self):
        # NC/NOFF/NVI are shared boundary-pin names with bias_resistors.py's
        # own RCG/ROFF/RDEG top_net fields -- the future wiring increment
        # relies on this exact name match.
        by_top_net = {r.top_net for r in dev.BIAS_RESISTORS}
        self.assertEqual(set(dev.VTOI_RESISTOR_NETS), by_top_net)


class VtoiCorePlanTests(unittest.TestCase):
    """vtoi_core.py's pure-Python placement/routing plan."""

    def test_every_inter_device_net_has_a_track(self):
        p = vtoi_core.plan()
        self.assertEqual(set(p.net_rows) - set(vtoi_core.NET_ORDER), set())

    def test_two_row_nets_get_a_link_column(self):
        p = vtoi_core.plan()
        two_row_nets = {n for n, rows in p.net_rows.items() if rows == {"nfet", "pfet"}}
        self.assertEqual(two_row_nets, {"VBPC", "NA", "NSU", "VFIX", "VBP0"})
        self.assertEqual(set(p.link_x), two_row_nets)

    def test_single_row_nets_get_no_link_column(self):
        p = vtoi_core.plan()
        single_row_nets = {n for n, rows in p.net_rows.items() if len(rows) == 1}
        self.assertEqual(single_row_nets & set(p.link_x), set())

    def test_msu1_gate_is_excluded_from_the_mesh(self):
        # GND_VCO is never a mesh-routed net in this block (see
        # vtoi_core.py's module docstring on MSU1) -- it must not show up in
        # net_rows even though MSU1.gate_net == "GND_VCO".
        p = vtoi_core.plan()
        self.assertNotIn("GND_VCO", p.net_rows)
        self.assertNotIn("VDD_VCO", p.net_rows)

    def test_footprint_has_positive_extent(self):
        x0, y0, x1, y1 = vtoi_core.footprint_um()
        self.assertGreater(x1 - x0, 0.0)
        self.assertGreater(y1 - y0, 0.0)

    def test_msum_footprint_accounts_for_all_four_fingers(self):
        w = vtoi_core.item_width_um(dev.VTOI_MSUM)
        finger_w = dev.VTOI_MSUM.finger_w_um
        expected = 4 * finger_w + 3 * vtoi_core.FINGER_GAP_UM
        self.assertAlmostEqual(w, expected)

    def test_msu1_footprint_is_dog_bone_widened(self):
        # MSU1's own w=0.22 um is narrower than primitives.MIN_SD_CONTACT_
        # WIDTH_UM (0.42 um) -- item_width_um() must report the widened
        # footprint, not the raw schematic W, or the row-placement math
        # would understate this device's real drawn extent.
        w = vtoi_core.item_width_um(dev.VTOI_MSU1)
        self.assertAlmostEqual(w, prim.MIN_SD_CONTACT_WIDTH_UM)
        self.assertGreater(prim.MIN_SD_CONTACT_WIDTH_UM, dev.VTOI_MSU1.w_um)


class VtoiCoreTapPitchTests(unittest.TestCase):
    """Test plan edge case: guard-ring tap pitch <= 15 um everywhere,
    including across MSU1's own L=20 um channel (the block's tallest
    device, per vtoi_core.py's own note on why this block needs a top AND
    a bottom n-well tap band)."""

    def test_pmos_devices_are_within_the_drc_tap_pitch_bound(self):
        d = vtoi_core.max_pmos_tap_distance_um()
        self.assertGreater(d, 0.0)
        self.assertLessEqual(d, dev.DRC_TAP_PITCH_MAX_UM)

    def test_nmos_devices_are_within_the_drc_tap_pitch_bound(self):
        d = vtoi_core.max_nmos_tap_distance_um()
        self.assertGreater(d, 0.0)
        self.assertLessEqual(d, dev.DRC_TAP_PITCH_MAX_UM)

    def test_pmos_tap_pitch_has_real_margin_not_just_barely_under(self):
        # MSU1's own L=20 um channel dominates this block's PMOS row height,
        # so the margin here is real but smaller than the other VCO
        # sub-blocks' own < 7.5 um convention -- 12.1 um is still well clear
        # of the 15 um bound, not a rounding-error pass.
        self.assertLess(vtoi_core.max_pmos_tap_distance_um(), 13.0)

    def test_nmos_tap_pitch_has_real_margin_not_just_barely_under(self):
        self.assertLess(vtoi_core.max_nmos_tap_distance_um(), dev.DRC_TAP_PITCH_MAX_UM / 2.0)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class VtoiCoreNetSeparationTests(unittest.TestCase):
    """``vtoi_core.py``'s PMOS row never shorts an internal net to
    ``VDD_VCO`` (issue #376) -- same reproduction discipline as
    ``RingMetal1NetSeparationTests``/``OutputBufferMetal1NetSeparationTests``,
    extended to a full Metal1/via1/Metal2 connectivity extraction (not just a
    Metal1-label merge check) because four of this row's own five affected
    nets (``NA``, ``VBPC``, ``VFIX``, ``NSU``) carry no boundary pin/label at
    all -- only ``VBP0`` does, which is why ``vco_block``'s own assembled LVS
    could only ever see this as a ``VBP0``/``VDD_VCO`` short.

    On ``main`` before ``vtoi_core._Builder._pmos_row_escape()`` existed,
    every one of the five bottom/gate escapes below extracted onto the same
    cluster as ``VDD_VCO``'s own n-well tap band -- reproduced directly
    against ``klayout.db.LayoutToNetlist`` in
    ``layout/evidence/vco-layout/PROOF-376-vbp0-fix.md``.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.result = vtoi_core.build()
        cls.plan = cls.result.plan
        canvas = cls.result.canvas
        layout = canvas.layout
        l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(layout, canvas.top, []))
        cls.layers = {}
        for name in ("metal1", "via1", "metal2"):
            cls.layers[name] = l2n.make_polygon_layer(layout.layer(*prim.LAYER[name]), name)
        l2n.connect(cls.layers["metal1"])
        l2n.connect(cls.layers["via1"])
        l2n.connect(cls.layers["metal2"])
        l2n.connect(cls.layers["metal1"], cls.layers["via1"])
        l2n.connect(cls.layers["via1"], cls.layers["metal2"])
        l2n.extract_netlist()
        cls.l2n = l2n

    def _cluster(self, x: float, y: float):
        n = self.l2n.probe_net(self.layers["metal1"], self.db.DPoint(x, y))
        self.assertIsNotNone(n, f"no metal1 net found at ({x}, {y})")
        return n.cluster_id

    def _vdd_cluster(self):
        tb = self.plan.tap_band_bottom
        return self._cluster(50.0, (tb[1] + tb[3]) / 2.0)

    def _bottom_pad_cluster(self, name: str):
        it = next(i for i in self.plan.pmos if i.name == name)
        x = it.x0 + it.width / 2.0
        y_bottom = self.plan.pmos_top - vtoi_core.device_height_um(it.fet.l_um)
        return self._cluster(x, y_bottom + 0.02)

    def test_every_pmos_row_bottom_pad_is_distinct_from_vdd_vco(self):
        vdd = self._vdd_cluster()
        for name in ("MP1", "MP2", "MPR", "MSUM", "MSU1"):
            with self.subTest(device=name):
                self.assertNotEqual(
                    self._bottom_pad_cluster(name),
                    vdd,
                    f"{name}'s own bottom (source) pad is shorted to VDD_VCO's "
                    "n-well tap band",
                )

    def test_vbp0_extracts_as_its_own_net_not_merged_with_vdd_vco(self):
        # MSUM's own bottom pad *is* VBP0 (devices.VTOI_MSUM.bottom_net).
        vbp0_cluster = self._bottom_pad_cluster("MSUM")
        self.assertNotEqual(vbp0_cluster, self._vdd_cluster())


@unittest.skipUnless(_HAVE_KLAYOUT, "klayout.db not importable in this environment")
class DogBoneMosfetTests(unittest.TestCase):
    """primitives.mosfet()'s min_sd_width_um dog-bone widening.

    Needs klayout.db: prim.Canvas() draws real geometry, so unlike the rest
    of this file these cases cannot run in the headless (no-PDK/no-KLayout)
    CI job -- same skip guard as test_pfdcp_devgen.py's device-generator
    tests."""

    def test_no_widening_when_min_sd_width_is_none_or_below_w(self):
        # Backward compatibility: every existing caller (min_sd_width_um not
        # passed) must draw exactly the same single-rectangle comp as before.
        for min_sd in (None, 1.0):
            canvas = prim.Canvas(f"dogbone_test_{min_sd}")
            fet = dev.Fet("T", "nfet", w_um=2.0, l_um=0.28, gate_net="G", top_net="D", bottom_net="S")
            ports = prim.mosfet(canvas, fet, 0.0, 0.0, min_sd_width_um=min_sd)
            self.assertAlmostEqual(ports.x1 - ports.x0, 2.0)

    def test_widening_reports_the_widened_footprint(self):
        canvas = prim.Canvas("dogbone_test_widen")
        fet = dev.VTOI_MSU1
        ports = prim.mosfet(
            canvas, fet, 0.0, 0.0, sd_overhang=1.5, min_sd_width_um=prim.MIN_SD_CONTACT_WIDTH_UM
        )
        # Overall footprint is the widened S/D extent, not the raw (narrower) W.
        self.assertAlmostEqual(ports.x1 - ports.x0, prim.MIN_SD_CONTACT_WIDTH_UM)
        self.assertGreater(prim.MIN_SD_CONTACT_WIDTH_UM, fet.w_um)
        # The channel is centered within the widened footprint, so the gate
        # contact tab's own centre sits close to the footprint's own centre
        # (offset only by the tab's fixed geometry, not by W).
        footprint_centre = (ports.x0 + ports.x1) / 2.0
        self.assertLess(abs(ports.gate_tab_x_center - footprint_centre), 1.0)


class AssembledVcoBlockPlacementTests(unittest.TestCase):
    """``vco/block.py``'s placement -- pure Python, no KLayout.

    Issue #293's final acceptance criteria: all five sub-blocks wired
    together under one dedicated ``GND_VCO`` guard ring, tap pitch <= 15 um
    everywhere inside the block, and the ``VCO_CORE`` placeholder replaced by
    real geometry.
    """

    def setUp(self):
        self.p = vco_block.placement()
        self.boxes = self.p.boxes()

    def test_all_five_sub_blocks_are_present(self):
        self.assertEqual(
            set(self.boxes),
            {"bias_resistors", "vtoi_core", "mirror", "ring", "buffer"},
        )

    def test_sub_blocks_do_not_overlap_each_other(self):
        items = sorted(self.boxes.items())
        for i, (name_a, a) in enumerate(items):
            for name_b, b in items[i + 1 :]:
                overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                self.assertFalse(overlap, f"{name_a} overlaps {name_b}: {a} vs {b}")

    def test_sub_block_guard_rings_clear_each_other_by_more_than_comp_spacing(self):
        # Two adjacent sub-blocks' own guard-ring comp must not merely miss
        # each other -- they have to clear DF.3a_LV. Checked with real margin
        # (1 um, ~3.5x the rule) because these are separate p-tap islands.
        items = sorted(self.boxes.items())
        for i, (name_a, a) in enumerate(items):
            for name_b, b in items[i + 1 :]:
                gap_x = max(b[0] - a[2], a[0] - b[2])
                gap_y = max(b[1] - a[3], a[1] - b[3])
                self.assertGreater(
                    max(gap_x, gap_y),
                    1.0,
                    f"{name_a} and {name_b} are closer than 1 um: {a} vs {b}",
                )

    def test_every_sub_block_sits_inside_the_block_guard_ring(self):
        x0, y0, x1, y1 = self.p.outer
        for name, b in self.boxes.items():
            self.assertTrue(
                x0 < b[0] and y0 < b[1] and b[2] < x1 and b[3] < y1,
                f"{name} escapes the block guard ring: {b} vs {self.p.outer}",
            )

    def test_footprint_is_the_outer_nwell_guard_ring_box(self):
        # Issue #324: the block's outermost geometry is no longer the GND_VCO
        # substrate ring but the VDD_VCO n-well ring concentric outside it.
        self.assertEqual(vco_block.footprint_um(), self.p.boundary)
        self.assertEqual(self.p.boundary, self.p.nwell_ring)

    def test_the_guard_ring_is_two_sided_and_concentric(self):
        # PLL-FLOORPLAN.md section 1: "a real two-sided ring, not a
        # substrate-only one" -- GND_VCO on the substrate side, a VDD_VCO
        # n-well tap ring outside it, each fully enclosing the last.
        sub, tap, nw = self.p.outer, self.p.nwell_tap, self.p.nwell_ring
        for inner, outer_box in ((sub, tap), (tap, nw)):
            self.assertLess(outer_box[0], inner[0])
            self.assertLess(outer_box[1], inner[1])
            self.assertGreater(outer_box[2], inner[2])
            self.assertGreater(outer_box[3], inner[3])

    def test_nwell_ring_meets_the_nwell_and_tap_rules_it_cites(self):
        # NW.1a_LV (n-well width), DF.4d_LV (n-well overlap of its own ncomp),
        # DF.16_LV (n-well to the substrate ring's comp outside it).
        self.assertGreaterEqual(vco_block.NWELL_RING_WIDTH_UM, dev.DRC_NWELL_MIN_WIDTH_UM)
        self.assertGreaterEqual(
            vco_block.NWELL_RING_TAP_INSET_UM, dev.DRC_NWELL_NCOMP_ENCLOSE_UM
        )
        self.assertGreaterEqual(vco_block.NWELL_RING_GAP_UM, dev.DRC_NWELL_TO_NCOMP_OUT_UM)
        # The drawn geometry has to agree with those constants, not just the
        # constants with the rules.
        self.assertAlmostEqual(
            self.p.nwell_ring[0] + vco_block.NWELL_RING_WIDTH_UM + vco_block.NWELL_RING_GAP_UM,
            self.p.outer[0],
        )
        self.assertAlmostEqual(
            self.p.nwell_tap[0] - self.p.nwell_ring[0], vco_block.NWELL_RING_TAP_INSET_UM
        )

    def test_nwell_ring_clears_every_sub_block_nwell_by_nw2b(self):
        # NW.2b_LV: 1.4 um between two n-well shapes. Measured against each
        # sub-block's own guard-ring box, which encloses its n-well.
        for name, b in self.boxes.items():
            gap = min(
                b[0] - self.p.nwell_ring[0],
                b[1] - self.p.nwell_ring[1],
                self.p.nwell_ring[2] - b[2],
                self.p.nwell_ring[3] - b[3],
            )
            self.assertGreater(gap, 1.4, f"{name} sits within NW.2b_LV of the block n-well ring")

    def test_tap_pitch_bound_holds_for_every_sub_block(self):
        # PLL-FLOORPLAN.md section 1 / DF.13_MV / DF.14_MV: <= 15 um to a tap
        # *everywhere inside the block*, not just at its perimeter. Each
        # sub-block keeps its own guard ring inside the assembled block, so
        # the bound is each generator's own worst case. Asserted against each
        # known worst case explicitly (not a blanket "same margin for every
        # sub-block" bound, which would be a false claim about a block that
        # genuinely runs this close for two different, named reasons):
        #
        # * the V-to-I core's PMOS band, 12.1 um, set by MSU1's deliberately
        #   long L=20 um channel (see vtoi_core.py);
        # * the mirror's own PMOS band, 13.4 um after issue #336's 2-D fold
        # of cascades A and C -- a 3-row array's bottom row is that much
        # comp-and-row-gap away from the bank's single top-of-bank tap band
        # (see mirror.py's own test_tap_pitch_bound_with_real_margin).
        #
        # Both are real DRC-clean margins against the 15 um rule (0.9 um and
        # 1.6 um respectively) -- run_pv.py drc confirms 0 violations on the
        # assembled block -- just tighter than the blanket "-2 um" bound this
        # test used before either of them was the block's known worst case.
        pmos_worst = (
            ring.max_pmos_tap_distance_um(),
            mirror.max_pmos_tap_distance_um(),
            buf.max_pmos_tap_distance_um(),
            vtoi_core.max_pmos_tap_distance_um(),
            bias_resistors.max_tap_distance_um(),
        )
        nmos_worst = (
            ring.max_nmos_tap_distance_um(),
            mirror.max_nmos_tap_distance_um(),
            buf.max_nmos_tap_distance_um(),
            vtoi_core.max_nmos_tap_distance_um(),
        )
        for d in pmos_worst:
            self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM - 1.4)
        for d in nmos_worst:
            self.assertLess(d, dev.DRC_TAP_PITCH_MAX_UM - 2.0)

    def test_left_channel_column_order_prevents_crossings(self):
        # The VBP0 riser spans the whole bias-row-to-mirror-row height, so it
        # has to sit OUTSIDE the input-pin column -- every input route runs
        # rightward from its pin and would otherwise cross it.
        blocks_x0 = min(b[0] for b in self.boxes.values())
        self.assertLess(self.p.col_vbp0_x, self.p.left_pin_x)
        self.assertLess(self.p.left_pin_x, blocks_x0)

    def test_right_channel_column_order_prevents_crossings(self):
        # VBP's horizontal run is above VBN's, so VBP takes the inner column;
        # the supply trunk is innermost of all (signals cross it on Metal2).
        blocks_x1 = max(b[2] for b in self.boxes.values())
        self.assertLess(blocks_x1, self.p.vdd_trunk_x)
        self.assertLess(self.p.vdd_trunk_x, self.p.col_vbp_x)
        self.assertLess(self.p.col_vbp_x, self.p.col_vbn_x)
        self.assertLess(self.p.col_vbn_x, self.p.clk_pin_x)

    def test_resistor_riser_column_order_prevents_crossings(self):
        # NVI is the inner column even though its own track is the outer one
        # -- see block.RES_COL_*_OFFSET_UM.
        self.assertLess(self.boxes["vtoi_core"][2], self.p.res_col_nvi_x)
        self.assertLess(self.p.res_col_nvi_x, self.p.res_col_noff_x)
        self.assertLess(self.p.res_col_noff_x, self.boxes["bias_resistors"][0])

    def test_supply_trunk_clears_the_widest_sub_block_guard_ring(self):
        # The Metal1 VDD trunk runs beside the band mirror's own Metal1-covered
        # GND guard ring band -- that gap is a real M1.2a check, not a
        # cosmetic one.
        blocks_x1 = max(b[2] for b in self.boxes.values())
        gap = (self.p.vdd_trunk_x - vco_block.VDD_TRUNK_WIDTH_UM / 2.0) - (
            blocks_x1 + prim.METAL1_PAD_MARGIN_UM
        )
        self.assertGreater(gap, dev.DRC_METAL1_MIN_SPACE_UM)

    def test_rcg_pad_lands_exactly_on_the_v_to_i_core_nc_track(self):
        # placement() picks the resistor block's y offset for this; if the
        # two ever drift the NC route becomes a dogleg nobody designed.
        pad_y = bias_resistors.top_pad_center_um(dev.BIAS_R_RCG)[1] + self.p.dy_res
        self.assertAlmostEqual(pad_y, vtoi_core.plan().track_lo["NC"])

    def test_decap_is_the_committed_pair_of_50um_devices(self):
        boxes = vco_block.decap_boxes_um()
        self.assertEqual(len(boxes), dev.DECAP_COUNT)
        for b in boxes:
            self.assertAlmostEqual(b[2] - b[0], dev.DECAP_SIZE_UM)
            self.assertAlmostEqual(b[3] - b[1], dev.DECAP_SIZE_UM)
        a, c = boxes
        self.assertLess(a[2], c[0])  # side by side, not overlapping

    def test_decap_sits_next_to_the_block_vdd_pin_and_inside_the_guard_ring(self):
        # AC: "placed adjacent to the VDD_VCO pin/ring-tap junction". The
        # block's VDD_VCO pin is on the Metal1 supply trunk, so adjacency is
        # measured against that trunk's own x.
        boxes = vco_block.decap_boxes_um()
        self.assertLess(self.p.vdd_trunk_x - boxes[1][2], 10.0)
        x0, y0, x1, y1 = self.p.outer
        for b in boxes:
            self.assertTrue(x0 < b[0] and y0 < b[1] and b[2] < x1 and b[3] < y1)

    def test_ring_decap_is_suppressed_inside_the_block(self):
        # One marker pair for one physical pair of caps: the ring's own copy
        # is off inside the block, so its rectangle here is the narrower
        # devices-and-guard-ring extent.
        with_decap = ring.footprint_um(with_decap=True)
        without = ring.footprint_um(with_decap=False)
        self.assertLess(without[2], with_decap[2])
        self.assertAlmostEqual(self.boxes["ring"][2] - self.boxes["ring"][0], without[2] - without[0])


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class RectFramePrimitiveTests(unittest.TestCase):
    """``primitives.rect_frame()`` draws a hole, and refuses not to (issue #339).

    Regression cover for the underlying failure class this issue names: PR
    #333's block-level n-well ring was a single filled ``canvas.rect()``
    spanning the ring's outer box, which put every device in the block inside
    n-well. Neither the foundry DRC deck (edge/spacing rules only) nor
    ``connectivity_report()`` (metal-only extraction) can see that -- it only
    surfaces at LVS. ``rect_frame()`` exists so the hollow shape is a single
    named primitive with its own tests, rather than an easily-mistyped
    four-``rect()`` idiom at each call site.
    """

    def _frame_region(self, canvas, layer="nwell"):
        import klayout.db as db

        idx = canvas.layout.layer(*prim.LAYER[layer])
        return db.Region(canvas.top.shapes(idx)).merged()

    def test_the_four_bands_merge_into_one_polygon_with_one_hole(self):
        canvas = prim.Canvas("frame_test")
        prim.rect_frame(canvas, "nwell", 0.0, 0.0, 20.0, 10.0, 1.5)
        region = self._frame_region(canvas)
        self.assertEqual(region.count(), 1)
        poly = next(region.each())
        self.assertEqual(poly.holes(), 1)
        self.assertEqual(poly.bbox(), _box(0.0, 0.0, 20.0, 10.0))

    def test_the_hole_is_the_width_inset_box_and_carries_no_geometry(self):
        import klayout.db as db

        canvas = prim.Canvas("frame_hole_test")
        prim.rect_frame(canvas, "nwell", 0.0, 0.0, 20.0, 10.0, 1.5)
        region = self._frame_region(canvas)
        hole = db.Region(_box(1.5, 1.5, 18.5, 8.5))
        self.assertTrue((region & hole).is_empty())
        # ...and the frame really covers everything outside that hole.
        self.assertTrue((db.Region(_box(0.0, 0.0, 20.0, 10.0)) - hole - region).is_empty())

    def test_a_width_that_would_fill_the_box_is_refused(self):
        canvas = prim.Canvas("frame_reject_test")
        with self.assertRaises(ValueError):
            prim.rect_frame(canvas, "nwell", 0.0, 0.0, 20.0, 10.0, 5.0)
        with self.assertRaises(ValueError):
            prim.rect_frame(canvas, "nwell", 0.0, 0.0, 20.0, 10.0, 0.0)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class AssembledVcoBlockNwellRingGeometryTests(unittest.TestCase):
    """The block-level n-well ring the assembler actually *draws* (issue #339).

    ``AssembledVcoBlockPlacementTests`` above checks the ring's arithmetic
    (``NWELL_RING_*`` against the rules they cite); those assertions are
    blind to *how* the geometry got drawn, which is exactly where PR #333's
    defect lived -- the numbers were fine, a single ``canvas.rect()`` call
    was not. These assertions run against ``build()``'s own canvas instead,
    so this class runs in the same unit-test pass as the rest of the suite
    rather than needing a manual KLayout session or an external
    ``klt ring-check`` invocation to catch a recurrence.
    """

    @classmethod
    def setUpClass(cls):
        import klayout.db as db

        cls.db = db
        cls.result = vco_block.build()
        canvas = cls.result.canvas

        def region(name):
            idx = canvas.layout.layer(*prim.LAYER[name])
            return db.Region(canvas.top.shapes(idx)).merged()

        cls.nwell = region("nwell")
        cls.pplus = region("pplus")
        # comp under poly, with nplus implant == a real NMOS gate-crossing
        # active area. Every actual NMOS device in the block, and nothing
        # else (an n-tap band has no poly over it).
        cls.nmos_gate = region("poly2") & region("comp") & region("nplus")
        p = cls.result.placement
        cls.placement = p
        # The block-level ring is the one merged n-well polygon whose bbox is
        # the whole ring box (``p.nwell_ring``); every other n-well polygon
        # in the layout is a sub-block's own PMOS well, entirely inside this
        # ring's hole.
        ring_polys = [q for q in cls.nwell.each() if q.bbox() == _box(*p.nwell_ring)]
        cls.ring_polys = ring_polys
        cls.block_frame = db.Region(ring_polys) if ring_polys else db.Region()
        w = vco_block.NWELL_RING_WIDTH_UM
        x0, y0, x1, y1 = p.nwell_ring
        cls.nwell_hole = (x0 + w, y0 + w, x1 - w, y1 - w)

    def test_the_block_level_nwell_is_an_annulus_not_a_slab(self):
        # The one assertion that would have failed on PR #333 as first
        # written: `klt ring-check --layers '[[21,0]]'` reported
        # "solid, hole-less region, not an annulus" there.
        self.assertEqual(
            len(self.ring_polys), 1, "no single polygon spans the block-level n-well ring"
        )
        self.assertGreaterEqual(
            self.ring_polys[0].holes(), 1, "the block-level n-well ring has no hole"
        )

    def test_the_annulus_hole_contains_every_sub_block(self):
        hole = self.db.Region(_box(*self.nwell_hole))
        self.assertTrue(
            (self.block_frame & hole).is_empty(),
            "the block-level n-well reaches into its own hole",
        )
        for name, b in self.placement.boxes().items():
            self.assertTrue(
                (self.db.Region(_box(*b)) - hole).is_empty(),
                f"{name} is not fully inside the n-well ring's hole",
            )

    def test_no_nmos_active_area_anywhere_in_the_block_sits_under_nwell(self):
        # Whole-layer, not just the block ring: an NMOS device inside an
        # n-well is not a DRC error the deck can see (its rules are
        # edge/spacing based) and connectivity_report() extracts metal only,
        # so this check is the block's only pre-LVS gate on it.
        self.assertGreater(self.nmos_gate.area(), 0, "no NMOS gate area found -- check broken")
        self.assertTrue(
            (self.nmos_gate & self.nwell).is_empty(),
            "NMOS gate-crossing active area is inside n-well",
        )

    def test_the_block_ring_does_not_engulf_the_substrate_ring_pplus(self):
        # The GND_VCO substrate ring and every sub-block's own p-taps must
        # stay out of the block-level well.
        self.assertTrue(
            (self.block_frame & self.pplus).is_empty(),
            "substrate-tie pplus falls under the block-level n-well ring",
        )

    def test_the_block_ring_carries_its_own_vdd_tied_ntap(self):
        # The ring is only a real well tie if the n-tap comp it exists for is
        # inside the drawn well -- i.e. the frame must not be *so* hollow
        # that it undercuts its own tap band (the opposite failure mode).
        canvas = self.result.canvas
        ntap = (
            self.db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["comp"])))
            & self.db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["nplus"])))
        ).merged()
        ring_band = self.db.Region(_box(*self.placement.nwell_ring)) - self.db.Region(
            _box(*self.nwell_hole)
        )
        band_ntap = ntap & ring_band
        self.assertGreater(band_ntap.area(), 0, "the block-level ring has no n-tap comp at all")
        self.assertTrue(
            (band_ntap - self.nwell).is_empty(),
            "part of the block ring's n-tap comp is outside the drawn n-well",
        )


class AssembledVcoBlockFloorplanTests(unittest.TestCase):
    """``skeleton.py``'s ``VCO_CORE`` is now the assembled block itself."""

    def test_vco_core_is_the_assembled_block_footprint(self):
        x0, y0, x1, y1 = vco_block.footprint_um()
        self.assertAlmostEqual(skeleton.VCO_CORE.w, x1 - x0)
        self.assertAlmostEqual(skeleton.VCO_CORE.h, y1 - y0)

    def test_every_vco_sub_block_rectangle_sits_inside_vco_core(self):
        for block in (
            skeleton.VCO_RING,
            skeleton.VCO_MIRROR,
            skeleton.VCO_BUFFER,
            skeleton.VCO_VTOI_CORE,
            skeleton.VCO_BIAS_RESISTORS,
            skeleton.VCO_DECAP_0,
            skeleton.VCO_DECAP_1,
        ):
            self.assertTrue(_contains(skeleton.VCO_CORE, block), f"{block.name} escapes VCO_CORE")

    def test_real_vco_area_overruns_the_rom_row_and_is_disclosed(self):
        # PLL-FLOORPLAN.md section 5's VCO row is 0.011-0.017 mm^2 ROM. The
        # real block is several times that; the record's own "fail-loud"
        # clause requires the overrun to be stated, which skeleton.py's
        # docstring does. This test pins the fact of the overrun so a future
        # edit cannot quietly re-describe it as within budget.
        area = skeleton.VCO_CORE.w * skeleton.VCO_CORE.h
        self.assertGreater(area, 17_000.0)

    def test_skeleton_bounding_box_headroom_against_the_draft_budget(self):
        # Issue #324's row fold bought back most of the headroom the real VCO
        # layout had eaten: ~148,200 um^2 (1.2 % under) before the fold,
        # ~126,400 um^2 (16 % under) after, *including* the +6.2 um per axis
        # the new block-level n-well guard ring costs. Both bounds are
        # asserted so a regression that unfolds the mirror trips here.
        #
        # SCOPE (issue #310): measured over BLOCKS *excluding* DIVIDER_LOCK --
        # see the identical note on
        # VcoSubBlockFloorplanTests.test_area_budget_headroom_is_reported_not_silently_exceeded.
        # The whole-skeleton number no longer fits the draft budget once the
        # real divider chain is in it; that is asserted, with its magnitude
        # ratcheted, in test_floorplan_skeleton.py.
        extent = skeleton.total_extent_um2(skeleton.BLOCKS_EXCLUDING_DIVIDER_LOCK)
        self.assertLess(extent, 135_000.0)
        self.assertGreater(extent, 115_000.0)

    def test_the_row_fold_actually_reduced_the_block_footprint(self):
        # The pre-fold assembled block (PR #325, recorded in
        # layout/evidence/vco-layout/PROOF-block.md) was 294.78 x 148.18 um =
        # 43,680 um^2, with a substrate-only block ring. This asserts the
        # direction and rough size of the change, so "folded" cannot silently
        # become "unfolded plus a wider ring".
        w, h = skeleton.VCO_CORE.w, skeleton.VCO_CORE.h
        self.assertLess(w, 200.0)
        self.assertLess(w * h, 35_000.0)
        # Height was the currency the width was bought with, and the budget
        # can afford it only while it stays under LOOP_FILTER's own 195 um.
        self.assertGreater(h, 148.18)
        self.assertLess(h, skeleton.LOOP_FILTER.h)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class AssembledVcoBlockConnectivityTests(unittest.TestCase):
    """The routed nets are electrically joined, not merely DRC-legal.

    A Metal2 wire that stops short of its via1 is perfectly clean under the
    DRC deck and completely broken; ``block.connectivity_report()`` extracts
    metal1/via1/metal2 connectivity and probes both ends of every route.
    """

    @classmethod
    def setUpClass(cls):
        cls.report = vco_block.connectivity_report(vco_block.build())

    def test_every_routed_net_is_one_connected_net(self):
        for name, ok, detail in self.report:
            self.assertTrue(ok, f"{name}: {detail}")

    def test_the_report_covers_every_inter_sub_block_net(self):
        names = {name for name, _, _ in self.report}
        for net in ("NC", "NOFF", "NVI", "VBP0", "VBP", "VBN", "Y5", "VDD_VCO", "GND_VCO"):
            self.assertIn(net, names)

    def test_nets_that_must_stay_separate_did_not_merge(self):
        checks = {name for name, _, _ in self.report if "!=" in name}
        self.assertIn("VDD_VCO != GND_VCO", checks)
        self.assertIn("VBP != VBN", checks)


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class PolyResistorPadArithmeticTests(unittest.TestCase):
    """``bias_resistors.top_pad_center_um()`` mirrors what is actually drawn."""

    def test_pure_python_pad_centre_matches_the_drawn_pad(self):
        for res in dev.BIAS_RESISTORS:
            canvas = prim.Canvas(f"pad_centre_{res.name}")
            ports = prim.poly_resistor(canvas, res, 0.0, 0.0)
            drawn = (
                (ports.top_pad[0] + ports.top_pad[2]) / 2.0,
                (ports.top_pad[1] + ports.top_pad[3]) / 2.0,
            )
            self.assertAlmostEqual(bias_resistors.top_pad_center_um(res)[0], drawn[0])
            self.assertAlmostEqual(bias_resistors.top_pad_center_um(res)[1], drawn[1])


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class CanvasOffsetTests(unittest.TestCase):
    """``Canvas.at()`` -- the one mechanism that makes the assembly possible."""

    def test_offset_translates_shapes_and_leaves_the_default_untouched(self):
        import klayout.db as db

        canvas = prim.Canvas("offset_test")
        canvas.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        with canvas.at(10.0, 20.0):
            canvas.rect("metal1", 0.0, 0.0, 1.0, 1.0)
        canvas.rect("metal1", 2.0, 0.0, 3.0, 1.0)
        region = db.Region(canvas.top.shapes(canvas.layout.layer(*prim.LAYER["metal1"])))
        boxes = sorted((s.bbox().left, s.bbox().bottom) for s in region.each())
        self.assertEqual(boxes, [(0, 0), (2000, 0), (10000, 20000)])

    def test_pins_are_recorded_in_absolute_coordinates_and_scoped(self):
        canvas = prim.Canvas("offset_pin_test")
        with canvas.at(5.0, 7.0) as scope:
            canvas.pin("N", 0.0, 0.0, 1.0, 1.0)
        self.assertEqual(scope["N"], [(5.0, 7.0, 6.0, 8.0)])
        self.assertEqual(canvas.pins["N"], [(5.0, 7.0, 6.0, 8.0)])
        # ... and the offset does not leak out of the context manager.
        canvas.pin("M", 0.0, 0.0, 1.0, 1.0)
        self.assertEqual(canvas.pins["M"], [(0.0, 0.0, 1.0, 1.0)])


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class ReferenceNetlistDeviceTests(unittest.TestCase):
    """``block.reference_netlist()`` matches ``devices.py``'s own tables
    (issue #367) -- per-class device count and summed drawn width, the same
    "checked by the run, not asserted" discipline ``devices.Fet.
    w_deviation_frac`` already documents.

    Gated on ``klayout.db`` per the issue's own instruction, even though the
    reference text itself needs no PV environment -- CI's headless job (#349)
    runs this class alongside the rest of the assembled-block suite.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = vco_block.reference_netlist()
        cls.lines = [ln for ln in cls.text.splitlines() if ln.startswith(("M_", "R_"))]

    @staticmethod
    def _param(line: str, key: str) -> float:
        for tok in line.split():
            if tok.startswith(f"{key}="):
                return float(tok[len(key) + 1 :].rstrip("u"))
        raise AssertionError(f"{key}= not found in {line!r}")

    def _expected_fets(self):
        fets = []
        for f in dev.STAGE_FETS:
            fets.extend([f] * dev.STAGE_COUNT)
        for st in dev.BUFFER_STAGES:
            fets.extend([st.pfet, st.nfet])
        for cascade in dev.MIRROR_CASCADES:
            fets.extend([cascade.always_on, cascade.switched])
        for mux in dev.MIRROR_MUXES:
            fets.extend([mux.on, mux.off])
        fets.extend(dev.MIRROR_LOADS)
        for inv in dev.MIRROR_INVERTERS:
            fets.extend([inv.pfet, inv.nfet])
        fets.extend(dev.VTOI_ALL_FETS)
        return fets

    def test_per_class_device_count_and_summed_drawn_width_match(self):
        expected = self._expected_fets()
        for kind, model in (("pfet", " pfet_03v3 "), ("nfet", " nfet_03v3 ")):
            want = [f for f in expected if f.kind == kind]
            got = [ln for ln in self.lines if model in ln]
            self.assertEqual(
                len(got), len(want), f"{kind}: device count mismatch ({len(got)} vs {len(want)})"
            )
            self.assertAlmostEqual(
                sum(self._param(ln, "W") for ln in got),
                sum(f.drawn_w_um for f in want),
                places=6,
                msg=f"{kind}: summed drawn W mismatch",
            )

    def test_resistor_count_and_sizes_match_devices_py(self):
        r_lines = [ln for ln in self.lines if ln.startswith("R_")]
        self.assertEqual(len(r_lines), len(dev.BIAS_RESISTORS))
        for r in dev.BIAS_RESISTORS:
            matches = [ln for ln in r_lines if ln.startswith(f"R_{r.name} ")]
            self.assertEqual(len(matches), 1, r.name)
            self.assertAlmostEqual(self._param(matches[0], "W"), r.w_um)
            self.assertAlmostEqual(self._param(matches[0], "L"), r.l_um)

    def test_resistors_use_the_decks_own_extracted_class_not_the_schematics(self):
        r_lines = [ln for ln in self.lines if ln.startswith("R_")]
        self.assertTrue(r_lines)
        for ln in r_lines:
            self.assertIn(vco_block.RESISTOR_LVS_MODEL, ln)
            self.assertNotIn("ppolyf_u_3k", ln)

    def test_resistor_model_is_the_marker_free_class_not_the_1k_bucket(self):
        """Regression guard for issue #378.

        ``RESISTOR_LVS_MODEL`` briefly named ``"ppolyf_u_1k"`` (the class the
        deck's own ``$poly_res`` switch selects for shapes carrying GDS layer
        ``(62, 0)``, gf180mcu's own ``res_derivations.lvs`` -- see
        ``PolyResistorMarkerLayerTests`` below for the direct geometric
        check) -- but ``primitives.poly_resistor()`` never draws that marker
        layer, so the deck's own extraction always lands every drawn
        resistor in the plain, switch-independent ``ppolyf_u`` bucket
        instead. A reference netlist naming ``"ppolyf_u_1k"`` device-class
        mismatched the actual extracted device (confirmed directly via
        ``klayout.db.LayoutVsSchematic`` cross-reference of the assembled
        ``vco_block`` LVS run -- see
        ``layout/evidence/vco-layout/PROOF-378-resistor-class-fix.md``),
        which is what escalated three internal nets (``NC``/``NOFF``/
        ``NVI``) plus ``GND_VCO`` into a spurious net-level ``Mismatch``
        despite every device individually pairing correctly. Pinned to the
        exact string (not just "not ppolyf_u_3k") so a future revert of
        either constant is caught here rather than only in a full PV run.
        """
        self.assertEqual(vco_block.RESISTOR_LVS_MODEL, "ppolyf_u")

    def test_decap_devices_are_not_emitted(self):
        self.assertNotIn(vco_block.DECAP_LVS_MODEL, self.text)

    def test_top_level_ports_match_the_frozen_netlist(self):
        header = next(ln for ln in self.text.splitlines() if ln.startswith(".subckt"))
        self.assertEqual(
            header.split(),
            [".subckt", "vco_block", "VCTRL", "B0", "B1", "B2", "CLK", "VDD_VCO", "GND_VCO"],
        )


@unittest.skipUnless(_HAVE_KLAYOUT, "needs klayout.db")
class ReferenceNetlistLabelCoverageTests(unittest.TestCase):
    """Every net ``block.py``'s router (or a sub-block generator it calls)
    routes is labelled with the exact name ``reference_netlist()`` gives it,
    on the *label/pin purpose* layer gf180mcu's own LVS deck actually reads
    net names from -- not just this package's own drawing-layer convention
    (issue #367).
    """

    @classmethod
    def setUpClass(cls):
        cls.result = vco_block.build()
        cls.expected_nets = (
            "NC",
            "NOFF",
            "NVI",
            "VBP0",
            "VBP",
            "VBN",
            "Y1",
            "Y2",
            "Y3",
            "Y4",
            "Y5",
            "VDD_VCO",
            "GND_VCO",
            "CLK",
            "VCTRL",
            "B0",
            "B1",
            "B2",
        )

    def test_every_net_reference_netlist_names_is_a_recorded_pin(self):
        for net in self.expected_nets:
            self.assertIn(net, self.result.canvas.pins, net)

    def test_every_net_carries_a_real_label_on_the_decks_own_purpose_layer(self):
        canvas = self.result.canvas
        for layer_name in ("metal1_label", "metal2_label"):
            self.assertIn(layer_name, prim.LAYER)
        labelled = set()
        for layer_name in ("metal1_label", "metal2_label"):
            li = canvas.layout.layer(*prim.LAYER[layer_name])
            for shape in canvas.top.shapes(li).each():
                if shape.is_text():
                    labelled.add(shape.text_string)
        for net in self.expected_nets:
            self.assertIn(net, labelled, net)

    def test_pin_layer_defaults_to_the_label_purpose_not_the_drawing_layer(self):
        self.assertEqual(prim.Canvas.PIN_LAYER, "metal1_label")


if __name__ == "__main__":
    unittest.main()
