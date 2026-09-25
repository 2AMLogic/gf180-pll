# DR-021: what `sim/supply-sensitivity`'s three FAILing criteria are evidence of, and who owns each

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-011 and
  DR-012 record (a builder drafts the record on the evidence; the operator's PR
  approval is the ratifying act). Status stays `proposed` until that approval
  and merge.
- **Date**: 2026-09-25
- **Decided by**: agent-builder, issue #506
- **Relates to**: DR-001 Decision 2 and **DR-003 Decision 5** (the control
  window — this record does not revise either; it states which of the two the
  campaign graded against and which one is current). DR-012 (the static-phase
  finding — criterion 1 turns out to be an instance of it; unchanged here).
  DR-011 (post-supply-step settling — its Decision 2 named the END-plateau
  `under-damped` result as the committed evidence inconsistent with its own
  single-pole model; this record identifies the recovery law that makes both
  observations consistent, and **does not** revise DR-011's Decision 1 or 2).
  DR-006 (the loop filter — nothing here indicts its sizing either).
- **Evidence**: `sim/supply-sensitivity/records/20260925-044237-4ff4f65.md` —
  arithmetic on committed data, no new simulation, reproducible from
  `sim/supply-sensitivity/testbench/fail_criteria_reexamination.py` and
  unit-tested in `sim/tests/test_supply_sensitivity_fail_reexamination.py`.
  It re-examines `.../20260901-155456-46b92f8.md` (#14/#257, the 45-point grid
  and all three step/ramp corners) and consumes
  `.../20260916-051708-8cedbba.md` (#394, behind DR-012) and
  `sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv` (#8).

## Context

`sim/supply-sensitivity/records/20260901-155456-46b92f8.md` records **FAIL** on
three of its four criteria and routes each class of finding, by name, to the
design issue that owns it: #9 (`pfd_cp`), #10 (`loop-dynamics`), #11
(`lock_detector`). All three of those issues closed between 2026-07-31 and
2026-09-15. `docs/chipalooza/challenge-5-proposal.md` and `README.md` — the two
documents written to be read by someone outside this repository — told that
reader the findings "are already routed to their owning issues", which stopped
being true without either document changing;
`docs/lib/check-issue-reference-state.sh` now fails CI on that class of rot, and
#506 was filed for the half a check cannot fix: correcting the sentence does not
give the findings an owner.

Naming an owner needs each finding said precisely first, and **two of the three
do not say what the record's headline says.** The record's own criterion names
are the source of the confusion, not its numbers: "output frequency vs. supply"
is a composite five-check lock criterion of which zero checks are about
frequency, and "control voltage inside DR-001's usable window" is not the
budget `spec/pll.md` actually ratifies. Both were read at face value — by this
repository's own aggregation report, by the proposal, and by the README — for
24 days.

## Decision

**1. Criterion 1's FAIL is the static-phase-offset finding DR-012 already owns,
and carries no frequency content.** 0 of the 45 corners missed either frequency
check; the worst frequency deviation anywhere on the grid has 3.4× headroom
against its own criterion and the worst residual fractional frequency error has
4.4×. The 10 non-`Y` corners are 2 static-phase and 8 LOCK-flag, and those two
classes are assigned to the wrong corners: neither corner the record routed to
the charge pump was settled when sampled (each moved 0.60–0.72 ns across the
run's own two measurement instants, more than half the ratified bound, at
≈1.3 τ), while **both** settled violations of the ratified ≤ 1 ns Lock criterion
sit inside the 8 routed to the lock detector. The flag not asserting and the
phase being out of bound are the same event read at two nodes.

Owners, all open, none new: **#511** (the design resolution of the two settled
misses of the ratified ≤ 1 ns criterion), **#399** (the settled static phase at
the 15 corners sampled on a decaying tail — DR-012 Decision 6) and **#437** (the
full-grid re-take at the trimmed detector window — the 8 LOCK-flag corners' own
mechanism, DR-013/DR-014). The specification already states the design gap:
row 9's "target **not met** at 2/45 corners".

**2. Criterion 1b's recorded FAIL is graded against a superseded figure and
does not reproduce against the current one.** The 4 failing points leave
DR-001 Decision 2's **predicted** 0.9–2.4 V control window. DR-003 Decision 5
**measured** the usable window at 0.9–2.7 V on 504 curves and supersedes that
prediction; `spec/pll.md`'s own Budget-2 text and band-selection rule both
already state 0.9–2.7 V. Against the current window **0 of 45 points leave
it** — and that is not a clearance, because the tightest margin anywhere is
**53 mV** of a 1.8 V window, at `ss`/−40 °C/3.63 V. The specification must say
so rather than carrying a FAIL against a number it no longer uses.

