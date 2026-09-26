# DR-032: The random period jitter is bounded, not estimated — ≤ 0.338 % RMS at every one of the 45 mandated PVT points, against the 0.50 % budget

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-031 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-26
- **Decided by**: Builder agent, issue #520
- **Relationship to earlier records**: **supersedes DR-020 Decision 1 and
  DR-023 Decision 2** — the random component is no longer "not obtainable" or
  "not measurable" on this toolchain *as an upper bound*, which is what the
  row's pass/fail needs; it remains not obtainable *as an estimate*, for the
  reasons those two records give. **Supersedes DR-020 Decision 2's "in
  simulation the row is deterministic-only"**, and DR-023 Decision 3's status
  of the 0.50 % allocation as an *unverified* budget: it is now verified, as a
  bound, within the scope Decision 4 states. **Retires DR-031 Decision 5's
  Verification-owed row** as a prerequisite of the random component (Decision
  3). DR-020 Decisions 3 and 5, DR-023 Decisions 1 and 4, DR-030 and the rest of
  DR-031 stand unchanged. **DR-002 Decision 5 is not superseded**: this record
  executes its method in substance — a transient-noise run dominated by the VCO
  plus a jitter-transfer argument through the closed loop — with calibrated
  `trnoise()` sources in place of the `TRANNOISE` option this build does not
  honour, and a small-signal analysis for the one block whose noise a
  one-period transient cannot bound; whether that confirms it is the operator's
  ratification call, and its status is left as it is. Neither DR-020, DR-023
  nor DR-002 is edited.

## Context

`spec/pll.md`'s [Period jitter](../pll.md#period-jitter) row targets ≤ 1.0 % of
the output period, RMS. The deterministic half is measured at all 45 mandated
PVT points (0.0508–0.2691 % RMS). The row's own supply-ripple derivation spends
0.50 % RMS of the target on supply ripple and leaves the other 0.50 % to the
random component; DR-023 Decision 3 made that allocation an explicit,
*unverified* budget line owed at #520.

#520 lists four ways to discharge it. Its option (B) — a calibrated `trnoise()`
injection — was refused by DR-020 and DR-023 for want of one thing: *"it must
state up front which bias point each amplitude was calibrated at and bound the
error that stationary approximation costs — without that bound it is the
uncalibrated figure DR-020 refuses."* DR-031 measured that error for one
convention (bias at peak-|I_d|): within ±1.2 dB of the `h²`-weighted density at
one corner, two-sided, and declined to license a number on it.

This record takes the other convention, the one that needs no ISF and no
per-corner transfer argument: **calibrate each generator at its maximum over
its own trajectory.** The error of that stationary approximation is not bounded
by a measurement; it is **one-signed by construction**. The evidence is
`sim/period-jitter/random-bound/`; every figure below is regenerated from its
committed `results/*.json` into `results/SUMMARY.md` by `summarize.py`.

## Decision

**1. The random period jitter is bounded at every mandated PVT point, and the
bound clears the budget at every one.** Worst point `sf_-40c_2.97v`,
**0.338 % RMS**, against 0.50 % — a margin of **1.48×**; range
0.255 … 0.338 % RMS over the 45. It is an **upper bound**: the random period jitter of
this design, within Decision 5's scope, is at most this; how far below it the
true value sits is not measured. Three independent terms, added in quadrature:
the ring's and output buffer's generators (a transient), the bias generator's
(a small-signal analysis), and the loop-filter resistor's (equipartition). At
the worst point they are 0.188 % (ring and buffer), 0.281 % (bias generator) and 0.0036 % (loop filter).

**2. The ring/buffer term rests on three inequalities, each conservative by
construction.**

- *Cyclostationary white → stationary white.* A white generator of
  time-varying density `S(t)` contributes `(1/ω₀²)·½·∫h(t)²S(t)dt` to one
  period's variance; `h² ≥ 0`, so a stationary injection at `S_inj ≥ max S(t)`
  produces at least that variance, with **the ring's true `h`** — the transient
  integrates it; no ISF table is read, so none of DR-030/DR-031's precision
  limits on `h` enters. What must be right is that `S_inj` really is the
  maximum, and that is measured: each switching device's density is sampled at
  384 phases and then at every 2.17 ps step — the trajectory's own resolution —
  around its three largest local maxima. That last step raised a 17 ps-sampled
  maximum by at most 8.6 %; a 48-phase grid alone would have missed the
  output buffer's final nfet's peak by up to 8.1×.
