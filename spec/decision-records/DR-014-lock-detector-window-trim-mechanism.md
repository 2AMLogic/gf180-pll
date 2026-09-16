# DR-014: The lock-detector window's spread fix is a trim code, not a bias-referenced delay

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-010 and
  DR-013 record (a builder drafts the record on the evidence; the operator's
  PR approval is the ratifying act). Status stays `proposed` until that
  approval and merge.
- **Date**: 2026-09-16
- **Decided by**: Builder agent, issue #407
- **Revises**: `spec/pll.md`'s [Lock detector](../pll.md#lock-detector)
  section — gap 1's size-of-miss text and the T2′ status wording — and the
  [Verification owed](../pll.md#verification-owed) row for the lock detector.
  **T1′/T2′'s numbers do not change** (DR-013 already fixed them); this
  record picks the *mechanism* DR-013 Decision 5 deliberately left open, and
  does not itself implement it.
- **Consumes**: DR-013 (states the ≤ 1.65× spread target — Decision 4 — and
  names the two candidate mechanisms without picking one — Decision 5), DR-006
  Decision 5 (the [Icp trim-code rule](../pll.md#icp-trim-code-rule), the
  idiom this record follows), DR-002 Decision 4 (scope boundary: a passive
  monitor, no band-search or self-calibration FSM — a rule the trim route must
  keep and the bias-referenced route would not have threatened either).
- **Evidence**:
  - `sim/lock-detector/records/20260916-122705-98c935b.md` — 189 points,
    clean tree at commit `98c935b395bf6b96aa00a98afdb71c324cc6e8e1`, the
    0.02 ns refinement DR-013 Decision 3 owed (issue #407 scope item 1). Sizes
    the T2′ miss at `ss`/125 °C/2.97 V to **[2.02, 2.04) ns** — a measured
    **1.0–2.0 %** overrun against the 2 ns T2′ budget, replacing DR-013's
    unresolved 0–5 % bound. This does not change Decision 4's ≤ 1.65× target
    (that target was already derived from the band's own margin requirement,
    not from the size of today's miss) and does not change which mechanism
    reaches it (see below) — it only replaces an open question with a
    measured, smaller one.
  - DR-013's own within-bundle voltage/temperature spread table (already
    measured; no new simulation needed for this decision): **1.453×** (`ff`),
    1.481× (`sf`), 1.491× (`typical`), 1.502× (`fs`), **1.513×** (`ss`).
    Combined with the trim step's own quantization (`sim/lock-window-sizing`'s
    0.5 µm ladder step is worth 4.6–4.8 % of window, so ± 2.4 % if trimmed to
    the nearest step), DR-013 already projected this route at **≈ 1.55×** —
    inside the 1.65× target with ≈ 13 % of margin per edge.

## Context

DR-013 Decision 4 set a numeric target (≤ 1.65× PVT spread of the observable
window) that no sizing of the present `delaywin_3v3` topology can reach: the
spread is a property of the open-loop inverter-chain-into-MOS-cap chain, not
of its sizing (1.928× at W = 8 µm, 1.906× at W = 26 µm — a 3.25× sizing change
buys 1 % of spread). Decision 5 named two candidate mechanisms — a
bias-referenced delay and a fixed trim code — and deliberately did not choose
between them, on the same "decide the axis the fix must act on; do not pick
the circuit without the evidence to pick it" pattern DR-012 Decision 7 used.
Picking the mechanism, and only the mechanism, is issue #407 scope item 2.

Issue #407 also asked, first and cheaply, for the coarse-to-fine sizing of the
still-unresolved T2′ miss (scope item 1) before spending effort on the
mechanism decision. That is done — see Evidence above — and it does not change
the direction of this decision, only the size of the number it starts from:
the flag is out of band by 1–2 %, not by an unresolved 0–5 %.

## Decision

**1. The mechanism is a trimmed delay: a fixed, test-set trim code, in the
same idiom as the existing [Icp trim-code rule](../pll.md#icp-trim-code-rule),
not a bias-referenced delay.** The trim route is chosen because it is already
evidenced as reaching Decision 4's target — DR-013's own within-bundle spread
numbers plus quantization land at ≈ 1.55×, inside 1.65× with ≈ 13 % of margin
per edge — while the bias-referenced route's own achievable spread in this PDK
is unmeasured and it adds an analog bias network to a cell DR-010 called
deliberately simple. Choosing the route that is *already* evidenced over the
route that would need new analog design work and its own characterization
campaign before it could even be compared is the same preference for measured
answers over speculative ones CLAUDE.md's "no claim without a testbench" rule
already states; it is not a preference for simplicity for its own sake.

**2. The trim is a process trim only, applied once at test, held for the life
of the part.** It is explicitly **not** a self-calibration FSM: DR-002
Decision 4 put a digital `lock` output in v1 scope as a passive monitor with
no band-search or calibration hardware, and that scope boundary applies to the
delay cell the monitor's window is built from exactly as it applies to the
monitor itself. The trim code is a static configuration input, set from a
test-time measurement of the cell's own delay (a 1–2 ns quantity, well within
a production tester's resolution), the same shape of decision the
[Icp trim-code rule](../pll.md#icp-trim-code-rule) already makes: "set from
[a fixed, known condition], not a discretionary margin knob."

**3. This is a block-interface change, and this record is the decision record
it requires.** Adding a trim-code input to `delaywin_3v3` (or its replacement)
changes the cell's pin list — DR-013 Decision 5 named this explicitly as the
condition under which the mechanism pick needs its own decision record. This
record satisfies that condition for the *choice of mechanism*. It does not by
itself define the trim code's bit width, step size, polarity, or default —
those are sizing questions that reopen from scratch once the circuit exists
(DR-013 Decision 6), and are scoped to the follow-up issue below, not decided
here in advance of the evidence a real circuit would produce.

**4. Implementation and re-characterization are scoped to #411, not to this
record or to #407 directly.** Realizing the trim in the schematic (e.g. a
binary- or thermometer-coded array of switched MOS-cap segments per delay
stage, sized against `sim/lock-window-sizing`'s own 0.5 µm ladder granularity
as a starting reference for the achievable step), sweeping the trim-code axis
across the full PVT grid to find a code (or per-bundle code set) that holds
T1′ and T2′ simultaneously, and re-running the full in-situ
`sim/lock-detector` loop plus the downstream `sim/supply-sensitivity` re-take
DR-013 already named as owed, is a separate, multi-hour circuit-design-and
-campaign phase from the mechanism pick itself. See #411's scope for the full
breakdown.

## Alternatives considered

- **A bias-referenced delay** — rejected for now, not permanently foreclosed.
  Its own achievable spread in this PDK is unmeasured, and measuring it would
  require designing and characterizing a whole new analog block before it
  could even be compared against the trim route's already-measured ≈ 1.55×.
  DR-013's own "what is still not known" list keeps this route on the table:
  if #411's actual trim implementation fails to hold ≤ 1.65× once device
  mismatch and extraction are folded in, a future record can reopen this
  choice on that evidence. It is not reopened speculatively here.
- **Decide the trim's bit count and step size in this record, alongside the
  mechanism.** Rejected: DR-013 Decision 5's own pattern — decide the axis the
  fix must act on; do not pick the circuit before the evidence to pick it —
  applies one level down here too. The step-size-vs-margin tradeoff is a
  sizing question that cannot be answered without a real trimmed circuit to
  sweep, and choosing a bit count in advance of that evidence would be
  choosing a number to fit a wish rather than a measurement, which CLAUDE.md
  forbids for the spec generally and which this record extends to the
  mechanism's own parameters.
- **Defer the mechanism decision until #411 lands a full implementation and
  re-characterization in one PR.** Rejected: DR-013 Decision 5 requires a
  decision record before a block-interface change is made, and the mechanism
  pick is a separable, cheap decision — it rests entirely on evidence DR-013
  already measured, with no new simulation required — that does not need to
  wait on, and should not block, the (materially larger) circuit-design work
  in #411.

## Consequences

- **`spec/pll.md` changes**: the [Lock detector](../pll.md#lock-detector)
  section's gap 1 restates the T2′ miss as measured (**[2.02, 2.04) ns**,
  **1.0–2.0 %** past budget) rather than the prior unresolved 0–5 % bound, and
  records that the fix mechanism is now decided (trim) though not yet
  implemented; the summary table's row 16 status wording and the
  [Verification owed](../pll.md#verification-owed) row for the lock detector
  are updated the same way, with item (a) — the 0.02 ns refinement — marked
  done and a pointer to #411 replacing the open-ended "(b) the lower-spread
  delay itself" text.
- **`sim/CHARACTERIZATION.md`'s `lock-detector` and `lock-window-sizing` rows**
  are re-pointed to cite the new record and this decision; no committed record
  is edited.
- **`delaywin_3v3` stays as drawn (W = 9.5 µm)** until #411 lands its
  replacement. DR-013 Decision 6 is otherwise unchanged by this record.
- **The [Icp trim-code rule](../pll.md#icp-trim-code-rule) itself is
  untouched.** A future "lock-detector trim rule" normative section would join
  it as a sibling callout once #411 lands the actual code table — that table
  does not exist yet and is not created by this record, which fixes the
  mechanism, not the numbers.
- **`sim/lock-time`'s held re-take (DR-013 Decision 7) stays held.** It is
  released when #411 lands a window meeting Decision 4's ≤ 1.65× target, not
  by this mechanism pick alone.
- **Nothing in `sim/` is invalidated.** This record is a specification and
  mechanism decision only; no design file changes and no committed evidence
  record is edited or superseded.
