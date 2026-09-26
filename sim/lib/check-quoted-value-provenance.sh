#!/usr/bin/env bash
#
# Fails if a measured number quoted in the Chipalooza proposal's spec table is
# not the number the cited record's committed per-corner evidence produces.
#
# WHY THIS EXISTS (issue #237)
#
# Nine checks already grade docs/chipalooza/challenge-5-proposal.md. Every one
# of them grades something *about* a number rather than the number:
#
#   check-readme-status.sh            counts of records and campaigns
#   check-characterization-coverage.sh  the aggregation's rows
#   check-layout-status-claims.sh     layout claims and the area figures
#   check-record-supersession.sh      whether the cited record is current
#   check-spec-row-coverage.sh        whether every spec row is present
#   check-io-list-coverage.sh         the I/O list
#   check-port-connectivity.sh        what a netlist wires
#   check-pvt-coverage-claims.sh      WHICH GRID the number was measured on
#   check-ref-drive-claims.sh         the reproduction commands
#   check-bias-drive-claims.sh        the bias-pin drive and the Limitations
#   check-issue-reference-state.sh    the forge references
#
# So a row could cite the current record, name the right grid, carry the right
# verdict -- and quote a value that is not in that record at all, or was
# correct once and drifted when a superseding run moved it. Nothing would see
# it. The gap was named explicitly in #237's own builder ledger on 2026-09-25:
# "the largest remaining ungraded surface is the measured *value* itself --
# nothing checks that a number quoted in section 5 equals the number in the
# cited record's committed CSV." That ledger verified a sample by hand. A hand
# check is not a check; this is the machine one.
#
# THE CONVENTION IT ENFORCES (proposal section 5.1)
#
# Section 5.1 of the proposal carries four tables (the third is rule 7's, and
# arrived after this header was first written). The first names, for each
# graded value, the record, the committed evidence file, the reduction that
# produces it, and the unit scale:
#
#   | section 5 row | Quoted value | Record(s) | Evidence file | Reduction | Scale |
#   | Output band | `6.449 MHz` | `20260731-175947-0a12e6c` | `vco_tuning.csv` | `max(min(fosc_hz) by bundle+temp_c+vdd_v)` | `1e-6` |
#
# The second names every section 5 row for which no value is re-derived here,
# with the reason. Together they are exhaustive over section 5: a row in
# neither table fails this check. That is the same "nothing is silently
# omitted" rule #237's acceptance criterion 5 states for verdicts, applied to
# values.
#
# The third names the figures that are a reduction DIVIDED BY A RATIFIED
# LINE -- rule 7's, described there.
#
# The fourth names the headline figures INSIDE graded rows that are still not
# re-derived, and why:
#
#   | section 5 row | Figure | Why it is not re-derived |
#   | Kvco | 115.8 MHz/V | Selecting it evaluates the band-selection rule ... |
#
# That list used to be prose, and prose does not get graded: it named four
# figures and silently missed a fifth. Rule 6 below makes it an artefact CI
# maintains.
#
# THE RULES
#
# 1. RESOLVABLE. Every record id in the first table must resolve to a real
#    sim/*/records/<id>.md, and the named evidence must be committed. Two forms
#    of evidence are accepted, both committed and both reduced by the same
#    grammar:
#
#      <file>.csv              sim/<campaign>/corners/<id>/<file>, the usual
#                              case: a per-corner CSV the harness wrote.
#
#      <id>.md § <first-col>   the pipe table INSIDE that record whose first
#                              column is <first-col> -- for a campaign whose
#                              per-point table was committed only in the
#                              record's own Markdown. Three rows of section 5
#                              are graded this way, and all three were in the
#                              EXCLUSION table until 2026-09-26 for the reason
#                              "no reduced CSV was committed, so the count
#                              cannot be re-derived": sim/divider-ratio-chain's
#                              235-point ratio table, sim/output-range's 90-row
#                              closed-loop band-edge table, and sim/lock-time's
#                              270-row cold/relock table. All three had been
#                              committed all along. "No CSV" is not "no
#                              evidence", and that reading cost three rows of
#                              grading; this form exists so it cannot recur.
#
#                              A markdown table CAN be elided where a CSV
#                              cannot, so this form carries a correspondence
#                              rule a CSV does not need: the table must have
#                              exactly one row per committed per-corner log in
#                              sim/<campaign>/corners/<id>/ -- one row per
#                              simulation that ran. Where the table's first
#                              column is the per-corner point id (some records
#                              write one; others head it `Corner` and split the
#                              corner over several columns) the row SETS are
#                              compared as well, which additionally catches a
#                              duplicated or mistyped row at the right count.
#                              Which tables got the stricter rule is printed in
#                              the OK line -- the weaker one is never applied
#                              silently.
#
#    A reduction over evidence that is not committed is not reproducible by a
#    reader.
#
# 2. CITED. Every record a section 5.1 entry reduces must be cited by the
#    section 5 row it is attached to -- or, where that row's Source cell says
#    "Same record", by the nearest preceding row that names one. Section 5.1
#    may not smuggle in evidence the row itself does not point a reader at.
#
# 3. PRESENT. The quoted value string must appear verbatim in that section 5
#    row's own cells. This is what stops the two tables from drifting apart:
#    editing a number in section 5 and not in section 5.1 fails here, in
#    either direction.
#
# 4. CORRECT. The value, re-derived from the committed evidence by the stated
#    reduction and scaled, must equal the quoted figure ROUNDED HALF-UP TO THE
#    PRECISION AS WRITTEN. `247.8 MHz` against a derived 247.751 passes;
#    against 247.6 it fails. Counts must match exactly. Precision-as-written
#    is the rule rather than a fixed tolerance because it is the rule a reader
#    applies: a figure printed to one decimal claims one decimal.
#
# 5. EXHAUSTIVE OVER ROWS. Every row of the section 5 table must appear in the
#    first table (at least one graded value) or the second (a stated reason),
#    and never in both.
#
# 6. DISCLOSED PER FIGURE, AND NOT STALE. Rule 5 is per row, not per number: a
#    graded row can still hold a headline figure nothing re-derives. Section
#    5.1's fourth table names each of those, and this check requires that each
#    entry names a real section 5 row, that the row is one this check grades
#    (a fully excluded row's figures are the exclusion table's business), that
#    the figure is not also a graded value for that row, that a reason is
#    given -- and that the figure STILL APPEARS VERBATIM in the row. That last
#    rule is the one with teeth: before it existed the list was prose, and it
#    had already gone wrong. It named four ungraded figures and missed a fifth
#    (the output band row's `27 %` worst adjacent-band overlap, which was
#    neither graded nor disclosed until it was graded in this pass).
#
# 7. DERIVED AGAINST A RATIFIED LINE. Some headline figures are not a reduction
#    of committed evidence at all: they are a reduction COMBINED WITH A
#    CONSTANT THAT IS WRITTEN DOWN IN A NORMATIVE DOCUMENT. `1.41x` is the
#    worst measured VCTRL travel over the 0.6 V Budget 2 allows; `47 %` is the
#    same travel over the 1.8 V width of DR-003 Decision 5's measured control
#    window. Both sat in the ungraded list until 2026-09-26 for the reason "a
#    ratio to a spec line is arithmetic on the line, not a column of the
#    committed evidence" -- true about the column and wrong about the
#    conclusion, in exactly the way section 5.2 had already shown for the spur
#    derivation: a hand derivation is not ungradeable when every ingredient it
#    uses is written down. Here both ingredients are. The measured one is a
#    reduction this check already evaluates; the ratified one is a line in
#    spec/pll.md.
#
#    TWO OPERATORS, because two shapes of figure say "against the line". A
#    RATIO (`/`) answers "how many times the allowance", which is what a budget
#    row states. A DISTANCE (`-`) answers "how far past the line", which is what
#    a dBc row states: the reference spur's two cold corners are `0.5 dB` and
#    `0.1 dB` over the ratified -55 dBc, which is -54.51 and -54.88 minus the
#    line. Before 2026-09-26 the table divided and only divided, so section 5
#    wrote that pair as the RANGE `0.1-0.5 dB` and the ungraded list had to
#    decline it -- not for want of evidence (both ends were already graded as
#    dBc values in the first table) but because a range is not a figure. The
#    operator is what let section 5 write the two ends as two figures.
#
#    A THIRD TABLE in section 5.1 carries them:
#
#      | section 5 row | Quoted value | Record(s) | Evidence file | Derivation | Constant | Scale |
#      | Supply sensitivity -- DC ... | `1.41x` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `max(span_full_v) / budget2-vctrl-consumption-v` | `0.6 V` | `1` |
#      | Reference spur | `0.5 dB` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `max(spur_dbc_at_200mhz) - reference-spur-line-dbc` | `-55 dBc` | `1` |
#
#    Rules 1-5 apply to it unchanged -- the record must resolve and be cited by
#    the row, the evidence must be committed, the figure must appear verbatim
#    in the row, and a row graded here counts as graded for rule 5. On top of
#    those:
#
#      a. THE CONSTANT IS READ, NEVER WRITTEN INTO THIS CHECK. The name in the
#         derivation resolves through the CONSTANTS registry below, which
#         reads the value out of spec/pll.md (and, where the spec cites one,
#         out of that decision record), for the same reason the Icp trim rule
#         is read rather than asserted: a re-ratified line has to fail this
#         check in the same commit, not be graded against the superseded one.
#
#      b. EVERY STATEMENT OF THE CONSTANT MUST AGREE. Each resolver requires
#         at least two independent statements of its line and fails if they
#         differ. Budget 2's 0.6 V is stated twice in spec/pll.md (the spec
#         table's row 12 and the Budget 2 section heading); the 0.9-2.7 V
#         control window is stated in spec/pll.md's ratified assumptions and
#         in DR-003 Decision 5, which that section 5 row cites; the -55 dBc
#         spur line is stated in the spec table's row 7 target cell and again
#         as the `**Target:**` line of the '## Reference spur' section that
#         derives it. A document that contradicts itself about a ratified
#         number is a failure here rather than a coin toss over which
#         statement the check happened to match first.
#
#      c. THE TABLE'S OWN STATEMENT OF THE CONSTANT IS GRADED TOO. The
#         Constant column is what a reader checks the arithmetic with, so it
#         is compared against the resolved value at the precision written. It
#         is not an input -- the derivation uses the resolved value.
#
#      d. NO COUNT AS THE MEASURED OPERAND. A count over a ratified voltage is
#         not a ratio, and a count minus a ratified line is not a distance; if
#         a figure ever needs either, it needs a stated reason first.
#
#      e. A CONSTANT THAT READS AS ZERO IS A FAILED READ, not a datum. Nothing
#         normative in this specification is a zero, so a resolver returning
#         one means its regex stopped matching the document. That is rejected
#         for both operators, even though subtracting zero would be harmless
#         arithmetic: a silently-zero line would grade `-54.51 - 0` as the
#         distance from the line and report -54.51 dB of overshoot as if it
#         were evidence.
#
#    And one guard shared with rule 4, which is what makes the remaining
#    entries in the ungraded list honest: A RANGE IS NOT A FIGURE. The quoted
#    value may not be a two-ended range (`0.1-0.5 dB`, `0.385 ... 0.846 V`),
#    because the figure parser reads the number at the front and would grade
#    the low end alone -- "grading half of a two-sided bound and calling it
#    the bound" is the named defect the ungraded list exists to catch, and
#    before this guard the check would have committed it silently. The guard
#    is not a way of declining work: `0.1-0.5 dB` was refused by it on
#    2026-09-26 and graded the same day, as two entries, once section 5 wrote
#    the two ends as two figures. Refusing the shape is what made the rewrite
#    necessary, not what made the figure ungradeable.
#
# WHAT IT DOES NOT DO
#
# Rule 6 makes the ungraded-figure list non-rotting, not complete: nothing can
# mechanically enumerate "every headline figure" out of section 5's prose
# cells, which quote hundreds of numbers, most of them commentary on a figure
# rather than a figure. So completeness of that list remains a reviewer's job,
# and this check's own coverage claim is per row (rule 5) plus per disclosed
# figure (rule 6) -- never "every number in section 5 is accounted for".
# Overstating it would be the same defect this check exists to catch.
#
# It reduces committed *reduced* evidence only -- a per-corner CSV, or a
# per-point table committed inside a record (rule 1). It never runs a simulator
# and never parses a logfile's contents: the per-corner logs are read only as
# NAMES, to prove a markdown table has one row per simulation that ran. So it
# cannot tell whether the simulation behind a number was the right experiment --
# that is what the record's own Methodology field and its campaign's testbench
# are for.
#
# THE REDUCTION GRAMMAR
#
#   min(COL) | max(COL) | mean(COL) | sum(COL)      over every row
#   AGG(AGG(COL) by KEY[+KEY...])                   inner aggregate per group,
#                                                   outer over the groups
#   count(rows)                                     row count
#   count(distinct KEY[+KEY...])                    distinct key count
#
# plus two GROUP-SEQUENCE derivations, for figures that are a property of an
# ordered curve rather than a reduction of cells (these take no where-clause):
#
#   count(non-monotonic(COL by AXIS) by KEY[+KEY...])
#       How many groups' COL sequence, ordered by AXIS, is neither
#       non-decreasing nor non-increasing -- "monotonic" as the document
#       writes it, in either direction, ties allowed. A group with fewer than
#       two points, or with a repeated AXIS value, is an error rather than a
#       pass: the figure this grades is a zero, so a test that quietly
#       examined nothing would report exactly what a clean grid reports. The
#       OK line therefore prints how many groups were examined.
#
#   min|max|mean|sum|sig3(adjacent-overlap(COL by AXIS) by KEY[+KEY...])
#       Per group, the worst (smallest) fractional overlap between the COL
#       interval at AXIS and the one at AXIS+1: max(COL at k) / min(COL at
#       k+1) - 1, where negative is a hole rather than an overlap. The pairing
#       is AXIS with AXIS+1 -- NOT "the next AXIS value in sort order" -- so
#       AXIS must be integer-coded and spaced by exactly 1 (`band` is), and
#       two things are errors rather than passes. A group holding no such pair
#       at all has no adjacent interval to overlap. And a group whose AXIS run
#       has a HOLE in it (`0, 1, 3`) would be examined over one pair while
#       looking like it was examined over two -- the same "quietly examined
#       less than it looks like" failure the anti-vacuity treatment of
#       count(non-monotonic(...)) above refuses, and just as invisible in a
#       worst case as it is in a zero. The OK line therefore prints how many
#       adjacent pairs were examined alongside the group count.
#
#   min|max|mean|sum|sig3(worst-magnitude(COL by AXIS) by KEY[+KEY...])
#       Per group, the SIGNED COL value of the point with the largest
#       magnitude across AXIS -- the "worst point in the window" selection
#       sim/cp-compliance and sim/mc-cp-mismatch both use, which compares
#       magnitudes to pick the point and then keeps that point's sign. Two
#       points tying on magnitude with opposite signs is an error, not a
#       coin toss.
#
# plus two AGGREGATES THAT ARE NOT EXTREMA, which compose with everything
# above because they are aggregates rather than verbs:
#
#   sig3(COL)   `|mean| + 3*sigma` over the selected values, with sigma the
#               SAMPLE standard deviation (N-1). Fewer than two values is an
#               error: a one-sample "3 sigma" is not a tail, it is a reading.
#
#   maxmag(COL) `max(|v|)` -- a TWO-SIDED bound over a signed column.
#               `max()` over such a column returns its positive end and
#               `min()` its negative one, and a figure written "to within
#               5.7 mV at every cell" claims BOTH ends at once. Until this
#               aggregate existed, section 5.1's ungraded list carried exactly
#               that figure with exactly that reason -- "the grammar has no
#               magnitude aggregate ... grading half of a two-sided bound and
#               calling it the bound is the defect this table exists to
#               catch". Two guards, one present and one deliberately absent:
#
#                 Fewer than two values is an error, for sig3's reason rather
#                 than a statistical one -- the figures a magnitude bound
#                 grades are stated OVER A SET ("at every cell"), and a bound
#                 over a single value is that value.
#
#                 worst-magnitude's opposite-sign tie is NOT an error here.
#                 That verb KEEPS the selected point's sign, so +x against -x
#                 is a coin toss; this aggregate discards the sign, so both
#                 ties give the same answer and there is nothing to be
#                 ambiguous about. A guard copied without its reason would
#                 reject a document that is not wrong.
#
#               A magnitude bound is silent about the sign it was taken over
#               in the same way a worst overlap is silent about how many
#               intervals it beat: `5.7` alone cannot tell a reader whether
#               the set ever had two sides. So the OK line prints how many
#               signed values each bound covered AND how many of them fell on
#               the far side of zero from the binding end -- which is the
#               evidence that this is a two-sided bound rather than a `max()`
#               in different clothing.
#
# THE THREE-LEVEL FORM, and why it exists
#
#   AGG(AGG(VERB(COL by AXIS) by KEY[+KEY...]) by KEY[+KEY...])
#       Outer groups, each sub-grouped again, each sub-group's sequence
#       reduced by VERB. The statistic that needs it is DR-018's term 1, the
#       charge pump's UP/DN current mismatch: per Monte Carlo sample the
#       worst-magnitude of three Vctrl points, then `|mean| + 3*sigma` over
#       the samples of one corner, then the worst corner --
#
#         max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)
#
#       which is three nested reductions because the statistic is: a
#       selection, a tail, and a worst case. Collapsing any level (pooling
#       corners, folding the samples to their magnitudes) gives a DIFFERENT
#       and smaller number -- 10.94 % pooled and 13.2172 % folded against
#       17.4798 % -- which is exactly why DR-018 Decision 3 names the
#       statistic rather than describing it, and why this grammar spells it
#       out instead of hiding it in a verb.
#
#       SECOND IMPLEMENTATION -- KEEP THEM IN AGREEMENT.
#       `spec/lib/check-mismatch-charge-derivation.sh` (rule 2) computes this
#       same statistic from this same `mc_cp_dc.csv` in its own hard-coded
#       arithmetic rather than through this grammar, because it needs the
#       number as an ingredient of spec/pll.md's charge-accounting totals.
#       Neither check subsumes the other -- that one asks whether the CHARGE
#       TOTALS still follow from their samples, this one asks whether a
#       PERCENTAGE QUOTED IN SECTION 5's PROSE is a reduction of committed
#       evidence at all -- but they must not disagree. If the selection
#       convention, the sample-sd (N-1) convention, the nesting order, or the
#       signed-vs-folded reading moves in one, move it in the other and re-run
#       both. Two routes to one number is what makes a silent drift loud.
#
# any of which may carry ` where COND[ and COND...]`, where COND is
# `COL OP LITERAL` with OP one of == != < <= > >= ~=. A literal that parses as a
# number is compared numerically, otherwise as a string (== and != only). COL
# may contain a space or a hyphen -- a record's own tables head their columns
# `DN guard` and `corner-id`.
#
# `~=` is the one operator that is not a comparison: it is SUBSTRING
# CONTAINMENT, always on the cell's text, never numeric. It exists because a
# per-point evidence table's only handle on a swept axis can be the point id
# itself -- sim/divider-ratio-chain's per-point table has a `corner-id` of
# `ss_125c_2.97v_f200n04` and no separate input-rate column, so "the divide
# ratios exercised AT 200 MHz" is `where corner-id ~= f200` and nothing else.
# Grading that figure without the filter would count the 10 MHz points too;
# they happen to reuse N in {4, 64} today, so the count would be right by
# accident and would go wrong silently the first time a bottom-of-band point
# added an N the 200 MHz sweep does not have.
#
# One named predicate is available in a where clause:
#
#   on-icp-trim-rule   the row's (f_ref_hz, trim_units) is the pairing
#                      spec/pll.md's normative "Icp trim-code rule" table
#                      requires.
#
# That predicate is READ OUT OF spec/pll.md, never written into this check, for
# the same reason check-pvt-coverage-claims.sh computes the mandated grid size
# from the harness: the proposal's loop-bandwidth, phase-margin and settling
# figures are stated over "the contracted (trim-rule) space", so if the
# ratified rule changes, what CI enforces has to change in the same commit.
#
# EVERY COLUMN A REDUCTION NAMES MUST EXIST IN ITS EVIDENCE
#
# A reduction that names a column its evidence does not have fails here, before
# any row is reduced, naming the column, the evidence source, and the columns
# that source DOES have -- so a renamed or mistyped column is a one-line
# diagnosis rather than a hunt.
#
# That is a rule and not a nicety, because the natural behaviour of a filter
# over a column that does not exist is to match NOTHING, and zero is a
# legitimate value for the figures this check grades -- the most load-bearing
# one it grades. `0 of 45 corners` and `0 ratio errors of 235 chain points` are
# both `count(rows where COL ...)`. Mistype `Status` in
# `count(rows where Status == PASS)` and the reduction returns 0, equals the
# quoted 0, and prints OK: a green check asserting a number it never computed,
# which is the precise failure the whole convention exists to prevent, one
# level up (issue #579). `!=` fails the same way in the other direction -- a
# missing column turns `count(rows where COL != X)` from the row count into a
# zero.
#
# Every column-consuming position is covered, including the two that are not
# written in the reduction at all:
#
#   where COL OP LITERAL            the filtered column
#   AGG(COL)                        the aggregated column, at either level
#   ... by KEY[+KEY...]             the group keys, at either level
#   count(distinct KEY[+KEY...])    the distinct keys
#   VERB(COL by AXIS)               a sequence verb's value and axis columns
#   on-icp-trim-rule                `f_ref_hz` and `trim_units`, which the
#                                   predicate reads implicitly -- and an
#                                   implicit column name is exactly the kind
#                                   that goes missing without anyone editing
#                                   the reduction that depends on it
#
# A column must be present in EVERY row an entry reduces, not merely in one:
# an entry may name several records (the closed-loop period-jitter figures
# reduce six), and a name only some of them carry would silently reduce a
# subset of the evidence.
#
# Usage: sim/lib/check-quoted-value-provenance.sh
# Exit codes: 0 every graded value re-derives, every derived figure follows
#             from its reduction and its ratified constant, every section 5 row
#             is accounted for, and every disclosed ungraded figure is still in
#             its row;
#             1 any rule above is violated, a table is missing or empty, or the
#             section 5 table cannot be parsed (a broken parser must not look
#             like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PROPOSAL="docs/chipalooza/challenge-5-proposal.md"
SPEC="spec/pll.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${PROPOSAL}" "${SPEC}" <<'PY'
import csv
import math
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

