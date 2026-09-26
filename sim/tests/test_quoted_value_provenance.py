#!/usr/bin/env python3
"""Unit tests for ``sim/lib/check-quoted-value-provenance.sh`` (issue #237).

    python3 -m unittest discover -s sim/tests -v

The check grades the *measured value itself*: a figure quoted in the Chipalooza
proposal's section 5 must be what the cited record's committed per-corner CSV
produces under the reduction section 5.1 names, rounded to the precision the
figure is written to.  It exists because eleven checks already grade that
table's counts, citations, grid, verdicts and references, and none of them
would have noticed a number that simply is not in the record.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  No PDK, no ngspice, no simulation
input -- the script reduces committed CSVs and reads committed Markdown.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CHECK = SIM_DIR / "lib" / "check-quoted-value-provenance.sh"

PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"
SPEC = "spec/pll.md"

CAMPAIGN = "vco-tuning-range"
RECORD = "20260731-175947-0a12e6c"
OTHER = "20260804-211600-f599a65"

#: Two corners, three samples each: min over all rows is 5.0, max is 40.0, and
#: the guaranteed floor (highest per-corner minimum) is 12.0 -- a figure no
#: single-stage reduction produces, which is what makes it worth grading.
TUNING_CSV = """\
# a committed per-corner reduction
bundle,temp_c,vdd_v,band,fosc_hz,isupply_a
all-fast,125,2.97,0,5000000,1.0e-4
all-fast,125,2.97,7,20000000,2.0e-4
all-fast,125,2.97,6,17500000,1.5e-4
all-slow,-40,3.63,0,12000000,3.0e-4
all-slow,-40,3.63,7,40000000,4.0e-4
all-slow,-40,3.63,6,33333333,3.5e-4
"""

#: The group-sequence fixture: five (corner, band) CURVES, not five cells.
#: Corner c1 holds bands 0-1 and c2 holds bands 0-2; every curve rises with
#: control voltage, so `non-monotonic` counts 0 -- the figure whose zero a
#: derivation that examined nothing would also report.
#:
#: Its adjacent-band overlaps are chosen so that a flattened implementation
#: gives a different answer: c1's only pair is 14/13 - 1 = 7.69 %, c2's first
#: is 15/14 - 1 = 7.14 % and its second 18/17 - 1 = 5.88 %. The worst pair of
#: the worst corner is therefore 5.88 % -- 5.9 % to one decimal -- and an
#: implementation that took the first pair, or the best one, or pooled the
#: corners would not produce it.
CURVES_CSV = """\
bundle,temp_c,vdd_v,band,vctrl_v,fosc_hz
c1,27,3.30,0,0.90,10000000
c1,27,3.30,0,1.20,12000000
c1,27,3.30,0,1.50,14000000
c1,27,3.30,1,0.90,13000000
c1,27,3.30,1,1.20,16000000
c1,27,3.30,1,1.50,20000000
c2,27,3.30,0,0.90,11000000
c2,27,3.30,0,1.20,13000000
c2,27,3.30,0,1.50,15000000
c2,27,3.30,1,0.90,14000000
c2,27,3.30,1,1.20,16000000
c2,27,3.30,1,1.50,18000000
c2,27,3.30,2,0.90,17000000
c2,27,3.30,2,1.20,19000000
c2,27,3.30,2,1.50,21000000
"""

#: The statistic fixture, for `sig3` and the `worst-magnitude` group verb.
#:
#: Two corners x three Monte Carlo samples x three control voltages. Each
#: sample's worst-MAGNITUDE signed value is designed, so every level of
#: `max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)` produces
#: a DIFFERENT number and a collapsed implementation cannot pass by accident:
#:
#:   per-sample worst magnitudes   k1: -3, 1, 5      k2: 1, 2, 3
#:   signed |mean|+3sigma          k1: 1 + 3*4 = 13  k2: 2 + 3*1 = 5
#:   the figure (worst corner)     13
#:   folded to magnitudes first    k1: 3 + 3*2 = 9   k2: 5        -> 9
#:   corners pooled, still signed  9.4937 -> 9.49
#:   selection by signed max       8.9117 -> 8.91
#:
#: 13 against 9 against 9.49 against 8.91 is the whole point: the campaign's
#: own readings differ the same way, level for level -- 17.4798 signed
#: per-corner (the figure DR-018 Amendment A1 states), 13.2172 folded,
#: 13.7936 pooled-but-still-signed, 10.944 pooled AND folded -- and a check
#: that quietly dropped a level would grade the wrong one of them.
MISMATCH_CSV = """\
# a committed Monte Carlo reduction
corner,seed,vctrl_v,mism_pct
k1,1,0.90,-3
k1,1,1.65,2
k1,1,2.40,1
k1,2,0.90,1
k1,2,1.65,-0.5
k1,2,2.40,0.25
k1,3,0.90,4
k1,3,1.65,5
k1,3,2.40,-2
k2,1,0.90,1
k2,1,1.65,0.5
k2,1,2.40,-0.25
k2,2,0.90,-1
k2,2,1.65,2
k2,2,2.40,1
k2,3,0.90,3
k2,3,1.65,-2
k2,3,2.40,1
"""

#: One value per sample, so `sig3` is exercised without the selection step:
#: grouped by corner the worst is 13, pooled over every row it is 9.49.
TERM3_CSV = """\
corner,seed,qnet_c
k1,1,1
k1,2,2
k1,3,3
k2,1,-3
k2,2,1
k2,3,5
"""

#: The contracted-space fixture: `on-icp-trim-rule` must select only the rows
#: whose (f_ref, trim) pairing the spec table requires -- 47.4 and not 25.4.
MARGINS_CSV = """\
f_ref_hz,trim_units,fc_min_hz,pm_min_deg,pass_pm
1e6,4,25960,47.41,1
1e6,1,10700,25.46,0
2e6,4,45210,60.40,1
2e6,2,30000,55.00,1
"""

#: The rule-7 fixture: one measured column whose worst case is 1.0 V, to be
#: divided by the two ratified lines the fixture spec states.
BUDGET_CSV = """\
cell,span_v
a,0.40
b,1.00
"""

#: Ratified lines, DELIBERATELY NOT THE REPOSITORY'S OWN. Budget 2 is 0.5 V
#: here against the real 0.6, and the control window is 1.0-3.0 V (2.0 V wide)
#: against the real 0.9-2.7 (1.8 V). A check that had the repository's numbers
#: written into it would grade 1.00/0.6 = 1.67 and fail every test below --
#: which is the point: the constants have to be READ out of these documents.
SPEC_TEXT = """\
# spec

## Icp trim-code rule

| f_ref | Required Icp trim (unit legs) | Worst phase margin at that code |
|---|---|---|
| 1 MHz | **4** | 47.4 deg |
| 2 MHz | **4** | 60.4 deg |

## Ratified assumptions

- Vctrl operating window **1.0 – 3.0 V** (DR-003 Decision 5);

## Supply sensitivity

A DC rail excursion must consume ≤ 0.5 V of the Vctrl window.

### Budget 2 -- DC: a full-range rail excursion must consume ≤ 0.5 V of the Vctrl window

## Something else
"""

DR003_TEXT = """\
# DR-003 -- VCO band map

