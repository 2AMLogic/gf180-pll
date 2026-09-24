#!/usr/bin/env bash
#
# Fails if a reader-facing status document points at a sim/ evidence record
# that a later record has superseded, without naming any successor.
#
# WHY THIS EXISTS (issue #237)
#
# sim/README.md fixes the supersession convention this repository runs on:
#
#   - a record's bytes never change after creation, so a superseded record
#     carries no back-reference to what replaced it;
#   - the pointer lives only in the NEW record's `Supersedes` field;
#   - therefore "Standing is found by reading *forward* from the superseded
#     record: scan for the record that names it."
#
# That forward scan is a thing a human has to remember to do. Nothing ran it.
# The consequence, found on 2026-09-24 and fixed in the same commit that added
# this check: docs/chipalooza/challenge-5-proposal.md -- the document written
# to be sent verbatim to an outside reader -- still described the period-jitter
# campaign's one FAIL verdict as a live, open measurement defect ("filed as
# issue #273", "tracked separately at issue #273"), 18 days after #273 closed
# and `sim/period-jitter/records/20260906-095050-3a8a6ef.md` re-measured
# exactly those two points against the corrected gate and recorded both PASS.
# Three of that document's other citations pointed at pre-`sim/harness`
# records whose migrated successors it never named.
#
# Not one existing check could see any of it: check-readme-status.sh grades
# README.md's counts, check-characterization-coverage.sh grades the aggregation
# report's rows and its own count of them, and check-layout-status-claims.sh
# grades layout claims. All three grade what a document *says*; none grades
# whether the evidence it *cites* is still the current evidence.
#
# THE RULES
#
# 1. EXISTENCE. Every `<record-id>` a graded document cites must resolve to a
#    real sim/*/records/<record-id>.md on the tree. A citation of a record that
#    does not exist is unverifiable by definition.
#
# 2. FORWARD POINTER. If a graded document cites record P, and some record S on
#    the tree declares `Supersedes: P`, then the document must also name at
#    least one such S -- somewhere in the same document, not necessarily beside
#    the citation.
#
#    "At least one, somewhere in the document" rather than "all of them, at the
#    citation site" is deliberate, and it is the weakest rule that still catches
#    every drift above. sim/README.md's supersession-is-per-bench rule means one
#    predecessor may legitimately have several successors, each replacing a
#    different half of it (20260731-194124-afa338c has three), and a document
#    citing it for the half that was not replaced should not be forced to name
#    the other halves' records. What must never happen is a reader being handed
#    a superseded record with no thread at all to pull.
#
# Deleting the predecessor citation does silence rule 2, and that is a
# legitimate fix, not a loophole: a document that does not point a reader at a
# superseded record has no stale pointer to be graded. This is the one place
# this check differs in doctrine from its siblings' "deleting the number is not
# a fix" -- there, the number is the claim; here, the claim is the pointer.
# Rule 1 still holds the other end: the successor you cite has to be real.
#
# WHY spec/pll.md IS NOT GRADED
#
# It carries exactly one citation this rule would flag -- the `vco-tuning-range`
# `20260731-175947-0a12e6c` output-band/Kvco citation -- and that one is already
# a ratified, reasoned, explicitly-recorded carve-out: DR-007 Amendment A4, of
# which spec/pll.md's own header states that the citation is "deliberately
# **not** updated even though a migrated successor exists," because the
# successor's printed numbers differ from this file's stated values in the last
# 1-2 significant digits at several rows. Grading spec/pll.md would mean either
# failing CI on a ratified decision or shipping a one-off exemption for the only
# case. When A4 is discharged (every affected row reconciled against the
# migrated record), adding "spec/pll.md" to GRADED below is the whole change.
#
# WHAT IT DOES NOT DO
#
# It does not read a record's content, so it cannot tell whether the prose
# around a citation still matches what the cited record measured; it grades the
# citation graph only. And a document that cites nothing is trivially clean.
#
# It DOES follow a supersession chain to its end, but as a consequence of the
# two rules rather than as a third one: naming a successor is itself a citation
# of that successor, so if that successor has in turn been superseded, rule 2
# applies to it too. A document therefore has to arrive at a record that is
# current. This is why fixing the proposal's lock-detector citation pulled in
# `20260916-052313-b1633b5` as well as `20260802-050119-c24ee3a` -- the check
# would not accept stopping halfway down a four-hop chain.
#
# Usage: sim/lib/check-record-supersession.sh
# Exit codes: 0 every graded document's citations exist and carry a forward
#             pointer, 1 a citation is dangling, a superseded citation has no
#             named successor, a graded document is missing, or the record tree
#             yields no supersession edges at all (a broken parser must not
#             look like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The reader-facing status documents. README.md and the Chipalooza proposal are
# the two documents check-layout-status-claims.sh already grades for the same
# reason (they are read by people who will not open sim/); CHARACTERIZATION.md
# is the aggregation whose entire job is to cite current evidence.
GRADED=(
  "README.md"
  "sim/CHARACTERIZATION.md"
  "docs/chipalooza/challenge-5-proposal.md"
)

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${GRADED[@]}" <<'PY'
import os
import re
import sys

