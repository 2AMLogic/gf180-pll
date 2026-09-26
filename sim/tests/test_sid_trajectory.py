"""`sim/period-jitter/sid-trajectory` -- deck derivation and reduction, off ngspice.

Four things are pinned here, all of which fail silently in simulation if they
break -- which is the criterion for being in this file at all.

1. **The standalone noise deck instantiates the COMMITTED ring device.**
   `sid_deck.device_line()` lifts the instance's model name and its whole
   parameter text out of `design/netlist/vco.spice`, because the drawn
   `ad`/`as`/`pd`/`ps` set the junction geometry, `nrd`/`nrs` set the
   terminal-resistance noise generators and `sa`/`sb`/`sd` set the stress
   corrections to the channel ones.  A hand-written `nfet_03v3 W=2u L=0.28u`
   would measure a different device than the ring contains, and every `S_id` in
   the table would be wrong while looking perfectly healthy.  So the derivation
   asserts loudly on drift, and this test pins that it does.

2. **The `save` card is emitted, and names every extra column.**
   An `@m...[vgs]` expression that appears only on `wrdata` comes back FROZEN at
   its DC value for every timepoint: the column varies not at all, the run exits
   0, and nothing announces it.  The whole trajectory ingredient would be a table
   of DC operating points.

3. **The reduction's absolute anchors are right.**  `units_anchor` is the check
   that catches an analysis band that is not 1 Hz wide, and it is only a check if
   its own closed form is right; `extract_sid` divides by a measured
   transimpedance; `noise_conductance` and `series_resistance` are inverted from
   closed forms.  Each is replayed here against numbers computed by hand.

4. **The stage shift is `1/(2N) + 1/2`, and the scan finds it.**  Comparing the
   five stages at `1/N` puts nearly-antiphase waveforms against each other and
   returns a ~100 % residual that reads exactly like a ring whose stages are not
   replicas.  This test replays a synthetic five-stage ring whose shift is known
   and asserts the scan recovers it.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO = SIM_DIR.parent
SID = SIM_DIR / "period-jitter" / "sid-trajectory"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

_deck = load_module(SID / "sid_deck.py")
_extract = load_module(SID / "sid_extract.py")


class DeviceLineDerivation(unittest.TestCase):
    """`stage_device_lines()` / `device_line()` against the committed netlist."""

    @classmethod
    def setUpClass(cls):
        cls.src = _deck.isf_deck.read_vco_netlist(REPO)
        cls.devs = _deck.stage_device_lines(cls.src)

    def test_the_four_ring_devices_are_found(self):
        self.assertEqual(set(self.devs), set(_deck.RING_DEVICES))

    def test_every_device_line_is_the_committed_netlists_own_text(self):
        """Not a transcription: each instance's line must appear in the source."""
        folded = _deck._join_continuations(self.src)
        for inst, dev in self.devs.items():
            with self.subTest(inst=inst):
                self.assertIn(dev["line"], [ln.strip() for ln in folded])

    def test_device_line_keeps_the_geometry_and_changes_only_the_nodes(self):
        line = _deck.device_line(self.src, "XMN", name="xm1",
                                 nodes=("d", "g", "0", "b"))
        self.assertTrue(line.startswith("xm1 d g 0 b nfet_03v3 "))
        # The drawn parameters that set the noise generators must survive.
        for token in ("L=0.28u", "W=2u", "nrd=", "nrs=", "sa=0", "sb=0", "sd=0"):
            self.assertIn(token, line)
        self.assertIn(self.devs["XMN"]["params"], line)

    def test_a_changed_instance_set_is_refused_rather_than_partially_matched(self):
        """Dropping a device must raise, not characterise three and call it the ring."""
        mangled = self.src.replace("XMNT NT VBN VSS VSS nfet_03v3",
                                   "XZZZ NT VBN VSS VSS nfet_03v3")
        with self.assertRaises(ValueError):
            _deck.stage_device_lines(mangled)

    def test_channel_polarity_follows_the_committed_model_name(self):
        self.assertEqual(_deck.channel_polarity(self.src, "XMN"), 1.0)
        self.assertEqual(_deck.channel_polarity(self.src, "XMNT"), 1.0)
        self.assertEqual(_deck.channel_polarity(self.src, "XMP"), -1.0)
        self.assertEqual(_deck.channel_polarity(self.src, "XMPH"), -1.0)

    def test_the_generator_terminals_are_what_the_weight_map_assumes(self):
        """`run.py`'s ISF_WEIGHT claims two sources are ideal rails.  Check it."""
        self.assertEqual(self.devs["XMPH"]["s"].upper(), "VDD")
        self.assertEqual(self.devs["XMNT"]["s"].upper(), "VSS")
        self.assertEqual(self.devs["XMPH"]["d"].upper(), "NH")
        self.assertEqual(self.devs["XMNT"]["d"].upper(), "NT")
        # ...and that the two switching devices' generators sit between two RING
        # nodes, which is why their h_gen cannot be had without direct injection.
        self.assertEqual(self.devs["XMN"]["d"].upper(), "Y")
        self.assertEqual(self.devs["XMN"]["s"].upper(), "NT")
        self.assertEqual(self.devs["XMP"]["d"].upper(), "Y")
        self.assertEqual(self.devs["XMP"]["s"].upper(), "NH")


