#!/usr/bin/env bash
#
# Fails if a row of spec/pll.md's summary table has no verdict in the
# Chipalooza proposal's target-specification table.
#
# WHY THIS EXISTS (issue #237)
#
# #237's acceptance criteria say it twice, in two different ways:
#
#   - "spec table with min/typ/max re-derived from sim/";
#   - "Every spec row states met/unmet against the brief; period-jitter's
#     zero-record status is either closed or explicitly marked unmet -- NOT
#     SILENTLY OMITTED from the table."
#
# The proposal is written to be emailed verbatim to an outside reader, so a
# spec row that never appears in it is invisible in exactly the way that
# criterion forbids: the reader cannot tell a row that was judged and met from
# a row nobody wrote down.
#
# That is not hypothetical. Found on 2026-09-24, and fixed in the commit that
# added this check: spec/pll.md's summary-table row 2, Reference input, had
# NO row in the proposal's section 5 at all. It is a row with real content to
# disclose -- its levels and edge-rate limits are `budget` (no sweep exists),
# it has a line of its own in spec/pll.md's "Verification owed" (#12), and it
# carries the reference-source-quality exclusion on which every jitter and
# spur number in section 5 rests ("every jitter and spur number in this file
# is the block's own contribution, measured or derived against an ideal
# reference"). None of that reached the outward-facing document; the signal
# appeared only as a pad-table line in section 2.2 describing what `REF` is.
#
# No existing check could see it. check-readme-status.sh grades README's
# counts; check-characterization-coverage.sh grades sim/CHARACTERIZATION.md's
# rows against the sim/ campaign tree; check-record-supersession.sh grades
# whether cited evidence is still current; check-layout-status-claims.sh
# grades layout claims. Every one of them grades something the document *has*.
# Only a rule anchored in spec/pll.md's own table can see a row the document
# does not have at all.
#
# THE RULES
#
# 1. COVERAGE. Every parameter row of spec/pll.md's "## Summary table" must be
#    named by at least one row of the proposal's section-5 table. A section-5
#    parameter cell names spec row S if it equals S or begins with S followed
#    by a separator -- so "Power, **closed-loop measured**" and "Lock time
#    (small-signal settling)" both count, which is how this document has
#    always split a spec row into several reported rows.
#
# 2. VERDICT. At least one of the rows covering a spec row must carry an
#    explicit verdict token -- MET, UNMET, PASS, FAIL, N/A or WAIVED -- in the
#    Verdict column. A row present but hedged into saying nothing is the same
#    omission with extra words.
#
#    "At least one of the covering rows", not "every covering row", is
#    deliberate, and it is the weakest rule that still catches the drift
#    above. Section 5 legitimately splits one spec row into a measured result
#    and a *condition imposed on the driving system* -- "Supply sensitivity --
#    AC (ripple) budget" is stated as "derived, conditional" because the 20 mV
#    pp ripple line is a condition, not an outcome, and forcing MET/UNMET onto
#    it would be false precision of exactly the kind CLAUDE.md's "no claim
#    without a testbench" forbids. What must never happen is a spec row on
#    which the whole document renders no verdict at all.
#
# 3. NO ORPHAN ROWS. Every section-5 parameter must name some spec row. This
#    is the other direction of rule 1: without it, renaming a spec row leaves
#    the proposal's stale row sitting there looking like coverage while the
#    renamed row silently goes unreported.
#
# Deleting a spec row silences rule 1 for it, and that is not a loophole:
# spec/pll.md is the ratified target specification, amended only through a
# decision record (CLAUDE.md: "agents do not relax the ratified spec to make
# results pass"), so a row leaving that table is a ratification act with its
# own paper trail -- not an edit a Builder makes to quiet a check.
#
# WHAT IT DOES NOT DO
#
# It does not read the verdict's *content*: it cannot tell a correct MET from
# an incorrect one, only a stated one from an absent one. Whether the numbers
# beside that verdict are the current evidence is check-record-supersession.sh's
# rule, and whether they are the current *counts* is the other two checks'.
#
# Usage: spec/lib/check-spec-row-coverage.sh
# Exit codes: 0 every spec summary-table row is reported with a verdict,
#             1 a row is omitted, a covered row carries no verdict, a
#             section-5 row names no spec row, a graded file is missing, or
#             either table fails to parse (a broken parser must not look like
#             a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SPEC="spec/pll.md"
PROPOSAL="docs/chipalooza/challenge-5-proposal.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${SPEC}" "${PROPOSAL}" <<'PY'
import os
import re
import sys

repo_root, spec_rel, proposal_rel = sys.argv[1], sys.argv[2], sys.argv[3]

#: The verdict vocabulary section 5 actually uses. Bounded by non-letters so
#: that "MET" does not match inside "UNMET" (both are listed anyway) and so
#: that an ordinary English word ending in "met" is not mistaken for a verdict.
VERDICT = re.compile(r"(?<![A-Za-z])(UNMET|MET|PASS|FAIL|N/A|WAIVED)(?![A-Za-z])")

#: A section-5 parameter names spec row S when it equals S or continues it
#: with a qualifier: "Power, **closed-loop measured**", "Lock time
#: (small-signal settling)", "Supply sensitivity -- AC (ripple) budget".
CONTINUES = re.compile(r"^\s*[,(:;-]")


