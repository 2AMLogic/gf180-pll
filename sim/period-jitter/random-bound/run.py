#!/usr/bin/env python3
"""gf180-pll :: period-jitter :: random-bound -- the runner.

Stages (see README.md for what each establishes):

  calibrate   trnoise's own PSD, measured through an RC with a closed-form
              variance, and the independence of two instances -- once
  loop        the closed-loop peaking factor over every loop the as-built
              filter admits at the ratified phase-margin floor -- once, no
              simulator
  trajectory  per point: one clean VCO, every device's operating point, and
              K_vco at the operating point
  sid         per point: every VCO device's noise densities along its
              trajectory (three rounds, down to the trajectory's own 2 ps
              resolution for switching devices), and the injection density
              that dominates all of them
  transient   per point: NCOPY noisy VCO copies plus one clean one, the period
              sequence, and its variance with a confidence limit
  validate    reference point only: does the transient converge in timestep
              and in trnoise's sample interval, and is it linear in amplitude?

Usage:
  run.py --stage calibrate
  run.py --stage loop
  run.py --point typical_27c_3.30v --stage trajectory --stage sid --stage transient
  run.py --point typical_27c_3.30v --stage validate
  run.py --list-points

One point per invocation, one ngspice process at a time within it.  The 45-point
grid is driven by `grid.sh`, which runs several invocations side by side.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import rb_deck  # noqa: E402
import rb_extract  # noqa: E402

TB_JSON = REPO / "sim" / "period-jitter" / "testbench" / "tb.json"
SUPPLY = {"low": 2.97, "nom": 3.30, "high": 3.63}
BAND = (0, 1, 1)  # B0 B1 B2 = 0 1 1: band 6, the band every 150 MHz point uses
REFERENCE_POINT = "typical_27c_3.30v"


def load_points() -> dict:
    """The 45 PVT points, from the deterministic campaign's OWN manifest.

    Each is `sim/period-jitter/testbench/tb.json`'s grid block: its MOS
    section, temperature, supply, and the control voltage that puts that
    corner's ring at 150 MHz.  Reading them rather than retyping them is what
    makes "the mandated grid" the same 45 points both halves of the Period
    jitter row are measured at.  Passives stay at `res_typical` /
    `moscap_typical`, as in that manifest (`corners: ["mos"]`).
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
        name = f"{corner}_{temp:g}c_{vsup:.2f}v"
        out[name] = dict(
            vctrl=float(vs[axis]["params"]["vstart"]), vsup=vsup,
            temp_c=float(temp), band=BAND, mos_section=corner,
            res_section="res_typical", moscap_section="moscap_typical",
        )
    if len(out) != 45:
        raise SystemExit(f"{TB_JSON}: expected 45 grid points, found {len(out)}")
    return out


# --- trajectory ----------------------------------------------------------------
T_SETTLE = 40e-9  # the ISF bring-up's measured settling, reused
TRAJ_PERIODS = 2
TRAJ_TSTEP = 2e-12
TRAJ_TMAX = 2e-12  # the ISF bring-up's converged ceiling
KVCO_DV = 0.010

# --- noise densities -----------------------------------------------------------
N_PHASE = 48
#: Frequency the flicker slope is anchored at, alongside the split frequency.
F_LO = 1e6
#: The nominal exponent (`ef` in every gf180mcu MOS card) sets WHERE the second
#: analysis frequency goes (`F = a f0 / 2`); the measured exponent is what the
#: bound then uses, re-evaluating the density at its own `F`.
ALPHA_NOMINAL = 0.95
RSENSE = 1e-3
ANCHOR_TOL = 5e-3
#: Refuse a standalone bias that does not reproduce the in-situ current to this.
REPRO_TOL = 1e-3

# --- transient -----------------------------------------------------------------
NT = 10e-12
TR_TSTEP = 10e-12
TR_TMAX = 10e-12
NCOPY = 4
N_PERIODS = 60
CONF = 0.95
MIN_DOF = 30

FATAL = ("Timestep too small", "simulation(s) aborted", "singular matrix",
         "Error:")


def pdk_models() -> Path:
    env = subprocess.run([sys.executable, str(REPO / "sim" / "run_corners.py"),
                          "--print-env"], capture_output=True, text=True,
                         check=True).stdout
    for line in env.splitlines():
        if line.startswith("export GF180_MODELS="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("could not resolve GF180_MODELS from sim/run_corners.py")


def run_deck(deck: str, work: Path, log: Path, expect: str | None = None) -> tuple[float, str]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "deck.sp").write_text(deck)
    t0 = time.time()
    proc = subprocess.run(["ngspice", "-b", "deck.sp"], cwd=work,
                          capture_output=True, text=True)
    elapsed = time.time() - t0
    out = proc.stdout + proc.stderr
    log.parent.mkdir(parents=True, exist_ok=True)
    # ngspice's batch progress meter ("Reference value : ...") is thousands of
    # characters of wall-clock noise per transient; nothing else is dropped.
    log.write_text(re.sub(r"(?: ?Reference value :\s*\S+)+", "", out))
    hit = [p for p in FATAL if p in out]
    if hit:
        raise SystemExit(f"ngspice reported {hit!r} -- see {log}; refused")
    if expect and not (work / expect).is_file():
        raise SystemExit(f"ngspice produced no {expect} -- see {log}")
    return elapsed, out


