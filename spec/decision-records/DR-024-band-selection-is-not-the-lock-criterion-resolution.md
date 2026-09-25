# DR-024: The band-selection axis is measured and eliminated as the Lock-criterion resolution — what the ratified Lock-criterion and Lock-time rows mean given the gap that remains

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-023 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #511
- **Numbering**: DR-024 is the next unused slot as of `4422f1d` (highest on
  `main` is DR-023). Per TEMPLATE.md's collision rule this was re-checked
  immediately before the PR was opened.

## Context

**DR-012 left exactly one thing deliberately open, and nothing owned it.**
Decision 3 of that record establishes, by measurement, that the loop settles
outside `spec/pll.md`'s ratified `<= 1 ns` static-phase Lock criterion at two
of the 45 mandated PVT corners — **1.227 ns** at `ff`/27 °C/3.63 V and
**1.049 ns** at `typical`/−40 °C/3.63 V, nominal-skew and systematic-only.
Decision 1 declines to relax the criterion, so the gap belongs to the design.
Decision 4b locates the axis it is lost on — the charge pump's residual
per-cycle charge `q_zero` at the control voltage the loop happens to stand at,
which grows steeply toward the bottom of the ratified control window — and
Decision 7 then names four candidate loci for a fix (the pump's output-stage
compliance, the Icp trim rule, the divider retiming, the band-selection rule)
and **declines to pick among them**.

Two of the four are cheap to eliminate or confirm from committed data, and one
of them — the band-selection rule — Decision 4b explicitly flagged and skipped:

> **Where a given (f_out, band code, N, trim code) cell lands on that window is
> set by the [band-selection rule], which this record does not re-derive**;
> what it establishes is that the control voltage — not the PVT corner — is the
> axis the criterion is lost on.

`spec/pll.md`'s [Verification owed](../pll.md#verification-owed) row for the
Lock criterion carries the consequence as two unowned items: **(b)** any
closed-loop measurement at an `(f_ref, N, trim-code)` cell other than the one
characterized, "so a closed-loop cell that parks low on that window is expected
to miss and has never been run"; and **(c)** "the design resolution, which
DR-012 Decision 7 deliberately does not pick". Neither had an issue. #394 and
#403 are closed; #399 owns a measurement (the 15 unsettled corners), not a fix.

`sim/supply-sensitivity/records/20260925-090649-4422f1d.md` does the
re-derivation Decision 4b named. It re-simulates nothing: it evaluates the
normative rule and `run.sh`'s own selector against #8's committed 3528-point
`f(Vctrl, vdd)` table, joins both to `sim/pfd-deadzone`'s measured 135-cell
open-loop systematic-offset grid, and reads the result against DR-012's own
grading of the 45-point closed-loop grid. What it finds forces this record.

## Decision

**1. The ratified Lock criterion is not relaxed, narrowed, cornered, or given
an exception.** It stands exactly as ratified — `|Δf_out/f_target| <= 0.1 %`
and static phase error at the PFD inputs `<= 1 ns`, held ≥ 20 consecutive
reference cycles. This restates DR-012 Decision 1 unchanged and is repeated
here because everything below narrows *what the evidence describes*, never the
bound it is judged against. No PVT carve-out, no per-corner value, no
Vctrl-conditioned restatement.

**2. The band-selection axis is eliminated as a sufficient resolution, on
measurement rather than on judgement.** Evaluated over DR-003 Decision 5's
measured 0.9–2.7 V control window across the whole ratified 10–200 MHz output
band — 39 output frequencies × 45 PVT points — `spec/pll.md`'s normative rule
("the lowest 3-bit band code that reaches `f`") still parks at least one corner
at `Vctrl <= 1.05 V` at **23 of the 39** frequencies, down to **0.919 V**
(`ss`/125 °C/2.97 V, band 6, f_out = 135 MHz). On DR-012 Decision 4a's own
summed budget (systematic + 0.576 ns statistical + 0.239 ns divider retiming)
the criterion is missed at **1397 of the 1628** rule-selected points with a
measured systematic term — **85.8 %**. Meeting the criterion on that summation
needs `t_sys <= 0.185 ns`; the rule-selected mean is 0.3954 ns. The band
boundaries are fixed and the VCO's PVT spread is wider than one code's overlap,
so at every output frequency some corner must sit near the bottom of some band.
**No band-selection policy on this band map keeps the loop out of the region
DR-012 Decision 4b measured the criterion is lost in.** DR-012 Decision 7's own
closing sentence therefore stands as the resolution's necessary condition: *a
fix that does not reduce `q_zero` at low Vctrl is not addressing the measured
cause.*

