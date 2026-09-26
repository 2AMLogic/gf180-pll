#!/usr/bin/env bash
#
# Fails if `spec/pll.md`'s reference-spur charge-accounting totals do not
# reproduce from the committed campaign evidence DR-018 cites for every
# ingredient they are built out of.
#
# WHY THIS EXISTS (issue #237)
#
# `spec/lib/check-spur-derivation-arithmetic.sh` grades the reference-spur
# derivation's arithmetic *from* its charge totals (7.93 / 11.19 / 11.66 fC)
# onward to a dBc figure. Its own header used to state what it does not do:
#
#   It does not grade where the charge terms themselves come from ... reducing
#   those samples ... needs a reduction language for a signed `|mean| + 3σ`
#   statistic, which it does not have.
#
# That statistic is not actually missing -- DR-018 computes it by hand from
# 300 samples committed at `sim/mc-cp-mismatch/corners/<record-id>/`, and
# `sim/mc-cp-mismatch/testbench/run.sh --restat` already re-derives it from
# those same files (no ngspice, no simulation). This check gives the
# reduction its own CI-checkable implementation and chains it into the three
# totals the sibling check takes as given:
#
#   term 1 (DC UP/DN mismatch)   <- sim/mc-cp-mismatch's `mc_cp_dc.csv`
#   term 3 (residual net charge) <- sim/mc-cp-mismatch's `mc_pfd_cp.csv`
#   q_systematic (|q_up + q_dn|) <- sim/cp-compliance's `cp_switch.csv`
#   Icp at the priced trim code  <- sim/cp-compliance's `cp_dc.csv`
#   T_ov (reset overlap)         <- sim/pfd-deadzone's `raw_measures.csv`
#   ΔQ total = q_systematic + q_term3 [+ m x Icp x T_ov]
#
# The last three arrived at issue #573; before it they were read from DR-018's
# Input table, which is now graded against them instead.
#
# THE RULES
#
# 1. RECORD RESOLVES. `spec/pll.md`'s `## Reference spur` section must name a
#    `run.sh --restat <record-id>` command (the same one its own prose cites
#    as the source of the term-1/term-3 figures), and the corner CSVs it
#    implies (`sim/mc-cp-mismatch/corners/<record-id>/{mc_cp_dc,mc_pfd_cp}.csv`)
#    must exist and parse with the schema this campaign has used since #146
#    (a `corner,seed,...` header, not the pre-corner-grid one).
#
# 2. TERM 1 REPRODUCES. For every (corner, seed) triple of Vctrl points in
#    `mc_cp_dc.csv`, the worst-magnitude reading is selected (the
#    `cp-compliance` "worst point in window" convention); per corner, both the
#    signed series' and the folded (absolute-value) series' `|mean| + 3*sd`
#    (sample sd, N-1) are formed, and the worst corner of each series is kept.
#    The **signed** worst-corner figure must equal the percentage
#    `spec/pll.md`'s charge-accounting table states term 1 is "measured" at.
#
# 3. TERM 3 REPRODUCES. Per corner, `mc_pfd_cp.csv`'s `qnet0_c` column forms
#    `|mean| + 3*sd`; the worst corner's figure must equal DR-018's stated
#    "Statistical residual net charge (term 3), corner-combined" input.
#
# 4. CHARGE TOTALS REPRODUCE. `spec/pll.md`'s charge-accounting table carries
#    three totals this check can now build from ingredients instead of taking
#    on faith:
#      - "term 1 still excluded"   = q_systematic + q_term3
#      - "at its measured X %"     = the row above + (X/100) x Icp x T_ov
#      - "at its budgeted Y %"     = the row above + (Y/100) x Icp x T_ov
#    with q_systematic, Icp and T_ov the figures rules 5-7 below reduce from
#    their own campaigns' committed CSVs -- not the values DR-018's Input
#    table states for them, which are themselves graded against those
#    reductions. Every total must agree with the table's own ΔQ column at the
#    precision written.
#
# 5. Icp REPRODUCES FROM `cp-compliance`. DR-018's Input row for `Icp` names
#    the trim code it prices, how many unit legs that code is, how many
#    corners it was measured over, and the record it comes from -- all of
#    which this check reads out of the row rather than assuming. That
#    record's `cp_dc.csv` is reduced by the campaign's OWN stated convention
#    (`cp_trim_range.csv`'s header: "mean of the two polarities at
#    Vctrl = 1.65 V, min/max across every corner", cross-read against the DC
#    bench's stated window nominal so the mid-window columns are the right
#    ones), and both ends of the stated range must reproduce -- against the
#    per-point grid AND against the campaign's own committed reduction in
#    `cp_trim_range.csv`, which is a second route to the same number.
#
# 6. T_ov REPRODUCES FROM `pfd-deadzone`. DR-018's Input row for the reset
#    overlap states its own reduction in words -- "min UP/DN pulse at zero
#    phase error, 45 corners" -- and names the `raw_measures.csv` it is taken
#    from. The zero-phase-error rows are selected by PARSING the dphi axis
#    value (`d0` -> 0 s), and that selection must coincide exactly with the
#    rows the campaign itself marks as measured in `q_zero` ("measured only
#    at the dphi = 0 points, `not measured` everywhere else by construction"),
#    so a mis-parsed axis cannot pass. Per corner the smallest UP/DN pulse
#    width over that corner's control-voltage points is taken; both ends of
#    the stated range must reproduce, and the corner the maximum lands at
#    must be the one the cell names in "(worst `ss`/125 °C/2.97 V)".
#
# 7. THE SYSTEMATIC ASYMMETRY REPRODUCES FROM `cp-compliance`'s SWITCHING
#    BENCH. DR-018's Input row for `|q_up + q_dn|` names a cp-compliance
#    record and the decision record that priced it (DR-006 §8). That record's
#    `cp_switch.csv` gives `|qup_c + qdn_c|` per (corner, Vctrl) point; its
#    worst case must equal DR-018's stated figure, AND both figures DR-006 §8
#    states for the same quantity -- "3.68 fC worst case, 2.16 fC median" --
#    must reproduce. The median is graded because it is the figure that says
#    the worst case is a tail rather than the typical part, and a reduction
#    that reproduced only the maximum could be selecting a different
#    population.
#
#    All three ingredient reductions must see the same number of distinct PVT
#    corners, and that number must be the corner count DR-018's own Input
#    rows state (45). A worst case over a subset of the mandated grid is not
#    the figure these rows claim, and is the failure mode most likely to be
#    silent.
#
# WHAT IT DOES NOT DO
#
# It reduces committed evidence; it does not re-run a simulator, and it
# cannot tell whether the simulation behind a CSV was the right experiment --
# that is what each campaign's manifest, testbench and record Methodology
# field are for, and `sim/lib/check-record-supersession.sh` is what keeps a
# cited record from being a superseded one. It also does not re-derive C2
# (1.814 pF) or the TIE scale point (0.669 ps at 1.825 mV): those are
# `check-spur-derivation-arithmetic.sh`'s inputs, downstream of the charge
# totals this check builds, and that check draws its own boundary around
# them.
#
# Up to issue #573 this list also included `Icp`, `T_ov` and the 3.68 fC
# systematic charge asymmetry, which were read from DR-018's Input table as
# the derivation itself reads them. They are rules 5-7 now: every ingredient
# of the three charge totals is reduced from a committed campaign CSV, and
# the Input table is graded as a claim about that evidence rather than
# trusted as the source of it.
#
# SECOND IMPLEMENTATION OF THE SAME STATISTIC -- KEEP THEM IN AGREEMENT
#
# Rule 2's reduction is deliberately duplicated. `sim/lib/check-quoted-value-
# provenance.sh` computes the *same* term-1 statistic from the *same*
# `mc_cp_dc.csv` -- its section 5.1 provenance entry
#
#   max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)   = 17.48 %
#
# where `sig3` is `|mean| + 3*sd` with sample sd (N-1) and `worst-magnitude`
# is this rule's per-(corner,seed) selection. The two exist for different
# reasons and neither subsumes the other: this check asks whether
# `spec/pll.md`'s **charge totals** still follow from their samples, while
# that one asks whether a **percentage quoted in the proposal's section 5
# prose** is a reduction of committed evidence at all (the "quoted in section
# 5, graded in neither accounting table" defect). So do not collapse one into
# the other -- but do change them together: if the selection convention, the
# sd convention (N-1), the nesting order, or the signed-vs-folded reading
# moves here, move it there too, and check the other check still passes.
# Agreeing by two routes is what makes a silent drift in either one loud.
#
# Usage: spec/lib/check-mismatch-charge-derivation.sh
# Exit codes: 0 every ingredient reproduces from its own campaign's committed
#               evidence and every charge-accounting total reproduces from
#               those ingredients,
#             1 the record/CSVs cannot be resolved or parsed, a figure does
#               not reproduce, or a graded table/row is missing (a broken
#               parser must not look like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SPEC="spec/pll.md"
DR018="spec/decision-records/DR-018-cp-term1-mismatch-budget-derived-from-the-spur-line.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${SPEC}" "${DR018}" <<'PY'
import glob
import math
import os
import re
import statistics
import sys

