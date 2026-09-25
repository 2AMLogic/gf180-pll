# PLL target specification — v1

- **Status**: **ratified, with amendments** (#1, 2026-09-08), per
  `spec/decision-records/DR-007-spec-review-verdict.md`'s
  `ratify-with-amendments` verdict, applied through this repo's
  spec/DR-ratification-via-PR policy (`2AMLogic/2am#357`, precedented on
  this repo by #148/PR #158): a Builder drafts the ratification as a PR on
  the evidence, and the operator's approval of that PR is the ratifying
  act. **Two rows are carved out of this ratification and remain
  unratified**, per DR-007 Amendment A1: [Lock time](#lock-time) (row 9)
  and [Lock detector](#lock-detector) (row 16) — both rows' own stated
  targets are *contradicted*, not merely unmeasured, by the evidence each
  row's own text already discloses, which is why DR-007 elevated exactly
  these two from footnote to a blocking condition on full ratification.
  Every other row is ratified as stated, including its own
  measured/derived/budget status column. DR-007's remaining amendments
  (A2, A3, A5) are evidence-maturity and traceability follow-ups, not
  additional blocking conditions, and are not applied as edits in this
  revision — see DR-007 and the ratifying PR's description for what each
  amendment's disposition was and why. **A3 has since been discharged** by
  DR-016 (#456) — see the Area-row revision bullet below. Amendment A4 (stale `sim/`
  citations) is partially applied in this revision: the `cp-compliance`,
  `lock-detector`, and `divider-ratio` citations below now point at their
  current `sim/harness`-migrated records; the `vco-tuning-range`
  `20260731-175947-0a12e6c` citation (output band / Kvco / band-selection
  rule) is deliberately **not** updated even though a migrated successor
  exists, because that successor's own printed numbers differ from this
  file's stated values in the last 1–2 significant digits at several rows
  (e.g. floor 6.449→6.451 MHz, ceiling 247.8→247.7 MHz, Kvco
  115.8→115.7 MHz/V) and reconciling every number those rows carry is out
  of this revision's scope — flagged here rather than silently applied;
  see the ratifying PR's description for detail.
- **Date**: 2026-07-31
- **Written by**: Builder agent, issue #55
- **Consumes**: DR-001 (architecture), DR-002 (scope ratification), DR-003
  (VCO band map / Kvco contract), DR-005 (dump-node buffer), DR-006 (loop
  filter values and the Icp trim rule), DR-010 (lock-detector window targets),
  DR-011 (post-supply-step settling), and the `sim/` evidence records each of
  those cites.
- **Revisions to the carved-out rows** (#387, 2026-09-15; row 16 updated
  again by #393, 2026-09-16, and again by #407, 2026-09-16). Row 16's targets
  **T1/T2 are replaced by T1′/T2′** per DR-010 — the original pair could not
  be satisfied simultaneously, as its own [section](#lock-detector) now shows
  with measured numbers — and the [Lock time](#lock-time) section gains a
  second limitation, on re-lock after a mid-operation supply excursion, per
  DR-011. DR-010's decided fix (W = 9.5 µm) is now implemented and
  re-characterized (#393): T1′ is met, but the re-characterization surfaces a
  new finding DR-010's own idealized sizing campaign did not show — **T2′ is
  exceeded** at the same corner it names as binding, by 0–5 %, under the
  realistic full-loop stimulus this in-situ campaign drives with rather than
  the isolated delay chain's ideal voltage step (#401). **DR-013** (#401) then
  decides that gap: T1′ and T2′ keep their numbers and T2′'s reach is **not**
  widened; what changes is that both are measured at the flag rather than at
  the delay chain, and that the window's PVT spread — not its centre — is what
  the fix has to move (#407). **#407** then sizes the miss precisely
  (**[2.02, 2.04) ns**, 1.0–2.0 % over budget) and **DR-014** picks the fix
  mechanism — a fixed test-set trim code, not a bias-referenced delay — with
  implementation and re-characterization scoped onward to **#411**. **#411**
  (2026-09-18) then builds the trimmed cell, sizes the code (four bits, a
  2.7–4.7 % step, on measurement rather than preference), adds the normative
  [Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule)
  as a third normative condition, and re-characterizes the assembled loop under
  it: **T1′ and T2′ are both met**, the observable window holding
  [1.14, 1.16) ns … [1.78, 1.80) ns across the grid at a spread of 1.53–1.58×
  against DR-013 Decision 4's ≤ 1.65×.
  **Neither carved-out row leaves DR-007 Amendment A1's
  carve-out on this revision, and #411 does not change that.** Row 16's T1′/T2′
  contradiction is resolved, but the row carries more than those two targets:
  **T4 and T5 remain uncharacterized below 25 MHz**, and the row now also
  depends on a normative trim rule whose code table is schematic-level and
  mismatch-free — and, per **DR-022** (#501, 2026-09-25), whose code **no
  present bench or tester procedure can select on a packaged part**: every
  quantity `pll_top`'s pads expose has now been measured against the rule's
  internal measurand and none reaches the accuracy the row's own spread figure
  assumes. That is a third reason this row stays carved out, not a reason to
  move it. Row 9's cold-start question is unchanged, though DR-013
  Decision 7's *hold* on its re-take is released by #411's window landing.
  Lifting the carve-out is a ratification act on evidence that does not exist
  yet, not a consequence of these revisions.
- **Revision to a ratified row** (#456, 2026-09-22, under #442): **[Area](#area)
  (row 15) is amended from ≤ 0.15 mm² to ≤ 0.30 mm² by DR-016.** This is the
  first amendment in this file that *weakens* a ratified target, so the
  standard it was held to is stated here rather than left in the record: the
  draft number was never derived from anything (DR-007 **Amendment A3** — "the
  one `budget` row in the table with no rationale behind the number at all"),
  and the 78.6 % of it that A3 said had "no estimate of any kind" is now four
  committed, DRC-clean, LVS-matched block layouts **measured** off GDS by
  `python3 layout/run_pv.py area` — 0.2733 mm², **1.82×** the draft target, as
  measured when DR-016 was ratified (0.2254 mm², 1.50× today — see the DR-017
  bullet below).
  DR-016's amendment rests on measurement, not on projection: it is set at the
  measured total, explicitly *not* at either of the two bounds that also fail
  0.15 mm² (0.1799 mm² granting every remaining lever its geometric ceiling;
  0.1702 mm² assuming all Metal2 routing is free), because those are estimates
  of a class this repository has now measured delivering 42 % and 66 % of their
  sizing when built (#455, #454). **A3 is thereby discharged** — by
  measurement rather than by the hand-estimate it asked for. No other row moves,
  and the carve-out set (rows 9 and 16) is unchanged.
- **Revision to a ratified row's *evidence*, with the row itself unchanged**
  (#476, 2026-09-23, follow-up to #458): **[Area](#area) (row 15) keeps
  ≤ 0.30 mm², and its measured table is refreshed to the committed GDS by
  DR-017.** Three Metal2 routing-track levers landed after DR-016 was ratified
  — #469 and #473 inside `pfd_cp`, #458 on `divider_chain` — taking the summed
  block footprint 218,631 → **180,307 µm²** (−17.5 %) and the total, after the
  floorplan's ×1.25 top-level overhead, 0.2733 → **0.2254 mm²** (91.1 % →
  **75.1 %** of the row; 1.82× → **1.50×** the draft target). None of those PRs
  refreshed this file, because refreshing DR-016's block-by-block figures is
  the same act as amending the row they sit under; DR-017 is that act.
  **The row is held, not amended down**, and the reason is that its margin is
  defined (DR-016 Decision 2) as covering the one factor nothing has measured —
  §5's ×1.25 multiplier, with no assembled `pll_top` to check it against (#17)
  — and that factor has not changed at all. DR-017 Decision 3 accordingly
  narrows DR-016 Decision 4's re-amendment trigger: a lower row now requires
  the uncertainty itself to shrink (an assembled `pll_top`, or a drawn loop
  filter whose 36,936 µm² stops being a DR-006 calculation), not another
  block-level lever. **No ratified row is relaxed by this revision** — the
  measured total moves further *under* the row, not past it — and no other row
  moves.
- **Supersedes**: nothing. The DRAFT target table that used to live in
  `README.md` was removed by the pre-publication audit (#38, PR #47) and is not
  restored there; this file is where the target spec lives from now on.

---

## How to read this file

Every parameter has:

1. a row in the [summary table](#summary-table), carrying the **v1 target**, a
   mandatory **corner binding**, and a **status** telling you whether the
   number is measured, derived, or a budget with no measurement behind it; and
2. a section further down whose heading is the parameter's stable **anchor** —
   `spec/pll.md#<anchor>` — which is what `sim/` evidence records cite.

Three status words are used, and the distinction is the point of the file:

| Status | Means |
|---|---|
| **measured** | a `sim/` record substantiates this number over a stated corner matrix |
| **derived** | computed from one or more measured records plus stated arithmetic; no single record reports it |
| **budget** | a target with no measurement behind it yet; the verification owed is named in [Verification owed](#verification-owed) |

A **corner binding** names the PVT point (and, where it matters, the band code,
trim code, N, or `f_ref`) at which the parameter is worst. Rows that are
conditions or interface contracts rather than PVT-varying quantities carry an
explicit `n/a` **with a reason** — never a blank.

Three rules in this file are **normative conditions**, not advice: the
[band-selection rule](#band-selection-rule), the
[Icp trim-code rule](#icp-trim-code-rule) and the
[Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule). A
part configured against any one of them is operating outside this
specification, and no row below applies to it.

### Everything here is schematic-level

No layout parasitics, no extracted netlists, no silicon. Every measured number
is a pre-layout simulation result, and extraction (#18) is where most of them
are at risk. Nothing in this repository has been fabricated or measured.

### Who else reads this file

[Consumers](#consumers), near the end of this document, names every repo that
declares a dependency on this block and checks its stated requirements
against the rows above. The structured, machine-readable counterpart —
top cell, port list, netlist/GDS paths, measured area, maturity rung — is
[`manifests/integrator.json`](../manifests/integrator.json).

---

## Summary table

| # | Parameter | v1 target | Corner binding | Status |
|---|---|---|---|---|
| 1 | [Output band](#output-band) | 10 – 200 MHz, continuous | floor `all-fast`/125 °C/2.97 V (6.449 MHz, 36 % below the line); ceiling `all-slow`/−40 °C/3.63 V (247.8 MHz, 24 % above) | **measured** |
| 2 | [Reference input](#reference-input) | 1 – 25 MHz, CMOS square wave, rising-edge triggered, duty 30–70 % | n/a — interface contract; the electrical limits are conditions on the driving system, not PVT-varying outputs | **budget** (levels, edge rate **and** duty — duty is argued from `design/pfd.sch`, not measured); range is **measured** as an operating condition of rows 8/9. The sweep that would discharge all three is declared and unmeasured at `sim/reference-input-contract`, owed from #499; DR-019 re-points that obligation off closed issue #12 and restates the reference-source-quality exclusion with its owner |
| 3 | [Multiplication ratio](#multiplication-ratio) | N = 4 – 64, every integer, static configuration | retiming setup `ss`/125 °C/2.97 V at N = 64, 200 MHz (6.1 % of a VCO period) | **measured** |
| 4 | [Integrated RMS jitter](#integrated-rms-jitter) | **not spec'd** — derived-only (DR-002 Decision 5) | n/a — deliberately unspecified; see the section for why this is visible rather than silent | **n/a** |
| 5 | [Period jitter](#period-jitter) | ≤ 1.0 % of the output period, RMS, **conditional on ≤ 20 mV pp `vdd_vco` ripple** | `all-slow`/−40 °C/2.97 V, band 5 (2.51 % RMS at 100 mV pp ripple, open-loop); closed-loop deterministic jitter measured at all 45 mandated PVT corners, 0.0508–0.2691 % RMS, PASS at every corner (`sim/period-jitter/`, #13) | **measured** (sensitivity, and the closed-loop **deterministic** half at 45/45); **derived** (the ripple condition); the **random (noise-driven) half is not measured and is not obtainable from any analysis this flow offers** — DR-023, owed at #520. The row is not discharged by the deterministic PASS |
| 6 | [Phase noise](#phase-noise) | **not spec'd** — derived-only (DR-002 Decision 5) | n/a — deliberately unspecified | **n/a** |
| 7 | [Reference spur](#reference-spur) | ≤ −55 dBc | measured worst −57.0 dBc at f_out = 150 MHz (`sf`/−40 °C/2.97 V), i.e. −54.5 dBc scaled to 200 MHz; derived worst case −61 dBc at 200 MHz, or **−56.6 dBc** once DR-018's corner-combined statistical charge terms are folded into the same derivation, against **−66.6 dBc** for the systematic-only stack a mismatch-off measurement is comparable with (DR-024) | **measured** (5 spanning corners, 150 MHz); **budget** (the 200 MHz binding point and the other 40 corners). The binding-point sweep is a declared campaign, `sim/reference-spur-band-top`, with **zero measured points**, owed at #533 — see [Verification owed](#verification-owed) |
| 8 | [Loop bandwidth](#loop-bandwidth) | f_c = 26 – 430 kHz over the ratified space, with `f_c < f_ref/10` as a hard ceiling | min 25.96 kHz at f_ref = 1 MHz / 4 legs; max 429.5 kHz at f_ref = 25 MHz / 1 leg; worst realized ratio `f_ref/13` | **measured** |
| 8a | [Phase margin](#phase-margin) | ≥ 45° everywhere in the contracted space | 47.4° at f_ref = 1 MHz, 4 legs (the tightest cell of the trim rule) | **measured** |
| 9 | [Lock time](#lock-time) | < 100 µs to the stated [lock criterion](#lock-time). **The < 20 µs stretch is dropped** | 71 µs at f_ref = 1 MHz under the trim rule; structural floor 43 µs. **The criterion this time is measured *to* is not met at 1 of the 45 mandated corners at the configuration the [band-selection rule](#band-selection-rule) selects, with a second corner owed** — the static-phase half settles at 1.049 ns at `typical`/−40 °C/3.63 V against the ratified ≤ 1 ns (DR-012), so at that corner there is no instant for a lock time to be measured to. The 1.227 ns at `ff`/27 °C/3.63 V is measured at **band 6**, which is not the band the rule selects there (DR-025); the rule-selected band-5 cell is unrun, so that corner is neither cleared nor confirmed and the count returns to 2 of 45 if it misses | **measured** (small-signal settling); **budget** (cold-start, owed to #163); target **not met** at 1/45 corners because the criterion itself is not reached there, with a 2nd corner's rule-selected configuration owed (DR-025, #511) |
| 10 | [Power](#power) | < 5 mW at 100 MHz, all domains, locked | `all-fast`/125 °C/3.63 V — derived total ≈ 1.98 mW | **derived** |
| 11 | [Standby current](#standby-current) | **no power-down mode in v1** — the block is always-on whenever its rails are up | n/a — no standby state exists to bind a corner to | **waived, with rationale** |
| 12 | [Supply sensitivity](#supply-sensitivity) | `vdd_vco` ripple ≤ 20 mV pp (100 kHz – 100 MHz); DC rail excursion over 2.97–3.63 V must consume ≤ 0.6 V of the Vctrl window | pushing worst −50.7 %/V at `ss`/−40 °C, band 4 (−52.3 %/V on the coarser tuning-range grid). **Budget 2's consumption is now measured on the closed loop at all 45 mandated points and the budget is not met**: 0.385 … 0.846 V consumed over the ratified rail, worst `ss`/−40 °C at **0.846 V** = **1.41×** the budget, over at **9 of the 15** (bundle, temperature) cells (DR-021). It is not an anomaly — it matches what each cell's selected band requires, from the open-loop `f(Vctrl, vdd)` table, to within 5.7 mV at every cell — and the consequence the budget guards (band plan re-cut) is **not** observed: no point leaves the measured 0.9–2.7 V window, by 53 mV at the tightest. The budget's own derivation prices a **±0.33 V** excursion where the row specifies **0.66 V**, under which reading 0 of 15 cells exceed it; which excursion governs is **#525** | **measured** (pushing; and, since DR-021, Budget 2's consumption); **derived** (the two budget *values*); Budget 2 target **not met** at 9/15 cells as the row states the excursion |
| 13 | [Output duty cycle](#output-duty-cycle) | 45 – 55 % at `CLK`, over the whole band and all corners | measured 44.375 – 50.696 % (90 points); worst `fs`/27 °C/3.63 V at the `lo` edge (band 0, Vctrl 0.9 V) — the bottom-of-band binding condition the design basis predicted | **measured** (90 points, loaded); target **not met** at 7/90 points, all at the `lo` edge |
| 14 | [Output levels and drive](#output-levels-and-drive) | rail-to-rail CMOS on `vdd_vco`: V_OH ≥ 0.9·VDD_VCO, V_OL ≤ 0.1·VDD_VCO into ≤ 50 fF external load | measured V_OH 1.006 – 1.044·VDD_VCO, V_OL −0.040 … −0.006·VDD_VCO into a 50 fF load, at every one of 90 points | **measured** (90 points); target **met** at every point |
| 15 | [Area](#area) | ≤ **0.30 mm²** total — **amended by DR-016** from the draft ≤ 0.15 mm², which was never derived from anything (DR-007 Amendment A3) and is *measured* to be unreachable, and **held** at that value by **DR-017** on a floor re-measured 17.5 % lower. The drawn blocks sum to 0.1803 mm², 0.2254 mm² after the floorplan's ×1.25 top-level overhead, **1.50×** that draft target; assuming *all* Metal2 routing is free still gives 0.1702 mm² (1.13×), and every remaining named lever is above that bound. 57.2 % of what a 0.15 mm² row allowed is consumed by two terms no layout lever touches: the loop filter (capacitance-set by DR-006) and `vco_block`'s guard-ring/tap spacing. The row is the measured total *as DR-016 measured it* plus margin sized to the one unmeasured factor in it (it now holds for a top-level overhead up to ×1.664) — **not** an allowance for block growth. It did not move with the three levers that have landed since (#469, #458, #473): per DR-017 Decision 3, a downward re-amendment now needs the *uncertainty* to shrink — an assembled `pll_top` (#17), or a drawn loop filter — not another block-level lever | n/a — drawn area is not a PVT quantity; the *capacitance* it buys is (C1 = 107.1 … 133 pF over corners) | **measured** (the four drawn blocks, off committed DRC/LVS-clean GDS via `python3 layout/run_pv.py area`); **derived** (the loop filter — DR-006's measured device area ×1.15; it has no layout); **budget** (the ×1.25 top-level overhead — no assembled `pll_top` GDS exists, #17). Target **met** at 0.2254 mm² against the amended row |
| 16 | [Lock detector](#lock-detector) | digital `lock` output; assert window within **1 … 2 ns** of phase error — i.e. ≥ the ratified Lock criterion and ≤ 2× it — at every PVT point (T1′/T2′, DR-010), **measured at the flag** (the largest phase error for which `lock` asserts and stays asserted through the assembled detector loop) rather than at the bare delay chain (DR-013 Decision 1); hysteresis ≥ 25 % of the assert window; no chatter. Conditioned on the [Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule) | **T1′ and T2′ are both met**, at the trimmed `delaywin_3v3` (DR-014, #411) with each part at the code the trim rule selects: window edge **[1.14, 1.16) ns** at `fs`/−40 °C/3.63 V (code 6, **+14 … +16 %** above the 1 ns lower edge) and **[1.78, 1.80) ns** at `ss`/125 °C/2.97 V (code 3, **10.0 … 11.0 % below** the 2 ns upper edge), each resolved to 0.02 ns at the corner it binds at. The observable's PVT spread is **1.53 … 1.58×** (≤ 1.62× as a resolution-independent bound), against DR-013 Decision 4's **≤ 1.65×** and **1.91–1.96×** for the untrimmed cell, whose edge sat at [2.02, 2.04) ns — 1.0–2.0 % past budget. Behaviour is unchanged by the trim: 0 of 205 points fail the four-check acceptance, no large static phase error and no frequency error asserted anywhere, worst deassert latency 5.63 ns. **An untrimmed part is outside this specification** — the spread at any one fixed code is 1.977–1.988× and no code holds the band. **That conditionality is not yet dischargeable on silicon** (DR-022, #501): the trim rule's measurand is internal, every quantity `pll_top`'s pads expose has now been measured against it and none selects the code to the accuracy this row's own spread figure assumes, so the rule is executable only in simulation — see [Executing the rule at test](#executing-the-rule-at-test--the-rule-is-normative-and-on-this-die-it-is-executable-only-in-simulation) | **measured** (205-point in-situ re-characterization, clean tree, plus a 1872-point code map); targets **met** (T1′/T2′), conditional on a trim rule with **no executable route on this die** (DR-022); **T4/T5 below 25 MHz still uncharacterized** |
| 17 | [Kvco](#kvco) | ≤ 150 MHz/V at every legal operating point under the [band-selection rule](#band-selection-rule) | 115.8 MHz/V at `all-fast`/27 °C/2.97 V, band 6, Vctrl 1.54 V (target 200 MHz) | **measured** |
| 18 | [Supply range](#supply-range) | 3.3 V ± 10 % (2.97 – 3.63 V), `nfet_03v3`/`pfet_03v3` only; three domains | n/a — the supply axis is the *independent* variable of every other row's corner binding | **measured** as a swept axis on every campaign |

Rows 4 and 6 are deliberately empty targets. They are listed rather than
omitted so that the omission is visible and attributable to DR-002 Decision 5,
which is exactly what a reader auditing this table for missing lines needs.

---

# Normative conditions

These two rules are part of the specification. Every number in the summary
table is stated under both of them; a part configured against either is outside
spec, and the failure mode in both cases looks like marginal stability rather
than like a configuration error.

## Band-selection rule

**A system targeting output frequency `f` must configure the lowest 3-bit band
code that reaches `f`.**

Source: DR-003 Decision 4, from `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md`
(checks 4a / 4b).

Why it is normative rather than advisory: `Kvco ∝ f_osc` *within* a band, so two
band codes that both reach the same output frequency do not present the same
gain to the loop. The higher code reaches `f` near the bottom of its Vctrl
range, where its Kvco is already large.

| Band choice | Worst Kvco inside 10–200 MHz | Against DR-001's ~150 MHz/V fixed-filter bound |
|---|---|---|
| Lowest band that reaches the target (this rule) | **115.8 MHz/V** (`all-fast`/27 °C/2.97 V, B6 @ 1.54 V) | **inside** |
| Any band that reaches the target (adversarial) | **154.3 MHz/V** (`all-fast`/27 °C/3.30 V, B7 @ 0.9 V) | **over** |

Band select is a **static configuration input** in v1 — there is no
auto-calibration FSM (DR-001 Decision 2). A part programmed into the wrong band
therefore costs loop margin as well as range, and nothing on-chip corrects it.

## Icp trim-code rule

**The 2-bit charge-pump current trim must be set from the reference frequency,
per the table below.** It is not a discretionary margin knob; it is the
mechanism that adapts the one fixed passive filter across the ratified 25:1
reference range.

Source: DR-006 Decision 5, from `sim/loop-dynamics/records/20260731-202550-82af5a9.md`
(section 6).

| f_ref | Required Icp trim (unit legs) | Worst phase margin at that code | Realized f_c | Small-signal 1 % settling | Other codes that also pass |
|---|---|---|---|---|---|
| 1 MHz | **4** | 47.4° | 25.96 – 73.8 kHz | 71 µs | none |
| 2 MHz | **4** | 60.4° | 45.21 – 154.4 kHz | 52 µs | 2, 3 |
| 4 MHz | **3** | 66.7° | 64.97 – 227.7 kHz | 54 µs | 1, 2, 4 |
| 8 MHz | **2** | 66.6° | 85.04 – 297.8 kHz | 55 µs | 1, 3, 4 |
| 16 MHz | **1** | 66.6° | 89.9 – 297.8 kHz | 55 µs | 2, 3 |
| 25 MHz | **1** | 60.0° | 135.9 – 429.5 kHz | 56 µs | 2 |

Unit-leg currents are 1.68–1.80 / 3.36–3.60 / 5.04–5.41 / 6.71–7.21 µA for
codes 00/01/10/11 across all 45 PVT corners
(`sim/cp-compliance/records/20260801-190821-734f483.md`, the `sim/harness`-
migrated successor to `20260731-194124-afa338c.md`, reproducing the same
range — DR-007 Amendment A4); the nominal code is 10 (three legs, ≈5.2 µA).

Reference frequencies between the decades above take the code of the **nearest
tabulated f_ref at or below** them; 105 of the 140 measured (f_ref, N, code)
cells pass both stability criteria unconditionally, and every one of the 35
failures is a code away from this rule, never a corner of a correctly
configured part.

## Lock-detector window trim-code rule

**The lock detector's 4-bit window trim (`LDT3:LDT0`) must be set, once per
part at test, from the part's own measured comparator-window delay at a fixed
reference condition.** It is not a discretionary margin knob and it is not a
per-application setting; it is the mechanism that holds the flag's assert
window inside the two-sided [T1′/T2′ band](#lock-detector) across the process
distribution.

Source: DR-014 (mechanism) and #411 (bit count, step, code table), from
`sim/lock-window-trim/records/20260917-185928-8adff3d.md` (1872 points, clean
tree).

**The rule.** Measure `t_win` — the `ERR → ERRD` propagation delay of
`delaywin_3v3`, a 1–2 ns quantity — at **27 °C and nominal supply (3.30 V)**,
and program the code whose `t_win` at that condition is **nearest 1.343 ns**.
"Nearest" is in the logarithmic sense, because the window's error budget is
multiplicative. The target is derived, not chosen: it is the band's own
geometric centre (√2 = 1.414 ns), divided by the measured 1.037× ratio between
the flag's observable window and the bare chain delay, times the measured
0.985 ratio between the reference condition and a bundle's geometric mean over
its own PVT box.

The reference condition is **one static measurement at one PVT point**, which
is what a production tester can hold. Nothing on-chip performs it: there is no
counter, no comparator and no state machine reading this code back, and
DR-002 Decision 4's "passive monitor, no band-search or self-calibration
hardware" boundary is unchanged by it. This is the same shape of rule as the
[Icp trim-code rule](#icp-trim-code-rule) above — *set from a fixed, known
condition*.

**What the rule selects, per simulated corner bundle**, and what the window
then does over that bundle's own nine voltage/temperature points:

| Corner bundle | Code | `LDT3:LDT0` | `t_win` at the reference condition | `t_win` over that bundle's PVT box | Codes left below / above |
|---|---|---|---|---|---|
| `ss`, `all-slow` | **3** | 0011 | 1.356 ns | 1.122 … 1.726 ns | 3 / 12 |
| `fs` | **6** | 0110 | 1.327 ns | 1.106 … 1.676 ns | 6 / 9 |
| `typical`, `sf`, and the six passive-only bundles | **7** | 0111 | 1.357–1.358 ns | 1.135 … 1.710 ns | 7 / 8 |
| `ff`, `all-fast` | **11** | 1011 | 1.363 ns | 1.152 … 1.694 ns | 11 / 4 |

That table is **illustrative, not normative** — a real part is not one of
thirteen simulated bundles. What is normative is the measurement and the
"nearest 1.343 ns" rule above; the table is what the rule produces when it is
applied to the bundles the PVT grid actually contains, and it is here so a
reader can see that the code range is well centred (the slowest bundle still
has 3 codes below it, the fastest 4 above) rather than running out at either
end.

**A part left untrimmed is outside this specification, and no single code
substitutes for the rule.** Measured over all sixteen codes: the window's PVT
spread with one fixed code is **1.977 … 1.988×** at *every* code — against a
band only 2× wide, that leaves at most ≈1 % of joint slack, and no code
actually holds it. The two closest both miss: code 6 falls to **0.9746 ns** at
`all-fast`/−40 °C/3.63 V (below the 1 ns T1′ edge) and code 7 reaches
**2.0029 ns** at `ss`/125 °C/2.97 V (above the 2 ns T2′ edge). With the rule
applied the same grid holds **1.106 … 1.726 ns**, a spread of **1.561×**.

**Step size and range**, measured rather than specified in advance
(DR-014 Decision 3 left both to this campaign): one code step is
**2.7–4.7 %** of window and the full 0 → 15 range is **1.69×**, against the
**1.31×** reference-condition spread between the fastest and slowest bundle.
The code-to-window map is **monotonic at every one of the 13 corner bundles**
— 0 of 195 adjacent steps non-monotonic — which is a property of the cell's
weighted switches and is checked per corner rather than assumed; see
`design/README.md`'s window-trim section for why an *un*weighted switch breaks
it.

### Executing the rule at test — the rule is normative, and on this die it is executable only in simulation

**DR-022 (#501).** The rule above says what code a part must carry. It does
not, and until DR-022 could not, say how anyone finds that code on a packaged
part. `t_win` is an internal node pair: neither `ERR` nor `ERRD` is a port of
`design/netlist/pll_top.spice`, and the quantity the pads *do* expose — the
flag's assert window, defined (DR-013 Decision 1) as the largest phase error
at the PFD inputs for which `LOCK` holds — is not one a bench can impose
either, because `FB` is an output of this block and no pad pair can be driven
to a known static phase offset.

**How accurate a substitute would have to be**, derived from this section's
own numbers at the measured 2.7–4.7 % trim step:

| Tier | What it protects | Tolerance on the selected code |
|---|---|---|
| **A** | the ratified [1, 2] ns T1′/T2′ band (+10.6 % / +13.7 % of margin under the rule) | never more than **2 codes low**, never more than **3 codes high** |
| **B** | DR-013 Decision 4's ≤ 1.65× spread, against the rule's own 1.610× continuous-population figure | **zero** — 2.48 % of allowance is left, and one code of bundle-dependent error costs two steps |

Tier B is the binding one, and it leaves no room: the rule's own rounding has
already spent all but 0.53 of a trim step of the spread allowance.

**What the pads can actually do**, measured over the full 13-bundle grid in
`sim/lock-window-proxy/records/20260925-050022-6d57802.md` — every candidate `pll_top`'s
pad list offers, each calibrated at one bundle and scored at the other twelve,
against a no-measurement control:

- **The free-running ring period at `CLK` is worse than not trimming at all** —
  2.434× spread against the untrimmed control's 1.984×, out of band at both
  edges, worst code error 8 of 16. Two measured reasons: the starved ring is
  biased through `ppolyf_u_3k` resistors (DR-009), so `res_ff`/`res_ss` move
  its period ∓27 % while `t_win` — all-MOS — does not move at all; and across
  the MOS axis its sign is inverted, the ring running 6 % *faster* at `ss`
  where the window is 16 % *slower*. Both ring operating points behave
  identically, so this is the topology, not the read point.
- **The `CLK`→`DIVOUT` pad-to-pad skew is the best candidate and is still not
  sufficient.** It leaves a 1.132× residual on the window's 1.316× process
  spread and holds the band at all 117 points, but at **1.697×** grid spread
  (1.74–1.78× continuous) it fails Tier B, and its worst code error of +4 is
  outside Tier A's own bound — the band survives on where this grid's thirteen
  bundles sit, not on a property of the selector. `CLK`→`FB` is worse (1.735×).

**Therefore**, and this is the normative part of this subsection:

1. **The rule is executable only in simulation on this die.** A part built
   from this netlist is **characterized at a recorded trim code**, not
   trimmed-to-rule at test. The code is a configuration of every measurement
   taken from the part and must be reported with it.
2. **No `spec/` row may be graded as met on the strength of a pad-referred
   code selection.** The `CLK`→`DIVOUT` skew is a characterization aid, not a
   trim procedure.
3. **The [Lock detector](#lock-detector) row's T1′/T2′ verdict is conditional
   on a trim no present bench or tester procedure can select** to the accuracy
   that row's own 1.53–1.58× spread figure assumes.
4. **A precondition on all of it, now met**: `pll_top` used to leave `LDT3`
   unconnected (#515), so only 8 of the 16 codes were reachable on the
   assembled part — and the table above selects code 11 for `ff`/`all-fast`.
   **DR-026 connects it**: the `XLD` instance wires `LDT3` through to the
   top-level port, all 16 codes are reachable, and
   `design/lib/check-port-connectivity.sh` fails CI if any committed netlist
   again declares a port nothing inside the subcircuit connects to. Removing
   that obstacle validated no route; it only stopped one from being defeated
   before it was tried.

**Of the two routes DR-022 named, one has now been measured and does not
work.** DR-028 (#527) characterizes the **symmetric `REF` phase-step
bisection** — step `REF`'s phase by a signed Δ with the loop locked, bisect Δ
in both directions for the thresholds at which `LOCK` drops, and take their
mean as the flag window with the loop's static offset cancelled. The deassert
*is* observable at the pad, promptly and unambiguously, at `pll_top` rather
than through a block-level loop. But **the threshold in Δ is not `t_flag`**:
the flag window is a per-reference-cycle *charge balance* in the detector's
`VWIN` integrator, while a step threshold is a *stored-charge* question —
`LOCK` drops only if the discharge integrated over the handful of cycles before
the loop absorbs the step exceeds `C_VWIN·(V_rail − V_TL)`. The step threshold
therefore exceeds the flag window by an additive time set by the integrator's
capacitance, the Schmitt trigger's falling threshold, the discharge device and
the loop's own bandwidth — **four quantities, none of them the delay chain the
trim moves, each with its own corner dependence** — so no fixed factor removes
it. Measured at the rule's reference condition (`typical`/27 °C/3.30 V, at the
rule's own code 7): the threshold is **2.200 ± 0.200 ns** against a flag window
committed evidence puts at **1.3769 … 1.4529 ns** — **+55.5 %**, which at the
measured 50.4 ps per trim code is **−12.6 codes** of selection error on a 16-code
trim. Both tiers **FAIL**, and by a margin no ladder resolution can reach: the
discrepancy is 3.7× the measurement's own bracket and 19× the reference
interval's width.

The obstacle generalizes past this particular stimulus, which is why DR-028
closes the route rather than deferring it. The flag's measurand is a
**sustained** phase error; a locked loop holds exactly its own `φ_ss` and
corrects everything else, `FB` is an output with no drive path, and so every
`REF`-side stimulus is a transient whose effect on the flag is governed by the
integrator's stored charge and the loop's correction speed. A phase ramp is no
escape (an integrating filter's steady-state phase error to a frequency offset
is zero), and eliminating the additive term with a second measurement would be
a fit against a model whose four terms vary independently — which Tier B leaves
no allowance for.

**The successor is therefore DR-022's second route**: exposing `ERR`/`ERRD`
through matched observation buffers onto two of the free digital-test-output
slots, making `t_win` a pad-to-pad edge difference with the buffers' own delays
cancelling to first order. That is a `design/` change and **still needs its own
decision record first**; neither DR-022 nor DR-028 authorizes it. What DR-028
adds to its case is that the cheaper route is not merely uncharacterized — it
is measured, and it fails on what it measures rather than on how precisely it
measures it.

---

# Parameters

## Output band

**Target: 10 – 200 MHz, continuous, at every PVT corner.**

The v1 output band is covered by the ring's own eight overlapping bands with no
post-VCO output divider (DR-002 Decision 2; the divider trigger did not fire).

| Edge | Binding corner | Measured | Margin |
|---|---|---|---|
| Floor — B0 must reach **down** to 10 MHz | `all-fast` / 125 °C / 2.97 V | 6.449 MHz | 36 % below the line |
| Ceiling — B7 must reach **up** to 200 MHz | `all-slow` / −40 °C / 3.63 V | 247.8 MHz | 24 % above the line |
| No coverage hole | `ss` / 125 °C / 3.63 V | worst adjacent-band overlap ratio 1.267 (27 %) | overlaps at all 63 corners |
| Monotonic control | — | 0 non-monotonic curves of 504 | — |

Conditions:

- the [band-selection rule](#band-selection-rule) applies at every frequency in
  the band;
- Vctrl operating window **0.9 – 2.7 V** (DR-003 Decision 5);
- 5-stage ring, and there is no fallback stage count — 3 stages does not start
  at the fast corner and floors 14 % above 10 MHz, 7 stages tops out 9 % short
  of 200 MHz at the slow corner (DR-003 Decision 2).

**The 400 MHz stretch is out of v1 scope** (DR-002 Decision 2) and is *not*
merely unbudgeted: above 200 MHz the extracted Kvco reaches 206 MHz/V, past the
fixed filter's bound, so the stretch needs a filter re-design or a finer band
map — not just more Vctrl.

Evidence: `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` (3528
points: 7 corner bundles × 3 temperatures × 3 supplies × 8 bands × 7 control
voltages; passive axes swept deliberately).

## Reference input

**Target: 1 – 25 MHz.** The 32 kHz mode is stretch-only and formally deferred
out of v1 (DR-002 Decision 1) — it is not a target design margin has to reach,
and it collides with three other rows as drafted (multiplier range, area, lock
time).

Electrical contract on the driving system — **conditions, not measured
outputs**, hence the `n/a` corner binding:

| Item | v1 requirement | Basis |
|---|---|---|
| Waveform | CMOS square wave into `REF`, referenced to the `vdd_ref` domain | design intent |
| Levels | V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD | **budget** — `sim/reference-input-contract` declares the sweep; no point of it is measured (DR-019) |
| Edge rate | ≤ 5 ns, 10–90 % | **budget** — same campaign, same state |
| Duty cycle | 30 – 70 % | **argued, not measured**: the PFD's edge detectors fire on the **rising** edge only (`design/pfd.sch`), so duty affects only pulse-width margin, not the sampled phase. `sim/reference-input-contract` states that argument falsifiably — the sampled phase must shift by ≤ 1 % of the reference-path set delay between 30 %, 50 % and 70 % duty — and does not yet test it |
| Source quality | **excluded from the jitter and spur budgets** — see below | explicit assumption, see rationale |

**None of the three lines above is measured**, and until DR-019 they were owed
from a closed issue on an unrelated subject (#12), which read as discharged.
The campaign that would discharge them now exists as a committed, self-checking
manifest and deck with **zero measured points** — `sim/reference-input-contract`
holds the DUT at `sim/pfd-deadzone`'s operating point and sweeps the `REF`
*waveform* to each boundary of this table, grading the per-corner shift of the
reference-path set delay `d_ref` (the interval from the reference edge's
mid-rail crossing to the instant the PFD acts on it — i.e. the phase the
detector sampled) against the 1 ns static-phase bound of the
[Lock criterion](#lock-time). A campaign directory is not evidence; see
[Verification owed](#verification-owed) for what is owed against each line, and
#499 for the measurement.

**Reference-source quality assumption (the "[no recorded value]" item, resolved
as an explicit exclusion rather than an invented number).** No
reference-noise-transfer measurement exists in `sim/`, and inventing a
reference phase-noise limit without one would be exactly the unsupported number
CLAUDE.md forbids. So this specification states the assumption instead: **every
jitter and spur number in this file is the block's own contribution, measured
or derived against an ideal reference.** Reference phase noise inside the loop
bandwidth transfers to the output multiplied by `20·log₁₀(N)` = 12 dB at N = 4
to 36 dB at N = 64, so a system integrating this block must budget its
reference against that multiplication itself.

**What this exclusion does and does not cover (DR-019 Decision 3).** It
excludes the *reference source's* own phase noise. It does **not** license this
block's reference-input path to contribute: that path's contribution is inside
this block's budget, not the integrator's, and is what
`sim/reference-input-contract` measures. Two things follow for an integrating
system, and the second is not covered by the `20·log₁₀(N)` line above:

- a reference whose edges sit at the ≤ 5 ns budget converts its own **amplitude**
  noise into timing noise at the input, at a rate set by the mid-rail slope —
  the campaign reports that coefficient per corner as `dtdv_worst`, in seconds
  of sampling-instant displacement per volt, so it can be budgeted; a reference
  with fast edges does not pay it;
- a reference well inside the contract still moves the *locked* reference-to-output
  phase by whatever `d_ref` shift its waveform causes, which is a static offset
  rather than jitter.

Converting the exclusion into a numeric reference-jitter limit requires the
closed-loop noise bench. This paragraph previously pointed that at **#12**,
which is closed and was never about it. It is **not** re-pointed at #13 either:
#13 is *also* closed (2026-09-08), and its bookkeeping successor #505 is
closed too (DR-023). The
honest state is that the numeric limit is **unowned**, sequenced behind the
noise methodology at #520 — and [Verification owed](#verification-owed) now
records it that way. Naming a plausible-looking owner is what hid this
obligation twice; an empty owner column is the more useful fact.

## Multiplication ratio

**Target: N = 4 – 64, every integer, no holes.**

| Check | Measured | Corner |
|---|---|---|
| Distinct N exercised at 200 MHz | 61 (N = 4 … 64) | 235 chain points |
| Points where the measured ratio was not exactly N | **0** | — |
| Retiming setup margin, N = 64 at 200 MHz | 3.03e-10 s (6.1 % of a VCO period) | `ss` / 125 °C / 2.97 V |
| Retiming hold margin | 2.00e-09 s | `ff` / −40 °C / 3.63 V |
| Feedback-edge delay spread across N at a fixed corner | 4 fs over 60 values of N | `ss` / 125 °C / 2.97 V |

Conditions:

- **N is a static configuration**, set alongside the band code; the loop
  re-locks after a change. Glitch-free on-the-fly modulus switching is out of
  v1 scope (DR-001 Decision 3).
- N and the band code must be *mutually consistent*: `f_out = N · f_ref` must
  land inside [the output band](#output-band) **and** `f_ref` inside
  [the reference input range](#reference-input). Not every (N, f_ref) pair in
  the two ranges is legal.
- The 6-cell ÷2/3 chain physically reaches N = 127. **That is spare margin, not
  a claim**: nothing above 64 is corner-verified and nothing above 64 is
  specified.
- The retiming margin above is *schematic-level* and is a difference of two
  numbers that both grow with parasitic load — it is an upper bound on the
  post-layout margin, and it is the single most important number for #18 to
  re-take before the 200 MHz ceiling is treated as closed.

Evidence: `sim/divider-ratio-chain/records/20260802-100727-082c879.md`
(chain), `sim/divider-ratio-cell/records/20260801-140529-3f883e3.md`
(single cell), `sim/divider-ratio-dff/records/20260801-125114-3f883e3.md`
(flop setup/hold) — the `sim/harness`-migrated successors to the
pre-migration `sim/divider-ratio/records/20260731-171817-0a12e6c.md` /
`…-171816-…` / `…-171815-…`, each reproducing its predecessor's measured
values (DR-007 Amendment A4).

## Integrated RMS jitter

**Not spec'd. Derived-only.**

DR-002 Decision 5 ratifies **period jitter** as the spec'd,
simulation-substantiable jitter quantity and records any integrated-RMS-jitter
figure as *derived*, not spec'd, until the flow demonstrably produces one
directly. A free-running oscillator's phase noise is not an AC `.noise` result
in ngspice, and this repo has no evidence-backed transient-noise or ISF
pipeline for it.

This row exists so the omission is **visible and attributed**, not silent. If
an integrated-jitter number ever appears in a datasheet draft or marketing
text, it must be labelled derived and sourced from the period-jitter
measurement — never presented as an independently spec'd quantity.

Corner binding: **n/a** — no target, so nothing to bind.

## Period jitter

**Target: ≤ 1.0 % of the output period, RMS**, at the output `CLK`, in lock —
**conditional on** the `vdd_vco` ripple budget below.

### The spec'd quantity, stated unambiguously

The ratified quantity is the **percentage** form: 1.0 % of the output period,
RMS. At 100 MHz that is **100 ps RMS**; at 200 MHz, 50 ps RMS.

DR-001's Context section glosses the draft line as "Period jitter < 1 % RMS
(stretch < 0.5 %) — 10 ps RMS at 100 MHz". Those two clauses differ by 10×:
1 % of a 10 ns period is 100 ps, not 10 ps. This specification resolves the
inconsistency **in favour of the percentage**, because (a) the percentage is
what DR-002 Decision 5 ratifies as the spec'd quantity, and (b) every recorded
evidence number is quoted against the percentage form (DR-003's "2.5 % RMS
against a draft spec line of < 1 %", DR-006 and the supply record likewise).
DR-001's parenthetical is a drafting error in a *Context* gloss, not in a
Decision, so nothing in DR-001's decision set is superseded by fixing it here —
but the arithmetic disagreement is recorded rather than quietly dropped.

**The < 0.5 % stretch is retained as a stretch** (uncommitted, no evidence
either way).

### The supply-ripple condition — without it this line is not ratifiable

`vdd_vco` ripple alone can break the 1 % line. Measured open-loop at 100 mV
peak-to-peak sinusoidal ripple at `f_osc/16`, over the full 63-point grid:

| | Period jitter pp | Period jitter RMS | TIE pp | TIE RMS |
|---|---|---|---|---|
| Worst — `all-slow`/−40 °C/2.97 V, f_osc = 78.52 MHz | 910 ps | 320 ps (**2.51 % of the period**) | 3.37 ns | 1.02 ns |
| Median — `ff`/−40 °C/3.63 V | 540 ps | 191 ps | 1.69 ns | 516 ps |
| Quiet reference (solver noise floor) | 2.27 ps | 0.614 ps | 9.63 ps | 2.81 ps |

The smallest margin between any rippled result and its own run's quiet
reference is 134× in TIE RMS, so these are circuit results, not solver noise.

Therefore the jitter line carries a **normative supply condition**:

> **`vdd_vco` ripple ≤ 20 mV peak-to-peak, integrated over 100 kHz – 100 MHz.**

Derivation: the measured worst-corner sensitivity is 2.51 % RMS per 100 mV pp,
i.e. 0.0251 %/mV pp. At 20 mV pp that is **0.50 % RMS** — half the budget,
leaving the other half for the random/thermal contribution that has not been
measured. The measurement is taken at a ripple frequency (`f_osc/16` ≈ 5 MHz)
an order of magnitude *above* the loop bandwidth (26–430 kHz), where the loop
does **not** correct the disturbance, so the open-loop number applies directly
at the frequencies the condition covers. Below the loop bandwidth the loop
attenuates ripple and the condition is conservative.

Ripple jitter is **not extrapolatable** from a supply step: across 90 rippled
runs the measured/predicted ratio spans 1.22 … 2.29 (median 1.45), because
`f ∝ 1/vdd` is convex. Ripple at a frequency that matters must be measured.

### Measurement configuration this line is stated at

| Item | Value |
|---|---|
| Output frequency | 100 MHz (band 5, Vctrl 1.8 V) is the reference point; the % form makes the line frequency-independent |
| Band | selected per the [band-selection rule](#band-selection-rule) |
| N / f_ref | any legal pair, with the [Icp trim-code rule](#icp-trim-code-rule) applied |
| Supply ripple | ≤ 20 mV pp, 100 kHz – 100 MHz (above) |
| Reference | ideal (see [Reference input](#reference-input)) |

### Limits of the present evidence

Open-loop, deterministic disturbances only, schematic-level, ideal supply
network, for the ripple-sensitivity figure above. **The closed-loop
deterministic component is now measured** — `sim/period-jitter/` holds six
merged records (`20260905-192724-a2ba48f` through `20260906-095050-3a8a6ef`,
#13) covering all 45 mandated PVT corners, the full temperature × supply
plane at every MOS bundle: 0.0508–0.2691 % RMS, PASS against the draft
target at every corner (see `sim/CHARACTERIZATION.md`'s `period-jitter`
row). The band sweep (1.18 % at B0 rising to 2.46 % at B6, as a fraction of
the period) is a separate, open-loop measurement that varies band rather
than temperature/supply, and was taken at nominal temperature and supply
only.

**No random (noise-driven) jitter number exists, and none is obtainable on
this toolchain** (DR-023). Every record's Methodology field discloses that
DR-002 Decision 5's specified transient-noise method (`.option TRANNOISE=1`)
injects no noise on this repo's pinned ngspice-46 build. DR-023 narrows the
reason: the device noise data is *not* the missing piece — `.noise` reports
each device's channel-thermal and flicker generators, for the gf180mcu models,
at a bias point. What is missing is any periodic-steady-state/`pnoise` path
(`pss` is not a command in this build) to weight those stationary PSDs over
the ring's switching trajectory, across which they move by 46.6 dB and
95.9 dB respectively. DR-002 Decision 5 therefore remains `proposed`, and is
**not** superseded: its method has not failed on the physics, it has not been
runnable. The measurement is owed at **#520**; the probes are committed at
`sim/period-jitter/noise-toolchain-probe/`.

**Consequently this line's 1.0 % target is not demonstrated — half of it is
an unverified budget.** Stated explicitly rather than left in the arithmetic
of the ripple derivation above:

| Component | Status | Number |
|---|---|---|
| Deterministic, closed-loop (control ripple) | **measured**, 45/45 corners | 0.0508–0.2691 % RMS |
| Supply-ripple sensitivity at the normative 20 mV pp condition | **derived** from a measured 100 mV pp open-loop sensitivity | 0.50 % RMS |
| Random / noise-driven | **budget — unverified, not measurable on this toolchain** | ≤ 0.50 % RMS *assumed*, owed at #520 |

A measured random component above 0.50 % RMS at any mandated corner would
break this split and put the 1.0 % line itself in question; DR-023
§Consequences names that as one of the conditions forcing a new record.

Evidence: `sim/vco-tuning-range/records/20260804-211600-f599a65.md`, the
`sim/harness`-migrated successor to `20260731-184845-0a12e6c.md` (DR-007
Amendment A4). The worst- and median-corner figures quoted above (910 ps /
320 ps / 3.37 ns / 1.02 ns; 540 ps / 191 ps / 1.69 ns / 516 ps) and the
worst-case 2.51 % RMS reproduce exactly; the migrated record's own "quiet
reference" solver-noise-floor row (an incidental figure, not a design
result) reads a few percent different from the value this file's own
[Period jitter](#period-jitter) table above still quotes — noted, not
silently reconciled, since it is not the number either row's own
pass/fail turns on.

## Phase noise

**Not spec'd. Derived-only, on the same basis as
[integrated RMS jitter](#integrated-rms-jitter)** (DR-002 Decision 5).

No dBc/Hz figure at any offset is committed for v1. This choice is load-bearing
upstream, not merely cautious: DR-001 Decision 1 rejected the sub-sampling and
injection-locked architectures *specifically* because their headline advantage
is a phase-noise number this flow cannot substantiate.

Corner binding: **n/a** — no target.

## Reference spur

**Target: ≤ −55 dBc**, at `f_ref` offset from the carrier, in lock, over the
ratified operating space.

Status: **measured** at five spanning PVT corners, against the derivation
below. `sim/reference-spur` (delivered by #145, **closed**) runs the assembled
`pll_top` to lock and reads the sidebands straight out of the locked output
spectrum — the first closed-loop spur measurement in `sim/`. It does **not**
retire the whole row:
it is five of the 45 PVT points, at one (f_ref, N, band, trim) operating point,
and at f_out = 150 MHz rather than the binding 200 MHz. What remains owed is
named in [Verification owed](#verification-owed).

The measurement at the binding frequency is now a **declared campaign of its
own**, `sim/reference-spur-band-top` — the full mandated 45-point PVT matrix at
f_ref = 25 MHz, N = 8, f_out = 200 MHz, Icp trim code 0, sharing
`sim/reference-spur`'s deck, spectral reduction and solver settings so the two
are comparable point for point. **Every point of it is owed**: its manifest,
deck and per-corner operating-point derivation are committed and self-checking,
and zero of its 45 points are measured (DR-024). A campaign directory is not
evidence. One property of it is a finding in its own right and is why 200 MHz
could not simply be dialled into the campaign above: the normative
[band-selection rule](#band-selection-rule) does **not** hold one band code
across the 200 MHz grid — band 6 at 34 of the 45 points, band 7 at the other 11
— so the binding-point measurement is configured per corner. Projected onto a
*static* code that split leaves four of the five MOS bundles with no single
code that reaches 200 MHz across the full ratified temperature × supply box;
that bears on [Output band](#output-band) rather than on this row and is filed
at #534, which this row does not pre-empt.

Measured — `sim/reference-spur/records/20260816-132150-5f405e7.md`, f_ref =
25 MHz, N = 6, f_out = 150 MHz, band 6, Icp trim code 0 (the trim the
[Icp trim-code rule](#icp-trim-code-rule) requires at 25 MHz):

| Corner | Measured spur at 150 MHz | Scaled to 200 MHz (`+20·log₁₀(200/150)` = +2.50 dB) |
|---|---|---|
| `sf` / −40 °C / 2.97 V | **−57.0 dBc** (worst) | **−54.5 dBc** |
| `ff` / −40 °C / 3.63 V | −57.4 dBc | −54.9 dBc |
| `typical` / 27 °C / 3.30 V | −58.4 dBc | −55.9 dBc |
| `ss` / 125 °C / 2.97 V | −63.1 dBc | −60.6 dBc |
| `fs` / 125 °C / 3.63 V | −72.7 dBc (best) | −70.2 dBc |

**Against the −55 dBc target: PASS at 150 MHz at all five corners; the two
cold corners do not clear it once scaled to the binding 200 MHz** (−54.5 and
−54.9 dBc, i.e. 0.1–0.5 dB over). The scaling is arithmetic on the
narrowband-FM relation `θ = 2π·f_out·TIE`, not a measurement — 200 MHz is not
reachable in one static band code across the PVT grid (band 6's ceiling falls
to 166 MHz at the slowest corner while band 7's floor rises to 225 MHz at the
fastest), which is why the measurement is at 150 MHz. **The bound is not
relaxed on the strength of that extrapolation**; a direct measurement at
200 MHz, per corner, is what would settle it.

How much to trust each number: the loop's slow pole is 9.3 µs and the run is
8 µs, so a residual settling drift is still present and is reported per point
as `drift_q_fc` (−1.60 … +2.78 fC, against the 2.16–3.68 fC charge-pump
asymmetry the spur is made of). It is of **either sign** — it can add to or
partly cancel the asymmetry — so an individual corner's number can be biased
in either direction, and the first-window-to-last-window spread (up to 11 dB
at `fs`) is the honest width of the per-corner uncertainty. The record's own
Methodology field calls `spur_dbc` unconditionally conservative; its own
`drift_q_fc` column disproves that, and the campaign manifest carries the
correction (records are append-only, so it is stated here rather than edited
into the record). What the five points do establish, and the derivation below
does not, is that the measured spur sits in the same −57…−73 dBc neighbourhood
the derivation predicts, by direct spectral measurement rather than by
assumption.

Derivation from the recorded dominant mechanism (charge-pump per-event charge
asymmetry landing on C2 once per reference cycle), kept as the cross-check the
measurement above is read against:

| Step | Value | Source |
|---|---|---|
| Systematic per-event charge asymmetry \|q_up + q_dn\|, worst corner | 3.68 fC (`fs`/125 °C/3.63 V, Vctrl 0.9 V) | `sim/cp-compliance/records/20260802-061841-c24ee3a.md` (the `sim/harness`-migrated switching-timing successor to `…-194124-afa338c`, reproducing the same `q_up`/`q_dn` pair at this corner — DR-007 Amendment A4) via DR-006 §8 |
| Statistical residual net charge, \|mean\| + 3σ | 2.99 fC | `sim/mc-cp-mismatch/…-212614-640560e` term 3 |
| Worst-case sum | 6.67 fC | linear add (conservative) |
| C2, worst-case minimum over corners | 1.814 pF | DR-006 Decision 1 |
| Peak Vctrl ripple, `ΔQ/C2` | 3.68 mV | — |
| Peak TIE, scaled from the recorded 0.669 ps at 1.825 mV | 1.35 ps | DR-006 §8 / loop-dynamics §7 |
| Peak phase deviation at f_out = 200 MHz | 1.70e-3 rad | `θ = 2π·f_out·TIE` |
| Single-sideband spur, `20·log₁₀(θ/2)` | **−61 dBc** | narrowband-FM |

The −55 dBc target leaves ~6 dB against that bound for the mechanisms this
derivation does not cover: UP/DN *current* mismatch during the ~1 ns
anti-backlash window (measured at 4.7 %, contributing under 1 fC per cycle, so
small but non-zero), supply and substrate coupling of `f_ref` into the VCO
rail, and layout coupling that does not exist yet. The bound improves at lower
output frequencies (−67 dBc at 100 MHz), so 200 MHz is the binding frequency as
well as the binding corner.

**That ~6 dB reserve is now ~1.6 dB, once the first mechanism it lists —
UP/DN current mismatch — is priced at its statistical 3σ instead of its
systematic value, and the table's own statistical-residual row is refreshed to
the corner-combined campaign (DR-018).** The table predates that campaign: its
statistical residual row is the *nominal-only* 2.99 fC (the corner-combined
figure is 4.25246 fC), and it excludes term-1 current mismatch entirely, on the
"under 1 fC" estimate in the paragraph above. That estimate is right for the
systematic 4.7 % (0.88 fC at the largest trim code and the worst measured reset
overlap); at the measured 3σ tail the same product is ≈ 1.35 – 1.94 fC
corner-consistent and 3.26 fC stacked, and at the ±20 % term-1 budget DR-018
derives it is 3.73 fC. Carrying those through the same chain:

| Charge accounting at 200 MHz | Total ΔQ | Derived spur |
|---|---|---|
| **Systematic asymmetry alone**, no statistical term — the row a **mismatch-off measurement** is comparable with (DR-024 Decision 4) | 3.68 fC | **−66.6 dBc** |
| The table above (systematic 3.68 fC + nominal-only statistical 2.99 fC) | 6.67 fC | **−61 dBc** |
| Corner-combined statistical residual, term 1 still excluded | 7.93 fC | −59.9 dBc |
| …plus term 1 at its **measured** 17.4798 % (signed `\|mean\| + 3σ`) | 11.19 fC | ≈ −57.0 dBc |
| …plus term 1 at its **budgeted** ±20 % | 11.66 fC | **−56.6 dBc** |

The "measured" row quotes term 1 as the signed `|mean| + 3σ` at the worst
corner (`ff`/−40 °C/3.63 V), the statistic `sim/mc-cp-mismatch` has reported
since #487. It previously quoted 13.2172 % (10.40 fC, −57.6 dBc), which was
`mean(|x|) + 3·sd(|x|)` on samples folded to their absolute value; both come
from the same committed 300 samples
(`sim/mc-cp-mismatch/testbench/run.sh --restat 20260923-095854-1655e11`). The
refresh is DR-018 Amendment A1, made under that record's Decision 3, which
pre-authorised the switch of statistic; it restates a derived row in the
conservative direction and moves nothing below.

The −55 dBc **target does not move**, and neither does the −61 dBc row, which
is retained as the historical cross-check it always was. What changes is how
much of the target's margin is spoken for: the last row above is a deliberately
conservative stack (three different worst corners added linearly, the largest
trim code, the longest overlap, and term 1 counted on top of a term-3
measurement that already contains it), but it is the honest upper bound, and it
sits 1.6 dB from the line. Read alongside the measured table's −54.5 dBc at the
two cold corners once scaled to 200 MHz, the spur row has less slack than the
−61 dBc figure alone suggests.

**Which of these rows a measurement may be read against** (DR-024 Decision 4).
Every closed-loop spur campaign in this repository — `sim/reference-spur` and
the owed `sim/reference-spur-band-top` — runs with **device mismatch off**, so
what they measure is the systematic, corner-driven spur. The comparable row is
therefore the **first** one, −66.6 dBc, *not* the −56.6 dBc stack, which adds
two statistical terms each at its own worst corner. Two things follow, and the
second is the reason this paragraph exists rather than being left to inference:

- A PASS from the binding-point campaign will not discharge the statistical
  half of this budget, and a FAIL will not by itself impeach DR-018's
  charge-pump mismatch budget. What either does is replace the binding-point
  number with a measured one. The closed-loop **statistical** spur — a
  Monte-Carlo closed-loop sideband, as distinct from `sim/mc-cp-mismatch`'s
  mismatch *charge* — is **unowned**.
- **The derivation does not predict the measurement's corner ordering.** The
  measured table above, scaled, exceeds the systematic-only −66.6 dBc by ~12 dB
  at the two cold corners (−54.5 and −54.9 dBc) while sitting 3.6 dB *below* it
  at `fs`/125 °C/3.63 V — the derivation's own worst corner — with mismatch off
  in every case. Whatever drives the cold-corner spur is not the
  charge-asymmetry term this derivation is built from. That is an argument for
  measuring at the frequency the line binds at, not for widening the line.

Closing [Verification
owed](#verification-owed)'s direct 200 MHz measurement is what would settle it;
a wider charge-pump mismatch budget is not.

The derivation's own −61 dBc lands inside the measured −57…−73 dBc range above,
which is a useful agreement and not a verification: the derivation is stated at
200 MHz and at its own worst corner, the measurement is at 150 MHz at five
corners, and the two are not the same quantity. **The −61 dBc row remains a
derivation — cite `sim/reference-spur`'s record for a measured number.**

## Loop bandwidth

**Target: f_c = 26 – 430 kHz** across the ratified (f_ref, N, corner, trim)
space, with **`f_c < f_ref/10`** as a hard ceiling.

| Quantity | Value | Binding point |
|---|---|---|
| Minimum f_c | 25.96 kHz | f_ref = 1 MHz, 4 legs |
| Maximum f_c | 429.5 kHz | f_ref = 25 MHz, 1 leg |
| Worst realized `f_c/f_ref` | `f_ref/13` | inside the ceiling at **every** point of the full cross-product, with no exception |

Conditions: the [Icp trim-code rule](#icp-trim-code-rule) and the
[band-selection rule](#band-selection-rule) both apply. A fixed passive filter
**cannot** span the ratified 25:1 reference range on its own — read down a
column of the trim table and the loop is too slow at low f_ref and too fast at
high f_ref. The trim code is what closes that gap.

As-built filter (DR-006 Decision 1), the values these bandwidths are measured
against:

| Element | Device | Drawn | Typical (27 °C, Vctrl 1.8 V) | Min … max over 27 passive bundles × 3 temperatures |
|---|---|---|---|---|
| R | 4 × `ppolyf_u` in series | W = 2 µm, L = 107 µm each | 77.1 kΩ | 61.6 … 93.4 kΩ |
| C1 | 4 × `cap_nmos_03v3_b` | 87 × 87 µm each | 120.8 pF | 107.1 … 133 pF |
| C2 | 1 × `cap_mim_2f0_m2m3_noshield` | 31.4 × 31.4 µm | 2.02 pF | 1.81 … 2.22 pF |

`C1/C2 ≈ 60`, **not** DR-001's placeholder `C1/C2 = 10`, which does not clear
45° of phase margin at the top of the reference range (DR-006 Decision 2).

Evidence: `sim/loop-dynamics/records/20260731-202550-82af5a9.md` — 405 filter
curves (27 passive bundles × 3 temperatures × 5 in-window Vctrl points) ×
25 loop-gain points × all legal N × all 4 trim codes, cross-checked against an
independent whole-loop AC simulation agreeing to 0.000 % in f_c and 0.000° in
phase margin.

## Phase margin

**Target: ≥ 45°** at every point of the contracted operating space.

DR-001 states the `f_c < f_ref/10` ceiling but no phase-margin number; DR-006
Decision 3 adopts 45°, and this specification carries it.

| Quantity | Value |
|---|---|
| Worst phase margin under the [Icp trim-code rule](#icp-trim-code-rule) | **47.4°** at f_ref = 1 MHz, 4 legs |
| Cells passing both criteria unconditionally | 105 of 140 (f_ref, N, code) |
| Cells failing | 35 — **every one at a trim code away from the rule**, never a corner of a correctly configured part |

f_ref = 1 MHz has **no alternative trim code**: 4 legs is the only code that
passes there, so that row of the rule has the least configuration slack as well
as the least margin.

## Lock time

**Target: < 100 µs**, cold start, to the lock criterion below.

**The < 20 µs stretch is dropped from this specification.** It is not
re-scoped, deferred, or carried as a reach goal — it is removed, for a
structural reason:

- 0 of 140 measured (f_ref, N, trim-code) cells reach it;
- settling saturates at **≈43 µs** regardless of how much Icp is applied,
  because the slowest closed-loop pole sits near `1/(2πRC1)` = 17.09 kHz — a
  property of the fixed filter, not of the drive level;
- reaching it would require reopening DR-001 Decision 1's fixed-filter
  constraint (a bandwidth-boost-during-acquisition scheme, which needs a
  band-search FSM DR-001 Decision 2 keeps out of v1).

DR-001's hand calc predicted exactly this and DR-006 Decision 7 confirmed it
with measured data. Carrying an unreachable stretch value in a ratified table
would be the "Not simulated" failure DR-001 §Prior art explicitly warns against.

**Lock criterion** (the "[no recorded value]" item, resolved):

> The loop is **locked** when, continuously for **≥ 20 consecutive reference
> cycles**, both hold: `|Δf_out / f_target| ≤ 0.1 %` (1000 ppm) **and** the
> static phase error at the PFD inputs is `≤ 1 ns`. Lock time is measured from
> enable-release (cold start, Vctrl = 0) to the start of that window.

Rationale for the two thresholds: 0.1 % is comfortably inside the fine
resolution the loop can hold and is a decade tighter than any band-overlap
margin; the 1 ns phase bound is set where the [lock detector](#lock-detector)'s
measured window sits (0.877 … 1.702 ns), so the criterion and the on-chip
observable are describing the same event rather than two different ones. The
20-cycle hold excludes a late re-acquisition from counting as lock.

**Both thresholds are absolute, and the phase one deliberately does not scale
with f_ref.** The `lock_detector` window is an inverter-chain delay — a fixed
number of nanoseconds — so a criterion expressed as a fraction of a reference
period would stop describing the same event as the flag watching it, and
DR-010's T1′/T2′ (which tie that window to this criterion's value) would lose
their anchor. A testbench judging this quantity therefore cites the 1 ns
itself; a per-period proxy is not an acceptable substitute, and one campaign
was found applying a 1.6× looser one (DR-012 Decision 5).

**This criterion is not met at every mandated corner today, and the axis it is
lost on is the control voltage.** Closed-loop, the loop settles at 1.227 ns of
static phase at `ff`/27 °C/3.63 V and 1.049 ns at `typical`/−40 °C/3.63 V —
nominal skew, systematic only, at f_ref = 12.5 MHz / N = 8 / Icp b1b0 = 10.
Open-loop, the charge pump's residual per-cycle charge nulls at a static offset
that grows steeply toward the bottom of DR-001 Decision 2's ratified 0.9–2.4 V
control window: at Vctrl = 0.90 V it exceeds this entire criterion by itself at
**36 of the 45** mandated corners (worst 1.873 ns), while at 1.65 V and 2.40 V
it exceeds it at none. The criterion is therefore reachable over most of the
control window and not at its bottom. It is **not** relaxed to accommodate that
(DR-012 Decision 1); the gap is recorded against the design in
[Verification owed](#verification-owed).

**Which of those two closed-loop corners is evidence about a *compliant* part
is narrower than it looks, and the band plan does not fix either (DR-025).**
The 1.227 ns at `ff`/27 °C/3.63 V was measured at band 6; over DR-003
Decision 5's measured 0.9–2.7 V control window the normative
[band-selection rule](#band-selection-rule) selects **band 5** at that cell,
which parks the control node at 1.967–2.595 V rather than 1.008–1.394 V — and
that configuration has never been run closed-loop, so the corner is neither
cleared nor confirmed. The 1.049 ns at `typical`/−40 °C/3.63 V is at the
rule-selected band under every reading and stands. Applying the rule is
nevertheless **not** a resolution: swept across the ratified 10–200 MHz output
band it still parks some corner at `Vctrl ≤ 1.05 V` at 23 of 39 output
frequencies — floor **0.919 V**, at `ss`/125 °C/2.97 V, f_out = 135 MHz — and
still misses this criterion on DR-012 Decision 4a's summed budget at 1397 of
1628 rule-selected points. The resolution has to reduce the pump's residual
charge at low Vctrl; no band plan substitutes for it
(`sim/supply-sensitivity/records/20260925-090649-4422f1d.md`).

| Quantity | Value | Binding point |
|---|---|---|
| Worst small-signal 1 % settling **under the trim rule** | 71 µs | f_ref = 1 MHz, 4 legs |
| Best | 52 µs | f_ref = 2 MHz, 4 legs |
| Structural settling floor | ≈43 µs | set by `1/(2πRC1)` |
| Cells meeting < 100 µs across the whole cross-product | 120 of 140 | the 20 failures are all off-rule trim codes |
| Cells meeting < 20 µs | **0 of 140** | — |

**Limitation, and it is a large one.** These are *small-signal settling*
estimates from a fitted 3-element model. Cold-start acquisition involves cycle
slipping and the VCO's large-signal nonlinearity, and is #163's number, not
this one. The < 100 µs target above is therefore **measured for settling and a
budget for cold start**; see [Verification owed](#verification-owed).

**A second limitation, and it is a different one: this specification states no
bound on re-lock after a mid-operation supply excursion** (DR-011). Every
number above is cold-start — from enable-release at `Vctrl = 0`. A supply step
*during* operation is a different disturbance, and the only evidence about it
is a lower bound: after a 3.30 → 3.63 V step (+10 % of nominal, 100 ns edge),
`lock` had **not** re-asserted **34.4 µs (3.70 τ)** later at 2 of the 3
sampled corners, with the static phase still decaying monotonically at that
instant (`sim/supply-sensitivity/records/20260901-155456-46b92f8.md`, the
escalated 40.08 µs high-plateau hold; classified as a settling tail rather
than a structural miss by `.../20260915-105055-2d6ab99.md` and
`.../20260915-124108-49f539f.md`). Arithmetic on that data brackets the
recovery at 37.2 … 42.6 µs after the step edge — at or below this loop's own
≈43 µs cold-start settling floor, so **nothing in evidence indicts the loop
filter** (DR-011 Decision 1) — but that bracket is a two-sample extrapolation
and `46b92f8` §3c's `under-damped` result at one of the same corners is
inconsistent with the model it rests on
(`.../20260915-202323-62391c6.md`). **A consumer gating logic on `lock` must
therefore treat post-excursion re-lock as unbounded above 34.4 µs** until
#395 measures it. Only 3 of 45 corners, one excursion size, and one
(f_ref, N, trim-code) cell have been run on that deck at all.

## Power

**Target: < 5 mW at 100 MHz output, in lock, all supply domains summed.**

Domain definition: `vdd_vco` (constant-gm bias + band mirrors + V→I converter +
5-stage ring + output buffer + on-chip decap) + `vdd_div` (÷2/3 chain, output
mux, retiming flop) + `vdd_ref` (PFD, charge pump, `cp_dumpbuf`, lock
detector). All three are separate pins (DR-001 Decisions 2 and 3).

Derived total at the binding corner — `all-fast` / 125 °C / 3.63 V:

| Domain | Current at 100 MHz | Power at 3.63 V | Basis |
|---|---|---|---|
| `vdd_vco` | 318 µA | 1.15 mW | **measured** — worst of 159 grid points with 90 ≤ f_osc ≤ 110 MHz (`vco_tuning.csv`); best is 133 µA at `all-slow`/−40 °C/2.97 V |
| `vdd_div` | ≈179 µA | 0.65 mW | **derived** — measured 16.95 µA worst at 10 MHz and 357 µA worst at 200 MHz; the two decades scale linearly to within 6 %, so 100 MHz interpolates cleanly |
| `vdd_ref` | ≲50 µA | ≲0.18 mW | **budget** — not separately measured; `cp_dumpbuf` alone is ≈16 µA (≈53 µW) by design, plus two polarities of ≤7.2 µA charge-pump legs and the PFD's dynamic current at f_ref ≤ 25 MHz |
| **Total** | **≈547 µA** | **≈1.98 mW** | **derived** |

That is 2.5× inside the 5 mW target at the worst corner measured so far.

**The < 2 mW stretch is retained as a stretch, uncommitted.** The derived total
lands right on it, which means the stretch is not obviously out of reach and is
equally not demonstrated — the `vdd_ref` line is a budget, the `vdd_div` line
is an interpolation, and none of it is a closed-loop measurement. Promoting the
stretch to a target requires #14.

Note that power binds at the **fast/hot/high-supply** corner, not at the
cold corner: at the fast corner the same 100 MHz is reached at a higher band
code and a higher Vctrl, so the starving current is larger.

## Standby current

**Waived: there is no power-down or standby mode in v1. The block is always-on
whenever its rails are powered.**

This is an explicit statement, not an omission. There is no enable, power-down,
or shutdown pin anywhere in `design/`, and neither DR-001 nor DR-002 scopes
one. A standby-current row with a number would imply a state the block cannot
enter.

Consequences a system integrating this block must plan for:

- the only way to stop the block drawing current is to remove its rails, and
  after that it must re-acquire lock from cold start ([lock time](#lock-time));
- there is no fast wake path, because there is no state to wake from.

If a future revision adds an enable pin, it needs its own decision record and
its own row here — including what the enable does to the Vctrl node, which is
the highest-impedance node in the block and the one most damaged by being
floated.

Corner binding: **n/a** — no standby state exists.

## Supply sensitivity

Two normative budgets, plus the characterized open-loop sensitivity they are
derived from. This is the most load-bearing row in the table for a
current-starved ring, and DR-001 Decision 2 accepted the underlying weakness
with eyes open.

### Budget 1 — AC: `vdd_vco` ripple ≤ 20 mV peak-to-peak, 100 kHz – 100 MHz

Derived in [Period jitter](#period-jitter) and repeated here because it is the
condition a system integrator has to design the rail against. Above the loop
bandwidth the PLL does not correct this disturbance at all.

### Budget 2 — DC: a full-range rail excursion must consume ≤ 0.6 V of the Vctrl window

With the loop closed and locked the output frequency is set by `N·f_ref`, so DC
supply pushing does not appear as a frequency error — it appears as a **Vctrl
re-positioning**, and the Vctrl window is finite (0.9–2.7 V, 1.8 V wide).

Derivation: a ±10 % (±0.33 V) rail excursion moves the open-loop frequency by
up to 17 %. The loop cancels that by moving Vctrl by `0.17 / (Kvco/f_out)`, and
`Kvco/f_out` spans 0.31 … 0.84 per volt across bands and corners, so the
required Vctrl shift is **0.20 V (high-Kvco bands) to 0.55 V (low-Kvco bands)**
— up to 31 % of the window. The 0.6 V budget above covers the worst of that
with a small allowance; if a future change pushes it past 0.6 V, the fine
tuning range left inside a band is no longer enough to hold lock across the
rail range and the band plan has to be re-cut.

**This budget is now measured, and it is missed — at 9 of the 15
(bundle, temperature) cells of the mandated grid.** With the loop closed and
locked at every one of the 45 mandated points, the control node moves
**0.385 … 0.846 V** across the 2.97–3.63 V rail. The worst cell is
`ss`/−40 °C at **0.846 V** — **1.41×** this budget, and **47 %** of the 1.8 V
window consumed by the rail alone (`sim/supply-sensitivity/records/20260925-044237-4ff4f65.md`,
arithmetic on the committed 45-point grid of `.../20260901-155456-46b92f8.md`;
DR-021 Decisions 3 and 4). Three things a reader has to be told alongside that
number, because each changes what it means:

- **The measurement is not anomalous.** It agrees with what each cell's own
  selected band requires, read off `sim/vco-tuning-range`'s committed open-loop
  `f(Vctrl, vdd)` table, to within **5.7 mV at every one of the 15 cells** and
  1.9 mV (0.2 %) at the worst. The loop is absorbing exactly the pushing
  characterized below, with nothing left over; nothing in this number indicts
  the charge pump, the loop filter or the VCO.
- **The derivation above prices half the excursion this row specifies.** Its
  17 % is `%/V × 0.33 V` — the same arithmetic the pushing table below uses for
  its own "worst frequency shift over a ±10 % rail" column — so the
  0.20 … 0.55 V it predicts, and the 0.6 V sized to cover that "with a small
  allowance", are for a **0.33 V** excursion, while the row demands the shift
  over **0.66 V**. Read over 0.33 V, **0 of the 15 cells** exceed the budget
  (worst 0.431 V, 28 % inside). The factor of two is in the numerator, not the
  denominator: the measured `Kvco/f_out` at the worst cell's band is 0.429/V,
  inside the 0.31 … 0.84/V assumed above, and 17 % / 0.429 is 0.396 V. Which
  excursion this row governs is a ratification question and is **#525**; until
  it is answered the row reads as it is written, i.e. missed. The budget's
  normative text is deliberately unchanged — relaxing a ratified line to make a
  result pass is not an option available here.
- **The failure mode this budget protects against is not observed, and the
  margin left is 53 mV.** The band holds lock across the rail at every one of
  the 45 points: **none** leaves the measured 0.9–2.7 V control window
  (DR-003 Decision 5). The tightest margin anywhere is **53 mV**, at
  `ss`/−40 °C/3.63 V (ripple peak 2.647 V against the 2.7 V edge); the next
  tightest are the three −40 °C band-6 cells at the window's *bottom*, at
  +78 … +91 mV. So the budget is exceeded and its stated consequence — re-cut
  the band plan — is 53 mV away on a measured, not estimated, consumption.

**A related grading defect, stated rather than left in the deck.**
`sim/supply-sensitivity`'s own criterion 1b does not grade this budget at all;
it grades whether the control node stays inside DR-001 Decision 2's
*predicted* 0.9–2.4 V window, which **DR-003 Decision 5 superseded** with the
measured 0.9–2.7 V above. Its recorded "4 of 45 outside the window" FAIL is
against that superseded figure and does not reproduce against the current one.
Correcting the deck to grade the ratified budget is part of #525, per DR-012
Decision 5 (where this specification ratifies a value, the deck cites that
value); every run until then, including #437's full-grid re-take at the trimmed
detector window, reproduces the same gap.

### Characterized open-loop pushing (what the budgets are derived from)

| Band | Most negative | Median | Least negative | Worst frequency shift over a ±10 % rail |
|---|---|---|---|---|
| B0 | −35.3 %/V | −29.0 %/V | −24.1 %/V | 12 % |
| B4 | −50.7 %/V | −41.3 %/V | −33.7 %/V | 17 % |
| B7 | −50.1 %/V | −44.6 %/V | −32.7 %/V | 17 % |

- Worst point: **−50.7 %/V** at `ss` / −40 °C, band 4, Vctrl 1.8 V (measured on
  the purpose-built 7-supply-point bench). The coarser tuning-range grid, which
  sweeps all eight bands at three supply points, reports −52.31 %/V at
  `ss`/−40 °C, B5, Vctrl 2.1 V — consistent, and quoted here so the two records
  are not read as disagreeing.
- Best: −24.1 %/V at `ff` / −40 °C, band 0.
- Pushing is **linear** across the whole ±10 % rail (worst departure from a
  straight-line fit is 2.26 % of f_nom), so one coefficient per corner is fair.

**This is structural, not a sizing error.** A current-starved ring runs at
`f ≈ I_stage/(n·C_stage·V_swing)` and `V_swing` *is* the supply, so even a
perfectly supply-independent starving current carries a `−1/vdd` term =
**−30.3 %/V** at 3.3 V. The measured median of −39.4 %/V is 1.30× that floor;
the bias generator contributes only the remainder. Reducing pushing materially
needs a regulated VCO rail or a swing-independent cell — the alternatives
DR-001 Decision 2 considered and rejected.

**The condition that reopens DR-001 Decision 2 is now explicit and measurable**:
if the system cannot deliver a rail inside Budget 1, the delay-cell choice must
be revisited, and `sim/vco-tuning-range/records/20260804-211600-f599a65.md`
(the `sim/harness`-migrated successor to `20260731-184845-0a12e6c.md`,
DR-007 Amendment A4) is the evidence that would drive it.

Supply-step response, for a loop-bandwidth budget: a 0.1 V step walks the
open-loop output edge by −25.7 ns/µs (best) to **−60.8 ns/µs** (worst,
`all-slow`/−40 °C/2.97 V) for as long as the loop takes to correct it. That is
why the loop bandwidth cannot be set arbitrarily low.

## Output duty cycle

**Target: 45 – 55 % at `CLK`, over the whole output band and all PVT corners.**

Status: **measured — 90/90 points, target not met at 7.** Measured on a
loaded `CLK` (50 fF, the same load [Output levels and drive](#output-levels-and-drive)
uses) at the two extremes of the ratified band-code/Vctrl window (band 0 /
Vctrl 0.9 V = `lo`, the slowest starved edges; band 7 / Vctrl 2.7 V = `hi`,
the fastest), across all five MOS process bundles and the full temperature/
supply grid (`sim/output-driver/records/20260817-100354-0e9cfc9.md`, 90
points). Measured duty cycle spans **44.375 – 50.696 %**. 7 of the 90 points
fall below the 45 % floor — **all seven are at the `lo` edge**: `ff`/−40 °C/
3.30 V (44.7873 %), `fs`/−40 °C/3.30 V (44.5683 %), `fs`/−40 °C/3.63 V
(44.894 %), `fs`/27 °C/3.30 V (44.4337 %), `fs`/27 °C/3.63 V (44.375 %, the
worst point), `fs`/125 °C/3.30 V (44.9554 %), `fs`/125 °C/3.63 V
(44.7828 %). Every `hi`-edge point clears the floor with margin
(47.26 – 50.696 %). No point exceeds the 55 % ceiling in either direction.

Design basis for believing it is reachable: the delay cell's PMOS head and NMOS
tail are *matched* — sized for equal charge and discharge current — so the
ring's duty stays near 50 % without the output buffer having to recover it
(`design/README.md`, delay cell §), and the buffer is a symmetric three-stage
tapered inverter chain.

Design basis for the ±5 % width rather than something tighter: DR-001
Decision 2's Consequences state plainly that duty cycle at the VCO output "is
not controlled to better than the cell's rise/fall symmetry", and that the
answer to a *tight* duty requirement is an output ÷2 — which halves the usable
output band and forces a VCO band re-plan. **A duty spec tighter than ±5 % is
therefore a scope change, not a design tweak**, and this row is written at the
loosest width a consumer of a clock is likely to accept so that the trade never
gets made by accident.

**Binding condition, confirmed by measurement**: the **bottom** of the band,
where the starved ring's internal edges are slowest and the buffer's first
stage is doing the most squaring — not the top, matching the design-basis
prediction above. The shortfall is concentrated in one process bundle: 6 of
the 7 failing points are `fs` (fast-NMOS/slow-PMOS) at the two higher supply
rails (3.30 V and 3.63 V) across all three temperatures — every `fs`/`lo`
point at the nominal-or-above rail fails, while the `fs`/2.97 V points at the
same edge pass. The seventh failing point, `ff`/−40 °C/3.30 V, is the one
excursion outside that pattern. The worst point is 0.625 percentage points
below the 45 % floor — small in absolute terms, but systematic within the
`fs` bundle rather than a single outlier. This gap is a design finding, not a
missing measurement — see [Verification owed](#verification-owed) for what
post-extraction work remains.

## Output levels and drive

**Target: rail-to-rail CMOS on the `vdd_vco` domain — V_OH ≥ 0.9·VDD_VCO,
V_OL ≤ 0.1·VDD_VCO — driving ≤ 50 fF of external load plus the on-die divider
input, over the whole output band and all corners.**

Status: **measured — 90/90 points PASS.** `CLK` driving an ideal 50 fF
capacitor to `GND_VCO` (the external-load half of the budget; see
Limitations below for the on-die divider input, which this record does not
add), swept at the same 90-point grid as
[Output duty cycle](#output-duty-cycle)
(`sim/output-driver/records/20260817-100354-0e9cfc9.md`). Measured V_OH spans
**1.006 – 1.044·VDD_VCO** (min at `ff`/125 °C/3.63 V, max at `ss`/125 °C/
2.97 V) and V_OL spans **−0.040 … −0.006·VDD_VCO** (most negative at
`ss`/125 °C/2.97 V, least at `ff`/125 °C/3.63 V) — both comfortably inside
the ≥ 0.9 / ≤ 0.1 budget at every corner, with V_OL's small negative values
coming from post-edge ringing into the load cap rather than a floor
violation. The loaded 10–90 % edge rate (the drive-strength proxy) ranges
from ~84 ps (fastest `hi`-edge corners) to ~16 ns (slowest `lo`-edge
corners) at the well-behaved points, tracking the ring's own edge-rate
extremes as expected — with one data-quality caveat: 5 of the 180 `trise`/
`tfall` readings (all at `hi`-edge, sub-nanosecond-period corners) came back
negative, a threshold-ordering artifact of the same kind
[Output duty cycle](#output-duty-cycle)'s methodology documents for
`thigh` (ngspice's `trig`/`targ` measure clauses search independently and
are not guaranteed ordered at these edge rates), not a physical negative
transition time. Excluded from the range above; see Limitations.

What *is* known beyond the measurement:

- `CLK` is driven by a three-stage tapered inverter buffer (×3 per stage,
  1.25/0.5 → 3.75/1.5 → 11.25/4.5 µm) on `VDD_VCO`/`GND_VCO`, with ≈22 pF of
  on-chip decoupling on that domain (`design/README.md`).
- The first buffer stage is deliberately small so it does not burn crowbar
  current on the ring's slow internal edges and inject it back into the VCO
  rail — so the buffer's drive is set by its *last* stage, and its input-side
  behaviour is what the band floor depends on.
- Frequency is measured at `CLK` rather than at a ring node specifically so
  that the record proves the buffer squares the ring's slow internal edges into
  a rail-to-rail clock at the bottom of the band.

**Limitations of the measurement** (full detail in the record's own
Limitations field): the 50 fF load is external-only — the on-die divider's
own input capacitance is not additionally modelled, so both this row's and
[Output duty cycle](#output-duty-cycle)'s numbers are mildly optimistic
relative to the assembled chip; the corner sweep is MOS-only (passives held
typical); only the two band/Vctrl extremes are swept, not the full band plan;
schematic-level, no layout parasitics; clean DC supply, no ripple; and
Vctrl is open-loop (a fixed DC source), isolating this measurement from loop
dynamics. Post-extraction re-run and the divider-input-capacitance addition
are owed to #18 — see [Verification owed](#verification-owed).

**Consequence of the domain choice, stated because it is easy to miss**: the
output clock's levels ride on `vdd_vco`, the same rail the
[supply-sensitivity](#supply-sensitivity) budgets constrain. A system that
regulates `vdd_vco` to meet Budget 1 changes the output swing at the same time.

## Area

**Budget: ≤ 0.30 mm² for the whole block — amended by DR-016 from the draft's
≤ 0.15 mm², and held there by DR-017.** The draft number was never derived
from anything — DR-007's review raised it as Amendment A3, "the one `budget`
row in the table with no rationale behind the number at all" — and the design
is now measured at **0.2254 mm²**, 1.50× that draft target, which itself stays
out of reach even with every Metal2 track in the design assumed to route for
free (0.1702 mm², **1.13×**). DR-016 is the amendment and carries the full
derivation; **DR-017** (#476) re-measures the floor after three reduction
levers, holds the row where DR-016 put it, and is what the table below is
refreshed onto.

**This row is no longer a budget for the drawn blocks.** Four of the five items
are **measured**, read from committed, DRC-clean, LVS-matched GDS by
`python3 layout/run_pv.py area`; the fifth (the loop filter) is **derived**
from DR-006's measured device area, because the loop filter has no layout.
What *is* still a **budget** is the top-level overhead factor: no assembled
`pll_top` GDS exists (#17), so nothing has measured it.

Measured at `main` @ `8c6cb7f3` (2026-09-23), reproducible with
`python3 layout/run_pv.py area`; the per-block rows are
[`layout/evidence/area-audit/area-audit.md`](../layout/evidence/area-audit/area-audit.md),
which `layout/tests/test_area_audit.py` re-derives from the committed GDS and
byte-compares on every test run:

| Item | As-drawn | % of the 0.30 mm² row | Status |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 0.0369 mm² (36,936 µm²) | 12.3 % | **derived** — DR-006's 32,118 µm² of *measured* device area (C1 30,276 at the measured 3.988 fF/µm², R 856, C2 986) ×1.15 for bulk taps and interconnect. Not measured: the loop filter has no drawn layout |
| `vco_block` (172.52 × 184.48 µm) | 0.0318 mm² (31,826 µm²) | 10.6 % | **measured** — committed GDS bbox |
| `pfd_cp` (344.98 × 74.30 µm) | 0.0256 mm² (25,630 µm²) | 8.5 % | **measured** — committed GDS bbox (folded at #455, glue bus packed at #469, glue inverters interleaved at #473) |
| `divider_chain` (1317.66 × 41.99 µm) | 0.0553 mm² (55,329 µm²) | 18.4 % | **measured** — committed GDS bbox (macro band packed at #454, tracks routed over the device rows at #458) |
| `lock_detector` (294.80 × 103.75 µm) | 0.0306 mm² (30,586 µm²) | 10.2 % | **measured** — committed GDS bbox |
| **Sum of block footprints** | **0.1803 mm² (180,307 µm²)** | **60.1 %** | |
| **× the floorplan's ×1.25 top-level overhead** | **0.2254 mm² (225,384 µm²)** | **75.1 %** | **budget** — ROM multiplier; no assembled `pll_top` exists to measure it (#17) |

**Met, at 0.2254 mm² against 0.30 mm².** The 24.9 % margin on the block-sum
allowance is sized to exactly one thing — the unmeasured ×1.25 factor, which
the row now carries up to **×1.664** before it fails — and is not an allowance
for block growth. It was 0.2733 mm² / 8.9 % / ×1.372 when DR-016 was ratified;
three routing-track levers have since landed (#469, #458, #473, in
`PLL-FLOORPLAN.md` §5.12–§5.14), taking the block sum down 17.5 %. **The row
did not move with them**, and DR-017 §Decision 1 states why in one sentence: a
margin sized to an uncertainty does not shrink because the measurement it sits
on top of shrank. Nothing has yet measured the ×1.25, and the loop filter still
has no layout.

**Why 0.15 mm² was not reachable, stated as a measurement** (DR-016 §Context,
re-derived at DR-017 §Context): two terms no layout lever touches consume
57.2 % of the 120,000 µm² of block footprint that a 0.15 mm² row allowed — the
loop filter (36,936 µm², set by DR-006's C1/C2 *capacitance*, so reducing it
moves [Loop bandwidth](#loop-bandwidth) and [Phase margin](#phase-margin), not
layout) and `vco_block` at its own ceiling (31,654 µm², whose height *is* its
device band, its 60.8 % whitespace being the guard-ring and 15 µm tap-pitch
spacing the foundry deck requires). DR-016's two bounds have since converged on
one, because #458 spent exactly the `divider_chain` term that separated them:
assuming **all** Metal2 routing is free gives 0.1702 mm² (**1.13×**), a bound
that survives any row fold and that every remaining named lever is also above.

**Reduction is still tracked, and a lower row now needs a *measurement*, not a
lever**: one unnamed `lock_detector` lever remains open, and DR-017 Decision 3
replaces DR-016 Decision 4's "any lever landing is grounds" trigger with a
narrower one — this row is re-amended downward when an assembled `pll_top`
(#17) turns the ×1.25 overhead into a measurement, or when the loop filter is
drawn and its 36,936 µm² (20.5 % of the block sum) stops being a calculation.
Further block-level reduction refreshes the table above; it does not move the
row.

Corner binding: **n/a** — drawn area does not vary with PVT. What *does* vary
is the capacitance that area buys: C1 spans 107.1 … 133 pF over the 27 passive
corner bundles × 3 temperatures, and moves only 1.6 % across the 0.9–2.7 V
Vctrl window (the body-tied connection is what buys that; the raw
`cap_nmos_03v3` has a 45× C–V ratio over the same span).

The 32 kHz reference mode is excluded partly on this row: it would need
single-digit-nF loop-filter capacitance, roughly 0.9 mm² — about **6× the
entire block budget** as that exclusion was ratified against the draft
≤ 0.15 mm² (DR-002 Decision 1), and still **3×** the amended ≤ 0.30 mm² row, so
the exclusion stands unchanged.

## Lock detector

**A digital `lock` status output is in v1 scope** (DR-002 Decision 4),
implemented as a phase-error window comparator — a passive monitor, explicitly
**not** bundled with any band-search or self-calibration FSM.

**Targets** (the "[no recorded target]" item, resolved; T1/T2 replaced by
T1′/T2′ per DR-010 — see the gap discussion below for why the original pair
could not be satisfied):

| # | Target | Rationale |
|---|---|---|
| T1′ | Assert window ≥ **1 ns** — the ratified [Lock criterion](#lock-time) itself — at every point of the mandated PVT grid | a part that *meets* the criterion must always be able to assert `lock`; a window narrower than the criterion at any corner is a false negative on a genuinely locked part |
| T2′ | Assert window ≤ **2 × the ratified Lock criterion** (2 ns), at every point of the same grid | the flag must not assert far outside the criterion it observes. 2× is the stated reach — **re-derived and left unchanged** by DR-013 Decision 2 against the loop's own measured static phase offsets — and this is the direction whose failure is unsafe for a consumer gating logic on `lock` |
| T3 | Hysteresis ≥ **25 % of the assert window** | so the flag cannot chatter at the window edge |
| T4 | Deassert latency ≤ **1 reference period** at every f_ref in 1–25 MHz | a consumer gating logic on `lock` needs the deassert to be prompt at the *bottom* of the reference range, which is where the present design is weakest |
| T5 | No chatter at any corner, at any f_ref in 1–25 MHz | measured today at 25 MHz only |

**"Assert window" means the observable, not the delay** (DR-013 Decision 1).
T1′ and T2′ bound *the largest phase error at the PFD inputs for which `lock`
asserts and stays asserted*, measured through the assembled detector loop
(`sim/lock-detector`'s `window_edges` table). That is **not** the same quantity
as the `ERR → ERRD` delay `t_win`: `WIDE = ERR · ERRD` is high for only
`terr − t_win`, so a phase error just past `t_win` makes a WIDE pulse of a few
tens of picoseconds that the `MDNW`/`VWIN` charge network cannot act on, and
the flag keeps asserting for a further **δ** — measured at **+1.4 … +3.3 %** at
`ff`/−40 °C/3.63 V and **+1.7 … +7.0 %** at `ss`/125 °C/2.97 V, i.e. larger at
the corner where T2′ binds. An isolated-delay-chain campaign cannot see δ, so
no T1′/T2′ verdict may rest on one alone.

**The window is trimmed, and every number below is conditioned on the
[Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule).**
`delaywin_3v3` carries a 4-bit static process trim `LDT3:LDT0` (DR-014, sized
by #411): each of the four delay stages is loaded by one always-on
`nfet_03v3` MOS capacitor plus four binary-weighted switched segments. The
code is set once at test from the cell's own delay at a fixed reference
condition and held for the life of the part — it is not a runtime knob and
nothing on-chip writes it, so DR-002 Decision 4's "passive monitor, no
band-search or self-calibration hardware" boundary is unchanged. A part left
untrimmed is outside this specification: measured over all sixteen codes, the
window's PVT spread at any **one** fixed code is 1.977 … 1.988×, and neither of
the two codes that come closest holds the band (code 6 falls to 0.9746 ns at
`all-fast`/−40 °C/3.63 V, code 7 reaches 2.0029 ns at `ss`/125 °C/2.97 V).

**And the condition cannot presently be discharged on a part** (DR-022, #501).
Every number in this section is conditioned on the trim rule, and the rule is
executable only in simulation: its measurand is internal, and
`sim/lock-window-proxy` has now measured every quantity `pll_top`'s pads
expose against it — the best of them, the `CLK`→`DIVOUT` skew, holds the
[1, 2] ns band across the 13-bundle grid but lands at a 1.697× spread against
DR-013 Decision 4's ≤ 1.65×, while the free-running ring period is worse than
not trimming at all. The full statement, and the two-tier accuracy bound a
future route must clear, is
[Executing the rule at test](#executing-the-rule-at-test--the-rule-is-normative-and-on-this-die-it-is-executable-only-in-simulation).

**Measured behaviour** (`sim/lock-detector/records/20260919-002812-1b12179.md`,
205 points, clean tree — the trimmed cell driven through the assembled
detector loop with each corner bundle at the code the trim rule selects for it
(#411); supersedes `20260916-122705-98c935b.md`, which measured the untrimmed
W = 9.5 µm cell over the same claim). The code-to-window map itself — step,
range, monotonicity, and the code table the rule produces — is
`sim/lock-window-trim/records/20260917-185928-8adff3d.md`, 16 codes × the full
13-bundle grid, 1872 points:

| Metric | Value | Corner |
|---|---|---|
| Points failing the four-check behavioural acceptance | **0** of 205 | — |
| Points where a large static error or a frequency error falsely asserted | **0** | — |
| Comparator window `t_win` (the delay, *not* the target's observable) | 1.108 … 1.740 ns | min at `fs`/−40 °C/3.63 V (code 6), max at `ss`/125 °C/2.97 V (code 3) |
| Assert time from cold start, deep in lock | 0.680 … 1.913 µs | max at `ss`/125 °C/2.97 V |
| Worst deassert latency after a perturbation | 5.63 ns | `sf`/125 °C/2.97 V |
| **Window edges — the T1′/T2′ observable** (asserted up to / did not assert from) | 1.14 ns / 1.16 ns at `fs`/−40 °C/3.63 V (code 6, T1′ binds); 1.78 ns / 1.80 ns at `ss`/125 °C/2.97 V (code 3, T2′ binds) | each resolved to 0.02 ns at the corner it binds at |
| Margin at each edge | **+14 … +16 %** above T1′'s 1 ns; **10.0 … 11.0 % below** T2′'s 2 ns | — |
| PVT spread of the observable (T2′ edge ÷ T1′ edge) | **1.53 … 1.58 ×**, against DR-013 Decision 4's ≤ 1.65 × | bounds, not a point |

**The spread figure does not depend on the ladder's resolution at any corner
other than those two.** `ERR` is a pulse exactly as wide as the phase error and
`ERRD` is that same pulse delayed by the (non-inverting, four-stage) chain, so
`WIDE = ERR · ERRD` opens at the chain's **rising**-edge delay and closes when
`ERR` itself falls: `WIDE` is empty for every phase error below that delay, the
flag cannot assert below it, and the observable is therefore never smaller than
it. The delay in question is the record's `twin_r` column — **not** `twin_f`,
which sets only how long `WIDE` would persist after `ERR` fell and never gates
the assert. This record measures `twin_r` at all 205 points and its minimum
there is 1.1084 ns (`fs`/−40 °C/3.63 V, code 6), which caps the spread at
1.80 / 1.1084 = **1.62 ×** whatever the unresolved edges at the non-binding
ladder corners turn out to be. (`twin_f`'s own minimum is lower, 1.0849 ns at
the same corner, and 1.80 / 1.0849 = 1.66 × — that number is *not* a bound on
this observable, and is spelled out here so a reader working from the adjacent
column does not derive it as one.)
What is *not* resolved to 0.02 ns is the edge at `ff`/−40 °C/3.63 V
and `ss`/−40 °C/3.63 V, where only the coarse ladder ran: each asserts at
1.0 ns and not at 1.2 ns, so T1′ is met at both but the margin there is bounded
only to [0, 20) %. See [Verification owed](#verification-owed).

**Gaps, recorded rather than papered over:**

1. **T2′ is now met, and the history of how is worth keeping** (DR-010 →
   DR-013 → DR-014 → #411). It was missed twice, by two different mechanisms,
   and each miss changed the shape of the problem rather than just its size.

   *First miss — the sizing was measured on the wrong quantity.* DR-010 sized
   the untrimmed cell to W = 9.5 µm against `sim/lock-window-sizing`'s ladder,
   which drives `delaywin_3v3` in isolation from an ideal voltage step and
   measured 1.956 ns at `ss`/125 °C/2.97 V — in-band, +2.2 % margin. Driving
   the same cell through the assembled loop (XOR → delay chain → `WIDE`/`VWIN`
   charge network → Schmitt trigger) from a realistic PFD-modeled UP/DN edge
   rate put the flag's own edge at **[2.02, 2.04) ns — 1.0–2.0 % past the 2 ns
   budget**. The delay itself reproduced in situ to within 0.9 %; the rest of
   the gap was **δ**, the residual `WIDE` pulse the charge network cannot act
   on, which the targets' observable includes and an isolated chain
   structurally cannot see. **DR-013 Decision 1** makes that permanent: no
   T1′/T2′ verdict may rest on an isolated-chain measurement.

   *Second miss — no sizing of that topology could have met it.* The chain's
   PVT spread is a property of the chain, not of its sizing: 1.928× at
   W = 8 µm, 1.906× at W = 26 µm, so a 3.25× sizing change buys 1 % of spread.
   Against a band only 2× wide that leaves ≈ 0 % of joint slack, before
   extraction (#18) or mismatch. **DR-013 Decision 2** re-derived T2′'s 2×
   reach and left it **unchanged** — at W = 9.5 µm the flag's window had
   already risen past the loop's *own* settled static phase offset at
   `typical`/−40 °C/3.63 V (1.140 ns in situ against DR-012's settled
   1.049 ns) and to within 6 % of it at `ff`/27 °C/3.63 V, so the reach had no
   room to widen into without licensing the flag to assert on exactly the
   parts DR-012 identifies as the design's real gap. **Decision 4** put the
   requirement on the *spread* instead: ≤ **1.65×** over the mandated grid, a
   2× band with 10 % of margin per edge, where 10 % per edge is derived from δ
   alone measuring up to 7 % at the binding corner.

   *The fix.* **DR-014** picked the mechanism — a fixed, test-set trim code in
   the same idiom as the [Icp trim-code rule](#icp-trim-code-rule), not a
   bias-referenced delay and not a self-calibration FSM — and **#411**
   implemented it and re-characterized T1′–T5 under it. The trim removes the
   *process* axis post-silicon; what is left is the voltage/temperature spread
   *within* one process bundle, measured at 1.471× (`ff`) … 1.538× (`ss`),
   plus the quantization of rounding to the nearest code. Four bits at a
   2.7–4.7 % step were chosen on measurement, not preference: a first build
   with three bits on a 2 µm unit segment measured a 4.9–6.8 % step, which
   leaves the continuous-population spread at 1.631× against the 1.65× target
   — 1.2 % of margin, smaller than δ itself
   (`sim/lock-window-trim/records/20260917-180533-92bd3ee.md`, 936 points, is
   that build's own record and is kept as the evidence for the bit count).

   *What it measures.* Through the assembled loop, with each bundle at its own
   code: **[1.14, 1.16) ns** at `fs`/−40 °C/3.63 V and **[1.78, 1.80) ns** at
   `ss`/125 °C/2.97 V — T1′ met with +14 … +16 %, T2′ met with 10.0 … 11.0 %
   to spare, and a spread of **1.53 … 1.58×** (bounded at 1.62×) against
   ≤ 1.65×. **T1′ binds at a different corner than it did untrimmed** — `fs`,
   not `ff` — because with every bundle pulled toward the same
   reference-condition target, which bundle ends up narrowest at its own PVT
   extreme is a measured question rather than "the fastest one".

   *What this does not fix.* The trim is schematic-level and mismatch-free
   like everything else here: a segment-to-segment mismatch inside one stage's
   binary array would appear as trim DNL, and #18 must re-take both the code
   map and this verdict after extraction. The two erosions DR-010 named as
   unquantified — extraction and device mismatch — are still unquantified, and
   the margin above is what there is to absorb them.

2. **T1′ is met, and was already met before the trim.** At the trimmed cell it
   closes between 1.14 and 1.16 ns at the narrowest corner
   (`fs`/−40 °C/3.63 V, code 6), **+14 … +16 %** above the ratified 1 ns Lock
   criterion; the untrimmed W = 9.5 µm cell closed between 1.04 and 1.06 ns at
   `ff`/−40 °C/3.63 V, +4–6 %. Both resolve the gap DR-010 was decided against:
   as drawn at
   W = 8 µm the window was 0.877–1.702 ns, 12 % *below* T1′ at that same
   corner, so a part meeting the criterion could fail to assert `lock`. It is
   **not** a change to the integrating capacitor: `WIDE = ERR · ERRD` fires
   when the error pulse outlasts the `ERR → ERRD` delay, so the phase
   threshold *is* that delay, and `MCW`/`VWIN` set the assert/deassert time
   constants (T4's subject) instead.

   **The original T1/T2 could not be satisfied at all**, which is why DR-010
   replaced them with T1′/T2′ in the first place. T1 (≥ 2.5 ns) is a
   *minimum*; "do not assert far outside the criterion" is a *maximum*; and
   the delay chain's fixed ≈1.92× PVT spread means the smallest sizing
   meeting T1 at every corner is W = 26 µm, where the window reaches
   **4.924 ns** — the flag would assert on a part 4.9× outside the very
   criterion it exists to observe. T1/T2's premise was that the window must
   cover "the worst-case static phase offset the loop actually stands off in
   lock" — 0.671 ns systematic worst-corner plus 0.576 ns statistical
   (`mc-cp-mismatch` term 4, |mean| + 3σ) plus 0.239 ns of divider-retiming
   flop clk→Q mismatch, up to ≈1.49 ns summed, and worse at the top of the
   reference range because the charge-derived component scales as `ΔQ/Icp`
   while the [trim rule](#icp-trim-code-rule) mandates the *smallest* Icp
   (1 leg, ≈1.7 µA) at f_ref ≥ 16 MHz. But ≈1.49 ns is **itself already
   outside** the ratified ≤ 1 ns Lock criterion: a part standing off that much
   phase is not locked, and a flag refusing to assert there is correct.

   **The systematic term is not a worst case and may not be quoted as one**
   (DR-012 Decision 4). 0.671 ns is `pfd-deadzone`'s worst corner
   (`ff`/125 °C/3.63 V) **at f_ref = 25 MHz with the control node pinned at
   1.65 V** — one point on a surface the term varies over by up to **87×** at a
   fixed corner (`ss`/−40 °C/2.97 V: 0.0089 ns at 1.65 V, 0.778 ns at 0.90 V),
   and by at least 4× at every one of the 45. Re-measured across DR-001
   Decision 2's ratified 0.9–2.4 V control window at the closed loop's own
   f_ref = 12.5 MHz (405 points,
   `sim/pfd-deadzone/records/20260916-051356-8cedbba.md`), it rises to
   **1.873 ns** at the window's bottom — 2.8× the cited figure — and at
   Vctrl = 0.90 V it exceeds the entire ratified 1 ns criterion **by itself at
   36 of the 45 corners**, leaving nothing for the other two terms. At 1.65 V
   and 2.40 V no corner does. The **reference frequency is nearly irrelevant**
   by comparison: at the cited corner and 1.65 V, halving f_ref moves the term
   only from 0.671 ns to 0.628 ns (−6.4 %). So the ≈1.49 ns sum above is the
   budget **at mid-window**; at the bottom of the control window the same three
   terms sum to ≈2.69 ns. The axis this criterion is lost on is the **control
   voltage**, not the PVT corner — and the budget never named it.

   **A separate, larger finding this does not fix**, restated on better
   evidence by **DR-012** (#394). The loop **does** miss the ratified ≤ 1 ns
   Lock criterion in its own undisturbed steady state, and no window change can
   make it do so without making the flag lie — but not at the corner this
   paragraph previously named. `sim/supply-sensitivity`'s 45-point
   steady-state grid, re-read as a population in
   `records/20260916-051708-8cedbba.md`, settles at **1.227 ns** at
   `ff`/27 °C/3.63 V and **1.049 ns** at `typical`/−40 °C/3.63 V — both
   stationary to ≈11 ps across the run's late window and cross-checked from
   the PFD's UP/DN pulse-width difference to better than 2.3 %. The
   **1.796 ns** previously quoted for `ff`/125 °C/3.63 V is **not a steady
   state**: that run was stopped at ≈1.3 of the loop's slowest time constant
   with the phase still falling (2.518 ns one window earlier), so it is an
   upper bound on a decaying tail and the settled value there is unmeasured.
   The detector agrees with the criterion at both settled violations — each
   carries `FAIL:lock` in the source record — which is Decision 4 of DR-010
   reporting correctly, not failing. **DR-025 later narrows which of the two
   is evidence about a rule-compliant part** — `ff`/27 °C/3.63 V was run at a
   band the [band-selection rule](#band-selection-rule) does not select — and
   changes nothing about the detector's behaviour at either. See
   [Verification owed](#verification-owed).
3. **T4/T5 are unverified below 25 MHz.** The detector was characterized at
   f_ref = 25 MHz only. Its assert hold-off is an *absolute* time set by a weak
   pull-up charging a MOS cap, so at the 1 MHz bottom of the reference range
   the hold-off is of order one reference period, where the flag would be
   expected to **chatter**. The record makes no claim at 1 MHz, and neither
   does this specification.

Item 3 is open and is listed in [Verification owed](#verification-owed);
items 1 and 2 are kept above as the history of two targets that are now met,
not as open gaps.

**Corner binding**: `ss` / 125 °C / 2.97 V at code 3 for the window width, the
assert time and the deassert latency; `fs` / −40 °C / 3.63 V at code 6 for the
*narrowest* window. T1′ therefore binds at `fs` / −40 °C / 3.63 V and T2′ at
`ss` / 125 °C / 2.97 V — the two edges of the band bind at opposite corners,
which is why the window must be checked against the whole grid at once rather
than at a nominal point, and why no single geometric re-size could fix T2′
without risking T1′ (see gap 1 above). **Which bundle T1′ binds at is itself a
measured result, not "the fastest one":** untrimmed it was `ff`, and with the
trim rule applied it is `fs`, because every bundle is pulled toward the same
reference-condition target and which one ends up narrowest at its own PVT
extreme then depends on that bundle's own voltage/temperature spread
(in situ at 4 ns of phase error: `fs` 1.1221 ns, `ss` 1.1357 ns, `typical`
1.1434 ns, `sf` 1.1450 ns, `ff` 1.1598 ns). Neither edge moves when the eight
passive
corner bundles are added to the five MOS ones: `delaywin_3v3`'s load is an
`nfet_03v3` wired as a MOS capacitor, not a device from the PDK's `moscap`
family, so the window rides entirely on the MOS axis (measured over all 13
bundles, in the 117-point-per-sizing sizing ladder in
`20260915-202802-79c0cee`, in the 117-point-per-code trim map in
`20260917-185928-8adff3d`, and in this record's own 117-point PVT grid).

Note that the window is an **absolute** number of nanoseconds (it is an
inverter-chain delay), so the *phase* band it implies is a fixed time, not a
fixed fraction of a cycle — it is a much tighter fraction of a cycle at 25 MHz
than at 1 MHz.

## Kvco

**Target: ≤ 150 MHz/V at every legal operating point** — "legal" meaning under
the [band-selection rule](#band-selection-rule). This is the bound DR-001
Decision 1's fixed passive filter is sized against, and DR-006 sizes the real
filter against the per-band table rather than against the bound.

**Kvco is specified as a per-band, per-corner table, not a single coefficient**
(DR-003 Decision 3). The interface is
`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_band.csv` and
`kvco_by_point.csv`.

| Band | Kvco min (MHz/V) | Kvco max (MHz/V) | max Kvco/f_out (per V) |
|---|---|---|---|
| B0 | 1.722 | 4.702 | 0.71 |
| B1 | 2.767 | 7.910 | 0.71 |
| B2 | 4.649 | 13.33 | 0.73 |
| B3 | 7.556 | 23.95 | 0.74 |
| B4 | 12.84 | 45.32 | 0.76 |
| B5 | 21.42 | 81.52 | 0.78 |
| B6 | 38.50 | 135.3 | 0.80 |
| B7 | 67.32 | 205.9 | 0.84 |

| Case | Worst Kvco | Verdict |
|---|---|---|
| Inside 10–200 MHz, band chosen per the rule | **115.8 MHz/V** at `all-fast`/27 °C/2.97 V, B6 @ Vctrl 1.54 V | **inside** the 150 MHz/V bound |
| Inside 10–200 MHz, adversarial band choice | 154.3 MHz/V at `all-fast`/27 °C/3.30 V, B7 @ Vctrl 0.9 V | **over** — this is why the rule is normative |
| Above 200 MHz (the deferred stretch) | 205.9 MHz/V at `all-fast`/125 °C/2.97 V, B7 @ Vctrl 1.5 V | far over; the stretch needs a filter re-design |

Within the v1 band Kvco spans **3.182 … 154.3 MHz/V** across bands and corners.
`Kvco/f_out` spans **0.31 … 0.84 per volt** and rises monotonically with band
code — it **brackets** DR-001's 0.7/V design-intent hand calc rather than
confirming it, and DR-003 Decision 3 withdraws that hand calc as a design
value. Reading 0.7/V as a single number under-predicts Kvco in the top bands,
which are the ones nearest the ceiling where the filter has least margin.

**Uncharacterized**: band-select mirror **mismatch**. Every cited record runs
with `sw_stat_mismatch = 0`, and mirror mismatch directly perturbs the 1.65×
ratio the band-overlap margins depend on.

## Supply range

**Target: 3.3 V ± 10 % (2.97 – 3.63 V).** Device flavor: gf180mcu **3.3 V
thick-oxide** (`nfet_03v3` / `pfet_03v3`) **exclusively** — no dual-flavor
design (DR-002 Decision 3). The **1.8 V core variant is formally deferred past
v1**; DR-001 and DR-002 both record it as a different block, not a variant.

Three separate supply domains, as a pin-list commitment (DR-001 Decisions 2 and
3, and `design/README.md`):

| Domain | Contents | Why separate |
|---|---|---|
| `vdd_vco` / `gnd_vco` | constant-gm bias, band mirrors, V→I converter, 5-stage ring, output buffer, ≈22 pF on-chip decap | the ring is the block's supply-sensitive element; [supply sensitivity](#supply-sensitivity) is written against *this* rail |
| `vdd_div` | ÷2/3 chain, output mux, retiming flop | keeps divider switching noise off the VCO rail |
| `vdd_ref` | PFD, charge pump, `cp_dumpbuf`, lock detector | reference-domain switching, and the charge pump's own bias |

Corner binding: **n/a** — the supply is the independent variable every other
row's corner binding is stated against. All three supply points (2.97 / 3.30 /
3.63 V) are swept on every campaign.

---

# Consumers

**This block's consumers are part of its spec** (2am cross-cutting rule 9,
`2AMLogic/2am` `REUSE.md` §"Adopt or record", ratified 2am#899, widened
2026-09-21 to same-PDK sub-blocks and cross-repo clock interfaces). A repo
becomes a consumer of this block exactly when `2AMLogic/2am` `repos.yml`
records a `consumes: [gf180-pll]` edge on it. **As of a live read of that
file at commit `9032d1d`, 2026-09-21, three repos do**: `gf180-tmds-tx`,
`gf180-usb2-phy`, and one private full-chip canary. Each gets a row set
below. "Unknown" is a legitimate row value (the consumer states no bound);
an unnamed consumer or an unstamped row is not.

The machine-readable integrator view this section's Meets/Unknown column is
checked against — top cell, port list, netlist/GDS paths, measured area,
maturity rung — lives at [`manifests/integrator.json`](../manifests/integrator.json),
not duplicated here.

## gf180-tmds-tx — DVI-mode TMDS transmitter (gf180mcu)

[`gf180-tmds-tx`](https://github.com/2AMLogic/gf180-tmds-tx) `README.md`
(§Scope, read at commit `8578f8b`, 2026-09-15) states: *"Not in scope: the
PLL. It comes from a sibling canary; specify the interface to it, including
the jitter budget, and stop."* — the sibling is never named. The numeric
interface contract is `spec/tmds-tx.md` §2 / DR-0004, read at the same
repo's commit `595b5c1` (2026-09-15):

| Requirement | Consumer's value (`gf180-tmds-tx` @ `595b5c1`) | This block's ratified spec | Verdict |
|---|---|---|---|
| Reference input | 27.000 MHz, single-ended CMOS, ±100 ppm | [Reference input](#reference-input): 1 – 25 MHz | **Not met** — 27.000 MHz is 2 MHz (8 %) above the ratified 25 MHz ceiling |
| Output ("bit-rate clock"), 720p60 target | 742.5 MHz | [Output band](#output-band): 10 – 200 MHz, ratified; measured ceiling 247.8 MHz at one fast-corner point (`all-slow`/−40 °C/3.63 V) is evidence, not a ratified extension | **Not met** — over 3.7× the ratified ceiling, and over 3× even the unratified measured point |
| Output ("bit-rate clock"), 480p fallback | 270 MHz | same | **Not met** — 35 % over the ratified 200 MHz ceiling, and 9 % over the unratified 247.8 MHz measured point |
| PLL-attributable jitter | ≤ 0.10 UI peak-to-peak on the bit-rate clock (≈135 ps @ 742.5 MHz, ≈370 ps @ 270 MHz) | [Period jitter](#period-jitter): ≤ 1.0 % of the output period, RMS — a different quantity (RMS-of-period vs. peak-to-peak-in-UI) at a different frequency | **Unknown** — no closed-loop jitter measurement exists at either requested frequency (both are outside the ratified band), and the unit mismatch means an in-band number would still need an explicit conversion before comparison |
| Clock relationship | bit-rate and pixel-rate clocks delivered as a fixed, edge-aligned 10:1 pair | n/a — this block has one output (`CLK`) and a static integer divider ratio `N` = 4 – 64 in the *feedback* path, not a second, pixel-rate output | **Not met as stated** — supplying both outputs described would need a second divided output or a different integration architecture, neither of which exists here |

Both requested frequencies exceed the ratified [output band](#output-band)
ceiling, and the reference frequency separately exceeds the ratified
[reference input](#reference-input) ceiling. This is the mismatch
[`gf180-tmds-tx#194`](https://github.com/2AMLogic/gf180-tmds-tx/issues/194)
(open, `loom:operator-only` as of 2026-09-21) exists to resolve, naming three
options: (a) this repo extends its output band, (b) `gf180-tmds-tx` takes a
lower-rate clock and multiplies/serializes locally, or (c) a different,
named clock source. **This section does not decide that question.**
Extending the ratified [output band](#output-band) past 200 MHz is a scope
change [Output band](#output-band) already prices as non-trivial: past
200 MHz the extracted Kvco reaches 206 MHz/V, past the fixed loop filter's
bound, so the stretch needs a filter re-design or a finer band map, not just
more Vctrl — it is not undertaken by this PR. When `gf180-tmds-tx#194`
decides, the outcome is carried here as a spec row change or a new decision
record.

## gf180-usb2-phy — USB 2.0 device PHY (gf180mcu)

[`gf180-usb2-phy`](https://github.com/2AMLogic/gf180-usb2-phy) records
`consumes: [gf180-pll]` in `2am/repos.yml` (@ `9032d1d`) with the comment
*"clock source not yet named in the repo; the kit PLL per product's block
matrix"*. That repo's own ratified spec (`spec/usb2-device-phy.md` §7, read
at commit `e831a7b`, 2026-09-05) states a **12 MHz external
crystal/resonator** as its reference clock and a 12 MHz UTMI interface
clock — it names no PLL-derived clock requirement anywhere in its ratified
target table.

| Requirement | Consumer's value (`gf180-usb2-phy` @ `e831a7b`) | This block's ratified spec | Verdict |
|---|---|---|---|
| Any clock this block would supply | **Unknown** — not stated in `gf180-usb2-phy`'s own ratified spec; the `repos.yml` edge comment itself says the source is unnamed | n/a — nothing named to check a ratified row against | **Unknown** |

## Private full-chip canary

`2am/repos.yml` (@ `9032d1d`) records a third `consumes: [gf180-pll]` edge,
on a private full-chip canary. Per this repo's own `CLAUDE.md` ("nothing
about ... the contents of other 2AM Logic repositories belongs in this
one"), no requirement rows or other content from that repo are reproduced
here — a private repo is also not a public audience for a public spec
section. What is stated publicly is the edge's existence and its date. If
that consumer's own requirements are ever made public, this section gains a
row set for it the same way the two above have one.

## Mechanism for future consumers

A new row set is added here the same way the three above were: a `consumes:
[gf180-pll]` edge appears in `2AMLogic/2am` `repos.yml`, this section
records the consumer's stated requirements (or the literal value `Unknown`
where none is stated, with a note naming where was checked) against this
block's ratified rows, and a verdict is recorded. Findings about a
consumer's *own* block belong on that consumer's repo, not here (the
`sky130-sar-adc#346` pattern cited in `2am/REUSE.md`) — this section records
what a consumer *requires* of this block, not defects in the consumer's own
design.

---

## Anchor index

Every anchor `sim/` cites against `spec/pll.md#…`, and where:

| Anchor | Section | Cited by |
|---|---|---|
| `#output-band` | [Output band](#output-band) | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md`, `…-081628-239e73b.md`, `sim/vco-tuning-range/testbench/run.sh` |
| `#kvco` | [Kvco](#kvco) | same three |
| `#supply-sensitivity` | [Supply sensitivity](#supply-sensitivity) | `sim/vco-tuning-range/records/20260804-211600-f599a65.md` (migrated successor to `20260731-184845-0a12e6c.md`, DR-007 Amendment A4), `…-100401-07f4b7b.md`, `sim/vco-tuning-range/testbench/run_supply.sh` |
| `#period-jitter` | [Period jitter](#period-jitter) | same three, plus `sim/README.md`'s worked example |
| `#lock-time` | [Lock time](#lock-time) | `sim/README.md` worked example, `sim/harness/README.md`, `sim/harness/cli.py` |

**Two deliberate non-anchors.** A mechanical
`git grep 'spec/pll.md#' -- 'sim/*'` also matches two strings that are *not*
citations and for which no section is created here:

- `spec/pll.md#anchor` in `sim/README.md` — metasyntax in the sentence that
  *defines* the citation format ("a ratified spec line (`spec/pll.md#anchor`)").
- `spec/pll.md#example` in `sim/tests/test_harness.py` — a fixture string in a
  unit test for the harness's claim-string handling.

Neither is a claim made by an evidence record, so neither creates an obligation
on this file. Every other match resolves to a section above.

## Verification owed

What this specification asserts that `sim/` does not yet substantiate. Each
line is a *known* gap, listed so that a reader auditing the table does not have
to reconstruct it from the status column.

| Row | What is owed | Whose campaign |
|---|---|---|
| [Period jitter](#period-jitter) | any **random** (noise-driven) jitter number at all — the closed-loop **deterministic** component (and the temperature/supply sweep it was taken over) now exists at all 45 mandated PVT corners, the full temperature × supply plane (`sim/period-jitter/`, 0.0508–0.2691 % RMS, PASS against the draft target at every corner); the random component remains unmeasured, and **not measurable on this toolchain** — not for want of device noise models, which `.noise` supplies per device and per mechanism, but because no periodic-steady-state/`pnoise` path exists on this repo's pinned ngspice-46 (`pss` is not a command in it, and `TRANNOISE` injects nothing) to weight those stationary PSDs over the ring's own switching trajectory, across which they move by 46.6 dB (thermal) and 95.9 dB (flicker). Re-derived rather than assumed: `sim/period-jitter/noise-toolchain-probe/`. **The 0.50 % RMS this row's [supply-ripple derivation](#period-jitter) leaves for the random/thermal contribution is an unverified budget, not a result** — see DR-023 §Decision 3 | #520 (`period-jitter`, random component); [DR-023](decision-records/DR-023-random-period-jitter-owner-and-cyclostationary-gap.md) re-points this row off the closed #13 (and its since-closed successor, #505) |
| [Period jitter](#period-jitter) | the **output-band** axis of that sweep — the temperature × supply axis is retired by the row above, but every measured closed-loop point is at band 6 / f_out = 150 MHz, so no jitter number exists at the binding f_out = 200 MHz top of [Output band](#output-band), and the open-loop band sweep (B0 → B6) remains nominal temperature and supply only. The 200 MHz sweep is now a declared campaign of its own, `sim/period-jitter-band-top` — its 45-point grid, manifest, deck and per-corner operating-point derivation are committed and self-checking, and **every measured point of it is still owed** (`sim/CHARACTERIZATION.md`'s "Period jitter — band sweep at non-nominal temp/supply" row). That derivation already shows the normative [band-selection rule](#band-selection-rule) does not hold one band code across the 200 MHz grid (band 6 at 34 of the 45 points, band 7 at the other 11), so the loop gain the one fixed filter sees varies 1.6× across it against 1.05× across the 150 MHz grid | **#503** (`period-jitter-band-top`, the campaign run). Re-pointed off closed issue #13 by DR-020 Decision 3 — attribution only; that decision makes no statement about this row's measurement, which is a deterministic campaign with no dependence on DR-020's noise finding. #496, which also held this work, closed 2026-09-25 |
| [Reference spur](#reference-spur) | **the mandated 45 PVT points at the binding f_out = 200 MHz** — restated from "the remaining 40 points [at 150 MHz], and a direct 200 MHz measurement" by DR-024 Decision 3, because completing the 150 MHz grid would produce 40 more numbers that still have to be scaled by +2.50 dB before they can be read against this row's line. The closed-loop measurement itself exists at 150 MHz (`sim/reference-spur/records/20260816-132150-5f405e7.md`, 5 spanning corners, not superseded), and its two cold corners do **not** clear −55 dBc once scaled to 200 MHz (−54.5 and −54.9 dBc). The binding-point sweep is now a declared campaign of its own, `sim/reference-spur-band-top` — 45-point grid, manifest, deck and per-corner operating-point derivation committed and self-checking, **zero measured points**, blocked on fleet access (#499) rather than on mechanism. Its derivation shows the normative [band-selection rule](#band-selection-rule) does not hold one band code across the 200 MHz grid (band 6 at 34 of the 45 points, band 7 at the other 11), which is why the measurement is configured per corner; the per-part consequence of that split is #534's, not this row's. **Not owed against this row**: the statistical half of the spur, which no closed-loop campaign here measures — see the derivation's own "which of these rows a measurement may be read against" | **#533** (`reference-spur-band-top`, the campaign run). Re-pointed off closed issue #145 by [DR-024](decision-records/DR-024-reference-spur-binding-point-owner-and-mismatch-relation.md) Decision 1 — attribution and scope; no target moves. The closed-loop **statistical** spur is **unowned** |
| [Lock time](#lock-time) | cold-start acquisition including cycle slipping — the closed-loop measurement itself now exists (`sim/lock-time/records/20260831-052456-effc505.md`, full 270-run PVT × N grid against the design's own `lock_detector` criterion): 22 PASS / 233 FAIL / 15 ERROR of 270; most `cold` FAILs read as a transient window too short for the detector to assert rather than a broken loop, and the majority of `relock` FAILs are not yet attributed to a cause (see `sim/CHARACTERIZATION.md`'s `lock-time` row and #284). **The re-take of that grid is no longer held.** DR-013 Decision 7 held it until #411 landed a window meeting Decision 4's ≤ 1.65× spread target, because the grid's verdicts are taken against the design's own `lock_detector` and would otherwise be read against a window that was about to move. #411 has landed that window (`sim/lock-detector/records/20260919-002812-1b12179.md`, observable spread 1.53–1.58×, T1′ and T2′ both met), so the hold is **released** and the re-take is owed on its own merits. Anyone re-running it must configure the lock detector's trim per the [Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule) — the 233 FAILs above were taken against the untrimmed cell and are not comparable point-for-point to a re-take at the rule's codes | #163 (`lock-time`); hold released by #411 |
| [Reference input](#reference-input) | **the input-threshold / edge-rate / duty sweep** — every point of it. `sim/reference-input-contract`'s manifest, deck and reduction are committed and self-checking, and **zero of its 288 declared points are measured** (the full mandated 45-point PVT grid × six `REF` waveform variants — the ideal pulse every other record here drives, plus one at each stated boundary of the [Reference input](#reference-input) contract and one at all three at once — plus an 18-point detector-gain slice at three corners). What is owed there is compute, not mechanism or design. The three lines it would discharge stay **budget** until it has a record; a campaign directory is not evidence | **#499** (`reference-input-contract`) |
| [Reference input](#reference-input) | a numeric reference-jitter limit to replace the current exclusion — which needs the closed-loop noise bench, i.e. this repository's noise methodology, **not** the closed-loop lock bench. **It has no owner, and this row now says so rather than naming one.** Its prerequisite is the noise methodology tracked at #520 (the successor to issue #505, closed, which was itself the successor to issue #13, closed too — DR-023); the reference-jitter limit is a further measurement on top of that and is unowned today. The exclusion itself is defensible and is restated with its boundary in [Reference input](#reference-input); what is owed is the number, and its input-side half (`dtdv_worst`, the AM-to-PM coefficient at the worst legal reference slope) is a deliverable of the campaign in the row above | **unowned** — sequenced behind #520 |
| [Power](#power) | a measured `vdd_ref` domain current, and a closed-loop total | #14 (`supply-sensitivity`) |
| [Supply sensitivity](#supply-sensitivity) | **Budget 2 is measured and missed, and what is owed is the decision, not the measurement** (DR-021): the closed loop consumes 0.385 … 0.846 V of the control window across the ratified 2.97–3.63 V rail, over the 0.6 V budget at **9 of the 15** (bundle, temperature) cells, worst `ss`/−40 °C at 1.41×. Three residuals. (a) **Which excursion the row governs** — its derivation prices ±0.33 V, under which 0 of 15 cells exceed the budget, while the row specifies the 0.66 V full range; the row is read as written until this is ratified, and the deck's criterion 1b must then grade the ratified budget instead of DR-001's superseded 0.9–2.4 V window (DR-012 Decision 5). (b) **The passive process axes** — every input is pinned `res_typical`/`moscap_typical`/`mimcap_typical`, and C1 alone spans 107.1–133 pF over corners (DR-006), so nothing bounds this consumption over the loop filter's own spread. (c) **The 10 of 45 rows the source grid flags as still converging**, nine of which sit in cells graded over budget — their settled `vctrl_avg_v` would move the count, which is why the 9-of-15 figure is the count on *that* grid and #437's re-take is entitled to another | **#525** (a, the decision + the deck); **#437** (c, the trimmed-window full-grid re-take); (b) unowned |
| [Output duty cycle](#output-duty-cycle) | the design does not meet its own 45 % floor at 7/90 measured points (`fs` bundle, `lo` edge, nominal-or-above supply); post-extraction re-run; the on-die divider's own input capacitance is not modelled (this record's 50 fF load is external-only) — the measurement itself now exists (`sim/output-driver/records/20260817-100354-0e9cfc9.md`, 90 points) | #144 (`output-driver`); #18 (extraction) |
| [Output levels and drive](#output-levels-and-drive) | post-extraction re-run; the on-die divider's own input capacitance is not modelled (this record's 50 fF load is external-only) — the loaded-output swing/edge-rate measurement itself now exists and PASSES at every point (`sim/output-driver/records/20260817-100354-0e9cfc9.md`, 90 points) | #144 (`output-driver`); #18 (extraction) |
| [Lock detector](#lock-detector) | **T1′ and T2′ are both met** at the trimmed `delaywin_3v3` under the [Lock-detector window trim-code rule](#lock-detector-window-trim-code-rule) (DR-010 → DR-013 → DR-014 → #411): edges [1.14, 1.16) ns at `fs`/−40 °C/3.63 V and [1.78, 1.80) ns at `ss`/125 °C/2.97 V, observable spread 1.53–1.58× against DR-013 Decision 4's ≤ 1.65×. What is still owed against this row: (a) **T4/T5 below 25 MHz** — the detector has only ever been characterized at f_ref = 25 MHz, its assert hold-off is an absolute time, and at the 1 MHz bottom of the reference range that hold-off is of order one reference period, where the flag would be expected to chatter; **unowned**; (b) **discharged at ONE of the two cells DR-013 names — the second is withdrawn** (DR-026, #515). `sim/supply-sensitivity` has been run at the trimmed window and DR-013's window-vs-offset crossing is **measured inside one closed loop** rather than inferred across two campaigns (**#417**, `sim/supply-sensitivity/records/20260920-180604-0f91a9b.md`, `SIM_PICKS='typical -40 ff 27'` at `KWINTRIM=rule`). At `typical`/−40 °C/3.63 V (code 7) the loop settles at a **0.814 ns** static offset and the flag **asserts** — window above the offset, which is what DR-013 inferred; that cell **stands**. At `ff`/27 °C/3.63 V the record states code 11 and the loop **ran at code 3**: `design/pll_top.sch` left the `LDT3` trim MSB unconnected inside `pll_top` (#515), so the detector saw `code & 0b0111` and the run's `1.233 ns` offset / `6.9 nV` flag is an observation at code 3, not at the code the rule selects. **That cell's crossing verdict is withdrawn pending a re-take**, and the withdrawal is not neutral: at code 11 the committed 1872-point code map puts `t_win` at **1.3015 / 1.2801 ns** against the same 1.2331 ns offset, i.e. **above** it, so the re-take is predicted to read `above` and make the cell **`moved`** rather than `confirmed` — a margin of only 3.8–5.5 %, and quoted from a campaign at another f_ref, which is why it is a prediction and not a verdict (`sim/supply-sensitivity/records/20260925-111906-1937f52.md`, which re-simulates nothing). Decision 4's "marginal observer at two corners and a wrong one at one" therefore rests on **one** in-loop cell, not two. **The rest of the residual is coverage, not method**: that record is a declared 2-cell / 6-point subset of the 45-point grid, so every other cell of the campaign is still at the untrimmed cell and the full-grid `20260901-155456-46b92f8` record remains its PVT statement — a trimmed-window **full-grid** re-run of that campaign is **#437**, which now also owns the `ff` cell's re-take and **must be run on a netlist at or after DR-026** (9 of its 45 points carry an MSB-set code and would otherwise be corrupted identically and silently); (c) a **0.02 ns edge refinement at `ff`/−40 °C/3.63 V (code 11) and `ss`/−40 °C/3.63 V (code 3)** — only the coarse ladder ran at those two, so each is bounded to [1.0, 1.2) ns: T1′ is met at both, but their margin is stated as [0, 20) % rather than to 0.02 ns, and the spread figure leans on the `t_win` bound (1.62×) instead of a measured edge there; (d) **extraction (#18) and device mismatch**, both still unquantified — including segment-to-segment mismatch inside one stage's binary trim array, which would appear as trim DNL; (e) **an executable route to the trim rule itself** — DR-022 (#501) measured every quantity `pll_top`'s pads expose against the rule's internal measurand and none selects the code to the accuracy this row's own 1.53–1.58× spread figure assumes, so **every verdict in this row is conditional on a trim that no present bench or tester procedure can perform**. The two candidate routes are a symmetric `REF` phase-step bisection read at `LOCK` (**#527**) and an output-side observation point for `ERR`/`ERRD` (a design change, needing its own decision record); both were blocked behind **#515**, which left `LDT3` unconnected at `pll_top` so only 8 of the 16 codes were reachable on the assembled part. **That obstacle is removed** (DR-026): the label now lands on the pin, `XLD`'s eighth argument reads `LDT3`, all 16 codes are reachable, and `design/lib/check-port-connectivity.sh` fails CI if any committed netlist ever again declares a port nothing inside the subcircuit connects to. Neither route is executable on its own merits yet, and **DR-022's finding stands in full** — removing an obstacle that would have defeated a route is not the same as having one | DR-013 (decision, #401); DR-014 (mechanism, #407); #411 (implementation + re-characterization); **#417** (b, discharged at `typical`/−40 °C only); **DR-026 / #515** (b, the `ff` cell withdrawn; e, the trim-MSB wiring); **#18** (d); **#437** (the trimmed-window full-grid `supply-sensitivity` re-run, which now also owns the `ff` cell's re-take); **DR-022 / #527** (e); T4/T5 unowned |
| [Lock criterion](#lock-time) | **a design gap, measured, and now narrowed to one corner plus one owed run** (DR-012, narrowed by DR-025): the loop misses the ratified ≤ 1 ns static-phase bound in its own undisturbed steady state at **1 of the 45** mandated corners *at the configuration the normative [band-selection rule](#band-selection-rule) selects* — **1.049 ns** at `typical`/−40 °C/3.63 V, nominal-skew and systematic-only, before `mc-cp-mismatch`'s 0.576 ns statistical term is added. The second violation, **1.227 ns** at `ff`/27 °C/3.63 V, is a correct measurement of **band 6**, which is *not* the band the rule selects there over DR-003 Decision 5's measured 0.9–2.7 V control window (it selects band 5, `Vctrl` 1.967–2.595 V against band 6's 1.008–1.394 V); that cell has never been run closed-loop, so the corner is **neither cleared nor confirmed** and the count returns to 2 of 45 if it misses (`sim/supply-sensitivity/records/20260925-090649-4422f1d.md`, the first re-derivation of the rule against the band map — DR-012 Decision 4b deliberately did not make it). What is *owed* is the rest of the picture, not the existence of the gap: (a) the settled static phase at the **15** further corners that exceed the bound with the phase still decaying — their committed values are upper bounds on a tail, needing `run.sh`'s 36.8 µs settling escalation (≈10 h of ngspice per corner); (b) a **closed-loop** measurement at an (f_ref, N, trim-code) cell other than 12.5 MHz / N = 8 / b1b0 = 10, the only cell characterized — **the cell is now named rather than left open**: f_out = 135 MHz at `ss`/125 °C, band 6 per the rule, which parks at 0.919 / 1.201 / 1.463 V, the lowest rule-compliant parking anywhere in the ratified output band (N = 8 ⇒ f_ref = 16.875 MHz ⇒ one Icp unit leg, b1b0 = 00, per the [Icp trim-code rule](#icp-trim-code-rule)); plus the `ff`/27 °C band-5 run above; (c) the design resolution — **DR-025 narrows DR-012 Decision 7's four candidate loci to one** by eliminating the band-selection axis on measurement: applying the rule across the ratified 10–200 MHz output band still parks some corner at `Vctrl ≤ 1.05 V` at 23 of 39 output frequencies (floor 0.919 V) and still misses the criterion on DR-012 Decision 4a's summed budget at **1397 of 1628** rule-selected points, so the resolution must reduce the pump's residual charge `q_zero` at low Vctrl and no band plan substitutes for it. The earlier entry here — "`ff`/125 °C/3.63 V stands off 1.796 ns" — was a sample on a decaying tail and is withdrawn by DR-012 Decision 2; that corner is neither cleared nor confirmed | #394 (found, closed); #399 (a, the 15-corner settling escalation); **#511** (b and c, via DR-025) |
| [Lock time](#lock-time) | any bound at all on **re-lock after a mid-operation supply excursion** — distinct from row 9's cold-start acquisition. Measured today only as a lower bound: `lock` had not re-asserted 34.4 µs (3.70 τ) after a +10 % step at 2 of 3 sampled corners (DR-011) | #395 |
| [Area](#area) | **the block-level numbers are no longer owed** — a floorplan exists (`layout/floorplan/PLL-FLOORPLAN.md`) and all four non-passive sub-blocks are drawn, DRC-clean, LVS-matched and measured off committed GDS by `python3 layout/run_pv.py area`, which is what DR-016 amends the row on and DR-017 refreshes it against. What remains owed is (a) an **assembled `pll_top`**, which would replace the ×1.25 top-level overhead factor — the only estimated term left in the row — with a measured extent, and (b) the loop filter's own **layout**, whose 36,936 µm² (20.5 % of the block sum) is still DR-006's device-data calculation ×1.15, not a drawn cell. **These two are now also the only triggers for a downward re-amendment of the row** (DR-017 Decision 3): the block-level reduction levers refresh the measured table, not the budget | #17 (top-level assembly, and the loop-filter layout with it), #18 (extraction) |
| [Kvco](#kvco), [Output band](#output-band) | Monte Carlo band-select mirror mismatch; **post-extraction re-run of every VCO number** | #15, #18 |
| [Multiplication ratio](#multiplication-ratio) | post-extraction retiming setup margin at N = 64, 200 MHz — the thinnest margin in the block at 6.1 % of a VCO period | #18 |

