"""reference-input-contract reductions: what a legal reference does to the PFD.

The claim this campaign answers is not any single measured number -- it is a
*difference*.  `spec/pll.md`'s Reference input row states three limits on the
driving system (levels, 10-90 % edge rate, duty cycle) which every testbench
in this repository had left at one ideal value, and the question is what
moves when a reference walks each of them to its stated boundary.  So every
verdict quantity here is a per-corner delta against the ideal pulse:

    dphi_shift(X) = d_ref(X) - d_ref(wideal)     the shift of the sampled phase
    dfb_dev(X)    = d_fb(X)  - d_fb(wideal)      the experiment's own control
    kd(X)         = [q(+200ps) - q(-200ps)] / 400ps   detector gain at the
                                                       reference variant X

`d_ref` and `d_fb` are ordinary per-point `.measure` results, so the manifest
gates them directly.  Everything above differences two or more points of the
`w` (waveform) or `p` (phase-offset) axis at one PVT corner, and a grid that
runs one ngspice invocation per (corner, waveform, offset) point cannot
express that per point -- those are reduced per corner in
:func:`derive_tables`, each with its own explicit `verdict` column, exactly as
`sim/pfd-deadzone`'s linearity ratio is.

Two per-point derivations do fit in :func:`derive_point`, and both exist so
that the record *proves its own stimulus* rather than asserting it from the
manifest's `pulse()` arguments:

    duty_ref_pct  the applied mid-rail duty cycle, in percent
    slope_ref     the applied mid-rail slew rate, in V/s

`duty_ref_pct` is gated against the ratified 30-70 % range by the manifest, so
a point that failed to drive the duty it claims fails the record instead of
quietly reporting a delay taken under the wrong condition.
"""

from harness.derived import DerivedTable, fmt_scalar

#: Reference period, seconds -- the manifest's `period` param.  Spelled here
#: rather than parsed out of `point.params` for the same reason
#: `sim/pfd-deadzone`'s derive.py spells its differencing spans: a reduction
#: that silently re-derived its own constants from a changed manifest would
#: relabel evidence rather than fail.
PERIOD_S = 40e-9

#: The `w` axis, in record order: (point id, the column label, the REF swing as
#: a fraction of VDD).  The swing fraction is what turns the measured 10-90 %
#: edge TIME into a slew RATE, and it is the one thing about the stimulus that
#: cannot be read back off a `.measure` result.
WAVEFORMS = (
    ("wideal", "ideal", 1.0),
    ("wlevel", "levels", 0.6),
    ("wedge", "edge5ns", 1.0),
    ("wd30", "duty30", 1.0),
    ("wd70", "duty70", 1.0),
    ("wworst", "worst", 0.6),
)
SWING_FRACTION = {pid: frac for pid, _, frac in WAVEFORMS}
LABEL = {pid: label for pid, label, _ in WAVEFORMS}
ORDER = {pid: i for i, (pid, _, _) in enumerate(WAVEFORMS)}

#: Manifest axis names and the points the reductions key on.
W_AXIS = "w"
P_AXIS = "p"
ANCHOR = "wideal"
LOCK_POINT = "p0"
NEAR_LO = "pm200"
NEAR_HI = "pp200"

#: The near pair's span, seconds -- `sim/pfd-deadzone`'s `kd_near` interval.
NEAR_SPAN_S = 400e-12

