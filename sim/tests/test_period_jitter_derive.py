"""`sim/period-jitter/testbench/derive.py` against waveforms of known jitter.

Pins the crossing-extraction/TIE-de-trending arithmetic `extract_period_jitter`
shares with `sim/vco-tuning-range`'s jitter extraction, off any simulator:

- an unmodulated triangle clock must read back zero jitter (to well under the
  interpolation tolerance the oversampling below gives it), and
- a clock frequency-modulated by a known sinusoid must read back the
  closed-form peak-to-peak period jitter that modulation predicts.

Runs in the harness unit-test suite: no PDK, no ngspice, no network.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "period-jitter" / "testbench"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402


def _load_derive():
    return load_module(TESTBENCH / "derive.py")


class PeriodJitterExtractionMath(unittest.TestCase):
    """`extract_period_jitter()` against an analytically-defined clock."""

    F0 = 150e6
    VSUP = 3.3
    NCYC = 300
    OVERSAMPLE = 400

    @classmethod
    def setUpClass(cls):
        cls.derive = _load_derive()

    def _clock(self, t, phase_of):
        """A triangle clock: linear through the threshold, interpolation-exact."""
        return [self.VSUP * (phase_of(x) % 1.0) for x in t]

    def test_unmodulated_clock_has_no_jitter(self):
        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt)
        t = [i * dt for i in range(n)]
        y = self._clock(t, lambda x: self.F0 * x)
        out = self.derive.extract_period_jitter(t, y, self.VSUP, tmin=0.0)
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out["f_meas_hz"] / self.F0, 1.0, places=6)
        period = 1.0 / self.F0
        self.assertLess(out["tj_pp_s"], 1e-6 * period)
        self.assertLess(out["tie_pp_s"], 1e-6 * period)
        self.assertLess(out["tj_rms_pct"], 1e-4)

    def test_frequency_modulated_clock_reports_the_analytic_tie(self):
        """f(t) = f0 (1 + m sin 2*pi*fr*t)  =>  TIE_pp = m*f0/(pi*fr*f0)."""
        fr = self.F0 / 20
        m = 0.02
        amp = m * self.F0 / (2 * math.pi * fr)

        def phase(x):
            return self.F0 * x - amp * (math.cos(2 * math.pi * fr * x) - 1.0)

        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt)
        t = [i * dt for i in range(n)]
        y = self._clock(t, phase)
        out = self.derive.extract_period_jitter(t, y, self.VSUP, tmin=0.0)
        self.assertIsNotNone(out)

        # Excess phase of amplitude `amp` cycles is a time error of amp/f0
        # peak, so 2*amp/f0 peak-to-peak.
        expected_tie_pp = 2 * amp / self.F0
        self.assertAlmostEqual(
            out["tie_pp_s"] / expected_tie_pp, 1.0, delta=0.05
        )
        self.assertGreater(out["tj_rms_pct"], 0.0)

    def test_too_few_crossings_returns_none(self):
        t = [0.0, 1e-9, 2e-9]
        y = [0.0, 0.1, 0.2]
        self.assertIsNone(
            self.derive.extract_period_jitter(t, y, self.VSUP, tmin=0.0)
        )


if __name__ == "__main__":
    unittest.main()
