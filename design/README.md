# `design/` — schematic capture

xschem schematics and symbols for the PLL's blocks, plus the export step that
turns them into the SPICE the `sim/` testbenches simulate. Layout is `layout/`,
measured silicon is `measurements/`, and every claim about any of these lives in
`sim/` under the append-only record format in `sim/README.md`.

```
design/
  xschemrc              project-local xschem config (symbol path, netlist dir)
  netlist.sh            batch netlist exporter — every block, one script
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

  # PFD + charge pump (#9, DR-001 Decision 1)
  pfd_cp.sch / .sym     PFD + charge pump, the phase-detect front end
  pfd.sch / .sym        tri-state phase-frequency detector
  cp.sch / .sym         charge pump: 2-bit unit-element trim, cascode output
  cp_leg_n/_p.sch/.sym  one unit of sink / source current
  srlatch, edgedet      custom logic cells the PFD is built from
  dut_export.sch        netlist-export root for pfd_cp; not part of the design

  # Shared 3.3 V static-CMOS logic library (VCO / divider / lock detector)
  inv_3v3, inv2x_3v3, nand2_3v3, nand3_3v3, nor2_3v3, xor2_3v3,
  tgate_3v3, schmitt_3v3, delaywin_3v3

  # Leaf cells owned by the PFD/CP block (DR-004 — see Leaf-cell ownership and naming)
  pfdcp_inv_3v3, pfdcp_nand2_3v3
```

- **Device flavour**: gf180mcu 3.3 V thick-oxide only — `nfet_03v3` /
  `pfet_03v3` (plus `ppolyf_u_3k` and `cap_nmos_03v3` in the VCO), 3.3 V ±10 %
  supply (DR-002 Decision 3). No 5 V or 1.8 V devices, and no standard cells:
  the two open standard-cell libraries for this node are 5 V-flavour, so every
  logic gate here is a custom cell.
- **File organization**: one `.sch` + `.sym` pair per cell, following the
  sky130 prior-art convention DR-001 recommends, so each block can be
  simulated and re-verified on its own.
- **PDK root**: set `GF180_PDK_ROOT` to point at a PDK root other than
  `~/.volare/gf180mcuD`; `xschemrc` and `sim/lib/simenv.sh` read the same
  variable.

## Netlist export

`netlist.sh` is the one exporter for everything in this directory:

```bash
./design/netlist.sh                        # rewrite design/netlist/*.spice
./design/netlist.sh --check                # fail if any committed export is stale
./design/netlist.sh --top pfd_cp <outdir>  # write <outdir>/dut.spice (not committed)
./design/netlist.sh --check-paths          # assert the symbol path is unshadowed
```

The blocks captured here ship their exports under **two conventions**, and the
convention is a property of the block, not of the script:

| Top | Output | Committed? | `--check`? |
|---|---|---|---|
| `vco`, `div23_cell`, `divider_chain`, `lock_detector`, `dff_tg_3v3` | `design/netlist/<top>.spice` | yes | yes |
| `pfd_cp` | `<outdir>/dut.spice`, path echoed on stdout | no | n/a |

**Why two conventions, rather than one of them being wrong.** The committed
tops are self-contained subcircuits whose exports are small and stable, so
committing them makes the netlist reviewable in a diff, lets a testbench run
without a working xschem install, and gives `--check` something to check
against. The PFD/CP is a nine-cell hierarchy re-exported per campaign, and
committing it would create a second source of truth beside the per-record
snapshot the evidence actually cites. Adding a block means adding it to the
`BLOCKS` array (or adding a case), not forking the script.

**Either way the export the evidence cites is frozen.** Every record under
`sim/` copies the netlist it simulated to
`sim/<slug>/netlist-snapshots/<record-id>.spice` (see `sim/README.md`), so the
provenance of a result never depends on re-running the exporter.

The only post-processing applied is un-commenting the top-level
`.subckt`/`.ends` pair that xschem comments out for a top sheet, dropping the
trailing `.end` (and, for `pfd_cp`, stripping the export root's own body so the
file is `.include`-able), and rewriting the path comments described next.
Nothing else in the xschem output is altered — no device card, port list or
`.subckt`/`.ends` block is touched — so each file stays a faithful rendering of
its schematic.

