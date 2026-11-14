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

``check-readme-status.sh``'s T1 tier-count rule (#928) is graded here too.
Its source of truth is a committed machine verdict rather than the record
tree, and the two traps a naive implementation hits -- the report's ``items``
array being longer than its own ``t1_item_count``, and a *struck* retraction
of the old figure sitting beside the live one -- are each pinned as a test
that must PASS, because both would otherwise fail a correct tree.

No PDK, no ngspice, no simulation input -- these scripts read committed files
and count paths.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _fixtures import TreeTestCase

SIM_DIR = Path(__file__).resolve().parents[1]
LIB = SIM_DIR / "lib"
README_CHECK = LIB / "check-readme-status.sh"
COVERAGE_CHECK = LIB / "check-characterization-coverage.sh"
CAMPAIGN_LIB = LIB / "record-campaigns.sh"

# A synthetic tree: campaign name -> number of evidence records in it.
CAMPAIGNS = {"lock-time": 3, "output-range": 2, "period-jitter": 1}
N_CAMPAIGNS = len(CAMPAIGNS)
N_RECORDS = sum(CAMPAIGNS.values())

# _Tree names each campaign's records "2026010<i>-000000-deadbee.md" for
# i in range(count) (see _Tree.__init__ below); a lexical sort is a
# chronological sort for this repo's <timestamp>-<hash> naming, so the
# highest i is the chronologically-latest record the latest-record-cited
# rule (#544) looks for in each campaign.
_LATEST = {name: f"2026010{count - 1}-000000-deadbee" for name, count in CAMPAIGNS.items()}

# Every synthetic record file is written with this exact body (see
# _Tree.__init__), so they all share one sha256 -- convenient for the
# content-hash rule (#544), which only cares that *a* hash matches *a* file.
_RECORD_BODY = "# record\n"
_RECORD_HASH = hashlib.sha256(_RECORD_BODY.encode()).hexdigest()[:12]


# The synthetic T1 verdict. Deliberately NOT the real tree's 6 of 22: if the
# rule ever read the repository's own signoff/tier-report.json instead of the
# throwaway tree's, these tests fail rather than pass by coincidence.
T1_MET = 3
T1_TOTAL = 7


def _tier_report_text(
    met: int = T1_MET,
    total: int = T1_TOTAL,
    *,
    items: list | None = None,
    drop: tuple = (),
    overrides: dict | None = None,
) -> str:
    """A minimal signoff/tier-report.json.

    ``items`` defaults to ``total`` T1 rows PLUS one each of T2/T3/T4 with a
    null partition -- i.e. deliberately longer than ``t1_item_count``, which
    is the real report's shape (22 T1 rows, 25 elements). A rule deriving the
    denominator from ``len(items)`` grades the wrong number against a correct
    README, so the default fixture carries the trap rather than a tidy array.
    """
    rows: list = [
        {
            "id": i + 1,
            "tier": "T1",
            "partition": "analog",
            "status": "met" if i < met else "unmet",
            "reason": None if i < met else "no_evidence",
        }
        for i in range(total)
    ]
    rows += [
        {"id": 90 + n, "tier": tier, "partition": None, "status": "unmet",
         "reason": "tier_not_supported"}
        for n, tier in enumerate(("T2", "T3", "T4"))
    ]
    report: dict = {
        "schema_version": 1,
        "t1_met_count": met,
        "t1_item_count": total,
        "items": rows if items is None else items,
    }
    report.update(overrides or {})
    for field in drop:
        report.pop(field, None)
    return json.dumps(report, indent=2) + "\n"


def _signoff_readme_text(
    met: int = T1_MET,
    total: int = T1_TOTAL,
    *,
    struck: bool = True,
    extra: str = "",
) -> str:
    """A minimal signoff/README.md, carrying the struck-retraction trap.

    ``struck=True`` (the default, and what the real file looks like) puts a
    retracted ``~~**0 of N T1 rows met**~~`` beside the live figure. The rule
    must not grade it; ``struck=False`` un-strikes the same sentence, which
    must then fail -- that pair is what proves the skip is load-bearing
    rather than vacuously passing.
    """
    retraction = f"**0 of {total} T1 rows met**"
    if struck:
        retraction = f"~~{retraction}~~"
    text = (
        "# signoff/ — this block's gap to T1, graded rather than hand-read\n\n"
        f"Today the verdict is **{met} of {total} T1 rows met** (the block's tier\n"
        f"is still `none`). {retraction} was the verdict until 2026-10-17.\n"
    )
    if extra:
        text += "\n" + extra + "\n"
    return text


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
        # Cites the actual chronologically-latest record id (see _LATEST)
        # so the latest-record-cited rule (#544) passes by default -- every
        # test below that does not target that rule specifically should not
        # have to think about it.
        body.append(f"| `{name}` | `sim/{name}/records/{_LATEST[name]}.md` | fine |")
    if extra:
        body.append("")
        body.append(extra)
    return "\n".join(body) + "\n"


