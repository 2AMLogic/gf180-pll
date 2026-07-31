# DR-002: Draft-spec scope ratification — reference mode, output ceiling, supply/device flavor, lock detector, jitter claim

- **Status**: Proposed (scope decisions, pending engineering ratification
  through the same governance path as the target spec — see #1). The jitter
  decision (Decision 5) is additionally marked *proposed, not ratified* on
  its own terms per #7's acceptance criteria, since it is an a priori
  assessment that precedes #13's actual jitter measurement and may be
  superseded by that evidence.
- **Date**: 2026-07-30
- **Decided by**: Builder agent, issue #7
- **Related**: #1 (spec ratification — consumes this record), #3 / DR-001
  (PLL architecture selection — this record cross-checks against DR-001's
  own "Sensitivity to the open spec questions in #7" section and is
  consistent with its recommendations), #6 (decision-record template — this
  record follows it), #11 (feedback divider and output path — consumes
  Decisions 2 and 4), #12 (testbench scope — consumes Decisions 2 and 4),
  #13 (jitter testbench — consumes Decision 5 and may supersede it)

**Format note.** One combined record for all five scope questions (plus the
output-divider sub-question absorbed into Decision 2), following the
precedent DR-001 already set in this repo for bundling multiple related
decisions in one record when the questions are tightly coupled and the
total content is well under the one-page-per-question guideline. Unlike
DR-001's three decisions (which are mutually constraining), these five are
mostly independent business/scope calls rather than one coupled
engineering choice — but they share a single theme (draft-spec scope
ratification ahead of #1) and are recorded together for the same reason
DR-001 gives: nothing downstream should re-litigate these per-block.

---

## Decision summary

| # | Question | Decision | Consumed by |
|---|---|---|---|
| 1 | Reference input / 32 kHz mode | **Stretch-only, deferred out of v1.** v1 reference range is 1–25 MHz. The 32 kHz mode is not a v1 commitment. | #1, #8, #9, #11 |
| 2 | Output ceiling / output-divider scope | **v1 design margin is budgeted to 200 MHz (the target), not 400 MHz (the stretch).** No post-VCO output-divider stage is in v1 scope — the VCO's own band-switched tuning range is relied on to cover 10–200 MHz directly, pending #8's extracted confirmation (see caveat below). | #1, #8, #11 |
| 3 | Supply / device flavor | **1.8 V core variant is formally deferred past v1.** v1 device-flavor commitment is the gf180mcu **3.3 V thick-oxide** flavor (`nfet_03v3`/`pfet_03v3`) exclusively — no dual-flavor design. | #1, #8, #9, #11 |
| 4 | Lock indication | **A lock-detector output IS in v1 scope**, implemented as a simple frequency/phase-error window comparator producing a digital `lock` status pin — explicitly NOT bundled with any auto band-calibration FSM (that stays out of v1 per DR-001). | #11, #12 |
| 5 | Jitter claim | **Ratify period jitter (RMS) as the spec'd, simulation-substantiable quantity** via a VCO-dominated transient-noise testbench. Any phase-noise or integrated-jitter figure is treated as *derived*, not spec'd, until the flow demonstrably produces it. Status: **proposed**, not ratified — precedes #13's actual measurement. | #1, #12, #13 |

Everything below is context and rationale per decision. As in DR-001: numbers
here are used to disposition scope, not to size circuits — #8/#9/#11/#12 own
the real sizing and measurement.

---

## Context

The README target-spec table (`README.md` → "Target specification") is
explicitly marked DRAFT and bundles five scope questions whose answers each
have concrete, divergent downstream impact on device selection, testbench
design, and layout work (original issue text, #7):

- Reference input: is the 32 kHz mode stretch-only, or required for v1?
- Output ceiling: is v1 design margin budgeted to 200 MHz (target) or must
  it also cover 400 MHz (stretch)?
- Supply: is the 1.8 V core variant formally deferred, and which gf180mcu
  device flavor (3.3 V thick-oxide vs. dual) is the v1 commitment?
- Lock indication: lock time < 100 µs is spec'd but no lock-detector output
  is listed — is a lock detector in v1 scope?
- Jitter claim: which jitter number is simulation-substantiable given
  ngspice's phase-noise/transient-noise limits?

A sixth, implicit question surfaced by #11 ("output dividers only if #7/#1
put them in scope") is folded into Decision 2 below.

Nothing downstream should re-litigate these per-block — they are decided
once, here, feeding #1's ratification, exactly as DR-001 already does for
the architecture-survey side of the same DRAFT table. DR-001 (written
against this same table, one day prior) already worked through most of
these questions in its own "Sensitivity to the open spec questions in #7"
section, as a side effect of stress-testing its architecture choices
against the open scope questions. This record is the authoritative,
purpose-built answer to each question; where it agrees with DR-001's
sensitivity analysis, that agreement is cross-checked and cited, not
re-derived from scratch.

---

# Decision 1 — Reference input / 32 kHz mode

## Decision

**32 kHz mode is stretch-only and deferred out of v1 scope.** The v1
reference-input range is **1–25 MHz** exclusively. The README stretch
column's "32 kHz mode" is recorded as a future, separately-scoped option —
not a v1 commitment, and not a target design margin has to reach.

## Alternatives considered

- **Required for v1 (32 kHz mode a hard commitment).** Rejected. DR-001's
  own sizing sanity check (§Decision 1) shows two independent problems: (a)
  32.768 kHz × the max multiplier (×64) is ~2.1 MHz, below the 10 MHz output
  floor — the "Ref: 32 kHz" and "Multiplier: ×4–×64" rows cannot both be v1
  as drafted, so N would have to span ~305–6100, not 4–64, which is a
  different divider (~13 ÷2/3 cells vs. 6) and a different loop-filter
  sizing regime entirely; (b) restoring damping at the resulting sub-kHz
  loop bandwidth needs single-digit-nF loop-filter capacitance — roughly
  0.9 mm², about 6× the entire 0.15 mm² area budget on its own. Lock time in
  that mode would also land in the hundreds of µs to ms, violating the
  < 100 µs spec line. Making this v1 would silently invalidate three other
  spec lines (multiplier range, area, lock time) at once.
- **Scope 32 kHz as a separate low-N configuration with its own spec row.**
  Considered as a middle path (also named in DR-001). Rejected for v1 on
  cost: it still requires the active-filter/cap-multiplier/dual-loop
  mitigation DR-001 names, which is a second loop-filter design and
  verification effort layered onto the canary's first pass. Worth
  revisiting as a v2 derivative once the primary 1–25 MHz design is
  measured, not before.
- **Stretch-only, deferred (this decision).** Accepted. Matches the
  README's own Target/Stretch framing (32 kHz is listed under Stretch, not
  Target), avoids the three-spec-line collision above, and keeps the
  divider and loop-filter sizing in #9/#11 to the single regime DR-001
  already designed against (N = 4–64, fixed passive filter).

## Consequences

**In scope now:**
- Feedback-divider N range for #11 is 4–64 (DR-001 Decision 3's 6-cell
  ÷2/3 chain), not the ~305–6100 range a 32 kHz mode would require.
