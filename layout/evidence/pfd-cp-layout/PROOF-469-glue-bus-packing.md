# `cp_output_stage`'s glue bus, packed — and why the floor is 13 tracks, not 9 (issue #469)

`PROOF-455-fold.md` closed with a 9,744 µm² residual between `pfd_cp` as drawn
(26,665 µm²) and its re-derived geometric ceiling (16,921 µm²), and sized the
first of two levers inside it: `cp_output_stage`'s glue bus gives each of 14
nets a dedicated Metal2 track where "the interval graph's own clique number is
9", worth **3.75 µm of block height (≈1,290 µm²)**.

This record is what executing that lever produced, and a correction to its
sizing that is the point of the record rather than a footnote.

| | before | after | Δ |
|---|---|---|---|
| `pfd_cp` `footprint` tuple | 347.410 × 76.225 µm (26,481.33 µm²) | **347.410 × 75.475 µm (26,220.77 µm²)** | **−261 µm², −1.0 %** |
| `pfd_cp` committed GDS bbox | 344.98 × 77.30 µm (26,665 µm²) | **344.98 × 76.55 µm (26,406 µm²)** | **−259 µm², −1.0 %** |
| `cp` committed GDS bbox | 344.98 × 74.30 µm (25,630 µm²) | 344.98 × 73.55 µm (25,372 µm²) | −259 µm² |
| `cp_output_stage` committed GDS bbox | 128.75 × 66.20 µm (8,523 µm²) | 128.75 × 65.45 µm (8,426 µm²) | −97 µm² |
| glue-bus tracks | 14 | **13** | −1 |
| `pfd_cp` flat Metal2 track census | 57 | 56 | −1 |
| `pfd_cp` fill | 22.9 % | 23.0 % | +0.1 pp |

Reproduce: `python3 -m pfd_cp.block --outdir <workdir>` (from
`layout/pll_top/`), `python3 layout/run_pv.py area`.

## The change

One substitution, in the router this block family shares:
`cp_array._route_side()` assigns its Metal2 channel with `NetTracks` (a fresh,
never-reused `track_y` per net) or, when a caller passes `bus_reach`, with the
new `cp_array.pack_tracks()` — the same left-edge interval-graph track
assignment `divider_chain/devgen.py` has carried since #341 and reused one
level down at #454. `cp_output_stage.build()` is the one call site that passes
it; `cp_array.build()`'s own two array channels still pass nothing and are
byte-identical (below).

Nothing else moved. No device, no riser column, no link column, no pin, no
pad. The only quantity that changed is which `track_y` each glue net's bus
sits at, and therefore how tall the band is.

### `bus_reach` is a safety precondition, not a tuning knob

`cp.py`'s module docstring records four routing designs that failed before the
one that held, and three of the four failed on the same class of defect: metal
belonging to one net arriving where another net's metal already is. Putting
two nets on one `track_y` is exactly that class of change, so the packing has
to know about every Metal2 shape that will *ever* be drawn at that y — not
just the ones `_route_side` itself draws.

The shapes it does not draw are this block's own. `cp_output_stage.build()`
links each net it shares with the array to a Metal3 link column beside the
block, and reaching that column means extending the glue-bus track sideways
(`_extend_bus`). A net packed onto a shared track and *then* extended through
its track-mate is a cross-net Metal2 merge: one legal polygon to the DRC deck,
a short to everything else, and invisible to both. So:

* `glue_bus_reach()` (pure arithmetic, unit-tested with no PV environment)
  turns the two link-column dicts into `net -> [every x this block will extend
  that net's bus to]`, and `build()` allocates those columns **before**
  routing so the packing and the link loop consume the identical dicts;
* `cp_array.check_track_separation()` re-proves the result *after* the link
  loop, against the x values the loop really drew rather than the ones it
  declared — so an extension added later without updating the declaration
  fails the build instead of drawing the short.

## The sizing was wrong, and the measurement says why

**#455 measured the clique on the bus spans alone.** Nine of the fourteen glue
nets are live at x = 22.41 if you look only at the Metal2 each net's own
risers span. But six of the fourteen — `VDD`, `VSS`, `B0`, `B0B`, `B1`, `B1B`
— are shared with **both** array polarities, so this block extends each of
them to a left column *and* a right column. Each is therefore live across the
block's entire width, and can share a track with nothing at all.

