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
# Not a supersession of either prior record. `20260817-143524-0e9cfc9` (bands 0
# and 7, mid-window, nominal corner) and `20260923-084925-1655e11` (band 0, its
# own worst corner and Vctrl) both stand unmodified as historical evidence --
# sim/ is append-only. This record is additive, and it does not widen the
# CORNER axis: one corner, the pair's own worst, which is where the margin
# binds and is already identified by the systematic 45-point sweep. The axis it
# widens is the band axis, which is the one #597 found at 1. The sibling
# `sim/mc-cp-mismatch` campaign is where #597 widens the corner axis.
#
# Also not a check of any other adjacent pair. B0 -> B1 is the pair band 0's
# own coverage-hole risk lives on; the worst ratio across ALL SEVEN pairs
# belongs to B3 -> B4 (1.268 at the same corner) and is unmeasured under
# mismatch. The deck takes both bands' codes as parameters, so extending to
# another pair is a runner change and no deck change -- but it is not done
# here, and is stated as a residual gap rather than implied to be covered.
#
# Usage:
#   ./run_band_pair_worst_corner.sh          # full campaign -> mints records/<id>.md
#   ./run_band_pair_worst_corner.sh --check  # 2 draws, to stdout
#   N_SAMPLES=.. ./run_band_pair_worst_corner.sh   # draw count (default 200)

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
simenv_apply_omp_pin

DECK="${HERE}/tb_vco_band_pair.sp"
DUT_SRC="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-band-pair-worst-corner"

# Corner -- see header comment for the full derivation/verification.
CORNER="ss,res_typical,moscap_typical"
CORNER_TAG=ss
TEMP=125
VDD=3.63

# The pair. Band A is the LOWER band, measured at the TOP of its control window
# (its f_max); band B is the UPPER band, measured at the BOTTOM (its f_min).
BAND_A=0
BAND_B=1
VCTRL_A=2.7
VCTRL_B=0.9
# Systematic (sw_stat_mismatch=0) reference frequency at each of those exact
# points, read directly from
# sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv
# (corner=ss, temp_c=125.0, vdd=3.63; band0's f7 and band1's f1).
FNOM_A=9122300
FNOM_B=6917000

# Transient-window margin on those systematic frequencies. WIDER than the
# +/-30% the single-band scripts use, because this deck's window has to hold a
# MISMATCHED frequency whose own 3-sigma spread those records measured at
# ~25% of the mean -- a 30% window leaves essentially no margin past 3 sigma
# and would start losing samples to a `meas` that cannot find its fifth rising
# edge. The window is never trusted for a result, only for tstep/tstop sizing,
# so widening it costs wall clock and nothing else.
WIN_LO_FRAC=0.55
WIN_HI_FRAC=1.45

# The systematic ratio those two reference figures give -- `band_overlap.csv`'s
# B0 -> B1 row for this corner reads 1.319; this is that figure recomputed
# unrounded from its own two operands, so the record states both and a reader
# can see they agree.
SYS_RATIO=$(awk -v a="${FNOM_A}" -v b="${FNOM_B}" 'BEGIN{printf "%.5f", a/b}')
# Hole-free means the ratio stays >= this. 1.0 is not a tuning knob: at exactly
# 1.0 the lower band's top and the upper band's bottom meet, and below it there
# is a frequency neither band reaches.
RATIO_FLOOR=1.0

N_SAMPLES="${N_SAMPLES:-200}"

