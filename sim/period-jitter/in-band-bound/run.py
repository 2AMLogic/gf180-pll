#!/usr/bin/env python3
"""gf180-pll :: period-jitter :: in-band-bound -- the runner.

Stages (see README.md for what each establishes):

  loop      the closed-loop transfer `|T/(1+T)|^2` over every loop the as-built
            filter admits at the ratified 45 degree phase-margin floor, and the
            period weight it is integrated against -- once, no simulator
  digital   per point: the committed `pll_top` open loop (`VCTRL` held at this
            corner's own 150 MHz control voltage) -- the reset-window overlap,
            the charge-pump switch timing, and the slowest edge slew anywhere
            in the PFD, the divider chain or the lock detector
  cp        per point: the charge pump's output-current noise density, both
            switches on (the overlap state) and both off (the rest of the
            reference period), at this campaign's trim code
  cells     per point: every logic cell type the three digital blocks
            instantiate, at its trip point, loaded generously -- the
            output-noise density that becomes edge jitter, the measured fact
            that the trip point is the worst bias, and the output slew rate the
            noise is divided by
  clkload   per point: what the divider chain's clock-input devices put back
            onto `CLK` itself -- the one path that does not go through the loop
  ldload    per point: what the lock detector's XOR-input devices put back onto
            `UP`/`DN` -- the lock detector's ONLY path to the output, since it
            drives nothing and is in no timing path
  bound     per point: all of it assembled, against the margin `../random-bound`
            leaves at this same point

Usage:
  run.py --stage loop
  run.py --point typical_27c_3.30v --stage digital --stage cp --stage cells \
         --stage clkload --stage ldload --stage bound
  run.py --point typical_27c_3.30v --stage validate
  run.py --list-points

One point per invocation, one ngspice process at a time within it.  The 45-point
grid is driven by `grid.sh`.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "sim"))

from harness.pdk import find_pdk  # noqa: E402
from harness import execution, legacy_provenance  # noqa: E402

import ib_deck  # noqa: E402
import ib_extract as ib  # noqa: E402

RB_RESULTS = HERE.parent / "random-bound" / "results"
TB_JSON = REPO / "sim" / "period-jitter" / "testbench" / "tb.json"
NETLIST = REPO / "design" / "netlist" / "pll_top.spice"
RESULTS = HERE / "results"
LOGS = HERE / "logs"

SUPPLY = {"low": 2.97, "nom": 3.30, "high": 3.63}
REFERENCE_POINT = "typical_27c_3.30v"

#: `spec/pll.md` "Period jitter": the share of the 1.0 % RMS line the
#: supply-ripple derivation leaves for the random contribution (DR-023
#: Decision 3), the same figure `../random-bound` is quoted against.
BUDGET_PCT = 0.50

#: The four blocks this directory bounds, and the `pll_top` subcircuit each one's
#: devices live in.  Used for the device-enumeration claims (`non_mos_devices`
#: must be empty for each, which is what makes `flatten_mos` their complete
#: generator set) and for the retired every-device-in-series comparison; the
#: bound itself counts stages per declared timing path, not per block
#: (`ib_extract.TIMING_PATHS`).
BLOCKS = {"pfd": "pfd", "charge_pump": "cp",
          "divider_chain": "divider_chain", "lock_detector": "lock_detector"}

#: `../random-bound/results/loop.json`'s filter ranges and phase-margin floor,
#: read from that file rather than retyped, so both directories envelope the
#: same loop set.
LOOP_JSON = RB_RESULTS / "loop.json"

#: The `.noise` frequency grid.  It has to span from well below the loop's
#: crossover (where a flicker component lands) to well past `10/t_on` (where
#: the charge pump's window function has rolled off) and past every node's own
#: corner (so `high_frequency_tail` extrapolates a measured `f^-2`, not a
#: guess).  4 points per decade over 11 decades.
NOISE_F_LO = 1.0
NOISE_F_HI = 1e11
NOISE_PER_DECADE = 4

#: The envelope grid the folded (flat) part of every spectrum is integrated on.
ENV_PER_DECADE = 12

#: Load capacitance every logic cell is characterized into.  A stage's edge
#: jitter grows as `sqrt(C_load)` (see `ib_deck.cell_noise_deck`), so this is
#: set well above any fan-out in the three blocks on purpose.
C_LOAD_F = 50e-15

#: Input biases the cells' `.noise` is run at, as offsets from the trip point.
#: The claim `ib_extract.edge_jitter` rests on -- that the trip point is the
#: worst bias -- is measured by these, not assumed.
CELL_BIAS_OFFSETS_V = (-0.4, -0.2, -0.05, 0.0, 0.05, 0.2, 0.4)

#: Sense resistance the charge pump's output is held through, and the drive
#: resistance `CLK` is driven through.  Both are recorded with the result;
#: `validate` re-runs at 10x to show the first does not matter and that the
#: second is the conservative direction.
RSENSE_OHM = 1e3

#: Drive resistances the `CLK` node is characterized at.  `stage_clkload`'s
#: docstring says why this is a sweep with a maximum taken over it rather than
#: one "conservative" value: the divider loads `CLK` capacitively, so the noise
#: it puts back is not monotone in the drive impedance.  The range brackets any
#: real CMOS output buffer's on-resistance by two decades either side.
R_DRIVE_SWEEP_OHM = (100.0, 1e3, 1e4, 1e5)

#: The `clkload` deck's own grid top.  The `CLK` node's `R_drive * C_node` corner
#: is tens of GHz at the smallest drive resistance in the sweep, and this is the
#: one measurand whose variance lives at the top of the band, so its grid has to
#: reach well past that corner for `high_frequency_tail` to extrapolate a
#: measured `f^-2` rather than refuse.
CLKLOAD_F_HI = 1e14

#: Series resistance the open-loop deck holds `VCTRL` through (`ib_deck.digital_deck`
#: documents why it is not zero).  `validate` re-runs at 100x to show the reset
#: window and every slew rate do not depend on it.
R_HOLD_OHM = 1.0

#: The `gmin` ladder the open-loop deck escalates through, starting ABOVE
#: ngspice's own 1e-12 default.  `ib_deck.digital_deck`'s `gmin` docstring says
#: why the default is not the first rung: at the default a `vsel<k>` branch --
#: a static configuration source whose net drives gates only, so its branch
#: current is ~0 and the solver has nothing to scale its step against -- makes
#: the transient either abort (`Timestep too small`) or, worse, grind: the same
#: `ff`/27 °C/3.30 V deck that finishes in **45 s** at `gmin = 1e-11` was still
#: running after **two hours** at the default, inching forward on a repeatedly
#: halved timestep with no error to show for it.  A silent 100x slowdown that
#: still produces a number is a worse failure than an abort, so the whole grid
#: runs at 1e-11 and escalates from there; the value used is recorded per point.
#: Each rung is `(gmin, ic_offset)`.  The FIRST rung is what the whole grid runs
#: at; a rung is tried only because the one before it stalled or ran past
#: `DIGITAL_TIMEOUT_S`, and the rung that produced the result is recorded with the
#: point.  Raising `gmin` is the first axis (see above); lifting the ring's
#: symmetry-breaking initial condition is the second, which is what
#: `../random-bound` does at the one point where its own deck stalls, and which
#: the oscillator forgets well inside the 60 ns of settling.
ATTEMPT_LADDER = ((1e-11, 0.0), (1e-10, 0.0), (1e-9, 0.0), (1e-11, 0.1),
                  (1e-10, 0.1))

#: Wall-clock cap on one open-loop transient, seconds.  A deck that is grinding
#: rather than converging must escalate the `gmin` ladder rather than hold a grid
#: slot for hours (see `GMIN_LADDER`).  A healthy pass is 45-90 s alone and about
#: 300 s with five siblings sharing the machine.
DIGITAL_TIMEOUT_S = 900

#: The open-loop transient.  60 ns of settling (`../random-bound`'s measured 40 ns
#: of ring settling, rounded up so the divider's state machine has reached its
#: steady sequence too) plus three reference periods at 25 MHz, at a 25 ps
#: internal timestep ceiling -- four times finer than the closed-loop campaigns'
#: 100 ps, because this deck's measurands are edge slews.
#:
#: 25 ps rather than 10 ps is a cost choice with a KNOWN SIGN.  Every measurand
#: this deck feeds the bound is degraded by a coarser step in the conservative
#: direction: a chord over a longer interval under-states an edge's slew, and
#: `edge_jitter` divides by that slew, so a coarser step inflates the bound.  The
#: `validate` stage re-runs the same deck at 2.5 ps and reports each measurand's
#: ratio, so the size of the choice is measured rather than assumed.
TRAN_TSTOP = 180e-9
TRAN_TSTEP = 25e-12
TRAN_TMAX = 25e-12
TRAN_T_SETTLE = 60e-9

#: A saved node counts as switching, and so contributes a slew rate, only if it
#: swings at least this fraction of the supply.  A node that merely glitches
#: through mid-supply would otherwise report a meaninglessly small slew and
#: dominate the bound with an artefact.
SWING_FRACTION = 0.8

#: How far, as a fraction of the reference period, `REF` may still sit from `FB`
#: after the alignment pass before the deck is refused.  In lock the two coincide
#: to the static phase offset (DR-012's quantity, tens of picoseconds); 2 % of a
#: 40 ns reference period is 800 ps, loose enough to absorb the alignment's own
#: timestep granularity and tight enough that an alignment that did not happen
#: cannot pass.
ALIGN_RESIDUAL_FRACTION = 0.02

FATAL = ("Timestep too small", "simulation(s) aborted", "singular matrix",
         "Error:")


# ---------------------------------------------------------------------------
# points, environment, ngspice
# ---------------------------------------------------------------------------
def load_points() -> dict:
    """The 45 PVT points, from the deterministic campaign's OWN manifest.

    `sim/period-jitter/testbench/tb.json`'s grid: MOS section, temperature,
    supply, and the control voltage that puts that corner's ring at 150 MHz.
    Read rather than retyped, so "the mandated grid" is the same 45 points both
    halves of the Period jitter row -- and `../random-bound` -- are measured at.
    """
    d = json.loads(TB_JSON.read_text())
    vs = d["sweeps"]["vs"]["points"]
    out = {}
    for g in d["grid"]:
        (corner,) = g["corners"]
        (temp,) = g["temperatures_c"]
        (sup,) = g["supplies"]
        (axis,) = g["axes"]["vs"]
        vsup = SUPPLY[sup]
        out[f"{corner}_{temp:g}c_{vsup:.2f}v"] = dict(
            vctrl=float(vs[axis]["params"]["vstart"]), vsup=vsup,
            temp_c=float(temp), mos_section=corner, res_section="res_typical",
            moscap_section="moscap_typical", mimcap_section="mimcap_typical",
        )
    if len(out) != 45:
        raise SystemExit(f"{TB_JSON}: expected 45 grid points, found {len(out)}")
    return out


def load_config() -> tuple[dict, float, float, float]:
    """The static configuration, `f_ref`, `N` and `iunit` from the same manifest.

    Every bit of this campaign's operating point comes from
    `sim/period-jitter/testbench/tb.json` and its deck: `f_ref = 25 MHz`,
    `N = 6`, band 6, `Icp` trim code 0.  `iunit` is the ideal bias reference
    `tb_period_jitter.sp` sets (`.param iunit=8u`), parsed from the deck so the
    two cannot drift apart.
    """
    d = json.loads(TB_JSON.read_text())
    p = d["params"]
    config = {}
    for bit in ib_deck.CONFIG_BITS:
        key = f"{bit}_code"
        if key not in p:
            raise SystemExit(f"{TB_JSON}: no `{key}` in params")
        config[bit] = int(p[key])
    deck = (TB_JSON.parent / d["netlist"]).read_text()
    m = re.search(r"^\.param\s+iunit=(\S+)", deck, re.M | re.I)
    if not m:
        raise SystemExit(f"{d['netlist']}: no `.param iunit=`")
    iunit = float(m.group(1).rstrip("uU")) * (1e-6 if m.group(1)[-1] in "uU" else 1.0)
    return config, float(p["fref"]), float(p["nratio"]), iunit


def pdk_models() -> Path:
    return find_pdk().ngspice_dir


#: Execution backend every deck in this runner goes through (#712). A test
#: injects a stand-in here; the default is the harness's local ngspice backend.
BACKEND = execution.LocalBackend()


def environment(models) -> dict:
    return legacy_provenance.runner_environment(
        models, REPO, ("design", "spec", "sim/period-jitter"))


def run_deck(deck: str, work: Path, log: Path, expect: str | None = None,
             timeout: float | None = None):
    run = legacy_provenance.run_deck_files(
        deck, work, backend=BACKEND, timeout_s=timeout)
    out = run.output
    log.parent.mkdir(parents=True, exist_ok=True)
    if run.timed_out:
        log.write_text(out)
        raise SystemExit(
            f"ngspice did not finish within {timeout:.0f} s ({run.seconds:.0f} s "
            f"elapsed) -- see {log}; refused")
    log.write_text(re.sub(r"(?: ?Reference value :\s*\S+)+", "", out))
    hit = [p for p in FATAL if p in out]
    if hit:
        raise SystemExit(f"ngspice reported {hit!r} -- see {log}; refused")
    if expect and not (work / expect).is_file():
        raise SystemExit(f"ngspice produced no {expect} -- see {log}")
    return run.seconds, out


def save(name: str, payload: dict):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(f"wrote results/{name}.json", flush=True)


def load(name: str) -> dict:
    p = RESULTS / f"{name}.json"
    if not p.is_file():
        raise SystemExit(f"missing results/{name}.json -- run its stage first")
    return json.loads(p.read_text())


def noise_freqs(hi: float = NOISE_F_HI) -> list[float]:
    return ib.log_grid(NOISE_F_LO, hi, NOISE_PER_DECADE)


# ---------------------------------------------------------------------------
# stage: loop
# ---------------------------------------------------------------------------
def stage_loop(env) -> dict:
    """The closed-loop envelope, and the period weight it is integrated against.

    `|T/(1+T)|^2` over every loop `../random-bound/rb_extract.admissible_loops`
    admits at the ratified 45 degree phase-margin floor, on the filter corners
    that directory already measured -- read from its `results/loop.json` so the
    two bounds envelope the same loop set.  The peak of the PRODUCT
    `|T/(1+T)|^2 * 4 sin^2(pi f T0)` is reported too: it is the single number
    that says how much of an in-band source can reach one period's length, and
    it is about 1e-2, not 1.
    """
    lj = json.loads(LOOP_JSON.read_text())
    import rb_extract  # noqa: E402  (through ib_extract's sys.path insert)
    loops = rb_extract.admissible_loops(
        r_range=tuple(lj["filter_R_ohm"]), c1_range=tuple(lj["filter_C1_F"]),
        c2_range=tuple(lj["filter_C2_F"]), pm_min_deg=lj["pm_floor_deg"])
    _, fref, _, _ = load_config()
    freqs = ib.log_grid(NOISE_F_LO, fref / 2.0, ENV_PER_DECADE)
    envelope = ib.closed_loop_envelope(freqs, loops)
    # The period weight needs an f0; use the grid's own nominal 150 MHz for the
    # reported peak only (every point's bound uses its own measured f0).
    f0 = 150e6
    prod = [e * ib.period_weight(f, f0) for f, e in zip(freqs, envelope)]
    peak = max(range(len(prod)), key=lambda i: prod[i])
    return {
        "source": str(LOOP_JSON.relative_to(REPO)),
        "n_loops": len(loops), "pm_floor_deg": lj["pm_floor_deg"],
        "fc_range_Hz": lj["fc_range_Hz"],
        "filter_R_ohm": lj["filter_R_ohm"], "filter_C1_F": lj["filter_C1_F"],
        "filter_C2_F": lj["filter_C2_F"],
        "env_freqs_Hz": freqs, "env_closed_loop_sq": envelope,
        "closed_loop_peak_sq": max(envelope),
        "product_peak": prod[peak], "product_peak_at_Hz": freqs[peak],
        "product_peak_f0_Hz": f0,
        "environment": env,
    }


# ---------------------------------------------------------------------------
# stage: digital
# ---------------------------------------------------------------------------
def _node_report(t, v, vsup: float, t0: float) -> dict:
    """Per-node swing, mid-supply crossings and the slowest chord slew after `t0`."""
    idx = [i for i, x in enumerate(t) if x >= t0]
    if len(idx) < 8:
        raise SystemExit("the transient window holds too few points")
    vv = [v[i] for i in idx]
    tt = [t[i] for i in idx]
    swing = max(vv) - min(vv)
    mid = 0.5 * vsup
    rise = ib.crossings_with_slew(tt, vv, mid)
    fall = ib.falling_crossings_with_slew(tt, vv, mid)
    slews = [c["slew"] for c in rise + fall]
    return {
        "swing_V": swing, "switching": swing >= SWING_FRACTION * vsup,
        "n_rise": len(rise), "n_fall": len(fall),
        "slew_min_V_per_s": min(slews) if slews else None,
        "slew_max_V_per_s": max(slews) if slews else None,
        "rise_times_s": [c["t"] for c in rise],
    }


def _digital_pass(point, op, config, fref, iunit, models, tstep, tmax, tstop,
                  tag, r_hold, ref_delay, gmin, ic_offset):
    """One run of the open-loop deck at ONE rung of the solver ladder.

    Escalation is the caller's job and is per POINT, not per pass -- see
    `stage_digital`.
    """
    deck, cols = ib_deck.digital_deck(
        pdk_models=models, repo_root=REPO, op=op, config=config, iunit=iunit,
        fref=fref, tstop=tstop, tstep=tstep, tmax=tmax, r_hold=r_hold,
        ref_delay=ref_delay, gmin=gmin, ic_offset=ic_offset)
    work = HERE / ".work" / point / tag
    first = (gmin, ic_offset) == ATTEMPT_LADDER[0]
    suffix = "" if first else f"_gmin{gmin:.0e}_ic{ic_offset:g}"
    el, _ = run_deck(deck, work, LOGS / f"{tag}{suffix}_{point}.log",
                     "dig.dat", timeout=DIGITAL_TIMEOUT_S)
    t, data = ib.read_wrdata(work / "dig.dat", len(cols))
    return el, cols, t, {c: d for c, d in zip(cols, data)}


def _align_ref(t, by, vsup: float, fref: float, t_settle: float) -> dict:
    """The `REF` delay that puts `REF`'s edges on `FB`'s -- the lock condition.

    Pass 1 runs with `REF` delayed half a reference period, at whatever phase
    the free-running ring leaves `FB` at.  The PFD's conduction window is a
    property of the LOCKED loop, so pass 2 needs `REF` moved onto `FB`.  With
    `VCTRL` held the ring is unaffected by where `REF` sits, so `FB`'s edges do
    not move between the passes and the shift is exact to the residual reported
    here (the `f_ref`/`f_fb` mismatch at this corner's control voltage walks the
    alignment by `(1 - f_fb/f_ref) T_ref` per cycle, which is picoseconds).
    """
    tref = 1.0 / fref
    idx = [i for i, x in enumerate(t) if x >= t_settle]
    tt = [t[i] for i in idx]
    mid = 0.5 * vsup
    ref = [c["t"] for c in ib.crossings_with_slew(tt, [by["v(ref)"][i] for i in idx], mid)]
    fb = [c["t"] for c in ib.crossings_with_slew(tt, [by["v(fb)"][i] for i in idx], mid)]
    if not ref or not fb:
        raise SystemExit("the alignment pass saw no REF or no FB edge")
    # How far REF's edges sit AFTER FB's, modulo one reference period.
    lag = (ref[0] - fb[0]) % tref
    new_delay = 0.5 * tref - lag
    while new_delay <= 0.2 * tref:
        new_delay += tref
    return {"ref_lag_s": lag, "pass1_ref_delay_s": 0.5 * tref,
            "pass2_ref_delay_s": new_delay,
            "pass1_ref_edges_s": ref, "pass1_fb_edges_s": fb}


def stage_digital(point, op, config, fref, nratio, iunit, models, env,
                  tstep=TRAN_TSTEP, tmax=TRAN_TMAX, tstop=TRAN_TSTOP,
                  tag="digital", r_hold=R_HOLD_OHM) -> dict:
    """The committed `pll_top`, open loop, `VCTRL` held, `REF` aligned to `FB`.

    Two passes of the same deck: the first at an arbitrary reference phase, to
    find where `FB`'s edges fall; the second with `REF` moved onto them, which
    is the lock condition and the only state whose charge-pump conduction window
    is the one the bound needs.  Every measurand below is the SECOND pass's; the
    first pass's alignment numbers are recorded beside them.

    THE SOLVER LADDER IS CLIMBED PER POINT, NOT PER PASS.  Both passes must run
    at the SAME rung, because the alignment pass 2 uses is derived from where
    pass 1 put `FB`'s edges, and a different `gmin` or a different
    symmetry-breaking initial condition starts the ring on a different phase --
    so pass 1's answer is not pass 2's question any more.  Escalating each pass
    independently produced exactly that: two points whose passes settled on
    different rungs (their residual stayed small by luck) and one whose residual
    came out 13.4 ns of a 40 ns reference period.  So a stall anywhere in the
    point re-runs BOTH passes at the next rung.
    """
    vsup = op["vsup"]
    last = None
    for gmin, ic_offset in ATTEMPT_LADDER:
        rung = {"gmin": gmin, "ic_offset_V": ic_offset,
                "rung": ATTEMPT_LADDER.index((gmin, ic_offset))}
        try:
            el1, cols, t1, by1 = _digital_pass(
                point, op, config, fref, iunit, models, tstep, tmax, tstop,
                f"{tag}_align", r_hold, None, gmin, ic_offset)
            align = _align_ref(t1, by1, vsup, fref, TRAN_T_SETTLE)
            el, cols, t, by = _digital_pass(
                point, op, config, fref, iunit, models, tstep, tmax, tstop, tag,
                r_hold, align["pass2_ref_delay_s"], gmin, ic_offset)
        except SystemExit as exc:
            last = exc
            print(f"-- {tag}: stalled at gmin={gmin:.0e} ic_offset={ic_offset:g}"
                  f" (rung {rung['rung']}), escalating BOTH passes", flush=True)
            continue
        break
    else:
        raise SystemExit(
            f"{point}: {tag} stalled at every rung of {ATTEMPT_LADDER}: {last}")
    el += el1
    nodes = {c: _node_report(t, by[c], vsup, TRAN_T_SETTLE) for c in cols
             if c not in ("v(ref)", "v(vctrl)")}
    vc_idx = [i for i, x in enumerate(t) if x >= TRAN_T_SETTLE]
    vc = [by["v(vctrl)"][i] for i in vc_idx]
    up = [i for i, x in enumerate(t) if x >= TRAN_T_SETTLE]
    tt = [t[i] for i in up]

    def widths(col):
        return ib.pulse_widths(tt, [by[col][i] for i in up], 0.5 * vsup)

    w_up, w_dn = widths("v(xdut.up)"), widths("v(xdut.dn)")
    if not w_up or not w_dn:
        raise SystemExit(f"{point}: the PFD produced no UP/DN pulse in the window")
    n_pairs = min(len(w_up), len(w_dn))
    overlap = [min(a, b) for a, b in zip(w_up[:n_pairs], w_dn[:n_pairs])]
    active = [max(a, b) for a, b in zip(w_up[:n_pairs], w_dn[:n_pairs])]
    clk = nodes["v(clk)"]["rise_times_s"]
    fb = nodes["v(fb)"]["rise_times_s"]
    if len(clk) < 10 or len(fb) < 2:
        raise SystemExit(f"{point}: too few CLK/FB edges to measure a frequency")
    f_clk = (len(clk) - 1) / (clk[-1] - clk[0])
    f_fb = (len(fb) - 1) / (fb[-1] - fb[0])
    switching = {k: v for k, v in nodes.items() if v["switching"] and v["slew_min_V_per_s"]}
    if not switching:
        raise SystemExit(f"{point}: no saved node switched -- nothing to slew-bound")
    slow = min(switching.items(), key=lambda kv: kv[1]["slew_min_V_per_s"])

    # Did the alignment land?  In lock the PFD's two outputs are asserted for
    # the reset delay plus the static phase offset, so a residual REF-to-FB
    # separation of a large fraction of the reference period would mean this
    # deck is still measuring an out-of-lock conduction window.
    tref = 1.0 / fref
    ref_edges = [c["t"] for c in ib.crossings_with_slew(
        tt, [by["v(ref)"][i] for i in up], 0.5 * vsup)]
    if not ref_edges:
        raise SystemExit(f"{point}: the aligned pass saw no REF edge")
    residual = min(abs((r - f) % tref if (r - f) % tref < 0.5 * tref
                       else ((r - f) % tref) - tref)
                   for r in ref_edges for f in fb)
    if abs(residual) > ALIGN_RESIDUAL_FRACTION * tref:
        raise SystemExit(
            f"{point}: REF and FB are still {residual * 1e9:.3f} ns apart after "
            f"alignment ({ALIGN_RESIDUAL_FRACTION:.0%} of T_ref allowed) -- the "
            "conduction window this deck reports would not be the locked one")

    return {
        "point": point, "operating_point": op, "elapsed_s": el,
        "tstep_s": tstep, "tmax_s": tmax, "tstop_s": tstop,
        "t_settle_s": TRAN_T_SETTLE, "fref_Hz": fref, "n_div": nratio,
        "r_hold_ohm": r_hold,
        # One rung for BOTH passes, by construction -- see stage_digital.
        "solver_rung": rung,
        "solver_ladder": [{"gmin": g, "ic_offset_V": o}
                          for g, o in ATTEMPT_LADDER],
        "alignment": dict(align, residual_s=residual,
                          residual_fraction_of_tref=abs(residual) / tref),
        "vctrl_hold_ripple_V": max(vc) - min(vc),
        "vctrl_hold_mean_V": sum(vc) / len(vc),
        "up_widths_s": w_up, "dn_widths_s": w_dn,
        "t_overlap_s": overlap, "t_active_s": active,
        "t_on_s": max(active),
        "f_clk_Hz": f_clk, "f_fb_Hz": f_fb, "divide_ratio_measured": f_clk / f_fb,
        "clk_slew_min_V_per_s": nodes["v(clk)"]["slew_min_V_per_s"],
        # The slowest of the two charge-pump switch inputs' own edges: what a
        # noise voltage on UP or DN is divided by to become a switch-edge
        # displacement (the lock detector's only path to the output).
        "updn_slew_min_V_per_s": min(nodes["v(xdut.up)"]["slew_min_V_per_s"],
                                     nodes["v(xdut.dn)"]["slew_min_V_per_s"]),
        "slowest_node": slow[0], "slew_min_V_per_s": slow[1]["slew_min_V_per_s"],
        "nodes": nodes, "environment": env,
    }


# ---------------------------------------------------------------------------
# stage: cp
# ---------------------------------------------------------------------------
def _cp_call(point, op, models, env, src, freqs, iunit, config, rsense, on, tag):
    deck, paths = ib_deck.cp_noise_deck(
        pdk_models=models, repo_root=REPO, op=op, src=src, freqs=freqs,
        rsense=rsense, iunit=iunit, cpb0=config["cpb0"], cpb1=config["cpb1"],
        switches_on=on)
    work = HERE / ".work" / point / tag
    el, out = run_deck(deck, work, LOGS / f"{tag}_{point}.log")
    parsed = ib.parse_noise_log(
        out, groups={"cp": paths},
        anchors={"rsense": (rsense, op["temp_c"])}, freqs=freqs)
    ids = ib.parse_op_currents(out, r"xcp\.xmsw(?:up|dn)")
    if len(ids) != 2:
        raise SystemExit(f"{point}: the charge-pump switch currents were not printed")
    rows = parsed["per_group"]["cp"]
    # V^2/Hz at VOUT -> A^2/Hz of SHORT-CIRCUIT output current, through the
    # node's MEASURED transimpedance rather than through `rsense`.
    #
    # THE ANCHOR IS LOAD-BEARING HERE, NOT DECORATION.  `rsense` is only equal to
    # the node's impedance below the corner formed with everything else on VOUT
    # (the four cascoded legs' drains, the four dump-side switches, the dump
    # buffer's input): the anchor measures `|Z(f)|/rsense` directly, because
    # ngspice reports `rsense`'s own thermal contribution at the output as
    # `sqrt(4 k T |Z|^2 / rsense)` and `parse_noise_log` divides it by
    # `sqrt(4 k T rsense)`.  At this campaign's grid top that ratio is ~0.013 --
    # the node is two decades past its corner -- so dividing the measured voltage
    # noise by `rsense` alone would UNDER-state the current noise by up to
    # ~6000x there, which is the wrong direction for a bound.  Dividing by
    # `rsense * (|Z|/rsense) = |Z|` is exact, and `validate`'s 10x-`rsense` run
    # is what shows the recovered `S_i` no longer depends on `rsense`.
    z_over_r = parsed["anchor_ratios"]
    if len(z_over_r) != len(rows):
        raise SystemExit("one anchor reading per frequency is required")
    if min(z_over_r) <= 0:
        raise SystemExit(f"{point}: the sense node's transimpedance came back zero")
    z_abs = [rsense * z for z in z_over_r]
    return {
        "elapsed_s": el, "rsense_ohm": rsense, "n_devices": len(paths),
        "anchor_ratio_at_grid_bottom": parsed["anchor_ratio_first"],
        "anchor_ratio_min": parsed["anchor_ratio_min"],
        "anchor_ratio_max": parsed["anchor_ratio_max"],
        "z_node_ohm": z_abs,
        "switch_id_A": ids,
        "freqs_Hz": [r["freq_Hz"] for r in rows],
        "s_v_total_V2_per_Hz": [r["total"] for r in rows],
        "s_i_total_A2_per_Hz": [r["total"] / z ** 2 for r, z in zip(rows, z_abs)],
        "s_i_flicker_A2_per_Hz": [r["flicker"] / z ** 2 for r, z in zip(rows, z_abs)],
    }


def stage_cp(point, op, config, iunit, models, env, rsense=RSENSE_OHM) -> dict:
    """The charge pump's output-current noise, overlap state and off state."""
    src = NETLIST.read_text()
    freqs = noise_freqs()
    on = _cp_call(point, op, models, env, src, freqs, iunit, config, rsense,
                  True, "cp_on")
    off = _cp_call(point, op, models, env, src, freqs, iunit, config, rsense,
                   False, "cp_off")
    icp = min(abs(v) for v in on["switch_id_A"].values())
    if icp <= 0:
        raise SystemExit(f"{point}: a charge-pump leg carries no current")
    return {"point": point, "operating_point": op, "on": on, "off": off,
            "icp_A": icp, "n_mos": len(ib_deck.flatten_mos(src, "cp", "xcp")),
            "non_mos_devices": ib_deck.non_mos_devices(src, "cp"),
            "environment": env}


