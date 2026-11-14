#!/usr/bin/env bash
#
# Fails if README.md's (and sim/STATUS.md's) top-level "evidence records" / "verification
# campaigns" counts have drifted from what is actually on disk under
# sim/*/records/*.md.
#
# This exists because the two numbers are hand-written prose (issue #117):
# the tree grows every time a new record lands, but nothing forced the
# README to grow with it, and it silently underreported the repository for
# months. This check makes that drift a CI failure instead of a stale claim.
#
# Every occurrence of each claim in README.md is graded, not only the first;
# the sibling copy of the same two counts in sim/CHARACTERIZATION.md is graded
# by sim/lib/check-characterization-coverage.sh's aggregate-count rule, which
# is where that document's other tree-derived claim already lives (#237).
#
# It also grades README.md's and signoff/README.md's quotation of
# signoff/tier-report.json's T1 met count (issue #928) -- the one claim here
# whose source of truth is a committed machine verdict rather than the sim/
# tree. See that rule's own header for the strikethrough skip it needs.
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
# Dependencies: python3 (hard -- the T1 tier-count rule needs it; absence is
# a failure, not a skip, because a partial pass is not a pass).
#
# Exit codes: 0 counts match, 1 mismatch (or README prose not found).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
README="${REPO_ROOT}/README.md"
# The long-form campaign narrative moved out of README.md (#703) into this
# page. It is graded exactly as README.md was: every occurrence of every
# claim in either file must agree with the tree.
STATUS_PAGE="${REPO_ROOT}/sim/STATUS.md"

# shellcheck source=sim/lib/record-campaigns.sh
. "$(dirname "${BASH_SOURCE[0]}")/record-campaigns.sh"

# Actual counts from the tree: one directory per campaign, one file per
# evidence record, under sim/<campaign>/records/*.md.
records_actual=$(find "${REPO_ROOT}/sim" -path '*/records/*.md' -type f | wc -l | tr -d ' ')
campaigns_actual=$(sim_record_campaigns "${REPO_ROOT}" | wc -l | tr -d ' ')

# Claimed counts, scraped from README.md's status section, e.g.:
#   "**52 evidence records** across 18\nverification campaigns"
# Prose may wrap across lines, so collapse whitespace before matching.
#
# EVERY occurrence of each claim is graded, not just the first. The
# period-jitter rule below already worked that way, because the drift it was
# written for was two different stale numbers in two paragraphs of this same
# file -- but these two claims were checked with `head -1`, so a second,
# contradicting count further down README.md would have passed silently. That
# is the identical gap the layout-side count rule closed in #495 (a commit
# fixed one count and left a stale sibling four sections later, and a
# presence-only check reported OK on that tree); it is closed here before it
# is needed rather than after.
for doc in "${README}" "${STATUS_PAGE}"; do
  if [ ! -f "${doc}" ]; then
    echo "FAIL: ${doc#"${REPO_ROOT}"/} does not exist -- its status claims cannot be graded" >&2
    exit 1
  fi
done
readme_flat=$(cat "${README}" "${STATUS_PAGE}" | tr '\n' ' ' | tr -s ' ')
mapfile -t records_claims < <(echo "${readme_flat}" | grep -oE '[0-9]+ evidence records' | grep -oE '^[0-9]+')
mapfile -t campaigns_claims < <(echo "${readme_flat}" | grep -oE '[0-9]+ verification campaigns' | grep -oE '^[0-9]+')

status=0

if [ "${#records_claims[@]}" -eq 0 ]; then
  echo "FAIL: could not find '<N> evidence records' in README.md or sim/STATUS.md" >&2
  status=1
else
  for claimed in "${records_claims[@]}"; do
    if [ "${claimed}" != "${records_actual}" ]; then
      echo "FAIL: README.md/sim/STATUS.md claims ${claimed} evidence records," \
        "but sim/*/records/*.md has ${records_actual}" >&2
      status=1
    fi
  done
fi

