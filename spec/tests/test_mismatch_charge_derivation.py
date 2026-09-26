#!/usr/bin/env python3
"""Unit tests for ``spec/lib/check-mismatch-charge-derivation.sh`` (issue #237).

    python3 -m unittest discover -s spec/tests -v

``check-spur-derivation-arithmetic.sh`` grades the reference-spur derivation's
arithmetic *from* its charge totals (7.93 / 11.19 / 11.66 fC) onward to a dBc
figure, and states plainly what it does not do: grade where those totals
themselves come from, because doing that needs "a reduction language for a
signed `|mean| + 3sigma` statistic, which it does not have". This check gives
it that reduction -- term 1 and term 3 reduced straight from
``sim/mc-cp-mismatch``'s committed per-corner CSVs, the same worst-of-three
Vctrl-point / worst-corner convention ``sim/mc-cp-mismatch/testbench/run.sh``
implements -- and grades the charge-accounting table's totals against it.

Every test builds a throwaway tree whose answer is known and runs the real
script in it. The fixture uses small, hand-verifiable Monte Carlo samples
(not a 300-sample campaign) so every expected figure in this file is checked
by direct arithmetic in a comment, the same discipline the sibling test suite
(``test_spur_derivation_arithmetic.py``) uses for its own fixture. No PDK, no
ngspice, no simulation input -- the script reduces committed CSVs and reads
committed Markdown.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parents[1]
CHECK = SPEC_DIR / "lib" / "check-mismatch-charge-derivation.sh"

SPEC_DOC = "spec/pll.md"
DR018_DOC = (
    "spec/decision-records/"
    "DR-018-cp-term1-mismatch-budget-derived-from-the-spur-line.md"
)

RECORD_ID = "20260101-000000-abc1234"
DC_CSV = "sim/mc-cp-mismatch/corners/%s/mc_cp_dc.csv" % RECORD_ID
PFD_CSV = "sim/mc-cp-mismatch/corners/%s/mc_pfd_cp.csv" % RECORD_ID

#: Term 1 (DC UP/DN mismatch): two corners, four (corner, seed) samples each.
#: Each seed's three Vctrl rows carry a "worst" value at 2.4 V and smaller-
#: magnitude decoys at 0.9 V/1.65 V (half and a third of it), so the
#: worst-of-three selection is unambiguous and the selected series is exactly
#: cornerA = [-10, -2, 6, 14], cornerB = [-1, -1, 1, 1].
#:
#: cornerA folded  = [10, 2, 6, 14]  -> mean 8,  sample sd 5.16398 (n=4)
#:                    |mean|+3sd = 8 + 15.49194 = 23.49194 -> 23.492 (3dp)
#: cornerA signed   = [-10, -2, 6, 14] -> mean 2, sample sd 10.328  (n=4)
#:                    |mean|+3sd = 2 + 30.984 = 32.984
#: cornerB (both series, values +-1) -> |mean|+3sd well under cornerA's, so
#: cornerA is the worst corner for both series -- as the real campaign's own
#: term 1 happens to be (`ff_-40c_3.63v` binds both readings).
DC_CSV_TEXT = """\
# campaign: mc-cp-mismatch (dc) -- test fixture
corner,seed,vctrl_v,iup_a,idn_a,mism_pct
cornerA,1,0.9,0,0,-5
cornerA,1,1.65,0,0,-3.3333
cornerA,1,2.4,0,0,-10
cornerA,2,0.9,0,0,-1
cornerA,2,1.65,0,0,-0.6667
cornerA,2,2.4,0,0,-2
cornerA,3,0.9,0,0,3
cornerA,3,1.65,0,0,2
cornerA,3,2.4,0,0,6
cornerA,4,0.9,0,0,7
cornerA,4,1.65,0,0,4.6667
cornerA,4,2.4,0,0,14
cornerB,1,0.9,0,0,-0.5
cornerB,1,1.65,0,0,-0.3333
cornerB,1,2.4,0,0,-1
cornerB,2,0.9,0,0,-0.5
cornerB,2,1.65,0,0,-0.3333
cornerB,2,2.4,0,0,-1
cornerB,3,0.9,0,0,0.5
cornerB,3,1.65,0,0,0.3333
cornerB,3,2.4,0,0,1
cornerB,4,0.9,0,0,0.5
cornerB,4,1.65,0,0,0.3333
cornerB,4,2.4,0,0,1
"""

#: Term 3 (residual net charge): cornerA's qnet0_c = [-3.5, -2.0, -1.0, 1.5]
#: (x1e-15 C) -> mean -1.25e-15, sample sd 2.10159e-15 (n=4);
#: |mean|+3sd = 1.25e-15 + 6.30477e-15 = 7.55477e-15 C = 7.5548 fC (4dp).
#: cornerB's is well under it, so cornerA is the worst corner here too.
PFD_CSV_TEXT = """\
# campaign: mc-cp-mismatch (pfd_cp) -- test fixture
corner,seed,qnet0_c,qplus_c,qminus_c,kd_wide_a,t_offset_s
cornerA,1,-3.5e-15,0,0,0,0
cornerA,2,-2.0e-15,0,0,0,0
cornerA,3,-1.0e-15,0,0,0,0
cornerA,4,1.5e-15,0,0,0,0
cornerB,1,0.2e-15,0,0,0,0
cornerB,2,0.3e-15,0,0,0,0
cornerB,3,0.1e-15,0,0,0,0
cornerB,4,0.4e-15,0,0,0,0
"""

#: Charge totals, from the reduced figures above and Icp = 6.00 uA,
#: T_ov = 2.000 ns (both the worst/larger end of the ranges the DR-018
#: fixture states):
#:   excluded  = 3.00 (systematic) + 7.5548 (term 3)        = 10.5548 -> 10.55
#:   measured  = 10.5548 + 0.32984 * 6.00e-6 * 2.000e-9 * 1e15 (3.95808 fC)
#:             = 14.51288 -> 14.51
#:   budgeted  = 10.5548 + 0.40    * 6.00e-6 * 2.000e-9 * 1e15 (4.8 fC)
#:             = 15.3548  -> 15.35
SPEC_TEXT = """# PLL target specification — v1

