#!/usr/bin/env bash
# Shared ngspice corner-sweep helpers for the gf180-pll device-characterization
# campaigns.
#
# This is a deliberately small, self-contained shim: it exists so the three
# `sim/devchar-*` campaigns can run raw ngspice decks over the repo's PVT corner
# grid before the sim-harness (#2) lands. Folding these campaigns into the
# harness later is mechanical -- the decks themselves contain no corner logic,
# they only read `.param` values that this shim injects through a generated
# header.
#
# Usage from a campaign runner:
#   . "$(dirname "$0")/../lib/simenv.sh"
#   simenv_require_tools
#   simenv_run_deck <deck.sp> <workdir> <tag> <lib-sections> <temp_c> [param=value ...]
#
# shellcheck shell=bash

set -euo pipefail

# --------------------------------------------------------------------------
# Environment pin
# --------------------------------------------------------------------------

# PDK root. Override with GF180_PDK_ROOT to point at a different volare install.
SIMENV_PDK_ROOT="${GF180_PDK_ROOT:-$HOME/.volare/gf180mcuD}"
SIMENV_MODELS="${SIMENV_PDK_ROOT}/libs.tech/ngspice/sm141064.ngspice"
SIMENV_DESIGN="${SIMENV_PDK_ROOT}/libs.tech/ngspice/design.ngspice"

# --------------------------------------------------------------------------
# Corner grid (repo protocol: every recorded result carries full PVT coverage)
# --------------------------------------------------------------------------

# Every array below is consumed by the campaign runners that source this file,
# never inside it -- hence the SC2034 suppressions.

# MOS process corner sections in sm141064.ngspice
# shellcheck disable=SC2034
SIMENV_MOS_CORNERS=(typical ff ss fs sf)

# Passive process corner sections have their OWN axes, independent of the MOS
# tt/ff/ss/fs/sf sections. A MOS-corner-only sweep silently leaves passives at
# typical, so campaigns must name these explicitly. The three arrays are kept
# index-aligned (typical / ff / ss) so a runner can step them in lockstep.
# shellcheck disable=SC2034
SIMENV_MIMCAP_CORNERS=(mimcap_typical mimcap_ff mimcap_ss)
# shellcheck disable=SC2034
SIMENV_MOSCAP_CORNERS=(moscap_typical moscap_ff moscap_ss)
# shellcheck disable=SC2034
SIMENV_RES_CORNERS=(res_typical res_ff res_ss)

# Temperature grid, degrees C
# shellcheck disable=SC2034
SIMENV_TEMPS=(-40 27 125)
# Supply grid, volts (3.3 V +/- 10%)
# shellcheck disable=SC2034
SIMENV_VDDS=(2.97 3.30 3.63)

# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

simenv_pdk_hash() {
  # volare records the open_pdks commit it built from in SOURCES.
  if [ -f "${SIMENV_PDK_ROOT}/SOURCES" ]; then
    awk '/open_pdks/ {print $2; exit}' "${SIMENV_PDK_ROOT}/SOURCES"
  else
    echo "unknown"
  fi
}

simenv_pdk_variant() {
  basename "${SIMENV_PDK_ROOT}"
}

simenv_ngspice_version() {
  ngspice -v 2>&1 | awk '/ngspice-/ {gsub(/^\*+ /,""); sub(/ :.*/,""); print; exit}'
}

simenv_repo_root() {
  git rev-parse --show-toplevel
}

simenv_git_sha() {
  git rev-parse --short=7 HEAD
}

# "clean" or "DIRTY" -- a dirty-tree record is not reproducible from the sha
# alone, and sim/README.md requires the record to say so.
simenv_git_state() {
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then echo "DIRTY"; else echo "clean"; fi
}

simenv_host() {
  echo "$(uname -s) $(uname -r) / $(uname -m)"
}

# Mint a record ID per sim/README.md: <YYYYMMDD>-<HHMMSS>-<short-sha>, UTC.
simenv_record_id() {
  echo "$(date -u +%Y%m%d-%H%M%S)-$(simenv_git_sha)"
}

