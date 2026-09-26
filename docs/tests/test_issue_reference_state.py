#!/usr/bin/env python3
"""Unit tests for ``docs/lib/check-issue-reference-state.sh`` (issue #237).

    python3 -m unittest discover -s docs/tests -v

The check grades the claims the outward-facing documents make *about the
forge* -- "Tracked at issue #13", "issue #499 (open)", "routed to their owning
issues (#9, #10, #11)".  Every other check in this repository grades a document
against something committed in the tree, so none of them could see those claims
go stale, and they did: #13 and #17 both closed on 2026-09-08 and were still
named as live owners seventeen days later, #9/#10/#11 were all closed while the
proposal told its reader they owned three FAILing criteria, and ``Epic #542``
never resolved in this repository at all.

Every test builds a throwaway tree whose answer is known, installs the real
script in it, and puts a stub ``gh`` first on ``PATH`` so the forge's answers
are part of the fixture.  No network, no token, no PDK: the stub is what makes
this suite hermetic, and running the real script against it is what makes it a
test of the check rather than of a reimplementation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DOCS_DIR.parent
CHECK = DOCS_DIR / "lib" / "check-issue-reference-state.sh"

PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
README = "README.md"
SIM_README = "sim/README.md"
CHARACTERIZATION = "sim/CHARACTERIZATION.md"
SIGNOFF_README = "signoff/README.md"

#: The forge fixture every test starts from: which numbers exist, and how.
STATES = {
    9: "closed",
    13: "closed",
    17: "closed",
    18: "open",
    149: "open",
    297: "open",
    499: "open",
    503: "open",
    505: "closed",
    520: "open",
}

#: A `gh` that answers `gh api repos/OWNER/NAME/issues/N --jq .state` from a
#: table baked into the script, and 404s for anything not in it -- the shape
#: `gh api` really produces for a number this repository does not have.
GH_STUB = """#!/usr/bin/env bash
if [ "${1:-}" != "api" ]; then
  echo "stub gh: unexpected subcommand ${1:-}" >&2
  exit 1
fi
number="${2##*/}"
case "$number" in
%s
  *)
    echo '{"message":"Not Found","status":"404"}' >&2
    echo "gh: Not Found (HTTP 404)" >&2
    exit 1 ;;
esac
"""

#: A `gh` that cannot answer at all -- the rate-limited / unauthenticated
#: shape, which must SKIP rather than report every reference as missing.
GH_STUB_UNREACHABLE = """#!/usr/bin/env bash
echo "GraphQL: API rate limit already exceeded for installation ID 1" >&2
exit 1
"""


def _gh_stub(states=None) -> str:
    states = STATES if states is None else states
    arms = "\n".join(
        '  %d) echo "%s" ;;' % (number, state) for number, state in sorted(states.items())
    )
    return GH_STUB % arms


def _proposal(section5_rows=None, section6="", section7="") -> str:
    rows = section5_rows if section5_rows is not None else (
        ("Period jitter, random", "UNMET", "issue #520 (open)"),
    )
    lines = [
        "# Chipalooza Challenge #5 — integer-N PLL proposal",
        "",
        "## 2. I/O list, including test ports",
        "",
        "Mapped onto the Challenge #5 budget.",
        "",
        "## 5. Target specification",
        "",
        "| Parameter | Verdict | Source (dated) |",
        "|---|---|---|",
    ]
    for parameter, verdict, source in rows:
        lines.append("| %s | %s | %s |" % (parameter, verdict, source))
    lines += ["", "## 6. Layout status", "", section6 or "Nothing to report."]
    lines += ["", "## 7. Open items", "", section7 or "Nothing open."]
    return "\n".join(lines) + "\n"


def _readme(body="Status: early.") -> str:
    return "# gf180-pll\n\n%s\n" % body


class _Tree:
    """A throwaway repo tree with the real check and a stub forge installed."""

    def __init__(self, root: Path):
        self.root = root
        (root / "docs" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "docs" / "lib" / CHECK.name)
        self.bin = root / "stub-bin"
        self.bin.mkdir()
        self.set_forge(_gh_stub())
        self.write(PROPOSAL, _proposal())
        self.write(README, _readme())
        self.write(SIM_README, "# sim\n\nCampaigns.\n")
        self.write(CHARACTERIZATION, "# Characterization\n\nCoverage.\n")
        self.write(SIGNOFF_README, "# Signoff\n\nVerdict of record.\n")

    def set_forge(self, script: str) -> None:
        stub = self.bin / "gh"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = "%s%s%s" % (self.bin, os.pathsep, env.get("PATH", ""))
        env["GH_REPO"] = "2AMLogic/gf180-pll"
        return subprocess.run(
            ["bash", str(self.root / "docs" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
            env=env,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def assertPasses(self) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertNotIn("SKIP", result.stdout)
        return result

    def assertSkips(self) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("SKIP", result.stdout)
        return result

    def assertFails(self, *needles: str) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        return result


class TestResolvableRule(_TreeTest):
    def test_a_clean_tree_passes(self):
        self.assertPasses()

    def test_a_cross_repository_number_is_caught(self):
        """The real `Epic #542` drift: a 404 for the reader it is written for."""
        self.tree.write(
            PROPOSAL,
            _proposal(section6="Mapped per Epic #542's slot budget."),
        )
        self.assertFails("references #542, which is not an issue")

    def test_challenge_5_is_not_an_issue_reference(self):
        """`Challenge #5` appears on nearly every page and is not issue 5."""
        self.tree.write(
            PROPOSAL,
            _proposal(section6="Submitted to Challenge #5, not to Challenge #3."),
        )
        self.assertPasses()

    def test_a_heading_anchor_is_not_an_issue_reference(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section6="See [Lock time](../../spec/pll.md#lock-time)."),
        )
        self.assertPasses()

    def test_the_readme_is_graded_too(self):
        self.tree.write(README, _readme("Routed to #542 by name."))
        self.assertFails("README.md", "#542")

    def test_the_sim_documents_are_graded_too(self):
        """sim/README.md's campaign table named closed #505 as an owner, and
        nothing graded it: the check read only the proposal and README.md."""
        for rel in (SIM_README, CHARACTERIZATION):
            with self.subTest(rel=rel):
                self.tree.write(rel, "# x\n\nThe random half is tracked at #505.\n")
                self.assertFails("%s:3 hands work to #505" % rel)
                self.tree.write(rel, "# x\n\nThe random half is tracked at #520.\n")
                self.assertPasses()


class TestStateAnnotationRule(_TreeTest):
    def test_open_annotation_on_a_closed_issue_is_caught(self):
        """The real drift: section 5's Source column read `issue #13 (open)`."""
        self.tree.write(
            PROPOSAL,
            _proposal(section5_rows=(("Period jitter", "UNMET", "issue #13 (open)"),)),
        )
        self.assertFails("says #13 is open; the forge says it is closed")

    def test_closed_annotation_on_an_open_issue_is_caught(self):
        self.tree.write(PROPOSAL, _proposal(section6="#297 is closed."))
        self.assertFails("says #297 is closed; the forge says it is open")

    def test_a_correct_annotation_passes(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section6="#13 is closed, and #297 remains open."),
        )
        self.assertPasses()