repo_root, spec_rel, dr018_rel = sys.argv[1:4]

NUMBER = r"[+-]?\d+(?:\.\d+)?"

failures = []


def fail(message):
    failures.append(message)
    sys.stderr.write("FAIL: %s\n" % message)


def read(rel):
    path = os.path.join(repo_root, rel)
    if not os.path.isfile(path):
        sys.stderr.write("FAIL: %s does not exist\n" % rel)
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def plain(cell):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = text.replace("**", "").replace("`", "").replace("\\|", "|")
    for dash in ("—", "–", "‒", "‑"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


ESCAPED_PIPE = "\x00"


def tables(block):
    found, current = [], None
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            current = None
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", line):
            continue
        line = line.replace("\\|", ESCAPED_PIPE)
        cells = [
            c.strip().replace(ESCAPED_PIPE, "\\|") for c in line.strip("|").split("|")
        ]
        if current is None:
            current = [cells]
            found.append(current)
        else:
            current.append(cells)
    return found


def agrees(written, computed):
    """`computed` (float) matches the decimal string `written` when rounded
    to `written`'s own precision -- the same "at the precision written"
    contract `check-spur-derivation-arithmetic.sh` grades against."""
    decimals = len(written.split(".")[1]) if "." in written else 0
    fmt = "%%.%df" % decimals
    return (fmt % computed) == (fmt % float(written))


PRINTED = re.compile(r"([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?\s*$")


def agrees_printed(written, computed):
    """`computed` matches a value a campaign PRINTED, to within one unit in
    its last printed place.

    Unlike `agrees` this handles scientific notation (`7.20923e-06`), which a
    campaign's own reduced CSV writes and a document does not. The tolerance
    is one ulp of the printed place rather than exact equality because the
    committed figure went through the harness's own `%.6g` formatting: an
    agreement test tighter than the evidence's own precision would fail for a
    reason that has nothing to do with the samples."""
    match = PRINTED.match(written.strip())
    if match is None:
        return False
    frac = match.group(3) or ""
    exponent = int(match.group(4) or 0)
    ulp = 10.0 ** (exponent - len(frac))
    return abs(computed - float(written)) <= ulp


def load_csv(path, rel, required):
    """(comment block, column index, rows) of a committed campaign CSV.

    The comment lines are returned rather than discarded: several of these
    campaigns state their own reduction convention in that header, and this
    check reads the convention there instead of inventing one."""
    if not os.path.isfile(path):
        fail("%s does not exist -- a figure cited against evidence that is "
             "not there is not a checked one" % rel)
        return None, None, None
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh]
    comments = "\n".join(ln for ln in lines if ln.startswith("#"))
    body = [ln for ln in lines if not ln.startswith("#") and ln.strip()]
    if not body:
        fail("%s has no data after stripping comment lines" % rel)
        return None, None, None
    header = [c.strip() for c in body[0].split(",")]
    idx = {name: i for i, name in enumerate(header)}
    missing = [c for c in required if c not in idx]
    if missing:
        fail(
            "%s has no %s column(s) -- this check must not silently reduce a "
            "schema it does not recognise" % (rel, ", ".join(repr(m) for m in missing))
        )
        return None, None, None
    return comments, idx, [ln.split(",") for ln in body[1:]]


spec_text = read(spec_rel)
dr018_text = read(dr018_rel)
if spec_text is None or dr018_text is None:
    sys.exit(1)

section = re.search(
    r"^## Reference spur[^\n]*\n(.*?)(?=^## )", spec_text, re.M | re.S
)
if section is None:
    sys.stderr.write(
        "FAIL: %s has no '## Reference spur' section\n" % spec_rel
    )
    sys.exit(1)
