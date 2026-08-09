# DR-007: spec-review verdict on `spec/pll.md` v1 (ratify-with-amendments)

- **Status**: proposed
- **Date**: 2026-08-09
- **Decided by**: Builder agent, issue #1, running `2AMLogic/klayout-tools`'s
  `spec-review` skill (`.claude/skills/spec-review/SKILL.md`) as the
  expert-EE reviewer named by the operator's 2026-08-09 comment on #1
- **Related**: #1 (spec ratification — this record is input to it, not the
  ratification itself), DR-001 (architecture), DR-002 (scope), DR-003 (VCO
  band map / Kvco), DR-005 (dump-node buffer), DR-006 (loop filter sizing /
  trim rule) — the decision records `spec/pll.md` consumes and this review
  checks against, #116 (mechanical Tier-2 text cleanup, addressed but not
  applied by this record — see "Confidentiality sub-question" below)

## Context

`spec/pll.md`'s Status line reads "proposed — pending engineering
ratification (#1)". A prior spec-review pass on 2026-07-31 (recorded on
#1's own comment thread) returned **defer**, because at that time there was
no committed spec table at all — only DR-001/DR-002 restatements and
dangling `spec/pll.md#...` anchors in `sim/` evidence records. #55 (PR,
2026-07-31) closed that gap by committing the current `spec/pll.md`.

The operator's 2026-08-09 comment on #1 removed `loom:operator-only` and
set today's deliverable under an interim contract: `spec-review` cannot yet
*mark* a spec ratified (that requires `klayout-tools#654`, open), so the
deliverable is the full verdict plus this decision record — not the
Status-line flip. **This record does not ratify `spec/pll.md`.** Nothing in
`spec/pll.md` is edited by this record.

## Decision

**The verdict, in the skill's own format, is reproduced in full below.**

---

# Spec review: gf180-pll PLL (PLL / clock generation, gf180mcu 3.3 V thick-oxide)

Reviewed: 2026-08-09 · Skill references dated: 2026-07-31
(`.claude/skills/spec-review/references/pll.md`)
Grounding: bundled references + this repo's own `sim/` evidence and decision
records (no `kb/entries/` PLL-class match found in this repo; no `klt kb`
probed — this repo does not carry a `kb/` directory; WebSearch refresh not
used — the 2026-07-31 reference file is 9 days old, well inside the ~2-year
staleness threshold, so no refresh was needed) ·
Devchar evidence consulted: `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md`,
`.../20260731-184845-0a12e6c.md`, `sim/loop-dynamics/records/20260731-202550-82af5a9.md`,
`sim/cp-compliance/records/20260731-194124-afa338c.md`,
`sim/mc-cp-mismatch/records/20260731-212614-640560e.md`,
`sim/lock-detector/records/20260731-162119-0a12e6c.md`,
`sim/divider-ratio/records/20260731-171815/16/17-0a12e6c.md`, plus a scan of
`sim/README.md`'s supersession chains for every one of the above (see
Amendment A4 — several of these citations have since been superseded by
value-preserving `sim/harness` migration re-runs).

## Two flagged internal-consistency questions, checked against the current committed file

The issue asked me to specifically re-check two things a pre-#55 review is
recorded as having found, since that review predates this file's current
committed form:

1. **The "10 ps vs. 100 ps" period-jitter ambiguity.** `spec/pll.md`'s
   [Period jitter](../pll.md#period-jitter) section already states and
   resolves this explicitly: DR-001's Context gloss says "10 ps RMS at
   100 MHz" while 1 % of a 10 ns period is 100 ps, and the file resolves the
   conflict **in favour of the percentage form** (100 ps at 100 MHz),
   citing that every recorded evidence number is quoted against the
   percentage and that DR-001's parenthetical is a drafting error in a
   *Context* gloss, not a Decision. **Already fixed in the committed file —
   no outstanding ambiguity.**
2. **The "< 20 µs lock-time" line.** `spec/pll.md`'s
   [Lock time](../pll.md#lock-time) section already states "**The < 20 µs
   stretch is dropped**" as a normative removal (not a stretch, not
   deferred), with the same structural reasoning the prior review is
   recorded as having found (0/140 measured configurations reach it;
   saturation at ≈43 µs from `1/(2πRC1)`, a property of the fixed filter,
   not the drive level). **Already fixed in the committed file — no
   outstanding ambiguity.** The remaining open item on this row is
   different and is raised as Amendment A1 below (cold-start acquisition,
   not the 20 µs question).

## Per-line review

### Output band — 10–200 MHz, continuous, all corners
- **Achievability**: comfortable — the reference's pitfall list requires
  "≥ ±20–30 % design margin" for ring-VCO tuning-range coverage at both
  slow and fast corners; the measured margins here are 36 % (floor) and
  24 % (ceiling), both at or above that convention.
- **Evidence**: supports — `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md`,
  3528 points, 0 non-monotonic curves, worst adjacent-band overlap 27 %.
- **Corner binding**: stated OK — floor at `all-fast`/125 °C/2.97 V,
  ceiling at `all-slow`/−40 °C/3.63 V, both named per the reference's
  "VCO range binds at both SS/hot and FF/cold simultaneously" convention.

### Reference input — 1–25 MHz, CMOS square wave
- **Achievability**: comfortable — a 25:1 reference range with a 1–25 MHz
  ceiling is unremarkable for this block class.
- **Evidence**: no evidence for the electrical levels/edge-rate sub-rows
  (V_IL/V_IH, ≤ 5 ns edge) — self-declared `budget` in the file, consistent
  with the Verification-owed table. The range itself is exercised as an
  operating condition of the loop-bandwidth/trim-rule campaign, so that
  part is measured.
- **Corner binding**: `n/a` with reason, correctly — it is an interface
  contract on the driving system, not a PVT-varying output.

### Multiplication ratio — N = 4–64
- **Achievability**: comfortable — standard integer-N range for this class.
- **Evidence**: supports — 235 chain points, 0 ratio errors; retiming
  setup margin 6.1 % of a VCO period at the worst corner is thin but
  positive, and the file itself flags it as schematic-level and the
  thinnest margin owed to #18's extraction.
- **Corner binding**: stated OK — setup at `ss`/125 °C/2.97 V, hold at
  `ff`/−40 °C/3.63 V (two different, correctly named corners, exactly the
  reference's setup/hold pattern).

### Integrated RMS jitter — not spec'd
- **Achievability**: n/a — no target.
- **Evidence**: n/a by design (DR-002 Decision 5).
- **Corner binding**: `n/a`, correctly, since there is no target to bind.
- **Completeness note**: this is a canonical checklist line (#4) with no
  value, but it is not a *silent* omission — the row exists, states why,
  and attributes the decision to DR-002. That is the correct way to carry
  an intentional gap and satisfies the reference's "missing lines are
  findings, not footnotes" rule by making the finding explicit in the spec
  itself rather than leaving it for a reviewer to discover.

### Period jitter — ≤ 1.0 % of period RMS, conditional on ≤ 20 mV pp ripple
- **Achievability**: aggressive, not comfortable. The reference's
  comfortable/aggressive bands are stated for *integrated* jitter, a
  different quantity (the reference's own pitfall #1), so they don't map
  directly onto this row — but computing the ring-PLL FoM from the spec's
  own numbers as an approximation (period jitter substituted for σt,
  1.98 mW derived power at 100 MHz): FoM ≈ 10·log10[(100 ps)² · 1.98] ≈
  **−197 dB**. That sits *below* (worse than) the −215 to −225 dB
  "comfortable" band for ring PLLs in the reference table — i.e. this is a
  legitimate, unremarkable-for-an-unoptimized-schematic number, not a
  "too good to be true" one, and definitely not "not credible." The more
  material risk is budget exhaustion, not achievability: the file's own
  derivation spends *half* the 1 % RMS budget on the ripple term alone
  (0.50 % at the 20 mV pp condition), leaving the other half for an
  unmeasured random/thermal contribution.
- **Evidence**: supports for the ripple sensitivity (measured open-loop,
  63-point grid, 134× above the solver noise floor at the tightest margin);
  no evidence for the random-jitter half of the same budget — self-declared
  in Verification owed, consumer of #13.
- **Corner binding**: stated OK — `all-slow`/−40 °C/2.97 V, band 5.

### Phase noise — not spec'd
- Same treatment as integrated RMS jitter above: intentional, attributed,
  visible gap (DR-002 Decision 5). No amendment needed beyond what row 4
  already states.

### Reference spur — ≤ −55 dBc
- **Achievability**: comfortable per the reference table (−40 to −55 dBc
  comfortable, −60 to −70 dBc aggressive) — the target sits at the
  comfortable/aggressive boundary, not past it.
- **Evidence**: no evidence — the file is explicit that this is derived,
  not measured, and says so twice ("do not cite as evidence"). More
  specifically: the derivation covers exactly **one** mechanism (charge-pump
  per-event charge asymmetry) and states three others it does *not* cover
  (anti-backlash-window UP/DN current mismatch, supply/substrate coupling
  of f_ref into the VCO rail, and layout coupling), leaving only ~6 dB of
  headroom against its own single-mechanism bound for all three of them
  combined. That is thin, and it is thin against unquantified terms, not
  measured ones.
- **Corner binding**: stated — `fs`/125 °C/3.63 V, Vctrl 0.9 V, f_out =
  200 MHz — correctly identified as both the worst corner and worst
  frequency.
- **See Amendment A2.**

### Loop bandwidth — f_c = 26–430 kHz, f_c < f_ref/10
- **Achievability**: comfortable — Gardner's f_ref/10 discrete-time
  stability limit is respected with margin everywhere (worst realized
  f_c/f_ref = 1/13, i.e. inside the ceiling by 30 % relative even at the
  single worst point of a 140-cell × 27-passive-bundle × 3-temperature ×
  5-Vctrl-point sweep).
- **Evidence**: supports — this is the single most heavily corner-swept row
  in the file (`sim/loop-dynamics`, 405 filter curves × 25 loop-gain points
  × all legal N × all 4 trim codes, cross-checked to an independent
  whole-loop AC sim to 0.000 % agreement).
- **Corner binding**: stated OK, with the [Icp trim-code rule](../pll.md#icp-trim-code-rule)
  correctly promoted from a discretionary margin knob to a normative
  operating condition — this is exactly the kind of "condition, not
  advice" flagging the reference's stability pitfalls call for.

### Phase margin — ≥ 45°
- **Achievability**: comfortable per Gardner-class practice for a
  charge-pump PLL; DR-006 adopts 45° explicitly since DR-001 states the
  bandwidth ceiling but no phase-margin number.
- **Evidence**: supports — worst 47.4° at f_ref = 1 MHz, 4 legs, which is
  the row with the least trim-code slack (only one code passes there). The
  2.4° margin above the 45° floor is thin but it is a measured floor, not
  an assumed one, and 105/140 cells clear it unconditionally.
- **Corner binding**: stated OK.

### Lock time — < 100 µs, the < 20 µs stretch dropped
- **Achievability**: comfortable against the reference's own table (10–100 µs
  is "comfortable" for an integer-N, kHz–MHz-loop-BW PLL) — the worst
  measured settling (71 µs) sits inside that band, and the reasoning for why
  < 20 µs (the reference's own "aggressive"/edge-of-not-credible territory
  for this loop-BW class) is unreachable matches the reference's own
  "Loop bandwidth vs. reference frequency unstated" pitfall almost exactly:
  a fixed passive filter obeying `f_c ≤ f_ref/10` cannot deliver a
  settling time an order of magnitude below the loop's own time constant.
- **Evidence**: measured for small-signal settling (120/140 cells pass;
  every failure is an off-rule trim code); **not measured for the headline
  quantity's actual starting condition.** The file's own [lock
  criterion](../pll.md#lock-time) is stated for **cold start** (Vctrl = 0),
  which involves cycle slipping and large-signal VCO nonlinearity that a
  fitted 3-element small-signal model does not capture — the file states
  this limitation itself, in the same section, in plain language.
- **Corner binding**: stated OK — 71 µs at f_ref = 1 MHz, 4 legs.
- **See Amendment A1** — not because the row is dishonest (it is
  unusually explicit about its own limitation already) but because the
  gap between "modeled settling time" and "the thing the summary table's
  headline number is titled" is large enough, and #12's cold-start bench
  important enough, that it belongs in this review's amendment list rather
  than only in a Verification-owed footnote.

### Power — < 5 mW at 100 MHz, all domains
- **Achievability**: comfortable — 2.5× margin at the binding corner is
  ample for this block class at this node.
- **Evidence**: measured for `vdd_vco` (worst of 159 grid points); derived
  by linear interpolation for `vdd_div` (two measured decades agreeing to
  6 %, a reasonable interpolation); **budget** (not separately measured at
  all) for `vdd_ref` — roughly 9 % of the derived total.
- **Corner binding**: stated OK — `all-fast`/125 °C/3.63 V, correctly
  identified as the binding corner (higher band code, higher Vctrl at the
  fast corner drives more starving current, not the cold corner).

### Standby current — waived, no power-down mode
- **Achievability/Evidence**: n/a by design; the waiver is explicit and its
  consequences (no way to stop current draw except removing rails; no fast
  wake path) are stated rather than glossed over.
- **Corner binding**: `n/a` with reason — correct.

### Supply sensitivity — ripple ≤ 20 mV pp; DC budget ≤ 0.6 V of Vctrl window
- **Achievability**: this is the row the reference's own pitfalls flag most
  directly ("No supply-sensitivity row for a ring PLL" is listed as a
  common spec-writing failure) — the file avoids that failure comprehensively:
  AC and DC budgets both stated, both derived from a measured open-loop
  pushing characterization, and the −30.3 %/V structural floor (the
  unavoidable `f ∝ 1/V_swing` term of any current-starved ring) is
  correctly separated from the measured −39.4 %/V median so a reader can
  tell how much of the number is architecture-inherent vs. bias-generator
  contribution.
- **Evidence**: supports — measured on a purpose-built 7-supply-point bench
  plus cross-checked against the coarser tuning-range grid (consistent,
  not contradictory, and the file says so explicitly rather than silently
  picking one number).
- **Corner binding**: stated OK — worst −50.7 %/V at `ss`/−40 °C, band 4.
- **See Amendment A5 (soft)** — the reference's own pitfall text for this
  row explicitly says to "cross-check against the LDO spec's PSRR-vs-
  frequency row at the loop bandwidth." No such cross-reference exists in
  this repo yet, because no LDO block spec for this system exists yet
  (only the sister `2AMLogic/gf180-bandgap` repo, which is a different
  block). This is not a defect in this file today, but it is a system-level
  integration dependency the file correctly names in prose ("a system
  integrating this block must design its rail against Budget 1") without
  a citable target to check against yet.

### Output duty cycle — 45–55 %
- **Achievability**: comfortable, on design-intent grounds (matched
  PMOS/NMOS starving devices, symmetric buffer chain) — plausible, not
  measured.
- **Evidence**: no evidence — zero duty-cycle measurements exist anywhere
  in `sim/`. The file states this plainly and lists it in Verification
  owed. This is a canonical checklist row (#12) carried entirely on design
  intent.
- **Corner binding**: `n/a` with reason (no measurement exists to bind), and
  the file additionally states its expected binding corner (bottom of the
  band) as a prediction, which is good practice even without data yet.

### Output levels and drive — rail-to-rail, ≤ 50 fF external load
- **Achievability**: comfortable — a three-stage tapered CMOS buffer driving
  50 fF is unremarkable.
- **Evidence**: no evidence — every recorded frequency point in
  `sim/vco-tuning-range` is taken essentially unloaded. Self-declared
  `budget`.
- **Corner binding**: `n/a` with reason, correctly stated.

### Area — ≤ 0.15 mm²
- **Achievability**: cannot be assessed against the reference (it has no
  area anchors for this block class), and cannot really be assessed at all
  yet — see Evidence.
- **Evidence**: measured for the loop filter only (21.4 % of budget, from
  real device density data); **no estimate of any kind** — not even a
  hand calculation — exists for the remaining 78.6 % (VCO, PFD/CP, divider,
  lock detector, routing, decap). This is different in kind from the other
  `budget` rows in the table: those have a stated design-intent rationale
  even without a measurement; this one has neither a measurement nor an
  estimate for the majority of the block.
- **Corner binding**: `n/a` with reason — correct (drawn area is not a PVT
  quantity).
- **See Amendment A3.**

### Lock detector — targets not met today
- **Achievability**: the *targets themselves* are reasonably chosen (T1/T2
  tie the assert window to 2× the worst-case static phase offset rather
  than to an arbitrary absolute number, which is exactly the kind of
  self-tracking definition the reference's completeness discipline wants).
- **Evidence**: **contradicts** — the file states this itself in as many
  words: the measured window (0.877–1.702 ns) and the measured worst-case
  static phase offset (≈1.49 ns summed) are of comparable size, so "a
  correctly locked part may fail to assert `lock`" at several corners,
  worst at the top of the reference range where the trim rule mandates the
  smallest Icp. T4/T5 are additionally unverified below 25 MHz, with a
  stated (not measured) expectation of chatter at the low end.
- **Corner binding**: stated OK — `ss`/125 °C/2.97 V for window/assert/
  deassert timing, `ff`/−40 °C/3.63 V for the narrowest window (the T1
  binding corner) — two different, correctly distinguished corners.
- **See Amendment A1** (bundled with lock time as the sharpest "not yet
  achieved" pair in the table).

### Kvco — ≤ 150 MHz/V under the band-selection rule
- **Achievability**: comfortable — 115.8 MHz/V worst legal point against
  the 150 MHz/V bound is 23 % of margin, and the file is unusually good
  about showing the adversarial counter-example (154.3 MHz/V if the rule
  is violated) so the rule's necessity is falsifiable rather than asserted.
- **Evidence**: supports — full per-band, per-corner table
  (`kvco_by_band.csv`/`kvco_by_point.csv`), 3528-point grid.
- **Corner binding**: stated OK — `all-fast`/27 °C/2.97 V, B6 @ 1.54 V.
- **Uncharacterized, self-declared**: band-select mirror mismatch — every
  cited record runs with `sw_stat_mismatch = 0`, and mismatch directly
  perturbs the 1.65× ratio the band-overlap margins depend on. Listed in
  Verification owed; not a new finding.

### Supply range — 3.3 V ± 10 %
- **Achievability**: comfortable — standard for the device flavor.
- **Evidence**: supports — swept as the independent axis of every cited
  campaign.
- **Corner binding**: `n/a` with reason — correctly identified as the
  independent variable other rows bind against, not a bindable quantity
  itself.

## Completeness

Walking the reference's 13-item canonical checklist against the summary
table: **every canonical line has a row.** No line is silently absent —
which is itself worth stating plainly, because it is the opposite of the
2026-07-31 review's finding (at that time there was no committed table at
all). Within that, the honest state is:

- Two rows (integrated RMS jitter, phase noise) are canonical lines
  present with **no target**, by a cited, reasoned decision (DR-002
  Decision 5) rather than a silent gap — acceptable as drafted.
- Four rows (reference-input electrical levels, output duty cycle, output
  levels/drive, and most of area) carry **zero measured or estimated
  evidence** and are self-declared `budget`. Three of those four (duty
  cycle, output levels, reference-input levels) at least carry a stated
  design-intent rationale; area's non-loop-filter 78.6 % carries **no**
  rationale of any kind (see Amendment A3).
- One row (lock detector) has a **measured contradiction** of its own
  stated target (see Amendment A1).
- One row (reference spur) is **derived, not measured**, from a partial
  mechanism accounting with thin headroom against the mechanisms it
  excludes (see Amendment A2).

None of this is a *missing* canonical line — it is a spread of evidence
maturity across lines that are all present, which is exactly the
distinction the file's own measured/derived/budget status column is built
to make visible, and it makes it well.

## Corner-binding check

Every row in the summary table carries either a stated PVT/configuration
binding or an explicit `n/a` with a reason. This is a strong result against
the reference's own stated baseline ("the stripped draft table had no
corner-binding column at all" — the 2026-07-31 review's finding on the
pre-#55 state). Two places worth calling out as done *well*, matching the
reference's own worked pattern (throughput/entropy binding at opposite
corners on adjacent rows):

- **Multiplication ratio** binds setup at `ss`/125 °C/2.97 V and hold at
  `ff`/−40 °C/3.63 V on the same row, correctly as two different corners.
- **Lock detector** binds window/assert/deassert timing at `ss`/125 °C/
  2.97 V but the *narrowest* window (its T1 failure mode) at `ff`/−40 °C/
  3.63 V, again two different corners on the same row.
- **Power** correctly identifies the fast/hot/high-supply corner as
  binding rather than defaulting to the intuitively-obvious cold corner,
  and explains why (higher band code and Vctrl at the fast corner drive
  more current).

No row fails the corner-binding check outright.

## Verdict

**ratify-with-amendments**

- **A1 — Lock detector and cold-start lock time need to close, not just be
  disclosed, before final ratification of those two rows.** The lock
  detector's own stated targets (T1/T2) are measured to fail at several
  corners today, and the lock-time row's headline number is a small-signal
  model that has never been checked against the nonlinear cold-start
  acquisition its own criterion is defined against. Both gaps are already
  named in the file's Verification-owed table (owed to #11 rework and #12
  respectively) — this amendment does not add new information, it
  elevates these two from footnote to blocking-for-full-ratification,
  because they are the two rows where the evidence *contradicts or cannot
  yet substantiate* the stated target, as opposed to merely not yet
  measuring it.
- **A2 — Reference spur's derivation should bound (even roughly) the two
  mechanisms it currently excludes** (anti-backlash-window current
  mismatch, supply/substrate f_ref coupling) before the −55 dBc row is
  treated as more than a provisional placeholder — the derivation's own
  ~6 dB of headroom is thin against unquantified terms.
- **A3 — Area's non-loop-filter 78.6 % should carry at least a rough
  hand-estimate** (transistor count × a typical gf180mcu layout density)
  before ≤ 0.15 mm² is read as anything more than aspirational; today it
  is the one `budget` row in the table with no rationale behind the
  number at all, not even a disposition-only hand calc.
- **A4 — Update `spec/pll.md`'s cited `sim/` record IDs to their current
  successors.** Several of the file's own `sim/` citations
  (`vco-tuning-range/records/20260731-175947-0a12e6c.md` and
  `.../20260731-184845-0a12e6c.md`, `cp-compliance/records/20260731-194124-afa338c.md`,
  `lock-detector/records/20260731-162119-0a12e6c.md`,
  `divider-ratio/records/20260731-171815/16/17-0a12e6c.md`) have since
  been superseded by `sim/harness`-migration re-runs, each explicitly
  marked "NOT a value correction" with a stated numeric-agreement check
  against the predecessor. The substance is unaffected — this is a pure
  traceability fix, not a technical finding — but a reader following
  `spec/pll.md`'s citations today lands on superseded evidence rather than
  the currently-citable record, which is exactly the failure mode
  `sim/README.md`'s "read forward" supersession convention exists to avoid.
- **A5 (soft, no action owed by this repo alone) — the supply-sensitivity
  row's own cross-check (an LDO PSRR-vs-frequency spec at the loop
  bandwidth) does not yet exist anywhere in this program**, because no LDO
  block spec for this system has been ratified. Noted so the dependency is
  visible; not a defect in this file.

**Confidentiality sub-question** (per #1's acceptance criteria — addressed,
not silently dropped, and deliberately **not resolved here** as a business
call): `spec/pll.md`'s own Confidentiality section rests on this repo's
CLAUDE.md carrying a "Tier 2" restriction. As of this review, **the current
committed `CLAUDE.md` carries no Tier 2 or confidentiality language at
all** (`git grep -i 'tier 2\|confidential' CLAUDE.md` returns nothing) —
that framework was removed by `e6fc114` ("docs: prepare CLAUDE.md for
publication," #115). The predicate `spec/pll.md`'s Confidentiality section
cites therefore no longer holds in the tree as committed. This is a factual
observation about what the repository's own governing document currently
says, not a publication-safety ruling — whether the specific numeric values
in `spec/pll.md` are safe to publish is a business/publication call this
review is not positioned to make (CLAUDE.md: business positioning and
commercial terms do not belong in this repo, and by the same logic a
publication-safety ruling is not an engineering-achievability question this
skill is built to answer). #116 (open) already tracks the mechanical
follow-up to `spec/pll.md`/DR-001's stale Tier 2 text; this record surfaces
the underlying fact so #116 is not blocked on rediscovering it, and leaves
the actual ruling to the operator on #1, per that file's own routing.

**None of the five amendments above is a "not credible" finding.** Every
achievability call in the per-line review above lands at *comfortable* or
*aggressive*, never *not credible* — the engineering is sound and, on
several rows (loop bandwidth, output band, Kvco, supply sensitivity), is
backed by evidence stronger than most published open-silicon work at this
stage (the same conclusion the 2026-07-31 review reached about the
DR-001/DR-002 scope work, now extended to the committed spec table itself).
The amendments are about evidence maturity and traceability on specific
rows, not about the target values being wrong or unreachable. Ratification
is the operator's call; this review is an opinion.

## Alternatives considered

- **ratify outright.** Rejected: two rows (lock detector, reference spur)
  carry a measured contradiction or a thinly-covered derivation
  respectively, and one row (area, non-filter portion) carries no estimate
  at all — these are the kind of findings the reference's per-line
  procedure exists to surface, and burying them under an unqualified
  "ratify" would understate them.
- **defer.** Rejected: unlike the 2026-07-31 review, there is now a
  committed, corner-bound, heavily-evidenced spec table, and none of this
  review's findings are "a load-bearing line is not credible" or "a
  prerequisite decision record is missing" — the two conditions the skill
  names for `defer`. Every amendment above names a scoped, closeable gap on
  a specific row rather than a reason the whole table cannot be judged.
- **Mark the confidentiality sub-question resolved (ratify-safe-for-publication)
  as part of this record.** Rejected: this record's job (per the interim
  contract on #1) is the engineering verdict, not a publication-safety
  ruling, which is explicitly named in `spec/pll.md` itself as routed to
  the operator via #1. Stating the underlying CLAUDE.md fact (no Tier 2
  language exists today) without making the ruling keeps this record inside
  its own lane.

## Consequences

- **#1 remains open.** This record does not flip `spec/pll.md`'s Status
  line; that remains an operator action on #1 (directly, or once
  `klayout-tools#654` lands a binding-with-veto path for `spec-review`
  itself).
- **A1–A4 are actionable follow-ups**, not spec edits made by this record:
  A1 is design/testbench work already tracked (#11 rework, #12's cold-start
  bench); A2 and A3 are additional derivation/estimation work on existing
  rows, not new campaigns; A4 is a small, mechanical citation update to
  `spec/pll.md` (separate from this record, since this issue's scope does
  not include editing `spec/pll.md`).
- **The confidentiality observation is handed to #1/#116** rather than
  acted on here — #116 can now cite this record instead of rediscovering
  the CLAUDE.md fact independently.
- **What this does *not* invalidate**: DR-001 through DR-006 all stand.
  Nothing in this review found an architecture, scope, or sizing decision
  that needs superseding — every finding is at the evidence-completeness
  level of an individual spec row, not at the level of a decision record's
  own reasoning.
