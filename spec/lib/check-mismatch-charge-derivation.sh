#!/usr/bin/env bash
#
# Fails if `spec/pll.md`'s reference-spur charge-accounting totals do not
# reproduce from the committed Monte Carlo samples and inputs DR-018 cites for
# them.
#
# WHY THIS EXISTS (issue #237)
#
# `spec/lib/check-spur-derivation-arithmetic.sh` grades the reference-spur
# derivation's arithmetic *from* its charge totals (7.93 / 11.19 / 11.66 fC)
# onward to a dBc figure. Its own header states what it does not do:
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
#   ΔQ total = q_systematic + q_term3 [+ m x Icp x T_ov]
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
#    with q_systematic, Icp and T_ov read from DR-018's own Input table (each
#    a worst-case figure over a 45-corner grid this check does not re-sweep --
#    see "WHAT IT DOES NOT DO"). Every total must agree with the table's own
#    ΔQ column at the precision written.
#
# WHAT IT DOES NOT DO
#
# It does not re-derive `Icp`, `T_ov` or the systematic charge asymmetry
# (3.68 fC) from their own campaigns (`cp-compliance`, `pfd-deadzone`) --
# those are worst-of-45-corners figures this check takes from DR-018's Input
# table exactly as the derivation itself does, the same way
# `check-spur-derivation-arithmetic.sh` takes C2 and the TIE scale point as
# given. What moves here is narrower and specific: the two figures that
# DR-018 states were "computed by hand from the committed 300 raw samples" --
# term 1's signed `|mean| + 3sigma` and term 3's -- now have a machine
# reduction, and the totals `check-spur-derivation-arithmetic.sh` receives are
# graded back to it.
#
# Usage: spec/lib/check-mismatch-charge-derivation.sh
# Exit codes: 0 term 1 and term 3 reproduce from their committed samples and
#               every charge-accounting total reproduces from them,
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
import math
import os
import re
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
# Icp, T_ov and the systematic charge asymmetry: worst-of-45-corners figures
# this check takes from DR-018's own Input table rather than re-sweeping
# cp-compliance/pfd-deadzone itself (see "WHAT IT DOES NOT DO").
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


def input_row(prefix):
    for cells in input_table[1:]:
        if plain(cells[0]).casefold().startswith(prefix.casefold()):
            return plain(cells[1])
    fail(
        "%s's Input table has no row beginning %r" % (dr018_rel, prefix)
    )
    return None


t_ov_cell = input_row("Reset overlap")
icp_cell = input_row("Icp,")
q_sys_cell = input_row("Systematic per-event charge asymmetry")
q_stat_cell = input_row("Statistical residual net charge (term 3)")
if None in (t_ov_cell, icp_cell, q_sys_cell, q_stat_cell):
    sys.exit(1)


def worst_of_range(cell):
    """The larger of a `a - b <unit>` range, or the single number in a cell
    with no range (`x <unit> worst corner`)."""
    nums = [float(m) for m in re.findall(NUMBER, cell.split("(")[0])]
    if not nums:
        fail("%s: no number in %r" % (dr018_rel, cell))
        return None
    return max(nums)


t_ov_ns = worst_of_range(t_ov_cell)
icp_ua = worst_of_range(icp_cell)
q_sys_fc = worst_of_range(q_sys_cell)
q_stat_stated_fc = worst_of_range(q_stat_cell)
if None in (t_ov_ns, icp_ua, q_sys_fc, q_stat_stated_fc):
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

q_excluded_computed = q_sys_fc + term3_fc
if not agrees(q_excluded_written, q_excluded_computed):
    fail(
        "%s's charge-accounting table states the 'still excluded' total as "
        "%s fC, but its own ingredients (q_systematic %s fC + term 3 %.5f "
        "fC, corner-combined from %s) sum to %.5f fC"
        % (
            spec_rel,
            q_excluded_written,
            q_sys_fc,
            term3_fc,
            os.path.relpath(pfd_path, repo_root),
            q_excluded_computed,
        )
    )


def dq1_fc(pct):
    # ΔQ1 = m * Icp * T_ov, m dimensionless, Icp in A, T_ov in s -> C -> fC
    return (pct / 100.0) * (icp_ua * 1e-6) * (t_ov_ns * 1e-9) * 1e15


q_measured_computed = q_excluded_computed + dq1_fc(measured_pct)
if not agrees(q_measured_written, q_measured_computed):
    fail(
        "%s's charge-accounting table states the 'measured %s %%' total as "
        "%s fC, but %.5f fC (excluded total) + %.5f fC (term 1 at %s %% x "
        "Icp %s uA x T_ov %s ns) is %.5f fC"
        % (
            spec_rel,
            measured_pct,
            q_measured_written,
            q_excluded_computed,
            dq1_fc(measured_pct),
            measured_pct,
            icp_ua,
            t_ov_ns,
            q_measured_computed,
        )
    )

q_budgeted_computed = q_excluded_computed + dq1_fc(budgeted_pct)
if not agrees(q_budgeted_written, q_budgeted_computed):
    fail(
        "%s's charge-accounting table states the 'budgeted %s %%' total as "
        "%s fC, but %.5f fC (excluded total) + %.5f fC (term 1 at %s %% x "
        "Icp %s uA x T_ov %s ns) is %.5f fC"
        % (
            spec_rel,
            budgeted_pct,
            q_budgeted_written,
            q_excluded_computed,
            dq1_fc(budgeted_pct),
            budgeted_pct,
            icp_ua,
            t_ov_ns,
            q_budgeted_computed,
        )
    )

if failures:
    sys.exit(1)

print(
    "OK: %s's reference-spur charge totals reproduce from "
    "sim/mc-cp-mismatch/corners/%s's committed samples -- term 1 signed "
    "|mean|+3sigma %.4f %% at %s (n=%d), term 1 folded mean(|x|)+3*sd(|x|) "
    "%.4f %% at %s (n=%d), term 3 |mean|+3sigma %.5f fC at %s (n=%d); the "
    "'still excluded' (%s fC), 'measured' (%s fC) and 'budgeted' (%s fC) "
    "totals each reproduce from those figures plus DR-018's stated Icp "
    "(%s uA) and T_ov (%s ns)"
    % (
        spec_rel,
        record_id,
        term1_signed_3s,
        term1_signed_corner,
        term1_signed_n,
        term1_folded_3s,
        term1_folded_corner,
        term1_folded_n,
        term3_fc,
        term3_corner,
        term3_n,
        q_excluded_written,
        q_measured_written,
        q_budgeted_written,
        icp_ua,
        t_ov_ns,
    )
)
PY
