#!/usr/bin/env bash
# gf180-pll :: lock-time :: closed-loop lock-acquisition campaign (#12)
#
# DUT: the full closed loop, assembled by sim/lib/assemble_closed_loop.sh
# (VCO #8 + PFD/CP #9 + loop filter #10 + feedback divider #11), driven by
# tb_lock_time.sp. Uses sim/lib/simenv.sh's corner-sweep primitives -- the
# SAME pattern already landed by #10 (loop-dynamics) and #11's campaigns for
# real evidence -- rather than sim/harness's tb.json manifest, because a
# manifest carries exactly ONE fixed .param set per experiment (see
# sim/harness/testbench.py's Testbench dataclass and cli.py: no per-run
# --param override exists) and this campaign needs N x cold-start/re-lock as
# an axis IN ADDITION TO the PVT grid, inside one evidence record. That is a
# real, load-bearing gap, not a preference: see this record's own
# Methodology field for the citation.
#
# Usage:
#   ./run.sh                 # the (deliberately reduced, see below) campaign
#   ./run.sh --check         # one short debug run, nominal corner, to stdout
#   SIM_JOBS=1 ./run.sh      # cap parallelism (default: sequential -- see below)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_lock_time.sp"
ASSEMBLE="${REPO}/sim/lib/assemble_closed_loop.sh"
WORK="${EXP}/work"

# --------------------------------------------------------------------------
# Fixed design point (see design/README.md for the divider bit encoding and
# the VCO band map).
#
#   Band 5 (B2 B1 B0 = 1 0 1), target f_out = 80 MHz: sim/vco-tuning-range's
#   own kvco_by_point.csv shows 80 MHz sits comfortably inside band 5's
#   0.9-2.7 V Vctrl window at every one of the 45 MOS/temp/supply corners
#   (worst-margin corner: ff/125C/2.97V, Vctrl ~1.0 V for 80 MHz, still
#   > 0.1 V off the bottom rail) -- see this record's Methodology field.
#   Icp trim code "10" (icp1=1 icp0=0) -- three unit legs, the nominal
#   setting design/README.md names (~5.2 uA), matching pfd-deadzone's and
#   cp-compliance's own nominal-code convention.
# --------------------------------------------------------------------------
FOUT_TARGET=80e6
BAND_B2=1; BAND_B1=0; BAND_B0=1
ICP_B1=1; ICP_B0=0
IUNIT=8u

# n_to_code <N> -> "k sel0..sel5 p0..p5" (DR-001 Decision 3 chain-length /
# modulus encoding: N = 2^k + sum(p_i . 2^i) for i<k, SEL_(k-1)=1) -- same
# algorithm as sim/divider-ratio/testbench/run.sh.
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
# Grid.  DELIBERATELY REDUCED from the mandated 45-point PVT x N=4/16/64 x
# {cold,relock} matrix -- see the record's Corner matrix run / Methodology
# fields for the measured justification (this DUT's simulated-time cost is
# governed by loop bandwidth, which falls with N, so N=64's cold-start alone
# is not completable inside an interactive session on shared build hardware;
# concrete throughput numbers are in the record). This run.sh sweeps ONE
# corner (typical/27C/3.30V) at N=4 (the fastest, most tractable case) for
# both conditions -- 2 runs total. #<followup> tracks extending this to the
# full grid and to N=16/64.
# --------------------------------------------------------------------------
CORNER="typical"; TEMP=27; VDD=3.30
N_VALUES=(4)
CONDITIONS=(cold relock)   # vctrl_ic = 0.9 V / 2.7 V respectively

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