HEADER="seed,band_a,vctrl_a_v,f_a_hz,i_a_a,band_b,vctrl_b_v,f_b_hz,i_b_a,ratio"

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
run_one() {
  local seed="$1" sfile="$2"
  local tag="pair_seed$(printf '%03d' "${seed}")"
  stage_netlist "${WORK}/${tag}"
  local ts0 tstop0 tmax0 ts1 tstop1 tmax1
  read -r ts0 tstop0 tmax0 <<<"$(window_for "${FNOM_A}")"
  read -r ts1 tstop1 tmax1 <<<"$(window_for "${FNOM_B}")"
  local a0 a1 a2 b0 b1 b2
  a0=$(( BAND_A & 1 )); a1=$(( (BAND_A >> 1) & 1 )); a2=$(( (BAND_A >> 2) & 1 ))
  b0=$(( BAND_B & 1 )); b1=$(( (BAND_B >> 1) & 1 )); b2=$(( (BAND_B >> 2) & 1 ))
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl0=${VCTRL_A}" "vctrl1=${VCTRL_B}" \
    "b0c0=${a0}" "b1c0=${a1}" "b2c0=${a2}" \
    "b0c1=${b0}" "b1c1=${b1}" "b2c1=${b2}" \
    "ts0=${ts0}" "tstop0=${tstop0}" "tmax0=${tmax0}" \
    "ts1=${ts1}" "tstop1=${tstop1}" "tmax1=${tmax1}" \
    "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" la lb fa ia fb ib
  la=$(grep "^MCVCOPAIR_A " "${log}" | tail -1)
  lb=$(grep "^MCVCOPAIR_B " "${log}" | tail -1)
  [ -n "${la}" ] && [ -n "${lb}" ] || {
    echo "ERROR: missing MCVCOPAIR_A/_B for seed=${seed} (see ${log})" >&2
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
  awk -v fa="${fa}" -v fb="${fb}" -v na="${FNOM_A}" -v nb="${FNOM_B}" \
      -v lo="${WIN_LO_FRAC}" -v hi="${WIN_HI_FRAC}" -v s="${seed}" '
    BEGIN {
      bad = 0
      if (fa+0 < na*lo || fa+0 > na*hi) { printf "ERROR: seed %s band A f=%g outside window bracket [%g, %g]\n", s, fa, na*lo, na*hi > "/dev/stderr"; bad = 1 }
      if (fb+0 < nb*lo || fb+0 > nb*hi) { printf "ERROR: seed %s band B f=%g outside window bracket [%g, %g]\n", s, fb, nb*lo, nb*hi > "/dev/stderr"; bad = 1 }
      exit bad
    }'
  awk -v s="${seed}" -v ba="${BAND_A}" -v va="${VCTRL_A}" -v fa="${fa}" -v ia="${ia}" \
      -v bb="${BAND_B}" -v vb="${VCTRL_B}" -v fb="${fb}" -v ib="${ib}" \
    'BEGIN { printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%.6f\n", s, ba, va, fa, ia, bb, vb, fb, ib, fa/fb }' >>"${sfile}"
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
if [ "${SIM_RESUME:-0}" = "1" ] && [ "${1:-}" = "--one" ] && [ -n "${3:-}" ] && [ -s "${3}" ]; then
  echo "vco-tuning-range band-pair: SIM_RESUME=1 -- ${3} already present, skipping" >&2
  exit 0
fi
case "${1:-}" in
  --one)
    shift
    run_one "$@"
    exit 0
    ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

[ -f "${DUT_SRC}" ] || {
  echo "ERROR: ${DUT_SRC} missing -- run design/netlist.sh --top vco" >&2
  exit 1
}

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "vco-tuning-range band-pair --check: 2 joint draws at ${CORNER_TAG}/${TEMP}C/${VDD}V (band ${BAND_A} @ Vctrl=${VCTRL_A}, band ${BAND_B} @ Vctrl=${VCTRL_B})"
  for s in 1 2; do run_one "${s}" "${tmpdir}/out.csv"; done
  echo "${HEADER}"; cat "${tmpdir}/out.csv"
  exit 0
fi

echo "vco-tuning-range band-pair: N_SAMPLES=${N_SAMPLES} JOINT draws (band ${BAND_A} @ Vctrl=${VCTRL_A} and band ${BAND_B} @ Vctrl=${VCTRL_B} per draw) at ${CORNER_TAG}/${TEMP}C/${VDD}V, $(simenv_jobs) parallel jobs"

if [ "${SIM_RESUME:-0}" != "1" ]; then
  rm -f "${WORK}"/mc_*.csv
else
  echo "vco-tuning-range band-pair: SIM_RESUME=1 -- keeping any already-completed per-draw CSVs from a prior run"
fi

seq 1 "${N_SAMPLES}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run_band_pair_worst_corner.sh\" --one {} \"${WORK}/mc_{}.csv\""

cat "${WORK}"/mc_*.csv | sort -t, -k1,1n >"${WORK}/all.csv"

GOT=$(wc -l <"${WORK}/all.csv" | tr -d ' ')
[ "${GOT}" -eq "${N_SAMPLES}" ] || { echo "ERROR: expected ${N_SAMPLES} rows, got ${GOT}" >&2; exit 1; }

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

for f in "${WORK}"/pair_seed*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")")_${CORNER_TAG}_${TEMP}c_${VDD}v.log"
done