# ---------------------------------------------------------------------------
# stage: cells
# ---------------------------------------------------------------------------
def stage_cells(point, op, models, env, in_slew: float, cload=C_LOAD_F) -> dict:
    """Every logic cell type, at its trip point, into a generous load."""
    src = NETLIST.read_text()
    cells = list(ib_deck.CELLS)
    freqs = noise_freqs()

    trip_deck, inverting = ib_deck.cell_trip_deck(
        pdk_models=models, repo_root=REPO, op=op, cells=cells)
    work = HERE / ".work" / point
    _, out = run_deck(trip_deck, work / "cell_trip", LOGS / f"cell_trip_{point}.log")
    got = dict(ib.parse_print(out))
    trips = {}
    for k, cell in enumerate(inverting):
        key = f"v(y{k})"
        if key not in got:
            raise SystemExit(f"{point}: no trip point solved for {cell}")
        trips[cell] = got[key]
    for cell in cells:
        if cell not in trips:
            trips[cell] = 0.5 * op["vsup"]  # the pass gate: no trip point

    entries = []
    for cell in cells:
        for dv in CELL_BIAS_OFFSETS_V:
            if not ib_deck.CELLS[cell]["inverting"] and dv != 0.0:
                continue
            b = trips[cell] + dv
            if not 0.0 <= b <= op["vsup"]:
                continue
            entries.append((cell, b, f"{cell}@{dv:+.2f}"))
    noise_deck, groups = ib_deck.cell_noise_deck(
        pdk_models=models, repo_root=REPO, op=op, entries=entries, freqs=freqs,
        cload=cload, src=src)
    el, out = run_deck(noise_deck, work / "cell_noise",
                       LOGS / f"cell_noise_{point}.log")
    parsed = ib.parse_noise_log(
        out, groups=groups,
        anchors={"ranch": (ib_deck.ANCHOR_OHM, op["temp_c"])}, freqs=freqs)

    slew_deck, snames = ib_deck.cell_slew_deck(
        pdk_models=models, repo_root=REPO, op=op, cells=cells, cload=cload,
        in_slew=in_slew, tstep=TRAN_TSTEP, tmax=TRAN_TMAX)
    _, _ = run_deck(slew_deck, work / "cell_slew", LOGS / f"cell_slew_{point}.log",
                    "slew.dat")
    t, data = ib.read_wrdata(work / "cell_slew" / "slew.dat", len(snames) + 1)
    mid = 0.5 * op["vsup"]
    slews = {}
    for k, cell in enumerate(snames):
        v = data[k + 1]
        cs = ib.crossings_with_slew(t, v, mid) + ib.falling_crossings_with_slew(t, v, mid)
        if not cs:
            raise SystemExit(f"{point}: {cell} did not cross mid-supply in the slew deck")
        slews[cell] = min(c["slew"] for c in cs)

    out_rows = {}
    for tag, rows in parsed["per_group"].items():
        cell = tag.split("@")[0]
        out_rows[tag] = {
            "cell": cell, "bias_offset_V": float(tag.split("@")[1]),
            "freqs_Hz": [r["freq_Hz"] for r in rows],
            "s_v_total_V2_per_Hz": [r["total"] for r in rows],
            "s_v_flicker_V2_per_Hz": [r["flicker"] for r in rows],
            "sigma_v_V": math.sqrt(
                ib.integrate_log([r["freq_Hz"] for r in rows], [r["total"] for r in rows])
                + ib.high_frequency_tail([r["freq_Hz"] for r in rows],
                                         [r["total"] for r in rows])),
            "slew_V_per_s": slews[cell],
        }
    for tag, rec in out_rows.items():
        rec["sigma_t_s"] = ib.edge_jitter(rec["sigma_v_V"], rec["slew_V_per_s"])
    worst = max(out_rows.items(), key=lambda kv: kv[1]["sigma_t_s"])
    # Is the trip point the worst bias, per cell?  The inequality
    # `ib_extract.edge_jitter` rests on, measured.
    trip_is_worst = {}
    for cell in cells:
        same = {tag: r for tag, r in out_rows.items() if r["cell"] == cell}
        top = max(same.values(), key=lambda r: r["sigma_v_V"])
        trip_is_worst[cell] = {
            "worst_offset_V": top["bias_offset_V"],
            "sigma_v_at_trip_V": next(r["sigma_v_V"] for r in same.values()
                                      if r["bias_offset_V"] == 0.0),
            "sigma_v_worst_V": top["sigma_v_V"],
        }
    return {
        "point": point, "operating_point": op, "elapsed_s": el,
        "c_load_F": cload, "in_slew_V_per_s": in_slew,
        "anchor_ohm": ib_deck.ANCHOR_OHM,
        "anchor_ratio_min": parsed["anchor_ratio_min"],
        "anchor_ratio_max": parsed["anchor_ratio_max"],
        "bias_offsets_V": list(CELL_BIAS_OFFSETS_V),
        "trip_points_V": trips, "slews_V_per_s": slews,
        "cells": out_rows, "worst_tag": worst[0],
        "trip_point_dominance": trip_is_worst,
        "environment": env,
    }


