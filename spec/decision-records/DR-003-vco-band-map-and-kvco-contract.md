# DR-003: Ring VCO band map, stage count and the Kvco contract handed to the loop

- **Status**: proposed
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #8
- **Refines**: DR-001 Decision 2 (VCO delay-cell style). This record does
  **not** supersede DR-001 — DR-001 Decision 2 explicitly delegated the sizing,
  the stage-count confirmation and the real Kvco number to #8, and this record
  is that delegation coming back with extracted data. One sentence of DR-001's
  implementation sketch is replaced (see Decision 1); the architecture it
  decides is unchanged and remains binding.
- **Evidence** (all `sim/vco-tuning-range/records/`):
  - `20260731-081628-239e73b` — open-loop `f(Vctrl)` and `Kvco(Vctrl)`, 3528
    points (7 corner bundles × 3 temperatures × 3 supplies × 8 bands × 7
    control voltages)
  - `20260731-100719-07f4b7b` — 3- vs 5- vs 7-stage comparison
  - `20260731-100401-07f4b7b` — supply pushing and supply-induced jitter

## Context

DR-001 Decision 2 fixed the VCO topology and left three things to #8: the
coarse band map ("a binary-weighted set of legs in the bias mirror" producing
"8 overlapping frequency bands, each covering roughly 2:1 with ~20% overlap"),
the stage count ("odd stage count (5 nominal; #8 to confirm against the 200 MHz
top of band and the power budget)"), and Kvco itself ("design intent is
Kvco ≈ 0.7·f_out per volt … This issue produces the *real*, extracted number").

Extraction now exists, and it settles all three — but two of them do not come
back the way the hand calc predicted, and one of those changes what #9 and #10
have to design against. Those are decisions, not just results, so they belong in
`spec/` rather than only in `sim/`.

The two sentences of DR-001 Decision 2 that extraction contradicts are:

1. **"a binary-weighted set of legs"** cannot produce **"8 bands each ~2:1 with
   ~20% overlap"**. Legs of weight 1, 2, 4 plus an always-on unit leg give band
   gains 1, 2, 3, …, 8, so the *adjacent-band* step falls from 2.00× (B0→B1) to
   1.14× (B6→B7). With a ~2:1 fine range per band, the bottom of the code space
   has no overlap at all while the top wastes 80 % of it. The two halves of the
   sentence are mutually exclusive; only one of them can be built.
2. **"Kvco ≈ 0.7·f_out per volt"** is not a constant of this topology. Measured
   over the whole grid, Kvco/f_out rises monotonically with band code from
   **0.31/V to 0.84/V**. A single-number reading would under-predict Kvco in the
   top bands — the ones nearest the 200 MHz ceiling, where the loop filter has
   least margin — and over-predict it in the bottom ones.

## Decision

**1. The 3-bit coarse control is a *geometric* mirror cascade, ×1.65 per code,
not binary-weighted legs.** Three cascaded current mirrors, each with one
always-on leg and one leg switched by a band bit, give gains ×1.65, ×1.65² and
×1.65⁴, so `I_stage ∝ 1.65^code` for code = 0…7 and every adjacent band step is
the same 1.65×. This realizes DR-001's stated *requirement* (8 overlapping
bands, ~2:1 each, uniform overlap) and replaces its incompatible implementation
sketch. Measured across all 63 corners: fine range **2.00–2.70×** per band,
adjacent-band overlap **27–36 %** at every corner with no coverage hole, and
1.65⁷ ≈ 41.6× of coarse range. Cascading also keeps the largest device ratio in
any single mirror to 6.4:1 instead of 41:1.

**2. The stage count is 5, and there is no fallback to 3 or 7.** Measured side
by side from the same cell and bias generator: the **3-stage** ring does not
start at the fast corner (it needs 2.00× per-stage gain against 1.24× for five,
and a current-starved inverter loses gain as its head/tail devices are driven
fully on) and its lowest band floors 14 % above the 10 MHz bottom of the band;
the **7-stage** ring tops out 9 % *short* of the 200 MHz v1 ceiling at the slow
corner. Five clears the ceiling by 28 %, reaches 34 % below the floor, starts
everywhere and holds full swing.

