#!/usr/bin/env python3
"""A Monte Carlo CSV may not claim it ran without Monte Carlo (issue #601).

    python3 -m unittest discover -s sim/tests -v

Every extracted-metrics CSV under ``sim/*/corners/`` opens with
``sim/lib/simenv.sh``'s ``simenv_provenance`` header, whose stated purpose is
to keep the table self-describing away from its record.  One of its lines names
the statistical switches the run used::

    # switches: design.ngspice defaults (sw_stat_global=0, sw_stat_mismatch=0
    #           -> nominal skew, no Monte Carlo)

Until #601 that line was *hardcoded*, with no parameter and no condition, while
the sibling ``simenv_env_block`` -- which writes the prose Environment
provenance field of the record beside the CSV -- had carried an optional
switches-note override since #15 for exactly the campaigns that turn mismatch
on.  The override therefore landed on the Markdown and not on the machine
readable header, and fourteen committed CSVs from this repository's two Monte
Carlo campaigns shipped asserting "no Monte Carlo" over data that is nothing
but Monte Carlo samples.  Those bytes are append-only evidence and were not
rewritten; each affected campaign's live ``run*.sh`` carries an erratum naming
the files, and this test keeps the *next* campaign from joining them.

What it grades is the pairing, statically, with no PDK and no simulator: a
testbench script whose runs turn ``sw_stat_mismatch`` on -- either by passing
``sw_stat_mismatch=1`` to ngspice itself, quoted or not, or by driving a deck
that declares it after the ``design.ngspice`` include -- must pass a fifth
``switches-note`` argument to *every* ``simenv_provenance`` call it makes, and
that note must say mismatch is on rather than repeat the mismatch-off default.
The default wording is graded too, against ``sim/lib/simenv.sh`` itself: it is
the sentence every honestly-nominal committed CSV carries, so it may not come to
claim Monte Carlo either (#614).

The converse is deliberately NOT graded.  A script that runs at the
``design.ngspice`` defaults passes four arguments and inherits the default
wording, which is correct for it and byte-identical to what it emitted before
#601; requiring an explicit note everywhere would churn every honest campaign
in the tree to fix two dishonest ones.
"""

from __future__ import annotations

import re
import shlex
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]

#: The wording ``simenv_provenance`` falls back to when no note is passed.  A
#: campaign that overrides the switches and then hands back this sentence has
#: defeated the parameter, so the note is matched against it directly.
MISMATCH_OFF_TOKEN = "sw_stat_mismatch=0"
MISMATCH_ON_TOKEN = "sw_stat_mismatch=1"

#: Where a run script may turn mismatch on from the shell: an ngspice
#: key=value override on the command line, as sim/mc-cp-mismatch does.  The
#: token is matched on word boundaries, NOT inside quotes: ``"x=1"`` and a bare
#: ``x=1`` are the same argument once the shell is done with them, so a pattern
#: that insisted on the quotes let an unquoted override -- the same run, written
#: one character differently -- walk past the guard (issue #614).  Nothing in
#: the tree was ever mislabelled by that, since every live call site quotes; the
#: gap was that the *next* campaign need not.  The value side stays literal
#: ``1``: an exotic spelling such as ``=10`` trips it too, which for a guard is
#: the safe direction to err in -- a flagged honest campaign is a loud test
#: failure, an unflagged Monte Carlo campaign is a CSV header that lies.
_CLI_OVERRIDE = re.compile(r"(?<![\w.])sw_stat_mismatch\s*=\s*1")

#: The same switch declared inside a SPICE deck.  ``*`` opens a comment in
#: SPICE, so commented mentions -- of which the decks have many, explaining the
#: include-ordering hazard -- must not count as declarations.
_DECK_DECL = re.compile(r"^\s*\.param\s+sw_stat_mismatch\s*=\s*1\b", re.MULTILINE)

#: A shell assignment of a literal string, used to resolve a note passed as
#: ``"${SWITCHES_NOTE}"`` back to the text it will expand to.
_ASSIGN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)=(".*?"|\'.*?\')\s*$', re.MULTILINE)


