#!/usr/bin/env python3
"""gf180-pll :: supply-sensitivity :: which lock-detector trim code the closed
loop ACTUALLY ran at, read out of the committed logs rather than out of the
deck's configuration (issue #515).

    python3 trim_msb_audit.py [source-record-id] [--outdir DIR]

`design/pll_top.sch` placed the `LDT3` trim label three grid rows off the
`XLD` lock-detector instance's real `LDT3` pin, so the exported netlist wired
that instance's eighth argument to `net1` -- an xschem auto-named net with
exactly one connection -- while `.subckt pll_top` still declared a real
`LDT3` port. The pad existed and could be driven; nothing inside the
subcircuit read it. The detector therefore saw `code & 0b0111` at every code:
the eight codes 8..15 were not reachable on the assembled part, and a deck
that programmed one of them ran at the code eight below it.

`sim/supply-sensitivity/records/20260920-180604-0f91a9b.md` is the one
committed record that programmed a code with its MSB set -- `ff` -> 11
(`1011`), from `spec/pll.md`'s normative Lock-detector window trim-code rule.
Its `typical` cell is at code 7 (`0111`), MSB clear, and is unaffected.

THIS SCRIPT RE-SIMULATES NOTHING. Every number it emits is read out of
artifacts already committed under prior records (`sim/README.md`'s
append-only rule); it opens no PDK file and invokes no simulator.

Two independent readings, because one of them is a node dump and the other is
a behavioural consequence, and agreeing is what makes the conclusion safe:

  A. THE NODE DUMP -- direct. Each per-corner log prints the deck's
     `.param ldt<i>_code` values AND the DC operating point of every node,
     including the `ldt3` pad and the stray `xdut.net1` the instance's eighth
     terminal actually landed on. A pad at `vdd` beside a `net1` at 0 V is
     the defect, stated by the simulator itself.

  B. THE WINDOW COMPARISON -- behavioural, and it discriminates. The lock
     flag asserting IS the detector comparing its own window against the
     offset the loop stands off, so for each point the observed flag can be
     read against the window `sim/lock-window-trim`'s committed 1872-point
     code map measures at the SAME (bundle, temperature, supply) for the
     REQUESTED code and for the EFFECTIVE one. Where those two predictions
     disagree, the observed flag says which code ran.

  The predicted direction uses the source campaign's own stated rule, from
  `window_crossing.csv`'s header: the observable assert window is never
  SMALLER than `t_win`, so `t_win > |phi_b|` predicts the flag asserts. It is
  a one-sided bound, so a point where `t_win < |phi_b|` predicts nothing on
  its own and is reported as `unpredicted` rather than as a prediction.

Reads, and never modifies:
    sim/supply-sensitivity/corners/<src>/*.log
    sim/supply-sensitivity/corners/<src>/supply_steady.csv
    sim/lock-window-trim/corners/<trim-map>/raw_measures.csv

Writes (to --outdir, default sim/supply-sensitivity/corners/<this record>/):
    trim_msb_audit.csv      one row per committed steady-state log
    trim_msb_summary.txt    the same, reduced to the sentences the record quotes
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# The record whose `ff` cell programmed a code with its MSB set.
DEFAULT_SOURCE = "20260920-180604-0f91a9b"

# `sim/lock-window-trim`'s committed code map: t_win at all 16 codes across the
# 9 (temperature, supply) points of three bundles. It is the same artifact
# `window_crossing.csv` already cites for corroboration, at the same codes.
TRIM_MAP = os.path.join(
    "sim", "lock-window-trim", "corners", "20260917-185928-8adff3d", "raw_measures.csv"
)

# The bit the schematic dropped. `pll_top`'s LDT3 pad reached no gate inside
# the subcircuit, so the detector saw the low three bits of whatever was
# programmed.
MSB = 0b1000
LOW_BITS = 0b0111

# The stray xschem auto-named net `XLD`'s eighth terminal landed on. Named
# explicitly rather than pattern-matched: this audit is about one known defect
# in one committed export, not a search for others (that search is
# `design/lib/check-port-connectivity.sh`, which runs on every netlist).
STRAY_NET = "xdut.net1"
PAD_NODE = "ldt3"

# `run.sh`'s own assert threshold, transcribed: a flag is asserted when it
# stands at >= this fraction of the rail. Used only to re-derive `asserted`
# from the committed `lock_lvl_v` column, never to re-grade a corner.
ACC_LOCK_FRAC = 0.90

LOG_NAME_RE = re.compile(
    r"^(?P<deck>f\d+x?)_(?P<bundle>[a-z-]+)_(?P<temp>-?\d+)c_(?P<vdd>\d+\.\d+)v\.log$"
)
PARAM_RE = re.compile(r"^\.param\s+ldt(?P<bit>[0-3])_code\s*=\s*(?P<value>\d+)\s*$")
TSTOP_RE = re.compile(r"^\.param\s+tstop\s*=\s*(?P<value>\S+)\s*$")
NODE_RE = re.compile(r"^(?P<node>\S+)\s+(?P<value>-?[\d.]+(?:[eE][-+]?\d+)?)\s*$")


# --------------------------------------------------------------------------
# Pure functions. Each is unit-tested against analytically-known inputs in
# sim/tests/test_supply_sensitivity_trim_msb_audit.py -- a silent bug in any
# of them would change a decision record's conclusion.
# --------------------------------------------------------------------------


def requested_code(log_text: str) -> int | None:
    """The `LDT3:LDT0` code the DECK programmed, from its own `.param` lines.

    Returns None when the log does not carry all four -- a log from a deck
    that does not drive the trim at all must not be reported as code 0.
    """
    bits: dict[int, int] = {}
    for line in log_text.splitlines():
        m = PARAM_RE.match(line.strip())
        if m is not None:
            bits[int(m.group("bit"))] = int(m.group("value"))
    if len(bits) != 4:
        return None
    return sum((1 << bit) for bit, value in bits.items() if value)


def log_tstop(log_text: str) -> str:
    """The transient length this log ran at, from its own `.param tstop`.

    `run.sh`'s settling escalation re-runs the SAME steady-state deck at a
    longer `tstop` under an `f<N>x_` name, and the escalated run is the one
    whose numbers land in `supply_steady.csv`. Carrying `tstop` makes which
    of the two supplied a row visible instead of inferred.
    """
    for line in log_text.splitlines():
        m = TSTOP_RE.match(line.strip())
        if m is not None:
            return m.group("value")
    return ""


def node_dc(log_text: str, node: str) -> float | None:
    """The DC operating-point voltage ngspice printed for `node`.

    The operating-point table is `name<whitespace>value` lines; anything else
    in the log that happens to match that shape would have to begin with the
    exact node name to collide, so the lookup is exact-name rather than
    positional. Returns None when the node is absent, which is itself
    information: a node that does not exist was not in the netlist.
    """
    for line in log_text.splitlines():
        m = NODE_RE.match(line.strip())
        if m is not None and m.group("node") == node:
            return float(m.group("value"))
    return None


def msb_reached_the_cell(pad_v: float | None, stray_v: float | None) -> bool | None:
    """Did the `LDT3` pad's level reach the detector?

    True when there is no stray net at all (the post-fix netlist: the pad IS
    the instance terminal). False when a stray net exists and sits at a level
    that disagrees with the pad -- the defect. None when the log carries
    neither node, i.e. this audit cannot tell.

    The comparison is against half the pad's own level rather than against a
    fixed threshold, so it does not need to know the rail.
    """
    if pad_v is None:
        return None
    if stray_v is None:
        return True
    if pad_v == 0.0:
        # A pad at 0 V is indistinguishable from a stray net at 0 V: the bit
        # is low either way, so the code the detector saw is the code
        # programmed and this row carries no evidence about the wiring.
        return None
    return stray_v >= 0.5 * pad_v


def effective_code(code: int, msb_connected: bool | None) -> int:
    """The code the DETECTOR saw.

    `msb_connected is False` is the defect: the detector's LDT3 input is a
    gate on a net nothing drives, which ngspice resolves to 0 V, so the top
    bit reads low whatever the pad does.
    """
    if msb_connected is False:
        return code & LOW_BITS
    return code


def asserted_from_level(lock_lvl_v: float, vdd_v: float) -> bool:
    """`run.sh`'s own assert criterion, re-derived from the committed level."""
    return lock_lvl_v >= ACC_LOCK_FRAC * vdd_v


