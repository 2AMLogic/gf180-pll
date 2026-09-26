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
DR006_DOC = "spec/decision-records/DR-006-loop-filter-sizing-and-trim-rule.md"

RECORD_ID = "20260101-000000-abc1234"
DC_CSV = "sim/mc-cp-mismatch/corners/%s/mc_cp_dc.csv" % RECORD_ID
PFD_CSV = "sim/mc-cp-mismatch/corners/%s/mc_pfd_cp.csv" % RECORD_ID

#: The three campaigns the remaining ingredients are reduced from (issue
#: #573). Two live in `cp-compliance` under different record ids -- the DC
#: bench for Icp and the switching bench for the charge asymmetry -- and
#: DR-018 cites the second one in its elided `…-<time>-<sha>` form, which the
#: check has to resolve against the committed corner directories.
ICP_RECORD = "20260103-000000-aaa1111"
QSYS_RECORD = "20260104-000000-bbb2222"
TOV_RECORD = "20260102-000000-def5678"
CP_DC_CSV = "sim/cp-compliance/corners/%s/cp_dc.csv" % ICP_RECORD
CP_TRIM_CSV = "sim/cp-compliance/corners/%s/cp_trim_range.csv" % ICP_RECORD
CP_SWITCH_CSV = "sim/cp-compliance/corners/%s/cp_switch.csv" % QSYS_RECORD
TOV_CSV = "sim/pfd-deadzone/corners/%s/raw_measures.csv" % TOV_RECORD

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

#: Icp (rule 5): three corners, two trim codes. At the code DR-018's fixture
#: prices (b1 b0 = 1 1, four unit legs) the campaign's own convention -- mean
#: of the two polarities at the window's nominal point, which is the `*_mid_a`
#: column pair -- gives
#:   cornerA/27/3.30  (5.10 + 4.90)/2 = 5.00 uA   <- best corner
#:   cornerB/125/3.30 (5.60 + 5.40)/2 = 5.50 uA
#:   cornerC/125/2.97 (6.10 + 5.90)/2 = 6.00 uA   <- worst corner, the Icp
#:                                                   the charge totals price
#: The code-00 rows are decoys an unfiltered reduction would drag in (they
#: would make the range 1.50 - 6.00 uA), and the `_lo_a`/`_hi_a` columns are
#: decoys a reduction reading the wrong window point would pick up.
CP_DC_CSV_TEXT = """\
# per (PVT corner, trim code): output current at the three Vctrl window points
# Vctrl window under test: 0.9 .. 2.4 V, nominal 1.65 V (DR-001 Decision 2)
# units: Icp in unit legs = 1 + b0 + 2*b1
process,temp_c,vdd_v,b1,b0,units,iup_lo_a,idn_lo_a,iup_mid_a,idn_mid_a,iup_hi_a,idn_hi_a
cornerA,27,3.30,0,0,1,1.60e-06,1.40e-06,1.55e-06,1.45e-06,1.50e-06,1.50e-06
cornerA,27,3.30,1,1,4,5.30e-06,4.70e-06,5.10e-06,4.90e-06,5.00e-06,5.00e-06
cornerB,125,3.30,0,0,1,1.80e-06,1.60e-06,1.75e-06,1.65e-06,1.70e-06,1.70e-06
cornerB,125,3.30,1,1,4,5.80e-06,5.20e-06,5.60e-06,5.40e-06,5.50e-06,5.50e-06
cornerC,125,2.97,0,0,1,1.90e-06,1.70e-06,1.85e-06,1.75e-06,1.80e-06,1.80e-06
cornerC,125,2.97,1,1,4,6.30e-06,5.70e-06,6.10e-06,5.90e-06,6.00e-06,6.00e-06
"""

#: The campaign's own committed reduction of the same grid -- the second route
#: rule 5 cross-checks against, and the file whose header states the
#: convention the check reads rather than inventing one.
CP_TRIM_CSV_TEXT = """\
# Icp delivered per trim code -- mean of the two polarities at Vctrl = 1.65 V, min/max across every corner
units,icp_min_a,icp_max_a
1,1.55e-06,1.85e-06
4,5.00e-06,6.00e-06
"""

