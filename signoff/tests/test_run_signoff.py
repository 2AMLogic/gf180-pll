#!/usr/bin/env python3
"""Unit tests for ``signoff/run-signoff.sh``'s klt version pin (issue #630).

    python3 -m unittest discover -s signoff/tests -t signoff/tests -v

``run-signoff.sh`` used to check only that ``klt`` was *present*
(``command -v klt``), never that it was the version
``.github/workflows/ci.yml`` pins.  ``klt signoff`` embeds its own build
identity in the rendered report (``build.version``, ``git_tag``,
``is_release``, ``grading_ruleset_id``), and every one of those fields
differs between the released wheel and a post-tag source build of the same
release number -- so ``--check`` re-rendered, diffed, and reported a current
``signoff/tier-report.json`` as **stale** on any host whose ``klt`` was a
source build.  That is the same ``0.6.0`` vs. ``0.6.0+g<sha>`` trap issue
#127 closed on the ERC-report side, surfacing here as a false failure rather
than a false pass.

The check now reads the pin out of the workflow and requires ``klt
--version`` to print exactly ``klt <pin>``.  A rule that only ever runs where
it passes proves nothing about what it would have caught, so every test below
builds a throwaway tree -- the real script, a miniature workflow, and a stub
``klt`` on ``PATH`` reporting a version of the test's choosing -- and runs the
real script in it.  No PDK, no KLayout, no klt install.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _fixtures import TreeWriter

SIGNOFF_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SIGNOFF_DIR / "run-signoff.sh"

CI_WORKFLOW = ".github/workflows/ci.yml"
MANIFEST = "signoff/block-manifest.json"
REPORT = "signoff/tier-report.json"

#: The klt version the fixture's workflow pins.  Read from that file by the
#: script rather than restated in it -- the same doctrine
#: ``layout/lib/check-layout-status-claims.sh``'s ERC rule follows -- so the
#: fixture has to carry one for the check to have anything to grade against.
PINNED_KLT = "0.6.0"

#: A post-tag source build of that same release: a PEP 440 *local version*.
#: `pip show klayout-tools` prints a bare `0.6.0` with `INSTALLER: pip` for
#: both this and the released wheel, and a source build installed into
#: `~/.local/bin` shadows the wheel on `PATH`, so `klt --version` is the only
#: discriminator -- which is why the check compares the whole string.
SOURCE_BUILD_KLT = f"{PINNED_KLT}+gd574697ed72c"

WORKFLOW_TEMPLATE = """\
name: CI
on: [push]
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - name: Install klt (klayout-tools) for the signoff tier check
        run: pip install 'klayout-tools==%s'
"""

#: What the stub `klt signoff` renders, shaped like the real report's
#: envelope: a verdict body plus the `build` block carrying klt's own build
#: identity.  Only the fields these tests read are present.
def _report(build_version: str = PINNED_KLT, t1_met_count: int = 0) -> dict:
    return {
        "schema_version": 1,
        "block": "pll_ring_integer_n",
        "tier": "T1",
        "t1_met_count": t1_met_count,
        "build": {
            "version": build_version,
            "git_tag": f"v{build_version}",
            "is_release": True,
            "grading_ruleset_id": "sha256:0d8cc27c752ce25fc78499d4c280a4b4",
        },
        "items": [],
    }


class _Tree(TreeWriter):
    """A throwaway repo tree with the real script installed at signoff/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "signoff").mkdir(parents=True)
        shutil.copy2(SCRIPT, root / "signoff" / SCRIPT.name)
        self.bin = root / "stub-bin"
        self.bin.mkdir()
        self.write_workflow(PINNED_KLT)
        self.write(MANIFEST, json.dumps({"block": "pll_ring_integer_n"}) + "\n")
        self.write_report(_report())
        self.stub_klt(PINNED_KLT, _report())

    # --- fixture pieces -----------------------------------------------------

    def write_workflow(self, pin: str | None) -> None:
        if pin is None:
            self.write(CI_WORKFLOW, WORKFLOW_TEMPLATE.split("      - name:")[0])
            return
        self.write(CI_WORKFLOW, WORKFLOW_TEMPLATE % pin)

    def write_report(self, report: dict) -> None:
        """The committed report, as `--check` compares against it."""
        self.write(REPORT, json.dumps(report, indent=2) + "\n")

    def read_report(self) -> str:
        return (self.root / REPORT).read_text(encoding="utf-8")

    def stub_klt(self, version: str, report: dict, exit_code: int = 3) -> None:
        """A `klt` on PATH reporting `version` and rendering `report`.

        `exit_code` is what `klt signoff --manifest` exits with: 3 ("not yet
        T1") is this block's real, expected verdict today, and the script
        treats 0 and 3 alike, so the stub defaults to the honest one.
        """
        rendered = self.root / "stub-klt-report.json"
        rendered.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        klt = self.bin / "klt"
        klt.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1" = "--version" ]; then\n'
            f'  echo "klt {version}"\n'
            "  exit 0\n"
            "fi\n"
            f'cat "{rendered}"\n'
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        klt.chmod(0o755)

    # --- driving the real script -------------------------------------------

    def run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = f"{self.bin}{os.pathsep}{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(self.root / "signoff" / SCRIPT.name), *args],
            capture_output=True,
            text=True,
            env=env,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)