**5. The usable Vctrl window is 1.0–3.0 V**, wider than DR-001 predicted.
"""

#: The Phase margin row's measured cell. Every figure section 5.1's tables
#: grade against this row has to appear here verbatim, including the two
#: rule-7 derived ones, so the tests that override the row build on this
#: string rather than retyping a shorter one and losing them.
PM_MEASURED = (
    "Worst 47.4 deg; 3/4 cells pass; 1.9 deg of margin; travel 2.00x of the "
    "budget, 50 % of the window"
)

SPEC_ROWS = (
    # (name, measured cell, verdict, source cell)
    ("Output band", "Floor 12 MHz; ceiling 20 MHz", "**MET**",
     f"`sim/{CAMPAIGN}/records/{RECORD}.md`"),
    ("Phase margin", PM_MEASURED, "**MET**", "Same record"),
    ("Standby current", "n/a -- no standby state exists", "**N/A**",
     "`spec/pll.md#standby-current`"),
)

#: The section 5 Output band row as the group-sequence tests need it: the two
#: curve figures have to appear verbatim in the row, which is the rule that
#: keeps the two tables one artefact.
CURVE_SPEC_ROW = (
    "Output band",
    "Floor 12 MHz; ceiling 20 MHz; 0 non-monotonic curves of 5; "
    "worst adjacent overlap 5.9 %",
    "**MET**",
    f"`sim/{CAMPAIGN}/records/{RECORD}.md`",
)

MONOTONIC_ENTRY = (
    "Output band", "`0 non-monotonic curves of 5`", RECORD, "kvco_by_point.csv",
    "count(non-monotonic(fosc_hz by vctrl_v) by bundle+temp_c+vdd_v+band)", "1",
)
OVERLAP_ENTRY = (
    "Output band", "`5.9 %`", RECORD, "kvco_by_point.csv",
    "min(adjacent-overlap(fosc_hz by band) by bundle+temp_c+vdd_v)", "100",
)

PROVENANCE_HEADER = (
    "| §5 row | Quoted value | Record(s) | Evidence file | Reduction | Scale |\n"
    "|---|---|---|---|---|---|\n"
)
DERIVED_HEADER = (
    "| §5 row | Quoted value | Record(s) | Evidence file | Derivation | "
    "Constant | Scale |\n|---|---|---|---|---|---|---|\n"
)
EXCLUSION_HEADER = (
    "| §5 row | Why no value here is re-derived from a CSV |\n|---|---|\n"
)
UNGRADED_HEADER = (
    "| §5 row | Figure | Why it is not re-derived |\n|---|---|---|\n"
)

DEFAULT_PROVENANCE = [
    ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
     "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6"),
    ("Output band", "`20 MHz`", RECORD, "vco_tuning.csv",
     "min(max(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6"),
    ("Phase margin", "`47.4`", RECORD, "loop_margins.csv",
     "min(pm_min_deg where on-icp-trim-rule)", "1"),
    ("Phase margin", "`3`", RECORD, "loop_margins.csv",
     "count(rows where pass_pm == 1)", "1"),
]

#: Rule 7: a measurement over a ratified line. 1.00 V of travel is 2.00x the
#: fixture's 0.5 V budget and 50 % of its 2.0 V window -- two different
#: arithmetics over one reduction, so a check that ignored the constant or the
#: scale could not pass both.
DEFAULT_DERIVED = [
    ("Phase margin", "`2.00x`", RECORD, "budget.csv",
     "max(span_v) / budget2-vctrl-consumption-v", "0.5 V", "1"),
    ("Phase margin", "`50 %`", RECORD, "budget.csv",
     "max(span_v) / dr003-vctrl-window-width-v", "2.0 V", "100"),
]

DEFAULT_EXCLUSIONS = [
    ("Standby current", "Waived -- no power-down mode exists in v1, so there "
                        "is no state to measure"),
]

#: A figure inside a GRADED row that nothing re-derives. The check requires
#: this list to exist and to stay attached to a figure section 5 still writes.
DEFAULT_UNGRADED = [
    ("Phase margin", "1.9 deg of margin",
     "The distance to the line is a spec arithmetic, not a column of the "
     "committed evidence file"),
]


def _spec_table(rows) -> str:
    out = ["| Parameter | v1 draft target | Measured / derived (3.3 V) | "
           "Verdict | Source (dated) |", "|---|---|---|---|---|"]
    for name, measured, verdict, source in rows:
        out.append(f"| {name} | a target | {measured} | {verdict} | {source} |")
    return "\n".join(out) + "\n"


def _provenance_table(entries) -> str:
    body = "".join(
        "| %s | %s | `%s` | `%s` | `%s` | `%s` |\n" % entry for entry in entries
    )
    return PROVENANCE_HEADER + body


def _derived_table(entries) -> str:
    body = "".join(
        "| %s | %s | `%s` | `%s` | `%s` | `%s` | `%s` |\n" % entry
        for entry in entries
    )
    return DERIVED_HEADER + body


def _exclusion_table(entries) -> str:
    body = "".join("| %s | %s |\n" % entry for entry in entries)
    return EXCLUSION_HEADER + body


def _ungraded_table(entries) -> str:
    body = "".join("| %s | %s | %s |\n" % entry for entry in entries)
    return UNGRADED_HEADER + body


def proposal(
    spec_rows=SPEC_ROWS,
    provenance=None,
    derived=None,
    exclusions=None,
    ungraded=None,
    include_5_1=True,
    include_derived=True,
) -> str:
    provenance = DEFAULT_PROVENANCE if provenance is None else provenance
    derived = DEFAULT_DERIVED if derived is None else derived
    exclusions = DEFAULT_EXCLUSIONS if exclusions is None else exclusions
    ungraded = DEFAULT_UNGRADED if ungraded is None else ungraded
    text = "# proposal\n\n## 5. Target specification\n\n"
    text += _spec_table(spec_rows) + "\n"
    if include_5_1:
        text += "### 5.1 Value provenance\n\n"
        text += _provenance_table(provenance) + "\n"
        if include_derived:
            text += _derived_table(derived) + "\n"
        text += _exclusion_table(exclusions) + "\n"
        text += _ungraded_table(ungraded) + "\n"
    text += "## 6. Next section\n"
    return text


class _Tree:
    """A throwaway repo tree with the real check installed at sim/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "sim" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "sim" / "lib" / CHECK.name)

        rec_dir = root / "sim" / CAMPAIGN / "records"
        rec_dir.mkdir(parents=True)
        for rid in (RECORD, OTHER):
            (rec_dir / f"{rid}.md").write_text("# record\n")

        corners = root / "sim" / CAMPAIGN / "corners" / RECORD
        corners.mkdir(parents=True)
        (corners / "vco_tuning.csv").write_text(TUNING_CSV)
        (corners / "loop_margins.csv").write_text(MARGINS_CSV)
        (corners / "kvco_by_point.csv").write_text(CURVES_CSV)
        (corners / "mc_cp_dc.csv").write_text(MISMATCH_CSV)
        (corners / "mc_term3.csv").write_text(TERM3_CSV)
        (corners / "budget.csv").write_text(BUDGET_CSV)

        (root / "spec").mkdir()
        (root / SPEC).write_text(SPEC_TEXT)
        dr_dir = root / "spec" / "decision-records"
        dr_dir.mkdir()
        (dr_dir / "DR-003-vco-band-map.md").write_text(DR003_TEXT)

        (root / "docs" / "chipalooza").mkdir(parents=True)
        self.write(proposal())

    def write(self, text: str) -> None:
        (self.root / PROPOSAL).write_text(text)

    def write_curves(self, text: str) -> None:
        (self.root / "sim" / CAMPAIGN / "corners" / RECORD
         / "kvco_by_point.csv").write_text(text)

    def write_evidence(self, name: str, text: str) -> None:
        (self.root / "sim" / CAMPAIGN / "corners" / RECORD
         / name).write_text(text)

    def write_other_evidence(self, name: str, text: str) -> None:
        """Evidence under the SECOND record, for a multi-record entry.

        Section 5.1 has entries that reduce six records of one file at once, so
        "the columns this entry may name" is a property of all of them together
        rather than of whichever one happens to be read first.
        """
        corners = self.root / "sim" / CAMPAIGN / "corners" / OTHER
        corners.mkdir(parents=True, exist_ok=True)
        (corners / name).write_text(text)

    def write_spec(self, text: str) -> None:
        (self.root / SPEC).write_text(text)

    def write_dr003(self, text: str) -> None:
        (self.root / "spec" / "decision-records"
         / "DR-003-vco-band-map.md").write_text(text)

    def write_record(self, rid: str, text: str) -> None:
        (self.root / "sim" / CAMPAIGN / "records" / f"{rid}.md").write_text(text)

    def write_logs(self, rid: str, names) -> None:
        """The per-corner logs a record's own table is checked against.

        Their CONTENTS are never read -- the check reads their names, to prove
        a markdown table has one row per simulation that ran.
        """
        corners = self.root / "sim" / CAMPAIGN / "corners" / rid
        corners.mkdir(parents=True, exist_ok=True)
        for name in corners.glob("*.log"):
            name.unlink()
        for name in names:
            (corners / f"{name}.log").write_text("ngspice log\n")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "sim" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def assertPasses(self) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        return result

    def assertFails(self, *needles: str) -> subprocess.CompletedProcess:
        result = self.tree.run()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)
        return result