**3. Kvco is specified as a per-band, per-corner table, not a single
coefficient.** `sim/vco-tuning-range/corners/20260731-081628-239e73b/
kvco_by_band.csv` and `kvco_by_point.csv` are the interface #9 and #10 size
against. DR-001's 0.7·f_out/V is withdrawn as a design value and retained only
as the disposition hand calc it was labelled to be.

**4. The band-selection rule is part of the loop-stability contract.** A system
targeting output frequency f **must configure the lowest band code that reaches
f**. Under that rule the worst-case Kvco anywhere in the ratified 10–200 MHz
band is **116 MHz/V**, inside the ~150 MHz/V bound DR-001 Decision 1's fixed
passive filter assumes. Configure a higher band than the target needs and the
same frequency is produced near the bottom of that band's Vctrl range, where
Kvco is already large: the worst in-band point over all codes is **154 MHz/V**,
*above* the bound. The band code is therefore no longer only a range-selection
convenience, and #9/#10 must publish the selection rule alongside the filter
values.

**5. The usable Vctrl window is 0.9–2.7 V**, wider than the 0.9–2.4 V DR-001
predicted; `f(Vctrl)` is monotonic on all 504 measured curves.

## Alternatives considered

- **Keep binary-weighted legs and accept non-uniform overlap** — rejected: at
  the bottom of the code space the bands would not overlap at all, which is the
  exact failure ("holes in the tuning range") DR-001 told #8 to check for.
- **Fewer, wider bands (drop to 2-bit)** — rejected: a wider fine range per band
  means a larger Kvco at the top of each band, pushing further past the loop
  filter's ceiling. The geometric map trades coarse-code width for Kvco, which
  is the scarce quantity.
- **Auto-calibrated band selection (a lock-driven FSM)** — out of scope by
  DR-001 ("band select is a static input in v1"), and Decision 4 above raises
  its value: with a static code, a mis-programmed part now costs loop margin as
  well as range. Recorded here as the strongest argument yet for revisiting it
  in v2, not as a v1 change.
- **Superseding DR-001 outright** — rejected as disproportionate: DR-001's three
  decisions stand, and it delegated exactly these numbers. A supersede would
  invalidate the loop-type and divider decisions that nothing here touches.

## Consequences

- **#9 / #10 gain a harder input and a new obligation.** They size against a
  Kvco *table* spanning 3.2–154 MHz/V in band, not a single number, and they
  must state the band-selection rule with the filter values. A part configured
  into too high a band presents the loop with more gain than the fixed filter
  was sized for — a failure that shows up as ringing or instability, not as a
  frequency error, and so will not be caught by a range test.
- **#11's output divider stays out of v1 scope.** DR-002 Decision 2 made the
  low-band floor the trigger: the lowest band reaches **6.4 MHz at the fastest
  corner**, 36 % below the 10 MHz spec line, so the ring covers the bottom of
  the band unaided. The trigger does not fire.
- **The 400 MHz stretch is not free.** Above 200 MHz the extracted Kvco reaches
  206 MHz/V, well past the fixed filter's bound, so the stretch target would
  need either a filter re-design or a finer band map — not just more Vctrl.
- **Supply sensitivity is confirmed as the block's dominant risk, and it is
  structural.** Pushing is −24 to −51 %/V across the grid, of which −30.3 %/V is
  the unavoidable `f ∝ 1/V_swing` term of any current-starved ring on an
  unregulated rail. A 100 mV peak-to-peak ripple produces up to **2.5 % RMS
  period jitter** open-loop, against a draft spec line of < 1 %. Nothing in this
  record fixes that; it bounds it. The condition that would reopen DR-001
  Decision 2 is now explicit and measurable: *if the system cannot deliver a
  quiet enough `vdd_vco`, the cell choice must be revisited*, and
  `20260731-100401-07f4b7b` is the evidence that would drive it.
- **There is no second choice on stage count.** Decision 2 removes 3 and 7 as
  fallbacks, so the 5-stage margins (28 % at the ceiling, 36 % at the floor) are
  the whole budget for layout parasitics. Extraction (#18) is where this
  decision is actually at risk, and a re-run of `sim/vco-tuning-range` against
  the extracted netlist is a prerequisite for treating any of it as final.
- **Everything here is schematic-level.** No parasitics, no mismatch (the
  statistical switches are off in every cited record). Band-select mirror
  mismatch in particular is uncharacterized and directly perturbs the 1.65×
  ratio this record's overlap margins depend on.
