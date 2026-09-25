#!/usr/bin/env python3
"""Unit tests for ``spec/lib/check-spec-row-coverage.sh`` (issue #237).

    python3 -m unittest discover -s spec/tests -v

The check grades *presence*: every row of ``spec/pll.md``'s summary table must
be reported, with an explicit verdict, in the Chipalooza proposal's section-5
target-specification table.  It exists because #237's acceptance criteria
demand that a spec row be "either closed or explicitly marked unmet -- not
silently omitted from the table", and one row was omitted for the document's
whole life: ``Reference input`` (spec row 2), whose input levels and edge rate
are unmeasured ``budget`` items with a "Verification owed" line of their own,
and which carries the ideal-reference exclusion every jitter and spur number
in section 5 rests on.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  No PDK, no ngspice, no simulation
input -- the script reads committed Markdown.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SPEC_DIR.parent
CHECK = SPEC_DIR / "lib" / "check-spec-row-coverage.sh"

SPEC_DOC = "spec/pll.md"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"

#: A miniature of the real pair of tables: three spec rows, one of which the
#: proposal splits into two reported rows the way section 5 really does.
SPEC_ROWS = (
    ("1", "[Output band](#output-band)"),
    ("2", "[Reference input](#reference-input)"),
    ("3", "[Supply sensitivity](#supply-sensitivity)"),
)

PROPOSAL_ROWS = (
    ("Output band", "**MET** (open-loop characterization)"),
    ("Reference input", "**Range MET; levels/edge rate UNMET -- budget**"),
    ("Supply sensitivity — AC (ripple) budget", "**derived, conditional**"),
    (
        "Supply sensitivity — DC / closed-loop, full grid",
        "**UNMET on 3 of 4 measured criteria**",
    ),
)


def _spec(rows=SPEC_ROWS, heading="## Summary table") -> str:
    lines = [
        "# PLL target specification — v1",
        "",
        "## How to read this file",
        "",
        "Prose the check must not mistake for a table.",
        "",
        heading,
        "",
        "| # | Parameter | v1 target | Corner binding | Status |",
        "|---|---|---|---|---|",
    ]
    for num, param in rows:
        lines.append(f"| {num} | {param} | a target | a corner | **measured** |")
    lines += ["", "# Normative conditions", "", "Text after the table."]
    return "\n".join(lines) + "\n"


def _proposal(
    rows=PROPOSAL_ROWS,
    heading="## 5. Target specification at the Challenge #5 rails",
    header="| Parameter | v1 draft target | Measured / derived (3.3 V) | Verdict | Source (dated) |",
) -> str:
    lines = [
        "# Chipalooza Challenge #5 — integer-N PLL proposal",
        "",
        "## 2. I/O list, including test ports",
        "",
        "| `REF` | in | digital control input | 1 of 24 | Reference clock |",
        "",
        heading,
        "",
        header,
        "|---|---|---|---|---|",
    ]
    for param, verdict in rows:
        lines.append(f"| {param} | a target | a measurement | {verdict} | a record |")
    lines += ["", "## 6. Layout, DRC/LVS, and post-layout status", "", "Text after."]
    return "\n".join(lines) + "\n"


class _Tree:
    """A throwaway repo tree with the real check installed at spec/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "spec" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "spec" / "lib" / CHECK.name)
        self.write(SPEC_DOC, _spec())
        self.write(PROPOSAL, _proposal())

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "spec" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def assertPasses(self) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        return result

    def assertFails(self, *needles: str) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        return result


class TestCoverageRule(_TreeTest):
    def test_a_fully_reported_table_passes(self):
        self.assertPasses()

    def test_the_real_drift_shape_is_caught(self):
        """The exact regression: a spec row with no section-5 row at all.

        This is the proposal as it stood at `3f39aa11` -- `Reference input`
        appeared only as a pad-table line in section 2.2 describing what `REF`
        is, which the fixture reproduces, and nowhere in section 5.
        """
        self.tree.write(
            PROPOSAL,
            _proposal(tuple(r for r in PROPOSAL_ROWS if r[0] != "Reference input")),
        )
        self.assertFails(
            "[Reference input](#reference-input)",
            "has no row in docs/chipalooza/challenge-5-proposal.md section 5",
        )

    def test_a_qualified_row_covers_its_spec_row(self):
        """Section 5 has always split a spec row into several reported rows."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                (
                    ("Output band", "**MET**"),
                    ("Output band, **closed-loop**", "**UNMET / open finding**"),
                    ("Reference input (interface condition)", "**UNMET** — budget"),
                    ("Supply sensitivity: AC ripple", "**derived, conditional**"),
                    ("Supply sensitivity — DC", "**UNMET on 3 of 4**"),
                )
            ),
        )
        self.assertPasses()

    def test_a_qualifier_without_a_separator_does_not_cover(self):
        """`Reference inputs of other blocks` is not a report of row 2."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                tuple(
                    ("Reference inputs elsewhere", v) if p == "Reference input" else (p, v)
                    for p, v in PROPOSAL_ROWS
                )
            ),
        )
        self.assertFails("[Reference input](#reference-input)")

    def test_every_spec_row_is_graded_not_just_the_first(self):
        for num, param in SPEC_ROWS:
            with self.subTest(row=param):
                self.setUp()
                name = param.split("]")[0].lstrip("[")
                self.tree.write(
                    PROPOSAL,
                    _proposal(
                        tuple(r for r in PROPOSAL_ROWS if not r[0].startswith(name))
                    ),
                )
                self.assertFails(param)


