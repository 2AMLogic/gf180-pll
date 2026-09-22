# DR-016: The area row is amended from ≤ 0.15 mm² to ≤ 0.30 mm², on the measured block sum rather than on a projected floor

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-010,
  DR-011, DR-013, DR-014 and DR-015 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge. This record differs from those in
  one respect that deserves the operator's attention explicitly: it is the
  first record in this repository that **amends a ratified `spec/pll.md` row to
  a weaker number**, so the bar it has to clear is not "is the evidence good"
  but "is the original target reachable at all". §Decision states the answer as
  a measurement, not as a judgement call.
- **Date**: 2026-09-22
- **Decided by**: Builder agent, issue #456 (under #442)

## Context

`spec/pll.md`'s [Area](../pll.md#area) row has read **≤ 0.15 mm² for the whole
block** since the draft, inherited from DR-001's opening target list where it
appears as one line — "Area < 0.15 mm² — the binding constraint on the loop
filter" — with no derivation behind it. DR-007's spec review said so in as many
words and raised it as **Amendment A3**: the row is "the one `budget` row in the
table with no rationale behind the number at all, not even a disposition-only
hand calc", because 78.6 % of it (VCO, PFD/CP, divider, lock detector, routing,
decap) had "**no estimate of any kind**". Only the loop filter's 21.4 % was ever
measured, from DR-006's device data.

That 78.6 % is now drawn. Four transistor-level blocks are committed, DRC-clean
on the foundry deck and LVS-matched against their own ratified schematics, and
their areas are read from the committed GDS bounding boxes by a command rather
than maintained by hand:

```
$ python3 layout/run_pv.py area
```

