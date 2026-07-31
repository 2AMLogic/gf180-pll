# `design/` — schematic capture

xschem schematics and symbols for the PLL's blocks, plus the export step that
turns them into the SPICE the `sim/` testbenches simulate.

```
design/
  xschemrc              project-local xschem config (symbol path, netlist dir)
  netlist.sh            batch netlist exporter — one script, one --top per block

  vco.sch  / .sym       top-level VCO: bias + 5-stage ring + buffer + decap
  vco_bias.sch / .sym   constant-gm bias, V->I converter, band-select mirror
  vco_stage.sch / .sym  one current-starved inverter delay cell
  netlist/vco.spice     committed VCO export (checked by `netlist.sh --check`)

  pfd_cp.sch / .sym     PFD + charge pump, the phase-detect front end
  pfd.sch / .sym        tri-state phase-frequency detector
  cp.sch / .sym         charge pump: 2-bit unit-element trim, cascode output
  cp_leg_n/_p.sch/.sym  one unit of sink / source current
  srlatch, edgedet,     custom logic cells the PFD is built from
    nand2_3v3, inv_3v3
  dut_export.sch        netlist-export root for pfd_cp; not part of the design
```

- **Device flavour**: gf180mcu 3.3 V thick-oxide only — `nfet_03v3` /
  `pfet_03v3` (plus `ppolyf_u_3k` and `cap_nmos_03v3` in the VCO), 3.3 V ±10 %
  supply (DR-002 Decision 3). No 5 V or 1.8 V devices, and no standard cells:
  the two open standard-cell libraries for this node are 5 V-flavour, so every
  logic gate here is a custom cell.
- **File organization**: one `.sch` + `.sym` pair per block, following the
  sky130 prior-art convention DR-001 recommends, so each block can be
  simulated and re-verified on its own.
- **PDK root**: set `GF180_PDK_ROOT` to point at a PDK root other than
  `~/.volare/gf180mcuD`; `xschemrc` and `sim/lib/simenv.sh` read the same
  variable.

## Netlist export

`netlist.sh` is the one exporter for everything in this directory. It takes an
explicit `--top`, because the two blocks captured here deliberately ship their
exports under **different conventions** and inferring which one was meant would
be exactly the kind of silent mistake this flow cannot afford:

```bash
./design/netlist.sh                        # rewrite design/netlist/vco.spice
./design/netlist.sh --check                # fail if that committed export is stale
./design/netlist.sh --top pfd_cp <outdir>  # write <outdir>/dut.spice (not committed)
```

| `--top` | Output | Committed? | `--check`? |
|---|---|---|---|
| `vco` (default) | `design/netlist/vco.spice` | yes | yes |
| `pfd_cp` | `<outdir>/dut.spice`, path echoed on stdout | no | n/a |

**Why two conventions, rather than one of them being wrong.** The VCO is a
single self-contained subcircuit whose export is small and stable, so
committing it makes the netlist reviewable in a diff and gives `--check`
something to check against; its post-processing is nothing but un-commenting
the top-level `.subckt`/`.ends` pair xschem comments out for a top sheet and
dropping the trailing `.end`, so the committed file stays a faithful rendering
of `vco.sch`. The PFD/CP is a nine-cell hierarchy re-exported per campaign, and
committing it would create a second source of truth beside the per-record
snapshot the evidence actually cites. Adding a third block means adding a case
to `netlist.sh`, not forking it.

**Either way the export the evidence cites is frozen.** Every record under
`sim/` copies the netlist it simulated to
`sim/<slug>/netlist-snapshots/<record-id>.spice` (see `sim/README.md`), so the
provenance of a result never depends on re-running the exporter.