**3. The rule is nevertheless load-bearing on this criterion, and the evidence
grid does not apply it.** The same sweep shows the rule *does* bound the
systematic half well where it is applied: `t_sys` alone exceeds the ratified
1 ns at only **2 of 1628** rule-selected points. But `sim/supply-sensitivity`'s
`derive_op_points` does not apply the rule — it picks, per (bundle,
temperature), the band whose control voltage is closest to the midpoint of a
0.85–2.70 V search window. It is the only band selector in `sim/` that is not
the rule (`sim/pll-top-smoke` states and applies the rule by name). At
f_out = 100 MHz the two selectors agree at 14 of the 15 cells and disagree at
**`ff`/27 °C**, which is the cell carrying the grid's largest settled
violation. `derive_op_points` is corrected to the rule; the correction affects
**future runs only** and re-judges nothing already committed.

**4. What that does, and does not do, to the two settled violations.** It does
**not** clear either, and it does not reduce the measured numbers:

| Corner | settled phase | band run | band the rule selects | status after this record |
|---|---|---|---|---|
| `typical`/−40 °C/3.63 V | **1.049 ns** | 6 | 6 (under both window readings) | **a settled violation of the ratified criterion at a rule-compliant configuration.** Unchanged, and it is now the *binding* one |
| `ff`/27 °C/3.63 V | **1.227 ns** | 6 | **5** (over the measured 0.9–2.7 V window) | **a settled violation at a configuration no rule-compliant part carries.** The measurement stands as a correct measurement of band 6; what it is evidence *about* changes. The rule-selected cell (`Vctrl` 2.595 V) has **never been run closed-loop**, and its systematic term is **unmeasured** — `sim/pfd-deadzone`'s grid tops out at 2.40 V, where that corner measures 0.1750 ns against 1.0546 ns interpolated at the band-6 cell |

The `ff`/27 °C row is **not** reclassified as passing, and no number anywhere is
softened to make it look like one: it is reclassified from *measured evidence
about a compliant part* to *measured evidence about a configuration the rule
does not select, with the rule-selected configuration owed*. At the two
supplies where the rule-selected cell **is** inside the measured offset grid,
the band choice moves the systematic term by 2.7× (0.9121 → 0.3333 ns at
2.97 V; 0.9490 → 0.3548 ns at 3.30 V).