class TestOwnershipRule(_TreeTest):
    def test_tracked_at_a_closed_issue_is_caught(self):
        """The real drift: `Tracked at issue #13`, seventeen days after it closed."""
        self.tree.write(PROPOSAL, _proposal(section7="Tracked at issue #13."))
        self.assertFails('hands work to #13 with "Tracked at", but #13 is closed')

    def test_routed_to_a_closed_issue_is_caught(self):
        """The real drift: `routed to their owning issues (#9, #10, #11)`."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="They are already routed to their owning issues (#9)."),
        )
        self.assertFails('hands work to #9 with "routed to"')

    def test_tracked_at_an_open_issue_passes(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Tracked at issues #297, #149 and #18."),
        )
        self.assertPasses()

    def test_every_issue_in_one_ownership_clause_is_graded(self):
        """`Tracked at issues #297, #17 and #18` must flag the middle one."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Tracked at issues #297, #17 and #18."),
        )
        self.assertFails("hands work to #17")

    def test_past_tense_narration_is_exempt(self):
        """`was filed as issue #273` is history, and history does not rot."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="It was filed as issue #13 and is now closed."),
        )
        self.assertPasses()

    def test_an_em_dash_aside_ends_the_ownership_clause(self):
        """The document must be able to explain which owner it replaced."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                section7="Tracked at issue #297 — #17, named here before, closed."
            ),
        )
        self.assertPasses()

    def test_a_sentence_boundary_ends_the_ownership_clause(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Tracked at issue #297. Earlier this said #17."),
        )
        self.assertPasses()

    def test_a_compound_modifier_is_not_an_owner(self):
        """`the post-#24 charge pump (#9)` names a design state, not an owner."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Routed to the post-#13 charge pump (#297)."),
        )
        self.assertPasses()

    def test_owed_at_a_closed_issue_is_caught(self):
        """The real drift: sim/README.md said the random half "is owed at **#505**"
        for as long as #505 had been closed, because "owed at" was not a phrase
        the check recognised."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="The random half is owed at **#505**."),
        )
        self.assertFails('hands work to #505 with "owed at", but #505 is closed')

    def test_owed_by_and_owed_from_are_ownership_too(self):
        for phrase in ("owed by", "owed from"):
            with self.subTest(phrase=phrase):
                self.tree.write(
                    PROPOSAL, _proposal(section7="The sweep is %s #13." % phrase)
                )
                self.assertFails('with "%s", but #13 is closed' % phrase)

    def test_owed_at_an_open_issue_passes(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section7="The random half is owed at **#520** (open)."),
        )
        self.assertPasses()

    def test_past_tense_owed_is_exempt(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Until 2026-09-25 it was owed at #505."),
        )
        self.assertPasses()

    def test_owned_at_a_closed_issue_is_caught(self):
        """The real drift: sim/CHARACTERIZATION.md's `owned at **#505**`."""
        self.tree.write(
            CHARACTERIZATION,
            "# x\n\nThe owed item is a methodology, owned at **#505**.\n",
        )
        self.assertFails('hands work to #505 with "owned at"')

    def test_a_closed_issue_the_document_marks_closed_is_not_an_owner(self):
        """`owed from #499 ... (the successor to #505, itself closed)` names
        #505 as history inside #499's ownership clause, and says so."""
        for text in (
            "The sweep is owed from **#499** (the successor to #505, itself closed).",
            "The loop was routed to the now-closed #13 (owner **#297**).",
            "The row is tracked at #297, not closed issue #13.",
        ):
            with self.subTest(text=text):
                self.tree.write(PROPOSAL, _proposal(section7=text))
                self.assertPasses()

    def test_a_hyphenated_adjective_does_not_hide_a_closed_owner(self):
        """Only named sibling repositories qualify a reference; an adjective
        like `differently-shaped` in front of `#13` does not."""
        self.tree.write(
            PROPOSAL,
            _proposal(section7="It is tracked at the differently-shaped #13."),
        )
        self.assertFails('hands work to #13 with "tracked at"')

    def test_an_ownership_clause_does_not_reach_the_next_paragraph(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section7="Tracked at issue #297.\n\nSeparately, #17 landed."),
        )
        self.assertPasses()