- Loop-filter sizing for #9 targets the single fixed-filter regime DR-001
  sized against; no active filter, cap multiplier, or dual-loop scheme is
  needed for v1.
- The lock-time spec (< 100 µs target, < 20 µs stretch) applies only over
  the 1–25 MHz reference range. DR-001 already notes the 20 µs stretch is
  not met at the low end of even that range with a single fixed filter —
  that is a separate, already-flagged risk, unrelated to this decision.

**Explicitly deferred (not decided here):**
- A future 32 kHz-capable mode or variant remains a possible stretch/v2
  goal, exactly as the README already frames it. If pursued, it needs its
  own issue and decision record (active filter or dual-loop architecture,
  a widened divider, and a relaxed or mode-specific lock-time spec) — this
  record does not commit to it, schedule it, or imply timing.

---

# Decision 2 — Output ceiling and output-divider scope

## Decision

**v1 design margin is budgeted to 200 MHz (the target), not 400 MHz (the
stretch).** Every block's headroom, corner analysis, and verification plan
targets the 10–200 MHz output band; the 400 MHz stretch is an explicitly
lower-priority reach goal, not a design constraint that must be met without
compromise.

**No post-VCO output-divider stage is in v1 scope**, by default. DR-001
Decision 2 already commits the VCO to a 5-stage, current-starved,
band-switched ring with a 3-bit band code sized to cover the full 10–200 MHz
(20:1) range on its own — the band plan was deliberately sized to reach the
output floor and ceiling directly, not to rely on a downstream divider. An
output divider is unnecessary complexity (extra custom cell, extra power,
extra jitter-injecting logic in the signal path) if the VCO's own tuning
range in fact reaches 10 MHz at the low end across corners.

