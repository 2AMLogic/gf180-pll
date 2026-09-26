# `period-jitter` random component — bounded, over the 45-point grid

**This directory puts an upper bound on the random (noise-driven) period jitter
of the locked output at every point of the mandated PVT grid**, which is what
`spec/pll.md`'s [Period jitter](../../../spec/pll.md#period-jitter) row owed at
[#520](https://github.com/2AMLogic/gf180-pll/issues/520). It is #520's option
**(B)** — a calibrated `trnoise()` injection — in the one form that option can
take without an ISF table: calibrated at each generator's **maximum over its own
trajectory**, which turns the stationary approximation's error from a two-sided
unknown into a one-sided, provable over-estimate. The decision record is
[`DR-032`](../../../spec/decision-records/DR-032-random-period-jitter-bounded-over-the-grid.md).

<!-- RESULT-HEADLINE -->

Run it:

```sh
sim/period-jitter/random-bound/grid.sh 6        # all 45 points, 6 side by side; hours
sim/period-jitter/random-bound/run.py --point typical_27c_3.30v \
    --stage trajectory --stage sid --stage bias --stage transient   # one point
sim/period-jitter/random-bound/summarize.py > sim/period-jitter/random-bound/results/SUMMARY.md
```

Every number quoted below is in [`results/SUMMARY.md`](results/SUMMARY.md),
regenerated from [`results/*.json`](results/) by `summarize.py`.

<!-- toc -->

- [The idea: three inequalities](#the-idea-three-inequalities)
- [Method](#method)
- [What it found](#what-it-found)
- [What this does NOT establish](#what-this-does-not-establish)
- [Files](#files)

## The idea: three inequalities

A bound is only as good as the inequalities under it, so they are stated before
anything is measured. Each is proved in the docstring of the function that
applies it in [`rb_extract.py`](rb_extract.py), and each has a test in
`sim/tests/test_random_bound.py`.

**1. Cyclostationary white → stationary white, one-sided.** A white generator
whose density follows the device's bias, `S(t)`, contributes

```
var(ΔT) = (1/ω₀²) · ½ · ∫ h(t)² S(t) dt
```

to one period's variance, with `h(t)² ≥ 0` whatever the impulse sensitivity
function `h` is. So a **stationary** injection at any `S_inj ≥ max_t S(t)`
produces **at least** that variance. The transient integrates the ring's true
`h` itself — no ISF table is read — and the only thing that has to be right is
that `S_inj` really is the maximum. That is why every switching device's
density is sampled along its own trajectory down to the trajectory's own 2 ps
resolution around its peaks, why each bias-generator device's is raised by its
own sampled span, and why the maximum's convergence against sampling
resolution is reported per point.

This is the bound #520 asked option (B) to state, and it is not the one DR-031
measured. DR-031 compared a **peak-|I_d|** calibration with the `h²`-weighted
average `S_eff` and found it within ±1.2 dB — two-sided, at one corner, on a
weight with 2.4 effective phases, and it declined to license a number on it. A
**maximum** does not need to be close to `S_eff`; it only needs to be above it,
and it is by construction.

**2. Flicker → white, through the loop.** A flicker generator
`S(t, f) = m(t)² K f^−α` has no finite single-period variance for `α ≥ 1` in a
free-running oscillator — the integral diverges at DC — and this matters here,
because the pfet cards set `ef = 1.12`. The row is not stated free-running,
though: it is stated **in lock**, and in lock the loop multiplies each spectral
component of the free-running period deviation by its error transfer
`|1/(1 + T(j2πf))|²`, which falls as `f⁴` below crossover. With that, and two
facts true of any period-deviation functional `g` (Cauchy–Schwarz and Parseval),
the flicker generator is dominated by a **white** generator with the same
modulation and density `Φ · S(t, F)`,

```
Φ = 2 T_w F^α ∫₀^F f^−α env(f) df + sup_{f≥F} env(f),     F = 0.475 f₀,
```

where `env` is the upper envelope of `|1/(1+T)|²` over **every** loop the
as-built filter admits at the ratified 45° phase-margin floor, and
`T_w = 1.1 T` is the period plus a margin for the output buffer, whose
generators move one edge rather than the ring's phase. So the flicker half is
folded into the same white injection, **with no observation interval**: the
bound is the stationary variance, which every finite window's expected sample
variance is at most (`flicker_factor`).

**3. Open loop → closed loop.** The transient runs the VCO free-running; in lock
the loop can raise a white generator's period variance only inside a band
around its crossover, a few MHz wide against a white generator's spread past
`f₀/2`. The factor is `1 + 2 T_w ∫ (env − 1)₊ df` (`white_loop_factor`), about
1.08 — not the envelope's 2.57 peak, which is reported beside it. The
loop-filter resistor, which the VCO transient does not contain, is bounded
separately through the control node by equipartition, `kT·C1/(C2(C1+C2))` of
voltage variance (`kt_over_c_bound`), times the envelope's peak and the
measured `K_vco`.

## Method

**What is injected into.** Every noise-generating device in one `vco`
instance, derived from the committed `design/netlist/vco.spice` at deck-build
time ([`rb_deck.py`](rb_deck.py)): the ring's 20 MOS devices (4 per stage × 5
stages), the 36 MOS devices and 3 poly resistors of the bias generator
`vco_bias`, and the output buffer's 6 MOS devices. The two MOS decoupling
capacitors are excluded on purpose: both their terminals sit on the testbench's
ideal supply, so their noise is shorted. Noise elements are appended **inside**
derived copies of `vco_stage` (one per stage, so the five stages' amplitudes are
separate quantities), `vco_bias` and `vco`, because ngspice will not connect a
top-level element to a subcircuit's internal net; every device line is the
committed netlist's own text. `CLK` is loaded by one real `div23_cell` with its
mode pins static — the same first divider cell that is `CLK`'s only load in
`pll_top`.

**The operating point.** Each point of `sim/period-jitter/testbench/tb.json`'s
45-point grid, read from that manifest rather than retyped, released at the
point's own 150 MHz control voltage, band 6. So both halves of the Period
jitter row are measured at the same 45 points.

**The trajectory** (stage `trajectory`). One clean VCO copy at a 2 ps ceiling —
the ISF bring-up's converged setting — with every device's `V_gs, V_ds, V_bs,
I_d, g_m, g_ds` saved (a `save` card, not only `wrdata`: an unsaved
`@m…[…]` column comes back frozen at its DC value), sampled on a 3072-point
phase grid (2.17 ps) by snapping to solved timepoints. Two more clean copies at
`V_ctrl ± 10 mV` measure `K_vco` at the operating point on the same timestep
sequence.

**The densities** (stage `sid`). Every device, standalone, at a trajectory
timepoint, each in its own sub-network with its own ideal bias sources, sense
resistor and 1 A AC probe. The sub-networks are disjoint, so one deck holds
many of them — every device at several phases — and one `.noise` per
frequency, referred to the sum of every drain voltage through unit-gain
VCVSs, reports each device's contribution separately (the `validate` stage
compares this against one `.noise` per device on a single-phase deck). One
Newton step on the observed bias residual (`../sid-trajectory/`'s method); the
standalone device must reproduce the in-situ `I_d` to 10⁻³ or the point is
refused, and each sub-network's sense resistor must reproduce its own
closed-form thermal noise to 0.5 % on every call or the point is refused. The
density used is ngspice's per-**device** total (channel thermal, flicker and
the `rd`/`rs`/`rg` terminal generators), split into its white part and its
flicker part at `F = 0.475 f₀`; the flicker exponent is measured at every row
from a second frequency, 1 MHz. Three rounds:

| Round | Devices | Phases |
|---|---|---|
| A | all 65 | 48 uniform (139 ps) |
| B | the 26 switching devices (ring, output buffer) | 384 uniform (17 ps) |
| C | the same 26 | every 2.17 ps step between the round-B neighbours of each device's three largest round-B local maxima |

A switching device's injection density is its maximum over all three rounds;
C over B is reported per point as the maximum's convergence against sampling
resolution. A bias-generator device is quasi-DC — its round-A span is
reported — and its injection density is its round-A maximum raised by that
same span, a margin that covers any excursion between samples no larger than
the samples themselves show.

The **poly resistors** get no `.noise`: the PDK models the body resistance as a
voltage-dependent expression, which ngspice turns into a behavioural source and
treats as **noiseless** — `.noise` reports only the two ~33 Ω terminal
segments. Their resistance is measured (`V/I`) and the thermal density is
`4kT/R`; their flicker is the card's own `KF·|I|^AF/f` on all three segments.

**The injection** (stage `transient`). `trnoise(NA NT 0 0)` across each
channel, drain to source, with `NA = √(S_inj / 2NT)`, `NT = 10 ps`. `S_inj` is
the device's maximum over its trajectory; the ring's is the maximum over the
class across all five stages. Four noisy copies and one clean reference copy
share one deck and so one timestep sequence; 60 periods per copy after 40 ns of
settling. `rndseed` is set per point, but on this build it does not reproduce a
`trnoise` realisation (see Validation), so a re-run reproduces the statistics,
not the sequence. The period is rising-edge to rising-edge at mid-supply on `CLK`. The
figure carried forward is the pooled standard deviation's one-sided 95 % upper
confidence limit.

**Calibration of the tool** (stage `calibrate`). `trnoise` into
`1 Ω ∥ 1 nF` over 4 µs at three sample intervals, against the closed-form
variance `S R/(4C)` of a white current of one-sided density `S = 2 NA² NT`; and
the correlation between two instances, which must be zero for the copies to be
independent realisations.

**Validation** (stage `validate`, reference point). Nine independent decks of
the transient stage's own shape, each compared statistically with that stage's
result: the same deck again (`repeat`), a 2.5 ps timestep ceiling, `trnoise`
sample intervals of 5 and 20 ps at equal density, every amplitude × 3, the
flicker parts removed, and each block (ring, bias generator, buffer) alone.
Statistically, because a period-by-period comparison on one shared realisation
is not available: on this build fixing `rndseed` does not reproduce a
`trnoise` realisation — `repeat` is the evidence. And the noise deck's summed,
multi-phase form against one `.noise` per device.

<!-- RESULT-BODY -->

## What this does NOT establish

Each of these is a limit of the bound, stated so that nobody has to infer it.

- **It is an upper bound, not an estimate.** The random period jitter of this
  PLL is *at most* the figure per point; how far below it the true value sits
  is not measured here. Two of the three inequalities are loose on purpose —
  every generator is injected at its trajectory maximum for the whole cycle,
  and the flicker factor `Φ` is taken over every loop the as-built filter
  admits at the 45° floor, crossovers down to ~14 kHz, not the loop the trim
  rule selects. A bound that clears the budget clears it; a bound that did not
  would have said nothing about the part.
- **Which generators it covers.** Every MOS channel (with its `rd`/`rs`/`rg`
  terminal generators) and every resistor in `vco` — ring, bias generator,
  output buffer — and the loop-filter resistor. It does **not** cover the
  charge pump, the PFD, the feedback divider or the lock detector. Those are
  in-band sources: they reach the output only through the closed loop's
  low-pass transfer, whose bandwidth (≤ 1.4 MHz over every admissible loop) is
  ~1 % of `f₀`, and period jitter is the first difference of phase, which
  attenuates in-band phase by `(2π f T)²` — ≈ 3.4 × 10⁻³ at 1.4 MHz. That is
  an argument for why they are small, not a bound on them; it is the scope
  DR-002 Decision 5 itself specified ("a transient-noise testbench dominated
  by the VCO plus a jitter-transfer argument through the closed loop"), and it
  is stated as a scope, not as a result. The reference source is excluded by
  `spec/pll.md` (DR-019).
- **Schematic level, ideal supply.** No layout parasitics; the supply and
  control sources are ideal, which is also why the two MOS decoupling
  capacitors are noiseless here. Supply-borne noise is the supply-ripple
  campaign's quantity, not this one's.
- **The PDK's noise models, as the PDK states them.** BSIM4 channel thermal
  and flicker, per device, from `.noise`; flicker treated as a
  modulated-stationary process (`S(t, f) = m(t)² K f^−α`), the model every
  periodic-noise analysis uses. The poly resistors' body flicker uses the
  card's own `KF`/`AF`, which `.noise` cannot report for a behavioural body.
- **One output frequency.** 150 MHz, band 6 — the same operating point as the
  deterministic half of the row, and not the 200 MHz band top, which is
  #503's campaign for the deterministic half and is not covered here either.
- **Linear response.** The bound's first inequality is a small-signal
  statement; the `validate` stage's 3× amplitude run is what shows the ring
  responds linearly at the injected level.

## Files

| File | What it is |
|---|---|
| [`rb_deck.py`](rb_deck.py) | Device catalogue and all three decks, derived from the committed netlist |
| [`rb_extract.py`](rb_extract.py) | Periods and statistics, the noise-deck parse and anchors, the three inequalities, the loop model and the assembled bound — no simulator |
| [`run.py`](run.py) | The six stages; one point per invocation |
| [`grid.sh`](grid.sh) | The 45-point driver |
| [`summarize.py`](summarize.py) | `results/*.json` → [`results/SUMMARY.md`](results/SUMMARY.md) |
| [`results/`](results/) | The committed evidence |
| [`logs/`](logs/) | ngspice output: every trajectory and transient deck, the calibration, the validation decks, and — at the reference point — the noise decks of the phases that set an injection density |
| `sim/tests/test_random_bound.py` | Derivation, bound arithmetic and statistics, pinned off any simulator |
