#!/usr/bin/env python3
"""Tests for the host-path guard and capture-time normalisation (issue #701).

    python3 -m unittest discover -s layout/tests -t layout/tests -v

Two halves:

* ``layout/lib/check-evidence-host-paths.sh`` is run for real inside a
  throwaway git repository (script copied into the same relative position, as
  the other ``check-*.sh`` tests do): a PR branch is cut from ``main`` and the
  script grades what the branch added or modified.
* ``harness.env.normalise_run_dir`` is exercised on a synthetic run directory
  shaped like a KLayout deck's output. No PDK, no KLayout.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _env import LAYOUT_DIR  # noqa: E402  (also puts LAYOUT_DIR on sys.path)

from harness import env  # noqa: E402

CHECK = LAYOUT_DIR / "lib" / "check-evidence-host-paths.sh"

HOST_LOG = (
    "Starting running GF180MCU Klayout DRC runset on "
    "/home/ubuntu/GitHub/gf180-pll/.loom/worktrees/issue-1/layout/x.gds\n"
)


class _Repo:
    def __init__(self, root: Path):
        self.root = root
        (root / "layout" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "layout" / "lib" / CHECK.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.write("README.md", "x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def branch(self) -> None:
        self.git("checkout", "-q", "-b", "pr")

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "layout" / "lib" / CHECK.name), "--base", "main", *args],
            capture_output=True,
            text=True,
            cwd=self.root,
        )


class TestEvidenceHostPathCheck(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = _Repo(Path(self._tmp.name))

    def assertPasses(self, *args: str) -> subprocess.CompletedProcess:
        r = self.repo.run(*args)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        return r

    def assertFails(self, needle: str) -> None:
        r = self.repo.run()
        self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)
        self.assertIn(needle, r.stderr)

    def test_added_layout_evidence_with_home_path_fails(self):
        self.repo.branch()
        self.repo.write("layout/evidence/blk/drc-clean/drc.stdout.log", HOST_LOG)
        self.repo.commit()
        self.assertFails("layout/evidence/blk/drc-clean/drc.stdout.log")

    def test_normalised_output_passes(self):
        self.repo.branch()
        self.repo.write(
            "layout/evidence/blk/drc-clean/drc.stdout.log",
            "runset on <REPO>/layout/x.gds\noutput at <RUN_DIR>/x.lyrdb\n",
        )
        self.repo.commit()
        self.assertPasses()

    def test_users_path_fails(self):
        self.repo.branch()
        self.repo.write("layout/evidence/a.txt", "/Users/someone/x\n")
        self.repo.commit()
        self.assertFails("layout/evidence/a.txt")

    def test_agent_worktree_path_fails(self):
        self.repo.branch()
        self.repo.write("layout/evidence/a.txt", "foo .loom/worktrees/issue-9/y\n")
        self.repo.commit()
        self.assertFails("layout/evidence/a.txt")

    def test_grandfathered_file_on_main_is_ignored(self):
        # The legacy file is committed on main itself (still checked out), then the PR branch is cut.
        self.repo.write("layout/evidence/old/drc.stdout.log", HOST_LOG)
        self.repo.commit()
        self.repo.branch()
        self.repo.write("layout/evidence/new/ok.txt", "clean\n")
        self.repo.commit()
        self.assertPasses()

    def test_modifying_a_grandfathered_file_is_graded(self):
        self.repo.write("layout/evidence/old/drc.stdout.log", "clean\n")
        self.repo.commit()
        self.repo.branch()
        self.repo.write("layout/evidence/old/drc.stdout.log", HOST_LOG)
        self.repo.commit()
        self.assertFails("layout/evidence/old/drc.stdout.log")

    def test_sim_record_dir_is_graded_but_other_sim_paths_are_not(self):
        self.repo.branch()
        self.repo.write("sim/lib/note.sh", "# /home/ubuntu/x\n")
        self.repo.write("layout/notes.md", "/home/ubuntu/x\n")
        self.repo.commit()
        self.assertPasses()
        self.repo.write("sim/camp/records/r.md", "ran at /home/ubuntu/x\n")
        self.repo.commit()
        self.assertFails("sim/camp/records/r.md")

    def test_pinned_ngspice_citation_is_allowlisted(self):
        self.repo.branch()
        self.repo.write(
            "sim/supply-sensitivity/records/r.md",
            "binary: `/home/ubuntu/.local/bin/ngspice` (ngspice-46)\n"
            "also `/Users/dev/.local/bin/ngspice`,\n",
        )
        self.repo.commit()
        self.assertPasses()

    def test_allowlist_does_not_excuse_other_paths_in_the_same_file(self):
        self.repo.branch()
        self.repo.write(
            "sim/supply-sensitivity/records/r.md",
            "binary: `/home/ubuntu/.local/bin/ngspice`\nrun in /home/ubuntu/work\n",
        )
        self.repo.commit()
        self.assertFails("sim/supply-sensitivity/records/r.md")

    def test_unknown_base_fails_loudly(self):
        r = subprocess.run(
            ["bash", str(self.repo.root / "layout" / "lib" / CHECK.name), "--base", "nope"],
            capture_output=True, text=True, cwd=self.repo.root,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("merge base", r.stderr)


class TestNormalisation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name).resolve() / "run"
        self.run_dir.mkdir()
        self.pdk = Path.home() / ".volare" / "gf180mcuD"

    def _subs(self):
        return env.path_substitutions(self.run_dir, self.pdk)

    def test_tokens_replace_run_dir_repo_pdk_and_home(self):
        text = (
            f"out at {self.run_dir}/cp_main.lyrdb\n"
            f"runset on {env.REPO_ROOT}/layout/x.gds\n"
            f"warn {self.pdk}/libs.tech/klayout/drc/run_drc.py:698\n"
            f"cfg {Path.home()}/.cache/x\n"
        )
        out = env.normalise_paths(text, self._subs())
        self.assertIn("<RUN_DIR>/cp_main.lyrdb", out)
        self.assertIn("<REPO>/layout/x.gds", out)
        self.assertIn("<PDK>/libs.tech/klayout/drc/run_drc.py:698", out)
        self.assertIn("<HOME>/.cache/x", out)
        self.assertNotIn(str(Path.home()), out)

    def test_normalise_run_dir_rewrites_text_artifacts_and_discloses(self):
        (self.run_dir / "drc.stdout.log").write_text(f"Klayout DRC run is clean {self.run_dir}\n")
        (self.run_dir / "cp_main.lyrdb").write_text(
            f"<generator>drc: script='{self.run_dir}/main.drc'</generator>\n"
        )
        (self.run_dir / "cp.gds").write_bytes(str(self.run_dir).encode())
        n = env.normalise_run_dir(self.run_dir, self._subs())
        self.assertEqual(n, 2)
        self.assertEqual(
            (self.run_dir / "cp_main.lyrdb").read_text(),
            "<generator>drc: script='<RUN_DIR>/main.drc'</generator>\n",
        )
        self.assertIn("Klayout DRC run is clean <RUN_DIR>", (self.run_dir / "drc.stdout.log").read_text())
        # Binary layouts are never rewritten.
        self.assertEqual((self.run_dir / "cp.gds").read_bytes(), str(self.run_dir).encode())
        note = (self.run_dir / env.NORMALISATION_NOTE).read_text()
        self.assertIn("<RUN_DIR>", note)
        self.assertIn("cp_main.lyrdb", note)
        self.assertIn("drc.stdout.log", note)


if __name__ == "__main__":
    unittest.main()