def _join_continuations(text: str) -> list[str]:
    """Shell logical lines: physical lines joined across trailing ``\\``."""
    out: list[str] = []
    pending = ""
    for line in text.splitlines():
        if line.endswith("\\"):
            pending += line[:-1]
            continue
        out.append(pending + line)
        pending = ""
    if pending:
        out.append(pending)
    return out


def provenance_calls(script_text: str) -> list[list[str]]:
    """Argument lists of every ``simenv_provenance`` invocation in a script.

    Comment lines are skipped -- run.sh files discuss the function in prose --
    and each surviving call is split with ``shlex`` in non-POSIX mode so that
    quoted arguments holding spaces and ``${...}`` expansions stay one token.
    """
    calls: list[list[str]] = []
    for line in _join_continuations(script_text):
        if line.lstrip().startswith("#"):
            continue
        idx = line.find("simenv_provenance ")
        if idx < 0:
            continue
        try:
            words = shlex.split(line[idx:], posix=False)
        except ValueError:  # unbalanced quoting -- not ours to diagnose
            continue
        if words and words[0] == "simenv_provenance":
            calls.append(words[1:])
    return calls


def resolve_note(arg: str, script_text: str) -> str | None:
    """Expand a switches-note argument to its literal text, if we can.

    Returns the text of a literal argument, the right-hand side of the shell
    assignment a ``"${NAME}"`` argument refers to, or ``None`` when the value
    is computed some other way (in which case its content is not graded -- the
    *presence* of the argument still is).
    """
    inner = arg
    if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in "\"'":
        inner = inner[1:-1]
    var = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", inner)
    if not var:
        return inner
    name = var.group(1) or var.group(2)
    for found, value in _ASSIGN.findall(script_text):
        if found == name:
            return value[1:-1]
    return None


def decks_referenced(script_path: Path, script_text: str) -> list[Path]:
    """SPICE decks named by a script that exist next to it."""
    found = []
    for name in sorted(set(re.findall(r"[\w./-]+\.sp\b", script_text))):
        candidate = (script_path.parent / Path(name).name)
        if candidate.is_file():
            found.append(candidate)
    return found


def shell_code(text: str) -> str:
    """A script's executable lines, with whole-line ``#`` comments dropped.

    The run scripts in this tree carry long comment preambles that *discuss*
    ``sw_stat_mismatch=1`` -- three of them name the unquoted token while
    explaining the include-ordering hazard -- so a word-boundary search over the
    raw text would classify a campaign on the strength of its own prose.  Only
    lines the shell executes can turn a switch on, so only those are searched.
    This can never hide a real override (a commented-out override does not run),
    and it mirrors ``provenance_calls`` below, which skips comments for the same
    reason.
    """
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def runs_with_mismatch_on(script_path: Path) -> bool:
    """Does this script's ngspice run have ``sw_stat_mismatch=1`` in force?"""
    text = script_path.read_text(encoding="utf-8")
    if _CLI_OVERRIDE.search(shell_code(text)):
        return True
    return any(_DECK_DECL.search(d.read_text(encoding="utf-8")) for d in decks_referenced(script_path, text))


def testbench_scripts() -> list[Path]:
    """Every shell script under a ``sim/`` experiment's testbench directory."""
    return sorted(p for p in SIM_DIR.glob("*/testbench*/*.sh") if p.is_file())