repo_root, graded = sys.argv[1], sys.argv[2:]

# A record id is the record's filename stem, e.g. 20260906-095050-3a8a6ef.
RECORD_ID = r"\d{8}-\d{6}-[0-9a-f]{7}"

# `- **Supersedes**: <record-id> -- optional free-text qualifier`, per
# sim/README.md's record schema. Only the first token after the colon is a
# record id: the qualifier that follows routinely names *other* records in
# prose ("`20260901-155456-46b92f8` is re-read in full and ..."), and the
# no-predecessor spellings this tree uses -- "(none)", "(none -- first record
# for this claim)", "nothing. ..." -- must not be mined for ids either.
SUPERSEDES = re.compile(
    r"^- \*\*Supersedes\*\*:[ \t]*[`\[]?(" + RECORD_ID + r")\b", re.MULTILINE
)

records = {}
for campaign in sorted(os.listdir(os.path.join(repo_root, "sim"))):
    rec_dir = os.path.join(repo_root, "sim", campaign, "records")
    if not os.path.isdir(rec_dir):
        continue
    for name in sorted(os.listdir(rec_dir)):
        if name.endswith(".md"):
            records[name[:-3]] = os.path.join("sim", campaign, "records", name)

if not records:
    sys.stderr.write(
        "FAIL: found no sim/*/records/*.md files -- enumeration is broken\n"
    )
    sys.exit(1)

# predecessor id -> [successor ids], read forward exactly as sim/README.md
# says standing must be read.
successors = {}
for rid, path in records.items():
    with open(os.path.join(repo_root, path), encoding="utf-8") as fh:
        m = SUPERSEDES.search(fh.read())
    if m:
        successors.setdefault(m.group(1), []).append(rid)

if not successors:
    sys.stderr.write(
        "FAIL: no record on the tree declares a `Supersedes` predecessor. The "
        "tree holds %d records and this repository's supersession convention "
        "is in active use, so this is a parser failure, not a clean tree.\n"
        % len(records)
    )
    sys.exit(1)

failed = False
checked = 0

for doc in graded:
    doc_path = os.path.join(repo_root, doc)
    if not os.path.isfile(doc_path):
        sys.stderr.write("FAIL: %s does not exist\n" % doc)
        failed = True
        continue
    with open(doc_path, encoding="utf-8") as fh:
        text = fh.read()

    cited = sorted(set(re.findall(RECORD_ID, text)))
    checked += len(cited)

    for rid in cited:
        if rid not in records:
            failed = True
            sys.stderr.write(
                "FAIL: %s cites record `%s`, which is not on the tree -- no "
                "sim/*/records/%s.md exists\n" % (doc, rid, rid)
            )

    for rid in cited:
        succ = successors.get(rid)
        if not succ or any(s in text for s in succ):
            continue
        failed = True
        sys.stderr.write(
            "FAIL: %s cites the superseded record `%s` and names none of its "
            "successor(s) %s. A reader is pointed at evidence that has been "
            "replaced with no thread to pull -- name the successor, or drop "
            "the citation (see %s).\n"
            % (doc, rid, ", ".join("`%s`" % s for s in succ), records[succ[0]])
        )

if failed:
    sys.exit(1)

print(
    "OK: %d record citations across %d documents; every cited record exists "
    "and every superseded one names a successor (%d supersession edges on a "
    "tree of %d records)"
    % (
        checked,
        len(graded),
        sum(len(v) for v in successors.values()),
        len(records),
    )
)
PY