repo_root, proposal_rel, spec_rel = sys.argv[1], sys.argv[2], sys.argv[3]

RECORD_ID = r"\d{8}-\d{6}-[0-9a-f]{7}"

# Two data rows is not a threshold anyone should ever be near -- this tree has
# 27 -- and it is deliberately not set near the real count, for the same reason
# check-spec-row-coverage.sh gives: the guard exists so that a regex which
# silently stops matching reports a parser failure instead of a clean tree, not
# as a second copy of the row count. The real count is asserted from the other
# side, by sim/tests/test_quoted_value_provenance.py, which re-parses section 5
# independently and fails if this check reports a different number of rows.
MIN_SPEC_ROWS = 3

errors = []


def fail(msg):
    errors.append(msg)


# ---------------------------------------------------------------- markdown ---

def normalize_row_name(text):
    """A section 5 row name, comparable between the two tables.

    Section 5's own Parameter cells carry bold markers and non-breaking
    spellings that section 5.1 should not have to reproduce byte for byte.
    Strip emphasis and collapse whitespace; keep everything else, including
    the em dashes that distinguish the two supply-sensitivity rows.
    """
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_tables(text):
    """Every pipe table in a document, as (header_cells, [row_cells...])."""
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        header = split_row(lines[i])
        if i + 1 >= len(lines) or not re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]
        ):
            i += 1
            continue
        body = []
        j = i + 2
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            body.append(split_row(lines[j]))
            j += 1
        tables.append((header, body))
        i = j
    return tables


