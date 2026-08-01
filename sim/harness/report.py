"""Summaries, spec checks, and append-only evidence records.

The output format here is the one ratified in ``sim/README.md``: a run
produces a Markdown summary record at

    sim/<experiment-slug>/records/<record-id>.md

alongside a frozen netlist at ``netlist-snapshots/<record-id>.spice`` and the
raw per-corner ngspice logs at ``corners/<record-id>/<corner-id>.log``.

``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``.

CLAUDE.md and ``sim/README.md``: "sim/ results are append-only evidence."
This module never overwrites an existing record -- on a collision it mints a
new (still conforming) record-id rather than clobbering, and corrections are
expected to reference the prior record via ``Supersedes``. Deleting evidence
is a human decision, not a script's.

Field set and order follow ``sim/README.md``'s "Summary record format"
verbatim: Record ID, Claim, Netlist provenance, **Environment provenance**,
Corner matrix run, **Methodology / criteria / limitations**, Statistical
convention, Result, Links, Timestamp / author, Supersedes. The two bolded
fields are this repo's own additions ("[PLL delta]" in sim/README.md) beyond
the ported bandgap schema.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import platform
import socket
import subprocess
import sys
from pathlib import Path

from . import HARNESS_VERSION
from .corners import (
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
    REQUIRED_MOS_CORNERS,
    PvtPoint,
)
from .pdk import Pdk
from .runner import PointResult
from .testbench import Testbench

#: Subdirectories of ``sim/<experiment-slug>/`` defined by ``sim/README.md``.
TESTBENCH_DIR = "testbench"          # the default; a record cites the
                                     # directory its own manifest came from
SNAPSHOT_DIR = "netlist-snapshots"
CORNERS_DIR = "corners"
RECORDS_DIR = "records"


def _git(*args: str, cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:  # pragma: no cover - git always present in this repo
        return ""


def git_provenance(repo_root: Path) -> dict:
    commit = _git("rev-parse", "HEAD", cwd=repo_root)
    dirty = bool(_git("status", "--porcelain", cwd=repo_root))
    return {
        "commit": commit or "unknown",
        "short": (commit[:7] if commit else "unknown"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root) or "unknown",
        "dirty": dirty,
    }


def format_record_id(short_sha: str, when: _dt.datetime) -> str:
    """``<YYYYMMDD>-<HHMMSS>-<short-git-sha>`` -- see ``sim/README.md``.

    The git sha is the *only* provenance carried in the id; a dirty tree is
    reported inside the record body instead, so the id keeps the exact shape
    the ratified convention specifies.
    """
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{short_sha}"


def allocate_record_id(
    repo_root: Path,
    records_dir: Path,
    when: _dt.datetime | None = None,
    git: dict | None = None,
) -> str:
    """Mint a fresh, unused ``<record-id>``.

    Append-only: if a record with this id already exists (same second, same
    commit) we advance the timestamp until the id is free rather than
    overwriting or inventing a non-conforming suffix.
    """
    when = when or _dt.datetime.now(_dt.timezone.utc)
    short_sha = (git or git_provenance(repo_root))["short"]
    while True:
        record_id = format_record_id(short_sha, when)
        if not (records_dir / f"{record_id}.md").exists():
            return record_id
        when += _dt.timedelta(seconds=1)


def summarize(results: list[PointResult], measure_names: list[str]) -> dict:
    """Min / max / mean / spread of each measurement across the PVT grid."""
    summary: dict[str, dict] = {}
    ok = [r for r in results if r.status == "ok"]
    for name in measure_names:
        samples = [(r.measurements[name], r.point.corner_id) for r in ok if name in r.measurements]
        if not samples:
            summary[name] = {"n": 0}
            continue
        values = [v for v, _ in samples]
        lo_value, lo_at = min(samples, key=lambda s: s[0])
        hi_value, hi_at = max(samples, key=lambda s: s[0])
        mean = sum(values) / len(values)
        spread_pct = (hi_value - lo_value) / abs(mean) * 100.0 if mean else None
        summary[name] = {
            "n": len(values),
            "min": lo_value,
            "min_at": lo_at,
            "max": hi_value,
            "max_at": hi_at,
            "mean": mean,
            "spread_pct": spread_pct,
        }
    return summary


def evaluate_checks(
    checks: dict[str, dict],
    results: list[PointResult],
    summary: dict,
) -> list[dict]:
    """Return a list of check failures (empty list == everything passed)."""
    failures: list[dict] = []
    for name, spec in checks.items():
        low = spec.get("min")
        high = spec.get("max")
        if low is not None or high is not None:
            for result in results:
                if result.status != "ok" or name not in result.measurements:
                    continue
                value = result.measurements[name]
                if low is not None and value < low:
                    failures.append(
                        {
                            "measurement": name,
                            "kind": "min",
                            "limit": low,
                            "value": value,
                            "at": result.point.corner_id,
                        }
                    )
                if high is not None and value > high:
                    failures.append(
                        {
                            "measurement": name,
                            "kind": "max",
                            "limit": high,
                            "value": value,
                            "at": result.point.corner_id,
                        }
                    )
        # Grid-level spread checks. max_spread_pct is the usual "this must be
        # stable over PVT" assertion; min_spread_pct is its inverse and exists
        # to prove the harness is actually *moving* the corner -- a measurement
        # that is supposed to be strongly PVT-sensitive but comes back flat
        # means .temp / .lib never took effect.
        for kind, limit in (
            ("max_spread_pct", spec.get("max_spread_pct")),
            ("min_spread_pct", spec.get("min_spread_pct")),
        ):
            if limit is None:
                continue
            stats = summary.get(name) or {}
            # A single-point grid has zero spread by construction (there is
            # nothing to spread across), which is indistinguishable from "the
            # sweep is broken" by value alone. min_spread_pct exists to catch
            # the latter, so it does not apply to a singleton grid (e.g. a
            # --corners typical --temps 27 --supply-tol 0 debugging run) --
            # max_spread_pct is unaffected, since 0 spread trivially satisfies
            # "stays under the limit".
            if kind == "min_spread_pct" and stats.get("n", 0) <= 1:
                continue
            observed = stats.get("spread_pct")
            violated = (
                observed is None
                or (kind == "max_spread_pct" and observed > limit)
                or (kind == "min_spread_pct" and observed < limit)
            )
            if violated:
                failures.append(
                    {
                        "measurement": name,
                        "kind": kind,
                        "limit": limit,
                        "value": observed,
                        "at": "grid",
                    }
                )
    return failures


def environment(pdk: Pdk, ngspice: str, repo_root: Path, git: dict | None = None) -> dict:
    """Reproducibility provenance for the record.

    ``git`` should be sampled *before* the run starts. The harness writes its
    own per-corner logs into the tracked evidence tree, so sampling afterwards
    would report every record as taken against a dirty tree.
    """
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover - unusual environments
        user = "unknown"
    return {
        "harness_version": HARNESS_VERSION,
        "ngspice": ngspice,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "host": socket.gethostname(),
        "user": user,
        "pdk": pdk.provenance(),
        "git": git if git is not None else git_provenance(repo_root),
    }


def matrix_conformance(tb: Testbench, points: list[PvtPoint]) -> dict:
    """Is this run the full PVT matrix CLAUDE.md/sim/README.md mandates?

    ``sim/README.md`` requires every record's *Corner matrix run* field to be
    the full matrix (-40/27/125 C, +/-10% supply, the five MOS process
    bundles) unless the record states why a subset was used. This returns
    what is missing so the CLI can insist on a written justification instead
    of quietly recording a thinner run.
    """
    temps = {round(p.temp_c, 6) for p in points}
    supplies = {round(p.vdd, 6) for p in points}
    process = {p.corner.name for p in points}

    required_temps = {round(t, 6) for t in DEFAULT_TEMPERATURES_C}
    nominal = tb.nominal_supply_v
    required_supplies = {
        round(nominal * (1.0 - DEFAULT_SUPPLY_TOLERANCE), 6),
        round(nominal, 6),
        round(nominal * (1.0 + DEFAULT_SUPPLY_TOLERANCE), 6),
    }

    missing: list[str] = []
    if not required_temps <= temps:
        missing.append(
            "temperature: missing "
            + ", ".join(f"{t:g} C" for t in sorted(required_temps - temps))
        )
    if not required_supplies <= supplies:
        missing.append(
            "supply: missing "
            + ", ".join(f"{v:.2f} V" for v in sorted(required_supplies - supplies))
        )
    if not REQUIRED_MOS_CORNERS <= process:
        missing.append(
            "process: missing MOS bundle(s) "
            + ", ".join(sorted(REQUIRED_MOS_CORNERS - process))
        )

    return {"full": not missing, "missing": missing}


def build_record(
    tb: Testbench,
    pdk: Pdk,
    points: list[PvtPoint],
    results: list[PointResult],
    ngspice: str,
    repo_root: Path,
    record_id: str,
    started_utc: str,
    wall_seconds: float,
    claim: str = "",
    supersedes: str = "",
    statistical_convention: str = "",
    subset_reason: str = "",
    git: dict | None = None,
) -> dict:
    measure_names = tb.measure_names
    summary = summarize(results, measure_names)
    failures = evaluate_checks(tb.checks, results, summary)
    n_ok = sum(1 for r in results if r.status == "ok")

    if n_ok != len(results):
        status = "error"
    elif failures:
        status = "fail"
    else:
        status = "pass"

    corners = []
    seen = set()
    for point in points:
        if point.corner.name not in seen:
            seen.add(point.corner.name)
            corners.append(
                {
                    "name": point.corner.name,
                    "sections": list(point.corner.sections),
                    "description": point.corner.description,
                }
            )

    return {
        "record_id": record_id,
        "experiment": tb.experiment,
        "status": status,
        "started_utc": started_utc,
        "wall_seconds": round(wall_seconds, 2),
        "claim": claim or tb.claim,
        "methodology": list(tb.methodology),
        "supersedes": supersedes,
        "statistical_convention": statistical_convention,
        "subset_reason": subset_reason,
        "matrix": matrix_conformance(tb, points),
        "testbench": tb.provenance(),
        "environment": environment(pdk, ngspice, repo_root, git),
        "grid": {
            "corners": corners,
            "extra_lib_sections": list(tb.extra_lib_sections),
            "temperatures_c": sorted({p.temp_c for p in points}),
            "supplies_v": sorted({p.vdd for p in points}),
            "points": len(points),
            "points_ok": n_ok,
        },
        "measure": {
            name: (
                tb.measure[name]
                if name in tb.measure
                else f"raw: .measure {tb.raw_measures[name].analysis} {tb.raw_measures[name].expr}"
            )
            for name in measure_names
        },
        # Empty for a single-topology testbench, which keeps the one flat
        # result table below. A multi-topology manifest gets one entry per
        # sub-circuit (plus a trailing 'ungrouped' entry for anything it did
        # not assign) and one sub-table per entry.
        "topology_groups": [
            {
                "name": group.name,
                "description": group.description,
                "measures": list(group.measures),
            }
            for group in tb.measure_groups
        ],
        "checks": {
            "spec": tb.checks,
            "passed": not failures,
            "failures": failures,
        },
        "summary": summary,
        "points": [r.as_dict() for r in results],
    }


def _fmt(value) -> str:
    """Human-readable scalar for the Markdown record."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.6e}"
        return f"{value:.6g}"
    return str(value)


