"""Capability probe: does the resolved ngspice expand this PDK's
nonlinear-capacitance moscap family without emitting a malformed element?

The moscap advisory in :mod:`sim.harness.runner` used to key on the leading
``ngspice-<N>`` version token (#268). That stopped being able to answer the
question the moment the upstream fix shipped in a *point* build: the patched
build prints the same ``ngspice-47`` banner token as the broken one (both
builds on this repo's reference host were compared byte-for-byte,
2026-11-14, #926), so no amount of parsing ``ngspice --version`` can
separate "known-bad" from "fixed". On a patched host every point of an
affected campaign completed normally while ``--check-env`` and the run path
still predicted total failure -- the warning stated the opposite of what
happened, in the operator's own view of a passing campaign.

The property the harness needs is a **capability** of the resolved binary:
can it expand the family cleanly? This module asks that directly. It
composes a few-line deck that instantiates ``cap_nmos_03v3`` the way the
real DUTs do -- ``m=1`` on the instance line, the construct measured
(#926, 2026-11-14) to make the broken build emit ``unknown parameter (eN)``
-- runs it through the same :class:`sim.harness.execution.LocalBackend`
invocation the grid's points use (so the shared ``.spiceinit``/``wnflag``
pre-netlist configuration is in place when the netlist is read, #755), and
classifies the output into three distinct verdicts:

- ``True``  -- the probe deck loaded: this build does not emit the malformed
  element. This is a statement about loading only; it says nothing about
  the *values* the build returns, which is #932's question and is
  deliberately left unanswered here.
- ``False`` -- the output carries the regression signature
  (``unknown parameter``, case-insensitive; the measured output also
  matches ``runner._ERROR_RE``'s ``Error on line ...`` form). The broken
  build also exits non-zero, so ``returncode`` corroborates -- but a
  non-zero exit alone is not a verdict, since ngspice's exit status is not
  known to be reliable (see ``execution.DeckRun``).
- ``None``  -- inconclusive: no ``ngspice`` on PATH, the probe timed out,
  or the output carried neither the success marker nor the failure
  signature. Callers abstain rather than guess, the same convention
  ``execution.simulator_of`` and ``siminit.init_of`` follow for provenance.

Like the advisory it feeds, this never hard-blocks: a host whose only build
fails the probe must still be able to run and see the real per-point error.

The verdict is memoized per process
(:func:`functools.lru_cache`, keyed on the resolved executable and the PDK
paths), so a run probes at most once regardless of grid size -- the probe
must never add a simulator invocation per grid point. There is deliberately
no on-disk cache: a binary rebuilt at the same path would be answered from
a stale entry, and a stale ``False`` is exactly the false warning this
module removes.

``SIM_MOSCAP_PROBE_RESULT`` (``loads`` / ``malformed`` / ``unknown``)
overrides the live probe, mirroring ``omp.LDD_OVERRIDE_ENV``: CI is headless
with no ngspice and no PDK, so the override is the only way every branch is
testable. An unrecognized value abstains rather than guessing.
"""

from __future__ import annotations

import functools
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from . import execution, runner

__all__ = [
    "MARKER",
    "PROBE_OVERRIDE_ENV",
    "nested_moscap_loads",
    "probe_deck",
    "verdict_of",
]

#: What the deck's ``.control`` block echoes after a successful ``op``. Its
#: presence in the output is the only proof the deck loaded -- a clean exit
#: code is not (ngspice's exit status is not known to be reliable).
MARKER = "gf180-pll-moscap-probe-ok"

#: Test override for the live probe -- ``loads`` / ``malformed`` /
#: ``unknown``, mirroring ``omp.LDD_OVERRIDE_ENV`` so headless CI can
#: exercise every branch with no ngspice and no PDK.
PROBE_OVERRIDE_ENV = "SIM_MOSCAP_PROBE_RESULT"

_DEFAULT_TIMEOUT_S = 60

#: The regression signature: the broken build emits a malformed internal
#: element named with a trailing parameter token it cannot resolve.
_MALFORMED_ELEMENT_RE = re.compile(r"unknown parameter", re.IGNORECASE)

