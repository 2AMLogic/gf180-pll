# DR-031: The ISF route's remaining two ingredients are built, and the stationary-approximation bound #520's option (B) owes is measured — 1.2 dB for the thermal generator at one corner, and not transferable

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-030 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-26
- **Decided by**: Builder agent, issue #520
- **Relationship to DR-030, DR-023 and DR-020**: **narrows nothing further and
  supersedes nothing.** DR-030 narrowed DR-023 Decision 2's falsification clause
  to *"a pipeline — all three ingredients, assembled, with its
  stationary-approximation error bounded — demonstrates convergence, or `pss`
  resolves"*. This record reports that the **ingredients** now exist and the
  **bound** now exists. The **assembly** does not, and `pss` still does not
  resolve, so the trigger has not fired. DR-023, DR-020 and DR-002 Decision 5 are
  untouched.

## Context

`spec/pll.md`'s [Period jitter](../pll.md#period-jitter) row targets ≤ 1.0 % of
the output period, RMS. Its deterministic half is measured at all 45 mandated PVT
corners (0.0508–0.2691 % RMS, PASS at every one). Its random half has no record.
DR-020 and DR-023 record why: ngspice-46 *does* report each device's
channel-thermal and flicker generators per device and per mechanism (`.noise`),
and has no periodic-steady-state analysis (`pss` is not a command in this build)
to weight them over the ring's own switching trajectory.

DR-030 brought up the first of the three ingredients an
impulse-sensitivity-function (ISF) route needs — `h(x) = Γ(x)/q_max` — showed it
converges against the internal-timestep ceiling, and named what the next
increment owed:

> `S_id(V_gs, V_ds)` per ring device class, evaluated along the ring's own
> trajectory rather than at a chosen bias point; the trajectory itself; … the
> assembly … and then the 45-point grid on the batch fleet.

`sim/period-jitter/sid-trajectory/` is those first two, at three PVT points, plus
one thing DR-030 did not ask for and #520's option (B) does: *the error a
stationary single-bias `S_id` costs*, measured against the `h²`-weighted average
the jitter integral actually contains rather than against a plain cycle average.
Every number below is regenerated from committed JSON into
[`results/SUMMARY.md`](../../sim/period-jitter/sid-trajectory/results/SUMMARY.md)
by `summarize.py`; none is transcribed.

The extraction is anchored rather than argued, and this is the precondition for
anything else in the record:

| Check | Question | Result |
|---|---|---|
| Units anchor | Is the reported number a spectral density, in the units the reduction assumes? | **Yes, to 3 × 10⁻⁷.** The sense resistor's own thermal contribution is re-derived from `√(4kTR·bw)·Z_m/R` on every `.noise` call and the run is **refused** outside 0.5 %. It fired during bring-up: an upper band edge written `f·(1+1e-7)+1` instead of `f+1` made every mechanism appear to rise as `√f` together — including a resistor's, which cannot. |
| Two normalisations | Does `(onoise/Z_m)²` agree with ngspice's own `inoise²`? | **Yes, ≤ 1.7 × 10⁻⁶.** So "`inoise_total` is the input-referred density" is measured here, not cited. |
| Network independence | Does the extracted `S_id` depend on the network it was measured through? | **No, ≤ 0.93 % over 10⁷** in sense resistance (1 mΩ → 10 kΩ). |
| Bias reproduction | Did the trajectory's bias triple land on the right terminals with the right polarity? | **Yes**: ≤ 7.2 µV on `V_gs`/`V_ds`/`V_bs`, ≤ 8.9 × 10⁻⁶ relative on `I_d`/`g_m`/`g_ds`, at all 288 (device, phase, corner) points. |
| Physics bracket | Is `g_n = S_id/4kT` inside the range the channel allows? | **Yes**, 0.13–1.15 × `max(g_m, g_ds, I_d/2V_T)` everywhere. |
| Frequency dependence | Is thermal white, and what is the flicker slope? | Thermal **exactly** white over 1 kHz–300 MHz; flicker `S ∝ f^−0.94997` with ≤ 2 × 10⁻⁴ dex of residual — a pure power law, and **not** `α = 1`. |