OUT="${CORNERSDIR}/mismatch.csv"
{
  simenv_provenance "vco-tuning-range (B${BAND_A}->B${BAND_B} pair, joint two-band draw)" "${RID}" \
    "design/netlist/vco.spice (committed export)" \
    "${CORNER_TAG}/${TEMP}C/${VDD}V, band ${BAND_A} @ Vctrl=${VCTRL_A} and band ${BAND_B} @ Vctrl=${VCTRL_B} in ONE parse per draw, N=${N_SAMPLES} joint mismatch draws"
  echo "${HEADER}"; cat "${WORK}/all.csv"
} >"${OUT}"

# Statistics, read back from the CSV just written so the record text cannot
# drift from the data.
col_stats() { simenv_datarows "${OUT}" | awk -F, -v f="$1" '{print $f}' | simenv_stats_from_values; }

A=$(col_stats 4)
A_M=$(echo "${A}" | awk '{print $1}'); A_SD=$(echo "${A}" | awk '{print $2}'); A_N=$(echo "${A}" | awk '{print $3}')
B=$(col_stats 8)
B_M=$(echo "${B}" | awk '{print $1}'); B_SD=$(echo "${B}" | awk '{print $2}')
R=$(col_stats 10)
R_M=$(echo "${R}" | awk '{print $1}'); R_SD=$(echo "${R}" | awk '{print $2}'); R_N=$(echo "${R}" | awk '{print $3}')

# THE VERDICT STATISTIC: the ratio distribution's own one-sided 3-sigma tail,
# in the direction the coverage hole opens.
R_LO=$(awk -v m="${R_M}" -v s="${R_SD}" 'BEGIN{printf "%.5f", m - 3*s}')
R_VERDICT=$(awk -v r="${R_LO}" -v f="${RATIO_FLOOR}" 'BEGIN{print (r>=f)?"PASS":"FAIL"}')
R_SE=$(awk -v s="${R_SD}" -v n="${R_N}" 'BEGIN{printf "%.6g", (n>0)? s/sqrt(n) : 0}')
# How many standard errors of the ratio's mean separate the verdict statistic
# from the floor -- so an exceedance can be told from sampling noise.
R_MARGIN_SE=$(awk -v r="${R_LO}" -v f="${RATIO_FLOOR}" -v se="${R_SE}" 'BEGIN{printf "%.4g", (se>0)? (r-f)/se : 0}')
# Fraction of the systematic overlap margin the mismatch draw consumes.
R_MARGIN_LEFT_PCT=$(awk -v w="${R_LO}" -v s="${SYS_RATIO}" -v f="${RATIO_FLOOR}" \
  'BEGIN{printf "%.3g", 100*(w-f)/(s-f)}')

# The INDEPENDENT-draw bound the same samples would have produced under the
# prior records' methodology: each band pushed to its own opposite tail as if
# the two were unrelated. Reported to quantify what independent draws discard,
# not as a verdict.
IND_A_LO=$(awk -v m="${A_M}" -v s="${A_SD}" 'BEGIN{printf "%.6g", m - 3*s}')
IND_B_HI=$(awk -v m="${B_M}" -v s="${B_SD}" 'BEGIN{printf "%.6g", m + 3*s}')
IND_RATIO=$(awk -v a="${IND_A_LO}" -v b="${IND_B_HI}" 'BEGIN{printf "%.5f", a/b}')
IND_VERDICT=$(awk -v r="${IND_RATIO}" -v f="${RATIO_FLOOR}" 'BEGIN{print (r>=f)?"PASS":"FAIL"}')

