"""lock-window-bisection: does a symmetric REF phase-step bisection read at the
LOCK pad select the lock-detector window trim code?

The per-point measurements are one transient each: the loop locked, REF's phase
stepped once by a signed ``delta``, and the design's own ``LOCK`` output
watched. Nothing in a single point is the claim. The claim is a reduction over
the ``d`` (phase-step) axis at one (bundle, trim-code) cell, and it is three
tables:

``step_ladder``
    Every rung, in order: what was asked of the stimulus, what the stimulus
    actually did, whether LOCK dropped, how far the detector's integrator got,
    and the loop's own static offset at the moment of the step. This is the
    evidence the other two tables reduce.

``bisection_thresholds``
    The procedure executed. Per bundle: the smallest step in each direction
    that deasserted LOCK, bracketed by the largest that did not; then
    ``t_flag = (Theta+ + Theta-)/2`` and ``|phi_ss| = |Theta- - Theta+|/2`` --
    the procedure's own two outputs -- against the committed reference for
    each. ``t_flag``'s reference is an INTERVAL, not a point:
    ``t_win x [1.014, 1.070]`` at that (bundle, code, 27 C, 3.30 V) point, with
    ``t_win`` from sim/lock-window-proxy's committed 16-code window map (this
    manifest's ``winmap`` join) and the interval the measured flag-to-chain
    excess spec/pll.md records. DR-022 Decision 2's corollary forbids dividing a
    flag-referred measurement by the fixed 1.037x the rule's own target embeds,
    so this reduction does not. ``phi_ss``'s reference is the same run's own
    directly-measured REF -> FB skew, which needs no conversion at all.

``tier_verdict``
    The grading, against DR-022 Decision 2's two tiers, in trim codes rather
    than in picoseconds -- because a code is the only unit in which the rule
    can be got right or wrong. The measurement error is converted into codes
    through the *measured* per-code step of that bundle's own window ladder
    (also from the join), so the conversion is not a nominal 4.7 % but the real
    geometric step of the committed cell.

Two conventions, stated because they decide what the tables mean:

* **The verdict is taken from LOCK.** ``vwin_min`` -- the detector's integrator
  node, of which LOCK is a Schmitt trigger -- is reported at every rung and is
  why a coarse ladder plus a fine ladder can replace a nine-transient binary
  search, but a threshold is always the LOCK bracket. On silicon a tester has
  the bit and nothing else.
* **A threshold is a bracket, not a point.** It is reported as
  ``[largest step that held, smallest step that dropped]`` with its midpoint
  and half-width. The half-width is the measurement's own resolution and is
  carried all the way into the code error, so a verdict can never be more
  precise than the ladder that produced it.
"""

from __future__ import annotations

import math

from harness.derived import DerivedTable, fmt_scalar

#: The trim rule's target at the reference condition, in ns
#: (spec/pll.md#lock-detector-window-trim-code-rule).
TARGET_NS = 1.343

#: The measured flag-to-chain excess, as a RANGE and deliberately not as the
#: single 1.037x constant the rule's own target embeds. `WIDE = ERR . ERRD` is
#: high for only `terr - t_win`, so a phase error just past t_win makes a WIDE
#: pulse too short for the MDNW/VWIN charge network to act on and the flag keeps
#: asserting for a further delta -- measured at +1.4 .. +3.3 % at
#: ff/-40 C/3.63 V and +1.7 .. +7.0 % at ss/125 C/2.97 V (spec/pll.md's Lock
#: detector section, from sim/lock-detector's 205-point in-situ campaign).
#:
#: DR-022 Decision 2's corollary is explicit that a FLAG-referred route must not
#: divide by a fixed 1.037x to recover t_win: the ratio's own 1.055x spread is
#: worth 1.2-2.0 codes, so the conversion alone fails Tier B before any
#: measurement error. This reduction therefore does not convert. It compares the
#: procedure's t_flag against the interval t_win x [1.014, 1.070] -- what the
#: flag window at this point is KNOWN to be, from committed evidence -- and
#: reports the reference's own width in codes alongside the measurement's, so a
#: verdict can never be sharper than the two uncertainties that produced it.
DELTA_MIN = 0.014
DELTA_MAX = 0.070

#: DR-022 Decision 2 Tier A: a pad-referred substitute preserves the ratified
#: [1, 2] ns band if its code error never exceeds this many codes low / high.
#: (Corrected on merge from the figures issue #527's body carries -- the high
#: side is 3, not 4: ln(2.0/1.726)/ln(1.047) = 3.2 at the largest measured step.)
TIER_A_LOW = -2
TIER_A_HIGH = 3