class TestDiscovery(unittest.TestCase):
    """A guard over an empty set reports the same clean result as a healthy one."""

    def test_finds_testbench_scripts(self) -> None:
        self.assertGreater(len(testbench_scripts()), 5, "testbench glob matched almost nothing")

    def test_finds_provenance_calls(self) -> None:
        total = sum(len(provenance_calls(p.read_text(encoding="utf-8"))) for p in testbench_scripts())
        self.assertGreater(total, 10, "simenv_provenance call parser matched almost nothing")

    def test_both_classes_are_populated(self) -> None:
        """Mismatch-on and mismatch-off campaigns both exist, so both arms run."""
        scripts = [p for p in testbench_scripts() if provenance_calls(p.read_text(encoding="utf-8"))]
        on = [p for p in scripts if runs_with_mismatch_on(p)]
        off = [p for p in scripts if not runs_with_mismatch_on(p)]
        self.assertTrue(on, "no mismatch-on campaign found -- detection is broken")
        self.assertTrue(off, "no mismatch-off campaign found -- detection is broken")

    def test_known_campaigns_classify_correctly(self) -> None:
        """The three scripts #601 names, plus one control, land where they should."""
        for rel in (
            "mc-cp-mismatch/testbench/run.sh",
            "vco-tuning-range/testbench/run_mismatch.sh",
            "vco-tuning-range/testbench/run_band0_worst_corner.sh",
        ):
            with self.subTest(script=rel):
                self.assertTrue(runs_with_mismatch_on(SIM_DIR / rel))
        # Same experiment directory, same helper library, mismatch genuinely off.
        self.assertFalse(runs_with_mismatch_on(SIM_DIR / "vco-tuning-range/testbench/run.sh"))


class TestCommittedScripts(unittest.TestCase):
    """The property itself, over the tree as committed."""

    def test_mismatch_on_scripts_pass_a_switches_note(self) -> None:
        for script in testbench_scripts():
            text = script.read_text(encoding="utf-8")
            calls = provenance_calls(text)
            if not calls or not runs_with_mismatch_on(script):
                continue
            for args in calls:
                with self.subTest(script=script.relative_to(SIM_DIR), campaign=args[0]):
                    self.assertGreaterEqual(
                        len(args),
                        5,
                        "this run turns sw_stat_mismatch on, so simenv_provenance needs its "
                        "fifth switches-note argument -- without it the CSV header states "
                        "the design.ngspice default 'no Monte Carlo' over Monte Carlo data "
                        "(issue #601)",
                    )
                    note = resolve_note(args[4], text)
                    if note is None:
                        continue
                    self.assertIn(MISMATCH_ON_TOKEN, note)
                    self.assertNotIn(MISMATCH_OFF_TOKEN, note)


class TestProvenanceDefault(unittest.TestCase):
    """The wording a four-argument call inherits must itself be true (#614).

    ``TestCommittedScripts`` grades the *override* against the run.  The
    **default** -- the sentence every four-argument call emits, and the only
    ``# switches:`` line any committed CSV carries today (all 84 that have one,
    as of 2026-09-27) -- was graded by nothing, so editing it in sim/lib/simenv.sh
    to claim Monte Carlo ran would have relabelled every honest nominal table
    minted afterwards without failing a test.
    """

    #: The ``${5:-...}`` default of simenv_provenance's switches argument.
    _DEFAULT = re.compile(r'^\s*local switches="\$\{5:-(?P<note>[^"]*)\}"', re.MULTILINE)

    def test_default_switches_note_states_mismatch_off(self) -> None:
        text = (SIM_DIR / "lib" / "simenv.sh").read_text(encoding="utf-8")
        found = self._DEFAULT.search(text)
        self.assertIsNotNone(
            found,
            "simenv_provenance's switches default was not found in sim/lib/simenv.sh -- "
            "if its shape changed, update this pattern rather than dropping the check",
        )
        note = found.group("note")  # type: ignore[union-attr]
        self.assertIn(
            MISMATCH_OFF_TOKEN,
            note,
            "the default '# switches:' sentence is what a run at the design.ngspice "
            "defaults emits, so it must say the switches are off",
        )
        self.assertNotIn(
            MISMATCH_ON_TOKEN,
            note,
            "the default sentence would then claim Monte Carlo over the nominal runs "
            "that omit the fifth argument -- the inverse of issue #601's defect",
        )


