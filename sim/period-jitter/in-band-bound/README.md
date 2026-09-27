# `period-jitter` random component — the in-band generators, bounded over the 45-point grid

**This directory puts an upper bound on the random (noise-driven) period jitter
the charge pump, the PFD, the feedback divider and the lock detector contribute
to the locked output, at every point of the mandated PVT grid.** Those four are
the generators [`../random-bound/`](../random-bound/) (issue
[#520](https://github.com/2AMLogic/gf180-pll/issues/520),
[DR-032](../../../spec/decision-records/DR-032-random-period-jitter-bounded-over-the-grid.md))
states as outside its own scope, and which its README hands to
[#580](https://github.com/2AMLogic/gf180-pll/issues/580) — where they were an
*argument* that they are small ("in-band, so the loop's low-pass transfer and
then the period difference's `(2πfT)²` weighting"), not a bound. This directory
turns that argument into inequalities and measures them. The decision record is
[`DR-033`](../../../spec/decision-records/DR-033-in-band-random-period-jitter-bounded-over-the-grid.md).

It is issue #580's option **(A)** — each source referred to the output through
the closed-loop transfer — and not option (B), a closed-loop `trnoise()`
transient. §[Why option (A)](#why-option-a) says why, in one paragraph, before
any result.

**Result: the four in-band blocks together contribute at most 0.0249 % RMS of
the output period at every one of the 45 mandated PVT points** (worst
`sf`/125 °C/2.97 V), against the **0.368 … 0.430 %** the VCO-side bound leaves
inside the 0.50 % RMS `spec/pll.md` allocates to the random component — a
headroom of **15.8× or better at every point**, and the whole random half
(DR-032's bound and this one, in quadrature) stays at **0.2559 … 0.3388 %**
against 0.50 %. It is an upper bound, not an estimate; see
[What this does NOT establish](#what-this-does-not-establish).

Run it:

```sh
sim/period-jitter/in-band-bound/grid.sh 6        # all 45 points, 6 side by side
sim/period-jitter/in-band-bound/run.py --point typical_27c_3.30v \
    --stage digital --stage cp --stage cells --stage clkload --stage ldload --stage bound
sim/period-jitter/in-band-bound/run.py --point typical_27c_3.30v --stage validate
sim/period-jitter/in-band-bound/summarize.py \
    > sim/period-jitter/in-band-bound/results/SUMMARY.md
```

Every number quoted below is in [`results/SUMMARY.md`](results/SUMMARY.md),
regenerated from [`results/*.json`](results/) by `summarize.py`.

- [Why option (A)](#why-option-a)
- [The idea](#the-idea)
- [Which stages are in a path, and which are not](#which-stages-are-in-a-path-and-which-are-not)
- [Method](#method)
- [What it found](#what-it-found)
- [What this does NOT establish](#what-this-does-not-establish)
- [Files](#files)

## Why option (A)

Issue #580 offered two routes. Option (B) — a closed-loop transient with
`trnoise()` in these four blocks — is not merely heavier here, it measures the
wrong thing with the wrong resolution. The quantity to be resolved is a period
deviation of order 10⁻⁴ of the period, produced by sources whose path to the
output is attenuated by ~10⁻² (the loop) times ~10⁻³ (the period difference).
A transient would have to separate a ~1 fs period perturbation from a solver
floor `../random-bound` measures in the tens of femtoseconds, on a deck ten
times the size of that campaign's VCO-only one. Option (A) has no such problem:
the attenuation that makes the answer small is applied analytically, over
**every** loop the as-built filter admits at once, and the only thing simulated
is each block's own noise at a fixed, measured operating point — where `.noise`
is exact and cheap.

## The idea

A bound is only as good as the inequalities under it, so they are stated before
anything is measured. Each is derived in the docstring of the function that
applies it in [`ib_extract.py`](ib_extract.py), and each has a test in
`sim/tests/test_in_band_bound.py`.

The four blocks are not bounded the way `../random-bound` bounds the ring,
because they do not act the way the ring does: **none of them moves the ring's
phase directly.** Every one of them acts on the output by changing *the charge
delivered to the loop filter in one reference cycle*, and that charge reaches the
output phase through the closed loop. Seven steps.

**1. Enumeration.** In the committed `design/netlist/pll_top.spice`, the four
blocks touch the rest of the PLL through exactly five nets: `VCTRL` (the charge
pump's output current), `UP`/`DN` (the PFD's outputs, which gate the charge
pump's switches and are the lock detector's only inputs), `FB` (the divider's
output, the PFD's second input) and `CLK` (the divider's *input*, which is also
the measured output). The first four act only by changing one reference cycle's
charge; `CLK` is the one path that does not pass through the loop and is bounded
separately. `connectivity_claim` checks this against the netlist, and
`unclassified_shared_nets` must be empty — a shared net that is neither one of
these five nor an inert supply/configuration net would be a path nobody
considered.

**2. Charge → input-referred phase.** In lock the PFD/charge-pump pair delivers
`I_cp T_ref / 2π` coulombs per radian of input phase error, so a charge error
`dq` in one cycle is indistinguishable from an input phase error
`dφ = 2π dq/(I_cp T_ref)`; a displacement `dt` of a switch edge is `dq = I_cp dt`,
i.e. `dφ = 2π dt/T_ref` with `I_cp` cancelled. That is why the charge pump's own
current noise is measured in coulombs and the other three in seconds, and why the
three timing blocks' contributions do not depend on the charge-pump trim code at
all.

**3. Input phase → output phase, in lock.** `S_φ,out = N² |G|² S_φ,in` with
`G = T/(1+T)`, taken as the upper envelope over every loop `admissible_loops`
admits at the ratified 45° phase-margin floor — the same 1606 loops
`../random-bound` envelopes, read from its own `results/loop.json` so the two
bounds cannot disagree about the loop set. Note this is the **complementary**
transfer to that campaign's: it envelopes `|1/(1+T)|²`, what the VCO's own noise
sees; an input-referred source sees `|T/(1+T)|²`, which the same loop *passes*
where it *suppresses* the other. That is why these four blocks need their own
calculation and not a reuse of #520's number.

**4. Output phase → period.** One period is the first difference of output
phase, so `var(δT/T₀) = (1/4π²) ∫ S_φ,out(f) · 4 sin²(π f T₀) df`. That weight is
`≈ (2π f T₀)²` in band — 3.44 × 10⁻³ at 1.4 MHz against a 150 MHz output — and it
is the whole reason these four blocks are small. **It is applied as an integral,
never as that one number**: the peak of the product `|T/(1+T)|² · 4 sin²(π f T₀)`
over the whole admissible-loop envelope is 6.75 × 10⁻³, and that is reported
rather than used.

**5. Sampling.** Every quantity in step 2 is a once-per-reference-cycle
sequence, so its spectrum lives on `0 … f_ref/2` and whatever the underlying
continuous-time noise has above `f_ref/2` folds into that band. `fold_to_nyquist`
splits a measured density there: the in-band part keeps its shape (a slow,
flicker component tracks from one cycle to the next, and the frequency-dependent
weight of step 4 is what makes it harmless), the part above is re-emitted as the
flat density `2σ²/f_ref` an independent-per-cycle sequence of the same variance
has. Total variance is preserved; `f_ref/2` does not fall on a grid point, and
the straddling interval is counted in **both** halves rather than in neither, so
the fold can over-state by one interval and never drop a sliver.

**6. Cyclostationary → the worst instant.** Two places, both one-sided.

*(a) The charge pump conducts only for the reset window.* This is the adaptation
#580 asked to see stated rather than assumed away. `../random-bound` injects
generators live at every instant of every cycle; the charge pump's are not. Both
switches conduct only for the overlap of the `UP` and `DN` pulses — 1.26 … 2.86 ns
measured, out of a 40 ns reference period — and what one reference cycle sees is
a *windowed* integral `dq_k = ∫_window i_n(t) dt`, so a density `S_i` contributes
`var(dq) = ∫ S_i(f) t_on² sinc²(f t_on) df`. For white `S_i` that is exactly
`S_i t_on/2`: the duty-cycle factor `t_on f_ref` below what a continuously
conducting source of the same density would deliver — 3.15 … 7.16 % here. That
factor is the sentence the bound is allowed to use *only because it states it*,
and `sim/tests/test_in_band_bound.py` pins it against the closed form. Two
one-sided choices go with it: `S_i` is measured with both switches **fully on**,
which is at least the density at any instant of a window whose edges have
partially-on switches; and the off state, over the other ~95 % of the reference
period, is **measured too** rather than assumed negligible — it is not, because
the dump buffer's own devices sit on `VOUT`.

*(b) A logic stage's noise at its own output crossing.* A stage's output crosses
the next stage's threshold displaced by `−v_n/SR`. `v_n` is bounded by the
stage's **stationary** output-noise variance at its **trip point**, which covers
both regimes: if the node's time constant is longer than the transition the
noise has had less than that to accumulate and is below the stationary value; if
it is shorter the noise is stationary at the instantaneous bias, and a CMOS
stage's stationary variance goes as its small-signal gain, which is maximal at
the trip point. That last clause is **measured, not asserted**: `.noise` is run
at seven biases across each cell's transition and the trip point's dominance is
reported per cell, per point.

**7. Which stages are in a path at all** — the step that does most of the work,
below.

## Which stages are in a path, and which are not

A gate's noise displaces a charge-pump switch edge only if it sits between a
triggering input edge and that switch edge. A gate elsewhere in the block does
not displace it, and charging the block for it is not conservatism — it is a
different circuit. So the stages are **declared per path** in
`ib_extract.TIMING_PATHS` and **checked against the committed netlist** by
`timing_path_claim` at every point, rather than counted off a device list. A
renamed or retyped gate fails there rather than quietly dropping out of, or into,
a path.

| Path | Stages | What sets it |
|---|---|---|
| `pfd_ref_to_up` | 4 | `REF`↑ → `UP`↑: the edge detector's NAND and output inverter, the set inverter, the latch's own NAND. The detector's five-inverter chain sets how long the set *pulse lasts*, not when the latch is set, so it is not in this path |
| `pfd_fb_to_dn` | 4 | `FB`↑ → `DN`↑, the same four on the feedback side |
| `divider_retime` | 4 | `CLK`↑ → `FB`↑ through the retiming flip-flop only |
| `cp_switch_driver` | 1 | `UP` → `UPB` → the up switch's gate. `DN` drives the down switch's gate directly, so there is no second |
| `pfd_reset_common` | 27 | `UP`&`DN` → `RB`: the reset NAND, the first inverter, the 24-stage delay chain, the reset inverter. **Common mode**, see below |
| `pfd_reset_up_side` / `_dn_side` | 2 each | `RB` → that latch's own output. One output each, so not common mode |

Three consequences worth naming, because each is worth an order of magnitude or
more and each is checked rather than argued:

- **The divider chain's other 226 MOS devices set no edge time.** `XFRT` is a
  `dff_tg_3v3` with `D = DIVOUT`, `CK = CLK`, `Q = FB`, so `FB`'s edge sits where
  `CLK`'s edge plus that one flip-flop's clock-to-Q delay puts it. The six
  `div23_cell`s, the mode logic and the NAND/NOR decode decide only *whether* `FB`
  toggles on a given `CLK` edge, never when. (The assumption that makes this true
  is that `DIVOUT` settles before the `CLK` edge that samples it — a setup-time
  statement, not a noise one, and the deterministic campaign's own divider timing
  is where it is established, not here.)
- **The lock detector is in no path at all.** Its only inputs are `UP`/`DN` and
  its only output `LOCK` reaches no other `pll_top` instance — which
  `connectivity_claim` establishes from the netlist at every point, and which
  `sim/tests/test_in_band_bound.py` pins, because a re-netlist that ever consumed
  `LOCK` would make this treatment wrong *silently*. So it can act on the output
  only by **loading** `UP`/`DN`, which is measured as a gate load and not
  counted as a stage.
- **The PFD's reset path is common mode.** `RB` resets both latches, so a
  displacement of the reset edge lengthens the `UP` and the `DN` pulse by the
  same amount, and the *net* charge the filter receives — `I_up t_up − I_dn t_dn`
  — changes only through the leg **imbalance**. Its 27 stages are therefore
  scaled by `max(|I_up − I_dn|/min(I_up, I_dn), 10 %)`: the measured imbalance at
  that point and in the conducting state, floored at 10 % to cover the random
  mismatch a nominal-sizes measurement does not contain. Both numbers are
  recorded and the floor sets it at every point (the measured systematic
  imbalance is ≤ 0.7 %).

Stages within a path are independent generators and add **in quadrature**. The
perfectly-correlated (linear) figure is reported beside every path so the size of
that choice is visible, and so is the figure the retired
every-inverting-device-in-series count would have produced.

## Method

**The operating point** (stage `digital`). Each point of
`sim/period-jitter/testbench/tb.json`'s 45-point grid, read from that manifest
rather than retyped, at the point's own 150 MHz control voltage, band 6, `Icp`
trim code 0 — so this campaign, `../random-bound` and the deterministic half of
the row are all at the same 45 points. The DUT is the committed `pll_top` with
one substitution: `VCTRL` held at that corner's control voltage, so the reset
window, the switch timing and every edge slew are measured at a fixed, known
operating point and the loop's own response to them is applied afterwards,
analytically, over every admissible loop at once.

Two details of that deck are not cosmetic:

- **`VCTRL` is held through 1 Ω, not by a bare ideal source.** `loop_filter` puts
  `XCF5`, a 2 nF MIM capacitor, directly across `VCTRL`; a bare ideal source
  there leaves that capacitor's branch current determined by nothing but the
  source's own and the solver stalls on it reproducibly (`Timestep too small …
  trouble with node "vvc#branch"`, once the charge pump starts switching). One
  ohm makes it well-posed and leaves a residual `VCTRL` ripple of ~0.17 mV.
  `validate` re-runs at 100 Ω.
- **The deck is run twice, to put it in lock.** The conduction window this bound
  gates the charge pump's noise by is a property of the *locked* loop, and an
  open-loop deck leaves `REF` and `FB` at whatever relative phase the
  free-running ring produces. At an arbitrary phase the PFD asserts one output
  for the reset delay and the other for the reset delay **plus the phase error** —
  at the reference point, 1.70 ns and 21.18 ns respectively, the wrong window by
  12×. So pass 1 finds where `FB`'s edges fall and pass 2 moves `REF` onto them;
  with `VCTRL` held the ring does not care where `REF` sits, so the shift is
  exact to the residual reported per point (picoseconds), and a point whose
  residual exceeds 2 % of the reference period is refused rather than reported.

**The charge pump's output-current noise** (stage `cp`). The `cp` subcircuit
alone at this campaign's trim code, twice: both switches fully on (the overlap
state) and both off (the rest of the reference period), with the output held at
this corner's control voltage through a sense resistor. `.noise` once per
frequency over a 1 Hz band — so ngspice's integrated plot *is* the density — with
per-device contributions printed, 45 frequencies over 11 decades.

The sense resistor is not only the units anchor. ngspice reports its own thermal
contribution at the output as `√(4kT|Z|²/rsense)`, so dividing that by
`√(4kT·rsense)` measures `|Z(f)|/rsense` — the node's transimpedance — directly,
at every frequency. The short-circuit output current noise is recovered as
`S_v/|Z|²` with that measured `|Z|`, **not** as `S_v/rsense²`: `rsense` is the
node's impedance only below the corner it forms with everything else on `VOUT`
(four cascoded legs' drains, four dump-side switches, the dump buffer's input),
and at the grid top the measured ratio is ~0.013, so the naive reduction would
under-state the current noise by ~6000× there — the wrong direction for a bound.
`validate`'s 10×-`rsense` run is what shows the recovered `S_i` no longer depends
on `rsense` while the naive one does.

**The logic cells** (stage `cells`). Every **single-stage leaf** cell the three
digital blocks instantiate, standalone, at its trip point (found by tying input
to output, which for a single-path inverting gate *is* its switching threshold,
with no sweep and no interpolation), into a deliberately generous 50 fF load —
edge jitter grows as `√C_load`, so a load above anything the design's fan-out
presents makes the bound looser, never tighter. `.noise` for the output-noise
density, at seven input biases across the transition; then a transient driven by
the **slowest edge measured anywhere** in the PFD, the divider chain or the lock
detector, for the output slew that divides it.

*Single-stage* is load-bearing, not descriptive. The trip-point inequality of
step 6(b) is a statement about one gain stage. Self-biasing a multi-stage cell
finds the bias at which its whole **cascade's** gain is maximal, and the `.noise`
there is the cascade's — neither a bias the cell ever occupies nor a small-signal
regime. `xor2_3v3` (three `nand2_3v3` stages from A to Y) reports `σ_v = 0.87 V`
at 27 °C, against 4.1 mV for a single `pfdcp_inv_3v3`: 0.87 V is not a noise
voltage, it is a linearisation that has stopped being one. So the characterized
set is exactly the netlist's own single-stage subcircuits (`single_stage_cells`
derives it; the test pins `CELLS` against it), and every composite cell is
bounded as the composition of the single-stage cells along the path through it.

**The two gate-only loads** (stages `clkload`, `ldload`). `div23_cell`'s clock
input on `CLK`, and `lock_detector`'s `XERR` input on `UP`/`DN`. Neither has a
channel connected to the node it loads — `CKIN` goes only to the two
`dff_tg_3v3` clock inverters' gates — so both couple back through `C_gd` alone,
with the real driver absent and replaced by a source resistance (the VCO output
buffer's generators are `../random-bound`'s; `UP`'s driver is the PFD latch,
already a stage — counting either here would double-count).

That coupling is why these two are the one place a single "conservative"
parameter value would not have been conservative. The transfer from a load
device's noise to the node **rises** with frequency until the node's own
`R_drive·C_node` corner, so `σ_v² ∼ 1/R_drive` while the coupling is resistive
and saturates at the capacitive-divider ceiling once it is not: neither a large
nor a small `R_drive` is the safe side by inspection. Each is therefore
characterized at 100 Ω, 1 kΩ, 10 kΩ and 100 kΩ and the **maximum** is used, with
the whole sweep recorded. For the same reason these two decks alone run to
10¹⁴ Hz and extrapolate **no** tail: the density there is measured *flat* from
~10¹¹ to ~10¹³ Hz, and at the same level for every drive resistance in the
sweep, which is what a capacitive divider looks like and not an RC corner — there
is no measured `f⁻²` to extrapolate, so the integration stops at a stated band
and the per-decade cumulative is recorded so a reader can see exactly what that
choice is worth. (Both terms land five orders below the allocation, so it cannot
change the verdict.)

**Validation** (stage `validate`, reference point). The timestep ceiling at
2.5 ps instead of 25 ps; the `VCTRL` hold at 100 Ω instead of 1 Ω; the charge
pump's sense resistance at 10 kΩ instead of 1 kΩ, against both the transimpedance
reduction and the retired one; the trip point's dominance per cell; and every
netlist claim re-resolved — the unclassified-shared-net set, `LOCK`'s consumers,
each block's non-MOS leaf set, the declared timing paths, and that every
characterized cell is a single-stage leaf.

**The 2.5 ps timestep sub-check does not converge on this ngspice build.** At
every rung of the same `gmin`/initial-condition escalation ladder the
campaign's own 25 ps grid uses (which converges at all 45 mandated points),
the open-loop deck's first internal timepoint collapses on `xlf.xcf4`'s
moscap state node (`Timestep too small ... trouble with node
"e.xdut.xlf.xcf4.ec_moscap#branch"`, down to a 3 × 10⁻²⁴ s step) regardless of
`gmin`. This is recorded as `timestep.converged = false` rather than silently
retried or dropped, and `stage_validate` does not let it take the other three
checks — `VCTRL`-hold, sense-resistance and trip-point-dominance, all of which
converge normally — down with it. It is a limit of this one robustness
cross-check on the campaign's own 25 ps measurement, which the 45-point grid
itself does not share.

## What it found

Every figure here is in [`results/SUMMARY.md`](results/SUMMARY.md).

- **The in-band bound clears the margin DR-032 leaves, everywhere**:
  0.0193 … 0.0249 % RMS over the 45 points, worst `sf`/125 °C/2.97 V, against
  0.368 … 0.430 % remaining — a headroom of 15.8× at the tightest point
  (`sf`/125 °C/2.97 V) and 21.8× at the loosest. Combined with DR-032's own
  bound in quadrature, the whole random half is 0.2559 … 0.3388 % against the
  0.50 % allocation, which matches DR-032's own figure to three decimal places
  (0.2549 … 0.3381 % on its own): **this campaign adds nothing measurable to it.**
- **The charge pump's own output current sets it** — 0.0193 … 0.0248 % of the
  0.0193 … 0.0249 % total, i.e. essentially all of it, split roughly 4:3 between
  the conduction window and the off state. The three timing blocks together
  contribute ≤ 0.0025 %, and the lock detector ≤ 0.00006 %.
- **The duty cycle is what makes even that small**: the measured conduction
  window is 1.26 … 2.86 ns out of 40 ns, a duty of 3.15 … 7.16 %, and without
  that factor the charge-pump term would be ~3.7 … 5.6× larger in amplitude.
- **The three timing blocks are femtosecond-scale at the PFD's input.** The
  independent-per-cycle input-referred jitter that would, on its own, consume the
  whole remaining margin is 721 … 843 ps. Every stage's contribution is in the
  femtosecond decade.
- **The trip point is the worst bias, for every characterized cell but one.**
  `schmitt_3v3` peaks at −0.20 V of offset instead, by 2.24×; it appears in no
  timing path (it is the lock detector's output stage), so nothing in the bound
  rests on it, and it is reported rather than filed away.
- **The path derivation and the single-stage restriction together are worth
  4.1 … 9.9×.** The retired every-inverting-device-in-series count — every
  block's devices charged at its own worst *single-stage* cell (`pfdcp_inv_3v3`
  at every point) and put in one path, with no path derivation at all — gives
  0.080 … 0.245 % in total across the grid, against the 0.0193 … 0.0249 % this
  campaign's declared-path, single-stage accounting actually finds. `xor2_3v3`
  (three `nand2_3v3` stages, whose self-biased `.noise` is a cascade gain of
  0.87 V rather than a bound — see [Method](#method)) is excluded from even the
  retired count for the same reason it is excluded from the real one: it is not
  a single-stage cell, and charging its cascade figure as if it were would not
  be conservatism, it would be a different, wrong measurement.
- **Three toolchain facts, each of which produced a wrong answer first.**
  `setplot noise<2k>` after every `.noise` call is not optional: without it
  ngspice resolves the per-device vector in whichever plot it finds first and
  reprints the *first* call's density for every frequency. A 1 Hz band's two
  edges must be printed with enough significant digits to stay distinct — at 12
  digits they collapse past 10¹² Hz and ngspice does a single-frequency
  measurement that creates no integrated plot at all. And `.noise` needs its
  named input source to carry an `ac` value, or every call aborts with `ac input
  not found` and the per-device vectors come back zero-length.
- **A fourth, in this directory's own Python, also produced a wrong answer
  first.** `ib_extract.py` used to *prepend* `../random-bound` to `sys.path` to
  reach `rb_extract`. `random-bound` has its own `run.py`; a caller that does
  `import ib_extract` and then `import run` in the same process — exactly what
  `summarize.py` does — resolved *that* `run.py` instead of this directory's
  own, silently, because the prepended path shadowed the caller's own
  directory. It surfaced as an `AttributeError` on a name only this directory's
  `run.py` defines rather than as a wrong number, which is the only reason it
  was caught before a result was quoted from it. Fixed by appending, not
  prepending, so a caller's own directory (always inserted at `sys.path[0]`
  first) wins.

## What this does NOT establish

Each of these is a limit of the bound, stated so that nobody has to infer it.

- **It is an upper bound, not an estimate.** How far below it the true value sits
  is not measured here. Where the bound is loose is stated rather than hidden:
  every stage is charged its cell's trip-point noise into a 50 fF load at the
  slowest slew measured anywhere in the three blocks; the loop envelope is taken
  over every loop the as-built filter admits at the 45° floor, not the loop the
  trim rule selects; the reset path's common-mode scale is floored at 10 % when
  the measured imbalance is ≤ 0.7 %; and `xlat_*.xn1` is counted in both its
  side's rising and falling paths.
- **The `validate` stage's 2.5 ps timestep sub-check does not converge.** At
  the reference point, at every rung of the escalation ladder the campaign's
  own 25 ps grid uses. The other three `validate` sub-checks (`VCTRL`-hold
  resistance, charge-pump sense resistance, trip-point dominance) run and
  converge normally and are not affected. See [Method](#method)'s Validation
  paragraph.
- **Which generators it covers.** Every MOS channel (with its `rd`/`rs`/`rg`
  terminal generators) in `cp`, `pfd`, `divider_chain` and `lock_detector`; each
  block's non-MOS leaf set is asserted empty at every point, which is what makes
  the MOS enumeration complete. It does **not** cover the VCO, its bias
  generator, the output buffer or the loop-filter resistor — those are DR-032's,
  and this bound is quoted against the margin they leave. The reference source is
  excluded by `spec/pll.md` (DR-019). The `IBN`/`ICN`/`IBP`/`ICP` references are
  ideal current sources here at `iunit = 8 µA`, exactly as every other
  `sim/period-jitter`, `sim/reference-spur`, `sim/pll-top-smoke` and
  `sim/lock-time` deck drives them — the bias generator is a separate,
  not-yet-designed block (`design/README.md`), so **no noise from the current
  reference is in this bound**.
- **The timing paths are a first-order statement.** A gate outside a declared
  path displaces the switch edges only to second order (through its own loading
  of a node in a path, or through a setup-time margin it does not consume). The
  two loading paths that are *first*-order because they are the block's only path
  — the divider on `CLK`, the lock detector on `UP`/`DN` — are measured; the rest
  are not, and are dominated by those blocks' own in-path stage terms, which are
  counted.
- **The divider's retiming argument rests on setup time, not on noise.** If
  `DIVOUT` did not settle before the `CLK` edge that samples it, the combinational
  chain would enter `FB`'s edge timing and this bound would not cover it. That is
  the deterministic campaign's quantity.
- **Schematic level, ideal supply.** No layout parasitics; the supply and
  control sources are ideal. Supply-borne noise is the supply-ripple campaign's
  quantity, not this one's.
- **The PDK's noise models, as the PDK states them.** BSIM4 channel thermal and
  flicker, per device, from `.noise`. The gate-load terms integrate a density
  that is flat to ~10¹³ Hz, four decades above these devices' own transit
  frequency, where those models have no claim to validity — which is why that
  integration stops at a stated band and its per-decade cumulative is published
  rather than an extrapolation being invented.
- **One output frequency.** 150 MHz, band 6 — the same operating point as the
  deterministic half of the row, and not the 200 MHz band top, which is #503's
  campaign and is not covered here either.
- **Linear response.** `edge_jitter` is first order in `v_n`, which is
  microvolts to millivolts against volt-scale swings.

## Files

| File | What it is |
|---|---|
| [`ib_deck.py`](ib_deck.py) | Device and cell enumeration, and every deck — the open-loop `pll_top` transient, the charge pump's noise, the cells' trip point / noise / slew, the two gate loads — derived from the committed netlists |
| [`ib_extract.py`](ib_extract.py) | The inequalities, the declared timing paths and their netlist check, the loop transfer, the sampling fold, the gated charge spectrum and the assembled bound — no simulator |
| [`run.py`](run.py) | The eight stages; one point per invocation |
| [`grid.sh`](grid.sh) | The 45-point driver |
| [`summarize.py`](summarize.py) | `results/*.json` → [`results/SUMMARY.md`](results/SUMMARY.md) |
| [`results/`](results/) | The committed evidence |
| [`logs/`](logs/) | ngspice output for every deck, plus one driver log per grid point |
| `sim/tests/test_in_band_bound.py` | The enumeration, the declared paths, the single-stage restriction and every inequality's arithmetic, pinned off any simulator |