class RecordExists(RuntimeError):
    """Refused to overwrite an existing append-only record."""


def write_netlist_snapshot(tb: Testbench, experiment_dir: Path, record_id: str) -> Path:
    """Freeze the DUT netlist for this record.

    ``sim/README.md``: ``netlist-snapshots/<record-id>.spice`` is "the frozen
    DUT netlist used for this record", so later edits to ``testbench/`` never
    change what an existing record refers to.
    """
    out_dir = experiment_dir / SNAPSHOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record_id}.spice"
    if path.exists():
        raise RecordExists(f"{path} already exists; append-only evidence is never rewritten")
    header = "\n".join(
        [
            f"* Frozen netlist snapshot for record {record_id}",
            f"* source     : {tb.netlist.relative_to(experiment_dir.parent.parent)}",
            f"* sha256     : {tb.netlist_sha256}",
            "* This is a verbatim copy taken at record time. Do not edit.",
            "",
        ]
    )
    path.write_text(header + tb.netlist.read_text())
    return path


def _corner_matrix_lines(record: dict) -> list[str]:
    grid = record["grid"]
    lines = [
        "- **Corner matrix run**:",
        "  - Process (bundle -> `.lib` sections): "
        + "; ".join(
            f"`{c['name']}` -> {' '.join(c['sections'])}" for c in grid["corners"]
        ),
    ]
    # Corner-independent model sections no bundle carries (see
    # testbench._load_extra_lib_sections). Older records predate the key.
    if grid.get("extra_lib_sections"):
        lines.append(
            "  - Corner-independent `.lib` sections added at every point: "
            + ", ".join(f"`{s}`" for s in grid["extra_lib_sections"])
        )
    lines += [
        "  - Temperature: " + ", ".join(f"{t:g} °C" for t in grid["temperatures_c"]),
        "  - Supply: " + ", ".join(f"{v:.2f} V" for v in grid["supplies_v"]),
        f"  - {grid['points']} point full-factorial grid "
        f"(process x temperature x supply), {grid['points_ok']} completed",
    ]
    if record["matrix"]["full"]:
        lines.append(
            "  - Full PVT matrix per CLAUDE.md / sim/README.md "
            "(-40/27/125 °C, ±10% supply, the five MOS process bundles)."
        )
    else:
        lines.append("  - **Subset of the mandated PVT matrix.** Gaps: "
                     + "; ".join(record["matrix"]["missing"]) + ".")
        lines.append("  - Justification: " + (record["subset_reason"] or "(none given)"))
    return lines