section_text = section.group(1)

# --------------------------------------------------------------- rule 1 ---
restat = re.search(
    r"run\.sh --restat\s+(\d{8}-\d{6}-[0-9a-f]{7})", section_text
)
if restat is None:
    fail(
        "%s's Reference spur section does not cite a "
        "`run.sh --restat <record-id>` command -- that citation is this "
        "check's only source for which committed campaign the term-1/term-3 "
        "figures come from, and it cannot be assumed" % spec_rel
    )
    sys.exit(1)
record_id = restat.group(1)

corners_dir = os.path.join(
    repo_root, "sim", "mc-cp-mismatch", "corners", record_id
)
dc_path = os.path.join(corners_dir, "mc_cp_dc.csv")
pfd_path = os.path.join(corners_dir, "mc_pfd_cp.csv")
for path, rel in (
    (dc_path, "sim/mc-cp-mismatch/corners/%s/mc_cp_dc.csv" % record_id),
    (pfd_path, "sim/mc-cp-mismatch/corners/%s/mc_pfd_cp.csv" % record_id),
):
    if not os.path.isfile(path):
        fail(
            "%s cites record %s, but %s does not exist -- a hand derivation "
            "cited against evidence that is not there is not a checked one"
            % (spec_rel, record_id, rel)
        )
if failures:
    sys.exit(1)


def read_csv_rows(path, expected_header_prefix):
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#")]
    if not lines:
        fail("%s has no data after stripping comment lines" % path)
        return None, None
    header = [c.strip() for c in lines[0].split(",")]
    if not header or header[0] != expected_header_prefix:
        fail(
            "%s's header is %r, expected to start with %r -- this is not a "
            "corner-combined campaign (records before #146 have no `corner` "
            "column) and this check must not silently reduce an empty match"
            % (path, header, expected_header_prefix)
        )
        return None, None
    idx = {name: i for i, name in enumerate(header)}
    rows = [ln.split(",") for ln in lines[1:] if ln.strip()]
    return idx, rows


def sig6(value):
    """Round to 6 significant figures, C `%.6g` semantics.

    `sim/lib/simenv.sh`'s `simenv_stats_from_values` -- the campaign's own
    reduction helper -- prints mean and sd at `%.6g` *before* `sig3()` forms
    `|mean| + 3*sd` from the printed strings, not from full double precision.
    Reproducing the campaign's own intermediate rounding here (rather than a
    higher-precision recomputation) is why this check's figures match the
    committed record's to the same 6th significant figure DR-018 itself
    reports them at, instead of disagreeing with it in the last digit for a
    reason that has nothing to do with the samples."""
    return float("%.6g" % value)


def sample_stats(values):
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
    else:
        var = 0.0
    sd = math.sqrt(var)
    return sig6(mean), sig6(sd), n


dc_idx, dc_rows = read_csv_rows(dc_path, "corner")
pfd_idx, pfd_rows = read_csv_rows(pfd_path, "corner")
if dc_idx is None or pfd_idx is None:
    sys.exit(1)
for col in ("corner", "seed", "mism_pct"):
    if col not in dc_idx:
        fail("%s has no %r column" % (dc_path, col))
for col in ("corner", "qnet0_c"):
    if col not in pfd_idx:
        fail("%s has no %r column" % (pfd_path, col))
if failures:
    sys.exit(1)

# --------------------------------------------------------------- rule 2 ---
# Term 1: worst-magnitude Vctrl reading per (corner, seed), then per-corner
# |mean| + 3*sd on the signed series and, separately, on the series folded to
# |x| first -- both readings DR-018 prices, kept distinct because folding
# shrinks the tail (issue #487).
groups = {}
for row in dc_rows:
    corner = row[dc_idx["corner"]]
    seed = row[dc_idx["seed"]]
    mism = float(row[dc_idx["mism_pct"]])
    key = (corner, seed)
    if key not in groups or abs(mism) > abs(groups[key]):
        groups[key] = mism

if not groups:
    fail("%s selected no (corner, seed) samples for term 1" % dc_path)
    sys.exit(1)

signed_by_corner = {}
folded_by_corner = {}
for (corner, _seed), worst in groups.items():
    signed_by_corner.setdefault(corner, []).append(worst)
    folded_by_corner.setdefault(corner, []).append(abs(worst))


def worst_corner_3sigma(by_corner):
    stats = {}
    for corner, values in by_corner.items():
        mean, sd, n = sample_stats(values)
        stats[corner] = (abs(mean) + 3 * sd, mean, sd, n)
    worst = max(stats, key=lambda c: stats[c][0])
    return stats[worst][0], worst, stats[worst][3]


term1_signed_3s, term1_signed_corner, term1_signed_n = worst_corner_3sigma(
    signed_by_corner
)
term1_folded_3s, term1_folded_corner, term1_folded_n = worst_corner_3sigma(
    folded_by_corner
)

# --------------------------------------------------------------- rule 3 ---
term3_by_corner = {}
for row in pfd_rows:
    corner = row[pfd_idx["corner"]]
    q = float(row[pfd_idx["qnet0_c"]])
    term3_by_corner.setdefault(corner, []).append(q)
if not term3_by_corner:
    fail("%s selected no samples for term 3" % pfd_path)
    sys.exit(1)
term3_3s, term3_corner, term3_n = worst_corner_3sigma(term3_by_corner)
term3_fc = abs(term3_3s) * 1e15

# Cross-check both readings against the two figures spec/pll.md's own prose
# quotes for them, if it quotes the folded one (the signed one is graded
# again below, against the charge-accounting table's own row label).
folded_quote = re.search(
    r"quoted\s+(%s)\s*%%" % NUMBER, section_text
)
if folded_quote is not None and not agrees(
    folded_quote.group(1), term1_folded_3s
):
    fail(
        "%s quotes term 1's folded mean(|x|)+3*sd(|x|) as %s %%, but "
        "reducing %s's own committed samples the same way gives %.4f %% at "
        "%s (n=%d)"
        % (
            spec_rel,
            folded_quote.group(1),
            dc_path,
            term1_folded_3s,
            term1_folded_corner,
            term1_folded_n,
        )
    )

