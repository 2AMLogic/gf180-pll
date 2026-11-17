"""output-driver reduction: duty cycle and 10-90 % edge times from independently-timed crossings.

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

`trise`/`tfall` get the same treatment (issue #969): a `trig`/`targ` 10-90 %
pair latched different edges at 5 of 90 points when `tsettle` fell inside an
edge. They are now reduced from eight independent threshold crossings, pairing
a 10 % and a 90 % crossing only when the 50 % crossing of that direction lies
between them, i.e. only when both belong to one edge.
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
    out = {"thigh": thigh, "duty_pct": 100.0 * thigh / tperiod}

    trise = _edge_time(point, "t_r10_", "t_r90_", (t_r1, t_r2), (t_f1, t_f2))
    if trise is not None:
        out["trise"] = trise
    tfall = _edge_time(point, "t_f90_", "t_f10_", (t_f1, t_f2), (t_r1, t_r2))
    if tfall is not None:
        out["tfall"] = tfall
    return out


def _edge_time(point, first_prefix, second_prefix, mid_crossings, opposite_crossings):
    """10-90 % (or 90-10 %) transition time of one edge, or None.

    `first_prefix`/`second_prefix` name the two threshold crossings in the
    order the edge passes them; `mid_crossings` are the 50 % crossings of the
    same direction. A (first, second) pair is one edge iff
    `first < mid < second` for some 50 % crossing and no opposite-direction
    50 % crossing lies inside the pair; the earliest such pair wins.
    """
    firsts = [point.get(f"{first_prefix}{k}") for k in (1, 2)]
    seconds = [point.get(f"{second_prefix}{k}") for k in (1, 2)]
    mids = [m for m in mid_crossings if m is not None]
    opps = [m for m in opposite_crossings if m is not None]
    best = None
    for a in firsts:
        for b in seconds:
            if a is None or b is None:
                continue
            if (
                any(a < m < b for m in mids)
                and not any(a < o < b for o in opps)
                and (best is None or a < best[0])
            ):
                best = (a, b)
    return None if best is None else best[1] - best[0]
