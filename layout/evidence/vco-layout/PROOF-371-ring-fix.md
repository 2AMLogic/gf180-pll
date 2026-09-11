# `ring.py`'s half of the issue-#368 short — fixed, and LVS-clean on its own

Fix record for [issue #371](https://github.com/2AMLogic/gf180-pll/issues/371),
the second of the two follow-ups [`PROOF-368-rootcause.md`](PROOF-368-rootcause.md)
decomposed issue #368 into (the first, `buffer.py`, is
[`PROOF-372-buffer-fix.md`](PROOF-372-buffer-fix.md), issue #372, already
merged). Same discipline as that record: every claim below is a command run
against the artifacts committed beside this file.

`vco_ring` now has a **standalone LVS reference netlist of its own** and
**matches it**:

```
INFO : Congratulations! Netlists match.
```

## Provenance

| | |
|---|---|
| Fixed / measured | 2026-09-11 |
| Branch point | `origin/main` @ `52987e5` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.30.9` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |

Same disclosed KLayout-version deviation `PROOF-lvs.md`/`PROOF-368-rootcause.md`/
`PROOF-372-buffer-fix.md` all carry: this repo's earliest committed DRC/LVS
evidence was captured on `KLayout 0.28.16`, and releases newer than that have
been observed to report a *false LVS mismatch* on an unchanged, LVS-clean
layout. That failure mode can only make a result here **worse**, never
better — the result below is a **match**.

## What was wrong (four things — the issue names three, root-causing this
one turned up a fourth, the same way `buffer.py`'s own fix found a third
beyond the two `PROOF-368-rootcause.md` named for it)

1. **`VDD_VCO`/`GND_VCO` full-row Metal1 rails structurally overlapped their
   own device's bias-gate pad** (`primitives.mosfet()`'s gate/terminal-pad
   overlap, `0.26 - l/2` µm — 0.01 µm at `l=0.5`, harmless per device,
   fatal once stretched across the row).
2. **No deliberate device-to-ring strap** — the internal rail, the inner
   n-well tap ring and the outer p guard ring were three separately-labelled
   Metal1 islands never joined by any drawn metal.
3. **The Y5→A1 wraparound route's own vertical risers cross other nets'
   Metal1** on the way down to `wrap_y` — not just `GND_VCO`'s rail (the
   issue's own text), but `MNT`'s own `NT` (drain) pad under the Y5 riser's
   column and `VBN`'s own natural gate pad under the A1 riser's column too.
4. **(New) `VBP`/`VBN` cannot be a full-row Metal1 rail at all.** Unlike
   `VDD_VCO`/`GND_VCO` (open channel on their *outer* side to relocate
   into), each bias-gate pad sits *between* two different terminal pads of
   its own device (`MNT`: `GND_VCO` below, `NT` above; `MPH`: `NH` below,
   `VDD_VCO` above) and overlaps *both* by the same structural ~0.01 µm.
   The clear room between those two neighbours (~0.6 µm) is narrower than
   one legal-width Metal1 rail plus M1.2a clearance on *both* sides
   (>= 0.23 + 0.23 + 0.23 µm) — there is no y-range a clipped rail could
   occupy at all, "moved wholesale" (`buffer.py`'s own conclusion) isn't
   available either.
   Found (not assumed) by running the reproduction script against this fix
   with items 1-3 alone: it still showed `VBN` merged with `MNT`'s own `NT`
   pad across the whole row, and separately `VBP` merged with `MPH`'s own
   `NH` pad.
5. **(New, found by running the reproduction script against items 1-4's own
   fix) The inner n-well tap ring's bottom band is disconnected from its
   top band.** `ring.py` draws the tap ring as top+bottom Metal1/comp bands
   only (no left/right band — the n-well has no free interior room for
   one). With items 1-4 fixed, nothing else on Metal1 legally touches the
   bottom band any more (it used to "connect" only via the accidental
   short in item 3), so it was a second, genuinely disconnected `VDD_VCO`
   Metal1 island. `buffer.py`'s own fix hit the identical thing and used
   the identical fix (a plain Metal1 strap down one edge of the well,
   *not* a third `tap_strip()` — a comp band there lands on the last
   stage's own gate-poly endcap).

## Reproduction of the "before" state

`PROOF-368-rootcause.md`'s own script, against `ring.py` on `origin/main`:

```
poly bbox (-2.12,-1.34)-(67.32,8.34) um: {'GND_VCO','S1.Y'..'S5.Y','VBN','VDD_VCO','Y1'..'Y5','Y5_CLK_IN'}
poly bbox (-2.12, 8.22)-(66.00,10.78) um: {'VBP','VDD_VCO'}
multi-label polys: 2
```

Both wraparound risers cross the row's own bias/supply Metal1 at once (item
3), dragging almost everything — every chain net, both supplies, `VBN` — into
one polygon; `VBP` merges with `VDD_VCO` separately (items 1/2).

## The fix

All of it is in `layout/pll_top/vco/ring.py` and `layout/pll_top/vco/stage.py`
(the NMOS/PMOS channel hop, item 3's `NT`/`VBN` half — `stage.py` is only
ever called by `ring.py`, so this is still this issue's own scope, the same
way `buffer.py`'s fix touched only itself). `primitives.py` is unchanged.

| # | Change | Why this shape |
|---|---|---|
| 1 | `VDD_VCO`/`GND_VCO` rails relocate into the clear channel beyond `VBP`/`VBN`'s own *natural* pad (not merely clipped in place) | Same "moved wholesale" conclusion `buffer.py`'s fix reached — a plain clip left under M1.1's 0.23 µm minimum |
| 2 | Each rail runs into the ring biasing the same net, a real `METAL1_PAD_MARGIN_UM` overlap | The missing strap — real area, not a coincident edge one grid-snap from being no joint |
| 3 | Y5→A1 wraparound risers hop their *entire* descent to `wrap_y` on Metal2 (`_route_wraparound_hop()`), not just a computed obstruction window | A first version of this fix computed one explicit band and missed `MNT`'s own `NT` pad — hopping unconditionally needs no obstruction inventory at all |
| 4 | `VBP`/`VBN` each get a dedicated Metal2 trunk (`_bias_trunk()`) tying every stage's own *untouched* natural gate pad together, instead of any Metal1 rail | The squeeze in item 4 above has no Metal1 solution; Metal2 has no spacing relationship with Metal1 at all |
| 5 | A Metal1 strap down the n-well's right-hand edge ties the tap ring's top and bottom bands together | Same fix `buffer.py` used for the identical defect |

Two routing details worth naming: the A1 riser jogs sideways to a clear
column immediately after leaving its own pad (its natural landing column is
`VBN`'s own stage-1 gate-tab column too — same x, different y bands, and
Metal2 does not get to ignore *other Metal2*). And in the assembled
`vco_block`, `block.py`'s own `VBP` route (mirror → ring) had to move too:
`VBP`'s trunk sits *above* the inner tap ring, `VBN`'s sits *below* `wrap_y`
(opposite ends of the ring block), so a straight vertical entry for `VBP`
from the mirror-ring gap below would cross `VBN`'s own trunk on the way up.
It now takes the clear channel outside the ring's own left edge instead —
the same "channel outside the block's own width" escape `block.py`'s own
`VBP0` riser already uses for an analogous crossing.

## Results

| Check | Command | Expected | Got | Verdict |
|---|---|---|---|---|
| Reproduction script, post-fix | `PROOF-368-rootcause.md`'s script vs. `vco_ring.gds` | no polygon with >1 net label | `multi-label polys: 0` | **PASS** |
| `vco_ring` DRC, table `main` | `run_pv.py drc … --top vco_ring` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_ring` **LVS** | `run_pv.py lvs … --top vco_ring --lvs-sub GND_VCO` | match | `Congratulations! Netlists match.` | **PASS** |
| `vco_block` DRC, table `main` | `run_pv.py drc … --top vco_block` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `vco_block` `connectivity_report()` | `python3 -m layout.pll_top.vco.block --check-connectivity` | PASS | `connectivity: PASS` (18/18, incl. `VBP != VBN`) | **PASS** |
| `vco_block` LVS | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `ERROR : Netlists don't match` | **mismatch — pre-existing, separate short, see below** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 527 tests … OK` | **PASS** |

Artifacts committed beside this file: `vco_ring.gds`, `vco_block.gds`,
`drc-clean/drc.stdout.log` + `vco_ring_main.lyrdb`,
`drc-clean/drc-block.stdout.log` + `vco_block_main.lyrdb`,
`drc-clean/connectivity-block.log`, the new `lvs-ring/` directory
(`lvs.stdout.log`, `vco_ring.cir`, `vco_ring.lvsdb`, `vco_ring.spice`), and a
refreshed `lvs-attempt/` (the *current* — different-cause — `vco_block`
mismatch; see below).

### Reproducing the standalone LVS

```bash
python3 -m layout.pll_top.vco.ring --outdir <workdir>
python3 -c "from layout.pll_top.vco import ring; \
  open('<workdir>/vco_ring.spice','w').write(ring.reference_netlist())"
