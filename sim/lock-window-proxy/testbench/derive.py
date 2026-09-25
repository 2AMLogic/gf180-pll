"""lock-window-proxy: can a pad-referred quantity stand in for the lock
detector's internal window delay when a tester picks the trim code?

The trim rule (spec/pll.md#lock-detector-window-trim-code-rule) is normative
and its measurand is internal: t_win, the ERR -> ERRD delay of delaywin_3v3.
Neither node is a port of pll_top. This reduction scores the quantities the
pads DO expose against the rule they would have to replace.

Four tables:

``proxy_candidates``
    The verdict, one row per candidate observable plus two controls (the
    internal-measurand rule itself, and doing nothing). Residual spread, worst
    code error, and whether the resulting code holds the ratified band at
    every point of every bundle.

``proxy_tracking``
    The per-bundle detail behind it: how far each bundle's window and each
    candidate observable sit from typical's, at the rule's reference
    condition.

``proxy_code_table``
    For the best-scoring candidate: the code a tester would program, against
    the code the rule programs, and what the tester's code then does over that
    bundle's own nine voltage/temperature points.

``twin_crosscheck``
    This deck's sixteen-copies-on-one-step window against the committed
    single-copy campaign, point by point.

Nothing here is fitted to more than one bundle. ``typical`` supplies every
calibration constant -- its sixteen-entry window table and its own value of
each candidate observable -- and every other bundle is a test point. A table
fitted to all thirteen bundles and then scored against those same thirteen
would be circular.
"""

from __future__ import annotations

import math

from harness.derived import DerivedTable

#: The trim rule's target, spec/pll.md#lock-detector-window-trim-code-rule.
TARGET_NS = 1.343

#: The ratified two-sided band the selected code has to hold over the bundle's
#: whole PVT box (spec/pll.md's Lock detector row, T1'/T2', DR-010).
BAND_LO_NS = 1.0
BAND_HI_NS = 2.0

#: The bundle every candidate is calibrated at, and the only one.
CALIBRATION_BUNDLE = "typical"

#: The power-up code, i.e. what an untrimmed part runs at (DR-015).
UNTRIMMED_CODE = 8

CODES = tuple(range(16))

#: Rising edges the deck's period measurement spans (rise=1 -> rise=9).
PERIODS_MEASURED = 8

#: The pad-referred candidates, in the order they are reported.
CANDIDATES = (
    ("ring_a", "free-running ring period, band 4 / Vctrl 1.80 V (CLK pad)"),
    ("ring_b", "free-running ring period, band 7 / Vctrl 2.70 V (CLK pad)"),
    ("clk_fb", "CLK -> FB retiming skew, the flop's clock-to-Q (CLK and FB pads)"),
    ("clk_do", "CLK -> DIVOUT skew, the divider's own output path (CLK and DIVOUT pads)"),
)


def _twin_ns(point, code):
    if code is None:
        return None
    value = point.get(f"twin_c{code}")
    return None if value is None else value * 1e9


def _period_ns(point, which):
    value = point.get(f"t8p_{which}")
    return None if value is None else value * 1e9 / PERIODS_MEASURED


def _skew_ns(point, raw_name):
    """A CLK-referred skew, recovered modulo the ring period.

    FB and DIVOUT only change on a CLK edge, so the deck's trig/targ returns
    the skew plus an unknown whole number of CLK periods. The skew is shorter
    than one period by construction, so the remainder is exact.
    """
    raw = point.get(raw_name)
    period = _period_ns(point, "a")
    if raw is None or not period:
        return None
    return math.fmod(raw * 1e9, period)


def _observable(point, name):
    if name == "ring_a":
        return _period_ns(point, "a")
    if name == "ring_b":
        return _period_ns(point, "b")
    if name == "clk_fb":
        return _skew_ns(point, "tcq_raw")
    if name == "clk_do":
        return _skew_ns(point, "tdo_raw")
    raise KeyError(name)


def _is_ref(point, nominal_v):
    """The trim rule's reference condition: 27 C at nominal supply."""
    return abs(point.temp_c - 27.0) < 0.5 and abs(point.vdd - nominal_v) < 1e-6


def _nearest_code(table_ns, target_ns):
    """The code whose window is nearest ``target_ns`` in the LOG sense.

    Logarithmic because the window's error budget is multiplicative -- the same
    reason the trim rule says "nearest ... in the logarithmic sense".
    """
    usable = {c: v for c, v in table_ns.items() if v and v > 0}
    if not usable or not target_ns or target_ns <= 0:
        return None
    return min(usable, key=lambda c: abs(math.log(usable[c] / target_ns)))


