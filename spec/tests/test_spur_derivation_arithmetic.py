#!/usr/bin/env python3
"""Unit tests for ``spec/lib/check-spur-derivation-arithmetic.sh`` (issue #237).

    python3 -m unittest discover -s spec/tests -v

The check grades *arithmetic*: ``spec/pll.md``'s reference-spur derivation has
to reproduce its own figures from its own ingredients, and the Chipalooza
proposal may only quote dBc figures that derivation (or the measured table
beside it) contains.  It is the counterpart of
``sim/lib/check-quoted-value-provenance.sh`` for the one row of the proposal
whose verdict turns on a derived number rather than a measured one -- the row
that check's own section 5.1 listed as ungraded, because a hand derivation has
no CSV to reduce.

Every test builds a throwaway tree whose answer is known and runs the real
script in it, because a check that only ever runs where it passes proves
nothing about what it would have caught.  The fixture carries the real
numbers, so each negative control is a one-figure mutation of a derivation
that does reproduce itself.  No PDK, no ngspice, no simulation input -- the
script reads committed Markdown.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parents[1]
CHECK = SPEC_DIR / "lib" / "check-spur-derivation-arithmetic.sh"

SPEC_DOC = "spec/pll.md"
PROPOSAL = "docs/chipalooza/challenge-5-proposal.md"

#: A miniature of spec/pll.md's `## Reference spur` section: the same three
#: tables, the same ingredients, three of the five measured corners and three
#: of the five charge-accounting rows.  Every figure here is the real one, so
#: the fixture passes for the same reason the repository does.
SPEC_TEXT = """# PLL target specification — v1

## Phase noise

N/A by design. Prose the check must not mistake for a table.

## Reference spur

Target: ≤ −55 dBc at the binding output frequency.

| Corner | Measured spur at 150 MHz | Scaled to 200 MHz (`+20·log₁₀(200/150)` = +2.50 dB) |
|---|---|---|
| `sf` / −40 °C / 2.97 V | **−57.0 dBc** (worst) | **−54.5 dBc** |
| `ff` / −40 °C / 3.63 V | −57.4 dBc | −54.9 dBc |
| `fs` / 125 °C / 3.63 V | −72.7 dBc (best) | −70.2 dBc |

Derivation from the recorded dominant mechanism:

| Step | Value | Source |
|---|---|---|
| Systematic per-event charge asymmetry \\|q_up + q_dn\\|, worst corner | 3.68 fC (`fs`/125 °C/3.63 V) | a record via DR-006 §8 |
| Statistical residual net charge, \\|mean\\| + 3σ | 2.99 fC | a record, term 3 |
| Worst-case sum | 6.67 fC | linear add (conservative) |
| C2, worst-case minimum over corners | 1.814 pF | DR-006 Decision 1 |
| Peak Vctrl ripple, `ΔQ/C2` | 3.68 mV | — |
| Peak TIE, scaled from the recorded 0.669 ps at 1.825 mV | 1.35 ps | DR-006 §8 |
| Peak phase deviation at f_out = 200 MHz | 1.70e-3 rad | `θ = 2π·f_out·TIE` |
| Single-sideband spur, `20·log₁₀(θ/2)` | **−61 dBc** | narrowband-FM |

Re-priced over the corner-combined campaign (DR-018):

| Charge accounting at 200 MHz | Total ΔQ | Derived spur |
|---|---|---|
| **Systematic asymmetry alone**, no statistical term | 3.68 fC | **−66.6 dBc** |
| The table above (systematic + nominal-only statistical) | 6.67 fC | **−61 dBc** |
| …plus term 1 at its **measured** 17.4798 % | 11.19 fC | ≈ −57.0 dBc |
| …plus term 1 at its **budgeted** ±20 % | 11.66 fC | **−56.6 dBc** |

## Loop bandwidth