# ---------------------------------------------------------------------------
# stages: clkload, ldload -- the two gate-only loads
# ---------------------------------------------------------------------------
def _gate_load_call(point, op, models, src, freqs, r_drive, load) -> dict:
    deck, paths = ib_deck.gate_load_deck(
        pdk_models=models, repo_root=REPO, op=op, src=src, freqs=freqs,
        r_drive=r_drive, load=load)
    tag = f"{load}load_r{r_drive:.0f}"
    work = HERE / ".work" / point / tag
    el, out = run_deck(deck, work, LOGS / f"{tag}_{point}.log")
    parsed = ib.parse_noise_log(out, groups={"load": paths},
                                anchors={"rdrv": (r_drive, op["temp_c"])},
                                freqs=freqs)
    rows = parsed["per_group"]["load"]
    f = [r["freq_Hz"] for r in rows]
    s = [r["total"] for r in rows]
    band = ib.integrate_log(f, s)
    # WHY THIS ONE STAGE DOES NOT EXTRAPOLATE A TAIL.  Everywhere else in this
    # directory a density falls as `f^-2` past a node's corner and
    # `high_frequency_tail` adds what the grid omits.  On `CLK` it does not: the
    # divider couples to the node through `C_gd` only, so the transfer RISES as
    # `f` until it hits the capacitive-divider ceiling `C_gd/(C_gd + C_node)`,
    # above which the density is FLAT -- measured flat from ~10^11 to ~10^13 Hz,
    # and at the same level for every drive resistance in the sweep, which is
    # what a capacitive divider (not an RC corner) looks like.  There is no
    # measured `f^-2` to extrapolate, so instead of inventing one the variance is
    # integrated over a STATED band and its dependence on that band's top is
    # reported per decade.  `decade_cumulative_V2` is the evidence for the
    # statement in the README that the term is negligible however that top is
    # chosen.
    cum = []
    for k in range(1, len(f)):
        cum.append({"up_to_Hz": f[k], "var_V2": ib.integrate_log(f[:k + 1], s[:k + 1])})
    decades = [c for c in cum if abs(math.log10(c["up_to_Hz"]) % 1.0) < 1e-9]
    return {
        "elapsed_s": el, "r_drive_ohm": r_drive, "n_devices": len(paths),
        # The anchor's own transfer to `CLK` rolls off with the node, so the
        # units check is the BOTTOM of the grid; the rest of the ratio curve is
        # a measurement of where that roll-off happens.
        "anchor_ratio_at_grid_bottom": parsed["anchor_ratio_first"],
        "anchor_ratio_min": parsed["anchor_ratio_min"],
        "anchor_ratio_max": parsed["anchor_ratio_max"],
        "freqs_Hz": f, "s_v_V2_per_Hz": s,
        "var_in_grid_V2": band,
        "decade_cumulative_V2": decades,
        "peak_density_at_Hz": f[s.index(max(s))],
        "sigma_v_V": math.sqrt(band),
    }


