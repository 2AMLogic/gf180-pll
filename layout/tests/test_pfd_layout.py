#!/usr/bin/env python3
"""Geometry + connectivity tests for the PFD block layout (issue #300).

Pure Python, no KLayout and no PDK: ``pfd_cp/rowgen.py``'s ``Canvas`` is a
plain shape recorder and every placement/routing decision in ``pfd_cp/pfd.py``
is resolved before anything is written to GDS, so the whole block can be
built and inspected in a bare checkout::

    python3 -m unittest discover -s layout/tests -t layout/tests -v

What these tests are *for*, beyond the usual regression net:

* **The mirror-symmetry claim is checked on the emitted geometry**, not on
  the intent. ``pfd.py`` draws the DN branch through a mirroring proxy, so
  the two branches start out identical by construction -- but the routing is
  added afterwards, at block level, and could quietly break the property.
  ``BranchMirrorSymmetryTests`` clips every drawn shape to the UP branch's
  window and to the reflected DN window and demands the two sets be equal.
* **Shorts and opens are checked here because a DRC deck cannot see them.**
  Two different nets overlapping on one layer merge into a single polygon
  that satisfies every width/space/enclosure rule; a net drawn in two
  disconnected pieces is likewise geometrically legal. Only LVS or an
  explicit connectivity check catches those, and this file is the check that
  runs on every build with no PDK.
* **The placement is checked against ``design/*.sch``**, by parsing the
  schematics: instance names, cell types, and the flattened port-to-net
  connectivity of all 47 leaf instances.

The DRC-clean claim itself needs the foundry deck and lives in
``layout/evidence/pfd-layout/PROOF.md``.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LAYOUT_DIR.parent
DESIGN_DIR = REPO_ROOT / "design"
sys.path.insert(0, str(LAYOUT_DIR))
sys.path.insert(0, str(LAYOUT_DIR / "pll_top"))

from pfd_cp import pfd  # noqa: E402
from pfd_cp import pfd_cells as cells  # noqa: E402
from pfd_cp import rowgen  # noqa: E402

LEAF_SYMBOLS = {"pfdcp_inv_3v3": "inv", "pfdcp_nand2_3v3": "nand2"}

_INST_RE = re.compile(r"^C \{(?:.*/)?([\w.]+)\.sym\}(?:\s+\S+){4}\s+\{name=([\w.]+)")
_LAB_RE = re.compile(r"^C \{devices/lab_pin\.sym\}(?:\s+\S+){4}\s+\{name=l_(\S+)\s+lab=(\S+)\}")
_PIN_RE = re.compile(r"^C \{devices/[io]+pin\.sym\}(?:\s+\S+){4}\s+\{name=\w+\s+lab=(\S+)\}")


class Schematic:
    """The little bit of xschem ``.sch`` a placement check needs.

    Instances (``C {foo.sym} ... {name=xbar}``), their port-to-net
    ``lab_pin`` attachments (``{name=l_xbar_A lab=NET}``) and the subcircuit's
    own boundary pins (``ipin``/``opin``/``iopin``).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.instances: dict[str, str] = {}
        self.pins: list[str] = []
        labels: list[tuple[str, str]] = []
        for line in path.read_text().splitlines():
            m = _INST_RE.match(line)
            if m and not m.group(1).endswith(("lab_pin", "ipin", "opin", "iopin")):
                self.instances[m.group(2)] = m.group(1)
            m = _LAB_RE.match(line)
            if m:
                labels.append((m.group(1), m.group(2)))
            m = _PIN_RE.match(line)
            if m:
                self.pins.append(m.group(1))
        self.conn: dict[str, dict[str, str]] = {name: {} for name in self.instances}
        for tag, net in labels:
            for name in self.instances:
                if tag.startswith(name + "_"):
                    self.conn[name][tag[len(name) + 1 :]] = net
                    break
            else:  # pragma: no cover - a lab_pin with no matching instance
                raise AssertionError(f"{path.name}: lab_pin l_{tag} matches no instance")