#: T_ov (rule 6): three corners x two control voltages x three dphi points.
#: At zero phase error the smallest UP/DN pulse per corner is
#:   cornerA/27/3.30  min(1.20, 1.50, 1.60, 1.00) = 1.000 ns  <- best corner
#:   cornerB/125/3.30 min(1.70, 1.90, 1.80, 1.75) = 1.700 ns
#:   cornerC/125/2.97 min(2.00, 2.20, 2.30, 2.40) = 2.000 ns  <- worst corner
#: Every d-1n / d1n row carries a 0.500 ns pulse: a reduction that failed to
#: select on the dphi axis would report 0.500 ns as the best corner and fail,
#: which is the point of putting them there. They also carry `not measured`
#: in q_zero, the campaign's own marker for "this is not a dphi = 0 point".
TOV_CSV_TEXT = """\
corner,temp_c,vdd,vc,d,corner_id,qnet2,qnet,width_up,width_dn,q_zero,verdict
cornerA,27.0,3.30,v0p90,d-1n,cornerA_27c_3.30v_v0p90_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerA,27.0,3.30,v0p90,d0,cornerA_27c_3.30v_v0p90_d0,-8.0e-15,-4.0e-15,1.20e-09,1.50e-09,-4.0e-15,PASS
cornerA,27.0,3.30,v0p90,d1n,cornerA_27c_3.30v_v0p90_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
cornerA,27.0,3.30,v1p65,d-1n,cornerA_27c_3.30v_v1p65_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerA,27.0,3.30,v1p65,d0,cornerA_27c_3.30v_v1p65_d0,-8.0e-15,-4.0e-15,1.60e-09,1.00e-09,-4.0e-15,PASS
cornerA,27.0,3.30,v1p65,d1n,cornerA_27c_3.30v_v1p65_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
cornerB,125.0,3.30,v0p90,d-1n,cornerB_125c_3.30v_v0p90_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerB,125.0,3.30,v0p90,d0,cornerB_125c_3.30v_v0p90_d0,-8.0e-15,-4.0e-15,1.70e-09,1.90e-09,-4.0e-15,PASS
cornerB,125.0,3.30,v0p90,d1n,cornerB_125c_3.30v_v0p90_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
cornerB,125.0,3.30,v1p65,d-1n,cornerB_125c_3.30v_v1p65_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerB,125.0,3.30,v1p65,d0,cornerB_125c_3.30v_v1p65_d0,-8.0e-15,-4.0e-15,1.80e-09,1.75e-09,-4.0e-15,PASS
cornerB,125.0,3.30,v1p65,d1n,cornerB_125c_3.30v_v1p65_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
cornerC,125.0,2.97,v0p90,d-1n,cornerC_125c_2.97v_v0p90_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerC,125.0,2.97,v0p90,d0,cornerC_125c_2.97v_v0p90_d0,-8.0e-15,-4.0e-15,2.00e-09,2.20e-09,-4.0e-15,PASS
cornerC,125.0,2.97,v0p90,d1n,cornerC_125c_2.97v_v0p90_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
cornerC,125.0,2.97,v1p65,d-1n,cornerC_125c_2.97v_v1p65_d-1n,-2.0e-14,-1.0e-14,0.50e-09,0.50e-09,not measured,PASS
cornerC,125.0,2.97,v1p65,d0,cornerC_125c_2.97v_v1p65_d0,-8.0e-15,-4.0e-15,2.30e-09,2.40e-09,-4.0e-15,PASS
cornerC,125.0,2.97,v1p65,d1n,cornerC_125c_2.97v_v1p65_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09,not measured,PASS
"""

