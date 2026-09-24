#!/usr/bin/env bash
#
# Fails if a sim/*/records/ campaign directory exists on disk without a
# corresponding entry in sim/CHARACTERIZATION.md's summary table.
#
# This exists because #147's aggregated characterization report (unlike
# sim/README.md's per-campaign methodology entries) is hand-maintained --
# nothing forces it to grow when a new campaign directory lands. This check
# makes "a whole new campaign exists and nobody added it to the report" a CI
# failure instead of a silent gap.
#
# A second guard, the AGGREGATE-COUNT RULE, grades the report's own count of
# what it covers (issue #237). The coverage rule above only asks whether each
# campaign has a row; the report *also* states, in prose, how many campaign
# directories and evidence records it aggregates -- and that number went
# stale by 19 records and 3 campaigns while every row it describes was
# present and the coverage rule reported OK:
#
#   "the current count is **21 campaign directories, 72 evidence records**
#    ... matching `README.md`'s own "72 evidence records across 21
#    verification campaigns" line"
#
# against a tree holding 91 records across 24 campaigns. Both halves of that
# sentence were wrong, including its *quotation* of a README line that
# sim/lib/check-readme-status.sh had already forced to 91/24 -- so the
# aggregation report told a reader that the graded document agreed with it
# when it did not. This is the same drift class the sim- and layout-side
# status checks were written for (#117, #237), in the one remaining document
# that restates the counts, and the same lesson as the layout side's count
# rule: grading the claim in one document does not grade the sibling copy of
# it in another.
#
# The rule: every "<N> campaign directories, <M> evidence records" and
# "<M> evidence records across <N> verification campaigns" phrase in
# sim/CHARACTERIZATION.md must equal the tree, wherever in the document it
# sits, and at least one such phrase must be present -- deleting the count is
# not a way to stop it being stale. A figure explicitly marked as historical
# ("at this report's original writing that was ...") is deliberately exempt:
# the report is allowed to say where it started, and pinning that exemption
# is what keeps this rule from forcing history to be rewritten.
#
# It does NOT detect a stale per-campaign headline number, a hash that no
# longer matches its cited record, or a new record added inside an
# already-listed campaign -- see CHARACTERIZATION.md's own "Maintenance"
# section for what still needs human review.
#
# Usage: sim/lib/check-characterization-coverage.sh
# Exit codes: 0 every campaign is covered and the stated counts match the
#             tree, 1 a campaign is missing, a count disagrees, or the report
#             file is absent.

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
fi

# The aggregate-count rule (see the header). Needs python3 for a match
# position and a window around it; a missing interpreter is a failure, not a
# quiet pass on the coverage rule alone -- a partial pass is not a pass.
records_actual=$(find "${REPO_ROOT}/sim" -path '*/records/*.md' -type f | wc -l | tr -d ' ')

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- the aggregate-count rule could not run," \
    "and a partial pass is not a pass" >&2
  status=1
elif ! python3 - "${REPORT}" "${#campaigns[@]}" "${records_actual}" <<'PY'
import re
import sys

report_path, campaigns, records = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

with open(report_path, encoding="utf-8") as fh:
    flat = re.sub(r"[ \t\n]+", " ", fh.read())

# Whitespace and/or markdown emphasis markers between the tokens of a claim:
# the real document writes its counts inside a `**...**` span.
E = r"[\s*]*"
# ("pattern", index of the campaign-count group, index of the record-count group)
SHAPES = [
    (
        r"([0-9]+)" + E + r"campaign director(?:y|ies)," + E + r"([0-9]+)" + E + r"evidence records?",
        1,
        2,
    ),
    (
        r"([0-9]+)" + E + r"evidence records?" + E + r"across" + E + r"([0-9]+)" + E + r"verification campaigns?",
        2,
        1,
    ),
]

# A figure introduced as the report's starting point is history, not a claim
# about the tree as it stands. Deliberately narrow -- one phrase, matched
# within a bounded lookback -- so that a writer cannot exempt a live count by
# accident. In the real document the marker sits ~11 characters ahead of the
# historical figure and ~110 ahead of the current one.
HISTORICAL = re.compile(r"original writing", re.IGNORECASE)
LOOKBACK = 60

failed = False
graded = 0

for pattern, ci, ri in SHAPES:
    for m in re.finditer(pattern, flat, re.IGNORECASE):
        if HISTORICAL.search(flat[max(0, m.start() - LOOKBACK):m.start()]):
            continue
        graded += 1
        stated_campaigns, stated_records = int(m.group(ci)), int(m.group(ri))
        if (stated_campaigns, stated_records) == (campaigns, records):
            continue
        failed = True
        quoted = flat[max(0, m.start() - 40):m.end() + 40].strip()
        sys.stderr.write(
            'FAIL: sim/CHARACTERIZATION.md states %d campaign directories and '
            "%d evidence records, but sim/*/records/*.md holds %d records "
            'across %d campaigns: "...%s..."\n'
            % (stated_campaigns, stated_records, records, campaigns, quoted)
        )

if graded == 0:
    failed = True
    sys.stderr.write(
        "FAIL: sim/CHARACTERIZATION.md states no current count of what it "
        "aggregates -- it must say how many campaign directories and evidence "
        "records it covers (%d and %d today). Deleting the number is not a way "
        "to stop it being stale.\n" % (campaigns, records)
    )

sys.exit(1 if failed else 0)
PY
then
  status=1
fi

if [ "${status}" -ne 0 ]; then
  exit 1
fi

echo "OK: sim/CHARACTERIZATION.md covers all ${#campaigns[@]} campaign directories" \
  "and states ${#campaigns[@]} campaigns / ${records_actual} records, matching the tree"
