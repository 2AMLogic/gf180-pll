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
# WHAT IT DOES NOT DO
#
# It grades presence, not adequacy: it cannot tell a bench step that drives a
# pin correctly from one that merely mentions it, and it says nothing about
# whether a pad row's slot assignment or its Notes are right. It also does not
# grade the Challenge-budget totals in section 2.2's closing paragraph against
# the per-row counts rule 4 checks -- those totals are stated per budget
# category, some as ranges ("1-3 of <= 12 digital test outputs"), and a rule
# that had to encode the category taxonomy would be grading this check's own
# model of the document rather than the document.
#
# Usage: design/lib/check-io-list-coverage.sh
# Exit codes: 0 the proposal's I/O list matches the exported port list and its
#               bench plan names every pin,
#             1 a port is unmapped, a pad row names a port that does not
#               exist, the quoted port list disagrees with the netlist, a row
#               count disagrees with the signals beside it, the bench plan
#               omits a pin, a graded file is missing, or either the netlist
#               or the pad table fails to parse (a broken parser must not look
#               like a clean tree).

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
bench_section = section(
    proposal_text, r"^## 4\.[^\n]*\n(.*?)(?=^## )", "'## 4.' section", proposal_rel
)
if pad_section is None or bench_section is None:
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
for name in ("signal(s)", "count used"):
    if name not in header:
        sys.stderr.write(
            "FAIL: %s section 2.2's pad table has no %r column (header reads: "
            "%s) -- this check cannot grade a table it cannot parse\n"
            % (proposal_rel, name, " | ".join(pad_rows[0]))
        )
        sys.exit(1)
sig_col, count_col = header.index("signal(s)"), header.index("count used")

pad_entries = []
for row in pad_rows[1:]:
    if sig_col >= len(row) or count_col >= len(row):
        sys.stderr.write(
            "FAIL: %s section 2.2 has a pad row with %d cell(s), fewer than "
            "its own header declares: %s\n"
            % (proposal_rel, len(row), " | ".join(row))
        )
        sys.exit(1)
    pad_entries.append((row[sig_col], signals(row[sig_col]), row[count_col]))

mapped = {name for _raw, names, _count in pad_entries for name in names}

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

for raw, names, _count in pad_entries:
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

for raw, names, count in pad_entries:
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

if failed:
    sys.exit(1)

print(
    "OK: all %d ports of %s's '.subckt pll_top' are mapped in %s section 2.2 "
    "(%d pad rows, counts consistent, quoted port list in netlist order) and "
    "named in section 4's bench test plan"
    % (len(ports), netlist_rel, proposal_rel, len(pad_entries))
)
PY
