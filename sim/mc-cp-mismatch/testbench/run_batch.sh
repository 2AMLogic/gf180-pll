#!/usr/bin/env bash
# gf180-pll :: mc-cp-mismatch :: batch-fleet transport for the Monte Carlo
# campaign (#826 re-qualification under open_pdks f6eeac7)
#
# run.sh composes one ngspice deck per (stage, corner, seed) itself, via
# sim/lib/simenv.sh's simenv_run_deck -- a campaign form the harness's corner
# manifest cannot express (run.sh's own header comment records the two gaps:
# the sw_stat_mismatch override ordering and the per-sample `.option rndseed`
# axis). On a dispatch host KLT_SIM_BACKEND=batch rightly refuses that local
# fan-out (simenv_guard_local_grid, #740), so the sanctioned fleet route for a
# self-composing campaign is `klt sim`'s DECK-LIST transport ("pre-composed
# decks"): each unit's deck ships byte-for-byte, runs with `ngspice -b` on its
# own execution host under the batch image's pinned PDK, and the unit's raw
# stdout comes back. This driver is that transport's compose/submit/collect
# half; the reduction, control, statistics and record minting stay run.sh's,
# driven with SIM_FLEET_REPLAY=1 over the collected logs.
#
# Deck bytes mirror simenv_run_deck's composition exactly -- same card order
# (`.include design.ngspice`, `.lib <models> <section>`, `.temp`,
# `.param sim_temp`, the kv overrides with `.option rndseed` special-cased,
# `.include <campaign deck>`, `.end`) -- with exactly two path-spelling
# differences the transport requires: PDK files are named through
# `$PDK_ROOT/...` (expanded by the executing host; the batch image pins
# open_pdks f6eeac7) and repo files (campaign deck, dut.spice) are staged
# relatively as unit inputs. Everything that could change a result -- corner
# section, temp, supply, vctrl/dphi, sw_stat_mismatch, the per-sample seed --
# is identical bytes to what simenv_run_deck writes locally. The unit id IS
# run.sh's ${WORK} tag, so a collected log lands exactly where run.sh's
# parsers and the record's log archiver expect it.
#
# The DUT exports are the same files run.sh itself produces:
#   design/netlist.sh --top pfd_cp ${WORK}   -> ${WORK}/dut.spice
#   cat design/netlist/dff_tg_3v3.spice tb_mc_dff_ctq.sp -> ${WORK}/dut_dff.spice
# The xschem export is byte-deterministic (its sha256 is recorded in the
# committed cp-compliance records and reproduces), so the bytes the fleet runs
# are the bytes run.sh's minting snapshots.
#
# Grids (one per successor record this re-qualification mints):
#   control   run.sh --control's grid: 21 corners x 4 stages x 5 runs
#   full      run.sh's default campaign: 21 corners x (N_DC dc + N_SW sw +
#             N_PFD x 3 dphi pfd + N_DFF dff), N defaults as run.sh's
#   nominal   20260731-212614-640560e's own grid: typical/27C/3.30V only,
#             N_DC=200 N_SW=40 N_PFD=40 N_DFF=50
#
# Compose retains every expected unit. A cached unit is eligible for reuse
# only when its collected worker receipt, input digests and log agree.
#
# Usage:
#   ./run_batch.sh compose <grid> [record-id] # export DUTs, or use the record's frozen DUTs
#   ./run_batch.sh submit   <grid>            # --submit-only each request (persist each accepted job)
#   ./run_batch.sh status   <grid>            # one klt sim --job-status line per job
#   ./run_batch.sh collect  <grid>            # --attach every job, copy stdout -> WORK/<tag>/ngspice.log
#   ./run_batch.sh recover <grid>            # re-attach jobs from the original two-column jobs.tsv
#   ./run_batch.sh publish <grid> <record-id> # store verified evidence from an existing record
#   ./run_batch.sh verify   <grid>            # every expected tag present + parseable (no klt)
# A submit refused for capacity is retried by klt's own --wait-for-capacity
# (600 s, per CLAUDE.md host rules); a refusal that outlives it is reported,
# never worked around with a local grid.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
WORK="${EXP}/work"

GRID="${2:-}"
BATCH_DIR="${WORK}/batch/${GRID:-<grid>}"

# Campaign decks (same files run.sh runs).
DECK_DC="${HERE}/tb_mc_cp_dc.sp"
DECK_SW="${HERE}/tb_mc_cp_switch.sp"
DECK_PFD="${HERE}/tb_mc_pfd_cp.sp"
DECK_DFF_SRC="${REPO}/design/netlist/dff_tg_3v3.spice"
DECK_DFF_TB="${HERE}/tb_mc_dff_ctq.sp"

VCTRL_MID=1.65
N_DC="${N_DC:-100}"
N_SW="${N_SW:-16}"
N_PFD="${N_PFD:-16}"
N_DFF="${N_DFF:-20}"
CONTROL_SEED_A=1
CONTROL_SEED_B=97

