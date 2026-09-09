# VCO block — mirror row-fold + block-level n-well guard-ring band (issues #293/#324)

Companion to [`PROOF-block.md`](PROOF-block.md) (increment 5: the assembled
`vco_block`, PR #325). That PROOF's own "one acceptance criterion this
increment does not fully close" section named two coupled, un-funded items
and filed issue #324 to track them:

1. The block-level guard ring was `GND_VCO` substrate-only — no second,
   concentric `VDD_VCO`-tied n-well tap ring at the block boundary
   (`PLL-FLOORPLAN.md` §1's "real two-sided ring").
2. Every VCO sub-block is a single row, and the band-select mirror alone
   (266 µm wide) set the whole assembled block's width — folding it into
   multiple rows was named as "the real lever" and the natural way to fund
   item 1's missing ring band (block *height* is free; width is not).

This increment is that work: `layout/pll_top/vco/mirror.py` is refolded from
one PMOS-row-over-one-NMOS-row into **two stacked tiers**, and
`layout/pll_top/vco/block.py` adds the missing n-well ring, funded by the
width the fold recovers.

## Why the fold cuts where it does

`vco_bias.sch`'s band-select mirror is a signal-flow ladder: `VBP0` (input)
→ cascade A → `VBN1` → cascade B → `VBP2` → cascade C → `VBN`/`VBP`
(output). Tracing every device's own nets (`devices.py`) shows exactly one
net crosses the boundary between cascade B and cascade C: `VBP2` (cascade
B's own drain feeds `MDB`, `MSWC0`, and cascade C's always-on gate). Every
other net either half touches is entirely local to it. So:

* **Tier 1** (bottom): `MIP0`/`MIN0` (bit-0 inverter), cascade A, `MSWA0`/
  `MSWA1`, `MIP1`/`MIN1` (bit-1 inverter), cascade B, `MDA`, `MSWB0`/`MSWB1`.
* **Tier 2** (stacked above, its own gap): `MDB`, `MIP2`/`MIN2` (bit-2
  inverter), cascade C, `MSWC0`/`MSWC1`, `MDN`/`MMN`/`MDP` (the output
  mirror's own diode loads).

Both tiers keep the exact machinery the single-row generator used — their
own PMOS row, NMOS row, and Metal2 mesh channel between them
(`mirror.py`'s own module docstring covers why that channel is Metal2, not
Metal1, unchanged from PR #313) — plus three things that are genuinely new
for two tiers instead of one:

* **A local `GND_VCO` substrate tap between the tiers** (`mid_gnd_tap`):
  tier 2's own NMOS row is well past `DF.13_MV`/`DF.14_MV`'s 15 µm bound
  from the shared ring's bottom band, so a second, local p+ tap sits
  between tier 1's n-well and tier 2's NMOS row, and is explicitly strapped
  to the shared outer ring (not left as a same-net-name-but-disconnected
  metal island — this repo proves connectivity, it does not assume it).
* **One cross-tier Metal2 riser for `VBP2`** — the only net neither tier's
  own local channel carries end-to-end. Pure Metal2 (no spacing
  relationship to Metal1/comp/poly/implant in this deck), so it freely
  crosses tier 1's PMOS row, its own tap band, and the mid GND tap.
* **One shared outer `GND_VCO` guard ring**, around both tiers, instead of
  one ring per tier — this is still one sub-block, not two.

## The block-level n-well ring

`block.py` adds a second, concentric `VDD_VCO`-tied n-well tap ring, one
guard-ring width in from the existing `GND_VCO` substrate ring, closing
`PLL-FLOORPLAN.md` §1's "real two-sided ring, not a substrate-only one":

* `NW.1a_LV`-legal width — 0.9 µm of n-tap comp inside a 1.5 µm-wide drawn
  `nwell` **annulus** (both ≥ the rule's 0.86 µm minimum; the annulus is the
  n-tap band plus `DF.4d_LV`'s enclosure on the inner *and* the outer edge).
* `DF.16_LV`-clear of every sub-block's own comp (1.0 µm from the annulus's
  own inner edge to the content bbox, ≥ the rule's 0.43 µm minimum) and
  `DF.4c_LV`-clear of the `GND_VCO` ring's own comp (1.0 µm outer, same
  margin).
* Tied to the real `VDD_VCO` supply trunk, not left floating — a Metal1
  strap on the block's own right side, next to the existing supply-trunk
  feeds.
* The mirror fold recovered far more width (~80 µm) than this ring costs —
  it fits inside the pre-existing `SHARED_MARGIN_UM` gap between the
  block's own content and its outer ring, rather than growing the block
  further (see `block.py`'s own `SHARED_MARGIN_UM`/`NWELL_RING_*_UM`
  comments for the exact arithmetic).

**The one real design conflict this surfaced, and how it is resolved**: the
block's own pre-existing `GND_VCO` straps (block ring → each sub-block's own
ring) run radially through exactly the annulus the new n-well ring now
occupies. A Metal1 strap crossing a Metal1 ring merges into it — a real
short, not a spacing nit (first caught by `block.connectivity_report()`,
*not* by DRC — see "DRC alone would not have caught this" below). Each strap
now hops onto Metal2 for exactly the width of that crossing
(`block.py`'s `strap_across_nwell_ring()`), landing back on Metal1 on the far
side — the same "Metal2 has no spacing relationship to Metal1" principle
`block.py`'s own inter-sub-block routing already uses.

## The ring is a hollow annulus, and that is now checked, not asserted

**This is the correction of a real defect in this PR's first revision, kept
here rather than quietly rewritten** (this repo's evidence is append-only,
and the failure mode is the interesting part).

The first version of the ring drew the *n-well layer itself* as a single
filled `canvas.rect("nwell", …)` spanning the ring's outer box. That box is
derived from `content` — the union bbox of all five sub-blocks — so the
"annulus" was in fact a solid slab covering the entire block interior.
Measured on the GDS that shipped in the first revision:

```
$ klt ring-check vco_block.gds --layers '[[21,0]]' --top vco_block --ignore-enclosed
status: broken
no_hole: ring layer set is a solid, hole-less region, not an annulus:
         no closed loop encloses an interior
```

| Metric (KLayout `Region` booleans on the built GDS) | filled `rect()` | hollow annulus (current) | on `main`, pre-PR |
|---|---|---|---|
| block-level `nwell` polygon's hole count | **0** | **1** | (no block-level n-well) |
| NMOS gate-crossing active area (`poly2 & comp & nplus`) | 79,070,000 nm² | 79,070,000 nm² | 79,070,000 nm² |
| …of which under `nwell` | **79,070,000 nm² (100 %)** | **0 nm² (0 %)** | 0 nm² (0 %) |
| `pplus` under `nwell` | 3,960,690,000 nm² | **1,488,310,000 nm²** | 1,488,310,000 nm² |

Every NMOS device in the block was inside n-well, and most of the block's own
p-type substrate ties were engulfed. Both figures are now back to their
pre-PR values exactly.

**Why neither existing gate caught it, which is the point.** The foundry DRC
deck's rules are edge- and spacing-based: an nplus active island sitting deep
inside an oversized n-well, with generous clearance from that well's own
edge, is geometrically indistinguishable from a legitimate n-well tap, so the
deck returned **0 violations** on the broken geometry. `connectivity_report()`
extracts metal1/via1/metal2 only — no device recognition — so it returned
**PASS**. Both gates are real gates for what they check; neither checks
device-level well placement. Block-level LVS would have caught it, and this
block has none yet (see "What is still not proved"). A "0 violations + PASS"
pair is therefore *not* sufficient evidence that a well shape is correct, and
this repo now says so in a test rather than in prose.

The fix is `primitives.rect_frame()` — a hollow rectangular frame drawn as
four corner-overlapping bands, the same construction `guard_ring()` already
uses for its tap strips, which raises rather than silently degrading to a
filled rect if the width would leave no hole. `block.py` draws the n-well
with it.

### The new checks are in the test suite, not in this document

`layout/tests/test_vco_layout.py` (runs in the ordinary
`python3 -m pytest layout/tests/` pass; the geometric half is gated on
`klayout.db` the same way the rest of the file is):

| Test class | Asserts |
|---|---|
| `AssembledVcoBlockNwellRingPlanTests` | pure-Python arithmetic: `Placement.nwell_hole` exists and is a real hole; it clears every sub-block *and* `content` by more than `DF.16_LV`; the band is wider than `NW.1a_LV`; the drawn well encloses its own tap comp by more than `DF.4d_LV` on the **inner** edge as well as the outer; the `GND_VCO` strap's inboard Metal2 jump lands inside the hole |
| `RectFramePrimitiveTests` | `rect_frame()`'s four bands merge into exactly one polygon with exactly one hole; the hole is the width-inset box and carries no geometry; a width that would fill the box raises |
| `AssembledVcoBlockNwellRingGeometryTests` | on the geometry `build()` actually draws: the block-level `nwell` polygon has ≥ 1 hole; that hole fully contains every sub-block; **no** NMOS gate-crossing active area anywhere in the block is under `nwell`; no substrate-tie `pplus` is under the block ring; and the ring's own n-tap comp *is* inside the drawn well (the opposite failure mode — a frame so hollow it undercuts its own tap) |

**These are real gates, verified by injection.** Monkeypatching
`rect_frame()` back to the filled `canvas.rect()` of the first revision and
re-running `AssembledVcoBlockNwellRingGeometryTests`:

```
test_the_block_level_nwell_is_an_annulus_not_a_slab                ... FAIL
    AssertionError: 0 not greater than or equal to 1 :
    the block-level n-well ring has no hole
test_the_annulus_hole_contains_every_sub_block                     ... FAIL
test_no_nmos_active_area_anywhere_in_the_block_sits_under_nwell    ... FAIL
    AssertionError: NMOS gate-crossing active area is inside n-well
test_the_block_ring_does_not_engulf_the_substrate_ring_pplus       ... FAIL
test_the_block_ring_carries_its_own_vdd_tied_ntap                  ... ok
Ran 5 tests -- FAILED (failures=4)
```

Four of the five fail on the injected defect; the fifth correctly still
passes (a solid slab does still enclose the tap band — that assertion is
guarding a different, opposite mistake). The identical run against the
current geometry is 5/5 green.

The external cross-check agrees, and is reproducible with the same command
that found the defect:

```
$ klt ring-check layout/evidence/vco-layout/vco_block.gds \
      --layers '[[21,0]]' --top vco_block --ignore-enclosed
layers: 21/0
status: continuous
violations: 0
```

## Result

```
$ python3 -m vco.mirror --outdir layout/evidence/vco-layout   # (from layout/pll_top/)
$ python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_bandsel_mirror.gds \
      --top vco_bandsel_mirror --run-dir <run> --offgrid
DRC clean: vco_bandsel_mirror (D), 0 violations

$ python3 -m vco.block --outdir layout/evidence/vco-layout --check-connectivity
$ python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_block.gds \
      --top vco_block --run-dir <run> --offgrid
DRC clean: vco_block (D), 0 violations
connectivity: PASS

$ klt ring-check layout/evidence/vco-layout/vco_block.gds \
      --layers '[[21,0]]' --top vco_block --ignore-enclosed
status: continuous
violations: 0

$ python3 -m pytest layout/tests/
245 passed
```

| Item | Value |
|---|---|
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| KLayout | 0.30.10 |
| Deck | the PDK's own `libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D`, `--offgrid` |
| Polygons in `vco_block` | 14,118 (14,115 in this PR's first revision; the hollow n-well annulus is 4 rectangles where the rejected filled slab was 1) |
| DRC violations (`vco_bandsel_mirror`) | **0** |
| DRC violations (`vco_block`) | **0** |
| `block.connectivity_report()` | **PASS** — every routed net (including the new `VBP2` cross-tier riser) probes as one connected net; `VDD_VCO != GND_VCO`, `VBP != VBN`, `NOFF != NVI`, `VBP0 != VBP` all still distinct |
| `klt ring-check` on `nwell` (21/0) | **continuous**, 0 violations — a real annulus (see "The ring is a hollow annulus" above) |
| NMOS gate-crossing active area under `nwell` | **0 nm²** of 79,070,000 nm², identical to pre-PR `main` |
| `layout/tests/` | **245 passed** (232 before this correction; +13 for the n-well-ring annulus/overlap regression tests) |

## Before / after footprint

| Block | Before (PR #325) | After (this increment) | Change |
|---|---|---|---|
| `vco_bandsel_mirror` (`mirror.py`) | 269.86 × 37.12 µm (10,017 µm²) | 189.48 × 50.82 µm (9,629 µm²) | −80.38 µm width (−29.8 %), +13.70 µm height, −3.9 % area |
| `vco_block` (`block.py`) | 294.78 × 148.18 µm (43,680 µm²) | 214.82 × 162.88 µm (34,990 µm²) | −79.96 µm width (−27.1 %), +14.70 µm height, **−19.9 % area** |
| `skeleton.total_extent_um2()` | 148,157 µm² (≈98.8 % of the 150,000 µm² draft target) | 132,565 µm² (≈**88.4 %** of the same target) | headroom **improves** from ≈1.2 % to ≈11.6 % |

(The mirror's own width dropped from 269.86 to 189.48 µm, a 29.8 µm / 11.0 %
reduction on its own — the block-level number is larger because folding the
mirror also let several of `block.py`'s own routing channels shrink.)

**Budget headroom improves, rather than eroding further, and that is stated
plainly because the opposite was equally possible**: PR #325's own PROOF
recorded the fold as "the real lever," worth "roughly another 2×" at full
utilisation — this increment does not chase that ceiling (folding only the
mirror, not every sub-block), but even this one fold recovers enough width
that the new n-well ring is funded with margin to spare, and the whole
skeleton's own bounding box moves further from the 150,000 µm² draft target
instead of closer to it.
`test_area_budget_headroom_is_reported_not_silently_exceeded` /
`test_skeleton_bounding_box_headroom_against_the_draft_budget` pin both the
old and new ranges so a future edit that erodes this margin again is caught
in the test suite, not just in review.

## The DRC run is a real gate, not a tautology

Same negative control `PROOF-block.md` uses — inject an undersized Metal1
shape into the regenerated `vco_block.gds` and re-run the identical command:

```
$ python3 -c "...faults.inject_drc_violation('vco_block.gds', 'vco_block_drcfault.gds')"
$ python3 layout/run_pv.py drc vco_block_drcfault.gds --top vco_block --run-dir <run> --offgrid
DRC violations: vco_block (D), 1 item(s) -- M1.1x1
```

## Connectivity is a real gate too — and it is what caught the strap/ring short above

Suppressing the new `VBP2` cross-tier riser (skip its `m2_route()` call) in
a scratch build of `mirror.py`'s own two tiers: both tiers still draw their
own local `VBP2` track and the block still stands, but the two tiers' own
`VBP2` tracks probe as **two separate nets** (cluster ids 3 and 15 in the
re-run below, 4 and 16 in the original — the ids are extraction-order
dependent, the structural result is not; unsuppressed, both probe 13)
— the fold's one genuinely new inter-tier connection is proven load-bearing,
not decorative.

The Metal1-strap-through-the-n-well-ring short described above was caught
the same way, during development rather than as a hypothetical: the first
version of `block.py`'s new ring left every `GND_VCO` strap running straight
through it as plain Metal1, which DRC accepted (same-layer shapes touching
is not a width/spacing violation) but which
`block.connectivity_report()` correctly reported as
`VDD_VCO != GND_VCO: SHORTED together`. `strap_across_nwell_ring()`'s Metal2
jump is the fix; the passing connectivity report above is what proves it,
not just the DRC-clean run.

## The four unaffected sub-blocks are still unaffected

`ring.py`, `buffer.py`, `vtoi_core.py` and `bias_resistors.py` are untouched
by this increment. Regenerated and compared against the committed GDS here,
per layer, with KLayout's own XOR (`Region ^ Region`, merged): **empty on
every layer, all four blocks** — bit-identical geometry, not merely "still
builds." Each was also re-run through the DRC deck independently: all four
still 0 violations.

| Block | XOR vs. committed GDS | DRC (re-run) |
|---|---|---|
| `vco_ring` | empty (all layers) | clean, 0 violations |
| `vco_out_buffer` | empty (all layers) | clean, 0 violations |
| `vco_vtoi_core` | empty (all layers) | clean, 0 violations |
| `vco_bias_resistors` | empty (all layers) | clean, 0 violations |

The n-well-annulus correction above is confined to `block.py` and a new
`primitives.py` helper, so `vco_bandsel_mirror.gds` is *also* bit-identical
across it: regenerating all five sub-blocks and XOR'ing per layer against the
committed GDS is **empty on every layer for all five**, including the folded
mirror. Only `vco_block.gds` changed (+3 polygons — 4 rectangles where the
rejected filled slab was 1).

## Acceptance criteria, checked

| Issue #324 AC | Where |
|---|---|
| At least one sub-block refolded into multiple rows, reducing `block.py`'s assembled width | `mirror.py`'s two-tier fold (this file, "Before / after footprint") |
| Recovered width funds a block-level n-well tap ring, concentric with `GND_VCO`, `DF.4d_LV`/`DF.16_LV`-clear | `block.py`'s `NWELL_RING_*_UM`/`NWELL_FRAME_WIDTH_UM`; `test_nwell_ring_is_concentric_with_and_inside_the_gnd_ring` / `test_nwell_ring_encloses_all_content_with_real_margin` |
| …and it is a **ring**, not a slab over the block's own devices | `AssembledVcoBlockNwellRingPlanTests` / `RectFramePrimitiveTests` / `AssembledVcoBlockNwellRingGeometryTests`; `klt ring-check` = `continuous` ("The ring is a hollow annulus" above) |
| `block.py` regenerates DRC-clean; `connectivity_report()` passes for every net | "Result" above |
| `skeleton.py`'s `VCO_CORE`/`total_extent_um2()` updated; budget margin change noted | Both are derived from `vco_block.footprint_um()`/`placement()`, so they update automatically; "Before / after footprint" states the margin improved |
| `PROOF-block.md` (or a companion) records before/after, confirms the four other standalone proofs unaffected | this file |

Both issue #293 and issue #324 are closed by this increment: #293's own
"dedicated VCO guard ring ... tied to `GND_VCO` on the substrate side and to
a local `VDD_VCO`-tied n-well tap ring" acceptance criterion — the one gap
PR #325 left open specifically because of this — is now met in full, and
#324's own acceptance criteria (stated almost verbatim from #293's own
follow-up scope) are the checklist directly above.

## What is still not proved

Unchanged from `PROOF-block.md`: no block-level LVS (SPICE netlist +
device-recognition extraction) yet, and no post-layout extraction/
simulation. This increment's own connectivity extension (`VBP2`'s cross-tier
riser, the mid GND tap's own strap, the n-well ring's own supply strap) is
covered by the same metal-graph connectivity check `PROOF-block.md`
introduced, not by LVS.

That gap is what made the filled-slab defect above survive both existing
gates, so it is worth restating precisely rather than leaving as a bullet:
**this block has no gate that recognises devices.** The new
`AssembledVcoBlockNwellRingGeometryTests` narrow the gap for exactly one
class of well-placement error (active area under the wrong well) and are
explicitly *not* a substitute for LVS — a wrong device *size*, a mis-wired
terminal, or a missing implant would still pass everything recorded here.
Block-level LVS remains the next real increment.

## Artifacts

| Path | What it is |
|---|---|
| `vco_bandsel_mirror.gds` | the two-tier mirror block (updated in place; supersedes the single-row geometry `PROOF-mirror-buffer.md` recorded) |
| `vco_block.gds` | the assembled block with the new n-well ring (updated in place; supersedes `PROOF-block.md`'s geometry) |
| `drc-clean/drc-mirror.stdout.log`, `drc-clean/vco_bandsel_mirror_main.lyrdb` | updated DRC run for the folded mirror (0 violations) |
| `drc-clean/drc-block.stdout.log`, `drc-clean/vco_block_main.lyrdb` | updated DRC run for the assembled block (0 violations) |
| `drc-clean/connectivity-block.log` | updated `connectivity_report()` output (PASS, including the new `VBP2` cross-tier riser and n-well-ring strap probes) |
| `layout/tests/test_vco_layout.py` | the annulus/overlap regression tests described above — re-runnable evidence, not a one-off manual KLayout session |

Regenerate via `python3 -m vco.mirror` / `python3 -m vco.block --check-connectivity`
(from `layout/pll_top/`) + `layout/run_pv.py drc`; do not hand-edit any file
under this directory. `vco_bandsel_mirror.gds` and the four other sub-block
GDSs are unchanged by the n-well-annulus correction (XOR-empty, above), so
only `vco_block.gds` and its own two DRC artifacts moved.

## Friction protocol (CLAUDE.md)

No new `klayout-tools` gap was hit. This increment's one genuinely new
technique — routing a supply/ground strap across an intervening ring on
Metal2 rather than Metal1 — is a layout *strategy* this repo's own
generators already use for signal nets (`block.py`'s own module docstring);
applying it to a strap is a design choice inside this repo's generators, not
a capability KLayout (or `klt`) was missing.

One observation from the annulus correction, recorded because it is about
the *tooling*, not this design: `klt ring-check` diagnosed the defect
correctly and immediately (`no_hole: … solid, hole-less region, not an
annulus`), which is exactly the capability that was wanted — no gap to file.
What the repo lacked was any reason to *run* it as part of the normal gate,
which is a discipline problem this repo fixed on its own side by folding the
equivalent check into `layout/tests/`. Worth noting only so a future reader
does not mistake this for a `klayout-tools` shortcoming.
