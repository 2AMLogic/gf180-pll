# DR-033: The charge pump, PFD, divider and lock detector's random period jitter is bounded — ≤ 0.0249 % RMS at every one of the 45 mandated PVT points, at most 15.8× inside the margin DR-032 leaves

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-032 and its own predecessors record (a builder drafts the
  record on the evidence; the operator's PR approval is the ratifying act).
  Status stays `proposed` until that approval and merge.
- **Date**: 2026-09-27
- **Decided by**: Builder agent, issue #580
- **Relationship to earlier records**: **Completes the scope [DR-032](DR-032-random-period-jitter-bounded-over-the-grid.md)
  explicitly left open.** DR-032 bounds every generator inside `vco` (the ring,
  the bias generator, the output buffer) and the loop-filter resistor; its own
  §Decision 5 names the charge pump, the PFD, the feedback divider and the lock
  detector as in-band sources it does not inject, and hands bounding them to
  this issue. This record does not revise DR-032's number, its scope statement,
  or any of its inequalities — it adds an independent term and reports the sum.
  DR-002 Decision 5 ("a transient-noise testbench dominated by the VCO plus a
  jitter-transfer argument through the closed loop") is, for the first time,
  executed in full on **both** halves of that sentence: DR-032 is the
  transient, this record turns the jitter-transfer argument into a measured
  inequality rather than leaving it as prose. Neither DR-002, DR-020, DR-023
  nor DR-032 is edited.

## Context

`spec/pll.md`'s [Period jitter](../pll.md#period-jitter) row's supply-ripple
derivation leaves 0.50 % RMS of the ≤ 1.0 % target for the random component.
DR-032 spends 0.255 … 0.338 % RMS of that budget on the VCO's own generators
and the loop-filter resistor, leaving a margin of **0.368 … 0.430 % RMS**
across the 45 mandated PVT points (`sqrt(0.50² − vco²)`) — the number this
record's bound is compared against, not the full 0.50 % allocation.

The charge pump, the PFD, the feedback divider and the lock detector reach the
output only through the closed loop's low-pass transfer (≤ 1.4 MHz over every
admissible loop, ~1 % of `f₀`), and period jitter — the first difference of
output phase — attenuates in-band phase by `4 sin²(π f T₀)` ≈ `(2πfT₀)²` ≈
3.4 × 10⁻³ at 1.4 MHz against a 150 MHz output. That is DR-032's own stated
reason these four are small; it was an argument, not a bound, and turning it
into one is this issue's whole content. The evidence is
`sim/period-jitter/in-band-bound/`; every figure below is regenerated from its
committed `results/*.json` into `results/SUMMARY.md` by `summarize.py`.

## Decision

**1. The four in-band blocks' random period jitter is bounded at every
mandated PVT point, and it clears the margin DR-032 leaves at every one.**
Worst point `sf_125c_2.97v`, **0.0249 % RMS**, against a remaining margin of
0.394 % — a headroom of **15.8×**; range 0.0193 … 0.0249 % RMS over the 45
points, headroom 15.8 … 21.8×. It is an **upper bound**: within Decision 6's
scope, the random period jitter these four blocks contribute is at most this;
how far below it the true value sits is not measured. Combined with DR-032's
own bound in quadrature (the two are independent sources), the whole random
half of the row is **0.2559 … 0.3388 % RMS** against the 0.50 % allocation —
DR-032's own figure to three decimal places (0.2549 … 0.3381 % on its own):
**this record adds nothing measurable to the row's pass/fail.**

**2. The bound is option (A) — a loop-referred bound, not option (B), a
closed-loop transient — because the quantity is too small for a transient to
resolve.** The period deviation these four blocks produce is of order 10⁻⁴ of
the period, reached through a chain attenuated by ~10⁻² (the loop) times ~10⁻³
(the period-difference weighting). A `trnoise()` transient would have to
separate a roughly one-femtosecond period perturbation from a solver floor
DR-032's own transient measures in the tens of femtoseconds, on a deck an
order of magnitude larger than that campaign's VCO-only one. Option (A) has no
such problem: the attenuation that makes the answer small is applied
analytically, over **every** admissible loop at once, and the only thing
simulated is each block's own noise at a fixed, measured operating point,
where `.noise` is exact and cheap.

**3. Seven inequalities, stated before anything was measured, in
`ib_extract.py`'s module docstring and pinned by `sim/tests/test_in_band_bound.py`.**

- *Enumeration.* The four blocks touch the rest of `pll_top` through exactly
  five nets — `VCTRL`, `UP`, `DN`, `FB`, `CLK` — checked against the committed
  netlist (`connectivity_claim`) rather than asserted; `CLK` is the one net
  that does not pass through the loop (it is the divider's input and the
  measured output at once) and is bounded separately.
- *Charge → input-referred phase, then output phase.* `I_cp T_ref / 2π`
  coulombs per radian in lock, so a timing displacement `dt` of a charge-pump
  switch edge is an input phase error `dφ = 2π dt / T_ref` with `I_cp`
  cancelled — the PFD's, the divider's and the lock detector's contributions
  do not depend on the charge-pump trim code at all. `S_φ,out = N² |G|² S_φ,in`
  with `G = T/(1+T)`, taken as the upper envelope over the same 1606 admissible
  loops DR-032 envelopes (`../random-bound/results/loop.json`), so the two
  bounds cannot disagree about the loop set — but the **complementary**
  transfer to DR-032's: `|T/(1+T)|²`, not `|1/(1+T)|²`, because an
  input-referred source sees what DR-032's VCO-side source does not.
- *Output phase → period, exactly, not by the in-band approximation.* One
  period is the first difference of phase, weighted by `4 sin²(π f T₀)`, and
  that exact weight is integrated at every point — never replaced by the
  `(2πfT₀)²` limit that motivates the whole record.
- *Sampling.* Every one of these quantities is a once-per-reference-cycle
  sequence; `fold_to_nyquist` splits a measured density at `f_ref/2`, keeping
  the in-band shape below it and re-emitting an independent-per-cycle flat
  density above it, with the straddling grid interval counted in both halves
  rather than dropped.
- *The charge pump's pulsed duty cycle* — the adaptation the issue asked to
  see stated, not assumed away. `../random-bound` injects generators live at
  every instant; the charge pump's switches conduct only for the measured
  reset-window overlap (1.26 … 2.86 ns of a 40 ns reference period, a duty of
  3.15 … 7.16 %), so what one cycle sees is a windowed integral
  `dq_k = ∫_window i_n(t) dt`, and for white `S_i` that is exactly `S_i t_on/2`
  — the duty-cycle factor below a continuously-conducting source of the same
  density. `S_i` is measured with both switches fully on (at least the density
  any instant of the window has) and the off state, over the rest of the
  cycle, is measured too rather than assumed negligible.
- *A logic stage's edge.* `σ_t = σ_v / SR`, with `σ_v` the stage's stationary
  output-noise variance at its trip point — the worst bias for every
  characterized cell but one (`schmitt_3v3`, which is in no timing path), which
  is measured across seven biases per cell rather than asserted.
- *Which stages are in a path at all.* A gate's noise displaces a charge-pump
  switch edge only if it sits between a triggering input edge and that switch
  edge; `TIMING_PATHS` declares those gates per path and `timing_path_claim`
  checks every entry against the committed netlist. The divider chain's other
  226 MOS devices set no edge time (its output is retimed on `CLK` through one
  flip-flop); the lock detector is in no path at all (`LOCK` reaches no other
  `pll_top` instance) and acts only by loading `UP`/`DN`; the PFD's reset path
  is common mode between `UP` and `DN` and is scaled by the measured up/down
  current imbalance, floored at 10 % to cover random mismatch a nominal-sizes
  measurement does not contain.

**4. What sets the bound, and by how much.** The charge pump's own output
current noise is essentially all of it — 0.0193 … 0.0248 % of the
0.0193 … 0.0249 % total, split roughly 4:3 between the conduction window and
the off state. The three timing blocks together contribute ≤ 0.0025 %, and the
lock detector ≤ 0.00006 %; the independent-per-cycle input-referred jitter that
would, on its own, consume the whole remaining margin is 721 … 843 ps, against
every stage's actual contribution in the femtosecond decade. The declared-path,
single-stage accounting is worth 4.1 … 9.9× against the retired
every-device-in-series count (every block's devices charged at its own worst
single-stage cell, `pfdcp_inv_3v3`, in one path): 0.080 … 0.245 % in total,
against 0.0193 … 0.0249 % actually found.

**5. The measurement is validated as a measurement, with one sub-check that
does not converge on this build.** At the reference point: the `VCTRL`-hold
resistance at 100× (conduction window, every slew rate and frequency ratios
within 1.4 % of unity); the charge pump's sense resistance at 10× (the
recovered short-circuit current noise ratio 0.9999 … 1.0000, against the
retired `S_v/rsense²` reduction's 0.0100 … 0.9998 — i.e. the retired reduction
*does* depend on `rsense`, which is why it is retired); the trip point's
dominance, measured per cell; and every netlist claim re-resolved (the
unclassified-shared-net set is empty, `LOCK` reaches only its own instance,
every block's non-MOS leaf set is empty, every characterized cell is a
single-stage leaf). **The 2.5 ps timestep sub-check does not converge**: at
every rung of the same escalation ladder the campaign's own 25 ps grid uses
(which converges at all 45 mandated points), the open-loop deck's first
internal timepoint collapses on the loop filter's moscap state node
regardless of `gmin`. This is recorded (`timestep.converged = false`) rather
than silently retried or dropped, and does not affect the other three
sub-checks or the 45-point grid itself, which runs at the coarser (25 ps)
step throughout. `sim/period-jitter/in-band-bound/README.md`'s Method section
states this as a limit of one robustness cross-check, not of the bound.

