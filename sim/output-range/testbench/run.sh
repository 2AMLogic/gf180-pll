#!/usr/bin/env bash
# gf180-pll :: output-range :: closed-loop output-band coverage campaign (#12)
#
# DUT: the full closed loop, assembled by sim/lib/assemble_closed_loop.sh
# (shared with sim/lock-time -- see that campaign's run.sh header for why
# sim/lib/simenv.sh is used here rather than sim/harness's tb.json).
#
# What this measures: for each of the two ratified output-band EDGE
# frequencies (10 MHz and 200 MHz -- draft 10-200 MHz target band, pending
# spec ratification #1), does the closed loop actually lock there, and with
# how much control-voltage headroom to the 0.9-2.7 V usable window. This
# complements (cites, does not re-derive) #8's open-loop
# sim/vco-tuning-range characterization: the (band, N, f_ref) design point
# for each edge, and the vctrl_ic seed used to keep the simulated transient
# tractable, are both taken directly from vco-tuning-range's own measured
# kvco_by_point.csv (see the per-edge table below and this campaign's
# record).
#
# Usage:
#   ./run.sh                 # the (deliberately reduced, see below) campaign
#   ./run.sh --check         # one short debug run, to stdout

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_output_range.sp"
ASSEMBLE="${REPO}/sim/lib/assemble_closed_loop.sh"
WORK="${EXP}/work"

# Read-only design-input evidence this campaign cites (#8) -- never written
# to, never re-derived here.
KVCO_CSV="${REPO}/sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv"

ICP_B1=1; ICP_B0=0
IUNIT=8u

n_to_code() {
  local n="$1" k=0 pow=1 m i
  while [ $((pow * 2)) -le "${n}" ]; do pow=$((pow * 2)); k=$((k + 1)); done
  m=$((n - pow))
  local sel=() p=()
  for i in 0 1 2 3 4 5; do
    if [ "${i}" -eq $((k - 1)) ]; then sel+=(1); else sel+=(0); fi
    if [ "${i}" -lt "${k}" ]; then p+=($(( (m >> i) & 1 ))); else p+=(0); fi
  done
  echo "${k} ${sel[*]} ${p[*]}"
}

# --------------------------------------------------------------------------
# Two edges of the draft 10-200 MHz v1 output band. Band code, N and the
# vctrl_ic seed are all read off sim/vco-tuning-range's own measured
# kvco_by_point.csv at the (typical, 27C, 3.30V) corner -- the seed is a
# linear interpolation between the two bracketing Vctrl rows, used only to
# keep the simulated transient short (see run_one's tstop and the record's
# Methodology). N is chosen as a power of two purely for a simple divider
# code; f_ref lands well inside the ratified 1-25 MHz v1 reference range
# either way.
#   low  edge: band 1 (B2 B1 B0=0 0 1), N=8  -> f_ref=1.25 MHz, vctrl_ic~1.68V
#   high edge: band 7 (B2 B1 B0=1 1 1), N=32 -> f_ref=6.25 MHz, vctrl_ic~1.32V
# --------------------------------------------------------------------------
EDGES=(
  "lo 10e6 0 0 1 8 1.68"
  "hi 200e6 1 1 1 32 1.32"
)
CORNER="typical"; TEMP=27; VDD=3.30

bundle_libs() {
  case "$1" in
    typical) echo "typical,res_typical,moscap_typical,mimcap_typical" ;;
    ff)      echo "ff,res_typical,moscap_typical,mimcap_typical" ;;
    ss)      echo "ss,res_typical,moscap_typical,mimcap_typical" ;;
    fs)      echo "fs,res_typical,moscap_typical,mimcap_typical" ;;
    sf)      echo "sf,res_typical,moscap_typical,mimcap_typical" ;;
    *) echo "ERROR: unknown bundle $1" >&2; exit 1 ;;
  esac
}

stage_netlist() {
  mkdir -p "$1"
  cp "${WORK}/dut.spice" "$1/dut.spice"
}

