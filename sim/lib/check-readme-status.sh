#!/usr/bin/env bash
#
# Fails if README.md's top-level "evidence records" / "verification
# campaigns" counts have drifted from what is actually on disk under
# sim/*/records/*.md.
#
# This exists because the two numbers are hand-written prose (issue #117):
# the tree grows every time a new record lands, but nothing forced the
# README to grow with it, and it silently underreported the repository for
# months. This check makes that drift a CI failure instead of a stale claim.
#
# Usage: sim/lib/check-readme-status.sh
# Exit codes: 0 counts match, 1 mismatch (or README prose not found).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
README="${REPO_ROOT}/README.md"

# Actual counts from the tree: one directory per campaign, one file per
# evidence record, under sim/<campaign>/records/*.md.
records_actual=$(find "${REPO_ROOT}/sim" -path '*/records/*.md' -type f | wc -l | tr -d ' ')
campaigns_actual=$(find "${REPO_ROOT}/sim" -path '*/records/*.md' -type f \
  | sed -E 's#.*/sim/([^/]+)/records/.*#\1#' | sort -u | wc -l | tr -d ' ')

# Claimed counts, scraped from README.md's status section, e.g.:
#   "**52 evidence records** across 18\nverification campaigns"
# Prose may wrap across lines, so collapse whitespace before matching.
readme_flat=$(tr '\n' ' ' < "${README}" | tr -s ' ')
records_claimed=$(echo "${readme_flat}" | grep -oE '[0-9]+ evidence records' | head -1 | grep -oE '[0-9]+')
campaigns_claimed=$(echo "${readme_flat}" | grep -oE '[0-9]+ verification campaigns' | head -1 | grep -oE '[0-9]+')

status=0

if [ -z "${records_claimed:-}" ]; then
  echo "FAIL: could not find '<N> evidence records' in README.md" >&2
  status=1
elif [ "${records_claimed}" != "${records_actual}" ]; then
  echo "FAIL: README.md claims ${records_claimed} evidence records," \
    "but sim/*/records/*.md has ${records_actual}" >&2
  status=1
fi

if [ -z "${campaigns_claimed:-}" ]; then
  echo "FAIL: could not find '<N> verification campaigns' in README.md" >&2
  status=1
elif [ "${campaigns_claimed}" != "${campaigns_actual}" ]; then
  echo "FAIL: README.md claims ${campaigns_claimed} verification campaigns," \
    "but sim/*/records/*.md spans ${campaigns_actual} campaign directories" >&2
  status=1
fi

if [ "${status}" -eq 0 ]; then
  echo "OK: README.md matches the tree (${records_actual} records," \
    "${campaigns_actual} campaigns)"
fi

exit "${status}"