def read(rel):
    path = os.path.join(repo_root, rel)
    if not os.path.isfile(path):
        sys.stderr.write("FAIL: %s does not exist\n" % rel)
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def normalize(cell):
    """Link text, no emphasis, no backticks, one dash, one space, casefolded."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = text.replace("*", "").replace("`", "")
    for dash in ("—", "–", "‒", "‑", "−"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def table_rows(block):
    """[[cell, ...]] for a GitHub-flavoured Markdown table, header included."""
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", line):
            continue
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def columns(header, wanted, where):
    """Index of each wanted column name, or None with a parse failure logged."""
    index = {}
    lowered = [normalize(c) for c in header]
    for name in wanted:
        if name not in lowered:
            sys.stderr.write(
                "FAIL: %s's table has no %r column (header reads: %s) -- this "
                "check cannot grade a table it cannot parse, and a parse "
                "failure is not a pass\n" % (where, name, " | ".join(header))
            )
            return None
        index[name] = lowered.index(name)
    return index


spec_text = read(spec_rel)
proposal_text = read(proposal_rel)
if spec_text is None or proposal_text is None:
    sys.exit(1)

spec_block = re.search(
    r"^## Summary table[^\n]*\n(.*?)(?=^#{1,2} )", spec_text, re.M | re.S
)
proposal_block = re.search(
    r"^## 5\.[^\n]*\n(.*?)(?=^## )", proposal_text, re.M | re.S
)
if spec_block is None:
    sys.stderr.write("FAIL: %s has no '## Summary table' section\n" % spec_rel)
    sys.exit(1)
if proposal_block is None:
    sys.stderr.write(
        "FAIL: %s has no '## 5.' section -- the target-specification table is "
        "what this check grades\n" % proposal_rel
    )
    sys.exit(1)

spec_rows = table_rows(spec_block.group(1))
proposal_rows = table_rows(proposal_block.group(1))

# Two data rows is not a threshold anyone should ever be near: this tree has 19
# spec rows and 26 section-5 rows. It exists so that a regex that silently
# stops matching reports a parser failure instead of a clean tree.
if len(spec_rows) < 3 or len(proposal_rows) < 3:
    sys.stderr.write(
        "FAIL: parsed %d row(s) from %s's summary table and %d from %s's "
        "section 5 -- too few to be real; the table format has changed under "
        "this check\n"
        % (len(spec_rows) - 1, spec_rel, len(proposal_rows) - 1, proposal_rel)
    )
    sys.exit(1)

spec_index = columns(spec_rows[0], ("parameter",), spec_rel)
proposal_index = columns(proposal_rows[0], ("parameter", "verdict"), proposal_rel)
if spec_index is None or proposal_index is None:
    sys.exit(1)

spec_params = []
for row in spec_rows[1:]:
    col = spec_index["parameter"]
    if col >= len(row):
        continue
    name = normalize(row[col])
    if name:
        spec_params.append((name, row[col].strip()))

proposal_entries = []
for row in proposal_rows[1:]:
    pcol, vcol = proposal_index["parameter"], proposal_index["verdict"]
    if pcol >= len(row) or vcol >= len(row):
        sys.stderr.write(
            "FAIL: %s section 5 has a row with %d cell(s), fewer than its own "
            "header declares: %s\n" % (proposal_rel, len(row), " | ".join(row))
        )
        sys.exit(1)
    proposal_entries.append(
        (normalize(row[pcol]), row[pcol].strip(), row[vcol])
    )

if not spec_params or not proposal_entries:
    sys.stderr.write(
        "FAIL: no data rows parsed (%d spec, %d section 5)\n"
        % (len(spec_params), len(proposal_entries))
    )
    sys.exit(1)


def covers(param, spec_name):
    if param == spec_name:
        return True
    if not param.startswith(spec_name):
        return False
    return bool(CONTINUES.match(param[len(spec_name):]))


failed = False

for spec_name, spec_raw in spec_params:
    covering = [e for e in proposal_entries if covers(e[0], spec_name)]
    if not covering:
        failed = True
        sys.stderr.write(
            "FAIL: %s's summary table row %r has no row in %s section 5. "
            "#237's acceptance criteria require every spec row to state "
            "met/unmet in that table rather than be silently omitted from "
            "it -- add the row with an honest verdict (UNMET is a verdict; "
            "absence is not)\n" % (spec_rel, spec_raw, proposal_rel)
        )
        continue
    if not any(VERDICT.search(e[2]) for e in covering):
        failed = True
        sys.stderr.write(
            "FAIL: %s section 5 reports %s's row %r (as %s) but states no "
            "verdict for it -- no MET/UNMET/PASS/FAIL/N/A/WAIVED appears in "
            "the Verdict column of any row covering it\n"
            % (
                proposal_rel,
                spec_rel,
                spec_raw,
                ", ".join(repr(e[1]) for e in covering),
            )
        )

for param, raw, _verdict in proposal_entries:
    if not any(covers(param, spec_name) for spec_name, _ in spec_params):
        failed = True
        sys.stderr.write(
            "FAIL: %s section 5 has a row %r naming no row of %s's summary "
            "table. Either the spec row was renamed (fix the section-5 row to "
            "match, so the renamed row is graded) or this row reports against "
            "a target that does not exist\n" % (proposal_rel, raw, spec_rel)
        )

if failed:
    sys.exit(1)

print(
    "OK: all %d rows of %s's summary table are reported with a verdict in %s "
    "section 5 (%d rows), and every section-5 row names a spec row"
    % (len(spec_params), spec_rel, proposal_rel, len(proposal_entries))
)
PY
