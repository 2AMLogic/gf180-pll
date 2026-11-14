#!/usr/bin/env python3
"""The invariants the two 200 MHz band-top campaigns share, in one place.

``sim/period-jitter-band-top`` and ``sim/reference-spur-band-top`` are two
different measurements of the same *configuration*: the mandated 45-point PVT
matrix at the 200 MHz top of the ratified output band, with the 3-bit VCO band
code chosen per point by `spec/pll.md`'s band-selection rule (normative, DR-003
Decision 4). Everything that follows from that configuration rather than from
what is being measured belongs here and is checked identically for both:

* the declared grid is exactly the mandated matrix,
* every point id spells the band and release voltage it is configured with,
* every ``(band, vstart)`` pair is the one the rule and the committed VCO
  record select, and no lower band reaches the target,
* the selected points sit inside `spec/pll.md` row 17's Kvco bound,
* the manifest fragment is still the one its own generator emits,
* the static divider and Icp trim bits encode N = 8 at f_ref = 25 MHz.

The point of sharing them is that a change to one of these invariants -- the
point-id format, the mandated matrix, the Kvco bound -- is then made once. Two
hand-maintained copies fail in a specific way: the copy that is missed goes on
checking its campaign against the *old* rule and nothing fails, so one campaign
is silently measuring a differently-configured part. (The same duplication in
the two campaigns' ``check_config.sh`` scripts was consolidated under #881;
this is the test-side half of that.)

The three classes below are **mixins, not test cases**: they do not inherit
``unittest.TestCase``, so neither this module nor an import of it hands
``unittest discover`` anything to collect. A campaign's ``test_*.py`` combines
each with ``unittest.TestCase`` and points it at a testbench::

    class BandTopGrid(_band_top_grid.BandTopGridMixin, unittest.TestCase):
        TESTBENCH = SIM_DIR / "reference-spur-band-top" / "testbench"

and adds whatever that campaign checks beyond the shared configuration. This
module is also not itself a ``test_*.py`` module, which is the same belt-and-
braces arrangement ``sim/tests/_fixtures.py`` uses.

Reads committed CSV and committed JSON only: no PDK, no ngspice, no network.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_DIR))

from harness.derived import load_module  # noqa: E402,F401  (re-exported)

#: The mandated matrix: `sim/harness/corners.py`'s `CORNER_SETS["mos"]` x the
#: three temperatures x the three supplies.
MOS_BUNDLES = {"typical", "ff", "ss", "fs", "sf"}
TEMPERATURES = {-40.0, 27.0, 125.0}
SUPPLY_ALIASES = {"low", "nom", "high"}

#: The top of the ratified output band -- both campaigns' reason for existing.
TARGET_HZ = 200e6

#: `spec/pll.md` row 17: Kvco <= 150 MHz/V at every legal operating point
#: under the band-selection rule.
KVCO_BOUND_HZ_PER_V = 150e6

#: `spec/pll.md`'s Icp trim-code rule at f_ref = 25 MHz: one unit leg, i.e.
#: `cp.sch`'s `Icp = Iunit * (1 + B0 + 2*B1)` with B0 = B1 = 0.
TRIM_CODE_AT_25MHZ = {"cpb0_code": "0", "cpb1_code": "0"}


def load_manifest(testbench):
    """The campaign's committed ``tb.json``, parsed."""
    return json.loads((Path(testbench) / "tb.json").read_text())


def divider_codes(n):
    """`divider_chain.sch`'s documented encoding, as `cloop_divider_params` emits it.

    N = 2^k + sum_{j<k} P_j*2^j with one-hot SEL_(k-1) = 1. Re-derived here
    rather than shelling out so the test runs anywhere python does;
    `check_config.sh` in each campaign directory independently diffs the same
    bits against `sim/lib/pll_top_dut.sh` itself.
    """
    k = 0
    while 2 ** (k + 1) <= n:
        k += 1
    resid = n - 2 ** k
    codes = {}
    for j in range(6):
        codes["sel%d_code" % j] = "1" if j == k - 1 else "0"
        codes["p%d_code" % j] = "1" if (j < k and (resid >> j) & 1) else "0"
    return codes


