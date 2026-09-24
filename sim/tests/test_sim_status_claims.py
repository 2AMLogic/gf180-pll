#!/usr/bin/env python3
"""Unit tests for the two sim-side status checks (issues #117, #237).

    python3 -m unittest discover -s sim/tests -v

``sim/lib/check-readme-status.sh`` and
``sim/lib/check-characterization-coverage.sh`` both grade hand-written prose
against the ``sim/*/records/*.md`` tree.  Running them only against the real
tree, where they pass, proves nothing about whether they would have *caught*
the drift they exist for -- so every test here builds a throwaway tree whose
answer is known and runs the real scripts in it.

The drift that motivated the aggregate-count rule: ``sim/CHARACTERIZATION.md``
spent six weeks stating the counts of a much smaller tree (19 records and 3
campaigns behind) *and* quoting ``README.md``'s status line as agreeing with
those figures, while ``check-readme-status.sh`` had already forced that README
line to the true numbers.  Both sim-side checks reported OK on that tree: one
grades README only, the other graded row coverage only.

No PDK, no ngspice, no simulation input -- these scripts read committed files
and count paths.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
LIB = SIM_DIR / "lib"
README_CHECK = LIB / "check-readme-status.sh"
COVERAGE_CHECK = LIB / "check-characterization-coverage.sh"
CAMPAIGN_LIB = LIB / "record-campaigns.sh"

# A synthetic tree: campaign name -> number of evidence records in it.
CAMPAIGNS = {"lock-time": 3, "output-range": 2, "period-jitter": 1}
N_CAMPAIGNS = len(CAMPAIGNS)
N_RECORDS = sum(CAMPAIGNS.values())


def _coverage_bullet(campaigns: int, records: int) -> str:
    """The report's current-count claim, in the real document's shape."""
    return (
        "- **Coverage.** One entry below for every directory under `sim/` that\n"
        "  contains a `records/` subdirectory. At this report's original writing that\n"
        "  was **20 campaign directories, 61 evidence records**; the tree has grown\n"
        f"  since, and the current count is **{campaigns} campaign directories, "
        f"{records} evidence\n  records**.\n"
    )


def _report_text(
    campaigns: int = N_CAMPAIGNS,
    records: int = N_RECORDS,
    *,
    rows: dict | None = None,
    bullet: str | None = None,
    extra: str = "",
) -> str:
    """A minimal sim/CHARACTERIZATION.md that satisfies both rules."""
    rows = CAMPAIGNS if rows is None else rows
    body = ["# sim/ — aggregated characterization report", ""]
    body.append(
        _coverage_bullet(campaigns, records) if bullet is None else bullet
    )
    body.append("")
    body.append("| Campaign | Latest record | Headline |")
    body.append("|---|---|---|")
    for name in rows:
        body.append(f"| `{name}` | `sim/{name}/records/x.md` | fine |")
    if extra:
        body.append("")
        body.append(extra)
    return "\n".join(body) + "\n"


def _readme_text(records: int = N_RECORDS, campaigns: int = N_CAMPAIGNS, extra: str = "") -> str:
    """A minimal README.md that satisfies check-readme-status.sh."""
    text = (
        "# gf180-pll\n\n"
        f"- **Done** — a reproducible PVT corner harness; **{records} evidence records**\n"
        f"  across {campaigns} verification campaigns; `period-jitter` covers 1 of the\n"
        "  mandated 45 PVT corners.\n"
    )
    if extra:
        text += "\n" + extra + "\n"
    return text


class _Tree:
    """A throwaway repo tree with both checks installed at sim/lib/."""

    def __init__(self, root: Path, rows: dict | None = None):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        for script in (README_CHECK, COVERAGE_CHECK, CAMPAIGN_LIB):
            shutil.copy2(script, root / "sim" / "lib" / script.name)

        rows = CAMPAIGNS if rows is None else rows
        for name, count in rows.items():
            records = root / "sim" / name / "records"
            records.mkdir(parents=True)
            for i in range(count):
                (records / f"2026010{i}-000000-deadbee.md").write_text("# record\n")
            # period-jitter's coverage rule counts distinct corner logs.
            if name == "period-jitter":
                corners = root / "sim" / name / "corners" / "20260101-000000-deadbee"
                corners.mkdir(parents=True)
                (corners / "typical-27C-3p30V.log").write_text("ok\n")

        self.write_readme(_readme_text())
        self.write_report(_report_text())

    def write_readme(self, text: str) -> None:
        (self.root / "README.md").write_text(text)

    def write_report(self, text: str) -> None:
        (self.root / "sim" / "CHARACTERIZATION.md").write_text(text)

    def run(self, script: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / script.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def assertPasses(self, script: Path) -> subprocess.CompletedProcess:
        result = self.tree.run(script)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        return result

    def assertFails(self, script: Path, *needles: str) -> subprocess.CompletedProcess:
        result = self.tree.run(script)
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        return result


class TestAggregateCountRule(_TreeTest):
    """sim/lib/check-characterization-coverage.sh's aggregate-count rule."""

    def test_a_correct_report_passes(self):
        result = self.assertPasses(COVERAGE_CHECK)
        self.assertIn(
            f"states {N_CAMPAIGNS} campaigns / {N_RECORDS} records", result.stdout
        )

    def test_the_real_drift_shape_is_caught(self):
        """The exact regression: counts of a smaller tree, every row present.

        The coverage rule alone reports OK here -- every campaign has a row.
        Only the count rule sees that the report describes a tree that has
        moved on underneath it.
        """
        self.tree.write_report(_report_text(campaigns=N_CAMPAIGNS - 1, records=N_RECORDS - 3))
        self.assertFails(
            COVERAGE_CHECK,
            f"holds {N_RECORDS} records across {N_CAMPAIGNS} campaigns",
        )

    def test_a_stale_quotation_of_the_readme_line_is_caught(self):
        """Quoting a checked document is not the same as being checked.

        The stale bullet asserted that README's own graded line agreed with
        its figures. The rule grades the quotation too, in the other claim
        shape ("<M> evidence records across <N> verification campaigns"), so
        the assertion cannot outlive the line it cites.
        """
        self.tree.write_report(
            _report_text(
                extra=(
                    "`README.md`'s status section states the same pair as "
                    f"{N_RECORDS - 3} evidence records across {N_CAMPAIGNS - 1} "
                    "verification campaigns."
                )
            )
        )
        self.assertFails(COVERAGE_CHECK, "evidence records across")

    def test_a_second_contradicting_count_later_in_the_document_is_caught(self):
        """Every occurrence is graded, not just the first correct one."""
        self.tree.write_report(
            _report_text(
                extra=(
                    "Later, in a section nobody re-read: this report aggregates "
                    f"{N_CAMPAIGNS - 1} campaign directories, {N_RECORDS - 3} "
                    "evidence records."
                )
            )
        )
        self.assertFails(COVERAGE_CHECK, "campaign directories")

    def test_an_overstated_count_fails_too(self):
        """Two-sided: over-reporting the tree is drift as much as under."""
        self.tree.write_report(_report_text(campaigns=N_CAMPAIGNS + 2, records=N_RECORDS + 40))
        self.assertFails(COVERAGE_CHECK, f"states {N_CAMPAIGNS + 2} campaign directories")

    def test_deleting_the_count_is_not_a_fix(self):
        """A claim cannot be un-staled by removing it."""
        self.tree.write_report(
            _report_text(bullet="- **Coverage.** One entry below for every campaign.")
        )
        self.assertFails(COVERAGE_CHECK, "states no current count of what it aggregates")

    def test_the_historical_figure_is_exempt(self):
        """The report may say where it started without being forced to lie.

        The "at this report's original writing that was **20 campaign
        directories, 61 evidence records**" clause sits in the same sentence
        as the live count, roughly 110 characters ahead of it, and describes a
        tree that no longer exists. Grading it would force history to be
        rewritten on every new record.
        """
        self.assertPasses(COVERAGE_CHECK)
        self.assertIn("61 evidence records", (self.tree.root / "sim" / "CHARACTERIZATION.md").read_text())

    def test_the_exemption_does_not_leak_onto_the_live_count(self):
        """The marker must not exempt the *current* figure beside it."""
        self.tree.write_report(_report_text(campaigns=N_CAMPAIGNS, records=N_RECORDS - 1))
        self.assertFails(COVERAGE_CHECK, f"{N_RECORDS - 1} evidence records")

    def test_a_missing_campaign_row_still_fails(self):
        """The pre-existing coverage rule is untouched by the new one."""
        rows = dict(list(CAMPAIGNS.items())[:-1])
        self.tree.write_report(_report_text(rows=rows))
        self.assertFails(COVERAGE_CHECK, "has no entry for:", "period-jitter")

    def test_both_rules_report_in_one_run(self):
        """A missing row and a stale count are both named, not just the first."""
        rows = dict(list(CAMPAIGNS.items())[:-1])
        self.tree.write_report(
            _report_text(rows=rows, campaigns=N_CAMPAIGNS - 1, records=N_RECORDS - 3)
        )
        self.assertFails(COVERAGE_CHECK, "has no entry for:", "holds")


