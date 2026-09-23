#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: band 0's OWN worst-corner adjacent-overlap
# verdict (issue #482)
#
# --- What gap this closes -------------------------------------------------
#
# record `sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md` (#146)
# measured band 0's frequency dispersion under random device mismatch at ONE
# nominal point (`typical`/27C/3.30V, Vctrl=1.8V mid-window) and compared it
# against a headroom figure (26.8%) borrowed from a DIFFERENT record's
# DIFFERENT band pair, at a DIFFERENT corner:
# `sim/vco-tuning-range/records/20260804-164956-72883fb.md`'s band_overlap
# check cites "worst adjacent overlap ratio 1.268" as the single worst ratio
# ACROSS ALL SEVEN adjacent-band pairs -- but that worst-of-all-pairs figure
# belongs to the B3->B4 pair, not B0->B1. Band 0's OWN adjacent pair (B0->B1)
# has a different worst ratio (1.319, i.e. 31.9% headroom) at a different
# corner (`ss`/125C/3.63V, not `typical`/27C/3.30V). That earlier record said
# so itself in its own "What this is NOT" paragraph and named exactly this
# follow-on as the fix. This script is that follow-on -- see
# sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md's Result field for
# the full self-declared gap.
#
# --- Corner + Vctrl point choice, and how it was verified ------------------
#
# `sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv`'s
# "B0 -> B1" row: worst overlap ratio 1.319 at corner `ss`/125C/3.63V. `ss`
# here is the bare 5-way MOS-only bundle (passives left at `res_typical`,
# `moscap_typical`) from that record's "mos" sweep entry -- NOT the composite
# `all-slow` bundle (`ss,res_ss,moscap_ss`, see common.sh's bundle_libs()).
# Confirmed directly against that record's raw per-point data
# (`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv`,
# filtering corner=ss, temp_c=125, vdd=3.63):
#   band0 f7 (Vctrl=2.7V, i.e. f_max(band0)) = 9122300 Hz
#   band1 f1 (Vctrl=0.9V, i.e. f_min(band1)) = 6917000 Hz
#   ratio = 9122300 / 6917000 = 1.3188 -- matches the cited 1.319, confirming
#   this is the exact point the systematic sweep's overlap check used.
# `band_overlap`'s definition is `f_max(band b) / f_min(band b+1)` -- f_max
# for a band is achieved at the TOP of the 0.9-2.7V control window (f7, the
# seventh of the seven 0.3V-spaced control points the systematic sweep
# takes), not the MID-window point (Vctrl=1.8V) the earlier mismatch record
# used for its band0/band7 characterization pass. This script measures
# dispersion AT Vctrl=2.7V specifically so the Monte Carlo draw is centered on
# the exact operating point the coverage-hole check itself depends on --
# anything else would still be an uncombined comparison, just with the corner
# fixed and the Vctrl mismatch left in place.
#
# --- What this is, and what it deliberately is NOT -------------------------
#
# This is band 0's OWN dispersion (mean, sd, |mean|+3sigma as % of mean) at
# the (corner, Vctrl) point that sets band 0's contribution to its own worst
# adjacent-band margin, compared against band 0's OWN headroom (31.9%, not
# the borrowed 26.8% figure). It reuses the earlier record's SAME proxy
# convention (a two-sided +/-3sigma relative dispersion vs. a one-sided
# fractional overlap margin is an order-of-magnitude sanity flag, not a
# rigorous directional bound -- see that record's own caveat, unchanged here)
# and its SAME independent-draw limitation: band 1 is NOT re-measured with
# mismatch in this script, so this is band 0's dispersion against band 1's
# UNCHANGED systematic (mismatch-off) reference floor, not a joint two-band
# Monte Carlo. A joint draw would also need band 0 and band 1's shared
# always-on mirror legs to carry the SAME per-instance mismatch draw in one
# simulation (they are physically the same devices on one die) -- this
# script, like its predecessor, draws each band in an independent ngspice
# invocation instead, which is a real, stated limitation, not silently
# smoothed over.
#
# This record does NOT supersede or invalidate
# `sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md` -- that record's
# mid-window characterization of BOTH band 0 and band 7 stands unmodified as
# historical evidence (sim/ results are append-only); this record adds the
# corrected, same-corner, same-Vctrl verdict for band 0 specifically that the
# earlier one named as its own open follow-on.
#
# Usage:
#   ./run_band0_worst_corner.sh          # full campaign -> mints records/<id>.md
#   ./run_band0_worst_corner.sh --check  # 2 samples, to stdout
#   N_SAMPLES=.. ./run_band0_worst_corner.sh   # override sample count (default 100)

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

