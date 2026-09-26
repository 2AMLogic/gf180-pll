# DR-030: The ISF route's Γ ingredient is brought up and converges; DR-023's finding stands, and the clause that would have overtaken it is narrowed to the two ingredients that remain

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-029 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-26
- **Decided by**: Builder agent, issue #520
- **Relationship to DR-023 and DR-020**: **narrows DR-023 Decision 2; supersedes
  nothing.** DR-023 Decision 2 recorded the random period-jitter component as
  not measurable on this toolchain and — unusually, and to its credit — stated
  the condition that would overturn it: *"if `pss` resolves, or if an ISF
  pipeline demonstrates convergence, this decision is overtaken and a new record
  supersedes it."* Half of that trigger has now been tested directly, so this
  record exists to say which half and what it did and did not settle. `pss`
  still does not resolve. An ISF **extraction** now demonstrably converges; an
  ISF **pipeline** still does not exist, because two of its three ingredients do
  not. DR-023's finding is therefore unchanged in substance and its owner
  (#520) is unchanged. DR-020 and DR-002 Decision 5 are untouched.

## Context

`spec/pll.md`'s [Period jitter](../pll.md#period-jitter) row targets ≤ 1.0 % of
the output period, RMS. Its deterministic (control-ripple) half is measured at
all 45 mandated PVT corners, 0.0508–0.2691 % RMS, PASS at every one. Its random
(noise-driven) half has no record, and DR-020 and DR-023 record why. DR-023
located the gap precisely: ngspice-46 *does* report each device's channel-thermal
and flicker generators at a bias point (`.noise`, per device, per mechanism), and
this build has no periodic-steady-state analysis to weight them over the
oscillation trajectory (`pss: no such command available in ngspice`).

Issue #520 lists an impulse-sensitivity-function (ISF, Hajimiri–Lee) pipeline as
alternative (A) for closing that gap, and names its load-bearing risk explicitly:

> The load-bearing risk is Γ: it needs one transient per injection phase per
> node, and its accuracy near the switching edge — where it matters most — is
> exactly where timestep control is weakest. A bring-up that cannot show Γ
> converging against timestep is a negative result worth recording, not a
> failure to hide.

That is a falsifiable claim about a simulator, and it has now been tested rather
than reasoned about. `sim/period-jitter/isf-bringup/` is the bring-up: seven
stages at one PVT point (typical / 27 °C / 3.30 V, VCO band 6, Vctrl = 1.795 V —
`sim/period-jitter/testbench/tb.json`'s own release voltage for that corner, so
the bring-up sits on the operating point the deterministic half is already
measured at). It reports `h(x) = Γ(x)/q_max` in rad/C rather than Γ, because
`q_max` is a modelling convention and every `q_max` in the textbook jitter sum
cancels against the one inside Γ.

Four properties had to hold before any `h` was worth reporting, and the bring-up
refuses to report one without all four; a fifth row below is the deck limit that
bounds how many phases one deck can resolve. The numbers are regenerated
from committed JSON by `summarize.py` into
[`results/SUMMARY.md`](../../sim/period-jitter/isf-bringup/results/SUMMARY.md),
not transcribed:

| Check | Question | Result |
|---|---|---|
| Settling | Does the injected impulse leave a pure phase shift, or a frequency change? | **Phase shift.** Across all 24 sampled phases the settled tail's peak-to-peak spread is 1.3–15.2 fs on displacements of 0.14–43 ps, and its least-squares drift ≤ 0.47 fs/cycle. |
| Convergence in `tmax` | Is `h` independent of the internal-timestep ceiling? | **Yes at the 2 ps setting the bring-up runs at, and this is the risk #520 names.** Halving the ceiling **from 2 ps to 1 ps** moves `h` by **≤ 0.02 %** at every sampled phase, and 4 ps is within 0.14 % of the 1 ps limit. **This is the last halving, not every halving**: the 8 ps → 4 ps halving moves `h` by up to 2.32 % (at a phase where \|h\| is 20× below its peak), so the span of the whole sweep against its limit is 2.36 % and 8 ps is not a converged setting. Four phases, at the peaks and flats of `h(x)` — not at the two flanks the linearity row below identifies. |
| Linearity in `dq` | Is the response linear over the charge used? | **At the peaks and flats, only below ~0.25 fC, and the pilot charge was not. At the ISF's zero crossings, not at any charge in the sweep.** At the four peak/flat phases `h` moves 0.21–0.75 % over the last halving (0.25 → 0.125 fC), and the 2 fC pilot sits **+10.48 %** (falling edge) and **+6.76 %** (rising edge) from that limit, with 8 fC at +30.5 %. At the two phases on the steep flanks before `h(Y)` changes sign (1/6, 2/3), the same last halving still moves `h` by **4.31 %** and **7.34 %**, the 2 fC pilot is **−55.7 %** and **−154 %** from the 0.125 fC value, and 8 fC **inverts the sign** at 1/6. The linear window is a property of the phase. |
| Two constructions of `h_gen` | Does the directly-injected two-terminal ISF match the one built by subtracting single-node ISFs? | **At the Γ²-dominant phases yes, to 0.06 %, 0.07 % and 0.23 %; at the ISF's zero crossings no, and uninformatively so.** 3 of 12 pair/phase points agree to better than 1 %; **4 of 12 disagree by ≥ 36 %**, worst 107.6 % (`Y-NH` at 2/3); median 16.6 %. The disagreement tracks the **single-node charge dependence at the same phase** (Spearman rho **+0.93**) and **not** the ratio of the two charges (rho **−0.00**) — a 16× charge ratio agrees to 0.23 % while a 1.21× ratio disagrees by 107.6 %. It is the finite amplitude of both stimuli at phases where the linearity row above shows no converged `h` exists. |
| Deck capacity | How many copies does the one-deck construction hold? | **31 complete; 37 abort** (`Timestep too small`, within the first 20 fs, on injection-free 3 ns decks). Above the ceiling ngspice still writes a one- or two-row `clk.dat`, so the failure surfaces as the reduction dividing by an empty crossing list. |

## Decision

**1. The load-bearing risk #520 names is retired, with a number, and the number
carries its qualifier.** `h` is converged against the internal-timestep ceiling to
**better than 0.02 % over the last halving (2 ps → 1 ps) at the 2 ps setting** the
bring-up runs at, including at the switching-edge phases where \|h\| is largest
and where #520 predicted the difficulty would be. The qualifier is not decoration:
the *first* halving in the sweep, 8 ps → 4 ps, still moves `h` by 2.32 %, so "per
halving" without naming which halving is a false generalisation of this result and
every restatement of it elsewhere names the step. The prediction
was reasonable and is not what the simulator does. The construction that makes
this true is worth naming, because it is not the obvious one: every injection
phase is a **copy of the whole VCO inside one deck**, alongside one uninjected
reference copy, so ngspice picks a single timestep sequence for the entire
circuit and the grid error is common-mode between the perturbed and unperturbed
trajectories. Two separate ngspice processes would integrate the two
trajectories on two independently-chosen adaptive grids, and that grid
difference alone is the same order as the 0.14–43 ps being measured.

**2. DR-023's finding is NOT overtaken, and its falsification clause is
narrowed.** A converging Γ *extraction* is **one of three ingredients** of a
pipeline, and it is not the ingredient where the cyclostationary weighting
happens. The other two do not exist: an `S_id(V_gs, V_ds)` table per ring device
class, and the trajectory `(V_gs, V_ds)(t)` to evaluate it along. DR-023
Decision 2's trigger is therefore restated as the narrower and still-falsifiable:
*this decision is overtaken when a pipeline — all three ingredients, assembled,
with its stationary-approximation error bounded — demonstrates convergence, or
when `pss` resolves.* One ingredient converging is progress and is recorded as
progress; it is not the finding changing.

**3. The precision the remaining pipeline needs is measured, and it is not the
precision the per-node tables demonstrate.** This is the record's own new
finding, and it changes what "build the pipeline" means rather than merely
sizing it. A MOSFET's channel-noise generator is a current source **between**
drain and source, so the ISF weighting it is `h_gen = h(source) − h(drain)`, not
`h(drain)`. On this ring those two terms are nearly equal, and the bring-up's
`diff` stage measures the residue directly — by injecting *between* the two
nodes — as well as by subtraction, both in one deck, so the two constructions
can be compared on one timestep grid. Consequences, in the order they bind:

- **The cancellation is measured, not estimated**: at the strongest of the
  sampled phases the residue is **1.54 % of the larger term**, so a pipeline
  building `h_gen` by subtraction needs ~65× the precision the per-node tables
  demonstrate. Measured as a difference, the residue's own signal-to-floor falls
  to **1.8** (median 35). Injected directly between the two nodes it is **34 at
  worst, median 254**.
- **A pipeline must therefore inject the two-terminal generator directly**, and
  must not difference across two decks: differencing across decks reintroduces
  precisely the independent-grid error the one-deck construction exists to
  cancel, and at this cancellation ratio that error is no longer negligible.
  That is a deck-construction requirement, discovered by measurement, and it is
  now available (`isf_deck.injection_element`) rather than owed.
- **The cross-check earned its place on its first run, by catching a sign
  error.** It returned ~200 % *signed* disagreement with ~0 % *magnitude*
  disagreement at the high-signal points — the unmistakable signature of a sign
  convention, and the actual cause: `h_gen` had been defined drain-minus-source,
  the negative of the generator's own sensitivity. Only `h_gen²` reaches the
  jitter sum, so that error would never have surfaced in a final number, and no
  amount of internal consistency in either construction would have shown it.
  The convention is now stated in `isf_extract.node_differences` and pinned by a
  test that asserts exactly that 200 %/0 % signature.
- **The comparison of the two constructions is the only evidence available about
  the deck** — that the injection lands on the nets it names — **and it is
  evidence at some phases and not at others.** Stated precisely, because the
  first draft of this record overstated it: 3 of the 12 pair/phase points agree
  to **0.06 %, 0.07 % and 0.23 %**, and all three are at phases where the
  single-node `h(Y)` is charge-independent to 0.1–0.3 %; **4 of 12 disagree by
  ≥ 36 %**, and those are at phases where `h(Y)` itself moves 31–50 % between the
  two charges in play. The disagreement is ranked by that charge dependence
  (Spearman rho **+0.93**), not by the ratio of the two charges (rho **−0.00**).
  The worst row, `Y-NH` at phase 2/3, is the one worth naming outright: direct
  injection gives `h_gen = −6.25e10` at 1.42 fC and 34× above its own floor, the
  subtraction gives **+8.22e11** at 1.17 fC and 48× above its own floor — 13×
  larger and sign-inverted, with a charge ratio of only 1.21× and neither side
  anywhere near its floor. It is not a floor artefact and it is not a charge-ratio
  artefact; phase 2/3 is one of the two flanks where the linearity sweep shows no
  converged `h` exists at any charge it covers, so **at that phase the cross-check
  supports no conclusion about the deck, and this record claims none.** What the
  cross-check does establish is the deck at the Γ²-dominant phases, where it agrees
  to ≤ 0.23 %. That distinction earned its place: ngspice accepts `iinj 0 xa.Y1`
  against a subcircuit-internal
  node, silently creates a *new top-level node* named `xa.y1`, and runs clean
  while injecting nothing. Confirmed during this bring-up: the measured period
  came back bit-identical with and without a 1 µA injection that, had it
  connected, would have moved the node by volts. The wrappers are therefore
  **derived from** the committed `design/netlist/vco.spice` at deck-build time
  rather than hand-copied, and `sim/tests/test_isf_bringup.py` pins that every
  device line is the committed netlist's own text.
- **A fourth consequence, found by being forced to explain that disagreement: the
  ISF's linear window is a property of the phase, and it is narrowest exactly
  where `h` passes through zero.** The first version of the linearity sweep
  sampled only the peaks and the flats and reported a single window (below
  ~0.25 fC). Re-run with the two phases on the steep flanks before `h(Y)`'s zero
  crossings added, it does not converge there at all: the last halving still moves
  `h` by 4.31 % and 7.34 %, the 2 fC pilot is −55.7 % and −154 %, and 8 fC inverts
  the sign at one of them. The mechanism is geometric — where `h` is small and
  `dh/dx` is large, the second-order term in the response (`dq²·dh/dx`, the
  injection displacing the trajectory while it is still being delivered) is
  comparable to the linear `h·dq` term that *is* `h`; at those two phases
  `|d ln h/dx|` is 161 and 315 per cycle against 0.3–23 elsewhere. **What a
  pipeline owes as a result**: `h` at the ISF's zero crossings must be obtained by
  extrapolating a charge sweep to `dq → 0`, not by measuring at one charge, and a
  single "the method is linear below X fC" figure is not a property of the ring.
  The mitigation is real but is a statement about weighting, not about accuracy: a
  Γ²-weighted sum is dominated by the \|h\| peaks, and \|h\| at these two phases is
  15–30× below that peak, so `h²` there is 200–1000× below.
- **The one-deck construction has a measured copy ceiling, and it caps phase
  resolution per deck.** 31 copies complete, 37 abort. Three node classes plus
  two two-terminal pairs is five injection variants per phase, so one deck buys
  six phases — which is why the `diff` stage's phase set is chosen at the
  switching edges, where a Γ²-weighted sum is dominated, rather than uniformly. A
  pipeline wanting finer `h_gen(x)` must either span several decks, losing the
  single-grid guarantee between them, or raise the ceiling — a
  simulator-settings question this record does not open.

**4. No number enters `spec/pll.md`, and the unverified budget stays
unverified.** The bring-up produces no random period-jitter figure at any
corner, so the Verification-owed row keeps **#520** as its owner, the ≤ 0.50 %
RMS that the row's supply-ripple derivation leaves for the random contribution
remains an **unverified budget** (DR-023 Decision 3), and
`docs/chipalooza/challenge-5-proposal.md` §5 continues to read **UNMET** against
the random component. This record adds what is now known about the route to
closing it and subtracts nothing from what is owed. It is also why the bring-up
is single-corner and mints no evidence record: it brings a *method* up, and a
45-point PVT grid would multiply the cost of an unvalidated method by 45 before
anyone knew whether it converged — the same reasoning
`sim/period-jitter/noise-toolchain-probe/` states for being single-corner, and
the same reason neither directory appears in `sim/CHARACTERIZATION.md` as a
campaign.

**5. The pilot charge's figures are corrected rather than withdrawn.** The
`gamma` and `nodes` stages were run at 2 fC, which the linearity sweep then
showed to be outside the linear regime at the switching edges by +10.48 % and
+6.76 %. Those runs are kept and reported with that bias stated, because they
are the pilot the per-phase charge rule is derived from and deleting them would
hide the reason the rule exists. The `diff` stage then re-measures every node at
a charge chosen **per phase** to land each displacement near 2 ps — 0.125 fC at
the switching edges, where linearity binds and the converged limit is known to
0.75 %, up to ~3 fC at the flat parts of the cycle, where the displacement is
otherwise only ~10× the numerical floor and where the Γ²-weighted sum is
insensitive anyway. Putting the accuracy where the sum needs it, and saying
where that is, is a methodology result in its own right. **Decision 3's fourth
bullet is the limit of that rule**: at the ISF's zero crossings no charge in the
sweep lands in a linear regime, so the per-phase rule chooses a *readable*
displacement there but not an accurate `h`, and the record says so rather than
letting the rule imply otherwise.

**6. The injected charge is the pulse's area, and it is normalised by the charge
actually delivered.** Recorded as a decision rather than a fix note because it
sets what every `h` in this directory means. ngspice's `PULSE(V1 V2 TD TR TF PW
PER)` is a trapezoid, so a pulse of amplitude `amp` delivers `amp·(PW + TR/2 +
TF/2)`, not `amp·PW`. The first revision of the deck set `amp = dq/PW`, which at
`PW = 10 ps` and `TR = TF = 1 ps` delivered 1.10·`dq` while the reduction divided
by the nominal `dq` — a systematic **+10 % bias on every reported `h`, and +21 %
on every `h²`**, the form that enters the jitter sum. The amplitude is now sized
`dq/(PW + TR)` so that the delivered area *is* the nominal `dq`, every affected
stage has been re-run, and the committed `results/*.json` and `results/SUMMARY.md`
are the corrected numbers. Every figure in this record is post-correction.
Because `PW` was constant across all stages, the bias cancelled out of every
*ratio* — the convergence, linearity, cancellation, signal-to-floor and
two-construction findings are unchanged in substance, and the re-run confirmed
that rather than assuming it (`h` fell by exactly the expected 1/1.10 at 22 of
the 24 `gamma` phases; the two exceptions are the zero-crossing flanks, which is
itself Decision 3's fourth bullet showing up). What was wrong was the absolute
value of the deliverable quantity, and `sim/tests/test_isf_bringup.py` now pins
the trapezoid's **area** rather than its plateau amplitude — an assertion on the
amplitude is structurally incapable of catching this class of error.

## Alternatives considered

- **Publish an order-of-magnitude jitter number from `h` and a single-bias
  `S_id`.** Rejected, and this is the alternative the record most wants to
  refuse explicitly, because it is now *cheap*: `h` exists, `.noise` gives
  `S_id` at a bias point, and the two multiply together in an afternoon. DR-023
  already refused exactly this for exactly the right reason — the generator
  being sampled moves by 46.6 dB (thermal) and 95.9 dB (flicker) across the bias
  the device actually traverses, so *which* single bias point one picks sets the
  answer, and a number whose value is chosen by an undocumented modelling choice
  is worse than no number because it looks like evidence. Nothing in this record
  weakens that refusal; having one more ingredient in hand does not.
- **Record the ISF route as a negative result, under #520's option (D), on the
  strength of the pilot charge's non-linearity.** Rejected. The pilot charge
  being outside the linear regime is an *amplitude* choice, not a property of
  the method: at the phases that dominate a Γ²-weighted sum, extending the sweep
  downward converges to 0.21–0.75 % over the last halving. Filing an avoidable
  stimulus error as a methodology failure would have closed a route that works.
  Decision 3's fourth bullet is the honest boundary of that rejection — at the
  ISF's zero crossings the sweep does *not* converge, and that is recorded as an
  open requirement on the pipeline rather than folded into this dismissal.
- **Report `h` without the linearity sweep.** Rejected. The pilot figures are
  10 % from the limit at the phases that dominate the sum; a table of them
  presented as Γ would have been wrong by more than the timestep error the
  bring-up was built to bound, and wrong in a direction nothing in the run
  would have revealed.
- **Build `h_gen` by differencing the existing `gamma` and `nodes` stages.**
  Rejected on Decision 3's measurement: the residue is small enough that
  differencing across two decks' independent timestep grids is not a valid
  operation. Naming this as the reason, rather than simply building the direct
  injection, is the point — the invalid version is the one a reader would
  reconstruct from the per-node tables.
- **Run the bring-up over the mandated 45-point PVT grid.** Rejected as
  premature, not as unnecessary. Convergence is an integration-error question
  and is corner-independent *in kind*; a grid is what the *pipeline* owes, on
  the batch fleet, once all three ingredients exist. Paying for it now would
  have bought 45 copies of an answer to a question the bring-up exists to ask
  once.
- **Hold this record until a jitter number exists.** Rejected. DR-023 Decision 2
  named a falsification trigger, and half of it has now fired: leaving that
  unrecorded would leave the ratified reasoning in a state where a reader cannot
  tell whether the trigger had been tested and failed, tested and passed, or
  never tested at all. A stated trigger that is tested owes a record either way.

## Consequences

- **`spec/pll.md` gains no number and loses no obligation.** The
  [Period jitter](../pll.md#period-jitter) section and the
  [Verification owed](../pll.md#verification-owed) row both now say that the ISF
  route's Γ ingredient is brought up and converges, that two ingredients remain,
  and that the row is still owed at **#520**. The ≤ 1.0 % RMS target does not
  move; neither does the 0.50 % RMS allocation's status as an unverified budget.
- **`sim/period-jitter/isf-bringup/` is a method directory, not a campaign.** It
  has no `records/`, mints no record id, appears in no coverage table, and
  reports no design number — the same standing as
  `sim/period-jitter/noise-toolchain-probe/`. Its claims are checkable without a
  simulator: `sim/tests/test_isf_bringup.py` pins the wrapper derivation against
  the committed netlist, and pins the reduction — crossing interpolation,
  settled-tail selection, drift rejection, the sign convention, the differential
  residue and its floor — against answers known in closed form.
- **What the next increment owes is now specific.** `S_id(V_gs, V_ds)` per ring
  device class, evaluated along the ring's own trajectory rather than at a chosen
  bias point; the trajectory itself; **`h` at the ISF's zero crossings obtained by
  extrapolating a charge sweep to `dq → 0`** rather than measured at one charge
  (Decision 3's fourth bullet), and the timestep convergence sweep extended to
  those phases; the assembly, with the flicker term's
  observation-bandwidth dependence stated rather than integrated silently; and
  then the 45-point grid on the batch fleet. Two further limits of the bring-up
  are load-bearing for that work and are stated in its README rather than
  discovered later: `h` is measured at the stage output and the two
  current-source nodes only, so the VCO bias generator's own noise injection is
  unmeasured and a sum over the measured classes alone would be a **lower**
  bound presented as a result; and everything here is schematic-level, while a
  ring node's capacitance — precisely what `h` scales against — is exactly what
  layout parasitics change.
- **If the pipeline is eventually built and does not converge**, that is #520's
  option (D) and needs its own record superseding this one's Decision 2
  narrowing. This record deliberately does not pre-judge it.