# Same corner order and spellings as run.sh.
CORNER_POINTS=(
  "typical 27 3.30"
  "typical -40 2.97"
  "typical -40 3.63"
  "typical 125 2.97"
  "typical 125 3.63"
  "ss -40 2.97"
  "ss -40 3.63"
  "ss 125 2.97"
  "ss 125 3.63"
  "ff -40 2.97"
  "ff -40 3.63"
  "ff 125 2.97"
  "ff 125 3.63"
  "fs -40 2.97"
  "fs -40 3.63"
  "fs 125 2.97"
  "fs 125 3.63"
  "sf -40 2.97"
  "sf -40 3.63"
  "sf 125 2.97"
  "sf 125 3.63"
)

grid_corners() {
  case "${GRID}" in
    control|full) printf '%s\n' "${CORNER_POINTS[@]}" ;;
    nominal) echo "typical 27 3.30" ;;
    *) echo "ERROR: unknown grid '${GRID}' (control|full|nominal)" >&2; exit 1 ;;
  esac
}

grid_sample_counts() {
  case "${GRID}" in
    # nominal re-runs 20260731-212614-640560e's own per-point counts
    nominal) N_DC=200; N_SW=40; N_PFD=40; N_DFF=50 ;;
  esac
}

# stage_table lines: "<tag> <deck-file> <input1,input2,...> <timeout_s>"
# Enumerated in exactly run.sh's own order and tag spelling.
grid_units() {
  local point pc pt pv ctag s dphi dsuf mism seed runtag
  grid_sample_counts
  while read -r point; do
    read -r pc pt pv <<<"${point}"
    ctag="${pc}_${pt}c_${pv}v"
    case "${GRID}" in
      control)
        for runtag in mc1_seedA_run1 mc1_seedA_run2 mc1_seedB mc0_seedA mc0_seedB; do
          case "${runtag}" in
            mc1_seedA_run1|mc1_seedA_run2) mism=1; seed=${CONTROL_SEED_A} ;;
            mc1_seedB) mism=1; seed=${CONTROL_SEED_B} ;;
            mc0_seedA) mism=0; seed=${CONTROL_SEED_A} ;;
            mc0_seedB) mism=0; seed=${CONTROL_SEED_B} ;;
          esac
          emit ctl_dc  "${ctag}" "ctl_dc_${ctag}_${runtag}"  "${DECK_DC}" "${pc}" "${pt}" "${pv}" 900 "sw_stat_mismatch=${mism}" "rndseed=${seed}"
          emit ctl_sw  "${ctag}" "ctl_sw_${ctag}_${runtag}"  "${DECK_SW}" "${pc}" "${pt}" "${pv}" 1800 "vctrl=${VCTRL_MID}" "sw_stat_mismatch=${mism}" "rndseed=${seed}"
          emit ctl_pfd "${ctag}" "ctl_pfd_${ctag}_${runtag}" "${DECK_PFD}" "${pc}" "${pt}" "${pv}" 1800 "dphi=0" "sw_stat_mismatch=${mism}" "rndseed=${seed}"
          emit ctl_dff "${ctag}" "ctl_dff_${ctag}_${runtag}" "${WORK}/dut_dff.spice" "${pc}" "${pt}" "${pv}" 900 "sw_stat_mismatch=${mism}" "rndseed=${seed}"
        done
        ;;
      full|nominal)
        for s in $(seq 1 "${N_DC}"); do
          emit dc "${ctag}" "dc_${ctag}_seed$(printf '%03d' "${s}")" "${DECK_DC}" "${pc}" "${pt}" "${pv}" 900 "sw_stat_mismatch=1" "rndseed=${s}"
        done
        for s in $(seq 1 "${N_SW}"); do
          emit sw "${ctag}" "sw_${ctag}_seed$(printf '%03d' "${s}")" "${DECK_SW}" "${pc}" "${pt}" "${pv}" 1800 "vctrl=${VCTRL_MID}" "sw_stat_mismatch=1" "rndseed=${s}"
        done
        for s in $(seq 1 "${N_PFD}"); do
          for dphi in -1n 0 1n; do
            dsuf="d${dphi}"; dsuf="${dsuf//./p}"; dsuf="${dsuf//-/m}"
            emit pfd "${ctag}" "pfd_${ctag}_seed$(printf '%03d' "${s}")_${dsuf}" "${DECK_PFD}" "${pc}" "${pt}" "${pv}" 1800 "dphi=${dphi}" "sw_stat_mismatch=1" "rndseed=${s}"
          done
        done
        for s in $(seq 1 "${N_DFF}"); do
          emit dff "${ctag}" "dff_${ctag}_seed$(printf '%03d' "${s}")" "${WORK}/dut_dff.spice" "${pc}" "${pt}" "${pv}" 900 "sw_stat_mismatch=1" "rndseed=${s}"
        done
        ;;
    esac
  done < <(grid_corners)
}

