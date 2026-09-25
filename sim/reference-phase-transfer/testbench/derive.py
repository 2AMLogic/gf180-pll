"""reference-phase-transfer reductions: the measured REF-to-output transfer.

The deck applies one KNOWN reference phase step, `dphi`, at `tphase`, and
`.measure`s the closed loop's own REF-vs-FB static phase error at three
instants: `ta` (before the step), `tc` (partway through the post-step
settling window) and `tb` (after the loop has had several loop time
constants to re-settle). Everything here is arithmetic on those three
numbers plus the manifest's own `dphi`/`fref`/`nratio` -- there is no
spectral or statistical reduction, on purpose (#509's recommended first
increment is a deterministic transient, not a noise methodology).

    phi_shift    = unwrap(phi_post - phi_pre)   -- how much the loop's own
                   static phase error moved across the step.  Zero means the
                   loop re-tracked the ENTIRE injected step; a residual R
                   means it tracked only `dphi - R` of it.
    settle_resid = unwrap(phi_post - phi_mid)   -- is the run actually
                   settled by `tb`, or still moving between `tc` and `tb`?
                   Large here means the record's own window was too short,
                   not that the loop's transfer is bad.
    tracking_ratio = 1 + phi_shift / dphi       -- the fraction of `dphi`
                   FB actually tracked; 1.0 is ideal (full unity tracking).

The OUTPUT's phase moves by exactly N times whatever FB moved, because CLK =
N*FB is an exact digital divide ratio, not a statistical relationship -- so
the measured closed-loop REF-to-output transfer is

    measured_gain     = nratio * tracking_ratio
    measured_gain_db  = 20*log10(|measured_gain|)

compared directly against the spec's own

    target_gain_db    = 20*log10(nratio)

`transfer_error_db` is the difference the record's Result table and
spec/pll.md's decision record actually read.
"""

from __future__ import annotations

import math

#: Reference period is not swept independently of fref in this campaign, so
#: it is always derivable from the point's own `fref` -- never assumed to be
#: any one campaign-wide constant, unlike a fixed-frequency campaign's own
#: differencing spans (sim/pfd-deadzone) might be.


def _unwrap(delta_s: float, tref_s: float, fref_hz: float) -> float:
    """Unwrap a REF-period-scale phase delta into (-tref/2, +tref/2].

    Identical arithmetic to sim/reference-spur's `dphi` raw_measures entry
    (`(phi_b-phi_a) - (1/fref)*floor((phi_b-phi_a)*fref + 0.5)`), reused here
    in Python because this campaign differences THREE instants, not two, and
    a `.measure param=` expression cannot share a sub-expression across two
    outputs.
    """
    return delta_s - tref_s * math.floor(delta_s * fref_hz + 0.5)


def derive_point(point):
    phi_pre = point.get("phi_pre")
    phi_mid = point.get("phi_mid")
    phi_post = point.get("phi_post")
    if phi_pre is None or phi_mid is None or phi_post is None:
        # One of the three .measure cards did not fire -- most likely the
        # loop never locked at this corner.  Reporting nothing here (rather
        # than a coerced zero) is what lets a downstream "not measured"
        # verdict say so honestly.
        return {}

    fref = float(point.params.get("fref"))
    dphi = float(point.params.get("dphi"))
    nratio = float(point.params.get("nratio"))
    if fref <= 0 or dphi == 0:
        return {}
    tref = 1.0 / fref

    phi_shift = _unwrap(phi_post - phi_pre, tref, fref)
    settle_resid = _unwrap(phi_post - phi_mid, tref, fref)
    tracking_ratio = 1.0 + phi_shift / dphi
    measured_gain = nratio * tracking_ratio

    out = {
        "phi_shift": phi_shift,
        "settle_resid": settle_resid,
        "tracking_ratio": tracking_ratio,
        "measured_gain": measured_gain,
        "target_gain_db": 20.0 * math.log10(nratio),
    }
    if measured_gain != 0:
        measured_gain_db = 20.0 * math.log10(abs(measured_gain))
        out["measured_gain_db"] = measured_gain_db
        out["transfer_error_db"] = measured_gain_db - out["target_gain_db"]
    return out
