"""Off-host execution of one composed deck, via an S3 job-contract batch layer.

This is the consumer half of the "submit / wait / collect" seam an external
EDA batch execution layer leaves to the repository that owns the tool
knowledge. The layer itself runs jobs on ephemeral Spot capacity and knows
nothing about ngspice; this module knows nothing about instances, fleets, or
budgets. The whole of the contract between them is four steps and one small
document:

    1. write   s3://<bucket>/<jobs>/<job-id>/job.json  (+ inputs/)
    2. launch  <provision-script> launch --job <job-id> --apply
    3. poll    s3://<bucket>/<jobs>/<job-id>/status.json
               until state in {done, failed, timeout, interrupted}
    4. collect s3://<bucket>/<jobs>/<job-id>/outputs/

``job.json`` is a *shell-command* contract -- ``{tool, cmd, pdk_variant,
pdk_root, cores_per_job, timeout_seconds}``, everything optional but ``cmd``
-- which the layer runs with ``EDA_INPUT_DIR`` / ``EDA_OUTPUT_DIR`` /
``EDA_JOB_DIR`` and a resolved ``PDK_ROOT`` in the environment, collecting
whatever lands in ``$EDA_OUTPUT_DIR``.

Nothing here is credential-bearing or site-specific: the bucket, region,
profile, jobs prefix, and provision-script path all resolve from
configuration (``SIM_BATCH_*`` in the environment, then the ``KLT_BATCH_*``
names an installed ``klt`` already uses for the same layer, then the layer's
own env file sitting beside the provision script). An unresolvable value
raises :class:`~sim.harness.execution.BackendError` naming all three sources
rather than guessing one.

Why one job per deck
--------------------
The harness's per-point contract is the thing worth protecting: one point
that times out, fails to converge, or loses its log must degrade *that point*
and leave the other 44 intact and recorded. One fleet job per deck preserves
that exactly -- a job's ``timeout_seconds`` is the point's own ``--timeout``,
and a lost job is a lost point, not a lost grid. Concurrency then comes for
free from the fan-out the harness already has: under a batch backend
``run_grid``'s ``-j`` bounds how many *jobs are in flight*, not how many
ngspice processes run locally, so the submitting host does no simulation
work at all and ``-j`` may exceed its core count.

Relocating the deck
-------------------
``compose_deck`` writes absolute host paths for its ``.include``/``.lib``
cards, which do not exist on a job instance. Rather than teach the composer
about remote execution, this module rewrites the *composed* deck:

- a path under the resolved PDK variant directory becomes
  ``@PDK_VARIANT_DIR@/<relative>``, and the job command substitutes the
  instance's own resolved variant directory before invoking ngspice. The PDK
  is baked into the job image, so it is never uploaded.
- any other referenced file (the DUT export, the stimulus fragment) is
  uploaded to ``inputs/`` under its base name and referenced by that name;
  the job command runs ngspice from the directory those land in.

Both rewrites are content-addressed by the *deck itself* (see
``execution.deck_dependencies``), so a manifest that adds a fragment needs no
change here.

One directory per job, in both directions
-----------------------------------------
The job contract's own output names are fixed (``ngspice.log``,
``ngspice.rc``, ``ngspice.host``), while the ``rundir`` the harness hands a
point is *shared* by every point of a grid unless the manifest declares
``raw_files``. So both halves of the transport are scoped to
``<rundir>/.batch-<job-id>/``: the upload stages ``job.json``/``inputs/``
there, and the download collects ``outputs/`` there -- never into the shared
rundir, where a concurrent point's download would otherwise overwrite those
three files between this point's own download and its read of them, and
silently attribute another PVT point's log, exit code and host to this one
(#507). What the *deck* wrote is then published into the rundir, because that
is where the harness resolves a manifest's ``raw_files``.

Every transport command is bounded
----------------------------------
Each upload, launch, status read and output download runs under its own
wall-clock budget (:data:`DEFAULT_TRANSPORT_TIMEOUT_S` and siblings), and an
overrun degrades only the affected point: a failed :class:`DeckRun` naming
the job id and the stage, with whatever partial output and downloaded files
exist kept as evidence. A launch that overruns is never retried, because it
may already have submitted a job (#727).

Safety: nothing is submitted without ``apply``
----------------------------------------------
Launching jobs spends real money from a shared budget. Mirroring the
execution layer's own "nothing mutates without ``--apply``" discipline, a
:class:`BatchBackend` constructed with ``apply=False`` (the CLI default for
``--backend batch``) will shape and report every job it *would* submit and
refuse to submit any of them. ``sim/run_corners.py --backend batch`` prints
that plan and exits without minting a record; ``--batch-apply`` is the
deliberate second step.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .execution import BackendError, DeckRun, deck_dependencies

#: Placeholder the relocated deck carries in place of the submitting host's
#: PDK variant directory. Resolved on the job instance, not here.
PDK_TOKEN = "@PDK_VARIANT_DIR@"

#: Files the job command writes into ``$EDA_OUTPUT_DIR`` in addition to
#: whatever the deck itself produced.
LOG_NAME = "ngspice.log"
RC_NAME = "ngspice.rc"
HOST_NAME = "ngspice.host"
#: What the instance actually ran on: the ngspice banner, the PDK revision
#: stamp beside the resolved variant, the image manifest, CPU and thread
#: environment. Written best-effort (never fails the job) so a batch result
#: that disagrees with a local one can be attributed to a concrete image delta
#: instead of guessed at (#533).
ENV_NAME = "ngspice.env"

#: The four above, as a set. These names are fixed by the job contract, so two
#: jobs' copies of them may never share a directory -- they are collected into
#: a per-job directory and deliberately not published into a point's (possibly
#: shared) rundir. See :meth:`BatchBackend._collect`.
CONTRACT_OUTPUT_NAMES = frozenset({LOG_NAME, RC_NAME, HOST_NAME, ENV_NAME})

#: Terminal ``status.json`` states. ``interrupted`` is terminal *for one
#: submission*: the layer's own reconcile step may relaunch it, but this
#: backend reports the point rather than silently waiting forever.
TERMINAL_STATES = ("done", "failed", "timeout", "interrupted")

#: How long to wait beyond the deck's own timeout before giving up on a job
#: that never reached a terminal state. Spot capacity has to be acquired and
#: an instance booted before the deck starts, so the submitter's deadline
#: cannot be the deck's timeout alone.
DEFAULT_PROVISION_GRACE_S = 1800

DEFAULT_POLL_INTERVAL_S = 20

#: The execution layer caps how many instances it will have running at once,
#: **fleet-wide and shared with every other campaign submitting to it**, and
#: refuses a launch that would exceed it:
#:
#:     error: 9 instance(s) already running + 1 requested exceeds
#:     BATCH_MAX_CONCURRENT_INSTANCES=8
#:
#: That refusal is *transient by construction* -- the running instances are
#: finishing -- and it is not a thing a submitter can avoid by choosing its own
#: ``-j``: the ceiling counts instances this run did not launch. Matched on the
#: layer's own contract name, the same coupling :func:`_env_file_value` already
#: has, rather than on the sentence around it.
CEILING_REFUSAL_RE = re.compile(r"BATCH_MAX_CONCURRENT_INSTANCES", re.IGNORECASE)

#: How many times a ceiling-refused launch is re-offered before the point is
#: given up on. With :data:`DEFAULT_POLL_INTERVAL_S` between attempts this is
#: ~20 minutes of waiting for a slot, which is the same order as the provision
#: grace a job already gets once it *is* launched -- a submitter willing to wait
#: half an hour for Spot capacity should be willing to wait for a slot to ask
#: for it in.
LAUNCH_CEILING_ATTEMPTS = 60

#: Wall-clock budgets for each *transport* command, in seconds (#727).
#:
#: The polling deadline in :meth:`BatchBackend.run_deck` bounds how long the
#: submitter waits for a job to reach a terminal state, but it is checked
#: *between* commands -- it cannot interrupt one. A stalled upload, launch
#: script, status read or output download therefore held a grid worker
#: forever, and ``run_grid`` waits for every worker before any record is
#: minted, so one hung socket withheld every sibling point's result. Each
#: transport command now carries its own budget:
#:
#: - :data:`DEFAULT_TRANSPORT_TIMEOUT_S` -- the job-document/inputs upload
#:   and each ``status.json`` read. Both move kilobytes.
#: - :data:`DEFAULT_LAUNCH_TIMEOUT_S` -- one invocation of the layer's launch
#:   script, which itself makes several provider API calls.
#: - :data:`DEFAULT_COLLECT_TIMEOUT_S` -- the recursive output download,
#:   which carries the deck's waveforms and so can be large.
#:
#: These are *not* the simulator's budget (``--timeout``, carried in the job
#: document and enforced on the instance) and not the provisioning grace
#: (:data:`DEFAULT_PROVISION_GRACE_S`, which bounds the wait for a terminal
#: state). They bound only how long this host waits on one command it ran.
DEFAULT_TRANSPORT_TIMEOUT_S = 300
DEFAULT_LAUNCH_TIMEOUT_S = 600
DEFAULT_COLLECT_TIMEOUT_S = 1800

#: After a timed-out command's process group is killed, how long to wait for
#: its pipes to drain before giving up on the remaining partial output.
_REAP_GRACE_S = 5.0

#: Transport stages, as they are named in a point's diagnostic detail.
STAGE_UPLOAD = "upload"
STAGE_LAUNCH = "launch"
STAGE_STATUS = "status"
STAGE_COLLECT = "collect"

#: Default ``aws`` CLI profile name. A profile *name* is not a secret -- the
#: credential it resolves to lives in the operator's own AWS config, and a
#: host without that profile gets a clean CLI error naming it.
DEFAULT_PROFILE = "batch-runner-submit"

DEFAULT_JOBS_PREFIX = "jobs"


def _default_runner(
    argv: Sequence[str], timeout: float | None = None, **kwargs
) -> subprocess.CompletedProcess:
    """Run one transport command, capturing its output.

    **Output capture, text mode and the never-raise-on-exit-status rule are
    this function's to set, and a call site must not repeat them** -- passing
    ``capture_output``/``text``/``check`` raises ``TypeError`` (a duplicated
    or unknown keyword), which is a submission that dies *after* its inputs
    are already uploaded (#512). See the regression tests in
    ``sim/tests/test_execution_backend.py`` (``StrictRunnerSignatureTests``,
    ``DefaultRunnerTests``), which apply these keyword rules to every call
    site the submission path makes. ``timeout`` is the one keyword call sites
    are expected to pass.

    ``timeout`` (seconds, or ``None`` for unbounded) is enforced against the
    command's **whole process group**, not just its direct child. The child
    is started in a session of its own, and on expiry that session is killed
    and :class:`subprocess.TimeoutExpired` is raised carrying whatever
    stdout/stderr had arrived. ``subprocess.run``'s own ``timeout`` kills only
    the direct child, which for the launch script -- a shell script that runs
    provider CLI calls of its own -- would leave the actual stalled call
    running unobserved after this host had given up on it (#727).
    """
    argv = list(argv)
    with subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        **kwargs,
    ) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            try:
                stdout, stderr = proc.communicate(timeout=_REAP_GRACE_S)
            except subprocess.TimeoutExpired:
                # A descendant that left the session still holds a pipe open.
                # Do not wait on it: report what had arrived when time ran out.
                stdout, stderr = exc.stdout, exc.stderr
                proc.kill()
            raise subprocess.TimeoutExpired(
                argv, timeout, output=stdout, stderr=stderr
            ) from None
        except BaseException:
            _kill_group(proc)
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def _kill_group(proc: subprocess.Popen) -> None:
    """Kill ``proc`` and everything in its session; never raises."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        # Already gone, or no process groups on this platform.
        try:
            proc.kill()
        except OSError:
            pass


def _text(value) -> str:
    """Partial output from a :class:`subprocess.TimeoutExpired`, as text.

    On POSIX the exception carries *bytes* even for a ``text=True`` call,
    because the partial read never reached the decoder.
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class StageTimeout(Exception):
    """One transport command exceeded its budget (#727).

    Internal to this module: :meth:`BatchBackend.run_deck` converts it into
    a failed :class:`DeckRun` for the affected point and never lets it reach
    ``run_grid``.
    """

    def __init__(self, stage: str, job_id: str, budget_s: float, stdout="", stderr=""):
        self.stage = stage
        self.job_id = job_id
        self.budget_s = budget_s
        self.stdout = _text(stdout)
        self.stderr = _text(stderr)
        super().__init__(self.describe())

    def describe(self) -> str:
        text = (
            f"job {self.job_id} {self.stage} stage timed out after "
            f"{self.budget_s:g}s"
        )
        for label, stream in (("stdout", self.stdout), ("stderr", self.stderr)):
            flat = " ".join(stream.split())
            if flat:
                text += f" (partial {label}: {flat[-500:]})"
        return text


def _env_file_value(path: Path, key: str) -> str:
    """Read ``KEY="value"`` out of a shell env file without sourcing it.

    The execution layer's own env file is the single source of truth for the
    bucket/region its IAM policy is bound to, so reading it is strictly
    better than re-declaring those values here -- but it is shell, and this
    is Python, so it is *parsed*, never executed.
    """
    try:
        text = path.read_text()
    except OSError:
        return ""
    pattern = re.compile(rf'^\s*(?:export\s+)?{re.escape(key)}=(.*)$', re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    value = match.group(1).strip()
    # The values this reads are simple identifiers (a bucket name, a region,
    # a profile), so a conservative unquote plus trailing-comment strip is
    # enough -- and is strictly safer than sourcing the file.
    if value[:1] in ('"', "'"):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    return value.split("#", 1)[0].strip()


@dataclass(frozen=True)
class BatchConfig:
    """Everything the batch layer needs, and nothing it does not.

    Resolution order per field, most specific first: an explicit constructor
    argument, ``SIM_BATCH_<NAME>`` in the environment, ``KLT_BATCH_<NAME>``
    (the same names an installed ``klt`` resolves for this same layer, so one
    host export drives both), then the layer's own env file beside the
    provision script.
    """

    bucket: str
    region: str
    profile: str
    provision_script: Path
    jobs_prefix: str = DEFAULT_JOBS_PREFIX

    @property
    def jobs_uri_base(self) -> str:
        return f"s3://{self.bucket}/{self.jobs_prefix.strip('/')}"

    def job_uri(self, job_id: str) -> str:
        return f"{self.jobs_uri_base}/{job_id}"

    def as_dict(self) -> dict:
        """The provenance-safe subset, for a record that will be committed.

        Deliberately **not** the whole config. ``sim/`` records are committed
        evidence in a repository prepared to be public, so two fields are
        withheld on purpose:

        - ``bucket`` -- an object-store bucket name commonly embeds the
          owning account identifier, and a record does not need it to be
          reproducible: the bucket is where the *job* transited, not where
          the measurement came from, and it is configuration on the
          operator's side either way.
        - ``provision_script`` -- an absolute path on the submitting host,
          i.e. a leaked home directory, which this repo's evidence records
          must not carry.

        ``region`` stays, because "which region's capacity produced this
        evidence" is a real provenance fact and carries nothing private.
        """
        return {"region": self.region}


def _resolve(name: str, explicit: str, env_file: Path | None, env_key: str) -> str:
    if explicit:
        return explicit
    for prefix in ("SIM_BATCH_", "KLT_BATCH_"):
        value = os.environ.get(prefix + name, "").strip()
        if value:
            return value
    if env_file is not None:
        value = _env_file_value(env_file, env_key)
        if value:
            return value
    return ""


def resolve_config(
    bucket: str = "",
    region: str = "",
    profile: str = "",
    provision_script: str = "",
    jobs_prefix: str = "",
) -> BatchConfig:
    """Resolve the batch layer's configuration or say exactly what is missing."""
    script = _resolve("PROVISION_SCRIPT", provision_script, None, "")
    if not script:
        raise BackendError(
            "batch backend: no provision script. Set $SIM_BATCH_PROVISION_SCRIPT "
            "(or $KLT_BATCH_PROVISION_SCRIPT) to the execution layer's "
            "`... launch --job <id> --apply` entry point."
        )
    script_path = Path(script).expanduser()
    env_file = script_path.parent / "batch-fleet.env"

    resolved_bucket = _resolve("JOB_BUCKET", bucket, env_file, "BATCH_JOB_BUCKET")
    resolved_region = _resolve("REGION", region, env_file, "BATCH_REGION")
    resolved_profile = (
        _resolve("PROFILE", profile, env_file, "BATCH_SUBMIT_PROFILE") or DEFAULT_PROFILE
    )
    resolved_prefix = (
        _resolve("JOBS_PREFIX", jobs_prefix, env_file, "BATCH_JOBS_PREFIX")
        or DEFAULT_JOBS_PREFIX
    )

    missing = [
        label
        for label, value in (("bucket", resolved_bucket), ("region", resolved_region))
        if not value
    ]
    if missing:
        raise BackendError(
            "batch backend: could not resolve " + ", ".join(missing) + ". Tried, in "
            f"order: $SIM_BATCH_*, $KLT_BATCH_*, and {env_file}."
        )
    return BatchConfig(
        bucket=resolved_bucket,
        region=resolved_region,
        profile=resolved_profile,
        provision_script=script_path,
        jobs_prefix=resolved_prefix,
    )


@dataclass
class JobPlan:
    """One deck, shaped for submission -- and printable without submitting."""

    job_id: str
    job_uri: str
    #: ``job.json``'s exact content.
    spec: dict
    #: ``{uploaded name: local source path}``. The relocated deck is included
    #: under its own name with a ``None`` source (its bytes are in ``deck``).
    inputs: dict[str, Path | None]
    #: The relocated deck text actually uploaded.
    deck: str
    deck_name: str

    def render(self) -> str:
        uploads = ", ".join(sorted(self.inputs))
        return (
            f"  job {self.job_id}\n"
            f"    uri     : {self.job_uri}\n"
            f"    inputs  : {uploads}\n"
            f"    timeout : {self.spec.get('timeout_seconds')}s"
            f"  cores/job: {self.spec.get('cores_per_job')}\n"
            f"    cmd     : {self.spec.get('cmd')}"
        )


class BatchBackend:
    """Run each composed deck as one job on an external batch execution layer.

    ``apply=False`` (the default) is a hard refusal to submit, not a quiet
    no-op: :meth:`run_deck` raises :class:`BackendError`. Callers that want a
    plan use :meth:`plan_deck` directly, which never touches the network.
    """

    name = "batch"

    def __init__(
        self,
        pdk_variant_dir: Path,
        pdk_variant: str,
        *,
        config: BatchConfig | None = None,
        apply: bool = False,
        cores_per_job: int = 1,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        provision_grace_s: float = DEFAULT_PROVISION_GRACE_S,
        runner=None,
        job_prefix: str = "gf180-pll-sim",
        transport_timeout_s: float = DEFAULT_TRANSPORT_TIMEOUT_S,
        launch_timeout_s: float = DEFAULT_LAUNCH_TIMEOUT_S,
        collect_timeout_s: float = DEFAULT_COLLECT_TIMEOUT_S,
    ) -> None:
        self.pdk_variant_dir = Path(pdk_variant_dir)
        self.pdk_variant = pdk_variant
        self.config = config if config is not None else resolve_config()
        self.apply = apply
        self.cores_per_job = cores_per_job
        self.poll_interval_s = poll_interval_s
        self.provision_grace_s = provision_grace_s
        for label, value in (
            ("transport", transport_timeout_s),
            ("launch", launch_timeout_s),
            ("collect", collect_timeout_s),
        ):
            if not value or value <= 0:
                raise BackendError(
                    f"batch backend: the {label} timeout must be a positive "
                    f"number of seconds, not {value!r}; an unbounded transport "
                    "command can hold a grid worker forever (#727)."
                )
        #: Per-command budgets; see :data:`DEFAULT_TRANSPORT_TIMEOUT_S`.
        self.transport_timeout_s = transport_timeout_s
        self.launch_timeout_s = launch_timeout_s
        self.collect_timeout_s = collect_timeout_s
        self._run = runner if runner is not None else _default_runner
        self.job_prefix = job_prefix
        #: Every plan this backend shaped, in submission order -- the record's
        #: audit trail of which job id ran which point.
        self.jobs: list[JobPlan] = []

    # -- provenance ------------------------------------------------------ #

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "submitted": bool(self.apply),
            "cores_per_job": self.cores_per_job,
            **self.config.as_dict(),
        }

    def prepare(self, points: int) -> None:  # noqa: D401 - no-op hook
        """Nothing to set up: each deck carries its own job."""

    # -- shaping (no network) -------------------------------------------- #

    def relocate(self, deck_text: str) -> tuple[str, dict[str, Path]]:
        """Rewrite a composed deck's absolute paths; return it plus uploads.

        Raises :class:`BackendError` for a dependency that is neither under
        the PDK variant directory nor a readable file -- a deck that would
        arrive at the instance with a dangling include is a worse outcome
        than a refused submission.
        """
        uploads: dict[str, Path] = {}
        replacements: dict[str, str] = {}
        variant_dir = self.pdk_variant_dir.resolve()
        for dependency in deck_dependencies(deck_text):
            path = Path(dependency)
            try:
                resolved = path.resolve()
            except OSError:  # pragma: no cover - defensive
                resolved = path
            if resolved.is_relative_to(variant_dir):
                replacements[dependency] = (
                    f"{PDK_TOKEN}/{resolved.relative_to(variant_dir).as_posix()}"
                )
                continue
            if not resolved.is_file():
                raise BackendError(
                    f"batch backend: deck references {dependency!r}, which is "
                    "neither under the PDK variant directory "
                    f"({variant_dir}) nor a readable file -- it could not be "
                    "shipped to the job instance."
                )
            name = resolved.name
            if uploads.get(name, resolved) != resolved:
                raise BackendError(
                    f"batch backend: two different files named {name!r} are "
                    f"referenced by one deck ({uploads[name]} and {resolved}); "
                    "the job contract uploads inputs flat, so their base names "
                    "must be distinct."
                )
            uploads[name] = resolved
            replacements[dependency] = name

        out: list[str] = []
        for line in deck_text.splitlines():
            for original, replacement in replacements.items():
                if original in line:
                    line = line.replace(original, replacement)
                    break
            out.append(line)
        return "\n".join(out) + "\n", uploads

    def job_command(self, deck_name: str) -> str:
        """The ``cmd`` field: resolve the PDK, run the deck, return everything.

        Deliberately never fails the *job* on a failing deck (`exit 0`): a
        non-zero ngspice exit is a property of the point, carried back in
        ``ngspice.rc`` and classified by the harness exactly as a local
        non-zero exit is. A job marked ``failed`` would instead be
        indistinguishable from a transport fault.
        """
        variant = shlex.quote(self.pdk_variant)
        deck = shlex.quote(deck_name)
        token = PDK_TOKEN
        return (
            'set -u; '
            'work="$EDA_JOB_DIR/ngspice"; mkdir -p "$work"; '
            'cp -R "$EDA_INPUT_DIR"/. "$work"/; cd "$work"; '
            f'variant_dir="${{PDK_ROOT%/}}/{variant}"; '
            f'for f in *.spice *.sp; do [ -f "$f" ] || continue; '
            f'sed -i "s|{token}|$variant_dir|g" "$f"; done; '
            f'ngspice -b {deck} > {LOG_NAME} 2>&1; rc=$?; '
            f'printf "%s" "$rc" > "$EDA_OUTPUT_DIR/{RC_NAME}"; '
            f'hostname > "$EDA_OUTPUT_DIR/{HOST_NAME}" 2>/dev/null || true; '
            f'{{ echo "== ngspice"; ngspice --version 2>&1 | head -12; '
            f'echo "== pdk_variant_dir $variant_dir"; '
            f'cat "$variant_dir/SOURCES" 2>&1 | head -5; '
            f'echo "== image manifest"; cat /etc/eda-batch-image.json 2>&1; '
            f'echo "== cpu"; grep -m1 "model name" /proc/cpuinfo; nproc; '
            f'echo "OMP_NUM_THREADS=${{OMP_NUM_THREADS:-<unset>}}"; }} '
            f'> "$EDA_OUTPUT_DIR/{ENV_NAME}" 2>&1 || true; '
            'find . -maxdepth 1 -type f -exec cp -f {} "$EDA_OUTPUT_DIR/" \\; ; '
            'exit 0'
        )

    def plan_deck(self, deck_path: Path, timeout_s: int) -> JobPlan:
        """Shape one deck's job without touching the network."""
        deck_text = deck_path.read_text()
        relocated, uploads = self.relocate(deck_text)
        job_id = f"{self.job_prefix}-{deck_path.stem}-{uuid.uuid4().hex[:8]}"
        inputs: dict[str, Path | None] = {deck_path.name: None}
        inputs.update(uploads)
        spec = {
            "tool": "ngspice",
            "cmd": self.job_command(deck_path.name),
            "pdk_variant": self.pdk_variant,
            "cores_per_job": self.cores_per_job,
            # The layer kills the job at this budget; the deck's own timeout is
            # the point's, so they are deliberately the same number.
            "timeout_seconds": int(timeout_s),
        }
        return JobPlan(
            job_id=job_id,
            job_uri=self.config.job_uri(job_id),
            spec=spec,
            inputs=inputs,
            deck=relocated,
            deck_name=deck_path.name,
        )

    # -- transport ------------------------------------------------------- #

    def _aws_argv(self, *args: str) -> list[str]:
        return [
            "aws",
            "--region",
            self.config.region,
            "--profile",
            self.config.profile,
            *args,
        ]

    def _bounded(
        self, stage: str, plan: JobPlan, argv: Sequence[str], timeout_s: float
    ) -> subprocess.CompletedProcess:
        """Run one transport command under ``timeout_s``, or raise
        :class:`StageTimeout` naming the stage and the job.

        Every transport command goes through here, so none of them can be
        issued without a budget (#727).
        """
        try:
            return self._run(list(argv), timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise StageTimeout(
                stage, plan.job_id, timeout_s, exc.stdout, exc.stderr
            ) from None

    def _upload(self, plan: JobPlan, staging: Path) -> None:
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "job.json").write_text(json.dumps(plan.spec, indent=2) + "\n")
        inputs_dir = staging / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        (inputs_dir / plan.deck_name).write_text(plan.deck)
        for name, source in plan.inputs.items():
            if source is None:
                continue
            (inputs_dir / name).write_bytes(Path(source).read_bytes())
        proc = self._bounded(
            STAGE_UPLOAD,
            plan,
            self._aws_argv(
                "s3", "cp", str(staging), plan.job_uri + "/",
                "--recursive", "--only-show-errors",
            ),
            self.transport_timeout_s,
        )
        if proc.returncode != 0:
            raise BackendError(
                f"batch backend: uploading {plan.job_uri} failed "
                f"(aws s3 cp exit {proc.returncode}): {(proc.stderr or '').strip()}"
            )

    def _launch(self, plan: JobPlan) -> None:
        # `--region`/`--profile` are passed for the same reason `_aws` passes
        # them: the resolved config is the submission's identity, and every
        # transport call must run under it. Omitting them here let the launch
        # script fall back to its OWN default profile -- its *admin*
        # provisioning identity, which a day-to-day submitting host has no
        # credential for -- and the failure was neither a permission error nor
        # a refusal but a silently empty subnet list, surfacing several layers
        # later as `only 0 subnet/AZ(s) resolved, floor is 3`. That reads as
        # "the fleet is not provisioned" when the fleet was fine and the
        # submitter had simply asked as the wrong principal (#509). The layer's
        # own env file says as much -- its admin profile "can create the bucket
        # / launch template / SG", while "day-to-day launches use
        # --profile <submit>" -- so passing the resolved profile is what the
        # contract already asked for, not a new policy.
        #
        # No subprocess keywords here: `_default_runner` already applies
        # capture_output/text/check, and repeating them made every real
        # submission die with `TypeError: subprocess.run() got multiple values
        # for keyword argument 'capture_output'` -- after `_upload` had already
        # put the job document and inputs in the bucket. Every other call site
        # passes argv alone; this one is now uniform with them.
        # A refusal that names the layer's fleet-wide concurrency ceiling is
        # waited out, not propagated. The ceiling counts instances *other*
        # campaigns launched, so no choice of `-j` here can stay under it, and
        # letting it out of this method aborted a whole grid at the first
        # refusal: a 288-point run of `sim/reference-input-contract` at `-j 24`
        # died after 118 points with 170 never submitted, because one launch
        # out of twenty-four was told to come back later (#499). Every other
        # per-point degradation in this harness follows the rule `_write_log`
        # states -- "must degrade that one point rather than raising out of
        # run_grid and discarding every other point the grid already
        # completed" -- and a transient slot shortage has even less claim to
        # abort a grid than a lost log write does.
        argv = [
            str(self.config.provision_script),
            "launch",
            "--job",
            plan.job_id,
            "--apply",
            "--region",
            self.config.region,
            "--profile",
            self.config.profile,
        ]
        #
        # Each attempt is bounded by `launch_timeout_s`. A launch that times
        # out is NOT retried, ceiling or not: the script may have submitted the
        # job (and started spending) before it stalled, and this host cannot
        # tell. The `StageTimeout` propagates to `run_deck`, which fails the
        # point and says the outcome is ambiguous (#727).
        for attempt in range(1, LAUNCH_CEILING_ATTEMPTS + 1):
            proc = self._bounded(STAGE_LAUNCH, plan, argv, self.launch_timeout_s)
            if proc.returncode == 0:
                return
            stderr = (proc.stderr or "").strip()
            if not CEILING_REFUSAL_RE.search(stderr):
                raise BackendError(
                    f"batch backend: launching {plan.job_id} failed "
                    f"(exit {proc.returncode}): {stderr}"
                )
            if attempt == LAUNCH_CEILING_ATTEMPTS:
                raise BackendError(
                    f"batch backend: launching {plan.job_id} was refused for "
                    f"want of a concurrency slot on all {attempt} attempt(s) "
                    f"over ~{attempt * self.poll_interval_s:g}s; the layer's "
                    f"fleet-wide ceiling is held by other work, not by this "
                    f"run's -j. Last refusal: {stderr}"
                )
            time.sleep(self.poll_interval_s)

    def _status(self, plan: JobPlan, timeout_s: float | None = None) -> dict:
        """Read ``status.json`` once; ``{}`` when it cannot be read.

        Raises :class:`StageTimeout` when the read itself exceeds
        ``timeout_s`` (default :attr:`transport_timeout_s`); the polling loop
        treats that as one unanswered poll, since a status read is idempotent.
        """
        budget = self.transport_timeout_s if timeout_s is None else timeout_s
        proc = self._bounded(
            STAGE_STATUS,
            plan,
            self._aws_argv(
                "s3", "cp", plan.job_uri + "/status.json", "-", "--only-show-errors"
            ),
            budget,
        )
        if proc.returncode != 0:
            return {}
        try:
            return json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _staging(plan: JobPlan, rundir: Path) -> Path:
        """This job's private directory under the (possibly shared) rundir.

        One directory per job id, used for both halves of the transport: the
        upload's staged ``job.json``/``inputs/``, and the download's collected
        ``outputs/``. Job ids are unique per submission, so nothing another
        point is doing can be inside it.
        """
        return rundir / f".batch-{plan.job_id}"

    def _collect(
        self, plan: JobPlan, rundir: Path
    ) -> tuple[Path, subprocess.CompletedProcess]:
        """Download one job's outputs into a directory only that job writes.

        **The download target must be job-scoped, not the rundir itself.** A
        testbench that declares no ``raw_files`` gives every point of a grid
        the same ``rundir`` (``runner._run_phase``), points run concurrently at
        the CLI's own default ``-j``, and the job contract's output names are
        fixed (:data:`LOG_NAME`/:data:`RC_NAME`/:data:`HOST_NAME`). Collecting
        straight into the shared rundir therefore let one point's download
        overwrite those three files between another point's own download and
        its read of them -- silently recording a *different* PVT point's
        ngspice log, exit code and executing host (#507). The upload side was
        already isolated this way; this is the same isolation on the way back.

        Returns the directory the outputs landed in, which is what
        :meth:`run_deck` reads the three contract files from, together with
        the download's own result. A nonzero download is **not** raised here:
        whatever files did arrive are still evidence, and :meth:`run_deck`
        turns the failure into a failed point (#714).

        A download that exceeds :attr:`collect_timeout_s` is reported the same
        way, as a failed download whose stderr names the stage and budget: the
        files that had arrived when it was stopped stay where they landed and
        are still read and published as partial evidence (#727).
        """
        collected = self._staging(plan, rundir) / "outputs"
        collected.mkdir(parents=True, exist_ok=True)
        argv = self._aws_argv(
            "s3",
            "cp",
            plan.job_uri + "/outputs/",
            str(collected),
            "--recursive",
            "--only-show-errors",
        )
        try:
            proc = self._bounded(STAGE_COLLECT, plan, argv, self.collect_timeout_s)
        except StageTimeout as exc:
            proc = subprocess.CompletedProcess(
                argv, -1, exc.stdout, exc.describe()
            )
        return collected, proc

    def _publish(self, plan: JobPlan, collected: Path, rundir: Path) -> None:
        """Copy what the *deck* produced out of the job directory into rundir.

        The harness resolves a manifest's ``raw_files`` against the point's
        ``rundir`` (``runner.capture_raw_files``), so a collected waveform has
        to arrive there for a reduction to read it -- job isolation is for the
        three files *this module's* job command writes, not for the deck's own
        output.

        Two classes of collected file are deliberately **not** published, and
        both are about not overwriting something the harness owns:

        - the three fixed contract names (:data:`CONTRACT_OUTPUT_NAMES`), which
          are already carried back in the returned :class:`DeckRun` and whose
          shared-rundir collision is the whole point of this isolation. The
          point's log is written to ``corners/<record-id>/<run-id>.log`` by the
          runner, not from here;
        - the job's own **inputs**. ``job_command`` copies every file in the
          instance's work directory to ``$EDA_OUTPUT_DIR``, so the *relocated*
          deck comes back with the instance's PDK path substituted into it --
          and for a testbench without ``raw_files`` the rundir *is* the workdir
          holding ``<run-id>.spice``, the file the record's ``deck`` field names
          as the reproduction input. Publishing it would replace a deck composed
          for this host with one naming a path that exists only on a job
          instance.

        A copy that fails is not fatal here: a declared raw file that does not
        arrive is reported as missing by the record (``raw_files_missing``),
        which is a disclosed degradation of one point rather than a lost grid.
        """
        withheld = CONTRACT_OUTPUT_NAMES | set(plan.inputs)
        rundir.mkdir(parents=True, exist_ok=True)
        for source in sorted(collected.rglob("*")):
            relative = source.relative_to(collected)
            if relative.as_posix() in withheld:
                continue
            destination = rundir / relative
            try:
                if source.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            except OSError:
                continue

    @staticmethod
    def _stage_failure(exc: StageTimeout, started: float, consequence: str) -> DeckRun:
        """A transport stage that timed out before the job could be awaited.

        Reported as an *execution failure*, not a simulator timeout: the deck
        may never have run, and ``timed_out`` would have the point's log say
        ``TIMEOUT after <--timeout>s``, which is a claim about ngspice. The
        partial transport output is diagnostics, not simulator output, so it
        goes in ``detail`` (and from there the point's message) rather than in
        ``output``, where the measurement parser would read it.
        """
        return DeckRun(
            output="",
            returncode=-1,
            seconds=time.monotonic() - started,
            execution_failed=True,
            detail=f"{exc.describe()}; {consequence}",
        )

    # -- the backend interface ------------------------------------------- #

    def run_deck(
        self,
        deck_path: Path,
        rundir: Path,
        timeout_s: int,
        env: Mapping[str, str] | None = None,
    ) -> DeckRun:
        """Submit, wait, collect. ``env`` is deliberately ignored.

        A local OpenMP budget divides *this* host between *this* host's
        workers (``sim/harness/omp.py``); a job instance's thread budget is
        the layer's own ``cores_per_job``/``EDA_JOB_CONCURRENCY``, so
        forwarding the submitting host's pin would misdescribe the run. The
        record says which of the two applied -- see ``report._execution_lines``.
        """
        if not self.apply:
            raise BackendError(
                "batch backend: refusing to submit without --batch-apply. "
                "Run `sim/run_corners.py <experiment> --backend batch` first to "
                "print the submission plan, then re-run with --batch-apply."
            )
        plan = self.plan_deck(deck_path, timeout_s)
        self.jobs.append(plan)
        staging = self._staging(plan, rundir)
        started = time.monotonic()
        # Upload and launch are bounded per command (`_bounded`). A timeout in
        # either is a failed point, never an exception out of `run_grid`
        # (#727). Neither is retried here: a re-upload is pointless without a
        # launch, and a launch that timed out may already have submitted.
        try:
            self._upload(plan, staging)
        except StageTimeout as exc:
            return self._stage_failure(
                exc, started, "the job was not launched"
            )
        try:
            self._launch(plan)
        except StageTimeout as exc:
            return self._stage_failure(
                exc, started,
                "the launch outcome is unknown -- the job may have been "
                "submitted -- so it was not relaunched; check the layer for "
                f"job {plan.job_id} before resubmitting this point",
            )

        # The polling budget is the deck's own timeout plus the provisioning
        # grace, measured from submission start on the monotonic clock. Each
        # status read is bounded by the smaller of its own budget and what is
        # left of this one, and so is each sleep, so the loop cannot overrun
        # the deadline by more than one command's reap time.
        deadline = started + timeout_s + self.provision_grace_s
        state = ""
        status: dict = {}
        status_timeouts = 0
        last_status_timeout: StageTimeout | None = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                status = self._status(
                    plan, min(self.transport_timeout_s, remaining)
                )
            except StageTimeout as exc:
                # One unanswered poll. A status read is idempotent, so it is
                # simply re-asked until the polling budget runs out.
                status_timeouts += 1
                last_status_timeout = exc
                status = {}
            state = str(status.get("state") or "")
            if state in TERMINAL_STATES:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.poll_interval_s, remaining))

        seconds = time.monotonic() - started
        host = str(status.get("instance_id") or "")

        if state not in TERMINAL_STATES:
            detail = (
                f"job {plan.job_id} never reached a terminal state "
                f"(last state {state or 'unknown'!r}) within "
                f"{timeout_s}s + {self.provision_grace_s:g}s provisioning grace"
            )
            if status_timeouts:
                detail += (
                    f"; {status_timeouts} {STAGE_STATUS} read(s) timed out, "
                    f"the last: {last_status_timeout.describe()}"
                )
            return DeckRun(
                output="",
                returncode=-1,
                seconds=seconds,
                host=host,
                timed_out=True,
                detail=detail,
            )

        # Read this job's own log/rc/host out of ITS OWN collect directory. A
        # concurrent point collecting into the same rundir writes only inside
        # its own `.batch-<job-id>/`, so nothing it does can reach these three
        # reads (#507).
        collected, download = self._collect(plan, rundir)
        log_path = collected / LOG_NAME
        output = log_path.read_text() if log_path.is_file() else ""
        host_path = collected / HOST_NAME
        if host_path.is_file():
            host = host_path.read_text().strip() or host
        rc_path = collected / RC_NAME
        try:
            returncode = int((rc_path.read_text() or "").strip())
        except (OSError, ValueError):
            returncode = -1
        # Whatever the deck itself wrote belongs in the rundir the harness
        # resolves `raw_files` against -- for every terminal state, since a
        # timed-out or failed point's partial output is still evidence.
        self._publish(plan, collected, rundir)

        # A download that exited nonzero is a known-incomplete collection: the
        # point must not read as a success just because the files that did
        # arrive happen to hold every measurement (#714). The files stay.
        collect_failed = download.returncode != 0
        collect_detail = ""
        if collect_failed:
            err = " ".join((download.stderr or "").split())
            collect_detail = (
                f"job {plan.job_id} output collection failed "
                f"(exit {download.returncode})" + (f": {err[:500]}" if err else "")
            )
            if not (log_path.is_file() or rc_path.is_file()):
                collect_detail += "; no job outputs were downloaded"

        def _compose(detail: str) -> str:
            return f"{detail}; {collect_detail}" if collect_detail else detail

        if state == "timeout":
            return DeckRun(
                output=output,
                returncode=returncode,
                seconds=seconds,
                host=host,
                timed_out=True,
                detail=_compose(
                    f"job {plan.job_id} hit the layer's {timeout_s}s budget"
                ),
            )
        if state in ("failed", "interrupted"):
            return DeckRun(
                output=output,
                returncode=returncode if returncode else 1,
                seconds=seconds,
                host=host,
                execution_failed=True,
                detail=_compose(
                    f"job {plan.job_id} ended {state}"
                    + (f": {status['detail']}" if status.get("detail") else "")
                ),
            )
        return DeckRun(
            output=output,
            returncode=returncode,
            seconds=seconds,
            host=host,
            execution_failed=collect_failed,
            detail=collect_detail or f"job {plan.job_id}",
        )