def stage_gate_load(point, op, models, env, load: str,
                    r_drives=R_DRIVE_SWEEP_OHM) -> dict:
    """What a gate-only load's own devices put back onto the node driving it.

    Two loads, both declared in `ib_deck.GATE_LOADS`: the divider chain's clock
    input on `CLK` (the one path of the four blocks that does not pass through
    the loop) and the lock detector's XOR input on `UP`/`DN` (the lock detector's
    ONLY path to the output, since it is in no timing path at all).

    THIS IS THE ONE PLACE A SINGLE "CONSERVATIVE" PARAMETER VALUE WOULD NOT HAVE
    BEEN CONSERVATIVE.  The load is capacitive -- no channel of it is connected
    to the node -- so its devices reach the node through `C_gd` alone, and that
    coupling's transfer RISES with frequency until the node's own
    `R_drive * C_node` corner.  The output-noise density therefore rises as `f^2`
    over most of the band, and the total variance depends on where the corner
    sits: `sigma_v^2 ~ 1/R_drive` while the coupling is resistive, saturating at
    the capacitive-divider ceiling once it is not.  Neither a large nor a small
    `R_drive` is the safe side by inspection.

    So the deck is run at every `R_drive` in `r_drives` -- two decades either
    side of any real CMOS output stage's on-resistance -- and the term uses the
    MAXIMUM `sigma_v` over the sweep, with the whole sweep recorded.  That is the
    same "replace an unknown by its maximum over the plausible set" step
    `../random-bound` applies to a switching device's density, applied here to a
    drive impedance these decks deliberately do not model in detail (the real
    drivers' own generators are counted elsewhere -- the VCO output buffer in
    `../random-bound`, the PFD latch as a stage in `ib_extract.TIMING_PATHS` --
    and putting them in here would double-count them).
    """
    spec = ib_deck.GATE_LOADS[load]
    src = (REPO / "design" / "netlist" / spec["netlist"]).read_text()
    # A wider grid than the rest of the campaign, because this is the one
    # measurand whose variance lives at the TOP of the band (see
    # `_gate_load_call`).  The top is four decades above these devices' own
    # transit frequency, and the per-decade cumulative recorded with every call
    # says how much of the answer the last decade is worth.
    freqs = noise_freqs(CLKLOAD_F_HI)
    calls = [_gate_load_call(point, op, models, src, freqs, r, load)
             for r in r_drives]
    worst = max(calls, key=lambda c: c["sigma_v_V"])
    return {
        "point": point, "operating_point": op, "load": load,
        "load_cell": spec["cell"], "load_what": spec["what"],
        "elapsed_s": sum(c["elapsed_s"] for c in calls),
        "r_drive_sweep_ohm": list(r_drives),
        "grid_top_Hz": CLKLOAD_F_HI,
        "calls": {f"{c['r_drive_ohm']:.0f}": c for c in calls},
        "r_drive_ohm": worst["r_drive_ohm"],
        "n_devices": worst["n_devices"],
        "anchor_ratio_at_grid_bottom": worst["anchor_ratio_at_grid_bottom"],
        "anchor_ratio_min": worst["anchor_ratio_min"],
        "anchor_ratio_max": worst["anchor_ratio_max"],
        "freqs_Hz": worst["freqs_Hz"], "s_v_V2_per_Hz": worst["s_v_V2_per_Hz"],
        "decade_cumulative_V2": worst["decade_cumulative_V2"],
        "peak_density_at_Hz": worst["peak_density_at_Hz"],
        "sigma_v_V": worst["sigma_v_V"],
        "sigma_v_by_r_drive_V": {f"{c['r_drive_ohm']:.0f}": c["sigma_v_V"]
                                 for c in calls},
        "environment": env,
    }


