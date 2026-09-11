# `vco_block` assembled LVS — clean at last: the resistor reference-netlist device class was wrong

> **Correction and follow-on (issue #381):** two statements below are
> withdrawn, though the constant change this record made was correct for the
> geometry as it then stood.
> (1) "the PDK's own `ppolyf_u_3k` pcell instance, calling the identical
> `polyf_res_inst()` body" — it does not: the high-sheet family has its own
> pcell class, `ppolyf_u_high_Rs_resistor` (`cells/res.py:1202`), calling
> `draw_ppolyf_u_high_Rs_res()` (`cells/draw_res.py:851`), which **does** draw
> `layer["resistor"]` = `(62, 0)`. `sm141064.ngspice` lists `ppolyf_u_3k`
> (line 79, "3k high-Rs") and `ppolyf_u` (line 72) as two different devices.
> (2) The framing of the naming difference as a "foundry-deck device-class-naming
> difference" understates it: the drawn device really was the 350 ohm/sq one,
> i.e. an 8.3x resistance error against the schematic, which this record's own
> fix made LVS-clean rather than visible.
> `PROOF-381-high-rs-resistor.md` corrects the geometry (the generator now
> draws the marker and the rest of the PDK's high-Rs recipe), measures the
> bias-current consequence across PVT, and records the decision in
> `spec/decision-records/DR-009-vco-bias-resistor-device-class.md`.
> `sim/`-style append-only discipline applies here too — this pointer is added,
> the body below is otherwise unedited.

Fix record for [issue #378](https://github.com/2AMLogic/gf180-pll/issues/378),
which [`PROOF-376-vbp0-fix.md`](PROOF-376-vbp0-fix.md) filed once fixing
issue #376's `VBP0`/`VDD_VCO` short exposed it. Same discipline as every
other record in this directory: every claim below is a command run against
the artifacts committed beside this file, cross-referenced directly against
the resulting `.lvsdb` via `klayout.db.LayoutVsSchematic`, not inferred from
the deck's pass/fail line alone.

**The assembled `vco_block` LVS run is now fully clean:**

```
INFO : Congratulations! Netlists match.
```

Direct `klayout.db.LayoutVsSchematic` cross-reference of the resulting
`.lvsdb` confirms **every** device and **every** net matches with zero
warnings — a strictly better result than `PROOF-376-vbp0-fix.md`'s own
65/65-devices-but-4-nets-mismatch state:

| | Before this fix (`PROOF-376-vbp0-fix.md`'s own state) | After this fix |
|---|---|---|
| Devices | 65/65 paired: 62 `Match`, 3 `MatchWithWarning` | 65/65 `Match` (**0 warnings**) |
| Nets | 39/43 `Match`, 4 `Mismatch` (`GND_VCO`, `NC`, `NOFF`, `NVI`) | 43/43 `Match` |
| Deck verdict | `ERROR : Netlists don't match` | `Congratulations! Netlists match.` |

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `8f57802` (PR #379 / issue #376 merged) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.28.16` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |

Same disclosed KLayout-version deviation `PROOF-lvs.md`/`PROOF-368-rootcause.md`/
`PROOF-371-ring-fix.md`/`PROOF-372-buffer-fix.md`/`PROOF-376-vbp0-fix.md` all
carry: releases newer than `0.28.16` have been observed to report a *false*
LVS mismatch on an unchanged, LVS-clean layout. That failure mode can only
make a result here **worse**, never better — the result below is a full
**match**, and this record's own application run was made on `0.28.16`
directly (not the deviation-affected newer release), so it is not in play
here at all.

## The leading hypothesis (issue #378's own) was tested directly, and refuted

The issue's own leading hypothesis was that `NC`/`NOFF`/`NVI` each carrying
two boundary-pin labels on *different* metal layers (one `metal2_label` from
`vtoi_core.py`, one `metal1_label` from `bias_resistors.py`, since the latter
omits `layer=` and gets `Canvas.PIN_LAYER`'s default) was the cause, by
analogy with `VBP0` (also double-labelled, but on *matching* layers, and
`VBP0` shows no defect). Tested directly, not assumed:

```python
# bias_resistors.py, experimentally: canvas.pin(res.top_net, *p.top_pad, layer="metal2_label")
```

Rebuilding `vco_block` and rerunning the assembled LVS with only that one
line changed reproduced the **exact same** four-net mismatch
(`GND_VCO`/`NC`/`NOFF`/`NVI`, identical terminal/pin counts) — the layer
match made no difference. **Refuted.**

A second, related hypothesis (the reference netlist's own resistor SPICE
line, `R_<name> {top_net} {bottom_net} {bottom_net} <model> W=... L=...`,
declares terminal order `A=top_net, B=bottom_net, W=bottom_net`, but direct
`net_for_terminal()` introspection of the layout-extracted device showed the
opposite: `A=bottom_net(GND_VCO), B=top_net(signal), W=bottom_net`) was also
tested directly by swapping the reference's own node order to match. The
device pair's own per-terminal net correspondence became exact (`A`/`B`/`W`
identical on both sides), but the net-level `Mismatch` verdict was
**unchanged** and the device pair stayed `MatchWithWarning` (not `Match`) —
so terminal order was a real, independent, but *cosmetic* discrepancy
(harmless because `ppolyf_u`/`PPOLYF_U_1K`-class resistors have no polarity
between their `A`/`B` terminals — see "The fix" below for whether it needed
its own correction), not the root cause either. **Refuted as the cause of
the net-level mismatch specifically.**

## Root cause, confirmed directly

`each_net_pair()`/`each_device_pair()` cross-reference showed the 3
`MatchWithWarning` devices (`RCG`/`ROFF`/`RDEG`) are the **only** devices in
the whole 65-device netlist not marked plain `Match`, and the 4 `Mismatch`
nets (`GND_VCO`, `NC`, `NOFF`, `NVI`) are **exactly** the nets those 3
devices' own terminals touch and no others — every net touching only
`Match` devices (13 other nets also carry the same "extra circuit pin"
pattern the issue's own evidence described, e.g. `NB1`, `VBP0`, `S1.Y`, and
none of them mismatch) stayed `Match`. This 1:1 correlation (not the pin
labels, not the terminal order) is what a `MatchWithWarning` device
actually costs at the net level: any net it terminates on cannot itself
reach a `Match` verdict, only `Mismatch`.

So the real question became: why is `RCG`/`ROFF`/`RDEG` only
`MatchWithWarning`, not `Match`, given `block.RESISTOR_LVS_MODEL` was
already meant to state exactly the class the deck extracts? Reading
`gf180mcuD`'s own `rule_decks/res_derivations.lvs` directly (not assumed)
shows the poly-resistor layer derivation is a **two-way**, mutually
exclusive split on a *third* GDS marker layer, not a single switch-selected
class as `RESISTOR_LVS_MODEL`'s own prior docstring claimed:

```ruby
ppolyf_u_layer = pplus.and(poly2).and(sab).and(res_mk).not_interacting(resistor).not(dnwell).not(ppoly_exclude)
ppolyf_u_h     = poly2.and(sab).and(res_mk).and(resistor).not(dnwell).not(v5_xtor).not(dualgate).not(ppoly_exclude)
```

(`resistor` here is `get_polygons(62, 0)` in `layers_definitions.lvs` — an
unrelated derived-layer *name* collision with this repo's own vocabulary,
nothing to do with any layer `primitives.LAYER` names.) `res_extraction.lvs`
extracts every `ppolyf_u_layer`-matching shape unconditionally as the plain,
fixed-350-ohm/sq `ppolyf_u` class (**no `$poly_res` switch involved at
all**), and only `ppolyf_u_h`-matching shapes (i.e. shapes that *also*
overlap GDS layer `(62, 0)`) get extracted as the switch-selected
`ppolyf_u_1k`/`_2k`/`_3k` family `res_extraction.lvs`'s own `case POLY_RES`
block names. `primitives.poly_resistor()` never draws layer `(62, 0)`
anywhere — confirmed directly (see "Results" below) — and reading
`$PDK_ROOT/libs.tech/klayout/tech/pymacros/cells/draw_res.py` directly shows
why: `polyf_res_inst()`, the pcell body the module's own docstring already
cited as this generator's model, also never draws it (that marker layer is
drawn only by a *different* pcell function, `draw_ppolyf_u_high_Rs_res()`,
which this repo's generator does not call and never claimed to model). So
every resistor this repo draws — and the PDK's own `ppolyf_u_3k` pcell
instance, which calls the identical `polyf_res_inst()` body — always lands
in the `ppolyf_u_layer` bucket and extracts as plain `ppolyf_u`, regardless
of `$poly_res`. `block.RESISTOR_LVS_MODEL`'s prior value, `"ppolyf_u_1k"`,
named the *other* bucket — a real, exact-string device-class mismatch,
confirmed directly via `net_for_terminal()`/`device_class().name`
introspection (see "Results" below), not merely "differently named but
compatible": `SubcircuitModelsReader.element()` (`custom_classes.lvs`)
creates the reference's device class dynamically by that exact string, and
the netlist comparer requires it to equal the layout-extracted class's own
name for a device pair to reach `Match`.

### Reproduction: confirming the layout-extracted resistor class directly

```python
import klayout.db as db
lvs = db.LayoutVsSchematic()
lvs.read('<rundir>/vco_block.lvsdb')
xref = lvs.xref()
top = next(c for c in lvs.netlist().each_circuit() if c.name == 'vco_block')
for dp in xref.each_device_pair(top):
    a, b = dp.first(), dp.second()
    if b and b.name == '_RCG':
        print('layout class:', a.device_class().name)   # -> ppolyf_u
        print('reference class:', b.device_class().name)  # -> PPOLYF_U_1K (before fix)
        for t in a.device_class().terminal_definitions():
            print(' layout', t.name, '->', a.net_for_terminal(t.id()).name)
        for t in b.device_class().terminal_definitions():
            print(' ref   ', t.name, '->', b.net_for_terminal(t.id()).name)
```

**Before this fix** (`block.RESISTOR_LVS_MODEL = "ppolyf_u_1k"`):

```
layout class: ppolyf_u
reference class: PPOLYF_U_1K
 layout A -> GND_VCO
 layout B -> NC
 layout W -> GND_VCO
 ref    A -> NC
 ref    B -> GND_VCO
 ref    W -> GND_VCO
```

(Device pair status: `MatchWithWarning`. `NC`/`GND_VCO` net pair status:
`Mismatch`, despite this exact per-terminal net correspondence — the class
*name* difference alone is what blocks the net-level `Match`, independent
of the `A`/`B` terminal-order discrepancy visible above.)

**After this fix** (`block.RESISTOR_LVS_MODEL = "ppolyf_u"`):

```
layout class: ppolyf_u
reference class: ppolyf_u
```

(Device pair status: `Match`. Every net touching it: `Match`.)

### Confirming the geometric fact directly: no `(62, 0)` shape is ever drawn

```python
import klayout.db as db
from layout.pll_top.vco import primitives as prim, devices as dev
canvas = prim.Canvas("probe")
prim.poly_resistor(canvas, dev.BIAS_R_RCG, 0.0, 0.0)
marker_layer = canvas.layout.layer(62, 0)
region = db.Region(canvas.top.begin_shapes_rec(marker_layer))
print(region.is_empty())  # -> True
```

Committed as `layout/tests/test_vco_layout.py`'s
`PolyResistorMarkerLayerTests` (klayout-gated, no PDK/LVS-deck dependency),
alongside a value-pinned regression guard on `RESISTOR_LVS_MODEL` itself
(`ReferenceNetlistDeviceTests.test_resistor_model_is_the_marker_free_class_not_the_1k_bucket`).

## The fix

All of it is in `layout/pll_top/vco/block.py` — `RESISTOR_LVS_MODEL`'s value
and its own docstring (corrected to describe the two-way marker-layer split
above rather than the previously-assumed single `$poly_res`-switch
selection). **No geometry changed at all**: `vco_block.gds` (and every
sub-block `.gds`) is byte-for-byte the same layout as `PROOF-376-vbp0-fix.md`
committed (confirmed via per-layer shape-count + bounding-box comparison,
not just assumed from "no `.py` generator file changed") — this was purely a
reference-netlist device-class-name correction, not a layout defect.

| Change | Why |
|---|---|
| `RESISTOR_LVS_MODEL = "ppolyf_u_1k"` → `"ppolyf_u"` | The deck's own two-way marker-layer split (above) means every resistor this repo draws always extracts as the plain, switch-independent class, never the switch-selected one — confirmed directly, not by re-guessing which switch value applies |
| Docstring rewritten | The prior docstring's own reasoning (deck hardcodes `poly_res=1k`, therefore extraction is `ppolyf_u_1k`) assumed the switch alone decides the class; it does not — the switch only matters for shapes that already carry GDS layer `(62, 0)`, which this module's own geometry never draws |

The `A`/`B` terminal-order discrepancy the "leading hypothesis" section
above found (real, but shown independent of the net-mismatch root cause) is
**left uncorrected**: `ppolyf_u`/`PPOLYF_U_1K`-class resistors have no
polarity between their two poly-contact terminals (only `W`, the bulk/tap
terminal, is asymmetric, and that one already matches on both sides), so a
same-class device pair with `A`/`B` swapped is electrically and
topologically identical either way — confirmed by this fix's own result:
once the class name is corrected, the pair reaches a plain `Match` with the
terminal order exactly as this reference netlist already had it, no further
change needed.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| `vco_vtoi_core` DRC | `run_pv.py drc … --top vco_vtoi_core` | clean | unaffected (no geometry changed by this fix) — `PROOF-376-vbp0-fix.md`'s own clean result stands | **PASS** |
| `vco_block` DRC | `run_pv.py drc … --top vco_block` | clean | `DRC clean: vco_block (D), 0 violations` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (18/18) | **PASS** |
| `vco_block` assembled LVS, device-level | `lvs.xref().each_device_pair()` | every device `Match` | 65/65 `Match`, **0 warnings, 0 mismatches** | **PASS** |
| `vco_block` assembled LVS, net-level | `lvs.xref().each_net_pair()` | every net `Match` | 43/43 `Match`, **0 mismatches** | **PASS** |
| `vco_block` assembled LVS, deck verdict | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `Congratulations! Netlists match.` | **PASS** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 531 tests … OK` (2 new tests added by this fix) | **PASS** |

### Reproducing the assembled-block LVS run

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from layout.pll_top.vco import block
r = block.build(outdir='<workdir>')
open('<workdir>/vco_block.spice','w').write(block.reference_netlist())
"
python3 layout/run_pv.py lvs <workdir>/vco_block.gds <workdir>/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
```

### Reproducing the full device-level and net-level cross-reference

```python
import klayout.db as db
lvs = db.LayoutVsSchematic()
lvs.read('<rundir>/vco_block.lvsdb')
xref = lvs.xref()
top = next(c for c in lvs.netlist().each_circuit() if c.name == 'vco_block')
from collections import Counter
print('devices:', Counter(dp.status() for dp in xref.each_device_pair(top)))
print('nets:', Counter(np.status() for np in xref.each_net_pair(top)))
```

```
devices: Counter({Match (1): 65})
nets: Counter({Match (1): 43})
```

## `lvs-attempt/` renamed to `lvs-clean/`

Per that directory's own stated convention (referenced in
`PROOF-376-vbp0-fix.md`'s body, deferred by issues #371, #372 and #376 in
turn): the combined `vco_block` LVS run now genuinely matches, so
`layout/evidence/vco-layout/lvs-attempt/` is renamed to `lvs-clean/` and
refreshed with this fix's own clean run (`lvs.stdout.log`, `vco_block.cir`,
`vco_block.lvsdb`, `vco_block.spice`). No other evidence file in this
directory needed refreshing (`vco_block.gds`, `drc-clean/*` — geometry and
DRC/connectivity are all byte-for-byte/behaviourally unchanged by this fix).
