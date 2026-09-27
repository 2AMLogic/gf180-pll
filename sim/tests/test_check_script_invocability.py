#!/usr/bin/env python3
"""The grading scripts must be runnable the way their own headers say (issue #237).

    python3 -m unittest discover -s sim/tests -v

Every check in this repository's grading family opens with a ``# Usage:`` line
naming itself bare -- ``# Usage: sim/lib/check-readme-status.sh`` -- and that
line is a claim like any other here: it promises a reader can type the path and
get a verdict. ``sim/lib/check-record-trim-connectivity.sh`` was committed at
mode ``100644`` in the single commit that created it (``1f8a574e``, PR #562),
so for anyone who believed its own header it exited **126** instead, while all
fourteen of its siblings exited 0.

Nothing could see it. ``.github/workflows/ci.yml`` invokes all fifteen as
``bash <path>``, and each script's unit tests spawn ``["bash", str(CHECK)]``
too -- both forms read the file and never ask the kernel to execute it, so the
mode bit is not on any path CI exercises. The defect surfaced only when an
agent working issue #237 typed the documented form, lost time to the 126, and
wrote a note into #237's thread warning the *next* pass not to misread it as a
failing gate. A warning comment is not a fix: it costs every future reader the
same diagnosis, and it does nothing for the next script committed at 644.

So this grades the mode itself, and it grades it **in the git index** rather
than on disk. On-disk is the wrong oracle: a contributor whose umask or
filesystem hands out the execute bit sees a working script locally while the
committed mode -- the one a fresh clone and CI receive -- is still 644. The
index is what ships.

Three properties, one per test:

1. The family is discovered from the index, and discovering *nothing* is a
   failure rather than a pass. A guard over an empty set reports the same
   clean result as a guard over a healthy one, which is the failure mode this
   repository names explicitly where it grades a zero (the proposal's section
   5.1, on the monotonicity count). If the pathspec ever stops matching, this
   says so instead of going quietly green.
2. Every member is mode ``100755`` in the index and carries a ``#!`` line, the
   two things the kernel needs before ``./path`` can run at all.
3. Every member's ``# Usage:`` line names its own path, so the claim this file
   enforces is the claim each script actually makes.

Installer-managed trees (``.loom/``, ``.claude/``) are excluded: those are
resync-refreshed copies owned upstream, and their modes are not this
repository's to assert.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The pathspec every grading check in this repository matches. Kept as one
#: string so the discovery below and the docstring above cannot disagree.
FAMILY_PATHSPEC = "*/lib/check-*.sh"

#: The family had fifteen members when this guard was written. It is a floor,
#: not an equality: adding a sixteenth check is normal and must not fail here,
#: while the pathspec silently matching fewer is the regression worth catching.
KNOWN_FAMILY_SIZE = 15

#: Present at the start of every member today. Matching the shebang loosely --
#: any ``#!`` -- keeps this test about executability rather than about which
#: interpreter a future check picks.
SHEBANG = "#!"

USAGE_RE = re.compile(r"^#\s*Usage:\s*(\S+)", re.MULTILINE)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _family() -> list[tuple[str, str]]:
    """Return ``(mode, path)`` for each grading check, read out of the index."""
    out = _git("ls-files", "--stage", "--", FAMILY_PATHSPEC)
    found: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]
        # Installer-managed copies are owned upstream, not here.
        if path.startswith("."):
            continue
        found.append((mode, path))
    return sorted(found, key=lambda pair: pair[1])


class CheckScriptInvocabilityTest(unittest.TestCase):
    """The ``# Usage:`` line of every grading check must actually work."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            _git("rev-parse", "--show-toplevel")
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(
                f"not a git checkout, so the committed modes cannot be read: {exc}"
            )
        cls.family = _family()

    def test_the_family_is_discovered_and_is_not_empty(self) -> None:
        """A guard that examined nothing must not report the same as a clean one."""
        self.assertTrue(
            self.family,
            f"pathspec {FAMILY_PATHSPEC!r} matched no grading script; either the "
            f"family moved or this guard stopped covering it -- both are "
            f"regressions, not a pass",
        )
        self.assertGreaterEqual(
            len(self.family),
            KNOWN_FAMILY_SIZE,
            f"the grading family shrank from {KNOWN_FAMILY_SIZE} to "
            f"{len(self.family)} members: "
            f"{[path for _, path in self.family]}",
        )

    def test_every_grading_script_is_committed_executable(self) -> None:
        """Mode 100755 in the index, plus a shebang: what ``./path`` needs."""
        not_executable = [path for mode, path in self.family if mode != "100755"]
        self.assertEqual(
            [],
            not_executable,
            "these grading scripts document bare invocation in their own "
            "'# Usage:' line but are not committed executable, so './<path>' "
            "exits 126 in a fresh clone (CI cannot see it -- ci.yml runs them "
            "all as 'bash <path>'). Fix with: git update-index --chmod=+x "
            f"{' '.join(not_executable)}",
        )

        missing_shebang = []
        for _, path in self.family:
            first_line = (REPO_ROOT / path).read_text(encoding="utf-8").split("\n", 1)[0]
            if not first_line.startswith(SHEBANG):
                missing_shebang.append(path)
        self.assertEqual(
            [],
            missing_shebang,
            "an executable bit without a shebang still cannot be run directly; "
            f"these carry no '{SHEBANG}' line: {missing_shebang}",
        )

        # On-disk is not the oracle this test grades, but a mismatch between the
        # index and the working tree is worth naming rather than leaving for a
        # reader to trip over.
        for _, path in self.family:
            self.assertTrue(
                os.access(REPO_ROOT / path, os.X_OK),
                f"{path} is committed executable but is not executable on disk; "
                f"run 'chmod +x {path}'",
            )

    def test_every_usage_line_names_its_own_path(self) -> None:
        """The claim enforced above is the claim each script actually makes."""
        wrong: list[str] = []
        for _, path in self.family:
            text = (REPO_ROOT / path).read_text(encoding="utf-8")
            match = USAGE_RE.search(text)
            if match is None:
                wrong.append(f"{path}: no '# Usage:' line")
            elif match.group(1) != path:
                wrong.append(f"{path}: '# Usage: {match.group(1)}' names another path")
        self.assertEqual(
            [],
            wrong,
            "a '# Usage:' line that does not name its own script is not a "
            f"runnable instruction: {wrong}",
        )


if __name__ == "__main__":
    unittest.main()
