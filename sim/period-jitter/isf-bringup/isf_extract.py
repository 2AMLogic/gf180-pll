"""gf180-pll :: period-jitter :: ISF bring-up -- waveform reduction.

Turns the multi-copy transient `sim/period-jitter/isf-bringup/isf_deck.py`
writes into the impulse sensitivity function, in the only units that matter to
a jitter calculation:

    h(x) = dphi / dq        [rad / C]

`h` is Hajimiri-Lee's `Gamma(x) / q_max`.  The two are never separated here,
deliberately: `q_max` is a modelling convention (which node, which swing, which
capacitance), whereas `h` is directly measurable -- inject a known charge, read
the asymptotic phase shift -- and it is `h`, not `Gamma` and not `q_max`
individually, that the period-jitter sum needs:

    var(dT) over one period = (1 / w0^2) * (1/2) * integral_0^T h(t)^2 S_i(t) dt

for a noise current of one-sided PSD `S_i`.  Every `q_max` in the textbook
statement of that sum cancels against the `q_max` inside `Gamma`.  Reporting
`h` therefore removes a whole class of convention error from the pipeline, at
the cost of numbers that are not directly comparable with a published
`Gamma`-normalised plot.  That trade is stated here rather than hidden.

The crossing primitive is `sim/vco-tuning-range/testbench/_numeric.py`'s
`crossings()` -- the same linear interpolation `sim/period-jitter`'s own
deterministic reduction and `sim/reference-spur`'s TIE cross-check use -- so
this bring-up cannot disagree with the committed campaigns about what a
threshold crossing of the same waveform is.
"""

from __future__ import annotations

import math
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_NUMERIC = _HERE.parents[1] / "vco-tuning-range" / "testbench" / "_numeric.py"


def _load_numeric():
    import importlib.util
    import sys

    key = "_gf180_isf_numeric"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, _NUMERIC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def crossings(t, y, th, tmin=0.0):
    """Rising mid-supply crossings -- `sim/vco-tuning-range`'s own primitive."""
    return _load_numeric().crossings(t, y, th, tmin)


def read_wrdata(path, ncol):
    """ngspice `wrdata`/`wr_singlescale` output -> (t, [col0, col1, ...])."""
    t: list[float] = []
    cols: list[list[float]] = [[] for _ in range(ncol)]
    with open(path) as fh:
        for line in fh:
            f = line.split()
            if len(f) != ncol + 1:
                continue
            try:
                vals = [float(x) for x in f]
            except ValueError:
                continue
            t.append(vals[0])
            for i in range(ncol):
                cols[i].append(vals[i + 1])
    if not t:
        raise ValueError(f"{path}: no {ncol + 1}-column rows found")
    return t, cols


def shift_sequence(ref, perturbed):
    """Per-crossing time shift of `perturbed` against `ref`, in seconds.

    Both sequences come from the SAME transient, so crossing `i` of one is
    crossing `i` of the other -- no alignment search, and none is wanted: a
    search would silently absorb a whole-cycle slip instead of reporting it.

    Unequal crossing counts are an ERROR, not something to truncate past.  A
    perturbed copy that gains or loses an edge relative to the reference is
    either outside the linear regime or has had an edge clipped by the end of
    the window; either way, index `i` no longer means the same cycle in both
    sequences and every shift after the discrepancy would be wrong by a whole
    period while still looking like a plausible number.
    """
    if len(ref) != len(perturbed):
        raise ValueError(
            f"crossing-count mismatch: reference has {len(ref)}, perturbed has "
            f"{len(perturbed)} -- shorten the window or reduce the injected "
            "charge; index alignment is not recoverable by truncation"
        )
    if not ref:
        raise ValueError("no crossings to compare")
    return [p - r for r, p in zip(ref, perturbed)]


def settled_shift(dts, t_cross, t_inject, settle_cycles=2):
    """The asymptotic shift, and the evidence that it IS asymptotic.

    Returns `(dt, spread, n, drift)`:
      `dt`      mean shift over the settled tail, seconds
      `spread`  peak-to-peak of the tail about that mean, seconds -- the
                bring-up's own numerical noise floor, reported beside every
                number rather than assumed
      `n`       how many crossings the tail has
      `drift`   least-squares slope of the tail, seconds per cycle: a
                non-zero slope means the perturbation has NOT settled into a
                pure phase shift and the number must not be used

    `settle_cycles` crossings immediately after the injection are discarded:
    an oscillator's response to an impulse contains an amplitude transient
    that decays, and only the phase part survives it.
    """
    num = _load_numeric()
    tail = [
        d
        for d, tc in zip(dts, t_cross)
        if tc > t_inject
    ][settle_cycles:]
    if len(tail) < 3:
        raise ValueError(
            f"only {len(tail)} settled crossings after t_inject={t_inject:g} "
            "-- lengthen the run or inject earlier"
        )
    mean = sum(tail) / len(tail)
    spread = max(tail) - min(tail)
    _, slope = num.linefit_residual(tail)
    return mean, spread, len(tail), slope