**5. The ratified Lock-criterion row says this, and the Lock-time row says what
follows from it.** `spec/pll.md`'s [Lock criterion](../pll.md#verification-owed)
Verification-owed row states **one** settled violation at a rule-compliant
configuration (`typical`/−40 °C/3.63 V, 1.049 ns, 4.9 % over) and **one**
settled violation at an off-rule configuration whose rule-selected replacement
is owed; items (b) and (c) are re-pointed to this record and to #511, and item
(b) is given the cell to run rather than left open (Decision 6). The
[Lock time](../pll.md#lock-time) row (row 9) keeps its "**not met**" status and
keeps naming the criterion as the reason, with the corner count corrected from
2/45 to **1/45 measured at a rule-compliant configuration, plus 1/45 owed** —
this is a change of *attribution*, not of target, and the row's `< 100 µs`
number is untouched.

**6. The design gap is accepted for v1, with a measured bound and a named
cause, and the work it needs is filed rather than implied.** No circuit change
is made by this record: DR-012 Decision 7's four loci are narrowed to one (the
pump's `q_zero` at low Vctrl) by Decision 2 above, and choosing *how* to reduce
it is a circuit-design campaign with its own characterization, not a
carry-through of an evidence join. What this record fixes is that the gap is now
**bounded, attributed and owned** instead of open-ended:

- **Owed measurement (item b)**, and the cell is named, not left to be chosen:
  **f_out = 135 MHz at `ss`/125 °C**, band 6 per the rule, parking at
  0.919 / 1.201 / 1.463 V across the rail — the lowest rule-compliant parking
  anywhere in the ratified output band. At N = 8 that is f_ref = 16.875 MHz,
  which the [Icp trim-code rule](../pll.md#icp-trim-code-rule) maps to the
  16 MHz row (one unit leg, b1b0 = 00): a different cell on all three axes from
  the only one ever characterized. The prediction it must test is stated in
  advance in the evidence record so it can be wrong.
- **Owed measurement (`ff`/27 °C at the rule-selected band 5)**, without which
  the reclassification in Decision 4 stays a reclassification and never becomes
  a clearance.
- **Owed design work (item c)**: reduce `q_zero` at low Vctrl, or the criterion
  is not met over the ratified `(f_out × PVT)` space on DR-012 4a's budget.

**7. What this record does not establish, stated plainly.** It does not measure
anything. Every `t_sys` it reasons from is open-loop, at f_ref = 12.5 MHz, and
interpolated on three control voltages of a curve DR-012 measured to be
strongly non-linear. The 85.8 % figure is a statement about DR-012 4a's
worst-case **linear** budget sum, which is conservative against the nominal-skew
closed-loop grid (settled phases 0.14–1.23 ns) — it is not a prediction of 1397
failing measurements, and this record does not claim one. The one cross-check of
its own predictive quality available on committed data came in 0.21 ns high
(`typical`/−40 °C/3.63 V: 0.8354 ns predicted, 1.049 ns measured), which is the
size of the retiming term.

## Alternatives considered

- **Amend the band-selection rule to prefer the band that parks highest on the
  control window.** Rejected on the record's own evidence: the rule *already*
  biases that way — it is the low band codes that reach a given `f` near the
  top of their range, which is why the rule's stated Kvco rationale and this
  criterion point the same direction — and Decision 2 shows even the existing
  bias leaves some corner at 0.92–1.05 V at 23 of 39 output frequencies. An
  amendment would buy a few tens of millivolts at some cells and cost the Kvco
  bound the rule exists to hold, for a gap of ≈0.7 ns.

- **State the rule's evaluation window normatively as 0.9–2.7 V (DR-003
  Decision 5's measured window) and stop there.** Rejected as a *resolution*,
  though the ambiguity is real and is reported: `spec/pll.md` states "reaches
  `f`" without naming a window, and the two available readings select different
  bands at `ff`/27 °C / 100 MHz. Under DR-001 Decision 2's predicted 0.9–2.4 V
  window the rule has **no answer at all** at 4 of the 15 cells at 100 MHz, so
  the measured window is the only reading under which the rule is satisfiable —
  which is an argument for writing it down, not for calling it a fix. Making it
  normative is a separate spec change with its own blast radius (it governs
  every campaign's operating-point derivation, not just this one) and is filed
  rather than smuggled in here on a Lock-criterion record.

- **Declare `ff`/27 °C/3.63 V cleared, on the strength of the 0.1750 ns
  measured at 2.40 V and the 2.7× improvement at the two supplies that are on
  the grid.** Rejected outright. The rule-selected cell sits at 2.595 V, off the
  measured grid, and no closed loop has ever been run there. Clearing a ratified
  criterion at an unmeasured operating point on the strength of a trend is the
  precise failure DR-012 was written to correct — it is what the withdrawn
  1.796 ns sentence did, in the other direction.

- **Relax the criterion, or condition it on a control-voltage sub-range.**
  Rejected on the same grounds DR-010 and DR-012 Decision 1 rejected it, and
  CLAUDE.md states outright: agents do not relax the ratified spec to make
  results pass. It would also now be rejected on evidence — Decision 2 shows the
  region where the criterion is lost is reachable under the *normative* rule at
  most output frequencies, so a Vctrl carve-out would exclude operating points
  the specification requires the part to support.

- **Pick a circuit fix here (pump output-stage compliance, or the Icp trim
  rule).** Rejected as out of scope for an evidence-join record and as
  premature on this evidence: both are real design campaigns needing their own
  closed-loop re-characterization, and nothing in the committed data ranks them
  against each other. Decision 2 narrows Decision 7's four loci to the one
  quantity any of them must move (`q_zero` at low Vctrl); choosing the mechanism
  is filed, not guessed.

- **Leave the `derive_op_points` deviation alone, since it agrees with the rule
  at 14 of 15 cells.** Rejected: the one cell it disagrees at is the cell
  carrying the grid's largest settled violation of a ratified criterion, which
  is the whole finding. A selector that silently departs from a normative rule
  measures a configuration no compliant part carries, and the next re-take of
  this campaign — #437's trimmed-window full-grid run — would reproduce the
  same off-rule cell.

## Consequences

- **`spec/pll.md` changes in two places.** The [Lock criterion] row of
  [Verification owed](../pll.md#verification-owed) is restated per Decisions 4,
  5 and 6 and re-pointed off the closed #394 onto this record and #511, with
  item (b)'s cell named. Row 9 ([Lock time](../pll.md#lock-time)) keeps its
  **not met** status and its `< 100 µs` target, with the corner attribution
  corrected. **The Lock criterion's own normative text is unchanged** — that is
  Decision 1, and the [Band-selection rule](../pll.md#band-selection-rule)
  section's normative text is unchanged too.

- **A design gap previously stated as "2 of 45 corners" is now stated as "1 of
  45 measured at a compliant configuration, 1 of 45 owed".** That is a *weaker*
  claim than the spec carried yesterday, and it is the reason this record states
  its own limitations at length: the 1.227 ns is not withdrawn, is not
  re-judged, and is not explained away — it is relocated to a configuration the
  rule does not select, and the rule-selected replacement is owed. If that run
  comes back over the bound, the count returns to 2 and nothing in this record
  needs revising except this sentence.

- **`sim/supply-sensitivity` changes what it measures at one cell.**
  `derive_op_points` now applies the normative rule, so a future run puts
  `ff`/27 °C on band 5 at 1.967–2.595 V instead of band 6 at 1.008–1.394 V. Every
  cached run under `work/` for that cell is invalidated by the parameter change
  (the `.sig` guard handles this), and the re-run is **expensive** — of order
  3.2 h of ngspice per corner at the unescalated length. The other 14 cells are
  bit-identical in their parameters and re-use their cache.

- **The 3.63 V arm of the rule-selected `ff`/27 °C cell is off the bottom of
  nothing and off the top of the measured offset grid.** 2.595 V is inside
  DR-003 Decision 5's measured 0.9–2.7 V window with 105 mV of margin, but
  outside `sim/pfd-deadzone`'s 0.90–2.40 V sweep and outside DR-001 Decision 2's
  predicted window. Anyone citing a systematic term there has nothing to cite;
  extending that campaign's control-voltage axis to the measured window's top is
  a second, smaller owed measurement this record surfaces and does not close.

- **An ambiguity in a normative rule is now written down and unresolved.**
  `spec/pll.md`'s band-selection rule does not name the control window "reaches
  `f`" is evaluated over, and the answer at `ff`/27 °C / 100 MHz changes with
  the choice. This record reports it under both readings and uses the measured
  one; making the window normative is filed separately (see Decision 6's
  Alternatives entry) because it governs every campaign's operating-point
  derivation, not only this one.

- **A structural property of the band map is exposed that no row tracks.** At
  f_out = 100 MHz, 4 of the 15 (bundle, temperature) cells have **no single
  static band code** that reaches the target across the ratified ±10 % rail
  inside DR-001 Decision 2's predicted 0.9–2.4 V window; across the swept output
  band, 2 (f_out, cell) pairs have none inside the *measured* 0.9–2.7 V window
  either. Band select has no calibration FSM (DR-001 Decision 2), so this is a
  property of the shipped part, not of a search. It is consistent with — and
  independently reproduces — `20260925-044237-4ff4f65`'s criterion-1b finding,
  and it is not otherwise owned.

- **What is still not known, stated plainly**: whether the loop meets the
  criterion at the rule-selected `ff`/27 °C cell; whether it meets it at the
  named low-parked cell (f_out = 135 MHz, `ss`/125 °C); where the 15 unsettled
  over-bound corners settle (#399); and the post-extraction value of any of it
  (#18). Decision 2 bounds the problem's *shape* — the band map cannot solve
  it — not its size.
