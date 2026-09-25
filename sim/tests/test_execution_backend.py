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
import threading
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

    def test_the_launch_runs_under_the_resolved_region_and_profile(self):
        """#509: a launch that omits them asks as the launch script's OWN default.

        That default is the layer's *admin* provisioning identity, which a
        day-to-day submitting host has no credential for -- and the resulting
        failure is not a permission error but an empty subnet list, surfacing
        later as `only 0 subnet/AZ(s) resolved, floor is 3`, i.e. "the fleet is
        not provisioned" when the fleet was fine. Every transport call must run
        under the submission's resolved identity, the launch included.
        """
        transport = _FakeTransport(["done"], outputs={batch.RC_NAME: "0"})
        backend = self._backend(transport)
        backend.run_deck(self.deck, self.rundir, 60, None)
        argv = transport.launched()[0]
        self.assertEqual(argv[argv.index("--region") + 1], backend.config.region)
        self.assertEqual(argv[argv.index("--profile") + 1], backend.config.profile)

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
# 6b. The default runner: the one seam an injected `runner=` cannot cover
# ===========================================================================

class _RecordingRun(_FakeTransport):
    """A `subprocess.run` stand-in that also records the keywords it got."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kwargs: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.kwargs.append(dict(kwargs))
        return super().__call__(argv, **kwargs)


class DefaultRunnerTests(unittest.TestCase):
    """Drive `batch._default_runner` itself, with `subprocess.run` patched.

    Every other test in this file injects its own ``runner=``, and such a stub
    absorbs any keyword a call site adds. The real submission path goes through
    ``batch._default_runner``, which already fixes ``capture_output``/``text``/
    ``check`` -- so a call site that re-supplies one of them hands
    ``subprocess.run`` the same keyword twice and raises ``TypeError`` before
    ``aws`` or the provision script is ever reached (#512). Patching
    ``subprocess.run`` rather than the backend's runner keeps the collision
    reachable while still spawning no process.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "gf180mcuD"
        self.pdk_dir.mkdir()
        self.deck = self.root / "typical_27c_3.30v.spice"
        self.deck.write_text("* deck\n.end\n")
        self.rundir = self.root / "run"

    def _default_backend(self):
        return batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir,
            pdk_variant="gf180mcuD",
            config=_config(self.root),
            apply=True,
            poll_interval_s=0,
        )

    def test_launch_composes_a_call_the_default_runner_accepts(self):
        """The regressed call site: `_launch` through the real default runner."""
        backend = self._default_backend()
        plan = backend.plan_deck(self.deck, 60)
        run = _RecordingRun(["done"])
        with mock.patch.object(batch.subprocess, "run", run):
            backend._launch(plan)
        self.assertEqual(len(run.launched()), 1)
        self.assertIn("--apply", run.launched()[0])

    def test_a_whole_submission_runs_through_the_default_runner(self):
        backend = self._default_backend()
        run = _RecordingRun(
            ["running", "done"],
            outputs={batch.LOG_NAME: "m_vout = 1.65\n", batch.RC_NAME: "0"},
        )
        with mock.patch.object(batch.subprocess, "run", run):
            got = backend.run_deck(self.deck, self.rundir, 60, None)
        self.assertEqual(got.returncode, 0)
        self.assertEqual(got.output, "m_vout = 1.65\n")
        self.assertEqual(len(run.launched()), 1)

    def test_the_runner_owned_keywords_are_supplied_exactly_once_each(self):
        """No call site may re-specify what `_default_runner` already sets."""
        backend = self._default_backend()
        run = _RecordingRun(["done"], outputs={batch.RC_NAME: "0"})
        with mock.patch.object(batch.subprocess, "run", run):
            backend.run_deck(self.deck, self.rundir, 60, None)
        self.assertTrue(run.kwargs)
        for seen in run.kwargs:
            self.assertEqual(seen.get("capture_output"), True)
            self.assertEqual(seen.get("text"), True)
            self.assertEqual(seen.get("check"), False)


# ===========================================================================
# 6c. Two points, one rundir: a collected log/rc/host belongs to ONE job
# ===========================================================================