def _methodology_lines(record: dict) -> list[str]:
    lines = ["- **Methodology / criteria / limitations**:"]
    if record["methodology"]:
        lines += [f"  - {item}" for item in record["methodology"]]
    else:
        lines.append(
            "  - N/A -- no methodology notes were provided by this testbench's "
            "manifest (`testbench/tb.json`'s `methodology` field)."
        )
    return lines


def _failures_by_corner(failures: list[dict]) -> dict[str, list[str]]:
    """``{corner-id (or "grid"): ["<measurement> <kind>=<limit> (got <value>)"]}``."""
    out: dict[str, list[str]] = {}
    for failure in failures:
        out.setdefault(failure["at"], []).append(
            f"{failure['measurement']} {failure['kind']}={_fmt(failure['limit'])} "
            f"(got {_fmt(failure['value'])})"
        )
    return out


def _corner_table_lines(
    record: dict, measure_names: list[str], failures_at: dict[str, list[str]]
) -> list[str]:
    """One ``corner-id | <measure...> | pass/fail`` table.

    ``failures_at`` is passed in rather than derived so a per-topology table
    can be given only its own columns' failures -- an unrelated topology's
    FAIL in this table's pass/fail column would be pure noise. A point that
    failed to simulate at all is reported as ERROR in *every* table, because
    the whole point is missing, not one topology's slice of it.
    """
    lines = [
        "  | corner-id | " + " | ".join(measure_names) + " | pass/fail |",
        "  |---|" + "---|" * (len(measure_names) + 1),
    ]
    for point in record["points"]:
        cells = [_fmt(point["measurements"].get(name)) for name in measure_names]
        problems = failures_at.get(point["corner_id"], [])
        if point["status"] != "ok":
            verdict = f"ERROR — {point.get('message', point['status'])}"
        elif problems:
            verdict = "FAIL — " + "; ".join(problems)
        else:
            verdict = "PASS"
        lines.append(f"  | `{point['corner_id']}` | " + " | ".join(cells) + f" | {verdict} |")
    return lines


