# `vco_block`'s `VDD_VCO` was two things at once: one real floating supply island, and one thing `klt erc` cannot see

Investigation + fix record for
[issue #433](https://github.com/2AMLogic/gf180-pll/issues/433) — the
`klt erc` finding [`PROOF-erc.md`](PROOF-erc.md) disclosed and handed on:
`VDD_VCO` resolved to **3 disconnected electrical islands** under the
committed supply spec, while this same block's committed LVS run reported a
clean **65/65 devices, 43/43 nets `Match`**.

Same discipline as every other record in this directory: every claim below is
a command run against the artifacts committed beside this file, not inferred
from a tool's pass/fail line.

## The short version

The two tools were not contradicting each other. **The `klt erc` finding was
right about one island and wrong about the other, and the LVS `Match` was
evidence of neither** — because the PDK's own LVS deck ends with
`connect_implicit('*')`, which joins **same-named** nets whether or not any
conductor joins them.

| `klt erc` island | What it actually is | Verdict |
|---|---|---|
| 1 (main) | The supply trunk, the block n-well ring, and every tap band the trunk feeds | — |
| 2 | `vtoi_core.py`'s **bottom** n-well tap band, in the *same* merged n-well polygon as the top band the trunk feeds | **False positive.** Ohmically one node through the well; outside `klt erc`'s declared-conductor model (klayout-tools#2180) |
| 3 | `mirror.py`'s **bank 0** tap band — its own n-well, its `ntap`, and every pfet source `mirror.py` rail-stubs onto that band | **Real defect.** Joined to `VDD_VCO` by no conductor at all. Fixed here |

`block.py` fed **one Metal2 hop per sub-block** (each sub-block's topmost tap
band). That silently assumed one n-well per sub-block. `mirror.py` gives
**every bank its own n-well**, and says so in its own module docstring: *"only
block.py's own supply trunk joins the banks' tap bands into one net."* Nothing
joined them. The fix is one line of selection logic — feed one band per
**n-well**, not per sub-block — which adds exactly one Metal2 hop and two
Via1s to the layout.

## Provenance

| | |
|---|---|
| Investigated / fixed | 2026-09-20 |
| Branch point | `origin/main` @ `6b40844` (PR #434 / issue #427 merged) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, DRC/LVS deck runner) | `KLayout 0.30.10` |
| KLayout (pip wheel, geometry + `.lvsdb` introspection) | `0.30.10` |
| `klt` | `0.5.0+gf2f1d14e4cb9`, built from a `pip install` of `klayout-tools` `main` @ `f2f1d14e` into a clean venv (KLayout wheel `0.30.12` inside it) |

**Disclosed KLayout-version deviation.** `layout/README.md`'s "The two
KLayouts" section warns that KLayout releases newer than `0.28.16` — the
version this directory's earlier LVS evidence was captured on — have been
observed to report a *false* LVS mismatch on an LVS-clean, unchanged layout.
The runs below were made on `0.30.10` and report a **match**, so that failure
mode did not fire here; it is recorded because the version differs from
[`PROOF-381-high-rs-resistor.md`](PROOF-381-high-rs-resistor.md)'s, not
because it affected a result.

**Disclosed `klt` deviation, second occurrence.** `PROOF-erc.md` already
recorded that the `uv tool install`ed `klt` in this environment reports
`klt 0.5.0` but emits an ERC report with **no `status` field and no
`provenance` block**, contradicting its own published `docs/cli/erc.md`. That
is still true as of this record — and the previously built-from-source `klt`
that *did* emit them was no longer on `PATH` by the time this investigation
ran, so a from-source build was made again (`f2f1d14e`, the tip of
`klayout-tools` `main` at the time). Two further schema drifts between
`d5893304` (the build `PROOF-erc.md` used) and `f2f1d14e` are visible in the
regenerated `erc-report.json` and are called out plainly rather than smoothed
over: `provenance.input` no longer carries `"role": "layout"`, and
`provenance.klt_version` is now the bare `"0.5.0"` rather than the
`+g<sha>`-suffixed build string. Neither affects a claim here — the input and
spec `content_hash` fields this record relies on are unchanged in shape.

## Step 1 — reproduce the finding

```
$ klt erc --top vco_block --format json \
    layout/evidence/vco-layout/vco_block.gds \
    layout/evidence/vco-layout/erc-supply-spec.json
```

Against the pre-fix GDS (`sha256:b1798bf8…3b8ca5b18b`, the hash
`PROOF-erc.md` pins):

```json
{"rule": "erc.unconnected_net",
 "description": "declared net 'VDD_VCO' resolves to 3 disconnected electrical islands (expected exactly one)",
 "net": "VDD_VCO"}
```

Reproduced verbatim. `GND_VCO` clean.

## Step 2 — locate the islands (`klt erc` does not tell you where they are)

`klt erc`'s finding carries `"bbox": null` and no per-island geometry, so the
islands were re-derived by rebuilding its documented connectivity model
directly (`klayout.db.LayoutToNetlist`: `poly2`/`metal1`/`metal2` as
conductors, `contact` and `via1` as the vias between them, `34/10` as the
Metal1 label layer — exactly what `erc-supply-spec.json` declares, and exactly
what `klayout_tools/erc.py` wires up):

| Island | Metal1 | Contact | Metal2 | Via1 | Metal1 bbox (µm) |
|---|---|---|---|---|---|
| 1 | 64 | 2590 | 18 | 12 | `(-19.56, -10.64)` – `(152.20, 173.08)` |
| 2 | 1 | 211 | 0 | 0 | `(-0.12, 18.48)` – `(105.64, 19.32)` |
| 3 | 22 | 329 | 3 | 2 | `(-0.12, 84.28)` – `(91.92, 90.44)` |

Cross-referenced against the generators' own plans (`dx_vtoi = dy_vtoi = 0`,
`dy_mirror = 58.72`), the two stray islands are **named structures**, not
stray metal:

```
$ python3 -c "... from layout.pll_top.vco import block, vtoi_core, mirror ..."
merged n-well polygons: 6

vtoi_core:
   tap_band (top)   (0.0, 43.4, 105.52, 44.0)   -> n-well #0 (-0.5,18.1;106.02,44.5)
   tap_band_bottom  (0.0, 18.6, 105.52, 19.2)   -> n-well #0 (-0.5,18.1;106.02,44.5)

mirror banks (block coords):
   bank 0 tap_band  (0.0, 89.72, 91.8, 90.32)   -> n-well #1 (-0.5,80.22;92.3,90.82)
   bank 1 tap_band  (0.0, 117.62, 51.42, 118.22)-> n-well #2 (-0.5,103.72;51.92,118.72)
```

— island 2 is `vtoi_core.plan().tap_band_bottom`; island 3 is
`mirror.plan().banks[0].tap_band` and everything rail-stubbed onto it.

## Step 3 — the LVS `Match` was never evidence that these were connected

This is the part that made the two results *look* contradictory. The PDK's own
LVS deck ends its connectivity setup with (`$PDK_ROOT/gf180mcuD/libs.tech/
klayout/lvs/rule_decks/general_connections.lvs:100`):

```ruby
# Multifinger Devices
connect_implicit('*')
```

`connect_implicit` joins nets **by name**. Two `VDD_VCO` islands that touch
nothing at all are therefore one net in the extracted netlist, compare as one
net against the reference, and produce `Congratulations! Netlists match.`

Demonstrated directly against the **pre-fix** `.lvsdb` committed with
`PROOF-erc.md` (`sha256:a94c9a8b…10b4c26`) — take the single extracted
`VDD_VCO` net's own shapes on *every* layer the deck extracted (metal, vias,
contacts, `ntap`, `psd`, **and the n-well**) and count merged geometric
islands:

```python
lvs = db.LayoutVsSchematic(); lvs.read(".../lvs-clean/vco_block.lvsdb")
net = [n for n in lvs.netlist().circuit_by_name("vco_block").each_net()
       if n.name == "VDD_VCO"][0]
u = db.Region()
for ln in lvs.layer_names():
    sh = lvs.shapes_of_net(net, lvs.layer_by_name(ln), True)
    if sh: [u.insert(db.Polygon(p)) for p in sh.each()]
print(u.merged().count())
```

```
VDD_VCO: union of ALL extracted-net shapes -> 2 geometric islands
   island bbox (-0.5,80.22;92.3,90.82)     area=983.68um2     <- mirror bank 0's n-well
   island bbox (-19.94,-11.02;152.58,173.46) area=5603.71um2  <- everything else
```

**Two conclusions at once, and they point opposite ways:**

1. `klt erc`'s island 2 (`vtoi_core`'s bottom band) has *already vanished*
   here — it is inside the 5603 µm² island, because the deck counts the n-well
   as the conductor it is (`connect(nwell_con, ntap)`, `general_connections
   .lvs:28`) and both `vtoi_core` bands tap the same merged well polygon #0.
   **Island 2 is a false positive of a metal-only model.**
