# DR-001: PLL architecture selection — loop type, VCO delay cell, feedback divider

- **Status**: Proposed (survey + recommendation; pending engineering
  ratification through the same governance path as the target spec — see #1)
- **Date**: 2026-07-30
- **Decided by**: Builder agent, issue #3
- **Related**: #1 (spec ratification — consumes this record), #6
  (decision-record template — had not merged when this record was written;
  format follows the convention that template states, see *Format note*
  below), #7 (open draft-spec ambiguities — sensitivities flagged in
  §"Sensitivity to the open spec questions in #7"), #8 (ring VCO / Kvco
  extraction — consumes Decision 2), #9 (PFD + charge pump + loop filter —
  consumes Decision 1), #11 (feedback divider — consumes Decision 3)

**Format note.** #6 will land a decision-record template adapted from the
sister repo `2AMLogic/gf180-bandgap`, whose `spec/decision-records/TEMPLATE.md`
prescribes `spec/decision-records/DR-NNN-<slug>.md` with sections Status /
Date / Decided by / Context / Decision / Alternatives considered /
Consequences. This record follows that convention ahead of #6 rather than
inventing a second one; if #6 ratifies a different shape, reformat in place
(this record is *proposed*, not ratified, so reformatting is not a rewrite of
ratified history). That template also says "one decision per record" — this
record deliberately carries three, because the three choices are mutually
constraining (§"Why these three are one decision"). If #6's one-per-record
rule is enforced strictly, split this into DR-001/002/003 preserving the text.

---

## Decision summary

| # | Question | Decision | Consumed by |
|---|---|---|---|
| 1 | Loop type | Type-II charge-pump PLL: tri-state PFD + charge pump + **passive** 2nd-order (R + C1, C2) filter. Fixed R/C, coarse (2-bit) Icp trim only. | #9 |
| 2 | VCO delay cell | **Single-ended CMOS inverter ring, current-starved** (matched PMOS head + NMOS tail devices), odd stage count (5 nominal), 3-bit **coarse band select** + fine analog Vctrl through a source-degenerated V→I converter. Dedicated `vdd_vco` domain. | #8 |
| 3 | Feedback divider | **Cascaded ÷2/3 (Vaucher) cells**, 6 cells with programmable chain length for continuous N = 4–64, static CMOS logic throughout, **final retiming DFF clocked by the VCO** before the PFD. | #11 |

Everything below is the rationale. Numbers marked *sanity check* are
first-order hand calculations used to disposition options, not design values —
#8/#9/#11 own the real sizing, and every number here must be re-derived from
extracted devices before it enters the spec.

---

## Context