# ------------------------------------------------------------------ numbers ---

NUMBER = re.compile(r"^([+-]?\d+(?:\.\d+)?)(?:[eE]([+-]?\d+))?")

#: A two-ended range, which is NOT a figure this check may grade.
#:
#: `parse_quoted` reads the number at the front of the string, so `0.1-0.5 dB`
#: would be graded as `0.1` and the other end of the bound would never be
#: looked at -- "grading half of a two-sided bound and calling it the bound",
#: which is the defect section 5.1's ungraded list exists to make visible. The
#: separator must be followed by a digit so that a figure whose UNITS carry a
#: hyphen is untouched: `45-point PVT grid` and `0 non-monotonic curves of 504`
#: are figures, `2.255e-4` is a figure, `0.385 ... 0.846 V` is a range.
RANGE_FIGURE = re.compile(
    r"^\s*[+\-−]?\d[\d.]*\s*(?:[–—−-]|\.\.\.|…)\s*"
    r"[+\-−]?\d"
)


#: A rule-7 derivation: one reduction, one named operator, one ratified
#: constant.
#:
#: The operator must carry whitespace on BOTH sides. That is not cosmetic: a
#: where-clause inside the reduction can hold a negative literal
#: (`where temp_c == -40`), which has a space before its minus sign and none
#: after, so requiring both keeps a filter from being read as the subtraction.
#: The constant is an identifier, anchored to the end of the cell, which is
#: what makes the non-greedy reduction split at the operator rather than
#: inside the constant's own hyphens (`reference-spur-line-dbc`).
DERIVATION = re.compile(
    r"^(?P<reduction>.+?)\s+(?P<op>[/-])\s+(?P<constant>[A-Za-z][\w.-]*)$"
)


def is_range_figure(raw):
    return bool(RANGE_FIGURE.match(raw.strip().strip("`").strip()))


def parse_quoted(raw):
    """A quoted figure -> (Decimal mantissa, exponent, decimals as written).

    U+2212 MINUS SIGN is what this document actually uses in front of a
    negative dBc or ppm figure; treating it as text would make every negative
    row unreadable to this check.
    """
    s = raw.strip().strip("`").strip()
    s = s.replace("−", "-").replace("–", "-").replace(" ", " ")
    s = s.replace(",", "")
    m = NUMBER.match(s)
    if not m:
        return None
    mantissa, exp = m.group(1), int(m.group(2) or 0)
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    return Decimal(mantissa), exp, decimals


def rounds_to(derived, mantissa, exp, decimals):
    """Does `derived` print as the quoted figure at the precision written?"""
    try:
        d = Decimal(repr(float(derived)))
    except (InvalidOperation, ValueError, OverflowError):
        return False
    if exp:
        d = d / (Decimal(10) ** exp)
    quantum = Decimal(1).scaleb(-decimals)
    return d.quantize(quantum, rounding=ROUND_HALF_UP) == mantissa.quantize(
        quantum, rounding=ROUND_HALF_UP
    )


def as_float(cell):
    try:
        return float(str(cell).strip())
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------- the Icp trim rule ---

def read_icp_trim_rule(spec_text):
    """{f_ref_hz: required trim unit legs}, read out of spec/pll.md.

    The normative table's first column is a frequency with a unit ("1 MHz")
    and its second is the required code in bold ("**4**").
    """
    section = re.search(
        r"^## Icp trim-code rule\s*$(.*?)(?=^## |\Z)",
        spec_text,
        re.MULTILINE | re.DOTALL,
    )
    if not section:
        return {}
    rule = {}
    for header, body in read_tables(section.group(1)):
        if not header or not header[0].lower().startswith("f_ref"):
            continue
        for cells in body:
            if len(cells) < 2:
                continue
            fm = re.match(
                r"^\s*([\d.]+)\s*([kMG]?)Hz\s*$", cells[0].replace("`", "")
            )
            tm = re.search(r"(\d+)", cells[1])
            if not fm or not tm:
                continue
            mult = {"": 1, "k": 1e3, "M": 1e6, "G": 1e9}[fm.group(2)]
            rule[float(fm.group(1)) * mult] = int(tm.group(1))
    return rule


# ------------------------------------------------------ the ratified lines ---
#
# The constants a rule-7 derivation may divide by. Each resolver returns
# (value, [(where it was read, value as stated), ...]) and is required to find
# the line stated at least TWICE, in independent places, and to find the
# statements in agreement. That is not belt-and-braces: a ratified number that
# two sections of the spec disagree about is a spec defect, and a check that
# matched whichever statement came first in the file would hide it behind a
# figure that still "grades".
#
# Nothing here writes a number into this check. Every value is a capture group
# out of a committed document, for the same reason read_icp_trim_rule is: when
# a line is re-ratified, this check has to fail in the same commit rather than
# keep grading the superseded one.

class ConstantError(ValueError):
    """A ratified constant that could not be read, or that disagrees."""


def _one_agreed_value(label, readings):
    """[(where, value)] -> the value, if there are >= 2 and they agree."""
    if len(readings) < 2:
        raise ConstantError(
            "%s: found %d statement(s) of this ratified line, and at least 2 "
            "independent ones are required (%s). A constant read from one "
            "place is a constant nothing corroborates."
            % (label, len(readings), "; ".join(w for w, _ in readings) or "none")
        )
    values = {round(v, 12) for _, v in readings}
    if len(values) > 1:
        raise ConstantError(
            "%s: the ratified line is stated inconsistently -- %s. Which one "
            "governs is a spec question, not this check's to pick."
            % (label, "; ".join("%s says %g" % (w, v) for w, v in readings))
        )
    return readings[0][1]


def read_budget2_consumption_v(docs):
    """Budget 2's allowance, in volts of the VCTRL window (spec/pll.md).

    Stated twice: in the spec table's Supply sensitivity target cell and in
    the `Budget 2 -- DC` section heading that derives it.
    """
    readings = [
        ("%s statement %d" % (spec_rel, i + 1), float(m))
        for i, m in enumerate(
            re.findall(
                r"must consume ≤\s*([\d.]+)\s*V of the Vctrl window",
                docs["spec"],
            )
        )
    ]
    return _one_agreed_value("budget2-vctrl-consumption-v", readings), readings


def _window_readings(docs):
    out = []
    m = re.search(
        r"Vctrl operating window \*\*([\d.]+)\s*[–-]\s*([\d.]+)\s*V\*\*",
        docs["spec"],
    )
    if m:
        out.append(("%s (ratified assumptions)" % spec_rel,
                    (float(m.group(1)), float(m.group(2)))))
    m = re.search(
        r"usable Vctrl window is \*{0,2}([\d.]+)\s*[–-]\s*([\d.]+)\s*V",
        docs.get("dr003", ""),
    )
    if m:
        out.append(("DR-003 Decision 5",
                    (float(m.group(1)), float(m.group(2)))))
    return out


def read_dr003_window_width_v(docs):
    """The width of DR-003 Decision 5's measured 0.9-2.7 V control window.

    The WIDTH is nowhere a primary number -- the window is ratified by its two
    ends, so the width is derived from them here rather than matched against
    the "1.8 V wide" the spec writes in passing. Reading the ends from both
    spec/pll.md and the decision record it cites is what makes the derivation
    safe: the proposal's own section 5 row cites DR-003 Decision 5, so a
    divergence between the two documents is a divergence this figure rests on.
    """
    readings = _window_readings(docs)
    widths = [(where, hi - lo) for where, (lo, hi) in readings]
    ends = [(where, lo) for where, (lo, _) in readings]
    _one_agreed_value("dr003-vctrl-window-width-v (window floor)", ends)
    return _one_agreed_value("dr003-vctrl-window-width-v", widths), widths


