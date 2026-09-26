#!/usr/bin/env python3
"""gf180-pll :: period-jitter :: ISF bring-up -- the runner.

Seven stages, all at ONE PVT point (typical / 27 C / 3.30 V, VCO band 6,
Vctrl = 1.795 V -- `sim/period-jitter`'s own operating point for that corner):

  period      the free-running reference, and how fast it settles
  gamma       h(x) across one cycle at the ring output node Y
  nodes       h(x) at the two current-source nodes NH and NT
  linearity   h at six injected charges -- over what range is h linear in dq?
  timestep    h at four internal-timestep ceilings -- does h converge?
  capacity    how many copies one deck holds before the transient stops
              starting -- the hard limit on how many phases a deck can resolve
  diff        all three node classes in ONE deck, at a per-phase charge sized
              from the `gamma`/`nodes` pilot, so the DIFFERENCES h(Y)-h(NT)
              and h(Y)-h(NH) -- which is what a device's drain-to-source noise
              generator is actually weighted by -- are measured on a single
              timestep grid instead of subtracted across two decks

WHY ONE CORNER.  This directory brings a METHOD up; it does not characterise
the design.  A PVT grid would multiply the cost of an unvalidated method by 45
before anyone knows whether the method converges.  The convergence question is
corner-independent in kind (an integration-error question), and the bring-up's
whole purpose is to answer it before a grid is paid for.  Nothing here is an
evidence record and nothing here appears in `spec/pll.md`.

Sequential by construction -- one ngspice process at a time.  This host is a
shared dispatch worker; a PVT grid belongs on the batch fleet via the harness,
not in a shell loop here.

Usage:
  sim/period-jitter/isf-bringup/run.py [--stage NAME]... [--outdir DIR] [--quick]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import isf_deck  # noqa: E402
import isf_extract  # noqa: E402

# --- the operating point ---------------------------------------------------
# typical / 27 C / 3.30 V, VCO band code 6 (B2 B1 B0 = 1 1 0), released at the
# 150 MHz control voltage sim/period-jitter/testbench/tb.json carries for this
# corner (1.795 V, interpolated there from VCO record 20260804-162735-72883fb).
# Reusing that exact point rather than inventing one is deliberate: whatever
# this bring-up eventually feeds is the SAME operating point the deterministic
# half of the period-jitter row is already measured at.
OP = dict(vctrl=1.795, vsup=3.3, temp_c=27.0, band=(0, 1, 1))

T_INJECT0 = 40e-9  # ~6 cycles in: past settling (see the `period` stage)
TSTOP = 120e-9
TSTEP = 2e-12
TMAX = 2e-12
PW = 10e-12  # injection pulse width, 0.15 % of a period
DQ = 2e-15  # the PILOT charge for `gamma`/`nodes`; the `linearity` stage
# measures how far from the dq -> 0 limit it leaves them, and `diff` re-measures
# every node at a charge sized per phase from their result.

# --- the `diff` stage's per-phase charge rule ---------------------------------
# One fixed dq cannot serve every phase, and the `linearity` stage is what shows
# why: the ISF's own definition wants dq -> 0, while the settled-tail spread
# (~10 fs) puts a floor under how small a phase displacement can be read.  At
# the switching edges |h| is ~2e13 rad/C and 2 fC already displaces the edge by
# 35-47 ps -- 0.7 % of a period, far outside the linear regime.  At the flat
# parts of the cycle |h| is 300x smaller and 2 fC displaces the edge by ~0.1 ps,
# only ~10x the floor.  So dq is chosen PER PHASE to land the displacement in a
# window that is simultaneously small enough to be linear and large enough to
# read, which puts the accuracy where the Gamma^2-weighted sum needs it.
TARGET_DT = 2e-12  # ~0.03 % of a period: >100x the tail spread, and see above
DQ_MIN, DQ_MAX = 0.125e-15, 8e-15  # the range `linearity` characterises


def pdk_models() -> Path:
    env = subprocess.run(
        [sys.executable, str(REPO / "sim" / "run_corners.py"), "--print-env"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for line in env.splitlines():
        if line.startswith("export GF180_MODELS="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("could not resolve GF180_MODELS from sim/run_corners.py")


#: ngspice diagnostics that invalidate a run rather than annotate it.  A
#: "Timestep too small" abort in particular leaves a clk.dat with a couple of
#: rows in it, so the reduction's own "no crossings" failure is several steps
#: downstream of the cause -- worth naming at the source.
FATAL_LOG_PATTERNS = ("Timestep too small", "simulation(s) aborted", "singular")


def run_deck(deck: str, work: Path, logname: str, logs: Path,
             tolerate_abort: bool = False) -> float:
    work.mkdir(parents=True, exist_ok=True)
    (work / "deck.sp").write_text(deck)
    t0 = time.time()
    proc = subprocess.run(
        ["ngspice", "-b", "deck.sp"], cwd=work, capture_output=True, text=True
    )
    elapsed = time.time() - t0
    logs.mkdir(parents=True, exist_ok=True)
    out = proc.stdout + proc.stderr
    (logs / logname).write_text(out)
    if not (work / "clk.dat").is_file():
        raise SystemExit(
            f"ngspice produced no clk.dat for {logname} -- see logs/{logname}"
        )
    if not tolerate_abort:
        hit = [p for p in FATAL_LOG_PATTERNS if p in out]
        if hit:
            raise SystemExit(
                f"ngspice reported {hit!r} for {logname}: the transient did not "
                f"complete, so any reduction of it is meaningless. See "
                f"logs/{logname}. If this is a many-copy deck, check it against "
                f"the `capacity` stage's measured ceiling."
            )
    return elapsed


def deck_aborted(logs: Path, logname: str) -> bool:
    txt = (logs / logname).read_text()
    return any(p in txt for p in FATAL_LOG_PATTERNS)


def phase_set(n):
    return [i / n for i in range(n)]


def build_phase_run(models, phases, period, *, node="Y", stage=1, dq=DQ,
                    tmax=TMAX, tstop=TSTOP, pw=PW):
    injections = []
    meta = {}
    for i, ph in enumerate(phases):
        copy = i + 1
        t_inj = T_INJECT0 + ph * period
        injections.append((copy, node, stage, t_inj, dq, pw))
        meta[copy] = dict(
            t_inject=t_inj, dq=dq, phase=ph, node=node, stage=stage
        )
    deck = isf_deck.build_deck(
        repo_root=REPO,
        pdk_models=models,
        injections=injections,
        ncopy=len(phases) + 1,
        tstop=tstop,
        tstep=TSTEP,
        tmax=tmax,
        **OP,
    )
    return deck, meta


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------
def stage_period(models, out, logs, work, quick):
    deck = isf_deck.build_deck(
        repo_root=REPO, pdk_models=models, injections=(), ncopy=1,
        tstop=TSTOP, tstep=TSTEP, tmax=TMAX, **OP,
    )
    elapsed = run_deck(deck, work / "period", "period.log", logs)
    t, cols = isf_extract.read_wrdata(work / "period" / "clk.dat", 1)
    cross = isf_extract.crossings(t, cols[0], OP["vsup"] / 2)
    per = [cross[i + 1] - cross[i] for i in range(len(cross) - 1)]
    period = isf_extract.mean_period(cross[4:])
    return {
        "elapsed_s": elapsed,
        "n_crossings": len(cross),
        "first_crossing_s": cross[0],
        "periods_s": per,
        "period_s": period,
        "f0_Hz": 1.0 / period,
        "settled_period_ptp_s": max(per[4:]) - min(per[4:]),
    }


def stage_gamma(models, out, logs, work, quick, period):
    n = 8 if quick else 24
    phases = phase_set(n)
    deck, meta = build_phase_run(models, phases, period)
    elapsed = run_deck(deck, work / "gamma", "gamma.log", logs)
    res = isf_extract.reduce_run(
        work / "gamma" / "clk.dat", len(phases) + 1, meta, OP["vsup"] / 2
    )
    res["elapsed_s"] = elapsed
    res["n_phases"] = n
    return res


def stage_nodes(models, out, logs, work, quick, period):
    n = 6 if quick else 12
    phases = phase_set(n)
    injections, meta = [], {}
    copy = 0
    for node in ("NH", "NT"):
        for ph in phases:
            copy += 1
            t_inj = T_INJECT0 + ph * period
            injections.append((copy, node, 1, t_inj, DQ, PW))
            meta[copy] = dict(
                t_inject=t_inj, dq=DQ, phase=ph, node=node, stage=1
            )
    deck = isf_deck.build_deck(
        repo_root=REPO, pdk_models=models, injections=injections,
        ncopy=copy + 1, tstop=TSTOP, tstep=TSTEP, tmax=TMAX, **OP,
    )
    elapsed = run_deck(deck, work / "nodes", "nodes.log", logs)
    res = isf_extract.reduce_run(
        work / "nodes" / "clk.dat", copy + 1, meta, OP["vsup"] / 2
    )
    res["elapsed_s"] = elapsed
    return res


def stage_linearity(models, out, logs, work, quick, period):
    """Is the phase response linear in the injected charge?

    Six charges spanning 64x, at six phases spanning the cycle, each in its
    own deck so that all six charges at a given phase are compared on
    trajectories that saw the same injection times.

    The sweep runs DOWN to 0.125 fC, not just down to the pilot charge, because
    the pilot charge turns out not to be in the linear regime at the switching
    edges and the question "where does linearity start?" cannot be answered by
    a sweep whose smallest value is the one under suspicion.

    WHICH PHASES, and why two of them are not on a uniform grid.  `h(x)` on this
    ring swings from +2e13 through zero to -2e13 within a tenth of a cycle, so
    the linear window is not a property of the ring alone -- it is a property of
    the phase.  At a phase where `h` is small and `dh/dx` is enormous the
    second-order term in the response (which scales as `dq**2 * dh/dx`, the
    injection displacing the trajectory while it is still being delivered) is
    comparable to the linear `h*dq` term, so the window closes.  `1/6` and `2/3`
    are added for exactly that reason: they are the two phases sitting on the
    steep flanks immediately before `h(Y)`'s two zero crossings, and they are
    where the `diff` stage's two constructions of `h_gen` disagree most.  A
    linearity sweep taken only at the peaks and the flats would establish a
    window that does not hold where it is needed, and would leave that
    disagreement unexplained -- which is precisely what the first pass of this
    bring-up did.  Both are multiples of 1/24, so they coincide with the `gamma`
    sweep's grid and with `diff`'s phase set.
    """
    phases = [0.0, 1 / 6, 0.25, 0.5, 2 / 3, 0.75]
    charges = [0.125e-15, 0.25e-15, 0.5e-15, 1e-15, 2e-15, 8e-15]
    runs = []
    for dq in charges:
        deck, meta = build_phase_run(models, phases, period, dq=dq)
        tag = f"lin_{dq * 1e15:g}fC"
        elapsed = run_deck(deck, work / tag, f"{tag}.log", logs)
        res = isf_extract.reduce_run(
            work / tag / "clk.dat", len(phases) + 1, meta, OP["vsup"] / 2
        )
        res["elapsed_s"] = elapsed
        res["dq_C"] = dq
        runs.append(res)
    return {"charges_C": charges, "phases_cycles": phases, "runs": runs}


def stage_timestep(models, out, logs, work, quick, period):
    """Does h converge as the internal-timestep ceiling is tightened?

    This is the bring-up's load-bearing question -- issue #520 names it as
    such.  Four ceilings spanning 16x, at four phases including the two the
    `gamma` stage finds h largest at (the switching edges, where timestep
    control is weakest and where a non-converging method would show it).

    WHAT THIS PHASE SET DOES NOT COVER, stated because the convergence claim is
    read more broadly than it is measured.  These four phases are the peaks and
    the flats.  They do NOT include the two phases on the steep flanks before
    `h(Y)`'s zero crossings (1/6 and 2/3), where `stage_linearity` shows the
    charge response is not linear even at 0.125 fC.  A convergence-in-`tmax`
    statement from this stage therefore covers the peaks and flats -- which is
    where a Gamma^2-weighted sum is dominated -- and is silent about those two
    phases.  Extending it there is work for the pipeline, not a gap this
    bring-up hides.
    """
    phases = [0.0, 0.25, 0.5, 0.75]
    ceilings = [8e-12, 4e-12, 2e-12, 1e-12] if not quick else [8e-12, 4e-12]
    runs = []
    for tmax in ceilings:
        deck, meta = build_phase_run(models, phases, period, tmax=tmax)
        tag = f"dt_{tmax * 1e12:g}ps"
        elapsed = run_deck(deck, work / tag, f"{tag}.log", logs)
        res = isf_extract.reduce_run(
            work / tag / "clk.dat", len(phases) + 1, meta, OP["vsup"] / 2
        )
        res["elapsed_s"] = elapsed
        res["tmax_s"] = tmax
        runs.append(res)
    return {"tmax_s": ceilings, "phases_cycles": phases, "runs": runs}


def _pilot_dt_signed(out, node, phase):
    """The signed dt the pilot run measured for `node` at `phase`, or None.

    `gamma` is the pilot for Y, `nodes` for NH/NT.  Both were run at `DQ`.  The
    sign is kept because the pair charges are sized from a DIFFERENCE of two
    pilot displacements, and |a| - |b| is not |a - b|.
    """
    src = "gamma.json" if node == "Y" else "nodes.json"
    path = out / src
    if not path.is_file():
        return None
    for r in json.loads(path.read_text())["rows"]:
        if r["node"] == node and abs(r["phase_cycles"] - phase) < 1e-9:
            return r["dt_s"]
    return None


def _charge_for(out, node, phase):
    """The `diff` stage's per-phase charge -- see TARGET_DT above."""
    signed = _pilot_dt_signed(out, node, phase)
    dt = abs(signed) if signed is not None else None
    if not dt:
        raise SystemExit(
            f"the `diff` stage needs the `gamma` and `nodes` pilots first "
            f"(no pilot dt for {node} at phase {phase:g})"
        )
    dq = DQ * TARGET_DT / dt
    return min(DQ_MAX, max(DQ_MIN, dq))