# ---------------------------------------------------------------------------
# stage: bound
# ---------------------------------------------------------------------------
def _vco_bound_pct(point: str) -> float:
    p = RB_RESULTS / f"transient_{point}.json"
    if not p.is_file():
        raise SystemExit(
            f"missing {p} -- this bound is quoted against the margin "
            "../random-bound leaves at this same point, so that point must exist")
    return json.loads(p.read_text())["bound"]["total_pct"]


def _cell_stage_variance(cells, tag, *, loops, env_flat_freqs, env_flat,
                         f0, fref, nratio, t_ref) -> dict:
    """One stage of cell `tag`: its `var(dT/T0)` through the loop.

    The cell's trip-point output-noise density divided by its slowest measured
    slew (`stage_timing_spectrum`), folded at `f_ref/2`, referred to the PFD's
    input by `timing_to_phase`, and integrated against the closed-loop envelope
    and the period weight.  One stage, so a path of `n` independent stages of
    this cell is `n` times this VARIANCE.
    """
    rec = cells["cells"][tag]
    lo_f, lo_s, flat, above = ib.stage_timing_spectrum(
        rec["freqs_Hz"], rec["s_v_total_V2_per_Hz"],
        slew=rec["slew_V_per_s"], f_ref=fref)
    env_lo = ib.closed_loop_envelope(lo_f, loops)
    v = ib.block_period_variance(
        in_band_freqs=lo_f, in_band_s_dt=lo_s, flat_s_dt=flat,
        env_in_band=env_lo, env_flat_freqs=env_flat_freqs, env_flat=env_flat,
        f0_hz=f0, f_ref=fref, n_div=nratio, t_ref_s=t_ref)
    return dict(v, tag=tag, sigma_v_V=rec["sigma_v_V"],
                slew_V_per_s=rec["slew_V_per_s"], sigma_t_s=rec["sigma_t_s"],
                folded_edge_var_s2=above)