**3. The ratified Budget 2 is missed at 9 of 15 (bundle, temperature) cells,
and this record does not relax it.** Row 12's Budget 2 — a DC rail excursion
over 2.97–3.63 V must consume ≤ 0.6 V of the control window — is a different
check from the window check above, and nothing had ever graded the grid against
it. Measured: **9 of 15 cells exceed 0.6 V**, worst **0.846 V** at `ss`/−40 °C,
**1.41×** the budget and **47 %** of the window consumed by the rail alone. The
consumption is **not anomalous**: it agrees with what the cell's own selected
band requires, from #8's committed open-loop `f(Vctrl, vdd)` table, to within
**5.7 mV at every one of the 15 cells** and 1.9 mV (0.2 %) at the worst. The
loop is absorbing exactly the supply pushing #8 characterised, with nothing
left over.

**4. Budget 2's own derivation prices half the excursion its row specifies, and
which of the two is normative is an operator decision this record refuses to
make.** The derivation reads "a ±10 % (±0.33 V) rail excursion moves the
open-loop frequency by up to 17 %", and its 17 % is `%/V × 0.33 V` — the same
arithmetic the section's own pushing table uses for its "worst frequency shift
over a ±10 % rail" column. So the 0.20 … 0.55 V it predicts, and therefore the
0.6 V budget sized to cover it "with a small allowance", are for a **0.33 V**
excursion; the row demands the shift over **0.66 V**. Read over 0.33 V, **0 of
15 cells** exceed the budget (worst 0.431 V, 28 % inside). The factor of two is
in the numerator, not the denominator: the measured `Kvco/f_out` at the worst
cell's band is 0.429/V, inside the 0.31 … 0.84/V the derivation assumed, and
17 % / 0.429 is 0.396 V.

Two readings, and they disagree on whether a ratified row is met. **The
full-range reading is the operative one until an operator says otherwise**,
because it is what the row says; so `spec/pll.md` states Budget 2 as **missed
at 9 of 15 cells** with the derivation's inconsistency disclosed beside it.
Choosing the reading under which the row passes would be relaxing a ratified
line to make a result pass, which CLAUDE.md forbids and which this record does
not do. The choice is filed as **#525**.

**4a. The consequence Budget 2 was protecting against is not observed, and the
margin left is stated.** The section's own text says that past 0.6 V "the fine
tuning range left inside a band is no longer enough to hold lock across the
rail range and the band plan has to be re-cut". The band **does** hold at every
one of the 45 points: 0 leave the measured 0.9–2.7 V window. It holds by
**53 mV** at `ss`/−40 °C/3.63 V. So the budget is missed and its stated failure
mode is 53 mV away, at a corner whose consumption is measured, not estimated —
which is a sharper statement than either "met" or "the band plan must be
re-cut", and is the statement the specification now carries.

**5. Criterion 3's one `under-damped` corner is a linear, current-limited
recovery ≈8 µs short of settled — not an under-damped loop.** Section 3c
classifies `ss`/−40 °C from the ratio of two frequency-residual samples against
`exp(-Δt/τ)`, a discriminant that assumes an exponential recovery. The retained
END-plateau waveform is not one: the control node slews at a nearly constant
−20.3 mV/µs for 18.75 µs after the ramp and then stops, and a straight line fits
those samples with 33 % less residual in volts than a single exponential (20.5
vs 30.8 mV rms; 21 % less at `typical`/27 °C; at `ff`/125 °C the segment is
4 bins and discriminates nothing). The model-free damping test — overshoot past
the final value, and reversal count — does **not** separate that corner from the
two the record classifies `settles`: 17.2 mV of overshoot on 20.0 mV of its own
control-line ripple, against 19.5 and 22.5 mV at those two.

What separates it is how far its control node has to travel: the three corners'
recovery durations (18.75, 9.75, 2.25 µs) rank exactly as their Budget-2
consumptions (0.846, 0.698, 0.558 V), at slopes within 1.6× of each other. The
ramp demands that travel in 6.4 µs; at `ss`/−40 °C the node takes 2.9× longer.
At the extended hold's end it still had 13.11 ns of REF→FB phase closing at the
measured 1.705e-3 — 7.69 µs more at that rate, against 7.00 and 8.06 µs at the
two `settles` corners. **Decisions 3 and 5 are the same mechanism**: the corner
that consumes the most control window for a rail excursion is the corner that
takes longest to recover from one.

Owner, open, not new: **#405** (the #395 remainder), whose scope item 3 already
names section 3c's `under-damped` classification as something its ≈800-sample
measured decay law must test. One scope note is added there by comment: the
campaign must retain the **END** plateau's phase trace as well as the high
plateau's, since the END plateau is where this classification lives.

**6. No verdict in `20260901-155456-46b92f8` is re-judged, and no spec line is
relaxed.** That record stands exactly as written, remains the campaign's PVT
statement, and every number quoted from it here is quoted. Criterion 3's
residual is still outside 1e-3 at the hold it ran; criterion 1b's window check
still FAILs against the figure it applied; the 7.69 µs above is still an
extrapolation at a measured rate, which is the optimistic end of the same
bracket DR-011 declined to promote to a spec bound, for the same reason.
`sim/README.md` is append-only: a re-reading is a new record, never an edit.

