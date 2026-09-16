#!/usr/bin/env python3
"""Unit test for `phase_trace.awk` (#395, DR-011 Decision 4).

`sim/supply-sensitivity/testbench/run.sh --one-dyn` extracts a per-REFERENCE-
CYCLE REF->FB phase trace from the closed-loop transient it already simulates
-- see the "--- per-REF-cycle phase trace" block in that file for what it
measures and why. Exercising it end-to-end costs a multi-hour ngspice run (the
whole reason #395 exists), so this test runs the actual awk PROGRAM run.sh
invokes -- not a reimplementation of it -- against a SYNTHETIC trace built
from closed-form ramps, where the crossing instants, the interpolation error
and the phase sign are all known analytically. A bug in the crossing math, the
REF/FB pairing or the aliasing guard is caught here in milliseconds, not hours.

    python3 -m unittest discover -s sim/tests -v

No PDK and no ngspice required.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
AWK_PROGRAM = SIM_DIR / "supply-sensitivity" / "testbench" / "phase_trace.awk"


def run_phase_trace(rows: list[str], vth: float, half_t: float) -> list[list[str]]:
    """Feed synthetic `supply_transient_full.csv` rows through the real awk program.

    `rows` are pre-formatted data lines (ngspice's own `wrdata` column order:
    $1/$2 vctrl, $3/$4 lock, $5/$6 vdd, $7/$8 fb, $9/$10 ref). Returns the
    parsed `t_ref_s,phi_ns,lock_v,vctrl_v,vdd_v` output rows.
    """
    assert AWK_PROGRAM.is_file(), f"{AWK_PROGRAM} not found"
    proc = subprocess.run(
        ["awk", "-v", f"vth={vth!r}", "-v", f"halfT={half_t!r}", "-f", str(AWK_PROGRAM)],
        input="\n".join(rows) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stderr == "", proc.stderr
    return [line.split(",") for line in proc.stdout.splitlines() if line]


def ramp_row(t: float, vctrl: float, lock: float, vdd: float, fb: float, ref: float) -> str:
    """One `supply_transient_full.csv` line at time `t`, all five vectors sampled together."""
    return f"{t:.12g} {vctrl:.9g} {t:.12g} {lock:.9g} {t:.12g} {vdd:.9g} {t:.12g} {fb:.9g} {t:.12g} {ref:.9g}"


class SingleCycleCrossing(unittest.TestCase):
    """One REF cycle, FB lagging by a known, sub-sample skew."""

    # 10 MHz reference, so one period is 100 ns and half a period is 50 ns --
    # comfortably inside the aliasing guard for a skew of a few ns.
    F_REF = 10e6
    PERIOD = 1.0 / F_REF
    VTH = 0.5  # v_lo/2 for a 0/1 V logic swing, matching tb_supply_dyn.sp's own .meas threshold
    HALF_T = 0.5 * PERIOD

    def test_interpolated_crossing_matches_the_closed_form_ramp(self):
        # REF rises linearly from 0 -> 1 V across [0, 1] ns, crossing 0.5 V at
        # exactly t = 0.5 ns. FB is the identical ramp delayed by 2 ns, so it
        # crosses 0.5 V at t = 2.5 ns: a known +2 ns phase (FB lags REF).
        t_ref_cross = 0.5e-9
        t_fb_cross = 2.5e-9
        rows = [
            ramp_row(0.0, 0, 0, 3.3, 0.0, 0.0),
            ramp_row(1e-9, 0, 0, 3.3, 0.0, 1.0),  # REF crosses vth between these two samples
            ramp_row(2e-9, 0, 0, 3.3, 0.0, 1.0),
            ramp_row(3e-9, 0, 0, 3.3, 1.0, 1.0),  # FB crosses vth between these two samples
            ramp_row(3.5e-9, 0, 0, 3.3, 1.0, 1.0),
        ]
        out = run_phase_trace(rows, self.VTH, self.HALF_T)
        self.assertEqual(len(out), 1, out)
        t_ref_s, phi_ns, lock_v, vctrl_v, vdd_v = out[0]
        self.assertAlmostEqual(float(t_ref_s), t_ref_cross, places=12)
        self.assertAlmostEqual(float(phi_ns), (t_fb_cross - t_ref_cross) * 1e9, places=4)
        # Sign convention: FB lagging REF (crossing later) is POSITIVE.
        self.assertGreater(float(phi_ns), 0.0)

    def test_fb_leading_ref_is_negative(self):
        # FB crosses BEFORE ref: a negative phi_ns.
        rows = [
            ramp_row(0.0, 0, 0, 3.3, 0.0, 0.0),
            ramp_row(1e-9, 0, 0, 3.3, 1.0, 0.0),  # FB crosses between these two samples
            ramp_row(2e-9, 0, 0, 3.3, 1.0, 1.0),  # REF crosses between these two samples
            ramp_row(3e-9, 0, 0, 3.3, 1.0, 1.0),
        ]
        out = run_phase_trace(rows, self.VTH, self.HALF_T)
        self.assertEqual(len(out), 1, out)
        self.assertLess(float(out[0][1]), 0.0)

    def test_lock_vctrl_vdd_are_the_uninterpolated_sample_nearest_the_ref_crossing(self):
        # The row straddling the REF crossing carries lock=1, vctrl=1.8, vdd=3.63
        # on its FIRST (pre-crossing) sample -- what the extraction should emit,
        # un-interpolated, per the header contract ("the ngspice sample at the
        # crossing, un-interpolated").
        rows = [
            ramp_row(0.0, 1.8, 1.0, 3.63, 0.0, 0.0),
            ramp_row(1e-9, 1.8, 1.0, 3.63, 0.0, 1.0),
            ramp_row(2e-9, 1.8, 1.0, 3.63, 1.0, 1.0),
            ramp_row(3e-9, 1.8, 1.0, 3.63, 1.0, 1.0),
        ]
        out = run_phase_trace(rows, self.VTH, self.HALF_T)
        self.assertEqual(len(out), 1, out)
        _, _, lock_v, vctrl_v, vdd_v = out[0]
        self.assertAlmostEqual(float(lock_v), 1.0, places=6)
        self.assertAlmostEqual(float(vctrl_v), 1.8, places=6)
        self.assertAlmostEqual(float(vdd_v), 3.63, places=6)


class AliasingGuard(unittest.TestCase):
    """A REF/FB pair further apart than half a reference period is DROPPED, not folded."""

    F_REF = 10e6
    PERIOD = 1.0 / F_REF
    VTH = 0.5
    HALF_T = 0.5 * PERIOD

    def test_a_skew_inside_half_period_is_kept(self):
        # FB lags by 40 ns, inside the 50 ns half-period guard.
        rows = [
            ramp_row(0.0, 0, 0, 3.3, 0.0, 0.0),
            ramp_row(1e-9, 0, 0, 3.3, 0.0, 1.0),
            ramp_row(40.5e-9, 0, 0, 3.3, 0.0, 1.0),
            ramp_row(41.5e-9, 0, 0, 3.3, 1.0, 1.0),
        ]
        out = run_phase_trace(rows, self.VTH, self.HALF_T)
        self.assertEqual(len(out), 1, out)

    def test_a_skew_outside_half_period_is_dropped_not_folded(self):
        # FB lags by 60 ns, OUTSIDE the 50 ns half-period guard: the cycle is
        # dropped entirely rather than reported as a wrapped -40 ns skew.
        rows = [
            ramp_row(0.0, 0, 0, 3.3, 0.0, 0.0),
            ramp_row(1e-9, 0, 0, 3.3, 0.0, 1.0),
            ramp_row(60.5e-9, 0, 0, 3.3, 0.0, 1.0),
            ramp_row(61.5e-9, 0, 0, 3.3, 1.0, 1.0),
        ]
        out = run_phase_trace(rows, self.VTH, self.HALF_T)
        self.assertEqual(out, [], out)


class MultiCycleTrace(unittest.TestCase):
    """Several reference cycles at a fixed, known phase: one row per cycle, no drift."""

    F_REF = 10e6
    PERIOD = 1.0 / F_REF
    VTH = 0.5
    HALF_T = 0.5 * PERIOD
    N_CYCLES = 5
    SKEW_S = 3e-9  # FB lags REF by a fixed 3 ns every cycle

    def _build_rows(self) -> list[str]:
        # Integer step index * exact dt avoids float accumulation drift near
        # the modulo boundary, which a `t += dt` loop can trip (an edge landing
        # a few ULPs on the wrong side of the rise window and being missed).
        dt = 0.2e-9  # sample spacing, fine enough to bracket both edges every cycle
        n_steps = int(round((self.N_CYCLES * self.PERIOD + self.PERIOD) / dt)) + 1
        rows = []
        for k in range(n_steps):
            t = k * dt
            # REF: a 0/1 square-ish ramp with edges at each period boundary,
            # crossing vth exactly halfway through a short (0.4 ns) rise.
            phase_ref = t % self.PERIOD
            ref = min(1.0, max(0.0, phase_ref / 0.4e-9)) if phase_ref < 0.4e-9 else 1.0
            phase_fb = (t - self.SKEW_S) % self.PERIOD
            fb = min(1.0, max(0.0, phase_fb / 0.4e-9)) if phase_fb < 0.4e-9 else 1.0
            rows.append(ramp_row(t, 1.5, 1.0, 3.3, fb, ref))
        return rows

    def test_one_row_per_cycle_at_the_fixed_measured_skew(self):
        out = run_phase_trace(self._build_rows(), self.VTH, self.HALF_T)
        # N_CYCLES full periods are covered by the sweep; each should yield one row.
        self.assertGreaterEqual(len(out), self.N_CYCLES - 1, out)
        for row in out:
            phi_ns = float(row[1])
            # Interpolation error is bounded by the 0.2 ns sample spacing on
            # a 0.4 ns edge; require agreement well inside one sample step.
            self.assertAlmostEqual(phi_ns, self.SKEW_S * 1e9, delta=0.05)

    def test_consecutive_rows_are_one_reference_period_apart(self):
        out = run_phase_trace(self._build_rows(), self.VTH, self.HALF_T)
        times = [float(row[0]) for row in out]
        for a, b in zip(times, times[1:]):
            self.assertAlmostEqual(b - a, self.PERIOD, delta=1e-11)


if __name__ == "__main__":
    unittest.main()
