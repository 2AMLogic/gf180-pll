#!/usr/bin/env python3
"""Diff every configured number in tb.json against the thing that owns it.

`tb.json` carries 30-odd static bits, three per-bundle trim codes, three band
codes, three warm-start voltages and a ladder of phase steps. Every one of them
is a *derivation* from something else in this repository -- a ratified rule, a
committed record, or an encoder in `sim/lib/pll_top_dut.sh` -- and a
transcription error in any of them would mean measuring a mis-configured part
and reporting the result as evidence about a compliant one. That is exactly what
DR-025 and DR-026 each caught after the fact.

So nothing here is a new decision. This script re-derives each number from its
owner and fails if the manifest disagrees:

1. **The divider, Icp and band bits** come from `sim/lib/pll_top_dut.sh`'s own
   encoders (`cloop_divider_params`, `cloop_trim_params`, `cloop_band_params`,
   `cloop_window_trim_params`) -- the single owner of "what the configuration
   bits mean" for every closed-loop campaign here.
2. **The band code and the warm-start control voltage** come from
   `sim/supply-sensitivity/testbench/run.sh --op-table`, which applies
   `spec/pll.md`'s normative band-selection rule to `sim/vco-tuning-range`'s
   committed f(Vctrl) record. That campaign owns the derivation; this script
   calls it rather than reimplementing it, so the two can never drift.
3. **The per-bundle trim code** is re-derived here from
   `sim/lock-window-proxy`'s committed 16-code window map by applying the
   normative trim-code rule directly -- the code whose `t_win` at 27 C /
   3.30 V is nearest 1.343 ns in the log sense.
4. **The phase-step ladder** is checked against the deck's own structural
   requirement: `|delta| < 0.2 * tref`, which is what keeps the two-source
   select instant inside a low plateau of both sources, plus the step instant
   and the post-step window both fitting inside `ktstop`.

Usage: `python3 sim/lock-window-bisection/testbench/check_config.py`
Exit 0 and a per-item OK line, or exit 1 naming every disagreement.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TB = HERE / "tb.json"

TARGET_NS = 1.343
WINMAP = (REPO / "sim" / "lock-window-proxy" / "corners"
          / "20260925-050022-6d57802" / "raw_measures.csv")
REFERENCE_TEMP_C = "27.0"
REFERENCE_VDD = "3.3"

failures: list[str] = []
notes: list[str] = []


def ok(msg: str) -> None:
    notes.append("OK   " + msg)


def bad(msg: str) -> None:
    failures.append("FAIL " + msg)


def shell(script: str) -> str:
    return subprocess.run(
        ["bash", "-c", script], cwd=REPO, check=True,
        capture_output=True, text=True,
    ).stdout


def encoders() -> dict[str, str]:
    """Every static bit `sim/lib/pll_top_dut.sh` would emit, as one dict."""
    out = shell(
        ". sim/lib/simenv.sh >/dev/null 2>&1; . sim/lib/pll_top_dut.sh >/dev/null 2>&1; "
        "echo \"$(cloop_divider_params 8) $(cloop_trim_params 2)\"; "
        "for b in 5 6; do echo \"BAND$b $(cloop_band_params $b)\"; done; "
        "for c in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do "
        "echo \"WIN$c $(cloop_window_trim_params $c)\"; done"
    )
    flat: dict[str, str] = {}
    grouped: dict[str, dict[str, str]] = {}
    for line in out.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0].startswith(("BAND", "WIN")):
            grouped[fields[0]] = dict(f.split("=", 1) for f in fields[1:])
        else:
            flat.update(dict(f.split("=", 1) for f in fields))
    flat["_grouped"] = grouped  # type: ignore[assignment]
    return flat


def op_table() -> dict[str, tuple[str, str]]:
    """{bundle: (band, vctrl@3.30V)} at 27 C, from supply-sensitivity's owner."""
    out = shell("./sim/supply-sensitivity/testbench/run.sh --op-table")
    table: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        fields = line.strip().split(",")
        if len(fields) != 6 or fields[1] != "27":
            continue
        if fields[0] in table:  # the second (50 MHz) block -- first wins
            continue
        table[fields[0]] = (fields[2], fields[4])
    return table


def rule_codes() -> dict[str, int]:
    """{bundle: code} -- the trim rule applied to the committed 16-code map."""
    with WINMAP.open() as fh:
        rows = list(csv.DictReader(fh))
    codes: dict[str, int] = {}
    for row in rows:
        if row["temp_c"] != REFERENCE_TEMP_C or row["vdd"] != REFERENCE_VDD:
            continue
        best, best_dist = None, None
        for code in range(16):
            twin_ns = float(row["twin_c%d" % code]) * 1e9
            dist = abs(math.log(twin_ns / TARGET_NS))
            if best_dist is None or dist < best_dist:
                best, best_dist = code, dist
        codes[row["corner"]] = best
    return codes


