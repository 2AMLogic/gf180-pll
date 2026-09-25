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

#: Default ``aws`` CLI profile name. A profile *name* is not a secret -- the
#: credential it resolves to lives in the operator's own AWS config, and a
#: host without that profile gets a clean CLI error naming it.
DEFAULT_PROFILE = "batch-runner-submit"

DEFAULT_JOBS_PREFIX = "jobs"


def _default_runner(argv: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
    """Run one transport command, capturing its output.

    **``capture_output`` / ``text`` / ``check`` are this function's to set, and
    a call site must not repeat them** -- ``subprocess.run`` rejects a
    duplicated keyword with ``TypeError: got multiple values for keyword
    argument``, which is a submission that dies *after* its inputs are already
    uploaded. See the regression test in ``sim/tests/test_execution_backend.py``
    (``StrictRunnerSignatureTests``), which applies these keyword rules to
    every call site the submission path makes.
    """
    return subprocess.run(
        list(argv), capture_output=True, text=True, check=False, **kwargs
    )


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
    ) -> None:
        self.pdk_variant_dir = Path(pdk_variant_dir)
        self.pdk_variant = pdk_variant
        self.config = config if config is not None else resolve_config()
        self.apply = apply
        self.cores_per_job = cores_per_job
        self.poll_interval_s = poll_interval_s
        self.provision_grace_s = provision_grace_s
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

    def _aws(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        argv = [
            "aws",
            "--region",
            self.config.region,
            "--profile",
            self.config.profile,
            *args,
        ]
        return self._run(argv, **kwargs)

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
        proc = self._aws(
            "s3", "cp", str(staging), plan.job_uri + "/", "--recursive", "--only-show-errors"
        )
        if proc.returncode != 0:
            raise BackendError(
                f"batch backend: uploading {plan.job_uri} failed "
                f"(aws s3 cp exit {proc.returncode}): {(proc.stderr or '').strip()}"
            )

    def _launch(self, plan: JobPlan) -> None:
        # No subprocess keywords here: `_default_runner` already applies
        # capture_output/text/check, and repeating them made every real
        # submission die with `TypeError: subprocess.run() got multiple values
        # for keyword argument 'capture_output'` -- after `_upload` had already
        # put the job document and inputs in the bucket. Every other call site
        # passes argv alone; this one is now uniform with them.
        proc = self._run(
            [
                str(self.config.provision_script),
                "launch",
                "--job",
                plan.job_id,
                "--apply",
            ]
        )
        if proc.returncode != 0:
            raise BackendError(
                f"batch backend: launching {plan.job_id} failed "
                f"(exit {proc.returncode}): {(proc.stderr or '').strip()}"
            )

    def _status(self, plan: JobPlan) -> dict:
        proc = self._aws(
            "s3", "cp", plan.job_uri + "/status.json", "-", "--only-show-errors"
        )
        if proc.returncode != 0:
            return {}
        try:
            return json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {}

    def _collect(self, plan: JobPlan, rundir: Path) -> None:
        rundir.mkdir(parents=True, exist_ok=True)
        self._aws(
            "s3",
            "cp",
            plan.job_uri + "/outputs/",
            str(rundir),
            "--recursive",
            "--only-show-errors",
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
        staging = rundir / f".batch-{plan.job_id}"
        started = time.monotonic()
        self._upload(plan, staging)
        self._launch(plan)

        deadline = started + timeout_s + self.provision_grace_s
        state = ""
        status: dict = {}
        while time.monotonic() < deadline:
            status = self._status(plan)
            state = str(status.get("state") or "")
            if state in TERMINAL_STATES:
                break
            time.sleep(self.poll_interval_s)

        seconds = time.monotonic() - started
        host = str(status.get("instance_id") or "")

        if state not in TERMINAL_STATES:
            return DeckRun(
                output="",
                returncode=-1,
                seconds=seconds,
                host=host,
                timed_out=True,
                detail=(
                    f"job {plan.job_id} never reached a terminal state "
                    f"(last state {state or 'unknown'!r}) within "
                    f"{timeout_s}s + {self.provision_grace_s:g}s provisioning grace"
                ),
            )

        self._collect(plan, rundir)
        log_path = rundir / LOG_NAME
        output = log_path.read_text() if log_path.is_file() else ""
        host_path = rundir / HOST_NAME
        if host_path.is_file():
            host = host_path.read_text().strip() or host
        rc_path = rundir / RC_NAME
        try:
            returncode = int((rc_path.read_text() or "").strip())
        except (OSError, ValueError):
            returncode = -1

        if state == "timeout":
            return DeckRun(
                output=output,
                returncode=returncode,
                seconds=seconds,
                host=host,
                timed_out=True,
                detail=f"job {plan.job_id} hit the layer's {timeout_s}s budget",
            )
        if state in ("failed", "interrupted"):
            return DeckRun(
                output=output,
                returncode=returncode if returncode else 1,
                seconds=seconds,
                host=host,
                detail=(
                    f"job {plan.job_id} ended {state}"
                    + (f": {status['detail']}" if status.get("detail") else "")
                ),
            )
        return DeckRun(
            output=output,
            returncode=returncode,
            seconds=seconds,
            host=host,
            detail=f"job {plan.job_id}",
        )
