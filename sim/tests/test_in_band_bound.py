"""`sim/period-jitter/in-band-bound` -- the in-band bound's derivation, off ngspice.

`../random-bound` (issue #520, DR-032) bounds the generators inside `vco` and
the loop-filter resistor. This directory bounds the four it states as outside
that scope -- the charge pump, the PFD, the feedback divider and the lock
detector (issue #580, DR-033). What is pinned here is what would fail SILENTLY
if it broke, because a bound that is quietly smaller than it claims looks
exactly like a good result:

1. **The enumeration.** `pll_top`'s five instances, the nets they share, and the
   fact that every shared net is either one of the five paths this bound
   considers or an inert supply/configuration net. An unclassified shared net is
   a path nobody looked at.
2. **`LOCK` reaches nothing.** The lock detector's only output is consumed by no
   other `pll_top` instance, which is the whole reason it is charged zero timing
   stages and reduced to a load on `UP`/`DN`. If a re-netlist ever consumed
   `LOCK`, this bound's treatment of that block would become wrong, silently.
3. **Every declared timing-path stage exists, in that position, as that cell.**
   `TIMING_PATHS` is the replacement for a device count, so a renamed or retyped
   gate must fail here rather than quietly drop out of a path.
4. **Only single-stage leaf cells are characterized.** Self-biasing a multi-stage
   cell reports its cascade's gain, not a noise voltage (`xor2_3v3`: 0.87 V).
   `CELLS` must stay a subset of the netlist's own single-stage set.
5. **The inequalities' arithmetic**: the gated charge spectrum's closed form for
   a white input (`S t_on/2`, the duty-cycle factor the pulsed charge pump is
   allowed to use), the period weight's small-`f` limit and its exactness at
   `f = f0`, the sampling fold's variance conservation, the closed-loop
   transfer's complementarity with `../random-bound`'s error transfer, the
   common-mode imbalance scale's floor, and the assembly's quadrature against the
   margin DR-032 leaves.
6. **The bound refuses rather than guesses**: a grid that does not straddle
   `f_ref/2`, a grid that has not reached a node's corner, a VCO-side bound that
   does not leave a margin, a zero conduction window.

No PDK, no ngspice, no network.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO = SIM_DIR.parent
IB = SIM_DIR / "period-jitter" / "in-band-bound"
RB = SIM_DIR / "period-jitter" / "random-bound"

sys.path.insert(0, str(SIM_DIR))
from harness.derived import load_module  # noqa: E402

_deck = load_module(IB / "ib_deck.py")
_x = load_module(IB / "ib_extract.py")
_rb = load_module(RB / "rb_extract.py")

NETLIST = REPO / "design" / "netlist" / "pll_top.spice"


def _src():
    return NETLIST.read_text()


# ---------------------------------------------------------------------------
# 1 + 2: the enumeration, and what the lock detector is connected to
# ---------------------------------------------------------------------------
class Enumeration(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_five_instances_and_their_kinds(self):
        claim = _x.connectivity_claim(self.src)
        insts = {i for v in claim["nets"].values() for i in v}
        self.assertEqual(insts, set(_x.TOP_INSTANCES))

    def test_no_unclassified_shared_net(self):
        """Every net two `pll_top` instances share is a considered path or inert.

        This is step 1 of the bound. A shared net that is neither would be a way
        one of the four blocks reaches the output that nothing here bounds.
        """
        self.assertEqual(_x.unclassified_shared_nets(self.src), [])

    def test_lock_reaches_no_other_instance(self):
        """`LOCK` is consumed by nobody -- why the lock detector has 0 stages."""
        nets = _x.connectivity_claim(self.src)["nets"]
        self.assertEqual(nets["LOCK"], ["XLD"])

    def test_lock_detector_shares_only_up_dn_and_supplies(self):
        shared = _x.connectivity_claim(self.src)["shared"]
        with_ld = set()
        for (a, b), nets in shared.items():
            if "XLD" in (a, b):
                with_ld.update(nets)
        signal = {n for n in with_ld if n not in _x.INERT_SHARED_NETS}
        self.assertEqual(signal, {"UP", "DN"})

    def test_vctrl_is_shared_by_the_charge_pump_and_the_filter_and_the_vco(self):
        nets = _x.connectivity_claim(self.src)["nets"]
        self.assertEqual(set(nets["VCTRL"]), {"XPFD", "XLF", "XVCO"})

    def test_a_new_instance_is_refused(self):
        bad = _src().replace(
            "XLD UP DN LOCK", "XNEW UP DN LOCK VWIN LDT0 LDT1 LDT2 LDT3 VDD VSS "
            "lock_detector\nXLD UP DN LOCK")
        with self.assertRaises(ValueError):
            _x.connectivity_claim(bad)

    def test_each_block_has_no_non_mos_leaf(self):
        """What makes `flatten_mos` each block's COMPLETE generator set."""
        for sub in ("cp", "pfd", "divider_chain", "lock_detector"):
            self.assertEqual(_deck.non_mos_devices(self.src, sub), [],
                             f"{sub} grew a non-MOS device")


