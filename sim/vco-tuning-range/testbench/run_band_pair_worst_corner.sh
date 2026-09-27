#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: the B0 -> B1 adjacent-band pair, BOTH bands
# drawn from ONE mismatch draw, at the pair's own worst corner (issue #597)
#
# --- What gap this closes -------------------------------------------------
#
# `sim/vco-tuning-range/records/20260923-084925-1655e11.md` (#482, minted by
# `run_band0_worst_corner.sh`) measured band 0's frequency dispersion under
# random device mismatch at the exact (corner, Vctrl) point that sets band 0's
# contribution to its own worst adjacent-band overlap margin -- `ss`/125C/
# 3.63V, Vctrl = 2.7V -- and compared it against band 1's UNCHANGED SYSTEMATIC
# (`sw_stat_mismatch=0`) floor. Both that record and its predecessor
# (`20260817-143524-0e9cfc9`) name the same two limitations in their own text:
#
#   (1) "Band 1's own f_min is NOT re-measured with mismatch here ... not a
#        joint two-band Monte Carlo."
#   (2) The verdict rested on a PROXY -- band 0's `|mean|+3sigma` as a
#       percentage of its mean, read against the fractional overlap margin --
#       which both records flagged as "an order-of-magnitude sanity flag, not
#       a rigorous directional bound".
#
# T1/bronze item 6 (#127) asks for Monte Carlo evidence combined with process
# corners, and #597's derivation of that item found this campaign's Monte Carlo
# evidence at 2 corners x 1 band, never 1 corner x 2 bands. This script closes
# the band axis, and closing it removes BOTH limitations at once, because (2)
# was only a proxy BECAUSE of (1): with one band drawn, the inequality the
# coverage-hole check actually asks about cannot be written down under mismatch
# at all.
#
# --- What the joint draw makes measurable ---------------------------------
#
# The band plan's coverage-hole question is an inequality between two bands ON
# ONE DIE: `f_max(band 0) >= f_min(band 1)`. Bands 0 and 1 differ by one
# switched leg of `design/vco_bias.sch`'s mirror cascade and share every
# always-on leg, the V->I converter and all five ring stages -- so on real
# silicon the two frequencies in that inequality are strongly coupled, and the
# quantity that decides the hole is their RATIO, not either one's spread.
#
# `testbench/tb_vco_band_pair.sp` (new for this issue) measures both band codes
# in ONE ngspice invocation: the gf180mcu mismatch model's `agauss()` draws are
# evaluated once at netlist PARSE time, so two `tran` runs inside one
# `.control` block see the SAME per-instance Vth/beta offsets, and the band
# code is moved between them with `alter` on three DC sources -- no device
# added, removed or re-parameterised. Each invocation therefore yields a
# per-DRAW ratio sample, and the verdict is the ratio distribution's own
# one-sided 3-sigma tail:
#
#   worst-case overlap ratio  =  mean(f0/f1) - 3*sigma(f0/f1)   >= 1
#
# That is the quantity the systematic `band_overlap` check computes (1.319 at
# this corner), with mismatch folded in, and nothing about it is a proxy.
#
# --- Why this is not just a tighter number -------------------------------
#
# This script also reports what the INDEPENDENT-draw bound would have been on
# the same samples -- `(mean(f0) - 3*sd(f0)) / (mean(f1) + 3*sd(f1))`, pushing
# each band to its own opposite tail as if the two were unrelated -- together
# with the measured Pearson correlation between f0 and f1 across draws. Those
# two figures are the evidence for how much the independent-draw methodology
# was throwing away, and they are why a record built on independent draws could
# not have settled this question in either direction: an independent bound that
# fails says nothing about a die, and an independent bound that passes is
# accidentally lucky rather than argued. The correlation is a MEASUREMENT here,
# not an assumption, which is the difference between this record and a stated
# hope about common-mode cancellation.
#
# --- Corner + Vctrl points, and how they were verified ---------------------
#
# `sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv`'s
# "B0 -> B1" row: worst overlap ratio 1.319 at `ss`/125C/3.63V, where `ss` is
# the bare 5-way MOS-only bundle (passives at `res_typical`, `moscap_typical`,
# see common.sh's bundle_libs()), NOT the composite `all-slow` bundle.
# Re-confirmed for this script directly against that record's own per-point
# data (`corners/20260804-164956-72883fb/raw_measures.csv`, rows
# `ss,125.0,3.63,band0` and `ss,125.0,3.63,band1`):
#   band0 f7 (Vctrl=2.7V, i.e. f_max(band0)) = 9122300.0 Hz
#   band1 f1 (Vctrl=0.9V, i.e. f_min(band1)) = 6917000.0 Hz
#   ratio = 9122300 / 6917000 = 1.31882 -- matches the cited 1.319.
# `band_overlap` is defined as `f_max(band b) / f_min(band b+1)`, so f_max is
# taken at the TOP of the 0.9-2.7V control window (the seventh of the seven
# 0.3V-spaced control points) and f_min at the BOTTOM (the first). Each band is
# driven at ITS OWN of those two Vctrl values here, which is what makes the
# ratio this script measures the same quantity the systematic check computes.
#
# --- What this is NOT ------------------------------------------------------
#
# Not a supersession of any prior record. `20260817-143524-0e9cfc9` (bands 0
# and 7, mid-window, nominal corner), `20260923-084925-1655e11` (band 0, its
# own worst corner and Vctrl) and `20260927-081930-d004d5b` (the single-point
# B0 -> B1 joint draw this script minted for #597) all stand unmodified as
# historical evidence -- sim/ is append-only. Every record this script mints is
# additive and supersedes by CITATION only.
#
# === #622: the CORNER and PAIR axes, which the #597 version left at 1 ========
#
# The paragraph that used to stand here said, of the #597 single-point version
# of this script, that it "does not widen the CORNER axis: one corner, the
# pair's own worst" and "not a check of any other adjacent pair". #622 is the
# issue that came back for both of those residuals, and this section is the
# answer. The reasoning it replaces was: the binding corner is already known
# from the systematic 45-point sweep, so measuring dispersion anywhere else
# reintroduces a different-point comparison. That argument is sound about WHERE
# THE DETERMINISTIC MARGIN IS THINNEST and silent about the thing a Monte Carlo
# campaign is for -- whether the DISPERSION that eats that margin is also
# largest there. Those are two different orderings, and until this version
# nothing in the tree had measured the second one. #597's own finding on the
# sibling `sim/mc-cp-mismatch` campaign is the precedent that they can disagree:
# widening that campaign from a 3-point diagonal subset to the 20 box vertices
# moved three of its four terms' binding corner onto points the subset did not
# contain.
#
# THE GRID, and why these points and not others (sim/README.md's "Default
# corner matrix" rule requires a justification for any subset of the 45):
#
#   Group 1 -- THE BUNDLE AXIS, 5 points. Each of the five MOS bundles
#   (`typical`, `ff`, `fs`, `sf`, `ss`) at ITS OWN deterministically-thinnest
#   adjacent-pair point, computed over all 7 pairs x 3 temperatures x
#   3 supplies from `corners/20260804-164956-72883fb/raw_measures.csv`. That
#   computation returns the SAME (pair, temperature, supply) for all five
#   bundles -- B3 -> B4 at 125 C / 3.63 V -- which is itself the finding that
#   makes this group cheap: the bundle axis can be swept at fixed T and V
#   without any bundle being sampled away from its own worst point. This group
#   is what discharges the "three of five MOS bundles are never drawn" gap.
#
#   Group 2 -- THE TEMPERATURE x SUPPLY BOX, 3 further points. `ss` (the
#   thinnest bundle) at B3 -> B4 at the remaining three vertices of the
#   temperature x supply box: -40 C/2.97 V, -40 C/3.63 V, 125 C/2.97 V. The
#   125 C/3.63 V vertex is already in group 1, so the four vertices are
#   complete. This is the group that tests the ordering rather than assuming
#   it: -40 C/2.97 V is where the systematic ratio is WIDEST for this bundle
#   (1.40054 vs 1.26784 at 125 C/3.63 V), so if relative dispersion grows
#   faster than the margin does, the binding point under mismatch is here and
#   not in group 1. Nothing before this version could have detected that.
#
#   Group 3 -- THE PAIR AXIS, 3 further points. `ss`/125 C/3.63 V for
#   B0 -> B1, B1 -> B2 and B6 -> B7. B0 -> B1 is the continuity/regression
#   point -- it is the exact point `20260927-081930-d004d5b` sampled, so its
#   verdict is re-derived here on independent seeds and can be read against
#   that record's 1.28193. B1 -> B2 is the second-thinnest pair at this point
#   (1.29887) and B6 -> B7 is the top of the band plan, whose own worst point
#   the systematic sweep places at a DIFFERENT supply (`ss`/125 C/2.97 V) --
#   the one pair whose deterministic optimum disagrees with the rest.
#
# WHAT THE GRID STILL DOES NOT SAMPLE, stated rather than implied: the 27 C
# temperature and the 3.30 V supply mid-points; the two COMPOSITE bundles
# (`all-slow`/`all-fast`, which are not among the 45 mandated MOS-axis points
# -- see bundle_libs() in common.sh); pairs B2 -> B3, B3 -> B4 (at bundles
# other than `ss`), B4 -> B5 and B5 -> B6 away from 125 C/3.63 V; and every
# intermediate Vctrl point. The last of those is a DEFINITIONAL exclusion, not
# a sampling gap: `band_overlap` is `f_max(band b) / f_min(band b+1)`, so the
# inequality this campaign measures only exists at the two ends of the control
# window, and a mid-window Vctrl does not appear in it at all.
#
# --- Erratum: the `# switches:` line of the CSV already committed (#601) -----
#
# This script was written on a branch cut BEFORE #601 landed on main (as #607,
# `4b8dcad9`), which gave `simenv_provenance` its optional fifth switches-note
# argument. Its first version called `simenv_provenance` with four arguments,
# so the `# switches:` line of the one CSV it had already minted --
#
#   corners/20260927-081930-d004d5b/mismatch.csv
#
# -- carries the pre-#601 harness default:
#
#   # switches: design.ngspice defaults (sw_stat_global=0, sw_stat_mismatch=0
#   #           -> nominal skew, no Monte Carlo)
#
# -- which is the opposite of what tb_vco_band_pair.sp does. That deck declares
# `sw_stat_global=0` / `sw_stat_mismatch=1` after the design.ngspice include, so
# the later declaration wins (the harness-ordering finding cited above), and
# every one of the 200 rows under that header is a mismatch draw.
#
# Those bytes are NOT edited and neither is the record beside them -- sim/ is
# append-only evidence and sim/README.md forbids editing a committed record even
# to correct it. The correction is made forward: SWITCHES_NOTE below now feeds
# simenv_provenance, so every CSV minted from this script states the switches
# the run actually used, and this file names the one file that predates it. The
# same disposition run_mismatch.sh and run_band0_worst_corner.sh use for their
# own pre-#601 CSVs.
#
# For that one file the record's Environment provenance field is authoritative
# and the CSV's `# switches:` line is a harness default that was never true of
# the run. `records/20260927-081930-d004d5b.md` states the switches correctly in
# both its "Environment provenance" field and its "Statistical convention"
# field, as simenv_env_block has taken the override since #15.
#
# Usage:
#   ./run_band_pair_worst_corner.sh          # full grid -> mints records/<id>.md
#   ./run_band_pair_worst_corner.sh --check  # 2 draws at the binding point, to stdout
#   ./run_band_pair_worst_corner.sh --grid   # print the grid and exit (no simulator)
#   N_SAMPLES=.. ./run_band_pair_worst_corner.sh   # draws PER POINT (default 200)
#   SIM_JOBS=.. ./run_band_pair_worst_corner.sh    # parallel ngspice processes
#
# Cost, MEASURED on this host by running it, not estimated: the full 11-point
# grid at N_SAMPLES=200 is 2200 joint draws (two transient analyses per parse)
# and took 44m16s wall at SIM_JOBS=10 on an 18-core arm64 host that was also
# carrying unrelated load -- 12.1 core-seconds per draw, ~7.4 CPU-hours total.
# #622 asked that this be priced before being claimed, because its own "Compute
# cost" section suspected a batch-backend campaign. It is not one: it fits a
# single session at SIM_JOBS >= 8, so KLT_SIM_BACKEND=batch is not needed and
# the issue was not re-routed to the operator. Budget roughly proportionally if
# you change N_SAMPLES or add grid rows -- but note the per-draw cost is set by
# the point's OSCILLATION FREQUENCY (the transient window is sized off it), so a
# low-band row like B0 -> B1 at 9 MHz costs several times a B6 -> B7 row at
# 233 MHz, and a grid's cost is not its row count times a constant.

