#!/usr/bin/env python3
"""Shared test fixtures for ``docs/tests/``.

Not itself a ``test_*.py`` module, so ``unittest discover`` never collects it
directly. The generic helper is defined once in ``lib/testtree.py`` and
re-exported here so the test files' ``from _fixtures import ...`` lines stay
put; each ``_Tree`` keeps its own ``__init__``/``run`` (#871).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from testtree import TreeWriter  # noqa: E402

__all__ = ["TreeWriter"]
