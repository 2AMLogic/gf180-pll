#!/usr/bin/env bash
#
# Fails if the Chipalooza proposal's I/O list disagrees with the design's own
# exported port list, or if its bench test plan never drives a pin that list
# declares.
#
# WHY THIS EXISTS (issue #237)
#
# #237's acceptance criterion AC4 names four deliverables the proposal must
# carry: "block type, I/O list, functional description, spec table". The spec
# table is graded by spec/lib/check-spec-row-coverage.sh; the layout claims by
# layout/lib/check-layout-status-claims.sh; the cited evidence by
# sim/lib/check-record-supersession.sh; the counts by the two status checks.
# Nothing graded the I/O list -- the one deliverable whose source of truth is
# not a document at all but `design/netlist/pll_top.spice`, the committed
# export of design/pll_top.sch.
#
# The simulation side of this repository already refuses to drift from that
# file: sim/lib/pll_top_dut.sh carries CLOOP_PORTS and aborts any closed-loop
# run whose netlist port list does not match it, name for name and in order,
# "since the instance line below is positional". The document written to be
# emailed verbatim to an outside reader had no such guard, and it is the one
# artifact whose reader cannot re-run anything to find out.
#
# That drift is not hypothetical. It has already happened once, in exactly the
# way this check would have caught:
#
#   - PR #418 (commit bfde9893, 2026-09-18) added `LDT0`-`LDT3` to
#     design/pll_top.sch and design/netlist/pll_top.spice as real top-level
#     ports.
#   - Three days later, issue #441 found section 2.2's pad table still had no
#     `LDT0`-`LDT3` entry -- "the proposal described a part that could not be
#     configured into its own ratified spec" (DR-015's own Context section).
#     Its digital-control-input total was stale at 18 of 24 against a real
#     22, and section 2.3's "18 configuration bits" sentence was stale by one
#     against a 21-bit set.
#   - DR-015 fixed the pad table and closed with: "Future harness integration
#     work (bench test plans, tester programming) can now cite `LDT0`-`LDT3`
#     as fixed, addressable pins." Section 4's bench test plan was never
#     updated, so the same omission survived one section further down.
#
# THE RULES
#
# 1. COVERAGE. Every port of `.subckt pll_top` must be named by some row of
#    section 2.2's pad table. This is the mechanical form of section 2.3's own
#    claim -- "Nothing in design/pll_top.sch's port list is dropped. Every pin
#    the schematic exposes is mapped to a slot above" -- which until now was
#    true only by hand-checking.
#
# 2. NO ORPHAN SIGNALS. Every signal the pad table's Signal(s) column names
#    must be a real exported port. The other direction of rule 1: without it,
#    renaming or removing a pin leaves a stale pad row sitting there looking
#    like coverage while the real pin goes unmapped.
#
# 3. THE QUOTED PORT LIST. Section 2.2 transcribes the `.subckt pll_top` line
#    into its prose, as the stated basis of the mapping ("is the port list
#    this table maps, unedited"). That transcription must be the netlist's
#    ports, all of them, in the netlist's order. A literal `+` continuation
#    marker is allowed anywhere in the quote, because the netlist wraps and
#    the document quotes the wrap.
#
# 4. PER-ROW COUNTS. A pad row whose Count-used cell reads "K of M" or
#    "K requested vs. J offered" must name exactly K signals. This is what
#    went stale first in the #441 incident -- a count is the cheapest thing in
#    a table to leave behind when the row beside it changes.
#
# 5. THE BENCH PLAN. Every exported port must be named somewhere in section 4,
#    the bench test plan. Section 4 opens by claiming "All measurements below
#    use only the pads in section 2.2", which says nothing about whether it
#    uses all of them; a pad the plan never mentions is a pad the bench
#    operator never drives.
#
#    Found on 2026-09-25, and fixed in the commit that added this check: the
#    plan named neither `LDT0`-`LDT3` nor `IBN`/`ICN`/`IBP`/`ICP`. Both
#    omissions are load-bearing rather than cosmetic. The four bias currents
#    are what every closed-loop record in sim/ drives from ideal sources at
#    8 uA -- without them the charge pump does nothing and no step of the plan
#    works at all. The trim pins are worse than absent: the plan's step 7
#    compares `LOCK` against spec/pll.md's lock-detector targets, and
#    spec/pll.md says in terms that "a part left untrimmed is outside this
#    specification" (no fixed code holds the [1, 2] ns band across PVT), so
#    that step as written would have read an in-family part as a failure.
#
# 6. THE BUDGET'S CATEGORIES. Every pad row's Challenge-slot cell must name a
#    slot category that section 2.2's own transcribed budget lists, and any
#    cap the row states -- "budget <= 24" in the slot cell, the M of a
#    "K of M" count, the "J offered" of a "K requested vs. J offered" -- must
#    equal that category's transcribed cap.
#
#    The taxonomy is read out of the document, never encoded here: the
#    categories and their caps come from the sentence that transcribes the
#    budget ("one bandgap-referenced bias voltage, up to 2 bandgap-referenced
#    current sources, ..."), so amending that sentence moves what CI enforces
#    in the same commit. That is the answer to the objection this file used to
#    carry in its own "what it does not do" -- that a totals rule would have to
#    encode the category taxonomy and would then be grading the check's model
#    of the document rather than the document.
#
# 7. TOTALS ARE THE SUM OF THE ROWS. Section 2.2 closes with a totals
#    paragraph stated per budget category. For each category, the total's
#    upper figure must equal the sum of every pad row carrying that slot, and
#    its lower figure the sum of the rows that are not marked "(proposed)" --
#    which is what makes "1-3 of <= 12 digital test outputs" a legal way to
#    report one mandatory and two optional pins. A row that states a count
#    contributes that count (rule 4 already ties it to the signals beside it);
#    a rail row, which states none, contributes the pins it names.
#
# 8. EVERY CATEGORY IS TOTALLED. Every category the transcribed budget names
#    must appear in the totals paragraph, and every category the totals
#    paragraph names must be one the budget transcribes. A category with no
#    pad rows is reported as "0 of 1" (the bandgap bias voltage is), not
#    omitted -- the paragraph says "every category", so a silently absent line
#    is the omission that claim forbids.
#
#    Found on 2026-09-25, and fixed in the commit that added these rules: the
#    three rail rows mapped `VDD`/`VSS`, `VDD_VCO`/`GND_VCO` and `VDD_DIV` to
#    a slot -- "3.3 V digital rail" -- that the transcribed budget does not
#    have, and the totals paragraph, which claims to cover every category,
#    never mentioned the five pads at all. That is not a bookkeeping nicety:
#    the table's own Notes require `VDD`, `VDD_VCO` and `VDD_DIV` to be three
#    electrically distinct nodes, so a harness that budgets rails per block
#    was being asked for a number this document never stated. The fix states
#    the rail line in the budget transcription as an explicit absence ("no
#    transcribed line at all for supply/ground pads"), which these rules then
#    hold the table and the totals to.
#
# 9. THE CONFIGURATION-BIT COUNT. Section 2.3's "N configuration bits (...)"
#    sentence must state the count its own bus list expands to; every bit it
#    names must be a pin of some pad row in a single slot category; and every
#    other pin in that category must be named in the same paragraph -- which
#    is how `REF`, a continuously toggling input rather than a static level,
#    is legitimately excluded from the count while `B0`..`SEL5` are not.
#
#    This is the other half of the #441 drift, and the document says so in its
#    own voice: "the prior revision of this sentence read 18 configuration
#    bits for the 17-bit set that existed before LDT0-LDT3 were pins at all --
#    an off-by-one". Rule 4 grades a count against the row beside it; nothing
#    graded the count that lives two sections away in prose.
#
# WHAT IT DOES NOT DO
#
# It grades presence, not adequacy: it cannot tell a bench step that drives a
# pin correctly from one that merely mentions it, and it says nothing about
# whether a pad row's slot assignment or its Notes are right -- rules 6-8
# grade that a slot is a category the budget offers and that the arithmetic
# over it closes, not that a pin belongs in that category rather than another.
# Nor does it grade the transcription itself: the challenge's own rules page
# is the authority for what the slot counts are, and confirming them is stated
# in section 2.2 as the submitting operator's job.
#
# Usage: design/lib/check-io-list-coverage.sh
# Exit codes: 0 the proposal's I/O list matches the exported port list, its
#               bench plan names every pin, and its Challenge-budget
#               accounting closes over its own pad rows,
#             1 a port is unmapped, a pad row names a port that does not
#               exist, the quoted port list disagrees with the netlist, a row
#               count disagrees with the signals beside it, the bench plan
#               omits a pin, a pad row's slot is not a transcribed budget
#               category, a stated cap disagrees with the transcribed one, a
#               category total disagrees with the rows beneath it, a category
#               has no total, section 2.3's configuration-bit count disagrees
#               with its own bus list, a graded file is missing, or any of the
#               netlist, the pad table, the budget transcription, the totals
#               paragraph or the configuration-bit sentence fails to parse (a
#               broken parser must not look like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