class NoiseDeckShape(unittest.TestCase):
    """The generated `.noise` deck, without running it."""

    @classmethod
    def setUpClass(cls):
        cls.src = _deck.isf_deck.read_vco_netlist(REPO)
        cls.text = _deck.noise_deck(
            pdk_models="/nonexistent/models", src=cls.src, instance="XMN",
            vgs=1.2, vds=0.5, vbs=-0.1, freqs=(1e6, 1e8), temp_c=27.0,
            rsense=1e-3,
        )

    def test_the_analysis_band_is_exactly_one_hertz(self):
        """`f*(1+eps)` instead of `f+1` makes every mechanism rise as sqrt(f)."""
        self.assertEqual(_deck.NOISE_BANDWIDTH_HZ, 1.0)
        self.assertIn("noise v(d) iprb lin 2 1000000 1000001 1", self.text)
        self.assertIn("noise v(d) iprb lin 2 100000000 100000001 1", self.text)

    def test_each_frequency_gets_its_own_ac_before_its_noise(self):
        """The transimpedance is measured at the frequency, not assumed flat."""
        lines = [ln for ln in self.text.splitlines()
                 if ln.startswith(("ac ", "noise ", "setplot "))]
        self.assertEqual(lines[0], "ac lin 1 1000000 1000000")
        self.assertTrue(lines[1].startswith("noise "))
        self.assertEqual(lines[2], "setplot noise2")
        self.assertEqual(lines[3], "ac lin 1 100000000 100000000")
        self.assertEqual(lines[5], "setplot noise4")

    def test_the_integrated_plot_index_is_two_per_noise_call(self):
        """ngspice allocates the spectral plot then the integrated one."""
        for k in range(2):
            self.assertIn(f"setplot noise{2 * k + 2}", self.text)

    def test_an_ntype_bias_is_applied_with_positive_terminals(self):
        self.assertIn("vg g 0 dc 1.200000000000e+00", self.text)
        self.assertIn("vb b 0 dc -1.000000000000e-01", self.text)

    def test_a_ptype_bias_is_applied_with_every_terminal_negated(self):
        """Getting this backwards biases the device OFF and reports smooth garbage."""
        text = _deck.noise_deck(
            pdk_models="/nonexistent/models", src=self.src, instance="XMP",
            vgs=1.2, vds=0.5, vbs=-0.1, freqs=(1e6,), temp_c=27.0,
        )
        self.assertIn("vg g 0 dc -1.200000000000e+00", text)
        self.assertIn("vd dd 0 dc -5.000000000000e-01", text)
        self.assertIn("vb b 0 dc 1.000000000000e-01", text)

    def test_the_probe_is_a_one_amp_ac_source_from_source_to_drain(self):
        """It is both the transimpedance stimulus and the `.noise` input source."""
        self.assertIn("iprb 0 d dc 0 ac 1", self.text)
        self.assertIn("noise v(d) iprb", self.text)


