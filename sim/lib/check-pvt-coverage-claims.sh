#!/usr/bin/env bash
#
# Fails if a reader-facing status document quotes a measurement at a process
# corner without saying which PVT grid that corner belongs to, or states a
# corner count no committed evidence produces.
#
# WHY THIS EXISTS (issue #237)
#
# CLAUDE.md's standing rule for this repository is "PVT corners on every
# recorded result", and #237's first acceptance criterion is closed-loop
# behavior "verified across the full PVT corner matrix, not just the single
# nominal corner". Seven checks already grade docs/chipalooza/
# challenge-5-proposal.md -- its counts, its layout claims, its citations and
# their supersession, its spec-row and decision-record coverage, its I/O list,
# and its forge references. Every one of them grades *what* the document says.
# None grades *where the number was measured*.
#
# That gap had a consequence, found on 2026-09-25 and fixed in the same commit
# that added this check. Section 5's table reports most rows against the
# 45-point mandated grid and says so -- "Full 45-point PVT grid", "All 45 of
# the mandated PVT points", "5 of 45 PVT points measured, not the full grid".
# Four rows in the same column report a worst case at `all-fast` or `all-slow`:
#
#   Output band       floor 6.449 MHz  (`all-fast`/125 °C/2.97 V)
#   Period jitter     2.51 % RMS       (`all-slow`/-40 °C/2.97 V)
#   Power             1.98 mW          (`all-fast`/125 °C/3.63 V)
#   Kvco              115.8 MHz/V      (`all-fast`/27 °C/2.97 V)
#
# `all-fast` and `all-slow` are not in the mandated grid. sim/harness/corners.py
# defines them as combined bundles -- every device family skewed together,
# passives included -- outside the five MOS bundles (`typical`/`ff`/`ss`/`fs`/
# `sf`) that grid is built from. The records behind those four rows say so
# plainly; sim/vco-tuning-range/records/20260731-175947-0a12e6c.md's own corner
# field reads "The PVT grid is 63 points, a **superset** of the 45-point default
# grid". None of that reached the document written to be emailed verbatim to an
# outside reader, who had no way to tell that four rows of one table are worst
# cases over a different -- and wider, hence stricter -- corner universe than
# the rest of it. The numbers were right; the grid they were measured on was
# not stated.
#
# THE RULES
#
# 1. CORNER NAMES ARE REAL. Every process bundle a graded document names in a
#    corner triple (`` `<bundle>`/<T> °C/<V> V ``) must be a key of
#    sim/harness/corners.py's CORNERS registry. A bundle renamed or dropped
#    from the harness leaves a stale corner name in an outward-facing document
#    that nothing else would catch.
#
# 2. OFF-GRID ROWS ARE DISCLOSED. A table row is off the mandated grid if
#    EITHER of two things is true:
#
#      (a) it QUOTES a corner triple whose bundle is not one of
#          REQUIRED_MOS_CORNERS; or
#      (b) a record it CITES has committed per-corner evidence at such a
#          bundle -- whatever corner the row chose to quote.
#
#    Such a row must name the grid it was measured on: an `<N>-point` or
#    `<N>-bundle` token equal to the distinct PVT-point count, or the
#    distinct-bundle count, of a record the row cites, and not equal to the
#    mandated grid's own 45 / 5, since a disclosure that repeats the mandated
#    numbers discloses nothing.
#
#    Both spellings are accepted because both are already in honest use:
#    sim/CHARACTERIZATION.md's `lock-window-trim` row says "the full 13-bundle"
#    set and passes this rule unchanged, while the vco-tuning-range rows are
#    naturally stated as a 63-point grid.
#
#    Trigger (b) was added on 2026-09-25, after trigger (a) alone was found to
#    be a disclosure rule keyed on WHAT A ROW HAPPENS TO SAY. A row can rest
#    entirely on a 13-bundle campaign and stay silent simply by quoting only
#    its `ss` and `fs` corners -- which is exactly what the proposal's Lock
#    detector row did. Its five cited records (`lock-detector`,
#    `lock-window-trim`, `lock-window-sizing` and two superseded predecessors)
#    each cover 117 PVT points across 13 bundles, and the row said 205 points
#    and nothing about the grid. Four more rows across two documents were in
#    the same state, including `sim/CHARACTERIZATION.md`'s `harness-selftest`
#    row, which called a record's grid "45-point" when that record's own
#    corner field reads "63 point full-factorial grid" over 7 bundles -- an
#    error rule 3 structurally cannot catch, because it allows the mandated
#    size unconditionally.
#
#    Trigger (b) also accepts a SUBSET disclosure, which trigger (a) could
#    not: `devchar-passives` sweeps `typical`/`all-fast`/`all-slow` at one
#    supply, 9 points across 3 bundles -- off the mandated grid in both
#    directions at once. "9-point" and "3-bundle" are honest names for it, so
#    the token is required to differ from the mandated numbers rather than to
#    exceed them.
#
# 3. CORNER COUNTS HAVE EVIDENCE BEHIND THEM. Every PVT-qualified corner or
#    grid count in a graded table row -- "10/45 corners", "5 of 45 PVT points",
#    "full 90-point grid" -- must equal the mandated grid size or a count the
#    committed per-corner evidence of a record cited in that row actually
#    produces (its distinct PVT-point count, or the row count of one of its
#    committed CSVs). A count matching nothing on the tree is a number with no
#    evidence behind it.
#
#    Deliberately narrow: only counts qualified by "corner", "PVT point" or
#    "<N>-point grid" are graded. A bare "<N> points" is left alone, because
#    this tree uses it for run counts on extra sweep axes (90 output-driver
#    runs = 45 PVT points x 2 band edges; 205 lock-detector points; 140
#    loop-dynamics cells) that are not PVT grids and must not be forced to look
#    like one.
#
# 4. A CLAIM OF FULL MANDATED COVERAGE IS CHECKED POINT BY POINT. A row that
#    says it covers the whole mandated grid -- "Full 45-point PVT grid", "all
#    45 of the mandated PVT points", "45/45" -- must cite record(s) whose
#    committed per-corner evidence, taken in UNION, contains every one of the
#    mandated (bundle, temperature, supply) triples. Not the count: the points.
#
#    Rule 3 cannot do this, and not by oversight. Its allowed-count set starts
#    at {MANDATED_GRID} unconditionally, because "of 45" is a legitimate thing
#    for a row to say about a grid it only partly measured ("5 of 45 PVT points
#    measured, not the full grid" is the reference-spur row, and is honest).
#    The cost of that unconditional allowance is that the strongest claim in
#    the table -- I measured all of it -- is the one claim nothing verified.
#    Rules 1 and 2 do not reach it either: both grade corners that ARE named,
#    and a row overclaiming full coverage is characterized by the corners it
#    does not name.
#
#    The union matters as much as the rule. `sim/period-jitter` reached the
#    mandated 45 across five records that cover 1, 4, 8, 18 and 16 points; no
#    single one of them covers the grid, and a per-record test would reject the
#    honest row. A sixth record re-measures 2 of those points against #273's
#    wrap-safe lock gate and adds no new corner -- so citing it alone would
#    satisfy a count-based rule at 2 points and a point-based one at none.
#
#    Trigger (b) of rule 2 grades evidence WIDER than the grid; this rule
#    grades evidence NARROWER than the grid the row claims. Added on
#    2026-09-25 after a sweep of all three graded documents for full-coverage
#    claims found one row resting on nothing: `sim/CHARACTERIZATION.md`'s
#    Verification-owed cross-reference said the deterministic jitter component
#    is "measured at all 45 of the mandated PVT corners" and cited campaign
#    directories rather than records, so there was no evidence for the check --
#    or for a reader -- to reach. The claim was true; it was unsupported in the
#    place it was made. That sweep found 13 rows making a full-coverage claim;
#    the other 12 were verified point-by-point against the union of their own
#    citations in the same pass, and the count this check prints on success is
#    that same number.
#
# THE MANDATED GRID SIZE IS DERIVED, NOT WRITTEN DOWN HERE
#
# It is len(REQUIRED_MOS_CORNERS) x len(DEFAULT_TEMPERATURES_C) x
# len(supply_points()), imported from sim/harness/corners.py. Widening the
# temperature axis or the supply tolerance changes the number this check
# enforces in the same commit that changes the harness, rather than leaving a
# remembered 45 behind in eight documents.
#
# WHAT IT DOES NOT DO
#
# It does not check that a quoted *value* is the value in the cited record --
# that is a different and much larger check. It grades the corner a value is
# attributed to and the grid that corner sits in. A row that quotes no corner
# triple, no corner count and no full-coverage claim is trivially clean; so is
# a derived or waived row.
#
# Rule 4 does not check that the cited evidence covering the grid is evidence
# OF the claim. A row could satisfy it by citing an unrelated record that
# happens to run the mandated grid, exactly as rule 2's disclosure tokens could
# be satisfied by an unrelated record's width before `names_its_grid` narrowed
# them to the off-grid candidates. The rule grades that a full-coverage claim
# has full-coverage evidence behind it and that a reader can follow the
# citation to it; pairing a claim with the right record is the reader's job,
# and the record's own campaign name is what makes it doable.
#
# Rule 4 is also row-scoped, like rules 2 and 3. Full-coverage claims made in
# prose -- the proposal's numbered "Known gaps" list restates several -- are
# not graded, because prose has no citation column to check them against.
#
# Two grid-shape claims are also still taken on trust, both of them hand-
# verified and written into section 5.0 of the proposal rather than graded
# (issue #516):
#
#   * A record whose corner axis is NOT the MOS grid. sim/loop-dynamics sweeps
#     the passive loop filter over 27 passive-corner bundles x 3 temperatures
#     and declares the MOS and supply axes N/A; its committed artifacts are
#     named for filter corners, so evidence() returns zero points and zero
#     bundles -- indistinguishable here from a parser that found nothing.
#   * A deliberately non-rectangular sample of a cross-product.
#     sim/divider-ratio-chain runs 235 of the 2835 cells of a 61-N x 45-corner
#     product; every bundle it touches is on-grid and its PVT point set IS the
#     mandated 45, so both triggers above pass it.
#
# Usage: sim/lib/check-pvt-coverage-claims.sh
# Exit codes: 0 every quoted corner is a real bundle, every off-grid corner is
#             disclosed, every corner count is backed by evidence, and every
#             claim of full mandated coverage cites evidence that covers it;
#             1 any rule fails, a graded document is missing, the harness
#             cannot be imported, or the document yields no corner triples at
#             all (a broken parser must not look like a clean document).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The same three reader-facing documents check-record-supersession.sh grades,
# for the same reason: they are read by people who will not open sim/.
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
import csv
import os
import re
import sys