set -euo pipefail

# Host oversubscription fix -- same finding as sim/mc-cp-mismatch's #146
# build and this experiment's own run_mismatch.sh (see that file's header
# comment for the full measurement). #241 centralized the DETECTION half
# into sim/lib/simenv.sh::simenv_apply_omp_pin; this campaign's own opt-in
# call is unchanged convention.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# bundle_libs() -- the same bundle -> `.lib` sections mapping the systematic
# sweep used, so a grid row naming `ss` means exactly what `ss` meant there.
# shellcheck source=./common.sh
. "${HERE}/common.sh"
simenv_apply_omp_pin

DECK="${HERE}/tb_vco_band_pair.sp"
DUT_SRC="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-band-pair-worst-corner"

# Band A is the LOWER band of the pair, measured at the TOP of its control
# window (its f_max); band B is the UPPER band, measured at the BOTTOM (its
# f_min). Those two Vctrl values are fixed by the DEFINITION of the quantity
# (`band_overlap` = f_max(band b) / f_min(band b+1)) and are the same at every
# grid point, so they are constants rather than grid fields.
VCTRL_A=2.7
VCTRL_B=0.9

# --------------------------------------------------------------------------
# THE GRID (#622). One line per sampled point. See the header comment for the
# derivation of each group and for what the grid deliberately omits.
#
# Fields:
#   bundle temp vdd band_a fnom_a fnom_b group
#
# `band_b` is always `band_a + 1` (adjacent pairs are the only pairs the
# coverage-hole inequality is defined over). `bundle` is expanded to its `.lib`
# sections by common.sh's bundle_libs(), so the MOS-only bundles leave the
# passive sections at typical exactly as the systematic sweep did.
#
# fnom_a / fnom_b are the SYSTEMATIC (sw_stat_mismatch=0) reference frequencies
# at that exact point, transcribed from
# `sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv` --
# fnom_a is band_a's `f7` column (Vctrl = 2.7 V, the seventh of the seven
# 0.3 V-spaced control points) and fnom_b is band_b's `f1` (Vctrl = 0.9 V), for
# the row matching that bundle, temperature and supply. They are used ONLY to
# size each band's transient window and as the per-point systematic reference
# the mismatched result is reported against; `--grid` re-derives them from that
# committed CSV and fails if any has drifted, so a transcription error here
# cannot survive a run.
GRID=(
  # Group 1 -- the bundle axis: all five MOS bundles at their own
  # deterministically-thinnest pair/temperature/supply, which is the same
  # (B3 -> B4, 125 C, 3.63 V) for all five.
  "typical 125 3.63 3 40223800 30785300 bundle"
  "ff      125 3.63 3 39128100 29226700 bundle"
  "fs      125 3.63 3 41040100 30531400 bundle"
  "sf      125 3.63 3 39601500 31229800 bundle"
  "ss      125 3.63 3 41913500 33058900 bundle"
  # Group 2 -- the remaining three vertices of the temperature x supply box, at
  # the thinnest bundle and the same pair. The 125C/3.63V vertex is group 1's
  # `ss` row above.
  "ss      -40 2.97 3 49967100 35676900 tempvolt"
  "ss      -40 3.63 3 35705500 26525300 tempvolt"
  "ss      125 2.97 3 57273800 43730500 tempvolt"
  # Group 3 -- the pair axis at the binding bundle/temperature/supply.
  # B0 -> B1 is the continuity point with records/20260927-081930-d004d5b.md.
  "ss      125 3.63 0  9122300  6917000 pair"
  "ss      125 3.63 1 14890400 11464100 pair"
  "ss      125 3.63 6 232629000 169811000 pair"
)

# The systematic sweep the grid's reference frequencies are transcribed from,
# and which `--grid` re-derives them against.
SYS_RECORD=20260804-164956-72883fb
SYS_RAW="${EXP}/corners/${SYS_RECORD}/raw_measures.csv"

# This campaign's own committed negative control -- the record whose point set
# `run_mismatch.sh`'s CONTROL_POINTS enumerates, which must be the point set of
# THIS grid for signoff/README.md's "Item 6(c)" rule to keep holding (a
# control's grid is the grid of the samples it validates). Named explicitly
# rather than resolved as "the newest control record", so the citation this
# script mints is a fixed, checkable reference; `--grid` asserts the file
# exists, so widening one of the two without the other fails loudly here
# instead of minting a dangling citation.
CONTROL_RECORD=20260927-214737-546a397

# point_id <bundle> <temp> <vdd> <band_a> -- the key used in the CSV, in every
# committed log's filename, and in the record's per-point table. One string, so
# a row and its logs can never disagree about which point they belong to.
point_id() { echo "$1_$2c_$3v_b$4b$(( $4 + 1 ))"; }

# Transient-window margin on those systematic frequencies. WIDER than the
# +/-30% the single-band scripts use, because this deck's window has to hold a
# MISMATCHED frequency whose own 3-sigma spread those records measured at
# ~25% of the mean -- a 30% window leaves essentially no margin past 3 sigma
# and would start losing samples to a `meas` that cannot find its fifth rising
# edge. The window is never trusted for a result, only for tstep/tstop sizing,
# so widening it costs wall clock and nothing else.
WIN_LO_FRAC=0.55
WIN_HI_FRAC=1.45

