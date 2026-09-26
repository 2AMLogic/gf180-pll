#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-quoted-value-provenance.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades the *measured value itself*: a figure quoted in the Chipalooza
proposal's section 5 must be what the cited record's committed per-corner CSV
produces under the reduction section 5.1 names, rounded to the precision the
figure is written to.  It exists because eleven checks already grade that
table's counts, citations, grid, verdicts and references, and none of them
would have noticed a number that simply is not in the record.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  No PDK, no ngspice, no simulation
input -- the script reduces committed CSVs and reads committed Markdown.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-quoted-value-provenance.sh"

PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
SPEC = "spec/pll.md"

CAMPAIGN = "vco-tuning-range"
RECORD = "20260731-175947-0a12e6c"
OTHER = "20260804-211600-f599a65"

#: Two corners, three samples each: min over all rows is 5.0, max is 40.0, and
#: the guaranteed floor (highest per-corner minimum) is 12.0 -- a figure no
#: single-stage reduction produces, which is what makes it worth grading.
TUNING_CSV = """\
# a committed per-corner reduction
bundle,temp_c,vdd_v,band,fosc_hz,isupply_a
all-fast,125,2.97,0,5000000,1.0e-4
all-fast,125,2.97,7,20000000,2.0e-4
all-fast,125,2.97,6,17500000,1.5e-4
all-slow,-40,3.63,0,12000000,3.0e-4
all-slow,-40,3.63,7,40000000,4.0e-4
all-slow,-40,3.63,6,33333333,3.5e-4
"""

#: The contracted-space fixture: `on-icp-trim-rule` must select only the rows
#: whose (f_ref, trim) pairing the spec table requires -- 47.4 and not 25.4.
MARGINS_CSV = """\
f_ref_hz,trim_units,fc_min_hz,pm_min_deg,pass_pm
1e6,4,25960,47.41,1
1e6,1,10700,25.46,0
2e6,4,45210,60.40,1
2e6,2,30000,55.00,1
"""

SPEC_TEXT = """\
# spec

## Icp trim-code rule

| f_ref | Required Icp trim (unit legs) | Worst phase margin at that code |
|---|---|---|
| 1 MHz | **4** | 47.4 deg |
| 2 MHz | **4** | 60.4 deg |

## Something else
"""

SPEC_ROWS = (
    # (name, measured cell, verdict, source cell)
    ("Output band", "Floor 12 MHz; ceiling 20 MHz", "**MET**",
     f"`sim/{CAMPAIGN}/records/{RECORD}.md`"),
    ("Phase margin", "Worst 47.4 deg; 3/4 cells pass", "**MET**", "Same record"),
    ("Standby current", "n/a -- no standby state exists", "**N/A**",
     "`spec/pll.md#standby-current`"),
)

PROVENANCE_HEADER = (
    "| §5 row | Quoted value | Record(s) | Evidence file | Reduction | Scale |\n"
    "|---|---|---|---|---|---|\n"
)
EXCLUSION_HEADER = (
    "| §5 row | Why no value here is re-derived from a CSV |\n|---|---|\n"
)

DEFAULT_PROVENANCE = [
    ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
     "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6"),
    ("Output band", "`20 MHz`", RECORD, "vco_tuning.csv",
     "min(max(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6"),
    ("Phase margin", "`47.4`", RECORD, "loop_margins.csv",
     "min(pm_min_deg where on-icp-trim-rule)", "1"),
    ("Phase margin", "`3`", RECORD, "loop_margins.csv",
     "count(rows where pass_pm == 1)", "1"),
]

DEFAULT_EXCLUSIONS = [
    ("Standby current", "Waived -- no power-down mode exists in v1, so there "
                        "is no state to measure"),
]


def _spec_table(rows) -> str:
    out = ["| Parameter | v1 draft target | Measured / derived (3.3 V) | "
           "Verdict | Source (dated) |", "|---|---|---|---|---|"]
    for name, measured, verdict, source in rows:
        out.append(f"| {name} | a target | {measured} | {verdict} | {source} |")
    return "\n".join(out) + "\n"


def _provenance_table(entries) -> str:
    body = "".join(
        "| %s | %s | `%s` | `%s` | `%s` | `%s` |\n" % entry for entry in entries
    )
    return PROVENANCE_HEADER + body


def _exclusion_table(entries) -> str:
    body = "".join("| %s | %s |\n" % entry for entry in entries)
    return EXCLUSION_HEADER + body


