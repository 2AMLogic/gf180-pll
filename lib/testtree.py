"""Test-side helpers shared by every ``<dir>/tests/_fixtures.py``.

Kept beside ``checklib/`` rather than inside it so ``install_checklib``'s copy
of that package does not carry test helpers into every throwaway tree.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_CHECKLIB = Path(__file__).resolve().parent / "checklib"


def install_checklib(root: Path) -> None:
    """Install the shared checker helpers into a throwaway repo tree.

    The check scripts import ``checklib`` from ``$REPO_ROOT/lib``, and inside
    a throwaway tree that tree IS ``$REPO_ROOT`` for the run -- so the real
    repository's package has to be laid down next to the script, exactly as a
    fresh clone would receive it.
    """
    shutil.copytree(
        _CHECKLIB, root / "lib" / "checklib", ignore=shutil.ignore_patterns("__pycache__")
    )


class TreeWriter:
    """``write(rel, text)`` for a throwaway repo tree rooted at ``self.root``.

    Mixed into the per-file ``_Tree`` helpers that build a miniature repository
    and run a real check script in it. Only this generic relative-path writer
    is shared: each ``_Tree`` keeps its own ``__init__``, ``run`` and
    conveniences layered on top of ``write``.
    """

    #: Set by the concrete ``_Tree.__init__``.
    root: Path

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class TreeTestCase(unittest.TestCase):
    """Gives every test its own freshly-built ``self.tree``.

    A subclass names its module-level ``_Tree`` in ``tree_cls``; ``setUp``
    builds one under a per-test ``tempfile.TemporaryDirectory`` whose cleanup
    is registered for teardown. A subclass needing a baseline tree (decks,
    records, documents) overrides ``setUp``, calls ``super().setUp()`` first,
    then populates ``self.tree``.
    """

    #: The ``_Tree`` class ``self.tree`` is instantiated from.
    tree_cls: type

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = self.tree_cls(Path(self._tmp.name))
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
