#!/usr/bin/env bash
# gf180-pll :: mc-cp-mismatch :: Monte Carlo runner for the charge-pump
# mismatch budget (#15), checked against design/README.md's "Up/down
# mismatch budget" table.
#
# Four sub-campaigns, one record (they substantiate one claim -- "how far
# does RANDOM device mismatch actually push the charge-pump/PFD static phase
# error and reference-spur budget, on top of the SYSTEMATIC values
# cp-compliance and pfd-deadzone already measured"):
#
#   dc    tb_mc_cp_dc.sp     x design/ `cp` (via the pfd_cp export) -- term 1
#         DC UP/DN current mismatch at 0.9/1.65/2.4 V, N_DC single-instance
#         samples at the nominal PVT point.
#   sw    tb_mc_cp_switch.sp x the same `cp` -- terms 2/2a
#         Switching-time UP/DN mismatch at Vctrl = 1.65 V (mid-window only --
#         see the record's Methodology field for why a single Vctrl point is
#         used for the STATISTICAL claim), N_SW samples.
#   pfd   tb_mc_pfd_cp.sp    x design/ `pfd_cp` -- terms 3/4 + PFD-path
#         Residual charge at zero phase error and the local detector gain
#         (dphi = -1n/0/+1n), with the REAL PFD driving -- so PFD-gate
#         mismatch is folded into the same measurement as the charge pump's
#         own, N_PFD samples.
#   dff   tb_mc_dff_ctq.sp   x design/netlist/dff_tg_3v3.spice -- the
#         divider-retiming-flop contribution (a separate acceptance
#         criterion from the charge-pump terms above): clk->Q delay spread
#         under mismatch, N_DFF invocations x 2 samples each (rise + fall).
#
# All four run at ONE nominal PVT point (typical/27C/3.30V) rather than the
# repo's usual 45-corner grid: sim/README.md explicitly allows "a single
# nominal point for a Monte Carlo distribution claim ... with an in-record
# justification" -- corner sensitivity of the MEAN is already the
# corner-matrix campaigns' job (cp-compliance, pfd-deadzone); this campaign's
# job is the DISPERSION random mismatch adds on top, and there is no reason
# to expect that dispersion's mechanism (device-area-scaled Vth/mobility
# mismatch, sim/README.md's Statistical convention field) to have strong PVT
# dependence the way the systematic tail-charge term does.
#
# Deliberately does NOT attempt a closed-loop reference-spur check: the
# acceptance criteria (#15) ask for one using #12's lock-time/output-range
# bench specifically, "not a separate ad hoc closed-loop harness" -- and #12
# has not landed (`sim/lock-time/`, `sim/output-range/` do not exist on
# `main` as of this run; #12 is still open). Building an ad hoc closed-loop
# harness here would violate that instruction directly, so this record
# states the gap honestly (see its Methodology field) instead of fabricating
# one, per #13's precedent for an honest methodology/dependency gap.
#
# Usage:
#   ./run.sh                 # full campaign -> mints a records/<id>.md
#   ./run.sh --check         # a handful of samples per sub-campaign, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#   N_DC=.. N_SW=.. N_PFD=.. N_DFF=..   override sample counts

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK_DC="${HERE}/tb_mc_cp_dc.sp"
DECK_SW="${HERE}/tb_mc_cp_switch.sp"
DECK_PFD="${HERE}/tb_mc_pfd_cp.sp"
DECK_DFF="${HERE}/tb_mc_dff_ctq.sp"
WORK="${EXP}/work"
NETLIST="${WORK}/dut.spice"
DFF_NETLIST_SRC="${REPO}/design/netlist/dff_tg_3v3.spice"
DUT_DFF="${WORK}/dut_dff.sp"

# Nominal PVT point (see header: single-point campaign, justified above).
CORNER=typical
TEMP=27
VDD=3.30
# Mid-window Vctrl, matching pfd-deadzone / design/README.md's term 3/4.
VCTRL_MID=1.65

# Sample counts. dc/dff are cheap (<2 s/invocation); sw/pfd are expensive
# (cp_dumpbuf's stiff control node, ~35-110 s/invocation even with the
# itl4=200 solver-effort bump -- see the .sp headers), so they run fewer,
# still-nontrivial samples. Overridable for a smaller --check run or a
# larger re-run.
N_DC="${N_DC:-200}"
N_SW="${N_SW:-40}"
N_PFD="${N_PFD:-40}"
N_DFF="${N_DFF:-50}"

DC_HEADER="seed,vctrl_v,iup_a,idn_a,mism_pct"
SW_HEADER="seed,vctrl_v,wskew_s"
PFD_HEADER="seed,qnet0_c,qplus_c,qminus_c,kd_wide_a,t_offset_s"
DFF_HEADER="seed,tcq_r_s,tcq_f_s"

