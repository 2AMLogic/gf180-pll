# DR-024: the Reference spur row's owed verification is re-pointed off closed issue #145, restated at the binding 200 MHz, and given the relation it has to DR-018's derived stack

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-023 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #510
- **Relates to**: **DR-018** (charge-pump term-1 mismatch budget, derived from
  this very spur line — this record does not revise it, and Decision 4 below
  states how a mismatch-off measurement must be read against it).
  **DR-003 Decision 4** (the band-selection rule) and **Decision 5** (the
  0.9–2.7 V control window) — applied here, revised nowhere.
  **DR-001 Decision 2** (band select is a static input) — the reason Decision 5
  below routes a finding out to #534 rather than resolving it.
  **DR-019** and **DR-023**, which repaired the identical defect on the
  [Reference input](../pll.md#reference-input) and
  [Period jitter](../pll.md#period-jitter) rows; this record follows their
  form deliberately, so the three read alike.
- **Evidence**: `sim/reference-spur/records/20260816-132150-5f405e7.md` (the
  only closed-loop spur measurement this repository has — 5 corners at
  150 MHz); `sim/vco-tuning-range/corners/20260804-162735-72883fb/raw_measures.csv`
  (the committed f(Vctrl) table every band/release-voltage figure below is read
  out of); `spec/pll.md#reference-spur`'s own derivation table. No new
  simulation: every number here is arithmetic on committed data, re-derivable
  by `python3 sim/reference-spur-band-top/testbench/band_and_vstart_from_vco_record.py`
  and pinned in `sim/tests/test_reference_spur_band_top_grid.py`.

## Context

`spec/pll.md`'s [Verification owed](../pll.md#verification-owed) table names
**#145** against the [Reference spur](../pll.md#reference-spur) row, for "the
remaining 40 PVT points, and a direct measurement at the binding
f_out = 200 MHz". **#145 is closed.** It delivered what it was opened for — the
first closed-loop spur measurement in `sim/`, 5 spanning corners at 150 MHz —
and nothing since has picked up the rest. A ratified table pointing an open
obligation at a closed issue reads to an outside reader as *discharged*, which
is the opposite of true. That is the same defect DR-019 and DR-023 repaired on
two other rows, and fixing it is an edit to a ratified table, hence this record.

**The gap tightened while it sat unowned.** DR-018 priced charge-pump term-1
UP/DN current mismatch at its statistical 3σ instead of its systematic value
and refreshed the statistical-residual row to the corner-combined campaign; the
Reference spur section's own derivation now lands the 200 MHz spur at
**−56.6 dBc** against the ratified **−55 dBc** — 1.6 dB, where the older
−61 dBc row implied ~6 dB. Meanwhile the one measurement, scaled to 200 MHz,
already sits **outside** the line at the two coldest corners (−54.5 dBc at
`sf`/−40 °C/2.97 V, −54.9 dBc at `ff`/−40 °C/3.63 V). The row most likely to
fail on silicon was the one whose remaining verification had nobody holding it.

**And the owed measurement could not have been produced by extending the
existing grid.** `sim/reference-spur` holds the VCO band code fixed at 6 in its
manifest `params`, which is correct at 150 MHz — one static code reaches
150 MHz at all 45 mandated corners. At 200 MHz no single code does. Read out of
the committed VCO record inside DR-003 Decision 5's 0.9–2.7 V window, the
band-selection rule selects **band 6 at 34 of the 45 points and band 7 at the
other 11**; band 6 misses 11 points from below (its ceiling falls to 166.3 MHz
at `ff`/−40 °C/3.63 V) and band 7 misses 4 from above (its floor rises to
225.4 MHz at `ss`/125 °C/2.97 V). Their union covers all 45. So the binding-
point measurement needs a per-point static configuration — a different
manifest shape, not a different parameter.

### What now exists, and what does not

Issue #510 lands the campaign, not the measurement.
`sim/reference-spur-band-top/` carries a complete, self-checking manifest, deck
and per-corner operating-point derivation: the full mandated 45-point PVT
matrix at f_ref = 25 MHz, **N = 8**, f_out = **200 MHz**, Icp trim code 0 (what
the [Icp trim-code rule](../pll.md#icp-trim-code-rule) requires at 25 MHz), each
point in the band the ratified rule selects for it and released at the control
voltage the committed VCO record puts 200 MHz at in *that* band. Its reduction
is not a copy: `derive.py` there loads
`sim/reference-spur/testbench/derive.py`, so the two campaigns' numbers come
out of one file and `sim/tests/test_reference_spur_derive.py`'s known-answer
coverage applies to both. Its band/release-voltage generator likewise loads
`sim/period-jitter-band-top`'s, which loads `sim/reference-spur`'s
interpolation — three campaigns, one reading of what the committed VCO record
says a corner does.

**It carries no record.** Zero of the 45 declared points are measured. A
45-point closed-loop transient grid at this repository's 100 ps internal-
timestep ceiling is several CPU-days, which this repository's operating rules
route to the batch fleet rather than to a shared dispatch host — and that
launch path is blocked outside this repository, on the same fleet-credential
fault DR-019 §Consequences documents and #499 tracks (re-confirmed 2026-09-25
with no harness involved: `only 0 subnet/AZ(s) resolved, floor is 3`). A
single-corner bring-up probe (`ff`/−40 °C/3.63 V, band 7, `--no-write`) is what
establishes the deck composes, converges and measures at this operating point.
**It is a bring-up probe, not evidence**: it mints no record, it is one corner
of forty-five, and no number from it appears in `spec/pll.md` or in
`docs/chipalooza/`.

## Decision

**1. The Reference spur row's Verification-owed owner is re-pointed.** The
`#145` in that row is replaced by **#533** (`reference-spur-band-top`, the
campaign run), with the campaign directory named beside it so a reader can tell
an unowned gap from a queued one. **No requirement in the row moves.**

**2. The −55 dBc target does not move, and neither does the row's status.**
Reference spur stays **measured** (5 spanning corners, 150 MHz) and **budget**
everywhere else. A campaign directory is not evidence and this record does not
let it be cited as any; the row is upgraded by a record, not by a manifest.

**3. What is owed is restated: the mandated 45 points at the binding 200 MHz —
not 40 more points at 150 MHz.** The old wording owed two things that sound
independent and are not: "the remaining 40 PVT points" (at 150 MHz) and "a
direct measurement at the binding f_out = 200 MHz". Completing the first would
produce 40 more numbers that still have to be multiplied by +2.50 dB before
they can be read against the ratified line — i.e. 40 more extrapolations at the
point where the claim binds. The 200 MHz grid is strictly stronger evidence for
this row at every corner, and it is what is now owed. Two things this does
**not** do: it does not supersede
`sim/reference-spur/records/20260816-132150-5f405e7.md`, which remains the
evidence for its own 150 MHz operating point and the only measured spur this
repository has; and it does not retire `sim/reference-spur` as a campaign — a
150 MHz point is still the right thing to run when the question is what the
spur does *below* the binding frequency.

**4. A mismatch-off measurement and DR-018's −56.6 dBc are different
quantities, and the row now says so in the same place it states both.** Both
closed-loop spur campaigns run with device mismatch **off**: they measure the
systematic, corner-driven spur. DR-018's stack adds three charges linearly,
each at its own worst corner — 3.68 fC systematic asymmetry + 4.25 fC
corner-combined statistical residual + 3.73 fC of term-1 current mismatch at
its ratified ±20 % budget = 11.66 fC → −56.6 dBc at 200 MHz. The row comparable
with a mismatch-off measurement is the **first term alone**: 3.68 fC through
the identical chain is **−66.6 dBc** at 200 MHz. `spec/pll.md` now carries that
systematic-only figure explicitly, because without it a reader has a measured
number and a derived number that look comparable and are not. Three
consequences follow and are stated rather than left to inference:

- The committed 150 MHz record, scaled, already exceeds the systematic-only
  figure by ~12 dB at the two cold corners (−54.5 and −54.9 dBc against
  −66.6 dBc) while sitting 3.6 dB *below* it at `fs`/125 °C/3.63 V, the
  derivation's own worst corner — with mismatch off in every case. **Whatever
  drives the cold-corner spur is therefore not the charge-asymmetry term the
  derivation is built from.** This record does not name the mechanism; it
  records that the derivation does not predict the measurement's corner
  ordering, which is the strongest argument for measuring at the binding
  frequency rather than extrapolating to it.
- A PASS from the 200 MHz campaign will **not** discharge the statistical half
  of the spur budget, and a FAIL will not by itself impeach DR-018's charge-pump
  mismatch budget. What either does is replace the binding-point number with a
  measured one.
- **The closed-loop statistical spur is unowned**, and this record says so
  rather than implying `sim/mc-cp-mismatch` covers it: that campaign measures
  the charge-pump's mismatch *charge*, not a closed-loop sideband. A
  Monte-Carlo closed-loop spur campaign would be a further measurement on top of
  #533 and nobody holds it today.

**5. The per-corner band configuration is recorded as a property of the claim,
and its per-part consequence is routed rather than resolved.** That the
band-selection rule selects two different codes across the 200 MHz grid is a
condition on how the owed measurement must be configured, and the campaign
encodes it (`--check` refuses a manifest that has drifted from the rule). The
adjacent observation — that projecting that split onto one *static* code leaves
**four of the five MOS bundles with no single code that reaches 200 MHz across
the full ratified temperature × supply box** — bears on the
[Output band](../pll.md#output-band) row, not on this one. It is filed at
**#534** with its per-bundle table. **This record changes nothing about the
Output band row**, makes no recommendation among the dispositions open to it,
and does not make this row's owed measurement conditional on it: each point of
#533 is measured in the band a part targeting 200 MHz *at that point* would be
programmed into, which is the correct configuration to measure whatever #534
concludes.

## Alternatives considered

- **Re-point the row at #503** (`period-jitter-band-top`, the other campaign at
  this binding point). Rejected: it measures a different quantity — the
  period-to-period spacing of the locked output, not the spectral sideband —
  and folding a spur obligation under it would make a row look owned by a
  campaign that will never report a dBc number. The two share the mandated
  matrix and the same per-corner band assignment (a property
  `sim/tests/test_reference_spur_band_top_grid.py` now asserts point-for-point),
  and that is the whole of their relationship.
- **Re-point at #237.** Rejected: #237 is the documentation-grading epic that
  surfaced this. A tracking epic is not an owner, and naming one would repeat,
  in gentler form, the defect this record exists to fix.
- **Leave `#145` and add a footnote that it is closed.** Rejected, on DR-019's
  reasoning: a ratified table is read by people who do not read footnotes, and
  the failure mode being fixed is precisely a reader concluding the obligation
  was discharged.
- **Extend `sim/reference-spur`'s own manifest to 200 MHz** instead of a sibling
  campaign. Rejected on three counts. The manifest-level `checks` that decide
  whether a point is locked (`fout` inside its band, `nmeas` at the configured
  N) are per manifest, not per point, and this operating point has a different
  N and a different output band. The band bits sit in that manifest's `params`,
  which is *correct* at 150 MHz and must not become per-point there. And a
  campaign whose records mixed two output frequencies could not be read
  point-for-point against itself, which is the comparison the whole exercise
  rests on. Same reason `sim/period-jitter-band-top` is a sibling rather than a
  second grid.
- **Complete the 40 remaining 150 MHz points first**, as the old wording asks.
  Rejected — see Decision 3. It is the more expensive half of the work and it
  leaves the binding number an extrapolation.
- **Declare a spanning subset at 200 MHz** — five points, as the 150 MHz record
  ran, with the same "the spur's PVT inputs are characterized over the full
  matrix elsewhere" argument. Rejected twice over. That argument bounds the
  *inputs* to the spur, not the spur: the 5-point grid's own measured spread is
  15.6 dB, its extremes are not the corners the derivation predicts, and nothing
  in the subset explains why. And at 200 MHz a five-point subset would sample
  one band at four points and the other at one, when the 11 band-7 points are
  precisely the cold/high-supply ones the committed record already misses the
  line at once scaled.
- **Widen the −55 dBc line, or re-open DR-018's ±20 % term-1 budget, on the
  strength of the 1.6 dB derived margin.** Rejected, and named here because it
  is the tempting move: DR-018 Decision 1 is explicit that the ratified row does
  not move, and `CLAUDE.md` forbids relaxing a ratified spec to make results
  pass. The derived margin being thin is an argument for measuring, not for
  moving the line.
- **Hold this record until the campaign has a measured record.** Rejected on
  DR-019's reasoning: the attribution defect is live *now*, and every day it is,
  a reader can reasonably conclude the work is done. The defect is independent
  of the measurement and is fixed independently of it.

## Consequences

- **`spec/pll.md` changes in four places and no requirement moves**: the
  Verification-owed row's owner column and owed text (Decisions 1 and 3); the
  Reference spur section's status paragraph, which now names the campaign, its
  state, and the band split it is configured under; the derivation's
  charge-accounting table, which gains the **systematic-only −66.6 dBc** row and
  the sentence saying which number a mismatch-off measurement is comparable with
  (Decision 4); and the summary table's row 7 status cell, which names the
  campaign rather than leaving "budget" unattributed. The −55 dBc target, the
  −61 dBc historical cross-check and every row of DR-018's stack are unchanged.
- **The measurement is still owed, and now has somewhere to be owed from.**
  Zero of 45 points measured. `sim/CHARACTERIZATION.md`'s Reference spur row
  moves from "5 of 45, one frequency" to "a campaign at the binding frequency
  exists, every point of it is owed" — the same state
  `period-jitter-band-top` and `reference-input-contract` are in, and stated in
  the same words so the three read alike.
- **The blocker on those points is compute access, not mechanism or design.**
  The campaign composes, the deck converges, the reduction is unit-tested
  against known answers; what is missing is a fleet launch from a host that can
  resolve subnets (#499, operator-held).
- **One shared reduction changed, and no committed number moves.**
  `sim/reference-spur/testbench/derive.py` derived its binding-point column from
  a hardcoded `F_OUT_MEASURED = 150e6`; it now reads the run's own declared
  operating point (`nratio * fref`). At 25 MHz × 6 that is the identical
  arithmetic — `20·log₁₀(200/150)` = +2.4988 dB, exactly what
  `20260816-132150-5f405e7` carries — so the committed record reproduces
  unchanged, and the same code reports **0.00 dB** for a 200 MHz run, where the
  constant would have silently added 2.5 dB to a number already at the binding
  frequency. The `spur_dbc_at_200mhz` column therefore means "the measurement
  itself" in one campaign and "an extrapolation" in the other, and each table's
  own notes now say which.
- **The bad consequence, stated plainly**: this record improves the
  *bookkeeping* of a gap and adds one derived row; it does not close the gap.
  After it, `spec/pll.md` is honest about an unmeasured binding point instead of
  pointing at a closed issue for it, and that is all. An outside reader of
  `docs/chipalooza/challenge-5-proposal.md` §5 still finds the Reference spur
  row **UNMET**, and should.
- **Nothing in `design/` changes**, no schematic, no netlist, and no `sim/`
  record is added, rewritten or superseded. The append-only tree is untouched.
- **The path to needing a further record is named.** If #533's grid measures a
  spur outside −55 dBc at the binding point, what a new record has to re-derive
  is the *mechanism* — the cold-corner term the charge-asymmetry chain does not
  predict — and the candidate levers are the charge pump's reset-overlap
  behaviour, the loop filter's C2, and the band the rule selects at those
  corners. Widening the −55 dBc line to fit the result is not one of them, and
  neither is re-opening DR-018's mismatch budget, which Decision 4 shows is not
  the term the measurement is even sensitive to.