class TrajectoryDeckColumns(unittest.TestCase):
    """The `save` card, whose absence freezes every operating-point column."""

    @classmethod
    def setUpClass(cls):
        cls.src = _deck.isf_deck.read_vco_netlist(REPO)
        cls.text, cls.cols = _deck.trajectory_deck(
            repo_root=REPO, pdk_models="/nonexistent/models",
            tstop=1e-7, tstep=2e-12, tmax=2e-12,
            op=dict(vctrl=1.795, vsup=3.3, temp_c=27.0, band=(0, 1, 1)),
            stages=(1, 2), src=cls.src,
        )

    def test_every_extra_column_is_also_saved(self):
        save = next(ln for ln in self.text.splitlines() if ln.startswith("save "))
        for col in self.cols:
            with self.subTest(col=col):
                self.assertIn(col, save)

    def test_the_save_card_precedes_the_tran(self):
        lines = self.text.splitlines()
        self.assertLess(
            next(i for i, ln in enumerate(lines) if ln.startswith("save ")),
            next(i for i, ln in enumerate(lines) if ln.startswith("tran ")),
        )

    def test_the_column_order_is_stage_then_instance_then_param(self):
        """`sid_extract` indexes columns by position; `wrdata` writes no header."""
        expect = [
            _deck.op_vector(0, s, inst, p)
            for s in (1, 2)
            for inst in _deck.RING_DEVICES
            for p in _deck.OP_VECTORS
        ]
        self.assertEqual(self.cols, expect)

    def test_the_wrdata_line_carries_the_clock_first_then_the_columns(self):
        wr = next(ln for ln in self.text.splitlines() if ln.startswith("wrdata "))
        fields = wr.split()[2:]
        self.assertEqual(fields[0], "v(clk0)")
        self.assertEqual(fields[1:], self.cols)

    def test_with_no_extra_vectors_no_save_card_is_emitted(self):
        """Additive by construction: the ISF bring-up's own decks are unchanged."""
        plain = _deck.isf_deck.build_deck(
            repo_root=REPO, pdk_models="/nonexistent/models", injections=(),
            ncopy=1, tstop=1e-7, tstep=2e-12, tmax=2e-12, vctrl=1.795,
            src=self.src,
        )
        self.assertNotIn("\nsave ", plain)


class UnitsAnchor(unittest.TestCase):
    """The check that catches a widened analysis band -- against its own closed form."""

    def test_a_resistors_thermal_noise_is_recovered_exactly(self):
        r, t_c, bw, zm = 1e-3, 27.0, 1.0, 1e-3
        expect = math.sqrt(4.0 * _extract.K_B * (t_c + 273.15) * r * bw) * zm / r
        block = {"zm0": zm, "onoise_total_rs_thermal": expect}
        self.assertAlmostEqual(
            _extract.units_anchor(block, rsense=r, temp_c=t_c, bw=bw), 1.0,
            places=12)

    def test_a_band_widened_by_a_factor_shows_up_as_its_square_root(self):
        """The failure mode: every mechanism appears to rise together as sqrt(bw)."""
        r, t_c, zm = 1.0, 27.0, 1.0
        true = math.sqrt(4.0 * _extract.K_B * (t_c + 273.15) * r * 100.0) * zm / r
        block = {"zm0": zm, "onoise_total_rs_thermal": true}
        self.assertAlmostEqual(
            _extract.units_anchor(block, rsense=r, temp_c=t_c, bw=1.0),
            10.0, places=6)

    def test_the_anchor_scales_with_temperature_as_sqrt_T(self):
        r, bw, zm = 1.0, 1.0, 1.0
        v = math.sqrt(4.0 * _extract.K_B * 300.15 * r * bw) * zm / r
        block = {"zm0": zm, "onoise_total_rs_thermal": v}
        hot = _extract.units_anchor(block, rsense=r, temp_c=127.0, bw=bw)
        self.assertAlmostEqual(hot, math.sqrt(300.15 / 400.15), places=9)


