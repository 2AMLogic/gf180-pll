# VCO band-select mirror + output buffer — real transistor-level layout DRC runs (issue #293, increment 2)

Companion to [`PROOF.md`](PROOF.md), which records increment 1 (the 5-stage
ring, its guard ring, and the carried-forward 22 pF decap — PR #305). This
file records the next two sub-blocks of the same issue:

| Block | Generator | Top cell | GDS |
|---|---|---|---|
| 3-cascade band-select mirror (`vco_bias.sch`) | `layout/pll_top/vco/mirror.py` | `vco_bandsel_mirror` | `vco_bandsel_mirror.gds` |
| 3-stage tapered output buffer (`vco.sch`) | `layout/pll_top/vco/buffer.py` | `vco_out_buffer` | `vco_out_buffer.gds` |

Both are real device geometry on the PDK's own device/interconnect layers
(`comp` 22/0, `poly2` 30/0, `contact` 33/0, `nplus` 32/0, `pplus` 31/0,
`nwell` 21/0, `metal1` 34/0, and — new in this increment — `via1` 35/0 and
`metal2` 36/0), not the layer-(0,0) `DIEAREA` marker
`layout/floorplan/skeleton.py` uses. Layer choices are confirmed the same way
`PROOF.md` documents: against `nfet_03v3`/`pfet_03v3`'s own recipe in
`$PDK_ROOT/libs.tech/klayout/lvs/rule_decks/mos_extraction.lvs`, and against
`layers_def.drc`'s `get_polygons()` calls for `via1`/`metal2`.

## Scope, disclosed explicitly (issue #293 is still not complete)

| Drawn for real, cumulative | Still deferred |
|---|---|
| 5-stage current-starved ring + its guard ring + 22 pF decap (increment 1) | Bias generator **V-to-I core** (`MP1`/`MP2`/`MN1`/`MN2`/`MSU*`/`MPR`/`MD1`/`MD2`/`MOFF`/`MVI`/`MSUM` + `RCG`/`ROFF`/`RDEG`) |
| 3-cascade band-select mirror, common-centroid, with band muxes, band-code inverters and diode loads (this increment) | Inter-sub-block wiring / a single shared VCO guard ring |
| 3-stage tapered output buffer (this increment) | Combined-block standalone DRC run |

**Why the V-to-I core is the deferral boundary, and not an arbitrary cut**:
three of its elements (`RCG`, `ROFF`, `RDEG`) are `ppolyf_u_3k` poly
resistors — a device class `layout/pll_top/vco/primitives.py` has no
generator for, with its own `PRES`/`sab` rule set to derive from the deck.
Everything drawable from the existing `nfet_03v3`/`pfet_03v3` generator is
drawn. Faking a resistor with a transistor to claim the whole scope would
have been worse than an honest partial. `VBP0` (the summing node that core
produces) is therefore an **input pin** of the mirror block for now.

## Provenance

| | |
|---|---|
| Generated | 2026-09-08T21:08 UTC |
| Invoked as | `python3 -m vco.mirror --outdir layout/evidence/vco-layout` / `python3 -m vco.buffer --outdir …` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc <gds> --top <cell> --run-dir <tmp> --offgrid` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D`, `--offgrid` (signoff-grade — the off-grid check class is included, not skipped) |

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `vco_bandsel_mirror` DRC, table `main`, `--offgrid` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_out_buffer` DRC, table `main`, `--offgrid` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_ring` re-run after this increment's `primitives.py` changes | still clean, geometry unchanged | clean; KLayout XOR against the committed `vco_ring.gds` is **empty on every layer** | **PASS (no regression)** |

The ring re-run matters because this increment changed shared code
(`primitives.py` gained grid snapping, a `w_um`/`sd_overhang` keyword on
`mosfet()`, and via1/metal2 helpers). "The ring still builds" would not have
been enough — the XOR proves the ring's *geometry* is bit-identical, so
`PROOF.md`'s own result still stands unmodified.

Rules this increment newly exercises on top of the ones `PROOF.md` lists:
`M2.1`/`M2.2a`/`M2.3` (metal2 width/space/area), `V1.1` (via1 size — min
**and** max, 0.26 µm), `V1.2a` (via1 space), `V1.3a`/`V1.4a` (metal1/metal2
overlap of via1), and the whole `geom.drc` OFFGRID class against a block
whose device widths are not natural grid multiples (see below).

## The two failures this generator hit, and what they cost

Recorded because both are exactly the class of bug an "it DRC'd clean" claim
hides, and because the fixes are now enforced in code rather than in a
comment:

1. **A metal1 short between two different nets** (13 132-violation first
   run's structural sibling). `MDN`'s drain-pad escape column in the NMOS row
   landed on `MSWA0`'s gate-tab escape column in the PMOS row — the two rows'
   escape columns pass each other in the routing channel, and nothing about
   their x positions is coordinated. Fixed structurally, not by nudging one
   device: the channel's metal2 tracks are split into a lower group reachable
   only from the NMOS row and an upper group reachable only from the PMOS
   row, with a metal1 link column per net in a strip to the right of both
   rows. By construction every NMOS escape now ends below every PMOS escape
   begins (13.40 µm vs 14.20 µm, one full track pitch apart), so the two rows
   cannot interact whatever their x. `mirror.Plan.reserve()` additionally
   fails the *build* — not the DRC run — if any two different nets' metal1
   columns come within `M1.2a`'s 0.23 µm.
2. **13 132 off-grid / `CO.1` / `V1.1` violations.** `geom.drc`'s OFFGRID
   section runs `ongrid(0.005)` on every drawn layer, and this block's
   derived coordinates (a pad midpoint, a bus centreline, a width divided by
   a finger count) land off that grid routinely. `primitives.Canvas._u` now
   snaps every coordinate; contact and via origins are snapped *explicitly*
   on top of that, because `CO.1` and `V1.1` make 0.22 µm and 0.26 µm the
   min **and max** size — an off-grid origin whose far edge rounds the other
   way is a 0.215 µm contact, i.e. a hard violation, not a cosmetic nudge.

## Common-centroid: the claim, and how it is substantiated

`layout/floorplan/PLL-FLOORPLAN.md` §1 requires each cascade to be "a
common-centroid pair (always-on leg interdigitated with its switched leg),
not three separate blobs", because "a mismatch between an always-on and a
switched leg shows up directly as adjacent-band-step error". A matching
mistake DRCs perfectly clean, so DRC evidence alone cannot substantiate this
one — `mirror.check_common_centroid()` proves it arithmetically at build
time and `layout/tests/test_vco_layout.py`'s `CommonCentroidTests` re-check
it, including two **negative controls** (a row-placed `A A S S` pattern and
an asymmetric 9-finger pattern are both rejected).

| Cascade | Legs (schematic W) | Drawn pattern | Array width | Array centre | Always-on centroid | Switched centroid |
|---|---|---|---|---|---|---|
| A (pfet) | `MA0` 26.5 / `MA1` 17.225 µm | `A S S A` | 52.720 µm | 26.360 µm | 26.360 µm | 26.360 µm |
| B (nfet) | `MB0` 5 / `MB1` 8.6125 µm | `A S S A` | 22.610 µm | 11.305 µm | 11.305 µm | 11.305 µm |
| C (pfet) | `MC0` 12.3 / `MC1` 78.87 µm | `S S S S A S S S S` | 115.180 µm | 57.590 µm | 57.590 µm | 57.590 µm |

The stronger property the tests also pin: with a uniform inter-finger gap, a
palindromic pattern makes the whole finger-position sequence mirror-symmetric
about the array centre (`center_i + center_{n-1-i} == array width` for every
`i`), which is what actually cancels a linear process gradient — centroid
equality alone is necessary but not sufficient.

## Two deliberate deviations from the frozen netlist, stated not buried

**1. Cascade B's finger count.** `MB0` and `MB1` are both `nf=1` in
`design/netlist/vco.spice`, and two single-finger devices cannot be
interdigitated at all: a one-finger leg's centroid *is* that finger's centre,
which can never coincide with a different one-finger leg's centre. Each leg
is therefore folded into **2** drawn fingers of half its schematic `W`. Total
`W`, `L` and device count are preserved; only `nf` differs. Cascades A
(`nf=2`/`nf=2`) and C (`nf=1`/`nf=8`) need no folding — C's single `MC0`
finger sits at the array centre with `MC1`'s eight split 4/4 around it.

**2. Grid-quantised widths.** Three per-finger widths are not exact multiples
of the 5 nm manufacturing grid, so the drawn width is the nearest grid point:

| Leg | Fingers drawn | Per-finger W | Drawn total W | Schematic W | Deviation |
|---|---|---|---|---|---|
| `MA0` | 2 (`nf=2`) | 13.250 µm | 26.500 µm | 26.500 µm | 0 |
| `MA1` | 2 (`nf=2`) | 8.610 µm | 17.220 µm | 17.225 µm | −0.029 % |
| `MB0` | 2 (folded from `nf=1`) | 2.500 µm | 5.000 µm | 5.000 µm | 0 |
| `MB1` | 2 (folded from `nf=1`) | 4.305 µm | 8.610 µm | 8.6125 µm | −0.029 % |
| `MC0` | 1 (`nf=1`) | 12.300 µm | 12.300 µm | 12.300 µm | 0 |
| `MC1` | 8 (`nf=8`) | 9.860 µm | 78.880 µm | 78.870 µm | +0.013 % |

Worst case 0.029 %, i.e. ~2.5 nm per finger edge. This is a property of the
schematic's own W values (which came out of a ratio computation and are not
grid-representable), not of the generator; it is recorded here so the future
LVS increment reconciles it deliberately rather than discovering it. The
tests bound it at < 0.05 % and assert every drawn finger width is on-grid.

## Tap pitch (test plan edge case)

Checked independently in pure Python
(`mirror.max_*_tap_distance_um()` / `buffer.max_*_tap_distance_um()`,
`layout/tests/test_vco_layout.py`), not inferred from "the DRC run passed":

| Block | Worst-case PMOS → n-well tap | Worst-case NMOS → substrate tap | Bound (PLL-FLOORPLAN.md §1) |
|---|---|---|---|
| `vco_bandsel_mirror` | 4.60 µm | 6.52 µm | ≤ 15 µm |
| `vco_out_buffer` | 1.24 µm | 3.78 µm | ≤ 15 µm |

Both blocks are single-row layouts with a tap band running their full length
— the mirror's `VDD_VCO` n-well tap band spans the whole PMOS row's top edge,
and the outer `GND_VCO` p-guard-ring's bottom band spans the whole NMOS row —
so the worst case is a device's own far edge, not a corner far from any tap.
The tests assert real headroom (< half the bound), not merely `<= 15`.

The mirror's n-well tap is a **top band plus the ring's own left/right
context**, not a closed four-sided ring inside the well: the bottom edge of
the PMOS row is where every device's drain escape column leaves for the
routing channel, so a bottom tap band there would short every drain to
`VDD_VCO`. `ring.py` made the same trade for the same kind of reason and
`PROOF.md` records it — a closed ring is a stronger shape than
`DF.13_MV`/`DF.14_MV` require, and 4.60 µm is well inside 15 µm.

## Placement requirements from PLL-FLOORPLAN.md §1, and how each is met

| Requirement | How this layout meets it |
|---|---|
| "The output buffer's 3-stage taper … sits at the VCO-block boundary, closest to the `CLK` pin" | `buffer.py` places the stages left→right smallest-first; the ring-facing `Y5` input pin is the left edge, the `CLK` pin the right edge, so the 11.25/4.5 µm stage abuts `CLK`. Asserted against the drawn x's (`test_largest_stage_is_the_one_nearest_the_clk_pin`), not against tuple order. |
| "… farthest from the ring's own starved internal nodes" | Same ordering: the 1.25/0.5 µm first stage is the one nearest the ring, which is `design/README.md`'s stated reason for making it small (a large first inverter injects switching current back into the VCO rail). |
| "The band-select mirror is common-centroid, not row-placed" | See the table above, plus the two negative controls. |
| "Tap pitch ≤ 15 µm everywhere inside the VCO block … not just the block perimeter" | See the tap-pitch table; both blocks' worst case is under a third of the bound. |
| "A dedicated guard ring … tied to `GND_VCO` on the substrate side and to a local `VDD_VCO`-tied n-well tap" | Each block carries its own closed `GND_VCO` p-guard-ring and `VDD_VCO` n-well tap, so each is provable standalone. Merging the three under one shared ring is the remaining integration increment. |

## Footprints vs. the ROM estimate (issue #293 AC — deviation disclosed)

| Block | Real footprint | Area |
|---|---|---|
| `vco_ring` (increment 1) | 177.40 × 18.66 µm | 3 310 µm² |
| `vco_bandsel_mirror` | 269.86 × 37.12 µm | 10 017 µm² |
| `vco_out_buffer` | 31.65 × 13.28 µm | 420 µm² |

All three deviate from PLL-FLOORPLAN.md §5's 140 × 100 µm ROM box in the same
direction and for the same reason: these are single-row full-custom layouts,
each transistor its own diffusion island wired by Metal1 (see
`primitives.py`'s module docstring), so a block the ROM budget imagined as a
compact square comes out as a long thin band.

`layout/floorplan/skeleton.py` is updated accordingly: `VCO_MIRROR` and
`VCO_BUFFER` join `VCO_RING` as real sub-block footprints, stacked inside
`VCO_CORE`, and `VCO_CORE.w` is widened 140 → **279.86 µm** (driven by the
mirror). `VCO_CORE.h` stays at the ROM 100 µm — all three stacked use ~89 of
it, so the height estimate held.

**Consequence stated plainly rather than re-baselined**: at 280 µm wide the
VCO block pushes `skeleton.total_extent_um2()` to **145 248 µm², ≈ 96.8 % of
PLL-FLOORPLAN.md §5's 0.15 mm² draft target**. Folding these single-row
blocks into multiple rows is the identified next area optimisation, and the
un-drawn V-to-I core has to fit in what is left.
`test_area_budget_headroom_is_reported_not_silently_exceeded` pins the number
so a later increment cannot cross the line unnoticed.

## Artifacts

| Path | What it is |
|---|---|
| `vco_bandsel_mirror.gds` | the real transistor-level band-select mirror block |
| `vco_out_buffer.gds` | the real transistor-level 3-stage output buffer block |
| `drc-clean/vco_bandsel_mirror_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/vco_out_buffer_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc-mirror.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |
| `drc-clean/drc-buffer.stdout.log` | ditto, for the buffer |

Regenerate via `python3 -m vco.mirror` / `python3 -m vco.buffer` (from
`layout/pll_top/`) + `layout/run_pv.py drc`; do not hand-edit any file under
this directory.

## Friction protocol (CLAUDE.md)

No new `klayout-tools` gap was hit drawing this increment. The one place this
pass ran into real friction — needing a *generator*-side guarantee that an
interdigitated common-centroid array's two legs share a centroid, which no
DRC deck can express — is a design-intent check, not a tool gap: it belongs
in this repo's own generator and tests (`mirror.check_common_centroid()`),
where it now lives, and would make no sense as a generic `klt` feature
request phrased without reference to this block. `layout/README.md`'s
existing friction entries (no `klt lvs`; `klt drc`'s curated rule subset)
remain the complete list.
