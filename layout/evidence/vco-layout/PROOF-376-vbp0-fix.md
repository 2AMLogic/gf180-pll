# `vtoi_core.py`'s half of the `VBP0`/`VDD_VCO` short — fixed, root-caused directly

Fix record for [issue #376](https://github.com/2AMLogic/gf180-pll/issues/376),
the third of the three follow-ups `PROOF-368-rootcause.md` decomposed issue
#368 into: the first, `buffer.py`, is `PROOF-372-buffer-fix.md` (issue #372,
merged); the second, `ring.py`, is `PROOF-371-ring-fix.md` (issue #371,
merged via PR #377). Same discipline as both: every claim below is a command
run against the artifacts committed beside this file.

**Every device in the assembled `vco_block` now matches its reference
1:1** — all 65 devices (`Match`: 62, `MatchWithWarning`: 3, the 3 being the
already-disclosed `RESISTOR_LVS_MODEL` deviation, pre-existing and
unrelated to this fix). The `VBP0`/`VDD_VCO` short this issue names is
gone. The assembled `vco_block` LVS run still does **not** report
`Congratulations! Netlists match.` — but for a distinct, newly-exposed,
pre-existing reason unrelated to this fix, filed separately as
[issue #378](https://github.com/2AMLogic/gf180-pll/issues/378) (see "How far
this moves the assembled block" below).

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `9994427` (PR #377 / issue #371 merged) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.30.9` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.12` |

Same disclosed KLayout-version deviation `PROOF-lvs.md`/`PROOF-368-rootcause.md`/
`PROOF-372-buffer-fix.md`/`PROOF-371-ring-fix.md` all carry: this repo's
earliest committed DRC/LVS evidence was captured on `KLayout 0.28.16`, and
releases newer than that have been observed to report a *false LVS
mismatch* on an unchanged, LVS-clean layout. That caveat is irrelevant to
the device-level result reported here (below), which was confirmed by
direct `klayout.db` netlist cross-reference, not by trusting the deck's
own pass/fail line alone.

## Root cause

`vtoi_core.py`'s PMOS row is *top*-aligned to `plan.pmos_top` (`_y_bottom()`'s
own pfet convention — a shorter device's own body sits higher, not lower, so
`MSU1`'s own `l=20 um` channel, the tallest thing in the row, can reach all
the way down to `plan.pmos_bottom`). But every PMOS-row device's own
**bottom** (source) pad still has to reach the inter-row channel below, and
`plan.tap_band_bottom` (the `VDD_VCO` n-well tap band `build()` draws along
the row's own bottom edge, spanning the *entire* row width) sits directly in
that path for every one of them, not just `MSU1`. The pre-fix code used a
plain `escape()` column there — a single Metal1 wire straight down to the
channel, what every other mesh-routed net in this block uses — which runs
directly through that band's own drawn Metal1, merging the escaping net
into `VDD_VCO`.

Direct `klayout.db.LayoutToNetlist` connectivity probing (not assumed)
confirms all **five** of this row's own bottom/gate nets (`NA`, `VBPC`,
`VFIX`, `VBP0`, `NSU`) showed this identical merge before the fix —
`VBP0` is the only one of the five with a boundary pin exposed at the
`vco_block` level, which is why issue #376 could only ever see it as its own
separate `VBP0`/`VDD_VCO` short (the other four were merged into the same
`VDD_VCO` net internally, but have no boundary pin of their own to expose
the short through at the assembled-block level).

### Reproduction: probing each PMOS-row bottom pad's own Metal1 cluster

```python
import sys; sys.path.insert(0, '.')
import klayout.db as db
from layout.pll_top.vco import vtoi_core, primitives as prim

result = vtoi_core.build(outdir='<workdir>')
plan, canvas = result.plan, result.canvas
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(canvas.layout, canvas.top, []))
layers = {n: l2n.make_polygon_layer(canvas.layout.layer(*prim.LAYER[n]), n)
          for n in ('metal1', 'via1', 'metal2')}
l2n.connect(layers['metal1']); l2n.connect(layers['via1']); l2n.connect(layers['metal2'])
l2n.connect(layers['metal1'], layers['via1']); l2n.connect(layers['via1'], layers['metal2'])
l2n.extract_netlist()

def cluster(x, y):
    n = l2n.probe_net(layers['metal1'], db.DPoint(x, y))
    return n.cluster_id if n else None

tb = plan.tap_band_bottom
vdd = cluster(50.0, (tb[1] + tb[3]) / 2.0)
for name in ('MP1', 'MP2', 'MPR', 'MSUM', 'MSU1'):
    it = next(i for i in plan.pmos if i.name == name)
    x = it.x0 + it.width / 2.0
    y_bottom = plan.pmos_top - vtoi_core.device_height_um(it.fet.l_um)
    print(name, cluster(x, y_bottom + 0.02))
```

**Before** (`vtoi_core.py` on `origin/main` @ `9994427`, no `_pmos_row_escape()`):

```
VDD_VCO cluster: 7
MP1 bottom pad cluster: 7   == VDD_VCO
MP2 bottom pad cluster: 7   == VDD_VCO
MPR bottom pad cluster: 7   == VDD_VCO
MSUM bottom pad cluster: 7  == VDD_VCO   (MSUM's bottom net is VBP0)
MSU1 bottom pad cluster: 7  == VDD_VCO
```

**After** (this fix):

```
VDD_VCO cluster: 12
MP1 bottom pad cluster: 7    (separate)
MP2 bottom pad cluster: 11   (separate)
MPR bottom pad cluster: 3    (separate)
MSUM bottom pad cluster: 5   (separate)   (MSUM's bottom net is VBP0)
MSU1 bottom pad cluster: 10  (separate)
```

Every one of the five now extracts as its own distinct net, separate from
`VDD_VCO` — matching `layout/tests/test_vco_layout.py`'s
`VtoiCoreNetSeparationTests` committed alongside this fix.

## The fix

All of it is in `layout/pll_top/vco/vtoi_core.py`. No other file changed.

| Change | Why this shape |
|---|---|
| `_pmos_row_escape()`: a new escape variant for every PMOS-row bottom/gate pad, replacing the plain `escape()` call those pads used | Metal2 has no spacing relationship with Metal1 at all — the same fact `block.py`'s own top-level routing and `ring.py`'s #371 fix both already lean on for an analogous same-layer crossing |
| Runs ordinary Metal1 from the pad down to just above `plan.tap_band_bottom`'s own drawn edge, hops onto Metal2 for exactly the crossing (`via1_stack` + a short Metal2 jog + `via1_stack` back down), then resumes the ordinary Metal1 `escape()` for the rest of the descent | Unconditional for *every* PMOS-row escape, regardless of whether its own x happens to fall inside the tap band's drawn extent — the same "no obstruction inventory needed" shape `ring.py`'s own wraparound-riser fix (#371) used for an analogous same-layer crossing; an earlier, position-conditional version of a similar fix in `ring.py` missed a case, so this one deliberately doesn't try to be clever about which pads actually need it |
| Clearance computed from `prim.METAL1_PAD_MARGIN_UM` + `dev.DRC_METAL1_MIN_SPACE_UM` (M1.2a) + `via1`'s own landing-pad half-width, not from `tap_band_bottom`'s bare comp-box edge | `tap_strip()` itself grows the tap band's own drawn Metal1 pad past the comp box `tap_band_bottom` gives; it's the *via1 landing pad*, not the hop point itself, that has to clear the tap band's own drawn Metal1 edge by the real DRC minimum |

Applied to both the bottom (source) pad and — where the gate is not tied to
`GND_VCO` (`MSU1`'s own always-on gate is the one exception, tied directly
to the guard ring, unaffected) — the gate pad, since both sit above the same
tap band and both used the same plain `escape()` before.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| Reproduction script, post-fix | script above, all 5 PMOS-row bottom pads | none share `VDD_VCO`'s cluster | none do (see table above) | **PASS** |
| `vco_vtoi_core` DRC | `run_pv.py drc … --top vco_vtoi_core` | clean | `DRC clean: vco_vtoi_core (D), 0 violations` | **PASS** |
| `vco_block` DRC | `run_pv.py drc … --top vco_block` | clean | `DRC clean: vco_block (D), 0 violations` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (18/18, incl. `VBP0 != VBP`) | **PASS** |
| `vco_block` assembled LVS, device-level | `lvs.xref().each_device_pair()` on the resulting `.lvsdb` | every device matches | 65/65: `Match` 62, `MatchWithWarning` 3 (pre-existing `RESISTOR_LVS_MODEL` deviation), **0 device mismatches** | **PASS** |
| `vco_block` assembled LVS, deck verdict | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `ERROR : Netlists don't match` — 4 of 43 nets (`GND_VCO`, `NC`, `NOFF`, `NVI`) still mismatch, for a cause independent of this fix (see below) | **mismatch — separate, pre-existing, newly-exposed defect, see below** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 529 tests … OK` | **PASS** |

### On the remaining net-level mismatch

Direct `klayout.db.LayoutVsSchematic` cross-reference (`lvs.xref()`) of the
post-fix `.lvsdb` shows the 4 remaining net-level mismatches are not a
connectivity defect: every device's own terminal-to-net assignment matches
the reference exactly (see the device-pair table above — 65/65). The 3
nets `NC`/`NOFF`/`NVI` each carry a spurious circuit **pin** on the layout
side (`each_net_pin_pair()`: layout pin named `NC`, reference pin `None`)
that `block.reference_netlist()`'s `.subckt` line correctly does not
declare (those are internal nodes, not top-level I/O); `GND_VCO` then also
shows `Mismatch` despite **identical** terminal and pin counts on both
sides (59/59, 1/1), most likely as a downstream side effect of the other
three rather than a defect of its own. This pattern is **not present before
this fix** — before it, `NC`/`NOFF`/`NVI` couldn't even be name-matched
between layout and reference at all (they were entangled inside the larger
`VBP0`/`VDD_VCO` short), so this specific defect was invisible until the
bigger short was removed — the same decomposition pattern #368 → #371/#372/#376
already used twice. Filed as
[issue #378](https://github.com/2AMLogic/gf180-pll/issues/378) rather than
pulled into this one; its own Evidence section has the full `.lvsdb`
introspection and the leading (unconfirmed) hypothesis.

**`lvs-attempt/` is deliberately not renamed to `lvs-clean/`.** This fix
closes out its own named defect (`VBP0`/`VDD_VCO`) completely — but the
*combined* `vco_block` LVS run still mismatches on the newly-separately-scoped
`NC`/`NOFF`/`NVI`/`GND_VCO` defect above, which is not in this issue's
control. `lvs-attempt/` is refreshed with this fix's own run (still a
mismatch, but a different, smaller, well-understood one) so the next
increment starts from an accurate baseline.

Artifacts committed beside this file: `vco_block.gds`, `vco_vtoi_core.gds`,
`drc-clean/drc-block.stdout.log` + `vco_block_main.lyrdb`,
`drc-clean/drc-vtoi-core.stdout.log` + `vco_vtoi_core_main.lyrdb`,
`drc-clean/connectivity-block.log`, and a refreshed `lvs-attempt/`
(`lvs.stdout.log`, `vco_block.cir`, `vco_block.lvsdb`, `vco_block.spice`).

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

### Reproducing the device-level cross-reference

```python
import klayout.db as db
lvs = db.LayoutVsSchematic()
lvs.read('<rundir>/vco_block.lvsdb')
xref = lvs.xref()
top = next(c for c in lvs.netlist().each_circuit() if c.name == 'vco_block')
for dp in xref.each_device_pair(top):
    if dp.status() != db.NetlistCrossReference.Match:
        print(dp.status(), dp.first(), dp.second())
```
