# VCO block — band-mirror row fold + block-level n-well guard ring (issue #324)

Companion to [`PROOF-block.md`](PROOF-block.md), which recorded the assembled
block as it stood after issue #293's final increment (PR #325). That record
disclosed two coupled things it deliberately did **not** close, and named them
as one follow-up:

1. the block-level guard ring was `GND_VCO` substrate-only, not the
   "real two-sided ring" `PLL-FLOORPLAN.md` §1 asks for; and
2. every VCO sub-block was a single device row, so the band-select mirror
   alone (266 µm wide) set the whole block's width and its 2.6–4.0× overrun
   against `PLL-FLOORPLAN.md` §5's ROM area row.

They are the same increment because folding pays for the ring. **This is that
increment.** The mirror's device rows are folded into two stacked banks, and
part of the width that buys is spent on the missing n-well band.

## Result

| | Before (PR #325) | After (this increment) | Δ |
|---|---|---|---|
| `vco_bandsel_mirror` | 269.86 × 37.12 µm (10,017 µm²) | **152.64 × 53.02 µm (8,093 µm²)** | −43 % width, −19 % area |
| `vco_block`, fold only | 294.78 × 148.18 µm (43,680 µm²) | 176.98 × 164.08 µm (29,039 µm²) | −40 % width, −34 % area |
| `vco_block`, + n-well ring | — | **183.18 × 170.28 µm (31,192 µm²)** | −38 % width, −29 % area |
| Block guard ring | `GND_VCO` substrate only | **`GND_VCO` + concentric `VDD_VCO` n-well tap ring** | §1 criterion closed |
| Widest sub-block | mirror, 269.86 µm | mirror, 152.64 µm | still the mirror |

The n-well ring costs 3.1 µm per side (`NWELL_RING_GAP_UM` 1.5 + a 1.6 µm
n-well band), i.e. +6.2 µm on each axis — less than the ≈8.8 µm of width
`PROOF-block.md` budgeted for it, because that estimate assumed the band would
also need its own outer margin before the block boundary. It does not: the band
*is* the block boundary now, and `PLL-FLOORPLAN.md` §1's 15 µm keep-out (which
`skeleton.py` already draws) is what separates it from whatever abuts the
block — comfortably above `NW.2b_LV`'s 1.4 µm n-well-to-n-well spacing.

```
$ python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_block.gds \
      --top vco_block --run-dir <run> --offgrid
DRC clean: vco_block (D), 0 violations

$ python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_bandsel_mirror.gds \
      --top vco_bandsel_mirror --run-dir <run> --offgrid
DRC clean: vco_bandsel_mirror (D), 0 violations
```

