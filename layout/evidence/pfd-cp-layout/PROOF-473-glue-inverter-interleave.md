# `cp_output_stage`'s glue inverters, interleaved with the switches they drive — 13 tracks to 10 (issue #473)

`PROOF-469-glue-bus-packing.md` packed this block's glue bus onto **13** Metal2
tracks for 14 nets, which is that band's interval-graph clique number and
therefore the provable minimum *for a track-assignment change*. Its closing
section decomposed the 13 and named what the remaining slack actually was:

```
13 = 6 structural full-width nets + a local clique of 7
```

— and the 7 existed because the row placed all six switches left to right and
then all four glue inverters in one group past the right-hand end, so each
inverter sat 34–82 µm from the gate it drives. That is a **placement**
property, filed separately as this issue per `PLL-FLOORPLAN.md` §5.5's
one-lever-per-PR discipline, and explicitly filed with the caveat that "it may
well measure out at zero".

It does not. The clique goes **13 → 10**.

| | before | after | Δ |
|---|---|---|---|
| glue-bus tracks (14 nets) | 13 | **10** | **−3** |
| `cp_output_stage` `footprint` tuple | 130.310 × 65.975 µm (8,597.20 µm²) | **130.310 × 63.725 µm (8,304.00 µm²)** | −293 µm² |
| `cp_output_stage` committed GDS bbox | 128.75 × 65.45 µm (8,426 µm²) | **128.75 × 63.20 µm (8,136 µm²)** | −290 µm² |
| `cp` committed GDS bbox | 344.98 × 73.55 µm (25,372 µm²) | **344.98 × 71.30 µm (24,595 µm²)** | −777 µm² |
| `pfd_cp` `footprint` tuple | 347.410 × 75.475 µm (26,220.77 µm²) | **347.410 × 73.225 µm (25,439.10 µm²)** | −782 µm² |
| `pfd_cp` committed GDS bbox | 344.98 × 76.55 µm (26,406 µm²) | **344.98 × 74.30 µm (25,630 µm²)** | **−776 µm², −2.9 %** |
| `pfd_cp` flat Metal2 track census | 56 | 53 | −3 |
| `pfd_cp` fill | 23.0 % | 23.5 % | +0.5 pp |

Reproduce: `python3 -m pfd_cp.block --outdir <workdir>` (from
`layout/pll_top/`), `python3 layout/run_pv.py area`.

## The change

One constant, and the placement function that reads it:

```python
ROW_ORDER = ("xi_dn", "MSWDN", "MDMPDN", "MDUMN",
             "xi_up", "MSWUP", "MDMPUP", "MDUMP",
             "xi_b0", "xi_b1")
```

Each steering pair's own inverter now sits immediately **before** the switch
group whose gates it feeds. `xi_b0`/`xi_b1` stay at the row's right-hand end,
because `B0`/`B0B`/`B1`/`B1B` are shared with both array polarities and are
live across the block's whole width wherever the cells sit — moving them buys
nothing and is not done for tidiness.

`switch_row_x()` becomes `row_x()`, which lays out *every* row item rather than
only the six switches, with one gap rule per kind of adjacency. The new one is
`INV_TO_SWITCH_GAP_UM` (7.0 µm, inverter origin → next comp), needed because an
inverter and a switch are asymmetric in the same direction: a
`devgen.mosfet()` and a `pfdcp_inv_3v3` both hang a gate-tab pad *before* their
comp, but an inverter's three escape columns all run 2.0–5.0 µm *after* its
origin, so an inverter followed by a switch needs more room than the reverse.
`check_escape_clearance()` now runs over the whole row instead of once per
group, and proves that arithmetic on every build; the tightest clearance on the
committed row is 0.66 µm (both inverter→switch pairs), against
`METAL1_PAD_MARGIN_UM`'s 0.12 µm floor.

Nothing else about the block's routing design changed. Same riser-column
scheme, same `check_riser_columns()` identity invariant, same three escape
columns per inverter, same `_escape()` for a switch whose diffusions are
different nets, same link-column allocation, same `glue_bus_reach()`
declaration and same `check_track_separation()` re-proof. The reference
netlist is untouched and byte-identical: this is geometry.

## Why the groups stay contiguous, and why that is not a style choice

The obvious next step — dropping `xi_dn` *between* `MSWDN` and `MDMPDN`, so
that both `DN` and `DNB` become a couple of microns long — is not taken, and
the reason is a new invariant rather than caution. `check_row_groups()` raises
unless each switch group occupies one unbroken span of the row, because two of
this block's drawing steps assume exactly that, and neither failure is one a
spacing-based DRC deck can report:

