"""gf180-pll :: vco-tuning-range :: stage-count campaign reduction.

The `sim/harness` `derived` extension point carrying the reduction the
pre-migration `analyze_stages.py` computed, with the same arithmetic and the
same formatting, so the migrated record is comparable line by line with the
record it supersedes (`20260731-180254-0a12e6c`).

The decision this supports is DR-001 Decision 2's open question -- 3 vs 5 vs 7
stages -- judged on four things the grid can measure:

  0. does the ring start at all, at every point on the grid?
  1. does the count reach the 200 MHz top of band at the SLOW corner, and the
     10 MHz bottom at the FAST corner?
  2. what does it cost in energy per output cycle at a matched frequency?
  3. does the ring keep full swing at the bottom of the band?

A ring that did not oscillate is recorded by the pre-migration CSV as
`fosc_hz = 0`; here it is an absent (`optional`) `.measure`, which the harness
records as *not measured* -- the same fact, carried without a magic zero.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.derived import DerivedTable  # noqa: E402

F_LO = 10e6
F_HI = 200e6
STAGES = (3, 5, 7)
#: Worst-case ring swing, as a fraction of that run's supply, below which a
#: count is rejected: a ring node that no longer reaches the rails cannot drive
#: a rail-to-rail buffer reliably at every corner.
SWING_FLOOR = 0.90


# ---------------------------------------------------------------- per point
def derive_point(point):
    """Energy per output cycle and fractional ring swing, per stage count."""
    out = {}
    for n in STAGES:
        f = point.get("f%d" % n)
        cur = point.get("i%d" % n)
        hi = point.get("s%dhi" % n)
        lo = point.get("s%dlo" % n)
        if f and f > 0 and cur is not None:
            # I * Vdd / f -- the comparable number across counts, because the
            # three rings are not at the same frequency.
            out["e%d" % n] = abs(cur) * point.vdd / f * 1e12  # pJ
        if hi is not None and lo is not None:
            out["swing%d" % n] = (hi - lo) / point.vdd
    return out


# ------------------------------------------------------------- the reduction
def _index(run):
    """``(corner, band, vctrl) -> point``, plus the axis values present."""
    by_key = {}
    for p in run.points:
        band = int(p.params["band"])
        vctrl = float(p.params["vctrl"])
        by_key[(p.corner, band, vctrl)] = p
    corners = sorted({k[0] for k in by_key})
    bands = sorted({k[1] for k in by_key})
    vctrls = sorted({k[2] for k in by_key})
    return by_key, corners, bands, vctrls


def _pick(corners, name, fallback_index):
    return name if name in corners else corners[fallback_index]


def derive_tables(run):
    by_key, corners, bands, vctrls = _index(run)
    slow = _pick(corners, "all-slow", 0)
    fast = _pick(corners, "all-fast", -1)
    nom = _pick(corners, "typical", 0)
    top_band, bot_band = bands[-1], bands[0]
    v_lo, v_hi = vctrls[0], vctrls[-1]
    npoints = len(by_key)

    # --- 0. start-up -------------------------------------------------------
    dead = {n: [] for n in STAGES}
    for (c, b, v), p in sorted(by_key.items()):
        for n in STAGES:
            f = p.get("f%d" % n)
            if not f or f <= 0:
                dead[n].append((c, b, v))

    startup_rows = []
    for n in STAGES:
        req = 1.0 / math.cos(math.pi / n)
        startup_rows.append(
            (str(n), "%.2f" % req, "%d of %d" % (len(dead[n]), npoints),
             "**DISQUALIFIED**" if dead[n] else "oscillates everywhere")
        )
    startup_notes = [
        "A current-starved ring must satisfy Barkhausen with the small-signal",
        "gain its cell actually has: an N-stage single-ended ring needs a",
        "per-stage gain of 1/cos(pi/N) -- **2.00 for N=3**, 1.24 for N=5, 1.11",
        "for N=7. A current-starved inverter loses gain as its head and tail",
        "devices are driven fully on, because their series resistance degenerates",
        "the stage. So the top of the band is where a low stage count is at risk,",
        "and that is exactly where this grid finds it.",
    ]
    for n in STAGES:
        if dead[n]:
            startup_notes += [
                "",
                "The %d-stage ring is **static** (no half-supply crossing to measure," % n,
                "despite the same start-up kick that dislodged the other counts) at:",
                "%s." % ", ".join("%s B%d @ %s V" % (c, b, ("%g" % v)) for c, b, v in dead[n][:6]),
                "This is a measured outcome, not a missing measurement -- those",
                "`.measure` statements are declared `optional` for exactly this reason,",
                "and the point's other measurements are kept.",
            ]
    startup = DerivedTable(
        name="startup",
        description="0. does the ring oscillate at all, at every point on the grid?",
        columns=("stages", "required per-stage gain",
                 "points where the ring did not start", "verdict"),
        rows=tuple(startup_rows),
        notes=tuple(startup_notes),
    )

    # --- 1. band edges -----------------------------------------------------
    verdicts = {}
    edge_rows = []
    for n in STAGES:
        hi_p = by_key.get((slow, top_band, v_hi))
        lo_p = by_key.get((fast, bot_band, v_lo))
        hi = (hi_p.get("f%d" % n) if hi_p else None) or 0.0
        lo = (lo_p.get("f%d" % n) if lo_p else None) or 0.0
        ok_hi = hi >= F_HI
        ok_lo = 0 < lo <= F_LO
        verdicts[n] = (ok_hi, ok_lo, hi, lo)
        edge_rows.append(
            (str(n),
             "did not oscillate" if hi <= 0 else "%.4g MHz" % (hi / 1e6),
             "**FAIL**" if hi <= 0 else
             ("PASS (%+.0f %%)" % (100 * (hi - F_HI) / F_HI) if ok_hi
              else "**FAIL** (%+.0f %%)" % (100 * (hi - F_HI) / F_HI)),
             "did not oscillate" if lo <= 0 else "%.4g MHz" % (lo / 1e6),
             "**FAIL**" if lo <= 0 else
             ("PASS (%+.0f %%)" % (100 * (lo - F_LO) / F_LO) if ok_lo
              else "**FAIL** (%+.0f %%)" % (100 * (lo - F_LO) / F_LO)))
        )
    band_edges = DerivedTable(
        name="band_edges",
        description="1. can each stage count reach the band edges at the binding corner?",
        columns=("stages",
                 "max f at %s (B%d, Vctrl %g V)" % (slow, top_band, v_hi),
                 "vs 200 MHz",
                 "min f at %s (B%d, Vctrl %g V)" % (fast, bot_band, v_lo),
                 "vs 10 MHz"),
        rows=tuple(edge_rows),
        notes=(
            "Top of band is binding at the **slow** corner (%s), bottom of band at" % slow,
            "the **fast** corner (%s) -- the ring has to still be fast enough at one" % fast,
            "extreme and still be slow enough at the other.",
        ),
    )

    # --- 2. energy at a matched frequency ----------------------------------
    best = {}
    energy_rows = []
    for n in STAGES:
        cands = []
        for (c, b, v), p in by_key.items():
            if c != nom:
                continue
            f = p.get("f%d" % n)
            if f and f > 0:
                cands.append((abs(f - 100e6), b, v))
        if not cands:
            continue
        _, b, v = min(cands)
        p = by_key[(nom, b, v)]
        f = p.get("f%d" % n)
        cur = abs(p.get("i%d" % n))
        epc = cur * p.vdd / f * 1e12
        best[n] = {"f": f, "i": cur, "vdd": p.vdd, "epc": epc}
        energy_rows.append(
            (str(n), "B%d @ %g V" % (b, v), "%.4g MHz" % (f / 1e6),
             "%.0f uA" % (cur * 1e6), "%.2f pJ" % epc)
        )
    ref = best[5] if 5 in best else best[STAGES[len(STAGES) // 2]]
    energy = DerivedTable(
        name="energy_at_100mhz",
        description="2. cost at a matched frequency -- supply current of each complete "
                    "ring (bias generator included) at the band/Vctrl point closest to "
                    "100 MHz at the nominal corner (%s), which is where the draft power "
                    "line is quoted" % nom,
        columns=("stages", "closest point to 100 MHz", "f", "I_supply",
                 "energy per output cycle"),
        rows=tuple(energy_rows),
        notes=(
            "Energy per cycle is the comparable number across counts (current alone",
            "is not, because the three rings are not at the same frequency). Relative",
            "to the 5-stage ring: %s."
            % ", ".join("%d stages %.2fx" % (n, best[n]["epc"] / ref["epc"])
                        for n in STAGES if n in best),
        ),
    )

    # --- 3. worst-case swing ----------------------------------------------
    swing_ok = {}
    swing_rows = []
    for n in STAGES:
        worst = None
        for (c, b, v), p in by_key.items():
            f = p.get("f%d" % n)
            frac = p.get("swing%d" % n)
            if not f or f <= 0 or frac is None:
                continue
            if worst is None or frac < worst[0]:
                worst = (frac, c, b, v)
        if worst is None:
            swing_ok[n] = 0.0
            swing_rows.append((str(n), "n/a (never oscillated)", "n/a"))
            continue
        swing_ok[n] = worst[0]
        swing_rows.append(
            (str(n), "%.3f" % worst[0], "%s, B%d, Vctrl %g V" % (worst[1], worst[2], worst[3]))
        )
    swing = DerivedTable(
        name="worst_swing",
        description="3. swing at the bottom of the band -- worst-case ring swing over "
                    "the whole grid, as a fraction of that run's supply",
        columns=("stages", "worst swing (fraction of vdd)", "at"),
        rows=tuple(swing_rows),
        notes=(
            "A current-starved ring loses output swing before it loses oscillation;",
            "a ring node that no longer reaches the rails cannot drive a",
            "rail-to-rail buffer reliably at every corner.",
        ),
    )

    # --- 4. conclusion -----------------------------------------------------
    concl_rows = []
    for n in STAGES:
        ok_hi, ok_lo, _hi, _lo = verdicts[n]
        epc = best[n]["epc"] if n in best else float("nan")
        good = ok_hi and ok_lo and swing_ok[n] > SWING_FLOOR and not dead[n]
        concl_rows.append(
            (str(n), "**no**" if dead[n] else "yes",
             "yes" if ok_hi else "**no**", "yes" if ok_lo else "**no**",
             "%.2f pJ" % epc, "%.3f" % swing_ok[n],
             "viable" if good else "**rejected**")
        )
    viable = [n for n in STAGES
              if verdicts[n][0] and verdicts[n][1] and swing_ok[n] > SWING_FLOOR and not dead[n]]
    verdict = DerivedTable(
        name="stage_count_verdict",
        description="4. conclusion -- DR-001 Decision 2's open stage-count question",
        columns=("stages", "starts everywhere", "reaches 200 MHz slow",
                 "reaches 10 MHz fast", "energy/cycle", "worst swing", "verdict"),
        rows=tuple(concl_rows),
        notes=_verdict_notes(viable, verdicts, dead, swing_ok, best, ref, npoints),
    )

    return [startup, band_edges, energy, swing, verdict]


def _verdict_notes(viable, verdicts, dead, swing_ok, best, ref, npoints):
    notes = []
    if viable == [5]:
        notes += [
            "**5 stages is confirmed** as DR-001 Decision 2's nominal count, and",
            "it is the *only* viable odd count of the three: each of the other two",
            "is rejected by a measurement, not by a preference.",
        ]
    else:
        notes += [
            "**Viable counts on this grid: %s.** DR-001 Decision 2's nominal"
            % (", ".join(str(n) for n in viable) if viable else "none"),
            "count of 5 is %samong them." % ("" if 5 in viable else "NOT "),
        ]
    notes.append("")
    for n in STAGES:
        ok_hi, ok_lo, hi, lo = verdicts[n]
        reasons = []
        if dead[n]:
            reasons.append(
                "**it does not start at %d of %d grid points** (%s) -- with a "
                "per-stage gain requirement of %.2f it cannot sustain oscillation "
                "once the starving devices are driven fully on, and it then sits "
                "at mid-rail drawing static crowbar current"
                % (len(dead[n]), npoints,
                   ", ".join("%s B%d @ %g V" % (c, b, v) for c, b, v in dead[n][:3]),
                   1.0 / math.cos(math.pi / n))
            )
        if not ok_hi:
            reasons.append(
                "it tops out at %.4g MHz at the slow corner, **%.0f %% short of the "
                "200 MHz v1 ceiling** DR-002 Decision 2 budgets margin to"
                % (hi / 1e6, 100 * (F_HI - hi) / F_HI)
            )
        if not ok_lo and lo > 0:
            reasons.append(
                "its lowest band floors at %.4g MHz at the fast corner, **%.0f %% "
                "above the 10 MHz bottom of the band** -- it cannot reach the bottom "
                "of the ratified range without the output divider DR-002 Decision 2 "
                "keeps out of v1 scope" % (lo / 1e6, 100 * (lo - F_LO) / F_LO)
            )
        if swing_ok[n] <= SWING_FLOOR:
            reasons.append(
                "its worst-case ring swing falls to %.2f of the supply, so the output "
                "buffer would not see a reliable full-swing input at every corner"
                % swing_ok[n]
            )
        epc = best[n]["epc"] if n in best else float("nan")
        if reasons:
            notes += [
                "  - **%d stages -- rejected**: %s." % (n, "; and ".join(reasons)),
                "    (Its %.2f pJ per output cycle, %.2fx the 5-stage ring, is not the "
                "reason;" % (epc, epc / ref["epc"]),
                "    the failures above are disqualifying on their own.)",
            ]
        else:
            notes.append(
                "  - **%d stages -- viable**: clears the 200 MHz v1 ceiling at the slow "
                "corner by %.0f %%, reaches %.0f %% below the 10 MHz floor at the fast "
                "corner, starts at every grid point, keeps full swing (%.2f of supply "
                "worst case), and costs %.2f pJ per output cycle."
                % (n, 100 * (hi - F_HI) / F_HI, 100 * (F_LO - lo) / F_LO,
                   swing_ok[n], epc)
            )
    notes.append("")
    if viable == [5]:
        notes += [
            "This **confirms** rather than revises DR-001 Decision 2, so it is not",
            "grounds for a superseding decision record on the stage count. It does",
            "narrow the decision: DR-001 left the count open as \"odd (5 nominal)\",",
            "and this grid shows the neighbouring odd counts are not fallbacks --",
            "there is no second choice to retreat to if layout parasitics erode the",
            "5-stage margins, which makes the extraction step (#18) the point where",
            "this decision would actually be at risk.",
        ]
    else:
        notes += [
            "This result **does not confirm** DR-001 Decision 2's nominal count and",
            "is grounds for a decision record revisiting it.",
        ]
    return tuple(notes)
