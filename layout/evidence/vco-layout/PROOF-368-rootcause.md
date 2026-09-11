# `vco_block` LVS short (issue #368) — root cause found, fix not yet implemented

> **Status update (2026-09-11): half of the fix has landed.**
> [`PROOF-372-buffer-fix.md`](PROOF-372-buffer-fix.md) implements everything
> below for **`buffer.py`** (issue #372) — `vco_out_buffer` is now DRC-clean
> *and* matches a standalone LVS reference netlist of its own, and the
> reproduction script in this file reports zero multi-net Metal1 polygons
> against it. **`ring.py` is still unfixed** (issue #371), so `vco_block` LVS
> still mismatches and everything this record says about `ring.py` still
> stands verbatim. Two details of this record were refined by doing the work:
>
> * `buffer.py` had a **third** short of the same family that items 1 and 2
>   below masked — the inner n-well tap ring's *bottom* band lies across the
>   NMOS/PMOS routing channel, so each stage's plain-Metal1 drain and gate
>   bridges shorted its own nodes to `VDD_VCO` too. `ring.py` should be
>   checked for the same thing rather than assumed to have only the three
>   listed here.
> * "Recommended fix shape" item 1 says to *clip* the wide rail's y-extent.
>   For `buffer.py` that is not sufficient on its own: the clearance a clip
>   would leave (0.11 µm) is narrower than M1.1's own minimum *width*, so the
>   rail was moved wholesale into the clear channel outside the row's pads
>   instead. Same conclusion, one step further.

This is **not** a fix record. It documents a complete, mechanistically-verified
root cause for the connectivity short `PROOF-lvs.md` (issue #367) discovered,
reached by direct KLayout `klayout.db` introspection of the extracted
`.lvsdb`, the assembled `vco_block.gds`, and each affected sub-block's own
standalone GDS (`ring.py`, `buffer.py`). Per this repo's own verification
discipline (CLAUDE.md: "no claim without a testbench"), the root cause below
is reported because it is directly reproducible from commands in this file,
not because it "feels right" — but no code fix accompanies this record. The
actual fix requires new strap geometry in two generators, each verified by a
full DRC + LVS + `connectivity_report()` cycle; issue #368 is decomposed into
two follow-up issues (linked below) that scope that work.

## Provenance

| | |
|---|---|
| Investigated | 2026-09-11 |
| Branch point | `origin/main` @ `31fff27` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.9` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |

Same disclosed KLayout-version deviation as `PROOF-lvs.md` — irrelevant here,
since the finding below is reproduced identically on **standalone** `ring.py`
and `buffer.py` GDS (no LVS deck involved at all, just KLayout's own
`klayout.db.Region`/`Shapes`/`Layout` API against Metal1 geometry and pin
labels), independent of any LVS-deck version sensitivity.

## Summary

`vco_block`'s reported short is not one bug — it is **two independent,
per-generator design gaps**, each masked by a different mechanism, whose
combined effect exactly reproduces every number in issue #368's own report
(39/20 extracted vs. 65/43 expected; the 43-terminal alias list; the
separate 7-terminal `VBP,VDD_VCO` net).

1. **Neither `ring.py` nor `buffer.py` ever deliberately straps its own
   transistors' supply/bias terminals to its own guard ring / n-well tap
   ring.** Each generator draws *four* Metal1 islands that are all labelled
   with real net names (`VDD_VCO`, `GND_VCO`, plus `VBP`/`VBN` in `ring.py`)
   but are **not connected to each other by any drawn metal**:
   - the internal "rail" drawn across each device row (the actual transistor
     terminals),
   - the inner n-well tap ring (`VDD_VCO`),
   - the outer p-type guard ring (`GND_VCO`).

   The only reason these blocks have ever looked "connected" is that a
   *different*, accidental bug (item 2) happens to bridge the internal rail
   to something else with the same net name. Remove that accidental bridge
   without adding a deliberate strap, and the ring's/buffer's own PMOS
   sources and NMOS sources become genuinely floating — a **worse** bug than
   the one reported.

2. **A structural Metal1 pad-sizing overlap in `primitives.mosfet()`,
   combined with each generator's own "one wide rail per net" rail-drawing
   pattern, creates real, DRC-invisible Metal1-to-Metal1 shorts**:
   - `mosfet()`'s `gate_pad` (the gate-contact-tab's own Metal1 pad,
     `primitives.py:394-399`) and the adjacent terminal's `top_pad`/
     `bottom_pad` (`primitives.py:405-421`, the `_terminal_pad()` helper)
     have Y-ranges that overlap by `0.26 - l_um/2` micron whenever
     `l_um < 0.52` (derivation below) — for a *single* device this is
     harmless, because the gate tab sits at a different X than the main
     comp column (see `mosfet()`'s own docstring on the tab's left offset).
   - But `ring.py` (`ring.py:237-244`) and `buffer.py`
     (`buffer.py:201-206`) each turn *one representative stage's* pad into a
     **full-row-width** Metal1 rectangle for `VDD_VCO`/`GND_VCO`
     (and, in `ring.py`, `VBP`/`VBN` too) — and a full-row-width rail's X
     necessarily reaches every *other* stage's own gate pad, whose X is
     *not* offset the same way relative to the rail. The originally-safe,
     per-device Y-overlap becomes a real cross-row short.
   - `ring.py` additionally has a **third, independent** short: the
     Y5→A1 wraparound route's vertical riser (`ring.py:183-184`,
     `prim.route_pads(canvas, src.y_pad, dst.a_gate_pad_bottom, wrap_y)`)
     must cross from the NMOS band (y > 0) down to `wrap_y` (−1.2, chosen to
     duck under every stage's comp/poly) — but the `GND_VCO` rail (item 2,
     above) is *also* Metal1 and spans the entire row width at y ≈ 0, so the
     riser's own Metal1 passes straight through it. This is a plain
     "signal wire crosses a same-layer supply rail with no via/no
     Metal2 hop" bug — the module's own docstring says the route goes
     "below the whole NMOS band, clear of every stage's own comp/poly"
     but does not account for the `GND_VCO` rail also occupying that space.

## Why every earlier check missed this

- **DRC** cannot see it: once two same-layer shapes touch/overlap, KLayout's
  region-merge treats them as *one polygon* before any spacing rule runs —
  there is no "spacing violation" to report between a polygon and itself.
- **`block.connectivity_report()`** (block.py:1092-1141) does run a real
  metal1/via1/metal2 `LayoutToNetlist` extraction — but its own probe list,
  `CONNECTED_PROBES` (block.py:998-1013), only asks two questions per supply
  net: *"does the trunk reach every n-well tap band + the block n-well
  ring?"* (`VDD_VCO`) and *"does the block guard ring reach every sub-block
  guard ring + bank tap strip?"* (`GND_VCO`). **It never probes whether an
  actual transistor's own drawn terminal pad is on the same cluster as the
  guard ring.** Item 1 above (no deliberate device-to-ring strap) is
  therefore invisible to this check by construction, not by oversight in a
  particular run.
- **The two suspects `PROOF-lvs.md` ruled out** (`--lvs_sub` global
  substrate synthesis; `connect_implicit('*')`) were correctly ruled out —
  neither is the mechanism. **The "not yet tried" step it named**
  (an `nplus`/`pplus`-aware `psd`/`nsd`/`ptap`/`ntap` reconstruction) was
  reproduced independently here (see "What was ruled out again" below) and,
  as `PROOF-lvs.md` already found, shows **zero** merged nets — because the
  real mechanism is a **plain Metal1-to-Metal1 geometric overlap**, not a
  derived-implant-layer ambiguity. The generic phrase in issue #368's own
  scope ("a derived-layer proximity effect, not necessarily a raw
  metal-to-metal touch") turned out to name the wrong branch of its own "or"
  — it *is* a raw metal-to-metal touch, just one invisible to DRC for the
  polygon-merge reason above, not because it lives on some other derived
  layer.

## Reproduction (standalone `ring.py`, no LVS deck, no PDK needed)

```python
import sys; sys.path.insert(0, ".")
from layout.pll_top.vco import ring
ring.build(outdir="/tmp/ring_repro", draw_decap=False)
```

```python
import klayout.db as db, collections
ly = db.Layout(); ly.read("/tmp/ring_repro/vco_ring.gds")
top = ly.top_cell(); top.flatten(-1, True); dbu = ly.dbu

def region(l, d):
    return db.Region(top.begin_shapes_rec(ly.layer(l, d))).merged()

def texts(l, d):
    out = []
    it = top.begin_shapes_rec(ly.layer(l, d))
    while not it.at_end():
        s = it.shape()
        if s.is_text():
            pt = it.itrans() * db.Point(s.text.x, s.text.y)
            out.append((s.text.string, pt.x * dbu, pt.y * dbu))
        it.next()
    return out

metal1 = region(34, 0)          # Metal1 drawing layer
m1_texts = texts(34, 10)        # Metal1 *label* purpose datatype (pin text)
polys = list(metal1.each_merged())
poly_nets = collections.defaultdict(set)
for name, x, y in m1_texts:
    pt = db.Point(int(x / dbu), int(y / dbu))
    for i, p in enumerate(polys):
        if p.bbox().contains(pt) and not (
            db.Region(p) & db.Region(db.Box(pt.x - 1, pt.y - 1, pt.x + 1, pt.y + 1))
        ).is_empty():
            poly_nets[i].add(name)
            break

for i, n in poly_nets.items():
    if len(n) > 1:
        print(polys[i].bbox(), sorted(n))
```

Output (as of this record):

```
poly bbox (-2.12,-1.34)-(67.32,8.34) um: {'GND_VCO','S1.Y'..'S5.Y','VBN','VDD_VCO','Y1'..'Y5','Y5_CLK_IN'}
poly bbox (-2.12, 8.22)-(66.00,10.78) um: {'VBP','VDD_VCO'}
```

— i.e. `ring.py`'s own standalone `vco_ring.gds` already contains both
shorts, with **zero LVS deck involved**. The same script against
`buffer.py`'s standalone `vco_out_buffer.gds` shows:

```
poly bbox (-1.32,-0.02)-(23.57,6.58) um: {'BUF1.NB1','BUF2.NB2','BUF3.CLK','CLK','GND_VCO','VDD_VCO','Y5'}
```

And the same script against the *real* `guard_ring()`/tap-strip-only
polygons (single-label, in both files) confirms items 1's "four disconnected
islands" claim directly — `ring.py` draws an outer `GND_VCO` guard-ring
polygon at `(-4.82,-3.82)-(70.82,15.08)` and an inner `VDD_VCO` tap-ring
polygon at `(-1.32,11.24)-(67.32,12.08)`, **neither of which shares a single
point with** the two shorted polygons above (nearest gap ≈ 0.46-0.58 μm,
matching `TAP_GAP_UM`/`OUTER_MARGIN_BELOW_UM` — a deliberate clearance with
no strap ever drawn across it).

## The gate-pad/terminal-pad overlap, derived algebraically

For a `primitives.mosfet()` instance with channel length `l_um` and the
module's own `SD_OVERHANG_UM = 0.5`, `GATE_TAB_H_UM = 0.4`,
`METAL1_PAD_MARGIN_UM = 0.12`, `CONTACT_ROW_MARGIN_UM = 0.1`,
`CONTACT_SIZE_UM = 0.22` (all `primitives.py` module constants):

```
gate_pad upper edge  = y1 + l_um/2 + GATE_TAB_H_UM/2 + METAL1_PAD_MARGIN_UM
                      = y1 + l_um/2 + 0.32
top_pad  lower edge  = y1 + l_um + SD_OVERHANG_UM
                        - CONTACT_ROW_MARGIN_UM - CONTACT_SIZE_UM - METAL1_PAD_MARGIN_UM
                      = y1 + l_um + 0.5 - 0.44
overlap              = (gate_pad upper) - (top_pad lower)
                      = 0.26 - l_um/2
```

`overlap > 0` (a real Y-range overlap) whenever `l_um < 0.52`. This repo's
own device tables give:

| Device | `l_um` | computed overlap |
|---|---|---|
| `MPH`/`MNT` (ring stage, `devices.STAGE_FETS`) | 0.5 | **0.01 μm** |
| `MP`/`MN` (ring stage) | 0.28 | 0.12 μm (not turned into a wide rail — safe on its own) |
| Buffer inverter fets (`devices.BUFFER_STAGES`) | 0.28 | **0.12 μm** (turned into a wide rail — unsafe) |

Verified directly (not just algebraically) by calling `stage.build_stage()`
and `primitives.mosfet()` in isolation and printing the returned pad tuples
— see the issue #368 investigation transcript for the exact printed values
(`vbp_pad=(-1.12, 9.69, -0.48, 10.33)`, `vdd_pad=(0.02, 10.32, 9.98, 10.78)`,
overlap `10.33 - 10.32 = 0.01`).

## What was ruled out again

Independently reproduced `PROOF-lvs.md`'s own "not yet tried" reconstruction
(an `nplus`/`pplus`-aware `psd`/`nsd`/`ptap`/`ntap` boolean-region
replication of `general_derivations.lvs`'s own formulas, run directly
against `vco_block.gds` via `klayout.db.Region`): zero overlaps between any
pair of `{ptap, psd, nsd, ntap}`, and zero contacts landing on more than one
of those four derived regions. This confirms the mechanism is **not** a
derived-implant-layer ambiguity — it is the plain Metal1 overlap documented
above.

## Recommended fix shape (not implemented here)

For each of `ring.py` and `buffer.py`:

1. **Remove the accidental overlaps** — clip each wide supply/bias rail's
   Y-extent so it does not reach into a neighbouring net's pad (needs at
   least `dev.DRC_METAL1_MIN_SPACE_UM` = 0.23 μm clearance, M1.2a). For
   `ring.py`'s wraparound riser specifically, route it around the `GND_VCO`
   rail (a Metal1→via1→Metal2→via1→Metal1 hop over the rail, the same
   "Metal2 has no spacing relationship with Metal1" escape `block.py`'s own
   routing already relies on) rather than trying to trim the rail — the
   riser and the rail cross by necessity, not by a fixable margin.
2. **Add the deliberate strap this repo's guard-ring architecture assumed
   already existed**: a real Metal1 (or Metal1→via1→Metal2→via1→Metal1)
   connection from each generator's own internal supply rail to its own
   n-well tap ring (`VDD_VCO`) and outer p-type guard ring (`GND_VCO`).
   Mirror `mirror.py`'s own `rail_stub()` pattern (mirror.py:1003-1004),
   which already does exactly this per-bank, per-fet tie — `ring.py`'s
   and `buffer.py`'s per-row rail never had an equivalent.
3. Re-run DRC, LVS (against `block.reference_netlist()`), and
   `block.connectivity_report()` after each change — this is a real
   physical redesign of two generators' power distribution, not a
   metadata/labelling fix, and needs the same iterative real-tool
   verification loop `PROOF-lvs.md`'s own increment did, not just a
   read-through.
4. Once `ring.py`'s and `buffer.py`'s own device-to-ring straps exist,
   consider adding `CONNECTED_PROBES` entries in `block.py` that check
   device-terminal-to-guard-ring continuity directly (not just
   ring-to-ring), so a future regression of this exact kind is caught by
   `connectivity_report()` instead of requiring a full device-level LVS run.

Decomposed as follow-up issues from #368 (see that issue's own comments for
the exact numbers): one issue per generator (`ring.py`, `buffer.py`), each
scoped to items 1-3 above for that one file.
