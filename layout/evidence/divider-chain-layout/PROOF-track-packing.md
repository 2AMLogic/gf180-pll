# `divider_chain` block — routing-track packing (issue #341)

Companion to [`PROOF.md`](PROOF.md), which recorded the assembled block as it
stood after issue #310's final increment (PR #342): DRC-clean, LVS-clean, but
2634.28 x 93.82 um = 0.2471 mm^2, a 2.9x whole-chip area overrun once
re-summed with every other measured block (`PLL-FLOORPLAN.md` section 5.1).
That record traced ~57% of the block's *height* to a single structural cause
-- `devgen.NetTracks` handing every one of the block's 71 top-level nets its
own never-reused Metal2 track_y, regardless of how local that net's own pads
actually are -- and explicitly did not attempt fixing it, since #310's own
scope was the DRC/LVS-clean assembly, not the area budget.

**This is that fix, on the height axis only.** The width (six `div23_cell`
instances + 46 glue-logic columns, side by side) is unchanged; folding that
row is issue #344, filed as a follow-up rather than attempted here (see "What
this does not fix" below for why the two are separate).

## Result

| | Before (PR #342, issue #310) | After (this increment) | Delta |
|---|---|---|---|
| `divider_chain` footprint | 2634.28 x 93.82 um (247,148 um^2) | **2634.28 x 57.07 um (150,338 um^2)** | height -39%, area -39% |
| Top-level Metal2 tracks used | 71 (one per net) | **22** | -69% |
| Routing band height | ~53.25 um (71 x 0.75 um pitch) | **~16.5 um** (22 x 0.75 um pitch) | -36.75 um |
| Divider chain + lock detector | 0.2546 mm^2 | **0.1578 mm^2** | -38% |
| Whole-chip re-summed overrun (`PLL-FLOORPLAN.md` section 5) | ~2.9x | **~2.0x** | still an overrun, smaller |
| `skeleton.total_extent_um2()` | ~1.19e6 um^2 | **~1.09e6 um^2** | -8% |

DRC and LVS are unaffected by this change in the sense that matters most --
both are still clean, at the new footprint:

```
$ python3 -m layout.pll_top.divider_chain.divider_chain --outdir <workdir>
footprint : 2634.280 x 57.070 um  (150338.4 um^2)

$ python3 layout/run_pv.py drc <workdir>/divider_chain.gds \
      --top divider_chain --run-dir <rundir>
DRC clean: divider_chain (D), 0 violations

$ python3 layout/run_pv.py lvs <workdir>/divider_chain.gds <workdir>/divider_chain.spice \
      --top divider_chain --run-dir <rundir>
LVS match: divider_chain (D) layout == schematic
```

Artifacts (re-committed here, replacing #310's committed copies -- same
convention `layout/evidence/vco-layout/PROOF-fold.md` used for its own
changed-cell artifacts): `divider_chain.gds`, `divider_chain.spice` (**byte-
for-byte unchanged** -- `reference_netlist()` derives purely from this
package's net tables, not from drawn geometry, so no LVS-reference content
changed here), `drc-clean/drc.stdout.log`,
`drc-clean/divider_chain_main.lyrdb`, `lvs-clean/lvs.stdout.log`,
`lvs-clean/divider_chain.cir` (extracted -- still **226 `pfet_03v3` + 226
`nfet_03v3` = 452 devices**, unchanged from #310), `lvs-clean/divider_chain.lvsdb`.

| | |
|---|---|
| Generated | 2026-09-09 |
| Branch point | `origin/main` @ `155f062` (#310/PR #342 landed) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| KLayout (pip wheel, geometry generation) | same install used for `--outdir` build |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D`, `--lvs_sub=VSS` |

## What changed, and why it is safe

`layout/pll_top/divider_chain/devgen.py` gains one new function,
`pack_tracks()`, alongside the existing `NetTracks` class (left completely
unmodified -- every other composite in this package, `div23_cell.py`'s and
`dff_tg_3v3.py`'s own `build()`, still calls `NetTracks` exactly as before,
so neither of those two modules' generated GDS is touched by this change at
all). `divider_chain.py`'s own top-level `build()` is the only caller
switched over:

```python
# before (issue #310):
tracks = NetTracks(base_y=base_y)
for net, pads in nets.items():
    route_net(canvas, net, pads, tracks.get(net))

# after (issue #341):
track_y = pack_tracks(nets, base_y=base_y)
for net, pads in nets.items():
    route_net(canvas, net, pads, track_y[net])
```

`route_net()`/`_riser()` (the actual Metal1-pad -> Via1 -> Metal2 -> Via2 ->
Metal3-riser -> Via2 -> Metal2-bus wiring for one net) are **completely
unchanged** -- `pack_tracks()` only changes *which* `track_y` value gets
handed to `route_net()` for each net, reusing a `track_y` across nets whose
drawn extents do not collide instead of manufacturing a fresh one for every
net regardless.

### The algorithm: left-edge interval packing, not a heuristic

This is the same *track assignment* step a real channel router performs (the
routing itself -- Metal1 straps, Metal2 buses, Metal3 risers -- is unchanged;
nothing here is a channel router, only its track-assignment sub-problem):

1. For every net, compute the x-extent its own drawn Metal2 geometry actually
   occupies at `track_y` -- not just `route_net()`'s own bus rectangle
   (`x_lo - METAL2_WIRE_WIDTH_UM/2 .. x_hi + METAL2_WIRE_WIDTH_UM/2`), but the
   wider of that and each end riser's own Via2/Metal2 landing square
   (`_riser()`'s `half_m3_top = VIA2_SIZE_UM/2 + VIA_ENCLOSURE_UM` = 0.22 um,
   wider than half the bus wire's own 0.34 um width, 0.17 um) -- so the two
   outermost pads' own landing squares, which are what actually reach
   furthest at the extreme ends, are never underestimated.
2. Sort nets by increasing left edge (ties broken by name, for determinism).
3. Walk the sorted list; place each net on the first already-open track whose
   most recently placed net's right edge clears this net's own left edge by
   at least `METAL2_TRACK_PITCH_UM - METAL2_WIRE_WIDTH_UM` (0.41 um -- the
   same margin `NetTracks` already used *between* tracks in y, reused here as
   the required x-direction gap between two different nets' bus rectangles
   sharing one track); open a new track only if none does.

This greedy "first-fit by left edge" assignment is a textbook result for
interval graphs: it always uses the *minimum* possible number of tracks (the
maximum number of nets whose extents mutually overlap at any single x,
i.e. the interval graph's own clique number) -- not a heuristic that might
leave packing opportunity on the table, the provably optimal answer to this
1-D placement sub-problem.

### Why sharing a track cannot introduce a same-layer collision

Two different nets sharing one `track_y` only ever risk a Metal2-layer
collision at that shared y -- and `pack_tracks()`'s own clearance check (step
3 above) is built directly from each net's own *true* physical extent (step
1), including the riser landing squares that `route_net()`'s own bus
rectangle alone would underestimate. Two other potential collision classes
were checked and ruled out, not merely assumed clear by construction:

* **Metal3 riser-to-riser, different nets, same x.** Risers run the long
  vertical distance on Metal3 (`_riser()`'s own docstring), which is why a
  net's own Metal3 riser can freely cross an *unrelated* net's Metal2 bus at
  a different x with no via and no short. Two *different* nets' Metal1 pads
  landing at (or near) the same x is a pre-existing risk this package's
  routing fabric already defuses independently of which track_y either net
  gets -- `divider_chain.py`'s own per-column, per-role
  (`GATE_REF_DX_UM`/`CHANNEL_REF_DX_UM`) net-offset scheme (inherited from
  `div23_cell.py`, both documented in their own module docstrings) already
  guarantees at least `NET_OFFSET_STEP_UM` (0.7 um) of x-separation between
  any two distinct nets' pads within one column, well over the 0.41 um
  clearance `pack_tracks()` itself uses. Track sharing does not change that
  guarantee at all -- it only decides which y two *already x-separated* nets'
  buses land on.
* **Via1/Metal2 landing pad at a net's own pad y (not at `track_y`).** Each
  riser's near-pad end also draws a small Via1/Metal2 landing square, but at
  that pad's own y -- unrelated to which `track_y` value the net's far end
  gets, so track reuse changes nothing about this collision class either.

### The result, verified against the property that actually matters

The proof that this reasoning holds is the same PDK signoff DRC/LVS decks
every other increment in this repository uses, at the new, smaller
footprint -- not a re-derivation trusted on inspection alone. Both are clean
(see "Result" above), and LVS in particular is the check that would catch a
same-layer merge this reasoning missed: two nets whose buses actually
touched at a shared `track_y` would extract as one shorted node, which
`design/netlist/divider_chain.spice`'s own 71-named-net structure (unchanged
by this increment -- `reference_netlist()` is untouched) would immediately
flag as a mismatch. It did not.

## Six identical `div23_cell` instances -- still true, re-checked

#295's acceptance criterion (the six instances must stay byte-identical) is
unaffected by this change in principle -- `pack_tracks()` only touches this
block's own top-level routing pass, drawn *after* the six instances are
placed and flattened, never their own interior geometry -- and is re-checked
the same way #310's own evidence did: `layout/tests/test_divider_chain.py`'s
`test_six_div23_instances_are_laid_out_identically` clips each instance's own
window, translates it to a common origin, and XORs it against instance 0's,
on every device layer (`comp`, `poly2`, `nplus`, `pplus`, `nwell`, `contact`,
`metal1`). Still passes -- empty XOR on every layer, unchanged from #310 (this
increment never touches any of those layers inside an instance's own window;
only metal2/via1/via2/metal3 above the instances, and this test's own device
layer list already excludes those on purpose, per that test's own docstring).

## What this does not fix

* **The block's width.** Six `div23_cell` instances placed side by side plus
  46 glue-logic columns is unchanged; the block's width is still the sum of
  every sub-cell's width, and on its own the block (0.1503 mm^2) is still
  just over the entire 0.15 mm^2 die target.
* **The remaining whole-chip overrun.** `PLL-FLOORPLAN.md` section 5.2's own
  arithmetic still shows ~2.0x against the < 0.15 mm^2 draft budget (down from
  ~2.9x at #310) -- an improvement, not a close.
* **The row fold itself.** #310's own record explained why a naive fold did
  not pay off *before* this fix existed: with one track per net, folding
  trades width for height at roughly constant area, since every new row would
  still want its own full-width band. This fix removes that precondition (a
  row's own track count now scales with how many *locally-colliding* nets it
  introduces, not its total net count), which is what makes a future fold
  worth attempting -- but the fold itself (re-deriving the six instances'
  placement grid, the glue logic's own layout, and re-proving #295's
  "identical instances" criterion for however many rows result) is a
  materially larger piece of work than this routing-fabric change, filed
  separately as issue #344 rather than attempted in the same pass.
* **Device density.** The diffusion-island-per-device convention costs this
  block ~547 um^2/transistor against `lock_detector`'s ~187 um^2 for the same
  PDK/flavour -- untouched here, and shares its own follow-up scope with the
  VCO's residual overrun (`layout/evidence/vco-layout/PROOF-fold.md`'s "What
  is still not proved" section).

## klayout-tools friction: none new

Per this repository's friction protocol (`CLAUDE.md`), a genuine `klt`
capability gap hit while drawing real geometry gets filed generically on
`2AMLogic/klayout-tools`. This increment hit none: `pack_tracks()` is plain
Python (an interval-scheduling assignment over floats), calling no KLayout
API at all -- the only KLayout-touching code in this change is the unmodified
`route_net()`/`_riser()` it feeds, already proven out at #308/#309/#310.
