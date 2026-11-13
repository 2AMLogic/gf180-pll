#!/usr/bin/env python3
"""Unit tests for ``docs/lib/check-claim-checker-inventory.sh`` (issue #237).

    python3 -m unittest discover -s docs/tests -v

The check grades the claims this repository's documents make *about the
grading family itself* -- "there are 16 ``*/lib/check-*.sh`` scripts", "Eleven
checks grade the table above".  Every other check here grades a document
against evidence, a netlist, the spec or the forge, so none of them could see
those two claims go stale, and both had: ``sim/lib/check-artifact-manifests.sh``
was committed on 2026-10-23 and ``docs/claim-checker-inventory.md`` -- the
ratified answer to which checkers exist -- went three weeks asserting a total
of sixteen over a table of sixteen rows while the tree held seventeen.

Every test builds a throwaway tree whose answer is known, installs the real
script in it, and runs it there.  No network, no forge, no PDK: the family the
check discovers is whatever the fixture wrote, which is what makes running the
real script a test of the check rather than of a reimplementation.

One property of the fixture is worth stating because it is load-bearing: the
copied check is *itself* a member of the family it discovers (it lives at
``docs/lib/check-*.sh``) and its own text names the proposal's path, so it
counts as a reader too.  Every expected count below includes it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _fixtures import TreeWriter

DOCS_DIR = Path(__file__).resolve().parents[1]
CHECK = DOCS_DIR / "lib" / "check-claim-checker-inventory.sh"

INVENTORY = "docs/claim-checker-inventory.md"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"

#: The check's own relative path inside a throwaway tree. It is a family
#: member there exactly as it is in the real repository.
SELF = "docs/lib/check-claim-checker-inventory.sh"

#: A checker that reads the proposal, and one that does not. The difference is
#: the whole of rule 4's derivation, so both shapes are in every fixture.
READER = "#!/usr/bin/env bash\n# grades %s\nexit 0\n" % PROPOSAL
NON_READER = "#!/usr/bin/env bash\n# grades spec/pll.md\nexit 0\n"


def _inventory(total="three", rows=None) -> str:
    rows = [SELF, "sim/lib/check-alpha.sh", "spec/lib/check-beta.sh"] \
        if rows is None else rows
    lines = [
        "# Claim-checker inventory",
        "",
        "Counts are `wc -l` at the commit that wrote each row; there are %s"
        % total,
        "`*/lib/check-*.sh` scripts.",
        "",
        "| Script | Lines | Reads | Class | Commits | Catch | Decision |",
        "|---|---:|---|---|---:|---|---|",
    ]
    for path in rows:
        lines.append("| `%s` | 1 | a tree | tree | 1 | drift | KEEP |" % path)
    return "\n".join(lines) + "\n"


def _proposal(readers="two", family="three") -> str:
    return (
        "# Chipalooza Challenge #5 — integer-N PLL proposal\n"
        "\n"
        "### 5.1 Value provenance\n"
        "\n"
        "**%s of this repository's %s claim checkers read this\n"
        "document, and until 2026-09-26 none of them graded a number.**\n"
        % (readers, family)
    )


class _Tree(TreeWriter):
    """A throwaway repo tree with the real check and a miniature family."""

    def __init__(self, root: Path, at: str = SELF):
        self.root = root
        self.at = at
        installed = root / at
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CHECK, installed)
        self.write("sim/lib/check-alpha.sh", READER)
        self.write("spec/lib/check-beta.sh", NON_READER)
        self.write(INVENTORY, _inventory())
        self.write(PROPOSAL, _proposal())

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / self.at)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    AT = SELF

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name), at=self.AT)
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


class TestFamilyDiscovery(_TreeTest):
    def test_a_clean_tree_passes(self):
        result = self.assertPasses()
        self.assertIn("3 checker(s) match", result.stdout)
        self.assertIn("2 of them read", result.stdout)

    def test_an_installer_managed_copy_is_not_a_family_member(self):
        """`.loom/` and `.claude/` are resync-refreshed and owned upstream."""
        self.tree.write(".loom/lib/check-upstream.sh", NON_READER)
        self.assertPasses()


class TestEmptyFamily(_TreeTest):
    #: Installed outside the pathspec so the family it discovers is empty.
    #: `docs/bin/../..` is still the tree root, so the check runs normally --
    #: it simply finds nothing to inventory.
    AT = "docs/bin/check-claim-checker-inventory.sh"

    def test_discovering_nothing_fails_rather_than_passing(self):
        """The trap this repository names wherever it grades a zero."""
        shutil.rmtree(self.tree.root / "sim")
        shutil.rmtree(self.tree.root / "spec")
        self.assertFails("matched no checker", "not a pass")


class TestInventoryTotal(_TreeTest):
    def test_a_stale_total_is_caught(self):
        """The real defect: sixteen asserted over a tree of seventeen."""
        self.tree.write(INVENTORY, _inventory(total="16"))
        self.assertFails('says the number of `*/lib/check-*.sh` scripts is "16"',
                         "the tree has 3")

    def test_digits_and_words_are_both_accepted(self):
        self.tree.write(INVENTORY, _inventory(total="3"))
        self.assertPasses()

    def test_a_count_past_the_word_list_fails_rather_than_passing(self):
        """The word list stops at thirty; past it, digits are the honest form.

        A count the check cannot parse must fail loudly -- passing for want of
        a parser would be a guard reporting clean on input it never read.
        """
        self.tree.write(INVENTORY, _inventory(total="thirty-one"))
        self.assertFails("cannot read as a number", "digits")

    def test_deleting_the_sentence_fails(self):
        self.tree.write(INVENTORY, "# Claim-checker inventory\n\nNo total.\n")
        self.assertFails("no longer states the size")

    def test_the_sentence_is_found_by_the_pathspec_not_the_prose(self):
        """Rewording around the number is free; changing the number is not."""
        self.tree.write(
            INVENTORY,
            _inventory().replace(
                "Counts are `wc -l` at the commit that wrote each row; there",
                "Rewritten entirely, and there",
            ),
        )
        self.assertPasses()


class TestInventoryRows(_TreeTest):
    def test_a_script_with_no_row_is_caught(self):
        """`sim/lib/check-artifact-manifests.sh`'s real three-week absence."""
        self.tree.write(
            INVENTORY, _inventory(rows=[SELF, "spec/lib/check-beta.sh"]))
        self.assertFails("has no row for `sim/lib/check-alpha.sh`")

    def test_a_row_naming_a_script_the_tree_does_not_have_is_caught(self):
        self.tree.write(INVENTORY, _inventory(
            total="four",
            rows=[SELF, "sim/lib/check-alpha.sh", "spec/lib/check-beta.sh",
                  "sim/lib/check-deleted.sh"],
        ))
        self.assertFails("carries a row for `sim/lib/check-deleted.sh`")

    def test_a_duplicated_row_cannot_stand_in_for_a_missing_one(self):
        """The row *set* is graded, not its length -- a count can agree while
        the sets differ, which is exactly how the real defect survived."""
        self.tree.write(INVENTORY, _inventory(
            rows=[SELF, "sim/lib/check-alpha.sh", "sim/lib/check-alpha.sh"]))
        self.assertFails("more than one row for `sim/lib/check-alpha.sh`",
                         "has no row for `spec/lib/check-beta.sh`")

    def test_a_missing_inventory_is_a_failure(self):
        (self.tree.root / INVENTORY).unlink()
        self.assertFails("could not be read")


