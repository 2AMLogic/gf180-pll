#!/usr/bin/env python3
"""gf180-pll :: period-jitter :: ISF bring-up -- render results/ as markdown.

Every number quoted in this directory's README.md comes out of here, so that a
reader can regenerate the table rather than trust that it was transcribed
correctly:

    sim/period-jitter/isf-bringup/summarize.py > sim/period-jitter/isf-bringup/results/SUMMARY.md

Reads only `results/*.json`; runs no simulation and needs no PDK.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(results: Path, name: str):
    p = results / f"{name}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def _si(x, unit, digits=4):
    for scale, pfx in ((1e12, "p"), (1e9, "n"), (1e6, "u"), (1e3, "m")):
        if abs(x) * scale >= 1.0 and abs(x) * scale < 1e4:
            return f"{x * scale:.{digits}g} {pfx}{unit}"
    return f"{x:.{digits}g} {unit}"


def _rows_by_phase(res):
    return sorted(res["rows"], key=lambda r: (r["node"], r["phase_cycles"]))


def section_period(res, out):
    if not res:
        return
    out.append("## The free-running reference\n")
    out.append(
        f"- f0 = **{res['f0_Hz'] / 1e6:.4f} MHz** "
        f"(T = {res['period_s'] * 1e9:.6f} ns), {res['n_crossings']} crossings "
        f"in the window\n"
        f"- first mid-supply crossing at {res['first_crossing_s'] * 1e9:.3f} ns\n"
        f"- period peak-to-peak over cycles 5..end: "
        f"**{res['settled_period_ptp_s'] * 1e15:.3g} fs** "
        f"({res['settled_period_ptp_s'] / res['period_s'] * 1e6:.2g} ppm of T) "
        "-- the deck's own numerical floor, and the reason an injection is not "
        "made before ~6 cycles\n"
    )
    per = res["periods_s"]
    out.append("\n| cycle | period (ns) |\n|---|---|")
    for i, p in enumerate(per[:8]):
        out.append(f"| {i} | {p * 1e9:.6f} |")
    out.append("")


def section_gamma(res, out, title, note=""):
    if not res:
        return
    out.append(f"## {title}\n")
    if note:
        out.append(note + "\n")
    out.append(
        f"f0 from the reference copy: {res['f0_Hz'] / 1e6:.4f} MHz; "
        f"{res.get('elapsed_s', float('nan')):.0f} s of ngspice for "
        f"{len(res['rows'])} injected copies + 1 reference, one deck.\n"
    )
    out.append(
        "| node | phase x/2pi | dq (fC) | dt (ps) | tail p-p (fs) | "
        "tail drift (fs/cycle) | h = dphi/dq (rad/C) |"
    )
    out.append("|---|---|---|---|---|---|---|")
    for r in _rows_by_phase(res):
        out.append(
            f"| {r['node']}{r['stage']} | {r['phase_cycles']:.4f} | "
            f"{r['dq_C'] * 1e15:g} | {r['dt_s'] * 1e12:+.4f} | "
            f"{r['dt_spread_s'] * 1e15:.2f} | "
            f"{r['dt_drift_s_per_cycle'] * 1e15:+.3f} | "
            f"{r['h_rad_per_C']:+.4e} |"
        )
    out.append("")
    by_node = {}
    for r in res["rows"]:
        by_node.setdefault(r["node"], []).append(r["h_rad_per_C"])
    for node, hs in sorted(by_node.items()):
        rms = math.sqrt(sum(h * h for h in hs) / len(hs))
        out.append(
            f"- **{node}**: h_rms over the sampled phases = {rms:.4e} rad/C, "
            f"|h|max = {max(abs(h) for h in hs):.4e} rad/C"
        )
    worst = max(res["rows"], key=lambda r: r["dt_spread_s"])
    out.append(
        f"- worst settled-tail peak-to-peak across all copies: "
        f"{worst['dt_spread_s'] * 1e15:.2f} fs at phase "
        f"{worst['phase_cycles']:.4f} "
        f"(|dt| = {abs(worst['dt_s']) * 1e12:.3f} ps)"
    )
    out.append("")


def _pivot(runs, key, keyfmt):
    """phase -> {key value -> h}."""
    table = {}
    for run in runs:
        for r in run["rows"]:
            table.setdefault(r["phase_cycles"], {})[keyfmt(run[key])] = r[
                "h_rad_per_C"
            ]
    return table


def section_sweep(res, out, *, title, key, keyfmt, colname, blurb):
    """One convergence sweep, compared against the limit it approaches.

    WHICH COLUMN IS THE REFERENCE MATTERS, and getting it wrong inverts the
    conclusion rather than perturbing it.  Both sweeps here approach a limit at
    the SMALLEST value of their swept parameter -- `tmax -> 0` is the exact
    integration, `dq -> 0` is the ISF's own definition -- so the reference is
    `min(key)`, chosen by value and not by column position.  (An earlier
    revision of this file took `vals[-1]`, which is the finest ceiling for the
    timestep sweep, whose runs happen to descend, and the *coarsest* charge for
    the linearity sweep, whose runs ascend: it reported the linearity spread
    against the least linear charge in the set.)
    """
    if not res:
        return
    out.append(f"## {title}\n")
    out.append(blurb + "\n")
    table = _pivot(res["runs"], key, keyfmt)
    cols = [keyfmt(run[key]) for run in res["runs"]]
    ref_col = keyfmt(min(run[key] for run in res["runs"]))
    out.append(
        f"| phase x/2pi | " + " | ".join(f"h @ {c}" for c in cols)
        + f" | worst dev. vs. {ref_col} |"
    )
    out.append("|---" * (len(cols) + 2) + "|")
    worst = 0.0
    worst_adj = 0.0
    for ph in sorted(table):
        row = table[ph]
        vals = [row.get(c) for c in cols]
        fine = row.get(ref_col)
        dev = (
            max(abs(v - fine) for v in vals if v is not None) / abs(fine)
            if fine
            else float("nan")
        )
        worst = max(worst, dev)
        # The halving-to-halving step: how much h still moves between the two
        # values closest to the limit.  A sweep can look badly spread over its
        # whole range and still be converged AT the limit, and vice versa --
        # this column is the one that says which.
        ordered = sorted(
            ((run[key], row.get(keyfmt(run[key]))) for run in res["runs"]),
            key=lambda kv: kv[0],
        )
        if len(ordered) >= 2 and ordered[0][1] and ordered[1][1] is not None:
            adj = abs(ordered[1][1] - ordered[0][1]) / abs(ordered[0][1])
            worst_adj = max(worst_adj, adj)
        out.append(
            f"| {ph:.4f} | "
            + " | ".join("--" if v is None else f"{v:+.4e}" for v in vals)
            + f" | {dev * 100:.2f} % |"
        )
    out.append("")
    out.append(
        f"- **worst deviation of any {colname} in the sweep from the "
        f"{ref_col} limit: {worst * 100:.2f} %**"
    )
    out.append(
        f"- **worst change over the last step towards the limit "
        f"(the two smallest {colname}s): {worst_adj * 100:.2f} %** — this is "
        "the convergence statement; the row above is the span of the sweep"
    )
    for run in res["runs"]:
        out.append(
            f"  - {keyfmt(run[key])}: {run.get('elapsed_s', float('nan')):.0f} s"
        )
    out.append("")


def section_capacity(res, out):
    """The one-deck construction's copy ceiling."""
    if not res:
        return
    out.append("## How many copies one deck holds\n")
    out.append(
        "The one-deck-many-copies construction is what makes `h` measurable, so "
        "the number of copies it supports caps how many injection phases one deck "
        "can resolve. Injection-free, "
        f"{res['tstop_s'] * 1e9:g} ns decks: the question is whether the "
        "transient starts at all at that circuit size, which is settled in the "
        "first picoseconds.\n"
    )
    out.append("| copies | transient | data rows | wall |")
    out.append("|---|---|---|---|")
    for r in res["rows"]:
        out.append(
            f"| {r['ncopy']} | "
            f"{'**ABORTED**' if r['aborted'] else 'completed'} | "
            f"{r['data_rows']} | {r['elapsed_s']:.0f} s |"
        )
    out.append("")
    out.append(
        f"- **largest copy count that completes: {res['largest_completing']}; "
        f"smallest that aborts: {res['smallest_aborting']}**"
    )
    out.append(
        "- the abort is `Timestep too small` within the first 20 fs, and ngspice "
        "still writes a `clk.dat` — so without this stage the symptom is the "
        "reduction dividing by an empty crossing list, several steps downstream "
        "of the cause. `run_deck()` refuses any run whose log carries it."
    )
    out.append("")


