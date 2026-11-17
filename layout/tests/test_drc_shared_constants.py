#!/usr/bin/env python3
"""Guard: shared DRC rule values have exactly one literal definition.

``layout/pll_top/_drc.py`` owns the numeric value of each DRC rule the
``layout/pll_top/*`` blocks may not disagree about -- currently CO.1
(contact size, issue #1001), CO.7 (contact-to-gate-poly space), CO.8
(poly-contact-to-comp space) and NP.5a/PP.5a (implant overlap of the gate)
(issue #1013). Every block-level constant for a watched rule must alias
``_drc``, so a rule revision lands once rather than in several hand-copied
places. These tests fail if a block re-types the number.

The scan keys on rule *names*, never on the values: 0.22, 0.15, 0.17 and
0.23 all collide with unrelated literals (``TRIM_W_UNIT_SW_UM``, the
``MUPW`` width, ``POLY_RES_CONTACT_TO_SAB_UM`` for HRES.8,
``DRC_METAL1_MIN_WIDTH_UM`` for M1.1) that are different rules and must
stay untouched, as must the per-block margins (``VIA_ENCLOSURE_UM`` etc.).

``RULE_NAMES`` is also kept complete: every module-level numeric literal
in ``_drc.py`` must be covered by some ``RULE_NAMES`` entry, so the next
rule added there fails a test naming it until its entry lands -- the
watch list cannot silently lag the file it watches (issue #1024).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import ast
import importlib
import unittest

from _env import LAYOUT_DIR

# Rule -> every name a block binds that rule's value under.
RULE_NAMES: dict[str, frozenset[str]] = {
    "CO.1": frozenset({"CONTACT_SIZE_UM", "DRC_CONTACT_SIZE_UM", "CONTACT_UM"}),
    "CO.7": frozenset({"CONTACT_TO_GATE_POLY_UM", "DRC_CONTACT_TO_GATE_POLY_UM"}),
    "CO.8": frozenset({"POLY_CONTACT_TO_COMP_UM", "DRC_POLY_CONTACT_TO_COMP_UM"}),
    "NP.5a": frozenset({"IMPLANT_GATE_ENCLOSE_UM", "DRC_IMPLANT_GATE_ENCLOSE_UM"}),
}
DRC_PATH = LAYOUT_DIR / "pll_top" / "_drc.py"

# (module path relative to layout/pll_top, constant, dotted source of its RHS,
#  the ``_drc`` attribute the constant's value must resolve to)
ALIASES = [
    ("divider_chain/devgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("pfd_cp/devgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("pfd_cp/rowgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("vco/devices.py", "DRC_CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("lock_detector/devices.py", "DRC_CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("loop_filter/primitives.py", "CONTACT_UM", "_drc.CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("vco/primitives.py", "CONTACT_SIZE_UM", "dev.DRC_CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("lock_detector/primitives.py", "CONTACT_SIZE_UM", "dev.DRC_CONTACT_SIZE_UM", "CONTACT_SIZE_UM"),
    ("vco/devices.py", "DRC_CONTACT_TO_GATE_POLY_UM", "_drc.CONTACT_TO_GATE_POLY_UM", "CONTACT_TO_GATE_POLY_UM"),
    ("vco/devices.py", "DRC_POLY_CONTACT_TO_COMP_UM", "_drc.POLY_CONTACT_TO_COMP_UM", "POLY_CONTACT_TO_COMP_UM"),
    ("vco/devices.py", "DRC_IMPLANT_GATE_ENCLOSE_UM", "_drc.IMPLANT_GATE_ENCLOSE_UM", "IMPLANT_GATE_ENCLOSE_UM"),
]


def _module_assignments(source: str) -> dict[str, ast.expr]:
    """Module-level ``NAME = value`` / ``NAME: T = value`` bindings."""
    out: dict[str, ast.expr] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out[tgt.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                out[node.target.id] = node.value
    return out


def literal_definitions(source: str) -> list[tuple[str, str]]:
    """``(rule, name)`` pairs from ``RULE_NAMES`` bound to a numeric literal."""
    assignments = _module_assignments(source)
    found: list[tuple[str, str]] = []
    for rule, names in RULE_NAMES.items():
        for name in names:
            value = assignments.get(name)
            if value is None:
                continue
            if any(
                isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                for n in ast.walk(value)
            ):
                found.append((rule, name))
    return sorted(found)


def uncovered_literal_names(source: str) -> set[str]:
    """Module-level names bound to a numeric literal that no ``RULE_NAMES``
    entry watches.

    ``literal_definitions`` only sees the names ``RULE_NAMES`` already
    lists, so a rule literal added to ``_drc.py`` without a matching entry
    there is invisible to it (issue #1024). This helper walks every
    module-level binding instead and reports the ones whose name is outside
    the watch list; the guard test asserts the set is empty.
    """
    covered = frozenset().union(*RULE_NAMES.values())
    return {
        name
        for name, value in _module_assignments(source).items()
        if name not in covered
        and any(
            isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            for node in ast.walk(value)
        )
    }


class SharedRuleValueTest(unittest.TestCase):
    def test_drc_holds_the_only_literal_definitions(self) -> None:
        self.assertEqual(
            literal_definitions(DRC_PATH.read_text()),
            [
                ("CO.1", "CONTACT_SIZE_UM"),
                ("CO.7", "CONTACT_TO_GATE_POLY_UM"),
                ("CO.8", "POLY_CONTACT_TO_COMP_UM"),
                ("NP.5a", "IMPLANT_GATE_ENCLOSE_UM"),
            ],
        )
        offenders = {}
        for path in sorted(LAYOUT_DIR.rglob("*.py")):
            if path == DRC_PATH:
                continue
            found = literal_definitions(path.read_text())
            if found:
                offenders[str(path.relative_to(LAYOUT_DIR))] = found
        self.assertEqual(offenders, {}, "shared DRC rule literal re-typed outside _drc.py")

    def test_drc_binds_no_unwatched_literals(self) -> None:
        uncovered = uncovered_literal_names(DRC_PATH.read_text())
        self.assertEqual(
            uncovered,
            set(),
            "module-level numeric literal(s) in _drc.py that no RULE_NAMES "
            f"entry watches: {sorted(uncovered)} -- add each one's rule to "
            "RULE_NAMES in the same change",
        )

    def test_block_constants_alias_drc(self) -> None:
        for rel, name, expected, _ in ALIASES:
            with self.subTest(module=rel, constant=name):
                path = LAYOUT_DIR / "pll_top" / rel
                value = _module_assignments(path.read_text()).get(name)
                self.assertIsNotNone(value, f"{rel} no longer defines {name}")
                self.assertEqual(ast.unparse(value), expected)

    def test_alias_values_resolve_to_drc(self) -> None:
        drc = importlib.import_module("_drc")
        for rel, name, _, drc_attr in ALIASES:
            modname = rel[: -len(".py")].replace("/", ".")
            try:
                mod = importlib.import_module(modname)
            except ImportError as exc:  # optional deps (e.g. klayout) absent
                self.skipTest(f"cannot import {modname}: {exc}")
            with self.subTest(module=modname, constant=name):
                self.assertEqual(getattr(mod, name), getattr(drc, drc_attr))

    def test_scanner_bites_on_synthetic_literals(self) -> None:
        self.assertEqual(
            literal_definitions("CONTACT_SIZE_UM = 0.22\n"), [("CO.1", "CONTACT_SIZE_UM")]
        )
        self.assertEqual(
            literal_definitions("CONTACT_UM: float = 0.22\n"), [("CO.1", "CONTACT_UM")]
        )
        self.assertEqual(literal_definitions("CONTACT_SIZE_UM = _drc.CONTACT_SIZE_UM\n"), [])
        self.assertEqual(
            literal_definitions("CONTACT_TO_GATE_POLY_UM = 0.15\n"),
            [("CO.7", "CONTACT_TO_GATE_POLY_UM")],
        )
        self.assertEqual(
            literal_definitions("DRC_CONTACT_TO_GATE_POLY_UM = 0.15\n"),
            [("CO.7", "DRC_CONTACT_TO_GATE_POLY_UM")],
        )
        self.assertEqual(
            literal_definitions("POLY_CONTACT_TO_COMP_UM = 0.17\n"),
            [("CO.8", "POLY_CONTACT_TO_COMP_UM")],
        )
        self.assertEqual(
            literal_definitions("DRC_POLY_CONTACT_TO_COMP_UM = 0.17\n"),
            [("CO.8", "DRC_POLY_CONTACT_TO_COMP_UM")],
        )
        self.assertEqual(
            literal_definitions("IMPLANT_GATE_ENCLOSE_UM = 0.23\n"),
            [("NP.5a", "IMPLANT_GATE_ENCLOSE_UM")],
        )
        self.assertEqual(
            literal_definitions("DRC_IMPLANT_GATE_ENCLOSE_UM = 0.23\n"),
            [("NP.5a", "DRC_IMPLANT_GATE_ENCLOSE_UM")],
        )
        self.assertEqual(
            literal_definitions("DRC_IMPLANT_GATE_ENCLOSE_UM = _drc.IMPLANT_GATE_ENCLOSE_UM\n"),
            [],
        )

    def test_unwatched_scanner_bites_on_synthetic_literals(self) -> None:
        self.assertEqual(
            uncovered_literal_names("CONTACT_COMP_ENCLOSE_UM = 0.07\n"),
            {"CONTACT_COMP_ENCLOSE_UM"},
        )
        self.assertEqual(
            uncovered_literal_names(
                "CONTACT_SIZE_UM = 0.22\nCONTACT_COMP_ENCLOSE_UM = 0.07\n"
            ),
            {"CONTACT_COMP_ENCLOSE_UM"},
        )
        self.assertEqual(
            uncovered_literal_names("CONTACT_SIZE_UM: float = 0.22\n"), set()
        )
        self.assertEqual(
            uncovered_literal_names("CONTACT_COMP_ENCLOSE_UM: float = 0.07\n"),
            {"CONTACT_COMP_ENCLOSE_UM"},
        )
        self.assertEqual(
            uncovered_literal_names(
                "CONTACT_COMP_ENCLOSE_UM = _drc.CONTACT_SIZE_UM\n"
                "CONTACT_SIZE_UM = _drc.CONTACT_SIZE_UM\n"
            ),
            set(),
        )

    def test_scanner_ignores_non_rule_literals(self) -> None:
        src = (
            "TRIM_W_UNIT_SW_UM = 0.22\n"
            "POLY_RES_CONTACT_TO_SAB_UM = 0.22\n"
            "VIA_ENCLOSURE_UM = 0.09\n"
            "CONTACT_PITCH_UM = 0.5\n"
            "DRC_METAL1_MIN_WIDTH_UM = 0.23\n"
            "DRC_CONTACT_SPACE_UM = 0.15\n"
            "DRC_CONTACT_COMP_ENCLOSE_UM = 0.17\n"
        )
        self.assertEqual(literal_definitions(src), [])


if __name__ == "__main__":
    unittest.main()