repo_root, graded = sys.argv[1], sys.argv[2:]

sys.path.insert(0, os.path.join(repo_root, "sim"))
try:
    from harness.corners import (
        CORNERS,
        DEFAULT_TEMPERATURES_C,
        REQUIRED_MOS_CORNERS,
        supply_points,
    )
except Exception as exc:  # pragma: no cover - exercised by the import-guard test
    sys.stderr.write(
        "FAIL: could not import sim/harness/corners.py (%s) -- the mandated "
        "grid size and the corner registry are derived from it, so this check "
        "cannot run\n" % exc
    )
    sys.exit(1)

MANDATED_BUNDLES = len(REQUIRED_MOS_CORNERS)
#: Every (bundle, temperature, supply) triple the mandated grid is made of --
#: the same product whose size is MANDATED_GRID, kept as points because rule 4
#: has to say *which* of them a row's evidence is missing.
MANDATED_POINTS = frozenset(
    (bundle, float(temp), float(vdd))
    for bundle in REQUIRED_MOS_CORNERS
    for temp in DEFAULT_TEMPERATURES_C
    for vdd in supply_points()
)
MANDATED_GRID = len(MANDATED_POINTS)
assert MANDATED_GRID == (
    MANDATED_BUNDLES * len(DEFAULT_TEMPERATURES_C) * len(supply_points())
), "the mandated grid is a full-factorial product; a duplicate axis value broke it"