#: DR-022 Decision 2 Tier B: DR-013 Decision 4's <= 1.65x spread target survives
#: a pad-referred substitute only if its worst code error is exactly zero -- the
#: rule's own rounding already spends all but 0.53-0.92 of one trim step of the
#: allowance.
TIER_B_MAX_ABS = 0


def _f(point, name):
    v = point.get(name)
    return None if v is None else float(v)


def _param(point, name):
    raw = point.params.get(name)
    return None if raw is None else float(raw)


def _tphi(point):
    """The nominal step instant, exactly as the deck computes it."""
    fref = _param(point, "fref")
    nstep = _param(point, "nstep")
    if fref is None or nstep is None:
        return None
    tref = 1.0 / fref
    return 0.5 * tref + nstep * tref


def derive_point(point):
    out = {}

    fref = _param(point, "fref")
    delta = _param(point, "delta")
    if delta is not None:
        out["delta_s"] = delta

    # What the stimulus actually did. `tref_span` is the REF period that
    # straddles the step boundary, so the achieved step is that minus the
    # nominal period. A mismatch means the two-source select did not place the
    # edge where the manifest asked, and the manifest's delta_err check fails
    # the point rather than letting a wrong threshold through.
    span = _f(point, "tref_span")
    if span is not None and fref is not None:
        meas = span - 1.0 / fref
        out["delta_meas"] = meas
        if delta is not None:
            out["delta_err"] = meas - delta

    # The loop's own settled static offset, the second of the two independent
    # ways: a reset-type PFD's UP and DN both pulse every reference cycle for
    # the reset delay, and the loop stands off exactly the phase that balances
    # the pump's per-event charge asymmetry, so w_up - w_dn is the REF -> FB
    # skew. Reported alongside phi_pre so a disagreement is visible.
    tup_r, tup_f = _f(point, "tup_r"), _f(point, "tup_f")
    tdn_r, tdn_f = _f(point, "tdn_r"), _f(point, "tdn_f")
    if None not in (tup_r, tup_f, tdn_r, tdn_f):
        out["skew_pw"] = (tup_f - tup_r) - (tdn_f - tdn_r)

    # Was the offset still moving when the step arrived? Measured, not assumed.
    phi_pre, phi_early = _f(point, "phi_pre"), _f(point, "phi_early")
    if phi_pre is not None and phi_early is not None:
        out["phi_drift"] = phi_pre - phi_early

    # The pad's own answer. vdd is the rail this point ran at, so the half-rail
    # discriminator does not assume 3.3 V.
    lock_min = _f(point, "lock_min")
    if lock_min is not None:
        out["deasserted"] = 1.0 if lock_min < 0.5 * point.vdd else 0.0

    vwin_pre, vwin_min = _f(point, "vwin_pre"), _f(point, "vwin_min")
    if vwin_pre is not None and vwin_min is not None:
        out["vwin_drop"] = vwin_pre - vwin_min

    # Deassert latency and dip duration -- issue #527 checkbox 1's two numbers.
    # Both are absent by design below threshold (LOCK never drops), which is
    # why the underlying `when` measures are declared optional.
    tphi = _tphi(point)
    t_de, t_re = _f(point, "t_deassert"), _f(point, "t_reassert")
    if t_de is not None and tphi is not None:
        out["deassert_lat_ns"] = (t_de - tphi) * 1e9
    if t_de is not None and t_re is not None and t_re > t_de:
        out["dip_ns"] = (t_re - t_de) * 1e9

    return out


# --------------------------------------------------------------------------
# the run-level reduction
# --------------------------------------------------------------------------

def _code_of(point):
    """The trim code this point ran at, from the four LDT bits it drove."""
    bits = 0
    for i in range(4):
        v = _param(point, "ldt%d_code" % i)
        if v is None:
            return None
        bits |= int(round(v)) << i
    return bits


def _winmap_row(run, point):
    """This (bundle, temperature, supply) row of the committed 16-code map."""
    table = run.join("winmap").index_by("corner", "temp_c", "vdd")
    for temp in ("%.1f" % point.temp_c, "%g" % point.temp_c):
        for vdd in ("%g" % point.vdd, "%.1f" % point.vdd, "%.2f" % point.vdd):
            row = table.get((point.corner, temp, vdd))
            if row is not None:
                return row
    return None


