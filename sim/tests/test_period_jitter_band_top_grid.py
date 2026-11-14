"""`sim/period-jitter-band-top/testbench/tb.json`, against committed evidence.

This campaign is `sim/period-jitter` moved to the 200 MHz top of the ratified
output band, and moving there is not a one-parameter change: `spec/pll.md`'s
**band-selection rule** (normative, DR-003 Decision 4) requires the lowest
3-bit VCO band code that reaches the target, and at 200 MHz that is not one
code for the whole grid — it is band 6 at 34 of the 45 PVT points and band 7
at the other 11. So this manifest carries 45 hand-checkable *(band, vstart)*
pairs that came out of another record plus a ratified rule, and four things
can rot there, none of which any simulator run would notice — it would just
silently measure a **mis-configured part**, or a correctly-configured one
released at the wrong voltage:

- a band code drifting away from the one the rule selects,
- a `vstart` drifting away from what the committed VCO record says,
- a point id (`b6vs2p417`) drifting away from the band and voltage it names,
- the union of the grid blocks quietly ceasing to be the mandated PVT matrix.

Those four, plus the N = 8 divider encoding (a wrong one-hot SEL still locks,
at the wrong N — `sim/lib/pll_top_dut.sh`'s own header says so), follow from
the *configuration* rather than from what is being measured, so they are
checked by the mixins in `sim/tests/_band_top_grid.py`, shared with the
`sim/reference-spur-band-top` campaign that runs the same matrix at the same
binding point. What is campaign-specific, and stays below, is *comparability*:
everything this campaign claims to hold identical to `sim/period-jitter` must
actually be identical, or "what does moving to the top of the band do to the
jitter?" is not the question the two campaigns jointly answer.

Runs in the harness unit-test suite: no PDK, no ngspice, no network — it reads
committed CSV and committed JSON only.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "period-jitter-band-top" / "testbench"
SIBLING_TB = SIM_DIR / "period-jitter" / "testbench" / "tb.json"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

from _band_top_grid import (  # noqa: E402
    BandTopGridMixin,
    OperatingPointIsRuleCompliantMixin,
    StaticConfigurationEncodesTheClaimedOperatingPointMixin,
)


class BandTopGrid(BandTopGridMixin, unittest.TestCase):
    """The manifest's own shape: is the declared grid the mandated matrix?"""

    TESTBENCH = TESTBENCH


class OperatingPointIsRuleCompliant(
    OperatingPointIsRuleCompliantMixin, unittest.TestCase
):
    """Every band code and release voltage, re-derived from the ratified rule."""

    TESTBENCH = TESTBENCH


class StaticConfigurationEncodesTheClaimedOperatingPoint(
    StaticConfigurationEncodesTheClaimedOperatingPointMixin, unittest.TestCase
):
    """N = 8 and Icp code 0, spelled in bits rather than asserted in prose."""

    TESTBENCH = TESTBENCH


class ComparableWithTheSiblingCampaign(unittest.TestCase):
    """What this campaign claims to hold identical must actually be identical."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((TESTBENCH / "tb.json").read_text())
        cls.sibling = json.loads(SIBLING_TB.read_text())

    def test_only_the_intended_parameters_differ(self):
        mine, theirs = self.manifest["params"], self.sibling["params"]
        # Held: the reference rate, the Icp trim code, and every transient /
        # window control -- so the ripple mechanism is excited identically and
        # the measurement window is the same 2.0 us of settled output.
        for key in ("fref", "cpb0_code", "cpb1_code",
                    "ktstep", "ktstop", "ktstart", "ktmax",
                    "ta", "tb", "wa", "wb"):
            self.assertEqual(mine[key], theirs[key], key)
        # Changed: N, and therefore the divider bits.
        self.assertNotEqual(mine["nratio"], theirs["nratio"])
        # Changed in kind: the sibling pins one static band in `params`; here
        # the band is per point.
        for key in ("b0_code", "b1_code", "b2_code"):
            self.assertIn(key, theirs)
            self.assertNotIn(key, mine)

    def test_solver_settings_and_measurements_are_identical(self):
        # A jitter number is only comparable across two campaigns if both
        # converged under the same tolerances and reduced the same measures.
        self.assertEqual(self.manifest["options"], self.sibling["options"])
        self.assertEqual(self.manifest["raw_measures"], self.sibling["raw_measures"])
        self.assertEqual(self.manifest["analyses"], self.sibling["analyses"])
        self.assertEqual(self.manifest["derived"], self.sibling["derived"])

    def test_the_reduction_code_is_the_siblings_own_file_not_a_copy(self):
        mod = load_module(TESTBENCH / "derive.py")
        base = SIM_DIR / "period-jitter" / "testbench" / "derive.py"
        # `load_module` re-executes the file, so identity of the module object
        # is not the invariant -- provenance of the code is. Every reduction
        # entry point this campaign exposes must be defined in the SIBLING's
        # file, which is what makes sim/tests/test_period_jitter_derive.py's
        # synthetic-waveform coverage apply to this campaign too.
        for name in ("extract_period_jitter", "derive_point", "derive_tables"):
            self.assertEqual(
                Path(getattr(mod, name).__code__.co_filename).resolve(),
                base.resolve(),
                name,
            )
        self.assertEqual(mod.DRAFT_TJ_RMS_PCT, load_module(base).DRAFT_TJ_RMS_PCT)

    def test_the_draft_jitter_target_is_the_same_line(self):
        self.assertEqual(
            self.manifest["checks"]["tj_rms_pct"], self.sibling["checks"]["tj_rms_pct"]
        )


if __name__ == "__main__":
    unittest.main()
