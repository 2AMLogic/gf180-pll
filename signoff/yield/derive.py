#!/usr/bin/env python3
"""Thin derivation step for the T1 item-6 `klt yield` evidence (#1081).

`klt yield-csv` derives the sample-set documents; this script only writes the
long-format per-draw CSVs it reads, from the committed Monte Carlo records,
plus the per-term spec-limits files `klt yield` grades against. Grouping,
failed-draw handling and the `measurements[]` shape stay in klt. Two things
the committed records have that `klt yield-csv` (0.9.2) cannot consume
directly, both filed upstream rather than worked around here:

  1. every record CSV opens with `#` metadata lines, and `klt yield-csv`
     takes the file's first line as its header
     (2AMLogic/klayout-tools#<comment-prefix issue, see signoff/yield/README.md>);
  2. budget term 1's per-draw value is the signed worst-magnitude mismatch
     across the three Vctrl points of one draw -- the verdict statistic
     `sim/mc-cp-mismatch/testbench/run.sh` computes and design/README.md's
     budget table checks -- while the committed `mc_cp_dc.csv` carries one
     row per (corner, seed, vctrl point).

The derived CSVs under `signoff/yield/csv/` and the limits under
`signoff/yield/limits/` are committed; tests re-derive them byte-for-byte
from the records below, so the record -> CSV -> sample-set -> envelope chain
is checkable without a simulator.

Sources are the records current when #1081 was implemented: PR #1074
(re-qualification under open_pdks f6eeac7) was still open, so the
`c6d73a35`-era records are used. Records are append-only; when a successor
record supersedes one of these, re-point the constants and re-run
`signoff/yield/run.sh`.

Usage (from the repo root, or anywhere -- paths resolve from the script):

    python3 signoff/yield/derive.py [--out DIR]

Writes `csv/` and `limits/` under DIR (default: this script's directory).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

YIELD_DIR = Path(__file__).resolve().parent
REPO_ROOT = YIELD_DIR.parents[1]

MC_RECORD = "sim/mc-cp-mismatch/corners/20260927-102154-d004d5b"
VCO_RECORD = "sim/vco-tuning-range/corners/20260927-220631-546a397"

TERM1_SPEC_ROW = "cp-budget/1"
TERM2A_SPEC_ROW = "cp-budget/2a"
TERM3_SPEC_ROW = "cp-budget/3"
TERM4_SPEC_ROW = "cp-budget/4"
VCO_SPEC_ROW = "vco-band-coverage/adjacent-pair-ratio"


class DeriveError(Exception):
    pass


def read_record_rows(rel: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (header, rows) of a record CSV, skipping its `#` preamble."""
    path = REPO_ROOT / rel
    data_lines = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            data_lines.append(line.rstrip("\n").rstrip("\r"))
    data_lines = [ln for ln in data_lines if ln]
    if not data_lines:
        raise DeriveError(f"{rel}: no header row after the `#` preamble")
    header = data_lines[0].split(",")
    rows = [dict(zip(header, ln.split(","))) for ln in data_lines[1:]]
    return header, rows


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(",".join(header) + "\n")
        for row in rows:
            fh.write(",".join(row) + "\n")


