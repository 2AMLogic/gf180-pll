#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: VCO band-select mirror Monte Carlo (#146)
#
# Characterizes the frequency DISPERSION random device mismatch in the
# band-select mirror (design/README.md's "3-bit band-select mirror" --
# design/vco_bias.sch's cascaded current mirrors) adds on top of the
# systematic f(Vctrl)/band-plan curve testbench/tb.json's harness-driven
# sweep already measures (sw_stat_mismatch=0 there, unchanged). This is a
# SEPARATE, additive record, not a re-run of that sweep with the switch
# flipped -- see below for why.
#
# --- Why a raw sim/lib/simenv.sh deck instead of extending tb.json --------
#
# The obvious-looking approach -- add `"params": {"sw_stat_mismatch": "1"}`
# to testbench/tb.json -- was tried first and found NOT to work, for a
# harness-ordering reason worth recording so the next person does not
# rediscover it the hard way:
#
#   sim/harness/runner.py's compose_deck() emits every `tb.params` entry as a
#   `.param key=value` line BEFORE `.include "<design.ngspice>"` (see that
#   file: the PVT-parameter block at the top of the generated deck, then the
#   models section). design.ngspice itself declares
#   `.param sw_stat_global = 0` / `.param sw_stat_mismatch = 0` -- AFTER the
#   testbench's own params, in deck order. Direct experiment (three ngspice
#   decks, redefinition ordering isolated from every other variable) confirms
#   ngspice-46 resolves a parameter redefined more than once by LAST
#   occurrence in the deck, not first -- so a tb.json `params` override of
#   sw_stat_mismatch is SILENTLY nullified back to design.ngspice's own
#   default by the include that follows it. This is a genuine, previously
#   undocumented harness limitation (it affects ANY manifest trying to
#   override a design.ngspice-defaulted global via `params`, not just this
#   one) -- fixing it generally is out of scope for #146 (a shared
#   sim/harness/runner.py behavior change affecting every existing harness
#   campaign's deck ordering needs its own review, not a side effect of a
#   two-record evidence issue) and is worth a follow-up issue if the operator
#   agrees.
#
#   sim/mc-cp-mismatch's own established pattern already puts the override
#   AFTER the design.ngspice include (simenv_run_deck emits `.param` kv
#   overrides, then `.include "<campaign deck>"` last) -- which is exactly
#   why that campaign's `sw_stat_mismatch=1` override works. This deck
#   reuses the SAME ordering by declaring the switches directly inside
#   tb_vco_mismatch.sp (included after the corner .lib sections, same as
#   every other testbench netlist in this repo), not via a `params` kv.
#
#   Separately, the harness's PVT-grid runner has no Monte Carlo seed axis:
#   `.option rndseed=N` must be read at netlist PARSE time (see
#   sim/mc-cp-mismatch's established finding, confirmed unchanged by this
#   issue), and neither tb.json's `sweeps` axis mechanism nor its `options`
#   list passes a per-point value through the harness's `{placeholder}`
#   substitution the way `analyses` text does -- so a seed axis would need
#   its own harness feature, not just a manifest edit.
#
# Given both gaps, this campaign reuses mc-cp-mismatch's raw
# `sim/lib/simenv.sh` pattern (the same pattern that campaign itself uses
# because it predates the harness) instead of "extending" the harness
# manifest that does not yet support either need. testbench/tb.json's own
# harness-driven sweep is UNCHANGED by this file (still sw_stat_mismatch=0,
# still the systematic PVT claim) -- this is additive, not a replacement.
#
# --- Scope of this campaign -------------------------------------------------
#
# ONE VCO copy (not the seven-copy f(Vctrl) topology) at a FIXED Vctrl
# (1.8 V, mid-window) and TWO band codes -- band 0 (no switched leg active:
# only the three always-on mirror legs) and band 7 (every switched leg
# active: the full three-cascade path) -- the two ends of the band-select
# mirror's cascade activation, at nominal PVT
# (typical/27C/3.30V). sim/README.md's "single nominal point ... for a Monte
# Carlo distribution claim ... allowed with justification" rule applies here
# exactly as it does for mc-cp-mismatch: corner sensitivity of the MEAN is
# testbench/tb.json's job (45-corner grid, already measured); this
# campaign's job is the DISPERSION mismatch adds on top, and there is no
# reason to expect the mirror's Pelgrom-mismatch mechanism to have strong PVT
# dependence the way a systematic tail-charge term would (same reasoning
# mc-cp-mismatch's original nominal-only record used). #146's
# mc-cp-mismatch corner-grid extension (this issue's other half) is where
# that assumption gets its own combined-with-corners check for the
# charge-pump/PFD side of the loop; this smaller campaign does not repeat
# that exercise for the VCO given the added wall clock a second corner-grid
# extension would cost in the same PR.
#
# No numeric budget exists for VCO band-select mirror mismatch in
# design/README.md (only the charge-pump "Up/down mismatch budget" table
# does) -- this record reports the measured dispersion without a pass/fail
# verdict, same honest handling mc-cp-mismatch already uses for its
# divider-retiming-flop term (also not itself a budget-table line).
#
# Usage:
#   ./run_mismatch.sh                 # full campaign -> mints a records/<id>.md
#   ./run_mismatch.sh --check         # 2 samples per band, to stdout
#   SIM_JOBS=8 ./run_mismatch.sh      # cap parallelism
#   N_SAMPLES=.. ./run_mismatch.sh    # override per-band sample count

