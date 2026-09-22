# `pfd_cp` — the fold, and the track band above it (issue #455)

`layout/evidence/area-audit/PROOF.md` (issue #442) sized two levers on this
block and paired them in one issue because they interact. This record is what
executing them produced, measured against those sizings.

| | as-drawn before | as-drawn after | Δ |
|---|---|---|---|
| `footprint` tuple | 434.310 × 80.725 µm (35,059.67 µm²) | **347.410 × 76.225 µm (26,481.33 µm²)** | **−8,578 µm², −24.5 %** |
| committed GDS bbox | 432.66 × 81.55 µm (35,281 µm²) | **344.98 × 77.30 µm (26,665 µm²)** | **−8,616 µm², −24.4 %** |
| fill | 17.1 % | **22.9 %** | +5.8 pp |
| drawn area | 6,030 µm² | 6,116 µm² | +86 µm² (the trunks got longer) |
| device band / no-device band | 37.18 / 44.37 µm | **49.05 / 28.24 µm** | +11.87 / −16.13 µm |
| Metal2 tracks | 57 | 57 | — |

Reproduce: `python3 -m pfd_cp.block --outdir <workdir>` (from
`layout/pll_top/`), `python3 layout/run_pv.py area`.

## What changed, in two moves

### Lever 1 — `pfd` folded into `cp`'s own empty band

Through #386 this block placed `pfd` at the origin and `cp` 6 µm to its
right. That bought an 80.90 µm column of block width whose upper 58.24 µm
was 2.2 % filled. `cp` already had a hole the right size: `cp_dumpbuf`
(211.10 × 36.00 µm) sits beside the much taller `cp_output_stage` (130.31 ×
66.73 µm), leaving a 217.10 × 38.72 µm band above the dump buffer that is
99.0 % empty. `pfd` is 80.90 × 22.48 µm.

`cp` now lands at a zero offset and `pfd` is translated into that band —
`BLOCK_GAP_UM` (6.0 µm) above `cp_dumpbuf`'s own topmost drawn edge and
`BLOCK_GAP_UM` right of the rightmost thing `cp` draws above it. That second
quantity is `cp.py`'s own `d_riser_x`, which is local to its `build()` and
not exposed, so `block.py`'s `_cp_band_right_edge()` **measures it off `cp`'s
own finished GDS** rather than re-deriving it — the same "read the geometry
back out of its own finished GDS, so it cannot drift out of sync with the
module that drew it" convention `cp.py`'s own `_dumpbuf_bus_track()`
established for the mirror-image problem one level down.

The result is a block exactly as wide as `cp` itself: **434.31 → 347.41 µm**,
the full 86.90 µm the lever was sized at. `build()` raises rather than
returning a *larger* block if `pfd` ever stops fitting in the band, and
`test_pfdcp_block_layout.py` asserts the property (`pfd` inside `cp`'s own
extent on both axes; the block's width equal to `cp`'s) that makes the saving
real rather than incidental.

### Lever 2 — the trunk band, at this block's own level

Two defects, both in how the Metal2 trunk rows above the placed blocks were
pitched and based:

1. **The pitch was the wrong constant.** Both `cp.py` and `block.py` set
   `BACKBONE_PITCH_UM = cp_array.RISER_MIN_PITCH_UM` (1.00 µm). That constant
   is `cp_array`'s minimum centre-to-centre separation between two Metal3
   *riser columns* — an **X** pitch between vertical Metal3 strips, sized
   against `M3.2a`. A trunk row is a horizontal **Metal2** strip, and the
   pitch two of those need is `cp_array.METAL2_TRACK_PITCH_UM` (0.75 µm),
   which leaves 0.75 − 0.44 = 0.31 µm between two adjacent rows' Via2 landing
   pads, above `M2.2a`'s 0.28 µm minimum. This is not an argument from first
   principles: `cp_output_stage`'s own glue bus already stacks 14 tracks at
   exactly this pitch *with* Via2 landings on them and is signoff-clean. Both
   modules now use it — 6 rows in `cp`, 4 here: **−2.50 µm**.
2. **The base restated a clearance `cp` had already applied.** `block.py`
   based its own rows at `max(pfd_top, cp_top) + BACKBONE_MARGIN_UM`. But
   `cp`'s topmost drawn edge *is* the top row of `cp`'s own backbone band,
   and what one more row of the same band needs above it is one track pitch,
   not a block-to-block margin — the rows are parallel, non-touching
   same-layer strips, exactly as `cp`'s own six are to each other. The four
   rows now continue `cp`'s band: **−2.00 µm**. `BACKBONE_MARGIN_UM` still
   binds against `pfd`, whose top is not a trunk row; post-fold it sits low
   enough in the band that it never does, and the rule is stated in code
   rather than assumed away.

Together: **80.725 → 76.225 µm** of height.

## Why this was one issue and one PR, and in which order

The issue required the two levers to be planned jointly rather than
sequenced blind, and the reason turned out to be sharper than "they overlap".

Before the fold, `cp`'s six backbone rows (x ∈ [86, 189]) and this block's
four trunks (x ∈ [−14, 97]) are nearly x-disjoint, and a four-colouring of
that interval graph exists — all four trunks could have shared `cp`'s
existing rows for free, removing the band entirely. **The fold destroys that
option**: with `pfd` on the right, every trunk spans from `cp_output_stage`'s
glue bus (x ≈ −17) out to `pfd`'s riser columns (x ≈ 120–200), covering all
six of `cp`'s rows. Executing lever 2 first and lever 1 second would have
built the row-sharing and then thrown it away.

The three arrangements, all on the `footprint` tuple:

| Arrangement | Footprint | Area | vs today |
|---|---|---|---|
| Row-sharing alone (no fold) | 434.31 × 73.23 µm | 31,803 µm² | −9.3 % |
| Fold alone (band unchanged) | 347.41 × 80.73 µm | 28,045 µm² | −20.0 % |
| **Fold + band continued above `cp`'s own top row** | **347.41 × 76.23 µm** | **26,481 µm²** | **−24.5 %** |

So the fold is worth more than the row-sharing it forecloses, and what
survives of lever 2 alongside it is the pitch correction plus the base
correction. One PR, because the decision is one decision.

## Achieved against the ceilings

The issue's own ceilings, and what came out:

| | Ceiling (#455 / #442) | Achieved | |
|---|---|---|---|
| Lever 1, width | 434.31 → 347.41 µm (−7,015 µm²) | **347.41 µm** | **ceiling reached exactly** |
| Lever 2, height | 81.55 → 42.75 µm (−16,785 µm²) | 81.55 → 77.30 µm (−1,466 µm²) | 8.7 % of the ceiling |
| Joint | 347.41 × 42.75 = 14,852 µm² (**−58 %**) | **26,665 µm² (−24.4 %)** | 42 % of the ceiling |

The width ceiling is reached because it is real: 347.41 µm is `cp`'s own
width, and no arrangement that keeps `cp` intact is narrower. **The height
ceiling is not reachable at all**, and the three reasons are measurable
rather than a matter of effort. This is the same class of finding §5.8
recorded for #454 (estimate 60,006 µm², outcome 39,530 µm²), and the first
reason is literally the same mistake:

**1. The 57-track census is flat over five levels; only 4 of the 57 are
assignable here.** Rebuilding each sub-block standalone and running the same
census on each:

| Level | Metal2 tracks it owns | Packed floor |
|---|---|---|
| `pfd` | 5 | 3.75 µm |
| `cp_dumpbuf` | 10 | 7.50 µm |
| `cp_output_stage` (incl. `cp_array`) | 32 | 24.00 µm |
| `cp`'s own backbone band | 6 | 4.50 µm |
| **`pfd_cp`'s own trunk band** | **4** | **3.00 µm** |
| flat total | **57** | 42.75 µm |

Composition is hierarchical: `cp` places `cp_output_stage` and `cp_dumpbuf`
as opaque boxes, and this block places `cp` as one. A track can only be
re-assigned within the level that drew it, so "57 tracks packed solid into
42.75 µm" is not a transformation any single module can perform. §5.8's
attribution error, in a different block.

**2. After the fold, devices bind before tracks do.** The 37.18 µm device
figure in the ceiling was measured *before* the fold, when `pfd`'s devices
shared y-bands with `cp`'s. Moving `pfd` up gives it a band of its own: the
block's device bands now total **49.05 µm**, above the 42.75 µm packed-track
floor. Re-derived on the post-fold geometry, the same `max(packed, devices)`
ceiling is `344.98 × 49.05 = 16,921 µm²` — **−52.0 %**, not −58 %. The fold
moved the binding constraint from the routing band to the device bands; that
is a consequence of lever 1 that lever 2's sizing could not have known.

**3. One sub-block already exceeds the ceiling height on its own.**
`cp_output_stage`'s drawn diffusion spans **52.23 µm** of y when built
standalone (`cp`'s spans 54.03 µm). No arrangement of `pfd_cp` can be
42.75 µm tall while containing a block whose own devices are 52.23 µm tall.

### What this block's own level *could* do, and did

The honest measure of a composition-level lever is what the composition
costs over the blocks it composes:

| | before | after |
|---|---|---|
| `pfd_cp` bbox | 35,281 µm² | 26,665 µm² |
| `cp` bbox (contained) | 26,062 µm² | 25,630 µm² |
| **cost of composing `pfd` + the trunk band on top of `cp`** | **9,219 µm²** | **1,035 µm²** |

**−88.8 % of this level's own additive cost.** What remains above `cp` is
four trunk rows and nothing else; `pfd` itself now costs zero block area.
Everything left is inside `cp`, `cp_output_stage`, `cp_array` and
`cp_dumpbuf` — the residual lever, sized below.

### The residual, sized

Post-fold, the gap between the block as drawn (26,665 µm²) and its
re-derived geometric ceiling (16,921 µm²) is **9,744 µm², 36.5 % of the
block**, and it lives entirely below this level:

* `cp_output_stage`'s glue bus assigns one dedicated Metal2 track per net
  (`cp_array._route_side` → `NetTracks`), 14 tracks over 9.75 µm. Their
  x-spans are at most **9** deep anywhere (measured: 9 of the 14 nets are
  live at x = 22.41), so an interval-graph assignment — the same
  `pack_tracks()` substitution #341/#454 made twice in the divider-chain
  family — has a floor of 9 rather than 14 tracks, worth up to 3.75 µm of
  block height (≈1,290 µm²).
* `cp_dumpbuf` spends 25.87 µm of its 37.07 µm height on a band carrying 10
  tracks whose packed floor is 7.50 µm.
* Neither is a `pfd_cp` change: both ripple through `cp_array`,
  `cp_output_stage`, `cp` and this block, four committed GDS artifacts with
  their own DRC (and, here, LVS) claims. Filed as **issue #469** per §5.5's
  one-lever-per-PR discipline, the same way #458 was split out of #454
  rather than folded in — with the sizings above, and with the note that a
  `cp_dumpbuf` fold and *this* block's fold are mutually exclusive (`pfd`
  now occupies the band a folded dump buffer would need), so that pair has
  to be decided together the same way #455's own two levers were.

## Verification

Every check this block carried before is re-run against the new geometry,
not assumed. Nothing here is a by-construction claim.

```bash
python3 -m pfd_cp.cp    --outdir <workdir>            # (from layout/pll_top/)
python3 -m pfd_cp.block --outdir <workdir>
python3 layout/run_pv.py drc layout/evidence/pfd-cp-layout/pfd_cp.gds --top pfd_cp --run-dir <rundir>
python3 layout/run_pv.py drc layout/evidence/pfd-cp-layout/pfd_cp.gds --top pfd_cp --run-dir <rundir> --offgrid
python3 layout/run_pv.py lvs layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.spice --top pfd_cp --run-dir <rundir>
python3 layout/run_pv.py drc layout/evidence/cp-block-layout/cp.gds --top cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfd_cp` DRC, table `main` (default) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` LVS, deck verdict | match | `INFO : Congratulations! Netlists match.` | **PASS** |
| `pfd_cp` net count, layout vs. reference | equal | 92 / 92 | **PASS** |
| `pfd_cp` device count, layout vs. reference | equal | 168 / 168 | **PASS** |
| `pfd_cp` extracted top-level ports | the 13 boundary pins | `IBP IBN VSS B0 ICN ICP VDD B1 UP VOUT REF DN FB` | **PASS** |
| `netcheck.check_gds()` on `pfd_cp` | no shorts, no splits | `connectivity clean: 76 nets, no shorts, no splits` | **PASS** |
| `cp` DRC, table `main` (default) | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `netcheck.check_gds()` on `cp` | no shorts, no splits | `connectivity clean: 22 nets, no shorts, no splits` | **PASS** |
| `layout/tests` suite | pass | 719 tests, all passing | **PASS** |

**The LVS claim did not regress, and the #448 risk was watched for.** Issue
#448's root cause was stray *inherited* net labels surviving a composing
`flatten()` — eight `ENB` texts on the ground rail, which broke the deck's
global substrate-net merge and mismatched all 84 n-channel bulks. Both
`cp.py` and `block.py` still call `_canvas.Canvas.clear_inherited_labels()`
immediately after their own `flatten()`, both call sites are untouched by
this change, and `test_pfdcp_block_layout.py`'s `PinLabelTests` still assert
that the finished GDS carries exactly 13 labels — the block's own boundary
pins, `UP`/`DN` on the Metal2 pin purpose (36/10) and the other eleven on
Metal1's (34/10) — and that none of `{EN, ENB, VBN, VBP, VCASCN, VCASCP,
TAIL, UPT, DNT, VREF, B0B, B1B}` survives. A relocation is exactly the kind
of change that could have reintroduced the defect (every label moves with
its geometry), so the check is named here rather than left implicit.

**The reference netlist was not touched.** `block.reference_netlist()` is
still the mechanical flattening of the frozen `design/pfd_cp.sch` export, and
its output is byte-identical to the committed `lvs-clean/pfd_cp.spice` —
asserted by `test_pfdcp_block_layout.py`. This is a geometry change; the
schematic it is compared against did not move.

**No routing design was invented.** `cp.py`'s own docstring records four
routing designs that failed before the one that held, and the failure modes
are `V1.1`/`V2.1`/`M2.2a` from a second via stack on an occupied pad and a
Metal3 riser climbing through another net's trunk row. This change reuses
the surviving design unchanged — every riser still lands at its own side's
native, provably via-free edge (`glue_bus[net]`'s `x_lo` on the `cp` side,
`pfd`'s far-from-axis bus edge and its continuous Metal1 rail on the `pfd`
side), and every trunk still runs above every row either sub-block drew.
What moved is *where the two blocks sit* and *how tightly the trunk rows are
stacked*, not how a connection is made. The one new adjacency the fold
creates — `pfd`'s four riser columns beside `cp`'s six dumpbuf-side riser
columns — is what `_cp_band_right_edge()` + `BLOCK_GAP_UM` exist to keep
apart, and the signoff `--offgrid` run is what proves they are.

## What else moved, and why

| Artifact | Change | Re-verified |
|---|---|---|
| `layout/evidence/cp-block-layout/cp.gds` | the trunk-row pitch correction (1.00 → 0.75 µm) shortens `cp` by 1.25 µm: 344.98 × 75.55 → 344.98 × 74.30 µm, −432 µm² (−1.7 %) | DRC `main` clean; `netcheck` clean (22 nets); `drc-clean/` and `connectivity/` regenerated |
| `layout/evidence/floorplan-skeleton/pll_floorplan_skeleton.gds` | `skeleton.PFD_CP`'s own w/h are the recorded standalone footprint, so the skeleton's `PFD_CP` rectangle shrinks with the block | regenerated; `test_gds_reproducibility.py` rebuilds it from `floorplan.skeleton` on every run |
| `layout/evidence/area-audit/area-audit.md` | machine-rendered from the committed GDS files; `test_area_audit.py` fails if it goes stale | regenerated via `python3 layout/run_pv.py area --out …` |
| `layout/floorplan/PLL-FLOORPLAN.md` | §5.10 | — |

`cp_output_stage`, `cp_array`, `cp_dumpbuf`, `cp_leg_*` and `pfd` are
**not** touched: `python3 -m unittest discover -s layout/tests` includes
`test_gds_reproducibility.py`, which rebuilds all 26 committed block GDS
files and XORs them layer by layer against what is committed, so an
unintended change to any of them would fail the suite rather than ride
along.

## Provenance

| | |
|---|---|
| Run | 2026-09-22 |
| Branch point | `origin/main` @ `0fca67d4` |
| Invoked as | `python3 -m pfd_cp.block --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc` / `lvs`, PDK/KLayout/PV-python resolved per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D` (default `--lvs_sub=VSS`) |

## Artifacts

All under this directory, regenerated against the new geometry and
overwriting the #386/#448 run's own copies (the *records* of those runs stay
in `PROOF.md`, which is append-only; the deck outputs are re-derived files,
not history):

| Path | What it is |
|---|---|
| `pfd_cp.gds` | the assembled block, `pfd` folded into `cp`'s band |
| `drc-clean/pfd_cp_main.lyrdb`, `drc-clean/drc.stdout.log` | DRC, default run |
| `drc-clean-offgrid/pfd_cp_main.lyrdb`, `drc-clean-offgrid/drc.stdout.log` | DRC, `--offgrid` (signoff-grade) run |
| `lvs-clean/lvs.stdout.log`, `lvs-clean/pfd_cp.cir`, `lvs-clean/pfd_cp.lvsdb` | LVS run against the unchanged `lvs-clean/pfd_cp.spice` |
| `connectivity/pfd_cp.netcheck.log` | `netcheck.check_gds()` summary and per-net component breakdown |

`lvs-attempt/` — the mismatch this block's first block-level LVS run really
found (#440) — is untouched, as `test_pfdcp_block_layout.py::LvsEvidenceTests`
requires.
