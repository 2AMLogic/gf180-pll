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
# It also guards period-jitter's PVT-corner coverage claim (issue #237).
# That campaign's coverage grew from 5 corners to the full mandated 45 over
# six records in a single day, and the README kept claiming 5 (in one
# paragraph) and 13 (in another) for weeks afterwards -- two different stale
# numbers for the same campaign in one file. It is the one sim/ claim whose
# value is quoted in README prose rather than left to the records, so it is
# the one that needed a check.
#
# Usage: sim/lib/check-readme-status.sh
# Exit codes: 0 counts match, 1 mismatch (or README prose not found).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
README="${REPO_ROOT}/README.md"

# shellcheck source=sim/lib/record-campaigns.sh
. "$(dirname "${BASH_SOURCE[0]}")/record-campaigns.sh"

# Actual counts from the tree: one directory per campaign, one file per
# evidence record, under sim/<campaign>/records/*.md.
records_actual=$(find "${REPO_ROOT}/sim" -path '*/records/*.md' -type f | wc -l | tr -d ' ')
campaigns_actual=$(sim_record_campaigns "${REPO_ROOT}" | wc -l | tr -d ' ')

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

# period-jitter PVT-corner coverage. Each corner run leaves exactly one
# <corner-id>.log under sim/period-jitter/corners/<record-id>/; a corner
# re-run by a later record reuses its id, so the union of basenames across
# every record directory is the campaign's real coverage. EVERY occurrence
# of the claim in README.md must agree -- the drift this guards against was
# two different stale numbers in two paragraphs of the same file.
pj_actual=$(find "${REPO_ROOT}/sim/period-jitter/corners" -name '*.log' -type f \
  -exec basename {} .log \; 2>/dev/null | sort -u | wc -l | tr -d ' ')
pj_claims=$(echo "${readme_flat}" |
  grep -oE 'covers [0-9]+ of the mandated 45 PVT corners' |
  grep -oE '^covers [0-9]+' | grep -oE '[0-9]+')

if [ -z "${pj_claims}" ]; then
  echo "FAIL: could not find 'covers <N> of the mandated 45 PVT corners' in README.md" \
    "-- period-jitter's coverage is quoted in README prose and must stay checkable" >&2
  status=1
else
  while read -r claimed; do
    if [ "${claimed}" != "${pj_actual}" ]; then
      echo "FAIL: README.md claims period-jitter covers ${claimed} of the mandated 45 PVT" \
        "corners, but sim/period-jitter/corners/*/ holds ${pj_actual} distinct corner logs" >&2
      status=1
    fi
  done <<<"${pj_claims}"
fi

if [ "${status}" -eq 0 ]; then
  echo "OK: README.md matches the tree (${records_actual} records," \
    "${campaigns_actual} campaigns, period-jitter at ${pj_actual}/45 corners)"
fi

exit "${status}"
