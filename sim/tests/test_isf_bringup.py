"""`sim/period-jitter/isf-bringup` -- deck derivation and reduction, off ngspice.

Two things are pinned here, both of which fail silently in simulation if they
break:

1. **The port-widened wrappers really are the committed ring.**
   `isf_deck.derive_wrappers()` promotes `vco`'s and `vco_stage`'s internal
   nodes to ports so charge can be injected into them.  If a schematic change
   reorders those port lists, or adds/removes a stage, the derivation would
   quietly wire the injection to the wrong net and every Gamma number after it
   would be wrong while looking perfectly healthy.  So the derivation asserts
   loudly on drift, and this test pins that it does -- and that it changes
   nothing else: every device line of the wrappers must be byte-identical to
   the committed `design/netlist/vco.spice`.

2. **The reduction recovers a phase shift it is given.**
   `isf_extract` turns two crossing sequences into `h = dphi/dq`.  Replaying a
   synthetic clock whose phase is stepped by a known amount at a known time
   exercises the whole path -- crossing interpolation, settled-tail selection,
   drift rejection, the sign convention -- against an answer known in closed
   form, before any simulator output is trusted.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO = SIM_DIR.parent
ISF = SIM_DIR / "period-jitter" / "isf-bringup"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

_deck = load_module(ISF / "isf_deck.py")
_extract = load_module(ISF / "isf_extract.py")


class WrapperDerivation(unittest.TestCase):
    """`derive_wrappers()` against the committed VCO netlist."""

    @classmethod
    def setUpClass(cls):
        cls.src = _deck.read_vco_netlist(REPO)
        cls.wrappers = _deck.derive_wrappers(cls.src)

    def test_stage_wrapper_exposes_head_and_tail_nodes(self):
        self.assertIn(
            ".subckt vco_stage_isf A Y VDD VSS VBP VBN NH NT", self.wrappers
        )

    def test_vco_wrapper_exposes_all_fifteen_internal_nodes(self):
        hdr = next(
            ln for ln in self.wrappers.splitlines()
            if ln.startswith(".subckt vco_isf ")
        )
        ports = hdr.split()[2:]
        self.assertEqual(
            ports[:7], ["VCTRL", "B0", "B1", "B2", "CLK", "VDD_VCO", "GND_VCO"]
        )
        self.assertEqual(
            ports[7:],
            [f"Y{s}" for s in range(1, 6)]
            + [f"NH{s}" for s in range(1, 6)]
            + [f"NT{s}" for s in range(1, 6)],
        )

    def test_all_five_stages_are_repointed(self):
        stages = [
            ln for ln in self.wrappers.splitlines()
            if ln.startswith("XS") and ln.endswith("vco_stage_isf")
        ]
        self.assertEqual(len(stages), 5)
        for s, ln in enumerate(stages, start=1):
            self.assertTrue(ln.endswith(f"NH{s} NT{s} vco_stage_isf"), ln)

    def test_no_device_line_is_rewritten(self):
        """Every non-.subckt, non-XS line must be the committed netlist's own.

        This is the guard that matters: the wrappers are a PORT-WIDENING, so if
        a single `W=`, `L=`, `m=` or net name differed from the committed
        netlist the bring-up would be measuring a different ring than the one
        `sim/period-jitter` measures.
        """
        committed = set(
            ln.rstrip() for ln in self.src.splitlines() if ln.strip()
        )
        for ln in self.wrappers.splitlines():
            s = ln.rstrip()
            if not s or s.startswith(".subckt") or s.startswith("XS"):
                continue
            self.assertIn(s, committed, f"wrapper line not in vco.spice: {s!r}")

    def test_drifted_stage_port_list_raises(self):
        drifted = self.src.replace(
            ".subckt vco_stage A Y VDD VSS VBP VBN",
            ".subckt vco_stage A Y VDD VSS VBN VBP",
        )
        with self.assertRaises(ValueError):
            _deck.derive_wrappers(drifted)

    def test_drifted_vco_port_list_raises(self):
        drifted = self.src.replace(
            ".subckt vco VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO",
            ".subckt vco VCTRL B0 B1 B2 VDD_VCO GND_VCO CLK",
        )
        with self.assertRaises(ValueError):
            _deck.derive_wrappers(drifted)

    def test_removed_stage_raises(self):
        drifted = self.src.replace(
            "XS5 Y4 Y5 VDD_VCO GND_VCO VBP VBN vco_stage\n", ""
        )
        with self.assertRaises(ValueError):
            _deck.derive_wrappers(drifted)


class DeckAssembly(unittest.TestCase):
    """`build_deck()` structure, without running anything."""

    @classmethod
    def setUpClass(cls):
        cls.src = _deck.read_vco_netlist(REPO)

    def _build(self, **kw):
        base = dict(
            repo_root=REPO,
            pdk_models=Path("/nonexistent/models"),
            ncopy=3,
            tstop=1e-7,
            tstep=2e-12,
            tmax=2e-12,
            vctrl=1.795,
            src=self.src,
        )
        base.update(kw)
        return _deck.build_deck(**base)

    def test_reference_copy_carries_no_injection(self):
        deck = self._build(
            injections=[(1, "Y", 1, 4e-8, 2e-15, 1e-11)]
        )
        self.assertIn("iinj1 0 y1_1 pulse(", deck)
        self.assertNotIn("iinj0", deck)

    def test_injecting_into_copy_zero_is_refused(self):
        with self.assertRaises(ValueError):
            self._build(injections=[(0, "Y", 1, 4e-8, 2e-15, 1e-11)])

    def test_two_injections_into_one_copy_is_refused(self):
        with self.assertRaises(ValueError):
            self._build(
                injections=[
                    (1, "Y", 1, 4e-8, 2e-15, 1e-11),
                    (1, "NT", 1, 4e-8, 2e-15, 1e-11),
                ]
            )

    def test_unknown_node_class_is_refused(self):
        with self.assertRaises(ValueError):
            _deck.injection_net("VBP", 1, 1)

    def test_injected_amplitude_is_charge_over_width(self):
        deck = self._build(injections=[(2, "NT", 3, 4e-8, 4e-15, 1e-11)])
        line = next(ln for ln in deck.splitlines() if ln.startswith("iinj2"))
        self.assertIn("nt2_3", line)
        amp = float(line.split("pulse(0 ")[1].split()[0])
        self.assertAlmostEqual(amp, 4e-15 / 1e-11, places=12)

    def test_a_node_pair_injects_between_the_two_nets(self):
        """A two-terminal generator must be an element ACROSS drain and source.

        The element's first net is the drain and its second the source, so
        positive current leaves the drain and enters the source -- which is the
        direction a MOSFET's channel generator drives.  A `0 <net>` element
        instead of a `<net> <net>` one would silently measure the single-node
        ISF while being reported as the differential one.
        """
        deck = self._build(injections=[(1, ("Y", "NT"), 3, 4e-8, 4e-14, 1e-11)])
        line = next(ln for ln in deck.splitlines() if ln.startswith("iinj1"))
        self.assertEqual(line.split()[1:3], ["y1_3", "nt1_3"])
        amp = float(line.split("pulse(0 ")[1].split()[0])
        self.assertAlmostEqual(amp, 4e-14 / 1e-11, places=9)
        self.assertIn(" 4.00000000e-08 ", line)

    def test_a_node_pair_with_an_unknown_class_is_refused(self):
        with self.assertRaises(ValueError):
            self._build(injections=[(1, ("Y", "VBN"), 1, 4e-8, 1e-15, 1e-11)])

    def test_every_copy_gets_the_same_initial_condition(self):
        deck = self._build(ncopy=3, injections=())
        ics = [ln for ln in deck.splitlines() if ln.startswith(".ic ")]
        self.assertEqual(len(ics), 3)
        shapes = {
            " ".join(tok.split(")=")[1] for tok in ln.split()[1:]) for ln in ics
        }
        self.assertEqual(len(shapes), 1, ics)


class ReductionMath(unittest.TestCase):
    """`isf_extract` against a clock whose phase step is known in closed form."""

    F0 = 150e6
    VSUP = 3.3
    OVERSAMPLE = 500
    NCYC = 40

    def _clock(self, shift_at, shift_s, tau_s=0.0, kick_s=0.0):
        """A triangle clock, delayed by `shift_s` for t > `shift_at`.

        `kick_s`/`tau_s` optionally add a decaying extra delay on top, standing
        in for the amplitude transient a real oscillator shows for a cycle or
        two after an impulse -- what `settle_cycles` exists to discard.

        The delay is continuous at `shift_at` (it rises over 1 % of a cycle
        rather than stepping): a discontinuous phase step in a SYNTHETIC
        waveform manufactures an extra threshold crossing out of the jump
        itself, which is a defect of the fixture, not of the reduction.
        """
        dt = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt)
        tau_rise = 0.01 / self.F0
        t, y = [], []
        for i in range(n):
            x = i * dt
            d = 0.0
            if x > shift_at:
                u = x - shift_at
                d = shift_s
                if tau_s > 0.0:
                    d += kick_s * math.exp(-u / tau_s)
                d -= (shift_s + kick_s) * math.exp(-u / tau_rise)
            y.append(self.VSUP * (((x - d) * self.F0) % 1.0))
            t.append(x)
        return t, y

    def test_recovers_a_known_phase_step(self):
        shift = 12.0e-12
        t, y0 = self._clock(0.0, 0.0)
        _, y1 = self._clock(1e-7, shift)
        c0 = _extract.crossings(t, y0, self.VSUP / 2)
        c1 = _extract.crossings(t, y1, self.VSUP / 2)
        dts = _extract.shift_sequence(c0, c1)
        dt, spread, n, drift = _extract.settled_shift(dts, c0, 1e-7)
        self.assertAlmostEqual(dt, shift, delta=0.02e-12)
        self.assertLess(spread, 0.02e-12)
        self.assertLess(abs(drift), 1e-15)
        self.assertGreater(n, 5)

    def test_discards_the_post_impulse_amplitude_transient(self):
        """A decaying kick must not bias the asymptotic shift."""
        shift = 12.0e-12
        t, y0 = self._clock(0.0, 0.0)
        _, y1 = self._clock(1e-7, shift, tau_s=1.5 / self.F0, kick_s=40e-12)
        c0 = _extract.crossings(t, y0, self.VSUP / 2)
        c1 = _extract.crossings(t, y1, self.VSUP / 2)
        dts = _extract.shift_sequence(c0, c1)
        loose, _, _, _ = _extract.settled_shift(dts, c0, 1e-7, settle_cycles=0)
        tight, _, _, _ = _extract.settled_shift(dts, c0, 1e-7, settle_cycles=6)
        self.assertGreater(abs(loose - shift), 1e-12)
        self.assertAlmostEqual(tight, shift, delta=0.15e-12)

    def test_a_frequency_shift_is_reported_as_drift_not_as_a_phase_step(self):
        """An impulse that changes the FREQUENCY is not a phase shift.

        The ISF formalism assumes an impulse perturbs phase only.  A response
        that keeps accumulating is outside it, and the reduction must surface
        that as non-zero drift rather than average it into a number.
        """
        dt_s = 1.0 / (self.F0 * self.OVERSAMPLE)
        n = int(self.NCYC / self.F0 / dt_s)
        t, y0, y1 = [], [], []
        for i in range(n):
            x = i * dt_s
            d = 0.0 if x <= 1e-7 else 2e-5 * (x - 1e-7)
            t.append(x)
            y0.append(self.VSUP * ((x * self.F0) % 1.0))
            y1.append(self.VSUP * (((x - d) * self.F0) % 1.0))
        c0 = _extract.crossings(t, y0, self.VSUP / 2)
        c1 = _extract.crossings(t, y1, self.VSUP / 2)
        dts = _extract.shift_sequence(c0, c1)
        _, _, _, drift = _extract.settled_shift(dts, c0, 1e-7)
        self.assertGreater(abs(drift), 1e-13)

    def test_sign_convention_a_later_edge_is_a_phase_lag(self):
        h = _extract.sensitivity(dt=10e-12, period=1 / self.F0, dq=2e-15)
        self.assertLess(h, 0.0)
        self.assertAlmostEqual(
            h, -2 * math.pi * 10e-12 * self.F0 / 2e-15, delta=1.0
        )

    def test_sensitivity_is_charge_normalised(self):
        a = _extract.sensitivity(10e-12, 1 / self.F0, 2e-15)
        b = _extract.sensitivity(40e-12, 1 / self.F0, 8e-15)
        self.assertAlmostEqual(a, b, delta=abs(a) * 1e-12)

    def test_crossing_count_mismatch_is_refused(self):
        """A lost or gained edge must not be silently truncated past."""
        with self.assertRaises(ValueError):
            _extract.shift_sequence([1.0, 2.0, 3.0], [1.0, 2.0])

    def test_too_short_a_tail_is_an_error_not_a_number(self):
        t, y0 = self._clock(0.0, 0.0)
        _, y1 = self._clock(self.NCYC / self.F0 * 0.98, 5e-12)
        c0 = _extract.crossings(t, y0, self.VSUP / 2)
        c1 = _extract.crossings(t, y1, self.VSUP / 2)
        dts = _extract.shift_sequence(c0, c1)
        with self.assertRaises(ValueError):
            _extract.settled_shift(dts, c0, self.NCYC / self.F0 * 0.98)


class DifferentialReduction(unittest.TestCase):
    """`node_differences` / `crosscheck_pairs`, on hand-built rows.

    These two carry the bring-up's sharpest claim -- that the ISF weighting a
    device's channel noise is a small residue of two large single-node ISFs --
    so the arithmetic that produces the residue, its numerical floor and its
    cross-check is pinned here off any simulator.
    """

    T = 6.668688e-9

    def _row(self, node, phase, h, dq=1e-15, spread=1e-14):
        """A row whose `dt_s` is exactly consistent with the `h` asked for."""
        return {
            "node": node,
            "stage": 1,
            "phase_cycles": phase,
            "dq_C": dq,
            "dt_s": -h * self.T * dq / (2 * math.pi),
            "dt_spread_s": spread,
            "dt_drift_s_per_cycle": 0.0,
            "n_settled": 10,
            "h_rad_per_C": h,
        }

    def test_generator_isf_is_source_minus_drain(self):
        """`h_gen = h(source) - h(drain)`, not the other way round.

        A generator current of +1 A leaves the drain and enters the source.  Only
        `h_gen**2` reaches the jitter sum, so this sign changes no result -- but
        it decides whether the direct and subtracted constructions are comparable
        at all, and having it backwards showed up as a ~200 % signed disagreement
        against a ~0 % magnitude disagreement.
        """
        rows = [
            self._row("Y", 0.0, 1.6e13),
            self._row("NT", 0.0, 1.5e13),
        ]
        (d,) = _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))
        self.assertAlmostEqual(d["h_gen_rad_per_C"], -1.0e12, delta=1.0)
        self.assertAlmostEqual(d["h_drain_rad_per_C"], 1.6e13, delta=1.0)
        self.assertAlmostEqual(d["h_source_rad_per_C"], 1.5e13, delta=1.0)
        # |1e12| of 1.6e13 -- the cancellation the pipeline pays for.
        self.assertAlmostEqual(d["cancellation_ratio"], -1.0 / 16.0, places=6)
        # floor = 2*pi*(spread_a + spread_b)/(T*dq), both spreads 10 fs
        self.assertAlmostEqual(
            d["floor_rad_per_C"],
            2 * math.pi * 2e-14 / (self.T * 1e-15),
            delta=1.0,
        )
        self.assertGreater(d["snr"], 1.0)

    def test_differencing_unequal_charges_is_refused(self):
        rows = [
            self._row("Y", 0.0, 1.6e13, dq=1e-15),
            self._row("NT", 0.0, 1.5e13, dq=2e-15),
        ]
        with self.assertRaises(ValueError):
            _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))

    def test_pair_rows_are_not_themselves_differenced(self):
        """A `Y-NT` row is a measurement, not a node -- it must not be paired."""
        rows = [
            self._row("Y", 0.0, 1.6e13),
            self._row("NT", 0.0, 1.5e13),
            self._row("Y-NT", 0.0, 1.0e12),
        ]
        diffs = _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))
        self.assertEqual(len(diffs), 1)

    def test_crosscheck_compares_direct_against_subtracted(self):
        rows = [
            self._row("Y", 0.0, 1.6e13),
            self._row("NT", 0.0, 1.5e13),
            self._row("Y-NT", 0.0, -1.02e12, dq=2e-14),
        ]
        diffs = _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))
        (c,) = _extract.crosscheck_pairs(rows, diffs, (("Y", "NT"),))
        self.assertAlmostEqual(c["h_direct_rad_per_C"], -1.02e12, delta=1.0)
        self.assertAlmostEqual(c["h_subtracted_rad_per_C"], -1.0e12, delta=1.0)
        self.assertAlmostEqual(c["rel_disagreement"], 0.02 / 1.02, places=6)
        self.assertAlmostEqual(
            c["rel_disagreement_magnitude"], 0.02 / 1.02, places=6
        )
        self.assertEqual(c["h_direct_dq_C"], 2e-14)
        self.assertEqual(c["h_subtracted_dq_C"], 1e-15)

    def test_a_sign_flip_reads_as_200_percent_signed_and_0_percent_magnitude(self):
        """The signature the cross-check exists to make unmistakable."""
        rows = [
            self._row("Y", 0.0, 1.6e13),
            self._row("NT", 0.0, 1.5e13),
            self._row("Y-NT", 0.0, +1.0e12, dq=2e-14),   # correct magnitude, wrong sign
        ]
        diffs = _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))
        (c,) = _extract.crosscheck_pairs(rows, diffs, (("Y", "NT"),))
        self.assertAlmostEqual(c["rel_disagreement"], 2.0, places=6)
        self.assertAlmostEqual(c["rel_disagreement_magnitude"], 0.0, places=9)

    def test_crosscheck_is_silent_when_no_pair_was_injected(self):
        rows = [self._row("Y", 0.0, 1.6e13), self._row("NT", 0.0, 1.5e13)]
        diffs = _extract.node_differences(rows, self.T, pairs=(("Y", "NT"),))
        self.assertEqual(_extract.crosscheck_pairs(rows, diffs, (("Y", "NT"),)), [])


class SweepReferenceColumn(unittest.TestCase):
    """`summarize.section_sweep` must compare against the LIMIT, not column -1.

    Both sweeps in this bring-up approach their limit at the smallest swept
    value.  The timestep sweep's runs descend, so the last column is the limit;
    the linearity sweep's ascend, so the last column is the value furthest FROM
    it.  A positional reference therefore reports the linearity spread against
    the least linear charge in the set -- a defect that inverts the reading of
    the table rather than perturbing it, and that this test exists to prevent
    coming back.
    """

    @classmethod
    def setUpClass(cls):
        cls.sm = load_module(ISF / "summarize.py")

    def _res(self, key, values, h_of):
        return {
            "runs": [
                {
                    key: v,
                    "elapsed_s": 1.0,
                    "rows": [
                        {"phase_cycles": 0.0, "h_rad_per_C": h_of(v)},
                    ],
                }
                for v in values
            ]
        }

    def test_ascending_sweep_is_referenced_to_its_smallest_value(self):
        # h -> 1.0e13 as dq -> 0; 2.0e13 at the largest charge.
        res = self._res(
            "dq_C", [0.5e-15, 1e-15, 2e-15], lambda v: 1.0e13 * (1 + v / 2e-15)
        )
        out = []
        self.sm.section_sweep(
            res, out, title="t", key="dq_C",
            keyfmt=lambda x: f"{x * 1e15:g} fC", colname="charge", blurb="b",
        )
        text = "\n".join(out)
        self.assertIn("worst dev. vs. 0.5 fC", text)
        # 2 fC is 2.0e13 against 1.25e13 at 0.5 fC -> 60 %, not 37.5 %
        self.assertIn("60.00 %", text)

    def test_descending_sweep_is_referenced_to_its_smallest_value_too(self):
        res = self._res(
            "tmax_s", [8e-12, 4e-12, 2e-12], lambda v: 1.0e13 * (1 + v / 8e-12)
        )
        out = []
        self.sm.section_sweep(
            res, out, title="t", key="tmax_s",
            keyfmt=lambda x: f"{x * 1e12:g} ps", colname="ceiling", blurb="b",
        )
        text = "\n".join(out)
        self.assertIn("worst dev. vs. 2 ps", text)

    def test_the_last_step_towards_the_limit_is_reported_separately(self):
        """A sweep can span badly and still be converged at the limit."""
        res = self._res(
            "dq_C",
            [1e-15, 2e-15, 8e-15],
            lambda v: 1.0e13 if v <= 2e-15 else 5.0e13,
        )
        out = []
        self.sm.section_sweep(
            res, out, title="t", key="dq_C",
            keyfmt=lambda x: f"{x * 1e15:g} fC", colname="charge", blurb="b",
        )
        text = "\n".join(out)
        self.assertIn("worst dev. vs. 1 fC", text)
        self.assertIn("400.00 %", text)       # the span
        self.assertIn("the two smallest charges): 0.00 %", text)  # the limit


if __name__ == "__main__":
    unittest.main()