#: Copy counts the `capacity` stage probes for the one-deck construction's
#: ceiling.  Injection-free and 3 ns long: the question is whether the transient
#: starts at all at that circuit size, which is answered in the first
#: picoseconds.
COPY_PROBE = (25, 31, 37, 41, 61)


def stage_capacity(models, out, logs, work, quick, period):
    """How many copies can one deck hold before the transient stops starting?

    The one-deck-many-copies construction is what makes `h` measurable -- it is
    the reason the perturbed and unperturbed trajectories share a timestep
    sequence -- so the number of copies it supports is a hard limit on how many
    injection phases one deck can resolve, and therefore on the whole method's
    cost.  It is measured here rather than discovered as a mystery failure,
    because the failure mode is genuinely misleading: above the ceiling the
    transient aborts with `Timestep too small` in the first 20 fs, ngspice still
    writes a `clk.dat` with one or two rows in it, and the first thing that
    actually complains is the reduction dividing by an empty crossing list.

    Every copy is a disjoint circuit; the only things they share are ground, the
    ideal supply and the ideal control/band-code sources.  This stage is
    therefore a statement about ngspice's transient startup on a large stiff
    circuit, not about the ring.
    """
    rows = []
    for ncopy in COPY_PROBE:
        deck = isf_deck.build_deck(
            repo_root=REPO, pdk_models=models, injections=(), ncopy=ncopy,
            tstop=3e-9, tstep=TSTEP, tmax=TMAX, **OP,
        )
        tag = f"capacity_{ncopy}"
        elapsed = run_deck(
            deck, work / tag, f"{tag}.log", logs, tolerate_abort=True
        )
        t, cols = isf_extract.read_wrdata(work / tag / "clk.dat", ncopy)
        rows.append(
            {
                "ncopy": ncopy,
                "aborted": deck_aborted(logs, f"{tag}.log"),
                "data_rows": len(t),
                "elapsed_s": elapsed,
            }
        )
        print(
            f"       ncopy={ncopy}: "
            f"{'ABORTED' if rows[-1]['aborted'] else 'ok'} "
            f"({len(t)} rows, {elapsed:.0f}s)",
            flush=True,
        )
    ok = [r["ncopy"] for r in rows if not r["aborted"]]
    bad = [r["ncopy"] for r in rows if r["aborted"]]
    return {
        "tstop_s": 3e-9,
        "rows": rows,
        "largest_completing": max(ok) if ok else None,
        "smallest_aborting": min(bad) if bad else None,
    }


