#!/usr/bin/env bash
#
# Fails if spec/pll.md's reference-spur derivation does not reproduce its own
# arithmetic, or if the Chipalooza proposal quotes a dBc figure that derivation
# (and the measured table beside it) does not contain.
#
# WHY THIS EXISTS (issue #237)
#
# `sim/lib/check-quoted-value-provenance.sh` grades the *measured* value: it
# re-derives a figure quoted in the proposal's section 5 from a committed
# per-corner CSV. That check's own section 5.1 lists what it cannot reach, and
# one entry on that list is not a measurement at all:
#
#   Reference spur | `≈ −57.0 dBc` | A hand derivation that re-prices DR-018's
#   term stack over a Monte Carlo campaign, not a reduction of one CSV.
#
# True, and it left the whole derived half of this row ungraded. The reference
# spur is the row where that matters most: it is the only row in the proposal
# whose *verdict* turns on a derived number rather than a measured one. The
# closed-loop campaign measures 5 of 45 PVT points, all at 150 MHz with device
# mismatch off, so what the proposal tells an outside reader about the binding
# 200 MHz point -- "1.6 dB inside the line" rather than the ~6 dB the older
# −61 dBc figure implied -- is a hand derivation: a charge total carried
# through C2, a recorded TIE scale point, the narrowband-FM relation, and a
# 20·log₁₀ at the end. Five numbers, in two tables, quoted in a third
# document, with nothing mechanically tying any of them together.
#
# A hand derivation is not ungradeable. Every ingredient it uses is written
# down in the table that states it, so the arithmetic is reproducible to the
# digit -- which is what this check does. It is the counterpart of
# check-quoted-value-provenance.sh for the figures that have no CSV to reduce:
# same contract (re-derive, and match at the precision written), different
# evidence (the ratified derivation's own ingredients instead of committed
# per-corner measurements).
#
# What it found on its first run is a small thing said plainly rather than a
# defect: the `≈ −57.0 dBc` row is −56.95 dBc carried through unrounded, which
# rounds to −56.9 at the precision it is written to. The `≈` is load-bearing,
# and rule 4 below is the only place in this check that accepts a figure which
# does not match at its written precision -- explicitly, for figures that
# carry that marker, by one unit in the last written place.
#
# THE RULES
#
# All three graded tables must live inside spec/pll.md's `## Reference spur`
# section. A table this check cannot find is a failure, never a pass.
#
# 1. FORMULA FIDELITY. The derivation must still state the two relations this
#    check implements -- `θ = 2π·f_out·TIE` for the phase deviation and
#    `20·log₁₀(θ/2)` for the single-sideband spur -- and the measured table's
#    own header must still state its scaling as `+20·log₁₀(hi/lo)`. This check
#    reads the relations out of the specification rather than asserting them:
#    if a ratification changes how the spur is derived, the check fails in the
#    same commit instead of silently grading the old arithmetic. That is the
#    same principle check-quoted-value-provenance.sh applies to the Icp
#    trim-code rule and check-pvt-coverage-claims.sh to the mandated grid.
#
# 2. WORST-CASE SUM. The step table's `Worst-case sum` row must equal the sum
#    of the two charge rows above it (systematic asymmetry + statistical
#    residual), at the precision written. The table calls itself a "linear add
#    (conservative)"; this is that claim, graded.
#
# 3. STEP CHAIN. Each remaining row of the step table must follow from the row
#    above it: peak ripple from ΔQ/C2, peak TIE from the recorded ps-per-mV
#    scale point, peak phase deviation from `θ = 2π·f_out·TIE`, and the spur
#    from `20·log₁₀(θ/2)`.
#
#    The chain is graded on the *displayed* figures, because that is how the
#    table is written: each row carries the rounded value forward (θ from
#    1.35 ps, not from 1.34897 ps). Grading an unrounded chain instead would
#    fail on the rounding rather than on any error -- 1.70e-3 rad is right
#    from the displayed TIE and wrong from the unrounded one. So that rounding
#    cannot hide a real error, the rule also requires the end-to-end unrounded
#    chain to agree with the displayed final spur within 0.1 dB.
#
# 4. CHARGE-ACCOUNTING CHAIN. Every row of the charge-accounting table must
#    reproduce its own derived spur from its own total ΔQ through the same
#    chain, unrounded end to end (that table displays no intermediates), at
#    the precision written. A figure written with `≈` or `~` is accepted
#    within one unit of the last written place, and the OK line reports how
#    many figures needed it -- see the `≈ −57.0 dBc` note above.
#
# 5. SCALING TO THE BINDING FREQUENCY. The measured table's stated scaling
#    constant must equal `20·log₁₀(hi/lo)` computed from the two frequencies
#    its own header names, and every row's scaled figure must equal that
#    row's measured figure plus that constant, at the precision written. This
#    is the arithmetic the proposal's verdict rests on -- the two cold corners
#    are UNMET at 200 MHz only after scaling -- and it was written out by hand
#    five times.
#
# 6. CARRY-THROUGH. Every absolute dBc figure anywhere in the proposal must
#    equal, at the precision written, one of: a measured figure, a scaled
#    figure, a derived figure from either table, or the ratified `≤ −55 dBc`
#    line itself. Rules 1-5 grade the specification's arithmetic; this grades
#    that the document mailed to an outside reader quotes that arithmetic and
#    not a number of its own. It is one-directional on purpose: the proposal
#    need not quote every derived row (it does not quote −59.9 dBc), but it
#    may not quote a dBc figure the derivation does not contain.
#
#    A figure is allowed to match either the value the specification *writes*
#    or the value this check *computes* for the same row -- the proposal may
#    quote the derivation's own arithmetic at finer precision than the
#    specification rounds it to. It does: section 5.2 states that the
#    `≈ −57.0 dBc` row is −56.95 dBc unrounded, which is the disclosure that
#    makes the `≈` visible to a reader, and a rule that rejected it would be
#    pushing the document towards saying less than it knows.
#
# WHAT IT DOES NOT DO
#
# It grades the derivation *from* its charge totals (7.93 / 11.19 / 11.66 fC)
# onward to a dBc figure, not where those totals themselves come from --
# `spec/lib/check-mismatch-charge-derivation.sh` is the sibling check for
# that, reducing the corner-combined statistical residual and term-1 products
# DR-018 derives in prose straight from `sim/mc-cp-mismatch`'s 300 committed
# samples (the reduction this check's own header used to say did not exist),
# and chaining them into the same three totals graded here. That check still
# takes `Icp`, `T_ov` and the systematic charge asymmetry from DR-018's own
# Input table rather than re-sweeping `cp-compliance`/`pfd-deadzone`'s
# 45-corner grids -- see its own header for that boundary.
#
# Nor does it grade the dB *margins* stated in prose ("1.6 dB inside the
# line", "~12 dB at the two cold corners"): rule 6 is restricted to absolute
# dBc figures, because a bare "dB" in this document is as often a spread or a
# reserve as it is a difference of two graded numbers.
#
# Usage: spec/lib/check-spur-derivation-arithmetic.sh
# Exit codes: 0 the derivation reproduces itself and the proposal quotes only
#               figures it contains,
#             1 a derived figure does not follow from its own ingredients, a
#               stated relation is no longer the one this check implements, the
#               proposal quotes a dBc figure the derivation does not contain, a
#               graded file or table is missing, or a table fails to parse (a
#               broken parser must not look like a clean tree).

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
import math
import os
import re
import sys

