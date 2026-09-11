# `buffer.py`'s half of the issue-#368 short — fixed, and LVS-clean on its own

Fix record for [issue #372](https://github.com/2AMLogic/gf180-pll/issues/372),
one of the two follow-ups [`PROOF-368-rootcause.md`](PROOF-368-rootcause.md)
decomposed issue #368 into (this one is `buffer.py`; `ring.py` is the sibling,
issue #371). That record is a root cause without a fix; this one is the fix,
with the same discipline applied to it: every claim below is a command in this
file, run against the artifacts committed beside it.

The headline result is stronger than the issue asked for. `vco_out_buffer`
now has a **standalone LVS reference netlist of its own** and **matches it**:

```
INFO : Congratulations! Netlists match.
```

That makes the output buffer the first VCO sub-block with a device-level LVS
proof, not just a DRC-clean claim.

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `1c918b0` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.30.9`/`0.30.10` — see below |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |

**Disclosed KLayout-version deviation**, same one `PROOF-lvs.md` and
`PROOF-368-rootcause.md` carry: this repo's earliest committed DRC/LVS
evidence was captured on `KLayout 0.28.16`, and `layout/README.md`'s "The two
KLayouts" section records that releases newer than that have been observed to
report a *false LVS mismatch* on an unchanged, LVS-clean layout. That failure
mode can only make a result here **worse**, never better — and the result
here is a **match**, produced on `0.30.10`. Nothing in this record depends on
the version being favourable.

## What was wrong (three things, one of them not in the issue's own text)

`PROOF-368-rootcause.md` names two per-generator gaps. Reproducing it against
`buffer.py` in isolation turned up a third, of exactly the same family, that
the first two were masking:

1. **No deliberate device-to-ring strap.** The internal per-row `VDD_VCO` /
   `GND_VCO` rails, the inner n-well tap bands and the outer p guard ring
   were four separately-labelled Metal1 islands never joined by any drawn
   metal (nearest gap ≈ 0.46–0.58 µm, i.e. `TAP_GAP_UM` /
   `OUTER_MARGIN_BELOW_UM` — deliberate clearance, no strap across it).
2. **The full-row-width rails sat on stages 2 and 3's own gate pads.**
   `primitives.mosfet()`'s gate pad and its adjacent terminal pad overlap in
   *y* by `0.26 - l/2` µm (0.12 µm at these 0.28 µm-long inverter fets).
   Harmless per device — the gate tab is at a different *x* — but a rail
   drawn at a terminal pad's own *y* and stretched across the row reaches
   every *other* stage's gate tab, whose *x* is not offset the same way.
   Stage 1's tab falls left of `row_x0` and was never affected; stages 2 and
   3's fall inside it.
3. **(New) The inner n-well tap ring's bottom band lies across the
   NMOS/PMOS routing channel**, and each stage's drain bridge and gate
   bridge were plain Metal1 risers straight through it — so every stage's
   own output and input node was shorted to `VDD_VCO` as well. This is not
   in issue #372's text; it is item 2's twin, found by running the
   reproduction script against `buffer.py` alone rather than reading the
   generator.

## Reproduction of the "before" state

Exactly `PROOF-368-rootcause.md`'s script, pointed at `buffer.py`
(`git stash`-free: build the pre-fix generator from `origin/main` @ `1c918b0`):

```python
import sys; sys.path.insert(0, ".")
from layout.pll_top.vco import buffer
buffer.build(outdir="/tmp/buf_repro")
```

then that record's merge-and-label script against
`/tmp/buf_repro/vco_out_buffer.gds`:

```
poly bbox (-1.32,-0.02)-(23.57,6.58) um: ['BUF1.NB1','BUF2.NB2','BUF3.CLK','CLK','GND_VCO','VDD_VCO','Y5']
multi-label polys: 1
```

And the same pre-fix GDS against **this record's own** reference netlist
(`lvs-buffer/vco_out_buffer.spice`, i.e. the fix's testbench applied to the
unfixed layout — a negative control for the whole result below):

```
LVS mismatch: vco_out_buffer (D) layout != schematic
pre-fix extracted nets: 2 devices: 2
    7  BUF1.NB1,BUF2.NB2,BUF3.CLK,CLK,GND_VCO,VDD_VCO,Y5
    1  GND_VCO
```

Two nets and two devices extracted from a six-transistor block: the deck sees
one enormous shorted node, and the two transistors it does recognise are
whatever survives it.

## The fix

All of it is in `layout/pll_top/vco/buffer.py`. `primitives.py` is unchanged —
the pad-overlap geometry in item 2 is a property of every `mosfet()` this repo
draws, and narrowing it would change every block's DRC-proven geometry at
once; the generator's job is not to stretch a rail across it.

| # | Change | Why this shape |
|---|---|---|
| 1 | Each supply rail is one full-row-width Metal1 band in the **clear channel outside** its row's pads — below the NMOS `GND_VCO` pads, above the PMOS `VDD_VCO` pads — instead of across them | Structurally removes item 2: there is no gate pad in either channel at all, so the failure cannot recur by a margin being shaved |
| 2 | Each band runs **into** the ring that biases the same net (the outer p ring for `GND_VCO`, the n-well tap band for `VDD_VCO`), overlapping its Metal1 pad by a real `METAL1_PAD_MARGIN_UM` of area | Item 1's missing strap, in the one place that also serves as the inter-stage rail. Real overlap rather than a coincident edge: a butt joint is one grid snap away from being no joint |
| 3 | A plain Metal1 strap down the well's right-hand edge ties the two n-well tap bands together | Without it the *bottom* tap band is its own `VDD_VCO` island — legal only because nothing may touch it. Metal1, not a third `tap_strip()`: a comp band there lands on the last stage's own gate-poly endcap (`pmos_x1 + POLY_ENDCAP_UM` reaches into that column) — `DF.2a_LV` ×2, `CO.7`, `NP.12`, all four reported by the deck on the first attempt at it |
| 4 | Drain and gate bridges cross the channel on **Metal2** (`via1_stack()` inside each Metal1 pad it joins, then `m2_route()`) | Item 3. Metal2 has no spacing relationship with Metal1, the same escape `block.py`'s own routing already relies on. Each via1's 0.44 µm landing pad sits strictly inside its 0.46 µm terminal pad, so this adds **no new Metal1 geometry at all** |
| 5 | Stage outputs are labelled with the schematic's own net names (`NB1`, `NB2`), and the last stage's output is labelled only once, as `CLK` | The `BUF<i>.` prefix invented names no reference netlist has (unlike `ring.py`'s per-stage `S<i>.Y`, these are top-level `vco.sch` nets), and `BUF3.CLK` + `CLK` put two different strings on one net — the one thing an LVS deck reads labels *for* |

Plus a draw-time guard: `build()` computes the worst-case Euclidean Metal1 gap
between either rail band and every stage's gate pads and **refuses to draw**
below `devices.DRC_METAL1_MIN_SPACE_UM` (M1.2a, 0.23 µm). Measured:
**0.340 µm**. A guard, not a comment, because this failure mode is invisible
to every check that was in place: DRC merges two touching same-layer shapes
into one polygon *before* any spacing rule runs, so a short is never a
violation, and `block.connectivity_report()` only ever asks whether same-net
conductors reach each other, never whether different-net ones stay apart.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| Reproduction script, post-fix | `PROOF-368-rootcause.md`'s script vs. `vco_out_buffer.gds` | no polygon with >1 net label | `multi-label polys: 0` | **PASS** |
| …and no floating islands | same script, polygons *per net* | 1 each | `CLK/GND_VCO/NB1/NB2/VDD_VCO/Y5: 1 poly each` | **PASS** |
| `vco_out_buffer` DRC, table `main` | `run_pv.py drc … --top vco_out_buffer` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_out_buffer` **LVS** | `run_pv.py lvs … --top vco_out_buffer --lvs-sub GND_VCO` | match | `Congratulations! Netlists match.` | **PASS** |
| `vco_block` DRC, table `main` | `run_pv.py drc … --top vco_block` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (18/18) | **PASS** |
| `vco_block` LVS | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `ERROR : Netlists don't match` | **still MISMATCH — `ring.py` (issue #371) not fixed yet** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 517 tests … OK` | **PASS** |

Artifacts committed beside this file: `vco_out_buffer.gds`, `vco_block.gds`,
`drc-clean/drc-buffer.stdout.log` + `vco_out_buffer_main.lyrdb`,
`drc-clean/drc-block.stdout.log` + `vco_block_main.lyrdb`,
`drc-clean/connectivity-block.log`, and the new `lvs-buffer/` directory
(`lvs.stdout.log`, `vco_out_buffer.cir`, `vco_out_buffer.lvsdb`,
`vco_out_buffer.spice`).

### Reproducing the standalone LVS

```bash
python3 -m layout.pll_top.vco.buffer --outdir <workdir>
python3 -c "from layout.pll_top.vco import buffer; \
  open('<workdir>/vco_out_buffer.spice','w').write(buffer.reference_netlist())"
python3 layout/run_pv.py lvs <workdir>/vco_out_buffer.gds \
  <workdir>/vco_out_buffer.spice --top vco_out_buffer \
  --lvs-sub GND_VCO --run-dir <rundir>
```

The reference is generated from `devices.BUFFER_STAGES`, not hand-written, so
it cannot drift from the device table the layout is drawn from; the extracted
side (`lvs-buffer/vco_out_buffer.cir`) is six transistors on six nets:

```
.SUBCKT vco_out_buffer CLK GND_VCO NB1 NB2 VDD_VCO Y5
M$1 VDD_VCO NB2 CLK     VDD_VCO pfet_03v3 L=0.28U W=11.25U
M$2 VDD_VCO NB1 NB2     VDD_VCO pfet_03v3 L=0.28U W=3.75U
M$3 VDD_VCO Y5  NB1     VDD_VCO pfet_03v3 L=0.28U W=1.25U
M$4 CLK     NB2 GND_VCO GND_VCO nfet_03v3 L=0.28U W=4.5U
M$5 NB2     NB1 GND_VCO GND_VCO nfet_03v3 L=0.28U W=1.5U
M$6 NB1     Y5  GND_VCO GND_VCO nfet_03v3 L=0.28U W=0.5U
```

(area/perimeter parameters elided for width here; the committed `.cir` has
them.)

## How far this moves the assembled block

`vco_block` LVS still mismatches, and is expected to until issue #371 fixes
`ring.py`'s own two shorts — this record does not claim otherwise. What it can
claim is a measured step, taken from the extracted netlist in each run's own
`.lvsdb` (`db.LayoutVsSchematic().netlist().circuit_by_name("vco_block")`):

| | devices | nets | largest shorted net |
|---|---|---|---|
| Reference (`block.reference_netlist()`) | 65 | 43 | — |
| Before (`PROOF-lvs.md`, `main`) | 39 | 20 | 19 aliases, 43 terminals |
| After (this fix, `ring.py` untouched) | **44** | **23** | 15 aliases, 47 terminals |

Every alias the buffer contributed is gone from the shorted net. It now reads

```
GND_VCO,S1.Y,S2.Y,S3.Y,S4.Y,S5.Y,VBN,VBP0,VDD_VCO,Y1,Y2,Y3,Y4,Y5,Y5_CLK_IN
```

— entirely `ring.py`'s chain nets plus the supplies they drag in, with
`BUF1.NB1`, `BUF2.NB2`, `BUF3.CLK` and `CLK` no longer among them. The
buffer's own nodes extract as ordinary nets with the right terminal counts
(`NB1` 4, `NB2` 4, `CLK` 2), its NMOS sources land on the real 42-terminal
`GND_VCO`, and its PMOS sources land on the `VDD_VCO`-aliased cluster — which
*is* physically `VDD_VCO`, contaminated by the ring, and resolves when #371
does.

**`lvs-attempt/` is deliberately not renamed to `lvs-clean/`.** That rename is
gated on the *combined* fix producing a matching `vco_block` run, which is not
in this issue's control.

## What this leaves for issue #371

`ring.py` needs the same three items, plus the one that is only its: the
Y5→A1 wraparound riser crosses the `GND_VCO` rail on Metal1 by necessity (see
`PROOF-368-rootcause.md` §2's third bullet) and needs the Metal2 hop item 4
above establishes the pattern for. `ring.py` is untouched here.

Worth doing after both land, and not attempted here: `block.py`'s
`CONNECTED_PROBES` still cannot see any of this (item 4 of
`PROOF-368-rootcause.md`'s recommended fix shape). The unit tests added with
this fix —
`OutputBufferMetal1NetSeparationTests` /
`OutputBufferSupplyRailTests` in `layout/tests/test_vco_layout.py`, which run
the reproduction script above as an assertion and include a negative control
that the clearance guard really refuses a short — cover `buffer.py` only.
