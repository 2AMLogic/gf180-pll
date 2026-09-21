# DR-015: The lock-detector window trim reaches the pads as four dedicated static digital inputs — already built, not a new choice

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-010,
  DR-011, DR-013 and DR-014 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge, even though the interface this
  record documents is already implemented and merged — what is pending
  ratification is the *decision record itself* as the spec-process artifact
  DR-014 said was still owed, not the schematic or netlist.
- **Date**: 2026-09-21
- **Decided by**: Builder agent, issue #441

## Context

`spec/pll.md`'s [Lock-detector window trim-code rule](../pll.md#lock-detector-window-trim-code-rule)
(normative, DR-014) requires the 4-bit static trim code `LDT3:LDT0` to be set,
once per part at test, from that part's own measured comparator-window delay.
DR-014 itself picked the trim *mechanism* (a fixed code over a bias-referenced
delay) but explicitly scoped out "bit width, step size, polarity, or default"
— and, by the same logic, it never addressed how those four bits reach the
die's pins at all. That is a distinct question from the trim mechanism: four
bits have to land on real pads somehow, against the Challenge #5 harness's
24-slot digital-control-input budget (Epic #542), and nothing before this
record said which of the plausible options — dedicated pins, a shared/muxed
bus, a serial shift-in register, or a fuse/metal option — was chosen.

Issue #441 found that `docs/chipalooza/challenge-5-proposal.md` §2.2's pad
table, which maps this design's I/O onto that budget, had no `LDT0`–`LDT3`
entry at all — the proposal described a part that could not be configured
into its own ratified spec. Investigating that gap turned up the answer
already on `main`: `LDT0`–`LDT3` are not an open design question. They landed
as real, top-level `pll_top` ports via PR #418 ("Implement the lock-detector
window trim (DR-014) and re-characterize T1′–T5", commit `bfde9893`, merged
2026-09-18T21:24:34-07:00) — three days before issue #441 was filed. Verified
directly against `origin/main` (`387d03c6`, 2026-09-21):

- `design/pll_top.sch` carries four `ipin.sym` instances — `p_ldt0`…`p_ldt3`
  (lines 98–101) — each wired to a top-level net (`LDT0`…`LDT3`), in the same
  idiom as the existing `p_cpb0`/`p_cpb1` charge-pump trim pins (lines 90–91).
  The schematic's own header comment (lines 63–66) documents `LDT3..LDT0` as
  "lock-detector window trim, 4-bit binary … DR-014: a fixed process trim set
  once at test, same idiom as the Icp trim code — not a calibration loop,"
  alongside the `CPB1 CPB0` entry it sits next to.
- `design/netlist/pll_top.spice`'s `.subckt pll_top` line lists
  `REF B0 B1 B2 CPB0 CPB1 LDT0 LDT1 LDT2 LDT3 P0 P1 P2 P3 P4 P5 SEL0 SEL1
  SEL2 SEL3 SEL4 SEL5 IBN ICN IBP ICP CLK DIVOUT FB LOCK VCTRL` — `LDT0`–`LDT3`
  sit between `CPB1` and `P0`, declared with `*.ipin` markers exactly like
  every other static digital-control input.

So the pad-budget-exposure decision this record is required to make (per
CLAUDE.md: "spec changes go through `spec/` with a decision record") already
has a built, evidenced answer. This record exists to make that answer an
official spec-process artifact — the thing DR-014 itself said was still
missing — not to relitigate it from a blank slate.

## Decision

**The lock-detector window trim reaches the die as four dedicated static
digital-control-input pins, `LDT3:LDT0` — the same shape of interface the
charge-pump `Icp` trim (`CPB0`/`CPB1`) already uses.** This is Option 1 of
the candidate set issue #441 enumerated (four dedicated digital control
inputs), chosen and **already implemented**, not merely selected here:

