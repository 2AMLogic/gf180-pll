#!/usr/bin/env bash
# Regression test for simenv_run_deck_retried() in simenv.sh (issue #187).
#
# There is no existing bash-level unit-test harness for sim/lib/simenv.sh
# (sim/selftest.sh only drives the separate Python sim/harness/run_corners.py
# stack), so this is a small standalone script. Run directly:
#
#   sim/lib/test_simenv_run_deck_retried.sh
#
# Each case sources simenv.sh fresh in a subshell and stubs
# simenv_run_deck() to control the pass/fail sequence, then asserts on the
# wrapper's return code and stderr WARN lines.
#
# Shared run_case/assert_rc/fail_count/test_summary scaffolding lives in
# test_helpers.sh (issue #249); only assert_contains/assert_not_contains
# (used solely by this file) are defined locally.
#
# shellcheck disable=SC2016 # run_case's single-quoted bodies intentionally
# defer $-expansion to the `bash -c` subshell they're spliced into.

set -uo pipefail

SIM_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMENV_SH="${SIM_LIB_DIR}/simenv.sh"

# shellcheck source=sim/lib/test_helpers.sh
. "${SIM_LIB_DIR}/test_helpers.sh"

# assert_contains <needle> <haystack> <case_name>
assert_contains() {
  local needle="$1" haystack="$2" name="$3"
  case "${haystack}" in
    *"${needle}"*)
      echo "PASS: ${name}: found '${needle}'"
      ;;
    *)
      echo "FAIL: ${name}: expected to find '${needle}' in stderr:"
      # shellcheck disable=SC2001 # multi-line indent, not a plain substitution
      echo "${haystack}" | sed 's/^/    /'
      fail_count=$((fail_count + 1))
      ;;
  esac
}

# assert_not_contains <needle> <haystack> <case_name>
assert_not_contains() {
  local needle="$1" haystack="$2" name="$3"
  case "${haystack}" in
    *"${needle}"*)
      echo "FAIL: ${name}: did not expect to find '${needle}' in stderr:"
      # shellcheck disable=SC2001 # multi-line indent, not a plain substitution
      echo "${haystack}" | sed 's/^/    /'
      fail_count=$((fail_count + 1))
      ;;
    *)
      echo "PASS: ${name}: '${needle}' absent as expected"
      ;;
  esac
}

echo "== case 1: all 3 attempts fail -> wrapper returns real non-zero rc =="
run_case '
  simenv_run_deck() { return 5; }
  simenv_run_deck_retried argX
  exit "$?"
'
assert_rc 5 "${CASE_RC}" "all-fail returns stubbed rc (not 0)"
assert_contains "rc=5" "${CASE_STDERR}" "all-fail WARN reports real per-attempt rc"
assert_not_contains "rc=0" "${CASE_STDERR}" "all-fail WARN never falls back to rc=0"

echo
echo "== case 2: first attempt succeeds -> immediate return 0, no WARN lines =="
run_case '
  simenv_run_deck() { return 0; }
  simenv_run_deck_retried argX
  exit "$?"
'
assert_rc 0 "${CASE_RC}" "first-attempt-succeeds returns 0"
assert_not_contains "WARN" "${CASE_STDERR}" "first-attempt-succeeds emits no WARN lines"

echo
echo "== case 3: fails attempt 1, succeeds attempt 2 -> return 0, one WARN line =="
run_case '
  n=0
  simenv_run_deck() {
    n=$((n + 1))
    if [ "${n}" -eq 1 ]; then return 3; else return 0; fi
  }
  simenv_run_deck_retried argX
  exit "$?"
'
assert_rc 0 "${CASE_RC}" "fails-then-succeeds returns 0"
assert_contains "rc=3" "${CASE_STDERR}" "fails-then-succeeds WARN reports attempt-1's real rc"

test_summary "simenv_run_deck_retried"
exit "$?"
