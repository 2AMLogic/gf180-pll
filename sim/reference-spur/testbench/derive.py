"""gf180-pll :: reference-spur :: the spectral reduction that IS this claim.

`sim/harness` reports `.measure` scalars. The reference spur is not a scalar
ngspice can measure: it is the ratio between two *lines of the output
spectrum* -- the sideband at `f_out - f_ref` (and at `f_out + f_ref`) and the
carrier at `f_out`. So the deck writes the locked output waveform with
`wrdata` and this module reduces it, which is the shape
`sim/harness/README.md` documents for `raw_files` + `derived`.

Three things it computes, and why each is here:

``spur_dbc``      the DIRECT measurement -- resample the locked output onto a
                  uniform grid, Hann-window an integer number of reference
                  periods, DFT at exactly ``k * f_ref``, take the worse of the
                  two sidebands, in the LAST window of the run. This is the
                  number the record claims and the one the checks score.
``spur_dbc_fit``  the same measurement extrapolated to zero residual settling
                  drift. The run is ~10 us long and the loop's slow pole is
                  9.3 us, so a few millivolts of control-voltage error is
                  still decaying while the spectrum is taken; that residual
                  moves an extra charge onto the filter each reference cycle
                  and ADDS to the ripple. Every window gives a (sideband
                  amplitude, measured drift charge) pair, and the ripple is
                  linear in the per-cycle charge, so the straight-line fit's
                  intercept at zero drift is the settled value. ``spur_dbc``
                  and ``spur_dbc_fit`` bracket the truth from the pessimistic
                  side and the modelled side, and both are reported.
``spur_tie_dbc``  a cross-check that shares no arithmetic with either: rising
                  edge crossing times only, de-trended into a TIE sequence,
                  its ``f_ref`` component turned into a narrowband-FM spur
                  ``20*log10(theta/2)``. It reads the waveform only where it is
                  steepest (smallest interpolation error) and is blind to
                  anything that is not phase modulation.

Agreement between the DFT and TIE paths is the evidence that neither the
resampling grid nor the window is manufacturing the answer -- the failure mode
this campaign was flagged `complex` for. Disagreement is data too: it would
mean the sideband carries a non-phase (amplitude / waveform-shape) component
once per reference cycle, which the DFT sees and the TIE path does not.

Everything here is stdlib -- `sim/harness` is stdlib-only by design and this
module does not get to add a numpy dependency to the repo's simulation flow
for a handful of DFT bins. Only ~20 bins are needed, so a direct DFT with a
precomputed twiddle table is both simpler and faster than an FFT.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.derived import DerivedTable, fmt_scalar  # noqa: E402

#: Uniform resampling density, samples per reference period. The carrier sits
#: at 6 * f_ref here, so this is ~85 samples per output period -- far above
#: Nyquist, and high enough that aliasing of the clock's own harmonics back
#: onto the sideband bins is negligible (the folding harmonics are at ~13 GHz,
#: where the output buffer's edge rate has long since rolled them off).
NSAMP_PER_REF = 512

#: Highest harmonic of f_ref the spectrum table reports.
KMAX = 20

#: Loop-filter series capacitance, from sim/loop-dynamics record
#: 20260731-195707-3e3814c (R = 77.11 kOhm, C1 = 120.8 pF, C2 = 2.016 pF).
#: Used only to convert a MEASURED control-voltage drift into the
#: per-reference-cycle charge it represents, so the residual settling can be
#: compared against the charge-pump asymmetry charge the spur is made of
#: (2.16 fC median / 3.68 fC worst corner, sim/cp-compliance record
#: 20260731-194124-afa338c via DR-006 section 8).
C1_F = 120.8e-12

#: The measurement runs at 150 MHz -- the highest output frequency one static
#: band code holds across the corner grid (see tb.json's methodology). The
#: ratified band's binding frequency for spur is its 200 MHz ceiling, and
#: theta = 2*pi*f_out*TIE makes that scaling exact arithmetic, reported as its
#: own separately labelled measure rather than folded into the measurement.
F_OUT_MEASURED = 150e6
F_OUT_BINDING = 200e6

#: The spec line this campaign is scored against (spec/pll.md, Reference spur).
SPUR_TARGET_DBC = -55.0


# --------------------------------------------------------------- resampling
def resample(t, y, t0, dt, n):
    """Resample (t, y) onto ``t0 + i*dt`` for ``i < n``, cubically.

    ngspice stores a transient at its own internal timesteps, so the waveform
    is not uniformly sampled and a DFT cannot be taken over it directly.
    ngspice's own `linearize` would resample inside the simulator, but it
    rebuilds the plot that every `.measure` card is then re-evaluated against,
    so the log would carry two different values per measurement -- the same
    reason sim/pll-top-smoke decimates in its runner rather than in ngspice.

    **The interpolant is cubic, and that is load-bearing, not a refinement.**
    A straight linear interpolation of a switching waveform sampled at ~75 ps
    against ~300 ps edges leaves a broadband reconstruction error whose
    spectral floor sits near -74 dBc (measured, see
    `sim/tests/test_reference_spur_derive.py`) -- which is only ~13 dB below
    the level this campaign reports, and biases a -61 dBc sideband by nearly
    2 dB. That is precisely the failure mode this measurement has to avoid: a
    plausible-looking number that is wrong by more than the margin it is being
    judged against. A local four-point Lagrange cubic through the two samples
    on each side is exact for anything up to a cubic and drops the floor by
    ~20 dB on the same data, at no meaningful cost.
    """
    out = [0.0] * n
    j = 0
    last = len(t) - 1
    for i in range(n):
        ti = t0 + i * dt
        while j < last and t[j + 1] < ti:
            j += 1
        if j >= last:
            out[i] = y[last]
            continue
        if j < 1 or j + 2 > last:
            # No room for the four-point stencil at the ends: fall back to
            # linear, which is what the endpoints of any window get anyway.
            t_a, t_b = t[j], t[j + 1]
            out[i] = y[j] if t_b <= t_a else (
                y[j] + (ti - t_a) / (t_b - t_a) * (y[j + 1] - y[j])
            )
            continue
        # Lagrange cubic through (t[j-1], t[j], t[j+1], t[j+2]).
        x0, x1, x2, x3 = t[j - 1], t[j], t[j + 1], t[j + 2]
        y0, y1, y2, y3 = y[j - 1], y[j], y[j + 1], y[j + 2]
        d0 = (x0 - x1) * (x0 - x2) * (x0 - x3)
        d1 = (x1 - x0) * (x1 - x2) * (x1 - x3)
        d2 = (x2 - x0) * (x2 - x1) * (x2 - x3)
        d3 = (x3 - x0) * (x3 - x1) * (x3 - x2)
        if d0 == 0.0 or d1 == 0.0 or d2 == 0.0 or d3 == 0.0:
            out[i] = y1
            continue
        a0, a1 = ti - x0, ti - x1
        a2, a3 = ti - x2, ti - x3
        out[i] = (
            y0 * (a1 * a2 * a3) / d0
            + y1 * (a0 * a2 * a3) / d1
            + y2 * (a0 * a1 * a3) / d2
            + y3 * (a0 * a1 * a2) / d3
        )
    return out


def hann(n):
    """Periodic Hann window (the DFT-correct one, not the symmetric variant)."""
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / n) for i in range(n)]


def harmonic_amplitudes(t, y, fref, t0, t1, kmax=KMAX):
    """Single-sided amplitude (volts) at ``k * fref``, k = 0..kmax.

    The window is an exact integer number of reference periods, so every line
    of a loop that is periodic at f_ref lands exactly on a DFT bin (bin
    ``k * ncyc``): coherent, no scalloping loss, and no peak search that could
    pick the wrong bin. The Hann window is deliberate rather than incidental --
    a rectangular window is leakage-free only for a perfectly stationary
    carrier, and a still-settling loop moves the carrier by a fraction of a
    bin, whose rectangular-window leakage falls only as 1/(bin distance).
    Hann's falls as 1/(distance^3), which puts carrier leakage into the
    sideband bin far below the -60 dBc this measurement is looking for.

    Returns ``None`` when the window is shorter than one reference period.
    """
    span = t1 - t0
    ncyc = int(round(span * fref))
    if ncyc < 1:
        return None
    n = ncyc * NSAMP_PER_REF
    dt = span / n
    ys = resample(t, y, t0, dt, n)
    win = hann(n)
    tab_cos = [math.cos(2.0 * math.pi * i / n) for i in range(n)]
    tab_sin = [math.sin(2.0 * math.pi * i / n) for i in range(n)]
    wy = [ys[i] * win[i] for i in range(n)]

    amps = []
    for k in range(kmax + 1):
        m = (k * ncyc) % n
        re = 0.0
        im = 0.0
        idx = 0
        for i in range(n):
            v = wy[i]
            re += v * tab_cos[idx]
            im -= v * tab_sin[idx]
            idx += m
            if idx >= n:
                idx -= n
        # Hann coherent gain is 0.5; single-sided amplitude is (2|X|/n)/0.5.
        amps.append(4.0 * math.hypot(re, im) / n)
    return amps


# ----------------------------------------------------------- edge / TIE path
def rising_crossings(t, y, threshold, t0, t1):
    """Rising mid-supply crossing times of ``y`` inside ``[t0, t1]``."""
    out = []
    for i in range(1, len(t)):
        if t[i] < t0 or t[i] > t1:
            continue
        if y[i - 1] < threshold <= y[i]:
            dy = y[i] - y[i - 1]
            if dy <= 0:
                continue
            out.append(t[i - 1] + (threshold - y[i - 1]) * (t[i] - t[i - 1]) / dy)
    return out


def linfit(xs, ys):
    """Least-squares (slope, intercept, r2) -- the only fit this module needs."""
    m = len(xs)
    if m < 2:
        return None, None, None
    mx = sum(xs) / m
    my = sum(ys) / m
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None, None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(m))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 1.0
    return slope, intercept, r2


def tie_sequence(crossings):
    """De-trended crossing times: (TIE sequence, mean output period).

    The best-fit straight line through crossing time vs. edge index is the
    ideal clock this waveform is compared against; removing it leaves the time
    interval error. Fitting the ramp rather than assuming a nominal period is
    what keeps a residual frequency offset -- a still-settling loop -- out of
    the TIE, where it would otherwise appear as a ramp and leak into every
    frequency bin.
    """
    m = len(crossings)
    if m < 8:
        return (), None
    slope, intercept, _ = linfit(list(range(m)), list(crossings))
    if slope is None:
        return (), None
    tie = tuple(crossings[i] - (intercept + slope * i) for i in range(m))
    return tie, slope


def tie_component(tie, crossings, freq):
    """Amplitude of the ``freq`` component of a TIE sequence, in seconds."""
    m = len(tie)
    re = sum(tie[i] * math.cos(2.0 * math.pi * freq * crossings[i]) for i in range(m))
    im = -sum(tie[i] * math.sin(2.0 * math.pi * freq * crossings[i]) for i in range(m))
    return 2.0 * math.hypot(re, im) / m


# ---------------------------------------------------------------- windowing
def window_bounds(params):
    """The list of (t0, t1) spectral windows this run's parameters describe."""
    fref = float(params["fref"])
    wa = float(params["wa"])
    wb = float(params["wb"])
    wcyc = int(round(float(params["wcyc"])))
    tw = wcyc / fref
    n = int(math.floor((wb - wa) / tw + 1e-9))
    return [(wa + i * tw, wa + (i + 1) * tw) for i in range(n)]