#: The systematic per-event charge asymmetry (rule 7): nine switching events,
#: three per corner, with qup_c fixed at 1.0e-14 so |qup + qdn| is exactly the
#: intended figure. The nine values in fC are
#:   0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0
#: -> worst case 3.00 fC (DR-018's stated input) and median 1.50 fC (the
#: second figure DR-006 SS8 states for the same quantity).
CP_SWITCH_CSV_TEXT = """\
# per (PVT corner, control voltage): steady-state current, delivered charge, effective pulse width
process,temp_c,vdd_v,vctrl_v,iup_ss_a,idn_ss_a,qup_c,qdn_c
cornerA,27,3.30,0.9,5.0e-06,-5.0e-06,1.0e-14,-9.5e-15
cornerA,27,3.30,1.65,5.0e-06,-5.0e-06,1.0e-14,-9.2e-15
cornerA,27,3.30,2.4,5.0e-06,-5.0e-06,1.0e-14,-9.0e-15
cornerB,125,3.30,0.9,5.0e-06,-5.0e-06,1.0e-14,-8.8e-15
cornerB,125,3.30,1.65,5.0e-06,-5.0e-06,1.0e-14,-8.5e-15
cornerB,125,3.30,2.4,5.0e-06,-5.0e-06,1.0e-14,-8.2e-15
cornerC,125,2.97,0.9,5.0e-06,-5.0e-06,1.0e-14,-8.0e-15
cornerC,125,2.97,1.65,5.0e-06,-5.0e-06,1.0e-14,-7.5e-15
cornerC,125,2.97,2.4,5.0e-06,-5.0e-06,1.0e-14,-7.0e-15
"""

#: DR-006 SS8 is where the systematic asymmetry was priced, and DR-018's
#: Source column points at it. Both figures it states are graded.
DR006_TEXT = """# DR-006: test fixture

## Consequences

**8. Control-line ripple is dominated by charge-pump charge asymmetry.** The
per-event charge asymmetry `|q_up + q_dn|` lands on C2 once per reference
cycle, and the campaign measures the result: `|q_up + q_dn|` = **3.00 fC
worst case, 1.50 fC median**, against far larger figures for the pre-#46
charge pump.
"""

#: Charge totals, from the reduced figures above and Icp = 6.00 uA,
#: T_ov = 2.000 ns (both the worst/larger end of the ranges the DR-018
#: fixture states, and both now re-derived from the fixtures above):
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
#: systematic charge asymmetry and the stated term-3 figure from. Each row's
#: label states its own reduction (the trim code, the corner count, "min
#: UP/DN pulse at zero phase error") and its Source column names the campaign
#: to reduce, both of which the check reads rather than assuming.
DR018_TEXT = """# DR-018: test fixture

- **Status**: proposed

## Context

Both are measured, not assumed:

| Input | Value | Source |
|---|---|---|
| Reset overlap `T_ov`, min UP/DN pulse at zero phase error, 3 corners | 1.000 – 2.000 ns (worst `cornerC`/125 °C/2.97 V) | `%(tov_csv)s` |
| `Icp`, largest trim code (11, four unit legs), 3 corners | 5.00 – 6.00 µA | `sim/cp-compliance/records/%(icp_record)s.md` |
| Systematic per-event charge asymmetry \\|q_up + q_dn\\| | 3.00 fC worst corner | `sim/cp-compliance/…-000000-bbb2222` via DR-006 §8 |
| Statistical residual net charge (term 3), corner-combined \\|mean\\|+3σ | 7.5548 fC | a test source |

## Decision

Not exercised by this check.
""" % {"tov_csv": TOV_CSV, "icp_record": ICP_RECORD}