Text after the section this check grades.
"""

#: A miniature of the proposal's section-5 reference-spur row: the measured
#: range, one scaled corner, and the two derived figures the document leans on.
PROPOSAL_TEXT = """# Chipalooza Challenge #5 — integer-N PLL proposal

## 5. Target specification at the Challenge #5 rails

| Parameter | v1 draft target | Measured / derived (3.3 V) | Verdict | Source |
|---|---|---|---|---|
| Reference spur | ≤ −55 dBc | −57.0…−72.7 dBc measured at 150 MHz; scaled to 200 MHz the worst corner lands at −54.5 dBc; the re-priced stack lands at ≈ −57.0 dBc, against the systematic-only **−66.6 dBc** | **PASS at 150 MHz; UNMET at 200 MHz** | a record |

## 6. Layout status

Text after.
"""


class _Tree:
    """A throwaway repo tree with the real check installed at spec/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "spec" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "spec" / "lib" / CHECK.name)
        self.write(SPEC_DOC, SPEC_TEXT)
        self.write(PROPOSAL, PROPOSAL_TEXT)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / "spec" / "lib" / CHECK.name)],
            capture_output=True,
            text=True,
        )


class _TreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = _Tree(Path(self._tmp.name))
        self.addCleanup(self._tmp.cleanup)

    def mutate_spec(self, old: str, new: str) -> None:
        """Rewrite the spec fixture, asserting the mutation is unambiguous."""
        self.assertEqual(SPEC_TEXT.count(old), 1, msg=f"{old!r} is not unique")
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace(old, new))

    def mutate_proposal(self, old: str, new: str) -> None:
        self.assertEqual(PROPOSAL_TEXT.count(old), 1, msg=f"{old!r} is not unique")
        self.tree.write(PROPOSAL, PROPOSAL_TEXT.replace(old, new))

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


class TestTheRealDerivation(_TreeTest):
    def test_a_derivation_that_reproduces_itself_passes(self):
        result = self.assertPasses()
        self.assertIn("reproduces itself", result.stdout)

    def test_the_ok_line_reports_what_it_graded(self):
        """A check whose OK line says nothing cannot be audited by reading it."""
        result = self.assertPasses()
        self.assertIn("4 step(s)", result.stdout)
        self.assertIn("4 charge-accounting row(s)", result.stdout)
        self.assertIn("3 measured corner(s)", result.stdout)
        self.assertIn("+2.50 dB", result.stdout)


class TestWorstCaseSum(_TreeTest):
    def test_a_sum_that_is_not_the_sum_of_its_terms_fails(self):
        self.mutate_spec("| Worst-case sum | 6.67 fC", "| Worst-case sum | 6.70 fC")
        self.assertFails("linear add")

    def test_a_changed_term_must_move_the_sum(self):
        """Editing one charge row and not the total is the drift this catches."""
        self.mutate_spec(
            "| Statistical residual net charge, \\|mean\\| + 3σ | 2.99 fC",
            "| Statistical residual net charge, \\|mean\\| + 3σ | 3.99 fC",
        )
        self.assertFails("worst-case sum")


