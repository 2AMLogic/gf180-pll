# `period-jitter` S_id along the trajectory — the other two ingredients

**This directory produces no jitter number, and nothing in it belongs in
`spec/pll.md`.** It builds the two ingredients of the
impulse-sensitivity-function (ISF) route to random period jitter that
[`../isf-bringup/`](../isf-bringup/) did not — each ring device's
channel-thermal and flicker generator PSD *at the bias it actually occupies at
phase `x` of the oscillation*, and the trajectory `(V_gs, V_ds, V_bs)(x)` it is
evaluated along — and it measures the one number
[#520](https://github.com/2AMLogic/gf180-pll/issues/520)'s option **(B)** is
required to state before any calibrated-`trnoise()` figure may be published:

> it must state up front which bias point each amplitude was calibrated at and
> bound the error that stationary approximation costs — without that bound it is
> the uncalibrated figure DR-020 refuses.

That bound is now measured, in dB, per device class, per generator, at three PVT
points, and — at the one point where a committed `h` exists — against the
`h²`-weighted average the jitter integral actually contains rather than against a
plain cycle average.

Run it:

```sh
sim/period-jitter/sid-trajectory/run.py                  # ~2 min, one core, three corners
sim/period-jitter/sid-trajectory/summarize.py \
    > sim/period-jitter/sid-trajectory/results/SUMMARY.md
```

One ngspice process at a time, sequentially — this host is a shared dispatch
worker. Every number quoted below is in
[`results/SUMMARY.md`](results/SUMMARY.md), regenerated from
[`results/*.json`](results/) by `summarize.py` rather than transcribed by hand.

<!-- toc -->

- [Where this sits in the ISF route](#where-this-sits-in-the-isf-route)
- [Method](#method)
- [What it found](#what-it-found)
- [What this does NOT establish](#what-this-does-not-establish)
- [Files](#files)

## Where this sits in the ISF route

[`DR-023`](../../../spec/decision-records/DR-023-random-period-jitter-owner-and-cyclostationary-gap.md)
and
[`DR-020`](../../../spec/decision-records/DR-020-random-period-jitter-is-not-obtainable-on-this-toolchain.md)
located the gap precisely: ngspice-46 *does* hand over each device's thermal and
flicker generators at a bias point (`.noise`, per device, per mechanism), and this
build has *no* periodic-steady-state analysis to weight them over the oscillation
trajectory (`pss: no such command available in ngspice`). The ISF route is the
hand-built substitute for that missing weighting:

```
var(ΔT) = (1 / ω₀²) · ½ · ∫₀ᵀ h_gen(t)² · S_i(t) dt      summed over noise sources
```

for a noise current of one-sided PSD `S_i`, where `h(x) = Γ(x)/q_max` is the phase
shift per unit injected charge in rad/C and `h_gen` is the *two-terminal* ISF of a
generator that sits between a device's drain and its source.

| Ingredient | Status |
|---|---|
| **`h(x)`** — phase shift per unit injected charge, per node, across the cycle | [`../isf-bringup/`](../isf-bringup/), and [`DR-030`](../../../spec/decision-records/DR-030-isf-gamma-converges-and-the-gap-moves-to-the-remaining-two-ingredients.md): converged against timestep, with the linear window a property of the phase |
| **`h_gen(x)`** — the same for a two-terminal generator | `../isf-bringup/` at **six** phases for the two switching devices; **exactly and at 12 phases** for the two current-source devices, because their source is an ideal rail — see [What it found](#what-it-found) |
| **`S_id(x)`** — each ring device's thermal and flicker generator at the bias it traverses | **this directory** |
| **the trajectory** — `(V_gs, V_ds, V_bs, I_d, g_m, g_ds)(x)` per device | **this directory** |
| the assembly, over the mandated 45-point PVT grid | not built — [What this does NOT establish](#what-this-does-not-establish) |

Note what the second row changed. The route's most-feared term, the
near-cancelling `h(source) − h(drain)` of a switching device, does not arise at
all for the two current-source devices: `XMPH`'s source is `VDD`, `XMNT`'s is
`VSS`, both ideal sources in the ISF deck, and charge injected into an ideal
source does not move the node. So `h(VDD) = h(VSS) = 0` identically and
`|h_gen| = |h(drain)|` — a quantity `../isf-bringup/`'s `nodes` stage already
measured, with no subtraction and therefore no precision loss.

## Method

Two decks, and they are a pair.

**1. The trajectory deck is the ISF bring-up's own reference deck.** It is not
re-derived here: `sid_deck.trajectory_deck()` calls
`../isf-bringup/isf_deck.build_deck()` with one VCO copy and no injection —
byte-for-byte the deck that directory's `period` stage runs — and adds only a
`save`/`wrdata` column list naming each ring device's operating-point vectors.
That matters because the phase axis of the committed `h(x)` table is
`t = 40 ns + x·T` on *that* deck's own adaptive timestep sequence; sampling the
bias trajectory out of a second, nominally-equivalent deck would put the two
ingredients of the jitter sum on two phase axes whose relative offset nobody
measured. The measured periods agree to **−3.7 × 10⁻⁶** relative, which is the
check that they are in fact one axis.

The `save` card is the load-bearing half of that addition, and its absence fails
*silently*: a device operating-point expression such as `@m.x0.xs1.xmn.m0[vgs]`
that is named only on `wrdata` comes back **frozen at its DC value** for every
timepoint — the column varies not at all, the run exits 0, and nothing announces
it.

**2. The noise deck is one ring device, alone, biased at a triple lifted off that
trajectory, with `.noise` run on it.** Four things about it are deliberate:

- **The device line is the committed netlist's own text** for that instance, not a
  hand-written `nfet_03v3 W=2u L=0.28u`. The drawn `ad`/`as`/`pd`/`ps` set the
  junction geometry, `nrd`/`nrs` set the terminal-resistance noise generators, and
  `sa`/`sb`/`sd` set the stress corrections to the channel ones — so a
  hand-written line measures a different device than the ring contains.
  ([`../noise-toolchain-probe/probe_sid_bias.sp.in`](../noise-toolchain-probe/probe_sid_bias.sp.in)
  does write it by hand, correctly for what it is: a 1-D existence probe.)
- **A 1 A AC current source sits between drain and source** purely to measure the
  transimpedance `Z_m = |v(d)|` from a drain-to-source current to the output node.
  `.noise` reports each generator's contribution to the *output voltage*; the
  pipeline needs the generator's own *drain-current* PSD, so the reduction divides
  by `Z_m`. Because that probe is also the `.noise` input source,
  `inoise_total.<gen>` is the same quantity by an independent route, and both are
  computed and compared on every run (they agree to ≤ 1.7 × 10⁻⁶).
- **Every `.noise` runs in a 1 Hz band.** ngspice's integrated (`noise2`, `noise4`,
  …) plot holds noise integrated over the analysis band in V RMS, so a band of
  exactly 1 Hz makes the integrated number equal the spectral density. Writing the
  upper edge as `f·(1+ε)` instead of `f + 1` silently widens the band in proportion
  to `f`, so every mechanism appears to rise as `√f` together — including a plain
  resistor's thermal noise, which cannot. That error occurred during this bring-up
  and `sid_extract.units_anchor()` is what caught it: the sense resistor's own
  thermal contribution is re-derived in closed form on *every* `.noise` call, and
  the runner refuses the whole PVT point if it disagrees by more than 0.5 %.
- **The bias is settled in two passes, on an observed residual.** Series
  resistances sit between the deck's ideal sources and the bias ngspice reports:
  the sense resistor, and the device's own `rd`/`rs` (measured here at
  0.18–1.26 Ω, recovered from the noise deck's own operating point rather than
  read off a model card). The offsets are **not** computed from the closed form
  `I_d·(rd + rs + rsense)`, because that form has no fixed **sign**: a ring
  device's `V_ds` crosses zero twice per cycle, BSIM4 swaps source and drain
  internally for `V_ds < 0`, the reported `I_d`'s sign therefore stops following
  `V_ds` there, and the two p-type devices add a polarity flip on top. The runner
  instead takes one Newton step on each *observed* residual, which is
  sign-agnostic, and it **measures the alternative in both signs** rather than
  arguing about it — see [What it found](#what-it-found) §1. What the Newton step
  leaves is reported, not assumed: **≤ 7.2 µV** on all three voltages and
  **≤ 8.9 × 10⁻⁶** relative on `I_d`, `g_m` and `g_ds`, at every one of the 288
  (device, phase, PVT) points.

That last residual settles a second question by measurement, worth naming because
the deck would otherwise have to assume it away: ngspice's *transient*
`@m…[id]` agreeing with a standalone `op`'s to ~10⁻⁵ means it **is** the channel
current at the sampled timepoints, not channel plus `dQ_d/dt`.

**Why the `S_id` grid snaps to solved timepoints.** `I_d`, `g_m` and `g_ds` are
nonlinear functions of `(V_gs, V_ds, V_bs)`, so interpolating all six columns
independently to a requested phase yields a row whose current is *not* the current
of its own bias triple. The noise deck is built from the triple and then checked
against the current, so an interpolated row would fail that check by the
interpolation error instead of by anything about the probe. The grid therefore
takes the nearest *stored* timepoint unmodified, at a cost of ≤ 1.5 × 10⁻⁴ of a
cycle in phase, reported as `phase_cycles_actual`; the 4×-finer trajectory trace,
which nothing is rebuilt from, is interpolated. How much that choice is worth is
measured, not assumed — see [What it found](#what-it-found) §1, and note there
that the measurement only sees it at one of the four sampled phase classes.

**Why three PVT points and not 45.** This directory characterises a *method* and
reports no design number, the same standing as `../isf-bringup/` and
`../noise-toolchain-probe/`; it mints no evidence record and appears in no
coverage table. But unlike a convergence question, the *size* of the
cyclostationary variation is corner-dependent — measured here at 74–115 dB of span
for the same device across three corners — so a single point could not show that
the stationary-approximation cost is a property of the ring rather than of one
operating point. Three points (the reference point the ISF bring-up and the
deterministic period-jitter records share, plus the slowest/coldest-supply and
fastest/hottest-supply extremes of the mandated grid, each released at its own
committed 150 MHz control voltage) is what answers that. The mandated 45-point
grid is owed by the *assembled* pipeline, on the batch fleet through
`sim/harness`.

## What it found

Numbers are from [`results/SUMMARY.md`](results/SUMMARY.md).

### 1. The extraction is anchored, not argued

| Check | Question | Result |
|---|---|---|
| Units anchor | Is the reported density a density, in the units the reduction assumes? | **Yes, to 3 × 10⁻⁷.** The sense resistor's own thermal contribution is re-derived from `√(4kTR·bw)·Z_m/R` on *every* `.noise` call, and the runner aborts the PVT point if it is outside 0.5 %; over the 2016 calls that make up the three committed `S_id` tables, measured/expected is 0.9999997–1.0000000. |
| Two normalisations | Does `(onoise/Z_m)²` agree with ngspice's own `inoise²`? | **Yes, to ≤ 1.7 × 10⁻⁶.** So "`inoise_total` is the input-referred density" is measured here, not cited. |
| Network independence | Does the extracted `S_id` depend on the sense resistance it was measured through? | **No, to ≤ 0.93 %** over **10⁷** in sense resistance (1 mΩ → 10 kΩ), at the peak-, median- and minimum-`I_d` phases of all three corners. |
| Bias reproduction | Did the trajectory's bias triple land on the right terminals with the right polarity? | **Yes**: ≤ 7.2 µV on `V_gs`/`V_ds`/`V_bs` and ≤ 8.9 × 10⁻⁶ relative on `I_d`/`g_m`/`g_ds`, over all 288 (device, phase, corner) points. This is the only check available on a p-type sign error, a dropped `V_bs` or an uncorrected sense drop — each of which leaves `.noise` perfectly happy and the resulting table smooth and wrong. |
| Physics bracket | Is `g_n = S_id/4kT` inside the textbook range for the channel it came from? | **Yes**: 0.13–1.15 times `max(g_m, g_ds, I_d/2V_T)` at every point. |
| Thermal whiteness | Is the channel-thermal generator white? | **Exactly**, to machine precision, over 1 kHz–300 MHz. |
| Flicker exponent | What is the flicker slope, and is it `1/f`? | **`S ∝ f^−0.94997`**, fitted over seven frequencies spanning 1 kHz–300 MHz with ≤ 2 × 10⁻⁴ dex of residual — i.e. a pure power law, and **not** `α = 1`. Reported rather than assumed because `fnoimod = 1` in the gf180mcu BSIM4 cards is the unified flicker model. |

And two *deck choices*, measured rather than argued, at four phases of every
device class — the peak-, median- and minimum-`|I_d|` phases plus the phase where
`I_d` moves fastest:

- **The bias offsets are a Newton step, not `I_d·R`.** The Newton step leaves
  ≤ 2.6 × 10⁻⁶ relative on `I_d` at every one of the 48 (device, phase, corner)
  points. The closed form leaves up to 5.5 × 10⁻⁴ with one sign and up to
  3.2 × 10⁻³ with the other — and **which sign is the better one changes with the
  device and with the phase**: at the reference corner `−I_d·R` wins on `XMPH`'s
  deep-triode phase and loses by 3200× on `XMN`'s. That is the whole argument for
  a sign-agnostic construction, and it is now a measurement rather than an
  argument.
- **Snapping the `S_id` grid to solved timepoints is worth two and a half orders,
  at one phase class out of four.** The snapped row's own internal inconsistency
  is ~1 × 10⁻⁶ everywhere. The interpolated row's is indistinguishable from it at
  the reference corner's peak/median/min phases, and reaches 8.2 × 10⁻⁵ (reference)
  to 5.0 × 10⁻⁴ (slow/hot) at the **steepest** phase. **The fourth phase is what
  made this measurable**: a three-phase check at the reference corner finds nothing
  and would have licensed the conclusion that snapping is unnecessary. Worth
  recording as a methodology point in its own right — a check whose phase set is
  chosen for interpretability rather than for sensitivity can return a clean
  result and mean nothing.

### 2. The five ring stages are one trajectory shifted by 0.6 of a cycle, not 0.2

A jitter sum that measures `h` and `S_id` on one stage and multiplies by the stage
count assumes the stages are one trajectory, displaced in time. The shift is
**measured** here, by scanning it, and the topological prediction is worth stating
because the obvious guess is wrong: in an `N`-stage ring of *inverting* stages the
oscillation takes one inversion per lap, so `T = 2·N·t_d` and one stage's delay is
`T/(2N)`; the next stage's waveform is that delayed *and inverted*, and for a
waveform whose half-cycles are alike, inverted is the same as shifted by `T/2`.
The stage-to-stage shift is therefore `1/(2N) + 1/2` = **0.6** of a cycle for
`N = 5`, not `1/N = 0.2`.

Getting this wrong does not look like an error. The first version of this check
compared at `1/5`, put nearly-antiphase waveforms against each other, and returned
a residual of **98 % of the peak-to-peak swing** — which reads exactly like a ring
whose stages are not replicas. Scanning the shift is what distinguishes a
statement about the stages from a statement about the prediction:

- The best-fit shift lands within **0.006 of a cycle** of the predicted 0.6 per
  stage, at a scan resolution of 0.0026, for every ring-phase-dependent quantity
  at all three corners.
- At that shift the stages agree to **≤ 7.4 % of peak-to-peak on `V_gs`** (≤ 2.3 %
  RMS) and **≤ 40 % peak / ≤ 7.6 % RMS on `I_d`**. They are *not* identical: stage
  5's output also drives the output buffer chain, a load the other four do not
  carry. The peak `I_d` figure is set by the switching instant, where the current
  is a spike a few sampled phases wide, so the RMS figure is the one to quote.
- **The two current-source devices' `V_gs` is the exception that confirms the
  reading**: their gate sits on the *shared* bias net `VBP`/`VBN`, so all five
  stages see the same gate ripple with **no** stage shift, and the scan duly finds
  its best fit at shift 0 rather than 0.6, with a residual ≤ 0.3 % of that
  ripple's 6–14 mV. Their `V_ds` swings with the ring and their `I_d` carries the
  0.6 shift like everything else.

### 3. The cyclostationary variation is large, corner-dependent, and its raw span is the wrong number to quote

At 1 MHz, over the sampled phases, `10·log10(max/min)` of the channel-thermal
generator is **1.7–2.1 dB** for the two current-source devices and **67–115 dB**
for the two switching devices; for the flicker generator, 56–86 dB and
121–223 dB. The corner dependence is the point: the same device (`XMP`, thermal)
spans 74.3 dB at slow/hot and 114.7 dB at fast/cold. A single-corner
characterisation could not have said whether the span is a property of the ring or
of one operating point.

But those spans are set by the phases where the device is **off**, which
contribute nothing to any integral, so the span is a statement about the size of
the variation and **not** the error a usable single-bias choice makes. That error
is the per-convention figure, and it is much smaller — and it is what option (B)
owes.

### 4. The bound option (B) owes: against the *weighted* average, "calibrate at peak |I_d|" is good to 1.2 dB for thermal and 5.7 dB for flicker

This is the directory's load-bearing result, and it needs the distinction between
two averages to state. Substituting a constant `S₀` into the jitter integral makes
it wrong by `S₀ / S_eff`, where

```
S_eff = Σ h_gen² S_id / Σ h_gen²
```

is the `h²`-**weighted** cycle average — not the plain `⟨S⟩` that a reader with
only this directory's `cost` stage would compare against. The two differ, and not
by a sign one could guess: the ISF weighting pushes the effective **thermal**
density **down** by 1.0–4.1 dB and the effective **flicker** density **up** by
3.3–5.2 dB relative to `⟨S⟩`. So the unweighted figure is not a bound on the
weighted one in either direction.

Against `S_eff`, at the reference corner:

| Single-bias convention | channel-thermal error | channel-flicker error |
|---|---|---|
| at the device's **peak \|I_d\|** phase | **−1.15 … +1.06 dB** | +1.16 … +5.67 dB |
| at its **minimum \|I_d\|** phase | +1.6 dB (current sources) / −74 … −89 dB (switching) | −60 … −183 dB |
| at the phase nearest its **mean `V_gs`** | +0.9 … +3.3 dB | −50.7 … +1.0 dB |

Read that first row carefully, because it is the useful one and it is not
obvious. The naive calibration choice — "bias the device where it carries its peak
current" — is within **1.2 dB** of the correctly-weighted channel-thermal
generator for all four device classes, i.e. within 0.77–1.28× in PSD and
**0.88–1.13× in jitter RMS**. Against the *unweighted* average the same choice is
1.05–3.81 dB off at the same corner. The ISF weighting concentrates on the switching edge, which is
where the switching devices carry their peak current — so the weighting and the
convention happen to agree, and only a measurement could have said so.

For the flicker generator it is 5.7 dB at worst, and the flicker term has a
deeper problem than its calibration: a period-jitter RMS from a `1/f^α` generator
is not defined until an observation interval is, and `spec/pll.md`'s Period jitter
row does not state one. That is why the flicker density is reported at each
measured frequency plus a measured exponent and is never integrated here.

The resolution caveat belongs next to the result rather than below it: `n_eff`,
the effective number of phases setting `S_eff`, is **2.4 of 12** for the two
current-source devices and 7.2 of 24 for the two switching ones. The weight is
sharply peaked, so the rows whose weight is *exact* are exactly the rows whose
phase resolution is *coarsest*. A finer `h_gen(x)` grid is the first thing the
assembly needs.

## What this does NOT establish

Stated as a list because each line is a reason no jitter number appears here, and
a reader who skips them will over-read what is above.

- **No random period-jitter number is produced, at any corner.** The integral is
  not evaluated. `spec/pll.md`'s Verification-owed row is unchanged by this
  directory, still owned by #520, and `docs/chipalooza/challenge-5-proposal.md` §5
  still reads **UNMET** against the random component — correctly.
- **DR-023 and DR-020 are not overtaken.** DR-023 §Decision 2's falsification
  trigger, as narrowed by DR-030, is *a pipeline — all three ingredients,
  assembled, with its stationary-approximation error bounded — demonstrating
  convergence, or `pss` resolving.* `pss` still does not resolve. Two of the three
  ingredients now exist and the error is now bounded; the **assembly** does not
  exist, so the trigger has not fired.
- **The switching devices' weight here is a declared shape proxy, not their
  `h_gen`.** `XMP`'s and `XMN`'s channel generators sit between two *ring* nodes.
  DR-030 measured that residue at 1.54 % of the larger term and rejected building
  it by subtraction of two per-node tables; the direct two-terminal measurement
  exists at six phases, not at the 24 the `S_id` grid uses. So `h(Y)` stands in as
  a weight *shape* for those two rows, flagged `exact: false` in the JSON and in
  the summary, and **no jitter contribution is claimed from them**. Only the two
  current-source rows carry a weight that is the generator's own.
- **`S_id` is tabulated for one stage, at 24 phases, for four device classes.**
  The stage-symmetry measurement above is what licenses multiplying by five, and
  it licenses it to ~8 % RMS in `I_d`, not exactly.
- **The VCO bias generator's own devices are not here.** `vco_bias` is a couple of
  dozen devices injecting noise onto `VBP`/`VBN`, and neither its `S_id` nor an `h`
  for those nodes is measured. A sum over the four `vco_stage` classes alone would
  be a *lower* bound presented as a result. Section 2's finding sharpens this
  rather than softening it: the current sources' `V_gs` ripple is *common to all
  five stages*, so bias-net noise enters all five identically instead of
  incoherently, and a common-mode injection does not average down the way five
  independent ones would.
- **Only the two channel generators are tabulated.** `.noise` also reports the
  `rd`/`rg`/`rs` terminal-resistance generators for these devices; they are
  printed in the logs and are not in the table.
- **The flicker term is never integrated**, for want of a stated observation
  interval — see above.
- **Mismatch is off and there is no Monte Carlo.** Same limitation the
  deterministic `sim/period-jitter` records carry.
- **Schematic-level only**: no layout parasitics. Both ingredients depend on them
  — `h` scales against a ring node's capacitance, and `S_id` is evaluated at a
  trajectory that capacitance sets.

## Files

| File | What it is |
|---|---|
| [`sid_deck.py`](sid_deck.py) | The two decks: the trajectory deck (delegated to `../isf-bringup/isf_deck.build_deck`, plus operating-point columns) and the standalone-device `.noise` deck, whose device line is the committed netlist's own text |
| [`sid_extract.py`](sid_extract.py) | The reduction: `wrdata` → trajectory, noise log → `S_id` two ways, the units anchor, the physics bracket, the flicker exponent, the measured stage shift, and the two stationary-approximation costs (plain and `h²`-weighted) |
| [`run.py`](run.py) | The five stages, sequentially, one ngspice process at a time |
| [`summarize.py`](summarize.py) | `results/*.json` → [`results/SUMMARY.md`](results/SUMMARY.md) |
| [`results/`](results/) | The committed evidence this directory's claims rest on, including the `S_id` and trajectory tables themselves |
| [`logs/`](logs/) | Captured ngspice output for every deck; the per-phase `sid` runs are consolidated one file per (point, device) in phase order. This directory is **committed evidence**, un-ignored by name in the repository's `.gitignore`, so `run.py`'s log destination follows `--outdir`: a `--quick --outdir /tmp/...` smoke test writes to `/tmp/.../logs`. It did not always — an early revision pinned `logs/` here, and a smoke run overwrote the committed full-run output of the point it touched while exiting 0 |
| `sim/tests/test_sid_trajectory.py` | The deck derivation and the reduction, pinned off any simulator (runs in `sim/selftest.sh`) |
