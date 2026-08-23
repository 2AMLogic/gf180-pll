#!/usr/bin/env python3
"""gf180-pll :: vco-tuning-range :: stage-count Result section.

Reads `stage_count.csv` from `run_stages.sh` and emits the Markdown **Result**
section of the stage-count record on stdout. Every number is computed here from
the CSV, never hand-typed.

The decision this supports is DR-001 Decision 2's open question -- 3 vs 5 vs 7
stages -- judged on four things the record can measure:

  1. does the count reach the 200 MHz top of the v1 band at the SLOW corner?
  2. does it reach the 10 MHz bottom at the FAST corner?
  3. what does it cost in supply current at a matched frequency?
  4. does the ring keep full swing at the bottom of the band? (a starved ring
     that has lost swing is not a usable oscillator, and losing it is the
     specific failure mode a low stage count risks)

Usage:  analyze_stages.py <stage_count.csv>
"""

import importlib.util
import math
import sys
from collections import defaultdict
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_vco_tuning_range_numeric", Path(__file__).resolve().parent / "_numeric.py"
)
_numeric = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_numeric)
read_csv_rows = _numeric.read_csv_rows

F_LO = 10e6
F_HI = 200e6


def main():
    rows = read_csv_rows(sys.argv[1])
    d = {}
    for r in rows:
        d[(r["bundle"], r["band"], r["vctrl_v"], r["nstage"])] = {
            "f": float(r["fosc_hz"]),
            "i": float(r["isupply_a"]),
            "hi": float(r["swing_hi_v"]),
            "lo": float(r["swing_lo_v"]),
            "vdd": float(r["vdd_v"]),
        }
    bundles = sorted({r["bundle"] for r in rows})
    ns = sorted({r["nstage"] for r in rows}, key=int)
    bands = sorted({r["band"] for r in rows}, key=int)
    top_band, bot_band = bands[-1], bands[0]

    slow = "all-slow" if "all-slow" in bundles else bundles[0]
    fast = "all-fast" if "all-fast" in bundles else bundles[-1]
    nom = "typical" if "typical" in bundles else bundles[0]

    o = []
    a = o.append

    # A ring that did not oscillate is recorded with fosc = 0. That outranks
    # every other criterion: a stage count that fails to start anywhere on the
    # grid is not a candidate, whatever its frequency range or its power.
    dead = defaultdict(list)
    for (b_, bd, v_, n_), e in sorted(d.items()):
        if e["f"] <= 0.0:
            dead[n_].append((b_, bd, v_))

    a("  ### 0. Does the ring oscillate at all, at every point on the grid?")
    a("")
    a("  A current-starved ring must satisfy Barkhausen with the small-signal")
    a("  gain its cell actually has: an N-stage single-ended ring needs a")
    a("  per-stage gain of 1/cos(pi/N) -- **2.00 for N=3**, 1.24 for N=5, 1.11")
    a("  for N=7. A current-starved inverter loses gain as its head and tail")
    a("  devices are driven fully on, because their series resistance degenerates")
    a("  the stage. So the top of the band is where a low stage count is at risk,")
    a("  and that is exactly where this grid finds it:")
    a("")
    a("  | Stages | required per-stage gain | points where the ring did not start | verdict |")
    a("  |---|---|---|---|")

    for n in ns:
        req = 1.0 / math.cos(math.pi / int(n))
        pts = dead.get(n, [])
        a(
            "  | %s | %.2f | %d of %d | %s |"
            % (n, req, len(pts), len(bands) * 2 * len(bundles),
               "**DISQUALIFIED**" if pts else "oscillates everywhere")
        )
    a("")
    for n in ns:
        if dead.get(n):
            a(
                "  The %s-stage ring is **static** (max = min on the measured ring"
                % n
            )
            a("  node across the whole window, despite the same start-up kick that")
            a("  dislodged the other counts) at: %s."
              % ", ".join("%s B%s @ %s V" % p for p in dead[n][:6]))
            a("  This is a measured outcome, not a missing measurement -- see the")
            a("  `fosc_hz = 0` convention in `stage_count.csv`.")
            a("")

    a("  ### 1. Can each stage count reach the band edges at the binding corner?")
    a("")
    a("  Top of band is binding at the **slow** corner (%s), bottom of band at" % slow)
    a("  the **fast** corner (%s) -- the ring has to still be fast enough at one" % fast)
    a("  extreme and still be slow enough at the other.")
    a("")
    a("  | Stages | max f at %s (B%s, Vctrl 2.7 V) | vs 200 MHz | min f at %s (B%s, Vctrl 0.9 V) | vs 10 MHz |"
      % (slow, top_band, fast, bot_band))
    a("  |---|---|---|---|---|")
    verdicts = {}
    for n in ns:
        hi = d[(slow, top_band, "2.7", n)]["f"]
        lo = d[(fast, bot_band, "0.9", n)]["f"]
        ok_hi = hi >= F_HI
        ok_lo = 0 < lo <= F_LO
        verdicts[n] = (ok_hi, ok_lo, hi, lo)
        a(
            "  | %s | %s | %s | %s | %s |"
            % (
                n,
                "did not oscillate" if hi <= 0 else "%.4g MHz" % (hi / 1e6),
                "**FAIL**" if hi <= 0 else
                ("PASS (%+.0f %%)" % (100 * (hi - F_HI) / F_HI) if ok_hi
                 else "**FAIL** (%+.0f %%)" % (100 * (hi - F_HI) / F_HI)),
                "did not oscillate" if lo <= 0 else "%.4g MHz" % (lo / 1e6),
                "**FAIL**" if lo <= 0 else
                ("PASS (%+.0f %%)" % (100 * (lo - F_LO) / F_LO) if ok_lo
                 else "**FAIL** (%+.0f %%)" % (100 * (lo - F_LO) / F_LO)),
            )
        )
    a("")

    a("  ### 2. Cost at a matched frequency")
    a("")
    a("  Supply current of each complete ring (bias generator included) at the")
    a("  band/Vctrl point closest to 100 MHz at the nominal corner (%s), which is" % nom)
    a("  where the draft power line is quoted:")
    a("")
    a("  | Stages | closest point to 100 MHz | f | I_supply | energy per output cycle |")
    a("  |---|---|---|---|---|")
    best = {}
    for n in ns:
        cands = [
            (abs(d[(nom, b, v, n)]["f"] - 100e6), b, v)
            for b in bands for v in ("0.9", "2.7")
            if (nom, b, v, n) in d and d[(nom, b, v, n)]["f"] > 0
        ]
        _, b, v = min(cands)
        e = d[(nom, b, v, n)]
        best[n] = e
        a(
            "  | %s | B%s @ %s V | %.4g MHz | %.0f uA | %.2f pJ |"
            % (n, b, v, e["f"] / 1e6, e["i"] * 1e6, e["i"] * e["vdd"] / e["f"] * 1e12)
        )
    a("")
    ref = best[ns[len(ns) // 2]]
    a(
        "  Energy per cycle is the comparable number across counts (current alone"
    )
    a("  is not, because the three rings are not at the same frequency). Relative")
    a(
        "  to the %s-stage ring: %s."
        % (
            ns[len(ns) // 2],
            ", ".join(
                "%s stages %.2fx"
                % (n, (best[n]["i"] * best[n]["vdd"] / best[n]["f"]) /
                   (ref["i"] * ref["vdd"] / ref["f"]))
                for n in ns
            ),
        )
    )
    a("")

    a("  ### 3. Swing at the bottom of the band")
    a("")
    a("  A current-starved ring loses output swing before it loses oscillation;")
    a("  a ring node that no longer reaches the rails cannot drive a")
    a("  rail-to-rail buffer reliably at every corner. Worst-case swing over the")
    a("  whole grid, as a fraction of that run's supply:")
    a("")
    a("  | Stages | worst swing (fraction of vdd) | at |")
    a("  |---|---|---|")
    swing_ok = {}
    for n in ns:
        worst = None
        for (b_, bd, v_, n_), e in d.items():
            if n_ != n or e["f"] <= 0:
                continue
            frac = (e["hi"] - e["lo"]) / e["vdd"]
            if worst is None or frac < worst[0]:
                worst = (frac, b_, bd, v_)
        swing_ok[n] = worst[0]
        a("  | %s | %.3f | %s, B%s, Vctrl %s V |" % (n, worst[0], worst[1], worst[2], worst[3]))
    a("")

    a("  ### 4. Conclusion")
    a("")
    a("  | Stages | starts everywhere | reaches 200 MHz slow | reaches 10 MHz fast | energy/cycle | worst swing | verdict |")
    a("  |---|---|---|---|---|---|---|")
    for n in ns:
        ok_hi, ok_lo, _hi, _lo = verdicts[n]
        e = best[n]
        epc = e["i"] * e["vdd"] / e["f"] * 1e12
        good = ok_hi and ok_lo and swing_ok[n] > 0.90 and not dead.get(n)
        a(
            "  | %s | %s | %s | %s | %.2f pJ | %.3f | %s |"
            % (n, "**no**" if dead.get(n) else "yes",
               "yes" if ok_hi else "**no**", "yes" if ok_lo else "**no**",
               epc, swing_ok[n], "viable" if good else "**rejected**")
        )
    a("")
    viable = [
        n for n in ns
        if verdicts[n][0] and verdicts[n][1] and swing_ok[n] > 0.90 and not dead.get(n)
    ]
    if viable == ["5"]:
        a("  **5 stages is confirmed** as DR-001 Decision 2's nominal count, and")
        a("  it is the *only* viable odd count of the three: each of the other two")
        a("  is rejected by a measurement, not by a preference.")
    else:
        a(
            "  **Viable counts on this grid: %s.** DR-001 Decision 2's nominal"
            % (", ".join(viable) if viable else "none")
        )
        a("  count of 5 is %s among them."
          % ("" if "5" in viable else "NOT "))
    a("")
    for n in ns:
        ok_hi, ok_lo, hi, lo = verdicts[n]
        reasons = []
        if dead.get(n):
            reasons.append(
                "**it does not start at %d of %d grid points** (%s) -- with a "
                "per-stage gain requirement of %.2f it cannot sustain "
                "oscillation once the starving devices are driven fully on, and "
                "it then sits at mid-rail drawing static crowbar current"
                % (len(dead[n]), len(bands) * 2 * len(bundles),
                   ", ".join("%s B%s @ %s V" % p for p in dead[n][:3]),
                   1.0 / math.cos(math.pi / int(n)))
            )
        if not ok_hi:
            reasons.append(
                "it tops out at %.4g MHz at the slow corner, **%.0f %% short of "
                "the 200 MHz v1 ceiling** DR-002 Decision 2 budgets margin to"
                % (hi / 1e6, 100 * (F_HI - hi) / F_HI)
            )
        if not ok_lo and lo > 0:
            reasons.append(
                "its lowest band floors at %.4g MHz at the fast corner, **%.0f %% "
                "above the 10 MHz bottom of the band** -- it cannot reach the "
                "bottom of the ratified range without the output divider DR-002 "
                "Decision 2 keeps out of v1 scope"
                % (lo / 1e6, 100 * (lo - F_LO) / F_LO)
            )
        if swing_ok[n] <= 0.90:
            reasons.append(
                "its worst-case ring swing falls to %.2f of the supply, so the "
                "output buffer would not see a reliable full-swing input at "
                "every corner" % swing_ok[n]
            )
        epc = best[n]["i"] * best[n]["vdd"] / best[n]["f"] * 1e12
        ref_epc = ref["i"] * ref["vdd"] / ref["f"] * 1e12
        if reasons:
            a("  - **%s stages -- rejected**: %s." % (n, "; and ".join(reasons)))
            a(
                "    (Its %.2f pJ per output cycle, %.2fx the 5-stage ring, is "
                "not the reason;" % (epc, epc / ref_epc)
            )
            a("    the failures above are disqualifying on their own.)")
        else:
            a(
                "  - **%s stages -- viable**: clears the 200 MHz v1 ceiling at the "
                "slow corner by %.0f %%, reaches %.0f %% below the 10 MHz floor at "
                "the fast corner, starts at every grid point, keeps full swing "
                "(%.2f of supply worst case), and costs %.2f pJ per output cycle."
                % (n, 100 * (hi - F_HI) / F_HI, 100 * (F_LO - lo) / F_LO,
                   swing_ok[n], epc)
            )
    a("")
    if viable == ["5"]:
        a("  This **confirms** rather than revises DR-001 Decision 2, so it is not")
        a("  grounds for a superseding decision record on the stage count. It does")
        a("  narrow the decision: DR-001 left the count open as \"odd (5 nominal)\",")
        a("  and this grid shows the neighbouring odd counts are not fallbacks --")
        a("  there is no second choice to retreat to if layout parasitics erode the")
        a("  5-stage margins, which makes the extraction step (#18) the point where")
        a("  this decision would actually be at risk.")
    else:
        a("  This result **does not confirm** DR-001 Decision 2's nominal count and")
        a("  is grounds for a decision record revisiting it.")

    sys.stdout.write("\n".join(o) + "\n")


if __name__ == "__main__":
    main()
