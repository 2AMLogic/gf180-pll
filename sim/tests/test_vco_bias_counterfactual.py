"""`sim/vco-bias-current`'s counterfactual arm is derived, never hand-written.

That campaign (issue #381) measures the bias-current consequence of drawing
`design/netlist/vco.spice`'s `ppolyf_u_3k` bias resistors as the unmarked
350 ohm/sq `ppolyf_u` class, which is what `layout/pll_top/vco/primitives.
poly_resistor()` did until that issue. Its second arm therefore has to be the
committed bias generator with **only** the resistor device class changed --
if it drifts from the schematic in any other way, the measured ratio stops
being attributable to the resistor and the record silently becomes a
comparison of two different circuits.

`make_counterfactual.py` guarantees that by deriving the file mechanically.
These tests pin the derivation itself (exactly three model tokens rewritten,
one subckt renamed, nothing else) and that the committed artifact still
matches a fresh derivation from the current `design/netlist/vco.spice` -- so
a future re-export of the schematic that touched the bias generator fails
here rather than at the next reading of the record.

    python3 -m unittest discover -s sim/tests -t sim/tests
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTBENCH = REPO_ROOT / "sim" / "vco-bias-current" / "testbench"
GENERATOR = TESTBENCH / "make_counterfactual.py"
COMMITTED = TESTBENCH / "vco_bias_as_drawn_350.spice"
SOURCE = REPO_ROOT / "design" / "netlist" / "vco.spice"


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_counterfactual", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _devices(text: str) -> list[list[str]]:
    """Every instance line of a subckt body, as whitespace-split fields."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("*", ".", "+")):
            continue
        out.append(stripped.split())
    return out


class CounterfactualDerivationTests(unittest.TestCase):
    def setUp(self):
        self.generator = _load_generator()
        self.committed = COMMITTED.read_text()
        self.source_subckt = self.generator.extract_subckt(
            SOURCE.read_text(), self.generator.SOURCE_SUBCKT
        )

    def test_the_committed_file_matches_a_fresh_derivation(self):
        self.assertEqual(
            self.committed,
            self.generator.render(),
            "sim/vco-bias-current/testbench/vco_bias_as_drawn_350.spice is stale "
            "-- re-run make_counterfactual.py (design/netlist/vco.spice has "
            "changed since it was generated)",
        )

    def test_only_the_three_resistor_models_differ_from_the_schematic(self):
        src = _devices(self.source_subckt)
        cf = _devices(self.committed)
        self.assertEqual(len(src), len(cf), "device count changed")
        differences = []
        for a, b in zip(src, cf):
            self.assertEqual(a[0], b[0], "instance name or order changed")
            if a != b:
                differences.append((a, b))
        self.assertEqual(
            len(differences), 3, f"expected exactly 3 changed lines, got {differences}"
        )
        for a, b in differences:
            self.assertIn(a[0].upper(), ("XRCG", "XROFF", "XRDEG"))
            self.assertEqual(
                [f for f in a if f != self.generator.AS_SPECIFIED_MODEL],
                [f for f in b if f != self.generator.AS_DRAWN_MODEL],
                "a changed line differs by more than its model token",
            )

    def test_the_schematic_still_declares_the_high_sheet_class(self):
        models = {
            fields[4]
            for fields in _devices(self.source_subckt)
            if fields[0].upper() in ("XRCG", "XROFF", "XRDEG")
        }
        self.assertEqual(models, {self.generator.AS_SPECIFIED_MODEL})

    def test_the_counterfactual_subckt_is_renamed_so_both_arms_coexist(self):
        headers = re.findall(r"^\.subckt\s+(\S+)", self.committed, re.MULTILINE)
        self.assertEqual(headers, [self.generator.TARGET_SUBCKT])

    def test_the_generators_check_mode_agrees(self):
        self.assertEqual(self.generator.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