NETLIST="design/netlist/pll_top.spice"
PROPOSAL="docs/chipalooza/challenge-5-proposal.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${NETLIST}" "${PROPOSAL}" <<'PY'
import os
import re
import sys

repo_root, netlist_rel, proposal_rel = sys.argv[1], sys.argv[2], sys.argv[3]

#: A port name as the netlist and the document both spell them: uppercase,
#: digits and underscores (REF, B0, LDT3, VDD_VCO, GND_VCO).
IDENT = r"[A-Z][A-Z0-9_]*"

#: `LDT0`...`LDT3`, `B0..B2`, `CPB0..1`, `P5..P0`, `LDT3:LDT0` -- every range
#: spelling either section uses, with the backticks optionally inside or
#: outside the connector, and either index order.
RANGE = re.compile(
    r"(?<![A-Za-z0-9_`])"
    r"`?(?P<a>[A-Z][A-Z0-9_]*?)(?P<i>\d+)`?"
    r"\s*(?:…|\.\.\.|\.\.|:)\s*"
    r"`?(?P<b>[A-Z][A-Z0-9_]*?)?(?P<j>\d+)`?"
)

#: A whole code span that is nothing but one identifier. Requiring the whole
#: span keeps `spec/pll.md#kvco` and `SEL_(k-1)=1` from reading as pin names.
SPAN = re.compile(r"`([^`]+)`")

