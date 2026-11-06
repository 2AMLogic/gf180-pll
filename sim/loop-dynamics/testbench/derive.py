"""loop-dynamics reductions for the harness form of the campaign.

The pre-migration `run.sh` fanned ngspice out by hand, stitched the raw
`wrdata` output into two CSVs with awk, and ran `analyze.py` over them.  Here
the harness runs the grid; this module does the stitching and calls the SAME
`analyze.py` unchanged in its algebra, so the numbers are produced by the
method the baseline record used and not by a re-implementation of it.

    derive_point    per filter-impedance point: R, C1, C2 of the 3-element fit
                    at Vctrl = 1.8 V (an integrity read: a passive corner that
                    silently failed to apply would show up as zero spread)
    derive_tables   the whole analysis (`analyze.py` -> the CSVs it always
                    wrote), plus `baseline_comparison`: every metric the pilot
                    go/no-go gate names, new value vs. the baseline record's,
                    with the tolerance and a pass/fail.

Tolerances are the ones ratified in the issue and are NOT loosened here; a row
that misses is reported as FAIL and makes the gate NO-GO.
"""

import contextlib
import csv
import importlib.util
import io
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from harness.derived import DerivedTable, fmt_scalar

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
REPO = SIM.parent

#: The record this campaign supersedes; the comparison is against it.
BASELINE = "20260731-202550-82af5a9"
BASELINE_DIR = SIM / "loop-dynamics" / "corners" / BASELINE
BASELINE_RECORD = SIM / "loop-dynamics" / "records" / f"{BASELINE}.md"

#: Read-only design-input evidence, pinned exactly as `run.sh` pins it.
KVCO_CSV = SIM / "vco-tuning-range/corners/20260731-081628-239e73b/kvco_by_point.csv"
CPDC_CSV = SIM / "cp-compliance/corners/20260731-194124-afa338c/cp_dc.csv"
CPSW_CSV = SIM / "cp-compliance/corners/20260731-194124-afa338c/cp_switch.csv"

AXIS = "run"
Z_RUN = "z"
VCTRLS = (0.3, 0.9, 1.35, 1.8, 2.25, 2.7)
#: Z columns (m<k>, a<k>) per Vctrl, in `VCTRLS` order.
TYP_BUNDLE = "rtyp-mtyp-xtyp"
FZ_HEADER = "bundle,res_sec,moscap_sec,mimcap_sec,temp_c,vctrl_v,freq_hz,zmag_ohm,zph_deg"
LAC_HEADER = "tag,bundle,temp_c,vctrl_v,icp_a,kvco_hz_per_v,n_div,freq_hz,tmag,tph_deg"

SECTION = {"typ": "typical", "ff": "ff", "ss": "ss"}

# ---- tolerances (issue #741, "Baseline (what reproduces means)") ----------
TOL_RCC_REL = 0.005       # R, C1, C2, C-V: 0.5 % relative
TOL_FIT_ABS_PCT = 0.5     # 3-element-fit worst |Z| mismatch: <= 0.5 % absolute
TOL_PM_DEG = 0.5          # worst-case phase margin
TOL_REL_2PCT = 0.02       # f_c/f_ref and settling: 2 % relative
TOL_XC_PM_DEG = 0.5       # cross-check agreement margin over the baseline's own
TOL_XC_FC_PCT = 0.5       # same, for f_c (percent)


