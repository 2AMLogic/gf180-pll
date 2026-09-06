"""ngspice internal-thread budgeting for the corner runner.

`sim/lib/simenv.sh` already carries this repository's diagnosis of ngspice
**self-oversubscription** (#146 -> #241 -> #244): on hosts where `ngspice`
links an OpenMP runtime, each `ngspice -b` process spawns several OS threads
of its own for BSIM model evaluation, *independently of and on top of* any
process-level fan-out the caller does. A campaign that runs `J` ngspice
processes in parallel on an `N`-core host therefore demands `J x T` threads,
not `J` -- and when `J x T` far exceeds `N`, every point slows down together
and long transients start hitting their per-point timeouts.

That fix only ever reached the **shell** campaign path (`sim/lib/simenv.sh`'s
`simenv_apply_omp_pin`, opted into by individual `run.sh` scripts). The
Python harness under `sim/harness/` -- which is what `sim/run_corners.py`
drives, and therefore what every migrated campaign now runs through -- had no
equivalent, so `run_corners.py -j8` on an 8-core host requested 64 threads for
8 cores. This module is that missing half.

Why this budgets rather than pins to 1
--------------------------------------

`simenv_apply_omp_pin` pins to a literal `1` thread, and is deliberately
opt-in per campaign, because a shell `run.sh` does not know how many sibling
processes the campaign will fan out to -- so `1` is the only value it can
choose that is safe at any fan-out, and forcing it on a `-j1`-style caller
would needlessly serialize model evaluation for zero benefit.

The harness does not have that limitation: :func:`sim.harness.runner.run_grid`
is told its own `jobs` count. So instead of pinning to 1 it divides the
machine between its own workers -- `max(1, cpu_count // jobs)` threads each,
so total thread demand lands at or under the core count. The two ends of that
rule are the important ones:

- `jobs == 1`: no fan-out exists, so no self-oversubscription is possible and
  **nothing is exported** -- a single-point or serial run keeps whatever
  threading the build does natively, exactly as before this module existed.
- `jobs >= cpu_count`: the budget floors at 1, reproducing
  `simenv_apply_omp_pin`'s behavior for the case it was written for.

Detection and both failure directions are borrowed from `simenv.sh` verbatim
in substance, including the `SIMENV_NGSPICE_LDD_OUTPUT` test override, so the
shell and Python halves can never disagree about whether a given build is
internally threaded:

- an OpenMP-linked build is a *static* property of the installed binary, so it
  is answered from `ldd` output rather than by spawning a throwaway simulation;
- an inconclusive probe (no `ngspice` on PATH, no `ldd` -- e.g. macOS, a build
  that threads through some other mechanism) exports **nothing** rather than
  guessing;
- a caller who set `OMP_NUM_THREADS` and/or `OMP_THREAD_LIMIT` explicitly is
  always respected, each variable defaulted independently (#244: the two are
  not interchangeable -- `OMP_NUM_THREADS` only seeds `nthreads-var`, which an
  in-process `omp_set_num_threads()` may overwrite, while `OMP_THREAD_LIMIT`
  seeds the hard per-process ceiling `thread-limit-var` that made the pin
  actually stick on this repository's closed-loop decks).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Mapping

__all__ = [
    "LDD_OVERRIDE_ENV",
    "OMP_VARS",
    "ngspice_openmp_linked",
    "omp_env_overrides",
    "thread_budget",
]

# Same three runtime SONAMEs `simenv_ngspice_openmp_linked` greps for.
_OPENMP_RUNTIME_RE = re.compile(r"libgomp|libiomp|libomp\.")

#: Test override for the live `ldd` probe -- set it to literal `ldd` output to
#: exercise the detection logic without an OpenMP-linked ngspice on the host.
#: Deliberately the same variable name `sim/lib/simenv.sh` uses, so one export
#: drives both implementations.
LDD_OVERRIDE_ENV = "SIMENV_NGSPICE_LDD_OUTPUT"

#: The two OpenMP environment variables this module may default, in the order
#: they are reported. Each is defaulted independently (#244).
OMP_VARS = ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT")

_NGSPICE = "ngspice"


def ngspice_openmp_linked(env: Mapping[str, str] | None = None) -> bool:
    """True if the `ngspice` on PATH appears to link an OpenMP runtime.

    False when it does not, when `ngspice` is not on PATH, or when the probe
    cannot be performed at all (no `ldd`) -- "cannot tell" and "no" are
    deliberately collapsed, because both must lead to the same leave-the-
    environment-alone behavior.
    """
    environ = os.environ if env is None else env
    override = environ.get(LDD_OVERRIDE_ENV)
    if override is not None:
        return bool(_OPENMP_RUNTIME_RE.search(override))

    exe = shutil.which(_NGSPICE)
    if not exe or not shutil.which("ldd"):
        return False
    try:
        out = subprocess.run(
            ["ldd", exe], capture_output=True, text=True, check=False, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(_OPENMP_RUNTIME_RE.search(out))


def thread_budget(jobs: int, cpu_count: int | None = None) -> int | None:
    """Threads to allow each ngspice worker, or ``None`` for "no budget".

    ``None`` means *leave the environment alone*; it is returned for a serial
    run (``jobs <= 1``), where the harness runs one ngspice at a time and
    internal threading costs nothing it has to share.
    """
    if jobs <= 1:
        return None
    cpus = os.cpu_count() if cpu_count is None else cpu_count
    if not cpus or cpus < 1:
        cpus = 1
    return max(1, cpus // jobs)


def omp_env_overrides(
    jobs: int,
    env: Mapping[str, str] | None = None,
    cpu_count: int | None = None,
) -> dict[str, str]:
    """The `OMP_*` variables to add to an ngspice subprocess's environment.

    Empty dict means "change nothing" -- the caller should then pass no `env`
    override at all rather than a copy of `os.environ`, so ambient behavior is
    bit-for-bit unchanged.
    """
    budget = thread_budget(jobs, cpu_count=cpu_count)
    if budget is None:
        return {}
    if not ngspice_openmp_linked(env=env):
        return {}
    environ = os.environ if env is None else env
    return {var: str(budget) for var in OMP_VARS if not environ.get(var)}