class TestProposalCounts(_TreeTest):
    def test_a_stale_reader_count_is_caught(self):
        self.tree.write(PROPOSAL, _proposal(readers="eleven"))
        self.assertFails('the number of checkers that read it is "eleven"',
                         "the tree has 2")

    def test_a_stale_family_count_is_caught(self):
        self.tree.write(PROPOSAL, _proposal(family="seventeen"))
        self.assertFails('the size of the checker family is "seventeen"',
                         "the tree has 3")

    def test_deleting_the_sentence_fails(self):
        """Removing a narration must not be the way to stop it going stale."""
        self.tree.write(PROPOSAL, "# Proposal\n\n### 5.1\n\nNo counts here.\n")
        self.assertFails("no longer states how many", "should not print")

    def test_a_delegating_wrapper_counts_as_a_reader(self):
        """`check-artifact-manifests.sh`'s shape: logic in a `.py` sibling.

        Grading only the twelve-line wrapper would report that it reads
        nothing, so a checker could read the proposal and not be counted.
        """
        self.tree.write(
            "sim/lib/check-beta.sh",
            "#!/usr/bin/env bash\nexec python3 "
            '"$(dirname "${BASH_SOURCE[0]}")/check_beta.py" "$@"\n',
        )
        self.tree.write("sim/lib/check_beta.py", "# grades %s\n" % PROPOSAL)
        self.tree.write(INVENTORY, _inventory(
            total="four",
            rows=[SELF, "sim/lib/check-alpha.sh", "sim/lib/check-beta.sh",
                  "spec/lib/check-beta.sh"],
        ))
        self.tree.write(PROPOSAL, _proposal(readers="three", family="four"))
        self.assertPasses()

    def test_a_missing_proposal_is_a_failure(self):
        (self.tree.root / PROPOSAL).unlink()
        self.assertFails("could not be read")


if __name__ == "__main__":
    unittest.main()
