#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-record-supersession.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades the *citation graph*: a reader-facing document must not point
at a ``sim/`` evidence record that a later record has superseded without naming
a successor somewhere in the same document.  It exists because
``sim/README.md`` makes standing a *forward* scan ("a record is `current` until
some later record names it in a **Supersedes** field") and nothing ran that
scan -- so ``docs/chipalooza/challenge-5-proposal.md``, the document meant to
be read by an outsider, described the ``period-jitter`` campaign's one FAIL as
a live measurement defect for 18 days after issue #273 closed and a successor
record re-measured both affected points as PASS.

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

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-record-supersession.sh"

OLD = "20260101-000000-aaaaaaa"
NEW = "20260202-000000-bbbbbbb"
NEWER = "20260303-000000-ccccccc"
SOLO = "20260404-000000-ddddddd"

#: An uncited, unremarkable supersession pair, so that a tree built to test the
#: `Supersedes`-field parser still has one real edge on it -- otherwise the
#: broken-parser guard (TestSelfDefence) fires and masks what is under test.
EDGE = {"devchar-cp": {"20260505-000000-eeeeeee": None,
                       "20260606-000000-fffffff": "20260505-000000-eeeeeee"}}

GRADED = (
    "README.md",
    "sim/CHARACTERIZATION.md",
    "docs/chipalooza/challenge-5-proposal.md",
)


def _record(supersedes: str | None = None, qualifier: str = "") -> str:
    """A record file holding only the fields this check reads."""
    body = "# Record\n\n- **Claim**: something\n"
    if supersedes is not None:
        body += f"- **Supersedes**: {supersedes}{qualifier}\n"
    return body


class _Tree:
    """A throwaway repo tree with the real check installed at sim/lib/."""

    #: campaign -> {record id: Supersedes field value (None = no field)}
    DEFAULT = {
        "period-jitter": {
            OLD: None,
            NEW: OLD,
            SOLO: "(none -- first record for this claim)",
        }
    }

    def __init__(self, root: Path, records: dict | None = None):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)

        # `records={}` means "an empty tree", not "use the default" -- the
        # empty-tree guard is one of the cases under test.
        for campaign, ids in (self.DEFAULT if records is None else records).items():
            rec_dir = root / "sim" / campaign / "records"
            rec_dir.mkdir(parents=True, exist_ok=True)
            for rid, supersedes in ids.items():
                (rec_dir / f"{rid}.md").write_text(_record(supersedes))

        # Every graded document must exist; by default each is clean.
        for doc in GRADED:
            path = root / doc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# doc\n\nNo record is cited here.\n")

    def write(self, doc: str, text: str) -> None:
        (self.root / doc).write_text(text)

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    records: dict | None = None

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name), self.records)
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


class TestForwardPointerRule(_TreeTest):
    def test_a_document_citing_nothing_passes(self):
        self.assertPasses()

    def test_citing_only_the_current_record_passes(self):
        self.tree.write(
            "docs/chipalooza/challenge-5-proposal.md",
            f"Measured value | `sim/period-jitter/records/{NEW}.md`\n",
        )
        self.assertPasses()

    def test_the_real_drift_shape_is_caught(self):
        """The exact regression: a superseded citation, no successor named.

        This is the proposal's period-jitter row as it stood at `44c40062` --
        the cited record exists, reads perfectly well, and has been replaced.
        """
        self.tree.write(
            "docs/chipalooza/challenge-5-proposal.md",
            f"overall status is FAIL ... filed as issue #273 | "
            f"`sim/period-jitter/records/{OLD}.md`\n",
        )
        self.assertFails(
            "docs/chipalooza/challenge-5-proposal.md",
            f"cites the superseded record `{OLD}`",
            f"`{NEW}`",
        )

    def test_every_graded_document_is_checked_not_just_the_first(self):
        for doc in GRADED:
            with self.subTest(doc=doc):
                self.setUp()
                self.tree.write(doc, f"cited: {OLD}\n")
                self.assertFails(doc, f"cites the superseded record `{OLD}`")

    def test_naming_the_successor_anywhere_in_the_document_passes(self):
        """Document-scoped, not citation-site-scoped -- deliberately.

        sim/README.md's per-bench supersession rule means a predecessor may be
        cited for a half a successor did not replace.  Requiring the successor
        beside the citation would force noise; requiring it *somewhere* still
        guarantees the reader a thread to pull.
        """
        self.tree.write(
            "sim/CHARACTERIZATION.md",
            f"| row | `sim/period-jitter/records/{OLD}.md` | headline |\n\n"
            f"Several sections later: superseded by `{NEW}`.\n",
        )
        self.assertPasses()

    def test_dropping_the_citation_is_a_legitimate_fix(self):
        """Pinned because it differs from the sibling checks' doctrine.

        "Deleting the number is not a fix" holds where the number *is* the
        claim.  Here the claim is a pointer, and a document that points at
        nothing stale has nothing stale to grade.  If that ever stops being
        the intent, this test is the place it has to be argued.
        """
        self.tree.write("docs/chipalooza/challenge-5-proposal.md", "No citation.\n")
        self.assertPasses()

    def test_a_chain_must_be_followed_to_a_current_record(self):
        """Naming a successor is itself a citation of that successor.

        So stopping halfway down a chain does not satisfy the rule: this is
        how fixing the proposal's lock-detector citation pulled in
        `20260916-052313-b1633b5` as well as `20260802-050119-c24ee3a`.
        """
        self.records = {"period-jitter": {OLD: None, NEW: OLD, NEWER: NEW}}
        self.setUp()
        self.tree.write("README.md", f"{OLD} superseded by {NEW}\n")
        self.assertFails(f"cites the superseded record `{NEW}`", f"`{NEWER}`")

    def test_a_chain_named_to_its_end_passes(self):
        self.records = {"period-jitter": {OLD: None, NEW: OLD, NEWER: NEW}}
        self.setUp()
        self.tree.write("README.md", f"{OLD} -> {NEW} -> {NEWER}\n")
        self.assertPasses()

    def test_one_of_several_successors_is_enough(self):
        """20260731-194124-afa338c really does have three successors, one per
        bench, per sim/README.md's "supersession is scoped per-bench" rule."""
        self.records = {
            "cp-compliance": {OLD: None, NEW: OLD, NEWER: OLD, SOLO: OLD}
        }
        self.setUp()
        self.tree.write("README.md", f"{OLD}, switching-skew half at {NEWER}\n")
        self.assertPasses()