* each group is tapped by a **single** `cp_array._tap_strip()` running from its
  leftmost comp to its rightmost. A glue inverter inside that span sits in the
  *identical* y band (the leaf's own substrate tap and the row's are both
  `TAP_GAP_UM + TAP_SIZE_UM` below the row baseline), so the strip's comp,
  implant and contact row would be drawn straight through the inverter's own —
  overlapping-but-not-identical contact squares, the `CO.1`-class defect this
  module's docstring already records for via stacks;
* the P group is covered by a **single** n-well box spanning its comps and its
  tap strip. An inverter inside that span would have its own NMOS — which sits
  *below* its PMOS, inside the switch row's own y band — enclosed by that
  n-well.

Splitting either the strips or the well per contiguous run is a real option and
a bigger change than this one; it is not needed, because the measurement below
shows the contiguous-group family already reaches the floor that matters.

## The measurement, taken before anything was built

The issue required the clique to be measured on a trial placement before any
geometry was drawn, and to be closed as a null result if it did not improve.
`glue_riser_x()` exists for that: it is the pure-arithmetic twin of the riser
set `build()` draws (`net -> every x at which the row rises to the glue bus`),
so a candidate order can be costed with `cp_array.pack_tracks()` — the same
function the router uses — with no geometry, no PDK and no KLayout.

Because a model that has drifted from the builder would have chosen `ROW_ORDER`
on fiction, the two are pinned to each other:
`test_cp_output_stage.py::test_the_arithmetic_riser_model_matches_what_build_actually_drew`
asserts `glue_riser_x()`'s output equals `build()`'s own drawn `riser_points`,
net for net and x for x.

**All 25,920 legal orderings were costed** (6 N-group permutations × 6 P-group
permutations × 720 arrangements of {N group, P group, `xi_up`, `xi_dn`,
`xi_b0`, `xi_b1`}), and the distribution is the finding:

| tracks | orderings |
|---|---|
| **10** | 1,260 |
| 11 | 3,960 |
| 12 | 9,180 |
| 13 (includes the as-built order before this change) | 6,120 |
| 14 | 5,400 |

`ROW_ORDER` is one of the 1,260 at ten — the most compact of them, and the
one whose row reaches least far right. The sweep is
`test_no_legal_row_order_packs_the_glue_band_below_ten_tracks`, so the claim
"10 is the floor" is re-derived on every test run rather than asserted once
here. (Each ordering keeps the row inside `cp_array`'s own x extent, which the
test also asserts — that is what makes holding the link columns fixed exact.)

## Ten is a floor, not a lucky assignment

`pack_tracks()` achieves the clique number, and for an interval graph the
clique number is the minimum. The clique here is 10, reached at x ≈ 30:

```
track   y        net(s)                         extent (um, link columns included)
  0    43.98    B1B                             [-27.01, 100.74]
  1    44.73    B1                              [-26.01, 101.74]
  2    45.48    B0B                             [-25.01,  98.74]
  3    46.23    B0                              [-24.01,  99.74]
  4    46.98    DNT, UP                         [-23.01,   8.93] [ 18.19, 47.63]
  5    47.73    VSS                             [-22.01,  95.74]
  6    48.48    VDD                             [-21.01,  96.74]
  7    49.23    DN, VOUT                        [-17.81, -10.37] [ -7.01, 49.93]
  8    49.98    DNB, UPB, UPT                   [-15.01,  11.63] [ 20.99, 25.63] [ 28.99, 97.74]
  9    50.73    VDUMP                           [  3.99,  44.93]
```

The 10 = 6 + 4, and the 4 are structural in the same sense the 6 are:

* `VOUT` is `MSWDN`'s drain and `MSWUP`'s — it ties the N group to the P group
  by definition, so it is live everywhere between them;
* `VDUMP` is `MDMPDN`'s drain and `MDMPUP`'s — likewise;
* `UPT` runs from the P group out to its own right-hand link column, because
  `cp_array`'s P side carries it;
* and at whichever P device is not the one bounding `VOUT`, one of `UP`/`UPB`
  is live as well.

No ordering removes any of those, which is why the sweep bottoms out at 10 and
not lower. The remaining slack in this block is no longer in the glue band.

## What the four nets actually did

The issue's own table, re-measured on the built geometry:

| net | glue-bus span before | after | |
|---|---|---|---|
| `DN` | x ∈ [−17.59, 64.41] — **82.0 µm** | x ∈ [−17.59, −10.59] — **7.0 µm** | `MSWDN`'s gate now sits one gap from `xi_dn`'s `A` pin |
| `DNB` | x ∈ [−6.59, 67.21] — **73.8 µm** | x ∈ [−14.79, 11.41] — **26.2 µm** | `xi_dn`'s `Y` escape to `MDUMN`'s gate, across the N group |
| `UPB` | x ∈ [11.41, 59.21] — **47.8 µm** | x ∈ [21.21, 25.41] — **4.2 µm** | `xi_up`'s `Y` escape to `MSWUP`'s gate |
| `UP` | x ∈ [22.41, 56.41] — **34.0 µm** | x ∈ [18.41, 47.41] — **29.0 µm** | still crosses the P group: `MDUMP`'s gate is at its far end |
| **sum** | **237.6 µm** | **66.4 µm** | |

`UP` is the one that barely moves, and the reason is worth stating because it
is the same reason the floor is 10: `UP` gates both `MDMPUP` and `MDUMP`, which
sit at opposite ends of the P group, so it spans that group however the
inverter is placed. `DNB` has the same shape on the N side (`MDMPDN` and
`MDUMN`). Interleaving shortens the *single*-gate nets to nothing and leaves
the multi-gate ones spanning their own group — which is exactly what the
clique arithmetic above says.

## What this does to the block's residual

`PROOF-455-fold.md` re-derived `pfd_cp`'s geometric ceiling at 16,921 µm².

| | residual | share of the block |
|---|---|---|
| after #455 | 9,744 µm² | 36.5 % |
| after #469 | 9,485 µm² | 35.9 % |
| **after this change** | **8,709 µm²** | **34.0 %** |

`PROOF-469`'s own component table, restated:

| Component | µm² of block height | packable at this level? |
|---|---|---|
| `cp_output_stage` glue band (**10** tracks × 0.75 µm) | **7.50 µm** | **no** — at the clique number, and the clique is now structural (above) |
| `cp_array` N+P channels (18 tracks) | 6.75 µm (P side binds) | no — parent-reached from one side |
| `cp`'s backbone band (6 rows) | 4.50 µm | no — all six span the block-to-block gap |
| `pfd_cp`'s trunk band (4 rows) | 3.00 µm | no — all four span glue bus → `pfd` (§5.10) |
| device bands | 49.05 µm | not a routing lever |