def read_reference_spur_line_dbc(docs):
    """The ratified reference-spur line, in dBc (spec/pll.md).

    Stated twice, independently, and both statements are required to agree:
    in the summary table's Reference spur target cell, and as the `**Target:**`
    line of the `## Reference spur` section that derives it -- the same
    two-places shape Budget 2's allowance is read in.

    The target cell is located by the ROW that links to the section
    (`[Reference spur](#reference-spur)`) and then by the cell AFTER the link,
    required to be nothing but the line. spec/pll.md's "Verification owed"
    table carries a row that links to the same section, so a looser match would
    read an owner cell as a target; requiring the whole cell to be `<= <x> dBc`
    is what keeps the two apart.
    """
    spec = docs["spec"]
    readings = []
    for line in spec.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "(#reference-spur)" not in stripped:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        for i, cell in enumerate(cells[:-1]):
            if "(#reference-spur)" not in cell:
                continue
            target = cells[i + 1].replace("−", "-").replace("–", "-")
            m = re.match(r"^(?:≤|<=)\s*([+-]?\d+(?:\.\d+)?)\s*dBc$", target)
            if m:
                readings.append(
                    ("%s summary-table target cell" % spec_rel, float(m.group(1)))
                )
    section = re.search(
        r"^## Reference spur[^\n]*\n(.*?)(?=^## )", spec, re.M | re.S
    )
    if section is not None:
        m = re.search(
            r"\*\*Target:\s*(?:≤|<=)\s*([+-]?\d+(?:\.\d+)?)\s*dBc\*\*",
            section.group(1).replace("−", "-").replace("–", "-"),
        )
        if m:
            readings.append(
                ("%s '## Reference spur' target line" % spec_rel, float(m.group(1)))
            )
    return _one_agreed_value("reference-spur-line-dbc", readings), readings


CONSTANTS = {
    "budget2-vctrl-consumption-v": read_budget2_consumption_v,
    "dr003-vctrl-window-width-v": read_dr003_window_width_v,
    "reference-spur-line-dbc": read_reference_spur_line_dbc,
}


# ----------------------------------------------------------- the evidence ---

class Evidence:
    """The rows one section 5.1 entry reduces, and where a reader finds them.

    Rows and source travel together so that a column-existence failure can name
    the artefact to open -- `sim/<campaign>/corners/<id>/<file>.csv`, or
    `sim/<campaign>/records/<id>.md § <first column>` for a table committed
    inside a record -- rather than "the evidence file", which is not a path at
    all in the second case.

    `columns` is the set of names EVERY row carries, in the order the evidence
    heads them. Header order rather than sorted order because the reader of a
    failure is diagnosing a rename, and a renamed column is next to where it
    used to be. Every row rather than any row because an entry may name several
    records -- the closed-loop period-jitter figures reduce six -- and a name
    only some of them carry is not a name a reduction may use: reducing it
    would silently read a subset of the evidence.
    """

    def __init__(self, rows, source):
        self.rows = rows
        self.source = source
        # csv.DictReader files a row's surplus fields under the key None; a
        # column nothing can name is not a column to offer in a diagnosis.
        columns = [c for c in (rows[0] if rows else {}) if isinstance(c, str)]
        for row in rows[1:]:
            columns = [c for c in columns if c in row]
        self.columns = columns


def require_columns(evidence, needed, ctx, what):
    """False, having reported, if any of `needed` is not a column of `evidence`.

    WHY THIS IS AN ERROR AND NOT A SKIP. Reducing a column the evidence does not
    have is naturally SILENT: a where-clause over a missing column matches no
    rows, and a count of no rows is 0 -- a legitimate, and the most load-bearing,
    value for the figures section 5.1 grades. So the missing column is reported
    once, here, before any row is reduced, instead of per row where it reads as
    an answer (issue #579).

    `what` is the whole leading phrase rather than just a column position, so
    each call site says which part of the grammar named the column: a
    where-clause, an aggregate, a group key, a distinct key, or the implicit
    pairing the `on-icp-trim-rule` predicate reads.
    """
    missing = [col for col in needed if col not in evidence.columns]
    if not missing:
        return True
    fail(
        "%s: %s `%s`, which %s does not have. Its columns are: %s. A reduction "
        "over a column its evidence does not have selects nothing rather than "
        "failing, and a zero is a legitimate value for the figures this check "
        "grades -- so this is an error, never a passing zero."
        % (
            ctx,
            what,
            missing[0],
            evidence.source,
            ", ".join(evidence.columns) or "(none)",
        )
    )
    return False


# --------------------------------------------------------------- reductions ---

# A column name here may hold a hyphen or a space, because a record's own
# tables head their columns as a reader reads them -- `corner-id`, `DN guard`,
# `Target f_out` -- and a where-clause needs to name them. The column is
# therefore everything left of the operator, matched non-greedily; clauses are
# split on ` and ` first and no evidence column contains that token.
COND = re.compile(r"^([A-Za-z_][\w.\- ]*?)\s*(~=|==|!=|<=|>=|<|>)\s*(.+)$")


#: The columns the `on-icp-trim-rule` predicate reads. They are the only column
#: names in this grammar that a reduction does not spell out, which is exactly
#: why they are named here and validated with the rest: an implicit name is the
#: kind that goes missing without anyone editing the reduction that needs it.
ICP_RULE_COLUMNS = ("f_ref_hz", "trim_units")


def make_predicate(where, icp_rule, evidence, reduction, ctx):
    """` where ...` -> a function of one CSV row. None means "every row"."""
    if not where:
        return lambda row: True
    tests = []
    where_cols = []
    reads_icp_rule = False
    for clause in [c.strip() for c in where.split(" and ")]:
        if clause == "on-icp-trim-rule":
            if not icp_rule:
                fail(
                    "%s: reduction uses the `on-icp-trim-rule` predicate, but "
                    "no Icp trim-code rule table could be read out of %s. The "
                    "rule is deliberately not written into this check; if the "
                    "table moved, this check has to follow it."
                    % (ctx, spec_rel)
                )
                return None
            tests.append(("icp", None, None))
            reads_icp_rule = True
            continue
        m = COND.match(clause)
        if not m:
            fail("%s: cannot parse where-clause `%s`" % (ctx, clause))
            return None
        col, op, literal = m.group(1), m.group(2), m.group(3).strip().strip("`")
        lit_num = as_float(literal)
        if lit_num is None and op not in ("==", "!=", "~="):
            fail(
                "%s: where-clause `%s` orders a non-numeric literal; only == "
                "and != are defined for strings" % (ctx, clause)
            )
            return None
        where_cols.append(col)
        tests.append(("cmp", (col, op, literal, lit_num), None))

    # Both checks are made HERE, at parse time, and not inside the predicate:
    # a per-row answer to "does this row have that column" is `no`, and `no`
    # filters the row out, which is a zero rather than a failure.
    if where_cols and not require_columns(
        evidence,
        where_cols,
        ctx,
        "reduction `%s`'s where-clause names column" % reduction,
    ):
        return None
    if reads_icp_rule and not require_columns(
        evidence,
        ICP_RULE_COLUMNS,
        ctx,
        "reduction `%s`'s `on-icp-trim-rule` predicate reads column"
        % reduction,
    ):
        return None

    def predicate(row):
        for kind, spec, _ in tests:
            if kind == "icp":
                f_ref, trim = as_float(row.get("f_ref_hz")), row.get("trim_units")
                if f_ref is None or trim is None:
                    return False
                if icp_rule.get(f_ref) != as_float(trim):
                    return False
                continue
            col, op, literal, lit_num = spec
            # `col` is a column of every row: require_columns proved it above,
            # rather than this loop answering "no" and filtering the row out.
            cell = row[col]
            if op == "~=":
                # Substring containment, always on the text, even when both
                # sides parse as numbers: `~=` selects a slice of an id, and
                # "is 200 inside 1200" is not a comparison anyone would want
                # answered numerically.
                if literal not in str(cell).strip():
                    return False
                continue
            cell_num = as_float(cell)
            if lit_num is not None and cell_num is not None:
                a, b = cell_num, lit_num
            else:
                a, b = str(cell).strip(), literal
            if op == "==" and not a == b:
                return False
            if op == "!=" and not a != b:
                return False
            if op == "<" and not a < b:
                return False
            if op == "<=" and not a <= b:
                return False
            if op == ">" and not a > b:
                return False
            if op == ">=" and not a >= b:
                return False
        return True

    return predicate


class AggError(ValueError):
    """An aggregate that cannot be formed over the values it was given."""


def _sig3(values):
    """`|mean| + 3*sigma`, sigma the SAMPLE standard deviation (N-1).

    The worst-case magnitude of a signed error that has both a systematic
    offset and a random spread, which is what DR-018 term 1 and term 3 are and
    what `sim/mc-cp-mismatch/testbench/run.sh`'s own `sig3()` computes. Folding
    the samples to their magnitudes first gives a SMALLER number (13.2172 %
    against 17.4798 % on the same 300 samples, DR-018 Amendment A1), so the two
    readings are not interchangeable and this one is the signed one.
    """
    if len(values) < 2:
        raise AggError(
            "sig3 needs at least two samples to have a standard deviation at "
            "all; it was given %d" % len(values)
        )
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return abs(mean) + 3.0 * math.sqrt(variance)


#: How many magnitude bounds ran, over how many signed values, and how many of
#: those values lay on the far side of zero from the binding end. Reported in
#: the OK line for the reason the adjacent-pair count is: a magnitude bound
#: DISCARDS the sign it was taken over, so the figure alone cannot tell a
#: reader whether both sides of zero were ever in the set. The opposite-side
#: count is the evidence that the bound is genuinely two-sided.
mag_stats = {"bounds": 0, "values": 0, "opposite": 0}


def _maxmag(values):
    """`max(|v|)` over the selected values -- a two-sided bound.

    See THE REDUCTION GRAMMAR above for why this is not `max()` and why
    `worst-magnitude`'s opposite-sign tie guard deliberately has no twin here.
    """
    if len(values) < 2:
        raise AggError(
            "a magnitude bound is a bound over a set; maxmag was given %d "
            "value, and a bound over one value is that value" % len(values)
        )
    magnitudes = [abs(v) for v in values]
    bound = max(magnitudes)
    binding_is_negative = values[magnitudes.index(bound)] < 0
    mag_stats["bounds"] += 1
    mag_stats["values"] += len(values)
    mag_stats["opposite"] += sum(
        1 for v in values if v != 0 and (v < 0) != binding_is_negative
    )
    return bound


AGGS = {
    "min": min,
    "max": max,
    "mean": lambda vs: sum(vs) / len(vs),
    "sum": sum,
    "sig3": _sig3,
    "maxmag": _maxmag,
}

#: Every aggregate name, for the regexes below, LONGEST FIRST. `count` is
#: deliberately not one of these -- it takes `rows`/`distinct ...` rather than
#: a column.
#:
#: The ordering is load-bearing rather than tidy. One aggregate name is now a
#: PREFIX of another (`max` of `maxmag`), and a regex alternation is
#: first-match, not longest-match. Every use below happens to be anchored by a
#: `(` immediately after the name, so Python's backtracking would recover --
#: but that is a property of the engine and of today's regexes, not of this
#: grammar, and the next form added here would silently inherit the hazard.
#: Sorting removes the dependency instead of resting on it.
AGG_NAMES = "|".join(sorted(AGGS, key=len, reverse=True))

OUTER = re.compile(r"^(" + AGG_NAMES + r"|count)\((.*)\)$", re.DOTALL)
INNER_BY = re.compile(
    r"^(" + AGG_NAMES + r")\((.*)\)\s+by\s+([\w+.]+)$", re.DOTALL
)

