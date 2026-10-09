# Loop filter -- standalone physical layout (issue #748)

`loop_filter.gds`, top cell `loop_filter`, is the first physical drawing of
`design/netlist/loop_filter.spice` (sizes ratified by DR-006). It is a
standalone cell: it is not placed in `pll_top`, and no post-layout simulation
has been run on it (#297 owns both).

**Verdict in one line:** every device is drawn at its ratified size and count
and wired as the netlist says (checked from the exported GDS, with negative
controls); the foundry DRC deck reports **1 violation on this repository's
default PDK variant (gf180mcuD)** and **0 on variant A**; the foundry LVS deck
**does not match on either variant as shipped** -- for reasons isolated below to
the MIM capacitor's option/variant and to a two-line connectivity gap in the
PDK runset's option-A branch. This block is **not DRC-clean on the variant the
rest of the PLL is verified on, and not LVS-matched**. The C2 variant question
is follow-up issue #753.

## What is drawn

| Element | Netlist | Device | Drawn as | Drawn device extent (read back from the GDS) |
|---|---|---|---|---|
| C1 | XCF1-XCF4, NZ / VSS | `cap_nmos_03v3_b` 87 x 87 um, x4 | 2 x 2 array; each its own n-well (the body), tied to VSS through its own n+ diffusion strips; p-substrate tap band around every cap | gate (`poly2 AND comp`, under `mos_cap_mk`, inside `nwell`): 4 x 87.000 x 87.000 um |
| R | XRF1-XRF4, VCTRL-NR1-NR2-NR3-NZ, sub VSS | plain `ppolyf_u` 2 x 107 um, x4 | side by side, metal1 links at alternating ends, own p-tap ring | body (`pplus AND poly2 AND sab AND res_mk`): 4 x 2.000 x 107.000 um; no `(62, 0)` high-Rs marker anywhere |
| C2 | XCF5, VCTRL / VSS | `cap_mim_2f0_m2m3_noshield` 31.4 x 31.4 um | Metal2 bottom plate = VCTRL; FuseTop/Metal3 top plate = VSS | FuseTop: 1 x 31.400 x 31.400 um; Metal2 bottom plate 0.6 um larger on every side |

Every structural choice follows the PDK's own device generators
(`libs.tech/klayout/tech/pymacros/cells/draw_cap_mos.py`, `draw_cap_mim.py`
MIM-A, `draw_res.py` `polyf_res_inst`); every deviation is extra margin, named
at its constant in `layout/pll_top/loop_filter/primitives.py`. The plain
`ppolyf_u` is drawn with `pplus` over the whole poly and *no* `(62, 0)` marker
-- unlike `vco/primitives.poly_resistor()`, which draws the high-Rs
`ppolyf_u_3k` and was not reused.

Interconnect: metal1 (VSS frame, resistor links), metal2 (NZ straps and bus,
VCTRL stub to the MIM bottom plate), metal3 (VSS strap to the MIM top plate,
through a 2 x 2 Via1/Via2 stack). Labels: `VCTRL` (metal2), `VSS` (metal1),
plus `NZ`, `NR1`-`NR3` so internal nets are named in reports.

**Layer census** -- the committed file's own `layer_indexes()`:
`{21/0, 22/0, 30/0, 31/0, 32/0, 33/0, 34/0, 34/10, 35/0, 36/0, 36/10, 38/0, 42/0, 49/0, 75/0, 110/5, 117/5, 117/10, 166/5}`
-- nwell, comp, poly2, pplus, nplus, contact, metal1 (+label), via1, metal2
(+label), via2, metal3, sab, FuseTop, res_mk, cap_mk, mim_l_mk, mos_cap_mk.
No `(0, 0)` boundary shape, no `(62, 0)`, no `dualgate`. Shape counts per layer
are in `census-and-connectivity.txt`.

## Area

| Quantity | Value |
|---|---|
| Block bounding box (measured on the committed GDS, every layer incl. the 0.3 um tap-ring implants: (-0.3, -0.3)-(219.6, 184.3) um) | **219.900 x 184.600 um = 40,593.54 um^2** |
| Device area (gates + plate + resistor bodies) | 32,118.0 um^2 (C1 30,276 + C2 985.96 + R 856) |
| `PLL-FLOORPLAN.md` sections 3/5 estimate | 36,936 um^2 (32,118 x 1.15) |
| `floorplan/skeleton.py` `LOOP_FILTER` reservation | 235.0 x 195.0 um = 45,825 um^2 |

The measured block is **9.9 % above the floorplan's estimate** (overhead x1.264
on device area, not x1.15) and fits inside the skeleton's reservation. The
excess is the per-capacitor n-well + 1.0 um gap + 1.2 um tap band (2.8 um per
side of every 88.2 x 87 um cap) and the resistor/MIM column beside the array.
This record does not change the floorplan's numbers; it states the
discrepancy for whoever re-derives the area rows (DR-017 Decision 3 names "the
loop filter is drawn" as a trigger for that).

## Provenance

| Item | Value |
|---|---|
| `loop_filter.gds` sha256 | `fdc762879b8ba64ef7bac8874e68b8dcc6128994c9e982a8c8a227129fd6e39c` (the GDS header carries a write time, so a rebuild differs in bytes; geometry identity is what `layout/tests/test_gds_reproducibility.py` checks -- this file is registered in `layout/harness/reproduce.py`) |
| `loop_filter.spice` sha256 | `f0c20f0fe8776dfbc821a3b4457d7a21694c75d502d8fa63baa43d85a28c3326` (flat LVS reference, `block.reference_netlist()`) |
| Generator | `layout/pll_top/loop_filter/` -- `cd layout && python3 -m pll_top.loop_filter.block --outdir evidence/loop-filter-layout --reference-netlist --check-connectivity` |
| Layout writer | `klayout` Python wheel 0.30.10 |
| PV KLayout | 0.28.16 (`/usr/bin/klayout`), PV python `<HOME>/opt/gf180pv-venv` |
| PDK | open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare): `gf180mcuD` (repo default, `sim/pdk.json`) and `gf180mcuA` -- see `check-env.txt`, `check-env-variant-A.txt` |
| klt | 0.7.0+gc64637dcd303 (used only for the attempts below) |

