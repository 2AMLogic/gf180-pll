#!/usr/bin/env python3
"""Unit tests for `trim_msb_audit.py` (issue #515).

That script answers a question no committed artifact answers directly: *which
lock-detector window trim code did the closed loop actually run at*, as
opposed to which one the deck programmed. `design/pll_top.sch` placed the
`LDT3` label off the `XLD` instance's real `LDT3` pin, so the exported
netlist wired that terminal to an xschem auto-named net instead of to the
declared port. The pad could be driven and nothing inside the subcircuit read
it, so the detector saw `code & 0b0111` — and the one committed record that
programmed a code with its MSB set ran eight codes below its own stated
configuration.

Five of the script's judgements are load-bearing enough that a silent bug in
any of them would change a decision record's conclusion, so each is tested
against an input whose right answer is known by construction:

1. **`requested_code`** — the code the deck programmed, assembled from four
   separate `.param ldt<i>_code` lines. A log missing any of the four must
   yield `None` rather than a code with a silently-zero bit, because
   "programmed 0" and "did not program" are different facts.
2. **`node_dc`** — the DC operating point ngspice printed for one named node.
   The evidence for the defect is two nodes in the same table disagreeing, so
   a lookup that matched a prefix or the wrong column would fabricate it.
3. **`msb_reached_the_cell`** — the defect's signature. It must say `unknown`,
   not `no`, when the pad itself is at 0 V: a low pad and a floating net are
   indistinguishable, and reporting that row as evidence of a wiring defect
   would overstate what the log shows.
4. **`predict_assert`** — the ONE-SIDED bound `window_crossing.csv`'s header
   states. `t_win` above the offset predicts an assert; below it the bound
   predicts nothing. Turning the second case into a "predicts no assert"
   would convert a bound into a claim.
5. **`crossing_verdict`** — the source record's own confirmed/refuted/moved
   key, which decides whether DR-013's inference at the affected cell stands.

No PDK, no ngspice, and no committed evidence is read by these tests: every
input is built analytically.

    python3 -m unittest discover -s sim/tests -v
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SIM_DIR / "supply-sensitivity" / "testbench" / "trim_msb_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("trim_msb_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load()


# A miniature of the operating-point block every committed per-corner log
# carries, with the exact shape of the defect in it: the pad at the rail, the
# stray auto-named net at 0 V.
LOG = """\
==== generated deck (f100_ff_27c_3.63v) ====
.param vsup=3.63
.param tstop=12.0u
.param ldt0_code=1
.param ldt1_code=1
.param ldt2_code=0
.param ldt3_code=1

        Node                                   Voltage
        ----                                   -------
        vdd                                       3.63
        ldt2                                         0
        ldt3                                      3.63
        ldt30                                     1.23
        xdut.net1                                    0
"""


class TestRequestedCode(unittest.TestCase):
    def test_all_four_bits_assemble_msb_first(self):
        self.assertEqual(MOD.requested_code(LOG), 0b1011)

    def test_a_missing_bit_is_none_not_a_zero_bit(self):
        partial = "\n".join(
            line for line in LOG.splitlines() if "ldt3_code" not in line
        )
        self.assertIsNone(MOD.requested_code(partial))

    def test_all_bits_low_is_code_zero_not_none(self):
        text = "\n".join(
            ".param ldt%d_code=0" % bit for bit in range(4)
        )
        self.assertEqual(MOD.requested_code(text), 0)

    def test_the_rules_other_code_round_trips(self):
        text = "\n".join(
            ".param ldt%d_code=%d" % (bit, (0b0111 >> bit) & 1) for bit in range(4)
        )
        self.assertEqual(MOD.requested_code(text), 7)


class TestNodeDc(unittest.TestCase):
    def test_reads_the_named_node(self):
        self.assertEqual(MOD.node_dc(LOG, "ldt3"), 3.63)
        self.assertEqual(MOD.node_dc(LOG, "xdut.net1"), 0.0)

    def test_a_longer_node_sharing_a_prefix_is_not_matched(self):
        """`ldt3` must not pick up `ldt30`'s row."""
        self.assertEqual(MOD.node_dc(LOG, "ldt3"), 3.63)
        self.assertEqual(MOD.node_dc(LOG, "ldt30"), 1.23)

    def test_an_absent_node_is_none(self):
        self.assertIsNone(MOD.node_dc(LOG, "xdut.net7"))

    def test_scientific_notation_parses(self):
        self.assertAlmostEqual(
            MOD.node_dc("        lock                               6.949e-09", "lock"),
            6.949e-9,
        )


class TestMsbReachedTheCell(unittest.TestCase):
    def test_the_defect_is_pad_high_stray_low(self):
        self.assertIs(MOD.msb_reached_the_cell(3.63, 0.0), False)

    def test_no_stray_net_at_all_means_the_pad_is_the_terminal(self):
        """The post-fix netlist has no auto-named net to find."""
        self.assertIs(MOD.msb_reached_the_cell(3.63, None), True)

    def test_a_stray_net_tracking_the_pad_is_not_the_defect(self):
        self.assertIs(MOD.msb_reached_the_cell(3.63, 3.63), True)

    def test_a_low_pad_carries_no_evidence_either_way(self):
        """A code with its MSB clear cannot show whether the wire exists."""
        self.assertIsNone(MOD.msb_reached_the_cell(0.0, 0.0))

    def test_no_pad_node_is_unknown(self):
        self.assertIsNone(MOD.msb_reached_the_cell(None, 0.0))


