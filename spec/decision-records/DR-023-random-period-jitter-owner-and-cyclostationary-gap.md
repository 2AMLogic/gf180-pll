# DR-023: The random period-jitter component's owed verification is re-pointed off closed issue #13 (and its stale successor, #505), and the reason it cannot be measured here is narrowed from "no noise machinery" to a missing cyclostationary bridge

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-019 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #505
- **Relationship to DR-020**: **narrows it; does not contradict it.** While
  this record was in progress, PR #521 independently merged its own
  `spec/decision-records/DR-020-random-period-jitter-is-not-obtainable-on-this-toolchain.md`
  against the same row, taking the DR-020 slot first — this record is
  therefore renumbered per TEMPLATE.md's collision rule. DR-020's Decision 1
  and Decision 3 already reach the same finding this record does (the random
  component is not obtainable on this toolchain, and the row's owner moves off
  closed #13), on the strength of three single-run debug probes run locally
  and **not committed** to `sim/` ("no fleet, no `sim/` record minted …
  reproduced inline here rather than as evidence records", DR-020 §Context).
  This record does not re-litigate that finding; it commits the equivalent
  probes as a reproducible, re-runnable artifact
  (`sim/period-jitter/noise-toolchain-probe/`, four checks against a fourth
  fact — periodic-steady-state availability — DR-020 did not probe), and
  corrects one attribution DR-020 got overtaken on by events at its own
  merge: DR-020 Decision 3 re-points the row at **#505**, the issue that PR
  #521 itself closed on landing — so the ratified table carried a stale
  closed-issue owner from the moment DR-020 merged, the identical defect
  DR-020 exists to repair. **#520**, filed by this record, is the row's owner
  going forward; DR-020 is not rewritten (append-only), and stands as the
  record of the original disposition and its single-run probes.

## Context

`spec/pll.md`'s [Verification owed](../pll.md#verification-owed) table names
**#13** against the [Period jitter](../pll.md#period-jitter) row's random
(noise-driven) component. **#13 closed on 2026-09-08 (`completed`).** A
ratified table pointing a live obligation at a closed issue reads to an outside
reader as *discharged*, which is the opposite of true — the identical defect
#500 found for #12 on the Reference input row, and the identical defect issue
#505 was filed to repair here.

The deterministic half of that row is in good standing and is not at issue:
`sim/period-jitter`'s six records cover all 45 mandated PVT corners at
0.0508–0.2691 % RMS, PASS against the draft target at every one. The random
half has **zero records** and every one of the six says so in its own
Limitations field.

### What the existing records say, and the one clause that turned out to be wrong

Each record attributes the gap to a methodology problem: DR-002 Decision 5
specifies a VCO-dominated **transient-noise** testbench; `.option TRANNOISE=1`
injects nothing on this repository's pinned `ngspice-46`; and turning ngspice's
explicit `trnoise()` PWL source into a credible figure

> "requires first calibrating the injected amplitude against a validated
> noise-PSD measurement of the VCO's dominant noise contributors … which is
> real, separately-scoped methodology development this record does not attempt."

That is nearly right, and the part of it this record had to test is the phrase
**"a validated noise-PSD measurement"** — read plainly, it says the device
noise PSDs are themselves unavailable. They are not.

### Re-derived, not restated

This record does not cite the toolchain claims above; it re-measured all four,
because the whole record turns on them. The decks are committed at
[`sim/period-jitter/noise-toolchain-probe/`](../../sim/period-jitter/noise-toolchain-probe/)
with their captured logs, and `run.sh` there reproduces every number,
self-checking its own units against `sqrt(4kTR·B)` each pass.

| # | Question | Result |
|---|---|---|
| 1 | Does `.option TRANNOISE=1` inject device noise into a `.tran`? | **No.** A 100 k/100 k divider off a DC source is bit-for-bit flat over 10 µs — `vspan` exactly `0.000000e+00`. DR-002 Decision 5's specified method is not merely unconfirmed on this build; it is **unavailable**. |
| 2 | Does the explicit `trnoise()` PWL source work? | **Yes** — `trnoise(1m 1n 0 0)` gives a measured 0.865 mV RMS. It synthesizes a waveform from an amplitude the *deck* supplies and knows nothing about any device. |
| 3 | Does `.noise` give per-device, per-mechanism PSDs for the gf180mcu models? | **Yes — 28 per-device vectors**, including `…m0.id` (channel thermal) and `…m0.1overf` (flicker), plus terminal-resistance noise. |
| 4 | Is a periodic-steady-state analysis available? | **No.** `pss: no such command available in ngspice`. No PSS ⇒ no Pnoise. |

And the quantity that makes 3 and 4 add up to a blocker — the ring stage's own
switching nfet (`nfet_03v3`, L = 0.28 µm, W = 2 µm, exactly as drawn in
`design/netlist/vco.spice`), at 1 MHz, V_ds = 1.65 V:

| V_gs (V) | I_d (A) | channel thermal (V/√Hz) | flicker (V/√Hz) |
|---|---|---|---|
| 0.30 | 1.479e-09 | 1.917e-14 | 7.920e-16 |
| 1.65 | 3.005e-04 | 3.115e-12 | 2.189e-11 |
| 3.30 | 9.598e-04 | 4.084e-12 | 4.946e-11 |

**46.6 dB** of channel-thermal and **95.9 dB** of flicker PSD variation across
the gate range each ring device traverses twice per oscillation. Across the
conducting points alone it is still 7.1 dB and 13.4 dB. (The probe sweeps V_gs
at fixed V_ds, so these are a *lower* bound on the real two-dimensional
trajectory's variation — conservative in the direction this record argues.)

### The gap, located

`.noise` is a small-signal analysis linearized about **one fixed DC operating
point**. The ring's devices are strongly cyclostationary. Producing an
oscillator phase-noise number from stationary per-device PSDs requires
weighting them over the periodic large-signal trajectory — which is what a
PSS/Pnoise pair does, and probe 4 shows this build has neither.

So the honest statement is **not** "this flow has no noise machinery." It is:
*the calibration input exists; nothing in this toolchain carries it over the
oscillation cycle.*

## Decision

**1. The Verification-owed row's owner is re-pointed from #13 to #520.**
`#13 (period-jitter)` in the random-component row is replaced by
**#520 (`period-jitter`, random component)**, which is open, and the row cites
this record for the reason. The owed text is narrowed to say *what* is missing
(the cyclostationary bridge) rather than implying the device noise data is.

**It is deliberately not re-pointed at #505.** #505 is the issue that found
this defect, and the pull request landing this record **closes** #505 — so
naming it would have reproduced, at merge, the precise defect this record
exists to repair. DR-019 rejected the mirror-image substitution for the same
reason ("an empty owner column is a worse look and a better fact"); here an
empty column is not needed, because #520 exists and owns the measurement.
**The rule both records are instances of: an owner column must be verified
against the forge at the moment it is written — and if the writing act itself
will close the candidate, that counts as closed.**

**No requirement in the row moves.** ≤ 1.0 % of the output period, RMS, stands
exactly as ratified. This is an attribution fix and a narrowing of a stated
reason, not a relaxation.

**2. The random component is recorded as NOT MEASURABLE on this toolchain, and
the reason is narrowed to a falsifiable one.** The blocker is not the absence
of device noise models — probe 3 disproves that — and not the absence of an
injected-noise source — probe 2 disproves that. It is the absence of any
periodic-steady-state / cyclostationary-noise path (probe 4) to weight the
former over the oscillation trajectory (probe 3b). This is stated as a
condition a future build or a future pipeline can **falsify**: if `pss`
resolves, or if an ISF pipeline demonstrates convergence, this decision is
overtaken and a new record supersedes it.

**3. The ≤ 1.0 % RMS row stays ratified, and the budget silently allocated to
the random component is made explicit as an UNVERIFIED BUDGET.** The row's own
supply-ripple derivation already spends the target twice over:

> "At 20 mV pp that is **0.50 % RMS** — half the budget, leaving the other half
> for the random/thermal contribution that has not been measured."

That sentence allocates **0.50 % RMS to the random component**. Nothing has
ever measured against it. This record does not change the allocation and does
not weaken the row; it changes the allocation's *status* from an implicit
arithmetic step into a named, unverified budget line that #520 must close.
Concretely, the row's evidentiary state is now:

| Component | Status | Number |
|---|---|---|
| Deterministic, closed-loop (control ripple) | **measured**, 45/45 corners | 0.0508–0.2691 % RMS |
| Supply-ripple sensitivity at the normative 20 mV pp condition | **derived** from a measured 100 mV pp open-loop sensitivity | 0.50 % RMS |
| Random / noise-driven | **budget — unverified, and not measurable on this toolchain** | ≤ 0.50 % RMS *assumed*, owned by #520 |

**The consequence a reader must not miss: the 1.0 % line is not demonstrated.**
Half of it rests on an assumption no simulation in this repository has tested,
and this record's contribution is to say so in the table rather than in an
arithmetic aside. `docs/chipalooza/challenge-5-proposal.md` §5 continues to
mark the random row **UNMET**, and should.

**4. DR-002 Decision 5 is NOT superseded, and its `proposed` status is
unchanged.** Its substance — that period jitter (RMS) is the spec'able quantity
and that any phase-noise or integrated-jitter figure is derived-only — is
untouched by anything here, and remains correct. What changes is the *reason*
its status is still `proposed`: DR-002 anticipated that #13's measurement would
"confirm, refine, or supersede" it, whereas the method it names cannot be
executed on the pinned build at all. That makes Decision 5's own §Consequences
branch (b) — "shows the transient-noise approach cannot substantiate even
period jitter reliably at this node" — **not yet reached**: the approach has
not failed on the physics, it has not been runnable. Superseding a decision on
a tooling absence would destroy a judgement that is still sound; this record
narrows it instead, which is what the append-only rule is for.

## Alternatives considered

- **Re-point the row at #505 (the issue this record discharges).** Rejected —
  the PR landing this record closes #505, so the table would name a closed
  issue again within the same merge. This was the obvious reading of #505's own
  acceptance criterion ("names an open issue — this one, or a successor"), and
  taking the successor branch is what makes the criterion satisfiable rather
  than self-defeating.
- **Leave `#13` in place and add a footnote that it is closed.** Rejected, on
  DR-019's reasoning: a ratified table is read by people who do not read
  footnotes, and the failure mode being repaired is exactly a reader concluding
  the obligation was discharged.
- **Build the ISF pipeline now and produce a number in this PR.** Rejected as
  scope, but *named* rather than waved off, and issue #520 carries the design:
  an `S_id(V_gs, V_ds)` table per ring device class (a `sim/devchar-*`-shaped
  campaign, genuinely tractable — probe 3 is one point of it) plus a per-node
  impulse sensitivity function Γ(x) from charge-injection transients, combined
  by the standard Γ²-weighted sum. The load-bearing risk is Γ: one transient
  per injection phase per node, and its accuracy is weakest exactly at the
  switching edge where it matters most. That is a campaign with a real chance
  of a negative result, which is why it is scoped as its own issue with a
  recorded-negative-result branch, not smuggled into a bookkeeping fix.
- **Calibrate `trnoise()` from a single-bias `.noise` result and publish the
  number.** Rejected, and this is the alternative this record exists to refuse.
  It is *cheap* — probes 2 and 3 are both green, and the two compose in an
  afternoon. It is also the uncalibrated figure the six existing records
  already declined to publish, dressed up: probe 3b shows the generator being
  sampled moves by 46.6 dB (thermal) and 95.9 dB (flicker) across the bias the
  device actually traverses, so *which* single bias point one picks sets the
  answer. A number whose value is chosen by an undocumented modelling choice is
  worse than no number, because it looks like evidence. It stays available to
  #520 as alternative (B) **only** with the bias point declared and the error
  of the stationary approximation bounded.
- **Declare the random component out of scope for v1 and delete the row's owed
  line.** Rejected. It is a real part of the ratified target — the supply-ripple
  derivation in §Decision 3 spends half the budget on it — and removing the
  obligation because it is hard is the relaxation `CLAUDE.md` forbids. The
  obligation stays; only its owner and the precision of its stated reason change.
- **Hold this record until #520 has a measured result.** Rejected. The
  attribution defect is live *now*: every day the ratified table names a closed
  issue, a reader can reasonably conclude the work is done. The defect is
  independent of the measurement and is fixed independently of it.

## Consequences

- **`spec/pll.md` changes in two places and no requirement moves**: the
  Verification-owed row's owner column and owed text, and the
  [Period jitter](../pll.md#period-jitter) section's "Limits of the present
  evidence" paragraph, which gains the explicit budget table of §Decision 3 and
  the narrowed reason. The target, the stretch, the normative 20 mV pp ripple
  condition and every measured number are untouched.
- **The measurement is still owed, and now has somewhere to be owed from.**
  Zero records exist for the random component and this record produces none.
  What it produces is a correctly-addressed obligation and a scoped successor
  (#520) with four named discharge routes, one of which is an honest negative
  result.
- **`sim/period-jitter/noise-toolchain-probe/` is added, and is deliberately
  not a campaign.** It measures the simulator, mints no evidence record, and is
  single-corner on purpose. It exists so this record's four load-bearing claims
  are reproducible. `sim_record_campaigns` keys on `sim/<name>/records/*.md`, so
  it adds no campaign to any count; `sim/README.md`'s and
  `sim/CHARACTERIZATION.md`'s totals are unchanged by it.
- **One prior statement in this repository is narrowed, not contradicted.** The
  six `period-jitter` records' phrase "requires first calibrating the injected
  amplitude against a validated noise-PSD measurement" implies the PSD data is
  missing. It is available (probe 3). The records are **not edited** — they are
  append-only evidence and their conclusion (no credible random-jitter number is
  publishable) is unchanged and correct. This record is where the sharper reason
  now lives, and #520 and the probe README both point back to it.
- **The bad consequence, stated plainly.** This record improves the bookkeeping
  and the diagnosis of a gap without closing the gap, and it makes the
  specification *look worse* by doing so: §Decision 3 promotes a quietly
  implicit 0.50 % assumption into a visible unverified budget line against a
  ratified target. That is the correct direction. An outside reader of
  `docs/chipalooza/challenge-5-proposal.md` §5 still finds **UNMET** against
  this row and now also finds, in `spec/pll.md` itself, that half the 1.0 %
  line is unverified.
- **Nothing in `design/` changes**, no schematic, no netlist, and no `sim/`
  record is added, rewritten or superseded. The append-only tree is untouched.
- **What would force a new record.** Any of: `pss`/`pnoise` appearing in a
  future pinned build (§Decision 2 falsified, and DR-002 Decision 5's original
  method becomes runnable); #520 measuring a random component **above 0.50 %
  RMS** at any mandated corner, which would break the budget split §Decision 3
  makes explicit and put the ratified 1.0 % line itself in question; or #520
  recording that both (A) and (B) fail to converge, which would finally reach
  DR-002 Decision 5's §Consequences branch (b) and require superseding it
  rather than narrowing it. Widening the 1.0 % row to fit a measured result is
  not among them.