**Absolute paths in the export (#28).** xschem stamps the absolute filesystem
path of each expanded `.sch`/`.sym` into a `**` comment (`** sch_path:
/abs/checkout/design/foo.sch`). Left alone, that path makes the export
machine-specific: a re-export from a different checkout would differ on those
lines alone even though nothing electrical changed, and a byte-exact snapshot
hash would only be reproducible in the checkout that minted it. `netlist.sh`
rewrites those comment lines, and only those, to repo-relative form **at write
time under both conventions** — the committed tops in `export_block`, the
per-record `pfd_cp` export in `netlist_pfd_cp`. So neither the committed bytes
under `design/netlist/` nor a `netlist-snapshots/<record-id>.spice` frozen from
a `pfd_cp` export ever embeds a machine-specific path, and both are
reproducible from any checkout.

`--check` runs the same rewrite again on both sides of its comparison. That
pass is a no-op on anything this script wrote; it is kept as defense in depth
against a committed file minted before write-time normalization existed.

Turning on write-time normalization for the committed tops rewrote their bytes
(comment lines only), which invalidates the netlist-snapshot SHA-256 that the
`vco-tuning-range`, `divider-ratio` and `lock-detector` records cite.
`sim/README.md`'s append-only rule therefore requires those campaigns to be
re-run and re-minted under new record IDs rather than edited in place; that
re-run is tracked in **#32**, and **#28** stays open until it lands.

Connectivity in these schematics is **label-driven**: each device terminal
carries a `lab_pin` symbol placed exactly on the terminal coordinate, rather
than a drawn wire. xschem resolves nets from those labels (this is how the
PDK's own test schematics are built). That makes a missing library path
dangerous — xschem would instantiate the unresolved label symbols as pin-less
placeholders, auto-name every net and report no error at all — so `netlist.sh`
self-checks **every** export for the expected `.subckt` set, for auto-generated
`netN` names in a port list, and for unconnected pins, and fails loudly on any
of them, before writing anything. `design/xschemrc` documents the symbol-path
union the blocks need, and `--check-paths` re-asserts at run time that the
union cannot shadow (no `.sym` sits directly in either parent directory).

Never `.include` two committed exports in the same deck — each carries its own
copy of the shared logic library, so including two would redefine them.

## Leaf-cell ownership and naming

`design/` is a **single flat namespace** — every block PR lands its schematics
into this one directory, with no directory-per-block split. That means two
independently-developed blocks landing their own copy of the same
static-CMOS leaf cell (`inv_3v3`, `nand2_3v3`, …) under the same filename is
an **add/add collision**, not a merge that resolves cleanly: whichever side a
human picks silently re-sizes the *other* block's already-characterized cell,
and the export still succeeds — nothing reports a problem. This has already
happened twice (issue #30).

**Convention: every leaf cell is namespaced by its owning block**, using the
pattern `<block-prefix>_<cellname>` — e.g. a PFD/CP-owned unit inverter would
be `pfdcp_inv_3v3`, a divider-owned one `div_inv_3v3`. A **bare** cell name
(no block prefix) is reserved for a cell that is a genuinely **shared,
canonical** definition instantiated by more than one block; whether a given
cell is "shared" or "per-block" is a decision recorded the same way any other
spec choice is (a `spec/decision-records/` decision record), not something an
implementer decides silently by reusing a bare filename. This is checkable by
a human reviewer with no tooling at all: `ls design/*.sch design/*.sym` and
confirm every filename other than the block-agnostic `xschemrc` / `netlist.sh`
/ `README.md` either carries a `<block-prefix>_` prefix or is on the
shared-cell list below.

**The shared-cell list**, recorded by **DR-004** as this convention requires —
these bare names are one canonical definition instantiated by more than one
block (the VCO, the divider and the lock detector), at Wp/Wn = 2.5/1.0 µm,
L = 0.28 µm and its ratios:

> `inv_3v3`, `inv2x_3v3`, `nand2_3v3`, `nand3_3v3`, `nor2_3v3`, `xor2_3v3`,
> `tgate_3v3`, `schmitt_3v3`, `delaywin_3v3`, `dff_tg_3v3`

**Block-owned cells today:**

| Cell | Owner | Sizing | Sized for |
|---|---|---|---|
| `pfdcp_inv_3v3` | PFD/CP (#9) | Wp/Wn = 1.5/0.5 µm, L = 0.3 µm | symmetric rise/fall in the PFD's 24-stage reset chain, with L one step above minimum for matching, and full `ad/pd/as/ps/nrd/nrs` junction geometry — the *absolute* delay of that chain is the load-bearing parameter behind the dead-zone result, so it is modelled rather than approximated |
| `pfdcp_nand2_3v3` | PFD/CP (#9) | Wp 1.5 µm, series NMOS 1 µm, L = 0.3 µm | pull-down strength tracking `pfdcp_inv_3v3`, keeping the reset path symmetric between the UP and DN branches |

The VCO's `vco_stage` / `vco_bias` and the PFD/CP's `pfd`, `cp`, `cp_leg_n`,
`cp_leg_p`, `srlatch`, `edgedet` are block *internals*, not leaf cells offered
to anyone else; they are named for their function and are instantiated only by
their own block's top.

**Rationale.** Of the three options considered (namespace per block; one
canonical shared library with a documented sizing rationale; a
subdirectory per block), per-block namespacing is the cheapest rule that
turns the failure mode from *silent* (same name, different meaning, picked by
whoever resolves the merge) into *structural* (names cannot collide, because
each block owns its own prefix) — reviewable by eye and requiring no schematic
rework. A single canonical shared library is arguably the better long-run end
state, but it requires converging the sizings two blocks have *already*
characterized over their own PVT grids and re-running whichever campaigns
move, which this issue does not force onto every future leaf cell just to get
a naming rule in place; a subdirectory per block would work too, but ripples
through `xschemrc`'s symbol search path and every existing schematic's
bare-name symbol references for no benefit over a filename prefix. Per-block
namespacing is also the outcome consistent with the lower-risk "separate"
default documented for resolving the *current* `inv_3v3` / `nand2_3v3`
instance of this exact problem.

**The `inv_3v3` / `nand2_3v3` collision that prompted this convention is now
resolved under it**, by **DR-004** (#29): the bare names stay with the shared
library exactly as the divider and lock detector landed them, and the PFD/CP
block's differently-sized copies were renamed to `pfdcp_inv_3v3` /
`pfdcp_nand2_3v3`. Neither block's electrical content moved — see DR-004 for
why adopting one sizing for both was rejected, and `sim/pfd-deadzone/` /
`sim/cp-compliance/` for the re-minted records that pin the renamed export.

`design/netlist.sh` mechanically enforces the failure-mode half of this
convention: every export is self-contained and inlines its own copy of every
leaf cell it uses, frozen at whatever the schematic looked like when that top
was last regenerated. The check hashes every `.subckt <name> … .ends` block
across all exports and fails loudly — naming the colliding tops and cell — if
the same cell name ever hashes differently across two of them. Byte-identical
content under the same name across multiple tops is expected and is **not** a
failure; only genuine divergence is.

Two properties of the check are worth knowing:

- it reads the **committed** exports, not freshly regenerated ones. That is the
  only version that can fire: `design/` is a flat namespace, so one
  `<name>.sch` yields one body and a set of exports all regenerated in the same
  run can never disagree. Committed exports *can*, because each is frozen at
  whatever the schematics said when its top was last regenerated;
- it spans the per-record **`pfd_cp`** top as well, from its fresh export,
  since it has no committed file to read. This is the half that catches the
  #26/#27 case — `pfd_cp` regenerated from today's schematics against the
  committed tops' frozen copies — and `pfd_cp` is otherwise the one top a
  collision passes through silently, having no committed export for the
  staleness diff to catch either;
- it runs, and blocks, under **both** invocations: `--check` fails (exit 1)
  without writing anything, and plain write mode refuses to write or copy the
  colliding exports into `design/netlist/` either, rather than reporting the
  collision and writing the colliding set anyway (#34).

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
| `pfdcp_inv_3v3` | unit inverter, Wp/Wn = 1.5u/0.5u at L = 0.3u — **block-owned**, see [Leaf-cell ownership and naming](#leaf-cell-ownership-and-naming) |
| `pfdcp_nand2_3v3` | unit 2-input NAND, Wp/Wn = 1.5u/1u at L = 0.3u — block-owned |
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
explicit **24-inverter delay chain**.

That delay chain is the dead-zone-elimination element, and **its length is set
by the charge pump, not by the logic**. The requirement is not merely that UP
and DN both toggle at zero phase error — they do that for any non-zero reset
delay — but that the minimum UP/DN pulse be long enough for the pump's output
current to actually *establish*. That is the whole reason this block's
dead-zone criterion is stated in the charge domain (see `sim/pfd-deadzone`).

Three constraints size it, and the first two are *ratios of the same gate
delays*, so they track process and temperature rather than holding at one
corner:

1. **Edge-detector pulse > SR-latch loop delay.** A SET pulse released before
   QB has responded lets the latch fall back for one NAND delay and re-set,
   which appears as a narrow glitch splitting the UP pulse in two *right at
   zero phase error*. A 3-stage detector chain was measured doing exactly
   that on the UP branch (the branch loaded by the reset NAND's inner input);
   5 stages carries roughly 5× the latch loop delay and removes it.
2. **Edge-detector pulse < reset delay**, else set and reset would be
   asserted simultaneously. 5 stages against ~27 gate delays.
3. **Reset delay > charge-pump turn-on time.** This is the binding one, and it
   is *not* a pure gate-delay ratio: the pump's turn-on is set by how fast the
   steering switch drags its tail node to the control-node voltage and how
   fast the bias nodes recover from that disturbance. A 6-inverter chain
   (~9 gate delays, 0.5–1.1 ns minimum pulse) was built and measured, and the
   phase-to-charge transfer went flat at 9 of the 45 PVT corners — every one
   of them slow/cold/low-supply — while the *logic* waveforms at those same
   corners were perfect. 24 stages gives a 1.1–1.9 ns minimum pulse and, with
   the charge-pump changes described below, restores the gain.

   The cost is bounded and small: the constant UP/DN overlap grows, and that
   overlap converts up/down *current* mismatch into static phase error at a
   rate of (overlap × mismatch fraction) — a few percent of a couple of
   nanoseconds, i.e. tens of picoseconds, far below the tail-charge offset
   that dominates the budget below.

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
  unit current.
- **Bias branch runs at 4× the unit current, with 4×-scaled diodes.** The
  mirror ratio is unchanged (4·Iunit through a 4× device mirrors Iunit into a
  1× leg) but every bias node gets 4× the transconductance. This is not
  cosmetic. Each bias node drives the paralleled gates of four legs, and the
  cascode-bias node drives four *wide* cascode gates; at 1× bias current its
  1/gm against that capacitance gives a recovery time constant comparable to
  the PFD pulse itself, so a bias node still recovering from the switching
  kick modulates the delivered current for the whole pulse. Measured at the
  worst corner (ss/−40 °C/2.97 V), scaling the bias 4× raised the
  phase-to-charge gain by **3.8×** with no other change.
- **Steering switches are sized for CHARGE and for RECOVERY, not for
  on-resistance.** They pass a few microamps, so IR drop is irrelevant (tens
  of millivolts at worst). Equal N and P widths (6u/0.3u) — *not*
  mobility-ratioed widths — because unequal widths put unequal channel and
  overlap charge on the two polarities and inject a net residue onto the
  control node at every switching event; an earlier 3u(N)/9u(P) pair did
  exactly that. They are not shrunk, either: the switch must re-establish its
  tail node at turn-on, and that recovery is what bounds how short the PFD's
  minimum pulse may be. A 1u pair measurably lowered the detector gain.
  `MDUMN`/`MDUMP` are the standard half-width dummies gated by the
  complementary control.
- **Shared, clamped dump node.** Idle legs steer to `VDUMP`, held near
  mid-supply by two stacked NMOS diodes to VSS and two stacked PMOS diodes
  from VDD (4u/12u — sized to hold the node *stiffly*, not merely to bound
  it: a narrower 1u/3u clamp left VDUMP free to swing ~0.5 V during a pulse,
  dragging the idle tail with it). See "Charge-error mechanism" below for why
  this is not the obvious rail-dump design.
- **Bias generation is out of scope for this block.** `IBN`/`ICN`/`IBP`/`ICP`
  are the four reference nodes; the testbenches drive them from ideal current
  sources at 4× the unit-leg current, as `sim/devchar-cp` drives its mirrors,
  so the measured mismatch is the output stage's own. The integrated block
  must supply four matched references from
  one constant-gm reference, and that contribution is additive to the budget
  below.

`Icp` lands in the **single-digit µA** range at every trim code, as DR-001's
sizing sanity check requires: 1.68–1.80 / 3.36–3.60 / 5.04–5.41 / 6.71–7.21 µA
for codes 00/01/10/11, min–max across all 45 PVT corners. The nominal setting
is code 10 (three unit legs, ≈5.2 µA).

The **effective phase-detector gain** — the charge actually delivered per unit
of phase error, which is what #10's loop-filter design must use, not the DC
Icp — is 2.19–5.67 µA across corners at the nominal code (`pfd-deadzone`
record). It is below the DC Icp because the pump spends part of every pulse
establishing its output current, and the gap widens at the slow/cold/low-supply
corners.

### Charge-error mechanism (why the dump node is shared and clamped)

At a few microamps and a sub-nanosecond minimum pulse, the *signal* charge per
pulse is only a few femtocoulombs. Anything that exchanges tens of
femtocoulombs with the control node once per reference cycle therefore
dominates it. The dominant such term is the **tail node**: when a steering
switch closes, the tail it was holding at its idle voltage is dragged to VOUT,
and that charge comes out of the control node.

Three dump-node designs were built and measured at the nominal corner, in this
order:

| Idle tail parked at | Measured net charge at zero phase error |
|---|---|
| each polarity's own rail (the obvious design) | ≈ −10 fC |
| shared unclamped dump node | ≈ −7 fC, and the node sat at 0.18 V |
| shared **clamped** dump node (current design) | ≈ −6 fC |

The unclamped shared node fails for an instructive reason: with both legs idle
it carries only the *difference* of two nominally equal currents, so it is
degenerate and any mismatch walks it to whichever end saturates first. The
clamp removes the degeneracy without adding a control loop.

The same tail mechanism has a second, sharper consequence — it does not just
offset the transfer, it can *flatten* it. If the tail has not finished moving
by the time the pulse ends, the pump delivers only a fraction of Icp for the
entire pulse, and lengthening the pulse by a phase error adds almost no
charge: the detector gain collapses even though the UP/DN waveforms look
perfect. That is what the 6-inverter reset chain hit at 9 of 45 corners. The
three changes that fixed it all attack the same time constant — a longer
minimum pulse (24 stages), a faster tail (6u switches, stiff clamp), and a
faster bias recovery (4× bias branch).

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

| # | Term | Systematic (measured, all 45 PVT corners) | **Budget (3σ, incl. random mismatch)** | Verified by |
|---|---|---|---|---|
| 1 | DC UP/DN current mismatch, `(Iup−Idn)/Iavg`, worst point in 0.9–2.4 V | −2.6 % … +4.7 % | **±12 %** | #15 |
| 2 | Effective UP/DN switching-time skew, `w_up − w_dn`, over the whole Vctrl window | −19.4 ns … +15.8 ns | **±30 ns** | #15 |
| 2a | — the same term at mid-window (Vctrl = 1.65 V) only | −8.4 ns … +3.0 ns | **±14 ns** | #15 |
| 3 | Residual net charge per reference cycle at zero phase error (Vctrl = 1.65 V) | −40.7 fC … +14.7 fC | **±100 fC** | #15 |
| 4 | Resulting static phase offset, `q_zero / Kd` (Vctrl = 1.65 V) | −3.9 ns … +9.8 ns | **±30 ns** over the full Vctrl window (= term 2) | #12 (closed loop) |

Notes on how to read this table:

- **Term 1 is dominated by finite output resistance**, and is measured at the
  *worst point inside the window*, not at mid-window: the two polarities' `ro`
  are not equal, so their curves diverge across the compliance range. The
  budget is set at ±12 % — well above the measured systematic value — because
  random `Vth`/`β` mismatch on the mirror devices is *not* in the measured
  number (`sw_stat_mismatch = 0`) and is the term #15 adds.
- **Terms 2, 3 and 4 are one physical effect** seen three ways, and it is
  **not** current mismatch. It is the **tail-node charge exchange**: when a
  steering switch closes, the tail it was holding at the dump-node voltage is
  dragged to the control-node voltage, and that charge comes out of the
  control node once per reference cycle. Term 2 measures it per polarity from
  a clean control edge; term 3 measures the net the loop actually sees with
  the real PFD driving; term 4 is term 3 divided by the detector gain, i.e.
  the phase at which the loop settles.
- **Term 2's strong Vctrl dependence is the mechanism's signature**, and it is
  the single most important number in this table for downstream work:

  | Vctrl | mean skew across 45 corners | worst corner |
  |---|---|---|
  | 0.9 V | +8.9 ns | +15.8 ns |
  | 1.65 V | −1.9 ns | −8.4 ns |
  | 2.4 V | −12.7 ns | −19.4 ns |

  The skew is proportional to `V_dump − Vctrl` and crosses zero near the dump
  node's own idle voltage. **This is a real limitation of the present design,
  not a measurement artefact.** A ±30 ns static offset is a couple of percent
  of a reference period at 1 MHz and most of a period at 25 MHz, so as drawn
  this block is comfortable at the bottom of the ratified 1–25 MHz reference
  range and is *not* comfortable at the top with Vctrl near a window edge.
  The fix is to make the dump node track Vctrl (a unity-gain buffer nulls the
  exchange outright) or, more cheaply, to re-centre the dump node so the error
  is symmetric about the window instead of one-sided. Both are scoped in
  **#24**, with this record set as the before-picture. Until then, #10's
  loop-filter and spur analysis and #12's closed-loop work should treat the
  static offset as Vctrl-dependent rather than a constant.
- **Term 4 is a static offset, not a frequency error.** A charge-pump
  asymmetry does not shift the locked frequency; the loop settles at the phase
  where the net charge per cycle is zero. What it costs is control-node ripple
  — the equilibrium UP pulse is longer than the DN pulse by exactly this
  offset — which is a reference-spur mechanism, hence a budget rather than a
  shrug.
- **The overlap-times-mismatch term is negligible here.** The classic
  static-phase-error formula (reset overlap × current-mismatch fraction) gives
  about 2 ns × 5 % ≈ 100 ps with the numbers above — two orders below the
  tail-charge term. That is worth stating explicitly, because it is the term
  most PFD/CP write-ups lead with, and at this current level it is not the one
  that matters.
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

This is the **shared** logic library: the VCO, divider and lock detector all
instantiate these cells unmodified. The PFD/CP block does not — it owns
`pfdcp_inv_3v3` / `pfdcp_nand2_3v3`, sized to a different argument, per DR-004 and
[Leaf-cell ownership and naming](#leaf-cell-ownership-and-naming).

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
- **A leaf cell is named for its owner** — a block that needs a gate sized to
  its own argument owns a copy prefixed with the block name (`pfdcp_inv_3v3`),
  rather than editing the shared library cell another block instantiates. See
  [Leaf-cell ownership and naming](#leaf-cell-ownership-and-naming) and DR-004; `netlist.sh` enforces
  it.
- Ports: inputs `ipin`, outputs `opin`, supplies `iopin`. Supplies are
  explicit pins on every cell — there are no global `VDD`/`VSS` nets, so a
  block can be placed on `vdd_div` without editing its children.
- Connectivity inside a schematic is by **net label** (`lab_pin`) rather than
  drawn wire. That keeps a schematic diffable as text and keeps the netlist
  the reviewable artifact; the trade-off is that the graphical rendering is
  sparse.
- Device geometry is written on the instance, not hidden in a model card, so
  a sizing change is visible in the diff.