# A group-sequence derivation: the group's rows are a SEQUENCE along an axis,
# and the figure is a property of that sequence rather than a reduction of its
# cells. `non-monotonic` is a group *predicate* (true or false of one curve, so
# only count(...) is defined over it); `adjacent-overlap` and `worst-magnitude`
# are group *scalars*, which is also what lets them compose three deep under a
# second aggregate (see INNER_SEQ_NESTED) where a predicate cannot.
SEQ_PREDICATES = ("non-monotonic",)
SEQ_SCALARS = ("adjacent-overlap", "worst-magnitude")
SEQ_VERBS = SEQ_PREDICATES + SEQ_SCALARS
SEQ_VERB_NAMES = "|".join(SEQ_VERBS)
INNER_SEQ = re.compile(
    r"^(" + SEQ_VERB_NAMES + r")\(\s*([\w.]+)\s+by\s+([\w.]+)\s*\)"
    r"\s+by\s+([\w+.]+)$",
    re.DOTALL,
)

# The three-level form: AGG(AGG(VERB(COL by AXIS) by KEY...) by KEY...). Matched
# BEFORE INNER_BY, whose greedy `(.*)` would otherwise swallow the verb call and
# then look for a column by that name.
INNER_SEQ_NESTED = re.compile(
    r"^(" + AGG_NAMES + r")\(\s*(" + SEQ_VERB_NAMES + r")\(\s*([\w.]+)\s+by\s+"
    r"([\w.]+)\s*\)\s+by\s+([\w+.]+)\s*\)\s+by\s+([\w+.]+)$",
    re.DOTALL,
)

#: How many group-sequence derivations ran, over how many groups, and -- for
#: `adjacent-overlap` -- over how many adjacent AXIS pairs. Reported in the OK
#: line because the headline figure one of them grades is a ZERO: a derivation
#: that quietly examined nothing would produce the same 0 as a derivation that
#: examined 504 curves and found none violating. The pair count is the same
#: guard one level down: a worst overlap is equally silent about how many
#: intervals it was the worst of.
seq_stats = {"derivations": 0, "groups": 0, "pairs": 0}


def group_sequences(evidence, rows, keys, columns, reduction, ctx):
    """Group `rows` by `keys`, keeping `columns` as floats. Fails loudly.

    Unlike the reduction path, a non-numeric or missing cell is an error here
    rather than a skipped row: a dropped point silently weakens a sequence
    test, and the figure these derivations grade is one a weakened test still
    reports as passing.

    `rows` may be one partition of `evidence` (the three-level form calls this
    once per outer group), so the column names are validated against the whole
    evidence rather than against whichever rows this call was handed.
    """
    if not require_columns(
        evidence,
        list(keys) + list(columns),
        ctx,
        "reduction `%s` names column" % reduction,
    ):
        return None
    groups = {}
    for row in rows:
        values = [as_float(row.get(col)) for col in columns]
        if any(value is None for value in values):
            fail(
                "%s: reduction `%s` meets a row whose %s is not a number (%s). "
                "A dropped point weakens a sequence test without changing what "
                "it reports, so this is an error rather than a skip."
                % (
                    ctx,
                    reduction,
                    " or ".join("`%s`" % c for c in columns),
                    ", ".join("%s=%r" % (c, row.get(c)) for c in columns),
                )
            )
            return None
        groups.setdefault(
            tuple(str(row.get(k, "")).strip() for k in keys), []
        ).append(values)
    if not groups:
        # UNREACHABLE TODAY, AND DELIBERATELY KEPT. `groups` can only be empty
        # when `rows` is, and collect_evidence_rows() has already refused that
        # with "the evidence file(s) hold no data rows" -- which is the guard
        # that actually delivers "an empty derivation must not read as a
        # passing zero", and which the empty-file test asserts. This branch is
        # defence in depth for a future caller that reaches this function by
        # some other route; it is not the one the anti-vacuity guarantee rests
        # on, so do not read it as such.
        fail(
            "%s: reduction `%s` formed no groups at all. There is nothing to "
            "derive, and an empty derivation must not read as a passing zero."
            % (ctx, reduction)
        )
        return None
    return groups


def apply_agg(name, values, reduction, ctx):
    """AGGS[name](values), turning an AggError into a reported failure."""
    try:
        return AGGS[name](values)
    except AggError as exc:
        fail("%s: reduction `%s` cannot be formed -- %s" % (ctx, reduction, exc))
        return None


#: The verbs that read one point PER AXIS VALUE, so that a group holding two
#: rows at the same AXIS value is ambiguous rather than richer. `non-monotonic`
#: reads a curve and `worst-magnitude` selects one point of a window; both are
#: in this set. `adjacent-overlap` deliberately is NOT: its groups hold a whole
#: control sweep at each band code, and collapsing those to one point per band
#: is the interval it measures.
SEQ_VERBS_ONE_POINT_PER_AXIS_VALUE = ("non-monotonic", "worst-magnitude")


def ordered_group_points(groups, verb, axis, reduction, ctx):
    """Each group's points ordered by AXIS, with the ambiguity guards applied.

    A group of fewer than two points is not a sequence for any verb. A repeated
    AXIS value is an error only for the verbs that read one point per axis value
    (see above). Both are errors rather than skips -- see group_sequences().
    """
    ordered = {}
    for key, points in sorted(groups.items()):
        points = sorted(points, key=lambda point: point[1])
        if len(points) < 2:
            fail(
                "%s: group %s holds %d point(s); a sequence test over fewer "
                "than two points is not a test"
                % (ctx, "/".join(key), len(points))
            )
            return None
        if verb in SEQ_VERBS_ONE_POINT_PER_AXIS_VALUE:
            axis_values = [point[1] for point in points]
            if len(set(axis_values)) != len(axis_values):
                fail(
                    "%s: group %s repeats a value of the ordering column `%s`, "
                    "so the sequence it would be tested as is ambiguous"
                    % (ctx, "/".join(key), axis)
                )
                return None
        ordered[key] = points
    return ordered


def sequence_group_scalars(
    evidence, verb, col, axis, keys, rows, reduction, ctx
):
    """{group key: the verb's scalar for that group} for a SEQ_SCALAR verb."""
    groups = group_sequences(evidence, rows, keys, [col, axis], reduction, ctx)
    if groups is None:
        return None
    ordered = ordered_group_points(groups, verb, axis, reduction, ctx)
    if ordered is None:
        return None
    # Group accounting only: a three-level reduction calls this once per outer
    # partition, and the OK line counts DERIVATIONS (one per section 5.1 entry),
    # not invocations. Its callers do that half.
    seq_stats["groups"] += len(ordered)

    scalars = {}
    for key, points in ordered.items():
        if verb == "worst-magnitude":
            best = max(abs(value) for value, _ in points)
            candidates = {value for value, _ in points if abs(value) == best}
            if len(candidates) > 1:
                fail(
                    "%s: group %s has two points tying at magnitude %g with "
                    "different signs (%s), so the worst point's sign is "
                    "ambiguous"
                    % (
                        ctx,
                        "/".join(key),
                        best,
                        ", ".join("%g" % c for c in sorted(candidates)),
                    )
                )
                return None
            scalars[key] = candidates.pop()
            continue

        # adjacent-overlap: the worst (smallest) fractional overlap between the
        # COL interval at AXIS and the one at AXIS+1. max(COL at k) / min(COL
        # at k+1) - 1; negative means a hole rather than an overlap. The
        # pairing is k with k+1, so AXIS is integer-coded and unit-spaced --
        # see the grammar note in the header -- and a gap in the run is an
        # error rather than a pair this walk steps over.
        spans = {}
        for value, step in points:
            low, high = spans.get(step, (value, value))
            spans[step] = (min(low, value), max(high, value))
        steps = sorted(spans)
        paired = [step for step in steps if step + 1 in spans]
        if not paired:
            fail(
                "%s: group %s holds no pair of consecutive `%s` values, so it "
                "has no adjacent interval to overlap"
                % (ctx, "/".join(key), axis)
            )
            return None
        holes = [
            (low, high)
            for low, high in zip(steps, steps[1:])
            if high - low != 1
        ]
        if holes:
            where = ", ".join(
                "%g then %g" % (low, high) for low, high in holes
            )
            fail(
                "%s: group %s has a gap in its `%s` run (%s): this derivation "
                "pairs `%s` with `%s`+1, so it would examine %d pair(s) of "
                "the %d that %d values look like they hold. A partially "
                "gapped group is an error rather than a shorter walk -- a "
                "worst overlap taken over fewer intervals than the group "
                "appears to hold reads exactly like one taken over all of "
                "them."
                % (
                    ctx,
                    "/".join(key),
                    axis,
                    where,
                    axis,
                    axis,
                    len(paired),
                    len(steps) - 1,
                    len(steps),
                )
            )
            return None
        overlaps = []
        for step in paired:
            upper, lower = spans[step][1], spans[step + 1][0]
            if lower == 0:
                fail(
                    "%s: group %s divides by a zero `%s` at %s+1"
                    % (ctx, "/".join(key), col, step)
                )
                return None
            overlaps.append(upper / lower - 1.0)
        seq_stats["pairs"] += len(overlaps)
        scalars[key] = min(overlaps)
    return scalars


def apply_nested_group_sequence(
    outer, inner, verb, col, axis, inner_keys, outer_keys, evidence, reduction,
    ctx
):
    """Evaluate AGG(AGG(VERB(COL by AXIS) by KEY...) by KEY...).

    The outer keys partition the rows; inside each partition the inner keys do
    it again, each innermost group's AXIS sequence collapses to the verb's
    scalar, `inner` combines those and `outer` combines the partitions. Only
    SEQ_SCALAR verbs compose this way: a group predicate is true or false, and
    `sig3` of a set of booleans is not a statistic anyone means.
    """
    if verb in SEQ_PREDICATES:
        fail(
            "%s: `%s` is a group predicate -- it is true or false of one group "
            "-- so it does not compose into a three-level reduction; only "
            "count(%s(...) by ...) is defined over it" % (ctx, verb, verb)
        )
        return None
    rows = evidence.rows
    if not require_columns(
        evidence,
        outer_keys,
        ctx,
        "reduction `%s` groups by column" % reduction,
    ):
        return None
    partitions = {}
    for row in rows:
        partitions.setdefault(
            tuple(str(row.get(k, "")).strip() for k in outer_keys), []
        ).append(row)
    if not partitions:
        # Same standing as group_sequences()' twin of this branch: unreachable
        # behind collect_evidence_rows()' no-data-rows refusal, kept as defence
        # in depth rather than as the guarantee's source.
        fail(
            "%s: reduction `%s` formed no groups at all. There is nothing to "
            "derive, and an empty derivation must not read as a passing zero."
            % (ctx, reduction)
        )
        return None
    seq_stats["derivations"] += 1
    inner_values = []
    for key in sorted(partitions):
        scalars = sequence_group_scalars(
            evidence, verb, col, axis, inner_keys, partitions[key], reduction,
            ctx
        )
        if scalars is None:
            return None
        value = apply_agg(inner, list(scalars.values()), reduction, ctx)
        if value is None:
            return None
        inner_values.append(value)
    value = apply_agg(outer, inner_values, reduction, ctx)
    if value is None:
        return None
    return value, False