# emit <stage> <ctag> <tag> <deck-abs-path> <bundle> <temp> <vdd> <timeout_s> [kv...]
# (vsup=<vdd> is prepended to every unit's kv list, exactly as every
# simenv_run_deck_retried call in run.sh passes it.)
emit() {
  local stage="$1" ctag="$2" tag="$3" deck="$4" pc="$5" pt="$6" pv="$7" tmo="$8"
  shift 8
  set -- "vsup=${pv}" "$@"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${tag}" "${stage}" "${ctag}" "${deck}" "${pc}" "${pt}" "${pv}" "${tmo}" "$*"
}

write_unit_deck() {
  # args: tag deck-abs-path bundle temp vdd kv...
  local tag="$1" deck="$2" pc="$3" pt="$4" pv="$5"
  shift 5
  local deckbase out kv key val
  deckbase="$(basename "${deck}")"
  out="${BATCH_DIR}/decks/${tag}.spice"
  {
    echo "* GENERATED by run_batch.sh -- do not edit; mirrors simenv_run_deck's"
    echo "* composition (sim/lib/simenv.sh) for the klt sim deck-list transport."
    echo "* tag=${tag} libs=${pc} temp=${pt}C"
    # PDK files are named through $PDK_ROOT/<variant>/...: the executing host
    # expands the variable (locally: the parent of the variant dir; on the
    # batch image: /opt/pdk, the family root volare enabled the variant into).
    # shellcheck disable=SC2016 # Expanded on the worker.
    echo '.include "$PDK_ROOT/gf180mcuD/libs.tech/ngspice/design.ngspice"'
    echo ".lib \"\$PDK_ROOT/gf180mcuD/libs.tech/ngspice/sm141064.ngspice\" ${pc}"
    echo ".temp ${pt}"
    echo ".param sim_temp=${pt}"
    for kv in "$@"; do
      key="${kv%%=*}"
      val="${kv#*=}"
      if [ "${key}" = "rndseed" ]; then
        echo ".option rndseed=${val}"
      else
        echo ".param ${key}=${val}"
      fi
    done
    echo ".include \"${deckbase}\""
    echo ".end"
  } >"${out}"
}

do_compose() {
  local netlist="${WORK}/dut.spice"
  mkdir -p "${BATCH_DIR}/decks"
  if [ -n "${1:-}" ]; then
    # Reconstruct a historical request against the DUT bytes frozen at mint.
    [[ "$1" =~ ^[0-9]{8}-[0-9]{6}-[0-9a-f]{7}$ ]] || { echo "invalid snapshot ID" >&2; exit 2; }
    cp "${EXP}/netlist-snapshots/$1-cppfd.spice" "${netlist}"
    cp "${EXP}/netlist-snapshots/$1-dff.spice" "${WORK}/dut_dff.spice"
  else
    "${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
    cat "${DECK_DFF_SRC}" "${DECK_DFF_TB}" >"${WORK}/dut_dff.spice"
  fi
  # The unit decks' `.include` targets must resolve on THIS host relative to
  # the deck file's directory, so the campaign decks and both DUT files are
  # staged into decks/ beside them; klt's closure stager ships them (and the
  # campaign deck's own `.include "dut.spice"`) at those relative paths into
  # every unit directory, deduped by content.
  cp "${DECK_DC}" "${DECK_SW}" "${DECK_PFD}" "${BATCH_DIR}/decks/"
  cp "${WORK}/dut.spice" "${WORK}/dut_dff.spice" "${BATCH_DIR}/decks/"

  local tag stage ctag deck pc pt pv tmo kvs
  grid_units >"${BATCH_DIR}/grid.tsv"
  while IFS=$'\t' read -r tag stage ctag deck pc pt pv tmo kvs; do
    # shellcheck disable=SC2086
    write_unit_deck "${tag}" "${deck}" "${pc}" "${pt}" "${pv}" ${kvs}
    printf '%s\t%s\t%s\t%s\t%s\n' "${tag}" "${stage}" "${ctag}" "${tmo}" "${deck##*/}"
  done <"${BATCH_DIR}/grid.tsv" >"${BATCH_DIR}/units.tsv.new"
  mv "${BATCH_DIR}/units.tsv.new" "${BATCH_DIR}/units.tsv"
}

case "${GRID}" in
  control|full|nominal) ;;
  *) echo 'usage: run_batch.sh {compose|submit|status|collect|recover|publish|verify} {control|full|nominal}' >&2; exit 2 ;;
esac
mkdir -p "${BATCH_DIR}"
# The three grids share their per-tag cache. Serialize updates to it and to
# the ledger, including the submit/checkpoint pair.
exec 9>"${WORK}/batch/transport.lock"
flock 9
if [ "${1:-}" = publish ]; then
  rid="${3:?publish needs the record ID}"
  exec python3 "${HERE}/fleet_archive.py" publish "${EXP}/corners/${rid}" "${GRID}" "${rid}"
fi
if [ "${1:-}" = compose ]; then
  do_compose "${3:-}"
fi
exec python3 "${HERE}/fleet_batch.py" "${1:-}" "${BATCH_DIR}"
