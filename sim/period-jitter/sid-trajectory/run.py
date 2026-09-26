#!/usr/bin/env python3
"""gf180-pll :: period-jitter :: S_id along the trajectory -- the runner.

Builds the ISF route's SECOND and THIRD ingredients, the two
`sim/period-jitter/isf-bringup/` did not: each ring device's channel-thermal and
flicker generator PSD evaluated at the bias it actually sits at at phase `x` of
the oscillation, and the trajectory `(V_gs, V_ds, V_bs)(x)` it is evaluated
along.  See this directory's README.md, and DR-031, for what this does and does
not settle.

Stages:

  trajectory  one transient of the free-running VCO -- the ISF bring-up's own
              reference deck, one added `save` column list -- sampled into
              `(V_gs, V_ds, V_bs, I_d, g_m, g_ds)(x)` per ring device on the
              SAME phase axis the committed h(x) table uses, plus the five-stage
              symmetry residual
  sid         one standalone `.noise` deck per (device, phase), the device line
              taken verbatim from the committed netlist, biased at that phase's
              own triple -- S_id thermal and flicker, extracted two independent
              ways, with the in-situ operating point reproduced as the check that
              the bias landed on the right terminals
  checks      the extraction's own validation: the sense-resistor units anchor,
              network independence over 10^7 in sense resistance, the frequency
              dependence of both mechanisms, and the physics bracket on g_n
  cost        what a stationary single-bias S_id costs against the trajectory
              average, per device, in dB -- the bound #520's option (B) owes and
              DR-023 refused a figure without
  weighted    the same cost against the h^2-WEIGHTED average that the jitter
              integral actually contains, using the committed h table from
              ../isf-bringup/ -- exact for the two current-source devices, whose
              generators sit against an ideal rail, and a declared weight-shape
              proxy for the two switching devices.  Reference point only: it is
              the only PVT point where h was measured.

WHY THREE PVT POINTS AND NOT 45.  This directory characterises a METHOD and
reports no design number, the same standing as `../isf-bringup/` and
`../noise-toolchain-probe/`; it mints no evidence record and appears in no
coverage table.  But unlike a convergence question, the SIZE of the
cyclostationary variation is corner-dependent, so a single point could not show
that the stationary-approximation cost is a property of the ring rather than of
one operating point.  Three points -- the reference point the ISF bring-up and
the deterministic period-jitter records share, plus the slowest/coldest-supply
and fastest/hottest-supply extremes of the mandated grid, each at its own
committed release voltage -- is what answers that without paying 45x for an
ingredient that cannot yet produce a jitter number.  The mandated 45-point grid
is owed by the ASSEMBLED pipeline, on the batch fleet through `sim/harness`, and
is not discharged here.

Sequential by construction -- one ngspice process at a time.  This host is a
shared dispatch worker.

Usage:
  sim/period-jitter/sid-trajectory/run.py [--stage NAME]... [--point NAME]...
                                          [--outdir DIR] [--quick]
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import sid_deck  # noqa: E402
import sid_extract  # noqa: E402

# --- the PVT points -----------------------------------------------------------
# Every one is a point of the mandated 45-point matrix declared in
# sim/period-jitter/testbench/tb.json, released at THAT point's own 150 MHz
# control voltage from the same manifest (interpolated there from VCO record
# 20260804-162735-72883fb, band 6).  `typical/27C/3.30V` is additionally the
# point sim/period-jitter/isf-bringup/ measures h(x) at, which is why it is
# first: it is the only point where the two ingredients can currently be put on
# the same phase axis.
POINTS = {
    "typical_27c_3.30v": dict(
        vctrl=1.795, vsup=3.30, temp_c=27.0, band=(0, 1, 1),
        mos_section="typical", res_section="res_typical",
        moscap_section="moscap_typical",
    ),
    "ss_125c_2.97v": dict(
        vctrl=1.093, vsup=2.97, temp_c=125.0, band=(0, 1, 1),
        mos_section="ss", res_section="res_typical",
        moscap_section="moscap_typical",
    ),
    "ff_-40c_3.63v": dict(
        vctrl=2.430, vsup=3.63, temp_c=-40.0, band=(0, 1, 1),
        mos_section="ff", res_section="res_typical",
        moscap_section="moscap_typical",
    ),
}
#: The point the ISF bring-up's committed h(x) table is measured at.  Named
#: rather than assumed to be POINTS' first key.
REFERENCE_POINT = "typical_27c_3.30v"

# --- the transient ------------------------------------------------------------
# Identical to sim/period-jitter/isf-bringup/run.py's own constants, by
# reference rather than by coincidence: the phase convention is
# `t = T_INJECT0 + x * period` on a deck with these settings, so changing any of
# them here would move this directory's phase axis off the committed h(x)
# table's without saying so.
T_INJECT0 = 40e-9
TSTOP = 120e-9
TSTEP = 2e-12
TMAX = 2e-12
STAGES = (1, 2, 3, 4, 5)
#: The stage the per-device S_id table is built for.  Stage 1 is the stage the
#: ISF bring-up injects into, so it is the stage whose h(x) exists.
SID_STAGE = 1

# --- the phase grid -----------------------------------------------------------
# 24 phases is `isf-bringup`'s own `gamma` grid (`phase_set(24)`), so every row of
# the S_id table has an h(Y) row at exactly the same phase.  The trajectory is
# additionally sampled on a 4x finer grid, which costs nothing (it is
# interpolation of one already-computed transient) and is what an assembled
# integral would want.
N_PHASE_SID = 24
N_PHASE_TRAJ = 96

# --- the noise analysis -------------------------------------------------------
#: Frequencies the generators are reported at.  1 MHz is
#: `../noise-toolchain-probe/probe_sid_bias.sp.in`'s frequency, kept so the two
#: are comparable; the rest span 1 kHz to 300 MHz (twice the 150 MHz carrier)
#: because that is the range a period-jitter integral would draw on, and because
#: the thermal generator's whiteness and the flicker exponent are claims that
#: need a band to be claims about.
FREQS_HZ = (1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 3e8)
#: The frequency the per-phase S_id tables are tabulated at.
F_TABULATE_HZ = 1e6
#: Sense resistance of the noise deck, ohm.  `checks` measures the extracted
#: S_id's independence of it over 10^7 -- which is the point: the extraction
#: divides by a MEASURED transimpedance, so `S_id` must not depend on this value
#: at all, and the sweep is what says so rather than an argument that 1 Ohm is
#: "small".  1 mOhm rather than the 1 Ohm
#: `../noise-toolchain-probe/probe_sid_bias.sp.in` uses only because it makes the
#: `vd_offset` Newton step in `_one_noise_point` smaller, not because the answer
#: needs it.
RSENSE_OHM = 1e-3
#: Tolerance on the sense-resistor units anchor.  A run outside it is refused:
#: the deviation applies in the same proportion to every S_id read off that run.
ANCHOR_TOL = 5e-3

#: ngspice diagnostics that invalidate a run rather than annotate it.
FATAL_LOG_PATTERNS = ("Timestep too small", "simulation(s) aborted", "singular")


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


def run_deck(deck: str, work: Path, logname: str, logs: Path,
             expect_file: str | None = None, *, banner: str | None = None,
             append: bool = False) -> tuple[float, str]:
    """One ngspice process, in its own directory, with its log captured.

    Refuses on any `FATAL_LOG_PATTERNS` hit rather than letting the reduction
    complain several steps downstream -- the lesson
    `../isf-bringup/run.py::run_deck` records about `Timestep too small` leaving
    a two-row output file behind.

    `append=True` concatenates this run's output onto `logname` behind a `banner`
    line and the deck's BIAS CARDS.  The per-phase `sid` stage uses it: 24 phases
    x 4 devices x 2 passes is 192 processes per PVT point, and 192 separate files
    per point is not reviewable evidence.  One file per (point, device), holding
    every run in phase order, is.  Only the bias cards are echoed, not the whole
    deck: everything else in it is identical from block to block and is written by
    the committed `sid_deck.noise_deck`, so repeating it 48 times would be 250 kB
    per file of duplicated text, while the three source lines are exactly what
    differs and exactly what a reader checking the bias needs.
    """
    work.mkdir(parents=True, exist_ok=True)
    (work / "deck.sp").write_text(deck)
    t0 = time.time()
    proc = subprocess.run(
        ["ngspice", "-b", "deck.sp"], cwd=work, capture_output=True, text=True
    )
    elapsed = time.time() - t0
    logs.mkdir(parents=True, exist_ok=True)
    out = proc.stdout + proc.stderr
    if append:
        bias = "\n".join(
            ln for ln in deck.splitlines()
            if ln.startswith(("vg ", "vb ", "vd ", "rs ", ".temp"))
        )
        head = f"\n{'=' * 70}\n=== {banner or logname}\n{'=' * 70}\n"
        with (logs / logname).open("a") as fh:
            fh.write(head + bias + "\n--- ngspice output ---\n" + out)
    else:
        (logs / logname).write_text(out)
    hit = [p for p in FATAL_LOG_PATTERNS if p in out]
    if hit:
        raise SystemExit(
            f"ngspice reported {hit!r} for {banner or logname} -- see "
            f"logs/{logname}; the run is refused rather than reduced"
        )
    if expect_file and not (work / expect_file).is_file():
        raise SystemExit(
            f"ngspice produced no {expect_file} for {banner or logname} -- see "
            f"logs/{logname}"
        )
    return elapsed, out


def phase_set(n):
    return [i / n for i in range(n)]


# ---------------------------------------------------------------------------
# stage: trajectory
# ---------------------------------------------------------------------------
def _project_to_tabulated_stage(rows):
    """Drop the non-tabulated stages' columns from the committed trajectory rows.

    All five stages are SAMPLED -- `stage_symmetry` needs them, and its residual is
    what says whether one stage may stand in for five -- but only `SID_STAGE`'s 24
    columns are the ingredient, and carrying the other 96 would quintuple this
    file for numbers nothing downstream reads.  The symmetry residual that the
    other four stages exist to produce is reported in full.
    """
    keep = {sid_deck.op_vector(0, SID_STAGE, inst, p)
            for inst in sid_deck.RING_DEVICES for p in sid_deck.OP_VECTORS}
    return [{k: v for k, v in r.items() if not k.startswith("@m.") or k in keep}
            for r in rows]


def stage_trajectory(models, point, op, logs, work, quick):
    src = sid_deck.isf_deck.read_vco_netlist(REPO)
    tstop = 60e-9 if quick else TSTOP
    deck, cols = sid_deck.trajectory_deck(
        repo_root=REPO, pdk_models=models, tstop=tstop, tstep=TSTEP,
        tmax=TMAX, op=op, stages=STAGES, src=src,
    )
    elapsed, _ = run_deck(deck, work, f"trajectory_{point}.log", logs,
                          expect_file="clk.dat")
    t, columns = sid_extract.read_wrdata(work / "clk.dat", 1 + len(cols))
    clk = columns[0]
    opcols = columns[1:]

    # The period, measured the same way the ISF bring-up's `period` stage
    # measures it, so the two are comparable digit for digit.
    sys.path.insert(0, str(HERE.parent / "isf-bringup"))
    import isf_extract  # noqa: E402

    cross = isf_extract.crossings(t, clk, op["vsup"] / 2)
    if len(cross) < 6:
        raise SystemExit(
            f"trajectory_{point}: only {len(cross)} mid-supply crossings -- "
            "the oscillator did not start"
        )
    period = isf_extract.mean_period(cross[4:])

    ph_traj = phase_set(24 if quick else N_PHASE_TRAJ)
    ph_sid = phase_set(8 if quick else N_PHASE_SID)
    traj = sid_extract.sample_trajectory(
        t, opcols, cols, t0=T_INJECT0, period=period, phases=ph_traj
    )
    # snap=True: the S_id grid's rows must be a SOLVED timepoint, not an
    # interpolated one -- see sid_extract.sample_trajectory's docstring.
    sid_grid = sid_extract.sample_trajectory(
        t, opcols, cols, t0=T_INJECT0, period=period, phases=ph_sid, snap=True
    )
    snap_err = max(abs(r["phase_cycles_actual"] - r["phase_cycles"])
                   for r in sid_grid)
    # Both the gate bias and the drain current: `vgs` is what the standalone
    # noise deck is rebuilt from, `id` is the quantity whose PSD is tabulated, and
    # a ring that is symmetric in one and not the other would invalidate the
    # multiply-by-five step for a reason neither alone would show.
    sym = [
        sid_extract.stage_symmetry(
            t, opcols, cols, t0=T_INJECT0, period=period, phases=ph_traj,
            stages=STAGES, instance=inst, param=param,
        )
        for inst in sid_deck.RING_DEVICES
        for param in ("vgs", "id")
    ]
    return {
        "point": point,
        "operating_point": op,
        "elapsed_s": elapsed,
        "tstop_s": tstop,
        "period_s": period,
        "f0_Hz": 1.0 / period,
        "n_crossings": len(cross),
        "t_inject0_s": T_INJECT0,
        "phase_convention": "t = t_inject0 + phase_cycles * period_s "
                            "-- sim/period-jitter/isf-bringup/run.py's own",
        "columns_sampled": cols,
        "columns_reported": sorted(
            sid_deck.op_vector(0, SID_STAGE, inst, p)
            for inst in sid_deck.RING_DEVICES for p in sid_deck.OP_VECTORS
        ),
        "tabulated_stage": SID_STAGE,
        "phases_fine": ph_traj,
        "phases_sid": ph_sid,
        "sid_grid_snap_max_phase_error_cycles": snap_err,
        "trajectory": _project_to_tabulated_stage(traj),
        "trajectory_sid_grid": _project_to_tabulated_stage(sid_grid),
        "stage_symmetry": sym,
    }


# ---------------------------------------------------------------------------
# stage: sid
# ---------------------------------------------------------------------------
def _insitu(row, instance, stage=SID_STAGE):
    return {
        p: row[sid_deck.op_vector(0, stage, instance, p)]
        for p in sid_deck.OP_VECTORS
    }


def _one_noise_point(models, src, point, op, instance, bias, logs, work, tag,
                     freqs=FREQS_HZ, rsense=RSENSE_OHM, settle=True,
                     logfile=None, offsets=None):
    """One standalone-device `.noise` point, with the channel bias settled.

    TWO PASSES, and each Newton step is on an OBSERVED bias residual rather than on
    `I_d * R` -- see `sid_deck.noise_deck`'s docstring for why an `I_d * R`
    correction is applied backwards at the phases where `V_ds` changes sign (BSIM4
    swaps source and drain there and the reported current's sign stops following
    `V_ds`), and for what the residuals are residuals against.  `settle=False` runs a
    single pass with `offsets` (default none): that is all `_calibrate_r_series`
    needs -- its measurement is internally self-consistent whatever the terminals
    were set to -- and it is how the `bias_correction` check measures what an
    `I_d * R` offset would have left behind, in both signs.
    """
    if offsets is not None and settle:
        raise ValueError("`offsets` is only meaningful with settle=False")
    polarity = sid_deck.channel_polarity(src, instance)

    def _run(offsets, suffix):
        deck = sid_deck.noise_deck(
            pdk_models=models, src=src, instance=instance,
            vgs=bias["vgs"], vds=bias["vds"], vbs=bias["vbs"],
            freqs=freqs, temp_c=op["temp_c"],
            mos_section=op["mos_section"], rsense=rsense, **offsets,
        )
        _, txt = run_deck(
            deck, work, logfile or f"{tag}{suffix}.log", logs,
            banner=f"{tag}{suffix}", append=logfile is not None,
        )
        return sid_extract.parse_noise_log(txt, freqs)

    zero = offsets or {"vg_offset": 0.0, "vd_offset": 0.0, "vb_offset": 0.0}
    if settle:
        first = _run(zero, "_pass1")
        offsets = {
            f"v{t}_offset": polarity * (bias[f"v{t}s"] - first["op"][f"v{t}s"])
            for t in ("g", "d", "b")
        }
        parsed = _run(offsets, "")
        parsed["op"]["bias_offsets_V"] = offsets
    else:
        parsed = _run(zero, "")
        parsed["op"]["bias_offsets_V"] = zero
    blocks = []
    for blk in parsed["per_freq"]:
        anchor = sid_extract.units_anchor(
            blk, rsense=rsense, temp_c=op["temp_c"],
            bw=sid_deck.NOISE_BANDWIDTH_HZ,
        )
        if abs(anchor - 1.0) > ANCHOR_TOL:
            raise SystemExit(
                f"{tag} at f={blk['freq_Hz']:g} Hz: the sense resistor's own "
                f"thermal noise is {anchor:.6f} of its closed-form value -- "
                "the analysis band or the units are not what the reduction "
                "assumes, and every S_id in this run is off in the same "
                f"proportion (see logs/{tag}.log)"
            )
        rec = sid_extract.extract_sid(blk)
        rec["units_anchor"] = anchor
        blocks.append(rec)
    return parsed["op"], blocks


def _calibrate_r_series(models, src, point, op, instance, logs, work, traj):
    """`rd + rs` for one device class, measured at its peak-|I_d| phase.

    Peak current on purpose: `r_series` is recovered by dividing a voltage
    difference by `I_d`, so the phase that makes that division best-conditioned
    is the one where `I_d` is largest.
    """
    key = sid_deck.op_vector(0, SID_STAGE, instance, "id")
    row = max(traj["trajectory_sid_grid"], key=lambda r: abs(r[key]))
    bias = _insitu(row, instance)
    tag = f"rseries_{point}_{instance.lower()}"
    standalone, _ = _one_noise_point(
        models, src, point, op, instance, bias, logs, work, tag,
        freqs=(F_TABULATE_HZ,), settle=False,
    )
    r = sid_extract.series_resistance(
        standalone, polarity=sid_deck.channel_polarity(src, instance),
        rsense=RSENSE_OHM,
    )
    return {"instance": instance, "r_series_ohm": r,
            "calibrated_at_phase_cycles": row["phase_cycles"],
            "id_at_calibration_A": bias["id"]}


def stage_sid(models, point, op, logs, work, quick, traj):
    src = sid_deck.isf_deck.read_vco_netlist(REPO)
    freqs = (1e6,) if quick else FREQS_HZ
    cal = {
        inst: _calibrate_r_series(models, src, point, op, inst, logs, work, traj)
        for inst in sid_deck.RING_DEVICES
    }
    # One evidence file per (point, device), in phase order, truncated here so a
    # re-run replaces it rather than appending to the previous run's.
    for instance in sid_deck.RING_DEVICES:
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"sid_{point}_{instance.lower()}.log").write_text(
            f"* gf180-pll :: sim/period-jitter/sid-trajectory :: stage `sid`\n"
            f"* point {point}, device {instance}, stage {SID_STAGE}\n"
            f"* Every deck and every ngspice log of the per-phase S_id table,\n"
            f"* in phase order, `_pass1` being the uncorrected bias pass.\n"
        )
    rows = []
    for row in traj["trajectory_sid_grid"]:
        x = row["phase_cycles"]
        for instance in sid_deck.RING_DEVICES:
            bias = _insitu(row, instance)
            tag = f"sid_{point}_{instance.lower()}_p{round(x * 1000):04d}"
            standalone, blocks = _one_noise_point(
                models, src, point, op, instance, bias, logs, work, tag,
                freqs=freqs,
                logfile=f"sid_{point}_{instance.lower()}.log",
            )
            rows.append({
                "point": point,
                "phase_cycles": x,
                "t_s": row["t_s"],
                "instance": instance,
                "stage": SID_STAGE,
                "bias_insitu": bias,
                "reproduction": sid_extract.reproduction(bias, standalone),
                "noise": blocks,
                "physics_bracket": sid_extract.physics_bracket(
                    next(b["S_thermal_A2_per_Hz"] for b in blocks
                         if b["freq_Hz"] == (freqs[0] if quick else F_TABULATE_HZ)),
                    bias, op["temp_c"],
                ),
            })
    return {
        "point": point,
        "stage": SID_STAGE,
        "freqs_Hz": list(freqs),
        "f_tabulate_Hz": freqs[0] if quick else F_TABULATE_HZ,
        "rsense_ohm": RSENSE_OHM,
        "noise_bandwidth_Hz": sid_deck.NOISE_BANDWIDTH_HZ,
        "units_anchor_tolerance": ANCHOR_TOL,
        "series_resistance": cal,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# stage: checks
# ---------------------------------------------------------------------------
#: Sense resistances the network-independence check spans.  `S_id` is a property
#: of the device at its bias; if the extraction is right, dividing the measured
#: output noise by the measured transimpedance must give the same answer whatever
#: the network between the generator and the output node is.
RSENSE_SWEEP = (1e-3, 1.0, 1e2, 1e4)


def _pick_check_phases(traj, instance, n=4):
    """Four phases of one device's own cycle, chosen from the trajectory.

    Chosen rather than fixed, because which phase puts a given device in triode, in
    saturation or off is a property of the corner, and because the phase where the
    bias moves FASTEST -- which is where an interpolated trajectory row and a
    snapped one differ most -- is not any of the three obvious ones.

      peak_id       largest |I_d|: the best-conditioned point for anything divided
                    by the current, and the bias a "calibrate at peak current"
                    convention would pick
      median_id     the middle of the |I_d| ordering, which on this ring is a
                    deep-triode phase (V_ds of a few mV) and therefore the phase
                    where a bias offset applied in the wrong direction hurts most
      min_id        the device off
      steepest_id   largest |dI_d/dx| across the sampled grid
    """
    key = sid_deck.op_vector(0, SID_STAGE, instance, "id")
    rows = sorted(traj["trajectory_sid_grid"], key=lambda r: abs(r[key]))
    if not rows:
        raise SystemExit("no trajectory rows to pick check phases from")
    byphase = sorted(traj["trajectory_sid_grid"], key=lambda r: r["phase_cycles"])
    steep, best = byphase[0], -1.0
    for a, b in zip(byphase, byphase[1:] + byphase[:1]):
        dx = (b["phase_cycles"] - a["phase_cycles"]) % 1.0
        if dx <= 0:
            continue
        slope = abs(b[key] - a[key]) / dx
        if slope > best:
            best, steep = slope, a
    picks = [rows[-1], rows[len(rows) // 2], rows[0], steep][:n]
    labels = ("peak_id", "median_id", "min_id", "steepest_id")
    return [(r["phase_cycles"], _insitu(r, instance), lbl)
            for r, lbl in zip(picks, labels)]


def _extraction_chain_checks(models, src, point, op, logs, work, quick, traj,
                             instance, cal, out):
    """The absolute checks on the extraction chain, at one device's own phases.

    One device suffices: none of these three questions is about the device. The
    sense-resistor sweep asks whether the reduction's division by a measured
    transimpedance is right, the frequency sweep asks what the two mechanisms'
    frequency dependence is, and both are properties of the extraction and of the
    BSIM4 noise model rather than of which instance was biased.
    """
    logs.mkdir(parents=True, exist_ok=True)
    (logs / f"chk_chain_{point}.log").write_text(
        f"* gf180-pll :: sim/period-jitter/sid-trajectory :: stage `checks`\n"
        f"* point {point}, device {instance} -- the extraction-chain checks:\n"
        f"* `chk_net_*` sweeps the sense resistance over 10^7, `chk_freq_*` sweeps\n"
        f"* frequency over 1 kHz - 300 MHz.\n"
    )
    for x, bias, label in _pick_check_phases(traj, instance, n=2 if quick else 3):
        # --- network independence ---
        per_r = []
        for r in (RSENSE_SWEEP[:2] if quick else RSENSE_SWEEP):
            tag = f"chk_net_{point}_{label}_r{r:g}"
            standalone, blocks = _one_noise_point(
                models, src, point, op, instance, bias, logs, work, tag,
                freqs=(F_TABULATE_HZ,), rsense=r,
                logfile=f"chk_chain_{point}.log",
            )
            blk = blocks[0]
            per_r.append({
                "rsense_ohm": r,
                "zm_ohm": blk["zm_ohm"],
                "S_thermal_A2_per_Hz": blk["S_thermal_A2_per_Hz"],
                "S_flicker_A2_per_Hz": blk["S_flicker_A2_per_Hz"],
                "vds_standalone": standalone["vds"],
                "id_standalone": standalone["id"],
                "units_anchor": blk["units_anchor"],
            })
        base = per_r[0]["S_thermal_A2_per_Hz"]
        out["network"].append({
            "phase_cycles": x,
            "label": label,
            "bias_insitu": bias,
            "per_rsense": per_r,
            "S_thermal_span_rel": (
                max(p["S_thermal_A2_per_Hz"] for p in per_r)
                / min(p["S_thermal_A2_per_Hz"] for p in per_r) - 1.0
            ) if base > 0 else float("nan"),
        })

        # --- frequency dependence ---
        tag = f"chk_freq_{point}_{label}"
        standalone, blocks = _one_noise_point(
            models, src, point, op, instance, bias, logs, work, tag,
            freqs=FREQS_HZ, logfile=f"chk_chain_{point}.log",
        )
        freqs = [b["freq_Hz"] for b in blocks]
        th = [b["S_thermal_A2_per_Hz"] for b in blocks]
        fl = [b["S_flicker_A2_per_Hz"] for b in blocks]
        out["frequency"].append({
            "phase_cycles": x,
            "label": label,
            "bias_insitu": bias,
            "blocks": blocks,
            "thermal_whiteness": sid_extract.whiteness(freqs, th),
            "flicker_fit": sid_extract.flicker_exponent(freqs, fl),
            "inoise_vs_onoise_max_rel_diff": max(
                abs(b["S_thermal_rel_diff"]) for b in blocks
            ),
        })


def _bias_method_checks(models, src, point, op, logs, work, quick, traj, cal, out):
    """The two BIAS-method choices, measured for every device class.

    Both are decisions `sid_deck.noise_deck` and `sid_extract.sample_trajectory`
    make, and both are the kind of decision that is normally defended with an
    argument.  Here each is defended with the residual it leaves, per device class
    and per phase, so a reader can see the size of what the choice bought:

      `bias_correction`  the offsets that put the channel at the requested bias are
                         a Newton step on an OBSERVED residual.  The alternative is
                         the closed-form `I_d * (rd + rs + rsense)`, whose sign is
                         the question: BSIM4 swaps source and drain for `V_ds < 0`,
                         so the reported `I_d`'s sign stops following `V_ds` at the
                         phases where a ring device's `V_ds` crosses zero.  Both
                         signs are run.  All four classes matter because the two
                         p-type devices carry an extra polarity flip.

      `snap_vs_interp`   the `S_id` grid takes the nearest SOLVED timepoint rather
                         than interpolating the six operating-point columns to the
                         requested phase, because interpolating them independently
                         yields a row whose `I_d` is not the `I_d` of its own bias
                         triple.  The comparison runs the same noise deck on both
                         rows and reports what each row's internal inconsistency
                         costs the reproduction check -- including at the phase
                         where the bias moves fastest, which is where the two rows
                         differ most.
    """
    for instance in sid_deck.RING_DEVICES:
        polarity = sid_deck.channel_polarity(src, instance)
        r_tot = cal[instance]["r_series_ohm"] + RSENSE_OHM
        phases = _pick_check_phases(traj, instance, n=2 if quick else 4)
        logfile = f"chk_bias_{point}_{instance.lower()}.log"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / logfile).write_text(
            f"* gf180-pll :: sim/period-jitter/sid-trajectory :: stage `checks`\n"
            f"* point {point}, device {instance} -- the two bias-method checks.\n"
            f"* `_newton` is the two-pass observed-residual settle the S_id table\n"
            f"* uses; `plus_IdR`/`minus_IdR` are the closed-form alternative in both\n"
            f"* signs; `_interp` is the same phase's INTERPOLATED trajectory row.\n"
        )
        for x, bias, label in phases:
            tagbase = f"chk_{point}_{instance.lower()}_{label}"
            snapped, _ = _one_noise_point(
                models, src, point, op, instance, bias, logs, work,
                f"{tagbase}_newton", freqs=(F_TABULATE_HZ,), logfile=logfile,
            )
            snap_rep = sid_extract.reproduction(bias, snapped)

            idr = {}
            for sgn, name in ((+1.0, "plus_IdR"), (-1.0, "minus_IdR")):
                st_r, _ = _one_noise_point(
                    models, src, point, op, instance, bias, logs, work,
                    f"{tagbase}_{name}", freqs=(F_TABULATE_HZ,), settle=False,
                    logfile=logfile,
                    offsets={"vg_offset": 0.0,
                             "vd_offset": sgn * polarity * bias["id"] * r_tot,
                             "vb_offset": 0.0},
                )
                idr[name] = sid_extract.reproduction(bias, st_r)
            out["bias_correction"].append({
                "instance": instance,
                "phase_cycles": x,
                "label": label,
                "vds_insitu": bias["vds"],
                "id_insitu": bias["id"],
                "r_series_plus_rsense_ohm": r_tot,
                "newton_reproduction": snap_rep,
                "IdR_reproduction": idr,
            })

            fine = next((r for r in traj["trajectory"]
                         if abs(r["phase_cycles"] - x) < 1e-9), None)
            if fine is None:
                continue
            ibias = _insitu(fine, instance)
            st_i, _ = _one_noise_point(
                models, src, point, op, instance, ibias, logs, work,
                f"{tagbase}_interp", freqs=(F_TABULATE_HZ,), logfile=logfile,
            )
            out["snap_vs_interp"].append({
                "instance": instance,
                "phase_cycles": x,
                "label": label,
                "interpolated_bias": ibias,
                "snapped_bias": bias,
                "bias_abs_diff_V": {
                    q: ibias[q] - bias[q] for q in ("vgs", "vds", "vbs")
                },
                "id_rel_diff_between_rows": (
                    ibias["id"] / bias["id"] - 1.0 if bias["id"] else None
                ),
                "interpolated_reproduction": sid_extract.reproduction(ibias, st_i),
                "snapped_reproduction": snap_rep,
            })


def stage_checks(models, point, op, logs, work, quick, traj):
    src = sid_deck.isf_deck.read_vco_netlist(REPO)
    #: The switching nfet, which is `../noise-toolchain-probe/probe_sid_bias.sp.in`'s
    #: own device, so the extraction-chain checks are comparable with that probe's.
    chain_instance = "XMN"
    cal = {
        inst: _calibrate_r_series(models, src, point, op, inst, logs, work, traj)
        for inst in sid_deck.RING_DEVICES
    }
    out = {"point": point,
           "extraction_chain_instance": chain_instance,
           "rsense_sweep_ohm": list(RSENSE_SWEEP),
           "series_resistance": cal,
           "freqs_Hz": list(FREQS_HZ),
           "network": [], "frequency": [],
           "bias_correction": [], "snap_vs_interp": []}
    _extraction_chain_checks(models, src, point, op, logs, work, quick, traj,
                             chain_instance, cal[chain_instance], out)
    _bias_method_checks(models, src, point, op, logs, work, quick, traj, cal, out)
    return out


# ---------------------------------------------------------------------------
# stage: cost
# ---------------------------------------------------------------------------
def stage_cost(point, op, sid):
    """What a stationary single-bias S_id costs against the trajectory average."""
    f_tab = sid["f_tabulate_Hz"]
    out = {"point": point, "f_tabulate_Hz": f_tab, "devices": {}}
    for instance in sid_deck.RING_DEVICES:
        rows = [r for r in sid["rows"] if r["instance"] == instance]
        rows.sort(key=lambda r: r["phase_cycles"])
        phases = [r["phase_cycles"] for r in rows]

        def trace(gen):
            return [
                next(b[f"S_{gen}_A2_per_Hz"] for b in r["noise"]
                     if b["freq_Hz"] == f_tab)
                for r in rows
            ]

        dev = {}
        for gen in ("thermal", "flicker"):
            dens = trace(gen)
            ids = [abs(r["bias_insitu"]["id"]) for r in rows]
            i_peak = max(range(len(rows)), key=lambda k: ids[k])
            i_min = min(range(len(rows)), key=lambda k: ids[k])
            # Third convention: the bias that IS the cycle-average bias -- the
            # "average operating point" a reader would reach for first.  It is
            # not measured with its own .noise run here; the nearest sampled
            # phase to the average V_gs stands in for it, and the row says so.
            vgs = [r["bias_insitu"]["vgs"] for r in rows]
            vgs_avg = sid_extract.cycle_average(phases, vgs)
            i_avgbias = min(range(len(rows)), key=lambda k: abs(vgs[k] - vgs_avg))
            dev[gen] = sid_extract.stationary_cost(
                phases, dens,
                conventions={
                    "at_peak_Id": dens[i_peak],
                    "at_min_Id": dens[i_min],
                    "at_nearest_phase_to_mean_Vgs": dens[i_avgbias],
                },
            )
            dev[gen]["convention_phases"] = {
                "at_peak_Id": phases[i_peak],
                "at_min_Id": phases[i_min],
                "at_nearest_phase_to_mean_Vgs": phases[i_avgbias],
                "mean_Vgs_V": vgs_avg,
            }
            dev[gen]["trace"] = [
                {"phase_cycles": p, "S_A2_per_Hz": s} for p, s in zip(phases, dens)
            ]
        out["devices"][instance] = dev
    return out


# ---------------------------------------------------------------------------
# stage: weighted
# ---------------------------------------------------------------------------
#: Where each ring device's channel generator sits, and therefore which ISF
#: weights it.  A BSIM4 channel-thermal/flicker generator is a current source
#: between the device's DRAIN and SOURCE, so the ISF that weights it is
#: `h_gen = h(source) - h(drain)` (DR-030 Decision 3, and the sign convention
#: pinned in `../isf-bringup/isf_extract.node_differences`).
#:
#: For the two CURRENT-SOURCE devices that difference is EXACT and needs no
#: subtraction of two measured numbers: `XMPH`'s source is `VDD` and `XMNT`'s is
#: `VSS`, and in the ISF deck `VDD` is `vdd vdd 0 dc 'vsup'` -- an ideal voltage
#: source -- while `VSS` is node 0.  Charge injected into an ideal source does not
#: move the node, so `h(VDD) = h(VSS) = 0` identically and `|h_gen| = |h(drain)|`.
#: The committed `../isf-bringup/results/nodes.json` measures exactly `h(NH)` and
#: `h(NT)`, so these two classes' weights are available at full accuracy.
#:
#: For the two SWITCHING devices it is not: both terminals are ring nodes,
#: DR-030 measured the residue at 1.54 % of the larger term, and it rejected
#: building `h_gen` by subtraction for that reason.  The committed `diff` stage
#: measures it directly but at only six phases, which is fewer than the S_id grid
#: -- so `h(Y)` stands in as a WEIGHT SHAPE PROXY, flagged `exact=False`, and
#: every number derived from it says so.  It is not `h_gen` and this directory
#: claims no jitter contribution from it.
ISF_WEIGHT = {
    "XMPH": {"node": "NH", "exact": True,
             "why": "source is VDD, an ideal source: h(VDD) = 0, so |h_gen| = |h(NH)|"},
    "XMNT": {"node": "NT", "exact": True,
             "why": "source is VSS = node 0: h(VSS) = 0, so |h_gen| = |h(NT)|"},
    "XMP": {"node": "Y", "exact": False,
            "why": "generator is Y-NH, both ring nodes; h(Y) is a weight-SHAPE "
                   "proxy only (DR-030 Decision 3 rejects subtraction, and the "
                   "direct measurement exists at 6 phases, not 24)"},
    "XMN": {"node": "Y", "exact": False,
            "why": "generator is Y-NT, both ring nodes; h(Y) is a weight-SHAPE "
                   "proxy only (DR-030 Decision 3 rejects subtraction, and the "
                   "direct measurement exists at 6 phases, not 24)"},
}

#: The committed ISF tables this stage reads, and which node classes each holds.
ISF_RESULTS = (
    ("nodes.json", ("NH", "NT")),
    ("gamma.json", ("Y",)),
)


def _load_isf_h(stage=SID_STAGE):
    """`{node_class: (phases, h_rad_per_C)}` from the committed ISF bring-up JSON.

    Read rather than re-measured: the whole reason `sid_deck.trajectory_deck`
    delegates to `isf_deck.build_deck` is that the two tables then share one phase
    axis, and re-measuring `h` here would break that by construction.
    """
    base = HERE.parent / "isf-bringup" / "results"
    out = {}
    for fname, classes in ISF_RESULTS:
        path = base / fname
        if not path.is_file():
            raise SystemExit(f"stage weighted needs {path}")
        data = json.loads(path.read_text())
        for cls in classes:
            rows = [r for r in data["rows"]
                    if r["node"] == cls and r["stage"] == stage]
            if not rows:
                raise SystemExit(f"{path} holds no node {cls} at stage {stage}")
            rows.sort(key=lambda r: r["phase_cycles"])
            out[cls] = {
                "source": f"../isf-bringup/results/{fname}",
                "phases": [r["phase_cycles"] for r in rows],
                "h_rad_per_C": [r["h_rad_per_C"] for r in rows],
                "dq_C": sorted({r["dq_C"] for r in rows}),
                "period_s": data["period_s"],
                "f0_Hz": data["f0_Hz"],
            }
    return out


def stage_weighted(point, op, sid, traj):
    """The `h^2`-weighted stationary-approximation cost, at the reference point only.

    This is the only stage that combines this directory's ingredient with the ISF
    bring-up's, and it deliberately combines them into a RATIO rather than into the
    jitter integral.  The reason is stated in `sid_extract`'s module docstring and
    in DR-030 Decision 5: the committed `h` is measured at a 2 fC pilot charge that
    the bring-up's own linearity sweep places +10.5 % / +6.8 % from the `dq -> 0`
    limit at the switching edges, and at the ISF's zero crossings no charge in that
    sweep converges at all.  A ratio of two `h^2`-weighted averages of the SAME `h`
    table divides that bias out -- it is common to numerator and denominator -- so
    the cost figures here survive a correction to `h` that an absolute jitter
    number would not.
    """
    if point != REFERENCE_POINT:
        raise SystemExit(
            f"stage weighted is only defined at {REFERENCE_POINT}: it is the only "
            "PVT point where ../isf-bringup/ measured h"
        )
    f_tab = sid["f_tabulate_Hz"]
    hs = _load_isf_h()
    out = {
        "point": point,
        "f_tabulate_Hz": f_tab,
        "isf_period_s": hs["Y"]["period_s"],
        "trajectory_period_s": traj["period_s"],
        "period_rel_diff": hs["Y"]["period_s"] / traj["period_s"] - 1.0,
        "isf_sources": {k: v["source"] for k, v in hs.items()},
        "isf_dq_C": {k: v["dq_C"] for k, v in hs.items()},
        "weight_map": ISF_WEIGHT,
        "devices": {},
    }
    for instance, wspec in ISF_WEIGHT.items():
        rows = sorted((r for r in sid["rows"] if r["instance"] == instance),
                      key=lambda r: r["phase_cycles"])
        phases = [r["phase_cycles"] for r in rows]
        h = hs[wspec["node"]]
        dev = {"weight_node": wspec["node"], "weight_is_exact_h_gen": wspec["exact"],
               "weight_rationale": wspec["why"],
               "h_phases": h["phases"], "h_rad_per_C": h["h_rad_per_C"]}
        for gen in ("thermal", "flicker"):
            dens = [
                next(b[f"S_{gen}_A2_per_Hz"] for b in r["noise"]
                     if b["freq_Hz"] == f_tab)
                for r in rows
            ]
            ph, s_on, h_on = sid_extract.match_phase_grids(
                phases, dens, h["phases"], h["h_rad_per_C"]
            )
            ids = [abs(r["bias_insitu"]["id"]) for r in rows]
            vgs = [r["bias_insitu"]["vgs"] for r in rows]
            vgs_avg = sid_extract.cycle_average(phases, vgs)
            conv = {
                "at_peak_Id": dens[max(range(len(rows)), key=lambda k: ids[k])],
                "at_min_Id": dens[min(range(len(rows)), key=lambda k: ids[k])],
                "at_nearest_phase_to_mean_Vgs": dens[
                    min(range(len(rows)), key=lambda k: abs(vgs[k] - vgs_avg))
                ],
            }
            dev[gen] = sid_extract.isf_weighted_cost(
                ph, s_on, h_on, conventions=conv
            )
            dev[gen]["trace"] = [
                {"phase_cycles": p, "S_A2_per_Hz": s, "h_rad_per_C": hh}
                for p, s, hh in zip(ph, s_on, h_on)
            ]
        out["devices"][instance] = dev
    return out


# ---------------------------------------------------------------------------
def environment(models):
    ver = subprocess.run(["ngspice", "-v"], capture_output=True, text=True)
    return {
        "ngspice": ver.stdout.splitlines()[1].strip() if len(
            ver.stdout.splitlines()) > 1 else ver.stdout.strip(),
        "pdk_models": str(models),
        "repo_head": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "vco_netlist_sha1": subprocess.run(
            ["git", "-C", str(REPO), "hash-object",
             str(REPO / "design" / "netlist" / "vco.spice")],
            capture_output=True, text=True).stdout.strip(),
        "python": sys.version.split()[0],
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


ALL_STAGES = ("trajectory", "sid", "checks", "cost", "weighted")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", action="append", choices=ALL_STAGES,
                    help="run only these stages (default: all)")
    ap.add_argument("--point", action="append", choices=sorted(POINTS),
                    help="run only these PVT points (default: all three)")
    ap.add_argument("--outdir", default=str(HERE / "results"))
    ap.add_argument("--logdir", default=None,
                    help="where the captured ngspice output goes (default: "
                         "`logs/` beside the default --outdir, or `<outdir>/logs` "
                         "for any other --outdir)")
    ap.add_argument("--workdir", default=None,
                    help="scratch directory for decks (default: a temp dir)")
    ap.add_argument("--quick", action="store_true",
                    help="coarser phase grid, one frequency, shorter transient "
                         "-- a smoke test, not evidence")
    args = ap.parse_args(argv)

    stages = tuple(args.stage) if args.stage else ALL_STAGES
    points = tuple(args.point) if args.point else tuple(POINTS)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    # The logs follow `--outdir`, and this is not a convenience.  `logs/` here is
    # COMMITTED EVIDENCE (see this repository's `.gitignore`, which un-ignores it
    # by name), and a pinned `logs/` directory meant that
    # `run.py --quick --outdir /tmp/...` -- a smoke test, explicitly not evidence --
    # overwrote the committed full-run output of whichever point it touched, exiting
    # 0 and announcing nothing.  It did.  Only a run that writes its results to the
    # default `results/` writes to the default `logs/`.
    default_out = HERE / "results"
    if args.logdir:
        logs = Path(args.logdir)
    elif out.resolve() == default_out.resolve():
        logs = HERE / "logs"
    else:
        logs = out / "logs"
    models = pdk_models()

    import tempfile
    tmp = None
    if args.workdir:
        workroot = Path(args.workdir)
    else:
        tmp = tempfile.TemporaryDirectory(prefix="gf180-sid-")
        workroot = Path(tmp.name)

    (out / "environment.json").write_text(
        json.dumps(environment(models) | {"quick": bool(args.quick),
                                          "points": list(points),
                                          "stages": list(stages)}, indent=2) + "\n"
    )

    try:
        for point in points:
            op = POINTS[point]
            traj = None
            traj_path = out / f"trajectory_{point}.json"
            if "trajectory" in stages:
                print(f"[{point}] trajectory ...", flush=True)
                traj = stage_trajectory(
                    models, point, op, logs, workroot / point / "trajectory",
                    args.quick)
                traj_path.write_text(json.dumps(traj, indent=2) + "\n")
                print(f"[{point}]   f0 = {traj['f0_Hz'] / 1e6:.4f} MHz "
                      f"({traj['elapsed_s']:.1f} s)", flush=True)
            elif traj_path.is_file():
                traj = json.loads(traj_path.read_text())

            sid = None
            sid_path = out / f"sid_{point}.json"
            if "sid" in stages:
                if traj is None:
                    raise SystemExit(f"stage sid needs {traj_path}")
                print(f"[{point}] sid ...", flush=True)
                sid = stage_sid(models, point, op, logs,
                                workroot / point / "sid", args.quick, traj)
                sid_path.write_text(json.dumps(sid, indent=2) + "\n")
                worst = max(
                    abs(r["reproduction"]["id_rel_diff"] or 0.0) for r in sid["rows"]
                )
                print(f"[{point}]   {len(sid['rows'])} (device, phase) points, "
                      f"worst I_d reproduction {worst:.2e}", flush=True)
            elif sid_path.is_file():
                sid = json.loads(sid_path.read_text())

            if "checks" in stages:
                if traj is None:
                    raise SystemExit(f"stage checks needs {traj_path}")
                print(f"[{point}] checks ...", flush=True)
                chk = stage_checks(models, point, op, logs,
                                   workroot / point / "checks", args.quick, traj)
                (out / f"checks_{point}.json").write_text(
                    json.dumps(chk, indent=2) + "\n")

            if "cost" in stages:
                if sid is None:
                    raise SystemExit(f"stage cost needs {sid_path}")
                print(f"[{point}] cost ...", flush=True)
                cost = stage_cost(point, op, sid)
                (out / f"cost_{point}.json").write_text(
                    json.dumps(cost, indent=2) + "\n")

            if "weighted" in stages and point == REFERENCE_POINT:
                if sid is None:
                    raise SystemExit(f"stage weighted needs {sid_path}")
                if traj is None:
                    raise SystemExit(f"stage weighted needs {traj_path}")
                print(f"[{point}] weighted ...", flush=True)
                (out / f"weighted_{point}.json").write_text(
                    json.dumps(stage_weighted(point, op, sid, traj), indent=2)
                    + "\n")
            elif "weighted" in stages:
                print(f"[{point}] weighted: skipped -- h is measured only at "
                      f"{REFERENCE_POINT}", flush=True)
    finally:
        if tmp is not None:
            tmp.cleanup()

    print("done.  regenerate the summary with:\n"
          "  sim/period-jitter/sid-trajectory/summarize.py "
          "> sim/period-jitter/sid-trajectory/results/SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