RECORD_ID = r"\d{8}-\d{6}-[0-9a-f]{7}"

#: `` `all-fast`/125 °C/2.97 V `` -- the corner spelling every graded document
#: uses. The degree sign is optional because README.md writes one without it.
CORNER_TRIPLE = re.compile(
    r"`([A-Za-z][A-Za-z0-9_-]*)`\s*/\s*[-−]?\d+\s*°?\s*C"
)

#: A corner-file stem: `<bundle>_<temp>c_<vdd>v`, possibly behind a
#: campaign-specific prefix (`jit_all-fast_-40c_2.97v.log`). Anchored on a known
#: bundle name so a prefix is never mistaken for one.
_BUNDLE_ALT = "|".join(
    re.escape(name) for name in sorted(CORNERS, key=len, reverse=True)
)
CORNER_FILE = re.compile(
    r"(?:^|[_/])(" + _BUNDLE_ALT + r")_(-?\d+)c_([0-9.]+)v"
)

#: "10/45 corners", "5 of 45 PVT points", "2 of the 45 mandated corners".
#: Qualified by `corner` or `PVT point` only -- see rule 3's note on bare
#: "<N> points".
DENOMINATOR = re.compile(
    r"\b\d+\s*(?:of\s+(?:the\s+)?|/)\s*(\d+)[\s -]+"
    r"(?:mandated[\s -]+)?(?:PVT[\s -]+point|corner)s?\b"
)
#: "Full 45-point PVT grid", "full 90-point grid", "63-point superset grid".
GRID_SIZE = re.compile(
    r"\b(\d+)[\s -]point"
    r"(?:[\s -]+(?:mandated|PVT|superset|default))*[\s -]+grid\b"
)
#: Rule 2's disclosure tokens: "63-point", "13-bundle", "13 bundles".
DISCLOSURE = re.compile(r"\b(\d+)[\s -]*(?:point|bundle)s?\b")

