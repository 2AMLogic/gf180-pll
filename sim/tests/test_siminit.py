"""The shared simulator init file (``set wnflag=1``) both backends stage (#755, DR-040).

Covers the contract in :mod:`harness.siminit`: the same bytes reach ngspice's
working directory before the netlist is read on the local and the batch path,
an ambient init file is shadowed rather than edited, parallel jobs do not
collide, a failure leaves nothing behind, and the record only credits a
configuration the simulator's own output proves ran.

Run:  python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from _fixtures import ManifestFixture, fake_pdk  # noqa: E402
from harness import batch, corners, execution, report, runner, siminit, testbench  # noqa: E402

#: Stands in for ngspice: records, *at start*, what init file the working
#: directory holds, then prints what a real run prints from the init file.
FAKE_NGSPICE = """#!/bin/sh
if [ -f .spiceinit ]; then
  echo "seen-at-start: $(cat .spiceinit | tr '\\n' '|')"
  echo "{marker} wnflag=1"
else
  echo "seen-at-start: none"
fi
echo "ngspice-46 done"
"""


def _fake_ngspice(directory: Path) -> Path:
    exe = directory / "ngspice"
    exe.write_text(FAKE_NGSPICE.format(marker=siminit.MARKER))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


class InitOfTests(unittest.TestCase):
    def test_the_marker_from_the_init_file_is_the_only_proof(self):
        out = f"banner\n{siminit.MARKER} wnflag=1\nngspice-46 done\n"
        self.assertEqual(siminit.init_of(out), f"sha256:{siminit.INIT_SHA256}")

    def test_a_banner_or_the_setting_text_alone_is_not_proof(self):
        self.assertEqual(siminit.init_of("ngspice-46 done\n"), "")
        self.assertEqual(siminit.init_of("set wnflag=1\n"), "")
        self.assertEqual(siminit.init_of(""), "")

    def test_a_marker_that_saw_the_flag_unset_is_not_proof(self):
        self.assertEqual(siminit.init_of(f"{siminit.MARKER} wnflag=0\n"), "")
        self.assertEqual(siminit.init_of(f"{siminit.MARKER} wnflag=\n"), "")

    def test_the_init_sets_the_flag_before_it_reports_it(self):
        lines = siminit.INIT_TEXT.splitlines()
        self.assertLess(lines.index("set wnflag=1"), len(lines) - 1)
        self.assertTrue(lines[-1].startswith(f"echo {siminit.MARKER}"))


class StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "dir with spaces"
        self.root.mkdir()

    def test_stage_writes_the_exact_bytes(self):
        path = siminit.stage(self.root)
        self.assertEqual(path, self.root / ".spiceinit")
        self.assertEqual(path.read_text(), siminit.INIT_TEXT)

    def test_a_stale_conflicting_file_is_replaced_and_no_temp_file_remains(self):
        (self.root / ".spiceinit").write_text("set wnflag=0\n")
        siminit.stage(self.root)
        self.assertEqual((self.root / ".spiceinit").read_text(), siminit.INIT_TEXT)
        self.assertEqual([p.name for p in self.root.iterdir()], [".spiceinit"])

    def test_identical_bytes_are_left_alone(self):
        path = siminit.stage(self.root)
        before = path.stat().st_ino
        siminit.stage(self.root)
        self.assertEqual(path.stat().st_ino, before)

    def test_parallel_stagers_sharing_a_directory_never_expose_a_partial_file(self):
        errors: list[BaseException] = []

        def _go() -> None:
            try:
                for _ in range(30):
                    siminit.stage(self.root)
                    self.assertEqual(
                        (self.root / ".spiceinit").read_text(), siminit.INIT_TEXT
                    )
            except BaseException as exc:  # noqa: BLE001 - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=_go) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual([p.name for p in self.root.iterdir()], [".spiceinit"])

    def test_a_failed_stage_leaves_no_temp_file(self):
        with mock.patch.object(siminit.os, "replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                siminit.stage(self.root)
        self.assertEqual(list(self.root.iterdir()), [])


class LocalStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run dir"
        self.root.mkdir()
        self.deck = self.root / "d.spice"
        self.deck.write_text("* deck\n.end\n")
        self.exe = _fake_ngspice(Path(self.tmp.name))
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        (self.home / ".spiceinit").write_text("set wnflag=0\n")

    def _run(self, backend):
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            return backend.run_deck(self.deck, self.root, 30, None)

    def test_the_init_is_in_place_when_the_simulator_starts(self):
        got = self._run(execution.LocalBackend(str(self.exe)))
        self.assertIn("seen-at-start: * gf180-pll harness", got.output)
        self.assertIn("set wnflag=1|", got.output)
        self.assertEqual(siminit.init_of(got.output), f"sha256:{siminit.INIT_SHA256}")

    def test_an_ambient_home_init_is_not_touched(self):
        self._run(execution.LocalBackend(str(self.exe)))
        self.assertEqual((self.home / ".spiceinit").read_text(), "set wnflag=0\n")
        self.assertEqual([p.name for p in self.home.iterdir()], [".spiceinit"])

    def test_the_negative_control_stages_nothing_and_is_unattributed(self):
        got = self._run(execution.LocalBackend(str(self.exe), stage_init=False))
        self.assertIn("seen-at-start: none", got.output)
        self.assertEqual(siminit.init_of(got.output), "")
        self.assertFalse((self.root / ".spiceinit").exists())

    def test_a_timeout_still_leaves_the_staged_file_as_the_only_extra_file(self):
        with mock.patch.object(
            subprocess, "run", side_effect=subprocess.TimeoutExpired("ngspice", 5)
        ):
            got = execution.LocalBackend().run_deck(self.deck, self.root, 5, None)
        self.assertTrue(got.timed_out)
        self.assertEqual(
            sorted(p.name for p in self.root.iterdir()), [".spiceinit", "d.spice"]
        )

    @unittest.skipUnless(shutil.which("ngspice"), "ngspice not installed")
    def test_real_ngspice_runs_the_init_and_it_shadows_a_conflicting_home_init(self):
        deck = self.root / "real.spice"
        deck.write_text(
            "t\nv1 1 0 1\nr1 1 0 1k\n.control\nop\necho flag=$?wnflag\n.endc\n.end\n"
        )
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            got = execution.LocalBackend().run_deck(deck, self.root, 60, None)
        self.assertEqual(siminit.init_of(got.output), f"sha256:{siminit.INIT_SHA256}")
        self.assertIn("flag=1", got.output)


def _config(root: Path) -> batch.BatchConfig:
    return batch.BatchConfig(
        bucket="b", region="r", profile="p", provision_script=root / "p.sh",
        jobs_prefix="jobs",
    )


class BatchStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "pdk" / "gf180mcuD"
        self.pdk_dir.mkdir(parents=True)
        self.deck = self.root / "pt.spice"
        self.deck.write_text("* deck\n.end\n")

    def _backend(self, **kw):
        return batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir, pdk_variant="gf180mcuD",
            config=_config(self.root),
            runner=lambda argv, **k: subprocess.CompletedProcess(argv, 0, "", ""),
            **kw,
        )

    def test_the_plan_ships_the_init_bytes_and_lists_them_as_an_input(self):
        plan = self._backend().plan_deck(self.deck, 60)
        self.assertEqual(plan.init, siminit.INIT_TEXT)
        self.assertIn(siminit.UPLOAD_NAME, plan.inputs)

    def test_upload_writes_the_exact_bytes_into_the_inputs_prefix(self):
        backend = self._backend()
        plan = backend.plan_deck(self.deck, 60)
        staging = self.root / "staging"
        backend._upload(plan, staging)
        self.assertEqual(
            (staging / "inputs" / siminit.UPLOAD_NAME).read_text(), siminit.INIT_TEXT
        )

    def test_the_init_is_installed_after_the_inputs_and_before_ngspice(self):
        cmd = self._backend().plan_deck(self.deck, 60).spec["cmd"]
        copied = cmd.index('cp -R "$EDA_INPUT_DIR"')
        installed = cmd.index(f"cp -f {siminit.UPLOAD_NAME} {siminit.INIT_NAME}")
        ran = cmd.index("ngspice -b")
        self.assertLess(copied, installed)
        self.assertLess(installed, ran)
        self.assertNotIn("HOME=", cmd)

    def test_the_negative_control_ships_and_installs_nothing(self):
        plan = self._backend(stage_init=False).plan_deck(self.deck, 60)
        self.assertEqual(plan.init, "")
        self.assertNotIn(siminit.UPLOAD_NAME, plan.inputs)
        self.assertNotIn(f"cp -f {siminit.UPLOAD_NAME}", plan.spec["cmd"])
        self.assertIn(f"rm -f {siminit.INIT_NAME}", plan.spec["cmd"])

    def test_a_dependency_using_the_reserved_name_is_refused(self):
        clash = self.root / siminit.UPLOAD_NAME
        clash.write_text("* not ours\n")
        self.deck.write_text(f'.include "{clash}"\n.end\n')
        with self.assertRaises(execution.BackendError):
            self._backend().plan_deck(self.deck, 60)

    def test_the_collected_init_copy_is_not_published_into_the_rundir(self):
        backend = self._backend()
        plan = backend.plan_deck(self.deck, 60)
        collected = self.root / "collected"
        collected.mkdir()
        (collected / siminit.INIT_NAME).write_text(siminit.INIT_TEXT)
        (collected / "data.raw").write_text("raw")
        rundir = self.root / "rundir"
        backend._publish(plan, collected, rundir)
        self.assertEqual([p.name for p in rundir.iterdir()], ["data.raw"])

    def _execute(self, plan, *, ambient_home_init=True, break_upload=False):
        """Run the job command for real against a fake ngspice; return its dirs."""
        job = self.root / "job"
        inputs, outputs = job / "in", job / "out"
        inputs.mkdir(parents=True)
        outputs.mkdir()
        (inputs / plan.deck_name).write_text(plan.deck)
        if plan.init and not break_upload:
            (inputs / siminit.UPLOAD_NAME).write_text(plan.init)
        bindir = self.root / "bin"
        bindir.mkdir()
        _fake_ngspice(bindir)
        home = self.root / "home"
        home.mkdir()
        if ambient_home_init:
            (home / ".spiceinit").write_text("set wnflag=0\n")
        env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "EDA_JOB_DIR": str(job), "EDA_INPUT_DIR": str(inputs),
            "EDA_OUTPUT_DIR": str(outputs), "PDK_ROOT": str(self.root / "pdk"),
            "HOME": str(home),
        }
        subprocess.run(["bash", "-c", plan.spec["cmd"]], env=env, check=True,
                       capture_output=True)
        return outputs, home

    def test_the_job_command_runs_ngspice_with_the_init_present(self):
        plan = self._backend().plan_deck(self.deck, 60)
        outputs, home = self._execute(plan)
        log = (outputs / batch.LOG_NAME).read_text()
        self.assertIn("seen-at-start: * gf180-pll harness", log)
        self.assertEqual(siminit.init_of(log), f"sha256:{siminit.INIT_SHA256}")
        self.assertEqual((home / ".spiceinit").read_text(), "set wnflag=0\n")

    def test_the_executor_environment_file_records_the_init_identity(self):
        plan = self._backend().plan_deck(self.deck, 60)
        outputs, _ = self._execute(plan)
        env_text = (outputs / batch.ENV_NAME).read_text()
        self.assertIn(siminit.INIT_SHA256, env_text)
        self.assertIn("set wnflag=1", env_text)

    def test_the_negative_control_job_runs_without_an_init(self):
        plan = self._backend(stage_init=False).plan_deck(self.deck, 60)
        outputs, _ = self._execute(plan)
        log = (outputs / batch.LOG_NAME).read_text()
        self.assertIn("seen-at-start: none", log)
        self.assertEqual(siminit.init_of(log), "")

    def test_a_failed_install_stops_before_ngspice_and_reports_the_failure(self):
        plan = self._backend().plan_deck(self.deck, 60)
        outputs, _ = self._execute(plan, break_upload=True)
        self.assertEqual((outputs / batch.RC_NAME).read_text(), "1")
        log = (outputs / batch.LOG_NAME).read_text()
        self.assertIn("init staging failed", log)
        self.assertNotIn("ngspice-46 done", log)


class _Scripted:
    name = "batch"

    def __init__(self, output):
        self.output = output

    def describe(self) -> dict:
        return {"backend": self.name}

    def run_deck(self, deck_path, rundir, timeout_s, env=None):
        return execution.DeckRun(output=self.output, returncode=0, seconds=0.1, host="h")


class InitRecordTests(ManifestFixture):
    def _run(self, output):
        pdk = fake_pdk(self.root / "pdk")
        self.write({"measure": {"vout": "v(out)"}, "analyses": ["tran 1n 10n"]})
        tb = testbench.load(self.tb_dir)
        points = corners.build_sweep_grid(corners.resolve_corners(["typical"]), [27.0], [3.3])
        results = runner.run_grid(tb, pdk, points, self.root / "work", backend=_Scripted(output))
        record = report.build_record(
            tb=tb, pdk=pdk, points=points, results=results, ngspice="ngspice-46",
            repo_root=self.root, record_id="rid", started_utc="2026-01-01T00:00:00+00:00",
            wall_seconds=1.0, execution={"jobs": 1, "omp": {}, "backend": "batch"},
        )
        return results[0], record

    def test_a_point_whose_output_shows_the_init_carries_its_identity(self):
        result, record = self._run(f"{siminit.MARKER} wnflag=1\nm_vout = 1.65\n")
        ident = f"sha256:{siminit.INIT_SHA256}"
        self.assertEqual(result.init, ident)
        self.assertEqual(result.as_dict()["init"], ident)
        self.assertEqual(record["environment"]["execution"]["inits"], {ident: 1})

    def test_a_point_without_the_marker_is_unattributed(self):
        result, record = self._run("ngspice-46 done\nm_vout = 1.65\n")
        self.assertEqual(result.init, "")
        self.assertNotIn("init", result.as_dict())
        self.assertEqual(record["environment"]["execution"]["inits"], {"": 1})


class InitProvenanceTests(unittest.TestCase):
    def test_a_fully_attributed_run_names_the_checksum(self):
        ident = f"sha256:{siminit.INIT_SHA256}"
        lines = report._execution_init_lines({ident: 3})
        self.assertEqual(len(lines), 1)
        self.assertIn(ident, lines[0])
        self.assertNotIn("unattributed", lines[0])

    def test_unproven_points_are_disclosed_not_credited(self):
        ident = f"sha256:{siminit.INIT_SHA256}"
        line = report._execution_init_lines({ident: 1, "": 2})[0]
        self.assertIn("unattributed (2)", line)
        self.assertIn("not comparable", line)

    def test_a_run_with_no_proof_at_all_is_still_reported(self):
        line = report._execution_init_lines({"": 1})[0]
        self.assertIn("unattributed (1)", line)

    def test_no_attribution_block_renders_nothing(self):
        self.assertEqual(report._execution_init_lines({}), [])

    def test_the_console_line_carries_the_init_tally(self):
        ident = f"sha256:{siminit.INIT_SHA256}"
        line = report.execution_console_lines(
            {"backend": "batch", "hosts": {"h": 1}, "simulators": {"ngspice-46": 1},
             "inits": {ident: 1}}
        )[0]
        self.assertIn(f"init {ident} (1)", line)
        missing = report.execution_console_lines(
            {"backend": "batch", "hosts": {"h": 1}, "simulators": {}, "inits": {"": 1}}
        )[0]
        self.assertIn("init unattributed (1)", missing)


if __name__ == "__main__":
    unittest.main()
