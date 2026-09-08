# VCO bias generator: `ppolyf_u_3k` poly resistors — real transistor-level layout DRC run (issue #293, increment 3)

Companion to [`PROOF.md`](PROOF.md) (increment 1: the 5-stage ring, PR #305)
and [`PROOF-mirror-buffer.md`](PROOF-mirror-buffer.md) (increment 2: the
band-select mirror + output buffer, PR #313). Both of those increments named
the same deferral boundary: `vco_bias.sch`'s V-to-I core has three
`ppolyf_u_3k` poly resistors (`RCG`, `ROFF`, `RDEG`), and
`layout/pll_top/vco/primitives.py` had no generator for that device class.
This increment adds one (`primitives.poly_resistor()`) and draws the three
resistors it was missing, as a standalone block:

| Block | Generator | Top cell | GDS |
|---|---|---|---|
| `RCG`/`ROFF`/`RDEG` (`vco_bias.sch`) | `layout/pll_top/vco/bias_resistors.py` | `vco_bias_resistors` | `vco_bias_resistors.gds` |

Real device geometry on the PDK's own layers: `poly2` (30/0), `pplus`
(31/0), `contact` (33/0), `metal1` (34/0), plus two layers new to this
increment — `sab` (49/0, salicide block) and `res_mk` (110/5, resistor body
marker). Layer numbers are confirmed against `layers_def.drc`'s own
`get_polygons()` calls, same convention `PROOF.md`/`PROOF-mirror-buffer.md`
already use for every other layer.

## Where the recipe came from

Rather than re-derive a resistor generator from `pres.drc`'s `PRES.*` rules
in isolation, `primitives.poly_resistor()`'s constants are read directly off
the gf180mcuD PDK's own device generator —
`$PDK_ROOT/libs.tech/klayout/tech/pymacros/cells/draw_res.py`'s
`polyf_res_inst()` (the shared body every `draw_*polyf*_res()` wraps),
called with `res_type="ppolyf_u"` via `draw_ppolyf_res()`'s non-`"_s"`
branch — the PDK's own shipped recipe for this exact device class. Two
places deliberately deviate from that recipe rather than copying it
verbatim, both documented in `primitives.py` itself:

1. **`POLY_RES_CONTACT_TO_SAB_UM` (PRES.7, 0.22 µm) is drawn as an explicit
   clearance**, not inherited from the pcell's own `con_enc=0` placement —
   this module's convention throughout is margin on top of a rule's stated
   minimum, not sitting exactly on the boundary (see `poly_resistor()`'s own
   docstring for the full reasoning).
2. **No per-resistor local substrate tap is drawn.** The pcell's own
   `sub_rect` assumes no guaranteed nearby tie; every resistor this repo
   draws instead lives inside a block with its own dedicated `GND_VCO` guard
   ring (`ring.py`/`mirror.py`/`buffer.py`'s convention), and two of the
   three resistors here (`ROFF`/`RDEG`, `L=33 µm`) are themselves longer
   than PLL-FLOORPLAN.md §1's 15 µm tap-pitch bound, so a single
   end-of-resistor tap would leave the far end un-tapped by anything closer
   than the block's outer ring anyway. See the "Tap pitch" section below.

## Provenance

| | |
|---|---|
| Generated | 2026-09-08T21:41 UTC |
| Invoked as | `python3 -m vco.bias_resistors --outdir layout/evidence/vco-layout` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc layout/evidence/vco-layout/vco_bias_resistors.gds --top vco_bias_resistors --run-dir <tmp> --offgrid` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.10` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D`, `--offgrid` (signoff-grade — the off-grid check class is included, not skipped) |

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `vco_bias_resistors` DRC, table `main`, `--offgrid` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| All 9 `PRES.*` rules actually executed (not skipped) | `PRES.1`..`PRES.7`, `PRES.9a`, `PRES.9b` | all 9 present in `drc-bias-resistors.stdout.log` | **PASS** |
| `vco_ring` / `vco_bandsel_mirror` / `vco_out_buffer` re-run after this increment's `primitives.py` changes | still clean, geometry unchanged | clean; KLayout XOR against each committed `.gds` is **empty on every layer** | **PASS (no regression)** |

The three-block re-run matters for the same reason `PROOF-mirror-buffer.md`
records one: this increment adds new module-level constants and two new
`LAYER` entries to `primitives.py` (shared by every VCO sub-block), plus a
new `poly_resistor()` function. Nothing in `mosfet()` or the other existing
generators changed, and the XOR proves it — every layer of every
already-shipped block's GDS is bit-identical to what is committed on `main`.

Rules this increment newly exercises: the full `PRES.*` family (`PRES.1`
minimum poly2-resistor width, `PRES.2` resistor-to-resistor isolation,
`PRES.3` resistor-to-COMP spacing, `PRES.4` resistor-to-unrelated-poly2
spacing, `PRES.5` pplus enclosure, `PRES.6` sab width-direction overlap,
`PRES.7` contact-to-sab clearance, `PRES.9a`/`PRES.9b` `res_mk` marker
rules), plus `geom.drc`'s OFFGRID class against the new `sab`/`res_mk`
layers.

## Tap pitch (test plan edge case)

Checked independently in pure Python (`bias_resistors.max_tap_distance_um()`,
`layout/tests/test_vco_layout.py`), not inferred from "the DRC run passed":

| Block | Worst-case in-plane distance to nearest guard-ring tap | Bound (PLL-FLOORPLAN.md §1) |
|---|---|---|
| `vco_bias_resistors` | 1.80 µm | ≤ 15 µm |

Unlike `ring.py`/`mirror.py`/`buffer.py` (wide, short rows, where the
top/bottom guard-ring bands are what matters), this block is narrow and tall
— the row of three resistors is 13 µm wide but `ROFF`/`RDEG` are each
33.66 µm of poly2 tall. The guard ring's **left and right** bands run the
block's full height, so every point along even the longest resistor sits a
fixed ~1.8 µm from a tap regardless of the resistor's own length — a
stronger and simpler guarantee than tapping each resistor's own ends would
give. The test asserts real headroom (< half the 15 µm bound), not merely
`<=`.

## Footprint vs. the ROM estimate — not yet reconciled with `skeleton.py`

| Block | Real footprint | Area |
|---|---|---|
| `vco_bias_resistors` | 13.00 × 40.32 µm | 524 µm² |

`layout/floorplan/skeleton.py` is **not** updated in this increment. The
acceptance criterion ("note explicitly if the real footprint deviates from
the ROM estimate") applies to the VCO block's real footprint once its
sub-blocks are drawn — this resistor trio is one piece of the still-undrawn
V-to-I core, not a complete "bias generator" sub-block in its own right.
Wiring a partial fragment of the bias generator into `skeleton.py`'s
`VCO_CORE` stacking would misrepresent the floorplan more than it would
inform it; the honest move is to wait until the V-to-I core's transistors
are drawn and the whole bias-generator footprint is known. Worth flagging
regardless: `PROOF-mirror-buffer.md` already recorded the VCO block at
≈96.8% of PLL-FLOORPLAN.md §5's 0.15 mm² draft area budget with only the
ring, mirror and buffer counted. Even this small 524 µm² resistor trio, once
folded in alongside the V-to-I core's dozen-odd transistors, is going to
matter for that budget — flagged here so it is not a surprise later.

## What remains of issue #293 after this increment

| Drawn for real, cumulative | Still deferred |
|---|---|
| 5-stage current-starved ring + its guard ring + 22 pF decap (PR #305) | V-to-I core **transistors** (`MP1`/`MP2`/`MN1`/`MN2`/`MSU1`-`MSU3`/`MPR`/`MD1`/`MD2`/`MOFF`/`MVI`/`MSUM`) |
| 3-cascade band-select mirror + 3-stage output buffer (PR #313) | Inter-sub-block wiring / a single shared VCO guard ring |
| `RCG`/`ROFF`/`RDEG` poly resistors + the `ppolyf_u_3k` primitive (this increment) | Combined-block standalone DRC run |
| | `skeleton.py`'s VCO_CORE update, once the full bias generator's footprint is known |

Per this issue's own established convention (`PR #313`'s body: "no follow-up
issue is filed — #293 itself accumulates"), no new issue is filed for the
remaining scope above.

## Artifacts

| Path | What it is |
|---|---|
| `vco_bias_resistors.gds` | the real transistor-level poly-resistor block |
| `drc-clean/vco_bias_resistors_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc-bias-resistors.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list, including all 9 `PRES.*` rules) |

Regenerate via `python3 -m vco.bias_resistors` (from `layout/pll_top/`) +
`layout/run_pv.py drc`; do not hand-edit any file under this directory.

## Friction protocol (CLAUDE.md)

No new `klayout-tools` gap was hit drawing this increment. The PDK's own
poly-resistor pcell (`draw_res.py`) was read directly rather than
re-derived from the DRC deck's rules alone, which is a design-research
question this repo's own generator has to answer for itself (which existing
PDK recipe applies to *this* device), not a gap in `klt`'s own feature
surface — `layout/README.md`'s existing friction entries (no `klt lvs`;
`klt drc`'s curated rule subset) remain the complete list.