## Decision

**1. The two remaining ingredients exist, and the ISF route now lacks only its
assembly.** `S_id` for channel-thermal and flicker, per ring device class, at 24
phases of the oscillation, at three PVT points of the mandated grid, together with
the `(V_gs, V_ds, V_bs, I_d, g_m, g_ds)(x)` trajectory it is evaluated along at 96
phases. The trajectory is sampled out of **the ISF bring-up's own reference
deck** — `sid_deck.trajectory_deck()` calls
`../isf-bringup/isf_deck.build_deck()` and adds only a column list — so the two
ingredients sit on one phase axis by construction rather than by coincidence; the
two decks' measured periods agree to **−3.7 × 10⁻⁶**. That was the design
constraint, not a nicety: `h(x)`'s phase convention is `t = 40 ns + x·T` on that
deck's own adaptive timestep sequence, and a second nominally-equivalent deck
would have put the two ingredients on two axes whose relative offset nobody
measured.

**2. The bound #520's option (B) owes is measured, and the correctly-weighted
version of it is the one that matters — but it holds at one corner only.** This
is the record's load-bearing result and it has three parts, in the order they
bind.

- **The raw cyclostationary span is not the bound, and quoting it as one would
  overstate the problem by orders of magnitude.** At 1 MHz the channel-thermal
  generator spans 1.7–2.1 dB over the cycle for the two current-source devices and
  **67–115 dB** for the two switching devices (flicker: 56–86 dB and 121–223 dB).
  Those spans are set by the phases where the device is **off** and contribute
  nothing to any integral.
- **The plain cycle average is not the right reference either.** Substituting a
  constant `S₀` into `var(ΔT) = (1/ω₀²)·½·∫h_gen²S_i dt` makes the integral wrong
  by `S₀/S_eff` where `S_eff = Σh²S/Σh²`, and the ISF weighting is not flat: it
  moves the effective **thermal** density **down** by 1.0–4.1 dB and the effective
  **flicker** density **up** by 3.3–5.2 dB relative to `⟨S⟩`. So the unweighted
  figure bounds the weighted one in neither direction.
- **Against `S_eff`, the naive calibration convention is good to 1.2 dB for
  thermal.** Biasing each device at its own **peak-|I_d|** phase reproduces the
  `h²`-weighted channel-thermal generator to **−1.15 … +1.06 dB** for all four
  device classes — 0.77–1.28× in PSD, **0.88–1.13× in jitter RMS**. Against the
  unweighted average the same choice is 1.05–3.81 dB off. The two happen to agree
  because the ISF weighting concentrates on the switching edge, which is where the
  switching devices carry their peak current; only a measurement could have said
  so, and the two other conventions tried are far worse (mean `V_gs`: +0.9 … +3.3 dB
  thermal and −50.7 … +1.0 dB flicker; minimum `I_d`: −60 … −183 dB flicker).

  **What this licenses and what it does not.** It licenses #520's option (B) to be
  *built* with a stated error bound on its thermal term, which DR-020 and DR-023
  refused it without. It does **not** license a jitter number, for three reasons
  this record states rather than leaves to a reader: the bound is measured at the
  **one** PVT point where a committed `h` exists, and the unweighted spans vary by
  40 dB across the three corners, so it may not transfer; `n_eff` — the effective
  number of phases setting `S_eff` — is only **2.4 of 12** for the two device
  classes whose weight is exact; and the flicker term has the separate problem in
  Decision 5.