#: spec/pll.md "Period jitter": the share of the 1.0 % RMS line the supply-ripple
#: derivation leaves for the random contribution (DR-023 Decision 3).
BUDGET_PCT = 0.50


def environment(models) -> dict:
    """What produced a result: simulator, PDK, repo HEAD, host, time."""
    def sh(*cmd, cwd=None):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout.strip()
        except OSError:
            return ""
    ver = next((ln.strip("* ").split(" :")[0] for ln in
                sh("ngspice", "-v").splitlines() if "ngspice-" in ln), "")
    return {
        "ngspice": ver, "pdk_models": str(models),
        "repo_head": sh("git", "rev-parse", "--short=8", "HEAD", cwd=REPO),
        # Tracked files only: this directory's own results/ and logs/ are
        # written while the grid runs, and must not mark later points dirty.
        "repo_dirty": bool(sh("git", "status", "--porcelain", "--untracked-files=no",
                              "--", "design", "sim/period-jitter", cwd=REPO)),
        "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def seed_for(point: str, salt: str = "") -> int:
    """A fixed, per-point `rndseed`: re-running reproduces the committed sequence."""
    return int(hashlib.sha256((point + salt).encode()).hexdigest()[:7], 16)


def _save(outdir: Path, name: str, obj) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / name).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def _load(outdir: Path, name: str):
    p = outdir / name
    if not p.is_file():
        raise SystemExit(f"{p} missing -- run the stage that writes it first")
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# calibrate
# ---------------------------------------------------------------------------
CAL_R = 1.0
CAL_C = 1e-9
CAL_TSTOP = 4e-6
CAL_SKIP = 20e-9
CAL_SOURCES = (("a", 1e-3, 10e-12), ("b", 1e-3, 10e-12), ("c", 1e-3, 5e-12),
               ("d", 1e-3, 20e-12))


def stage_calibrate(outdir, logs, work):
    lines = ["* gf180-pll :: random-bound :: trnoise calibration. GENERATED."]
    for tag, na, nt in CAL_SOURCES:
        lines += [f"i{tag} 0 n{tag} trnoise({na:g} {nt:g} 0 0)",
                  f"r{tag} n{tag} 0 {CAL_R:g}", f"c{tag} n{tag} 0 {CAL_C:g}"]
    cols = " ".join(f"v(n{t})" for t, _, _ in CAL_SOURCES)
    lines += [".control", "set rndseed=1", f"tran 10p {CAL_TSTOP:g} 0 5p",
              "linearize", "set wr_singlescale", f"wrdata cal.dat {cols}",
              ".endc", ".end"]
    elapsed, _ = run_deck("\n".join(lines) + "\n", work, logs / "calibrate.log",
                          expect="cal.dat")
    t, vs = rb_extract.read_wrdata(work / "cal.dat", len(CAL_SOURCES))
    sel = [i for i, x in enumerate(t) if x >= CAL_SKIP]
    dt = t[1] - t[0]
    n_eff = rb_extract.effective_samples(len(sel), dt, CAL_R * CAL_C)

    def var(col):
        m = sum(col[i] for i in sel) / len(sel)
        return sum((col[i] - m) ** 2 for i in sel) / len(sel), m

    rows = []
    for (tag, na, nt), col in zip(CAL_SOURCES, vs):
        v, _ = var(col)
        expect = rb_extract.rc_variance_expected(2 * na * na * nt, CAL_R, CAL_C)
        rows.append({"source": tag, "NA_A": na, "NT_s": nt,
                     "S_one_sided_theory_A2_per_Hz": 2 * na * na * nt,
                     "measured_over_theory": v / expect,
                     "rel_std_error": math.sqrt(2.0 / n_eff)})
    a, b = vs[0], vs[1]
    ma = sum(a[i] for i in sel) / len(sel)
    mb = sum(b[i] for i in sel) / len(sel)
    cov = sum((a[i] - ma) * (b[i] - mb) for i in sel) / len(sel)
    corr = cov / math.sqrt(var(a)[0] * var(b)[0])
    _save(outdir, "calibrate.json", {
        "environment": environment("n/a"), "elapsed_s": elapsed, "R_ohm": CAL_R, "C_F": CAL_C, "tstop_s": CAL_TSTOP,
        "effective_independent_samples": n_eff, "sources": rows,
        "corr_a_b": corr, "corr_expected_std": 1.0 / math.sqrt(n_eff),
    })


# ---------------------------------------------------------------------------
# loop
# ---------------------------------------------------------------------------
#: spec/pll.md "Loop bandwidth", as-built filter: min ... max over 27 passive
#: bundles x 3 temperatures.  PM floor: spec/pll.md "Phase margin", the ratified
#: target (45 deg), NOT the measured worst case (47.4 deg) -- a lower floor
#: admits more loops, so the peaking found is larger, i.e. conservative.
FILTER_R = (61.6e3, 93.4e3)
FILTER_C1 = (107.1e-12, 133e-12)
FILTER_C2 = (1.81e-12, 2.22e-12)
PM_FLOOR_DEG = 45.0


ENV_F = (1.0, 1e10)
ENV_PER_DECADE = 60


