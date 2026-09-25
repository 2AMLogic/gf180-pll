"""Where one composed deck's ``ngspice -b`` invocation actually runs.

Until #496 the harness had exactly one answer: a local ``subprocess.run``,
fanned out across a ``ThreadPoolExecutor`` by :func:`sim.harness.runner.run_grid`
and budgeted against the local core count by :mod:`sim.harness.omp`. That is
the right answer on a workstation and the *only* answer on a host with no
execution layer behind it -- but it is also why this repo's 45-point
closed-loop campaigns have no records: the hosts the agent fleet dispatches
onto are shared, and a 45-point closed-loop transient grid is not something
they may launch.

This module is the seam that makes "where" a choice instead of an assumption.
It is deliberately the *narrowest* seam that does the job:

- A backend is handed **one already-composed, self-contained deck** and a
  working directory, and returns what ngspice printed plus how it exited.
  Everything else -- deck composition, measurement parsing, optional/required
  classification, raw-file capture, the campaign's ``derive_point`` reduction,
  record minting, the checks -- stays exactly where it was, backend-agnostic,
  and is therefore identical whichever backend ran the point. A record minted
  through a remote backend is not a *different kind* of record.
- The deck is self-describing: ``compose_deck`` writes every dependency it has
  as an absolute ``.include``/``.lib`` path, so a backend that has to ship the
  point somewhere else can discover exactly what to ship by reading the deck,
  with no second channel from the manifest.

Per-point attribution
---------------------
:class:`DeckRun` carries ``host``: the machine that actually executed this
deck. Under the local backend that is this host for every point and the
record says so once. Under an off-host backend it varies point to point, which
is precisely the single-host assumption ``sim/README.md``'s Environment
provenance used to bake in -- so it is carried per point, from the backend
that knows it, rather than sampled once at record time from whichever host
happened to *mint* the record. See ``report._execution_lines``.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

NGSPICE = "ngspice"

#: ``.include "<path>"`` / ``.inc "<path>"`` -- the form ``compose_deck``
#: writes for the PDK's design include, the DUT export, and the stimulus
#: fragment. Quoted and unquoted are both accepted because a hand-written
#: fragment may use either, and a backend that has to relocate a deck must
#: not silently miss a dependency over a quoting style.
INCLUDE_RE = re.compile(r'^\s*\.inc(?:lude)?\s+"?([^"\s]+)"?\s*$', re.IGNORECASE)

#: ``.lib "<path>" <section>`` -- the model-library card, one per corner
#: section. The section name is not a path and is deliberately not captured.
LIB_RE = re.compile(r'^\s*\.lib\s+"?([^"\s]+)"?\s+(\S+)\s*$', re.IGNORECASE)


class BackendError(RuntimeError):
    """A backend could not run the deck for a reason that is not the deck's
    fault -- an unresolvable configuration, a transport failure, a refused
    submission. Distinct from "ngspice ran and the point failed", which is an
    ordinary :class:`DeckRun` with a non-zero ``returncode``."""


@dataclass(frozen=True)
class DeckRun:
    """One deck's execution, as the runner needs to see it.

    ``output`` is the combined stdout/stderr text the measurement parser reads
    and the per-corner ``.log`` file is written from -- the same bytes
    whichever backend produced them.

    ``host`` names the machine that ran *this* deck. It is never inferred by
    the caller: a backend that cannot determine it reports the empty string,
    which provenance renders as "unattributed" rather than silently
    substituting the minting host.
    """

    output: str
    returncode: int
    seconds: float
    host: str = ""
    timed_out: bool = False
    #: Free-text detail a backend wants preserved on an unsuccessful run
    #: (a job id, a status document's own message). Surfaced in the point's
    #: ``message`` so a failed remote point is diagnosable from the record.
    detail: str = ""


def deck_dependencies(deck_text: str) -> list[str]:
    """Every file path ``deck_text`` names in a ``.include``/``.lib`` card.

    Order-preserving and de-duplicated. This is what a relocating backend has
    to ship alongside the deck; a backend that runs in place ignores it.

    Only *paths* are returned -- a ``.lib``'s section name is a selector
    inside the named file, not a second file.
    """
    seen: dict[str, None] = {}
    for line in deck_text.splitlines():
        match = INCLUDE_RE.match(line)
        if match:
            seen.setdefault(match.group(1), None)
            continue
        match = LIB_RE.match(line)
        if match:
            seen.setdefault(match.group(1), None)
    return list(seen)


class LocalBackend:
    """``ngspice -b <deck>`` as a child process of this harness.

    Byte-for-byte the invocation every committed record was taken through:
    same argv, same ``cwd``, same ``capture_output``/``text``, same
    ``stdout + "\\n" + stderr`` join, same ambient-environment rule (an empty
    ``env`` override passes ``env=None`` rather than a reconstructed
    ``os.environ``, which is not equivalent on every libc). Nothing about the
    local path changed when this seam was introduced, and nothing about it
    should: it is the reference behaviour every other backend is compared to.
    """

    name = "local"

    def __init__(self, executable: str = NGSPICE) -> None:
        self.executable = executable

    def describe(self) -> dict:
        return {"backend": self.name}

    def prepare(self, points: int) -> None:  # noqa: D401 - no-op hook
        """Nothing to set up for a local run."""

    def run_deck(
        self,
        deck_path: Path,
        rundir: Path,
        timeout_s: int,
        env: Mapping[str, str] | None = None,
    ) -> DeckRun:
        child_env = {**os.environ, **env} if env else None
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [self.executable, "-b", str(deck_path)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=rundir,
                check=False,
                env=child_env,
            )
        except subprocess.TimeoutExpired:
            return DeckRun(
                output="",
                returncode=-1,
                seconds=time.monotonic() - started,
                host=socket.gethostname(),
                timed_out=True,
            )
        return DeckRun(
            output=proc.stdout + "\n" + proc.stderr,
            returncode=proc.returncode,
            seconds=time.monotonic() - started,
            host=socket.gethostname(),
        )


#: ngspice's own closing banner -- ``ngspice-46 done`` -- printed by the binary
#: that actually ran the deck. This is the only statement of the simulator
#: version that travels *with* the measurement: everything else the harness
#: knows about ``ngspice`` was resolved on the submitting host, which under an
#: off-host backend never ran the deck at all (#509).
SIMULATOR_RE = re.compile(r"^\s*(ngspice-\d+)\s+done\s*$", re.IGNORECASE | re.MULTILINE)


def simulator_of(output: str) -> str:
    """The ngspice version that produced ``output``, or ``""`` if it did not say.

    Reads the *last* banner in the text: a deck's output is one invocation, but
    a transport that concatenates stdout and stderr (or a future backend that
    retries) may carry more than one, and the run that produced the
    measurements is the last one.

    Abstains rather than guessing. An empty string means "this output does not
    name a simulator", which provenance renders as unattributed -- never as the
    recording host's own version, which is exactly the substitution this
    function exists to stop.
    """
    found = SIMULATOR_RE.findall(output or "")
    return found[-1].lower() if found else ""


@dataclass
class HostTally:
    """Which hosts ran a grid's points, and how many each ran.

    Assembled from the per-point ``host`` fields rather than from the backend,
    so it reports what actually happened (including points a backend could not
    attribute) instead of what was intended.

    Also used, unchanged, to tally the **executing simulator** per point
    (:func:`simulator_of`): the question has the identical shape -- "which
    distinct values ran how many points, and how many were unattributed" --
    and giving it a second, near-identical class would only invite the two to
    drift apart.
    """

    counts: dict[str, int] = field(default_factory=dict)

    def add(self, host: str) -> None:
        key = host or ""
        self.counts[key] = self.counts.get(key, 0) + 1

    @property
    def distinct(self) -> int:
        """Number of *named* hosts. Unattributed points are not a host."""
        return len([h for h in self.counts if h])

    def as_dict(self) -> dict:
        """``{host: points}``, unattributed points under the empty key."""
        return dict(sorted(self.counts.items()))
