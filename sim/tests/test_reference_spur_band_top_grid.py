"""`sim/reference-spur-band-top/testbench/tb.json`, against committed evidence.

This campaign is `sim/reference-spur` moved to the 200 MHz top of the ratified
output band — the frequency `spec/pll.md`'s ≤ −55 dBc spur line actually binds
at, and which that campaign reports by *scaling* its 150 MHz measurement by
+2.50 dB rather than by measuring. Moving there is not a one-parameter change:
`spec/pll.md`'s **band-selection rule** (normative, DR-003 Decision 4) requires
the lowest 3-bit VCO band code that reaches the target, and at 200 MHz that is
not one code for the whole grid — it is band 6 at 34 of the 45 PVT points and
band 7 at the other 11. So this manifest carries 45 hand-checkable
*(band, vstart)* pairs that came out of another record plus a ratified rule,
and four things can rot there, none of which any simulator run would notice —
it would just silently measure a **mis-configured part**, or a correctly
configured one released at the wrong voltage:

- a band code drifting away from the one the rule selects,
- a `vstart` drifting away from what the committed VCO record says,
- a point id (`b7vs1p886`) drifting away from the band and voltage it names,
- the union of the grid blocks quietly ceasing to be the mandated PVT matrix.

Those four, plus the N = 8 divider encoding (a wrong one-hot SEL still locks,
at the wrong N — `sim/lib/pll_top_dut.sh`'s own header says so, and a spur read
at the wrong N is the ratio of whatever landed beside the carrier bin), follow
from the *configuration* rather than from what is being measured, so they are
checked by the mixins in `sim/tests/_band_top_grid.py`, shared with the
`sim/period-jitter-band-top` campaign that runs the same matrix at the same
binding point.

What stays below is campaign-specific — all of it about *comparability with
the 150 MHz campaign whose number this one is meant to replace at the binding
point*: everything this campaign claims to hold identical to
`sim/reference-spur` must actually be identical; the reduction must be that
campaign's own file rather than a copy, so
`sim/tests/test_reference_spur_derive.py`'s known-answer coverage applies here
too; and the binding-point column must be a measurement here and a scaling
there.

Runs in the harness unit-test suite: no PDK, no ngspice, no network — it reads
committed CSV and committed JSON only.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "reference-spur-band-top" / "testbench"
SIBLING_TB = SIM_DIR / "reference-spur" / "testbench" / "tb.json"
SIBLING_DERIVE = SIM_DIR / "reference-spur" / "testbench" / "derive.py"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

from _band_top_grid import (  # noqa: E402
    TARGET_HZ,
    BandTopGridMixin,
    OperatingPointIsRuleCompliantMixin,
    StaticConfigurationEncodesTheClaimedOperatingPointMixin,
)

#: `spec/pll.md`'s ratified Reference spur line.
SPUR_TARGET_DBC = -55.0


class BandTopGrid(BandTopGridMixin, unittest.TestCase):
    """The manifest's own shape: is the declared grid the mandated matrix?

    The gap this campaign exists to close is "40 of the 45 PVT points have no
    measurement at the binding frequency", so a grid that is not the whole
    mandated matrix would not close it even once run.
    """

    TESTBENCH = TESTBENCH


class OperatingPointIsRuleCompliant(
    OperatingPointIsRuleCompliantMixin, unittest.TestCase
):
    """Every band code and release voltage, re-derived from the ratified rule."""

    TESTBENCH = TESTBENCH

    def test_the_two_band_top_campaigns_agree_point_for_point(self):
        # sim/period-jitter-band-top runs the same mandated matrix at the same
        # 200 MHz binding point. If the two ever disagreed about which band the
        # ratified rule selects at a corner, one of them would be measuring a
        # differently-configured part and the two campaigns' numbers could not
        # be read together. They load the same rule module, so this test is
        # what would catch a hand-edit to either manifest, not a logic drift.
        sibling_tb = json.loads(
            (SIM_DIR / "period-jitter-band-top" / "testbench" / "tb.json").read_text()
        )
        self.assertEqual(
            self.mod.declared_map(self.manifest), self.mod.declared_map(sibling_tb)
        )


class StaticConfigurationEncodesTheClaimedOperatingPoint(
    StaticConfigurationEncodesTheClaimedOperatingPointMixin, unittest.TestCase
):
    """N = 8 and Icp code 0, spelled in bits rather than asserted in prose."""

    TESTBENCH = TESTBENCH

    def test_the_carrier_bin_the_reduction_reads_is_the_one_n_puts_it_on(self):
        # derive.py reads the carrier at bin `nratio` and the sidebands at
        # `nratio +- 1`. At N = 8 that is 8*f_ref = 200 MHz, and the manifest's
        # own `fout` window is what refuses a run that locked elsewhere.
        n = int(float(self.params["nratio"]))
        fref = float(self.params["fref"])
        self.assertAlmostEqual(n * fref, TARGET_HZ, delta=1.0)
        self.assertGreaterEqual(n + 1, 2)


class ComparableWithTheSiblingCampaign(unittest.TestCase):
    """What this campaign claims to hold identical must actually be identical."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((TESTBENCH / "tb.json").read_text())
        cls.sibling = json.loads(SIBLING_TB.read_text())

    def test_only_the_intended_parameters_differ(self):
        mine, theirs = self.manifest["params"], self.sibling["params"]
        # Held: the reference rate, the Icp trim code, the lock-detector
        # window trim, and every transient / spectral-window control -- so the
        # once-per-reference-cycle charge event is excited identically and the
        # spectrum is taken over the same windows.
        for key in ("fref", "cpb0_code", "cpb1_code",
                    "ldt0_code", "ldt1_code", "ldt2_code", "ldt3_code",
                    "ktstep", "ktstop", "ktstart", "ktmax",
                    "ta", "tb", "wa", "wb", "wcyc"):
            self.assertEqual(mine[key], theirs[key], key)
        # Changed: N, and therefore the divider bits.
        self.assertNotEqual(mine["nratio"], theirs["nratio"])
        # Changed in kind: the sibling pins one static band in `params`; here
        # the band is per point.
        for key in ("b0_code", "b1_code", "b2_code"):
            self.assertIn(key, theirs)
            self.assertNotIn(key, mine)

    def test_solver_settings_and_measurements_are_identical(self):
        # A spur is only comparable across two campaigns if both converged
        # under the same tolerances and reduced the same measures.
        self.assertEqual(self.manifest["options"], self.sibling["options"])
        self.assertEqual(self.manifest["raw_measures"], self.sibling["raw_measures"])
        self.assertEqual(self.manifest["analyses"], self.sibling["analyses"])
        self.assertEqual(self.manifest["derived"], self.sibling["derived"])
        self.assertEqual(self.manifest["raw_files"], self.sibling["raw_files"])
        self.assertEqual(
            self.manifest["topology_groups"], self.sibling["topology_groups"]
        )

    def test_the_reduction_code_is_the_siblings_own_file_not_a_copy(self):
        mod = load_module(TESTBENCH / "derive.py")
        # `load_module` re-executes the file, so identity of the module object
        # is not the invariant -- provenance of the code is. Every reduction
        # entry point this campaign exposes must be defined in the SIBLING's
        # file, which is what makes sim/tests/test_reference_spur_derive.py's
        # known-answer coverage apply to this campaign too.
        for name in ("derive_point", "derive_tables"):
            self.assertEqual(
                Path(getattr(mod, name).__code__.co_filename).resolve(),
                SIBLING_DERIVE.resolve(),
                name,
            )
        self.assertEqual(mod.SPUR_TARGET_DBC, load_module(SIBLING_DERIVE).SPUR_TARGET_DBC)

    def test_both_campaigns_are_scored_against_the_same_ratified_line(self):
        self.assertEqual(
            self.manifest["checks"]["spur_dbc"], self.sibling["checks"]["spur_dbc"]
        )
        self.assertEqual(self.manifest["checks"]["spur_dbc"]["max"], SPUR_TARGET_DBC)
        # The binding-point column is checked against the same line in both,
        # which is what makes a manifest edit that quietly changed N show up as
        # two diverging columns rather than one silently re-based number.
        self.assertEqual(
            self.manifest["checks"]["spur_dbc_200m"],
            self.sibling["checks"]["spur_dbc_200m"],
        )


class TheBindingPointColumnIsNoLongerArithmetic(unittest.TestCase):
    """`spur_dbc_at_200mhz` must be the measurement here, and a scaling there."""

    @classmethod
    def setUpClass(cls):
        cls.derive = load_module(SIBLING_DERIVE)
        cls.manifest = json.loads((TESTBENCH / "tb.json").read_text())
        cls.sibling = json.loads(SIBLING_TB.read_text())

    def test_this_campaign_needs_no_extrapolation(self):
        scale = self.derive.binding_scale_db(self.manifest["params"])
        self.assertAlmostEqual(scale, 0.0, places=9)
        self.assertAlmostEqual(
            self.derive.f_out_of(self.manifest["params"]),
            self.derive.F_OUT_BINDING,
            delta=1.0,
        )

    def test_the_150mhz_campaign_still_gets_its_2_5_db(self):
        # The same function, on the sibling's manifest: the change that made
        # this campaign possible must not have re-based the committed one.
        scale = self.derive.binding_scale_db(self.sibling["params"])
        self.assertAlmostEqual(scale, 2.4988, places=3)
        self.assertAlmostEqual(
            self.derive.f_out_of(self.sibling["params"]), 150e6, delta=1.0
        )


if __name__ == "__main__":
    unittest.main()