#: "1 of 24", "**4 requested** vs. 2 offered" -- the two shapes the pad
#: table's Count-used column uses for a row that states a number at all.
COUNT = re.compile(r"^\**\s*(\d+)\s*\**\s+(?:of|requested)\b")

#: A Count-used cell's stated budget: the M of "1 of 24", the J of
#: "4 requested vs. 2 offered". Read on the normalized cell.
COUNT_BUDGET = re.compile(
    r"^\s*\d+\s+(?:of\s+(?P<of>\d+)\b|requested\s+vs\.?\s+(?P<offered>\d+)\s+offered)"
)

#: One entry of section 2.2's transcribed budget: "one bandgap-referenced bias
#: voltage", "up to 24 digital control inputs". Read on the normalized,
#: code-span-stripped clause that follows the colon.
BUDGET_ENTRY = re.compile(
    r"(?:up to\s+(?P<n>\d+)|(?P<one>\bone\b))\s+"
    r"(?P<name>[a-z][a-z0-9 /-]*?)(?=\s*(?:,|;|$))"
)

#: The same sentence's way of transcribing a category the budget has no slot
#: count for at all -- "no transcribed line at all for supply/ground pads".
#: Written as an absence on purpose: a category left out entirely is one no
#: rule below can hold the table to.
BUDGET_ABSENT = re.compile(
    r"no transcribed line(?: at all)? for\s+(?P<name>[a-z][a-z0-9 /-]*?)"
    r"(?=\s*(?:,|;|$))"
)

#: One entry of the totals paragraph: "0 of 1 bandgap-referenced bias
#: voltage", "1-3 of <= 12 digital test outputs", "4 requested vs. 2 offered
#: bandgap-referenced current sources", "5 supply/ground pads". Read on the
#: normalized paragraph with its parenthetical asides removed.
TOTAL_ENTRY = re.compile(
    r"(?P<lo>\d+)\s*(?:-\s*(?P<hi>\d+))?\s+"
    r"(?:of\s+(?:≤|<=)?\s*(?P<cap>\d+)\s+"
    r"|requested\s+vs\.?\s+(?P<offered>\d+)\s+offered\s+)?"
    r"(?P<name>[a-z][a-z0-9 /-]*?)(?=\s*(?:,|\.|$))"
)

