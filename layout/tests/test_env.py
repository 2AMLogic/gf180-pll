#!/usr/bin/env python3
"""Unit tests for ``layout/harness/env.py``'s KLayout version-pin advisory.

No PDK and no KLayout application binary required -- ``klayout_version_
mismatch_warning()`` is a pure string comparison over a caller-supplied
version string (see that function's docstring in ``harness/env.py``).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from _env import LAYOUT_DIR  # noqa: F401

from harness import drc, env  # noqa: E402


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


def _tools(pdk_root: Path, files: list) -> "env.PvTools":
    for rel in files:
        target = pdk_root / "libs.tech" / "klayout" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    pdk = SimpleNamespace(
        path=pdk_root, variant="gf180mcuD", klayout_dir=pdk_root / "libs.tech" / "klayout"
    )
    return env.PvTools(pdk=pdk, klayout=Path("/opt/klayout"), python=Path("/usr/bin/python3"))


class DeckLayoutTests(unittest.TestCase):
    """Deck directories are chosen from the files present, not a revision."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_pinned_tech_layout_runs_deck_directly(self):
        tools = _tools(self.root, ["tech/drc/gf180mcu.drc", "tech/lvs/run_lvs.py"])
        k = self.root / "libs.tech" / "klayout"
        self.assertEqual(tools.drc_dir, k / "tech" / "drc")
        self.assertEqual(tools.lvs_dir, k / "tech" / "lvs")
        self.assertIsNone(tools.drc_runner)
        self.assertEqual(tools.drc_entry, k / "tech" / "drc" / "gf180mcu.drc")
        self.assertEqual(tools.lvs_runner, k / "tech" / "lvs" / "run_lvs.py")

    def test_deck_command_shape(self):
        tools = _tools(self.root, ["tech/drc/gf180mcu.drc", "tech/lvs/run_lvs.py"])
        cmd = drc.deck_command(tools, Path("/x/a.gds"), "top", Path("/r/top.lyrdb"), "deep", False)
        self.assertEqual(cmd[:4], ["/opt/klayout", "-b", "-r", str(tools.drc_deck)])
        pairs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-rd"]
        self.assertIn("input=/x/a.gds", pairs)
        self.assertIn("topcell=top", pairs)
        self.assertIn("report=/r/top.lyrdb", pairs)
        self.assertIn("variant=D", pairs)
        self.assertIn("run_mode=deep", pairs)
        self.assertIn("decks=all,-density,-offgrid", pairs)
        full = drc.deck_command(tools, Path("/x/a.gds"), "top", Path("/r/top.lyrdb"), "deep", True)
        self.assertIn("decks=all,-density", full)

    def test_legacy_layout_uses_run_drc(self):
        tools = _tools(self.root, ["drc/run_drc.py", "lvs/run_lvs.py"])
        k = self.root / "libs.tech" / "klayout"
        self.assertEqual(tools.drc_dir, k / "drc")
        self.assertEqual(tools.drc_runner, k / "drc" / "run_drc.py")
        self.assertEqual(tools.drc_entry, k / "drc" / "run_drc.py")
        self.assertEqual(tools.lvs_runner, k / "lvs" / "run_lvs.py")

    def test_both_layouts_prefer_tech(self):
        tools = _tools(
            self.root,
            ["tech/drc/gf180mcu.drc", "drc/run_drc.py", "tech/lvs/run_lvs.py", "lvs/run_lvs.py"],
        )
        k = self.root / "libs.tech" / "klayout"
        self.assertEqual(tools.drc_dir, k / "tech" / "drc")
        self.assertEqual(tools.lvs_dir, k / "tech" / "lvs")

    def test_neither_layout_fails_with_missing_file_error(self):
        tools = _tools(self.root, [])
        self.assertEqual(tools.drc_dir, self.root / "libs.tech/klayout/tech/drc")
        self.assertFalse(tools.drc_entry.is_file())
        orig = (env.find_pdk, env.find_klayout, env.find_pv_python)
        self.addCleanup(lambda: setattr(env, "find_pdk", orig[0]))
        self.addCleanup(lambda: setattr(env, "find_klayout", orig[1]))
        self.addCleanup(lambda: setattr(env, "find_pv_python", orig[2]))
        env.find_pdk = lambda variant=None: tools.pdk
        env.find_klayout = lambda: tools.klayout
        env.find_pv_python = lambda: tools.python
        with self.assertRaisesRegex(env.ToolNotFound, "expected PDK file is missing"):
            env.find_tools()


if __name__ == "__main__":
    unittest.main()