## Foundry DRC

Both runs: `python3 layout/run_pv.py [--variant gf180mcuA] drc layout/evidence/loop-filter-layout/loop_filter.gds --top loop_filter --run-dir <dir> --offgrid` (deep mode, off-grid checks on; density and antenna are off, the deck's default).

| Run | Deck switches (from the log) | Exit | Result |
|---|---|---|---|
| `drc-variant-D/` | MIM option **B**, 5LM, metal_top 11K, `Offgrid enabled: true` | 1 | **1 violation: `MIMTM.3`**, on the FuseTop polygon (187.6,122)-(219,153.4) |
| `drc-variant-A/` | MIM option **A**, 3LM, metal_top 30K, `Offgrid enabled: true` | 0 | **0 violations** -- "Klayout DRC run is clean" |

Reading them:

* **Variant D (the repository's default) is not clean.** `MIMTM.3` is the
  option-B rule "MiM bottom plate overlap of top plate", with the bottom plate
  defined as Metal4 (`topmin1_metal` for 5LM). C2 is ratified as an option-A
  device whose bottom plate is Metal2, so on variant D its FuseTop has no
  Metal4 under it at all. Nothing else fires: every FEOL rule on the MOS caps,
  the plain-poly resistors (`PRES.*`, `SB.*`), the taps, the metal1-3 routing
  and the off-grid checks pass on variant D. Fixing `MIMTM.3` means changing
  C2's device class or the target variant -- a spec decision, not a layout
  fix (#753).
* **Variant A is clean**, including every option-A MIM rule (`MIM.1`-`MIM.11`)
  and variant A's thick-top-metal rules for Metal3 (`MT30.*`). The first
  variant-A run of this generator failed `MT30.1a/5/6/8` on a single-via VSS
  stack; that was fixed in the generator (`primitives.metal1_to_metal3_stack`:
  2 x 2 vias, 2.6 um Metal3) before the recorded run. Variant A is a 3-metal
  stack, so this is evidence about the drawn devices and routing on the
  ratified MIM option, not about the PLL's 5-metal target.

## Foundry LVS

Reference: `loop_filter.spice`, i.e. `block.reference_netlist()`. It restates
the netlist's nine instances as the R/C primitive cards the PDK's LVS reader
needs (`custom_classes.lvs` turns a capacitor's W/L/M into the A/P it compares).
C1's four identical parallel caps are one card with `M=4`: the runset merges
parallel devices in the extracted netlist by default but not in the reference
(only under `--schematic_simplify`, which the harness does not pass), so four
separate reference cards cannot match the one merged layout device (A = 30,276
um^2). That four separate caps are *drawn* is established by the census above,
not by this card.

Command: `python3 layout/run_pv.py [--variant gf180mcuA] lvs layout/evidence/loop-filter-layout/loop_filter.gds layout/evidence/loop-filter-layout/loop_filter.spice --top loop_filter --run-dir <dir>` (substrate `VSS`, `poly_res` 3k -- irrelevant here, the resistors are unmarked).

| Run | Exit | Extracted (`*.cir`) | Result |
|---|---|---|---|
| `lvs-variant-D/` | 1 | 4 x `ppolyf_u` L=107 W=2 on the right nets; `cap_nmos_03v3_b` A=30276 P=1392 NZ/VSS; **no MIM device** | **mismatch** -- the option-B deck has no option-A MIM to recognise |
| `lvs-variant-A/` | 1 | same, plus `cap_mim_2f0_m2m3_noshield` A=985.96 P=125.6 -- **on two floating nets** (`$13`, `$17`) | **mismatch** -- C2 recognised with the right class and area, but neither plate is connected to anything |

So on both variants, every resistor and the MOS-cap group extract with the
correct device class, size and terminal nets; the mismatch is C2 alone.

### Why C2 floats on variant A: the PDK runset, not the layout

The PDK's `rule_decks/mimcap_connections.lvs`, option-A branch, is

```
connect(metal2, mim_virtual)
connect(fuse_cap, via2_cap)
```

`metal2` there is the raw input layer, but all routing connectivity uses the
derived `metal2_con` (`general_connections.lvs`), and nothing connects
`via2_cap` (Via2 inside FuseTop) to Metal3. Both plates are therefore islands
in the runset's own connectivity graph. The option-B branch does not have this
gap (`connect(topmin1_metal, mimtm_virtual)` and
`connect(top_via_cap, top_metal_cap)`). The PDK's own option-A unit test
(`lvs/testing/testcases/unit/mimcap_devices/cap_mim_2f0_m2m3_noshield`) does not
exercise it: its caps' plates are unlabelled and unrouted and it "matches" with
every terminal on an anonymous net (run here as a control; not committed).

**Diagnostic only -- not a foundry verdict:**
`lvs-variant-A-mim-connect-diagnostic/` re-runs the same command against a
scratch copy of the variant-A runset with exactly the two-line change in
`mimcap_connections.lvs.patch` (`metal2` -> `metal2_con`, plus
`connect(via2_cap, metal3_con)`). Result: **"Congratulations! Netlists match."**,
with C2 extracted as `C$5 VCTRL VSS ... cap_mim_2f0_m2m3_noshield`. Its
negative control, `negative-control-open-NR2/`, runs the same patched deck on a
copy of the GDS with the NR2 metal1 link deleted: **mismatch**. This shows the
layout is consistent with the netlist once the runset connects the MIM plates;
it is not signoff, because the deck was modified.

To reproduce: copy `$PDK_ROOT/gf180mcuA/libs.tech/klayout/lvs/` to a scratch
directory (the logs name `<REPO>/layout/evidence/work/loop-filter-deckA`,
git-ignored and not committed), apply `mimcap_connections.lvs.patch` there, and
from inside that copy run
`<pv-python> layout/harness/_pdk_lvs_poly_res.py <copy>/run_lvs.py 3k --layout=<gds> --netlist=layout/evidence/loop-filter-layout/loop_filter.spice --variant=A --topcell=loop_filter --run_dir=<dir> --run_mode=deep --lvs_sub=VSS`
-- the same shim and arguments `layout/harness/lvs.py` uses, pointed at the copy.

## Connectivity from the exported GDS (`netcheck.py`)

`census-and-connectivity.txt` records, for the committed GDS:

* the device census above, read back with the LVS deck's own recognition
  expressions -- `device problems: none`;
* **topology from the GDS alone** (`check_topology`, 42 terminal probes,
  every terminal located from the census, not from the generator): the four
  resistors form one unbranched chain of five distinct nets; one end is shared
  by all eight MOS-cap gate contact rows (NZ), the other by the MIM bottom
  plate and the `VCTRL` label; the MIM top plate, all eight MOS-cap body
  diffusions, all four n-wells, all 12 substrate-tap shapes and the `VSS`
  label are one net distinct from all five -- **OK**;
* **named terminal probes** (`check_probes`, 43 probes, positions from the
  generator, nets from the GDS) -- **OK**;
* **the checker boundary**: a metal-only extraction (every Via2 joins Metal2 to
  Metal3, FuseTop ignored) reports `short: VCTRL / VSS` on this correct
  layout. The plate-aware extraction splits Via2 on FuseTop exactly as the
  foundry runset does, which is why it does not.

What it does not do: recognise device values (that is the census plus the LVS
runs above), or treat the substrate as a conductor -- substrate ties are
proved by checking every tap is *wired* to VSS.

Negative controls (`layout/tests/test_loop_filter_layout.py`, each on a
temporary mutated copy of a fresh build): deleting the NR2 link is reported as
an open; a metal1 bridge between XRF4's NZ end and the NR2 link is reported as
`NR2 / NZ` short; one Via2 outside FuseTop where the VSS Metal3 strap crosses
the bottom plate is reported as `VCTRL / VSS` short; a `(62, 0)` marker over a
resistor plus a `(0, 0)` box in place of one cap's `mos_cap_mk` are reported by
the census. Two builds compare equal layer by layer, and every vertex is on
the 5 nm grid.

## klayout-tools

`klt` was tried on this block and could not do either job (records committed):

* `klt-extract-attempt.txt` -- `klt extract --deck gf180mcu`: extracts the four
  resistors only; no MOS-cap class exists in the curated deck (filed
  2AMLogic/klayout-tools#2919) and only the option-B MIM exists, so C2 is not
  recognised and its top-plate vias merge `VCTRL` and `VSS` into one net
  (2AMLogic/klayout-tools#2920).
* `klt-components-attempt.txt` -- `klt components`: raw-layer conductors and
  vias cannot express "Via2 inside FuseTop lands on the top plate, not the
  Metal2 under it", so the two plates come out as one component
  (2AMLogic/klayout-tools#2921). This is why `netcheck.py` uses
  `klayout.db.LayoutToNetlist` directly.

## Limitations (stated, not papered over)

1. **Not DRC-clean on variant D** (1 x `MIMTM.3`), and the assembled `pll_top`
   (#297) will inherit it unless #753 changes C2's device class or the target
   variant. The variant-A clean run is on a 3-metal stack.
2. **No foundry LVS match** on either variant as shipped. The only match is on
   a patched runset (diagnostic, above).
3. **ERC (`klt erc`) not run.** The block has no transistor gate; ERC was not
   part of this issue's scope.
4. **No density or antenna DRC** (deck defaults off).
5. **Standalone only**: no top-level placement, no pins on a boundary, no
   post-layout extraction or simulation.
6. **Area** is 9.9 % over the floorplan's estimate (see Area).
7. **Harness fix carried in this change**: `layout/harness/env.py` wrote its
   path tokens (`<RUN_DIR>`, ...) unescaped into the `.lyrdb` XML report, so
   `run_pv.py drc` crashed parsing its own report on the first DRC run after
   issue #701. Tokens are now XML-escaped in `.lyrdb` files (decoded back to
   `<RUN_DIR>` by any XML reader); `layout/tests/test_evidence_host_paths.py`
   covers it.