simenv_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

# Emit a provenance header. Every extracted-metrics CSV starts with one of
# these so a table stays self-describing away from its record.
# Args: <campaign> <record-id> <netlist-path> <corner-list-description>
simenv_provenance() {
  local campaign="$1" rid="$2" netlist="$3" corners="$4"
  cat <<EOF
# campaign: ${campaign}
# record_id: ${rid}
# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)
# pdk_variant: $(simenv_pdk_variant)
# pdk_open_pdks_hash: $(simenv_pdk_hash)
# pdk_root: ${SIMENV_PDK_ROOT}
# model_file: libs.tech/ngspice/sm141064.ngspice (+ sm141064_mim.ngspice via mimcap_* sections)
# switches: design.ngspice defaults (sw_stat_global=0, sw_stat_mismatch=0 -> nominal skew, no Monte Carlo)
# simulator: $(simenv_ngspice_version)
# netlist: ${netlist}
# corners: ${corners}
EOF
}

# The "Environment provenance" block of a record, in the field order
# sim/README.md prescribes.
simenv_env_block() {
  cat <<EOF
  - PDK: volare \`$(simenv_pdk_variant)\`, open_pdks \`$(simenv_pdk_hash)\`
  - Models: \`libs.tech/ngspice/sm141064.ngspice\` (MIM devices via
    \`sm141064_mim.ngspice\`, pulled in by the \`mimcap_*\` sections);
    \`design.ngspice\` included first, leaving its default statistical switches
    \`sw_stat_global = sw_stat_mismatch = 0\` (nominal skew, no Monte Carlo)
  - Simulator: $(simenv_ngspice_version). Schematic capture: N/A — these
    testbenches are hand-written SPICE, not an xschem export; there is no
    schematic for a device-level DUT.
  - Repo commit: \`$(simenv_git_sha)\` ($(simenv_git_state) tree)
  - Host: $(simenv_host)
EOF
}

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

simenv_require_tools() {
  local missing=0
  command -v ngspice >/dev/null 2>&1 || {
    echo "ERROR: ngspice not found on PATH (brew install ngspice)" >&2
    missing=1
  }
  [ -f "${SIMENV_MODELS}" ] || {
    echo "ERROR: gf180mcu models not found at ${SIMENV_MODELS}" >&2
    echo "       Install with: volare enable --pdk gf180mcu <open_pdks-hash>" >&2
    echo "       or set GF180_PDK_ROOT to your PDK root." >&2
    missing=1
  }
  [ -f "${SIMENV_DESIGN}" ] || {
    echo "ERROR: ${SIMENV_DESIGN} not found" >&2
    missing=1
  }
  [ "${missing}" -eq 0 ] || exit 1
}

# --------------------------------------------------------------------------
# Deck generation + execution
# --------------------------------------------------------------------------

# simenv_run_deck <deck> <workdir> <tag> <lib-sections-csv> <temp_c> [param=value ...]
#
# Builds a generated top-level deck that
#   1. includes design.ngspice (statistical switches off),
#   2. pulls in each requested `.lib` section of sm141064.ngspice,
#   3. sets .temp and any campaign `.param` overrides,
#   4. includes the campaign netlist verbatim.
#
# The generated deck, ngspice log and any data files land in
# <workdir>/<tag>/. Returns non-zero if ngspice fails; the log is left in place
# for debugging.
simenv_run_deck() {
  local deck="$1" workdir="$2" tag="$3" libs="$4" temp="$5"
  shift 5

  local rundir="${workdir}/${tag}"
  mkdir -p "${rundir}"

  local gen="${rundir}/deck.sp"
  {
    echo "* GENERATED by simenv.sh -- do not edit; edit ${deck} instead"
    echo "* tag=${tag} libs=${libs} temp=${temp}C"
    echo ".include \"${SIMENV_DESIGN}\""
    # One .lib card per requested section. Split via tr rather than unquoted
    # word splitting so the helper behaves the same if it is ever sourced from
    # a shell that does not word-split unquoted expansions (zsh).
    printf '%s\n' "${libs}" | tr ',' '\n' | while read -r sec; do
      [ -n "${sec}" ] && echo ".lib \"${SIMENV_MODELS}\" ${sec}"
    done
    echo ".temp ${temp}"
    echo ".param sim_temp=${temp}"
    local kv
    for kv in "$@"; do
      echo ".param ${kv%%=*}=${kv#*=}"
    done
    echo ".include \"${deck}\""
    echo ".end"
  } >"${gen}"

  # ngspice must run with rundir as cwd so `wrdata` relative paths stay local.
  (cd "${rundir}" && ngspice -b -o ngspice.log "${gen}" >stdout.log 2>&1) || {
    echo "ERROR: ngspice failed for tag=${tag} (see ${rundir}/ngspice.log)" >&2
    return 1
  }

  # ngspice exits 0 on some model/measure errors; catch the common fatal ones.
  if grep -qiE "^ *(fatal|error)|could not find|unknown subckt|no such (vector|parameter)" \
      "${rundir}/ngspice.log" 2>/dev/null; then
    echo "ERROR: ngspice reported an error for tag=${tag}:" >&2
    grep -iE "^ *(fatal|error)|could not find|unknown subckt|no such (vector|parameter)" \
      "${rundir}/ngspice.log" | head -5 >&2
    return 1
  fi
  return 0
}

# Corner ID per sim/README.md: <corner-bundle>_<temp>c_<supply>v, supply always
# written to two decimals so filenames sort lexically in supply order.
# simenv_corner_id <bundle> <temp_c> <supply_v>
simenv_corner_id() {
  printf '%s_%sc_%.2fv\n' "$1" "$2" "$3"
}

# Archive one run as committed evidence: corners/<record-id>/<corner-id>.log,
# containing the exact generated deck followed by the raw ngspice output. The
# deck is prepended because the generated header (PDK path, .lib sections,
# .temp, .param overrides) is the half of the input ngspice does not echo, and
# without it the log is not sufficient to reproduce the run.
# simenv_archive_log <workdir> <tag> <corners-dir> <corner-id>
simenv_archive_log() {
  local workdir="$1" tag="$2" cornersdir="$3" cid="$4"
  local rundir="${workdir}/${tag}"
  mkdir -p "${cornersdir}"
  {
    echo "==== generated deck (${cid}) ===="
    cat "${rundir}/deck.sp"
    echo
    echo "==== ngspice output ===="
    cat "${rundir}/ngspice.log"
  } >"${cornersdir}/${cid}.log"
}

# Extract a `.meas` result from an ngspice batch log.
# simenv_meas <logfile> <measure-name>  -> prints the numeric value, or "nan"
simenv_meas() {
  local log="$1" name="$2"
  awk -v want="${name}" '
    {
      line = $0
      sub(/^[ \t]+/, "", line)
      n = index(line, "=")
      if (n == 0) next
      key = substr(line, 1, n - 1)
      gsub(/[ \t]+$/, "", key)
      if (tolower(key) != tolower(want)) next
      rest = substr(line, n + 1)
      if (match(rest, /-?[0-9]+\.?[0-9]*([eE][-+]?[0-9]+)?/)) {
        print substr(rest, RSTART, RLENGTH)
        exit
      }
    }
    END { }
  ' "${log}" | head -1 | grep -E '^-?[0-9]' || echo "nan"
}

# Number of parallel ngspice jobs. Device-level decks are tiny; the model-file
# parse dominates, so oversubscribing slightly is fine.
simenv_jobs() {
  if [ -n "${SIM_JOBS:-}" ]; then
    echo "${SIM_JOBS}"
  elif command -v sysctl >/dev/null 2>&1 && sysctl -n hw.ncpu >/dev/null 2>&1; then
    sysctl -n hw.ncpu
  elif command -v nproc >/dev/null 2>&1; then
    nproc
  else
    echo 4
  fi
}