## Phase noise

N/A by design. Prose the check must not mistake for a table.

## Reference spur

Target: ≤ −55 dBc at the binding output frequency.

Term 1 and term 3 are re-derived from the same committed 300 samples
(`sim/mc-cp-mismatch/testbench/run.sh --restat %s`). It previously quoted
23.492 %% (10.55 fC-ish, folded), which was `mean(|x|) + 3*sd(|x|)` on samples
folded to their absolute value first.

| Charge accounting at 200 MHz | Total ΔQ | Derived spur |
|---|---|---|
| Corner-combined statistical residual, term 1 still excluded | 10.55 fC | −60.0 dBc |
| …plus term 1 at its **measured** 32.984 %% (signed `\\|mean\\| + 3σ`) | 14.51 fC | ≈ −58.0 dBc |
| …plus term 1 at its **budgeted** ±40 %% | 15.35 fC | **−57.0 dBc** |

## Loop bandwidth

Text after the section this check grades.
""" % RECORD_ID

#: A miniature of DR-018's own "Input | Value | Source" table inside its
#: `## Context` section -- the four rows this check reads Icp, T_ov, the
#: systematic charge asymmetry and the stated term-3 figure from.
DR018_TEXT = """# DR-018: test fixture

- **Status**: proposed

## Context

Both are measured, not assumed:

| Input | Value | Source |
|---|---|---|
| Reset overlap `T_ov`, min UP/DN pulse at zero phase error, 45 corners | 1.000 – 2.000 ns (worst test corner) | a test source |
| `Icp`, largest trim code (11, four unit legs), 45 corners | 5.00 – 6.00 µA | a test source |
| Systematic per-event charge asymmetry \\|q_up + q_dn\\| | 3.00 fC worst corner | a test source |
| Statistical residual net charge (term 3), corner-combined \\|mean\\|+3σ | 7.5548 fC | a test source |

