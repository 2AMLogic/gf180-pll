# VCO block — a verification gate for "n-well drawn over a block's own devices" (issue #339)

Companion to [`PROOF-fold.md`](PROOF-fold.md) (issue #324), which drew the
block-level n-well ring correctly as a real annulus. This file is not a new
geometry increment — `vco_block.gds` is unchanged, byte-for-byte, by this
work (confirmed below) — it is the verification gate `PROOF-fold.md` itself
named as still missing: nothing on `main` asserted, geometrically, that the
drawn n-well *is* an annulus, or that no active device sits under it. The
same defect PR #333 shipped once (caught only by manual KLayout inspection
during review) could have landed again on top of #324's correct fix,
undetected, until block-level LVS exists.

## The defect this closes, restated

PR #333's first revision drew the block-level n-well "guard ring" as a
single filled `canvas.rect()` spanning the ring's outer box (derived from the
union bbox of all five sub-blocks). Measured on the GDS that shipped:

* `klt ring-check --layers '[[21,0]]'`: `status: broken`, `"solid, hole-less
  region, not an annulus"`
* `poly2 & comp & nplus` (real NMOS gate-crossing active area):
  79,070,000 nm², of which **100 %** sat under `nwell` — every NMOS device
  in the block inside the well
* `pplus` under `nwell` grew from 1.49e9 to 3.96e9 nm²

**Neither of the block's two existing gates could see it:**

* The foundry DRC deck's rules are edge/spacing-based. An `nplus` active
  island sitting deep inside an oversized `nwell`, with generous clearance
  from that well's own edge, is geometrically indistinguishable from a
  legitimate n-well tap. The deck returned 0 violations.
* `block.connectivity_report()` extracts `metal1`/`via1`/`metal2` only — no
  device recognition. It returned PASS.

Only LVS would catch it, and block-level LVS does not exist yet
(`PROOF-block.md` / `PROOF-fold.md` → "What is still not proved"). PR #337
(issue #324) fixed the geometry on `main` — the block-level ring is a real
4-band annulus today — but `main`'s own regression tests for it
(`test_nwell_ring_meets_the_nwell_and_tap_rules_it_cites`,
`test_nwell_ring_clears_every_sub_block_nwell_by_nw2b`, …) are
**arithmetic-only**: they check `NWELL_RING_*` against the DRC rules they
cite, never the geometry `build()` actually draws. Nothing asserted the
drawn `nwell` polygon has a hole, or that no active area sits under it — the
same edit that broke PR #333 would have landed green on `main` right up to
this issue.

## What this increment adds

1. **`primitives.rect_frame(canvas, layer, x0, y0, x1, y1, width)`** — a
   hollow rectangular frame drawn as four corner-overlapping bands (the same
   construction `guard_ring()` already uses for its `tap_strip()` bands),
   which **raises** rather than silently degrading to a filled rect if
   `width` would leave no hole.
2. **`block.py`'s block-level n-well ring now calls `rect_frame()`** instead
   of open-coding the same four `canvas.rect()` calls inline. The geometry
   is unchanged (see "No GDS drift" below) — this replaces an easily
   re-broken idiom with a named, independently-tested primitive.
3. **Geometric regression tests**, gated on `klayout.db` the same way the
   rest of `test_vco_layout.py` is, asserting against the geometry
   `build()` actually draws (`layout/tests/test_vco_layout.py`):
   * `RectFramePrimitiveTests` — the primitive itself: one merged polygon
     with exactly one hole, the hole is empty and exactly the width-inset
     box, and an infeasible width raises `ValueError`.
   * `AssembledVcoBlockNwellRingGeometryTests` — the assembled block:
     * the block-level `nwell` polygon has ≥ 1 hole (not a slab);
     * that hole fully contains every sub-block;
     * **no** NMOS gate-crossing active area (`poly2 & comp & nplus`)
       anywhere in the block sits under `nwell`;
     * no substrate-tie `pplus` falls under the block-level ring;
     * the ring's own n-tap `comp` (the `ncomp`/`nplus` tap band
       `guard_ring(kind="n")` draws) *is* inside the drawn well — the
       opposite failure mode, a frame so hollow it undercuts its own tap.

## Fault injection: the gate is real, not decorative

The failure mode is demonstrated by injection, the same discipline
`layout/harness/faults.py`'s DRC/LVS negative controls use: a check that has
only ever been shown clean is not evidence it can catch a dirty result.

`vco_block.prim.rect_frame` was monkeypatched back to exactly PR #333's
original construction — a single filled `canvas.rect(layer, x0, y0, x1,
y1)` over the ring's full outer box, ignoring `width` — and the block was
rebuilt from that patched module:

```python
def _filled_rect_not_a_frame(canvas, layer, x0, y0, x1, y1, width):
    canvas.rect(layer, x0, y0, x1, y1)

vco_block.prim.rect_frame = _filled_rect_not_a_frame
result = vco_block.build()
```

Re-running the same checks `AssembledVcoBlockNwellRingGeometryTests` makes
against that injected-fault build:

```
ring_polys count: 1
holes on the (single) ring polygon: 0
NMOS gate-crossing active area under nwell: 79070000 nm^2 (total gate area 79070000 nm^2)
pplus under nwell: 4998954000 nm^2

annulus_not_slab:           FAIL: the block-level n-well ring has no hole
hole_contains_subblocks:    FAIL: the block-level n-well reaches into its own hole
no_active_under_nwell:      FAIL: NMOS gate-crossing active area is inside n-well
pplus_not_engulfed:         FAIL: substrate-tie pplus falls under the block-level n-well ring
own_ntap_inside_well:       PASS

4 of 5 checks FAILED under the injected fault, 1 still passed
```

