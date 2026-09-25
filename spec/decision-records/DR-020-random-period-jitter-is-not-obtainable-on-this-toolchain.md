# DR-020: The random (noise-driven) half of the period-jitter row is not obtainable from any analysis this repository's toolchain offers, the ≤ 1.0 % RMS row stands unrelaxed as deterministic-only-in-simulation, and both Period jitter rows are re-pointed off closed issue #13

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-019 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #505
- **Relationship to DR-002 Decision 5**: **partial supersession of its method
  clause only, recorded here and deliberately not written into DR-002.**
  Decision 5 has two clauses. Its *quantity* clause — period jitter (RMS) is
  the spec'd, simulation-substantiable quantity, with phase noise and
  integrated jitter derived-only — is **confirmed** by `sim/period-jitter`'s
  45-corner campaign and stands. Its *method* clause — "measured via a
  transient-noise testbench dominated by the VCO" — names an analysis this
  flow does not have (§Context). DR-002's own Consequences anticipate a
  superseding record for the case where "#13 … shows the transient-noise
  approach cannot substantiate even period jitter reliably at this node". That
  is **not** what happened: period jitter *is* substantiated, at 45 of 45
  corners, for its deterministic half. Only the method for the other half
  failed, so a whole-record supersession would be wrong twice over — it would
  retract four unrelated scope decisions (reference range, output ceiling,
  device flavor, lock detector) and it would retract a quantity clause the
  evidence confirms. DR-002 Decision 5 is `proposed`, never ratified, so the
  never-rewrite rule's strict form does not bind it; even so DR-002 is not
  edited here, and the pointer runs one way, from this record to it. **If the
  operator prefers a formal whole-record supersession of DR-002 with the four
  surviving decisions restated, that is a one-record follow-up and this record
  does not pre-empt it.**

## Context

`spec/pll.md`'s [Period jitter](../pll.md#period-jitter) row targets **≤ 1.0 %
of the output period, RMS**, conditional on the normative ≤ 20 mV pp `vdd_vco`
ripple budget. That total has two physically distinct halves, and only one of
them has ever been measured:

| Half | Mechanism | State |
|---|---|---|
| Deterministic | control ripple on `vctrl`, divider pattern, supply ripple | **measured at 45 of 45 mandated PVT corners** — `sim/period-jitter/`, 0.0508 – 0.2691 % RMS, PASS against the draft target at every corner |
| Random | device thermal + flicker noise in the current-starved ring and its bias | **zero records, at any corner, at any maturity** |