**Caveat — this is conditional on #8's evidence, not a final answer.**
DR-001's band-plan sizing is a hand-calculation disposition, not corner-swept
extracted data. If #8's actual `f(Vctrl)` extraction shows the ring's
band-overlap or low-band floor does not reach 10 MHz across all PVT corners
(a real risk at the slow corner, where ring delay is longest and the lowest
band's *floor*, not headroom, is what is being tested), then an output
divider becomes in-scope by this same decision's own logic — it is the
standard fix for "VCO can't tune low enough," and #11 should treat that as
the documented fallback trigger, not a fresh scope negotiation. This
condition is recorded explicitly per #7's acceptance criteria (do not leave
a silent gap): **default is no divider; the trigger is #8 showing a band-plan
shortfall at the low end.**

## Alternatives considered

- **Budget margin to 400 MHz (the stretch) as if it were the v1 target.**
  Rejected. This is exactly the ambiguity the original issue text flags
  ("confirm design margin is budgeted to the target, not the stretch").
  DR-001 already shows 400 MHz is not a delay-cell crisis in isolation (a
  5-stage ring at 400 MHz needs only 250 ps/stage, achievable in 3.3 V
  gf180mcu) but treating it as the binding target would consume 6 of 8
  coarse bands, push the pseudo-differential delay cell (DR-001's
  closest-call rejected alternative) back into contention, and force the
  first ÷2/3 divider cell to close timing at 400 MHz rather than 200 MHz at
  the slow corner — margin the spec does not actually require for v1.
- **Always include a post-VCO output divider (defensive, in-scope
  unconditionally).** Rejected as premature. Adding a divider before #8's
  data exists would spend area/power/verification budget against a risk
  that has not been confirmed, and DR-001's band plan was specifically
  sized to avoid needing one. Revisit only on the evidence trigger above.
- **No output divider, unconditionally, regardless of #8's findings.**
  Rejected — this would leave #11 with a silent gap if the VCO tuning range
  does turn out to have a hole, which is exactly what #7's acceptance
  criteria warns against. The conditional decision above is preferred.

## Consequences

- #8's corner-swept band-overlap/floor extraction is now load-bearing for
  more than DR-001's own architecture choice — it also disposition's this
  record's output-divider default. #8 should explicitly call out the
  low-band floor at the slow corner as a pass/fail check against the
  10 MHz spec line, not just band-overlap continuity.
- #11's deliverable is "feedback divider only" for v1 under the default
  branch; an output-divider stage is added scope only if #8 trips the
  trigger above, at which point #11 should treat it as an addendum to this
  record rather than a fresh scope question.
- 400 MHz stretch capability is preserved as a *documented* reach (DR-001's
  3-bit band code and swappable first divider cell already keep the door
  open) without being a v1 verification requirement.

---

# Decision 3 — Supply / device flavor

## Decision

