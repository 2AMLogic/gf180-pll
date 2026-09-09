#!/usr/bin/env python3
"""Unit tests for ``layout/harness/env.py``'s KLayout version-pin advisory.

No PDK and no KLayout application binary required -- ``klayout_version_
mismatch_warning()`` is a pure string comparison over a caller-supplied
version string (see that function's docstring in ``harness/env.py``).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))

from harness import env  # noqa: E402


class KlayoutVersionMismatchWarningTests(unittest.TestCase):
    def test_exact_match_is_silent(self):
        self.assertIsNone(
            env.klayout_version_mismatch_warning(env.KNOWN_GOOD_KLAYOUT_VERSION)
        )

    def test_older_or_newer_version_produces_a_warning(self):
        warning = env.klayout_version_mismatch_warning("KLayout 0.30.9")
        self.assertIsNotNone(warning)
        self.assertIn("0.30.9", warning)
        self.assertIn(env.KNOWN_GOOD_KLAYOUT_VERSION, warning)

    def test_unknown_version_string_is_silent_not_a_mismatch(self):
        # This is the literal shape PvTools.klayout_version()'s exception
        # path produces (env.py's own klayout_version() docstring/impl) --
        # an undetermined version must not be treated as evidence of drift.
        self.assertIsNone(
            env.klayout_version_mismatch_warning("unknown (some subprocess error)")
        )

    def test_empty_string_is_silent(self):
        self.assertIsNone(env.klayout_version_mismatch_warning(""))

    def test_helper_never_raises_on_odd_input(self):
        # Not a real KLayout version format at all -- still must not raise,
        # and since it doesn't match the pin, it is reported as a mismatch.
        try:
            warning = env.klayout_version_mismatch_warning("garbage-not-a-version")
        except Exception as exc:  # pragma: no cover - defensive
            self.fail(f"klayout_version_mismatch_warning raised unexpectedly: {exc}")
        self.assertIsNotNone(warning)


if __name__ == "__main__":
    unittest.main()