# --------------------------------------------------------------- DR-018 ---
# Icp, T_ov and the systematic charge asymmetry: worst-case figures over the
# mandated PVT grid, stated in DR-018's own Input table and RE-DERIVED below
# (rules 5-7) from the campaigns that table names as their source. The table
# is read for what it claims -- the trim code, the corner count, the record --
# and then graded against the evidence rather than trusted as the evidence.
dr018_section = re.search(
    r"^## Context\s*$(.*?)(?=^## )", dr018_text, re.M | re.S
)
if dr018_section is None:
    fail("%s has no '## Context' section" % dr018_rel)
    sys.exit(1)

dr018_tables = tables(dr018_section.group(1))
input_table = None
for table in dr018_tables:
    header = [plain(c).lower() for c in table[0]]
    if header[:1] == ["input"]:
        input_table = table
        break
if input_table is None:
    fail("%s has no 'Input | Value | Source' table" % dr018_rel)
    sys.exit(1)


def input_cells(prefix):
    """The (label, value, source) triple of one Input row, markup stripped.

    All three matter: the label states the reduction and the grid the figure
    is a worst case over, the value is the figure to grade, and the source
    names the committed campaign to reduce."""
    for cells in input_table[1:]:
        if plain(cells[0]).casefold().startswith(prefix.casefold()):
            padded = [plain(c) for c in cells] + ["", "", ""]
            return padded[0], padded[1], padded[2]
    fail(
        "%s's Input table has no row beginning %r" % (dr018_rel, prefix)
    )
    return None


t_ov_row = input_cells("Reset overlap")
icp_row = input_cells("Icp,")
q_sys_row = input_cells("Systematic per-event charge asymmetry")
q_stat_row = input_cells("Statistical residual net charge (term 3)")
if None in (t_ov_row, icp_row, q_sys_row, q_stat_row):
    sys.exit(1)
t_ov_cell = t_ov_row[1]
icp_cell = icp_row[1]
q_sys_cell = q_sys_row[1]
q_stat_cell = q_stat_row[1]


def stated_range(cell):
    """The written endpoints of a `a - b <unit>` range, as STRINGS (so each
    is graded at its own written precision), or `(None, x)` for a cell with a
    single figure (`x <unit> worst corner`). Anything in parentheses is a
    gloss, not a figure."""
    nums = re.findall(NUMBER, cell.split("(")[0])
    if not nums:
        fail("%s: no number in %r" % (dr018_rel, cell))
        return None, None
    if len(nums) == 1:
        return None, nums[0]
    ordered = sorted(nums, key=float)
    return ordered[0], ordered[-1]


# Every Input cell must state a figure at all before anything is graded
# against it; rules 5-7 below then grade each against the campaign that
# produced it.
for cell in (t_ov_cell, icp_cell, q_sys_cell, q_stat_cell):
    stated_range(cell)
if failures:
    sys.exit(1)

if not agrees(q_stat_cell.split()[0], term3_fc):
    fail(
        "%s states term 3's corner-combined |mean|+3sigma as %s fC, but "
        "reducing %s's committed qnet0_c samples the same way gives %.5f fC "
        "at %s (n=%d)"
        % (dr018_rel, q_stat_cell, pfd_path, term3_fc, term3_corner, term3_n)
    )

if failures:
    sys.exit(1)

# ------------------------------------------------------------ rules 5-7 ---
# The three remaining ingredients of the charge totals, each re-derived from
# the campaign its own Input row names, by the reduction its own Input row
# (or that campaign's own CSV header) states. Before issue #573 these were
# read from the Value column and the chain was graded from a table a human
# typed rather than from the grids the numbers were measured on.

#: A record id as the documents cite it: either in full
#: (`20260801-190821-734f483`) or in the elided form DR-018's own Source
#: column uses for two of these rows (`sim/cp-compliance/…-061841-c24ee3a`).
#: Both are resolved the same way -- by matching committed corner directories
#: against the cited tail -- so an elided citation is as checkable as a full
#: one, and an ambiguous one fails rather than picking a directory.
RECORD_TAIL = re.compile(r"(?:(\d{8})-)?(\d{6})-([0-9a-f]{7})")
LEG_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
}


def stated_corner_count(label, what):
    match = re.search(r"(\d+)\s+corners", label)
    if match is None:
        fail(
            "%s's Input row for %s does not state how many corners its figure "
            "is a worst case over -- a worst case over an unstated grid is "
            "not a checkable claim" % (dr018_rel, what)
        )
        return None
    return int(match.group(1))


def source_record(source, campaign, what):
    """The record id an Input row's Source column cites, resolved against the
    campaign's committed corner directories."""
    match = RECORD_TAIL.search(source)
    if match is None:
        fail(
            "%s's Input row for %s cites no record id in its Source column -- "
            "this check resolves the committed CSV to reduce from that id"
            % (dr018_rel, what)
        )
        return None
    tail = "%s-%s" % (match.group(2), match.group(3))
    if match.group(1):
        tail = "%s-%s" % (match.group(1), tail)
    found = sorted(
        os.path.basename(p)
        for p in glob.glob(
            os.path.join(repo_root, "sim", campaign, "corners", "*" + tail)
        )
        if os.path.isdir(p)
    )
    if not found:
        fail(
            "%s's Input row for %s cites record %s, but sim/%s/corners has no "
            "committed directory for it -- a figure cited against evidence "
            "that is not there is not a checked one"
            % (dr018_rel, what, tail, campaign)
        )
        return None
    if len(found) > 1:
        fail(
            "%s's Input row for %s cites record %s, which matches %d committed "
            "directories under sim/%s/corners (%s) -- an ambiguous citation is "
            "not a resolved one"
            % (dr018_rel, what, tail, len(found), campaign, ", ".join(found))
        )
        return None
    return found[0]


def corner_key(row, idx, columns):
    return tuple(row[idx[c]].strip() for c in columns)


# ---- rule 5: Icp at the trim code DR-018 prices, from sim/cp-compliance ---
icp_corners = stated_corner_count(icp_row[0], "Icp")
icp_record = source_record(icp_row[2], "cp-compliance", "Icp")
code_match = re.search(
    r"trim code\s*\((\d)\s*(\d)\s*,\s*([a-z]+)\s+unit legs\)", icp_row[0], re.I
)
if code_match is None:
    fail(
        "%s's Input row for Icp does not name the trim code it prices in the "
        "form 'trim code (11, four unit legs)' -- the code and its leg count "
        "are what select the rows to reduce, and this check reads them out of "
        "the row rather than assuming the largest code" % dr018_rel
    )
if None in (icp_corners, icp_record) or code_match is None:
    sys.exit(1)

