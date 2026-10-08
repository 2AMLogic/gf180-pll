"""Compatibility seam for the period-jitter ``run.py`` campaign runners (#712).

Four committed runners under ``sim/period-jitter/`` (``in-band-bound``,
``random-bound``, ``sid-trajectory``, ``isf-bringup``) predate the harness
execution layer and used to launch ``ngspice -b`` themselves and build their own
provenance dictionaries. This module lets them delegate both jobs to the
harness without changing what they write:

* :func:`run_deck_files` writes ``deck.sp`` and executes it through an
  execution backend (:class:`harness.execution.LocalBackend` by default), so a
  runner's deck execution goes through the backend interface.
* :func:`runner_environment`, :func:`sid_environment` and :func:`ngspice_banner`
  produce the *runner-shaped* provenance dictionaries that are already committed
  under each campaign's ``results/``. They are projections of the harness's own
  provenance sources (``harness.report.environment`` fields: simulator banner,
  interpreter version, UTC time; ``harness.report._git``) and deliberately keep
  the legacy key names, so no committed record changes shape.

Nothing here re-measures anything or alters a result.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from . import execution, report

#: The deck file name every period-jitter runner has always used.
DECK_NAME = "deck.sp"


def run_deck_files(
    deck: str,
    work: Path,
    *,
    backend=None,
    timeout_s: float | None = None,
) -> "execution.DeckRun":
    """Write ``deck`` to ``work/deck.sp`` and run it through ``backend``.

    ``work`` is the run directory (created if needed). The deck path handed to
    the backend is absolute, so relocating backends can ship it.
    """
    work.mkdir(parents=True, exist_ok=True)
    deck_path = work / DECK_NAME
    deck_path.write_text(deck)
    chosen = backend if backend is not None else execution.LocalBackend()
    return chosen.run_deck(deck_path.resolve(), work.resolve(), timeout_s)  # type: ignore[arg-type]


def _ngspice_v() -> str:
    """stdout of ``ngspice -v`` ("" if the binary is absent)."""
    try:
        return subprocess.run(
            [execution.NGSPICE, "-v"], capture_output=True, text=True
        ).stdout
    except OSError:
        return ""


def ngspice_banner(style: str = "version-token") -> str:
    """The simulator string a runner records, in that runner's own legacy form.

    ``version-token``: the ``ngspice-NN`` token (random-bound, in-band-bound).
    ``second-line``: line 2 of ``ngspice -v``, stripped (sid-trajectory).
    ``second-line-squeezed``: line 2 with whitespace collapsed (isf-bringup).
    """
    out = _ngspice_v()
    lines = out.splitlines()
    if style == "version-token":
        return next((ln.strip("* ").split(" :")[0] for ln in lines if "ngspice-" in ln), "")
    if style == "second-line":
        return lines[1].strip() if len(lines) > 1 else out.strip()
    if style == "second-line-squeezed":
        return " ".join(lines[1].split()) if len(lines) > 1 else out.strip()
    raise ValueError(f"unknown ngspice banner style {style!r}")


def _git(repo: Path, *args: str) -> str:
    return report._git(*args, cwd=repo)


def runner_environment(models, repo: Path, dirty_pathspec: tuple[str, ...]) -> dict:
    """The random-bound / in-band-bound ``environment`` record, key for key.

    ``dirty_pathspec`` is per-campaign (the two runners have always differed);
    tracked files only, so a campaign's own ``results/`` and ``logs/`` written
    mid-grid do not mark later points dirty.
    """
    return {
        "ngspice": ngspice_banner("version-token"),
        "pdk_models": str(models),
        "repo_head": _git(repo, "rev-parse", "--short=8", "HEAD"),
        "repo_dirty": bool(_git(
            repo, "status", "--porcelain", "--untracked-files=no", "--", *dirty_pathspec)),
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def sid_environment(models, repo: Path) -> dict:
    """The sid-trajectory ``environment`` record, key for key."""
    return {
        "ngspice": ngspice_banner("second-line"),
        "pdk_models": str(models),
        "repo_head": _git(repo, "rev-parse", "--short", "HEAD"),
        "vco_netlist_sha1": _git(repo, "hash-object", str(repo / "design" / "netlist" / "vco.spice")),
        "python": sys.version.split()[0],
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