def stage_loop(outdir):
    t0 = time.time()
    loops = rb_extract.admissible_loops(r_range=FILTER_R, c1_range=FILTER_C1,
                                        c2_range=FILTER_C2, pm_min_deg=PM_FLOOR_DEG)
    freqs = rb_extract.log_grid(*ENV_F, ENV_PER_DECADE)
    env = rb_extract.loop_envelope(freqs, loops)
    i_pk = max(range(len(env)), key=env.__getitem__)
    fcs = [lp["fc_Hz"] for lp in loops]
    kt = {tc: rb_extract.kt_over_c_bound(temp_c=tc, c1=FILTER_C1[1], c2=FILTER_C2[0])
          for tc in (-40.0, 27.0, 125.0)}
    _save(outdir, "loop.json", {
        "elapsed_s": time.time() - t0,
        "filter_R_ohm": FILTER_R, "filter_C1_F": FILTER_C1, "filter_C2_F": FILTER_C2,
        "pm_floor_deg": PM_FLOOR_DEG, "n_loops": len(loops),
        "fc_range_Hz": [min(fcs), max(fcs)],
        "envelope_freqs_Hz": freqs, "envelope": env,
        "peak_sq": env[i_pk], "peak_at_Hz": freqs[i_pk],
        "kt_over_c_var_V2_by_temp": kt,
        "kt_over_c_note": "C1 at its max and C2 at its min maximise C1/(C2(C1+C2))",
    })


# ---------------------------------------------------------------------------
# trajectory
# ---------------------------------------------------------------------------
def _crossing_period(t, v, level, t_start):
    c = rb_extract.rising_crossings(t, v, level)
    p = rb_extract.periods(c, t_start)
    if len(p) < 1:
        raise SystemExit("the oscillator did not complete a period after settling")
    return rb_extract.mean(p), c


def stage_trajectory(point, op, outdir, logs, work, models, quick):
    """One clean VCO, sampled on a dense phase grid; K_vco at the operating point.

    The dense rows go to the WORK directory (`traj_rows.json`), not to
    `results/`: 384 phases x 62 devices x 6 quantities is ~1.5 MB per point and
    nothing a reviewer reads.  What IS committed, by the `sid` stage, is the bias
    each device's injection density was calibrated at -- the one row per device
    #520 asks to be stated.  Re-running `sid` therefore needs `trajectory` re-run
    into the same `--work` first; `grid.sh` always runs them together.
    """
    src = rb_deck.isf_deck.read_vco_netlist(REPO)
    devs = rb_deck.devices(src)
    tstop = T_SETTLE + (TRAJ_PERIODS + 0.2) * 6.9e-9
    deck, cols = rb_deck.trajectory_deck(
        repo_root=REPO, pdk_models=models, op=op, devs=devs, tstop=tstop,
        tstep=TRAJ_TSTEP, tmax=TRAJ_TMAX, kvco_dv=KVCO_DV, src=src)
    elapsed, _ = run_deck(deck, work, logs / f"trajectory_{point}.log",
                          expect="traj.dat")
    t, data = rb_extract.read_wrdata(work / "traj.dat", len(cols))
    lvl = op["vsup"] / 2
    period, cross = _crossing_period(t, data[0], lvl, T_SETTLE)
    pp, _ = _crossing_period(t, data[1], lvl, T_SETTLE)
    pm, _ = _crossing_period(t, data[2], lvl, T_SETTLE)
    kvco = (1 / pp - 1 / pm) / (2 * KVCO_DV)
    # Phase origin: the first rising CLK crossing after settling.  Nothing here
    # shares a phase axis with another directory's table, so the origin is the
    # clock itself.
    t0 = min(c for c in cross if c >= T_SETTLE)
    n = N_DENSE_QUICK if quick else N_DENSE
    idx = {c: i for i, c in enumerate(cols)}
    rows = []
    j = 0
    for k in range(n):
        tt = t0 + (k / n) * period
        while j + 1 < len(t) and abs(t[j + 1] - tt) <= abs(t[j] - tt):
            j += 1
        # SNAP to the nearest solved timepoint: interpolating the six
        # operating-point columns independently gives a row whose I_d is not
        # the I_d of its own bias triple (../sid-trajectory/, DR-031 Decision 6).
        row = {"phase": k / n, "t_s": t[j]}
        for d in devs:
            if d["kind"] == "mos":
                row[d["path"]] = {q: data[idx[rb_deck.op_vector(0, d["path"], q)]][j]
                                  for q in rb_deck.OP_VECTORS}
            else:
                a, b = rb_deck.resistor_vectors(d)
                va = data[idx[a]][j] if a != "0" else 0.0
                vb = data[idx[b]][j] if b != "0" else 0.0
                row[d["path"]] = {"v": va - vb}
        rows.append(row)
    work.parent.mkdir(parents=True, exist_ok=True)
    (work.parent / "traj_rows.json").write_text(json.dumps(rows))
    _save(outdir, f"trajectory_{point}.json", {
        "point": point, "operating_point": op, "elapsed_s": elapsed,
        "tmax_s": TRAJ_TMAX, "period_s": period, "f0_Hz": 1 / period,
        "kvco_Hz_per_V": kvco, "kvco_dv_V": KVCO_DV, "phase_origin_s": t0,
        "n_dense": n,
        "max_snap_phase_error": max(abs((r["t_s"] - t0) / period - r["phase"])
                                    for r in rows),
    })


