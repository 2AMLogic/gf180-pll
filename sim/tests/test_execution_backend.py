#!/usr/bin/env python3
"""Unit tests for the execution-backend seam (#496).

    python3 -m unittest discover -s sim/tests -v

No PDK, no ngspice, no network, no cloud credential and no `aws` binary: the
batch backend's transport is an injected callable in every test here, in the
same "no test in this suite ever calls the real thing" discipline the rest of
``sim/tests`` keeps for ``subprocess``. What is exercised is the part that
can be wrong *without* a fleet: how a deck is relocated, what job document is
shaped from it, how a returned status is classified back into the harness's
own per-point status vocabulary, and what all of that puts in a record's
provenance.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from _fixtures import ManifestFixture, fake_pdk  # noqa: E402
from harness import batch, corners, execution, report, runner, testbench  # noqa: E402


# ===========================================================================
# 1. Deck introspection -- what a relocating backend has to ship
# ===========================================================================

class DeckDependencyTests(unittest.TestCase):
    DECK = """* header
.param vdd_val=3.3
.include "/pdk/gf180mcuD/libs.tech/ngspice/design.ngspice"
.lib "/pdk/gf180mcuD/libs.tech/ngspice/sm141064.ngspice" typical
.lib "/pdk/gf180mcuD/libs.tech/ngspice/sm141064.ngspice" res_typical
.include /repo/design/netlist/pll_top.spice
.inc "/repo/sim/x/testbench/tb.sp"
.control
tran 1n 5u
.endc
.end
"""

    def test_every_include_and_lib_path_is_found_once(self):
        found = execution.deck_dependencies(self.DECK)
        self.assertEqual(
            found,
            [
                "/pdk/gf180mcuD/libs.tech/ngspice/design.ngspice",
                "/pdk/gf180mcuD/libs.tech/ngspice/sm141064.ngspice",
                "/repo/design/netlist/pll_top.spice",
                "/repo/sim/x/testbench/tb.sp",
            ],
        )

    def test_a_lib_section_name_is_not_mistaken_for_a_file(self):
        self.assertNotIn("typical", execution.deck_dependencies(self.DECK))
        self.assertNotIn("res_typical", execution.deck_dependencies(self.DECK))

    def test_non_card_lines_are_ignored(self):
        self.assertEqual(execution.deck_dependencies("* .include nope\ntran 1n 5u\n"), [])


class HostTallyTests(unittest.TestCase):
    def test_unattributed_points_are_counted_but_are_not_a_host(self):
        tally = execution.HostTally()
        tally.add("host-a")
        tally.add("host-a")
        tally.add("")
        self.assertEqual(tally.distinct, 1)
        self.assertEqual(tally.as_dict(), {"": 1, "host-a": 2})


# ===========================================================================
# 2. The local backend is still exactly what it always was
# ===========================================================================

class LocalBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.deck = self.root / "d.spice"
        self.deck.write_text("* deck\n.end\n")

    def test_argv_cwd_and_output_join_are_unchanged(self):
        seen = {}

        def _run(argv, **kwargs):
            seen["argv"] = argv
            seen["cwd"] = kwargs.get("cwd")
            seen["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(argv, 0, stdout="m_v = 1.0\n", stderr="warn")

        with mock.patch.object(subprocess, "run", side_effect=_run):
            got = execution.LocalBackend().run_deck(self.deck, self.root, 30, None)

        self.assertEqual(seen["argv"], ["ngspice", "-b", str(self.deck)])
        self.assertEqual(seen["cwd"], self.root)
        # An absent pin must leave the child's environment bit-for-bit ambient.
        self.assertIsNone(seen["env"])
        self.assertEqual(got.output, "m_v = 1.0\n" + "\n" + "warn")
        self.assertEqual(got.returncode, 0)
        self.assertTrue(got.host)

    def test_an_omp_pin_is_layered_over_the_ambient_environment(self):
        seen = {}

        def _run(argv, **kwargs):
            seen["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        with mock.patch.object(subprocess, "run", side_effect=_run):
            execution.LocalBackend().run_deck(
                self.deck, self.root, 30, {"OMP_NUM_THREADS": "2"}
            )
        self.assertEqual(seen["env"]["OMP_NUM_THREADS"], "2")
        self.assertIn("PATH", seen["env"])

    def test_a_timeout_is_reported_as_a_timeout_not_an_exception(self):
        with mock.patch.object(
            subprocess, "run", side_effect=subprocess.TimeoutExpired("ngspice", 5)
        ):
            got = execution.LocalBackend().run_deck(self.deck, self.root, 5, None)
        self.assertTrue(got.timed_out)
        self.assertEqual(got.returncode, -1)


# ===========================================================================
# 3. Batch config resolution -- and refusing to guess
# ===========================================================================

class BatchConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = self.root / "provision.sh"
        self.script.write_text("#!/bin/sh\n")

    def test_no_provision_script_is_an_error_naming_the_variable(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(execution.BackendError) as caught:
                batch.resolve_config()
        self.assertIn("SIM_BATCH_PROVISION_SCRIPT", str(caught.exception))

    def test_sim_batch_env_wins_over_the_layers_own_env_file(self):
        (self.root / "batch-fleet.env").write_text(
            'BATCH_JOB_BUCKET="from-file"\nBATCH_REGION="eu-west-1"\n'
        )
        env = {
            "SIM_BATCH_PROVISION_SCRIPT": str(self.script),
            "SIM_BATCH_JOB_BUCKET": "from-env",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            config = batch.resolve_config()
        self.assertEqual(config.bucket, "from-env")
        # Not overridden, so it still falls through to the layer's own file --
        # which is the single source of truth its IAM policy is bound to.
        self.assertEqual(config.region, "eu-west-1")
        self.assertEqual(config.profile, batch.DEFAULT_PROFILE)

    def test_klt_names_are_honoured_so_one_host_export_drives_both(self):
        env = {
            "KLT_BATCH_PROVISION_SCRIPT": str(self.script),
            "KLT_BATCH_JOB_BUCKET": "b",
            "KLT_BATCH_REGION": "us-east-1",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            config = batch.resolve_config()
        self.assertEqual(config.job_uri("j1"), "s3://b/jobs/j1")

    def test_an_unresolvable_bucket_says_all_three_places_it_looked(self):
        with mock.patch.dict(
            "os.environ", {"SIM_BATCH_PROVISION_SCRIPT": str(self.script)}, clear=True
        ):
            with self.assertRaises(execution.BackendError) as caught:
                batch.resolve_config()
        message = str(caught.exception)
        self.assertIn("SIM_BATCH_", message)
        self.assertIn("KLT_BATCH_", message)
        self.assertIn("batch-fleet.env", message)

    def test_provenance_withholds_the_bucket_and_the_host_path(self):
        """A record is committed evidence in a repo prepared to be public."""
        config = batch.BatchConfig(
            bucket="acct-12345-jobs",
            region="us-east-1",
            profile="p",
            provision_script=Path("/home/someone/infra/provision.sh"),
        )
        rendered = json.dumps(config.as_dict())
        self.assertNotIn("acct-12345-jobs", rendered)
        self.assertNotIn("/home/someone", rendered)
        self.assertIn("us-east-1", rendered)


# ===========================================================================
# 4. Relocating a composed deck
# ===========================================================================

def _config(root: Path) -> batch.BatchConfig:
    return batch.BatchConfig(
        bucket="bucket",
        region="us-east-1",
        profile="profile",
        provision_script=root / "provision.sh",
    )


class RelocateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "pdk" / "gf180mcuD"
        (self.pdk_dir / "libs.tech" / "ngspice").mkdir(parents=True)
        self.models = self.pdk_dir / "libs.tech" / "ngspice" / "sm141064.ngspice"
        self.models.write_text("* models\n")
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.dut = self.repo / "pll_top.spice"
        self.dut.write_text("* dut\n")
        self.backend = batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir,
            pdk_variant="gf180mcuD",
            config=_config(self.root),
            runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""),
        )

    def test_pdk_paths_become_a_token_and_are_never_uploaded(self):
        deck = f'.lib "{self.models}" typical\n.include "{self.dut}"\n'
        relocated, uploads = self.backend.relocate(deck)
        self.assertIn(
            f'{batch.PDK_TOKEN}/libs.tech/ngspice/sm141064.ngspice', relocated
        )
        self.assertEqual(list(uploads), ["pll_top.spice"])
        self.assertNotIn(str(self.pdk_dir), relocated)

    def test_repo_files_are_referenced_by_base_name(self):
        deck = f'.include "{self.dut}"\n'
        relocated, uploads = self.backend.relocate(deck)
        self.assertIn('.include "pll_top.spice"', relocated)
        self.assertEqual(uploads["pll_top.spice"], self.dut.resolve())

    def test_a_dangling_dependency_refuses_rather_than_shipping_a_broken_deck(self):
        deck = '.include "/nope/missing.spice"\n'
        with self.assertRaises(execution.BackendError) as caught:
            self.backend.relocate(deck)
        self.assertIn("missing.spice", str(caught.exception))

    def test_two_different_files_with_one_base_name_are_refused(self):
        other = self.repo / "sub"
        other.mkdir()
        twin = other / "pll_top.spice"
        twin.write_text("* other\n")
        deck = f'.include "{self.dut}"\n.include "{twin}"\n'
        with self.assertRaises(execution.BackendError) as caught:
            self.backend.relocate(deck)
        self.assertIn("base names must be distinct", str(caught.exception))


# ===========================================================================
# 5. The job document
# ===========================================================================

class JobPlanTests(RelocateTests):
    def _plan(self, timeout_s: int = 900):
        deck_path = self.root / "typical_27c_3.30v.spice"
        deck_path.write_text(f'.lib "{self.models}" typical\n.include "{self.dut}"\n')
        return self.backend.plan_deck(deck_path, timeout_s)

    def test_the_spec_carries_the_points_own_timeout_and_the_pdk_variant(self):
        plan = self._plan(900)
        self.assertEqual(plan.spec["timeout_seconds"], 900)
        self.assertEqual(plan.spec["pdk_variant"], "gf180mcuD")
        self.assertEqual(plan.spec["tool"], "ngspice")
        self.assertEqual(plan.spec["cores_per_job"], 1)

    def test_the_job_command_resolves_the_pdk_on_the_instance(self):
        cmd = self._plan().spec["cmd"]
        self.assertIn(batch.PDK_TOKEN, cmd)
        self.assertIn("${PDK_ROOT%/}/gf180mcuD", cmd)

    def test_the_job_command_returns_the_rc_and_the_host_and_never_fails_the_job(self):
        """A non-zero ngspice exit is a property of the POINT, not the job.

        A job marked ``failed`` would be indistinguishable from a transport
        fault, which is a different diagnosis and a different remedy.
        """
        cmd = self._plan().spec["cmd"]
        self.assertIn(batch.RC_NAME, cmd)
        self.assertIn(batch.HOST_NAME, cmd)
        self.assertTrue(cmd.rstrip().endswith("exit 0"))

    def test_the_inputs_are_the_deck_plus_everything_it_includes(self):
        plan = self._plan()
        self.assertEqual(
            sorted(plan.inputs), ["pll_top.spice", "typical_27c_3.30v.spice"]
        )
        # The deck's own bytes travel in `plan.deck`, relocated, not as a copy
        # of the on-disk original -- which still names this host's paths.
        self.assertIsNone(plan.inputs["typical_27c_3.30v.spice"])

    def test_job_ids_are_unique_per_submission(self):
        self.assertNotEqual(self._plan().job_id, self._plan().job_id)

    def test_planning_touches_no_transport(self):
        calls = []
        self.backend._run = lambda argv, **kw: calls.append(argv) or (
            subprocess.CompletedProcess(argv, 0, "", "")
        )
        self._plan()
        self.assertEqual(calls, [])


# ===========================================================================
# 6. Submission: refused by default, and classified on return
# ===========================================================================

class _FakeTransport:
    """Stands in for `aws` + the launch script, recording every call.

    ``states`` is the sequence of ``status.json`` states served to successive
    polls, so a test can make a job be ``running`` before it is terminal.
    """

    def __init__(self, states, outputs: dict[str, str] | None = None, instance="i-0abc"):
        self.states = list(states)
        self.outputs = outputs or {}
        self.instance = instance
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append(argv)
        if argv[0] != "aws":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "status.json" in " ".join(argv):
            state = self.states.pop(0) if self.states else "done"
            body = json.dumps({"state": state, "instance_id": self.instance})
            return subprocess.CompletedProcess(argv, 0, body, "")
        if "cp" in argv:
            source, dest = argv[argv.index("cp") + 1 : argv.index("cp") + 3]
            if source.endswith("/outputs/"):
                # Collect: materialise the job's outputs into the destination.
                out = Path(dest)
                out.mkdir(parents=True, exist_ok=True)
                for name, text in self.outputs.items():
                    (out / name).write_text(text)
        return subprocess.CompletedProcess(argv, 0, "", "")

    def launched(self) -> list[str]:
        return [a for a in self.calls if a[0] != "aws"]


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "gf180mcuD"
        self.pdk_dir.mkdir()
        self.deck = self.root / "typical_27c_3.30v.spice"
        self.deck.write_text("* deck\n.end\n")
        self.rundir = self.root / "run"

    def _backend(self, transport, apply=True):
        return batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir,
            pdk_variant="gf180mcuD",
            config=_config(self.root),
            apply=apply,
            runner=transport,
            poll_interval_s=0,
        )

    def test_without_apply_nothing_is_submitted_at_all(self):
        transport = _FakeTransport(["done"])
        backend = self._backend(transport, apply=False)
        with self.assertRaises(execution.BackendError) as caught:
            backend.run_deck(self.deck, self.rundir, 60, None)
        self.assertIn("--batch-apply", str(caught.exception))
        self.assertEqual(transport.calls, [])

    def test_a_completed_job_returns_the_log_the_rc_and_the_executing_host(self):
        transport = _FakeTransport(
            ["running", "done"],
            outputs={
                batch.LOG_NAME: "m_vout = 1.65\n",
                batch.RC_NAME: "0",
                batch.HOST_NAME: "ip-10-0-0-7\n",
            },
        )
        got = self._backend(transport).run_deck(self.deck, self.rundir, 60, None)
        self.assertEqual(got.output, "m_vout = 1.65\n")
        self.assertEqual(got.returncode, 0)
        self.assertEqual(got.host, "ip-10-0-0-7")
        self.assertFalse(got.timed_out)
        self.assertEqual(len(transport.launched()), 1)

    def test_the_job_document_and_the_relocated_deck_are_staged_before_launch(self):
        transport = _FakeTransport(["done"], outputs={batch.RC_NAME: "0"})
        backend = self._backend(transport)
        backend.run_deck(self.deck, self.rundir, 60, None)
        plan = backend.jobs[0]
        staging = self.rundir / f".batch-{plan.job_id}"
        self.assertTrue((staging / "job.json").is_file())
        self.assertTrue((staging / "inputs" / self.deck.name).is_file())
        spec = json.loads((staging / "job.json").read_text())
        self.assertEqual(spec["timeout_seconds"], 60)

    def test_a_layer_timeout_becomes_a_point_timeout(self):
        transport = _FakeTransport(["timeout"], outputs={batch.RC_NAME: "-1"})
        got = self._backend(transport).run_deck(self.deck, self.rundir, 60, None)
        self.assertTrue(got.timed_out)
        self.assertIn("budget", got.detail)

    def test_an_interrupted_job_is_reported_not_silently_retried_forever(self):
        transport = _FakeTransport(["interrupted"])
        got = self._backend(transport).run_deck(self.deck, self.rundir, 60, None)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("interrupted", got.detail)
        self.assertFalse(got.timed_out)

    def test_a_job_that_never_reaches_a_terminal_state_times_out_the_point(self):
        transport = _FakeTransport(["running"] * 50)
        backend = self._backend(transport)
        backend.provision_grace_s = 0
        got = backend.run_deck(self.deck, self.rundir, 0, None)
        self.assertTrue(got.timed_out)
        self.assertIn("never reached a terminal state", got.detail)

    def test_a_failed_upload_raises_rather_than_launching_a_job_with_no_inputs(self):
        def transport(argv, **kwargs):
            argv = list(argv)
            if argv[0] == "aws":
                return subprocess.CompletedProcess(argv, 1, "", "AccessDenied")
            raise AssertionError("launch must not be reached")

        backend = self._backend(transport)
        with self.assertRaises(execution.BackendError) as caught:
            backend.run_deck(self.deck, self.rundir, 60, None)
        self.assertIn("AccessDenied", str(caught.exception))


# ===========================================================================
# 7. The harness end of the seam: per-point attribution reaches the record
# ===========================================================================

class _ScriptedBackend:
    """A backend whose per-deck outcome (including host) is dictated per call."""

    name = "batch"

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def describe(self) -> dict:
        return {"backend": self.name, "region": "us-east-1"}

    def run_deck(self, deck_path, rundir, timeout_s, env=None):
        return self.outcomes.pop(0)


class BackendAttributionTests(ManifestFixture):
    def setUp(self):
        super().setUp()
        self.pdk = fake_pdk(self.root / "pdk")
        self.write({"measure": {"vout": "v(out)"}, "analyses": ["tran 1n 10n"]})
        self.tb = testbench.load(self.tb_dir)
        self.points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]), [27.0], [3.3]
        )

    def test_the_backends_host_lands_on_the_point_and_in_the_record(self):
        backend = _ScriptedBackend(
            [execution.DeckRun(output="m_vout = 1.65\n", returncode=0, seconds=1.0,
                               host="i-0feedface")]
        )
        results = runner.run_grid(
            self.tb, self.pdk, self.points, self.root / "work", backend=backend
        )
        self.assertEqual(results[0].host, "i-0feedface")
        self.assertEqual(results[0].as_dict()["host"], "i-0feedface")

        record = report.build_record(
            tb=self.tb, pdk=self.pdk, points=self.points, results=results,
            ngspice="ngspice-46", repo_root=self.root, record_id="rid",
            started_utc="2026-01-01T00:00:00+00:00", wall_seconds=1.0,
            execution={"jobs": 4, "omp": {}, **backend.describe()},
        )
        self.assertEqual(
            record["environment"]["execution"]["hosts"], {"i-0feedface": 1}
        )

    def test_an_unattributed_point_is_never_credited_to_the_recording_host(self):
        backend = _ScriptedBackend(
            [execution.DeckRun(output="m_vout = 1.65\n", returncode=0, seconds=1.0)]
        )
        results = runner.run_grid(
            self.tb, self.pdk, self.points, self.root / "work", backend=backend
        )
        self.assertEqual(results[0].host, "")
        self.assertNotIn("host", results[0].as_dict())

    def test_an_off_host_backend_is_not_given_a_local_openmp_pin(self):
        seen = {}

        class _Recording(_ScriptedBackend):
            def run_deck(self, deck_path, rundir, timeout_s, env=None):
                seen["env"] = env
                return super().run_deck(deck_path, rundir, timeout_s, env)

        backend = _Recording(
            [execution.DeckRun(output="m_vout = 1.0\n", returncode=0, seconds=0.1,
                               host="h")]
        )
        with mock.patch.object(
            runner, "omp_env_overrides", return_value={"OMP_NUM_THREADS": "4"}
        ):
            runner.run_grid(
                self.tb, self.pdk, self.points, self.root / "work", jobs=4,
                backend=backend,
            )
        self.assertIsNone(seen["env"])


# ===========================================================================
# 8. Provenance rendering
# ===========================================================================

class ExecutionProvenanceTests(unittest.TestCase):
    def test_a_single_host_local_record_renders_exactly_the_one_line_it_always_did(self):
        lines = report._execution_lines(
            {"jobs": 4, "omp": {}, "backend": "local", "hosts": {"box": 45}}, "box"
        )
        self.assertEqual(len(lines), 1)
        self.assertIn("4 parallel ngspice job(s)", lines[0])

    def test_a_record_with_no_execution_block_still_renders_nothing(self):
        self.assertEqual(report._execution_lines({}, "box"), [])

    def test_an_off_host_run_says_the_recording_host_ran_nothing(self):
        lines = report._execution_lines(
            {
                "jobs": 12,
                "omp": {},
                "backend": "batch",
                "hosts": {"i-0a": 23, "i-0b": 22},
            },
            "submitter",
        )
        self.assertIn("off-host job(s)", lines[0])
        self.assertIn("ran no ngspice of its own", lines[0])
        self.assertIn("budgets the recording host, which ran nothing", lines[0])
        self.assertIn("45 point(s) across 2 named execution host(s)", lines[1])
        self.assertIn("`i-0a` (23)", lines[1])

    def test_unattributed_points_are_disclosed_not_hidden(self):
        lines = report._execution_lines(
            {"jobs": 1, "omp": {}, "backend": "batch", "hosts": {"i-0a": 2, "": 1}},
            "submitter",
        )
        self.assertIn("unattributed (1)", lines[1])

    def test_a_local_run_that_somehow_reports_a_foreign_host_still_discloses_it(self):
        lines = report._execution_lines(
            {"jobs": 1, "omp": {}, "backend": "local", "hosts": {"elsewhere": 3}},
            "here",
        )
        self.assertEqual(len(lines), 2)
        self.assertIn("`elsewhere` (3)", lines[1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
