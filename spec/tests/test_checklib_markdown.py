#!/usr/bin/env python3
"""Tests for the helpers ``lib/checklib`` shares between the check scripts.

The claim checkers are graded end to end by the ``test_<check>.py`` files
beside this one, which run a real ``check-*.sh`` inside a throwaway tree.
That is the right level for a rule, and the wrong level for the two readings
of "what is a table" the five checks now share: a reading only one check uses
would be exercised by exactly one of those suites, by accident, through
whatever document that suite happens to write. So the splitter's own contract
is pinned here, on the shapes that made it a parameter (issue #918).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from checklib.files import read_text  # noqa: E402
from checklib.markdown import normalize, plain, tables  # noqa: E402


class TablesReadsEscapedPipesAsCellText(unittest.TestCase):
    """`\\|` is a literal pipe, never a column boundary."""

    BLOCK = (
        "| Step | Value |\n"
        "|---|---|\n"
        "| Systematic \\|q_up + q_dn\\|, worst corner | 3.68 fC |\n"
    )

    def test_the_escaped_pipes_stay_inside_one_cell(self) -> None:
        for strict in (False, True):
            with self.subTest(require_separator=strict):
                row = tables(self.BLOCK, require_separator=strict)[0][1]
                self.assertEqual(
                    row, ["Systematic \\|q_up + q_dn\\|, worst corner", "3.68 fC"]
                )

    def test_the_value_column_does_not_shift(self) -> None:
        # The defect this guards: a naive split puts "3.68 fC" in column 4,
        # so a check reading column 1 grades ", worst corner" instead.
        header, row = tables(self.BLOCK)[0]
        self.assertEqual(len(row), len(header))
        self.assertEqual(row[header.index("Value")], "3.68 fC")


class TablesSkipsSeparatorRowsWhereverTheyAppear(unittest.TestCase):
    """A row of dashes is a separator, not a row of data to grade."""

    def test_a_placeholder_dash_row_is_not_a_data_row(self) -> None:
        # sim/supply-sensitivity records write an all-`--` row to say "not
        # measured in this record". Reading it as data invents a measurement.
        block = (
            "| Temp | Domain | total (mW) |\n"
            "|---|---|---|\n"
            "| -- | -- | -- |\n"
        )
        for strict in (False, True):
            with self.subTest(require_separator=strict):
                self.assertEqual(
                    tables(block, require_separator=strict), [[
                        ["Temp", "Domain", "total (mW)"]
                    ]]
                )


class RequireSeparatorRejectsAPipeLineThatIsProse(unittest.TestCase):
    """The reading `sim/lib/check-quoted-value-provenance.sh` needs."""

    #: A wrapped paragraph in a sim record whose continuation line opens with
    #: a code span: `the total IS vdd x (|i_core| + |i_vco| + |i_div|) and ...`
    BLOCK = (
        "  the total IS vdd x (|i_core| + |i_vco| +\n"
        "  |i_div|) and there is no fourth domain.\n"
    )

    def test_the_permissive_reading_calls_it_a_one_row_table(self) -> None:
        self.assertEqual(
            tables(self.BLOCK),
            [[["i_div", ") and there is no fourth domain."]]],
        )

    def test_requiring_a_separator_reads_no_table_at_all(self) -> None:
        self.assertEqual(tables(self.BLOCK, require_separator=True), [])

    def test_a_real_table_later_in_the_same_text_is_still_found(self) -> None:
        # Rejecting the prose line must not cost the document its tables.
        block = self.BLOCK + "\n| Corner | f |\n|---|---|\n| typical | 200 |\n"
        self.assertEqual(
            tables(block, require_separator=True),
            [[["Corner", "f"], ["typical", "200"]]],
        )


class RequireSeparatorKeepsAHeaderOfEmptyCells(unittest.TestCase):
    """`| | |` is itself `[\\s:|-]+` between pipes -- and is still a header."""

    BLOCK = (
        "| | |\n"
        "|---|---|\n"
        "| Attempted | 2026-09-10 |\n"
        "| PDK | gf180mcuD |\n"
    )

    def test_the_table_is_not_dropped(self) -> None:
        # The line BELOW decides, so the run table several PROOF.md files open
        # this way keeps its rows instead of vanishing under the strict read.
        self.assertEqual(
            tables(self.BLOCK, require_separator=True),
            [[["", ""], ["Attempted", "2026-09-10"], ["PDK", "gf180mcuD"]]],
        )


class NormalizeIsTheLabelTolerance(unittest.TestCase):
    """What `normalize` folds away, and where it parts company with `plain`."""

    def test_it_folds_link_emphasis_backticks_dashes_and_case(self) -> None:
        self.assertEqual(
            normalize("[**Lock time**](spec/pll.md#lock)  — `small-signal`"),
            "lock time - small-signal",
        )

    def test_it_folds_every_dash_including_u2212(self) -> None:
        for dash in ("—", "–", "‒", "‑", "−"):
            with self.subTest(dash=dash):
                self.assertEqual(normalize("Supply %s AC" % dash), "supply - ac")

    def test_it_strips_a_single_asterisk_where_plain_keeps_it(self) -> None:
        self.assertEqual(normalize("*Power*"), "power")
        self.assertEqual(plain("*Power*"), "*Power*")

    def test_it_leaves_an_escaped_pipe_alone_where_plain_unescapes_it(self) -> None:
        self.assertEqual(normalize("\\|mean\\|"), "\\|mean\\|")
        self.assertEqual(plain("\\|mean\\|"), "|mean|")


class ReadTextReportsAMissingFileAsAFailure(unittest.TestCase):
    """A check that cannot read its document did not run, so it did not pass."""

    def test_an_existing_file_reads_back(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "spec").mkdir()
            (root / "spec" / "pll.md").write_text("# spec\n", encoding="utf-8")
            self.assertEqual(read_text(str(root), "spec/pll.md"), "# spec\n")

    def test_a_missing_file_returns_none_and_names_the_relative_path(self) -> None:
        import io
        import tempfile
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertIsNone(read_text(tmp, "spec/pll.md"))
            # The repo-relative path, not the absolute one: a CI log's reader
            # is looking for a path they can check out.
            self.assertEqual(err.getvalue(), "FAIL: spec/pll.md does not exist\n")


if __name__ == "__main__":
    unittest.main()