def _analyze():
    spec = importlib.util.spec_from_file_location("loop_dynamics_analyze", HERE / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle_parts(corner):
    """`rtyp-mtyp-xtyp` -> (res, moscap, mimcap) section names."""
    r, m, x = corner.split("-")
    return SECTION[r[1:]], SECTION[m[1:]], SECTION[x[1:]]


def _z_curves(point):
    """[(vctrl, freqs, mags, phases)] from a bench-z point's z.dat, or None."""
    raw = point.raw("z.dat")
    if not raw.exists():
        return None
    rows = [r for r in raw.rows() if r[0] >= 100.0 * (1 - 1e-9)]
    if len(rows) < 10:
        return None
    out = []
    for k, vctrl in enumerate(VCTRLS):
        out.append(
            (
                vctrl,
                [r[0] for r in rows],
                [r[1 + 2 * k] for r in rows],
                [r[2 + 2 * k] for r in rows],
            )
        )
    return out


def derive_point(point):
    if point.axes.get(AXIS) != Z_RUN:
        return {}
    curves = _z_curves(point)
    if curves is None:
        return {}
    an = _analyze()
    worst = 0.0
    typ = None
    for vctrl, f, m, p in curves:
        c = an.ZCurve((point.corner, point.temp_c, vctrl), f, m, p)
        worst = max(worst, c.fit["err"])
        if vctrl == 1.8:
            typ = c.fit
    return {
        "r_ohm": typ["r"],
        "c1_f": typ["c1"],
        "c2_f": typ["c2"],
        "fit_err_pct": 100.0 * worst,
    }


def _write_inputs(run, tmp):
    """The two CSVs `analyze.py` reads, rebuilt from the harness's raw files."""
    fz_lines = [FZ_HEADER]
    lac_lines = [LAC_HEADER]
    for point in run.points:
        kind = point.axes.get(AXIS)
        if kind == Z_RUN:
            curves = _z_curves(point)
            if curves is None:
                continue
            res, mos, mim = _bundle_parts(point.corner)
            for vctrl, f, m, p in curves:
                for fi, mi, pi in zip(f, m, p):
                    fz_lines.append(
                        "%s,%s,%s,%s,%g,%s,%.8g,%.8g,%.6f"
                        % (point.corner, res, mos, mim, point.temp_c, vctrl, fi, mi, pi)
                    )
        elif kind:
            raw = point.raw("t.dat")
            if not raw.exists():
                continue
            pr = point.params
            tag = "loop_%s_T%g_F%g_N%d_L%d" % (
                point.corner,
                point.temp_c,
                float(pr["fref_mhz"]),
                int(float(pr["ndiv"])),
                int(float(pr["legs"])),
            )
            tag = tag.replace(".", "p")
            for r in raw.rows():
                lac_lines.append(
                    "%s,%s,%g,%s,%s,%s,%s,%.8g,%.8g,%.6f"
                    % (tag, point.corner, point.temp_c, pr["vctrl"], pr["icp"],
                       pr["kvco"], pr["ndiv"], r[0], r[1], r[2])
                )
    fz = Path(tmp) / "filter_z_raw.csv"
    lac = Path(tmp) / "loop_ac_raw.csv"
    fz.write_text("\n".join(fz_lines) + "\n")
    lac.write_text("\n".join(lac_lines) + "\n")
    return fz, lac


def _read(path):
    lines = [l for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith("#")]
    return list(csv.DictReader(lines))


def _table_from_csv(name, path, description):
    lines = [l for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith("#")]
    reader = list(csv.reader(lines))
    return DerivedTable(
        name=name,
        description=description,
        columns=tuple(reader[0]),
        rows=tuple(tuple(r) for r in reader[1:]),
    )


# ---------------------------------------------------------------------------
# Comparison against the baseline record
# ---------------------------------------------------------------------------

def _rc_stats(rows):
    """Typical and min..max R, C1 (in-window), C2 -- the baseline's section 1."""
    def f(r, k):
        return float(r[k])

    typ = [r for r in rows if r["bundle"] == TYP_BUNDLE and float(r["temp_c"]) == 27
           and float(r["vctrl_v"]) == 1.8][0]
    win = [r for r in rows if 0.9 <= float(r["vctrl_v"]) <= 2.7]
    return {
        "R typical": f(typ, "r_ohm"),
        "R min": min(f(r, "r_ohm") for r in rows),
        "R max": max(f(r, "r_ohm") for r in rows),
        "C1 typical": f(typ, "c1_f"),
        "C1 min (in window)": min(f(r, "c1_f") for r in win),
        "C1 max (in window)": max(f(r, "c1_f") for r in win),
        "C2 typical": f(typ, "c2_f"),
        "C2 min": min(f(r, "c2_f") for r in rows),
        "C2 max": max(f(r, "c2_f") for r in rows),
    }


def _cv(rows):
    return {
        float(r["vctrl_v"]): float(r["c1_f"])
        for r in rows
        if r["bundle"] == TYP_BUNDLE and float(r["temp_c"]) == 27
    }


def _cells(rows):
    """Section 4's table: per (f_ref, trim legs), the worst case over N."""
    out = defaultdict(lambda: [1e9, 0.0, 0.0])
    for r in rows:
        k = (float(r["f_ref_hz"]), int(float(r["trim_units"])))
        v = out[k]
        v[0] = min(v[0], float(r["pm_min_deg"]))
        v[1] = max(v[1], float(r["fc_over_fref_max"]))
        v[2] = max(v[2], float(r["settle_max_s"]))
    return out


def _sets(rows):
    star, lock = set(), set()
    for r in rows:
        k = (float(r["f_ref_hz"]), int(float(r["n_div"])), int(float(r["trim_units"])))
        if int(r["pass_pm"]) and int(r["pass_fcratio"]):
            star.add(k)
        if int(r["pass_lock"]):
            lock.add(k)
    return star, lock


def _verdict_line(text):
    m = re.search(r"\*\*Overall:[^\n]*\*\*", text)
    return m.group(0) if m else ""


def _area_line(text):
    m = re.search(r"C1 is (\d+) um\^2 of `cap_nmos_03v3_b` = \*\*([\d.]+) mm\^2\*\*, "
                  r"\*\*([\d.]+) % of the", text)
    return m.groups() if m else ()


def _rel_row(rows, metric, base, new, tol_rel, unit=""):
    delta = (new - base) / base if base else float("inf")
    ok = abs(delta) <= tol_rel
    rows.append((metric, fmt_scalar(base), fmt_scalar(new), "%+.4f %%" % (100 * delta),
                 "%g %% relative" % (100 * tol_rel), "pass" if ok else "FAIL"))


def _comparison(new_dir, new_md):
    rows = []
    base_rc, new_rc = _read(BASELINE_DIR / "filter_rc.csv"), _read(Path(new_dir) / "filter_rc.csv")
    bs, ns = _rc_stats(base_rc), _rc_stats(new_rc)
    for k in bs:
        _rel_row(rows, "s1 " + k + " (ohm or F)", bs[k], ns[k], TOL_RCC_REL)

    bw = 100 * max(float(r["fit_err_frac"]) for r in base_rc)
    nw = 100 * max(float(r["fit_err_frac"]) for r in new_rc)
    rows.append(("s1 worst 3-element-fit |Z| mismatch (%)", fmt_scalar(bw), fmt_scalar(nw),
                 "%+.4f" % (nw - bw), "<= %g absolute" % TOL_FIT_ABS_PCT,
                 "pass" if nw <= TOL_FIT_ABS_PCT else "FAIL"))

    base_text = BASELINE_RECORD.read_text()
    ba, na = _area_line(base_text), _area_line(new_md)
    rows.append(("s2 C1 area (um^2 / mm^2 / % of budget)", " / ".join(ba), " / ".join(na),
                 "0" if ba == na else "differs", "exact", "pass" if ba and ba == na else "FAIL"))

    bc, nc = _cv(base_rc), _cv(new_rc)
    for v in sorted(bc):
        _rel_row(rows, "s3 C1 at Vctrl=%g V (typical corner, 27 C)" % v, bc[v], nc.get(v, float("nan")),
                 TOL_RCC_REL)

    base_m, new_m = _read(BASELINE_DIR / "loop_margins.csv"), _read(Path(new_dir) / "loop_margins.csv")
    bcell, ncell = _cells(base_m), _cells(new_m)
    for key in sorted(bcell):
        fr, legs = key
        label = "s4 f_ref=%g MHz, %d leg(s): " % (fr / 1e6, legs)
        if key not in ncell:
            rows.append((label + "cell", "present", "missing", "-", "present", "FAIL"))
            continue
        b, n = bcell[key], ncell[key]
        rows.append((label + "worst PM (deg)", fmt_scalar(b[0]), fmt_scalar(n[0]),
                     "%+.3f deg" % (n[0] - b[0]), "%g deg" % TOL_PM_DEG,
                     "pass" if abs(n[0] - b[0]) <= TOL_PM_DEG else "FAIL"))
        _rel_row(rows, label + "worst f_c/f_ref", b[1], n[1], TOL_REL_2PCT)
        _rel_row(rows, label + "worst 1 % settling (s)", b[2], n[2], TOL_REL_2PCT)

    bstar, block = _sets(base_m)
    nstar, nlock = _sets(new_m)
    for name, b, n in (("s4/s5 cells meeting PM and f_c/f_ref (the * cells)", bstar, nstar),
                       ("s5 cells meeting the small-signal lock-time limit", block, nlock)):
        rows.append((name, str(len(b)), str(len(n)),
                     "flipped: %d" % len(b ^ n), "identical set",
                     "pass" if b == n else "FAIL"))

    bx, nx = _read(BASELINE_DIR / "loop_ac_crosscheck.csv"), _read(Path(new_dir) / "loop_ac_crosscheck.csv")
    for col, tol, unit in (("fc_err_pct", TOL_XC_FC_PCT, "%"), ("pm_err_deg", TOL_XC_PM_DEG, "deg")):
        b = max(abs(float(r[col])) for r in bx)
        n = max(abs(float(r[col])) for r in nx) if nx else float("nan")
        rows.append(("s8 cross-check worst |%s|" % col, fmt_scalar(b), fmt_scalar(n),
                     "%+.4f" % (n - b), "baseline + %g %s" % (tol, unit),
                     "pass" if n <= b + tol else "FAIL"))
    rows.append(("s8 cross-check run count", str(len(bx)), str(len(nx)), "-", "equal",
                 "pass" if len(bx) == len(nx) else "FAIL"))

    bv, nv = _verdict_line(base_text), _verdict_line(new_md)
    rows.append(("s10 verdict", bv, nv, "-", "identical text", "pass" if bv and bv == nv else "FAIL"))
    return rows


def derive_tables(run):
    an = _analyze()
    with tempfile.TemporaryDirectory(prefix="loop-dynamics-") as tmp:
        fz, lac = _write_inputs(run, tmp)
        outdir = Path(tmp) / "out"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            an.main([str(fz), str(lac), str(KVCO_CSV), str(CPDC_CSV), str(CPSW_CSV), str(outdir)])
        new_md = buf.getvalue()

        tables = []
        spec = (
            ("filter_rc", "measured R / C1 / C2 per (passive bundle, temperature, Vctrl) from a "
                          "3-element fit of each measured Z(jw) curve"),
            ("loop_margins", "the full (f_ref, N, Icp trim code) cross-product verdict: worst PM, "
                             "f_c/f_ref and 1 % settling over every in-window filter curve"),
            ("loop_margins_by_filter_corner", "worst case per filter curve"),
            ("kappa_by_target", "Kvco per (f_ref, N) under the three band-selection rules"),
            ("ripple_tradeoff", "control-line ripple vs. lock time per C2"),
            ("loop_ac_crosscheck", "whole-loop simulated T(jw) vs. the impedance-plus-algebra result"),
            ("filter_z", "decimated measured impedance curves"),
        )
        for name, desc in spec:
            tables.append(_table_from_csv(name, outdir / f"{name}.csv", desc))

        comp = _comparison(outdir, new_md)
        failing = [r[0] for r in comp if r[-1] != "pass"]
        gate = "GO" if not failing else "NO-GO (%d failing row(s))" % len(failing)
        tables.append(
            DerivedTable(
                name="baseline_comparison",
                description=(
                    "every metric of the pilot go/no-go gate, this run vs. baseline record "
                    f"{BASELINE}: PILOT GATE = {gate}"
                ),
                notes=(
                    "tolerances are the ratified ones; a missed row is reported, never widened",
                    "baseline: ngspice-46 / Darwin arm64; see Environment provenance for this run's "
                    "simulator and host",
                    "failing rows: " + ("none" if not failing else "; ".join(failing)),
                ),
                columns=("metric", "baseline", "new", "delta", "tolerance", "verdict"),
                rows=tuple(comp),
            )
        )
    return tables
