"""output-range reductions for the harness form of the campaign.

The campaign's pre-migration `run.sh` scored each row (status, DN-branch guard)
in bash and wrote one CSV row per (PVT point, edge).  Here the harness runs the
grid and this module does the same scoring from the raw measurements, then
compares every row to the baseline.

    derive_point    per row: Vctrl margin to each window edge and the lock flag
    derive_tables   `output_range_rows` (the baseline's row schema),
                    `row_comparison` (side by side with the baseline, per row)
                    and `baseline_comparison` (the summary and GO/NO-GO gate)

The baseline is the UNION of two read-only records: 20260819-160843-4e32f91
(90 rows; its ff/27C/3.30V `hi` row has no verdict) and 20260819-190341-70a4128
(which replaces that one row with a reproducible CAPPED outcome and carries a
labelled control run at a +1e-7 V seed that does complete).

Tolerances are proposals made before the run and are NOT widened here; a row that
misses is reported as FAIL and makes the gate NO-GO.
"""

import re
from pathlib import Path

from harness.derived import DerivedTable, fmt_scalar

HERE = Path(__file__).resolve().parent
RECORDS = HERE.parent / "records"
BASE_MAIN = "20260819-160843-4e32f91"
BASE_FIX = "20260819-190341-70a4128"

# ---- tolerances (issue #878) ------------------------------------------------
TOL_VCTRL_V = 0.005     # vctrl_final: 5 mV absolute (reltol 1e-3 convergence)
ACC_DN_FRAC = 3e-4      # PFD DN-branch guard floor, fraction of the supply (#69)
LOCK_HELD_V = 1.5       # lock_at_end threshold run.sh used for PASS
V_LO, V_HI = 0.9, 2.7   # usable control-voltage window

#: the one known marginal row: (corner, temp, vdd, edge)
MARGINAL = ("ff", "27", "3.30", "hi")

OP_RE = re.compile(r"^(lo|hi)(in|below|above)(.+)$")


def _num(text):
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text or "")
    return float(m.group(0)) if m and "N/A" not in text else None


def _key(corner, temp, vdd, edge):
    return (corner, "%g" % float(temp), "%.2f" % float(vdd), edge)


def _tables(text):
    """Every markdown table in `text` as a list of {header: cell} dicts."""
    out, cur, head = [], None, None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if head is None:
                head, cur = cells, []
                out.append(cur)
            elif not set("".join(cells)) <= set("-: "):
                cur.append(dict(zip(head, cells)))
        else:
            head = None
    return out


def _base_row(r):
    status = re.sub(r"[*]", "", r["Status"]).split()[0]
    guard = r["DN guard"].split()[0]
    return {
        "status": status,
        "vctrl": _num(r["vctrl_final"]),
        "dn": _num(r["mean DN"]),
        "guard": guard,
        "seed": _num(r["Seed Vctrl"]),
    }


def load_baseline():
    """({key: row}, control_row) from the two read-only baseline records."""
    rows = {}
    for table in _tables((RECORDS / f"{BASE_MAIN}.md").read_text()):
        for r in table:
            if "Corner" in r and r.get("Edge") in ("lo", "hi") and "Status" in r:
                rows[_key(r["Corner"], r["Temp"].rstrip("C"), r["VDD"].rstrip("V"), r["Edge"])] = _base_row(r)
    fix = [r for t in _tables((RECORDS / f"{BASE_FIX}.md").read_text()) for r in t if "Corner" in r]
    primary, control = fix[0], fix[1]
    k = _key(primary["Corner"], primary["Temp"].rstrip("C"), primary["VDD"].rstrip("V"), primary["Edge"])
    assert k == MARGINAL, k
    rows[k] = _base_row(primary)
    return rows, _base_row(control)