icp_b1, icp_b0 = code_match.group(1), code_match.group(2)
icp_legs_word = code_match.group(3).lower()
if icp_legs_word not in LEG_WORDS:
    fail(
        "%s's Input row for Icp spells its leg count %r, which is not a "
        "number word this check knows" % (dr018_rel, icp_legs_word)
    )
    sys.exit(1)
icp_legs = LEG_WORDS[icp_legs_word]
# The campaign's own leg formula, stated in cp_dc.csv's header as
# "Icp in unit legs = 1 + b0 + 2*b1" and asserted against every selected row
# below; checked here against the word DR-018 writes so a code/leg-count
# disagreement between the two documents fails rather than silently picking
# one of them.
if 1 + int(icp_b0) + 2 * int(icp_b1) != icp_legs:
    fail(
        "%s's Input row for Icp names trim code %s%s as %s (%d) unit legs, but "
        "the campaign's own leg formula (1 + b0 + 2*b1) makes that code %d legs"
        % (
            dr018_rel, icp_b1, icp_b0, icp_legs_word, icp_legs,
            1 + int(icp_b0) + 2 * int(icp_b1),
        )
    )
    sys.exit(1)

icp_dc_rel = "sim/cp-compliance/corners/%s/cp_dc.csv" % icp_record
icp_range_rel = "sim/cp-compliance/corners/%s/cp_trim_range.csv" % icp_record
icp_dc_comments, icp_dc_idx, icp_dc_rows = load_csv(
    os.path.join(repo_root, icp_dc_rel),
    icp_dc_rel,
    ("process", "temp_c", "vdd_v", "b1", "b0", "units",
     "iup_mid_a", "idn_mid_a"),
)
icp_range_comments, icp_range_idx, icp_range_rows = load_csv(
    os.path.join(repo_root, icp_range_rel),
    icp_range_rel,
    ("units", "icp_min_a", "icp_max_a"),
)
if icp_dc_idx is None or icp_range_idx is None:
    sys.exit(1)

# The reduction convention is the campaign's own, read out of the header of
# the file that states it, not invented here.
conv = re.search(
    r"mean of the two polarities at Vctrl\s*=\s*(%s)\s*V,\s*min/max across "
    r"every corner" % NUMBER,
    icp_range_comments,
)
if conv is None:
    fail(
        "%s's header no longer states the reduction this check performs "
        "('mean of the two polarities at Vctrl = <v> V, min/max across every "
        "corner') -- the convention is the campaign's to state and this check "
        "must not substitute one of its own" % icp_range_rel
    )
    sys.exit(1)
conv_vctrl = float(conv.group(1))
window = re.search(
    r"Vctrl window under test:\s*(%s)\s*\.\.\s*(%s)\s*V,\s*nominal\s*(%s)\s*V"
    % (NUMBER, NUMBER, NUMBER),
    icp_dc_comments,
)
if window is None:
    fail(
        "%s's header no longer states its Vctrl window and nominal point -- "
        "this check reads which of the low/mid/high column triples the "
        "trim-range convention refers to out of that statement" % icp_dc_rel
    )
    sys.exit(1)
if float(window.group(3)) != conv_vctrl:
    fail(
        "%s reduces at Vctrl = %s V but %s's window nominal (its mid-window "
        "column) is %s V -- this check reads the mid-window columns and "
        "cannot do so when the two disagree"
        % (icp_range_rel, conv.group(1), icp_dc_rel, window.group(3))
    )
    sys.exit(1)

icp_by_corner = {}
for row in icp_dc_rows:
    if row[icp_dc_idx["b1"]].strip() != icp_b1:
        continue
    if row[icp_dc_idx["b0"]].strip() != icp_b0:
        continue
    key = corner_key(row, icp_dc_idx, ("process", "temp_c", "vdd_v"))
    if int(row[icp_dc_idx["units"]]) != icp_legs:
        fail(
            "%s row %s at trim code %s%s reports %s unit legs, but %s calls "
            "that code %s"
            % (
                icp_dc_rel, "/".join(key), icp_b1, icp_b0,
                row[icp_dc_idx["units"]], dr018_rel, icp_legs_word,
            )
        )
        break
    if key in icp_by_corner:
        fail(
            "%s has more than one row at corner %s, trim code %s%s -- this "
            "reduction is one point per corner and cannot choose between two"
            % (icp_dc_rel, "/".join(key), icp_b1, icp_b0)
        )
        break
    iup = abs(float(row[icp_dc_idx["iup_mid_a"]]))
    idn = abs(float(row[icp_dc_idx["idn_mid_a"]]))
    icp_by_corner[key] = (iup + idn) / 2.0
if failures:
    sys.exit(1)
if len(icp_by_corner) != icp_corners:
    fail(
        "%s states Icp as a worst case over %d corners, but %s has %d corner(s) "
        "at trim code %s%s -- a worst case over a subset of the mandated grid "
        "is not the figure the row claims"
        % (
            dr018_rel, icp_corners, icp_dc_rel, len(icp_by_corner),
            icp_b1, icp_b0,
        )
    )
    sys.exit(1)

icp_min_a = min(icp_by_corner.values())
icp_max_a = max(icp_by_corner.values())
icp_max_corner = max(icp_by_corner, key=lambda k: icp_by_corner[k])
icp_ua_measured = icp_max_a * 1e6
icp_lo_written, icp_hi_written = stated_range(icp_cell)
if icp_lo_written is None:
    fail(
        "%s's Icp row states a single figure (%r), not the `lo - hi` range "
        "this check grades both ends of" % (dr018_rel, icp_cell)
    )
    sys.exit(1)
if not agrees(icp_lo_written, icp_min_a * 1e6):
    fail(
        "%s states Icp's best corner as %s uA, but reducing %s's own committed "
        "grid at trim code %s%s the campaign's way gives %.5f uA"
        % (dr018_rel, icp_lo_written, icp_dc_rel, icp_b1, icp_b0, icp_min_a * 1e6)
    )
if not agrees(icp_hi_written, icp_ua_measured):
    fail(
        "%s states Icp's worst corner as %s uA, but reducing %s's own committed "
        "grid at trim code %s%s the campaign's way gives %.5f uA at %s"
        % (
            dr018_rel, icp_hi_written, icp_dc_rel, icp_b1, icp_b0,
            icp_ua_measured, "/".join(icp_max_corner),
        )
    )

