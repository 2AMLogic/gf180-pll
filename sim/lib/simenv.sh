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
# Closed-loop integration bound (a property of the PFD, not of any one bench)
# --------------------------------------------------------------------------
#
# Ceiling on the ngspice INTERNAL transient timestep for any campaign whose DUT
# contains the PFD (design/pfd_cp.sch). It is set by the PFD's INTERNAL SET
# PULSE -- not by f_out, and not by the UP/DN output pulse either.
# design/edgedet.sch fires each SR latch with AND(X, NOT(X delayed by 5
# inverters)); that pulse measures 0.33-0.39 ns. The UP/DN pulse it eventually
# produces is 1.1-1.9 ns wide (the 24-inverter reset chain) and sizing the
# ceiling from THAT number is the trap: an integrator whose mean internal step
# is comparable to the set pulse steps clean over it on a large fraction of
# feedback edges, and every miss is an edge the PFD never sees -- the loop then
# reads as jammed with UP asserted, ramping Vctrl to the rail while the
# feedback is ALREADY faster than the reference. That is a "the loop does not
# lock" result which is entirely an artefact of the integration.
#
# 100 ps puts 3-4 internal steps inside the set pulse. First established and
# measured by sim/pll-top-smoke (see its run.sh KTMAX comment and
# sim/pll-top-smoke/records/20260801-085349-0e5c22d.md); hoisted here because
# EVERY closed-loop campaign inherits it, and two of them (sim/lock-time,
# sim/output-range) were previously sizing the ceiling from f_out and
# violating it. See sim/README.md's "Closed-loop internal-timestep bound".
#
# Campaigns pass this to their deck's `.tran <tstep> <tstop> 0 <tmax>` 4th
# argument. Leaving that argument off is what causes the violation: ngspice
# then defaults the internal ceiling to the PRINT step, silently tying the
# integration accuracy to an unrelated output-waveform quantity.
#
# SIM_TMAX overrides it. This exists for ONE legitimate use -- a deliberate
# bound-sensitivity study, where the point is to run the same corner at two
# ceilings in one environment so the ceiling is the only variable (that is how
# #65 established the bound actually changes this DUT's verdict, rather than
# inferring it from two runs that also differed in simulator version and host).
# It is NOT a knob for making a slow campaign finish: a record minted at a
# ceiling coarser than the value above is not evidence about the loop, and the
# campaign runners put the effective value in their work-directory tag so such
# a run cannot be quietly mistaken for a compliant one.
# shellcheck disable=SC2034
SIMENV_CLOSED_LOOP_TMAX="${SIM_TMAX:-100p}"

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