def sensitivity(dt, period, dq):
    """h = dphi/dq in rad/C, from an asymptotic time shift.

    Sign convention: a LATER crossing (`dt > 0`) is a phase LAG, so
    `dphi = -2*pi*dt/T`.  Stated because the sign of `h` is meaningless on its
    own but its shape across the cycle is the whole point of the measurement.
    """
    return -2.0 * math.pi * dt / (period * dq)


def mean_period(cross):
    """Mean period of a crossing sequence (least-squares, not first-to-last)."""
    num = _load_numeric()
    slope, _ = num.linfit(list(range(len(cross))), list(cross))
    return slope


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0


def node_differences(rows, period, pairs=(("Y", "NT"), ("Y", "NH"))):
    """The DIFFERENTIAL ISFs a two-terminal noise generator is weighted by.

    A device's channel-noise generator is a current source between its drain
    and its source, not a current into one node: the switching nfet's generator
    drives current from the stage output `Y` into the tail node `NT`.  The phase
    shift it produces is therefore weighted by a DIFFERENCE of the two nodes'
    ISFs, and a jitter sum built from `h(Y)` alone would be weighting a current
    that does not exist.

    SIGN CONVENTION, stated because getting it wrong is invisible in the answer.
    `pairs` entries are `(drain, source)`.  A drain-to-source generator current of
    `+1 A` REMOVES charge from the drain and delivers it to the source, so its
    sensitivity is

        h_gen = h(source) - h(drain)

    -- the negative of the drain-referred difference one writes down first.  Only
    `h_gen**2` enters the jitter sum, so the sign changes no result; what it
    changes is whether this function and `crosscheck_pairs` are talking about the
    same quantity, and the first version of this file had it backwards.  The
    cross-check is what caught it: the two constructions came back agreeing to
    0.03 % in magnitude and exactly opposite in sign, which is what a sign error
    looks like and is not something any amount of internal consistency in either
    construction would have revealed.

    The reason this gets its own reduction, rather than being a subtraction the
    reader can do from the per-node tables: on this ring the two terms are
    nearly equal, so the difference is a small residue of two large numbers and
    its error bar is NOT either term's error bar.  Two things follow, and both
    are reported here beside every difference rather than assumed:

      `ratio`  |h_gen| / max(|h(drain)|, |h(source)|) -- how much cancellation
               there is.  This is the factor by which the precision the pipeline
               needs exceeds the precision the per-node tables demonstrate.
      `floor`  the difference's own numerical floor, propagated from the two
               settled-tail spreads (added, not RSS'd: they are not independent
               -- both copies are integrated on the same timestep sequence, so
               a worst-case sum is the honest bound).  `snr` is |h_gen| / floor,
               and a difference whose `snr` approaches 1 is not a measurement.

    Both terms must come from the SAME deck for this to mean anything -- see
    `isf_deck.py`'s one-deck-many-copies note.  Differencing across two decks
    reintroduces exactly the independent-timestep-grid error that construction
    exists to cancel, and at this cancellation ratio that error is no longer
    negligible.
    """
    by = {}
    for r in rows:
        by[(r["node"], round(r["phase_cycles"], 9))] = r
    out = []
    for drain, source in pairs:
        for node, ph in sorted(by):
            if node != drain:
                continue
            rs = by.get((source, ph))
            if rs is None:
                continue
            rd = by[(drain, ph)]
            if rd["dq_C"] != rs["dq_C"]:
                raise ValueError(
                    f"{drain}/{source} at phase {ph}: differenced ISFs must be "
                    f"measured at the same injected charge, got {rd['dq_C']} and "
                    f"{rs['dq_C']}"
                )
            gen = rs["h_rad_per_C"] - rd["h_rad_per_C"]
            common = max(abs(rd["h_rad_per_C"]), abs(rs["h_rad_per_C"]))
            floor = (
                2.0
                * math.pi
                * (rd["dt_spread_s"] + rs["dt_spread_s"])
                / (period * rd["dq_C"])
            )
            out.append(
                {
                    "pair": f"{drain}-{source}",
                    "phase_cycles": ph,
                    "dq_C": rd["dq_C"],
                    "h_drain_rad_per_C": rd["h_rad_per_C"],
                    "h_source_rad_per_C": rs["h_rad_per_C"],
                    "h_gen_rad_per_C": gen,
                    "cancellation_ratio": (gen / common) if common else float("nan"),
                    "floor_rad_per_C": floor,
                    "snr": (abs(gen) / floor) if floor else float("inf"),
                }
            )
    return out


