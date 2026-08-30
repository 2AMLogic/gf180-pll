#!/usr/bin/env bash
# gf180-pll :: lock-time :: closed-loop lock-acquisition campaign (#12)
#
# DUT: `pll_top` -- the whole PLL from design/pll_top.sch, prepended to
# tb_lock_time.sp by sim/lib/pll_top_dut.sh (#52). Uses sim/lib/simenv.sh's
# corner-sweep primitives -- the
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
#   ./run.sh                 # full 45-point PVT grid x N in {4,16,64} x
#                             #   {cold,relock}, 270 runs -- see the Grid
#                             #   comment below for how N=16/64 (#65) scale
#                             #   the transient window
#   ./run.sh --check         # one short debug run, nominal corner, to stdout
#   ./run.sh --one <corner> <temp_c> <vdd> <n> <cold|relock> <outcsv>
#                             # single targeted point (used by the anomaly-
#                             #   investigation records; bypasses the grid)
#   SIM_JOBS=1 ./run.sh      # cap parallelism (default: sequential -- see below)
#   SIM_WINCAP=2.5e-7 ./run.sh --one ...
#                             # shorten the transient window for a CONTROLLED
#                             #   sub-experiment only (appears in the work-dir
#                             #   tag; see run_one). Same discipline as
#                             #   SIM_TMAX: not a knob for making a grid finish.
#
# NOTE ON HOST CONTENTION: this campaign's real cost is dominated by
# wall-clock contention, not raw CPU-seconds -- the SAME corner/window that
# took 714.3 CPU-s (and much longer in wall-clock) on a heavily-loaded shared
# host took only 62.1 CPU-s on an idle one (see
# sim/lock-time/records/20260801-073931-eec269e.md's own throughput note).
# Check `uptime` before committing to a full grid invocation -- this has cost
# every session that has attempted the N=4-only 90-run grid so far a completed
# run (see #65's own PR history: #68 and #83 both deferred it for exactly this
# reason). The N=16/64 rows added here are proportionally longer per run (see
# the Grid comment below), so the same host-contention discipline applies with
# more force, not less.
#
# NOTE ON COST, POST-#65: those historical CPU-second figures were measured at
# the OLD, bound-violating 250 ps internal-timestep ceiling. This campaign now
# runs at the 100 ps ceiling every closed-loop bench inherits from the PFD
# (sim/lib/simenv.sh :: SIMENV_CLOSED_LOOP_TMAX), which raises the internal
# step count ~2.4x. Budget the full grid accordingly, and do NOT reach for
# SIM_TMAX to claw the time back -- a grid minted at a coarser ceiling is not
# evidence about this loop. See sim/lock-time/records/20260801-101734-5eb00db.md.
#
# NOTE ON COST, POST-#159: this campaign's deck previously carried BOTH a
# top-level `.tran` card and a `.control ... run` block, which makes ngspice
# batch mode execute the transient TWICE (sim/pll-top-smoke's own deck
# documented that; this campaign's records observed it from the other end, as
# ngspice "re-entering its own analysis path a second time" after printing a
# complete set of measurements). #159's deck issues the transient once, from
# the control block. Historical per-run CPU-second figures quoted above were
# therefore paying for two transients per row; do not read them as a floor for
# a run of the current deck.
#
# DUT MIGRATION (#159): until #159 this campaign built its DUT with
# sim/lib/assemble_closed_loop.sh, which concatenates the five committed block
# exports and leaves the loop's top-level wiring to the testbench's own
# instance list. It now builds it with sim/lib/pll_top_dut.sh, i.e. from the
# committed export of design/pll_top.sch, so this campaign and
# sim/pll-top-smoke / sim/supply-sensitivity all simulate the SAME
# connectivity and a change to the loop is a schematic diff rather than a
# silent divergence between two hand-written instance lists. Every record
# already in sim/lock-time/records/ was taken against the older DUT and names
# it in its own Netlist provenance field; those records are append-only and
# are neither edited nor reinterpreted by this change. NO record in this
# campaign has yet been taken against `pll_top` -- the full-grid re-run that
# supersedes them is #159's remaining scope.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${HERE}/../../lib/pll_top_dut.sh"

