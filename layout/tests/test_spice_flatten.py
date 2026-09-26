#!/usr/bin/env python3
"""Unit tests for ``layout/harness/spice_flatten.py`` (issue #440).

Pure-Python, no ``klayout.db``/PDK needed:

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import unittest

from _env import LAYOUT_DIR

REPO_ROOT = LAYOUT_DIR.parent

from harness import spice_flatten as sf  # noqa: E402

_SMALL_HIER = """\
* a tiny two-level hierarchy, deliberately shaped like this repo's real
* xschem exports: continuation lines, quoted multi-word parameters, and two
* separately-instantiated copies of the same leaf cell.
.subckt leaf A Y VDD VSS
XMP Y A VDD VDD pfet_03v3 L=0.3u W=1.5u nf=1 ad='int((nf+1)/2) * W/nf * 0.18u'
+ as='int((nf+2)/2) * W/nf * 0.18u' sa=0 sb=0
XMN Y A VSS VSS nfet_03v3 L=0.3u W=0.5u
.ends

.subckt top A B Y1 Y2 VDD VSS
xi1 A Y1 VDD VSS leaf
xi2 B Y2 VDD VSS leaf
.ends
"""


class ParseSubcktsTests(unittest.TestCase):
    def test_parses_names_and_ports(self):
        subckts = sf.parse_subckts(_SMALL_HIER)
        self.assertEqual(set(subckts), {"leaf", "top"})
        self.assertEqual(subckts["leaf"].ports, ("A", "Y", "VDD", "VSS"))
        self.assertEqual(subckts["top"].ports, ("A", "B", "Y1", "Y2", "VDD", "VSS"))

    def test_continuation_line_is_joined_onto_its_parent(self):
        subckts = sf.parse_subckts(_SMALL_HIER)
        # One instance line, not two -- the "+" line must not become its own
        # bogus zero-net instance.
        self.assertEqual(len(subckts["leaf"].lines), 2)
        self.assertIn("ad='int((nf+1)/2) * W/nf * 0.18u'", subckts["leaf"].lines[0])
        self.assertIn("as='int((nf+2)/2) * W/nf * 0.18u'", subckts["leaf"].lines[0])

    def test_comments_are_dropped(self):
        subckts = sf.parse_subckts(_SMALL_HIER)
        for line in subckts["leaf"].lines + subckts["top"].lines:
            self.assertFalse(line.lstrip().startswith("*"))

    def test_unclosed_subckt_raises(self):
        with self.assertRaises(ValueError):
            sf.parse_subckts(".subckt broken A B\nXMP Y A VDD VDD pfet_03v3\n")

    def test_ends_with_no_open_subckt_raises(self):
        with self.assertRaises(ValueError):
            sf.parse_subckts(".ends\n")

    def test_continuation_with_nothing_to_continue_raises(self):
        with self.assertRaises(ValueError):
            sf.parse_subckts("+ this continues nothing\n")


class FlattenTests(unittest.TestCase):
    def setUp(self):
        self.subckts = sf.parse_subckts(_SMALL_HIER)

    def test_top_level_ports_pass_through_unchanged(self):
        flat = sf.flatten(self.subckts, "top")
        self.assertEqual(
            flat.splitlines()[0], ".subckt top A B Y1 Y2 VDD VSS"
        )
        self.assertEqual(flat.splitlines()[-1], ".ends")

    def test_device_count_matches_two_leaf_instances(self):
        flat = sf.flatten(self.subckts, "top")
        device_lines = [l for l in flat.splitlines() if l.startswith("M_")]
        self.assertEqual(len(device_lines), 4)  # 2 devices x 2 leaf instances

    def test_two_leaf_instances_stay_electrically_distinct(self):
        # xi1 and xi2 are two separate instances of the SAME leaf cell --
        # every device name flattening produces must be unique, and each
        # instance's own boundary nets (A/Y mapped from the caller) must
        # differ between the two copies (that is the whole point of
        # per-instance qualification).
        flat = sf.flatten(self.subckts, "top")
        device_lines = [l for l in flat.splitlines() if l.startswith("M_")]
        names = [l.split()[0] for l in device_lines]
        self.assertEqual(len(names), len(set(names)), "duplicate device name after flattening")
        self.assertTrue(any("xi1" in n for n in names))
        self.assertTrue(any("xi2" in n for n in names))

    def test_caller_side_nets_are_correctly_substituted(self):
        # xi1's Y (leaf-local) must resolve to Y1 (top-level, caller-side);
        # xi2's Y must resolve to Y2 -- not to each other, and not left
        # unresolved as a bare "Y".
        flat = sf.flatten(self.subckts, "top")
        xi1_line = next(l for l in flat.splitlines() if "xi1_MP" in l)
        xi2_line = next(l for l in flat.splitlines() if "xi2_MP" in l)
        self.assertIn(" Y1 ", xi1_line)
        self.assertIn(" A ", xi1_line)  # top's own A, passed straight through
        self.assertIn(" Y2 ", xi2_line)
        self.assertIn(" B ", xi2_line)

    def test_quoted_multiword_parameter_survives_flattening_unmangled(self):
        flat = sf.flatten(self.subckts, "top")
        xi1_line = next(l for l in flat.splitlines() if "xi1_MP" in l)
        self.assertIn("ad='int((nf+1)/2) * W/nf * 0.18u'", xi1_line)
        self.assertIn("as='int((nf+2)/2) * W/nf * 0.18u'", xi1_line)

    def test_unknown_top_raises_keyerror(self):
        with self.assertRaises(KeyError):
            sf.flatten(self.subckts, "does_not_exist")

    def test_mismatched_arg_count_raises(self):
        bad = _SMALL_HIER + "\n.subckt bad A VDD VSS\nxi1 A VDD VSS leaf\n.ends\n"
        subckts = sf.parse_subckts(bad)
        with self.assertRaises(ValueError):
            sf.flatten(subckts, "bad")

    def test_flatten_text_matches_parse_then_flatten(self):
        self.assertEqual(sf.flatten_text(_SMALL_HIER, "top"), sf.flatten(self.subckts, "top"))


class RealExportsTests(unittest.TestCase):
    """Sanity-check the flattener against this repo's own real exports."""

    def test_lock_detector_committed_netlist_flattens_to_expected_device_count(self):
        path = REPO_ROOT / "design" / "netlist" / "lock_detector.spice"
        if not path.exists():
            self.skipTest("design/netlist/lock_detector.spice not generated")
        subckts = sf.parse_subckts(path.read_text())
        flat = sf.flatten(subckts, "lock_detector")
        device_lines = [l for l in flat.splitlines() if l.startswith("M_")]
        # xor2 (4x nand2 = 16) + delaywin (84) + nand2 (4) + inv (2) + MDNW/
        # MUPW/MCW (3, standalone) + schmitt (6) + inv (2) = 117 -- see
        # design/netlist/lock_detector.spice's own subckt bodies.
        self.assertEqual(len(device_lines), 117)
        self.assertEqual(
            flat.splitlines()[0],
            ".subckt lock_detector UP DN LOCK VWIN LDT0 LDT1 LDT2 LDT3 VDD VSS",
        )


if __name__ == "__main__":
    unittest.main()
