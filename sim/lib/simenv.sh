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
# Repo root (for relativizing generated-artifact headers, #247)
# --------------------------------------------------------------------------
#
# This file always lives at <repo-root>/sim/lib/simenv.sh, so two `dirname`
# hops off its own location -- not off $0 or the caller's cwd -- gives the
# checkout root regardless of whether this is the primary checkout or a
# `.loom/worktrees/issue-N` worktree. Used only to relativize paths this
# script itself echoes into generated headers; never touches the deck's
# `.include` path, which must stay absolute for ngspice to resolve it from
# its own rundir cwd.
SIMENV_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMENV_REPO_ROOT="$(cd "${SIMENV_LIB_DIR}/../.." && pwd)"

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

# (Hoisted from byte-identical local copies in sim/cp-compliance and
# sim/pfd-deadzone's testbench/run.sh -- the same file pair
# `simenv_supersedes_field`/`simenv_method_note` were hoisted from, for the
# same reason: two copies of one evidence-record field emitter is how the
# copies drift.)
simenv_author_field() {
  echo "- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #9)}"
}

# tag for a work subdirectory: filesystem-safe, unique per job.
#
# (Hoisted from byte-identical local copies in sim/divider-ratio and
# sim/lock-detector's testbench/run.sh.)
simenv_mktag() {
  local t="$*"
  t="${t// /_}"; t="${t//./p}"; t="${t//-/m}"
  echo "${t}"
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

# The divider chain length k, read back OUT of the encoding rather than
# computed a second time beside it (#159). cloop_divider_params (see
# sim/lib/pll_top_dut.sh) is the single owner of the SEL/P encoding; k is just
# "which one-hot SEL bit did it set", +1. Deriving it this way means a
# campaign's reported k_cells column cannot disagree with the bits the DUT
# was actually given.
#
# (Hoisted from byte-identical local copies in sim/lock-time and
# sim/output-range's testbench/run.sh -- #181.)
simenv_k_from_divparams() {
  printf '%s\n' "$1" | tr ' ' '\n' \
    | awk -F= '/^sel[0-9]_code=1$/ { print substr($1, 4, 1) + 1; found = 1 }
               END { if (!found) print 0 }'
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

# Data rows of a record CSV: neither the leading `simenv_provenance` `#`
# comment block nor the CSV header row.
#
# (Hoisted from byte-identical local copies in sim/mc-cp-mismatch and
# sim/vco-tuning-range's testbench/run.sh -- #183.)
simenv_datarows() {
  grep -v '^#' "$1" | tail -n +2
}

# simenv_stats_from_values <newline-separated values> -> "mean sd n"
#
# (Hoisted from byte-identical local copies in sim/mc-cp-mismatch and
# sim/vco-tuning-range's testbench/run.sh -- #183.)
simenv_stats_from_values() {
  awk '{x[n++]=$1; s+=$1} END{
    if (n==0) { print "nan nan 0"; exit }
    m=s/n
    for (i=0;i<n;i++) ss+=(x[i]-m)*(x[i]-m)
    sd = (n>1) ? sqrt(ss/(n-1)) : 0
    printf "%.6g %.6g %d\n", m, sd, n
  }'
}

# simenv_kv <space-separated key=value blob> <key> -> value
#
# Pull one key=value out of a summary-line blob. The leading-space anchor is
# load-bearing: an unanchored `grep -o "$1=..."` also matches the "$1=" inside
# a longer key like `mism_absmax_all_at=` or `wmin_min=`, which would
# silently turn a scalar into several lines of record text.
#
# (Hoisted from byte-identical local copies -- modulo the caller-specific
# line-prefix filter (`^DCSUM`/`^SUMMARY`) applied before the call -- in
# sim/cp-compliance (dcget/swget) and sim/pfd-deadzone's (get) testbench/
# run.sh -- #189.)
simenv_kv() {
  echo "$1" | grep -oE "(^| )$2=[^ ]*" | tr -d ' ' | cut -d= -f2
}

# simenv_stage_netlist <dest-dir> <source-netlist-path>
#
# Create <dest-dir> and copy the campaign's DUT netlist into it as
# <dest-dir>/dut.spice.
#
# (Hoisted from byte-identical local copies -- modulo which variable held the
# source netlist path (`NETLIST` vs `DUT`) -- in sim/mc-cp-mismatch,
# sim/loop-dynamics and sim/cp-compliance's testbench/run.sh -- #191.)
simenv_stage_netlist() {
  mkdir -p "$1"
  cp "$2" "$1/dut.spice"
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
# ngspice binary pin (#259)
# --------------------------------------------------------------------------
#
# Every citable `sim/` evidence record cites `ngspice-46`, and #241/#242
# tuned this shim's OpenMP-internal-thread-pin detection
# (simenv_apply_omp_pin above) against that specific build. The convention
# every host that has minted a record so far actually follows (see the
# `/home/ubuntu/.local/bin/ngspice`-cited records under
# sim/supply-sensitivity/records/) is to install that pinned build at
# `~/.local/bin/ngspice` -- NOT to rely on it winning whatever order the
# rest of PATH happens to be in.
#
# #259: on a host where that pinned binary is simply absent (never
# installed, or removed by an unrelated package upgrade), PATH falls
# through silently to whatever "ngspice" resolves to next -- e.g.
# Homebrew's current bottle, which self-reports `ngspice-47`. That fallback
# is not merely "an untested version": #153/sim/harness/README.md's
# "ngspice-46 required for nested nonlinear moscap decks" already
# documents that ngspice-47 mis-expands this PDK's nonlinear
# cap_*mos_03v3/06v0 loop-filter/VCO moscap family into a malformed
# element ("unknown parameter (e9)") whenever it is instantiated inside a
# named `.subckt` -- and #259 additionally found that build does not even
# exit on that error, it hangs indefinitely (~13-14% CPU), which stalls an
# entire `xargs`-driven run.sh job pool since the affected corner's slot
# never frees. A campaign that silently ran on the wrong binary because the
# pin happened to be missing is exactly the kind of quiet wrong number
# CLAUDE.md's "Verification is the product" line exists to prevent -- so
# the check below fails loudly by default instead.
#
# SIM_NGSPICE_BIN overrides the pinned path itself, for a host that
# deliberately keeps its pinned ngspice-46 build somewhere other than
# `~/.local/bin/ngspice` (e.g. a from-source `--prefix` install, per
# sim/harness/README.md's build recipe).
SIMENV_NGSPICE_PIN="${SIM_NGSPICE_BIN:-$HOME/.local/bin/ngspice}"

# simenv_require_ngspice_pin -- called by simenv_require_tools. Exits 0 (and,
# as a side effect, prepends the pinned binary's directory onto PATH so it is
# what every subsequent `ngspice` invocation in this process actually runs,
# regardless of what else sits earlier on the caller's PATH) when
# SIMENV_NGSPICE_PIN exists and is executable. Otherwise prints a detailed,
# actionable ERROR to stderr and returns 1 -- unless SIM_ALLOW_UNPINNED_NGSPICE
# is set, in which case it prints a WARNING instead and returns 0, deliberately
# falling through to plain PATH resolution (this is an explicit opt-in escape
# hatch, not a default -- a host that sets it is asserting it has already
# checked whatever "ngspice" resolves to on PATH is not #259's defective
# ngspice-47 fallback).
simenv_require_ngspice_pin() {
  if [ -x "${SIMENV_NGSPICE_PIN}" ]; then
    local pin_dir
    pin_dir="$(cd "$(dirname "${SIMENV_NGSPICE_PIN}")" && pwd)"
    # Unconditionally prepend, even if pin_dir already appears somewhere
    # else in PATH -- a later duplicate entry is harmless, but merely being
    # PRESENT in PATH is not enough to guarantee the pinned binary is the
    # one that resolves: another directory earlier in PATH (e.g. Homebrew's
    # own bin dir) could still contain an `ngspice` of its own and win.
    # Being FIRST is what actually stops #259's silent fallback.
    case ":${PATH}:" in
      ":${pin_dir}:"*) ;; # already first; avoid a redundant duplicate entry
      *) PATH="${pin_dir}:${PATH}" ;;
    esac
    export PATH
    return 0
  fi

  if [ -n "${SIM_ALLOW_UNPINNED_NGSPICE:-}" ]; then
    echo "WARN: pinned ngspice not found at ${SIMENV_NGSPICE_PIN}; SIM_ALLOW_UNPINNED_NGSPICE=1 is set, so falling through to whatever 'ngspice' resolves to on PATH ($(command -v ngspice 2>/dev/null || echo '<not found>'), $(simenv_ngspice_version 2>/dev/null || echo 'unknown')). This is UNVERIFIED against #259's ngspice-47 parse/hang defect -- see sim/harness/README.md's 'ngspice-46 required for nested nonlinear moscap decks'." >&2
    return 0
  fi

  cat >&2 <<EOF
ERROR: pinned ngspice not found at ${SIMENV_NGSPICE_PIN} (issue #259).

Every citable sim/ evidence record cites ngspice-46 at this path, and
#241/#242 tuned this shim's OpenMP-thread-pin detection against that build.
Silently falling through to whatever "ngspice" resolves to on PATH is not
safe here: Homebrew's current ngspice-47 bottle has a reproducible parse
failure ("unknown parameter (e9)") on this PDK's nested nonlinear loop-
filter/VCO moscaps (see sim/harness/README.md's "ngspice-46 required for
nested nonlinear moscap decks", #153) and, worse, does not exit on that
error -- it hangs indefinitely, which stalls an entire xargs-driven run.sh
job pool since the affected corner's job slot never frees (#259).

  Fix:      install ngspice-46 at ${SIMENV_NGSPICE_PIN}
            (sim/harness/README.md's "ngspice-46 required..." section has
            the from-source build recipe).
  Relocate: export SIM_NGSPICE_BIN=/path/to/ngspice-46/bin/ngspice
  Override: export SIM_ALLOW_UNPINNED_NGSPICE=1
            (not recommended -- asserts you have already checked whatever
            "ngspice" resolves to on PATH is not #259's defective fallback)
EOF
  return 1
}

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

simenv_require_tools() {
  local missing=0
  simenv_require_ngspice_pin || missing=1
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

  # Relativize the deck path for the header comment only (#247) -- the
  # `.include` below keeps the absolute form, which ngspice needs since it
  # runs with rundir as cwd. Falls back to the absolute path unchanged if
  # deck is not under the repo root (e.g. an out-of-tree deck during
  # ad-hoc debugging).
  local deck_rel="${deck}"
  case "${deck}" in
    "${SIMENV_REPO_ROOT}"/*) deck_rel="${deck#"${SIMENV_REPO_ROOT}"/}" ;;
  esac

  local gen="${rundir}/deck.sp"
  {
    echo "* GENERATED by simenv.sh -- do not edit; edit ${deck_rel} instead"
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

# Retry wrapper around simenv_run_deck (#146). The shared build host used for
# sim/mc-cp-mismatch and sim/vco-tuning-range was observed, during
# mc-cp-mismatch's #146 build, to externally SIGKILL individual `ngspice -b`
# invocations sporadically -- confirmed NOT the OOM killer (checked
# `dmesg`/`/var/log/kern.log`: no OOM entries; `free -h` had >10 GiB available
# at the time) and NOT this cgroup's own memory or CPU quota (`memory.max`
# unlimited, `memory.events` `oom 0`/`oom_kill 0`; `cpu.max` throttles but does
# not kill) -- root cause not identified from inside this sandbox, but
# reproducibly transient: the SAME invocation that got killed once succeeded
# outright on a bare retry with no other change. A multi-hour, many-invocation
# campaign hitting even a low per-invocation kill probability is likely to
# lose at least one sample to this outright without a retry, and
# `set -euo pipefail` means ONE lost sample would abort the entire corner
# grid, not just that sample -- so every simenv_run_deck call in a campaign
# exposed to this host flakiness should go through this wrapper rather than
# calling simenv_run_deck directly. 3 attempts, short fixed backoff; a sample
# that still fails after 3 tries is a real error (bad deck, missing model,
# etc.), not host flakiness, and is still reported and still aborts the run
# via `return 1`, unchanged from before.
#
# (Hoisted from byte-identical local copies in sim/mc-cp-mismatch and
# sim/vco-tuning-range's testbench/run.sh -- #184.)
simenv_run_deck_retried() {
  local attempt rc=0
  for attempt in 1 2 3; do
    # Capture the real exit status via a separate assignment rather than
    # reading $? after the `if` completes: per POSIX, when an `if cmd; then
    # ...; fi` condition is false and the then-branch never runs, $? reflects
    # the `if` compound's own status (0), not cmd's. See #187.
    simenv_run_deck "$@" && return 0
    rc=$?
    if [ "${attempt}" -lt 3 ]; then
      echo "WARN: simenv_run_deck failed (attempt ${attempt}/3, rc=${rc}) for: $* -- retrying" >&2
      sleep 2
    fi
  done
  return "${rc}"
}

# Cache-aware wrapper around simenv_run_deck (#192). Distinct from
# simenv_run_deck_retried above: that one retries a transient host-level
# ngspice SIGKILL; this one skips a re-run entirely when a prior run's deck
# and full argument signature are unchanged on disk. Sweeps here are hours
# long on a shared machine, so a resumable runner is worth having.
#
# simenv_run_deck_soft <deck> <workdir> <tag> [args...]
#
# Reuse a completed run only if BOTH the deck it was produced from is
# unchanged (mtime) and the exact argument list -- corner, temperature, every
# injected .param -- is identical (signature file). Caching on the deck alone
# would silently reuse a run taken at different parameters, which is
# precisely the kind of quiet wrong number sim/README.md exists to prevent.
# SIM_FORCE=1 forces a cold run regardless.
#
# Success is "did the transient finish" (a `Total analysis time` line in the
# ngspice log), not "was the log clean" -- callers use this instead of
# simenv_run_deck/simenv_run_deck_retried specifically where a FAILED `.meas`
# is itself the expected, recorded result of a corner rather than an error.
#
# (Hoisted from byte-identical local copies in sim/divider-ratio and
# sim/lock-detector's testbench/run.sh -- #192.)
simenv_run_deck_soft() {
  local deck="$1" workdir="$2" tag="$3"
  local rundir="${workdir}/${tag}" log="${workdir}/${tag}/ngspice.log"
  local sig="$*"
  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${deck}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    return 0
  fi
  simenv_run_deck "$@" >/dev/null 2>&1 || true
  if grep -q "Total analysis time" "${log}" 2>/dev/null; then
    printf '%s' "${sig}" >"${rundir}/.sig"
    return 0
  fi
  echo "ERROR: ngspice did not complete a transient for tag=${tag} (see ${log})" >&2
  return 1
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
#
# NOTE (#241): this answers "how many cores does this host have," which is
# the right question for a campaign's EXTERNAL `xargs -P` process-level
# parallelism only if each `ngspice` PROCESS itself uses exactly one core.
# At least one `ngspice` build in this fleet links its own OpenMP runtime and
# spawns up to `nproc` internal threads per process regardless of this
# function's answer -- a campaign that fans out `simenv_jobs()` external
# processes of such a build squares its true thread count instead of adding
# it (`SIM_JOBS` processes x up to `nproc` internal threads each, on `nproc`
# cores). This function's return value is deliberately left unchanged by
# that finding -- see `simenv_recommend_omp_threads`/`simenv_apply_omp_pin`
# below for the (opt-in, per-campaign) fix, and why the fix is NOT to make
# this function threading-aware itself.
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

# --------------------------------------------------------------------------
# ngspice internal-threading detection (#241)
# --------------------------------------------------------------------------
#
# #146 (sim/mc-cp-mismatch, sim/vco-tuning-range/run_mismatch.sh) found and
# fixed this exact self-oversubscription on the shared build host: `ngspice`
# there links an OpenMP runtime and spawns several OS threads PER PROCESS for
# BSIM model evaluation, independent of and on top of `simenv_jobs()`'s own
# external process-level fan-out. Both campaigns fixed it locally with
# `export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"` in their own `run.sh`,
# deliberately NOT in this file -- their own comments say why: doing it here
# would silently change every OTHER campaign's behavior too, including on a
# host/`ngspice` build where BSIM evaluation is NOT internally threaded, where
# forcing `OMP_NUM_THREADS=1` would serialize model evaluation for zero
# benefit (and, on a genuinely multi-core-per-process workload, could hurt).
#
# #241 centralizes the DETECTION (so it is not re-derived or copy-pasted per
# campaign, which is how sim/supply-sensitivity went unfixed despite being
# the campaign that originally surfaced the failure mode in #58) while
# keeping the OPT-IN, per-campaign DEFAULT #146 chose: `simenv_jobs()` above
# is completely unchanged, and nothing in this file exports `OMP_NUM_THREADS`
# on its own -- a campaign must call `simenv_apply_omp_pin` (typically right
# after `simenv_require_tools`) to opt in.
#
# Detection strategy: an OpenMP-linked `ngspice` binary is a STATIC property
# of the installed build, so it can be answered by inspecting the binary's
# shared-library dependencies (`ldd`) rather than by spawning a throwaway
# ngspice job and inspecting its thread count -- cheaper, and does not cost a
# real simulation just to answer a yes/no question. This is a heuristic, not
# a guarantee: a build could spawn internal threads via a mechanism other
# than a detectable OpenMP/pthread runtime, or (on a platform without `ldd`,
# e.g. macOS) the check cannot run at all. Both failure directions are safe
# by construction -- see `simenv_ngspice_openmp_linked`'s and
# `simenv_recommend_omp_threads`'s return-nothing-on-uncertain behavior below
# -- an inconclusive probe leaves `OMP_NUM_THREADS` untouched rather than
# guessing.
#
# #244 found that `OMP_NUM_THREADS` alone is NOT a reliable pin on this same
# ngspice-46 build: for `sim/supply-sensitivity`'s closed-loop lock deck
# (a much larger BSIM3/4 device count than #146's charge-pump-only deck),
# `OMP_NUM_THREADS=1` -- confirmed present in the running process's own
# `/proc/<pid>/environ` -- left `/proc/<pid>/status`'s `Threads:` line at 8
# for the whole run (matching #242's own idle-host record). Live probing
# (`/proc/<pid>/status`, sampled every 0.2s across the process's life, on
# `ngspice -b` invoked directly against the generated deck) found the
# OpenMP-standard `OMP_THREAD_LIMIT` environment variable DOES cap this
# deck's thread count to 1, where `OMP_NUM_THREADS` alone does not. This is
# consistent with the OpenMP spec's own distinction between the two
# variables: `OMP_NUM_THREADS` only seeds the `nthreads-var` internal control
# variable, which a program's OWN in-process `omp_set_num_threads()` call can
# reassign afterward for a specific parallel region (plausibly what this
# ngspice build's larger-circuit code path does, independent of environment);
# `OMP_THREAD_LIMIT` seeds `thread-limit-var`, a hard ceiling on live thread
# count for the whole process that no in-program call can exceed. Both decks
# (`sim/mc-cp-mismatch`'s #146 precedent and `sim/supply-sensitivity`'s
# closed-loop deck) were re-probed with `OMP_THREAD_LIMIT` added and neither
# regressed -- `simenv_apply_omp_pin` below now exports both, independently
# defaulted, so a deck class where `OMP_NUM_THREADS` alone was already
# sufficient (#146) is unaffected and a deck class where it was not (#244) is
# now actually pinned.

# simenv_ngspice_openmp_linked -- exit 0 if the `ngspice` binary on PATH
# appears to link an OpenMP (or raw pthread-based) runtime, exit 1 if it does
# not, `ngspice` is not on PATH, or the check cannot be performed (no `ldd`,
# e.g. macOS -- a future `otool -L` branch is out of scope for #241, which
# found this on a Linux host).
#
# SIMENV_NGSPICE_LDD_OUTPUT overrides the live `ldd` invocation with a literal
# string for testing (see sim/lib/test_simenv_omp_pin.sh) -- this is what makes
# the detection logic unit-testable without an actual OpenMP-linked ngspice
# binary present on the test host.
simenv_ngspice_openmp_linked() {
  local ldd_output
  if [ -n "${SIMENV_NGSPICE_LDD_OUTPUT+x}" ]; then
    ldd_output="${SIMENV_NGSPICE_LDD_OUTPUT}"
  else
    local ngspice_path
    ngspice_path="$(command -v ngspice 2>/dev/null)" || return 1
    command -v ldd >/dev/null 2>&1 || return 1
    ldd_output="$(ldd "${ngspice_path}" 2>/dev/null)" || return 1
  fi
  printf '%s\n' "${ldd_output}" | grep -qE 'libgomp|libiomp|libomp\.'
}

# simenv_recommend_omp_threads -> prints "1" if simenv_ngspice_openmp_linked
# detects an internally-threaded ngspice build, prints nothing (empty stdout,
# exit 0) otherwise -- "nothing" means "no recommendation," not "recommend
# unlimited," so a caller must treat empty output as leave-alone, never as a
# literal thread count.
simenv_recommend_omp_threads() {
  simenv_ngspice_openmp_linked && echo 1
  return 0
}

# simenv_apply_omp_pin -- the opt-in call a campaign's run.sh makes (typically
# right after simenv_require_tools) to avoid squaring `simenv_jobs()` process
# count against ngspice's own internal thread count (#241), and -- per #244's
# finding above -- to actually make that pin stick on deck classes where
# `OMP_NUM_THREADS` alone is silently ineffective.
#
#   - Exports BOTH `OMP_NUM_THREADS` and `OMP_THREAD_LIMIT` to
#     simenv_recommend_omp_threads()'s recommendation (the two variables get
#     the SAME value -- there is currently no evidence any deck in this repo
#     needs them to differ). Each is defaulted INDEPENDENTLY: an explicit,
#     caller-set value for either one (env or a prior line in the same
#     script) is ALWAYS respected and left untouched, exactly preserving the
#     `${OMP_NUM_THREADS:-1}` semantics #146's two campaigns already used for
#     that variable specifically. A caller that explicitly sets ONLY
#     `OMP_NUM_THREADS` (e.g. an old copy of #146's pattern) still gets
#     `OMP_THREAD_LIMIT` filled in -- #244 found the ceiling is what makes
#     the pin effective on the deck class `OMP_NUM_THREADS` alone does not
#     cover, so silently skipping it just because the OTHER variable was
#     already set would reintroduce #244's exact failure mode for that
#     caller.
#   - If neither is already set, both are set to
#     simenv_recommend_omp_threads()'s recommendation, but ONLY if that
#     recommendation is non-empty. On a host/build where detection does not
#     fire (not internally threaded, or the probe itself is inconclusive),
#     this function exports nothing -- both variables are left exactly as the
#     ambient environment set them (typically unset), so ngspice's own
#     default threading behavior is unchanged. This is the "does not
#     silently change behavior when internal threading is absent" guarantee
#     #241 asks for.
simenv_apply_omp_pin() {
  local rec=""
  if [ -z "${OMP_NUM_THREADS:-}" ] || [ -z "${OMP_THREAD_LIMIT:-}" ]; then
    rec="$(simenv_recommend_omp_threads)"
  fi
  if [ -z "${OMP_NUM_THREADS:-}" ] && [ -n "${rec}" ]; then
    export OMP_NUM_THREADS="${rec}"
  fi
  if [ -z "${OMP_THREAD_LIMIT:-}" ] && [ -n "${rec}" ]; then
    export OMP_THREAD_LIMIT="${rec}"
  fi
  return 0
}
