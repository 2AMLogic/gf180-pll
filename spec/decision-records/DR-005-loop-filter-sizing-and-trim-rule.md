# DR-005: Loop filter component values and the Icp-trim-vs-f_ref rule

- **Status**: proposed
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #10
- **Refines**: DR-001 Decision 1 (loop type / fixed passive filter). This
  record does **not** supersede DR-001 — DR-001 Decision 1 explicitly labels
  its own filter-sizing numbers "disposition only" and delegates the real
  design to this issue ("Sizing sanity check (disposition only — #9 owns the
  real design)"). The topology DR-001 decides (tri-state PFD → charge pump →
  passive fixed series-R/shunt-C1/shunt-C2 filter → VCO → divider, no trim
  banks) is unchanged and remains binding; this record is that delegation
  coming back with the real component values, the real corner-swept
  stability table, and one correction to the hand calc's `C2 = C1/10`
  placeholder.
- **Evidence**: `sim/loop-dynamics/records/20260731-195707-3e3814c.md` (this
  issue's own corner-matrix sweep, cross-checked against an independent
  whole-loop simulation to < 0.001 % agreement); consumes
  `sim/devchar-passives/records/20260731-041345-833292f.md` and
  `.../20260731-041346-833292f.md` (#4, capacitor/resistor device data),
  `sim/vco-tuning-range/records/20260731-081628-239e73b.md` (#8, Kvco table),
  `sim/cp-compliance/records/20260731-122451-63e4b47.md` (#9, Icp/trim data).

## Context

DR-001 Decision 1 fixed the filter topology and handed three numbers to this
issue as *requirements*, not free choices: `Icp` in the single-digit-µA
range, `Kvco` bounded to roughly ≤150 MHz/V (settled precisely by DR-003
Decision 4's band-selection rule), and a sizing method to re-derive with real
data — `ω_c = Icp·Kvco·R/(2π·N)`, zero at `ω_c/4`, `C2 = C1/10`, target
`f_c = f_ref/20`. That method was explicitly a disposition-only hand
calculation ("~130 pF, ~0.027 mm², ≈18 % of budget" at the low-ref/max-N
corner), not a design value.

Sizing R and C1 from the real `sim/devchar-passives` device data (#4) and
checking the result against #8's real Kvco table and #9's real Icp/trim data
reproduces the hand calc's *order of magnitude* almost exactly — but the
`C2 = C1/10` rule, applied literally, does not survive contact with the real
25:1 reference-frequency range DR-002 ratifies. This record is the real
design that comes back from that check, and it is not a silent match to
DR-001's placeholder on one specific point.

## Decision

**1. Component values and device choices are as drawn in `design/loop_filter.sch`**,
sized from #4's real device data and confirmed by full corner-matrix
simulation (`sim/loop-dynamics`), not from the DR-001 hand calc:

| Element | Device | Drawn | Typical (27 °C, `Vctrl` = 1.8 V) | Min .. max over all 27 passive-corner bundles × 3 temperatures |
|---|---|---|---|---|
| R | 4× `ppolyf_u` in series | W = 2 µm, L = 107 µm each | 77.1 kΩ | 61.6 .. 93.4 kΩ |
| C1 | 4× `cap_nmos_03v3_b` | 87×87 µm each (30 276 µm²) | 120.8 pF | 107.1 .. 133 pF |
| C2 | 1× `cap_mim_2f0_m2m3_noshield` | 31.4×31.4 µm | 2.02 pF | 1.81 .. 2.22 pF |

`ppolyf_u` (≈ −75 ppm/°C) and the body-tied `cap_nmos_03v3_b` (`cv_ratio` ≈
1.10× vs. 45× for the raw device) are the loop-filter-friendly choices #4's
device-characterization campaign identified; this record confirms both hold
their design intent across the real Vctrl operating window (C1 moves only
1.6 % across 0.9–2.7 V) and across the real corner grid.

**2. `C2 = C1/10` is withdrawn as a design value; the as-built ratio is
`C1/C2 ≈ 60`, and this is a correction, not a discretionary choice.** DR-001's
hand calc sized C2 to place a third pole at roughly 10× the R–C1 zero,
targeting a single reference-frequency operating point. The real design has
to hold phase margin across the whole ratified **25:1** reference range
(1–25 MHz, DR-002) with **one fixed C2**, and `sim/loop-dynamics`'s
corner-matrix sweep shows `C1/C2 ≈ 10` does not clear 45° of phase margin at
the top of that range at the corners this record actually swept (the R–C1
zero and the C2-driven third pole are too close together once R and C1 carry
their own ±20–25 % process spread on top of the Kvco/Icp spread). Sizing C2
smaller — pushing the third pole to ≈1.04 MHz, roughly 60× the zero rather
than 10× — is what makes the filter meet the phase-margin criterion at the
high-f_ref end without giving up area (C2 is already the smallest of the
three elements at either ratio; the correction costs no extra area budget).

**3. Explicit stability criterion: phase margin ≥ 45°, `f_c < f_ref/10`.**
DR-001 states the `f_c < f_ref/10` sampled-loop ceiling but no phase-margin
number; this record adopts 45° as the criterion checked at every point.

**4. `f_c < f_ref/10` holds at every point in the full cross-product with no
exception.** Across all 140 (f_ref, N, Icp-trim-code) legal combinations ×
27 passive-corner bundles × 3 temperatures × 5 in-window Vctrl points, the
worst realized ratio is `f_c ≈ f_ref/13` — inside the ceiling everywhere, not
just at the nominal design point.

**5. Phase margin ≥ 45° holds everywhere *conditional on* the Icp-trim code
following a stated per-f_ref rule — it does not hold at an arbitrary trim
code.** 105 of 140 (f_ref, N, code) cells pass unconditionally; the other 35
fail only at a trim code away from the rule below, never as a corner of a
correctly-configured part. The rule (worst phase margin at that code, over
every corner and every legal N at that f_ref):

| f_ref | required Icp-trim (unit legs) | worst PM | realized f_c |
|---|---|---|---|
| 1 MHz | 4 | 47.4° | 26.0 – 73.8 kHz |
| 2 MHz | 4 (2, 3 also pass) | 60.4° | 45.2 – 154.4 kHz |
| 4 MHz | 3 (1, 2, 4 also pass) | 66.7° | 65.0 – 227.7 kHz |
| 8 MHz | 2 (1, 3, 4 also pass) | 66.6° | 85.0 – 297.8 kHz |
| 16 MHz | 1 (2, 3 also pass) | 66.6° | 89.9 – 297.8 kHz |
| 25 MHz | 1 (2 also passes) | 60.0° | 135.9 – 429.5 kHz |

**This is now a load-bearing design contract, parallel to DR-003 Decision
4's band-selection rule**: the 2-bit Icp trim is not a discretionary margin
knob (as DR-001 characterized it, "a coarse charge-pump current trim as a
margin knob") but the mechanism that adapts the fixed filter across the 25:1
reference range. A part configured with the wrong trim code for its
reference frequency can fail the phase-margin criterion even though every
component is within spec — a failure mode that looks like marginal stability
or reference-spur trouble, not a configuration error, unless this table
travels with the filter values.

**6. C1's real area is 20.2 % of the 0.15 mm² budget** (0.0303 mm² at
30 276 µm² and the real 3.99 fF/µm² density at the typical corner) — within
2 points of DR-001's 18 % hand-calc placeholder. R and C2 together add a
further 1.2 %, so the whole filter is **21.4 %** of the area budget.

**7. Lock time: the <100 µs draft target is met at 120 of 140 cells; the
<20 µs stretch target is met at none.** This confirms DR-001's hand-calc
prediction ("lock times land in the tens of µs, meeting the <100 µs target
but not the <20 µs stretch at the low-ref end") with a measured number
(43 µs is the small-signal settling floor set by the dominant closed-loop
pole near `1/(2πRC1)`, regardless of how much Icp is applied) rather than an
asserted one.

**8. Control-line ripple is dominated by charge-pump charge asymmetry, not
current mismatch**, and it is C2's tradeoff alone: worst-case peak Vctrl
ripple 51.6 mV (median 20.8 mV), bounding the accumulated timing error at
472.6 ps worst-case (median 79.6 ps). Ripple scales as `1/C2` while the
pole-zero spread this record's phase margin depends on scales as `C1/C2` —
the same knob cuts both ways, and the as-built 2.02 pF is the point where the
phase-margin criterion is met at every f_ref without giving up more ripple
margin than that requires (`sim/loop-dynamics`'s `ripple_tradeoff.csv`).

## Alternatives considered

- **Literal `C2 = C1/10`** — rejected: fails the 45° phase-margin criterion
  at the high-f_ref end of the ratified range at corners this record's sweep
  actually reaches, for no area benefit (C2 is already the smallest element
  at the corrected ratio).
- **A single, frequency-independent trim code with more margin at every
  f_ref** — not available: no single code clears 45° at both ends of the
  25:1 reference range simultaneously (row-wise reading of the phase-margin
  table in the evidence record — low f_ref needs the largest Icp, high f_ref
  needs a smaller one to avoid over-driving `f_c` toward the third pole).
  Rejecting a fixed code in favor of the stated per-f_ref rule is therefore
  not a preference, it is what the measured data requires.
- **Widening C2 further to relax the phase-margin criterion's dependence on
  trim code** — not pursued in this record: it would increase ripple (§8)
  for a margin problem that the existing 2-bit trim, correctly used, already
  resolves at every f_ref in the ratified range. Revisit only if a future
  spec change removes the trim mechanism this decision assumes.
- **Re-deriving R/C1 target values from scratch instead of DR-001's
  `ω_c ∝ Icp·Kvco·R/N` starting point** — not needed: the hand-calc order of
  magnitude for R and C1 holds up against the real device data (within a few
  percent on C1's area fraction), so only the C2/trim-rule correction was
  required.

## Consequences

- **#12 (closed-loop bench) and #13 (jitter) consume the trim-code rule as a
  fixed input**, not a free parameter: a closed-loop test that does not
  configure the trim code from the table in Decision 5 above is testing an
  unsupported configuration, exactly as a closed-loop test that mis-selects
  the VCO band is (DR-003 Decision 4).
- **#17 (floorplan) has a concrete, real C1 area (20.2 % of budget) to plan
  against**, not DR-001's placeholder.
- **The <20 µs lock-time stretch goal is not reachable with this fixed
  filter** at the low end of the reference range — DR-001's hand calc
  predicted this and it is now confirmed with real data. Reaching it would
  require either relaxing the fixed-filter constraint (reopening DR-001
  Decision 1) or accepting it as out of v1 scope, which is a spec question
  for #1, not a design question for this record to resolve.
- **Everything here is schematic-level.** No layout parasitics on the
  filter's own R/C network (#18); no Monte Carlo mismatch (nominal skew
  only, inherited from the #4/#8/#9 records this campaign consumes).
