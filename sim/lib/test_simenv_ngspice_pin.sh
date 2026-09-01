#!/usr/bin/env bash
# Regression test for simenv_require_ngspice_pin, the ngspice-46-pin
# preflight added by issue #259.
#
# #259: on a host where the pinned ngspice-46 binary this repo's evidence
# records cite (conventionally $HOME/.local/bin/ngspice, per #241/#242) is
# absent, PATH previously fell through SILENTLY to whatever "ngspice"
# resolved to next -- observed on at least one host to be Homebrew's
# ngspice-47, which has a reproducible parse failure on this PDK's nested
# nonlinear loop-filter/VCO moscaps (#153) and, worse, hangs instead of
# exiting on that failure. This suite drives simenv_require_ngspice_pin
# against fake `ngspice` stubs under a scratch $TMPDIR -- no real ngspice
# binary or PDK required -- covering:
#   1. pinned binary present -> its directory wins PATH, even when another
#      directory containing its own "ngspice" sits earlier in the caller's
#      PATH already.
#   2. pinned binary absent -> loud ERROR, non-zero return (simenv.sh's own
#      `set -euo pipefail` then aborts the sourcing shell, matching
#      simenv_require_tools's `exit 1` in real use).
#   3. pinned binary absent + SIM_ALLOW_UNPINNED_NGSPICE=1 -> loud WARNING,
#      zero return, falls through to PATH as before.
#
# There is no existing bash-level unit-test harness for sim/lib/simenv.sh
# (see sim/lib/test_simenv_run_deck_retried.sh's header, the established
# precedent this file follows) -- run directly:
#
#   sim/lib/test_simenv_ngspice_pin.sh
#
# Shared run_case/assert_rc/fail_count/test_summary scaffolding lives in
# test_helpers.sh (issue #249).
#
# shellcheck disable=SC2016 # run_case's single-quoted bodies intentionally
# defer $-expansion to the `bash -c` subshell they're spliced into.

set -uo pipefail

SIM_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMENV_SH="${SIM_LIB_DIR}/simenv.sh"

# shellcheck source=sim/lib/test_helpers.sh
. "${SIM_LIB_DIR}/test_helpers.sh"

# assert_contains <haystack> <needle> <case_name>
assert_contains() {
  local haystack="$1" needle="$2" name="$3"
  case "${haystack}" in
    *"${needle}"*)
      echo "PASS: ${name}"
      ;;
    *)
      echo "FAIL: ${name}: expected to find '${needle}'"
      fail_count=$((fail_count + 1))
      ;;
  esac
}

# --------------------------------------------------------------------------
# Fixture: two fake, self-identifying "ngspice" stubs in a scratch $TMPDIR --
# a "pinned" one and an "other" one standing in for an unpinned PATH fallback
# (e.g. Homebrew's ngspice-47 in #259's report).
# --------------------------------------------------------------------------
FIXTURE_DIR="$(mktemp -d)"
trap 'rm -rf "${FIXTURE_DIR}"' EXIT

mkdir -p "${FIXTURE_DIR}/pin_dir" "${FIXTURE_DIR}/other_dir"

cat >"${FIXTURE_DIR}/pin_dir/ngspice" <<'STUB'
#!/bin/sh
echo "** ngspice-46 : fake pinned stub (test_simenv_ngspice_pin.sh)"
STUB
chmod +x "${FIXTURE_DIR}/pin_dir/ngspice"

cat >"${FIXTURE_DIR}/other_dir/ngspice" <<'STUB'
#!/bin/sh
echo "** ngspice-47 : fake unpinned PATH-fallback stub (test_simenv_ngspice_pin.sh)"
STUB
chmod +x "${FIXTURE_DIR}/other_dir/ngspice"

PIN_NGSPICE="${FIXTURE_DIR}/pin_dir/ngspice"
OTHER_NGSPICE="${FIXTURE_DIR}/other_dir/ngspice"
MISSING_NGSPICE="${FIXTURE_DIR}/pin_dir/does-not-exist"

# Each run_case below sets SIMENV_NGSPICE_PIN directly (the variable
# simenv_require_ngspice_pin() actually reads), rather than the real
# caller-facing SIM_NGSPICE_BIN override -- run_case's `source
# "${SIMENV_SH}"` runs BEFORE the case body, so SIMENV_NGSPICE_PIN has
# already been computed from SIM_NGSPICE_BIN (or its $HOME/.local/bin/ngspice
# default) by the time the body would set it; only the already-sourced
# variable can still be overridden per case.

echo "== simenv_require_ngspice_pin: pin present =="

run_case "
  export PATH=\"${FIXTURE_DIR}/other_dir:\${PATH}\"
  SIMENV_NGSPICE_PIN='${PIN_NGSPICE}'
  simenv_require_ngspice_pin
  echo rc=\"\$?\"
  echo resolved=\"\$(command -v ngspice)\"
"
assert_rc 0 "${CASE_RC}" "pin present: returns 0"
assert_contains "${CASE_STDOUT}" "resolved=${PIN_NGSPICE}" "pin present, another ngspice earlier in PATH: pinned binary still wins PATH resolution (#259 -- presence isn't enough, it must be FIRST)"

run_case "
  export PATH=\"${FIXTURE_DIR}/other_dir:\${PATH}\"
  SIMENV_NGSPICE_PIN='${PIN_NGSPICE}'
  simenv_require_ngspice_pin >/dev/null 2>&1
  ngspice -v
"
assert_contains "${CASE_STDOUT}" "ngspice-46" "pin present: subsequent bare 'ngspice' invocations (as simenv_run_deck makes) actually run the pinned build"

echo
echo "== simenv_require_ngspice_pin: pin absent =="

run_case "
  export PATH=\"${FIXTURE_DIR}/other_dir:\${PATH}\"
  SIMENV_NGSPICE_PIN='${MISSING_NGSPICE}'
  simenv_require_ngspice_pin
"
assert_rc 1 "${CASE_RC}" "pin absent: returns non-zero (simenv_require_tools' caller then exits 1, rather than falling through silently)"
assert_contains "${CASE_STDERR}" "ERROR: pinned ngspice not found" "pin absent: loud ERROR on stderr, not a silent fallback"
assert_contains "${CASE_STDERR}" "#259" "pin absent: error names issue #259"
assert_contains "${CASE_STDERR}" "SIM_ALLOW_UNPINNED_NGSPICE" "pin absent: error documents the explicit opt-out"

echo
echo "== simenv_require_ngspice_pin: pin absent, SIM_ALLOW_UNPINNED_NGSPICE=1 =="

run_case "
  export PATH=\"${FIXTURE_DIR}/other_dir:\${PATH}\"
  SIMENV_NGSPICE_PIN='${MISSING_NGSPICE}'
  SIM_ALLOW_UNPINNED_NGSPICE=1
  simenv_require_ngspice_pin
  echo rc=\"\$?\"
  echo resolved=\"\$(command -v ngspice)\"
"
assert_rc 0 "${CASE_RC}" "pin absent + opt-out set: returns 0 (deliberate fallback, not an error)"
assert_contains "${CASE_STDERR}" "WARN: pinned ngspice not found" "pin absent + opt-out set: still a loud WARNING, not silent"
assert_contains "${CASE_STDOUT}" "resolved=${OTHER_NGSPICE}" "pin absent + opt-out set: falls through to whatever 'ngspice' resolves to on PATH, as before #259's fix"

test_summary "simenv ngspice pin (#259)"
exit "$?"