def _geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def _fmt(value, digits=4):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return f"{value:.{digits}g}"


def _box(points, code):
    return [v for v in (_twin_ns(p, code) for p in points) if v]


def _band_verdict(values):
    if not values:
        return None, None, None, "not measured"
    lo, hi = min(values), max(values)
    ok = lo >= BAND_LO_NS and hi <= BAND_HI_NS
    return lo, hi, hi / lo, "in-band" if ok else "OUT OF BAND"


def derive_tables(run):
    supplies = sorted({p.vdd for p in run.points})
    nominal_v = supplies[len(supplies) // 2]

    bundles = []
    by_bundle = {}
    ref_point = {}
    for point in run.points:
        if point.corner not in by_bundle:
            by_bundle[point.corner] = []
            bundles.append(point.corner)
        by_bundle[point.corner].append(point)
        if _is_ref(point, nominal_v):
            ref_point[point.corner] = point
    bundles.sort()

    calib = ref_point.get(CALIBRATION_BUNDLE)
    if calib is None:
        note = (
            f"no {CALIBRATION_BUNDLE} point at the reference condition "
            f"(27 C, {nominal_v} V) -- every candidate's calibration constant "
            "comes from that point, so no verdict is derivable from this run"
        )
        return [
            DerivedTable(
                name=name,
                columns=("note",),
                rows=((note,),),
                description="not derivable: the calibration point was not run",
            )
            for name in ("proxy_candidates", "proxy_tracking", "proxy_code_table", "twin_crosscheck")
        ]

    calib_twin = {c: _twin_ns(calib, c) for c in CODES}
    calib_obs = {name: _observable(calib, name) for name, _ in CANDIDATES}

    # ---- per-bundle relatives, once -----------------------------------------
    twin_rel = {}
    obs_rel = {}
    for bundle in bundles:
        point = ref_point.get(bundle)
        if point is None:
            continue
        ratios = [
            _twin_ns(point, c) / calib_twin[c]
            for c in CODES
            if _twin_ns(point, c) and calib_twin[c]
        ]
        if ratios:
            twin_rel[bundle] = _geomean(ratios)
        obs_rel[bundle] = {}
        for name, _ in CANDIDATES:
            value = _observable(point, name)
            if value and calib_obs.get(name):
                obs_rel[bundle][name] = value / calib_obs[name]

    # ---- proxy_tracking -----------------------------------------------------
    tracking_columns = ["bundle", "twin_rel_to_typical"]
    for name, _ in CANDIDATES:
        tracking_columns += [f"{name}_ns", f"{name}_rel", f"{name}_residual"]
    tracking_rows = []
    for bundle in bundles:
        if bundle not in twin_rel:
            continue
        row = [bundle, _fmt(twin_rel[bundle], 5)]
        point = ref_point[bundle]
        for name, _ in CANDIDATES:
            value = _observable(point, name)
            rel = obs_rel.get(bundle, {}).get(name)
            row += [
                _fmt(value, 5),
                _fmt(rel, 5),
                _fmt(twin_rel[bundle] / rel, 5) if rel else "",
            ]
        tracking_rows.append(tuple(row))

    tables = [
        DerivedTable(
            name="proxy_tracking",
            columns=tuple(tracking_columns),
            rows=tuple(tracking_rows),
            description=(
                "at the trim rule's reference condition (27 C, nominal supply): how far "
                "each bundle's window sits from typical's, and how far each candidate "
                "pad-referred observable does"
            ),
            notes=(
                "twin_rel_to_typical is the geometric mean, over all sixteen codes, of "
                "this bundle's t_win divided by typical's t_win at the same code. Its "
                "spread across the bundles is the process variation the trim exists to "
                "remove.",
                "<candidate>_rel is the same ratio for the candidate observable. "
                "<candidate>_residual = twin_rel / <candidate>_rel, which is 1 exactly "
                "when the candidate is a perfect stand-in. A residual FURTHER from 1 "
                "than twin_rel itself means the candidate is worse than measuring "
                "nothing: it moves the estimate the wrong way.",
                "ring_a and ring_b are ring PERIODS in ns; clk_fb and clk_do are "
                "CLK-referred skews in ns, recovered modulo the ring period.",
            ),
        )
    ]

    # ---- proxy_candidates ---------------------------------------------------
    def score(selector):
        """Apply a code-selection policy to every bundle; return its scorecard."""
        deltas = []
        grid = []
        verdicts = []
        per_bundle = {}
        for bundle in bundles:
            point = ref_point.get(bundle)
            if point is None:
                continue
            rule_code = _nearest_code({c: _twin_ns(point, c) for c in CODES}, TARGET_NS)
            code = selector(bundle, point)
            if code is None or rule_code is None:
                continue
            box = _box(by_bundle[bundle], code)
            lo, hi, spread, verdict = _band_verdict(box)
            per_bundle[bundle] = (rule_code, code, lo, hi, spread, verdict)
            deltas.append(code - rule_code)
            grid.extend(box)
            verdicts.append(verdict)
        return deltas, grid, verdicts, per_bundle

    def selector_for(name):
        def pick(bundle, point):
            rel = obs_rel.get(bundle, {}).get(name)
            if not rel:
                return None
            return _nearest_code(calib_twin, TARGET_NS / rel)

        return pick

    def rule_selector(bundle, point):
        return _nearest_code({c: _twin_ns(point, c) for c in CODES}, TARGET_NS)

    policies = [
        ("RULE (internal t_win)", "the normative rule -- not executable at the pads", rule_selector),
    ]
    policies += [(name, desc, selector_for(name)) for name, desc in CANDIDATES]
    policies.append(
        (
            f"NONE (untrimmed, c{UNTRIMMED_CODE})",
            "the control: no measurement at all, every part left at the power-up code",
            lambda bundle, point: UNTRIMMED_CODE,
        )
    )

    candidate_rows = []
    scorecards = {}
    for name, desc, selector in policies:
        deltas, grid, verdicts, per_bundle = score(selector)
        if not grid:
            continue
        scorecards[name] = (deltas, grid, verdicts, per_bundle)
        residuals = [
            twin_rel[b] / obs_rel[b][name]
            for b in bundles
            if b in twin_rel and name in obs_rel.get(b, {})
        ]
        lo, hi = min(grid), max(grid)
        candidate_rows.append(
            (
                name,
                len(per_bundle),
                _fmt(max(residuals) / min(residuals), 5) if residuals else "",
                max(abs(d) for d in deltas) if deltas else "",
                len(grid),
                _fmt(lo, 4),
                _fmt(hi, 4),
                _fmt(hi / lo, 4),
                _fmt(100.0 * (lo - BAND_LO_NS) / BAND_LO_NS, 4),
                _fmt(100.0 * (BAND_HI_NS - hi) / BAND_HI_NS, 4),
                "all in-band" if all(v == "in-band" for v in verdicts) else "OUT OF BAND somewhere",
                desc,
            )
        )

    tables.insert(
        0,
        DerivedTable(
            name="proxy_candidates",
            columns=(
                "policy",
                "n_bundles",
                "residual_spread",
                "worst_code_error",
                "n_points",
                "twin_min_ns",
                "twin_max_ns",
                "spread",
                "margin_to_lo_pct",
                "margin_to_hi_pct",
                "verdict",
                "what it is",
            ),
            rows=tuple(candidate_rows),
            description=(
                "the answer: each way of choosing the trim code, scored over the whole "
                "grid -- the normative rule, each pad-referred candidate, and the "
                "no-measurement control"
            ),
            notes=(
                "residual_spread is max/min over the bundles of twin_rel / observable_rel. "
                "1.0 is a perfect stand-in. The RULE row has no residual (it measures the "
                "quantity itself) and the NONE row has none (it measures nothing); for "
                "those two the number to compare a candidate against is the process "
                "spread of the window itself, which is the spread of twin_rel_to_typical "
                "in proxy_tracking.",
                "worst_code_error is the largest |proxy code - rule code| over the "
                "bundles. It is diagnostic, not the verdict: a proxy that misses the "
                "rule's code but still holds the band everywhere has executed the rule's "
                "intent, which is what spec/pll.md's Lock detector row is conditioned on.",
                "twin_min/max and the verdict are over every PVT point of every bundle "
                "with that bundle at the code the policy chose -- the same band test "
                "sim/lock-window-trim applies to the rule's own code.",
                "The typical bundle is every candidate's calibration point and agrees "
                "with the rule there by construction; it is included in the counts so "
                "the grid is the same grid for every row, but it is not evidence for a "
                "candidate.",
            ),
        ),
    )

    # ---- proxy_code_table: the best-scoring candidate, per bundle -----------
    best = None
    for name, _ in CANDIDATES:
        residuals = [
            twin_rel[b] / obs_rel[b][name]
            for b in bundles
            if b in twin_rel and name in obs_rel.get(b, {})
        ]
        if len(residuals) < 2:
            continue
        spread = max(residuals) / min(residuals)
        if best is None or spread < best[1]:
            best = (name, spread)

    if best and best[0] in scorecards:
        name = best[0]
        _, _, _, per_bundle = scorecards[name]
        rows = []
        for bundle in bundles:
            if bundle not in per_bundle:
                continue
            rule_code, code, lo, hi, spread, verdict = per_bundle[bundle]
            rows.append(
                (
                    bundle,
                    f"c{rule_code}",
                    f"c{code}",
                    code - rule_code,
                    _fmt(TARGET_NS / obs_rel[bundle][name], 4) if name in obs_rel.get(bundle, {}) else "",
                    _fmt(lo, 4),
                    _fmt(hi, 4),
                    _fmt(spread, 4),
                    _fmt(100.0 * (lo - BAND_LO_NS) / BAND_LO_NS, 4),
                    _fmt(100.0 * (BAND_HI_NS - hi) / BAND_HI_NS, 4),
                    verdict + (" (calibration)" if bundle == CALIBRATION_BUNDLE else ""),
                )
            )
        description = (
            f"the best-scoring pad-referred candidate ({name}, residual spread "
            f"{best[1]:.4g}x) applied bundle by bundle, against the rule's own code"
        )
    else:
        rows = []
        description = "not derivable: no candidate had two comparable bundles"

    tables.append(
        DerivedTable(
            name="proxy_code_table",
            columns=(
                "bundle",
                "rule_code",
                "proxy_code",
                "code_delta",
                "adjusted_target_ns",
                "twin_min_ns",
                "twin_max_ns",
                "spread",
                "margin_to_lo_pct",
                "margin_to_hi_pct",
                "verdict",
            ),
            rows=tuple(rows),
            description=description,
            notes=(
                "adjusted_target_ns is 1.343 ns scaled by typical's observable over this "
                "bundle's observable -- the number the tester looks up in TYPICAL's "
                "sixteen-entry window table, which is the whole of the test program.",
                "twin_min/max are over this bundle's own nine voltage/temperature points "
                "at the PROXY's code.",
            ),
        )
    )

    tables.append(_crosscheck(run, by_bundle))
    return tables


def _crosscheck(run, by_bundle):
    """This deck's sixteen-copy window against the committed single-copy record."""
    try:
        join = run.join("trim")
    except Exception:  # noqa: BLE001 -- an absent join is a reportable state
        return DerivedTable(
            name="twin_crosscheck",
            columns=("note",),
            rows=(
                (
                    "no 'trim' join supplied -- pass --join "
                    "trim=lock-window-trim/corners/<record-id>/raw_measures.csv to "
                    "compare this deck's sixteen-copy window against the committed "
                    "single-copy campaign",
                ),
            ),
            description="not derivable: the committed single-copy record was not joined",
        )

    committed = {}
    for row in join.rows:
        try:
            key = (
                row["corner"],
                round(float(row["temp_c"])),
                round(float(row["vdd"]), 2),
                int(row["trim"].lstrip("c")),
            )
            committed[key] = float(row["twin_r"]) * 1e9
        except (KeyError, ValueError, AttributeError):
            continue

    ratios = []
    worst = None
    for points in by_bundle.values():
        for point in points:
            for code in CODES:
                mine = _twin_ns(point, code)
                theirs = committed.get(
                    (point.corner, round(point.temp_c), round(point.vdd, 2), code)
                )
                if not mine or not theirs:
                    continue
                ratio = mine / theirs
                ratios.append(ratio)
                if worst is None or abs(math.log(ratio)) > abs(math.log(worst[0])):
                    worst = (ratio, point.corner_id, code)

    if not ratios:
        return DerivedTable(
            name="twin_crosscheck",
            columns=("note",),
            rows=(("the joined record shares no (bundle, temperature, supply, code) point with this run",),),
            description="not derivable: no overlapping points",
        )

    return DerivedTable(
        name="twin_crosscheck",
        columns=(
            "n_points_compared",
            "ratio_min",
            "ratio_geomean",
            "ratio_max",
            "worst_point",
            "worst_code",
        ),
        rows=(
            (
                len(ratios),
                _fmt(min(ratios), 6),
                _fmt(_geomean(ratios), 6),
                _fmt(max(ratios), 6),
                worst[1] if worst else "",
                f"c{worst[2]}" if worst else "",
            ),
        ),
        description=(
            "this deck's sixteen-copies-on-one-step window divided by the committed "
            "single-copy campaign's, at every shared (bundle, temperature, supply, code)"
        ),
        notes=(
            "A ratio of 1 means putting sixteen chains on one ideal source changed "
            "nothing, which is what a zero-output-impedance stimulus should do. A "
            "systematic offset would mean the two campaigns are not measuring the same "
            "quantity, and the pairing this campaign rests on would not hold.",
        ),
    )
