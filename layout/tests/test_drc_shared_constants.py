#!/usr/bin/env python3
"""Guard: the CO.1 contact size has exactly one literal definition (issue #1001).

``layout/pll_top/_drc.py`` owns ``CONTACT_SIZE_UM``. Every block-level
contact-size constant must alias it, so a rule revision lands once rather than
in six hand-copied places. These tests fail if a block re-types the number.

The scan keys on contact-*size* constant names, never on the value 0.22:
other 0.22 literals (``TRIM_W_UNIT_SW_UM``, the ``MUPW`` width,
``POLY_RES_CONTACT_TO_SAB_UM`` for HRES.8) are different rules and must stay
untouched, as must the per-block margins (``VIA_ENCLOSURE_UM`` etc.).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import ast
import importlib
import unittest

from _env import LAYOUT_DIR

CO1_NAMES = frozenset({"CONTACT_SIZE_UM", "DRC_CONTACT_SIZE_UM", "CONTACT_UM"})
DRC_PATH = LAYOUT_DIR / "pll_top" / "_drc.py"

# (module path relative to layout/pll_top, constant, dotted source of its RHS)
ALIASES = [
    ("divider_chain/devgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM"),
    ("pfd_cp/devgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM"),
    ("pfd_cp/rowgen.py", "CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM"),
    ("vco/devices.py", "DRC_CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM"),
    ("lock_detector/devices.py", "DRC_CONTACT_SIZE_UM", "_drc.CONTACT_SIZE_UM"),
    ("loop_filter/primitives.py", "CONTACT_UM", "_drc.CONTACT_SIZE_UM"),
    ("vco/primitives.py", "CONTACT_SIZE_UM", "dev.DRC_CONTACT_SIZE_UM"),
    ("lock_detector/primitives.py", "CONTACT_SIZE_UM", "dev.DRC_CONTACT_SIZE_UM"),
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


def co1_literal_names(source: str) -> list[str]:
    """CO.1 contact-size names bound to a numeric literal in ``source``."""
    found = []
    for name, value in _module_assignments(source).items():
        if name not in CO1_NAMES:
            continue
        if any(
            isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            for n in ast.walk(value)
        ):
            found.append(name)
    return found


class SharedContactSizeTest(unittest.TestCase):
    def test_drc_is_the_only_literal_definition(self) -> None:
        self.assertEqual(co1_literal_names(DRC_PATH.read_text()), ["CONTACT_SIZE_UM"])
        offenders = {}
        for path in sorted(LAYOUT_DIR.rglob("*.py")):
            if path == DRC_PATH:
                continue
            names = co1_literal_names(path.read_text())
            if names:
                offenders[str(path.relative_to(LAYOUT_DIR))] = names
        self.assertEqual(offenders, {}, "CO.1 literal re-typed outside _drc.py")

    def test_block_constants_alias_drc(self) -> None:
        for rel, name, expected in ALIASES:
            with self.subTest(module=rel, constant=name):
                path = LAYOUT_DIR / "pll_top" / rel
                value = _module_assignments(path.read_text()).get(name)
                self.assertIsNotNone(value, f"{rel} no longer defines {name}")
                self.assertEqual(ast.unparse(value), expected)

    def test_alias_values_resolve_to_drc(self) -> None:
        drc = importlib.import_module("_drc")
        for rel, name, _ in ALIASES:
            modname = rel[: -len(".py")].replace("/", ".")
            try:
                mod = importlib.import_module(modname)
            except ImportError as exc:  # optional deps (e.g. klayout) absent
                self.skipTest(f"cannot import {modname}: {exc}")
            with self.subTest(module=modname, constant=name):
                self.assertEqual(getattr(mod, name), drc.CONTACT_SIZE_UM)

    def test_scanner_bites_on_synthetic_literal(self) -> None:
        self.assertEqual(co1_literal_names("CONTACT_SIZE_UM = 0.22\n"), ["CONTACT_SIZE_UM"])
        self.assertEqual(co1_literal_names("CONTACT_UM: float = 0.22\n"), ["CONTACT_UM"])
        self.assertEqual(co1_literal_names("CONTACT_SIZE_UM = _drc.CONTACT_SIZE_UM\n"), [])

    def test_scanner_ignores_non_co1_literals(self) -> None:
        src = (
            "TRIM_W_UNIT_SW_UM = 0.22\n"
            "POLY_RES_CONTACT_TO_SAB_UM = 0.22\n"
            "VIA_ENCLOSURE_UM = 0.09\n"
            "CONTACT_PITCH_UM = 0.5\n"
        )
        self.assertEqual(co1_literal_names(src), [])


if __name__ == "__main__":
    unittest.main()