class SidExtraction(unittest.TestCase):
    """`extract_sid` and the two normalisations it compares."""

    def test_both_normalisations_recover_the_same_density(self):
        zm, s_rms = 1e-3, 3.0e-12     # A/sqrt(Hz) of drain-current noise
        block = {
            "freq_Hz": 1e6, "zm0": zm,
            "onoise_total.m.xm1.m0.id": s_rms * zm,
            "onoise_total.m.xm1.m0.1overf": 2 * s_rms * zm,
            "inoise_total.m.xm1.m0.id": s_rms,
            "inoise_total.m.xm1.m0.1overf": 2 * s_rms,
        }
        out = _extract.extract_sid(block)
        self.assertAlmostEqual(out["S_thermal_A2_per_Hz"], s_rms ** 2, places=30)
        self.assertAlmostEqual(out["S_flicker_A2_per_Hz"], (2 * s_rms) ** 2,
                               places=30)
        self.assertAlmostEqual(out["S_thermal_rel_diff"], 0.0, places=12)

    def test_a_disagreement_between_the_two_is_reported_not_hidden(self):
        block = {
            "freq_Hz": 1e6, "zm0": 1.0,
            "onoise_total.m.xm1.m0.id": 1.0,
            "onoise_total.m.xm1.m0.1overf": 1.0,
            "inoise_total.m.xm1.m0.id": 2.0,      # 4x in power
            "inoise_total.m.xm1.m0.1overf": 1.0,
        }
        out = _extract.extract_sid(block)
        self.assertAlmostEqual(out["S_thermal_rel_diff"], 3.0, places=12)

    def test_noise_conductance_inverts_four_k_T(self):
        g = 1.2e-4
        s = 4.0 * _extract.K_B * 300.15 * g
        self.assertAlmostEqual(_extract.noise_conductance(s, 27.0) / g, 1.0,
                               places=9)

    def test_series_resistance_is_recovered_from_the_two_drain_voltages(self):
        """`(polarity*v(d) - vds)/id - rsense` for both polarities."""
        for pol in (1.0, -1.0):
            with self.subTest(pol=pol):
                idv, vds, rser, rsense = 5e-5, 1.5, 1.28, 1e-3
                vd = pol * (vds + idv * (rser + rsense))
                got = _extract.series_resistance(
                    {"id": idv, "vds": vds, "v_drain_node": vd},
                    polarity=pol, rsense=rsense)
                self.assertAlmostEqual(got, rser, places=9)


class NoiseLogParsing(unittest.TestCase):
    """A short parse must raise, not return a table of zeros."""

    HEAD = "\n".join([
        "@m.xm1.m0[vgs] = 1.4e+00",
        "@m.xm1.m0[vds] = 9.0e-02",
        "@m.xm1.m0[vbs] = -2.0e-01",
        "@m.xm1.m0[id] = 4.8e-05",
        "@m.xm1.m0[gm] = 5.6e-05",
        "@m.xm1.m0[gds] = 4.8e-04",
        "v(d) = 9.0e-02",
    ])
    BLOCK = "\n".join([
        "zm0 = 1.0e-03",
        "onoise_total_rs_thermal = 4.07e-12",
        "onoise_total.m.xm1.m0.id = 3.0e-15",
        "onoise_total.m.xm1.m0.1overf = 2.9e-15",
        "inoise_total.m.xm1.m0.id = 3.0e-12",
        "inoise_total.m.xm1.m0.1overf = 2.9e-12",
    ])

    def test_a_complete_log_parses(self):
        out = _extract.parse_noise_log(self.HEAD + "\n" + self.BLOCK, (1e6,))
        self.assertAlmostEqual(out["op"]["id"], 4.8e-05)
        self.assertEqual(len(out["per_freq"]), 1)
        self.assertAlmostEqual(out["per_freq"][0]["zm0"], 1e-3)

    def test_a_missing_noise_vector_raises(self):
        """An unknown-vector `print` emits a diagnostic and nothing parseable."""
        bad = self.BLOCK.replace(
            "inoise_total.m.xm1.m0.1overf = 2.9e-12",
            "Error: no such vector inoise_total.m.xm1.m0.1overf")
        with self.assertRaises(ValueError):
            _extract.parse_noise_log(self.HEAD + "\n" + bad, (1e6,))

    def test_a_missing_operating_point_raises(self):
        bad = self.HEAD.replace("@m.xm1.m0[gds] = 4.8e-04", "")
        with self.assertRaises(ValueError):
            _extract.parse_noise_log(bad + "\n" + self.BLOCK, (1e6,))

    def test_per_frequency_vectors_are_taken_in_print_order_not_by_name(self):
        """They share one name, so a by-name parse would read the first twice."""
        second = self.BLOCK.replace("zm0 = 1.0e-03", "zm1 = 2.0e-03").replace(
            "onoise_total.m.xm1.m0.id = 3.0e-15",
            "onoise_total.m.xm1.m0.id = 6.0e-15")
        out = _extract.parse_noise_log(
            self.HEAD + "\n" + self.BLOCK + "\n" + second, (1e6, 1e8))
        self.assertAlmostEqual(out["per_freq"][0]["onoise_total.m.xm1.m0.id"],
                               3.0e-15)
        self.assertAlmostEqual(out["per_freq"][1]["onoise_total.m.xm1.m0.id"],
                               6.0e-15)


