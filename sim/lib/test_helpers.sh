# Shared bash test-assertion scaffolding for the sim/lib/test_simenv_*.sh
# standalone regression tests (issue #249). Sourced, not executed directly.
#
# Provides:
#   fail_count       -- shared failure counter, initialized to 0 here
#   assert_rc         <expected_rc> <actual_rc> <case_name>
#   run_case          <script_body> -- runs script_body in `bash -c` against
#                      SIMENV_SH with `set +e` so a stubbed non-zero return
#                      doesn't kill the subshell before we can inspect it.
#                      Sets globals CASE_RC, CASE_STDOUT, and CASE_STDERR
#                      (a strict superset of what each caller needs
#                      individually -- some tests only look at CASE_STDOUT,
#                      others only at CASE_STDERR).
#   test_summary      <suite_name> -- prints the trailing pass/fail summary
#                      block and returns 0 if fail_count is 0, else 1. The
#                      caller is expected to `exit "$?"` (or just call this
#                      last, since bash exits with the last command's
#                      status).
#
# Callers must set SIMENV_SH before calling run_case().
#
# shellcheck shell=bash

fail_count=0

# assert_rc <expected_rc> <actual_rc> <case_name>
assert_rc() {
  local expected="$1" actual="$2" name="$3"
  if [ "${expected}" -ne "${actual}" ]; then
    echo "FAIL: ${name}: expected rc=${expected}, got rc=${actual}"
    fail_count=$((fail_count + 1))
  else
    echo "PASS: ${name}: rc=${actual}"
  fi
}

# run_case <script_body> -- runs script_body in `bash -c` with `set +e` so a
# stubbed non-zero return doesn't kill the subshell before we can inspect it.
# Sets globals CASE_RC, CASE_STDOUT, and CASE_STDERR.
run_case() {
  local body="$1"
  local out_file err_file
  out_file="$(mktemp)"
  err_file="$(mktemp)"
  bash -c "source \"${SIMENV_SH}\"; set +e; ${body}" >"${out_file}" 2>"${err_file}"
  # Consumed by callers, never inside this file -- hence the SC2034
  # suppressions (matches the convention in simenv.sh's own corner arrays).
  # shellcheck disable=SC2034
  CASE_RC=$?
  # shellcheck disable=SC2034
  CASE_STDOUT="$(cat "${out_file}")"
  # shellcheck disable=SC2034
  CASE_STDERR="$(cat "${err_file}")"
  rm -f "${out_file}" "${err_file}"
}

# test_summary <suite_name> -- prints the trailing pass/fail block based on
# fail_count and returns 0 (all passed) or 1 (at least one failure).
test_summary() {
  local suite_name="$1"
  echo
  if [ "${fail_count}" -eq 0 ]; then
    echo "All ${suite_name} regression tests passed."
    return 0
  else
    echo "${fail_count} ${suite_name} regression test(s) failed."
    return 1
  fi
}
