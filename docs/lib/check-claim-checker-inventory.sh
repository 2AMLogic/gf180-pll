#!/usr/bin/env bash
#
# Fails if a document that states how many claim checkers this repository has
# -- or which ones -- disagrees with the tree.
#
# WHY THIS EXISTS (issue #237)
#
# This repository grades almost every claim its outward-facing documents make
# against something it can re-derive: counts against the `sim/` tree, cited
# records against the supersession graph, quoted values against the committed
# per-corner CSVs, issue references against the forge. Two claims were left
# out, and both are claims about the grading family itself:
#
#   - `docs/claim-checker-inventory.md` -- the ratified answer to "what
#     checkers exist" (#699) -- said "there are 16 `*/lib/check-*.sh`
#     scripts" and carried a 16-row table. The tree had 17.
#     `sim/lib/check-artifact-manifests.sh` landed on 2026-10-23 and was
#     never added, so for three weeks the file written to enumerate the
#     family omitted a member of it while asserting a total.
#   - `docs/chipalooza/challenge-5-proposal.md` section 5.1 opened with
#     "Eleven checks grade the table above." That was true on 2026-09-25,
#     when eleven was every checker then in the tree bar the one the same
#     commit added. Six more have landed since.
#
# `sim/tests/test_check_script_invocability.py` already guarantees a new
# checker cannot be forgotten by CI: it discovers the family from the git
# index and fails on a member that is not runnable the way its own header
# says. Nothing made the same guarantee about the documents that COUNT the
# family, so a new checker could be fully wired, fully tested, and still
# invisible to the two files a reader consults to find out what is graded.
#
# That is the failure mode section 5.1 of the proposal narrates about itself,
# in the paragraph immediately below the sentence this check grades: "A
# section that narrates what CI prints was the one part of this document CI
# did not grade", after a corner-axis widening moved two counts and left the
# prose a day behind. The same doctrine applies one level up. An inventory
# that is not re-derived is a memory, and memories drift.
#
# THE RULES
#
# 1. FAMILY DISCOVERED. The family is `*/lib/check-*.sh` -- the same pathspec
#    `sim/tests/test_check_script_invocability.py` uses, kept identical on
#    purpose so the two guards cannot disagree about what a checker is.
#    Discovering ZERO members is a FAILURE, not a pass: a guard over an empty
#    set reports the same clean result as a guard over a healthy one, which is
#    the trap this repository names explicitly wherever it grades a zero
#    (the proposal's own section 5.1, on the monotonicity count).
#
#    Installer-managed trees are excluded by the glob itself -- `*` does not
#    match a leading dot -- so `.loom/` and `.claude/` copies, which are owned
#    upstream and are not this repository's to inventory, never enter the set.
#
# 2. INVENTORY TOTAL. `docs/claim-checker-inventory.md` must state the family
#    size. The sentence is located by the pathspec it quotes, so rewording the
#    prose around it is free and changing the number is not.
#
# 3. INVENTORY ROWS. The inventory's per-checker table must carry exactly one
#    row per family member, and no row naming a script the tree does not have.
#    This is the rule that would have caught the real defect: the total and
#    the row count were consistent with each other and both wrong, because
#    they were maintained together and derived from nothing.
#
# 4. PROPOSAL COUNTS. `docs/chipalooza/challenge-5-proposal.md` must state,
#    in one sentence, how many family members read it and how large the family
#    is -- "Eleven of this repository's eighteen claim checkers read this
#    document". Both numbers are re-derived here: the second is the family
#    size, the first is the number of members whose own text (or that of a
#    `.py` sibling they delegate to) names the proposal's path.
#
#    DELETING the sentence FAILS. Otherwise removing a narration would be the
#    cheapest way to stop it going stale, which is the doctrine
#    `check-characterization-coverage.sh`'s aggregate-count rule and
#    `check-quoted-value-provenance.sh`'s narration rule already state. A
#    claim this repository will not grade is a claim it should not print.
#
# NUMBER FORMS
#
# Both documents write small counts as English words, and section 5.1's
# sentence opens one -- a digit there would read as a defect of its own. So
# each graded count is accepted as a word ("eighteen") or as digits ("18"),
# and the failure message prints the form the document used beside the
# derived value. The word list stops at thirty; past that the family would be
# large enough that digits are the honest form anyway, and a count the check
# cannot parse FAILS rather than passing silently.
#
# WHAT IT DOES NOT DO
#
# It does not grade the inventory's `Lines` or `Commits` columns. Those are
# `wc -l` and `git log` readings taken at the commit that wrote each row --
# the file says so -- and they move on every edit to any checker. Grading
# them would make the inventory churn on changes that do not touch what it
# is for, which is the set of checkers and what each one reads.
#
# It does not grade each row's `Reads`, `Class` or `Decision` cell. Those are
# the judgements #699 ratified; a check that re-derived them would be grading
# its own model of the work, not the work.
#
# It does not decide whether a checker SHOULD read the proposal. Rule 4
# re-derives how many do, not how many ought to.
#
# Usage: docs/lib/check-claim-checker-inventory.sh
# Exit codes: 0 the family is non-empty, the inventory states its size and
#               carries exactly one row per member, and the proposal states
#               both derived counts,
#             1 the family is empty or undiscoverable, a stated count differs
#               from the derived one, the inventory's rows and the family
#               differ in either direction, a graded sentence is missing, or
#               a graded file is missing.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" <<'PY'
import glob
import os
import re
import sys