class _ConcurrentCollectTransport:
    """Transport that makes two overlapping collects interleave on purpose.

    ``run_grid`` runs points concurrently (``ThreadPoolExecutor``, at the CLI's
    own default ``-j``), and a testbench that declares no ``raw_files`` gives
    every point of the grid the *same* ``rundir``. The job contract's output
    names are fixed (``ngspice.log``/``ngspice.rc``/``ngspice.host``), so the
    download-then-read sequence in :meth:`batch.BatchBackend.run_deck` is only
    safe if each job's download lands somewhere no other job writes.

    This stub forces the worst ordering rather than hoping for it: every
    ``outputs/`` download writes *that job's own* marked content and then waits
    on a barrier, so **neither** point may read its collected files until
    **both** have downloaded. Any implementation that reads the three fixed
    names out of the shared ``rundir`` therefore serves both points whichever
    job wrote last -- misattributing one point's log, exit code and host.
    """

    def __init__(self, parties: int, timeout: float = 30.0):
        self.barrier = threading.Barrier(parties, timeout=timeout)
        #: Extra files a *deck* wrote (``wrdata`` output), which the harness
        #: reads back from the rundir via ``runner.capture_raw_files``.
        self.extra_outputs: dict[str, str] = {}
        #: The job command copies every file in its work directory to
        #: ``$EDA_OUTPUT_DIR``, so a job's own *inputs* -- the relocated deck,
        #: with the instance's PDK path substituted in -- come back too.
        self.echo_inputs = False
        #: Prepended to the log so a point can be made to measure cleanly.
        self.log_prefix = ""
        self.collected: list[str] = []
        #: ``{job id: the local staging directory it was uploaded from}``.
        self.staged: dict[str, Path] = {}

    @staticmethod
    def job_id_of(uri: str) -> str:
        """``s3://bucket/jobs/<job-id>/outputs/`` -> ``<job-id>``."""
        return uri.rstrip("/").rsplit("/", 2)[-2]

    def inputs_of(self, job_id: str) -> list[str]:
        """What this job's upload staged under ``inputs/``."""
        staging = self.staged.get(job_id)
        if staging is None:
            return []
        return sorted(p.name for p in (staging / "inputs").iterdir() if p.is_file())

    @staticmethod
    def rc_for(job_id: str) -> str:
        """A distinct exit code per point, so a swap cannot hide."""
        return "3" if "pointa" in job_id else "4"

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        if argv[0] != "aws":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "status.json" in " ".join(argv):
            body = json.dumps({"state": "done", "instance_id": "i-unattributed"})
            return subprocess.CompletedProcess(argv, 0, body, "")
        if "cp" in argv:
            index = argv.index("cp")
            source, dest = argv[index + 1], argv[index + 2]
            if not source.startswith("s3://") and dest.startswith("s3://"):
                # Upload: remember where this job's inputs were staged.
                self.staged[dest.rstrip("/").rsplit("/", 1)[-1]] = Path(source)
            if source.endswith("/outputs/"):
                job_id = self.job_id_of(source)
                out = Path(dest)
                out.mkdir(parents=True, exist_ok=True)
                (out / batch.LOG_NAME).write_text(
                    f"{self.log_prefix}* log for {job_id}\n"
                )
                (out / batch.RC_NAME).write_text(self.rc_for(job_id))
                (out / batch.HOST_NAME).write_text(f"host-{job_id}\n")
                for name, text in self.extra_outputs.items():
                    (out / name).write_text(f"{text} {job_id}\n")
                if self.echo_inputs:
                    for name in self.inputs_of(job_id):
                        (out / name).write_text("* as the instance ran it\n")
                self.collected.append(job_id)
                self.barrier.wait()
        return subprocess.CompletedProcess(argv, 0, "", "")


class ConcurrentRundirTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "gf180mcuD"
        self.pdk_dir.mkdir()
        # The shared scratch directory `_run_phase` hands every point of a
        # grid whose manifest declares no `raw_files`.
        self.rundir = self.root / "work"
        self.decks = []
        for stem in ("pointa", "pointb"):
            deck = self.root / f"{stem}.spice"
            deck.write_text("* deck\n.end\n")
            self.decks.append(deck)

    def _backend(self, transport):
        return batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir,
            pdk_variant="gf180mcuD",
            config=_config(self.root),
            apply=True,
            runner=transport,
            poll_interval_s=0,
        )

    def test_two_points_sharing_a_rundir_each_read_their_own_log_rc_and_host(self):
        transport = _ConcurrentCollectTransport(len(self.decks))
        backend = self._backend(transport)
        results: dict[str, execution.DeckRun] = {}
        failures: list[BaseException] = []

        def _point(deck: Path) -> None:
            try:
                results[deck.stem] = backend.run_deck(deck, self.rundir, 60, None)
            except BaseException as exc:  # noqa: BLE001 - reported below
                failures.append(exc)

        threads = [threading.Thread(target=_point, args=(d,)) for d in self.decks]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual([repr(f) for f in failures], [])
        self.assertEqual(sorted(results), ["pointa", "pointb"])
        self.assertEqual(len(transport.collected), 2)

        for stem, got in results.items():
            job_id = got.detail.split()[-1]
            self.assertIn(stem, job_id, "the detail must name this point's own job")
            self.assertEqual(got.output, f"* log for {job_id}\n")
            self.assertEqual(got.host, f"host-{job_id}")
            self.assertEqual(got.returncode, int(transport.rc_for(job_id)))
        self.assertNotEqual(results["pointa"].host, results["pointb"].host)

    def test_a_decks_own_outputs_still_reach_the_rundir_the_harness_reads(self):
        """`runner.capture_raw_files` reads the rundir, so collect must fill it."""
        transport = _ConcurrentCollectTransport(1)
        transport.extra_outputs = {"jit.dat": "* raw from"}
        backend = self._backend(transport)
        got = backend.run_deck(self.decks[0], self.rundir, 60, None)
        job_id = got.detail.split()[-1]

        raw = self.rundir / "jit.dat"
        self.assertTrue(raw.is_file(), "the deck's own output must land in rundir")
        self.assertIn(job_id, raw.read_text())
        # ...while the three harness-internal names stay job-scoped, where a
        # second point running into the same rundir cannot overwrite them.
        collected = self.rundir / f".batch-{job_id}" / "outputs"
        self.assertEqual((collected / batch.LOG_NAME).read_text(), got.output)
        self.assertEqual((collected / batch.HOST_NAME).read_text().strip(), got.host)

    def test_the_composed_deck_the_record_names_is_never_overwritten(self):
        """A job returns its own inputs too -- and one of them is the deck.

        The job command copies everything in its work directory into
        ``$EDA_OUTPUT_DIR``, so a collect brings back the *relocated* deck with
        the job instance's own PDK path substituted into it. The rundir a
        testbench without ``raw_files`` gets is the workdir the harness wrote
        ``<run-id>.spice`` into -- the very file the record's ``deck`` field
        names as the reproduction input -- so an input that came back must not
        be published over it.
        """
        transport = _ConcurrentCollectTransport(1)
        transport.echo_inputs = True
        deck = self.rundir / "typical_27c_3.30v.spice"
        self.rundir.mkdir(parents=True, exist_ok=True)
        composed = "* composed on THIS host\n.end\n"
        deck.write_text(composed)
        backend = self._backend(transport)
        got = backend.run_deck(deck, self.rundir, 60, None)

        job_id = got.detail.split()[-1]
        self.assertEqual(transport.inputs_of(job_id), [deck.name])
        self.assertEqual(deck.read_text(), composed)


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