def flatten_pfd() -> dict[str, tuple[str, dict[str, str]]]:
    """``design/pfd.sch`` flattened to its 47 leaf instances.

    Returns ``{instance path: (cell kind, {port: net})}`` with hierarchical
    names joined by ``.`` -- the same naming ``pfd.py`` places under.
    """
    top = Schematic(DESIGN_DIR / "pfd.sch")
    subs = {name: Schematic(DESIGN_DIR / f"{name}.sch") for name in ("edgedet", "srlatch")}
    flat: dict[str, tuple[str, dict[str, str]]] = {}
    for inst, symbol in top.instances.items():
        if symbol in LEAF_SYMBOLS:
            flat[inst] = (LEAF_SYMBOLS[symbol], top.conn[inst])
            continue
        sub = subs[symbol]
        boundary = top.conn[inst]

        def rename(net: str, _inst=inst, _sub=sub, _boundary=boundary) -> str:
            return _boundary[net] if net in _sub.pins else f"{_inst}.{net}"

        for sub_inst, sub_symbol in sub.instances.items():
            assert sub_symbol in LEAF_SYMBOLS, f"{symbol}.sch: unexpected {sub_symbol}"
            ports = {p: rename(n) for p, n in sub.conn[sub_inst].items()}
            flat[f"{inst}.{sub_inst}"] = (LEAF_SYMBOLS[sub_symbol], ports)
    return flat


class SchematicTranscriptionTests(unittest.TestCase):
    """Every leaf instance in design/pfd.sch is placed, wired as drawn."""

    @classmethod
    def setUpClass(cls):
        cls.flat = flatten_pfd()
        cls.place = pfd.build_placement()
        cls.by_name = {c.name: c for c in cls.place.cells}

    def test_instance_count_matches_the_schematics(self):
        kinds = [k for k, _ in self.flat.values()]
        self.assertEqual(kinds.count("inv"), 40)
        self.assertEqual(kinds.count("nand2"), 7)
        self.assertEqual(len(self.flat), 47)

    def test_every_schematic_instance_is_placed_exactly_once(self):
        self.assertEqual(set(self.by_name), set(self.flat))
        self.assertEqual(len(self.place.cells), len(self.by_name))

    def test_cell_kinds_match(self):
        for name, (kind, _) in sorted(self.flat.items()):
            self.assertEqual(self.by_name[name].kind, kind, name)

    def test_transistor_count_is_108(self):
        n = sum(len(c.fets) for c in self.place.cells)
        self.assertEqual(n, 108)

    def test_port_nets_match_the_flattened_schematic(self):
        for name, (_, ports) in sorted(self.flat.items()):
            self.assertEqual(self.by_name[name].roles, ports, name)

    def test_device_sizes_match_the_leaf_schematics(self):
        # design/pfdcp_inv_3v3.sch: pfet W=1.5u/L=0.3u, nfet W=0.5u/L=0.3u.
        # design/pfdcp_nand2_3v3.sch: pfet W=1.5u/L=0.3u x2, nfet W=1u/L=0.3u x2.
        for text, sizes in (
            ((DESIGN_DIR / "pfdcp_inv_3v3.sch").read_text(), {("pfet", 1.5), ("nfet", 0.5)}),
            ((DESIGN_DIR / "pfdcp_nand2_3v3.sch").read_text(), {("pfet", 1.5), ("nfet", 1.0)}),
        ):
            for kind, w in sizes:
                model = f"{kind}_03v3"
                self.assertIn(model, text)
            self.assertIn("L=0.3u", text)
        inv = self.by_name["xd1"]
        self.assertEqual({(f.fet.kind, f.fet.w_um, f.fet.l_um) for f in inv.fets},
                         {("pfet", 1.5, 0.3), ("nfet", 0.5, 0.3)})
        nand = self.by_name["xnand_rst"]
        self.assertEqual({(f.fet.kind, f.fet.w_um, f.fet.l_um) for f in nand.fets},
                         {("pfet", 1.5, 0.3), ("nfet", 1.0, 0.3)})
        self.assertEqual(sum(1 for f in nand.fets if f.fet.kind == "pfet"), 2)
        self.assertEqual(sum(1 for f in nand.fets if f.fet.kind == "nfet"), 2)