def predict_assert(t_win_ns: float | None, abs_phi_ns: float) -> str:
    """What the code map predicts the flag does, as the one-sided bound it is.

    `window_crossing.csv`'s header states the rule this transcribes: the
    observable assert window is never SMALLER than `t_win`, so `t_win` above
    the offset predicts an assert. Below it, the bound says nothing -- the
    observable window could still be above the offset -- so the answer is
    `unpredicted`, not `no`.
    """
    if t_win_ns is None:
        return "unknown"
    return "assert" if t_win_ns > abs_phi_ns else "unpredicted"


def crossing_verdict(dr013_crossed: bool, asserted: bool) -> str:
    """The source record's own verdict key, transcribed and never typed.

    inferred crossed + asserted        -> confirmed
    inferred crossed + not asserted    -> refuted
    inferred not-crossed + asserted    -> moved
    inferred not-crossed + not         -> confirmed
    """
    if dr013_crossed:
        return "confirmed" if asserted else "refuted"
    return "moved" if asserted else "confirmed"


def parse_log_name(name: str) -> dict[str, str] | None:
    """(deck, bundle, temp_c, vdd_v) from a committed per-corner log name."""
    m = LOG_NAME_RE.match(name)
    if m is None:
        return None
    return {
        "deck": m.group("deck"),
        "bundle": m.group("bundle"),
        "temp_c": m.group("temp"),
        "vdd_v": m.group("vdd"),
    }