python3 layout/run_pv.py lvs <workdir>/vco_ring.gds \
  <workdir>/vco_ring.spice --top vco_ring \
  --lvs-sub GND_VCO --run-dir <rundir>
```

Generated from `devices.STAGE_FETS`, not hand-written — 20 transistors (4
per stage x 5 stages) on 9 nets (`lvs-ring/vco_ring.cir`, node names abridged
here; the committed `.cir` has the full alias lists and area/perimeter
parameters):

```
.SUBCKT vco_ring GND_VCO Y1 Y2 Y3 Y4 Y5 VBN VBP VDD_VCO
M$1..M$5   MPH x5: VDD_VCO/VBP/NH_i/VDD_VCO, pfet_03v3 L=0.5U  W=10U
M$6..M$10  MP  x5: NH_i/Y_(i-1)/Y_i/VDD_VCO,  pfet_03v3 L=0.28U W=5U
M$11..M$14,M$17  MN x5: Y_i/Y_(i-1)/NT_i/GND_VCO, nfet_03v3 L=0.28U W=2U
M$15,M$16,M$18..M$20  MNT x5: NT_i/VBN/GND_VCO/GND_VCO, nfet_03v3 L=0.5U W=4U
.ENDS vco_ring
```

## How far this moves the assembled block

`vco_block` LVS still mismatches — but for a *different* reason than before,
one entirely outside `ring.py`'s own scope. Measured from the extracted
netlist in each run's own `.lvsdb`:

| | devices | nets | largest shorted net |
|---|---|---|---|
| Reference (`block.reference_netlist()`) | 65 | 43 | — |
| Before (`PROOF-372-buffer-fix.md`, `ring.py` untouched) | 44 | 23 | 15 aliases, 47 terminals |
| After (this fix) | **60** | **39** | 2 aliases, 45 terminals |

`VDD_VCO` (18 terminals), `GND_VCO` (55), `VBP` (8) and `VBN` (10) each now
extract as their own ordinary net — none of `ring.py`'s own nets are shorted
to anything any more. The one remaining shorted net is:

```
VBP0,VDD_VCO
```

**This is a pre-existing defect, not something this fix introduces or leaves
behind in `ring.py`.** Rebuilding `vco_block` from `origin/main` @ `52987e5`
(`buffer.py`'s own fix landed, `ring.py` untouched) and running the identical
`.lvsdb` inspection shows the *exact same* `VBP0,VDD_VCO` merge already
present there, inside the pre-existing 47-terminal mega-short (`grep` for
`VBP0` in that run's own net list finds it in the same cluster as
`GND_VCO`/the ring's own chain nets) — this fix's own contribution was never
touching it, it was simply invisible as a *separate* short until the larger
one it was riding along with got fixed. `VBP0` is entirely a `vtoi_core.py` /
`mirror.py` / `block.py` net (the V-to-I core's summing node, routed to the
band-select mirror's cascade A) with no `ring.py` involvement at all — its
own Metal2 polygon (`block.py`'s own `VBP0` routing) has the identical
bounding box in both runs (`(-12.64,16.38)-(114.66,76.34)` µm), well outside
`ring.py`'s own footprint (`ring` sits at world y >= 127.22 in the assembled
block). Filed as [issue #376](https://github.com/2AMLogic/gf180-pll/issues/376)
rather than pulled into this one (see that issue for the specific
mechanism, once root-caused).

**`lvs-attempt/` is deliberately not renamed to `lvs-clean/`.** Both
sub-block fixes (#372, #371) are now in and both match their own standalone
LVS — but the *combined* `vco_block` run still mismatches on the
newly-separately-scoped `VBP0`/`VDD_VCO` defect above, which is not in this
issue's control.