def _twin(row, code):
    raw = row.get("twin_c%d" % code)
    return None if raw in (None, "") else float(raw)


def _step_fraction(row):
    """The measured geometric per-code step of this bundle's window ladder.

    Not a nominal 4.7 %: the geometric mean of t_win(c+1)/t_win(c) over the
    fifteen adjacent pairs of the committed map, at this bundle's own point.
    """
    vals = [_twin(row, c) for c in range(16)]
    if any(v is None or v <= 0 for v in vals):
        return None
    ratios = [vals[c + 1] / vals[c] for c in range(15)]
    return math.exp(sum(math.log(r) for r in ratios) / len(ratios)) - 1.0


def _tier(codes_err, kind, low, high):
    """Grade one tier, refusing to turn an unresolved ladder into a PASS.

    A *bound* can still FAIL conclusively -- if the least unfavourable value
    consistent with the data is already outside the tier, every value consistent
    with it is too. It can never PASS: the true threshold is on the far side of
    the bound, so a bound inside the tier says nothing.
    """
    if codes_err is None:
        return "n/a"
    err = round(codes_err)
    inside = low <= err <= high
    if kind == "bracketed":
        return "PASS" if inside else "FAIL"
    if kind == "lower_bound":
        # theta is larger than reported -> t_flag_meas larger -> code_err more
        # negative. Already below `low` means conclusively out.
        return "FAIL" if err < low else "unresolved"
    if kind == "upper_bound":
        return "FAIL" if err > high else "unresolved"
    return "unresolved"


def _by_bundle(run):
    groups = {}
    for p in run.points:
        groups.setdefault(p.corner, []).append(p)
    return groups


def _threshold(points, positive):
    """Bracket the smallest |step| in one direction that deasserted LOCK.

    Returns (held, dropped) in seconds of |delta|: the largest magnitude that
    left LOCK asserted and the smallest that dropped it. Either may be None --
    no rung dropped it (the ladder did not reach the threshold), or the
    smallest rung already dropped it (the ladder did not bracket it from
    below). Both cases are reported as such rather than interpolated over.
    """
    held = None
    dropped = None
    for p in points:
        delta = _param(p, "delta")
        de = p.get("deasserted")
        if delta is None or de is None or delta == 0.0:
            continue
        if (delta > 0) != positive:
            continue
        mag = abs(delta)
        if de >= 0.5:
            if dropped is None or mag < dropped:
                dropped = mag
        else:
            if held is None or mag > held:
                held = mag
    # A ladder is only a bracket if every rung below the drop held.
    if held is not None and dropped is not None and held > dropped:
        held = max((m for m in
                    (abs(_param(p, "delta")) for p in points
                     if _param(p, "delta") is not None
                     and (_param(p, "delta") > 0) == positive
                     and (p.get("deasserted") or 0) < 0.5)
                    if m < dropped), default=None)
    return held, dropped