The README target table is DRAFT (ratification is #1) and already fixes the
outer architecture: integer-N, ring-oscillator VCO. What it does not fix is
the loop type, the delay-cell style, or the divider architecture — and #8, #9
and #11 each declare themselves blocked on exactly one of those. This record
surveys the options and picks, so schematic work starts from a fixed
architecture instead of re-litigating it per block.

The draft targets that actually do work in this record:

- **Output 10–200 MHz** (stretch 10–400 MHz) — a **20:1** continuous tuning
  range (40:1 with the stretch). This is the single most architecture-defining
  line in the table.
- **N = ×4–×64 integer** — a 16:1 span that must be *continuous* over the
  integers, including small N.
- **Ref 1–25 MHz** (stretch 32 kHz) — a 25:1 span in the sampling rate of the
  discrete-time part of the loop.
- **Lock < 100 µs** (stretch < 20 µs).
- **Period jitter < 1% RMS** (stretch < 0.5%) — 10 ps RMS at 100 MHz.
- **Power < 5 mW @ 100 MHz** (stretch < 2 mW).
- **Area < 0.15 mm²** — the binding constraint on the loop filter.
- **Supply 3.3 V ±10%** (2.97–3.63 V), stretch 1.8 V core variant.

Two node facts shape the survey as much as the targets do:

- gf180mcu's open primitive set (`gf180mcu_fd_pr`) gives us `nfet_03v3` /
  `pfet_03v3`, MOS caps (`cap_nmos_03v3`, `cap_pmos_03v3`), MIM caps
  (`cap_mim_1f0fF` / `1f5fF` / `2f0fF`) and poly resistors (`ppolyf_u_1k` /
  `2k` / `3k`). Loop-filter capacitance is therefore cheap in *density* terms
  (MOS cap ≈ 4–5 fF/µm², to be confirmed against the PDK) but still the
  largest single area item in the block.
- The two open standard-cell libraries for this node (`gf180mcu_fd_sc_mcu7t5v0`,
  `gf180mcu_fd_sc_mcu9t5v0`) are **5 V-flavor** libraries. A 3.3 V-domain
  divider cannot simply instantiate them, so every divider flop is a
  custom-drawn 3.3 V CMOS cell in xschem. **Architectures are therefore scored
  partly on how few *distinct* custom cells they need** — this is a real cost
  here in a way it would not be in a node with a matching digital library.

Finally, the evidence rule from CLAUDE.md ("no claim without a testbench")
makes *verifiability in ngspice* a first-class selection criterion, not an
afterthought. An architecture whose headline advantage cannot be demonstrated
in this flow buys us nothing on the canary.

## Why these three are one decision

The three questions are not independent, and the coupling is the reason for
the specific combination chosen:

1. A **current-starved** ring has `f_osc ∝ I_ctrl`, so `Kvco = ∂f/∂V ∝ f_osc`.
2. The loop's unity-gain frequency for a type-II CP-PLL is
   `ω_c ≈ Icp·Kvco·R / (2π·N)`. With `N = f_out/f_ref` and `Kvco ∝ f_out`, the
   `f_out` terms cancel: **`ω_c ∝ Icp·R·f_ref`**.
3. So `ω_c/ω_ref` — the ratio that sets stability margin in a sampled loop —
   is approximately **invariant across the entire 10–200 MHz output band and
   the entire N = 4–64 range**, with a *fixed* passive filter.

That is what makes a fixed passive filter viable here (Decision 1) and it is
a property of the current-starved cell specifically (Decision 2); a
supply-regulated ring does not deliver it as cleanly. And the divider choice
(Decision 3) is constrained by the same 20:1 band: the divider must work at
10 MHz *and* 200 MHz, which rules out dynamic logic families. Recording the
three separately would hide the coupling.

---

# Decision 1 — Loop type

## Decision

**Classic type-II charge-pump PLL**: tri-state phase-frequency detector →
charge pump → **passive** second-order loop filter (series R + C1, shunt C2)
→ ring VCO → feedback divider. No active filter, no opamp in the loop path.
Filter R and C are **fixed**; the only programmability is a coarse (2-bit)
charge-pump current trim as a margin knob.

## Alternatives considered

**Sub-sampling / sampling PLL — rejected.** A sub-sampling phase detector
removes the divider from the noise path and its in-band phase noise does not
degrade with N, which is genuinely attractive at N = 64. But it has **no
frequency-detection capability**: it locks to whichever VCO harmonic is
nearest, so it mandates an auxiliary frequency-locked loop plus a handover
scheme. Two facts kill it for this block: (a) our VCO must be acquired over a
20:1 range with the free-running frequency unknown to within a factor of ~2
over PVT, which is exactly the regime where the FLL is doing all the real
work and the sub-sampling loop is a refinement; and (b) the benefit it buys
is in-band **phase noise**, and per #7 we cannot yet promise that ngspice will
substantiate a phase-noise number at all (a free-running oscillator's phase
noise is not an AC `.noise` result). We would be paying two loops' worth of
area, power and verification effort for an improvement we cannot put evidence
behind. Revisit for a v2 low-jitter variant once the measurement path exists.

**Injection-locked clock multiplier — rejected.** Lock range for a ring ILCM
is a small fraction of the free-running frequency, so the ring must already
sit within a few percent of `N·f_ref` — which on gf180mcu, across corners and
across a 20:1 programmed band, it will not, by a wide margin. Making it work
requires a background frequency-tracking loop and a calibration engine. Same
verdict as sub-sampling but worse: more calibration infrastructure, and the
headline benefit (very low jitter for very low power) is again a phase-noise
claim we cannot currently evidence.

**All-digital PLL (TDC + digital loop filter + DCO) — rejected for v1.** The
attraction is real: the loop filter capacitor is the largest passive in the
block, and an ADPLL deletes it. The Caravel management SoC's ring-oscillator
clock multiplier (sky130) is an existence proof that this style is buildable
in an open PDK. But it is rejected here for three node/flow-specific reasons:

- **No matching digital library.** The digital loop filter would have to be
  synthesized against a 5 V standard-cell library while the analog runs at
  3.3 V, or hand-drawn. That is a mixed-domain integration problem on top of
  the actual design problem.
- **Verification cost is the deal-breaker.** Our flow is xschem + ngspice.
  Verifying an ADPLL means transistor-level simulation of a TDC and a
  multi-bit digital filter over many reference cycles, or a mixed-signal
  co-simulation path this repo does not have. The canary is supposed to
  produce evidence, and this choice makes evidence 10–100× more expensive.
- **TDC resolution vs. the jitter line.** Hitting 1% RMS period jitter needs a
  TDC whose quantization contribution is well inside that budget, plus DCO
  LSB fine enough not to limit-cycle — i.e. calibration infrastructure beyond
  a first canary.

Record it as the natural v2/derivative product, not as v1.

**Active (opamp-based) loop filter — rejected.** An active filter would let
Vctrl exceed the supply rails or be level-shifted, and would allow a
capacitance-multiplier trick to shrink C1. At 3.3 V we have ample Vctrl
headroom without it, and the opamp costs static current against a 5 mW budget
(2 mW stretch), adds its own 1/f noise directly onto the control node — the
most jitter-sensitive node in the block — and adds a second stability problem
nested inside the PLL loop. Reconsider **only** if the 1.8 V variant or the
32 kHz mode is ratified into scope (see §#7 sensitivities).

**Programmable R / C filter banks — rejected as unnecessary.** The closest
open-PDK prior art (§Prior art) exposes filter-cap, filter-resistor and
charge-pump-current trim pins because its VCO is narrowband (fixed ~96 MHz)
while its N varies 6–24, so `Kvco/N` swings 4:1 and the loop gain has to be
compensated externally. Our band-switched current-starved ring makes
`Kvco ∝ f_out`, so `Kvco/N ∝ f_ref` and the loop self-compensates
(§"Why these three are one decision"). We keep a 2-bit Icp trim as insurance
against the `Kvco ∝ f_out` proportionality being imperfect in silicon, and
drop the R/C banks — fewer pins, fewer switches in the highest-impedance node
in the block (switch leakage onto the control node is a spur mechanism).

## Sizing sanity check (disposition only — #9 owns the real design)

Using `ω_c = Icp·Kvco·R/(2π·N)`, zero placed at `ω_c/4`, `C2 = C1/10`,
`Kvco ≈ 0.7·f_out` per volt (from the band plan in Decision 2), and a target
`f_c = f_ref/20` (conservative against the `f_c < f_ref/10` sampled-loop
limit):

| Case | f_ref | N | f_out | f_c | C1 | C1 area (MOS cap) |
|---|---|---|---|---|---|---|
| Low ref, max N | 1 MHz | 64 | 64 MHz | ~50 kHz | ~130 pF | ~0.027 mm² (≈18% of budget) |
| High ref, min N | 25 MHz | 8 | 200 MHz | ~1.2 MHz | (same fixed C1 — loop is over-damped, dominant τ ≈ 13 µs) | — |
| Stretch: 32 kHz ref | 32.768 kHz | ~305 | 10 MHz | ~1.6 kHz | **~4 nF for ζ ≈ 1** | **~0.9 mm² — ≈6× the entire area budget** |

Read-outs: (a) a single fixed passive filter spans the whole ratified space
with lock times in the tens of µs, meeting <100 µs but **not** the 20 µs
stretch at the low end of the reference range; (b) `Icp` in the single-digit
µA range and `Kvco` bounded to roughly ≤150 MHz/V are *requirements* handed
to #8/#9, not free choices — an unbounded Kvco pushes C1 into mm² territory;
(c) the 32 kHz mode does not fit, at all, and that is a spec question, not a
design question (see #7).

Capacitor implementation note for #9: MOS caps give ~4–5 fF/µm² (vs ~1–2
fF/µm² MIM) and are the area-efficient choice for C1, at the cost of strong
voltage dependence — C1 must be evaluated across the whole Vctrl range, and
the accumulation-mode connection chosen so that C1 does not collapse at low
Vctrl (which would raise `ω_n` exactly where the loop is slowest). MIM is the
better choice for C2 and for anything in the R path, and MIM sits between top
metals so it can be stacked over the divider/PFD at near-zero incremental
area — worth exploiting if the MOS-cap voltage coefficient proves ugly.

---

# Decision 2 — VCO delay-cell style

## Decision

**Single-ended CMOS inverter ring, current-starved**, with matched PMOS-head
and NMOS-tail starving devices per stage, **odd stage count (5 nominal;** #8
to confirm against the 200 MHz top of band and the power budget**)**.

Control mapping, in order:

1. **Coarse: 3-bit band select** — a binary-weighted set of legs in the bias
   mirror (equivalently, switched starving-current segments) selects one of 8
   overlapping frequency bands, each covering roughly 2:1 with ~20% overlap.
   Five bands cover the 10–200 MHz (20:1) requirement; the 3-bit code leaves
   headroom for the 40:1 stretch ceiling without changing the control scheme.
   The band code is a **static configuration input alongside the N code** —
   there is no auto-calibration FSM in v1 (see Consequences).
2. **Fine: analog Vctrl** → a **source-degenerated V→I converter** → the bias
   mirror. Degeneration is the point: it compresses the effective
   transconductance so `∂I/∂Vctrl ≈ 1/R_deg` is roughly constant, which keeps
   Kvco from exploding at the top of the Vctrl range the way a bare square-law
   V→I would.
3. Frequency then follows `f_osc ≈ I_ctrl / (n · C_eff · V_swing)` — linear in
   the starving current, so `Kvco ∝ f_osc` within a band. Design intent is
   Kvco ≈ 0.7·f_out per volt (≈7 MHz/V in the lowest band, ≈140 MHz/V in the
   highest), with Vctrl usable over roughly 0.9–2.4 V of the 3.3 V rail.

**#8 consumes this as**: extract `f(Vctrl)` and `Kvco(Vctrl)` **per band, per
PVT corner**, and check both the band-overlap requirement (adjacent bands must
overlap across all corners, or the tuning range has holes) and the Kvco
ceiling that Decision 1's fixed filter assumes.

The VCO gets a **dedicated supply domain** (`vdd_vco` / `gnd_vco`), separate
from the reference/PFD and divider domains, with a supply-independent
(constant-gm) bias for the starving mirror and dedicated on-chip decoupling.

## Alternatives considered

**Supply-regulated ring (regulator sets ring VDD; Vctrl → regulator) —
rejected as the primary, retained as the documented fallback.** This is the
textbook low-jitter CMOS ring, and it is what the closest open-PDK prior art
uses (§Prior art: a 4-stage pseudo-differential ring off a regulated `vhi`
node). Its supply rejection is far better than a current-starved ring's, which
is the single biggest jitter risk we are accepting. It is rejected as primary
on **tuning range**: frequency is roughly proportional to `(V_reg − V_th)^~1.3`,
so a 20:1 range would need V_reg to span from just above threshold to the rail
— which is not achievable while keeping the regulator in regulation, and the
prior-art design only needs ±10% tuning, which is why it can afford the style.
Secondary reasons: the regulator is a second feedback loop nested inside the
PLL loop whose stability must be characterized across the entire load range
(the ring's current varies 20:1 with frequency), which is real ngspice work;
and it loses the `Kvco ∝ f_out` self-compensation that makes the fixed passive
filter work. **Fallback trigger**: if #8's supply-induced-jitter simulation
shows the current-starved ring cannot meet 1% RMS period jitter under a
realistic `vdd_vco` noise stimulus, the mitigation ladder is (i) improve the
bias/decap, (ii) add a regulator *in front of* the current-starved bias (keeping
the current control for range), (iii) supersede this record.

**Fully differential ring with symmetric loads + replica bias (Maneatis-style)
— rejected.** Best-in-class supply and substrate rejection, even stage counts,
quadrature availability. Costs: static bias current in every stage (against a
2 mW stretch budget), a replica-bias amplifier (another nested loop), reduced
swing requiring a level shifter to drive CMOS logic, and roughly 2× the device
count to draw and verify. The spec asks for none of what it buys — there is no
quadrature-output requirement — and for equal power a rail-to-rail single-ended
CMOS ring converts more charge per transition, which is the dominant term in
ring jitter.

**Pseudo-differential ring (inverter pair + cross-coupled latch) — rejected
for v1, but this is the closest call.** It gives most of the differential
common-mode rejection at near-CMOS power, allows an **even** stage count, and
is exactly what the sky130 prior art built. Two reasons it loses here: it needs
a level shifter / differential-to-CMOS converter before the divider (the prior
art has one: an extra cell, extra power, and a duty-cycle/skew error path
directly in the feedback), and the cross-coupled devices fight the starving
control, compressing the achievable tuning range — again, the prior art only
needed ±10%. **This is the option to revisit if the 400 MHz stretch is
ratified** (see #7 sensitivities).

**Single-ended ring with switched-capacitor (varactor/load) tuning — rejected.**
Load-capacitance tuning gives a much smaller range than current starving for
the same area and puts switches on the highest-frequency nodes. Useful as a
fine-trim vernier, not as the primary control.

## Consequences

- **Supply noise is the accepted risk.** A current-starved single-ended ring
  has the worst supply rejection of the options considered. Mitigations are
  mandated above (separate domain, constant-gm bias, decap) and #8 must
  produce a supply-step/supply-noise jitter testbench, not just a clean-supply
  Kvco sweep. This is the number most likely to force a supersede.
- **Band select is a static input in v1.** No auto-band-calibration FSM. That
  means a system using this block must know its band code, and it means a
  part programmed into the wrong band will not lock. If #7 pulls a lock
  detector into v1 scope, the natural next step is lock-detector-driven band
  search — which is an FSM, i.e. a scope change that supersedes this record.
- **Even/odd stage constraint.** Single-ended requires an odd stage count, so
  frequency granularity via stage count is coarse (5 → 3 stages is a 1.67×
  jump). #8 should confirm 5 stages meets 200 MHz at the slow corner with
  starving headroom left before committing.
- **No quadrature outputs.** Any future fractional-N or phase-interpolating
  derivative will need a different cell. Noted, not a v1 cost.
- **Duty cycle** at the VCO output is not controlled to better than the cell's
  rise/fall symmetry. The spec does not require an output duty-cycle figure;
  if one is added, the answer is an output ÷2, which halves the usable output
  band and would force a VCO band re-plan.

---

# Decision 3 — Feedback divider architecture

## Decision

**Cascaded ÷2/3 cells (Vaucher-style modular divider): 6 identical cells with
programmable chain length**, giving continuous integer N over the full
4–64 range:

| Active cells | N range |
|---|---|
| 2 | 4–7 |
| 3 | 8–15 |
| 4 | 16–31 |
| 5 | 32–63 |
| 6 | 64–127 |

The modulus-control chain is terminated at the last *active* cell (chain
length selected by the N code), so the division ratio is
`N = 2^k + Σ mᵢ·2^i` over the active cells — continuous integers, no holes,
and N = 64 is reachable exactly. Coverage extends free to 127, which is spare
margin, not a spec claim.

**Logic family: static CMOS throughout** (transmission-gate master-slave
flops), custom-drawn 3.3 V cells in xschem — no dynamic/TSPC or E-TSPC.

**Retiming: a final DFF clocked by the VCO** resamples the chain output before
it reaches the PFD. The feedback edge the PFD sees is therefore a VCO edge
delayed by exactly one flop's clk→Q, **independent of N**, rather than the
accumulated clk→Q of `k` cells (which varies with the programmed chain
length). The retimed pulse is shaped to be at least as wide as the PFD reset
delay. Setup budget for the retiming flop is one VCO period (5 ns at 200 MHz)
minus the chain's accumulated clk→Q — **#11 must close this at the slow corner
(SS, 125 °C, 2.97 V)**; if it does not close, the documented fallback is to
retime on the first cell's output (VCO/2), accepting coarser feedback-edge
quantization.

N is treated as a **static configuration** (set alongside the band code); the
loop re-locks after a change. Glitch-free on-the-fly modulus switching is
explicitly out of v1 scope — if it is ever needed, the modulus word must be
loaded synchronously to the divider output edge.

## Alternatives considered

**Pulse-swallow counter (÷P/P+1 prescaler + program counter M + swallow
counter S, N = P·M + S) — rejected on a hard range violation.** The classic
architecture, and the sky130 prior art uses it. But the pulse-swallow
structure requires `M ≥ S`, which puts a floor on the continuously reachable
N at roughly `P²` (or `P·(P−1)`). With the smallest practical prescaler,
÷4/5, the floor is **N ≥ 12–16 — and the spec requires N = 4**. The whole
4–15 region would need a prescaler-bypass mode, i.e. a second divider
architecture bolted onto the first, with a different feedback delay in bypass
than in normal mode (a loop-dynamics discontinuity right where N is smallest
and the loop is fastest). Note this is exactly why the prior-art design's N
range starts at 6 rather than at 1. Disqualified by the ×4 line in the spec
table.

**Synchronous programmable counter (binary counter + comparator + reload) —
rejected on power and custom-cell count.** Every flop is clocked at the full
VCO rate, so at 200 MHz a 7-bit counter burns roughly 7× the dynamic power of
the ÷2/3 chain's first cell, against a 5 mW total budget (2 mW stretch); and
the comparator-plus-reload path must settle within one VCO period (5 ns) at
the slow corner, a global timing path rather than a local one. The decisive
cost at this node is **custom-cell count**: with no 3.3 V standard-cell
library, a counter+comparator means hand-drawing an assortment of gates and
timing-closing them by simulation, whereas the ÷2/3 chain is **one cell,
verified once and replicated six times**. Reuse dominates here.

**Ripple (asynchronous) counter with decode/reload — rejected.** Lowest power
of all, since each stage runs at half the previous rate. But the output edge
arrives after the accumulated delay of every stage, which (a) varies with the
programmed N, giving an N-dependent static phase offset and an N-dependent
loop delay, and (b) piles every stage's delay noise into the feedback edge —
directly against a 1% period-jitter line. The retiming flop can mask (a) and
(b) only if the ripple chain's total delay still fits inside one VCO period,
which defeats the point of using ripple. Acceptable only for a divider whose
output is never a phase reference; ours is exactly that.

**Dynamic logic (TSPC / E-TSPC) for the first cell — rejected as the default,
retained as a targeted fallback.** TSPC would buy speed margin at the top of
the band. But dynamic logic has a **minimum** clock frequency (charge leaks
off dynamic nodes), and this divider must run at 10 MHz at the bottom of the
band — and much slower still during acquisition transients, when the ring can
briefly sit far below the band, and slower again at 125 °C where leakage is
worst. A divider that stops dividing during acquisition is a loop that cannot
acquire. Static CMOS has no minimum frequency and that property is worth more
here than speed margin we do not need at 200 MHz. E-TSPC additionally burns
static current. **Fallback**: lay out the first ÷2/3 cell so it is separately
swappable, so the 400 MHz stretch (see #7) can be addressed by replacing one
cell rather than the chain.

## Consequences

- **One cell to verify, six to instantiate.** The verification plan for #11 is
  a single-cell testbench (both moduli, both edges, min/max input rate, all
  corners) plus a chain-level ratio sweep over all N = 4–64, plus the retiming
  setup check. This is the cheapest evidence path of the options considered.
- **Interface contract to the PFD** (for #9): feedback edge is the retiming
  DFF's rising edge; pulse width ≥ PFD reset delay; feedback delay is constant
  vs. N, so the PFD's static phase offset does not move as N is reprogrammed.
- **Divider power scales as ~2× the first cell**, not `k ×`, since each cell
  runs at half the previous cell's rate — comfortably inside the budget, and
  it is the *first* cell that must be optimized, nothing else.
- **Divider gets its own supply domain** (`vdd_div`), consistent with the
  domain split adopted in Decision 2, so that divider switching noise does not
  land on the VCO supply.
- **N > 64 is reachable but unspecified.** The 6-cell chain covers to 127. Do
  not let that leak into the spec table as a claim without corner evidence.

---

## Sensitivity to the open spec questions in #7

Each item below states the condition under which one of the three decisions
above changes, so ratification in #1 can settle it deliberately.

**1. 32 kHz reference mode — the sharpest sensitivity; recommend it stays out
of v1.** Two independent problems:

- *Internal inconsistency in the draft table.* 32.768 kHz × the specified
  maximum multiplier (×64) is ~2.1 MHz, which is **below the 10 MHz output
  floor**. A 32 kHz reference with a 10–200 MHz output implies **N ≈ 305–6100**,
  not 4–64. The "Ref input: 32 kHz" row and the "Multiplier: ×4–×64" row
  cannot both be v1 as written.
- *It breaks Decision 1 quantitatively.* The sampled-loop limit caps `f_c` at
  a few kHz, and restoring ζ ≈ 1 at that bandwidth needs C1 in the **single-digit
  nF** range — roughly 0.9 mm², about **6× the entire 0.15 mm² area budget**
  (sanity check above). Lock time would also land in the hundreds of µs to ms,
  against a <100 µs spec.

*If ratified into v1 anyway*, Decision 1 changes to an active filter or a
capacitance multiplier (or a dual-loop scheme with an intermediate reference),
Decision 3 changes to ~13 ÷2/3 cells, and the lock-time spec must be relaxed
for that mode. Cleanest resolution: keep 32 kHz explicitly out of scope, or
scope it as a separate low-N configuration with its own spec row.

**2. 400 MHz stretch ceiling.** Quantitatively this is *not* a delay-cell
crisis: 400 MHz from a 5-stage ring needs 250 ps per stage, which 3.3 V
gf180mcu devices can deliver. What it does change:

- Tuning range goes 20:1 → **40:1**, consuming ~6 of the 8 coarse bands. This
  is precisely why Decision 2 specifies a **3-bit** band code rather than
  2-bit — the stretch ceiling is already budgeted for, and this is the cheapest
  place to buy that option.
- The first ÷2/3 cell must toggle at 400 MHz (2.5 ns) at the slow corner. If
  the static-CMOS cell does not close there, the swappable-first-cell fallback
  in Decision 3 applies.
- If 400 MHz becomes a hard v1 *target* rather than a stretch, the
  pseudo-differential delay cell (rejected above as the closest call) becomes
  the better choice, because even stage counts and a 4-stage ring give more
  margin than dropping to a 3-stage single-ended ring. **That is the one
  condition that flips Decision 2.**

Per the issue's own framing: design margin should be budgeted to the 200 MHz
target, with the band plan (not the cell topology) carrying the stretch.

**3. 1.8 V core variant.** Decision 2's V→I converter and Decision 1's passive
filter both assume a comfortable Vctrl range (≈0.9–2.4 V of a 3.3 V rail). At
1.8 V, a threshold plus degeneration drop eats a third of the rail, the usable
Vctrl range collapses, and to keep the same tuning range Kvco must rise —
which drives C1 up quadratically in Decision 1's sizing. **If the 1.8 V
variant is ratified into v1**, expect: supply-regulated ring (the rejected
Decision 2 alternative) or a charge pump with level-shifted output, plus
possibly an active filter. Recommendation for #1: keep 1.8 V formally
deferred; it is a different block, not a variant.

**4. Device flavor (3.3 V thick-oxide vs. dual).** This record assumes
`nfet_03v3` / `pfet_03v3` throughout, including the divider. If #7 ratifies a
dual-flavor design, the divider is the block that would move (potentially
enabling the 5 V standard-cell libraries), which would reopen Decision 3's
custom-cell-count argument — the argument, not necessarily the conclusion.

**5. Lock detector in v1 scope.** Decision 2 deliberately leaves band select
as a static input with no calibration FSM. A lock detector is the natural
trigger for automatic band search; if #7 puts one in v1, expect a follow-on
record adding a band-search FSM, which changes the VCO control interface (and
adds a digital block with the same no-3.3 V-library problem noted above).

**6. Which jitter number is simulation-substantiable.** This shaped Decision 1
directly: sub-sampling and injection-locked architectures were dispositioned
partly because their advantage is *phase noise*, and in ngspice a free-running
oscillator's phase noise is not an AC `.noise` result — it needs transient
noise plus long runs, or ISF-based post-processing. The chosen architecture's
jitter is dominated by the VCO and is attributable by a VCO-only transient-noise
testbench plus a jitter-transfer argument, which is a tractable evidence path
under CLAUDE.md's "no claim without a testbench" rule. Recommendation for #1:
ratify **period jitter** (which is directly measurable from a transient run)
as the spec'd quantity, and treat any phase-noise/integrated-jitter figure as
derived, not spec'd, until the flow demonstrably produces it.

---

## Prior art on open PDKs

Links only. Nothing from this repository — spec values, results, design
detail — appears in, or has been contributed to, any of these public trackers
(CLAUDE.md, Tier 2 confidentiality). These are citations, one-directional.

- **`ejfogleman/sky130_ejf_ip__pll_dev`** —
  https://github.com/ejfogleman/sky130_ejf_ip__pll_dev — the closest and most
  useful prior art: a full charge-pump PLL clock multiplier on sky130, built
  in **xschem** with ngspice testbenches, Apache-2.0. Structure to note: a
  4-stage pseudo-differential ring off a regulated supply node with a level
  shifter to CMOS; a pulse-swallow feedback divider assembled from ÷2/3 cells;
  a per-block file organization (`*_vco`, `*_chp`, `*_pfd`, `*_lpf`, `*_div*`
  each as its own `.sch`/`.sym`) with a matching `tb_*` per block plus a top
  testbench; and three separate supply domains for reference, VCO and divider.
- **`efabless/caravel`** — https://github.com/efabless/caravel — the management
  SoC's ring-oscillator clock multiplier with a digital control loop
  (`verilog/rtl/digital_pll.v`, `digital_pll_controller.v`, `ring_osc2x13.v`,
  sky130). Cited as the existence proof for the all-digital option that
  Decision 1 rejects, and as the reason that rejection is on flow/verification
  grounds rather than feasibility grounds.
- **`idea-fasoc/OpenFASOC`** — https://github.com/idea-fasoc/OpenFASOC —
  generator-based open analog flow; the `temp-sense-gen` generator is
  ring-oscillator-based and the project targets both sky130 and gf180mcu.
  Cited as evidence that ring oscillators on gf180mcu are a trodden path in
  open flows, and as a reference for corner/model-file organization.
- **`google/gf180mcu-pdk`** — https://github.com/google/gf180mcu-pdk — the PDK.
- **`efabless/globalfoundries-pdk-libs-gf180mcu_fd_pr`** —
  https://github.com/efabless/globalfoundries-pdk-libs-gf180mcu_fd_pr — the
  primitive device library and xschem symbols; source of the device names used
  in this record.
- **`google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0`** and
  **`…_mcu9t5v0`** —
  https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0 ,
  https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu9t5v0 —
  the open standard-cell libraries for this node; both 5 V-flavor, which is the
  basis for the "no matching 3.3 V digital library" argument in Decision 3.
  Confirm the characterized corner set against the installed PDK before relying
  on this.
- **`StefanSchippers/xschem`** — https://github.com/StefanSchippers/xschem —
  the schematic entry tool this repo's flow is built on.
- **`iic-jku/IIC-OSIC-TOOLS`** — https://github.com/iic-jku/IIC-OSIC-TOOLS —
  packaged sky130/gf180 analog design environment; useful as a reference for a
  known-good tool/PDK version combination.
- **`google/skywater-pdk`** — https://github.com/google/skywater-pdk — context
  for the sky130 prior art above; not a target node here.

### What transfers to xschem + ngspice, concretely

1. **Adopt the per-block `.sch`/`.sym` + `tb_<block>` file organization** from
   the sky130 PLL for `design/` and `sim/`. It matches the block decomposition
   in #8/#9/#11 one-to-one and makes each block's evidence independently
   re-runnable — which is what CLAUDE.md's append-only `sim/` evidence rule
   needs.
2. **Adopt the split supply domains** (`vdd_ref`, `vdd_vco`, `vdd_div`) as a
   pin-list decision now, before schematics. Decisions 2 and 3 both depend on
   it, and retrofitting a domain split after layout is expensive.
3. **Do not adopt the programmable filter/CP-trim pin set.** It exists in the
   prior art to compensate a `Kvco/N` swing our architecture does not have
   (§Decision 1). We keep only a 2-bit Icp trim.
4. **Do not adopt its VCO topology.** Its regulated pseudo-differential ring
   is the right answer for a ±10% tuning range and the wrong answer for 20:1.
   This is the clearest illustration of why prior art must be dispositioned
   against *our* spec lines rather than copied.
5. **Heed its jitter row.** That spec table lists jitter figures annotated
   "Not simulated." Our jitter line must not end up in the same state — which
   is exactly the #7 question about what is simulation-substantiable.

---

## Consequences (whole-architecture)

**What this makes possible**

- #8, #9 and #11 can start immediately, each against a fixed interface: #9 gets
  a fixed passive filter topology with Icp and Kvco bounds; #8 gets a control
  scheme and the specific Kvco-vs-band-vs-corner extraction it must produce;
  #11 gets one cell to design plus a retiming contract.
- A single fixed loop filter spans the whole ratified operating space, so
  there is one loop-dynamics story to verify rather than one per configuration.
- The divider is one custom cell replicated — the cheapest verification path
  available at a node with no matching 3.3 V standard-cell library.

**What this makes harder / what we are accepting**

- **Supply-noise-induced jitter is the top technical risk**, by construction:
  we chose the delay cell with the weakest supply rejection because it was the
  only one that spans 20:1. If #8's supply-noise testbench fails the 1% period
  jitter line, the mitigation ladder is in Decision 2 and the last rung is
  superseding this record.
- **The block requires correct static configuration** (band code + N code) to
  lock. There is no self-calibration in v1. That is a datasheet/integration
  burden pushed onto the user of the block.
- **The 20 µs lock-time stretch is not met at the low end of the reference
  range** with a single fixed filter (sanity check above). Meeting it would
  need a bandwidth-boost-during-acquisition scheme, which needs a lock
  detector — i.e. it is coupled to #7 item 5.
- **The 32 kHz reference mode is architecturally out of reach** for this
  design by roughly 6× on area alone. This record's recommendation to #1 is to
  descope it rather than carry it as a stretch goal it cannot reach.

**What must be re-derived before any of this enters the ratified spec**

Every number in this record is a hand calculation used to *disposition
options*. The Kvco bound, Icp range, C1 value, band count and band overlap all
become real only when #8/#9/#11 produce extracted, corner-swept evidence. If
that evidence contradicts a sizing assumption here, the architecture decisions
may still stand — check which of them actually depended on the number before
superseding.
