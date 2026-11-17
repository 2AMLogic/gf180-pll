#!/usr/bin/env python3
"""Command-construction tests for ``layout/harness/lvs.py``'s ``run()``.

No PDK, no KLayout, no subprocess: these exercise only the runner command
``lvs.run()`` builds, by stubbing the toolchain and capturing the command
through ``env.run_pv_command`` (the single seam every real invocation goes
through). What is graded here:

* ``--combine`` is passed by default (DR-043: the f6eeac7 runset defaults
  ``SIMPLIFY`` off, so the fold-merge has to be asked for) and is **absent**
  when ``combine=False`` (the runset's own default invocation);
* the poly-resistor shim stays in front of the PDK runner by default and is
  bypassed for ``poly_res=None`` (DR-009's option reaches the deck through
  the shim, not through a flag the runner does not have).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from _env import LAYOUT_DIR  # noqa: F401  (sys.path side effect)

from harness import env as env_mod  # noqa: E402
from harness import lvs  # noqa: E402


class _StubPdk:
    path = Path("/nonexistent/pdk/gf180mcuD")
    variant = "gf180mcuD"
    version = "stub"


class _StubTools:
    """The PvTools surface ``lvs.run()`` touches before the subprocess."""

    def __init__(self, tmp: Path) -> None:
        self.pdk = _StubPdk()
        self.python = Path("/nonexistent/pvpython")
        self.klayout = Path("/nonexistent/klayout")
        self.tmp = tmp

    @property
    def lvs_runner(self) -> Path:
        return self.pdk.path / "libs.tech" / "klayout" / "tech" / "lvs" / "run_lvs.py"

    @property
    def lvs_dir(self) -> Path:
        return self.lvs_runner.parent

    @property
    def variant_letter(self) -> str:
        return "D"

    def subprocess_env(self) -> dict:
        return {}


def _run_capture(tmp: Path, **kwargs) -> list[str]:
    """Call ``lvs.run()`` against a stub toolchain; return the command built.

    ``env.run_pv_command`` is replaced so nothing executes; the fake log it
    returns carries the deck's match marker so ``run()`` completes its normal
    post-processing (path normalisation included) against real files.
    """
    tools = _StubTools(tmp)
    layout = tmp / "block.gds"
    layout.write_bytes(b"")
    netlist = tmp / "block.spice"
    netlist.write_text("* stub\n")
    captured: dict = {}

    def fake_run_pv_command(command, *, cwd, timeout, env, log_path):
        captured["command"] = list(command)
        log = f"... {lvs.MATCH_MARKER} ...\n"
        log_path.write_text(log)

        class _Completed:
            returncode = 0

        return _Completed(), log

    with unittest.mock.patch.object(env_mod, "run_pv_command", fake_run_pv_command):
        result = lvs.run(
            layout,
            netlist,
            "block",
            tmp / "run",
            tools=tools,  # type: ignore[arg-type]
            **kwargs,
        )
    assert result.status == "match", result.summary()
    return captured["command"]


class LvsCommandConstructionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_combine_is_passed_by_default(self):
        """DR-043: the harness asks the f6eeac7 runset for the fold-merge."""
        command = _run_capture(self.dir)
        self.assertIn("--combine", command)

    def test_combine_absent_when_disabled(self):
        """``combine=False`` must run the deck exactly as the runset defaults it."""
        command = _run_capture(self.dir, combine=False)
        self.assertFalse(
            [arg for arg in command if arg.startswith("--combine")],
            f"--combine leaked into {command}",
        )

    def test_poly_res_shim_wraps_the_pdk_runner_by_default(self):
        command = _run_capture(self.dir)
        self.assertEqual(command[0], str(_StubTools(self.dir).python))
        self.assertEqual(command[1], str(lvs._POLY_RES_SHIM))
        self.assertEqual(command[2], str(_StubTools(self.dir).lvs_runner))
        self.assertEqual(command[3], lvs.POLY_RES)
        self.assertIn("--lvs_sub=VSS", command)

    def test_poly_res_none_runs_the_pdk_runner_directly(self):
        command = _run_capture(self.dir, poly_res=None)
        self.assertEqual(command[1], str(_StubTools(self.dir).lvs_runner))
        self.assertNotIn(str(lvs._POLY_RES_SHIM), command)


if __name__ == "__main__":
    unittest.main()