def section_diff(res, out):
    """The differential ISFs, and the two constructions of them agreeing."""
    if not res:
        return
    out.append("## The differential ISF a channel-noise generator sees\n")
    out.append(
        "A device's channel-noise generator is a current source between its "
        "drain and its source, so the phase shift it produces is weighted by "
        "`h_gen = h(source) - h(drain)`, not by `h(drain)`. (A generator current "
        "of +1 A removes charge from the drain and delivers it to the source, "
        "hence the order; only `h_gen**2` reaches the jitter sum, so the sign "
        "changes no result — it changes whether two constructions of it are "
        "comparable.) Every copy below is in ONE deck, on one timestep sequence: "
        "the single-node injections, and a direct injection BETWEEN each pair of "
        "nodes. By linearity the two must give the same `h_gen`, and their "
        "agreeing is evidence about the deck — that the pair element landed on "
        "the nets it names — that no internal check on either construction alone "
        "can give.\n"
    )
    out.append(
        f"f0 from the reference copy: {res['f0_Hz'] / 1e6:.4f} MHz; "
        f"{res.get('elapsed_s', float('nan')):.0f} s of ngspice for "
        f"{len(res['rows'])} injected copies + 1 reference, one deck. Charges "
        "are per-phase, sized to land every displacement near "
        f"{res.get('target_dt_s', 0) * 1e12:g} ps (see `run.py`).\n"
    )
    out.append(
        "| pair (drain-source) | phase x/2pi | h(drain) | h(source) | "
        "h_gen | residue / larger term | h_gen floor | h_gen / floor |"
    )
    out.append("|---" * 8 + "|")
    worst_ratio = 1.0
    worst_snr = float("inf")
    for d in res.get("differences", []):
        worst_ratio = min(worst_ratio, abs(d["cancellation_ratio"]))
        worst_snr = min(worst_snr, d["snr"])
        out.append(
            f"| {d['pair']} | {d['phase_cycles']:.4f} | "
            f"{d['h_drain_rad_per_C']:+.4e} | {d['h_source_rad_per_C']:+.4e} | "
            f"{d['h_gen_rad_per_C']:+.4e} | "
            f"{abs(d['cancellation_ratio']) * 100:.2f} % | "
            f"{d['floor_rad_per_C']:.3e} | {d['snr']:.1f} |"
        )
    out.append("")
    out.append(
        f"- **strongest cancellation over the sampled phases: the residue is "
        f"{worst_ratio * 100:.2f} % of the larger term** — i.e. a pipeline that "
        "built `h_gen` by subtracting single-node ISFs would need "
        f"{1 / worst_ratio:.0f}x the precision those tables demonstrate"
    )
    out.append(
        f"- worst `h_gen`/floor of any differenced pair: {worst_snr:.1f}"
    )
    out.append("")
    cc = res.get("crosscheck") or []
    if cc:
        out.append(
            "### Cross-check: directly injected `h_gen` vs. the subtraction\n"
        )
        out.append(
            "Two stimuli, two charges, one timestep grid. The **signed** column "
            "is the one with teeth: a ~200 % signed disagreement alongside a ~0 % "
            "magnitude disagreement is a sign-convention error, which is exactly "
            "how the convention now pinned in `isf_extract.node_differences` was "
            "found.\n"
        )
        out.append(
            "| pair | phase x/2pi | dq direct | h_gen direct | dq single-node | "
            "h_gen subtracted | signed | magnitude |"
        )
        out.append("|---" * 8 + "|")
        for c in cc:
            out.append(
                f"| {c['pair']} | {c['phase_cycles']:.4f} | "
                f"{c['h_direct_dq_C'] * 1e15:g} fC | "
                f"{c['h_direct_rad_per_C']:+.4e} | "
                f"{(c['h_subtracted_dq_C'] or 0) * 1e15:g} fC | "
                f"{c['h_subtracted_rad_per_C']:+.4e} | "
                f"{c['rel_disagreement'] * 100:.2f} % | "
                f"{c.get('rel_disagreement_magnitude', float('nan')) * 100:.2f} % |"
            )
        out.append("")
        worst = max(cc, key=lambda c: c["rel_disagreement"])
        med = sorted(c["rel_disagreement"] for c in cc)[len(cc) // 2]
        wm = max(cc, key=lambda c: c.get("rel_disagreement_magnitude", 0.0))
        medm = sorted(
            c.get("rel_disagreement_magnitude", float("nan")) for c in cc
        )[len(cc) // 2]
        out.append(
            f"- worst SIGNED disagreement: {worst['rel_disagreement'] * 100:.2f} % "
            f"({worst['pair']} at phase {worst['phase_cycles']:.4f}); "
            f"median {med * 100:.2f} %"
        )
        out.append(
            f"- **worst MAGNITUDE disagreement: "
            f"{wm.get('rel_disagreement_magnitude', float('nan')) * 100:.2f} %** "
            f"({wm['pair']} at phase {wm['phase_cycles']:.4f}); "
            f"median {medm * 100:.2f} %"
        )
        out.append("")


def render(results: Path) -> str:
    out = [
        "# ISF bring-up -- results",
        "",
        "GENERATED by `sim/period-jitter/isf-bringup/summarize.py` from",
        "`results/*.json`. Do not edit by hand.",
        "",
    ]
    env = _load(results, "environment")
    if env:
        op = env["operating_point"]
        out.append("## Environment\n")
        out.append(f"- ngspice: `{env['ngspice']}`")
        out.append(f"- PDK models: `{env['pdk_models']}`")
        out.append(
            f"- operating point: typical / {op['temp_c']:g} C / {op['vsup']}"
            f" V, band code bits (B0,B1,B2) = {tuple(op['band'])}, "
            f"Vctrl = {op['vctrl']} V"
        )
        out.append(
            f"- transient: `.tran {env['tstep_s']:g} {env['tstop_s']:g} 0 "
            f"{env['tmax_s']:g}`, injection at t0 = "
            f"{env['t_inject0_s'] * 1e9:g} ns + phase, pulse width "
            f"{env['pulse_width_s'] * 1e12:g} ps, default dq = "
            f"{env['pilot_dq_C'] * 1e15:g} fC"
        )
        out.append(
            f"- `diff` stage: charges chosen per phase to land the displacement "
            f"near {env['target_dt_s'] * 1e12:g} ps, clipped to "
            f"[{env['dq_min_C'] * 1e15:g}, {env['dq_max_C'] * 1e15:g}] fC "
            f"(pair injections capped at the pilot charge); phases "
            + ", ".join(f"{p:.4f}" for p in env["diff_phases_cycles"])
            + "; two-terminal pairs (drain-source) "
            + ", ".join(env["diff_pairs_drain_source"])
        )
        out.append(
            "- `capacity` stage: copy counts probed — "
            + ", ".join(str(n) for n in env["capacity_probe_ncopy"])
        )
        if env.get("quick"):
            out.append(
                "- **`--quick` run: a smoke check, NOT the recorded bring-up**"
            )
        out.append("")

    section_period(_load(results, "period"), out)
    section_gamma(
        _load(results, "gamma"),
        out,
        "h(x) at the ring output node Y",
        "One period sampled uniformly. `Y1` is the drain of both switching "
        "devices of stage 1 and the gate of stage 2.",
    )
    section_gamma(
        _load(results, "nodes"),
        out,
        "h(x) at the two current-source nodes NH and NT",
        "`NT1` is the source of the stage-1 nfet and the drain of its tail "
        "current source; `NH1` is the source of the stage-1 pfet and the drain "
        "of its head current source. The channel-thermal generator of the "
        "switching nfet drives current between Y and NT, so the ISF that "
        "weights it is the DIFFERENCE h(Y) - h(NT), not h(Y) alone.",
    )
    section_capacity(_load(results, "capacity"), out)
    section_diff(_load(results, "diff"), out)
    section_sweep(
        _load(results, "timestep"),
        out,
        title="Convergence against the internal-timestep ceiling",
        key="tmax_s",
        keyfmt=lambda x: f"{x * 1e12:g} ps",
        colname="ceiling",
        blurb=(
            "Issue #520 names this the load-bearing risk: Gamma's accuracy near "
            "the switching edge is exactly where ngspice's timestep control is "
            "weakest. Same injection phases and same charge at every ceiling; "
            "only `tmax` changes."
        ),
    )
    section_sweep(
        _load(results, "linearity"),
        out,
        title="Linearity in the injected charge",
        key="dq_C",
        keyfmt=lambda x: f"{x * 1e15:g} fC",
        colname="charge",
        blurb=(
            "The ISF is defined in the limit of an infinitesimal impulse. A "
            "charge small enough to be linear but large enough to move the "
            "crossing well clear of the numerical floor is what makes the "
            "measurement possible at all; this sweep is how that window is "
            "established rather than assumed."
        ),
    )
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=str(HERE / "results"))
    args = ap.parse_args(argv)
    print(render(Path(args.results)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
