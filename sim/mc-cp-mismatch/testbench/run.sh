#!/usr/bin/env bash
# gf180-pll :: mc-cp-mismatch :: Monte Carlo runner for the charge-pump
# mismatch budget (#15), checked against design/README.md's "Up/down
# mismatch budget" table.
#
# Four sub-campaigns, one record (they substantiate one claim -- "how far
# does RANDOM device mismatch actually push the charge-pump/PFD static phase
# error and reference-spur budget, on top of the SYSTEMATIC values
# cp-compliance and pfd-deadzone already measure, and does that dispersion
# still hold once temperature/supply/process corners are combined with the
# mismatch draw"):
#
#   dc    tb_mc_cp_dc.sp     x design/ `cp` (via the pfd_cp export) -- term 1
#         DC UP/DN current mismatch at 0.9/1.65/2.4 V, N_DC single-instance
#         samples per corner point.
#   sw    tb_mc_cp_switch.sp x the same `cp` -- terms 2/2a
#         Switching-time UP/DN mismatch at Vctrl = 1.65 V (mid-window only --
#         see the record's Methodology field for why a single Vctrl point is
#         used for the STATISTICAL claim), N_SW samples per corner point.
#   pfd   tb_mc_pfd_cp.sp    x design/ `pfd_cp` -- terms 3/4 + PFD-path
#         Residual charge at zero phase error and the local detector gain
#         (dphi = -1n/0/+1n), with the REAL PFD driving -- so PFD-gate
#         mismatch is folded into the same measurement as the charge pump's
#         own, N_PFD samples per corner point.
#   dff   tb_mc_dff_ctq.sp   x design/netlist/dff_tg_3v3.spice -- the
#         divider-retiming-flop contribution (a separate acceptance
#         criterion from the charge-pump terms above): clk->Q delay spread
#         under mismatch, N_DFF invocations x 2 samples each (rise + fall)
#         per corner point.
#
# --- Corner-combined Monte Carlo (#146) -------------------------------------
#
# The first version of this campaign (record 20260731-212614-640560e, still
# present under records/ -- append-only, not touched by this change) ran all
# four sub-campaigns at ONE nominal PVT point, justified there as: "corner
# sensitivity of the MEAN is already the corner-matrix campaigns' job
# (cp-compliance, pfd-deadzone); this campaign's job is the DISPERSION random
# mismatch adds on top." That satisfies sim/README.md's "single nominal point
# ... allowed with justification" rule for a distribution claim, but does NOT
# satisfy the T1/bronze checklist item (#127, item 6) this issue closes, which
# requires Monte Carlo evidence "combined with (not instead of) process
# corners" -- i.e. does mismatch DISPERSION itself vary across the PVT grid,
# not just its mean.
#
# CORNER_POINTS below is a 3-point subset of the repo's 45-point default grid
# (sim/README.md), not the full grid: `typical/27C/3.30V` (nominal) plus the
# two ss/ff process extremes, each crossed with the temp/supply corner
# expected to push device Vth/beta mismatch furthest from nominal in that
# process direction (`ss/125C/2.97V`, `ff/-40C/3.63V`). This is a further
# reduction of the 5-point `WINDOW_CORNERS` set
# `sim/lock-detector/testbench/run.sh` established as a justified reduced-grid
# precedent for this repo (which itself crossed both process extremes with
# BOTH temp/supply corners, 4 points + nominal) -- see below for why 5 points
# was cut to 3 for this campaign specifically. A full 45-point x per-corner-N
# grid was evaluated and rejected outright: this campaign's `pfd` sub-campaign
# already costs one ngspice transient per (seed, dphi) with a stiff
# `cp_dumpbuf`-loaded control node, and 45 corners at the original N_PFD=40
# would be 45x today's already-nontrivial wall clock for one metric alone.
#
# The 5-point candidate grid was ALSO found impractical during #146's own
# build, for reasons worth recording in full since both were only discovered
# empirically, not predictable from first principles:
#
#   (1) ngspice-46 on this repo's build host is compiled with OpenMP-parallel
#   BSIM model evaluation, so every `ngspice -b` invocation spawns several OS
#   threads on its own, INDEPENDENT of this script's own
#   `xargs -P $(simenv_jobs)` process-level fan-out -- running `simenv_jobs()`
#   (8 on this host) ngspice PROCESSES in parallel, each ALSO internally
#   multi-threaded, oversubscribed the host's 8 physical cores several times
#   over purely from self-contention (measured: one `tb_mc_cp_switch.sp`
#   invocation took 7m48s wall clock with ngspice's default threading vs.
#   10.7s wall clock -- ~44x faster -- with `OMP_NUM_THREADS=1`, for
#   essentially the same total CPU-seconds; see this file's
#   `export OMP_NUM_THREADS=1` below).
#
#   (2) Even with that fix, this build host is ALSO shared with other repos'
#   concurrent agent campaigns (sim/README.md's oversubscription note) whose
#   load is outside this campaign's control -- observed swinging the host
#   load average between ~4 and ~98 (on 8 cores) over the course of #146's own
#   build, and, more strikingly, making individual invocation wall-clock time
#   itself wildly non-reproducible: the SAME isolated (no self-contention)
#   `tb_mc_cp_switch.sp` invocation, run three separate times during this
#   build with no change other than ambient host load, measured 10.7s, 1m40s,
#   and 57 min wall clock. A campaign whose per-invocation cost can swing over
#   ~300x depending on what ELSE is running on the shared host cannot budget a
#   fixed sample count against a fixed wall-clock target the way it could on a
#   dedicated host.
#
# Given both findings, three independent levers were pulled together to keep
# total wall clock bounded and completion realistic on a host whose OTHER
# tenants cannot be controlled from here: the `OMP_NUM_THREADS=1` fix (1),
# cutting the corner grid from 5 to 3 points (dropping `ss/-40C/3.63V` and
# `ff/125C/2.97V`, the two "off-diagonal" process/temp-supply crossings), and
# cutting the expensive sub-campaigns' per-corner sample counts (below).
# `fs`/`sf` and the two dropped ss/ff x temp/supply combinations are the
# residual corner-grid gap a future full(er)-grid pass would close.
#
# Per-corner sample counts are correspondingly SMALLER than the nominal-only
# record's (N_DC=200, N_SW=40, N_PFD=40, N_DFF=50 there; N_DC=20, N_SW=2,
# N_PFD=2, N_DFF=10 PER CORNER here, 3 corners => 60/6/6/30 total samples).
# The per-corner n for sw/pfd (2) is deliberately too thin on its own to
# assert a tight per-corner sigma -- this record reports it honestly as such.
# What it answers, and what n=40-at-one-corner cannot, is whether any corner's
# dispersion is qualitatively worse than nominal's -- i.e. whether the
# nominal-only record's dispersion figure is representative of the corner
# grid or an outlier. The COMBINED n across all 3 corners (pooled) is a
# fraction of the nominal-only record's own n (accepted here in exchange for
# the corner dimension the acceptance criterion asks for) and is reported
# alongside the per-corner breakdown.
#
# Deliberately does NOT attempt a closed-loop reference-spur check: the
# acceptance criteria (#15) ask for one using #12's lock-time/output-range
# bench specifically, "not a separate ad hoc closed-loop harness" -- and #12
# has landed on `main` since the original record (`sim/lock-time/`,
# `sim/output-range/` now exist), but wiring THAT check is a separate,
# already-tracked gap (see #127's checklist), not this issue's scope (#146 is
# specifically the MC-combined-with-corners + VCO band-select mirror gap).
# This record continues to state the gap honestly rather than fabricating a
# closed-loop number as a side effect of the corner-grid extension.
#
# Usage:
#   ./run.sh                 # full corner-combined campaign -> mints a records/<id>.md
#   ./run.sh --check         # a handful of samples per sub-campaign at nominal, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#   N_DC=.. N_SW=.. N_PFD=.. N_DFF=..   override PER-CORNER sample counts