def window_slice(t, y, t0, t1):
    return [(t[i], y[i]) for i in range(len(t)) if t0 <= t[i] <= t1]


def analyse_window(t, clk, vctrl, vdd, fref, nratio, t0, t1):
    """One window: sideband ratio, drift charge, ripple, TIE spur."""
    amps = harmonic_amplitudes(t, clk, fref, t0, t1)
    out = {"t0": t0, "t1": t1}
    if amps and amps[nratio] > 0.0:
        carrier = amps[nratio]
        out["carrier"] = carrier
        out["lsb"] = amps[nratio - 1] / carrier
        out["usb"] = amps[nratio + 1] / carrier
        out["ratio"] = max(out["lsb"], out["usb"])

    seg = window_slice(t, vctrl, t0, t1)
    if len(seg) > 8:
        xs = [p[0] for p in seg]
        ys = [p[1] for p in seg]
        slope, _, _ = linfit(xs, ys)
        if slope is not None:
            # The charge the residual settling moves per reference cycle:
            # i = C1 * dV/dt, q = i / f_ref.
            out["drift_q_fc"] = C1_F * slope / fref * 1e15
        out["ripple_mv"] = (max(ys) - min(ys)) * 1e3
        out["vctrl_mean"] = sum(ys) / len(ys)

    cross = rising_crossings(t, clk, vdd / 2.0, t0, t1)
    tie, period = tie_sequence(cross)
    if tie and period:
        amp_s = tie_component(tie, cross, fref)
        out["fout_edge"] = 1.0 / period
        out["tie_pk_ps"] = amp_s * 1e12
        theta = 2.0 * math.pi * (1.0 / period) * amp_s
        if theta > 0.0:
            out["tie_dbc"] = 20.0 * math.log10(theta / 2.0)
    return out