class TestDetection(unittest.TestCase):
    """Synthetic controls: a check that only ever runs where it passes proves nothing."""

    def _script(self, body: str, deck: str | None = None) -> Path:
        tmp = Path(tempfile.mkdtemp())
        if deck is not None:
            (tmp / "tb_x.sp").write_text(deck, encoding="utf-8")
        path = tmp / "run.sh"
        path.write_text(body, encoding="utf-8")
        return path

    def test_cli_override_detected(self) -> None:
        path = self._script('simenv_run_deck "$D" "vsup=3.3" "sw_stat_mismatch=1"\n')
        self.assertTrue(runs_with_mismatch_on(path))

    def test_unquoted_cli_override_detected(self) -> None:
        """The same override without quotes is the same run (issue #614).

        ngspice receives one argument either way; the quotes are the shell's
        business and not the switch's.  A guard that recognised only the quoted
        spelling could be stepped around by a campaign that never quotes.
        """
        path = self._script('simenv_run_deck "$DECK" --define sw_stat_mismatch=1\n')
        self.assertTrue(runs_with_mismatch_on(path))

    def test_unquoted_override_in_a_shell_comment_is_not_a_run(self) -> None:
        """Prose about the switch is not the switch, whatever the quoting.

        The deck-side counterpart of this is
        ``test_commented_deck_mention_is_not_a_declaration``; this is the shell
        side, and it is what keeps the word-boundary match above from reading
        the long ``#``-comment preambles in sim/*/testbench/run*.sh as runs.
        """
        path = self._script(
            "# This campaign does NOT pass sw_stat_mismatch=1; see run_mismatch.sh.\n"
            'simenv_run_deck "$DECK" "vsup=3.3"\n'
        )
        self.assertFalse(runs_with_mismatch_on(path))

    def test_unquoted_off_value_is_not_flagged(self) -> None:
        """Dropping the quotes did not widen *which value* counts as on."""
        path = self._script('simenv_run_deck "$D" sw_stat_mismatch=0\n')
        self.assertFalse(runs_with_mismatch_on(path))

    def test_deck_declaration_detected(self) -> None:
        path = self._script('DECK="${HERE}/tb_x.sp"\n', deck=".param sw_stat_global=0\n.param sw_stat_mismatch=1\n")
        self.assertTrue(runs_with_mismatch_on(path))

    def test_commented_deck_mention_is_not_a_declaration(self) -> None:
        path = self._script('DECK="${HERE}/tb_x.sp"\n', deck="* .param sw_stat_mismatch=1 would turn it on\n")
        self.assertFalse(runs_with_mismatch_on(path))

    def test_mismatch_off_script_is_not_flagged(self) -> None:
        path = self._script('simenv_run_deck "$D" "vsup=3.3"\n')
        self.assertFalse(runs_with_mismatch_on(path))

    def test_call_parser_reads_continuations_and_skips_comments(self) -> None:
        text = (
            '# simenv_provenance is described here and must not be parsed\n'
            '  simenv_provenance "camp (dc)" "${RID}" "design/cp.sch (export)" \\\n'
            '    "3 corners x N=10 samples" "${SWITCHES_NOTE}"\n'
        )
        calls = provenance_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 5)
        self.assertEqual(calls[0][0], '"camp (dc)"')

    def test_note_resolves_through_a_variable(self) -> None:
        text = 'SWITCHES_NOTE="defaults OVERRIDDEN (sw_stat_mismatch=1 -> Monte Carlo)"\n'
        self.assertIn(MISMATCH_ON_TOKEN, resolve_note('"${SWITCHES_NOTE}"', text) or "")
        self.assertIsNone(resolve_note('"${NOT_DEFINED_ANYWHERE}"', text))

    def test_a_four_argument_mismatch_on_call_is_rejected(self) -> None:
        """The exact pre-#601 defect, rebuilt, so the guard is known to catch it."""
        path = self._script(
            'simenv_run_deck "$D" "sw_stat_mismatch=1"\n'
            'simenv_provenance "camp" "${RID}" "net" "3 corners x N=10"\n'
        )
        self.assertTrue(runs_with_mismatch_on(path))
        calls = provenance_calls(path.read_text(encoding="utf-8"))
        self.assertEqual(len(calls), 1)
        self.assertLess(len(calls[0]), 5)


if __name__ == "__main__":
    unittest.main()