if [ "${#campaigns_claims[@]}" -eq 0 ]; then
  echo "FAIL: could not find '<N> verification campaigns' in README.md or sim/STATUS.md" >&2
  status=1
else
  for claimed in "${campaigns_claims[@]}"; do
    if [ "${claimed}" != "${campaigns_actual}" ]; then
      echo "FAIL: README.md/sim/STATUS.md claims ${claimed} verification campaigns," \
        "but sim/*/records/*.md spans ${campaigns_actual} campaign directories" >&2
      status=1
    fi
  done
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
  echo "FAIL: could not find 'covers <N> of the mandated 45 PVT corners' in README.md or sim/STATUS.md" \
    "-- period-jitter's coverage is quoted in status prose and must stay checkable" >&2
  status=1
else
  while read -r claimed; do
    if [ "${claimed}" != "${pj_actual}" ]; then
      echo "FAIL: README.md/sim/STATUS.md claims period-jitter covers ${claimed} of the mandated 45 PVT" \
        "corners, but sim/period-jitter/corners/*/ holds ${pj_actual} distinct corner logs" >&2
      status=1
    fi
  done <<<"${pj_claims}"
fi

# T1 tier-count claim vs. signoff/tier-report.json (issue #928).
#
# README.md introduces that report as the "machine verdict of record" and
# then quotes its met count in prose, two clauses after promising the figure
# is "re-checked in CI so it cannot go stale". Nothing compared the two, and
# the figure sat at **0 of 22** for weeks after the report moved to 6 -- the
# same defect class #654 fixed one directory down, recurring in a second
# file. That recurrence is the argument for grading it here rather than
# correcting the sentence again.
#
# Three things this rule deliberately does NOT do:
#
#   * It does not shell out to `klt` and does not regenerate the report.
#     `signoff/run-signoff.sh --check` already owns regeneration and requires
#     the pinned klt, so a rule built on it would only run on the klt-gated
#     CI step. This one reads the committed JSON, so it keeps running in the
#     headless `checks` job and for a contributor with no klt installed.
#   * It does not derive the denominator from `len(items)`. That array holds
#     25 rows -- the 22 T1 rows plus one each of T2/T3/T4, whose `partition`
#     is null -- so counting it grades 25 and fails a correct README. The
#     scalar `t1_item_count`/`t1_met_count` fields are the report's own
#     answer and are what this reads.
#   * It does not reuse `readme_flat` above. That blob is `cat`-ed and
#     whitespace-collapsed across documents, which both loses the per-file
#     attribution a `FAIL:` here needs and destroys the newlines the
#     strikethrough bound below depends on. This rule reads each file
#     separately and strips struck spans BEFORE collapsing.
#
# The strikethrough skip is the one subtlety. This repository corrects itself
# by striking the old sentence and writing the new one beside it, so
# signoff/README.md carries the live "**6 of 22 T1 rows met**" on line 9 and
# the retracted "~~**0 of 22 T1 rows met**~~" (the pre-#798 verdict) on line
# 11. A rule that graded both would read a retraction as a live claim and
# fail CI on a correct tree. The pattern is the documented form from
# docs/lib/check-issue-reference-state.sh:248, `re.DOTALL` included: 10 of
# signoff/README.md's struck spans wrap a newline within one paragraph, so a
# single-line pattern would miss them, and the `(?!\n\s*\n)` bound keeps an
# odd number of `~~` markers from pairing an unclosed opener with the next
# real opener and silently exempting everything between them.
TIER_REPORT="${REPO_ROOT}/signoff/tier-report.json"
SIGNOFF_README="${REPO_ROOT}/signoff/README.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- the T1 tier-count rule could not run," \
    "and a check that did not run is not a check that passed" >&2
  status=1
  tier_summary="ungraded"
