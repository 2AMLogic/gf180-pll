#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-ref-drive-claims.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades a class of claim no other check in this repository could see:
a document that hands the reader a shell command as its own proof.
``docs/chipalooza/challenge-5-proposal.md``'s Reference input row and
``spec/decision-records/DR-019``'s Context both rested on ``grep -n '^vref '
sim/*/testbench/*.sp`` returning one waveform shape in every deck.  It did --
because the one deck in this repository that varies the reference waveform is
``.spice``, and landed in the same commit (#518) that wrote both sentences.  The
command could not return the counterexample, so it read as a confirmation.

Every test builds a throwaway tree whose answer is known -- a handful of
miniature decks, one miniature document -- installs the real script in it, and
runs it.  No ngspice, no PDK, no simulation input: the decks are three lines
each and only their ``vref`` line is ever read.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-ref-drive-claims.sh"

PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
DR019 = (
    "spec/decision-records/"
    "DR-019-reference-input-contract-owner-and-source-quality-exclusion.md"
)
README = "README.md"
CHARACTERIZATION = "sim/CHARACTERIZATION.md"

#: The ideal shape every record in this repository was measured against.
IDEAL = "vref ref 0 pulse(0 'vsup' 'tstart' 200p 200p '0.5*tref' 'tref')"

#: `sim/reference-input-contract`'s real source line: parameterised levels,
#: parameterised edges, parameterised width.
VARYING = "vref ref 0 pulse('vlo' 'vhi' 'tmid-0.5*trf' 'trf' 'trf' 'pw' period)"

#: The claim, unscoped -- what both documents said before this check existed.
UNSCOPED_CLAIM = (
    "Every testbench in this repository that drives `REF` drives it "
    "identically."
)

#: The same claim, scoped to the decks that produced evidence.
SCOPED_CLAIM = (
    "Every testbench in this repository that has produced a record drives "
    "`REF` identically."
)


def _deck(source_line: str) -> str:
    return "* a miniature deck\n.param tref=40n\n%s\n.end\n" % source_line


class _Tree:
    """A throwaway repo tree with the real check installed."""

    def __init__(self, root: Path):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)
        # Every graded document must exist, or the check fails on the absence
        # rather than on what the test is about.
        for rel in (README, CHARACTERIZATION, PROPOSAL, DR019):
            self.write(rel, "# placeholder\n")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def deck(self, rel: str, source_line: str = IDEAL) -> None:
        self.write(rel, _deck(source_line))

    def record(self, campaign: str, name: str = "20260925-000000-abcdef0") -> None:
        self.write("sim/%s/records/%s.md" % (campaign, name), "# a record\n")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)
        # A baseline every test starts from: two ordinary ideal-shape decks,
        # one of each extension, so nothing here passes merely because the
        # tree holds a single file type.
        self.tree.deck("sim/lock-time/testbench/tb_lock_time.sp")
        self.tree.deck("sim/pfd-deadzone/testbench/tb_pfd_deadzone.spice")

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


class TestDeckEnumeration(_TreeTest):
    """Rule 1: a parser that reads nothing must not look like a clean tree."""

    def test_a_tree_of_ideal_decks_and_no_claims_passes(self):
        result = self.assertPasses()
        self.assertIn("2 REF-driving decks", result.stdout)

    def test_no_decks_at_all_fails(self):
        for rel in (
            "sim/lock-time/testbench/tb_lock_time.sp",
            "sim/pfd-deadzone/testbench/tb_pfd_deadzone.spice",
        ):
            (self.tree.root / rel).unlink()
        self.assertFails("enumeration is broken")

    def test_netlist_snapshots_are_not_decks(self):
        """A run's generated copy is not a deck anyone maintains."""
        self.tree.deck("sim/lock-time/netlist-snapshots/20260925-x.spice", VARYING)
        result = self.assertPasses()
        self.assertIn("2 REF-driving decks", result.stdout)

    def test_a_width_trim_is_still_the_ideal_shape(self):
        """`tb_lock_time.sp` really does trim pw by one edge time."""
        self.tree.deck(
            "sim/output-range/testbench/tb_output_range.sp",
            "vref ref 0 pulse(0 'vsup' 20n 200p 200p '0.5/fref-200p' '1/fref')",
        )
        result = self.assertPasses()
        self.assertIn("3 ideal, 0 deviating", result.stdout)

    def test_a_renamed_rail_is_still_the_ideal_shape(self):
        """`tb_supply_dyn.sp` drives REF to `v_lo`, its own nominal rail."""
        self.tree.deck(
            "sim/supply-sensitivity/testbench/tb_supply_dyn.sp",
            "vref ref 0 pulse(0 'v_lo' 'tstart' 200p 200p '0.5*tref' 'tref')",
        )
        result = self.assertPasses()
        self.assertIn("3 ideal, 0 deviating", result.stdout)


class TestGlobCompleteness(_TreeTest):
    """Rule 2: the real defect -- a `*.sp` glob over a `.spice` counterexample."""

    def test_the_sp_only_glob_that_hid_the_counterexample(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp` returns one shape.\n"
            "The deviating deck is under `sim/reference-input-contract`.\n"
            % UNSCOPED_CLAIM,
        )
        self.assertFails(
            "that glob's extension excludes 2 file(s) its own pattern matches",
            "sim/reference-input-contract/testbench/tb_ref_contract.spice",
            "<-- DEVIATES",
        )

    def test_naming_both_extensions_passes(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp sim/*/testbench/*.spice` "
            "returns 3 decks, 2 of them that shape; the third is "
            "`sim/reference-input-contract`'s.\n" % SCOPED_CLAIM,
        )
        self.assertPasses()

    def test_a_grep_about_something_else_is_not_graded(self):
        """Only commands whose own pattern finds a REF source are in scope."""
        self.tree.write(
            PROPOSAL,
            "Loop filter sizing: `grep -n '^cfilt ' sim/*/testbench/*.sp`.\n",
        )
        self.assertPasses()

    def test_a_directory_the_glob_does_not_name_is_out_of_scope(self):
        """Only the extension is relaxed -- guessing a directory is not."""
        self.tree.deck(
            "sim/pfd-deadzone/testbench-operating-point/tb_op.spice", IDEAL
        )
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp sim/*/testbench/*.spice` "
            "says so.\n" % SCOPED_CLAIM,
        )
        self.assertPasses()


class TestDeviationIsNamed(_TreeTest):
    """Rule 3: a claim of uniformity has to name its exceptions."""

    def test_an_unnamed_deviating_deck_fails(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.tree.write(PROPOSAL, "%s\n" % SCOPED_CLAIM)
        self.assertFails(
            "never names `sim/reference-input-contract/testbench/"
            "tb_ref_contract.spice`",
            "A claim of uniformity has to name its exceptions",
        )

    def test_naming_the_campaign_directory_is_enough(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.tree.write(
            PROPOSAL,
            "%s The exception is `sim/reference-input-contract`.\n" % SCOPED_CLAIM,
        )
        self.assertPasses()

    def test_a_document_making_no_claim_need_name_nothing(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.assertPasses()


class TestUnqualifiedClaim(_TreeTest):
    """Rule 4: an unscoped claim is held to every deck its command can reach."""

    def setUp(self) -> None:
        super().setUp()
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )

    def test_an_unscoped_claim_over_a_two_shape_tree_fails(self):
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp sim/*/testbench/*.spice` "
            "returns one shape. The deck is `sim/reference-input-contract`'s.\n"
            % UNSCOPED_CLAIM,
        )
        self.assertFails(
            "asserts, without scoping it",
            "reaches decks of more than one shape",
            "DEVIATION",
        )

    def test_scoping_the_claim_to_records_passes(self):
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp sim/*/testbench/*.spice` "
            "returns 3 decks, 2 of them that shape; the third is "
            "`sim/reference-input-contract`'s and carries no record.\n"
            % SCOPED_CLAIM,
        )
        self.assertPasses()

    def test_narrowing_the_glob_does_not_rescue_an_unscoped_claim(self):
        """The union is graded, so re-narrowing the glob is not a way out."""
        self.tree.write(
            PROPOSAL,
            "%s `grep -n '^vref ' sim/*/testbench/*.sp` returns one shape. "
            "The deck is `sim/reference-input-contract`'s.\n" % UNSCOPED_CLAIM,
        )
        self.assertFails("reaches decks of more than one shape")

    def test_the_claim_is_graded_in_every_document_that_makes_it(self):
        """DR-019 is where the claim originates; the proposal transcribes it."""
        self.tree.write(
            DR019,
            "%s `grep -n '^vref ' sim/*/testbench/*.spice` says so. See "
            "`sim/reference-input-contract`.\n" % UNSCOPED_CLAIM,
        )
        self.assertFails("DR-019", "reaches decks of more than one shape")


class TestDeviatingDeckHasNoRecord(_TreeTest):
    """Rule 5: the substance, which needs no wording at all."""

    def test_a_deviating_deck_with_a_record_fails_whatever_any_document_says(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.tree.record("reference-input-contract")
        self.assertFails(
            "varies the reference waveform",
            "committed record(s)",
            "has to be argued rather than assumed",
        )

    def test_the_same_deck_without_a_record_passes(self):
        self.tree.deck(
            "sim/reference-input-contract/testbench/tb_ref_contract.spice", VARYING
        )
        self.assertPasses()

    def test_a_record_against_an_ideal_deck_is_fine(self):
        self.tree.record("lock-time")
        self.assertPasses()


# A behavioural REF driver: `refa`/`refb` are private nodes, and `ref` is
# synthesised from them. Neither line is `v<name> ref 0 pulse(`, which is why
# the original enumerator could not see the one deck in this repository whose
# whole purpose is to drive REF differently (#509).
SYNTHESISED = (
    "vrefa refa 0 pulse(0 'vdd_val' 'tstart' 200p 200p '0.5*tref' 'tref')\n"
    "vrefb refb 0 pulse(0 'vdd_val' 'tstart+dstep' 200p 200p '0.5*tref' 'tref')\n"
    "bref  ref  0 v='v(refa)*(1-v(gate)/vdd_val) + v(refb)*(v(gate)/vdd_val)'"
)


class TestSynthesisedReference(_TreeTest):
    """Rule 1, widened: a reference that is not a `pulse()` at all (#509)."""

    #: Deliberately NOT `reference-phase-transfer`: the real check's REARGUED
    #: table excuses that campaign, and these tests are about whether the
    #: enumerator can SEE such a deck at all.
    CAMPAIGN = "ref-phase-probe"

    def test_a_behaviourally_driven_ref_is_seen_and_classified_a_deviation(self):
        self.tree.deck(
            "sim/%s/testbench/tb_ref_phase.sp" % self.CAMPAIGN, SYNTHESISED
        )
        self.tree.record(self.CAMPAIGN)
        self.assertFails("synthesised by source bref", "committed record(s)")

    def test_it_must_be_named_by_a_document_asserting_uniformity(self):
        self.tree.deck(
            "sim/%s/testbench/tb_ref_phase.sp" % self.CAMPAIGN, SYNTHESISED
        )
        self.tree.write(
            PROPOSAL,
            "every testbench in this repository that drives `REF` drives it the "
            "same way, as the records show\n",
        )
        self.assertFails("never names", self.CAMPAIGN)

    def test_a_private_pulse_train_alone_is_not_a_ref_driver(self):
        """`vrefa refa 0 pulse(...)` drives a private node, not `ref`."""
        self.tree.deck(
            "sim/somewhere/testbench/tb_private.sp",
            "vrefa refa 0 pulse(0 'v' 'ts' 1n 1n '20n' '40n')",
        )
        self.tree.record("somewhere")
        self.assertPasses()


class TestReargument(_TreeTest):
    """Rule 5's one way through: a named, readable, on-topic decision record."""

    DR = "spec/decision-records/DR-999-reargued.md"

    def _install(self, campaign="deviating-campaign"):
        """A deviating deck plus a record, with the check pointed at self.DR."""
        self.tree.deck(
            "sim/%s/testbench/tb_dev.spice" % campaign, VARYING
        )
        self.tree.record(campaign)
        check = self.tree.root / "sim" / "lib" / CHECK.name
        text = check.read_text(encoding="utf-8")
        marker = 'REARGUED = {'
        assert marker in text
        text = text.replace(
            marker,
            'REARGUED = {\n    "%s": "%s",' % (campaign, self.DR),
            1,
        )
        check.write_text(text, encoding="utf-8")

    def test_a_named_record_that_argues_the_premise_lets_the_record_stand(self):
        self._install()
        self.tree.write(
            self.DR,
            "# DR-999\n\ndeviating-campaign measures the transfer.\n" + "x" * 2000,
        )
        result = self.assertPasses()
        self.assertIn("re-argued in", result.stdout)

    def test_a_missing_record_is_not_a_reargument(self):
        self._install()
        self.assertFails("does not exist", "cannot read is not a re-argument")

    def test_a_stub_is_not_an_argument(self):
        self._install()
        self.tree.write(self.DR, "# DR-999\n\ndeviating-campaign\n")
        self.assertFails("below the", "A stub is not an argument")

    def test_a_record_that_never_mentions_the_campaign_does_not_excuse_it(self):
        self._install()
        self.tree.write(self.DR, "# DR-999\n\nabout something else entirely\n" + "x" * 2000)
        self.assertFails("and never", "mentions", "about the campaign it")

    def test_an_unlisted_campaign_still_fails_and_is_told_what_to_do(self):
        self.tree.deck("sim/other-campaign/testbench/tb_dev.spice", VARYING)
        self.tree.record("other-campaign")
        self.assertFails(
            "REARGUED table", "do not make this check pass any other way"
        )


class TestRealTree(unittest.TestCase):
    """The check must pass on this repository as committed."""

    def test_the_repository_passes(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
