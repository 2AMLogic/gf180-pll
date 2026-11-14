#!/usr/bin/env python3
"""Grade one evidence record against the record it supersedes.

    python3 sim/lib/record_delta.py <old-record.md> <new-record.md>

Prints a Markdown delta table: for every measurement the two records share,
the old and new value range over the grid, the largest absolute and relative
change, the corner that moved most, and whether any per-corner `pass/fail`
verdict or any `limits` entry changed.

WHY THIS EXISTS (#825)
----------------------

`sim/README.md` makes evidence records immutable: a re-run mints a new record
and names its predecessor in **Supersedes**. That convention says nothing
about *how much the numbers moved*, and a re-qualification (re-running a
frozen reference record after a PDK or simulator pin changes) is exactly the
case where the movement is the finding. Reading two 45-row records side by
side by eye does not scale and is not reviewable.

This reads the records themselves rather than the raw per-corner output,
deliberately: under `manifests/artifacts/README.md` the raw output of a new
run lives in the fleet artifact store and never lands in git, while the
Markdown record is the citable object that does. Grading the artifact a
reader can actually fetch is the point.

WHAT IT DOES NOT DO
-------------------

It does not decide whether a movement is acceptable -- it reports the
movement and the limit beside it. A measurement that moves past its stated
tolerance, or a verdict that flips, is a finding for a human to route into an
issue or a decision record (`spec/decision-records/`); this script only makes
that visible, and never edits either record.

It compares the *intersection* of the two records' measurements. A record
that drops or adds a measurement family relative to its predecessor (the
harness migration in #40 did both) has those columns listed as
present-in-one-only rather than silently ignored.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A per-corner result row: `| `corner-id` | v1 | v2 | ... | PASS |`
_ROW = re.compile(r"^\s*\|\s*`([^`]+)`\s*\|(.+)\|\s*$")
# A table header row: `| corner-id | m1 | m2 | ... | pass/fail |`
_HEAD = re.compile(r"^\s*\|\s*corner-id\s*\|(.+)\|\s*$")
# A topology sub-table caption: `**name** — prose`
_TOPO = re.compile(r"^\s*\*\*([A-Za-z0-9_.+-]+)\*\*\s*[—-]")
# The spread table's rows, which carry the `limits` column.
_SPREAD_HEAD = re.compile(r"^\s*\|\s*(topology\s*\|\s*)?measurement\s*\|")


def _cells(body: str) -> list[str]:
    return [c.strip() for c in body.split("|")]


def _num(text: str) -> float | None:
    """Parse a record cell as a float, or None if it is not numeric.

    Records render `—` for an absent limit and bare strings for verdicts, so
    a non-numeric cell is normal and must not be coerced to 0.
    """
    text = text.strip().strip("`")
    if not text or text in {"—", "-", "n/a", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_record(path: Path) -> tuple[dict, dict]:
    """Return ``(values, limits)``.

    ``values`` maps ``(topology, measurement, corner_id)`` to a float, plus
    ``(topology, "pass/fail", corner_id)`` to the verdict string.
    ``limits`` maps ``(topology, measurement)`` to the record's own stated
    limit text, taken from the "Spread across the grid" table.
    """
    values: dict[tuple[str, str, str], object] = {}
    limits: dict[tuple[str, str], str] = {}

    topo = ""
    columns: list[str] | None = None
    in_spread = False

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _TOPO.match(line)
        if m:
            topo, columns = m.group(1), None
            continue

        if _SPREAD_HEAD.match(line):
            # The spread table ends the per-corner tables; from here the rows
            # carry limits, not corner values.
            in_spread = True
            columns = None
            continue

        if in_spread:
            cells = _cells(line)
            # `| topology | measurement | min | max | mean | spread % | limits |`
            # or, single-topology records, the same without the topology column.
            if len(cells) == 9:
                limits[(cells[1].strip("`"), cells[2].strip("`"))] = cells[7]
            elif len(cells) == 8:
                limits[(topo, cells[1].strip("`"))] = cells[6]
            continue

        m = _HEAD.match(line)
        if m:
            columns = [c.strip() for c in m.group(1).split("|")]
            continue

        m = _ROW.match(line)
        if m and columns:
            corner, cells = m.group(1), _cells(m.group(2))
            for name, cell in zip(columns, cells):
                if name == "pass/fail":
                    values[(topo, name, corner)] = cell
                else:
                    v = _num(cell)
                    if v is not None:
                        values[(topo, name, corner)] = v

    return values, limits


def _fmt(x: float) -> str:
    if x == 0:
        return "0"
    if 1e-4 <= abs(x) < 1e5:
        return f"{x:.6g}"
    return f"{x:.6e}"


def compare(old_path: Path, new_path: Path) -> tuple[list[str], int]:
    """Render the delta tables. Returns ``(lines, n_findings)``."""
    old_v, old_l = parse_record(old_path)
    new_v, new_l = parse_record(new_path)

    def measurements(values):
        return {(t, m) for (t, m, _c) in values if m != "pass/fail"}

    old_m, new_m = measurements(old_v), measurements(new_v)
    shared = sorted(old_m & new_m)

    lines: list[str] = []
    findings = 0

    lines.append(
        f"| topology | measurement | limit | old min..max | new min..max "
        f"| max abs delta | max rel delta % | worst corner |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")

    for topo, meas in shared:
        corners = sorted(
            c for (t, m, c) in old_v if (t, m) == (topo, meas) and (t, m, c) in new_v
        )
        if not corners:
            continue
        olds = [old_v[(topo, meas, c)] for c in corners]
        news = [new_v[(topo, meas, c)] for c in corners]

        worst_abs = 0.0
        worst_rel = 0.0
        worst_corner = "—"
        for c, o, n in zip(corners, olds, news):
            d = abs(n - o)
            # Relative to the OLD value: the old record is the baseline a
            # reader is comparing against. A zero baseline has no meaningful
            # relative change, so it contributes to the absolute column only.
            r = (d / abs(o) * 100.0) if o != 0 else 0.0
            if r > worst_rel or (r == worst_rel and d > worst_abs):
                worst_abs, worst_rel, worst_corner = d, r, c
            worst_abs = max(worst_abs, d)

        limit = new_l.get((topo, meas), old_l.get((topo, meas), "—")) or "—"
        lines.append(
            f"| `{topo}` | `{meas}` | {limit} "
            f"| {_fmt(min(olds))}..{_fmt(max(olds))} "
            f"| {_fmt(min(news))}..{_fmt(max(news))} "
            f"| {_fmt(worst_abs)} | {worst_rel:.4g} | `{worst_corner}` |"
        )

    # --- verdict flips -----------------------------------------------------
    flips = []
    for (topo, meas, corner), old_val in sorted(old_v.items()):
        if meas != "pass/fail":
            continue
        new_val = new_v.get((topo, meas, corner))
        if new_val is not None and new_val != old_val:
            flips.append((topo, corner, old_val, new_val))

    lines.append("")
    if flips:
        findings += len(flips)
        lines.append("**Per-corner verdict flips** (each one is a finding):")
        lines.append("")
        lines.append("| topology | corner-id | old | new |")
        lines.append("|---|---|---|---|")
        for topo, corner, o, n in flips:
            lines.append(f"| `{topo}` | `{corner}` | {o} | {n} |")
    else:
        lines.append(
            f"**Per-corner verdicts**: unchanged on all "
            f"{sum(1 for (_t, m, _c) in old_v if m == 'pass/fail')} graded rows."
        )

    # --- limit drift -------------------------------------------------------
    limit_changes = [
        (t, m, old_l[(t, m)], new_l[(t, m)])
        for (t, m) in sorted(set(old_l) & set(new_l))
        if old_l[(t, m)] != new_l[(t, m)]
    ]
    lines.append("")
    if limit_changes:
        findings += len(limit_changes)
        lines.append("**Stated limits changed** (each one is a finding):")
        lines.append("")
        for t, m, o, n in limit_changes:
            lines.append(f"- `{t}`/`{m}`: `{o}` -> `{n}`")
    else:
        lines.append("**Stated limits**: identical in both records.")

    # --- coverage ----------------------------------------------------------
    only_old = sorted(old_m - new_m)
    only_new = sorted(new_m - old_m)
    if only_old or only_new:
        lines.append("")
        lines.append("**Measurement coverage differs between the two records:**")
        lines.append("")
        for t, m in only_old:
            lines.append(f"- in `{old_path.stem}` only: `{t}`/`{m}`")
        for t, m in only_new:
            lines.append(f"- in `{new_path.stem}` only: `{t}`/`{m}`")

    return lines, findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old", type=Path, help="the superseded record (.md)")
    ap.add_argument("new", type=Path, help="the superseding record (.md)")
    args = ap.parse_args(argv)

    for p in (args.old, args.new):
        if not p.is_file():
            print(f"record-delta: no such record: {p}", file=sys.stderr)
            return 2

    lines, findings = compare(args.old, args.new)
    print(f"### `{args.new.stem}` vs `{args.old.stem}`")
    print()
    print("\n".join(lines))
    if findings:
        print()
        print(f"_{findings} finding(s) above need a human disposition._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
