# `divider_chain` block — routing the Metal2 tracks over the device rows (issue #458)

Fourth area increment on this block, and the one
[`PROOF-macro-track-packing.md`](PROOF-macro-track-packing.md) (#454)
explicitly declined to take. Companions:
[`PROOF.md`](PROOF.md) (#310, the DRC/LVS-clean assembly),
[`PROOF-track-packing.md`](PROOF-track-packing.md) (#341, packing the
top-level track band) and [`PROOF-fold.md`](PROOF-fold.md) (#344, folding the
one row into two).

#454 left the block with 43 distinct Metal2 tracks packed as tightly as an
interval assignment can pack them — 11 of them `div23_cell`'s, which is that
interval graph's own clique number and therefore provably minimal — but still
sitting in an *exclusive band above* the device rows. `run_pv.py area` measured
that band at 43.97 µm over 26.32 µm of devices, with the Metal2 plane over
those device rows **1.0 % occupied**. This increment puts the tracks in that
plane. **It takes 37,289 µm², 74.4 % of #458's own stated 50,124 µm²
ceiling.**

## Result

| | Before (#454, PR #459) | After (this increment) | Delta |
|---|---|---|---|
| `divider_chain` footprint | 1317.66 × 70.29 µm (92,618 µm²) | **1317.66 × 41.99 µm (55,329 µm²)** | height **−40.3 %**, area **−40.3 %** |
| `div23_cell` footprint | 332.14 × 22.80 µm (7,573 µm²) | **332.14 × 12.52 µm (4,158 µm²)** | height **−45.1 %** |
| `divider_chain` device band | 26.32 µm | 26.32 µm | — (no device moved) |
| `divider_chain` no-device band | 43.97 µm | **15.67 µm** | **−64.4 %** |
| Metal2 fill over the device rows | 1.0 % | **15.9 %** | +14.9 pp |
| `divider_chain` fill | 26.5 % | **36.9 %** | +10.4 pp |
| `comp` share of the bbox | 1.46 % | **2.44 %** | +0.98 pp (same diffusion, smaller box) |

Against the ceiling this issue stated:

```
before                        1317.66 x 70.29 = 92,618 um2
ceiling (#458's own framing)  1317.66 x 32.25 = 42,494 um2   (saving 50,124)
achieved                      1317.66 x 41.99 = 55,329 um2   (saving 37,289)
                                                             ------------
                                                             74.4 % of the ceiling
```

The residual, 12,835 µm², is 9.74 µm of height: the tracks whose x-extent
crosses a `div23_cell` instance's own interior and therefore still have to
open a track above the rows. See "What this does not fix" below.

## Reproduction

```
$ python3 -m layout.pll_top.divider_chain.div23_cell     --outdir <workdir>/div23
$ python3 -m layout.pll_top.divider_chain.divider_chain  --outdir <workdir>/chain

$ python3 layout/run_pv.py drc <workdir>/div23/div23_cell.gds \
      --top div23_cell --run-dir <rundir>
DRC clean: div23_cell (D), 0 violations

$ python3 layout/run_pv.py drc <workdir>/div23/div23_cell.gds \
      --top div23_cell --offgrid --run-dir <rundir>
DRC clean: div23_cell (D), 0 violations

$ python3 layout/run_pv.py lvs <workdir>/div23/div23_cell.gds \
      <workdir>/div23/div23_cell.spice --top div23_cell --run-dir <rundir>
LVS match: div23_cell (D) layout == schematic

$ python3 layout/run_pv.py drc <workdir>/chain/divider_chain.gds \
      --top divider_chain --run-dir <rundir>
DRC clean: divider_chain (D), 0 violations

$ python3 layout/run_pv.py drc <workdir>/chain/divider_chain.gds \
      --top divider_chain --offgrid --run-dir <rundir>
DRC clean: divider_chain (D), 0 violations

$ python3 layout/run_pv.py lvs <workdir>/chain/divider_chain.gds \
      <workdir>/chain/divider_chain.spice --top divider_chain --run-dir <rundir>
LVS match: divider_chain (D) layout == schematic
```

Artifacts re-committed here and under `layout/evidence/divider-div23-proof/`,
replacing #454's copies (the convention
[`PROOF-track-packing.md`](PROOF-track-packing.md) and
`layout/evidence/vco-layout/PROOF-fold.md` already use for changed-cell
artifacts): `divider_chain.gds`, `div23_cell.gds`, both `drc-clean/` pairs,
both `lvs-clean/` triples. `layout/evidence/floorplan-skeleton/` is
regenerated too, because `skeleton.py` reads the block's recorded height.
**Both `.spice` reference netlists are byte-for-byte unchanged** — verified by
`diff` against the previously committed copies — because `reference_netlist()`
in each module derives from that package's net tables and never from drawn
geometry. The extracted `divider_chain.cir` still carries **226 `pfet_03v3` +
226 `nfet_03v3` = 452 devices**, and `div23_cell.cir` still carries 60.

| | |
|---|---|
| Generated | 2026-09-22 |
| Branch point | `origin/main` @ `d3e12cc` (#456/DR-016 landed) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` — this repo's pinned version, so #360's false-mismatch caveat does not arise |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D`, `--lvs_sub=VSS`, `poly_res=3k` (DR-009) |

## Why the plane over the device rows was empty, and what actually blocks it

The plane was never reserved. **Metal2 has no DRC relationship to the
diffusion, poly, implant, well or Metal1 underneath it** — no rule in
`<pdk>/libs.tech/klayout/drc/rule_decks/` relates the two. Every generator in
this package nevertheless stacked its tracks in a band above the cells,
because a band is trivially safe to reason about: `devgen.pack_tracks()` only
has to check x against nets already on the same track, and the band provably
contains nothing else.

What a track in the device plane genuinely has to clear is *other Metal2*, and
in this block there are exactly two sources of it:

1. **The Via1/Metal2 landing square `devgen._riser()` drops on every routed
   pad** (0.44 µm square, at the pad's own y). This is the
   `M2.2a`/`V1.1`/`V2.1` failure class `layout/pll_top/pfd_cp/cp.py`'s module
   docstring records **four** separate routing designs failing against, and
   the stated reason #454 did not take this lever.
2. **Every Metal2 shape a placed sub-block already contains** — here, each
   `div23_cell` instance's own interior: its track band plus its own pads'
   landing squares.

Measured on the committed pre-change GDS (`HEAD~1`), the Metal2-free
horizontal bands across one whole `ROW_PLAN` row — all 1317.66 µm of x, every
obstacle of both kinds included — were:

| Free band (row-relative y) | Height | What bounds it |
|---|---|---|
| −2.00 … −0.01 µm | 1.99 µm | below the pulldown row's lowest pad |
| 1.59 … 1.87 µm | 0.28 µm | between two pulldown pad rows |
| 3.47 … 3.75 µm | 0.28 µm | between two pulldown pad rows |
| **5.35 … 9.99 µm** | **4.64 µm** | **the inter-row channel: pulldown pads below, pullup pads above** |
| 11.59 … 11.87 µm | 0.28 µm | between two pullup pad rows |
| 13.17 … 14.86 µm | 1.69 µm | above the tallest pullup pad, below `div23_cell`'s own band |
| 15.30 … 22.36 µm | 10 × 0.31 µm | the gaps *between* `div23_cell`'s own 11 packed tracks |
| 22.80 µm upward | — | above the instances |

A 0.44 µm landing square needs ~1.26 µm of free band to sit in with this
package's 0.41 µm clearance, so the 0.28 µm and 0.31 µm bands are unusable
*to a net that spans the row*, and the corridor at 5.35 … 9.99 µm is the
prize: **5 tracks at the 0.75 µm pitch, free across the entire row**. It
exists because this package's fixed row-cell frame (`devgen.ROW_PD_Y0` = 0,
`ROW_PU_Y0` = 10) puts every pulldown and every pullup device at the same y in
every column, whether that column is a glue gate or one inside a
`div23_cell` — so the inter-row channel is a channel across the *whole block*,
not just one cell.

The same measurement on `div23_cell` alone is slightly looser, because the
glue columns the assembled row adds have taller stacks and therefore more pad
rows: free at −1.00 … −0.01, 1.29 … 1.87, 3.17 … 3.75, **5.05 … 9.99** and
11.29 … 14.56 µm. And because the obstacle test is per-net rather than
per-row, a *local* net — one whose two or three pads sit in a single column —
sees an even freer picture: a narrow band is only closed for a net whose own
x-extent actually reaches a pad in it. That is why 12 of `div23_cell`'s 13
tracks fit below its topmost pad rather than only the 5 a row-wide corridor
count would predict.

## What changed

One new function in `devgen.py`, `pack_tracks_over_devices()`, and one call
site substituted at each of the two levels — the same shape as #341's and
#454's substitutions:

```python
# before (issues #341, #454):
track_y = pack_tracks(nets, base_y=content_top + 3.0)

# after (issue #458):
obstacles = devgen.metal2_boxes(canvas)          # incl. placed instances, recursive
for pads in nets.values():
    obstacles += devgen.riser_landing_boxes(pads)  # what route_net() is about to draw
track_y = pack_tracks_over_devices(nets, y_floor=row_y, obstacles=obstacles)
```

`route_net()` and `_riser()` draw exactly what they always drew — one Metal2
bus rectangle plus one riser per pad, at whatever `track_y` they are handed.
**Only which `track_y` values are legal changed**, which is why both
`reference_netlist()` outputs are byte-identical and no pin moved.

`pack_tracks_over_devices()` keeps `pack_tracks()`'s left-edge order and its
same-track x-clearance rule unchanged, and replaces "track *i* sits at
`base_y + i·pitch`" with "this net sits on the lowest 0.75 µm step, at or
above `y_floor`, whose drawn rectangle clears every obstacle". Two deliberate
asymmetries in the clearance model, both chosen so it can never be *less*
strict than what already ships clean:

* **Against an obstacle**, a full 2-D separating-axis test at 0.41 µm on both
  axes, using the *landing square's* half-height (0.22 µm), not the narrower
  bus wire's (0.17 µm). 0.41 µm is well past M2.2a's 0.28 µm minimum; the
  extra is deliberate headroom, because an obstacle is geometry the function
  does not control.
* **Against another net already placed**, exactly `pack_tracks()`'s test: an
  x-clearance check, and only between nets on the *same* track. Two nets on
  adjacent tracks are 0.75 µm apart in y, i.e. 0.31 µm between their landing
  squares — under this function's own 0.41 µm obstacle clearance but over
  M2.2a's 0.28 µm minimum, and exactly the relationship every `pack_tracks()`
  band in this repo already ships DRC-clean. Re-testing it at 0.41 µm would
  reject the pitch this package is built on.

`pack_tracks()` itself is untouched, and remains the documented baseline the
new function is defined against.

### Both levels want the same corridor, and the macro wins

The two levels compete: a top-level bus crossing a `div23_cell` instance can
only use a corridor that instance left free, so whichever level takes the
inter-row channel denies it to the other. Both allocations were built and
measured rather than argued:

| Allocation | `div23_cell` | `divider_chain` |
|---|---|---|
| Neither (#454, before) | 332.14 × 22.80 µm | 1317.66 × 70.29 µm (92,618 µm²) |
| Top level only | 332.14 × 22.80 µm | 1317.66 × 53.99 µm (71,140 µm²) |
| **Macro (and top level with what is left)** | **332.14 × 12.52 µm** | **1317.66 × 41.99 µm (55,329 µm²)** |

The macro wins because a `ROW_PLAN` row's height is gated by the `div23_cell`
instance standing in it, so a micron taken out of the macro is taken out of
the block twice — the same leverage #454 measured for packing. No code selects
between the two: giving *both* levels the obstacle-aware assignment produces
the third row, because the macro's pass runs first and the top level's pass
then measures what is actually left.

### Where the tracks ended up

**A track count is no longer a height.** Under `pack_tracks()` the two were
the same thing: *n* tracks meant *n* × 0.75 µm of band. Here they are not, and
the distinct-track count actually goes *up* while the height goes down,
because a net takes the lowest y that fits it rather than the lowest y that
packs the set. This is the right trade and it is worth stating plainly, since
every prior record in this series used the track count as the figure of merit.

`div23_cell`, **13 distinct tracks** (up from `pack_tracks()`'s provably
minimal 11): **12 of them below the macro's own topmost pad** — y = 0.00,
2.25, 3.00, 3.75, 4.50, 5.25, 6.00, 6.75, 7.50, 8.25, 9.00, 9.75 — and **one
above**, y = 12.00, carrying `Q` and `XFQ_NMB`. Footprint top 22.50 →
12.22 µm.

`divider_chain` row 0, **18 distinct tracks** (up from 12): 9 below the
instances (y = 0.00 … 9.00) and 9 above (14.25 … 20.25). Row 1, **17** (up
from 10): 9 below, 8 above. The tracks that stay above are exactly the ones
whose x-extent crosses a `div23_cell` interior — `VSS`, `VDD_DIV`, `MA`,
`MI0`…`MI4`, `T0`…`T4`, `CK1`…`CK6`, `MO3`, `MB` — and the ones below are the
nets local to a single glue group.

### The tightest spacing in the block did not move

The obvious way for a change like this to be wrong is to shave a real DRC
margin somewhere the deck happens not to look. It did not: the **minimum
positive edge-to-edge gap between any two shapes on a layer** is identical
before and after, on both layers, in both cells —

| | Metal2 | Metal3 |
|---|---|---|
| `divider_chain`, before (`HEAD~1`) | 0.3100 µm | 0.3100 µm |
| `divider_chain`, after | **0.3100 µm** | **0.3100 µm** |
| `div23_cell`, before (`HEAD~1`) | 0.3100 µm | 0.3100 µm |
| `div23_cell`, after | **0.3100 µm** | **0.3100 µm** |

— against M2.2a's and M3.2a's 0.28 µm minimum. 0.31 µm is the pitch-minus-
landing-square relationship between two adjacent tracks, which is this
package's tightest geometry by construction and has been since #308. The
tracks moved; the closest approach between two of them did not, which is what
the clearance model above was designed to guarantee and what the deck then
confirmed independently.

### The "packed track floor" metric no longer bounds this block

`run_pv.py area`'s `max(packed-track floor, device band) × width` ceiling —
#442's own rule, and the source of both this issue's 42,494 µm² figure and
DR-016's 1.20× bound — assumes tracks occupy an *exclusive* band. That is the
assumption this change breaks. The audit now reports 53 distinct Metal2 tracks
for this block (up from 43: the same nets, at more distinct y values, because
they are no longer all on one band's pitch grid) for a nominal 39.75 µm
"packed floor" against 15.67 µm of no-device band actually drawn. **The
formula's output is now larger than the geometry it describes**, so for this
block it is a historical comparator, not a bound. The real floor is the device
band alone: 26.32 × 1317.66 = 34,681 µm², i.e. DR-016's 1.13× "every Metal2
track routed at zero area cost" term, which this block is now 20,648 µm²
above rather than 57,937 µm² above.

`layout/tests/test_area_audit.py`'s two `divider_chain` assertions are
**inverted rather than deleted** for the same reason: the plane over the cells
being ≥ 10 % occupied, and the routing band being *shorter* than the device
band, are now the evidence that §5.5's lever C was spent.

## What this does not fix

**9.74 µm of height, 12,835 µm², is still a band above the rows**, carrying
the nets whose x-extent crosses a `div23_cell` instance. Those cannot drop
into the channel because the macro's own tracks are there now, and they cannot
cross on Metal3 either — the macro's own risers are vertical Metal3 runs
through exactly that span. Closing it needs something this repo's routing
fabric does not have: a fourth routing layer, or a macro that reserves a
through-corridor for its parent. Neither is a `track_y` change, and neither is
in this issue's scope.

**Width is unchanged**, as at #341 and #454: 1317.66 µm, six `div23_cell`
instances plus 46 glue columns in two rows.

**The block is no longer the chip's dominant area term.** At 55,329 µm² it is
behind the loop filter's 36,936 µm² only by a factor of 1.5, where at #454 it
was 2.5× the next-largest block. The whole-chip arithmetic is re-derived in
`PLL-FLOORPLAN.md` §5.13; `spec/pll.md#area`'s ratified ≤ 0.30 mm² row is
**not** touched here — coming in further under a ratified row needs no
amendment, and amending it downward is a decision record's job, not a
layout PR's.

**Stated rather than quietly left**: the consequence is that
`spec/pll.md#area`'s *measured* table — the one reproducing DR-016's
block-by-block figures — now lags the committed geometry by **two** levers,
still reading `pfd_cp` at 344.98 × 77.30 µm / 0.0267 mm² (#469 took it to
0.0264 mm²), `divider_chain` at 1317.66 × 70.29 µm / 0.0926 mm² and the total
at 0.2733 mm² / 1.82×. Those were true when DR-016 was ratified and are false
of the committed GDS after this PR. Refreshing them is the same act as
amending the row they sit under, which CLAUDE.md routes through `spec/` with a
decision record; it is filed as **#476** rather than done here, and until that
lands `PLL-FLOORPLAN.md` §5.13 and
`layout/evidence/area-audit/area-audit.md` are the current measurement.

## Properties re-proved rather than assumed

- **#295's "six identical `div23_cell` instances"** — re-proved geometrically
  at the new footprint by `test_divider_chain.py`'s
  `test_six_div23_instances_are_laid_out_identically`, which clips six windows
  out of the flattened GDS at the recorded `div23_boxes` and compares them
  shape-for-shape, the same way #344 and #454 re-proved it.
- **Both `reference_netlist()` outputs byte-for-byte unchanged** — `diff`
  against the previously committed `.spice` files, zero bytes differing.
- **`div23_cell`'s pin locations and x-extent unchanged** — all seven pins and
  `x0`/`x1`/`y0` are identical to the values
  `layout/evidence/divider-div23-proof/PROOF.md` records; only `y1` moves,
  22.50 → 12.22. Same property #454 had, asserted by `test_divider_div23.py`.
- **`skeleton.DIVIDER_CHAIN_STANDALONE_H_UM`** updated to 41.99 and
  cross-checked against a live rebuild by `test_floorplan_skeleton.py`'s
  `test_divider_chain_recorded_footprint_matches_the_generator`, so the
  no-KLayout floorplan view cannot drift from the generator.
- **Every committed block GDS still reproduces from its generator** —
  `test_gds_reproducibility.py`, which is why the `floorplan-skeleton`
  artifact and its DRC output are regenerated here too.
- **The new routing code is tested on known answers, not only through the
  block** — `test_divider_devgen.py` adds 20 tests over
  `_boxes_clear()`/`riser_landing_boxes()`/`metal2_boxes()`/
  `pack_tracks_over_devices()`: the no-obstacle case is asserted *equal* to
  `pack_tracks(base_y=y_floor)` (so the new function is a strict
  generalization, not a different algorithm wearing the same name), a
  corridor between two obstacle bands is asserted to be used rather than
  climbed over, an obstacle outside a net's own x-extent is asserted not to
  push it up, and `metal2_boxes()` is asserted to see Metal2 *inside* an
  un-flattened placed instance — the obstacle that dominates the top level.
- Full suite: `python3 -m unittest discover -s layout/tests -t layout/tests`,
  748 tests, OK.

## `klt` friction

None to report for this increment, on the same reading #341/#454 recorded:
`pack_tracks_over_devices()` is plain Python over float rectangles, and the
only tool surface it touches is `klayout.db`'s own
`Cell.begin_shapes_rec()` (to read a placed instance's Metal2 back out of the
canvas), which did exactly what it says. Per CLAUDE.md's friction protocol,
nothing here is a `klt` gap.
