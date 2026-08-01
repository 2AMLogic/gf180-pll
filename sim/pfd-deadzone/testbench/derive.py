"""pfd-deadzone reductions: the per-corner dead-zone verdict.

The claim this campaign answers is not any single measured number -- it is a
*ratio* of two detector gains, each of which is a difference of two integrated
charges taken at different phase offsets.  This module reproduces, measurement
for measurement, what the pre-migration `testbench/run.sh` computed in awk over
`pfd_deadzone.csv`:

    kd_near  = [q(+200ps) - q(-200ps)] / 400ps   detector gain AT the lock point
    kd_wide  = [q(+1ns)   - q(-1ns)  ] / 2ns     gain well away from it
    ratio    = kd_near / kd_wide                 1.0 = linear; a dead zone -> 0
    wmin_zero= min(width_up, width_dn) at dphi=0 = the PFD reset delay
    q_zero   = net charge per reference cycle at dphi=0 (the residual offset)
    t_offset = -q_zero / kd_wide                 the static phase offset that
                                                 nulls that residual charge

Two of those -- `wmin_zero` and `q_zero` -- are properties of the dphi = 0
point alone, so they are emitted by :func:`derive_point` as ordinary per-point
measurements and the manifest's `checks` gate them directly.  The three that
difference charge ACROSS dphi points (`kd_near`, `kd_wide`, `ratio`, and the
`t_offset` that divides by `kd_wide`) cannot be per-point on a grid that runs
one invocation per (corner, dphi); they are reduced per corner in
:func:`derive_tables`, which carries its own explicit per-corner `verdict`
column rather than folding the dead-zone question into the record's overall
pass/fail.
"""

from harness.derived import DerivedTable

#: The dphi axis, as the manifest declares it: (sweep point id, the label the
#: pre-migration CSV used, the offset in seconds).
DPHI_POINTS = (
    ("d-1n", "-1n", -1e-9),
    ("d-200p", "-200p", -200e-12),
    ("d0", "0", 0.0),
    ("d200p", "200p", 200e-12),
    ("d1n", "1n", 1e-9),
)

#: The manifest's name for the dphi sweep axis.
AXIS = "d"
#: The sweep point at zero phase error.
ZERO_POINT = "d0"

#: The two differencing intervals, in seconds.
NEAR_SPAN = 400e-12
WIDE_SPAN = 2e-9


def derive_point(point):
    """`wmin_zero` and `q_zero` -- the two verdict quantities that are local.

    Both are defined only at zero phase error, so every other dphi point
    returns nothing and is recorded `not measured`.  That is deliberate: it is
    what makes `min_measured_points = 45` a real check that every one of the
    45 PVT corners produced a zero-phase pulse.
    """
    if point.axes.get(AXIS) != ZERO_POINT:
        return {}

    out = {}

    # The residual up/down asymmetry the loop has to null out as static phase
    # error.  A point whose charge integral failed is left unset rather than
    # defaulted -- "did not measure" and "measured zero" are different facts,
    # and zero is the *ideal* value here.
    q_zero = point.get("qnet")
    if q_zero is not None:
        out["q_zero"] = q_zero

    # width_up / width_dn are `optional`: a real dead zone produces no pulse to
    # measure at all.  Absent means "no pulse", which must fail the record --
    # so leave the measure unset and let min_measured_points catch it, rather
    # than coercing a 0 that a `min` check would have to special-case.
    w_up = point.get("width_up")
    w_dn = point.get("width_dn")
    if w_up is not None and w_dn is not None:
        out["wmin_zero"] = min(w_up, w_dn)
    return out


def _corner_key(point):
    """`ff/125C/3.63V` -- the key the pre-migration verdict CSV used."""
    return f"{point.corner}/{point.temp_c:g}C/{point.vdd:.2f}V"


def _fmt(value, spec="%.6g"):
    return "" if value is None else spec % value


