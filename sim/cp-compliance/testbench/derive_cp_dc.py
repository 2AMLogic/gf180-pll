"""cp-compliance (DC) reductions -- the two quantities a fixed .measure at a
single Vctrl point cannot express, plus the per-trim-code Icp ladder.

- ``mism_absmax_pct`` / ``iup_flat_pct`` / ``idn_flat_pct`` need the WHOLE
  0..3.63 V output curve inside the ~0.9-2.4 V compliance window, not just
  the three fixed points (0.9 / 1.65 / 2.4 V) ``raw_measures`` reads directly
  -- ngspice's ``.measure dc find ... at=`` cannot report a worst-case or a
  peak-to-peak swing over a window, only a single interpolated point.
- ``satcasc_lo_v`` / ``satcasc_hi_v`` / ``satmir_lo_v`` / ``satmir_hi_v`` are
  the minimum |vds|-|vdsat| margin among a *pair* of devices (one polarity's
  cascode, and separately its bottom/top mirror) at each end of the window --
  a `min()` over two prior raw measurements, done here in Python rather than
  a `param=` expression for clarity.
- ``cp_trim_range`` is the pre-migration record's headline trim-range table:
  Icp mean (of the two polarities, at Vctrl mid-window) versus unit-leg
  count, min/max across the 45-corner PVT grid -- a reduction across the
  'code' sweep axis that no single point's own measurements can produce.

This module is the reduction half of the DC bench; the switching bench
(``testbench-switch/``) needs no reduction at all -- every one of its
headline numbers (iup_ss, idn_ss, qup, qdn, wup, wdn, wskew) is a plain
``.measure`` or a ``param=`` arithmetic expression over prior measurements.
"""

from __future__ import annotations

from collections import defaultdict

from harness.derived import DerivedTable

# Vctrl window under test (DR-001 Decision 2 design intent): the compliance
# verdict and the mismatch/flatness figures are all taken over this range.
VLO = 0.9
VHI = 2.4

# code sweep-axis point id ("code<b1><b0>") -> unit legs = 1 + b0 + 2*b1.
LEGS_BY_CODE = {"code00": 1, "code01": 2, "code10": 3, "code11": 4}
NOMINAL_CODE = "code10"  # b1b0 = 10, 3 unit legs -- design/README.md nominal


def _margin(point, vds_name: str, vdsat_name: str):
    vds = point.get(vds_name)
    vdsat = point.get(vdsat_name)
    if vds is None or vdsat is None:
        return None
    return abs(vds) - abs(vdsat)


def _mismatch_pct(iup, idn):
    if iup is None or idn is None:
        return None
    denom = 0.5 * (iup + idn)
    if denom == 0:
        return None
    return 100.0 * (iup - idn) / denom