## Alternatives considered

- **Re-point the two documents' routing at #437 and stop there.** Rejected:
  #437 re-takes the same grid at the trimmed detector window. A re-take may
  move the numbers; it cannot tell a reader that criterion 1 has no frequency
  content, that criterion 1b was graded against a superseded window, or that
  the budget the row actually ratifies was never graded at all. Those are
  properties of the committed evidence, available for the cost of arithmetic,
  and #506's acceptance criteria ask for them.
- **Read Budget 2 as its derivation prices it (±0.33 V), report the row as
  met, and note the wording.** Rejected, and this is the most tempting
  alternative here: it is arithmetically defensible, it makes nine cells pass,
  and the wording change looks editorial. It is exactly the move CLAUDE.md
  forbids — "agents do not relax the ratified spec to make results pass" — and
  the row's text is unambiguous about the excursion. Filed as an operator
  decision (#525) with both readings measured, which is the most an agent may
  do here.
- **Tighten Budget 2 to cover the measured 0.846 V, or re-cut the band plan.**
  Rejected as unsupported in both directions: the band plan holds at every
  measured point (Decision 4a), and neither a looser nor a tighter number is a
  measurement. DR-001 Decision 2 accepted this weakness "with eyes open" and
  named its own reopening condition (Budget 1, the AC ripple line) — which this
  evidence does not touch.
- **File one new issue per criterion, three in total.** Rejected: two of the
  three already have open owners whose scope covers them (#511/#399/#437 for
  criterion 1, #405 scope item 3 for criterion 3). Filing duplicates would
  split the evidence trail and create exactly the ownership ambiguity #506 is
  about. One new issue, for the one question nobody owns.
- **Record the criterion-3 re-classification as `settles` and close the
  finding.** Rejected: the residual **is** outside 1e-3 at the hold that ran,
  so the FAIL is real. What this record changes is what the FAIL is evidence
  *of* — a hold ≈8 µs short of a slew-limited recovery, rather than a filter
  with inadequate damping — and the difference matters because the two route to
  different fixes. Measuring it is #405's, on ≈800 samples rather than 2.
- **Fix `run.sh`'s criterion-1b window constant to 0.9–2.7 V in this change.**
  Rejected as out of scope and premature: the deck's 1b check should grade
  Budget 2 (the ratified line) rather than a window figure at all, and what it
  should grade depends on #525's answer. Named as follow-on work in #525's own
  scope instead of changed here.

## Consequences

- **`spec/pll.md` changes in two places.** Row 12's Status/corner-binding cell
  and the Supply sensitivity section's Budget 2 both stop reading as a purely
  **derived** budget and state the measured consumption: 9 of 15 cells over the
  0.6 V line under the row's own excursion, worst 0.846 V at `ss`/−40 °C, the
  derivation's ±0.33 V inconsistency, and the 53 mV of window margin left. The
  budget's **normative text is unchanged** — that is Decision 4, and changing
  it is #525's to propose.
- **This is worse news than the record it re-reads, on one criterion and better
  on two.** Criterion 1b goes from "4 of 45 points outside a window" to "a
  ratified budget missed at 9 of 15 cells, with 53 mV of window left" — a
  larger finding against a line that actually binds. Criteria 1 and 3 go from
  two unowned design-margin findings to instances of findings already owned and
  already in the specification. A reader who took "FAILs 3 of 4 criteria" as
  three independent design defects was reading it wrong in both directions.
- **One new issue (#525), no reopened ones.** #9, #10 and #11 stay closed:
  nothing here is work they scoped. #511, #399, #437 and #405 each gain a named
  criterion they are now the recorded owner of, and #405 gains one scope note.
- **`sim/supply-sensitivity`'s criterion 1b is measuring the wrong thing and
  will keep doing so until #525 answers.** Every future run of `run.sh`,
  including #437's full-grid re-take, will emit the same 0.9–2.4 V window check
  and the same absent Budget-2 check. That is a known, filed defect in the deck
  rather than a surprise, and the re-take's record must be read with this one
  beside it.
- **Two things this evidence cannot say, and no future reading of it can.** The
  passive process axes are pinned in every input read, so nothing here bounds
  the Budget-2 consumption or the recovery slope over the loop filter's own
  R/C spread (C1 alone spans 107.1–133 pF, DR-006) — and the recovery rate is
  the quantity that spread moves most directly. And the post-ramp analysis
  reads 3 corners of 45, at one excursion, one rate and one
  (f_ref, N, trim-code) cell; the step/ramp deck has never been run wider.
- **The criterion names in this campaign's own report are a hazard, and they
  stay.** "Output frequency vs. supply" and "control voltage inside DR-001's
  usable window" are the headings under which a composite lock criterion and a
  superseded window figure were read as a frequency finding and a window
  failure by three documents. They are not renamed here, because renaming a
  committed record's section headings is an edit and `sim/` is append-only;
  `sim/CHARACTERIZATION.md` and the proposal carry the correction instead.