class FlickerAndWhiteness(unittest.TestCase):
    """The frequency-dependence fits, against exact power laws."""

    def test_a_pure_power_law_returns_its_own_exponent(self):
        freqs = [1e3, 1e4, 1e5, 1e6]
        out = _extract.flicker_exponent(freqs, [1e-20 * f ** -0.95 for f in freqs])
        self.assertAlmostEqual(out["alpha"], 0.95, places=9)
        self.assertAlmostEqual(out["K_at_1Hz"], 1e-20, places=27)
        self.assertLess(out["max_abs_resid_dex"], 1e-9)

    def test_a_flat_trace_has_zero_whiteness_span(self):
        out = _extract.whiteness([1e3, 1e6], [2.0, 2.0])
        self.assertEqual(out["span_rel"], 0.0)

    def test_a_two_to_one_trace_reports_a_span_of_one(self):
        out = _extract.whiteness([1e3, 1e6], [1.0, 2.0])
        self.assertAlmostEqual(out["span_rel"], 1.0, places=12)


class StationaryCost(unittest.TestCase):
    """Both cost reductions, against hand-computed averages."""

    def test_the_cycle_average_of_a_uniform_grid_is_the_plain_mean(self):
        ph = [i / 4 for i in range(4)]
        self.assertAlmostEqual(_extract.cycle_average(ph, [1.0, 2.0, 3.0, 4.0]),
                               2.5, places=12)

    def test_a_non_uniform_grid_is_refused(self):
        with self.assertRaises(ValueError):
            _extract.cycle_average([0.0, 0.1, 0.5], [1.0, 1.0, 1.0])

    def test_a_convention_at_twice_the_average_reports_plus_three_dB(self):
        ph = [i / 4 for i in range(4)]
        out = _extract.stationary_cost(ph, [1.0, 1.0, 1.0, 1.0],
                                       conventions={"double": 2.0})
        self.assertAlmostEqual(out["cycle_average"], 1.0, places=12)
        self.assertAlmostEqual(out["conventions"]["double"]["error_dB"],
                               10.0 * math.log10(2.0), places=12)

    def test_the_span_is_ten_log_ten_of_max_over_min(self):
        self.assertAlmostEqual(_extract.span_db([1.0, 100.0]), 20.0, places=12)

    def test_a_flat_weight_makes_the_weighted_average_the_plain_one(self):
        ph = [i / 4 for i in range(4)]
        dens = [1.0, 2.0, 3.0, 4.0]
        out = _extract.isf_weighted_cost(ph, dens, [1.0] * 4, conventions={})
        self.assertAlmostEqual(out["S_eff_A2_per_Hz"], 2.5, places=12)
        self.assertAlmostEqual(out["weighted_over_unweighted_dB"], 0.0, places=12)
        self.assertAlmostEqual(out["h2_participation"], 1.0, places=12)

    def test_a_weight_concentrated_on_one_phase_picks_that_phase_out(self):
        ph = [i / 4 for i in range(4)]
        dens = [1.0, 2.0, 3.0, 4.0]
        out = _extract.isf_weighted_cost(ph, dens, [0.0, 0.0, 1.0, 0.0],
                                         conventions={"c": 3.0})
        self.assertAlmostEqual(out["S_eff_A2_per_Hz"], 3.0, places=12)
        self.assertAlmostEqual(out["h2_participation"], 0.25, places=12)
        self.assertAlmostEqual(out["conventions"]["c"]["error_dB"], 0.0, places=12)

    def test_the_weight_is_h_squared_so_its_sign_does_not_matter(self):
        ph = [i / 4 for i in range(4)]
        dens = [1.0, 2.0, 3.0, 4.0]
        pos = _extract.isf_weighted_cost(ph, dens, [1.0, 2.0, 3.0, 4.0],
                                         conventions={})
        neg = _extract.isf_weighted_cost(ph, dens, [-1.0, 2.0, -3.0, 4.0],
                                         conventions={})
        self.assertAlmostEqual(pos["S_eff_A2_per_Hz"], neg["S_eff_A2_per_Hz"],
                               places=12)

    def test_an_all_zero_weight_is_refused(self):
        with self.assertRaises(ValueError):
            _extract.isf_weighted_cost([0.0, 0.5], [1.0, 1.0], [0.0, 0.0],
                                       conventions={})


