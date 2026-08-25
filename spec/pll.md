# PLL target specification — v1

- **Status**: **proposed** — pending engineering ratification (#1). This file
  is the artifact #1 ratifies *against*; it does not ratify itself, and no row
  below is binding until #1 says so.
- **Date**: 2026-07-31
- **Written by**: Builder agent, issue #55
- **Consumes**: DR-001 (architecture), DR-002 (scope ratification), DR-003
  (VCO band map / Kvco contract), DR-005 (dump-node buffer), DR-006 (loop
  filter values and the Icp trim rule), and the `sim/` evidence records each of
  those cites.
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

Two rules in this file are **normative conditions**, not advice: the
[band-selection rule](#band-selection-rule) and the
[Icp trim-code rule](#icp-trim-code-rule). A part configured against either one
is operating outside this specification, and no row below applies to it.

### Everything here is schematic-level

No layout parasitics, no extracted netlists, no silicon. Every measured number
is a pre-layout simulation result, and extraction (#18) is where most of them
are at risk. Nothing in this repository has been fabricated or measured.

---

## Summary table

| # | Parameter | v1 target | Corner binding | Status |
|---|---|---|---|---|
| 1 | [Output band](#output-band) | 10 – 200 MHz, continuous | floor `all-fast`/125 °C/2.97 V (6.449 MHz, 36 % below the line); ceiling `all-slow`/−40 °C/3.63 V (247.8 MHz, 24 % above) | **measured** |
| 2 | [Reference input](#reference-input) | 1 – 25 MHz, CMOS square wave, rising-edge triggered, duty 30–70 % | n/a — interface contract; the electrical limits are conditions on the driving system, not PVT-varying outputs | **budget** (levels/edge rate); range is **measured** as an operating condition of rows 8/9 |
| 3 | [Multiplication ratio](#multiplication-ratio) | N = 4 – 64, every integer, static configuration | retiming setup `ss`/125 °C/2.97 V at N = 64, 200 MHz (6.1 % of a VCO period) | **measured** |
| 4 | [Integrated RMS jitter](#integrated-rms-jitter) | **not spec'd** — derived-only (DR-002 Decision 5) | n/a — deliberately unspecified; see the section for why this is visible rather than silent | **n/a** |
| 5 | [Period jitter](#period-jitter) | ≤ 1.0 % of the output period, RMS, **conditional on ≤ 20 mV pp `vdd_vco` ripple** | `all-slow`/−40 °C/2.97 V, band 5 (2.51 % RMS at 100 mV pp ripple, open-loop) | **measured** (sensitivity); **derived** (the ripple condition) |
| 6 | [Phase noise](#phase-noise) | **not spec'd** — derived-only (DR-002 Decision 5) | n/a — deliberately unspecified | **n/a** |
| 7 | [Reference spur](#reference-spur) | ≤ −55 dBc | measured worst −57.0 dBc at f_out = 150 MHz (`sf`/−40 °C/2.97 V), i.e. −54.5 dBc scaled to 200 MHz; derived worst case −61 dBc at 200 MHz | **measured** (5 spanning corners, 150 MHz); **budget** (the 200 MHz binding point and the other 40 corners — see [Verification owed](#verification-owed)) |
| 8 | [Loop bandwidth](#loop-bandwidth) | f_c = 26 – 430 kHz over the ratified space, with `f_c < f_ref/10` as a hard ceiling | min 25.96 kHz at f_ref = 1 MHz / 4 legs; max 429.5 kHz at f_ref = 25 MHz / 1 leg; worst realized ratio `f_ref/13` | **measured** |
| 8a | [Phase margin](#phase-margin) | ≥ 45° everywhere in the contracted space | 47.4° at f_ref = 1 MHz, 4 legs (the tightest cell of the trim rule) | **measured** |
| 9 | [Lock time](#lock-time) | < 100 µs to the stated [lock criterion](#lock-time). **The < 20 µs stretch is dropped** | 71 µs at f_ref = 1 MHz under the trim rule; structural floor 43 µs | **measured** (small-signal settling); **budget** (cold-start, owed to #12) |
| 10 | [Power](#power) | < 5 mW at 100 MHz, all domains, locked | `all-fast`/125 °C/3.63 V — derived total ≈ 1.98 mW | **derived** |
| 11 | [Standby current](#standby-current) | **no power-down mode in v1** — the block is always-on whenever its rails are up | n/a — no standby state exists to bind a corner to | **waived, with rationale** |
| 12 | [Supply sensitivity](#supply-sensitivity) | `vdd_vco` ripple ≤ 20 mV pp (100 kHz – 100 MHz); DC rail excursion over 2.97–3.63 V must consume ≤ 0.6 V of the Vctrl window | pushing worst −50.7 %/V at `ss`/−40 °C, band 4 (−52.3 %/V on the coarser tuning-range grid) | **measured** (pushing); **derived** (the two budgets) |
| 13 | [Output duty cycle](#output-duty-cycle) | 45 – 55 % at `CLK`, over the whole band and all corners | measured 44.375 – 50.696 % (90 points); worst `fs`/27 °C/3.63 V at the `lo` edge (band 0, Vctrl 0.9 V) — the bottom-of-band binding condition the design basis predicted | **measured** (90 points, loaded); target **not met** at 7/90 points, all at the `lo` edge |
| 14 | [Output levels and drive](#output-levels-and-drive) | rail-to-rail CMOS on `vdd_vco`: V_OH ≥ 0.9·VDD_VCO, V_OL ≤ 0.1·VDD_VCO into ≤ 50 fF external load | measured V_OH 1.006 – 1.044·VDD_VCO, V_OL −0.040 … −0.006·VDD_VCO into a 50 fF load, at every one of 90 points | **measured** (90 points); target **met** at every point |
| 15 | [Area](#area) | ≤ 0.15 mm² total — **a budget, not a result** (no layout exists) | n/a — drawn area is not a PVT quantity; the *capacitance* it buys is (C1 = 107.1 … 133 pF over corners) | **budget**; loop-filter allocation is **measured** |
| 16 | [Lock detector](#lock-detector) | digital `lock` output; assert window ≥ 2.5 ns of phase error, ≥ 2× the worst-case static phase offset; hysteresis ≥ 25 % of the assert window; no chatter | window measured 0.877 … 1.702 ns, max at `ss`/125 °C/2.97 V — **the target is not met today** | **measured** (behaviour); **budget** (the target, currently a gap) |
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
(`sim/cp-compliance/records/20260731-194124-afa338c.md`); the nominal code is
10 (three legs, ≈5.2 µA).

Reference frequencies between the decades above take the code of the **nearest
tabulated f_ref at or below** them; 105 of the 140 measured (f_ref, N, code)
cells pass both stability criteria unconditionally, and every one of the 35
failures is a code away from this rule, never a corner of a correctly
configured part.

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
| Levels | V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD | budget — no input-threshold sweep exists |
| Edge rate | ≤ 5 ns, 10–90 % | budget |
| Duty cycle | 30 – 70 % | the PFD's edge detectors fire on the **rising** edge only (`design/pfd.sch`), so duty affects only pulse-width margin, not the sampled phase |
| Source quality | **excluded from the jitter and spur budgets** — see below | explicit assumption, see rationale |

**Reference-source quality assumption (the "[no recorded value]" item, resolved
as an explicit exclusion rather than an invented number).** No
reference-noise-transfer measurement exists in `sim/`, and inventing a
reference phase-noise limit without one would be exactly the unsupported number
CLAUDE.md forbids. So this specification states the assumption instead: **every
jitter and spur number in this file is the block's own contribution, measured
or derived against an ideal reference.** Reference phase noise inside the loop
bandwidth transfers to the output multiplied by `20·log₁₀(N)` = 12 dB at N = 4
to 36 dB at N = 64, so a system integrating this block must budget its
reference against that multiplication itself. Converting this assumption into a
numeric reference-jitter limit requires the closed-loop bench (#12) and is
named in [Verification owed](#verification-owed).

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

Evidence: `sim/divider-ratio/records/20260731-171817-0a12e6c.md` (chain),
`…-171816-…` (single cell), `…-171815-…` (flop setup/hold).

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
network. **No closed-loop and no random-jitter number exists** — that is #13's
campaign, and DR-002 Decision 5 is explicitly `proposed` until it runs. The
band sweep (1.18 % at B0 rising to 2.46 % at B6, as a fraction of the period)
was taken at nominal temperature and supply only.

Evidence: `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md`.

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
below. `sim/reference-spur` (#145) runs the assembled `pll_top` to lock and
reads the sidebands straight out of the locked output spectrum — the first
closed-loop spur measurement in `sim/`. It does **not** retire the whole row:
it is five of the 45 PVT points, at one (f_ref, N, band, trim) operating point,
and at f_out = 150 MHz rather than the binding 200 MHz. What remains owed is
named in [Verification owed](#verification-owed).

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
| Systematic per-event charge asymmetry \|q_up + q_dn\|, worst corner | 3.68 fC (`fs`/125 °C/3.63 V, Vctrl 0.9 V) | `sim/cp-compliance/…-194124-afa338c` via DR-006 §8 |
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

| Quantity | Value | Binding point |
|---|---|---|
| Worst small-signal 1 % settling **under the trim rule** | 71 µs | f_ref = 1 MHz, 4 legs |
| Best | 52 µs | f_ref = 2 MHz, 4 legs |
| Structural settling floor | ≈43 µs | set by `1/(2πRC1)` |
| Cells meeting < 100 µs across the whole cross-product | 120 of 140 | the 20 failures are all off-rule trim codes |
| Cells meeting < 20 µs | **0 of 140** | — |

**Limitation, and it is a large one.** These are *small-signal settling*
estimates from a fitted 3-element model. Cold-start acquisition involves cycle
slipping and the VCO's large-signal nonlinearity, and is #12's number, not this
one. The < 100 µs target above is therefore **measured for settling and a
budget for cold start**; see [Verification owed](#verification-owed).

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
be revisited, and `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md` is
the evidence that would drive it.

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

**Budget: ≤ 0.15 mm² for the whole block. This is a budget, not a result** —
`layout/` is empty, nothing has been through DRC/LVS, and no area number in
this repository comes from a drawn cell.

Committed allocation so far, from real device data:

| Item | Area | % of the 0.15 mm² budget | Status |
|---|---|---|---|
| C1 (4 × `cap_nmos_03v3_b`, 30 276 µm² drawn) | 0.0303 mm² | **20.2 %** | **measured** — real 3.988 fF/µm² density at the typical corner |
| R + C2 | 0.0018 mm² | 1.23 % | measured |
| **Loop filter total** | **0.0321 mm²** | **21.4 %** | measured |
| Everything else (VCO, PFD/CP, divider, lock detector, routing, decap) | unallocated | 78.6 % | **not estimated** — owed to #17 |

Corner binding: **n/a** — drawn area does not vary with PVT. What *does* vary
is the capacitance that area buys: C1 spans 107.1 … 133 pF over the 27 passive
corner bundles × 3 temperatures, and moves only 1.6 % across the 0.9–2.7 V
Vctrl window (the body-tied connection is what buys that; the raw
`cap_nmos_03v3` has a 45× C–V ratio over the same span).

The 32 kHz reference mode is excluded partly on this row: it would need
single-digit-nF loop-filter capacitance, roughly 0.9 mm² — about **6× the
entire block budget** (DR-002 Decision 1).

## Lock detector

**A digital `lock` status output is in v1 scope** (DR-002 Decision 4),
implemented as a phase-error window comparator — a passive monitor, explicitly
**not** bundled with any band-search or self-calibration FSM.

**Targets** (the "[no recorded target]" item, resolved — and note that the
design does **not** meet them today):

| # | Target | Rationale |
|---|---|---|
| T1 | Assert window ≥ **2.5 ns** of phase error at the PFD inputs | it must be wider than the worst-case static phase offset the loop actually stands off in lock, or the flag will refuse to assert on a correctly locked part |
| T2 | Assert window ≥ **2× the worst-case static phase offset** over the ratified (f_ref, trim-code) space | the same requirement expressed as a ratio, so it tracks a future charge-pump or trim change instead of freezing at one number |
| T3 | Hysteresis ≥ **25 % of the assert window** | so the flag cannot chatter at the window edge |
| T4 | Deassert latency ≤ **1 reference period** at every f_ref in 1–25 MHz | a consumer gating logic on `lock` needs the deassert to be prompt at the *bottom* of the reference range, which is where the present design is weakest |
| T5 | No chatter at any corner, at any f_ref in 1–25 MHz | measured today at 25 MHz only |

**Measured behaviour** (`sim/lock-detector/records/20260731-162119-0a12e6c.md`,
95 points):

| Metric | Value | Corner |
|---|---|---|
| Points failing the four-check behavioural acceptance | **0** | — |
| Points where a large static error or a frequency error falsely asserted | **0** | — |
| Comparator window `t_win` | 0.877 … 1.702 ns | max at `ss`/125 °C/2.97 V |
| Assert time from cold start, deep in lock | 0.680 … 1.913 µs | max at `ss`/125 °C/2.97 V |
| Worst deassert latency after a perturbation | 5.45 ns | `ss`/125 °C/2.97 V |
| Window edges (asserted up to / did not assert from) | 0.8 ns / 1.0 ns at `ff`/−40 °C/3.63 V; 1.5 ns / 2.0 ns at `ss`/125 °C/2.97 V | — |

**Two gaps, recorded rather than papered over:**

1. **T1/T2 are not met.** The window is 0.877–1.702 ns, and the static phase
   offset the loop stands off in lock is of comparable size: 0.671 ns
   systematic worst-corner (`pfd-deadzone`, `ff`/125 °C/3.63 V) plus 0.576 ns
   statistical (`mc-cp-mismatch` term 4, |mean| + 3σ) plus 0.239 ns of
   divider-retiming flop clk→Q mismatch — up to ≈1.49 ns summed. That is at or
   past the assert edge at several corners. It is worse at the top of the
   reference range: the charge-derived component scales as `ΔQ/Icp`, and the
   [trim rule](#icp-trim-code-rule) mandates the *smallest* Icp (1 leg,
   ≈1.7 µA) at f_ref ≥ 16 MHz. **A correctly locked part may fail to assert
   `lock`.** The fix is geometric (widen the delay window, or scale the
   integrating capacitor), not architectural.
2. **T4/T5 are unverified below 25 MHz.** The detector was characterized at
   f_ref = 25 MHz only. Its assert hold-off is an *absolute* time set by a weak
   pull-up charging a MOS cap, so at the 1 MHz bottom of the reference range
   the hold-off is of order one reference period, where the flag would be
   expected to **chatter**. The record makes no claim at 1 MHz, and neither
   does this specification.

Both gaps are listed in [Verification owed](#verification-owed).

**Corner binding**: `ss` / 125 °C / 2.97 V for the window width, the assert
time and the deassert latency; `ff` / −40 °C / 3.63 V for the *narrowest*
window, which is the corner that binds T1.

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

## Anchor index

Every anchor `sim/` cites against `spec/pll.md#…`, and where:

| Anchor | Section | Cited by |
|---|---|---|
| `#output-band` | [Output band](#output-band) | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md`, `…-081628-239e73b.md`, `sim/vco-tuning-range/testbench/run.sh` |
| `#kvco` | [Kvco](#kvco) | same three |
| `#supply-sensitivity` | [Supply sensitivity](#supply-sensitivity) | `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md`, `…-100401-07f4b7b.md`, `sim/vco-tuning-range/testbench/run_supply.sh` |
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
| [Period jitter](#period-jitter) | closed-loop period jitter, and any **random** (noise-driven) jitter number at all | #13 (`period-jitter`) |
| [Period jitter](#period-jitter) | the band sweep at corners other than nominal temp/supply | #13 |
| [Reference spur](#reference-spur) | the remaining 40 PVT points, and a direct measurement at the binding f_out = 200 MHz rather than the 150 MHz one static band code holds across corners — the closed-loop measurement itself now exists (`sim/reference-spur/records/20260816-132150-5f405e7.md`, 5 spanning corners), and the two cold corners do not clear −55 dBc once scaled to 200 MHz | #145 (`reference-spur`) |
| [Lock time](#lock-time) | cold-start acquisition including cycle slipping; everything recorded today is small-signal settling | #12 (`lock-time`) |
| [Reference input](#reference-input) | input thresholds/edge-rate sweep; a numeric reference-jitter limit to replace the current exclusion | #12 |
| [Power](#power) | a measured `vdd_ref` domain current, and a closed-loop total | #14 (`supply-sensitivity`) |
| [Output duty cycle](#output-duty-cycle) | the design does not meet its own 45 % floor at 7/90 measured points (`fs` bundle, `lo` edge, nominal-or-above supply); post-extraction re-run; the on-die divider's own input capacitance is not modelled (this record's 50 fF load is external-only) — the measurement itself now exists (`sim/output-driver/records/20260817-100354-0e9cfc9.md`, 90 points) | #144 (`output-driver`); #18 (extraction) |
| [Output levels and drive](#output-levels-and-drive) | post-extraction re-run; the on-die divider's own input capacitance is not modelled (this record's 50 fF load is external-only) — the loaded-output swing/edge-rate measurement itself now exists and PASSES at every point (`sim/output-driver/records/20260817-100354-0e9cfc9.md`, 90 points) | #144 (`output-driver`); #18 (extraction) |
| [Lock detector](#lock-detector) | T1/T2 window widening (the design does not meet its own target today); T4/T5 characterization below 25 MHz | #11 rework, verified by #12 |
| [Area](#area) | everything except the loop filter; the block has no floorplan | #17 (floorplan), #18 (extraction) |
| [Kvco](#kvco), [Output band](#output-band) | Monte Carlo band-select mirror mismatch; **post-extraction re-run of every VCO number** | #15, #18 |
| [Multiplication ratio](#multiplication-ratio) | post-extraction retiming setup margin at N = 64, 200 MHz — the thinnest margin in the block at 6.1 % of a VCO period | #18 |

