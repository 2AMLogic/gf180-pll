"""`sim/period-jitter/random-bound` -- derivation, bound arithmetic and statistics, off ngspice.

What is pinned here is what would fail SILENTLY if it broke -- a bound that is
quietly smaller than it claims looks exactly like a good result:

1. **Every VCO generator gets a noise source, and no device line is altered.**
   A device left noiseless makes the bound a lower bound presented as a bound.
   The derivation must raise on a missing amplitude, carry the committed
   netlist's own device text through untouched, and put exactly one `trnoise`
   across each channel.
2. **The `trnoise` calibration arithmetic**: one-sided PSD `2 NA^2 NT`.
3. **The noise deck's sub-networks are disjoint** -- the property that lets one
   `.noise` referred to `v(d<j>)` see device `j` alone -- and a pfet is biased
   with its terminals negated.
4. **The three inequalities' arithmetic**: the flicker factor reduces to its
   open-loop closed form when the loop does nothing, is finite for the pfet
   cards' `ef = 1.12` only because of the loop, and the white loop factor is 1
   when the loop does nothing.
5. **The statistics**: chi-square quantiles against tabulated values, the
   one-sided confidence limit's direction, and the pairwise slope on a sequence
   whose answer is known.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import math
import random
import re
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO = SIM_DIR.parent
RB = SIM_DIR / "period-jitter" / "random-bound"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

_deck = load_module(RB / "rb_deck.py")
_x = load_module(RB / "rb_extract.py")


def _src():
    return _deck.isf_deck.read_vco_netlist(REPO)


class DeviceCatalogue(unittest.TestCase):
    def setUp(self):
        self.devs = _deck.devices(_src())

    def test_counts(self):
        by = {}
        for d in self.devs:
            by[(d["block"], d["kind"])] = by.get((d["block"], d["kind"]), 0) + 1
        self.assertEqual(by[("ring", "mos")], 20)  # 4 devices x 5 stages
        self.assertEqual(by[("buffer", "mos")], 6)
        self.assertEqual(by[("bias", "res")], 3)
        self.assertGreater(by[("bias", "mos")], 30)

    def test_paths_unique(self):
        paths = [d["path"] for d in self.devs]
        self.assertEqual(len(paths), len(set(paths)))

    def test_decaps_excluded_on_purpose(self):
        # Both terminals on the ideal supply: noiseless by construction.
        self.assertFalse(any(d["instance"].startswith("XCDEC") for d in self.devs))

    def test_ring_terminals(self):
        ring = {d["instance"]: d for d in self.devs if d["block"] == "ring"}
        self.assertEqual((ring["XMPH"]["d"], ring["XMPH"]["s"]), ("NH", "VDD"))
        self.assertEqual((ring["XMP"]["d"], ring["XMP"]["s"]), ("Y", "NH"))
        self.assertEqual((ring["XMN"]["d"], ring["XMN"]["s"]), ("Y", "NT"))
        self.assertEqual((ring["XMNT"]["d"], ring["XMNT"]["s"]), ("NT", "VSS"))


class NoisyDerivation(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.devs = _deck.devices(self.src)
        self.amps = {d["path"]: 1e-7 * (1 + i) for i, d in enumerate(self.devs)}
        self.text = _deck.noisy_subckts(self.src, self.amps, 1e-11, tag="t")

    def test_one_source_per_device(self):
        self.assertEqual(self.text.count("trnoise("), len(self.devs))

    def test_zero_amplitude_emits_no_source(self):
        """0 is how the transient leaves the bias generator to the `bias` stage:
        exactly the zero-amplitude devices lose their source, no others."""
        amps = {d["path"]: (0.0 if d["block"] == "bias" else 1e-7) for d in self.devs}
        text = _deck.noisy_subckts(self.src, amps, 1e-11)
        n_bias = sum(d["block"] == "bias" for d in self.devs)
        self.assertEqual(text.count("trnoise("), len(self.devs) - n_bias)
        for d in self.devs:
            if d["block"] == "bias":
                self.assertNotIn(f"in_{d['instance'].lower()} ", text)

    def test_missing_amplitude_raises(self):
        amps = dict(self.amps)
        amps.pop(self.devs[0]["path"])
        with self.assertRaises(ValueError):
            _deck.noisy_subckts(self.src, amps, 1e-11)

    def test_unknown_amplitude_raises(self):
        amps = dict(self.amps, **{"xnope.xm1": 1e-7})
        with self.assertRaises(ValueError):
            _deck.noisy_subckts(self.src, amps, 1e-11)

    def test_device_lines_verbatim(self):
        joined = "\n".join(_deck._join_continuations(self.text))
        for d in self.devs:
            if d["kind"] == "mos":
                line = (f"{d['instance']} {d['d']} {d['g']} {d['s']} {d['b']} "
                        f"{d['model']} {d['params']}")
            else:
                line = f"{d['instance']} {d['n1']} {d['n2']} {d['n3']} {d['model']} {d['params']}"
            self.assertIn(line.lower(), joined.lower(), d["path"])

    def test_each_stage_has_its_own_subckt_and_amplitudes(self):
        for s in _deck.STAGES:
            m = re.search(rf"^\.subckt vco_stage_rbt_s{s} .*?^\.ends", self.text, re.M | re.S)
            self.assertIsNotNone(m)
            body = m.group(0)
            for d in self.devs:
                if d["block"] == "ring" and d["stage"] == s:
                    na = self.amps[d["path"]]
                    self.assertIn(f"in_{d['instance'].lower()} {d['d']} {d['s']} "
                                  f"trnoise({na:.6e} ", body)
            self.assertRegex(self.text, rf"(?m)^XS{s} .* vco_stage_rbt_s{s}$")
        self.assertRegex(self.text, r"(?m)^XBIAS .* vco_bias_rbt$")

    def test_noise_is_drain_to_source(self):
        for d in self.devs:
            if d["kind"] == "mos":
                self.assertRegex(
                    self.text,
                    rf"(?m)^in_{d['instance'].lower()} {re.escape(d['d'])} "
                    rf"{re.escape(d['s'])} trnoise\(")

    def test_trnoise_amplitude(self):
        s, nt = 3.7e-23, 1e-11
        na = _deck.trnoise_amplitude(s, nt)
        self.assertAlmostEqual(2 * na * na * nt / s, 1.0, places=12)
        with self.assertRaises(ValueError):
            _deck.trnoise_amplitude(-1.0, nt)


OP = dict(vctrl=1.795, vsup=3.3, temp_c=27.0, band=(0, 1, 1), mos_section="typical",
          res_section="res_typical", moscap_section="moscap_typical")


class Decks(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.devs = _deck.devices(self.src)

    def test_transient_deck_structure(self):
        amps = {d["path"]: 1e-7 for d in self.devs}
        deck, copies = _deck.transient_deck(
            repo_root=REPO, pdk_models="/pdk", op=OP,
            variants=[("", amps, 1e-11, 3)], tstop=1e-7, tstep=1e-11, tmax=1e-11,
            rndseed=1234, src=self.src)
        self.assertEqual([c["variant"] for c in copies], ["clean", "", "", ""])
        self.assertRegex(deck, r"(?m)^x0 .* vco_isf$")
        for k in (1, 2, 3):
            self.assertRegex(deck, rf"(?m)^x{k} .* vco_rb$")
            self.assertRegex(deck, rf"(?m)^xld{k} clk{k} .* div23_cell$")
        self.assertIn("set rndseed=1234", deck)
        self.assertLess(deck.index("\nsave "), deck.index("\ntran "))

    def test_ic_offset_only_moves_the_first_ring_node(self):
        """The start-up retry's only change: with no offset the `.ic` is the ISF
        bring-up's, byte for byte; with one, only `y<k>_1` moves."""
        self.assertEqual(_deck._ic(3),
                         ".ic v(y3_1)=0 v(y3_2)='vsup' v(y3_3)=0 v(y3_4)='vsup' v(y3_5)=0")
        self.assertEqual(_deck._ic(3, 1e-3),
                         ".ic v(y3_1)=0.001 v(y3_2)='vsup' v(y3_3)=0 v(y3_4)='vsup' v(y3_5)=0")

    def test_trajectory_deck_saves_before_tran(self):
        deck, cols = _deck.trajectory_deck(
            repo_root=REPO, pdk_models="/pdk", op=OP, devs=self.devs, tstop=5e-8,
            tstep=2e-12, tmax=2e-12, kvco_dv=0.01, src=self.src)
        self.assertLess(deck.index("\nsave "), deck.index("\ntran "))
        self.assertEqual(cols[:3], ["v(clk0)", "v(clk1)", "v(clk2)"])
        self.assertIn("@m.x0.xs3.xmn.m0[vgs]", cols)
        self.assertIn("@m.x0.xbias.xmp1.m0[id]", cols)
        self.assertIn("@m.x0.xmbn3.m0[vds]", cols)

    def test_noise_deck_disjoint_and_polarity(self):
        entries = []
        for j, d in enumerate(self.devs):
            bias = ({"vgs": 1.0, "vds": 0.5, "vbs": -0.1} if d["kind"] == "mos"
                    else {"v": 0.2})
            entries.append((j, d, bias, None))
        deck = _deck.noise_deck(pdk_models="/pdk", op=OP, entries=entries,
                                freqs=(1e6,), rsense=1e-3, combined=False)
        for j, d in enumerate(self.devs):
            if d["kind"] == "mos":
                p = -1.0 if d["model"].startswith("p") else 1.0
                self.assertIn(f"vg{j} g{j} 0 dc {p * 1.0:.12e}", deck)
                self.assertIn(f"xm{j} d{j} g{j} 0 b{j} ", deck)
                self.assertIn(f"noise v(d{j}) iprb{j} ", deck)
            else:
                self.assertNotIn(f"noise v(r{j})", deck)
        # disjoint: every drain/gate/bulk net name appears on exactly one device
        for j, d in enumerate(self.devs):
            if d["kind"] == "mos":
                self.assertEqual(len(re.findall(rf"\bd{j}\b", deck)), 5)  # rs, iprb, xm, noise, print mag

    def test_combined_noise_deck_sums_every_drain_once(self):
        """The default form: one `.noise` per frequency, referred to a VCVS stack
        that adds every MOS drain exactly once -- a drain left out of the sum
        would report a zero density for that device, i.e. a noiseless one."""
        entries = []
        for j, d in enumerate(self.devs):
            bias = ({"vgs": 1.0, "vds": 0.5, "vbs": -0.1} if d["kind"] == "mos"
                    else {"v": 0.2})
            entries.append((j, d, bias, None))
        freqs = (1e6, 7e7)
        deck = _deck.noise_deck(pdk_models="/pdk", op=OP, entries=entries,
                                freqs=freqs, rsense=1e-3)
        mos = [j for j, d in enumerate(self.devs) if d["kind"] == "mos"]
        self.assertEqual(len(re.findall(r"(?m)^noise ", deck)), len(freqs))
        stack = re.findall(r"(?m)^esum(\d+) sum(\d+) (\S+) d(\d+) 0 1$", deck)
        self.assertEqual([int(s[3]) for s in stack], mos)
        prev = "0"
        for e, s, p, dj in stack:
            self.assertEqual((e, s, dj), (dj, dj, dj))
            self.assertEqual(p, prev)
            prev = f"sum{s}"
        self.assertEqual(len(re.findall(rf"(?m)^noise v\({prev}\) ", deck)), len(freqs))
        for j in mos:  # every device's contribution is printed at every frequency
            self.assertEqual(deck.count(f"print onoise_total.m.xm{j}.m0 "), len(freqs))

    def test_noise_deck_op_only_pass(self):
        d = next(x for x in self.devs if x["kind"] == "mos")
        deck = _deck.noise_deck(pdk_models="/pdk", op=OP,
                                entries=[(0, d, {"vgs": 1, "vds": 1, "vbs": 0}, None)],
                                freqs=(), rsense=1e-3)
        self.assertNotIn("noise v(", deck)
        self.assertIn("@m.xm0.m0[vgs]", deck)