def apply_group_sequence(
    outer, verb, col, axis, keys, evidence, reduction, ctx
):
    """Evaluate AGG(VERB(COL by AXIS) by KEY[+KEY...]). (value, is_count)."""
    rows = evidence.rows
    if verb in SEQ_PREDICATES and outer != "count":
        fail(
            "%s: `%s` is a group predicate -- it is true or false of one group "
            "-- so only count(...) is defined over it, not %s(...)"
            % (ctx, verb, outer)
        )
        return None
    if verb in SEQ_SCALARS and outer == "count":
        fail(
            "%s: `%s` is a group scalar, not a predicate; count(...) over it is "
            "not defined -- use %s" % (ctx, verb, "/".join(AGGS))
        )
        return None

    if verb == "non-monotonic":
        groups = group_sequences(
            evidence, rows, keys, [col, axis], reduction, ctx
        )
        if groups is None:
            return None
        ordered_groups = ordered_group_points(
            groups, verb, axis, reduction, ctx
        )
        if ordered_groups is None:
            return None
        seq_stats["derivations"] += 1
        seq_stats["groups"] += len(ordered_groups)
        violations = 0
        for _, points in sorted(ordered_groups.items()):
            series = [point[0] for point in points]
            steps = list(zip(series, series[1:]))
            rising = all(b >= a for a, b in steps)
            falling = all(b <= a for a, b in steps)
            if not rising and not falling:
                violations += 1
        return float(violations), True

    seq_stats["derivations"] += 1
    scalars = sequence_group_scalars(
        evidence, verb, col, axis, keys, rows, reduction, ctx
    )
    if scalars is None:
        return None
    value = apply_agg(outer, list(scalars.values()), reduction, ctx)
    if value is None:
        return None
    return value, False


def apply_reduction(reduction, evidence, icp_rule, ctx):
    """Evaluate a reduction over `evidence`. (value, is_count), or None."""
    rows = evidence.rows
    m = OUTER.match(reduction.strip())
    if not m:
        fail("%s: cannot parse reduction `%s`" % (ctx, reduction))
        return None
    outer, body = m.group(1), m.group(2).strip()

    three_level = INNER_SEQ_NESTED.match(body)
    if three_level:
        if outer == "count":
            fail(
                "%s: `count(... by ...)` is not defined -- use "
                "count(distinct KEY+KEY)" % ctx
            )
            return None
        return apply_nested_group_sequence(
            outer,
            three_level.group(1),
            three_level.group(2),
            three_level.group(3).strip(),
            three_level.group(4).strip(),
            three_level.group(5).split("+"),
            three_level.group(6).split("+"),
            evidence,
            reduction,
            ctx,
        )

    nested = INNER_BY.match(body)
    if nested:
        if outer == "count":
            fail(
                "%s: `count(... by ...)` is not defined -- use "
                "count(distinct KEY+KEY)" % ctx
            )
            return None
        inner_agg, inner_body, keys = (
            nested.group(1),
            nested.group(2).strip(),
            nested.group(3),
        )
        col, _, where = [p.strip() for p in _split_where(inner_body)]
        group_keys = keys.split("+")
        if not require_columns(
            evidence, [col], ctx, "reduction `%s` names column" % reduction
        ):
            return None
        if not require_columns(
            evidence,
            group_keys,
            ctx,
            "reduction `%s` groups by column" % reduction,
        ):
            return None
        predicate = make_predicate(where, icp_rule, evidence, reduction, ctx)
        if predicate is None:
            return None
        groups = {}
        for row in rows:
            if not predicate(row):
                continue
            value = as_float(row.get(col))
            if value is None:
                continue
            groups.setdefault(
                tuple(str(row.get(k, "")).strip() for k in group_keys), []
            ).append(value)
        if not groups:
            fail("%s: reduction `%s` selected no rows" % (ctx, reduction))
            return None
        inner = []
        for values in groups.values():
            value = apply_agg(inner_agg, values, reduction, ctx)
            if value is None:
                return None
            inner.append(value)
        value = apply_agg(outer, inner, reduction, ctx)
        if value is None:
            return None
        return value, False

    sequence = INNER_SEQ.match(body)
    if sequence:
        return apply_group_sequence(
            outer,
            sequence.group(1),
            sequence.group(2).strip(),
            sequence.group(3).strip(),
            sequence.group(4).split("+"),
            evidence,
            reduction,
            ctx,
        )
    if re.search(r"(?:^|\()(?:" + SEQ_VERB_NAMES + r")\(", body):
        fail(
            "%s: cannot parse reduction `%s` -- a group-sequence derivation is "
            "spelled AGG(VERB(COL by AXIS) by KEY[+KEY...]), or "
            "AGG(AGG(VERB(COL by AXIS) by KEY[+KEY...]) by KEY[+KEY...]) for "
            "the three-level form, and takes no where-clause"
            % (ctx, reduction)
        )
        return None

    target, _, where = [p.strip() for p in _split_where(body)]
    predicate = make_predicate(where, icp_rule, evidence, reduction, ctx)
    if predicate is None:
        return None
    selected = [row for row in rows if predicate(row)]

    if outer == "count":
        if target == "rows":
            return float(len(selected)), True
        if target.startswith("distinct "):
            keys = target[len("distinct ") :].strip().split("+")
            if not require_columns(
                evidence,
                keys,
                ctx,
                "reduction `%s` counts distinct values of column" % reduction,
            ):
                return None
            seen = {
                tuple(str(row.get(k, "")).strip() for k in keys)
                for row in selected
            }
            return float(len(seen)), True
        fail(
            "%s: `count(%s)` is not defined -- use count(rows) or "
            "count(distinct KEY+KEY)" % (ctx, target)
        )
        return None

    if not require_columns(
        evidence, [target], ctx, "reduction `%s` names column" % reduction
    ):
        return None
    values = []
    for row in selected:
        value = as_float(row.get(target))
        if value is not None:
            values.append(value)
    if not values:
        fail("%s: reduction `%s` selected no numeric values" % (ctx, reduction))
        return None
    value = apply_agg(outer, values, reduction, ctx)
    if value is None:
        return None
    return value, False


def _split_where(body):
    parts = re.split(r"\s+where\s+", body, maxsplit=1)
    return (parts[0], "where", parts[1]) if len(parts) == 2 else (parts[0], "", "")


# ------------------------------------------------------------------ the tree ---

