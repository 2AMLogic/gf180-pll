"""Verify the migration's planned corner set against the committed record.

The test plan of #1090: dry-run every generated request, take the full
(rate, divisor, process, temperature, supply) key set the fleet would
actually simulate, and compare it with the f6eeac7 chain record
``20261114-093804-ad9eef8`` minus the #1083 pilot's 45 ``f200n33`` points.
Duplicate or missing keys fail; extra keys fail.  Prints one line per slice
group and a per-request corner count; exit 0 only on an exact match.

Key semantics: the rate and divisor come from the request's point id (the
netlist body pins them, so the request stem is the point of record), and
process/temperature/supply come from the dry-run ``units[]`` ``corner_id``
(``<process>/novdd/<temp>C/params:vdd_val=<v>``) -- the identity the fleet
will echo back, not a re-derivation from the request JSON.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUESTS = HERE / "requests"
RECORD = HERE.parent.parent / "records" / "20261114-093804-ad9eef8.md"
PILOT_POINT = "f200n33"

_ROW = re.compile(r"^\s*\|\s*`([a-z]+)_(-?\d+c)_(\d\.\d\dv)_(f\d+n\d+)`\s*\|")


def baseline_keys() -> dict[tuple[str, int, str, int, float], None]:
    keys: dict[tuple[str, int, str, int, float], None] = {}
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        process, temp_c, vdd_v, point = match.groups()
        rate, divisor = point[1:].split("n")
        key = (process, int(temp_c.rstrip("c")), point, int(rate), float(vdd_v.rstrip("v")))
        if point == PILOT_POINT:
            continue
        if key in keys:
            raise SystemExit(f"error: duplicate baseline row {key}")
        keys[key] = None
    return keys


def planned_keys() -> dict[tuple[str, int, str, int, float], Counter]:
    keys: dict[tuple[str, int, str, int, float], Counter] = {}
    for request_path in sorted(REQUESTS.glob("*.request.json")):
        stem = request_path.name[: -len(".request.json")]
        proc = subprocess.run(
            ["klt", "sim", str(request_path), "--dry-run", "--format", "json"],
            capture_output=True, text=True, cwd=HERE,
        )
        if proc.returncode != 0:
            print(proc.stdout[-2000:], file=sys.stderr)
            print(proc.stderr[-2000:], file=sys.stderr)
            raise SystemExit(f"error: dry-run failed for {stem} (exit {proc.returncode})")
        report = json.loads(proc.stdout)
        if report.get("dry_run") is not True or report.get("status") != "valid":
            raise SystemExit(f"error: {stem}: unexpected dry-run status {report.get('status')!r}")
        rate = 200 if stem.startswith("f200") else 10
        # f200n64 splits into two requests (one per joined tsetup group); both
        # cover the same sweep point f200n64.
        point = stem[:-1] if stem[-1] in "ab" else stem
        divisor = int(point[5:7])
        count = 0
        for unit in report["units"]:
            corner_id = unit["corner_id"]
            process, _, temp_c, params = corner_id.split("/")
            vdd = float(params.split("vdd_val=")[1])
            key = (process, int(temp_c.rstrip("C")), point, rate, vdd)
            keys.setdefault(key, Counter())[stem] += 1
            count += 1
        print(f"{stem}: {count} corner(s)")
    return keys


def main() -> None:
    baseline = baseline_keys()
    planned = planned_keys()
    duplicates = {k: v for k, v in planned.items() if sum(v.values()) > 1}
    missing = sorted(set(baseline) - set(planned))
    extra = sorted(set(planned) - set(baseline))
    by_slice: Counter = Counter(key[2].rsplit("n", 1)[0] if key[2].startswith("f010")
                                else "f200" for key in planned)
    print(f"\nplanned {sum(sum(c.values()) for c in planned.values())} corners "
          f"across {len(set(k[2] for k in planned))} requests; "
          f"baseline-minus-pilot {len(baseline)}")
    if duplicates:
        for key, counts in sorted(duplicates.items()):
            print(f"DUPLICATE {key}: {dict(counts)}", file=sys.stderr)
    for key in missing:
        print(f"MISSING {key}", file=sys.stderr)
    for key in extra:
        print(f"EXTRA {key}", file=sys.stderr)
    if duplicates or missing or extra:
        raise SystemExit(2)
    print("key set matches the committed record minus the pilot: "
          "no duplicates, none missing, none extra")


if __name__ == "__main__":
    main()
