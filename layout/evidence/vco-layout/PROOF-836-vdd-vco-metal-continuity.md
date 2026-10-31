# `VDD_VCO` made metal-continuous in `vco_block` (issue #836)

T1 checklist item 11 wants every declared supply to resolve to one electrical
island under `klt erc`, whose conductor model is metal-only. `vco_block` had
one `erc.unconnected_net` finding: `VDD_VCO` in two islands, the second a
single Metal1 shape (bbox x -0.12..105.64, y 18.48..19.32 um) -- `vtoi_core`'s
**bottom** n-well tap band. `block.vdd_feed_bands()` feeds one band per n-well
(#433), because two bands in one well are one node through the silicon; that is
true, but not something a metal-only extractor credits.

## Confirmed cause

The finding's island bbox equals `vtoi_core.plan().tap_band_bottom`'s Metal1
pad (y 18.6..19.2 um plus the 0.12 um pad margin). Only the top band
(y 43.4..44.0) had a hop to the trunk.

## Change

`layout/pll_top/vco/block.py`, step 6: every `vtoi_core` tap band below the top
one gets a short Metal1 stub off its right end and a Metal2 strap (x =
band right edge + 0.6 um) running up to the top band's existing Metal2 hop, with
one Via1 stack at the bottom. The tap band is kept (it exists for the
DF.13_MV/DF.14_MV tap-distance bound).

Rejected routes, by measurement:

* A second hop to the trunk, as for the top band: the Metal2 run crosses the
  `NOFF` Metal2 column at x = 120.84 um (`_Router` raises M2.2a).
* A Metal1 strap through the left channel: signal Metal1 occupies it
  (x -1.02..-0.58, y 15.6..40.5).
* A Metal1 strap on the right: crossed by a signal Metal1 run at y 31.0..31.6.

The Metal2 strap sits 0.47 um from the nearest other-net Metal2 (the escape at
x 105.09..105.53), above the 0.28 um M2.2a rule; the router also checks this.

## Results (`klayout-tools==0.6.0`, `--deck gf180mcu`)

| | before (`3fa3026`) | after |
|---|---|---|
| `vco_block` `erc_status` / findings | `violations` / 1 (`VDD_VCO`, 2 islands) | `clean` / 0 |
| `pll_top` `erc_status` / findings | `violations` / 1 (inherited) | `clean` / 0 |
| `vco_block.gds` sha256 | `515f8161...` | `4f5151dfbcd2d43694bfc845a507fbd43974559f1e1f8c4a8b6064afe95deb3c` |
| `pll_top.gds` sha256 | -- | `fbe4001364aa586f6bdbf1babe85cbb4d40d8fbf4560b899ee158d7f5f12b11c` |
| `klt drc --deck gf180mcu` (curated), both GDS | clean | clean |

`pll_top` was regenerated with `python3 -m pll_top.top_level.assemble --outdir
evidence/pll-top-layout --check`; boundary and total area are unchanged
(407,776.2 um^2). `area-audit.md` was regenerated (`vco_block` drawn area
18,226 -> 18,233 um^2 from the added metal).

Tests: `VddFeedBandSelectionTests` / `AssembledBlockVddIslandTests` in
`layout/tests/test_vco_layout.py`; the new
`test_every_vtoi_core_tap_band_reaches_the_trunk_on_metal_issue_836` extracts
metal-only connectivity and requires both `vtoi_core` bands in the trunk's
cluster. It fails on the pre-change geometry (the bottom band is its own
cluster there) and passes now.

## Not done here -- stated plainly

* **Foundry DRC and LVS were not re-run.** This host's installed PDK
  (open_pdks `f6eeac7`) has no `run_drc.py` and is not the revision the recorded
  evidence uses (`c6d73a3`), and host tooling must not be changed. The `klt drc`
  rows above use `klt`'s curated deck, which is a subset: it does not report
  the known loop-filter `MIMTM.3` violation on `pll_top`, so "clean" there is
  weaker than the PDK deck's verdict. The DRC-clean (`vco_block`) and LVS
  `match` (43/43 nets) acceptance criteria therefore still need a run with the
  pinned PDK: `python3 run_pv.py drc evidence/vco-layout/vco_block.gds --top
  vco_block --offgrid` and `... lvs ... --lvs-sub GND_VCO`. The added geometry
  is one 0.44 um Metal1 stub, one Via1 stack and one Metal2 strap, all
  spaced from other nets by the generator's own checks.
* The LVS deck joins same-named nets, so it cannot see this change either way.
* Top-level LVS (#149) and the `signoff/` item-11 citation are untouched.
* VCO sims: the `sim/` decks read schematic netlists; they reference `layout/`
  only in tests that check committed claims, not extracted geometry.

## 2026-10-30 note: curated-deck DRC re-run; LVS not obtainable

This supersedes the "Foundry DRC and LVS were not re-run" bullet above (kept as
written). Per the 2026-10-30 operator ruling the evidence was taken with
klayout-tools' **curated gf180mcu deck**, not the foundry `run_drc.py` /
`run_lvs.py` (`klt 0.8.1.dev849+gf05774458ae2`, KLayout 0.30.12, deck content
hash `sha256:88d269a2...`, deck not released).

| | result | evidence |
|---|---|---|
| `klt drc --deck gf180mcu` on `vco_block.gds` (`--top vco_block`) | `clean`, 0 violations | `klt-curated-836/drc-vco_block.json` |
| `klt drc --deck gf180mcu` on `pll_top.gds` | `clean`, 0 violations | `../pll-top-layout/klt-curated-836/drc-pll_top.json` |
| `klt lvs` on `vco_block.gds` vs `lvs-clean/vco_block.spice` | **no verdict**: the reference does not parse | `klt-curated-836/lvs-attempt.md`, `lvs-request.json` |

Both DRC reports pass `klt drc --check`; their input hashes equal the GDS
sha256 values in the table above.

What the curated deck covers: 53 rules on this layout (COMP, Poly2, Nplus,
Pplus, Nwell, Contact, Metal1, Via1, Metal2 width/space/enclosure/on-grid, plus
LV tap distance). It skips Metal3-5, Via2-4, MIM, ESD, fuse, guard-ring and
the `_MV` rules, and lists roughly 280 foundry rules as unmodeled. No MIM rule
is in the deck, so it cannot report the known loop-filter `MIMTM.3` at
`pll_top`: `pll_top` "clean" here is **not** evidence that `MIMTM.3` is the
only violation, and neither report shows the foundry deck is clean. The
geometry added by #837 is Metal1 / Via1 / Metal2, all inside the checked set.

LVS: `klt lvs` could not read the committed reference (its three poly
resistors use the foundry deck's valueless form). The reference was not
edited. The 43/43-net `match` therefore remains the pre-#837 foundry result,
and the post-strap LVS criterion is still open. The LVS deck joins same-named
nets, so even a `match` would not exercise the strap.

## 2026-10-31: curated-deck LVS on `vco_block` -- runs now, verdict `mismatch`

Supersedes the "LVS: `klt lvs` could not read the committed reference" paragraph
above (kept as written). `klt 0.8.1.dev965+g5d8e4f2b5009`, KLayout 0.30.12,
`--deck gf180mcu`. The reference netlist is unmodified. The only change to the
request (`klt-curated-836/lvs-request.json`) is `reference.deck: "gf180mcu"`,
which `klt lvs` names in its error hint as what `reference.form: "subckt-call"`
needs to rewrite the valueless foundry-style resistor cards.

Result (`klt-curated-836/lvs-vco_block.json`, passes `klt lvs --check`): status
**`mismatch`**, 57 errors. Nets 43 layout / 43 reference / **31 matched**;
devices 81 / 65 / 56 matched; pins 20 / 7 / 20 matched. **The "match, 43/43
nets" criterion is not met by the curated deck.**

Cause attribution: the same run on the `vco_block.gds` from before the #837
strap (`389cf07d^`) gives the identical category counts and net/device/pin
counts. The mismatch is therefore **not caused by #837's Metal1/Via1/Metal2
strap**, and no geometry was changed. Breakdown of what the report names:

- 14 layout MOS devices with no reference counterpart (12 pfet, 2 nfet), plus
  30 `device.property` differences on matched MOS devices (`w_um`, `as`, `ad`,
  `ps`, `pd`).
- 2 `cap_nmos_03v3` layout devices (the supply decap from #759) with no
  reference counterpart; the reference has none.
- The three poly resistors are paired but flagged `device.class`: the layout
  extracts `ppolyf_u_1k`, the reference rewrites to `PPOLYF_U_3K`.
- 5 `topology` findings where nets were paired despite a name/identity
  conflict.

Not diagnosed here: whether these come from the reference netlist being older
than the layout (it predates #759's decap and the #381 resistor change), from
how the curated deck extracts MOS parameters and resistor classes, or from the
layout. The reference was not edited, per the issue. The recorded foundry-deck
`match` in `lvs-clean/` is unchanged and still predates #837's strap. Also,
the LVS joins same-named nets, so even a `match` would not exercise the strap.