class PlacementTests(unittest.TestCase):
    """No two cells overlap, and the branches sit where the floorplan says."""

    @classmethod
    def setUpClass(cls):
        cls.place = pfd.build_placement()

    def _spans(self, row: int) -> list[tuple[float, float, str]]:
        return sorted(
            (*cells.real_span(c, pfd.AXIS_X), c.name) for c in self.place.cells if c.row == row
        )

    def test_no_cell_footprints_overlap(self):
        for row in (0, 1):
            spans = self._spans(row)
            for (x0, x1, name), (nx0, _, nname) in zip(spans, spans[1:]):
                self.assertLessEqual(
                    x1, nx0, f"row {row}: {name} overlaps {nname}"
                )

    def test_cell_gaps_are_at_least_the_declared_pitch(self):
        for row in (0, 1):
            spans = self._spans(row)
            for (_, x1, name), (nx0, _, nname) in zip(spans, spans[1:]):
                self.assertGreaterEqual(
                    round(nx0 - x1, 6), pfd.CELL_GAP_UM, f"row {row}: {name} -> {nname}"
                )

    def test_branches_are_on_opposite_sides_of_the_axis(self):
        up = [c for c in self.place.cells if c.row == 0 and not c.mirror and c.name != "xnand_rst"]
        dn = [c for c in self.place.cells if c.row == 0 and c.mirror]
        self.assertEqual(len(up), len(dn))
        self.assertTrue(all(cells.real_span(c, pfd.AXIS_X)[1] < pfd.AXIS_X for c in up))
        self.assertTrue(all(cells.real_span(c, pfd.AXIS_X)[0] > pfd.AXIS_X for c in dn))

    def test_branch_placements_are_mirror_images(self):
        up = {c.name.replace("_ref", "").replace("xinv_sr", "xinv_s"): cells.real_span(c, pfd.AXIS_X)
              for c in self.place.cells if c.row == 0 and not c.mirror and c.name != "xnand_rst"}
        dn = {c.name.replace("_fb", "").replace("xinv_sf", "xinv_s"): cells.real_span(c, pfd.AXIS_X)
              for c in self.place.cells if c.row == 0 and c.mirror}
        self.assertEqual(set(up), set(dn))
        for key, (x0, x1) in up.items():
            self.assertEqual((round(-x1, 6), round(-x0, 6)), dn[key], key)

    def test_reset_nand_straddles_the_axis_symmetrically(self):
        rst = next(c for c in self.place.cells if c.name == "xnand_rst")
        x0, x1 = cells.real_span(rst, pfd.AXIS_X)
        self.assertAlmostEqual(x0 + x1, 2 * pfd.AXIS_X, places=9)
        lanes = {p.net: p.lane for p in rst.ports if p.kind == "full"}
        # A takes UP (left branch), B takes DN (right branch): their gate
        # lanes must be reflections, or the two routes could not be.
        self.assertAlmostEqual(lanes["UP"] + lanes["DN"], 2 * pfd.AXIS_X, places=9)
        self.assertLess(lanes["UP"], pfd.AXIS_X)
        self.assertGreater(lanes["DN"], pfd.AXIS_X)

    def test_shared_reset_path_is_placed_once(self):
        shared = [c.name for c in self.place.cells if c.row == 1]
        self.assertEqual(len(shared), 26)
        self.assertEqual(sorted(shared), sorted(["xinv_r0", "xinv_rb"] + [f"xd{i}" for i in range(1, 25)]))
        self.assertTrue(all(not c.mirror for c in self.place.cells if c.row == 1))


