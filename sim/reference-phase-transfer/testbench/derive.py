"""reference-phase-transfer reductions: the measured REF-to-output transfer.

Each PVT point runs TWO decks (``tb.json``'s ``phases``), identical in every
respect except the step selector ``apply``:

    ctl   apply = 0   no step is applied -- the CONTROL run
    stp   apply = 1   the known ``dphi`` reference phase step is applied

Both ``.measure`` the loop's own REF-vs-FB static phase error

    phi(t) = t(first FB rising edge after t) - t(first REF rising edge after t)

at four instants: ``ta`` (before the step), ``tfast`` (0.3-1.2 loop time
constants after it), ``tc`` and ``tb`` (15-60 time constants after it, 3 us
apart). ``derive_point`` runs once per PVT point, after both phases, so it sees
all eight readings in one place -- which is the whole reason this campaign uses
``phases`` rather than a sweep axis.

WHY DIFFERENTIAL, AND WHAT IT FIXES
-----------------------------------
This campaign's first record, ``20260925-073001-ed38ff1``, differenced phi AFTER
the step against phi BEFORE it, inside ONE run. That is confounded here: at this
release point the loop's static phase error is still winding at ~1e-4 fractional
frequency error 9.2 us in (0.12-0.19 ns per microsecond, monotonic at every
corner, consistent with the +72 ppm the same points measured on ``ffb``), so the
baseline moved 0.4-1.4 ns across the 6.4 us between readings -- against a 1 ns
step. Subtracting a drifting baseline from a step response measures their sum,
and nothing in that arithmetic separates them.

The control run removes the drift instead of bounding it. The two decks are
bit-identical up to ``tphase``, so

    d(t) = unwrap(phi_stp(t) - phi_ctl(t))

is the step response alone: 0 before the step, about -dphi immediately after it
(REF's edges moved by +dphi and FB's have not moved yet), returning to 0 as the
loop re-tracks.

WHAT IS REPORTED
----------------
    pair_resid   = d(ta)              the two decks are the same run before
                   the step, so this is a VALIDITY check on the pairing rather
                   than a physical quantity -- and its size IS the
                   differential's own solver-noise floor, which is not zero
                   (the stepped deck's `refb` source puts a breakpoint where
                   the control deck has none).  Checked at +/-50 ps, 5% of
                   dphi; DR-027 records why that band and not the +/-1 ps a
                   bit-identical pairing would imply.
    drift_ctl    = unwrap(cphi_post - cphi_pre)
                   the baseline drift the control run alone saw, reported so
                   the record states the size of what the pairing cancelled.
    d_fast       = d(tfast)           the step response above the loop bandwidth
    d_mid        = d(tc)              the settled reading, 3 us after the step
    phi_shift    = d(tb)              the settled reading this record's number
                   is taken from, 6 us after the step
    settle_resid = d(tb) - d(tc)      the run's own proof it waited long enough

    tracking_ratio = 1 + phi_shift / dphi
                   the fraction of dphi FB actually tracked; 1.0 is full
                   (unity) tracking, 0.0 is none.

The OUTPUT's phase moves by exactly N times whatever FB moved, because CLK =
N*FB is an exact digital divide ratio, not a statistical relationship -- so the
measured closed-loop REF-to-output transfer is

    measured_gain     = nratio * tracking_ratio
    measured_gain_db  = 20*log10(|measured_gain|)

compared directly against the spec's own ``target_gain_db`` = 20*log10(nratio),
the difference being ``transfer_error_db``.

The same arithmetic at ``tfast`` gives ``fast_gain`` / ``fast_gain_db``: the
transfer to a reference perturbation the loop cannot follow yet.
``fast_rejection_db`` = ``fast_gain_db`` - ``measured_gain_db`` is how far below
the in-band transfer that point sits -- the roll-off ABOVE the loop bandwidth
spec/pll.md's derivation asserts alongside the 20*log10(N) figure, measured in
the time domain at one frequency rather than swept.
"""

from __future__ import annotations

import math

#: `measured_gain_db` for a tracking ratio of exactly zero is -inf, which is a
#: true statement about the transfer and an unusable one in a CSV column. A
#: gain this far below unity is reported as "no measurable transfer" by omitting
#: the dB columns -- the same abstention `derive_point` makes when a `.measure`
#: did not fire, and for the same reason: a coerced number reads as evidence.
GAIN_FLOOR = 1e-9


def _unwrap(delta_s: float, tref_s: float, fref_hz: float) -> float:
    """Unwrap a REF-period-scale phase delta into (-tref/2, +tref/2].

    Identical arithmetic to sim/reference-spur's `dphi` raw_measures entry
    (`(phi_b-phi_a) - (1/fref)*floor((phi_b-phi_a)*fref + 0.5)`), reused here
    in Python because this campaign differences four instants across two decks,
    and a `.measure param=` expression cannot share a sub-expression across two
    outputs -- nor reach the other phase's measurements at all.
    """
    return delta_s - tref_s * math.floor(delta_s * fref_hz + 0.5)


def _gain_db(nratio: float, ratio: float) -> float | None:
    """20*log10(|nratio * ratio|), or None below the reporting floor."""
    gain = abs(nratio * ratio)
    if gain < GAIN_FLOOR:
        return None
    return 20.0 * math.log10(gain)


def derive_point(point):
    names = (
        "cphi_pre",
        "cphi_fast",
        "cphi_mid",
        "cphi_post",
        "sphi_pre",
        "sphi_fast",
        "sphi_mid",
        "sphi_post",
    )
    read = {n: point.get(n) for n in names}
    if any(v is None for v in read.values()):
        # At least one .measure card did not fire in one of the two decks, so
        # there is no pair to difference. Reporting nothing (rather than a
        # coerced zero) is what lets a downstream "not measured" verdict say so
        # honestly -- and a half-measured pair is not a weaker measurement of
        # the transfer, it is not a measurement of it.
        return {}

    fref = float(point.params.get("fref"))
    dphi = float(point.params.get("dphi"))
    nratio = float(point.params.get("nratio"))
    if fref <= 0 or dphi == 0:
        return {}
    tref = 1.0 / fref

    def d(instant: str) -> float:
        return _unwrap(read["sphi_" + instant] - read["cphi_" + instant], tref, fref)

    pair_resid = d("pre")
    d_fast = d("fast")
    d_mid = d("mid")
    phi_shift = d("post")

    tracking_ratio = 1.0 + phi_shift / dphi
    fast_ratio = 1.0 + d_fast / dphi

    out = {
        "pair_resid": pair_resid,
        "drift_ctl": _unwrap(read["cphi_post"] - read["cphi_pre"], tref, fref),
        "d_fast": d_fast,
        "d_mid": d_mid,
        "phi_shift": phi_shift,
        "settle_resid": phi_shift - d_mid,
        "tracking_ratio": tracking_ratio,
        "measured_gain": nratio * tracking_ratio,
        "target_gain_db": 20.0 * math.log10(nratio),
        "fast_gain": nratio * fast_ratio,
    }

    measured_gain_db = _gain_db(nratio, tracking_ratio)
    if measured_gain_db is not None:
        out["measured_gain_db"] = measured_gain_db
        out["transfer_error_db"] = measured_gain_db - out["target_gain_db"]

    fast_gain_db = _gain_db(nratio, fast_ratio)
    if fast_gain_db is not None:
        out["fast_gain_db"] = fast_gain_db
        if measured_gain_db is not None:
            out["fast_rejection_db"] = fast_gain_db - measured_gain_db

    return out