## Decision

Not exercised by this check.
"""


class _Tree:
    """A throwaway repo tree with the real check installed at spec/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "spec" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "spec" / "lib" / CHECK.name)
        self.write(SPEC_DOC, SPEC_TEXT)
        self.write(DR018_DOC, DR018_TEXT)
        self.write(DC_CSV, DC_CSV_TEXT)
        self.write(PFD_CSV, PFD_CSV_TEXT)

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


class MismatchChargeDerivationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.tree = _Tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_fixture_passes(self):
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK:", result.stdout)
        self.assertIn("10.55 fC", result.stdout)
        self.assertIn("14.51 fC", result.stdout)
        self.assertIn("15.35 fC", result.stdout)

    def test_no_restat_citation_fails(self):
        self.tree.write(
            SPEC_DOC, SPEC_TEXT.replace("run.sh --restat %s" % RECORD_ID, "run.sh")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not cite", result.stderr)

    def test_missing_dc_csv_fails(self):
        (self.root / DC_CSV).unlink()
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    def test_pre_corner_grid_csv_schema_fails(self):
        # Records before #146 have no `corner` column -- a schema this check
        # must refuse rather than silently reduce an empty match against.
        self.tree.write(
            DC_CSV,
            "seed,vctrl_v,iup_a,idn_a,mism_pct\n1,0.9,0,0,-5\n",
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not a corner-combined campaign", result.stderr)

    def test_folded_quote_drift_fails(self):
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace("23.492 %", "99.0 %"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("folded mean(|x|)+3*sd(|x|)", result.stderr)

    def test_dr018_term3_figure_drift_fails(self):
        # DR-018's own stated term-3 figure no longer matches what the
        # committed qnet0_c samples reduce to.
        self.tree.write(DR018_DOC, DR018_TEXT.replace("7.5548 fC", "9.0 fC"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("term 3", result.stderr)

    def test_measured_percentage_drift_fails(self):
        # The charge-accounting table's "measured X %" no longer matches the
        # signed worst-corner reduction (32.984 %).
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace("32.984 %", "50.0 %"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'measured'", result.stderr)

    def test_excluded_total_arithmetic_error_fails(self):
        # 3.00 fC (systematic) + 7.5548 fC (term 3) is 10.55 fC, not 20.00 fC.
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace("10.55 fC", "20.00 fC"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still excluded", result.stderr)

    def test_measured_total_arithmetic_error_fails(self):
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace("14.51 fC", "40.00 fC"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("measured 32.984", result.stderr)

    def test_budgeted_total_arithmetic_error_fails(self):
        self.tree.write(SPEC_DOC, SPEC_TEXT.replace("15.35 fC", "40.00 fC"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("budgeted 40", result.stderr)

    def test_icp_drift_fails(self):
        # Widening Icp's stated range moves every downstream ΔQ total that
        # depends on it (measured/budgeted), which no longer matches the
        # table's own written figures.
        self.tree.write(DR018_DOC, DR018_TEXT.replace("6.00 µA", "9.00 µA"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)

    def test_t_ov_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("2.000 ns", "5.000 ns"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)

    def test_systematic_charge_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("3.00 fC worst", "9.00 fC worst"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)

    def test_missing_still_excluded_row_fails(self):
        mutated = SPEC_TEXT.replace(
            "Corner-combined statistical residual, term 1 still excluded",
            "Corner-combined statistical residual, term 1 accounted for",
        )
        self.tree.write(SPEC_DOC, mutated)
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still excluded", result.stderr)

    def test_missing_accounting_table_fails(self):
        mutated = SPEC_TEXT.split("| Charge accounting")[0] + "\n## Loop bandwidth\n"
        self.tree.write(SPEC_DOC, mutated)
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("charge-accounting table", result.stderr)

    def test_missing_input_table_fails(self):
        mutated = DR018_TEXT.split("| Input |")[0] + "\n## Decision\n"
        self.tree.write(DR018_DOC, mutated)
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Input", result.stderr)


if __name__ == "__main__":
    unittest.main()