#: The accepted ``PROBE_OVERRIDE_ENV`` values, mapped to the verdict each
#: stands for. Anything else -- including garbage -- abstains.
_OVERRIDE_VERDICTS: dict[str, bool | None] = {
    "loads": True,
    "malformed": False,
    "unknown": None,
}


def _deck_text(design_include: Path, model_lib: Path) -> str:
    return (
        "* gf180-pll moscap capability probe (#926): does this ngspice\n"
        "* expand the PDK's nonlinear-capacitance moscap family without\n"
        "* emitting a malformed internal element (\"unknown parameter (eN)\")?\n"
        f'.include "{design_include}"\n'
        f'.lib "{model_lib}" moscap_typical\n'
        ".subckt probe_wrap vdd gnd\n"
        "XCDEC1 vdd gnd cap_nmos_03v3 c_width=50u c_length=50u m=1\n"
        ".ends\n"
        "x1 nprobe 0 probe_wrap\n"
        "v1 nprobe 0 1\n"
        ".control\n"
        "op\n"
        f"echo {MARKER}\n"
        "quit\n"
        ".endc\n"
        ".end\n"
    )


def probe_deck(pdk) -> str:
    """The probe deck text for a resolved PDK.

    The instance mirrors ``design/netlist/vco.spice``'s decoupling-cap line
    -- same family, same geometry, and the ``m=1`` multiplier -- wrapped in
    a ``.subckt`` so the deck is a superset of the construct any committed
    DUT composes. The ``m=1`` is load-bearing, not stylistic: a deck
    without it loads cleanly on the broken build (measured, #926), so a
    probe built that way would silence the warning permanently.
    """
    return _deck_text(pdk.design_include, pdk.model_lib)


def verdict_of(output: str) -> bool | None:
    """Classify probe output: ``False`` on the regression signature, ``True``
    on the success marker, ``None`` when it carries neither.

    The signature is checked first and wins: an output that somehow carries
    both is a build that emitted the malformed element, whatever else it
    printed.
    """
    text = output or ""
    if _MALFORMED_ELEMENT_RE.search(text):
        return False
    if MARKER in text:
        return True
    return None


def nested_moscap_loads(
    pdk, *, timeout_s: int = _DEFAULT_TIMEOUT_S, env: Mapping[str, str] | None = None
) -> bool | None:
    """Can the ngspice the harness resolves expand the PDK's nonlinear
    moscap family without emitting a malformed element?

    ``True`` / ``False`` / ``None`` (inconclusive) -- see the module
    docstring for what each verdict licenses and what it deliberately does
    not. Memoized per process on the resolved executable and PDK paths, so
    repeated calls (a campaign calling this once per run, ``--check-env``,
    a grid) never re-probe; a grid of any size costs exactly one probe.
    """
    environ = os.environ if env is None else env
    override = environ.get(PROBE_OVERRIDE_ENV)
    if override is not None:
        return _OVERRIDE_VERDICTS.get(override.strip().lower())
    return _loads_cached(
        runner.ngspice_executable(),
        str(pdk.design_include),
        str(pdk.model_lib),
        timeout_s,
    )


@functools.lru_cache(maxsize=None)
def _loads_cached(
    executable: str | None, design_include: str, model_lib: str, timeout_s: int
) -> bool | None:
    return _run_probe(executable, Path(design_include), Path(model_lib), timeout_s)


def _run_probe(
    executable: str | None, design_include: Path, model_lib: Path, timeout_s: int
) -> bool | None:
    if not executable:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rundir = Path(tmp)
            deck_path = rundir / "moscap_probe.spice"
            deck_path.write_text(_deck_text(design_include, model_lib))
            backend = execution.LocalBackend(executable)
            run = backend.run_deck(deck_path, rundir, timeout_s)
    except (OSError, execution.BackendError):
        # The probe's own plumbing failed -- that is not a verdict about
        # the binary's capability.
        return None
    if run.timed_out:
        # A probe that could not finish within its budget is inconclusive,
        # not a failure -- partial output may carry anything.
        return None
    return verdict_of(run.output)
