"""gf180-pll :: lock-window-sizing :: the reduction this campaign claims.

Two hooks:

``derive_point``
    ``repl_err_pct`` -- at the ``w08`` sizing point ONLY, the percentage
    disagreement between the parameterised replica (``twin_r``) and the
    committed ``delaywin_3v3`` control (``ctl_r``). At ``w08`` the replica is
    the same circuit as the control, so this column is the campaign's own
    proof that the swept device really is a faithful stand-in for the drawn
    cell -- checked (``|repl_err_pct| <= 1``) rather than asserted in prose.
    At every other sizing the replica differs by design, so the measure is
    deliberately not produced and is recorded ``not measured``.

``derive_tables``
    ``window_sizing`` -- one row per sizing point, reducing the 117 PVT points
    at that sizing to what the decision actually turns on: the MINIMUM window
    over the grid (the corner that decides whether a part meeting the ratified
    Lock criterion can fail to assert) and the MAXIMUM (the corner that
    decides how far outside the criterion the flag can still assert), their
    ratio, and the verdict against the two-sided band.

The band, restated here because the verdict column is meaningless without it:

    WIN_LO_NS  spec/pll.md's ratified Lock criterion, "the static phase error
               at the PFD inputs is <= 1 ns". A window narrower than this at
               ANY corner can refuse to assert on a part that meets the
               criterion -- a false negative.
    WIN_HI_NS  twice that. A window wider than this lets the flag assert on a
               part more than 2x outside the criterion -- a false positive,
               and the unsafe direction for a consumer gating logic on lock
               (design/lock_detector.sch's own "slow to rise, quick to fall"
               note is about exactly that asymmetry of consequence).

Neither number is a new spec value invented by this reduction: the lower edge
IS the ratified criterion and the upper edge is a stated multiple of it. The
decision record this campaign backs is where they are argued.

Note the arithmetic consequence the table's ``ratio`` column exists to make
visible: the band is satisfiable at all only if the window's own PVT spread
(max/min) is at or under WIN_HI_NS / WIN_LO_NS = 2.0. That ratio is a
property of the delay chain's PVT sensitivity, NOT of its sizing -- scaling
every load by the same factor moves both edges together. A sizing ladder can
therefore re-CENTRE the window but can barely narrow its spread, which is why
the ratio column is reported per sizing: if it does not fall with kwc, no
amount of widening buys margin against the band, and the fix has to come from
somewhere other than geometry. (Measured on this ladder it falls only from
1.928 at the as-drawn W = 8 um to 1.907 at W = 24 um -- a 3x sizing change
buying 1 % of spread, which is the quantitative form of "geometry re-centres,
it does not narrow".)
"""

from __future__ import annotations

from harness.derived import DerivedTable

#: spec/pll.md's ratified Lock criterion, in nanoseconds.
WIN_LO_NS = 1.0
#: Twice the criterion -- the false-positive reach the flag is allowed.
WIN_HI_NS = 2.0

#: spec/pll.md row 16 / target T1, in nanoseconds: "assert window >= 2.5 ns of
#: phase error at the PFD inputs". Reported per sizing ALONGSIDE the band above
#: -- not as a second verdict, but because the two cannot both be satisfied and
#: the evidence should show that rather than the decision record asserting it.
#: T1 is a MINIMUM on the window; the band's upper edge is a MAXIMUM; the
#: chain's own PVT spread (ratio_max_over_min, ~1.9) means a sizing whose
#: minimum clears 2.5 ns has a maximum near 4.8 ns, i.e. the flag would assert
#: on a part ~4.8x outside the ratified Lock criterion.
T1_MIN_NS = 2.5

#: The sizing point at which the replica and the committed cell are the same
#: circuit, and therefore the only one where disagreement is a defect.
CONTROL_POINT = "w08"


def derive_point(point):
    if point.axes.get("wc") != CONTROL_POINT:
        return {}
    replica = point.get("twin_r")
    control = point.get("ctl_r")
    if replica is None or control is None or control == 0:
        return {}
    return {"repl_err_pct": 100.0 * (replica - control) / control}


def _fmt(value):
    return "" if value is None else f"{value:.4g}"


