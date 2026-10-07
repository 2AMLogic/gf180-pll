#!/usr/bin/env bash
#
# Fails if a file ADDED OR MODIFIED relative to the merge base, under the
# layout evidence tree or a per-campaign sim evidence directory, embeds a
# host-absolute path: `/home/`, `/Users/`, or an agent-worktree directory
# (`.loom/worktrees`).
#
# WHY THIS EXISTS (issue #701)
#
# #247 stopped the sim deck header from recording the generating host's
# directories and #28 did the same for design/netlist.sh, but nothing guarded
# the result: layout DRC/LVS bundles kept shipping the KLayout run-directory
# banner, the DeprecationWarning source paths and the report database's
# `<generator>` script path verbatim. The repository is being prepared for
# public release; evidence that names a contributor's home directory looks
# machine-specific and leaks the agent worktree layout.
#
# layout/harness/{drc,lvs}.py now normalise those strings at capture time
# (run dir -> <RUN_DIR>, repo -> <REPO>, PDK -> <PDK>, home -> <HOME>). This
# check is the ratchet that keeps the next regression from landing.
#
# GRANDFATHERING
#
# `sim/` and the layout evidence tree are append-only evidence, so existing
# files are never rewritten. Only files that differ from the merge base with
# the base ref are graded; every historical file is left alone by
# construction, not by a baseline list.
#
# ALLOWLIST
#
# sim/lib/simenv.sh documents the pinned-binary convention: the supply-
# sensitivity campaign records cite `<home>/.local/bin/ngspice` as the
# provenance of the ngspice-46 build. That exact citation form
# (`/home/<user>/.local/bin/ngspice`, likewise `/Users/<user>/...`) is
# accepted; any OTHER host path in the same file still fails.
#
# GRADED PATHS
#
#   layout/evidence/**
#   sim/<campaign>/records/**  sim/<campaign>/corners/**
#   sim/<campaign>/netlist-snapshots/**
#
# Usage: layout/lib/check-evidence-host-paths.sh [--base REF] [--files PATH ...]
#   --base REF     base ref to take the merge base with (default: origin/main,
#                  falling back to main). When HEAD already IS the merge base
#                  (a push to the default branch), the diff is HEAD^..HEAD.
#   --files PATH   grade exactly these repo-relative files instead of a diff
#                  (paths outside the graded trees are ignored).
# Exit codes: 0 no graded changed file embeds a host path,
#             1 at least one does, or the diff could not be computed (a
#               check that did not run is not a check that passed).

set -uo pipefail
export LC_ALL=C

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}" || exit 1

base=""
files=()
explicit=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) base="${2:-}"; shift 2 ;;
    --files) explicit=1; shift; while [ $# -gt 0 ] && [[ "$1" != --* ]]; do files+=("$1"); shift; done ;;
    *) echo "FAIL: unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ "${explicit}" -eq 0 ]; then
  if [ -z "${base}" ]; then
    if git rev-parse --verify -q origin/main >/dev/null; then base=origin/main; else base=main; fi
  fi
  if ! mb="$(git merge-base HEAD "${base}" 2>/dev/null)"; then
    echo "FAIL: cannot compute a merge base between HEAD and '${base}'" \
      "(shallow checkout? use fetch-depth: 0)" >&2
    exit 1
  fi
  head_sha="$(git rev-parse HEAD)"
  if [ "${mb}" = "${head_sha}" ]; then
    mb="$(git rev-parse -q --verify HEAD^ 2>/dev/null || true)"
  fi
  if [ -n "${mb}" ]; then
    mapfile -t files < <(git diff --name-only --diff-filter=AM "${mb}" HEAD)
  fi
fi

is_graded() {
  case "$1" in
    layout/evidence/*) return 0 ;;
    sim/*/records/* | sim/*/corners/* | sim/*/netlist-snapshots/*) return 0 ;;
  esac
  return 1
}

# Host-absolute path shapes. The pinned-binary citation is stripped first.
ALLOW_RE='/(home|Users)/[A-Za-z0-9_.-]+/\.local/bin/ngspice'
HOST_RE='/home/|/Users/|\.loom/worktrees'

status=0
checked=0
for f in "${files[@]}"; do
  [ -n "${f}" ] || continue
  is_graded "${f}" || continue
  [ -f "${f}" ] || continue
  checked=$((checked + 1))
  hits="$(sed -E "s#${ALLOW_RE}##g" "${f}" | grep -anE "${HOST_RE}" | head -3)"
  if [ -n "${hits}" ]; then
    status=1
    echo "FAIL: ${f} embeds a host-absolute path:" >&2
    while IFS= read -r line; do echo "    ${line:0:200}" >&2; done <<< "${hits}"
  fi
done

if [ "${status}" -ne 0 ]; then
  echo "Evidence is append-only; normalise the path at capture time" \
    "(layout/harness/env.py normalise_run_dir) and re-capture instead of" \
    "committing the raw output. Issue #701." >&2
  exit 1
fi
echo "OK: ${checked} changed evidence file(s) checked; none embed a host-absolute path"
exit 0