# ---------------------------------------------------------------------------
# 3: the declared timing paths
# ---------------------------------------------------------------------------
class TimingPaths(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_every_declared_stage_resolves_to_the_declared_cell(self):
        claim = _x.timing_path_claim(self.src)
        self.assertEqual(set(claim), set(_x.TIMING_PATHS))
        for name, stages in claim.items():
            self.assertEqual([c for _, c in stages],
                             [c.lower() for _, c in _x.TIMING_PATHS[name]])

    def test_stage_counts(self):
        """The counts the bound is built on, pinned.

        Four stages from REF to UP and four from FB to DN (the edge detector's
        NAND and inverter, the set inverter, the latch's own NAND); four from CLK
        to FB through the retiming flip-flop alone; one charge-pump switch
        driver (`DN` drives its nfet gate directly, so there is no second); and
        the reset path's 27 common-mode stages -- the reset NAND, the first
        inverter, the 24-stage delay chain, the reset inverter -- plus two per
        side inside each latch.
        """
        n = {k: len(v) for k, v in _x.TIMING_PATHS.items()}
        self.assertEqual(n, {"pfd_ref_to_up": 4, "pfd_fb_to_dn": 4,
                             "divider_retime": 4, "cp_switch_driver": 1,
                             "pfd_reset_common": 27,
                             "pfd_reset_up_side": 2, "pfd_reset_dn_side": 2})

    def test_the_delay_chain_is_all_24_of_it(self):
        insts = [i for i, _ in _x.TIMING_PATHS["pfd_reset_common"]]
        for k in range(1, 25):
            self.assertIn(f"xpfd.xpfd.xd{k}", insts)

    def test_the_retime_path_is_inside_the_retiming_flipflop_only(self):
        insts = [i for i, _ in _x.TIMING_PATHS["divider_retime"]]
        self.assertTrue(all(i.startswith("xdiv.xfrt.") for i in insts), insts)

    def test_only_the_reset_path_is_common_mode(self):
        self.assertIn(_x.COMMON_MODE_PATH, _x.TIMING_PATHS)
        self.assertEqual(_x.COMMON_MODE_PATH, "pfd_reset_common")

    def test_every_path_has_a_block(self):
        self.assertEqual(set(_x.PATH_BLOCK), set(_x.TIMING_PATHS))

    def test_a_retyped_gate_is_refused(self):
        bad = _src().replace("xd7 RD6 RD7 VDD VSS pfdcp_inv_3v3",
                             "xd7 RD6 RD7 VDD VSS inv_3v3")
        self.assertNotEqual(bad, _src())
        with self.assertRaises(ValueError):
            _x.timing_path_claim(bad)

    def test_a_missing_gate_is_refused(self):
        with self.assertRaises(ValueError):
            _x.resolve_instance(_src(), "pll_top", "xpfd.xpfd.xd99")

    def test_resolve_walks_the_hierarchy(self):
        self.assertEqual(
            _x.resolve_instance(_src(), "pll_top", "xpfd.xpfd.xed_ref"), "edgedet")
        self.assertEqual(
            _x.resolve_instance(_src(), "pll_top", "xdiv.xfrt"), "dff_tg_3v3")


# ---------------------------------------------------------------------------
# 4: only single-stage cells are characterized
# ---------------------------------------------------------------------------
class SingleStageCells(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_cells_are_all_single_stage_leaves(self):
        self.assertTrue(set(_deck.CELLS).issubset(
            _deck.single_stage_cells(self.src)),
            sorted(set(_deck.CELLS) - _deck.single_stage_cells(self.src)))

    def test_xor2_is_not_characterized(self):
        """The cell whose self-biased `.noise` is its cascade's gain, not noise."""
        self.assertNotIn("xor2_3v3", _deck.CELLS)
        self.assertNotIn("xor2_3v3", _deck.single_stage_cells(self.src))

    def test_composites_are_not_single_stage(self):
        ss = _deck.single_stage_cells(self.src)
        for composite in ("xor2_3v3", "dff_tg_3v3", "div23_cell", "srlatch",
                          "edgedet", "delaywin_3v3"):
            self.assertNotIn(composite, ss, composite)

    def test_every_cell_a_path_names_is_characterized(self):
        for stages in _x.TIMING_PATHS.values():
            for _, cell in stages:
                self.assertIn(cell, _deck.CELLS, cell)

    def test_cell_ports_match_the_netlist(self):
        subs = _deck.subckts(self.src)
        for cell, spec in _deck.CELLS.items():
            decl = None
            for ln in self.src.splitlines():
                if ln.strip().lower().startswith(f".subckt {cell} "):
                    decl = ln.split()[2:]
            self.assertIsNotNone(decl, cell)
            self.assertEqual([p.upper() for p in spec["ports"].split()],
                             [p.upper() for p in decl], cell)
            self.assertIn(cell, subs)


# ---------------------------------------------------------------------------
# 5: the inequalities
# ---------------------------------------------------------------------------
class GatedChargeSpectrum(unittest.TestCase):
    """The adaptation the charge pump's pulsed duty cycle needs.

    For a white input density the windowed charge variance has the closed form
    `S t_on / 2` -- exactly the duty-cycle factor `t_on f_ref` below what a
    continuously-conducting source of the same density would deliver. That is
    the sentence the bound is allowed to use, so it is pinned against the
    closed form rather than against itself.
    """

    def setUp(self):
        self.f_ref = 25e6
        # 32 points per decade: the closed form below is exact, so what is left
        # is the log-trapezoid's own error on `sinc^2` around `1/t_on`, and the
        # tolerances here are set to see a broken WINDOW rather than to chase
        # that quadrature.
        self.freqs = _x.log_grid(1.0, 1e13, 32)

    def _var(self, s_white, t_on):
        lo_f, lo_s, flat, above = _x.gated_charge_spectrum(
            self.freqs, [s_white] * len(self.freqs), t_on=t_on, f_ref=self.f_ref)
        return _x.integrate_log(lo_f, lo_s) + above

    def test_white_input_matches_the_closed_form(self):
        for t_on in (1e-9, 2e-9, 5e-9):
            got = self._var(1e-24, t_on)
            want = 1e-24 * t_on / 2.0
            self.assertAlmostEqual(got / want, 1.0, delta=0.02, msg=f"{t_on=}")

    def test_the_duty_cycle_factor_is_what_it_claims(self):
        """`S t_on/2` against a full-cycle source's `S T_ref/2`: the duty."""
        t_on = 1.75e-9
        ratio = self._var(1e-24, t_on) / self._var(1e-24, 1.0 / self.f_ref)
        self.assertAlmostEqual(ratio, t_on * self.f_ref,
                              delta=0.05 * t_on * self.f_ref)

    def test_variance_grows_with_the_window(self):
        v = [self._var(1e-24, t) for t in (1e-9, 2e-9, 4e-9)]
        self.assertLess(v[0], v[1])
        self.assertLess(v[1], v[2])

    def test_a_zero_window_is_refused(self):
        with self.assertRaises(ValueError):
            _x.gated_charge_spectrum(self.freqs, [1e-24] * len(self.freqs),
                                     t_on=0.0, f_ref=self.f_ref)

    def test_a_grid_that_does_not_resolve_the_window_is_refused(self):
        short = _x.log_grid(1.0, 1e8, 8)          # 1/t_on = 5.7e8, needs 10x
        with self.assertRaises(ValueError):
            _x.gated_charge_spectrum(short, [1e-24] * len(short),
                                     t_on=1.75e-9, f_ref=self.f_ref)

    def test_the_grid_must_straddle_nyquist(self):
        hi = _x.log_grid(1e9, 1e13, 8)
        with self.assertRaises(ValueError):
            _x.gated_charge_spectrum(hi, [1e-24] * len(hi), t_on=1.75e-9,
                                     f_ref=self.f_ref)


class PeriodWeight(unittest.TestCase):
    def test_small_f_limit(self):
        """`4 sin^2(pi f/f0) -> (2 pi f/f0)^2`: the `(2 pi f T)^2` in the argument."""
        f0 = 150e6
        for f in (1e3, 1e4, 1e5):
            self.assertAlmostEqual(
                _x.period_weight(f, f0) / (2 * math.pi * f / f0) ** 2, 1.0,
                delta=1e-4)

    def test_the_quoted_in_band_value(self):
        """~3.4e-3 at 1.4 MHz against a 150 MHz output -- the README's figure."""
        self.assertAlmostEqual(_x.period_weight(1.4e6, 150e6), 3.44e-3, delta=5e-5)

    def test_zero_at_the_output_frequency(self):
        self.assertAlmostEqual(_x.period_weight(150e6, 150e6), 0.0, places=12)

    def test_maximum_at_half_the_output_frequency(self):
        self.assertAlmostEqual(_x.period_weight(75e6, 150e6), 4.0, places=12)


class SamplingFold(unittest.TestCase):
    def setUp(self):
        self.f_ref = 25e6
        self.freqs = _x.log_grid(1.0, 1e12, 8)

    def test_variance_is_conserved_and_never_understated(self):
        """The fold loses no variance, and errs by over-counting if at all.

        `f_ref/2` does not fall on a grid point, so the interval straddling it is
        counted in both halves rather than in neither (`_split_at`). The total
        after the fold is therefore >= the total before, never below it: a
        dropped sliver would make the bound quietly smaller than it claims.
        """
        s = [1e-24 / (1.0 + (f / 1e9) ** 2) for f in self.freqs]
        lo_f, lo_s, flat, above = _x.fold_to_nyquist(self.freqs, s, self.f_ref)
        total_before = _x.integrate_log(self.freqs, s) + _x.high_frequency_tail(
            self.freqs, s)
        total_after = _x.integrate_log(lo_f, lo_s) + flat * self.f_ref / 2.0
        self.assertGreaterEqual(total_after, total_before)
        self.assertAlmostEqual(total_after / total_before, 1.0, delta=5e-3)

    def test_the_flat_re_emission_is_the_independent_sequence_density(self):
        s = [1e-24 / (1.0 + (f / 1e9) ** 2) for f in self.freqs]
        _, _, flat, above = _x.fold_to_nyquist(self.freqs, s, self.f_ref)
        self.assertAlmostEqual(flat, 2.0 * above / self.f_ref, delta=1e-30)

    def test_in_band_shape_is_untouched(self):
        s = [1e-24 / f for f in self.freqs]
        lo_f, lo_s, _, _ = _x.fold_to_nyquist(self.freqs, s, self.f_ref)
        for f, v in zip(lo_f, lo_s):
            self.assertAlmostEqual(v, 1e-24 / f, delta=1e-40)

    def test_a_non_integrating_tail_is_refused(self):
        """A flat density at the grid top means the corner was never reached."""
        flat = [1e-24] * len(self.freqs)
        with self.assertRaises(ValueError):
            _x.high_frequency_tail(self.freqs, flat)

    def test_the_tail_of_a_measured_f_minus_2(self):
        f = _x.log_grid(1.0, 1e12, 8)
        s = [1e-6 / ff ** 2 for ff in f]
        # int_{f_hi}^inf s df = s(f_hi) f_hi / (2 - 1)
        self.assertAlmostEqual(
            _x.high_frequency_tail(f, s) / (s[-1] * f[-1]), 1.0, delta=1e-6)


class ClosedLoopTransfer(unittest.TestCase):
    """The transfer an input-referred source sees, against the one `../random-bound` uses.

    `|T/(1+T)|^2` and `|1/(1+T)|^2` are complementary: their square roots' phasors
    sum to 1, so `sqrt(a) + sqrt(b)` cannot be less than 1 and a loop that
    suppresses one passes the other. That is the reason this directory cannot
    reuse #520's envelope, and it is pinned here on the same loop objects.
    """

    def setUp(self):
        self.loops = _rb.admissible_loops(
            r_range=(8e3, 12e3), c1_range=(1.8e-9, 2.2e-9),
            c2_range=(180e-12, 220e-12), pm_min_deg=45.0)
        self.assertTrue(self.loops)

    def test_complementary_with_the_error_transfer(self):
        lp = self.loops[0]
        for f in (1e3, 1e5, 1e6, 1e7):
            g = math.sqrt(_x.closed_loop_sq(f, lp))
            e = math.sqrt(_rb.error_transfer_sq(f, lp))
            self.assertGreaterEqual(g + e, 1.0 - 1e-9, f"{f=}")

    def test_passes_in_band_and_rejects_out_of_band(self):
        lp = self.loops[0]
        self.assertGreater(_x.closed_loop_sq(1.0, lp), 0.99)
        self.assertLess(_x.closed_loop_sq(1e9, lp), 1e-6)

    def test_envelope_dominates_every_member(self):
        freqs = _x.log_grid(1.0, 1e8, 4)
        env = _x.closed_loop_envelope(freqs, self.loops)
        for lp in self.loops[:20]:
            for f, e in zip(freqs, env):
                self.assertGreaterEqual(e, _x.closed_loop_sq(f, lp) - 1e-12)


class CommonModeScale(unittest.TestCase):
    def test_the_measured_imbalance_when_it_dominates(self):
        got = _x.common_mode_scale(1.2e-6, 1.0e-6, floor=0.01)
        self.assertAlmostEqual(got["measured_imbalance"], 0.2, places=12)
        self.assertAlmostEqual(got["scale"], 0.2, places=12)
        self.assertEqual(got["set_by"], "measured")

    def test_the_floor_when_the_measurement_is_smaller(self):
        got = _x.common_mode_scale(1.745783e-6, 1.734613e-6)
        self.assertLess(got["measured_imbalance"], 0.01)
        self.assertAlmostEqual(got["scale"], _x.COMMON_MODE_IMBALANCE_FLOOR,
                               places=12)
        self.assertEqual(got["set_by"], "floor")

    def test_symmetric_in_its_two_arguments(self):
        a = _x.common_mode_scale(1.2e-6, 1.0e-6, floor=0.0)
        b = _x.common_mode_scale(1.0e-6, 1.2e-6, floor=0.0)
        self.assertAlmostEqual(a["scale"], b["scale"], places=12)

    def test_a_dead_leg_is_refused(self):
        with self.assertRaises(ValueError):
            _x.common_mode_scale(1e-6, 0.0)


class ChargeAndTiming(unittest.TestCase):
    def test_charge_to_phase_is_the_inverse_pd_gain(self):
        icp, tref = 1.7e-6, 40e-9
        k_pd = icp * tref / (2 * math.pi)        # coulombs per radian
        self.assertAlmostEqual(_x.charge_to_phase(icp, tref) * k_pd, 1.0, places=12)

    def test_timing_to_phase_does_not_depend_on_icp(self):
        tref = 40e-9
        for icp in (1e-7, 1e-6, 1e-5):
            self.assertAlmostEqual(
                _x.charge_to_phase(icp, tref) * icp / _x.timing_to_phase(tref),
                1.0, places=12)

    def test_a_full_reference_period_is_two_pi(self):
        self.assertAlmostEqual(_x.timing_to_phase(40e-9) * 40e-9, 2 * math.pi,
                               places=12)

    def test_edge_jitter_is_noise_over_slew(self):
        self.assertAlmostEqual(_x.edge_jitter(4.1e-3, 4.7e9), 4.1e-3 / 4.7e9,
                               places=20)

    def test_a_zero_slew_is_refused(self):
        with self.assertRaises(ValueError):
            _x.edge_jitter(1e-3, 0.0)

    def test_clk_loading_counts_two_independent_edges(self):
        got = _x.clk_loading_period_variance(sigma_v=1e-4, slew=4e10, f0_hz=1.5e8)
        sigma_t = 1e-4 / 4e10
        self.assertAlmostEqual(got["var"], 2.0 * (sigma_t * 1.5e8) ** 2, places=24)


class Assembly(unittest.TestCase):
    """The comparison is against the margin DR-032 leaves, not the whole budget."""

    def test_remaining_margin_is_the_quadrature_difference(self):
        got = _x.assemble_bound({"a": (1e-4) ** 2}, vco_bound_pct=0.338,
                                budget_pct=0.50)
        self.assertAlmostEqual(got["remaining_pct"],
                               math.sqrt(0.50 ** 2 - 0.338 ** 2), places=12)

    def test_terms_add_in_quadrature(self):
        got = _x.assemble_bound({"a": (3e-4) ** 2, "b": (4e-4) ** 2},
                                vco_bound_pct=0.3, budget_pct=0.5)
        self.assertAlmostEqual(got["in_band_pct"], 100.0 * 5e-4, places=10)

    def test_combined_is_the_whole_random_half(self):
        got = _x.assemble_bound({"a": (1e-3) ** 2}, vco_bound_pct=0.4,
                                budget_pct=0.5)
        self.assertAlmostEqual(got["combined_pct"],
                               math.sqrt(0.4 ** 2 + 0.1 ** 2), places=10)
        self.assertTrue(got["clears"])

    def test_it_does_not_clear_when_the_combination_exceeds_the_budget(self):
        got = _x.assemble_bound({"a": (4e-3) ** 2}, vco_bound_pct=0.4,
                                budget_pct=0.5)
        self.assertAlmostEqual(got["combined_pct"],
                               math.sqrt(0.4 ** 2 + 0.4 ** 2), places=10)
        self.assertFalse(got["clears"])

    def test_the_boundary_is_exactly_the_budget(self):
        """`clears` is strict: a combination that exactly spends it is not a pass."""
        got = _x.assemble_bound({"a": (3e-3) ** 2}, vco_bound_pct=0.4,
                                budget_pct=0.5)
        self.assertAlmostEqual(got["combined_pct"], 0.5, places=10)
        self.assertFalse(got["clears"])

    def test_headroom_is_remaining_over_in_band(self):
        got = _x.assemble_bound({"a": (1e-3) ** 2}, vco_bound_pct=0.3,
                                budget_pct=0.5)
        self.assertAlmostEqual(got["headroom"], got["remaining_pct"] / 0.1,
                               places=10)

    def test_a_vco_bound_outside_the_budget_is_refused(self):
        with self.assertRaises(ValueError):
            _x.assemble_bound({"a": 1e-8}, vco_bound_pct=0.6, budget_pct=0.5)


class PeriodVariance(unittest.TestCase):
    def test_zero_density_is_zero_variance(self):
        freqs = _x.log_grid(1.0, 1e7, 4)
        self.assertEqual(
            _x.period_variance(freqs, [0.0] * len(freqs), [1.0] * len(freqs),
                               f0_hz=1.5e8, n_div=6.0), 0.0)

    def test_scales_with_n_squared(self):
        freqs = _x.log_grid(1.0, 1e7, 4)
        s = [1e-12] * len(freqs)
        e = [1.0] * len(freqs)
        a = _x.period_variance(freqs, s, e, f0_hz=1.5e8, n_div=3.0)
        b = _x.period_variance(freqs, s, e, f0_hz=1.5e8, n_div=6.0)
        self.assertAlmostEqual(b / a, 4.0, places=9)

    def test_mismatched_lengths_are_refused(self):
        with self.assertRaises(ValueError):
            _x.period_variance([1.0, 2.0], [1.0], [1.0, 2.0], f0_hz=1e8, n_div=1.0)

    def test_a_flat_density_against_the_closed_form(self):
        """`int 4 sin^2(pi f/f0) df` over `0..F` with `env = 1`, `N = 1`.

        `= 2F - f0 sin(2 pi F/f0)/pi`, so the variance is that over `4 pi^2`.
        Integrated in `ln f` from a low enough floor that the omitted decade is
        negligible (the weight goes as `f^2`). What is left of the residual is
        the log-trapezoid's own error on an `f^2`-weighted integrand, which it
        over-states -- the conservative side -- so the tolerance is one-sided and
        loose enough not to chase quadrature.
        """
        f0, F = 1.5e8, 1.25e7
        freqs = _x.log_grid(1e2, F, 400)
        s = [1.0] * len(freqs)
        got = _x.period_variance(freqs, s, [1.0] * len(freqs), f0_hz=f0, n_div=1.0)
        want = (2 * F - f0 * math.sin(2 * math.pi * F / f0) / math.pi) / (4 * math.pi ** 2)
        self.assertGreaterEqual(got, want)
        self.assertAlmostEqual(got / want, 1.0, delta=1e-2)


# ---------------------------------------------------------------------------
# 6: the deck builders carry the committed netlist's own text
# ---------------------------------------------------------------------------
class Decks(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.op = dict(vsup=3.3, vctrl=1.795, temp_c=27.0, mos_section="typical",
                       res_section="res_typical", moscap_section="moscap_typical",
                       mimcap_section="mimcap_typical")
        self.freqs = _x.log_grid(1.0, 1e11, 4)

    def test_cp_deck_names_every_cp_device_once_per_frequency(self):
        deck, paths = _deck.cp_noise_deck(
            pdk_models="/nonexistent", repo_root=REPO, op=self.op, src=self.src,
            freqs=self.freqs, rsense=1e3, iunit=8e-6, cpb0=0, cpb1=0,
            switches_on=True)
        self.assertEqual(len(paths), len(_deck.flatten_mos(self.src, "cp", "xcp")))
        self.assertEqual(deck.count("\nnoise v(vout)"), len(self.freqs))
        # One `setplot` per call, naming that call's OWN integrated plot: without
        # it every call reprints the first one's numbers (ngspice resolves the
        # vector in whichever plot it finds first).
        for k in range(1, len(self.freqs) + 1):
            self.assertIn(f"setplot noise{2 * k}\n", deck)
        self.assertEqual(deck.count("\nprint onoise_total_rsense_thermal"),
                         len(self.freqs))

    def test_cp_deck_switch_levels(self):
        on, _ = _deck.cp_noise_deck(
            pdk_models="/x", repo_root=REPO, op=self.op, src=self.src,
            freqs=self.freqs, rsense=1e3, iunit=8e-6, cpb0=0, cpb1=0,
            switches_on=True)
        off, _ = _deck.cp_noise_deck(
            pdk_models="/x", repo_root=REPO, op=self.op, src=self.src,
            freqs=self.freqs, rsense=1e3, iunit=8e-6, cpb0=0, cpb1=0,
            switches_on=False)
        self.assertIn("vup up 0 dc 'vsup'", on)
        self.assertIn("vup up 0 dc 0", off)

    def test_noise_band_edges_are_distinct_at_the_grid_top(self):
        """A 1 Hz band must still be two distinct numbers at 10^14 Hz.

        At 12 significant digits `f` and `f+1` print identically past 10^12, the
        band collapses, and ngspice does a single-frequency measurement that
        creates no integrated plot at all -- so every call after that point
        fails with `no such plot`.
        """
        top = _x.log_grid(1.0, 1e14, 4)
        deck, _ = _deck.gate_load_deck(
            pdk_models="/x", repo_root=REPO, op=self.op,
            src=(REPO / "design" / "netlist" / "div23_cell.spice").read_text(),
            freqs=top, r_drive=1e3, load="clk")
        for ln in deck.splitlines():
            if ln.startswith("noise v(clk)"):
                tok = ln.split()
                self.assertNotEqual(tok[4], tok[5], ln)

    def test_gate_load_decks_count_only_the_load_devices(self):
        for load, netlist, cell in (("clk", "div23_cell.spice", "div23_cell"),
                                    ("up", "pll_top.spice", "xor2_3v3")):
            src = (REPO / "design" / "netlist" / netlist).read_text()
            deck, paths = _deck.gate_load_deck(
                pdk_models="/x", repo_root=REPO, op=self.op, src=src,
                freqs=self.freqs, r_drive=1e3, load=load)
            self.assertEqual(paths, _deck.flatten_mos(src, cell, "xld"))
            self.assertIn("rdrv drv", deck)
            self.assertEqual(deck.count("\nprint onoise_total_rdrv_thermal"),
                             len(self.freqs))

    def test_digital_deck_holds_vctrl_through_a_resistor(self):
        deck, cols = _deck.digital_deck(
            pdk_models="/x", repo_root=REPO, op=self.op,
            config={b: 0 for b in _deck.CONFIG_BITS}, iunit=8e-6, fref=25e6,
            tstop=180e-9, tstep=25e-12, tmax=25e-12, r_hold=1.0)
        self.assertIn("vvc vchold 0 dc 'vc'", deck)
        self.assertIn("rvchold vchold vctrl 1", deck)
        self.assertIn("v(vctrl)", cols)

    def test_digital_deck_reference_delay_is_settable(self):
        kw = dict(pdk_models="/x", repo_root=REPO, op=self.op,
                  config={b: 0 for b in _deck.CONFIG_BITS}, iunit=8e-6,
                  fref=25e6, tstop=180e-9, tstep=25e-12, tmax=25e-12)
        unaligned, _ = _deck.digital_deck(**kw)
        aligned, _ = _deck.digital_deck(**kw, ref_delay=4.055e-8)
        self.assertIn("pulse(0 'vsup' '0.5*tref'", unaligned)
        self.assertIn("pulse(0 'vsup' 4.055000e-08", aligned)

    def test_digital_columns_name_parent_nets_not_child_ports(self):
        """`v(xdut.xdiv.xd1.ckout)` is not a vector: ngspice does not alias ports."""
        cols = _deck.digital_columns()
        self.assertIn("v(xdut.xdiv.ck1)", cols)
        self.assertFalse([c for c in cols if "ckout" in c], cols)

    def test_cell_noise_deck_carries_a_units_anchor(self):
        entries = [("inv_3v3", 1.6, "inv_3v3@+0.00")]
        deck, groups = _deck.cell_noise_deck(
            pdk_models="/x", repo_root=REPO, op=self.op, entries=entries,
            freqs=self.freqs, cload=50e-15, src=self.src)
        self.assertIn("ranch anch anchy", deck)
        self.assertEqual(deck.count("\nprint onoise_total_ranch_thermal"),
                         len(self.freqs))
        # The `.noise` input source needs an AC value or every call aborts.
        self.assertIn("vin0 a0 0 dc 1.6 ac 1", deck)
        self.assertEqual(set(groups), {"inv_3v3@+0.00"})

    def test_cell_instances_are_disjoint_subnetworks(self):
        entries = [("inv_3v3", 1.6, "a"), ("nand2_3v3", 1.5, "b")]
        deck, groups = _deck.cell_noise_deck(
            pdk_models="/x", repo_root=REPO, op=self.op, entries=entries,
            freqs=self.freqs[:2], cload=50e-15, src=self.src)
        self.assertIn("vin0 a0 0 dc 1.6 ac 1", deck)
        self.assertIn("vin1 a1 0 dc 1.5", deck)
        self.assertEqual(set(groups["a"]) & set(groups["b"]), set())

    def test_flatten_mos_does_not_walk_into_the_vco_from_the_divider(self):
        """`XD0 VCO MI0 ... div23_cell`'s second token is the NET `VCO`.

        Resolving a model left to right would match the subcircuit of the same
        name and count the whole oscillator as part of the divider.
        """
        div = _deck.flatten_mos(self.src, "divider_chain")
        vco = set(_deck.flatten_mos(self.src, "vco"))
        self.assertTrue(div)
        self.assertEqual(set(div) & vco, set())

    def test_gate_loads_declare_a_cell_this_netlist_has(self):
        subs = _deck.subckts(self.src)
        div = _deck.subckts(
            (REPO / "design" / "netlist" / "div23_cell.spice").read_text())
        for spec in _deck.GATE_LOADS.values():
            self.assertTrue(spec["cell"] in subs or spec["cell"] in div,
                            spec["cell"])


if __name__ == "__main__":
    unittest.main()