def _spread_rows(record: dict, groups: list[dict]):
    """``(topology-or-None, name, stats)`` in the order the record renders.

    Grouped records walk the groups in manifest order; anything the grouping
    never mentioned is still emitted (with no topology) at the end, so no
    measurement can fall out of the spread table.
    """
    summary = record["summary"]
    if not groups:
        for name, stats in summary.items():
            yield None, name, stats
        return
    seen: set[str] = set()
    for group in groups:
        for name in group["measures"]:
            if name in summary:
                seen.add(name)
                yield group["name"], name, summary[name]
    for name, stats in summary.items():
        if name not in seen:
            yield None, name, stats


def _spread_table_lines(record: dict, groups: list[dict]) -> list[str]:
    if groups:
        lines = [
            "  | topology | measurement | min | max | mean | spread % | limits |",
            "  |---|---|---|---|---|---|---|",
        ]
    else:
        lines = [
            "  | measurement | min | max | mean | spread % | limits |",
            "  |---|---|---|---|---|---|",
        ]
    for topology, name, stats in _spread_rows(record, groups):
        spec = record["checks"]["spec"].get(name, {})
        limits = ", ".join(
            f"{key}={_fmt(spec[key])}"
            for key in ("min", "max", "max_spread_pct", "min_spread_pct")
            if key in spec
        ) or "—"
        lead = f"| `{topology}` " if groups else ""
        if not stats.get("n"):
            lines.append(f"  {lead}| `{name}` | no data | | | | {limits} |")
            continue
        lines.append(
            f"  {lead}| `{name}` | {_fmt(stats['min'])} (`{stats['min_at']}`) "
            f"| {_fmt(stats['max'])} (`{stats['max_at']}`) "
            f"| {_fmt(stats['mean'])} | {_fmt(stats['spread_pct'])} | {limits} |"
        )
    return lines


