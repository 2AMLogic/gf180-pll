#!/usr/bin/env bash
# Regression test for the ngspice-internal-threading detection helpers in
# simenv.sh -- simenv_ngspice_openmp_linked, simenv_recommend_omp_threads,
# simenv_apply_omp_pin (issue #241; extended by #244 to also cover
# OMP_THREAD_LIMIT, the variable that turned out to be the effective pin for
# sim/supply-sensitivity's closed-loop deck where OMP_NUM_THREADS alone was
# not).
#
# This is host/binary-dependent behavior in production use (it inspects the
# REAL `ngspice` binary's shared-library dependencies), which is exactly why
# #241's own Test Plan calls the end-to-end effect "not practically unit
# testable." What IS unit-testable in isolation, with no real ngspice binary
# required, is the detection LOGIC itself: SIMENV_NGSPICE_LDD_OUTPUT lets a
# test supply the "ldd" output directly, so these cases run identically on
# any host regardless of what ngspice build (if any) is actually installed.
#
# There is no existing bash-level unit-test harness for sim/lib/simenv.sh
# (see sim/lib/test_simenv_run_deck_retried.sh's header, the established
# precedent this file follows) -- run directly:
#
#   sim/lib/test_simenv_omp_pin.sh
#
# Shared run_case/assert_rc/fail_count/test_summary scaffolding lives in
# test_helpers.sh (issue #249); only assert_eq (used solely by this file) is
# defined locally.
#
# shellcheck disable=SC2016 # run_case's single-quoted bodies intentionally
# defer $-expansion to the `bash -c` subshell they're spliced into.

set -uo pipefail

SIM_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMENV_SH="${SIM_LIB_DIR}/simenv.sh"

# shellcheck source=sim/lib/test_helpers.sh
. "${SIM_LIB_DIR}/test_helpers.sh"

# assert_eq <expected> <actual> <case_name>
assert_eq() {
  local expected="$1" actual="$2" name="$3"
  if [ "${expected}" != "${actual}" ]; then
    echo "FAIL: ${name}: expected '${expected}', got '${actual}'"
    fail_count=$((fail_count + 1))
  else
    echo "PASS: ${name}: '${actual}'"
  fi
}

echo "== simenv_ngspice_openmp_linked =="

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="linux-vdso.so.1 (0x00007fff)
libgomp.so.1 => /usr/lib/x86_64-linux-gnu/libgomp.so.1 (0x00007f1)
libc.so.6 => /usr/lib/x86_64-linux-gnu/libc.so.6 (0x00007f2)"
  simenv_ngspice_openmp_linked
  exit "$?"
'
assert_rc 0 "${CASE_RC}" "libgomp-linked ldd output detected as OpenMP-linked"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="linux-vdso.so.1 (0x00007fff)
libiomp5.so => /usr/lib/libiomp5.so (0x00007f1)"
  simenv_ngspice_openmp_linked
  exit "$?"
'
assert_rc 0 "${CASE_RC}" "libiomp5-linked ldd output detected as OpenMP-linked"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="linux-vdso.so.1 (0x00007fff)
libc.so.6 => /usr/lib/x86_64-linux-gnu/libc.so.6 (0x00007f2)
libreadline.so.8 => /usr/lib/x86_64-linux-gnu/libreadline.so.8 (0x00007f3)"
  simenv_ngspice_openmp_linked
  exit "$?"
'
assert_rc 1 "${CASE_RC}" "no OpenMP runtime in ldd output -> not detected"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT=""
  simenv_ngspice_openmp_linked
  exit "$?"
'
assert_rc 1 "${CASE_RC}" "empty ldd output -> not detected (inconclusive is safe)"

echo
echo "== simenv_recommend_omp_threads =="

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  simenv_recommend_omp_threads
'
assert_rc 0 "${CASE_RC}" "recommend: OpenMP-linked case exits 0"
assert_eq "1" "${CASE_STDOUT}" "recommend: OpenMP-linked build recommends 1 thread"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libc.so.6 => /usr/lib/libc.so.6"
  simenv_recommend_omp_threads
'
assert_rc 0 "${CASE_RC}" "recommend: non-OpenMP case still exits 0 (not an error)"
assert_eq "" "${CASE_STDOUT}" "recommend: non-OpenMP build makes no recommendation"

echo
echo "== simenv_apply_omp_pin =="

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  simenv_apply_omp_pin
  printf "%s" "${OMP_NUM_THREADS:-<unset>}"
'
assert_eq "1" "${CASE_STDOUT}" "apply: OpenMP-linked build exports OMP_NUM_THREADS=1"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  simenv_apply_omp_pin
  printf "%s" "${OMP_THREAD_LIMIT:-<unset>}"
'
assert_eq "1" "${CASE_STDOUT}" "apply: OpenMP-linked build also exports OMP_THREAD_LIMIT=1 (#244 -- the variable that actually caps sim/supply-sensitivity's closed-loop deck)"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libc.so.6 => /usr/lib/libc.so.6"
  simenv_apply_omp_pin
  printf "%s,%s" "${OMP_NUM_THREADS:-<unset>}" "${OMP_THREAD_LIMIT:-<unset>}"
'
assert_eq "<unset>,<unset>" "${CASE_STDOUT}" "apply: non-OpenMP build leaves both OMP_NUM_THREADS and OMP_THREAD_LIMIT unset (no regression)"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  OMP_NUM_THREADS=4
  simenv_apply_omp_pin
  printf "%s" "${OMP_NUM_THREADS}"
'
assert_eq "4" "${CASE_STDOUT}" "apply: an explicit caller-set OMP_NUM_THREADS is always respected, never overridden"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  OMP_NUM_THREADS=4
  simenv_apply_omp_pin
  printf "%s" "${OMP_THREAD_LIMIT:-<unset>}"
'
assert_eq "1" "${CASE_STDOUT}" "apply: an explicit caller-set OMP_NUM_THREADS does NOT suppress the OMP_THREAD_LIMIT default (#244 -- the two variables are defaulted independently)"

run_case '
  SIMENV_NGSPICE_LDD_OUTPUT="libgomp.so.1 => /usr/lib/libgomp.so.1"
  OMP_THREAD_LIMIT=4
  simenv_apply_omp_pin
  printf "%s,%s" "${OMP_NUM_THREADS:-<unset>}" "${OMP_THREAD_LIMIT}"
'
assert_eq "1,4" "${CASE_STDOUT}" "apply: an explicit caller-set OMP_THREAD_LIMIT is always respected, never overridden, and does not suppress the OMP_NUM_THREADS default"

test_summary "simenv ngspice-thread-pin"
exit "$?"
