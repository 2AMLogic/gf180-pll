# DR-019: The Reference input row's owed verification is re-pointed from closed issue #12 to a campaign that exists, and the reference-source-quality exclusion is restated with its ownership stated honestly rather than plausibly

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-018 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #499

## Context

`spec/pll.md`'s [Reference input](../pll.md#reference-input) row states an
electrical contract on the driving system in four lines. Three of them carry no
measurement:

| Item | v1 requirement | Basis as ratified |
|---|---|---|
| Levels | V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD | budget — "no input-threshold sweep exists" |
| Edge rate | ≤ 5 ns, 10–90 % | budget |
| Duty cycle | 30 – 70 % | argued from `design/pfd.sch` (rising-edge-only detectors), not measured |
| Source quality | excluded from the jitter and spur budgets | an explicit assumption, not a number |

That is not an oversight in the record-keeping: **no simulation *result* in
this repository has ever varied any of the three.** Every testbench here that
has produced a record drives `REF` identically —
`grep -n '^vref ' sim/*/testbench*/*.sp sim/*/testbench*/*.spice` returns 13
decks, 12 of them the same
`pulse(0 <vdd> <tstart> 200p 200p <half-period> <period>)` shape — so the
reference is ideal by construction in every jitter, spur and phase number this
repository reports. The thirteenth is this record's own campaign deck,
`sim/reference-input-contract/testbench/tb_reference_input_contract.spice`,
which varies the waveform on purpose and carries no record (§"What now
exists"). See Amendment A1 for why this paragraph is scoped to records rather
than to decks, and why its command names both deck extensions.

**Two separate defects follow from that, and this record addresses the one that
is a spec defect.**

1. *The owed verification has no owner.* `spec/pll.md`'s
   [Verification owed](../pll.md#verification-owed) table names **#12** against
   this row ("input thresholds/edge-rate sweep; a numeric reference-jitter limit
   to replace the current exclusion"). #12 is **closed**, and its subject is
   closed-loop lock acquisition and output-range coverage — it is the owner of
   `sim/lock-time` and `sim/output-range`, and never contained this work. A
   ratified table pointing an open obligation at a closed, unrelated issue reads
   to an outside reader as *discharged*, which is the opposite of true. Fixing
   it is an edit to a ratified table, hence this record.

2. *The measurement itself is owed.* That is not a spec decision and this record
   does not pretend to make it. It is tracked in §Consequences and remains open
   at #499.

### What now exists, and what does not

Issue #499 lands the campaign, not the measurement:
`sim/reference-input-contract/` carries a complete, self-checking manifest, deck
and reduction module. It holds the DUT at exactly the operating point
`sim/pfd-deadzone` characterizes (`pfd_cp`, 25 MHz reference, Vctrl = 1.65 V,
Icp trim code b1 b0 = 10) and sweeps the **REF waveform** instead: the ideal
pulse every prior record used, plus one variant at each stated boundary of the
contract (0.2·VDD – 0.8·VDD levels; 5.00 ns 10–90 % edges; 30 % and 70 % duty)
and one at all three simultaneously. Its verdict quantity is the
reference-path set delay

> `d_ref = t(UP crosses VDD/2, rising) − t(REF crosses VDD/2, rising)`

— the interval between the reference edge as a driving system would time it and
the instant the phase detector acts on it, i.e. *the phase the PFD sampled*. The
graded quantity is the per-corner **shift** of `d_ref` against the ideal pulse.

**It carries no record.** The declared grid is 288 points (the full mandated
45-point PVT matrix × six waveform variants, plus an 18-point detector-gain
slice at three corners), which this repository's operating rules require to run
on the Spot batch fleet rather than on a shared dispatch host. The submission
path was exercised and is blocked outside this repository; the exact failure,
its reproduction and its owner are in §Consequences.

A 12-point single-corner debug probe (`typical`/27 °C/3.30 V, every waveform
variant and both near-pair points, `--no-write`) did run locally and is what
establishes the deck resolves, converges and measures. **It is a bring-up probe,
not evidence**: it mints no record, it is one corner of forty-five, and no
number from it appears in `spec/pll.md` or in `docs/chipalooza/`.

### The source-quality line is a different kind of item

The other three lines are *measurable and unmeasured*. The source-quality line
is an **exclusion**, and it is a defensible one: `spec/pll.md` states the
`20·log₁₀(N)` transfer (12 dB at N = 4 to 36 dB at N = 64) and tells an
integrating system to budget its own reference against that multiplication.
Replacing it with a number requires injecting reference jitter into the closed
loop and measuring the output contribution. What made it a *defect* is not the
exclusion — it is that the exclusion's own escape hatch pointed at #12 too
("Converting this assumption into a numeric reference-jitter limit requires the
closed-loop bench (#12)"), so the row disclaimed and mis-attributed in the same
sentence.

## Decision

**1. The Reference input row's Verification-owed owner is re-pointed.** The
`#12` in that row is replaced by **#499 (`reference-input-contract`)** for the
input-threshold / edge-rate / duty sweep. The reference-jitter limit is
recorded as **unowned**, sequenced behind the noise methodology at **#505**.
The owed text is split accordingly, because the two halves have different
states and different blockers.

**It is deliberately not re-pointed at #13.** #13 is the obvious candidate —
it is where this repository's noise methodology was written — and it is *also
closed* (2026-09-08), with its own successor gap filed as #505. Substituting
one closed issue for another would have reproduced, in the same edit, the
precise defect this record exists to repair. An empty owner column is a worse
look and a better fact. **No requirement in the row moves**:
V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD, ≤ 5 ns 10–90 %, and 30 – 70 % duty all stand
exactly as ratified. This is an attribution fix, not a relaxation.

**2. The three electrical lines stay `budget`, and the row says what would
change that.** Levels, edge rate and duty are *not* upgraded to `measured` —
nothing is measured yet. What changes is that the row now names the campaign
that would discharge each one and the quantity it grades (`dphi_shift`, the
per-corner shift of the sampled phase), so the next reader can tell an unowned
gap from a queued one. A campaign directory is not evidence and this record does
not let it be cited as any.

**3. The reference-source-quality exclusion is restated, its ownership stated
honestly, and narrowed to say what it does and does not cover.** The exclusion stands:
*every jitter and spur number in `spec/pll.md` is the block's own contribution,
measured or derived against an ideal reference.* Three things are added to it:

- **It is recorded as unowned**, not re-pointed at #12 (closed, wrong subject)
  nor at #13 (also closed). Converting it into a numeric limit needs the
  closed-loop noise bench, whose own methodology gap is #505; the limit is a
  further measurement on top of that and nobody holds it today.
- **What the exclusion covers is stated as a boundary, not a gap.** It excludes
  the *reference source's* phase noise. It does **not** license the block's own
  reference-input path to contribute: that path's contribution is exactly what
  `sim/reference-input-contract` measures, and it is inside the block's budget,
  not the integrator's.
- **The input-side coefficient an integrator needs is named as a deliverable of
  that campaign**, so the exclusion hands over something concrete rather than
  only a caveat: `dtdv_worst`, the seconds of sampling-instant displacement per
  volt of reference amplitude noise at the worst legal reference slope. A
  reference whose edges are at the ≤ 5 ns budget converts its own amplitude
  noise into timing noise at that rate; a reference with fast edges does not.
  That is the mechanism the `20·log₁₀(N)` line does not cover, and stating it is
  how the exclusion stops being purely a disclaimer.

**4. A campaign directory with no record is disclosed as such, everywhere it is
cited.** `sim/README.md`, `sim/CHARACTERIZATION.md` and
`docs/chipalooza/challenge-5-proposal.md` each carry
`reference-input-contract` marked as declared-and-unmeasured, on the same terms
`sim/period-jitter-band-top` already is. The proposal's §5 verdict for this row
stays **UNMET**.

## Alternatives considered

- **Re-point the row at #13** — for the whole row, or for the reference-jitter
  half alone. Rejected twice over. Substantively, #13's subject is noise
  methodology, and the levels/edge-rate/duty sweep is not a noise measurement:
  it is a deterministic delay sweep that needs no noise machinery and was never
  blocked on #13's TRANNOISE gap, so folding it under #13 would have made an
  unblocked measurement look blocked. **And mechanically, #13 is closed** —
  since 2026-09-08, with its own successor gap at #505. This alternative was
  the draft of this record until that was checked, which is the strongest
  available evidence for §Decision 1's rule: an owner column must be verified
  against the forge at the moment it is written, not inferred from what the
  issue is *about*.
- **Leave `#12` and add a footnote that it is closed.** Rejected: a ratified
  table is read by people who do not read footnotes, and the failure mode being
  fixed is precisely a reader concluding the obligation was discharged. The
  table is the artefact that has to be right.
- **Upgrade the duty line from `budget` to `argued`, or to `measured`, on the
  schematic argument alone.** Rejected. The rising-edge-only argument from
  `design/pfd.sch` is sound and the row already states it, but an argument from
  a schematic is not a corner-swept result, and this repository's rule is that a
  claim needs a testbench. The campaign now states the argument in falsifiable
  form — `|dphi_shift|` at 30 % and 70 % duty ≤ 1 % of `d_ref` — which is worth
  more than a status upgrade and costs nothing if it fails.
- **Replace the exclusion with a number derived from the `20·log₁₀(N)`
  transfer.** Tempting because the transfer is already stated, and rejected
  because it is a transfer, not a limit: multiplying an unmeasured input by a
  known gain produces an unmeasured output. Inventing the input is exactly the
  unsupported number `CLAUDE.md` forbids.
- **Hold this record until the campaign has a measured record.** Rejected. The
  attribution defect is live *now* — the ratified table points at a closed issue
  today, and every day it does, a reader can reasonably conclude the work is
  done. The defect is independent of the measurement and is fixed independently
  of it. Deferring would also leave the measurement unowned for as long as the
  deferral lasted, which is the failure being repaired.

## Consequences

- **`spec/pll.md` changes in three places and no requirement moves**: the
  Verification-owed row's owner column and owed text; the Reference input row's
  Basis column, which now names the campaign behind each budget line; and the
  reference-source-quality paragraph, whose "(#12)" becomes an explicit
  *unowned*, plus the boundary statement of Decision 3.
- **The measurement is still owed, and now has somewhere to be owed from.**
  Zero of the 288 declared points are measured. `sim/CHARACTERIZATION.md`'s
  Reference input row moves from "no campaign directory covers this" to "a
  campaign exists, every point of it is owed" — the same state
  `period-jitter-band-top` is in, and stated in the same words so the two read
  alike.
- **The blocker on those points is not a missing mechanism, and is not in this
  repository.** Two distinct faults were found in the path to the fleet:
  1. *In this repository, and fixed, but not by this record's PR*:
     `sim/harness/batch.py`'s `_launch` passed `capture_output` / `text` /
     `check` into a runner that already supplies all three, so every real
     submission died with `TypeError: subprocess.run() got multiple values
     for keyword argument 'capture_output'` — **after** `_upload` had already
     written the job document and inputs to the bucket. The suite's transport
     stub accepts and drops arbitrary keywords, which is why it stayed green.
     A full-grid submission from this campaign failed at point 0 of 288 on
     it. The fix was diagnosed here, but landed independently on `main` via
     issue #512 / PR #519 (`b6114ad4`) while this record's PR was still open;
     this record's own copy of the same fix was dropped in favor of theirs on
     rebase, and `sim/tests/test_execution_backend.py` carries both regression
     suites — `DefaultRunnerTests` (#512/#519) and this record's
     `StrictRunnerSignatureTests`, kept because it binds against
     `subprocess.run`'s real signature and so catches an illegal keyword at
     *any* submission call site, not only the three runner-owned ones
     `DefaultRunnerTests` checks by name. **This also blocked
     `sim/period-jitter-band-top` (#503)**, whose own unrun grid was waiting on
     the same path believing it to work.
  2. *Outside this repository, and not fixed here*: with that repaired, the
     launch reaches the fleet's provisioning script, which fails
     `only 0 subnet/AZ(s) resolved, floor is 3`. That script runs its AWS calls
     under an **admin** profile; the dispatch host carries only the submit-only
     credential. Reproducible with no harness involved, by invoking the
     provisioning script directly. It is a worker-provisioning matter, not a
     design or a spec matter, and is routed to the operator on #499.
- **The bad consequence, stated plainly**: this record improves the *bookkeeping*
  of a gap without closing the gap. After it, `spec/pll.md` is honest about
  three unmeasured lines instead of dishonest about them, and that is all. An
  outside reader of `docs/chipalooza/challenge-5-proposal.md` §5 still finds
  **UNMET** against the Reference input row's electrical contract, and should.
- **Nothing in `design/` changes**, no schematic, no netlist, and no `sim/`
  record is added, rewritten or superseded. The append-only tree is untouched.
- **The path to needing a further record is named**: if the campaign, once run,
  measures a `dphi_shift` outside the 1 ns static-phase bound at any corner, the
  contract's limits — not its bookkeeping — are what a new record has to
  re-derive, and the candidate levers are the reference contract itself
  (tightening the ≤ 5 ns edge-rate budget) or the PFD input path. Widening the
  static-phase bound to fit the result is not one of them.

## Amendment A1 — the REF-drive premise is scoped to records, and its reproduction command reaches both deck extensions (issue #237)

**Date**: 2026-09-25. **No decision, target, budget or verdict moves.** This
amendment corrects a factual imprecision in §Context that this record's own
§"What now exists" already contradicted on the day it was written.

§Context asserted its uniformity over the *decks* this repository holds rather
than over the *records* they produced, and offered a `.sp`-only glob over
`sim/*/testbench/` as the reproduction. (Neither the superseded sentence nor
its glob is reproduced here: the check described below cannot tell a document
asserting a claim from one quoting it, and `git log -p` on this file is where
the exact prior wording belongs.) Both halves were wrong in the same way, and
in this record's own favour:

- **The claim was about decks when the premise it supports is about records.**
  The campaign this record lands exists precisely to vary the reference
  waveform. Its deck was committed by the same PR (#518) that wrote the
  sentence, so the sentence was false about decks from the moment it was
  written — while the thing it is used for, that every jitter, spur and phase
  number in this repository was measured against an ideal reference, was and
  remains true, because that deck has produced no record.
- **The reproduction command could not return the counterexample.** This
  repository writes SPICE decks as both `.sp` and `.spice` (`sim/harness/batch.py`
  loops `for f in *.spice *.sp` for exactly that reason); the campaign deck is
  `.spice`, and the quoted glob says `*.sp`. The command therefore returned ten
  decks of one shape and read as a confirmation. A reproduction command offered
  as evidence has to be able to return the thing that would disprove it.

Both are corrected in place above: the premise is scoped to testbenches that
have produced a record, and the command names both extensions and both
`testbench*/` directories — 13 decks, 12 of one shape, the deviating one named.

`docs/chipalooza/challenge-5-proposal.md`'s Reference input row carried the
same sentence and the same glob, transcribed from here, and is corrected in the
same change. `sim/lib/check-ref-drive-claims.sh` now grades both documents in
CI: a quoted command's glob may not be outreached by its own pattern, an
unscoped uniformity claim must hold over every deck its command can reach, a
deviating deck must be named, and — the rule that needs no wording at all — a
deck that varies the reference waveform must carry no record. The last is the
one that guards this record's actual premise; if it ever fires, the
source-quality exclusion of Decision 3 has to be re-argued rather than
re-asserted.

## Amendment A2 — the deck count moved, the claim did not (issue #510)

**Date**: 2026-09-25. **No decision, target, budget or verdict moves.** §Context
and Amendment A1 state a *count* alongside the claim they support — "13 decks,
12 of one shape, the deviating one named". Issue #510 lands one more
ideal-`REF` deck, `sim/reference-spur-band-top/testbench/tb_reference_spur_band_top.sp`,
so the same command now returns **14 decks, 13 of one shape**, with the same
single deviating deck (`sim/reference-input-contract`'s). The counts above are
left as written — they were true of the tree that minted this record — and are
corrected here rather than in place.

**The premise is unaffected, and that is the point of recording this.** What
Decision 3 rests on is not how many decks exist but that every deck which has
produced a *record* drives `REF` with the identical ideal pulse. The new deck
carries no record (its campaign is declared and unmeasured, DR-024), and it is
of the ideal shape in any case, so it neither weakens nor strengthens the
source-quality exclusion. `sim/lib/check-ref-drive-claims.sh` grades the
property rather than the number, which is why it passed across this change
without either document being edited.
