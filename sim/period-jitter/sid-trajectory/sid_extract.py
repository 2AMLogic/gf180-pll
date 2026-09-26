"""gf180-pll :: period-jitter :: S_id along the trajectory -- the reduction.

Turns the two decks `sid_deck.py` writes into the second and third ingredients
of the ISF route's jitter sum:

    var(dT) over one period = (1 / w0^2) * (1/2) * integral_0^T h(t)^2 S_i(t) dt

`sim/period-jitter/isf-bringup/` measures `h`.  This module produces `S_i(t)` --
each ring device's channel-thermal and flicker generator PSD, in A^2/Hz,
evaluated at the bias that device actually sits at at phase `x` of the
oscillation -- and the trajectory `(V_gs, V_ds, V_bs)(x)` it is evaluated along.

FOUR THINGS ARE DELIBERATELY NOT DONE HERE.

  * The integral is not evaluated.  Assembling `h` and `S_i` into a jitter
    number needs `h_gen(x)` at more than the six phases the ISF bring-up's deck
    capacity afforded, needs `h` at the ISF's zero crossings extrapolated to
    `dq -> 0` (DR-030 Decision 3), and needs the bias generator's own injection
    either measured or declared.  A number computed without those would be a
    lower bound presented as a result.
  * The flicker term is not integrated over any bandwidth.  It is reported as a
    density at each measured frequency plus a measured exponent, because a
    period-jitter RMS from a 1/f^alpha generator is not defined until an
    observation interval is, and `spec/pll.md`'s Period jitter row does not
    state one.  See `flicker_exponent`.
  * No stationary single-bias `S_id` is blessed.  `stationary_cost` reports what
    three different single-bias conventions cost against the trajectory average,
    and `isf_weighted_cost` reports the same against the `h^2`-weighted average
    that the jitter integral actually contains, precisely so that the choice is
    visible as a choice.  Neither function picks one.
  * Nothing is averaged across PVT points.  Each point stands alone.

THE UNITS TRAP THIS MODULE EXISTS TO CATCH.  ngspice's `noise2`-style integrated
plot holds noise integrated over the analysis band, in V RMS (not V^2).  With a
1 Hz band the number IS the density -- and a band that is accidentally wider
scales every mechanism, including a resistor's, by `sqrt(bandwidth)`.  So
`units_anchor` re-derives the sense resistor's own thermal noise from
`sqrt(4 k T R * bw) * Z_m / R` on every single `.noise` call and the runner
refuses the point if it disagrees.  During this bring-up that check fired: an
upper band edge written `f * (1 + 1e-7) + 1` instead of `f + 1` made the channel
generator appear to rise 3.3x between 1 kHz and 100 MHz, which reads exactly like
a real high-frequency excess and is not one.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

#: Boltzmann constant, J/K -- CODATA 2019 exact value.
K_B = 1.380649e-23
#: 0 degC in kelvin.
T0_K = 273.15
#: Elementary charge, C -- CODATA 2019 exact value.  Used only by
#: `shot_conductance`, the subthreshold arm of the physics bracket.
Q_E = 1.602176634e-19


def kelvin(temp_c: float) -> float:
    return temp_c + T0_K


# ---------------------------------------------------------------------------
# the trajectory deck
# ---------------------------------------------------------------------------
def read_wrdata(path, ncol: int):
    """ngspice `wrdata` + `set wr_singlescale` output -> `(t, [col, ...])`.

    Same shape as `isf_extract.read_wrdata`, kept separate only because this
    directory's column count is set by `sid_deck.trajectory_vectors` rather than
    by a copy count.
    """
    t: list[float] = []
    cols: list[list[float]] = [[] for _ in range(ncol)]
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) != ncol + 1:
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue
        t.append(vals[0])
        for i in range(ncol):
            cols[i].append(vals[i + 1])
    if not t:
        raise ValueError(f"{path}: no data rows with {ncol + 1} columns")
    return t, cols


def interp_at(t, y, t_target: float) -> float:
    """Linear interpolation of `y(t)` at `t_target`, with both ends clamped.

    Linear, not spline, on purpose: the transient is written on a 2 ps grid
    against a 6.67 ns period, so a phase sample is ~0.03 % of a cycle away from
    a stored point, and a higher-order interpolant would be fitting the
    integrator's own local error.
    """
    if t_target <= t[0]:
        return y[0]
    if t_target >= t[-1]:
        return y[-1]
    lo, hi = 0, len(t) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if t[mid] <= t_target:
            lo = mid
        else:
            hi = mid
    span = t[hi] - t[lo]
    if span <= 0:
        return y[lo]
    w = (t_target - t[lo]) / span
    return y[lo] * (1.0 - w) + y[hi] * w


def nearest_index(t, t_target: float) -> int:
    """Index of the stored timepoint closest to `t_target`."""
    lo, hi = 0, len(t) - 1
    if t_target <= t[0]:
        return 0
    if t_target >= t[-1]:
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if t[mid] <= t_target:
            lo = mid
        else:
            hi = mid
    return lo if (t_target - t[lo]) <= (t[hi] - t_target) else hi


def sample_trajectory(t, cols, column_names, *, t0: float, period: float, phases,
                      snap: bool = False):
    """The bias trajectory on a phase grid, in the ISF bring-up's phase convention.

    `phase = x` means `t = t0 + x * period`, which is
    `sim/period-jitter/isf-bringup/run.py`'s `T_INJECT0 + ph * period` -- the SAME
    absolute-time convention the committed `h(x)` table uses.  Nothing here
    re-derives the phase origin from a threshold crossing, precisely so the two
    tables cannot drift apart: whatever `t0` the ISF bring-up injected at is the
    `t0` this trajectory is sampled at.

    `snap=False` interpolates every column linearly to the requested phase, which
    is what a trace wants.  `snap=True` instead returns the NEAREST STORED
    TIMEPOINT's values, unmodified, which is what the `S_id` grid wants, and the
    difference is not cosmetic: `I_d`, `g_m` and `g_ds` are nonlinear functions of
    `(V_gs, V_ds, V_bs)`, so interpolating all six columns independently yields a
    row whose current is NOT the current of its own bias triple.  The standalone
    `.noise` deck is built from the triple and then checked against the current,
    so an interpolated row makes that check fail by the interpolation error instead
    of by anything about the probe.

    The size of that is MEASURED rather than argued, by `run.py`'s `checks` stage
    (`snap_vs_interp`, which runs the same noise deck on both rows at four phases of
    every device class) -- and the measurement is also the reason the check needed a
    fourth phase.  At the peak-, median- and minimum-`I_d` phases the two rows are
    indistinguishable: both reproduce to ~1e-6, because over one 2 ps stored step
    the bias barely moves and linear interpolation error is second order.  At the
    phase where `I_d` moves FASTEST the interpolated row reproduces to 8.2e-5 while
    the snapped row reproduces to 6.0e-7 -- 140x worse, and that ratio, not the
    absolute size, is what says the choice is real.  Snapping costs at most half a
    stored timestep of phase error -- 1 ps against a 6.67 ns period, 1.5e-4 of a
    cycle -- and is reported as `phase_cycles_actual`.

    Returns `[{"phase_cycles": x, "phase_cycles_actual": x', "t_s": t,
    "<column>": value, ...}, ...]`.
    """
    rows = []
    for x in phases:
        tt = t0 + x * period
        if tt > t[-1]:
            raise ValueError(
                f"phase {x} lands at t={tt:.6e} s, past the transient's end "
                f"{t[-1]:.6e} s -- the trajectory deck's tstop is too short"
            )
        if snap:
            i = nearest_index(t, tt)
            row = {"phase_cycles": x,
                   "phase_cycles_actual": (t[i] - t0) / period,
                   "t_s": t[i], "snapped": True}
            for name, col in zip(column_names, cols):
                row[name] = col[i]
        else:
            row = {"phase_cycles": x, "phase_cycles_actual": x,
                   "t_s": tt, "snapped": False}
            for name, col in zip(column_names, cols):
                row[name] = interp_at(t, col, tt)
        rows.append(row)
    return rows


#: Shift, in cycles, between one ring stage's trajectory and the next's.
#:
#: MEASURED rather than assumed -- see `stage_symmetry` -- but this is the value
#: the ring's topology predicts and the one the residual is quoted against.  In an
#: N-stage ring of INVERTING stages the oscillation has one inversion per lap, so
#: the period is `2 N t_d` and one stage's delay is `T / (2 N)`; the next stage's
#: waveform is the previous one delayed by that AND inverted, and for a waveform
#: whose two half-cycles are alike, inverted is the same as shifted by `T / 2`.
#: So the stage-to-stage shift is `1/(2N) + 1/2` of a cycle, which for N = 5 is
#: **0.6**, not the `1/5` that "five stages evenly spaced around the cycle" would
#: suggest.  Getting this wrong does not look like an error: comparing at `1/5`
#: puts nearly-antiphase waveforms against each other and returns a residual of
#: ~98 % of the peak-to-peak swing, which reads exactly like a ring whose stages
#: are not replicas.  That is what the first version of this check reported.
STAGE_SHIFT_CYCLES = 0.6


def stage_symmetry(t, cols, column_names, *, t0, period, phases, stages,
                   instance, param, shift_scan=400):
    """Are the ring's stages one trajectory, shifted?  And shifted by how much?

    A jitter sum that measures `h` and `S_i` on ONE stage and multiplies the
    result by the stage count assumes every stage traverses the same trajectory,
    displaced in time.  This function measures that assumption instead of making
    it, in two parts:

      * the residual at the **predicted** shift `STAGE_SHIFT_CYCLES * (stage - 1)`
        (mod 1), normalised by stage 1's own peak-to-peak swing of the same
        quantity, and
      * the shift that **minimises** the RMS residual, found by scanning
        `shift_scan` shifts across the full cycle, and its residual.

    The second is what makes the first trustworthy: if the best-fit shift comes
    back at the predicted value, then the residual at that shift is a statement
    about the stages, and if it does not, the residual at the predicted shift was
    a statement about the prediction.  The two are not distinguishable from one
    number.

    The stages are NOT expected to be identical to zero residual: stage 5's output
    also drives the output buffer chain (`XMBP1`/`XMBN1` in
    `design/netlist/vco.spice`), so it carries a load the other four do not.
    """
    idx = {n: i for i, n in enumerate(column_names)}

    def key_of(stage):
        k = f"@m.x0.xs{stage}.{instance.lower()}.m0[{param}]"
        if k not in idx:
            raise ValueError(f"{k} is not a sampled column")
        return k

    n = len(phases)
    if n < 2:
        raise ValueError("stage_symmetry needs a phase grid")
    for k, x in enumerate(phases):
        if abs(x - k / float(n)) > 1e-9:
            raise ValueError(
                "stage_symmetry needs the uniform phase grid `k/n` -- the shift "
                "scan indexes a dense reference grid by integer arithmetic"
            )
    # The scan resolution, rounded to a multiple of the phase count so that
    # `ref(x - shift)` is an INDEX into a precomputed grid rather than another
    # interpolation: the naive form is `shift_scan * n_phases` interpolations per
    # stage and dominates the whole reduction's runtime.
    m = max(1, round(shift_scan / n)) * n
    step = m // n
    ref_col = cols[idx[key_of(stages[0])]]
    grid = [interp_at(t, ref_col, t0 + (j / float(m)) * period) for j in range(m)]
    ptp = max(grid) - min(grid)

    def residual(col, shift):
        resid = [
            interp_at(t, col, t0 + x * period)
            - interp_at(t, ref_col, t0 + (x - shift) * period)
            for x in phases
        ]
        return (max(abs(r) for r in resid),
                math.sqrt(sum(r * r for r in resid) / len(resid)))

    out = []
    for stage in stages:
        col = cols[idx[key_of(stage)]]
        predicted = (STAGE_SHIFT_CYCLES * (stage - stages[0])) % 1.0
        peak, rms = residual(col, predicted)
        got = [interp_at(t, col, t0 + x * period) for x in phases]
        best_shift, best = None, None
        for i in range(m):
            resid = [got[k] - grid[(k * step - i) % m] for k in range(n)]
            cand = (max(abs(r) for r in resid),
                    math.sqrt(sum(r * r for r in resid) / n))
            if best is None or cand[1] < best[1]:
                best, best_shift = cand, i / float(m)
        out.append({
            "stage": stage,
            "predicted_shift_cycles": predicted,
            "peak_residual": peak,
            "rms_residual": rms,
            "peak_residual_frac_of_ptp": (peak / ptp if ptp > 0 else float("nan")),
            "best_fit_shift_cycles": best_shift,
            "best_fit_shift_minus_predicted_cycles": (
                (best_shift - predicted + 0.5) % 1.0 - 0.5
            ),
            "best_fit_peak_residual": best[0],
            "best_fit_rms_residual": best[1],
            "best_fit_peak_residual_frac_of_ptp": (
                best[0] / ptp if ptp > 0 else float("nan")
            ),
            # The RMS fraction is the one to quote for `id`: its peak residual is
            # set by the switching instant, where the current is a spike a few
            # sampled phases wide, so a peak-normalised figure there reports the
            # grid's resolution of that spike rather than the stages' likeness.
            "best_fit_rms_residual_frac_of_ptp": (
                best[1] / ptp if ptp > 0 else float("nan")
            ),
            "rms_residual_frac_of_ptp": (rms / ptp if ptp > 0 else float("nan")),
            "shift_scan_resolution_cycles": 1.0 / m,
        })
    return {"instance": instance, "param": param, "stage1_ptp": ptp,
            "predicted_shift_per_stage_cycles": STAGE_SHIFT_CYCLES,
            "stages": out}


# ---------------------------------------------------------------------------
# the noise deck
# ---------------------------------------------------------------------------
_PRINT_RE = re.compile(r"^(\S+)\s*=\s*([-+0-9.eEdD]+)\s*$")


def parse_noise_log(text: str, freqs) -> dict:
    """One `sid_deck.noise_deck` log -> operating point + one block per frequency.

    Parses positionally, in the order `noise_deck` prints: the operating point
    once, then per frequency `zm<k>`, `onoise_total_rs_thermal`, the two
    `onoise_total.<gen>` and the two `inoise_total.<gen>`.  Raises if any
    expected name is missing -- an ngspice `print` of an unknown vector emits a
    diagnostic and no `name = value` line, so a silently short parse is exactly
    how a renamed noise vector would become a table of zeros.
    """
    seen: list[tuple[str, float]] = []
    for line in text.splitlines():
        m = _PRINT_RE.match(line.strip())
        if m:
            seen.append((m.group(1), float(m.group(2).replace("D", "E").replace("d", "e"))))
    byname: dict[str, float] = {}
    for name, val in seen:
        byname.setdefault(name, val)

    op = {}
    for p in ("vgs", "vds", "vbs", "id", "gm", "gds"):
        key = f"@m.xm1.m0[{p}]"
        if key not in byname:
            raise ValueError(f"noise log: `{key}` not printed -- the op failed?")
        op[p] = byname[key]
    if "v(d)" not in byname:
        raise ValueError("noise log: `v(d)` not printed -- the op failed?")
    op["v_drain_node"] = byname["v(d)"]

    per_f = []
    # The per-frequency vectors all share one name, so they must be taken in
    # print order rather than by name.
    order = [n for n, _ in seen]
    vals = [v for _, v in seen]
    cursor = 0
    for k, f in enumerate(freqs):
        want = [
            f"zm{k}",
            "onoise_total_rs_thermal",
            "onoise_total.m.xm1.m0.id",
            "onoise_total.m.xm1.m0.1overf",
            "inoise_total.m.xm1.m0.id",
            "inoise_total.m.xm1.m0.1overf",
        ]
        block = {}
        for name in want:
            try:
                cursor = order.index(name, cursor)
            except ValueError as exc:
                raise ValueError(
                    f"noise log: `{name}` not printed for f={f:g} Hz -- "
                    "an unknown-vector diagnostic prints nothing parseable"
                ) from exc
            block[name] = vals[cursor]
            cursor += 1
        block["freq_Hz"] = f
        per_f.append(block)
    return {"op": op, "per_freq": per_f}


def units_anchor(block: dict, *, rsense: float, temp_c: float, bw: float) -> float:
    """`measured / expected` for the sense resistor's own thermal noise.

    The resistor is a known noise source in the same network as the device, so
    its reported contribution is an absolute check on the whole chain: the
    `noise2` plot's units (V RMS, not V^2), the analysis bandwidth actually used,
    and the transimpedance the reduction divides by.  Expected value: the
    resistor's thermal current `sqrt(4 k T / R * bw)` into the node impedance
    `Z_m`, i.e. `sqrt(4 k T R * bw) * Z_m / R`.

    Returns a ratio that must be 1 to within the caller's tolerance.  Any
    deviation is a deviation in the *density* every `S_id` in the same run is
    read off, in the same proportion.
    """
    # Each block carries its own `zm<k>` under the k it was parsed at.
    zm = next(v for k, v in block.items() if k.startswith("zm"))
    expect = math.sqrt(4.0 * K_B * kelvin(temp_c) * rsense * bw) * zm / rsense
    return block["onoise_total_rs_thermal"] / expect


def extract_sid(block: dict) -> dict:
    """One frequency block -> drain-current PSDs, two ways, and their agreement.

    `onoise_total.<gen>` is the generator's contribution to the output node
    voltage; dividing by the measured transimpedance `Z_m` and squaring gives the
    generator's own current PSD in A^2/Hz.  `inoise_total.<gen>` is ngspice's own
    input-referred figure, and because the `.noise` input source IS the
    drain-to-source current probe, squaring it gives the same quantity by a
    different route.  Both are returned, with the relative difference, because
    "`inoise_total` is the input-referred density" is a statement about ngspice
    that this directory would rather measure than cite.
    """
    zm = next(v for k, v in block.items() if k.startswith("zm"))
    out = {"freq_Hz": block["freq_Hz"], "zm_ohm": zm}
    for gen, key in (("thermal", "id"), ("flicker", "1overf")):
        via_o = (block[f"onoise_total.m.xm1.m0.{key}"] / zm) ** 2
        via_i = block[f"inoise_total.m.xm1.m0.{key}"] ** 2
        out[f"S_{gen}_A2_per_Hz"] = via_o
        out[f"S_{gen}_A2_per_Hz_inoise"] = via_i
        out[f"S_{gen}_rel_diff"] = (
            (via_i - via_o) / via_o if via_o > 0 else float("nan")
        )
    return out


def series_resistance(standalone: dict, *, polarity: float, rsense: float) -> float:
    """`rd + rs` of the device, measured from one `op` of the noise deck.

    The deck's source node is ground, so in the device's own polarity the
    external drain-source voltage is `polarity * v(d)` while `@m...[vds]` is the
    voltage across the channel inside `rd`/`rs`.  The difference, over `I_d`, is
    `rd + rs + rsense`; subtracting the known `rsense` leaves the device's own.

    Measured rather than read out of the model card because `rd`/`rs` are
    assembled from `nrd`/`nrs`, the sheet resistance of the selected corner
    section and BSIM4's own geometry model -- three places a transcription could
    go wrong.  One measurement per device class suffices (`rdsmod = 0`, so these
    are geometric and bias-independent), and the per-phase `reproduction()` check
    is what confirms the value travels.
    """
    idv = standalone["id"]
    if idv == 0:
        raise ValueError("series_resistance needs a conducting bias point")
    total = (polarity * standalone["v_drain_node"] - standalone["vds"]) / idv
    return total - rsense


def reproduction(insitu: dict, standalone: dict) -> dict:
    """Does the standalone device reproduce the in-situ one's small-signal state?

    This is the only check available on whether the bias triple lifted off the
    trajectory was applied to the right terminals with the right polarity.  A
    p-type sign error, a `V_bs` dropped on the floor, a `V_ds` left uncorrected
    for the sense resistor -- each one leaves `.noise` perfectly happy and the
    resulting table smooth and wrong.  Comparing `I_d`, `g_m` and `g_ds` catches
    all three, because all three are steep functions of the bias in exactly the
    region a ring device spends its cycle traversing.

    Both an ABSOLUTE and a relative residual are reported for every quantity, and
    the absolute one is the honest figure of merit for the voltages: `V_bs` of the
    two current-source devices is identically zero by construction (source and
    bulk are the same net), so a relative residual there divides by ~1e-6 V of
    solver noise and reports a "1260 % error" on a bias that is correct to a
    nanovolt.  The summary quotes absolute volts for `V_gs`/`V_ds`/`V_bs` and
    relative for `I_d`/`g_m`/`g_ds` for exactly that reason.
    """
    out = {}
    for p in ("vgs", "vds", "vbs", "id", "gm", "gds"):
        ref = insitu[p]
        got = standalone[p]
        out[f"{p}_insitu"] = ref
        out[f"{p}_standalone"] = got
        out[f"{p}_abs_diff"] = got - ref
        out[f"{p}_rel_diff"] = (abs(got) / abs(ref) - 1.0) if ref else None
    return out


def noise_conductance(s_thermal: float, temp_c: float) -> float:
    """`g_n = S_id / (4 k T)`, siemens -- the physics bracket's own quantity.

    A channel thermal generator is `4 k T * g_n` for some conductance `g_n` set
    by the channel, so dividing it out gives a number with a textbook range
    rather than an absolute PSD with no scale.  In strong-inversion saturation
    `g_n ~ (2/3) g_m`; in triode `g_n ~ g_d0`, the zero-bias channel conductance,
    of which the reported `g_ds` is a lower bound; deep in subthreshold the
    generator is shot-like, `2 q I_d`, i.e. `g_n ~ I_d / (2 V_T)`.  So a correct
    extraction lands `g_n` inside a factor of a few of `max(g_m, g_ds,
    I_d / 2 V_T)` at every phase, and a units or transimpedance error does not.
    """
    return s_thermal / (4.0 * K_B * kelvin(temp_c))


def shot_conductance(id_a: float, temp_c: float) -> float:
    """`2 q |I_d| / (4 k T)` -- the subthreshold arm of the physics bracket."""
    return 2.0 * Q_E * abs(id_a) / (4.0 * K_B * kelvin(temp_c))


def physics_bracket(s_thermal: float, op: dict, temp_c: float) -> dict:
    """`g_n` against the three textbook limits, and the ratio to the largest."""
    g_n = noise_conductance(s_thermal, temp_c)
    limits = {
        "gm": abs(op["gm"]),
        "gds": abs(op["gds"]),
        "shot": shot_conductance(op["id"], temp_c),
    }
    largest = max(limits.values()) if max(limits.values()) > 0 else float("nan")
    return {
        "g_n_S": g_n,
        "limits_S": limits,
        "g_n_over_largest_limit": g_n / largest if largest > 0 else float("nan"),
    }


def flicker_exponent(freqs, densities) -> dict:
    """Fit `S(f) = K * f**(-alpha)` by least squares in log-log, and report residual.

    Reported rather than assumed, because `fnoimod = 1` in the gf180mcu BSIM4
    cards is the unified flicker model, which is not exactly `1/f`.  The
    exponent is what decides whether the flicker contribution to a period-jitter
    RMS converges at the low-frequency end at all, and the observation interval
    that bounds that integral is not stated by `spec/pll.md`'s Period jitter row
    -- so this function's job is to make the dependence explicit rather than to
    integrate it away.
    """
    pts = [(f, s) for f, s in zip(freqs, densities) if f > 0 and s > 0]
    if len(pts) < 2:
        raise ValueError("need >= 2 positive (f, S) points for an exponent")
    xs = [math.log10(f) for f, _ in pts]
    ys = [math.log10(s) for _, s in pts]
    n = len(pts)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    return {
        "alpha": -slope,
        "K_at_1Hz": 10.0 ** intercept,
        "max_abs_resid_dex": max(abs(r) for r in resid),
        "n_points": n,
    }


def whiteness(freqs, densities) -> dict:
    """Peak-to-peak spread of a nominally white density across the measured band."""
    lo, hi = min(densities), max(densities)
    return {
        "min": lo,
        "max": hi,
        "span_rel": (hi / lo - 1.0) if lo > 0 else float("nan"),
        "f_min_Hz": min(freqs),
        "f_max_Hz": max(freqs),
    }


# ---------------------------------------------------------------------------
# what the stationary approximation costs
# ---------------------------------------------------------------------------
def cycle_average(phases, values) -> float:
    """Time average of `values` over one cycle, sampled on a UNIFORM phase grid.

    For a uniform grid covering `[0, 1)` of a periodic function, the trapezoid
    rule and the plain mean coincide (the wrap-around interval closes the loop),
    so the mean is exact to the same order and needs no endpoint special-casing.
    A non-uniform grid is refused rather than silently mis-weighted.
    """
    if len(phases) != len(values) or not phases:
        raise ValueError("phases and values must be the same non-zero length")
    if len(phases) > 1:
        step = phases[1] - phases[0]
        for a, b in zip(phases, phases[1:]):
            if abs((b - a) - step) > 1e-9:
                raise ValueError(
                    "cycle_average needs a uniform phase grid; got "
                    f"non-uniform spacing near {a}"
                )
    return sum(values) / len(values)


def db10(ratio: float) -> float:
    """`10 log10` -- for POWER-like quantities: a PSD ratio."""
    return 10.0 * math.log10(ratio) if ratio > 0 else float("-inf")


def span_db(values) -> float:
    """`10 log10 (max / min)` over a PSD trace -- the cyclostationary span."""
    pos = [v for v in values if v > 0]
    if len(pos) < 2:
        return float("nan")
    return db10(max(pos) / min(pos))


def match_phase_grids(phases_a, values_a, phases_b, values_b, *, tol=1e-6):
    """The phases present in BOTH grids, with both traces' values, in order.

    Used to put the committed `h(x)` table (measured on a 12- or 24-point grid by
    `../isf-bringup/`) and this directory's `S_id(x)` table on one grid without
    interpolating either.  Interpolation is refused on purpose: `h` near the
    switching edge changes sign and swings by 20x between adjacent sampled
    phases, so an interpolated `h` is a fabricated number exactly where the
    `h^2`-weighted sum is dominated.  The intersection is used instead, and the
    caller reports how many phases it kept.

    Returns `(phases, a_values, b_values)` and refuses a non-uniform
    intersection, because every average downstream weights phases equally.
    """
    out = []
    for pa, va in zip(phases_a, values_a):
        for pb, vb in zip(phases_b, values_b):
            if abs(pa - pb) <= tol:
                out.append((pa, va, vb))
                break
    if not out:
        raise ValueError("the two phase grids share no phase within tol")
    out.sort(key=lambda r: r[0])
    ph = [r[0] for r in out]
    if len(ph) > 1:
        step = ph[1] - ph[0]
        for a, b in zip(ph, ph[1:]):
            if abs((b - a) - step) > 1e-6:
                raise ValueError(
                    "the intersection of the two phase grids is non-uniform "
                    f"near {a} -- an equal-weight average of it is not a cycle "
                    "average"
                )
    return ph, [r[1] for r in out], [r[2] for r in out]


def isf_weighted_cost(phases, densities, h_gen, *, conventions) -> dict:
    """What a stationary `S_id` costs against the `h^2`-WEIGHTED trajectory average.

    The jitter sum is `var(dT) = (1/w0^2) (1/2) integral h_gen(t)^2 S_i(t) dt`, so
    the single number a stationary approximation has to get right is not the plain
    cycle average `<S>` that `stationary_cost` compares against -- it is the
    `h^2`-weighted one,

        S_eff = sum(h^2 S) / sum(h^2),

    because substituting a constant `S_0` into the integral gives
    `S_0 * sum(h^2)`, so the integral is wrong by exactly `S_0 / S_eff`.  That
    ratio is what this function reports, per naming convention, in dB.  It is the
    quantity `stationary_cost`'s docstring names as owed and does not compute, and
    it is the bound #520's option (B) has to state before a `trnoise()` amplitude
    calibrated at one bias may be published.

    `weighted_over_unweighted_dB` is the interesting comparison for a reader who
    has only the unweighted figure: it says whether the ISF weighting lands on the
    high-`S` or the low-`S` part of the cycle, i.e. whether the unweighted number
    flatters or penalises the stationary approximation.

    `h2_participation` is `(sum h^2)^2 / (n sum h^4)`: 1.0 if every phase carries
    equal weight, `1/n` if one phase carries all of it.  A small value is a
    warning that the weighted average is set by one or two sampled phases and is
    therefore limited by the phase resolution of the `h` table, not by `S_id`.
    """
    if len(phases) != len(densities) or len(phases) != len(h_gen):
        raise ValueError("phases, densities and h_gen must be the same length")
    w = [hh * hh for hh in h_gen]
    sw = sum(w)
    if sw <= 0:
        raise ValueError("sum(h^2) is not positive -- no weighting is defined")
    s_eff = sum(wi * s for wi, s in zip(w, densities)) / sw
    avg = cycle_average(phases, densities)
    sw4 = sum(wi * wi for wi in w)
    out = {
        "n_phases": len(phases),
        "phases": list(phases),
        "S_eff_A2_per_Hz": s_eff,
        "unweighted_cycle_average_A2_per_Hz": avg,
        "weighted_over_unweighted_dB": db10(s_eff / avg) if avg > 0 else float("nan"),
        "h2_participation": (sw * sw) / (len(w) * sw4) if sw4 > 0 else float("nan"),
        "h_gen_peak_abs": max(abs(hh) for hh in h_gen),
        "conventions": {},
    }
    for name, value in conventions.items():
        out["conventions"][name] = {
            "S_A2_per_Hz": value,
            "ratio_to_S_eff": (value / s_eff) if s_eff > 0 else float("nan"),
            "error_dB": db10(value / s_eff) if (s_eff > 0 and value > 0) else float("nan"),
        }
    return out


def stationary_cost(phases, densities, *, conventions) -> dict:
    """What a single-bias `S_id` costs against the trajectory average.

    `conventions` maps a name to a single-bias PSD -- e.g. the value at the phase
    where the device carries its peak current, the value at mid-rail, the value
    at the time-averaged bias.  Each is reported as a ratio to the cycle average
    `<S_id>` and in dB.

    This is the quantity #520's option (B) is required to bound before a
    `trnoise()` amplitude calibrated at one bias point may be published, and the
    quantity DR-023 refused a jitter figure for want of.  It is an UPPER bound on
    the error only for a weighting that is flat in phase; the ISF weighting is
    not flat, so the assembled pipeline owes the `h^2`-weighted version of this
    same comparison.  Stated here rather than left for a reader to assume.
    """
    avg = cycle_average(phases, densities)
    out = {"cycle_average": avg, "span_dB": span_db(densities), "conventions": {}}
    for name, value in conventions.items():
        out["conventions"][name] = {
            "S_A2_per_Hz": value,
            "ratio_to_cycle_average": (value / avg) if avg > 0 else float("nan"),
            "error_dB": db10(value / avg) if (avg > 0 and value > 0) else float("nan"),
        }
    return out