**The 1.8 V core variant is formally deferred past v1.** The v1 device-flavor
commitment is the gf180mcu **3.3 V thick-oxide flavor** (`nfet_03v3` /
`pfet_03v3`) exclusively, at the already-specified 3.3 V ±10% supply. No
dual-flavor (3.3 V + 1.8 V, or 3.3 V + 5 V) design work is undertaken in v1.

This mirrors the sister repo's analogous scope decision
(`2AMLogic/gf180-bandgap` `spec/decision-records/0001-supply-voltage-scope.md`,
"3.3V-only for wave 1") applied to this block's own draft-spec ambiguity —
cited for precedent and rigor level only; no content from that repo's
specifics is reproduced here beyond the pattern.

## Alternatives considered

- **1.8 V core variant in v1 (dual-flavor or 1.8 V-only).** Rejected. DR-001
  already quantifies why: at 1.8 V, a threshold-plus-degeneration drop eats
  roughly a third of the rail, the usable Vctrl range for DR-001's
  source-degenerated V→I converter collapses, and recovering the same
  tuning range drives Kvco up — which drives the fixed passive filter's C1
  up quadratically (DR-001 Decision 1's sizing). Supporting it would force
  DR-001's rejected supply-regulated-ring alternative back into play, plus
  a level-shifted charge pump and possibly an active filter — effectively a
  different block, not a variant, exactly as DR-001's own recommendation to
  #1 already states.
- **Dual 3.3 V / 5 V-flavor device commitment.** Rejected. DR-001 Decision 3
  already notes the two open standard-cell libraries for this node
  (`gf180mcu_fd_sc_mcu7t5v0`, `gf180mcu_fd_sc_mcu9t5v0`) are 5 V-flavor, and
  a 3.3 V analog core cannot simply reuse them without a level-shift/
  domain-crossing problem across every custom digital cell (divider, and
  now the Decision 4 lock detector). Committing to dual-flavor for v1 would
  roughly double the device-qualification, testbench, and layout-rule
  scope of the very first canary block — directly against the goal of
  fastest time to a measured shuttle result.
- **3.3 V thick-oxide only for v1, others formally deferred (this
  decision).** Accepted. Matches DR-001's existing assumption
  (`nfet_03v3`/`pfet_03v3` throughout, stated in its Context section) and
  the README's own Target/Stretch framing (1.8 V core listed as Stretch,
  not Target), so this decision promotes an already-implicit choice to an
  explicit, recorded one rather than introducing a new constraint.

## Consequences

**In scope now:**
- Single device-flavor qualification (Vgs/Vds ratings, models) across
  every block: VCO (DR-001 Decision 2), PFD/charge pump/filter (#9),
  divider (DR-001 Decision 3), and the new lock detector (Decision 4
  below) — all `nfet_03v3`/`pfet_03v3`.
- A single 3.3 V ±10% PVT corner matrix (per CLAUDE.md's −40/27/125 °C ×
  supply × process corners) is sufficient; no separate 1.8 V or 5 V corner
  sweep is required for v1.
- DR-001's architecture (fixed passive filter, current-starved ring,
  static-CMOS divider) remains valid as designed — none of its
  device-flavor assumptions need revisiting.

**Explicitly deferred (not decided here):**
- A future 1.8 V-core variant or dual-flavor version remains a possible
  stretch/derivative product, exactly as the README already frames it. If
  pursued, it is scoped as its own issue and decision record (with DR-001's
  fallback architecture: supply-regulated ring, level-shifted charge pump,
  possibly active filter) — this record does not commit to it, schedule
  it, or imply timing.

---

# Decision 4 — Lock indication

## Decision

**A lock-detector output IS in v1 scope.** The block exposes a digital
`lock` status output, implemented as a simple frequency/phase-error window
comparator (e.g., monitoring PFD up/down pulse width or a frequency-error
window around the divided feedback edge) that asserts once the loop has
settled within a defined phase/frequency error band and stays asserted while
it remains there.

