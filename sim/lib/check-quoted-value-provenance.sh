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
# Section 5.1 of the proposal carries three tables. The first names, for each
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
# The third names the headline figures INSIDE graded rows that are still not
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
#    sim/*/records/<id>.md, and the named evidence file must exist at
#    sim/<campaign>/corners/<id>/<file>. A reduction over a file that is not
#    committed is not reproducible by a reader.
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
#    5.1's third table names each of those, and this check requires that each
#    entry names a real section 5 row, that the row is one this check grades
#    (a fully excluded row's figures are the exclusion table's business), that
#    the figure is not also a graded value for that row, that a reason is
#    given -- and that the figure STILL APPEARS VERBATIM in the row. That last
#    rule is the one with teeth: before it existed the list was prose, and it
#    had already gone wrong. It named four ungraded figures and missed a fifth
#    (the output band row's `27 %` worst adjacent-band overlap, which was
#    neither graded nor disclosed until it was graded in this pass).
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
# It reduces committed CSVs only. It never runs a simulator, reads no logfile,
# and cannot tell whether the simulation behind a CSV was the right experiment
# -- that is what the record's own Methodology field and its campaign's
# testbench are for.
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
#   min|max|mean|sum(adjacent-overlap(COL by AXIS) by KEY[+KEY...])
#       Per group, the worst (smallest) fractional overlap between the COL
#       intervals of consecutive AXIS values: max(COL at k) / min(COL at k+1)
#       - 1, where negative is a hole rather than an overlap. A group with no
#       pair of consecutive AXIS values is an error.
#
# any of which may carry ` where COND[ and COND...]`, where COND is
# `COL OP LITERAL` with OP one of == != < <= > >=. A literal that parses as a
# number is compared numerically, otherwise as a string (== and != only).
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
# Usage: sim/lib/check-quoted-value-provenance.sh
# Exit codes: 0 every graded value re-derives, every section 5 row is accounted
#             for, and every disclosed ungraded figure is still in its row;
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


# --------------------------------------------------------------- reductions ---

COND = re.compile(r"^([A-Za-z_][\w.]*)\s*(==|!=|<=|>=|<|>)\s*(.+)$")


def make_predicate(where, icp_rule, ctx):
    """` where ...` -> a function of one CSV row. None means "every row"."""
    if not where:
        return lambda row: True
    tests = []
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
            continue
        m = COND.match(clause)
        if not m:
            fail("%s: cannot parse where-clause `%s`" % (ctx, clause))
            return None
        col, op, literal = m.group(1), m.group(2), m.group(3).strip().strip("`")
        lit_num = as_float(literal)
        if lit_num is None and op not in ("==", "!="):
            fail(
                "%s: where-clause `%s` orders a non-numeric literal; only == "
                "and != are defined for strings" % (ctx, clause)
            )
            return None
        tests.append(("cmp", (col, op, literal, lit_num), None))

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
            if col not in row:
                return False
            cell = row[col]
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


AGGS = {
    "min": min,
    "max": max,
    "mean": lambda vs: sum(vs) / len(vs),
    "sum": sum,
}

OUTER = re.compile(r"^(min|max|mean|sum|count)\((.*)\)$", re.DOTALL)
INNER_BY = re.compile(r"^(min|max|mean|sum)\((.*)\)\s+by\s+([\w+.]+)$", re.DOTALL)

# A group-sequence derivation: the group's rows are a SEQUENCE along an axis,
# and the figure is a property of that sequence rather than a reduction of its
# cells. `non-monotonic` is a group *predicate* (true or false of one curve, so
# only count(...) is defined over it); `adjacent-overlap` is a group *scalar*.
SEQ_PREDICATES = ("non-monotonic",)
SEQ_SCALARS = ("adjacent-overlap",)
SEQ_VERBS = SEQ_PREDICATES + SEQ_SCALARS
INNER_SEQ = re.compile(
    r"^(" + "|".join(SEQ_VERBS) + r")\(\s*([\w.]+)\s+by\s+([\w.]+)\s*\)"
    r"\s+by\s+([\w+.]+)$",
    re.DOTALL,
)

#: How many group-sequence derivations ran, and over how many groups. Reported
#: in the OK line because the headline figure one of them grades is a ZERO: a
#: derivation that quietly examined nothing would produce the same 0 as a
#: derivation that examined 504 curves and found none violating.
seq_stats = {"derivations": 0, "groups": 0}


def group_sequences(rows, keys, columns, reduction, ctx):
    """Group `rows` by `keys`, keeping `columns` as floats. Fails loudly.

    Unlike the reduction path, a non-numeric or missing cell is an error here
    rather than a skipped row: a dropped point silently weakens a sequence
    test, and the figure these derivations grade is one a weakened test still
    reports as passing.
    """
    if rows:
        have = set(rows[0])
        for col in list(keys) + list(columns):
            if col not in have:
                fail(
                    "%s: reduction `%s` names column `%s`, which the evidence "
                    "file does not have (columns: %s)"
                    % (ctx, reduction, col, ", ".join(sorted(have)))
                )
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
        fail(
            "%s: reduction `%s` formed no groups at all. There is nothing to "
            "derive, and an empty derivation must not read as a passing zero."
            % (ctx, reduction)
        )
        return None
    return groups


