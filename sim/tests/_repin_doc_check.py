#!/usr/bin/env python3
"""Shared check for the re-pin delta documents: generated, not typed tables.

Not itself a ``test_*.py`` module, so ``unittest discover`` never collects it
directly -- the three re-pin delta suites (``test_repin_deltas_lock_divider``,
``test_repin_deltas_vco_output_cp_pfd``, ``test_repin_deltas_closed_loop``)
import it instead of each carrying its own copy of the fenced-command regex,
the comparator invocation and the output check (#1107).

What the check asserts: every fenced ``record_delta.py`` command a document
prints is executed, and every non-blank line of its output must appear in
the document **section that follows that command** -- the span from the end
of the command to the start of the next one, or the end of the document.
The documents repeat their table headers, so searching the whole document
let a line deleted from one section be supplied by another section's
identical table; scoping to the section is what makes "the document shows
this command's output" true per command rather than per document (#1107).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent

#: A fenced regeneration command, as the documents write it:
#:     python3 sim/lib/record_delta.py \
#:       sim/<slug>/records/<old>.md \
#:       sim/<slug>/records/<new>.md
REGEN = re.compile(
    r"python3 sim/lib/record_delta\.py \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md) \\\n"
    r"\s+(sim/[\w.-]+/records/[\d-]+-\w+\.md)\n"
)


def sections(text: str) -> list[tuple[re.Match, str]]:
    """(command, its section) for every fenced command, in document order.

    A command's section runs from the end of the command to the start of
    the next one, or to the end of the document for the last.
    """
    matches = list(REGEN.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m, text[m.end():end]))
    return out


def command_section_failures(
        text: str, *, check_headings: bool = True
) -> list[tuple[str, list[str]]]:
    """Run every command ``text`` documents; report per-section drift.

    Returns one ``(new_record_rel, missing_lines)`` entry per command whose
    own section does not reproduce its generated output, or whose records
    or command are missing. An empty list means every documented table is
    its command's output, in the section that follows the command.
    """
    failures: list[tuple[str, list[str]]] = []
    for m, section in sections(text):
        old_rel, new_rel = m.group(1), m.group(2)
        absent = [rel for rel in (old_rel, new_rel)
                  if not (REPO_ROOT / rel).is_file()]
        if absent:
            failures.append((new_rel, [f"record file missing: {rel}"
                                       for rel in absent]))
            continue
        r = subprocess.run(
            [sys.executable, "sim/lib/record_delta.py", old_rel, new_rel],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if r.returncode != 0:
            failures.append((new_rel, [f"command failed: {r.stderr.strip()}"]))
            continue
        # Every non-blank line of the generated table must appear in its own
        # section verbatim, as a whole line. Comparing line by line rather
        # than as one block keeps the failure message readable.
        missing = [
            ln for ln in r.stdout.splitlines()
            if ln.strip()
            and (check_headings or not ln.startswith("#"))
            and ln not in section.splitlines()
        ]
        if missing:
            failures.append((new_rel, missing))
    return failures


class RepinGeneratedTablesMixin:
    """The shared "tables are generated, not typed" test for a re-pin delta
    document. A suite combines it with ``unittest.TestCase``, sets ``DOC`` --
    and, where the document replaces the generator's own ``###`` headings
    with section headings of its own, sets ``CHECK_GENERATOR_HEADINGS =
    False`` -- and keeps its document-existence and campaign-specific tests
    beside it.

    Deliberately not a ``unittest.TestCase`` subclass: a TestCase base
    imported into a test module is collected in its own right (with no
    ``DOC`` to read), while this plain mixin is invisible to the loader.

    This is the check that stops a hand-edited table: the document is not
    merely *accompanied* by a command, each of its sections *is* its
    command's output.
    """

    #: The document under test; a subclass must set it.
    DOC: Path

    #: Whether the generator's own ``###`` heading lines are compared.
    CHECK_GENERATOR_HEADINGS = True

    def _doc_text(self) -> str:
        return self.DOC.read_text(encoding="utf-8")

    def test_every_documented_regeneration_command_reproduces_its_table(self):
        failures = command_section_failures(
            self._doc_text(), check_headings=self.CHECK_GENERATOR_HEADINGS)
        for new_rel, missing in failures:
            with self.subTest(pair=new_rel):
                self.assertEqual(
                    missing[:3], [],
                    f"{new_rel}: the document does not show this generated "
                    f"output in the section that follows its command -- "
                    f"regenerate it ({len(missing)} line(s) differ)",
                )