# ---------------------------------------------------------------------------
# sid
# ---------------------------------------------------------------------------
def _noise_eval(models, op, entries, freqs, work, log, combined=True):
    """One noise deck over `entries` (`(id, dev, bias, offsets)`) -> parsed, keyed by id."""
    deck = rb_deck.noise_deck(pdk_models=models, op=op, entries=entries,
                              freqs=freqs, rsense=RSENSE, combined=combined)
    _, out = run_deck(deck, work, log)
    mos = [i for i, d, _, _ in entries if d["kind"] == "mos"]
    res = [i for i, d, _, _ in entries if d["kind"] == "res"]
    return rb_extract.parse_noise_log(out, mos, res, freqs)


def _measure(models, op, pairs, rows, devs, freqs, work, logdir, tag, chunk=None):
    """`(device index, dense index)` pairs -> `{pair: (op record, [block per freq] | None)}`.

    Every pair is its own disjoint sub-network, so pairs at DIFFERENT phases
    share one deck exactly as devices at one phase do (`rb_deck.noise_deck`):
    a deck is a set of standalone devices, and nothing in it knows or cares
    which trajectory timepoint each one's bias came from.  `chunk` pairs per
    deck.  Two passes per deck: an operating point only, then -- after one
    Newton step on each device's observed bias residual, sign-agnostic, the
    method `../sid-trajectory/` measured and adopted (DR-031) -- the noise.
    """
    chunk = chunk or CHUNK
    out = {}
    for c0 in range(0, len(pairs), chunk):
        part = pairs[c0:c0 + chunk]
        ents = [(i, devs[j], rows[k][devs[j]["path"]], None) for i, (j, k) in enumerate(part)]
        name = f"{tag}_{c0 // chunk:03d}"
        first = _noise_eval(models, op, ents, (), work, logdir / f"{name}_pass1.log")
        ents2 = []
        for i, d, bias, _ in ents:
            off = None
            if d["kind"] == "mos":
                p = rb_deck.polarity(d)
                got = first["op"][i]
                off = {"v" + q[1]: p * (bias[q] - got[q]) for q in ("vgs", "vds", "vbs")}
            ents2.append((i, d, bias, off))
        parsed = _noise_eval(models, op, ents2, freqs, work, logdir / f"{name}.log")
        for i, pair in enumerate(part):
            out[pair] = (parsed["op"][i], parsed["per_freq"].get(i))
    return out


def resistor_flicker_card(models) -> tuple[float, float]:
    """`(KF, AF)` of `ppolyf_u_3k_body`, read from the PDK file this run uses."""
    txt = (Path(models) / "sm141064.ngspice").read_text()
    m = re.search(r"^\.model\s+ppolyf_u_3k_body\s+r\s*\n((?:\+.*\n)+)", txt, re.M)
    if not m:
        raise SystemExit("PDK: no `.model ppolyf_u_3k_body r` card")
    kv = dict(re.findall(r"\+\s*(\w+)\s*=\s*([-+0-9.eE]+)", m.group(1)))
    return float(kv["kf"]), float(kv["af"])


#: The dense trajectory grid.  3072 steps is 2.17 ps at 150 MHz -- the
#: trajectory's own 2 ps timestep ceiling, so the grid is as fine as the
#: waveform the densities are evaluated along; nothing finer exists.
N_DENSE = 3072
N_DENSE_QUICK = 384
#: Round B: every switching (ring and output-buffer) device on this many
#: phases -- 17 ps at 150 MHz.
N_PHASE_SWITCHING = 384
#: Round C: around this many of each switching device's largest round-B local
#: maxima, every dense step between the neighbouring round-B samples.
N_PEAKS = 3
#: Sub-networks per noise deck.  The cost per sub-network grows with the deck
#: (measured on this build: 21, 23, 33, 61 and ~150 ms at 40, 80, 150, 300 and
#: 600), and a 600-sub-network deck holds ~0.7 GB, enough for ngspice's own
#: available-memory check to refuse the noise output when many points run side
#: by side -- which it does loudly ("memory required ... is more than memory
#: available", caught by FATAL), not silently.
CHUNK = 80


def _local_maxima(ks, val, n):
    """Indices in the (circular, sorted) grid `ks` whose value is >= both neighbours."""
    out = []
    for i, k in enumerate(ks):
        a, b = ks[i - 1], ks[(i + 1) % len(ks)]
        if val[k] >= val[a] and val[k] >= val[b]:
            out.append(k)
    return sorted(out, key=lambda k: -val[k])