class BatchRawFileCaptureTests(ManifestFixture):
    """A manifest that declares ``raw_files`` is unaffected by job isolation.

    Those testbenches already get a private per-point ``rundir``
    (``<workdir>/<run-id>.d``, ``runner._run_phase``), and the file the *deck*
    wrote is resolved from that rundir by ``runner.capture_raw_files`` -- so a
    batch collect that isolates only its own three contract files must still
    deliver the deck's output to the rundir the harness reads.
    """

    def test_a_raw_file_the_job_produced_is_captured_from_the_points_rundir(self):
        self.write(
            {
                "measure": {"vout": "v(out)"},
                "analyses": ["tran 1n 10n"],
                "raw_files": ["jit.dat"],
            }
        )
        tb = testbench.load(self.tb_dir)
        pdk = fake_pdk(self.root / "pdk")
        points = corners.build_sweep_grid(
            corners.resolve_corners(["typical"]), [27.0], [3.3]
        )
        transport = _ConcurrentCollectTransport(1)
        transport.extra_outputs = {"jit.dat": "* raw from"}
        transport.log_prefix = "m_vout = 1.65\n"
        backend = batch.BatchBackend(
            pdk_variant_dir=pdk.path,
            pdk_variant=pdk.variant,
            config=_config(self.root),
            apply=True,
            runner=transport,
            poll_interval_s=0,
        )
        results = runner.run_grid(
            tb, pdk, points, self.root / "work", backend=backend
        )
        self.assertEqual(results[0].status, "ok")
        self.assertEqual(results[0].measurements["vout"], 1.65)
        raw = results[0].raw_files["jit.dat"]
        self.assertTrue(raw.exists(), "the collected raw file must be readable")
        self.assertIn(backend.jobs[0].job_id, Path(raw.path).read_text())


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



# ===========================================================================
# 9. The transport contract itself: every call site must be callable through
#    the REAL default runner
# ===========================================================================

class StrictRunnerSignatureTests(unittest.TestCase):
    """The keyword rules ``_FakeTransport`` does not enforce, enforced.

    ``_FakeTransport.__call__(self, argv, **kwargs)`` accepts and silently
    drops whatever keywords a call site passes. That is the right shape for a
    stub *recording* calls, but it means the suite above says nothing about
    whether those keywords are legal for the runner the harness actually ships
    -- :func:`batch._default_runner`, which itself supplies
    ``capture_output``/``text``/``check`` to ``subprocess.run``.

    They were not. ``_launch`` repeated all three, so every real submission
    raised ``TypeError: subprocess.run() got multiple values for keyword
    argument 'capture_output'`` -- and did so *after* ``_upload`` had already
    written the job document and inputs to the bucket, i.e. the one failure
    mode that spends on a job that can never run. A full-grid submission from
    this repository failed at point 0 of 288 on it.

    This test closes the gap without a process, a credential or a network
    call: the transport binds each call against ``subprocess.run``'s own
    signature exactly as ``_default_runner`` would, and a duplicated keyword
    raises there the same way it does in production.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdk_dir = self.root / "gf180mcuD"
        self.pdk_dir.mkdir()
        self.deck = self.root / "typical_27c_3.30v.spice"
        self.deck.write_text("* deck\n.end\n")

    @staticmethod
    def _strict(inner):
        """Wrap a transport so it applies ``_default_runner``'s keyword rules."""
        import inspect

        signature = inspect.signature(subprocess.run)

        def transport(argv, **kwargs):
            # Exactly what _default_runner does with the call, minus running it.
            signature.bind(
                list(argv), capture_output=True, text=True, check=False, **kwargs
            )
            return inner(argv, **kwargs)

        return transport

    def test_every_submission_call_site_is_legal_for_the_default_runner(self):
        inner = _FakeTransport(
            ["done"],
            outputs={
                batch.LOG_NAME: "m_vout = 1.65\n",
                batch.RC_NAME: "0",
                batch.HOST_NAME: "ip-10-0-0-7\n",
            },
        )
        backend = batch.BatchBackend(
            pdk_variant_dir=self.pdk_dir,
            pdk_variant="gf180mcuD",
            config=_config(self.root),
            apply=True,
            runner=self._strict(inner),
            poll_interval_s=0,
        )
        got = backend.run_deck(self.deck, self.root / "run", 60, None)
        self.assertEqual(got.returncode, 0)
        # The launch call is the one that was broken; assert it was reached,
        # so a future refactor that stops launching cannot pass this test.
        self.assertEqual(len(inner.launched()), 1)

    def test_the_strict_transport_would_have_caught_the_defect(self):
        """The guard is real: re-introduce the duplicate and this fails."""
        transport = self._strict(_FakeTransport(["done"]))
        with self.assertRaises(TypeError):
            transport(["/provision.sh", "launch"], capture_output=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