class RoutingTests(unittest.TestCase):
    """Track assignment: mirror pairs share a track; nothing collides."""

    @classmethod
    def setUpClass(cls):
        cls.place = pfd.build_placement()
        cls.tracks = {row: pfd.assign_tracks(cls.place, row) for row in (0, 1)}

    def test_mirror_paired_nets_share_a_track(self):
        pairs = [(u, d) for u, d in pfd.MIRROR_NET_PAIRS.items() if u in self.tracks[0]]
        self.assertGreaterEqual(len(pairs), 10)
        for up_net, dn_net in pairs:
            self.assertIn(dn_net, self.tracks[0], dn_net)
            self.assertEqual(self.tracks[0][up_net], self.tracks[0][dn_net], f"{up_net}/{dn_net}")

    def test_mirror_paired_nets_have_reflected_bus_intervals(self):
        for up_net, dn_net in pfd.MIRROR_NET_PAIRS.items():
            a = pfd.net_interval(self.place, 0, up_net)
            b = pfd.net_interval(self.place, 0, dn_net)
            self.assertEqual(a is None, b is None, up_net)
            if a is None:
                continue
            self.assertEqual((round(-a[1], 6), round(-a[0], 6)), (round(b[0], 6), round(b[1], 6)), up_net)

    def test_nets_sharing_a_track_keep_their_clearance(self):
        for row, assignment in self.tracks.items():
            per_track: dict[int, list[tuple[float, float, str]]] = {}
            for net, track in assignment.items():
                span = pfd.net_interval(self.place, row, net)
                if span is not None:
                    per_track.setdefault(track, []).append((*span, net))
            for track, spans in per_track.items():
                spans.sort()
                for (_, x1, a), (nx0, _, b) in zip(spans, spans[1:]):
                    self.assertGreaterEqual(
                        round(nx0 - x1, 6),
                        rowgen.TRACK_CLEARANCE_UM,
                        f"row {row} track {track}: {a} -> {b}",
                    )

    def test_rb_and_nrst_links_do_not_share_an_x_lane(self):
        rb = self.place.links[(0, "RB")]
        nrst = self.place.links[(0, "NRST")]
        self.assertGreaterEqual(
            abs(rb - nrst), rowgen.METAL3_WIRE_WIDTH_UM + 0.28, "M3.2a needs 0.28 um between links"
        )


class BuiltLayoutTests(unittest.TestCase):
    """Checks on the drawn geometry itself."""

    @classmethod
    def setUpClass(cls):
        cls.layout = pfd.build()

    def test_no_two_nets_are_shorted(self):
        self.assertEqual(rowgen.shorted_pairs(self.layout.conductors), [])

    def test_every_net_is_one_connected_island(self):
        self.assertEqual(rowgen.disconnected_nets(self.layout.conductors, self.layout.vias), [])

    def test_net_count_matches_the_flattened_schematic(self):
        drawn = {c[0] for c in self.layout.conductors}
        flat = flatten_pfd()
        expected = {net for _, ports in flat.values() for net in ports.values()}
        expected |= {f"{name}.NI" for name, (kind, _) in flat.items() if kind == "nand2"}
        self.assertEqual(drawn, expected)

    def test_footprint_is_wider_than_tall_and_within_the_rom_budget(self):
        x0, y0, x1, y1 = self.layout.footprint()
        area = (x1 - x0) * (y1 - y0)
        # PLL-FLOORPLAN.md section 5 budgets 10,000-20,000 um^2 for the whole
        # PFD + charge pump + dump buffer. The PFD alone must leave room.
        self.assertLess(area, 6000.0)
        self.assertGreater(area, 500.0)

    def test_rows_do_not_overlap_in_y(self):
        row0, row1 = self.layout.rows
        self.assertGreaterEqual(
            round(row1.y_bottom - row0.y_top, 6), 0.0, "row 1's taps run into row 0's nwell"
        )