#: Acceptance bounds.  BOTH ARE TAKEN FROM THE RATIFIED SPEC, not from the
#: measured distribution.
#:
#: `STATIC_PHASE_BOUND_S` is the 1 ns static-phase bound of spec/pll.md's Lock
#: criterion: a reference-induced shift of the sampling instant is
#: indistinguishable, at the detector's input, from static phase error, so it
#: is the scale that makes the number mean something.
STATIC_PHASE_BOUND_S = 1e-9
#: `DUTY_BOUND_FRACTION` is the falsifiable form of spec/pll.md's duty row,
#: which argues from design/pfd.sch that the edge detectors fire on the rising
#: edge only and therefore that duty "affects only pulse-width margin, not the
#: sampled phase".  1 % of the corner's own set delay is that claim with a
#: number on it.
DUTY_BOUND_FRACTION = 0.01
#: ... floored at the deck's own crossing-time resolution.  `.measure ... when`
#: interpolates linearly between adjacent timepoints, and the transient runs at
#: a 20 ps maximum timestep, so two runs of the same crossing are not expected
#: to agree below a few picoseconds.  Grading a difference against a bound
#: tighter than the resolution that produced it would report solver noise as a
#: contract violation.
RESOLUTION_FLOOR_S = 5e-12


def _duty_bound(d_ref_anchor):
    """The duty / control bound at one corner: 1 % of `d_ref`, never below the
    deck's own crossing-time resolution."""
    if d_ref_anchor is None:
        return RESOLUTION_FLOOR_S
    return max(DUTY_BOUND_FRACTION * abs(d_ref_anchor), RESOLUTION_FLOOR_S)


def derive_point(point):
    """`duty_ref_pct` and `slope_ref` -- the applied stimulus, measured back.

    Both are properties of this point's own REF waveform, and both are here so
    that the contract limits are *conditions the record measured* rather than
    numbers read off the manifest.  A point whose `.measure` did not fire
    returns nothing for that entry and is recorded `not measured`, which the
    manifest's `min_measured_points` then fails -- an unmeasured condition is
    not a satisfied one.
    """
    out = {}

    t_high = point.get("thigh_ref")
    if t_high is not None:
        out["duty_ref_pct"] = 100.0 * t_high / PERIOD_S

    slew = point.get("slew_ref")
    frac = SWING_FRACTION.get(point.axes.get(W_AXIS))
    if slew is not None and slew > 0 and frac is not None:
        # 10-90 % of the swing traversed in `slew` seconds.  For the linear
        # ramp a `pulse()` source produces, that ratio IS the mid-rail slope.
        out["slope_ref"] = 0.8 * frac * point.vdd / slew

    return out


def _corner_key(point):
    """`ff/125C/3.63V` -- the key every per-corner table in sim/ uses."""
    return f"{point.corner}/{point.temp_c:g}C/{point.vdd:.2f}V"


def _extract_threshold(d_fast, s_fast, d_slow, s_slow):
    """Solve `d_ref = d0 + vth_off / slope` from two (slope, delay) pairs.

    `vth_off` is the effective switching threshold of the REF input path
    measured from mid-rail, in volts: positive means the path trips *above*
    VDD/2, so a slower reference edge arrives at the detector later.  `d0` is
    the slope-independent remainder of the set delay.

    Returns `(vth_off, d0)`, or `(None, None)` when the two slopes are too
    close to separate the two unknowns -- which cannot happen for the
    160 ps / 5 ns pair this campaign feeds it, but is checked rather than
    assumed.
    """
    if None in (d_fast, s_fast, d_slow, s_slow) or not s_fast or not s_slow:
        return None, None
    inv_delta = (1.0 / s_slow) - (1.0 / s_fast)
    if abs(inv_delta) < 1e-15:
        return None, None
    vth_off = (d_slow - d_fast) / inv_delta
    return vth_off, d_fast - vth_off / s_fast


