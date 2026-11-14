"""Repo-relative file reading shared by the claim-checker scripts.

Every check resolves its inputs against ``$REPO_ROOT`` and has to say the same
thing when one of them is missing: a check that cannot read the document it
grades did not pass, it did not run. Four scripts had carried their own
byte-identical copy of that rule; the body lives here once.
"""

import os
import sys


def read_text(repo_root, rel):
    """The text of ``repo_root/rel``, or ``None`` after reporting its absence.

    ``repo_root`` is an explicit argument rather than module state: the copies
    this replaces each closed over their own script's ``repo_root``, and a
    shared helper that reached for one global would be reading whichever
    script imported it last.

    The failure line is written to stderr as ``FAIL: <rel> does not exist`` --
    the repo-relative path, not the absolute one, because the reader of a CI
    log is looking for a path they can check out, and an absolute path names
    the runner's scratch directory instead.
    """
    path = os.path.join(repo_root, rel)
    if not os.path.isfile(path):
        sys.stderr.write("FAIL: %s does not exist\n" % rel)
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()
