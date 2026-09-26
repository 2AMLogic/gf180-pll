"""Shared test bootstrap for ``layout/tests/*.py``.

Every test module in this directory previously repeated the same three
snippets: resolving ``LAYOUT_DIR``, inserting it (and, where needed,
``LAYOUT_DIR / "pll_top"``) onto ``sys.path``, and computing an
``_HAVE_KLAYOUT`` flag via a ``try/except ImportError`` around
``import klayout.db``. This module centralizes that boilerplate.

Not ``test_``-prefixed, so ``unittest discover`` does not try to collect it
as a test module itself.

Usage, at the top of a test file (after ``from __future__ import
annotations`` and stdlib imports, before any ``pll_top``/module-local
imports)::

    from _env import LAYOUT_DIR, HAVE_KLAYOUT

Importing this module has the side effect of inserting ``LAYOUT_DIR`` and
``LAYOUT_DIR / "pll_top"`` at the front of ``sys.path`` (mirroring the two
``sys.path.insert(0, ...)`` calls every prior test file made directly),
which is required before any bare ``from pfd_cp import ...`` /
``from vco import ...`` / ``from pll_top... import ...`` style import.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]

for _path in (LAYOUT_DIR, LAYOUT_DIR / "pll_top"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

# Computed once via importlib.util.find_spec rather than an actual import.
# find_spec("klayout.db") imports the parent "klayout" package as a side
# effect of resolving the dotted name, so a missing "klayout" package raises
# ModuleNotFoundError here rather than returning None -- caught below to
# preserve the exact skip-vs-fail semantics of the try/except ImportError
# block this replaces.
try:
    HAVE_KLAYOUT: bool = importlib.util.find_spec("klayout.db") is not None
except ImportError:
    HAVE_KLAYOUT = False
