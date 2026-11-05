#!/usr/bin/env bash
#
# Store a run's raw outputs in the fleet artifact store and write the manifest
# (issue #830). Git keeps only the manifest; the bytes never enter the repo.
#
# Fails closed: a missing $KLT_ARTIFACT_BROKER, a klt without `artifact put`,
# or an unreachable broker exits nonzero and leaves no manifest behind. There
# is no fallback to committing bytes.
#
# Usage: sim/lib/artifact-put.sh <bench> <run-id> <file>...
#   Stage <file>s under sim/.artifact-stage/ (git-ignored) if you like; any
#   path works. Writes manifests/artifacts/<bench>-<run-id>.manifest.json.
# Exit codes: 0 stored, 2 bad usage, 3 broker unset, 4 klt lacks `artifact put`,
#   otherwise klt's own nonzero status (e.g. broker unreachable).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <bench> <run-id> <file>..." >&2
  exit 2
fi
bench="$1"; run_id="$2"; shift 2
case "${bench}${run_id}" in
  *[!A-Za-z0-9._-]*) echo "artifact-put: bench/run-id must match [A-Za-z0-9._-]+" >&2; exit 2 ;;
esac

if [ -z "${KLT_ARTIFACT_BROKER:-}" ]; then
  echo "artifact-put: KLT_ARTIFACT_BROKER is unset; refusing (no fallback to committed bytes)" >&2
  exit 3
fi
if ! klt artifact put --help >/dev/null 2>&1; then
  echo "artifact-put: this klt has no 'artifact put'; refusing (no fallback to committed bytes)" >&2
  exit 4
fi

manifest="${REPO_ROOT}/manifests/artifacts/${bench}-${run_id}.manifest.json"
mkdir -p "$(dirname "$manifest")"
# Write to a temp manifest and move it into place only on success, so a
# failed put never leaves a partial manifest.
tmp="$(mktemp "${manifest}.XXXXXX")"
rm -f "$tmp"
trap 'rm -f "$tmp"' EXIT
klt artifact put --manifest "$tmp" "$@"
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "artifact-put: klt artifact put failed (exit ${rc}); no manifest written" >&2
  exit "$rc"
fi
mv "$tmp" "$manifest"
trap - EXIT
echo "artifact-put: wrote ${manifest#"${REPO_ROOT}"/}"