stage_netlist() {
  mkdir -p "$1"
  cp "${NETLIST}" "$1/dut.spice"
}

# ===========================================================================
# dc: tb_mc_cp_dc.sp -- term 1 (DC UP/DN current mismatch)
# ===========================================================================
run_dc() {
  local seed="$1" sfile="$2"
  local tag="dc_seed${seed}"
  stage_netlist "${WORK}/${tag}"
  simenv_run_deck "${DECK_DC}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log"
  local pt line iup idn
  for pt in "LO:0.9" "MID:1.65" "HI:2.4"; do
    local tag2="${pt%%:*}" v="${pt##*:}"
    line=$(grep "^MCDC_${tag2} " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCDC_${tag2} for seed=${seed}" >&2; return 1; }
    iup=$(echo "${line}" | sed -n 's/.*iup=\([^ ]*\).*/\1/p')
    idn=$(echo "${line}" | sed -n 's/.*idn=\([^ ]*\).*/\1/p')
    awk -v s="${seed}" -v v="${v}" -v iu="${iup}" -v id="${idn}" \
      'BEGIN { printf "%s,%s,%.6g,%.6g,%.4f\n", s, v, iu, id, 100*(iu-id)/(0.5*(iu+id)) }' >>"${sfile}"
  done
}

# ===========================================================================
# sw: tb_mc_cp_switch.sp -- terms 2/2a (switching-time UP/DN mismatch)
# ===========================================================================
run_sw() {
  local seed="$1" sfile="$2"
  local tag="sw_seed${seed}"
  stage_netlist "${WORK}/${tag}"
  simenv_run_deck "${DECK_SW}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL_MID}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" line wskew
  line=$(grep "^MCSW " "${log}" | tail -1)
  [ -n "${line}" ] || { echo "ERROR: missing MCSW for seed=${seed}" >&2; return 1; }
  wskew=$(echo "${line}" | sed -n 's/.*wskew=\([^ ]*\).*/\1/p')
  printf '%s,%s,%s\n' "${seed}" "${VCTRL_MID}" "${wskew}" >>"${sfile}"
}

# ===========================================================================
# pfd: tb_mc_pfd_cp.sp -- terms 3/4 (residual charge / static phase offset)
# ===========================================================================
run_pfd() {
  local seed="$1" sfile="$2"
  local dphi qnet0="" qplus="" qminus=""
  for dphi in -1n 0 1n; do
    local tag="pfd_seed${seed}_d${dphi}"; tag="${tag//./p}"; tag="${tag//-/m}"
    stage_netlist "${WORK}/${tag}"
    simenv_run_deck "${DECK_PFD}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
      "vsup=${VDD}" "dphi=${dphi}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
    local log="${WORK}/${tag}/ngspice.log" line q
    line=$(grep "^MCPFD " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCPFD for seed=${seed} dphi=${dphi}" >&2; return 1; }
    q=$(echo "${line}" | sed -n 's/.*qnet=\([^ ]*\).*/\1/p')
    case "${dphi}" in
      0) qnet0="${q}" ;;
      1n) qplus="${q}" ;;
      -1n) qminus="${q}" ;;
    esac
  done
  awk -v s="${seed}" -v q0="${qnet0}" -v qp="${qplus}" -v qm="${qminus}" '
    BEGIN {
      kd = (qp - qm) / 2e-9
      toff = q0 / kd
      printf "%s,%.6g,%.6g,%.6g,%.6g,%.6g\n", s, q0, qp, qm, kd, toff
    }' >>"${sfile}"
}

# ===========================================================================
# dff: tb_mc_dff_ctq.sp -- divider-retiming clk->Q spread
# ===========================================================================
run_dff() {
  local seed="$1" sfile="$2"
  local tag="dff_seed${seed}"
  simenv_run_deck "${DUT_DFF}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" tcq_r tcq_f
  tcq_r=$(simenv_meas "${log}" tcq_r)
  tcq_f=$(simenv_meas "${log}" tcq_f)
  printf '%s,%s,%s\n' "${seed}" "${tcq_r}" "${tcq_f}" >>"${sfile}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
case "${1:-}" in
  --one-dc) shift; run_dc "$@"; exit 0 ;;
  --one-sw) shift; run_sw "$@"; exit 0 ;;
  --one-pfd) shift; run_pfd "$@"; exit 0 ;;
  --one-dff) shift; run_dff "$@"; exit 0 ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

echo "mc-cp-mismatch: exporting design/ via xschem ..."
"${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
[ -f "${NETLIST}" ] || { echo "ERROR: ${NETLIST} not produced" >&2; exit 1; }