def proposal(
    spec_rows=SPEC_ROWS, provenance=None, exclusions=None, include_5_1=True
) -> str:
    provenance = DEFAULT_PROVENANCE if provenance is None else provenance
    exclusions = DEFAULT_EXCLUSIONS if exclusions is None else exclusions
    text = "# proposal\n\n## 5. Target specification\n\n"
    text += _spec_table(spec_rows) + "\n"
    if include_5_1:
        text += "### 5.1 Value provenance\n\n"
        text += _provenance_table(provenance) + "\n"
        text += _exclusion_table(exclusions) + "\n"
    text += "## 6. Next section\n"
    return text


class _Tree:
    """A throwaway repo tree with the real check installed at sim/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)

        rec_dir = root / "sim" / CAMPAIGN / "records"
        rec_dir.mkdir(parents=True)
        for rid in (RECORD, OTHER):
            (rec_dir / f"{rid}.md").write_text("# record\n")

        corners = root / "sim" / CAMPAIGN / "corners" / RECORD
        corners.mkdir(parents=True)
        (corners / "vco_tuning.csv").write_text(TUNING_CSV)
        (corners / "loop_margins.csv").write_text(MARGINS_CSV)

        (root / "spec").mkdir()
        (root / SPEC).write_text(SPEC_TEXT)

        (root / "docs" / "chipalooza").mkdir(parents=True)
        self.write(proposal())

    def write(self, text: str) -> None:
        (self.root / PROPOSAL).write_text(text)

    def write_spec(self, text: str) -> None:
        (self.root / SPEC).write_text(text)

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / CHECK.name)],
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


class TestCleanTree(_TreeTest):
    def test_a_consistent_document_passes(self):
        result = self.assertPasses()
        self.assertIn("4 quoted values re-derived", result.stdout)
        self.assertIn("all 3 section 5 rows accounted for", result.stdout)

    def test_the_grouped_reduction_is_not_a_flat_one(self):
        """`max(min(x) by corner)` must be the guaranteed floor, not min(x).

        The fixture's flat minimum is 5.0 MHz and its guaranteed floor is
        12.0 MHz. A check that silently dropped the grouping would accept
        5.000 here; this asserts it does not.
        """
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 5.000 MHz; ceiling 20 MHz", "**MET**",
                   f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`5.000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("gives 12", "does not round to it")


class TestValueRule(_TreeTest):
    def test_a_drifted_value_fails(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12.999 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.999 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("does not round to it at the 3 decimal place(s)")

    def test_a_value_correct_to_the_precision_written_passes(self):
        """12.0 MHz written to no decimals is 12; to four it is 12.0000.

        Both spellings must pass, and a figure the derived value does NOT
        round to at the precision written must not -- the neighbouring
        drift test covers that direction.
        """
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12.0000 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.0000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertPasses()

    def test_a_wrong_count_fails_exactly(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[3] = ("Phase margin", "`4`", RECORD, "loop_margins.csv",
                      "count(rows where pass_pm == 1)", "1")
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin", "Worst 47.4 deg; 4/4 cells pass", "**MET**",
                   "Same record")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("counts 3")

    def test_the_scale_is_applied(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12000000 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12000000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("does not round to it")


class TestDriftBetweenTheTwoTables(_TreeTest):
    def test_a_figure_not_present_in_the_section_5_row_fails(self):
        """The rule that makes the two tables one artefact rather than two.

        `12.0000 MHz` is the correct value at a precision section 5 does not
        write it to, so rule 4 is satisfied and only rule 3 fires: the failure
        really is "these two tables disagree", not a wrong number.
        """
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.0000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("does not appear in that section 5 row", "drifted")

    def test_an_entry_naming_no_section_5_row_fails(self):
        entries = DEFAULT_PROVENANCE + [
            ("Nonexistent row", "`12 MHz`", RECORD, "vco_tuning.csv",
             "min(fosc_hz)", "1e-6")
        ]
        self.tree.write(proposal(provenance=entries))
        self.assertFails("names a section 5 row that does not exist")


class TestCitationRule(_TreeTest):
    def test_reducing_a_record_the_row_does_not_cite_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", OTHER, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("which that section 5 row does not cite")

    def test_same_record_inherits_the_preceding_rows_citation(self):
        """The Phase margin row's Source cell says only "Same record"."""
        self.assertPasses()

    def test_a_record_not_on_the_tree_fails(self):
        missing = "20990101-000000-fffffff"
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{missing}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", missing, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        entries[1] = ("Output band", "`20 MHz`", missing, "vco_tuning.csv",
                      "min(max(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("is not on the tree")

    def test_an_uncommitted_evidence_file_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "not_committed.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("no committed evidence file at")