def write_limits(path: Path, groups: list[str], spec_row: str,
                 minv: float | None, maxv: float | None) -> None:
    entry: dict = {"spec_row": spec_row, "target_sigma": 3.0}
    if minv is not None:
        entry["min"] = minv
    if maxv is not None:
        entry["max"] = maxv
    doc = {"measurements": {g: entry for g in groups}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def derive_mc_term1(out: Path) -> list[str]:
    """Term 1: per (corner, seed), the signed worst-magnitude `mism_pct`
    across the draw's three Vctrl points -- the verdict statistic run.sh
    computes (its `DC term1 SIGNED worst-of-3` line), kept signed."""
    _, rows = read_record_rows(Path(MC_RECORD) / "mc_cp_dc.csv")
    per_draw: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for r in rows:
        key = (r["corner"], r["seed"])
        if key not in per_draw:
            order.append(key)
            per_draw[key] = []
        per_draw[key].append(r["mism_pct"])
    out_rows = []
    for key in order:
        vals = per_draw[key]
        if len(vals) != 3:
            raise DeriveError(
                f"term 1 draw {key}: expected 3 Vctrl points, found {len(vals)}")
        worst = max(vals, key=lambda v: abs(float(v)))
        out_rows.append([key[0], key[1], worst])
    write_csv(out / "csv" / "mc-cp-term1-worst-window.csv",
              ["corner", "seed", "mism_worst_pct"], out_rows)
    groups = list(dict.fromkeys(k[0] for k in order))
    write_limits(out / "limits" / "term1.json", groups, TERM1_SPEC_ROW, -20.0, 20.0)
    return groups


def _derive_passthrough(out: Path, source: str, out_csv: str,
                        columns: list[str], group_col: str) -> list[str]:
    """Strip the `#` preamble and project `columns`, verbatim."""
    _, rows = read_record_rows(Path(MC_RECORD) / source)
    out_rows = [[r[c] for c in columns] for r in rows]
    write_csv(out / "csv" / out_csv, columns, out_rows)
    return list(dict.fromkeys(r[group_col] for r in rows))


def derive_vco(out: Path) -> list[str]:
    _, rows = read_record_rows(Path(VCO_RECORD) / "mismatch.csv")
    columns = ["point_id", "seed", "ratio"]
    out_rows = [[r[c] for c in columns] for r in rows]
    write_csv(out / "csv" / "vco-adjacent-pair-ratio.csv", columns, out_rows)
    groups = list(dict.fromkeys(r["point_id"] for r in rows))
    write_limits(out / "limits" / "vco-adjacent-pair-ratio.json", groups,
                 VCO_SPEC_ROW, 1.0, None)
    return groups


def derive_digital_spec_projection(out: Path) -> list[str]:
    """Project spec/pll.md's ratified row ids into the JSON shape `klt
    signoff`'s item-6 `not_applicable` form cites ("no shipped spec schema
    exists yet; only status and the row ids are required"). Generated, not
    hand-typed, and re-derived byte-for-byte by the tests, so the projection
    cannot drift from the spec's summary table. Ratification is this
    repository's own governance claim: spec rows move only through
    spec/decision-records (CLAUDE.md), which is what "status: ratified"
    asserts here."""
    text = (REPO_ROOT / "spec/pll.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    ids: list[str] = []
    for i, line in enumerate(lines):
        if not (line.startswith("|") and "#" in line):
            continue
        header = [c.strip() for c in line.strip("|").split("|")]
        if "#" not in header:
            continue
        if i + 1 >= len(lines) or not set(lines[i + 1]) <= set("|-: "):
            continue
        col = header.index("#")
        for row in lines[i + 2:]:
            if not row.startswith("|"):
                break
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != len(header) or not cells[col]:
                break
            ids.append(cells[col])
        break
    if not ids:
        raise DeriveError("spec/pll.md: no pipe table with a '#' id column")
    doc = {"status": "ratified", "rows": [{"id": r} for r in ids]}
    path = out / "digital" / "spec-rows.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(YIELD_DIR),
                    help="output directory (default: the script's own)")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()

    term1 = derive_mc_term1(out)
    term2a = _derive_passthrough(
        out, "mc_cp_switch.csv", "mc-cp-term2a-wskew.csv",
        ["corner", "seed", "wskew_s"], "corner")
    terms34 = _derive_passthrough(
        out, "mc_pfd_cp.csv", "mc-cp-terms3-4.csv",
        ["corner", "seed", "qnet0_c", "t_offset_s"], "corner")
    vco = derive_vco(out)

    write_limits(out / "limits" / "term2a.json", term2a, TERM2A_SPEC_ROW,
                 -2e-9, 2e-9)
    write_limits(out / "limits" / "term3.json", terms34, TERM3_SPEC_ROW,
                 -20e-15, 20e-15)
    write_limits(out / "limits" / "term4.json", terms34, TERM4_SPEC_ROW,
                 -3e-9, 3e-9)
    spec_ids = derive_digital_spec_projection(out)

    summary = {
        "sources": [MC_RECORD, VCO_RECORD],
        "groups": {"term1": len(term1), "term2a": len(term2a),
                   "terms3-4": len(terms34), "vco": len(vco)},
        "spec_row_ids": spec_ids,
    }
    json.dump(summary, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeriveError as exc:
        print(f"derive.py: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