[ -f "${DFF_NETLIST_SRC}" ] || {
  echo "ERROR: ${DFF_NETLIST_SRC} missing -- run design/netlist.sh" >&2
  exit 1
}
cat "${DFF_NETLIST_SRC}" "${DECK_DFF}" >"${DUT_DFF}"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "mc-cp-mismatch --check: 2 samples per sub-campaign"
  for s in 1 2; do run_dc "${s}" "${tmpdir}/dc.csv"; done
  for s in 1 2; do run_sw "${s}" "${tmpdir}/sw.csv"; done
  for s in 1 2; do run_pfd "${s}" "${tmpdir}/pfd.csv"; done
  for s in 1 2; do run_dff "${s}" "${tmpdir}/dff.csv"; done
  echo "${DC_HEADER}"; cat "${tmpdir}/dc.csv"
  echo "${SW_HEADER}"; cat "${tmpdir}/sw.csv"
  echo "${PFD_HEADER}"; cat "${tmpdir}/pfd.csv"
  echo "${DFF_HEADER}"; cat "${tmpdir}/dff.csv"
  exit 0
fi

echo "mc-cp-mismatch: N_DC=${N_DC} N_SW=${N_SW} N_PFD=${N_PFD} N_DFF=${N_DFF} at ${CORNER}/${TEMP}C/${VDD}V, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.dc.csv "${WORK}"/*.sw.csv "${WORK}"/*.pfd.csv "${WORK}"/*.dff.csv

seq 1 "${N_DC}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dc {} \"${WORK}/dc_{}.csv\""
seq 1 "${N_SW}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-sw {} \"${WORK}/sw_{}.csv\""
seq 1 "${N_PFD}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-pfd {} \"${WORK}/pfd_{}.csv\""
seq 1 "${N_DFF}" | xargs -P "$(simenv_jobs)" -I{} \
  "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dff {} \"${WORK}/dff_{}.csv\""

cat "${WORK}"/dc_*.csv | sort -t, -k1,1n -k2,2n >"${WORK}/dc_all.csv"
cat "${WORK}"/sw_*.csv | sort -t, -k1,1n >"${WORK}/sw_all.csv"
cat "${WORK}"/pfd_*.csv | sort -t, -k1,1n >"${WORK}/pfd_all.csv"
cat "${WORK}"/dff_*.csv | sort -t, -k1,1n >"${WORK}/dff_all.csv"

GOT_DC=$(wc -l <"${WORK}/dc_all.csv" | tr -d ' ')
GOT_SW=$(wc -l <"${WORK}/sw_all.csv" | tr -d ' ')
GOT_PFD=$(wc -l <"${WORK}/pfd_all.csv" | tr -d ' ')
GOT_DFF=$(wc -l <"${WORK}/dff_all.csv" | tr -d ' ')
[ "${GOT_DC}" -eq $(( N_DC * 3 )) ] || { echo "ERROR: expected $(( N_DC * 3 )) dc rows, got ${GOT_DC}" >&2; exit 1; }
[ "${GOT_SW}" -eq "${N_SW}" ] || { echo "ERROR: expected ${N_SW} sw rows, got ${GOT_SW}" >&2; exit 1; }
[ "${GOT_PFD}" -eq "${N_PFD}" ] || { echo "ERROR: expected ${N_PFD} pfd rows, got ${GOT_PFD}" >&2; exit 1; }
[ "${GOT_DFF}" -eq "${N_DFF}" ] || { echo "ERROR: expected ${N_DFF} dff rows, got ${GOT_DFF}" >&2; exit 1; }

# --------------------------------------------------------------------------
# Mint the evidence record.
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${NETLIST}" "${SNAPDIR}/${RID}-cppfd.spice"
cp "${DUT_DFF}" "${SNAPDIR}/${RID}-dff.spice"
SHA_CPPFD=$(simenv_sha256 "${SNAPDIR}/${RID}-cppfd.spice")
SHA_DFF=$(simenv_sha256 "${SNAPDIR}/${RID}-dff.spice")

# Archive every raw log -- see the record's Methodology field for why the
# sample count (not 45 PVT corners) is what sets the log count here.
for f in "${WORK}"/dc_seed*/ngspice.log; do
  seed=$(basename "$(dirname "${f}")" | sed 's/dc_seed//')
  cp "${f}" "${CORNERSDIR}/dc_${CORNER}_${TEMP}c_${VDD}v_seed$(printf '%03d' "${seed}").log"
done
for f in "${WORK}"/sw_seed*/ngspice.log; do
  seed=$(basename "$(dirname "${f}")" | sed 's/sw_seed//')
  cp "${f}" "${CORNERSDIR}/sw_${CORNER}_${TEMP}c_${VDD}v_vctrl${VCTRL_MID}_seed$(printf '%03d' "${seed}").log"