2. `klt erc`'s island 3 survives even that. No conductor in the PDK's own
   device-aware extraction — metal, contact, diffusion, well, or the global
   substrate — reaches `mirror.py`'s bank 0. **Island 3 is a real open,** and
   the `Match` verdict came from the name-join, not from the geometry.

**Control that this metric is not simply "count the islands and panic":**
`GND_VCO`, on the same pre-fix database, reports **11** geometric islands —
ten of them tiny, single-layer `ptap` patches with no metal on them at all,
joined to the ninth by `connect_global(sub, substrate_name)`
(`general_connections.lvs:95`). That is a genuinely global node, not a
name-join, which is also why `klt erc` (which never sees them, since they
carry no conductor it declares) correctly reports `GND_VCO` as one island.

## Step 4 — root cause of the real defect

`block.py` step 6 drew one Metal2 hop from the Metal1 supply trunk per
sub-block, onto that sub-block's **topmost** `VDD_VCO` tap band:

```python
def vdd_feed(pins: dict) -> float:
    band = max(pins[VDD_NET], key=lambda b: b[3])   # <-- topmost only
    ...
```

Both generators that draw more than one band have a reason to:

* `vtoi_core.plan()` draws `tap_band` **and** `tap_band_bottom` around one
  PMOS row because `MSU1`'s `L = 20 µm` channel makes a top-only band exceed
  `DF.13_MV`/`DF.14_MV`'s 15 µm pfet-to-tap bound. Both tap the **same** well,
  and `vtoi_core.py`'s own `build()` says so explicitly: *"Both bands make
  ohmic contact to the same continuous n-well body, so they are the same
  electrical net without any extra Metal1 jumper between them."* Verified
  above (both in merged n-well polygon #0) — **correct as designed.**
* `mirror.py` draws one band per **bank**, and each bank has its own n-well,
  separated by that bank's NMOS row and a `GND_VCO` substrate tap strip. The
  wells are physically disjoint (polygons #1 and #2 above), so the bands are
  not each other's node by any mechanism. `mirror.py`'s own
  `connectivity_report()` comment states the contract it relies on: *"only
  `block.py`'s own supply trunk joins the banks' tap bands into one net."*
  `block.py` did not.

**What was actually floating.** `mirror.plan().banks[0]` carries 9 PMOS items,
six of them plain fets whose `top_net` is `VDD_VCO` (`MIP0`, `MSWA1`, `MIP1`,
`MDB`, `MIP2`, `MSWC1`) plus the common-centroid array `A`, whose pfet row
rail-stubs to the same band (`mirror.py:1139-1145`). Measured on the pre-fix
GDS, island 3 carried **10 `psd` (pfet source/drain) regions, 1 `ntap`, 22
Metal1 shapes and 329 contacts**. The band-select mirror's lower bank had no
supply.

### Why every earlier check missed it

* **DRC** cannot see a missing connection; there is no rule for "these two
  shapes should have been joined."
* **LVS** — `connect_implicit('*')`, step 3 above. This is the important one:
  it means *a clean LVS net-level match is not evidence that two same-named
  metal islands are physically connected*, in this deck, ever.
* **`block.connectivity_report()`** probed the VDD bands with the *same*
  topmost-only expression the router fed them with
  (`_probe_points()`: `band = max(sp[key][VDD_NET], key=lambda b: b[3])`), so
  the unfed band was never probed. Invisible by construction — the identical
  shape of blind spot [`PROOF-368-rootcause.md`](PROOF-368-rootcause.md)
  documented for `CONNECTED_PROBES` before it.
* **`mirror.connectivity_report()`** runs pre-assembly, where the banks'
  rails are *expected* to be separate islands (its own docstring says so), so
  it cannot be the check either.

## Step 5 — the fix

One selection rule, shared by the router and the probe list so they cannot
drift apart again (`layout/pll_top/vco/block.py`):

```python
def vdd_feed_bands(key: str, pins: dict, p: Placement) -> list[tuple]:
    """One band per n-well, not one per sub-block (issue #433)."""
    bands = pins[VDD_NET]
    wells = _vdd_wells(key, p)          # mirror -> one box per bank; else None
    if wells is None:
        return [max(bands, key=lambda b: b[3])]
    ...                                  # topmost band inside each well
```

`build()`'s step 6 and `_probe_points()` both call it. A sub-block n-well with
no `VDD_VCO` tap band inside it now raises `ValueError` rather than being
skipped silently.

**The drawn delta is exactly one supply hop.** Merged-region XOR of the
pre-fix against the post-fix GDS, every drawn layer:

```
layer      added (um2)   removed (um2)   added bboxes
35/0           0.1352          0.0000    (91.17,89.89;91.43,90.15), (137.93,89.89;138.19,90.15)
36/0          20.7680          0.0000    (91.08,89.8;138.28,90.24)
```

— two Via1 squares and one Metal2 wire from bank 0's tap band to the trunk at
`y = 90.02 µm`. **Nothing was removed and no other layer changed at all**,
including Metal1: both `via1_stack()` landings fall wholly inside metal that
was already there (the tap band on the left, the trunk on the right), which is
also why they are enclosed by construction rather than by luck. The corridor
was checked for Metal2 obstructions before routing (zero Metal2 shapes within
`M2.2a`'s 0.28 µm of the route between `x = 91.3` and the trunk at
`x = 138.06`), and `block._Router._reserve()`'s own M2.2a check — which raises
a Python exception naming both nets rather than emitting DRC markers — passed.

## Results

All against the artifacts committed beside this file.

| Check | Command | Expected | Observed | Verdict |
|---|---|---|---|---|
| `klt erc`, `VDD_VCO` | `klt erc --top vco_block --format json vco_block.gds erc-supply-spec.json` | fewer islands | **3 → 2 islands** (island 3 gone; island 2 remains — see below) | **improved, not yet clean** |
| `klt erc`, `GND_VCO` | same run | clean | no finding | **PASS** |
| `VDD_VCO`, PDK deck's own extraction | union of every extracted-net shape, merged | one island | **2 → 1 geometric island** | **PASS** |
| `vco_block` DRC | `run_pv.py drc … --top vco_block` | clean | `DRC clean: vco_block (D), 0 violations` | **PASS** |
| `vco_block` LVS, deck verdict | `run_pv.py lvs … --top vco_block --lvs-sub GND_VCO` | match | `Congratulations! Netlists match.` (`POLY_RES Selected is 3k`) | **PASS** |
| `vco_block` LVS, device-level | `lvs.xref().each_device_pair()` | every device `Match` | 65/65 `Match`, 0 warnings, 0 mismatches | **PASS** (no regression) |
| `vco_block` LVS, net-level | `lvs.xref().each_net_pair()` | every net `Match` | 43/43 `Match`, 0 mismatches | **PASS** (no regression) |
| `connectivity_report()` | `python3 -m vco.block --check-connectivity` | 18/18 `PASS` | 18/18 `PASS`; `VDD_VCO` now **7** probe points, was 6 | **PASS** |
| `layout/tests` | `python3 -m unittest discover -s layout/tests -t layout/tests` | pass | `Ran 612 tests … OK` | **PASS** |

Artifact hashes (post-fix, committed beside this file):

```
8c839b913756d6c31986b9d447bb8317b572a68f1dc13ccf79fffa1b4b5c47f9  vco_block.gds
890016efff277faebde42c2c085346cad26b0abefdb75c5550ef01fc22e8cc85  erc-supply-spec.json   (unchanged)
d6433905ae4cfe3fcc305d020b1ce98b6a60fda662fbdde52e9c0e7cfd1a3f83  erc-report.json
fdc87ebcad198453c6134a931162f79605be7dc9ebc54a94355baa2c1893902d  lvs-clean/vco_block.lvsdb
```

`erc-report.json`'s `provenance.input.content_hash` is
`sha256:8c839b91…4b5c47f9` — identical to the committed GDS, so the committed
report was run against exactly the committed layout.
`lvs-clean/vco_block.spice` is **byte-identical** to before: the reference
netlist did not change, because nothing about the *circuit* changed — only a
missing physical connection was drawn.

## The regression gates added

`layout/tests/test_vco_layout.py`:

* `VddFeedBandSelectionTests` — `vdd_feed_bands()` returns one band per bank
  for `mirror`, one for each single-well sub-block, and raises rather than
  silently skipping a well with no band in it.
* `AssembledBlockVddIslandTests` — two `klayout.db` extractions of the
  assembled block:
  * *metal-only*: every band the trunk feeds lands on the trunk's own cluster
    (a hop that did not land is caught);
  * *well-aware* (`ntap = ((comp − poly2) ∧ nplus) ∧ nwell`, `connect(nwell,
    ntap)` — the PDK deck's own derivation): **every** `VDD_VCO` tap band,
    including `vtoi_core`'s deliberately well-tied bottom band, is one node
    (a band nothing reaches is caught).

**Negative control, run before committing:** with `block._vdd_wells()`
monkey-patched back to the pre-fix behaviour (return `None` for every
sub-block, i.e. topmost band only), three of the five new tests fail, the
decisive one being

```
FAIL: test_every_tap_band_including_the_well_tied_ones_is_one_node
      (sub_block='mirror', band=(0.0, 89.72, 91.8, 90.32))
AssertionError: 24 != 12 : mirror's tap band (0.0, 89.72, 91.8, 90.32) is not
on VDD_VCO even counting the n-well's own ohmic continuity
```

The metal-only test alone passes under the pre-fix rule, and that is stated
here rather than hidden: it iterates the *fed* list, so it proves each hop
landed, not that the coverage was complete. The well-aware test is the one
that holds coverage, because it iterates every band the generators drew.

## What is deliberately NOT fixed, and why

`klt erc` still reports `VDD_VCO` as **2 islands**, the remaining one being
`vtoi_core.plan().tap_band_bottom`. **No geometry was changed to make that go
away.**

It is not a defect. Both `vtoi_core` bands make ohmic contact to the same
continuous n-well body (merged n-well polygon #0, verified in step 2), which
is a real conductor and is exactly how the PDK's own LVS deck models it
(`connect(nwell_con, ntap)`). The band's job is to tie that well; the well is
tied. The design intent is stated in `vtoi_core.py`'s own `build()` and is
correct as written.

`klt erc` cannot represent this, by design: its connectivity model traces only
the conductors a spec's `stackup` declares, and declaring the well as one is
not available here — the well-aware spec mechanism (`ties[]`) is itself
documented broken for real routed designs (klayout-tools#2169), and adding
`nwell`/`comp` to the `stackup` would need `comp` as a conductor with no
device recognition to break the channel, which would short every source to
every drain and produce a blizzard of false `erc.supply_short`s. This is the
gap [klayout-tools#2180](https://github.com/2AMLogic/klayout-tools/issues/2180)
already describes generically. Tuning `erc-supply-spec.json` until the finding
disappears is the one thing issue #427 explicitly asked nobody to do, and the
spec is byte-unchanged here.

**Net effect on T1 checklist item 11 (power delivery, structural): still not
met for `vco_block`, and now for exactly one known reason instead of an
unexplained one.** The pass condition is "every declared supply resolves to
exactly one electrical island"; `GND_VCO` does, `VDD_VCO` resolves to two
under a metal-only model and to **one** under any model that counts the
n-well. Item 11 should be re-evaluated when klayout-tools#2180 (or #2169)
lands a way to state well/diffusion continuity in a supply spec.

## Reproducing

```bash
# rebuild the block and the reference netlist
PYTHONPATH=layout/pll_top python3 -m vco.block --outdir <workdir> --check-connectivity
python3 -c "
import sys; sys.path.insert(0,'.')
from layout.pll_top.vco import block
open('<workdir>/vco_block.spice','w').write(block.reference_netlist())
"

python3 layout/run_pv.py drc <workdir>/vco_block.gds --top vco_block --run-dir <rundir>
python3 layout/run_pv.py lvs <workdir>/vco_block.gds <workdir>/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>

klt erc --top vco_block --format json \
  <workdir>/vco_block.gds layout/evidence/vco-layout/erc-supply-spec.json

python3 -m unittest discover -s layout/tests -t layout/tests
```

## Follow-up

* **[klayout-tools#2180](https://github.com/2AMLogic/klayout-tools/issues/2180)**
  — the connectivity-model gap that makes island 2 a false positive. This
  record supplies it a concrete, measured instance, and **corrects a claim in
  its own body**: that issue states the discrepancy is "not explained by
  simple continuous-n-well conduction either", on the strength of the same
  wrong well comparison [`PROOF-erc.md`](PROOF-erc.md) made. One of the two
  islands *was* explained by it. Correction posted upstream as a comment
  there, generically — it makes the "declare well/tap geometry as a scoped
  conductor" option a real fix rather than a guess, and it warns against the
  "cross-check with LVS" fallback that issue suggests, for the
  `connect_implicit('*')` reason in step 3 above.
* **[klayout-tools#2194](https://github.com/2AMLogic/klayout-tools/issues/2194)**
  (new, filed from this work) — `klt erc`'s `erc.unconnected_net` reports
  *how many* islands a net has and never *where they are* (`bbox` and `layer`
  are always `null`, one finding per net rather than per island). Step 2 of
  this record is the bespoke re-implementation of `klt erc`'s own
  connectivity model that gap forced.