#: A cap stated inside a pad row's Challenge-slot cell: "(budget <= 24)",
#: "does not fit the <= 2 ... budget".
SLOT_CAP = re.compile(r"(?:≤|<=)\s*(\d+)")

#: Section 2.3's configuration-bit count and the bus list it rests on.
CONFIG_BITS = re.compile(r"(?P<n>\d+)\s+configuration bits\s*\((?P<list>[^)]*)\)")


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


def budget_key(name):
    """A slot category as a comparable key: no hyphens, singular, casefolded.

    The document writes one category several ways -- "bandgap-referenced
    current sources" in the budget, "bandgap-referenced current-source budget"
    in a slot cell, "digital control input" in one row and "digital control
    inputs" in the totals. All four are the same slot, and a rule that could
    not see that would be grading spelling.
    """
    text = normalize(name).replace("-", " ")
    words = [w for w in re.split(r"\s+", text) if w]
    if words and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def strip_parens(text):
    """`text` with its parenthetical asides removed, innermost first.

    The totals paragraph explains itself inside parentheses -- "(18 without
    the lock-detector trim; LDT0-LDT3 add 4 ...)" -- and those numbers are
    prose, not entries. Scanning them as entries would invent categories the
    document does not have.
    """
    while True:
        stripped = re.sub(r"\([^()]*\)", " ", text)
        if stripped == text:
            return text
        text = stripped


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


def signals(text):
    """Every pin name `text` names, ranges expanded, in order of appearance.

    Ranges are consumed first and blanked out, so `B0..B2` contributes B1 as
    well as its two endpoints rather than only the endpoints a bare-identifier
    scan would see.
    """
    found = []
    remainder = []
    last = 0
    for match in RANGE.finditer(text):
        remainder.append(text[last:match.start()])
        last = match.end()
        prefix, other = match.group("a"), match.group("b")
        lo, hi = int(match.group("i")), int(match.group("j"))
        if other is not None and other != prefix:
            # Not a range over one prefix (`REF..CLK` is not a bus); take the
            # two endpoints literally and expand nothing.
            found.append("%s%d" % (prefix, lo))
            found.append("%s%d" % (other, hi))
            continue
        if lo > hi:
            lo, hi = hi, lo
        found.extend("%s%d" % (prefix, n) for n in range(lo, hi + 1))
    remainder.append(text[last:])
    for span in SPAN.findall("".join(remainder)):
        if re.fullmatch(IDENT, span):
            found.append(span)
    seen = set()
    ordered = []
    for name in found:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def section(text, pattern, where, rel):
    match = re.search(pattern, text, re.M | re.S)
    if match is None:
        sys.stderr.write(
            "FAIL: %s has no %s -- this check cannot grade a section it cannot "
            "find, and a parse failure is not a pass\n" % (rel, where)
        )
        return None
    return match.group(1)


netlist_text = read(netlist_rel)
proposal_text = read(proposal_rel)
if netlist_text is None or proposal_text is None:
    sys.exit(1)

# ------------------------------------------------- the exported port list --

subckt = re.search(r"^\.subckt\s+pll_top\b(.*)$", netlist_text, re.M)
if subckt is None:
    sys.stderr.write(
        "FAIL: %s has no '.subckt pll_top' line -- the exported port list is "
        "what this check grades everything else against\n" % netlist_rel
    )
    sys.exit(1)

declared = subckt.group(1)
# ngspice wraps a long port list onto `+` continuation lines, and pll_top's
# 36 ports always wrap. Folding them back is the whole reason this is not a
# one-line grep: a scan that stopped at the first newline would read a
# truncated port list as the complete one and report a clean tree.
for line in netlist_text[subckt.end():].lstrip("\r\n").splitlines():
    if not line.startswith("+"):
        break
    declared += " " + line[1:]
ports = declared.split()

