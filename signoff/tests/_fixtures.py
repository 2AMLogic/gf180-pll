#!/usr/bin/env python3
"""Shared test fixtures for ``signoff/tests/``.

Not itself a ``test_*.py`` module, so ``unittest discover`` never collects it
directly -- it exists purely to be imported by the ``test_*.py`` files that
need ``TreeWriter``.

The same mixin, for the same reason, as ``sim/tests/_fixtures.py``'s: every
test in this directory builds a throwaway miniature repository and runs the
real ``signoff/run-signoff.sh`` inside it, and the generic relative-path
writer that lays that tree out was hand-duplicated once per file (#677)
rather than shared.
"""

from __future__ import annotations

from pathlib import Path


class TreeWriter:
    """``write(rel, text)`` for a throwaway repo tree rooted at ``self.root``.

    Mixed into the per-file ``_Tree`` helpers that build a miniature repository
    and run the real ``signoff/run-signoff.sh`` in it. Only this generic
    relative-path writer is shared: each ``_Tree`` keeps its own ``__init__``
    (which script it installs, which documents and stub executables must
    pre-exist so the check fails on what the test is about rather than on an
    absence), its own ``run`` (which script it invokes, with which arguments)
    and its own workflow/manifest/report conveniences layered on top of
    ``write``.
    """

    #: Set by the concrete ``_Tree.__init__``.
    root: Path

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
