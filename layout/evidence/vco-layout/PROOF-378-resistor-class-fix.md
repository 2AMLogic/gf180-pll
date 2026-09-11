# `vco_block` LVS matches: the reference named a device class the deck never extracted

Fix record for [issue #378](https://github.com/2AMLogic/gf180-pll/issues/378),
the last of the leaf defects `PROOF-368-rootcause.md` decomposed issue #368
into (`buffer.py` → `PROOF-372-buffer-fix.md`; `ring.py` →
`PROOF-371-ring-fix.md`; `vtoi_core.py`'s `VBP0`/`VDD_VCO` short →
`PROOF-376-vbp0-fix.md`). Same discipline as all three: every claim below is a
command run against the artifacts committed beside this file.

**The assembled `vco_block` LVS run now reports `Congratulations! Netlists
match.`** — 65/65 devices `Match` (zero `MatchWithWarning`), 43/43 nets
`Match`, circuit-pair status `Match`. `lvs-attempt/` is accordingly renamed to
`lvs-clean/` (the rename #371, #372 and #376 each deferred in turn; earlier
PROOF documents' references to `lvs-attempt/` mean this same directory under
its former name).

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `6e979c4` (PR #379 / issue #376 merged) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.30.9` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.12` |

The disclosed KLayout-version caveat every prior record in this directory
carries (this repo's earliest committed evidence was captured on `0.28.16`,
and newer releases have been observed to report a *false* LVS mismatch on an
unchanged, LVS-clean layout) cuts the *safe* way here: the verdict below is a
**match**, produced by the release that has been observed to over-report
mismatches, and it is corroborated by direct `klayout.db` cross-reference
rather than taken from the deck's own pass line alone.

## The issue's leading hypothesis was wrong — disproved before anything was changed

Issue #378 named, as its strongest (explicitly unconfirmed) lead, the spurious
layout-side circuit **pin** on `NC`/`NOFF`/`NVI`, attributed to
`bias_resistors.py` and `vtoi_core.py` labelling the same logical net on two
different label layers. That lead does not survive contact with the `.lvsdb`.

Dumping *every* net pair's pin counts — not only the mismatching ones — shows
a layout-side pin with no reference counterpart on **thirteen** nets, ten of
which `Match` perfectly:

```
  Match      NB1                 NB1      pins 1/0  terms 4/4
  Match      NB2                 NB2      pins 1/0  terms 4/4
  Match      S1.Y,Y1             Y1       pins 1/0  terms 4/4
  ...
  Match      VBN                 VBN      pins 1/0  terms 10/10
  Match      VBP                 VBP      pins 1/0  terms 8/8
  Match      VBP0                VBP0     pins 1/0  terms 6/6
* Mismatch   NC                  NC       pins 1/0  terms 2/2
* Mismatch   NOFF                NOFF     pins 1/0  terms 2/2
* Mismatch   NVI                 NVI      pins 1/0  terms 2/2
* Mismatch   GND_VCO             GND_VCO  pins 1/1  terms 59/59
```

An extra layout-side pin is therefore **not** what distinguishes the four
failing nets: `VBP0` has the identical `pins 1/0` signature and matches. A
second, independent disproof: the reference netlist's node order for the three
resistors was swapped (`R_RCG GND_VCO NC GND_VCO` instead of
`R_RCG NC GND_VCO GND_VCO`, matching the extracted `.cir`'s own A/B
assignment) and the deck re-run — still `ERROR : Netlists don't match`, byte
for byte the same four nets. Terminal order is not it either; KLayout declares
a resistor's A/B terminals equivalent.

What *does* distinguish the four failing nets is stated plainly by the same
dump: they are exactly the four nets touching the three poly resistors —
`NC`/`NOFF`/`NVI` at their top terminals and `GND_VCO` at all three bottom
terminals — and those three resistors are exactly the three devices the run
reported `MatchWithWarning` rather than `Match`.

## Root cause

`block.RESISTOR_LVS_MODEL` named `ppolyf_u_1k`. The deck extracts `ppolyf_u`.

The deck's own extracted netlist (`lvs-clean/vco_block.cir`) says so directly:

```
R$77 GND_VCO NC   GND_VCO  1960 ppolyf_u L=5.6U W=1U
R$78 GND_VCO NOFF GND_VCO 11550 ppolyf_u L=33U  W=1U
R$79 GND_VCO NVI  GND_VCO 11550 ppolyf_u L=33U  W=1U
```

— class `ppolyf_u`, at 1960/5.6 == 11550/33 == **350 ohm/sq**, the *unmarked*
p+ poly resistor.

**Why the geometry can only ever produce that class.**
`rule_decks/res_derivations.lvs` derives every high-sheet variant as

```
ppolyf_u_h = poly2.and(sab).and(res_mk).and(resistor)...     # PPOLYF_U_1K
```

where `resistor` is `get_polygons(62, 0)`
(`rule_decks/layers_definitions.lvs:79`). `primitives.poly_resistor()` draws
`res_mk` (110, 5), `poly2`, `sab`, `pplus`, contacts and Metal1 — and no
(62, 0) at all. The geometry therefore lands in the *unmarked* branch of that
same file,

```
ppolyf_u_layer = pplus.and(poly2).and(sab).and(res_mk).not_interacting(resistor)...
```

extracted by `res_extraction.lvs:88`'s un-gated
`extract_devices(resistor_with_bulk('ppolyf_u', 350, BResistor))`. The PDK
`run_lvs.py`'s hardcoded `poly_res = "1k"` switch — the entire basis for the
old constant — only selects *which* high-sheet class the **marked** branch
produces. With no (62, 0) drawn, that branch matches nothing in this layout
and the switch is irrelevant to it.

**Where the wrong inference came from.** `PROOF-lvs.md` (issue #367) cited the
deck log line `Extracting PPOLYF_U_1K device` as empirical confirmation. That
line is printed for **every** class the deck attempts, independent of whether
any geometry matches it — `Extracting PPOLYF_U device` appears six lines above
it in the same log:

```
215: ... Extracting PPOLYF_U device
221: ... Extracting PPOLYF_U_1K device
```

The same paragraph also read the extracted resistances "1960/11550/11550 ohms"
as "1000 ohm/sq x L/W". 1960 / 5.6 is 350, not 1000 — the arithmetic that
would have caught this in #367 was stated but not carried out.

**Why a name cost the whole run.** Netlist comparison in KLayout propagates
net matching across device terminals only between device classes it considers
the same. With the two classes named differently, the comparer could pair the
three resistors only as `MatchWithWarning`, and every net whose *only*
remaining unconfirmed adjacency ran through one of them stayed topologically
unconfirmed — `NC`/`NOFF`/`NVI` and, through their shared bottom terminal,
`GND_VCO`. Four nets, exactly the four reported. Neither the pins nor the
terminal order had anything to do with it.

## The fix

One constant, in `layout/pll_top/vco/block.py`:

```python
-RESISTOR_LVS_MODEL = "ppolyf_u_1k"
+RESISTOR_LVS_MODEL = "ppolyf_u"
```

(plus its docstring, rewritten to state what was measured rather than what was
inferred). **No layout geometry changed** — asserted, not assumed: a
layer-by-layer `Region` XOR of the `vco_block.gds` built before and after the
change is empty on all 14 layers.

```
layers compared: 14 | XOR-nonempty layers: NONE -- geometry identical
```

### What this fix does *not* claim

The reference now names the class the deck extracts — it does **not** make the
drawn device the one `design/netlist/vco.spice` asks for. That file specifies
`ppolyf_u_3k` (3000 ohm/sq); the layout draws an unmarked 350 ohm/sq resistor,
so `RCG`/`ROFF`/`RDEG` are 1.96/11.55/11.55 kohm where the schematic implies
16.8/99/99 kohm. That ~8.6x is a real design-level discrepancy in the bias
network (first order: an ~8.6x high constant-gm reference current), and it is
**worse** than the deviation the old constant disclosed, not better. It is
filed separately as
[issue #381](https://github.com/2AMLogic/gf180-pll/issues/381) with the three
candidate resolutions, rather than resolved here: choosing a resistor's sheet
resistance is a design decision with spec consequences, not a side effect of an
LVS-matching fix.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| `vco_block` assembled LVS, deck verdict | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `INFO : Congratulations! Netlists match.` | **PASS** |
| `vco_block` assembled LVS, device-level | `lvs.xref().each_device_pair()` | every device matches | 65/65 `Match`, **0** `MatchWithWarning`, 0 mismatches | **PASS** |
| `vco_block` assembled LVS, net-level | `lvs.xref().each_net_pair()` | every net matches | 43/43 `Match`, 0 mismatches | **PASS** |
| `vco_block` assembled LVS, circuit-level | `lvs.xref().each_circuit_pair()` | match | `Match` | **PASS** |
| `vco_block` DRC | `run_pv.py drc … --top vco_block` | clean | `DRC clean: vco_block (D), 0 violations` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (incl. `VBP0 != VBP`, `NOFF != NVI`) | **PASS** |
| Geometry unchanged by the fix | per-layer `Region` XOR, pre- vs post-fix GDS | empty | empty on all 14 layers | **PASS** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 532 tests … OK` | **PASS** |

Artifacts committed beside this file: `lvs-clean/lvs.stdout.log`,
`lvs-clean/vco_block.cir`, `lvs-clean/vco_block.lvsdb`,
`lvs-clean/vco_block.spice` (the committed reference — identical to
`reference_netlist()`'s own output). `vco_block.gds` is **not** refreshed,
deliberately: the committed one from #376 is bit-for-bit the geometry this run
verified (see the XOR above), and rewriting it would only churn a GDS header
timestamp.

## Reproducing

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from layout.pll_top.vco import block
r = block.build(outdir='<workdir>')
open('<workdir>/vco_block.spice','w').write(block.reference_netlist())
"
python3 layout/run_pv.py lvs <workdir>/vco_block.gds <workdir>/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
python3 layout/run_pv.py drc <workdir>/vco_block.gds --top vco_block --run-dir <drcdir>
python3 -m layout.pll_top.vco.block --check-connectivity
```

### Reproducing the cross-reference (the table above, not the deck's pass line)

```python
import klayout.db as db
from collections import Counter

lvs = db.LayoutVsSchematic()
lvs.read('<rundir>/vco_block.lvsdb')
xref = lvs.xref()
cp = next(p for p in xref.each_circuit_pair()
          if p.first() and p.first().name == 'vco_block')
print("circuit:", cp.status())
print("devices:", Counter(str(dp.status()) for dp in xref.each_device_pair(cp)))
print("nets   :", Counter(str(np.status()) for np in xref.each_net_pair(cp)))
```

Before the fix (`origin/main` @ `6e979c4`):

```
circuit: NoMatch  devices: {'Match': 62, 'MatchWithWarning': 3}  nets: {'Match': 39, 'Mismatch': 4}
```

After:

```
circuit: Match    devices: {'Match': 65}                          nets: {'Match': 43}
```

### Reproducing the "extra pins are harmless" disproof

```python
for np in xref.each_net_pair(cp):
    a, b = np.first(), np.second()
    print(np.status(),
          a.expanded_name() if a else None, b.expanded_name() if b else None,
          "pins", a.pin_count() if a else -1, "/", b.pin_count() if b else -1)
```

### Regression guard

`layout/tests/test_vco_layout.py::PolyResistorLvsClassTests` asserts the two
halves of this fix *against the built geometry*, not against each other's
restatement: the drawn resistors carry no (62, 0) high-sheet marker, the four
layers the unmarked derivation needs are all present, and
`RESISTOR_LVS_MODEL == "ppolyf_u"`. Adding the marker later (one of issue
#381's candidate resolutions) fails that class until the constant is updated
in lockstep, instead of silently re-opening this mismatch.
