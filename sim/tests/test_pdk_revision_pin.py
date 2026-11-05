"""``find_pdk`` refuses a PDK tree whose open_pdks revision is not the pin.

No real PDK is needed: each case builds a fake variant tree whose ``SOURCES``
carries a chosen revision and points the resolver at it.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import pdk as pdk_mod  # noqa: E402
from harness.pdk import PdkNotFound, PdkRevisionMismatch, find_pdk, pinned_open_pdks  # noqa: E402

OLD = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"


def make_tree(root: Path, revision: str | None, variant: str = "gf180mcuD") -> Path:
    tree = root / variant
    (tree / "libs.tech" / "ngspice").mkdir(parents=True)
    (tree / "libs.tech" / "ngspice" / "sm141064.ngspice").write_text("* fake\n")
    if revision is not None:
        (tree / "SOURCES").write_text(f"open_pdks {revision}\n")
    return tree


class TestPdkRevisionPin(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.pin = pinned_open_pdks()
        # Isolate from the host: no overrides, no local config, and the only
        # search roots are the ones a test supplies.
        env = {k: v for k, v in os.environ.items()
               if k not in ("GF180_PDK_PATH", "GF180_PDK_ROOT", "PDK_ROOT", "PDK")}
        patches = [
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(pdk_mod, "BUILTIN_SEARCH_ROOTS", ()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _search(self, *roots: Path):
        cfg = {"variant": "gf180mcuD", "search_roots": [str(r) for r in roots]}
        with mock.patch.object(pdk_mod, "_load_config", return_value=cfg):
            return find_pdk()

    def test_pin_is_committed_and_is_a_full_hash(self):
        self.assertRegex(self.pin or "", r"^[0-9a-f]{40}$")
        self.assertNotEqual(self.pin, OLD)

    def test_matching_tree_is_returned(self):
        make_tree(self.root / "ciel", self.pin)
        self.assertEqual(self._search(self.root / "ciel").version, self.pin)

    def test_stale_tree_alone_reports_mismatch(self):
        make_tree(self.root / "volare", OLD)
        with self.assertRaises(PdkRevisionMismatch) as cm:
            self._search(self.root / "volare")
        msg = str(cm.exception)
        self.assertIn(OLD, msg)
        self.assertIn(self.pin, msg)
        self.assertIsInstance(cm.exception, PdkNotFound)

    def test_stale_tree_is_skipped_for_a_matching_one_later(self):
        make_tree(self.root / "volare", OLD)
        make_tree(self.root / "ciel", self.pin)
        found = self._search(self.root / "volare", self.root / "ciel")
        self.assertEqual(found.path, self.root / "ciel" / "gf180mcuD")

    def test_builtin_order_prefers_ciel_over_volare(self):
        # setUp patches BUILTIN_SEARCH_ROOTS out, so read the declaration.
        src = Path(pdk_mod.__file__).read_text()
        self.assertLess(src.index('"~/.ciel"'), src.index('"~/.volare"'))

    def test_missing_or_odd_sources_is_a_mismatch(self):
        tree = make_tree(self.root / "a", None)
        with self.assertRaises(PdkRevisionMismatch) as cm:
            self._search(self.root / "a")
        self.assertIn("unknown", str(cm.exception))
        (tree / "SOURCES").write_text("some free-form line\n")
        with self.assertRaises(PdkRevisionMismatch):
            self._search(self.root / "a")

    def test_explicit_path_override_at_wrong_revision_hard_fails(self):
        tree = make_tree(self.root / "x", OLD)
        with mock.patch.dict(os.environ, {"GF180_PDK_PATH": str(tree)}):
            with self.assertRaises(PdkRevisionMismatch):
                find_pdk()

    def test_legacy_root_override_at_wrong_revision_hard_fails(self):
        tree = make_tree(self.root / "x", OLD)
        with mock.patch.dict(os.environ, {"GF180_PDK_ROOT": str(tree)}):
            with self.assertRaises(PdkRevisionMismatch):
                find_pdk()

    def test_pdk_root_override_at_wrong_revision_hard_fails(self):
        make_tree(self.root / "x", OLD)
        with mock.patch.dict(os.environ, {"PDK_ROOT": str(self.root / "x")}):
            with self.assertRaises(PdkRevisionMismatch):
                find_pdk()

    def test_explicit_override_at_pinned_revision_is_accepted(self):
        tree = make_tree(self.root / "x", self.pin)
        with mock.patch.dict(os.environ, {"GF180_PDK_PATH": str(tree)}):
            self.assertEqual(find_pdk().source, "GF180_PDK_PATH")

    def test_local_config_cannot_move_the_pin(self):
        make_tree(self.root / "volare", OLD)
        cfg = {"variant": "gf180mcuD", "open_pdks": OLD,
               "search_roots": [str(self.root / "volare")]}
        with mock.patch.object(pdk_mod, "_load_config", return_value=cfg):
            with self.assertRaises(PdkRevisionMismatch):
                find_pdk()

    def test_nothing_installed_is_plain_not_found(self):
        with self.assertRaises(PdkNotFound) as cm:
            self._search(self.root / "empty")
        self.assertNotIsInstance(cm.exception, PdkRevisionMismatch)
        self.assertIn("ciel", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