| Item | `vco_block` | `vco_bandsel_mirror` |
|---|---|---|
| PDK | gf180mcuD, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` | same |
| KLayout | 0.28.16 | same |
| Deck | the PDK's own `libs.tech/klayout/drc/run_drc.py`, deep mode, `--offgrid` on | same |
| Rules executed | 556 | 556 |
| Polygons in the design | 13,366 | 3,868 |
| Violations | **0** | **0** |

Artifacts: `vco_block.gds`, `vco_bandsel_mirror.gds`,
`drc-clean/drc-block.stdout.log`, `drc-clean/drc-mirror.stdout.log`,
`drc-clean/vco_block_main.lyrdb`,
`drc-clean/vco_bandsel_mirror_main.lyrdb`,
`drc-clean/connectivity-block.log`.

## What "folded" means here — a bank, not a coordinate shift

`mirror.py` has always drawn one **NMOS row / Metal2 channel / PMOS row**
stack, with every inter-device net given a horizontal Metal2 track in that
channel and a short Metal1 escape column from each device pad up or down to
its track ("mesh, not a chain" — see that module's docstring, and
`vtoi_core.py`'s, for why a single metal is provably not enough here).

The fold stacks **two complete such banks**. It is not a coordinate shift,
because the mesh is per bank: each bank's channel carries only the tracks its
own two rows need, and each bank re-derives its own lo/hi track split from its
own devices. Concretely:

| | Bank 0 (`lower`) | Bank 1 (`upper`) |
|---|---|---|
| PMOS row | `MIP0`, cascade A, `MSWA0/1`, `MIP1`, `MDB`, `MIP2`, `MSWC0/1` | cascade C, `MDP` |
| NMOS row | `MIN0`, `MDA`, cascade B, `MSWB0/1`, `MIN1`, `MIN2` | `MDN`, `MMN` |
| PMOS row width | 115.02 µm | 128.58 µm |
| NMOS row width | 61.11 µm | 11.40 µm |
| Channel | 16.0 µm (12 lo + 12 hi tracks) | 4.8 µm (4 + 4) |

Against a single flat PMOS row of 248.10 µm. The split is by **cascade
section**, not by width alone, and that choice is what keeps the routing cost
of the fold at essentially zero: only **two nets cross a bank boundary at
all** — `VBP2` (`MDB`/`MSWC0` in bank 0 feeding cascade C's always-on gate in
bank 1) and `GC` (cascade C's mux, in bank 0, feeding its switched gate).
`test_only_two_nets_cross_a_bank_boundary` pins that property.

A cross-bank net costs exactly one extra Metal1 **link column** in the strip
right of every bank's rows — which is where a net escaped from both rows was
*already* being joined before the fold. 11 link columns now, against 10
before. The column is drawn from the net's lowest track to its highest with a
via1 on each, so one column serves any number of banks.

### Three new pieces of geometry, and the rule each one answers

| Piece | Why | Rule / margin |
|---|---|---|
| Per-bank n-well + `VDD_VCO` tap band | Each bank's PMOS row is its own well | unchanged per-bank arithmetic; worst pfet-to-tap distance still **4.60 µm** |
| `sub_tap`: a `GND_VCO` substrate tap strip under every bank above the first | Bank 0's NMOS sources tie into the outer ring's bottom band, which is directly below them; bank 1 has no such band in reach | `BANK_NWELL_TO_TAP_UM` = 1.5 µm to the bank below's n-well (`DF.16_LV` min 0.43); `BANK_TAP_TO_NMOS_UM` = 1.0 µm to the NMOS comp above (`DF.3a_LV` min 0.28, and enough that the two islands' implants also clear by `PP.2`/`NP.2`'s 0.4 µm) |
| That strip **butted into** the block's own guard-ring left band | So it is one continuous pcomp shape with the ring, not an island relying on substrate conduction — and so the metal extraction sees one `GND_VCO` net | proved, not asserted: `connectivity_report()` probes the strip (see below) |

Worst-case nfet-to-substrate-tap distance is **6.52 µm**, unchanged: folding
does not lengthen it, because each new bank brings its own tap strip with it.

### Why the two banks' track groups cannot interact

`mirror.py`'s original invariant — every NMOS escape column ends below every
PMOS escape column starts, so two columns from different rows can never
overlap whatever their x — is a *per-bank* property now, and the tests assert
it bank by bank rather than globally. Globally it is deliberately false: bank
1's lo tracks sit above bank 0's hi tracks.

Across banks the same guarantee comes from the geometry instead: bank 1's NMOS
row starts at y = 30.80 µm, above everything bank 0 draws (its n-well tops out
at 27.70 µm). `test_banks_do_not_overlap_in_y` asserts both halves of that.

`Plan.reserve()` — the Metal1 spacing guard that raises a Python exception
naming both nets rather than letting a short reach DRC — is block-wide, not
per bank, so it also covers the one genuinely new neighbour relationship the
fold introduces: a link column that now spans several banks' worth of y.

## The block guard ring is two-sided now

`PLL-FLOORPLAN.md` §1: "tied to `GND_VCO` on the substrate side and to a local
`VDD_VCO`-tied n-well tap ring on the p-well side … a real two-sided ring, not
a substrate-only one."

Both bands are drawn, concentric:

| Band | Net | Geometry |
|---|---|---|
| inner | `GND_VCO` | p+ substrate ring, 1.2 µm bands, `placement().outer` |
| outer | `VDD_VCO` | n-well ring 1.6 µm wide (`NW.1a_LV` min 0.86), carrying a 0.6 µm n+ tap ring inset 0.5 µm from each n-well edge (`DF.4d_LV` min 0.12), 1.5 µm clear of the substrate ring's comp (`DF.16_LV` min 0.43) |

`footprint_um()` is the **outer** band's box now; `placement().outer` is still
the substrate ring, so every check that is really about "inside the block's
guard ring" (sub-block containment, decap placement) is unchanged.

**The n-well band goes outside on purpose.** In a p-substrate flow with no
deep n-well, the p+ ring is what the devices' own sources already tie into, so
it belongs closest to them; the reverse-biased well/substrate junction belongs
outside it, collecting what gets past. Putting it inside would also mean
threading a well band between the substrate ring and five sub-block rings that
are already strapped to that ring in Metal1.

It is fed the same way every sub-block's tap band is: one Metal2 hop from the
Metal1 supply trunk, hopping over the substrate ring on the layer that has no
spacing relationship with it. One feed is enough for the whole ring because
`primitives.guard_ring()` draws all four bands as one continuous Metal1 shape
— and that claim is *checked*, not assumed: the connectivity probe lands on
the band **opposite** the feed.

Every n-well *inside* the block remains `VDD_VCO`-tied by its own sub-block's
tap band, worst case 12.1 µm (the V-to-I core's PMOS band, set by `MSU1`'s
deliberately long L = 20 µm channel), inside §1's own 15 µm bound. That half
of §1's sentence was already satisfied before this increment and still is.

## Connectivity is still proved, and the proof grew two probes

DRC alone would not catch a Metal2 wire that stops 0.5 µm short of its via1.
`block.connectivity_report()` runs KLayout's own `LayoutToNetlist` extraction
over metal1/via1/metal2 and probes both ends of every route
(`drc-clean/connectivity-block.log`):

```
  ok   VDD_VCO   supply trunk <-> four n-well tap bands + the block n-well ring: 6 probe(s) -> one net
  ok   GND_VCO   block guard ring <-> every sub-block guard ring + bank tap strips: 7 probe(s) -> one net
  ...
