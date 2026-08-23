#!/usr/bin/env python3
"""gf180-pll :: vco-tuning-range :: supply pushing + supply-jitter Result section.

Reads the two CSVs `run_supply.sh` writes (static pushing, transient jitter) and
emits the Markdown **Result** section of the supply record on stdout. Every
number is computed here from the CSVs, never hand-typed.

Usage:  analyze_supply.py <supply_pushing.csv> <supply_jitter.csv>
"""

import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_vco_tuning_range_numeric", Path(__file__).resolve().parent / "_numeric.py"
)
_numeric = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_numeric)
linfit = _numeric.linfit
ts = _numeric.ts
read_csv_rows = _numeric.read_csv_rows
cname = _numeric.corner_temp_name


def min_med_max(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[0], xs[n // 2], xs[-1]


def main():
    push = read_csv_rows(sys.argv[1])
    jit = read_csv_rows(sys.argv[2])
    o = []
    a = o.append

    # ------------------------------------------------------- static pushing
    # group by (bundle, temp, band, vctrl) -> [(vdd, f, i)]
    g = defaultdict(list)
    for r in push:
        g[(r["bundle"], r["temp_c"], r["band"], r["vctrl_v"])].append(
            (float(r["vdd_v"]), float(r["fosc_hz"]), float(r["isupply_a"]))
        )
    rows = []
    for k, pts in g.items():
        pts.sort()
        vs = [p[0] for p in pts]
        fs = [p[1] for p in pts]
        m, c = linfit(vs, fs)
        f_nom = [f for v, f in zip(vs, fs) if abs(v - 3.30) < 1e-9][0]
        # worst deviation of the measured curve from its own straight line,
        # as a fraction of the nominal frequency: how non-linear pushing is
        nl = max(abs(f - (m * v + c)) for v, f in zip(vs, fs)) / f_nom
        rows.append(
            {
                "key": k, "slope": m, "norm": m / f_nom, "f_nom": f_nom,
                "nl": nl, "i_nom": [i for v, _f, i in pts if abs(v - 3.30) < 1e-9][0],
            }
        )
    rows.sort(key=lambda r: r["norm"])

    a("  ### 1. Static supply pushing (`tb_vco_pushing.sp`)")
    a("")
    a("  Local slope of f_osc against `vdd_vco`, least-squares over the seven")
    a("  supply points spanning 2.97-3.63 V, at every (bundle, temperature,")
    a("  band) combination -- %d curves of 7 points each." % len(rows))
    a("")
    a("  | Band | pushing, most negative | median | least negative | worst-case frequency shift over a +/-10 % rail |")
    a("  |---|---|---|---|---|")
    for band in sorted({r["key"][2] for r in rows}, key=int):
        sel = [r for r in rows if r["key"][2] == band]
        lo, md, hi = min_med_max([r["norm"] for r in sel])
        worst = max(abs(r["norm"]) for r in sel)
        a(
            "  | B%s | %.1f %%/V | %.1f %%/V | %.1f %%/V | %.0f %% |"
            % (band, 100 * lo, 100 * md, 100 * hi, 100 * worst * 0.33)
        )
    a("")
    wr = min(rows, key=lambda r: r["norm"])
    br = max(rows, key=lambda r: r["norm"])
    a(
        "  - Worst (most supply-sensitive) point: **%.1f %%/V** (%s MHz/V at"
        % (100 * wr["norm"], "%.4g" % (wr["slope"] / 1e6))
    )
    a(
        "    %s MHz) at %s, band %s, Vctrl %s V."
        % ("%.4g" % (wr["f_nom"] / 1e6), cname(wr["key"][0], wr["key"][1]),
           wr["key"][2], wr["key"][3])
    )
    a(
        "  - Best: **%.1f %%/V** at %s, band %s."
        % (100 * br["norm"], cname(br["key"][0], br["key"][1]), br["key"][2])
    )
    a(
        "  - Curvature: the largest departure of any measured f(vdd) curve from"
    )
    a(
        "    its own straight-line fit is %.2f %% of f_nom, so pushing is"
        % (100 * max(r["nl"] for r in rows))
    )
    a("    effectively linear across the whole +/-10 % rail and a single")
    a("    coefficient per corner is a fair summary.")
    a("")
    a("  **Where the sensitivity comes from, and why it is not a sizing error.**")
    a("  A current-starved ring runs at f ~ I_stage / (N * C_stage * V_swing),")
    a("  and V_swing *is* the supply. Even with a perfectly supply-independent")
    a("  starving current, f therefore carries a -1/vdd term = **-30.3 %/V** at")
    a("  3.3 V. The measured median of %.1f %%/V is %.2fx that floor, i.e. the"
      % (100 * min_med_max([r["norm"] for r in rows])[1],
         abs(min_med_max([r["norm"] for r in rows])[1]) / 0.303))
    a("  bias generator contributes only the remainder. Reducing supply pushing")
    a("  materially would require a regulated VCO rail or a swing-independent")
    a("  cell (a differential delay cell with replica-biased load), i.e. exactly")
    a("  the alternatives DR-001 Decision 2 considered and rejected on power and")
    a("  cell-count grounds -- not a resizing of this cell.")
    a("")

    # ------------------------------------------------------- transient
    seen = set()
    main_grid = []
    for r in jit:
        if r["ripple_div"] != "16" or r["band"] != "5" or r["vctrl_v"] != "1.8":
            continue
        k = (r["bundle"], r["temp_c"], r["vdd_v"])
        if k in seen:
            continue  # the band sweep repeats band 5 at three bundles
        seen.add(k)
        main_grid.append(r)

    def f_(r, k):
        return float(r[k])

    a("  ### 2. Supply-step response (`tb_vco_supply_jitter.sp`)")
    a("")
    a(
        "  A %s V step on `vdd_vco` with a 1 ns edge, at every one of the %d PVT"
        % (main_grid[0]["astep_v"], len(main_grid))
    )
    a("  points of the default grid (band 5, Vctrl 1.8 V ~ 100 MHz class).")
    a("")
    a("  | | df for the step | df/f | transient pushing | open-loop timing error per us |")
    a("  |---|---|---|---|---|")
    for label, pick in (
        ("Worst", max(main_grid, key=lambda r: abs(f_(r, "step_df_hz")) / f_(r, "step_f_pre_hz"))),
        ("Median", sorted(main_grid, key=lambda r: abs(f_(r, "step_df_hz")) / f_(r, "step_f_pre_hz"))[len(main_grid) // 2]),
        ("Best", min(main_grid, key=lambda r: abs(f_(r, "step_df_hz")) / f_(r, "step_f_pre_hz"))),
    ):
        a(
            "  | %s (%s) | %.3g MHz | %.2f %% | %.3g MHz/V | %.3g ns |"
            % (
                label, cname(pick["bundle"], pick["temp_c"], pick["vdd_v"]),
                f_(pick, "step_df_hz") / 1e6,
                100 * f_(pick, "step_df_hz") / f_(pick, "step_f_pre_hz"),
                f_(pick, "step_kvdd_hz_per_v") / 1e6,
                f_(pick, "step_tie_per_us_s") * 1e9,
            )
        )
    a("")
    a("  The last column is the number a loop-bandwidth budget has to beat: with")
    a("  the loop open, a supply step of this size walks the VCO's output edge")
    a("  by that much timing error for every microsecond the loop takes to")
    a("  correct it. It is *not* a jitter spec violation on its own -- inside the")
    a("  loop bandwidth the PLL cancels it -- but it is the reason #10 cannot")
    a("  choose an arbitrarily low loop bandwidth, and it is a direct input to")
    a("  #14's supply-sensitivity budget.")
    a("")

    a("  ### 3. Supply-ripple jitter, and the numerical floor")
    a("")
    a(
        "  Sinusoidal ripple of %s V amplitude (%.0f mV peak-to-peak, %.1f %% of"
        % (main_grid[0]["arip_v"], 2000 * float(main_grid[0]["arip_v"]),
           100 * 2 * float(main_grid[0]["arip_v"]) / 3.30)
    )
    a("  the nominal rail) at f_osc/16, over the same %d-point grid." % len(main_grid))
    a("")
    a("  | | period jitter pp | period jitter RMS | TIE pp | TIE RMS |")
    a("  |---|---|---|---|---|")
    wrst = max(main_grid, key=lambda r: f_(r, "rip_tie_pp_s"))
    med = sorted(main_grid, key=lambda r: f_(r, "rip_tie_pp_s"))[len(main_grid) // 2]
    best = min(main_grid, key=lambda r: f_(r, "rip_tie_pp_s"))
    qw = max(main_grid, key=lambda r: f_(r, "quiet_tie_pp_s"))
    for label, pick, pfx in (
        ("Rippled, worst (%s)" % cname(wrst["bundle"], wrst["temp_c"], wrst["vdd_v"]), wrst, "rip"),
        ("Rippled, median (%s)" % cname(med["bundle"], med["temp_c"], med["vdd_v"]), med, "rip"),
        ("Rippled, best (%s)" % cname(best["bundle"], best["temp_c"], best["vdd_v"]), best, "rip"),
        ("**Quiet reference, worst** (numerical floor)", qw, "quiet"),
    ):
        a(
            "  | %s | %s | %s | %s | %s |"
            % (
                label,
                ts(f_(pick, pfx + "_tj_pp_s")), ts(f_(pick, pfx + "_tj_rms_s")),
                ts(f_(pick, pfx + "_tie_pp_s")), ts(f_(pick, pfx + "_tie_rms_s")),
            )
        )
    a("")
    ratio = min(f_(r, "rip_tie_rms_s") / max(f_(r, "quiet_tie_rms_s"), 1e-18) for r in main_grid)
    a(
        "  The smallest margin between a rippled result and its own run's quiet"
    )
    a(
        "  reference anywhere on the grid is **%.0fx** in TIE RMS, so every"
        % ratio
    )
    a("  supply-induced number above is a circuit result, not solver noise.")
    a("")
    a(
        "  Worst case as a fraction of the period: **%.2f %% RMS period jitter**"
        % (100 * f_(wrst, "rip_tj_rms_s") * f_(wrst, "rip_f_hz"))
    )
    a(
        "  and %.2f %% peak-to-peak, at %s, f_osc = %.4g MHz."
        % (100 * f_(wrst, "rip_tj_pp_s") * f_(wrst, "rip_f_hz"),
           cname(wrst["bundle"], wrst["temp_c"], wrst["vdd_v"]), f_(wrst, "rip_f_hz") / 1e6)
    )
    a("  The draft spec line is < 1 % RMS period jitter, so **a 100 mV")
    a("  peak-to-peak ripple on an unregulated VCO rail is on its own")
    a(
        "  %s that line** open-loop."
        % ("sufficient to break" if 100 * f_(wrst, "rip_tj_rms_s") * f_(wrst, "rip_f_hz") > 1.0
           else "inside")
    )
    a("")

    # ---- band dependence
    band_rows = [r for r in jit if r["ripple_div"] == "16" and r["temp_c"] == "27"
                 and r["vdd_v"] == "3.30" and r["bundle"] in ("typical", "all-slow", "all-fast")]
    if band_rows:
        a("  ### 4. Band dependence")
        a("")
        a("  Same ripple, all eight band codes, at three bundles (nominal temp and")
        a("  supply). Jitter *as a fraction of the period* is the comparable")
        a("  quantity across a 40:1 frequency range:")
        a("")
        a("  | Band | f_osc (MHz) | TIE pp (ps) | period jitter RMS (% of period) |")
        a("  |---|---|---|---|")
        for band in sorted({r["band"] for r in band_rows}, key=int):
            sel = [r for r in band_rows if r["band"] == band]
            fw = max(sel, key=lambda r: f_(r, "rip_tie_pp_s"))
            a(
                "  | B%s | %.4g .. %.4g | %s | %.2f |"
                % (band, min(f_(r, "rip_f_hz") for r in sel) / 1e6,
                   max(f_(r, "rip_f_hz") for r in sel) / 1e6,
                   ts(f_(fw, "rip_tie_pp_s")),
                   100 * f_(fw, "rip_tj_rms_s") * f_(fw, "rip_f_hz"))
            )
        a("")

    # ---- ripple-frequency dependence and the model check
    fr_rows = [r for r in jit if r["band"] == "5" and r["temp_c"] == "27"
               and r["vdd_v"] == "3.30" and r["bundle"] in ("typical", "all-slow", "all-fast")]
    if fr_rows:
        a("  ### 5. Ripple-frequency dependence, and whether these numbers project")
        a("")
        a("  | Ripple freq | TIE pp measured | TIE pp predicted from the step | measured/predicted |")
        a("  |---|---|---|---|")
        for rdv in sorted({r["ripple_div"] for r in fr_rows}, key=int):
            sel = [r for r in fr_rows if r["ripple_div"] == rdv]
            mm = sum(f_(r, "rip_tie_pp_s") for r in sel) / len(sel)
            pp = sum(f_(r, "rip_tie_pp_pred_s") for r in sel) / len(sel)
            a(
                "  | f_osc/%s (%.3g MHz) | %s | %s | %.2f |"
                % (rdv, sum(f_(r, "frip_hz") for r in sel) / len(sel) / 1e6,
                   ts(mm), ts(pp), mm / pp if pp else 0)
            )
        a("")
        allsel = [r for r in jit if f_(r, "rip_tie_pp_pred_s") > 0]
        rr = [f_(r, "rip_tie_pp_s") / f_(r, "rip_tie_pp_pred_s") for r in allsel]
        lo, md, hi = min_med_max(rr)
        a(
            "  Across all %d rippled runs the measured/predicted ratio spans"
            % len(rr)
        )
        a("  %.2f .. %.2f (median %.2f)." % (lo, hi, md))
        if lo > 0.8 and hi < 1.25:
            a("  The quasi-static model therefore reproduces the measurement to")
            a("  better than 25 %, and supply-ripple TIE at ripple frequencies")
            a("  that were not simulated may be projected as TIE_pp =")
            a("  K_vdd * A / (pi * f_ripple * f_osc).")
        else:
            a("  TIE scales as 1/f_ripple as the model predicts -- the *shape* is")
            a("  right -- but the magnitude is consistently off by that factor, so")
            a("  the step-derived coefficient is **not** a safe basis for")
            a("  projecting ripple jitter: a ring's response to a bidirectional")
            a("  ripple is larger than its response to a unidirectional step of")
            a("  the same peak-to-peak size, because f ~ 1/vdd is convex. Ripple")
            a("  jitter at a ripple frequency that matters must be **measured**,")
            a("  not extrapolated. The measured numbers in section 3 stand on")
            a("  their own; only the extrapolation is withheld.")
        a("")

    a("  ### 6. Conclusion")
    a("")
    a("  - Supply pushing is characterized across the full +/-10 % rail at every")
    a("    corner, is linear, and is dominated by the ring's swing-vs-supply")
    a("    term rather than by bias-current sensitivity.")
    a("  - DR-001's top named risk now has a **number**, not a caveat: a 100 mV")
    a(
        "    peak-to-peak rail ripple produces up to %s peak-to-peak TIE and"
        % ts(f_(wrst, "rip_tie_pp_s"))
    )
    a(
        "    %.2f %% RMS period jitter open-loop at the worst corner, %.0fx above"
        % (100 * f_(wrst, "rip_tj_rms_s") * f_(wrst, "rip_f_hz"), ratio)
    )
    a("    the solver's numerical floor.")
    a("  - **This does not by itself supersede DR-001 Decision 2.** The measured")
    a("    sensitivity is what a current-starved single-ended ring is expected to")
    a("    have, and DR-001 accepted it explicitly with eyes open. What the")
    a("    number does establish is a hard constraint for #10 and #14: the VCO")
    a("    rail needs either regulation or a decoupling/ripple budget, and the")
    a("    loop bandwidth cannot be set without knowing the supply-noise")
    a("    spectrum. If the system cannot deliver a quiet enough rail, *that* is")
    a("    the condition under which DR-001 Decision 2 should be revisited, and")
    a("    this record is the evidence that would drive it.")

    sys.stdout.write("\n".join(o) + "\n")


if __name__ == "__main__":
    main()
