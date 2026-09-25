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
# A third guard, the LATEST-RECORD-CITED RULE (#544), closes the one
# direction the two rules above still miss: a campaign that already has a
# row, and whose *directory* is therefore invisible to the coverage rule
# above, can grow a new record whose headline nobody folds into that row.
# That happened for real: PR #484 added
# `sim/vco-tuning-range/records/20260923-084925-1655e11.md`, closing #482's
# band-0 coverage-hole finding, to the already-listed `vco-tuning-range`
# campaign -- and `sim/CHARACTERIZATION.md`'s row kept citing only the
# earlier, superseded-in-substance-but-not-in-form record, so its Status
# column asserted an open finding the tree had already closed, for two days,
# with every existing check green throughout. The rule: for every campaign
# directory, the chronologically-latest record under its `records/`
# (records are named `<timestamp>-<hash>.md`, so lexical sort is
# chronological) must either be cited somewhere in `sim/CHARACTERIZATION.md`,
# or be named -- record id plus a one-line reason -- in this script's own
# NOT_AGGREGATED allowlist below. The allowlist exists because
# `sim/README.md`'s supersession-is-per-bench rule means a campaign
# directory can legitimately carry several live sub-claims and diagnostic /
# re-examination records that are deliberately not the campaign's headline
# (see e.g. this report's `supply-sensitivity` row, which already names
# several such records by hand) -- a bare "every record must be cited" rule
# would be wrong, not merely strict. Putting an exclusion on the allowlist
# makes it a written decision instead of a silent omission.
#
# It does NOT detect a stale headline number *inside* a citation that is
# already present (only a whole new, wholly uncited record) -- see
# CHARACTERIZATION.md's own "Maintenance" section for what still needs
# human review there.
#
# A fourth, optional guard (also #544) recomputes the sha256 of every
# `path` (`hash`) citation pair this report makes and fails on mismatch, so
# the "records are append-only, so a citation's hash never goes stale"
# claim several records make is self-enforcing rather than self-asserted.
#
# Usage: sim/lib/check-characterization-coverage.sh
# Exit codes: 0 every campaign is covered, the stated counts match the tree,
#             every campaign's latest record is cited or allowlisted, and
#             every cited content hash matches; 1 otherwise (a campaign is
#             missing, a count disagrees, an uncited/unallowlisted latest
#             record exists, a cited hash is stale, or the report file is
#             absent).

# NOT_AGGREGATED: deliberate exclusions from the latest-record-cited rule.
# One "<campaign>:<record-id>  # <one-line reason>" entry per exclusion.
# A campaign/record pair not on this list, and not cited in
# sim/CHARACTERIZATION.md, fails the check below.
NOT_AGGREGATED=(
  # Text/arithmetic re-examination of already-committed logs (trim-code
  # wiring audit, #515) -- 0 new simulations, no verdict in this report's
  # supply-sensitivity row changes as a result. Same class as the
  # DR-021/DR-025 re-examination records that row already names by hand;
  # see sim/supply-sensitivity/records/20260925-111906-1937f52.md's own
  # "Claim" and "Limitations" sections.
  "supply-sensitivity:20260925-111906-1937f52  # DR-025-class re-examination record, 0 new simulations, no verdict changed"
)

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

# The latest-record-cited rule (see the header, #544): every campaign's
# chronologically-latest record must be cited or allowlisted.
uncited=()

for campaign in "${campaigns[@]}"; do
  rec_dir="${REPO_ROOT}/sim/${campaign}/records"
  # Records are named <timestamp>-<hash>.md, e.g. 20260923-084925-1655e11.md,
  # so a plain lexical sort of the filenames is a chronological sort too.
  latest_file=$(find "${rec_dir}" -maxdepth 1 -name '*.md' -type f | sort | tail -1)
  if [ -z "${latest_file}" ]; then
    echo "FAIL: ${rec_dir} has no *.md records -- enumeration is broken" >&2
    status=1
    continue
  fi
  latest_id="$(basename "${latest_file}" .md)"

  if grep -qF "${latest_id}" "${REPORT}"; then
    continue
  fi

  allowlisted=0
  for entry in "${NOT_AGGREGATED[@]:-}"; do
    # Strip the trailing "  # reason" comment before matching the key.
    key="${entry%%#*}"
    key="${key%"${key##*[![:space:]]}"}"
    if [ "${key}" = "${campaign}:${latest_id}" ]; then
      allowlisted=1
      break
    fi
  done

  if [ "${allowlisted}" -eq 0 ]; then
    uncited+=("${campaign}:${latest_id}")
    status=1
  fi
done

if [ "${#uncited[@]}" -gt 0 ]; then
  echo "FAIL: the chronologically-latest record in these campaigns is" \
    "neither cited by sim/CHARACTERIZATION.md nor listed in this script's" \
    "own NOT_AGGREGATED allowlist:" >&2
  for entry in "${uncited[@]}"; do
    echo "  - ${entry}" >&2
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

# The optional content-hash rule (see the header, #544): recompute the
# sha256 of every "`path` (`12-hex-prefix`)" citation this report makes and
# fail if any no longer matches the file on disk. Needs python3, same as
# the aggregate-count rule above; a missing interpreter fails this leg too.
if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- the content-hash rule could not run," \
    "and a partial pass is not a pass" >&2
  status=1
elif ! python3 - "${REPO_ROOT}" "${REPORT}" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

repo_root, report_path = Path(sys.argv[1]), Path(sys.argv[2])

with open(report_path, encoding="utf-8") as fh:
    text = fh.read()

# `` `sim/<campaign>/records/<record-id>.md` (`<12-hex-prefix>`) `` -- the
# citation convention this report documents and uses at every cited record.
# The parenthesis sometimes carries a trailing annotation after the hash
# (e.g. "(`92c02f50a4a2`, #58)"), so the hash need not be the parenthesis's
# only content -- just its first, immediately after the opening `(`.
CITATION = re.compile(
    r"`(sim/[A-Za-z0-9_./-]+\.md)`\s*\(`([0-9a-f]{12})`[^)]*\)"
)

pairs = sorted(set(CITATION.findall(text)))

# A document that cites nothing in this format is trivially clean -- same
# doctrine sim/lib/check-record-supersession.sh states for its own citation
# graph. The real sim/CHARACTERIZATION.md always carries dozens of these
# pairs, so an empty result here in CI is a real signal (see the report's
# own coverage rule above, which would already be failing by then); it is
# not grounds to fail *this* leg on its own.
if not pairs:
    print("OK: sim/CHARACTERIZATION.md cites no `path` (`hash`) pairs -- nothing to check")
    sys.exit(0)

failed = False
for rel_path, cited_hash in pairs:
    full_path = repo_root / rel_path
    if not full_path.is_file():
        failed = True
        sys.stderr.write(
            "FAIL: sim/CHARACTERIZATION.md cites `%s` (`%s`), which does not "
            "exist on disk\n" % (rel_path, cited_hash)
        )
        continue
    actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()[:12]
    if actual_hash != cited_hash:
        failed = True
        sys.stderr.write(
            "FAIL: sim/CHARACTERIZATION.md cites `%s` with hash `%s`, but its "
            "sha256 12-hex prefix on disk is `%s` -- sim/ records are "
            "append-only, so a cited record's bytes should never change; "
            "re-check whether the citation itself is stale.\n"
            % (rel_path, cited_hash, actual_hash)
        )

if not failed:
    print(
        "OK: all %d `path` (`hash`) citations in sim/CHARACTERIZATION.md "
        "match the files on disk" % len(pairs)
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