class BiasSmallSignal(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.devs = _deck.devices(self.src)

    def test_ideal_bias_vco_drops_only_xbias(self):
        text = _deck.ideal_bias_vco_subckt(self.src)
        self.assertTrue(text.startswith(".subckt vco_ib "))
        self.assertTrue(text.split("\n", 1)[0].endswith(" VBP VBN"))
        self.assertNotRegex(text, r"(?m)^XBIAS ")
        wrappers = _deck.isf_deck.derive_wrappers(self.src)
        vco_isf = re.search(r"^\.subckt vco_isf\b.*?^\.ends", wrappers, re.M | re.S).group(0)
        kept = [ln for ln in vco_isf.splitlines()[1:] if not ln.startswith("XBIAS ")]
        self.assertEqual(text.rstrip().splitlines()[1:], kept)

    def test_lti_deck_structure(self):
        res = {d["instance"]: {"R_ohm": 1e5, "I_A": 1e-5}
               for d in self.devs if d["block"] == "bias" and d["kind"] == "res"}
        nh = {s: 2.0 for s in _deck.STAGES}
        nt = {s: 0.1 for s in _deck.STAGES}
        freqs = (1.0, 10.0, 100.0)
        deck = _deck.bias_lti_deck(pdk_models="/pdk", repo_root=REPO, op=OP, src=self.src,
                                   kp=1e8, kn=-2e8, nh=nh, nt=nt, resistors=res,
                                   kf_body=1e-25, af_body=1.0, freqs=freqs)
        for ln in _deck.subckt_lines(self.src, "vco_bias"):  # verbatim device text
            self.assertIn(ln, deck)
        self.assertEqual(len(re.findall(r"(?m)^noise v\(out\) vvc ", deck)), len(freqs))
        for tag in (t.lower() for t in res):
            # dummy body resistor, its sense source, the mirror and the DC cancel
            self.assertRegex(deck, rf"(?m)^rd_{tag} da_{tag} db_{tag} rbody_{tag} ")
            self.assertRegex(deck, rf"(?m)^f_{tag} \S+ \S+ vs_{tag} 1$")
            self.assertRegex(deck, rf"(?m)^ic_{tag} \S+ \S+ dc 1\.0+e-05$")
        self.assertEqual(len(re.findall(r"(?m)^xlp\d dlp\d vbp vdd vdd pfet_03v3", deck)), 5)
        self.assertEqual(len(re.findall(r"(?m)^xln\d dln\d vbn 0 0 nfet_03v3", deck)), 5)
        self.assertIn("eo1 o1 0 vbp 0 1.000000000e+08", deck)
        self.assertIn("eout out o1 vbn 0 -2.000000000e+08", deck)

    def test_lti_variance_white_closed_form(self):
        """A white frequency noise S gives var(D)/T^2 = S/(2 f0) open-loop
        (int_0^inf sinc^2(f/f0) df = f0/2), and an envelope of 1 changes nothing."""
        f0 = 150e6
        freqs = [10 ** (k / 40) for k in range(0, 40 * 13 + 1)]  # 1 Hz .. 1 THz
        s = [1e6] * len(freqs)
        v = _x.lti_period_variance(freqs, s, f0)
        self.assertAlmostEqual(v / (1e6 / (2 * f0)), 1.0, delta=2e-3)
        ones = [1.0] * 10
        ef = [10 ** k for k in range(10)]
        self.assertAlmostEqual(_x.lti_period_variance(freqs, s, f0, ef, ones) / v, 1.0, places=12)

    def test_lti_variance_uses_the_peak_above_half_f0(self):
        f0 = 150e6
        freqs = [10 ** (k / 40) for k in range(0, 40 * 12 + 1)]
        s = [1e6] * len(freqs)
        ef = [10 ** k for k in range(11)]
        env = [2.0] * 11
        self.assertAlmostEqual(_x.lti_period_variance(freqs, s, f0, ef, env)
                               / _x.lti_period_variance(freqs, s, f0), 2.0, places=6)


class FlickerFactor(unittest.TestCase):
    def test_reduces_to_open_loop_closed_form(self):
        # env == 1 everywhere, grid reaching far below F: the numeric Phi must
        # equal (1 + eps a)/(1 - a) at F = a f0 / 2 and t_w = (1 + eps) T.
        f0, a, eps = 150e6, 0.5, _x.WINDOW_MARGIN
        freqs = _x.log_grid(1e-24, 1e10, 40)
        env = [1.0] * len(freqs)
        big_f = _x.flicker_corner_frequency(a, f0)
        got = _x.flicker_factor(a, big_f, (1 + eps) / f0, freqs, env)
        self.assertAlmostEqual(got / _x.flicker_factor_open_loop(a), 1.0, places=3)

    def test_open_loop_refuses_alpha_ge_1(self):
        with self.assertRaises(ValueError):
            _x.flicker_factor_open_loop(1.12)

    def test_closed_loop_finite_for_pfet_exponent(self):
        loops = [{"A": 2 * math.pi * 3e5 / abs(_x._z(2 * math.pi * 3e5, 77e3, 120e-12, 2e-12)),
                  "r": 77e3, "c1": 120e-12, "c2": 2e-12}]
        freqs = _x.log_grid(1.0, 1e10, 40)
        env = _x.loop_envelope(freqs, loops)
        phi = _x.flicker_factor(1.12, 71e6, 1.1 / 150e6, freqs, env)
        self.assertTrue(math.isfinite(phi))
        self.assertGreater(phi, 1.0)
        self.assertLess(phi, 1e3)

    def test_type_ii_asymptote(self):
        lp = {"A": 2 * math.pi * 3e5 / abs(_x._z(2 * math.pi * 3e5, 77e3, 120e-12, 2e-12)),
              "r": 77e3, "c1": 120e-12, "c2": 2e-12}
        e1, e2 = _x.error_transfer_sq(10.0, lp), _x.error_transfer_sq(20.0, lp)
        self.assertAlmostEqual(math.log2(e2 / e1), 4.0, places=2)

    def test_white_loop_factor_unity_without_loop(self):
        freqs = _x.log_grid(1.0, 1e10, 20)
        self.assertEqual(_x.white_loop_factor(freqs, [1.0] * len(freqs), 1e-8), 1.0)

    def test_admissible_loops_meet_floor(self):
        loops = _x.admissible_loops(r_range=(61.6e3, 93.4e3), c1_range=(107.1e-12, 133e-12),
                                    c2_range=(1.81e-12, 2.22e-12), pm_min_deg=45.0,
                                    n_rc=2, n_cross=70)
        self.assertTrue(loops)
        self.assertTrue(all(lp["pm_deg"] >= 45.0 for lp in loops))

    def test_kt_over_c(self):
        v = _x.kt_over_c_bound(temp_c=27.0, c1=120e-12, c2=2e-12)
        self.assertAlmostEqual(v / (_x.K_B * 300.15 * 120 / (2e-12 * 122)), 1.0, places=12)


class Statistics(unittest.TestCase):
    def test_chi2_quantiles(self):
        # Tabulated lower-tail 5 % points.
        for dof, want in ((30, 18.493), (100, 77.929), (236, 201.3)):
            self.assertAlmostEqual(_x.chi2_ppf(0.05, dof) / want, 1.0, delta=2e-3)

    def test_sigma_upper_above_estimate(self):
        self.assertGreater(_x.sigma_upper(1.0, 100), 1.0)
        self.assertLess(_x.sigma_upper(1.0, 10000), 1.03)

    def test_pooled_variance_removes_group_means(self):
        v, dof, n = _x.pooled_variance([[1.0, 3.0], [101.0, 103.0]])
        self.assertEqual((v, dof, n), (2.0, 2, 4))

    def test_pairwise_slope(self):
        rng = random.Random(7)
        a = [rng.gauss(0, 1) for _ in range(200)]
        b = [3.0 * x + 5.0 for x in a]
        r = _x.pairwise_deviation_ratio(a, b)
        self.assertAlmostEqual(r["slope"], 3.0, places=12)
        self.assertLess(r["resid_rel"], 1e-12)

    def test_rising_crossings(self):
        t = [0, 1, 2, 3, 4]
        v = [0, 2, 0, 2, 0]
        self.assertEqual(_x.rising_crossings(t, v, 1.0), [0.5, 2.5])

    def test_rc_variance(self):
        self.assertAlmostEqual(_x.rc_variance_expected(4.0, 2.0, 1.0), 2.0)


class Points(unittest.TestCase):
    def test_45_points_from_the_manifest(self):
        run = load_module(RB / "run.py")
        pts = run.load_points()
        self.assertEqual(len(pts), 45)
        self.assertEqual(len({(p["mos_section"], p["temp_c"], p["vsup"]) for p in pts.values()}), 45)
        self.assertIn(run.REFERENCE_POINT, pts)
        self.assertAlmostEqual(pts[run.REFERENCE_POINT]["vctrl"], 1.795)

    def test_local_maxima_are_circular_and_ranked(self):
        """Round C zooms on these; a peak straddling phase 0 must not be lost,
        and the largest must come first."""
        run = load_module(RB / "run.py")
        ks = [0, 8, 16, 24, 32]
        val = {0: 5.0, 8: 1.0, 16: 3.0, 24: 2.0, 32: 4.0}
        self.assertEqual(run._local_maxima(ks, val, 40), [0, 16])
        val = {0: 1.0, 8: 2.0, 16: 1.0, 24: 1.0, 32: 9.0}
        self.assertEqual(run._local_maxima(ks, val, 40)[0], 32)

    def test_sampling_grids_nest(self):
        """Round A and round B must be subsets of the dense grid at the trajectory's
        own resolution, and round B's stride must make round C's window
        (+/- stride-1 steps) cover every step between two round-B samples."""
        run = load_module(RB / "run.py")
        n = run.N_DENSE
        self.assertEqual(n % run.N_PHASE, 0)
        self.assertEqual(n % run.N_PHASE_SWITCHING, 0)
        self.assertEqual((n // run.N_PHASE) % (n // run.N_PHASE_SWITCHING), 0)
        # the dense step is within 10 % of the trajectory's timestep ceiling
        self.assertLess(1.0 / 150e6 / n, 1.1 * run.TRAJ_TMAX)


if __name__ == "__main__":
    unittest.main()