def score(point_vals, vdd, seed_pos):
    """Status / DN guard exactly as run.sh's run_one scored them.

    `point_vals` is {t_lock_last_rise, lock_at_end, vctrl_final, dn_lvl}, any may
    be None.  Returns (status, guard)."""
    vfin = point_vals.get("vctrl_final")
    if vfin is None:
        return "ERROR", "ERROR"
    tlock, endok = point_vals.get("t_lock_last_rise"), point_vals.get("lock_at_end")
    status = "FAIL"
    if tlock is not None and endok is not None and endok >= LOCK_HELD_V:
        status = "PASS"
    if seed_pos != "in":
        status = "OUT-OF-WINDOW"
    dn = point_vals.get("dn_lvl")
    if dn is None:
        guard = "ERROR"
    elif dn >= ACC_DN_FRAC * vdd:
        guard = "PASS"
    else:
        guard = "FAIL" if status == "PASS" else "SUSPECT"
    return status, guard


def _point_axes(point):
    m = OP_RE.match(point.axes.get("op", ""))
    return m.groups() if m else None


def derive_point(point):
    parsed = _point_axes(point)
    vfin = point.get("vctrl_final")
    if parsed is None or vfin is None:
        return {}
    status, _ = score(
        {k: point.get(k) for k in ("t_lock_last_rise", "lock_at_end", "vctrl_final", "dn_lvl")},
        point.vdd, parsed[1])
    return {
        "vctrl_margin_lo_v": vfin - V_LO,
        "vctrl_margin_hi_v": V_HI - vfin,
        "pass_lock": 1.0 if status == "PASS" else 0.0,
    }


def _new_rows(run):
    rows = {}
    for p in run.points:
        parsed = _point_axes(p)
        if parsed is None:
            continue
        edge, pos, seed = parsed
        vals = {k: p.get(k) for k in ("t_lock_last_rise", "lock_at_end", "vctrl_final", "dn_lvl")}
        status, guard = score(vals, p.vdd, pos)
        rows[_key(p.corner, p.temp_c, p.vdd, edge)] = {
            "status": status, "vctrl": vals["vctrl_final"], "dn": vals["dn_lvl"],
            "guard": guard, "seed": float(seed.replace("p", ".")), "pos": pos,
        }
    return rows


def _cmp(base, new, key, control):
    """(verdict, note) for one row."""
    problems, note = [], ""
    if new is None:
        new = {"status": "ERROR", "vctrl": None, "guard": "ERROR", "dn": None}
    ref = base
    marginal = key == MARGINAL
    status_ok = new["status"] == base["status"]
    if marginal and not status_ok:
        # Known marginal row: judge against the second record's control run.
        ref = control
        note = ("marginal row: baseline grid row is %s, judged against the second "
                "record's control run (seed + 1e-7 V)" % base["status"])
        status_ok = new["status"] == control["status"]
    if not status_ok:
        problems.append("status")
    if ref["vctrl"] is None or new["vctrl"] is None:
        if (ref["vctrl"] is None) != (new["vctrl"] is None):
            problems.append("vctrl_final presence")
    elif abs(new["vctrl"] - ref["vctrl"]) > TOL_VCTRL_V:
        problems.append("vctrl_final")
    if new["guard"] != ref["guard"]:
        problems.append("DN guard")
    return ("FAIL" if problems else ("documented" if note else "pass")), (
        ("; ".join(problems) + ("; " if problems and note else "") + note) if (problems or note) else "")


def _fmt(v):
    return "N/A" if v is None else fmt_scalar(v)