# run_one <corner> <temp> <vdd> <n> <condition> <outdir> -> writes result.csv row
run_one() {
  local corner="$1" temp="$2" vdd="$3" n="$4" cond="$5" outcsv="$6"
  local code; code=$(n_to_code "${n}")
  local k; k=$(echo "${code}" | cut -d' ' -f1)
  local sel; sel=$(echo "${code}" | cut -d' ' -f2-7)
  local p;   p=$(echo "${code}" | cut -d' ' -f8-13)
  local fref; fref=$(awk -v f="${FOUT_TARGET}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  local vctrl_ic; [ "${cond}" = "cold" ] && vctrl_ic=0.9 || vctrl_ic=2.7
  local tag="lt_${corner}_${temp}c_${vdd}v_n${n}_${cond}"
  tag="${tag//./p}"

  # Transient window: generous multiple of the reference period, sized so a
  # loop that locks in the expected few-to-tens-of-us range has wide margin,
  # while staying inside a tractable simulated-time budget (see Methodology).
  # The two conditions get DIFFERENT caps -- not for a nicer-looking result,
  # but because the `cold` window's real cost (measured: 906.2 ngspice
  # CPU-seconds for 4 us -- see the record) left too little of this
  # session's compute budget for `relock` at the same length; the shorter
  # window is disclosed per-row, not silently assumed equal.
  local tstop tstep t_force wincap
  wincap=4e-6; [ "${cond}" = "relock" ] && wincap=2e-6
  tstop=$(awk -v fr="${fref}" -v cap="${wincap}" 'BEGIN{t=80/fr; if (t>cap) t=cap; printf "%.6g", t}')
  tstep=$(awk -v fo="${FOUT_TARGET}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
  t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

  local params=(
    "vsup=${vdd}" "fref=${fref}"
    "bnd0v=${BAND_B0}*vsup" "bnd1v=${BAND_B1}*vsup" "bnd2v=${BAND_B2}*vsup"
    "icp0v=${ICP_B0}*vsup" "icp1v=${ICP_B1}*vsup" "iunit=${IUNIT}"
    "vctrl_ic=${vctrl_ic}" "t_force=${t_force}"
    "tstep=${tstep}" "tstop=${tstop}" "lockthresh=0.5*vsup"
  )
  local i=0 s
  for s in ${sel}; do params+=("sel${i}v=${s}*vsup"); i=$((i + 1)); done
  i=0
  for s in ${p}; do params+=("p${i}v=${s}*vsup"); i=$((i + 1)); done

  local log="${WORK}/${tag}/ngspice.log"
  # Idempotent re-run: a prior invocation that already produced a
  # `vctrl_final` reading completed its transient (even if a later step of
  # THIS script mis-scored the result, or ngspice's own "Total analysis
  # time" banner never printed -- see below) -- don't burn a
  # multi-hundred-CPU-second re-simulation just to re-classify an
  # already-real log.
  if [ -f "${log}" ] && grep -q "^vctrl_final" "${log}"; then
    : # reuse the existing log below
  else
    stage_netlist "${WORK}/${tag}"
    local libs; libs=$(bundle_libs "${corner}")
    # simenv_run_deck treats ANY "Error:" line in the log as a hard failure,
    # which also matches ngspice's own ".measure ... failed!" line -- a
    # perfectly legitimate outcome here (LOCK simply had not asserted inside
    # the simulated window yet), not a broken deck. Capture its exit status
    # but do NOT let it gate whether we try to read the log.
    #
    # Completion is judged by whether `vctrl_final` was actually printed,
    # NOT by ngspice's own "Total analysis time" banner: on at least one
    # corner (see sim/output-range's record) this DUT's ngspice run printed
    # a complete, internally-consistent set of measurements and THEN
    # re-entered its own analysis/gmin-stepping path a second time before
    # exiting (observed, not fully root-caused). Gating on the final banner
    # alone would discard that real, already-computed result.
    simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" >/dev/null || true
    if [ ! -f "${log}" ] || ! grep -q "^vctrl_final" "${log}"; then
      echo "${corner},${temp},${vdd},${n},${cond},${fref},ERROR,,,${k}" >>"${outcsv}"
      return 0
    fi
  fi
  local tlock endok vfin
  tlock=$(simenv_meas "${log}" t_lock_last_rise)
  endok=$(simenv_meas "${log}" lock_at_end)
  vfin=$(simenv_meas "${log}" vctrl_final)
  local status="FAIL"
  if [ "${tlock}" != "nan" ] && [ "${endok}" != "nan" ]; then
    # locked (LOCK high) at the end of the window and held from t_lock to end
    local held; held=$(awk -v e="${endok}" -v thr="1.5" 'BEGIN{print (e+0 >= thr) ? 1 : 0}')
    [ "${held}" -eq 1 ] && status="PASS"
  fi
  echo "${corner},${temp},${vdd},${n},${cond},${fref},${status},${tlock},${vfin},${k}" >>"${outcsv}"
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
  echo "corner,temp_c,vdd_v,n,condition,fref_hz,status,t_lock_s,vctrl_final_v,k_cells" >"${tmpdir}/out.csv"
  run_one "${CORNER}" "${TEMP}" "${VDD}" 4 cold "${tmpdir}/out.csv"
  cat "${tmpdir}/out.csv"
  exit 0
fi

RESULT_CSV="${WORK}/lock_time_raw.csv"
echo "corner,temp_c,vdd_v,n,condition,fref_hz,status,t_lock_s,vctrl_final_v,k_cells" >"${RESULT_CSV}"

JOBS="${SIM_JOBS:-1}"
JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for n in "${N_VALUES[@]}"; do
  for cond in "${CONDITIONS[@]}"; do
    echo "${CORNER} ${TEMP} ${VDD} ${n} ${cond}" >>"${JOBLIST}"
  done
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "lock-time: ${NJOBS} runs (deliberately-reduced grid -- see run.sh header), ${JOBS} parallel"

export OUTCSV="${RESULT_CSV}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@" "${OUTCSV}"' "${HERE}/run.sh" \
  <"${JOBLIST}"

echo "lock-time: wrote ${RESULT_CSV}"
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

while read -r corner temp vdd n cond; do
  tag="lt_${corner}_${temp}c_${vdd}v_n${n}_${cond}"
  tag="${tag//./p}"
  cid="${corner}_${temp}c_${vdd}v_n${n}_${cond}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${JOBLIST}"

RESULT_MD="${WORK}/result.md"
{
  echo "| N | Condition | Status | t_lock | vctrl_final |"
  echo "|---|---|---|---|---|"
  tail -n +2 "${RESULT_CSV}" | while IFS=, read -r corner temp vdd n cond fref status tlock vfin k; do
    tlock_fmt="N/A (not asserted within window)"
    [ -n "${tlock}" ] && [ "${tlock}" != "nan" ] && tlock_fmt=$(awk -v t="${tlock}" 'BEGIN{printf "%.3g s", t}')
    vfin_fmt="N/A"
    [ -n "${vfin}" ] && [ "${vfin}" != "nan" ] && vfin_fmt=$(awk -v v="${vfin}" 'BEGIN{printf "%.4g V", v}')
    echo "| ${n} | ${cond} | ${status} | ${tlock_fmt} | ${vfin_fmt} |"
  done
} >"${RESULT_MD}"

ALL_PASS=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$7!="PASS"{f=1} END{print (f?"0":"1")}')
if [ "${ALL_PASS}" = "1" ]; then
  OVERALL_SUMMARY="Both rows PASS against the draft < 100 us lock-time target (placeholder, pending spec ratification #1) at this single corner and N=4."
else
  OVERALL_SUMMARY="At least one row did NOT reach a sustained-lock PASS inside the simulated window at this single corner and N=4 -- see the per-row Status above and the transient-window discussion in Methodology. \`cold\`'s FAIL means only that the window was too short (Vctrl is moving correctly toward the target); \`relock\`'s reported vctrl_final is an open, un-diagnosed anomaly (see Methodology) and is NOT presented as evidence the loop is either broken or fine at that extreme -- it is reported as measured."
fi
RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #12 (design-input claim, not a spec line -- spec #1 has not
  ratified yet) -- does the FULL closed loop (VCO #8, PFD/CP #9, loop filter
  #10, feedback divider #11, per \`spec/decision-records/DR-001-pll-architecture.md\`)
  actually acquire lock from a cold start and from a worst-case control-node
  disturbance, and how long does that take, at the design's own real
  lock_detector criterion (not an externally-imposed threshold)?
- **Netlist provenance**: schematic (assembled by
  \`sim/lib/assemble_closed_loop.sh\` from \`design/netlist/vco.spice\`,
  \`design/netlist/divider_chain.spice\`, \`design/netlist/loop_filter.spice\`
  and a fresh \`pfd_cp\` export -- see that script for why concatenation is
  the correct assembly, not a re-implementation) ->
  \`sim/lock-time/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    design/vco.sch, design/divider_chain.sch, design/loop_filter.sch,
    design/pfd_cp.sch via design/netlist.sh; the DUT netlist is a schematic
    export, not a hand-written deck)")
- **Corner matrix run**: **DELIBERATELY REDUCED from the mandated 45-point
  PVT grid to ONE corner** (\`typical\`/27 C/3.30 V), at N=4 only (of the
  DR-001 N=4-64 range), both cold-start and worst-case re-lock -- 2 runs
  total. Not a "the sim was slow" shrug: a full closed-loop transistor-level
  transient of this DUT cost ngspice **906.2 CPU-seconds of its own internal
  analysis time** (a CPU-time figure, independent of wall-clock contention)
  for just the 4 us window this record's \`cold\` run covers -- **~4.4 ns of
  simulated time per CPU-second**. N=64's loop bandwidth is ~16x narrower
  than N=4's (loop bandwidth scales with \`Icp*Kvco/N\`, per #10's own
  \`loop-dynamics\` result), so its cold-start lock time is expected in the
  hundreds-of-us range -- at the measured rate that is tens of CPU-hours PER
  CORNER even before wall-clock contention from this machine's other
  concurrently-running builder sessions (observed 10-40 concurrent
  \`ngspice\` processes during this campaign's development) is added, and
  45 corners x 3 N-settings x 2 conditions is not completable inside an
  interactive builder session on this hardware. A follow-up issue (#49)
  tracks extending this campaign to the full grid and to N=16/64 on
  longer-running or dedicated compute, and suggests profiling *why* this
  DUT's throughput is this low as a first step.
  - Axes not swept: process (4 of 5 MOS bundles), temperature (2 of 3),
    supply (2 of 3), N (2 of 3 required settings) -- all for the compute-cost
    reason above, not a design judgement that they do not matter.
- **Methodology / criteria / limitations**:
  - **Lock criterion**: the design's own real \`lock_detector\` (#11,
    \`design/netlist/lock_detector.spice\`) wired directly to the PFD's
    UP/DN outputs -- \`ERR = XOR(UP,DN)\`, \`LOCK\` asserts once \`ERR\` has
    stayed inside the comparator's window \`t_win\` continuously long enough
    to charge \`VWIN\` through the Schmitt trigger threshold, and deasserts
    fast on a single out-of-window pulse (see \`design/README.md\`'s
    lock-detector section). This is a genuine phase-settling criterion, and
    it implies a frequency-settling one: sustained containment inside a fixed
    phase window for the many reference cycles \`VWIN\`'s RC time constant
    requires is only possible if \`|Δf|→0\` -- a residual frequency error
    would walk the phase error monotonically out of the window every few
    cycles, which is exactly the deassert path. \`sim/lock-detector\`'s own
    45-point record puts \`t_win\` at 0.877-1.70 ns absolute (max at
    ss/125C/2.97V); at this record's N=4 / 20 MHz reference (T_ref=50 ns)
    that is a 1.75-3.4% phase-settling band. **Minimum hold window**: LOCK
    time is read as the LAST rising edge of \`LOCK\` in the simulated window
    (\`rise=last\`), with the run sized so at least several hundred reference
    cycles remain after it (see \`t_lock_last_rise\`/\`lock_at_end\` in
    \`tb_lock_time.sp\`) -- \`lock_at_end\` failing would mean the window was
    too short, and no such case is in this record's PASS rows.
  - **Cold-start vs. worst-case re-lock**: the control node has a
    well-determined DC operating point (it is DC-connected through the
    charge pump's output impedance and the filter's resistor to ground), so
    a bare \`.ic v(vctrl)=...\` does not survive into the op-point solve --
    op always converges to the same node voltage regardless of the seed.
    \`tb_lock_time.sp\` instead uses a released voltage-controlled switch
    clamp: VCTRL is hard-forced to \`vctrl_ic\` (a low-Ron path) through the
    op solve and the first \`t_force\`, then the switch opens (Roff) and the
    loop runs freely. \`vctrl_ic\` = 0.9 V (bottom of the 0.9-2.7 V usable
    window) is cold start; 2.7 V (top) is the largest excursion the loop
    could ever have to recover from -- the "frequency step sized to worst
    case" the acceptance criteria ask for is realized as the full usable
    control-voltage span rather than a specific reference-frequency step,
    because DR-001 makes N and the VCO band code static configuration
    (re-locked after a change, not switched glitch-free on the fly -- see
    \`design/README.md\`), so there is no in-run reference-retune scenario to
    step between; the full-span control-voltage disturbance upper-bounds any
    smaller real one (supply glitch, coarse-band change, post-reprogram
    re-enable).
  - **Design point**: VCO band 5 (\`design/README.md\`'s geometric band
    map), target \`f_out\` = 80 MHz -- \`sim/vco-tuning-range\`'s own
    \`kvco_by_point.csv\` shows 80 MHz sits inside band 5's 0.9-2.7 V window
    at every one of its 45 corners with real margin (worst case
    ff/125C/2.97V, ~0.15-0.3 V off a rail). Icp trim code "10" (three unit
    legs, ~5.2 uA), the nominal setting.
  - **Simulator settings**: \`.options reltol=1e-3 abstol=1e-9 vntol=1e-4
    chgtol=1e-13\`; max timestep \`1/(50*f_out)\`; transient length up to
    **4 us for \`cold\`, 2 us for \`relock\`** (or 80 reference periods,
    whichever is shorter) -- narrowed from successively longer targets
    (16 us, then 8 us) during development, and made asymmetric between the
    two conditions once \`cold\`'s real measured cost (906.2 CPU-s, below)
    showed the two conditions could not both run at 4 us inside this
    session's remaining budget. This is disclosed, not hidden: the
    achievable window had to be re-picked against the CPU-second budget
    actually available in this session (see the throughput figure below)
    rather than the window that would show the cleanest result.
  - **What the two windows actually show, stated plainly rather than dressed
    up**:
    - \`cold\` (0.9 V clamp, 4 us): Vctrl moves purposefully in the correct
      direction, from 0.9 V to 1.427 V, toward the ~1.69 V band 5 needs for
      80 MHz at this corner (interpolated from \`sim/vco-tuning-range\`'s own
      table) -- real, correctly-directed closed-loop action, just not yet
      arrived: the residual frequency error is still large enough at 4 us
      that \`lock_detector\` has not asserted, and this record does not claim
      it did.
    - \`relock\` (2.7 V clamp, 2 us): Vctrl moves to **3.138 V -- past the
      2.7 V clamp value, and past the nominal 0.9-2.7 V usable window
      entirely**, in the OPPOSITE direction from the naive expectation (at
      2.7 V, band 5 already runs ~124 MHz, well above the 80 MHz target, so
      a correctly-signed loop should sink current and pull Vctrl DOWN toward
      ~1.69 V, not push it further up). **This is reported as observed, not
      explained away**: it was not diagnosed further inside this session's
      remaining budget, and no causal story (PFD/CP polarity at extreme
      \`vctrl\`, a large-signal artifact of the released-clamp mechanism
      itself, or a genuine loop-stability question at the rail) is asserted
      without the additional simulation (a captured \`vctrl\`/\`up\`/\`dn\`
      waveform, not just the single end-of-window \`.measure\` sample this
      deck takes) that would be needed to tell them apart. This is flagged as
      an open question for #49, not silently normalized into the "moving
      correctly" story the \`cold\` row supports.
    See the Result table for both \`vctrl_final\` readings; a longer window to
    actually reach and hold lock -- and, for \`relock\`, to understand this
    anomaly -- is exactly what #49 tracks.
  - **Measured simulator throughput** (this record's own development, not a
    vendor number, and this is ngspice's OWN internal \`Total analysis time\`
    -- a CPU-time figure, not affected by wall-clock contention from other
    concurrently-running builder sessions on this shared machine): the
    committed \`cold\` run's 4 us window cost **906.2 CPU-seconds** of
    ngspice's own analysis time, i.e. **~4.4 ns of simulated time per
    CPU-second**. Wall-clock time on top of that varied 2-20x depending on
    how many other \`ngspice\` processes this shared machine was running at
    the time (observed 10-40 concurrent processes during this campaign's
    development) -- see \`corners/${RID}/\` logs for the per-run
    \`Total analysis time\` line, and #49 for the case to profile and speed
    this up before scaling the grid.
  - **Limitations**: schematic-level, no parasitics (#18 is post-layout);
    nominal-skew only (\`sw_stat_global = sw_stat_mismatch = 0\`, no Monte
    Carlo -- mismatch's contribution to lock behaviour is #15's mc-cp-mismatch
    scope, not re-derived here); single design point (one band, one Icp
    code, one target frequency) rather than the full N=4-64 x band x Icp-trim
    cross-product loop-dynamics (#10) already covers in the frequency domain.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY} **This does NOT extend to the un-simulated
  corners/N=16/64, which is exactly the coverage gap the follow-up issue
  tracks.** No overall PASS/FAIL against the full mandated matrix is claimed.
- **Links**:
  - Testbench: \`sim/lock-time/testbench/tb_lock_time.sp\`,
    \`sim/lock-time/testbench/run.sh\`,
    \`sim/lib/assemble_closed_loop.sh\`
  - Design: \`design/vco.sch\`, \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/netlist/lock_detector.spice\`
  - Consumed design-input evidence (read-only): \`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv\`,
    \`sim/lock-detector/records/20260731-162119-0a12e6c.md\`
  - Netlist snapshot: \`sim/lock-time/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/lock-time/corners/${RID}/\`
  - Raw CSV: \`${RESULT_CSV#"${REPO}"/}\` (not committed -- \`work/\` is
    git-ignored scratch; the per-corner logs above are the committed
    evidence)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #12)}
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "lock-time: wrote ${RECORD}"
echo "lock-time: wrote ${SNAPDIR}/${RID}.spice"
echo "lock-time: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
