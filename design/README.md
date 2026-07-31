# `design/` — schematic capture

xschem schematics for the gf180-pll block, plus the export step that turns them
into the SPICE the `sim/` testbenches simulate. Layout is `layout/`, measured
silicon is `measurements/`, and every claim about any of these lives in `sim/`
under the append-only record format in `sim/README.md`.

```
design/
  xschemrc              project-local xschem config (symbol path, netlist dir)
  netlist.sh            regenerate design/netlist/*.spice from the schematics
  netlist/*.spice       committed exports (checked by `netlist.sh --check`)

  # VCO (#8, DR-001 Decision 2 / DR-003)
  vco.sch  / .sym       top-level VCO: bias + 5-stage ring + buffer + decap
  vco_bias.sch/.sym     constant-gm bias, V->I converter, band-select mirror
  vco_stage.sch/.sym    one current-starved inverter delay cell

  # Feedback divider + lock detector (#11, DR-001 Decision 3 / DR-002 Decision 4)
  divider_chain.sch/.sym  six ÷2/3 cells + termination + output mux + retiming
  div23_cell.sch/.sym     one Vaucher-style ÷2/3 cell
  lock_detector.sch/.sym  phase-error window comparator
  dff_tg_3v3.sch/.sym     transmission-gate master-slave D flip-flop
  inv_3v3, inv2x_3v3, nand2_3v3, nand3_3v3, nor2_3v3, xor2_3v3,
  tgate_3v3, schmitt_3v3, delaywin_3v3   3.3 V static-CMOS leaf cells
```

## Regenerating / checking the netlists

`design/netlist.sh` exports each top block, with its full hierarchy, to a
self-contained ngspice subcircuit under `design/netlist/`:

```bash
./design/netlist.sh          # rewrite design/netlist/*.spice
./design/netlist.sh --check  # regenerate to a temp dir and diff — fails if stale
```

One script covers every block — the VCO and the divider/lock-detector cells are
listed together in its `BLOCKS` array, so `--check` is a single gate over the
whole library. Run it after editing any `.sch`; the campaign runners in `sim/`
consume whatever is committed and never regenerate.

The exported `.spice` files are **committed**, so a testbench can be run (and a
`sim/` record reproduced) without a working xschem install, and so a diff of a
schematic change shows up as a diff of the netlist it produces. The committed
export is the artifact `sim/` consumes, and every evidence record freezes its own
copy under `sim/<slug>/netlist-snapshots/<record-id>.spice`.

The only post-processing `netlist.sh` applies is un-commenting the top-level
`.subckt`/`.ends` pair that xschem comments out for a top sheet, and dropping the
trailing `.end`; nothing else in the xschem output is altered, so each committed
file stays a faithful rendering of its schematic. `--check` compares byte for
byte with one exception: xschem stamps the absolute filesystem path of each
expanded `.sch`/`.sym` into a `**` comment, so those comment lines (and only
those) are rewritten to repo-relative form on both sides before diffing —
otherwise the check would call every clone but the one that generated the files
stale.

Never `.include` two of these files in the same deck — each carries its own copy
of the shared leaf cells, so including two would redefine them.

Set `GF180_PDK_ROOT` to point at a PDK root other than `~/.volare/gf180mcuD`;
`design/xschemrc` and `sim/lib/simenv.sh` read the same variable.

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

# The feedback divider and lock detector

Cells landed by #11 (feedback divider + lock detector, DR-001 Decision 3 and
DR-002 Decision 4).

## Leaf cells (3.3 V static CMOS)

