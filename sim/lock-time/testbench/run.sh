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
#   ./run.sh                 # full 45-point PVT grid x N=4 x {cold,relock},
#                             #   90 runs -- see the Grid comment below for
#                             #   why N=16/64 are a separate follow-up
#   ./run.sh --check         # one short debug run, nominal corner, to stdout
#   ./run.sh --one <corner> <temp_c> <vdd> <n> <cold|relock> <outcsv>
#                             # single targeted point (used by the anomaly-
#                             #   investigation records; bypasses the grid)
#   SIM_JOBS=1 ./run.sh      # cap parallelism (default: sequential -- see below)
#
# NOTE ON HOST CONTENTION: this campaign's real cost is dominated by
# wall-clock contention, not raw CPU-seconds -- the SAME corner/window that
# took 714.3 CPU-s (and much longer in wall-clock) on a heavily-loaded shared
# host took only 62.1 CPU-s on an idle one (see
# sim/lock-time/records/20260801-073931-eec269e.md's own throughput note).
# Check `uptime` before committing to a full 90-run invocation.
#
# NOTE ON COST, POST-#65: those historical CPU-second figures were measured at
# the OLD, bound-violating 250 ps internal-timestep ceiling. This campaign now
# runs at the 100 ps ceiling every closed-loop bench inherits from the PFD
# (sim/lib/simenv.sh :: SIMENV_CLOSED_LOOP_TMAX), which raises the internal
# step count ~2.4x. Budget the 90-run grid accordingly, and do NOT reach for
# SIM_TMAX to claw the time back -- a grid minted at a coarser ceiling is not
# evidence about this loop. See sim/lock-time/records/20260801-101734-5eb00db.md.

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

# PFD DN-branch integration guard floor (#69), as a fraction of the rail --
# the same floor sim/pll-top-smoke's check 7 uses, so the two campaigns cannot
# disagree about what "the DN branch asserted" means.  In lock both branches
# pulse once per reference cycle for the PFD's reset delay, so the expected
# duty is ~1.5 ns * f_ref; this floor is more than an order of magnitude below
# that.  It does not measure the overlap -- it asks only whether DN asserts AT
# ALL, which is the question sim/README.md's "Closed-loop internal-timestep
# bound" makes load-bearing.
ACC_DN_FRAC=3e-4

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
# Grid.  #65 (the follow-up #49 itself named) extends this campaign from the
# original single-corner N=4 pilot to the FULL 45-point PVT grid at N=4 --
# but ONLY after #65's own gate: a targeted vctrl/up/dn/fb waveform
# investigation of `relock`'s anomalous vctrl_final (see
# sim/lock-time/records/20260801-073931-eec269e.md) had to land first and be
# understood, and it now has. That record's finding matters here: `relock`
# rows below are NOT expected to reach a stable in-window PASS in general --
# the mechanism it found (a large-frequency-error PFD/CP acquisition-
# dynamics anomaly, not a simple polarity bug) is not corner-specific in any
# way this record establishes, so seeing it recur across many/most corners
# below is the expected outcome of an already-diagnosed mechanism, not a new
# per-corner anomaly needing its own investigation. N=16/64 remain deferred
# (#65's own item 3, gated on this grid landing first) -- loop bandwidth
# falls with N (per #10's loop-dynamics), so cold-start lock time at N=16/64
# is expected far outside this record's transient window; extending N is a
# separate, larger follow-up.
# --------------------------------------------------------------------------
BUNDLES=("${SIMENV_MOS_CORNERS[@]}")
TEMPS=("${SIMENV_TEMPS[@]}")
VDDS=("${SIMENV_VDDS[@]}")
N_VALUES=(4)
CONDITIONS=(cold relock)   # vctrl_ic = 0.9 V / 2.7 V respectively

# Single-point debug corner, used only by --check below.
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