class TestReadmeCountsEveryOccurrence(_TreeTest):
    """sim/lib/check-readme-status.sh, after #237 dropped its `head -1`."""

    def test_a_correct_readme_passes(self):
        result = self.assertPasses(README_CHECK)
        self.assertIn(f"{N_RECORDS} records", result.stdout)

    def test_a_second_stale_record_count_later_in_the_readme_is_caught(self):
        """The gap the layout-side count rule closed in #495, sim side.

        The first (correct) occurrence used to satisfy the check outright,
        so a contradicting sibling count anywhere below it passed silently.
        """
        self.tree.write_readme(
            _readme_text(extra=f"Elsewhere, unrevised: {N_RECORDS - 2} evidence records.")
        )
        self.assertFails(README_CHECK, f"claims {N_RECORDS - 2} evidence records")

    def test_a_second_stale_campaign_count_later_in_the_readme_is_caught(self):
        self.tree.write_readme(
            _readme_text(extra=f"Elsewhere: {N_CAMPAIGNS + 5} verification campaigns.")
        )
        self.assertFails(README_CHECK, f"claims {N_CAMPAIGNS + 5} verification campaigns")

    def test_every_repeated_correct_count_passes(self):
        """The direction that must never regress: restating a true count."""
        self.tree.write_readme(
            _readme_text(
                extra=(
                    f"Restated, still true: {N_RECORDS} evidence records across "
                    f"{N_CAMPAIGNS} verification campaigns."
                )
            )
        )
        self.assertPasses(README_CHECK)

    def test_a_missing_count_still_fails(self):
        self.tree.write_readme("# gf180-pll\n\nNothing quantified here.\n")
        self.assertFails(README_CHECK, "could not find '<N> evidence records'")


if __name__ == "__main__":
    unittest.main()
