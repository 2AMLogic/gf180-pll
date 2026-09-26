# `period-jitter` random component — bounded, over the 45-point grid

**This directory puts an upper bound on the random (noise-driven) period jitter
of the locked output at every point of the mandated PVT grid**, which is what
`spec/pll.md`'s [Period jitter](../../../spec/pll.md#period-jitter) row owed at
[#520](https://github.com/2AMLogic/gf180-pll/issues/520). It is #520's option
**(B)** — a calibrated `trnoise()` injection — in the one form that option can
take without an ISF table: each generator calibrated at its **maximum over its
own trajectory**, which turns the stationary approximation's error from a
two-sided unknown into a one-sided over-estimate. The bias generator, whose
noise has a memory of many periods, is bounded by a small-signal analysis
instead, where that analysis is exact. The decision record is
[`DR-032`](../../../spec/decision-records/DR-032-random-period-jitter-bounded-over-the-grid.md).

**Result: the random period jitter is at most 0.338 % RMS at every one of
the 45 mandated PVT points** (worst `sf`/−40 °C/2.97 V), against the 0.50 % RMS
`spec/pll.md` allocates to it — a 1.48× margin. It is an upper bound, not
an estimate, and it does not cover the charge pump, PFD, divider or lock
detector; see [What this does NOT establish](#what-this-does-not-establish).

Run it:

```sh
sim/period-jitter/random-bound/grid.sh 6        # all 45 points, 6 side by side; hours
sim/period-jitter/random-bound/run.py --point typical_27c_3.30v \
    --stage trajectory --stage sid --stage bias --stage transient   # one point
sim/period-jitter/random-bound/summarize.py > sim/period-jitter/random-bound/results/SUMMARY.md
```

Every number quoted below is in [`results/SUMMARY.md`](results/SUMMARY.md),
regenerated from [`results/*.json`](results/) by `summarize.py`.

- [The idea](#the-idea)
- [Method](#method)
- [What it found](#what-it-found)
- [What this does NOT establish](#what-this-does-not-establish)
- [Files](#files)

## The idea

A bound is only as good as the inequalities under it, so they are stated before
anything is measured. Each is derived in the docstring of the function that
applies it in [`rb_extract.py`](rb_extract.py), and each has a test in
`sim/tests/test_random_bound.py`.

The generators split into two kinds, and the split is measured, not assumed.
The **ring's and the output buffer's** act within about a period: noise in one
period changes that period and, by moving an edge before the ring has settled
back to its limit cycle, the next one in the opposite sense — the period
sequence of a transient with only those generators injected has a *negative*
lag-1 autocorrelation. The **bias generator's** act through VBP and VBN, slow
nets shared by all five stages, so they move the frequency for many periods —
alone, they give a *positive* lag-1 autocorrelation. The first kind is bounded
by a transient; the second by a small-signal analysis.

**1. Cyclostationary white → stationary white, one-sided** (ring and buffer). A
white generator whose density follows the device's bias, `S(t)`, contributes

```
var(ΔT) = (1/ω₀²) · ½ · ∫ h(t)² S(t) dt
```

to one period's variance, with `h(t)² ≥ 0` whatever the impulse sensitivity
function `h` is. So a **stationary** injection at any `S_inj ≥ max_t S(t)`
produces **at least** that variance. The transient integrates the ring's true
`h` itself — no ISF table is read — and the only thing that has to be right is
that `S_inj` really is the maximum. That is why every switching device's
density is sampled along its own trajectory down to the trajectory's own 2 ps
resolution around its peaks, and why the maximum's convergence against sampling
resolution is reported per point.

This is the bound #520 asked option (B) to state, and it is not the one DR-031
measured. DR-031 compared a **peak-|I_d|** calibration with the `h²`-weighted
average `S_eff` and found it within ±1.2 dB — two-sided, at one corner, on a
weight with 2.4 effective phases, and it declined to license a number on it. A
**maximum** does not need to be close to `S_eff`; it only needs to be above it,
and it is by construction.

**2. Flicker → white, through the loop** (ring and buffer). A flicker generator
`S(t, f) = m(t)² K f^−α` has no finite single-period variance for `α ≥ 1` in a
free-running oscillator — the integral diverges at DC — and this matters here,
because the pfet cards set `ef = 1.12`. The row is not stated free-running,
though: it is stated **in lock**, and in lock the loop multiplies each spectral
component of the free-running period deviation by its error transfer
`|1/(1 + T(j2πf))|²`, which falls as `f⁴` below crossover. With that, and two
facts true of any period-deviation functional `g` supported on a window `T_w`
(Cauchy–Schwarz and Parseval), the flicker generator is dominated by a **white**
generator with the same modulation and density `Φ · S(t, F)`,

```
Φ = 2 T_w F^α ∫₀^F f^−α env(f) df + sup_{f≥F} env(f),     F = 0.475 f₀,
```

where `env` is the upper envelope of `|1/(1+T)|²` over **every** loop the
as-built filter admits at the ratified 45° phase-margin floor (1606 loops,
crossovers 14 kHz – 1.4 MHz). `T_w = 2T`: the period, plus a whole period for the
edge memory the negative lag-1 autocorrelation shows; a memory longer than that
would make the lag-2 autocorrelation non-zero, and it is reported for every
point. `Φ` = 20.5 / 25.5 / 45.7 at α = 0.95 / 1.0 / 1.12. So the flicker half is
folded into the same white injection, **with no observation interval**: the
bound is on the stationary variance of the locked period sequence, and no
finite window's expected sample variance (about the window's own mean) exceeds
it.

**3. Open loop → closed loop** (ring and buffer). The transient runs the VCO
free-running; in lock the loop can raise a white generator's period variance
only inside a band around its crossover, a few MHz wide against a white
generator's spread past `f₀/2`. The factor is `1 + 2 T_w ∫ (env − 1)₊ df`
(`white_loop_factor`) = 1.142 — not the envelope's 2.571 peak.

**4. The bias generator, small-signal.** It is quasi-DC — every one of its
devices' noise densities moves by ≤ 0.24 dB over the cycle — so it is analysed
where a small-signal analysis is exact: `.noise` about its DC operating point,
loaded as in the VCO, with the output taken as the ring's instantaneous
frequency deviation `δf = K_p v(VBP) + K_n v(VBN)` through the ring's measured
static sensitivities. One period's deviation is `−T²` times `δf` averaged over
the period, so

```
var(ΔT)/T² ≤ (1/f₀²) [ ∫₀^{f₀/2} S_δf sinc²(f/f₀) env df + max(env) ∫_{f₀/2}^∞ S_δf sinc²(f/f₀) df ]
```

with the bias generator's own flicker spectrum in `S_δf` — no `Φ`, no window
(`lti_period_variance`). The quasi-static reading of the ring's response is
the model's assumption, and the `validate` stage tests it against the circuit:
the bias generator's white generators injected in the transient must reproduce
the model's open-loop white prediction.

**5. The loop-filter resistor**, which the VCO decks do not contain, is bounded
through the control node by equipartition, `kT·C1/(C2(C1+C2))` of voltage
variance (`kt_over_c_bound`), times the envelope's peak and the measured
`K_vco`.

The terms are independent and add in quadrature.

## Method

**What is injected into.** Every noise-generating device in one `vco`
instance, derived from the committed `design/netlist/vco.spice` at deck-build
time ([`rb_deck.py`](rb_deck.py)): the ring's 20 MOS devices (4 per stage × 5
stages) and the output buffer's 6 MOS devices in the transient; the 36 MOS
devices and 3 poly resistors of the bias generator `vco_bias` in the
small-signal deck. The two MOS decoupling capacitors are excluded on purpose:
both their terminals sit on the testbench's ideal supply, so their noise is
shorted. Noise elements are appended **inside** derived copies of `vco_stage`
(one per stage, so the five stages' amplitudes are separate quantities),
`vco_bias` and `vco`, because ngspice will not connect a top-level element to a
subcircuit's internal net; every device line is the committed netlist's own
text. `CLK` is loaded by one real `div23_cell` with its mode pins static — the
same first divider cell that is `CLK`'s only load in `pll_top`.

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
sequence. A deck whose solver stalls in its first nanosecond (one point did,
deterministically, at t = 45 fs) is re-run with the symmetry-breaking initial
condition moved by up to 100 mV; the oscillator forgets it within the 40 ns of
settling, and the offset used is recorded.

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
resolution. The bias generator's round A is what shows it quasi-DC, and feeds
the validation's comparison.

**The bias generator** (stage `bias`). Its cycle-average VBP, VBN and each
stage's `NH`/`NT` from the trajectory. The ring's static sensitivities
`K_p = ∂f/∂V_BP`, `K_n = ∂f/∂V_BN` from one deck of six clean copies: the VCO
as it is, the VCO with VBP/VBN held by ideal sources at their averages (which
must reproduce its frequency), and ± 5 mV on each. Then `.noise` of `vco_bias`
alone, 1 Hz – 10 GHz, VBP loaded by five `XMPH`s and VBN by five `XMNT`s (the
committed device text, drains held at the stages' average `NH`/`NT` — so the nets
see the ring's gate capacitance, and the loads' own channel noise, which the
transient carries, flows into an ideal source), output `K_p v(VBP) + K_n v(VBN)`.
The **poly resistors' bodies** need one addition: the PDK models the body as a
voltage-dependent expression, which ngspice turns into a behavioural source and
treats as **noiseless** — `.noise` reports only the two ~33 Ω terminal
segments. So each gets a dummy resistor of the body's value carrying the
body's DC current (thermal `4kT/R`, flicker the card's own `KF·|I|^AF/f` on all
three segments), whose short-circuit noise current a noiseless CCCS mirrors
across the real resistor, the mirrored DC current cancelled by an ideal source.

**The injection** (stage `transient`). `trnoise(NA NT 0 0)` across each ring
and output-buffer channel, drain to source, with `NA = √(S_inj / 2NT)`,
`NT = 10 ps`. `S_inj` is the device's maximum over its trajectory of
`S_white + Φ(α)·S_flicker(F)`; the ring's is the maximum over the class across
all five stages. Four noisy copies and one clean reference copy share one deck
and so one timestep sequence; 60 periods per copy after 40 ns of settling. The
period is rising-edge to rising-edge at mid-supply on `CLK`. The figure carried
forward is the pooled standard deviation's one-sided 95 % upper confidence
limit. `rndseed` is set per point, but on this build it does not reproduce a
`trnoise` realisation (see Validation), so a re-run reproduces the statistics,
not the sequence.

**Calibration of the tool** (stage `calibrate`). `trnoise` into
`1 Ω ∥ 1 nF` over 4 µs at three sample intervals, against the closed-form
variance `S R/(4C)` of a white current of one-sided density `S = 2 NA² NT`; and
the correlation between two instances, which must be zero for the copies to be
independent realisations.

**Validation** (stage `validate`, reference point). Nine independent decks of
the transient stage's own shape, each compared statistically with that stage's
result: the same deck again (`repeat`), a 2.5 ps timestep ceiling, `trnoise`
sample intervals of 5 and 20 ps at equal density, every amplitude × 3, the
flicker parts removed, the ring and the buffer each alone — and the bias
generator's white generators alone, against the `bias` stage's open-loop white
prediction. Statistically, because a period-by-period comparison on one shared
realisation is not available: on this build fixing `rndseed` does not
reproduce a `trnoise` realisation — `repeat` is the evidence. And the noise
deck's summed, multi-phase form against one `.noise` per device.

## What it found

Every figure here is in [`results/SUMMARY.md`](results/SUMMARY.md). The
points ran at two recorded repository heads, `1c57daf4` and `89ead93d`; between
them only this README changed, and nothing under `design/` or
`sim/period-jitter/` was modified at run time at any point (both recorded per
point).

- **The bound clears the allocation everywhere**: 0.255 … 0.338 % RMS over the 45
  points, worst `sf`/−40 °C/2.97 V at 0.338 %, a 1.48× margin on 0.50 %.
  Its three terms: ring and output buffer 0.106 … 0.188 %, bias generator
  0.229 … 0.281 %, loop-filter resistor ≤ 0.0056 %.
- **The bias generator sets it.** Its term is the largest at every point —
  69–83 % of the bound's variance — because VBP and VBN are shared by all
  five stages, so each of its generators reaches every stage at once, and
  coherently. That is the place to look if this bound ever needs to
  be tighter, or the design quieter.
- **The window the ring/buffer factors assume holds.** With only the ring's and
  buffer's generators injected, the period sequence's lag-1 autocorrelation is
  -0.258 … +0.160 and its lag-2 -0.117 … +0.127 over the grid (standard error ≈ 0.065 each) —
  no memory beyond the next period. The bias generator's white generators
  alone, by contrast, give +0.43 at the reference point: the memory that
  is why it is analysed small-signal.
- **The maximum is resolved.** Sampling each switching device's density at the
  trajectory's own 2.17 ps around its peaks raised its 17 ps-sampled maximum
  by at most 8.6 %; a 48-phase grid alone would have missed the output
  buffer's peak by up to 8.1×.
- **The transient measures what it claims** (reference point, as ratios of
  independent decks to the transient's own result): 2.5 ps timestep ceiling
  1.028 ± 0.067; `trnoise` sample interval 5 / 20 ps 1.061 ± 0.069 and 1.126 ± 0.073; every amplitude × 3
  3.161 ± 0.206; the same deck again 1.114 ± 0.073; the ring's and buffer's
  variance shares sum to 1.104 ± 0.14. White generators alone carry 0.54
  of the ring/buffer variance — the rest is the flicker folded in through `Φ`.
- **The bias generator's model is conservative against the circuit**: its
  white generators injected in the transient give 0.910 ± 0.042 of the model's
  open-loop white prediction — the model over-states them, the safe direction
  for a bound.
- **Two toolchain facts.** Fixing `rndseed` does not reproduce a `trnoise`
  realisation on this build (same deck run twice: correlations +0.172, +0.342, +0.053, +0.069, where a
  reproduced realisation would give 1), so every comparison is statistical.
  And the summed, multi-phase noise deck reports each device exactly as a
  per-device `.noise` does — identical in every printed digit.

## What this does NOT establish

Each of these is a limit of the bound, stated so that nobody has to infer it.

- **It is an upper bound, not an estimate.** The random period jitter of this
  PLL is *at most* the figure per point; how far below it the true value sits
  is not measured here. The ring/buffer half is loose on purpose — every
  generator is injected at its trajectory maximum for the whole cycle, `Φ` is
  taken over every loop the as-built filter admits at the 45° floor
  (crossovers down to ~14 kHz, not the loop the trim rule selects), and the
  window allows a full extra period of memory. A bound that clears the budget
  clears it; a bound that did not would have said nothing about the part.
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
  is stated as a scope, not as a result. Bounding them is #580's. The
  reference source is excluded by `spec/pll.md` (DR-019).
- **The bias generator's term rests on a model**, not on a transient: its
  noise through a quasi-static ring response, the ring's gate loading at the
  stages' average bias. The `validate` stage checks that model against the
  circuit at the reference point only, and on its white generators only.
- **Schematic level, ideal supply.** No layout parasitics; the supply and
  control sources are ideal, which is also why the two MOS decoupling
  capacitors are noiseless here. Supply-borne noise is the supply-ripple
  campaign's quantity, not this one's.
- **The PDK's noise models, as the PDK states them.** BSIM4 channel thermal
  and flicker, per device, from `.noise`; flicker treated as a
  modulated-stationary process (`S(t, f) = m(t)² K f^−α`), the model every
  periodic-noise analysis uses. The poly resistors' body noise uses the
  card's own `KF`/`AF` and `4kT/R`, which `.noise` cannot report for a
  behavioural body.
- **One output frequency.** 150 MHz, band 6 — the same operating point as the
  deterministic half of the row, and not the 200 MHz band top, which is
  #503's campaign for the deterministic half and is not covered here either.
- **Linear response.** The ring/buffer half is a small-signal statement; the
  `validate` stage's 3× amplitude run is what shows the ring responds
  linearly at the injected level.

## Files

| File | What it is |
|---|---|
| [`rb_deck.py`](rb_deck.py) | Device catalogue and every deck — trajectory, noise, transient, bias sensitivity, bias small-signal — derived from the committed netlist |
| [`rb_extract.py`](rb_extract.py) | Periods and statistics, the noise-deck parse and anchors, the inequalities, the loop model, the small-signal integral and the assembled bound — no simulator |
| [`run.py`](run.py) | The seven stages; one point per invocation |
| [`grid.sh`](grid.sh) | The 45-point driver |
| [`summarize.py`](summarize.py) | `results/*.json` → [`results/SUMMARY.md`](results/SUMMARY.md) |
| [`results/`](results/) | The committed evidence |
| [`logs/`](logs/) | ngspice output: every trajectory, bias and transient deck, the calibration and the validation decks (the `sid` stage's noise decks stay in the work area; every check made on them is in `results/sid_*.json`) |
| `sim/tests/test_random_bound.py` | Derivation, bound arithmetic and statistics, pinned off any simulator |