**6. The scope is stated, not implied.** Covered: every MOS channel (with its
`rd`/`rs`/`rg` terminal generators) in `cp`, `pfd`, `divider_chain` and
`lock_detector`; each block's non-MOS leaf set is asserted empty at every
point, which is what makes the MOS enumeration complete. **Not covered**: the
VCO, its bias generator, the output buffer and the loop-filter resistor
(DR-032's); the reference source (excluded by `spec/pll.md`, DR-019); layout
parasitics and supply-borne noise (schematic level, ideal supply); the
200 MHz band top (#503's campaign, neither half measured there); the
current-reference block itself, which is a separate, not-yet-designed block
(`design/README.md`) driven by ideal current sources here, exactly as every
other `sim/period-jitter` deck drives it.

**7. What `spec/pll.md` now says.** The Period jitter row's random component,
already **bounded ≤ 0.338 % RMS at 45/45 points** by DR-032 with its in-band
scope named as owed at #580, now has that scope closed: **bounded
≤ 0.0249 % RMS at 45/45 points**, combined with DR-032's own bound
**≤ 0.3388 % RMS at 45/45 points**. The ≤ 1.0 % target does not move, and
neither does the 0.50 % allocation. `docs/chipalooza/challenge-5-proposal.md`
§5's random row, already MET as an upper bound with a scope note naming #580,
drops that scope note: the random half's bound now covers every generator this
design's schematic level admits, other than the reference source and the
not-yet-designed current reference.

## Alternatives considered

- **Build a closed-loop `trnoise()` transient instead (option B).** Rejected
  for the reason Decision 2 gives: the quantity is too small, relative to the
  transient's own solver floor, for a transient to resolve without measuring
  the wrong thing. Reusing DR-032's own transient's period-sequence floor
  (tens of femtoseconds) against this record's ~1 fs-scale in-band
  contribution is the same comparison DR-032's own README makes for why its
  transient is not the tool to extend.
- **Refer the reset path's common-mode scale to the measured systematic
  imbalance alone (≤ 0.7 %).** Rejected: DR-018's random-mismatch scope is not
  this record's, and a nominal-sizes measurement of a differential pair's
  legs does not contain the random mismatch a fabricated part has. The 10 %
  floor is set well above any plausible mismatch on this switch pair and its
  cascoded leg and is checked, not assumed, at every point.
- **Charge every block's devices in one path, as the retired
  every-device-in-series count does.** Rejected as the wrong circuit, not
  merely conservative: a gate whose output does not sit between a triggering
  input edge and a charge-pump switch edge does not displace that edge, and
  `TIMING_PATHS`'s declared-path, single-stage accounting is checked against
  the netlist (`timing_path_claim`) rather than counted off a device list.
  Reported anyway, at 4.1 … 9.9× the real figure, so the size of that choice
  is visible.
- **Assume the fine-timestep sub-check's non-convergence away, or retry it
  silently until it happens to pass.** Rejected. `stage_validate` records
  `timestep.converged = false` with the ngspice error that produced it, and
  the other three sub-checks — none of which depend on the fine timestep — are
  not gated by it. Silently dropping the whole `validate` stage on one
  sub-check's failure would have thrown away the sense-resistance and
  trip-point-dominance evidence for no reason connected to their own validity.

## Consequences

- `spec/pll.md`'s Period jitter section and Verification-owed table,
  `docs/chipalooza/challenge-5-proposal.md` §5, and `sim/CHARACTERIZATION.md`
  (if it names this scope) carry the combined bound and drop the scope note
  naming #580 as the owner of the remaining generator class. Issue #580 is
  closed by the pull request landing this record.
- `sim/period-jitter/in-band-bound/` is a method directory with committed
  evidence, the same standing as `../random-bound/`: no `records/` and no
  record id of its own, because it runs several decks per point with a
  reduction between them, outside `sim/harness`. Re-running it is `grid.sh`;
  everything it concludes is regenerated by `summarize.py`. Its `.work/`
  scratch tree (generated per-point decks and raw waveform data) is
  `.gitignore`d, matching how `../random-bound`'s own scratch is not
  committed; the driver logs (`logs/grid_<point>.txt`, one per point) and
  `results/*.json` are the committed evidence.
- The `sys.path` ordering bug this record's own verification pass found and
  fixed in `ib_extract.py` (prepending `../random-bound` to `sys.path` shadowed
  this directory's own `run.py` whenever a caller imported both, as
  `summarize.py` does) is fixed by appending instead of prepending. It is
  recorded in the directory README's toolchain-facts list rather than only in
  a commit message, since a future reader of `ib_extract.py` needs the same
  warning a future editor of it does.
- If a later design change moves the charge pump, the PFD, the divider chain
  or the lock detector — or DR-032's own VCO-side bound, which this record's
  margin is computed against — this bound must be re-run before the row may
  keep citing it; nothing here grades a changed netlist automatically.