class _Tree:
    """A throwaway repo tree with the real check installed at spec/lib/."""

    def __init__(self, root: Path):
        self.root = root
        (root / "spec" / "lib").mkdir(parents=True)
        shutil.copy2(CHECK, root / "spec" / "lib" / CHECK.name)
        self.write(SPEC_DOC, SPEC_TEXT)
        self.write(DR018_DOC, DR018_TEXT)
        self.write(DR006_DOC, DR006_TEXT)
        self.write(DC_CSV, DC_CSV_TEXT)
        self.write(PFD_CSV, PFD_CSV_TEXT)
        self.write(CP_DC_CSV, CP_DC_CSV_TEXT)
        self.write(CP_TRIM_CSV, CP_TRIM_CSV_TEXT)
        self.write(CP_SWITCH_CSV, CP_SWITCH_CSV_TEXT)
        self.write(TOV_CSV, TOV_CSV_TEXT)

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

    # ------------------------------------------------------------ rule 5 --
    # Icp, re-derived from sim/cp-compliance's own committed grid (issue
    # #573). Before it, these three figures were read from DR-018's Input
    # table and a drift in either the table or the evidence was invisible.

    def test_icp_stated_worst_corner_drift_fails(self):
        # DR-018 says 9.00 uA; the campaign's own grid says 6.00 uA.
        self.tree.write(DR018_DOC, DR018_TEXT.replace("6.00 µA", "9.00 µA"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("states Icp's worst corner as 9.00 uA", result.stderr)

    def test_icp_stated_best_corner_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("5.00 – 6.00", "4.00 – 6.00"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("states Icp's best corner as 4.00 uA", result.stderr)

    def test_icp_evidence_drift_fails(self):
        # The evidence moves instead of the document: the worst corner's
        # mid-window currents now reduce to 7.00 uA, not the stated 6.00.
        self.tree.write(
            CP_DC_CSV,
            CP_DC_CSV_TEXT.replace(
                "cornerC,125,2.97,1,1,4,6.30e-06,5.70e-06,6.10e-06,5.90e-06",
                "cornerC,125,2.97,1,1,4,6.30e-06,5.70e-06,7.10e-06,6.90e-06",
            ),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("states Icp's worst corner as 6.00 uA", result.stderr)

    def test_icp_disagrees_with_campaigns_own_reduction_fails(self):
        # The per-point grid and the campaign's own committed reduction of it
        # must agree -- two routes to one number.
        self.tree.write(
            CP_TRIM_CSV, CP_TRIM_CSV_TEXT.replace("4,5.00e-06,6.00e-06", "4,5.00e-06,9.00e-06")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not the one the campaign committed", result.stderr)

    def test_icp_wrong_trim_code_selects_nothing_fails(self):
        # DR-018 prices code 11; a document that priced code 10 would be
        # reduced against rows this campaign does not have.
        self.tree.write(
            DR018_DOC,
            DR018_TEXT.replace("(11, four unit legs)", "(10, three unit legs)"),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at trim code 10", result.stderr)

    def test_icp_leg_count_inconsistent_with_code_fails(self):
        self.tree.write(
            DR018_DOC,
            DR018_TEXT.replace("(11, four unit legs)", "(11, three unit legs)"),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("leg formula", result.stderr)

    def test_icp_corner_shortfall_fails(self):
        # One corner dropped from the grid: a worst case over 2 of the 3
        # corners the row claims is a different figure.
        mutated = "\n".join(
            ln for ln in CP_DC_CSV_TEXT.splitlines() if not ln.startswith("cornerB")
        ) + "\n"
        self.tree.write(CP_DC_CSV, mutated)
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("subset of the mandated grid", result.stderr)

    def test_icp_campaign_convention_removed_fails(self):
        self.tree.write(
            CP_TRIM_CSV,
            "\n".join(
                ln
                for ln in CP_TRIM_CSV_TEXT.splitlines()
                if not ln.startswith("# Icp delivered")
            )
            + "\n",
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer states the reduction", result.stderr)

    def test_icp_window_nominal_disagreement_fails(self):
        # The convention reduces at Vctrl = 1.65 V; if the DC bench's window
        # nominal moved, the mid-window columns are no longer that point.
        self.tree.write(
            CP_DC_CSV, CP_DC_CSV_TEXT.replace("nominal 1.65 V", "nominal 2.00 V")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot do so when the two disagree", result.stderr)

    def test_icp_unresolvable_record_citation_fails(self):
        self.tree.write(
            DR018_DOC, DR018_TEXT.replace(ICP_RECORD, "20269999-999999-fff9999")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no committed directory", result.stderr)

    def test_icp_missing_corner_count_fails(self):
        self.tree.write(
            DR018_DOC,
            DR018_TEXT.replace("(11, four unit legs), 3 corners", "(11, four unit legs)"),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not state how many corners", result.stderr)

    # ------------------------------------------------------------ rule 6 --
    # T_ov, re-derived from sim/pfd-deadzone's own committed grid.

    def test_t_ov_stated_worst_corner_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("2.000 ns", "5.000 ns"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "states the worst-corner reset overlap as 5.000 ns", result.stderr
        )

    def test_t_ov_stated_best_corner_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("1.000 – 2.000", "0.500 – 2.000"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shortest reset overlap as 0.500 ns", result.stderr)

    def test_t_ov_evidence_drift_fails(self):
        self.tree.write(
            TOV_CSV, TOV_CSV_TEXT.replace("d0,cornerC_125c_2.97v_v0p90_d0,-8.0e-15,-4.0e-15,2.00e-09", "d0,cornerC_125c_2.97v_v0p90_d0,-8.0e-15,-4.0e-15,3.00e-09")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "states the worst-corner reset overlap as 2.000 ns", result.stderr
        )

    def test_t_ov_named_worst_corner_drift_fails(self):
        # The right number at the wrong corner is not the same reduction.
        self.tree.write(
            DR018_DOC,
            DR018_TEXT.replace(
                "(worst `cornerC`/125 °C/2.97 V)", "(worst `cornerA`/27 °C/3.30 V)"
            ),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("as T_ov's worst corner", result.stderr)

    def test_t_ov_ignores_non_zero_phase_rows(self):
        # The +-1 ns rows carry 0.500 ns pulses and must not enter the
        # reduction at all; moving one further does not change the verdict.
        self.tree.write(
            TOV_CSV,
            TOV_CSV_TEXT.replace(
                "d1n,cornerA_27c_3.30v_v0p90_d1n,-1.4e-15,-7.0e-16,0.50e-09,0.50e-09",
                "d1n,cornerA_27c_3.30v_v0p90_d1n,-1.4e-15,-7.0e-16,0.05e-09,9.90e-09",
            ),
        )
        result = self.tree.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_t_ov_zero_phase_marker_disagreement_fails(self):
        # The campaign measures q_zero only at dphi = 0; a numeric q_zero on
        # a +1 ns row means this check's axis parse and the campaign's own
        # marker disagree about which rows are the zero-phase ones.
        self.tree.write(
            TOV_CSV,
            TOV_CSV_TEXT.replace(
                "0.50e-09,0.50e-09,not measured,PASS\ncornerA,27.0,3.30,v1p65,d-1n",
                "0.50e-09,0.50e-09,-1.0e-15,PASS\ncornerA,27.0,3.30,v1p65,d-1n",
            ),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disagree", result.stderr)

    def test_t_ov_missing_csv_fails(self):
        (self.root / TOV_CSV).unlink()
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    # ------------------------------------------------------------ rule 7 --
    # The systematic per-event charge asymmetry, re-derived from
    # sim/cp-compliance's switching bench.

    def test_systematic_charge_stated_drift_fails(self):
        self.tree.write(DR018_DOC, DR018_TEXT.replace("3.00 fC worst", "9.00 fC worst"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("as 9.00 fC worst corner", result.stderr)

    def test_systematic_charge_evidence_drift_fails(self):
        self.tree.write(
            CP_SWITCH_CSV,
            CP_SWITCH_CSV_TEXT.replace(
                "cornerC,125,2.97,2.4,5.0e-06,-5.0e-06,1.0e-14,-7.0e-15",
                "cornerC,125,2.97,2.4,5.0e-06,-5.0e-06,1.0e-14,-5.0e-15",
            ),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("largest |qup + qdn|", result.stderr)

    def test_dr006_worst_case_drift_fails(self):
        self.tree.write(
            DR006_DOC, DR006_TEXT.replace("3.00 fC\nworst case", "9.00 fC\nworst case")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prices the systematic charge asymmetry at 9.00 fC", result.stderr)

    def test_dr006_median_drift_fails(self):
        # The median says the worst case is a tail rather than the typical
        # part; a reduction over a different population can still reproduce
        # the maximum, so both figures are graded.
        self.tree.write(DR006_DOC, DR006_TEXT.replace("1.50 fC median", "2.50 fC median"))
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("median as 2.50", result.stderr)

    def test_dr006_restated_figure_missing_fails(self):
        self.tree.write(
            DR006_DOC,
            DR006_TEXT.replace(
                "`|q_up + q_dn|` = **3.00 fC\nworst case, 1.50 fC median**",
                "the asymmetry is small",
            ),
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer states", result.stderr)

    def test_systematic_charge_corner_shortfall_fails(self):
        mutated = "\n".join(
            ln for ln in CP_SWITCH_CSV_TEXT.splitlines() if not ln.startswith("cornerB")
        ) + "\n"
        self.tree.write(CP_SWITCH_CSV, mutated)
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("subset of the mandated grid", result.stderr)

    def test_elided_record_citation_resolves(self):
        # DR-018 cites this record in its `…-<time>-<sha>` short form; an
        # unresolvable short form must fail rather than be skipped.
        self.tree.write(
            DR018_DOC, DR018_TEXT.replace("…-000000-bbb2222", "…-000000-ccc3333")
        )
        result = self.tree.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no committed directory", result.stderr)

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