**3. Two of the four device classes need no `h_gen` subtraction at all, and that
relocates DR-030's precision problem rather than solving it.** DR-030's Decision 3
established that a channel generator's ISF is `h(source) − h(drain)`, that on this
ring the two terms cancel to 1.54 % of the larger, and that a pipeline must
therefore inject the two-terminal generator directly. That reasoning applies to the
two **switching** devices. It does not apply to the two **current-source** devices:
`XMPH`'s source is `VDD`, `XMNT`'s is `VSS`, both ideal sources in the deck
(`vdd vdd 0 dc 'vsup'`; `VSS` is node 0), and charge injected into an ideal source
does not move the node — so `h(source) = 0` identically and `|h_gen| = |h(drain)|`,
a quantity `../isf-bringup/`'s `nodes` stage already measured with no subtraction
and no precision loss. `sim/tests/test_sid_trajectory.py` pins those terminal
assignments against the committed netlist, because the argument is only as good as
the topology it assumes.

The relocation is the finding, and it is not comfortable: the two classes whose
weight is **exactly** available are measured on the **coarsest** phase grid (12
phases, `n_eff` 2.4), while the two whose grid is finer (24 phases) have no
`h_gen` at that resolution at all. A finer `h_gen(x)` for all four classes is
therefore the first thing the assembly needs, ahead of anything else on DR-030's
list.

**4. The ring's five stages are one trajectory shifted by 0.6 of a cycle, not
0.2 — and the current sources' gate ripple is not shifted at all.** A jitter sum
that measures one stage and multiplies by five assumes the stages are one
trajectory displaced in time. Recorded as a decision because getting the shift
wrong does not look like an error: in an `N`-stage ring of *inverting* stages the
oscillation takes one inversion per lap, so `T = 2N·t_d`, one stage's delay is
`T/(2N)`, and the next stage's waveform is that delayed **and inverted** — for a
waveform whose half-cycles are alike, the same as a further `T/2`. The shift is
`1/(2N) + 1/2` = **0.6**, and the first version of this check compared at `1/N`
= 0.2, put nearly-antiphase waveforms against each other, and reported a residual
of **98 % of peak-to-peak** — which reads exactly like a ring whose stages are not
replicas. The check now **scans** the shift, so a residual at the predicted shift
is a statement about the stages rather than about the prediction:

- The best fit lands within **0.006 of a cycle** of 0.6 per stage (scan resolution
  0.0026) for every ring-phase-dependent quantity at all three corners.
- At that shift the stages agree to ≤ 7.4 % of peak-to-peak on `V_gs` (≤ 2.3 %
  RMS) and ≤ 40 % peak / **≤ 7.6 % RMS** on `I_d`. They are not identical — stage
  5's output also drives the output buffer chain — so the multiply-by-five step is
  licensed to ~8 % RMS in `I_d`, not exactly.
- **The two current-source devices' `V_gs` is the exception, and it has a
  consequence for the unmeasured noise source.** Their gate sits on the *shared*
  bias net `VBP`/`VBN`, so all five stages see the same 6–14 mV of gate ripple with
  **no** stage shift, and the scan duly finds its best fit at shift 0 with a
  residual ≤ 0.3 % of that ripple. The consequence: noise injected by `vco_bias`
  onto `VBP`/`VBN` reaches all five stages **coherently**, and a common-mode
  injection does not average down the way five independent ones would. DR-030
  recorded the bias generator's injection as unmeasured; this record adds that
  assuming it averages like the per-stage sources would be wrong.

**5. The flicker term cannot be turned into a period-jitter RMS without an
observation interval, and `spec/pll.md`'s Period jitter row does not state one.**
The ISF integral `var(ΔT) = (1/ω₀²)·½·∫h²S_i dt` is derived for a
**delta-correlated** generator; for a `1/f^α` generator the single-period variance
depends on the correlation structure and hence on the observation window or
measurement bandwidth over which "period jitter RMS" is defined. The flicker slope
is now measured (`α = 0.94997`), so this is no longer a question about the model —
it is a question about the specification. This record therefore reports the flicker
generator as a **density at each measured frequency plus a measured exponent** and
integrates it nowhere, and it adds the missing definition to
`spec/pll.md`'s [Verification owed](../pll.md#verification-owed) as an explicit
prerequisite of the random-component measurement rather than leaving a future
assembly to pick an interval silently. **No target or limit is changed.**

