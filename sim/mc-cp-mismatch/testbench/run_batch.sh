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
# compose skips any tag whose ${WORK}/<tag>/ngspice.log already exists, so a
# re-compose after a partial collect resumes rather than re-spends (the
# nominal grid's typical-corner tags 1..16 etc. reuse the full campaign's
# logs -- deterministic same-seed reruns, not new evidence).
#
# Usage:
#   ./run_batch.sh compose  <grid>            # write per-corner requests + unit decks
#   ./run_batch.sh submit   <grid>            # --submit-only each request (job ids -> jobs.tsv)
#   ./run_batch.sh status   <grid>            # one klt sim --job-status line per job
#   ./run_batch.sh collect  <grid>            # --attach every job, copy stdout -> WORK/<tag>/ngspice.log
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

# 21-point vertex set -- MUST match run.sh's CORNER_POINTS array; the counts
# and spellings below are cross-checked against it by `compose` (the script
# sources run.sh's array verbatim through MCCP_CORNER_POINTS round-tripping:
# compose enumerates from this copy, verify re-reads run.sh's own array the
# same way run.sh's loops do, so a drift between the two fails loudly).
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
  if [ -s "${WORK}/${tag}/ngspice.log" ]; then
    echo "skip ${tag} (log present)"
    return 0
  fi
  local stage_input
  if [ "${deck}" = "${WORK}/dut_dff.spice" ]; then
    stage_input="dut_dff.spice"
  else
    stage_input="dut.spice"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${tag}" "${stage}" "${ctag}" "${deck}" "${stage_input}" "${pc}" "${pt}" "${pv}" "${tmo}$([ $# -gt 0 ] && printf '\t%s' "$*")"
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

stage_marker() {
  case "$1" in
    dc|ctl_dc)   echo '^MCDC_LO ' ;;
    sw|ctl_sw)   echo '^MCSW ' ;;
    pfd|ctl_pfd) echo '^MCPFD ' ;;
    dff|ctl_dff) echo 'tcq_r' ;;
    *) echo "ERROR: unknown stage $1" >&2; exit 1 ;;
  esac
}

do_compose() {
  local netlist="${WORK}/dut.spice"
  mkdir -p "${BATCH_DIR}/decks"
  echo "run_batch: exporting design/ via netlist.sh (same export run.sh snapshots) ..."
  "${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
  [ -f "${netlist}" ] || { echo "ERROR: ${netlist} not produced" >&2; exit 1; }
  cat "${DECK_DFF_SRC}" "${DECK_DFF_TB}" >"${WORK}/dut_dff.spice"
  # The unit decks' `.include` targets must resolve on THIS host relative to
  # the deck file's directory, so the campaign decks and both DUT files are
  # staged into decks/ beside them; klt's closure stager ships them (and the
  # campaign deck's own `.include "dut.spice"`) at those relative paths into
  # every unit directory, deduped by content.
  cp "${DECK_DC}" "${DECK_SW}" "${DECK_PFD}" "${BATCH_DIR}/decks/"
  cp "${WORK}/dut.spice" "${WORK}/dut_dff.spice" "${BATCH_DIR}/decks/"

  local tag stage ctag deck inputs pc pt pv tmo kvs ucount=0 skipped
  : >"${BATCH_DIR}/units.tsv"
  while IFS=$'\t' read -r tag stage ctag deck inputs pc pt pv tmo kvs; do
    [ -n "${tag}" ] || continue
    # shellcheck disable=SC2086
    write_unit_deck "${tag}" "${deck}" "${pc}" "${pt}" "${pv}" ${kvs:-}
    printf '%s\t%s\t%s\t%s\t%s\n' "${tag}" "${stage}" "${ctag}" "${tmo}" "${inputs}" >>"${BATCH_DIR}/units.tsv"
    ucount=$((ucount+1))
  done < <(grid_units | grep -v '^skip ')
  skipped=$(grid_units | grep -c '^skip ' || true)

  # one request per corner: fleet-parallel across corners, one job id each
  python3 - "${BATCH_DIR}" <<'PYEOF'
import json, sys, re
bdir = sys.argv[1]
reqs = {}
with open(f"{bdir}/units.tsv") as f:
    for line in f:
        tag, stage, ctag, tmo, _ = (line.rstrip("\n").split("\t") + [""]*5)[:5]
        reqs.setdefault(ctag, []).append(
            {"id": tag, "deck": f"decks/{tag}.spice", "outputs": [], "timeout_s": int(tmo)})
for ctag, decks in sorted(reqs.items()):
    req = {"backend": "batch",
           "models": {"pdk": "gf180mcuD"},
           "decks": decks,
           "options": {"timeout_s": 1800},
           "batch": {"capacity_wait_s": 600, "poll_timeout_s": 86400}}
    name = re.sub(r"[^A-Za-z0-9]", "", ctag)
    with open(f"{bdir}/req-{name}.json", "w") as f:
        json.dump(req, f, indent=1)
    print(f"req-{name}.json: {len(decks)} units")
PYEOF
  echo "run_batch: composed ${ucount} unit deck(s) under ${BATCH_DIR} (${skipped} skipped: log already present)"
}