# Second route to the same two numbers: the campaign's own committed
# reduction. `cp_trim_range.csv` is what the record's Result section prints,
# so a disagreement here means this check's reduction is not the campaign's,
# whatever the header says.
committed = None
for row in icp_range_rows:
    if int(row[icp_range_idx["units"]]) == icp_legs:
        committed = row
        break
if committed is None:
    fail(
        "%s has no row for %d unit legs -- the campaign's own reduction of the "
        "code %s%s DR-018 prices" % (icp_range_rel, icp_legs, icp_b1, icp_b0)
    )
else:
    for written, computed, which in (
        (committed[icp_range_idx["icp_min_a"]].strip(), icp_min_a, "min"),
        (committed[icp_range_idx["icp_max_a"]].strip(), icp_max_a, "max"),
    ):
        if not agrees_printed(written, computed):
            fail(
                "%s's committed icp_%s_a at %d legs is %s A, but reducing %s's "
                "per-point grid the same way gives %.6g A -- this check's "
                "reduction is not the one the campaign committed"
                % (icp_range_rel, which, icp_legs, written, icp_dc_rel, computed)
            )

# ---- rule 6: the reset overlap T_ov, from sim/pfd-deadzone ---------------
t_ov_corners = stated_corner_count(t_ov_row[0], "the reset overlap T_ov")
t_ov_source = re.search(r"([\w./-]+\.csv)", t_ov_row[2])
if t_ov_source is None:
    fail(
        "%s's Input row for the reset overlap cites no committed CSV in its "
        "Source column" % dr018_rel
    )
if t_ov_corners is None or t_ov_source is None:
    sys.exit(1)
t_ov_rel = t_ov_source.group(1)
_t_ov_comments, t_ov_idx, t_ov_rows = load_csv(
    os.path.join(repo_root, t_ov_rel),
    t_ov_rel,
    ("corner", "temp_c", "vdd", "vc", "d", "width_up", "width_dn", "q_zero"),
)
if t_ov_idx is None:
    sys.exit(1)

SI_SUFFIX = {"": 1.0, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}


def phase_offset_s(cell):
    """The dphi axis value a `pfd-deadzone` point id carries (`d0`, `d-1n`),
    parsed as seconds. Parsed rather than matched against the literal `d0` so
    the selection is of the axis VALUE the Input row names ('at zero phase
    error'), not of a label that happens to spell it."""
    match = re.fullmatch(
        r"d([+-]?\d*\.?\d+)\s*([munpf]?)s?", cell.strip(), re.I
    )
    if match is None:
        return None
    return float(match.group(1)) * SI_SUFFIX[match.group(2).lower()]


t_ov_by_corner = {}
zero_rows = 0
measured_rows = 0
for row in t_ov_rows:
    offset = phase_offset_s(row[t_ov_idx["d"]])
    if offset is None:
        fail(
            "%s has a dphi axis value %r this check cannot parse as a time -- "
            "it selects the zero-phase-error rows by the axis value, so an "
            "unparseable one must fail rather than be skipped"
            % (t_ov_rel, row[t_ov_idx["d"]])
        )
        break
    q_zero_measured = True
    try:
        float(row[t_ov_idx["q_zero"]])
    except ValueError:
        q_zero_measured = False
    if q_zero_measured:
        measured_rows += 1
    if offset != 0.0:
        if q_zero_measured:
            fail(
                "%s reports a measured q_zero at a row whose dphi is %s, not "
                "zero -- the campaign states q_zero is 'measured only at the "
                "dphi = 0 points', so this check's zero-phase selection and "
                "the campaign's own marker disagree"
                % (t_ov_rel, row[t_ov_idx["d"]])
            )
            break
        continue
    if not q_zero_measured:
        fail(
            "%s reports q_zero as %r at a dphi = 0 row -- this check's "
            "zero-phase selection and the campaign's own marker disagree"
            % (t_ov_rel, row[t_ov_idx["q_zero"]])
        )
        break
    zero_rows += 1
    key = corner_key(row, t_ov_idx, ("corner", "temp_c", "vdd"))
    width = min(
        float(row[t_ov_idx["width_up"]]), float(row[t_ov_idx["width_dn"]])
    )
    if key not in t_ov_by_corner or width < t_ov_by_corner[key]:
        t_ov_by_corner[key] = width
if failures:
    sys.exit(1)
if zero_rows != measured_rows:
    fail(
        "%s: this check selected %d zero-phase-error row(s) but the campaign "
        "marks %d as measured in q_zero" % (t_ov_rel, zero_rows, measured_rows)
    )
    sys.exit(1)
if len(t_ov_by_corner) != t_ov_corners:
    fail(
        "%s states T_ov as a range over %d corners, but %s has %d corner(s) at "
        "zero phase error"
        % (dr018_rel, t_ov_corners, t_ov_rel, len(t_ov_by_corner))
    )
    sys.exit(1)

t_ov_min_s = min(t_ov_by_corner.values())
t_ov_max_s = max(t_ov_by_corner.values())
t_ov_max_corner = max(t_ov_by_corner, key=lambda k: t_ov_by_corner[k])
t_ov_ns_measured = t_ov_max_s * 1e9
t_ov_lo_written, t_ov_hi_written = stated_range(t_ov_cell)
if t_ov_lo_written is None:
    fail(
        "%s's reset-overlap row states a single figure (%r), not the "
        "`lo - hi` range this check grades both ends of"
        % (dr018_rel, t_ov_cell)
    )
    sys.exit(1)
if not agrees(t_ov_lo_written, t_ov_min_s * 1e9):
    fail(
        "%s states the shortest reset overlap as %s ns, but the smallest "
        "UP/DN pulse at zero phase error in %s is %.5f ns"
        % (dr018_rel, t_ov_lo_written, t_ov_rel, t_ov_min_s * 1e9)
    )
if not agrees(t_ov_hi_written, t_ov_ns_measured):
    fail(
        "%s states the worst-corner reset overlap as %s ns, but reducing %s "
        "the way the row itself states (min UP/DN pulse at zero phase error, "
        "per corner) gives %.5f ns at %s"
        % (
            dr018_rel, t_ov_hi_written, t_ov_rel, t_ov_ns_measured,
            "/".join(t_ov_max_corner),
        )
    )