def derive_tables(run):
    groups = _by_bundle(run)
    tables = []

    # ---------------------------------------------------------------- ladder
    rows = []
    for bundle in sorted(groups):
        pts = sorted(groups[bundle], key=lambda p: (_param(p, "delta") or 0.0))
        for p in pts:
            rows.append((
                bundle,
                fmt_scalar(_code_of(p), "%d"),
                fmt_scalar((_param(p, "delta") or 0.0) * 1e12, "%.0f"),
                fmt_scalar((p.get("delta_err") or 0.0) * 1e12, "%.2f"),
                fmt_scalar(p.get("lock_pre"), "%.4g"),
                fmt_scalar(p.get("lock_min"), "%.4g"),
                "yes" if (p.get("deasserted") or 0) >= 0.5 else "no",
                fmt_scalar(p.get("vwin_pre"), "%.4g"),
                fmt_scalar(p.get("vwin_min"), "%.4g"),
                fmt_scalar(p.get("deassert_lat_ns"), "%.3g"),
                fmt_scalar(p.get("dip_ns"), "%.3g"),
                fmt_scalar((_f(p, "phi_pre") or 0.0) * 1e9, "%.4f"),
                fmt_scalar((p.get("skew_pw") or 0.0) * 1e9, "%.4f"),
                fmt_scalar((p.get("phi_drift") or 0.0) * 1e12, "%.1f"),
            ))
    tables.append(DerivedTable(
        name="step_ladder",
        description=(
            "every rung of the phase-step ladder: what the stimulus was asked for, what it "
            "achieved, whether the LOCK pad dropped, how far the detector's integrator got, "
            "and the loop's own static offset at the instant of the step"
        ),
        notes=(
            "delta_ps is the signed phase step applied to REF (positive = REF retarded). "
            "delta_err_ps is the achieved step minus the requested one -- a stimulus check, "
            "not a result.",
            "deasserted is the procedure's own observable, taken from the LOCK pad at half "
            "rail. vwin_pre/vwin_min are the detector's integrator node, reported because they "
            "explain a threshold that does not reproduce t_flag; they are not available to a "
            "tester.",
            "deassert_lat_ns and dip_ns are blank at a rung where LOCK never dropped, which is "
            "the expected outcome below threshold rather than a missing measurement.",
            "phi_pre_ns is the REF -> FB skew over the last two pre-step reference cycles and "
            "skew_pw_ns is the same quantity from the PFD's UP/DN pulse-width difference. "
            "phi_drift_ps is that skew minus its value ten reference cycles earlier: how far "
            "from stationary the offset still was when the step arrived.",
        ),
        columns=("bundle", "code", "delta_ps", "delta_err_ps", "lock_pre_v", "lock_min_v",
                 "deasserted", "vwin_pre_v", "vwin_min_v", "deassert_lat_ns", "dip_ns",
                 "phi_pre_ns", "skew_pw_ns", "phi_drift_ps"),
        rows=tuple(rows),
    ))

    # ------------------------------------------------------------ thresholds
    thresh_rows = []
    verdict_rows = []
    for bundle in sorted(groups):
        pts = groups[bundle]
        ref_pt = pts[0]
        code = _code_of(ref_pt)
        row = _winmap_row(run, ref_pt)
        twin = _twin(row, code) if row is not None and code is not None else None
        step = _step_fraction(row) if row is not None else None
        ref_lo = None if twin is None else twin * (1.0 + DELTA_MIN)
        ref_hi = None if twin is None else twin * (1.0 + DELTA_MAX)
        t_flag_ref = None if twin is None else 0.5 * (ref_lo + ref_hi)

        held_p, drop_p = _threshold(pts, True)
        held_m, drop_m = _threshold(pts, False)

        # A ladder resolves one of exactly three things per direction, and the
        # three are not interchangeable. Reporting an unbracketed threshold as a
        # midpoint with a huge half-width invites a reader to use the midpoint;
        # naming the kind does not.
        #   bracketed    -- a rung held and a larger one dropped: theta is the
        #                   midpoint, hw the half-width.
        #   lower_bound  -- every rung held: theta > the largest of them. The
        #                   value reported is that bound, which is the LEAST
        #                   unfavourable value consistent with the data.
        #   upper_bound  -- the smallest rung already dropped: theta <= it.
        def resolve(held, drop):
            if held is not None and drop is not None:
                return 0.5 * (held + drop), 0.5 * (drop - held), "bracketed"
            if drop is None and held is not None:
                return held, None, "lower_bound"
            if held is None and drop is not None:
                return drop, None, "upper_bound"
            return None, None, "none"

        th_p, hw_p, kind_p = resolve(held_p, drop_p)
        th_m, hw_m, kind_m = resolve(held_m, drop_m)

        t_flag = phi_der = t_flag_hw = None
        t_flag_kind = "none"
        if th_p is not None and th_m is not None:
            t_flag = 0.5 * (th_p + th_m)
            if kind_p == kind_m == "bracketed":
                t_flag_kind = "bracketed"
                t_flag_hw = 0.5 * ((hw_p or 0.0) + (hw_m or 0.0))
                phi_der = 0.5 * (th_m - th_p)
            elif kind_p == kind_m == "lower_bound":
                t_flag_kind = "lower_bound"
            elif kind_p == kind_m == "upper_bound":
                t_flag_kind = "upper_bound"
            else:
                t_flag_kind = "mixed_bound"

        phi_meas = _f(ref_pt, "phi_pre")
        # The baseline rung (delta = 0) is the one whose pre-step read is not
        # contaminated by anything; every rung shares the same pre-step
        # transient, but read the baseline's when it is there.
        for p in pts:
            if _param(p, "delta") == 0.0 and _f(p, "phi_pre") is not None:
                phi_meas = _f(p, "phi_pre")
                break

        codes_err = codes_err_hw = codes_err_ref = None
        if t_flag is not None and t_flag_ref and step:
            # A tester who measures t_flag high thinks the chain is slower than
            # it is and programs a LOWER code; the sign convention here is
            # "codes the tester lands away from the rule's code".
            codes_err = -math.log(t_flag / t_flag_ref) / math.log(1.0 + step)
            codes_err_hw = (None if t_flag_hw is None
                            else (t_flag_hw / t_flag_ref) / math.log(1.0 + step))
            # How much of the verdict's own width is the REFERENCE's, not the
            # measurement's: the committed flag-to-chain excess is a +1.4..+7.0 %
            # interval, and half that interval converts to codes here. A verdict
            # is never sharper than this, whatever the ladder resolves to.
            codes_err_ref = (0.5 * math.log((1.0 + DELTA_MAX) / (1.0 + DELTA_MIN))
                             / math.log(1.0 + step))

        thresh_rows.append((
            bundle,
            fmt_scalar(code, "%d"),
            t_flag_kind,
            fmt_scalar(None if held_p is None else held_p * 1e12, "%.0f"),
            fmt_scalar(None if drop_p is None else drop_p * 1e12, "%.0f"),
            fmt_scalar(None if th_p is None else th_p * 1e12, "%.1f"),
            fmt_scalar(None if hw_p is None else hw_p * 1e12, "%.1f"),
            fmt_scalar(None if held_m is None else held_m * 1e12, "%.0f"),
            fmt_scalar(None if drop_m is None else drop_m * 1e12, "%.0f"),
            fmt_scalar(None if th_m is None else th_m * 1e12, "%.1f"),
            fmt_scalar(None if hw_m is None else hw_m * 1e12, "%.1f"),
            fmt_scalar(None if t_flag is None else t_flag * 1e9, "%.4f"),
            fmt_scalar(None if t_flag_hw is None else t_flag_hw * 1e12, "%.1f"),
            fmt_scalar(None if ref_lo is None else ref_lo * 1e9, "%.4f"),
            fmt_scalar(None if ref_hi is None else ref_hi * 1e9, "%.4f"),
            fmt_scalar(None if (t_flag is None or not t_flag_ref)
                       else (t_flag / t_flag_ref - 1.0) * 100.0, "%.2f"),
            "n/a" if (t_flag is None or ref_lo is None) else
            ("yes" if ref_lo <= t_flag <= ref_hi else "no"),
            fmt_scalar(None if phi_der is None else phi_der * 1e9, "%.4f"),
            fmt_scalar(None if phi_meas is None else phi_meas * 1e9, "%.4f"),
            fmt_scalar(None if (phi_der is None or phi_meas is None)
                       else (phi_der - phi_meas) * 1e12, "%.1f"),
        ))

        one_step_ps = None if (t_flag_ref is None or step is None) else t_flag_ref * step * 1e12
        verdict_rows.append((
            bundle,
            fmt_scalar(code, "%d"),
            fmt_scalar(None if step is None else step * 100.0, "%.2f"),
            fmt_scalar(one_step_ps, "%.1f"),
            fmt_scalar(None if one_step_ps is None else one_step_ps / 2.0, "%.1f"),
            fmt_scalar(None if t_flag_hw is None else t_flag_hw * 1e12, "%.1f"),
            t_flag_kind,
            fmt_scalar(codes_err, "%+.2f"),
            fmt_scalar(codes_err_hw, "%.2f"),
            fmt_scalar(codes_err_ref, "%.2f"),
            fmt_scalar(None if codes_err is None else round(codes_err), "%+d"),
            _tier(codes_err, t_flag_kind, TIER_A_LOW, TIER_A_HIGH),
            _tier(codes_err, t_flag_kind, -TIER_B_MAX_ABS, TIER_B_MAX_ABS),
        ))

    tables.append(DerivedTable(
        name="bisection_thresholds",
        description=(
            "the procedure executed, per bundle: the bracketed phase-step threshold in each "
            "direction, and the two quantities the symmetric pair is supposed to yield -- "
            "t_flag with the static offset cancelled, and the static offset itself -- each "
            "against its own committed reference"
        ),
        notes=(
            "held_ps / dropped_ps are the largest |step| that left LOCK asserted and the "
            "smallest that dropped it. resolution says which of three things the ladder "
            "actually resolved, and the three are not interchangeable: `bracketed` (a rung held "
            "and a larger one dropped -- theta_ps is the midpoint and hw_ps its half-width), "
            "`lower_bound` (every rung held -- theta_ps is the largest of them and the true "
            "threshold is ABOVE it, so every derived number is the least unfavourable value "
            "consistent with the data), or `upper_bound` (the smallest rung already dropped). "
            "hw_ps is blank for a bound, because a bound has no half-width.",
            "t_flag_meas_ns = (theta+ + theta-)/2, the procedure's estimate with the loop's "
            "static offset cancelled. t_flag_ref_lo_ns .. t_flag_ref_hi_ns is what the flag "
            "window at this point is KNOWN to be from committed evidence: t_win x [1.014, "
            "1.070], t_win from sim/lock-window-proxy's committed 16-code map and the interval "
            "the flag-to-chain excess spec/pll.md measures (+1.4 .. +7.0 % over the grid). "
            "err_pct is the measurement against that interval's midpoint; in_ref_interval says "
            "whether it falls inside the interval at all. DR-022 Decision 2's corollary is why "
            "this is an interval and not 1.037 x t_win: the ratio's own 1.055x spread is worth "
            "1.2-2.0 codes, so a route that divides by the constant fails Tier B on the "
            "conversion before making a measurement error of its own.",
            "phi_derived_ns = (theta- - theta+)/2, the static offset the SAME symmetric pair "
            "yields as a by-product. phi_measured_ns is the same run's directly-measured "
            "REF -> FB skew at the instant of the step. Their difference is the direct test of "
            "issue #527 checkbox 3: if the +/- cancellation holds, these agree; if the loop's "
            "own asymmetric UP/DN correction breaks it, this is where it shows.",
        ),
        columns=("bundle", "code", "resolution",
                 "held_plus_ps", "dropped_plus_ps", "theta_plus_ps", "hw_plus_ps",
                 "held_minus_ps", "dropped_minus_ps", "theta_minus_ps", "hw_minus_ps",
                 "t_flag_meas_ns", "t_flag_hw_ps", "t_flag_ref_lo_ns", "t_flag_ref_hi_ns",
                 "err_pct", "in_ref_interval",
                 "phi_derived_ns", "phi_measured_ns", "phi_diff_ps"),
        rows=tuple(thresh_rows),
    ))

    tables.append(DerivedTable(
        name="tier_verdict",
        description=(
            "the grading, in trim codes: the procedure's measurement error converted through "
            "the measured per-code step of that bundle's own window ladder, against DR-022 "
            "Decision 2's two accuracy tiers"
        ),
        notes=(
            "step_pct is the geometric mean of t_win(c+1)/t_win(c) over the fifteen adjacent "
            "pairs of the committed 16-code map at this bundle's own point -- the real step, "
            "not a nominal 4.7 %. one_step_ps is that fraction of the reference interval's "
            "midpoint: the "
            "picoseconds one trim code is worth here, and therefore what the instrument has "
            "to resolve. half_step_ps is the rounding budget the rule itself already spends.",
            "code_err is the continuous code offset a tester would land at, "
            "-ln(t_flag_meas / t_flag_ref) / ln(1 + step) against the reference interval's "
            "midpoint: positive means the procedure would make the tester program a code ABOVE "
            "the rule's. code_err_hw is the same conversion applied to the threshold bracket's "
            "half-width -- how much of code_err is the ladder's own resolution rather than a "
            "bias. code_err_ref_hw is the same conversion applied to the committed reference "
            "interval's half-width: no verdict here can be sharper than that, because the flag "
            "window at this point has only ever been bounded, never measured.",
            "Tier A (DR-022 Decision 2) preserves the ratified [1, 2] ns band if the code "
            "error is never more than 2 low or 3 high. Tier B preserves DR-013 Decision 4's "
            "<= 1.65x spread target only if the worst code error over the process population "
            "is exactly ZERO -- the rule's own rounding already spends all but 0.53-0.92 of "
            "one trim step of that allowance. The two are separate outcomes and both are "
            "reported: a procedure that holds the band but not the spread is a different "
            "finding from one that holds neither, and it changes which of DR-022 Decision 5's "
            "routes is the right next step.",
            "Three bundles at one temperature and one supply are not the process population "
            "Tier B is defined over. A FAIL here is conclusive (one bundle is enough to break "
            "a zero-error requirement); a PASS here is necessary and not sufficient, and the "
            "record says so rather than claiming the tier is met.",
        ),
        columns=("bundle", "code", "step_pct", "one_step_ps", "half_step_ps",
                 "t_flag_hw_ps", "resolution", "code_err", "code_err_hw", "code_err_ref_hw",
                 "code_err_rounded", "tier_a", "tier_b"),
        rows=tuple(verdict_rows),
    ))

    return tables