class BandTopGridMixin:
    """The manifest's own shape: is the declared grid the mandated matrix?

    Mix with ``unittest.TestCase`` and set ``TESTBENCH``.
    """

    #: The campaign's ``testbench/`` directory. Set by the subclass.
    TESTBENCH: Path

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifest = load_manifest(cls.TESTBENCH)
        cls.blocks = cls.manifest["grid"]
        cls.points = cls.manifest["sweeps"]["op"]["points"]

    def test_grid_union_is_exactly_the_mandated_pvt_matrix(self):
        seen = []
        for block in self.blocks:
            for corner in block["corners"]:
                for temp in block["temperatures_c"]:
                    for supply in block["supplies"]:
                        seen.append((corner, float(temp), supply))
        self.assertEqual(len(seen), len(set(seen)), "a PVT point is declared twice")
        expected = {
            (corner, temp, supply)
            for corner in MOS_BUNDLES
            for temp in TEMPERATURES
            for supply in SUPPLY_ALIASES
        }
        self.assertEqual(set(seen), expected)
        self.assertEqual(len(seen), 45)

    def test_every_block_carries_a_description_and_exactly_one_operating_point(self):
        for block in self.blocks:
            self.assertTrue(block.get("description", "").strip(), block)
            self.assertEqual(len(block["axes"]["op"]), 1, block)
            self.assertIn(block["axes"]["op"][0], self.points, block)

    def test_point_id_spells_its_own_band_and_release_voltage(self):
        # `b6vs2p417` must name band 6 and 2.417 V. A hand-edit that changes one
        # without the other produces a manifest that reads correctly and
        # simulates wrongly -- at the wrong band, which is a mis-configured part.
        for point_id, spec in self.points.items():
            match = re.match(r"^b(\d)vs(\d+p\d+)$", point_id)
            self.assertIsNotNone(match, "malformed point id %r" % point_id)
            band = int(match.group(1))
            params = spec["params"]
            self.assertEqual(match.group(2), params["vstart"].replace(".", "p"), point_id)
            self.assertEqual(band & 1, int(params["b0_code"]), point_id)
            self.assertEqual((band >> 1) & 1, int(params["b1_code"]), point_id)
            self.assertEqual((band >> 2) & 1, int(params["b2_code"]), point_id)

    def test_nothing_fixed_in_params_shadows_the_axis(self):
        # A leftover fixed `vstart` or band bit is emitted BEFORE the axis
        # point's own, so it would not change the deck -- but the manifest would
        # read as though every corner ran at one voltage in one band. That is
        # how the 150 MHz sibling campaigns' manifests correctly read, and
        # exactly the misreading a band-top campaign exists to correct.
        for key in ("vstart", "b0_code", "b1_code", "b2_code"):
            self.assertNotIn(key, self.manifest["params"], key)

    def test_pvt_axes_are_the_full_default_grid(self):
        self.assertEqual(self.manifest["corners"], ["mos"])
        self.assertEqual(set(self.manifest["temperatures_c"]), {-40, 27, 125})
        self.assertEqual(self.manifest["supply_tolerance"], 0.1)