class TestSourceColumnRule(_TreeTest):
    def test_an_unannotated_source_issue_is_caught(self):
        """The real drift: the band-top row's Source column read `issue #13`."""
        self.tree.write(
            PROPOSAL,
            _proposal(section5_rows=(("Band top", "UNMET", "issue #13"),)),
        )
        self.assertFails("cites #13 in section 5's Source column with no (open)")

    def test_an_annotated_source_issue_passes(self):
        self.tree.write(
            PROPOSAL,
            _proposal(section5_rows=(("Band top", "UNMET", "issue #503 (open)"),)),
        )
        self.assertPasses()

    def test_provenance_inside_a_source_cell_is_not_a_source_of_record(self):
        """`the wrap-safe gate of #273` cites a record's history, not an owner."""
        self.tree.write(
            PROPOSAL,
            _proposal(
                section5_rows=(
                    ("Jitter", "MET", "`sim/x/records/a.md` (the gate of #13)"),
                )
            ),
        )
        self.assertPasses()

    def test_the_rule_does_not_reach_outside_section_5(self):
        self.tree.write(PROPOSAL, _proposal(section7="See issue #13 for history."))
        self.assertPasses()


class TestForeignRepositoryReferences(_TreeTest):
    def test_a_sibling_repository_reference_is_not_graded_here(self):
        """`klayout-tools #309` is not this repository's #309 -- which here is
        a closed layout issue -- and must not be resolved against it."""
        for text in (
            "The tool is tracked at klayout-tools #309.",
            "Filed upstream as 2AMLogic/klayout-tools #999.",
            "Copied from gf180-bandgap #4242.",
        ):
            with self.subTest(text=text):
                self.tree.write(CHARACTERIZATION, "# x\n\n%s\n" % text)
                self.assertPasses()


class TestForgeFailureModes(_TreeTest):
    def test_an_unreachable_forge_skips_rather_than_failing(self):
        """A rate-limited `gh` must not report every reference as missing."""
        self.tree.set_forge(GH_STUB_UNREACHABLE)
        result = self.assertSkips()
        self.assertIn("A skip is not a pass", result.stdout)

    def test_a_missing_graded_document_fails(self):
        for rel in (README, SIM_README, CHARACTERIZATION, SIGNOFF_README):
            with self.subTest(rel=rel):
                path = self.tree.root / rel
                saved = path.read_text(encoding="utf-8")
                path.unlink()
                self.assertFails("%s does not exist" % rel)
                path.write_text(saved, encoding="utf-8")

    def test_a_pull_request_number_resolves(self):
        """`gh api .../issues/N` answers for pull requests too, and must pass."""
        states = dict(STATES)
        states[418] = "closed"
        self.tree.set_forge(_gh_stub(states))
        self.tree.write(PROPOSAL, _proposal(section6="PR #418 added the pins."))
        self.assertPasses()


class TestScriptHygiene(unittest.TestCase):
    def test_the_check_is_executable_and_shellcheck_clean_enough_to_run(self):
        self.assertTrue(os.access(CHECK, os.X_OK), "%s is not executable" % CHECK)
        result = subprocess.run(
            ["bash", "-n", str(CHECK)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_the_header_states_the_forge_dependency(self):
        """The one check here that is not deterministic on a tree must say so."""
        # The header is the leading comment block, however long it grows --
        # a fixed character window silently dropped its own tail when
        # issue #564 added a paragraph above it.
        lines = CHECK.read_text(encoding="utf-8").splitlines()
        header_lines = []
        for line in lines:
            if not line.startswith("#"):
                break
            header_lines.append(line)
        header = "\n".join(header_lines)
        self.assertIn("THIS IS THE ONE CHECK IN THIS REPOSITORY THAT NEEDS THE FORGE",
                      header)
        self.assertIn("A skip is not a pass", header)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