# ngspice internal-threading pin (#241/#244/#246), applied HERE -- above the
# `--one` dispatch below -- rather than next to simenv_require_tools, because
# the grid path runs every one of its points as a FRESH `run.sh --one`
# invocation via xargs, and that entry point returns before
# simenv_require_tools is ever reached. A pin placed after it would cover
# `--check` and the record-minting parent only, i.e. exactly not the 270
# processes that do the work.
#
# Why this campaign opts in (measured this session, typical/27C/3.30V, N=4,
# `cold`, SIM_WINCAP=2.5e-7, same contended host, back-to-back):
#
#   unpinned (ngspice-46 spawns up to nproc OpenMP threads)  177.7 s wall, 357.1 CPU-s
#   OMP_THREAD_LIMIT=1                                        17.5 s wall,  11.5 CPU-s
#
# -- a 10x wall-clock and 31x CPU-second difference for a BIT-IDENTICAL result
# row (same status, same vctrl_final 1.05995e+00, same dn_lvl 1.33230e-05).
# The threads are not doing useful work on this deck; they are spinning at
# OpenMP barriers, and the cost grows with host contention, which is the exact
# mechanism #58/#65 and this campaign's own records repeatedly diagnosed as
# "the host was loaded" and budgeted around instead of fixing. Without this
# line the full 270-run grid measured ~61 h of wall-clock on this host; with
# it the same grid is a couple of hours, which is the difference between this
# campaign having a full-grid record and not.
#
# simenv_apply_omp_pin is a no-op on a host/build whose ngspice is not
# internally threaded, and never overrides an OMP_NUM_THREADS/OMP_THREAD_LIMIT
# the caller already set -- so `OMP_THREAD_LIMIT=8 ./run.sh` still reproduces
# the unpinned regime deliberately. See sim/lib/simenv.sh and
# sim/supply-sensitivity/records/20260829-114117-aca2990.md for why
# OMP_THREAD_LIMIT (not OMP_NUM_THREADS) is the variable that actually binds
# on a closed-loop deck of this size.
simenv_apply_omp_pin

FRAGMENT="${HERE}/tb_lock_time.sp"
WORK="${EXP}/work"
# The deck actually handed to ngspice: the committed pll_top export with the
# stimulus fragment appended, so the frozen netlist snapshot a record cites is
# self-contained and reproduces the run from the record alone.
DECK="${WORK}/dut_lock_time.sp"

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
# Band and Icp trim are named by CODE now (#159), not as loose bits: the bit
# patterns are produced by sim/lib/pll_top_dut.sh's cloop_band_params /
# cloop_trim_params, which own the encoding for every campaign on this DUT.
# Band 5 = (B2 B1 B0) 1 0 1; Icp code 2 = (CPB1 CPB0) 1 0 -- the same two
# settings this campaign has always run, restated in the shared encoding.
BAND_CODE=5
ICP_CODE=2
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

# --------------------------------------------------------------------------
# Grid.  #65 (the follow-up #49 itself named) extends this campaign from the
# original single-corner N=4 pilot to the FULL 45-point PVT grid -- but ONLY
# after #65's own gate: a targeted vctrl/up/dn/fb waveform investigation of
# `relock`'s anomalous vctrl_final (see
# sim/lock-time/records/20260801-073931-eec269e.md) had to land first and be
# understood, and it now has. That record's finding matters here: `relock`
# rows below are NOT expected to reach a stable in-window PASS in general --
# the mechanism it found (a large-frequency-error PFD/CP acquisition-
# dynamics anomaly, not a simple polarity bug) is not corner-specific in any
# way this record establishes, so seeing it recur across many/most corners
# below is the expected outcome of an already-diagnosed mechanism, not a new
# per-corner anomaly needing its own investigation.
#
# N=16/64 (#65's item 3): loop bandwidth falls with N (T(s) in
# sim/loop-dynamics's own derivation carries an explicit 1/N term), so
# cold-start/re-lock settling is expected to take longer in absolute time as N
# grows. run_one's transient window was previously capped at a FIXED absolute
# time (4 us cold / 2 us relock) that happened to equal exactly 80/40
# reference periods at N=4 -- reusing that same fixed cap unchanged at N=16/64
# would silently shrink the window to 20/10 reference periods at N=16 and
# 5/2.5 at N=64, the wrong direction given loop bandwidth falls with N. The
# cap below instead scales the SAME 80/40-reference-period budget
# proportionally with N (wincap = base * n/4), so N=4's own window is
# unchanged bit-for-bit (4e-6*4/4 = 4e-6) and N=16/64 get proportionally more
# absolute time rather than less. This preserves the reference-period margin
# the N=4 window was tuned for; it has not been validated against an actual
# N=16/64 run in this session (see this PR's description for why) and should
# be re-examined once a completed run is available.
# --------------------------------------------------------------------------
BUNDLES=("${SIMENV_MOS_CORNERS[@]}")
TEMPS=("${SIMENV_TEMPS[@]}")
VDDS=("${SIMENV_VDDS[@]}")
N_VALUES=(4 16 64)
CONDITIONS=(cold relock)   # vctrl_ic = 0.9 V / 2.7 V respectively

