"""gf180-pll :: period-jitter :: random-bound -- the reduction.

Everything that turns ngspice output into the numbers this directory reports,
kept free of any simulator so `sim/tests/test_random_bound.py` can pin it.

THE BOUND.  The ring's and output buffer's generators are bounded by a
transient through three inequalities, each stated where it is used:

  1. WHITE, CYCLOSTATIONARY -> WHITE, STATIONARY.  A white generator of
     time-varying density `S(t)` contributes `(1/w0^2)(1/2) int h(t)^2 S(t) dt`
     to the variance of one period, with `h(t)^2 >= 0`.  So a stationary
     injection at `S_inj >= max_t S(t)` produces at least that variance.  The
     transient measures the left-hand side of the inequality directly, with the
     ring's true `h`; nothing here needs an ISF table.
  2. FLICKER -> WHITE.  A modulated flicker generator `S(t, f) = m(t)^2 K f^-a`
     contributes, IN LOCK, at most what a white generator of density
     `Phi * S(t, F)` would, `F = 0.475 f0` -- see `flicker_factor`.  The loop
     is what makes this finite: the gf180mcu pfet cards set `ef = 1.12`, for
     which a free-running oscillator's single-period variance diverges at DC,
     and the loop's error transfer falls as `f^4` below its crossover.  The
     bound is on the stationary variance, so it needs no observation interval.
  3. OPEN LOOP -> CLOSED LOOP.  In lock the output phase is the free-running
     phase times the loop's error transfer `1/(1 + T(jw))`.  For a white
     generator that can raise the period variance only inside a band around
     the crossover -- `white_loop_factor`, not the envelope's peak.

The bias generator's generators are bounded by a small-signal analysis
instead, because their memory is longer than the window 2 and 3 assume
(`lti_period_variance`); the loop-filter resistor by equipartition
(`kt_over_c_bound`).  `assemble_bound` adds the three in quadrature.

The bound is conservative by construction.  How conservative is reported, not
hidden: `S_inj` against the per-phase values it dominates, and the loop
factors against 1.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

K_B = 1.380649e-23
T0_K = 273.15


def kelvin(temp_c: float) -> float:
    return temp_c + T0_K


# ---------------------------------------------------------------------------
# waveforms and periods
# ---------------------------------------------------------------------------
def read_wrdata(path, ncol: int):
    """`wrdata` + `set wr_singlescale` output -> `(t, [col, ...])`."""
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


def rising_crossings(t, v, level: float):
    """Rising crossings of `level`, linearly interpolated between stored points.

    The same construction `sim/vco-tuning-range/testbench/_numeric.py` and the
    ISF bring-up use: the crossing is placed on the chord between the two stored
    timepoints that straddle it.  At a 10 ps timestep ceiling the chord's error
    is the clean copy's period spread, which every run reports beside its noisy
    copies as the floor.
    """
    out = []
    for i in range(1, len(t)):
        a, b = v[i - 1], v[i]
        if a < level <= b:
            out.append(t[i - 1] + (level - a) * (t[i] - t[i - 1]) / (b - a))
    return out


def periods(crossings, t_start: float):
    """Periods between successive crossings, both ends after `t_start`."""
    c = [x for x in crossings if x >= t_start]
    return [b - a for a, b in zip(c, c[1:])]


def mean(xs):
    return sum(xs) / len(xs)


def pooled_variance(groups):
    """Variance pooled over independent groups, each about its OWN mean.

    Each noisy copy is an independent realisation; removing each copy's own
    mean means a copy-to-copy offset in mean period (there should be none: the
    copies are identical circuits) cannot inflate the jitter.  Returns
    `(variance, degrees_of_freedom, n)`.
    """
    ss = 0.0
    n = 0
    dof = 0
    for g in groups:
        if len(g) < 2:
            raise ValueError("a group needs at least two periods")
        m = mean(g)
        ss += sum((x - m) ** 2 for x in g)
        n += len(g)
        dof += len(g) - 1
    return ss / dof, dof, n


def lag_autocorrelation(groups, lag: int):
    """Lag-`lag` autocorrelation of the period sequence, pooled over groups."""
    num = 0.0
    den = 0.0
    for g in groups:
        m = mean(g)
        d = [x - m for x in g]
        num += sum(a * b for a, b in zip(d, d[lag:]))
        den += sum(a * a for a in d)
    return num / den if den > 0 else float("nan")


def lag1_autocorrelation(groups):
    """Lag-1 autocorrelation of the period sequence, pooled over groups.

    For white generators driving the ring, successive period deviations are
    (to first order) independent, and the pooled sample variance is then an
    unbiased estimate with the stated degrees of freedom.  A large positive
    value would mean slow wander -- dof overstated, confidence interval too
    narrow -- so it is reported beside every variance rather than assumed.
    """
    num = 0.0
    den = 0.0
    for g in groups:
        m = mean(g)
        d = [x - m for x in g]
        num += sum(a * b for a, b in zip(d, d[1:]))
        den += sum(a * a for a in d)
    return num / den if den > 0 else float("nan")


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation, |err| < 1.2e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - plow:
        return -_norm_ppf(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def chi2_ppf(p: float, dof: int) -> float:
    """Chi-square quantile by the Wilson-Hilferty transform.

    Relative error below 1e-3 for `dof >= 30`, which every variance in this
    directory has (the runner refuses fewer).  Implemented here rather than
    imported because this repository's reductions carry no SciPy dependency.
    """
    if dof < 1:
        raise ValueError("dof must be >= 1")
    z = _norm_ppf(p)
    k = float(dof)
    return k * (1.0 - 2.0 / (9.0 * k) + z * math.sqrt(2.0 / (9.0 * k))) ** 3


def sigma_upper(variance: float, dof: int, conf: float = 0.95) -> float:
    """One-sided upper confidence limit on a standard deviation.

    `dof * s^2 / sigma^2 ~ chi2(dof)`, so `sigma <= s * sqrt(dof / chi2_(1-conf))`
    with probability `conf`.  This is the figure every bound here is quoted at:
    the statistical uncertainty of a finite period sequence is added to the
    bound rather than averaged into it.
    """
    return math.sqrt(variance * dof / chi2_ppf(1.0 - conf, dof))


def pairwise_deviation_ratio(a, b):
    """Least-squares slope of `b`'s period deviations on `a`'s, and the residual.

    Used where two runs share ONE noise realisation (same `rndseed`, same deck
    structure) and differ in one setting: a pure amplitude scale, or the
    timestep ceiling.  Each run's deviations are about its own mean.  For a
    linear system the slope is the amplitude ratio exactly, and for a converged
    timestep it is 1; `resid_rel` is the RMS of what the slope does not explain,
    relative to the RMS of `b`'s deviations.
    """
    if len(a) != len(b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    ma, mb = mean(a), mean(b)
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    saa = sum(x * x for x in da)
    if saa <= 0:
        raise ValueError("reference run has no deviation to regress on")
    slope = sum(x * y for x, y in zip(da, db)) / saa
    res = [y - slope * x for x, y in zip(da, db)]
    rms_b = math.sqrt(sum(y * y for y in db) / len(db))
    return {
        "n": len(da),
        "slope": slope,
        "resid_rel": math.sqrt(sum(r * r for r in res) / len(res)) / rms_b,
        "corr": sum(x * y for x, y in zip(da, db)) / math.sqrt(
            saa * sum(y * y for y in db)),
    }


# ---------------------------------------------------------------------------
# the calibration of trnoise itself
# ---------------------------------------------------------------------------
def rc_variance_expected(s_one_sided: float, r: float, c: float) -> float:
    """Variance of `v` across `R || C` driven by a white current of one-sided PSD `S`.

    `v = i * R / (1 + j w R C)`, so `var = int_0^inf S R^2 / (1 + (2 pi f R C)^2) df
    = S R / (4 C)`.  Valid while the source is white well past `1 / (2 pi R C)`,
    which the calibration deck makes true by a factor of 100 (`tau = 1 ns`
    against `NT <= 20 ps`).
    """
    return s_one_sided * r / (4.0 * c)


def effective_samples(n_points: int, dt: float, tau: float) -> float:
    """Effective independent samples of an RC-filtered record: `T / (2 tau)`."""
    return n_points * dt / (2.0 * tau)


# ---------------------------------------------------------------------------
# the noise deck
# ---------------------------------------------------------------------------
_PRINT_RE = re.compile(r"^(\S+)\s*=\s*([-+0-9.eEdD]+)\s*$")


def parse_print(text: str) -> list[tuple[str, float]]:
    out = []
    for line in text.splitlines():
        m = _PRINT_RE.match(line.strip())
        if m:
            out.append((m.group(1), float(m.group(2).replace("D", "E").replace("d", "e"))))
    return out


def parse_noise_log(text: str, mos_ids, res_ids, freqs) -> dict:
    """One `rb_deck.noise_deck` log -> operating points + per-(device, f) densities.

    Positional where names repeat (the `onoise_total...` vectors are printed once
    per frequency), by name where they do not.  Raises on anything missing: an
    ngspice `print` of an unknown vector prints no `name = value` line, so a
    silently short parse is how a renamed vector would become a table of zeros.
    """
    seen = parse_print(text)
    names = [n for n, _ in seen]
    vals = [v for _, v in seen]
    first = {}
    for n, v in seen:
        first.setdefault(n, v)
    op = {}
    for j in mos_ids:
        rec = {}
        for p in ("vgs", "vds", "vbs", "id", "gm", "gds"):
            key = f"@m.xm{j}.m0[{p}]"
            if key not in first:
                raise ValueError(f"noise log: `{key}` not printed -- the op failed?")
            rec[p] = first[key]
        op[j] = rec
    for j in res_ids:
        key = f"i(vr{j})"
        if key not in first:
            raise ValueError(f"noise log: `{key}` not printed")
        op[j] = {"i": first[key]}
    cursor = 0

    def take(name):
        nonlocal cursor
        try:
            cursor = names.index(name, cursor)
        except ValueError as exc:
            raise ValueError(f"noise log: `{name}` missing after position {cursor}") from exc
        v = vals[cursor]
        cursor += 1
        return v

    per = {j: [] for j in mos_ids}
    for f in freqs:
        zm = {j: take(f"mag(v(d{j}))") for j in mos_ids}
        for j in mos_ids:
            blk = {
                "freq_Hz": f,
                "zm_ohm": zm[j],
                "on_total": take(f"onoise_total.m.xm{j}.m0"),
                "on_flicker": take(f"onoise_total.m.xm{j}.m0.1overf"),
                "on_thermal": take(f"onoise_total.m.xm{j}.m0.id"),
                "on_rsense": take(f"onoise_total_rs{j}_thermal"),
            }
            per[j].append(blk)
    return {"op": op, "per_freq": per}


def units_anchor(blk: dict, *, rsense: float, temp_c: float, bw: float = 1.0) -> float:
    """Measured / closed-form for the sense resistor's own thermal noise.

    `sqrt(4 k T R bw) * Z_m / R` -- the same absolute check
    `../sid-trajectory/sid_extract.units_anchor` applies, on every call here too.
    """
    expect = math.sqrt(4.0 * K_B * kelvin(temp_c) * rsense * bw) * blk["zm_ohm"] / rsense
    return blk["on_rsense"] / expect


def densities(blk: dict) -> dict:
    """One block -> the device's current PSDs, A^2/Hz, referred to drain-source.

    `total` is ngspice's per-DEVICE total (`onoise_total.m.<dev>.m0`), which is
    every mechanism the model carries -- channel thermal, flicker, and the
    `rd`/`rs`/`rg` terminal-resistance generators -- and excludes the sense
    resistor.  `white = total - flicker` is everything but the flicker term.
    """
    z = blk["zm_ohm"]
    tot = (blk["on_total"] / z) ** 2
    fl = (blk["on_flicker"] / z) ** 2
    th = (blk["on_thermal"] / z) ** 2
    return {"total": tot, "flicker": fl, "channel_thermal": th,
            "white": max(tot - fl, 0.0),
            "terminal": max(tot - fl - th, 0.0)}


def flicker_exponent(f1: float, s1: float, f2: float, s2: float) -> float:
    """`a` in `S = K f^-a`, from two frequencies."""
    if s1 <= 0 or s2 <= 0:
        return float("nan")
    return math.log(s1 / s2) / math.log(f2 / f1)


# ---------------------------------------------------------------------------
# inequality 2: flicker folded into an equivalent white density
# ---------------------------------------------------------------------------
#: How far past one period the linear response of one period's length can
#: reach, as a fraction of the period.  Every generator the transient injects
#: sits in the ring or the output buffer, whose memory is an edge or a stage's
#: amplitude recovery: noise in period k changes period k, and -- by moving an
#: edge before the ring has settled back to its limit cycle -- period k+1 in
#: the opposite sense, which is the negative lag-1 autocorrelation the
#: transient reports for them.  A full extra period is allowed for that, and
#: the lag-2 autocorrelation, which a longer memory would make non-zero, is
#: reported beside every result.  The bias generator's generators are NOT
#: covered by this window: their memory is the bias nets' time constant, many
#: periods, and they are bounded separately by a small-signal analysis
#: (`lti_period_variance`).  See `flicker_factor`.
WINDOW_MARGIN = 1.0


def flicker_corner_frequency(alpha: float, f0: float) -> float:
    """`F = a f0 / 2` -- the split frequency that minimises the open-loop bound."""
    return alpha * f0 / 2.0


def flicker_factor_open_loop(alpha: float, margin: float = WINDOW_MARGIN) -> float:
    """`(1 + eps a) / (1 - a)`: `flicker_factor` with no loop, for `0 < a < 1` only.

    Kept because it is the closed form `flicker_factor` must reproduce when the
    loop envelope is 1 everywhere (the test pins that), and because it is the
    number that says what the FREE-RUNNING oscillator would do -- which for a
    pfet (`ef = 1.12`) is: diverge.  Raises for `a >= 1` for exactly that reason.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(
            f"flicker exponent {alpha!r} is not in (0, 1): a free-running "
            "oscillator's single-period variance from a 1/f^a generator with "
            "a >= 1 diverges at DC -- only the closed loop bounds it"
        )
    return (1.0 + margin * alpha) / (1.0 - alpha)