**6. A methodology finding worth recording because it nearly produced a false
clean result: a check whose sample set is chosen for interpretability can pass and
mean nothing.** The `S_id` grid snaps to solved timepoints rather than
interpolating the six operating-point columns, because interpolating them
independently yields a row whose `I_d` is not the `I_d` of its own bias triple.
The first version of the measurement backing that choice probed the peak-, median-
and minimum-`|I_d|` phases — the three a reader would name — and found the
interpolated and snapped rows **indistinguishable** (~1 × 10⁻⁶ each), which would
have licensed dropping the snap. Adding a fourth phase class, *the phase where
`I_d` moves fastest*, is what made the difference visible: 8.2 × 10⁻⁵ (reference
corner) to 5.0 × 10⁻⁴ (slow/hot) for the interpolated row against ~1 × 10⁻⁶ for
the snapped one. The general form — choose a check's sample set for **sensitivity
to the failure**, not for legibility — is now stated in the directory README, and
the same logic is why `bias_correction` runs all four device classes rather than
the one nfet: which sign of an `I_d·R` bias correction is the better one changes
with the device *and* with the phase, worst case 3.2 × 10⁻³ relative on `I_d`
against 1.0 × 10⁻⁶ for the sign-agnostic Newton step at the same point.

**7. No number enters `spec/pll.md`, and the unverified budget stays
unverified.** No random period-jitter figure is produced at any corner, so the
Verification-owed row keeps **#520** as its owner, the ≤ 0.50 % RMS that the row's
supply-ripple derivation leaves for the random contribution remains an **unverified
budget** (DR-023 Decision 3), and `docs/chipalooza/challenge-5-proposal.md` §5
continues to read **UNMET** against the random component. `sim/period-jitter/sid-trajectory/`
is a method directory on the same standing as `../isf-bringup/` and
`../noise-toolchain-probe/`: no `records/`, no record id, no row in
`sim/CHARACTERIZATION.md`'s coverage table, no design number.

## Alternatives considered

- **Evaluate the integral for the two current-source device classes and publish it
  as a lower bound.** This is the alternative the record most wants to refuse
  explicitly, because after Decision 3 it is *cheap*: those two classes' `h_gen` is
  exact, their `S_id` is tabulated on a grid that contains the `h` grid, and the sum
  is arithmetic on committed JSON. Rejected on four compounding deficits, none of
  which a "lower bound" caveat repairs: two of four `vco_stage` classes, none of
  `vco_bias`; 12 phases with `n_eff` = 2.4 on a weight that peaks at the switching
  edge; `h` measured at the 2 fC pilot charge that DR-030's linearity sweep places
  +10.5 %/+6.8 % from the `dq → 0` limit at exactly those phases; and one corner of
  45. A number with four unquantified deficits *looks* like evidence, and
  `sim/README.md`'s own worked example is about preferring a recorded gap to that.
  The `h²`-weighted **cost** is reported instead precisely because it is a *ratio*
  of two averages of the same `h` table, so the pilot-charge bias is common to
  numerator and denominator and divides out — DR-030 Decision 6's own observation
  about which quantities survived its `dq` correction.
- **Report only the plain cycle-average cost, as the campaign was originally
  scoped to.** Rejected once the weighted and unweighted figures were both
  computed and found to differ by −4.1 to +5.2 dB with opposite signs for the two
  mechanisms. A bound on the wrong average is not a bound, and option (B) would
  have been licensed on a figure that does not bound its error.
