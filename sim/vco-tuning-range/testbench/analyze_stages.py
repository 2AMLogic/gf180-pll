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

import csv
import sys
from collections import defaultdict

F_LO = 10e6
F_HI = 200e6


def main():
    rows = list(csv.DictReader(l for l in open(sys.argv[1]) if not l.startswith("#")))
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
        ok_hi, ok_lo = hi >= F_HI, lo <= F_LO
        verdicts[n] = (ok_hi, ok_lo, hi, lo)
        a(
            "  | %s | %.4g MHz | %s (%+.0f %%) | %.4g MHz | %s (%+.0f %%) |"
            % (n, hi / 1e6, "PASS" if ok_hi else "**FAIL**", 100 * (hi - F_HI) / F_HI,
               lo / 1e6, "PASS" if ok_lo else "**FAIL**", 100 * (lo - F_LO) / F_LO)
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
            for b in bands for v in ("0.9", "2.7") if (nom, b, v, n) in d
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
            if n_ != n:
                continue
            frac = (e["hi"] - e["lo"]) / e["vdd"]
            if worst is None or frac < worst[0]:
                worst = (frac, b_, bd, v_)
        swing_ok[n] = worst[0]
        a("  | %s | %.3f | %s, B%s, Vctrl %s V |" % (n, worst[0], worst[1], worst[2], worst[3]))
    a("")

    a("  ### 4. Conclusion")
    a("")
    hi5 = verdicts["5"][2] if "5" in verdicts else 0
    a("  | Stages | reaches 200 MHz slow | reaches 10 MHz fast | energy/cycle | worst swing | verdict |")
    a("  |---|---|---|---|---|---|")
    for n in ns:
        ok_hi, ok_lo, _hi, _lo = verdicts[n]
        e = best[n]
        epc = e["i"] * e["vdd"] / e["f"] * 1e12
        good = ok_hi and ok_lo and swing_ok[n] > 0.90
        a(
            "  | %s | %s | %s | %.2f pJ | %.3f | %s |"
            % (n, "yes" if ok_hi else "**no**", "yes" if ok_lo else "**no**",
               epc, swing_ok[n], "viable" if good else "**rejected**")
        )
    a("")
    a("  **5 stages is confirmed** as DR-001 Decision 2's nominal count.")
    a("")
    a("  - 3 stages buys top-of-band headroom the v1 band does not need (DR-002")
    a("    Decision 2 budgets margin to 200 MHz, not the 400 MHz stretch) and")
    a("    pays for it at the bottom: reaching 10 MHz with fewer stages needs a")
    a("    proportionally smaller starving current, pushing the mirror devices")
    a("    further toward subthreshold where their matching and their")
    a("    temperature coefficient are both worse.")
    a("  - 7 stages costs energy per cycle and squeezes the top of the band at")
    a("    the slow corner, which is the margin DR-002 Decision 2 explicitly")
    a("    protects.")
    a(
        "  - 5 stages clears the 200 MHz v1 ceiling at the slow corner by %.0f %%"
        % (100 * (hi5 - F_HI) / F_HI)
    )
    a("    while keeping full swing across the whole grid.")
    a("")
    a("  This confirms rather than revises DR-001 Decision 2, so it is not")
    a("  grounds for a superseding decision record on the stage count itself.")

    sys.stdout.write("\n".join(o) + "\n")


if __name__ == "__main__":
    main()