# Parse a --submit-only output (json or text) down to its job id.
submit_job_id() {
  python3 -c '
import json, re, sys
raw = sys.stdin.read()
i = raw.find("{")
if i >= 0:
    try:
        d = json.loads(raw[i:])
        j = d.get("job_id") or d.get("job", {}).get("job_id")
        if j:
            print(j); sys.exit(0)
    except Exception:
        pass
m = re.search(r"job_id\"?\s*[=:]\s*\"?([A-Za-z0-9._-]+)", raw)
if m:
    print(m.group(1))
' <<<"$1"
}

do_submit() {
  local req idjson id stem
  : >"${BATCH_DIR}/jobs.tsv.new"
  [ -f "${BATCH_DIR}/jobs.tsv" ] && cp "${BATCH_DIR}/jobs.tsv" "${BATCH_DIR}/jobs.tsv.new"
  for req in "${BATCH_DIR}"/req-*.json; do
    [ -e "${req}" ] || { echo "ERROR: no req-*.json under ${BATCH_DIR}; compose first" >&2; exit 1; }
    stem="$(basename "${req}")"
    if grep -q "^${stem}	" "${BATCH_DIR}/jobs.tsv.new" 2>/dev/null; then
      echo "run_batch: ${stem} already submitted, skipping"
      continue
    fi
    echo "run_batch: submitting ${stem} ..."
    idjson=$(klt sim "${req}" --submit-only --wait-for-capacity 600 --format json 2>&1)
    id=$(submit_job_id "${idjson}")
    [ -n "${id}" ] || { echo "ERROR: no job id parsed from submit output:" >&2; printf '%s\n' "${idjson}" >&2; exit 1; }
    printf '%s\t%s\n' "${stem}" "${id}" >>"${BATCH_DIR}/jobs.tsv.new"
    printf '%s' "${id}" >"${BATCH_DIR}/jobid-$(basename "${req}" .json).txt"
  done
  mv "${BATCH_DIR}/jobs.tsv.new" "${BATCH_DIR}/jobs.tsv"
  echo "run_batch: submitted $(wc -l <"${BATCH_DIR}/jobs.tsv" | tr -d ' ') job(s); see ${BATCH_DIR}/jobs.tsv"
}

do_status() {
  local req stem id state
  while IFS=$'\t' read -r stem id; do
    [ -n "${id}" ] || { echo "${stem}: no job id recorded" >&2; continue; }
    req="${BATCH_DIR}/${stem}"
    state=$(klt sim "${req}" --job-status "${id}" --format json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("state") or d.get("status","?"))' 2>/dev/null || echo "?")
    echo "${stem}: ${id} ${state}"
  done <"${BATCH_DIR}/jobs.tsv"
}

do_collect() {
  local req stem id out tag base n=0 fail=0
  while IFS=$'\t' read -r stem id; do
    [ -n "${id}" ] || { echo "ERROR: ${stem}: no job id recorded" >&2; exit 1; }
    req="${BATCH_DIR}/${stem}"
    out="${BATCH_DIR}/out-$(basename "${stem}" .json)"
    echo "run_batch: attaching ${id} (${stem}) -> ${out} ..."
    klt sim "${req}" --attach "${id}" -o "${out}" --format json >/dev/null
    for tag in "${out}"/*/; do
      tag="${tag%/}"
      base="$(basename "${tag}")"
      if [ -s "${tag}/stdout.bin" ]; then
        mkdir -p "${WORK}/${base}"
        cp "${tag}/stdout.bin" "${WORK}/${base}/ngspice.log"
        n=$((n+1))
      else
        echo "ERROR: unit ${base} produced no stdout" >&2
        fail=$((fail+1))
      fi
    done
  done <"${BATCH_DIR}/jobs.tsv"
  echo "run_batch: collected ${n} unit log(s) into ${WORK} (${fail} missing stdout)"
  [ "${fail}" -eq 0 ]
}

do_verify() {
  local missing=0 bad=0 total=0 tag stage marker
  while IFS=$'\t' read -r tag stage _; do
    total=$((total+1))
    if [ ! -s "${WORK}/${tag}/ngspice.log" ]; then
      echo "MISSING ${tag}"
      missing=$((missing+1))
      continue
    fi
    marker=$(stage_marker "${stage}")
    if ! grep -qE "${marker}" "${WORK}/${tag}/ngspice.log"; then
      echo "UNPARSEABLE ${tag} (no ${marker} line)"
      bad=$((bad+1))
    fi
  done <"${BATCH_DIR}/units.tsv"
  echo "run_batch: verify ${GRID}: ${total} unit(s), ${missing} missing, ${bad} unparseable"
  [ "${missing}" -eq 0 ] && [ "${bad}" -eq 0 ]
}

case "${1:-}" in
  compose)  [ -n "${GRID}" ] || { echo "usage: $0 compose <control|full|nominal>" >&2; exit 1; }; do_compose ;;
  submit)   [ -n "${GRID}" ] || { echo "usage: $0 submit <grid>" >&2; exit 1; }; do_submit ;;
  status)   [ -n "${GRID}" ] || { echo "usage: $0 status <grid>" >&2; exit 1; }; do_status ;;
  collect)  [ -n "${GRID}" ] || { echo "usage: $0 collect <grid>" >&2; exit 1; }; do_collect ;;
  verify)   [ -n "${GRID}" ] || { echo "usage: $0 verify <grid>" >&2; exit 1; }; do_verify ;;
  *) echo "usage: $0 {compose|submit|status|collect|verify} <control|full|nominal>" >&2; exit 1 ;;
esac
