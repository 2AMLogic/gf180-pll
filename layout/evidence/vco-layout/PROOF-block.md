# Assembled VCO block — five sub-blocks, one guard ring, DRC-clean (issue #293, increment 5)

Companion to [`PROOF.md`](PROOF.md) (increment 1: the 5-stage ring, PR #305),
[`PROOF-mirror-buffer.md`](PROOF-mirror-buffer.md) (increment 2: the
band-select mirror + output buffer, PR #313),
[`PROOF-bias-resistors.md`](PROOF-bias-resistors.md) (increment 3: the
`ppolyf_u_3k` primitive + `RCG`/`ROFF`/`RDEG`, PR #314), and
[`PROOF-vtoi-core.md`](PROOF-vtoi-core.md) (increment 4: the V-to-I core's
thirteen transistors, PR #316).

Every one of those four increments named the same remaining scope in its own
words: **the inter-sub-block wiring that merges ring + bias generator
(resistors + V-to-I core) + band mirror + output buffer under one shared
guard ring, and the combined block's own standalone DRC run.** This increment
is that work.

**Update (issue #324, closing #293):** the one acceptance criterion this
increment left open below — a block-level `VDD_VCO`-tied n-well tap ring,
concentric with the `GND_VCO` ring — is now drawn, funded by folding the
band-select mirror into two tiers. See
[`PROOF-mirror-fold.md`](PROOF-mirror-fold.md) for that increment's own
before/after footprint, DRC/connectivity results, and negative controls. The
footprint numbers and DRC run recorded below are this increment's own
historical record (PR #325) and are superseded by that file, not edited
here.

| Block | Generator | Top cell | GDS |
|---|---|---|---|
| Whole VCO (`vco.sch` + `vco_bias.sch`) | `layout/pll_top/vco/block.py` | `vco_block` | `vco_block.gds` |

## What "assembled" means here

Five separately-clean blocks are not one clean block. Before this increment
none of the nets *between* the sub-blocks existed as drawn geometry anywhere:

| Net | From | To |
|---|---|---|
| `NC` | `RCG`'s signal pad (`bias_resistors.py`) | V-to-I core's `MN2` source degeneration |
| `NOFF` | `ROFF`'s signal pad | V-to-I core's `MOFF` source |
| `NVI` | `RDEG`'s signal pad | V-to-I core's `MVI` source |
| `VBP0` | V-to-I core's summing node | band mirror's cascade A gate |
| `VBP` | band mirror output | ring's `VBP` bias rail (all 5 stages' `MPH` gates) |
| `VBN` | band mirror output | ring's `VBN` bias rail (all 5 stages' `MNT` gates) |
| `Y5` | ring stage 5's output pad | output buffer's stage-1 input gate |
| `VDD_VCO` | block supply trunk | all four n-well tap bands |
| `GND_VCO` | block guard ring | all five sub-block guard rings |

plus the block's own boundary pins (`VCTRL`, `B0`/`B1`/`B2` in; `CLK` out;
`VDD_VCO`/`GND_VCO`).

## Result

```
$ python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_block.gds \
      --top vco_block --run-dir <run> --offgrid
DRC clean: vco_block (D), 0 violations
```

| Item | Value |
|---|---|
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| KLayout | 0.28.16 |
| Deck | the PDK's own `libs.tech/klayout/drc/run_drc.py`, deep mode, `--offgrid` on |
| Rules executed | 556 |
| Polygons in the design | 13,291 |
| Block footprint | 294.78 × 148.18 µm (43,680 µm²) |
| Violations | **0** |

Artifacts in this directory: `vco_block.gds`,
`drc-clean/drc-block.stdout.log`, `drc-clean/vco_block_main.lyrdb`,
`drc-clean/connectivity-block.log`.

## The DRC run is a real gate, not a tautology

Same negative control this repo's `layout/harness/faults.py` uses everywhere
else — inject an undersized Metal1 shape into the assembled block's own GDS
and re-run the identical command:

```
$ python3 -c "...faults.inject_drc_violation('vco_block.gds', 'vco_block_drcfault.gds')"
inserted a 0.10 x 2.00 um Metal1 rectangle at (3.0, 7.0) um -- below the 0.23 um minimum Metal1 width
$ python3 layout/run_pv.py drc vco_block_drcfault.gds --top vco_block --run-dir <run> --offgrid
DRC violations: vco_block (D), 1 item(s) -- M1.1x1
```

The deck sees this block's geometry and fails it when it should.

## DRC alone would not have caught a broken route — so connectivity is proved too

A Metal2 wire that stops 0.5 µm short of its via1, or a via1 that lands
beside a rail instead of on it, is **perfectly DRC-clean and completely
broken**. Full LVS needs a block-level SPICE netlist and a device-recognition
pass (its own increment); what this increment is responsible for is the
*interconnect*, and that is checkable now. `block.connectivity_report()`
runs KLayout's own `LayoutToNetlist` connectivity extraction over
metal1/via1/metal2 and probes both ends of every route
(`drc-clean/connectivity-block.log`):

```
  ok   NC               RCG signal pad <-> V-to-I core's NC track: 2 probe(s) -> one net
  ok   NOFF             ROFF signal pad <-> V-to-I core's NOFF track: 2 probe(s) -> one net
  ok   NVI              RDEG signal pad <-> V-to-I core's NVI track: 2 probe(s) -> one net
  ok   VBP0             V-to-I core summing node <-> band mirror cascade A: 2 probe(s) -> one net
  ok   VBP              band mirror VBP output <-> ring VBP rail: 2 probe(s) -> one net
  ok   VBN              band mirror VBN output <-> ring VBN rail: 2 probe(s) -> one net
  ok   Y5               ring stage-5 output <-> output buffer input gate: 2 probe(s) -> one net
  ok   VDD_VCO          supply trunk <-> all four n-well tap bands: 5 probe(s) -> one net
  ok   GND_VCO          block guard ring <-> every sub-block guard ring: 6 probe(s) -> one net
  ok   CLK              output buffer's last stage <-> the block's CLK pin: 2 probe(s) -> one net
  ok   VCTRL            block VCTRL pin <-> V-to-I core's VCTRL track: 2 probe(s) -> one net
  ok   B0/B1/B2         block pin <-> band mirror's own track: 2 probe(s) -> one net
  ok   VDD_VCO != GND_VCO / VBP != VBN / NOFF != NVI / VBP0 != VBP   distinct nets
connectivity: PASS
```

**This check is itself a real gate**, verified the same way the DRC run is:
suppressing exactly one via1 (the one that lands `Y5` on the buffer's input
gate) leaves the layout DRC-clean and makes the check fail —

```
  [neg-control] suppressed via1 at (56.2, 125.94)
  FAIL Y5 ring stage-5 output <-> output buffer input gate: 2 probe(s) -> 2 separate nets [15, 22]
```

The four `!=` rows matter as much as the `ok` rows: they show the extraction
distinguishes nets at all, so "one net" is a finding rather than an artifact
of everything having merged.

## Why the layout is flat, not hierarchical

Each sub-block generator is drawn into one shared `primitives.Canvas` through
`Canvas.at(dx, dy)`, which translates that generator's own local coordinates
into the block's frame. That is deliberate: this block's routing has to
*merge* with sub-block shapes — a via1 landing inside a sub-block's own
Metal1 rail, a Metal2 track extended past a sub-block's boundary — and two
shapes that must merge into one polygon for DRC have to live in the same
cell. A cell instance's shapes cannot be grown by its parent.

**The five standalone proofs above are still valid**, because the offset is
`(0, 0)` for a standalone build. Verified rather than asserted: all five
standalone GDS files were regenerated with this increment's `primitives.py`
changes in place and compared against the artifacts already committed here,
per layer, on merged-polygon count and merged area — **identical for all
five** — and each was re-run through the DRC deck (0 violations each).

## Routing discipline (what makes this hand-checkable)

Two sub-blocks (`mirror.py`, `vtoi_core.py`) already use Metal2, as
horizontal per-net tracks on a 0.8 µm pitch inside their own device channel;
the other three are Metal1-only. So:

* **Every top-level signal route is Metal2.** Metal2 has no spacing
  relationship with Metal1/comp/poly/implant in this deck, so a route may
  cross any sub-block's guard ring, rails, devices and taps freely. The only
  geometry it can collide with is other Metal2.
* **A route into a mesh-block pin is that pin's own track, extended** — same
  direction, same `y`, so the extension's nearest other-net Metal2 is still
  the adjacent track at 0.8 − 0.44 = 0.36 µm, above `M2.2a`'s 0.28 µm.
* **Everything else runs in an inter-row channel or a side column.**
  `block._Router.reserve()` records every drawn segment and raises a Python
  exception naming both nets if two different nets' Metal2 come within
  `M2.2a` — the same "cheaper as an exception than as a DRC marker" check
  `mirror.py`'s `Plan.reserve()` makes on Metal1.

### The one net that is not Metal2: `VDD_VCO`

A Metal2 supply trunk would cross every Metal2 signal escaping to the same
side. A plain Metal1 run *into* a sub-block is worse — it would cross that
block's own Metal1-covered `GND_VCO` guard-ring band, i.e. short to ground.
So `VDD_VCO` is a **Metal1 vertical trunk** in the right-hand channel
(signals cross over it on Metal2, no rule between the layers), and each
sub-block is fed by a short Metal2 hop from the trunk to a via1 landing on
that block's own n-well tap band — hopping over the guard ring on the layer
that is allowed to. `GND_VCO` needs no trunk: it is the substrate, and the
block-level ring is tied to each sub-block's ring by a Metal1 strap in the
left-hand channel (the side the supply trunk is not on).

## Acceptance criteria, checked

| Issue #293 AC | Where |
|---|---|
| Real DRC-clean layout for ring + bias generator + 3-cascade band mirror + 3-stage buffer | this block; per-sub-block proofs in the four companion PROOFs |
| Dedicated VCO guard ring, tap pitch ≤ 15 µm everywhere inside the block | **partial** — block-level `GND_VCO` p-ring drawn by `block.build()`, per-sub-block rings retained inside it, worst-case device-to-tap distance anywhere in the block 12.1 µm (`test_tap_pitch_bound_holds_for_every_sub_block`). The `VDD_VCO`-tied n-well tap rings are **per sub-block**, not a block-level second ring — see "The one acceptance criterion this increment does not fully close" below |
| Band-mirror cascades common-centroid | `mirror.py` + `check_common_centroid()`, PR #313 |
| Buffer's largest stage closest to `CLK`, farthest from the ring's starved nodes | `buffer.py` orders stages smallest-first with `CLK` on its right edge; `block.py` places the buffer with its *input* over the ring's stage-5 pad, so the large stage is the far one |
| 22 pF decap carried forward unchanged, adjacent to the `VDD_VCO` pin/ring-tap junction | `block.decap_boxes_um()` — the same 2 × 50 × 50 µm layer-(0,0) markers, placed against the block's own `VDD_VCO` trunk pin; `ring.build(draw_decap=False)` suppresses the ring's own copy so there is exactly one marker pair |
| Block runs DRC-clean standalone against real geometry | above |
| `skeleton.py`'s `VCO_CORE` placeholder replaced; footprint deviation from the 140 × 100 µm ROM noted explicitly | `skeleton.py`'s `VCO_CORE` is now this block's own guard-ring box; see below |
| klayout-tools gaps filed generically | none hit — see below |

## Area: the ROM estimate is overrun, stated plainly

`PLL-FLOORPLAN.md` §5 budgets the whole VCO at **0.011–0.017 mm²** (ROM).
The real block is **0.0437 mm²** — a **2.6–4.0× overrun**. That record's own
§5 anticipates exactly this and prescribes the response ("if real per-block
layout pushes the conservative estimate's ≈34 % margin below zero, that is a
budget overrun this record's own methodology predicts is plausible … the next
floorplan revision should state the overrun explicitly rather than silently
rounding the total down"), so:

* Re-running §5's own arithmetic with the measured VCO number replacing its
  ROM row: block subtotal ≈ 0.111 mm² conservative (0.0369 loop filter +
  0.0437 VCO + 0.020 PFD/CP + 0.0052 divider+lock), ≈ **0.139 mm²** after
  §5's ×1.25 top-level overhead. Still inside the 0.15 mm² budget — but the
  margin drops from ≈34 % to ≈**7 %**.
* `skeleton.total_extent_um2()` (the whole-skeleton bounding box, a
  deliberately looser number than the budget table) is **148,157 µm²**, i.e.
  ≈1.2 % under the 150,000 µm² draft target where it previously had ≈3 %.
  `test_skeleton_bounding_box_headroom_against_the_draft_budget` asserts
  *both* facts — under budget, and above 140,000 µm² — so the next block to
  land real geometry discovers the tightness in its own test run rather than
  in review.

The cause is structural and already on record per sub-block: every device is
its own diffusion island wired by metal (`primitives.py`'s module docstring),
and every sub-block is a single row, so the band-select mirror alone is
266 µm wide and sets the block's width. This increment did take the easy
half of that back — packing the resistor trio into the V-to-I core row's own
leftover width instead of beside it, and trimming the boundary-pin channels,
cut the block from 327.2 × 148.2 µm to 294.8 × 148.2 µm (−11 %) — but
**folding the single-row sub-blocks into multiple rows is the real lever and
is not this issue's scope.** At ~50 % area utilisation inside the guard ring,
that lever is worth roughly another 2× and should be a separate issue.

## The one acceptance criterion this increment does not fully close

**Closed by issue #324, see [`PROOF-mirror-fold.md`](PROOF-mirror-fold.md).**
The section below is left exactly as PR #325 recorded it, for history.

`PLL-FLOORPLAN.md` §1 asks for the VCO's guard ring to be "tied to `GND_VCO`
on the substrate side and to a local `VDD_VCO`-tied n-well tap ring on the
p-well side … a real two-sided ring, not a substrate-only one."

What is drawn: the **block-level** ring is `GND_VCO` substrate only. Every
n-well inside the block is `VDD_VCO`-tied by its own sub-block's tap band
(12.1 µm worst case), which satisfies the well-tie and tap-pitch halves of
that sentence and is arguably what "a *local* … n-well tap ring" means — but
it is not a second, concentric n-well ring at the block boundary, which is
the other reading. This PROOF does not pick the reading that flatters it.

Why it is not simply added here: an n-well band at the block boundary needs
its own width (≥ `NW.1a_LV`'s 0.86 µm), its `DF.4d_LV` tap inset, and
`DF.16_LV` clearance to comp on both sides — about 4.4 µm per side, so
+8.8 µm of block width. There is no width budget for that today: as the area
section above records, `skeleton.total_extent_um2()` already sits ~1.2 %
under the 0.15 mm² draft target, and +8.8 µm of VCO width would take that to
~0.1 %. Block *height* is free (the skeleton's height is set by the loop
filter, not the VCO), so the fix and the area optimisation are naturally the
same increment: folding the single-row sub-blocks into multiple rows both
recovers the width and pays for the ring.

That is why this PR is `Part of #293` rather than closing it.

## klayout-tools friction: none new

Per this repo's friction protocol, tool gaps hit while drawing real geometry
get filed generically on `2AMLogic/klayout-tools`. This increment hit none:
it builds geometry directly against `klayout.db`, uses KLayout's own
`LayoutToNetlist` for the connectivity proof, and runs the PDK's own DRC
deck — the same approach the rest of `layout/` already uses and documents in
`layout/README.md`. The one capability this increment needed and did not have
(placing an existing generator's output at an offset) is a property of *this
repo's* generators, not of klayout-tools, and was added here as
`primitives.Canvas.at()`.

## What is still not proved

* **LVS.** No block-level SPICE netlist is generated yet, and no device
  recognition is run. The connectivity check above covers the interconnect
  only. `mirror.py` also records one deliberate layout-vs-netlist deviation
  (cascade B's legs folded 1 → 2 fingers, total W/L and device count
  preserved) that a future LVS increment has to reconcile.
* **Extraction / post-layout simulation.** Nothing here says what the drawn
  parasitics do to DR-003's tuning range or jitter — that is a separate
  deliverable and the numbers in `sim/` remain pre-layout.
* **The block-level n-well guard ring** — see the section above.
* **Top-level assembly.** Wiring this block into `pll_top` alongside the
  PFD/CP, divider chain and lock detector is issue #297.