- *Flicker → white, in lock.* A modulated flicker generator
  `S(t,f) = m(t)²Kf^−α` is dominated, through the loop's error transfer, by a
  white one of density `Φ·S(t, F)`, `F = 0.475 f₀`, with `Φ` from the upper
  envelope of `|1/(1+T)|²` over **every** loop the as-built filter admits at the
  ratified 45° phase-margin floor (1606 loops, crossovers 14 kHz – 1.4 MHz) and
  a response window of two periods: `Φ` = 20.5 / 25.5 / 45.7 at α = 0.95 / 1.0 /
  1.12. The loop is what makes this finite: the pfet cards' `ef = 1.12` gives a
  free-running single-period variance that diverges at DC.
- *Open loop → closed loop.* The loop can raise a white generator's period
  variance only inside a band around its crossover; bounded by
  `1 + 2T_w∫(env − 1)₊df` = 1.142, not the envelope's 2.571 peak.

The two-period window is measured, not assumed: with only the ring's and
buffer's generators injected, the period sequence's lag-1 autocorrelation is
−0.258 … +0.160 and its lag-2 −0.117 … +0.127 over the 45 points, against a
standard error of ≈ 0.065 each — no correlation reaching past the next period,
which is all the window allows. (Alone, at the reference point, the ring's
generators give +0.00 and the buffer's −0.47: an edge moved, then restored.)

**3. The bias generator is bounded small-signal, because a transient window
cannot hold it.** Its outputs VBP and VBN are slow nets shared by all five
stages, so its noise moves the frequency for many periods: its white generators
alone, injected in the transient at the reference point, give a period sequence
with lag-1 autocorrelation **+0.43**, a memory the window the two factors above
rely on cannot hold. (A first run with the bias generator inside the transient
showed +0.17 … +0.49 over 20 grid points; it was withdrawn on that finding
before its results were used, and is not committed.) It is also quasi-DC (its devices' densities move ≤ 0.24 dB over
the cycle), so it is analysed where that is exact: `.noise` about its DC
operating point, loaded as in the VCO, referred to the ring's frequency through
measured static sensitivities to VBP and VBN, and integrated through the loop
envelope with its own flicker spectrum — no `Φ`, no window. Two things the
`.noise` does not do are done explicitly: the PDK's poly-resistor bodies, which
ngspice treats as noiseless, get their thermal and flicker noise mirrored in;
and the model is checked against the circuit — the bias generator's white
generators injected in the transient give 0.910 ± 0.042 of the model's
open-loop white prediction at the reference point. **It is the largest of the
three terms** at every point (69–83 % of the bound's variance), which is a design fact worth
having: the VCO's random jitter is set by its bias generator, not its ring.

**4. The flicker half needs no observation interval, so DR-031 Decision 5's
prerequisite does not bind a bound.** DR-031 added to `spec/pll.md`'s
Verification-owed table the observation interval that would make a *point
estimate* of a `1/f^α` contribution well defined. Both flicker treatments here
bound the **stationary** variance of the locked period sequence; for any finite
window, the expected sample variance about the window's own mean is at most
that. So the bound holds whatever interval the row is later given, and that
Verification-owed row is retired. The interval is not chosen here and the row
states none; this record only shows that the answer does not depend on it.

**5. The scope is stated, not implied.** Covered: every MOS channel (with its
`rd`/`rs`/`rg` generators) and every resistor in `vco` — the five-stage ring,
the bias generator and the output buffer — and the loop-filter resistor.
**Not covered: the charge pump, the PFD, the feedback divider and the lock
detector.** They are in-band: they reach the output through the closed loop's
low-pass transfer (≤ 1.4 MHz, ~1 % of `f₀`), and period jitter, the first
difference of phase, attenuates in-band phase by about `(2πfT)²` ≈ 3.4 × 10⁻³ at
1.4 MHz. That is DR-002 Decision 5's own scope ("dominated by the VCO plus a
jitter-transfer argument"), and it is an argument, not a bound — **#580** owns
the bound. Also outside: layout parasitics (schematic level, ideal supply —
which is also why the two MOS decoupling capacitors are noiseless here); the
200 MHz band top (#503's campaign, for the deterministic half too); the
reference source (excluded by `spec/pll.md`, DR-019).

**6. The measurement is validated as a measurement.** `trnoise()` delivers the
density it is asked for (four sources through an RC with a closed-form variance, measured/expected 0.985 … 1.046 at ±0.032 statistical) and two instances are uncorrelated
(correlation -0.004, ±0.022 expected). At the reference point, as ratios of independent decks to the
transient's own result: a 2.5 ps timestep ceiling 1.028 ± 0.067 (1 if converged);
`trnoise` sample intervals of 5 and 20 ps at equal density 1.061 ± 0.069 and 1.126 ± 0.073 (1 if the
source is white where the ring can see it); every amplitude × 3 3.161 ± 0.206 (3 if
linear); the ring's and buffer's variance shares sum to 1.104 ± 0.14 (1). The
per-device densities are anchored on every sub-network of every deck (each
sense resistor's thermal noise against its closed form, 0.9999996 … 1.0000000) and each
standalone bias reproduces the in-situ `I_d` to ≤ 1.8e-05.

**7. Two toolchain facts, recorded so no one relies on the opposite.** (i) On
this build a `trnoise()` realisation is **not** reproduced by fixing the
random seed: the `validate` stage's `repeat` deck — the transient stage's own
deck at the reference point, same `set rndseed`, run again — correlates with
the original period by period at +0.17, +0.34, +0.05 and +0.07 across its four
noisy copies, where a reproduced realisation would give 1 (`.option seed` and
`setseed` fared no better on a scratch two-source deck). Results reproduce
statistically, not sequence for sequence, and every comparison in Decision 6
is statistical for that reason. (ii) One `.noise` per frequency, referred to
the sum of many disjoint standalone devices' drains through unit-gain VCVSs,
reports each device's contribution exactly as a `.noise` referred to its own
drain does — identical in every printed digit, on every device, at the phase
that set the largest ring density — which is what made sampling 26 switching
devices at about 430 phases each, per point, affordable.

**8. What `spec/pll.md` now says.** The Period jitter row's random component
moves from *budget — unverified* to **bounded ≤ 0.338 % RMS at 45/45
points (upper bound, scope per Decision 5)**. The ≤ 1.0 % target does not move,
and neither does the 0.50 % allocation: it is now a verified allocation, with
1.48× margin at the worst point. `docs/chipalooza/challenge-5-proposal.md`
§5's random row moves from UNMET to **MET as an upper bound**, with the scope in
the same cell.

## Alternatives considered

- **Build the ISF assembly (option A) instead.** Not rejected — deferred. It
  would give an *estimate*, which this record does not claim, and DR-030/DR-031
  have built its ingredients. But the row needs a pass/fail against a budget,
  and a bound that clears the budget answers that without the assembly's open
  precision questions (`h_gen` for all four classes at the density grid's
  resolution, `h` at the ISF's zero crossings, `n_eff` of the weighting). If a
  future change pushes the bound over the budget, the assembly is the way to
  tighten it — and the bias generator, the largest term, is where to look first.
- **Keep the bias generator in the transient** with the ring and buffer. That
  is how this campaign was first run, over 20 points; it was withdrawn when the
  period sequences' positive lag-1 autocorrelation showed the bias generator's
  memory breaks the window the flicker and loop factors assume. Enlarging the
  window to cover it was the other option, rejected because the memory is set
  by the bias nets' bandwidth, not by the period, and a window long enough to
  hold it would have loosened the ring's and buffer's factors for no reason.
- **Calibrate at the peak-|I_d| phase, as DR-031 measured.** Rejected: that
  convention's error is two-sided (−1.15 … +1.06 dB at one corner) and was
  measured where one committed `h` exists. The maximum costs a looser figure
  and removes the need to know the error's sign.
- **Use the envelope's peak (2.57) as the closed-loop factor for the ring and
  buffer.** Rejected as needlessly loose — it assumes the loop amplifies every
  frequency a white generator's period variance is spread over, when it can
  only amplify inside a band of a few MHz.
- **Take `Φ` over the loop the trim rule selects, not every admissible loop.**
  Rejected for the bound: the trim rule's loop depends on N, `f_ref` and the
  trim code, and a bound over the superset holds for all of them.
- **Report the random component as "measured".** Rejected. It is bounded. A
  reader who sees "measured 0.3 %" will quote it as the jitter of the part;
  this document may only say "at most".

## Consequences

- `spec/pll.md`'s Period jitter section and Verification-owed table,
  `sim/CHARACTERIZATION.md`, `README.md`, `sim/README.md` and
  `docs/chipalooza/challenge-5-proposal.md` §5 carry the bound, its scope and
  the owner of the one uncovered generator class (#580). The
  observation-interval row is retired per Decision 4. #520 is closed by the
  pull request landing this record.
- `sim/period-jitter/random-bound/` is a method directory with committed
  evidence, the same standing as `../isf-bringup/` and `../sid-trajectory/`: it
  has no `records/` and no record id, because it runs outside `sim/harness`
  (several decks per point, with a reduction between them). Re-running it is
  `grid.sh`; everything it concludes is regenerated by `summarize.py`.
- If a later design change moves the VCO, the bound must be re-run before the
  row may keep citing it; nothing here grades a changed netlist automatically.