1. **The interface exists in `design/` today.** `design/pll_top.sch` and
   `design/netlist/pll_top.spice` both carry `LDT0`–`LDT3` as top-level
   `pll_top` ports as of commit `bfde9893` (PR #418, merged 2026-09-18). No
   schematic or netlist change accompanies this record.
2. **It fits the Challenge #5 24-slot digital-control-input budget with
   headroom.** Re-deriving the count directly from
   `design/netlist/pll_top.spice`'s `.subckt pll_top` port list against
   `docs/chipalooza/challenge-5-proposal.md` §2.2's own categorization: 1
   (`REF`) + 3 (`B0`–`B2`) + 2 (`CPB0`–`CPB1`) + 4 (`LDT0`–`LDT3`) + 12
   (`P0`–`P5`, `SEL0`–`SEL5`) = **22 of ≤ 24**, leaving 2 slots of headroom.
   Before this record, the proposal's own total (omitting `LDT0`–`LDT3`
   entirely) stood at 18 of 24.
3. **Dedicated pins were the right choice given what already exists,** not
   merely the least-surprising default. A shared/muxed bus (option 2) or a
   serial shift-in register (option 3) would each require new on-die
   multiplexing or shift logic that does not exist and was never drawn for
   this purpose — a real design change this record would then need to
   authorize, on top of the pad-count savings such a change would buy. A
   fuse/metal option (option 4) is foreclosed by DR-014 Decision 2 and the
   trim rule itself: the code is measured per-part at test and applied once,
   which is not what a fixed metal option or fuse encodes. With the dedicated-
   pin interface already built, evidenced, and fitting the budget with
   margin, there is no unmet constraint left for a different mechanism to
   solve.

This record's scope is the pad-budget-exposure choice only — it does not
revisit DR-014's mechanism choice (fixed trim code) or #411's bit-width/step/
default choices (4 bits, 16-code array, nominal code 1000/8), both of which
are already ratified and implemented.

## Alternatives considered

- **Share the existing digital control bus** (multiplex the trim code onto
  already-static pins behind a mode/strobe pin), costing 1–2 slots instead of
  4. Not chosen: it needs on-die mux/strobe logic that `design/` does not
  have today, and the 24-slot budget already accommodates the built
  dedicated-pin interface with 2 slots to spare — there is no pad-count
  pressure this alternative would relieve.
- **A serial/shift-in configuration register** for all static trim state
  (`CPB1:CPB0` + `LDT3:LDT0`, 6 bits), costing 2–3 slots. Not chosen for the
  same reason: it is unbuilt, would also change how `CPB0`/`CPB1` are
  described in §2.2, and buys pad-count margin the design does not currently
  need.
- **Fuse/metal-option the code.** Not chosen: DR-014's own trim rule sets the
  code from a per-part test measurement at a fixed reference condition — a
  fixed metal option or fuse defeats the rule's per-part adaptivity outright,
  the same objection DR-014 itself raised against a non-adaptive mechanism.
- **Revisit the lock-detector trim rule** (conclude the trimmed-window
  approach does not fit Challenge #5's I/O envelope). Not applicable: the
  slot arithmetic above shows the chosen mechanism fits with margin, so there
  is no infeasibility finding to record.

## Consequences

- **`docs/chipalooza/challenge-5-proposal.md` §2.2 and §2.3 are updated** (in
  the same PR as this record) to add an `LDT0`–`LDT3` row to the pad table,
  matching the `CPB0`/`CPB1` row's format, and to restate the "Totals against
  the Challenge #5 budget" paragraph's digital-control-input count as 22 of
  ≤ 24. §2.3's dropped/multiplexed/substituted list now states explicitly
  that `LDT0`–`LDT3` are neither dropped nor newly added relative to
  `design/pll_top.sch`'s port list.
- **No design or netlist file changes.** The interface this record documents
  already exists; nothing in `design/` is added, removed, or resized here.
- **No `spec/pll.md` changes.** The [Lock-detector window trim-code
  rule](../pll.md#lock-detector-window-trim-code-rule) already states the
  trim requirement; this record only settles how the trim's four bits reach
  a pad, which the rule itself was never scoped to answer.
- **Future harness integration work** (bench test plans, tester programming)
  can now cite `LDT0`–`LDT3` as fixed, addressable pins rather than as an
  open interface question.