repo_root = sys.argv[1]
os.chdir(repo_root)

#: The pathspec that defines the family. Identical to FAMILY_PATHSPEC in
#: sim/tests/test_check_script_invocability.py on purpose: two guards that
#: disagreed about what a checker is would each be right about a different
#: set.
FAMILY_PATHSPEC = "*/lib/check-*.sh"

INVENTORY = "docs/claim-checker-inventory.md"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"

#: Counts up to thirty, as either document writes them. See NUMBER FORMS.
WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "twenty-one": 21, "twenty-two": 22, "twenty-three": 23,
    "twenty-four": 24, "twenty-five": 25, "twenty-six": 26,
    "twenty-seven": 27, "twenty-eight": 28, "twenty-nine": 29, "thirty": 30,
}
COUNT = r"(\d{1,3}|[A-Za-z]+(?:-[A-Za-z]+)?)"

#: Rule 2's selector: the sentence is found by the pathspec it quotes, so the
#: prose around the number is free to change and the number is not.
INVENTORY_TOTAL = re.compile(
    r"there\s+are\s+" + COUNT + r"\s*\n?\s*`\*/lib/check-\*\.sh`\s+scripts",
    re.IGNORECASE,
)

#: Rule 3's row shape: the first cell of a table row, a backticked path.
INVENTORY_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)

#: Rule 4's selector. Anchored on the claim itself rather than on any
#: surrounding wording, and spanning a line break because the document is
#: hard-wrapped.
PROPOSAL_COUNTS = re.compile(
    COUNT + r"\s+of\s+this\s+repository's\s*\n?\s*" + COUNT
    + r"\s+claim\s+checkers\s*\n?\s*read\s+this\s+document",
    re.IGNORECASE,
)

failures = []


def fail(message):
    failures.append(message)


def parse_count(token):
    """Return the integer a graded count token names, or None."""
    if token.isdigit():
        return int(token)
    return WORDS.get(token.lower())


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        fail("%s could not be read, so the claims in it could not be graded "
             "(%s)" % (path, exc))
        return None