# The cell names the corner its worst case lands at; grade that too -- a
# reduction landing on the right number at the wrong corner is not the same
# reduction.
worst_gloss = re.search(r"\(worst\s+([^)]*)\)", t_ov_cell, re.I)
if worst_gloss is None:
    fail(
        "%s's reset-overlap cell no longer names the corner its worst case "
        "lands at ('(worst <process>/<temp> C/<vdd> V)')" % dr018_rel
    )
else:
    named = re.match(
        r"([A-Za-z_]+)\s*/\s*(%s)\s*°?\s*C\s*/\s*(%s)\s*V" % (NUMBER, NUMBER),
        worst_gloss.group(1).strip(),
    )
    if named is None:
        fail(
            "%s's reset-overlap cell names its worst corner as %r, which this "
            "check cannot read as <process>/<temp> C/<vdd> V"
            % (dr018_rel, worst_gloss.group(1).strip())
        )
    else:
        reduced = (
            t_ov_max_corner[0],
            float(t_ov_max_corner[1]),
            float(t_ov_max_corner[2]),
        )
        claimed = (
            named.group(1),
            float(named.group(2)),
            float(named.group(3)),
        )
        if reduced != claimed:
            fail(
                "%s names %s as T_ov's worst corner, but the worst corner in "
                "%s is %s"
                % (
                    dr018_rel, worst_gloss.group(1).strip(), t_ov_rel,
                    "/".join(t_ov_max_corner),
                )
            )

# ---- rule 7: the systematic per-event charge asymmetry -------------------
q_sys_record = source_record(
    q_sys_row[2], "cp-compliance", "the systematic charge asymmetry"
)
if q_sys_record is None:
    sys.exit(1)
q_sys_rel = "sim/cp-compliance/corners/%s/cp_switch.csv" % q_sys_record
_q_sys_comments, q_sys_idx, q_sys_rows = load_csv(
    os.path.join(repo_root, q_sys_rel),
    q_sys_rel,
    ("process", "temp_c", "vdd_v", "vctrl_v", "qup_c", "qdn_c"),
)
if q_sys_idx is None:
    sys.exit(1)

q_sys_points = []
q_sys_corners = set()
for row in q_sys_rows:
    q_sys_corners.add(corner_key(row, q_sys_idx, ("process", "temp_c", "vdd_v")))
    q_sys_points.append(
        abs(float(row[q_sys_idx["qup_c"]]) + float(row[q_sys_idx["qdn_c"]])) * 1e15
    )
if not q_sys_points:
    fail("%s selected no switching events" % q_sys_rel)
    sys.exit(1)
# This row states no corner count of its own; the grid it must have been
# measured over is the one its sibling Input rows state, which are the same
# mandated PVT matrix. A worst case over fewer corners is a different claim.
if icp_corners != t_ov_corners:
    fail(
        "%s's Input rows state different corner counts (%d for Icp, %d for "
        "T_ov) -- this check reads the mandated grid size from them and they "
        "must agree" % (dr018_rel, icp_corners, t_ov_corners)
    )
    sys.exit(1)
if len(q_sys_corners) != icp_corners:
    fail(
        "%s is a worst case over %d corner(s), but DR-018's other inputs are "
        "stated over %d -- a worst case over a subset of the mandated grid is "
        "not the figure the row claims"
        % (q_sys_rel, len(q_sys_corners), icp_corners)
    )
    sys.exit(1)

q_sys_fc_measured = max(q_sys_points)
q_sys_median_fc = statistics.median(q_sys_points)
q_sys_written = stated_range(q_sys_cell)[1]
if q_sys_written is None:
    sys.exit(1)
if not agrees(q_sys_written, q_sys_fc_measured):
    fail(
        "%s states the systematic per-event charge asymmetry as %s fC worst "
        "corner, but the largest |qup + qdn| in %s is %.5f fC"
        % (dr018_rel, q_sys_written, q_sys_rel, q_sys_fc_measured)
    )

# DR-006 SS8 is where this figure was priced; it states a worst case AND a
# median for the same quantity, and both are graded so a reduction that
# reproduced only the maximum (a different population with the same tail)
# cannot pass.
dr006_ref = re.search(r"DR-(\d{3})", q_sys_row[2])
if dr006_ref is None:
    fail(
        "%s's Input row for the systematic charge asymmetry no longer names "
        "the decision record that priced it" % dr018_rel
    )
else:
    matches = sorted(
        glob.glob(
            os.path.join(
                repo_root, "spec", "decision-records",
                "DR-%s-*.md" % dr006_ref.group(1),
            )
        )
    )
    if not matches:
        fail(
            "%s cites DR-%s for the systematic charge asymmetry, but no such "
            "decision record exists" % (dr018_rel, dr006_ref.group(1))
        )
    else:
        dr006_rel = os.path.relpath(matches[0], repo_root)
        with open(matches[0], encoding="utf-8") as fh:
            dr006_text = fh.read()
        priced = re.search(
            # Whitespace-tolerant: the sentence is prose and may be rewrapped.
            r"q_up \+ q_dn\|`?\s*=\s*\*\*(%s)\s*fC\s+worst case,\s*(%s)\s*fC"
            r"\s+median\*\*" % (NUMBER, NUMBER),
            dr006_text,
        )
        if priced is None:
            fail(
                "%s no longer states `|q_up + q_dn|` as '<x> fC worst case, "
                "<y> fC median' -- this check grades both figures against the "
                "campaign %s names, and cannot grade a restatement it cannot "
                "find" % (dr006_rel, dr018_rel)
            )
        else:
            if not agrees(priced.group(1), q_sys_fc_measured):
                fail(
                    "%s prices the systematic charge asymmetry at %s fC worst "
                    "case, but the largest |qup + qdn| in %s is %.5f fC"
                    % (dr006_rel, priced.group(1), q_sys_rel, q_sys_fc_measured)
                )
            if not agrees(priced.group(2), q_sys_median_fc):
                fail(
                    "%s states the systematic charge asymmetry's median as %s "
                    "fC, but the median |qup + qdn| over %s's %d committed "
                    "switching events is %.5f fC"
                    % (
                        dr006_rel, priced.group(2), q_sys_rel,
                        len(q_sys_points), q_sys_median_fc,
                    )
                )

if failures:
    sys.exit(1)

# ------------------------------------------------------- accounting table --
accounting = None
for table in tables(section_text):
    header = [plain(c).lower() for c in table[0]]
    if (
        len(header) >= 3
        and header[0].startswith("charge accounting at")
        and header[1].startswith("total")
        and header[2].startswith("derived spur")
    ):
        accounting = table
        break