def derive_tables(run):
    by_sizing: dict[str, list] = {}
    for point in run.points:
        sizing = point.axes.get("wc")
        if sizing is None:
            continue
        by_sizing.setdefault(sizing, []).append(point)

    rows = []
    for sizing in sorted(by_sizing):
        points = by_sizing[sizing]
        measured = [
            (point.get("twin_r"), point) for point in points if point.get("twin_r")
        ]
        if not measured:
            continue
        kwc = points[0].params.get("kwc", "")
        lo_value, lo_point = min(measured, key=lambda item: item[0])
        hi_value, hi_point = max(measured, key=lambda item: item[0])
        lo_ns = lo_value * 1e9
        hi_ns = hi_value * 1e9
        ratio = hi_ns / lo_ns if lo_ns else None

        meets_lo = lo_ns >= WIN_LO_NS
        meets_hi = hi_ns <= WIN_HI_NS
        if meets_lo and meets_hi:
            verdict = "in-band"
        elif not meets_lo and not meets_hi:
            verdict = "both-edges-missed"
        elif not meets_lo:
            verdict = "below-lo"
        else:
            verdict = "above-hi"

        # How much room is left before the nearer edge is crossed, as a
        # percentage of the band. Negative means the edge is already crossed.
        margin_lo_pct = 100.0 * (lo_ns - WIN_LO_NS) / WIN_LO_NS
        margin_hi_pct = 100.0 * (WIN_HI_NS - hi_ns) / WIN_HI_NS

        rows.append(
            (
                sizing,
                kwc,
                len(measured),
                _fmt(lo_ns),
                lo_point.corner_id.rsplit("_", 1)[0],
                _fmt(hi_ns),
                hi_point.corner_id.rsplit("_", 1)[0],
                _fmt(ratio),
                _fmt(margin_lo_pct),
                _fmt(margin_hi_pct),
                verdict,
                "yes" if lo_ns >= T1_MIN_NS else "no",
                _fmt(hi_ns / WIN_LO_NS),
            )
        )

    return [
        DerivedTable(
            name="window_sizing",
            description=(
                "per delaywin_3v3 MOS-cap sizing: the comparator window t_win "
                "(twin_r) reduced over the 117-point PVT grid to its extremes, "
                f"against the two-sided band [{WIN_LO_NS:g}, {WIN_HI_NS:g}] ns "
                "-- lower edge = spec/pll.md's ratified Lock criterion, upper "
                "edge = 2x it"
            ),
            columns=(
                "sizing",
                "kwc",
                "n_points",
                "twin_min_ns",
                "twin_min_corner",
                "twin_max_ns",
                "twin_max_corner",
                "ratio_max_over_min",
                "margin_to_lo_pct",
                "margin_to_hi_pct",
                "verdict",
                "meets_t1_2p5ns",
                "twin_max_over_lock_criterion",
            ),
            rows=tuple(rows),
            notes=(
                "verdict 'in-band' means BOTH edges hold at every one of the "
                "grid's points simultaneously, not that the nominal value sits "
                "between them.",
                "margin_to_lo_pct is (twin_min - lo)/lo; margin_to_hi_pct is "
                "(hi - twin_max)/hi. A negative value means that edge is "
                "already crossed.",
                "ratio_max_over_min is the window's own PVT spread. It is a "
                "property of the delay chain, not of its sizing, and the band "
                "is satisfiable at all only while it stays at or under "
                f"{WIN_HI_NS / WIN_LO_NS:g}.",
                f"meets_t1_2p5ns is spec/pll.md row 16's target T1 ("
                f"twin_min >= {T1_MIN_NS:g} ns) evaluated on the same data. It "
                "is reported, not used as the verdict: T1 is a minimum and the "
                "band's upper edge is a maximum, so at this chain's PVT spread "
                "the two cannot both hold.",
                "twin_max_over_lock_criterion is twin_max / the ratified Lock "
                f"criterion ({WIN_LO_NS:g} ns) -- how far outside the criterion "
                "a part can be and still have the flag assert, at the worst "
                "corner. It is the cost column for T1: the sizing that meets "
                "T1 is the sizing that lets the flag assert furthest outside "
                "the criterion it is supposed to observe.",
            ),
        )
    ]
