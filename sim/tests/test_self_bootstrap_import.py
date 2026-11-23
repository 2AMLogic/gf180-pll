#!/usr/bin/env python3
"""Self-bootstrapping importers of ``harness.numeric`` must import cold and alone (#985).

The extractors and derive modules consolidated onto ``sim/harness/numeric.py``
in #985 are loaded by path -- their directories are not packages -- so each
carries its own guarded ``sys.path`` insert putting ``sim/`` on the path
before ``from harness.numeric import ...``. The bootstrap is one
``parents[N]`` off-by-one away from inserting a directory that contains no
``harness`` package at all, and exactly that landed in the first cut of PR
#1014: ``rb_extract.py`` anchored ``parents[1]`` at the *file* (resolving to
``sim/period-jitter``) while its two siblings anchored ``parents[1]`` at a
*directory* (resolving to ``sim/``).

Nothing downstream could see it. Every test in ``sim/tests/`` that loads one
of these modules puts ``sim/`` on ``sys.path`` first (``test_random_bound.py``
inserts ``SIM_DIR`` before ``load_module``), so a module whose own bootstrap
is wrong looks identical to one whose bootstrap is right -- 203 scoped tests
and a green CI run all passed over the broken commit. The one consumer that
exercises the bootstrap on its own is the documented entry point
(``sim/period-jitter/random-bound/summarize.py``), which imports
``rb_extract`` with nothing but its own directory on the path -- the same
"grade the committed artifact, not the convenient in-test path" principle as
``test_check_script_invocability.py`` (#237).

So each pinned module is imported in a **subprocess**, cwd'd to its own
directory, with ``PYTHONPATH`` stripped from the environment: the closest
in-test equivalent of a fresh clone running the module the way its own
consumers do. The pin list is exact -- discovery below fails if a module
joins or leaves the class without the pin following it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Every module outside ``sim/harness/`` and ``sim/tests/`` that imports
#: ``harness.numeric`` and therefore self-bootstraps ``sim/`` onto
#: ``sys.path``. Sorted so the discovery comparison is stable.
SELF_BOOTSTRAPPED = sorted(
    [
        "sim/period-jitter/in-band-bound/ib_extract.py",
        "sim/period-jitter/isf-bringup/isf_extract.py",
        "sim/period-jitter/random-bound/rb_extract.py",
        "sim/period-jitter/testbench/derive.py",
        "sim/reference-spur/testbench/derive.py",
        "sim/vco-tuning-range/testbench-tightband1/_numeric.py",
        "sim/vco-tuning-range/testbench/_numeric.py",
    ]
)


def _importers_of_harness_numeric() -> set[str]:
    """Modules in the git index that import ``harness.numeric``.

    Graded in the index rather than on disk for the same reason
    ``test_check_script_invocability.py`` grades modes there: the index is
    what a fresh clone and CI receive.
    """
    proc = subprocess.run(
        ["git", "grep", "-le", "from harness.numeric import", "--", "sim/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # git grep exits 1 on no matches; an empty class is handled as a failure
    # by the caller, not here.
    if proc.returncode not in (0, 1):
        raise AssertionError(
            f"git grep failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return {
        line
        for line in proc.stdout.splitlines()
        if not line.startswith(("sim/harness/", "sim/tests/"))
    }


class SelfBootstrapImport(unittest.TestCase):
    def test_discovered_importers_match_the_pin(self):
        """The pin and the class must agree, in both directions.

        A new self-bootstrapping importer discovered here but absent from the
        pin is unpinned -- the exact silent gap that let the ``rb_extract``
        off-by-one through. A pinned path that no longer imports
        ``harness.numeric`` is a stale entry that pins nothing.
        """
        discovered = _importers_of_harness_numeric()
        self.assertTrue(
            discovered,
            "discovery found no importers of harness.numeric outside "
            "sim/harness/ -- the pathspec or the import must have changed",
        )
        self.assertEqual(
            sorted(discovered),
            SELF_BOOTSTRAPPED,
            "the set of self-bootstrapping importers of harness.numeric no "
            "longer matches SELF_BOOTSTRAPPED; update the pin with the class",
        )

    def test_each_module_imports_alone_in_its_own_directory(self):
        """Each pinned module imports with only its own directory on the path.

        The subprocess strips ``PYTHONPATH`` and cwd's to the module's own
        directory, so the only way ``from harness.numeric import ...`` can
        succeed is the module's own bootstrap -- the shape of the documented
        consumer invocations (``summarize.py`` et al.).
        """
        for rel in SELF_BOOTSTRAPPED:
            with self.subTest(module=rel):
                path = REPO_ROOT / rel
                self.assertTrue(
                    path.is_file(),
                    f"pinned module {rel} does not exist -- stale pin entry",
                )
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if k != "PYTHONPATH"
                }
                proc = subprocess.run(
                    [sys.executable, "-c", f"import {path.stem}"],
                    cwd=str(path.parent),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    "standalone import failed (a self-bootstrap that does "
                    f"not put sim/ on sys.path?):\n{proc.stderr.strip()}",
                )


if __name__ == "__main__":
    unittest.main()