Issue #442 audited the result and sized every remaining area lever; issues #454
and #455 then executed the two largest of them. This record is the end state
#442's fourth acceptance criterion named and that `layout/evidence/area-audit/
PROOF.md` § "What this record does *not* conclude" deliberately refused to write
on an estimate: **the levers are spent, the total is a measurement, and the
target does not survive it.**

### The measurement

Re-derived from committed geometry at `origin/main` @ `62ceb087` (2026-09-22),
not from any estimate. Per-block figures are the committed GDS bounding box —
`layout/evidence/area-audit/area-audit.md`, the committed output of the command
above:

| Block | Footprint | As-drawn | Basis |
|---|---|---|---|
| Loop filter (R + C1 + C2) | — | 36,936 µm² | DR-006 / `PLL-FLOORPLAN.md` §3 — a device-data **calculation**; no loop-filter layout exists |
| `vco_block` | 172.52 × 184.48 µm | 31,826 µm² | committed GDS |
| `pfd_cp` | 344.98 × 77.30 µm | 26,665 µm² | committed GDS (folded at #455) |
| `divider_chain` | 1317.66 × 70.29 µm | 92,618 µm² | committed GDS (macro band packed at #454) |
| `lock_detector` | 294.80 × 103.75 µm | 30,586 µm² | committed GDS (DR-014 trim network drawn at #449) |
| **Sum** | | **218,631 µm² (0.2186 mm²)** | |
| **After `PLL-FLOORPLAN.md` §5's ×1.25 top-level overhead** | | **273,289 µm² (0.2733 mm²)** | **1.82× the 0.15 mm² target** |

This is a **sum of block extents, not a placed-and-routed top level** — no
assembled `pll_top` GDS exists (#17), so the ×1.25 factor is the one term in
that product that is still an estimate. It matters below.

### Why this is the floor, and not merely the current number

Three bounds, each derived from the same measured audit, each tighter than the
last. None of them reaches 0.15 mm².

**1. Every remaining named lever at its geometric ceiling: 1.20×.** The three
unexecuted levers are all Metal2-track-band levers (#458 on `divider_chain`,
#469 inside `pfd_cp`, and the still-unnamed one on `lock_detector`). Their
common ceiling is the one #442 defined: a block cannot be shorter than
`max(its own tracks packed solid at 0.75 µm, its drawn device bands)`, and its
width is what it is.

| Block | Packed-track floor | Device band | Ceiling height | Ceiling area |
|---|---|---|---|---|
| `vco_block` | 34.50 µm | **183.48 µm** | 183.48 µm | 31,654 µm² |
| `pfd_cp` | 42.75 µm | **49.05 µm** | 49.05 µm | 16,921 µm² |
| `divider_chain` | **32.25 µm** | 26.32 µm | 32.25 µm | 42,495 µm² |
| `lock_detector` | 36.00 µm | **54.10 µm** | 54.10 µm | 15,949 µm² |
| Loop filter | — | — | no lever | 36,936 µm² |
| **Sum** | | | | **143,955 µm²** |
| **After ×1.25** | | | | **179,944 µm² (0.1799 mm²) = 1.20×** |

**2. Every Metal2 track routed at zero area cost: 1.13×.** Strike the routing
term entirely — every net hidden over a device row, no band anywhere — and what
is left is each block's own drawn device bands, which is `width × device band`:
31,654 + 16,921 + 34,681 + 15,949 = 99,205 µm², plus the loop filter's 36,936 =
**136,141 µm²**, or **170,176 µm² (0.1702 mm²) after ×1.25 — 1.13× the target.**
This bound is fold-invariant: folding a row halves its width and doubles its
device-band height, leaving `width × device band` unchanged, so no rearrangement
of these blocks escapes it. Note how little separates bounds 1 and 2 — the whole
difference is `divider_chain`'s 7,814 µm², 2.6 % of the amended row: for the
other three blocks the packed-track floor is already *below* the device band, so
their routing is already free in the limit.

**3. Two blocks alone are 57.2 % of the pre-overhead budget, and neither is a
layout problem.** Against the ×1.25 factor, 0.15 mm² allows 120,000 µm² of
summed block footprint. Two terms consume 68,590 µm² of it — 57.2 % — and no
layout lever touches either:

- **Loop filter, 36,936 µm².** Set by DR-006's C1/C2 *capacitance* at the
  measured 3.988 fF/µm² of `cap_nmos_03v3_b`. C1 alone is 30,276 µm² of drawn
  device for 107.1 … 133 pF over the passive corner bundles. Reducing it is a
  **loop-dynamics** change — it moves [Loop bandwidth](../pll.md#loop-bandwidth)
  and [Phase margin](../pll.md#phase-margin), both ratified and both measured —
  not a layout change. Nothing in `layout/` can touch it; it has no layout.
- **`vco_block`, 31,654 µm² at its own ceiling (31,826 as drawn, −0.5 %).** Its
  height *is* its device band: 183.48 µm of the block's 184.48 µm, leaving a
  1.00 µm no-device band. There is no track band to pack. Its 60.8 % whitespace
  is the guard ring and well/substrate-tap spacing `PLL-FLOORPLAN.md` §1 sizes
  against `DF.13_MV`/`DF.14_MV`'s 15 µm tap pitch — a foundry-deck rule, checked
  live in `layout/evidence/inv-tb-proof/PROOF.md`. It also has the **highest**
  drawn-diffusion share of any block (13.78 % `comp`), i.e. it is the *densest*
  block here, not the emptiest.

That leaves 51,410 µm² for `pfd_cp` + `divider_chain` + `lock_detector`, whose
combined ceiling (bound 1) is 75,365 µm² and whose combined device bands alone
(bound 2) are 67,551 µm². **1.47× and 1.31× short respectively, before a single
wire is drawn.**

### And the ceilings above run optimistic — measured twice, not assumed

Every bound in this section is a *ceiling*, and this repository now has two
measured data points on how ceilings of this exact class behave when someone
builds them:

- **#454** (`divider_chain` macro track band) delivered 39,530 µm² against
  #442's 60,006 µm² sizing — **65.9 %**. `PLL-FLOORPLAN.md` §5.8 records why:
  the track census is flat over a hierarchy, and packing only works within one
  level.
- **#455** (`pfd_cp` fold + track band) took the block 35,281 → 26,665 µm²,
  i.e. **8,616 µm² of the 20,429 µm² its 14,852 µm² ceiling implied — 42 %**,
  and §5.10 measured the shortfall to be in the
  *ceiling*, not the execution: only 4 of the 57 tracks counted belong to
  `pfd_cp`, and the fold raised the block's own device-band floor above the
  packed-track floor its ceiling was measured against. Re-deriving post-fold
  gives 16,921 µm², −52.0 % rather than −58 %.

So the amendment below is deliberately **not** set at bound 1 or bound 2. Both
are estimates of the same kind that have now been measured optimistic twice,
and setting a ratified row to an unexecuted projection would be the identical
mistake — with the extra hazard that the row would then be unmeetable by the
design that exists.

### One correction to the record this replaces

`PLL-FLOORPLAN.md` §5.9's 185,263 µm² projection (1.54×) and §5.10's 197,076 µm²
(1.64×) both carry **`divider_chain`'s pre-#454 ceiling**, 72,142 µm², computed
on the 73-track / 100.29 µm-tall block that #454 has since replaced with a
43-track / 70.29 µm one. §5.9 reached its figure as `162,145 − 7,468 + 30,586`
— #442's whole-chip ceiling sum with `lock_detector`'s row swapped — which also
subtracts that block's *as-drawn* 7,468 µm² where the sum contained its 6,562 µm²
ceiling, a 906 µm² double-count. Re-derived from the current audit, the correct
figure is the 143,955 µm² / **1.20×** of bound 1: the projected floor is
**better** than the record has been carrying, not worse, and it is still over.
This is stated because the direction is inconvenient for this record's own
conclusion and suppressing it would be the same hand-maintenance failure the
audit command exists to end.

## Decision

**1. `spec/pll.md`'s Area row is amended from ≤ 0.15 mm² to ≤ 0.30 mm² for the
whole block.** The row's status changes from `budget` to **measured (blocks) /
budget (top-level overhead)**.

**2. The amended number is the measured total, plus margin sized to the one
factor in it that is not measured.** 0.30 mm² is 273,289 µm² (the measurement
above) carrying the ×1.25 top-level overhead up to **×1.372** before the row
fails. That is the margin's entire meaning: `PLL-FLOORPLAN.md` §5's ×1.25 is a
ROM multiplier and no assembled `pll_top` exists to measure it against (#17).
Equivalently, the row allows 240,000 µm² of summed block footprint against the
218,631 µm² drawn today — **8.9 % margin on the measured sum**. The margin is
*not* an allowance for block growth.

**3. `0.15 mm² is not reachable for this design as specified` is now a measured
statement, and is recorded as such.** Not "the levers have not been executed
yet" — every measured bound above, including one that assumes all Metal2
routing is free, exceeds it. Reaching 0.15 mm² requires changing something this
specification ratifies elsewhere: the loop-filter capacitance (DR-006, and with
it [Loop bandwidth](../pll.md#loop-bandwidth) / [Phase margin](../pll.md#phase-margin)),
or the VCO isolation strategy (`PLL-FLOORPLAN.md` §1, which is sized to foundry
DRC rules), or the device placement inside the three digital blocks — for which
no lever has ever been measured, and whose one *measured* density lever (#442's
shared-diffusion stacking) was **falsified at 0.10 % of the gap**.

**4. The amendment is a ceiling on the design as built, not a licence to stop
reducing.** Three levers remain open and unexecuted — **#458**
(`divider_chain`'s residual band-over-cells, the 7,814 µm² between bounds 1 and
2), **#469** (`cp_output_stage`'s glue bus and `cp_dumpbuf`'s band inside
`pfd_cp`, 9,744 µm² / 36.5 % of that block), and an **unnamed** lever against
`lock_detector`'s 65.5 % whitespace. Each of those landing is grounds for a
*downward* re-amendment of this row by a successor record. None of them was used
to justify the number chosen here.

**5. `PLL-FLOORPLAN.md` §5's fail-loud clause now fires against 0.30 mm², not
0.15 mm².** The clause is what surfaced this overrun in the first place (§5.1);
leaving it asserting a superseded target would retire the mechanism at the
moment it worked.

## Alternatives considered

- **Leave the row at ≤ 0.15 mm² and record the overrun in `layout/` only.** The
  status quo through §5.1–§5.10, and defensible while the floor was a
  projection. It is not defensible now: the row would be permanently unmeetable
  by the design this repository is actually building, and — the part that is
  not merely cosmetic — `manifests/integrator.json`, the machine-readable copy
  any consumer reads, would keep publishing a budget the block misses by 1.82×.
  A spec whose own repository knows the number is wrong is worse than a weaker
  spec that is true.
- **Amend to ≈0.18 mm² (bound 1, every remaining lever at its ceiling).** This
  is exactly the move CLAUDE.md forbids — relaxing a ratified row onto an
  *estimate* — and this repository has now measured that estimate class
  delivering 42 % and 65.9 % of its sizing on the only two occasions it has been
  built. The design would sit outside its own spec on the day the record merged.
- **Amend to ≈0.17 mm² (bound 2, all routing free).** Worse than the above for
  the same reason, plus it is a bound nothing can reach by construction.
- **Amend to exactly 0.2733 mm², the measured figure with no margin.** Honest,
  and rejected for one specific reason: 0.2733 contains the unmeasured ×1.25
  overhead factor. Ratifying it would mean the row is falsified by the *first*
  measurement of top-level overhead if it comes in at ×1.26 — a number nobody
  has claimed, about a top level nobody has assembled. The margin here buys
  exactly that uncertainty and is stated in those terms (×1.372), not as
  headroom.
- **Re-open DR-006 and shrink C1 to fit 0.15 mm².** The loop filter is the
  single largest term, so this is the lever that would actually move the number
  — and it is a change to [Loop bandwidth](../pll.md#loop-bandwidth) and
  [Phase margin](../pll.md#phase-margin), both ratified and both *measured*
  (f_c 26–430 kHz, PM ≥ 45° with the tightest cell at 47.4°). Trading measured,
  met loop dynamics for an area number that was never derived from anything is
  the wrong direction, and it is not this record's decision to make. It is
  named here so the option is visible rather than quietly unavailable.
- **Restate the row as a per-block allocation table instead of one number.**
  Attractive — it would make the loop filter's and VCO's irreducibility
  structural rather than narrative — but it changes the *shape* of a ratified
  row, not just its value, and it would need a floorplan the block does not have
  (#17). Left to a successor record if the top-level assembly makes it useful.

## Consequences

- **`spec/pll.md` Area row and summary-table row 15 both carry ≤ 0.30 mm²**,
  citing this record, with the measured per-block table replacing the
  "unallocated / **not estimated** — owed to #17" line and the stale "`layout/`
  is empty, nothing has been through DRC/LVS" preamble. Four of the five rows
  are now measured off committed GDS; the fifth (loop filter) is DR-006's
  calculation and says so.
- **The block now meets its own area row**, at 0.2733 mm² against 0.30 mm² — and
  that sentence is the one most likely to be misread. It does not mean the area
  problem is solved. It means the specification now states a number the design
  can be held to, and the 1.82× overrun against the original target is recorded
  permanently here and in `PLL-FLOORPLAN.md` §5.11 rather than living as an
  indefinite "still over" in a layout record.
- **`manifests/integrator.json` publishes 0.30 mm²** as `area.budget_mm2` with
  this record as its source, and its per-block figures are re-synced to the
  current audit (`pfd_cp` was still at its pre-#455 35,281 µm², and the sum and
  ratio with it).
- **`docs/chipalooza/challenge-5-proposal.md` states the final verdict** in its
  Area row and "Known gaps" item 8 — a document written to be read verbatim by
  an outside reader, where "over budget, amendment pending" and "over budget,
  amended on this evidence" are materially different claims.
- **Three reduction issues stay open and are now the *only* route to a lower
  row**: #458, #469, and an unnamed `lock_detector` lever. A successor record
  amending this row downward needs the same standard this one used — measured,
  from committed geometry, after the lever is built and DRC/LVS-clean.
- **Two `sim/` artifacts keep quoting the 0.15 mm² budget and are deliberately
  not rewritten**: `sim/loop-dynamics/testbench/analyze.py`'s `AREA_BUDGET`
  constant and the records it has already produced (C1 = 20.2 % of budget), plus
  `sim/CHARACTERIZATION.md`'s summary of them. `sim/` is append-only evidence
  (#5) — a record states what was true when it was taken. Anyone re-running that
  campaign against this record's number should change the constant in the same
  change that produces the new record, so the record and its budget stay
  consistent with each other. Against 0.30 mm², C1's 30,276 µm² of drawn device
  is **10.1 %** of the row rather than 20.2 %.
- **DR-007 Amendment A3 is discharged, by measurement rather than by the rough
  hand-estimate it asked for.** A3 wanted "at least a rough hand-estimate" for
  the non-loop-filter 78.6 % before ≤ 0.15 mm² was read as more than
  aspirational. That 78.6 % is now four committed, DRC-clean, LVS-matched
  layouts measured by a reproducible command — and the answer is that the
  aspiration was 1.82× off.
- **What this record does not touch**: no geometry, no generator, no committed
  GDS, no DRC or LVS verdict. Every block's signoff status is exactly what it
  was before it. `spec/pll.md`'s ratification carve-outs (rows 9 and 16,
  DR-007 A1) are unchanged — Area is not and has never been one of them, which
  is precisely why amending it needs this record.