if len(ports) < 10:
    sys.stderr.write(
        "FAIL: parsed %d port(s) from %s's '.subckt pll_top' line -- too few "
        "to be real; the export format has changed under this check\n"
        % (len(ports), netlist_rel)
    )
    sys.exit(1)

port_set = set(ports)

# --------------------------------------------------- the proposal's parts --

pad_section = section(
    proposal_text, r"^### 2\.2\b[^\n]*\n(.*?)(?=^#{1,3} )", "'### 2.2' section",
    proposal_rel,
)
slot_section = section(
    proposal_text, r"^### 2\.3\b[^\n]*\n(.*?)(?=^#{1,3} )", "'### 2.3' section",
    proposal_rel,
)
bench_section = section(
    proposal_text, r"^## 4\.[^\n]*\n(.*?)(?=^## )", "'## 4.' section", proposal_rel
)
if pad_section is None or slot_section is None or bench_section is None:
    sys.exit(1)

pad_rows = table_rows(pad_section)
if len(pad_rows) < 6:
    sys.stderr.write(
        "FAIL: parsed %d data row(s) from %s section 2.2's pad table -- too "
        "few to be real; the table format has changed under this check\n"
        % (max(len(pad_rows) - 1, 0), proposal_rel)
    )
    sys.exit(1)

header = [normalize(c) for c in pad_rows[0]]
for name in ("signal(s)", "challenge slot", "count used"):
    if name not in header:
        sys.stderr.write(
            "FAIL: %s section 2.2's pad table has no %r column (header reads: "
            "%s) -- this check cannot grade a table it cannot parse\n"
            % (proposal_rel, name, " | ".join(pad_rows[0]))
        )
        sys.exit(1)
sig_col = header.index("signal(s)")
slot_col = header.index("challenge slot")
count_col = header.index("count used")

pad_entries = []
for row in pad_rows[1:]:
    if max(sig_col, slot_col, count_col) >= len(row):
        sys.stderr.write(
            "FAIL: %s section 2.2 has a pad row with %d cell(s), fewer than "
            "its own header declares: %s\n"
            % (proposal_rel, len(row), " | ".join(row))
        )
        sys.exit(1)
    pad_entries.append(
        (row[sig_col], signals(row[sig_col]), row[count_col], row[slot_col])
    )

mapped = {name for _raw, names, _count, _slot in pad_entries for name in names}

failed = False

# ------------------------------------------------------- rule 1: coverage --

for port in ports:
    if port not in mapped:
        failed = True
        sys.stderr.write(
            "FAIL: port %r of %s's '.subckt pll_top' has no row in %s section "
            "2.2's pad table. #237's AC4 requires the proposal to carry the "
            "block's I/O list, and section 2.3 claims outright that "
            "\"nothing in design/pll_top.sch's port list is dropped\" -- add "
            "the pin to the pad table with its Challenge slot, or that claim "
            "is false\n" % (port, netlist_rel, proposal_rel)
        )

# -------------------------------------------------- rule 2: no orphan pins --

for raw, names, _count, _slot in pad_entries:
    for name in names:
        if name not in port_set:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's pad row %r names %r, which is not a "
                "port of %s's '.subckt pll_top'. Either the pin was renamed "
                "or removed in design/ (fix the pad row, so the real pin is "
                "mapped) or this row maps a pin the design does not have\n"
                % (proposal_rel, raw, name, netlist_rel)
            )

# ------------------------------------------------ rule 3: the quoted list --

quoted = re.search(r"`\.subckt\s+pll_top\s+([^`]*)`", proposal_text, re.S)
if quoted is None:
    failed = True
    sys.stderr.write(
        "FAIL: %s does not quote the '.subckt pll_top' line anywhere. Section "
        "2.2 states that line is \"the port list this table maps, unedited\" "
        "-- without it the mapping has no stated basis\n" % proposal_rel
    )
else:
    quoted_ports = [t for t in quoted.group(1).split() if t != "+"]
    if quoted_ports != ports:
        failed = True
        sys.stderr.write(
            "FAIL: the '.subckt pll_top' port list quoted in %s does not match "
            "%s, which it claims to quote unedited.\n"
            "  netlist:  %s\n"
            "  proposal: %s\n"
            "Re-quote the committed export rather than editing the document's "
            "copy of it\n"
            % (proposal_rel, netlist_rel, " ".join(ports), " ".join(quoted_ports))
        )