connectivity: PASS
```

Two probes are new, one per new piece of geometry:

* **`VDD_VCO` on the n-well ring's left band** — opposite its single Metal2
  feed on the right, so a break anywhere round the ring shows up.
* **`GND_VCO` on the mirror's bank-1 substrate tap strip** — which is only on
  the block's `GND_VCO` net if the butt joint into the mirror's own ring
  really merged. A strip that merely abutted on paper would come back as a
  separate cluster.

**Both are real gates**, verified the same way the DRC run is — suppress
exactly one via1, leave the layout DRC-clean, and the check must fail:

```
  [neg-control] suppressed via1 at (56.2, 141.84) -- Y5 -> the output buffer's input gate
  FAIL Y5        ring stage-5 output <-> output buffer input gate: 2 probe(s) -> 2 separate nets [21, 23]
  [neg-control] suppressed via1 at (162.44, 43.7) -- VDD_VCO -> the block-level n-well tap ring
  FAIL VDD_VCO   supply trunk <-> four n-well tap bands + the block n-well ring: 6 probe(s) -> 2 separate nets [1, 9]
```

And the DRC run is a real gate on the folded geometry specifically — the same
`layout/harness/faults.py` injection this repo uses everywhere else, applied
to **both** changed cells:

```
$ ...faults.inject_drc_violation('vco_bandsel_mirror.gds', '<tmp>_drcfault.gds')
inserted a 0.10 x 2.00 um Metal1 rectangle at (3.0, 7.0) um -- below the 0.23 um minimum Metal1 width
$ python3 layout/run_pv.py drc <tmp>_drcfault.gds --top vco_bandsel_mirror --run-dir <run> --offgrid
DRC violations: vco_bandsel_mirror (D), 1 item(s) -- M1.1x1