class TestExistenceRule(_TreeTest):
    def test_a_citation_of_a_record_that_does_not_exist_is_caught(self):
        ghost = "20261231-235959-fffffff"
        self.tree.write("README.md", f"see `sim/period-jitter/records/{ghost}.md`\n")
        self.assertFails(f"cites record `{ghost}`, which is not on the tree")

    def test_a_dangling_successor_cannot_satisfy_the_forward_rule(self):
        """Both rules fire together: you cannot silence the forward-pointer
        rule by citing a successor id that does not exist."""
        ghost = "20261231-235959-fffffff"
        self.tree.write("README.md", f"{OLD}, superseded by {ghost}\n")
        result = self.assertFails(f"cites record `{ghost}`")
        self.assertIn(f"cites the superseded record `{OLD}`", result.stderr)


class TestSupersedesFieldParsing(_TreeTest):
    """Only the first token after the colon is a record id.

    The first draft of the audit that found this drift mined the whole
    Supersedes line for record ids and reported two false positives on exactly
    these two spellings, both of which are real and in the tree today.
    """

    def test_none_with_a_record_id_in_the_prose_creates_no_edge(self):
        self.records = {
            "lock-time": {
                OLD: None,
                NEW: f"(none -- new record; `{OLD}.md` and its grid stand)",
            },
            **EDGE,
        }
        self.setUp()
        self.tree.write("README.md", f"cited: {OLD}\n")
        self.assertPasses()

    def test_nothing_with_a_record_id_in_the_prose_creates_no_edge(self):
        self.records = {
            "supply-sensitivity": {
                OLD: None,
                NEW: f"nothing. `{OLD}` is re-read in full and reconciled",
            },
            **EDGE,
        }
        self.setUp()
        self.tree.write("README.md", f"cited: {OLD}\n")
        self.assertPasses()

    def test_the_qualifier_after_the_id_does_not_hide_the_edge(self):
        self.records = {
            "output-range": {
                OLD: None,
                NEW: f"{OLD} -- the `ff`/27 C/3.30 V `hi` row ONLY",
            }
        }
        self.setUp()
        self.tree.write("README.md", f"cited: {OLD}\n")
        self.assertFails(f"cites the superseded record `{OLD}`")


class TestSelfDefence(_TreeTest):
    def test_a_tree_with_no_supersession_edges_fails(self):
        """A parser that silently stops matching must not read as a clean
        tree -- this repository's convention is in active use."""
        self.records = {"period-jitter": {OLD: None, NEW: "(none)"}}
        self.setUp()
        self.assertFails("no record on the tree declares a `Supersedes` predecessor")

    def test_a_missing_graded_document_fails(self):
        (Path(self.tree.root) / "docs" / "chipalooza" / "challenge-5-proposal.md").unlink()
        self.assertFails("docs/chipalooza/challenge-5-proposal.md does not exist")

    def test_an_empty_record_tree_fails(self):
        self.records = {}
        self.setUp()
        self.assertFails("found no sim/*/records/*.md files")


class TestTheRealTree(unittest.TestCase):
    def test_the_committed_tree_passes(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("every cited record exists", result.stdout)


if __name__ == "__main__":
    unittest.main()