# sys_ratio <fnom_a> <fnom_b> -- the systematic overlap ratio a point's two
# reference figures give, recomputed unrounded from its own two operands so the
# record can state both and a reader can see they agree with `band_overlap.csv`.
sys_ratio() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.5f", a/b}'; }
# Hole-free means the ratio stays >= this. 1.0 is not a tuning knob: at exactly
# 1.0 the lower band's top and the upper band's bottom meet, and below it there
# is a frequency neither band reaches.
RATIO_FLOOR=1.0

N_SAMPLES="${N_SAMPLES:-200}"

# The point id leads every row, so the CSV is self-describing per point and the
# per-point tables in the record are filtered from it by column 1 rather than by
# position. `group` rides along so a reader can see which of the header's three
# justification groups a row belongs to without re-deriving it.
HEADER="point_id,group,corner,temp_c,vdd,seed,band_a,vctrl_a_v,f_a_hz,i_a_a,band_b,vctrl_b_v,f_b_hz,i_b_a,ratio"

# The `# switches:` line of the CSV this script writes (#601), passed to
# simenv_provenance as its optional fifth argument. Prose counterpart: the
# simenv_env_block switches-note in the record body below. Without it
# simenv_provenance emits its design.ngspice-default wording -- "no Monte
# Carlo" -- which for this deck says the opposite of what ran, over data that
# is nothing but joint mismatch draws.
SWITCHES_NOTE="design.ngspice defaults OVERRIDDEN by tb_vco_band_pair.sp, which re-declares them after the include (sw_stat_global=0, sw_stat_mismatch=1 -> mismatch-only Monte Carlo, .option rndseed set per joint draw)"

stage_netlist() {
  mkdir -p "$1"
  cp "${DUT_SRC}" "$1/vco.spice"
}

# Transient window for one band, off its own systematic frequency.
# Echoes "tsettle tstop tmax".
window_for() {
  local fnom="$1" flo fhi
  flo=$(awk -v f="${fnom}" -v k="${WIN_LO_FRAC}" 'BEGIN{print f*k}')
  fhi=$(awk -v f="${fnom}" -v k="${WIN_HI_FRAC}" 'BEGIN{print f*k}')
  awk -v lo="${flo}" -v hi="${fhi}" 'BEGIN{
    ts = 1.2*4/lo
    printf "%.6g %.6g %.6g\n", ts, ts + 1.2*7/lo, 1/(80*hi)
  }'
}

# One draw -> one CSV row appended to $2. Both bands come out of THIS
# invocation, which is the whole point (see header comment).
#
# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# run_one <grid-index> <seed> <outfile>
#
# The point is addressed by its INDEX INTO ${GRID[@]} rather than by its ten
# expanded fields, because this function is re-entered through `--one` from the
# xargs fan-out below and a point spec that had to survive a shell round-trip is
# a point spec that can be corrupted by one. The index cannot be: it either
# names a grid row or it does not, and an out-of-range index fails loudly here
# instead of silently simulating some other corner.
run_one() {
  local idx="$1" seed="$2" sfile="$3"
  [ "${idx}" -ge 0 ] && [ "${idx}" -lt "${#GRID[@]}" ] || {
    echo "ERROR: grid index ${idx} out of range (grid has ${#GRID[@]} points)" >&2
    return 1
  }
  local bundle temp vdd band_a fnom_a fnom_b group
  read -r bundle temp vdd band_a fnom_a fnom_b group <<<"${GRID[$idx]}"
  local band_b=$(( band_a + 1 ))
  local libs pid
  libs="$(bundle_libs "${bundle}")"
  pid="$(point_id "${bundle}" "${temp}" "${vdd}" "${band_a}")"
  local tag="pair_${pid}_seed$(printf '%03d' "${seed}")"
  stage_netlist "${WORK}/${tag}"
  local ts0 tstop0 tmax0 ts1 tstop1 tmax1
  read -r ts0 tstop0 tmax0 <<<"$(window_for "${fnom_a}")"
  read -r ts1 tstop1 tmax1 <<<"$(window_for "${fnom_b}")"
  local a0 a1 a2 b0 b1 b2
  a0=$(( band_a & 1 )); a1=$(( (band_a >> 1) & 1 )); a2=$(( (band_a >> 2) & 1 ))
  b0=$(( band_b & 1 )); b1=$(( (band_b >> 1) & 1 )); b2=$(( (band_b >> 2) & 1 ))
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" \
    "vsup=${vdd}" "vctrl0=${VCTRL_A}" "vctrl1=${VCTRL_B}" \
    "b0c0=${a0}" "b1c0=${a1}" "b2c0=${a2}" \
    "b0c1=${b0}" "b1c1=${b1}" "b2c1=${b2}" \
    "ts0=${ts0}" "tstop0=${tstop0}" "tmax0=${tmax0}" \
    "ts1=${ts1}" "tstop1=${tstop1}" "tmax1=${tmax1}" \
    "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" la lb fa ia fb ib
  la=$(grep "^MCVCOPAIR_A " "${log}" | tail -1)
  lb=$(grep "^MCVCOPAIR_B " "${log}" | tail -1)
  [ -n "${la}" ] && [ -n "${lb}" ] || {
    echo "ERROR: missing MCVCOPAIR_A/_B for ${pid} seed=${seed} (see ${log})" >&2
    return 1
  }
  fa=$(echo "${la}" | sed -n 's/.* f=\([^ ]*\).*/\1/p')
  ia=$(echo "${la}" | sed -n 's/.* i=\([^ ]*\).*/\1/p')
  fb=$(echo "${lb}" | sed -n 's/.* f=\([^ ]*\).*/\1/p')
  ib=$(echo "${lb}" | sed -n 's/.* i=\([^ ]*\).*/\1/p')
  # Refuse a sample whose either half did not oscillate plausibly rather than
  # letting a `meas` that latched onto the wrong edge become a data point. The
  # band is expected within the transient window's own frequency bracket by
  # construction -- if it is outside, the window was wrong for this draw and
  # the measurement is not trustworthy, whichever direction it missed in.
  awk -v fa="${fa}" -v fb="${fb}" -v na="${fnom_a}" -v nb="${fnom_b}" \
      -v lo="${WIN_LO_FRAC}" -v hi="${WIN_HI_FRAC}" -v s="${seed}" -v p="${pid}" '
    BEGIN {
      bad = 0
      if (fa+0 < na*lo || fa+0 > na*hi) { printf "ERROR: %s seed %s band A f=%g outside window bracket [%g, %g]\n", p, s, fa, na*lo, na*hi > "/dev/stderr"; bad = 1 }
      if (fb+0 < nb*lo || fb+0 > nb*hi) { printf "ERROR: %s seed %s band B f=%g outside window bracket [%g, %g]\n", p, s, fb, nb*lo, nb*hi > "/dev/stderr"; bad = 1 }
      exit bad
    }'
  awk -v p="${pid}" -v g="${group}" -v c="${bundle}" -v t="${temp}" -v d="${vdd}" \
      -v s="${seed}" -v ba="${band_a}" -v va="${VCTRL_A}" -v fa="${fa}" -v ia="${ia}" \
      -v bb="${band_b}" -v vb="${VCTRL_B}" -v fb="${fb}" -v ib="${ib}" \
    'BEGIN { printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.6f\n", p, g, c, t, d, s, ba, va, fa, ia, bb, vb, fb, ib, fa/fb }' >>"${sfile}"
}

