"""output-driver reduction: duty cycle from a pair of independently-timed edges.

See tb.json's methodology field ("MEASUREMENT DEFINITIONS") for the full
story. In short: ngspice's `trig ... targ ...` measure clauses each search
independently from their own `td`, with **no** guarantee that the `targ`
crossing occurs after the `trig` crossing -- confirmed empirically while
developing this manifest (`hi`/`typical`/27 C/3.30 V measured `thigh` =
-1.33 ns, i.e. the deck's `fall=1` crossing landed 1.33 ns *before* its
`rise=1` crossing, both legally satisfying the same `td='tsettle'` gate). A
same-signal, opposite-slope pulse-width measurement is exactly the shape that
can go wrong this way, so duty cycle is not measured directly in SPICE here.

Instead tb.json's `raw_measures` records four unambiguous absolute crossing
times -- `t_r1`/`t_r2` (first/second RISING half-supply crossings after
`tsettle`, guaranteed `t_r2 > t_r1` because `rise=2` cannot occur before
`rise=1`) and `t_f1`/`t_f2` (same, falling) -- and this module picks whichever
of `t_f1`/`t_f2` actually falls inside the `[t_r1, t_r2]` window, i.e. the one
fall that is genuinely between this period's two rising edges, before
computing the high time and the duty cycle from it. That is correct
regardless of which the deck's own signal history happens to expose first.
"""

from __future__ import annotations


def derive_point(point):
    """`thigh` and `duty_pct` for one (corner, edge) point.

    Returns {} (not measured) if any of the four crossing times is missing,
    or if neither `t_f1` nor `t_f2` lands strictly inside `[t_r1, t_r2]` --
    which would mean the deck's measurement window did not actually capture
    a whole period, a real failure this record should not paper over with a
    fabricated duty cycle.
    """
    t_r1 = point.get("t_r1")
    t_r2 = point.get("t_r2")
    t_f1 = point.get("t_f1")
    t_f2 = point.get("t_f2")
    if t_r1 is None or t_r2 is None or t_r2 <= t_r1:
        return {}

    t_f = None
    if t_f1 is not None and t_r1 < t_f1 < t_r2:
        t_f = t_f1
    elif t_f2 is not None and t_r1 < t_f2 < t_r2:
        t_f = t_f2
    if t_f is None:
        return {}

    thigh = t_f - t_r1
    tperiod = t_r2 - t_r1
    return {"thigh": thigh, "duty_pct": 100.0 * thigh / tperiod}