Every one of the six `period-jitter` records discloses the second row in its
own Limitations field, and `sim/CHARACTERIZATION.md` carries it in two places.
The gap is stated honestly everywhere it appears. What it has not had is an
**owner** or a **disposition**: `spec/pll.md`'s
[Verification owed](../pll.md#verification-owed) table hands it — and the
separate 200 MHz band-top row beside it — to **#13**, which closed
2026-09-08 (`completed`). This is the same defect DR-019 repaired one row
below, for #12, and it is repaired here on the same reasoning: a ratified
table that points an open obligation at a closed issue reads to an outside
reader as *discharged*, which is the opposite of true.

### The toolchain finding, re-derived here rather than restated

The `period-jitter` records say TRANNOISE produces no noise on this
repository's pinned ngspice-46. This record does not take that on trust — a
decision about what a toolchain can do should rest on a run a stranger can
repeat. Three probes were run locally on the pinned `ngspice-46` binary
(single-run debug probes, no fleet, no `sim/` record minted — they make claims
about the *simulator*, not about the design, so they are reproduced inline
here rather than as evidence records).

**Probe A — `.option TRANNOISE=1` injects nothing, and says nothing.**

```spice
v1 in 0 dc 1
r1 in mid 1meg
r2 mid 0 1meg
.option TRANNOISE=1
.tran 1n 1u
```

`v(mid)` over 1008 rows: `vecmin = vecmax = 5.000000e-01`, peak-to-peak
**exactly `0.000000e+00`**. The option produces no warning and no effect. It
is silently accepted and discarded.

This is **structural, not a build defect.** ngspice has no device-noise model
in `.tran` at all; `TRANNOISE` is an option name from other simulators.
Rebuilding, upgrading or re-flagging this binary does not produce the
analysis, so "unsupported on this build" understates it — no ngspice offers
it.

**Probe B — the `trnoise()` source works, and that is exactly the problem.**

```spice
vn mid2 mid dc 0 trnoise(1m 1n 0 0)
```

Measured 873.6 µV RMS on the source against the 1 mV requested (the shortfall
is the 1 ns breakpoint interval against the 1 ns transient step), 2.21 mV pp
at the divider mid-node over 5008 rows. The mechanism is real and working.
**The `1m` is a number the deck author typed.** Nothing in the flow connects
it to the ring's devices, so a jitter figure produced this way measures the
author's choice of amplitude, not the circuit.

**Probe C — the device noise data is present and ngspice evaluates it
correctly, in the one analysis an oscillator cannot use.**

```spice
.include ".../design.ngspice"
.lib ".../sm141064.ngspice" typical    $ + res_/moscap_/mimcap_typical
vdd vdd 0 dc 3.3
vg  g   0 dc 0.9 ac 1
rd  vdd d 20k
xm1 d g 0 0 nfet_03v3 W=2u L=0.6u nf=1 m=1
.noise v(d) vg dec 10 1 1g
```

gives `onoise_total = 9.023e-4 V`, `inoise_total = 4.598e-4 V` over
1 Hz – 1 GHz, with a spectrum that is textbook-correct for these models:

| f (Hz) | 1 | 10 | 10³ | 10⁶ | 10⁸ | 10⁹ |
|---|---|---|---|---|---|---|
| `onoise_spectrum` (V/√Hz) | 3.583e-5 | 1.200e-5 | 1.347e-6 | 5.773e-8 | 2.834e-8 | 2.764e-8 |

The low-frequency amplitude slope is 10^−0.475 per decade, i.e. a **power
slope of 0.9500** — the gf180mcu models' own `ef = 0.95` reproduced to four
digits — rolling into a flat thermal floor of 27.6 nV/√Hz above the ~10 MHz
flicker corner. `sm141064.ngspice` carries `fnoimod = 1`, `tnoimod = 0`,
`ef = 0.95` and per-flavor `noia`/`noib`/`noic` (with an `fnoicor` corner
switch), for every device this design uses.

**So the missing piece is named precisely, and it is not the data.** The PDK
has the noise PSDs. ngspice can evaluate them. What ngspice offers to evaluate
them *with* is `.noise` — a small-signal analysis linearised about a **DC
operating point**. A free-running ring oscillator does not have one in the
sense `.noise` requires: its steady state is a limit cycle, its noise is
cyclostationary, and its phase noise is the up-conversion of that noise
through a time-varying sensitivity. Pointing `.noise` at the ring does not
give a wrong phase-noise number; it gives no phase-noise number.

The bridge between the two — extract each stage's PSD from `.noise` at points
around the limit cycle, weight by the impulse sensitivity function, integrate
to a phase-noise or period-jitter figure (Hajimiri–Lee, or an equivalent
PSS/Pnoise pipeline) — is a **well-defined but unbuilt methodology project**.
It is the same calibration the six records call "real, separately-scoped
methodology development this record does not attempt", stated with its input
and output named. It is not a run nobody got round to.

### What the row's arithmetic actually leaves for the unmeasured half

Stating the gap is not the same as saying nothing about its size. Two of the
three contributors to the 1.0 % line are measured, and the row's own normative
condition bounds the third:

| Contributor | Figure | Basis |
|---|---|---|
| Supply-ripple-driven, at the normative ≤ 20 mV pp ceiling | **0.502 % RMS** | measured sensitivity 0.0251 %/mV pp × 20 mV — already the derivation `spec/pll.md` gives for the ripple condition |
| Closed-loop control-ripple, quiet supply, worst of 45 corners | **0.2691 % RMS** | `sim/period-jitter/`, `typical`/−40 °C/3.63 V |
| Random / device noise | **unknown** | this record |

The two measured terms are different mechanisms at different frequencies
(≈ 5 MHz supply ripple vs. the 25 MHz reference), so as RMS quantities they
compose in quadrature: **0.570 % RMS**, leaving
`sqrt(1.0² − 0.570²) =` **0.822 % RMS** of quadrature allowance for the random
term. Forced to add linearly — the wrong composition law for RMS, but a hard
bound — they give 0.771 %, leaving **0.229 %**.

**This is derived, and it is a statement about the allowance, not about the
term.** It says the row is not tight, not that the row passes: the random term
could be anywhere in [0, ∞) for all this repository has measured, and both
figures stack worst-of-each across different corners, different bands (5 vs.
6) and different loop conditions (open- vs. closed-loop), so neither is a
corner-consistent total either. It is recorded because "what does the gap mean
for the row" is a question a reader will ask, and leaving it unanswered when
the inputs are all already committed would be a worse silence than an
explicitly-labelled derivation.

## Decision

**1. The random component is recorded as not obtainable from any analysis this
repository's toolchain offers, and DR-002 Decision 5's method clause is
recorded as unrealizable.** Not "unmeasured". Not "unsupported on this build".
The precise statement, which is what the spec now carries: *ngspice has no
transient device-noise analysis; its `.noise` analysis requires a DC operating
point a free-running oscillator does not have; and its `trnoise()` source
injects an amplitude the deck author chooses. No composition of the three
yields a device-noise-equivalent period-jitter figure without a
cyclostationary noise-referral pipeline that does not exist in this
repository.*

**2. The ≤ 1.0 % RMS row stands, unrelaxed, and its scope is stated rather
than implied.** The target is **not** narrowed to the deterministic component,
**not** caveated down, and **not** marked satisfied by the 45-corner
deterministic PASS. What changes is that every place the row's status is
stated must say the measured evidence covers the deterministic half only. The
specific failure this guards against is a reader — or a future agent — taking
"PASS at all 45 corners, 3.7× margin" as the row being discharged. It is half
the row, at 3.7× margin on that half.

**In simulation, for v1, the row is therefore deterministic-only, and the
random half is deferred to silicon.** This is not a new position invented
here: `sim/README.md`'s own worked example for this exact scenario has said
since it was written that "the ratified jitter claim must be stated as
deterministic-only in simulation, with random jitter deferred to silicon
measurement (`measurements/`)". This record ratifies that sentence instead of
leaving it as advice in an example. A phase-noise analyzer measures the random
half directly on a packaged part, so the gap is bounded to *pre-silicon
methodology* — it is not a quantity this project can never know.

**3. Both Period jitter rows in the Verification-owed table are re-pointed off
#13.** The random-component row goes to **#505** (open) with this record; the
200 MHz band-top row goes to **#503** (open). The band-top row's own
measurement is out of #505's scope and stays out — only its owner column
moves, because re-pointing one row of a table while knowingly leaving a closed
owner in the row beside it would force a third record for the identical
defect. #496, which that row's work also sat behind, closed 2026-09-25 and is
not substituted in. **No requirement moves in either row.** This is an
attribution fix.

**4. The gap is bounded by named exit conditions instead of left indefinite.**
Any one of these discharges it, and nothing less does:

- **(a) Build the referral pipeline.** Extract the ring stages' thermal and
  flicker PSDs from `.noise` (Probe C shows the data and the analysis both
  work), refer them to the timing node around the limit cycle via an impulse
  sensitivity function, integrate to a period-jitter figure, and **validate
  the round trip** against an independent construction before any number from
  it is quoted. The validation is the load-bearing part: an uncalibrated
  pipeline reproduces Probe B's defect with more steps. Result would be
  **derived**, never **measured**.
- **(b) Run the analysis in a simulator that has it natively.** The gf180mcu
  PDK ships Xyce models (`libs.tech/xyce`) alongside the ngspice ones. Whether
  this repository adds a second simulator is a scope and tool-policy question
  for the operator, not a Builder's call, and CLAUDE.md's flow commitment is
  to xschem + ngspice. Named because it exists, not recommended here.
- **(c) Measure it on silicon** into `measurements/`, per Decision 2.

Until one of those lands, `docs/chipalooza/challenge-5-proposal.md` §5's
random/noise-driven row stays **UNMET** and should.

**5. No `2AMLogic/klayout-tools` issue is owed for this.** CLAUDE.md's friction
protocol covers gaps in `klt`; this is a SPICE-analysis gap with no layout
component. Stated so a reader does not read the protocol as skipped.

## Alternatives considered

- **Publish a `trnoise()`-driven number and label it approximate.** Rejected.
  Probe B shows what such a number is: the amplitude the deck author typed,
  propagated through the ring. "No claim without a testbench" is not satisfied
  by a testbench whose answer is an input. All six existing records already
  refused this, for the same reason.
- **Derive the random half analytically from a Leeson or Hajimiri–Lee model
  using the PDK's `noia`/`noib`/`noic`.** Not rejected as *wrong* — it is
  route (a)'s final step — but rejected as a shortcut around it. The hard part
  is not the closed-form; it is referring per-device PSDs to the timing node
  over the limit cycle, which route (a) has to do anyway. Doing the closed-form
  with literature constants instead of extracted ones would be the invented
  number CLAUDE.md forbids, wearing an equation.
- **Relax the ≤ 1.0 % RMS row to cover the deterministic component only, so
  the 45-corner PASS discharges it.** Rejected, and named explicitly because
  it is the tempting move. CLAUDE.md: "agents do not relax the ratified spec
  to make results pass". The row's obligation is unchanged by this record;
  only the honesty of its status column is.
- **Add a caveat to the row's target — e.g. "≤ 1.0 % RMS, deterministic
  component".** Rejected as the same relaxation in softer wording. The
  deliverable a system integrator budgets against is total period jitter. A
  target that silently excludes the random half is a target for a different
  quantity.
- **Leave `#13` with a footnote saying it is closed.** Rejected on DR-019's
  reasoning: a ratified table is read by people who do not read footnotes, and
  the failure being fixed is a reader concluding the obligation was
  discharged.
- **Re-point at #237 (the parent epic) or record the row as unowned.**
  Rejected: #505 is open, specific, and exists for exactly this gap. DR-019
  recorded its reference-jitter half as unowned only because nothing open held
  it; that is not the case here.
- **Hold this record until a measurement or a pipeline exists.** Rejected. The
  attribution defect is live today — since 2026-09-08 the ratified table has
  pointed this obligation at a closed issue — and it is independent of the
  measurement. Deferring would also leave the gap unowned for the length of
  the deferral, which is the failure being repaired.

## Consequences

- **`spec/pll.md` changes in four places and no requirement moves.** Summary
  table row 5's Status column now names the random half as not obtainable on
  this flow; the [Period jitter](../pll.md#period-jitter) section's "Limits of
  the present evidence" states Decision 1's finding and Decision 2's
  deterministic-only-in-simulation position; and both Verification-owed
  Period jitter rows get open owners. The **≤ 1.0 % RMS** target, the
  **≤ 20 mV pp** ripple condition and the **< 0.5 %** stretch are all
  byte-identical after this record.
- **Row 5's `#13` parenthetical is kept, deliberately.** There it labels which
  campaign produced the six committed records — provenance for work that
  happened, which is the one use of a closed issue number that stays true.
  `docs/lib/check-issue-reference-state.sh`'s rule 3 exempts exactly this, and
  changing it would erase the trail to the records' own history.
- **No `sim/` record is added, superseded or rewritten, and no number in
  `sim/` changes.** This record mints no evidence and quotes none that did not
  already exist. `sim/CHARACTERIZATION.md`'s two `period-jitter` rows were
  checked against it and were already accurate; they gain a pointer to this
  record and nothing else. The three probes above are simulator probes, not
  design measurements, and are inline here rather than in `sim/` for that
  reason.
- **The bad consequence, stated plainly.** This record produces no jitter
  number and — unlike DR-019, which at least landed a campaign directory — no
  path to one that anyone is currently resourced to walk. It converts an
  unowned, indefinitely-open gap into an owned gap with named exit conditions
  and a written-down reason, and that is *all* it does. The most likely honest
  outcome for v1 is exit (c): the row's random half is answered by
  `measurements/` after tape-out, not by `sim/`. Anyone reading
  `docs/chipalooza/challenge-5-proposal.md` §5 still finds one row this
  project cannot report a number for, and should.
- **A second-order consequence for DR-019.** DR-019 sequenced the Reference
  input row's numeric reference-jitter limit "behind the noise methodology at
  #505". Decision 1 makes that sequencing concrete: that limit needs a
  closed-loop noise bench, which needs the pipeline of exit (a). It is behind
  this gap, not beside it.
- **Nothing in `design/` or `layout/` changes**, no schematic, no netlist, no
  GDS, and the append-only trees are untouched.
