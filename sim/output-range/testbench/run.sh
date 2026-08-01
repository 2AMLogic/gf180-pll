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
# kvco_by_point.csv (see seed_for_corner below and this campaign's record).
#
# Usage:
#   ./run.sh                 # full 45-point PVT grid x both band edges, 90 runs
#   ./run.sh --plan          # print the joblist (incl. per-corner seeds) and exit
#                             #   -- no simulation, for reviewing/costing a grid
#   ./run.sh --check         # one short debug run, nominal corner, to stdout
#   ./run.sh --one <corner> <temp_c> <vdd> <edge> <fout> <b2> <b1> <b0> <n> \
#                 <vctrl_ic> <outcsv> [seed_pos]
#                             # single targeted point (used by the lo-edge
#                             #   anomaly-investigation record; bypasses the grid)
#   SIM_JOBS=4 ./run.sh      # parallelism (default: sequential -- see below)
#
# NOTE ON HOST CONTENTION: exactly as for sim/lock-time, this campaign's real
# cost is dominated by wall-clock contention rather than raw CPU-seconds (the
# same corner/window has measured an order of magnitude apart on a contended
# vs. idle host -- see sim/lock-time/records/20260801-073931-eec269e.md).
# Check `uptime` before committing to the full 90-run invocation, and use
# `--plan` first if you want the joblist without paying for it.
#
# NOTE ON COST, POST-#65: this bench was the WORSE of the two closed-loop
# internal-timestep-bound violators. Its print step is 1/(50*f_out), so before
# #65 the `lo` (10 MHz) edge ran with a 2 ns internal ceiling -- 20x over the
# PFD's 100 ps bound, with 91% of its internal steps longer than the PFD's
# entire set pulse (sim/lock-time/records/20260801-101734-5eb00db.md). The
# ceiling is now passed explicitly (sim/lib/simenv.sh :: SIMENV_CLOSED_LOOP_TMAX),
# which raises `lo`'s internal step count roughly 20x; `hi` (200 MHz) is
# unchanged, because 1/(50*200 MHz) happened to equal 100 ps exactly. Budget
# the grid accordingly, and do NOT reach for SIM_TMAX to claw the time back --
# a grid minted at a coarser ceiling is not evidence about this loop.

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
# Two edges of the draft 10-200 MHz v1 output band. Band code and N are read
# off sim/vco-tuning-range's own measured kvco_by_point.csv. N is chosen as a
# power of two purely for a simple divider code; f_ref lands well inside the
# ratified 1-25 MHz v1 reference range either way.
#   low  edge: band 1 (B2 B1 B0=0 0 1), N=8  -> f_ref=1.25 MHz
#   high edge: band 7 (B2 B1 B0=1 1 1), N=32 -> f_ref=6.25 MHz
# The vctrl_ic seed is NOT fixed here -- it is interpolated PER CORNER by
# seed_for_corner below (see that function's comment for why the original
# single fixed seed does not survive the grid extension).
# --------------------------------------------------------------------------
EDGES=(
  "lo 10e6 0 0 1 8  1"
  "hi 200e6 1 1 1 32 7"
)

# --------------------------------------------------------------------------
# Grid.  #65 item 4 extends this campaign from the original deliberately-
# reduced single-corner pilot (`sim/output-range/records/20260731-223426-640560e.md`,
# 2 runs at typical/27C/3.30V) to the FULL 45-point PVT grid at both band
# edges -- the same grid loop sim/lock-time/testbench/run.sh already carries,
# applied to this script.
# --------------------------------------------------------------------------
BUNDLES=("${SIMENV_MOS_CORNERS[@]}")
TEMPS=("${SIMENV_TEMPS[@]}")
VDDS=("${SIMENV_VDDS[@]}")

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