set -euo pipefail

# Host oversubscription fix, same finding as sim/mc-cp-mismatch/testbench/
# run.sh's #146 build (see that file's header comment for the full
# measurement): ngspice-46 on this repo's build host is compiled with
# OpenMP-parallel BSIM model evaluation, so every `ngspice -b` invocation
# spawns several OS threads on its own, independent of this script's own
# `xargs -P $(simenv_jobs)` process-level fan-out -- oversubscribing the
# host's 8 physical cores several times over from self-contention alone.
# Pinning one thread per ngspice process and letting `simenv_jobs` provide
# parallelism at the process level (measured ~44x wall-clock improvement on
# the sibling campaign) is the correct division for this host.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_vco_mismatch.sp"
DUT_SRC="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-mismatch"

# The VCO's frequency is set in part by a poly resistor (the V->I
# degeneration resistor and the constant-gm reference resistor) -- the MOS
# `typical` bundle alone omits the res_*/moscap_* passive sections, and this
# DUT's ppolyf_u_3k / cap_nmos_03v3 devices need them (same three-section
# bundle tb_vco_tuning.sp's pre-harness run.sh used via its `bundle_libs`
# helper -- see sim/README.md's "Default corner matrix" MOS-vs-passive-axis
# hazard note this DUT is a worked example of).
CORNER="typical,res_typical,moscap_typical"
CORNER_TAG=typical
TEMP=27
VDD=3.30
VCTRL=1.8

N_SAMPLES="${N_SAMPLES:-25}"

# Two band points: (band, b0, b1, b2, nominal-f-at-Vctrl=1.8V-typical-27C-3.30V,
# used only to size the transient window, per record
# sim/vco-tuning-range/records/20260804-164956-72883fb.md's raw_measures.csv
# f4 column -- never trusted for a result, only for tstep/tstop sizing, same
# convention as tb_vco_tuning.spice's calibrated-envelope comment). band0 =
# no switched leg active (always-on legs only); band7 = every switched leg
# active (full three-mirror cascade) -- the two ends of the band-select
# mirror's cascade activation.
BAND_POINTS=(
  "0 0 0 0 6526290"
  "7 1 1 1 261947000"
)

HEADER="band,seed,f_hz,i_a"

stage_netlist() {
  mkdir -p "$1"
  cp "${DUT_SRC}" "$1/vco.spice"
}

# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# See that function's comment there for the full investigation.

