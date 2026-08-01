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

  # Closed-loop top level (#52, DR-001 Decisions 1-3)
  pll_top.sch / .sym    the five blocks below, wired into the loop

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
  cp_dumpbuf.sch/.sym   dump-node buffer holding VDUMP at the control voltage
  srlatch, edgedet      custom logic cells the PFD is built from
  dut_export.sch        netlist-export root for pfd_cp; not part of the design

  # Loop filter (#10, DR-001 Decision 1 / DR-006)
  loop_filter.sch/.sym  passive fixed 2nd-order filter: series R + shunt C1 + C2

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
| `vco`, `div23_cell`, `divider_chain`, `lock_detector`, `dff_tg_3v3`, `loop_filter`, `pll_top` | `design/netlist/<top>.spice` | yes | yes |
| `pfd_cp` | `<outdir>/dut.spice`, path echoed on stdout | no | n/a |

`pll_top` is committed even though it, like `pfd_cp`, is a deep hierarchy —
it inlines every cell in the block. That is the point: it is the DUT the
`pll_top_dut.sh` campaigns instantiate (#52's smoke test and #14's
supply-sensitivity today; #12's and #13's campaigns are still on the older
block-concatenation path — see "Simulating it" below), so exactly one exported
assembly has to exist for all of them to agree on, and `--check` staleness is
what keeps that one file honest against the schematics. It also means the
collision check below now has a *committed* copy of the PFD/CP hierarchy's
leaf cells to compare the per-record `pfd_cp` export against, which is strictly
more coverage than before.