class TestStepChain(_TreeTest):
    def test_a_ripple_that_is_not_delta_q_over_c2_fails(self):
        self.mutate_spec("| 3.68 mV |", "| 3.70 mV |")
        self.assertFails("peak ripple")

    def test_a_tie_that_does_not_scale_from_the_recorded_point_fails(self):
        self.mutate_spec("| 1.35 ps |", "| 1.40 ps |")
        self.assertFails("peak TIE")

    def test_a_phase_deviation_that_does_not_follow_from_tie_fails(self):
        self.mutate_spec("| 1.70e-3 rad |", "| 1.80e-3 rad |")
        self.assertFails("peak phase deviation")

    def test_a_spur_that_is_not_the_log_of_its_own_theta_fails(self):
        self.mutate_spec("| **−61 dBc** | narrowband-FM |", "| **−64 dBc** | narrowband-FM |")
        self.assertFails("single-sideband spur")

    def test_a_c2_edit_moves_every_row_below_it(self):
        self.mutate_spec("| 1.814 pF |", "| 2.814 pF |")
        self.assertFails("peak ripple")

    def test_a_chain_rounded_coarsely_enough_to_hide_an_error_fails(self):
        """Rule 3's own guard: displayed-figure chaining must stay honest.

        Every row below is individually right at the precision it is written
        to -- 1 ps *is* 1.3490 ps rounded to the unit, 1.26e-3 rad *is*
        2π·200 MHz·1 ps, and −64 dBc *is* 20·log₁₀(1.26e-3/2).  The chain
        nonetheless arrives 2.6 dB from where the same ΔQ arrives unrounded,
        which is rounding standing in for arithmetic.
        """
        text = SPEC_TEXT.replace("| 1.35 ps |", "| 1 ps |")
        text = text.replace("| 1.70e-3 rad |", "| 1.26e-3 rad |")
        text = text.replace(
            "| **−61 dBc** | narrowband-FM |", "| **−64 dBc** | narrowband-FM |"
        )
        self.tree.write(SPEC_DOC, text)
        self.assertFails("rounding spread")


class TestChargeAccounting(_TreeTest):
    def test_a_row_whose_spur_does_not_follow_from_its_charge_fails(self):
        self.mutate_spec("| 11.19 fC | ≈ −57.0 dBc |", "| 20.00 fC | ≈ −57.0 dBc |")
        self.assertFails("charge-accounting row")

    def test_the_approximation_marker_is_load_bearing(self):
        """`≈ −57.0 dBc` is −56.95 dBc unrounded: −56.9 at that precision.

        The tolerance rule 4 grants is granted only to a figure that says it
        is approximate.  Dropping the marker asserts a precision the
        derivation does not have, and the check says so.
        """
        self.mutate_spec("| ≈ −57.0 dBc |", "| −57.0 dBc |")
        self.assertFails("charge-accounting row", "56.9493")

    def test_the_marker_does_not_excuse_an_arbitrary_figure(self):
        """One unit of the last written place, not a free pass."""
        self.mutate_spec("| ≈ −57.0 dBc |", "| ≈ −57.4 dBc |")
        self.assertFails("charge-accounting row")

    def test_a_budgeted_row_is_graded_too_not_just_the_first(self):
        self.mutate_spec("| 11.66 fC | **−56.6 dBc** |", "| 11.66 fC | **−55.6 dBc** |")
        self.assertFails("charge-accounting row")


class TestScalingToTheBindingFrequency(_TreeTest):
    def test_a_scaled_column_that_does_not_add_the_constant_fails(self):
        self.mutate_spec("| **−54.5 dBc** |", "| **−55.5 dBc** |")
        self.assertFails("scales", "200 MHz")

    def test_a_stated_constant_that_is_not_the_log_ratio_fails(self):
        self.mutate_spec("= +2.50 dB)", "= +2.70 dB)")
        self.assertFails("+2.70 dB", "2.49877")

    def test_changing_the_binding_frequency_regrades_every_row(self):
        """The constant and the column both follow from the header's own pair."""
        self.mutate_spec("(`+20·log₁₀(200/150)` = +2.50 dB)", "(`+20·log₁₀(300/150)` = +2.50 dB)")
        self.assertFails("6.0")