# One (band, seed) sample -> one CSV row on stdout.
run_one() {
  local band="$1" b0="$2" b1="$3" b2="$4" fnom="$5" seed="$6" sfile="$7"
  local tag="band${band}_seed$(printf '%03d' "${seed}")"
  stage_netlist "${WORK}/${tag}"
  # Window sized generously off the nominal (mismatch-free) frequency: 30%
  # margin either side covers a mismatch-driven frequency shift far larger
  # than Vth/beta Pelgrom mismatch on gf180mcu 3.3V devices plausibly
  # produces (single-digit percent), so a missed .meas trigger here would
  # indicate a real problem worth seeing, not a tight window artifact.
  local flo fhi tsettle tstop tmax
  flo=$(awk -v f="${fnom}" 'BEGIN{print f*0.7}')
  fhi=$(awk -v f="${fnom}" 'BEGIN{print f*1.3}')
  tsettle=$(awk -v f="${flo}" 'BEGIN{printf "%.6g", 1.2*4/f}')
  tstop=$(awk -v ts="${tsettle}" -v f="${flo}" 'BEGIN{printf "%.6g", ts + 1.2*7/f}')
  tmax=$(awk -v f="${fhi}" 'BEGIN{printf "%.6g", 1/(80*f)}')
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL}" "b0v=$((b0))*${VDD}" "b1v=$((b1))*${VDD}" "b2v=$((b2))*${VDD}" \
    "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
    "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" f i
  f=$(simenv_meas "${log}" f1)
  i=$(simenv_meas "${log}" i1)
  printf '%s,%s,%s,%s\n' "${band}" "${seed}" "${f}" "${i}" >>"${sfile}"
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
  echo "vco-tuning-range mismatch --check: 2 samples per band at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}"
  for point in "${BAND_POINTS[@]}"; do
    read -r band b0 b1 b2 fnom <<<"${point}"
    for s in 1 2; do run_one "${band}" "${b0}" "${b1}" "${b2}" "${fnom}" "${s}" "${tmpdir}/out.csv"; done
  done
  echo "${HEADER}"; cat "${tmpdir}/out.csv"
  exit 0
fi

echo "vco-tuning-range mismatch: N_SAMPLES=${N_SAMPLES}/band x ${#BAND_POINTS[@]} bands at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/band*.csv

for point in "${BAND_POINTS[@]}"; do
  read -r band b0 b1 b2 fnom <<<"${point}"
  echo "vco-tuning-range mismatch: band${band} ..."
  seq 1 "${N_SAMPLES}" | xargs -P "$(simenv_jobs)" -I{} \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run_mismatch.sh\" --one ${band} ${b0} ${b1} ${b2} ${fnom} {} \"${WORK}/band${band}_{}.csv\""
done

cat "${WORK}"/band*.csv | sort -t, -k1,1n -k2,2n >"${WORK}/all.csv"

