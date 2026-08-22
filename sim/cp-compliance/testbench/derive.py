"""cp-compliance (DC bench) reductions.

Every number the pre-migration `testbench/run.sh` extracted in awk from
`iv_cp.dat` plus the two `SATLO`/`SATHI` operating-point lines is recomputed
here, index for index, from the same three files the deck now writes as
`raw_files`:

    iv_cp.dat   the 20 mV output characteristic of both polarities
    sat_lo.dat  |vds|/|vdsat| of the four verdict devices at Vctrl = 0.9 V
    sat_hi.dat  the same four devices at Vctrl = 2.4 V

The window endpoints are located on the sweep grid by the same nearest-index
rule the awk used (`int((target - v0)/dv + 0.5)`), not by interpolation, so a
migrated number is the same number and not a differently-rounded one.

Making these *derived per-point measurements* rather than a whole-run table is
what lets the manifest's `checks` gate the compliance verdict directly:
`satcasc_lo_v` / `satcasc_hi_v` must be positive at every corner and every trim
code, which is exactly the pre-migration acceptance criterion.
"""

from harness.derived import DerivedTable, fmt_scalar

#: trim-code sweep point id -> (b1, b0)
CODE_BITS = {
    "code00": (0, 0),
    "code01": (0, 1),
    "code10": (1, 0),
    "code11": (1, 1),
}
#: The manifest's name for the trim-code axis.
AXIS = "code"

#: The Vctrl window under test (DR-001 Decision 2 design intent).
V_LO = 0.9
V_MID = 1.65
V_HI = 2.4

#: The four devices `sat_lo.dat` / `sat_hi.dat` carry, in file order.
SAT_DEVICES = ("nbot", "ncasc", "ptop", "pcasc")
#: Devices the compliance verdict is taken over ...
CASCODES = ("ncasc", "pcasc")
#: ... and the ones reported for context only.
MIRRORS = ("nbot", "ptop")

#: The committed curve file keeps every 5th simulated point (20 mV -> 100 mV),
#: which still resolves both knees.
CURVE_DECIMATE = 5


def _sweep_index(target, v0, dv, n):
    """The awk `at()` rule: nearest sweep index, clamped to the sweep."""
    k = int((target - v0) / dv + 0.5)
    return 0 if k < 0 else (n - 1 if k > n - 1 else k)


def _sat_margins(raw, devices):
    """min(|vds| - |vdsat|) over `devices`, and the device that owns it.

    Returns ``(None, "")`` when the deck never wrote the file -- an operating
    point that did not solve is not a zero margin.
    """
    if not raw.exists():
        return None, ""
    rows = raw.rows()
    if not rows:
        return None, ""
    best = None
    best_name = ""
    for name in devices:
        vds = raw.column(f"{name}_vds")[0]
        vdsat = raw.column(f"{name}_vdsat")[0]
        margin = abs(vds) - abs(vdsat)
        if best is None or margin < best:
            best = margin
            best_name = name
    return best, best_name