def apply_group_sequence(outer, verb, col, axis, keys, rows, reduction, ctx):
    """Evaluate AGG(VERB(COL by AXIS) by KEY[+KEY...]). (value, is_count)."""
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
            "not defined -- use min/max/mean/sum" % (ctx, verb)
        )
        return None

    groups = group_sequences(rows, keys, [col, axis], reduction, ctx)
    if groups is None:
        return None
    seq_stats["derivations"] += 1
    seq_stats["groups"] += len(groups)

    if verb == "non-monotonic":
        violations = 0
        for key, points in sorted(groups.items()):
            ordered = sorted(points, key=lambda point: point[1])
            if len(ordered) < 2:
                fail(
                    "%s: group %s holds %d point(s); a sequence test over fewer "
                    "than two points is not a test"
                    % (ctx, "/".join(key), len(ordered))
                )
                return None
            axis_values = [point[1] for point in ordered]
            if len(set(axis_values)) != len(axis_values):
                fail(
                    "%s: group %s repeats a value of the ordering column `%s`, "
                    "so the sequence it would be tested as is ambiguous"
                    % (ctx, "/".join(key), axis)
                )
                return None
            series = [point[0] for point in ordered]
            steps = list(zip(series, series[1:]))
            rising = all(b >= a for a, b in steps)
            falling = all(b <= a for a, b in steps)
            if not rising and not falling:
                violations += 1
        return float(violations), True

    # adjacent-overlap: per group, the worst (smallest) fractional overlap
    # between the COL intervals of consecutive AXIS values. max(COL at k) /
    # min(COL at k+1) - 1; negative means a hole rather than an overlap.
    worst_per_group = []
    for key, points in sorted(groups.items()):
        spans = {}
        for value, step in points:
            low, high = spans.get(step, (value, value))
            spans[step] = (min(low, value), max(high, value))
        overlaps = []
        for step in sorted(spans):
            if step + 1 not in spans:
                continue
            upper, lower = spans[step][1], spans[step + 1][0]
            if lower == 0:
                fail(
                    "%s: group %s divides by a zero `%s` at %s+1"
                    % (ctx, "/".join(key), col, step)
                )
                return None
            overlaps.append(upper / lower - 1.0)
        if not overlaps:
            fail(
                "%s: group %s holds no pair of consecutive `%s` values, so it "
                "has no adjacent interval to overlap"
                % (ctx, "/".join(key), axis)
            )
            return None
        worst_per_group.append(min(overlaps))
    return AGGS[outer](worst_per_group), False


def apply_reduction(reduction, rows, icp_rule, ctx):
    """Evaluate a reduction over `rows`. Returns (value, is_count) or None."""
    m = OUTER.match(reduction.strip())
    if not m:
        fail("%s: cannot parse reduction `%s`" % (ctx, reduction))
        return None
    outer, body = m.group(1), m.group(2).strip()

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
        predicate = make_predicate(where, icp_rule, ctx)
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
                tuple(str(row.get(k, "")).strip() for k in keys.split("+")), []
            ).append(value)
        if not groups:
            fail("%s: reduction `%s` selected no rows" % (ctx, reduction))
            return None
        inner = [AGGS[inner_agg](v) for v in groups.values()]
        return AGGS[outer](inner), False

    sequence = INNER_SEQ.match(body)
    if sequence:
        return apply_group_sequence(
            outer,
            sequence.group(1),
            sequence.group(2).strip(),
            sequence.group(3).strip(),
            sequence.group(4).split("+"),
            rows,
            reduction,
            ctx,
        )
    if re.match(r"^(" + "|".join(SEQ_VERBS) + r")\(", body):
        fail(
            "%s: cannot parse reduction `%s` -- a group-sequence derivation is "
            "spelled AGG(VERB(COL by AXIS) by KEY[+KEY...]) and takes no "
            "where-clause" % (ctx, reduction)
        )
        return None

    target, _, where = [p.strip() for p in _split_where(body)]
    predicate = make_predicate(where, icp_rule, ctx)
    if predicate is None:
        return None
    selected = [row for row in rows if predicate(row)]

    if outer == "count":
        if target == "rows":
            return float(len(selected)), True
        if target.startswith("distinct "):
            keys = target[len("distinct ") :].strip().split("+")
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

    values = []
    for row in selected:
        if target not in row:
            fail(
                "%s: reduction `%s` names column `%s`, which the evidence file "
                "does not have (columns: %s)"
                % (ctx, reduction, target, ", ".join(sorted(row)))
            )
            return None
        value = as_float(row.get(target))
        if value is not None:
            values.append(value)
    if not values:
        fail("%s: reduction `%s` selected no numeric values" % (ctx, reduction))
        return None
    return AGGS[outer](values), False


def _split_where(body):
    parts = re.split(r"\s+where\s+", body, maxsplit=1)
    return (parts[0], "where", parts[1]) if len(parts) == 2 else (parts[0], "", "")


# ------------------------------------------------------------------ the tree ---

def read_csv_rows(path):
    with open(path, encoding="utf-8") as fh:
        lines = [line for line in fh if not line.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


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

tables = read_tables(proposal)

spec_rows = None          # normalized name -> (cells, source records)
spec_row_order = []
provenance = None
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

    rows = []
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
    if not resolved or not rows:
        if resolved:
            fail("%s: the evidence file(s) hold no data rows" % ctx)
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

    result = apply_reduction(reduction, rows, icp_rule, ctx)
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
    "over %d groups); all %d section 5 rows accounted for (%d graded, %d with a "
    "stated reason) and %d ungraded figure(s) in graded rows disclosed and "
    "still present in their row; Icp trim-code rule read from %s (%d reference "
    "frequencies)"
    % (
        checked,
        seq_stats["derivations"],
        seq_stats["groups"],
        len(spec_row_order),
        len(graded_rows),
        len(excluded_rows),
        disclosed_figures,
        spec_rel,
        len(icp_rule),
    )
)
PY