def crosscheck_pairs(rows, differences, pairs):
    """Directly-injected `h_gen` against the same thing built by subtraction.

    By linearity these must be equal: a current source between drain and source
    is exactly the superposition of `-dq` into the drain and `+dq` into the
    source, which is why `node_differences` defines `h_gen = h(source) -
    h(drain)`.  They are measured here by two different stimuli at two different
    injected charges on one timestep grid, so agreement is evidence about the
    DECK -- that the pair element really landed on the two nets it names, and
    that neither measurement is dominated by its own numerics -- in a way no
    internal consistency check on either construction alone can be.

    Disagreement is informative rather than fatal and is reported, not raised:
    the expected residual is the finite-amplitude error at two different charges
    plus the two numerical floors, and quantifying it is the point.  Because the
    signed comparison is the one with teeth -- it is how the sign error this
    convention now pins was found -- both the signed disagreement and the
    magnitude-only disagreement are reported, and a reader who sees ~200 % in the
    first with ~0 % in the second is looking at a sign flip, not a bad
    measurement.
    """
    direct = {}
    for r in rows:
        if "-" in str(r["node"]):
            direct[(r["node"], round(r["phase_cycles"], 9))] = r
    out = []
    for d in differences:
        key = (d["pair"], round(d["phase_cycles"], 9))
        r = direct.get(key)
        if r is None:
            continue
        subtracted = d["h_gen_rad_per_C"]
        # The pair element drives current OUT of the drain and INTO the source --
        # i.e. it IS the generator -- so its own `h` is already `h_gen` and is
        # compared with h(source) - h(drain) with no sign flip anywhere.
        got = r["h_rad_per_C"]
        denom = max(abs(got), abs(subtracted))
        out.append(
            {
                "pair": d["pair"],
                "phase_cycles": d["phase_cycles"],
                "h_direct_rad_per_C": got,
                "h_direct_dq_C": r["dq_C"],
                "h_direct_dt_s": r["dt_s"],
                "h_direct_spread_s": r["dt_spread_s"],
                "h_subtracted_rad_per_C": subtracted,
                "h_subtracted_dq_C": d.get("dq_C"),
                "rel_disagreement": (
                    abs(got - subtracted) / denom if denom else float("nan")
                ),
                "rel_disagreement_magnitude": (
                    abs(abs(got) - abs(subtracted)) / denom
                    if denom
                    else float("nan")
                ),
            }
        )
    return out


def reduce_run(datfile, ncopy, injections, threshold, settle_cycles=2):
    """One deck's worth of `h(x)`.

    `injections` maps copy index -> dict with at least `t_inject`, `dq`,
    `phase` (the injection phase in cycles, 0..1), `node`, `stage`.
    """
    t, cols = read_wrdata(datfile, ncopy)
    cross = [crossings(t, c, threshold) for c in cols]
    ref = cross[0]
    period = mean_period(ref)
    rows = []
    for copy in sorted(injections):
        inj = injections[copy]
        dts = shift_sequence(ref, cross[copy])
        dt, spread, n, drift = settled_shift(
            dts, ref, inj["t_inject"], settle_cycles
        )
        rows.append(
            {
                "copy": copy,
                "node": inj["node"],
                "stage": inj["stage"],
                "phase_cycles": inj["phase"],
                "dq_C": inj["dq"],
                "t_inject_s": inj["t_inject"],
                "dt_s": dt,
                "dt_spread_s": spread,
                "dt_drift_s_per_cycle": drift,
                "n_settled": n,
                "h_rad_per_C": sensitivity(dt, period, inj["dq"]),
            }
        )
    return {
        "period_s": period,
        "f0_Hz": 1.0 / period,
        "n_ref_crossings": len(ref),
        "rows": rows,
    }