def _extract(point):
    """Everything the awk computed for one (corner, trim code) point."""
    iv = point.raw("iv_cp.dat")
    if not iv.exists() or len(iv.rows()) < 10:
        return None

    v = iv.column("vsw")
    i_up = iv.column("i_up")
    i_dn = iv.column("i_dn")
    n = len(v)
    dv = (v[-1] - v[0]) / (n - 1)

    k_lo = _sweep_index(V_LO, v[0], dv, n)
    k_mid = _sweep_index(V_MID, v[0], dv, n)
    k_hi = _sweep_index(V_HI, v[0], dv, n)

    # Flatness of each polarity across the Vctrl window, as a percentage of its
    # mid-window value: the compliance evidence in current terms.  The worst
    # point-by-point mismatch inside the window is picked up in the same pass.
    up_win = i_up[k_lo : k_hi + 1]
    dn_win = i_dn[k_lo : k_hi + 1]
    mism_absmax = 0.0
    for a, b in zip(up_win, dn_win):
        mism = 100.0 * (a - b) / (0.5 * (a + b))
        if abs(mism) > abs(mism_absmax):
            mism_absmax = mism

    def mism_at(k):
        return 100.0 * (i_up[k] - i_dn[k]) / (0.5 * (i_up[k] + i_dn[k]))

    sat_lo_casc, sat_lo_dev = _sat_margins(point.raw("sat_lo.dat"), CASCODES)
    sat_hi_casc, sat_hi_dev = _sat_margins(point.raw("sat_hi.dat"), CASCODES)
    sat_lo_mir, _ = _sat_margins(point.raw("sat_lo.dat"), MIRRORS)
    sat_hi_mir, _ = _sat_margins(point.raw("sat_hi.dat"), MIRRORS)

    b1, b0 = CODE_BITS.get(point.axes.get(AXIS), (0, 0))

    return {
        "b1": b1,
        "b0": b0,
        "units": float(1 + b0 + 2 * b1),
        "iup_lo_a": i_up[k_lo],
        "idn_lo_a": i_dn[k_lo],
        "iup_mid_a": i_up[k_mid],
        "idn_mid_a": i_dn[k_mid],
        "iup_hi_a": i_up[k_hi],
        "idn_hi_a": i_dn[k_hi],
        "mism_lo_pct": mism_at(k_lo),
        "mism_mid_pct": mism_at(k_mid),
        "mism_hi_pct": mism_at(k_hi),
        "mism_absmax_pct": mism_absmax,
        "iup_flat_pct": 100.0 * (max(up_win) - min(up_win)) / i_up[k_mid],
        "idn_flat_pct": 100.0 * (max(dn_win) - min(dn_win)) / i_dn[k_mid],
        "satcasc_lo_v": sat_lo_casc,
        "satcasc_lo_dev": sat_lo_dev,
        "satcasc_hi_v": sat_hi_casc,
        "satcasc_hi_dev": sat_hi_dev,
        "satmir_lo_v": sat_lo_mir,
        "satmir_hi_v": sat_hi_mir,
        "curve": (v, i_up, i_dn),
    }


#: Names `derive_point` publishes as measurements (the rest of `_extract`'s
#: output is table-only: bit values, device names, and the whole curve).
MEASURES = (
    "units",
    "iup_lo_a", "idn_lo_a", "iup_mid_a", "idn_mid_a", "iup_hi_a", "idn_hi_a",
    "mism_lo_pct", "mism_mid_pct", "mism_hi_pct", "mism_absmax_pct",
    "iup_flat_pct", "idn_flat_pct",
    "satcasc_lo_v", "satcasc_hi_v", "satmir_lo_v", "satmir_hi_v",
)


def derive_point(point):
    data = _extract(point)
    if data is None:
        # No sweep to reduce.  Recorded not-measured rather than defaulted:
        # a compliance margin of "0" and "no data" are different claims.
        return {}
    return {k: data[k] for k in MEASURES if data.get(k) is not None}