Both halves of the glue-band lever are now spent, and the band's height is
6 full-width nets + 4 structural ones, none of which a placement or an
assignment can remove. What is left in this block above its device bands is
three bands that each span a block-to-block gap, and §5.13's finding that a
band can sometimes be routed *over* the device rows instead of above them
(`divider_chain`, #458) is the only class of lever this record can see that
has not been tried here. It is not sized: `cp_output_stage`'s device row is
1.3 µm tall against `divider_chain`'s 26.32 µm, so the obstacle-free y
available over it is a small fraction of what made that lever pay there.

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
python3 layout/run_pv.py drc layout/evidence/floorplan-skeleton/pll_floorplan_skeleton.gds \
  --top pll_floorplan_skeleton --run-dir <rundir>
python3 layout/run_pv.py area --out layout/evidence/area-audit/area-audit.md
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_output_stage` DRC, table `main` | clean | `DRC clean: cp_output_stage (D), 0 violations` | **PASS** |
| `cp` DRC, table `main` | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main` (default) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pll_floorplan_skeleton` DRC, table `main` | clean | `DRC clean: pll_floorplan_skeleton (D), 0 violations` | **PASS** |
| `pfd_cp` LVS, deck verdict | match | `LVS match: pfd_cp (D) layout == schematic` | **PASS** |
| `pfd_cp` net count, layout vs. reference | equal | 92 / 92 | **PASS** |
| `pfd_cp` device count, layout vs. reference | equal | 168 / 168 | **PASS** |
| `netcheck.check_gds()` on `cp_output_stage` | no shorts, no splits | `connectivity clean: 18 nets, no shorts, no splits` | **PASS** |
| `netcheck.check_gds()` on `cp` | no shorts, no splits | `connectivity clean: 22 nets, no shorts, no splits` | **PASS** |
| `netcheck.check_gds()` on `pfd_cp` | no shorts, no splits | `connectivity clean: 76 nets, no shorts, no splits` | **PASS** |
| `layout/tests` suite | pass | 774 tests, all passing | **PASS** |
| `layout/lib/check-layout-status-claims.sh` | OK | 4/4 drawn + DRC-clean, 4/4 LVS-matched | **PASS** |
| `signoff/run-signoff.sh --check` | current | `signoff/tier-report.json is current.` | **PASS** |
| `sim/lib/check-readme-status.sh` | OK | 89 records, 24 campaigns | **PASS** |
| `sim/lib/check-characterization-coverage.sh` | OK | all 24 campaign directories covered | **PASS** |
| `sim/selftest.sh` | PASS | 63/63 points ok | **PASS** |

**The devices moved, so this is a stronger claim than #469's.** #469 changed
only which `track_y` each net's bus sat at; this change moves every switch and
every inverter in the row, which means new well edges, new tap-strip spans, new
escape landings and new riser columns — every geometric relationship
`SWITCH_DEVICE_GAP_UM`, `SWITCH_WELL_GAP_UM`, `INV_GROUP_GAP_UM` and the new
`INV_TO_SWITCH_GAP_UM` exist to buy. The `--offgrid` signoff-grade DRC run is
the independent check that the arithmetic in `check_escape_clearance()` and
`check_row_groups()` is right about geometry, and `netcheck.check_gds()` is the
independent check that nothing merged or opened — DRC sees neither (a merged
same-layer pair is one legal polygon; a missing link is nothing at all).

**The #448 label regression was watched for.** All four
`_canvas.Canvas.clear_inherited_labels()` call sites are untouched; this change
draws no label, and the four `pfdcp_inv_3v3` instances are placed and flattened
by the same code as before, only at different x. `test_pfdcp_block_layout.py`'s
`PinLabelTests` still assert the finished GDS carries exactly the 13 boundary
pin labels and none of the internal names, and the LVS match is the end-to-end
proof (a stray inherited label breaks the deck's global substrate merge and
mismatches every n-channel bulk, which is what #448 was).

**The reference netlist was not touched.** `block.reference_netlist()` is still
the mechanical flattening of the frozen `design/pfd_cp.sch` export;
`test_pfdcp_block_layout.py` asserts its output is byte-identical to the
committed `lvs-clean/pfd_cp.spice`, and it is.

## What else moved, and why

| Artifact | Change | Re-verified |
|---|---|---|
| `layout/evidence/cp-layout/cp_output_stage.gds` | the row reordered, the band 13 → 10 tracks: 65.45 → 63.20 µm | DRC `main` clean; `netcheck` clean (18 nets); `drc-clean/` and `connectivity/` regenerated |
| `layout/evidence/cp-block-layout/cp.gds` | inherits the 2.25 µm: 73.55 → 71.30 µm | DRC `main` clean; `netcheck` clean (22 nets); `drc-clean/` and `connectivity/` regenerated |
| `layout/evidence/pfd-cp-layout/pfd_cp.gds` | inherits the 2.25 µm: 76.55 → 74.30 µm | DRC `main` clean, `--offgrid` clean, LVS match; all three regenerated |
| `layout/evidence/floorplan-skeleton/pll_floorplan_skeleton.gds` | `skeleton.PFD_CP_STANDALONE_H_UM` records `pfd_cp`'s standalone footprint, so the rectangle shrinks with the block (75.48 → 73.23 µm) | regenerated; DRC `main` clean; `test_gds_reproducibility.py` rebuilds it from `floorplan.skeleton` on every run |
| `layout/evidence/area-audit/area-audit.md` | machine-rendered from the committed GDS files; `test_area_audit.py` fails if it goes stale | regenerated via `python3 layout/run_pv.py area --out …` |
| `layout/floorplan/PLL-FLOORPLAN.md` | §5.14 | — |

`cp_array`, `cp_dumpbuf`, `cp_leg_n`, `cp_leg_p`, `pfdcp_inv_3v3`, `pfd`,
`divider_chain`, `vco_block` and `lock_detector` are **not** touched —
`test_gds_reproducibility.py` rebuilds all 26 committed block GDS files and
XORs them layer by layer against what is committed, so an unintended change to
any of them fails the suite rather than riding along.

## Provenance

| | |
|---|---|
| Run | 2026-09-23 |
| Branch point | `origin/main` @ `e9eb5ba0` |
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
| `../cp-layout/`, `../cp-block-layout/`, `../floorplan-skeleton/` | the same set for `cp_output_stage`, `cp` and the skeleton |

`lvs-attempt/` — the mismatch this block's first block-level LVS run really
found (#440) — is untouched, as `test_pfdcp_block_layout.py::LvsEvidenceTests`
requires.
