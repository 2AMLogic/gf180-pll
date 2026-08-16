"""Known-answer tests for `sim/reference-spur`'s spectral reduction.

The reference-spur campaign's claim is a **ratio between two lines of a
spectrum**, computed by a reduction this repo wrote itself (`derive.py`:
resample -> Hann window -> DFT at exactly k*f_ref, plus an independent
TIE-based cross-check). That reduction has a specific, dangerous failure mode:
a windowing, resampling or normalisation mistake produces a *plausible-looking*
spur number rather than an obvious error, and nothing downstream would catch
it. A -58 dBc that should have been -64 dBc looks exactly like a real result.

So the reduction is pinned here against waveforms whose spur level is known by
construction: a phase-modulated square wave with a chosen peak phase deviation
theta has first-order sidebands at 20*log10(theta/2) dBc, and that is what the
DFT path and the TIE path must both return. No PDK, no ngspice, no committed
record -- this runs in `sim/selftest.sh` stage 1 with the rest of the harness
unit tests.

What each test pins:

- ``SpurSpectrumKnownAnswer``   the DFT path recovers a synthesised sideband
  over three decades of spur level, on a NON-uniform time grid like the one
  ngspice actually writes.
- ``SpurTiePathKnownAnswer``    the TIE path recovers the same number from the
  same waveform, which is what makes their agreement in a real record
  meaningful rather than circular.
- ``SpurZeroDriftFit``          the zero-drift extrapolation returns the
  settled amplitude from a set of windows that are all contaminated.
- ``SpurWindowing``             the window list a manifest's wa/wb/wcyc
  describes, since an off-by-one there silently moves the measurement window.
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
TESTBENCH = SIM_DIR / "reference-spur" / "testbench"

sys.path.insert(0, str(SIM_DIR))


def _load_derive():
    spec = importlib.util.spec_from_file_location(
        "_reference_spur_derive_under_test", TESTBENCH / "derive.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = _load_derive()

F_REF = 25e6
N = 6
F_OUT = N * F_REF
VDD = 3.3


def pm_square(theta, t_end, jitter_seed=1, edge_s=3e-10, dt_mean=7.5e-11):
    """A phase-modulated square wave on a NON-uniform time grid.

    ``theta`` is the peak phase deviation in radians at ``F_OUT``, modulated at
    ``F_REF`` -- exactly the shape a reference spur has -- so the first-order
    sidebands sit at ``20*log10(theta/2)`` dBc by construction.

    The sample grid is deliberately irregular (jittered around ``dt_mean``,
    which is the ~75 ps mean internal step this DUT actually runs at under the
    100 ps ceiling), because that is the one property of ngspice's output that
    makes a DFT non-trivial here. A reduction that assumed uniform sampling
    would pass a uniform-grid test and be wrong on every real record.

    The waveform is a trapezoid with a finite edge (``edge_s``), like the real
    output buffer's, so the spectrum has genuine harmonics for the reduction to
    not confuse with the sideband.
    """
    rng = random.Random(jitter_seed)
    ts = []
    t = 0.0
    while t < t_end:
        ts.append(t)
        t += dt_mean * (0.4 + 1.2 * rng.random())
    ys = []
    for t in ts:
        # Instantaneous phase: linear ramp plus the F_REF phase modulation.
        phase = 2.0 * math.pi * F_OUT * t + theta * math.sin(2.0 * math.pi * F_REF * t)
        # Trapezoidal square wave of that phase, edges edge_s wide.
        frac = (phase / (2.0 * math.pi)) % 1.0
        edge_frac = edge_s * F_OUT
        if frac < edge_frac:
            v = frac / edge_frac
        elif frac < 0.5:
            v = 1.0
        elif frac < 0.5 + edge_frac:
            v = 1.0 - (frac - 0.5) / edge_frac
        else:
            v = 0.0
        ys.append(v * VDD)
    return ts, ys


class SpurSpectrumKnownAnswer(unittest.TestCase):
    """The DFT path returns the sideband level the waveform was built with."""

    def test_recovers_synthesised_spur(self):
        # theta values chosen to bracket the region this campaign lives in:
        # -55 dBc is the spec line and -61 dBc the derived estimate this
        # measurement is checked against. Levels below the reconstruction
        # floor pinned by test_clean_carrier_has_no_sideband are not claimed
        # to be recoverable and are not tested here.
        for want_dbc in (-45.0, -55.0, -61.0, -65.0):
            theta = 2.0 * (10.0 ** (want_dbc / 20.0))
            t, y = pm_square(theta, 1.4e-6)
            amps = D.harmonic_amplitudes(t, y, F_REF, 1.0e-7, 1.0e-7 + 16 / F_REF)
            self.assertIsNotNone(amps)
            carrier = amps[N]
            lsb = 20.0 * math.log10(amps[N - 1] / carrier)
            usb = 20.0 * math.log10(amps[N + 1] / carrier)
            self.assertAlmostEqual(lsb, want_dbc, delta=1.0, msg=f"lsb @ {want_dbc}")
            self.assertAlmostEqual(usb, want_dbc, delta=1.0, msg=f"usb @ {want_dbc}")

    def test_carrier_amplitude_is_volts(self):
        """The carrier comes back in volts, not in DFT units.

        A missing window-gain or 2/N normalisation cancels in the RATIO the
        spur is, so it would never show up in the spur number -- but the record
        also reports `carrier_v`, and a reader comparing it against the 3.3 V
        rail is entitled to a real voltage. A square wave's fundamental is
        (2/pi)*Vpp ~ 2.10 V at 3.3 V.
        """
        t, y = pm_square(0.0, 1.4e-6)
        amps = D.harmonic_amplitudes(t, y, F_REF, 1.0e-7, 1.0e-7 + 16 / F_REF)
        self.assertAlmostEqual(amps[N], 2.0 * VDD / math.pi, delta=0.06)

    def test_clean_carrier_has_no_sideband(self):
        """An unmodulated carrier must not manufacture a sideband.

        This is the test that pins the reduction's own noise floor: with no
        modulation at all, any energy at f_out +/- f_ref is an artefact of the
        window or of the resampling, and it bounds how far below the spec line
        a measured spur can be believed.

        The waveform here is deliberately the WORST case -- an ideal trapezoid
        (discontinuous slope at all four corners) on a uniformly random time
        grid. A real ngspice output has smooth, RC-shaped edges and an adaptive
        step that clusters samples *into* the transitions, both of which make
        reconstruction easier. The measured floor on this harsh input is about
        -84 dBc with the cubic resampler (it was -74 dBc with a linear one,
        which is why the resampler is cubic): ~23 dB below the -61 dBc the
        spec's derivation predicts, so a real measurement anywhere near that
        level is not floor-limited.
        """
        t, y = pm_square(0.0, 1.4e-6)
        amps = D.harmonic_amplitudes(t, y, F_REF, 1.0e-7, 1.0e-7 + 16 / F_REF)
        floor = 20.0 * math.log10(max(amps[N - 1], amps[N + 1]) / amps[N])
        self.assertLess(floor, -82.0, "spectral floor is too high to trust -60 dBc")


class SpurTiePathKnownAnswer(unittest.TestCase):
    """The TIE cross-check returns the same level, by different arithmetic."""

    def test_tie_matches_construction(self):
        for want_dbc in (-45.0, -55.0, -61.0):
            theta = 2.0 * (10.0 ** (want_dbc / 20.0))
            t, y = pm_square(theta, 1.4e-6)
            t0 = 1.0e-7
            t1 = t0 + 16 / F_REF
            cross = D.rising_crossings(t, y, VDD / 2.0, t0, t1)
            tie, period = D.tie_sequence(cross)
            self.assertTrue(tie, "no TIE sequence extracted")
            amp_s = D.tie_component(tie, cross, F_REF)
            got = 20.0 * math.log10(2.0 * math.pi * (1.0 / period) * amp_s / 2.0)
            self.assertAlmostEqual(got, want_dbc, delta=1.0, msg=f"tie @ {want_dbc}")

    def test_tie_removes_a_frequency_ramp(self):
        """A still-settling loop must not read as jitter.

        The TIE is de-trended by its own best-fit ramp precisely so a residual
        frequency offset does not leak into every bin. A 1e-4 fractional
        frequency error is well inside this campaign's own lock criterion, and
        it must not move the reported spur.
        """
        theta = 2.0 * (10.0 ** (-61.0 / 20.0))
        t, y = pm_square(theta, 1.4e-6)
        t0, t1 = 1.0e-7, 1.0e-7 + 16 / F_REF
        cross = D.rising_crossings(t, y, VDD / 2.0, t0, t1)
        skewed = [c * (1.0 + 1e-4) for c in cross]
        tie, period = D.tie_sequence(skewed)
        amp_s = D.tie_component(tie, skewed, F_REF)
        got = 20.0 * math.log10(2.0 * math.pi * (1.0 / period) * amp_s / 2.0)
        self.assertAlmostEqual(got, -61.0, delta=1.0)


class SpurZeroDriftFit(unittest.TestCase):
    """The zero-drift extrapolation recovers a settled amplitude."""

    def test_intercept_is_the_settled_value(self):
        settled = 9.0e-4          # the sideband ratio with no residual drift
        per_fc = 3.0e-4           # ratio added per fC of residual drift charge
        drifts = [2.5, 1.9, 1.5, 1.1, 0.9, 0.7]
        ratios = [settled + per_fc * q for q in drifts]
        slope, intercept, r2 = D.linfit(drifts, ratios)
        self.assertAlmostEqual(intercept, settled, delta=1e-6)
        self.assertAlmostEqual(slope, per_fc, delta=1e-6)
        self.assertGreater(r2, 0.999)

    def test_fit_reports_a_bad_model(self):
        """r2 has to fall when the linear model does not hold."""
        drifts = [2.5, 1.9, 1.5, 1.1, 0.9, 0.7]
        ratios = [9e-4 + 3e-4 * (q ** 3) for q in drifts]
        _, _, r2 = D.linfit(drifts, [r * (1 + 0.4 * math.sin(9 * r)) for r in ratios])
        self.assertLess(r2, 0.999)


class SpurWindowing(unittest.TestCase):
    """The window list is exactly what the manifest's wa/wb/wcyc describe."""

    def test_window_bounds(self):
        params = {"fref": "25e6", "wa": "2.04e-6", "wb": "6.92e-6", "wcyc": "16"}
        wins = D.window_bounds(params)
        self.assertEqual(len(wins), 7)
        self.assertAlmostEqual(wins[0][0], 2.04e-6, places=12)
        # Every window is an exact integer number of reference periods -- the
        # property the coherent DFT depends on.
        for t0, t1 in wins:
            cycles = (t1 - t0) * 25e6
            self.assertAlmostEqual(cycles, 16.0, places=6)
        # Contiguous, and inside the declared span.
        for i in range(1, len(wins)):
            self.assertAlmostEqual(wins[i][0], wins[i - 1][1], places=12)
        self.assertLessEqual(wins[-1][1], 6.92e-6 + 1e-15)

    def test_window_bounds_are_committed_manifest_values(self):
        """The manifest this test pins is the one the record is minted from."""
        import json

        manifest = json.loads((TESTBENCH / "tb.json").read_text())
        params = manifest["params"]
        wins = D.window_bounds(params)
        self.assertGreaterEqual(len(wins), 3, "too few windows for the drift fit")
        self.assertLessEqual(
            wins[-1][1], float(params["ktstop"]) + 1e-15,
            "the last spectral window ends after the transient does",
        )
        self.assertGreaterEqual(
            wins[0][0], float(params["ktstart"]),
            "the first spectral window starts before the deck stores any output",
        )


if __name__ == "__main__":
    unittest.main()