# ------------------------------------------------- rule 4: per-row counts --

for raw, names, count, _slot in pad_entries:
    match = COUNT.match(normalize(count))
    if match is None:
        continue
    stated = int(match.group(1))
    if stated != len(names):
        failed = True
        sys.stderr.write(
            "FAIL: %s section 2.2's pad row %r states %r but names %d signal(s)"
            " (%s). The count and the row beside it drifted apart once already "
            "(issue #441, DR-015) -- restate the count from the signals\n"
            % (
                proposal_rel,
                raw,
                count.strip(),
                len(names),
                ", ".join(names) or "none",
            )
        )

# -------------------------------------------------- rule 5: the bench plan --

benched = set(signals(bench_section))
for port in ports:
    if port not in benched:
        failed = True
        sys.stderr.write(
            "FAIL: port %r is never named in %s section 4, the bench test "
            "plan. That plan is what an outside reader executes on silicon; a "
            "pin it does not mention is a pin nobody drives. State how the pin "
            "is driven or observed -- or, if it genuinely takes no bench "
            "action, say so in a step rather than leaving it out\n"
            % (port, proposal_rel)
        )

# ------------------------------------- the Challenge budget, as transcribed --

# Everything in section 2.2 before the pad table: the sentence that transcribes
# the Challenge's slot budget lives there, and it is the only source this check
# has for what the categories and their caps are. Code spans go first -- the
# quoted `.subckt pll_top ...` line is full of the words and dots a sentence
# scanner would trip over, and rule 3 already grades it.
preamble_lines = []
for line in pad_section.splitlines():
    if line.lstrip().startswith("|"):
        break
    preamble_lines.append(line)
preamble = normalize(re.sub(r"`[^`]*`", " ", "\n".join(preamble_lines)))

budget = {}          # key -> (cap or None for untranscribed, as-written name)
budget_clause = ""
colon = preamble.find(":")
if colon != -1:
    stop = preamble.find(".", colon)
    budget_clause = preamble[colon + 1:stop if stop != -1 else len(preamble)]
    for match in BUDGET_ENTRY.finditer(budget_clause):
        cap = int(match.group("n")) if match.group("n") else 1
        budget[budget_key(match.group("name"))] = (cap, match.group("name").strip())
    for match in BUDGET_ABSENT.finditer(budget_clause):
        budget[budget_key(match.group("name"))] = (None, match.group("name").strip())

if len(budget) < 4:
    failed = True
    sys.stderr.write(
        "FAIL: parsed %d budget categor(ies) from %s section 2.2's transcribed "
        "Challenge budget -- too few to be real. That sentence ('...onto the "
        "Challenge #5 budget as this repository understands it: one "
        "bandgap-referenced bias voltage, up to 24 digital control inputs, "
        "...') is where rules 6-8 read the slot taxonomy from, so a parse "
        "failure here is a check that did not run, not a tree that is clean. "
        "Clause read: %r\n"
        % (len(budget), proposal_rel, budget_clause.strip()[:400])
    )

# --------------------------------------------- rule 6: slots are categories --

def category_of(slot_cell):
    """The budget category a Challenge-slot cell names, longest match wins."""
    haystack = budget_key(slot_cell)
    hits = [key for key in budget if key and key in haystack]
    return max(hits, key=len) if hits else None

