"""gf180-pll :: lock-window-trim :: the reductions this campaign claims.

``derive_tables`` produces two tables.

``trim_ladder``
    One row per (corner bundle, trim code): the window t_win reduced over that
    bundle's own nine voltage/temperature points to min / max / geometric
    mean, plus the ratio to the previous code. This is where the two numbers
    DR-014 Decision 3 deliberately left open -- the trim's STEP SIZE and its
    total RANGE -- become measurements, and where monotonicity in the code is
    checked rather than asserted.

``trim_code_table``
    One row per corner bundle: the code the trim rule selects, and what the
    window then does over that bundle's own PVT points. Plus three summary
    rows whose ``code`` column is a word rather than a number:

    ``GRID``       the spread actually measured over this grid once every
                   bundle carries its selected code -- the direct reading of
                   DR-013 Decision 4's "PVT spread of the window over the
                   mandated grid".
    ``CONTINUOUS`` the same quantity for a real, continuously-distributed
                   population rather than 13 discrete bundles: the worst
                   within-bundle spread multiplied by one trim step, because
                   the rule rounds a part's measured delay to the nearest
                   code and can therefore leave up to one step of the
                   correction unapplied. This is the number to compare
                   against 1.65x, and it is deliberately the pessimistic one.
    ``UNTRIMMED``  the same grid with every bundle at the nominal code -- what
                   the spread would be with no trim at all, so the trim's
                   effect is a measured delta and not a claim.

The trim rule, restated (spec/pll.md's "Lock-detector window trim-code rule"
is normative):

    Measure t_win at the REFERENCE CONDITION -- 27 C, nominal supply -- and
    program the code whose t_win there is nearest ``TRIM_TARGET_NS`` in the
    log sense.

``TRIM_TARGET_NS`` is not a free parameter. It is the value that puts the
trimmed window's geometric centre on the geometric centre of the ratified
band, so that the margin the band leaves is split evenly between the two
edges instead of being spent on one of them; see its definition below.
"""

from __future__ import annotations

import math

from harness.derived import DerivedTable

#: spec/pll.md's ratified Lock criterion, in nanoseconds -- the band's lower
#: edge. A window narrower than this at any corner can refuse to assert on a
#: part that meets the criterion.
WIN_LO_NS = 1.0
#: Twice the criterion -- the false-positive reach the flag is allowed.
WIN_HI_NS = 2.0

#: DR-013 Decision 4's acceptance target for the window's PVT spread.
SPREAD_TARGET = 1.65

#: The reference condition the trim rule measures at: 27 C, nominal supply.
#: A single testable measurement of a 1-2 ns delay, at the one PVT point a
#: tester can actually hold -- the same "fixed, known condition" shape as the
#: Icp trim-code rule.
REF_TEMP_C = 27.0

#: The band's geometric centre, in nanoseconds. Putting the trimmed window's
#: own geometric centre here is what splits the band's remaining margin evenly
#: between the two edges instead of spending it all on one of them.
BAND_CENTRE_NS = math.sqrt(WIN_LO_NS * WIN_HI_NS)

#: The band is stated against the OBSERVABLE window -- the largest phase error
#: at the PFD inputs for which the flag asserts, measured through the assembled
#: detector loop (DR-013 Decision 1) -- while this campaign measures the BARE
#: chain delay that sets it. The observable window runs slightly wider than the
#: bare delay, because the XOR's own edge rate and the coincidence gate's
#: threshold sit between them. Measured, not assumed: at ss/125 C/2.97 V the
#: committed in-situ record sim/lock-detector/records/20260916-122705-98c935b.md
#: brackets the observable edge at [2.02, 2.04) ns where the bare delay of the
#: same untrimmed cell is 1.9564 ns (sim/lock-window-sizing's w095 column at
#: that corner) -- a ratio of 1.0376. Rounded to 1.037 here; the residual is far
#: below one trim step, and sim/lock-detector re-measures the real thing at the
#: selected codes rather than relying on this conversion.
OBSERVABLE_TO_BARE = 1.037

#: Measured on this cell (see the trim_ladder table's twin_at_ref_ns vs
#: twin_geomean_ns columns): the ratio between a bundle's window at the
#: reference condition and its geometric mean over that bundle's own nine PVT
#: points. 27 C / nominal supply is not the middle of the -40..125 C,
#: 2.97..3.63 V box in the log sense, so the two differ by ~1.5 %; the measured
#: value is 0.9863 (ff) / 0.9852 (typical) / 0.9842 (ss). Used only to turn
#: BAND_CENTRE_NS into a reference-condition target -- the code table reports
#: the achieved centring, so an error here shows up as an off-centre margin
#: rather than as a hidden assumption.
REF_TO_GEOMEAN = 0.985

#: The nominal code -- the cell's centre code, the one the UNTRIMMED summary
#: row is taken at and the reset/default value the block documentation quotes.
NOMINAL_CODE = 4