class TestCoverageRule(_TreeTest):
    def test_a_row_in_neither_table_fails(self):
        self.tree.write(proposal(exclusions=[]))
        self.assertFails("appears in neither of section 5.1's tables")

    def test_a_row_in_both_tables_fails(self):
        self.tree.write(
            proposal(
                exclusions=DEFAULT_EXCLUSIONS
                + [("Output band", "a reason long enough to be a real one")]
            )
        )
        self.assertFails("is both graded and excluded")

    def test_an_exclusion_without_a_reason_fails(self):
        self.tree.write(proposal(exclusions=[("Standby current", "n/a")]))
        self.assertFails("gives no real reason")

    def test_an_exclusion_naming_no_section_5_row_fails(self):
        self.tree.write(
            proposal(
                exclusions=DEFAULT_EXCLUSIONS
                + [("Ghost row", "a reason long enough to be a real one")]
            )
        )
        self.assertFails("names a section 5 row that does not exist")


class TestIcpTrimRulePredicate(_TreeTest):
    def test_the_rule_is_read_from_the_spec_not_the_check(self):
        """Move the ratified pairing and the graded figure must move with it.

        The spec fixture requires trim 4 at 1 MHz, which selects pm 47.41.
        Requiring trim 1 instead selects 25.46 -- so the same document, the
        same CSV and the same reduction now fail. This is the property that
        makes the predicate a reading of spec/pll.md rather than a constant.
        """
        self.assertPasses()
        self.tree.write_spec(SPEC_TEXT.replace("| 1 MHz | **4** |",
                                               "| 1 MHz | **1** |"))
        self.assertFails("gives 25.46")

    def test_a_missing_rule_table_fails_rather_than_matching_everything(self):
        self.tree.write_spec("# spec\n\nNo rule table here.\n")
        self.assertFails("no Icp trim-code rule table could be read")


class TestSelfDefence(_TreeTest):
    """A parser that gave up must not be reported as a clean document."""

    def test_a_missing_proposal_fails(self):
        (Path(self.tree.root) / PROPOSAL).unlink()
        self.assertFails("does not exist")

    def test_a_missing_5_1_section_fails(self):
        self.tree.write(proposal(include_5_1=False))
        self.assertFails("no non-empty section 5.1 value-provenance table")

    def test_a_missing_exclusion_table_fails(self):
        text = proposal()
        text = text[: text.index(EXCLUSION_HEADER)] + "\n## 6. Next section\n"
        self.tree.write(text)
        self.assertFails("no section 5.1 exclusion table")

    def test_an_unparsable_reduction_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "median(fosc_hz)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("cannot parse reduction")

    def test_an_unknown_column_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "min(not_a_column)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("which the evidence file does not have")

    def test_a_where_clause_selecting_nothing_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "min(fosc_hz where bundle == nonesuch)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("selected no")

    def test_a_count_with_a_scale_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[3] = ("Phase margin", "`3`", RECORD, "loop_margins.csv",
                      "count(rows where pass_pm == 1)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("count reduction must carry scale 1")


class TestTheRealTree(unittest.TestCase):
    """The check must pass on this repository, and grade a real amount."""

    def test_the_committed_proposal_is_consistent(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("quoted values re-derived", result.stdout)

    def test_it_grades_more_than_a_token_number_of_values(self):
        """A check wired up but grading two values would pass vacuously."""
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        count = int(result.stdout.split("OK: ")[1].split(" ")[0])
        self.assertGreaterEqual(count, 30, msg=result.stdout)

    def test_it_sees_every_row_of_the_real_section_5_table(self):
        """The other half of the check's own MIN_SPEC_ROWS guard.

        That guard is set at 3, deliberately far from the real count, so it
        reports a parser that gave up rather than duplicating a number that
        would go stale. The real count is asserted here instead: section 5 is
        re-parsed independently, and the check must report exactly as many
        rows as this test finds. A silently-truncating parser fails here.
        """
        text = (REPO_ROOT / PROPOSAL).read_text(encoding="utf-8")
        rows, in_table = 0, False
        for line in text.split("\n"):
            if line.startswith("| Parameter |") and "Verdict" in line:
                in_table = True
                continue
            if in_table:
                if not line.startswith("|"):
                    break
                if set(line) <= set("|-: "):
                    continue
                rows += 1
        self.assertGreaterEqual(rows, 20, msg="section 5 table not found")

        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("all %d section 5 rows accounted for" % rows, result.stdout)


if __name__ == "__main__":
    unittest.main()