#: Rule 4's claim forms, in the spellings the three graded documents already
#: use: "Full 45-point PVT grid", "full 45-corner sweep", "full mandated
#: 45-point grid", "All 45 of the mandated PVT points".
FULL_COVERAGE = re.compile(
    r"\b(?:full|complete|all)\s+(?:the\s+)?(?:mandated\s+)?(\d+)"
    r"(?:[\s-]*(?:point|corner)"
    r"|\s+of\s+(?:the\s+)?(?:mandated[\s-]+)?(?:PVT[\s-]+)?(?:point|corner))",
    re.IGNORECASE,
)
#: The same claim written as a saturated fraction: "45/45", "45 of 45". Both
#: sides must be the same number, so "0 of 45" and "5 of 45" are untouched --
#: those are rule 3's, and are honest statements of partial coverage.
FULL_FRACTION = re.compile(r"\b(\d+)\s*(?:/|\s+of\s+(?:the\s+)?)\s*(\d+)\b")

#: A Source cell that defers to the row above instead of repeating the id.
SAME_RECORD = re.compile(r"\bSame\s+(?:record|as\s+above)\b", re.IGNORECASE)


def _f(text):
    try:
        return float(text)
    except ValueError:
        return text


_evidence_cache = {}


def evidence(record_id):
    """(the set of distinct PVT points, the set of distinct bundles, {CSV rows}).

    Read from sim/<campaign>/corners/<record-id>/ -- the committed per-corner
    artifacts of that record, which is the only place the tree says how much of
    a grid a run actually covered. Points are normalized to (bundle, float
    temperature, float supply) so a log stem (`ss_-40c_2.97v`) and a CSV row
    (`ss`, `-40.0`, `2.97`) count once, not twice.
    """
    if record_id in _evidence_cache:
        return _evidence_cache[record_id]
    points, bundles, rows = set(), set(), set()
    sim_dir = os.path.join(repo_root, "sim")
    for campaign in sorted(os.listdir(sim_dir)):
        corner_dir = os.path.join(sim_dir, campaign, "corners", record_id)
        if not os.path.isdir(corner_dir):
            continue
        for name in sorted(os.listdir(corner_dir)):
            for match in CORNER_FILE.finditer(name):
                bundle, temp, vdd = match.groups()
                points.add((bundle, _f(temp), _f(vdd)))
                bundles.add(bundle)
            if not name.endswith(".csv"):
                continue
            path = os.path.join(corner_dir, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = [ln for ln in fh if not ln.startswith("#")]
            table = list(csv.DictReader(lines))
            if not table:
                continue
            rows.add(len(table))
            head = table[0]
            bundle_col = next((c for c in ("corner", "bundle") if c in head), None)
            vdd_col = next((c for c in ("vdd", "vdd_v") if c in head), None)
            if not (bundle_col and "temp_c" in head and vdd_col):
                continue
            for row in table:
                points.add((row[bundle_col], _f(row["temp_c"]), _f(row[vdd_col])))
                bundles.add(row[bundle_col])
    result = (frozenset(points), frozenset(bundles), rows)
    _evidence_cache[record_id] = result
    return result


def names_its_grid(tokens, candidates):
    """True if the row names the grid one of ``candidates`` was measured on.

    ``candidates`` is the off-grid record(s) the row must account for -- not
    every record it cites. A number that happens to match some *on-grid*
    record's coverage is not a disclosure of the off-grid one: the aggregation
    row for `period-jitter` says "16 points" about the `fs`/`sf` block that
    completed its 45-point grid, and that must not excuse its silence about
    the 63-point `vco-tuning-range` record in the same cell.

    The token must not be the mandated grid's own 45 / 5 either: repeating the
    mandated numbers is not a disclosure that the row is off them.
    """
    for rid in candidates:
        points, bundles, _ = evidence(rid)
        for count in (len(points), len(bundles)):
            if count and count not in (MANDATED_GRID, MANDATED_BUNDLES):
                if count in tokens:
                    return True
    return False


failed = False
triples_seen = 0
counts_seen = 0
disclosures_seen = 0
full_claims_seen = 0

for doc in graded:
    doc_path = os.path.join(repo_root, doc)
    if not os.path.isfile(doc_path):
        sys.stderr.write("FAIL: %s does not exist\n" % doc)
        failed = True
        continue
    with open(doc_path, encoding="utf-8") as fh:
        text = fh.read()

    # Rule 1, document-wide: a corner name anywhere must be a real bundle.
    for bundle in sorted(set(CORNER_TRIPLE.findall(text))):
        triples_seen += 1
        if bundle in CORNERS:
            continue
        failed = True
        sys.stderr.write(
            "FAIL: %s quotes a measurement at corner `%s`, which is not a "
            "bundle sim/harness/corners.py defines. Known bundles: %s\n"
            % (doc, bundle, ", ".join(sorted(CORNERS)))
        )

    # Rules 2 and 3 are row-scoped: a table row is the unit that carries both a
    # number and the citation that number rests on.
    inherited = []
    for line in text.splitlines():
        if not line.startswith("| "):
            inherited = []
            continue
        cited = re.findall(RECORD_ID, line)
        if cited:
            inherited = cited
        elif SAME_RECORD.search(line):
            cited = inherited
        allowed = {MANDATED_GRID}
        measured = set()
        for rid in cited:
            points, _, row_counts = evidence(rid)
            if points:
                allowed.add(len(points))
            allowed |= row_counts
            measured |= points

        # Rule 2, trigger (a): the row quotes a corner outside the grid.
        quoted_off_grid = sorted(
            {
                b
                for b in CORNER_TRIPLE.findall(line)
                if b in CORNERS and b not in REQUIRED_MOS_CORNERS
            }
        )
        # Rule 2, trigger (b): the row's evidence sits outside the grid,
        # whatever corner it chose to quote.
        measured_off_grid = []
        for rid in cited:
            _, bundles, _ = evidence(rid)
            extra = sorted(bundles - REQUIRED_MOS_CORNERS)
            if extra:
                measured_off_grid.append((rid, extra))

        if quoted_off_grid or measured_off_grid:
            tokens = {int(n) for n in DISCLOSURE.findall(line)}
            widths = [
                (rid, len(evidence(rid)[0]), evidence(rid)[1]) for rid in cited
            ]
            # A row that only *quotes* an off-grid corner has no off-grid
            # record to point at, so every record it cites is a candidate.
            candidates = [rid for rid, _ in measured_off_grid] or cited
            if names_its_grid(tokens, candidates):
                disclosures_seen += 1
            else:
                failed = True
                why = []
                if quoted_off_grid:
                    why.append(
                        "quotes a measurement at %s"
                        % ", ".join("`%s`" % b for b in quoted_off_grid)
                    )
                if measured_off_grid:
                    why.append(
                        "rests on evidence measured at %s"
                        % "; ".join(
                            "%s (%s)" % (rid, ", ".join("`%s`" % b for b in extra))
                            for rid, extra in measured_off_grid
                        )
                    )
                sys.stderr.write(
                    "FAIL: %s %s, which sim/harness/corners.py places outside "
                    "the %d-point mandated grid's %d MOS bundles, and the row "
                    "does not say which grid it came from. Name the grid in "
                    "the row -- an `<N>-point` or `<N>-bundle` token matching "
                    "the cited record's own coverage, and not the mandated "
                    "%d / %d%s.\n  row: %s\n"
                    % (
                        doc,
                        " and ".join(why),
                        MANDATED_GRID,
                        MANDATED_BUNDLES,
                        MANDATED_GRID,
                        MANDATED_BUNDLES,
                        (
                            " (" + "; ".join(
                                "%s covers %d PVT points across %d bundles"
                                % (rid, pts, len(bnd))
                                for rid, pts, bnd in widths
                            ) + ")"
                        )
                        if widths
                        else ", and the row cites no record at all -- name one",
                        line.strip()[:220],
                    )
                )

        # Rule 3.
        for pattern in (DENOMINATOR, GRID_SIZE):
            for match in pattern.finditer(line):
                counts_seen += 1
                count = int(match.group(1))
                if count in allowed:
                    continue
                failed = True
                sys.stderr.write(
                    "FAIL: %s states \"%s\", but %d is neither the %d-point "
                    "mandated grid nor a count the committed evidence of the "
                    "record(s) this row cites produces (%s).\n  row: %s\n"
                    % (
                        doc,
                        match.group(0).strip(),
                        count,
                        MANDATED_GRID,
                        ", ".join(str(n) for n in sorted(allowed)) or "none",
                        line.strip()[:220],
                    )
                )

        # Rule 4: a claim of full mandated coverage, checked point by point.
        claims = [
            m.group(0).strip()
            for m in FULL_COVERAGE.finditer(line)
            if int(m.group(1)) == MANDATED_GRID
        ]
        claims += [
            m.group(0).strip()
            for m in FULL_FRACTION.finditer(line)
            if m.group(1) == m.group(2) == str(MANDATED_GRID)
        ]
        if claims:
            full_claims_seen += 1
            missing = MANDATED_POINTS - measured
            if missing:
                failed = True
                shown = sorted(missing)[:4]
                sys.stderr.write(
                    "FAIL: %s claims %s, but the committed evidence of the "
                    "record(s) this row cites covers %d of the %d mandated PVT "
                    "points -- %d missing, e.g. %s%s. A row that claims the "
                    "whole mandated grid has to cite evidence that covers it%s."
                    "\n  row: %s\n"
                    % (
                        doc,
                        " and ".join('"%s"' % c for c in claims),
                        len(MANDATED_POINTS & measured),
                        MANDATED_GRID,
                        len(missing),
                        ", ".join(
                            "`%s`/%g °C/%g V" % (b, t, v) for b, t, v in shown
                        ),
                        " ..." if len(missing) > len(shown) else "",
                        (
                            " (the union across every record it cites is what "
                            "counts -- no one record has to cover the grid alone)"
                            if cited
                            else ", and the row cites no record at all -- name "
                            "the record(s) whose evidence covers it"
                        ),
                        line.strip()[:220],
                    )
                )

if not triples_seen:
    sys.stderr.write(
        "FAIL: no corner triple (`` `<bundle>`/<T> °C ``) was found in any of "
        "the %d graded documents. These documents quote corners throughout, so "
        "this is a parser failure, not a clean tree.\n" % len(graded)
    )
    failed = True

if failed:
    sys.exit(1)

print(
    "OK: %d distinct corner bundles quoted across %d documents are all in "
    "sim/harness/corners.py; %d row(s) quoting or resting on an off-grid "
    "corner name the grid they were measured on; %d PVT corner count(s) "
    "match the %d-point mandated grid or the cited record's committed "
    "evidence; %d row(s) claiming the full mandated grid cite evidence "
    "covering all %d of its points"
    % (
        triples_seen,
        len(graded),
        disclosures_seen,
        counts_seen,
        MANDATED_GRID,
        full_claims_seen,
        MANDATED_GRID,
    )
)
PY