class TestCleanTree(_TreeTest):
    def test_a_consistent_document_passes(self):
        result = self.assertPasses()
        self.assertIn("4 quoted values re-derived", result.stdout)
        self.assertIn("all 3 section 5 rows accounted for", result.stdout)

    def test_the_grouped_reduction_is_not_a_flat_one(self):
        """`max(min(x) by corner)` must be the guaranteed floor, not min(x).

        The fixture's flat minimum is 5.0 MHz and its guaranteed floor is
        12.0 MHz. A check that silently dropped the grouping would accept
        5.000 here; this asserts it does not.
        """
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 5.000 MHz; ceiling 20 MHz", "**MET**",
                   f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`5.000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("gives 12", "does not round to it")


class TestValueRule(_TreeTest):
    def test_a_drifted_value_fails(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12.999 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.999 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("does not round to it at the 3 decimal place(s)")

    def test_a_value_correct_to_the_precision_written_passes(self):
        """12.0 MHz written to no decimals is 12; to four it is 12.0000.

        Both spellings must pass, and a figure the derived value does NOT
        round to at the precision written must not -- the neighbouring
        drift test covers that direction.
        """
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12.0000 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.0000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertPasses()

    def test_a_wrong_count_fails_exactly(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[3] = ("Phase margin", "`4`", RECORD, "loop_margins.csv",
                      "count(rows where pass_pm == 1)", "1")
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin",
                   PM_MEASURED.replace("3/4 cells pass", "4/4 cells pass"),
                   "**MET**", "Same record")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("counts 3")

    def test_the_scale_is_applied(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12000000 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12000000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("does not round to it")


class TestSignFlippingScale(_TreeTest):
    """A magnitude quoted from a uniformly-signed column, graded at scale -1.

    The Supply sensitivity -- DC row quotes `0.60-0.72 ns` of static-phase
    movement from a column holding -0.6048 and -0.7216. Scale -1 grades it,
    and swaps which aggregate gives which end. What makes that safe is that
    the check compares the SIGNED product: a positive value in the selection,
    or a larger negative one, moves the result off the quoted figure rather
    than being read as a magnitude. Each of those is asserted here.
    """

    DECAY_CSV = "corner,d_phi_ns\nc1,-0.6048\nc2,-0.7216\n"

    def _grade(self, quoted, reduction, scale):
        self.tree.write_evidence("phase_decay.csv", self.DECAY_CSV)
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin",
                   PM_MEASURED + "; 0.60-0.72 ns of movement",
                   "**MET**", "Same record")
        entries = list(DEFAULT_PROVENANCE) + [
            ("Phase margin", "`%s`" % quoted, RECORD, "phase_decay.csv",
             reduction, scale),
        ]
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))

    def test_both_ends_pass_at_scale_minus_one(self):
        self._grade("0.60", "max(d_phi_ns)", "-1")
        self.assertPasses()
        self._grade("0.72 ns", "min(d_phi_ns)", "-1")
        self.assertPasses()

    def test_without_the_sign_flip_the_magnitude_fails(self):
        self._grade("0.60", "max(d_phi_ns)", "1")
        self.assertFails("gives -0.6048")

    def test_the_flip_swaps_which_aggregate_gives_which_end(self):
        self._grade("0.72 ns", "max(d_phi_ns)", "-1")
        self.assertFails("gives 0.6048")

    def test_a_mixed_sign_column_is_not_read_as_a_magnitude(self):
        self._grade("0.60", "max(d_phi_ns)", "-1")
        self.tree.write_evidence("phase_decay.csv",
                                 self.DECAY_CSV + "c3,0.6048\n")
        self.assertFails("gives -0.6048")


class TestDriftBetweenTheTwoTables(_TreeTest):
    def test_a_figure_not_present_in_the_section_5_row_fails(self):
        """The rule that makes the two tables one artefact rather than two.

        `12.0000 MHz` is the correct value at a precision section 5 does not
        write it to, so rule 4 is satisfied and only rule 3 fires: the failure
        really is "these two tables disagree", not a wrong number.
        """
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12.0000 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("does not appear in that section 5 row", "drifted")

    def test_an_entry_naming_no_section_5_row_fails(self):
        entries = DEFAULT_PROVENANCE + [
            ("Nonexistent row", "`12 MHz`", RECORD, "vco_tuning.csv",
             "min(fosc_hz)", "1e-6")
        ]
        self.tree.write(proposal(provenance=entries))
        self.assertFails("names a section 5 row that does not exist")


class TestCitationRule(_TreeTest):
    def test_reducing_a_record_the_row_does_not_cite_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", OTHER, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("which that section 5 row does not cite")

    def test_same_record_inherits_the_preceding_rows_citation(self):
        """The Phase margin row's Source cell says only "Same record"."""
        self.assertPasses()

    def test_a_record_not_on_the_tree_fails(self):
        missing = "20990101-000000-fffffff"
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12 MHz; ceiling 20 MHz",
                   "**MET**", f"`sim/{CAMPAIGN}/records/{missing}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", missing, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        entries[1] = ("Output band", "`20 MHz`", missing, "vco_tuning.csv",
                      "min(max(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("is not on the tree")

    def test_an_uncommitted_evidence_file_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "not_committed.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("no committed evidence file at")


class TestCoverageRule(_TreeTest):
    def test_a_row_in_neither_table_fails(self):
        self.tree.write(proposal(exclusions=[]))
        self.assertFails("appears in neither of section 5.1's tables")

    def test_a_row_in_both_tables_fails(self):
        self.tree.write(
            proposal(
                exclusions=DEFAULT_EXCLUSIONS
                + [("Output band", "a reason long enough to be a real one")]
            )
        )
        self.assertFails("is both graded and excluded")

    def test_an_exclusion_without_a_reason_fails(self):
        self.tree.write(proposal(exclusions=[("Standby current", "n/a")]))
        self.assertFails("gives no real reason")

    def test_an_exclusion_naming_no_section_5_row_fails(self):
        self.tree.write(
            proposal(
                exclusions=DEFAULT_EXCLUSIONS
                + [("Ghost row", "a reason long enough to be a real one")]
            )
        )
        self.assertFails("names a section 5 row that does not exist")