# Schematic-capture tool version, for campaigns whose DUT netlist is an xschem
# export rather than a hand-written deck. Prints "unknown" if xschem is absent.
simenv_xschem_version() {
  if command -v xschem >/dev/null 2>&1; then
    xschem -v 2>&1 | awk '/XSCHEM/ {print tolower($1) " " $2; exit}'
  else
    echo "unknown"
  fi
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

# The "Supersedes" field of a record, per sim/README.md :: "Status /
# supersession language".
#
# That field is the ONLY pointer between a superseded record and the one that
# replaces it -- the superseded record's bytes are never edited, so standing is
# found by reading FORWARD from the old record to whichever new record names
# it. It therefore has to be settable AT MINT TIME: editing the field into an
# already-generated record afterwards is itself the rewrite the append-only
# rule forbids, even when the record is still uncommitted, because nothing
# distinguishes that edit from any other after-the-fact edit.
#
#   simenv_supersedes_field "${SIM_SUPERSEDES:-}"
#
# The reason is shared across every record a single invocation mints and comes
# from SIM_SUPERSEDES_NOTE. A runner that mints SEVERAL records in one
# invocation (divider-ratio mints three) passes a different variable per
# record -- SIM_SUPERSEDES_DFF, SIM_SUPERSEDES_CELL, ... -- so each record
# names the record it actually replaces rather than sharing one id.
#
# Called with an empty id the field reads exactly as the hardcoded line it
# replaced, so an ordinary first run of any campaign is unchanged.
#
# (#26 introduced this as a `supersedes_field` local to the pfd-deadzone and
# cp-compliance runners; it is hoisted here because #28's re-record pass needs
# the same field in four more runners, and five copies of one three-branch
# `if` is how the copies drift.)
simenv_supersedes_field() {
  local prior="${1:-}" note="${SIM_SUPERSEDES_NOTE:-}"
  if [ -z "${prior}" ]; then
    echo "- **Supersedes**: (none -- first record for this claim)"
  elif [ -z "${note}" ]; then
    echo "- **Supersedes**: ${prior}"
  else
    echo "- **Supersedes**: ${prior} -- ${note}"
  fi
}

# Emits with a LEADING newline and none trailing, so it is appended to the end
# of the last Methodology bullet: command substitution strips trailing
# newlines, so a trailing-newline form would run the next field onto the same
# line.
#
# (#26/#28 introduced this as a `method_note` local to cp-compliance,
# loop-dynamics, and pfd-deadzone; it is hoisted here for the same reason
# #135 hoisted `supersedes_field` -- three byte-identical copies is drift
# waiting to happen.)
simenv_method_note() {
  [ -n "${SIM_METHOD_NOTE:-}" ] && printf '\n  - %s' "${SIM_METHOD_NOTE}"
  return 0
}

# N -> chain programming (DR-001 Decision 3 chain-length/modulus encoding):
# N = 2^k + sum(p_i . 2^i) for i<k, SEL_(k-1)=1.
# Prints "k sel0..sel5 p0..p5" as 13 space-separated 0/1 fields plus k.
#
# (Hoisted from byte-identical local copies in sim/divider-ratio,
# sim/output-range, and sim/lock-time's testbench/run.sh -- lock-time's
# own copy already noted "same algorithm as
# sim/divider-ratio/testbench/run.sh" in a comment.)
simenv_n_to_code() {
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

# Map a MOS process-corner bundle name to the comma-separated list of
# sm141064.ngspice `.lib` sections a campaign should include for it
# (passives held at typical -- the five-bundle typical/ff/ss/fs/sf scheme).
#
# (Hoisted from byte-identical local copies in sim/output-range and
# sim/lock-time's testbench/run.sh. sim/vco-tuning-range/testbench/common.sh
# has its own DIFFERENT bundle_libs -- an all-slow/all-fast two-bundle
# scheme -- deliberately not deduplicated here; see that file's header
# comment.)
simenv_bundle_libs() {
  case "$1" in
    typical) echo "typical,res_typical,moscap_typical,mimcap_typical" ;;
    ff)      echo "ff,res_typical,moscap_typical,mimcap_typical" ;;
    ss)      echo "ss,res_typical,moscap_typical,mimcap_typical" ;;
    fs)      echo "fs,res_typical,moscap_typical,mimcap_typical" ;;
    sf)      echo "sf,res_typical,moscap_typical,mimcap_typical" ;;
    *) echo "ERROR: unknown bundle $1" >&2; exit 1 ;;
  esac
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
#
# simenv_env_block [schematic-capture-note] [switches-note]
#   The first optional argument replaces the default schematic-capture
#   sentence, for campaigns whose DUT netlist IS an xschem export
#   (sim/README.md requires the schematic-capture version whenever the
#   netlist came from a schematic). The second replaces the default
#   statistical-switches sentence, for campaigns (#15, mc-cp-mismatch) that
#   deliberately override `sw_stat_mismatch` away from design.ngspice's
#   default -- reporting "nominal skew, no Monte Carlo" for a run that turned
#   mismatch ON would misstate the record's own environment. Called with no
#   arguments the wording is unchanged, so every existing campaign keeps
#   emitting exactly what it emitted before.
simenv_env_block() {
  local capture="${1:-N/A — these
    testbenches are hand-written SPICE, not an xschem export; there is no
    schematic for a device-level DUT.}"
  local switches="${2:-\`design.ngspice\` included first, leaving its default
    statistical switches \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    skew, no Monte Carlo)}"
  cat <<EOF
  - PDK: volare \`$(simenv_pdk_variant)\`, open_pdks \`$(simenv_pdk_hash)\`
  - Models: \`libs.tech/ngspice/sm141064.ngspice\` (MIM devices via
    \`sm141064_mim.ngspice\`, pulled in by the \`mimcap_*\` sections);
    ${switches}
  - Simulator: $(simenv_ngspice_version). Schematic capture: ${capture}
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
    local kv key val
    for kv in "$@"; do
      key="${kv%%=*}"
      val="${kv#*=}"
      if [ "${key}" = "rndseed" ]; then
        # Monte Carlo seeding (#15, mc-cp-mismatch): ngspice's per-instance
        # mismatch draws (agauss() inside the gf180mcu nfet_03v3_dss /
        # pfet_03v3_dss subcircuits, gated by sw_stat_mismatch) are evaluated
        # once at netlist parse time, BEFORE any `.control` block runs -- so
        # `set rndseed=N` inside `.control` is too late to affect them (it only
        # reseeds behavioral-source noise for whatever analysis runs after it).
        # `.option rndseed=N` at the top level is read at parse time and DOES
        # make the mismatch draws reproducible: same seed -> same draws, a
        # different seed -> an independent draw. This is the ONLY kv key this
        # function treats specially; every other key becomes a `.param` line
        # as before.
        echo ".option rndseed=${val}"
      else
        echo ".param ${key}=${val}"
      fi
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