class PhaseGridMatching(unittest.TestCase):
    """`match_phase_grids` intersects rather than interpolating `h`."""

    def test_a_twelve_point_grid_inside_a_twenty_four_point_one_keeps_twelve(self):
        p24 = [i / 24 for i in range(24)]
        p12 = [i / 12 for i in range(12)]
        ph, a, b = _extract.match_phase_grids(
            p24, [float(i) for i in range(24)], p12, [float(i) for i in range(12)])
        self.assertEqual(len(ph), 12)
        self.assertEqual(a, [float(2 * i) for i in range(12)])
        self.assertEqual(b, [float(i) for i in range(12)])

    def test_a_non_uniform_intersection_is_refused(self):
        """An equal-weight average of a non-uniform grid is not a cycle average."""
        with self.assertRaises(ValueError):
            _extract.match_phase_grids(
                [0.0, 0.25, 0.5, 0.75], [1.0] * 4, [0.0, 0.25, 0.75], [1.0] * 3)

    def test_disjoint_grids_are_refused(self):
        with self.assertRaises(ValueError):
            _extract.match_phase_grids([0.1], [1.0], [0.2], [1.0])


class StageShift(unittest.TestCase):
    """The stage shift is measured, not assumed -- replayed on a synthetic ring."""

    N = 5
    NPH = 60

    def _synthetic(self, shift_per_stage, noise=0.0):
        """A 5-stage ring whose stage `k` is stage 1 delayed by `k*shift`.

        Returns `(t, cols, names)` in `stage_symmetry`'s calling convention.  The
        waveform is deliberately NOT sinusoidal: a sinusoid is its own antiphase up
        to a sign, so a shift error of 1/2 would be invisible on one.
        """
        period, t0 = 1.0, 0.0
        n = 600
        t = [i * period / n for i in range(2 * n)]

        def wave(x):
            x = x % 1.0
            # asymmetric: rises over 30 % of the cycle, falls over 70 %
            return x / 0.3 if x < 0.3 else (1.0 - x) / 0.7 + 0.0

        names, cols = [], []
        for stage in range(1, self.N + 1):
            key = f"@m.x0.xs{stage}.xmn.m0[vgs]"
            names.append(key)
            sh = shift_per_stage * (stage - 1)
            cols.append([wave(tt / period - sh) + noise * (i % 3 - 1)
                         for i, tt in enumerate(t)])
        return t, cols, names, period, t0

    def test_the_scan_recovers_a_shift_of_zero_point_six(self):
        t, cols, names, period, t0 = self._synthetic(0.6)
        phases = [i / self.NPH for i in range(self.NPH)]
        out = _extract.stage_symmetry(
            t, cols, names, t0=t0, period=period, phases=phases,
            stages=(1, 2, 3, 4, 5), instance="XMN", param="vgs")
        self.assertEqual(out["predicted_shift_per_stage_cycles"], 0.6)
        for row in out["stages"]:
            with self.subTest(stage=row["stage"]):
                self.assertLess(abs(row["best_fit_shift_minus_predicted_cycles"]),
                                2 * row["shift_scan_resolution_cycles"])
                self.assertLess(row["best_fit_peak_residual_frac_of_ptp"], 1e-6)

    def test_the_predicted_shift_is_one_over_two_N_plus_a_half(self):
        self.assertAlmostEqual(_extract.STAGE_SHIFT_CYCLES,
                               1.0 / (2 * self.N) + 0.5, places=12)

    def test_comparing_at_one_over_N_returns_a_large_residual(self):
        """The failure this scan exists to distinguish from a real asymmetry."""
        t, cols, names, period, t0 = self._synthetic(0.6)
        phases = [i / self.NPH for i in range(self.NPH)]
        saved = _extract.STAGE_SHIFT_CYCLES
        try:
            _extract.STAGE_SHIFT_CYCLES = 1.0 / self.N
            out = _extract.stage_symmetry(
                t, cols, names, t0=t0, period=period, phases=phases,
                stages=(1, 2, 3, 4, 5), instance="XMN", param="vgs")
        finally:
            _extract.STAGE_SHIFT_CYCLES = saved
        worst = max(r["peak_residual_frac_of_ptp"] for r in out["stages"])
        self.assertGreater(worst, 0.5)
        # ...while the scan still finds the true shift, which is the point.
        for row in out["stages"]:
            self.assertLess(row["best_fit_peak_residual_frac_of_ptp"], 1e-6)

    def test_a_non_uniform_phase_grid_is_refused(self):
        t, cols, names, period, t0 = self._synthetic(0.6)
        with self.assertRaises(ValueError):
            _extract.stage_symmetry(
                t, cols, names, t0=t0, period=period,
                phases=[0.0, 0.1, 0.5], stages=(1, 2), instance="XMN",
                param="vgs")