class TestGroupSequenceDerivations(_TreeTest):
    """The two figures that are properties of a CURVE, not of cells.

    `count(non-monotonic(...))` grades a **zero**, which is the most dangerous
    kind of figure to grade: a derivation that examined nothing reports exactly
    what a clean grid reports. Most of these tests exist to show that this one
    does not pass vacuously.
    """

    def write(self, entries=None, spec_rows=None, csv_text=None):
        if csv_text is not None:
            self.tree.write_curves(csv_text)
        rows = list(SPEC_ROWS)
        rows[0] = CURVE_SPEC_ROW if spec_rows is None else spec_rows
        provenance = DEFAULT_PROVENANCE + (
            [MONOTONIC_ENTRY, OVERLAP_ENTRY] if entries is None else entries
        )
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=provenance))

    @staticmethod
    def remap_bands(csv_text, bundle, mapping):
        """CURVES_CSV with one bundle's band codes relabelled.

        One pass over the rows rather than chained `str.replace` calls, which
        would re-match rows an earlier substitution had just renamed.
        """
        out = [csv_text.strip().split("\n")[0]]
        for line in csv_text.strip().split("\n")[1:]:
            fields = line.split(",")
            if fields[0] == bundle:
                fields[3] = mapping.get(fields[3], fields[3])
            out.append(",".join(fields))
        return "\n".join(out) + "\n"

    def test_both_curve_derivations_pass_and_report_their_group_count(self):
        self.write()
        result = self.assertPasses()
        self.assertIn("6 quoted values re-derived", result.stdout)
        # Seven groups: five curves for the monotonicity derivation and two
        # corners for the overlap one. Three pairs: c1's single 0-1 and c2's
        # 0-1 and 1-2 -- the count that tells a worst overlap taken over every
        # adjacent band apart from one taken over a gapped subset of them.
        self.assertIn("2 of them group-sequence derivations over 7 groups, "
                      "3 adjacent-axis pair(s) examined", result.stdout)

    def test_a_dip_in_one_curve_is_counted(self):
        """The fault the figure exists to exclude: f falls back mid-sweep."""
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,0,1.50,14000000", "c1,27,3.30,0,1.50,11000000"))
        self.assertFails("counts 1")

    def test_a_falling_curve_is_still_monotonic(self):
        """"Monotonic" is the document's word, and it has two directions.

        This pins the definition rather than assuming it: a curve that falls
        throughout is monotonic, and the check must not silently grade the
        stronger "strictly rising" claim the document does not make.
        """
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,1,0.90,13000000\nc1,27,3.30,1,1.20,16000000\n"
            "c1,27,3.30,1,1.50,20000000",
            "c1,27,3.30,1,0.90,20000000\nc1,27,3.30,1,1.20,16000000\n"
            "c1,27,3.30,1,1.50,13000000"))
        # c1's overlap pair is now 14/13 - 1 with band 1's minimum at 13 MHz
        # still, so 5.9 % is unchanged and only monotonicity is under test.
        self.assertPasses()

    def test_a_tie_inside_a_curve_is_still_monotonic(self):
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,0,1.20,12000000", "c1,27,3.30,0,1.20,10000000"))
        self.assertPasses()

    def test_a_misspelled_grouping_column_fails(self):
        """Without this, every curve pools into one group and 0 is a fluke."""
        entries = [
            ("Output band", "`0 non-monotonic curves of 5`", RECORD,
             "kvco_by_point.csv",
             "count(non-monotonic(fosc_hz by vctrl_v) by bundel+band)", "1"),
            OVERLAP_ENTRY,
        ]
        self.write(entries=entries)
        self.assertFails("names column `bundel`",
                         "kvco_by_point.csv does not have",
                         "Its columns are: bundle, temp_c, vdd_v, band, "
                         "vctrl_v, fosc_hz")

    def test_an_evidence_file_with_no_data_rows_cannot_report_zero(self):
        self.write(csv_text="bundle,temp_c,vdd_v,band,vctrl_v,fosc_hz\n")
        self.assertFails("hold no data rows")

    def test_a_one_point_curve_is_not_a_sequence_test(self):
        self.write(csv_text=CURVES_CSV + "c3,27,3.30,0,0.90,9000000\n")
        self.assertFails("a sequence test over fewer than two points is not a "
                         "test")

    def test_a_repeated_ordering_value_is_ambiguous(self):
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,0,1.20,12000000", "c1,27,3.30,0,0.90,12000000"))
        self.assertFails("repeats a value of the ordering column `vctrl_v`")

    def test_a_non_numeric_cell_is_an_error_not_a_skip(self):
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,0,1.20,12000000", "c1,27,3.30,0,1.20,n/a"))
        self.assertFails("is not a number",
                         "error rather than a skip")

    def test_the_overlap_is_the_worst_pair_of_the_worst_corner(self):
        """7.1 % is c2's FIRST pair; 7.7 % is c1's only one. Neither passes.

        Both are figures a flattened implementation would produce, so quoting
        either against this fixture must fail.
        """
        for wrong in ("7.1 %", "7.7 %"):
            with self.subTest(wrong=wrong):
                entries = [
                    MONOTONIC_ENTRY,
                    ("Output band", "`%s`" % wrong, RECORD,
                     "kvco_by_point.csv",
                     "min(adjacent-overlap(fosc_hz by band) "
                     "by bundle+temp_c+vdd_v)", "100"),
                ]
                self.write(
                    entries=entries,
                    spec_rows=(
                        "Output band",
                        "Floor 12 MHz; ceiling 20 MHz; 0 non-monotonic curves "
                        "of 5; worst adjacent overlap %s" % wrong,
                        "**MET**",
                        f"`sim/{CAMPAIGN}/records/{RECORD}.md`",
                    ),
                )
                self.assertFails("does not round to it")

    def test_a_corner_with_no_consecutive_bands_fails(self):
        self.write(csv_text=CURVES_CSV.replace(
            "c1,27,3.30,1,", "c1,27,3.30,3,"))
        self.assertFails("no pair of consecutive `band` values")

    def test_a_partially_gapped_corner_fails(self):
        """The case a `continue` used to pass quietly (issue #566).

        A corner holding bands `0, 1, 3` has one pair where it looks like it
        has two, and the figure the derivation reports -- a worst overlap --
        says nothing about how many intervals it was the worst of. So a gap is
        an error, not a shorter walk: the wholly gapped corner above already
        hard-fails, and it would be strange for a corner that is *half* missing
        to be the one that passes.

        Gaps at the end of the run, at the start, and in the middle are each
        exercised, because a walk that pairs `k` with `k+1` fails differently
        at each position.

        The first case is the negative control: c2's bands become `1, 2, 5`,
        whose surviving `1`-`2` pair is the 5.88 % one the document quotes, so
        the whole tree still GRADES CLEAN and the gap is the only thing wrong
        with it. That fixture passed under the `continue` this replaced.
        """
        cases = (
            # bands 1, 2, 5 -- the quoted 5.9 % survives the gap untouched
            ({"0": "5"}, None, "2 then 5", "1 pair(s) of the 2 that 3 values"),
            # bands 0, 1, 3 -- gap after the last pair
            ({"2": "3"}, None, "1 then 3", "1 pair(s) of the 2 that 3 values"),
            # bands 1, 3, 4 -- gap before the only pair
            ({"0": "1", "1": "3", "2": "4"}, None,
             "1 then 3", "1 pair(s) of the 2 that 3 values"),
            # bands 0, 1, 3, 4 -- a pair on either side of the gap
            ({"2": "3"},
             "c2,27,3.30,4,0.90,22000000\nc2,27,3.30,4,1.20,24000000\n"
             "c2,27,3.30,4,1.50,26000000\n",
             "1 then 3", "2 pair(s) of the 3 that 4 values"),
        )
        for mapping, extra, gap, counted in cases:
            with self.subTest(mapping=mapping, extra=extra):
                csv_text = self.remap_bands(CURVES_CSV, "c2", mapping)
                self.write(csv_text=csv_text + (extra or ""))
                self.assertFails(
                    "group c2/27/3.30 has a gap in its `band` run (%s)" % gap,
                    "pairs `band` with `band`+1",
                    "would examine %s look like they hold" % counted,
                )

    def test_a_whole_run_of_bands_is_not_read_as_a_gap(self):
        """The other direction: relabelling a whole run must still pass.

        Without this, "fail on a gap" could be satisfied by a check that fails
        on any band code it does not recognise. c2's bands become 5, 6, 7 --
        still unit-spaced, so still two pairs, and 5.9 % is unchanged because
        the frequencies did not move.
        """
        self.write(csv_text=self.remap_bands(
            CURVES_CSV, "c2", {"0": "5", "1": "6", "2": "7"}))
        result = self.assertPasses()
        self.assertIn("3 adjacent-axis pair(s) examined", result.stdout)

    def test_count_over_a_group_scalar_is_rejected(self):
        entries = [
            MONOTONIC_ENTRY,
            ("Output band", "`5.9 %`", RECORD, "kvco_by_point.csv",
             "count(adjacent-overlap(fosc_hz by band) by bundle+temp_c+vdd_v)",
             "100"),
        ]
        self.write(entries=entries)
        self.assertFails("is a group scalar, not a predicate")

    def test_an_aggregate_over_a_group_predicate_is_rejected(self):
        entries = [
            ("Output band", "`0 non-monotonic curves of 5`", RECORD,
             "kvco_by_point.csv",
             "min(non-monotonic(fosc_hz by vctrl_v) by bundle+band)", "1"),
            OVERLAP_ENTRY,
        ]
        self.write(entries=entries)
        self.assertFails("is a group predicate")

    def test_a_where_clause_on_a_sequence_derivation_is_rejected(self):
        """Rejected explicitly rather than silently misparsed."""
        entries = [
            ("Output band", "`0 non-monotonic curves of 5`", RECORD,
             "kvco_by_point.csv",
             "count(non-monotonic(fosc_hz by vctrl_v) by bundle+band "
             "where band == 0)", "1"),
            OVERLAP_ENTRY,
        ]
        self.write(entries=entries)
        self.assertFails("takes no where-clause")


class TestSignedTailStatistic(_TreeTest):
    """`sig3` and `worst-magnitude`: the statistic DR-018's term 1 is.

    Every other reduction in this grammar is an extremum or a count -- a figure
    a reader can find by eye in the CSV. This one is not: it is a selection
    (worst point of the control window), then a tail (`|mean| + 3*sigma` over
    that corner's samples), then a worst case (over corners). Collapsing any
    level gives a smaller, plausible-looking number, which is exactly how the
    campaign's own reported figure was 13.2172 % for months when the honest
    reading of its column header was 17.4798 % (DR-018 Amendment A1, #487). So
    most of these tests assert that a COLLAPSED reading fails.
    """

    SPUR_ROW = (
        "Reference spur",
        "term 1 at its measured 13 %; term 3 residual 13 C",
        "**MET**",
        f"`sim/{CAMPAIGN}/records/{RECORD}.md`",
    )
    THREE_LEVEL = (
        "max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)"
    )

    def write(self, value="`13 %`", reduction=None, measured=None,
              entries=None):
        rows = list(SPEC_ROWS) + [
            (self.SPUR_ROW[0],
             self.SPUR_ROW[1] if measured is None else measured,
             self.SPUR_ROW[2], self.SPUR_ROW[3])
        ]
        if entries is None:
            entries = [(
                "Reference spur", value, RECORD, "mc_cp_dc.csv",
                self.THREE_LEVEL if reduction is None else reduction, "1",
            )]
        self.tree.write(proposal(
            spec_rows=tuple(rows),
            provenance=DEFAULT_PROVENANCE + entries,
            exclusions=DEFAULT_EXCLUSIONS,
        ))

    def test_the_three_level_statistic_passes_and_counts_its_groups(self):
        self.write()
        result = self.assertPasses()
        self.assertIn("5 quoted values re-derived", result.stdout)
        # One derivation (this entry), six innermost groups (2 corners x 3
        # samples) -- not two derivations, one per corner partition.
        self.assertIn("1 of them group-sequence derivations over 6 groups",
                      result.stdout)

    def test_folding_the_samples_to_magnitudes_gives_a_different_number(self):
        """9 is the folded reading. It is the mistake DR-018 A1 corrected."""
        self.write(value="`9 %`", measured="term 1 at its measured 9 %")
        self.assertFails("gives 13", "does not round to it")

    def test_pooling_the_corners_gives_a_different_number(self):
        """9.49 pools the six samples into one tail instead of two."""
        self.write(value="`9.49 %`", measured="term 1 at its measured 9.49 %")
        self.assertFails("gives 13", "does not round to it")

    def test_selecting_the_window_point_by_value_gives_a_different_number(self):
        """8.91 is what selecting each sample's largest SIGNED value gives.

        `worst-magnitude` compares magnitudes and then keeps the sign, which is
        the "worst point in the window" convention sim/cp-compliance uses; a
        plain max would silently drop every negative worst case.
        """
        self.write(value="`8.91 %`", measured="term 1 at its measured 8.91 %")
        self.assertFails("gives 13", "does not round to it")

    def test_a_magnitude_tie_with_opposite_signs_is_ambiguous(self):
        self.write_tie = MISMATCH_CSV.replace(
            "k1,1,1.65,2", "k1,1,1.65,3")
        self.tree.write_evidence("mc_cp_dc.csv", self.write_tie)
        self.write()
        self.assertFails("tying at magnitude", "sign is ambiguous")

    def test_a_repeated_control_voltage_inside_a_window_is_ambiguous(self):
        self.tree.write_evidence("mc_cp_dc.csv", MISMATCH_CSV.replace(
            "k1,1,1.65,2", "k1,1,0.90,2"))
        self.write()
        self.assertFails("repeats a value of the ordering column `vctrl_v`")

    def test_a_misspelled_outer_grouping_column_fails(self):
        """Without this the two corners pool and the tail is the wrong one."""
        self.write(reduction=(
            "max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by cornor)"
        ))
        self.assertFails("groups by column `cornor`",
                         "mc_cp_dc.csv does not have",
                         "Its columns are: corner, seed, vctrl_v, mism_pct")

    def test_a_group_predicate_does_not_compose_three_deep(self):
        self.write(reduction=(
            "max(sig3(non-monotonic(mism_pct by vctrl_v) by seed) by corner)"
        ))
        self.assertFails("is a group predicate",
                         "does not compose into a three-level reduction")

    def test_count_over_the_worst_magnitude_verb_is_rejected(self):
        self.write(reduction=(
            "count(worst-magnitude(mism_pct by vctrl_v) by seed)"
        ))
        self.assertFails("is a group scalar, not a predicate")

    def test_the_grouped_statistic_is_the_worst_corner(self):
        """Two-level `max(sig3(COL) by KEY)`, no selection step."""
        self.write(entries=[(
            "Reference spur", "`13 C`", RECORD, "mc_term3.csv",
            "max(sig3(qnet_c) by corner)", "1",
        )])
        self.assertPasses()

    def test_the_flat_statistic_is_the_pooled_one(self):
        """`sig3(COL)` with no grouping pools every row, and says so: 9.49."""
        self.write(
            measured="term 1 at its measured 13 %; term 3 residual 9.49 C",
            entries=[(
                "Reference spur", "`9.49 C`", RECORD, "mc_term3.csv",
                "sig3(qnet_c)", "1",
            )],
        )
        self.assertPasses()

    def test_a_one_sample_group_is_not_a_tail(self):
        """A single sample has no standard deviation, so no 3 sigma either."""
        self.tree.write_evidence("mc_term3.csv", TERM3_CSV + "k3,1,7\n")
        self.write(entries=[(
            "Reference spur", "`13 C`", RECORD, "mc_term3.csv",
            "max(sig3(qnet_c) by corner)", "1",
        )])
        self.assertFails("sig3 needs at least two samples")