def _readme_text(
    records: int = N_RECORDS,
    campaigns: int = N_CAMPAIGNS,
    extra: str = "",
    *,
    t1: tuple | None = None,
    tier_claim: str | None = None,
) -> str:
    """A minimal README.md that satisfies check-readme-status.sh.

    ``tier_claim=""`` drops the T1 sentence entirely (the claim-not-found
    case); ``t1=(met, total)`` states a different pair than the report does.
    """
    t1_met, t1_total = (T1_MET, T1_TOTAL) if t1 is None else t1
    if tier_claim is None:
        # Wrapped mid-claim on purpose: the rule collapses whitespace per
        # file, so a claim broken across a line must still be graded.
        tier_claim = (
            "The **machine verdict of record** is `signoff/tier-report.json`; today\n"
            f"it reads **{t1_met} of {t1_total}\n  rows met**.\n"
        )
    text = (
        "# gf180-pll\n\n"
        f"- **Done** — a reproducible PVT corner harness; **{records} evidence records**\n"
        f"  across {campaigns} verification campaigns; `period-jitter` covers 1 of the\n"
        "  mandated 45 PVT corners.\n"
    )
    if tier_claim:
        text += "\n" + tier_claim
    if extra:
        text += "\n" + extra + "\n"
    return text


def _status_page_text(extra: str = "") -> str:
    """A minimal sim/STATUS.md (the narrative moved out of README.md, #703)."""
    text = "# Campaign status narrative\n\n`period-jitter` covers 1 of the mandated 45 PVT corners.\n"
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

        (root / "signoff").mkdir(parents=True)

        self.write_readme(_readme_text())
        self.write_status_page(_status_page_text())
        self.write_report(_report_text())
        self.write_tier_report(_tier_report_text())
        self.write_signoff_readme(_signoff_readme_text())

    def write_readme(self, text: str) -> None:
        (self.root / "README.md").write_text(text)

    def write_status_page(self, text: str) -> None:
        (self.root / "sim" / "STATUS.md").write_text(text)

    def write_report(self, text: str) -> None:
        (self.root / "sim" / "CHARACTERIZATION.md").write_text(text)

    def write_tier_report(self, text: str) -> None:
        (self.root / "signoff" / "tier-report.json").write_text(text)

    def write_signoff_readme(self, text: str) -> None:
        (self.root / "signoff" / "README.md").write_text(text)

    def run(self, script: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / script.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(TreeTestCase):
    tree_cls = _Tree

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

    def test_a_stale_count_in_the_moved_status_page_is_caught(self):
        """The narrative moved to sim/STATUS.md (#703) stays graded."""
        self.tree.write_status_page(
            _status_page_text(extra=f"Elsewhere: {N_RECORDS - 2} evidence records.")
        )
        self.assertFails(README_CHECK, f"claims {N_RECORDS - 2} evidence records")

    def test_a_stale_period_jitter_coverage_in_the_status_page_is_caught(self):
        self.tree.write_status_page(
            _status_page_text(
                extra="`period-jitter` covers 44 of the mandated 45 PVT corners."
            )
        )
        self.assertFails(README_CHECK, "claims period-jitter covers 44")

    def test_a_missing_status_page_fails(self):
        (self.tree.root / "sim" / "STATUS.md").unlink()
        self.assertFails(README_CHECK, "sim/STATUS.md does not exist")

    def test_a_missing_count_still_fails(self):
        self.tree.write_readme("# gf180-pll\n\nNothing quantified here.\n")
        self.assertFails(README_CHECK, "could not find '<N> evidence records'")


class TestT1TierCountRule(_TreeTest):
    """check-readme-status.sh's T1 tier-count rule (#928).

    The regression: README.md calls `signoff/tier-report.json` the "machine
    verdict of record", promises the figure is "re-checked in CI so it cannot
    go stale", and then quoted **0 of 22 rows met** for weeks after the report
    moved to 6 -- nothing compared the sentence with the report. The same
    defect class had already been fixed one directory down in #654, which is
    the argument for a check rather than a third correction.
    """

    def test_a_correct_readme_passes(self):
        result = self.assertPasses(README_CHECK)
        self.assertIn(f"T1 at {T1_MET}/{T1_TOTAL} rows met", result.stdout)

    def test_a_stale_met_count_in_the_readme_is_caught(self):
        """The mutated-README fixture: the drift the rule exists for."""
        self.tree.write_readme(_readme_text(t1=(0, T1_TOTAL)))
        self.assertFails(
            README_CHECK,
            f"README.md claims 0 of {T1_TOTAL} T1 rows met",
            f"signoff/tier-report.json records {T1_MET} of {T1_TOTAL}",
        )

    def test_an_overstated_met_count_fails_too(self):
        """Two-sided: claiming more evidence than the report grants is worse."""
        self.tree.write_readme(_readme_text(t1=(T1_TOTAL, T1_TOTAL)))
        self.assertFails(README_CHECK, f"claims {T1_TOTAL} of {T1_TOTAL} T1 rows met")

    def test_a_stale_denominator_is_caught(self):
        """Both halves of "N of M" are graded, not only the numerator."""
        self.tree.write_readme(_readme_text(t1=(T1_MET, T1_TOTAL + 3)))
        self.assertFails(README_CHECK, f"claims {T1_MET} of {T1_TOTAL + 3} T1 rows met")

    def test_a_claim_wrapped_across_lines_is_graded(self):
        """The baseline fixture wraps mid-claim (see _readme_text), so the
        passing case already proves wrapping is tolerated; this pins that a
        *stale* wrapped claim is still caught rather than silently unmatched."""
        self.assertIn("rows met**", (self.tree.root / "README.md").read_text())
        self.tree.write_readme(
            _readme_text(
                tier_claim=f"Today it reads **{T1_MET - 1} of\n  {T1_TOTAL} rows met**.\n"
            )
        )
        self.assertFails(README_CHECK, f"claims {T1_MET - 1} of {T1_TOTAL} T1 rows met")

    def test_a_second_contradicting_tier_count_later_is_caught(self):
        """Every occurrence is graded, not just the first correct one."""
        self.tree.write_readme(
            _readme_text(extra=f"Elsewhere, unrevised: 0 of {T1_TOTAL} rows met.")
        )
        self.assertFails(README_CHECK, f"claims 0 of {T1_TOTAL} T1 rows met")

    # -- trap 1: the struck retraction beside the live figure ---------------

    def test_a_struck_retraction_is_not_graded(self):
        """signoff/README.md:11's `~~**0 of 22 T1 rows met**~~`, in miniature.

        This repository corrects itself by striking the old sentence and
        writing the new one beside it, so a rule that graded struck spans
        would read a retraction as a live claim and fail a *correct* tree.
        The baseline fixture carries the strike, so this is the passing case.
        """
        signoff = (self.tree.root / "signoff" / "README.md").read_text()
        self.assertIn(f"~~**0 of {T1_TOTAL} T1 rows met**~~", signoff)
        self.assertPasses(README_CHECK)

    def test_un_striking_the_retraction_makes_it_graded(self):
        """The other half of the pair: the skip must not be vacuous.

        Without this, a rule that never matched anything in signoff/README.md
        at all would pass the test above for the wrong reason.
        """
        self.tree.write_signoff_readme(_signoff_readme_text(struck=False))
        self.assertFails(
            README_CHECK, f"signoff/README.md claims 0 of {T1_TOTAL} T1 rows met"
        )

    def test_a_struck_span_does_not_exempt_the_live_count_beside_it(self):
        """The exemption must not leak past its own `~~` pair."""
        self.tree.write_signoff_readme(_signoff_readme_text(met=T1_MET - 1))
        self.assertFails(
            README_CHECK,
            f"signoff/README.md claims {T1_MET - 1} of {T1_TOTAL} T1 rows met",
        )

    # -- trap 2: items[] is longer than t1_item_count ----------------------

    def test_a_longer_items_array_is_not_the_denominator(self):
        """The report's `items` holds the T1 rows plus T2/T3/T4 siblings.

        The real file has 22 T1 rows and 25 elements, so a rule deriving the
        denominator from `len(items)` grades 25 and fails a correct README.
        The baseline fixture is built with that shape; this asserts it.
        """
        report = json.loads((self.tree.root / "signoff" / "tier-report.json").read_text())
        self.assertEqual(report["t1_item_count"], T1_TOTAL)
        self.assertEqual(len(report["items"]), T1_TOTAL + 3)
        self.assertPasses(README_CHECK)

    # -- the report itself -------------------------------------------------

    def test_a_zero_met_count_is_still_graded(self):
        """A zero is a value, not a missing claim.

        Both directions: a README agreeing with a genuine 0 passes, and one
        still claiming the old figure against it fails. A truthiness test on
        the count would silently skip the rule in exactly the state the
        repository was in before #798.
        """
        self.tree.write_tier_report(_tier_report_text(met=0))
        self.tree.write_readme(_readme_text(t1=(0, T1_TOTAL)))
        self.tree.write_signoff_readme(_signoff_readme_text(met=0))
        self.assertPasses(README_CHECK)

        self.tree.write_readme(_readme_text(t1=(T1_MET, T1_TOTAL)))
        self.assertFails(README_CHECK, f"records 0 of {T1_TOTAL}")

    def test_a_missing_tier_report_fails_loudly(self):
        """Not a skip: the verdict of record being absent is a failure."""
        (self.tree.root / "signoff" / "tier-report.json").unlink()
        self.assertFails(README_CHECK, "signoff/tier-report.json does not exist")

    def test_an_unparseable_tier_report_fails_loudly(self):
        self.tree.write_tier_report("{ not json at all\n")
        self.assertFails(README_CHECK, "could not be read as JSON")

    def test_a_tier_report_that_is_not_an_object_fails(self):
        self.tree.write_tier_report("[1, 2, 3]\n")
        self.assertFails(README_CHECK, "is not a JSON object")

    def test_a_missing_count_field_fails(self):
        self.tree.write_tier_report(_tier_report_text(drop=("t1_met_count",)))
        self.assertFails(README_CHECK, "has no integer `t1_met_count` field")

    def test_a_non_integer_count_field_fails(self):
        """A string "6" is not the report answering the question."""
        self.tree.write_tier_report(_tier_report_text(overrides={"t1_item_count": "7"}))
        self.assertFails(README_CHECK, "has no integer `t1_item_count` field")

    def test_a_boolean_count_field_fails(self):
        """bool is an int subclass; `True` must not read as a count of 1."""
        self.tree.write_tier_report(_tier_report_text(overrides={"t1_met_count": True}))
        self.assertFails(README_CHECK, "has no integer `t1_met_count` field")

    # -- the claim must exist in both graded documents ---------------------

    def test_a_readme_with_no_tier_claim_fails(self):
        """A selector matching nothing is a check reporting OK ungraded."""
        self.tree.write_readme(_readme_text(tier_claim=""))
        self.assertFails(
            README_CHECK, "could not find '<N> of <M> rows met' in README.md"
        )

    def test_a_signoff_readme_with_no_tier_claim_fails(self):
        self.tree.write_signoff_readme("# signoff/\n\nNothing quantified here.\n")
        self.assertFails(
            README_CHECK, "could not find '<N> of <M> rows met' in signoff/README.md"
        )

    def test_a_missing_signoff_readme_fails(self):
        (self.tree.root / "signoff" / "README.md").unlink()
        self.assertFails(README_CHECK, "signoff/README.md could not be read")

    def test_deleting_the_claim_is_not_a_fix(self):
        """Both documents at once: a stale claim cannot be un-staled by
        removing it, the same doctrine as the aggregate-count rule."""
        self.tree.write_readme(_readme_text(tier_claim=""))
        self.tree.write_signoff_readme("# signoff/\n\nNo figure here.\n")
        result = self.assertFails(README_CHECK, "README.md", "signoff/README.md")
        self.assertEqual(result.stderr.count("could not find"), 2)


class TestLatestRecordCitedRule(_TreeTest):
    """check-characterization-coverage.sh's reverse-direction rule (#544).

    The real regression: `sim/vco-tuning-range/records/20260923-084925-1655e11.md`
    closed #482's band-0 finding inside an already-listed campaign, and
    nothing forced `sim/CHARACTERIZATION.md` to cite it -- the pre-existing
    coverage rule only asks whether the *campaign* has a row, which it
    already did.
    """

    def test_every_campaigns_latest_record_cited_passes(self):
        """The baseline fixture cites each campaign's newest record by
        construction (see `_LATEST`) -- this is the rule's quiet case."""
        self.assertPasses(COVERAGE_CHECK)

    def test_an_uncited_latest_record_fails(self):
        """A row that cites something other than the tree's newest record."""
        stale = _report_text().replace(
            f"`sim/period-jitter/records/{_LATEST['period-jitter']}.md`",
            "`sim/period-jitter/records/20260099-000000-deadbee.md`",
        )
        self.tree.write_report(stale)
        self.assertFails(
            COVERAGE_CHECK,
            f"period-jitter:{_LATEST['period-jitter']}",
            "NOT_AGGREGATED",
        )

    def test_an_allowlisted_record_need_not_be_cited(self):
        """The script's shipped NOT_AGGREGATED entry is live, not dead code.

        Exercises the one exclusion check-characterization-coverage.sh ships
        with (`sim/supply-sensitivity/records/20260925-111906-1937f52.md`,
        #544) against a minimal tree carrying only that record, cited
        nowhere -- the check must still pass.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sim" / "lib").mkdir(parents=True)
            for script in (README_CHECK, COVERAGE_CHECK, CAMPAIGN_LIB):
                shutil.copy2(script, root / "sim" / "lib" / script.name)
            records = root / "sim" / "supply-sensitivity" / "records"
            records.mkdir(parents=True)
            (records / "20260925-111906-1937f52.md").write_text(_RECORD_BODY)
            (root / "sim" / "CHARACTERIZATION.md").write_text(
                "# sim/ — aggregated characterization report\n\n"
                + _coverage_bullet(1, 1)
                + "\n| Campaign | Latest record | Headline |\n|---|---|---|\n"
                "| `supply-sensitivity` | (allowlisted, not cited on purpose) | fine |\n"
            )
            result = subprocess.run(
                ["bash", str(root / "sim" / "lib" / COVERAGE_CHECK.name)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


class TestContentHashRule(_TreeTest):
    """check-characterization-coverage.sh's optional content-hash leg (#544)."""

    def test_no_path_hash_citations_is_trivially_clean(self):
        """The baseline fixture cites no `path` (`hash`) pairs -- same
        doctrine as check-record-supersession.sh: nothing cited, nothing to
        grade."""
        result = self.assertPasses(COVERAGE_CHECK)
        self.assertIn("nothing to check", result.stdout)

    def test_a_matching_hash_passes(self):
        report = _report_text().replace(
            f"`sim/lock-time/records/{_LATEST['lock-time']}.md`",
            f"`sim/lock-time/records/{_LATEST['lock-time']}.md` (`{_RECORD_HASH}`)",
        )
        self.tree.write_report(report)
        result = self.assertPasses(COVERAGE_CHECK)
        self.assertIn("path` (`hash`) citations", result.stdout)

    def test_a_stale_hash_fails(self):
        report = _report_text().replace(
            f"`sim/lock-time/records/{_LATEST['lock-time']}.md`",
            f"`sim/lock-time/records/{_LATEST['lock-time']}.md` (`deadbeefcafe`)",
        )
        self.tree.write_report(report)
        self.assertFails(
            COVERAGE_CHECK,
            f"cites `sim/lock-time/records/{_LATEST['lock-time']}.md` with hash `deadbeefcafe`",
            f"on disk is `{_RECORD_HASH}`",
        )

    def test_a_citation_of_a_nonexistent_file_fails(self):
        report = _report_text().replace(
            f"`sim/lock-time/records/{_LATEST['lock-time']}.md`",
            f"`sim/lock-time/records/20269999-000000-nope.md` (`{_RECORD_HASH}`)",
        )
        self.tree.write_report(report)
        self.assertFails(COVERAGE_CHECK, "which does not exist on disk")


if __name__ == "__main__":
    unittest.main()
