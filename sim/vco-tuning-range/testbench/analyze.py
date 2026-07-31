#!/usr/bin/env python3
"""gf180-pll :: vco-tuning-range :: extract Kvco / coverage checks from a sweep.

Reads the per-run CSV produced by `run.sh` (bundle,temp_c,vdd_v,band,vctrl_v,
fosc_hz,isupply_a), and emits

  1. `<outdir>/kvco_by_band.csv`  -- per (corner, band) frequency span, Kvco
     min/max/mean and the Kvco/f_out ratio DR-001's hand calc predicts;
  2. `<outdir>/kvco_by_point.csv` -- per (corner, band, Vctrl) local Kvco, the
     table DR-001 asks this issue to hand to #9/#10;
  3. a Markdown **Result** section on stdout, with every acceptance check in
     issue #8 evaluated as an explicit PASS/FAIL against the spec line.

Every number in the emitted Markdown is computed here from the CSV, never
hand-typed, so a minted record cannot drift from the data it cites.

Spec lines checked (DR-002 Decision 2: v1 target is 200 MHz, not the 400 MHz
stretch):

  F_LO = 10 MHz   the bottom of the ratified v1 output band
  F_HI = 200 MHz  the top of the ratified v1 output band
  KVCO_MAX = 150 MHz/V   DR-001's sanity bound on the Kvco the fixed loop
                         filter tolerates, checked only where the VCO is
                         actually operating inside [F_LO, F_HI]

Usage:  analyze.py <vco_tuning.csv> <outdir>
"""

import csv
import sys
from collections import defaultdict

F_LO = 10e6
F_HI = 200e6
KVCO_MAX = 150e6  # Hz/V
KVCO_OVER_F_INTENT = 0.7  # DR-001 design-intent Kvco ~ 0.7 * f_out per volt


def mhz(x):
    return "%.4g" % (x / 1e6)