DECK="${HERE}/tb_vco_mismatch.sp"
DUT_SRC="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-band0-worst-corner"

# Corner + Vctrl point -- see header comment for full derivation/verification.
CORNER="ss,res_typical,moscap_typical"
CORNER_TAG=ss
TEMP=125
VDD=3.63
VCTRL=2.7

# Systematic (sw_stat_mismatch=0) reference values at this exact
# (corner, Vctrl, band) point, read directly from
# sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv
# (corner=ss, temp_c=125, vdd=3.63; band0's f7, band1's f1) -- see header
# comment for the ratio cross-check against band_overlap.csv's cited 1.319.
FNOM_BAND0=9122300
HEADROOM_PCT=31.88

N_SAMPLES="${N_SAMPLES:-100}"

HEADER="band,seed,f_hz,i_a"

stage_netlist() {
  mkdir -p "$1"
  cp "${DUT_SRC}" "$1/vco.spice"
}

# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# See that function's comment there for the full investigation.

# One (band0, seed) sample -> one CSV row on stdout.
run_one() {
  local seed="$1" sfile="$2"
  local tag="band0_seed$(printf '%03d' "${seed}")"
  stage_netlist "${WORK}/${tag}"
  # Window sized generously off the nominal (mismatch-free) frequency at THIS
  # (corner, Vctrl) point -- same 30%-margin convention as run_mismatch.sh's
  # run_one(), never trusted for a result, only for tstep/tstop sizing.
  local flo fhi tsettle tstop tmax
  flo=$(awk -v f="${FNOM_BAND0}" 'BEGIN{print f*0.7}')
  fhi=$(awk -v f="${FNOM_BAND0}" 'BEGIN{print f*1.3}')
  tsettle=$(awk -v f="${flo}" 'BEGIN{printf "%.6g", 1.2*4/f}')
  tstop=$(awk -v ts="${tsettle}" -v f="${flo}" 'BEGIN{printf "%.6g", ts + 1.2*7/f}')
  tmax=$(awk -v f="${fhi}" 'BEGIN{printf "%.6g", 1/(80*f)}')
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL}" "b0v=0*${VDD}" "b1v=0*${VDD}" "b2v=0*${VDD}" \
    "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
    "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" f i
  f=$(simenv_meas "${log}" f1)
  i=$(simenv_meas "${log}" i1)
  printf '0,%s,%s,%s\n' "${seed}" "${f}" "${i}" >>"${sfile}"
}

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
  echo "vco-tuning-range band0-worst-corner --check: 2 samples at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}"
  for s in 1 2; do run_one "${s}" "${tmpdir}/out.csv"; done
  echo "${HEADER}"; cat "${tmpdir}/out.csv"
  exit 0
fi

echo "vco-tuning-range band0-worst-corner: N_SAMPLES=${N_SAMPLES} at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/band0_*.csv

seq 1 "${N_SAMPLES}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run_band0_worst_corner.sh\" --one {} \"${WORK}/band0_{}.csv\""

cat "${WORK}"/band0_*.csv | sort -t, -k2,2n >"${WORK}/all.csv"

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

cp "${DUT_SRC}" "${SNAPDIR}/${RID}-vco-band0-worst-corner.spice"
SHA_VCO=$(simenv_sha256 "${SNAPDIR}/${RID}-vco-band0-worst-corner.spice")

for f in "${WORK}"/band0_seed*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")")_${CORNER_TAG}_${TEMP}c_${VDD}v.log"
done

OUT="${CORNERSDIR}/mismatch.csv"
{
  simenv_provenance "vco-tuning-range (band0 worst-corner overlap verdict)" "${RID}" \
    "design/netlist/vco.spice (committed export)" \
    "${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, band=0 only, N=${N_SAMPLES} mismatch samples"
  echo "${HEADER}"; cat "${WORK}/all.csv"
} >"${OUT}"

stats_band() {
  simenv_datarows "${OUT}" | awk -F, '{print $3}' | simenv_stats_from_values
}

B0_F=$(stats_band); B0_F_M=$(echo "${B0_F}" | awk '{print $1}'); B0_F_SD=$(echo "${B0_F}" | awk '{print $2}'); B0_F_N=$(echo "${B0_F}" | awk '{print $3}')

