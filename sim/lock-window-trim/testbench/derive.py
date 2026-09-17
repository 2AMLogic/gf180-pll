"""gf180-pll :: lock-window-trim :: the reduction this campaign claims.

Two hooks.

``derive_point``
    ``repl_err_pct`` -- the percentage disagreement between the parameterised
    replica (``twin_r``) and the committed ``delaywin_3v3`` control
    (``ctl_r``), at every point. Unlike ``sim/lock-window-sizing``'s version of
    this column, which was only meaningful at the one sizing where the replica
    and the drawn cell coincided, here the replica is parameterised at the
    DRAWN widths, so the two are the same circuit at every code and every
    corner -- and a disagreement anywhere is a defect in one of them.
    Checked (``|repl_err_pct| <= 1``) rather than asserted in prose.

``derive_tables``
    ``code_ladder`` -- one row per trim code, reducing that code's 117 PVT
    points to the extremes of the window. This is the untrimmed view of the
    data, and it is reported because it is the honest baseline: no single code
    holds the band at every corner, for exactly the reason
    ``sim/lock-window-sizing`` already measured (the window's PVT spread is
    wider than the band), and the table shows that rather than the record
    asserting it.

    ``bundle_trim`` -- the campaign's actual claim: one row per PROCESS
    BUNDLE, giving the code that bundle should be trimmed to, the window's
    within-bundle voltage/temperature envelope at that code, and the verdict
    against the band. The final row re-joins all 13 bundles at their own codes
    into the TRIMMED POPULATION -- the spread of that row, not of any single
    bundle, is what DR-013 Decision 4's <= 1.65x target is evaluated against.

Why per bundle. A trim is a per-part setting: a part is one process bundle, is
measured once at test, is given one code, and thereafter only has to survive
its own voltage and temperature range. Reducing the grid to a single
"min and max over everything" -- the right reduction for a cell with no trim,
and the one ``sim/lock-window-sizing`` used -- would charge the trimmed cell
for a process spread the trim exists to remove, and would therefore measure
something no part ever experiences.

The band, restated here because the verdict column is meaningless without it:

    WIN_LO_NS  spec/pll.md's ratified Lock criterion, "the static phase error
               at the PFD inputs is <= 1 ns". A window narrower than this at
               ANY corner of a trimmed part can refuse to assert on a part
               that meets the criterion -- a false negative.
    WIN_HI_NS  twice that. A window wider than this lets the flag assert on a
               part more than 2x outside the criterion -- a false positive,
               and the unsafe direction for a consumer gating logic on lock.
    SPREAD_TARGET  DR-013 Decision 4's <= 1.65x. Stricter than the band's own
               arithmetic width (2.0x), deliberately: a population whose
               spread exactly equalled the band would meet it with zero margin
               at both edges at once.

Code-selection rule. For each bundle the chosen code is the one whose
within-bundle geometric centre ``sqrt(min*max)`` is closest, in log terms, to
``sqrt(WIN_LO_NS*WIN_HI_NS)`` -- the geometric centre of the band. The
objective is geometric rather than arithmetic because the quantity's spread is
multiplicative: centring geometrically is what equalises the margin to the two
edges. A bundle for which several codes tie is not hidden -- the full per-code,
per-bundle data is in ``code_ladder``'s companion CSV and in the record's own
per-point table.
"""

from __future__ import annotations

import math

from harness.derived import DerivedTable

#: spec/pll.md's ratified Lock criterion, in nanoseconds.
WIN_LO_NS = 1.0
#: Twice the criterion -- the false-positive reach the flag is allowed.
WIN_HI_NS = 2.0
#: DR-013 Decision 4's target on the observable window's PVT spread.
SPREAD_TARGET = 1.65

#: The geometric centre of the band -- the placement that equalises the
#: multiplicative margin to both edges.
BAND_CENTRE_NS = math.sqrt(WIN_LO_NS * WIN_HI_NS)


def derive_point(point):
    replica = point.get("twin_r")
    control = point.get("ctl_r")
    if replica is None or control is None or control == 0:
        return {}
    return {"repl_err_pct": 100.0 * (replica - control) / control}


def _fmt(value):
    return "" if value is None else f"{value:.4g}"


def _code_of(point):
    """The numeric trim code of a point, from its ``code`` axis id (``c5``)."""
    axis = point.axes.get("code")
    if axis is None or not axis.startswith("c"):
        return None
    try:
        return int(axis[1:])
    except ValueError:
        return None


def _envelope(points):
    """``(min_ns, min_corner, max_ns, max_corner)`` of ``ctl_r`` over points."""
    measured = [(p.get("ctl_r"), p) for p in points if p.get("ctl_r")]
    if not measured:
        return None
    lo_value, lo_point = min(measured, key=lambda item: item[0])
    hi_value, hi_point = max(measured, key=lambda item: item[0])
    return (
        lo_value * 1e9,
        lo_point.corner_id.rsplit("_", 1)[0],
        hi_value * 1e9,
        hi_point.corner_id.rsplit("_", 1)[0],
        len(measured),
    )


def _verdict(lo_ns, hi_ns):
    meets_lo = lo_ns >= WIN_LO_NS
    meets_hi = hi_ns <= WIN_HI_NS
    if meets_lo and meets_hi:
        return "in-band"
    if not meets_lo and not meets_hi:
        return "both-edges-missed"
    if not meets_lo:
        return "below-lo"
    return "above-hi"