row_category = {}
for index, (raw, names, count, slot) in enumerate(pad_entries):
    key = category_of(slot) if budget else None
    row_category[index] = key
    if not budget:
        continue
    if key is None:
        failed = True
        sys.stderr.write(
            "FAIL: %s section 2.2's pad row %r carries the Challenge slot %r, "
            "which is not a category the transcribed budget above the table "
            "names (%s). Either map the row to a slot that budget offers, or "
            "transcribe the missing line -- including as an explicit absence "
            "('no transcribed line at all for <category>') when the challenge "
            "publishes no count for it. A row in a category nothing budgets "
            "cannot be totalled, and the totals paragraph claims to cover "
            "every category\n"
            % (
                proposal_rel,
                raw,
                normalize(slot),
                ", ".join(sorted(name for _cap, name in budget.values())),
            )
        )
        continue
    cap = budget[key][0]
    stated = [int(n) for n in SLOT_CAP.findall(normalize(slot))]
    budget_match = COUNT_BUDGET.match(normalize(count))
    if budget_match:
        stated += [
            int(g) for g in (budget_match.group("of"), budget_match.group("offered"))
            if g
        ]
    for number in stated:
        if cap is None:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's pad row %r states a budget of %d for "
                "the %r slot, but the transcribed budget has no count for that "
                "category at all -- it is transcribed as an absence. A cap "
                "this document invents is one its reader cannot check against "
                "the challenge's rules page\n"
                % (proposal_rel, raw, number, budget[key][1])
            )
        elif number != cap:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's pad row %r states a budget of %d for "
                "the %r slot, which the same section transcribes as %d. The "
                "transcription is the document's own statement of the "
                "challenge's budget; a row quoting a different number means "
                "one of the two is stale\n"
                % (proposal_rel, raw, number, budget[key][1], cap)
            )

# ----------------------------------- rules 7-8: the totals close over the rows --

totals_block = re.search(
    r"^\*\*Totals\b.*?(?=\n[ \t]*\n|\Z)", pad_section, re.M | re.S
)
if totals_block is None:
    failed = True
    sys.stderr.write(
        "FAIL: %s section 2.2 has no paragraph starting '**Totals' -- the "
        "per-category totals against the Challenge budget. #237's AC4 asks "
        "for the I/O list 'mapped to the slot budget', and the mapping is "
        "what that paragraph states; without it the pad table's per-row "
        "counts add up to nothing a reader is told\n" % proposal_rel
    )
elif budget:
    totals_text = strip_parens(normalize(totals_block.group(0)))
    totals = {}
    for match in TOTAL_ENTRY.finditer(totals_text):
        key = budget_key(match.group("name"))
        lo = int(match.group("lo"))
        hi = int(match.group("hi")) if match.group("hi") else lo
        cap = match.group("cap") or match.group("offered")
        totals[key] = (lo, hi, int(cap) if cap else None, match.group("name").strip())

    for key, (lo, hi, cap, name) in sorted(totals.items()):
        if key not in budget:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's totals paragraph reports %r, which is "
                "not a category the transcribed budget names (%s). A total "
                "against a budget line that does not exist cannot be checked "
                "by the reader it is written for\n"
                % (
                    proposal_rel,
                    name,
                    ", ".join(sorted(n for _cap, n in budget.values())),
                )
            )
            continue
        budgeted = budget[key][0]
        if cap is not None and budgeted is None:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's totals paragraph states a budget of %d "
                "for %r, a category the transcription carries as an absence. "
                "State it as a bare request ('5 supply/ground pads'), not as a "
                "fraction of a slot count this document does not have\n"
                % (proposal_rel, cap, name)
            )
        elif cap is not None and cap != budgeted:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's totals paragraph reports %r against a "
                "budget of %d, which the same section transcribes as %d\n"
                % (proposal_rel, name, cap, budgeted)
            )
        rows_all = 0
        rows_required = 0
        for index, (_raw, names, count, _slot) in enumerate(pad_entries):
            if row_category.get(index) != key:
                continue
            match = COUNT.match(normalize(count))
            used = int(match.group(1)) if match else len(names)
            rows_all += used
            if "proposed" not in normalize(count):
                rows_required += used
        if (lo, hi) != (rows_required, rows_all):
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's totals paragraph reports %s for %r, "
                "but the pad rows carrying that slot sum to %d (%d of them "
                "not marked '(proposed)'). The total is not a separately "
                "maintained number -- it is the sum of the rows above it, and "
                "this paragraph read 18 of 24 against a real 22 for three "
                "days the last time the two drifted (issue #441, DR-015)\n"
                % (
                    proposal_rel,
                    "%d" % lo if lo == hi else "%d-%d" % (lo, hi),
                    name,
                    rows_all,
                    rows_required,
                )
            )

    for key, (_cap, name) in sorted(budget.items()):
        if key not in totals:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.2's totals paragraph never reports %r, a "
                "category its own transcribed budget names. Report it -- as "
                "'0 of N' if this block asks for none of it, the way the "
                "bandgap bias voltage is reported. A category the paragraph "
                "leaves out is one a reader of the totals cannot see this "
                "block has an answer for\n" % (proposal_rel, name)
            )