# Measured Pearson correlation between the pair's two frequencies across
# draws. This is the number that says HOW MUCH of each band's dispersion is
# common to both -- i.e. why the independent bound above is the wrong
# statistic, as a measurement rather than as an argument.
RHO=$(simenv_datarows "${OUT}" | awk -F, '
  { n++; x=$4+0; y=$8+0; sx+=x; sy+=y; sxx+=x*x; syy+=y*y; sxy+=x*y }
  END {
    if (n < 2) { print "0"; exit }
    num = n*sxy - sx*sy
    den = sqrt((n*sxx - sx*sx) * (n*syy - sy*sy))
    printf "%.4f", (den > 0) ? num/den : 0
  }')

# The prior records' proxy figure, for continuity: +-3sigma as a percentage of
# the mean, per band. Not this record's verdict.
pct3s() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.4g", 300*s/m}'; }
A_3SPCT=$(pct3s "${A_M}" "${A_SD}")
B_3SPCT=$(pct3s "${B_M}" "${B_SD}")
SYS_MARGIN_PCT=$(awk -v s="${SYS_RATIO}" 'BEGIN{printf "%.2f", 100*(s-1)}')

echo "band ${BAND_A} f (Vctrl=${VCTRL_A}): mean=${A_M} Hz sd=${A_SD} Hz (+-3sigma = ${A_3SPCT}% of mean, n=${A_N})"
echo "band ${BAND_B} f (Vctrl=${VCTRL_B}): mean=${B_M} Hz sd=${B_SD} Hz (+-3sigma = ${B_3SPCT}% of mean)"
echo "JOINT per-draw ratio f_A/f_B: mean=${R_M} sd=${R_SD} (n=${R_N}), mean-3sigma = ${R_LO} vs floor ${RATIO_FLOOR}: ${R_VERDICT}"
echo "  measured correlation rho(f_A, f_B) across draws = ${RHO}"
echo "  independent-draw bound on the SAME samples: ${IND_A_LO} / ${IND_B_HI} = ${IND_RATIO} (${IND_VERDICT}) -- reported for contrast, not the verdict"
echo "  systematic ratio ${SYS_RATIO}; the joint 3-sigma worst case keeps ${R_MARGIN_LEFT_PCT}% of that margin, ${R_MARGIN_SE} SE of the ratio's mean above the floor"

if [ "${R_VERDICT}" = "PASS" ]; then
  RATIO_NOTE="
  **The pair stays overlapped with both bands drawn jointly.** The per-draw
  ratio's own 3-sigma low tail is ${R_LO} against the ${RATIO_FLOOR} floor --
  ${R_MARGIN_SE} standard errors of the ratio's mean above it, keeping
  ${R_MARGIN_LEFT_PCT}% of the ${SYS_RATIO} systematic margin. There is no
  frequency the B${BAND_A}/B${BAND_B} pair fails to reach at this corner at
  3 sigma of the joint draw."
else
  RATIO_NOTE="
  **The pair does NOT stay overlapped at 3 sigma of the joint draw.** The
  per-draw ratio's 3-sigma low tail is ${R_LO}, BELOW the ${RATIO_FLOOR} floor
  by $(awk -v x="${R_MARGIN_SE}" 'BEGIN{printf "%.4g", (x<0?-x:x)}') standard
  errors of the ratio's mean -- a coverage hole at this corner at 3 sigma, on a
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
  B${BAND_A} -> B${BAND_B} adjacent-band pair's coverage-hole check
  (\`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
  \`band_overlap\` check, worst ratio 1.319 at \`ss\`/125C/3.63V) with **both
  bands drawn from ONE per-instance mismatch draw** at that corner, each at its
  own end of the control window -- so the inequality the check actually asks
  about, \`f_max(band ${BAND_A}) >= f_min(band ${BAND_B})\` ON ONE DIE, is
  measured under mismatch as a per-draw ratio instead of being proxied by one
  band's relative dispersion. Closes both limitations
  \`sim/vco-tuning-range/records/20260923-084925-1655e11.md\` names in its own
  Methodology field -- "Band 1's own f_min is NOT re-measured with mismatch
  here ... not a joint two-band Monte Carlo", and the proxy convention it
  inherited ("an order-of-magnitude sanity flag, not a rigorous directional
  bound") -- and the band-axis half of T1/bronze item 6's corner-combination
  sub-criterion (#127, issue #597: this campaign's Monte Carlo evidence was
  2 corners x 1 band, never 1 corner x 2 bands). Neither prior record is
  superseded: \`20260817-143524-0e9cfc9\` (bands 0 and 7, mid-window, nominal
  corner) and \`20260923-084925-1655e11\` (band 0 at this corner and Vctrl,
  against band 1's systematic floor) both stand unmodified as historical
  evidence, sim/ being append-only. This record is additive and is the first in
  this repo to draw two band codes from one mismatch draw.
- **Model-capability gate**: this record RESTS ON the parse-time-seed finding
  rather than merely reusing it -- see
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`'s
  "Model-capability gate" for the original evidence (\`agauss()\` per-instance
  draws inside \`nfet_03v3_dss\`/\`pfet_03v3_dss\`, gated by
  \`sw_stat_mismatch\`, evaluated ONCE at netlist PARSE time, reproducible via
  \`.option rndseed=N\`). Parse-time evaluation is exactly what makes a joint
  two-band draw possible: two \`tran\` runs inside one \`.control\` block of
  \`testbench/tb_vco_band_pair.sp\` see the SAME offsets, because the draws
  happened before either ran. The band code is moved between the two runs with
  \`alter\` on three DC sources -- no device is added, removed or
  re-parameterised, so nothing the draw depends on changes. The same
  one-parse-many-analyses idiom is already in use in
  \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\` (three Vctrl points per
  draw); what is new here is applying it across the BAND axis.
  #597's own negative-control re-check was performed on the sibling campaign at
  a newly added MOS bundle and is recorded there.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\` (the
  same DUT both prior mismatch records and the systematic \`testbench/tb.json\`
  sweep compose, unmodified by this record), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band-pair-worst-corner.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck
  \`sim/vco-tuning-range/testbench/tb_vco_band_pair.sp\` is NEW for this record
  (the single-band \`tb_vco_mismatch.sp\` both prior records use is unchanged
  and still present); it contains stimulus, the two-run control block,
  measurement and the \`sw_stat_mismatch\`/\`rndseed\` overrides only, with
  both band codes and both control voltages as parameters.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this campaign's own deck (tb_vco_band_pair.sp) then declares sw_stat_global=0 / sw_stat_mismatch=1, positioned after the design.ngspice include so the later declaration wins -- same harness-ordering finding sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md documents in full")
- **Corner matrix run**: ONE corner, TWO bands per draw, each at its own
  control-window end -- \`${CORNER_TAG}\` (-> \`.lib\` sections \`${CORNER}\`)
  / ${TEMP} C / ${VDD} V, with band ${BAND_A} at Vctrl = ${VCTRL_A} V (its
  f_max) and band ${BAND_B} at Vctrl = ${VCTRL_B} V (its f_min). **Axes not
  swept**: every other corner, temperature and supply; the five intermediate
  Vctrl points; and band codes 2-7. **Justification** (sim/README.md's
  "Default corner matrix" rule): the corner is not chosen for convenience and
  is not nominal -- it is the EXACT point
  \`sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv\`
  reports as this pair's WORST overlap ratio, and the two Vctrl values are the
  exact two points that ratio is computed from (\`raw_measures.csv\` rows
  \`ss,125.0,3.63,band0\` f7 = ${FNOM_A} Hz and \`ss,125.0,3.63,band1\` f1 =
  ${FNOM_B} Hz, ratio ${SYS_RATIO}, matching the 1.319 that file cites). A
  margin binds where it is thinnest, and that corner is already identified by
  the systematic 45-point sweep; measuring the dispersion anywhere else would
  reintroduce exactly the different-point comparison the prior records had to
  flag. What THIS record adds over \`20260923-084925-1655e11\`, which already
  ran at this corner and this Vctrl, is the SECOND BAND, drawn jointly -- the
  axis #597 found at 1 for this campaign.
- **Methodology / criteria / limitations**:
  - **One invocation = one draw = both bands.** \`N_SAMPLES=${N_SAMPLES}\`
    invocations of \`tb_vco_band_pair.sp\`, one \`.option rndseed\` each, seeds
    \`1..N\`. Each invocation runs two \`tran\` analyses in one \`.control\`
    block: band ${BAND_A} (band-select code B2 B1 B0 = $(( (BAND_A >> 2) & 1 ))$(( (BAND_A >> 1) & 1 ))$(( BAND_A & 1 ))) at
    Vctrl = ${VCTRL_A} V, then band ${BAND_B} (code B2 B1 B0 = $(( (BAND_B >> 2) & 1 ))$(( (BAND_B >> 1) & 1 ))$(( BAND_B & 1 ))) at
    Vctrl = ${VCTRL_B} V. Measurement criterion identical to every other
    \`sim/vco-tuning-range/\` record: \`f = 4/tp\`, \`tp\` from the first to
    the fifth rising half-supply crossing of the buffered \`CLK\` output after
    \`tsettle\` (>= 4 estimated periods), taken independently for each of the
    two runs.
  - **THE VERDICT STATISTIC IS THE RATIO'S OWN TAIL, and that is the point of
    this record.** Because both frequencies come from one draw, the overlap
    ratio \`f_max(band ${BAND_A}) / f_min(band ${BAND_B})\` is itself a
    per-sample quantity, and the criterion is its one-sided 3-sigma low tail:
    \`mean(ratio) - 3*sigma(ratio) >= ${RATIO_FLOOR}\`. Below ${RATIO_FLOOR}
    the lower band's top has fallen past the upper band's bottom and there is a
    frequency neither band reaches. Both prior mismatch records reported
    \`|mean|+3sigma\` as a PERCENTAGE of one band's mean and read it against
    the fractional overlap margin, and both flagged that in their own text as a
    sanity flag rather than a bound -- necessarily, because with one band drawn
    the inequality could not be written down under mismatch at all. Those
    percentage figures are reported below for continuity only.
  - **The independent-draw bound is reported beside it, and it is the wrong
    statistic -- measurably so.** On these same samples, treating the two bands
    as unrelated and pushing each to its own opposite tail gives
    \`(mean(f_A) - 3sd(f_A)) / (mean(f_B) + 3sd(f_B))\` = ${IND_RATIO}
    (${IND_VERDICT}), against the joint ${R_LO} (${R_VERDICT}). The gap between
    those two numbers is not a modelling preference: the measured Pearson
    correlation between the pair's two frequencies across draws is
    **rho = ${RHO}**, i.e. the dispersion is largely COMMON to both bands,
    which is what the shared hardware predicts -- bands ${BAND_A} and
    ${BAND_B} differ by one switched leg of \`design/vco_bias.sch\`'s mirror
    cascade and share every always-on leg, the V->I converter and all five ring
    stages. Common-mode dispersion cancels in a ratio and does not open a
    coverage hole; the independent bound double-counts it. That correlation is
    a MEASUREMENT here, which is why this record can state the point instead of
    arguing it.
  - **What is still not measured.** (1) Only this pair: B${BAND_A} ->
    B${BAND_B} is the pair band ${BAND_A}'s own coverage-hole risk lives on,
    but the worst ratio across ALL SEVEN adjacent pairs belongs to B3 -> B4
    (1.268, same corner) and is unmeasured under mismatch on either side. The
    deck takes both band codes as parameters, so extending to another pair is a
    runner change with no deck change -- it is simply not done here.
    (2) Only this corner: the corner axis of this campaign's Monte Carlo
    evidence is still 1 wide, deliberately (the binding corner is known from
    the systematic sweep), whereas the sibling \`sim/mc-cp-mismatch\` campaign
    is where #597 widens the corner axis. (3) Global process variation stays
    off (\`sw_stat_global = 0\`), as in every Monte Carlo campaign here -- the
    corner grid, not a global draw, is how process spread is represented.
  - **Transient window**: sized per band off that band's own SYSTEMATIC
    frequency (${FNOM_A} Hz for band ${BAND_A}, ${FNOM_B} Hz for band
    ${BAND_B}, both from
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`)
    with a $(awk -v k="${WIN_LO_FRAC}" 'BEGIN{printf "%.0f", 100*(1-k)}')% /
    $(awk -v k="${WIN_HI_FRAC}" 'BEGIN{printf "%.0f", 100*(k-1)}')% bracket
    either side -- WIDER than the +/-30% the single-band scripts use, because
    this window has to hold a mismatched frequency whose own 3-sigma spread
    those records measured at roughly 25% of the mean, and a 30% window leaves
    no margin past 3 sigma. Never trusted for a result, only for tstep/tstop
    sizing. Every draw's two frequencies are asserted to land inside that
    bracket before the sample is accepted, so a \`meas\` that latched onto the
    wrong edge is rejected rather than averaged in; all ${N_SAMPLES} draws
    passed that assertion.
- **Statistical convention**: \`sw_stat_global = 0\`,
  \`sw_stat_mismatch = 1\` (mismatch-only, global process variation off,
  matching every other Monte Carlo campaign in this repo).
  \`N_SAMPLES=${N_SAMPLES}\` joint draws, each yielding both bands. Seeds:
  sequential integers \`1..N\`, passed via \`.option rndseed\`; every draw's
  raw log is committed under \`corners/${RID}/\` and holds BOTH runs, so a
  reader can see the two analyses share one parse. Dispersion reported at mean
  +/- sample standard deviation (N-1 denominator); the verdict uses the
  per-draw RATIO's one-sided 3-sigma tail, in the direction that closes the
  overlap.
- **Result**:

  | Quantity | Mean | sd | n | systematic reference |
  |---|---|---|---|---|
  | band ${BAND_A} f at Vctrl=${VCTRL_A} V (f_max side) | ${A_M} Hz | ${A_SD} Hz | ${A_N} | ${FNOM_A} Hz |
  | band ${BAND_B} f at Vctrl=${VCTRL_B} V (f_min side) | ${B_M} Hz | ${B_SD} Hz | ${A_N} | ${FNOM_B} Hz |
  | **per-draw overlap ratio f_A / f_B** | **${R_M}** | **${R_SD}** | ${R_N} | ${SYS_RATIO} |

  | Criterion | Statistic | Line | Verdict |
  |---|---|---|---|
  | B${BAND_A} -> B${BAND_B} overlap, joint 3-sigma worst case | mean(ratio) - 3sigma(ratio) = **${R_LO}** | >= ${RATIO_FLOOR} | **${R_VERDICT}** |
  | -- the same samples under the prior records' INDEPENDENT-draw treatment | ${IND_A_LO} / ${IND_B_HI} = ${IND_RATIO} | >= ${RATIO_FLOOR} | ${IND_VERDICT} (not this record's verdict) |
  | -- measured correlation between the pair's two frequencies | rho = ${RHO} | -- | -- |
${RATIO_NOTE}

  Standard error of the ratio's mean: ${R_SE} at n=${R_N} -- reported so the
  verdict's margin can be weighed against sampling noise rather than read as an
  exact figure. It is the MEAN's standard error, a lower bound on the
  uncertainty in \`mean - 3sigma\`, which also carries the 3-sigma multiplier's
  own estimation error.

  The prior two records' proxy figure, for continuity only and NOT this
  record's verdict: +-3sigma as a percentage of the mean is ${A_3SPCT}% for
  band ${BAND_A} and ${B_3SPCT}% for band ${BAND_B}, against the
  ${SYS_RATIO} systematic ratio's ${SYS_MARGIN_PCT}% fractional margin.
  Comparing those percentages against that margin is the comparison this
  record replaces, and the rho = ${RHO} above is why.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_band_pair.sp\` (new),
    \`run_band_pair_worst_corner.sh\` (new)
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`, \`design/vco_stage.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band-pair-worst-corner.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/mismatch.csv\`
  - Systematic sweep and overlap check this record's corner, Vctrl points and
    reference frequencies are drawn from (unchanged, untouched):
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`
  - Prior mismatch records this one follows on from (neither superseded):
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\` (bands 0 and 7,
    mid-window, nominal corner),
    \`sim/vco-tuning-range/records/20260923-084925-1655e11.md\` (band 0 at this
    same corner and Vctrl, against band 1's systematic floor)
  - The one-parse-many-analyses idiom this deck reuses:
    \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\`
  - Companion campaign in the same issue (the CORNER axis half):
    \`sim/mc-cp-mismatch/testbench/run.sh\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #597)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "vco-tuning-range band-pair: wrote ${RECORD}"
echo "vco-tuning-range band-pair: wrote ${OUT}"
echo "vco-tuning-range band-pair: wrote ${CORNERSDIR}/ (${N_SAMPLES} draw logs, two analyses each)"