else
  tier_summary=$(python3 - "${REPO_ROOT}" "${TIER_REPORT}" "${README}" "${SIGNOFF_README}" <<'PY'
import json
import re
import sys

repo_root, report_path = sys.argv[1], sys.argv[2]
graded = sys.argv[3:]

# docs/lib/check-issue-reference-state.sh:248, verbatim. See that file's
# header for why the blank-line bound and re.DOTALL are both required.
STRUCK = re.compile(r"~~(?:(?!\n\s*\n).)+?~~", re.DOTALL)
# "6 of 22 rows met" (README.md) and "6 of 22 T1 rows met"
# (signoff/README.md). Bold markers sit outside the match, so **...** and a
# bare sentence read the same.
CLAIM = re.compile(r"([0-9]+) of ([0-9]+) (?:T1 )?rows met")

failures = []


def rel(path):
    prefix = repo_root.rstrip("/") + "/"
    return path[len(prefix):] if path.startswith(prefix) else path


report = None
try:
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
except FileNotFoundError:
    failures.append(
        "FAIL: %s does not exist -- it is the T1 verdict of record, so the "
        "README's tier count cannot be graded without it" % rel(report_path)
    )
except (OSError, ValueError) as exc:
    failures.append(
        "FAIL: %s could not be read as JSON (%s) -- the README's tier count "
        "cannot be graded" % (rel(report_path), exc)
    )

counts = {}
if report is not None:
    if not isinstance(report, dict):
        failures.append(
            "FAIL: %s is not a JSON object -- the README's tier count cannot "
            "be graded" % rel(report_path)
        )
    else:
        for field in ("t1_met_count", "t1_item_count"):
            value = report.get(field)
            # A zero is a value, not a missing claim, so this tests the type
            # rather than truthiness. bool is an int subclass; exclude it.
            if isinstance(value, bool) or not isinstance(value, int):
                failures.append(
                    "FAIL: %s has no integer `%s` field -- the README's tier "
                    "count cannot be graded against it" % (rel(report_path), field)
                )
            else:
                counts[field] = value

summary = "ungraded"
if len(counts) == 2:
    met, total = counts["t1_met_count"], counts["t1_item_count"]
    summary = "%d/%d" % (met, total)
    for doc in graded:
        try:
            with open(doc, encoding="utf-8") as handle:
                raw = handle.read()
        except OSError as exc:
            failures.append(
                "FAIL: %s could not be read (%s) -- its T1 tier-count claim "
                "cannot be graded" % (rel(doc), exc)
            )
            continue
        # Struck spans out FIRST, while the newlines they are bounded on are
        # still present; only then collapse whitespace so a claim may wrap.
        text = " ".join(STRUCK.sub(" ", raw).split())
        claims = CLAIM.findall(text)
        if not claims:
            # A selector that silently matches nothing is a check reporting
            # OK on a tree it never graded -- the same reason the three rules
            # above treat "claim not found" as a failure.
            failures.append(
                "FAIL: could not find '<N> of <M> rows met' in %s -- the T1 "
                "verdict is quoted in that document's prose and must stay "
                "checkable against %s" % (rel(doc), rel(report_path))
            )
            continue
        # EVERY occurrence is graded, not just the first: the drift this
        # script was extended for was two paragraphs of one file carrying two
        # different stale numbers for the same campaign.
        for claimed_met, claimed_total in claims:
            if int(claimed_met) != met or int(claimed_total) != total:
                failures.append(
                    "FAIL: %s claims %s of %s T1 rows met, but %s records %d "
                    "of %d" % (
                        rel(doc), claimed_met, claimed_total,
                        rel(report_path), met, total,
                    )
                )

for failure in failures:
    sys.stderr.write(failure + "\n")
print(summary)
sys.exit(1 if failures else 0)
PY
  )
  tier_rc=$?
  [ "${tier_rc}" -eq 0 ] || status=1
  [ -n "${tier_summary}" ] || tier_summary="ungraded"
fi

if [ "${status}" -eq 0 ]; then
  echo "OK: README.md and sim/STATUS.md match the tree (${records_actual} records," \
    "${campaigns_actual} campaigns, period-jitter at ${pj_actual}/45 corners)," \
    "and README.md/signoff/README.md match signoff/tier-report.json" \
    "(T1 at ${tier_summary} rows met)"
fi

exit "${status}"