class TestUngradedFigureDisclosure(_TreeTest):
    """Rule 6: the per-figure disclosure is an artefact, not prose.

    It was prose until 2026-09-26, and it had already gone wrong -- it named
    four ungraded figures and silently missed a fifth.
    """

    def test_a_missing_disclosure_table_fails(self):
        text = proposal()
        text = text[: text.index(UNGRADED_HEADER)] + "\n## 6. Next section\n"
        self.tree.write(text)
        self.assertFails("no non-empty section 5.1 ungraded-figure table")

    def test_an_empty_disclosure_table_fails(self):
        self.tree.write(proposal(ungraded=[]))
        self.assertFails("no non-empty section 5.1 ungraded-figure table")

    def test_a_figure_no_longer_in_its_row_fails(self):
        """The rule with teeth: section 5 edited, the disclosure not."""
        self.tree.write(proposal(ungraded=[
            ("Phase margin", "2.4 deg of margin", DEFAULT_UNGRADED[0][2]),
        ]))
        self.assertFails("does not appear in the section 5 row it is declared "
                         "against", "gone stale")

    def test_a_figure_that_is_also_graded_fails(self):
        self.tree.write(proposal(ungraded=[
            ("Phase margin", "47.4", DEFAULT_UNGRADED[0][2]),
        ]))
        self.assertFails("cannot be both re-derived and declared "
                         "un-re-derived")

    def test_a_disclosure_against_a_fully_excluded_row_fails(self):
        self.tree.write(proposal(ungraded=[
            ("Standby current", "n/a -- no standby state exists",
             DEFAULT_UNGRADED[0][2]),
        ]))
        self.assertFails("already accounted for by the exclusion table")

    def test_a_disclosure_naming_no_section_5_row_fails(self):
        self.tree.write(proposal(ungraded=[
            ("Ghost row", "1.9 deg of margin", DEFAULT_UNGRADED[0][2]),
        ]))
        self.assertFails("names a section 5 row that does not exist")

    def test_a_disclosure_without_a_reason_fails(self):
        self.tree.write(proposal(ungraded=[
            ("Phase margin", "1.9 deg of margin", "no CSV"),
        ]))
        self.assertFails("gives no real reason")


class TestIcpTrimRulePredicate(_TreeTest):
    def test_the_rule_is_read_from_the_spec_not_the_check(self):
        """Move the ratified pairing and the graded figure must move with it.

        The spec fixture requires trim 4 at 1 MHz, which selects pm 47.41.
        Requiring trim 1 instead selects 25.46 -- so the same document, the
        same CSV and the same reduction now fail. This is the property that
        makes the predicate a reading of spec/pll.md rather than a constant.
        """
        self.assertPasses()
        self.tree.write_spec(SPEC_TEXT.replace("| 1 MHz | **4** |",
                                               "| 1 MHz | **1** |"))
        self.assertFails("gives 25.46")

    def test_a_missing_rule_table_fails_rather_than_matching_everything(self):
        self.tree.write_spec("# spec\n\nNo rule table here.\n")
        self.assertFails("no Icp trim-code rule table could be read")


class TestSelfDefence(_TreeTest):
    """A parser that gave up must not be reported as a clean document."""

    def test_a_missing_proposal_fails(self):
        (Path(self.tree.root) / PROPOSAL).unlink()
        self.assertFails("does not exist")

    def test_a_missing_5_1_section_fails(self):
        self.tree.write(proposal(include_5_1=False))
        self.assertFails("no non-empty section 5.1 value-provenance table")

    def test_a_missing_exclusion_table_fails(self):
        text = proposal()
        text = text[: text.index(EXCLUSION_HEADER)] + "\n## 6. Next section\n"
        self.tree.write(text)
        self.assertFails("no section 5.1 exclusion table")

    def test_an_unparsable_reduction_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "median(fosc_hz)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("cannot parse reduction")

    def test_an_unknown_column_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "min(not_a_column)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("names column `not_a_column`",
                         "vco_tuning.csv does not have",
                         "Its columns are: bundle, temp_c, vdd_v, band, "
                         "fosc_hz, isupply_a")

    def test_a_where_clause_selecting_nothing_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", RECORD, "vco_tuning.csv",
                      "min(fosc_hz where bundle == nonesuch)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("selected no")

    def test_a_count_with_a_scale_fails(self):
        entries = list(DEFAULT_PROVENANCE)
        entries[3] = ("Phase margin", "`3`", RECORD, "loop_margins.csv",
                      "count(rows where pass_pm == 1)", "1e-6")
        self.tree.write(proposal(provenance=entries))
        self.assertFails("count reduction must carry scale 1")


