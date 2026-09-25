# DR-029: The symmetric `REF` phase-step bisection does not execute the lock-detector window trim rule — a locked loop cannot be asked to hold the error the flag measures

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009, DR-010,
  DR-011, DR-013, DR-014, DR-015 and DR-022 record (a builder drafts the record
  on the evidence; the operator's PR approval is the ratifying act). Status
  stays `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #527
- **Numbering note**: `DR-027` is claimed by open PR #535 (unmerged) and
  `DR-028` was taken by #536's batch-image record while this one was being
  written, so this record takes `029`, per the collision rule in
  `TEMPLATE.md` and the precedent DR-028's own numbering note sets. If PR
  #535 is abandoned, `027` stays an unused gap — `DR-NNN` is a stable
  identifier, not a dense sequence.
- **Revises**: `spec/pll.md`'s
  [Executing the rule at test](../pll.md#executing-the-rule-at-test--the-rule-is-normative-and-on-this-die-it-is-executable-only-in-simulation)
  subsection — closes out the first of the two routes DR-022 Decision 5 named,
  with a measured negative result, and makes the second the successor. **The
  trim rule itself is not relaxed and nothing here makes an untrimmed part
  conforming**: the measurand, the reference condition and the 1.343 ns target
  are unchanged, and DR-022's own conclusion — the rule is executable only in
  simulation on this die — is strengthened, not weakened.
- **Consumes**: DR-022 Decision 2 (the two-tier accuracy bound this route is
  graded against, **and its corollary** — a flag-referred route must not divide
  by a fixed 1.037×), Decision 5 route 1 (the route characterized here) and
  Decision 5 route 2 (the successor); DR-013 Decision 1 (the observable is the
  flag's assert window, not the bare chain delay) and Decision 4 (the ≤ 1.65×
  spread target); DR-014 (the trim mechanism); DR-015 (four dedicated trim
  pins, no observation output); DR-026 (`LDT3` is connected at `pll_top`, so all
  16 codes are reachable — DR-022 Decision 6's precondition, now met).
- **Evidence**:
  - `sim/lock-window-bisection/records/20260925-162032-e341b58.md` — the campaign this
    record is written on, filed by #527. A closed-loop `pll_top` phase-step
    ladder at the trim rule's own reference condition (27 °C, 3.30 V), three MOS
    bundles at the three distinct codes the rule selects, both step directions.
  - `sim/lock-window-proxy/records/20260925-050022-6d57802.md` — the committed
    16-code window map the reference `t_win` at every graded point comes from,
    and DR-022's own evidence.
  - `sim/lock-detector/records/20260919-002812-1b12179.md` — the 205-point
    in-situ characterization the flag-to-chain excess δ (+1.4 … +7.0 %) and the
    5.63 ns worst deassert latency come from.
  - `sim/supply-sensitivity/records/20260901-155456-46b92f8.md` — the 45-point
    steady-state grid this campaign's operating point and warm-start seeds come
    from, and the only committed closed-loop evidence in this tree that the flag
    **asserts** in steady state across the MOS bundles at 27 °C / 3.30 V.

## Context

DR-022 established two things and deliberately left a third open. The trim
rule's measurand is internal (`t_win`, the `ERR` → `ERRD` delay of
`delaywin_3v3`; neither node is a port of `pll_top`), no quantity the present
pads expose selects the code to the accuracy the design's own verdicts assume,
and **two** routes might still close the gap. Its Decision 5 named them and
authorized neither: (1) a symmetric `REF` phase-step bisection read at the
`LOCK` pad, needing no design change and no new pad, owed a characterization at
#527; (2) exposing `ERR`/`ERRD` through matched observation buffers onto free
digital-test-output slots, a design change needing its own decision record.

Route 1 was the one to try first, and DR-022 said exactly why it was a
candidate and not a decision: *nothing had measured it.* This record is that
measurement. It is written as a negative result, which DR-022 Decision 5
anticipated as one of the two outcomes and which the issue that owns it calls
"equally valuable".

## Decision

### Decision 1 — The deassert is observable at the `LOCK` pad, promptly and unambiguously

The first of issue #527's four method-validity questions is answered **yes**,
and cleanly. At `typical`/27 °C/3.30 V with the loop locked at the rule's own
code 7, the detector's integrator sits at **3.2865 V** of a 3.30 V rail before
the step — so `LOCK` is asserted with the full stored charge behind it — and at
every step magnitude past threshold `LOCK` falls to ground **80.3 … 163.1 ns**
after the step (one to two reference periods at f_ref = 12.5 MHz) and stays
there for **1.04 … 1.37 µs**, while `VWIN` falls 2.65 … 3.28 V. Nothing about
the reading is marginal: there is no intermediate state, no chatter, and the
dip is three to four orders of magnitude longer than a sampling instant.

One correction to a number a reader might otherwise carry into a test program:
`spec/pll.md` records a worst deassert latency of **5.63 ns**, measured through
the block-level loop on a *large* perturbation. Near the threshold the latency
is one to two reference periods, not nanoseconds — the integrator needs whole
reference cycles to remove the stored charge when the excess is small. The
5.63 ns figure is not wrong; it is the large-signal case, and a tester must
budget the reference-period-scale number instead. This
matters beyond this route: it is the same observability DR-022 Decision 5
route 2 would rely on, and it is the first time the flag's deassert has been
read at `pll_top`'s own output rather than through the block-level loop
`sim/lock-detector` measures.

### Decision 2 — The threshold in Δ is not `t_flag`, and the difference is not a constant that can be calibrated away

Measured at the trim rule's own reference condition, `typical`/27 °C/3.30 V,
at the code the rule selects there (7):

| Quantity | Value |
|---|---|
| Θ₊ (REF retarded) | bracketed: held at 2.0 ns, dropped at 2.4 ns → **2.200 ± 0.200 ns** |
| Θ₋ (REF advanced) | bracketed: held at 2.0 ns, dropped at 2.4 ns → **2.200 ± 0.200 ns** |
| `t_flag` the procedure returns, (Θ₊ + Θ₋)/2 | **2.200 ± 0.200 ns** |
| `t_flag` the committed evidence supports, `t_win × [1.014, 1.070]` | **1.3769 … 1.4529 ns** |
| Discrepancy | **+55.5 %** over the interval's midpoint; outside the interval entirely |
| One trim code here, at the measured 3.56 % geometric step | **50.4 ps** |
| Code error a tester would land at | **−12.62 codes** (−13 rounded) |
| …of which the ladder's own resolution | ±4.04 codes |
| …of which the reference interval's own width | ±0.77 codes |
| **DR-022 Decision 2 Tier A** (−2 … +3 codes) | **FAIL** |
| **DR-022 Decision 2 Tier B** (zero codes) | **FAIL** |

The discrepancy is 0.747 ns — **3.7× the threshold bracket's own half-width and
19× the half-width of the reference interval**. Neither uncertainty is what
decides this: a ladder ten times finer and a flag window measured to a
picosecond would move the number by well under a code, against a bias of
thirteen. `LDT3:LDT0` has sixteen codes; an error of thirteen means a tester
executing this procedure on a `typical` part would drive the trim to its rail.

The other two bundles returned **no threshold at all**, for a reason that is
itself a constraint on the route: their flag was never asserted to begin with.
At the step instant `ff` sat at a **−1.760 ns** static offset and `ss` at
**+1.604 ns**, each wider than its own rule-selected window (1.363 ns at code
11, 1.356 ns at code 3), so `LOCK` was correctly low and every rung merely
re-observed an already-low flag. Every one of those six points carries a
`FAIL — lock_pre` verdict in the record. **This is a property of the run, not
of those bundles**: the pre-step window is long enough for the detector's
integrator to reach the rail but not for the loop's slowest pole, and
`sim/supply-sensitivity`'s committed 12 µs grid settles the same operating
point far below those values. What it does establish — independently of how
long anyone waits — is that the procedure can only be executed on a part that
is already inside its own window at the chosen operating point, which this
design is not everywhere (DR-012, DR-025).

**Why, in terms of the circuit rather than of the number.** The flag's assert
window and a phase-step threshold are answers to two different questions about
the same integrator, and the ratio between them is set by quantities that have
nothing to do with the delay chain the trim moves.

`VWIN` is a `6u × 30u` `nfet_03v3` MOS capacitor, charged by a pfet of
`W/L = 0.22u/20u` — a current source of order a microamp — and discharged by an
nfet of `W/L = 2u/0.5u`, three orders of magnitude stronger, gated by
`WIDE = ERR · ERRD`. `ERR` is high for the phase error |φ| each reference
cycle and `ERRD` is `ERR` delayed by `t_win`, so `WIDE` is high for
`max(0, |φ| − t_win)`.

- **`t_flag` is a per-cycle charge balance.** DR-013 Decision 1 defines the
  observable as the largest phase error for which `LOCK` asserts *and stays
  asserted*, i.e. the largest **sustained** |φ| for which the weak pull-up's
  charge per reference period still covers the discharge:
  `I_up · T_ref ≥ I_dn · (|φ| − t_win)`. That gives
  `t_flag = t_win + I_up·T_ref/I_dn` — a small additive excess over `t_win`,
  which is exactly the δ `spec/pll.md` measures at +1.4 … +7.0 %, and which is
  proportional to `T_ref` (the reason `spec/pll.md` flags T4/T5 as
  uncharacterized below 25 MHz is the same absolute-time mechanism).
- **A step threshold is a stored-charge question.** Before the step `VWIN` sits
  at the rail. The step raises the error to `|φ_ss ± Δ|` for only the handful of
  reference cycles the loop needs to absorb it, and `LOCK` drops only if the
  *integrated* discharge over those cycles exceeds
  `C_VWIN · (V_rail − V_TL)` — the charge stored between the rail and the
  Schmitt trigger's falling threshold.

So the step threshold is `t_win` plus an additive time set by `C_VWIN`,
`V_rail − V_TL`, `I_dn` and the number of excess cycles the loop's own
bandwidth leaves available. **Not one of those four is the delay chain.** They
move across process, temperature and supply independently of `t_win`, which is
why the discrepancy cannot be removed by any fixed factor — the same objection
DR-022 Decision 2's corollary raises against dividing by 1.037×, one order of
magnitude larger and with four independent contributors instead of one.

### Decision 3 — The ± cancellation is not what failed, and this cell cannot test it

Issue #527's third question — does the ± cancellation survive the loop's own
asymmetric UP/DN correction — is **not answered here, and is moot**.

The algebra is sound and the measurement is consistent with it: the two
directions' thresholds differ by `2·φ_ss`, and `(Θ₊ + Θ₋)/2` is independent of
`φ_ss` by construction. Measured at `typical`, the symmetric pair returns
`φ_ss = (Θ₋ − Θ₊)/2 = 0.000 ± 0.200 ns` against a directly-measured static
offset of **0.1327 ns** (cross-checked from the PFD's UP/DN pulse-width
difference at 0.110 ns, and stationary to 10.8 ps over the ten reference cycles
before the step). The two are consistent, and that is all that can be said:
the ladder's ±200 ps bracket is larger than the 133 ps it would have to
resolve, so this cell **cannot** distinguish a perfect cancellation from a
badly broken one. Resolving it would need a ladder an order of magnitude finer
at a cell whose static offset is an order of magnitude larger.

But the cancellation was never the weak part of route 1. Even a
*perfect* cancellation returns the step threshold, and Decision 2 is that the
step threshold is the wrong quantity. A future record that resolves the
cancellation to a picosecond would not change this record's verdict.

### Decision 4 — The route is not viable, and the obstacle generalizes to the whole class of `REF`-side procedures

The flag's measurand is a **sustained** phase error. A locked loop, by
construction, refuses to hold a sustained phase error of anyone's choosing: it
holds exactly its own `φ_ss` and corrects everything else. `REF` is the only
end of the loop a tester drives, and `FB` is an output with no input path
(DR-015 chose four trim *inputs* and §2.2's pad list has no `FB` drive), so
every `REF`-side stimulus is a **transient** — and the flag's response to a
transient is governed by the integrator's stored charge and the loop's own
correction speed, not by the delay chain.

Two variants that look like escapes are not:

- **A phase ramp instead of a step.** The loop's filter is integrating, so its
  steady-state phase error to a frequency offset is zero: a ramp produces no
  sustained error either, only a transient one whose size is set by the ramp
  rate against the loop bandwidth — the same two non-chain quantities.
- **Solving out the additive term with a second measurement** (two steps at two
  f_ref, or at two supplies, and eliminating it). That requires the
  `C_VWIN`/`V_TL`/`I_dn`/loop-bandwidth combination to be stable across the
  process population. It is not — each term has its own corner dependence — so
  this would be a fit against a model, not a measurement, and DR-022
  Decision 2's Tier B leaves no allowance for a fit's residual.

**Therefore DR-022 Decision 5 route 2 — an output-side observation point for
`ERR`/`ERRD` — is the successor**, exactly as DR-022 said it would be if #527
returned a negative result. This record does **not** authorize it: it is a
design change, and DR-022 already requires it to have its own decision record
first. What this record adds to that future record's case is the one thing it
could not have had before: route 1 is measured, and it is not a matter of
resolution or of a better bisection.

### Decision 5 — What this record does not close, stated so it is not read as more than it is

1. **The grid.** This is a declared three-bundle subset at 27 °C / 3.30 V — the
   trim rule's own reference condition, which is where a tester executes it —
   at one (f_ref, N) cell. The full worst-code-error grid over temperature and
   supply is **not** run, and issue #527's own cost note is why: it is worth
   buying only if the method-validity questions come back clean, and Decision 2
   is that they do not. A grid would refine a number whose sign and order of
   magnitude are already decided.
2. **f_ref dependence.** Not measured. Decision 2's balance relation makes
   `t_flag`'s excess over `t_win` proportional to `T_ref`, so the *flag window
   itself* widens at lower f_ref — which is a statement about the detector, not
   about this route, and it is the same mechanism behind `spec/pll.md`'s open
   T4/T5 item. This record does not discharge that item and does not touch it.
3. **The `LOCK` output driver.** `design/` contains no output pad driver for
   `LOCK`, `FB` or `DIVOUT` (`CLK` alone is buffered). A tester's threshold
   carries that driver's delay on top of everything here. It does not rescue
   the route — a driver delay common to both directions cancels, and one that
   does not is an extra error — but no record here bounds it.
4. **Extraction and mismatch.** Schematic-level, `sw_stat_global =
   sw_stat_mismatch = 0`. Extraction (#18) moves the integrator's capacitance
   and the chain's ~1 fF trim segments by different factors, which changes
   Decision 2's ratio but not its sign: the additive term is not zero and is
   not proportional to `t_win`.
5. **The loop's settled static offset.** The pre-step window is long enough for
   the detector's integrator to reach the rail but not for the loop's slowest
   pole (τ ≈ 9.3 µs, `sim/loop-dynamics`); the offset measured at the step
   instant is smaller than the settled value `sim/supply-sensitivity` reports at
   the same operating point. This does not move `(Θ₊ + Θ₋)/2`, which is
   independent of `φ_ss` by construction, and it is reported as a measured
   number (`phi_drift`) at every point rather than assumed away. It does mean
   the individual thresholds Θ₊ and Θ₋ would sit further apart on a fully
   settled loop while their mean stayed put.

## Alternatives considered

- **Report "inconclusive, needs a finer ladder".** Rejected on the measurement:
  the discrepancy is **+55.5 %** of the flag window, 3.7× the threshold
  bracket's own half-width, 19× the reference interval's, and thirteen codes
  past what Tier B allows. A finer ladder would resolve the threshold better
  and would not move it toward `t_flag`.
- **Grade the route against `t_win` through a fixed 1.037×** — the conversion
  the rule's own target embeds. Rejected because DR-022 Decision 2's corollary
  forbids it, and for a reason this record's evidence does not depend on: the
  ratio's own 1.055× spread is worth 1.2–2.0 codes. The grading here is against
  the *interval* `t_win × [1.014, 1.070]`, which is what committed evidence
  actually supports, and the reference interval's own width is reported in codes
  beside the measurement's so a reader can see which uncertainty dominates. It
  is not the reference's width that decides this: the measurement sits outside
  the interval by many times its own width.
- **Keep route 1 open as a "future work" item.** Rejected as the worse of two
  honest options. Decision 4's obstacle is structural — the measurand is a
  sustained error and `REF` cannot impose one — so leaving the route nominally
  open would leave `spec/pll.md` implying a cheaper path exists than the one
  that does. Naming route 2 as the successor is the actionable statement.
- **Take DR-022's route 2 here, in this record.** Rejected: DR-022 already
  requires it to carry its own decision record, it is a `design/` change to a
  block whose layout is committed, and the loaded-cell re-derivation of the
  1.343 ns target it forces is a measurement this record has not made. A
  negative result on one route does not authorize the other.

## Consequences

- `spec/pll.md`'s [Executing the rule at test] subsection loses its closing
  "two routes could still close this" sentence and gains a measured disposition:
  route 1 is closed with a negative result, route 2 is the successor and still
  needs its own decision record, and DR-022 Decision 6's `LDT3` precondition is
  discharged (DR-026).
- The [Lock detector] row's conditionality is **unchanged in substance and
  narrowed in prospect**: its T1′/T2′ verdict still rests on a trim no bench or
  tester procedure can select, and the set of candidate procedures is now one
  smaller and the remaining one costs a design change.
- No `sim/` record is superseded. `sim/lock-window-bisection` is a new campaign
  whose first record stands on its own; DR-022's evidence is untouched.
- A new campaign directory, one record, and the counts in `README.md` and
  `sim/CHARACTERIZATION.md` move with it.
- The off-host batch execution path this campaign's 45-rung ladder was shaped
  for **refused every job** (`only 0 subnet/AZ(s) resolved, floor is 3`), which
  is why the recorded ladder is 13 rungs run locally at `-j 2` rather than 45
  run off-host. That is an execution-layer fault outside this repository, not a
  harness or manifest defect: `sim/run_corners.py lock-window-bisection
  --backend batch` shapes all 45 jobs correctly and is re-runnable the moment
  the layer resolves subnets again. It is recorded here because it is the reason
  a reader will find fewer points than the manifest was written for.
- **The local fallback was not purely a loss, and DR-028 is why.** That record
  (#536) establishes that the batch job image runs **ngspice-42** against this
  repository's ngspice-46 pin, and that a batch-executed record must disclose
  the divergence. Every point here ran on the pinned **ngspice-46**, so this
  record carries no such divergence — an off-host run of the same 45-rung
  ladder would have, and a re-take that takes the batch path must read DR-028
  before quoting these numbers alongside its own.

[Executing the rule at test]: ../pll.md#executing-the-rule-at-test--the-rule-is-normative-and-on-this-die-it-is-executable-only-in-simulation
[Lock detector]: ../pll.md#lock-detector
