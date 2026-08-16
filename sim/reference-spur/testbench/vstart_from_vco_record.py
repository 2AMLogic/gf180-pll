#!/usr/bin/env python3
"""Where tb.json's `vs` axis (the control-node release voltage) comes from.

The measurement deck releases the loop at `vstart` and reads the spectrum a
few microseconds later. That release point is not a convenience knob: the
loop's slow closed-loop pole is 1/(R*C1) = 9.3 us regardless of Icp
(spec/pll.md's ~43 us structural settling floor, DR-006 Decision 7), so a
control-voltage error decays by only one e-fold per 9.3 us. Released 0.7 V
away from its lock point -- which is the spread across this PVT grid -- the
loop would need tens of microseconds of transient at a 100 ps internal
timestep before the residual stopped dominating the very ripple the spur is
made of. Released near it, ~8 us is enough.

So `vstart` is the corner's own predicted lock point: the control voltage at
which the ring runs at N*f_ref, read out of `sim/vco-tuning-range`'s COMMITTED
f(Vctrl) table by linear interpolation between its seven control points. This
script is that arithmetic, written down and re-runnable, so the numbers in
tb.json are reproducible from committed evidence rather than asserted:

    python3 vstart_from_vco_record.py            # the table tb.json carries
    python3 vstart_from_vco_record.py --check    # ... and diff it against tb.json

It reads only committed CSV. No simulator, no PDK, no network.

Nothing downstream trusts these numbers to be right. The release point only
decides where the loop STARTS; every reported quantity is measured after the
loop has closed on its own lock point, and how far the estimate missed is
itself measured and reported per point as `drift_q_fc` (the extra charge the
residual settling moves per reference cycle) alongside the spur.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]

#: The committed VCO characterization this interpolates. Record
#: 20260804-162735-72883fb is `sim/vco-tuning-range`'s current band-plan
#: record (63 corners x 8 bands x 7 control voltages).
VCO_RECORD = "20260804-162735-72883fb"
VCO_CSV = SIM / "vco-tuning-range" / "corners" / VCO_RECORD / "raw_measures.csv"

#: The seven control voltages that record's f1..f7 columns are measured at.
VCTRLS = (0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.7)


def interp_vctrl(freqs, target):
    """Control voltage at which this corner's curve reaches `target` (Hz)."""
    if target < freqs[0] or target > freqs[-1]:
        return None
    for i in range(len(VCTRLS) - 1):
        if freqs[i] <= target <= freqs[i + 1]:
            span = freqs[i + 1] - freqs[i]
            if span <= 0:
                return VCTRLS[i]
            f = (target - freqs[i]) / span
            return VCTRLS[i] + f * (VCTRLS[i + 1] - VCTRLS[i])
    return None


def load_curves(band):
    curves = {}
    with VCO_CSV.open() as handle:
        for row in csv.DictReader(handle):
            if row["band"] != band:
                continue
            key = (row["corner"], float(row["temp_c"]), float(row["vdd"]))
            curves[key] = [float(row["f%d" % i]) for i in range(1, 8)]
    return curves


def manifest_points(manifest):
    """(corner, temp, vdd, vs-point-id) for every point tb.json's grid runs."""
    supplies = {
        "low": round(manifest["nominal_supply_v"] * (1 - manifest["supply_tolerance"]), 2),
        "nom": round(manifest["nominal_supply_v"], 2),
        "high": round(manifest["nominal_supply_v"] * (1 + manifest["supply_tolerance"]), 2),
    }
    out = []
    for block in manifest["grid"]:
        for corner in block["corners"]:
            for temp in block["temperatures_c"]:
                for supply in block["supplies"]:
                    vdd = supplies.get(supply, supply)
                    for point_id in block["axes"]["vs"]:
                        out.append((corner, float(temp), float(vdd), point_id))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--band", type=int, default=6, help="VCO band code (default 6)")
    parser.add_argument(
        "--check", action="store_true",
        help="compare against tb.json's sweeps.vs points and exit non-zero on a mismatch",
    )
    parser.add_argument(
        "--tol", type=float, default=5e-3,
        help="tolerance in volts for --check (default 5 mV, the rounding tb.json carries)",
    )
    args = parser.parse_args()

    manifest = json.loads((HERE / "tb.json").read_text())
    fref = float(manifest["params"]["fref"])
    nratio = int(float(manifest["params"]["nratio"]))
    target = fref * nratio
    curves = load_curves("band%d" % args.band)
    declared = {
        pid: float(spec["params"]["vstart"])
        for pid, spec in manifest["sweeps"]["vs"]["points"].items()
    }

    print("vstart from %s, band %d, f_out = %.4f MHz" % (VCO_RECORD, args.band, target / 1e6))
    print("%-9s %6s %6s | %9s %9s" % ("corner", "temp", "vdd", "vstart", "tb.json"))
    bad = 0
    for corner, temp, vdd, point_id in manifest_points(manifest):
        curve = curves.get((corner, temp, vdd))
        if curve is None:
            print("%-9s %6g %6.2f | %9s %9s  MISSING from the VCO record"
                  % (corner, temp, vdd, "-", declared.get(point_id, "-")))
            bad += 1
            continue
        vstart = interp_vctrl(curve, target)
        got = declared.get(point_id)
        flag = ""
        if vstart is None:
            flag = "  UNREACHABLE in this band at this corner"
            bad += 1
        elif got is None or abs(got - vstart) > args.tol:
            flag = "  MISMATCH"
            bad += 1
        print("%-9s %6g %6.2f | %9s %9s%s"
              % (corner, temp, vdd,
                 "-" if vstart is None else "%.4f" % vstart,
                 "-" if got is None else "%.4f" % got, flag))

    if args.check:
        if bad:
            print("FAIL: %d point(s) do not match tb.json" % bad, file=sys.stderr)
            return 1
        print("PASS: every tb.json vstart matches the committed VCO record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