class TestVersionPin(_TreeTest):
    def test_the_pinned_release_is_accepted(self):
        """The negative control: the version the check exists to accept."""
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is current.", result.stderr)

    def test_a_post_tag_source_build_is_rejected(self):
        """The regression this check exists for (issue #630).

        `klt 0.6.0+gd574697ed72c` is a build of the klayout-tools tree after
        the v0.6.0 tag, not the released wheel: `is_release` is false,
        `git_tag` is null, and `grading_ruleset_id` may differ.  Before the
        check, the script ran it anyway and blamed the resulting diff on the
        committed report.
        """
        self.tree.stub_klt(SOURCE_BUILD_KLT, _report(SOURCE_BUILD_KLT))
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(f"klt {SOURCE_BUILD_KLT}", result.stderr)
        self.assertIn(f"klayout-tools=={PINNED_KLT}", result.stderr)
        # The message must name the trap by shape -- a version that *starts*
        # with the pin reads as a typo otherwise ...
        self.assertIn("local version", result.stderr)
        self.assertIn("source build", result.stderr)
        # ... and point at the way out.
        self.assertIn("uvx --from", result.stderr)
        self.assertIn("python3 -m venv", result.stderr)
        # And it must NOT be the misleading verdict this issue is about.
        self.assertNotIn("is stale", result.stderr)

    def test_an_unrelated_off_pin_version_is_rejected(self):
        """The other half: a klt from before the pin, no local suffix."""
        self.tree.stub_klt("0.5.0", _report("0.5.0"))
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("klt 0.5.0", result.stderr)
        self.assertIn(f"klayout-tools=={PINNED_KLT}", result.stderr)
        self.assertNotIn("is stale", result.stderr)

    def test_write_mode_refuses_an_off_pin_klt_too(self):
        """An off-pin klt must not *render* a report CI would then reject.

        The false-`--check`-failure is the noisy half of this gap; the
        dangerous half is a source build writing a report whose build block
        no host running the pinned wheel can reproduce.
        """
        before = self.tree.read_report()
        self.tree.stub_klt(SOURCE_BUILD_KLT, _report(SOURCE_BUILD_KLT))
        result = self.tree.run()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(before, self.tree.read_report())

    def test_a_workflow_with_no_pin_is_caught(self):
        """No pin, nothing to grade against -- and that is a failure.

        Same doctrine as the ERC rule's `test_ci_workflow_with_no_pin_is_caught`:
        a check whose source of truth has gone missing must say so rather than
        quietly grading nothing.
        """
        self.tree.write_workflow(None)
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("klayout-tools==", result.stderr)
        self.assertIn(CI_WORKFLOW, result.stderr)

    def test_a_missing_workflow_is_caught(self):
        (self.tree.root / CI_WORKFLOW).unlink()
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(CI_WORKFLOW, result.stderr)

    def test_the_pin_is_read_from_the_workflow_not_restated(self):
        """Bump the fixture's pin and the accepted version moves with it.

        This is what makes the check correct across a future pin bump with no
        code change -- and it is asserted, not assumed: a hardcoded `0.6.0`
        would pass every other test in this class.
        """
        self.tree.write_workflow("0.7.1")
        self.tree.stub_klt("0.7.1", _report("0.7.1"))
        self.tree.write_report(_report("0.7.1"))
        self.assertEqual(self.tree.run("--check").returncode, 0)

        self.tree.stub_klt(PINNED_KLT, _report())
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("klayout-tools==0.7.1", result.stderr)


class TestStaleReport(_TreeTest):
    """The behaviour the version check must not swallow."""

    def test_a_genuinely_stale_report_is_still_caught(self):
        self.tree.stub_klt(PINNED_KLT, _report(t1_met_count=4))
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("is stale", result.stderr)

    def test_a_tool_only_diff_says_the_tool_moved(self):
        """A stale report whose only difference is klt's own build block.

        The version check catches the common cause of this, but not every
        one: a same-version build can still differ in `git_commit`, `dirty`,
        or `grading_ruleset_id`.  A bare "stale" leaves a reader with no hint
        that the tool, not the evidence, is what moved.
        """
        moved = _report()
        moved["build"]["grading_ruleset_id"] = "sha256:88fdfb1700000000000000000000"
        self.tree.stub_klt(PINNED_KLT, moved)
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("is stale", result.stderr)
        self.assertIn("build", result.stderr)
        self.assertIn("no T1 verdict changed", result.stderr)

    def test_an_evidence_diff_is_not_reported_as_a_tool_move(self):
        """The negative control for the hint above."""
        moved = _report(t1_met_count=4)
        moved["build"]["grading_ruleset_id"] = "sha256:88fdfb1700000000000000000000"
        self.tree.stub_klt(PINNED_KLT, moved)
        result = self.tree.run("--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("no T1 verdict changed", result.stderr)


class TestToolErrors(_TreeTest):
    def test_a_klt_signoff_crash_is_not_written_out_as_a_report(self):
        """Unchanged behaviour, guarded: only 0 and 3 are verdicts."""
        self.tree.stub_klt(PINNED_KLT, {"error": "boom"}, exit_code=1)
        before = self.tree.read_report()
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not a tier verdict", result.stderr)
        self.assertEqual(before, self.tree.read_report())


if __name__ == "__main__":
    unittest.main()
