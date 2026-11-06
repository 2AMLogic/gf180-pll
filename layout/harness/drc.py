"""Drive the gf180mcu open-PDK KLayout DRC deck and normalise its result.

The deck itself is the PDK's, run unmodified. In the pinned tree
(``libs.tech/klayout/tech/drc/``) there is no ``run_drc.py``: the deck
``gf180mcu.drc`` is run directly as ``klayout -b -r gf180mcu.drc -rd ...``.
An older tree's ``drc/run_drc.py`` (which generates ``main.drc`` and hands it
to ``klayout -b -r``) is still driven when that file is present. This module adds
only the three things an automated gate needs and the PDK runner does not
give you:

* a **normalised verdict** (``clean`` / ``violations`` / ``error``) instead of
  having to grep the log,
* **per-rule violation counts**, read out of the KLayout report database
  (``*.lyrdb``) rather than out of prose, and
* a **trustworthy exit code** -- see ``run()``'s note on why the PDK runner's
  own exit status cannot be used for this.
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import env as env_mod

# Legacy run_drc.py markers, then the pinned deck's own ``ReportStatus`` lines.
CLEAN_MARKERS = ("Klayout DRC run is clean", "DRC RESULT: SUCCESS")
DIRTY_MARKERS = ("Klayout DRC run is not clean", "DRC RESULT: FAILURE")

#: KLayout DRC threads for a direct deck run. The deck defaults to ``max``,
#: which would take every core of a shared host.
DECK_THREADS = 2
_RULES_RE = re.compile(r"Violated rules are\s*:\s*\{(?P<rules>.*)\}")


@dataclass
class DrcResult:
    status: str  # "clean" | "violations" | "error"
    topcell: str
    layout: Path
    variant: str
    violation_count: int = 0
    rule_counts: dict = field(default_factory=dict)
    log: str = ""
    report_db: Path | None = None
    command: list = field(default_factory=list)
    runner_returncode: int | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "clean"

    def summary(self) -> str:
        if self.status == "clean":
            return f"DRC clean: {self.topcell} ({self.variant}), 0 violations"
        if self.status == "violations":
            rules = ", ".join(f"{r}x{n}" for r, n in sorted(self.rule_counts.items()))
            return (
                f"DRC violations: {self.topcell} ({self.variant}), "
                f"{self.violation_count} item(s) -- {rules}"
            )
        return f"DRC error: {self.message}"


def parse_report_db(path: Path) -> tuple[int, dict]:
    """Count violations per rule id in a KLayout ``.lyrdb`` report database."""
    if not Path(path).is_file():
        return 0, {}
    root = ET.parse(str(path)).getroot()
    counts: Counter = Counter()
    for item in root.iter("item"):
        category = item.findtext("category") or ""
        rule = category.strip().strip("'")
        multiplicity = item.findtext("multiplicity") or "1"
        try:
            n = int(multiplicity)
        except ValueError:
            n = 1
        counts[rule] += n
    return sum(counts.values()), dict(counts)


def rules_from_log(log: str) -> list:
    match = _RULES_RE.search(log)
    if not match:
        return []
    return sorted(part.strip().strip("'\"") for part in match.group("rules").split(",") if part.strip())


def deck_command(
    tools: "env_mod.PvTools",
    layout: Path,
    topcell: str,
    report: Path,
    run_mode: str,
    offgrid: bool,
) -> list:
    """``klayout -b -r gf180mcu.drc`` invocation, switches per the deck's header.

    The ``-rd`` names are the deck's own (``klayout -b -r gf180mcu.drc -rd
    help=true``): ``input``, ``report``, ``topcell``, ``variant``,
    ``run_mode``, ``threads`` and ``decks``. Off-grid checks are the rule
    decks tagged ``offgrid``; excluding them is ``decks=all,-offgrid``.

    Die-level density rules (tag ``density``: DCF.1b, M*.4, MT.3, PL.8, ...)
    are always excluded: the pinned deck's ``all`` includes them, but the
    legacy runner's ``main`` table did not (they were a separate table), they
    are meaningless on a leaf cell, and every committed verdict here was
    scored without them. The deck file itself is run unmodified.
    """
    command = [
        str(tools.klayout),
        "-b",
        "-r",
        str(tools.drc_deck),
        "-rd",
        f"input={layout}",
        "-rd",
        f"topcell={topcell}",
        "-rd",
        f"report={report}",
        "-rd",
        f"variant={tools.variant_letter}",
        "-rd",
        f"run_mode={run_mode}",
        "-rd",
        f"threads={DECK_THREADS}",
    ]
    excluded = ["-density"] + ([] if offgrid else ["-offgrid"])
    return command + ["-rd", "decks=" + ",".join(["all", *excluded])]


def run(
    layout: Path,
    topcell: str,
    run_dir: Path,
    tools: "env_mod.PvTools | None" = None,
    run_mode: str = "deep",
    offgrid: bool = False,
    timeout: int = 3600,
) -> DrcResult:
    """Run the foundry DRC deck. Never raises on a *dirty* result.

    ``offgrid`` defaults to False (``--no_offgrid``) because the off-grid
    checks are a separate, slow class of rule that this flow-bring-up proof
    does not need; turn it on for real signoff. Every other FEOL/BEOL and
    connectivity rule in the ``main`` table runs.
    """
    tools = tools or env_mod.find_tools()
    layout = Path(layout).resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    report = run_dir / f"{topcell}.lyrdb"
    if tools.drc_runner is not None:
        command = [
            str(tools.python),
            str(tools.drc_runner),
            f"--path={layout}",
            f"--variant={tools.variant_letter}",
            f"--topcell={topcell}",
            f"--run_dir={run_dir}",
            f"--run_mode={run_mode}",
        ]
        if not offgrid:
            command.append("--no_offgrid")
    else:
        command = deck_command(tools, layout, topcell, report, run_mode, offgrid)

    try:
        completed, log = env_mod.run_pv_command(
            command,
            cwd=tools.drc_dir,
            timeout=timeout,
            env=tools.subprocess_env(),
            log_path=run_dir / "drc.stdout.log",
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - operational
        return DrcResult(
            status="error",
            topcell=topcell,
            layout=layout,
            variant=tools.variant_letter,
            command=command,
            message=f"DRC run timed out after {timeout}s: {exc}",
        )

    # Issue #701: the deck's stdout and report database name the run
    # directory, the repo checkout and the PDK install. Swap those for stable
    # tokens (disclosed in path-normalisation.txt) before anything is kept as
    # evidence; the verdict markers below are unaffected.
    subs = env_mod.path_substitutions(run_dir, tools.pdk.path)
    env_mod.normalise_run_dir(run_dir, subs)
    log = env_mod.normalise_paths(log, subs)

    report_dbs = sorted(run_dir.glob("*.lyrdb"))
    report_db = report_dbs[0] if report_dbs else None
    count, rule_counts = parse_report_db(report_db) if report_db else (0, {})

    # The PDK runner's exit status is NOT the verdict. It exits non-zero when
    # the deck itself fails to run, and (in this version) also on a dirty
    # result -- but the log marker is the only signal that distinguishes
    # "ran, found violations" from "did not run". Decide on markers first and
    # use the return code only to catch a crash that printed neither marker.
    if any(m in log for m in DIRTY_MARKERS) or count > 0:
        if not rule_counts:
            rule_counts = {rule: 1 for rule in rules_from_log(log)}
            count = sum(rule_counts.values())
        return DrcResult(
            status="violations",
            topcell=topcell,
            layout=layout,
            variant=tools.variant_letter,
            violation_count=count,
            rule_counts=rule_counts,
            log=log,
            report_db=report_db,
            command=command,
            runner_returncode=completed.returncode,
        )
    if any(m in log for m in CLEAN_MARKERS):
        return DrcResult(
            status="clean",
            topcell=topcell,
            layout=layout,
            variant=tools.variant_letter,
            log=log,
            report_db=report_db,
            command=command,
            runner_returncode=completed.returncode,
        )
    return DrcResult(
        status="error",
        topcell=topcell,
        layout=layout,
        variant=tools.variant_letter,
        log=log,
        report_db=report_db,
        command=command,
        runner_returncode=completed.returncode,
        message=(
            "DRC deck produced neither a clean nor a violations verdict "
            f"(runner exit {completed.returncode}); see the captured log"
        ),
    )