def flicker_factor(alpha: float, big_f: float, t_w: float, freqs, env) -> float:
    """`Phi`: a flicker generator's period variance, as a multiple of a white one.

    Setup.  The generator is `n(t) = m(t) x(t)`, `m` periodic, `x` stationary
    with one-sided PSD `S_x(f) = K f^-a` -- the modulated-stationary model a
    periodic noise analysis uses.  One period's deviation is a linear functional
    `D = int_W g(t) x(t) dt` over a window of length `t_w = (1 + eps) T`,
    `g = h m`.  In lock the loop multiplies each spectral component of the
    free-running deviation by the error transfer `E(f) = 1/(1 + T_loop(j 2 pi f))`,
    so

        var D = int_0^inf S_x(f) |G(f)|^2 |E(f)|^2 df.

    Two facts hold for ANY `g`: `|G(f)|^2 <= t_w int g^2` (Cauchy-Schwarz) and
    `int_0^inf |G|^2 df = (int g^2) / 2` (Parseval).  Split at `F`: below it use
    the first with `|E|^2 <= env`; above it use `S_x(f) <= S_x(F)`,
    `|E|^2 <= sup_{f >= F} env` and the second:

        var D <= (int g^2) [ t_w int_0^F S_x env df + S_x(F) sup_{f>=F} env / 2 ].

    A WHITE generator of density `S_w` through the same `g` and NO loop gives
    exactly `S_w (int g^2) / 2`.  So the flicker generator is dominated by a white
    one, same modulation, of density `Phi * S(t, F)` with

        Phi = 2 t_w F^a int_0^F f^-a env(f) df + sup_{f >= F} env(f).

    `env` is the UPPER ENVELOPE of `|E|^2` over every loop the filter admits
    (`loop_envelope`), so `Phi` holds whichever legal configuration the part runs
    in.  Below the crossover `|E|^2` falls as `f^4` (type-II: two integrators), so
    the integral converges for every `a < 5` -- in particular for the pfet cards'
    `ef = 1.12`, where the free-running integral does not.  That is the whole
    reason the loop is in this function: the specification's "in lock" is what
    makes a pfet's flicker contribution to period jitter a finite number.

    What this does NOT need: an observation interval (the bound is the
    stationary variance, which every finite window's expected sample variance is
    at most), the ISF `h`, or the modulation's shape.  With `env == 1` it reduces
    to `flicker_factor_open_loop` at `F = a f0 / 2` -- pinned by a test.

    `freqs`/`env` is a log-spaced grid; below its first point the envelope is
    extended as `env(f0) (f / f0)^4` -- the type-II asymptote -- and that tail is
    doubled as margin (it is ~1e-10 of the total for any loop here).
    """
    if alpha <= 0 or alpha >= 5:
        raise ValueError(f"flicker exponent {alpha!r} outside (0, 5)")
    if not freqs or freqs[0] <= 0 or freqs[-1] < big_f:
        raise ValueError("envelope grid must be positive and reach F")
    # int f^-a env df on the grid, in u = ln f: f^(1-a) env du, trapezoid.
    acc = 0.0
    prev = None
    prev_e = None
    for f, e in zip(freqs, env):
        if f > big_f:
            # Close the last partial segment exactly AT F, with the envelope
            # interpolated in log f -- stopping at the last grid point below F
            # would drop up to one grid step of the integral, which is an
            # UNDER-estimate and so the wrong direction for a bound.
            w = (math.log(big_f) - prev[0]) / (math.log(f) - prev[0])
            e_f = prev_e + w * (e - prev_e)
            cur = (math.log(big_f), big_f ** (1.0 - alpha) * e_f)
            acc += 0.5 * (cur[0] - prev[0]) * (cur[1] + prev[1])
            break
        cur = (math.log(f), f ** (1.0 - alpha) * e)
        if prev is not None:
            acc += 0.5 * (cur[0] - prev[0]) * (cur[1] + prev[1])
        prev, prev_e = cur, e
    f_lo, e_lo = freqs[0], env[0]
    tail = e_lo * f_lo ** (1.0 - alpha) / (5.0 - alpha)  # int_0^f_lo e_lo (f/f_lo)^4 f^-a df
    acc += 2.0 * tail
    sup_hi = max((e for f, e in zip(freqs, env) if f >= big_f), default=1.0)
    return 2.0 * t_w * big_f ** alpha * acc + max(sup_hi, 1.0)