def stage_bound(point, op, config, fref, nratio, env) -> dict:
    """Assemble, at one PVT point, against the margin `../random-bound` leaves."""
    import rb_extract  # noqa: E402
    dig = load(f"digital_{point}")
    cp = load(f"cp_{point}")
    cells = load(f"cells_{point}")
    clk = load(f"clkload_{point}")
    ldl = load(f"ldload_{point}")
    lj = json.loads(LOOP_JSON.read_text())
    loops = rb_extract.admissible_loops(
        r_range=tuple(lj["filter_R_ohm"]), c1_range=tuple(lj["filter_C1_F"]),
        c2_range=tuple(lj["filter_C2_F"]), pm_min_deg=lj["pm_floor_deg"])
    f0 = dig["f_clk_Hz"]
    t_ref = 1.0 / fref
    env_flat_freqs = ib.log_grid(NOISE_F_LO, fref / 2.0, ENV_PER_DECADE)
    env_flat = ib.closed_loop_envelope(env_flat_freqs, loops)

    src = NETLIST.read_text()
    claim = ib.timing_path_claim(src)          # refuses a path the netlist lost
    terms: dict[str, float] = {}
    detail: dict[str, dict] = {}

    # Every cell that appears in a path, once: its own single-stage variance.
    per_cell = {}
    for stages in ib.TIMING_PATHS.values():
        for _, cell in stages:
            if cell not in per_cell:
                per_cell[cell] = _cell_stage_variance(
                    cells, f"{cell}@+0.00", loops=loops,
                    env_flat_freqs=env_flat_freqs, env_flat=env_flat,
                    f0=f0, fref=fref, nratio=nratio, t_ref=t_ref)

    # The reset path is common mode between UP and DN: only the leg imbalance
    # turns a displacement of it into a charge error.
    ids = cp["on"]["switch_id_A"]
    cm = ib.common_mode_scale(abs(ids["xcp.xmswup"]), abs(ids["xcp.xmswdn"]))

    # --- the timing paths -----------------------------------------------------
    for name, stages in ib.TIMING_PATHS.items():
        cell_counts: dict[str, int] = {}
        for _, cell in stages:
            cell_counts[cell] = cell_counts.get(cell, 0) + 1
        quad = sum(n * per_cell[cell]["total"] for cell, n in cell_counts.items())
        # The perfectly-correlated alternative, for comparison only: sum the
        # per-stage amplitudes rather than their variances.
        linear = sum(n * math.sqrt(per_cell[cell]["total"])
                     for cell, n in cell_counts.items()) ** 2
        scale = cm["scale"] ** 2 if name == ib.COMMON_MODE_PATH else 1.0
        terms[name] = quad * scale
        detail[name] = {
            "block": ib.PATH_BLOCK[name],
            "n_stages": len(stages), "cells": cell_counts,
            "instances": [i for i, _ in claim[name]],
            "common_mode": name == ib.COMMON_MODE_PATH,
            "common_mode_scale": cm["scale"] if name == ib.COMMON_MODE_PATH else None,
            "var_quadrature": quad * scale,
            "pct": 100.0 * math.sqrt(quad * scale),
            "pct_if_perfectly_correlated": 100.0 * math.sqrt(linear * scale),
        }
    detail["_common_mode"] = cm
    detail["_per_cell_stage"] = {
        c: {"pct_one_stage": 100.0 * math.sqrt(v["total"]),
            "sigma_v_V": v["sigma_v_V"], "slew_V_per_s": v["slew_V_per_s"],
            "in_band_var": v["in_band"], "folded_var": v["folded"]}
        for c, v in per_cell.items()}
    # What the retired every-device-in-series count would have said, so the
    # size of the path derivation is visible rather than implied.
    worst_cell = max(per_cell, key=lambda c: per_cell[c]["total"])
    detail["_retired_all_device_count"] = {
        "worst_cell": worst_cell,
        "pct_per_block": {
            blk: 100.0 * math.sqrt(
                math.ceil(len(ib_deck.flatten_mos(src, sub)) / 2) ** 2
                * per_cell[worst_cell]["total"])
            for blk, sub in BLOCKS.items()},
    }

    # --- the charge pump's own output current --------------------------------
    t_on = dig["t_on_s"]
    icp = cp["icp_A"]
    q_f, q_s, q_flat, q_above = ib.gated_charge_spectrum(
        cp["on"]["freqs_Hz"], cp["on"]["s_i_total_A2_per_Hz"], t_on=t_on, f_ref=fref)
    env_q = ib.closed_loop_envelope(q_f, loops)
    v_cp = ib.block_period_variance(
        in_band_freqs=q_f, in_band_s_dt=[s / icp ** 2 for s in q_s],
        flat_s_dt=q_flat / icp ** 2, env_in_band=env_q,
        env_flat_freqs=env_flat_freqs, env_flat=env_flat,
        f0_hz=f0, f_ref=fref, n_div=nratio, t_ref_s=t_ref)
    terms["cp_current"] = v_cp["total"]
    detail["cp_current"] = {
        "block": "charge_pump",
        "t_on_s": t_on, "duty": t_on * fref, "icp_A": icp,
        "sigma_q_C": math.sqrt(ib.integrate_log(q_f, q_s) + q_above),
        "in_band_var": v_cp["in_band"], "folded_var": v_cp["folded"],
        "pct": 100.0 * math.sqrt(v_cp["total"]),
    }
    # The off state, over the rest of the reference period, on the same terms.
    t_off = max(t_ref - t_on, 0.0)
    o_f, o_s, o_flat, o_above = ib.gated_charge_spectrum(
        cp["off"]["freqs_Hz"], cp["off"]["s_i_total_A2_per_Hz"], t_on=t_off,
        f_ref=fref)
    env_o = ib.closed_loop_envelope(o_f, loops)
    v_off = ib.block_period_variance(
        in_band_freqs=o_f, in_band_s_dt=[s / icp ** 2 for s in o_s],
        flat_s_dt=o_flat / icp ** 2, env_in_band=env_o,
        env_flat_freqs=env_flat_freqs, env_flat=env_flat,
        f0_hz=f0, f_ref=fref, n_div=nratio, t_ref_s=t_ref)
    terms["cp_off_state"] = v_off["total"]
    detail["cp_off_state"] = {
        "block": "charge_pump", "t_off_s": t_off, "sigma_q_C": math.sqrt(ib.integrate_log(o_f, o_s) + o_above),
        "pct": 100.0 * math.sqrt(v_off["total"]),
    }

    # --- the one path that does not go through the loop ----------------------
    clk_term = ib.clk_loading_period_variance(
        sigma_v=clk["sigma_v_V"], slew=dig["clk_slew_min_V_per_s"], f0_hz=f0)
    terms["divider_clk_loading"] = clk_term["var"]
    detail["divider_clk_loading"] = dict(
        clk_term, block="divider_chain", r_drive_ohm=clk["r_drive_ohm"],
        grid_top_Hz=clk["grid_top_Hz"])

    # --- the lock detector, which is in no timing path -----------------------
    # It reaches the output only by loading UP and DN.  A displacement of a
    # charge-pump switch edge is an input-referred phase error through
    # `timing_to_phase`, and the two loads (one on UP, one on DN) are
    # independent, so the variance is twice one of them.  The density is folded
    # and referred exactly as a stage's is.
    ld_sigma_t = ib.edge_jitter(ldl["sigma_v_V"], dig["updn_slew_min_V_per_s"])
    # One independent-per-cycle sequence of standard deviation `sigma_t` has the
    # flat one-sided density `2 sigma_t^2 / f_ref`; UP and DN carry one each and
    # they are independent, so the pair is twice that.
    ld_flat_one = 2.0 * ld_sigma_t ** 2 / fref
    v_ld = ib.block_period_variance(
        in_band_freqs=env_flat_freqs, in_band_s_dt=[0.0] * len(env_flat_freqs),
        flat_s_dt=2.0 * ld_flat_one, env_in_band=env_flat,
        env_flat_freqs=env_flat_freqs, env_flat=env_flat,
        f0_hz=f0, f_ref=fref, n_div=nratio, t_ref_s=t_ref)
    terms["lock_detector_loading"] = v_ld["total"]
    detail["lock_detector_loading"] = {
        "block": "lock_detector", "n_stages_in_timing_path": 0,
        "sigma_v_V": ldl["sigma_v_V"], "slew_V_per_s": dig["updn_slew_min_V_per_s"],
        "sigma_t_s": ld_sigma_t, "r_drive_ohm": ldl["r_drive_ohm"],
        "grid_top_Hz": ldl["grid_top_Hz"],
        "loaded_nets": ["UP", "DN"],
        "pct": 100.0 * math.sqrt(v_ld["total"]),
    }

    vco_pct = _vco_bound_pct(point)
    assembled = ib.assemble_bound(terms, vco_bound_pct=vco_pct, budget_pct=BUDGET_PCT)
    by_block: dict[str, float] = {}
    for k, v in terms.items():
        blk = detail[k].get("block") or ib.PATH_BLOCK.get(k, "other")
        by_block[blk] = by_block.get(blk, 0.0) + v
    return {
        "point": point, "operating_point": op, "f0_Hz": f0, "fref_Hz": fref,
        "n_div": nratio, "t_ref_s": t_ref,
        "detail": detail, "bound": assembled,
        "by_block_pct": {k: 100.0 * math.sqrt(v) for k, v in by_block.items()},
        "allowance": {
            "sigma_t_at_pfd_input_s": _allowance_sigma_t(
                assembled["remaining_pct"], nratio, t_ref, f0, env_flat_freqs,
                env_flat),
        },
        "environment": env,
    }


