"""pfd-deadzone (operating point) reductions: t_offset across the control window.

This is `testbench/derive.py`'s `t_offset` reduction, computed per **(PVT
corner, control voltage)** instead of per PVT corner, and with the parent
module's dead-zone half deliberately absent.

    kd_wide  = [q(+1ns) - q(-1ns)] / 2ns   detector gain well outside the
                                           PFD's reset window
    q_zero   = net charge per reference cycle at dphi = 0 -- the residual
                                           up/down asymmetry the loop must null
    t_offset = -q_zero / kd_wide           the static phase offset at the PFD
                                           inputs that nulls that residual

`q_zero` is a property of the dphi = 0 point alone, so it is emitted by
:func:`derive_point` as an ordinary per-point measurement and the manifest's
`checks` gates it directly (`min_measured_points = 135` = 45 corners x 3
control voltages, so a point that lost its zero-phase charge integral fails the
record rather than quietly dropping a row). `kd_wide` and `t_offset` difference
charge ACROSS dphi points and cannot be per-point on a grid that runs one
invocation per (corner, control voltage, dphi); they are reduced in
:func:`derive_tables`.

**What is NOT here, and why.** The parent module computes `kd_near`, `ratio`
and `wmin_zero` and carries a per-corner dead-zone `verdict`. The dead-zone
claim is the parent manifest's (#9) and is already answered across the full
45-corner grid; this manifest sweeps neither the near pair that `ratio` needs
nor any quantity a dead-zone verdict could rest on, so it computes none and
claims none. Emitting a `verdict` column that was not derived from the
dead-zone criterion would invite exactly the misreading `sim/README.md`'s
no-fabricated-evidence rule exists to prevent.
"""

from harness.derived import DerivedTable, fmt_scalar

#: The dphi axis, as the manifest declares it: (sweep point id, label, seconds).
DPHI_POINTS = (
    ("d-1n", "-1n", -1e-9),
    ("d0", "0", 0.0),
    ("d1n", "1n", 1e-9),
)

#: The control-voltage axis, as the manifest declares it: (point id, volts).
VCTRL_POINTS = (
    ("v0p90", 0.90),
    ("v1p65", 1.65),
    ("v2p40", 2.40),
)

#: Manifest names for the two sweep axes.
DPHI_AXIS = "d"
VCTRL_AXIS = "vc"
#: The sweep point at zero phase error.
ZERO_POINT = "d0"
#: The gain-differencing interval, in seconds.
WIDE_SPAN = 2e-9


def derive_point(point):
    """`q_zero` -- the one verdict quantity that is local to a single point.

    Defined only at zero phase error, so every other dphi point returns nothing
    and is recorded `not measured`. That is what makes the manifest's
    `min_measured_points = 135` a real check that all 45 corners produced a
    zero-phase charge integral at all three control voltages.
    """
    if point.axes.get(DPHI_AXIS) != ZERO_POINT:
        return {}

    q_zero = point.get("qnet")
    if q_zero is None:
        # "did not measure" and "measured zero" are different facts, and zero
        # is the IDEAL value here -- defaulting would turn a lost point into a
        # perfect one. Leave it unset and let min_measured_points catch it.
        return {}
    return {"q_zero": q_zero}


def _corner_key(point):
    """`ff/125C/3.63V` -- the key the parent manifest's verdict CSV uses."""
    return f"{point.corner}/{point.temp_c:g}C/{point.vdd:.2f}V"


def _vctrl_v(point):
    """This point's control voltage, from the axis id rather than re-parsed.

    Read from the manifest-declared axis table rather than from
    `point.params['vctrl']` so that the number in the CSV and the axis the
    manifest sweeps cannot drift apart silently: an axis id this module does
    not know about yields `None` and shows up as an empty cell, which is
    visible, rather than a plausible-looking value parsed out of a param string.
    """
    lookup = dict(VCTRL_POINTS)
    return lookup.get(point.axes.get(VCTRL_AXIS))