# --------------------------------------------------------------------------
# Readers over committed artifacts.
# --------------------------------------------------------------------------


def _read_csv_rows(path: str) -> list[dict[str, str]]:
    """Rows of a committed CSV, skipping this repo's `#`-comment preamble."""
    with open(path, encoding="utf-8") as fh:
        body = [line for line in fh if not line.startswith("#")]
    return list(csv.DictReader(body))


def read_trim_map(repo_root: str) -> dict[tuple[str, str, str, int], tuple[float, float]]:
    """(bundle, temp_c, vdd_v, code) -> (t_win_rise_ns, t_win_fall_ns).

    Keys are normalised to the string forms the supply-sensitivity logs use,
    so the join does not depend on how either campaign happened to format a
    float ('3.3' there, '3.63' here, '27.0' vs '27').
    """
    out: dict[tuple[str, str, str, int], tuple[float, float]] = {}
    for row in _read_csv_rows(os.path.join(repo_root, TRIM_MAP)):
        key = (
            row["corner"],
            str(int(float(row["temp_c"]))),
            f"{float(row['vdd']):.2f}",
            int(row["trim"].lstrip("c")),
        )
        out[key] = (float(row["twin_r"]) * 1e9, float(row["twin_f"]) * 1e9)
    return out


def read_steady(repo_root: str, source: str) -> dict[tuple[str, str, str], dict[str, str]]:
    """(bundle, temp_c, vdd_v) -> the source record's own steady-state row."""
    path = os.path.join(
        repo_root, "sim", "supply-sensitivity", "corners", source, "supply_steady.csv"
    )
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in _read_csv_rows(path):
        key = (
            row["bundle"],
            str(int(float(row["temp_c"]))),
            f"{float(row['vdd_v']):.2f}",
        )
        out[key] = row
    return out


