# `divider_chain` block — folding the six-instance row (issue #344)

Third record for this block, append-only alongside [`PROOF.md`](PROOF.md)
(issue #310, the DRC/LVS-clean assembly) and
[`PROOF-track-packing.md`](PROOF-track-packing.md) (issue #341, the routing
band). Those two left the block signoff-clean at **2634.28 x 57.07 um =
0.1503 mm^2** — still one row, still (just) over the entire 0.15 mm^2
whole-chip area target on its own, with exactly one structural cause
outstanding: its width was the sum of every sub-cell's width.

**This is the fold #310 and #341 both deferred.** The block is now two rows
of three `div23_cell` instances, each row carrying its own independent
`devgen.pack_tracks()` band.

## Result

| | Before (#341) | After (this increment) | Delta |
|---|---|---|---|
| `divider_chain` footprint | 2634.28 x 57.07 um (150,338 um^2) | **1317.66 x 100.29 um (132,148 um^2)** | area **-12.1 %** |
| Rows | 1 (6 instances + 46 glue columns, side by side) | **2** (3 instances + 23 glue columns each) | |
| Top-level Metal2 tracks | 22, in one full-width band | **12 + 10 = 22**, in two half-width bands | same count, half the width each |
| Cross-row nets (Metal3 spine columns) | n/a | **7** (`VSS`, `VDD_DIV`, `VCO`, `MO3`, `MB`, `DIVOUT`, `CK3`) | |
| Divider chain + lock detector | 0.1578 mm^2 | **0.1396 mm^2** | -12 % |
| Whole-chip re-summed overrun (`PLL-FLOORPLAN.md` §5) | ~2.0x | **~1.9x** | still an overrun, smaller |
| `skeleton.total_extent_um2()` | ~1.09e6 um^2 | **~0.61e6 um^2** | -44 % |

**Does the block now fit the 0.15 mm^2 whole-chip target on its own?**
Yes — 0.1321 mm^2 against 0.15 mm^2, for the first time since this block had
real geometry (0.2471 mm^2 at #310, 0.1503 mm^2 at #341). That is a
*necessary* condition for the chip to fit, never a sufficient one: the
re-summed whole-chip total is still ~1.9x the budget, and this record does
not claim otherwise.

```
$ python3 -m layout.pll_top.divider_chain.divider_chain --outdir <workdir>
rows      : 2
  row 0: y    0.000 ..   49.220  width  1275.220 um
  row 1: y   52.220 ..   99.940  width  1313.920 um
footprint : 1317.660 x 100.290 um  (132148.1 um^2)

$ python3 layout/run_pv.py drc <workdir>/divider_chain.gds \
      --top divider_chain --run-dir <rundir>
DRC clean: divider_chain (D), 0 violations

$ python3 layout/run_pv.py lvs <workdir>/divider_chain.gds <workdir>/divider_chain.spice \
      --top divider_chain --run-dir <rundir>
LVS match: divider_chain (D) layout == schematic
```

Artifacts (re-committed here, replacing #341's committed copies — the same
convention #341 itself used, and `layout/evidence/vco-layout/PROOF-fold.md`
before it): `divider_chain.gds`, `divider_chain.spice` (**byte-for-byte
unchanged** — `reference_netlist()` derives purely from this package's net
tables, never from drawn geometry, so re-grouping the glue logic for
*placement* changed nothing in it; verified by `diff` against the committed
copy before overwriting), `drc-clean/drc.stdout.log`,
`drc-clean/divider_chain_main.lyrdb`, `lvs-clean/lvs.stdout.log`,
`lvs-clean/divider_chain.cir` (extracted — still **226 `pfet_03v3` + 226
`nfet_03v3` = 452 devices**, unchanged from #310/#341),
`lvs-clean/divider_chain.lvsdb`.

| | |
|---|---|
| Generated | 2026-09-09 |
| Branch point | `origin/main` @ `2bb09f4` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| KLayout (pip wheel, geometry generation) | same install used for `--outdir` build |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D`, `--lvs_sub=VSS` |

## The edge case this had to clear first: does the fold actually *reduce* area?

#341's own record, and `PLL-FLOORPLAN.md` §5.1 before it, warned that a naive
row fold trades width for height at roughly **constant** area, because with
`devgen.NetTracks`'s one-never-reused-track-per-net scheme each new row wants
its own band whose height scales with the block's *total* net count. That is
the failure mode this increment had to avoid, not merely a caveat to repeat,
so the two levers are separated here:

| | Width x height | Area | vs #341 |
|---|---|---|---|
| #341 baseline, one row | 2634.28 x 57.07 um | 150,338 um^2 | — |
| Folded, placement gaps left at #310's 20 um | 1401.66 x 100.29 um | 140,572 um^2 | **-6.5 %** |
| Folded, instance/glue gap re-derived to 6 um | 1317.66 x 100.29 um | **132,148 um^2** | **-12.1 %** |

The fold *alone* is worth -6.5 %; re-deriving the placement gap (below) is
worth another -5.6 %. Both are reported rather than only the total, because
they are independent levers and a reader is entitled to know how much of the
headline number is the fold itself.

Where the -6.5 % comes from, arithmetically:

* **Device rows cost slightly more.** Two rows of 37.8 um (the `div23_cell`
  footprint height) at ~1400 um beats one row of 37.8 um at 2634 um only if
  the folded rows are narrower than half the original, which they are not
  quite: 2 x 1401.66 = 2803 um of row width against 2634 um, because each row
  pays its own instance/glue gaps and the spine. That term is **+9,700 um^2**.
* **The routing band costs much less.** 22 tracks over 2634 um of width
  (43,461 um^2 of band) became 12 + 10 tracks over ~1400 um each
  (23,100 um^2). That term is **-20,400 um^2**.

The band term wins, which is exactly the property #341 unlocked — and it only
wins because the *total* track count stayed at 22 rather than roughly
doubling to one full band per row. Two placement decisions are what kept it
there, both placement-only with no electrical change whatsoever:

* **The glue logic moved in beside the instances it wires.** Through #341 all
  46 glue-logic columns sat to the right of all six instances, so every chain
  net (`CK1`..`CK6`, `MI0`..`MI4`, `MO0`..`MO5`) ran the block's full width to
  reach them. Measured on the #341 geometry, the count of mutually
  overlapping net extents ramps monotonically from 0 at the block's left edge
  to its maximum of **22, at x = 2118.79 um — the first glue column** — and
  that peak *is* the track count the left-edge packing algorithm has to open,
  since it is the interval graph's own clique number. `_stage_columns(i)` now groups
  exactly the gates whose nets terminate on `XD<i>`/`XD<i+1>`, and `ROW_PLAN`
  places each group next to those instances.
* **The one-hot AND second stage split in two.** `XMA` consumes
  `T0`/`T1`/`T2` and `XMB` consumes `T3`/`T4`/`T5`. Placing each in the row
  holding the three stages that produce its own terms keeps all six `T` nets
  row-local; keeping them in one shared "mux" group leaves three of the six
  crossing a row boundary, and a cross-row net costs a whole track in *every*
  row it appears in (see the spine section below). Measured: 7 cross-row nets
  with the split, 9 without.

## What changed, and why it is safe

### `devgen.py`: two additions, no behaviour change for existing callers

* `route_net()` gains an optional keyword-only `bus_to_x`, which extends the
  drawn Metal2 bus out to that x without drawing a riser there — the landing
  a cross-row net's spine link comes down onto. Defaulting to `None`
  reproduces the previous drawing byte-for-byte, and every other caller in
  this package (`div23_cell.py`, `dff_tg_3v3.py`) passes nothing, so their
  generated GDS is untouched.
* `route_spine()` is new: one net's vertical Metal3 run at a reserved x, with
  a Via2 + Metal3/Metal2 landing square at each of that net's per-row
  `track_y` values. It is the cross-row counterpart of `route_net()`, built
  from the same `_canvas._via_square()` primitive `_riser()` already uses.

`NetTracks` and `pack_tracks()` are both unmodified.

### Why the spine cannot short anything

The spine sits at **negative x** — left of every row, all of which start at
x = 0 — one column per cross-row net at 1.0 um pitch, nearest column 3.0 um
from the rows' left edge. Three collision classes, each checked rather than
assumed:

* **Spine Metal3 to spine Metal3.** Neighbouring columns are 1.0 um apart and
  the widest shape either draws is a 0.44 um Via2 landing square, leaving
  0.56 um — over M3.2a's 0.28 um minimum.
* **Spine Metal3 to anything it passes over.** A spine run crosses every
  intervening row's full height, but only at x < 0, where no row draws
  anything at all. What it does cross is the Metal2 bus each row extends
  leftward to meet it — a different layer with no via between them, which is
  the same property `_riser()`'s own long Metal3 run has always relied on.
* **Two cross-row nets sharing one track.** They cannot: every cross-row net's
  extent runs from its own pads out to the spine, so all of them mutually
  overlap in the strip between the row's left edge and the nearest spine
  column. `pack_tracks()` is given each net's spine point as part of its
  extent precisely so this is visible to the packer, and it opens a separate
  track for each — which is also why `ROW_PLAN` is built to minimise the
  *number* of cross-row nets rather than to balance the two rows' widths
  perfectly.

Left rather than right is a mechanical choice, recorded because it is not
obvious: a right-hand spine's x depends on the widest row's drawn width,
which is not known until the glue columns are drawn, which cannot happen
until each row's y placement is known, which needs that row's track count,
which needs the spine. Anchoring at x = 0 makes the spine a function of the
net tables alone and cuts that circularity, instead of resolving it with a
throwaway measurement pass.

### The re-derived placement gap

#310 set `DIV23_GAP_X_UM = GLUE_GAP_X_UM = 20.0` um as "generous headroom
past NW.2b's ~1.4 um min nwell-to-nwell spacing, since each instance's own
nwell already reaches close to its footprint's own edge". Measured against
the drawn cell, that premise is not quite right, and a folded block pays this
gap several times per row:

* `div23_cell`'s n-well spans x = -0.5 .. 329.3 inside a footprint of
  -2.62 .. 329.52 — inset **2.12 um** from the instance box's left edge and
  **0.22 um** from its right. Two instances G um apart therefore have
  G + 2.34 um between their wells: at G = 6 that is **8.34 um**, ~6x NW.2b's
  minimum.
* The tightest rule at that boundary is not the well spacing at all but plain
  same-layer metal spacing — Metal1/2/3 *do* reach the instance box's edge —
  so two instances G apart have G um of metal-to-metal clearance against
  M1.2a/M2.2a/M3.2a's 0.23–0.28 um.
* DF.16_LV (n-well to nmos comp, 0.43 um min) is slacker still: the
  neighbour's leftmost nfet comp is a further 2.62 um in.

6 um keeps at least an order of magnitude of headroom on every one of those.
As always in this repository the derivation is not the proof — the PDK's own
DRC deck is, and it is clean at this value (see "Result").

## Six identical `div23_cell` instances — still true, re-checked at two rows

#295's acceptance criterion (the six instances must be one placed cell, not
six independent redraws) is the invariant a fold is most likely to break, so
it is checked the same way #310 and #341 checked it, extended to the folded
geometry: `layout/tests/test_divider_chain.py`'s
`test_six_div23_instances_are_laid_out_identically` clips each instance's own
window out of the flattened top cell, translates it to a common origin, and
XORs it against instance 0's — on every device layer (`comp`, `poly2`,
`nplus`, `pplus`, `nwell`, `contact`, `metal1`). Still an empty XOR on every
layer.

Two things changed in *how* it is checked, both forced by the fold:

* The six instances no longer sit on one uniform x step, so the windows come
  from `build()`'s own recorded `div23_boxes` (each instance's as-placed
  bounding box) rather than from a placement pitch.
* The windows are clipped in **y** as well as x. With one row, "clip the full
  height at this x" was equivalent; with two, the row above/below and this
  row's own track band would otherwise leak into the comparison.

The substance of the criterion is untouched: `build()` still reads one
`div23_cell` GDS and places six `CellInstArray` references to that single
cell, so a future TSPC/E-TSPC single-cell swap is still the one-symbol
substitution #295 asked for.

## What this does not fix

* **Device density.** At 0.1321 mm^2 for 452 transistors the block spends
  ~292 um^2/transistor, against `lock_detector`'s ~187 for the same PDK and
  flavour — the diffusion-island-per-device convention
  `vco/primitives.py` documents. That is now the *only* structural cause left
  in this block, it is shared with the VCO's own residual overrun
  (`layout/evidence/vco-layout/PROOF-fold.md`'s "What is still not proved"),
  and #344 deliberately did not fold it in.
* **The whole-chip overrun.** `PLL-FLOORPLAN.md` §5.3's arithmetic still
  shows ~1.9x against the < 0.15 mm^2 draft budget (down from ~2.0x at #341
  and ~2.9x at #310). The divider chain fitting the target *on its own* is
  necessary, not sufficient.
* **Further folding.** Three-, four- and six-row plans were all built and
  measured, each with a sampled search over where the four free glue groups
  (`MA`, `MB`, `OUT`, `FRT`) land, and all came out *worse* than two rows:

  | Rows | Best measured | vs two rows |
  |---|---|---|
  | **2** | **1317.66 x 100.29 um = 132,148 um^2** | — |
  | 3 | 883.47 x 154.01 um = 136,063 um^2 | +3.0 % |
  | 4 | 807.92 x 203.98 um = 164,800 um^2 | +24.7 % |
  | 6 | 487.88 x 300.92 um = 146,813 um^2 | +11.1 % |

  Each additional row repeats the `div23_cell` footprint's own 37.8 um height
  plus that row's own 3.0 um base gap, 3.0 um inter-row gap and band, while
  the width saving falls off as 1/R and the cross-row net count (and with it
  the per-row track floor) rises. Two rows is a measured optimum for this
  content, not a first guess that happened to work.

## klayout-tools friction: reported on the existing issue, not a new one

Per this repository's friction protocol (`CLAUDE.md`), a genuine `klt`
capability gap hit while drawing real geometry gets filed generically on
`2AMLogic/klayout-tools`. This increment hit one, and it is already tracked:
**`2AMLogic/klayout-tools#1467`** ("no track or layer assignment between
nets"), open, filed from a different block on this same friction path.

Everything this increment had to hand-write — a per-row track channel rather
than one global one, and a reserved cross-row column per net whose pins span
rows — is the same *routing-resource assignment* capability #1467 is about,
one axis further out. It is not a distinct defect, so it was
[added as a second data point on #1467](https://github.com/2AMLogic/klayout-tools/issues/1467)
rather than filed as a near-duplicate issue. The comment states the
multi-row dimension generically (a channel per row; a reserved cross-row
resource; and the second-order effect that every cross-row net then costs a
whole track of *every* row's channel, so a fold that ignores it produces a
taller block than the unfolded one) with no reference to this design.

Nothing else in this increment needed a `klt` capability that does not
exist. `route_spine()` and `route_net()`'s `bus_to_x` are drawn with the same
`Canvas.rect()` / `_via_square()` primitives this package has used since
#308; `ROW_PLAN` and `spine_columns()` are plain Python over the module's own
net tables and call no KLayout API at all; and the one KLayout-specific
operation the fold *did* need — clipping and XOR-comparing six windows out
of a flattened cell, for the identical-instances check — was already
available as `db.Region` boolean operations and already in use here.