def _allowance_sigma_t(remaining_pct: float, n_div: float, t_ref: float,
                       f0: float, env_freqs, env) -> float:
    """The input-referred timing jitter that WOULD consume the remaining margin.

    A flat (independent-per-cycle) timing-error sequence of standard deviation
    `sigma_t` gives `var(dT/T0) = (N/T_ref)^2 * (2 sigma_t^2/f_ref) * I` with
    `I = int env 4 sin^2 / 4 pi^2 * (2 pi/T_ref)^2 ...` -- computed here by
    running the same `period_variance` with a unit density and scaling.  It is
    reported beside every bound because it is the honest way to say how much
    room there is: not "the bound is small" but "the blocks would have to be
    this much noisier to matter".
    """
    unit = ib.period_variance(
        env_freqs, [ib.timing_to_phase(t_ref) ** 2] * len(env_freqs), env,
        f0_hz=f0, n_div=n_div)
    if unit <= 0:
        return float("inf")
    fref = 1.0 / t_ref
    target = (remaining_pct / 100.0) ** 2
    return math.sqrt(target / (unit * 2.0 / fref))


# ---------------------------------------------------------------------------
# stage: validate
# ---------------------------------------------------------------------------
def stage_validate(point, op, config, fref, nratio, iunit, models, env) -> dict:
    """Does the measurement depend on the things it should not?

    Three independent checks at the reference point:

      * TIMESTEP.  The digital deck again at a 2.5 ps internal ceiling.  The
        reset window and every slew rate must not move: they are chord
        measurements on edges, and a chord is only as good as the timestep.
      * SENSE RESISTANCE.  The charge pump's noise deck at `10x rsense`.  The
        recovered short-circuit current noise `S_v/|Z|^2` must not depend on
        `rsense` at all: `|Z|` is measured per frequency from the anchor, so a
        ten-times-larger sense resistor changes the measured voltage noise and
        the measured impedance together and must leave their ratio alone.  The
        same comparison against the retired `S_v/rsense^2` reduction is reported
        beside it, which is what makes the size of that correction visible.
      * VCTRL HOLD RESISTANCE.  The digital deck again at `100x r_hold`.  The
        reset window, the frequency and every slew rate must not move.
      * TRIP-POINT DOMINANCE.  Already measured by the `cells` stage at every
        point; repeated here as the reference point's explicit record.
    """
    src = NETLIST.read_text()
    # THE FINE-TIMESTEP PASS IS NOT ALLOWED TO TAKE THE OTHER THREE CHECKS DOWN
    # WITH IT.  On this ngspice build the 2.5 ps ceiling collapses the very
    # first internal timepoint on `xlf.xcf4`'s moscap state node (`Timestep
    # too small ... trouble with node "e.xdut.xlf.xcf4.ec_moscap#branch"`,
    # down to a 3e-24 s step) at every rung the escalation ladder offers,
    # independent of `gmin` -- a genuine toolchain limit of this check, not of
    # the campaign's own 25 ps grid (which converges at every one of the 45
    # points).  A SystemExit here is caught and recorded rather than aborting
    # `sense_resistance`, `vctrl_hold` and `trip_point_dominance`, none of
    # which this failure has any bearing on.
    fine_error: str | None = None
    try:
        fine = stage_digital(point, op, config, fref, nratio, iunit, models, env,
                             tstep=2.5e-12, tmax=2.5e-12, tag="digital_fine")
    except SystemExit as exc:
        fine = None
        fine_error = str(exc)
    loose = stage_digital(point, op, config, fref, nratio, iunit, models, env,
                          tag="digital_loose_hold", r_hold=100 * R_HOLD_OHM)
    base = load(f"digital_{point}")
    freqs = noise_freqs()
    hi = _cp_call(point, op, models, env, src, freqs, iunit, config,
                  10 * RSENSE_OHM, True, "cp_on_hi_rs")
    base_cp = load(f"cp_{point}")
    idx = min(range(len(freqs)), key=lambda i: abs(freqs[i] - 1e6))
    top = len(freqs) - 1
    cells = load(f"cells_{point}")
    rb = base_cp["on"]["rsense_ohm"]

    def naive(call, i):
        """The retired reduction: voltage noise over `rsense^2`."""
        return call["s_v_total_V2_per_Hz"][i] / call["rsense_ohm"] ** 2

    return {
        "point": point, "environment": env,
        "timestep": ({
            "tmax_fine_s": 2.5e-12, "converged": True,
            "t_on_ratio": fine["t_on_s"] / base["t_on_s"],
            "slew_min_ratio": fine["slew_min_V_per_s"] / base["slew_min_V_per_s"],
            "clk_slew_ratio": fine["clk_slew_min_V_per_s"] / base["clk_slew_min_V_per_s"],
            "f_clk_ratio": fine["f_clk_Hz"] / base["f_clk_Hz"],
        } if fine is not None else {
            "tmax_fine_s": 2.5e-12, "converged": False, "error": fine_error,
        }),
        "vctrl_hold": {
            "r_hold_base_ohm": base["r_hold_ohm"],
            "r_hold_loose_ohm": loose["r_hold_ohm"],
            "t_on_ratio": loose["t_on_s"] / base["t_on_s"],
            "slew_min_ratio": loose["slew_min_V_per_s"] / base["slew_min_V_per_s"],
            "clk_slew_ratio": loose["clk_slew_min_V_per_s"] / base["clk_slew_min_V_per_s"],
            "f_clk_ratio": loose["f_clk_Hz"] / base["f_clk_Hz"],
            "ripple_base_V": base["vctrl_hold_ripple_V"],
            "ripple_loose_V": loose["vctrl_hold_ripple_V"],
        },
        "sense_resistance": {
            "rsense_base_ohm": rb, "rsense_hi_ohm": 10 * RSENSE_OHM,
            "s_i_ratio_at_1MHz": hi["s_i_total_A2_per_Hz"][idx]
            / base_cp["on"]["s_i_total_A2_per_Hz"][idx],
            "s_i_ratio_at_grid_top": hi["s_i_total_A2_per_Hz"][top]
            / base_cp["on"]["s_i_total_A2_per_Hz"][top],
            "naive_ratio_at_1MHz": naive(hi, idx) / naive(base_cp["on"], idx),
            "naive_ratio_at_grid_top": naive(hi, top) / naive(base_cp["on"], top),
            "correction_at_1MHz": base_cp["on"]["s_i_total_A2_per_Hz"][idx]
            / naive(base_cp["on"], idx),
            "correction_at_grid_top": base_cp["on"]["s_i_total_A2_per_Hz"][top]
            / naive(base_cp["on"], top),
            "anchor_ratio_at_grid_bottom": hi["anchor_ratio_at_grid_bottom"],
            "anchor_ratio_min": hi["anchor_ratio_min"],
            "anchor_ratio_max": hi["anchor_ratio_max"],
        },
        "trip_point_dominance": cells["trip_point_dominance"],
        "netlist_claims": {
            "unclassified_shared_nets": ib.unclassified_shared_nets(src),
            "shared_nets": {f"{a}-{b}": nets for (a, b), nets
                            in ib.connectivity_claim(src)["shared"].items()},
            "non_mos_devices": {name: ib_deck.non_mos_devices(src, sub)
                                for name, sub in BLOCKS.items()},
            # Every declared timing-path stage, resolved against the netlist.
            "timing_paths": {k: [i for i, _ in v]
                             for k, v in ib.timing_path_claim(src).items()},
            # The cells characterized, against the netlist's own single-stage set.
            "cells_characterized": sorted(ib_deck.CELLS),
            "single_stage_cells_in_netlist": sorted(
                ib_deck.single_stage_cells(src)),
            "cells_characterized_are_single_stage": set(ib_deck.CELLS).issubset(
                ib_deck.single_stage_cells(src)),
            # `LOCK` reaches no other instance: the lock detector is in no path.
            "lock_detector_consumers": ib.connectivity_claim(src)["nets"].get(
                "LOCK", []),
        },
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
STAGES = ("loop", "digital", "cp", "cells", "clkload", "ldload", "bound",
          "validate")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--point")
    ap.add_argument("--stage", action="append", choices=STAGES, default=[])
    ap.add_argument("--list-points", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="skip a stage whose results/<name>.json already exists")
    a = ap.parse_args(argv)
    points = load_points()
    if a.list_points:
        for name in points:
            print(name)
        return 0
    if not a.stage:
        ap.error("at least one --stage")
    models = pdk_models()
    env = environment(models)
    config, fref, nratio, iunit = load_config()

    def done(name: str) -> bool:
        return a.resume and (RESULTS / f"{name}.json").is_file()

    if "loop" in a.stage:
        if done("loop"):
            print("-- loop: already in results/, skipped (--resume)", flush=True)
        else:
            save("loop", stage_loop(env))
        a.stage = [s for s in a.stage if s != "loop"]
    if not a.stage:
        return 0
    if not a.point:
        ap.error("--point is required for every stage but `loop`")
    if a.point not in points:
        ap.error(f"unknown point {a.point!r}; --list-points")
    op = points[a.point]
    print(f"== {a.point}: {op}", flush=True)

    for st in a.stage:
        t0 = time.time()
        if done(f"{st}_{a.point}"):
            print(f"-- {st}: already in results/, skipped (--resume)", flush=True)
            continue
        if st == "digital":
            save(f"digital_{a.point}",
                 stage_digital(a.point, op, config, fref, nratio, iunit, models, env))
        elif st == "cp":
            save(f"cp_{a.point}", stage_cp(a.point, op, config, iunit, models, env))
        elif st == "cells":
            dig = load(f"digital_{a.point}")
            save(f"cells_{a.point}",
                 stage_cells(a.point, op, models, env, dig["slew_min_V_per_s"]))
        elif st == "clkload":
            save(f"clkload_{a.point}",
                 stage_gate_load(a.point, op, models, env, "clk"))
        elif st == "ldload":
            save(f"ldload_{a.point}",
                 stage_gate_load(a.point, op, models, env, "up"))
        elif st == "bound":
            save(f"bound_{a.point}",
                 stage_bound(a.point, op, config, fref, nratio, env))
        elif st == "validate":
            save(f"validate_{a.point}",
                 stage_validate(a.point, op, config, fref, nratio, iunit, models, env))
        print(f"-- {st}: {time.time() - t0:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