def main() -> int:
    manifest = json.loads(TB.read_text())
    params = manifest["params"]
    enc = encoders()
    grouped = enc.pop("_grouped")

    # 1. static bits (divider + Icp) against the encoders
    for key, want in enc.items():
        got = params.get(key)
        if got is None:
            bad("tb.json params has no %s (encoder says %s)" % (key, want))
        elif got != want:
            bad("tb.json params %s=%s, sim/lib/pll_top_dut.sh says %s" % (key, got, want))
    ok("%d divider/Icp bits match sim/lib/pll_top_dut.sh's encoders "
       "(N=8, Icp trim code 2)" % len(enc))

    # 2/3. per-bundle op points: band + vstart from supply-sensitivity's
    #      derivation, trim code from the trim rule on the committed map
    ops = manifest["sweeps"]["op"]["points"]
    optab = op_table()
    codes = rule_codes()
    blocks = {tuple(b["corners"])[0]: b for b in manifest["grid"]}
    for bundle, block in sorted(blocks.items()):
        pid = block["axes"]["op"][0]
        got = ops[pid]["params"]
        if bundle not in optab:
            bad("%s: supply-sensitivity --op-table has no 27 C row" % bundle)
            continue
        band, vctrl = optab[bundle]
        want_band = grouped["BAND" + band]
        for key, value in want_band.items():
            if got.get(key) != value:
                bad("%s op point %s: %s=%s, band-selection rule says band %s -> %s=%s"
                    % (bundle, pid, key, got.get(key), band, key, value))
        if got.get("vstart") != vctrl:
            bad("%s op point %s: vstart=%s, supply-sensitivity's op table says %s"
                % (bundle, pid, got.get("vstart"), vctrl))
        if bundle not in codes:
            bad("%s: committed window map has no 27 C / 3.30 V row" % bundle)
            continue
        want_win = grouped["WIN%d" % codes[bundle]]
        for key, value in want_win.items():
            if got.get(key) != value:
                bad("%s op point %s: %s=%s, trim rule selects code %d -> %s=%s"
                    % (bundle, pid, key, got.get(key), codes[bundle], key, value))
        ok("%-8s band %s (rule), vstart %s V (committed f(Vctrl) record), "
           "trim code %2d (rule on the committed 16-code map)"
           % (bundle, band, vctrl, codes[bundle]))

    # 4. the ladder's structural bounds
    fref = float(params["fref"])
    tref = 1.0 / fref
    nstep = float(params["nstep"])
    ktstop = float(params["ktstop"])
    tphi = 0.5 * tref + nstep * tref
    guard = 0.2 * tref
    worst = 0.0
    for pid, point in manifest["sweeps"]["d"]["points"].items():
        delta = float(point["params"]["delta"])
        worst = max(worst, abs(delta))
        if abs(delta) >= guard:
            bad("d point %s: |delta|=%g s is not < 0.2*tref=%g s, so the "
                "two-source select instant is no longer inside a low plateau of "
                "both sources" % (pid, abs(delta), guard))
        spelled = ("d0000" if delta == 0
                   else ("dp" if delta > 0 else "dm") + "%04d" % round(abs(delta) * 1e12))
        if pid != spelled:
            bad("d point %s is spelled for %g ps, its delta is %g ps"
                % (pid, float(pid[2:]) if pid != "d0000" else 0, delta * 1e12))
    if tphi + 8 * tref > ktstop:
        bad("ktstop=%g s leaves under 8 reference periods after the step at "
            "tphi=%g s; the detector's integrator needs a real post-step window"
            % (ktstop, tphi))
    ok("ladder: %d rungs, worst |delta| %.0f ps against the %.0f ps select guard; "
       "step at %.3f us, %.0f reference periods of post-step window inside "
       "ktstop=%.3f us"
       % (len(manifest["sweeps"]["d"]["points"]), worst * 1e12, guard * 1e12,
          tphi * 1e6, (ktstop - tphi) / tref, ktstop * 1e6))

    for line in notes:
        print(line)
    for line in failures:
        print(line, file=sys.stderr)
    if failures:
        print("\n%d disagreement(s) -- tb.json does not match what owns these "
              "numbers." % len(failures), file=sys.stderr)
        return 1
    print("\nall configured numbers agree with their owners.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