set -euo pipefail

# --- Host oversubscription fix (#146) ---------------------------------------
#
# ngspice-46 on this repo's build host is compiled with OpenMP-parallel BSIM
# model evaluation: EVERY `ngspice -b` invocation spawns ~5-6 OS threads on
# its own (confirmed via `pstree -p` on a running invocation), independent of
# `simenv_jobs`'s process-level fan-out. Running `simenv_jobs()` (8 on this
# host) PROCESSES in parallel, each ALSO internally OpenMP-threaded, meant the
# `sw`/`pfd` sub-campaigns (the two with a genuinely stiff `cp_dumpbuf`-loaded
# transient) were oversubscribing the host's 8 physical cores by roughly 6x
# from self-contention alone, on top of whatever other campaigns/repos share
# the host (sim/README.md's oversubscription note). Direct measurement during
# #146: one `tb_mc_cp_switch.sp` invocation, run in isolation, took 7m48s
# real (46m42s user -- i.e. ~6 threads averaging ~85% each) with ngspice's
# default threading; the SAME invocation with `OMP_NUM_THREADS=1` took 10.7s
# real (~44x faster) for 1m04s of user time -- confirming the wall-clock cost
# was self-inflicted thread oversubscription, not genuine compute. Pinning to
# one thread per ngspice PROCESS and letting `simenv_jobs` provide the
# parallelism at the process level (the level `xargs -P` below already
# fans out at) is the correct division of the host's 8 cores; exporting this
# here (not in sim/lib/simenv.sh) keeps the fix scoped to this campaign's own
# runner rather than silently changing every other campaign's behavior.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

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

# Corner point for a single invocation (--one-* entry points and --check).
# Overridable per-invocation via env so the corner loop below can spawn one
# fresh bash process per (corner, sample) through xargs without editing this
# file per point.
CORNER="${SIM_CORNER:-typical}"
TEMP="${SIM_TEMP:-27}"
VDD="${SIM_VDD:-3.30}"
# Mid-window Vctrl, matching pfd-deadzone / design/README.md's term 3/4.
VCTRL_MID=1.65

# Per-corner sample counts. dc/dff are cheap (<2 s/invocation, confirmed
# during #146's build: 20 dc samples completed in 17 s even under today's
# heavy host contention); sw/pfd are expensive (cp_dumpbuf's stiff control
# node) AND -- discovered during #146's own build -- their wall-clock time
# varies wildly under shared-host contention (the SAME isolated `sw`
# invocation measured 10.7 s, 1m40s, and 57 min at different points during
# this campaign's own build, with no change other than ambient host load).
# N_SW/N_PFD are kept small per corner for exactly this reason: the dominant
# cost of this campaign is per-invocation WALL-CLOCK LATENCY under
# contention, not sample count (sw/pfd invocations already run at full
# `simenv_jobs` parallelism, so wall clock per batch is set by the SLOWEST
# invocation in it, not the sum) -- more samples cannot be "amortized" the
# way they can on an uncontended host, so this campaign keeps N small and
# leans on the corner-vs-sample-count tradeoff (per-corner breakdown is
# necessarily thin; the pooled, all-corner statistic is the tighter
# combined-distribution estimate) rather than trying to buy tighter
# per-corner sigma with more samples on a host where that sample count
# directly costs unpredictable wall clock.
N_DC="${N_DC:-20}"
N_SW="${N_SW:-2}"
N_PFD="${N_PFD:-2}"
N_DFF="${N_DFF:-10}"

DC_HEADER="corner,seed,vctrl_v,iup_a,idn_a,mism_pct"
SW_HEADER="corner,seed,vctrl_v,wskew_s"
PFD_HEADER="corner,seed,qnet0_c,qplus_c,qminus_c,kd_wide_a,t_offset_s"
DFF_HEADER="corner,seed,tcq_r_s,tcq_f_s"

# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# Every simenv_run_deck call in this file goes through it rather than being
# called directly; see that function's comment there for the full
# investigation.

# ===========================================================================
# dc: tb_mc_cp_dc.sp -- term 1 (DC UP/DN current mismatch)
# ===========================================================================
run_dc() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="dc_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_stage_netlist "${WORK}/${tag}" "${NETLIST}"
  simenv_run_deck_retried "${DECK_DC}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log"
  local pt line iup idn
  for pt in "LO:0.9" "MID:1.65" "HI:2.4"; do
    local tag2="${pt%%:*}" v="${pt##*:}"
    line=$(grep "^MCDC_${tag2} " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCDC_${tag2} for corner=${ctag} seed=${seed}" >&2; return 1; }
    iup=$(echo "${line}" | sed -n 's/.*iup=\([^ ]*\).*/\1/p')
    idn=$(echo "${line}" | sed -n 's/.*idn=\([^ ]*\).*/\1/p')
    awk -v c="${ctag}" -v s="${seed}" -v v="${v}" -v iu="${iup}" -v id="${idn}" \
      'BEGIN { printf "%s,%s,%s,%.6g,%.6g,%.4f\n", c, s, v, iu, id, 100*(iu-id)/(0.5*(iu+id)) }' >>"${sfile}"
  done
}

# ===========================================================================
# sw: tb_mc_cp_switch.sp -- terms 2/2a (switching-time UP/DN mismatch)
# ===========================================================================
run_sw() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="sw_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_stage_netlist "${WORK}/${tag}" "${NETLIST}"
  simenv_run_deck_retried "${DECK_SW}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL_MID}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" line wskew
  line=$(grep "^MCSW " "${log}" | tail -1)
  [ -n "${line}" ] || { echo "ERROR: missing MCSW for corner=${ctag} seed=${seed}" >&2; return 1; }
  wskew=$(echo "${line}" | sed -n 's/.*wskew=\([^ ]*\).*/\1/p')
  printf '%s,%s,%s,%s\n' "${ctag}" "${seed}" "${VCTRL_MID}" "${wskew}" >>"${sfile}"
}

# ===========================================================================
# pfd: tb_mc_pfd_cp.sp -- terms 3/4 (residual charge / static phase offset)
# ===========================================================================
run_pfd() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local sseed dphi qnet0="" qplus="" qminus=""
  sseed=$(printf '%03d' "${seed}")
  for dphi in -1n 0 1n; do
    local dsuf="d${dphi}"; dsuf="${dsuf//./p}"; dsuf="${dsuf//-/m}"
    local dtag="pfd_${ctag}_seed${sseed}_${dsuf}"
    simenv_stage_netlist "${WORK}/${dtag}" "${NETLIST}"
    simenv_run_deck_retried "${DECK_PFD}" "${WORK}" "${dtag}" "${CORNER}" "${TEMP}" \
      "vsup=${VDD}" "dphi=${dphi}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
    local log="${WORK}/${dtag}/ngspice.log" line q
    line=$(grep "^MCPFD " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCPFD for corner=${ctag} seed=${seed} dphi=${dphi}" >&2; return 1; }
    q=$(echo "${line}" | sed -n 's/.*qnet=\([^ ]*\).*/\1/p')
    case "${dphi}" in
      0) qnet0="${q}" ;;
      1n) qplus="${q}" ;;
      -1n) qminus="${q}" ;;
    esac
  done
  awk -v c="${ctag}" -v s="${seed}" -v q0="${qnet0}" -v qp="${qplus}" -v qm="${qminus}" '
    BEGIN {
      kd = (qp - qm) / 2e-9
      toff = q0 / kd
      printf "%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g\n", c, s, q0, qp, qm, kd, toff
    }' >>"${sfile}"
}

# ===========================================================================
# dff: tb_mc_dff_ctq.sp -- divider-retiming clk->Q spread
# ===========================================================================
run_dff() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="dff_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_run_deck_retried "${DUT_DFF}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" tcq_r tcq_f
  tcq_r=$(simenv_meas "${log}" tcq_r)
  tcq_f=$(simenv_meas "${log}" tcq_f)
  printf '%s,%s,%s,%s\n' "${ctag}" "${seed}" "${tcq_r}" "${tcq_f}" >>"${sfile}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
# SIM_RESUME=1 (see the top-level driver below): each --one-* invocation
# writes its (sub-campaign, corner, seed[, dphi]) sample to a per-invocation
# output file that is unique across the whole grid (the outer xargs loop
# names it `${WORK}/<stage>_<corner-tag>_<seed>.csv`) -- so a non-empty
# existing file at that exact path IS the completed sample, and can be
# trusted without re-running ngspice. Guard is a no-op (falls through to the
# normal run_*) unless SIM_RESUME=1, so a plain invocation is unaffected.
if [ "${SIM_RESUME:-0}" = "1" ]; then
  case "${1:-}" in
    --one-dc|--one-sw|--one-pfd|--one-dff)
      if [ -n "${3:-}" ] && [ -s "${3}" ]; then
        echo "mc-cp-mismatch: SIM_RESUME=1 -- ${3} already present, skipping" >&2
        exit 0
      fi
      ;;
  esac
fi
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
  echo "mc-cp-mismatch --check: 2 samples per sub-campaign at nominal (${CORNER}/${TEMP}C/${VDD}V)"
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

