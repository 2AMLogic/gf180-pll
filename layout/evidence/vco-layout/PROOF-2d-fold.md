# VCO band mirror — 2-D common-centroid array for cascades A and C (issue #336)

Companion to [`PROOF-fold.md`](PROOF-fold.md) (issue #324), which named this
exact follow-up in its own "What is still not proved" section: after #324
folded the mirror into two stacked banks, cascade C alone (115.18 µm, nine
fingers in one row) was still alone in its own bank's PMOS row, so *another
row split* could not shrink it further — "a 2-D common-centroid array for
cascade C could."

## Result

| | Before (#324, PR #337) | After (this increment) | Δ |
|---|---|---|---|
| Cascade A array | 1×4, 52.72 µm wide | **2×2, 29.50 × 8.40 µm** | −44 % width |
| Cascade C array | 1×9, 115.18 µm wide | **3×3, 38.02 × 12.80 µm** | −67 % width |
| `vco_bandsel_mirror` | 152.64 × 53.02 µm (8,093 µm²) | **115.86 × 66.22 µm (7,672 µm²)** | −24 % width, +25 % height, −5.2 % area |
| `vco_block` | 183.18 × 170.28 µm (31,192 µm²) | **172.52 × 183.48 µm (31,654 µm²)** | −5.8 % width, +7.8 % height, **+1.5 % area** |
| Widest sub-block | mirror, 152.64 µm | mirror, 115.86 µm — likely no longer the widest (see below) | |

**The headline number is the area line, and it is not a win.** The mirror
itself gets *smaller* (−5.2 %) because folding removes more inter-finger gap
than the two new inter-row gaps (`CC_ROW_GAP_UM` = 0.4 µm each) cost. But the
*assembled block's* area grows slightly (+1.5 %), because the mirror's new
13.2 µm of height has nothing else in its own row of sub-blocks to absorb it
into — unlike #324's width-for-height trade, which was free because the
block's height was already set by `LOOP_FILTER`'s 195 µm budget with room to
spare. That headroom is smaller now (170.28 → 183.48 µm of `LOOP_FILTER`'s
195 µm budget line, ≈87 % → ≈94 % used) but still comfortable — 11.52 µm of
margin remains.

**Recorded as what it is**: a real, DRC-clean width reduction that retires
cascade C as the mirror's own width bottleneck and the "another row split
can't go below it" dead-end #324 disclosed — but, on its own, essentially
area-neutral at the block level (+1.5 %, inside rounding of the stated
budget-margin percentage — see "Area" below).

## Why cascades A and C, and why 2×2 / 3×3

Cascade B (nfet, 1×4, `A S S A`) is untouched: it was never the mirror's
width bottleneck (22.61 µm, smaller than either A or C even before this
increment), so folding it would not move the mirror's own width at all —
the same "folding a narrower sub-block buys nothing" reasoning #324's PROOF
already applied at the block level, applied here one level down.

Both A and C fold on the same construction: a grid whose pattern is
symmetric under 180-degree rotation about its own centre (`A S` / `S A` for
cascade A; `S S S` / `S A S` / `S S S` for cascade C, MC0's single finger at
the grid's centre cell — its centroid *is* the centre). `col_widths_um()`
gives every column the width of the widest finger any row places there, so
cascade A's own unequal per-finger widths (26.5/2 = 13.25 µm always-on,
17.225/2 = 8.6125 µm switched — both legs are `nf=2` in the frozen netlist,
so no layout-side folding of the finger count is needed) pay uniform-pitch
slack exactly the same way cascade C's unequal legs (12.3 / 9.85 µm) do — the
issue's own "exercises the uniform-column-pitch question" rationale for
doing A first, cheaply, before C.

Measured against the issue's own back-of-envelope estimate: cascade C was
predicted to land "roughly 3 × 12.3 + 2 × `CC_FINGER_GAP_UM` ≈ 43 µm" and
measures **38.02 µm** — better than predicted, because the estimate's
worst-case assumption (every column paying MC0's 12.3 µm) is pessimistic:
only the *centre* column actually holds an MC0 finger in any row (see
`col_widths_um()`'s own docstring), so the two outer columns pay only
`MC1`'s 9.85 µm each.

## The routing: a second, local Metal2 hop, confined to the array's own footprint

This is where the issue's risk was named to live, and where the mechanism
had to answer the same "N nets across one span" question the single-row
array already answers (see `mirror.py`'s module docstring, "ROUTING") a
second time, in the other axis.

**Gate buses stay Metal1.** Every row's own gate bus for a given leg already
terminates at the same x (`ARRAY_LEFT_ESCAPE_UM`/`ARRAY_RIGHT_ESCAPE_UM`
past the array, in a lane no finger footprint ever reaches), so one Metal1
vertical spanning every row that owns that leg T-joins them into one node
with no via at all — cascade C's centre-only "A" leg (present in exactly one
row) reduces this to a no-op, correctly.

**S/D buses need a real hop.** A row's own S/D bus spans its full width, so
two rows' S/D pads only ever line up *inside* the array's own inter-column
gaps — which `col_box_x0_um()` guarantees are finger-free in every row by
construction, so the same two gap positions the pre-#336 single-row array
already used for its own escape points still work unchanged. Each row's own
pad gets a via1 up to a short Metal2 vertical spanning every row that needs
tying, and a via1 back down at the other end (`draw_cc_array()`'s
`_tie_rows()`). This hop is self-contained: it never leaves the array's own
x-span, so it cannot reach the bank's own Metal2 channel — which lives in a
completely different y band, between the NMOS and PMOS rows, not inside one
array's own footprint (the issue's own warning: "do not assume the Metal2
channel can absorb it — that channel is per bank and sits *outside* the
array").

**`Plan.reserve()` proves the spacing, generalized rather than bypassed.**
`reserve()` grew a `layer` parameter (`"metal1"` default, `"metal2"` for the
new risers) rather than gaining a second, separate spacing check — the two
layers are never compared against each other (matching the physical
reality: Metal1 and Metal2 shapes have no DRC spacing relationship absent a
via1 joining them), but every riser is still registered and proven clear of
every *other* net's riser on its own layer before DRC ever sees the GDS.

## Connectivity: DRC cannot see a riser that stops short of its own via1

The routing claim above — that an R-row array's per-row buses really are
one electrical node, not R separate islands that happen to sit near each
other — is new geometry no existing check covers: a Metal2 wire 0.01 µm
short of its via1 is DRC-clean and completely disconnected.
`mirror.connectivity_report()` (new) probes **every row** of every
multi-row array's own internal tie, not just the two end rows, because an
interior row's own broken via would leave the end-to-end riser electrically
intact (the Metal2 spine between the two *end* rows never touched that via)
while silently isolating the interior row — a fault a first/last-row-only
probe set would miss.

```
$ python3 -c "import layout.pll_top.vco.mirror as m; r = m.build(); \
    [print(n, ok, d) for n, ok, d in m.connectivity_report(r)]"
VBN1 (A)   True  2-D array internal tie: 2 probe(s) -> one net
VDD_VCO (A) True  2-D array internal tie: 2 probe(s) -> one net
VBP0 (A)   True  2-D array internal tie: 2 probe(s) -> one net
GA (A)     True  2-D array internal tie: 2 probe(s) -> one net
VBN (C)    True  2-D array internal tie: 3 probe(s) -> one net
VDD_VCO (C) True  2-D array internal tie: 3 probe(s) -> one net
GC (C)     True  2-D array internal tie: 3 probe(s) -> one net
```

**Negative control — the middle row, not an end row, and the check catches
it**: with the layout otherwise unmodified and still DRC-clean, suppressing
the single via1 that ties cascade C's *interior* (row 1 of 3) `VBN` S/D pad
into its own riser:

```
[neg-control] suppressed via1 at (10.86, 50.11) -- VBN (C), row 1 of 3, interior row
FAIL VBN (C)   2-D array internal tie: 3 probe(s) -> 2 separate nets [15, 18]
```

Every other net's report is unaffected by this one suppression (confirming
the probe is scoped correctly, not just reporting "something broke"
globally). `MirrorConnectivityTests` in `test_vco_layout.py` pins the clean
result; `test_cascade_c_middle_row_is_probed_not_just_the_two_ends` pins
that the probe count (3, not 2) actually reaches the interior row.

The assembled block's own pre-existing connectivity negative controls (from
`PROOF-fold.md`) were re-run against the regenerated `vco_block.gds` to
confirm they still catch a break in geometry #336 did not touch:

```
[neg-control] suppressed via1 at (56.87, 133.96) -- Y5 -> the output buffer's input gate
FAIL Y5      ring stage-5 output <-> output buffer input gate: 2 probe(s) -> 2 separate nets [20, 23]
```

(Coordinates shift from `PROOF-fold.md`'s because the block's own extent
changed; the mechanism and the result — a clean layout the check correctly
rejects once one via is missing — are unchanged.)

## `check_common_centroid()`, generalised to 2-D — and still a check that can fail

`devices.CascadePair.pattern` is now a grid of rows rather than a flat
tuple; a 1-row grid (cascades A pre-#336, B) is the special case this
generalises from. `check_common_centroid()` requires the grid be symmetric
under 180-degree rotation about its own centre — the condition that proves
both legs' centroids coincide with the array centre in *x and y*
regardless of the legs' unequal finger widths, generalising the old flat
palindrome check (`pattern[c] == pattern[C-1-c]`) to
`pattern[r][c] == pattern[R-1-r][C-1-c]`. Cascade A's own `A S` / `S A` grid
is the sharpest test of this generalisation: *neither individual row* is a
palindrome, but the grid is 180-degree-rotation-symmetric, which is why
rotation symmetry — not "every row and the row order are each separately a
palindrome" — is the condition that is actually general enough.

`CommonCentroidTests` (generalised) keeps both negative controls a real
check needs:

* **row-placed** (`A A` / `S S`, the 2-D analogue of a flat `A A S S`) —
  `check_common_centroid()` raises `ValueError` (correctly rejected: it is
  rotation-symmetric-looking only if compared to itself, not against the
  interdigitation run-count test, which reduces to 2 runs and fails); and
* **centroid-skewed** (MC0's finger moved off the grid's own centre cell,
  breaking rotation symmetry while still being "a single always-on finger
  among eight switched ones") — raises `ValueError`.

```
$ python3 -m pytest layout/tests/test_vco_layout.py -q
132 passed
```

## DRC: both changed cells clean, and the injected-fault negative control still fires

```
$ python3 -m layout.pll_top.vco.mirror --outdir <out>
wrote vco_bandsel_mirror.gds
footprint: 115.860 x 66.220 um (7672.2 um^2)

$ python3 -m layout.pll_top.vco.block --outdir <out> --check-connectivity
wrote vco_block.gds
footprint: 172.520 x 183.480 um (31654.0 um^2)
... (all 17 connectivity checks) ok
connectivity: PASS

$ python3 layout/run_pv.py drc <out>/vco_bandsel_mirror.gds \
      --top vco_bandsel_mirror --run-dir <run> --offgrid
DRC clean: vco_bandsel_mirror (D), 0 violations

$ python3 layout/run_pv.py drc <out>/vco_block.gds \
      --top vco_block --run-dir <run> --offgrid
DRC clean: vco_block (D), 0 violations
```

| Item | `vco_block` | `vco_bandsel_mirror` |
|---|---|---|
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` | same |
| KLayout | 0.28.16 | same |
| Deck | the PDK's own `libs.tech/klayout/drc/run_drc.py`, deep mode, `--offgrid` on | same |
| Rules executed | 556 | 556 |
| Polygons in the design | 12,891 | 3,367 |
| Violations | **0** | **0** |

Injected-fault negative control (`layout/harness/faults.py`'s
`inject_drc_violation`, the same generic Metal1-undersize injection every
prior VCO increment uses), against **both** regenerated cells:

```
$ ...faults.inject_drc_violation('vco_bandsel_mirror.gds', '<tmp>_drcfault.gds')
inserted a 0.10 x 2.00 um Metal1 rectangle at (3.0, 7.0) um -- below the 0.23 um minimum Metal1 width
$ python3 layout/run_pv.py drc <tmp>_drcfault.gds --top vco_bandsel_mirror --run-dir <run> --offgrid
DRC violations: vco_bandsel_mirror (D), 1 item(s) -- M1.1x1

$ ... same injection into vco_block.gds ...
DRC violations: vco_block (D), 1 item(s) -- M1.1x1
```

Artifacts (regenerated, replacing the #324-era committed bytes): `vco_bandsel_mirror.gds`,
`vco_block.gds`, `drc-clean/drc-mirror.stdout.log`, `drc-clean/drc-block.stdout.log`,
`drc-clean/vco_bandsel_mirror_main.lyrdb`, `drc-clean/vco_block_main.lyrdb`.

## The other four standalone proofs are unaffected — verified, not assumed

Only `mirror.py` (plus `devices.py`'s `CascadePair.pattern` values) changed;
`primitives.py`, `ring.py`, `buffer.py`, `bias_resistors.py` and
`vtoi_core.py` are untouched. Checked the same way every prior VCO increment
checked it: regenerate all six GDS files and XOR the result against the
committed artifact, per layer, on merged region area.

| Cell | Result |
|---|---|
| `vco_ring` | **identical** — XOR empty on every layer |
| `vco_out_buffer` | **identical** — XOR empty on every layer |
| `vco_bias_resistors` | **identical** — XOR empty on every layer |
| `vco_vtoi_core` | **identical** — XOR empty on every layer |
| `vco_bandsel_mirror` | changed (this increment's own work) |
| `vco_block` | changed (this increment's own work) |

All six were then re-run through the DRC deck against the freshly generated
GDS: **0 violations each**.

```
DRC clean: vco_ring (D), 0 violations
DRC clean: vco_bandsel_mirror (D), 0 violations
DRC clean: vco_out_buffer (D), 0 violations
DRC clean: vco_bias_resistors (D), 0 violations
DRC clean: vco_vtoi_core (D), 0 violations
DRC clean: vco_block (D), 0 violations
```

Only the two changed cells' artifacts are re-committed here
(`vco_bandsel_mirror.gds`, `vco_block.gds` and their `drc-clean/*` files).
The four unchanged cells' committed artifacts are left exactly as they
were — re-committing bytes that only differ in GDS timestamp fields is
binary churn, not evidence, the same convention `PROOF-fold.md` and PR #325
used.

## Area: the budget margin is essentially unchanged, stated rather than rounded away

`PLL-FLOORPLAN.md` §5 budgets the whole VCO at **0.011–0.017 mm²** (ROM).
The real block is now **0.031654 mm²** — a **1.9–2.9× overrun**, marginally
worse in the stated range than #324's 1.8–2.8× (the assembled block's own
area grew 1.5 %, see "Result" above), not because this increment made the
overrun worse in absolute terms (it did not — it made the block-level number
essentially flat) but because the ROM range's own denominator did not move.

Re-running §5's own conservative arithmetic with the measured VCO number in
place of its ROM row:

| | Loop filter | VCO | PFD/CP | Divider+lock | Subtotal | ×1.25 | Margin vs 0.15 mm² |
|---|---|---|---|---|---|---|---|
| Post-#324 (pre-#336) | 0.0369 | 0.031192 | 0.020 | 0.0052 | 0.093292 | 0.116615 | ≈22.3 % |
| **Post-#336** | 0.0369 | **0.031654** | 0.020 | 0.0052 | **0.093754** | **0.117193** | ≈**21.9 %** |

The margin moves by 0.4 points — unchanged within the rounding both
`skeleton.py`'s docstring and this record state it at ("~22 %"). This is the
number the issue's acceptance criteria ask to be stated explicitly rather
than silently absorbed: **#336 is not the area lever its own motivating
text (from `PROOF-fold.md`) hoped it would be**, because the width it
recovers is spent on height that (unlike #324's) has nothing free to fall
into.

`skeleton.total_extent_um2(BLOCKS_EXCLUDING_DIVIDER_LOCK)` — the VCO-scoped
whole-skeleton bounding box (see that function's own docstring for why the
default, whole-skeleton figure is scoped down here: issue #310/#341 grew the
divider chain to ~9× the size of everything else, which would otherwise
swamp this measurement) — moves from **126,395 µm²** to **124,316 µm²**
(≈17 % under the 150,000 µm² draft target, from ≈16 %) — a small
improvement, because the mirror's height growth is still well inside
`LOOP_FILTER`'s own 195 µm budget line, so it does not move the skeleton's
own overall height at all; only `VCO_CORE`'s own width moving left shrinks
the bounding box slightly.

## What this increment is, and is not

**Is**: a genuine 2-D common-centroid array generator (`draw_cc_array()`,
`check_common_centroid()`, `Plan.reserve()`'s `layer` parameter), proved by
construction (arithmetic centroid equality, generalised negative controls)
and by geometry (DRC, XOR against the four unaffected sub-blocks, a
row-scoped connectivity proof with its own interior-row negative control).
It retires cascade C as the mirror's own width bottleneck, which #324's own
PROOF named as the next thing blocking a row-fold-only strategy.

**Is not**: a block-level area win. The mirror's new height (66.22 µm, up
from 53.02 µm) has no other sub-block in its own row of the assembled block
to share that growth with — unlike #324's width-for-height trade, which was
free because the skeleton's height was set by `LOOP_FILTER`, not the VCO,
with room to spare. There is still room (170.28 → 183.48 µm of the 195 µm
budget line, 11.52 µm left), so this increment does not cost anything at
the floorplan level either — it
is simply not, on its own, the area lever the "Further area" section of
`PROOF-fold.md` was hoping for.

**The V-to-I core is now very likely the practical width floor.** The
mirror's own footprint (115.86 µm) is now narrower than the V-to-I core
(121.18 µm) and close to the V-to-I core + bias-resistors row's combined
140.7 µm (`bias_resistors` and `vtoi_core` sit side by side in the same
sub-block row — see `skeleton.py`'s `SUB_BLOCKS`). A further fold of the
mirror alone would very likely no longer move the block's own width at all;
the next area lever, if any, is on the V-to-I core / bias-resistors side,
not the mirror.

## klayout-tools friction: none new

Per this repo's friction protocol, tool gaps hit while drawing real
geometry get filed generically on `2AMLogic/klayout-tools`. This increment
hit none — the same operations every prior VCO-layout increment used
(`klayout.db` shape construction, `LayoutToNetlist` extraction, `Region`
XOR), plus a second `via1_stack()`/Metal2-hop call that reuses
`primitives.py`'s existing `m2_route()`/`via1_stack()` primitives rather
than needing a new one.

## What is still not proved

Unchanged from `PROOF-fold.md`: no block-level LVS, no post-layout
extraction/simulation, and top-level `pll_top` assembly (issue #297) is
still open. This increment adds one more open question of its own: whether
a further fold on the V-to-I core / bias-resistors side (identified above
as the now-likely width floor) is worth its own routing cost — not
investigated here, since it is outside this issue's own stated scope
(cascades A and C of the mirror).