$ ... same injection into vco_block.gds ...
DRC violations: vco_block (D), 1 item(s) -- M1.1x1
```

## The other four standalone proofs are unaffected — verified, not assumed

Only `mirror.py` changed; `primitives.py`, `devices.py`, `ring.py`,
`buffer.py`, `bias_resistors.py` and `vtoi_core.py` are untouched. That is a
claim about generated geometry, so it was checked the way every prior VCO
increment checked it: regenerate all six GDS files and XOR the result against
the artifact already committed here, per layer, on merged polygon count and
merged area.

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
(`vco_bandsel_mirror.gds`, `vco_block.gds` and their
`drc-clean/*.stdout.log` / `drc-clean/*.lyrdb`). The four unchanged cells'
committed artifacts are left exactly as they were: their regenerated GDS
differs from the committed bytes in **16 bytes each**, all of them the GDS
`BGNLIB`/`BGNSTR` timestamp fields, with identical file size and an empty XOR
on every layer — re-committing that is binary churn, not evidence. Same
convention PR #325 used when it regenerated and compared these same five.

## Area: the budget margin improves, and a prior arithmetic slip is corrected

`PLL-FLOORPLAN.md` §5 budgets the whole VCO at **0.011–0.017 mm²** (ROM). The
real block is now **0.0312 mm²** — still an overrun, but **1.8–2.8×** rather
than 2.6–4.0×.

Re-running §5's own conservative arithmetic with the measured VCO number in
place of its ROM row:

| | Loop filter | VCO | PFD/CP | Divider+lock | Subtotal | ×1.25 | Margin vs 0.15 mm² |
|---|---|---|---|---|---|---|---|
| §5's ROM (conservative) | 0.0369 | 0.017 | 0.020 | 0.0052 | 0.0791 | 0.0989 | ≈34 % |
| Pre-fold measurement | 0.0369 | 0.0437 | 0.020 | 0.0052 | 0.1058 | 0.1323 | ≈**12 %** |
| **Post-fold measurement** | 0.0369 | **0.0312** | 0.020 | 0.0052 | **0.0933** | **0.1167** | ≈**22 %** |

> **Correction.** `PROOF-block.md` and the previous revision of
> `skeleton.py`'s docstring quoted the pre-fold row as "≈0.111 mm² subtotal,
> ≈0.139 mm² after ×1.25, margin ≈7 %". Its own four terms sum to 0.1058, not
> 0.111. The corrected pre-fold margin is ≈12 %. Recorded rather than quietly
> restated: the conclusion those numbers supported — that real VCO layout had
> eaten most of the margin and folding was the fix — is unchanged, and the
> direction of this increment's effect (+10 points of margin) does not depend
> on which of the two before-numbers is used.

`skeleton.total_extent_um2()` — the whole-skeleton bounding box, a
deliberately looser number than the budget table — goes from **148,157 µm²**
(≈1.2 % under the 150,000 µm² draft target) to **126,395 µm²** (≈16 % under).
`test_skeleton_bounding_box_headroom_against_the_draft_budget` and
`test_the_row_fold_actually_reduced_the_block_footprint` assert both a floor
and a ceiling on that, so a regression that unfolds the mirror trips a test
rather than passing quietly.

**Height was the currency width was bought with.** The block grew from
148.18 µm to 170.28 µm tall. That is affordable and is not a hidden cost: the
skeleton's own height is set by `LOOP_FILTER`'s 195 µm, not by the VCO, so
block height below 195 µm costs the floorplan nothing at all — and
`test_the_row_fold_actually_reduced_the_block_footprint` asserts the block
stays under it.

## Acceptance criteria, checked

| Issue #324 AC | Where |
|---|---|
| At least one sub-block refolded from a single row into multiple rows, reducing the assembled block's width | `mirror.py`'s `BANKS`; 294.78 → 176.98 µm before the ring, 183.18 µm after |
| The recovered width funds a block-level `VDD_VCO` n-well tap ring, ≥`NW.1a_LV` wide, `DF.4d_LV`/`DF.16_LV`-clear, concentric with the `GND_VCO` ring | `block.py` step 8b + `NWELL_RING_*`; `test_the_guard_ring_is_two_sided_and_concentric`, `test_nwell_ring_meets_the_nwell_and_tap_rules_it_cites`, `test_nwell_ring_clears_every_sub_block_nwell_by_nw2b` |
| `block.py` regenerates DRC-clean and `connectivity_report()` still passes for every net | above; 0 violations, `connectivity: PASS`, with negative controls for both |
| `skeleton.py`'s `VCO_CORE` and `total_extent_um2()` updated; area-budget margin change stated | `VCO_CORE` derives from `footprint_um()` so it tracks automatically; the docstring's stated numbers and the budget arithmetic are updated, and the margin change (≈12 % → ≈22 %) is stated above |
| Before/after footprint recorded; the five standalone per-sub-block proofs regenerated + XOR-compared and confirmed unaffected | this document, "Result" and "The other four standalone proofs" above |

## klayout-tools friction: none new

Per this repo's friction protocol, tool gaps hit while drawing real geometry
get filed generically on `2AMLogic/klayout-tools`. This increment hit none. It
is the same three operations every prior VCO-layout increment used — build
geometry against `klayout.db`, extract connectivity with KLayout's own
`LayoutToNetlist`, run the PDK's own DRC deck — plus one XOR comparison
(`db.Region.__xor__` on merged per-layer regions), which is a one-line
KLayout API call, not a missing capability. Nothing here wanted a tool that
does not exist.

## What is still not proved

* **LVS.** No block-level SPICE netlist, no device recognition. The
  connectivity check covers interconnect only. `mirror.py`'s one deliberate
  layout-vs-netlist deviation (cascade B's legs folded 1 → 2 fingers, total
  W/L and device count preserved) is untouched by this increment and still
  has to be reconciled by a future LVS increment.
* **Extraction / post-layout simulation.** Nothing here says what the drawn
  parasitics do to DR-003's tuning range or jitter. The fold changes the
  mirror's internal wire lengths — cascade C's drain now reaches the output
  mirror through a link column rather than along one row — so post-layout
  numbers for this block will differ from the pre-fold geometry as well as
  from pre-layout. `sim/` remains pre-layout.
* **Further area.** The mirror is still the widest sub-block at 152.64 µm,
  and cascade C alone is 115.18 µm of that. Another row split cannot go below
  that; a 2-D common-centroid array for cascade C could. The other four
  sub-blocks are all narrower than the folded mirror (ring 75.4 µm, buffer
  31.65 µm, resistors 13.0 µm, V-to-I core 121.18 µm), so folding any one of
  them alone buys nothing at block level. Filed as **#336**, with the
  measured numbers and the routing question a 2-D array has to answer.
* **Top-level assembly.** Wiring this block into `pll_top` alongside the
  PFD/CP, divider chain and lock detector is issue #297.