# Single-point debug corner, used only by --check below.
CORNER="typical"; TEMP=27; VDD=3.30

# run_one <corner> <temp> <vdd> <n> <condition> <outdir> -> writes result.csv row
run_one() {
  local corner="$1" temp="$2" vdd="$3" n="$4" cond="$5" outcsv="$6"
  # Idempotent and cheap (it only rewrites the file when the bytes change), so
  # a bare `--one` invocation -- the single-point form the anomaly
  # investigations use -- assembles its own deck rather than depending on a
  # prior full-grid invocation having left one behind.
  cloop_assemble "${FRAGMENT}" "${DECK}"
  local divparams; divparams=$(cloop_divider_params "${n}")
  local k; k=$(simenv_k_from_divparams "${divparams}")
  local fref; fref=$(awk -v f="${FOUT_TARGET}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  local vctrl_ic; [ "${cond}" = "cold" ] && vctrl_ic=0.9 || vctrl_ic=2.7
  # NOT the sim/output-range::vctrl_ic seed-collision hazard (#170): unlike
  # that campaign, this bench's `--one` entry point does not take vctrl_ic as
  # an argument at all -- it is always this deterministic function of `cond`
  # (0.9 V cold / 2.7 V relock), which is already fully captured by the
  # `${cond}` component the tag below already carries. Two `--one`
  # invocations of the same (corner, temp, vdd, n, cond) are therefore
  # guaranteed to compute the identical vctrl_ic and cannot collide under
  # different stimuli, so no tag change is needed here.
  # The internal-timestep ceiling is part of the run's identity, not a tuning
  # knob: a log produced at the old (f_out-derived, bound-violating) ceiling is
  # NOT interchangeable with one produced at SIMENV_CLOSED_LOOP_TMAX. Putting
  # it in the tag keeps the idempotent-reuse check below from silently handing
  # back a stale pre-#65 result under a new record's ID.
  # SIM_WINCAP shortens the transient window. Like SIM_TMAX it exists for ONE
  # legitimate use -- a controlled sub-experiment where the point is to run the
  # SAME corner twice in one environment with a single variable changed, and
  # where the per-reference-cycle behaviour (not a settled Vctrl) is what is
  # being compared. Cost scales with the window, so a bound-sensitivity pair
  # that will not finish at 2 us on a contended host can still be run honestly
  # at a shorter one. It is NOT a knob for making a grid finish: a grid row
  # minted at a truncated window is not the same measurement as its neighbours.
  # When set it is appended to the tag (so a short-window log can never be
  # silently reused for a full-window record) and left out of the tag entirely
  # when unset (so default tags are unchanged).
  #
  # The two conditions get DIFFERENT default caps -- not for a nicer-looking
  # result, but because the `cold` window's real cost (measured: 906.2 ngspice
  # CPU-seconds for 4 us -- see the record) left too little of the originating
  # session's compute budget for `relock` at the same length; the shorter
  # window is disclosed per-row, not silently assumed equal.
  #
  # #65 (N=16/64): both base caps below are scaled by n/4 -- see the Grid
  # comment above for why a fixed absolute cap does not transfer across N.
  # At n=4 this is exactly the original constant (4e-6*4/4 = 4e-6,
  # 2e-6*4/4 = 2e-6), so N=4 rows are bit-for-bit unchanged from the
  # already-recorded pilot/grid behaviour.
  local wincap wintag=""
  wincap=$(awk -v n="${n}" 'BEGIN{printf "%.6g", 4e-6*n/4}')
  [ "${cond}" = "relock" ] && wincap=$(awk -v n="${n}" 'BEGIN{printf "%.6g", 2e-6*n/4}')
  if [ -n "${SIM_WINCAP:-}" ]; then
    # SECONDS, as a plain decimal or scientific-notation number -- NOT a SPICE
    # engineering suffix. The cap is consumed by awk (below), and awk parses
    # "250n" as the STRING "250n", which then compares against the computed
    # window as a string and yields tstop=250 -- a 250 SECOND transient that
    # looks superficially plausible in the deck. Rejected loudly rather than
    # silently mis-scaled.
    case "${SIM_WINCAP}" in
      *[!0-9.eE+-]*|"")
        echo "ERROR: SIM_WINCAP='${SIM_WINCAP}' must be seconds as a plain number (e.g. 2.5e-7), not a SPICE suffix" >&2
        exit 1 ;;
    esac
    wincap="${SIM_WINCAP}"
    wintag="_w${SIM_WINCAP}"
  fi
  local tag="lt_${corner}_${temp}c_${vdd}v_n${n}_${cond}_tmax${SIMENV_CLOSED_LOOP_TMAX}${wintag}"
  tag="${tag//./p}"

  # Transient window: generous multiple of the reference period, sized so a
  # loop that locks in the expected few-to-tens-of-us range has wide margin,
  # while staying inside a tractable simulated-time budget (see Methodology)
  # -- the cap itself is chosen above, next to the tag it feeds.
  #
  # `tstep` below is the PRINT step only. The ceiling on the INTERNAL timestep
  # is passed separately as the transient's 4th argument
  # (SIMENV_CLOSED_LOOP_TMAX -- since #159 that transient is issued from the
  # deck's `.control` block rather than a top-level `.tran` card, so that the
  # run happens once rather than twice; the argument's meaning is unchanged);
  # before #65 this deck omitted that argument, so ngspice defaulted the
  # internal ceiling to `tstep` itself and the integration accuracy was tied to
  # f_out instead of to the PFD. Sizing the two independently is the fix --
  # see sim/lib/simenv.sh and sim/README.md.
  local tstop tstep t_force
  tstop=$(awk -v fr="${fref}" -v cap="${wincap}" 'BEGIN{t=80/fr; if (t>cap) t=cap; printf "%.6g", t}')
  tstep=$(awk -v fo="${FOUT_TARGET}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
  t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

  local params=(
    "vsup=${vdd}" "fref=${fref}" "iunit=${IUNIT}"
    "vctrl_ic=${vctrl_ic}" "t_force=${t_force}"
    "tstep=${tstep}" "tstop=${tstop}" "tmax=${SIMENV_CLOSED_LOOP_TMAX}"
    "lockthresh=0.5*vsup"
  )
  # Word splitting of each helper's `name=value ...` line is exactly what is
  # wanted here: one array element per .param.
  # shellcheck disable=SC2206
  params+=( ${divparams} )
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${BAND_CODE}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${ICP_CODE}") )

  local log="${WORK}/${tag}/ngspice.log"
  # Idempotent re-run: a prior invocation that already produced a
  # `vctrl_final` reading completed its transient (even if a later step of
  # THIS script mis-scored the result, or ngspice's own "Total analysis
  # time" banner never printed -- see below) -- don't burn a
  # multi-hundred-CPU-second re-simulation just to re-classify an
  # already-real log.
  #
  # The `-nt "${DECK}"` guard is new with #159 and load-bearing: the deck is
  # now a GENERATED artifact (committed pll_top export + this campaign's
  # stimulus fragment), and the work-dir tag does not encode its contents, so
  # without it a log produced by a previous version of the fragment would be
  # silently reused under a new record's ID. cloop_assemble only rewrites the
  # deck when its bytes actually change, so an unchanged deck keeps its mtime
  # and a resumed grid still reuses everything it legitimately can.
  if [ -f "${log}" ] && [ "${log}" -nt "${DECK}" ] && grep -q "^vctrl_final" "${log}"; then
    : # reuse the existing log below
  else
    local libs; libs=$(simenv_bundle_libs "${corner}")
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
cloop_require_netlist
mkdir -p "${WORK}"
cloop_assemble "${FRAGMENT}" "${DECK}"

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
echo "lock-time: ${NJOBS} runs (full 45-point PVT grid x N in {4,16,64} x {cold,relock} -- see run.sh header), ${JOBS} parallel"

# Host contention is the single biggest determinant of this campaign's
# wall-clock (see the header), and every record it mints is read as evidence
# about throughput as well as about the loop -- so the load average is
# SAMPLED here rather than asserted in the record template. The template used
# to hard-code "an effectively uncontended host (load average 0.9-1.2 at the
# time)", inherited from a session that never actually completed the grid;
# that sentence would have been emitted verbatim, and false, by every
# subsequent run on a loaded host. Measure it instead.
LOAD_START="$(uptime | sed 's/.*load average: //')"
NCPU="$(nproc 2>/dev/null || echo unknown)"
export OUTCSV="${RESULT_CSV}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@" "${OUTCSV}"' "${HERE}/run.sh" \
  <"${JOBLIST}"
LOAD_END="$(uptime | sed 's/.*load average: //')"

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

cp "${DECK}" "${SNAPDIR}/${RID}.spice"
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
OVERALL_SUMMARY="Across the full 45-point PVT grid at N in {4,16,64}: \`cold\` reached a sustained in-window PASS on ${COLD_PASS}/${COLD_TOTAL} corners (${COLD_ERR} ERROR rows -- ngspice did not complete); \`relock\` reached PASS on ${RELOCK_PASS}/${RELOCK_TOTAL} corners (${RELOCK_ERR} ERROR rows). Of the ${RELOCK_TOTAL} \`relock\` rows, **${RELOCK_RAIL} report vctrl_final > 2.7 V** -- past the clamp value itself, the same rail-excursion signature 20260801-073931-eec269e's waveform investigation root-caused at the typical/27C/3.30V corner (a large-frequency-error PFD/CP acquisition-dynamics anomaly, not a per-corner bug -- see that record). This grid does NOT re-run that waveform investigation at every corner; a \`relock\` row with vctrl_final > 2.7 V here is reported as consistent with the already-diagnosed mechanism, not independently re-diagnosed. \`cold\` FAIL rows mean only that the transient window was too short for lock_detector to assert yet (see the original pilot record's own finding that vctrl moves correctly toward the target); they are not evidence of a broken loop -- **on rows whose DN-branch guard reads PASS.** ${DNG_SUMMARY}"
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
- **Netlist provenance**: schematic (\`design/pll_top.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`) ->
  \`sim/lock-time/netlist-snapshots/${RID}.spice\` (exported subcircuit +
  testbench fragment, concatenated by \`sim/lib/pll_top_dut.sh\`), SHA-256
  \`${SHA}\`.
  **DUT changed at #159**: every \`sim/lock-time\` record dated before that
  migration was taken against a different assembly of the same five blocks
  (\`sim/lib/assemble_closed_loop.sh\`, whose testbench wired the loop
  itself) and says so in its own provenance field. Those records stand as
  written; this one is not comparable to them netlist-for-netlist, only
  claim-for-claim.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    design/pll_top.sch via design/netlist.sh; the DUT netlist is a schematic
    export, not a hand-written deck)")
- **Corner matrix run**: the **FULL 45-point PVT grid** (5 MOS bundles x 3
  temperatures x 3 supplies) at N in {4, 16, 64}, both cold-start and
  worst-case re-lock -- ${NJOBS} runs total. Extends the original
  single-corner pilot (\`sim/lock-time/records/20260731-221408-640560e.md\`),
  gated on \`sim/lock-time/records/20260801-073931-eec269e.md\`'s \`relock\`
  waveform investigation landing first, per #65's own explicit dependency
  ("do not extend the relock/lo-style grid to more corners/N/edges until
  this is understood"). N=16/64 (#65's item 3) scale \`run_one\`'s transient
  window proportionally with N rather than reusing the N=4 window's fixed
  absolute cap unchanged -- see \`run.sh\`'s Grid comment and \`run_one\`'s
  \`wincap\` for the derivation and why the N=4 rows are unaffected by it.
  - Axes not swept: none of the campaign's own PVT/N grid; see Methodology
    for the design point (band, Icp trim code) held fixed across the grid.
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
    ss/125C/2.97V); at N=4's 20 MHz reference (T_ref=50 ns) that is a
    1.75-3.4% phase-settling band. \`t_win\` is a fixed absolute quantity, so
    at N=16/64's longer T_ref (200 ns/800 ns) the same window is a
    proportionally SMALLER (looser) percentage band -- 0.44-0.85% at N=16,
    0.11-0.21% at N=64. **Minimum hold window**: LOCK
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
    chgtol=1e-13\`; transient print step \`1/(50*f_out)\` = 250 ps with an
    explicit **internal-timestep ceiling of ${SIMENV_CLOSED_LOOP_TMAX}**
    (the transient's 4th argument, \`SIMENV_CLOSED_LOOP_TMAX\`). Since #159
    the transient is issued ONCE, from the deck's \`.control\` block, instead
    of from a top-level \`.tran\` card that ngspice batch mode then re-ran a
    second time (the "re-entered its own analysis path" observation earlier
    records in this campaign report -- see
    \`sim/pll-top-smoke/testbench/tb_pll_smoke.sp\`, which documented the
    mechanism). The analysis itself is unchanged; only the duplicate is gone,
    so per-run CPU-second figures quoted from pre-#159 records are roughly
    twice what the same row costs now. Transient length up to
    **4 us for \`cold\`, 2 us for \`relock\` at N=4** (or 80/40 reference
    periods, whichever is shorter), scaled proportionally with N for N=16/64
    (16 us/8 us at N=16, 64 us/32 us at N=64 -- see \`run.sh\`'s Grid comment
    for why the N=4 window's fixed absolute cap does not transfer to larger N
    unscaled) -- narrowed from successively longer targets (16 us, then 8 us)
    during development, and made asymmetric between the two conditions once
    \`cold\`'s real measured cost (906.2 CPU-s, below) showed the two
    conditions could not both run at 4 us inside this session's remaining
    budget. This is disclosed, not hidden: the achievable window had to be
    re-picked against the CPU-second budget actually available in this
    session (see the throughput figure below) rather than the window that
    would show the cleanest result.
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
    grid's actual runtime rather than a vendor number): **host load average
    was ${LOAD_START} when this grid started and ${LOAD_END} when it
    finished**, on a ${NCPU}-CPU shared host
    running \`${JOBS}\` of this campaign's runs in parallel; this figure is
    sampled by \`run.sh\` at run time, not asserted. Read every per-row
    \`Total analysis time\` below in that light -- the same corner and window
    has been measured at 62.1 CPU-s on an idle host and 714.3 CPU-s on a
    loaded one (\`sim/lock-time/records/20260801-073931-eec269e.md\`'s own
    throughput note), an order of magnitude attributable to contention rather
    than to any change in the DUT, so these numbers bound this host's
    throughput on this day and are not a portable cost model for the deck.
    **ngspice internal-threading pin (#241/#244/#246)**: this campaign now
    calls \`simenv_apply_omp_pin\`, so each run is one single-threaded
    \`ngspice\` process (\`OMP_NUM_THREADS=${OMP_NUM_THREADS:-unset}\`,
    \`OMP_THREAD_LIMIT=${OMP_THREAD_LIMIT:-unset}\`) and the campaign's
    parallelism is external (\`SIM_JOBS\`) rather than a fan-out of
    \`SIM_JOBS\` processes each spawning up to \`nproc\` OpenMP threads. Rows
    in the pre-#159 records above were taken WITHOUT that pin and their
    per-run figures are not comparable to these. Per-run \`Total analysis
    time\` for every one of the ${NJOBS} runs here is in its own committed
    log under \`corners/${RID}/\`.
  - **Limitations**: schematic-level, no parasitics (#18 is post-layout);
    nominal-skew only (\`sw_stat_global = sw_stat_mismatch = 0\`, no Monte
    Carlo -- mismatch's contribution to lock behaviour is #15's mc-cp-mismatch
    scope, not re-derived here); single design point (one band, one Icp
    code, one target frequency) rather than the full N=4-64 x band x Icp-trim
    cross-product loop-dynamics (#10) already covers in the frequency domain;
    the N=16/64 transient-window scaling (proportional to N, see Corner
    matrix run) preserves the same reference-period margin the N=4 window was
    tuned for but has not itself been validated against a completed N=16/64
    run -- if N=16/64 rows below show a disproportionate ERROR/FAIL rate
    relative to N=4 at the same corner, re-check the window before concluding
    the loop itself is slower than expected; \`relock\` rows showing the
    rail-excursion signature are attributed to the already-diagnosed
    mechanism by a cheap per-row proxy (vctrl_final > 2.7 V), not by
    re-running the waveform investigation at every corner -- a row that
    happens to land just inside 2.7 V but is still anomalous by some other
    measure would not be flagged by this proxy.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY} No overall PASS/FAIL against a lock-time spec threshold is
  claimed (spec #1 has not ratified a lock-time value).
- **Links**:
  - Testbench: \`sim/lock-time/testbench/tb_lock_time.sp\`,
    \`sim/lock-time/testbench/run.sh\`,
    \`sim/lib/pll_top_dut.sh\`
  - Design: \`design/pll_top.sch\` (which instantiates \`design/vco.sch\`,
    \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/lock_detector.sch\`)
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
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
} >"${RECORD}"

echo "lock-time: wrote ${RECORD}"
echo "lock-time: wrote ${SNAPDIR}/${RID}.spice"
echo "lock-time: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