def _result_lines(record: dict) -> list[str]:
    """The record's **Result** field.

    Single-topology (the default, and every record written before
    ``topology_groups`` existed): one flat table over every measurement.
    Multi-topology: one captioned sub-table per topology, in manifest order,
    so a deck with several sub-circuits reads as several experiments instead
    of one unreadably wide table.
    """
    groups = record.get("topology_groups") or []
    failures = record["checks"]["failures"]
    failures_at = _failures_by_corner(failures)

    lines = ["- **Result**:", ""]
    if groups:
        for group in groups:
            caption = f"  **{group['name']}**"
            if group.get("description"):
                caption += f" — {group['description']}"
            own = set(group["measures"])
            lines.append(caption)
            lines.append("")
            lines += _corner_table_lines(
                record,
                list(group["measures"]),
                _failures_by_corner([f for f in failures if f["measurement"] in own]),
            )
            lines.append("")
        lines.pop()  # the shared trailer below re-opens with its own blank line
    else:
        lines += _corner_table_lines(record, list(record["measure"]), failures_at)

    # Grid-level failures are reported once for the whole record, not once per
    # topology: they are properties of the sweep, and a check naming something
    # that is not a declared measurement can only surface here.
    grid_failures = failures_at.get("grid", [])
    if grid_failures:
        lines.append("")
        lines.append("  Grid-level check failures: " + "; ".join(grid_failures) + ".")

    lines.append("")
    lines.append("  Spread across the grid:")
    lines.append("")
    lines += _spread_table_lines(record, groups)

    verdict = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}[record["status"]]
    lines.append("")
    lines.append(f"  - **Overall: {verdict}**")
    return lines


