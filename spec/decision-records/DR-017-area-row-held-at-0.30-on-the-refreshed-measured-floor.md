# DR-017: The area row is **held** at ≤ 0.30 mm² on a re-measured floor 17.5 % below the one DR-016 amended it onto, and the spec's measured table is refreshed to the committed GDS

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009 … DR-016
  record (a builder drafts the record on the evidence; the operator's PR
  approval is the ratifying act). Status stays `proposed` until that approval
  and merge.
- **Date**: 2026-09-23
- **Decided by**: Builder agent, issue #476 (follow-up to #458; successor to
  DR-016, issue #456)
- **Relationship to DR-016**: **successor, not supersession.** DR-016 stays
  `ratified` and binding: its Decisions 1, 2, 3 and 5 are unchanged and this
  record re-states none of them. What this record does is (a) answer the
  successor question DR-016 Decision 4 invited, with a **hold**, and (b)
  replace the *trigger* in that decision with a sharper one (§Decision 3). No
  `superseded by` pointer is added to DR-016, because none is owed.

## Context

DR-016 (#456) amended [Area](../pll.md#area) from the draft ≤ 0.15 mm² to
**≤ 0.30 mm²**, on a measured block sum of 218,631 µm² carrying
`PLL-FLOORPLAN.md` §5's ×1.25 top-level overhead up to 273,289 µm²
(0.2733 mm², 91.1 % of the row). Its Decision 4 left three reduction levers
open and said each one landing "is grounds for a *downward* re-amendment of
this row by a successor record". Three have since landed:

| Lever | Issue / PR | Block delta |
|---|---|---|
| `cp_output_stage` glue-bus track packing | #469 / PR #474 | `pfd_cp` 26,665 → 26,406 µm² (−259) |
| `divider_chain` Metal2 routed over its own device rows | #458 / PR #477 | `divider_chain` 92,618 → 55,329 µm² (−37,289) |
| `cp_output_stage` glue-inverter interleave | #473 / PR #478 | `pfd_cp` 26,406 → 25,630 µm² (−776) |

None of the three PRs refreshed `spec/pll.md#area`'s measured table, each for
the same stated reason: refreshing DR-016's block-by-block figures is the same
act as amending the row they sit under, and CLAUDE.md routes that through
`spec/` with a decision record. `PLL-FLOORPLAN.md` §5.13 and §5.14 name the
resulting lag explicitly rather than leaving a reader to trip over it. **This
record is that decision record**, and its first job is that the spec has been
asserting a block area the committed GDS does not have.

### The measurement

Re-derived from committed geometry at `origin/main` @ `8c6cb7f3` (2026-09-23)
by the command itself, not copied from any prior record or issue:

```
$ python3 layout/run_pv.py area
```

Per-block figures are the committed GDS bounding box, as written to
`layout/evidence/area-audit/area-audit.md` (which
`layout/tests/test_area_audit.py` re-derives and byte-compares on every run, so
it cannot drift from the geometry by hand):

| Block | Footprint | As-drawn | Basis |
|---|---|---|---|
| Loop filter (R + C1 + C2) | — | 36,936 µm² | DR-006 / `PLL-FLOORPLAN.md` §3 — a device-data **calculation** (32,118 µm² of measured device ×1.15); no loop-filter layout exists |
| `vco_block` | 172.52 × 184.48 µm | 31,826 µm² | committed GDS |
| `pfd_cp` | 344.98 × 74.30 µm | 25,630 µm² | committed GDS (folded at #455, glue bus packed at #469, glue inverters interleaved at #473) |
| `divider_chain` | 1317.66 × 41.99 µm | 55,329 µm² | committed GDS (macro band packed at #454, tracks routed over the device rows at #458) |
| `lock_detector` | 294.80 × 103.75 µm | 30,586 µm² | committed GDS (DR-014 trim network drawn at #449) |
| **Sum** | | **180,307 µm² (0.1803 mm²)** | **60.1 % of the ≤ 0.30 mm² row** |
| **After `PLL-FLOORPLAN.md` §5's ×1.25 top-level overhead** | | **225,384 µm² (0.2254 mm²)** | **75.1 % of the row; 1.50× the draft 0.15 mm² target** |

Against DR-016's own measurement: the block sum falls **38,324 µm² (−17.5 %)**
and the total **47,905 µm² (−17.5 %)**; the row's utilisation goes 91.1 % →
75.1 %, and the draft-target ratio 1.82× → 1.50×. The row is **met**, and was
met before as well — nothing in this record is a failing budget.

This is still a **sum of block extents, not a placed-and-routed top level**.
No assembled `pll_top` GDS exists (#17), so the ×1.25 factor remains the term
that is not measured, exactly as DR-016 said. That is the whole of the
judgement below.

### What did *not* change

DR-016 Decision 2 is explicit about what the row's margin means: it is sized
to the ×1.25 top-level overhead factor and to nothing else — "**not** an
allowance for block growth". Read against that definition, here is the state
of the uncertainty the margin exists to cover, then and now:

| | DR-016 (#456) | Today (#476) |
|---|---|---|
| Assembled `pll_top` GDS | does not exist (#17) | **does not exist (#17)** |
| `PLL-FLOORPLAN.md` §5's overhead factor | ×1.25, a ROM multiplier | **×1.25, the same ROM multiplier** |
| Loop-filter term | DR-006 device sum ×1.15, no layout | **DR-006 device sum ×1.15, no layout** |
| Measured block sum | 218,631 µm² | 180,307 µm² |

**Three of those four rows are unchanged.** The three levers that landed are
all Metal2 routing-track levers inside three already-drawn blocks; not one of
them measured the top-level overhead, drew the loop filter, or reduced the
uncertainty in either. What got smaller is the quantity the margin sits on top
of — not the uncertainty the margin is sized to.

### The floor, re-derived, with §5.13's correction applied

DR-016 carried two bounds below the as-drawn total: 143,955 µm² (every
remaining named lever at its geometric ceiling, ×1.25 → 0.1799 mm², 1.20×) and
136,141 µm² (every Metal2 track routed at zero area cost, ×1.25 → 0.1702 mm²,
1.13×). **Those two bounds have now converged**, because #458 spent exactly the
7,814 µm² of `divider_chain` that separated them, and §5.13 established that
the `max(packed-track floor, device band) × width` ceiling formula no longer
applies to a block that routes over its own device rows — that block's term has
to come from its device band:

| Block | Ceiling term | Basis |
|---|---|---|
| `vco_block` | 31,654 µm² | 172.52 × 183.48 (device band; its height *is* its device band) |
| `pfd_cp` | 16,921 µm² | 344.98 × 49.05 (device band, above its 39.75 µm packed-track floor) |
| `divider_chain` | 34,681 µm² | 1317.66 × 26.32 (device band — §5.13's correction) |
| `lock_detector` | 15,949 µm² | 294.80 × 54.10 (device band, above its 36.00 µm packed-track floor) |
| Loop filter | 36,936 µm² | no layout lever exists |
| **Sum** | **136,141 µm²** | **×1.25 → 170,176 µm² (0.1702 mm²), 1.13× the draft target** |

So **DR-016 Decision 3 survives this re-derivation unchanged and slightly
strengthened**: 0.15 mm² is still not reachable, now on a *single* bound rather
than two, and that bound is the one that assumes all routing is free. The gap
between the block sum as drawn (180,307 µm²) and that floor is 44,166 µm², all
of it routing band in three blocks — and, per §5.14, `pfd_cp`'s own routing
levers are spent.

## Decision

**1. `spec/pll.md`'s Area row is HELD at ≤ 0.30 mm² for the whole block.** It is
not amended downward on this measurement. Its status column is unchanged —
**measured (blocks) / budget (top-level overhead)**.

The reason is one sentence: **a margin sized to an uncertainty does not shrink
because the measurement it sits on top of shrank.** DR-016 Decision 2 defined
the margin as covering the unmeasured ×1.25 top-level overhead and nothing
else. That factor is identical today — same ROM multiplier, same absent
`pll_top` (#17), same absent loop-filter layout. Re-pricing the row now would
be re-pricing an uncertainty that has not moved, on evidence about a different
quantity.

The arithmetic of what holding buys, stated so the choice is falsifiable rather
than merely defended. The row allows 240,000 µm² of summed block footprint
against the ×1.25 factor; 180,307 µm² is drawn, i.e. **24.9 % margin on the
block-sum allowance**, and the row holds to a measured top-level overhead of
**×1.664**. Alongside the ≤ 0.25 mm² alternative §Alternatives rejects:

| If `pll_top` measures an overhead of… | block sum the ≤ 0.30 mm² row allows | headroom over the 180,307 µm² drawn | same at a ≤ 0.25 mm² row |
|---|---|---|---|
| ×1.25 (§5's ROM figure) | 240,000 µm² | +59,693 µm² (+33.1 %) | 200,000 µm² → +19,693 (+10.9 %) |
| ×1.40 | 214,286 µm² | +33,979 µm² (+18.8 %) | 178,571 µm² → **fails, with zero block growth** |
| ×1.50 | 200,000 µm² | +19,693 µm² (+10.9 %) | 166,667 µm² → **fails** |
| ×1.664 | 180,288 µm² | **fails, with zero block growth** | — |
| ×1.386 | — | — | **the point at which ≤ 0.25 mm² fails** |

**2. The spec's measured table is refreshed to the committed GDS**, so the file
stops asserting block areas that are 17.5 % larger than the geometry in the
repository. The table in §Context above is what `spec/pll.md#area` now carries,
with `layout/evidence/area-audit/area-audit.md` as its source and
`python3 layout/run_pv.py area` as the way to reproduce it. This half of the
record is not a judgement — it is a correction of a stale claim, and it is the
defect #476 was filed on.

**3. DR-016 Decision 4's re-amendment trigger is replaced.** That decision made
*any* lever landing grounds for a successor record. In practice that trigger
fired three times within two days, for landings of 259 µm² (0.1 % of the block
sum), 776 µm² (0.4 %) and 37,289 µm² (17.1 %) — and it obliged the layout
record to argue in prose, at §5.12, why a 0.1 % landing was "not grounds for
the successor record §5.11 described". A trigger that has to be talked out of
firing for two of its three firings is the wrong trigger. The replacement is
aimed at the uncertainty rather than at the measurement, and this row is
re-amended **downward** when either of these becomes true:

- **(a)** an assembled `pll_top` GDS exists (#17) and the top-level overhead
  becomes a *measurement* rather than §5's ×1.25 ROM multiplier; or
- **(b)** the loop filter is drawn, and its 36,936 µm² — **20.5 % of the block
  sum**, and the largest single term in it — becomes a measurement rather than
  DR-006's device sum ×1.15.

Either one collapses the only estimated terms in the product, at which point
the row can be set against a total that is measured end to end. Until then, a
smaller block sum is recorded in the measured table (Decision 2), which is
where a reader looking for "how big is this block" should be reading anyway.

**4. The fail-loud condition is unchanged in kind and restated on today's
numbers.** If the measured block sum exceeds **240,000 µm²**, or an assembled
`pll_top` measures a top-level overhead above **×1.664**, say so in a new
`PLL-FLOORPLAN.md` §5 revision rather than re-deriving the budget to fit. This
is asserted mechanically, not in prose: `layout/tests/test_area_audit.py`'s
`WholeChipAreaRowTests` re-derives the sum from the committed GDS on every test
run and fails the build in **both** directions — past the row, and (per DR-016
Decision 3) under the draft 0.15 mm² target, which would supersede that
decision. Neither constant in `layout/floorplan/skeleton.py`
(`AREA_BUDGET_UM2 = 300_000.0`, `TOP_LEVEL_OVERHEAD = 1.25`) moves in this
record, which is the mechanical corollary of Decision 1.

**5. The `lock_detector` lever remains open, unnamed and unsized, and does not
block this record.** It is the last of DR-016 Decision 4's three, against that
block's measured 65.5 % whitespace (30,586 µm² drawn against a 15,949 µm²
device-band term). If it lands it will move these figures again, and under
Decision 3 it will *not* on its own be grounds for a downward re-amendment —
it will be grounds for another measured-table refresh, which is now a smaller
and cheaper act than it was before this record separated the two.

## Alternatives considered

- **Amend the row down to ≤ 0.25 mm², preserving DR-016's stated overhead
  tolerance.** The most serious alternative, and the one that follows most
  literally from DR-016 Decision 4. 0.25 mm² holds the measured 225,384 µm² with
  a top-level overhead up to **×1.386** — within a few per cent of the ×1.372
  DR-016 itself ratified — so it preserves that record's *stated* margin
  semantics almost exactly. Rejected on the sensitivity table in Decision 1:
  ×1.386 is 11 % above a ROM multiplier that **nobody has ever checked**, on a
  top level that does not exist. A ≤ 0.25 mm² row would be falsified by the
  first measurement of `pll_top` coming in at ×1.4 — a wholly unremarkable
  number for a four-domain mixed-signal block with guard rings and supply
  trunks — with zero block growth, and the repair would be an *upward*
  re-amendment of a ratified row, the direction CLAUDE.md most disfavours.
  Ratcheting a ceiling down on evidence about a different term, then having to
  relax it again, is worse than holding.
- **Amend to exactly 0.2254 mm², the measured figure with no margin.** Rejected
  for the identical reason DR-016 rejected 0.2733 mm²: the figure contains the
  unmeasured ×1.25, so the row would be falsified by the first top-level
  measurement at ×1.26. That reasoning was correct then and none of its inputs
  has changed.
- **Amend to ≈0.21 mm² (the 0.1702 mm² zero-routing floor plus a margin).**
  Rejected as CLAUDE.md-forbidden: it sets a ratified row on an *estimate*, and
  this repository has now measured that estimate class delivering 20 % – 80 % of
  its sizing on the five occasions it has been built (§5.8 66 %, §5.10 42 %,
  §5.12 20 %, §5.13 74 %, §5.14 80 % for the glue band read as one lever). The
  design would sit outside its own spec on the day the record merged.
- **Hold the row and leave the spec's table alone too, deferring to
  `PLL-FLOORPLAN.md` §5.13/§5.14 and `area-audit.md` as "the current
  measurement".** The status quo, and it is not tenable: `spec/pll.md` is the
  ratified document and `manifests/integrator.json` is what a consumer machine
  reads. Both publish per-block figures 17.5 % above the committed geometry. A
  spec whose own repository knows the number is wrong is worse than a weaker
  spec that is true — DR-016's own words, applied to its own table.
- **Restate the row as a per-block allocation table.** Still attractive, still
  premature, and still rejected on DR-016's reasoning: it changes the *shape* of
  a ratified row and needs a floorplan the block does not have (#17). Noted
  again so the option stays visible.
- **Wait for the `lock_detector` lever before writing anything.** Rejected: the
  lever is unnamed and unsized, the spec's table is wrong *today*, and blocking
  a correction on an unscheduled improvement is how the lag reached two levers
  and then three in the first place.

## Consequences

- **`spec/pll.md`'s Area section and summary-table row 15 carry the refreshed
  measured table** — sum 0.1803 mm², total 0.2254 mm², 75.1 % of the row,
  1.50× the draft target — and both cite this record alongside DR-016. The row
  itself, ≤ 0.30 mm², is byte-identical to what DR-016 ratified.
- **The block meets its own area row with more room than before**, and that
  sentence carries the same misreading risk DR-016 flagged: it does not mean
  the area problem is solved. The draft 0.15 mm² target is still missed by
  1.50×, still on a measurement, and still on a bound (0.1702 mm², 1.13×) that
  assumes every Metal2 track routes for free.
- **`manifests/integrator.json` is re-synced** to the same figures. It was one
  lever stale before this record (it published `pfd_cp` at 26,406 µm² and a
  1.51× draft ratio, both pre-#473) and would have contradicted the refreshed
  spec table if left; it is the machine-readable copy a consumer reads, so the
  two must not disagree.
- **`PLL-FLOORPLAN.md` §5's live fail-loud restatement is refreshed to
  Decision 4's numbers**, and a new §5.15 records the refresh. §5.13's and
  §5.14's "the spec's measured table lags" caveats are **discharged** — each was
  written as "until #476 lands", and this is #476 landing. Per that record's
  append-only convention neither section is rewritten; each gains a pointer to
  §5.15.
- **Nothing in `layout/` changes** — no geometry, no generator, no committed
  GDS, no DRC or LVS verdict, and neither area constant in `skeleton.py`. Every
  block's signoff status is exactly what it was before this record, and
  `layout/evidence/area-audit/area-audit.md` was already current: this record's
  table is that file, not a re-statement of it.
- **`docs/chipalooza/challenge-5-proposal.md` needs no change**: #478 already
  refreshed it to these figures. That it was *ahead* of the spec is itself the
  defect this record closes.
- **The downward-re-amendment path is now narrower, deliberately.** Anyone who
  wants a lower row has two routes and both are measurements, not layout
  levers: assemble `pll_top` (#17) or draw the loop filter. A reduction pass
  that takes the block sum below 120,000 µm² would reach the draft target and
  supersede DR-016 Decision 3 outright — `layout/tests/test_area_audit.py`
  fails the build if that ever silently becomes true, which is the mechanism
  that makes this record's own conclusion falsifiable rather than asserted.
- **Two `sim/` artifacts still quote the draft 0.15 mm² budget and are still
  deliberately not rewritten** — `sim/loop-dynamics/testbench/analyze.py`'s
  `AREA_BUDGET` constant and the records it has produced, plus
  `sim/CHARACTERIZATION.md`. `sim/` is append-only evidence (#5); DR-016's
  guidance is unchanged by this record.
