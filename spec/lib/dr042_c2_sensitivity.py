#!/usr/bin/env python3
"""Model-based C2 sensitivity of the baseline loop margins (DR-042, Decision 3).

An ESTIMATE, not a measurement.  It re-evaluates the committed option-A
baseline (sim/loop-dynamics record 20260731-202550-82af5a9) with C2 scaled by
a fixed fraction in the fitted 3-element filter model (series R + C1 to
ground, C2 to ground) and reports how far phase margin and crossover move.
Only C2's value changes; R, C1 and the loop-gain constant A = Icp*Kvco/N are
held at the baseline's fitted/measured values.  It says nothing about the
option-B device's parasitics, voltage coefficient or process spread.

Usage: python3 -I spec/lib/dr042_c2_sensitivity.py [--dc2 0.02] [--grid 25]
"""
import argparse
import csv
import math
import pathlib

REC = "sim/loop-dynamics/corners/20260731-202550-82af5a9/"
# DR-006 Decision 5: required Icp-trim code per f_ref
RULE = {"1e+06": 4, "2e+06": 4, "4e+06": 3, "8e+06": 2, "1.6e+07": 1, "2.5e+07": 1}


def rows(path):
    with open(path) as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith("#")))


def margin(r, c1, c2, a):
    """(phase margin deg, crossover Hz) of T(s) = a*(1+s*r*c1)/(s^2*(c1+c2)*(1+s*r*ceq))."""
    ct, ceq = c1 + c2, c1 * c2 / (c1 + c2)

    def t(w):
        s = 1j * w
        return a * (1 + s * r * c1) / (s * s * ct * (1 + s * r * ceq))

    lo, hi = 1.0, 1e9
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if abs(t(mid)) > 1 else (lo, mid)
    v = t(lo)
    pm = 180 + math.degrees(math.atan2(v.imag, v.real))
    return (pm - 360 if pm > 180 else pm), lo / 2 / math.pi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dc2", type=float, default=0.02)
    ap.add_argument("--grid", type=int, default=25)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    d = pathlib.Path(args.root) / REC
    filt = [x for x in rows(d / "filter_rc.csv") if float(x["vctrl_v"]) > 0.89]
    cells = rows(d / "loop_margins.csv")
    res = []
    for c in cells:
        a0, a1 = float(c["a_min"]), float(c["a_max"])
        worst, dpm, dfc = 1e9, 0.0, 0.0
        for x in filt:
            r, c1, c2 = float(x["r_ohm"]), float(x["c1_f"]), float(x["c2_f"])
            for k in range(args.grid):
                a = a0 * (a1 / a0) ** (k / (args.grid - 1))
                p0, f0 = margin(r, c1, c2, a)
                p1, f1 = margin(r, c1, c2 * (1 + args.dc2), a)
                worst = min(worst, p0)
                dpm, dfc = max(dpm, p0 - p1), max(dfc, abs(f1 / f0 - 1))
        res.append((c, worst, dpm, dfc))
    print(f"C2 scaled by {args.dc2:+.1%}; A grid {args.grid} points; {len(res)} cells")
    print(f"model-vs-record worst |pm_min diff|: "
          f"{max(abs(w - float(c['pm_min_deg'])) for c, w, _, _ in res):.3f} deg")
    for name, sel in (("DR-006 rule cells", lambda c: int(c["trim_units"]) == RULE[c["f_ref_hz"]]),
                      ("all 140 cells", lambda c: True)):
        sub = [x for x in res if sel(x[0])]
        print(f"{name} ({len(sub)}): max PM loss {max(x[2] for x in sub):.3f} deg, "
              f"max |df_c/f_c| {max(x[3] for x in sub):.2%}")
    nar = min((x for x in res if int(x[0]["trim_units"]) == RULE[x[0]["f_ref_hz"]]),
              key=lambda x: float(x[0]["pm_min_deg"]))
    c = nar[0]
    print(f"narrowest rule cell: f_ref={c['f_ref_hz']} N={c['n_div']} trim={c['trim_units']} "
          f"pm_min={c['pm_min_deg']} at {c['pm_min_at']}: PM loss {nar[2]:.3f} deg, df_c {nar[3]:.2%}")


if __name__ == "__main__":
    main()
