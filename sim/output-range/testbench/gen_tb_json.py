#!/usr/bin/env python3
"""Generate (or check) sim/output-range/testbench/tb.json.

The manifest has 90 sweep points -- 45 PVT points x the two band edges -- each
with its own per-corner Vctrl seed.  The seed is NOT recomputed here: it is read
from `run.sh --plan`, i.e. from run.sh's own `seed_for_corner` bash function,
which is what produced the baseline records' seeds.  The static band / divider /
Icp-trim / window-trim bits come from sim/lib/pll_top_dut.sh's `cloop_*`
encoders in the same way.  Nothing about the design is hand-transcribed.

    python3 gen_tb_json.py            # rewrite tb.json
    python3 gen_tb_json.py --check    # exit 1 if tb.json is not what this emits
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
TB = HERE / "tb.json"

#: (edge, fout, band, n) -- run.sh's EDGES table: band bits and N per edge.
EDGES = {"lo": ("10e6", 1, 8), "hi": ("200e6", 7, 32)}
ICP_CODE = 2
WINDOW_TRIM = 8
SUPPLY_ALIAS = {"2.97": "low", "3.30": "nom", "3.63": "high"}
POS_ID = {"in": "in", "below": "below", "above": "above"}


def _bash(script):
    out = subprocess.run(
        ["bash", "-c", script], check=True, capture_output=True, text=True, cwd=SIM
    ).stdout
    return out


def _codes(line):
    return dict(tok.split("=") for tok in line.split())


def static_codes():
    """{edge: {name: value}} from the shared pll_top_dut.sh encoders."""
    out = {}
    for edge, (_fout, band, n) in EDGES.items():
        text = _bash(
            ". lib/simenv.sh; . lib/pll_top_dut.sh; "
            f"cloop_band_params {band}; cloop_divider_params {n}; "
            f"cloop_trim_params {ICP_CODE}; cloop_window_trim_params {WINDOW_TRIM}"
        )
        codes = {}
        for line in text.splitlines():
            codes.update(_codes(line))
        out[edge] = codes
    return out


def plan_rows():
    text = _bash("bash output-range/testbench/run.sh --plan")
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 11 and parts[3] in EDGES:
            corner, temp, vdd, edge, fout, _b2, _b1, _b0, n, seed, pos = parts
            rows.append((corner, temp, vdd, edge, fout, int(n), seed, pos))
    return rows


def op_id(edge, pos, seed):
    return f"{edge}{POS_ID[pos]}{seed.replace('.', 'p')}"


def op_params(edge, fout, n, seed, codes):
    fref = "%.8g" % (float(fout) / n)
    tstop = "%.6g" % min(20.0 / float(fref), 2e-6)
    tstep = "%.6g" % (1.0 / (50.0 * float(fout)))
    tforce = "%.6g" % (0.02 / float(fref))
    p = {
        "fref": fref,
        "vctrl_ic": seed,
        "ktforce": tforce,
        "ktstep": tstep,
        "ktstop": tstop,
    }
    p.update(codes)
    return p


METHODOLOGY = [
    "**Harness form of an existing campaign (#878), not a new claim.** The campaign's question is unchanged from its baseline records: for each of the two ratified output-band EDGE frequencies (10 MHz `lo`, 200 MHz `hi`), does the closed `pll_top` loop lock there, and with how much control-voltage headroom to the 0.9-2.7 V usable window. The deck is the committed `tb_output_range.sp` re-expressed as a harness fragment (`tb_output_range_harness.sp`; its header lists the mechanical differences). Nothing about the design, the stimulus, the convergence tolerances or the 100 ps internal-timestep ceiling (#65) changed.",
    "**Grid: 45 PVT points x 2 edges = 90 rows**, the baseline's grid, expressed as 90 `grid` blocks (one per row) because the Vctrl seed is per (corner, temperature, supply, edge). Each block names the sweep point `op` that carries that row's seed, band code, divider code, f_ref and transient controls.",
    "**Seeds are the baseline's, by construction.** `gen_tb_json.py` obtains every seed by running `run.sh --plan`, i.e. `seed_for_corner` itself (a bash function over `sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv`); the static band / divider / Icp-trim / window-trim bits come from `sim/lib/pll_top_dut.sh`'s `cloop_*` encoders. `gen_tb_json.py --check` (run by the unit test) fails if this manifest drifts from them. The seed rule, including rows seeded at the nearer rail (`below` / `above`, reported OUT-OF-WINDOW), is unchanged.",
    "**Status rule (as run.sh's `run_one`):** PASS if the lock detector asserted at least once (`t_lock_last_rise` measured) and was still high at the end of the window (`lock_at_end` >= 1.5 V); else FAIL; OUT-OF-WINDOW overrides when the seed was clamped to a rail; ERROR when the transient produced no `vctrl_final` (including a point the execution backend killed at its `--timeout` budget, which this record reports as no-measurement, never as a simulator verdict). The PFD DN-branch guard (#69) is scored three-valued exactly as in run.sh (floor 3e-4 of the supply).",
    "**Comparison against the baseline** is the union of two records: `20260819-160843-4e32f91` (89 rows) and `20260819-190341-70a4128` (which replaces that record's `ff`/27 C/3.30 V `hi` row only). Per-row tolerances (proposals, never widened after the fact): Status exact; `vctrl_final` 5 mV absolute (runs converge within the simulator's voltage tolerance, reltol 1e-3); DN-guard verdict exact (mean DN is reported with its delta and graded by the guard verdict, because it spans six decades between SUSPECT and PASS rows). Both baseline records are read-only.",
    "**The `ff`/27 C/3.30 V `hi` row is a known marginal row** (a +1e-7 V seed perturbation moved the baseline between a non-terminating transient and a clean FAIL). It is compared against the second record's control row and reported separately; a flip on it alone is documented, not counted as a regression.",
    "**Simulator / host delta.** Both baseline records were taken with ngspice-46 on Darwin 25.6.0 / arm64; harness runs on this project's batch fleet use ngspice-46 on Linux x86_64. The record's Environment provenance is authoritative for this run. Read DR-028 and DR-039 for what the batch backend does and does not guarantee.",
    "**Limitations (unchanged from the baseline):** schematic-level, no parasitics; nominal skew only (`sw_stat_global = sw_stat_mismatch = 0`); one band/N design point per edge; the 2 us window is only ~2.5 reference cycles for `lo`, so a `lo` FAIL bounds nothing about whether that corner eventually locks.",
]


def build():
    codes = static_codes()
    rows = plan_rows()
    if len(rows) != 90:
        raise SystemExit(f"run.sh --plan returned {len(rows)} rows, expected 90")
    points, grid = {}, []
    for corner, temp, vdd, edge, fout, n, seed, pos in rows:
        oid = op_id(edge, pos, seed)
        params = op_params(edge, fout, n, seed, codes[edge])
        if oid in points and points[oid]["params"] != params:
            raise SystemExit(f"op id {oid} maps to two different parameter sets")
        points[oid] = {"description": f"{edge} edge ({fout} Hz, N={n}), seed {seed} V ({pos})",
                       "params": params}
        grid.append(
            {
                "description": f"{corner} / {temp} C / {vdd} V, {edge} edge: Vctrl seed {seed} V "
                f"({pos} the 0.9-2.7 V window) from run.sh's seed_for_corner",
                "corners": [corner],
                "temperatures_c": [float(temp)],
                "supplies": [SUPPLY_ALIAS[vdd]],
                "axes": {"op": [oid]},
            }
        )
    ordered = {k: points[k] for k in sorted(points)}
    return {
        "name": "output-range",
        "description": "closed-loop output-band edge coverage of pll_top: does the loop lock at the ratified 10 MHz and 200 MHz band edges, and with what control-voltage headroom to the 0.9-2.7 V window, over the 45-point PVT grid (harness form of the #12 campaign; baseline records 20260819-160843-4e32f91 + 20260819-190341-70a4128)",
        "claim": "#12 -> #878 (design-input claim, not a spec line) -- the closed pll_top loop reaches both ratified output-band edge frequencies (spec/pll.md output band, 10-200 MHz) across the mandated PVT matrix, with Vctrl margin to the 0.9-2.7 V usable window; reproduced under the harness so the PVT coverage is accounted for and the grid can run on the batch backend.",
        "methodology": METHODOLOGY,
        "dut": ["design/netlist/pll_top.spice"],
        "netlist": "tb_output_range_harness.sp",
        "nominal_supply_v": 3.3,
        "supply_tolerance": 0.1,
        "temperatures_c": [-40, 27, 125],
        "corners": ["mos"],
        "options": ["rshunt=1e12", "itl4=200", "reltol=1e-3", "abstol=1e-9", "vntol=1e-4", "chgtol=1e-13"],
        "params": {
            "ktmax": "100p",
            "cpb0_code": "0",
            "cpb1_code": "1",
            "ldt0_code": "0",
            "ldt1_code": "0",
            "ldt2_code": "0",
            "ldt3_code": "1",
        },
        "sweeps": {
            "op": {
                "description": "the per-row operating point: edge, per-corner Vctrl seed (and whether it was clamped to a rail), band code, divider code, f_ref and transient controls. Point id = <edge><in|below|above><seed with . as p>.",
                "points": ordered,
            }
        },
        "grid": grid,
        "analyses": [
            "save v(vctrl) v(lock) v(xdut.up) v(xdut.dn) v(xdut.vwin)",
            "tran {ktstep} {ktstop} 0 {ktmax}",
        ],
        "raw_measures": {
            "t_lock_last_rise": {
                "analysis": "tran",
                "expr": "when v(lock)='0.5*vdd_val' rise=last",
                "optional": True,
            },
            "lock_at_end": {"analysis": "tran", "expr": "find v(lock) at='ktstop-1p'"},
            "vctrl_final": {"analysis": "tran", "expr": "find v(vctrl) at='ktstop-1p'"},
            "dn_lvl": {"analysis": "tran", "expr": "avg v(xdut.dn) from='0.9*ktstop' to='ktstop-1p'"},
        },
        "topology_groups": {
            "headroom": {
                "description": "the campaign's measurand: where the control node settles",
                "measures": ["vctrl_final", "vctrl_margin_lo_v", "vctrl_margin_hi_v"],
            },
            "lock": {
                "description": "did the real lock detector assert and hold",
                "measures": ["t_lock_last_rise", "lock_at_end", "pass_lock"],
            },
            "integration": {
                "description": "the PFD DN-branch guard (#69): the internal timestep ceiling was honoured",
                "measures": ["dn_lvl"],
            },
        },
        "derived": {
            "module": "derive.py",
            "measures": ["vctrl_margin_lo_v", "vctrl_margin_hi_v", "pass_lock"],
            "tables": ["output_range_rows", "row_comparison", "baseline_comparison"],
        },
        "checks": {
            "vctrl_final": {"min_measured_points": 87},
            "dn_lvl": {"min_measured_points": 87},
        },
    }


def main(argv):
    text = json.dumps(build(), indent=2) + "\n"
    if "--check" in argv:
        if not TB.exists() or TB.read_text() != text:
            print("tb.json is stale: run gen_tb_json.py", file=sys.stderr)
            return 1
        return 0
    TB.write_text(text)
    print(f"wrote {TB} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