def derive_tables(run):
    """Three tables: every point, the per-corner contract verdict, the gain."""
    by_corner = {}
    for point in run.points:
        key = _corner_key(point)
        axes = (point.axes.get(W_AXIS), point.axes.get(P_AXIS))
        by_corner.setdefault(key, {})[axes] = point

    point_rows = []
    verdict_rows = []
    gain_rows = []

    for key in sorted(by_corner, key=_sort_key):
        cell = by_corner[key]

        for (w_id, p_id), point in sorted(
            cell.items(), key=lambda kv: (ORDER.get(kv[0][0], 99), kv[0][1] or "")
        ):
            point_rows.append(
                (
                    point.corner,
                    f"{point.temp_c:g}",
                    f"{point.vdd:.2f}",
                    LABEL.get(w_id, w_id),
                    p_id,
                    fmt_scalar(point.get("d_ref")),
                    fmt_scalar(point.get("d_fb")),
                    fmt_scalar(point.get("slew_ref")),
                    fmt_scalar(point.get("duty_ref_pct"), "%.3f"),
                    fmt_scalar(point.get("slope_ref")),
                    fmt_scalar(point.get("width_up")),
                    fmt_scalar(point.get("width_dn")),
                    fmt_scalar(point.get("qnet")),
                )
            )

        verdict_rows.extend(_verdict_row(key, cell))
        gain_rows.extend(_gain_rows(key, cell))

    nfail = sum(1 for row in verdict_rows if row[-1] == "FAIL")
    shifts = [
        abs(float(v))
        for row in verdict_rows
        for v in row[2:7]
        if v not in ("", None)
    ]
    worst_shift = max(shifts) if shifts else None

    gain_fail = sum(1 for row in gain_rows if row[-1] == "FAIL")

    return [
        DerivedTable(
            name="reference_input_points",
            description=(
                "every (PVT corner, REF waveform, applied phase offset) point -- "
                "the applied stimulus measured back from the waveform, and what "
                "the phase detector did with it"
            ),
            notes=(
                "ref period 40 ns (25 MHz, the top of DR-002's ratified 1-25 MHz v1 range)",
                "vctrl held at 1.65 V; Icp trim code b1b0=10 (3 unit legs) -- the "
                "sim/pfd-deadzone operating point, so the charge numbers compare",
                "waveform: ideal = full-rail 200 ps edges 50 % duty (what every other "
                "testbench in this repository drives); levels = 0.2*VDD - 0.8*VDD; "
                "edge5ns = 5.00 ns 10-90 %; duty30/duty70 = the ends of the ratified "
                "30-70 % range; worst = all three at once",
                "phase: p0 = zero applied phase offset (the lock point); pm200/pp200 = "
                "the +/-200 ps near pair, run only on the detector-gain sub-grid",
                "d_ref_s: REF mid-rail crossing -> UP assertion (s).  THIS IS THE "
                "SAMPLED PHASE: at lock the loop drives (t_ref + d_ref) = (t_fb + d_fb).",
                "d_fb_s: the same set delay down the feedback path (s).  FB is driven "
                "identically at every point, so this is the experiment's control.",
                "slew_ref_s: the 10-90 % edge time OF THE APPLIED WAVEFORM (s) -- "
                "measured, so the record proves it drove what it claims to have driven",
                "duty_pct: the applied mid-rail high span as a percentage of the period",
                "slope_ref_v_per_s: the applied mid-rail slew rate (V/s)",
                "width_up_s/width_dn_s: UP/DN pulse width at mid-supply, third "
                "reference cycle.  An empty cell is an `optional` measurement that "
                "never crossed mid-supply.",
                "qnet_c: net charge delivered to the control node per reference cycle "
                "(C), positive = pump sourcing",
            ),
            columns=(
                "process",
                "temp_c",
                "vdd_v",
                "waveform",
                "phase",
                "d_ref_s",
                "d_fb_s",
                "slew_ref_s",
                "duty_pct",
                "slope_ref_v_per_s",
                "width_up_s",
                "width_dn_s",
                "qnet_c",
            ),
            rows=tuple(point_rows),
        ),
        DerivedTable(
            name="reference_input_verdict",
            description=(
                "per-corner shift of the sampled phase against the ideal reference -- "
                f"{len(verdict_rows)} corner(s) checked, {nfail} FAILED"
                + (
                    f"; largest shift {worst_shift:.4g} s against the 1 ns "
                    "static-phase bound"
                    if worst_shift is not None
                    else ""
                )
            ),
            notes=(
                "d_ref_ideal_s: the reference-path set delay at the ideal waveform (s) "
                "-- the anchor every shift in this row is measured against",
                "shift_*_s: d_ref(variant) - d_ref(ideal) at this corner (s).  A "
                "positive shift means the phase detector acted on the reference LATER "
                "than it would have with the ideal pulse, which moves the locked "
                "loop's reference-to-output phase by the same amount.",
                "dfb_dev_max_s: the largest |d_fb(variant) - d_fb(ideal)| at this "
                "corner (s).  FB is driven identically at every point, so this is the "
                "experiment's own control and is graded on the same bound the duty "
                "claim is.",
                "vth_off_v: the effective switching threshold of the REF input path, "
                "measured from mid-rail (V), extracted from the ideal / 5 ns-edge "
                "slope pair.  Positive = trips above VDD/2, so a slower edge arrives "
                "later.",
                "vth_model_resid_s: measured d_ref(worst) minus the value that "
                "two-parameter model predicts at the worst point's own slope (s).  "
                "This is a CHECK of the extraction against a third, independent "
                "slope at reduced levels -- not a fit residual.",
                "dtdv_worst_s_per_v: 1 / slope at the worst legal reference waveform "
                "(s/V) -- the AM-to-PM coefficient an integrating system needs to turn "
                "its own reference's amplitude noise into a sampling-instant "
                "displacement.  This is the input side of the reference-source-quality "
                "exclusion; the output-referred jitter number it does not replace is "
                "named in that row's owner.",
                "verdict: pass iff every shift is within the 1 ns static-phase bound "
                "of spec/pll.md's Lock criterion, AND the two duty shifts are within "
                "1 % of d_ref (the falsifiable form of the duty row's rising-edge-only "
                "argument, floored at the deck's 5 ps crossing resolution), AND the "
                "d_fb control did not move by more than that same bound",
            ),
            columns=(
                "corner",
                "d_ref_ideal_s",
                "shift_levels_s",
                "shift_edge5ns_s",
                "shift_duty30_s",
                "shift_duty70_s",
                "shift_worst_s",
                "dfb_dev_max_s",
                "vth_off_v",
                "vth_model_resid_s",
                "dtdv_worst_s_per_v",
                "verdict",
            ),
            rows=tuple(verdict_rows),
        ),
        DerivedTable(
            name="reference_input_gain",
            description=(
                "detector gain at a legal reference, against the same corner's ideal "
                f"reference -- {len(gain_rows)} (corner, waveform) pair(s), "
                f"{gain_fail} FAILED.  A declared 3-corner slice of the grid; see the "
                "record's Corner matrix run field for why."
            ),
            notes=(
                "kd_a: [q(+200ps) - q(-200ps)] / 400ps at this waveform (A) -- the "
                "phase-detector gain the loop's bandwidth and stability depend on, "
                "measured over the same near pair sim/pfd-deadzone uses",
                "kd_ratio: kd(this waveform) / kd(ideal) at the same corner.  1.0 is "
                "'a legal reference does not change the gain'.",
                "verdict: pass iff kd_ratio is within +/-20 % of unity -- the loop "
                "already tolerates a 1.6x gain variation across the PVT grid "
                "(spec/pll.md, Period jitter band-top row), so a reference-shape term "
                "materially smaller than that does not move the loop's stability "
                "argument, and one larger than it would have to be budgeted",
            ),
            columns=("corner", "waveform", "kd_a", "kd_ratio", "verdict"),
            rows=tuple(gain_rows),
        ),
    ]


