"""divider-ratio-chain's reductions: the ratio pass/fail, and retiming_margin.csv.

Ports the awk reductions ``sim/divider-ratio/testbench/run.sh`` (pre-harness)
applied per point and per run:

- ``ratio_pass`` -- both the retimed-FB and the un-retimed DIVOUT period must
  read the point's own programmed N to within 0.05 (an order of magnitude
  inside the 0.5 that would confuse N with N+-1, and an order of magnitude
  outside the ``.measure`` interpolation resolution).
- ``fbpw_s`` -- FB high time, sign-corrected the same way tb_div23_cell's
  pulse widths are: a negative raw ``fall - rise`` means the DC operating
  point started the chain in the state that reads the edges one period apart
  in the other order, and adding N output periods back is exact, not a fudge.
- ``retiming_margin`` -- the cross-record join: setup_margin = T_vco - t_arr
  - t_setup and hold_margin = t_arr - t_hold, evaluated only at the N=64 /
  200 MHz points (DR-001's own worst-case selection), with t_setup / t_hold
  joined from sim/divider-ratio-dff's ``dff_setup_hold`` derived table at the
  same (process, temp_c, vdd_v).
"""

from __future__ import annotations

from harness.derived import DerivedTable

#: A divide ratio is an integer; this separates N from N+-1 with an order of
#: magnitude to spare on both sides of the 0.5 midpoint (see the module
#: docstring), matching the pre-harness runner's tolerance exactly.
_RATIO_TOL = 5e-2


def _near(value, target) -> bool:
    return value is not None and abs(value - target) < _RATIO_TOL


def derive_point(point):
    kn = point.params.get("kn")
    kf = point.params.get("kf")
    out: dict[str, float] = {}
    if kn is not None:
        n = float(kn)
        out["n_target"] = n
        n_fb = point.get("n_fb")
        ndo = point.get("ndo")
        out["ratio_pass"] = 1.0 if (_near(n_fb, n) and _near(ndo, n)) else 0.0

        if kf is not None:
            tvco = 1.0 / float(kf)
            fbpw = point.get("fbpw")
            if fbpw is not None:
                out["fbpw_s"] = fbpw + n * tvco if fbpw < 0 else fbpw
    return out


def derive_tables(run):
    dff = run.join("dff").index_by("process", "temp_c", "vdd_v")
    rows = []
    for point in run.points:
        # DR-001's own worst-case selection: the retiming budget is only ever
        # evaluated at the 200 MHz v1 ceiling with the longest chain (N=64).
        if point.axes.get("point") != "f200n64":
            continue
        key = (point.corner, f"{point.temp_c:g}", f"{point.vdd:.2f}")
        prior = dff.get(key)
        if prior is None:
            continue
        t_arr = point.get("t_arr")
        kf = point.params.get("kf")
        if t_arr is None or kf is None:
            continue
        tvco = 1.0 / float(kf)
        tsetup = float(prior["tsetup_s"])
        thold = float(prior["thold_s"])
        setup_margin = tvco - t_arr - tsetup
        hold_margin = t_arr - thold
        rows.append(
            (
                point.corner,
                point.temp_c,
                point.vdd,
                f"{t_arr:.6g}",
                f"{tsetup:.6g}",
                f"{thold:.6g}",
                f"{tvco:.6g}",
                f"{setup_margin:.6g}",
                f"{hold_margin:.6g}",
                "CLOSES" if (setup_margin > 0 and hold_margin > 0) else "FAILS",
            )
        )
    return [
        DerivedTable(
            name="retiming_margin",
            description=(
                "setup_margin_s = T_vco - t_arr_s - tsetup_s and hold_margin_s = "
                "t_arr_s - thold_s at N=64 (k=6), kf=200 MHz, joined against "
                "sim/divider-ratio-dff's per-PVT tsetup_s/thold_s"
            ),
            columns=(
                "process", "temp_c", "vdd_v", "t_arr_s", "tsetup_s", "thold_s",
                "tvco_s", "setup_margin_s", "hold_margin_s", "verdict",
            ),
            rows=tuple(rows),
        )
    ]