# ------------------------------- rule 9: section 2.3's configuration-bit count --

# Section 2.3 is a bullet list; the configuration-bit count lives in one of
# its bullets, and the exclusions it is allowed to make are the ones that
# bullet states. Grading against the whole section would let a pin dropped
# from the count be "explained" by an unrelated bullet mentioning it.
config_blocks = re.split(r"\n(?=\s*[-*] )", slot_section)
config_para = next(
    (block for block in config_blocks if CONFIG_BITS.search(block)), slot_section
)
config = CONFIG_BITS.search(slot_section)
if config is None:
    failed = True
    sys.stderr.write(
        "FAIL: %s section 2.3 has no 'N configuration bits (...)' sentence. "
        "That count is how the document tells a harness integrator how many "
        "static levels this block needs held, and it went stale by one the "
        "last time the pin list changed (issue #441, DR-015)\n" % proposal_rel
    )
else:
    stated_bits = int(config.group("n"))
    bits = signals(config.group("list"))
    if stated_bits != len(bits):
        failed = True
        sys.stderr.write(
            "FAIL: %s section 2.3 states %d configuration bits but its own bus "
            "list expands to %d (%s). Restate the count from the list\n"
            % (proposal_rel, stated_bits, len(bits), ", ".join(bits) or "none")
        )
    bit_categories = set()
    for name in bits:
        rows = [
            index
            for index, (_raw, names, _count, _slot) in enumerate(pad_entries)
            if name in names
        ]
        if not rows:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.3 counts %r as a configuration bit, but no "
                "pad row in section 2.2 names it. A bit with no pad is a level "
                "nobody can hold\n" % (proposal_rel, name)
            )
            continue
        bit_categories.update(
            row_category[index] for index in rows if row_category.get(index)
        )
    if len(bit_categories) > 1:
        failed = True
        sys.stderr.write(
            "FAIL: %s section 2.3's configuration bits span %d Challenge slot "
            "categories (%s). They are one kind of pin -- static levels the "
            "harness holds -- and counting them across categories makes the "
            "count uncheckable against any budget line\n"
            % (proposal_rel, len(bit_categories), ", ".join(sorted(bit_categories)))
        )
    elif bit_categories:
        category = bit_categories.pop()
        siblings = [
            name
            for index, (_raw, names, _count, _slot) in enumerate(pad_entries)
            if row_category.get(index) == category
            for name in names
        ]
        excluded = [name for name in siblings if name not in bits]
        unexplained = [
            name for name in excluded if not re.search(r"\b%s\b" % name, config_para)
        ]
        if unexplained:
            failed = True
            sys.stderr.write(
                "FAIL: %s section 2.3's configuration-bit count leaves out %s, "
                "which section 2.2 maps to the same %r slot, without naming "
                "%s anywhere in the same bullet. `REF` is left out legitimately "
                "because that section says so in terms -- it is a toggling "
                "clock, not a static level. A pin dropped from the count in "
                "silence is the same off-by-one in a quieter form\n"
                % (
                    proposal_rel,
                    ", ".join(repr(n) for n in unexplained),
                    category,
                    "it" if len(unexplained) == 1 else "them",
                )
            )

if failed:
    sys.exit(1)

print(
    "OK: all %d ports of %s's '.subckt pll_top' are mapped in %s section 2.2 "
    "(%d pad rows, counts consistent, quoted port list in netlist order) and "
    "named in section 4's bench test plan"
    % (len(ports), netlist_rel, proposal_rel, len(pad_entries))
)
print(
    "OK: %d Challenge slot categor(ies) transcribed (%s), every pad row in "
    "one of them, every one totalled from its own rows, and section 2.3's "
    "%d configuration bits expand from its own bus list"
    % (
        len(budget),
        "; ".join(
            "%s %s" % (name, "uncapped" if cap is None else "<= %d" % cap)
            for cap, name in sorted(budget.values(), key=lambda pair: pair[1])
        ),
        int(config.group("n")) if config else 0,
    )
)
PY