def derive_tables(run):
    base, control = load_baseline()
    new = _new_rows(run)
    result_rows, cmp_rows = [], []
    counts = {"pass": 0, "documented": 0, "FAIL": 0}
    failing = []
    for key in sorted(base, key=lambda k: (k[3] != "hi", k[0], float(k[1]), float(k[2]))):
        b, n = base[key], new.get(key)
        verdict, note = _cmp(b, n, key, control)
        counts[verdict] += 1
        label = "%s/%sC/%sV/%s" % key
        if verdict == "FAIL":
            failing.append(label + " (" + note + ")")
        nv = n or {"status": "ERROR", "vctrl": None, "dn": None, "guard": "ERROR"}
        dv = (None if b["vctrl"] is None or nv["vctrl"] is None else nv["vctrl"] - b["vctrl"])
        cmp_rows.append((key[0], key[1], key[2], key[3],
                         b["status"], nv["status"],
                         _fmt(b["vctrl"]), _fmt(nv["vctrl"]),
                         "N/A" if dv is None else "%+.2f" % (1e3 * dv), "%g mV" % (1e3 * TOL_VCTRL_V),
                         _fmt(b["dn"]), _fmt(nv["dn"]), b["guard"], nv["guard"], verdict, note))
        vf = nv["vctrl"]
        result_rows.append((key[0], key[1], key[2], key[3],
                            "32" if key[3] == "hi" else "8",
                            _fmt(n["seed"]) if n else "N/A", n["pos"] if n else "N/A", nv["status"],
                            _fmt(vf), "N/A" if vf is None else _fmt(vf - V_LO),
                            "N/A" if vf is None else _fmt(V_HI - vf), _fmt(nv["dn"]), nv["guard"]))
    extra = sorted(set(new) - set(base))
    for k in extra:
        counts["FAIL"] += 1
        failing.append("%s/%sC/%sV/%s (row not in baseline)" % k)
    gate = "GO" if not failing and len(base) == 90 and len(new) == 90 else (
        "NO-GO (%d failing row(s))" % len(failing) if failing else "NO-GO (grid incomplete)")
    summary = (
        ("baseline rows (union of two records)", "90", str(len(base)), "-", "90", "pass" if len(base) == 90 else "FAIL"),
        ("new rows measured", "-", str(len(new)), "-", "90", "pass" if len(new) == 90 else "FAIL"),
        ("rows passing every per-row tolerance", "-", str(counts["pass"]), "-", "all", "pass" if not failing else "FAIL"),
        ("rows documented separately (marginal ff/27C/3.30V hi)", "-", str(counts["documented"]), "-", "-", "pass"),
        ("rows missing a tolerance", "-", str(counts["FAIL"]), "-", "0", "pass" if not counts["FAIL"] else "FAIL"),
    )
    return [
        DerivedTable(
            name="output_range_rows",
            description="one row per (PVT point, edge) in the baseline's schema: status, vctrl_final, margins to the 0.9-2.7 V window, mean DN and the DN guard",
            columns=("corner", "temp_c", "vdd_v", "edge", "n", "seed_v", "seed_pos", "status",
                     "vctrl_final_v", "margin_to_0p9v", "margin_to_2p7v", "dn_lvl_v", "dn_guard"),
            rows=tuple(result_rows),
        ),
        DerivedTable(
            name="row_comparison",
            description="every row side by side with the baseline (union of %s and %s): baseline, new, delta, tolerance, verdict" % (BASE_MAIN, BASE_FIX),
            columns=("corner", "temp_c", "vdd_v", "edge", "status_base", "status_new", "vctrl_base_v",
                     "vctrl_new_v", "vctrl_delta_mv", "vctrl_tol", "dn_base_v", "dn_new_v",
                     "guard_base", "guard_new", "verdict", "note"),
            notes=("tolerances: status exact; vctrl_final 5 mV absolute; DN-guard verdict exact; mean DN reported with its delta and graded by the guard verdict",
                   "a missed row is reported, never widened"),
            rows=tuple(cmp_rows),
        ),
        DerivedTable(
            name="baseline_comparison",
            description="summary of the per-row comparison against the baseline: GATE FOR THE DEPENDENT mc-cp-mismatch WORK = %s" % gate,
            notes=("failing rows: " + ("none" if not failing else "; ".join(failing)),),
            columns=("metric", "baseline", "new", "delta", "tolerance", "verdict"),
            rows=summary,
        ),
    ]