class TestColumnExistence(_TreeTest):
    """Every column a reduction names must exist in its evidence (issue #579).

    This is the one validation rule whose absence was INVISIBLE rather than
    loud, because the natural behaviour of a filter over a column that does not
    exist is to match no rows -- and a count of no rows is `0`, which is a
    legitimate and load-bearing value here: `0 of 45 corners` and `0 ratio
    errors of 235 chain points` are both graded figures on the real tree. A
    mistyped `Status` in `count(rows where Status == PASS)` returned 0, equalled
    the quoted 0, and printed OK: a green check asserting a number it had never
    computed.

    Six of the nine cases below printed `OK` before this check existed, and each
    of those says so in its docstring -- because "it fails now" is only half the
    claim, and the half that matters is what it used to do instead. The other
    three already failed, but for the wrong reason ("selected no rows", which
    reads as a too-narrow filter rather than a column that is not there, and the
    two have opposite fixes).
    """

    def _grade(self, quoted, reduction, evidence="vco_tuning.csv", scale="1"):
        """One extra graded entry on the Output band row, and the row to match.

        The figure is appended to the section 5 row verbatim so that rule 3 is
        satisfied and the failure under test is the only one reported.
        """
        rows = list(SPEC_ROWS)
        rows[0] = (
            "Output band",
            "Floor 12 MHz; ceiling 20 MHz; %s" % quoted,
            "**MET**",
            f"`sim/{CAMPAIGN}/records/{RECORD}.md`",
        )
        entries = list(DEFAULT_PROVENANCE) + [
            ("Output band", "`%s`" % quoted, RECORD, evidence, reduction, scale),
        ]
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))

    def test_a_zero_count_over_a_mistyped_where_column_fails(self):
        """THE dangerous case: a filtered count whose honest answer is zero.

        Spelled right, `where bundle == nonesuch` selects nothing and 0 is the
        true count -- asserted first, so this test cannot pass merely because
        the entry is broken some other way. Mistyped, the filter selects nothing
        FOR A DIFFERENT REASON, and before this check the two were
        indistinguishable: both printed OK against the quoted 0.
        """
        self._grade("0 corners out of band",
                    "count(rows where bundle == nonesuch)")
        self.assertPasses()
        self._grade("0 corners out of band",
                    "count(rows where bundel == nonesuch)")
        self.assertFails(
            "where-clause names column `bundel`",
            "sim/%s/corners/%s/vco_tuning.csv does not have"
            % (CAMPAIGN, RECORD),
            "Its columns are: bundle, temp_c, vdd_v, band, fosc_hz, isupply_a",
            "never a passing zero",
        )

    def test_a_mistyped_where_column_under_not_equals_fails(self):
        """`!=` fails the other way: a total silently becomes a zero.

        `count(rows where band != 99)` is the whole table (6 rows). Mistype the
        column and the same reduction returned 0 -- so a mistyped column could
        turn a count of everything into a count of nothing, which is a much
        easier number to quote by accident.
        """
        self._grade("6 corners measured", "count(rows where band != 99)")
        self.assertPasses()
        self._grade("6 corners measured", "count(rows where bnad != 99)")
        self.assertFails("where-clause names column `bnad`",
                         "vco_tuning.csv does not have")

    def test_a_mistyped_group_key_fails_rather_than_pooling(self):
        """Before this check, a mistyped `by` key pooled every row silently.

        `max(min(fosc_hz) by bundel)` puts all six rows in one group keyed on
        the empty string, so the guaranteed floor collapses into the flat
        minimum: it returned 5 MHz, and a document quoting 5 MHz would have been
        graded green against a reduction that had stopped grouping at all.
        """
        self._grade("5 MHz floor", "max(min(fosc_hz) by bundel)", scale="1e-6")
        self.assertFails("groups by column `bundel`",
                         "vco_tuning.csv does not have",
                         "Its columns are: bundle, temp_c, vdd_v, band, "
                         "fosc_hz, isupply_a")

    def test_a_mistyped_distinct_key_fails_rather_than_counting_one(self):
        """`count(distinct bundel)` counted 1 -- one empty-string key.

        Any document quoting `1` for a distinct count would have passed against
        evidence the reduction never actually read.
        """
        self._grade("1 distinct bundle", "count(distinct bundel)")
        self.assertFails("counts distinct values of column `bundel`",
                         "vco_tuning.csv does not have")

    def test_a_mistyped_aggregated_column_inside_a_group_fails(self):
        """The inner aggregate's column, which only the flat form checked.

        `max(min(fosc_hzz) by ...)` used to fail with "selected no rows" -- a
        failure, but one that reads as "the where-clause was too narrow" rather
        than "that column does not exist", and the two have opposite fixes.
        """
        self._grade("12 MHz guaranteed",
                    "max(min(fosc_hzz) by bundle+temp_c+vdd_v)", scale="1e-6")
        self.assertFails("names column `fosc_hzz`",
                         "vco_tuning.csv does not have")

    def test_a_mistyped_sequence_axis_column_fails(self):
        """The ordering column of a group-sequence derivation.

        This position was already covered, and is asserted here so that routing
        it through the shared check did not lose it -- what it gains is the
        evidence source in the message.
        """
        self._grade(
            "0 non-monotonic curves of 5",
            "count(non-monotonic(fosc_hz by vctrl_vv) "
            "by bundle+temp_c+vdd_v+band)",
            evidence="kvco_by_point.csv",
        )
        self.assertFails("names column `vctrl_vv`",
                         "kvco_by_point.csv does not have")

    def test_the_icp_trim_rule_predicate_needs_its_implicit_columns(self):
        """The two column names no reduction spells out.

        `on-icp-trim-rule` reads `f_ref_hz` and `trim_units` itself, so a
        reduction carrying it over evidence that has neither matched no rows at
        all -- and `count(rows where on-icp-trim-rule)` therefore returned a
        clean, passing 0 over a CSV with nothing to do with the trim rule.
        """
        self._grade("0 contracted corners",
                    "count(rows where on-icp-trim-rule)")
        self.assertFails(
            "`on-icp-trim-rule` predicate reads column `f_ref_hz`",
            "vco_tuning.csv does not have",
        )

    def test_the_icp_trim_rule_predicate_needs_both_of_them(self):
        """Half the pairing is not the pairing: `trim_units` is required too."""
        self.tree.write_evidence(
            "half_rule.csv", "f_ref_hz,pm_min_deg\n1e6,47.41\n2e6,60.40\n")
        self._grade("0 contracted corners",
                    "count(rows where on-icp-trim-rule)",
                    evidence="half_rule.csv")
        self.assertFails(
            "`on-icp-trim-rule` predicate reads column `trim_units`",
            "half_rule.csv does not have",
            "Its columns are: f_ref_hz, pm_min_deg",
        )

    def test_a_column_only_some_of_the_records_have_is_refused(self):
        """A multi-record entry may only name columns ALL of its records have.

        Section 5.1's closed-loop period-jitter figures reduce six records of
        one filename at once. If one of them renamed the column, a reduction
        naming it would read a SUBSET of the evidence -- the rows that still
        have it -- and quietly grade a worst case over part of the grid. So the
        usable columns are the ones every row carries, and the failure lists
        exactly those.
        """
        self.tree.write_other_evidence(
            "vco_tuning.csv", TUNING_CSV.replace("fosc_hz", "f_osc_hz"))
        rows = list(SPEC_ROWS)
        rows[0] = (
            "Output band",
            "Floor 12 MHz; ceiling 20 MHz",
            "**MET**",
            f"`sim/{CAMPAIGN}/records/{RECORD}.md`, "
            f"`sim/{CAMPAIGN}/records/{OTHER}.md`",
        )
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 MHz`", f"{RECORD}`, `{OTHER}",
                      "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails(
            "names column `fosc_hz`",
            "sim/%s/corners/%s/vco_tuning.csv; "
            "sim/%s/corners/%s/vco_tuning.csv does not have"
            % (CAMPAIGN, RECORD, CAMPAIGN, OTHER),
            "Its columns are: bundle, temp_c, vdd_v, band, isupply_a",
        )


class TestInRecordTableEvidence(_TreeTest):
    """Rule 1's second evidence form: the table committed INSIDE a record.

    Three rows of section 5 were ungraded until 2026-09-26 for the reason "no
    reduced CSV was committed, so the count cannot be re-derived" -- and all
    three records had committed their full per-point table all along, in their
    own Markdown. "No CSV" is not "no evidence". These tests cover the form
    that closed that, and above all the correspondence rule that stops a
    markdown table from being trusted the way a CSV can be: a CSV cannot be
    abbreviated without being wrong, a markdown table can.
    """

    #: Four points: two at 200 MHz with N in {4, 5}, one 10 MHz point at N = 9,
    #: and a second corner at N = 5. So `count(distinct n_target)` is 3 over the
    #: whole table and 2 once the `~= f200` filter selects the 200 MHz points --
    #: the filter is load-bearing, which is what makes it worth testing.
    POINT_TABLE = """\
  | corner-id | n_target | ratio_pass | DN guard |
  |---|---|---|---|
  | `ss_125c_2.97v_f200n04` | 4 | 1 | PASS |
  | `ss_125c_2.97v_f200n05` | 5 | 1 | PASS |
  | `ss_125c_2.97v_f010n09` | 9 | 1 | ERROR |
  | `ff_-40c_3.63v_f200n05` | 5 | 1 | PASS |
"""

    #: The same four runs as a record that does NOT write a point-id column:
    #: the corner is spread over three columns, as sim/output-range and
    #: sim/lock-time write it. Only the row-count rule is available here.
    CORNER_TABLE = """\
  | Corner | Temp | VDD | Status |
  |---|---|---|---|
  | `ss` | 125C | 2.97V | FAIL |
  | `ss` | 125C | 2.97V | FAIL |
  | `ss` | 125C | 2.97V | FAIL |
  | `ff` | -40C | 3.63V | FAIL |
"""

    POINT = "20260901-010203-abcdef0"
    LOGS = (
        "ss_125c_2.97v_f200n04",
        "ss_125c_2.97v_f200n05",
        "ss_125c_2.97v_f010n09",
        "ff_-40c_3.63v_f200n05",
    )

    MEASURED = (
        "4 chain points, 0 ratio errors, 2 distinct N at 200 MHz, "
        "3 guard passes"
    )

    def setUp(self) -> None:
        super().setUp()
        self.tree.write_record(self.POINT, "# record\n\n" + self.POINT_TABLE)
        self.tree.write_logs(self.POINT, self.LOGS)
        self.write()

    def entries(self, **overrides):
        entries = {
            "points": ("`4 chain points`", "count(rows)"),
            "errors": ("`0 ratio errors`", "count(rows where ratio_pass != 1)"),
            "ratios": ("`2 distinct N`",
                       "count(distinct n_target where corner-id ~= f200)"),
            "guard": ("`3 guard passes`", "count(rows where DN guard == PASS)"),
        }
        entries.update(overrides)
        evidence = overrides.pop("evidence", f"{self.POINT}.md § corner-id")
        return list(DEFAULT_PROVENANCE) + [
            ("Multiplication ratio", quoted, self.POINT, evidence,
             reduction, "1")
            for quoted, reduction in entries.values()
        ]

    def write(self, provenance=None, measured=None) -> None:
        row = ("Multiplication ratio", measured or self.MEASURED, "**MET**",
               f"`sim/{CAMPAIGN}/records/{self.POINT}.md`")
        spec_rows = SPEC_ROWS[:2] + (row,) + SPEC_ROWS[2:]
        self.tree.write(proposal(
            spec_rows=spec_rows,
            provenance=self.entries() if provenance is None else provenance,
        ))

    def test_a_table_committed_inside_a_record_is_gradeable(self):
        result = self.assertPasses()
        self.assertIn("8 quoted values re-derived", result.stdout)
        self.assertIn("4 checked row-for-row against the committed logs by "
                      "point id", result.stdout)

    def test_the_substring_filter_is_load_bearing(self):
        """Drop ` where corner-id ~= f200` and the answer changes.

        The fixture's 10 MHz point runs an N the 200 MHz sweep does not, so an
        implementation that ignored the filter would count 3 where the document
        says 2. That is exactly the accident the real campaign's figure would
        have been graded by: its own 10 MHz points reuse N in {4, 64}, so the
        unfiltered count is right today and wrong the first time one does not.
        """
        self.write(provenance=self.entries(
            ratios=("`2 distinct N`", "count(distinct n_target)")))
        self.assertFails("counts 3")

    def test_a_column_name_with_a_space_is_usable(self):
        """`DN guard` is how a record heads that column, so it has to work."""
        self.assertPasses()
        self.write(provenance=self.entries(
            guard=("`3 guard passes`", "count(rows where DN guard != PASS)")))
        self.assertFails("counts 1")

    def test_a_truncated_table_fails(self):
        """The rule with teeth: an elided table must not read as an answer."""
        trimmed = "\n".join(self.POINT_TABLE.strip().split("\n")[:-1]) + "\n"
        self.tree.write_record(self.POINT, "# record\n\n" + trimmed)
        self.assertFails("3 row(s) against the 4 per-corner log(s)",
                         "must not read as a smaller, passing answer")

    def test_a_duplicated_row_at_the_right_count_fails(self):
        """The count rule alone would pass this; the point-id rule must not."""
        doubled = self.POINT_TABLE.replace(
            "| `ss_125c_2.97v_f010n09` | 9 |",
            "| `ss_125c_2.97v_f200n04` | 9 |",
        )
        self.tree.write_record(self.POINT, "# record\n\n" + doubled)
        self.assertFails("not by identity", "duplicated row id")

    def test_a_table_with_no_point_id_column_uses_the_count_rule_and_says_so(self):
        """The weaker rule is applied where it is all the evidence supports.

        A record that heads its first column `Corner` cannot be checked row for
        row, so it is checked by count -- and the OK line has to report which
        rule each table got, because a weaker check applied silently is how a
        reader ends up trusting the stronger one.
        """
        self.tree.write_record(self.POINT, "# record\n\n" + self.CORNER_TABLE)
        self.write(
            provenance=list(DEFAULT_PROVENANCE) + [(
                "Multiplication ratio", "`4 chain points`", self.POINT,
                f"{self.POINT}.md § Corner", "count(rows)", "1",
            )],
            measured="4 chain points",
        )
        result = self.assertPasses()
        self.assertIn("1 in-record table(s) read, 0 checked row-for-row "
                      "against the committed logs by point id and 1 by row "
                      "count alone", result.stdout)

    def test_an_entry_may_not_read_another_records_markdown(self):
        self.write(provenance=list(DEFAULT_PROVENANCE) + [(
            "Multiplication ratio", "`4 chain points`", self.POINT,
            f"{OTHER}.md § corner-id", "count(rows)", "1",
        )])
        self.assertFails("may only read the record it declares")

    def test_a_table_name_that_matches_nothing_fails(self):
        self.write(provenance=list(DEFAULT_PROVENANCE) + [(
            "Multiplication ratio", "`4 chain points`", self.POINT,
            f"{self.POINT}.md § not_a_column", "count(rows)", "1",
        )])
        self.assertFails("has no table whose first column is `not_a_column`")

    def test_an_ambiguous_table_name_fails(self):
        self.tree.write_record(
            self.POINT, "# record\n\n" + self.POINT_TABLE + "\n"
            + self.POINT_TABLE)
        self.assertFails("has 2 tables whose first column is `corner-id`",
                         "name one table")

    def test_a_record_committing_no_logs_fails(self):
        self.tree.write_logs(self.POINT, ())
        self.assertFails("commits no per-corner logs",
                         "table nothing corroborates is prose")


class TestDerivedAgainstARatifiedLine(_TreeTest):
    """Rule 7: a reduction divided by a constant read out of the documents.

    The figures this grades -- `1.41x` and `47 %` on the real tree -- are a
    measurement over a *spec line*, and sat in the ungraded list until
    2026-09-26 for the reason "arithmetic on the line, not a column of the
    committed evidence". Both ingredients are written down, so the arithmetic
    is checkable; what these tests assert is that it is checked against the
    DOCUMENTS and not against anything written into the script.
    """

    def _derived(self, **kwargs):
        self.tree.write(proposal(**kwargs))

    def test_a_derived_figure_passes_and_is_reported(self):
        result = self.assertPasses()
        self.assertIn("2 further figure(s) derived against 2 ratified", result.stdout)
        self.assertIn("budget2-vctrl-consumption-v = 0.5", result.stdout)
        self.assertIn("dr003-vctrl-window-width-v = 2", result.stdout)

    def test_a_drifted_derived_figure_fails(self):
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin", PM_MEASURED.replace("2.00x", "1.90x"),
                   "**MET**", "Same record")
        entries = list(DEFAULT_DERIVED)
        entries[0] = ("Phase margin", "`1.90x`", RECORD, "budget.csv",
                      "max(span_v) / budget2-vctrl-consumption-v", "0.5 V", "1")
        self._derived(spec_rows=tuple(rows), derived=entries)
        self.assertFails("over the ratified 0.5 that is 2", "does not round to it")

    def test_the_constant_is_read_from_the_documents_not_the_check(self):
        """Re-ratify the line and the figure must fail in the same commit.

        The fixture's budget moves 0.5 -> 1.0 V in both of its statements, so
        the documents stay self-consistent and only the ARITHMETIC changes:
        1.00 / 1.0 is 1.00x, not the 2.00x section 5 states.
        """
        self.tree.write_spec(SPEC_TEXT.replace("0.5 V", "1.0 V"))
        self.assertFails("the Constant column states 0.5 V",
                         "budget2-vctrl-consumption-v` reads 1")

    def test_a_line_stated_once_is_not_corroborated(self):
        spec = SPEC_TEXT.replace(
            "A DC rail excursion must consume ≤ 0.5 V of the Vctrl window.",
            "A DC rail excursion is budgeted.",
        )
        self.tree.write_spec(spec)
        self.assertFails("found 1 statement(s) of this ratified line",
                         "at least 2 independent ones are required")

    def test_two_statements_that_disagree_fail(self):
        spec = SPEC_TEXT.replace(
            "### Budget 2 -- DC: a full-range rail excursion must consume "
            "≤ 0.5 V",
            "### Budget 2 -- DC: a full-range rail excursion must consume "
            "≤ 0.7 V",
        )
        self.tree.write_spec(spec)
        self.assertFails("stated inconsistently", "is a spec question")

    def test_the_decision_record_must_agree_with_the_spec(self):
        """The window is ratified in two documents; a split between them fails.

        The real proposal's own section 5 row cites DR-003 Decision 5 for this
        window, so a divergence between the decision record and the spec is a
        divergence the figure rests on -- not a detail.
        """
        self.tree.write_dr003(DR003_TEXT.replace("3.0 V", "2.5 V"))
        self.assertFails("dr003-vctrl-window-width-v", "stated inconsistently")

    def test_a_missing_decision_record_is_not_silently_a_pass(self):
        self.tree.write_dr003("# DR-003\n\nNothing about the window here.\n")
        self.assertFails("found 1 statement(s) of this ratified line")

    def test_the_tables_own_statement_of_the_constant_is_graded(self):
        entries = list(DEFAULT_DERIVED)
        entries[0] = ("Phase margin", "`2.00x`", RECORD, "budget.csv",
                      "max(span_v) / budget2-vctrl-consumption-v", "0.6 V", "1")
        self._derived(derived=entries)
        self.assertFails("the Constant column states 0.6 V",
                         "The document and the ratified line have drifted apart")

    def test_an_unknown_constant_fails(self):
        entries = list(DEFAULT_DERIVED)
        entries[0] = ("Phase margin", "`2.00x`", RECORD, "budget.csv",
                      "max(span_v) / some-number-i-made-up", "0.5 V", "1")
        self._derived(derived=entries)
        self.assertFails("is not a ratified constant this check knows how to read")

    def test_an_unparsable_derivation_fails(self):
        entries = list(DEFAULT_DERIVED)
        entries[0] = ("Phase margin", "`2.00x`", RECORD, "budget.csv",
                      "max(span_v)", "0.5 V", "1")
        self._derived(derived=entries)
        self.assertFails("cannot read the derivation")

    def test_a_count_numerator_is_refused(self):
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin", PM_MEASURED + "; 4 over the line",
                   "**MET**", "Same record")
        entries = list(DEFAULT_DERIVED) + [
            ("Phase margin", "`4`", RECORD, "budget.csv",
             "count(rows) / budget2-vctrl-consumption-v", "0.5 V", "1"),
        ]
        self._derived(spec_rows=tuple(rows), derived=entries)
        self.assertFails("the numerator is a count", "is not a ratio")

    def test_the_scale_is_applied_to_the_ratio(self):
        """The two entries share a numerator and a row; only scale differs."""
        entries = list(DEFAULT_DERIVED)
        entries[1] = ("Phase margin", "`50 %`", RECORD, "budget.csv",
                      "max(span_v) / dr003-vctrl-window-width-v", "2.0 V", "1")
        self._derived(derived=entries)
        self.assertFails("does not round to it")

    def test_a_derived_figure_not_in_its_section_5_row_fails(self):
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin", "Worst 47.4 deg; 1.9 deg of margin; 50 %",
                   "**MET**", "Same record")
        self._derived(spec_rows=tuple(rows))
        self.assertFails("the derived figure does not appear in that section 5 row")

    def test_reducing_a_record_the_row_does_not_cite_fails(self):
        entries = list(DEFAULT_DERIVED)
        entries[0] = ("Phase margin", "`2.00x`", OTHER, "budget.csv",
                      "max(span_v) / budget2-vctrl-consumption-v", "0.5 V", "1")
        self._derived(derived=entries)
        self.assertFails("which that section 5 row does not cite")

    def test_a_row_graded_only_here_counts_as_graded(self):
        """Rule 5 is satisfied by a derived figure, not only by a reduction."""
        rows = list(SPEC_ROWS) + [
            ("Loop bandwidth", "travel 2.00x of the budget", "**MET**",
             f"`sim/{CAMPAIGN}/records/{RECORD}.md`"),
        ]
        entries = list(DEFAULT_DERIVED) + [
            ("Loop bandwidth", "`2.00x`", RECORD, "budget.csv",
             "max(span_v) / budget2-vctrl-consumption-v", "0.5 V", "1"),
        ]
        self._derived(spec_rows=tuple(rows), derived=entries)
        result = self.assertPasses()
        self.assertIn("all 4 section 5 rows accounted for", result.stdout)

    def test_a_row_graded_here_and_excluded_fails(self):
        exclusions = list(DEFAULT_EXCLUSIONS) + [
            ("Phase margin", "There is nothing here to re-derive at all"),
        ]
        self._derived(exclusions=exclusions)
        self.assertFails("is both graded and excluded")

    def test_a_derived_figure_also_declared_ungraded_fails(self):
        ungraded = list(DEFAULT_UNGRADED) + [
            ("Phase margin", "2.00x",
             "A ratio to a spec line is arithmetic on the line, not a column"),
        ]
        self._derived(ungraded=ungraded)
        self.assertFails("cannot be both re-derived and declared un-re-derived")

    def test_a_missing_derived_table_fails(self):
        self._derived(include_derived=False)
        self.assertFails("no non-empty section 5.1 derived-figure table",
                         "ungraded and silent")

    def test_an_empty_derived_table_fails(self):
        self._derived(derived=[])
        self.assertFails("no non-empty section 5.1 derived-figure table")