Every device is `nfet_03v3` / `pfet_03v3` — 3.3 V thick-oxide only, per
DR-002 Decision 3. There is deliberately **no** 5 V or 1.8 V device anywhere
in this block. The two open standard-cell libraries for gf180mcu are 5 V
flavour, which is why these are hand-drawn rather than instantiated (DR-001
Decision 3's "custom-cell count" argument).

| Cell | Contents |
|---|---|
| `inv_3v3` | inverter, Wp/Wn = 2.5 µm / 1.0 µm, L = 0.28 µm — the unit gate |
| `inv2x_3v3` | 2× inverter, Wp/Wn = 5.0 µm / 2.0 µm — clock/output drive |
| `nand2_3v3`, `nand3_3v3`, `nor2_3v3` | ratioed to the unit inverter |
| `xor2_3v3` | four-NAND XOR |
| `tgate_3v3` | transmission gate, separate n- and p-gate pins |
| `schmitt_3v3` | six-transistor Schmitt inverter (hysteresis for the lock flag) |
| `delaywin_3v3` | four inverters loaded by MOS capacitors — the lock detector's comparator window |
| `dff_tg_3v3` | positive-edge-triggered **transmission-gate master-slave** D flip-flop |

`dff_tg_3v3` is the cell the whole divider is built from. Both latches use
clocked-feedback (a feedback transmission gate on the opposite clock phase),
so the flop is **fully static**: it holds state indefinitely with the clock
stopped. That is the property DR-001 Decision 3 chose static CMOS for over
TSPC / E-TSPC — dynamic logic has a *minimum* clock frequency, and this
divider has to keep dividing at the 10 MHz bottom of the band and slower
still during acquisition transients.

## Blocks

| Block | Role |
|---|---|
| `div23_cell` | one ÷2/3 cell (Vaucher-style), two `dff_tg_3v3` plus four gates |
| `divider_chain` | six identical `div23_cell` + chain-length termination + one-hot output mux + VCO-clocked retiming flop |
| `lock_detector` | phase-error window comparator producing the digital `lock` output |

### `div23_cell`

Two flops, both clocked on the rising edge of `CKIN`:

```
Q'      = /Q . /(MODIN . P . MODOUT)
MODOUT' = MODIN . Q
CKOUT   = Q
```

With `MODIN . P = 0` the cell divides by 2 (`Q` simply toggles). With
`MODIN = P = 1` the state `(Q, MODOUT)` walks `(0,0) → (1,0) → (0,1) → (0,0)`,
i.e. divide by 3, and `MODOUT` is high for exactly one `CKIN` period per
output cycle — which is what the preceding, twice-as-fast cell needs in order
to see it as one of *its* own output periods.

### `divider_chain`

```
N = 2^k + Σ p_i · 2^i   (i < k),   SEL_(k-1) = 1
```

`SEL` is a one-hot chain-length code. It does two things at once: it
terminates the modulus chain (`MODIN_i = MODOUT_(i+1) + SEL_i`, so the last
active cell sees `MODIN = 1` permanently) and it selects that same cell's
clock output through the one-hot output multiplexer. Six cells give
continuous integer N over 4–64 with no holes; coverage extends free to 127,
which is spare margin and **not** a spec claim (DR-001 Decision 3).

N is a **static configuration**, set alongside the VCO band code; the loop
re-locks after a change. Glitch-free on-the-fly modulus switching is
explicitly out of v1 scope.

The final flop is clocked by the **VCO**, not by the chain, so the feedback
edge the PFD sees is one flop's clk→Q after a VCO edge **independent of N** —
rather than the accumulated clk→Q of the `k` active cells, which varies with
the programmed chain length. That constant feedback delay is DR-001's
interface contract to #9. The price is a setup budget of one VCO period minus
the chain's accumulated clk→Q, closed at the slow corner in
`sim/divider-ratio/`.

The chain runs on its own supply domain `vdd_div`, consistent with the
VCO/reference domain split (DR-001 Decisions 2 and 3), so divider switching
noise does not land on the VCO supply.

`div23_cell` is instantiated six times unmodified. DR-001 Decision 3 asks for
the *first* cell to be separately swappable so a future 400 MHz stretch push
can replace one cell with a TSPC/E-TSPC version rather than redesigning the
chain; keeping the six instances identical and distinct (`XD0`…`XD5`) is what
makes that a one-symbol substitution.

### `lock_detector`

```
ERR  = XOR(UP, DN)        the PFD's common reset overlap cancels
ERRD = ERR delayed t_win
WIDE = ERR . ERRD         pulses only if |phase error| > t_win
VWIN                      weak always-on pull-up, WIDE-gated pull-down, MOS cap
LOCK = /schmitt(VWIN)
```

Assert is slow (the pull-up must charge the node, i.e. the error has to stay
inside the window for many reference cycles) and deassert is fast (one
out-of-window pulse dumps the node). A lock flag that is slow to rise and
quick to fall is the safe direction for a consumer gating logic on it.

It is a **passive monitor**: no counter, no state machine, nothing driving a
loop node. DR-001 Decision 2 keeps band select a static input with no
calibration FSM and DR-002 Decision 4 preserves that unchanged.

---

# Conventions

- One block per `.sch` + `.sym` pair, named for the block.
- Ports: inputs `ipin`, outputs `opin`, supplies `iopin`. Supplies are
  explicit pins on every cell — there are no global `VDD`/`VSS` nets, so a
  block can be placed on `vdd_div` without editing its children.
- Connectivity inside a schematic is by **net label** (`lab_pin`) rather than
  drawn wire. That keeps a schematic diffable as text and keeps the netlist
  the reviewable artifact; the trade-off is that the graphical rendering is
  sparse.
- Device geometry is written on the instance, not hidden in a model card, so
  a sizing change is visible in the diff.