done
for f in "${WORK}"/pfd_seed*_d*/ngspice.log; do
  tag=$(basename "$(dirname "${f}")")
  cp "${f}" "${CORNERSDIR}/pfd_${CORNER}_${TEMP}c_${VDD}v_${tag#pfd_}.log"
done
for f in "${WORK}"/dff_seed*/ngspice.log; do
  seed=$(basename "$(dirname "${f}")" | sed 's/dff_seed//')
  cp "${f}" "${CORNERSDIR}/dff_${CORNER}_${TEMP}c_${VDD}v_seed$(printf '%03d' "${seed}").log"
done

OUT_DC="${CORNERSDIR}/mc_cp_dc.csv"
OUT_SW="${CORNERSDIR}/mc_cp_switch.csv"
OUT_PFD="${CORNERSDIR}/mc_pfd_cp.csv"
OUT_DFF="${CORNERSDIR}/mc_dff_ctq.csv"
{
  simenv_provenance "mc-cp-mismatch (dc)" "${RID}" "design/cp.sch (xschem export)" \
    "${CORNER}/${TEMP}C/${VDD}V, N=${N_DC} mismatch samples"
  echo "${DC_HEADER}"; cat "${WORK}/dc_all.csv"
} >"${OUT_DC}"
{
  simenv_provenance "mc-cp-mismatch (switch)" "${RID}" "design/cp.sch (xschem export)" \
    "${CORNER}/${TEMP}C/${VDD}V, Vctrl=${VCTRL_MID}, N=${N_SW} mismatch samples"
  echo "${SW_HEADER}"; cat "${WORK}/sw_all.csv"
} >"${OUT_SW}"
{
  simenv_provenance "mc-cp-mismatch (pfd_cp)" "${RID}" "design/pfd_cp.sch (xschem export)" \
    "${CORNER}/${TEMP}C/${VDD}V, dphi={-1n,0,+1n}, N=${N_PFD} mismatch samples"
  echo "${PFD_HEADER}"; cat "${WORK}/pfd_all.csv"
} >"${OUT_PFD}"
{
  simenv_provenance "mc-cp-mismatch (dff clk->Q)" "${RID}" "design/dff_tg_3v3.sch (committed netlist)" \
    "${CORNER}/${TEMP}C/${VDD}V, N=${N_DFF} mismatch samples x 2 (rise+fall)"
  echo "${DFF_HEADER}"; cat "${WORK}/dff_all.csv"
} >"${OUT_DFF}"

# --------------------------------------------------------------------------
# Statistics: mean, sample stddev (N-1), +/-3sigma, from the just-written
# CSVs so the record text cannot drift from the data. Data rows are neither
# the leading `simenv_provenance` `#` comment block nor the CSV header row --
# strip both before handing the column to awk.
# --------------------------------------------------------------------------
datarows() { grep -v '^#' "$1" | tail -n +2; }

stats_from_values() {
  # stats_from_values <newline-separated values> -> "mean sd n"
  awk '{x[n++]=$1; s+=$1} END{
    if (n==0) { print "nan nan 0"; exit }
    m=s/n
    for (i=0;i<n;i++) ss+=(x[i]-m)*(x[i]-m)
    sd = (n>1) ? sqrt(ss/(n-1)) : 0
    printf "%.6g %.6g %d\n", m, sd, n
  }'
}

stats() {
  # stats <file> <field> -> "mean sd n"
  datarows "$1" | awk -F, -v f="$2" '{print $f}' | stats_from_values
}