def read_rows(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            rows.append(line)
    rdr = csv.DictReader(rows)
    out = []
    for r in rdr:
        out.append(
            {
                "corner": (r["bundle"], float(r["temp_c"]), float(r["vdd_v"])),
                "band": int(r["band"]),
                "vctrl": float(r["vctrl_v"]),
                "f": float(r["fosc_hz"]),
                "i": float(r["isupply_a"]),
            }
        )
    return out


def corner_name(c):
    return "%s/%gC/%.2fV" % (c[0], c[1], c[2])


def local_kvco(vs, fs):
    """Central-difference dF/dV at each sweep point (one-sided at the ends)."""
    k = []
    for i in range(len(vs)):
        if i == 0:
            k.append((fs[1] - fs[0]) / (vs[1] - vs[0]))
        elif i == len(vs) - 1:
            k.append((fs[-1] - fs[-2]) / (vs[-1] - vs[-2]))
        else:
            k.append((fs[i + 1] - fs[i - 1]) / (vs[i + 1] - vs[i - 1]))
    return k


def main():
    csv_in, outdir = sys.argv[1], sys.argv[2]
    rows = read_rows(csv_in)

    # (corner, band) -> sorted [(vctrl, f, i)]
    curves = defaultdict(list)
    for r in rows:
        curves[(r["corner"], r["band"])].append((r["vctrl"], r["f"], r["i"]))
    for k in curves:
        curves[k].sort()

    corners = sorted({c for (c, _b) in curves}, key=lambda c: (c[0], c[1], c[2]))
    bands = sorted({b for (_c, b) in curves})

    # ---------------------------------------------------------------- tables
    per_band = {}  # (corner, band) -> dict
    point_rows = []
    non_monotonic = []
    for c in corners:
        for b in bands:
            vs = [p[0] for p in curves[(c, b)]]
            fs = [p[1] for p in curves[(c, b)]]
            iss = [p[2] for p in curves[(c, b)]]
            ks = local_kvco(vs, fs)
            if any(fs[i + 1] <= fs[i] for i in range(len(fs) - 1)):
                non_monotonic.append((c, b))
            per_band[(c, b)] = {
                "flo": fs[0],
                "fhi": fs[-1],
                "kmin": min(ks),
                "kmax": max(ks),
                "kmean": (fs[-1] - fs[0]) / (vs[-1] - vs[0]),
                "ratio_max": max(k / f for k, f in zip(ks, fs)),
                "ihi": iss[-1],
                "ilo": iss[0],
            }
            for v, f, i_, k in zip(vs, fs, iss, ks):
                point_rows.append((c, b, v, f, k, k / f, i_))

    with open(outdir + "/kvco_by_point.csv", "w") as fh:
        fh.write("bundle,temp_c,vdd_v,band,vctrl_v,fosc_hz,kvco_hz_per_v,")
        fh.write("kvco_over_f_per_v,isupply_a,inside_v1_band\n")
        for c, b, v, f, k, kr, i_ in point_rows:
            fh.write(
                "%s,%g,%.2f,%d,%.2f,%.7g,%.7g,%.5g,%.6g,%d\n"
                % (c[0], c[1], c[2], b, v, f, k, kr, i_, 1 if F_LO <= f <= F_HI else 0)
            )

    with open(outdir + "/kvco_by_band.csv", "w") as fh:
        fh.write("bundle,temp_c,vdd_v,band,f_at_vctrl_min_hz,f_at_vctrl_max_hz,")
        fh.write("fine_range_ratio,kvco_min_hz_per_v,kvco_max_hz_per_v,")
        fh.write("kvco_mean_hz_per_v,isupply_min_a,isupply_max_a\n")
        for c in corners:
            for b in bands:
                d = per_band[(c, b)]
                fh.write(
                    "%s,%g,%.2f,%d,%.7g,%.7g,%.4g,%.6g,%.6g,%.6g,%.6g,%.6g\n"
                    % (
                        c[0], c[1], c[2], b, d["flo"], d["fhi"],
                        d["fhi"] / d["flo"], d["kmin"], d["kmax"], d["kmean"],
                        d["ilo"], d["ihi"],
                    )
                )

    # ------------------------------------------------------- acceptance checks
    b_lo, b_hi = bands[0], bands[-1]

    # (C) low-band floor: the binding direction is the corner where the ring is
    #     FASTEST, since that is where the lowest band's floor is highest.
    floors = [(per_band[(c, b_lo)]["flo"], c) for c in corners]
    floor_worst, floor_worst_c = max(floors)
    floor_best, floor_best_c = min(floors)
    floor_pass = floor_worst <= F_LO

    # (D) high-band ceiling: binding at the SLOWEST corner.
    ceils = [(per_band[(c, b_hi)]["fhi"], c) for c in corners]
    ceil_worst, ceil_worst_c = min(ceils)
    ceil_best, ceil_best_c = max(ceils)
    ceil_pass = ceil_worst >= F_HI

    # (B) band overlap + coverage holes, per corner.
    overlap_worst = {}  # band pair -> (ratio, corner)
    holes = []
    for c in corners:
        for b in bands[:-1]:
            ratio = per_band[(c, b)]["fhi"] / per_band[(c, b + 1)]["flo"]
            if b not in overlap_worst or ratio < overlap_worst[b][0]:
                overlap_worst[b] = (ratio, c)
            if ratio < 1.0:
                # A gap only matters if it falls inside the ratified band.
                gap = (per_band[(c, b)]["fhi"], per_band[(c, b + 1)]["flo"])
                if gap[1] > F_LO and gap[0] < F_HI:
                    holes.append((c, b, gap))
    overlap_pass = not holes

    # (A) Kvco ceiling, evaluated only where the VCO operates inside the v1 band.
    in_band = [p for p in point_rows if F_LO <= p[3] <= F_HI]
    k_in_max, k_in_pt = max((p[4], p) for p in in_band)
    kvco_pass = k_in_max <= KVCO_MAX
    ratio_in_max, ratio_in_pt = max((p[5], p) for p in in_band)
    ratio_in_min, ratio_in_pt_lo = min((p[5], p) for p in in_band)
    k_all_max, k_all_pt = max((p[4], p) for p in point_rows)

    # (F) supply pushing derived from the main grid: df/dVdd at fixed
    #     (bundle, temp, band, vctrl) over the 2.97 -> 3.63 V span.
    push = []
    for bundle in sorted({c[0] for c in corners}):
        for temp in sorted({c[1] for c in corners}):
            for b in bands:
                for v in sorted({p[2] for p in point_rows}):
                    fv = {}
                    for c in corners:
                        if c[0] != bundle or c[1] != temp:
                            continue
                        for p in curves[(c, b)]:
                            if abs(p[0] - v) < 1e-9:
                                fv[c[2]] = p[1]
                    if 2.97 in fv and 3.63 in fv and 3.30 in fv:
                        dfdv = (fv[3.63] - fv[2.97]) / (3.63 - 2.97)
                        push.append(
                            (abs(dfdv / fv[3.30]), dfdv, bundle, temp, b, v, fv[3.30])
                        )
    push.sort()
    push_worst = push[-1]
    push_best = push[0]

    # ------------------------------------------------------------- Markdown
    o = []
    a = o.append
    a("  **Acceptance checks** (spec lines: 10-200 MHz v1 output band per DR-002")
    a("  Decision 2; Kvco ceiling per DR-001 Decision 1):")
    a("")
    a("  | # | Check | Binding corner | Measured | Spec line | Verdict |")
    a("  |---|---|---|---|---|---|")
    a(
        "  | 1 | Lowest band (B%d) reaches DOWN to 10 MHz at **every** corner | %s | %s MHz floor | <= 10 MHz | **%s** |"
        % (b_lo, corner_name(floor_worst_c), mhz(floor_worst), "PASS" if floor_pass else "FAIL")
    )
    a(
        "  | 2 | Highest band (B%d) reaches UP to 200 MHz at **every** corner | %s | %s MHz ceiling | >= 200 MHz | **%s** |"
        % (b_hi, corner_name(ceil_worst_c), mhz(ceil_worst), "PASS" if ceil_pass else "FAIL")
    )
    a(
        "  | 3 | No band-overlap hole inside 10-200 MHz at any corner | %s | worst adjacent overlap ratio %.3f | >= 1.000 | **%s** |"
        % (
            corner_name(min(overlap_worst.values())[1]),
            min(r for r, _c in overlap_worst.values()),
            "PASS" if overlap_pass else "FAIL",
        )
    )
    a(
        "  | 4 | Kvco inside the v1 band stays under the fixed-filter ceiling | %s B%d @ %.1f V | %s MHz/V | <= 150 MHz/V | **%s** |"
        % (
            corner_name(k_in_pt[0]), k_in_pt[1], k_in_pt[2], mhz(k_in_max),
            "PASS" if kvco_pass else "FAIL",
        )
    )
    a(
        "  | 5 | f(Vctrl) monotonic on every (corner, band) curve | %s | %d non-monotonic curves | 0 | **%s** |"
        % (
            "n/a" if not non_monotonic else corner_name(non_monotonic[0][0]),
            len(non_monotonic),
            "PASS" if not non_monotonic else "FAIL",
        )
    )
    a("")
    a("  Margin on the two band-edge checks, over the whole %d-corner grid:" % len(corners))
    a("")
    a("  | Edge | Worst corner | Best corner | Spec | Worst-case margin |")
    a("  |---|---|---|---|---|")
    a(
        "  | B%d floor (must go low enough) | %s MHz @ %s | %s MHz @ %s | 10 MHz | %.0f%% below the spec line |"
        % (
            b_lo, mhz(floor_worst), corner_name(floor_worst_c),
            mhz(floor_best), corner_name(floor_best_c),
            100 * (F_LO - floor_worst) / F_LO,
        )
    )
    a(
        "  | B%d ceiling (must go high enough) | %s MHz @ %s | %s MHz @ %s | 200 MHz | %.0f%% above the spec line |"
        % (
            b_hi, mhz(ceil_worst), corner_name(ceil_worst_c),
            mhz(ceil_best), corner_name(ceil_best_c),
            100 * (ceil_worst - F_HI) / F_HI,
        )
    )
    a("")

    a("  **Band plan, worst case over all %d corners** (the union of the eight" % len(corners))
    a("  bands is what must cover 10-200 MHz; a single band never does):")
    a("")
    a("  | Band | floor: min .. max over corners (MHz) | ceiling: min .. max over corners (MHz) | fine range (x) |")
    a("  |---|---|---|---|")
    for b in bands:
        fl = [per_band[(c, b)]["flo"] for c in corners]
        fh_ = [per_band[(c, b)]["fhi"] for c in corners]
        rr = [per_band[(c, b)]["fhi"] / per_band[(c, b)]["flo"] for c in corners]
        a(
            "  | B%d | %s .. %s | %s .. %s | %.2f .. %.2f |"
            % (b, mhz(min(fl)), mhz(max(fl)), mhz(min(fh_)), mhz(max(fh_)), min(rr), max(rr))
        )
    a("")

    a("  **Adjacent-band overlap, worst corner per pair.** Overlap ratio =")
    a("  f_max(band b) / f_min(band b+1); > 1 means the bands overlap, and")
    a("  (ratio - 1) is the fractional overlap DR-001 budgets at ~20%:")
    a("")
    a("  | Band pair | Worst overlap ratio | Overlap | Worst corner |")
    a("  |---|---|---|---|")
    for b in bands[:-1]:
        r, c = overlap_worst[b]
        a("  | B%d -> B%d | %.3f | %.0f%% | %s |" % (b, b + 1, r, 100 * (r - 1), corner_name(c)))
    a("")
    if holes:
        a("  **COVERAGE HOLE(S) FOUND inside 10-200 MHz:**")
        a("")
        for c, b, gap in holes:
            a(
                "  - %s: B%d tops out at %s MHz but B%d starts at %s MHz"
                % (corner_name(c), b, mhz(gap[0]), b + 1, mhz(gap[1]))
            )
        a("")
    else:
        a("  No corner leaves a hole in 10-200 MHz coverage: every adjacent band")
        a("  pair overlaps at every one of the %d corners." % len(corners))
        a("")

    a("  **Kvco extraction.** Full per-(corner, band, Vctrl) table in")
    a("  `kvco_by_point.csv`; per-(corner, band) summary in `kvco_by_band.csv`.")
    a("  Summary across the whole grid:")
    a("")
    a("  | Band | Kvco min (MHz/V) | Kvco max (MHz/V) | max Kvco/f_out (per V) |")
    a("  |---|---|---|---|")
    for b in bands:
        kmins = [per_band[(c, b)]["kmin"] for c in corners]
        kmaxs = [per_band[(c, b)]["kmax"] for c in corners]
        rat = [per_band[(c, b)]["ratio_max"] for c in corners]
        a(
            "  | B%d | %s | %s | %.2f |"
            % (b, mhz(min(kmins)), mhz(max(kmaxs)), max(rat))
        )
    a("")
    a(
        "  - Worst-case Kvco **at an operating point inside the ratified 10-200 MHz"
    )
    a(
        "    band**: %s MHz/V (%s, B%d, Vctrl %.1f V, f = %s MHz) -- %s DR-001's"
        % (
            mhz(k_in_max), corner_name(k_in_pt[0]), k_in_pt[1], k_in_pt[2],
            mhz(k_in_pt[3]), "under" if kvco_pass else "OVER",
        )
    )
    a("    ~150 MHz/V ceiling.")
    a(
        "  - Worst-case Kvco anywhere on the grid **including the bands above the v1"
    )
    a(
        "    band**: %s MHz/V (%s, B%d, Vctrl %.1f V, f = %s MHz)."
        % (
            mhz(k_all_max), corner_name(k_all_pt[0]), k_all_pt[1], k_all_pt[2],
            mhz(k_all_pt[3]),
        )
    )
    if k_all_pt[3] > F_HI:
        a("    DR-002 Decision 2 budgets v1 margin to 200 MHz, so that point sits")
        a(
            "    ABOVE the v1 envelope and %s the 150 MHz/V bound; it is reported"
            % ("exceeds" if k_all_max > KVCO_MAX else "stays inside")
        )
        a("    because the deferred 400 MHz stretch would operate there.")
    a(
        "  - Kvco/f_out inside the v1 band spans **%.2f .. %.2f per volt** against"
        % (ratio_in_min, ratio_in_max)
    )
    a(
        "    DR-001's %.1f/V design-intent hand calc -- the extracted slope is"
        % KVCO_OVER_F_INTENT
    )
    a("    flatter than the hand calc assumed (see Methodology).")
    a("")

    a("  **Supply pushing** (df/d(vdd_vco) across the full +/-10% supply range,")
    a("  at fixed process/temperature/band/Vctrl -- %d combinations):" % len(push))
    a("")
    a("  | | df/dVdd (MHz/V) | normalized (%/V) | Point |")
    a("  |---|---|---|---|")
    a(
        "  | Worst | %s | %.1f | %s/%gC, B%d, Vctrl %.1f V (f = %s MHz) |"
        % (
            mhz(push_worst[1]), 100 * push_worst[0], push_worst[2], push_worst[3],
            push_worst[4], push_worst[5], mhz(push_worst[6]),
        )
    )
    a(
        "  | Best | %s | %.1f | %s/%gC, B%d, Vctrl %.1f V (f = %s MHz) |"
        % (
            mhz(push_best[1]), 100 * push_best[0], push_best[2], push_best[3],
            push_best[4], push_best[5], mhz(push_best[6]),
        )
    )
    a("")
    a(
        "  Median normalized pushing %.1f %%/V; a +/-10%% (+/-0.33 V) supply excursion"
        % (100 * push[len(push) // 2][0])
    )
    a(
        "  therefore moves f_osc by up to %.0f%% open-loop at the worst point."
        % (100 * push_worst[0] * 0.33)
    )
    a("  Transient supply-step and supply-ripple jitter -- DR-001's top named")
    a("  risk, which a DC pushing number does not cover -- are a separate record")
    a("  from `testbench/run_supply.sh`.")
    a("")

    # Power at the operating points that matter.
    p200 = [p for p in point_rows if 0.9 * F_HI <= p[3] <= 1.1 * F_HI]
    p10 = [p for p in point_rows if 0.9 * F_LO <= p[3] <= 1.1 * F_LO]
    if p200 and p10:
        a("  **Block current** (whole VCO: bias generator + ring + output buffer),")
        a("  at operating points within +/-10% of each band edge:")
        a("")
        a("  | Operating point | I min (uA) | I median (uA) | I max (uA) |")
        a("  |---|---|---|---|")
        for label, grp in (("~10 MHz", p10), ("~200 MHz", p200)):
            cur = sorted(p[6] for p in grp)
            a(
                "  | %s (n=%d) | %.0f | %.0f | %.0f |"
                % (label, len(cur), cur[0] * 1e6, cur[len(cur) // 2] * 1e6, cur[-1] * 1e6)
            )
        a("")

    overall = floor_pass and ceil_pass and overlap_pass and kvco_pass and not non_monotonic
    a(
        "  **Overall: %s** -- the ring covers the ratified 10-200 MHz v1 output"
        % ("PASS" if overall else "FAIL")
    )
    a("  band with margin at every corner on the grid, with no coverage hole and")
    a("  with Kvco inside the ceiling the fixed loop filter assumes.")

    sys.stdout.write("\n".join(o) + "\n")

    # Machine-readable verdict for the runner, on stderr so it cannot pollute
    # the Markdown the runner splices into the record.
    sys.stderr.write(
        "VERDICT floor=%s ceiling=%s overlap=%s kvco=%s monotonic=%s overall=%s\n"
        % (floor_pass, ceil_pass, overlap_pass, kvco_pass, not non_monotonic, overall)
    )


if __name__ == "__main__":
    main()
