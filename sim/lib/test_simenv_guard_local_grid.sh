#!/usr/bin/env bash
# shellcheck disable=SC2016 # bash -c bodies intentionally defer expansion
# Regression test for simenv_guard_local_grid (issue #740): the refusal is
# keyed on grid cardinality, not worker count, and every legacy runner that
# fans out locally must call it. Headless: no ngspice, no PDK, no SPICE.
#
#   sim/lib/test_simenv_guard_local_grid.sh
set -uo pipefail

SIM_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMENV_SH="${SIM_LIB_DIR}/simenv.sh"
SIM_DIR="$(cd "${SIM_LIB_DIR}/.." && pwd)"
fails=0

# check <name> <expected_rc> <env assignments...> -- <units-arg...>
check() {
  local name="$1" want="$2"; shift 2
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  local out rc
  out="$(env -u KLT_SIM_BACKEND -u SIM_ALLOW_LOCAL_GRID -u SIM_JOBS "${envs[@]}" \
    bash -c '. "$0"; rc=0; simenv_guard_local_grid "$@" || rc=$?; echo "rc=${rc}"' "${SIMENV_SH}" "$@" 2>&1)"
  rc="$(printf '%s\n' "${out}" | sed -n 's/^rc=//p' | tail -1)"
  if [ "${rc}" != "${want}" ]; then
    echo "FAIL ${name}: want rc=${want}, got rc=${rc}"; fails=$((fails + 1))
  else
    echo "ok   ${name}"
  fi
}

check "batch, 5 units refuses"            2 KLT_SIM_BACKEND=batch -- 5 exp
check "batch, SIM_JOBS=1, 5 units refuses" 2 KLT_SIM_BACKEND=batch SIM_JOBS=1 -- 5 exp
check "batch, SIM_JOBS=8, 5 units refuses" 2 KLT_SIM_BACKEND=batch SIM_JOBS=8 -- 5 exp
check "batch, opt-in allows"              0 KLT_SIM_BACKEND=batch SIM_ALLOW_LOCAL_GRID=1 -- 5 exp
check "batch, 1 unit passes"              0 KLT_SIM_BACKEND=batch -- 1 exp
check "batch, 0 units passes"             0 KLT_SIM_BACKEND=batch -- 0 exp
check "batch, empty units refuses"        2 KLT_SIM_BACKEND=batch -- ""
check "batch, missing units refuses"      2 KLT_SIM_BACKEND=batch --
check "batch, non-numeric refuses"        2 KLT_SIM_BACKEND=batch -- abc exp
check "unset backend passes"              0 -- 5 exp
check "local backend passes"              0 KLT_SIM_BACKEND=local -- 5 exp

# Message names the supported path.
msg="$(env KLT_SIM_BACKEND=batch bash -c '. "$0"; simenv_guard_local_grid 5 foo' "${SIMENV_SH}" 2>&1)"
case "${msg}" in
  *"python3 sim/run_corners.py foo"*"SIM_ALLOW_LOCAL_GRID=1"*) echo "ok   message" ;;
  *) echo "FAIL message: ${msg}"; fails=$((fails + 1)) ;;
esac

# Status reaches a runner's exit code via the `|| exit $?` idiom.
env KLT_SIM_BACKEND=batch bash -c '. "$0"; simenv_guard_local_grid 5 foo 2>/dev/null || exit $?; exit 0' "${SIMENV_SH}"
if [ "$?" = 2 ]; then echo "ok   exit status propagates"; else echo "FAIL exit status propagates"; fails=$((fails + 1)); fi

# Coverage: every runner that fans out locally must call the guard.
unguarded=""
for f in "${SIM_DIR}"/*/testbench*/*.sh; do
  if grep -qE 'simenv_jobs|xargs -P' "${f}" && ! grep -q 'simenv_guard_local_grid' "${f}"; then
    unguarded="${unguarded} ${f#"${SIM_DIR}"/}"
  fi
done
if [ -z "${unguarded}" ]; then echo "ok   coverage"; else
  echo "FAIL coverage: runners without simenv_guard_local_grid:${unguarded}"; fails=$((fails + 1)); fi

# Ordering: under `set -u` a guard whose count variable is assigned later
# aborts the runner on every host. Each guard call must (a) read only
# variables assigned on an earlier line, and (b) precede the first fan-out.
misordered=""
for f in "${SIM_DIR}"/*/testbench*/*.sh; do
  grep -q '^simenv_guard_local_grid' "${f}" || continue
  first_guard="$(grep -n '^simenv_guard_local_grid' "${f}" | head -1 | cut -d: -f1)"
  first_fan="$(grep -nE '^[[:space:]]*xargs -P' "${f}" | head -1 | cut -d: -f1)"
  if [ -n "${first_fan}" ] && [ "${first_guard}" -gt "${first_fan}" ]; then
    misordered="${misordered} ${f#"${SIM_DIR}"/}(guard@${first_guard}>xargs@${first_fan})"
  fi
  while IFS=: read -r gl gtext; do
    for v in $(printf '%s\n' "${gtext}" | grep -oE '[A-Z][A-Z0-9_]+' | sort -u); do
      [ "${v}" = "simenv_guard_local_grid" ] && continue
      al="$(grep -nE "^[[:space:]]*(local |declare (-[a-zA-Z]+ )?)?${v}=" "${f}" | head -1 | cut -d: -f1)"
      if [ -z "${al}" ] || [ "${al}" -ge "${gl}" ]; then
        misordered="${misordered} ${f#"${SIM_DIR}"/}(${v} assigned@${al:-never}, guard@${gl})"
      fi
    done
  done < <(grep -n '^simenv_guard_local_grid' "${f}")
done
if [ -z "${misordered}" ]; then echo "ok   ordering"; else
  echo "FAIL ordering:${misordered}"; fails=$((fails + 1)); fi

if [ "${fails}" -gt 0 ]; then echo "${fails} failure(s)"; exit 1; fi
echo "all passed"