This is explicitly **not** bundled with any automatic band-search or
self-calibration FSM. DR-001 Decision 2 already commits v1 to a **static**
band-select input with no auto-calibration FSM, and that stance is
preserved here unchanged — the lock detector is a passive monitor, not a
corrective actuator, and does not imply or require the FSM DR-001 explicitly
keeps out of v1.

## Alternatives considered

- **No lock detector in v1 (defer it).** Considered, on the reasoning that
  lock time can be verified in simulation by directly observing loop
  settling (e.g., Vctrl or divided-feedback phase settling in a transient
  run) without any dedicated on-chip circuit, and that DR-001's "no
  calibration FSM in v1" stance might argue against adding related
  hardware. Rejected: a PLL macro with no externally observable lock status
  is materially harder to integrate — a system consuming this block's clock
  has no way to gate downstream logic on lock without re-running the
  testbench-level analysis itself. The area/power cost of a window
  comparator is small relative to the calibration FSM DR-001 rejects (no
  state machine, no counter, no band-search logic — just a comparator on
  an existing PFD signal), so the "no calibration FSM" cost argument does
  not transfer to a simple monitor.
- **Full lock detector + automatic band-search FSM.** Rejected for v1 —
  this is the scope DR-001 Decision 2's Consequences section explicitly
  flags as "the natural next step" if a lock detector is pulled into scope,
  and explicitly declines to take that step for the same reasons DR-001
  keeps the calibration FSM out of v1 (a digital FSM block with no matching
  3.3 V standard-cell library, per DR-001 Decision 3's device-flavor
  argument). This decision deliberately draws the line at the passive
  monitor, not the corrective loop.
- **Lock detector as a simple monitor, no FSM (this decision).** Accepted.
  Gives #11/#12 an unambiguous, low-cost v1 deliverable and an externally
  observable signal that strengthens (does not replace) the "no claim
  without a testbench" evidence path for the lock-time spec line, without
  reopening DR-001's calibration-FSM decision.

## Consequences

- #11's deliverable now explicitly includes one small comparator-class
  block (window comparator on the PFD/divider interface) in addition to
  the feedback divider itself.
- #12's testbench scope gains a concrete, checkable acceptance test: the
  `lock` pin must assert within the < 100 µs target (< 20 µs stretch) spec
  window and must not assert (or must deassert) if the loop is deliberately
  perturbed out of lock — giving the lock-time spec line an externally
  observable pass/fail signal, not just an internal-node measurement.
- If a future revision pulls automatic band-search into scope (DR-001's
  named "natural next step"), it consumes this decision's `lock` signal as
  its trigger input — this record's scope stops at the monitor and does
  not itself commit to that FSM.
- One additional custom-drawn 3.3 V cell (the comparator) is added to the
  device/verification list, consistent with Decision 3's single-flavor
  commitment.

---

# Decision 5 — Jitter claim

## Decision

**Ratify period jitter (RMS) as the spec'd, simulation-substantiable
quantity.** It is measured via a transient-noise testbench dominated by the
VCO (consistent with DR-001's architecture, where jitter is dominated by the
current-starved ring) plus a jitter-transfer argument through the closed
loop. Any phase-noise or integrated-jitter figure derived from that data is
recorded as **derived, not spec'd**, until the flow demonstrably produces
one directly.

**Status of this specific decision is `proposed`, not `ratified`**, per #7's
own acceptance criteria: it is an a priori assessment made ahead of #13's
actual transistor-level jitter testbench (which is blocked on #8–#11 and
will run much later). #13's eventual measurement may confirm, refine, or
supersede this decision via the standard "supersede" lifecycle (never
rewrite a ratified record — see TEMPLATE.md).

## Alternatives considered

- **Spec an integrated/phase-noise figure (e.g., an RMS jitter integrated
  from a phase-noise plot, or dBc/Hz at an offset) as the ratified
  quantity.** Rejected for v1. A free-running oscillator's phase noise is
  not an AC `.noise` analysis result in ngspice — it requires transient
  noise simulation over long runs, or ISF-based post-processing, neither of
  which this repo's flow currently has a demonstrated, evidence-backed
  path for. Per CLAUDE.md's "no claim without a testbench," spec'ing a
  number the flow cannot yet produce evidence for is exactly the promise
  #7 exists to prevent.