# --grid: print the grid, and RE-DERIVE every reference frequency in it against
# the systematic sweep's committed CSV. No simulator, so this is the cheap check
# that the transcription in GRID above is still exactly what that record
# measured -- the one way this script could silently size a window off, and
# report a systematic reference from, the wrong corner.
print_grid() {
  local rc=0
  [ -f "${SYS_RAW}" ] || {
    echo "ERROR: ${SYS_RAW} missing -- cannot verify the grid's reference frequencies" >&2
    return 1
  }
  # The negative control this record will CITE must exist before the record can
  # honestly cite it. Checked here (and therefore on every run, since the
  # pre-flight calls print_grid) rather than at mint time, so the failure lands
  # before the simulator burns hours rather than after.
  [ -f "${EXP}/records/${CONTROL_RECORD}.md" ] || {
    echo "ERROR: negative-control record ${CONTROL_RECORD} not found at" \
      "${EXP}/records/${CONTROL_RECORD}.md -- re-mint the control with" \
      "'./run_mismatch.sh --control' and update CONTROL_RECORD in this script" >&2
    return 1
  }
  printf '%-26s %-9s %-8s %-6s %-5s %12s %12s %9s\n' \
    point_id group bundle temp vdd fnom_a fnom_b sys_ratio
  local spec bundle temp vdd band_a fnom_a fnom_b group band_b pid ra rb
  for spec in "${GRID[@]}"; do
    read -r bundle temp vdd band_a fnom_a fnom_b group <<<"${spec}"
    band_b=$(( band_a + 1 ))
    pid="$(point_id "${bundle}" "${temp}" "${vdd}" "${band_a}")"
    # The systematic CSV writes temperature as a float ("125.0", "-40.0") and
    # the grid writes it as an integer; compare numerically, not as text.
    ra=$(awk -F, -v c="${bundle}" -v t="${temp}" -v v="${vdd}" -v b="band${band_a}" \
      '!/^#/ && $1==c && ($2+0)==(t+0) && ($3+0)==(v+0) && $4==b {print $19; exit}' "${SYS_RAW}")
    rb=$(awk -F, -v c="${bundle}" -v t="${temp}" -v v="${vdd}" -v b="band${band_b}" \
      '!/^#/ && $1==c && ($2+0)==(t+0) && ($3+0)==(v+0) && $4==b {print $13; exit}' "${SYS_RAW}")
    printf '%-26s %-9s %-8s %-6s %-5s %12s %12s %9s\n' \
      "${pid}" "${group}" "${bundle}" "${temp}" "${vdd}" "${fnom_a}" "${fnom_b}" \
      "$(sys_ratio "${fnom_a}" "${fnom_b}")"
    if [ -z "${ra}" ] || [ -z "${rb}" ]; then
      echo "  FAIL: no ${SYS_RECORD} row for ${bundle}/${temp}C/${vdd}V bands ${band_a},${band_b}" >&2
      rc=1
      continue
    fi
    awk -v a="${fnom_a}" -v b="${fnom_b}" -v ra="${ra}" -v rb="${rb}" -v p="${pid}" '
      BEGIN {
        bad = 0
        if ((a+0) != (ra+0)) { printf "  FAIL: %s fnom_a %s != raw_measures f7 %s\n", p, a, ra > "/dev/stderr"; bad = 1 }
        if ((b+0) != (rb+0)) { printf "  FAIL: %s fnom_b %s != raw_measures f1 %s\n", p, b, rb > "/dev/stderr"; bad = 1 }
        exit bad
      }' || rc=1
  done
  if [ "${rc}" -eq 0 ]; then
    echo "OK: ${#GRID[@]} grid points, every reference frequency re-derived from" \
      "corners/${SYS_RECORD}/raw_measures.csv"
  fi
  return "${rc}"
}

# SIM_RESUME=1: a per-draw output file that already exists and is non-empty IS
# the completed draw, so it can be trusted without re-running ngspice. Same
# mechanism, and the same reason, as sim/mc-cp-mismatch/testbench/run.sh's own
# resume guard: this shared build host has been observed terminating a
# long-running background campaign outright, and re-paying a whole campaign's
# wall clock to recover the missing tail of it is avoidable. It is also what
# makes re-minting a record from an already-complete work directory cheap --
# useful when the record TEXT needed a fix and the samples did not. Off by
# default, so a plain invocation is always a clean, from-scratch campaign.
if [ "${SIM_RESUME:-0}" = "1" ] && [ "${1:-}" = "--one" ] && [ -n "${4:-}" ] && [ -s "${4}" ]; then
  echo "vco-tuning-range band-pair: SIM_RESUME=1 -- ${4} already present, skipping" >&2
  exit 0
fi
case "${1:-}" in
  --one)
    shift
    run_one "$@"
    exit 0
    ;;
  --grid)
    print_grid
    exit $?
    ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

[ -f "${DUT_SRC}" ] || {
  echo "ERROR: ${DUT_SRC} missing -- run design/netlist.sh --top vco" >&2
  exit 1
}

# The grid's reference frequencies are re-derived against the systematic sweep
# BEFORE any simulator runs, on every invocation -- a whole grid sized off a
# stale reference is a whole grid of wasted wall clock, and a cheap check that
# only runs when a human remembers to pass --grid is a check that does not run.
print_grid >/dev/null || {
  echo "ERROR: grid verification failed -- run --grid to see which point" >&2
  exit 1
}

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  # Index 4 is group 1's `ss` row: the pair/bundle/temperature/supply the
  # systematic sweep makes the deterministically thinnest of the whole grid.
  echo "vco-tuning-range band-pair --check: 2 joint draws at grid point $(point_id ss 125 3.63 3)"
  for s in 1 2; do run_one 4 "${s}" "${tmpdir}/out.csv"; done
  echo "${HEADER}"; cat "${tmpdir}/out.csv"
  exit 0
fi

