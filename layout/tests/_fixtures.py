"""Shared throwaway-tree helpers for ``layout/tests/*.py``.

The counterpart of ``design/tests/_fixtures.py``, ``sim/tests/_fixtures.py``
and ``spec/tests/_fixtures.py``, and deliberately the same five lines: a test
that builds a miniature repo and runs a real check script in it needs
``install_checklib`` to lay ``lib/checklib`` down beside the script, because
inside that tree the tree IS ``$REPO_ROOT`` for the run.

Separate from ``_env.py`` rather than folded into it: importing ``_env`` puts
``layout/`` and ``layout/pll_top/`` on ``sys.path`` so that the KLayout-driven
geometry tests can do bare ``from vco import ...``, which a test that only
shells out to a check script has no use for.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from testtree import install_checklib  # noqa: E402

__all__ = ["install_checklib"]