repo_root, spec_rel, proposal_rel = sys.argv[1:4]

#: The two relations rule 1 pins. Written as the specification writes them,
#: with the same characters, so that re-wording the derivation trips the rule
#: rather than sliding past it.
PHASE_RELATION = "θ = 2π·f_out·TIE"
SPUR_RELATION = "20·log₁₀(θ/2)"

#: A number as this document writes one: optional Unicode minus, optional
#: `≈`/`~` marker, decimal digits, optional `e-3` exponent.
NUMBER = r"(?:≈|~)?\s*[−+-]?\d+(?:\.\d+)?(?:e[−+-]?\d+)?"

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
    """Cell text with Markdown emphasis, escapes and Unicode dashes removed."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = text.replace("**", "").replace("`", "").replace("\\|", "|")
    for dash in ("—", "–", "‒", "‑"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


class Figure(object):
    """A number as written, with the precision and marker it was written at.

    Grading "at the precision written" needs the written form, not just its
    value: `−61 dBc` is graded to the unit and `−56.6 dBc` to a tenth, and the
    difference is the whole point of the contract this check shares with
    check-quoted-value-provenance.sh.
    """

    def __init__(self, raw):
        self.raw = raw.strip()
        text = self.raw
        self.approx = bool(re.match(r"^\s*(?:≈|~)", text))
        text = re.sub(r"^\s*(?:≈|~)\s*", "", text)
        text = text.replace("−", "-").replace("+", "").strip()
        self.exponent = 0
        mantissa = text
        match = re.match(r"^(-?\d+(?:\.\d+)?)e(-?\d+)$", text)
        if match:
            mantissa, self.exponent = match.group(1), int(match.group(2))
        self.decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
        self.value = float(mantissa) * (10 ** self.exponent)

    def __str__(self):
        return self.raw

    def agrees(self, derived):
        """True if `derived` matches this figure at the precision written.

        An `≈`-marked figure is accepted within one unit of its last written
        place; every other figure must round to exactly what is written.
        """
        scale = 10 ** self.exponent
        written = self.value / scale
        computed = derived / scale
        if self.approx:
            return abs(computed - written) <= 10 ** (-self.decimals) + 1e-12
        fmt = "%%.%df" % self.decimals
        return (fmt % computed) == (fmt % written)


def figures_in(text):
    """Every absolute dBc figure in `text`, including `a…b dBc` ranges.

    A single `dBc` often covers two numbers ("−57.0…−72.7 dBc",
    "−54.5/−54.9 dBc"), so a pattern anchored only on the number nearest the
    unit would silently skip half the figures a reader sees.
    """
    found = []
    pattern = re.compile(
        r"(%s)(?:\s*(?:…|\.\.\.|/|-|to)\s*(%s))?\s*dBc" % (NUMBER, NUMBER)
    )
    for match in pattern.finditer(text):
        for group in match.groups():
            if group:
                found.append(Figure(group))
    return found


#: Stands in for an escaped `\|` while a row is split on its real pipes. The
#: step table's first row is `... \|q_up + q_dn\|, worst corner`, which a naive
#: split reads as three cells of a three-column table -- so the value column
#: shifts and the number this check grades is not in it.
ESCAPED_PIPE = "\x00"


def tables(block):
    """Every Markdown table in `block`, header row first."""
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


def table_matching(found, predicate, what):
    for table in found:
        if predicate([plain(c) for c in table[0]]):
            return table
    fail(
        "%s has no %s inside its '## Reference spur' section -- this check "
        "cannot grade a derivation it cannot find, and a missing table is not "
        "a clean one" % (spec_rel, what)
    )
    return None


def cell_figure(cell, what):
    """The first number in `cell`, as written."""
    match = re.search(NUMBER, plain(cell))
    if not match:
        fail("%s: no number in %r" % (what, plain(cell)))
        return None
    return Figure(match.group(0))


def row_labelled(table, prefix, what):
    for cells in table[1:]:
        if plain(cells[0]).casefold().startswith(prefix.casefold()):
            return cells
    fail(
        "%s's %s has no row beginning %r. The chain this check grades is the "
        "one the table states; a renamed or deleted step must fail here rather "
        "than drop out of the grading silently" % (spec_rel, what, prefix)
    )
    return None


spec_text = read(spec_rel)
proposal_text = read(proposal_rel)
if spec_text is None or proposal_text is None:
    sys.exit(1)

section = re.search(
    r"^## Reference spur[^\n]*\n(.*?)(?=^## )", spec_text, re.M | re.S
)
if section is None:
    sys.stderr.write(
        "FAIL: %s has no '## Reference spur' section -- the derivation this "
        "check grades lives there\n" % spec_rel
    )
    sys.exit(1)

found = tables(section.group(1))

measured = table_matching(
    found,
    lambda header: len(header) >= 3
    and header[1].lower().startswith("measured spur at")
    and header[2].lower().startswith("scaled to"),
    "measured-spur table (header 'Measured spur at … | Scaled to …')",
)
step = table_matching(
    found,
    lambda header: len(header) >= 3
    and [h.lower() for h in header[:3]] == ["step", "value", "source"],
    "derivation step table (header 'Step | Value | Source')",
)
accounting = table_matching(
    found,
    lambda header: len(header) >= 3
    and header[0].lower().startswith("charge accounting at")
    and header[1].lower().startswith("total")
    and header[2].lower().startswith("derived spur"),
    "charge-accounting table (header 'Charge accounting at … | Total ΔQ | "
    "Derived spur')",
)
if measured is None or step is None or accounting is None:
    sys.exit(1)

# --------------------------------------------------------------- rule 1 ---
# The relations this check implements must be the ones the specification
# states. Both are quoted in the step table's Source column.
step_text = "\n".join(" | ".join(cells) for cells in step)
for relation in (PHASE_RELATION, SPUR_RELATION):
    if relation not in step_text:
        fail(
            "%s's derivation step table no longer states %r. This check's "
            "arithmetic implements that relation; if the derivation changed, "
            "the check must change with it in the same commit rather than "
            "keep grading the superseded chain"
            % (spec_rel, relation)
        )

scaling = re.search(
    r"\+?20·log₁₀\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)`?\s*=\s*(\+?%s)\s*dB"
    % NUMBER,
    " | ".join(measured[0]),
)
if scaling is None:
    fail(
        "%s's measured-spur table header does not state its scaling as "
        "`+20·log₁₀(hi/lo)` = <constant> dB (header reads: %s). Rule 5 grades "
        "the scaled column against the constant the header itself names"
        % (spec_rel, " | ".join(measured[0]))
    )

if failures:
    sys.exit(1)

# --------------------------------------------------------------- rule 2 ---
systematic = row_labelled(step, "Systematic per-event charge asymmetry", "step table")
statistical = row_labelled(step, "Statistical residual net charge", "step table")
total = row_labelled(step, "Worst-case sum", "step table")
c2_row = row_labelled(step, "C2,", "step table")
ripple_row = row_labelled(step, "Peak Vctrl ripple", "step table")
tie_row = row_labelled(step, "Peak TIE", "step table")
theta_row = row_labelled(step, "Peak phase deviation", "step table")
spur_row = row_labelled(step, "Single-sideband spur", "step table")
if None in (systematic, statistical, total, c2_row, ripple_row, tie_row,
            theta_row, spur_row):
    sys.exit(1)

q_systematic = cell_figure(systematic[1], "step table, systematic asymmetry")
q_statistical = cell_figure(statistical[1], "step table, statistical residual")
q_total = cell_figure(total[1], "step table, worst-case sum")
c2 = cell_figure(c2_row[1], "step table, C2")
ripple = cell_figure(ripple_row[1], "step table, peak ripple")
tie = cell_figure(tie_row[1], "step table, peak TIE")
theta = cell_figure(theta_row[1], "step table, peak phase deviation")
derived_spur = cell_figure(spur_row[1], "step table, single-sideband spur")

scale_point = re.search(
    r"recorded\s*(\d+(?:\.\d+)?)\s*ps\s*at\s*(\d+(?:\.\d+)?)\s*mV",
    plain(tie_row[0]),
)
f_out = re.search(r"f_out\s*=\s*(\d+(?:\.\d+)?)\s*MHz", plain(theta_row[0]))
if scale_point is None:
    fail(
        "%s's 'Peak TIE' step does not name its scale point as 'recorded "
        "<x> ps at <y> mV' (reads: %r). That pair is the ingredient this "
        "check scales TIE with; it cannot be assumed"
        % (spec_rel, plain(tie_row[0]))
    )
if f_out is None:
    fail(
        "%s's 'Peak phase deviation' step does not name its output frequency "
        "as 'f_out = <x> MHz' (reads: %r)" % (spec_rel, plain(theta_row[0]))
    )
if None in (q_systematic, q_statistical, q_total, c2, ripple, tie, theta,
            derived_spur) or failures:
    sys.exit(1)

tie_ps_per_mv = float(scale_point.group(1)) / float(scale_point.group(2))
f_out_hz = float(f_out.group(1)) * 1e6

accounting_f_out = re.search(
    r"(\d+(?:\.\d+)?)\s*MHz", plain(accounting[0][0])
)
if accounting_f_out is None or (
    float(accounting_f_out.group(1)) * 1e6 != f_out_hz
):
    fail(
        "%s's charge-accounting table is headed %r but the step table derives "
        "at f_out = %s MHz. The two tables share one chain; a frequency stated "
        "in one and not the other is exactly the drift this check exists for"
        % (spec_rel, plain(accounting[0][0]), f_out.group(1))
    )

summed = q_systematic.value + q_statistical.value
if not q_total.agrees(summed):
    fail(
        "%s's step table states a worst-case sum of %s fC, but its own two "
        "charge rows add to %.5f fC (%s + %s). The table calls this a linear "
        "add; it has to be one"
        % (spec_rel, q_total, summed, q_systematic, q_statistical)
    )


def spur_dbc(q_fc):
    """The full unrounded chain: ΔQ (fC) -> ripple -> TIE -> θ -> dBc."""
    ripple_mv = q_fc / c2.value  # fC / pF == mV
    tie_ps = ripple_mv * tie_ps_per_mv
    radians = 2 * math.pi * f_out_hz * tie_ps * 1e-12
    return 20 * math.log10(radians / 2)


# --------------------------------------------------------------- rule 3 ---
# The step table's own chain, each row from the displayed value above it.
steps_graded = 0
ripple_from_q = q_total.value / c2.value
if ripple.agrees(ripple_from_q):
    steps_graded += 1
else:
    fail(
        "%s's step table states a peak ripple of %s mV, but ΔQ/C2 from its own "
        "rows is %.5f mV (%s fC / %s pF)"
        % (spec_rel, ripple, ripple_from_q, q_total, c2)
    )

tie_from_ripple = ripple.value * tie_ps_per_mv
if tie.agrees(tie_from_ripple):
    steps_graded += 1
else:
    fail(
        "%s's step table states a peak TIE of %s ps, but scaling its own "
        "recorded %s ps at %s mV to %s mV gives %.5f ps"
        % (spec_rel, tie, scale_point.group(1), scale_point.group(2), ripple,
           tie_from_ripple)
    )

theta_from_tie = 2 * math.pi * f_out_hz * tie.value * 1e-12
if theta.agrees(theta_from_tie):
    steps_graded += 1
else:
    fail(
        "%s's step table states a peak phase deviation of %s rad, but %s from "
        "its own %s ps at %s MHz gives %.6e rad"
        % (spec_rel, theta, PHASE_RELATION, tie, f_out.group(1),
           theta_from_tie)
    )

spur_from_theta = 20 * math.log10(theta.value / 2)
if derived_spur.agrees(spur_from_theta):
    steps_graded += 1
else:
    fail(
        "%s's step table states a single-sideband spur of %s dBc, but %s of "
        "its own %s rad gives %.4f dBc"
        % (spec_rel, derived_spur, SPUR_RELATION, theta, spur_from_theta)
    )

# The rounding the displayed chain carries forward must not be large enough to
# hide an error in it.
unrounded = spur_dbc(q_total.value)
if abs(unrounded - spur_from_theta) > 0.1:
    fail(
        "%s's step chain gives %.4f dBc when each row is carried forward as "
        "displayed but %.4f dBc unrounded end to end -- a %.2f dB rounding "
        "spread, wide enough to hide an error in the chain rather than merely "
        "round it"
        % (spec_rel, spur_from_theta, unrounded, abs(unrounded - spur_from_theta))
    )

# --------------------------------------------------------------- rule 4 ---
derived_figures = [derived_spur]
#: Every value this check computes for a graded row, so that rule 6 can accept
#: a proposal figure quoting the derivation's own arithmetic at finer precision
#: than the specification rounds it to.
computed_values = [spur_from_theta, unrounded]
accounting_rows = 0
approximate = 1 if derived_spur.approx else 0
for cells in accounting[1:]:
    if len(cells) < 3:
        fail(
            "%s's charge-accounting table has a row with %d cell(s), fewer "
            "than its own header declares: %s"
            % (spec_rel, len(cells), " | ".join(cells))
        )
        continue
    charge = cell_figure(cells[1], "charge-accounting table, total ΔQ")
    spur = cell_figure(cells[2], "charge-accounting table, derived spur")
    if charge is None or spur is None:
        continue
    derived_figures.append(spur)
    accounting_rows += 1
    if spur.approx:
        approximate += 1
    computed = spur_dbc(charge.value)
    computed_values.append(computed)
    if not spur.agrees(computed):
        fail(
            "%s's charge-accounting row %r states %s dBc, but carrying its own "
            "%s fC through ΔQ/C2 -> TIE -> %s -> %s gives %.4f dBc"
            % (spec_rel, plain(cells[0])[:60], spur, charge, PHASE_RELATION,
               SPUR_RELATION, computed)
        )

if len(derived_figures) < 3:
    fail(
        "%s: parsed %d derived spur figure(s) across the two derivation "
        "tables -- too few to be real; the table format has changed under this "
        "check" % (spec_rel, len(derived_figures))
    )

# --------------------------------------------------------------- rule 5 ---
hi, lo = float(scaling.group(1)), float(scaling.group(2))
stated_constant = Figure(scaling.group(3))
constant = 20 * math.log10(hi / lo)
if not stated_constant.agrees(constant):
    fail(
        "%s's measured-spur table header states its %g -> %g MHz scaling as "
        "%s dB, but 20·log₁₀(%g/%g) is %.5f dB"
        % (spec_rel, lo, hi, stated_constant, hi, lo, constant)
    )

measured_figures = []
scaled_figures = []
for cells in measured[1:]:
    if len(cells) < 3:
        fail(
            "%s's measured-spur table has a row with %d cell(s), fewer than "
            "its own header declares: %s"
            % (spec_rel, len(cells), " | ".join(cells))
        )
        continue
    at_lo = cell_figure(cells[1], "measured-spur table, measured column")
    at_hi = cell_figure(cells[2], "measured-spur table, scaled column")
    if at_lo is None or at_hi is None:
        continue
    measured_figures.append(at_lo)
    scaled_figures.append(at_hi)
    computed_values.append(at_lo.value + constant)
    if not at_hi.agrees(at_lo.value + constant):
        fail(
            "%s's measured-spur row %r scales %s dBc at %g MHz to %s dBc at "
            "%g MHz, but adding its own +%.5f dB gives %.4f dBc"
            % (spec_rel, plain(cells[0]), at_lo, lo, at_hi, hi, constant,
               at_lo.value + constant)
        )

if len(measured_figures) < 3:
    fail(
        "%s: parsed %d measured corner(s) -- too few to be real; the table "
        "format has changed under this check" % (spec_rel, len(measured_figures))
    )

# --------------------------------------------------------------- rule 6 ---
target = re.search(r"(?:≤|<=)\s*(%s)\s*dBc" % NUMBER, section.group(1))
if target is None:
    fail(
        "%s's '## Reference spur' section states no `≤ <x> dBc` line. Rule 6 "
        "allows the proposal to quote the ratified target as well as the "
        "measured and derived figures, and cannot tell which number that is "
        "without it" % spec_rel
    )

if failures:
    sys.exit(1)

allowed = [
    figure.value
    for figure in list(derived_figures) + measured_figures + scaled_figures
    + [Figure(target.group(1))]
] + computed_values

quoted = figures_in(proposal_text)
if len(quoted) < 5:
    fail(
        "%s: found %d dBc figure(s) in %s -- too few to be real; rule 6's "
        "extraction has stopped matching the document"
        % (spec_rel, len(quoted), proposal_rel)
    )

for figure in quoted:
    if any(figure.agrees(candidate) for candidate in allowed):
        continue
    fail(
        "%s quotes %s dBc, which is neither a measured corner, its scaled "
        "value at %g MHz, a derived figure of %s's reference-spur derivation, "
        "nor the ratified line. The proposal is written to be read by someone "
        "outside this repository: a dBc figure in it has to be one the "
        "specification contains"
        % (proposal_rel, figure, hi, spec_rel)
    )

if failures:
    sys.exit(1)

print(
    "OK: %s's reference-spur derivation reproduces itself -- %d step(s) of the "
    "ΔQ/C2 -> TIE -> %s -> %s chain on its own displayed figures, %d "
    "charge-accounting row(s) re-derived unrounded from their own total ΔQ, the "
    "worst-case sum a linear add of its own two terms, "
    "and %d measured corner(s) scaled %g -> %g MHz by their own stated "
    "+%.2f dB; %d dBc figure(s) quoted in %s all trace to one of them or to "
    "the ratified line (%d figure(s) written with `≈`, graded to one unit of "
    "the last written place)"
    % (
        spec_rel,
        steps_graded,
        PHASE_RELATION,
        SPUR_RELATION,
        accounting_rows,
        len(measured_figures),
        lo,
        hi,
        constant,
        len(quoted),
        proposal_rel,
        approximate,
    )
)
PY
