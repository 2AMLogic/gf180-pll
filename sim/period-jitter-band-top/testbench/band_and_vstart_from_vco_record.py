#!/usr/bin/env python3
"""Where this campaign's per-corner VCO band code and release voltage come from.

`sim/period-jitter` measures the deterministic (control-ripple-driven) period
jitter of the locked output at ONE operating point: f_ref = 25 MHz, N = 6,
f_out = **150 MHz**, VCO band 6. This campaign is the same measurement at the
**200 MHz top of the ratified output band** (`spec/pll.md#output-band`), and
it exists because nothing in this repository bounds closed-loop jitter there
-- the binding point, and the same one at which `sim/reference-spur`'s two
coldest corners already land over the spur line once scaled.

Moving to 200 MHz is not a one-parameter change, and this script is where the
arithmetic that decides the rest of it is written down.

**The band code is not a free choice.** `spec/pll.md`'s band-selection rule
(normative, from DR-003 Decision 4) says a system targeting output frequency
`f` must configure **the lowest 3-bit band code that reaches `f`**, inside the
DR-003 Decision 5 control-voltage window of 0.9-2.7 V. That rule is what keeps
Kvco under DR-001's ~150 MHz/V fixed-filter bound: two codes that both reach
`f` do not present the same gain to the loop, because the higher code reaches
it near the bottom of its own Vctrl range where its Kvco is already large. A
campaign that picked one convenient static band for all 45 corners would be
measuring a **mis-configured part** at some of them, and `spec/pll.md` says
plainly that no row of the specification applies to such a part.

Applied to `sim/vco-tuning-range`'s committed f(Vctrl) table at 200 MHz, the
rule does not select one code for the whole grid:

- **band 6 at 34 of the 45 PVT points**, and
- **band 7 at the remaining 11** -- the cold and/or high-supply points where
  band 6's curve tops out below 200 MHz.

That split is a *finding*, not a workaround: at 150 MHz one static code (6)
covers all 45 corners, which is exactly why `sim/reference-spur` and
`sim/period-jitter` could hold their band fixed; at 200 MHz no single code
does. Both halves of the split are inside the Kvco bound (74.7-117.0 MHz/V
across the grid, against 150 MHz/V), so the rule delivers what DR-003 says it
delivers -- but the loop gain `A = Icp*Kvco/N` this campaign presents to the
fixed filter therefore varies by 1.6x across its own grid, where
`sim/period-jitter`'s varies by 1.05x.

**The release voltage follows from the band.** As in `sim/period-jitter`,
every PVT point is released at *its own* predicted lock point -- the control
voltage at which that corner's curve, in that corner's rule-selected band,
reaches N*f_ref = 200 MHz -- because the loop's slow closed-loop pole is
1/(R*C1) = 9.3 us and a common release voltage would spend tens of
microseconds slewing at Icp/C1 = 14 mV/us before any measurement window could
open.

    python3 band_and_vstart_from_vco_record.py            # the table tb.json carries
    python3 band_and_vstart_from_vco_record.py --check    # ... and diff it against tb.json
    python3 band_and_vstart_from_vco_record.py --emit     # regenerate tb.json's sweeps.op + grid

It reads only committed CSV. No simulator, no PDK, no network.

**The interpolation itself is not re-implemented here.** It is loaded from
`sim/reference-spur/testbench/vstart_from_vco_record.py`, the same file
`sim/period-jitter/testbench/vstart_from_vco_record.py` loads it from, so all
three campaigns are physically incapable of disagreeing about what the
committed VCO record says a corner does.

Nothing downstream trusts these numbers to be right. The release point only
decides where the loop STARTS; every reported quantity is measured after the
loop has closed on its own lock point, and a point whose estimate missed badly
enough to leave the loop unlocked fails this manifest's `ferr`/`fout`/`nmeas`
lock checks and is reported as a failing point, never as a jitter number. The
band code is different in kind -- it is a real static configuration input of
the part, not an estimate -- which is why this script derives it from the
ratified rule rather than from convenience, and why `--check` refuses a
manifest that has drifted from it.
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
VCTRLS = _refspur.VCTRLS
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
    "ff": "fastest MOS",
    "ss": "slowest MOS",
    "fs": "skewed MOS -- the sign of the UP/DN current asymmetry one way",
    "sf": "skewed MOS -- the sign of the UP/DN current asymmetry the other way",
}

#: The 3-bit band codes, in the order the band-selection rule scans them:
#: lowest first, take the first that reaches the target.
BAND_CODES = tuple(range(8))

#: DR-001's fixed-filter bound on Kvco, restated by `spec/pll.md` row 17 as
#: "<= 150 MHz/V at every legal operating point under the band-selection rule".
KVCO_BOUND_HZ_PER_V = 150e6


def kvco_at(curve, vctrl):
    """Local slope of this corner's f(Vctrl) curve at `vctrl`, in Hz/V.

    The same piecewise-linear reading of the committed record `interp_vctrl`
    inverts: the segment the operating point falls in, differenced.
    """
    for i in range(len(VCTRLS) - 1):
        if VCTRLS[i] <= vctrl <= VCTRLS[i + 1]:
            return (curve[i + 1] - curve[i]) / (VCTRLS[i + 1] - VCTRLS[i])
    return None


def select_band(curves_by_band, key, target):
    """The band-selection rule, applied to one PVT point.

    `spec/pll.md#band-selection-rule`: the LOWEST 3-bit band code that reaches
    `target`. "Reaches" means the committed f(Vctrl) curve brackets `target`
    inside the 0.9-2.7 V control window (DR-003 Decision 5) -- which is exactly
    the condition `interp_vctrl` returns non-None for, since that record is
    sampled over precisely that window.

    Returns ``(band, vstart, kvco)``, or ``(None, None, None)`` if no band
    reaches the target at this corner.
    """
    for band in BAND_CODES:
        curve = curves_by_band[band].get(key)
        if curve is None:
            continue
        vstart = interp_vctrl(curve, target)
        if vstart is not None:
            return band, vstart, kvco_at(curve, vstart)
    return None, None, None


def full_grid(manifest):
    """(corner, temp, vdd, supply-alias) for every point of the mandated matrix."""
    supplies = supplies_of(manifest)
    out = []
    for corner in MOS_BUNDLES:
        for temp in manifest["temperatures_c"]:
            for alias in ("low", "nom", "high"):
                out.append((corner, float(temp), supplies[alias], alias))
    return out


def point_id(band, vstart):
    """`b<band>vs<value>`, with `.` spelled `p`.

    `sim/harness/README.md`: "Point ids are written out, not derived from a
    value ... the value spelled exactly as the deck spells it". This axis
    carries TWO things that must both be legible in the id, because either one
    silently wrong produces a deck that simulates and measures the wrong thing:
    the band code the part is configured into, and the voltage the loop is
    released from.
    """
    return "b%dvs%s" % (band, ("%.3f" % vstart).replace(".", "p"))


def derive_table(manifest):
    """[(corner, temp, vdd, alias, band, vstart, kvco)] over the mandated matrix."""
    target = float(manifest["params"]["fref"]) * int(float(manifest["params"]["nratio"]))
    curves_by_band = {band: load_curves("band%d" % band) for band in BAND_CODES}
    rows = []
    for corner, temp, vdd, alias in full_grid(manifest):
        band, vstart, kvco = select_band(curves_by_band, (corner, temp, vdd), target)
        rows.append((corner, temp, vdd, alias, band, vstart, kvco))
    return rows, target


def emit(manifest, rows, target):
    """The `sweeps.op` + `grid` fragment `tb.json` carries, regenerated."""
    points = {}
    for _corner, _temp, _vdd, _alias, band, vstart, _kvco in rows:
        points[point_id(band, vstart)] = {
            "params": {
                "vstart": "%.3f" % vstart,
                "b0_code": str(band & 1),
                "b1_code": str((band >> 1) & 1),
                "b2_code": str((band >> 2) & 1),
            }
        }
    grid = []
    for corner, temp, vdd, alias, band, vstart, kvco in rows:
        grid.append(
            {
                "description": (
                    "%s / %g C / %.2f V -- %s. Band %d is the LOWEST code that reaches "
                    "%.4f MHz at this corner (spec/pll.md#band-selection-rule, "
                    "normative), and %.3f V is where that band's committed f(Vctrl) "
                    "curve from VCO record %s crosses it; local Kvco there is "
                    "%.1f MHz/V. One block per PVT point because both the band code "
                    "and the release voltage are per point; the union of the 45 blocks "
                    "is exactly the mandated PVT matrix."
                    % (corner, temp, vdd, BUNDLE_NOTE[corner], band, target / 1e6,
                       vstart, VCO_RECORD, kvco / 1e6)
                ),
                "corners": [corner],
                "temperatures_c": [temp],
                "supplies": [alias],
                "axes": {"op": [point_id(band, vstart)]},
            }
        )
    return {
        "sweeps": {
            "op": {
                "description": (
                    "the per-PVT-point operating point: the VCO band code the "
                    "band-selection rule selects for %.4f MHz at that corner, and the "
                    "control-node release voltage at which that band's committed "
                    "f(Vctrl) curve (record %s) reaches it. band_and_vstart_from_vco_"
                    "record.py in this directory recomputes all 45 from that record "
                    "and the ratified rule, and diffs them against this manifest. The "
                    "band code is a real static configuration input of the part, so "
                    "getting it wrong would mean measuring a mis-configured part; the "
                    "release voltage only sets where the loop STARTS, and a point "
                    "whose estimate missed far enough to leave the loop unlocked fails "
                    "this manifest's ferr/fout/nmeas checks rather than being reported "
                    "as jitter." % (target / 1e6, VCO_RECORD)
                ),
                "points": points,
            }
        },
        "grid": grid,
    }


def declared_map(manifest):
    """{(corner, temp, supply-alias): (band, vstart)} as tb.json spells it."""
    declared = {}
    points = manifest.get("sweeps", {}).get("op", {}).get("points", {})
    for block in manifest.get("grid", []):
        for corner in block["corners"]:
            for temp in block["temperatures_c"]:
                for alias in block["supplies"]:
                    for pid in block["axes"]["op"]:
                        spec = points.get(pid)
                        if spec is None:
                            declared[(corner, float(temp), alias)] = None
                            continue
                        params = spec["params"]
                        band = (
                            int(params["b0_code"])
                            + 2 * int(params["b1_code"])
                            + 4 * int(params["b2_code"])
                        )
                        declared[(corner, float(temp), alias)] = (
                            band,
                            float(params["vstart"]),
                        )
    return declared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="compare against tb.json's sweeps.op + grid and exit non-zero on a mismatch",
    )
    parser.add_argument(
        "--emit", action="store_true",
        help="print the sweeps.op + grid JSON fragment tb.json carries",
    )
    parser.add_argument(
        "--tol", type=float, default=5e-3,
        help="tolerance in volts for --check (default 5 mV, the rounding tb.json carries)",
    )
    args = parser.parse_args()

    manifest = json.loads((HERE / "tb.json").read_text())
    rows, target = derive_table(manifest)

    if args.emit:
        print(json.dumps(emit(manifest, rows, target), indent=2))
        return 0

    declared = declared_map(manifest)
    print("band + vstart from %s under spec/pll.md's band-selection rule, "
          "f_out = %.4f MHz" % (VCO_RECORD, target / 1e6))
    print("%-9s %6s %6s | %5s %9s %10s | %s"
          % ("corner", "temp", "vdd", "band", "vstart", "Kvco MHz/V", "tb.json"))
    bad = 0
    per_band = {}
    for corner, temp, vdd, alias, band, vstart, kvco in rows:
        got = declared.get((corner, temp, alias))
        flag = ""
        if band is None:
            flag = "  NO BAND REACHES THE TARGET AT THIS CORNER"
            bad += 1
        else:
            per_band[band] = per_band.get(band, 0) + 1
            if kvco > KVCO_BOUND_HZ_PER_V:
                flag = "  Kvco OVER spec/pll.md row 17's 150 MHz/V bound"
                bad += 1
            elif got is None:
                flag = "  MISSING from tb.json's grid"
                bad += 1
            elif got[0] != band:
                flag = "  BAND MISMATCH -- tb.json says band %d" % got[0]
                bad += 1
            elif abs(got[1] - vstart) > args.tol:
                flag = "  VSTART MISMATCH"
                bad += 1
        print(
            "%-9s %6g %6.2f | %5s %9s %10s | %s%s"
            % (
                corner, temp, vdd,
                "-" if band is None else str(band),
                "-" if vstart is None else "%.4f" % vstart,
                "-" if kvco is None else "%.1f" % (kvco / 1e6),
                "-" if got is None else "band %d @ %.4f V" % got,
                flag,
            )
        )

    extra = sorted(set(declared) - {(c, t, a) for c, t, _v, a, _b, _s, _k in rows})
    for key in extra:
        print("tb.json declares %s, which is not a point of the mandated PVT matrix" % (key,))
        bad += 1

    print("\nband-selection rule outcome: " + ", ".join(
        "band %d at %d of %d points" % (band, n, len(rows))
        for band, n in sorted(per_band.items())
    ))

    if args.check:
        if bad:
            print("FAIL: %d point(s) do not match tb.json" % bad, file=sys.stderr)
            return 1
        print("PASS: all %d tb.json operating points match the committed VCO "
              "record under the ratified band-selection rule" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