- **Defer any jitter claim entirely until #13 runs.** Rejected — the
  original spec table already commits to a period-jitter line (< 1% RMS
  target, < 0.5% stretch), and DR-001's architecture choice (rejecting
  sub-sampling and injection-locked topologies specifically because their
  advantage is an unspecifiable phase-noise number) already depends on
  period jitter being the tractable, spec'able quantity. Leaving the claim
  fully open would contradict a decision #1 will otherwise ratify against.
- **Ratify period jitter now, mark phase noise/integrated jitter as
  derived-only pending flow capability (this decision).** Accepted. Matches
  DR-001's own recommendation to #1 (§"Sensitivity to the open spec
  questions in #7", item 6) verbatim, keeps the spec's evidentiary promise
  inside what the flow can currently produce, and leaves room for a future
  phase-noise capability to be added without contradicting this record (it
  would supersede, not merely extend, this decision).

## Consequences

- #12's testbench scope for the jitter spec line is a VCO-dominated
  transient-noise run plus a jitter-transfer argument — not a phase-noise
  `.noise` analysis or an ISF-based post-processing pipeline, which this
  repo's flow does not yet have evidence it can produce reliably.
- The ratified spec table (feeding #1) should carry period jitter (RMS) as
  its jitter line; if a phase-noise or integrated-jitter figure appears
  elsewhere (marketing text, a datasheet draft), it must be labeled derived
  and sourced from the period-jitter measurement, not presented as an
  independently spec'd/measured quantity.
- #13, when it runs, either (a) confirms this decision empirically and can
  be promoted/ratified without change, or (b) shows the transient-noise
  approach cannot substantiate even period jitter reliably at this node,
  in which case #13 must file a new record superseding this one — this
  record must not be silently edited in that case (append-only rule,
  TEMPLATE.md).

---

## Consequences (whole-record)

**What this makes possible**

- #1 can ratify the README target-spec table against five explicit,
  reasoned scope answers instead of five open questions, matching exactly
  what the original issue asked for ("decision records in `spec/` answering
  each question; #1 ratifies against them").
- #8, #9, #11, #12, #13 each get an unambiguous scope answer to build
  against for the specific line each consumes (reference range, output
  band, device flavor, lock-detector deliverable, jitter spec line) instead
  of re-litigating any of them per-block.
- Every decision here is either directly derived from, or explicitly
  cross-checked against, DR-001's existing sensitivity analysis of the same
  five questions — so the two records are mutually consistent rather than
  independently guessing at the same open items.

**What this makes harder / what we are accepting**

- The Decision 4 lock detector and Decision 2's conditional output-divider
  trigger are both new, real deliverables added to #11's scope beyond what
  DR-001 alone implied (DR-001 assumed no lock detector and no output
  divider). #11's issue body should be checked against this record before
  work starts there.
- Decision 5 is deliberately left in `proposed` status indefinitely until
  #13 runs, which means the ratified spec (#1) will carry a jitter line
  whose simulation methodology is not yet empirically confirmed at this
  node — a known, accepted gap, not an oversight.
- Decision 2's default ("no output divider") is conditional on evidence
  #8 has not yet produced. If #8's data trips the trigger, #11's scope
  grows after the fact; this is recorded now specifically so that growth is
  a documented consequence of this record, not a fresh scope negotiation.

**What must be re-derived before any of this enters the ratified spec**

As with DR-001: this record's cost/complexity comparisons (e.g., "roughly
doubles scope," "small comparator vs. an FSM") are dispositioning arguments,
not sized commitments. #8/#9/#11/#12/#13 own the real device sizing,
power/area accounting, and measured evidence: if extracted data contradicts
an assumption here, check which decision actually depended on it before
treating this record as invalidated.