def _sort_key(key):
    """`ss/125C/2.97V` -> a stable (process, temp, vdd) sort."""
    process, temp, vdd = key.split("/")
    return (process, float(temp.rstrip("C")), float(vdd.rstrip("V")))


def _verdict_row(key, cell):
    """One row of `reference_input_verdict`, or nothing at a corner with no
    lock-point slice (the detector-gain blocks add no new corners, so this
    never skips a corner in practice -- it is checked rather than assumed)."""
    anchor = cell.get((ANCHOR, LOCK_POINT))
    if anchor is None:
        return ()

    d_anchor = anchor.get("d_ref")
    fb_anchor = anchor.get("d_fb")
    bound = _duty_bound(d_anchor)

    shifts = {}
    fb_devs = []
    for w_id, _, _ in WAVEFORMS:
        if w_id == ANCHOR:
            continue
        point = cell.get((w_id, LOCK_POINT))
        d_var = point.get("d_ref") if point is not None else None
        shifts[w_id] = (
            d_var - d_anchor if (d_var is not None and d_anchor is not None) else None
        )
        fb_var = point.get("d_fb") if point is not None else None
        if fb_var is not None and fb_anchor is not None:
            fb_devs.append(abs(fb_var - fb_anchor))

    fb_dev_max = max(fb_devs) if fb_devs else None

    slow = cell.get(("wedge", LOCK_POINT))
    vth_off, d0 = _extract_threshold(
        d_anchor,
        anchor.get("slope_ref"),
        slow.get("d_ref") if slow is not None else None,
        slow.get("slope_ref") if slow is not None else None,
    )

    worst = cell.get(("wworst", LOCK_POINT))
    slope_worst = worst.get("slope_ref") if worst is not None else None
    dtdv_worst = 1.0 / slope_worst if slope_worst else None
    resid = None
    if (
        worst is not None
        and vth_off is not None
        and d0 is not None
        and slope_worst
        and worst.get("d_ref") is not None
    ):
        resid = worst.get("d_ref") - (d0 + vth_off / slope_worst)

    complete = d_anchor is not None and all(v is not None for v in shifts.values())
    within_static = complete and all(
        abs(v) <= STATIC_PHASE_BOUND_S for v in shifts.values()
    )
    within_duty = complete and all(
        abs(shifts[w]) <= bound for w in ("wd30", "wd70")
    )
    control_held = fb_dev_max is not None and fb_dev_max <= bound
    passed = complete and within_static and within_duty and control_held

    return (
        (
            key,
            fmt_scalar(d_anchor),
            fmt_scalar(shifts.get("wlevel")),
            fmt_scalar(shifts.get("wedge")),
            fmt_scalar(shifts.get("wd30")),
            fmt_scalar(shifts.get("wd70")),
            fmt_scalar(shifts.get("wworst")),
            fmt_scalar(fb_dev_max),
            fmt_scalar(vth_off, "%.5f"),
            fmt_scalar(resid),
            fmt_scalar(dtdv_worst),
            "pass" if passed else "FAIL",
        ),
    )


#: Acceptance on the gain ratio -- see the table's own notes for the derivation.
GAIN_RATIO_TOL = 0.20


def _gain_rows(key, cell):
    """Rows of `reference_input_gain` at a corner that ran the near pair."""

    def kd(w_id):
        lo = cell.get((w_id, NEAR_LO))
        hi = cell.get((w_id, NEAR_HI))
        if lo is None or hi is None:
            return None
        q_lo = lo.get("qnet")
        q_hi = hi.get("qnet")
        if q_lo is None or q_hi is None:
            return None
        return (q_hi - q_lo) / NEAR_SPAN_S

    kd_anchor = kd(ANCHOR)
    rows = []
    for w_id, label, _ in WAVEFORMS:
        value = kd(w_id)
        if value is None:
            continue
        ratio = value / kd_anchor if kd_anchor else None
        if w_id == ANCHOR:
            verdict = "reference"
        elif ratio is None:
            verdict = "FAIL"
        else:
            verdict = "pass" if abs(ratio - 1.0) <= GAIN_RATIO_TOL else "FAIL"
        rows.append(
            (
                key,
                label,
                fmt_scalar(value),
                fmt_scalar(ratio, "%.4f"),
                verdict,
            )
        )
    return tuple(rows)