# --------------------------------------------------------------------------
# seed_for_corner <bundle> <temp_c> <vdd> <band> <f_target> -> "<vctrl_v> <pos>"
#
# The vctrl_ic seed this bench applies through its released clamp, read off
# #8's own kvco_by_point.csv AT THE CORNER BEING RUN and linearly interpolated
# between the two bracketing Vctrl rows -- exactly the rule the pilot record
# (20260731-223426-640560e) applied by hand at its single corner, now applied
# programmatically at all 45. Verified against that record before being
# trusted: it reproduces the pilot's own hand-computed seeds, 1.679 V vs. its
# stated 1.68 V (lo) and 1.321 V vs. its stated 1.32 V (hi).
#
# Why per-corner rather than the pilot's two fixed constants: the VCO's f(Vctrl)
# curve moves a long way over PVT -- band 1 reaches 10 MHz anywhere from 1.17 V
# (ss/125C/2.97V) to 2.06 V (sf/-40C/3.63V). Carrying the nominal-corner seed
# across the grid would start most corners with a large control-voltage error
# and then give the loop the SAME short transient window to correct it in, so a
# FAIL row would confound "the loop cannot reach this edge here" with "the seed
# was for a different corner". Seeding per corner keeps the initial error small
# and corner-independent, so what varies across the grid is the loop, not the
# stimulus.
#
# <pos> is `in` when the target frequency falls inside the tabulated
# 0.9-2.7 V Vctrl sweep at that corner, `below`/`above` when it falls off
# the bottom/top end -- in which case the seed is clamped to the corresponding
# rail and the row is reported as OUT-OF-WINDOW rather than silently seeded at
# a Vctrl the open-loop table says cannot produce that frequency. That is a
# real design-input result (this band code cannot reach this edge at this
# corner), not a simulation failure, and the record says so.
# --------------------------------------------------------------------------
seed_for_corner() {
  awk -F, -v bundle="$1" -v temp="$2" -v vdd="$3" -v band="$4" -v ftarget="$5" '
    # n MUST be initialized: an uninitialized awk scalar used as a subscript
    # is the empty STRING, so the first matched row would land in v[""] and
    # leave v[0]/f[0] unset -- silently interpolating the lowest bracket
    # against a phantom (0 V, 0 Hz) point.
    BEGIN { n = 0 }
    NR == 1 { next }
    $1 == bundle && $2 + 0 == temp + 0 && $3 + 0 == vdd + 0 && $4 + 0 == band + 0 {
      v[n] = $5 + 0; f[n] = $6 + 0; n++
    }
    END {
      if (n < 2) { print "ERROR nodata"; exit }
      if (ftarget <= f[0])   { printf "%.4g below\n", v[0];   exit }
      if (ftarget >= f[n-1]) { printf "%.4g above\n", v[n-1]; exit }
      for (i = 0; i < n - 1; i++) {
        if (ftarget >= f[i] && ftarget <= f[i+1]) {
          printf "%.4g in\n", v[i] + (v[i+1] - v[i]) * (ftarget - f[i]) / (f[i+1] - f[i])
          exit
        }
      }
      print "ERROR nobracket"
    }
  ' "${KVCO_CSV}"
}

stage_netlist() {
  mkdir -p "$1"
  cp "${WORK}/dut.spice" "$1/dut.spice"
}