# Term 1: worst-|mismatch| per sample across the 3 Vctrl points, then stats
# over samples (matching the systematic record's "worst point in window").
DC_WORST=$(datarows "${OUT_DC}" | awk -F, '
  { a = ($5<0 ? -$5 : $5); s = $1; if (!(s in seen) || a > worst[s]) { worst[s] = a; seen[s] = 1 } }
  END { for (s in worst) print worst[s] }')
DC_STATS=$(echo "${DC_WORST}" | stats_from_values)
DC_MEAN=$(echo "${DC_STATS}" | awk '{print $1}'); DC_SD=$(echo "${DC_STATS}" | awk '{print $2}')

SW_STATS=$(stats "${OUT_SW}" 3)
SW_MEAN=$(echo "${SW_STATS}" | awk '{print $1}'); SW_SD=$(echo "${SW_STATS}" | awk '{print $2}')

PFD_Q_STATS=$(stats "${OUT_PFD}" 2)
PFD_Q_MEAN=$(echo "${PFD_Q_STATS}" | awk '{print $1}'); PFD_Q_SD=$(echo "${PFD_Q_STATS}" | awk '{print $2}')
PFD_T_STATS=$(stats "${OUT_PFD}" 6)
PFD_T_MEAN=$(echo "${PFD_T_STATS}" | awk '{print $1}'); PFD_T_SD=$(echo "${PFD_T_STATS}" | awk '{print $2}')

DFF_R_STATS=$(stats "${OUT_DFF}" 2)
DFF_R_MEAN=$(echo "${DFF_R_STATS}" | awk '{print $1}'); DFF_R_SD=$(echo "${DFF_R_STATS}" | awk '{print $2}')
DFF_F_STATS=$(stats "${OUT_DFF}" 3)
DFF_F_MEAN=$(echo "${DFF_F_STATS}" | awk '{print $1}'); DFF_F_SD=$(echo "${DFF_F_STATS}" | awk '{print $2}')

sig3() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.6g", (m<0?-m:m)+3*s}'; }
DC_3S=$(sig3 "${DC_MEAN}" "${DC_SD}")
SW_3S=$(sig3 "${SW_MEAN}" "${SW_SD}")
PFD_Q_3S=$(sig3 "${PFD_Q_MEAN}" "${PFD_Q_SD}")
PFD_T_3S=$(sig3 "${PFD_T_MEAN}" "${PFD_T_SD}")
DFF_R_3S=$(sig3 "${DFF_R_MEAN}" "${DFF_R_SD}")
DFF_F_3S=$(sig3 "${DFF_F_MEAN}" "${DFF_F_SD}")
DFF_SPREAD_3S=$(awk -v a="${DFF_R_3S}" -v b="${DFF_F_3S}" 'BEGIN{print (a>b)?a:b}')

echo "DC term1 |worst mismatch|: mean=${DC_MEAN}% sd=${DC_SD}% +-3sigma=${DC_3S}% (n=${N_DC})"
echo "SW term2a wskew: mean=${SW_MEAN}s sd=${SW_SD}s +-3sigma=${SW_3S}s (n=${N_SW})"
echo "PFD term3 qnet0: mean=${PFD_Q_MEAN}C sd=${PFD_Q_SD}C +-3sigma=${PFD_Q_3S}C (n=${N_PFD})"
echo "PFD term4 t_offset: mean=${PFD_T_MEAN}s sd=${PFD_T_SD}s +-3sigma=${PFD_T_3S}s (n=${N_PFD})"
echo "DFF tcq_r: mean=${DFF_R_MEAN}s sd=${DFF_R_SD}s +-3sigma=${DFF_R_3S}s (n=${N_DFF})"
echo "DFF tcq_f: mean=${DFF_F_MEAN}s sd=${DFF_F_SD}s +-3sigma=${DFF_F_3S}s (n=${N_DFF})"

verdict() { awk -v v="$1" -v b="$2" 'BEGIN{print (v<=b)?"PASS":"FAIL"}'; }
V1=$(verdict "${DC_3S}" 12)
V2A=$(verdict "${SW_3S}" 2e-9)
V3=$(verdict "${PFD_Q_3S}" 20e-15)
V4=$(verdict "${PFD_T_3S}" 3e-9)

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: design/README.md's "Up/down mismatch budget" table (not yet a
  ratified spec line -- #1 is open) -- does RANDOM gf180mcu device mismatch,
  on top of the SYSTEMATIC values \`cp-compliance\` and \`pfd-deadzone\`
  measure, fit inside the budget column that table states for terms 1, 2/2a,
  3 and 4; and, separately, what is the divider-retiming flop's own
  clk->Q mismatch contribution to static phase offset (an acceptance
  criterion of #15 alongside the charge-pump/PFD terms, not itself one of
  the table's numbered terms).
- **Model-capability gate (first step, per the original issue text)**: the
  open-PDK gf180mcu models DO carry usable per-instance mismatch/Monte Carlo
  data on this flow -- this is a finding, not a gap. Confirmed directly
  against \`sm141064.ngspice\`:
  - Every \`nfet_03v3_dss\`/\`pfet_03v3_dss\` subcircuit (the actual PDK
    devices \`nfet_03v3\`/\`pfet_03v3\` symbols netlist to, per DR-002
    Decision 3) declares \`mis_vth = agauss(0, var_vth, 1)\` and
    \`mis_k = agauss(0, var_k, 1)\`, Pelgrom-scaled by \`1/sqrt(W*L)\`, applied
    as \`delvto\`/\`mulu0\` on the internal MOSFET, gated by
    \`sw_stat_mismatch\` (\`design.ngspice\`'s global switch, default 0).
  - Because these \`agauss()\` calls live inside a \`.subckt\`, each
    instantiation gets an INDEPENDENT draw: two identical \`nfet_03v3_dss\`
    instances in the same circuit, same run, measurably disagree
    (\`v(d1)=1.176714\`/\`v(d2)=1.199711\` in a two-transistor sanity deck) --
    this is real per-device mismatch, not one shared global-corner shift.
  - \`sw_stat_mismatch\`'s draws are evaluated once at netlist PARSE time,
    before \`.control\` runs: \`set rndseed=N\` inside \`.control\` is
    provably too late (same seed, two runs, different draws) --
    \`.option rndseed=N\` at the top level IS read at parse time and gives
    bit-reproducible, seed-selectable draws (same seed -> same draws,
    confirmed across 3 independent seed values, including with
    \`sw_stat_mismatch=0\` giving seed-INDEPENDENT results as the negative
    control). \`sim/lib/simenv.sh\`'s \`simenv_run_deck\` now special-cases a
    \`rndseed=N\` kv into \`.option rndseed=N\` for exactly this reason (see
    that file's comment).
  - **What did NOT work, recorded for the next campaign that tries it**:
    running several mismatched replicas of the \`cp\`/\`pfd_cp\` hierarchy in
    ONE ngspice invocation (to amortize the ~1 s model-file parse cost) is
    valid for a plain DC operating point (verified with 20 parallel \`cp\`
    instances) and for the DFF-only bench (no cp_dumpbuf-loaded control
    node), but reliably hits \`Timestep too small\` in the \`cp\`/\`pfd_cp\`
    TRANSIENT benches once 2 or more replicas share the run --
    scaling with replica count, present even with \`sw_stat_mismatch=0\`
    (so it is a general stiffness of replicating \`cp_dumpbuf\`'s
    unity-gain-OTA-loaded control node under one Newton solve, not a
    mismatch-specific effect), and not resolved by raising \`itl1\`/\`itl4\`
    or \`gmin\`-stepping inside a practical wall-clock budget. This record's
    \`sw\`/\`pfd\` sub-campaigns therefore run ONE instance per invocation
    (see those decks' headers) at the cost of more invocations, which is
    reliable and is the same topology \`cp-compliance\`/\`pfd-deadzone\`
    already run at 45+ corners.
- **Netlist provenance**:
  - \`cp\`/\`pfd_cp\`: schematic (\`design/cp.sch\`, \`design/pfd_cp.sch\` and
    the cells below them) exported by \`design/netlist.sh --top pfd_cp\` ->
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-cppfd.spice\`, SHA-256
    \`${SHA_CPPFD}\`
  - \`dff_tg_3v3\` (divider-retiming flop): committed export
    \`design/netlist/dff_tg_3v3.spice\`, frozen together with
    \`tb_mc_dff_ctq.sp\` into
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-dff.spice\`, SHA-256
    \`${SHA_DFF}\`
  - Testbench decks contain stimulus, measurement and the
    \`sw_stat_mismatch\`/\`rndseed\` overrides only -- no hand-transcribed
    copy of the design.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    \`design/\` via \`design/netlist.sh\`; the cp/pfd_cp DUT is a schematic
    export, dff_tg_3v3 is design/netlist/'s committed export)" \
  "\`design.ngspice\` included first; this campaign explicitly OVERRIDES its
    default \`sw_stat_mismatch = 0\` to \`sw_stat_mismatch = 1\` for every run
    (\`sw_stat_global\` stays at the design.ngspice default 0 -- mismatch
    only, global process variation off, exactly sim/README.md's worked
    distribution example), with \`.option rndseed\` set per sample (see the
    Statistical convention field)")
- **Corner matrix run**: ONE nominal PVT point --
  \`${CORNER}\` (-> \`.lib\` section \`typical\`) / ${TEMP} C / ${VDD} V.
  **Axes not swept**: temperature, supply and MOS process corner are all
  fixed at nominal; passive corner sections (\`res_*\`, \`mimcap_*\`,
  \`moscap_*\`) N/A -- the DUTs are \`nfet_03v3\`/\`pfet_03v3\` only. See the
  Claim field's model-capability note and this file's header comment for the
  justification sim/README.md requires for a subset-of-grid record: the mean
  of the systematic term is already corner-swept by \`cp-compliance\` /
  \`pfd-deadzone\`; this record's job is the ADDITIONAL dispersion random
  mismatch contributes on top, sampled at the nominal point.
- **Methodology / criteria / limitations**:
  - **dc** (term 1): \`alter\`+\`op\` at Vctrl = 0.9/1.65/2.4 V (not a
    continuous sweep -- a Monte Carlo sample needs the mismatch at the
    budget table's stated points, not the full I-V curve), \`N=${N_DC}\`
    single-instance invocations, one \`.option rndseed\` per sample. Reported
    statistic is the WORST-magnitude mismatch across the 3 Vctrl points per
    sample, matching \`cp-compliance\`'s own "worst point in window"
    convention for term 1.
  - **sw** (terms 2/2a): transient switching bench at Vctrl = 1.65 V ONLY
    (mid-window), \`N=${N_SW}\` single-instance invocations.
    **Scope decision, stated per sim/README.md's "single nominal point ...
    allowed with justification"**: design/README.md's post-#24 measurement
    shows term 2's Vctrl dependence is now FLAT to within the corner spread
    (0.41/0.21/0.26 ns of mean at 0.9/1.65/2.4 V) -- the dump-node buffer
    nulls the Vctrl-dependent tail-charge mechanism that used to make term 2
    vary strongly with Vctrl. On that basis this record treats the
    mid-window dispersion as representative of the whole-window term 2, and
    checks it against BOTH the term 2 (\`+-3 ns\`) and term 2a (\`+-2 ns\`)
    budget lines. A follow-on record that sweeps Vctrl explicitly for the
    statistical claim is the more rigorous version of this if term 2's
    flatness is ever in question.
  - **pfd** (terms 3/4 + PFD-path mismatch): full \`pfd_cp\` hierarchy (the
    real PFD driving the real charge pump, not an idealized detector) at
    Vctrl = 1.65 V, dphi in {-1 ns, 0, +1 ns}, \`N=${N_PFD}\` samples, 3
    invocations each (one per dphi) sharing one \`.option rndseed\` so the
    3 points of one sample see the SAME mismatch draw. \`qnet0\` = term 3;
    \`kd_wide = (q(+1n) - q(-1n)) / 2ns\` is the sample's own local detector
    gain; \`t_offset = qnet0 / kd_wide\` = term 4 (matching
    design/README.md's term 4 definition exactly, per-sample rather than
    from a corner-averaged Kd).
    **PFD-path mismatch is folded into this same measurement and is NOT
    separable from the charge pump's own mismatch here**: because the DUT is
    the whole PFD+CP hierarchy, mismatch in the PFD's own gates (edge
    detectors, SR latch, reset chain) changes \`qnet\`/\`kd_wide\` exactly the
    same way charge-pump device mismatch does, and design/README.md's own
    systematic methodology note makes the identical point ("term 3 measures
    the net the loop actually sees with the real PFD driving"). This record
    reports ONE combined PFD+CP statistical distribution for terms 3/4,
    honestly, rather than fabricating a PFD-only split this measurement
    cannot produce. A future campaign wanting the split would need a
    PFD-only charge-domain testbench (an idealized charge-pump load driven by
    the real PFD), which does not exist yet.
  - **dff** (divider-retiming flop): single clean 0->1 / 1->0 capture per
    invocation (2 ns before the measured clock edge -- comfortably inside
    every corner's setup margin per \`divider-ratio\`'s \`tb_dff_setup.sp\`),
    \`N=${N_DFF}\` invocations x 2 directions = $(( N_DFF * 2 )) samples.
    A clk->Q delay shift converts to a phase-offset contribution
    ONE-FOR-ONE (no detector-gain division): a retiming flop that fires
    later presents FB to the PFD later, which IS phase error at the PFD
    input, with no charge-pump gain in between. Reported separately from
    terms 1-4 because design/README.md's mismatch-budget table does not
    carry a divider-retiming row -- this is the acceptance criterion's
    second half, not a fifth budget-table term.
  - **Closed-loop reference-spur check: NOT performed, honest gap, not
    fabricated.** #15's acceptance criteria ask for this using #12's
    lock-time/output-range bench specifically, "not a separate ad hoc
    closed-loop harness" -- and #12 (\`Testbench: closed-loop lock
    acquisition and output-range coverage across PVT\`) is still open
    (\`loom:blocked\`/\`loom:triage\`) as of this run; \`sim/lock-time/\` and
    \`sim/output-range/\` do not exist on \`main\`. Building an ad hoc
    closed-loop harness here to satisfy this one criterion would directly
    violate the instruction it comes with, so this record does not attempt
    one. The open-loop terms above (1-4, all four of which are inputs to a
    closed-loop spur estimate) are fully substantiated; the closed-loop
    conversion of those terms into an actual spur level is DEFERRED pending
    #12, and should be a follow-on record (\`Supersedes\` this one, or a
    sibling record) once #12's bench exists -- not a re-opening of this
    issue's scope, per #13's precedent for recording an honest methodology
    gap rather than a fabricated number.
  - Bias generation is out of scope and idealized in every sub-campaign,
    exactly as \`cp-compliance\`/\`pfd-deadzone\`/\`devchar-cp\`: four ideal
    current sources at 4x the unit-leg current. The measured mismatch is
    therefore the output stage's (+ \`cp_dumpbuf\`'s) own; a real bias
    generator's mirror mismatch is additive and out of this record's scope
    (design/README.md's existing note on the budget table).
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off -- exactly sim/README.md's
  worked distribution example). Sample counts: \`N_DC=${N_DC}\`,
  \`N_SW=${N_SW}\`, \`N_PFD=${N_PFD}\`, \`N_DFF=${N_DFF}\` (x2 for dff's
  rise/fall). Distribution reported at mean +/- sample standard deviation
  (N-1 denominator) and at \`|mean| + 3*sigma\` (a normal-tail bound, not an
  order-statistic max -- credible at these sample sizes for a
  Pelgrom-mismatch-driven, plausibly-Gaussian quantity, but not a
  guaranteed worst case the way a 45-corner PVT sweep's max is). Seeds:
  sequential integers \`1..N\` per sub-campaign, passed via \`.option
  rndseed\` (see the Claim field's model-capability note); every seed's raw
  log is committed under \`corners/${RID}/\`.
- **Result**:

  | # | Term | Statistical (this record, mean / sd / \|mean\|+3sigma, n) | Budget (design/README.md) | Verdict |
  |---|---|---|---|---|
  | 1 | DC UP/DN mismatch, worst of 0.9/1.65/2.4 V | ${DC_MEAN}% / ${DC_SD}% / ${DC_3S}% | +-12% | **${V1}** |
  | 2 | Switching-time skew, whole window (assessed at mid-window, see Methodology) | ${SW_MEAN} s / ${SW_SD} s / ${SW_3S} s | +-3 ns | **$(verdict "${SW_3S}" 3e-9)** |
  | 2a | Switching-time skew, mid-window (Vctrl=1.65 V) | ${SW_MEAN} s / ${SW_SD} s / ${SW_3S} s | +-2 ns | **${V2A}** |
  | 3 | Residual net charge at zero phase error | ${PFD_Q_MEAN} C / ${PFD_Q_SD} C / ${PFD_Q_3S} C | +-20 fC | **${V3}** |
  | 4 | Static phase offset, q_zero / Kd | ${PFD_T_MEAN} s / ${PFD_T_SD} s / ${PFD_T_3S} s | +-3 ns | **${V4}** |

  **Divider-retiming flop clk->Q mismatch** (not a budget-table term; see
  Methodology):
  - Rise capture: mean=${DFF_R_MEAN} s, sd=${DFF_R_SD} s, \`|mean|+3sigma\`=${DFF_R_3S} s (n=${N_DFF})
  - Fall capture: mean=${DFF_F_MEAN} s, sd=${DFF_F_SD} s, \`|mean|+3sigma\`=${DFF_F_3S} s (n=${N_DFF})
  - Worst-direction \`|mean|+3sigma\`: ${DFF_SPREAD_3S} s -- a direct
    (one-for-one) phase-offset contribution, additive to term 4 above at the
    PFD input; not itself checked against a budget line because
    design/README.md's table does not carry one for this contribution.

  **Systematic vs. statistical, kept distinct (per #15's acceptance
  criteria)**: design/README.md's "Systematic (measured, all 45 PVT
  corners)" column (terms 1-4) is #24's tail-node-charge-exchange mechanism
  and \`cp\`'s finite output resistance -- corner-swept, \`sw_stat_mismatch =
  0\`. This record's numbers are the ADDITIONAL statistical dispersion
  \`sw_stat_mismatch = 1\` adds on top, at one nominal corner. They are not
  interchangeable and this record does not add them together (the budget
  column already allocates room for both; this record checks the
  \`|mean|+3sigma\` figure against the standalone budget line, which is how
  design/README.md states it).
- **Links**:
  - Testbenches: \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\`,
    \`tb_mc_cp_switch.sp\`, \`tb_mc_pfd_cp.sp\`, \`tb_mc_dff_ctq.sp\`,
    \`run.sh\`
  - Design: \`design/cp.sch\`, \`design/cp_dumpbuf.sch\`, \`design/pfd_cp.sch\`,
    \`design/pfd.sch\`, \`design/dff_tg_3v3.sch\`
  - Netlist snapshots:
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-cppfd.spice\`,
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-dff.spice\`
  - Raw logs: \`sim/mc-cp-mismatch/corners/${RID}/\`
  - Extracted metrics: \`sim/mc-cp-mismatch/corners/${RID}/mc_cp_dc.csv\`,
    \`mc_cp_switch.csv\`, \`mc_pfd_cp.csv\`, \`mc_dff_ctq.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #15)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "mc-cp-mismatch: wrote ${RECORD}"
echo "mc-cp-mismatch: wrote ${OUT_DC}, ${OUT_SW}, ${OUT_PFD}, ${OUT_DFF}"
echo "mc-cp-mismatch: wrote ${CORNERSDIR}/ ($(( N_DC + N_SW + N_PFD * 3 + N_DFF )) corner logs)"