pct3s() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.4g", 300*s/m}'; }
B0_F_3SPCT=$(pct3s "${B0_F_M}" "${B0_F_SD}")

echo "band0 f (at its own worst-corner overlap point): mean=${B0_F_M} Hz sd=${B0_F_SD} Hz (+-3sigma = ${B0_F_3SPCT}% of mean, n=${B0_F_N})"

headroom_verdict() { awk -v p="$1" -v h="${HEADROOM_PCT}" 'BEGIN{print (p<=h)?"under":"OVER"}'; }
B0_HEADROOM_VERDICT=$(headroom_verdict "${B0_F_3SPCT}")
echo "band0 vs ${HEADROOM_PCT}% headroom (B0->B1 pair, its own worst corner): ${B0_HEADROOM_VERDICT}"

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 / design/README.md's "3-bit band-select mirror" -- band 0's
  OWN adjacent-band coverage-hole check (\`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
  band_overlap check, B0 -> B1 pair, worst overlap ratio 1.319 at
  \`ss\`/125C/3.63V), combined with the RANDOM device (Vth/beta) mismatch
  dispersion the band-select mirror cascade (\`design/vco_bias.sch\`) adds to
  band 0's frequency AT THAT EXACT (corner, Vctrl) point -- closing the
  open follow-on
  \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`'s own "What
  this is NOT" paragraph named (issue #482). That record's mid-window
  (\`typical\`/27C/3.30V, Vctrl=1.8V) characterization of band 0 AND band 7
  stands unmodified as historical evidence (append-only); this record is
  additive, giving band 0 specifically the same-corner, same-Vctrl verdict
  the earlier record's own borrowed-headroom comparison could not.
- **Model-capability gate**: unchanged from every other Monte Carlo campaign
  in this repo -- see \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`'s
  "Model-capability gate" for the full \`agauss()\`/parse-time-seed finding
  this campaign relies on (independent per-instance mismatch draws, gated by
  \`sw_stat_mismatch\`, reproducible via \`.option rndseed=N\`). Not
  re-derived here.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\`
  (same DUT \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\` and
  the systematic \`testbench/tb.json\` sweep both compose, unmodified by this
  record), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band0-worst-corner.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck (\`tb_vco_mismatch.sp\`, unchanged
  from the sibling record) contains stimulus, measurement and the
  \`sw_stat_mismatch\`/\`rndseed\` overrides only.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this campaign's own deck (tb_vco_mismatch.sp) then declares sw_stat_global=0 / sw_stat_mismatch=1, positioned after the design.ngspice include so the later declaration wins -- same harness-ordering finding sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md documents in full")
- **Corner matrix run**: ONE targeted point, deliberately NOT nominal --
  \`${CORNER_TAG}\` (-> \`.lib\` sections \`${CORNER}\`) / ${TEMP} C / ${VDD} V,
  Vctrl = ${VCTRL} V. **Axes not swept**: every other corner, temperature,
  supply, and Vctrl point, plus all band codes other than 0, are fixed/omitted
  by design -- this record's entire job is a same-point re-check of ONE
  specific coverage-hole risk already identified elsewhere, not a
  characterization sweep. **Justification** (sim/README.md's "Default corner
  matrix" rule): this (corner, Vctrl) point is not chosen for convenience --
  it is the EXACT point
  \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s own
  band_overlap check used to compute the B0->B1 pair's worst overlap ratio
  (1.319, 31.9% headroom). Measuring anywhere else would reintroduce the
  uncombined, different-corner comparison this record exists to fix. See this
  file's header comment for the full raw_measures.csv cross-check confirming
  \`ss\`/125C/3.63V, Vctrl=2.7V, band0's f7 point (9122300 Hz) is the same
  point that record's f_max(band0) uses.
- **Methodology / criteria / limitations**:
  - Single VCO copy, band 0 only, at Vctrl = ${VCTRL} V (the TOP of the
    0.9-2.7V control window -- f_max(band0), not the mid-window point
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\` used),
    \`N_SAMPLES=${N_SAMPLES}\` single-instance invocations, one \`.option
    rndseed\` per sample. Measurement criterion identical to every other
    \`sim/vco-tuning-range/\` record: \`f = 4/tp\`, \`tp\` from the first to
    the fifth rising half-supply crossing of the buffered \`CLK\` output
    after \`tsettle\` (>= 4 estimated periods).
  - **Transient window**: sized off the SYSTEMATIC frequency at this exact
    point (9122300 Hz, from
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`,
    corner=ss/temp_c=125/vdd=3.63/band0, f7 column) with a +/-30% margin
    either side -- never trusted for a result, only for tstep/tstop sizing.
  - **Headroom is band 0's OWN pair, at its OWN worst corner -- not a
    borrowed figure.** \`HEADROOM_PCT=${HEADROOM_PCT}\` is the fractional part
    of the B0->B1 pair's worst overlap ratio (1.319) from
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv\`,
    cross-checked directly against that record's own per-point
    \`raw_measures.csv\` (band0 f7 / band1 f1 at this exact corner = 1.3188,
    matching the cited 1.319) -- see this file's header comment for the full
    derivation. This replaces
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`'s use of
    1.268 (26.8%), which was that record's own honestly-flagged proxy: the
    worst overlap ratio ACROSS ALL SEVEN adjacent-band pairs (which turns out
    to be the B3->B4 pair, at the same corner but not the same pair), not
    band 0's own pair.
  - **Same-corner, same-Vctrl, but still NOT a joint two-band Monte Carlo.**
    Band 1's own f_min is NOT re-measured with mismatch here -- this record
    compares band 0's mismatch-driven dispersion against band 1's UNCHANGED
    systematic (\`sw_stat_mismatch=0\`) reference floor (6917000 Hz, same
    source file/point, band1 f1). A fully joint check would need band 0 and
    band 1 to share ONE per-instance mismatch draw on their common always-on
    mirror legs (they are the same physical devices on one die across band
    codes) within a single simulation -- this script, like its predecessor,
    draws independently instead. This is a real, stated limitation of the
    Monte Carlo methodology this repo currently has, not a gap specific to
    this record.
  - **Proxy convention unchanged from the sibling record**: \`|mean|+3sigma\`
    as a percentage of the mean is a two-sided relative-dispersion figure
    compared against a one-sided fractional overlap margin -- an
    order-of-magnitude sanity flag, not a rigorous directional bound. See
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`'s own caveat
    for the full statement; this record inherits it unchanged.
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off, matching every other Monte
  Carlo campaign in this repo). \`N_SAMPLES=${N_SAMPLES}\`, band 0 only.
  Seeds: sequential integers \`1..N\`, passed via \`.option rndseed\`; every
  seed's raw log is committed under \`corners/${RID}/\`.
- **Result**:

  | Band | f mean | f sd | \|mean\|+3sigma as %% of mean | vs. ${HEADROOM_PCT}% headroom (B0->B1 pair, its own worst corner) | n |
  |---|---|---|---|---|---|
  | 0 (at Vctrl=2.7V, \`ss\`/125C/3.63V -- its own f_max/overlap point) | ${B0_F_M} Hz | ${B0_F_SD} Hz | ${B0_F_3SPCT}% | **${B0_HEADROOM_VERDICT}** | ${B0_F_N} |

  Reference (unchanged, systematic, \`sw_stat_mismatch=0\`, from
  \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`):
  f_max(band0) = 9122300 Hz at this exact point; f_min(band1) = 6917000 Hz at
  \`ss\`/125C/3.63V, Vctrl=0.9V -- ratio 1.3188, matching the cited 1.319.

  This is now a genuine same-corner, same-Vctrl combined check (not the
  earlier record's nominal-dispersion-vs-worst-pair-elsewhere comparison),
  subject to the two limitations named above (proxy convention;
  independent-draw, not joint, Monte Carlo). Read together with
  \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`'s band 7 result
  (comfortably under headroom at its own mid-window nominal point, unaffected
  by this record), this closes the item-6 gap #482 filed for band 0's
  coverage-hole risk.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_mismatch.sp\`,
    \`run_band0_worst_corner.sh\`
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`, \`design/vco_stage.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-band0-worst-corner.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/mismatch.csv\`
  - Systematic sweep and overlap check this record's headroom is drawn from
    (unchanged, untouched): \`sim/vco-tuning-range/testbench/tb.json\`,
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/band_overlap.csv\`,
    \`sim/vco-tuning-range/corners/20260804-164956-72883fb/raw_measures.csv\`
  - Sibling Monte Carlo record this follows on from (mid-window
    characterization, band0 + band7, not superseded):
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #482)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "vco-tuning-range band0-worst-corner: wrote ${RECORD}"
echo "vco-tuning-range band0-worst-corner: wrote ${OUT}"
echo "vco-tuning-range band0-worst-corner: wrote ${CORNERSDIR}/ (${N_SAMPLES} corner logs)"
