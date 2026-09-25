# DR-022: How a tester executes the lock-detector window trim rule — the accuracy the rule actually demands, and what the present pad set can and cannot deliver

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-010,
  DR-011, DR-013, DR-014 and DR-015 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #501
- **Revises**: `spec/pll.md`'s
  [Lock-detector window trim-code rule](../pll.md#lock-detector-window-trim-code-rule)
  — adds the rule's *execution* clause. **The rule itself is not relaxed**: the
  measurand, the reference condition and the 1.343 ns target are unchanged, and
  nothing here makes an untrimmed part conforming.
- **Consumes**: DR-013 Decision 1 (the observable is the flag's assert window,
  not the bare chain delay) and Decision 4 (the ≤ 1.65× spread target this
  record grades an execution route against); DR-014 (the mechanism is a fixed
  test-set code); DR-015 (the code reaches the die as four dedicated pins);
  DR-002 Decision 4 (passive monitor, no self-calibration hardware).
- **Evidence**:
  - `sim/lock-window-proxy/records/20260925-050022-6d57802.md` — the campaign this record
    is written on, filed by #501. 117 points of the full 13-bundle PVT grid,
    two decks per point, one record: all sixteen trim codes measured
    simultaneously on one ideal step, paired at every point with the four
    quantities `pll_top`'s existing pads expose that could stand in for them.
  - `sim/lock-window-trim/records/20260917-185928-8adff3d.md` — the 1872-point
    code map the rule's own table comes from, and the source of every margin
    number the accuracy bound below is derived from.

## Context

`spec/pll.md`'s [Lock-detector window trim-code
rule](../pll.md#lock-detector-window-trim-code-rule) is **normative** — "a part
left untrimmed is outside this specification" — and the Lock detector row's
T1′/T2′ "met" verdict is conditioned on it. Its measurand is `t_win`, the
`ERR → ERRD` propagation delay of `delaywin_3v3` at 27 °C / 3.30 V.

**Neither node is a pad.** `design/netlist/pll_top.spice`'s `.subckt pll_top`
port list does not carry `ERR` or `ERRD`, and
`docs/chipalooza/challenge-5-proposal.md` §2.2's pad table has no row for
either. The quantity the pads *do* expose — the flag's own assert window,
which DR-013 Decision 1 defines as the largest phase error at the PFD inputs
for which `LOCK` asserts and stays asserted — is not something a bench can
impose either, because `FB` is an **output** of this block: there is no pad
pair a tester can drive to a known static phase offset.

So the rule was executable in simulation and had **no stated route to
execution on silicon at all** (issue #501). DR-015 closed by saying "future
harness integration work (bench test plans, tester programming) can now cite
`LDT0`–`LDT3` as fixed, addressable pins" — that work was never done, and
until it is, `docs/chipalooza/challenge-5-proposal.md` §4's lock-detector step
would compare an untrimmed part against a specification that explicitly does
not describe one.

Two things had to be settled before that gap could be closed rather than
merely restated: **how accurate a substitute measurement has to be**, which
nothing had ever derived; and **whether any quantity the existing pads expose
can reach that accuracy**, which nothing had ever measured. This record
settles both.

## Decision

### Decision 1 — The rule's measurand and target are unchanged

`t_win` at 27 °C / 3.30 V, programmed to the code nearest 1.343 ns in the
logarithmic sense, remains the normative rule. Nothing below relaxes it,
re-centres it, or makes an untrimmed part conforming. What is added is an
**execution clause**: a statement of how (or whether) a tester can carry the
rule out on a packaged part, which the rule as ratified never had.

### Decision 2 — The accuracy a substitute must reach is two-tiered, and both tiers are derived, not chosen

A pad-referred substitute does not have to reproduce `t_win`; it has to select
the same *code*, or a code close enough that the design's own ratified
verdicts survive. How close that is falls out of numbers already committed in
`sim/lock-window-trim/records/20260917-185928-8adff3d.md`, at that record's
measured trim step of **2.7–4.7 %** of window. Every code count below is
quoted at whichever end of that step range is the pessimistic one for the
claim being made, so none of them depends on a chosen mid-value:

**Tier A — band sufficiency (the ratified [1, 2] ns T1′/T2′ band).** With the
rule applied the grid holds **1.106 … 1.726 ns**: 10.6 % of margin below and
13.7 % above. Converting margin into codes at the **largest** measured step
(4.7 %, the conservative end — a smaller step buys more codes, not fewer):
`ln(1.106/1.0)/ln(1.047)` = **2.2 codes** of headroom downward and
`ln(2.0/1.726)/ln(1.047)` = **3.2 codes** upward. So a selector that is never
more than **2 codes low** and never more than **3 codes high** still holds the
band everywhere. **The bound is asymmetric, and the binding direction is
low** — a substitute that under-reads a fast part's window walks the fast
bundles off the 1 ns T1′ edge first.

**Tier B — spread sufficiency (DR-013 Decision 4's ≤ 1.65× observable-window
spread).** This is much tighter, and it is the tier that actually decides. The
same record's honest figure for a *continuous* process population — the grid
spread of 1.561× with one whole trim step of un-applied rounding added, which
is what a real part rather than one of thirteen bundles gets — is **1.610×**.
That leaves `ln(1.65/1.610)` = **2.48 %** of allowance against the target —
**0.53 of a trim step** at the largest measured step and **0.92** at the
smallest, in both cases less than one — while a *bundle-dependent* code error
of ±1 code adds two steps, not one: 1.610 × 1.027² = **1.698×** at the
smallest measured step, 1.610 × 1.047² = **1.765×** at the largest. Both are
past the target, so the conclusion does not turn on where in the measured step
range a part happens to sit.

**Therefore: a pad-referred substitute preserves DR-013 Decision 4 only if its
worst code error across the process population is zero.** Any nonzero
differential error costs more than the rule's own rounding has left. A
substitute with a worst error of 1 or 2 codes still holds the *band* (Tier A)
but no longer holds the *spread target* (Tier B), and a design whose Lock
detector row cites 1.53–1.58× cannot be trimmed by a method that delivers
1.70–1.77×.

This is the acceptance criterion any future proposal — on this die or a
successor — must be graded against. It is stated here so the grading is a
calculation rather than an argument.

**A corollary that constrains how a route may be written, not just how
accurate it must be.** The rule's 1.343 ns target is the band's geometric
centre divided by the **1.037×** ratio between the flag's observable window
and the bare chain delay. That ratio is not a constant: `spec/pll.md`'s
[Lock detector](../pll.md#lock-detector) section measures the excess δ at
**+1.4 … +3.3 %** at `ff`/−40 °C/3.63 V and **+1.7 … +7.0 %** at
`ss`/125 °C/2.97 V — a **1.055×** spread in the conversion factor itself,
worth **1.2 … 2.0 codes** across the measured 4.7 %–2.7 % step range. So a
route that measures the *flag* window and then divides by a fixed 1.037× to
recover `t_win` imports one to two codes of error before it has made a single
measurement error of its own, and fails Tier B on the conversion alone.

**The fix is to not convert.** A flag-referred route must be written with a
**flag-referred target** — the band's geometric centre times the
reference-condition-to-PVT-box factor, ≈ **1.393 ns** on the flag rather than
1.343 ns on the chain — so δ is absorbed into the measurement instead of into
a constant. That factor must be re-derived from `sim/lock-detector`'s own data
before it is written into `spec/`; the number here is the arithmetic, not a
measurement. Decision 5's route 1 is stated on that basis.

### Decision 3 — Measured: the pads can hold the ratified band, but nothing they expose can execute the rule

`sim/lock-window-proxy` enumerates the four candidates `pll_top`'s pad list
offers and measures every one of them against the cell's own sixteen-code
window map, paired at all 117 points of the full 13-bundle grid. Each
candidate is calibrated at **one** bundle (`typical`) and scored at the other
twelve; a no-measurement control (every part left at the power-up code 8) is
scored alongside, so "worse than measuring nothing" is a reportable outcome
rather than a rhetorical one. The window measurement is validated against the
committed single-copy campaign at all 1872 shared points — ratio
**0.999988 … 1.00001**, geometric mean 0.999999 — so the pairing this record
rests on is a measurement, not a join across campaigns.

| Policy | Residual spread | Worst code error | Window over the grid | Spread | Margin lo / hi | Verdict |
|---|---|---|---|---|---|---|
| **RULE** (internal `t_win`) | — | 0 | 1.106 … 1.726 ns | **1.561×** | +10.6 % / +13.7 % | in band |
| `ring_a` — ring period, band 4 / 1.80 V | 1.747× | 8 | 0.900 … 2.191 ns | 2.434× | −10.0 % / −9.6 % | **out of band** |
| `ring_b` — ring period, band 7 / 2.70 V | 1.700× | 8 | 0.900 … 2.191 ns | 2.434× | −10.0 % / −9.6 % | **out of band** |
| `clk_fb` — `CLK`→`FB` retiming skew | 1.592× | 4 | 1.122 … 1.947 ns | 1.735× | +12.3 % / +2.6 % | in band |
| `clk_do` — `CLK`→`DIVOUT` skew | **1.132×** | 4 | 1.122 … 1.905 ns | 1.697× | +12.3 % / +4.8 % | in band |
| **NONE** — untrimmed, code 8 | — | 5 | 1.041 … 2.066 ns | 1.984× | +4.1 % / −3.3 % | **out of band** |

**The ring period is not merely a poor proxy — it is worse than not trimming
at all** (2.434× against the untrimmed control's 1.984×), and the campaign
measures exactly why, in two independent mechanisms:

- **It responds to a process axis the window does not have.** `t_win` is
  invariant across all six passive-only bundles to four significant figures —
  every one of them reads a relative window of exactly 1.000 — because every
  device in `delaywin_3v3` is an `nfet_03v3`/`pfet_03v3`. The ring is not
  all-MOS: `design/netlist/vco.spice` starves it through three `ppolyf_u_3k`
  bias resistors (DR-009's device class), so `res_ff` moves the ring period
  **−27 %** and `res_ss` **+27 %** while the window does not move at all. A
  tester reading the ring would command a large trim correction on a part that
  needs none.
- **Across the MOS axis its sign is inverted.** At `ss` the window is 16 %
  *slower* than typical while the ring runs 6 % *faster* — the starved ring's
  frequency is set by the mirrored bias current, not by logic speed. The
  correction is applied in the wrong direction, which is how an 8-code error
  arises on a 16-code array.

Both ring operating points behave the same way, so this is a property of the
ring rather than of the (band, Vctrl) point chosen to read it.

**The two pad-to-pad digital skews are much better, and still not sufficient.**
`clk_do` is the best candidate the design has: it removes most of the window's
1.316× process spread, leaving a **1.132×** residual, and the code it selects
holds the ratified [1, 2] ns band at every one of the 117 points. But:

- **It fails Tier B outright.** Grid spread **1.697×** against DR-013 Decision
  4's ≤ 1.65×, and on a continuous population — adding the one trim step of
  rounding, as `sim/lock-window-trim` does for the rule itself — **1.74 …
  1.78×**. `clk_fb` is worse (1.735× / 1.78 … 1.82×).
- **Its Tier A pass is a property of this grid, not a guarantee.** Its worst
  code error is **+4**, one code beyond Tier A's derived +3 bound. Every error
  it makes happens to be *positive* (0, 0, 0, 0, 0, 0, 0, +1, +2, +2, +3, +4)
  and the bundles that took +3 and +4 are the fast ones, which carry the most
  upward headroom — so the band survives on where this grid's thirteen bundles
  happen to sit, not because the selector is bounded. The worst upper margin
  falls from the rule's +13.7 % to **+4.8 %**.
- **A silicon measurement owes a term this campaign cannot bound.** Both skews
  are measured between on-die nodes; a tester triggers on the `CLK` pad and
  times the `FB` or `DIVOUT` pad, and `design/` contains no output pad driver
  for `FB`, `DIVOUT` or `LOCK` at all. That path is the harness's, and its PVT
  behaviour is outside anything this repository can measure.

**Therefore: no quantity `pll_top`'s present pads expose may be written into
`spec/` as the trim rule's execution route.** The useful, narrower thing that
*is* established, and is worth stating because it is not nothing: the ratified
T1′/T2′ band can be held from the pads via the `CLK`→`DIVOUT` skew on this
13-bundle grid, with about a third of the rule's margin. DR-013 Decision 4's
spread target cannot be.

### Decision 4 — The rule is, on this die, executable only in simulation, and `spec/pll.md` says so

Until an execution route exists that meets Decision 2, `spec/pll.md`'s trim
rule carries an explicit **execution clause** stating that:

- the rule's measurand is not observable at `pll_top`'s pads, and every
  quantity that *is* observable there has been measured against it and found
  insufficient (Decision 3) — so the rule is, on this die, executable **only
  in simulation**;
- a part built from this netlist is therefore **characterized at a recorded
  trim code**, not trimmed-to-rule, at test — the code is a *configuration of*
  every measurement taken from the part, never a value derived from the part;
- the best pad-referred selector measured, the `CLK`→`DIVOUT` skew, holds the
  ratified T1′/T2′ band across the 13-bundle grid but exceeds DR-013 Decision
  4's spread target and is not bounded over a process population, so it is
  recorded as a **characterization aid, not a trim procedure** — a part whose
  code was chosen that way must report the fact alongside any `LOCK`
  measurement, and no `spec/` row may be graded as met on the strength of it;
- consequently the Lock detector row's T1′/T2′ "met" verdict is conditional on
  a trim that **no present bench or tester procedure can select to the
  accuracy the row's own spread figure assumes**, and the row says that in
  those words rather than leaving a reader to infer it.

This is a statement of what is true, not a relaxation. The rule stays
normative; what changes is that the spec stops implying a production path it
does not have, and now bounds how far from having one it is.

### Decision 5 — The two routes that could close it are named, and neither is authorized here

Both remain open, and this record deliberately does not pick between them,
on the same "do not pick the circuit without the evidence to pick it" pattern
DR-012 Decision 7 and DR-013 Decision 5 used:

1. **A symmetric `REF` phase-step bisection at the `LOCK` pad** (no design
   change). `REF` is a driven input and `LOCK` an output, so a tester can step
   `REF`'s phase by a known Δ and watch whether `LOCK` drops. Because the
   detector's `ERR = UP ⊕ DN` responds to |phase error| regardless of sign,
   stepping both ways gives two thresholds — Δ₊ = t_flag − φ_ss and
   Δ₋ = t_flag + φ_ss — whose mean is the flag window and whose half-difference
   is the loop's own static offset, so the offset that disqualifies the
   in-loop selector (see Alternatives) **cancels**. It measures the *flag*
   window, so it must be written against the flag-referred target of
   Decision 2's corollary, never against 1.343 ns through a fixed 1.037×.
   What makes this a candidate and not a decision is that nothing has measured
   it: it needs a closed-loop `pll_top` transient per step per code, the
   assert hold-off's contribution to the measured threshold is
   uncharacterized, the charge pump's UP/DN asymmetry may break the ±
   cancellation, and the tester must place a `REF` edge to ≈ 20 ps to resolve
   one trim step. Owner: **#527**.
2. **Expose the measurand** (a design change, and therefore a decision record
   of its own first). `ERR` and `ERRD` brought out through *matched*
   observation buffers onto two of §2.2's 9 free digital-test-output slots
   make `t_win` a pad-to-pad edge difference, with the buffers' own delays
   cancelling in the difference to first order. The tap loads the chain, so
   the rule's 1.343 ns target would have to be re-derived against the loaded
   cell — which `sim/lock-window-trim`'s deck can do cheaply, since it is a
   single-cell transient. DR-015 chose dedicated pins for the trim *inputs*
   and did not consider an output-side observation point, because the question
   had not been asked. Not authorized here; it becomes the route if #527
   returns a negative result.

### Decision 6 — A precondition that applies to every route

`pll_top` does not currently connect `LDT3` (**#515**): the committed export
wires the lock detector's MSB trim input to `net1`, an auto-named net with one
connection in the whole file, so only 8 of the rule's 16 codes are reachable
on the assembled part — and the rule's own table selects code **11** for the
`ff`/`all-fast` bundles. **No execution route can be validated on the part
until #515 lands.** This record's evidence is unaffected by it —
`sim/lock-window-proxy`'s window deck instantiates `delaywin_3v3` directly and
drives all four trim pins itself — but every statement here about what a
*tester* can do is conditional on that fix.

## Alternatives considered

- **Declare the rule simulation-only and stop there** (issue #501's option 4
  taken bare). Rejected as insufficient on its own: it records the conclusion
  without the two things that make it actionable — the accuracy bound a future
  route must clear (Decision 2) and the measured demonstration that the
  existing pads cannot clear it (Decision 3). A "simulation-only" note with no
  number behind it is exactly the kind of claim `CLAUDE.md` forbids.
- **Adopt the best pad-referred selector anyway** — write the `CLK`→`DIVOUT`
  skew procedure into `spec/` on the strength of its all-in-band result.
  Rejected: correlation is not the criterion and neither is a pass on one
  grid. It exceeds DR-013 Decision 4's spread target by 3–8 %, its worst code
  error is one code outside Tier A's own guarantee, and the band it does hold
  is held by which thirteen bundles this grid contains. Adopting it would put
  a number in `spec/` that the next grid could withdraw.
- **Read the ring frequency at a second, better-chosen (band, Vctrl) point.**
  Rejected on measurement: both operating points the campaign ran behave the
  same way (residual spread 1.747× and 1.700×, worst code error 8 at each),
  and the two mechanisms behind it — the poly-resistor bias axis and the
  inverted MOS-corner sign — are properties of a current-starved ring, not of
  where on its tuning curve it is read.
- **Select the code from the loop's own settled static phase offset** (issue
  #501's option 2 in its most obvious form: sweep `LDT3:LDT0` in a locked loop
  and take the code at which `LOCK` first asserts). Rejected on measured
  evidence: that code is where the flag's window crosses the loop's static
  offset, and the offset is a charge-pump property with its own large spread —
  #417 measured **0.814 ns** (`typical`/−40 °C/3.63 V) against **1.233 ns**
  (`ff`/27 °C/3.63 V) in-loop, a 1.51× span worth **9 … 16 trim codes** of
  selection error across the measured step range — against Decision 2's bound
  of zero, and wider than the 16-code array itself at the slow end. DR-012
  further measures that offset *itself*
  exceeding the ratified ≤ 1 ns criterion at 2 of 45 corners, so it is not a
  reference a trim can be set against in any case.
- **Take the process corner from wafer PCM / scribe-line data** rather than
  from the die. Not chosen: it is outside this block's control and outside the
  Challenge #5 harness's stated deliverables, it says nothing about the
  die-to-die and within-die terms the rule exists to absorb, and this
  repository cannot produce a testbench for it — so it could not be graded
  against Decision 2 even in principle.
- **Fuse or metal-option the code.** Rejected again, for DR-014 Decision 2's
  and DR-015's reason: the rule sets the code from a per-part measurement, and
  a fixed option defeats its per-part adaptivity outright. This record changes
  nothing about that argument.
- **Relax DR-013 Decision 4's ≤ 1.65× target so a 1- or 2-code-error selector
  passes.** Rejected on `CLAUDE.md`'s "agents do not relax the ratified spec to
  make results pass." The target was derived from the band's own margin
  requirement, not from what a convenient trim method can deliver.

## Consequences

- **`spec/pll.md`'s trim-rule section gains an execution clause** and the
  [Lock detector](../pll.md#lock-detector) row's conditionality is restated
  against it. No number in either moves; what changes is that the rule now
  states what a tester is expected to do, and what it cannot.
- **`docs/chipalooza/challenge-5-proposal.md` §4 step 4, §5's Lock detector
  row and §7 item 11 are restated** onto this record, so the proposal's bench
  plan, its target table and its open-items list all say the same thing about
  the same gap and cite measured evidence for it rather than an inference.
- **The gap is now quantified rather than open.** Before this record, "no
  stated route to execution on silicon" was a true observation with no bound
  on how hard the problem is. Decision 2 turns it into an engineering
  specification: a candidate route either delivers zero differential code
  error or it does not preserve the ratified spread target, and that is
  checkable before anyone builds a tester program.
- **A bad consequence, stated plainly: this makes the Lock detector row weaker
  than it read before.** T1′/T2′ are still met at the codes the rule selects —
  that measurement stands — but the row's conditionality now points at a trim
  no present procedure can execute, rather than at a trim merely not yet
  performed. A reader of `docs/chipalooza/challenge-5-proposal.md` §5 will see
  a narrower claim than the previous revision implied, and that is the correct
  claim.
- **Two campaigns are now owed against this record**: #527 (the `REF`
  phase-step route's characterization) and, if that returns negative, an
  option-3 decision record plus the re-derivation of the 1.343 ns target
  against an observation-buffer-loaded cell. Neither is started here.
- **#515 is a hard precondition** for any of it, and for the trim rule's
  executability at all on the present netlist.
- **What is *not* invalidated**: `sim/lock-window-trim` (1872 points) and
  `sim/lock-detector` (205 points) both drive the trim pins at block level and
  are untouched by everything above. The code table, the monotonicity result,
  the step size and the T1′/T2′ verdict all stand exactly as recorded.
- **An unplanned positive: the committed code map is now independently
  reproduced.** `sim/lock-window-proxy` re-measures the same sixteen-code
  window map on a different deck — sixteen parallel copies on one ideal step,
  rather than one copy swept sixteen times — and agrees with
  `sim/lock-window-trim` at all **1872** shared (bundle, temperature, supply,
  code) points to **0.999988 … 1.00001**. The rule's own table was previously
  carried by a single campaign; it is now carried by two that share only the
  cell.