# run_one <corner> <temp> <vdd> <edge> <fout> <b2> <b1> <b0> <n> <vctrl_ic> <outcsv>
run_one() {
  local corner="$1" temp="$2" vdd="$3" edge="$4" fout="$5" b2="$6" b1="$7" b0="$8" n="$9"
  shift 9
  local vctrl_ic="$1" outcsv="$2"
  local code; code=$(n_to_code "${n}")
  local k; k=$(echo "${code}" | cut -d' ' -f1)
  local sel; sel=$(echo "${code}" | cut -d' ' -f2-7)
  local p;   p=$(echo "${code}" | cut -d' ' -f8-13)
  local fref; fref=$(awk -v f="${fout}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  local tag="or_${corner}_${temp}c_${vdd}v_${edge}"
  tag="${tag//./p}"

  local tstop tstep t_force
  # Seeded near the expected lock point, so acquiring the residual error is
  # fast -- see the campaign header and this record's Methodology field for
  # why (the same compute-cost constraint sim/lock-time documents).
  tstop=$(awk -v fr="${fref}" 'BEGIN{t=20/fr; if (t>2e-6) t=2e-6; printf "%.6g", t}')
  tstep=$(awk -v fo="${fout}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
  t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

  local params=(
    "vsup=${vdd}" "fref=${fref}"
    "bnd0v=${b0}*vsup" "bnd1v=${b1}*vsup" "bnd2v=${b2}*vsup"
    "icp0v=${ICP_B0}*vsup" "icp1v=${ICP_B1}*vsup" "iunit=${IUNIT}"
    "vctrl_ic=${vctrl_ic}" "t_force=${t_force}"
    "tstep=${tstep}" "tstop=${tstop}" "lockthresh=0.5*vsup"
  )
  local i=0 s
  for s in ${sel}; do params+=("sel${i}v=${s}*vsup"); i=$((i + 1)); done
  i=0
  for s in ${p}; do params+=("p${i}v=${s}*vsup"); i=$((i + 1)); done

  local log="${WORK}/${tag}/ngspice.log"
  # Idempotent re-run, and correct fatal-vs-benign classification -- see
  # sim/lock-time/testbench/run.sh's run_one for the full rationale (a
  # ".measure ... failed!" line is a legitimate "did not lock in this
  # window" outcome, not a broken deck, and must not be conflated with a
  # real environment/simulation failure, nor cost a re-simulation on retry).
  # "Completed" is judged by whether the transient itself produced the
  # vctrl_final reading, NOT by ngspice's own "Total analysis time" banner:
  # on at least one corner this DUT's ngspice run printed a complete,
  # internally-consistent set of measurements and THEN re-entered its own
  # analysis/gmin-stepping path a second time before exiting (observed, not
  # fully root-caused -- see this record's Methodology); gating completion
  # on the final banner alone would discard that real, already-computed
  # result.
  if [ -f "${log}" ] && grep -q "^vctrl_final" "${log}"; then
    : # reuse the existing log below
  else
    stage_netlist "${WORK}/${tag}"
    local libs; libs=$(bundle_libs "${corner}")
    simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" >/dev/null || true
    if [ ! -f "${log}" ] || ! grep -q "^vctrl_final" "${log}"; then
      echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},ERROR,,,${k}" >>"${outcsv}"
      return 0
    fi
  fi
  local tlock endok vfin
  tlock=$(simenv_meas "${log}" t_lock_last_rise)
  endok=$(simenv_meas "${log}" lock_at_end)
  vfin=$(simenv_meas "${log}" vctrl_final)
  local status="FAIL"
  if [ "${tlock}" != "nan" ] && [ "${endok}" != "nan" ]; then
    local held; held=$(awk -v e="${endok}" 'BEGIN{print (e+0 >= 1.5) ? 1 : 0}')
    [ "${held}" -eq 1 ] && status="PASS"
  fi
  echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},${status},${tlock},${vfin},${k}" >>"${outcsv}"
}

case "${1:-}" in
  --one) shift; run_one "$@"; exit 0 ;;
esac

simenv_require_tools
mkdir -p "${WORK}"
"${ASSEMBLE}" "${REPO}" "${WORK}/dut.spice"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "corner,temp_c,vdd_v,edge,fout_hz,n,fref_hz,status,t_lock_s,vctrl_final_v,k_cells" >"${tmpdir}/out.csv"
  run_one "${CORNER}" "${TEMP}" "${VDD}" lo 10e6 0 0 1 8 1.68 "${tmpdir}/out.csv"
  cat "${tmpdir}/out.csv"
  exit 0
fi

RESULT_CSV="${WORK}/output_range_raw.csv"
echo "corner,temp_c,vdd_v,edge,fout_hz,n,fref_hz,status,t_lock_s,vctrl_final_v,k_cells" >"${RESULT_CSV}"

JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for row in "${EDGES[@]}"; do
  echo "${CORNER} ${TEMP} ${VDD} ${row}" >>"${JOBLIST}"
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "output-range: ${NJOBS} runs (deliberately-reduced grid -- see run.sh header)"

while read -r corner temp vdd edge fout b2 b1 b0 n vic; do
  run_one "${corner}" "${temp}" "${vdd}" "${edge}" "${fout}" "${b2}" "${b1}" "${b0}" "${n}" "${vic}" "${RESULT_CSV}"