class TestARangeIsNotAFigure(_TreeTest):
    """Both grading tables refuse a two-ended range.

    `parse_quoted` reads the number at the front of the string, so a quoted
    `0.1-0.5 dB` would be graded as `0.1` and the other end would never be
    looked at. "Grading half of a two-sided bound and calling it the bound" is
    the named defect section 5.1's ungraded list exists to make visible, and
    before this guard the check would have committed it silently.
    """

    def test_a_range_in_the_graded_table_is_refused(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12-20 MHz", "**MET**",
                   f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12-20 MHz`", RECORD, "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("two-ended range", "calling it the bound")

    def test_an_en_dash_range_is_refused(self):
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin", PM_MEASURED + "; 0.1–0.5 dB over",
                   "**MET**", "Same record")
        entries = list(DEFAULT_DERIVED) + [
            ("Phase margin", "`0.1–0.5 dB`", RECORD, "budget.csv",
             "max(span_v) / budget2-vctrl-consumption-v", "0.5 V", "1"),
        ]
        self.tree.write(proposal(spec_rows=tuple(rows), derived=entries))
        self.assertFails("two-ended range")

    def test_an_ellipsis_range_is_refused(self):
        rows = list(SPEC_ROWS)
        rows[0] = ("Output band", "Floor 12 … 20 MHz", "**MET**",
                   f"`sim/{CAMPAIGN}/records/{RECORD}.md`")
        entries = list(DEFAULT_PROVENANCE)
        entries[0] = ("Output band", "`12 … 20 MHz`", RECORD,
                      "vco_tuning.csv",
                      "max(min(fosc_hz) by bundle+temp_c+vdd_v)", "1e-6")
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertFails("two-ended range")

    def test_a_hyphenated_unit_is_still_a_figure(self):
        """`45-point PVT grid` and `2.255e-4` are figures, not ranges.

        The guard requires a DIGIT after the separator, which is what keeps it
        from swallowing the figures the tables already grade. Asserted here
        because a guard that over-fires would silently stop grading them.
        """
        self.tree.write_evidence(
            "hyphen.csv", "cell,v\na,0.0002255\nb,0.0001\nc,0.0002\n")
        rows = list(SPEC_ROWS)
        rows[1] = ("Phase margin",
                   PM_MEASURED + "; 2.255e-4 residual on a 3-point PVT grid",
                   "**MET**", "Same record")
        entries = list(DEFAULT_PROVENANCE) + [
            ("Phase margin", "`2.255e-4`", RECORD, "hyphen.csv", "max(v)", "1"),
            ("Phase margin", "`3-point PVT grid`", RECORD, "hyphen.csv",
             "count(distinct cell)", "1"),
        ]
        self.tree.write(proposal(spec_rows=tuple(rows), provenance=entries))
        self.assertPasses()


class TestTheRealTree(unittest.TestCase):
    """The check must pass on this repository, and grade a real amount."""

    def test_the_committed_proposal_is_consistent(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("quoted values re-derived", result.stdout)

    def test_it_grades_more_than_a_token_number_of_values(self):
        """A check wired up but grading two values would pass vacuously."""
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        count = int(result.stdout.split("OK: ")[1].split(" ")[0])
        self.assertGreaterEqual(count, 30, msg=result.stdout)

    def test_the_curve_derivations_examined_the_real_grid(self):
        """The zero-valued figure's anti-vacuity assertion on the real tree.

        `0 non-monotonic curves of 504` is reported by a derivation that
        examined 504 curves and by a derivation that examined none. Only the
        group count tells them apart, so it is asserted here (as a floor, not
        as a second copy of a number the document already states and CI
        already grades).
        """
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        groups = int(
            result.stdout.split("group-sequence derivations over ")[1].split(" ")[0]
        )
        self.assertGreaterEqual(groups, 500, msg=result.stdout)

    def test_the_overlap_derivation_examined_every_adjacent_band_pair(self):
        """The same anti-vacuity assertion one level down (issue #566).

        The group count says 63 corners were examined; it does not say how many
        of each corner's seven adjacent band pairs were. A gap in a corner's
        band codes is now an error rather than a skipped pair, so the floor
        asserted here is the whole grid's worth of pairs -- again a floor, not a
        second copy of a number §5.1 already states.
        """
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        match = re.search(r"(\d+) adjacent-axis pair\(s\) examined",
                          result.stdout)
        self.assertIsNotNone(match, msg=result.stdout)
        self.assertGreaterEqual(int(match.group(1)), 400, msg=result.stdout)

    def test_it_derives_the_ratio_figures_against_the_ratified_lines(self):
        """Rule 7 on the real tree, asserted from the other side.

        The count and the resolved constants are asserted as floors and as
        names, not as a second copy of the document's own numbers: what must
        not happen is the derived table quietly emptying out and the check
        still reporting OK.
        """
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        match = re.search(r"(\d+) further figure\(s\) derived against (\d+) "
                          r"ratified constant", result.stdout)
        self.assertIsNotNone(match, msg=result.stdout)
        self.assertGreaterEqual(int(match.group(1)), 2, msg=result.stdout)
        self.assertGreaterEqual(int(match.group(2)), 2, msg=result.stdout)
        self.assertIn("budget2-vctrl-consumption-v", result.stdout)
        self.assertIn("dr003-vctrl-window-width-v", result.stdout)

    def test_it_reports_the_ungraded_figures_it_disclosed(self):
        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        match = re.search(r"and (\d+) ungraded figure", result.stdout)
        self.assertIsNotNone(match, msg=result.stdout)
        disclosed = int(match.group(1))
        self.assertGreaterEqual(disclosed, 1, msg=result.stdout)

    def test_it_sees_every_row_of_the_real_section_5_table(self):
        """The other half of the check's own MIN_SPEC_ROWS guard.

        That guard is set at 3, deliberately far from the real count, so it
        reports a parser that gave up rather than duplicating a number that
        would go stale. The real count is asserted here instead: section 5 is
        re-parsed independently, and the check must report exactly as many
        rows as this test finds. A silently-truncating parser fails here.
        """
        text = (REPO_ROOT / PROPOSAL).read_text(encoding="utf-8")
        rows, in_table = 0, False
        for line in text.split("\n"):
            if line.startswith("| Parameter |") and "Verdict" in line:
                in_table = True
                continue
            if in_table:
                if not line.startswith("|"):
                    break
                if set(line) <= set("|-: "):
                    continue
                rows += 1
        self.assertGreaterEqual(rows, 20, msg="section 5 table not found")

        result = subprocess.run(
            ["bash", str(CHECK)], capture_output=True, text=True, cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("all %d section 5 rows accounted for" % rows, result.stdout)


if __name__ == "__main__":
    unittest.main()