#: The two-terminal generators this stage injects directly, as
#: (drain, source) node classes -- i.e. the channel-noise current sources of the
#: stage's two switching devices, in the direction the device drives them.
PAIRS = (("Y", "NT"), ("Y", "NH"))

#: The phases the `diff` stage samples.  NOT a uniform sweep, and the reason is
#: the `capacity` ceiling: five injection variants (three nodes plus two pairs)
#: per phase plus one reference means a uniform 12-phase set would need 61
#: copies, which is past the ceiling.  Under it, the phases worth spending on
#: are the ones a Gamma^2-weighted sum is dominated by -- the two switching
#: edges, where |h| peaks and where the drain/source cancellation is strongest --
#: plus the flat immediately after each.  `gamma` already gives the uniform
#: 24-phase curve at the output node; this stage is about the residue, at the
#: phases where the residue matters.  Every phase must be a multiple of 1/12
#: because the pair charges are sized from the `gamma`/`nodes` pilots, which
#: sample NH and NT on that grid.
DIFF_PHASES = (0.0, 1 / 12, 2 / 12, 6 / 12, 7 / 12, 8 / 12)


def stage_diff(models, out, logs, work, quick, period):
    """The quantity the jitter sum actually needs, measured two ways in ONE deck.

    A device's channel-noise generator is a current source between its drain and
    its source, so the phase shift it produces is weighted by `h_ds =
    h(drain) - h(source)`, not by `h(drain)`.  This stage measures `h_ds` for the
    stage's two switching devices

      * directly, by injecting between the two nodes (`PAIRS` below), and
      * as the difference of the two single-node measurements,

    with every copy in a single deck so both constructions share one timestep
    sequence.  They must agree; that agreement is the bring-up's own check that
    the injection lands on the nets it claims to, which no amount of internal
    consistency in a single construction can provide.

    Why not just difference `gamma` and `nodes`.  Those are separate decks, hence
    two independently-chosen adaptive timestep grids.  For a per-node `h` that
    does not matter -- each is measured against its own in-deck reference.  For a
    DIFFERENCE of two nearly-equal terms it matters a great deal, and on this
    ring the cancellation is strong enough that the grid error would no longer be
    negligible against the residue.

    Charges are per-phase (see TARGET_DT), so each copy sits at a displacement
    both readable against the settled-tail spread and inside the linear range
    `linearity` characterises.  The pair injections get their OWN charge, sized
    from the pilot difference rather than from either node, because the whole
    point is that the differential response is much smaller.
    """
    phases = DIFF_PHASES[:3] if quick else DIFF_PHASES
    nodes = ("Y", "NH", "NT")
    # One charge per phase, shared by all three single-node copies at that phase:
    # `node_differences` refuses to difference unequal charges, and taking the
    # smallest of the three keeps every member inside the linear range rather
    # than dragging the most sensitive node out of it.
    dq_by_phase = {
        ph: min(_charge_for(out, nd, ph) for nd in nodes) for ph in phases
    }
    # And one charge per (pair, phase), sized from the pilot DIFFERENCE -- which
    # is ~20x smaller than either term, so this is ~20x larger than the
    # single-node charge at the same phase and still lands at TARGET_DT.
    dq_pair = {}
    for drain, source in PAIRS:
        for ph in phases:
            d_dt = abs(
                (_pilot_dt_signed(out, drain, ph) or 0.0)
                - (_pilot_dt_signed(out, source, ph) or 0.0)
            )
            dq = DQ * TARGET_DT / d_dt if d_dt else DQ
            # Capped at the pilot charge, NOT at DQ_MAX.  The target-displacement
            # rule is about the PHASE shift, and for a pair injection that shift
            # is small while the local node excursion is not: dq/C_node is ~0.4 V
            # per 5.6 fC on a ring node.  `linearity` characterises the
            # single-node response only up to 8 fC, so holding the pair charge to
            # the largest value any recorded stage uses keeps the stimulus inside
            # the range something has been measured about.  What it costs is
            # visible: the displacement falls below TARGET_DT at the phases where
            # the pilot difference is small, and `snr` reports it there.
            dq_pair[(drain, source, ph)] = min(DQ, max(DQ_MIN, dq))

    injections, meta = [], {}
    copy = 0
    for node in nodes:
        for ph in phases:
            copy += 1
            dq = dq_by_phase[ph]
            injections.append((copy, node, 1, T_INJECT0 + ph * period, dq, PW))
            meta[copy] = dict(
                t_inject=T_INJECT0 + ph * period, dq=dq, phase=ph, node=node,
                stage=1,
            )
    for drain, source in PAIRS:
        for ph in phases:
            copy += 1
            dq = dq_pair[(drain, source, ph)]
            injections.append(
                (copy, (drain, source), 1, T_INJECT0 + ph * period, dq, PW)
            )
            meta[copy] = dict(
                t_inject=T_INJECT0 + ph * period, dq=dq, phase=ph,
                node=f"{drain}-{source}", stage=1,
            )
    deck = isf_deck.build_deck(
        repo_root=REPO, pdk_models=models, injections=injections,
        ncopy=copy + 1, tstop=TSTOP, tstep=TSTEP, tmax=TMAX, **OP,
    )
    elapsed = run_deck(deck, work / "diff", "diff.log", logs)
    res = isf_extract.reduce_run(
        work / "diff" / "clk.dat", copy + 1, meta, OP["vsup"] / 2
    )
    res["elapsed_s"] = elapsed
    res["target_dt_s"] = TARGET_DT
    res["dq_by_phase_C"] = {f"{ph:.6f}": dq for ph, dq in dq_by_phase.items()}
    res["differences"] = isf_extract.node_differences(
        res["rows"], res["period_s"], pairs=PAIRS
    )
    res["crosscheck"] = isf_extract.crosscheck_pairs(
        res["rows"], res["differences"], PAIRS
    )
    return res