class TrajectorySampling(unittest.TestCase):
    """`sample_trajectory`'s snap-vs-interpolate contract."""

    def _cols(self):
        t = [i * 1e-12 for i in range(1001)]
        names = ["@m.x0.xs1.xmn.m0[vgs]"]
        cols = [[float(i) for i in range(1001)]]
        return t, cols, names

    def test_interpolation_hits_the_requested_phase_exactly(self):
        t, cols, names = self._cols()
        rows = _extract.sample_trajectory(
            t, cols, names, t0=0.0, period=1e-10, phases=[0.5])
        self.assertAlmostEqual(rows[0]["phase_cycles"], 0.5)
        self.assertAlmostEqual(rows[0]["phase_cycles_actual"], 0.5)
        self.assertFalse(rows[0]["snapped"])
        self.assertAlmostEqual(rows[0]["@m.x0.xs1.xmn.m0[vgs]"], 50.0, places=9)

    def test_snapping_returns_a_stored_row_and_reports_where_it_landed(self):
        t, cols, names = self._cols()
        # phase 0.505 of a 100 ps period is t = 50.5 ps, exactly between samples.
        rows = _extract.sample_trajectory(
            t, cols, names, t0=0.0, period=1e-10, phases=[0.505], snap=True)
        self.assertTrue(rows[0]["snapped"])
        self.assertIn(rows[0]["@m.x0.xs1.xmn.m0[vgs]"], (50.0, 51.0))
        self.assertNotAlmostEqual(rows[0]["phase_cycles_actual"], 0.505, places=6)
        self.assertLess(abs(rows[0]["phase_cycles_actual"] - 0.505), 0.01)

    def test_a_phase_past_the_transients_end_is_refused(self):
        t, cols, names = self._cols()
        with self.assertRaises(ValueError):
            _extract.sample_trajectory(
                t, cols, names, t0=0.0, period=1e-9, phases=[2.0])


if __name__ == "__main__":
    unittest.main()
