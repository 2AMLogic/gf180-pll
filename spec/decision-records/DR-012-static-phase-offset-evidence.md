# DR-012: the static phase offset — what the evidence supports, and what the spec may say about it

- **Status**: proposed
- **Date**: 2026-09-16
- **Decided by**: agent-builder (issue #394)

## Context

`spec/pll.md` ratifies a **Lock criterion** with two thresholds, one of which
is `static phase error at the PFD inputs ≤ 1 ns`. Three places in the
specification then make claims *about* that criterion which #394 was filed to
reconcile:

1. The [Lock detector](../pll.md) section states that at `ff`/125 °C/3.63 V the
   loop "stands off **1.796 ns** of static phase in its own undisturbed steady
   state", citing `sim/supply-sensitivity`'s `supply_steady.csv`.
   [Verification owed](../pll.md) repeats it, and `DR-010` Decision 4 routes it
   to #394 rather than absorbing it into the lock-detector window.
2. The same section itemizes a static-phase-offset budget — 0.671 ns
   systematic (`sim/pfd-deadzone`) + 0.576 ns statistical (`mc-cp-mismatch`) +
   0.239 ns divider retiming, "up to ≈1.49 ns summed" — and notes that the sum
   is *itself* outside the ≤ 1 ns criterion.
3. The measured 1.796 ns is 2.7× the 0.671 ns systematic term it is nominally
   comparable to, at the same PVT corner and with mismatch disabled.

Two evidence records were taken to resolve this, and between them they change
which of the above the specification is entitled to say.

**`sim/supply-sensitivity/records/20260916-051708-8cedbba.md`** re-read all 45
rows of the committed steady-state grid — the first time that grid has been
read as a population rather than one row at a time. The deck measures the
REF→FB skew at two instants (`ta` = 6.4 µs, `tb` = 9.6 µs) and reports
`ferr = −(phi_b − phi_a)/(tb − ta)`; that identity inverts exactly, so every
committed row already carried how far its "static" phase moved between the run's
own two instants. Nobody had inverted it. Reading it:

- At `ff`/125 °C/3.63 V the phase fell from **2.518 ns to 1.796 ns** across
  that window and was still falling. The late window sits at 0.69–1.03 of the
  loop's slowest time constant; **one τ is not settled**. 1.796 ns is an upper
  bound on a decaying tail, not an undisturbed steady state.
- **30 of the 45 rows are in that condition**, including 15 of the 17 rows
  over the ratified bound, and every one of the 15 is moving *downward*.
- **Two rows are over the ratified bound *and* settled**, and they are not the
  corner the spec names: `ff`/27 °C/3.63 V at **1.227 ns** and
  `typical`/−40 °C/3.63 V at **1.049 ns**, with 11.7 ps and 10.6 ps of
  movement across the window, cross-checked from an independent node
  (`skew_s`, the UP/DN pulse-width difference) to 1.76 % and 2.26 %.
- **All 8 rows whose own `lock_detector` refused to assert are over the
  ratified bound** — 8 of 8. The source record routed those 8, as a class, to
  "#11, not a loop failure". Read against the ratified criterion rather than
  the deck's proxy, not one of them was inside the bound when its phase was
  sampled.
- The campaign's own acceptance threshold on that quantity was
  `ACC_PHI_FRAC = 0.02` of a reference period — **1.6 ns at its 12.5 MHz**,
  1.6× looser than the criterion it was being read against. Seven rows carry
  an overall `PASS` while standing off more static phase than `spec/pll.md`
  allows. That is why none of the above was visible from the verdict column.

**`sim/pfd-deadzone/records/20260916-051356-8cedbba.md`** measured the other
half, and it is the larger of the two findings. `spec/pll.md`'s 0.671 ns
systematic term is an *open-loop* charge-null offset taken at **f_ref = 25 MHz
with the control node pinned at 1.65 V**, while the closed loop runs at
**f_ref = 12.5 MHz** with its control node standing wherever the loop puts it
(1.396 V at `ff`/27 °C/3.63 V, 2.291 V at `ff`/125 °C/3.63 V, 0.978–0.991 V at
the three `−40 °C`/2.97 V corners). A second manifest re-measures the identical
quantity on the identical DUT — same stimulus, same reduction, same Icp code,
same solver options — at the loop's own reference frequency and across DR-001
Decision 2's whole ratified 0.9–2.4 V control window. 405 points, 45 corners ×
3 control voltages × 3 phase offsets, all measured:

| Vctrl | `t_offset` over the 45 corners | worst corner | corners over the ratified 1 ns |
|---|---|---|---|
| **0.90 V** (window bottom) | 0.778 … **1.873 ns** | `ff`/125 °C/3.63 V | **36 of 45** |
| 1.65 V (the cited point) | 0.009 … 0.657 ns | `ff`/27 °C/3.63 V | 0 of 45 |
| 2.40 V (window top) | 0.023 … 0.647 ns | `ff`/27 °C/2.97 V | 0 of 45 |

**The variable that matters is the control voltage, and the budget never
mentioned it.** Across the ratified control window the systematic term varies
by more than **100×** at a fixed corner (`ff`/27 °C/3.63 V: 0.175 ns at 2.40 V,
0.657 ns at 1.65 V, 1.823 ns at 0.90 V), and at the window's bottom it exceeds
the entire ratified criterion by itself at 36 of the 45 corners. By contrast
the **reference frequency is nearly irrelevant**: at the cited corner and the
cited 1.65 V, halving f_ref from 25 MHz to 12.5 MHz moves the term only from
0.671 ns to 0.628 ns (−6.4 %).

**The two campaigns cross-validate where they overlap.** At the three corners
where the closed loop settles near the bottom of the control window, the
open-loop systematic value at 0.90 V and the closed-loop settled phase agree to
within 0.09 ns — measured in different decks, different topologies (ideal
source vs. real filter), and different nodes:

| Corner | closed-loop Vctrl | open-loop `t_offset` @ 0.90 V | closed-loop settled phase |
|---|---|---|---|
| `fs`/−40 °C/2.97 V | 0.978 V | 0.897 ns | 0.838 ns |
| `typical`/−40 °C/2.97 V | 0.984 V | 0.923 ns | 0.953 ns |

That agreement is what licenses reading the two records together at all.

So the 2.7× "discrepancy" of #394's title was never a discrepancy between two
measurements of one quantity. It compared a tail sample to a settled number, at
a different reference frequency, and — decisively — at a different control
voltage. All three differences are now measured, and the control voltage
accounts for most of the gap.

## Decision

**1. The ratified Lock criterion is not relaxed, narrowed, cornered, or given
an exception.** It stands exactly as ratified: `|Δf_out/f_target| ≤ 0.1 %` and
static phase error at the PFD inputs `≤ 1 ns`, held ≥ 20 consecutive reference
cycles. No PVT carve-out, no per-corner value, no f_ref-scaled restatement.
This is the decision #394 explicitly left open, and it is decided in the
direction CLAUDE.md requires: the evidence that appeared to indict the
criterion turned out not to support the sentence built on it, and the evidence
that *does* indict it indicts the **design**, which is where the gap belongs.

**2. `spec/pll.md` stops asserting the 1.796 ns sentence, because the evidence
does not carry it.** Wherever the specification currently says the loop "stands
off 1.796 ns of static phase in its own undisturbed steady state" at
`ff`/125 °C/3.63 V, it must instead say that the value sampled there is
**1.796 ns and still falling** (2.518 ns one window earlier), that the run was
stopped at ≈1.3 τ, and that the settled value at that corner is **unmeasured**.
This is a correction of fact, not a softening: the corner is not cleared, and
it is not shown to meet the criterion either.

**3. The design does not meet the ratified Lock criterion at every PVT corner,
and the specification states that as a measured design gap.** The binding
evidence is `ff`/27 °C/3.63 V at **1.227 ns** settled — 23 % over the bound —
with `typical`/−40 °C/3.63 V at 1.049 ns behind it. Both are nominal-skew,
systematic-only numbers at f_ref = 12.5 MHz, N = 8, Icp code b1b0 = 10; the
0.576 ns statistical term adds on top of them, not instead of them. This
replaces a budget-arithmetic worry ("≈1.49 ns summed is already outside the
criterion") with a measurement, and it upgrades the [Lock criterion] entry in
[Verification owed](../pll.md) from "unreconciled" to a named, quantified
design gap.

**4. The 0.671 ns systematic term is not a worst case and may not be cited as
one.** `spec/pll.md`'s budget presents it as *the* worst-corner systematic
static offset. It is the worst **corner** at one **operating point** —
f_ref = 25 MHz, Vctrl pinned at 1.65 V — and the term varies by more than 100×
across the ratified control window at a fixed corner. The worst case over
DR-001 Decision 2's ratified 0.9–2.4 V window is **1.873 ns**
(`ff`/125 °C/3.63 V at Vctrl = 0.90 V), **2.8× the cited figure**. Wherever the
budget cites 0.671 ns it must carry the operating point it was taken at and
cite `sim/pfd-deadzone/records/20260916-051356-8cedbba.md` alongside; a number
this specification calls a worst case is only a worst case over the axes it was
swept on, and Vctrl was not one of them.

**4a. The static-phase-offset budget is restated against the control window.**
Summed at the bottom of the ratified control window the three terms are
1.873 ns systematic + 0.576 ns statistical + 0.239 ns divider retiming =
**≈2.69 ns**, against a ratified 1 ns. The previously stated ≈1.49 ns is the
same sum at Vctrl = 1.65 V. Both are stated, with their operating points,
because the spread between them *is* the finding.

**4b. The answer to "is ≤ 1 ns reachable at `ff`/125 °C/3.63 V, and over which
cells" is: not at the bottom of the control window, at that corner or at 35
others — and the limit is the charge pump's residual, not the corner.** At
Vctrl = 0.90 V the systematic term alone exceeds the whole criterion at **36 of
45** corners, leaving nothing for the statistical or retiming terms. At 1.65 V
and 2.40 V it exceeds it at none, so the criterion is reachable over most of
the window. **Where a given (f_out, band code, N, trim code) cell lands on that
window is set by the [band-selection rule](../pll.md)**, which this record does
not re-derive; what it establishes is that the control voltage — not the PVT
corner — is the axis the criterion is lost on. This supersedes nothing: it is
the first measurement of that axis.

**5. A testbench's acceptance threshold on a ratified quantity is the ratified
value, not a proxy for it.** `sim/supply-sensitivity` judged a ratified
absolute bound in seconds against a scale-free fraction of a reference period,
and the two disagreed by 1.6× at its own f_ref (3.2× at its 6.25 MHz bundle).
A deck whose acceptance is looser than the spec cannot substantiate a claim
about that spec, and a `PASS` from it is not evidence of compliance. This binds
every campaign, not only this one: where `spec/pll.md` ratifies a value, the
deck cites that value. `sim/supply-sensitivity` is converted with this record.
**`sim/pll-top-smoke` is not, and is the other live instance**: the
assembled-top-level acceptance gate applies the same `ACC_PHI_FRAC = 0.02` to
the same ratified quantity at f_ref = 9 MHz, i.e. a 2.22 ns bound, 2.2× looser.
Its committed measurement (0.4477 ns) is inside both thresholds so no verdict
is affected, but the gate has 2.2× less margin than it appears to; filed as
**#400** rather than changed here, because it is a different campaign with its
own record and its own test.

**6. The settled static phase at the unsettled over-bound corners is owed, and
is named rather than estimated.** Fifteen rows are over the ratified bound with
the phase still moving; where each settles is not derivable from committed data
and is not asserted anywhere in this record or the evidence behind it. Closing
it needs `run.sh`'s settling escalation (36.8 µs = 3.96 τ) run at those
corners, which is expensive — the unescalated 12.0 µs run at
`ff`/125 °C/3.63 V alone took 11 609 s of ngspice analysis time, so the
escalated length there is of order 10 h. It is filed as **#399** and listed in
[Verification owed](../pll.md).

**7. Implementation of a design fix is not decided here, but the axis it must
act on is.** This record establishes *that* the loop misses the criterion at
`ff`/27 °C/3.63 V, *why the prior evidence did not show it*, and *what the
offset is actually a function of*: the charge pump's residual per-cycle charge
`q_zero` at the control voltage the loop happens to stand at, which grows
steeply toward the bottom of the ratified window (−8.6 fC at 0.90 V against
−3.3 fC at 1.65 V at `ff`/125 °C/3.63 V). Whether the fix is in the pump's
output-stage compliance, the Icp trim rule, the divider retiming, or the
band-selection rule that decides where on the control window a cell sits, is a
design question this record deliberately does not settle — but a fix that does
not reduce `q_zero` at low Vctrl is not addressing the measured cause.

## Alternatives considered

- **Relax the Lock criterion to cover the measured offsets (≥ 1.3 ns, or
  1.8 ns to cover `ff`/125 °C/3.63 V's sample).** Rejected on the same grounds
  `DR-010` rejected it and CLAUDE.md states outright: agents do not relax the
  ratified spec to make results pass. It would also now be rejected on
  evidence, which is the stronger reason — the headline number it would have
  been sized against is a tail sample, so the relaxation would have been sized
  against an artefact of a too-short transient.
- **Give the criterion a per-corner or f_ref-scaled form** (e.g. a fraction of
  a reference period, which is what the deck was effectively applying).
  Rejected: the criterion is absolute *because* the observable is. The
  `lock_detector` window is an inverter-chain delay — an absolute number of
  nanoseconds — so a criterion that scaled with f_ref would stop describing the
  same event as the flag watching it, which is exactly the property the
  criterion's own rationale is built on. `DR-010` T1′/T2′ tie the window to the
  criterion's absolute value; scaling one and not the other breaks both.
- **Leave `spec/pll.md`'s 1.796 ns sentence alone and simply add the new
  corners beside it.** Rejected: the sentence is not merely incomplete, it
  asserts a steady state the data contradicts, and two downstream records
  (`DR-010` Decision 4, the Verification-owed row) reason *from* it. Leaving a
  known-unsupported claim in a ratified specification because correcting it is
  awkward is the failure mode this repository's append-only evidence
  convention exists to prevent.
- **Declare the criterion unreachable and route the whole thing to a design
  change.** Rejected as premature: it is missed at 2 of 45 corners on
  systematic-only evidence, by 23 % and 5 %, at one (f_ref, N, trim) cell. "Not
  met today at two corners" is a design gap with a measured size; "unreachable"
  is a much stronger claim that the 15 unsettled corners and the unswept
  reference-frequency axis do not yet support in either direction.
- **Fix the deck's threshold silently, without a record.** Rejected: tightening
  an acceptance threshold changes what past `PASS` verdicts meant, and seven
  committed rows are affected. The source record is not re-judged (append-only),
  so the only place that fact can live is here.

## Consequences

- **`spec/pll.md` changes in three places**: the Lock-detector section's
  "separate, larger finding" paragraph (restated per Decision 2 and 3), the
  static-phase-offset budget's citation of 0.671 ns (Decision 4), and the
  [Lock criterion] row of [Verification owed](../pll.md) (Decisions 3 and 6).
  The Lock criterion's own normative text is **unchanged** — that is Decision 1.
- **A design gap that was previously stated as a budget-arithmetic concern is
  now a measurement.** That is worse news, not better: "≈1.49 ns summed exceeds
  1 ns" could have been conservatism in the summation, and 1.227 ns settled at
  `ff`/27 °C/3.63 V cannot be. The block as drawn does not meet its own
  ratified Lock criterion at every mandated corner, and row 9's status reflects
  that.
- **`DR-010` Decision 4 is partly overtaken and partly reinforced.** Its
  conclusion — that this is a loop question and not a lock-detector-window
  question, and that a flag refusing to assert there is reporting correctly —
  stands, and is strengthened well beyond the one corner it was argued from:
  **all 8 of the grid's `FAIL:lock` corners are over the ratified phase bound**,
  so there is no corner on this grid where the flag deasserted on a part the
  criterion says is locked. Its *premise*, that 1.796 ns is what the loop
  stands off at `ff`/125 °C/3.63 V, does not stand. `DR-010` is **not
  superseded**: no decision it makes changes, and the sizing decision that
  record exists for is untouched.
- **`sim/supply-sensitivity`'s own routing of those 8 corners is not
  supported and should not be relied on.** `20260901-155456-46b92f8` reads
  them as a `lock_detector` window question owned by #11 — "everything
  electrical settled and the window comparator did not assert". Against the
  ratified criterion the electrical state at those corners is *not* inside
  spec, so #11 is at most a co-owner. The record is append-only and is **not**
  rewritten; the correction lives here and in the new evidence record, and
  `sim/CHARACTERIZATION.md`'s row for that campaign is updated to point at
  both. Anyone sizing work for #11 from that 8-corner list should read this
  record first.
- **Seven committed `PASS` verdicts in
  `20260901-155456-46b92f8` are now known to have been issued against a looser
  threshold than the spec's.** That record is **not** rewritten or re-judged —
  `sim/README.md`'s append-only rule — and the new evidence record carries an
  `over_deck` column preserving exactly what each row was judged at, so the two
  can never be confused. Every *future* run of that campaign judges against the
  ratified bound.
- **`sim/supply-sensitivity`'s settling escalation gets a second gate and will
  escalate more corners**, at real compute cost. The old gate (`|ferr| >
  1e-3`) is blind to the phase criterion, because a small residual frequency
  error integrated over a long window is a large phase shift; on the committed
  grid, 30 of 45 rows would trip the new phase gate. A full re-run of that
  campaign is therefore substantially more expensive than the committed one and
  is not attempted as part of this record.
- **`sim/pfd-deadzone` grows a second manifest** rather than a sibling
  experiment directory, per `sim/README.md`'s "two manifests, one experiment
  directory" rule — same DUT, same reduction, second operating point. Its
  record does **not** supersede the parent: the parent's dead-zone verdict is
  untouched and this manifest deliberately does not sweep the axis that verdict
  rests on.
- **What is still not known, stated plainly**: where the 15 unsettled
  over-bound corners settle; whether the criterion is met at any (f_ref, N,
  trim-code) cell other than the one measured; and the post-extraction value of
  any of it (#18). Decision 3's gap is a floor on the problem, not a
  characterization of it.