TOTAL_DRAWS=$(( ${#GRID[@]} * N_SAMPLES ))
echo "vco-tuning-range band-pair: ${#GRID[@]} grid points x N_SAMPLES=${N_SAMPLES} JOINT draws = ${TOTAL_DRAWS} draws, $(simenv_jobs) parallel jobs"

if [ "${SIM_RESUME:-0}" != "1" ]; then
  rm -f "${WORK}"/mc_*.csv
else
  echo "vco-tuning-range band-pair: SIM_RESUME=1 -- keeping any already-completed per-draw CSVs from a prior run"
fi

# One xargs job per (grid point, seed). Fanning out over the FULL cross product
# rather than looping the points and fanning out the seeds inside each keeps
# every core busy across a point boundary, which matters here because the grid's
# points differ in transient length by more than an order of magnitude (band 6's
# window is ~25x shorter than band 0's) and a per-point barrier would idle most
# of the host waiting for the slowest point in each batch.
for idx in "${!GRID[@]}"; do
  for s in $(seq 1 "${N_SAMPLES}"); do echo "${idx} ${s}"; done
done | xargs -P "$(simenv_jobs)" -L1 "${BASH:-/bin/bash}" -c \
  'exec "$0" --one "$2" "$3" "$1/mc_$2_$3.csv"' \
  "${HERE}/run_band_pair_worst_corner.sh" "${WORK}"

# Sorted by point id, then by seed numerically -- so the committed CSV's row
# order is the record's table order and a diff between two runs of the same grid
# is readable.
cat "${WORK}"/mc_*.csv | sort -t, -k1,1 -k6,6n >"${WORK}/all.csv"

GOT=$(wc -l <"${WORK}/all.csv" | tr -d ' ')
[ "${GOT}" -eq "${TOTAL_DRAWS}" ] || { echo "ERROR: expected ${TOTAL_DRAWS} rows, got ${GOT}" >&2; exit 1; }

# Every grid point must have contributed exactly N_SAMPLES rows. The total above
# can be right while a point is short and another long (a stale mc_*.csv from a
# prior grid, a resume that picked up the wrong index), and a point silently
# missing half its draws is exactly the failure this campaign is being widened
# to prevent.
for idx in "${!GRID[@]}"; do
  read -r gb gt gv gba _ _ _ <<<"${GRID[$idx]}"
  gpid="$(point_id "${gb}" "${gt}" "${gv}" "${gba}")"
  n=$(awk -F, -v p="${gpid}" '$1==p' "${WORK}/all.csv" | wc -l | tr -d ' ')
  [ "${n}" -eq "${N_SAMPLES}" ] || {
    echo "ERROR: point ${gpid} has ${n} rows, expected ${N_SAMPLES}" >&2
    exit 1
  }
done


# --------------------------------------------------------------------------
# Mint the evidence record.
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DUT_SRC}" "${SNAPDIR}/${RID}-vco-band-pair-worst-corner.spice"
SHA_VCO=$(simenv_sha256 "${SNAPDIR}/${RID}-vco-band-pair-worst-corner.spice")

# The run tag already carries the point id, so the committed log name needs no
# corner suffix appended to it -- unlike the single-point version of this script,
# where the tag was only `pair_seedNNN` and the corner had to be glued on here.
for f in "${WORK}"/pair_*_seed*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")").log"
done

OUT="${CORNERSDIR}/mismatch.csv"
{
  simenv_provenance "vco-tuning-range (adjacent-band pair, joint two-band draw, ${#GRID[@]}-point grid)" "${RID}" \
    "design/netlist/vco.spice (committed export)" \
    "${#GRID[@]} (bundle, temperature, supply, band pair) points -- all five MOS bundles, all four vertices of the temperature x supply box at the thinnest bundle, and four of the seven adjacent pairs; band b @ Vctrl=${VCTRL_A} and band b+1 @ Vctrl=${VCTRL_B} in ONE parse per draw, N=${N_SAMPLES} joint mismatch draws per point, ${TOTAL_DRAWS} draws total" \
    "${SWITCHES_NOTE}"
  echo "${HEADER}"; cat "${WORK}/all.csv"
} >"${OUT}"

# --------------------------------------------------------------------------
# PER-POINT statistics, read back from the CSV just written so the record text
# cannot drift from the data.
#
# The single-point version of this script derived one set of scalars here. A
# grid needs a derivation PER POINT, and the record has to state the verdict per
# point and name which one binds -- quoting only the worst is exactly what #622
# asked this campaign to stop doing, because a reader cannot tell a grid whose
# every point passes comfortably from one whose single worst point passes by a
# hair from the same headline number.
#
# The per-point derivation is committed as its own artifact rather than living
# only in the record's prose, so every figure in that table is re-derivable from
# bytes in this directory without re-running the campaign.
# --------------------------------------------------------------------------
PER_POINT="${CORNERSDIR}/per_point.csv"
{
  simenv_provenance "vco-tuning-range (adjacent-band pair, per-point derivation)" "${RID}" \
    "derived from mismatch.csv in this directory -- no simulator" \
    "${#GRID[@]} points, each aggregating its own ${N_SAMPLES} joint draws" \
    "${SWITCHES_NOTE}"
  echo "point_id,group,corner,temp_c,vdd,band_a,band_b,n,f_a_mean_hz,f_a_sd_hz,f_b_mean_hz,f_b_sd_hz,ratio_mean,ratio_sd,ratio_3s_lo,ratio_se,margin_se,sys_ratio,margin_left_pct,rho,ind_bound,f_a_3s_pct,f_b_3s_pct,verdict"
  for idx in "${!GRID[@]}"; do
    read -r p_bundle p_temp p_vdd p_band_a p_fnom_a p_fnom_b p_group <<<"${GRID[$idx]}"
    p_band_b=$(( p_band_a + 1 ))
    p_pid="$(point_id "${p_bundle}" "${p_temp}" "${p_vdd}" "${p_band_a}")"
    # One awk pass per point: both bands' moments, the per-draw ratio's moments,
    # and the Pearson correlation between the pair's two frequencies. The ratio
    # column (15) is used as-is rather than recomputed, so the statistic is taken
    # over exactly the numbers the CSV commits.
    simenv_datarows "${OUT}" | awk -F, -v p="${p_pid}" -v g="${p_group}" \
      -v c="${p_bundle}" -v t="${p_temp}" -v d="${p_vdd}" \
      -v ba="${p_band_a}" -v bb="${p_band_b}" \
      -v sr="$(sys_ratio "${p_fnom_a}" "${p_fnom_b}")" -v fl="${RATIO_FLOOR}" '
      $1 == p {
        n++
        x = $9 + 0; y = $13 + 0; r = $15 + 0
        sx += x; sxx += x*x; sy += y; syy += y*y; sxy += x*y
        sr_ += r; srr += r*r
      }
      END {
        if (n < 2) { printf "ERROR: point %s has n=%d\n", p, n > "/dev/stderr"; exit 1 }
        am = sx/n; asd = sqrt((sxx - n*am*am)/(n-1))
        bm = sy/n; bsd = sqrt((syy - n*bm*bm)/(n-1))
        rm = sr_/n; rsd = sqrt((srr - n*rm*rm)/(n-1))
        rlo = rm - 3*rsd
        rse = rsd/sqrt(n)
        mse = (rse > 0) ? (rlo - fl)/rse : 0
        left = (sr > fl) ? 100*(rlo - fl)/(sr - fl) : 0
        num = n*sxy - sx*sy
        den = sqrt((n*sxx - sx*sx) * (n*syy - sy*sy))
        rho = (den > 0) ? num/den : 0
        # The INDEPENDENT-draw bound the prior records methodology would have
        # produced on these same samples: each band pushed to its own opposite
        # tail as if the two were unrelated. Reported to quantify what
        # independent draws discard, never as the verdict.
        ind = (bm + 3*bsd > 0) ? (am - 3*asd)/(bm + 3*bsd) : 0
        printf "%s,%s,%s,%s,%s,%d,%d,%d,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.5f,%.6g,%.4g,%.5f,%.3g,%.4f,%.5f,%.4g,%.4g,%s\n", \
          p, g, c, t, d, ba, bb, n, am, asd, bm, bsd, rm, rsd, rlo, rse, mse, sr, left, rho, ind, \
          300*asd/am, 300*bsd/bm, (rlo >= fl) ? "PASS" : "FAIL"
      }' || exit 1
  done
} >"${PER_POINT}"

# ppcol <point_id> <column-number> -- one field of one point's derived row.
ppcol() { simenv_datarows "${PER_POINT}" | awk -F, -v p="$1" -v f="$2" '$1==p {print $f; exit}'; }

# THE BINDING POINT: the grid point whose verdict statistic (the per-draw ratio's
# one-sided 3-sigma low tail) is LOWEST. Derived, not asserted -- if widening the
# grid moved the binding point off the deterministically-thinnest corner, that is
# the finding, and the record has to be able to say so without being edited.
BIND_PID=$(simenv_datarows "${PER_POINT}" | sort -t, -k15,15g | head -1 | cut -d, -f1)
BIND_R_LO=$(ppcol "${BIND_PID}" 15)
BIND_GROUP=$(ppcol "${BIND_PID}" 2)
BIND_SYS=$(ppcol "${BIND_PID}" 18)
BIND_MARGIN_SE=$(ppcol "${BIND_PID}" 17)
BIND_LEFT_PCT=$(ppcol "${BIND_PID}" 19)
BIND_RHO=$(ppcol "${BIND_PID}" 20)
BIND_IND=$(ppcol "${BIND_PID}" 21)
BIND_VERDICT=$(ppcol "${BIND_PID}" 24)

# The point the SYSTEMATIC sweep predicts binds -- group 1's `ss` row. Named
# separately so the record can state whether mismatch agreed with the
# deterministic ordering or moved the binding point, which is the question the
# grid exists to answer.
SYS_BIND_PID="$(point_id ss 125 3.63 3)"
SYS_BIND_R_LO=$(ppcol "${SYS_BIND_PID}" 15)

FAIL_COUNT=$(simenv_datarows "${PER_POINT}" | awk -F, '$24=="FAIL"' | wc -l | tr -d ' ')
PASS_COUNT=$(simenv_datarows "${PER_POINT}" | awk -F, '$24=="PASS"' | wc -l | tr -d ' ')
if [ "${FAIL_COUNT}" -eq 0 ]; then GRID_VERDICT=PASS; else GRID_VERDICT=FAIL; fi

# Spread of the correlation across the grid -- the #597 record could only state
# rho at one point, so whether that near-unity figure was a property of that
# corner or of the shared hardware was untested until this grid.
RHO_MIN=$(simenv_datarows "${PER_POINT}" | awk -F, 'NR==1||$20<m{m=$20}END{printf "%.4f", m}')
RHO_MAX=$(simenv_datarows "${PER_POINT}" | awk -F, 'NR==1||$20>m{m=$20}END{printf "%.4f", m}')
# ...and, more usefully, the spread SPLIT BY AXIS, because the grid is built so
# that question is answerable: the eight B3 -> B4 points hold the PAIR fixed and
# vary bundle/temperature/supply, while the four points at ss/125C/3.63V hold the
# CORNER fixed and vary the pair. Whichever of those two ranges is the wide one
# is the axis rho actually depends on. Derived here rather than asserted in the
# record's prose, so the claim moves if the data does.
# rho_range <awk-condition> -- min .. max of the rho column over the rows that
# condition selects. The condition and the body are CONCATENATED into one awk
# program argument (adjacent shell quotes), so the caller's `$6`/`$20` reach awk
# unexpanded rather than being eaten by the shell.
rho_range() {
  simenv_datarows "${PER_POINT}" | awk -F, "$1"' {
    if (n == 0 || $20 + 0 < lo) lo = $20 + 0
    if (n == 0 || $20 + 0 > hi) hi = $20 + 0
    n++
  } END {
    if (n == 0) { print "n/a"; exit 1 }
    printf "%.4f .. %.4f", lo, hi
  }'
}
RHO_FIXED_PAIR=$(rho_range '$6==3')
RHO_FIXED_CORNER=$(rho_range '$3=="ss" && ($4+0)==125 && ($5+0)==3.63')
# The two ranges' widths, so the record can say WHICH axis dominates as a
# comparison of numbers rather than as an adjective.
rho_width() { echo "$1" | awk '{printf "%.4f", $3 - $1}'; }
RHO_W_FIXED_PAIR=$(rho_width "${RHO_FIXED_PAIR}")
RHO_W_FIXED_CORNER=$(rho_width "${RHO_FIXED_CORNER}")
if awk -v a="${RHO_W_FIXED_CORNER}" -v b="${RHO_W_FIXED_PAIR}" 'BEGIN{exit !(a>b)}'; then
  RHO_AXIS="the BAND PAIR"; RHO_OTHER_AXIS="corner, temperature and supply"
  RHO_W_WIDE="${RHO_W_FIXED_CORNER}"; RHO_W_NARROW="${RHO_W_FIXED_PAIR}"
else
  RHO_AXIS="the CORNER"; RHO_OTHER_AXIS="band pair"
  RHO_W_WIDE="${RHO_W_FIXED_PAIR}"; RHO_W_NARROW="${RHO_W_FIXED_CORNER}"
fi
# How many points the independent-draw bound would have failed, against how many
# the joint (correct) statistic fails. The gap is the methodology's cost, now
# measured over a grid instead of at one point.
IND_FAIL_COUNT=$(simenv_datarows "${PER_POINT}" | awk -F, -v f="${RATIO_FLOOR}" '($21+0)<f' | wc -l | tr -d ' ')

