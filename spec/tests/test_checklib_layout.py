#!/usr/bin/env python3
"""Tests for ``lib/checklib/layout.py``, the layout-evidence extractors.

A sibling of ``test_checklib_markdown.py`` and here for the same reason: the
``test_<check>.py`` suites grade a rule end to end by running a real
``check-*.sh`` in a throwaway tree, which is the right level for a rule and
the wrong level for a contract two callers share. ``audit_rows`` and
``klayout_pin`` are read by both ``layout/lib/gen_layout_status_table.py``
and ``layout/lib/check-layout-status-claims.sh``, and the shapes that made
them shared -- the later audit tables that must not be mistaken for the
geometry table, and an absent pin that the two callers answer differently --
would otherwise be exercised only incidentally, through whichever document
one of those suites happens to write (issue #924).

The module under test is ``lib/checklib/layout.py``, not anything under
``layout/``, which is why these tests sit beside the package's other unit
tests rather than in ``layout/tests/``.

    python3 -m unittest discover -s spec/tests -t spec/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from checklib.layout import audit_rows, klayout_pin  # noqa: E402

# The shape of layout/evidence/area-audit/area-audit.md: a geometry table,
# then further tables that open with the same `| `block` |` cell but carry a
# plain figure where the geometry table carries "W x H".
AUDIT = (
    "| Block | Footprint (um) | bbox (um2) | Drawn (um2) | Fill | Whitespace |\n"
    "|---|---|---|---|---|---|\n"
    "| `vco_block` | 226.69 x 184.48 | 41,820 | 18,233 | 43.6 % | 23,587 (56.4 %) |\n"
    "| `pfd_cp` | 344.98 x 74.30 | 25,630 | 6,016 | 23.5 % | 19,614 (76.5 %) |\n"
    "\n"
    "| Block | comp (um2) | comp share | Device band (um) |\n"
    "|---|---|---|---|\n"
    "| `vco_block` | 9,702.1 | 23.20 % | 183.48 |\n"
    "| `pfd_cp` | 1,562.1 | 6.09 % | 49.05 |\n"
)


class AuditRowsSelectsTheGeometryTable(unittest.TestCase):
    """Only the table that states a ``W x H`` pair is block geometry."""

    def test_the_later_tables_are_not_read_as_geometry(self) -> None:
        # The defect this guards: `| `vco_block` | 9,702.1 | 23.20 % | ...`
        # opens identically to a geometry row. Read as one, the block's
        # footprint silently becomes its comp area.
        self.assertEqual(set(audit_rows(AUDIT)), {"vco_block", "pfd_cp"})
        self.assertEqual(audit_rows(AUDIT)["vco_block"], ("226.69", "184.48", 41820))

    def test_a_document_with_no_geometry_table_yields_no_rows(self) -> None:
        self.assertEqual(audit_rows(AUDIT.split("\n\n")[1]), {})

    def test_the_first_row_wins_for_a_repeated_block(self) -> None:
        # A second geometry-shaped row for a name already seen belongs to a
        # later table, so it must not overwrite the audit's own measurement.
        extra = AUDIT + "| `vco_block` | 1.00 x 2.00 | 2 |\n"
        self.assertEqual(audit_rows(extra)["vco_block"], ("226.69", "184.48", 41820))


class AuditRowsReturnsTheDimensionsAsWritten(unittest.TestCase):
    """The strings, not floats -- the generator prints them verbatim."""

    def test_trailing_zeros_survive(self) -> None:
        # The reason this is not parsed to float here: the generator renders
        # the pair straight into layout/STATUS.md, where float("20.00") would
        # print "20.0" and rewrite the committed table.
        rows = audit_rows("| `blk` | 10.00 x 20.00 | 200 |\n")
        self.assertEqual(rows["blk"], ("10.00", "20.00", 200))

    def test_an_integer_dimension_needs_no_decimal_point(self) -> None:
        rows = audit_rows("| `blk` | 10 x 20.5 | 205 |\n")
        self.assertEqual(rows["blk"], ("10", "20.5", 205))

    def test_the_bbox_is_an_int_with_its_separators_stripped(self) -> None:
        rows = audit_rows("| `blk` | 1.0 x 2.0 | 1,234,567 |\n")
        self.assertEqual(rows["blk"][2], 1234567)
        self.assertIsInstance(rows["blk"][2], int)


class AuditRowsAcceptsBothMultiplicationSigns(unittest.TestCase):
    """``x`` and ``×`` both appear in the rendered audit."""

    def test_ascii_x_upper_x_and_u00d7_all_parse(self) -> None:
        for sign in ("x", "X", "×"):
            with self.subTest(sign=sign):
                rows = audit_rows("| `blk` | 1.50 %s 2.50 | 4 |\n" % sign)
                self.assertEqual(rows["blk"], ("1.50", "2.50", 4))


class KlayoutPinReadsTheModuleDeclaration(unittest.TestCase):
    """The pin every committed deck log's engine claim is graded against."""

    ENV = (
        '"""The layout harness environment."""\n'
        "\n"
        'KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.28.16"\n'
        "KLAYOUT_BIN = None\n"
    )

    def test_the_declared_pin_reads_back(self) -> None:
        self.assertEqual(klayout_pin(self.ENV), "KLayout 0.28.16")

    def test_an_undeclared_pin_is_none_rather_than_a_stand_in(self) -> None:
        # None, not "unknown": the checker fails the run on absence and the
        # generator renders "unknown", so the helper must not decide for
        # either of them.
        self.assertIsNone(klayout_pin("KLAYOUT_BIN = None\n"))

    def test_a_commented_out_pin_is_not_the_module_pin(self) -> None:
        # Line-anchored on purpose: a pin mentioned in a comment or a
        # docstring is prose about the pin, not the declaration.
        self.assertIsNone(
            klayout_pin('# KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.29.0"\n')
        )

    def test_the_real_declaration_still_wins_past_a_commented_one(self) -> None:
        text = (
            '# was KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.30.10"\n'
            'KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.28.16"\n'
        )
        self.assertEqual(klayout_pin(text), "KLayout 0.28.16")


if __name__ == "__main__":
    unittest.main()