def audit(repo_root: str, source: str) -> list[dict[str, object]]:
    """One row per committed per-corner log of the source record."""
    corners = os.path.join(repo_root, "sim", "supply-sensitivity", "corners", source)
    trim_map = read_trim_map(repo_root)
    steady = read_steady(repo_root, source)

    rows: list[dict[str, object]] = []
    for name in sorted(os.listdir(corners)):
        if not name.endswith(".log"):
            continue
        meta = parse_log_name(name)
        if meta is None:
            continue
        with open(os.path.join(corners, name), encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        code = requested_code(text)
        if code is None:
            continue
        pad_v = node_dc(text, PAD_NODE)
        stray_v = node_dc(text, STRAY_NET)
        connected = msb_reached_the_cell(pad_v, stray_v)
        eff = effective_code(code, connected)

        key = (meta["bundle"], meta["temp_c"], meta["vdd_v"])
        srow = steady.get(key)

        row: dict[str, object] = {
            "log": name,
            "deck": meta["deck"],
            "bundle": meta["bundle"],
            "temp_c": meta["temp_c"],
            "vdd_v": meta["vdd_v"],
            "code_requested": code,
            "bits_requested": format(code, "04b"),
            "ldt3_pad_v": "" if pad_v is None else f"{pad_v:g}",
            "stray_net_v": "" if stray_v is None else f"{stray_v:g}",
            "msb_reached_cell": {True: "yes", False: "no", None: "unknown"}[connected],
            "code_effective": eff,
            "bits_effective": format(eff, "04b"),
            "code_corrupted": "yes" if eff != code else "no",
            "log_tstop": log_tstop(text),
            "row_tstop": "" if srow is None else srow.get("tstop", ""),
            "supplied_row": "",
        }
        row["supplied_row"] = (
            "yes" if srow is not None and row["log_tstop"] == row["row_tstop"] else "no"
        )

        if srow is None:
            # A deck whose metrics this record does not tabulate per supply
            # point (the step/ramp deck). The node evidence above still
            # stands; the window comparison needs a settled offset it has no
            # row for, so it is left blank rather than guessed.
            row.update(
                {
                    "abs_phi_b_ns": "",
                    "lock_lvl_v": "",
                    "asserted": "",
                    "twin_requested_ns": "",
                    "twin_effective_ns": "",
                    "predict_at_requested": "",
                    "predict_at_effective": "",
                    "discriminates": "",
                }
            )
            rows.append(row)
            continue

        abs_phi_ns = abs(float(srow["phi_b_s"])) * 1e9
        lock_lvl = float(srow["lock_lvl_v"])
        vdd = float(srow["vdd_v"])
        is_asserted = asserted_from_level(lock_lvl, vdd)

        t_req = trim_map.get(key + (code,))
        t_eff = trim_map.get(key + (eff,))
        # The fall edge is the smaller of the two measured edges at every
        # point of the committed map, so it is the conservative half of the
        # one-sided bound: using it cannot manufacture an `assert` prediction
        # the rise edge would not also give.
        p_req = predict_assert(None if t_req is None else min(t_req), abs_phi_ns)
        p_eff = predict_assert(None if t_eff is None else min(t_eff), abs_phi_ns)

        row.update(
            {
                "abs_phi_b_ns": f"{abs_phi_ns:.4f}",
                "lock_lvl_v": f"{lock_lvl:g}",
                "asserted": "yes" if is_asserted else "no",
                "twin_requested_ns": ""
                if t_req is None
                else f"{t_req[0]:.4f}/{t_req[1]:.4f}",
                "twin_effective_ns": ""
                if t_eff is None
                else f"{t_eff[0]:.4f}/{t_eff[1]:.4f}",
                "predict_at_requested": p_req,
                "predict_at_effective": p_eff,
                # A point discriminates when the two codes predict different
                # things AND the observation matches exactly one of them.
                # Gated on `supplied_row` so an escalated re-run and the
                # short run it replaced count as ONE measurement, not two.
                "discriminates": "yes"
                if row["supplied_row"] == "yes"
                and p_req != p_eff
                and (("assert" in (p_req, p_eff)) and not is_asserted)
                else "no",
            }
        )
        rows.append(row)

    return rows


FIELDS = [
    "log",
    "deck",
    "bundle",
    "temp_c",
    "vdd_v",
    "code_requested",
    "bits_requested",
    "ldt3_pad_v",
    "stray_net_v",
    "msb_reached_cell",
    "code_effective",
    "bits_effective",
    "code_corrupted",
    "log_tstop",
    "row_tstop",
    "supplied_row",
    "abs_phi_b_ns",
    "lock_lvl_v",
    "asserted",
    "twin_requested_ns",
    "twin_effective_ns",
    "predict_at_requested",
    "predict_at_effective",
    "discriminates",
]

HEADER = """\
# campaign: supply-sensitivity (issue #515 -- which trim code the loop ran at)
# source_record: {source}
# generated_utc: {stamp}
# re-simulates: NOTHING. Every column is read out of artifacts committed under
#   prior records; no PDK file is opened and no simulator is invoked.
# code_requested/bits_requested: the LDT3:LDT0 code the DECK programmed, from
#   the log's own `.param ldt<i>_code` lines
# ldt3_pad_v: the DC level of pll_top's LDT3 PAD in the same log
# stray_net_v: the DC level of `{stray}`, the xschem auto-named net XLD's
#   eighth terminal landed on while the pad went nowhere (issue #515). Blank
#   means the log has no such node -- a netlist where the pad IS the terminal
# msb_reached_cell: no = the pad's level did not reach the detector
# code_effective: the code the DETECTOR saw -- `code & 0b0111` when the MSB
#   did not reach it
# log_tstop/row_tstop/supplied_row: run.sh's settling escalation re-runs the
#   SAME steady-state deck at a longer tstop under an `f<N>x_` name, so two
#   logs can share one (bundle, temperature, supply). supplied_row = yes marks
#   the one whose tstop matches the committed supply_steady.csv row, i.e. the
#   run that actually produced the measurement
# abs_phi_b_ns/lock_lvl_v/asserted: this point's own settled |static phase
#   offset| and lock level, read from supply_steady.csv; `asserted` re-derives
#   run.sh's own >= {frac} x vdd criterion from the committed level
# twin_requested_ns/twin_effective_ns: rise/fall t_win at the SAME (bundle,
#   temperature, supply) for each code, from sim/lock-window-trim's committed
#   1872-point code map ({trim_map}) -- CORROBORATION from a different
#   campaign at a different f_ref, exactly as window_crossing.csv cites it
# predict_at_*: the one-sided bound window_crossing.csv's header states -- the
#   observable window is never smaller than t_win, so t_win > |phi_b| predicts
#   `assert`; below it the bound predicts nothing (`unpredicted`)
# discriminates: yes = the two codes predict different flags and the observed
#   flag matches only the effective one
"""


def write_outputs(rows: list[dict[str, object]], outdir: str, source: str, stamp: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "trim_msb_audit.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(
            HEADER.format(
                source=source,
                stamp=stamp,
                stray=STRAY_NET,
                frac=ACC_LOCK_FRAC,
                trim_map=TRIM_MAP,
            )
        )
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    corrupted = [r for r in rows if r["code_corrupted"] == "yes"]
    discriminating = [r for r in rows if r["discriminates"] == "yes"]
    lines = [
        f"source record: {source}",
        f"logs audited: {len(rows)}",
        f"points whose programmed code did NOT reach the detector: {len(corrupted)}",
    ]
    for r in corrupted:
        lines.append(
            f"  {r['log']}: programmed {r['code_requested']} ({r['bits_requested']}),"
            f" detector saw {r['code_effective']} ({r['bits_effective']});"
            f" pad {r['ldt3_pad_v']} V, {STRAY_NET} {r['stray_net_v']} V"
        )
    lines.append(f"points that DISCRIMINATE between the two codes: {len(discriminating)}")
    for r in discriminating:
        lines.append(
            f"  {r['log']}: |phi_b| {r['abs_phi_b_ns']} ns,"
            f" t_win at {r['code_requested']} = {r['twin_requested_ns']} ns"
            f" -> predicts {r['predict_at_requested']};"
            f" t_win at {r['code_effective']} = {r['twin_effective_ns']} ns"
            f" -> predicts {r['predict_at_effective']};"
            f" observed asserted={r['asserted']}"
        )
    txt_path = os.path.join(outdir, "trim_msb_summary.txt")
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument("--outdir", default=None)
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--stamp", default="")
    args = parser.parse_args(argv)

    outdir = args.outdir or os.path.join(
        args.repo_root, "sim", "supply-sensitivity", "corners", args.source
    )
    rows = audit(args.repo_root, args.source)
    if not rows:
        print(f"FAIL: no per-corner logs found under record {args.source}", file=sys.stderr)
        return 1
    write_outputs(rows, outdir, args.source, args.stamp)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