4 of the 5 geometric checks fail under the injected fault; the 5th
(`own_ntap_inside_well`) correctly still passes — a filled slab still
encloses its own tap band, since it encloses everything. The measured
79,070,000 nm² of NMOS gate-crossing active area under `nwell` matches the
number PR #333 originally shipped exactly (same devices, same defect
construction), confirming this is the same failure class, reproduced.

`klt ring-check` on the same injected-fault GDS independently confirms the
same defect, at the tool layer this issue's "Notes" section already credited
as correct:

```
$ klt ring-check --layers '[[21,0]]' --ignore-enclosed vco_block.gds   # injected-fault build
status: broken
violations: 1
no_hole  vco_block  21/0  (-19940,-11020)-(163240,159260)  ring layer set is a
  solid, hole-less region, not an annulus: no closed loop encloses an interior
```

## Verification after the fix (current `main` geometry, unpatched)

```
$ python3 -m pytest layout/tests/  -> 349 passed
```

`AssembledVcoBlockNwellRingGeometryTests` (5 tests) and
`RectFramePrimitiveTests` (3 tests) are all in that count and all pass.

```
$ python3 layout/run_pv.py drc /tmp/vco339/vco_block.gds --top vco_block --run-dir <run>
DRC clean: vco_block (D), 0 violations
```

```
$ python3 -c "from pll_top.vco import block; block.connectivity_report(block.build())"
connectivity: PASS  (all 14 CONNECTED_PROBES, 4 DISTINCT_PROBES ok)
```

```
$ klt ring-check --layers '[[21,0]]' --ignore-enclosed vco_block.gds
status: continuous
violations: 0
```

(`--ignore-enclosed` is required here because the whole-GDS n-well layer also
carries each of the five sub-blocks' own PMOS wells inside the block ring's
hole — five separate polygons that `ring-check` would otherwise (correctly)
flag as fragments of a 6-piece "ring" without it. The block-level ring itself
is confirmed a genuine single annulus either way: this only suppresses the
sub-blocks' own enclosed n-well shapes from the ring computation, and a real
break in the ring's own perimeter still fails with the flag set, per the
tool's own `--help` text.)

### No GDS drift

`rect_frame()`'s four-band construction is algebraically identical to the
four `canvas.rect()` calls it replaces in `block.py` (same corner-overlapping
band coordinates, same layer, same order) — confirmed, not just argued: the
regenerated `vco_block.gds` was XOR'd per-layer against the committed copy
in this directory and is empty on every layer.

```
$ python3 -c "
import klayout.db as db
a = db.Layout(); a.read('evidence/vco-layout/vco_block.gds')
b = db.Layout(); b.read('<regenerated>/vco_block.gds')
... per-layer db.Region XOR over both cells ...
"
total layers with diffs: 0
```

No committed GDS file changed as part of this increment — this is a
verification-only change, per the issue's own acceptance criteria.

## Acceptance criteria, checked

| Issue #339 AC | Where |
|---|---|
| A test in `layout/tests/` fails when the block-level n-well is drawn as a filled rect instead of an annulus, and passes on current `main` | `AssembledVcoBlockNwellRingGeometryTests::test_the_block_level_nwell_is_an_annulus_not_a_slab`, `::test_the_annulus_hole_contains_every_sub_block` — pass on `main`'s #337 geometry, fail under injection above |
| A test in `layout/tests/` fails when any NMOS gate-crossing active area falls under `nwell`, and passes on current `main` | `::test_no_nmos_active_area_anywhere_in_the_block_sits_under_nwell` — pass on `main`, fail under injection above |
| The failure mode is demonstrated by injection, not asserted; injected-defect output recorded | "Fault injection: the gate is real, not decorative" above |
| Existing `layout/tests/` stay green; no committed GDS changes (or report any that occur) | 349 passed; "No GDS drift" above — 0 layers differ |

## klayout-tools friction: none new

`klt ring-check`'s `--ignore-enclosed` flag (needed here because the
whole-GDS `nwell` layer also carries five sub-blocks' own enclosed PMOS
wells) already existed and did exactly what this check needed — no gap
filed. Per this repo's friction protocol, this is recorded because the flag
was reached for, not because it was missing.

## What is still not proved

Unchanged from `PROOF-fold.md` / `PROOF-block.md`: no block-level LVS, no
post-layout parasitic extraction, `sim/` remains pre-layout. This increment
narrows the gap LVS would eventually close (an n-well/device-placement
defect that today can only be caught by LVS or a manual KLayout session now
also fails CI), it does not replace the need for LVS.

This increment's own scope is deliberately narrow: `rect_frame()` is added to
`layout/pll_top/vco/primitives.py` only, and the geometric regression tests
are not extended to `lock_detector`, `pfd_cp`, or `divider_chain` — issue
#339 explicitly scoped that generalization as optional. As of this
increment none of those three modules has an assembled, multi-sub-block
`block.py` with its own block-level well ring the way `vco/block.py` does
(their own `canvas.rect("nwell", ...)` calls, grepped at the same time as
this PROOF was written, are all per-device PMOS-well rects, one device per
call — the narrower pattern that is not this defect class). The same
reasoning applies the day any of them grows a block-level well ring of its
own; this is left for a follow-up at that point rather than pre-built now.
