# `divider_chain` block — packing the `div23_cell` macro's own track band (issue #454)

Third area increment on this block, and companion to
[`PROOF.md`](PROOF.md) (#310, the DRC/LVS-clean assembly),
[`PROOF-track-packing.md`](PROOF-track-packing.md) (#341, packing the
*top-level* track band) and [`PROOF-fold.md`](PROOF-fold.md) (#344, folding the
one row into two).

`PLL-FLOORPLAN.md` §5.5 and `layout/evidence/area-audit/PROOF.md` (issue #442)
sized this block's remaining lever at 60,006 µm² — the whole-block Metal2
track population (73 distinct tracks) packed solid at the 0.75 µm pitch into
54.75 µm of height, against the 100.29 µm drawn. **This increment takes
39,530 µm² of that, 65.9 % of the estimate, and it does so by a different
mechanism than the estimate assumed.** The estimate's residual is still
available and is filed as **#458** rather than claimed here.

## Result

| | Before (#344, PR #345) | After (this increment) | Delta |
|---|---|---|---|
| `divider_chain` footprint | 1317.66 x 100.29 µm (132,148 µm²) | **1317.66 x 70.29 µm (92,618 µm²)** | height **−29.9 %**, area **−29.9 %** |
| `div23_cell` footprint | 332.14 x 37.80 µm (12,555 µm²) | **332.14 x 22.80 µm (7,573 µm²)** | height **−39.7 %** |
| `div23_cell` Metal2 tracks | 31 (one per net) | **11** | −64.5 % |
| Distinct Metal2 tracks, whole block | 73 | **43** | −30 |
| `divider_chain` fill | 21.2 % | **26.5 %** | +5.3 pp |
| Whole-chip sum (`PLL-FLOORPLAN.md` §5.8) | 0.2437 mm² → 0.3046 mm² after ×1.25 | **0.2041 mm² → 0.2552 mm²** | **2.03× → 1.70×** over the 0.15 mm² target |

Both blocks are re-verified at the new geometry — DRC clean, LVS matched, and
for the first time on this block DRC clean under `--offgrid` as well:

```
$ python3 -m layout.pll_top.divider_chain.div23_cell --outdir <workdir>/div23
$ python3 -m layout.pll_top.divider_chain.divider_chain --outdir <workdir>/chain

$ python3 layout/run_pv.py drc <workdir>/div23/div23_cell.gds \
      --top div23_cell --run-dir <rundir>
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
replacing #344's and #309's copies (the convention
[`PROOF-track-packing.md`](PROOF-track-packing.md) and
`layout/evidence/vco-layout/PROOF-fold.md` already use for changed-cell
artifacts): `divider_chain.gds`, `div23_cell.gds`, both `drc-clean/` pairs,
both `lvs-clean/` triples. **Both `.spice` reference netlists are byte-for-byte
unchanged** — verified by `diff` against the previously committed copies —
because `reference_netlist()` in each module derives from that package's net
tables and never from drawn geometry. The extracted `divider_chain.cir` still
carries **226 `pfet_03v3` + 226 `nfet_03v3` = 452 devices**.

| | |
|---|---|
| Generated | 2026-09-21 |
| Branch point | `origin/main` @ `c357e13` (#442/PR #457 landed) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.10` — see "On the KLayout version" below |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D`, `--lvs_sub=VSS` |

## Estimate before the change, compared against the outcome

#454's own sizing, restated (it is the acceptance criterion this section
answers):

```
73 distinct Metal2 tracks x 0.75 um pitch = 54.75 um packed floor
device bands                              = 26.32 um
height floor = max(54.75, 26.32)          = 54.75 um   (drawn then: 100.29)
1317.66 x 54.75                           = 72,142 um2 (drawn then: 132,148)
                                            ----------
ceiling saving                              60,006 um2 = -45.4 % of the block
```

Achieved:

```
1317.66 x 70.29                           = 92,618 um2
                                            ----------
actual saving                               39,530 um2 = -29.9 % of the block
                                                       = 65.9 % of the ceiling
                                                       = 32.0 % of the whole-chip
                                                         123,660 um2 area gap
```

**Where the other 34.1 % went, and why that is not a shortfall in this
change.** The ceiling assumed a single flat plane of 73 tracks that could be
packed against each other and hidden over the device rows. Neither assumption
holds as stated:

1. The 73 tracks are not one population. They live at three levels of a
   hierarchy (`dff_tg_3v3` inside `div23_cell` inside `divider_chain`), and
   packing is only ever possible *within* one level — two different levels'
   bands cannot interleave, because the outer level places the inner one as an
   opaque box.
2. Hiding a track over a device row is a genuinely separate, riskier change
   (below), not a free consequence of packing.

What this increment does is drain the largest of those three bands. What it
leaves is the second assumption, intact and still worth taking.

## What changed

One call site, in `div23_cell.py`'s `build()` — the identical substitution
#341 made one level up:

```python
# before (issue #309):
tracks = NetTracks(base_y=nwell_box[3] + 3.0)
for net, pads in nets.items():
    route_net(canvas, net, pads, tracks.get(net))

# after (issue #454):
track_y = pack_tracks(nets, base_y=nwell_box[3] + 3.0)
for net, pads in nets.items():
    route_net(canvas, net, pads, track_y[net])
```

`route_net()` / `_riser()` — the actual Metal1-pad → Via1 → Metal2 → Via2 →
Metal3-riser → Via2 → Metal2-bus wiring — are untouched, as is `pack_tracks()`
itself. Only *which* `track_y` each net is handed changes.

### Why the macro's band, not the top-level one, was the cost

§5.5 measured 73.97 µm of the block's 100.29 µm height as containing no
diffusion, and attributed it to the top-level track fabric. The measurement is
right; the attribution was not. Instrumenting every `pack_tracks()` call in one
`divider_chain.build()` gives the real split:

| Term | Height (µm) | Share of 100.29 µm | How derived |
|---|---|---|---|
| devices (`comp`), both rows | 26.32 | 26.2 % | `run_pv.py area`'s coalesced diffusion band |
| **`div23_cell`'s own band, ×2 rows** | **46.50** | **46.4 %** | 31 nets × 0.75 µm, once per row |
| `divider_chain`'s own packed bands | 16.50 | 16.5 % | 12 and 10 tracks × 0.75 µm (already packed at #341/#344) |
| wells, taps, band base gaps, bbox margin | 10.97 | 10.9 % | remainder |

The top-level band was only 16.50 µm of the 73.97 — because #341 had already
packed it. The macro's band was 46.50 µm and had not been packed at all, and
it is paid **once per `ROW_PLAN` row**, because each row's height is gated by
the `div23_cell` instance standing in it. That is why a one-line change at the
macro level moves the block twice as much as the same change at the top level
did.

### 11 tracks is the optimum, not a good result

`pack_tracks()` is left-edge interval assignment, which is provably optimal for
an interval graph — see `devgen.py`'s own module comment. Checked rather than
assumed: computing the maximum number of the macro's 31 net extents that
mutually overlap at any single x (the interval graph's clique number, which is
a lower bound on any assignment) gives **11**, exactly the number
`pack_tracks()` uses. No smarter assignment exists at this level.

The macro packs well because only six of its 31 nets are wide — `VSS` (327.6
µm), `VDD` (327.5), `MODOUT` (313.8), `MODIN` (192.0), `CKIN` (158.0) and `QB`
(145.4) — against a 332.14 µm macro width. The other 25 are local to one or two
adjacent device columns, which is the regime `pack_tracks()` exists for.

### Band arithmetic

```
base_y = nwell_box.top + 3.0     = 14.78 um  (unchanged)
NetTracks : 31 tracks x 0.75     = 23.25 um  -> top 37.50 um
pack_tracks: 11 tracks x 0.75    =  8.25 um  -> top 22.50 um
                                   --------
per instance                       15.00 um
x 2 ROW_PLAN rows                  30.00 um  -> block 100.29 -> 70.29 um
```

## What this does not fix

**The tracks are packed but still above the cells.** After this change the
block's 43 remaining distinct Metal2 tracks occupy 43.97 µm of no-diffusion
band sitting above 26.32 µm of device rows, and the Metal2 plane over those
device rows is still **1.0 % occupied** (`run_pv.py area`). §5.5's lever-3
framing — put the band in the plane over the cells — is therefore untouched and
still worth, at its own ceiling, 70.29 → 32.25 µm of height (1317.66 × 32.25
= 42,494 µm², a further −50,124 µm² — 60 % of the remaining 84,129 µm² gap).

It is deliberately not attempted here. Packing changes only a `track_y`
*value*, and every net's drawn geometry stays in a band that provably contains
nothing else; moving a track down into the device band means a bus can run
through another net's own Metal2 riser landing square, which is the
`M2.2a`/`V1.1`/`V2.1` failure class `cp.py`'s module docstring records four
separate attempts against. It is filed as **#458**: one lever per PR, per
#442's own staged-execution note.

**Taken since, at #458** — see
[`PROOF-over-device-rows.md`](PROOF-over-device-rows.md). The risk named above
is real and was handled by making the *track assignment* obstacle-aware rather
than by moving a bus blind: `devgen.pack_tracks_over_devices()` takes every
riser landing square and every placed instance's own interior Metal2 as an
explicit obstacle map and places each net on the lowest 0.75 µm step that
clears it. `route_net()`/`_riser()` still draw exactly what they drew here.
Outcome: 1317.66 × 70.29 → **1317.66 × 41.99 µm** (92,618 → 55,329 µm²,
−40.3 %), 74.4 % of the ceiling stated above, DRC-clean on both decks and
LVS-matched at both levels.

**Width is unchanged**, as at #341: 1317.66 µm, six `div23_cell` instances plus
46 glue columns in two rows.

## Properties re-proved rather than assumed

- **#295's "six identical `div23_cell` instances"** — re-proved geometrically
  at the new footprint by `test_divider_chain.py`'s
  `test_six_div23_instances_are_laid_out_identically`, the same way #344
  re-proved it across two rows.
- **Both `reference_netlist()` outputs byte-for-byte unchanged** — `diff`
  against the previously committed `.spice` files, zero bytes differing.
- **`div23_cell`'s pin locations and x-extent unchanged** — all seven pins and
  `x0`/`x1`/`y0` are identical to the values
  `layout/evidence/divider-div23-proof/PROOF.md` recorded; only `y1` moves,
  37.50 → 22.50. That is what makes this a pure routing-fabric change and
  is asserted by `test_divider_div23.py`.
- **`skeleton.DIVIDER_CHAIN_STANDALONE_H_UM`** updated to 70.29 and cross-checked
  against a live rebuild by `test_floorplan_skeleton.py`'s
  `test_divider_chain_recorded_footprint_matches_the_generator`, so the
  no-KLayout floorplan view cannot drift from the generator.
- Full suite: `python3 -m unittest discover -s layout/tests -t layout/tests`,
  691 tests, OK.

## On the KLayout version

`layout/README.md`'s "KLayout version pin" note records that a KLayout newer
than the `0.28.16` pin has been observed to report a *false* `LVS mismatch` on
an otherwise LVS-clean `divider_chain` (issue #360). This evidence was captured
on `KLayout 0.30.10`, and **both LVS runs above returned a match, not a
mismatch** — so the known failure mode did not fire here and there is nothing
to discount. The DRC verdicts are on the same binary, which that note records
as unaffected either way.
