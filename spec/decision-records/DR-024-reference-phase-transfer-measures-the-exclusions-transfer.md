# DR-024: The reference-source-quality exclusion's 20·log₁₀(N) transfer is measured, not asserted — the exclusion stands, now backed by a measurement, and the numeric reference-jitter limit is untouched

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-023 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #509

## Context

`spec/pll.md`'s [Reference input](../pll.md#reference-input) row resolves
reference-source quality as an explicit exclusion rather than a number, and
states the transfer an integrating system must budget against:

> Reference phase noise inside the loop bandwidth transfers to the output
> multiplied by `20·log₁₀(N)` = 12 dB at N = 4 to 36 dB at N = 64, so a system
> integrating this block must budget its reference against that multiplication
> itself.

DR-019 (#499) gave that exclusion an honest ownership statement: converting it
into a **numeric reference-jitter limit** needs this repository's closed-loop
noise methodology, which does not exist (DR-020, #505), and is unowned. What
DR-019 did not reach — because #499's campaign does not touch it — is the
narrower question inside the same paragraph: **had the `20·log₁₀(N)`
multiplication itself ever been measured on this design, or only asserted from
theory?**

It had not. Every closed-loop record committed before this one (`lock-time`,
`output-range`, `supply-sensitivity`, `period-jitter`,
`period-jitter-band-top`, `reference-spur`) drives `REF` from a perfectly
periodic pulse source. `sim/reference-input-contract` (#499, DR-019) is the
closest existing campaign and is explicitly not this measurement: it varies
`REF`'s **waveform shape** at a fixed phase.

`sim/reference-phase-transfer` (#509) is the measurement. It is the first
testbench in this repository to displace the reference edge **in time**.

## The measurement

**Deterministic, not statistical — #509's own recommended first increment.** A
single, known reference phase step `dphi` = 1 ns is applied at `tphase` inside
an otherwise-ideal closed loop, and the loop's own REF-vs-FB static phase error
is read out. A phase step's residual, read many loop time constants later, *is*
the loop's deep-in-band response, which is the regime the sentence above
describes. No noise process is involved at any point, so none of #505's missing
methodology is needed.

**Differential against a paired control run.** This is the load-bearing detail,
and the campaign's first record is the evidence for why it is needed.
`sim/reference-phase-transfer/records/20260925-073001-ed38ff1.md` differenced
phi *after* the step against phi *before* it, within one run — and that
differencing is confounded at this operating point: the loop's static phase
error is still winding at ~1 × 10⁻⁴ fractional frequency error 9.2 µs into the
run (0.12–0.19 ns per microsecond, monotonic at every corner, corroborated by
the +72 ppm the same points measure on `ffb`), so the baseline moves 0.4–1.4 ns
across the 6.4 µs between readings — against a 1 ns step. Subtracting a drifting
baseline from a step response measures their sum.

So each PVT point now runs **two** decks, through the harness's `phases` key:
`ctl` with the step selector `apply` = 0 and `stp` with `apply` = 1, identical
in every other respect — same netlist, same PVT point, same `.ic` release, same
blend gate. The drift is common-mode by construction, and

    d(t) = unwrap( phi_stp(t) − phi_ctl(t) )

is the step response with the drift removed rather than bounded. The record
still reports `drift_ctl`, the drift the control run alone saw, so it states the
size of what the pairing cancelled instead of hiding it.

**The pairing is checked, and its residual is the measurement's own noise
floor.** `pair_resid` = d(`ta`) is read *before* the step, where the two decks
are still the same run, and would be exactly zero if they were bit-identical.
They are not: the stepped deck's private `refb` source transitions 1 ns later,
ngspice takes a breakpoint at every source discontinuity, and the two runs
therefore take slightly different internal timesteps from t = 0 even though
`ref` itself is identical in both until `tphase`. `pair_resid` measures that
solver-noise floor directly, on every point, and the record's dB numbers are
read against it rather than presented as exact.

**The roll-off comes out of the same pair.** `d` is also read 120 ns after the
step — 0.3–1.2 of the 100–400 ns loop time constant `sim/loop-dynamics`
measured at this operating point. There the loop has barely begun to re-track,
so the transfer is near *zero* rather than N: the low-pass shape the same spec
paragraph asserts, measured in the time domain at one frequency above the loop
bandwidth. It is one point, not a swept curve; §Decision 4 says so.

**Operating point and grid.** N = 6, VCO band 6, Icp trim code 0, f_ref =
25 MHz, f_out = 150 MHz — `sim/reference-spur`'s operating point exactly,
reusing that campaign's own `vco-tuning-range`-derived per-corner `vstart`
release table verbatim. The grid is the same justified 5-point PVT subset
`sim/reference-spur` runs (all five MOS bundles, all three temperatures, all
three supplies, not the 45-point cross-product), for the reason stated there:
one point is a whole-PLL closed-loop transient at the mandatory 100 ps internal
-timestep ceiling. Two decks per point makes it ten invocations.

## Decision

**1. The exclusion stands, and is now backed by a measured transfer rather than
by theory alone.** No ratified number moves. The `20·log₁₀(N)` sentence is kept
exactly as written and a paragraph is added beneath it stating that the
multiplication is measured at N = 6 — `sim/reference-phase-transfer`, the
measured in-band transfer against the `20·log₁₀(6)` = 15.563 dB the spec's own
formula gives, the corner spread, and the measured roll-off above the loop
bandwidth. This is the disposition #509's acceptance criteria offer as the
alternative to a numeric limit: "the same exclusion now backed by a measured
transfer rather than by theory alone."

**2. It is NOT converted into a numeric reference-jitter limit, and this record
does not sequence that work.** Measuring that a known phase *step* is
multiplied by a gain needs no noise process. Turning a *statistical* reference
phase-noise spectrum into an output jitter allocation does, and that is exactly
DR-020's recorded gap, owned at #505. `spec/pll.md`'s
[Verification owed](../pll.md#verification-owed) line for the numeric limit
stays **unowned**, unchanged in substance. Conflating the two is the
highest-consequence way to misread this record, which is why the two are
separate rows in that table.

**3. The ideal-reference premise every other record rests on is re-argued, not
re-asserted — and it survives, narrowed.** DR-019 Amendment A1 named the rule
that guards it (`sim/lib/check-ref-drive-claims.sh`, rule 5: a deck that varies
the reference must carry no record) and said what its firing would require:
"the source-quality exclusion of Decision 3 has to be re-argued rather than
re-asserted." This campaign fires it. The re-argument:

- The premise that does work in this specification is **every jitter and spur
  number here is the block's own contribution, measured or derived against an
  ideal reference**.
- `sim/reference-phase-transfer` reports **no jitter number and no spur
  number**. It reports a transfer — a gain, in dB, between a deliberate
  reference displacement and the output. Its own manifest, record and this
  record all say so.
- So the premise holds, for a reason that must now be *stated* rather than
  being true by construction: not "no deck ever varies the reference" (false
  since #499's deck landed), and no longer "no deck that varies it has produced
  evidence" (false since this record), but **"no record that reports a jitter
  or spur number was measured against a varied reference."**

That narrowed claim is what `spec/pll.md`,
`docs/chipalooza/challenge-5-proposal.md` and DR-019 Amendment A2 now make, and
what the CI check now enforces: rule 5 admits a deviating deck's record **only**
through a table in the check naming the decision record that re-argues the
premise, verified to exist, to be more than a stub, and to name the campaign
back. This record is that entry. An environment variable or a dropped file is
deliberately not offered — the point of the rule is that a reviewer sees the
argument.

**4. What this record does not claim.** (a) **One N.** N = 6 only. The mechanism
measured — a type-II loop's DC phase tracking multiplied by an *exact digital*
divide ratio — does not structurally depend on N, and the spec's figure is a
formula in N rather than a per-N table, but this is evidence at N = 6 and the
record says so. Extending it needs a `vstart` table at another (N, band, f_out)
triple. (b) **Two frequency points, not a swept transfer function.** The
settled reading is the near-DC transfer and `tfast` is one point above the loop
bandwidth; a continuous magnitude-vs-frequency curve (and therefore the loop
bandwidth read off *this* measurement rather than cited from
`sim/loop-dynamics`) remains #509's "option 1". (c) **Five of 45 PVT points**,
on `sim/reference-spur`'s stated justification. (d) **MOS-only**: the passive
axes are at typical — less consequential here than elsewhere, because the
loop-filter R/C sets the loop's time *constant* and a long-settled step
residual probes its DC *gain*, but it is a limitation, not an absence of one.
(e) **Schematic-level**, no layout parasitics (#18). (f) **Not evidence about
lock.** The design's own `lock` flag does not assert at four of these five
corners at this release point. The differential does not depend on it — what it
needs is that both decks are the same run up to `tphase` (checked) and that the
loop is tracking at N = 6 through the window (checked by `nmeas`/`fout`/
`dn_lvl`) — but this record must not be cited for a lock verdict. That is
`spec/pll.md` row 16's territory, and #437's.

**5. `docs/chipalooza/challenge-5-proposal.md`'s §5 Reference input row is
re-derived from the record, and its verdict does not move.** The row's
electrical-contract lines (levels, edge rate, duty) are **still UNMET** — this
campaign measures none of them; that is #499's. What changes is the sentence
that said converting the exclusion into a numeric limit "needs a
reference-perturbation bench that does not exist": a reference-perturbation
bench now exists and has measured the transfer, while the *noise* bench the
numeric limit needs still does not. Both halves are now said.

**6. Nothing in `design/` changes**, no schematic, no netlist, and no
pre-existing `sim/` record is edited or reinterpreted.

## Alternatives considered

- **Take the numeric reference-jitter limit instead.** Rejected on DR-020's
  already-ratified grounds: this toolchain has no transient device-noise
  analysis and no validated noise-referral path for a free-running oscillator,
  so the reference phase-noise spectrum an allocation needs would have to be
  invented. A deterministic step measures the transfer's magnitude; it is not
  the same deliverable and this record does not pretend otherwise.
- **Report the transfer from the single-run differencing record and stop.**
  Rejected — that is the record whose own guard says it cannot be read that
  way. `settle_resid` failed at all five corners and `tracking_ratio` at four,
  because the loop's winding baseline is comparable to the injected step. The
  right response to a guard firing is a better measurement, not a looser guard.
  Both records are committed; the first is the evidence for the second's
  method.
- **Widen the `tracking_ratio` band until the first record passed.** Rejected
  explicitly, and named here because it was the cheap option: CLAUDE.md forbids
  relaxing a criterion to make a result pass, and the criterion was not the
  problem — the differencing was.
- **Measure the output's absolute phase excursion directly rather than the
  loop's REF-vs-FB error.** Rejected on resolution: at the top of the ratified
  N = 4–64 range the expected output excursion N·dphi exceeds a whole output
  cycle long before dphi is large enough to resolve against 200 ps edges, so
  the reading wraps. FB's excursion is at most dphi itself, always well inside
  one reference period, and the divider carries the same fractional tracking
  onto the output structurally.
- **Wait for the loop to fully settle instead of pairing.** Rejected on cost
  and honesty: at the measured 0.12–0.19 ns/µs winding rate, getting the
  baseline below the step's residual would need tens of microseconds of extra
  closed-loop transient per point at a 100 ps internal-timestep ceiling — and
  it would still be a *bound* on a confound rather than its removal. The
  control run removes it exactly, for one extra deck per point.

## Consequences

- **`spec/pll.md` changes in three places, and no ratified requirement moves**:
  the Reference input section's source-quality paragraph gains a measured-transfer
  paragraph; the [Verification owed](../pll.md#verification-owed) table's
  transfer-figure row becomes discharged-at-N-6-with-named-residuals rather than
  owed-in-full; the numeric-limit row stays **unowned** and is reworded only
  enough to point at the row above rather than re-describe it.
- **`sim/README.md`, `sim/CHARACTERIZATION.md` and
  `docs/chipalooza/challenge-5-proposal.md`** each carry the campaign and its
  result, and the two evidence-count lines CI grades are updated.
- **`sim/lib/check-ref-drive-claims.sh` gained two capabilities, both of which
  this campaign forced.** Its enumerator could not *see* a reference that is
  not a `pulse()` — the one deck in this repository whose purpose is to drive
  `REF` differently — which is DR-019 Amendment A1's own lesson recurring one
  layer down, in the pattern rather than the glob. And rule 5 needed a way
  through that is an argument rather than a switch. Both are in Amendment A2.
- **Three findings this issue produced that are not about the spec at all**,
  each fixed in the same change and each reachable by every batch-executed
  campaign in this repository, not only this one:
  1. **The batch backend never told the launch script which identity to submit
     as**, so it fell back to the execution layer's *admin* provisioning
     profile, which a dispatch host has no credential for. The failure surfaced
     as an empty subnet list — `only 0 subnet/AZ(s) resolved, floor is 3` —
     which reads as "the fleet is not provisioned" when the fleet was fine.
     This is what #499's and #503's campaigns are blocked on, and it is not a
     credential gap: **the fleet ran this campaign's grid three times once the
     resolved profile was passed through.** Those two campaigns should be
     re-attempted.
  2. **The batch backend collected every job's outputs into the run's *shared*
     work directory**, where every job's files have identical names, so
     concurrent points overwrote each other and the caller read back whichever
     landed last. Three of ten decks in one grid came back carrying a fourth
     deck's log byte-for-byte. It failed loudly here only because a `phases`
     manifest's two decks expect different measurement names; on a single-deck
     manifest the wrong point's numbers would have parsed cleanly and been
     recorded against the wrong corner. **No pre-existing record is affected,
     and that is checked rather than assumed**: this campaign's three records
     are the only batch-executed records in the tree
     (`grep -l 'execution backend' sim/*/records/*.md`), and every committed
     corner log of all three is distinct except the three the defect produced
     (`md5sum sim/*/corners/*/*.log`). That check is the one to repeat on any
     future batch grid taken before the fix reaches it.
  3. **The execution layer's job image runs a different ngspice than the
     submitting host**, and provenance printed the submitter's. This
     repository treats the ngspice version as part of a run's identity
     (`sim/README.md`'s binary pin, #259/#153), so a record naming ngspice-46
     for points that printed `ngspice-42 done` in their own logs is a false
     provenance claim. The executing version is now read out of each deck's own
     output and disclosed per record. **Every number in this campaign's records
     was produced by the execution layer's pinned ngspice, not by the
     ngspice-46 the rest of `sim/` was measured on**, and is therefore not
     interchangeable point-for-point with those records; the records say so on
     their own faces. Aligning the job image with the repository's pin is a
     worker-provisioning matter, not a design one.
- **Nothing in `design/` changes.**