class OperatingPointIsRuleCompliantMixin:
    """Every band code and release voltage, re-derived from the ratified rule.

    Mix with ``unittest.TestCase`` and set ``TESTBENCH``.
    """

    #: The campaign's ``testbench/`` directory. Set by the subclass.
    TESTBENCH: Path

    TOL_V = 5e-3  # the millivolt rounding tb.json carries

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod = load_module(cls.TESTBENCH / "band_and_vstart_from_vco_record.py")
        cls.manifest = load_manifest(cls.TESTBENCH)
        cls.rows, cls.target = cls.mod.derive_table(cls.manifest)

    def test_the_target_really_is_the_top_of_the_ratified_band(self):
        self.assertAlmostEqual(self.target, TARGET_HZ, delta=1.0)
        self.assertEqual(len(self.rows), 45)

    def test_every_declared_point_matches_the_rule_and_the_vco_record(self):
        declared = self.mod.declared_map(self.manifest)
        for corner, temp, _vdd, alias, band, vstart, _kvco in self.rows:
            self.assertIsNotNone(
                band, "no band reaches 200 MHz at %s/%g C/%s" % (corner, temp, alias)
            )
            got = declared.get((corner, temp, alias))
            self.assertIsNotNone(
                got, "tb.json declares no operating point for %s/%g C/%s"
                % (corner, temp, alias)
            )
            self.assertEqual(
                got[0], band,
                "%s/%g C/%s: tb.json configures band %d, the band-selection rule "
                "selects band %d" % (corner, temp, alias, got[0], band),
            )
            self.assertLess(
                abs(got[1] - vstart), self.TOL_V,
                "%s/%g C/%s: tb.json releases at %.4f V, the VCO record puts "
                "200 MHz at %.4f V in band %d"
                % (corner, temp, alias, got[1], vstart, band),
            )

    def test_no_lower_band_reaches_the_target_at_any_point(self):
        # The rule is "the LOWEST code that reaches f", so this is the half of
        # it that a straight (band, vstart) diff cannot catch: a manifest could
        # agree with the derivation while both had drifted upward together.
        curves = {b: self.mod.load_curves("band%d" % b) for b in self.mod.BAND_CODES}
        for corner, temp, vdd, alias, band, _vstart, _kvco in self.rows:
            for lower in range(band):
                curve = curves[lower].get((corner, temp, vdd))
                if curve is None:
                    continue
                self.assertIsNone(
                    self.mod.interp_vctrl(curve, TARGET_HZ),
                    "%s/%g C/%s runs in band %d, but band %d also reaches "
                    "200 MHz there -- the band-selection rule requires the lower"
                    % (corner, temp, alias, band, lower),
                )

    def test_the_rule_splits_this_grid_across_two_bands(self):
        # Not decoration: at 150 MHz one static code covers all 45 corners,
        # which is why each campaign's 150 MHz sibling could hold its band
        # fixed in `params`. That a band-top campaign cannot is why its band
        # bits are a sweep axis at all, and why it exists as a sibling rather
        # than as more corners over there. If this ever collapsed to one code,
        # that central finding would have changed.
        by_band = {}
        for *_pvt, band, _vstart, _kvco in self.rows:
            by_band[band] = by_band.get(band, 0) + 1
        self.assertEqual(by_band, {6: 34, 7: 11})

    def test_every_selected_point_is_inside_the_kvco_bound(self):
        # spec/pll.md row 17. This is *why* the band-selection rule is
        # normative, so a campaign that claims to follow it must land inside.
        for corner, temp, _vdd, alias, band, _vstart, kvco in self.rows:
            self.assertLessEqual(
                kvco, KVCO_BOUND_HZ_PER_V,
                "%s/%g C/%s band %d: Kvco %.1f MHz/V exceeds spec/pll.md row "
                "17's 150 MHz/V bound"
                % (corner, temp, alias, band, kvco / 1e6),
            )

    def test_emit_reproduces_the_committed_manifest_fragment(self):
        # `--emit` is what generated the manifest; if it no longer reproduces
        # it, the manifest has been hand-edited away from its own generator.
        emitted = self.mod.emit(self.manifest, self.rows, self.target)
        self.assertEqual(
            emitted["sweeps"]["op"]["points"], self.manifest["sweeps"]["op"]["points"]
        )
        self.assertEqual(emitted["grid"], self.manifest["grid"])


class StaticConfigurationEncodesTheClaimedOperatingPointMixin:
    """N = 8 and Icp code 0, spelled in bits rather than asserted in prose.

    Mix with ``unittest.TestCase`` and set ``TESTBENCH``.
    """

    #: The campaign's ``testbench/`` directory. Set by the subclass.
    TESTBENCH: Path

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifest = load_manifest(cls.TESTBENCH)
        cls.params = cls.manifest["params"]

    def test_output_frequency_is_fref_times_n(self):
        fref = float(self.params["fref"])
        n = int(float(self.params["nratio"]))
        self.assertAlmostEqual(fref * n, TARGET_HZ, delta=1.0)
        # f_ref stays at the top of the ratified 1-25 MHz reference range, which
        # is what lets the Icp trim code stay where the 150 MHz sibling has it:
        # the trim code is a function of f_ref, not a free choice.
        self.assertEqual(fref, 25e6)
        self.assertEqual(n, 8)

    def test_divider_bits_encode_that_n(self):
        for key, want in divider_codes(8).items():
            self.assertEqual(self.params[key], want, key)

    def test_icp_trim_is_the_code_the_trim_rule_requires_at_25mhz(self):
        for key, want in TRIM_CODE_AT_25MHZ.items():
            self.assertEqual(self.params[key], want, key)

    def test_lock_checks_bracket_the_claimed_operating_point(self):
        checks = self.manifest["checks"]
        self.assertLess(checks["fout"]["min"], TARGET_HZ)
        self.assertGreater(checks["fout"]["max"], TARGET_HZ)
        self.assertLess(checks["nmeas"]["min"], 8.0)
        self.assertGreater(checks["nmeas"]["max"], 8.0)
