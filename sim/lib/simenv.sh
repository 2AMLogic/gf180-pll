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

# MOS process corner sections in sm141064.ngspice
SIMENV_MOS_CORNERS=(typical ff ss fs sf)
# Passive process corner sections have their OWN axes, independent of the MOS
# tt/ff/ss/fs/sf sections. A MOS-corner-only sweep silently leaves passives at
# typical, so campaigns must name these explicitly.
SIMENV_MIMCAP_CORNERS=(mimcap_typical mimcap_ff mimcap_ss)
SIMENV_MOSCAP_CORNERS=(moscap_typical moscap_ff moscap_ss)
SIMENV_RES_CORNERS=(res_typical res_ff res_ss)

# Temperature grid, degrees C
SIMENV_TEMPS=(-40 27 125)
# Supply grid, volts (3.3 V +/- 10%)
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

# Emit a provenance header. Every results file starts with one of these so a
# recorded table is self-describing (repo evidence convention).
# Args: <campaign> <netlist-path> <corner-list-description>
simenv_provenance() {
  local campaign="$1" netlist="$2" corners="$3"
  cat <<EOF
# campaign: ${campaign}
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
    local sec
    # shellcheck disable=SC2086
    for sec in ${libs//,/ }; do
      echo ".lib \"${SIMENV_MODELS}\" ${sec}"
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
