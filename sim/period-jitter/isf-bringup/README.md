# `period-jitter` ISF bring-up — measuring Γ, and nothing else yet

**This directory produces no jitter number, and nothing in it belongs in
`spec/pll.md`.** It brings up *one ingredient* of the impulse-sensitivity-function
(ISF) route to random period jitter — the impulse sensitivity function itself —
and answers the single question
[#520](https://github.com/2AMLogic/gf180-pll/issues/520) names as that route's
load-bearing risk:

> The load-bearing risk is Γ: it needs one transient per injection phase per
> node, and its accuracy near the switching edge is exactly where timestep
> control is weakest. A bring-up that cannot show Γ converging against timestep
> is a negative result worth recording, not a failure to hide.

Run it:

```sh
sim/period-jitter/isf-bringup/run.py                     # ~45 min, one core, one corner
sim/period-jitter/isf-bringup/summarize.py > sim/period-jitter/isf-bringup/results/SUMMARY.md
```

One ngspice process at a time, one PVT point, by construction — this is a
single-corner method bring-up, not a campaign. A PVT grid belongs on the batch
fleet through `sim/harness`, and is what the *pipeline* would owe once it exists;
see [What this does NOT establish](#what-this-does-not-establish).

Every number quoted below is in
[`results/SUMMARY.md`](results/SUMMARY.md), regenerated from
[`results/*.json`](results/) by `summarize.py` rather than transcribed by hand.

<!-- toc -->

- [What the ISF route needs, and which part this is](#what-the-isf-route-needs-and-which-part-this-is)
- [Method](#method)
- [What it found](#what-it-found)
- [What this does NOT establish](#what-this-does-not-establish)
- [Files](#files)

## What the ISF route needs, and which part this is

[`DR-023`](../../../spec/decision-records/DR-023-random-period-jitter-owner-and-cyclostationary-gap.md)
located the gap precisely: ngspice-46 *does* hand over each device's thermal and
flicker generators at a bias point (`.noise`, per device, per mechanism), and
this build has *no* periodic-steady-state analysis to weight them over the
oscillation trajectory (`pss: no such command available in ngspice`). The ISF
route is the hand-built substitute for that missing weighting. Writing it out in
the form this repository would actually evaluate, the variance of one period is

```
var(ΔT) = (1 / ω₀²) · ½ · ∫₀ᵀ h(t)² · S_i(t) dt          summed over noise sources
```

for a noise current of one-sided PSD `S_i`, where `h(x) = Γ(x)/q_max` is the
phase shift per unit injected charge, in rad/C. Three ingredients, and only one
of them is this directory:

| Ingredient | Status |
|---|---|
| **`h(x)`** — phase shift per unit injected charge, per node, across the cycle | **this directory** |
| **`h_ds(x)`** — the same thing for a two-terminal generator, i.e. `h(drain) − h(source)`, which is what a device's channel noise is actually weighted by | **this directory**, and see [What it found](#what-it-found): it is not obtainable from the per-node tables by subtraction |
| `S_id(V_gs, V_ds)` — each ring device's thermal and flicker generator across the bias it actually traverses | not built; [`probe_sid_bias.sp.in`](../noise-toolchain-probe/probe_sid_bias.sp.in) is one 1-D slice of it |
| the trajectory itself — `(V_gs, V_ds)(t)` per device, to evaluate `S_i(t)` along | not built |

`h` rather than `Γ` is reported throughout, deliberately. `q_max` is a modelling
convention (which node, which swing, which capacitance) while `h` is directly
measurable, and every `q_max` in the textbook statement of the sum above cancels
against the one inside `Γ`. The cost of that choice is that these numbers are
not directly comparable with a published `Γ`-normalised plot; the benefit is that
a whole class of convention error never enters the pipeline.

## Method

**Charge in, phase shift out.** A current pulse of known area `dq` is injected
onto one ring node at one phase of the cycle; several cycles later the
oscillator has settled back to its limit cycle, displaced in time by a constant
`Δt`. Then `h = −2π·Δt / (T·dq)` (a *later* edge is a phase *lag*, hence the
sign). Sweeping the injection phase over one period gives `h(x)`.

**Both trajectories in one deck.** `Δt` is 0.1–40 ps against a 6.67 ns period.
Two separate ngspice processes would integrate the perturbed and unperturbed
trajectories on two independently-chosen adaptive timestep grids, and that grid
difference alone is the same order as the quantity being measured. So every
injection phase is a *copy of the whole VCO inside one deck*, alongside one
uninjected reference copy: ngspice picks a single timestep sequence for the
whole circuit, every copy is integrated on it, and the grid error is
common-mode. The copies share only the ideal supply node and are otherwise
disjoint. `sim/vco-tuning-range/testbench/tb_vco_tuning.sp` already uses the
same one-deck-many-copies construction for a different reason (seven control
voltages in one transient).

**The ring is not re-drawn.** ngspice will not connect a circuit element to a
subcircuit's internal node — and, worse, it does not say so: `iinj 0 xa.Y1 …` is
accepted and silently creates a *new top-level node* called `xa.y1`, so the
injection does nothing and the run looks healthy. (Confirmed on the pinned
ngspice-46 during this bring-up: the measured period came back bit-identical
with and without a 1 µA / 10 ps injection that, had it connected, would have
moved the node by volts. Anyone reproducing this should expect the same trap.)
Rather than hand-copy the ring into a testbench — which would drift the moment
`design/vco.sch` changes — [`isf_deck.py`](isf_deck.py) **derives** port-widened
wrappers from the committed `design/netlist/vco.spice` at deck-build time:
`vco_stage_isf` is `vco_stage` with `NH`/`NT` promoted to ports, `vco_isf` is
`vco` with `Y1..Y5` plus each stage's `NH`/`NT` promoted to ports. Every device
line is the committed netlist's own text; the transformation touches only
`.subckt` headers and the five `XS*` instance lines, and raises loudly if the
committed port order or stage count is not what it assumes.
`sim/tests/test_isf_bringup.py` pins all of that against the committed netlist,
off any simulator.

**Operating point.** typical / 27 °C / 3.30 V, VCO band code 6, Vctrl = 1.795 V
— `sim/period-jitter/testbench/tb.json`'s own release voltage for that corner,
i.e. the 150 MHz point the deterministic half of this row is already measured
at. Reusing it rather than inventing one is deliberate: whatever this bring-up
eventually feeds must sit on the same operating point as the measurement it
would be added to.

**One corner, on purpose.** A PVT grid would multiply the cost of an unvalidated
method by 45 before anyone knows whether the method converges. The convergence
question is an integration-error question and is corner-independent *in kind*;
answering it is the whole purpose of a bring-up. This is the same reasoning
[`../noise-toolchain-probe/`](../noise-toolchain-probe/) states for being
single-corner, and for the same reason neither directory mints an evidence
record.

**A noise generator is an element, not a node.** A MOSFET's channel-noise
generator is a current source *between* drain and source: it removes charge from
the drain and adds the same charge to the source. The phase shift it produces is
therefore weighted by `h_ds = h(drain) − h(source)`, and a jitter sum built from
`h(Y)` alone would be weighting a current that does not flow. The `diff` stage
measures `h_ds` **two ways in one deck** — directly, by injecting between the two
nodes, and by subtracting the two single-node measurements — because the two
must agree *in the `dq → 0` limit* by linearity, and comparing them is the only
evidence available *about the deck* (that the injection lands on the nets it
names) rather than about its own internal consistency. Both are measured at
finite charge, so how far they can agree at a given phase is bounded by how
charge-dependent `h` is at that phase; [What it found](#what-it-found) items 2
and 4 are that bound, measured. It is why the direct injection is not a luxury.

**Four checks, not one number.** The bring-up refuses to report `h` without all
four:

1. **Settling.** After the injection, `Δt` must go *constant* — an impulse that
   leaves a residual drift has changed the frequency, not the phase, and is
   outside the ISF formalism. The reduction reports the settled tail's
   peak-to-peak spread and its least-squares slope beside every `h`.
2. **Linearity in `dq`.** The ISF is defined for an infinitesimal impulse. `h`
   must be independent of the injected charge over the range used — and the
   sweep must reach *below* the charge in use, or it cannot answer the question
   it is asked. It must also be swept at the phases where the window is
   *narrowest*, not only where `h` is largest: see finding 2.
3. **Convergence in the timestep ceiling.** `h` must be independent of `tmax`.
   This is the check #520 calls load-bearing.
4. **The two constructions of `h_ds` are compared.** Nothing inside a single
   construction can detect an injection that silently landed on the wrong net.
   The comparison is informative only where both constructions are in their
   linear range, and the sweep in check 2 is what says where that is.

**Charge, not amplitude.** ngspice's `PULSE(V1 V2 TD TR TF PW PER)` is a
*trapezoid*: the charge it delivers is `amp·(PW + TR/2 + TF/2)`, not `amp·PW`.
`isf_deck.injection_amplitude` therefore sizes the amplitude as `dq/(PW + TR)` so
that the area delivered is the nominal `dq` every `h` is normalised by. The first
revision of this directory set `amp = dq/PW`, which at `PW = 10 ps` and
`TR = TF = 1 ps` delivered 1.10·`dq` and biased every reported `h` 10 % high (and
every `h²`, the form that enters the jitter sum, 21 % high). Pinned now by a test
that asserts the trapezoid's *area*, since an assertion on the plateau amplitude
is structurally incapable of catching it.

**The failure mode a fifth stage exists to make legible.** The one-deck
construction has a copy-count ceiling, and above it the transient aborts with
`Timestep too small` in the first 20 fs — while ngspice still writes a `clk.dat`
with one or two rows in it, so the first thing that actually complains is the
reduction dividing by an empty crossing list, several steps downstream of the
cause. The `capacity` stage measures that ceiling on injection-free 3 ns decks,
`run_deck()` now refuses any run whose log carries an abort, and the `diff`
stage's phase set is sized under the measured ceiling rather than chosen for
symmetry.

## What it found

See [`results/SUMMARY.md`](results/SUMMARY.md) for the full tables — every
number below is in it, regenerated from `results/*.json` by `summarize.py`. The
headline, in the order the results bind:

**1. Γ converges against the timestep, and #520's load-bearing risk is
retired.** Halving the internal-timestep ceiling **from 2 ps to 1 ps** moves `h`
by **≤ 0.02 %** at every sampled phase, and 4 ps is within 0.14 % of the 1 ps
limit. That is the convergence statement, and the qualifier in it is
load-bearing: **it is a statement about the last halving, not about every
halving.** The 8 ps → 4 ps halving moves `h` by up to **2.32 %** (at phase 0.25,
where \|h\| is 20× below its peak), so the *span* of the whole sweep against its
1 ps limit is 2.36 %, and 8 ps is not a converged setting. The bring-up runs at
2 ps, where the remaining change towards the limit is 0.02 %. The switching edges
— where #520 predicted the difficulty, and where a Γ²-weighted sum is dominated —
are the *best*-converged points in the table, at 0.004 % and 0.014 % over that
last halving. The prediction was reasonable; it is not what this simulator does,
on this construction. What the sweep does **not** cover is the two phases on the
steep flanks of `h(Y)` before its zero crossings; see finding 4.

**2. The prediction was not wrong about the numerics, only about which
one.** The construction is what makes the timestep harmless: the perturbed and
unperturbed trajectories share one deck and therefore one adaptive timestep
sequence, so the grid error is common-mode in the difference being measured. What
*does* bite is the injected charge. The pilot 2 fC — chosen to put the phase
displacement comfortably above the numerical floor — is **+10.48 %** (falling
edge) and **+6.76 %** (rising edge) away from the `dq → 0` limit, and 8 fC is
+30.5 %. At the four phases that sit at the peaks and the flats of `h(x)`, below
0.25 fC the response is linear: `h` moves 0.21–0.75 % over the last halving, so
the limit is established there rather than assumed. A linearity sweep whose
smallest charge is the one in use cannot detect this, which is why this one goes
down to 0.125 fC.

**And the linear window is a property of the phase, not of the ring.** The sweep
also runs at the two phases sitting on the steep flanks of `h(Y)` immediately
before its zero crossings (1/6 and 2/3), and there it does not converge at all
over the charges used: the 2 fC pilot is **−55.7 %** and **−154 %** from the
0.125 fC value, 8 fC **inverts the sign** at phase 1/6 (−120 %) and is −963 % at
2/3, and even the last halving from 0.25 to 0.125 fC still moves `h` by **4.31 %**
and **7.34 %** — an order of magnitude worse than at any other sampled phase. The
mechanism is geometric rather than mysterious: where `h` is small and `dh/dx` is
enormous, the second-order term in the response — the injection displacing the
trajectory while it is still being delivered, which scales as `dq²·dh/dx` — is
comparable to the linear `h·dq` term, and the linear term is what `h` is defined
as. At those two phases `|d ln h/dx|` is 161 and 315 per cycle against 0.3–23 per
cycle everywhere else in the sampled set. This is the finding that explains
finding 4, and it is why the two phases were added to the sweep.

**3. The quantity the jitter sum needs is not the one the per-node tables
give.** A device's channel generator is a current source between drain and
source, so it is weighted by `h_gen = h(source) − h(drain)`. On this ring the two
node ISFs are nearly equal: at the strongest cancellation the residue is
**1.54 %** of the larger term, so a pipeline building `h_gen` by subtraction
needs ~65× the precision the per-node tables demonstrate. Measured as a
difference, the residue's signal-to-floor falls as low as **1.8** (median 35).
Injected directly between the two nodes it is **34 at worst, median 254** — the
direct injection buys an order of magnitude, and it is the construction a
pipeline must use.

**4. The two constructions agree only where the ISF is locally linear, and how
far they agree is set by the phase, not by the charge.** This is the finding
stated most carefully, because it is the one that is easiest to overstate — and
the first draft of this file did overstate it.

- **Where they agree, they agree very well.** 3 of the 12 pair/phase points come
  in under 1 %: **0.06 %**, **0.07 %** and **0.23 %**. All three are at phases
  where the single-node `h(Y)` is charge-independent to 0.1–0.3 % (finding 2's
  peaks and flats).
- **Where they disagree, they disagree badly.** 4 of 12 disagree by ≥ 36 %, the
  worst being `Y-NH` at phase 2/3 (**107.6 %** signed) and `Y-NT` at phase 1/6
  (**97.7 %**). Median across all 12 is 16.6 %. A headline of "the two
  constructions agree" is not what this table says.
- **The charge *ratio* does not explain it, and the first draft's claim that it
  did was wrong.** The two worst rows have charge ratios of 1.21× and 1.52×,
  while `Y-NH` at phase 1/12 agrees to 0.23 % at a **16×** ratio. Ranked against
  the ratio, the disagreement has a Spearman rho of **−0.00** — no relationship
  at all.
- **What does explain it is the single-node charge dependence at the same
  phase** — measured, not argued: rho = **+0.93** over the 12 rows. That is
  finding 2's result applied pointwise. At a phase where `h(Y)` itself moves
  31–50 % between the two charges in play, two differently stimulated
  constructions cannot agree better than that, whatever either one's numerical
  floor says. Both columns are in [`results/SUMMARY.md`](results/SUMMARY.md),
  regenerated from the JSON.
- **The one row that needs saying out loud.** `Y-NH` at phase 2/3: the direct
  injection gives `h_gen = −6.25e10` (at 1.42 fC, 34× above its own floor) and
  the subtraction gives **+8.22e11** (at 1.17 fC, 48× above its own floor) — 13×
  larger *and* opposite in sign, with neither side near its floor and a charge
  ratio of only 1.21×. Phase 2/3 is exactly one of the two flanks finding 2
  identifies: `h(Y)` there is −6.34e11 at 0.125 fC and −1.11e12 at the 1.17 fC
  the subtraction used, i.e. **1.8× its own `dq → 0` value**, and the residue
  inherits that. So neither number is a measurement of the ISF at that phase;
  both are finite-amplitude probes of a quantity whose charge derivative is
  enormous there. That is an explanation, not an excuse: at this phase the
  cross-check provides **no** evidence about the deck, and the bring-up does not
  claim any.
- **What the cross-check *is* evidence for, and it earned its place on its first
  run by catching a sign error.** It returned ~200 % signed disagreement with
  ~0 % magnitude disagreement at the high-signal points, which is the
  unmistakable signature of a sign convention: `h_gen` had been defined
  drain-minus-source, the negative of the generator's own sensitivity. Only
  `h_gen²` reaches the jitter sum, so that error would never have shown up in a
  final number, and nothing internal to either construction would have revealed
  it. The 0.06 %/0.07 %/0.23 % agreements at the Γ²-dominant phases are real
  evidence that the pair element lands on the nets it names. The claim is
  therefore: **the deck is corroborated at the phases that matter to the sum, and
  the comparison is amplitude-limited and uninformative at the ISF's zero
  crossings.**

**5. The one-deck construction has a measured copy ceiling, and it costs phase
resolution.** 31 copies complete; **37 abort** with `Timestep too small` in the
first 20 fs. Above the ceiling ngspice still writes a `clk.dat` with one or two
rows, so the first thing to complain is the reduction dividing by an empty
crossing list — several steps downstream of the cause. `run_deck()` now refuses
any run whose log carries that abort, and the `diff` stage's six phases are what
fits under the ceiling once three node classes and two pairs are budgeted for.
For a pipeline this is a real cost: phase resolution per deck is capped, so a
finer `h_gen(x)` needs several decks and therefore loses the single-grid
guarantee between them — or needs the ceiling itself raised, which is a
simulator-settings question this bring-up does not open.

**What none of this is.** No jitter number, at any corner. See below.

## What this does NOT establish

Stated as a list because each line is a reason no jitter number appears here,
and a reader who skips them will over-read what is above.

- **No random period-jitter number is produced, at any corner.** Two of the
  three ingredients in the table above do not exist. `spec/pll.md`'s
  Verification-owed row is unchanged by this directory, still owned by #520, and
  `docs/chipalooza/challenge-5-proposal.md` §5 still reads **UNMET** against the
  random component — correctly.
- **DR-023 is not overtaken.** Its §Decision 2 says the finding is falsified "if
  `pss` resolves, or if an ISF pipeline demonstrates convergence". `pss` still
  does not resolve, and a converging Γ *extraction* is not a converging
  *pipeline*: it is one of three ingredients, and the two missing ones are where
  the cyclostationary weighting actually happens. No decision record is
  superseded or amended by this directory.
- **Three node classes are not all the noise-injection points.** `h` is measured
  at the stage output `Y` and at the two current-source nodes `NH`/`NT`. The VCO
  bias generator (`vco_bias`, a couple of dozen devices) also injects noise, via
  `VBP`/`VBN`, and no `h` is measured for those nodes. A sum over the three
  measured classes alone would be a *lower* bound presented as a result.
- **`h_gen` is measured for two device pairs at six phases, not for every
  generator across the cycle.** The `diff` stage covers the two switching
  devices' channel generators (`Y`–`NT`, `Y`–`NH`) at the six phases the
  `capacity` ceiling affords, chosen at the switching edges where a Γ²-weighted
  sum is dominated. The two current-source devices' own generators
  (`NH`–`VDD`, `NT`–`GND`) are not measured, and the phase resolution is coarser
  than `gamma`'s 24-point single-node curve. What the stage establishes is the
  *method* and the precision it needs, not a complete `h_gen(x)` set.
- **No `h` here is the `dq → 0` limit at the ISF's zero crossings.** At the two
  phases on the steep flanks before `h(Y)` changes sign, the linearity sweep does
  not converge over the charges used — the last halving still moves `h` by 4.31 %
  and 7.34 %, and the 8 fC point inverts the sign at one of them. Every number
  reported at those phases (including both `h_gen` constructions, and the
  cross-check between them) is a finite-amplitude reading, not an ISF. A pipeline
  that needs `h` there must extract it by extrapolating a charge sweep to zero,
  not by measuring at one charge. What makes this tolerable rather than fatal is
  that a Γ²-weighted sum is dominated by the phases where \|h\| peaks, and \|h\|
  at these two is 15–30× below that peak (so `h²` is 200–1000× below) — but that
  is an argument about *weighting*, not a licence to report the number, which is
  why it is listed here instead.
- **The timestep convergence sweep does not cover those two phases either.** Its
  four phases are the peaks and the flats. The ≤ 0.02 % last-halving figure is a
  statement about those four, and is silent about the flanks.
- **Mismatch is off and there is no Monte Carlo.** Same limitation the
  deterministic `sim/period-jitter` records carry.
- **Schematic-level only**: no layout parasitics. A ring node's capacitance is
  precisely what `h` scales against, so extracted parasitics would move these
  numbers.

## Files

| File | What it is |
|---|---|
| [`isf_deck.py`](isf_deck.py) | Derives the port-widened wrappers from the committed netlist and assembles the multi-copy deck, including the two-terminal (drain-to-source) injection element |
| [`isf_extract.py`](isf_extract.py) | Waveform → crossing sequence → settled `Δt` → `h`, using `sim/vco-tuning-range/testbench/_numeric.py`'s crossing primitive; plus the differential ISF `h_gen`, its floor and the two-construction cross-check |
| [`run.py`](run.py) | The seven stages, sequentially, one ngspice process at a time |
| [`summarize.py`](summarize.py) | `results/*.json` → [`results/SUMMARY.md`](results/SUMMARY.md) |
| [`results/`](results/) | The committed evidence this directory's claims rest on |
| [`logs/`](logs/) | Captured ngspice output for every deck |
| `sim/tests/test_isf_bringup.py` | The derivation and the reduction, pinned off any simulator (runs in `sim/selftest.sh`) |
