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

# Message shapes (issue #996): the reroute line (`python3 sim/run_corners.py
# <exp>`) is printed only when <exp> is a bare slug that resolves to a real
# experiment manifest (sim/<exp>/testbench/tb.json, resolved from the lib's
# own directory, never the caller's cwd). A nonexistent slug, a
# "<slug> (negative control)" label passed by the control entry points, or a
# pathy string omits the line instead of printing a command that cannot run,
# and still names both alternatives.
want_slug=vco-tuning-range
if [ ! -f "${SIM_LIB_DIR}/../${want_slug}/testbench/tb.json" ]; then
  echo "FAIL message fixture: '${want_slug}' does not resolve"; fails=$((fails + 1))
fi
msg="$(env KLT_SIM_BACKEND=batch bash -c '. "$0"; simenv_guard_local_grid 5 "$1"' "${SIMENV_SH}" "${want_slug}" 2>&1)"
case "${msg}" in
  *"python3 sim/run_corners.py ${want_slug}"*"SIM_ALLOW_LOCAL_GRID=1"*)
    echo "ok   message: resolving slug prints reroute" ;;
  *) echo "FAIL message: resolving slug '${want_slug}' should print reroute: ${msg}"; fails=$((fails + 1)) ;;
esac

for bad in "mc-cp-mismatch" "mc-cp-mismatch (negative control)" "a/b" ""; do
  msg="$(env KLT_SIM_BACKEND=batch bash -c '. "$0"; simenv_guard_local_grid 5 "$1"' "${SIMENV_SH}" "${bad}" 2>&1)"
  if grep -q "python3 sim/run_corners.py" <<<"${msg}"; then
    echo "FAIL message: unresolvable '${bad:-<default>}' printed a reroute command: ${msg}"
    fails=$((fails + 1))
  elif grep -q "klt sim --wait-for-capacity 600" <<<"${msg}" \
    && grep -q "SIM_ALLOW_LOCAL_GRID=1" <<<"${msg}"; then
    echo "ok   message: '${bad:-<default>}' omits reroute, names both alternatives"
  else
    echo "FAIL message: '${bad}' dropped an alternative: ${msg}"; fails=$((fails + 1))
  fi
done

# Status reaches a runner's exit code via the `|| exit $?` idiom.
env KLT_SIM_BACKEND=batch bash -c '. "$0"; simenv_guard_local_grid 5 foo 2>/dev/null || exit $?; exit 0' "${SIMENV_SH}"
if [ "$?" = 2 ]; then echo "ok   exit status propagates"; else echo "FAIL exit status propagates"; fails=$((fails + 1)); fi

# Bypass class (#959): a `--control` entry point must not reach the control
# fan without consulting the guard. The coverage/ordering checks below only
# match a column-0 guard call in the runners -- they never read simenv.sh and
# never look inside a function body, so a guard the shared
# simenv_emit_control_evidence calls is invisible to them, and so is its
# absence. This check is behavioral instead: source the lib, call the helper
# with a stub campaign function under each environment, and assert whether
# the stub ran (and whether the helper was allowed to touch the tree at all).
ctl_case() {  # ctl_case <name> <want_rc> <want_stub> <want_tree> <env...> -- <units>
  local name="$1" want_rc="$2" want_stub="$3" want_tree="$4"; shift 4
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done
  shift
  local dir out rc stub tree
  dir="$(mktemp -d)"
  out="$(env -u KLT_SIM_BACKEND -u SIM_ALLOW_LOCAL_GRID "${envs[@]}" bash -c '
    . "$0"
    stub() { echo "CAMPAIGN RAN"; mkdir -p "$(dirname "$1")"; : >"$1"; }
    rc=0
    simenv_emit_control_evidence "$1/corners" "$1/work" lbl rid nl cd sw stub "$2" || rc=$?
    echo "rc=${rc}"
    if [ -e "$1/work/negative_control_rows.csv" ]; then echo "stub=1"; else echo "stub=0"; fi
  ' "${SIMENV_SH}" "${dir}" "$1" 2>&1)"
  rc="$(sed -n 's/^rc=//p' <<<"${out}" | tail -1)"
  stub="$(sed -n 's/^stub=//p' <<<"${out}" | tail -1)"
  tree="absent"; [ -e "${dir}/corners" ] && tree="present"
  rm -rf "${dir}"
  if [ "${rc}" = "${want_rc}" ] && [ "${stub}" = "${want_stub}" ] && [ "${tree}" = "${want_tree}" ]; then
    echo "ok   ${name}"
  else
    echo "FAIL ${name}: want rc=${want_rc} stub=${want_stub} tree=${want_tree}," \
      "got rc=${rc} stub=${stub} tree=${tree}"; fails=$((fails + 1))
  fi
}
ctl_case "control helper consults guard: batch refuses before any side effect" \
  2 0 absent KLT_SIM_BACKEND=batch -- 420
ctl_case "control helper consults guard: empty units fails closed under batch" \
  2 0 absent KLT_SIM_BACKEND=batch -- ""
ctl_case "control helper consults guard: SIM_ALLOW_LOCAL_GRID=1 opt-in runs" \
  0 1 present KLT_SIM_BACKEND=batch SIM_ALLOW_LOCAL_GRID=1 -- 420
ctl_case "control helper consults guard: non-batch backend runs" \
  0 1 present -- 420

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