class TestEffectiveCode(unittest.TestCase):
    def test_a_disconnected_msb_drops_exactly_the_top_bit(self):
        self.assertEqual(MOD.effective_code(11, False), 3)
        self.assertEqual(MOD.effective_code(15, False), 7)
        self.assertEqual(MOD.effective_code(8, False), 0)

    def test_a_code_with_its_msb_clear_is_unchanged_by_the_defect(self):
        for code in range(8):
            self.assertEqual(MOD.effective_code(code, False), code)

    def test_a_connected_or_unknown_msb_changes_nothing(self):
        self.assertEqual(MOD.effective_code(11, True), 11)
        self.assertEqual(MOD.effective_code(11, None), 11)

    def test_only_eight_distinct_codes_survive_the_defect(self):
        self.assertEqual(
            len({MOD.effective_code(c, False) for c in range(16)}), 8
        )


class TestAssertedFromLevel(unittest.TestCase):
    def test_the_rail_is_asserted_and_a_nanovolt_is_not(self):
        self.assertTrue(MOD.asserted_from_level(3.63, 3.63))
        self.assertFalse(MOD.asserted_from_level(6.949e-9, 3.63))

    def test_the_threshold_is_run_shs_own_fraction(self):
        vdd = 3.30
        self.assertTrue(MOD.asserted_from_level(MOD.ACC_LOCK_FRAC * vdd, vdd))
        self.assertFalse(MOD.asserted_from_level(MOD.ACC_LOCK_FRAC * vdd - 1e-6, vdd))


class TestPredictAssert(unittest.TestCase):
    def test_a_window_above_the_offset_predicts_an_assert(self):
        self.assertEqual(MOD.predict_assert(1.2801, 1.2331), "assert")

    def test_a_window_below_the_offset_predicts_NOTHING(self):
        """The bound is one-sided: not-above is not the same as no-assert."""
        self.assertEqual(MOD.predict_assert(0.9721, 1.2331), "unpredicted")

    def test_an_absent_window_is_unknown(self):
        self.assertEqual(MOD.predict_assert(None, 1.2331), "unknown")

    def test_the_515_cell_is_exactly_where_the_two_codes_part(self):
        """Code 11 predicts an assert at the cell; code 3 predicts nothing.

        These are the committed `ff`/27 C/3.63 V numbers: t_win 1.2801 ns at
        code 11 and 0.9721 ns at code 3 (fall edges, the conservative half),
        against a settled |phi_b| of 1.2331 ns. The flag did not assert.
        """
        phi = 1.2331
        self.assertEqual(MOD.predict_assert(1.2801, phi), "assert")
        self.assertEqual(MOD.predict_assert(0.9721, phi), "unpredicted")


class TestCrossingVerdict(unittest.TestCase):
    def test_the_four_cases_of_the_source_records_own_key(self):
        self.assertEqual(MOD.crossing_verdict(True, True), "confirmed")
        self.assertEqual(MOD.crossing_verdict(True, False), "refuted")
        self.assertEqual(MOD.crossing_verdict(False, True), "moved")
        self.assertEqual(MOD.crossing_verdict(False, False), "confirmed")

    def test_the_ff_cell_flips_from_confirmed_to_moved_if_it_asserts(self):
        """DR-013 inferred not-crossed there; an assert would be `moved`."""
        self.assertEqual(MOD.crossing_verdict(False, False), "confirmed")
        self.assertEqual(MOD.crossing_verdict(False, True), "moved")


class TestParseLogName(unittest.TestCase):
    def test_the_two_committed_name_shapes(self):
        self.assertEqual(
            MOD.parse_log_name("f100_ff_27c_3.63v.log"),
            {"deck": "f100", "bundle": "ff", "temp_c": "27", "vdd_v": "3.63"},
        )
        self.assertEqual(
            MOD.parse_log_name("f100x_typical_-40c_2.97v.log"),
            {"deck": "f100x", "bundle": "typical", "temp_c": "-40", "vdd_v": "2.97"},
        )

    def test_a_hyphenated_bundle_name_parses(self):
        self.assertEqual(
            MOD.parse_log_name("f100_all-fast_125c_3.30v.log")["bundle"], "all-fast"
        )

    def test_a_non_corner_log_is_none(self):
        self.assertIsNone(MOD.parse_log_name("settling_rerun.log"))


class TestLogTstop(unittest.TestCase):
    def test_reads_the_transient_length(self):
        self.assertEqual(MOD.log_tstop(LOG), "12.0u")

    def test_a_log_without_one_is_blank(self):
        self.assertEqual(MOD.log_tstop("* nothing here\n"), "")


if __name__ == "__main__":
    unittest.main()
