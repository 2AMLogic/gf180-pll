#!/usr/bin/env bash
#
# Fails if a sim/*/records/ campaign directory exists on disk without a
# corresponding entry in sim/CHARACTERIZATION.md's summary table.
#
# This exists because #147's aggregated characterization report (unlike
# sim/README.md's per-campaign methodology entries) is hand-maintained --
# nothing forces it to grow when a new campaign directory lands. This check
# makes "a whole new campaign exists and nobody added it to the report" a CI
# failure instead of a silent gap. It does NOT detect a stale headline
# number, a hash that no longer matches its cited record, or a new record
# added inside an already-listed campaign -- see CHARACTERIZATION.md's own
# "Maintenance" section for what still needs human review.
#
# Usage: sim/lib/check-characterization-coverage.sh
# Exit codes: 0 every campaign is covered, 1 a campaign is missing (or the
#             report file is absent).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="${REPO_ROOT}/sim/CHARACTERIZATION.md"

# shellcheck source=sim/lib/record-campaigns.sh
. "$(dirname "${BASH_SOURCE[0]}")/record-campaigns.sh"

if [ ! -f "${REPORT}" ]; then
  echo "FAIL: ${REPORT} does not exist" >&2
  exit 1
fi

# One campaign per sim/<name>/records/ directory that actually holds at
# least one record -- same enumeration rule sim/lib/check-readme-status.sh
# uses for its counts.
mapfile -t campaigns < <(sim_record_campaigns "${REPO_ROOT}")

if [ "${#campaigns[@]}" -eq 0 ]; then
  echo "FAIL: found no sim/*/records/*.md files -- enumeration is broken" >&2
  exit 1
fi

status=0
missing=()

for campaign in "${campaigns[@]}"; do
  # The report cites each campaign as a backtick-quoted first-column table
  # cell, e.g. "| \`devchar-delay\` |" -- see CHARACTERIZATION.md's summary
  # table. A plain string match is deliberately looser than a strict
  # per-column regex: it also accepts the same name appearing in a caveat
  # or cross-reference, which is fine -- the goal is "not silently absent",
  # not "appears in exactly one place".
  if ! grep -qF "\`${campaign}\`" "${REPORT}"; then
    missing+=("${campaign}")
    status=1
  fi
done

if [ "${status}" -ne 0 ]; then
  echo "FAIL: sim/CHARACTERIZATION.md has no entry for:" >&2
  for campaign in "${missing[@]}"; do
    echo "  - ${campaign}" >&2
  done
  exit 1
fi

echo "OK: sim/CHARACTERIZATION.md covers all ${#campaigns[@]} campaign directories"