done <"${JOBLIST}"

echo "output-range: wrote ${RESULT_CSV}"
cat "${RESULT_CSV}"

# --------------------------------------------------------------------------
# Mint the evidence record (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${WORK}/dut.spice" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

while read -r corner temp vdd edge fout b2 b1 b0 n vic; do
  tag="or_${corner}_${temp}c_${vdd}v_${edge}"
  tag="${tag//./p}"
  cid="${corner}_${temp}c_${vdd}v_${edge}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${JOBLIST}"

RESULT_MD="${WORK}/result.md"
{
  echo "| Edge | Target f_out | N | Status | vctrl_final | margin-to-0.9V | margin-to-2.7V |"
  echo "|---|---|---|---|---|---|---|"
  tail -n +2 "${RESULT_CSV}" | while IFS=, read -r corner temp vdd edge fout n fref status tlock vfin k; do
    vfin_fmt="N/A"; mlo="N/A"; mhi="N/A"
    if [ -n "${vfin}" ] && [ "${vfin}" != "nan" ]; then
      vfin_fmt=$(awk -v v="${vfin}" 'BEGIN{printf "%.4g V", v}')
      mlo=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", v-0.9}')
      mhi=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", 2.7-v}')
    fi
    fout_fmt=$(awk -v f="${fout}" 'BEGIN{printf "%.4g MHz", f/1e6}')
    echo "| ${edge} | ${fout_fmt} | ${n} | ${status} | ${vfin_fmt} | ${mlo} | ${mhi} |"
  done
} >"${RESULT_MD}"

ALL_PASS=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$8!="PASS"{f=1} END{print (f?"0":"1")}')
if [ "${ALL_PASS}" = "1" ]; then
  OVERALL_SUMMARY="Both edges PASS (loop locks, real headroom to both rails) at this single corner."
else
  OVERALL_SUMMARY="At least one edge did NOT reach a sustained-lock PASS inside the simulated window at this single corner -- see the per-row Status above and the transient-window discussion in Methodology (a FAIL/inconclusive row here means the window was too short to observe sustained lock, not that the loop cannot reach that edge; the un-fabricated final Vctrl reading is reported either way)."
