#!/usr/bin/env python3
"""Unit tests for ``layout/lib/check-layout-status-claims.sh`` (issue #237).

The script exists to make one specific documentation drift a build failure:
README.md and docs/chipalooza/challenge-5-proposal.md both stated that no
PLL block had been drawn for about five weeks after all four sub-blocks
landed with committed GDS and DRC-clean deck output.  A check that only
ever runs against the real tree, where it passes, proves nothing about
whether it would have *caught* that -- so these tests drive it against
synthetic trees where the answer is known, including the exact pre-fix
state of the two real documents.

The script resolves its own repo root from ``${BASH_SOURCE[0]}/../..``, so
each test builds a throwaway tree with the script copied into the same
relative position and runs it there.  No PDK, no KLayout, no layout input.

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = LAYOUT_DIR / "lib" / "check-layout-status-claims.sh"

# The four sub-blocks the script grades, as (evidence dir, block GDS name).
BLOCKS = [
    ("vco-layout", "vco_block.gds"),
    ("pfd-cp-layout", "pfd_cp.gds"),
    ("divider-chain-layout", "divider_chain.gds"),
    ("lock-detector-layout", "lock_detector.gds"),
]

LVS_MATCH_LINE = "INFO : Congratulations! Netlists match.\n"

# The scope rule reads a ~100-character window either side of a negation,
# so a synthetic document needs real distance between the boilerplate
# "no assembled `pll_top` GDS" sentinel (which legitimately carries a scope
# word) and the sentence under test.  Deliberately free of both negations
# and layout nouns.
PAD = "\n" + ("Filler prose that bears on nothing in particular. " * 5) + "\n"

RATIFIED_SPEC = "# PLL target specification\n\n- **Status**: **ratified, with amendments** (#1, 2026-09-08)\n"
UNRATIFIED_SPEC = "# PLL target specification\n\n- **Status**: proposed, not yet ratified\n"


def _doc_text(drawn: int, lvs: int, *, no_top: bool = True) -> str:
    """A minimal document that satisfies the script at the given counts."""
    body = [
        f"Layout status: {drawn} of the 4 PLL sub-blocks are drawn and",
        f"DRC-clean, and {lvs} of the 4 are LVS-matched.",
    ]
    if no_top:
        body.append("There is no assembled `pll_top` GDS.")
    return "\n".join(body) + "\n"


class _Tree:
    """A throwaway repo tree with the script installed at layout/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "layout" / "lib").mkdir(parents=True)
        (root / "docs" / "chipalooza").mkdir(parents=True)
        (root / "spec").mkdir(parents=True)
        shutil.copy2(SCRIPT, root / "layout" / "lib" / SCRIPT.name)
        self.write_spec(RATIFIED_SPEC)

    def write_spec(self, text: str) -> None:
        (self.root / "spec" / "pll.md").write_text(text)

    def add_block(self, evidence_dir: str, gds: str, *, drc: bool, lvs: bool) -> None:
        base = self.root / "layout" / "evidence" / evidence_dir
        base.mkdir(parents=True, exist_ok=True)
        (base / gds).write_bytes(b"")
        if drc:
            (base / "drc-clean").mkdir(exist_ok=True)
            (base / "drc-clean" / "drc.stdout.log").write_text("0 violations\n")
        if lvs:
            (base / "lvs-clean").mkdir(exist_ok=True)
            (base / "lvs-clean" / "lvs.stdout.log").write_text(LVS_MATCH_LINE)

    def add_assembled_top(self) -> None:
        base = self.root / "layout" / "evidence" / "pll-top-layout"
        base.mkdir(parents=True, exist_ok=True)
        (base / "pll_top.gds").write_bytes(b"")

    def write_docs(self, text: str) -> None:
        (self.root / "README.md").write_text(text)
        (self.root / "docs" / "chipalooza" / "challenge-5-proposal.md").write_text(text)

    def run(self, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "layout" / "lib" / SCRIPT.name)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def path_without_python(self) -> dict:
        """An environment whose PATH has every tool the script needs but python3."""
        bindir = self.root / "fakebin"
        bindir.mkdir(exist_ok=True)
        for tool in ("bash", "dirname", "grep", "tr"):
            resolved = shutil.which(tool)
            if resolved is None:  # pragma: no cover - not seen on CI or macOS
                raise unittest.SkipTest(f"{tool} not on PATH")
            target = bindir / tool
            if not target.exists():
                target.symlink_to(resolved)
        return {"PATH": str(bindir)}


class CheckLayoutStatusClaimsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name) / "repo")

    def tearDown(self):
        self._tmp.cleanup()

    def _all_four(self, *, lvs_for=("vco-layout", "divider-chain-layout")):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(
                evidence_dir, gds, drc=True, lvs=evidence_dir in lvs_for
            )

    def test_matching_documents_pass(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("4/4 drawn", result.stdout)

    def test_the_exact_pre_fix_prose_is_caught(self):
        # Verbatim from README.md and the proposal as they stood on main at
        # 2ddf0c54, with all four blocks already committed.  This is the
        # regression the script was written for; if this test ever passes
        # silently, the check has stopped doing its job.
        self._all_four()
        self.tree.write_docs(
            "No PLL block has been drawn yet, and `measurements/` stays empty\n"
            "until there is silicon.\n\n"
            "**No PLL-block layout exists.** `layout/` holds a proven flow.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("No PLL block has been drawn yet", result.stderr)
        self.assertIn("No PLL-block layout exists", result.stderr)

    def test_understated_block_count_is_caught(self):
        self._all_four()
        self.tree.write_docs(_doc_text(3, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("4 of the 4 PLL sub-blocks", result.stderr)

    def test_overstated_lvs_count_is_caught(self):
        # The direction that matters most for a document sent to an outside
        # reader: claiming more verification than the tree records.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 4))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("2 of the 4 are LVS-matched", result.stderr)

    def test_lvs_log_without_the_match_verdict_does_not_count(self):
        # A committed lvs-clean/ directory is not an LVS pass.  Only the
        # deck's own "Netlists match." verdict is.
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=True, lvs=False)
        base = self.tree.root / "layout" / "evidence" / "vco-layout" / "lvs-clean"
        base.mkdir(parents=True)
        (base / "lvs.stdout.log").write_text("ERROR: Netlists don't match.\n")
        self.tree.write_docs(_doc_text(4, 0))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_gds_without_a_drc_log_is_not_a_drawn_block(self):
        for evidence_dir, gds in BLOCKS:
            self.tree.add_block(evidence_dir, gds, drc=False, lvs=False)
        self.tree.write_docs(_doc_text(0, 0))
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_no_assembled_top_sentinel_is_caught(self):
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2, no_top=False))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no assembled `pll_top` GDS", result.stderr)

    def test_stale_no_assembled_top_sentinel_is_caught_once_a_top_lands(self):
        # The next drift due: when pll_top is assembled, every document
        # still carrying the sentinel becomes wrong in the other direction.
        self._all_four()
        self.tree.add_assembled_top()
        self.tree.write_docs(_doc_text(4, 2, no_top=True))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("still says", result.stderr)

    def test_an_empty_evidence_tree_does_not_forbid_the_historical_claims(self):
        # With nothing drawn, "no PLL block has been drawn yet" is true
        # again and must not be flagged -- the forbidden list is conditional
        # on the tree, not absolute.
        self.tree.write_docs(
            _doc_text(0, 0) + "No PLL block has been drawn yet.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The scope rule (issue #237, second pass) -------------------------
    #
    # The tests below are the ones the original hand-written forbidden list
    # could not have passed.  The list named exactly the sentences that had
    # already gone stale; the sentence that was *still* stale in the same
    # document -- section 3's "**No layout exists for this block**" -- was
    # not on it, and the check reported OK on the very commit that shipped
    # the list.

    def test_the_sentence_the_forbidden_list_missed_is_caught(self):
        # Verbatim from docs/chipalooza/challenge-5-proposal.md section 3 as
        # it stood on main at 387d03c6 -- i.e. AFTER the first pass of this
        # check shipped and passed over it.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + PAD
            + "**No layout exists for this block** -- `layout/` currently\n"
            "contains only the DRC/LVS flow's proof-of-flow test cell (a\n"
            "standard-cell inverter, `layout/evidence/inv-tb-proof/PROOF.md`),\n"
            "proven clean on that trivial circuit but never yet run against\n"
            "any PLL sub-block or the top level.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("without saying at what scope", result.stderr)
        self.assertIn("No layout exists for this block", result.stderr)

    def test_an_absence_claim_that_names_its_scope_passes(self):
        # The same grammatical shape, scoped to what is genuinely absent.
        # The rule must not force a document to stop saying true things.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "No GDS exists for the assembled top level, so there is no\n"
            "post-layout extracted netlist to re-verify against.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_freshly_invented_unscoped_phrasing_is_caught(self):
        # The point of the rule: it grades the claim, not a remembered
        # sentence.  None of these wordings appears on any forbidden list.
        self._all_four()
        for phrasing in (
            "Nothing has been drawn for this PLL.",
            "This design has never been drawn as layout.",
            "There is no layout for the PLL at this time.",
            "PLL-block GDS: none drawn.",
        ):
            with self.subTest(phrasing=phrasing):
                self.tree.write_docs(_doc_text(4, 2) + PAD + phrasing + "\n")
                result = self.tree.run()
                self.assertEqual(
                    result.returncode, 1, result.stdout + result.stderr
                )
                self.assertIn("without saying at what scope", result.stderr)

    def test_the_scope_rule_is_silent_when_nothing_is_drawn(self):
        # Conditional on the tree, like the forbidden list: with no drawn
        # block, "no layout exists" is simply true.
        self.tree.write_docs(
            _doc_text(0, 0) + "No layout exists for this block.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_top_level_scope_stops_excusing_claims_once_a_top_lands(self):
        # Two-sided, like the assembled-top sentinel: the day a pll_top GDS
        # is committed, every "no assembled top level" sentence in both
        # documents is due for a re-read, and the rule forces it.
        self._all_four()
        self.tree.add_assembled_top()
        self.tree.write_docs(
            _doc_text(4, 2, no_top=False)
            + "No GDS exists for the assembled top level.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("without saying at what scope", result.stderr)

    def test_a_negation_that_is_not_about_layout_is_not_flagged(self):
        # False positives cost real editorial freedom, so the shapes that
        # nearly match are pinned: "now" is not "no", and a "drawn-band
        # edge" is not a drawn layout.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "All four blocks now have a committed block GDS.\n"
            "The closed-loop campaign reaches PASS on none, at either\n"
            "drawn-band edge.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- The spec ratification guard --------------------------------------

    def test_a_blanket_unratified_claim_is_caught_once_the_spec_ratifies(self):
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is pending engineering ratification through #1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("pending engineering ratification", result.stderr)

    def test_a_row_scoped_carve_out_is_not_a_blanket_unratified_claim(self):
        # DR-007 Amendment A1 carves out two rows.  Saying so is true and
        # must stay sayable -- only the blanket claim is forbidden.
        self._all_four()
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is ratified, with two rows still unratified per\n"
            "DR-007 Amendment A1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_guard_is_silent_while_the_spec_is_still_proposed(self):
        self._all_four()
        self.tree.write_spec(UNRATIFIED_SPEC)
        self.tree.write_docs(
            _doc_text(4, 2)
            + "`spec/pll.md` is pending engineering ratification through #1.\n"
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_missing_python3_fails_rather_than_downgrading_the_check(self):
        # Without python3 the scope rule cannot run at all.  Passing on the
        # remaining literal-phrase checks would be the same silent downgrade
        # that let section 3 through in the first place.
        self._all_four()
        self.tree.write_docs(_doc_text(4, 2))
        env = self.tree.path_without_python()
        result = self.tree.run(env=env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("python3 is not on PATH", result.stderr)

    def test_an_unreadable_spec_status_fails_rather_than_skipping(self):
        # A guard that silently no-ops when its input goes missing is how a
        # check rots.  Say so instead.
        self._all_four()
        self.tree.write_spec("# PLL target specification\n\nNo status line.\n")
        self.tree.write_docs(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not read a '- **Status**:' line", result.stderr)

    def test_a_missing_document_is_a_failure_not_a_silent_pass(self):
        self._all_four()
        (self.tree.root / "README.md").write_text(_doc_text(4, 2))
        result = self.tree.run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