# ------------------------------------------------------------------ per point
def _dbc(ratio):
    return 20.0 * math.log10(ratio) if ratio and ratio > 0 else None


def derive_point(point):
    raw = point.raw("spur.dat")
    if not raw.exists():
        return {}
    if len(raw.rows()) < 1000:
        return {}
    t = raw.column("t")
    clk = raw.column("clk")
    vctrl = raw.column("vctrl")

    p = point.params
    fref = float(p["fref"])
    nratio = int(round(float(p["nratio"])))

    out = {}
    # The internal-timestep bound, verified rather than assumed. sim/README.md
    # warns that "there is no Tmax in this deck" is not the same statement as
    # "there is no bound to check": what matters is the ceiling actually in
    # force, and the waveform the deck wrote is the only honest witness to it.
    out["dt_int_mean"] = (t[-1] - t[0]) / (len(t) - 1)

    wins = [
        analyse_window(t, clk, vctrl, point.vdd, fref, nratio, t0, t1)
        for (t0, t1) in window_bounds(p)
    ]
    usable = [w for w in wins if "ratio" in w]
    if not usable:
        return out

    last = usable[-1]
    first = usable[0]
    out["carrier_v"] = last.get("carrier")
    out["spur_lsb_dbc"] = _dbc(last.get("lsb"))
    out["spur_usb_dbc"] = _dbc(last.get("usb"))
    out["spur_dbc"] = _dbc(last.get("ratio"))
    if out["spur_dbc"] is not None:
        out["spur_dbc_200m"] = out["spur_dbc"] + 20.0 * math.log10(
            F_OUT_BINDING / F_OUT_MEASURED
        )
    out["spur_dbc_first"] = _dbc(first.get("ratio"))
    for key, name in (
        ("tie_dbc", "spur_tie_dbc"),
        ("tie_pk_ps", "tie_pk_ps"),
        ("fout_edge", "fout_edge"),
        ("ripple_mv", "vctrl_ripple_mv"),
        ("drift_q_fc", "drift_q_fc"),
    ):
        if last.get(key) is not None:
            out[name] = last[key]

    # Zero-drift extrapolation. The sideband amplitude is linear in the net
    # per-reference-cycle charge, and the residual settling contributes a
    # measured amount of that charge which decays across the run, so a
    # straight line through (drift charge, sideband ratio) evaluated at zero
    # drift is the settled value. r2 is reported beside it: a poor fit means
    # the linear model does not describe this point and the extrapolation
    # should not be leaned on.
    qs = [w["drift_q_fc"] for w in usable if "drift_q_fc" in w]
    rs = [w["ratio"] for w in usable if "drift_q_fc" in w]
    if len(qs) >= 3:
        slope, intercept, r2 = linfit(qs, rs)
        if intercept is not None and intercept > 0:
            out["spur_dbc_fit"] = 20.0 * math.log10(intercept)
            out["spur_fit_r2"] = r2
    return out