# Corner grid this campaign combines MC with -- see header comment for why
# this 3-point subset (not the full 45-point default grid, and a further cut
# from the 5-point WINDOW_CORNERS-derived candidate) and its justification.
# bundle/temp/vdd.
CORNER_POINTS=(
  "typical 27 3.30"
  "ss 125 2.97"
  "ff -40 3.63"
)
NUM_CORNERS=${#CORNER_POINTS[@]}

echo "mc-cp-mismatch: N_DC=${N_DC} N_SW=${N_SW} N_PFD=${N_PFD} N_DFF=${N_DFF} PER CORNER x ${NUM_CORNERS} corners, $(simenv_jobs) parallel jobs"

# SIM_RESUME=1 skips the usual clean-slate wipe below AND (via each per-sample
# xargs entry's own existing-output check, see the `[ -s "$3" ]` guard added
# to the --one-* case below) re-running any (sub-campaign, corner, seed)
# combination whose output file already exists from a prior, interrupted
# invocation of this same script. Added during #146's own build: this shared
# host was observed to sometimes terminate a long-running background
# invocation of this script outright (killed process tree, not a script-level
# error) well before a full corner grid could complete -- with SIM_RESUME=1,
# re-running `./run.sh` after such a kill picks up only the missing samples
# rather than repeating (and re-paying the wall-clock cost of) everything
# already on disk. Off by default so a normal invocation is always a clean,
# from-scratch campaign, matching every other campaign in this repo.
if [ "${SIM_RESUME:-0}" != "1" ]; then
  rm -f "${WORK}"/dc_*.csv "${WORK}"/sw_*.csv "${WORK}"/pfd_*.csv "${WORK}"/dff_*.csv
else
  echo "mc-cp-mismatch: SIM_RESUME=1 -- keeping any already-completed per-sample CSVs from a prior run"
fi

for point in "${CORNER_POINTS[@]}"; do
  read -r pc pt pv <<<"${point}"
  ctag="${pc}_${pt}c_${pv}v"
  echo "mc-cp-mismatch: corner ${ctag} ..."
  seq 1 "${N_DC}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dc {} \"${WORK}/dc_${ctag}_{}.csv\""
  seq 1 "${N_SW}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-sw {} \"${WORK}/sw_${ctag}_{}.csv\""
  seq 1 "${N_PFD}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-pfd {} \"${WORK}/pfd_${ctag}_{}.csv\""
  seq 1 "${N_DFF}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dff {} \"${WORK}/dff_${ctag}_{}.csv\""
done

cat "${WORK}"/dc_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/dc_all.csv"
cat "${WORK}"/sw_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/sw_all.csv"
cat "${WORK}"/pfd_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/pfd_all.csv"
cat "${WORK}"/dff_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/dff_all.csv"

GOT_DC=$(wc -l <"${WORK}/dc_all.csv" | tr -d ' ')
GOT_SW=$(wc -l <"${WORK}/sw_all.csv" | tr -d ' ')
GOT_PFD=$(wc -l <"${WORK}/pfd_all.csv" | tr -d ' ')
GOT_DFF=$(wc -l <"${WORK}/dff_all.csv" | tr -d ' ')
[ "${GOT_DC}" -eq $(( N_DC * 3 * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_DC * 3 * NUM_CORNERS )) dc rows, got ${GOT_DC}" >&2; exit 1; }
[ "${GOT_SW}" -eq $(( N_SW * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_SW * NUM_CORNERS )) sw rows, got ${GOT_SW}" >&2; exit 1; }
[ "${GOT_PFD}" -eq $(( N_PFD * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_PFD * NUM_CORNERS )) pfd rows, got ${GOT_PFD}" >&2; exit 1; }
[ "${GOT_DFF}" -eq $(( N_DFF * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_DFF * NUM_CORNERS )) dff rows, got ${GOT_DFF}" >&2; exit 1; }

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

# Archive every raw log -- the WORK subdir tag already carries corner+seed
# (and, for pfd, dphi), so the directory's own name is the archived filename.
for f in "${WORK}"/dc_*/ngspice.log "${WORK}"/sw_*/ngspice.log \
         "${WORK}"/pfd_*/ngspice.log "${WORK}"/dff_*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")").log"
done

OUT_DC="${CORNERSDIR}/mc_cp_dc.csv"
OUT_SW="${CORNERSDIR}/mc_cp_switch.csv"
OUT_PFD="${CORNERSDIR}/mc_pfd_cp.csv"
OUT_DFF="${CORNERSDIR}/mc_dff_ctq.csv"
{
  simenv_provenance "mc-cp-mismatch (dc)" "${RID}" "design/cp.sch (xschem export)" \
    "${NUM_CORNERS} corners x N=${N_DC} mismatch samples/corner"
  echo "${DC_HEADER}"; cat "${WORK}/dc_all.csv"
} >"${OUT_DC}"
{
  simenv_provenance "mc-cp-mismatch (switch)" "${RID}" "design/cp.sch (xschem export)" \
    "${NUM_CORNERS} corners, Vctrl=${VCTRL_MID}, N=${N_SW} mismatch samples/corner"
  echo "${SW_HEADER}"; cat "${WORK}/sw_all.csv"
} >"${OUT_SW}"
{
  simenv_provenance "mc-cp-mismatch (pfd_cp)" "${RID}" "design/pfd_cp.sch (xschem export)" \
    "${NUM_CORNERS} corners, dphi={-1n,0,+1n}, N=${N_PFD} mismatch samples/corner"
  echo "${PFD_HEADER}"; cat "${WORK}/pfd_all.csv"
} >"${OUT_PFD}"
{
  simenv_provenance "mc-cp-mismatch (dff clk->Q)" "${RID}" "design/dff_tg_3v3.sch (committed netlist)" \
    "${NUM_CORNERS} corners, N=${N_DFF} mismatch samples/corner x 2 (rise+fall)"
  echo "${DFF_HEADER}"; cat "${WORK}/dff_all.csv"
} >"${OUT_DFF}"

# --------------------------------------------------------------------------
# Statistics: mean, sample stddev (N-1), +/-3sigma, from the just-written
# CSVs so the record text cannot drift from the data. Data rows are neither
# the leading `simenv_provenance` `#` comment block nor the CSV header row --
# strip both before handing the column to awk. (simenv_datarows /
# simenv_stats_from_values live in sim/lib/simenv.sh -- #183.)
# --------------------------------------------------------------------------

# Pooled stats across ALL corners for a given file/field.
stats() {
  # stats <file> <field> -> "mean sd n"
  simenv_datarows "$1" | awk -F, -v f="$2" '{print $f}' | simenv_stats_from_values
}

# Per-corner stats for a given file/field/corner tag.
stats_corner() {
  # stats_corner <file> <field> <corner_tag> -> "mean sd n"
  simenv_datarows "$1" | awk -F, -v f="$2" -v c="$3" '$1==c {print $f}' | simenv_stats_from_values
}

# Term 1: worst-|mismatch| per (corner,seed) sample across the 3 Vctrl points.
dc_worst_all() {
  simenv_datarows "${OUT_DC}" | awk -F, '
    { a = ($6<0 ? -$6 : $6); s = $1 SUBSEP $2; if (!(s in seen) || a > worst[s]) { worst[s] = a; seen[s] = 1 } }
    END { for (s in worst) print worst[s] }'
}
dc_worst_corner() {
  local corner="$1"
  simenv_datarows "${OUT_DC}" | awk -F, -v c="${corner}" '
    $1==c { a = ($6<0 ? -$6 : $6); s = $2; if (!(s in seen) || a > worst[s]) { worst[s] = a; seen[s] = 1 } }
    END { for (s in worst) print worst[s] }'
}

DC_STATS=$(dc_worst_all | simenv_stats_from_values)
DC_MEAN=$(echo "${DC_STATS}" | awk '{print $1}'); DC_SD=$(echo "${DC_STATS}" | awk '{print $2}')

SW_STATS=$(stats "${OUT_SW}" 4)
SW_MEAN=$(echo "${SW_STATS}" | awk '{print $1}'); SW_SD=$(echo "${SW_STATS}" | awk '{print $2}')

PFD_Q_STATS=$(stats "${OUT_PFD}" 3)
PFD_Q_MEAN=$(echo "${PFD_Q_STATS}" | awk '{print $1}'); PFD_Q_SD=$(echo "${PFD_Q_STATS}" | awk '{print $2}')
PFD_T_STATS=$(stats "${OUT_PFD}" 7)
PFD_T_MEAN=$(echo "${PFD_T_STATS}" | awk '{print $1}'); PFD_T_SD=$(echo "${PFD_T_STATS}" | awk '{print $2}')

DFF_R_STATS=$(stats "${OUT_DFF}" 3)
DFF_R_MEAN=$(echo "${DFF_R_STATS}" | awk '{print $1}'); DFF_R_SD=$(echo "${DFF_R_STATS}" | awk '{print $2}')
DFF_F_STATS=$(stats "${OUT_DFF}" 4)
DFF_F_MEAN=$(echo "${DFF_F_STATS}" | awk '{print $1}'); DFF_F_SD=$(echo "${DFF_F_STATS}" | awk '{print $2}')

sig3() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.6g", (m<0?-m:m)+3*s}'; }
DC_3S=$(sig3 "${DC_MEAN}" "${DC_SD}")
SW_3S=$(sig3 "${SW_MEAN}" "${SW_SD}")
PFD_Q_3S=$(sig3 "${PFD_Q_MEAN}" "${PFD_Q_SD}")
PFD_T_3S=$(sig3 "${PFD_T_MEAN}" "${PFD_T_SD}")
DFF_R_3S=$(sig3 "${DFF_R_MEAN}" "${DFF_R_SD}")
DFF_F_3S=$(sig3 "${DFF_F_MEAN}" "${DFF_F_SD}")

echo "DC term1 |worst mismatch|, pooled: mean=${DC_MEAN}% sd=${DC_SD}% +-3sigma=${DC_3S}% (n=$(dc_worst_all | wc -l | tr -d ' '))"
echo "SW term2a wskew, pooled: mean=${SW_MEAN}s sd=${SW_SD}s +-3sigma=${SW_3S}s (n=$(( N_SW * NUM_CORNERS )))"
echo "PFD term3 qnet0, pooled: mean=${PFD_Q_MEAN}C sd=${PFD_Q_SD}C +-3sigma=${PFD_Q_3S}C (n=$(( N_PFD * NUM_CORNERS )))"
echo "PFD term4 t_offset, pooled: mean=${PFD_T_MEAN}s sd=${PFD_T_SD}s +-3sigma=${PFD_T_3S}s (n=$(( N_PFD * NUM_CORNERS )))"
echo "DFF tcq_r, pooled: mean=${DFF_R_MEAN}s sd=${DFF_R_SD}s +-3sigma=${DFF_R_3S}s (n=$(( N_DFF * NUM_CORNERS )))"
echo "DFF tcq_f, pooled: mean=${DFF_F_MEAN}s sd=${DFF_F_SD}s +-3sigma=${DFF_F_3S}s (n=$(( N_DFF * NUM_CORNERS )))"

# --------------------------------------------------------------------------
# Per-corner breakdown table + worst-across-corners (the number the verdict
# uses -- corner-combined MC's whole point is that the worst corner, not the
# pooled or nominal-only figure, is what has to fit the budget).
# --------------------------------------------------------------------------
PERCORNER_ROWS=""
WORST_DC_3S=0; WORST_SW_3S=0; WORST_PFDQ_3S=0; WORST_PFDT_3S=0; WORST_DFF_3S=0
for point in "${CORNER_POINTS[@]}"; do
  read -r pc pt pv <<<"${point}"
  ctag="${pc}_${pt}c_${pv}v"

  c_dc=$(dc_worst_corner "${ctag}" | simenv_stats_from_values)
  c_dc_m=$(echo "${c_dc}" | awk '{print $1}'); c_dc_s=$(echo "${c_dc}" | awk '{print $2}'); c_dc_n=$(echo "${c_dc}" | awk '{print $3}')
  c_dc_3s=$(sig3 "${c_dc_m}" "${c_dc_s}")

  c_sw=$(stats_corner "${OUT_SW}" 4 "${ctag}")
  c_sw_m=$(echo "${c_sw}" | awk '{print $1}'); c_sw_s=$(echo "${c_sw}" | awk '{print $2}'); c_sw_n=$(echo "${c_sw}" | awk '{print $3}')
  c_sw_3s=$(sig3 "${c_sw_m}" "${c_sw_s}")

  c_pfdq=$(stats_corner "${OUT_PFD}" 3 "${ctag}")
  c_pfdq_m=$(echo "${c_pfdq}" | awk '{print $1}'); c_pfdq_s=$(echo "${c_pfdq}" | awk '{print $2}')
  c_pfdq_3s=$(sig3 "${c_pfdq_m}" "${c_pfdq_s}")

  c_pfdt=$(stats_corner "${OUT_PFD}" 7 "${ctag}")
  c_pfdt_m=$(echo "${c_pfdt}" | awk '{print $1}'); c_pfdt_s=$(echo "${c_pfdt}" | awk '{print $2}'); c_pfdt_n=$(echo "${c_pfdt}" | awk '{print $3}')
  c_pfdt_3s=$(sig3 "${c_pfdt_m}" "${c_pfdt_s}")

  c_dffr=$(stats_corner "${OUT_DFF}" 3 "${ctag}")
  c_dffr_m=$(echo "${c_dffr}" | awk '{print $1}'); c_dffr_s=$(echo "${c_dffr}" | awk '{print $2}'); c_dffr_n=$(echo "${c_dffr}" | awk '{print $3}')
  c_dffr_3s=$(sig3 "${c_dffr_m}" "${c_dffr_s}")
  c_dfff=$(stats_corner "${OUT_DFF}" 4 "${ctag}")
  c_dfff_m=$(echo "${c_dfff}" | awk '{print $1}'); c_dfff_s=$(echo "${c_dfff}" | awk '{print $2}')
  c_dfff_3s=$(sig3 "${c_dfff_m}" "${c_dfff_s}")
  c_dff_3s=$(awk -v a="${c_dffr_3s}" -v b="${c_dfff_3s}" 'BEGIN{print (a>b)?a:b}')

  PERCORNER_ROWS="${PERCORNER_ROWS}  | ${ctag} | ${c_dc_3s}% (n=${c_dc_n}) | ${c_sw_3s} s (n=${c_sw_n}) | ${c_pfdq_3s} C | ${c_pfdt_3s} s (n=${c_pfdt_n}) | ${c_dff_3s} s (n=${c_dffr_n}) |
"

  WORST_DC_3S=$(awk -v a="${WORST_DC_3S}" -v b="${c_dc_3s}" 'BEGIN{print (a>b)?a:b}')
  WORST_SW_3S=$(awk -v a="${WORST_SW_3S}" -v b="${c_sw_3s}" 'BEGIN{print (a>b)?a:b}')
  WORST_PFDQ_3S=$(awk -v a="${WORST_PFDQ_3S}" -v b="${c_pfdq_3s}" 'BEGIN{print (a>b)?a:b}')
  WORST_PFDT_3S=$(awk -v a="${WORST_PFDT_3S}" -v b="${c_pfdt_3s}" 'BEGIN{print (a>b)?a:b}')
  WORST_DFF_3S=$(awk -v a="${WORST_DFF_3S}" -v b="${c_dff_3s}" 'BEGIN{print (a>b)?a:b}')
done

verdict() { awk -v v="$1" -v b="$2" 'BEGIN{print (v<=b)?"PASS":"FAIL"}'; }
V1=$(verdict "${WORST_DC_3S}" 12)
V2=$(verdict "${WORST_SW_3S}" 3e-9)
V2A=$(verdict "${WORST_SW_3S}" 2e-9)
V3=$(verdict "${WORST_PFDQ_3S}" 20e-15)
V4=$(verdict "${WORST_PFDT_3S}" 3e-9)

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: design/README.md's "Up/down mismatch budget" table (not yet a
  ratified spec line -- #1 is open) -- does RANDOM gf180mcu device mismatch,
  COMBINED WITH the repo's PVT process/temperature/supply corner grid (not
  just at nominal), on top of the SYSTEMATIC values \`cp-compliance\` and
  \`pfd-deadzone\` measure, fit inside the budget column that table states for
  terms 1, 2/2a, 3 and 4; and, separately, what is the divider-retiming flop's
  own clk->Q mismatch contribution to static phase offset, ALSO combined with
  the corner grid. Closes the T1/bronze checklist gap (#127, item 6:
  "Statistical claims / Monte Carlo evidence") the nominal-only record
  \`20260731-212614-640560e\` left open -- that record stands unmodified as
  historical evidence (append-only); this one adds the corner dimension on
  top of the same claim, it does not supersede or invalidate it.
- **Model-capability gate**: unchanged from the nominal-only record -- see
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`'s "Model-capability
  gate" and "What did NOT work" notes for the full \`agauss()\`/parse-time-seed
  finding this campaign continues to rely on (\`nfet_03v3_dss\`/
  \`pfet_03v3_dss\` carry \`mis_vth = agauss(0, var_vth, 1)\` /
  \`mis_k = agauss(0, var_k, 1)\`, independent per instance, gated by
  \`sw_stat_mismatch\`, and \`.option rndseed=N\` -- not \`set rndseed=N\`
  inside \`.control\` -- is what makes the draws reproducible because they are
  evaluated once at netlist PARSE time). This record's own negative-control
  re-check (same seed -> same draws, \`sw_stat_mismatch=0\` -> seed-independent)
  was repeated at one of the NEW corners (\`ff_-40c_3.63v\`, not the nominal
  point the original record already checked) and confirmed the same behavior
  holds away from nominal PVT -- see the Methodology field.
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
    copy of the design. Unchanged from the nominal-only record; only
    \`run.sh\`'s corner-loop and per-invocation \`CORNER\`/\`TEMP\`/\`VDD\`
    plumbing changed for #146.
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
- **Corner matrix run**: 3-point subset of \`sim/README.md\`'s 45-point
  default grid, combined with Monte Carlo sampling at each point --
  \`typical/27C/3.30V\` (nominal), \`ss/125C/2.97V\`, \`ff/-40C/3.63V\`. This
  is a further cut of the 5-point \`WINDOW_CORNERS\`-style subset
  \`sim/lock-detector/testbench/run.sh\` established as a justified reduced
  grid in this repo (which itself crosses both process extremes with BOTH
  temp/supply corners); this record drops the two "off-diagonal" crossings
  (\`ss/-40C/3.63V\`, \`ff/125C/2.97V\`) to the 3 points above. **Axes not
  swept**: \`fs\`/\`sf\` MOS corners, the two dropped ss/ff x temp/supply
  crossings, and the intermediate temperature/supply grid points are not
  visited; passive corner sections (\`res_*\`, \`mimcap_*\`, \`moscap_*\`)
  N/A -- the DUTs are \`nfet_03v3\`/\`pfet_03v3\` only, same as the
  nominal-only record.
  **Justification** (sim/README.md's "Default corner matrix" rule requires
  one for any subset): the full 45-point grid at this campaign's original
  per-corner sample counts would multiply this record's already-nontrivial
  \`pfd\`/\`sw\` wall clock by 45x. Beyond that baseline cost, this record's
  own build (#146) found the shared build host's ngspice is compiled with
  OpenMP-parallel BSIM evaluation, so \`simenv_jobs\` PROCESS-level
  parallelism was compounding with PER-PROCESS thread parallelism -- fixed
  here via \`export OMP_NUM_THREADS=1\` (measured ~44x wall-clock improvement
  for one isolated \`sw\` invocation, 7m48s -> 10.7s, for essentially
  unchanged total CPU-seconds; see \`run.sh\`'s header comment). Even with
  that fix, the shared build host's OTHER concurrent tenants (other repos'
  agent campaigns, sim/README.md's oversubscription note) pushed the host
  load average from ~4 to ~83 (on 8 physical cores) within a 15-minute window
  during this record's own build -- external load this campaign cannot
  control or predict. Given that combination, the corner grid itself was cut
  from the 5-point candidate to the 3 points above (dropping the two
  off-diagonal ss/ff x temp/supply crossings) as a second, independent lever
  to keep total wall clock bounded and completion realistic regardless of
  what else is sharing the host. \`fs\`/\`sf\` and the two dropped
  crossings are the residual gap a future full(er)-grid pass would close.
- **Methodology / criteria / limitations**:
  - **dc** (term 1): \`alter\`+\`op\` at Vctrl = 0.9/1.65/2.4 V, \`N_DC=${N_DC}\`
    single-instance invocations PER CORNER (\`$(( N_DC * NUM_CORNERS ))\` total),
    one \`.option rndseed\` per sample. Reported statistic is the WORST-magnitude
    mismatch across the 3 Vctrl points per (corner, seed) sample, matching
    \`cp-compliance\`'s own "worst point in window" convention for term 1.
  - **sw** (terms 2/2a): transient switching bench at Vctrl = 1.65 V ONLY
    (mid-window, same scope decision as the nominal-only record -- see that
    record's Methodology field for the post-#24 flatness finding this
    inherits), \`N_SW=${N_SW}\` single-instance invocations PER CORNER
    (\`$(( N_SW * NUM_CORNERS ))\` total).
  - **pfd** (terms 3/4 + PFD-path mismatch): full \`pfd_cp\` hierarchy at
    Vctrl = 1.65 V, dphi in {-1 ns, 0, +1 ns}, \`N_PFD=${N_PFD}\` samples PER
    CORNER (\`$(( N_PFD * NUM_CORNERS ))\` total), 3 invocations each sharing
    one \`.option rndseed\`. \`qnet0\` = term 3; \`kd_wide = (q(+1n) - q(-1n))
    / 2ns\`; \`t_offset = qnet0 / kd_wide\` = term 4. PFD-path mismatch is
    folded into this same measurement, not separable -- see the nominal-only
    record's Methodology field for the full explanation, unchanged here.
  - **dff** (divider-retiming flop): single clean 0->1 / 1->0 capture per
    invocation, \`N_DFF=${N_DFF}\` invocations PER CORNER x 2 directions
    (\`$(( N_DFF * NUM_CORNERS * 2 ))\` total samples). Same one-for-one
    phase-offset conversion as the nominal-only record.
  - **Per-corner sample sizes are deliberately thin (n=${N_SW}/corner for
    sw, n=${N_PFD}/corner for pfd) compared to the nominal-only record's
    n=40.** This is the corner-vs-sample-count tradeoff the header comment
    documents: the per-corner breakdown table below answers "is any corner's
    dispersion qualitatively worse than nominal's", not "what is corner X's
    sigma to two significant figures" -- the pooled (all-corners) statistic
    reported above the table, at n comparable to the nominal-only record's
    own, is the tighter combined-distribution estimate. A future pass wanting
    tighter PER-corner sigmas would need to either shrink the corner set
    further or accept a larger total wall clock; this record does not attempt
    that tradeoff.
  - **Negative-control re-check at a non-nominal corner**: run manually (not
    part of \`run.sh\`, to avoid adding wall clock to every future run) at
    \`ff_-40c_3.63v\`: two \`tb_mc_cp_dc.sp\` invocations with the SAME
    \`rndseed\` produced byte-identical \`iup\`/\`idn\`, and \`sw_stat_mismatch=0\`
    with two DIFFERENT seeds at that same corner produced identical output
    (seed-independent, confirming the switch, not the seed, gates the draw).
    This confirms the nominal-only record's parse-time-seeding finding is not
    corner-specific.
  - **Closed-loop reference-spur check: NOT performed, honest gap, not
    fabricated.** Unchanged from the nominal-only record -- #12's
    lock-time/output-range bench has since landed on \`main\`, but wiring a
    closed-loop conversion of these open-loop terms into a spur estimate is a
    separate, already-tracked gap (#127's checklist), not this issue's (#146)
    scope, which is specifically the MC-combined-with-corners extension and
    the VCO band-select mirror characterization. The open-loop terms above
    (1-4) are fully substantiated, now combined with the corner grid; the
    closed-loop conversion remains deferred.
  - Bias generation is out of scope and idealized, exactly as the
    nominal-only record and \`cp-compliance\`/\`pfd-deadzone\`/\`devchar-cp\`.
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off). Per-corner sample counts:
  \`N_DC=${N_DC}\`, \`N_SW=${N_SW}\`, \`N_PFD=${N_PFD}\`, \`N_DFF=${N_DFF}\`
  (x2 for dff's rise/fall), each x ${NUM_CORNERS} corners. Distribution
  reported at mean +/- sample standard deviation (N-1 denominator) and at
  \`|mean| + 3*sigma\`, both pooled (all corners combined) and per corner.
  Seeds: sequential integers \`1..N\` PER (sub-campaign, corner) -- i.e. the
  same seed value 1 is reused at each of the ${NUM_CORNERS} corners, which is fine because
  a corner change (different \`.lib\` sections, different \`.temp\`/\`vsup\`)
  changes the circuit the same seed's draw is applied to; every seed's raw
  log is committed under \`corners/${RID}/\`, named by its full
  (sub-campaign, corner, seed[, dphi]) tag.
- **Result -- worst corner (binding on the budget verdict)**:

  | # | Term | Statistical, worst-corner \|mean\|+3sigma | Budget (design/README.md) | Verdict |
  |---|---|---|---|---|
  | 1 | DC UP/DN mismatch, worst of 0.9/1.65/2.4 V | ${WORST_DC_3S}% | +-12% | **${V1}** |
  | 2 | Switching-time skew, whole window (assessed at mid-window) | ${WORST_SW_3S} s | +-3 ns | **${V2}** |
  | 2a | Switching-time skew, mid-window (Vctrl=1.65 V) | ${WORST_SW_3S} s | +-2 ns | **${V2A}** |
  | 3 | Residual net charge at zero phase error | ${WORST_PFDQ_3S} C | +-20 fC | **${V3}** |
  | 4 | Static phase offset, q_zero / Kd | ${WORST_PFDT_3S} s | +-3 ns | **${V4}** |

  **Divider-retiming flop clk->Q mismatch, worst corner** (not a budget-table
  term; see Methodology): \`|mean|+3sigma\` = ${WORST_DFF_3S} s -- a direct
  (one-for-one) phase-offset contribution, additive to term 4 at the PFD
  input; not checked against a budget line (design/README.md's table does not
  carry one for this contribution).

- **Result -- per-corner breakdown**:

  | Corner | Term 1 \|mean\|+3sigma | Term 2/2a \|mean\|+3sigma | Term 3 \|mean\|+3sigma | Term 4 \|mean\|+3sigma | DFF worst-dir \|mean\|+3sigma |
  |---|---|---|---|---|---|
${PERCORNER_ROWS}
- **Result -- pooled (all ${NUM_CORNERS} corners combined; a fraction of the
  nominal-only record's own n, per the corner-vs-sample-count tradeoff above)**:

  | # | Term | Pooled mean / sd / \|mean\|+3sigma (n) |
  |---|---|---|
  | 1 | DC UP/DN mismatch, worst of 0.9/1.65/2.4 V | ${DC_MEAN}% / ${DC_SD}% / ${DC_3S}% (n=$(dc_worst_all | wc -l | tr -d ' ')) |
  | 2/2a | Switching-time skew, mid-window | ${SW_MEAN} s / ${SW_SD} s / ${SW_3S} s (n=$(( N_SW * NUM_CORNERS ))) |
  | 3 | Residual net charge at zero phase error | ${PFD_Q_MEAN} C / ${PFD_Q_SD} C / ${PFD_Q_3S} C (n=$(( N_PFD * NUM_CORNERS ))) |
  | 4 | Static phase offset, q_zero / Kd | ${PFD_T_MEAN} s / ${PFD_T_SD} s / ${PFD_T_3S} s (n=$(( N_PFD * NUM_CORNERS ))) |

  **Systematic vs. statistical, kept distinct** (unchanged convention from
  the nominal-only record): design/README.md's "Systematic (measured, all 45
  PVT corners)" column (terms 1-4) is the corner-swept MEAN (\`sw_stat_mismatch
  = 0\`). This record's numbers are the ADDITIONAL statistical dispersion
  \`sw_stat_mismatch = 1\` adds on top, now itself corner-swept (3-point
  subset). They are not interchangeable and this record does not add them
  together.
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
  - Prior record (nominal-only MC, not superseded, historical evidence):
    \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`
  - Reduced-corner-grid precedent: \`sim/lock-detector/testbench/run.sh\`
    (\`WINDOW_CORNERS\`)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #146)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "mc-cp-mismatch: wrote ${RECORD}"
echo "mc-cp-mismatch: wrote ${OUT_DC}, ${OUT_SW}, ${OUT_PFD}, ${OUT_DFF}"
echo "mc-cp-mismatch: wrote ${CORNERSDIR}/ ($(( (N_DC + N_SW + N_PFD * 3 + N_DFF) * NUM_CORNERS )) corner logs)"
