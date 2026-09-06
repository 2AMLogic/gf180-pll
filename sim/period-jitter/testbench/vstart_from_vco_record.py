#!/usr/bin/env python3
"""Where this campaign's `vs` axis (the control-node release voltage) comes from.

`sim/period-jitter` measures a STEADY-STATE property -- the period sequence of
the *locked* output -- not acquisition (`sim/lock-time`, #12, owns that claim).
The loop's slow closed-loop pole is 1/(R*C1) = 9.3 us regardless of Icp
(`spec/pll.md`'s ~43 us structural settling floor, DR-006 Decision 7), so a
control-voltage error decays by only one e-fold per 9.3 us. Across the full
45-point PVT grid the lock point spans 1.09-2.43 V, so releasing every corner
at one common voltage would spend tens of microseconds just slewing the
control node at Icp/C1 = 14 mV/us before any measurement window could start --
at this campaign's 100 ps internal-timestep ceiling that is not affordable,
and the residual would dominate the very ripple the jitter is made of.

So every PVT point is released at **its own** predicted lock point: the
control voltage at which `sim/vco-tuning-range`'s COMMITTED f(Vctrl) table
puts that corner's ring at N*f_ref = 150 MHz, by linear interpolation between
its seven control points. This script is that arithmetic, written down and
re-runnable, so the 45 numbers in `tb.json` are reproducible from committed
evidence rather than asserted:

    python3 vstart_from_vco_record.py            # the table tb.json carries
    python3 vstart_from_vco_record.py --check    # ... and diff it against tb.json
    python3 vstart_from_vco_record.py --emit     # regenerate tb.json's sweeps.vs + grid

It reads only committed CSV. No simulator, no PDK, no network.

**The interpolation itself is not re-implemented here.** It is loaded from
`sim/reference-spur/testbench/vstart_from_vco_record.py`, which introduced it
for the same operating point (f_ref = 25 MHz, N = 6, f_out = 150 MHz, band 6)
on a five-corner subset -- the same cross-directory `load_module` reuse
`derive.py` already uses for `sim/vco-tuning-range/testbench/_numeric.py`.
Single-sourcing it is the point: the two campaigns must never disagree about
what the committed VCO record says a corner's lock point is. What is new here
is the *coverage* -- all 45 points of the mandated PVT matrix rather than five
hand-picked ones -- and the `--emit` mode that generates the manifest fragment
those 45 points need.

Nothing downstream trusts these numbers to be right. The release point only
decides where the loop STARTS; every reported quantity is measured after the
loop has closed on its own lock point, and how far the estimate missed is
itself gated per point by the manifest's `ferr` / `fout` / `nmeas` lock checks.
A point whose estimate missed badly enough to leave the loop unlocked fails
those checks and is reported as such -- it is never silently reported as
jitter.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]

sys.path.insert(0, str(SIM))
from harness.derived import load_module  # noqa: E402

_refspur = load_module(SIM / "reference-spur" / "testbench" / "vstart_from_vco_record.py")
VCO_RECORD = _refspur.VCO_RECORD
interp_vctrl = _refspur.interp_vctrl
load_curves = _refspur.load_curves
supplies_of = _refspur.supplies_of

#: The MOS-bundle corner set `tb.json` names (`sim/harness/corners.py`'s
#: `CORNER_SETS["mos"]`), in the order the runner expands it.
MOS_BUNDLES = ("typical", "ff", "ss", "fs", "sf")

#: Human-readable why-this-corner text, so every generated `grid` block can
#: carry the `description` `sim/harness/README.md` requires of it.
BUNDLE_NOTE = {
    "typical": "nominal MOS",
    "ff": "fastest MOS (highest lock point on this grid)",
    "ss": "slowest MOS (lowest lock point on this grid)",
    "fs": "skewed MOS -- the sign of the UP/DN current asymmetry one way",
    "sf": "skewed MOS -- the sign of the UP/DN current asymmetry the other way",
}

SUPPLY_ALIAS = {"low": -1, "nom": 0, "high": +1}


def point_id(vstart: float) -> str:
    """`vs<value>` with `.` spelled `p`, the repo's written-out point-id form.

    `sim/harness/README.md`: "Point ids are written out, not derived from a
    value ... the value spelled exactly as the deck spells it". Three decimals
    is a millivolt, which is finer than the 5 mV `--tol` the check runs at and
    is what `sim/reference-spur`'s five ids already use (`vs1p795`, ...).
    """
    return "vs" + ("%.3f" % vstart).replace(".", "p")


def full_grid(manifest):
    """(corner, temp, vdd, supply-alias) for every point of the mandated matrix."""
    supplies = supplies_of(manifest)
    out = []
    for corner in MOS_BUNDLES:
        for temp in manifest["temperatures_c"]:
            for alias in ("low", "nom", "high"):
                out.append((corner, float(temp), supplies[alias], alias))
    return out


def derive_table(manifest, band):
    """[(corner, temp, vdd, alias, vstart-or-None)] over the full PVT matrix."""
    target = float(manifest["params"]["fref"]) * int(float(manifest["params"]["nratio"]))
    curves = load_curves("band%d" % band)
    rows = []
    for corner, temp, vdd, alias in full_grid(manifest):
        curve = curves.get((corner, temp, vdd))
        rows.append((corner, temp, vdd, alias, None if curve is None else interp_vctrl(curve, target)))
    return rows, target


def emit(manifest, rows, band, target):
    """The `sweeps.vs` + `grid` fragment `tb.json` carries, regenerated."""
    points = {}
    for corner, temp, vdd, _alias, vstart in rows:
        points[point_id(vstart)] = {"params": {"vstart": "%.3f" % vstart}}
    grid = []
    for corner, temp, vdd, alias, vstart in rows:
        grid.append(
            {
                "description": (
                    "%s / %g C / %.2f V -- %s; released at %.3f V, this corner's own "
                    "150 MHz control voltage from VCO record %s (band %d). One block "
                    "per PVT point because the release voltage is per point; the union "
                    "of the 45 blocks is exactly the mandated PVT matrix."
                    % (corner, temp, vdd, BUNDLE_NOTE[corner], vstart, VCO_RECORD, band)
                ),
                "corners": [corner],
                "temperatures_c": [temp],
                "supplies": [alias],
                "axes": {"vs": [point_id(vstart)]},
            }
        )
    return {
        "sweeps": {
            "vs": {
                "description": (
                    "control-node release voltage, one per PVT point: the control "
                    "voltage at which sim/vco-tuning-range's committed f(Vctrl) table "
                    "(record %s, band %d) puts that corner's ring at %.4f MHz. "
                    "vstart_from_vco_record.py in this directory recomputes all 45 "
                    "from that record and diffs them against this manifest. It sets "
                    "only where the loop STARTS -- every reported number is measured "
                    "microseconds later, after the loop has closed on its own lock "
                    "point, and a point whose release estimate missed badly enough to "
                    "leave the loop unlocked fails this manifest's ferr/fout/nmeas "
                    "lock checks rather than being reported as jitter."
                    % (VCO_RECORD, band, target / 1e6)
                ),
                "points": points,
            }
        },
        "grid": grid,
    }


def declared_map(manifest):
    """{(corner, temp, vdd-alias): vstart} as tb.json's grid actually spells it."""
    declared = {}
    points = manifest.get("sweeps", {}).get("vs", {}).get("points", {})
    for block in manifest.get("grid", []):
        for corner in block["corners"]:
            for temp in block["temperatures_c"]:
                for alias in block["supplies"]:
                    for pid in block["axes"]["vs"]:
                        spec = points.get(pid)
                        if spec is None:
                            declared[(corner, float(temp), alias)] = None
                            continue
                        declared[(corner, float(temp), alias)] = float(spec["params"]["vstart"])
    return declared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--band", type=int, default=6, help="VCO band code (default 6)")
    parser.add_argument(
        "--check", action="store_true",
        help="compare against tb.json's sweeps.vs + grid and exit non-zero on a mismatch",
    )
    parser.add_argument(
        "--emit", action="store_true",
        help="print the sweeps.vs + grid JSON fragment tb.json carries",
    )
    parser.add_argument(
        "--tol", type=float, default=5e-3,
        help="tolerance in volts for --check (default 5 mV, the rounding tb.json carries)",
    )
    args = parser.parse_args()

    manifest = json.loads((HERE / "tb.json").read_text())
    rows, target = derive_table(manifest, args.band)

    if args.emit:
        print(json.dumps(emit(manifest, rows, args.band, target), indent=2))
        return 0

    declared = declared_map(manifest)
    print("vstart from %s, band %d, f_out = %.4f MHz" % (VCO_RECORD, args.band, target / 1e6))
    print("%-9s %6s %6s | %9s %9s" % ("corner", "temp", "vdd", "vstart", "tb.json"))
    bad = 0
    for corner, temp, vdd, alias, vstart in rows:
        got = declared.get((corner, temp, alias))
        flag = ""
        if vstart is None:
            flag = "  UNREACHABLE in this band at this corner"
            bad += 1
        elif got is None:
            flag = "  MISSING from tb.json's grid"
            bad += 1
        elif abs(got - vstart) > args.tol:
            flag = "  MISMATCH"
            bad += 1
        print(
            "%-9s %6g %6.2f | %9s %9s%s"
            % (
                corner, temp, vdd,
                "-" if vstart is None else "%.4f" % vstart,
                "-" if got is None else "%.4f" % got,
                flag,
            )
        )

    extra = sorted(set(declared) - {(c, t, a) for c, t, _v, a, _s in rows})
    for key in extra:
        print("tb.json declares %s, which is not a point of the mandated PVT matrix" % (key,))
        bad += 1

    if args.check:
        if bad:
            print("FAIL: %d point(s) do not match tb.json" % bad, file=sys.stderr)
            return 1
        print("PASS: all %d tb.json vstart values match the committed VCO record" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