**Wrapped port lists (#52).** xschem breaks a long `.subckt` port list onto a
`*+` continuation line — which is a **comment**. Promoting only the
`**.subckt` header, as the exporter originally did, therefore left the tail of
a long port list commented out, silently demoting those ports to
subcircuit-local nodes: a deck that netlists, simulates, and is wrong.
`pll_top` is the first top here with enough ports to hit it. `export_block`
now promotes the continuation along with the header, and `check_export`
asserts that no `*+` line survives in any export — the failure is invisible to
every other check, since all the `.subckt`s are present, no `netN` appears, and
no pin is reported missing.

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
`cp_leg_p`, `cp_dumpbuf`, `srlatch`, `edgedet` are block *internals*, not leaf cells offered
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
| `edgedet` | rising-edge pulse generator (AND of X and X delayed 5 stages) — its **0.33–0.39 ns** output pulse is the narrowest signal anywhere in the loop, and therefore what bounds every closed-loop simulation's internal timestep; see [PFD (`pfd.sch`)](#pfd-pfdsch) below and `sim/README.md`'s "Closed-loop internal-timestep bound" |
| `srlatch` | NAND SR latch, active-low set/reset |
| `pfd` | tri-state phase-frequency detector |
| `cp_leg_n` / `cp_leg_p` | one **unit** of charge-pump sink / source current |
| `cp_dumpbuf` | dump-node tracking buffer: complementary pair of unity-gain 5T OTAs |
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

> **Simulating anything that contains this block?** `edgedet`'s internal SET
> pulse — `AND(X, NOT(X delayed by 5 inverters))`, measured **0.33–0.39 ns**
> — is narrower than the 1.1–1.9 ns UP/DN pulse the 24-inverter chain below
> eventually produces, and it is the *internal* pulse that bounds a transient's
> ngspice timestep. Sizing the ceiling from the UP/DN number instead is the
> trap: the integrator then steps clean over the set pulse, the PFD stops
> seeing feedback edges, and the loop reports a confident **false** "does not
> lock". `sim/README.md`'s "Closed-loop internal-timestep bound" states the
> rule (100 ps), how to comply, and which committed records predate it.

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
   nanoseconds, i.e. tens of picoseconds. That used to be two orders below the
   tail-charge offset; now that #24 has nulled the tail term it is only about
   one order below it, and it is the next term that would matter if the offset
   ever had to shrink further.

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
- **Shared, Vctrl-tracking dump node.** Idle legs steer to `VDUMP`, which
  `cp_dumpbuf` holds at the control-node voltage. Because the dump node and
  the control node are then at the same potential, a steering switch closing
  sees *no step* between the tail it was parked on and the node it is being
  connected to, and the tail-charge term is nulled rather than balanced. This
  replaces (does not supplement) the fixed diode clamp the block shipped in
  #9 — the two cannot coexist. See "Charge-error mechanism" below for the
  measured history, and **DR-005** for why a bias helper of this shape is
  compatible with DR-001 Decision 1's no-opamp-in-the-loop-path constraint.
- **The buffer is two amplifiers, not one, and that is a headroom result.** A
  single differential pair cannot span the 0.9–2.4 V Vctrl window on a 2.97 V
  worst-case rail: an NMOS-input pair runs out of tail headroom at the bottom
  and a PMOS-input pair at the top. `cp_dumpbuf` therefore ties the outputs of
  two unity-gain 5T OTAs, one of each polarity, together on `VDUMP`; where
  they overlap they work in parallel, and outside its range each one's tail
  collapses and its output device turns off rather than fighting. Tails mirror
  four unit currents (≈8 µA) each off the existing `IBN`/`IBP` diodes — sized
  to exceed the largest trim code's `Icp` so that a persistently one-sided PFD
  state (which is what acquisition looks like) cannot collapse the node, not
  merely for settling speed. Cost: ≈16 µA of static current (≈53 µW), and two
  MOS gates (≈0.3 pF) on the control node — 0.2 % of the loop filter's C1.
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
Icp — is **4.76–5.89 µA** across corners at the nominal code (`pfd-deadzone`
record `20260731-192355-afa338c`). It is still below the DC Icp because the
pump spends part of every pulse establishing its output current, but only
slightly, and the spread across corners is now 1.24:1. Before #24's dump-node
buffer the same measurement gave **2.19–5.67 µA**, a 2.6:1 spread with the
floor set by the slow/cold/low-supply corners: holding the dump node at the
control voltage removes the tail excursion the pump used to spend the start of
every pulse recovering from, so the gain a loop-filter design can rely on at
the worst corner **more than doubled**. #10 should size against the new floor,
not the old one.

### Charge-error mechanism (why the dump node is shared and buffered)

At a few microamps and a sub-nanosecond minimum pulse, the *signal* charge per
pulse is only a few femtocoulombs. Anything that exchanges tens of
femtocoulombs with the control node once per reference cycle therefore
dominates it. The dominant such term is the **tail node**: when a steering
switch closes, the tail it was holding at its idle voltage is dragged to VOUT,
and that charge comes out of the control node.

Four dump-node designs have been built and measured, in this order:

| Idle tail parked at | Measured net charge at zero phase error | Worst UP/DN skew over the Vctrl window |
|---|---|---|
| each polarity's own rail (the obvious design) | ≈ −10 fC | not characterized |
| shared unclamped dump node | ≈ −7 fC, and the node sat at 0.18 V | not characterized |
| shared **clamped** dump node (#9) | −40.7 … +14.7 fC over 45 corners | −19.4 … +15.8 ns |
| shared **Vctrl-tracking** dump node (current design, #24) | **−3.50 … +0.30 fC** over 45 corners | **−0.60 … −0.05 ns** |

(The first two rows are nominal-corner spot measurements taken while the
topology was being chosen; the last two are the full 45-point campaigns, from
`pfd-deadzone` records `20260731-121919-63e4b47` and `20260731-192355-afa338c`
and `cp-compliance` records `20260731-122451-63e4b47` and
`20260731-194124-afa338c` respectively.)

The unclamped shared node fails for an instructive reason: with both legs idle
it carries only the *difference* of two nominally equal currents, so it is
degenerate and any mismatch walks it to whichever end saturates first. The
clamp removes the degeneracy without adding a control loop — but a *fixed*
park voltage can only null the exchange at one control voltage, which is why
the clamped row still carries a large Vctrl-dependent skew. The measured null
sat at **1.487 V**, already close to the middle of the 0.9–2.4 V window, so
re-centring the clamp was measured to be nearly exhausted as a mitigation
(≈20 % off the worst case, and it makes the 0.9 V end worse). Making the node
*track* the control voltage removes the term instead of re-balancing it.

The same tail mechanism has a second, sharper consequence — it does not just
offset the transfer, it can *flatten* it. If the tail has not finished moving
by the time the pulse ends, the pump delivers only a fraction of Icp for the
entire pulse, and lengthening the pulse by a phase error adds almost no
charge: the detector gain collapses even though the UP/DN waveforms look
perfect. That is what the 6-inverter reset chain hit at 9 of 45 corners. The
three changes that fixed it all attack the same time constant — a longer
minimum pulse (24 stages), a faster tail (6u switches, stiff clamp), and a
faster bias recovery (4× bias branch).

**What remains, and the honest limit.** The buffered dump node (`cp_dumpbuf`,
ratified as compatible with DR-001 Decision 1 by **DR-005**) is that fix, and
it is now in the design. What survives is the buffer's own residual input
offset — a few millivolts of `V_dump − Vctrl` rather than up to 0.75 V — and it
is *measured, not assumed*, at every corner. Two honest limits remain:

1. **The residual is one-signed.** Post-mitigation the skew is negative at
   every one of the 135 (corner, Vctrl) points (−0.60 … −0.05 ns) rather than
   straddling zero, which says it is a systematic buffer offset and not noise.
   It is small enough not to matter at any reference frequency in the ratified
   range, but it will not average out.
2. **The buffer's own noise is not characterized here.** Its thermal and
   flicker noise reaches the control node through the input pairs' `C_gs`.
   #24's campaigns measure *charge*, not noise; **#14** owns that, and a
   supply/noise record taken from here on must state that it measured the
   buffered revision.

---

## Up/down mismatch budget

**This section is the budget #15's Monte Carlo campaign (`mc-cp-mismatch`)
checks statistical dispersion against.** It is a *stated budget*, not a
restatement of what one simulation happened to produce: the measured
systematic values are corner-swept worst cases, and the budget adds allocation
for the terms this block's own testbenches deliberately exclude.

| # | Term | Systematic (measured, all 45 PVT corners) | **Budget (3σ, incl. random mismatch)** | Verified by |
|---|---|---|---|---|
| 1 | DC UP/DN current mismatch, `(Iup−Idn)/Iavg`, worst point in 0.9–2.4 V | −2.7 % … +4.7 % | **±12 %** | #15 |
| 2 | Effective UP/DN switching-time skew, `w_up − w_dn`, over the whole Vctrl window | −0.60 ns … −0.05 ns | **±3 ns** | #15 |
| 2a | — the same term at mid-window (Vctrl = 1.65 V) only | −0.47 ns … −0.05 ns | **±2 ns** | #15 |
| 3 | Residual net charge per reference cycle at zero phase error (Vctrl = 1.65 V) | −3.50 fC … +0.30 fC | **±20 fC** | #15 |
| 4 | Resulting static phase offset, `q_zero / Kd` (Vctrl = 1.65 V) | −0.06 ns … +0.67 ns | **±3 ns** over the full Vctrl window (= term 2) | #12 (closed loop) |

**Provenance of the measured column**: term 1 and term 2 from `cp-compliance`
record `20260731-194124-afa338c`; terms 3 and 4 from `pfd-deadzone` record
`20260731-192355-afa338c`. Both were minted after #24 replaced the fixed
dump-node clamp with `cp_dumpbuf`. The before-picture records
(`20260731-122451-63e4b47`, `20260731-121919-63e4b47`) stand unmodified and
are what the "was" figures below refer to.

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
- **Terms 2, 3 and 4 fell by 12–32× in #24**, because the exchange is
  proportional to `V_dump − Vctrl` and the dump node now tracks `Vctrl`
  instead of sitting at a fixed 1.487 V. Term 2's worst case went
  **19.4 ns → 0.60 ns**, term 3's **40.7 fC → 3.50 fC**, term 4's
  **9.8 ns → 0.67 ns**. Term 1 did not move at all (the DC characteristic does
  not involve the dump node — the two campaigns' DC tables are numerically
  identical), which is the cleanest confirmation available that the two error
  mechanisms really are independent.
- **The budgets in the right-hand column were re-derived, not just scaled
  down.** They now sit at 4–6× the measured systematic worst case, where the
  pre-#24 budgets sat at 1.5–2.5×. That widening is deliberate and is the
  point: with the systematic term nulled, **random** device mismatch is no
  longer a perturbation on top of a large systematic error — it is the
  dominant contributor to terms 2–4, and it is not in the measured column
  (`sw_stat_mismatch = 0`). The residual now traces mostly to `cp_dumpbuf`'s
  own input offset, so #15's Monte Carlo must include the buffer's input pairs
  and not only the mirror legs. If #15 finds the distribution does not fit
  inside these numbers, the resolution is a decision record, not a quiet
  widening here.
- **Term 2's Vctrl dependence used to be the mechanism's signature, and it is
  now gone** — which is the single most useful fact in this table for
  downstream work:

  | Vctrl | mean skew across 45 corners | worst corner | *(was, #9)* mean | *(was)* worst |
  |---|---|---|---|---|
  | 0.9 V | −0.41 ns | −0.60 ns | +8.9 ns | +15.8 ns |
  | 1.65 V | −0.21 ns | −0.47 ns | −1.9 ns | −8.4 ns |
  | 2.4 V | −0.26 ns | −0.48 ns | −12.7 ns | −19.4 ns |

  The skew is proportional to `V_dump − Vctrl`, so with the dump node tracking
  the control node the term is nulled at every control voltage rather than at
  one. The worst-case corner of the before-picture — **Vctrl = 2.4 V**, where
  the skew reached −19.4 ns at `fs/125 °C/2.97 V` — now measures **−0.48 ns**
  worst case across all 45 corners, and the residual no longer varies
  systematically with Vctrl (0.41/0.21/0.26 ns of mean, i.e. flat to within
  the corner spread). **#10's loop-filter and spur analysis and #12's
  closed-loop work may now treat the static offset as a small constant rather
  than a Vctrl-dependent term.** At the 25 MHz top of the ratified reference
  range a 0.6 ns offset is 1.5 % of a reference period, against the ~50 % the
  pre-#24 design carried there.
- **Term 4 is a static offset, not a frequency error.** A charge-pump
  asymmetry does not shift the locked frequency; the loop settles at the phase
  where the net charge per cycle is zero. What it costs is control-node ripple
  — the equilibrium UP pulse is longer than the DN pulse by exactly this
  offset — which is a reference-spur mechanism, hence a budget rather than a
  shrug.
- **The overlap-times-mismatch term is now the *next* term, not a negligible
  one.** The classic static-phase-error formula (reset overlap ×
  current-mismatch fraction) gives about 2 ns × 5 % ≈ 100 ps with the numbers
  above. Against the pre-#24 tail-charge term that was two orders down and
  safely ignorable; against the post-#24 residual (0.60 ns worst case) it is
  only about 6× down. It is still not the binding term, but it is the one that
  would have to be attacked next — by trimming `Icp` (term 1 is what the 2-bit
  trim exists for) or by shortening the reset overlap — if the static offset
  ever had to shrink another order of magnitude.
- **Bias-generator contribution is excluded** from both the measured column
  and, deliberately, from the budget: it is a separate block. When it lands,
  its mirror mismatch adds to term 1 and the budget must be re-derived rather
  than silently absorbed. Note that `cp_dumpbuf`'s tails now mirror from the
  same `IBN`/`IBP` references, so the bias block must supply ≈16 µA more than
  it did before #24, and a bias failure now takes the dump node's definition
  with it (there is no passive clamp behind it any more — see DR-005).
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

# The loop filter (`loop_filter.sch`)

Cell landed by #10: DR-001 Decision 1's **passive, fixed** second-order
network between the charge pump (`cp.sch`) and the VCO's `VCTRL` input —
series R, shunt C1, shunt C2. No R/C trim banks: DR-001 explicitly rejects a
programmable filter (the band-switched VCO's `Kvco ∝ f_out` already
self-compensates the loop gain, and switches on the loop's highest-impedance
node are themselves a spur mechanism). The only loop-side programmability is
the charge pump's own 2-bit Icp trim (`cp.sch`), which `sim/loop-dynamics`'s
stability sweep covers as an axis of that campaign, not as a filter-side knob.

```
VCTRL --+-- C2 -- VSS          zero  fz  = 1/(2·π·R·C1)
        +-- R -- NZ -- C1 -- VSS    3rd pole fp3 = (C1+C2)/(2·π·R·C1·C2)
```

## Component choice and sizing

Each element is sized from `sim/devchar-passives`'s real, corner-swept device
data (#4 → #10), not DR-001's hand-calc placeholders:

- **R — 4× `ppolyf_u` in series**, W = 2 µm, L = 107 µm each. `ppolyf_u` is
  the near-zero-tempco poly option (≈ −75 ppm/°C, section- and
  width-independent) — the loop-filter-friendly choice next to the salicided
  and high-sheet variants, which trade tempco for density or run positive.
  Four devices in series (rather than one long one) only for layout
  convenience; electrically it is one resistor.
- **C1 — 4× `cap_nmos_03v3_b`**, 87 × 87 µm each (30 276 µm² total). This is
  the **body-tied (accumulation-mode)** connection DR-001 asks for: the raw
  `cap_nmos_03v3` is denser but has a severe voltage coefficient (`cv_ratio`
  ≈ 45× over 0.3–3.3 V) — unusable as the dominant loop-filter cap, since its
  effective value (and hence the loop's zero) would swing by the same factor
  as `Vctrl` moves. The body-tied variant trades some density for `cv_ratio`
  ≈ 1.10×, i.e. C1 stays within a few percent of its mid-window value across
  the DR-003 Decision 5 usable Vctrl range (0.9–2.7 V) — see
  `sim/loop-dynamics` for the measured C–V curve at the real operating
  points, not just the nominal one. Gate on the filter node, bulk on `VSS`.
- **C2 — 1× `cap_mim_2f0_m2m3_noshield`**, 31.4 × 31.4 µm. MIM is ideally
  linear (`cv_ratio` = 1.0000) and sits directly on `VCTRL`, where a
  voltage-dependent cap would modulate the ripple pole itself.

C1 is the area-dominant element (§ acceptance criteria in #10): at the real
device density from `sim/devchar-passives`, four 87×87 µm devices consume
≈ 20 % of the 0.15 mm² block area budget — see `sim/loop-dynamics/records/`
for the exact figure at every corner, not a single nominal number.

## Regenerating and editing

Same convention as every other block: edit `loop_filter.sch` in xschem, save,
then `design/netlist.sh --top loop_filter` to refresh the committed
`design/netlist/loop_filter.spice`, and re-run `sim/loop-dynamics/testbench/run.sh`
to mint a fresh evidence record (records are append-only; the old one
stands).

---

# The closed-loop top level (`pll_top.sch`)

The five blocks above, wired into DR-001's type-II charge-pump loop. Landed by
**#52**, whose framing is worth keeping in view: this file exists so there is
**one** top-level assembly in the repo. Before it, three separate issues each
nominally needed a top level and each would have built its own — which is not a
merge conflict but something worse, three subtly different loops each producing
its own "evidence".

```
  REF ──▶ [pfd_cp] ──UP/DN──▶ [lock_detector] ──▶ LOCK
            │ VOUT
            ▼
          VCTRL ════ [loop_filter]   (R + C1 + C2 to VSS)
            │
            ▼
          [vco] ──CLK──┬──▶ CLK (block output)
                       │
                       ▼
              [divider_chain] ──FB──▶ back to pfd_cp.FB
                       │
                       └──▶ DIVOUT (pre-retiming monitor tap)
```

## The four wiring facts that are load-bearing

1. **`pfd_cp.VOUT`, `loop_filter.VCTRL` and `vco.VCTRL` are one net.** The loop
   filter is a two-terminal shunt network — `loop_filter.sym` has exactly
   `VCTRL` and `VSS` — because DR-001 Decision 1 puts it *passively across* the
   charge pump's output node. There is no current-injection pin and nothing in
   series with the loop.
2. **`pfd_cp.FB` is driven by `divider_chain.FB`, not by `divider_chain.DIVOUT`.**
   `FB` is the output of the retiming flop `XFRT` inside `divider_chain`,
   clocked by the VCO, so the edge the PFD sees is one flop's clk→Q after a VCO
   edge **independent of N** — DR-001 Decision 3's interface contract to #9.
   `DIVOUT` is the raw chain/mux output, whose delay is the accumulated clk→Q of
   the `k` *active* cells and therefore moves with the programmed N. Wiring
   `DIVOUT` to the PFD would still lock, and a single-point smoke test would not
   notice, but it would reintroduce exactly the N-dependent static phase offset
   the retiming flop exists to remove. Both are brought out as monitor pins so a
   testbench can see the retiming for itself.
3. **The lock detector taps `UP`/`DN`, not the control node.** It is a passive
   monitor (DR-002 Decision 4); nothing in it drives a loop node. Its `VWIN` pin
   is an *output* — the integrating window node, brought out of the cell for
   observation — not a threshold input, so it stays an internal net here.
4. **Three supply domains stay separate all the way to the pins**: `VDD`
   (reference / PFD / charge pump / lock detector), `VDD_VCO` + `GND_VCO` (the
   VCO's own quiet domain, with its on-chip decap inside `vco.sch`) and
   `VDD_DIV` (the divider) — DR-001 Decisions 2 and 3. `VSS` is the shared
   ground for everything except the VCO.

## Pins

| Group | Pins | Notes |
|---|---|---|
| Reference | `REF` | reference clock in |
| VCO band | `B2 B1 B0` | 3-bit static band select (`vco.sch`) |
| Icp trim | `CPB1 CPB0` | 2-bit static charge-pump trim (`cp.sch`). Named `CPB*` rather than `B*` only so the top-level net names stay distinct from the VCO band bits |
| Divider | `P5..P0`, `SEL5..SEL0` | `N = 2^k + Σ P_j·2^j (j<k)`, one-hot `SEL_(k-1) = 1` |
| Bias | `IBN ICN IBP ICP` | charge-pump current references — **bias generation is out of scope for this block**, testbenches drive these ideally at 4× the unit-leg current |
| Outputs | `CLK`, `LOCK` | the block output and the lock flag |
| Monitors | `DIVOUT`, `FB`, `VCTRL` | observability only: the pre-retiming divider output, the retimed feedback edge, and the control node |
| Supplies | `VDD`, `VDD_VCO`, `GND_VCO`, `VDD_DIV`, `VSS` | three domains, per DR-001 |

Every configuration input is **static** — there is no calibration FSM in v1
(DR-001 Decision 2), so an integrator has to know its band code and its N code,
and a part programmed into the wrong band will not lock. That is a
datasheet/integration burden the architecture accepted deliberately.

## Simulating it

`sim/lib/pll_top_dut.sh` is the path from **this schematic** to a runnable
deck. It owns three things that would otherwise drift between campaigns: where
the DUT comes from (`design/netlist/pll_top.spice`, the committed export), how
the deck is put together (export + stimulus concatenated into one
self-contained file, so a record's frozen snapshot reproduces the run on its
own), and what the configuration bits mean — `cloop_divider_params 8` rather
than twelve hand-set bits, since a mis-encoded one-hot `SEL` still locks, just
at the wrong N. `sim/pll-top-smoke/` (#52) and `sim/supply-sensitivity/` (#14)
use it.

**It is not yet the only closed-loop assembly path in the repo.**
`sim/lib/assemble_closed_loop.sh` (#12) predates this schematic and takes a
different route: it concatenates the committed *block* exports with a fresh
`pfd_cp` export and leaves the loop to be wired by each testbench's own
top-level instance list — it never reads `pll_top.spice`. `sim/lock-time/` and
`sim/output-range/` are built that way and have recorded evidence against that
DUT, so the helper stays exactly as it is until those campaigns are re-run
against `pll_top`. Migrating them is follow-up work; `sim/README.md` ("Closed-loop
campaigns: two assembly paths") carries the current split, and every record's
Netlist provenance field names the helper its numbers came from.

`sim/pll-top-smoke/` is this block's own acceptance gate: one nominal-corner
cold-start run proving the assembled loop acquires and holds lock. It is
deliberately **not** a PVT campaign — lock time and band coverage are #12,
jitter is #13, supply pushing and power are #14. Of those, #14 runs against
this assembled DUT today; #12's two campaigns do not yet.

**Every closed-loop transient against this DUT inherits a 100 ps
internal-timestep ceiling from the PFD** — not from the VCO, and not from the
charge pump. It is a property of `edgedet`'s set pulse (see the note under
[PFD (`pfd.sch`)](#pfd-pfdsch) above), so it does not move when a campaign
changes its output frequency, its reference, or its divide ratio. The single
shared constant is `SIMENV_CLOSED_LOOP_TMAX` in `sim/lib/simenv.sh`; the rule,
the compliance recipe and the failure mode are in `sim/README.md`'s
"Closed-loop internal-timestep bound".

## Regenerating and editing

Same convention as every other block: edit `pll_top.sch` in xschem, save, then
`design/netlist.sh --top pll_top` to refresh the committed
`design/netlist/pll_top.spice`, and re-run
`sim/pll-top-smoke/testbench/run.sh` to mint a fresh evidence record (records
are append-only; the old one stands). A change here invalidates every record
taken through `sim/lib/pll_top_dut.sh`, not just this block's. Records taken
through `sim/lib/assemble_closed_loop.sh` (#12's `lock-time`, `output-range`)
do not read this file at all, so a change here does not invalidate them — it
makes them diverge from it, which is the reason those campaigns are queued to
move onto this assembly. The other blocks' own records are unaffected either
way, since they netlist their own tops.

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
