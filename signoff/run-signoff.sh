#!/usr/bin/env bash
# Render this block's T1 tier verdict with `klt signoff --manifest`, and
# either write it to signoff/tier-report.json or verify the committed copy
# still matches.
#
#   bash signoff/run-signoff.sh           # regenerate signoff/tier-report.json
#   bash signoff/run-signoff.sh --check   # fail if the committed report is stale
#
# The --check mode is what CI runs. It is the whole point of committing the
# report: a manifest that cites an evidence artifact which has since changed
# (a re-run DRC, an edited netlist, a moved file) re-renders differently, and
# the diff fails the build instead of the verdict quietly rotting.
#
# Run from anywhere; paths below are resolved against the repo root, and `klt`
# is invoked *from* the repo root so that relative evidence paths inside the
# manifest mean the same thing here, in CI, and on a reviewer's machine.
#
# Exit codes:
#   0  the report was written (default mode), or matches (--check)
#   1  the committed report is stale (--check), or the manifest/doc is bad
#   2  `klt` is not installed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="signoff/block-manifest.json"
TIERS_DOC="signoff/design-evidence-tiers.md"
REPORT="signoff/tier-report.json"

mode="write"
case "${1-}" in
  "") ;;
  --check) mode="check" ;;
  -h | --help)
    sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *)
    echo "error: unknown argument '$1' (expected --check or nothing)" >&2
    exit 1
    ;;
esac

cd "$REPO_ROOT"

if ! command -v klt >/dev/null 2>&1; then
  echo "error: klt not found on PATH -- install it with:" >&2
  echo "         pip install 'klayout-tools==0.5.0'" >&2
  echo "       (https://github.com/2AMLogic/klayout-tools)" >&2
  exit 2
fi

echo "klt: $(command -v klt) ($(klt --version 2>&1))" >&2

# `klt signoff --manifest` exits 3 when the block is not yet T1 -- which is
# the expected, honest state of this block today (see signoff/README.md). Only
# 0 (T1 reached) and 3 (not yet T1) are verdicts; anything else is a tool or
# input error and must not be written out as if it were a report.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
status=0
klt signoff \
  --manifest "$MANIFEST" \
  --tiers-doc "$TIERS_DOC" \
  --format json >"$tmp" || status=$?

case "$status" in
  0 | 3) ;;
  *)
    echo "error: klt signoff exited $status -- not a tier verdict" >&2
    cat "$tmp" >&2
    exit 1
    ;;
esac

if [ "$mode" = "check" ]; then
  if ! diff -u "$REPORT" "$tmp"; then
    echo >&2
    echo "error: $REPORT is stale -- re-render it with:" >&2
    echo "         bash signoff/run-signoff.sh" >&2
    echo "       and read signoff/README.md before updating any claim it backs." >&2
    exit 1
  fi
  echo "$REPORT is current." >&2
  exit 0
fi

cp "$tmp" "$REPORT"
echo "wrote $REPORT" >&2