def render_record(record: dict, experiment: str) -> str:
    """Render the ratified ``records/<record-id>.md`` summary.

    Field set and order follow ``sim/README.md``: Record ID, Claim, Netlist
    provenance, Environment provenance, Corner matrix run, Methodology /
    criteria / limitations, Statistical convention, Result, Links,
    Timestamp / author, Supersedes.
    """
    record_id = record["record_id"]
    env = record["environment"]
    tb = record["testbench"]
    git = env["git"]
    pdk = env["pdk"]

    # The manifest's own directory, not the default name: an experiment that
    # carries more than one testbench (devchar-passives: a capacitor deck and
    # a resistor deck, two distinct claims) must not cite the wrong path.
    tb_dir = tb.get("directory") or TESTBENCH_DIR
    provenance = f"schematic (`sim/{experiment}/{tb_dir}/{tb['netlist']}`)"
    if git["dirty"]:
        provenance += (
            f" — **taken against a dirty working tree** at commit `{git['commit']}`; "
            "not citable as a clean-tree result"
        )

    lines = [
        f"# Record {record_id}",
        "",
        f"- **Record ID**: {record_id}",
        f"- **Claim**: {record['claim'] or 'harness self-verification -- no spec or design-input claim'}",
        f"- **Netlist provenance**: {provenance}, netlist SHA-256 `{tb['netlist_sha256']}`",
        "- **Environment provenance**:",
        f"  - PDK: volare `{pdk.get('variant')}`, open_pdks `{pdk.get('open_pdks_version')}` "
        f"({pdk.get('path')}, found via {pdk.get('discovered_via')})",
        "  - Models: `libs.tech/ngspice/sm141064.ngspice`; `design.ngspice` included first",
        f"  - Simulator: {env['ngspice']}. Harness: sim/harness {env['harness_version']}, "
        f"python {env['python']}",
        f"  - Repo commit: `{git['commit']}` ({'DIRTY' if git['dirty'] else 'clean'} tree)",
        f"  - Host: {env['platform']} ({env['host']})",
    ]
    lines += _corner_matrix_lines(record)
    lines += _methodology_lines(record)
    lines.append(
        "- **Statistical convention**: "
        + (record["statistical_convention"]
           or "N/A (corner-matrix claim, not a distribution claim)")
    )
    lines += _result_lines(record)
    lines += [
        "- **Links**:",
        f"  - Testbench: `sim/{experiment}/{tb_dir}/{tb['netlist']}`, "
        f"`sim/{experiment}/{tb_dir}/tb.json`",
        f"  - Netlist snapshot: `sim/{experiment}/{SNAPSHOT_DIR}/{record_id}.spice`",
        f"  - Raw logs: `sim/{experiment}/{CORNERS_DIR}/{record_id}/`",
        f"- **Timestamp / author**: {record['started_utc']}, {env['user']}",
        f"- **Supersedes**: {record['supersedes'] or '(none)'}",
        "",
        "---",
        "",
        "Written by `sim/run_corners.py`. Append-only: never edit or delete this",
        "file -- a re-run or correction mints a new record-id and points back here",
        "via **Supersedes** (see `sim/README.md`).",
        "",
    ]
    return "\n".join(lines)


def write_record(record: dict, experiment_dir: Path) -> Path:
    """Write ``records/<record-id>.md``; never overwrite an existing record."""
    out_dir = experiment_dir / RECORDS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['record_id']}.md"
    if path.exists():
        raise RecordExists(
            f"{path} already exists; records are append-only -- mint a new record-id"
        )
    path.write_text(render_record(record, experiment_dir.name))
    return path