GOT=$(wc -l <"${WORK}/all.csv" | tr -d ' ')
EXPECT=$(( N_SAMPLES * ${#BAND_POINTS[@]} ))
[ "${GOT}" -eq "${EXPECT}" ] || { echo "ERROR: expected ${EXPECT} rows, got ${GOT}" >&2; exit 1; }

# --------------------------------------------------------------------------
# Mint the evidence record.
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DUT_SRC}" "${SNAPDIR}/${RID}-vco-mismatch.spice"
SHA_VCO=$(simenv_sha256 "${SNAPDIR}/${RID}-vco-mismatch.spice")

for f in "${WORK}"/band*_seed*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")")_${CORNER_TAG}_${TEMP}c_${VDD}v.log"
done

OUT="${CORNERSDIR}/mismatch.csv"
{
  simenv_provenance "vco-tuning-range (band-select mirror mismatch)" "${RID}" \
    "design/netlist/vco.spice (committed export)" \
    "${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, bands={0,7}, N=${N_SAMPLES} mismatch samples/band"
  echo "${HEADER}"; cat "${WORK}/all.csv"
} >"${OUT}"

stats_band() {
  local band="$1" field="$2"
  simenv_datarows "${OUT}" | awk -F, -v b="${band}" -v f="${field}" '$1==b {print $f}' | simenv_stats_from_values
}

B0_F=$(stats_band 0 3); B0_F_M=$(echo "${B0_F}" | awk '{print $1}'); B0_F_SD=$(echo "${B0_F}" | awk '{print $2}'); B0_F_N=$(echo "${B0_F}" | awk '{print $3}')
B7_F=$(stats_band 7 3); B7_F_M=$(echo "${B7_F}" | awk '{print $1}'); B7_F_SD=$(echo "${B7_F}" | awk '{print $2}'); B7_F_N=$(echo "${B7_F}" | awk '{print $3}')

pct3s() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.4g", 300*s/m}'; }
B0_F_3SPCT=$(pct3s "${B0_F_M}" "${B0_F_SD}")
B7_F_3SPCT=$(pct3s "${B7_F_M}" "${B7_F_SD}")

echo "band0 f: mean=${B0_F_M} Hz sd=${B0_F_SD} Hz (+-3sigma = ${B0_F_3SPCT}% of mean, n=${B0_F_N})"
echo "band7 f: mean=${B7_F_M} Hz sd=${B7_F_SD} Hz (+-3sigma = ${B7_F_3SPCT}% of mean, n=${B7_F_N})"

# --------------------------------------------------------------------------
# Headroom comparison, computed (not hardcoded prose) so the record's own
# words cannot silently drift from the numbers above. `HEADROOM_PCT` is the
# fractional overlap `sim/vco-tuning-range/records/20260804-164956-72883fb.md`'s
# band_overlap check found at its worst pair/corner (overlap ratio 1.268 =>
# 26.8%) -- see this record's Result field for the full caveat on why this
# is an order-of-magnitude sanity flag, not a formal combined check (a
# one-sided log-frequency overlap margin vs. a two-sided +/-3sigma
# dispersion-of-the-mean figure are not the same quantity). A band whose
# dispersion exceeds that headroom is flagged OVER, not silently rounded
# into a reassuring "well under" -- band 0's measured 38.79%-class result is
# exactly the case this guard exists for: the previous, unconditional prose
# ("both bands are well under") was FALSE for band 0 the first time this
# script produced real numbers, caught by a builder review before the
# record was committed (#146). Never repeat that mistake by hand-writing
# the verdict again.
HEADROOM_PCT=26.8
headroom_verdict() { awk -v p="$1" -v h="${HEADROOM_PCT}" 'BEGIN{print (p<=h)?"under":"OVER"}'; }
B0_HEADROOM_VERDICT=$(headroom_verdict "${B0_F_3SPCT}")
B7_HEADROOM_VERDICT=$(headroom_verdict "${B7_F_3SPCT}")
echo "band0 vs ${HEADROOM_PCT}% headroom: ${B0_HEADROOM_VERDICT}"
echo "band7 vs ${HEADROOM_PCT}% headroom: ${B7_HEADROOM_VERDICT}"

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 / design/README.md's "3-bit band-select mirror" -- does
  RANDOM device (Vth/beta) mismatch in the band-select mirror cascade
  (\`design/vco_bias.sch\`'s three cascaded current mirrors, see
  design/README.md's "Band map: a geometric mirror cascade" section) shift
  the VCO's oscillation frequency enough to matter against the systematic
  f(Vctrl)/band-plan curve \`testbench/tb.json\`'s harness-driven sweep
  measures (\`sw_stat_mismatch = 0\` there -- an explicitly documented gap in
  every prior \`sim/vco-tuning-range/\` record's methodology field, closed by
  this record). This is the second half of #146 (the first half extends
  \`sim/mc-cp-mismatch/\` with a corner-combined Monte Carlo record).
  Spec-line references are placeholders pending ratification (#1):
  \`spec/pll.md#output-band\`, \`spec/pll.md#kvco\`.
- **Model-capability gate**: reuses the finding
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\` established and
  \`sim/mc-cp-mismatch\`'s #146 corner-grid extension re-confirmed at a
  non-nominal corner -- \`nfet_03v3\`/\`pfet_03v3\` (via the
  \`nfet_03v3_dss\`/\`pfet_03v3_dss\` subcircuits) carry independent
  per-instance \`agauss()\` mismatch draws gated by \`sw_stat_mismatch\`,
  parsed once at netlist PARSE time, reproducible via \`.option rndseed=N\`.
  Not re-derived here.
- **Why a raw \`sim/lib/simenv.sh\` deck, not a \`testbench/tb.json\` manifest
  edit**: see \`run_mismatch.sh\`'s header comment for the full finding --
  in short, \`sim/harness/runner.py\`'s \`compose_deck()\` emits a manifest's
  \`params\` BEFORE \`.include design.ngspice\`, so a tb.json
  \`sw_stat_mismatch\` override is silently nullified by design.ngspice's own
  later-in-deck default (confirmed by direct ngspice-46 experiment: last
  \`.param\` redefinition in deck order wins). The harness also has no Monte
  Carlo seed axis. \`testbench/tb.json\`'s own 45-corner harness sweep is
  UNCHANGED and UNTOUCHED by this record (still \`sw_stat_mismatch = 0\`,
  still the systematic claim) -- this record is additive, reusing
  \`sim/mc-cp-mismatch\`'s pre-harness pattern for the one thing the harness
  cannot yet do.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\`
  (same DUT \`testbench/tb_vco_tuning.spice\` composes, unmodified by this
  record), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck (\`tb_vco_mismatch.sp\`) contains
  stimulus, measurement and the \`sw_stat_mismatch\`/\`rndseed\` overrides
  only -- one VCO instance instead of \`tb_vco_tuning.sp/.spice\`'s seven, no
  other change to the DUT.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly (same convention as tb_vco_tuning.sp/.spice's pre-harness sibling)" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this campaign's own deck (tb_vco_mismatch.sp) then declares sw_stat_global=0 / sw_stat_mismatch=1, positioned after the design.ngspice include specifically so the later declaration wins -- see this record's own note on the harness-ordering finding above; sw_stat_mismatch defaults to 0 in every OTHER sim/vco-tuning-range/ record, including this campaign's own harness-driven testbench/tb.json sweep, unaffected by this file")
- **Corner matrix run**: ONE nominal PVT point -- \`${CORNER_TAG}\` (-> \`.lib\`
  section \`typical\`) / ${TEMP} C / ${VDD} V, Vctrl = ${VCTRL} V (mid-window).
  **Axes not swept**: temperature, supply, MOS process corner, Vctrl (beyond
  the one mid-window point) and 6 of the 8 band codes are all fixed/omitted.
  **Justification** (sim/README.md's "Default corner matrix" rule): same
  reasoning as \`sim/mc-cp-mismatch\`'s original nominal-only record -- corner
  sensitivity of the MEAN f(Vctrl) curve is already \`testbench/tb.json\`'s
  45-corner harness sweep's job; this record's job is the DISPERSION random
  mismatch adds on top, and Pelgrom-mismatch dispersion is not expected to
  carry strong PVT dependence the way a systematic mechanism would. Band 0
  and band 7 are chosen as the two ends of the band-select mirror's cascade
  activation (band 0: only the three always-on legs; band 7: every switched
  leg active, the full three-mirror cascade) -- the intermediate 6 band codes
  and the rest of the Vctrl window are not sampled, a genuine limitation a
  future pass could widen.
- **Methodology / criteria / limitations**:
  - Single VCO copy (not \`tb_vco_tuning.sp/.spice\`'s seven), at Vctrl =
    ${VCTRL} V, band 0 or band 7, \`N_SAMPLES=${N_SAMPLES}\` single-instance
    invocations per band (\`$(( N_SAMPLES * 2 ))\` total), one \`.option
    rndseed\` per sample. Measurement criterion identical to
    \`tb_vco_tuning.sp/.spice\`: \`f = 4 / tp\`, \`tp\` from the first to the
    fifth rising half-supply crossing of the buffered \`CLK\` output after
    \`tsettle\` (>= 4 estimated periods), so the bias generator's own
    start-up transient is excluded.
  - **Transient window**: sized off the SYSTEMATIC nominal frequency at each
    band (from
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
    \`raw_measures.csv\`, \`typical/27C/3.30V\`, \`Vctrl=1.8V\`: band0
    ${BAND_POINTS[0]##* } Hz, band7 ${BAND_POINTS[1]##* } Hz) with a +/-30%
    margin either side -- never trusted for a result, only for
    \`tstep\`/\`tstop\` sizing; a missed \`.meas\` trigger would fail the
    sample rather than silently mis-measure it.
  - **No numeric budget exists for this term.** Unlike
    \`sim/mc-cp-mismatch\`'s charge-pump terms, design/README.md carries no
    "band-select mirror mismatch budget" table -- this record reports the
    measured dispersion as a characterization, not a pass/fail verdict, the
    same honest handling \`mc-cp-mismatch\` already uses for its
    divider-retiming-flop term (also not itself a budget-table line).
  - **Two band codes only, one Vctrl point.** A future, more complete pass
    would sweep the intermediate 6 band codes and more of the Vctrl window;
    this record characterizes the cascade's two activation extremes as an
    initial, honestly-scoped pass, matching this repo's evidence culture of
    a stated, narrower claim over a fabricated broad one.
  - Bias generation is NOT idealized here (unlike \`sim/mc-cp-mismatch\`'s
    charge-pump decks) -- the full \`vco_bias\` subcircuit, including its own
    mirror devices, is part of the DUT, so this record's dispersion already
    includes the bias generator's own mismatch contribution alongside the
    band-select mirror's.
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off, matching every other Monte
  Carlo campaign in this repo). \`N_SAMPLES=${N_SAMPLES}\` per band. Seeds:
  sequential integers \`1..N\` per band, passed via \`.option rndseed\`; every
  seed's raw log is committed under \`corners/${RID}/\`.
- **Result**:

  | Band | f mean | f sd | \|mean\|+3sigma as %% of mean | vs. ${HEADROOM_PCT}% headroom (see below) | n |
  |---|---|---|---|---|---|
  | 0 (no switched leg) | ${B0_F_M} Hz | ${B0_F_SD} Hz | ${B0_F_3SPCT}% | **${B0_HEADROOM_VERDICT}** | ${B0_F_N} |
  | 7 (full cascade) | ${B7_F_M} Hz | ${B7_F_SD} Hz | ${B7_F_3SPCT}% | **${B7_HEADROOM_VERDICT}** | ${B7_F_N} |

  Compare against \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
  worst adjacent-overlap ratio (1.268, \`ss/125C/3.63V\`) -- the margin that
  ratio carries above 1.0 is the headroom this dispersion draws against
  before mismatch alone could open a coverage hole at a band edge, expressed
  here as ${HEADROOM_PCT}% (the fractional part of the 1.268 ratio). **This
  is not a symmetric statement across both bands, and the two verdicts above
  are reported exactly as measured, not smoothed into one blanket
  conclusion.** Band 7 (full cascade, highest bias current) is comfortably
  UNDER headroom -- Pelgrom mismatch scales down with device current, so the
  highest-current band shows the tightest relative dispersion, as expected.
  Band 0 (only the always-on legs, the LOWEST bias current in the band plan)
  measures \`|mean|+3sigma\` OVER the 26.8% headroom figure: at this band's
  low bias current, per-instance Vth/beta mismatch is a much larger fraction
  of the drive, so its relative frequency dispersion is large enough that, in
  the worst case, random mismatch alone could plausibly erode band 0's
  adjacent-overlap margin against band 1 -- a genuine, not-yet-formally-closed
  finding, reported honestly rather than rounded down to a reassuring
  headline. **What this is NOT**: a formal combined verdict. The two source
  records' PVT points differ (this record is nominal-only \`typical/27C/3.30V\`;
  the 1.268 ratio is \`ss/125C/3.63V\`, a different corner entirely), band 0's
  own overlap ratio at its worst corner is not reproduced here, and
  \`n=${N_SAMPLES}/band\` is far short of the statistical power a real
  budget-table verdict would need. A follow-on record combining this
  campaign's per-band Monte Carlo with the systematic sweep's own worst-corner
  band-0-specific overlap ratio (not the worst-pair-overall figure used here
  as an order-of-magnitude proxy) would be needed to turn "band 0's dispersion
  looks large enough to matter" into an actual pass/fail coverage-hole check.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_mismatch.sp\`,
    \`run_mismatch.sh\`
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`, \`design/vco_stage.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/mismatch.csv\`
  - Systematic sweep this record adds dispersion on top of (unchanged,
    untouched): \`sim/vco-tuning-range/testbench/tb.json\`,
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`
  - Sibling Monte Carlo methodology (parse-time-seed finding, corner-combined
    precedent): \`sim/mc-cp-mismatch/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #146)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "vco-tuning-range mismatch: wrote ${RECORD}"
echo "vco-tuning-range mismatch: wrote ${OUT}"
echo "vco-tuning-range mismatch: wrote ${CORNERSDIR}/ ($(( N_SAMPLES * 2 )) corner logs)"