class BranchMirrorSymmetryTests(unittest.TestCase):
    """The two branches are literal reflections about the axis.

    Checked on every drawn shape, on every layer, after routing -- clipping
    the design to the UP branch's window and to the reflection of the DN
    branch's window and comparing the two shape multisets.
    """

    MARGIN_UM = 0.6

    @classmethod
    def setUpClass(cls):
        cls.layout = pfd.build()
        up = [
            c
            for c in cls.layout.placement.cells
            if c.row == 0 and not c.mirror and c.name != "xnand_rst"
        ]
        spans = [cells.real_span(c, pfd.AXIS_X) for c in up]
        cls.x_lo = min(s[0] for s in spans) - cls.MARGIN_UM
        cls.x_hi = max(s[1] for s in spans) + cls.MARGIN_UM
        row0 = cls.layout.rows[0]
        cls.y_lo = row0.y_bottom - 0.5
        cls.y_hi = row0.y_top + 0.5

    def _clip(self, x_lo: float, x_hi: float):
        out = []
        for layer, a0, b0, a1, b1 in self.layout.canvas.shapes:
            if a1 <= x_lo or a0 >= x_hi or b1 <= self.y_lo or b0 >= self.y_hi:
                continue
            out.append(
                (
                    layer,
                    round(max(a0, x_lo), 6),
                    round(max(b0, self.y_lo), 6),
                    round(min(a1, x_hi), 6),
                    round(min(b1, self.y_hi), 6),
                )
            )
        return out

    def test_up_and_dn_branch_windows_hold_the_same_geometry(self):
        up = self._clip(self.x_lo, self.x_hi)
        dn = [
            (layer, round(-x1, 6), y0, round(-x0, 6), y1)
            for layer, x0, y0, x1, y1 in self._clip(-self.x_hi, -self.x_lo)
        ]
        self.assertGreater(len(up), 400, "sanity: the window should hold a whole branch")
        self.assertEqual(sorted(up), sorted(dn))

    def test_each_branch_net_has_a_same_length_counterpart(self):
        """Every UP-side net's routed metal is the mirror of its DN twin's.

        Tolerance is exact (to the 1 nm database grid): the DN branch is
        drawn through a mirroring proxy and its nets are packed onto the same
        Metal2 tracks, so equal *length* is a consequence of equal *shape*.
        """
        by_net: dict[str, list] = {}
        for net, layer, x0, y0, x1, y1 in self.layout.conductors:
            by_net.setdefault(net, []).append((layer, x0, y0, x1, y1))
        checked = 0
        for up_net, dn_net in pfd.MIRROR_NET_PAIRS.items():
            if up_net not in by_net:
                continue
            self.assertIn(dn_net, by_net, dn_net)
            up = sorted(by_net[up_net])
            dn = sorted(
                (layer, round(-x1, 6), y0, round(-x0, 6), y1)
                for layer, x0, y0, x1, y1 in by_net[dn_net]
            )
            self.assertEqual(up, dn, f"{up_net} vs {dn_net}")
            self.assertAlmostEqual(_wire_length(up), _wire_length(dn), places=9)
            checked += 1
        self.assertEqual(checked, len(pfd.MIRROR_NET_PAIRS))


class SharedResetFanoutTests(unittest.TestCase):
    """``RB`` reaches both latches over equal-length arms (issue #300's AC)."""

    @classmethod
    def setUpClass(cls):
        cls.layout = pfd.build()
        cls.place = cls.layout.placement

    def test_rb_drops_onto_the_axis(self):
        self.assertAlmostEqual(self.place.links[(0, "RB")], pfd.AXIS_X, places=9)
        self.assertAlmostEqual(self.place.links[(1, "RB")], pfd.AXIS_X, places=9)

    def test_rb_fanout_is_matched(self):
        lanes = sorted(lane for lane, _ in self.place.lanes[(0, "RB")])
        self.assertEqual(len(lanes), 2, "RB feeds exactly the two latches in row 0")
        left, right = lanes
        self.assertLess(left, pfd.AXIS_X)
        self.assertGreater(right, pfd.AXIS_X)
        # Equal arm lengths from the axis, where the Metal3 link injects.
        self.assertAlmostEqual(pfd.AXIS_X - left, right - pfd.AXIS_X, places=9)

    def test_rb_reaches_both_latch_reset_inputs(self):
        latch_cells = [c for c in self.place.cells if c.name.endswith(".xn2")]
        self.assertEqual(len(latch_cells), 2)
        for cell in latch_cells:
            self.assertEqual(cell.roles["A"], "RB")

    def test_up_and_dn_routes_into_the_reset_nand_are_reflections(self):
        up = pfd.net_interval(self.place, 0, "UP")
        dn = pfd.net_interval(self.place, 0, "DN")
        self.assertIsNotNone(up)
        self.assertEqual((round(-up[1], 6), round(-up[0], 6)), (round(dn[0], 6), round(dn[1], 6)))


def _wire_length(shapes) -> float:
    """Sum of the long dimension of every shape -- a routed-length proxy."""
    return round(sum(max(x1 - x0, y1 - y0) for _, x0, y0, x1, y1 in shapes), 9)


if __name__ == "__main__":
    unittest.main()