if accounting is None:
    fail(
        "%s has no charge-accounting table (header 'Charge accounting at … "
        "| Total ΔQ | Derived spur')" % spec_rel
    )
    sys.exit(1)

row_excluded = row_measured = row_budgeted = None
measured_pct = budgeted_pct = None
for cells in accounting[1:]:
    label = plain(cells[0])
    if "still excluded" in label.casefold():
        row_excluded = cells
    m = re.search(r"measured\s+(%s)\s*%%" % NUMBER, label, re.I)
    if m:
        row_measured = cells
        measured_pct = float(m.group(1))
    m = re.search(r"budgeted\D*(%s)\s*%%" % NUMBER, label, re.I)
    if m:
        row_budgeted = cells
        budgeted_pct = float(m.group(1))

if row_excluded is None:
    fail(
        "%s's charge-accounting table has no row naming term 1 'still "
        "excluded' -- the row this check checks q_systematic + term 3 "
        "against" % spec_rel
    )
if row_measured is None or measured_pct is None:
    fail(
        "%s's charge-accounting table has no row naming term 1 'measured "
        "<x> %%' -- the row this check checks against the signed reduction "
        "above" % spec_rel
    )
if row_budgeted is None or budgeted_pct is None:
    fail(
        "%s's charge-accounting table has no row naming term 1 'budgeted "
        "<y> %%'" % spec_rel
    )
if failures:
    sys.exit(1)

if not agrees("%.4f" % measured_pct, term1_signed_3s):
    fail(
        "%s's charge-accounting table states term 1 'measured' at %s %%, "
        "but %s's own signed samples reduce (worst corner %s, n=%d) to "
        "%.4f %%"
        % (
            spec_rel,
            measured_pct,
            dc_path,
            term1_signed_corner,
            term1_signed_n,
            term1_signed_3s,
        )
    )


def cell_number(cell, what):
    match = re.search(NUMBER, plain(cell))
    if not match:
        fail("%s: no number in %r" % (what, plain(cell)))
        return None
    return match.group(0)


q_excluded_written = cell_number(row_excluded[1], "row 'still excluded'")
q_measured_written = cell_number(row_measured[1], "row 'measured'")
q_budgeted_written = cell_number(row_budgeted[1], "row 'budgeted'")
if None in (q_excluded_written, q_measured_written, q_budgeted_written):
    sys.exit(1)

# Every ingredient below is the figure rules 5-7 reduced from its own
# campaign's committed CSV, not the figure DR-018's Input table states for it
# (the table is graded against those reductions above).
q_excluded_computed = q_sys_fc_measured + term3_fc
if not agrees(q_excluded_written, q_excluded_computed):
    fail(
        "%s's charge-accounting table states the 'still excluded' total as "
        "%s fC, but its own ingredients (q_systematic %.5f fC, reduced from "
        "%s + term 3 %.5f fC, corner-combined from %s) sum to %.5f fC"
        % (
            spec_rel,
            q_excluded_written,
            q_sys_fc_measured,
            q_sys_rel,
            term3_fc,
            os.path.relpath(pfd_path, repo_root),
            q_excluded_computed,
        )
    )


def dq1_fc(pct):
    # ΔQ1 = m * Icp * T_ov, m dimensionless, Icp in A, T_ov in s -> C -> fC
    return (
        (pct / 100.0)
        * (icp_ua_measured * 1e-6)
        * (t_ov_ns_measured * 1e-9)
        * 1e15
    )


q_measured_computed = q_excluded_computed + dq1_fc(measured_pct)
if not agrees(q_measured_written, q_measured_computed):
    fail(
        "%s's charge-accounting table states the 'measured %s %%' total as "
        "%s fC, but %.5f fC (excluded total) + %.5f fC (term 1 at %s %% x "
        "Icp %.5f uA x T_ov %.5f ns, both reduced from their own campaigns) "
        "is %.5f fC"
        % (
            spec_rel,
            measured_pct,
            q_measured_written,
            q_excluded_computed,
            dq1_fc(measured_pct),
            measured_pct,
            icp_ua_measured,
            t_ov_ns_measured,
            q_measured_computed,
        )
    )

q_budgeted_computed = q_excluded_computed + dq1_fc(budgeted_pct)
if not agrees(q_budgeted_written, q_budgeted_computed):
    fail(
        "%s's charge-accounting table states the 'budgeted %s %%' total as "
        "%s fC, but %.5f fC (excluded total) + %.5f fC (term 1 at %s %% x "
        "Icp %.5f uA x T_ov %.5f ns, both reduced from their own campaigns) "
        "is %.5f fC"
        % (
            spec_rel,
            budgeted_pct,
            q_budgeted_written,
            q_excluded_computed,
            dq1_fc(budgeted_pct),
            budgeted_pct,
            icp_ua_measured,
            t_ov_ns_measured,
            q_budgeted_computed,
        )
    )

if failures:
    sys.exit(1)

print(
    "OK: %s's reference-spur charge totals reproduce from every ingredient's "
    "own committed campaign -- term 1 signed |mean|+3sigma %.4f %% at %s "
    "(n=%d), term 1 folded mean(|x|)+3*sd(|x|) %.4f %% at %s (n=%d), term 3 "
    "|mean|+3sigma %.5f fC at %s (n=%d), all from "
    "sim/mc-cp-mismatch/corners/%s; q_systematic %.5f fC worst of %d corners "
    "(median %.5f fC) from %s; Icp %.5f uA at trim code %s%s, worst of %d "
    "corners, from %s; T_ov %.5f ns at %s, worst of %d corners, from %s. The "
    "'still excluded' (%s fC), 'measured' (%s fC) and 'budgeted' (%s fC) "
    "totals each follow from those figures"
    % (
        spec_rel,
        term1_signed_3s,
        term1_signed_corner,
        term1_signed_n,
        term1_folded_3s,
        term1_folded_corner,
        term1_folded_n,
        term3_fc,
        term3_corner,
        term3_n,
        record_id,
        q_sys_fc_measured,
        len(q_sys_corners),
        q_sys_median_fc,
        q_sys_rel,
        icp_ua_measured,
        icp_b1,
        icp_b0,
        len(icp_by_corner),
        icp_dc_rel,
        t_ov_ns_measured,
        "/".join(t_ov_max_corner),
        len(t_ov_by_corner),
        t_ov_rel,
        q_excluded_written,
        q_measured_written,
        q_budgeted_written,
    )
)
PY