STAGES = [
    "period", "gamma", "nodes", "linearity", "timestep", "capacity", "diff",
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", action="append", choices=STAGES, default=None)
    ap.add_argument("--outdir", default=str(HERE / "results"))
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--quick", action="store_true",
                    help="fewer phases / fewer ceilings -- a smoke run, not evidence")
    ap.add_argument("--force", action="store_true",
                    help="re-run stages whose results JSON already exists")
    args = ap.parse_args(argv)

    stages = args.stage or STAGES
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    logs = HERE / "logs"
    work = Path(args.workdir) if args.workdir else Path(
        subprocess.run(["mktemp", "-d"], capture_output=True, text=True,
                       check=True).stdout.strip()
    )

    models = pdk_models()
    ngv = subprocess.run(["ngspice", "-v"], capture_output=True, text=True)
    env = {
        "ngspice": " ".join(ngv.stdout.splitlines()[1].split())
        if len(ngv.stdout.splitlines()) > 1 else ngv.stdout.strip(),
        "pdk_models": str(models),
        "operating_point": {k: (list(v) if isinstance(v, tuple) else v)
                            for k, v in OP.items()},
        "t_inject0_s": T_INJECT0, "tstop_s": TSTOP, "tstep_s": TSTEP,
        "tmax_s": TMAX, "pulse_width_s": PW, "pilot_dq_C": DQ,
        # Recorded because the DELIVERED charge is the trapezoid's area,
        # amp*(PW + TR/2 + TF/2), not amp*PW: without the ramp time a reader
        # cannot check that the amplitude in a deck matches the `dq` its row is
        # normalised by.  See `isf_deck.injected_charge`.
        "pulse_ramp_s": isf_deck.RAMP_S,
        "injection_amplitude_A": isf_deck.injection_amplitude(DQ, PW),
        # The `diff` stage's per-phase charge rule and phase set, and the
        # `capacity` probe's copy counts -- recorded because every `diff` number
        # is a function of them and a reader should not have to read the source
        # to know which rule produced the charge beside a given row.
        "target_dt_s": TARGET_DT, "dq_min_C": DQ_MIN, "dq_max_C": DQ_MAX,
        "diff_phases_cycles": list(DIFF_PHASES),
        "diff_pairs_drain_source": ["-".join(p) for p in PAIRS],
        "capacity_probe_ncopy": list(COPY_PROBE),
        "quick": bool(args.quick),
    }
    (out / "environment.json").write_text(json.dumps(env, indent=2) + "\n")

    period = None
    if (out / "period.json").is_file():
        period = json.loads((out / "period.json").read_text())["period_s"]

    for name in STAGES:
        if name not in stages:
            continue
        dest = out / f"{name}.json"
        if dest.is_file() and not args.force:
            print(f"[skip] {name} -- {dest} exists (--force to re-run)")
            if name == "period":
                period = json.loads(dest.read_text())["period_s"]
            continue
        print(f"[run ] {name} ...", flush=True)
        t0 = time.time()
        if name == "period":
            res = stage_period(models, out, logs, work, args.quick)
            period = res["period_s"]
        else:
            if period is None:
                raise SystemExit("run the `period` stage first (it sets T)")
            res = globals()[f"stage_{name}"](
                models, out, logs, work, args.quick, period
            )
        dest.write_text(json.dumps(res, indent=2) + "\n")
        print(f"[done] {name} in {time.time() - t0:.1f}s -> {dest}")

    print(f"\nwork directory: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