def _code_int(axis_id):
    """'c5' -> 5."""
    if not axis_id or not axis_id.startswith("c"):
        return None
    try:
        return int(axis_id[1:])
    except ValueError:
        return None


def _fmt(value, digits=4):
    return "" if value is None else f"{value:.{digits}g}"


def _geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def _target_ref_ns():
    """The trim rule's reference-condition target, in ns.

    Band centre -> bare-delay centre -> reference-condition value. Each factor
    is measured and documented above; none of them is fitted to make a verdict
    come out.
    """
    return BAND_CENTRE_NS / OBSERVABLE_TO_BARE * REF_TO_GEOMEAN


def derive_tables(run):
    # (bundle, code) -> [(temp_c, vdd, twin_r), ...]
    cells: dict[tuple[str, int], list] = {}
    nominal_v: dict[str, float] = {}
    for point in run.points:
        code = _code_int(point.axes.get("trim"))
        twin = point.get("twin_r")
        if code is None or not twin:
            continue
        cells.setdefault((point.corner, code), []).append((point.temp_c, point.vdd, twin))
        nominal_v.setdefault(point.corner, point.vdd)

    bundles = sorted({bundle for bundle, _ in cells})
    codes = sorted({code for _, code in cells})
    if not bundles or not codes:
        return []

    # The nominal supply is the middle of the three swept; take it from the
    # set actually run rather than from the manifest, so a thinned run still
    # reduces correctly.
    supplies = sorted({vdd for rows in cells.values() for _, vdd, _ in rows})
    ref_vdd = supplies[len(supplies) // 2] if supplies else None

    ladder_rows = []
    stats: dict[tuple[str, int], dict] = {}
    for bundle in bundles:
        prev_gm = None
        for code in codes:
            rows = cells.get((bundle, code))
            if not rows:
                continue
            values = [twin for _, _, twin in rows]
            lo, hi = min(values), max(values)
            gm = _geomean(values)
            ref = [twin for temp, vdd, twin in rows if temp == REF_TEMP_C and vdd == ref_vdd]
            stats[(bundle, code)] = {
                "lo": lo, "hi": hi, "gm": gm,
                "ref": ref[0] if ref else None,
                "n": len(values),
            }
            step = gm / prev_gm if prev_gm else None
            prev_gm = gm
            ladder_rows.append(
                (
                    bundle,
                    f"c{code}",
                    len(values),
                    _fmt(lo * 1e9),
                    _fmt(hi * 1e9),
                    _fmt(gm * 1e9),
                    _fmt(hi / lo),
                    _fmt(ref[0] * 1e9) if ref else "",
                    _fmt(step) if step else "",
                    "" if step is None else ("yes" if step > 1.0 else "NO"),
                )
            )

    # --- the trim rule, applied -------------------------------------------
    target_ref = _target_ref_ns() * 1e-9
    selected: dict[str, int] = {}
    for bundle in bundles:
        candidates = [
            (code, stats[(bundle, code)]["ref"])
            for code in codes
            if (bundle, code) in stats and stats[(bundle, code)]["ref"]
        ]
        if not candidates:
            continue
        selected[bundle] = min(candidates, key=lambda item: abs(math.log(item[1] / target_ref)))[0]

    code_rows = []
    grid_lo = grid_hi = None
    worst_within = None
    for bundle in bundles:
        code = selected.get(bundle)
        if code is None:
            continue
        cell = stats[(bundle, code)]
        lo_ns, hi_ns = cell["lo"] * 1e9, cell["hi"] * 1e9
        grid_lo = lo_ns if grid_lo is None else min(grid_lo, lo_ns)
        grid_hi = hi_ns if grid_hi is None else max(grid_hi, hi_ns)
        within = cell["hi"] / cell["lo"]
        worst_within = within if worst_within is None else max(worst_within, within)
        headroom_lo = code - min(codes)
        headroom_hi = max(codes) - code
        code_rows.append(
            (
                bundle,
                f"c{code}",
                f"{code:03b}",
                _fmt(cell["ref"] * 1e9) if cell["ref"] else "",
                _fmt(lo_ns),
                _fmt(hi_ns),
                _fmt(within),
                _fmt(100.0 * (lo_ns - WIN_LO_NS) / WIN_LO_NS),
                _fmt(100.0 * (WIN_HI_NS - hi_ns) / WIN_HI_NS),
                "in-band" if (lo_ns >= WIN_LO_NS and hi_ns <= WIN_HI_NS) else "OUT-OF-BAND",
                f"{headroom_lo}/{headroom_hi}",
            )
        )

    # Worst single step anywhere on the ladder -- the rounding residual a
    # continuously-distributed population can be left with.
    steps = []
    for bundle in bundles:
        ordered = [stats[(bundle, code)]["gm"] for code in codes if (bundle, code) in stats]
        steps += [b / a for a, b in zip(ordered, ordered[1:])]
    worst_step = max(steps) if steps else None

    # Untrimmed reference: the same grid with every bundle at the nominal code.
    untrimmed = [stats[(b, NOMINAL_CODE)] for b in bundles if (b, NOMINAL_CODE) in stats]
    unt_lo = min(c["lo"] for c in untrimmed) * 1e9 if untrimmed else None
    unt_hi = max(c["hi"] for c in untrimmed) * 1e9 if untrimmed else None

    def _summary(label, lo_ns, hi_ns, spread, note):
        return (
            label, "", "", "",
            _fmt(lo_ns), _fmt(hi_ns), _fmt(spread),
            _fmt(100.0 * (lo_ns - WIN_LO_NS) / WIN_LO_NS) if lo_ns else "",
            _fmt(100.0 * (WIN_HI_NS - hi_ns) / WIN_HI_NS) if hi_ns else "",
            note, "",
        )

    grid_spread = grid_hi / grid_lo if grid_lo else None
    code_rows.append(
        _summary(
            "GRID", grid_lo, grid_hi, grid_spread,
            "meets-1.65x" if (grid_spread and grid_spread <= SPREAD_TARGET) else "MISSES-1.65x",
        )
    )
    cont_spread = worst_within * worst_step if (worst_within and worst_step) else None
    code_rows.append(
        (
            "CONTINUOUS", "", "", "", "", "", _fmt(cont_spread), "", "",
            "meets-1.65x" if (cont_spread and cont_spread <= SPREAD_TARGET) else "MISSES-1.65x",
            _fmt(worst_step) if worst_step else "",
        )
    )
    if unt_lo and unt_hi:
        code_rows.append(
            _summary("UNTRIMMED", unt_lo, unt_hi, unt_hi / unt_lo, f"every bundle at c{NOMINAL_CODE}")
        )

    return [
        DerivedTable(
            name="trim_ladder",
            description=(
                "per (corner bundle, trim code): the window t_win (twin_r) reduced "
                "over that bundle's own 9 voltage/temperature points, plus the step "
                "to the previous code -- the trim's step size, total range and "
                "monotonicity, measured"
            ),
            columns=(
                "bundle",
                "code",
                "n_points",
                "twin_min_ns",
                "twin_max_ns",
                "twin_geomean_ns",
                "within_bundle_spread",
                "twin_at_ref_ns",
                "step_vs_prev_code",
                "monotonic_in_code",
            ),
            rows=tuple(ladder_rows),
            notes=(
                "twin_at_ref_ns is the window at the trim rule's reference "
                f"condition ({REF_TEMP_C:g} C, nominal supply) -- the single "
                "measurement the rule selects a code from.",
                "within_bundle_spread is max/min over that bundle's own PVT box "
                "at that code. It is the FLOOR the trim cannot go below: the trim "
                "removes the process axis, not the voltage/temperature axes.",
                "step_vs_prev_code is the ratio of geometric means between "
                "adjacent codes; monotonic_in_code is 'NO' for any step that is "
                "not > 1, which is the property an unweighted pass gate breaks.",
            ),
        ),
        DerivedTable(
            name="trim_code_table",
            description=(
                "the trim rule applied: per corner bundle, the selected code and "
                "what the window then does over that bundle's PVT points, against "
                f"the ratified band [{WIN_LO_NS:g}, {WIN_HI_NS:g}] ns and DR-013 "
                f"Decision 4's <= {SPREAD_TARGET:g}x spread target"
            ),
            columns=(
                "bundle",
                "code",
                "bits_T2T1T0",
                "twin_at_ref_ns",
                "twin_min_ns",
                "twin_max_ns",
                "spread",
                "margin_to_lo_pct",
                "margin_to_hi_pct",
                "verdict",
                "code_headroom_lo/hi",
            ),
            rows=tuple(code_rows),
            notes=(
                "The rule: measure t_win at the reference condition and program "
                f"the code nearest {_target_ref_ns():.4g} ns in the log sense. "
                "Nothing on-chip performs this measurement (DR-014 Decision 2).",
                "code_headroom_lo/hi is how many codes remain below/above the "
                "selected one. A bundle at 0/N or N/0 has no room left to correct "
                "a part beyond that corner, which is a range finding, not a pass.",
                "GRID is the spread over this 13-bundle grid with each bundle at "
                "its own selected code -- the literal reading of DR-013 Decision "
                "4's target.",
                "CONTINUOUS is the pessimistic reading, and the one to quote: a "
                "real population is continuous, the rule rounds to the nearest "
                "code, so up to one trim step of correction is left unapplied on "
                "top of the worst within-bundle spread. Its spread column is "
                "worst_within_bundle_spread x worst_step; the last column carries "
                "that worst step.",
                "UNTRIMMED is the same grid with every bundle at the nominal code "
                f"c{NOMINAL_CODE} -- the no-trim counterfactual, so the trim's "
                "effect is a measured delta rather than a claim.",
            ),
        ),
    ]