def derive_tables(run):
    dc_rows = []
    curve_rows = []
    trim = {}

    for point in run.points:
        data = _extract(point)
        if data is None:
            continue
        process = point.corner
        temp = f"{point.temp_c:g}"
        vdd = f"{point.vdd:.2f}"
        b1, b0 = data["b1"], data["b0"]

        dc_rows.append(
            (
                process, temp, vdd, b1, b0, int(data["units"]),
                fmt_scalar(data["iup_lo_a"]), fmt_scalar(data["idn_lo_a"]),
                fmt_scalar(data["iup_mid_a"]), fmt_scalar(data["idn_mid_a"]),
                fmt_scalar(data["iup_hi_a"]), fmt_scalar(data["idn_hi_a"]),
                fmt_scalar(data["mism_lo_pct"], "%.4f"),
                fmt_scalar(data["mism_mid_pct"], "%.4f"),
                fmt_scalar(data["mism_hi_pct"], "%.4f"),
                fmt_scalar(data["mism_absmax_pct"], "%.4f"),
                fmt_scalar(data["iup_flat_pct"], "%.4f"),
                fmt_scalar(data["idn_flat_pct"], "%.4f"),
                fmt_scalar(data["satcasc_lo_v"], "%.4f"), data["satcasc_lo_dev"],
                fmt_scalar(data["satcasc_hi_v"], "%.4f"), data["satcasc_hi_dev"],
                fmt_scalar(data["satmir_lo_v"], "%.4f"),
                fmt_scalar(data["satmir_hi_v"], "%.4f"),
                "pass"
                if (
                    data["satcasc_lo_v"] is not None
                    and data["satcasc_lo_v"] > 0
                    and data["satcasc_hi_v"] is not None
                    and data["satcasc_hi_v"] > 0
                )
                else "FAIL",
            )
        )

        v, i_up, i_dn = data["curve"]
        for k in range(0, len(v), CURVE_DECIMATE):
            curve_rows.append(
                (
                    process, temp, vdd, b1, b0,
                    "%.4f" % v[k], fmt_scalar(i_up[k]), fmt_scalar(i_dn[k]),
                )
            )

        # Icp at this code = mean of the two polarities at mid window, the
        # quantity the pre-migration record's trim table reported.
        icp = 0.5 * (data["iup_mid_a"] + data["idn_mid_a"])
        units = int(data["units"])
        lo, hi = trim.get(units, (icp, icp))
        trim[units] = (min(lo, icp), max(hi, icp))

    n_fail = sum(1 for row in dc_rows if row[-1] == "FAIL")

    return [
        DerivedTable(
            name="cp_dc",
            description=(
                "per (PVT corner, trim code): output current at the three Vctrl "
                "window points, UP/DN mismatch, current flatness, and the "
                f"saturation margins the compliance verdict reads -- {len(dc_rows)} "
                f"point(s), {n_fail} with a cascode out of saturation inside the window"
            ),
            notes=(
                f"Vctrl window under test: {V_LO} .. {V_HI} V, nominal {V_MID} V (DR-001 Decision 2)",
                "units: Icp in unit legs = 1 + b0 + 2*b1",
                "iup_*/idn_*: UP (source) and DN (sink) output current at the window's low, "
                "mid and high point (A)",
                "mism_*_pct: 100*(iup-idn)/mean at that point; mism_absmax_pct is the largest "
                "magnitude anywhere inside the window",
                "iup_flat_pct/idn_flat_pct: peak-to-peak variation of each polarity's current "
                "across the window, as a percentage of its mid-window value",
                "satcasc_lo_v/satcasc_hi_v: smallest |vds|-|vdsat| among the two output "
                "CASCODE devices at the low/high end of the window, with the device that owns "
                "it.  Positive = in saturation.  This is the compliance verdict: the cascode "
                "is the device whose operating point the output voltage moves.",
                "satmir_lo_v/satmir_hi_v: the same quantity for the two bottom MIRROR devices, "
                "reported for context only.  A wide-swing cascode bias parks those at the "
                "saturation boundary by construction (that is what buys the headroom), and "
                "their bias does not move with the output voltage, so a margin near zero there "
                "is the design working as intended.",
                "verdict: pass iff BOTH cascode margins are positive at this corner and code",
            ),
            columns=(
                "process", "temp_c", "vdd_v", "b1", "b0", "units",
                "iup_lo_a", "idn_lo_a", "iup_mid_a", "idn_mid_a", "iup_hi_a", "idn_hi_a",
                "mism_lo_pct", "mism_mid_pct", "mism_hi_pct", "mism_absmax_pct",
                "iup_flat_pct", "idn_flat_pct",
                "satcasc_lo_v", "satcasc_lo_dev", "satcasc_hi_v", "satcasc_hi_dev",
                "satmir_lo_v", "satmir_hi_v", "verdict",
            ),
            rows=tuple(dc_rows),
        ),
        DerivedTable(
            name="cp_curves",
            description=(
                "complete output characteristic of both polarities at every corner "
                "and trim code, decimated from the 20 mV simulation grid to 100 mV"
            ),
            columns=(
                "process", "temp_c", "vdd_v", "b1", "b0", "vout_v", "iup_a", "idn_a",
            ),
            rows=tuple(curve_rows),
        ),
        DerivedTable(
            name="cp_trim_range",
            description=(
                "Icp delivered per trim code -- mean of the two polarities at "
                f"Vctrl = {V_MID} V, min/max across every corner"
            ),
            columns=("units", "icp_min_a", "icp_max_a"),
            rows=tuple(
                (units, fmt_scalar(lo), fmt_scalar(hi)) for units, (lo, hi) in sorted(trim.items())
            ),
        ),
    ]