def derive_tables(run):
    """Per-point charge evidence, and the per-(corner, Vctrl) static offset."""
    label_of = {pid: label for pid, label, _ in DPHI_POINTS}
    order_of = {pid: i for i, (pid, _, _) in enumerate(DPHI_POINTS)}
    vctrl_order = {pid: i for i, (pid, _) in enumerate(VCTRL_POINTS)}

    # Group by (PVT corner, control voltage), keeping the dphi axis inside.
    cells = {}
    for point in run.points:
        key = (_corner_key(point), point.axes.get(VCTRL_AXIS))
        cells.setdefault(key, {})[point.axes.get(DPHI_AXIS)] = point

    per_point_rows = []
    offset_rows = []
    for key in sorted(
        cells, key=lambda k: (k[0], vctrl_order.get(k[1], 99))
    ):
        corner_key, vctrl_id = key
        by_dphi = cells[key]
        for point_id in sorted(by_dphi, key=lambda p: order_of.get(p, 99)):
            point = by_dphi[point_id]
            per_point_rows.append(
                (
                    point.corner,
                    f"{point.temp_c:g}",
                    f"{point.vdd:.2f}",
                    fmt_scalar(_vctrl_v(point), "%.2f"),
                    label_of.get(point_id, point_id),
                    fmt_scalar(point.get("qnet")),
                    fmt_scalar(point.get("width_up")),
                    fmt_scalar(point.get("width_dn")),
                )
            )

        q = {pid: p.get("qnet") for pid, p in by_dphi.items()}
        have_gain = q.get("d1n") is not None and q.get("d-1n") is not None
        kd_wide = (q["d1n"] - q["d-1n"]) / WIDE_SPAN if have_gain else None

        zero = by_dphi.get(ZERO_POINT)
        q_zero = zero.get("q_zero") if zero is not None else None
        # kd_wide == 0 would be a total dead zone; the parent manifest is what
        # rules that out, and it does at all 45 corners. Guarding here anyway
        # keeps a lost point from raising instead of reporting an empty cell.
        t_offset = (
            -q_zero / kd_wide
            if (q_zero is not None and kd_wide)
            else None
        )
        sample = next(iter(by_dphi.values()))
        offset_rows.append(
            (
                corner_key,
                fmt_scalar(_vctrl_v(sample), "%.2f"),
                fmt_scalar(kd_wide),
                fmt_scalar(q_zero),
                fmt_scalar(t_offset),
                fmt_scalar(abs(t_offset) * 1e9, "%.4f") if t_offset is not None else "",
            )
        )

    magnitudes = [float(row[5]) for row in offset_rows if row[5]]
    worst = max(magnitudes) if magnitudes else None
    worst_at = ""
    if worst is not None:
        worst_at = next(
            f"{row[0]} @ Vctrl={row[1]} V"
            for row in offset_rows
            if row[5] and float(row[5]) == worst
        )

    return [
        DerivedTable(
            name="pfd_operating_point",
            description=(
                "net charge per reference cycle and UP/DN pulse width at every "
                "(PVT corner, control voltage, phase offset) point -- the raw "
                "evidence the static-offset table reduces"
            ),
            notes=(
                "ref period 80 ns (12.5 MHz) -- sim/supply-sensitivity's own reference "
                "(100 MHz / N=8), NOT the parent manifest's 25 MHz",
                "Icp trim code b1b0=10 (3 unit legs), the nominal setting and the one "
                "sim/supply-sensitivity runs its closed loop at",
                "vctrl_v: control-node voltage, held by an ideal source (open loop)",
                "dphi_s: FB-relative-to-REF phase offset (s)",
                "qnet_c: net charge delivered to the control node per reference cycle (C), "
                "positive = pump sourcing",
                "width_up_s/width_dn_s: UP/DN pulse width (s) at the per-corner mid-supply "
                "crossing, third reference cycle. An empty cell is an `optional` "
                "measurement that did not fire -- that polarity never crossed mid-supply.",
            ),
            columns=(
                "process",
                "temp_c",
                "vdd_v",
                "vctrl_v",
                "dphi_s",
                "qnet_c",
                "width_up_s",
                "width_dn_s",
            ),
            rows=tuple(per_point_rows),
        ),
        DerivedTable(
            name="pfd_static_offset",
            description=(
                "static phase offset at the PFD inputs that nulls the pump's residual "
                f"charge -- {len(offset_rows)} (corner, control voltage) cell(s)"
                + (
                    f"; largest magnitude {worst:.4f} ns at {worst_at}"
                    if worst is not None
                    else ""
                )
            ),
            notes=(
                "kd_wide_a: detector gain well outside the reset window, "
                "[q(+1ns)-q(-1ns)]/2ns (A)",
                "q_zero_c: net charge per reference cycle at dphi = 0 (C) -- the residual "
                "up/down asymmetry the loop must null",
                "t_offset_s: the static phase offset that nulls it, -q_zero/kd_wide (s). "
                "This is the quantity spec/pll.md's static phase-offset budget calls the "
                "SYSTEMATIC term, measured here at the closed loop's own reference "
                "frequency and across DR-001 Decision 2's ratified control window.",
                "t_offset_abs_ns: |t_offset| in ns, for direct comparison against "
                "spec/pll.md's ratified 1 ns Lock criterion",
                "No dead-zone verdict column: this manifest does not sweep the near pair "
                "that criterion differences across, so it neither computes nor claims one "
                "(the parent manifest does, at all 45 corners).",
            ),
            columns=(
                "corner",
                "vctrl_v",
                "kd_wide_a",
                "q_zero_c",
                "t_offset_s",
                "t_offset_abs_ns",
            ),
            rows=tuple(offset_rows),
        ),
    ]