# run_one <corner> <temp> <vdd> <edge> <fout> <b2> <b1> <b0> <n> <vctrl_ic> \
#         <outcsv> [seed_pos]
#
# `seed_pos` is optional and defaults to `in`, so the single-point `--one`
# invocations the anomaly-investigation records used keep working unchanged.
run_one() {
  local corner="$1" temp="$2" vdd="$3" edge="$4" fout="$5" b2="$6" b1="$7" b0="$8" n="$9"
  shift 9
  local vctrl_ic="$1" outcsv="$2" seed_pos="${3:-in}"
  local code; code=$(n_to_code "${n}")
  local k; k=$(echo "${code}" | cut -d' ' -f1)
  local sel; sel=$(echo "${code}" | cut -d' ' -f2-7)
  local p;   p=$(echo "${code}" | cut -d' ' -f8-13)
  local fref; fref=$(awk -v f="${fout}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  # The internal-timestep ceiling is part of the run's identity -- see
  # sim/lock-time/testbench/run.sh's run_one for why it goes in the tag.
  local tag="or_${corner}_${temp}c_${vdd}v_${edge}_tmax${SIMENV_CLOSED_LOOP_TMAX}"
  tag="${tag//./p}"

  local tstop tstep t_force
  # Seeded near the expected lock point, so acquiring the residual error is
  # fast -- see the campaign header and this record's Methodology field for
  # why (the same compute-cost constraint sim/lock-time documents).
  #
  # `tstep` is the PRINT step only. Before #65 this deck's .tran omitted the
  # 4th (tmax) argument, so ngspice defaulted the INTERNAL timestep ceiling to
  # this print step -- and because it is derived from f_out, the 10 MHz `lo`
  # edge ran at a 2 ns internal ceiling, ~20x coarser than the PFD's set pulse
  # can tolerate. The ceiling is now passed independently as
  # SIMENV_CLOSED_LOOP_TMAX; note the resulting cost is strongly edge-dependent
  # here (the `lo` edge's internal step count rises ~18x, `hi`'s is unchanged
  # -- 200 MHz already computed to exactly 100 ps).
  tstop=$(awk -v fr="${fref}" 'BEGIN{t=20/fr; if (t>2e-6) t=2e-6; printf "%.6g", t}')
  tstep=$(awk -v fo="${fout}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
  t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

  local params=(
    "vsup=${vdd}" "fref=${fref}"
    "bnd0v=${b0}*vsup" "bnd1v=${b1}*vsup" "bnd2v=${b2}*vsup"
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
      echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},ERROR,,,${k},${vctrl_ic},${seed_pos}" >>"${outcsv}"
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
  # A corner whose open-loop table says this band cannot reach this edge
  # inside 0.9-2.7 V is reported as OUT-OF-WINDOW rather than PASS/FAIL: the
  # transient still ran and its vctrl_final is still reported, but scoring it
  # against a lock criterion would be scoring the loop for a target the VCO
  # band was never able to produce at that corner.
  if [ "${seed_pos}" != "in" ]; then
    status="OUT-OF-WINDOW"
  fi
  echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},${status},${tlock},${vfin},${k},${vctrl_ic},${seed_pos}" >>"${outcsv}"
}

case "${1:-}" in
  --one) shift; run_one "$@"; exit 0 ;;
esac
# Captured before the joblist loop below, which must not clobber "$@".
MODE="${1:-}"

# --------------------------------------------------------------------------
# Build the joblist (grid x edges), resolving each row's per-corner seed.
# Done before any simulation so `--plan` can print it for free.
# --------------------------------------------------------------------------
mkdir -p "${WORK}"
JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for corner in "${BUNDLES[@]}"; do
  for temp in "${TEMPS[@]}"; do
    for vdd in "${VDDS[@]}"; do
      for row in "${EDGES[@]}"; do
        read -r edge fout b2 b1 b0 n band <<<"${row}"
        seed=$(seed_for_corner "${corner}" "${temp}" "${vdd}" "${band}" "${fout}")
        vic="${seed%% *}"; pos="${seed##* }"
        if [ "${vic}" = "ERROR" ]; then
          echo "ERROR: no kvco_by_point.csv row for ${corner}/${temp}C/${vdd}V band ${band} (${pos})" >&2
          exit 1
        fi
        echo "${corner} ${temp} ${vdd} ${edge} ${fout} ${b2} ${b1} ${b0} ${n} ${vic} ${pos}" >>"${JOBLIST}"
      done
    done
  done
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')

if [ "${MODE}" = "--plan" ]; then
  echo "output-range: ${NJOBS} runs (full 45-point PVT grid x 2 band edges)"
  echo "corner temp vdd edge fout b2 b1 b0 n vctrl_ic seed_pos"
  cat "${JOBLIST}"
  awk '$11!="in"{c++} END{printf "output-range: %d row(s) OUT-OF-WINDOW (target unreachable inside 0.9-2.7 V at that corner)\n", c+0}' "${JOBLIST}"
  exit 0
fi

simenv_require_tools
"${ASSEMBLE}" "${REPO}" "${WORK}/dut.spice"

