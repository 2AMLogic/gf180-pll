# DR-011: Post-supply-step phase settling — no filter change, and a stated limitation rather than an invented bound

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007 and DR-009 record
  (a builder drafts the record on the evidence; the operator's PR approval is
  the ratifying act). Status stays `proposed` until that approval and merge.
- **Date**: 2026-09-15
- **Decided by**: Builder agent, issue #387 (finding 2)
- **Relates to**: DR-006 (loop-filter component values and the Icp-trim rule)
  — this record **does not** revise it. DR-006 Decisions 1, 3 and 7 stand
  unchanged. It adds one statement to `spec/pll.md`'s
  [Lock time](../pll.md#lock-time) section, alongside (not in place of) the
  existing cold-start row 9.
- **Evidence**:
  `sim/supply-sensitivity/records/20260915-202323-62391c6.md` — the
  post-step settling bracket, arithmetic on committed data, no new
  simulation. Consumes `.../20260901-155456-46b92f8.md` (#253/#255, the
  escalated step/ramp run and its section 3c END-plateau result),
  `.../20260915-124108-49f539f.md` and `.../20260915-105055-2d6ab99.md`
  (#389/#384, the classification), and
  `sim/lock-detector/records/20260802-050119-c24ee3a.md` (#11, the assert
  edge and assert hold-off).

## Context

After a 3.30 → 3.63 V supply step (+10 % of nominal, 100 ns edge), `lock`
stays deasserted for the whole of the escalated 40.08 µs high-plateau hold at
all 3 sampled corners. #384/#389 split that by corner: `ff`/125 °C is
structural (its own undisturbed steady state does not assert either — DR-010
Decision 4), while `ss`/-40 °C and `typical`/27 °C **do** assert fine
undisturbed at the same rail, so their failure is a transient phase-settling
tail. At the hold's own end those two corners still had 1.298 ns and
0.6861 ns of phase to shed before the detector could assert, and were still
shedding it.

#387 asks whether that indicts the loop-filter sizing. `sim/loop-dynamics`
(#10, closed) answered a *steady-state* phase-margin question (≥ 45°, met at
47.4° worst) and a *cold-start* settling-floor question (≈43 µs, set by the
dominant pole at 1/(2πRC1) = 17.09 kHz). Neither is the same question as
"how long does the loop take to get the static phase back inside the
detector's window after a mid-operation supply excursion", and `spec/pll.md`
states no bound on it: row 9 covers cold-start acquisition only.

## Decision

**1. No change to the loop filter.** `design/loop_filter.sch`'s values and
DR-006's sizing stand. Two measured facts support this and neither is
ambiguous:

- The remaining phase at the hold's end closes within **2.8 … 8.2 µs**,
  putting the phase back inside the detector's assert edge **37.2 … 42.6 µs**
  after the step edge — against the **34.40 µs** the escalated run actually
  reached. The hold was 8 … 24 % short of the answer, not short by an order
  of magnitude, and the result lands at or below the same loop's own
  cold-start structural settling floor of 43 µs.
- Over the 3.2 µs window actually observed, the distance to the assert edge
  was closing **faster** than a single pole at the loop's own τ = 9.313 µs
  would give (shrink factor 0.467 and 0.587 against `exp(-dt/τ)` = 0.709).
  That is the wrong sign for "the filter is under-damped enough to matter
  here".

**2. No settling-time *bound* is added to `spec/pll.md`.** A spec number is a
claim, and CLAUDE.md's "no claim without a testbench" applies to it. The
37.2 … 42.6 µs above is a **two-sample extrapolation**, and one committed
result at one of these same two corners is inconsistent with the model it
rests on: `46b92f8` section 3c measured `ss`/-40 °C's END-plateau *frequency*
residual decaying by 0.809 over 3 τ against a 0.0493 single-pole expectation
— roughly 16× slower — and classified it `under-damped`. Two phase samples
cannot distinguish the two behaviours. Promoting the bracket to a spec bound
would be exactly the "Not simulated" failure DR-001 §Prior art warns against.

**3. `spec/pll.md` gains a stated limitation instead — with the lower bound
that *is* measured.** The Lock time section states, in as many words, that
the specification makes **no claim** about re-lock time after a mid-operation
supply excursion, and that what is measured is a lower bound: at 2 of 3
sampled corners `lock` had not re-asserted **34.40 µs (3.70 τ)** after a
+10 % step, with the static phase still decaying monotonically at that
instant. This is a gap recorded rather than papered over, in the same form
the Lock detector section's own two gaps already take.

**4. The campaign that would close it is named, not performed.** Measuring
the post-step re-lock time needs the step/ramp deck re-run with the
high-plateau hold pushed out past `lock` re-assertion — at 2.5 h per corner
for the existing 40.08 µs hold, roughly 6 h per corner at a hold long enough
to catch it — and/or per-cycle phase instrumentation so the decay law is
measured rather than fitted to two points. That is a `sim/loop-dynamics`
successor campaign, filed as **#395**.

## Alternatives considered

- **Declare the margin adequate and state 43 µs (the cold-start floor) as the
  post-step bound.** Rejected: it is the right order of magnitude and it is
  not measured. A bound that happens to be correct for the wrong reason is
  indistinguishable, to a later reader, from one that is wrong.
- **Declare the tail a design defect and re-size the filter for faster
  settling.** Rejected: nothing in evidence indicts the sizing (Decision 1),
  and DR-006 Decision 7 already establishes that the ≈43 µs floor is set by
  the dominant pole "regardless of how much Icp is applied". Reaching a
  materially faster post-step recovery means reopening DR-001 Decision 1's
  fixed-filter constraint — a large change, on no evidence that it is needed.
- **Re-run the step/ramp deck now with a longer hold and settle it properly.**
  Not chosen for *this* record's scope, on cost: the committed escalated runs
  took 8 893 … 9 070 s of analysis time each for a 40.08 µs hold, so the run
  that answers this is hours per corner. It is the right work; it is a
  campaign, not a paragraph, and it is filed as one — #395.
- **Say nothing in `spec/pll.md` and leave the finding in `sim/` only.**
  Rejected: a consumer reading row 9 today would reasonably infer the
  block re-locks promptly after a supply disturbance, because the file's only
  lock-time statement is about cold start. The silence is itself misleading,
  which is what Decision 3 fixes.

## Consequences

- **`spec/pll.md`'s Lock time section gains a limitation paragraph and its
  Verification-owed table gains a row.** No target changes, no measured value
  changes, and row 9's own carve-out from ratification (DR-007 Amendment A1,
  for the cold-start question) is unaffected either way by this record.
- **A consumer gating logic on `lock` now has a stated worst case to design
  against, and it is "unbounded, ≥ 34.4 µs".** That is worse, from a
  consumer's point of view, than a number — and it is the truthful state of
  the evidence. It becomes a number when #395 runs.
- **Only 3 of 45 corners, and only one excursion size, have ever been run on
  the step/ramp deck** (`run.sh`'s `DYN_PICKS` samples 3). Nothing here — the
  limitation, the lower bound, or the decision not to change the filter —
  generalises past those 3 corners, that +10 % step, or that
  (f_ref = 12.5 MHz, N = 8, one trim code) cell. #395 inherits that as its
  first scoping question.
- **This record is falsifiable, deliberately.** If #395 measures a post-step re-lock materially past the ~43 µs neighbourhood — the
  outcome 3c's `under-damped` result would predict — then Decision 1 was
  wrong and a successor record must revise it. The bracket and the model it
  rests on are both stated in the evidence record so that comparison is
  mechanical rather than a matter of reinterpretation.