# ---------------------------------------------------------------------------
# inequality 3: the closed loop
# ---------------------------------------------------------------------------
def _z(w: float, r: float, c1: float, c2: float) -> complex:
    """Impedance of the as-built filter: `(R + 1/sC1) || 1/sC2`."""
    s = 1j * w
    zs = r + 1.0 / (s * c1)
    zc2 = 1.0 / (s * c2)
    return zs * zc2 / (zs + zc2)


def log_grid(lo: float, hi: float, per_decade: int) -> list[float]:
    n = int(round(math.log10(hi / lo) * per_decade)) + 1
    return [lo * 10 ** (i / per_decade) for i in range(n)]


def admissible_loops(*, r_range, c1_range, c2_range, pm_min_deg: float,
                     n_rc: int = 3, n_cross: int = 240) -> list[dict]:
    """Every loop `T(s) = A Z(s)/s` the as-built filter admits at `PM >= pm_min`.

    The loop-dynamics campaign's own model (`sim/loop-dynamics/testbench/analyze.py`):
    Icp, Kvco and N enter only through the scalar `A`, so sweeping `A` at each
    filter corner covers every trim code, divider ratio, reference frequency and
    Kvco at once.  `|Z|/w` is monotone, so `A` is swept by sweeping the crossover
    frequency itself (`A = w_c / |Z(w_c)|`) over 10 Hz .. 100 MHz.  Every `A`
    meeting the phase-margin floor is kept -- not only the ones the trim rule
    selects -- a superset, so anything computed from it bounds whatever the rule
    actually picks.
    """
    def lin(lo, hi, n):
        return [lo + (hi - lo) * i / (n - 1) for i in range(n)] if n > 1 else [lo]

    out = []
    fcs = log_grid(10.0, 1e8, n_cross // 7)
    for r in lin(*r_range, n_rc):
        for c1 in lin(*c1_range, n_rc):
            for c2 in lin(*c2_range, n_rc):
                for fc in fcs:
                    w = 2 * math.pi * fc
                    z = _z(w, r, c1, c2)
                    a = w / abs(z)
                    tc = a * z / (1j * w)
                    pm = 180.0 + math.degrees(math.atan2(tc.imag, tc.real))
                    if pm >= pm_min_deg:
                        out.append({"A": a, "r": r, "c1": c1, "c2": c2,
                                    "pm_deg": pm, "fc_Hz": fc})
    if not out:
        raise ValueError("no loop meets the phase-margin floor")
    return out


def error_transfer_sq(f: float, loop: dict) -> float:
    """`|1 / (1 + T(j 2 pi f))|^2` for one loop."""
    w = 2 * math.pi * f
    t = loop["A"] * _z(w, loop["r"], loop["c1"], loop["c2"]) / (1j * w)
    return 1.0 / abs(1.0 + t) ** 2


def loop_envelope(freqs, loops) -> list[float]:
    """Upper envelope of `|1/(1+T)|^2` over `loops`, on `freqs`."""
    return [max(error_transfer_sq(f, lp) for lp in loops) for f in freqs]


def white_loop_factor(freqs, env, t_w: float) -> float:
    """Bound on how much the loop can raise a WHITE generator's period variance.

    `int S_w |G|^2 |E|^2 df <= int S_w |G|^2 df + int S_w |G|^2 (|E|^2 - 1)_+ df
    <= (S_w int g^2 / 2) [1 + 2 t_w int (env - 1)_+ df]` by the same two facts
    `flicker_factor` uses.  The bracket is the factor.  It is close to 1 because
    the loop can only amplify inside a band around its crossover -- a few MHz
    wide at most -- while a white generator's single-period variance is spread
    to beyond `f0 / 2`; the naive bound, `max env`, would multiply everything
    by the peaking and is reported beside it for comparison.
    """
    acc = 0.0
    for (f1, e1), (f2, e2) in zip(zip(freqs, env), zip(freqs[1:], env[1:])):
        acc += 0.5 * (f2 - f1) * (max(e1 - 1.0, 0.0) + max(e2 - 1.0, 0.0))
    return 1.0 + 2.0 * t_w * acc


def kt_over_c_bound(*, temp_c: float, c1: float, c2: float) -> float:
    """Variance of the control node set by the loop-filter resistor's thermal noise.

    `R` in series with `C1`, both across `C2`: at equilibrium the one thermal
    mode is the series capacitance `C1 C2 / (C1 + C2)` charged to `kT`, so
    `var(v_C2) = kT C1 / (C2 (C1 + C2))`, independent of `R`.  Exact for the
    passive network in isolation (equipartition), and a bound in-circuit: every
    other capacitance on the node (the VCO input gate, the charge-pump output)
    only lowers it.

    Why not `.noise`: the filter's `ppolyf_u` resistors model their body as a
    voltage-dependent expression, which ngspice makes a behavioural source and
    treats as NOISELESS, so a `.noise` of the as-built filter would report
    almost none of this.  Equipartition does not depend on that.
    """
    return K_B * kelvin(temp_c) * c1 / (c2 * (c1 + c2))


# ---------------------------------------------------------------------------
# the bias generator: a small-signal (LTI) bound
# ---------------------------------------------------------------------------
def sinc2(x: float) -> float:
    """`(sin(pi x) / (pi x))^2`."""
    if x == 0:
        return 1.0
    y = math.pi * x
    return (math.sin(y) / y) ** 2


def lti_period_variance(freqs, s_df, f0: float, env_freqs=None, env=None) -> float:
    """Period variance, as a fraction of the period squared, from a frequency-noise PSD.

    `s_df` is the one-sided PSD of the oscillator's instantaneous-frequency
    deviation, Hz^2/Hz, on the log-spaced grid `freqs`.  One period's
    deviation is `D = -T^2 * mean over the period of df`, so

        var(D) / T^2 = (1/f0^2) int S_df(f) sinc^2(f/f0) df

    open loop.  In lock the sequence of `D` is filtered by the error transfer;
    with `env` (the upper envelope of `|1/(1+T)|^2` over every admissible
    loop) the closed-loop variance is at most

        (1/f0^2) [ int_0^{f0/2} S sinc^2 env df + max(env) int_{f0/2}^inf S sinc^2 df ]

    -- the second term because a component above `f0/2` aliases onto some
    frequency below it, where the envelope is at most its peak.  `env=None`
    gives the open-loop variance.  Trapezoid in `ln f`; below the grid's first
    point the integrand is dropped (with the loop: the type-II envelope falls
    as `f^4`, so the omitted part is below 1e-9 of the total for any density
    here; without the loop: a white or `1/f^a` density with `a < 1` below 1 Hz
    carries nothing a 150 MHz period can see, and the open-loop figure is used
    only for the validation's white-only comparison).
    """
    def env_at(f):
        if env is None:
            return 1.0
        if f <= env_freqs[0]:
            return env[0]
        if f >= env_freqs[-1]:
            return env[-1]
        lf = math.log(f)
        lo, hi = 0, len(env_freqs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if math.log(env_freqs[mid]) <= lf:
                lo = mid
            else:
                hi = mid
        w = (lf - math.log(env_freqs[lo])) / (math.log(env_freqs[hi]) - math.log(env_freqs[lo]))
        return env[lo] + w * (env[hi] - env[lo])

    peak = max(env) if env is not None else 1.0
    acc = 0.0
    prev = None
    for f, s in zip(freqs, s_df):
        weight = env_at(f) if f <= f0 / 2 else peak
        cur = (math.log(f), f * s * sinc2(f / f0) * weight)
        if prev is not None:
            acc += 0.5 * (cur[0] - prev[0]) * (cur[1] + prev[1])
        prev = cur
    return acc / f0 ** 2


# ---------------------------------------------------------------------------
# the assembled bound
# ---------------------------------------------------------------------------
def assemble_bound(*, sigma_upper_s: float, mean_period_s: float, white_factor: float,
                   peak_sq: float, kt_over_c_v2: float, kvco_hz_per_v: float,
                   f0_hz: float, bias_var_frac: float) -> dict:
    """The random period-jitter bound at one PVT point, in % of the period.

    Three terms, added in quadrature because their sources are independent:

      * the ring's and the output buffer's generators, measured by the
        transient at its one-sided confidence limit, times `white_factor`
        (`white_loop_factor`) for what the loop can do to them in lock.  The
        flicker half is already inside it (`flicker_factor` includes the
        loop), so applying `white_factor` to the whole variance over-counts
        slightly, in the safe direction;
      * the bias generator's generators, `bias_var_frac` (a variance as a
        fraction of the period squared, closed-loop, from
        `lti_period_variance`);
      * the loop-filter resistor, through the control node: `kT C1/(C2(C1+C2))`
        of voltage variance (`kt_over_c_bound`), times the loop's peak error
        transfer `peak_sq`, into fractional frequency by `K_vco / f0`.  A
        single period's frequency is an average of the instantaneous one, and
        averaging cannot raise a variance, so this bounds the period term.
    """
    ring = sigma_upper_s * math.sqrt(white_factor) / mean_period_s
    bias = math.sqrt(bias_var_frac)
    lf = math.sqrt(peak_sq * kt_over_c_v2) * abs(kvco_hz_per_v) / f0_hz
    return {
        "ring_buffer_pct": 100.0 * ring,
        "bias_generator_pct": 100.0 * bias,
        "loop_filter_pct": 100.0 * lf,
        "total_pct": 100.0 * math.sqrt(ring * ring + bias * bias + lf * lf),
    }