- **Bless the peak-|I_d| convention and declare option (B) discharged.**
  Rejected: the 1.2 dB figure exists at one corner, for one mechanism, on a weight
  with `n_eff` = 2.4. Discharging a 45-corner row on it would be exactly the
  "uncalibrated figure DR-020 refuses", one level up.
- **Build a cyclostationary `trnoise()` injection now** — a unit-variance
  `trnoise()` source scaled by a behavioural gain driven from a PWL table of
  `√S_id(x)`, which would make option (B) genuinely cyclostationary rather than
  stationary. Deferred, not rejected: it is a real route this toolchain can
  express, the `S_id(x)` table it needs is what this directory just built, and it
  is named here so the next increment does not have to rediscover it. It needs its
  own convergence and ensemble-length validation and is not a reduction of existing
  evidence.
- **Run the mandated 45-point grid now.** Rejected as premature, not unnecessary.
  Three points were chosen because the *size* of the cyclostationary variation is
  corner-dependent in a way a convergence question is not — and the measurement
  justifies the choice, at 74.3 dB of span for `XMP`'s thermal generator at slow/hot
  against 114.7 dB at fast/cold. The grid is owed by the assembled pipeline, on the
  batch fleet through `sim/harness`.
- **Hold this record until the assembly exists.** Rejected. Decision 2 changes
  what is known about option (B) — it moves from "refused for want of a bound" to
  "buildable with a stated bound on its thermal term at one corner" — and Decisions
  4 and 5 are load-bearing for any assembly by anyone. Leaving them in a directory
  README would leave the ratified reasoning in DR-020/DR-023/DR-030 without the
  pointer.

## Consequences

- **`spec/pll.md` gains no number and loses no obligation.** The
  [Period jitter](../pll.md#period-jitter) section and the
  [Verification owed](../pll.md#verification-owed) row now say that two of the
  three ISF ingredients exist, that the stationary-approximation bound exists at
  one corner for the thermal generator, that the assembly does not exist, and that
  the row is still owed at **#520**. The ≤ 1.0 % RMS target does not move; neither
  does the 0.50 % RMS allocation's status as an unverified budget.
- **One thing is genuinely newly owed, and it is a specification question, not a
  measurement**: the observation interval or measurement bandwidth that makes
  "period jitter RMS" well defined for a `1/f^0.95` generator (Decision 5). It is
  added to the Verification-owed table under #520 rather than decided here, because
  choosing it changes what the target means.
- **What the next increment owes is now a short list.** `h_gen(x)` for all four
  device classes at the `S_id` grid's 24 phases, by direct two-terminal injection
  (DR-030 Decision 3) — which the measured 31-copy deck ceiling affords in two
  decks of 12 phases, each carrying its own uninjected reference copy, so the
  single-grid guarantee is preserved *within* each deck where it is needed; `h` at
  the ISF's zero crossings by extrapolating a charge sweep to `dq → 0` (DR-030
  Decision 3, fourth bullet); the assembly; then the 45-point grid on the batch
  fleet. The bias generator's own injection and the terminal-resistance
  (`rd`/`rg`/`rs`) generators remain outside all of it, and Decision 4's
  common-mode finding says the first of those cannot be waved away as averaging
  down.
- **`sim/period-jitter/isf-bringup/isf_deck.build_deck()` grew one additive
  parameter**, `extra_vectors`, which emits a `save` card and extends `wrdata`.
  With its default empty tuple the generated deck is byte-identical to what it was
  before, so that directory's committed evidence is unaffected, and
  `sim/tests/test_sid_trajectory.py` pins exactly that. The `save` is the
  load-bearing half: an `@m…[vgs]` expression named only on `wrdata` comes back
  frozen at its DC value for every timepoint, the run exits 0, and nothing
  announces it — the whole trajectory ingredient would have been a table of DC
  operating points.
- **If the assembled pipeline does not converge**, that is #520's option (D) and
  needs its own record superseding DR-030's Decision 2 narrowing. This record
  deliberately does not pre-judge it.