if [ "${MODE}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "corner,temp_c,vdd_v,edge,fout_hz,n,fref_hz,status,t_lock_s,vctrl_final_v,k_cells,seed_v,seed_pos" >"${tmpdir}/out.csv"
  chk=$(seed_for_corner "${CORNER}" "${TEMP}" "${VDD}" 1 10e6)
  run_one "${CORNER}" "${TEMP}" "${VDD}" lo 10e6 0 0 1 8 "${chk%% *}" "${tmpdir}/out.csv" "${chk##* }"
  cat "${tmpdir}/out.csv"
  exit 0
fi

RESULT_CSV="${WORK}/output_range_raw.csv"
echo "corner,temp_c,vdd_v,edge,fout_hz,n,fref_hz,status,t_lock_s,vctrl_final_v,k_cells,seed_v,seed_pos" >"${RESULT_CSV}"

JOBS="${SIM_JOBS:-1}"
echo "output-range: ${NJOBS} runs (full 45-point PVT grid x 2 band edges -- see run.sh header), ${JOBS} parallel"

export OUTCSV="${RESULT_CSV}"
# Same re-invocation pattern as sim/lock-time: each job re-enters this script
# via --one, so a single run is independently reproducible from the joblist.
# Each joblist line is 11 fields; the first 10 are run_one's leading
# arguments and the 11th (seed_pos) is passed through AFTER outcsv, as
# run_one's optional 12th argument, so the classification a row was scored
# under is carried by the row itself rather than re-derived at mint time.
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "${@:1:10}" "${OUTCSV}" "${11}"' \
  "${HERE}/run.sh" \
  <"${JOBLIST}"

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

while read -r corner temp vdd edge fout b2 b1 b0 n vic pos; do
  tag="or_${corner}_${temp}c_${vdd}v_${edge}_tmax${SIMENV_CLOSED_LOOP_TMAX}"
  tag="${tag//./p}"
  cid="${corner}_${temp}c_${vdd}v_${edge}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
  # tb_output_range.sp's `.control` block unconditionally `wrdata`s a small
  # vctrl/up/dn/lock/vwin waveform CSV (#49's Vctrl-anomaly prerequisite --
  # see that file's header comment). The pilot record committed both of its
  # two, and those waveforms are what 20260801-101734-5eb00db's internal-step
  # analysis was measured from. At THIS grid's scale (${NJOBS} runs) archiving
  # every one by default would commit far more than sim/README.md's retention
  # table asks be justified, so it follows sim/lock-time's convention: default
  # OFF, SIM_ARCHIVE_WAVEFORMS=1 to opt back in for a small targeted run.
  if [ "${SIM_ARCHIVE_WAVEFORMS:-0}" = "1" ] && [ -f "${WORK}/${tag}/waveform.csv" ]; then
    cp "${WORK}/${tag}/waveform.csv" "${CORNERSDIR}/${cid}_waveform.csv"
  fi
done <"${JOBLIST}"

RESULT_MD="${WORK}/result.md"
{
  echo "| Corner | Temp | VDD | Edge | Target f_out | N | Seed Vctrl | Status | vctrl_final | margin-to-0.9V | margin-to-2.7V |"
  echo "|---|---|---|---|---|---|---|---|---|---|---|"
  tail -n +2 "${RESULT_CSV}" \
    | sort -t, -k4,4 -k1,1 -k2,2n -k3,3n \
    | while IFS=, read -r corner temp vdd edge fout n fref status tlock vfin k vic pos; do
    vfin_fmt="N/A"; mlo="N/A"; mhi="N/A"
    if [ -n "${vfin}" ] && [ "${vfin}" != "nan" ]; then
      vfin_fmt=$(awk -v v="${vfin}" 'BEGIN{printf "%.4g V", v}')
      mlo=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", v-0.9}')
      mhi=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", 2.7-v}')
    fi
    fout_fmt=$(awk -v f="${fout}" 'BEGIN{printf "%.4g MHz", f/1e6}')
    seed_fmt=$(awk -v v="${vic}" 'BEGIN{printf "%.4g V", v}')
    [ "${pos}" != "in" ] && seed_fmt="${seed_fmt} (${pos} band)"
    echo "| ${corner} | ${temp}C | ${vdd}V | ${edge} | ${fout_fmt} | ${n} | ${seed_fmt} | ${status} | ${vfin_fmt} | ${mlo} | ${mhi} |"
  done
} >"${RESULT_MD}"

# Per-edge counts. OUT-OF-WINDOW rows are counted separately from FAIL: they
# are a statement about the VCO band's reach at that corner (from #8's
# open-loop table), not about whether the loop locked.
edge_count() { awk -F, -v e="$1" -v s="$2" '$4==e && $8==s{c++} END{print c+0}' "${RESULT_CSV}"; }
edge_total() { awk -F, -v e="$1" '$4==e{c++} END{print c+0}' "${RESULT_CSV}"; }
LO_PASS=$(edge_count lo PASS);  LO_TOTAL=$(edge_total lo)
HI_PASS=$(edge_count hi PASS);  HI_TOTAL=$(edge_total hi)
LO_OOW=$(edge_count lo OUT-OF-WINDOW); HI_OOW=$(edge_count hi OUT-OF-WINDOW)
LO_ERR=$(edge_count lo ERROR);  HI_ERR=$(edge_count hi ERROR)
OOW_LIST=$(awk -F, '$13!="in" && NR>1 {printf "%s/%sC/%sV (%s, %s)\n", $1, $2, $3, $4, $13}' "${RESULT_CSV}" | paste -sd'; ' -)
[ -z "${OOW_LIST}" ] && OOW_LIST="(none)"
OVERALL_SUMMARY="Across the full 45-point PVT grid at both band edges (${NJOBS} runs): the \`lo\` (10 MHz) edge reached a sustained in-window PASS on ${LO_PASS}/${LO_TOTAL} corners (${LO_OOW} OUT-OF-WINDOW, ${LO_ERR} ERROR); the \`hi\` (200 MHz) edge on ${HI_PASS}/${HI_TOTAL} corners (${HI_OOW} OUT-OF-WINDOW, ${HI_ERR} ERROR). OUT-OF-WINDOW rows: ${OOW_LIST}. A FAIL row means the transient window (see Methodology) was too short to observe sustained lock at that corner, NOT that the loop cannot reach that edge there; the un-fabricated final Vctrl reading is reported either way."
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
- **Corner matrix run**: the **FULL 45-point PVT grid** (5 MOS bundles x 3
  temperatures x 3 supplies) at both ratified output-band edges -- ${NJOBS}
  runs total. Extends the original deliberately-reduced single-corner pilot
  (\`sim/output-range/records/20260731-223426-640560e.md\`, 2 runs at
  typical/27C/3.30V), which is cited and not superseded.
  - Axes not swept: passive process corners (held at
    \`res_typical\`/\`moscap_typical\`/\`mimcap_typical\`, the campaign's
    existing convention -- \`sim/lock-time\` does the same); VCO band code and
    N (one design point per edge, as the pilot chose them); Icp trim code
    (nominal "10" throughout).
- **Methodology / criteria / limitations**:
  - **Edge selection**: the draft ratified output band is 10-200 MHz
    (pending #1). Each edge's (VCO band code, N, f_ref) design point is read
    directly off #8's own
    \`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv\`
    -- **not re-measured or re-derived here**, per the acceptance criteria's
    "cite, do not re-derive" requirement:
    - **Low edge (10 MHz)**: band 1, N=8 (f_ref=1.25 MHz).
    - **High edge (200 MHz)**: band 7, N=32 (f_ref=6.25 MHz).
  - **Per-corner seed (changed from the pilot, deliberately)**: the pilot
    hand-computed ONE \`vctrl_ic\` seed per edge, at typical/27C/3.30V
    (1.68 V / 1.32 V). This grid interpolates the seed **at each corner**
    from the same cited table by the same rule (linear between the two
    bracketing Vctrl rows) -- see \`seed_for_corner\` in
    \`sim/output-range/testbench/run.sh\`. The change is load-bearing rather
    than cosmetic: band 1 reaches 10 MHz anywhere from ~1.17 V
    (ss/125C/2.97V) to ~2.06 V (sf/-40C/3.63V) across this grid, so carrying
    the nominal seed everywhere would hand most corners a large initial
    control-voltage error and then give the loop the SAME short window to
    correct it -- a FAIL would then confound "the loop cannot reach this edge
    here" with "the seed was for a different corner". **Validated before use**:
    the programmatic rule reproduces the pilot's own hand-computed seeds at
    the pilot's corner (1.679 V vs. its stated 1.68 V for \`lo\`, 1.321 V vs.
    1.32 V for \`hi\`).
  - **OUT-OF-WINDOW rows**: at some corners the cited open-loop table shows
    the chosen band cannot produce the edge frequency anywhere inside the
    0.9-2.7 V usable Vctrl window. Those rows are seeded at the nearer rail,
    still simulated, and reported as \`OUT-OF-WINDOW\` rather than scored
    PASS/FAIL -- scoring the loop against a target its VCO band demonstrably
    cannot reach at that corner would misattribute an open-loop range
    limitation to the closed loop. This is a **real design-input finding**
    (that band/N choice does not cover that edge at that corner), and the
    affected corners are named in the Result summary.
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
  - **Simulator settings**: identical \`.options\` to \`sim/lock-time\`;
    \`.tran\` print step \`1/(50*f_out)\` with an explicit
    **internal-timestep ceiling of ${SIMENV_CLOSED_LOOP_TMAX}**
    (\`.tran\`'s 4th argument, \`SIMENV_CLOSED_LOOP_TMAX\` -- see
    \`sim/README.md\`'s "Closed-loop internal-timestep bound"). This is the
    first \`output-range\` grid taken at a compliant ceiling; every earlier
    record for this claim ran with the 4th argument absent, which put the
    \`lo\` edge at a 2 ns internal ceiling (see
    \`sim/lock-time/records/20260801-101734-5eb00db.md\`). Transient length is
    capped at 2 us for BOTH edges. **The 2 us cap is a much smaller number of
    reference cycles for \`lo\` than for \`hi\`, and this record says so
    rather than leaving it implicit**: \`lo\`'s 1.25 MHz reference gives only
    **~2.5 reference cycles** in 2 us; \`hi\`'s 6.25 MHz reference gives
    **~12.5 cycles**. \`lo\`'s rows are correspondingly the weaker of the two
    -- a handful of charge-pump pulses, not a settled trajectory -- and that
    is the single biggest limitation of this record.
  - **Limitations**: schematic-level, no parasitics; nominal-skew only
    (\`sw_stat_global = sw_stat_mismatch = 0\`, no Monte Carlo); one band/N
    design point per edge; the 2 us window is short for \`lo\` (above), so a
    \`lo\` FAIL row bounds nothing about whether that corner eventually
    locks; margin is reported per corner but the worst-margin corner is only
    as trustworthy as the window that produced it.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY}
- **Links**:
  - Testbench: \`sim/output-range/testbench/tb_output_range.sp\`,
    \`sim/output-range/testbench/run.sh\`,
    \`sim/lib/assemble_closed_loop.sh\`
  - Design: \`design/vco.sch\`, \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/netlist/lock_detector.spice\`
  - Consumed design-input evidence (read-only, cited not re-derived):
    \`${KVCO_CSV#"${REPO}"/}\`
  - Predecessor records (cited, not superseded):
    \`sim/output-range/records/20260731-223426-640560e.md\` (single-corner
    pilot), \`sim/output-range/records/20260801-061907-67d7127.md\`
    (\`lo\`-edge waveform investigation),
    \`sim/lock-time/records/20260801-101734-5eb00db.md\` (the
    internal-timestep-bound reconciliation this grid is the first
    \`output-range\` campaign to satisfy)
  - Netlist snapshot: \`sim/output-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/output-range/corners/${RID}/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #65)}
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
} >"${RECORD}"

echo "output-range: wrote ${RECORD}"
echo "output-range: wrote ${SNAPDIR}/${RID}.spice"
echo "output-range: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