def _row(label, code, env):
    lo_ns, lo_corner, hi_ns, hi_corner, n = env
    ratio = hi_ns / lo_ns if lo_ns else None
    centre = math.sqrt(lo_ns * hi_ns)
    return (
        label,
        "" if code is None else str(code),
        n,
        _fmt(lo_ns),
        lo_corner,
        _fmt(hi_ns),
        hi_corner,
        _fmt(ratio),
        _fmt(centre),
        _fmt(100.0 * (lo_ns - WIN_LO_NS) / WIN_LO_NS),
        _fmt(100.0 * (WIN_HI_NS - hi_ns) / WIN_HI_NS),
        _verdict(lo_ns, hi_ns),
        "yes" if ratio is not None and ratio <= SPREAD_TARGET else "no",
    )


_COLUMNS = (
    "bundle",
    "code",
    "n_points",
    "twin_min_ns",
    "twin_min_corner",
    "twin_max_ns",
    "twin_max_corner",
    "ratio_max_over_min",
    "geo_centre_ns",
    "margin_to_lo_pct",
    "margin_to_hi_pct",
    "band_verdict",
    "meets_spread_target",
)


def derive_tables(run):
    by_code: dict[int, list] = {}
    by_bundle_code: dict[tuple[str, int], list] = {}
    for point in run.points:
        code = _code_of(point)
        if code is None:
            continue
        by_code.setdefault(code, []).append(point)
        by_bundle_code.setdefault((point.corner, code), []).append(point)

    ladder_rows = []
    for code in sorted(by_code):
        env = _envelope(by_code[code])
        if env is None:
            continue
        ladder_rows.append(_row("ALL (untrimmed)", code, env))

    bundles = sorted({bundle for bundle, _ in by_bundle_code})
    trim_rows = []
    chosen_points = []
    for bundle in bundles:
        best = None
        for code in sorted(by_code):
            points = by_bundle_code.get((bundle, code))
            if not points:
                continue
            env = _envelope(points)
            if env is None:
                continue
            lo_ns, _, hi_ns, _, _ = env
            centre = math.sqrt(lo_ns * hi_ns)
            # Distance in LOG space: the quantity's spread is multiplicative,
            # so "closest to the band's centre" has to be measured the same
            # way or a wide-but-low code can beat a well-centred one.
            distance = abs(math.log(centre / BAND_CENTRE_NS))
            if best is None or distance < best[0]:
                best = (distance, code, env, points)
        if best is None:
            continue
        _, code, env, points = best
        trim_rows.append(_row(bundle, code, env))
        chosen_points.extend(points)

    population = _envelope(chosen_points)
    if population is not None:
        trim_rows.append(_row("ALL (trimmed population)", None, population))

    return [
        DerivedTable(
            name="code_ladder",
            description=(
                "per trim code: the window t_win (ctl_r, the committed cell) "
                "reduced over the full 117-point PVT grid to its extremes, "
                f"against the two-sided band [{WIN_LO_NS:g}, {WIN_HI_NS:g}] ns. "
                "This is the UNTRIMMED view -- it charges one code with the "
                "whole process spread, which is what a part without a trim "
                "experiences and what the trim exists to remove"
            ),
            columns=_COLUMNS,
            rows=tuple(ladder_rows),
            notes=(
                "No single code is expected to be in-band at every corner: "
                "the untrimmed window's PVT spread (~1.93x, "
                "sim/lock-window-sizing/records/20260915-202802-79c0cee.md) is "
                f"wider than the band itself ({WIN_HI_NS / WIN_LO_NS:g}x). "
                "This table is reported so that fact is visible in this "
                "campaign's own data rather than carried over as an assertion.",
                "The ladder's floor (code 0) and ceiling (code 15) are what the "
                "trim range actually is, including the residual capacitance of "
                "a disabled segment -- the number that could not be computed "
                "from the drawn widths and is the reason this campaign exists "
                "as a measurement.",
            ),
        ),
        DerivedTable(
            name="bundle_trim",
            description=(
                "the claim: per process bundle, the trim code whose "
                "within-bundle voltage/temperature envelope is best centred in "
                f"the band [{WIN_LO_NS:g}, {WIN_HI_NS:g}] ns, and that "
                "envelope. The final row re-joins every bundle at its own code "
                "into the trimmed population, whose spread is what DR-013 "
                f"Decision 4's <= {SPREAD_TARGET:g}x target is evaluated against"
            ),
            columns=_COLUMNS,
            rows=tuple(trim_rows),
            notes=(
                "A part is one process bundle and is trimmed once at test, so "
                "the per-bundle rows are what a single part sees over its own "
                "voltage and temperature range. The trimmed-population row is "
                "what the whole shipped population spans once every part "
                "carries its own code -- bundle-to-bundle residual (the trim "
                "step's quantization) plus the worst bundle's own V/T spread.",
                "The chosen code maximises the multiplicative margin to both "
                "band edges: it is the code whose within-bundle geometric "
                f"centre sqrt(min*max) is closest to sqrt(lo*hi) = "
                f"{BAND_CENTRE_NS:.4g} ns, measured as a distance in log space.",
                "band_verdict 'in-band' means BOTH edges hold at every one of "
                "that bundle's points simultaneously, not that the centre sits "
                "between them. meets_spread_target is ratio_max_over_min <= "
                f"{SPREAD_TARGET:g}, DR-013 Decision 4's target -- reported per "
                "bundle as well as for the population, because a single bundle "
                "clearing it is necessary but not sufficient.",
                "This is the BARE delay chain, not the flag. DR-013 Decision 1 "
                "requires T1'/T2' to be judged on the observable window through "
                "the assembled detector loop; that measurement is "
                "sim/lock-detector's, at the codes this table picks.",
            ),
        ),
    ]
