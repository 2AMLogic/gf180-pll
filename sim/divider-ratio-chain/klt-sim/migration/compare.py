"""Compare the migration envelopes against committed record 20261114-093804.

The #1090 acceptance join, per point, on (process, temperature, supply):

- **Per-point deltas** for the campaign's eleven raw measurements: the
  envelope value against the committed record's printed value (the record
  prints seven significant digits; a value *matches at printed precision*
  when the absolute difference is at most one unit in that last printed
  place, so a boundary rounding in the record's own formatting does not
  read as a disagreement).  Written to ``deltas.csv`` and summarised per
  slice in deltas.csv.
- **The ratio check**, re-applied exactly as ``testbench/derive.py`` does:
  both ``n_fb`` and ``ndo`` within 0.05 of the point's programmed ``kn``
  (read from the request's circuit body, not re-derived), compared with the
  record's own ``ratio_pass`` column.
- **``fbpw_s``**, the sign-corrected FB high time (``fbpw + N*T_vco`` when
  the raw fall-minus-rise reads negative), the same correction derive.py
  applies, compared with the record's ``fbpw_s`` column.
- **The retiming-margin join** at the 17 ``f200n64`` points: the envelope's
  ``setup_margin``/``hold_margin`` (measured in-sweep against the pinned
  per-group ``tsetup_s``/``thold_s``) against the committed
  ``retiming_margin.csv``, plus an independent recomputation
  ``5 ns - t_arr - tsetup``/``t_arr - thold`` from the DFF table, and the
  strict-positivity closing verdict.

Exit 0 only when every one of the 190 expected points joined 1:1, every
measurement matched at printed precision, both ratio checks and both margin
verdicts agree with the record, and no value is missing; anything else is
named on stderr and exits non-zero (a disagreement is a result to record,
not a scripting failure -- but it must not pass silently).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
RECORD = HERE.parent.parent / "records" / "20261114-093804-ad9eef8.md"
MARGIN_CSV = HERE.parent.parent / "corners" / "20261114-093804-ad9eef8" / "retiming_margin.csv"
DFF_CSV = (
    HERE.parent.parent.parent / "divider-ratio-dff" / "corners"
    / "20261114-080736-f53d562" / "dff_setup_hold.csv"
)
PILOT_POINT = "f200n33"
MEASURES = ["tfb1", "tfb2", "n_fb", "tdo1", "tdo2", "ndo", "t_arr",
            "t_rtcq", "ffb2", "fbpw", "iavg"]

_ROW = re.compile(
    r"^\s*\|\s*`([a-z]+)_(-?\d+c)_(\d\.\d\dv)_(f\d+n\d+)`\s*\|(.+)\|\s*$"
)


def quantum(token: str) -> Decimal:
    """One unit in the last printed place of a record token like 4.203100e-08
    (the token's own exponent, trailing zeros kept -- ``normalize()`` would
    strip them and widen the place)."""
    return Decimal(1).scaleb(Decimal(token).as_tuple().exponent)


def load_record() -> dict[tuple, dict]:
    points: dict[tuple, dict] = {}
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        process, temp_c, vdd_v, point, rest = match.groups()
        cells = [c.strip() for c in rest.split("|")]
        entry = {
            "raw": dict(zip(MEASURES, cells[:11])),
            "ratio_pass": cells[11],
            "fbpw_s": cells[12],
            "n_target": cells[13],
            "verdict": cells[14],
        }
        key = (point, process, int(temp_c.rstrip("c")), float(vdd_v.rstrip("v")))
        if key in points:
            raise SystemExit(f"error: duplicate record row {key}")
        points[key] = entry
    return points


def load_margins() -> dict[tuple, dict]:
    out: dict[tuple, dict] = {}
    with MARGIN_CSV.open(encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
        for row in csv.DictReader(lines):
            key = (row["process"], int(float(row["temp_c"])), float(row["vdd_v"]))
            out[key] = {k: (v if k == "verdict" else float(v))
                        for k, v in row.items()
                        if k not in ("process", "temp_c", "vdd_v")}
            out[key]["tokens"] = {k: v for k, v in row.items()
                                  if k not in ("process", "temp_c", "vdd_v", "verdict")}
    return out


def load_dff() -> dict[tuple, tuple[float, float]]:
    out: dict[tuple, tuple[float, float]] = {}
    with DFF_CSV.open(encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
        for row in csv.DictReader(lines):
            out[(row["process"], int(float(row["temp_c"])), float(row["vdd_v"]))] = (
                float(row["tsetup_s"]), float(row["thold_s"]))
    return out


def body_params(stem: str) -> dict[str, float]:
    params: dict[str, float] = {}
    for line in (HERE / "netlists" / f"{stem}.sp").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\.param\s+([a-z0-9_]+)=(\S+)$", line)
        if match:
            params[match.group(1)] = float(match.group(2))
    return params


def point_of(stem: str) -> str:
    return stem[:-1] if stem[-1] in "ab" else stem


def main() -> None:
    record = load_record()
    margins = load_margins()
    dff = load_dff()
    problems: list[str] = []
    delta_rows: list[list] = []
    joined = 0

    reports = sorted(RUNS.glob("*/report.json"))
    if len(reports) != 63:
        problems.append(f"expected 63 member reports, found {len(reports)}")

    for report_path in reports:
        stem = report_path.parent.name
        point = point_of(stem)
        envelope = json.loads(report_path.read_text(encoding="utf-8"))
        params = body_params(stem)
        n_target = params["kn"]
        tvco = 1.0 / params["kf"]
        if envelope.get("status") != "pass":
            problems.append(f"{stem}: envelope status {envelope.get('status')!r}")
        for corner in envelope["corners"]:
            key = (point, corner["process"], corner["temperature_c"],
                   corner["params"]["vdd_val"])
            base = record.get(key)
            if base is None:
                problems.append(f"{key}: no baseline row")
                continue
            joined += 1
            values = {m["name"]: m for m in corner["measurements"]}
            for name in MEASURES:
                token = base["raw"][name]
                rec = float(token)
                got = values.get(name, {}).get("value")
                if got is None:
                    problems.append(f"{key}: measurement {name} missing")
                    continue
                delta = got - rec
                delta_rows.append([
                    point, corner["process"], corner["temperature_c"],
                    corner["params"]["vdd_val"], name,
                    token, repr(got), repr(delta),
                ])
                if abs(Decimal(repr(delta))) > abs(quantum(token)):
                    problems.append(
                        f"{key}: {name} disagrees beyond printed precision: "
                        f"record {token}, klt {got!r}")
            n_fb = values["n_fb"]["value"]
            ndo = values["ndo"]["value"]
            ratio_pass = abs(n_fb - n_target) < 0.05 and abs(ndo - n_target) < 0.05
            if ratio_pass != (base["ratio_pass"] == "1"):
                problems.append(f"{key}: ratio_pass klt {ratio_pass} vs record {base['ratio_pass']}")
            if not ratio_pass:
                problems.append(f"{key}: ratio check FAILED (n_fb={n_fb}, ndo={ndo}, N={n_target})")
            fbpw = values["fbpw"]["value"]
            fbpw_s = fbpw + n_target * tvco if fbpw < 0 else fbpw
            if abs(fbpw_s - float(base["fbpw_s"])) > abs(quantum(base["fbpw_s"])):
                problems.append(f"{key}: fbpw_s {fbpw_s!r} vs record {base['fbpw_s']}")

    # --- retiming-margin join ------------------------------------------------
    margin_rows: list[tuple] = []
    for group in ("f200n64a", "f200n64b"):
        envelope = json.loads((RUNS / group / "report.json").read_text(encoding="utf-8"))
        for corner in envelope["corners"]:
            key = (corner["process"], corner["temperature_c"], corner["params"]["vdd_val"])
            base = margins.get(key)
            if base is None:
                problems.append(f"margin {key}: no baseline row")
                continue
            values = {m["name"]: m for m in corner["measurements"]}
            t_arr = values["t_arr"]["value"]
            setup = values["setup_margin"]["value"]
            hold = values["hold_margin"]["value"]
            tsetup, thold = dff[key]
            setup_re = tvco - t_arr - tsetup
            hold_re = t_arr - thold
            closes = setup > 0 and hold > 0
            # The margin CSV prints six significant digits and the envelope's
            # .meas tokens carry six too, so both joins are compared at their
            # own printed precision, like the raw measurements.
            if abs(Decimal(repr(setup - base["setup_margin_s"]))) > abs(quantum(base["tokens"]["setup_margin_s"])):
                problems.append(f"margin {key}: setup {setup!r} vs record {base['setup_margin_s']!r}")
            if abs(Decimal(repr(hold - base["hold_margin_s"]))) > abs(quantum(base["tokens"]["hold_margin_s"])):
                problems.append(f"margin {key}: hold {hold!r} vs record {base['hold_margin_s']!r}")
            if abs(setup - setup_re) > abs(setup) * 1e-5 or abs(hold - hold_re) > abs(hold) * 1e-5:
                problems.append(f"margin {key}: in-envelope margins disagree with DFF-join recomputation")
            if closes != (base["verdict"] == "CLOSES"):
                problems.append(f"margin {key}: verdict {closes} vs record {base['verdict']}")
            margin_rows.append((key, t_arr, tsetup, thold, setup, hold, closes))

    expected = len(record) - sum(1 for k in record if k[0] == PILOT_POINT)
    if joined != expected:
        problems.append(f"joined {joined} points, expected {expected}")

    with (HERE / "deltas.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["point", "process", "temp_c", "vdd_v", "measurement",
                         "record", "klt_sim", "delta"])
        writer.writerows(delta_rows)

    print(f"joined {joined}/{expected} points; {len(delta_rows)} measurement deltas "
          f"written to deltas.csv; {len(margin_rows)} margin joins")
    for problem in problems:
        print(f"PROBLEM {problem}", file=sys.stderr)
    if problems:
        raise SystemExit(1)
    print("all eleven measurements match the record at printed precision; "
          "ratio checks, fbpw_s and both margin verdicts agree")


if __name__ == "__main__":
    main()
