# The VCO bias resistors are now the device the schematic specifies — `ppolyf_u_3k`, drawn and extracted

Fix record for [issue #381](https://github.com/2AMLogic/gf180-pll/issues/381),
filed out of [`PROOF-378-resistor-class-fix.md`](PROOF-378-resistor-class-fix.md)
once that fix made the discrepancy visible. Same discipline as every other
record in this directory: every claim below is a command run against the
artifacts committed beside this file, cross-referenced directly against the
resulting `.lvsdb` via `klayout.db.LayoutVsSchematic` or measured in ngspice,
not inferred from a deck's pass/fail line alone.

The engineering decision this record implements is
[`spec/decision-records/DR-009-vco-bias-resistor-device-class.md`](../../../spec/decision-records/DR-009-vco-bias-resistor-device-class.md).

## What was wrong

`design/netlist/vco.spice` declares `XRCG`/`XROFF`/`XRDEG` as **`ppolyf_u_3k`**
(3000 Ω/sq). `primitives.poly_resistor()` drew the **unmarked** `ppolyf_u`
class (350 Ω/sq): it modelled the PDK pcell body `polyf_res_inst()`, which
never draws GDS `(62, 0)`, the marker both decks use to tell the high-sheet
family apart from the unmarked one. Measured (not quoted — the witness
resistors of `sim/vco-bias-current`, typical/27 °C/3.30 V):

| Device | W/L (µm) | As drawn before this fix | As specified (this fix) |
|---|---|---|---|
| `RCG` | 1 / 5.6 | 2.191 kΩ | 18.19 kΩ |
| `ROFF`, `RDEG` | 1 / 33 | 12.29 kΩ | 103.99 kΩ |

The measured class ratio at the `RCG` geometry is **8.301×** at typical/27 °C
and spans **6.78 … 9.72×** over the 13-bundle × 3-temperature × 3-supply grid.
Issue #381's stated "~8.6×" was derived from the decks' nominal 350 / 3000 Ω/sq;
8.30× is the same number measured through the models, including both devices'
contact head resistance.

`PROOF-378` had corrected the *reference netlist* to name the class the deck
extracted, which is why `vco_block` LVS matched — on the wrong device. DRC
passed, LVS passed, and the schematic-level campaigns never see the layout, so
nothing in the flow could catch this.

> **Correction to `PROOF-378-resistor-class-fix.md`.** That record states, in
> passing, that the PDK's own `ppolyf_u_3k` pcell instance "calls the identical
> `polyf_res_inst()` body". It does not: the high-sheet family has its own pcell
> class, `ppolyf_u_high_Rs_resistor` (`cells/res.py:1202`), calling
> `draw_ppolyf_u_high_Rs_res()` (`cells/draw_res.py:851`), which *does* draw
> `layer["resistor"]` = `(62, 0)` (`cells/layers_def.py:43`). `sm141064.ngspice`
> likewise lists `ppolyf_u_3k` ("3-terminal 3k high-Rs p+ poly resistor on field
> oxide", line 79) and `ppolyf_u` (line 72) as two devices. `PROOF-378`'s own
> constant change was correct for the geometry as it then stood; that one
> sentence of its reasoning is withdrawn here rather than edited in place, per
> this directory's append-only convention.

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `fc0be07` (PR #380 / issue #378 merged) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.28.16` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |
| ngspice (bias-current campaign) | `ngspice-46` |

Same disclosed KLayout-version deviation every record in this directory
carries: releases newer than `0.28.16` have been observed to report a *false*
LVS mismatch on an unchanged, LVS-clean layout. That failure mode can only make
a result here **worse**, never better — the result below is a full **match**,
made on `0.28.16` directly — so it is not in play.

## The fix, geometrically

`poly_resistor()` now follows the PDK's own high-Rs recipe. Adding the marker
alone would not have been enough: `pres.drc`'s `pres_poly` derivation is
`...not_interacting(resistor)` and `hres.drc`'s `hres_poly` is
`...interacting(resistor)`, so the marker also **moves the geometry to a
different rule set**, and two of those rules contradict the shape the unmarked
recipe draws.

| Layer | Before (unmarked `ppolyf_u` recipe) | After (high-Rs recipe) | Rule that forces it |
|---|---|---|---|
| `(62, 0)` `resistor` | not drawn | encloses the whole resistor poly2 (body + both contact lands) by 0.5 µm | HRES.4 (≥ 0.4 µm, and no poly outside the marker at all) |
| `pplus` | one rectangle enclosing the entire footprint by 0.3 µm | **two** rectangles, one per contact land, each ending flush with `res_mk` so the body is un-implanted | HRES.12a (resistor length = poly inside `sab`, **outside** `pplus`) |
| `sab` | length-axis extent coincident with `res_mk` | overhangs `res_mk` by exactly 0.1 µm at each end | HRES.10 (pplus-over-sab overlap is a min **and max** 0.1 µm) |
| contacts | inset 0.22 µm from the `res_mk` boundary | inset 0.22 µm from the **`sab`** boundary, i.e. 0.32 µm from `res_mk` | HRES.8 (contact-to-salicide-block ≥ 0.22 µm) |

Drawn `W`/`L` are unchanged (1 × 5.6 / 33 / 33 µm), so no resistance value
moved except by being the right device class. `vco_block`'s footprint is
unchanged at **172.520 × 184.480 µm** — the marker and the re-shaped implant
fit inside the bias block's existing guard-ring margins, so no floorplan
number moves.

## The other half: `$poly_res` is a process option, not geometry

`res_extraction.lvs` derives **all three** of `ppolyf_u_1k`/`_2k`/`_3k` from the
same `ppolyf_u_h` layer, selected by the deck's `$poly_res` switch — the three
are one drawn device separated by a fab implant option. The PDK's own
`run_lvs.py` hardcodes `switches["poly_res"] = "1k"` for **all four**
`--variant` letters and exposes no CLI override, so the identical, unchanged
GDS extracts differently depending only on how the deck is invoked:

```
# --poly-res pdk  (the PDK runner's own hardcoded default)
R$1 GND_VCO NVI GND_VCO 33000 ppolyf_u_1k L=33U W=1U

# --poly-res 3k   (this repo's ratified option, DR-009 Decision 2/3)
R$1 GND_VCO NVI GND_VCO 99000 ppolyf_u_3k L=33U W=1U
```

`layout/harness/lvs.py` therefore passes `3k` through `_pdk_lvs_poly_res.py`,
a shim that imports the PDK runner as a module, re-uses that runner's **own**
docopt parsing and **own** `generate_klayout_switches()`, replaces exactly one
dict key, and calls the runner's own `main()`. The deck file, the klayout
invocation and the other ~20 switches are the PDK's, unmodified — nothing is
forked, so a PDK update cannot leave a stale copy of its switch table behind.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| `vco_bias_resistors` DRC | `run_pv.py drc … --top vco_bias_resistors` | clean | `DRC clean: vco_bias_resistors (D), 0 violations` | **PASS** |
| `vco_block` DRC | `run_pv.py drc … --top vco_block` | clean | `DRC clean: vco_block (D), 0 violations` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (18/18) | **PASS** |
| `vco_block` LVS, deck verdict | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `Congratulations! Netlists match.` (deck log also records `POLY_RES Selected is 3k`) | **PASS** |
| `vco_block` LVS, device-level | `lvs.xref().each_device_pair()` | every device `Match` | 65/65 `Match`, 0 warnings, 0 mismatches | **PASS** |
| `vco_block` LVS, net-level | `lvs.xref().each_net_pair()` | every net `Match` | 43/43 `Match`, 0 mismatches | **PASS** |
| Extracted resistor class | `grep ppolyf vco_block.cir` | `ppolyf_u_3k`, 16.8 k / 99 k | `R$77 … 16800 ppolyf_u_3k L=5.6U W=1U`, `R$78`/`R$79 … 99000 ppolyf_u_3k L=33U W=1U` | **PASS** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 540 tests … OK` | **PASS** |
| `sim/tests` | `python3 -m unittest discover -s sim/tests -t sim/tests` | pass | `Ran 433 tests … OK` | **PASS** |

The device class now agrees on **both** sides of the comparison, which is what
issue #378 could not achieve without this geometry change:

```
_RCG  | layout class: ppolyf_u_3k | reference class: PPOLYF_U_3K
_ROFF | layout class: ppolyf_u_3k | reference class: PPOLYF_U_3K
```

## Bias-current impact, measured

`sim/vco-bias-current/records/20260911-172350-da0bb1e.md` — 234 points
(13 corner bundles × 3 temperatures × 3 supplies × 2 band codes), overall
**PASS**. Two bias generators side by side at every point: `design/netlist/
vco.spice`'s own `.subckt vco_bias` (as specified) and a counterfactual derived
mechanically from it with only the three resistors' model token changed (the
device the pre-#381 layout would have manufactured).

At `spec/pll.md`'s own named 100 MHz reference point (band 5, Vctrl 1.8 V):

| Quantity | As specified (this fix) | As the old layout drew it | Ratio |
|---|---|---|---|
| Bias-generator supply current, typical/27 °C/3.30 V | 105.4 µA | 1452 µA | 13.8× |
| Bias-generator supply current, over the whole grid | 68.7 … 195.6 µA | 970 … 2163 µA | 7.4 … 20.4× |
| Per-stage ring starving current (replica `MNT`), over the grid | 19.1 … 48.4 µA | 199.5 … 397.6 µA | ~10× |
| Bias + 5-stage ring starving budget, over the grid | 164 … 436 µA | 1995 … 4131 µA | — |

`spec/pll.md`'s power section ratifies **318 µA** for the whole `vdd_vco`
domain at 100 MHz (bias + ring + output buffer). The counterfactual bias
generator **on its own** exceeds that at every one of the 234 points, by 3.1×
at its own best corner — a hard, spec-anchored statement of what the layout
defect cost, and the campaign's own `min` check.

No absolute pass/fail is placed on the as-specified arm, deliberately: the
318 µA figure is the worst of 159 grid points at a fixed *output frequency*
(90–110 MHz), reached at a corner-dependent band/Vctrl, while this deck holds
the operating *point* fixed and lets f_osc move with the corner. A `max` check
on the as-specified arm would be testing the corner's frequency, not the bias
network. The campaign's record states that limitation in its own Methodology
field rather than burying it.

**No `sim/` record is invalidated by this fix.** The design every record was
made against is unchanged; what changed is that the layout now builds it.

## The structural half of the fix

The geometry change alone would not prevent a recurrence — the defect survived
precisely because each artifact was individually self-consistent.
`layout/tests/test_vco_layout.py::PolyResistorLvsClassTests` now ties four
things together and fails if any one of them drifts:

1. the `(62, 0)` marker is drawn on every bias resistor, and encloses the whole
   resistor poly by at least HRES.4's 0.4 µm (plus direct checks that the
   implant leaves the body clear, that the pplus-over-sab overlap is exactly
   0.1 µm at each end, and that no contact touches `sab`);
2. `block.RESISTOR_LVS_MODEL` names a high-sheet class, never the unmarked one;
3. that class is exactly the token `design/netlist/vco.spice` carries on
   `XRCG`/`XROFF`/`XRDEG` — **read out of the committed export**, not restated
   in the test;
4. it equals `ppolyf_u_<layout.harness.lvs.POLY_RES>`, so the reference netlist
   and the switch the LVS run is actually made with cannot disagree.

`sim/tests/test_vco_bias_counterfactual.py` does the same job on the sim side:
it re-derives the counterfactual arm from the current schematic export and
fails if the committed file has gone stale or differs by more than the three
model tokens.

## Reproducing

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from layout.pll_top.vco import block
block.build(outdir='<workdir>')
open('<workdir>/vco_block.spice','w').write(block.reference_netlist())
"
python3 layout/run_pv.py drc <workdir>/vco_block.gds --top vco_block --run-dir <rundir>
python3 layout/run_pv.py lvs <workdir>/vco_block.gds <workdir>/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
# and, for the PDK runner's own hardcoded poly option:
python3 layout/run_pv.py lvs … --poly-res pdk

python3 sim/run_corners.py sim/vco-bias-current/testbench -j 4
```