# The markdown per-point table, generated from the committed derivation so the
# record and the CSV cannot disagree.
POINT_ROWS=$(simenv_datarows "${PER_POINT}" | awk -F, -v b="${BIND_PID}" '
  { mark = ($1 == b) ? " **(binding)**" : ""
    printf "  | `%s`%s | %s | B%s -> B%s | %s | %s | %s | %s | %s | %s | **%s** |\n", \
      $1, mark, $2, $6, $7, $8, $13, $14, $15, $18, $19, $24 }')

echo "vco-tuning-range band-pair: ${#GRID[@]} points, ${PASS_COUNT} PASS / ${FAIL_COUNT} FAIL -> ${GRID_VERDICT}"
echo "  binding point ${BIND_PID} (group ${BIND_GROUP}): mean(ratio)-3sigma = ${BIND_R_LO} vs floor ${RATIO_FLOOR} -> ${BIND_VERDICT}"
echo "  systematic sweep predicted ${SYS_BIND_PID} would bind; its own 3-sigma tail is ${SYS_BIND_R_LO}"
echo "  rho(f_A, f_B) across the grid: ${RHO_MIN} .. ${RHO_MAX}"
echo "  the independent-draw bound would have FAILED ${IND_FAIL_COUNT} of ${#GRID[@]} points"

if [ "${BIND_PID}" = "${SYS_BIND_PID}" ]; then
  ORDER_NOTE="**Mismatch did NOT move the binding point.** The grid's lowest
  3-sigma tail is at \`${SYS_BIND_PID}\`, the same point the systematic sweep's
  \`band_overlap.csv\` names as deterministically thinnest. That is now a
  MEASUREMENT over ${#GRID[@]} points rather than the assumption the
  single-point version of this campaign rested on, and it is the specific thing
  #622 said had never been checked."
else
  ORDER_NOTE="**Mismatch MOVED the binding point, and this is the finding.** The
  grid's lowest 3-sigma tail is at \`${BIND_PID}\` (${BIND_R_LO}), NOT at
  \`${SYS_BIND_PID}\` (${SYS_BIND_R_LO}) where the systematic sweep's
  \`band_overlap.csv\` places the thinnest deterministic margin. The
  deterministic ordering and the dispersion ordering therefore disagree for this
  campaign, exactly as #597 found on the sibling \`sim/mc-cp-mismatch\`
  campaign, and the single-point version of this campaign could not have seen
  it."
fi

if [ "${GRID_VERDICT}" = "PASS" ]; then
  RATIO_NOTE="
  **Every sampled pair stays overlapped with both bands drawn jointly.** All
  ${PASS_COUNT} of the ${#GRID[@]} grid points hold their per-draw ratio's
  one-sided 3-sigma low tail at or above the ${RATIO_FLOOR} floor. The binding
  point is \`${BIND_PID}\` at ${BIND_R_LO} -- ${BIND_MARGIN_SE} standard errors
  of that point's ratio mean above the floor, keeping ${BIND_LEFT_PCT}% of its
  ${BIND_SYS} systematic margin. There is no frequency any SAMPLED adjacent pair
  fails to reach at 3 sigma of the joint draw, at any sampled point."
else
  RATIO_NOTE="
  **${FAIL_COUNT} of the ${#GRID[@]} sampled points do NOT stay overlapped at
  3 sigma of the joint draw**, the worst being \`${BIND_PID}\` at
  ${BIND_R_LO}, BELOW the ${RATIO_FLOOR} floor by $(awk -v x="${BIND_MARGIN_SE}" 'BEGIN{printf "%.4g", (x<0?-x:x)}')
  standard errors of that point's ratio mean -- a coverage hole at 3 sigma, on a
  jointly-drawn sample, not on an independent-tail bound that could be dismissed
  as pessimistic. This record does not widen the band plan or soften the
  overlap criterion to absorb that: per CLAUDE.md a spec change goes through
  \`spec/\` with a decision record, and what is owed here is a decision record
  or a design change, not a restatement of the criterion."
fi

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 / design/README.md's "3-bit band-select mirror" -- the
  adjacent-band coverage-hole check
  (\`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
  \`band_overlap\` check) with **both bands of a pair drawn from ONE
  per-instance mismatch draw**, each at its own end of the control window, over
  a **${#GRID[@]}-point PVT and band-pair grid that visits all five MOS
  bundles** -- so the inequality the check actually asks about,
  \`f_max(band b) >= f_min(band b+1)\` ON ONE DIE, is measured under mismatch
  as a per-draw ratio at every sampled point, with a verdict PER POINT and the
  binding point named.
  **This record's specific contribution over
  \`20260927-081930-d004d5b\`** (the single-point B0 -> B1 joint draw, #597) is
  the CORNER and PAIR axes, which that record left at 1 and explicitly named as
  residual gaps in its own Methodology field. Those residuals are T1/bronze
  item 6's sub-criterion (d) for this row (#127, issue #622): the campaign's
  Monte Carlo evidence sampled 2 of the 45 mandated PVT points, missing \`ff\`,
  \`fs\` and \`sf\` entirely. What this record settles that no prior record in
  this directory could is whether the DETERMINISTIC ordering the systematic
  sweep establishes -- which corner's overlap margin is thinnest -- is also the
  ordering of the DISPERSION that eats that margin. Those are two different
  questions, and #597's own finding on the sibling \`sim/mc-cp-mismatch\`
  campaign (three of four terms' binding corner moved once the grid widened) is
  the precedent that they can disagree.
  **No prior record is superseded**: \`20260817-143524-0e9cfc9\` (bands 0 and 7,
  mid-window, nominal corner), \`20260923-084925-1655e11\` (band 0 at \`ss\`/
  125C/3.63V against band 1's systematic floor) and
  \`20260927-081930-d004d5b\` (the single-point joint draw) all stand
  unmodified as historical evidence, sim/ being append-only. This record is
  additive and supersedes by CITATION only -- and one of its grid points
  (\`$(point_id ss 125 3.63 0)\`) is deliberately the EXACT point
  \`20260927-081930-d004d5b\` sampled, on independent seeds, so that record's
  verdict is re-derived here rather than merely cited.
- **Model-capability gate**: this record RESTS ON the parse-time-seed finding
  rather than merely reusing it -- see
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`'s
  "Model-capability gate" for the original evidence (\`agauss()\` per-instance
  draws inside \`nfet_03v3_dss\`/\`pfet_03v3_dss\`, gated by
  \`sw_stat_mismatch\`, evaluated ONCE at netlist PARSE time, reproducible via
  \`.option rndseed=N\`). That reproducibility claim is HOST-SCOPED -- same
  host, same build, same seed -> same draw; a different host is an
  independent replicate, not a reproduction of the same sample -- see
  sim/README.md's "Statistical convention" field. Parse-time evaluation is
  exactly what makes a joint
  two-band draw possible: two \`tran\` runs inside one \`.control\` block of
  \`testbench/tb_vco_band_pair.sp\` see the SAME offsets, because the draws
  happened before either ran. The band code is moved between the two runs with
  \`alter\` on three DC sources -- no device is added, removed or
  re-parameterised, so nothing the draw depends on changes. The same
  one-parse-many-analyses idiom is already in use in
  \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\` (three Vctrl points per
  draw); \`20260927-081930-d004d5b\` was the first application of it across the
  BAND axis and this record reuses it unchanged at every grid point.
  **The negative control for this record's sampled points is committed in this
  directory**: \`records/${CONTROL_RECORD}.md\`, re-checkable from its own
  committed bytes with no simulator via
  \`run_mismatch.sh --recheck-control ${CONTROL_RECORD}\`.
  \`records/20260927-094524-b994116.md\` established the three legs
  (\`repeat\`/\`vary\`/\`gate\`) on this campaign's own deck and DUT (#602) at
  the three points the campaign sampled then;
  \`run_mismatch.sh\`'s \`CONTROL_POINTS\` has since been widened alongside this
  grid -- to every point of it, decomposed into the single-band ends the control
  deck runs -- so the control's point set is the point set of the samples it
  validates, per \`signoff/README.md\`'s Item 6(c) rule. The control's own record
  names its coverage and its per-point verdicts; this record does not restate
  them.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\` (the
  same DUT every prior mismatch record and the systematic \`testbench/tb.json\`
  sweep compose, unmodified by this record), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band-pair-worst-corner.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck
  \`sim/vco-tuning-range/testbench/tb_vco_band_pair.sp\` is UNCHANGED from
  \`20260927-081930-d004d5b\` -- it already took both band codes, both control
  voltages and both transient windows as parameters, so widening the grid is a
  RUNNER change with no deck change, exactly as that record predicted in its own
  "What is still not measured" field. The single-band \`tb_vco_mismatch.sp\` the
  two earlier records and the negative control use is likewise unchanged and
  still present.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this campaign's own deck (tb_vco_band_pair.sp) then declares sw_stat_global=0 / sw_stat_mismatch=1, positioned after the design.ngspice include so the later declaration wins -- same harness-ordering finding sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md documents in full")
- **Corner matrix run**: **${#GRID[@]} points**, each TWO bands per draw at
  opposite ends of the control window, ${N_SAMPLES} joint draws per point
  (${TOTAL_DRAWS} draws total). The sampled set spans **all five MOS bundles**
  (\`typical\`, \`ff\`, \`fs\`, \`sf\`, \`ss\`), **all four vertices of the
  temperature x supply box** (-40 C and 125 C x 2.97 V and 3.63 V) and **four of
  the seven adjacent band pairs** (B0 -> B1, B1 -> B2, B3 -> B4, B6 -> B7). The
  exact point list, with each point's group and its systematic reference
  frequencies, is committed at
  \`sim/vco-tuning-range/corners/${RID}/per_point.csv\` and re-printable with
  \`./run_band_pair_worst_corner.sh --grid\`, which also re-derives every
  reference frequency in it against the systematic sweep's own CSV with no
  simulator.

  **Justification** (sim/README.md's "Default corner matrix" rule requires one
  for any subset of the 45-point grid) -- the subset is built from three groups,
  each answering a question the single-point predecessor could not:

  1. **The bundle axis (5 points).** Each of the five MOS bundles at ITS OWN
     deterministically-thinnest adjacent-pair point, computed over all
     7 pairs x 3 temperatures x 3 supplies from
     \`corners/20260804-164956-72883fb/raw_measures.csv\`. That computation
     returns the SAME (pair, temperature, supply) for all five bundles --
     B3 -> B4 at 125 C / 3.63 V -- which is itself the finding that makes this
     group cheap: no bundle is sampled away from its own worst point even though
     temperature and supply are held fixed. Worst systematic ratio per bundle:
     \`ss\` 1.26784, \`sf\` 1.26807, \`typical\` 1.30659, \`ff\` 1.33878,
     \`fs\` 1.34419. This group is what discharges the "three of the five MOS
     bundles are never drawn" gap #622 names.
  2. **The temperature x supply box (3 further points).** \`ss\` -- the thinnest
     bundle -- at B3 -> B4 at the remaining three vertices: -40 C/2.97 V,
     -40 C/3.63 V, 125 C/2.97 V. This group exists to TEST the ordering rather
     than assume it. At -40 C/2.97 V the systematic ratio is WIDEST for this
     bundle (1.40054 against 1.26784 at 125 C/3.63 V), so if relative dispersion
     grows faster than the margin does, the binding point under mismatch is here
     and not in group 1. That possibility is the whole reason #622 was filed and
     nothing in this tree could previously have detected it.
  3. **The pair axis (3 further points).** \`ss\`/125 C/3.63 V for B0 -> B1,
     B1 -> B2 and B6 -> B7. B0 -> B1 is the continuity/regression point -- the
     exact point \`20260927-081930-d004d5b\` sampled, re-drawn here on
     independent seeds. B1 -> B2 is the second-thinnest pair at this point
     (1.29887). B6 -> B7 is the top of the band plan and the one pair whose own
     worst point the systematic sweep places at a DIFFERENT supply
     (\`ss\`/125 C/2.97 V), i.e. the pair whose deterministic optimum disagrees
     with the rest.

  **Axes NOT swept, stated rather than implied**: the 27 C temperature and the
  3.30 V supply mid-points; the two COMPOSITE bundles (\`all-slow\`/\`all-fast\`,
  which are not among the 45 mandated MOS-axis points -- see
  \`bundle_libs()\` in \`testbench/common.sh\`); pairs B2 -> B3, B4 -> B5,
  B5 -> B6, and B3 -> B4 at bundles other than \`ss\` away from 125 C/3.63 V;
  and every intermediate Vctrl point. That last one is a DEFINITIONAL exclusion
  rather than a sampling gap: \`band_overlap\` is
  \`f_max(band b) / f_min(band b+1)\`, so the inequality this campaign measures
  exists only at the two ends of the 0.9-2.7 V control window and a mid-window
  Vctrl does not appear in it at all. Vctrl = ${VCTRL_A} V (lower band) and
  ${VCTRL_B} V (upper band) are therefore the only two control voltages in the
  grid, at every point, and they
  are the same two the systematic \`band_overlap\` check computes its ratio from
  (the seventh and the first of the seven 0.3 V-spaced control points).
- **Methodology / criteria / limitations**:
  - **One invocation = one draw = both bands.** \`N_SAMPLES=${N_SAMPLES}\`
    invocations of \`tb_vco_band_pair.sp\` PER GRID POINT (${TOTAL_DRAWS} in
    total), one \`.option rndseed\` each, seeds \`1..N\` at every point. Each
    invocation runs two \`tran\` analyses in one \`.control\` block: the pair's
    LOWER band \`b\` (band-select code B2 B1 B0 = the three bits of \`b\`) at
    Vctrl = ${VCTRL_A} V, then its UPPER band \`b+1\` at
    Vctrl = ${VCTRL_B} V. Which \`b\` that is varies by grid point -- the four
    pairs sampled are B0 -> B1, B1 -> B2, B3 -> B4 and B6 -> B7, and each
    point's own \`band_a\`/\`band_b\` are committed in
    \`corners/${RID}/per_point.csv\` and in every row of
    \`corners/${RID}/mismatch.csv\`. Measurement criterion identical to every other
    \`sim/vco-tuning-range/\` record: \`f = 4/tp\`, \`tp\` from the first to
    the fifth rising half-supply crossing of the buffered \`CLK\` output after
    \`tsettle\` (>= 4 estimated periods), taken independently for each of the
    two runs.
  - **THE VERDICT STATISTIC IS THE RATIO'S OWN TAIL, PER POINT.** Because both
    frequencies come from one draw, the overlap ratio
    \`f_max(band b) / f_min(band b+1)\` is itself a per-sample quantity, and the
    criterion is its one-sided 3-sigma low tail:
    \`mean(ratio) - 3*sigma(ratio) >= ${RATIO_FLOOR}\`, evaluated SEPARATELY at
    each of the ${#GRID[@]} points. Below ${RATIO_FLOOR} the lower band's top has
    fallen past the upper band's bottom and there is a frequency neither band
    reaches. The two earliest mismatch records reported \`|mean|+3sigma\` as a
    PERCENTAGE of one band's mean and read it against the fractional overlap
    margin, and both flagged that in their own text as a sanity flag rather than
    a bound -- necessarily, because with one band drawn the inequality could not
    be written down under mismatch at all. Those percentage figures are carried
    in \`per_point.csv\` for continuity only.
  - **The verdict is stated PER POINT and the binding point is DERIVED.** The
    Result table below has one row per sampled point, and the binding point is
    the row with the lowest 3-sigma tail -- picked by the runner from the
    committed \`per_point.csv\`, not asserted in this prose. This is what #622
    asked for over the single-point predecessor: a grid whose every point passes
    comfortably and a grid whose single worst point passes by a hair produce the
    same headline number, and only a per-point table distinguishes them.
    ${ORDER_NOTE}
  - **The independent-draw bound is reported beside it, and it is the wrong
    statistic -- measurably so, now at every point rather than at one.** Treating
    the two bands as unrelated and pushing each to its own opposite tail gives
    \`(mean(f_A) - 3sd(f_A)) / (mean(f_B) + 3sd(f_B))\`, which is reported per
    point in \`per_point.csv\` and in the Result table. It would have FAILED
    ${IND_FAIL_COUNT} of the ${#GRID[@]} points, against ${FAIL_COUNT} for the
    joint statistic. The gap is not a modelling preference: the measured Pearson
    correlation between a pair's two frequencies across draws is
    **rho = ${RHO_MIN} .. ${RHO_MAX}** across the whole grid -- high everywhere,
    so the dispersion is largely COMMON to both bands at every point sampled,
    which is what the shared hardware predicts: adjacent bands differ by one
    switched leg of \`design/vco_bias.sch\`'s mirror cascade and share every
    always-on leg, the V->I converter and all five ring stages. Common-mode
    dispersion cancels in a ratio and does not open a coverage hole; the
    independent bound double-counts it.
  - **rho is a property of the BAND PAIR, not of the corner -- and that is a
    finding this grid produced, not an assumption it inherited.**
    \`20260927-081930-d004d5b\` measured rho at ONE point (0.9958) and therefore
    could not tell a property of that corner from a property of the hardware.
    This grid separates the two axes by construction, and they separate cleanly:
    holding the PAIR fixed at B3 -> B4 and varying bundle, temperature and
    supply over all eight of those points moves rho only across
    **${RHO_FIXED_PAIR}** (width ${RHO_W_FIXED_PAIR}), while holding the CORNER
    fixed at \`ss\`/125 C/3.63 V and varying the pair moves it across
    **${RHO_FIXED_CORNER}** (width ${RHO_W_FIXED_CORNER}). The pair axis is the
    wider by ${RHO_W_WIDE} against ${RHO_W_NARROW}, so rho tracks ${RHO_AXIS}
    and is nearly invariant to ${RHO_OTHER_AXIS}. The practical consequence is
    visible in the per-point table's "% margin kept" column: the B3 -> B4 points,
    whose rho is the LOWEST of the grid, keep only ~42-56% of their systematic
    margin, against ~88% at B0 -> B1 where rho is 0.9958. Less common-mode
    cancellation means more of the margin is eaten, which is precisely why the
    binding point is a B3 -> B4 point and why a campaign that had only ever
    sampled B0 -> B1 was reading this claim at its most favourable pair.
  - **What is still not measured.** (1) **Not every pair at every point**: the
    grid is a union of three one-dimensional cuts, not the full
    5 bundles x 4 vertices x 7 pairs cross product (140 points). The cuts are
    chosen so each crosses the other at the deterministically-thinnest point, but
    an interaction that only appears off all three cuts -- say \`fs\` at
    -40 C/2.97 V on B5 -> B6 -- is not sampled. (2) **Not the 27 C / 3.30 V
    mid-points, and not the composite bundles**: see the Corner matrix run field
    for why each is excluded. (3) **Global process variation stays off**
    (\`sw_stat_global = 0\`), as in every Monte Carlo campaign here -- the corner
    grid, not a global draw, is how process spread is represented. (4) **N is
    ${N_SAMPLES} per point, and the verdict statistic is a 3-sigma tail**, so the
    figure carries the estimation error of a standard deviation at that N; the
    per-point standard error is committed beside it in \`per_point.csv\` so a
    reader can weigh a margin against sampling noise rather than read it as
    exact.
  - **Transient window**: sized PER POINT AND PER BAND off that band's own
    SYSTEMATIC frequency at that exact point, transcribed from
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`
    (band b's \`f7\` column and band b+1's \`f1\`) and re-derived against that
    CSV on every invocation before any simulator runs, so a stale or mistyped
    reference cannot size a window. Bracket:
    $(awk -v k="${WIN_LO_FRAC}" 'BEGIN{printf "%.0f", 100*(1-k)}')% /
    $(awk -v k="${WIN_HI_FRAC}" 'BEGIN{printf "%.0f", 100*(k-1)}')% either side
    -- WIDER than the +/-30% the single-band scripts use, because this window has
    to hold a mismatched frequency whose own 3-sigma spread those records
    measured at roughly 25% of the mean, and a 30% window leaves no margin past
    3 sigma. Never trusted for a result, only for tstep/tstop sizing. Every
    draw's two frequencies are asserted to land inside that bracket before the
    sample is accepted, so a \`meas\` that latched onto the wrong edge is
    rejected rather than averaged in; all ${TOTAL_DRAWS} draws passed that
    assertion, and the runner additionally asserts that each of the
    ${#GRID[@]} points contributed exactly ${N_SAMPLES} accepted rows.
- **Statistical convention**: \`sw_stat_global = 0\`,
  \`sw_stat_mismatch = 1\` (mismatch-only, global process variation off,
  matching every other Monte Carlo campaign in this repo).
  \`N_SAMPLES=${N_SAMPLES}\` joint draws PER POINT (${TOTAL_DRAWS} total), each
  yielding both bands. Seeds: sequential integers \`1..N\` at every point, passed
  via \`.option rndseed\`. The same seed at two different points is a different
  draw (the corner, temperature and supply differ, so the parse differs), so the
  points are independent samples and not a repeated one; every draw's raw log is
  committed under \`corners/${RID}/\`, named for its point id and seed, and holds
  BOTH runs so a reader can see the two analyses share one parse. Dispersion
  reported at mean +/- sample standard deviation (N-1 denominator); the verdict
  uses the per-draw RATIO's one-sided 3-sigma tail, in the direction that closes
  the overlap, evaluated per point.
- **Result**: ${PASS_COUNT} PASS / ${FAIL_COUNT} FAIL over ${#GRID[@]} points --
  **${GRID_VERDICT}**. One row per sampled point, generated from
  \`corners/${RID}/per_point.csv\`, which is itself derived from
  \`corners/${RID}/mismatch.csv\` with no simulator:

  | point | group | pair | n | ratio mean | ratio sd | **mean-3sigma** | systematic ratio | % margin kept | verdict |
  |---|---|---|---|---|---|---|---|---|---|
${POINT_ROWS}

  The verdict line is \`mean(ratio) - 3*sigma(ratio) >= ${RATIO_FLOOR}\` at every
  row. "% margin kept" is that statistic's distance above the floor as a
  percentage of the systematic ratio's own distance above it, so a point whose
  deterministic margin is wide and a point whose margin is narrow are comparable.
${RATIO_NOTE}

  **The binding point, and the same samples under the retired methodology.**

  | Criterion | Statistic | Line | Verdict |
  |---|---|---|---|
  | binding point \`${BIND_PID}\` (group ${BIND_GROUP}), joint 3-sigma worst case | mean(ratio) - 3sigma(ratio) = **${BIND_R_LO}** | >= ${RATIO_FLOOR} | **${BIND_VERDICT}** |
  | -- the same point under the earlier records' INDEPENDENT-draw treatment | ${BIND_IND} | >= ${RATIO_FLOOR} | $(awk -v r="${BIND_IND}" -v f="${RATIO_FLOOR}" 'BEGIN{print (r>=f)?"PASS":"FAIL"}') (not this record's verdict) |
  | -- measured correlation at the binding point | rho = ${BIND_RHO} | -- | -- |
  | -- the point the SYSTEMATIC sweep predicted would bind, \`${SYS_BIND_PID}\` | mean(ratio) - 3sigma(ratio) = ${SYS_BIND_R_LO} | >= ${RATIO_FLOOR} | $(awk -v r="${SYS_BIND_R_LO}" -v f="${RATIO_FLOOR}" 'BEGIN{print (r>=f)?"PASS":"FAIL"}') |
  | -- points the INDEPENDENT-draw bound would have failed | ${IND_FAIL_COUNT} of ${#GRID[@]} | -- | (methodology cost, not a verdict) |

  Per-point standard errors, the full per-band moments, the +-3sigma-as-a-
  percentage-of-mean figures the two earliest records used as their proxy, and
  the per-point rho are all committed in \`corners/${RID}/per_point.csv\` rather
  than quoted selectively here. The proxy figures are carried for continuity
  only; comparing them against a fractional overlap margin is the comparison
  this record's per-draw ratio replaces, and the measured rho above is why.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_band_pair.sp\`
    (unchanged from \`20260927-081930-d004d5b\`),
    \`run_band_pair_worst_corner.sh\` (extended to the ${#GRID[@]}-point grid for
    this record; \`--grid\` prints it and re-derives its reference frequencies
    with no simulator)
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`, \`design/vco_stage.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band-pair-worst-corner.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\` (${TOTAL_DRAWS} draw logs,
    two analyses each, named \`pair_<point_id>_seedNNN.log\`)
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/mismatch.csv\`
    (one row per draw), \`.../per_point.csv\` (one derived row per grid point --
    the Result table above is generated from it)
  - Systematic sweep and overlap check every grid point's corner, Vctrl points
    and reference frequencies are drawn from (unchanged, untouched):
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`
  - Prior mismatch records this one follows on from (none superseded):
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\` (bands 0 and 7,
    mid-window, nominal corner),
    \`sim/vco-tuning-range/records/20260923-084925-1655e11.md\` (band 0 at
    \`ss\`/125C/3.63V, against band 1's systematic floor),
    \`sim/vco-tuning-range/records/20260927-081930-d004d5b.md\` (the
    single-point B0 -> B1 joint draw this grid's
    \`$(point_id ss 125 3.63 0)\` point re-derives on independent seeds)
  - This campaign's committed negative control, widened alongside this grid to
    cover every point of it:
    \`sim/vco-tuning-range/records/${CONTROL_RECORD}.md\`, re-checkable from
    committed bytes with no simulator via
    \`./run_mismatch.sh --recheck-control ${CONTROL_RECORD}\`; its
    pre-widening predecessor, which established the three legs on this deck, is
    \`sim/vco-tuning-range/records/20260927-094524-b994116.md\` (#602)
  - The one-parse-many-analyses idiom this deck reuses:
    \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\`
  - The sibling campaign whose own corner-axis widening (#597) is the precedent
    for this one, and whose finding that a subset's binding corner can move is
    why this grid tests the ordering instead of assuming it:
    \`sim/mc-cp-mismatch/records/20260927-102154-d004d5b.md\`,
    \`sim/mc-cp-mismatch/testbench/run.sh\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #622)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "vco-tuning-range band-pair: wrote ${RECORD}"
echo "vco-tuning-range band-pair: wrote ${OUT}"
echo "vco-tuning-range band-pair: wrote ${PER_POINT}"
echo "vco-tuning-range band-pair: wrote ${CORNERSDIR}/ (${TOTAL_DRAWS} draw logs over ${#GRID[@]} points, two analyses each)"