def derive_tables(run):
    """The two CSVs the pre-migration record cited, rebuilt from the same data."""
    label_of = {pid: label for pid, label, _ in DPHI_POINTS}
    order_of = {pid: i for i, (pid, _, _) in enumerate(DPHI_POINTS)}

    # Group the run's points by PVT corner, keeping the dphi axis inside.
    corners = {}
    for point in run.points:
        corners.setdefault(_corner_key(point), {})[point.axes.get(AXIS)] = point

    per_point_rows = []
    verdict_rows = []
    for key, by_dphi in corners.items():
        sample = next(iter(by_dphi.values()))
        for point_id in sorted(by_dphi, key=lambda p: order_of.get(p, 99)):
            point = by_dphi[point_id]
            per_point_rows.append(
                (
                    point.corner,
                    f"{point.temp_c:g}",
                    f"{point.vdd:.2f}",
                    label_of.get(point_id, point_id),
                    _fmt(point.get("qnet")),
                    _fmt(point.get("width_up")),
                    _fmt(point.get("width_dn")),
                )
            )

        q = {pid: p.get("qnet") for pid, p in by_dphi.items()}
        have = all(q.get(pid) is not None for pid, _, _ in DPHI_POINTS)
        if have:
            kd_near = (q["d200p"] - q["d-200p"]) / NEAR_SPAN
            kd_wide = (q["d1n"] - q["d-1n"]) / WIDE_SPAN
            # kd_wide == 0 is a total dead zone, not a division to fudge around:
            # 0.0 is the correct ratio to report, and it fails the criterion.
            ratio = kd_near / kd_wide if kd_wide else 0.0
        else:
            kd_near = kd_wide = ratio = None

        zero = by_dphi.get(ZERO_POINT)
        w_min = zero.get("wmin_zero") if zero is not None else None
        q_zero = zero.get("q_zero") if zero is not None else None
        t_offset = (
            -q_zero / kd_wide
            if (q_zero is not None and kd_wide)
            else (0.0 if (q_zero is not None and kd_wide == 0) else None)
        )
        passed = (
            ratio is not None
            and ratio > 0.5
            and w_min is not None
            and w_min > 0.0
        )
        verdict_rows.append(
            (
                key,
                _fmt(kd_near),
                _fmt(kd_wide),
                _fmt(ratio, "%.4f"),
                _fmt(w_min),
                _fmt(q_zero),
                _fmt(t_offset),
                "pass" if passed else "FAIL",
            )
        )
        del sample

    nfail = sum(1 for row in verdict_rows if row[-1] == "FAIL")
    ratios = [float(row[3]) for row in verdict_rows if row[3]]
    worst = min(ratios) if ratios else None
    worst_at = ""
    if worst is not None:
        worst_at = next(row[0] for row in verdict_rows if row[3] and float(row[3]) == worst)

    return [
        DerivedTable(
            name="pfd_deadzone",
            description=(
                "net charge per reference cycle and UP/DN pulse width at every "
                "(PVT corner, phase offset) point -- the raw evidence the "
                "per-corner verdict reduces"
            ),
            notes=(
                "ref period 40 ns (25 MHz, the top of DR-002's ratified 1-25 MHz v1 range)",
                "vctrl held at 1.65 V; Icp trim code b1b0=10 (3 unit legs)",
                "dphi_s: FB-relative-to-REF phase offset (s)",
                "qnet_c: net charge delivered to the control node per reference cycle (C), "
                "positive = pump sourcing.  This is the dead-zone-critical quantity.",
                "width_up_s/width_dn_s: UP/DN pulse width (s) at the per-corner mid-supply "
                "crossing, third reference cycle.  Their MINIMUM at dphi = 0 is the PFD "
                "reset delay that #11's retiming pulse must be at least as wide as.  An "
                "empty cell is an `optional` measurement that did not fire -- i.e. that "
                "polarity never crossed mid-supply at all, which the pre-migration runner "
                "spelled as a literal 0.",
            ),
            columns=(
                "process",
                "temp_c",
                "vdd_v",
                "dphi_s",
                "qnet_c",
                "width_up_s",
                "width_dn_s",
            ),
            rows=tuple(per_point_rows),
        ),
        DerivedTable(
            name="pfd_deadzone_verdict",
            description=(
                "per-corner dead-zone verdict and residual charge offset -- "
                f"{len(verdict_rows)} corner(s) checked, {nfail} FAILED"
                + (
                    f"; worst linearity ratio {worst:.4f} at {worst_at}"
                    if worst is not None
                    else ""
                )
            ),
            notes=(
                "kd_near_a: charge-pump gain at the lock point, [q(+200ps)-q(-200ps)]/400ps (A)",
                "kd_wide_a: same, measured out at +/-1 ns (A)",
                "ratio: kd_near / kd_wide -- 1.0 is perfectly linear through zero, a dead "
                "zone drives it toward 0.  Acceptance: > 0.5 at every corner.",
                "wmin_zero_s: smaller of the two UP/DN pulse widths at dphi=0 (s) = PFD reset delay",
                "q_zero_c: net charge per reference cycle at dphi=0 (C) -- the residual "
                "up/down asymmetry the loop must null out",
                "t_offset_s: static phase offset that nulls it, -q_zero/kd_wide (s)",
                "verdict: pass iff ratio > 0.5 AND both UP and DN pulse at dphi = 0 -- "
                "the dead-zone-freedom criterion, stated per corner rather than folded "
                "into the record's overall pass/fail",
            ),
            columns=(
                "corner",
                "kd_near_a",
                "kd_wide_a",
                "ratio",
                "wmin_zero_s",
                "q_zero_c",
                "t_offset_s",
                "verdict",
            ),
            rows=tuple(verdict_rows),
        ),
    ]
