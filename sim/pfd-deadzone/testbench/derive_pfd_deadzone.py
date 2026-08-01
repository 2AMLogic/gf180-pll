"""pfd-deadzone reductions -- the per-corner dead-zone verdict.

Dead-zone freedom is a property of a *family* of five dphi points at one PVT
corner together (the near pair, the wide pair, and zero), not of any single
point's own measurements -- so this lives entirely in ``derive_tables()``,
which is the only hook the harness hands whole-run visibility (``run.points``)
to. There is no ``derive_point()`` here: qnet/width_up/width_dn are plain
``raw_measures`` (a `.measure ... integ`, a `param=` quotient, and two
`trig`/`targ` widths), needing no per-point reduction.

Per pre-migration sim/pfd-deadzone/testbench/run.sh:
    kd_near = [q(+200ps) - q(-200ps)] / 400ps   (gain AT the lock point)
    kd_wide = [q(+1ns)   - q(-1ns)  ] / 2ns      (gain well away from it)
    ratio   = kd_near / kd_wide                  (1.0 = perfectly linear;
                                                   a dead zone drives it to 0)
    wmin    = min(width_up, width_dn) at dphi=0  (the PFD reset delay)
    t_offset = -q(0) / kd_wide                   (static phase offset the
                                                   residual charge implies)
verdict: PASS iff ratio > 0.5 and width_up(0) > 0 and width_dn(0) > 0.
"""

from __future__ import annotations

from harness.derived import DerivedTable

# The exact five dphi sweep-axis point ids this campaign declares.
DPHI_NEAR_HI = "200p"
DPHI_NEAR_LO = "-200p"
DPHI_WIDE_HI = "1n"
DPHI_WIDE_LO = "-1n"
DPHI_ZERO = "0"
DPHI_POINTS = (DPHI_WIDE_LO, DPHI_NEAR_LO, DPHI_ZERO, DPHI_NEAR_HI, DPHI_WIDE_HI)


def _fmt(x: float) -> str:
    return "%.6g" % x


def derive_tables(run):
    groups: dict[tuple, dict[str, object]] = {}
    order: list[tuple] = []
    for point in run.points:
        dphi = point.axes.get("dphi")
        if dphi is None:
            continue
        key = (point.corner, point.temp_c, point.vdd)
        if key not in groups:
            groups[key] = {}
            order.append(key)
        groups[key][dphi] = point

    rows = []
    n_checked = 0
    n_fail = 0
    worst_ratio = None
    worst_key = None
    for key in order:
        pts = groups[key]
        if not all(d in pts for d in DPHI_POINTS):
            continue  # an incomplete group (a run failure) contributes no row
        q = {d: pts[d].get("qnet") for d in DPHI_POINTS}
        if any(v is None for v in q.values()):
            continue
        kd_near = (q[DPHI_NEAR_HI] - q[DPHI_NEAR_LO]) / 400e-12
        kd_wide = (q[DPHI_WIDE_HI] - q[DPHI_WIDE_LO]) / 2e-9
        ratio = kd_near / kd_wide if kd_wide else 0.0
        wu0 = pts[DPHI_ZERO].get("width_up")
        wd0 = pts[DPHI_ZERO].get("width_dn")
        widths = [w for w in (wu0, wd0) if w is not None]
        wmin = min(widths) if widths else None
        qoff = q[DPHI_ZERO]
        toff = -qoff / kd_wide if kd_wide else 0.0

        n_checked += 1
        ok = ratio > 0.5 and (wu0 or 0.0) > 0.0 and (wd0 or 0.0) > 0.0
        if not ok:
            n_fail += 1
        if worst_ratio is None or ratio < worst_ratio:
            worst_ratio = ratio
            worst_key = key

        corner, temp_c, vdd = key
        corner_id = f"{corner}_{temp_c:g}c_{vdd:.2f}v"
        rows.append(
            (
                corner_id,
                _fmt(kd_near),
                _fmt(kd_wide),
                "%.4f" % ratio,
                _fmt(wmin) if wmin is not None else "",
                _fmt(qoff),
                _fmt(toff),
                "PASS" if ok else "FAIL",
            )
        )

    notes = [
        f"{n_checked} PVT corner(s) checked; {n_fail} corner(s) failed the "
        "dead-zone criterion (ratio > 0.5 AND non-zero UP and DN pulse at "
        "dphi = 0).",
    ]
    if worst_key is not None:
        wcorner, wtemp, wvdd = worst_key
        notes.append(
            f"Worst linearity ratio: {worst_ratio:.4f} at "
            f"`{wcorner}_{wtemp:g}c_{wvdd:.2f}v`."
        )

    return [
        DerivedTable(
            name="pfd_deadzone_verdict",
            description=(
                "per-corner dead-zone verdict: kd_near/kd_wide ratio through "
                "dphi = 0, the PFD reset delay (wmin_zero), and the residual "
                "charge offset (q_zero) / equivalent static phase offset "
                "(t_offset) at zero phase error"
            ),
            columns=(
                "corner_id",
                "kd_near_a",
                "kd_wide_a",
                "ratio",
                "wmin_zero_s",
                "q_zero_c",
                "t_offset_s",
                "verdict",
            ),
            rows=tuple(rows),
            notes=tuple(notes),
        )
    ]