class TestVerdictRule(_TreeTest):
    def test_a_reported_row_with_no_verdict_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                tuple(
                    (p, "still being characterized") if p == "Reference input" else (p, v)
                    for p, v in PROPOSAL_ROWS
                )
            ),
        )
        self.assertFails("states no verdict for it")

    def test_unmet_is_a_verdict(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                tuple(
                    (p, "**UNMET — explicitly, not omitted**")
                    if p == "Reference input"
                    else (p, v)
                    for p, v in PROPOSAL_ROWS
                )
            ),
        )
        self.assertPasses()

    def test_one_verdict_among_the_covering_rows_is_enough(self):
        """Deliberately per spec row, not per reported row.

        The real table states "Supply sensitivity -- AC (ripple) budget" as
        "derived, conditional" because the 20 mV pp ripple line is a condition
        on the driving system, not an outcome; its sibling DC row carries the
        verdict.  Forcing MET/UNMET onto the condition row would be false
        precision.  If that ever stops being the intent, this test is where it
        has to be argued.
        """
        self.assertPasses()

    def test_no_verdict_on_any_covering_row_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                tuple(
                    (p, "derived, conditional") if p.startswith("Supply sensitivity") else (p, v)
                    for p, v in PROPOSAL_ROWS
                )
            ),
        )
        self.assertFails(
            "[Supply sensitivity](#supply-sensitivity)", "states no verdict for it"
        )

    def test_an_english_word_ending_in_met_is_not_a_verdict(self):
        self.tree.write(
            PROPOSAL,
            _proposal(
                tuple(
                    (p, "the helmet analogy applies") if p == "Reference input" else (p, v)
                    for p, v in PROPOSAL_ROWS
                )
            ),
        )
        self.assertFails("states no verdict for it")


class TestOrphanRowRule(_TreeTest):
    def test_a_section_5_row_naming_no_spec_row_fails(self):
        """Catches a spec rename that leaves a stale reported row behind."""
        self.tree.write(
            PROPOSAL, _proposal(PROPOSAL_ROWS + (("Settling budget", "**MET**"),))
        )
        self.assertFails("naming no row of spec/pll.md's summary table")


class TestSelfDefence(_TreeTest):
    def test_a_missing_spec_fails(self):
        (self.tree.root / SPEC_DOC).unlink()
        self.assertFails("spec/pll.md does not exist")

    def test_a_missing_proposal_fails(self):
        (self.tree.root / PROPOSAL).unlink()
        self.assertFails(f"{PROPOSAL} does not exist")

    def test_a_renamed_summary_table_heading_fails(self):
        self.tree.write(SPEC_DOC, _spec(heading="## Target table"))
        self.assertFails("has no '## Summary table' section")

    def test_a_renumbered_proposal_section_fails(self):
        self.tree.write(PROPOSAL, _proposal(heading="## 5A. Target specification"))
        self.assertFails("has no '## 5.' section")

    def test_a_table_that_stops_parsing_fails(self):
        """A regex that silently matches nothing must not read as clean."""
        self.tree.write(SPEC_DOC, _spec(rows=SPEC_ROWS[:1]))
        self.assertFails("too few to be real")

    def test_a_missing_verdict_column_fails(self):
        self.tree.write(
            PROPOSAL,
            _proposal(header="| Parameter | Target | Measured | Status | Source |"),
        )
        self.assertFails("has no 'verdict' column")


class TestTheRealTree(unittest.TestCase):
    def test_the_committed_tree_passes(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("are reported with a verdict", result.stdout)


if __name__ == "__main__":
    unittest.main()