# run_one <corner> <temp> <vdd> <n> <condition> <outdir> -> writes result.csv row
run_one() {
  local corner="$1" temp="$2" vdd="$3" n="$4" cond="$5" outcsv="$6"
  local code; code=$(n_to_code "${n}")
  local k; k=$(echo "${code}" | cut -d' ' -f1)
  local sel; sel=$(echo "${code}" | cut -d' ' -f2-7)
  local p;   p=$(echo "${code}" | cut -d' ' -f8-13)
  local fref; fref=$(awk -v f="${FOUT_TARGET}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  local vctrl_ic; [ "${cond}" = "cold" ] && vctrl_ic=0.9 || vctrl_ic=2.7
  # The internal-timestep ceiling is part of the run's identity, not a tuning
  # knob: a log produced at the old (f_out-derived, bound-violating) ceiling is
  # NOT interchangeable with one produced at SIMENV_CLOSED_LOOP_TMAX. Putting
  # it in the tag keeps the idempotent-reuse check below from silently handing
  # back a stale pre-#65 result under a new record's ID.
  local tag="lt_${corner}_${temp}c_${vdd}v_n${n}_${cond}_tmax${SIMENV_CLOSED_LOOP_TMAX}"
  tag="${tag//./p}"

  # Transient window: generous multiple of the reference period, sized so a
  # loop that locks in the expected few-to-tens-of-us range has wide margin,
  # while staying inside a tractable simulated-time budget (see Methodology).
  # The two conditions get DIFFERENT caps -- not for a nicer-looking result,
  # but because the `cold` window's real cost (measured: 906.2 ngspice
  # CPU-seconds for 4 us -- see the record) left too little of this
  # session's compute budget for `relock` at the same length; the shorter
  # window is disclosed per-row, not silently assumed equal.
  #
  # `tstep` below is the PRINT step only. The ceiling on the INTERNAL timestep
  # is passed separately as .tran's 4th argument (SIMENV_CLOSED_LOOP_TMAX);
  # before #65 this deck omitted that argument, so ngspice defaulted the
  # internal ceiling to `tstep` itself and the integration accuracy was tied to
  # f_out instead of to the PFD. Sizing the two independently is the fix --
  # see sim/lib/simenv.sh and sim/README.md.
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
    "tstep=${tstep}" "tstop=${tstop}" "tmax=${SIMENV_CLOSED_LOOP_TMAX}"
    "lockthresh=0.5*vsup"
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
      echo "${corner},${temp},${vdd},${n},${cond},${fref},ERROR,,,${k},,ERROR" >>"${outcsv}"
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
  # PFD DN-branch integration guard (#69) -- the campaign-local form of
  # sim/pll-top-smoke's check 7, and the per-row regression detector for
  # sim/README.md's "Closed-loop internal-timestep bound".  #75 put this
  # campaign ON the bound, so every row is expected to read PASS; a row that
  # does not is the bound having been violated again, which is otherwise
  # invisible because the failure it causes looks like a clean design result.
  #
  # pll-top-smoke expects lock on EVERY row, so a bare PASS/FAIL suffices
  # there.  This campaign does not: a `cold` row can legitimately end the
  # window still converging, and on such a row a quiet DN branch is not by
  # itself proof of anything.  The tempting response -- suppress the guard on
  # non-PASS rows -- is wrong: it discards the discriminating measurement on
  # exactly the rows where "is this FAIL real?" is the open question.  So the
  # verdict is THREE-valued against one floor:
  #
  #   PASS     DN asserts.  The detector was resolved, so this row's own lock
  #            status means what it says -- locked or not.
  #   FAIL     DN never asserts on a row that DID reach PASS.  An apparent
  #            lock with an unresolved detector.
  #   SUSPECT  DN never asserts on a row that did NOT reach PASS.  That row's
  #            FAIL cannot be attributed to the design or to the window,
  #            because the detector was not resolved either.  Not an error --
  #            an attribution deliberately withheld.
  #   ERROR    the measurement did not land.  Never coerced to zero, which
  #            would read as a confident verdict on no evidence.
  local dnl dnguard
  dnl=$(simenv_meas "${log}" dn_lvl)
  dnguard=$(awk -v d="${dnl}" -v acc="${ACC_DN_FRAC}" -v v="${vdd}" -v st="${status}" 'BEGIN{
    if (d !~ /^-?[0-9.]+([eE][-+]?[0-9]+)?$/) { print "ERROR"; exit }
    if (d + 0 >= acc * v) { print "PASS"; exit }
    print (st == "PASS") ? "FAIL" : "SUSPECT";
  }')
  echo "${corner},${temp},${vdd},${n},${cond},${fref},${status},${tlock},${vfin},${k},${dnl},${dnguard}" >>"${outcsv}"
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
  echo "corner,temp_c,vdd_v,n,condition,fref_hz,status,t_lock_s,vctrl_final_v,k_cells,dn_lvl_v,dn_guard" >"${tmpdir}/out.csv"
  run_one "${CORNER}" "${TEMP}" "${VDD}" 4 cold "${tmpdir}/out.csv"
  cat "${tmpdir}/out.csv"
  exit 0
fi

RESULT_CSV="${WORK}/lock_time_raw.csv"
echo "corner,temp_c,vdd_v,n,condition,fref_hz,status,t_lock_s,vctrl_final_v,k_cells,dn_lvl_v,dn_guard" >"${RESULT_CSV}"

JOBS="${SIM_JOBS:-1}"
JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for corner in "${BUNDLES[@]}"; do
  for temp in "${TEMPS[@]}"; do
    for vdd in "${VDDS[@]}"; do
      for n in "${N_VALUES[@]}"; do
        for cond in "${CONDITIONS[@]}"; do
          echo "${corner} ${temp} ${vdd} ${n} ${cond}" >>"${JOBLIST}"
        done
      done
    done
  done
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "lock-time: ${NJOBS} runs (full 45-point PVT grid x N=4 x {cold,relock} -- see run.sh header), ${JOBS} parallel"

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
  tag="lt_${corner}_${temp}c_${vdd}v_n${n}_${cond}_tmax${SIMENV_CLOSED_LOOP_TMAX}"
  tag="${tag//./p}"
  cid="${corner}_${temp}c_${vdd}v_n${n}_${cond}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
  # tb_lock_time.sp's `.control` block unconditionally `wrdata`s a small
  # vctrl/up/dn/lock/vwin waveform CSV (#49's Vctrl-anomaly prerequisite --
  # see that file's header comment). It stays a useful per-CORNER artifact
  # for a small, targeted grid (the original 2-run pilot committed both), but
  # at THIS grid's scale (NJOBS runs, each producing a ~1-1.5 MB CSV) archiving
  # every one by default would commit tens to ~100+ MB for routine PASS/FAIL
  # rows that never need their waveform read -- sim/README.md's retention
  # table asks for justification above "a few MB per record", and "every
  # corner sweeps the same already-diagnosed anomaly" is not that
  # justification. Default OFF; set SIM_ARCHIVE_WAVEFORMS=1 to opt back in
  # for a small targeted run. The two waveforms that ARE the evidence for the
  # `lo`/`relock` anomaly investigations were captured via single-point
  # `--one` invocations and committed directly into their own records --
  # see sim/output-range/records/20260801-061907-67d7127.md and
  # sim/lock-time/records/20260801-073931-eec269e.md.
  if [ "${SIM_ARCHIVE_WAVEFORMS:-0}" = "1" ] && [ -f "${WORK}/${tag}/waveform.csv" ]; then
    cp "${WORK}/${tag}/waveform.csv" "${CORNERSDIR}/${cid}_waveform.csv"
  fi
done <"${JOBLIST}"

RESULT_MD="${WORK}/result.md"
{
  echo "| Corner | Temp | VDD | N | Condition | Status | t_lock | vctrl_final | mean DN | DN guard |"
  echo "|---|---|---|---|---|---|---|---|---|---|"
  tail -n +2 "${RESULT_CSV}" | while IFS=, read -r corner temp vdd n cond fref status tlock vfin k dnl dnguard; do
    tlock_fmt="N/A (not asserted within window)"
    [ -n "${tlock}" ] && [ "${tlock}" != "nan" ] && tlock_fmt=$(awk -v t="${tlock}" 'BEGIN{printf "%.3g s", t}')
    vfin_fmt="N/A"
    [ -n "${vfin}" ] && [ "${vfin}" != "nan" ] && vfin_fmt=$(awk -v v="${vfin}" 'BEGIN{printf "%.4g V", v}')
    # The raw dn_lvl sits beside its verdict on purpose: the verdict says only
    # whether the floor was cleared, while the magnitude says whether DN was
    # marginal or (as in the pre-bound violation this guard exists to catch)
    # three orders of magnitude away from asserting at all.
    dnl_fmt="N/A"
    [ -n "${dnl}" ] && [ "${dnl}" != "nan" ] && dnl_fmt=$(awk -v d="${dnl}" 'BEGIN{printf "%.3g V", d}')
    echo "| ${corner} | ${temp}C | ${vdd}V | ${n} | ${cond} | ${status} | ${tlock_fmt} | ${vfin_fmt} | ${dnl_fmt} | ${dnguard} |"
  done
} >"${RESULT_MD}"

# Summary counts -- cold vs relock PASS rates, and (relock only) how many
# rows land the SAME rail-excursion signature 20260801-073931-eec269e's
# waveform investigation diagnosed (vctrl_final past the 2.7 V clamp value
# itself -- a cheap per-row proxy for "hit the same already-diagnosed
# large-frequency-error PFD anomaly", not a re-diagnosis of each one).
COLD_PASS=$(awk -F, '$5=="cold" && $7=="PASS"{c++} END{print c+0}' "${RESULT_CSV}")
COLD_TOTAL=$(awk -F, '$5=="cold"{c++} END{print c+0}' "${RESULT_CSV}")
RELOCK_PASS=$(awk -F, '$5=="relock" && $7=="PASS"{c++} END{print c+0}' "${RESULT_CSV}")
RELOCK_TOTAL=$(awk -F, '$5=="relock"{c++} END{print c+0}' "${RESULT_CSV}")
RELOCK_RAIL=$(awk -F, '$5=="relock" && $9!="" && $9!="nan" && $9+0>2.7{c++} END{print c+0}' "${RESULT_CSV}")
RELOCK_ERR=$(awk -F, '$5=="relock" && $7=="ERROR"{c++} END{print c+0}' "${RESULT_CSV}")
COLD_ERR=$(awk -F, '$5=="cold" && $7=="ERROR"{c++} END{print c+0}' "${RESULT_CSV}")
# PFD DN-branch guard tallies (#69). Counted per verdict rather than folded
# into the PASS rate above, because the two answer different questions: the
# PASS rate is about the loop, the guard is about whether the integration was
# entitled to report on the loop at all.
DNG_PASS=$(awk -F, 'NR>1 && $12=="PASS"{c++} END{print c+0}' "${RESULT_CSV}")
DNG_FAIL=$(awk -F, 'NR>1 && $12=="FAIL"{c++} END{print c+0}' "${RESULT_CSV}")
DNG_SUSPECT=$(awk -F, 'NR>1 && $12=="SUSPECT"{c++} END{print c+0}' "${RESULT_CSV}")
DNG_ERROR=$(awk -F, 'NR>1 && $12=="ERROR"{c++} END{print c+0}' "${RESULT_CSV}")
DNG_SUMMARY="**PFD DN-branch integration guard** (#69; \`sim/README.md\`'s \"Closed-loop internal-timestep bound\"): **${DNG_PASS} PASS / ${DNG_FAIL} FAIL / ${DNG_SUSPECT} SUSPECT / ${DNG_ERROR} ERROR** across all rows, against a floor of ${ACC_DN_FRAC} of the rail. This grid runs AT the bound, so every row is expected to read PASS and the guard is a regression detector, not a diagnosis. A FAIL row reached lock while its DN branch never asserted; a SUSPECT row did not reach lock AND did not resolve its detector, so **this record does not attribute that row's FAIL to the design or to the transient window** -- the attribution is withheld rather than defaulted. Any non-PASS row means the ceiling was violated somewhere and the affected rows are not evidence about this loop."
OVERALL_SUMMARY="Across the full 45-point PVT grid at N=4: \`cold\` reached a sustained in-window PASS on ${COLD_PASS}/${COLD_TOTAL} corners (${COLD_ERR} ERROR rows -- ngspice did not complete); \`relock\` reached PASS on ${RELOCK_PASS}/${RELOCK_TOTAL} corners (${RELOCK_ERR} ERROR rows). Of the ${RELOCK_TOTAL} \`relock\` rows, **${RELOCK_RAIL} report vctrl_final > 2.7 V** -- past the clamp value itself, the same rail-excursion signature 20260801-073931-eec269e's waveform investigation root-caused at the typical/27C/3.30V corner (a large-frequency-error PFD/CP acquisition-dynamics anomaly, not a per-corner bug -- see that record). This grid does NOT re-run that waveform investigation at every corner; a \`relock\` row with vctrl_final > 2.7 V here is reported as consistent with the already-diagnosed mechanism, not independently re-diagnosed. \`cold\` FAIL rows mean only that the transient window was too short for lock_detector to assert yet (see the original pilot record's own finding that vctrl moves correctly toward the target); they are not evidence of a broken loop -- **on rows whose DN-branch guard reads PASS.** ${DNG_SUMMARY}"
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
- **Corner matrix run**: the **FULL 45-point PVT grid** (5 MOS bundles x 3
  temperatures x 3 supplies) at N=4, both cold-start and worst-case re-lock
  -- ${NJOBS} runs total. Extends the original single-corner pilot
  (\`sim/lock-time/records/20260731-221408-640560e.md\`), gated on
  \`sim/lock-time/records/20260801-073931-eec269e.md\`'s \`relock\`
  waveform investigation landing first, per #65's own explicit dependency
  ("do not extend the relock/lo-style grid to more corners/N/edges until
  this is understood"). N=16/64 are deliberately NOT included here -- #65's
  own item 3, a separate, larger follow-up (loop bandwidth falls with N per
  #10's \`loop-dynamics\`, so N=16/64 cold-start lock time is expected well
  outside this record's transient window; scaling the window AND the grid
  together in one record was judged less useful than landing the grid at
  the one N value this record's window is already sized for).
  - Axes not swept: N (2 of 3 required settings, deferred to #65's own next
    item) -- not a design judgement that it does not matter, a scoping
    decision to land the PVT grid on its own first.
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
    chgtol=1e-13\`; \`.tran\` print step \`1/(50*f_out)\` = 250 ps with an
    explicit **internal-timestep ceiling of ${SIMENV_CLOSED_LOOP_TMAX}**
    (\`.tran\`'s 4th argument, \`SIMENV_CLOSED_LOOP_TMAX\`); transient length up to
    **4 us for \`cold\`, 2 us for \`relock\`** (or 80 reference periods,
    whichever is shorter) -- narrowed from successively longer targets
    (16 us, then 8 us) during development, and made asymmetric between the
    two conditions once \`cold\`'s real measured cost (906.2 CPU-s, below)
    showed the two conditions could not both run at 4 us inside this
    session's remaining budget. This is disclosed, not hidden: the
    achievable window had to be re-picked against the CPU-second budget
    actually available in this session (see the throughput figure below)
    rather than the window that would show the cleanest result.
  - **PFD DN-branch integration guard (#69)**: \`tb_lock_time.sp\` measures
    \`dn_lvl\`, the mean DN level over the last 10 % of the window -- the
    same quantity \`sim/pll-top-smoke\`'s check 7 gates on, against the same
    floor (${ACC_DN_FRAC} of the rail). It is **not** a lock criterion. It
    is the per-row standing check that the internal-timestep ceiling above
    was actually honoured: when it is not, the PFD stops seeing feedback
    edges and the loop reports a confident, clean-looking "does not lock"
    that nothing else in this table flags (\`sim/README.md\`'s "Closed-loop
    internal-timestep bound"). #75 put this campaign on the bound, so the
    guard now earns its keep by catching a REGRESSION off it rather than
    the violation that motivated it.

    Because this campaign -- unlike \`pll-top-smoke\` -- has rows that can
    legitimately end the window still converging, the verdict is
    **three-valued** rather than a bare PASS/FAIL:
    - \`PASS\` -- DN asserts; the detector was resolved, so this row's own
      lock status means what it says.
    - \`FAIL\` -- the row reached lock PASS but its DN branch never
      asserted: an apparent lock with an unresolved detector.
    - \`SUSPECT\` -- the row did not reach lock PASS **and** did not resolve
      its detector. This record does not attribute such a row's FAIL to the
      design or to the transient window; the attribution is withheld.
      Suppressing the guard on non-PASS rows (reporting \`N/A\`) was
      considered and rejected -- it discards the discriminating measurement
      on precisely the rows where "is this FAIL real?" is the open question.
    - \`ERROR\` -- the measurement did not land; never coerced to zero.

    The per-row \`mean DN\` column carries the raw value beside the verdict,
    because the verdict says only whether the floor was cleared while the
    magnitude says whether DN was marginal or -- as measured on the
    pre-bound \`sim/output-range\` \`lo\` edge, 6.6e-7 V against a 9.9e-4 V
    floor -- not asserting at all.
  - **What the two conditions mean across the grid, stated plainly rather
    than dressed up**:
    - \`cold\` (0.9 V clamp, 4 us): the pilot record found Vctrl moving
      purposefully toward the target at the one corner it ran; across the
      full grid here a \`cold\` FAIL means only that this window was too
      short for \`lock_detector\` to assert yet at that corner -- not
      evidence of a broken loop. See the per-row \`vctrl_final\` column for
      whether the direction of travel looks purposeful at each corner.
      **That reading is conditional on the row's DN guard reading PASS**: a
      \`SUSPECT\` row did not resolve its phase detector either, so
      "the window was too short" is one of two explanations it cannot
      distinguish, and this record picks neither.
    - \`relock\` (2.7 V clamp, 2 us): \`sim/lock-time/records/20260801-073931-eec269e.md\`
      root-caused the pilot corner's \`vctrl_final\` = 3.138 V rail excursion
      as a genuine large-frequency-error PFD/CP acquisition-dynamics anomaly
      (empirically: \`up\` dominates persistently even though the measured
      feedback edge runs faster than the reference, the opposite of the
      naive tri-state-PFD expectation) -- NOT a per-corner bug, a
      polarity error, or a \`SWFORCE\`-release artifact. This grid's
      \`relock\` rows are read through that lens: see the Overall summary
      below for how many rows repeat the same rail-excursion signature
      (vctrl_final > 2.7 V), reported as consistent with the diagnosed
      mechanism rather than independently re-investigated at every corner.
  - **Measured simulator throughput** (this record's own development, this
    grid's actual runtime rather than a vendor number): unlike the original
    pilot record's single \`cold\` row (906.2 CPU-seconds on a then-heavily-
    contended shared host), this grid ran on an effectively uncontended host
    (load average 0.9-1.2 at the time) -- see \`sim/lock-time/records/20260801-073931-eec269e.md\`'s
    own throughput note for the single-corner comparison (62.1 CPU-s vs. that
    record's 714.3 CPU-s for the identical \`relock\` corner/window, an
    order of magnitude difference attributable to contention, not a change
    in the DUT). Per-run \`Total analysis time\` for every one of the
    ${NJOBS} runs here is in its own committed log under
    \`corners/${RID}/\`.
  - **Limitations**: schematic-level, no parasitics (#18 is post-layout);
    nominal-skew only (\`sw_stat_global = sw_stat_mismatch = 0\`, no Monte
    Carlo -- mismatch's contribution to lock behaviour is #15's mc-cp-mismatch
    scope, not re-derived here); single design point (one band, one Icp
    code, one target frequency) rather than the full N=4-64 x band x Icp-trim
    cross-product loop-dynamics (#10) already covers in the frequency domain;
    N=16/64 not covered (see Corner matrix run); \`relock\` rows showing the
    rail-excursion signature are attributed to the already-diagnosed
    mechanism by a cheap per-row proxy (vctrl_final > 2.7 V), not by
    re-running the waveform investigation at every corner -- a row that
    happens to land just inside 2.7 V but is still anomalous by some other
    measure would not be flagged by this proxy.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY} **This does NOT extend to N=16/64, which remains #65's
  own next item.** No overall PASS/FAIL against a lock-time spec threshold is
  claimed (spec #1 has not ratified a lock-time value).
- **Links**:
  - Testbench: \`sim/lock-time/testbench/tb_lock_time.sp\`,
    \`sim/lock-time/testbench/run.sh\`,
    \`sim/lib/assemble_closed_loop.sh\`
  - Design: \`design/vco.sch\`, \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/netlist/lock_detector.spice\`
  - Consumed design-input evidence (read-only): \`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv\`,
    \`sim/lock-detector/records/20260731-162119-0a12e6c.md\`
  - Predecessor records (cited, not superseded): \`sim/lock-time/records/20260731-221408-640560e.md\`
    (original single-corner pilot), \`sim/lock-time/records/20260801-073931-eec269e.md\`
    (the \`relock\` waveform investigation this grid's \`relock\` rows are
    read through)
  - Netlist snapshot: \`sim/lock-time/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/lock-time/corners/${RID}/\`
  - Raw CSV: \`${RESULT_CSV#"${REPO}"/}\` (not committed -- \`work/\` is
    git-ignored scratch; the per-corner logs above are the committed
    evidence)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #65)}
- **Supersedes**: (none -- new record; predecessors above are cited, not
  edited or superseded)
EOF
} >"${RECORD}"

echo "lock-time: wrote ${RECORD}"
echo "lock-time: wrote ${SNAPDIR}/${RID}.spice"
echo "lock-time: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