class TestCarryThrough(_TreeTest):
    def test_a_proposal_figure_the_derivation_does_not_contain_fails(self):
        self.mutate_proposal("−54.5 dBc", "−58.2 dBc")
        self.assertFails("neither a measured corner", "−58.2")

    def test_a_derived_figure_drifting_in_the_proposal_alone_fails(self):
        """Re-pricing the spec and not the document, or the reverse."""
        self.mutate_proposal("**−66.6 dBc**", "**−65.6 dBc**")
        self.assertFails("−65.6")

    def test_the_ratified_line_itself_is_allowed(self):
        self.mutate_proposal("≤ −55 dBc", "≤ −55 dBc (the ratified line, −55 dBc)")
        self.assertPasses()

    def test_the_proposal_need_not_quote_every_derived_row(self):
        """One-directional: −56.6 dBc is in the spec and not in the fixture."""
        self.assertPasses()

    def test_a_scaled_figure_is_allowed_without_being_measured(self):
        self.mutate_proposal("−54.5 dBc", "−54.9 dBc")
        self.assertPasses()

    def test_an_extraction_that_stopped_matching_is_not_a_pass(self):
        self.tree.write(PROPOSAL, "# Proposal\n\nNo figures at all.\n")
        self.assertFails("too few to be real")


class TestFormulaFidelity(_TreeTest):
    def test_a_derivation_that_no_longer_states_the_phase_relation_fails(self):
        self.mutate_spec("`θ = 2π·f_out·TIE`", "narrowband FM, as usual")
        self.assertFails("θ = 2π·f_out·TIE", "same commit")

    def test_a_derivation_that_no_longer_states_the_spur_relation_fails(self):
        self.mutate_spec("`20·log₁₀(θ/2)`", "the single-sideband relation")
        self.assertFails("20·log₁₀(θ/2)")

    def test_a_measured_table_without_a_stated_scaling_fails(self):
        self.mutate_spec(
            "| Corner | Measured spur at 150 MHz | Scaled to 200 MHz (`+20·log₁₀(200/150)` = +2.50 dB) |",
            "| Corner | Measured spur at 150 MHz | Scaled to 200 MHz |",
        )
        self.assertFails("scaling")

    def test_the_two_tables_must_derive_at_the_same_frequency(self):
        self.mutate_spec("| Charge accounting at 200 MHz |", "| Charge accounting at 150 MHz |")
        self.assertFails("share one chain")


class TestParserFailuresAreNotPasses(_TreeTest):
    def test_a_missing_spec_fails(self):
        (self.tree.root / SPEC_DOC).unlink()
        self.assertFails("does not exist")

    def test_a_missing_proposal_fails(self):
        (self.tree.root / PROPOSAL).unlink()
        self.assertFails("does not exist")

    def test_a_spec_without_the_section_fails(self):
        self.tree.write(SPEC_DOC, "# Spec\n\n## Loop bandwidth\n\nNo spur section.\n")
        self.assertFails("no '## Reference spur' section")

    def test_a_missing_derivation_table_fails(self):
        self.mutate_spec("| Step | Value | Source |", "| Stage | Value | Source |")
        self.assertFails("derivation step table")

    def test_a_missing_accounting_table_fails(self):
        self.mutate_spec(
            "| Charge accounting at 200 MHz | Total ΔQ | Derived spur |",
            "| Charge accounting at 200 MHz | Total ΔQ | Spur |",
        )
        self.assertFails("charge-accounting table")

    def test_a_renamed_step_row_fails_rather_than_dropping_out(self):
        self.mutate_spec("| Peak TIE, scaled", "| Peak time interval error, scaled")
        self.assertFails("has no row beginning")

    def test_a_tie_row_without_its_scale_point_fails(self):
        self.mutate_spec(
            "| Peak TIE, scaled from the recorded 0.669 ps at 1.825 mV |",
            "| Peak TIE, scaled from the recorded loop-dynamics point |",
        )
        self.assertFails("scale point")

    def test_a_measured_table_with_too_few_corners_fails(self):
        text = SPEC_TEXT
        for row in (
            "| `ff` / −40 °C / 3.63 V | −57.4 dBc | −54.9 dBc |\n",
            "| `fs` / 125 °C / 3.63 V | −72.7 dBc (best) | −70.2 dBc |\n",
        ):
            text = text.replace(row, "")
        self.tree.write(SPEC_DOC, text)
        self.assertFails("too few to be real")


if __name__ == "__main__":
    unittest.main()