def derive_point(point):
    out: dict[str, float] = {}

    ncasc_lo = _margin(point, "satlo_ncasc_vds", "satlo_ncasc_vdsat")
    pcasc_lo = _margin(point, "satlo_pcasc_vds", "satlo_pcasc_vdsat")
    ncasc_hi = _margin(point, "sathi_ncasc_vds", "sathi_ncasc_vdsat")
    pcasc_hi = _margin(point, "sathi_pcasc_vds", "sathi_pcasc_vdsat")
    nbot_lo = _margin(point, "satlo_nbot_vds", "satlo_nbot_vdsat")
    ptop_lo = _margin(point, "satlo_ptop_vds", "satlo_ptop_vdsat")
    nbot_hi = _margin(point, "sathi_nbot_vds", "sathi_nbot_vdsat")
    ptop_hi = _margin(point, "sathi_ptop_vds", "sathi_ptop_vdsat")
    if ncasc_lo is not None and pcasc_lo is not None:
        out["satcasc_lo_v"] = min(ncasc_lo, pcasc_lo)
    if ncasc_hi is not None and pcasc_hi is not None:
        out["satcasc_hi_v"] = min(ncasc_hi, pcasc_hi)
    if nbot_lo is not None and ptop_lo is not None:
        out["satmir_lo_v"] = min(nbot_lo, ptop_lo)
    if nbot_hi is not None and ptop_hi is not None:
        out["satmir_hi_v"] = min(nbot_hi, ptop_hi)

    iup_lo, idn_lo = point.get("iup_lo"), point.get("idn_lo")
    iup_mid, idn_mid = point.get("iup_mid"), point.get("idn_mid")
    iup_hi, idn_hi = point.get("iup_hi"), point.get("idn_hi")
    mlo = _mismatch_pct(iup_lo, idn_lo)
    mmid = _mismatch_pct(iup_mid, idn_mid)
    mhi = _mismatch_pct(iup_hi, idn_hi)
    if mlo is not None:
        out["mism_lo_pct"] = mlo
    if mmid is not None:
        out["mism_mid_pct"] = mmid
    if mhi is not None:
        out["mism_hi_pct"] = mhi
    if iup_mid is not None and idn_mid is not None:
        out["icp_mid_mean"] = 0.5 * (iup_mid + idn_mid)
        # Restricted copy for the nominal-code headline: 'not measured' at
        # every other code, so the grid spread table for this name reports
        # min/max over the nominal-code rows only (sim/harness's treatment of
        # an optional measurement that legitimately does not apply -- see
        # sim/harness/README.md "Expected .measure failures: optional").
        if point.axes.get("code") == NOMINAL_CODE:
            out["mism_mid_nom_pct"] = mmid if mmid is not None else 0.0

    raw = point.raw("iv_cp.dat")
    if raw.exists():
        # wrdata repeats the sweep variable once per requested vector, so the
        # file is (vsw, i_up, vsw2, i_dn) -- vsw2 is identical to vsw and
        # unused (see tb.json raw_files.iv_cp.dat.description).
        vsw_col = raw.column("vsw")
        iup_col = raw.column("i_up")
        idn_col = raw.column("i_dn")
        window = [
            (v, iu, idn_)
            for v, iu, idn_ in zip(vsw_col, iup_col, idn_col)
            if VLO - 1e-9 <= v <= VHI + 1e-9
        ]
        if window:
            mmax = 0.0
            up_vals = [r[1] for r in window]
            dn_vals = [r[2] for r in window]
            upmin, upmax = min(up_vals), max(up_vals)
            dnmin, dnmax = min(dn_vals), max(dn_vals)
            for _v, iu, idn_ in window:
                mm = _mismatch_pct(iu, idn_)
                if mm is not None and abs(mm) > abs(mmax):
                    mmax = mm
            out["mism_absmax_pct"] = mmax
            if point.axes.get("code") == NOMINAL_CODE:
                out["mism_absmax_nom_pct"] = mmax
            if iup_mid:
                out["iup_flat_pct"] = 100.0 * (upmax - upmin) / iup_mid
                if point.axes.get("code") == NOMINAL_CODE:
                    out["iup_flat_nom_pct"] = out["iup_flat_pct"]
            if idn_mid:
                out["idn_flat_pct"] = 100.0 * (dnmax - dnmin) / idn_mid
                if point.axes.get("code") == NOMINAL_CODE:
                    out["idn_flat_nom_pct"] = out["idn_flat_pct"]

    return out


def derive_tables(run):
    by_code: dict[str, list[float]] = defaultdict(list)
    for point in run.points:
        code = point.axes.get("code")
        icp = point.get("icp_mid_mean")
        if code is not None and icp is not None:
            by_code[code].append(icp)

    rows = []
    for code in sorted(by_code, key=lambda c: LEGS_BY_CODE.get(c, 0)):
        vals = by_code[code]
        rows.append(
            (
                LEGS_BY_CODE.get(code, code),
                "%.6g" % min(vals),
                "%.6g" % max(vals),
            )
        )

    return [
        DerivedTable(
            name="cp_trim_range",
            description=(
                "Icp trim range: mean of the two polarities at Vctrl = 1.65 V "
                "(mid-window), min/max across the 45-corner PVT grid, per "
                "2-bit trim code"
            ),
            columns=("unit_legs", "icp_min_a", "icp_max_a"),
            rows=tuple(rows),
        )
    ]