def read_csv_rows(path):
    with open(path, encoding="utf-8") as fh:
        lines = [line for line in fh if not line.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


#: How many in-record tables were read, and under which of the two
#: correspondence rules (see read_record_table). Reported in the OK line
#: because the weaker rule must never be applied silently.
record_table_stats = {"id_matched": 0, "count_matched": 0}

#: `<record-id>.md § <first column name>` -- the record's own per-point table as
#: an evidence source (rule 1). The record id is repeated inside the spec on
#: purpose: an entry may only read the markdown of the record it declares.
RECORD_TABLE = re.compile(r"^(" + RECORD_ID + r")\.md\s*§\s*([\w.\-/]+)$")


def read_record_table(rid, campaign, first_col, ctx):
    """A pipe table committed inside a record, in CSV-row shape.

    The table is identified by its first column's name, which must be unique
    among the record's tables. Cells are stripped of the backticks the record
    writes ids in, so a reduction sees the same strings a CSV would give it.

    THE ANTI-TRUNCATION RULE. A CSV cannot be abbreviated without being wrong;
    a markdown table can be elided, summarised, or hand-trimmed, and a
    `count(rows)` over an elided table is a smaller number that still looks
    like an answer. So the table must have exactly one row per committed
    per-corner log -- one row per simulation that ran. That correspondence is
    checked against the logs, which are raw evidence, and never against the
    record's own declared point count, which is the claim rather than the
    evidence.

    Where the table's first column IS the per-corner point id -- which some
    campaigns write and others do not, heading it `Corner` and splitting the
    corner across several columns instead -- the row SETS are compared too, not
    just their sizes: that additionally catches a duplicated or mistyped row
    that the count rule alone would let through. The stricter rule is applied
    whenever the evidence supports it and its absence is never silent: the OK
    line names which tables got which.
    """
    rec_path = os.path.join(repo_root, "sim", campaign, "records", rid + ".md")
    if not os.path.isfile(rec_path):
        fail("%s: no record at sim/%s/records/%s.md" % (ctx, campaign, rid))
        return None
    with open(rec_path, encoding="utf-8") as fh:
        record_text = fh.read()
    matches = [
        (header, body)
        for header, body in read_tables(record_text)
        if header and header[0].strip().strip("`") == first_col
    ]
    if not matches:
        fail(
            "%s: sim/%s/records/%s.md has no table whose first column is `%s`"
            % (ctx, campaign, rid, first_col)
        )
        return None
    if len(matches) > 1:
        fail(
            "%s: sim/%s/records/%s.md has %d tables whose first column is `%s`. "
            "An evidence source has to name one table, not a shape several "
            "tables share." % (ctx, campaign, rid, len(matches), first_col)
        )
        return None
    header, body = matches[0]
    names = [cell.strip().strip("`") for cell in header]
    rows = []
    for cells in body:
        if len(cells) != len(names):
            fail(
                "%s: a row of the `%s` table in sim/%s/records/%s.md has %d "
                "cells, not the %d its header declares: %r"
                % (ctx, first_col, campaign, rid, len(cells), len(names), cells)
            )
            return None
        rows.append(
            {
                name: cell.strip().strip("`")
                for name, cell in zip(names, cells)
            }
        )

    corners_dir = os.path.join(repo_root, "sim", campaign, "corners", rid)
    logs = (
        sorted(
            name[: -len(".log")]
            for name in os.listdir(corners_dir)
            if name.endswith(".log")
        )
        if os.path.isdir(corners_dir)
        else []
    )
    if not logs:
        fail(
            "%s: sim/%s/corners/%s/ commits no per-corner logs, so the `%s` "
            "table's row set cannot be checked against the simulations that "
            "ran. A markdown table nothing corroborates is prose."
            % (ctx, campaign, rid, first_col)
        )
        return None
    if len(rows) != len(logs):
        fail(
            "%s: the `%s` table in sim/%s/records/%s.md has %d row(s) against "
            "the %d per-corner log(s) sim/%s/corners/%s/ commits. One row per "
            "simulation that ran is what makes a count over this table a claim "
            "about the campaign; a table that was truncated, summarised or "
            "hand-trimmed must not read as a smaller, passing answer."
            % (
                ctx,
                first_col,
                campaign,
                rid,
                len(rows),
                len(logs),
                campaign,
                rid,
            )
        )
        return None

    ids = sorted(str(row.get(first_col, "")).strip() for row in rows)
    log_set = set(logs)
    if any(i in log_set for i in ids):
        # The first column is the per-corner point id, so the row SETS are
        # comparable and not merely their sizes.
        record_table_stats["id_matched"] += 1
        if ids != logs:
            missing = sorted(log_set - set(ids))
            extra = sorted(set(ids) - log_set)
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            fail(
                "%s: the `%s` table in sim/%s/records/%s.md has one row per "
                "committed log by count, but not by identity -- %d log(s) with "
                "no row (%s), %d row(s) with no log (%s), %d duplicated row id "
                "(%s)."
                % (
                    ctx,
                    first_col,
                    campaign,
                    rid,
                    len(missing),
                    ", ".join(missing[:3]) or "-",
                    len(extra),
                    ", ".join(extra[:3]) or "-",
                    len(dupes),
                    ", ".join(dupes[:3]) or "-",
                )
            )
            return None
    else:
        record_table_stats["count_matched"] += 1
    return rows


def describe_sources(sources):
    """The evidence an entry reduces, as one phrase a failure can name.

    Compacted past two because an entry may name six records of one file (the
    closed-loop period-jitter figures do) and a column-existence failure has to
    stay readable; the count is kept rather than dropped, so the phrase never
    understates what was read.
    """
    if len(sources) <= 2:
        return "; ".join(sources) or "(no evidence)"
    return "%s (and %d more record(s) of the same evidence file)" % (
        sources[0],
        len(sources) - 1,
    )


def collect_evidence_rows(record_ids, evidence_file, spec_cited, ctx):
    """The committed evidence an entry reduces, or None if a rule 1/2 fails.

    Shared by the graded-value table (rule 4) and the derived-figure table
    (rule 7) so that "which evidence an entry may read" has exactly one
    implementation. A second copy would be free to drift, and the rule it
    encodes -- an entry may only reduce a record the section 5 row itself
    cites -- is the one that stops section 5.1 smuggling in evidence.
    """
    rows = []
    sources = []
    resolved = True
    for rid in record_ids:
        if rid not in records:
            fail("%s: record `%s` is not on the tree" % (ctx, rid))
            resolved = False
            continue
        if rid not in spec_cited:
            fail(
                "%s: reduces record `%s`, which that section 5 row does not "
                "cite. A value may only be re-derived from evidence the row "
                "itself points a reader at." % (ctx, rid)
            )
            resolved = False
            continue
        table_spec = RECORD_TABLE.match(evidence_file)
        if table_spec:
            if table_spec.group(1) != rid:
                fail(
                    "%s: names evidence inside record `%s`'s markdown while "
                    "reducing record `%s`. An entry may only read the record it "
                    "declares." % (ctx, table_spec.group(1), rid)
                )
                resolved = False
                continue
            in_record = read_record_table(
                rid, records[rid], table_spec.group(2), ctx
            )
            if in_record is None:
                resolved = False
                continue
            rows.extend(in_record)
            sources.append(
                "sim/%s/records/%s.md § %s"
                % (records[rid], rid, table_spec.group(2))
            )
            continue
        path = os.path.join(
            repo_root, "sim", records[rid], "corners", rid, evidence_file
        )
        if not os.path.isfile(path):
            fail(
                "%s: no committed evidence file at sim/%s/corners/%s/%s"
                % (ctx, records[rid], rid, evidence_file)
            )
            resolved = False
            continue
        rows.extend(read_csv_rows(path))
        sources.append(
            "sim/%s/corners/%s/%s" % (records[rid], rid, evidence_file)
        )
    if not resolved:
        return None
    if not rows:
        fail("%s: the evidence file(s) hold no data rows" % ctx)
        return None
    return Evidence(rows, describe_sources(sources))


records = {}
sim_root = os.path.join(repo_root, "sim")
for campaign in sorted(os.listdir(sim_root)) if os.path.isdir(sim_root) else []:
    rec_dir = os.path.join(sim_root, campaign, "records")
    if not os.path.isdir(rec_dir):
        continue
    for name in sorted(os.listdir(rec_dir)):
        if name.endswith(".md"):
            records[name[:-3]] = campaign

proposal_path = os.path.join(repo_root, proposal_rel)
if not os.path.isfile(proposal_path):
    sys.stderr.write("FAIL: %s does not exist\n" % proposal_rel)
    sys.exit(1)
with open(proposal_path, encoding="utf-8") as fh:
    proposal = fh.read()

spec_path = os.path.join(repo_root, spec_rel)
spec_text = ""
if os.path.isfile(spec_path):
    with open(spec_path, encoding="utf-8") as fh:
        spec_text = fh.read()
icp_rule = read_icp_trim_rule(spec_text)

# The documents a rule-7 constant may be read out of: the ratified spec, and
# the decision records the spec cites for a line it does not restate in full.
dr_dir = os.path.join(repo_root, "spec", "decision-records")
constant_docs = {"spec": spec_text, "dr003": ""}
if os.path.isdir(dr_dir):
    for name in sorted(os.listdir(dr_dir)):
        if name.startswith("DR-003-") and name.endswith(".md"):
            with open(os.path.join(dr_dir, name), encoding="utf-8") as fh:
                constant_docs["dr003"] = fh.read()
            break

#: name -> (value, [(where it was read, value)]), resolved on first use.
resolved_constants = {}


def resolve_constant(name, ctx):
    if name in resolved_constants:
        return resolved_constants[name]
    if name not in CONSTANTS:
        fail(
            "%s: `%s` is not a ratified constant this check knows how to "
            "read. Known constants: %s. A constant is added by teaching this "
            "check to READ it out of a committed document, never by writing "
            "the number here." % (ctx, name, ", ".join(sorted(CONSTANTS)))
        )
        resolved_constants[name] = None
        return None
    try:
        value, readings = CONSTANTS[name](constant_docs)
    except ConstantError as exc:
        fail("%s: %s" % (ctx, exc))
        resolved_constants[name] = None
        return None
    if value == 0:
        fail("%s: ratified constant `%s` reads as zero" % (ctx, name))
        resolved_constants[name] = None
        return None
    resolved_constants[name] = (value, readings)
    return resolved_constants[name]


tables = read_tables(proposal)

spec_rows = None          # normalized name -> (cells, source records)
spec_row_order = []
provenance = None
derived_figures = None
exclusions = None
ungraded_figures = None

for header, body in tables:
    if len(header) >= 5 and header[0] == "Parameter" and "Verdict" in header:
        if spec_rows is not None:
            continue
        spec_rows, inherited = {}, []
        for cells in body:
            if len(cells) < 5:
                continue
            name = normalize_row_name(cells[0])
            cited = re.findall(r"(" + RECORD_ID + r")", cells[4])
            if cited:
                inherited = cited
            spec_rows[name] = (cells, cited or list(inherited))
            spec_row_order.append(name)
    elif (
        len(header) >= 7
        and header[1].lower().startswith("quoted value")
        and header[4].lower().startswith("derivation")
    ):
        # The rule-7 table. Discriminated on its `Derivation` column BEFORE
        # the graded-value table, because both are headed `Quoted value` and
        # a bare "second column" test would read one as the other.
        derived_figures = body
    elif len(header) >= 6 and header[1].lower().startswith("quoted value"):
        provenance = body
    elif len(header) >= 2 and header[1].lower().startswith("why no value"):
        exclusions = body
    elif (
        len(header) >= 3
        and header[1].lower().startswith("figure")
        and header[2].lower().startswith("why it is not")
    ):
        ungraded_figures = body

if spec_rows is None or len(spec_rows) < MIN_SPEC_ROWS:
    sys.stderr.write(
        "FAIL: parsed %d rows of %s's section 5 specification table (expected "
        "at least %d). This is a parser failure, not a clean document.\n"
        % (0 if spec_rows is None else len(spec_rows), proposal_rel, MIN_SPEC_ROWS)
    )
    sys.exit(1)

if not provenance:
    sys.stderr.write(
        "FAIL: %s has no non-empty section 5.1 value-provenance table (a "
        "header row whose second column is `Quoted value`). Every measured "
        "figure in section 5 would then be ungraded.\n" % proposal_rel
    )
    sys.exit(1)

if not derived_figures:
    sys.stderr.write(
        "FAIL: %s has no non-empty section 5.1 derived-figure table (a header "
        "row whose second column is `Quoted value` and whose fifth is "
        "`Derivation`). Deleting it would not make the figures it grades "
        "ungraded-and-declared; it would make them ungraded and silent, which "
        "is the state this section exists to prevent.\n" % proposal_rel
    )
    sys.exit(1)

if exclusions is None:
    sys.stderr.write(
        "FAIL: %s has no section 5.1 exclusion table (a header row whose "
        "second column begins `Why no value`). Without it, a row with no "
        "graded value is indistinguishable from a row nobody looked at.\n"
        % proposal_rel
    )
    sys.exit(1)

if not ungraded_figures:
    sys.stderr.write(
        "FAIL: %s has no non-empty section 5.1 ungraded-figure table (a header "
        "row whose columns are `Figure` and `Why it is not re-derived`). "
        "Coverage here is per row, not per number, so a graded row can still "
        "hold a figure nothing re-derives; an empty or absent list claims no "
        "graded row does, which this check cannot verify.\n" % proposal_rel
    )
    sys.exit(1)

# ---------------------------------------------------------------- the rules ---

graded_rows = set()
graded_values = {}        # normalized row name -> {quoted figure as written}
checked = 0

for cells in provenance:
    if len(cells) < 6:
        fail("section 5.1 provenance row has %d columns, expected 6: %r"
             % (len(cells), cells))
        continue
    row_name = normalize_row_name(cells[0])
    quoted_raw = cells[1].strip()
    record_ids = re.findall(RECORD_ID, cells[2])
    evidence_file = cells[3].strip().strip("`")
    reduction = cells[4].strip().strip("`")
    scale_raw = cells[5].strip().strip("`")
    ctx = "section 5.1 entry %s / %s" % (row_name, quoted_raw)

    if row_name not in spec_rows:
        fail(
            "%s: names a section 5 row that does not exist. Section 5's rows "
            "are: %s" % (ctx, "; ".join(spec_row_order))
        )
        continue
    graded_rows.add(row_name)
    spec_cells, spec_cited = spec_rows[row_name]

    quoted_plain = quoted_raw.strip("`").strip()
    graded_values.setdefault(row_name, set()).add(quoted_plain)
    haystack = " || ".join(spec_cells[1:4])
    if quoted_plain not in haystack:
        fail(
            "%s: the quoted value does not appear in that section 5 row. "
            "Section 5.1 and section 5 have drifted apart -- one of them was "
            "edited and the other was not." % ctx
        )

    if not record_ids:
        fail("%s: names no record id" % ctx)
        continue

    evidence = collect_evidence_rows(record_ids, evidence_file, spec_cited, ctx)
    if evidence is None:
        continue

    if is_range_figure(quoted_raw):
        fail(
            "%s: the quoted value is a two-ended range. Only the number at "
            "its front would be graded, which is grading half of a two-sided "
            "bound and calling it the bound -- grade each end as its own "
            "entry, or declare the range in the ungraded-figure table." % ctx
        )
        continue

    parsed = parse_quoted(quoted_raw)
    if parsed is None:
        fail("%s: cannot read a number out of the quoted value" % ctx)
        continue
    mantissa, exp, decimals = parsed

    scale = as_float(scale_raw)
    if scale is None:
        fail("%s: scale `%s` is not a number" % (ctx, scale_raw))
        continue

    result = apply_reduction(reduction, evidence, icp_rule, ctx)
    if result is None:
        continue
    raw_value, is_count = result

    if is_count and scale != 1.0:
        fail("%s: a count reduction must carry scale 1, not %s" % (ctx, scale_raw))
        continue

    derived = raw_value * scale
    checked += 1

    if is_count:
        if float(mantissa) * (10.0 ** exp) != derived:
            fail(
                "%s: section 5 says %s; `%s` over %s counts %d"
                % (ctx, quoted_plain, reduction, evidence_file, int(derived))
            )
        continue

    if not rounds_to(derived, mantissa, exp, decimals):
        fail(
            "%s: section 5 says %s; `%s` over %s gives %.6g, which does not "
            "round to it at the %d decimal place(s) written"
            % (ctx, quoted_plain, reduction, evidence_file, derived, decimals)
        )

# ---- rule 7: figures derived from a reduction and a ratified constant -------

derived_checked = 0
constants_used = set()

for cells in derived_figures or []:
    if len(cells) < 7:
        fail("section 5.1 derived-figure row has %d columns, expected 7: %r"
             % (len(cells), cells))
        continue
    row_name = normalize_row_name(cells[0])
    quoted_raw = cells[1].strip()
    record_ids = re.findall(RECORD_ID, cells[2])
    evidence_file = cells[3].strip().strip("`")
    derivation = cells[4].strip().strip("`")
    constant_stated = cells[5].strip().strip("`")
    scale_raw = cells[6].strip().strip("`")
    ctx = "section 5.1 derived figure %s / %s" % (row_name, quoted_raw)

    if row_name not in spec_rows:
        fail(
            "%s: names a section 5 row that does not exist. Section 5's rows "
            "are: %s" % (ctx, "; ".join(spec_row_order))
        )
        continue
    graded_rows.add(row_name)
    spec_cells, spec_cited = spec_rows[row_name]

    quoted_plain = quoted_raw.strip("`").strip()
    graded_values.setdefault(row_name, set()).add(quoted_plain)
    if quoted_plain not in " || ".join(spec_cells[1:4]):
        fail(
            "%s: the derived figure does not appear in that section 5 row. "
            "Section 5.1 and section 5 have drifted apart -- one of them was "
            "edited and the other was not." % ctx
        )

    parsed_derivation = DERIVATION.match(derivation)
    if parsed_derivation is None:
        fail(
            "%s: cannot read the derivation `%s`. The form is "
            "`<reduction> <op> <ratified constant>`, with <op> one of `/` "
            "(a measurement over a line) or `-` (a measurement's distance "
            "from a line), one operand each side, the constant named. The "
            "operator must be surrounded by spaces, which is what keeps it "
            "apart from a negative literal inside a where-clause "
            "(`temp_c == -40`)." % (ctx, derivation)
        )
        continue
    reduction = parsed_derivation.group("reduction").strip()
    operator = parsed_derivation.group("op")
    constant_name = parsed_derivation.group("constant").strip()

    if not record_ids:
        fail("%s: names no record id" % ctx)
        continue

    evidence = collect_evidence_rows(record_ids, evidence_file, spec_cited, ctx)
    if evidence is None:
        continue

    if is_range_figure(quoted_raw):
        fail(
            "%s: the derived figure is a two-ended range. Only the number at "
            "its front would be graded, which is grading half of a two-sided "
            "bound and calling it the bound -- derive each end as its own "
            "entry, or declare the range in the ungraded-figure table." % ctx
        )
        continue

    parsed = parse_quoted(quoted_raw)
    if parsed is None:
        fail("%s: cannot read a number out of the derived figure" % ctx)
        continue
    mantissa, exp, decimals = parsed

    scale = as_float(scale_raw)
    if scale is None:
        fail("%s: scale `%s` is not a number" % (ctx, scale_raw))
        continue

    constant = resolve_constant(constant_name, ctx)
    if constant is None:
        continue
    constant_value, constant_readings = constant
    constants_used.add(constant_name)

    # The table's own statement of the line is graded against the documents.
    # It is a reader's handle on the arithmetic, not an input to it.
    stated = parse_quoted(constant_stated)
    if stated is None:
        fail(
            "%s: the Constant column `%s` states no number. It has to state "
            "the line the derivation divides by or subtracts, so a reader can "
            "do the arithmetic." % (ctx, constant_stated)
        )
    elif not rounds_to(constant_value, *stated):
        fail(
            "%s: the Constant column states %s, but `%s` reads %.6g out of "
            "%s. The document and the ratified line have drifted apart."
            % (
                ctx,
                constant_stated,
                constant_name,
                constant_value,
                "; ".join(where for where, _ in constant_readings),
            )
        )

    result = apply_reduction(reduction, evidence, icp_rule, ctx)
    if result is None:
        continue
    raw_value, is_count = result

    if is_count:
        fail(
            "%s: the measured operand is a count. A count over a ratified "
            "quantity is not a ratio and a count minus one is not a distance; "
            "a figure that needs either needs a stated reason first." % ctx
        )
        continue

    if operator == "/":
        derived = (raw_value / constant_value) * scale
        against = "and over the ratified %.6g that is %.6g" % (
            constant_value, derived
        )
    else:
        derived = (raw_value - constant_value) * scale
        against = "and its distance from the ratified %.6g is %.6g" % (
            constant_value, derived
        )
    derived_checked += 1

    if not rounds_to(derived, mantissa, exp, decimals):
        fail(
            "%s: section 5 says %s; `%s` over %s gives %.6g, %s, which does "
            "not round to it at the %d decimal place(s) written"
            % (
                ctx,
                quoted_plain,
                reduction,
                evidence_file,
                raw_value,
                against,
                decimals,
            )
        )

excluded_rows = set()
for cells in exclusions:
    if len(cells) < 2:
        fail("section 5.1 exclusion row has %d columns, expected 2: %r"
             % (len(cells), cells))
        continue
    row_name = normalize_row_name(cells[0])
    reason = cells[1].strip()
    if row_name not in spec_rows:
        fail(
            "section 5.1 exclusion names a section 5 row that does not exist: "
            "%s" % row_name
        )
        continue
    if len(reason) < 20:
        fail(
            "section 5.1 exclusion for %s gives no real reason (%r). An "
            "ungraded row has to say why." % (row_name, reason)
        )
    excluded_rows.add(row_name)

disclosed_figures = 0
for cells in ungraded_figures:
    if len(cells) < 3:
        fail("section 5.1 ungraded-figure row has %d columns, expected 3: %r"
             % (len(cells), cells))
        continue
    row_name = normalize_row_name(cells[0])
    figure = cells[1].strip().strip("`").strip()
    reason = cells[2].strip()
    ctx = "section 5.1 ungraded figure %s / %s" % (row_name, figure or "(none)")
    if not figure:
        fail("%s: names no figure" % ctx)
        continue
    if row_name not in spec_rows:
        fail(
            "%s: names a section 5 row that does not exist. Section 5's rows "
            "are: %s" % (ctx, "; ".join(spec_row_order))
        )
        continue
    disclosed_figures += 1
    if row_name in excluded_rows:
        fail(
            "%s: that section 5 row has no re-derived value at all, so every "
            "figure in it is already accounted for by the exclusion table. "
            "This list is for figures inside GRADED rows." % ctx
        )
    if figure in graded_values.get(row_name, set()):
        fail(
            "%s: that figure is also graded in the provenance table -- a figure "
            "cannot be both re-derived and declared un-re-derived" % ctx
        )
    spec_cells, _ = spec_rows[row_name]
    if figure not in " || ".join(spec_cells[1:4]):
        fail(
            "%s: that figure does not appear in the section 5 row it is "
            "declared against. The disclosure has gone stale: the row was "
            "edited and this list was not." % ctx
        )
    if len(reason) < 20:
        fail(
            "%s: gives no real reason (%r). A figure nothing re-derives has to "
            "say why." % (ctx, reason)
        )

for name in spec_row_order:
    in_both = name in graded_rows and name in excluded_rows
    if in_both:
        fail(
            "section 5 row %s is both graded and excluded in section 5.1 -- it "
            "cannot be" % name
        )
    elif name not in graded_rows and name not in excluded_rows:
        fail(
            "section 5 row %s appears in neither of section 5.1's tables. Give "
            "it a re-derived value, or say in the exclusion table why it has "
            "none -- a row nobody accounted for is exactly what this check "
            "exists to stop." % name
        )

if errors:
    for message in errors:
        sys.stderr.write("FAIL: %s\n" % message)
    sys.exit(1)

print(
    "OK: %d quoted values re-derived from committed per-corner evidence and "
    "matched at the precision written (%d of them group-sequence derivations "
    "over %d groups, %d adjacent-axis pair(s) examined; %d magnitude bound(s) "
    "over %d signed value(s), %d of them on the far side of zero from the "
    "binding end); %d further figure(s) "
    "derived against %d ratified constant(s) read from the spec and its "
    "decision records (%s); %d "
    "in-record table(s) read, %d checked row-for-row "
    "against the committed logs by point id and %d by row count alone; all %d "
    "section 5 rows accounted for (%d graded, %d with a stated reason) and %d "
    "ungraded figure(s) in graded rows disclosed and still present in their "
    "row; Icp trim-code rule read from %s (%d reference frequencies)"
    % (
        checked,
        seq_stats["derivations"],
        seq_stats["groups"],
        seq_stats["pairs"],
        mag_stats["bounds"],
        mag_stats["values"],
        mag_stats["opposite"],
        derived_checked,
        len(constants_used),
        "; ".join(
            "%s = %g" % (name, resolved_constants[name][0])
            for name in sorted(constants_used)
            if resolved_constants.get(name)
        ) or "none",
        record_table_stats["id_matched"] + record_table_stats["count_matched"],
        record_table_stats["id_matched"],
        record_table_stats["count_matched"],
        len(spec_row_order),
        len(graded_rows),
        len(excluded_rows),
        disclosed_figures,
        spec_rel,
        len(icp_rule),
    )
)
PY