Connectivity in these schematics is **label-driven**: each device terminal
carries a `lab_pin` symbol placed exactly on the terminal coordinate, rather
than a drawn wire. xschem resolves nets from those labels (this is how the
PDK's own test schematics are built). That makes a missing library path
dangerous — xschem would instantiate the unresolved label symbols as pin-less
placeholders, auto-name every net and report no error at all — so `netlist.sh`
self-checks **both** exports for the expected `.subckt` set, for auto-generated
`netN` names in a port list, and for unconnected pins, and fails loudly on any
of them. `design/xschemrc` documents the symbol-path union the two blocks need.

---

# The VCO (`vco.sch`)

Implements DR-001 Decision 2 with the band map refined by DR-003. Devices are
gf180mcu 3.3 V thick-oxide wrappers only — `nfet_03v3`, `pfet_03v3`,
`ppolyf_u_3k`, `cap_nmos_03v3` — per DR-002 Decision 3.

```
 VCTRL ─┐                                            VDD_VCO ──┬── 22 pF decap
        │  ┌──────────── vco_bias ─────────────┐               │
 B[2:0] ┼─►│ constant-gm core (beta-multiplier)│               │
        │  │ 2*Vgs offset reference            │  VBP ─────────┤
        └─►│ source-degenerated V->I           │  VBN ──────┐  │
           │ 3-bit geometric band mirror       │            │  │
           └───────────────────────────────────┘            │  │
                                                            ▼  ▼
   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐        (starving
   │ S1  ├──►│ S2  ├──►│ S3  ├──►│ S4  ├──►│ S5  ├──┐      devices in
   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘  │      every stage)
      ▲                                             │
      └─────────────────────────────────────────────┴──► x3 tapered buffer ──► CLK
```

## Delay cell (`vco_stage.sch`)

A minimum-length CMOS inverter (`W_p = 5 µm`, `W_n = 2 µm`, `L = 0.28 µm`)
bracketed by a **PMOS head** (`W = 10 µm`, `L = 0.5 µm`) and an **NMOS tail**
(`W = 4 µm`, `L = 0.5 µm`), both gated from the bias mirror. The head/tail pair
is *matched* — sized for equal charge and discharge current — so the ring's duty
cycle stays near 50 % across the band and the output buffer does not have to
recover it.

The starving devices are drawn at `L = 0.5 µm`, longer than the switching
devices, so their output resistance holds the mirrored current against the swing
on the internal `NH`/`NT` nodes. That is the difference between `f_osc ∝ I_ctrl`
(what DR-001 Decision 1's fixed loop filter depends on) and a ring whose current
sags with its own internal node voltages.

**Sizing provenance.** This cell is a 2x width scaling of the cell characterized
in `sim/devchar-delay/` (#4), which measured `W_p = 2.5 / W_n = 1 µm` switching
devices with a `5 / 2 µm` head/tail pair over the full 45-point PVT grid. Scaling
all four widths together leaves `f_osc(I_stage/W)` unchanged and doubles the
current at a given frequency; the doubling buys drive against the (not yet
extracted) routing capacitance the ring will see after layout, which is the
single parasitic most able to move this block's numbers. The #4 tables are the
reason the starving current range needed to reach 10–200 MHz was known before
the first ring sweep: 5 stages of that cell run at 47–91 MHz on 10 µA/stage
across the grid, so the 10–200 MHz band lands at roughly 1–30 µA/stage in the 1x
cell, i.e. 2–60 µA/stage here — a range a poly-degenerated V→I converter can
deliver from a 3.3 V rail without pushing any device out of saturation.

## Bias generator (`vco_bias.sch`)

Four sub-blocks, in signal order:

1. **Constant-gm core** — a beta-multiplier (`K = 4`, `R = ppolyf_u_3k`,
   `W/L = 1 µm / 5.6 µm` → ≈16.8 kΩ) with an explicit start-up branch. Its job
   is *not* to set the VCO current; it sets the `2·Vgs` reference stack that
   defines the V→I converter's offset, so the bottom of the Vctrl range does not
   move with the supply.
2. **`2·Vgs` offset reference** — a diode stack biased from the constant-gm core,
   generating `VFIX`.
3. **Source-degenerated V→I converter** — two `10 µm / 1 µm` NMOS branches, each
   degenerated by a 99 kΩ poly resistor (`ppolyf_u_3k`, `1 µm / 33 µm`), summed
   into a diode-connected PMOS at `VBP0`. One branch is gated by `VFIX` (the
   floor current, i.e. the frequency at `Vctrl = 0`), the other by `VCTRL`.
   Because both branches are degenerated, `∂I/∂Vctrl ≈ 1/R_deg` rather than
   `g_m`, which is exactly the property DR-001 chose this topology for: it keeps
   Kvco from exploding at the top of the control range the way a bare square-law
   V→I would.
4. **3-bit band-select mirror** — see below.

## Band map: a *geometric* mirror cascade, not binary-weighted legs

DR-001 Decision 2 sketched the coarse control as "a binary-weighted set of legs
in the bias mirror" producing "8 overlapping frequency bands, each covering
roughly 2:1 with ~20 % overlap". Those two sentences are not compatible: legs of
weight 1,2,4 summed with an always-on unit leg give band gains 1,2,3,…,8, so the
*adjacent-band* step falls from 2.00× (B0→B1) to 1.14× (B6→B7). With a ~2:1
fine range per band, the bottom of the code space has no overlap at all while the
top wastes 80 % of it.

This design therefore realizes the *requirement* (8 bands, ~2:1 each, uniform
overlap) with a **geometric** map, implemented as three cascaded current mirrors,
each with one always-on leg and one leg switched by a band bit:

| Cascade | Always-on leg | Switched leg | Gain when the bit is set |
|---|---|---|---|
| A (`B0`) | pfet 26.5 µm | pfet 17.225 µm | ×1.65 |
| B (`B1`) | nfet 5 µm | nfet 8.6125 µm | ×1.65² = ×2.7225 |
| C (`B2`) | pfet 12.3 µm | pfet 78.87 µm | ×1.65⁴ = ×7.4120 |

so `I_stage = I_sum · A0 · 1.65^code` with `A0 = (26.5/60)·(5/10)·(12.3/20) ≈
0.136` and `code = B2·4 + B1·2 + B0`. Every adjacent band step is the same
1.65×; with a measured ~2.2× fine range that is ~35 % overlap at every code, and
1.65⁷ ≈ 41.6× of coarse range on top of the fine range. The switch devices are
PMOS/NMOS pass gates that steer the switched leg's gate between the mirror node
and its own rail, so an unselected leg is fully off rather than weakly biased.

The band code is a **static configuration input** (DR-001: no auto-calibration
FSM in v1). It is set alongside the divider's N code.

Cascading mirrors rather than paralleling weighted legs also keeps the largest
device ratio in any single mirror to 6.4:1 instead of 41:1, which matters for
matching and for area.

## Output buffer and supply domain

The ring drives a three-stage tapered inverter buffer (×3 per stage,
1.25/0.5 → 3.75/1.5 → 11.25/4.5 µm). The first stage is deliberately small: a
starved ring's internal edges are slow at the bottom of the band, and a large
first inverter would burn crowbar current on every one of them and inject that
current back into the VCO rail. Every frequency in `sim/vco-tuning-range/` is
measured at the buffered `CLK` output, not at a ring node, because `CLK` is what
the divider (#11) and the closed-loop bench (#12) actually see.

`VDD_VCO`/`GND_VCO` are separate pins from the rest of the block per DR-001
Decision 2, carrying ≈22 pF of on-chip decoupling (two `cap_nmos_03v3`
50 × 50 µm devices). The decoupling is in the schematic, not deferred to layout,
because it is part of the DUT the supply-noise testbench measures — DR-001 names
supply noise this topology's top risk, and a jitter number taken without the
decap that will actually be there would not be the number the block ships with.

---

# The PFD and charge pump (`pfd_cp.sch`)

The DR-001 Decision 1 phase-detect front end: a tri-state PFD driving a
current-steering charge pump with a 2-bit unit-element Icp trim.

## Cells

| Cell | Purpose |
|---|---|
| `inv_3v3` | unit inverter, Wp/Wn = 1.5u/0.5u at L = 0.3u |
| `nand2_3v3` | unit 2-input NAND |
| `edgedet` | rising-edge pulse generator (AND of X and X delayed 5 stages) |
| `srlatch` | NAND SR latch, active-low set/reset |
| `pfd` | tri-state phase-frequency detector |
| `cp_leg_n` / `cp_leg_p` | one **unit** of charge-pump sink / source current |
| `cp` | charge pump: 2-bit unit-element Icp trim, wide-swing cascode output |
| `pfd_cp` | PFD + charge pump — the DR-001 Decision 1 phase-detect front end |
| `dut_export` | netlist-export root only; not part of the design hierarchy |

Every cell carries its own design note as an annotation inside the `.sch`
file. What follows is the block-level rationale and the numbers other issues
consume.

---

## PFD (`pfd.sch`)

Tri-state PFD: each input's rising edge fires an `edgedet` that SETs its own
`srlatch`; both latches share one RESET, generated as `AND(UP, DN)` through an
explicit **6-inverter delay chain**.

That delay chain is the dead-zone-elimination element. It guarantees UP and DN
both stay asserted for the reset-path delay even when REF and FB coincide
exactly, so the charge pump's switches are fully on at zero phase error and
the phase-to-charge transfer stays linear through zero.

Two ratios, not two absolute delays, keep this correct across PVT — both are
ratios of the same gate delays, so they track process and temperature:

1. **Edge-detector pulse > SR-latch loop delay.** A SET pulse released before
   QB has responded lets the latch fall back for one NAND delay and re-set,
   which appears as a narrow glitch splitting the UP pulse in two *right at
   zero phase error*. A 3-stage detector chain was measured doing exactly
   that on the UP branch (the branch loaded by the reset NAND's inner input);
   5 stages carries roughly 5× the latch loop delay and removes it.
2. **Edge-detector pulse < reset delay** (5 stages against ~9 gate delays),
   else set and reset would be asserted simultaneously.

**Interface contract to #11 (feedback divider).** DR-001 Decision 3 specifies
that FB is a VCO edge retimed by exactly one flop's clk→Q, independent of N,
shaped to be **at least as wide as this PFD's reset delay**. The measured
reset delay is the minimum UP/DN pulse width in the `pfd-deadzone` record —
that is the number #11 must size its retiming pulse against. This block does
not verify the contract from the divider side.

---

## Charge pump (`cp.sch`)

Wide-swing cascode sink and source, current-steering switches, 2-bit
unit-element Icp trim.

- **Unit-element trim.** `Icp = Iunit · (1 + B0 + 2·B1)` built from four
  identical unit legs per polarity (one always on, one gated by B0, two by
  B1), not from binary-weighted devices. Consequence: the per-leg overdrive,
  and therefore the saturation headroom, does not move with the trim code.
  This is the **only** loop-side programmability DR-001 permits — the
  band-switched current-starved VCO makes `Kvco/N` self-compensating, so the
  filter R and C stay fixed and there are no R/C trim banks (switches on the
  control node are a spur mechanism).
- **Wide-swing cascode**, chosen from `sim/devchar-cp`'s six-stack comparison
  (#4): about an order of magnitude more output resistance than a simple
  mirror at materially less headroom than a self-biased cascode, which is what
  lets the output stay in saturation across the whole ~0.9–2.4 V Vctrl window
  at the 2.97 V corner.
- **Sizing.** Unit mirror devices are `4u/1u` (N) and `12u/1u` (P) — a
  long-channel analog geometry for output resistance and matching, with the P
  device 3× wider so both polarities run at comparable overdrive at the same
  unit current. Wide-swing cascode bias diodes are at W/4.
- **Steering switches are sized for CHARGE, not on-resistance.** They pass a
  few microamps, so IR drop is irrelevant (tens of millivolts at worst).
  Equal N and P widths (3u/0.3u) — *not* mobility-ratioed widths — because
  unequal widths put unequal channel and overlap charge on the two polarities
  and inject a net residue onto the control node at every switching event.
  `MDUMN`/`MDUMP` are the standard half-width dummies gated by the
  complementary control. They are not shrunk further either: the switch must
  also re-establish its tail node at turn-on, and a 1u pair measurably lowered
  the detector gain by slowing that recovery.
- **Shared, clamped dump node.** Idle legs steer to `VDUMP`, held near
  mid-supply by two stacked NMOS diodes to VSS and two stacked PMOS diodes
  from VDD, sized narrow (1u/3u) so their turn-on thresholds leave a dead band
  and no static crowbar current flows. See "Charge-error mechanism" below for
  why this is not the obvious rail-dump design.
- **Bias generation is out of scope for this block.** `IBN`/`ICN`/`IBP`/`ICP`
  are the four reference nodes; the testbenches drive them from ideal 2 µA
  sources, as `sim/devchar-cp` does, so the measured mismatch is the output
  stage's own. The integrated block must supply four matched references from
  one constant-gm reference, and that contribution is additive to the budget
  below.

`Icp` lands in the **single-digit µA** range at every trim code, as DR-001's
sizing sanity check requires (the measured per-code range across corners is in
the `cp-compliance` record).

### Charge-error mechanism (why the dump node is shared and clamped)

At a few microamps and a sub-nanosecond minimum pulse, the *signal* charge per
pulse is only a few femtocoulombs. Anything that exchanges tens of
femtocoulombs with the control node once per reference cycle therefore
dominates it. The dominant such term is the **tail node**: when a steering
switch closes, the tail it was holding at its idle voltage is dragged to VOUT,
and that charge comes out of the control node.

Three designs were built and measured, in this order:

| Idle tail parked at | Measured net charge at zero phase error |
|---|---|
| each polarity's own rail (the obvious design) | ≈ −10 fC |
| shared unclamped dump node | ≈ −7 fC, and the node sat at 0.18 V |
| shared **clamped** dump node (current design) | ≈ −6 to −9 fC with a near-ideal detector gain |

The unclamped shared node fails for an instructive reason: with both legs idle
it carries only the *difference* of two nominally equal currents, so it is
degenerate and any mismatch walks it to whichever end saturates first. The
clamp removes the degeneracy without adding a control loop.

**What remains, and the honest limit.** A unity-gain buffer holding the dump
node exactly at VOUT would null this residue outright and is the textbook
answer; it is not in this revision because DR-001 keeps opamps out of the loop
path and because the buffer is a design and verification item of its own. The
residue that survives is *measured, not assumed*, at every corner, and is the
dominant term in the budget below. If #10's loop-filter and spur analysis
finds the static offset too expensive, the buffered dump node is the first
thing to add.

---

## Up/down mismatch budget

**This section is the budget #15's Monte Carlo campaign (`mc-cp-mismatch`)
checks statistical dispersion against.** It is a *stated budget*, not a
restatement of what one simulation happened to produce: the measured
systematic values are corner-swept worst cases, and the budget adds allocation
for the terms this block's own testbenches deliberately exclude.

| # | Term | Systematic (measured, all 45 PVT corners) | **Budget (3σ, including mismatch)** | Verified by |
|---|---|---|---|---|
| 1 | DC UP/DN current mismatch, `(Iup−Idn)/Iavg`, anywhere in 0.9–2.4 V | see `cp-compliance` record | **±10 %** | #15 |
| 2 | Effective UP/DN switching-time skew, `w_up − w_dn` | see `cp-compliance` record | **±3.5 ns** | #15 |
| 3 | Residual net charge per reference cycle at zero phase error | see `pfd-deadzone` record | **±15 fC** | #15 |
| 4 | Resulting static phase offset, `q_zero / Icp` | see `pfd-deadzone` record | **±3 ns** | #12 (closed loop) |

Notes on how to read this table:

- **Term 1 is dominated by finite output resistance**, and is measured at the
  *worst point inside the window*, not at mid-window: the two polarities' `ro`
  are not equal, so their curves diverge across the compliance range. The
  budget is set at ±10 % — several times the measured systematic value —
  because random `Vth`/`β` mismatch on the mirror devices is *not* in the
  measured number (`sw_stat_mismatch = 0`) and is the term #15 adds.
- **Terms 2 and 3 are the same physical effect** seen two ways: term 2 is
  measured per polarity from a clean control edge, term 3 is the net the loop
  sees per reference cycle with the real PFD driving. Term 3 is the one that
  matters for the loop; term 2 is what tells you *which* polarity is
  responsible.
- **Term 4 is a static offset, not a frequency error.** A charge-pump
  asymmetry does not shift the locked frequency; the loop simply settles at
  the phase where the net charge per cycle is zero. What it costs is control-
  node ripple (the equilibrium UP pulse is longer than the DN pulse by exactly
  this offset), which is a reference-spur mechanism — hence the budget rather
  than a shrug. At the bottom of the ratified 1–25 MHz reference range this is
  a fraction of a degree; at 25 MHz it is a significant fraction of a period,
  which is why the `pfd-deadzone` campaign runs at 25 MHz, the demanding end.
- **Bias-generator contribution is excluded** from both the measured column
  and, deliberately, from the budget: it is a separate block. When it lands,
  its mirror mismatch adds to term 1 and the budget must be re-derived rather
  than silently absorbed.
- **The budget is not a spec line.** No ratified spec parameter exists for
  charge-pump mismatch (#1 is open). If #15's statistics or #10's spur
  analysis show these values do not buy the spur/jitter performance the
  ratified spec asks for, the resolution is a decision record superseding this
  budget — not a quiet relaxation here.

---

## Regenerating and editing

The cells were emitted programmatically to keep placement and the label
convention uniform, but the committed `.sch`/`.sym` files are ordinary xschem
files: open, edit, and save them in xschem as normal. After any edit, re-run
the affected campaign under `sim/` — the testbenches include the *exported*
netlist, so a schematic change is picked up automatically and a new evidence
record is minted for it (records are append-only; the old one stands).