def grade_count(token, derived, where, subject):
    """Grade one stated count against the value re-derived from the tree."""
    stated = parse_count(token)
    if stated is None:
        fail("%s writes %s as \"%s\", which this check cannot read as a "
             "number -- write it as digits or as an English word up to "
             "thirty, because a count that cannot be parsed cannot be graded"
             % (where, subject, token))
        return
    if stated != derived:
        fail("%s says %s is \"%s\" (%d); the tree has %d. The inventory is "
             "re-derived on every run -- update the document, not this check"
             % (where, subject, token, stated, derived))


# ---------------------------------------------------------------- rule 1
family = sorted(glob.glob(FAMILY_PATHSPEC))
if not family:
    sys.stderr.write(
        "FAIL: pathspec %r matched no checker. Either the family moved or "
        "this guard stopped covering it -- both are regressions, not a pass; "
        "a guard that examined nothing reports what a clean one reports.\n"
        % FAMILY_PATHSPEC)
    sys.exit(1)


def delegated_sources(script):
    """The script's own text, plus any `.py` sibling it hands its logic to.

    `sim/lib/check-artifact-manifests.sh` is a twelve-line entry point that
    `exec`s `check_artifact_manifests.py`; grading only the wrapper would
    report that it reads nothing. So a sibling named in the script, in the
    same directory, is read with it.
    """
    text = read(script)
    if text is None:
        return ""
    directory = os.path.dirname(script)
    for name in sorted(set(re.findall(r"[\w./-]+\.py", text))):
        sibling = os.path.join(directory, os.path.basename(name))
        if os.path.isfile(sibling):
            extra = read(sibling)
            if extra:
                text += "\n" + extra
    return text


readers = [s for s in family if PROPOSAL in delegated_sources(s)]

# ---------------------------------------------------------------- rule 2
inventory = read(INVENTORY)
if inventory is not None:
    match = INVENTORY_TOTAL.search(inventory)
    if not match:
        fail("%s no longer states the size of the `%s` family. The sentence "
             "is this file's reason for existing -- deleting it is not how a "
             "stale count is fixed" % (INVENTORY, FAMILY_PATHSPEC))
    else:
        grade_count(match.group(1), len(family), INVENTORY,
                    "the number of `%s` scripts" % FAMILY_PATHSPEC)

    # ------------------------------------------------------------ rule 3
    rows = [r for r in INVENTORY_ROW.findall(inventory) if r.endswith(".sh")]
    listed, duplicated = set(), sorted({r for r in rows if rows.count(r) > 1})
    listed.update(rows)
    for path in duplicated:
        fail("%s carries more than one row for `%s`, so its row count and "
             "the family can agree while naming different sets"
             % (INVENTORY, path))
    for path in sorted(set(family) - listed):
        fail("%s has no row for `%s`, which is in the tree. A checker that "
             "is wired, tested and absent from the inventory is invisible to "
             "the reader the inventory is for" % (INVENTORY, path))
    for path in sorted(listed - set(family)):
        fail("%s carries a row for `%s`, which the tree does not have"
             % (INVENTORY, path))

# ---------------------------------------------------------------- rule 4
proposal = read(PROPOSAL)
if proposal is not None:
    match = PROPOSAL_COUNTS.search(proposal)
    if not match:
        fail("%s no longer states how many of this repository's claim "
             "checkers read it. Deleting the sentence is not how a stale "
             "count is fixed: a claim this repository will not grade is a "
             "claim it should not print" % PROPOSAL)
    else:
        grade_count(match.group(1), len(readers), PROPOSAL,
                    "the number of checkers that read it")
        grade_count(match.group(2), len(family), PROPOSAL,
                    "the size of the checker family")

if failures:
    for message in failures:
        sys.stderr.write("FAIL: %s\n" % message)
    sys.stderr.write("FAIL: %d claim-checker inventory problem(s)\n"
                     % len(failures))
    sys.exit(1)

print("OK: %d checker(s) match `%s`; %s states that total and carries one "
      "row for each; %d of them read %s, which states both counts."
      % (len(family), FAMILY_PATHSPEC, INVENTORY, len(readers), PROPOSAL))
sys.exit(0)
PY