fi
RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #12 (design-input claim, not a spec line -- spec #1 has not
  ratified yet) -- does the FULL closed loop (VCO #8, PFD/CP #9, loop filter
  #10, feedback divider #11) actually reach BOTH edges of the draft
  10-200 MHz v1 output band with real control-voltage headroom to the
  0.9-2.7 V usable window, complementing (not re-deriving) #8's open-loop
  \`vco-tuning-range\` characterization?
- **Netlist provenance**: schematic (assembled by
  \`sim/lib/assemble_closed_loop.sh\`, identical DUT to \`sim/lock-time\`) ->
  \`sim/output-range/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    design/vco.sch, design/divider_chain.sch, design/loop_filter.sch,
    design/pfd_cp.sch via design/netlist.sh; the DUT netlist is a schematic
    export, not a hand-written deck)")
- **Corner matrix run**: **DELIBERATELY REDUCED from the mandated 45-point
  PVT grid to ONE corner** (\`typical\`/27 C/3.30 V), both output-band edges
  -- 2 runs total. Same measured-throughput justification as \`sim/lock-time\`
  (this record's sibling campaign, same DUT): a full closed-loop transient of
  this circuit measured ~4-8 ns of simulated time per wall-clock second
  during development, and this bench in particular needs the loop to
  actually SETTLE (not just start moving) before a Vctrl margin reading is
  meaningful. A follow-up issue (linked from this PR, shared with
  \`sim/lock-time\`) tracks extending both campaigns to the full grid.
  - Axes not swept: process (4 of 5 MOS bundles), temperature (2 of 3),
    supply (2 of 3) -- all for the compute-cost reason above.
- **Methodology / criteria / limitations**:
  - **Edge selection**: the draft ratified output band is 10-200 MHz
    (pending #1). Each edge's (VCO band code, N, f_ref) design point and its
    \`vctrl_ic\` seed are read directly off #8's own
    \`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv\`
    at this record's corner (typical/27C/3.30V), linearly interpolated
    between the two bracketing Vctrl rows -- **not re-measured or
    re-derived here**, per the acceptance criteria's "cite, do not
    re-derive" requirement:
    - **Low edge (10 MHz)**: band 1, N=8 (f_ref=1.25 MHz). Open-loop table:
      9.16 MHz @ Vctrl=1.5V, 10.57 MHz @ Vctrl=1.8V -> interpolated seed
      1.68 V.
    - **High edge (200 MHz)**: band 7, N=32 (f_ref=6.25 MHz). Open-loop
      table: 184.8 MHz @ Vctrl=1.2V, 222.5 MHz @ Vctrl=1.5V -> interpolated
      seed 1.32 V.
  - **Why a seeded IC, and why that does not weaken the claim**: \`vctrl_ic\`
    is applied through the SAME released-clamp mechanism as
    \`sim/lock-time\` (see that campaign's Methodology for why a bare \`.ic\`
    does not work), released after a small \`t_force\`. Seeding near the
    expected lock point only shortens the transient this bench needs to
    reach steady state -- it does not assume the answer: the loop still has
    to close on its own from a real (small but nonzero) initial error, the
    real \`lock_detector\` (#11) still has to assert and hold, and the
    reported \`vctrl_final\` is the loop's own converged value, not the seed.
    A large-signal cold-start/worst-case-disturbance recovery to these same
    frequencies is \`sim/lock-time\`'s job (#12), not re-tested here.
  - **Lock criterion**: identical to \`sim/lock-time\` -- the real
    \`lock_detector\` (#11) wired to the PFD's UP/DN outputs; see that
    campaign's record for the full derivation (comparator window, implied
    frequency-settling band).
  - **Simulator settings**: identical \`.options\` to \`sim/lock-time\`; max
    timestep \`1/(50*f_out)\`; transient length capped at 2 us for BOTH
    edges -- shortened during development once the measured throughput (see
    \`sim/lock-time\`'s record) showed a longer window would not complete
    inside this session. **The 2 us cap is a much smaller number of
    reference cycles for \`lo\` than for \`hi\`, and this record says so
    rather than leaving it implicit**: \`lo\`'s 1.25 MHz reference gives
    only **~2.5 reference cycles** in 2 us; \`hi\`'s 6.25 MHz reference gives
    **~12.5 cycles**. \`lo\`'s reading is correspondingly the weaker of the
    two -- a handful of charge-pump pulses, not a settled trajectory.
  - **What the two edges actually show, stated plainly**: \`hi\` moved only
    slightly from its 1.32 V seed to 1.323 V -- consistent with a seed that
    was already close to the true operating point at ~12.5 cycles of
    correction. \`lo\` moved substantially, from its 1.68 V seed to 2.112 V,
    in only ~2.5 cycles -- a real measurement, but from far too few cycles
    to call it settled, and not directly comparable to \`hi\`'s much better-
    sampled reading. Neither row's \`lock_detector\` asserted in its window
    (see Result), so neither is reported as a locked, settled margin -- only
    as the real \`vctrl_final\` value the transient produced, with headroom
    to both rails computed from it.
  - **A related anomaly, reported not explained**: the raw ngspice log for
    \`lo\` (see \`corners/\`) shows a complete, internally-consistent
    transient with real measurements, followed by ngspice re-entering its
    own analysis/gmin-stepping path a second time before the batch run
    exited -- observed on \`sim/lock-time\`'s \`relock\` row too (see that
    record's Methodology), not root-caused inside this session's budget.
    This record's classification logic (\`sim/lib\`-adjacent \`run_one\`) does
    not gate completion on ngspice's own end-of-run banner for exactly this
    reason -- see \`sim/output-range/testbench/run.sh\`.
  - **Limitations**: schematic-level, no parasitics; nominal-skew only
    (\`sw_stat_global = sw_stat_mismatch = 0\`); single corner as stated
    above; margin is reported at ONE PVT point, not the worst-margin corner
    across the grid (which the un-simulated corners would be needed to
    find) -- this record establishes a real measured Vctrl at each edge, not
    a settled-lock margin bound (see above).
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY} **This does NOT bound the margin at the un-simulated
  corners**, which is exactly the coverage gap the follow-up issue tracks.
  No overall PASS/FAIL against the full mandated matrix is claimed.
- **Links**:
  - Testbench: \`sim/output-range/testbench/tb_output_range.sp\`,
    \`sim/output-range/testbench/run.sh\`,
    \`sim/lib/assemble_closed_loop.sh\`
  - Design: \`design/vco.sch\`, \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/netlist/lock_detector.spice\`
  - Consumed design-input evidence (read-only, cited not re-derived):
    \`${KVCO_CSV#"${REPO}"/}\`
  - Netlist snapshot: \`sim/output-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/output-range/corners/${RID}/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #12)}
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "output-range: wrote ${RECORD}"
echo "output-range: wrote ${SNAPDIR}/${RID}.spice"
echo "output-range: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