| | clique number | achievable tracks |
|---|---|---|
| bus spans only (what #455 measured) | 9 | 9 |
| **bus spans + this block's own link extensions** | **13** | **13** |
| as drawn before (`NetTracks`) | — | 14 |

`pack_tracks()` achieves 13, which is the clique number, which for an interval
graph is the provable minimum — the left-edge algorithm is optimal here, so
the shortfall is not slack in the assignment. The extension-aware figure is
the real one: the six full-width nets are the wire that ties the two
polarities' rails and trim bits together, which is precisely the job
`cp_output_stage` exists to do (its own docstring: "that column region is also
what ties the two polarities' trim nets together for the first time").

The remaining seven of the thirteen are the local clique at x ≈ 22–31 (`DN`,
`VOUT`, `DNB`, `VDUMP`, `UPB`, `UP`, `UPT`), and the one pairing packing does
find is `DNT` (x ∈ [−23.01, 1.93] after its left extension) sharing a track
with `UPB` (x ∈ [11.19, 59.43]) — 9.26 µm apart, against the 0.41 µm the
clearance rule requires.

```
track   y        net(s)            track   y        net(s)
  0    43.98     B1B                 7    49.23     DN
  1    44.73     B1                  8    49.98     VOUT
  2    45.48     B0B                 9    50.73     DNB
  3    46.23     B0                 10    51.48     VDUMP
  4    46.98     DNT, UPB           11    52.23     UPT
  5    47.73     VSS                12    52.98     UP
  6    48.48     VDD
```

So: **1 track, 0.75 µm, 259 µm² — 20 % of the 1,290 µm² the lever was sized
at.** The ceiling arithmetic, restated against the achieved outcome:

| | Ceiling (#469 / #455) | Achieved | |
|---|---|---|---|
| Glue-bus packing | 14 → 9 tracks, −3.75 µm (−1,290 µm²) | 14 → **13** tracks, −0.75 µm (−259 µm²) | 20 % of the ceiling |
| `pfd_cp` against its geometric ceiling | 16,921 µm² | 26,406 µm² | gap 9,485 µm² (35.9 % of the block), was 9,744 µm² (36.5 %) |

This is the same class of finding §5.8 recorded for #454 and §5.10 for #455,
for the third time in this family: **a track census taken without the
neighbouring level's own routing obligations over-states what packing can
recover.** #455's own correction was that a *flat* census over five levels
over-states it; this one is that a census over one level's *own* bus spans,
ignoring what its parent draws on the same tracks, does too.

## Why the other two bands in this block gain nothing (measured, not assumed)

`cp_array._route_side()` is called three times. Only the glue call is packed,
and the other two were measured rather than skipped:

| Channel | nets | tracks now | packed | binds the block above it? | worth |
|---|---|---|---|---|---|
| `cp_array` N side | 9 | 9 (top y = 21.97) | **7** (top y = 20.47) | no — `cp_array.footprint[3]` = 24.08 is set by the P side, 2.11 µm higher | **0 µm** |
| `cp_array` P side | 9 | 9 (top y = 24.08) | **9** (unchanged) | yes | **0 µm** |
| `cp_output_stage` glue bus | 14 | 14 | **13** | yes | **0.75 µm** |

The P channel does not pack *at all*, and the reason generalises: `cp_output_stage`
extends 7 of the P side's 9 buses rightward to its own link columns, so those
7 all overlap out at the column region and form a 7-clique; the remaining two
(`IBP`, `ICP` — the block's private bias pins, which `cp.py` reaches by rising
at the bus's own edge rather than extending it) span x ∈ [30.22, 72.83] and
[35.29, 80.22], overlapping every one of the 7. Clique 9, nets 9.

**A band every one of whose nets is reached by a parent from the same side
cannot be packed**, because every such net's extent runs out to that side's
link-column region. That is now stated in `cp_array.py`'s own "track *reuse*"
section, so the next reader does not have to re-measure it.

Packing the N channel anyway would have changed `cp_array`'s committed GDS —
a fifth artifact, with its own DRC claim — for zero block area. It is not
done, and `test_gds_reproducibility.py` proves `cp_array.gds`, `cp_dumpbuf.gds`,
`cp_leg_n/p.gds`, `pfdcp_inv_3v3.gds` and `pfd.gds` all still reproduce
byte-for-byte.

## The `cp_dumpbuf` fold was decided, and decided against

#469 required the two residual targets to be **decided together, not
sequenced**, because they are mutually exclusive. They were. Target 2 —
folding `cp_dumpbuf`'s 25.87 µm routing band over its own 11.20 µm of device
bands — is **not pursued**, and the reasoning is arithmetic rather than
preference:

1. **It cannot pay `pfd_cp` anything on its own.** `cp_dumpbuf` is
   211.10 × 36.00 µm sitting beside `cp_output_stage`, which is 65.45 µm tall
   and is what sets `cp`'s height. Height won inside the dump buffer comes off
   a block that is already 29 µm shorter than its neighbour; `cp`'s bbox does
   not move.
2. **It only pays in combination with a `cp_dumpbuf` fold at `cp` level — and
   that band is occupied.** The 217.10 × 38.72 µm band above `cp_dumpbuf` is
   exactly where #455 put `pfd`, and #455 measured that arrangement as worth
   8,616 µm². Reclaiming it for a folded dump buffer means giving that back
   and re-widening `pfd_cp` to 434.31 µm. The fold that already landed is
   worth 33× what this one could be.
3. **So the exclusivity resolves in favour of the merged fold**, and target 2
   is closed rather than deferred. It is not "not done yet": it is
   *foreclosed* for as long as `pfd` lives in that band, which is a property
   of the geometry, not of scheduling. If a future pass ever relocates `pfd`,
   this record is where the arithmetic to re-open the question lives.

Stated explicitly here because #469's acceptance criteria require the decision
to be recorded rather than left implicit.

## What the residual actually is now

9,485 µm² between `pfd_cp` as drawn and its 16,921 µm² ceiling, and after this
pass the composition of that residual is measured rather than estimated:

| Component | µm² of block height | packable at this level? |
|---|---|---|
| `cp_output_stage` glue band (13 tracks × 0.75 µm) | 9.75 µm | **no** — at the clique number already |
| `cp_array` N+P channels (18 tracks) | 6.75 µm (P side binds) | **no** — parent-reached from one side |
| `cp`'s backbone band (6 rows) | 4.50 µm | no — all six span the block-to-block gap |
| `pfd_cp`'s trunk band (4 rows) | 3.00 µm | no — all four span glue bus → `pfd` (§5.10) |
| device bands | 49.05 µm | not a routing lever |

The one lever this measurement *does* expose is not a routing lever at all:
the glue band's clique of 13 is 6 structural full-width nets plus a local
clique of 7, and the 7 exist because `cp_output_stage` places its four glue
inverters in one row at the right-hand end, so `DN`/`DNB`/`UP`/`UPB` each run
most of the block's width from a switch on the left to an inverter on the
right. Interleaving the inverters with the switches they drive would shorten
all four. That is a *placement* change, not a track assignment one, so per
§5.5's one-lever-per-PR discipline it is filed as **issue #473** rather than
folded in here — with the caveat that it may well measure out at zero, since
the floor is the 6 full-width nets plus whatever local clique survives, and
nothing guarantees interleaving takes that below 7.

## Verification

Every check each changed block carried is re-run against the new geometry.

```bash
python3 -m pfd_cp.cp_output_stage --outdir <workdir>   # (from layout/pll_top/)
python3 -m pfd_cp.cp             --outdir <workdir>
python3 -m pfd_cp.block          --outdir <workdir>
python3 layout/run_pv.py drc layout/evidence/cp-layout/cp_output_stage.gds --top cp_output_stage --run-dir <rundir>
python3 layout/run_pv.py drc layout/evidence/cp-block-layout/cp.gds --top cp --run-dir <rundir>
python3 layout/run_pv.py drc layout/evidence/pfd-cp-layout/pfd_cp.gds --top pfd_cp --run-dir <rundir>
python3 layout/run_pv.py drc layout/evidence/pfd-cp-layout/pfd_cp.gds --top pfd_cp --run-dir <rundir> --offgrid
python3 layout/run_pv.py lvs layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.spice --top pfd_cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_output_stage` DRC, table `main` | clean | `DRC clean: cp_output_stage (D), 0 violations` | **PASS** |
| `cp` DRC, table `main` | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main` (default) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` LVS, deck verdict | match | `LVS match: pfd_cp (D) layout == schematic` | **PASS** |
| `pfd_cp` net count, layout vs. reference | equal | 92 / 92 | **PASS** |
| `pfd_cp` device count, layout vs. reference | equal | 168 / 168 | **PASS** |
| `netcheck.check_gds()` on `cp_output_stage` | no shorts, no splits | `connectivity clean: 18 nets, no shorts, no splits` | **PASS** |
| `netcheck.check_gds()` on `cp` | no shorts, no splits | `connectivity clean: 22 nets, no shorts, no splits` | **PASS** |
| `netcheck.check_gds()` on `pfd_cp` | no shorts, no splits | `connectivity clean: 76 nets, no shorts, no splits` | **PASS** |
| `layout/tests` suite | pass | 746 tests, all passing (744 when this record was first written; #472/DR-016 added the two `WholeChipAreaRowTests`, which pass on this geometry) | **PASS** |

**The #448 label regression was watched for, as #469 required.**
`_canvas.Canvas.clear_inherited_labels()` has four call sites, and `cp_array`
is one of them. All four are untouched by this change — `cp_array.build()`,
`cp_output_stage.build()`, `cp.build()` and `block.build()` each still call it
immediately after their own composing `flatten()`, and this change draws no
label and moves no pin. `test_pfdcp_block_layout.py`'s `PinLabelTests` still
assert the finished GDS carries exactly the 13 boundary-pin labels
(`UP`/`DN` on 36/10, the other eleven on 34/10) and that none of
`{EN, ENB, VBN, VBP, VCASCN, VCASCP, TAIL, UPT, DNT, VREF, B0B, B1B}`
survives; the LVS run above is the end-to-end proof (a stray inherited label
breaks the deck's global substrate merge and mismatches every n-channel bulk,
which is what #448 was).

**The reference netlist was not touched.** `block.reference_netlist()` is
still the mechanical flattening of the frozen `design/pfd_cp.sch` export, and
`test_pfdcp_block_layout.py` asserts its output is byte-identical to the
committed `lvs-clean/pfd_cp.spice`. This is a geometry change.

**No routing design was invented.** Every riser, every link column, every
Metal3 vertical and every bus extension is drawn by the same four functions,
at the same x, as before this change. What moved is one `track_y` per net.
The one new hazard a shared track creates — two nets' Metal2 at the same y —
is the one `pack_tracks()`'s clearance and `check_track_separation()`'s
post-hoc re-proof exist for, and the `--offgrid` signoff DRC run is the
independent check that they are right.

## What else moved, and why

| Artifact | Change | Re-verified |
|---|---|---|
| `layout/evidence/cp-layout/cp_output_stage.gds` | the packed glue band: 66.20 → 65.45 µm | DRC `main` clean; `netcheck` clean (18 nets); `drc-clean/` and `connectivity/` regenerated |
| `layout/evidence/cp-block-layout/cp.gds` | inherits the 0.75 µm: 74.30 → 73.55 µm | DRC `main` clean; `netcheck` clean (22 nets); `drc-clean/` and `connectivity/` regenerated |
| `layout/evidence/pfd-cp-layout/pfd_cp.gds` | inherits the 0.75 µm: 77.30 → 76.55 µm | DRC `main` clean, `--offgrid` clean, LVS match; all three regenerated |
| `layout/evidence/floorplan-skeleton/pll_floorplan_skeleton.gds` | `skeleton.PFD_CP_STANDALONE_H_UM` is the recorded standalone footprint, so the rectangle shrinks with the block (76.23 → 75.48 µm) | regenerated; `test_gds_reproducibility.py` rebuilds it from `floorplan.skeleton` on every run |
| `layout/evidence/area-audit/area-audit.md` | machine-rendered from the committed GDS files; `test_area_audit.py` fails if it goes stale | regenerated via `python3 layout/run_pv.py area --out …` |
| `layout/floorplan/PLL-FLOORPLAN.md` | §5.11 | — |

`cp_array`, `cp_dumpbuf`, `cp_leg_n`, `cp_leg_p`, `pfdcp_inv_3v3` and `pfd` are
**not** touched — `test_gds_reproducibility.py` rebuilds all 26 committed
block GDS files and XORs them layer by layer against what is committed, so an
unintended change to any of them fails the suite rather than riding along.

## Provenance

| | |
|---|---|
| Run | 2026-09-22 |
| Branch point | `origin/main` @ `62ceb087` |
| Invoked as | `python3 -m pfd_cp.block --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc` / `lvs`, PDK/KLayout/PV-python resolved per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D` (default `--lvs_sub=VSS`) |

## Artifacts

| Path | What it is |
|---|---|
| `pfd_cp.gds` | the assembled block at its new height |
| `drc-clean/pfd_cp_main.lyrdb`, `drc-clean/drc.stdout.log` | DRC, default run |
| `drc-clean-offgrid/pfd_cp_main.lyrdb`, `drc-clean-offgrid/drc.stdout.log` | DRC, `--offgrid` (signoff-grade) run |
| `lvs-clean/lvs.stdout.log`, `lvs-clean/pfd_cp.cir`, `lvs-clean/pfd_cp.lvsdb` | LVS against the unchanged `lvs-clean/pfd_cp.spice` |
| `connectivity/pfd_cp.netcheck.log` | `netcheck.check_gds()` summary and per-net component breakdown |
| `../cp-layout/`, `../cp-block-layout/` | the same set for `cp_output_stage` and `cp` |

`lvs-attempt/` — the mismatch this block's first block-level LVS run really
found (#440) — is untouched, as `test_pfdcp_block_layout.py::LvsEvidenceTests`
requires.