# ------------------------------------------------------------------ per run
def derive_tables(run):
    rows = []
    worst_point = None
    worst_value = None
    for pt in run.points:
        spur = pt.get("spur_dbc")
        if spur is not None and (worst_value is None or spur > worst_value):
            worst_value = spur
            worst_point = pt
        verdict = ""
        if spur is not None:
            verdict = "PASS" if spur <= SPUR_TARGET_DBC else "FAIL"
        rows.append(
            (
                pt.corner_id,
                pt.corner,
                fmt_scalar(pt.temp_c, "%g"),
                fmt_scalar(pt.vdd, "%.2f"),
                pt.params.get("vstart", ""),
                fmt_scalar(pt.get("fout"), "%.6g"),
                fmt_scalar(pt.get("carrier_v"), "%.4f"),
                fmt_scalar(pt.get("spur_lsb_dbc"), "%.2f"),
                fmt_scalar(pt.get("spur_usb_dbc"), "%.2f"),
                fmt_scalar(spur, "%.2f"),
                fmt_scalar(pt.get("spur_dbc_200m"), "%.2f"),
                fmt_scalar(pt.get("spur_dbc_fit"), "%.2f"),
                fmt_scalar(pt.get("spur_fit_r2"), "%.3f"),
                fmt_scalar(pt.get("spur_tie_dbc"), "%.2f"),
                fmt_scalar(pt.get("spur_dbc_first"), "%.2f"),
                fmt_scalar(pt.get("tie_pk_ps"), "%.3f"),
                fmt_scalar(pt.get("vctrl_ripple_mv"), "%.3f"),
                fmt_scalar(pt.get("drift_q_fc"), "%.3f"),
                fmt_scalar(pt.get("dt_int_mean"), "%.3e"),
                fmt_scalar(pt.get("ferr"), "%.2e"),
                verdict,
            )
        )

    tables = [
        DerivedTable(
            name="spur_by_corner",
            description=(
                "measured reference spur per PVT point: the worse of the two "
                "f_ref-offset sidebands read out of the locked output spectrum "
                "in the last window, with the zero-drift extrapolation, the TIE "
                "cross-check, the first-window value, the residual drift charge "
                "and the mean internal timestep beside it"
            ),
            columns=(
                "corner_id", "process", "temp_c", "vdd_v", "vstart_v", "fout_hz",
                "carrier_v", "spur_lsb_dbc", "spur_usb_dbc", "spur_dbc",
                "spur_dbc_at_200mhz", "spur_dbc_zero_drift_fit", "fit_r2",
                "spur_tie_dbc", "spur_dbc_first_window", "tie_pk_ps",
                "vctrl_ripple_mv", "drift_q_fc", "dt_int_mean_s", "ferr",
                "verdict_vs_minus55dbc",
            ),
            rows=tuple(rows),
            notes=(
                "spur_dbc is the direct measurement, in the last spectral window "
                "of the run. It is the CONSERVATIVE number: the residual "
                "settling drift still present adds to the ripple rather than "
                "subtracting from it.",
                "spur_dbc_at_200mhz scales spur_dbc by 20*log10(200/150) = "
                "+2.50 dB to the ratified band's binding output frequency. That "
                "is arithmetic on the narrowband-FM relation, not a measurement.",
                "spur_dbc_zero_drift_fit extrapolates the per-window (drift "
                "charge, sideband amplitude) pairs to zero residual drift; "
                "fit_r2 says how well the linear model held. drift_q_fc is the "
                "last window's own residual, to be read against the 2.16-3.68 fC "
                "charge-pump asymmetry the spur is made of.",
            ),
        )
    ]

    # `spectrum_worst` is declared, so it is always returned -- an empty table
    # when no point produced a spectrum, never a missing one. The harness
    # treats a declared-but-absent table as an error, and rightly: a record
    # that silently drops a declared reduction is weaker than the one it
    # replaces.
    spec_rows = []
    if worst_point is not None:
        raw = worst_point.raw("spur.dat")
        if raw.exists() and raw.rows():
            t = raw.column("t")
            clk = raw.column("clk")
            p = worst_point.params
            fref = float(p["fref"])
            nratio = int(round(float(p["nratio"])))
            bounds = window_bounds(p)
            if bounds:
                t0, t1 = bounds[-1]
                amps = harmonic_amplitudes(t, clk, fref, t0, t1)
                if amps:
                    carrier = amps[nratio]
                    for k, a in enumerate(amps):
                        dbc = _dbc(a / carrier) if carrier > 0 else None
                        role = ""
                        if k == nratio:
                            role = "carrier (f_out)"
                        elif k == nratio - 1:
                            role = "lower reference sideband (f_out - f_ref)"
                        elif k == nratio + 1:
                            role = "upper reference sideband (f_out + f_ref)"
                        elif k and k % nratio == 0:
                            role = "harmonic of f_out"
                        spec_rows.append(
                            (k, "%.6g" % (k * fref), "%.6e" % a, fmt_scalar(dbc, "%.2f"), role)
                        )
    where = worst_point.corner_id if worst_point is not None else "no point produced one"
    tables.append(
        DerivedTable(
            name="spectrum_worst",
            description=(
                "the measured output spectrum at the worst-spur corner (%s), "
                "last window: amplitude at every harmonic of f_ref through "
                "k = %d, so the sideband the claim rests on can be read against "
                "the carrier and against everything else in the spectrum"
                % (where, KMAX)
            ),
            columns=("k", "f_hz", "amplitude_v", "dbc", "role"),
            rows=tuple(spec_rows),
        )
    )
    return tables