def stage_sid(point, op, outdir, logs, work, models, quick):
    """Every VCO device's noise densities along its trajectory, and the injection density.

    Three rounds, each one noise deck (or a few) of many disjoint sub-networks:

      A. every device, at `N_PHASE` phases;
      B. every switching device (ring and output buffer), at `N_PHASE_SWITCHING`
         phases -- 17 ps;
      C. every switching device, at every dense step (2.17 ps, the trajectory's
         own resolution) between the round-B neighbours of each of its
         `N_PEAKS` largest round-B local maxima.

    The injection density is the maximum over all three.  C over B, per device,
    is reported as the maximum's convergence against sampling resolution.  The
    bias generator's devices are quasi-DC and are sampled in round A only; the
    injection density given them is their round-A maximum RAISED by their own
    round-A span (max/min), a margin that covers any excursion between samples
    no larger than the excursion the samples themselves show.
    """
    src = rb_deck.isf_deck.read_vco_netlist(REPO)
    devs = rb_deck.devices(src)
    traj = _load(outdir, f"trajectory_{point}.json")
    rows_path = work.parent / "traj_rows.json"
    if not rows_path.is_file():
        raise SystemExit(f"{rows_path} missing -- run `trajectory` with the same --work")
    rows = json.loads(rows_path.read_text())
    n = len(rows)
    loop = _load(outdir, "loop.json")
    f0 = traj["f0_Hz"]
    t_w = (1.0 + rb_extract.WINDOW_MARGIN) / f0
    f_star = rb_extract.flicker_corner_frequency(ALPHA_NOMINAL, f0)
    freqs = (F_LO, f_star)
    tk = rb_extract.kelvin(op["temp_c"])
    kf, af = resistor_flicker_card(models)
    phi_cache = {}

    def phi(alpha):
        key = round(alpha, 4)
        if key not in phi_cache:
            phi_cache[key] = rb_extract.flicker_factor(
                alpha, f_star, t_w, loop["envelope_freqs_Hz"], loop["envelope"])
        return phi_cache[key]

    # Per-deck logs are large and there are several per point, so they go to
    # the WORK area; the committed JSON carries every check made on them
    # (units anchor, bias reproduction) and, per device, the bias its
    # injection density was calibrated at.
    plog = work.parent / "sid_logs"
    plog.mkdir(parents=True, exist_ok=True)
    per_dev = {d["path"]: {} for d in devs}  # dense index -> record
    anchors, repro = [], []

    def record(j, k, got, blks):
        d = devs[j]
        ins = rows[k][d["path"]]
        if d["kind"] == "res":
            i = got["i"]
            r = abs(ins["v"] / i) if i else float("inf")
            s_th = 4 * rb_extract.K_B * tk / r
            # Flicker from the card's own KF/AF in ngspice's resistor form
            # KF |I|^AF / f (EF = 1), on all three segments (body + two
            # terminals) -- which `.noise` cannot report for the body.
            s_fl = 3 * kf * abs(i) ** af / f_star
            return {"phase": rows[k]["phase"], "R_ohm": r, "I_A": i, "S_white": s_th,
                    "S_flicker_F": s_fl, "alpha": 1.0, "phi": phi(1.0),
                    "S_equiv": s_th + phi(1.0) * s_fl}
        if abs(ins["id"]) > 1e-9:
            repro.append(abs(abs(got["id"]) / abs(ins["id"]) - 1.0))
        blk_lo, blk_hi = blks
        for blk in (blk_lo, blk_hi):
            an = rb_extract.units_anchor(blk, rsense=RSENSE, temp_c=op["temp_c"])
            anchors.append(an)
            if abs(an - 1) > ANCHOR_TOL:
                raise SystemExit(f"{point} {d['path']} @ {k}: units anchor {an:.6f}")
        lo = rb_extract.densities(blk_lo)
        hi = rb_extract.densities(blk_hi)
        if hi["flicker"] > 0 and lo["flicker"] > 0:
            alpha = rb_extract.flicker_exponent(F_LO, lo["flicker"], f_star, hi["flicker"])
            if not 0 < alpha < 5:
                raise SystemExit(f"{point} {d['path']} @ {k}: flicker exponent {alpha}")
            ph = phi(alpha)
        else:
            alpha, ph = None, 0.0
        return {"phase": rows[k]["phase"],
                "bias": {q: ins[q] for q in ("vgs", "vds", "vbs", "id")},
                "S_white": hi["white"], "S_channel_thermal": hi["channel_thermal"],
                "S_flicker_F": hi["flicker"], "alpha": alpha, "phi": ph,
                "S_equiv": hi["white"] + ph * hi["flicker"]}

    def run_round(pairs, tag):
        todo = [(j, k) for j, k in pairs if k not in per_dev[devs[j]["path"]]]
        got = _measure(models, op, todo, rows, devs, freqs, work, plog, tag,
                       chunk=CHUNK)
        for (j, k), (o, blks) in got.items():
            per_dev[devs[j]["path"]][k] = record(j, k, o, blks)
        return len(todo)

    everyone = list(range(len(devs)))
    switching = [j for j, d in enumerate(devs) if d["block"] in ("ring", "buffer")]
    round_a = list(range(0, n, n // (8 if quick else N_PHASE)))
    round_b = list(range(0, n, n // (48 if quick else N_PHASE_SWITCHING)))
    stride_b = round_b[1] - round_b[0]
    n_a = run_round([(j, k) for k in round_a for j in everyone], "A")
    n_b = run_round([(j, k) for k in round_b for j in switching], "B")
    pairs_c = []
    peaks = {}
    for j in switching:
        val = {k: per_dev[devs[j]["path"]][k]["S_equiv"] for k in round_b}
        top = _local_maxima(round_b, val, n)[:N_PEAKS]
        peaks[devs[j]["path"]] = [rows[k]["phase"] for k in top]
        for k0 in top:
            pairs_c += [(j, (k0 + m) % n) for m in range(-(stride_b - 1), stride_b)]
    n_c = run_round(pairs_c, "C")

    def vmax(path, ks):
        recs = per_dev[path]
        return max(recs[k]["S_equiv"] for k in ks if k in recs)

    out = {}
    for d in devs:
        p = d["path"]
        recs = per_dev[p]
        k0 = max(recs, key=lambda k: recs[k]["S_equiv"])
        ra = [recs[k]["S_equiv"] for k in round_a]
        span = max(ra) / min(ra) if min(ra) > 0 else float("inf")
        rec = {
            "block": d["block"], "instance": d["instance"], "kind": d["kind"],
            "model": d["model"], "argmax_phase": recs[k0]["phase"],
            "at_argmax": recs[k0], "S_equiv_max": recs[k0]["S_equiv"],
            "n_phases": len(recs),
            "max_round_a": max(ra),
            "round_a_span_dB": 10 * math.log10(span) if math.isfinite(span) else None,
            "round_a_S_equiv": [float(f"{v:.4g}") for v in ra],
        }
        if d["block"] in ("ring", "buffer"):
            mb = vmax(p, round_b)
            rec.update({"max_round_b": mb, "peaks_round_b": peaks[p],
                        "gain_c_over_b": recs[k0]["S_equiv"] / mb if mb > 0 else 1.0,
                        "gain_b_over_a": mb / max(ra) if max(ra) > 0 else 1.0,
                        "margin_factor": 1.0})
        else:
            rec["margin_factor"] = span if math.isfinite(span) else 1.0
        out[p] = rec
    # The injection density.  Ring: the maximum over the class across all five
    # stages, so every stage's generator is dominated by one density.  Bias
    # generator: its maximum times its margin.
    def pool(d):
        if d["block"] == "ring":
            return [e["path"] for e in devs
                    if e["block"] == "ring" and e["instance"] == d["instance"]]
        return [d["path"]]

    inj, inj_white = {}, {}
    for d in devs:
        pl = pool(d)
        inj[d["path"]] = max(out[q]["S_equiv_max"] * out[q]["margin_factor"] for q in pl)
        inj_white[d["path"]] = max(r["S_white"] * out[q]["margin_factor"]
                                   for q in pl for r in per_dev[q].values())
    worst_repro = max(repro) if repro else 0.0
    if worst_repro > REPRO_TOL:
        raise SystemExit(f"{point}: standalone bias reproduces I_d only to {worst_repro:.2e}")
    _save(outdir, f"sid_{point}.json", {
        "point": point, "f0_Hz": f0, "freqs_Hz": list(freqs), "F_Hz": f_star,
        "window_margin": rb_extract.WINDOW_MARGIN, "t_window_s": t_w,
        "rsense_ohm": RSENSE, "units_anchor_range": [min(anchors), max(anchors)],
        "n_units_anchor_checks": len(anchors),
        "repro_worst_id_rel": worst_repro, "resistor_kf_af": [kf, af],
        "phi": [{"alpha": a_, "phi": v} for a_, v in sorted(phi_cache.items())],
        "n_dense": n, "round_a_phases": [rows[k]["phase"] for k in round_a],
        "n_evaluated": {"A": n_a, "B": n_b, "C": n_c},
        "devices": out,
        "S_inj_A2_per_Hz": inj, "S_inj_white_only_A2_per_Hz": inj_white,
    })


# ---------------------------------------------------------------------------
# transient
# ---------------------------------------------------------------------------
def _amps(inj: dict, scale: float, nt: float) -> dict:
    return {k: scale * rb_deck.trnoise_amplitude(v, nt) for k, v in inj.items()}


def _run_transient(point, op, models, work, log, variants, rndseed, n_periods, tmax):
    src = rb_deck.isf_deck.read_vco_netlist(REPO)
    tstop = T_SETTLE + (n_periods + 1.5) * 6.9e-9
    deck, copies = rb_deck.transient_deck(
        repo_root=REPO, pdk_models=models, op=op, variants=variants, tstop=tstop,
        tstep=TR_TSTEP, tmax=tmax, rndseed=rndseed, src=src)
    elapsed, _ = run_deck(deck, work, log, expect="clk.dat")
    t, cols = rb_extract.read_wrdata(work / "clk.dat", len(copies))
    for c, v in zip(copies, cols):
        cr = rb_extract.rising_crossings(t, v, op["vsup"] / 2)
        c["periods_s"] = rb_extract.periods(cr, T_SETTLE)[:n_periods]
    return elapsed, copies, tstop


def _summarise(copies, variant, quick=False):
    groups = [c["periods_s"] for c in copies if c["variant"] == variant]
    var, dof, n = rb_extract.pooled_variance(groups)
    if dof < (2 if quick else MIN_DOF):
        raise SystemExit(f"only {dof} degrees of freedom for {variant}")
    m = rb_extract.mean([x for g in groups for x in g])
    return {"n_periods": n, "dof": dof, "mean_period_s": m,
            "sigma_s": math.sqrt(var), "sigma_pct": 100 * math.sqrt(var) / m,
            "sigma_upper_s": rb_extract.sigma_upper(var, dof, CONF),
            "sigma_upper_pct": 100 * rb_extract.sigma_upper(var, dof, CONF) / m,
            "lag1_autocorrelation": rb_extract.lag1_autocorrelation(groups)}


def stage_transient(point, op, outdir, logs, work, models, quick):
    sid = _load(outdir, f"sid_{point}.json")
    n_per = 12 if quick else N_PERIODS
    ncopy = 2 if quick else NCOPY
    variants = [("", _amps(sid["S_inj_A2_per_Hz"], 1.0, NT), NT, ncopy)]
    elapsed, copies, tstop = _run_transient(
        point, op, models, work, logs / f"transient_{point}.log", variants,
        seed_for(point), n_per, TR_TMAX)
    clean = [c["periods_s"] for c in copies if c["variant"] == "clean"]
    cv, cdof, _ = rb_extract.pooled_variance(clean)
    noisy = _summarise(copies, "", quick)
    traj = _load(outdir, f"trajectory_{point}.json")
    loop = _load(outdir, "loop.json")
    t_w = (1.0 + rb_extract.WINDOW_MARGIN) / traj["f0_Hz"]
    wf = rb_extract.white_loop_factor(loop["envelope_freqs_Hz"], loop["envelope"], t_w)
    ktc = rb_extract.kt_over_c_bound(temp_c=op["temp_c"], c1=FILTER_C1[1], c2=FILTER_C2[0])
    bound = rb_extract.assemble_bound(
        sigma_upper_s=noisy["sigma_upper_s"], mean_period_s=noisy["mean_period_s"],
        white_factor=wf, peak_sq=loop["peak_sq"], kt_over_c_v2=ktc,
        kvco_hz_per_v=traj["kvco_Hz_per_V"], f0_hz=traj["f0_Hz"])
    _save(outdir, f"transient_{point}.json", {
        "point": point, "operating_point": op, "environment": environment(models),
        "elapsed_s": elapsed, "tstop_s": tstop, "tmax_s": TR_TMAX, "nt_s": NT,
        "rndseed": seed_for(point), "confidence": CONF,
        "noisy": noisy,
        "floor": {"sigma_s": math.sqrt(cv), "n_periods": cdof + 1},
        "white_loop_factor": wf, "loop_peak_sq": loop["peak_sq"],
        "kt_over_c_V2": ktc, "kvco_Hz_per_V": traj["kvco_Hz_per_V"],
        "bound": bound, "budget_pct": BUDGET_PCT,
        "copies": copies,
    })


# ---------------------------------------------------------------------------
# validate (reference point)
# ---------------------------------------------------------------------------
VAL_PERIODS = 60
VAL_NCOPY = NCOPY
VAL_SCALE = 3.0
VAL_TMAX_FINE = 2.5e-12


def _ratio(num: dict, den: dict) -> dict:
    """`sigma_num / sigma_den` with its standard error, for two independent estimates.

    The relative standard error of a sample standard deviation with `dof`
    degrees of freedom is ~`1/sqrt(2 dof)`; for a ratio of two independent ones
    the relative errors add in quadrature.
    """
    r = num["sigma_s"] / den["sigma_s"]
    rel = math.sqrt(1.0 / (2 * num["dof"]) + 1.0 / (2 * den["dof"]))
    return {"ratio": r, "se": r * rel}


def _compare_noise_forms(point, op, sid, devs, models, work, logdir):
    """Does the one-`.noise`-per-frequency deck report what per-device `.noise` does?

    `sid` runs the summed form (`rb_deck.noise_deck(combined=True)`) over decks
    that batch many phases, because it is orders of magnitude cheaper.  This
    compares it, at the phase that set the largest ring injection density
    (where the switching devices are strongly on), against the per-device form
    on a deck holding that phase alone, and returns the largest relative
    difference of every quantity the reduction reads.  Zero is the expected
    answer: the sub-networks are disjoint, so the sum node sees each device
    through its own drain only, and a second phase's sub-networks are simply
    more disjoint sub-networks.
    """
    rows = json.loads((work.parent.parent / "traj_rows.json").read_text())
    n = len(rows)
    ring = [(p, v) for p, v in sid["devices"].items() if v["block"] == "ring"]
    top_path, top = max(ring, key=lambda kv: kv[1]["S_equiv_max"])
    k = round(top["argmax_phase"] * n) % n
    k2 = (k + n // 2) % n
    freqs = tuple(sid["freqs_Hz"])
    nd = len(devs)
    # Form 1, as `sid` runs it: one summed `.noise` per frequency over a deck
    # that holds every device at TWO phases (2 x 65 sub-networks).
    batch = ([(j, d, rows[k][d["path"]], None) for j, d in enumerate(devs)]
             + [(nd + j, d, rows[k2][d["path"]], None) for j, d in enumerate(devs)])
    got_b = _noise_eval(models, op, batch, freqs, work, logdir / "batched_summed.log")
    # Form 2: one phase, one `.noise` per device per frequency.
    single = [(j, d, rows[k][d["path"]], None) for j, d in enumerate(devs)]
    got_s = _noise_eval(models, op, single, freqs, work, logdir / "per_device.log",
                        combined=False)
    worst = {}
    for j, d in enumerate(devs):
        if d["kind"] != "mos":
            continue
        for a_, b_ in zip(got_b["per_freq"][j], got_s["per_freq"][j]):
            for key in ("zm_ohm", "on_total", "on_flicker", "on_thermal", "on_rsense"):
                if b_[key]:
                    worst[key] = max(worst.get(key, 0.0), abs(a_[key] / b_[key] - 1.0))
    return {"phase_index": k, "phase": rows[k]["phase"], "selected_by": top_path,
            "max_rel_diff": worst}


def stage_validate(point, op, outdir, logs, work, models, quick):
    """Is the transient a measurement of what it claims to measure?

    Every comparison is STATISTICAL: each variant is its own deck -- one clean
    copy and `VAL_NCOPY` noisy ones, the transient stage's own shape -- and its
    pooled period deviation is compared with the transient stage's result at
    this point (`base`), as a ratio with a standard error.  (A period-by-period
    comparison on one shared noise realisation is not available: on this build
    a `trnoise` realisation is not reproduced by fixing the seed -- `repeat`,
    the transient stage's deck run again unchanged, is the evidence, and is
    also a second independent estimate of `base`.)  The variants:

      repeat     the transient stage's deck, unchanged           -> 1
      fine_tmax  timestep ceiling 2.5 ps instead of 10 ps          -> 1 (converged)
      nt5, nt20  trnoise sample interval 5 / 20 ps, same PSD       -> 1 (white)
      x3         every amplitude x3                                -> 3 (linear)
      white      flicker parts removed                             -> share
      ring, bias, buffer   one block's generators alone          -> shares, summing to 1

    The decks are independent, so they run side by side.  And the noise deck's
    summed, multi-phase form is compared with the per-device form
    (`_compare_noise_forms`).
    """
    from concurrent.futures import ThreadPoolExecutor

    src = rb_deck.isf_deck.read_vco_netlist(REPO)
    devs = rb_deck.devices(src)
    sid = _load(outdir, f"sid_{point}.json")
    base = _load(outdir, f"transient_{point}.json")
    inj = sid["S_inj_A2_per_Hz"]
    n_per = 12 if quick else VAL_PERIODS
    ncopy = 2 if quick else VAL_NCOPY
    plan = {
        "repeat": (inj, 1.0, NT, TR_TMAX, seed_for(point)),
        "fine_tmax": (inj, 1.0, NT, VAL_TMAX_FINE, seed_for(point, "fine_tmax")),
        "nt5": (inj, 1.0, 5e-12, TR_TMAX, seed_for(point, "nt5")),
        "nt20": (inj, 1.0, 20e-12, TR_TMAX, seed_for(point, "nt20")),
        "x3": (inj, VAL_SCALE, NT, TR_TMAX, seed_for(point, "x3")),
        "white": (sid["S_inj_white_only_A2_per_Hz"], 1.0, NT, TR_TMAX, seed_for(point, "white")),
        "ring": (_only(inj, devs, "ring"), 1.0, NT, TR_TMAX, seed_for(point, "ring")),
        "bias": (_only(inj, devs, "bias"), 1.0, NT, TR_TMAX, seed_for(point, "bias")),
        "buffer": (_only(inj, devs, "buffer"), 1.0, NT, TR_TMAX, seed_for(point, "buffer")),
    }

    def one(name):
        amps, scale, nt, tmax, seed = plan[name]
        el, copies, _ = _run_transient(
            point, op, models, work / name, logs / f"validate_{name}_{point}.log",
            [("", _amps(amps, scale, nt), nt, ncopy)], seed, n_per, tmax)
        return name, {"elapsed_s": el, "copies": copies, "tmax_s": tmax, "nt_s": nt,
                      "scale": scale, "rndseed": seed,
                      "summary": _summarise(copies, "", quick)}

    with ThreadPoolExecutor(max_workers=len(plan)) as ex:
        runs = dict(ex.map(one, plan))
    ratios = {k: _ratio(v["summary"], base["noisy"]) for k, v in runs.items()}
    shares = {k: ratios[k]["ratio"] ** 2 for k in ("ring", "bias", "buffer", "white")}
    # Same seed, same deck: if `set rndseed` reproduced a realisation, the
    # repeat's period sequence would equal the transient stage's bit for bit.
    rep = [rb_extract.pairwise_deviation_ratio(ca["periods_s"], cb["periods_s"])
           for ca, cb in zip(base["copies"], runs["repeat"]["copies"])
           if ca["variant"] != "clean"]
    forms = _compare_noise_forms(point, op, sid, devs, models, work / "forms",
                                 logs / f"validate_noise_forms_{point}")
    _save(outdir, f"validate_{point}.json", {
        "point": point, "environment": environment(models),
        "base": {k: base["noisy"][k] for k in ("sigma_s", "dof", "n_periods")},
        "runs": runs, "ratios": ratios,
        "block_shares_of_variance": shares,
        "block_shares_sum": shares["ring"] + shares["bias"] + shares["buffer"],
        "repeat_vs_transient_same_seed": rep,
        "noise_deck_forms": forms,
    })


ALL = ("calibrate", "loop", "trajectory", "sid", "transient", "validate")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", action="append", choices=ALL)
    ap.add_argument("--point", default=REFERENCE_POINT)
    ap.add_argument("--outdir", default=str(HERE / "results"))
    ap.add_argument("--logs", default=None,
                    help="default: <outdir>/../logs (committed evidence -- a "
                         "scratch --outdir gets scratch logs)")
    ap.add_argument("--work", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--list-points", action="store_true")
    a = ap.parse_args(argv)
    points = load_points()
    if a.list_points:
        print("\n".join(points))
        return 0
    if a.point not in points:
        raise SystemExit(f"unknown point {a.point!r}; see --list-points")
    op = points[a.point]
    outdir = Path(a.outdir)
    logs = Path(a.logs) if a.logs else outdir.parent / "logs"
    work = Path(a.work) if a.work else Path("/tmp") / f"rb_work_{a.point}"
    models = pdk_models()
    for st in a.stage or ():
        t0 = time.time()
        if st == "calibrate":
            stage_calibrate(outdir, logs, work / "cal")
        elif st == "loop":
            stage_loop(outdir)
        else:
            fn = {"trajectory": stage_trajectory, "sid": stage_sid,
                  "transient": stage_transient, "validate": stage_validate}[st]
            fn(a.point, op, outdir, logs, work / st, models, a.quick)
        print(f"{a.point} {st}: {time.time() - t0:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
