# `pfd_cp` structural power-delivery ERC (T1 checklist item 11, issue #565)

The first `klt erc` supply-spec run committed for this block. It targets the
T1/bronze design-evidence checklist's eleventh item, *"Power delivery
(structural)"* (klayout-tools#2025, bundled with klt 0.6.0 as
`docs/design-evidence-tiers.md`) — a purely structural question ("is the supply
net connected to what it powers"), not IR-drop or EM analysis.

**Result: both declared supplies resolve to exactly one labelled electrical
island with no `erc.unconnected_net` and no `erc.supply_short` — and item 11 is
nonetheless `unmet` for this block, because the well-tie half cannot be
expressed.** This block's one drawn tub layer carries **two deliberately
differently-biased n-well classes**: fourteen wells on `VDD`, and one on the
charge-pump dump buffer's own source node `PSRC`, a body-tie `design/cp_dumpbuf.sch`
documents in as many words. A single `ties[]` entry grades *every* shape of the
declared well layer against its own one net, so declaring the `VDD` class
reports a false `erc.missing_tie` on the `PSRC` well; the mechanism klt provides
for exactly this shape needs a marker layer to select on, and this stream draws
none.

So the spec declares a machine-readable **`ties_disclosure`** (`kind:
"tool_limitation"`) rather than either a false tie or a silent omission. That
renders item 11 `supply_spec_disclosed_tool_limitation` — still `unmet`, because
a disclosure is the caller's word and never a computed `erc.missing_tie` result,
but mechanically distinguishable from "nobody asked the question". The obstacle
is measured below, not asserted, and the gap is filed upstream.

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | The `klt erc` spec: gate+conductor stackup (Poly2 through Metal3, `active_layer` = Comp for true `poly ∩ diff` gate area), the vias bridging it, the two declared supply nets (`VDD`, `VSS`), and the `ties_disclosure`. Every entry carries an inline `_comment` justifying it. |
| [`erc-report.json`](erc-report.json) | The run below, against the exact `pfd_cp.gds` committed alongside it. |

## Provenance

| | |
|---|---|
| Run | 2026-09-26 (issue #565) |
| `klt` | `0.6.0+gf2d249ab23d4` — the released `klayout-tools==0.6.0` wheel, exactly what `.github/workflows/ci.yml` installs for the signoff tier check |
| KLayout (Python engine) | `0.30.12` |
| `--deck` | `gf180mcu`, `content_hash` `sha256:8da880a4b42bb27d4710b3647c2157c42b32de22da51b0259c82aa2c1c3441b4` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) — the layer numbers this spec was cross-checked against, and the deck behind the LVS cross-check below. `klt erc` itself needs no PDK install. |

```
$ klt erc --top pfd_cp --deck gf180mcu --format json \
    layout/evidence/pfd-cp-layout/pfd_cp.gds \
    layout/evidence/pfd-cp-layout/erc-supply-spec.json
$ cd layout/evidence/pfd-cp-layout && sha256sum pfd_cp.gds erc-supply-spec.json
212c27c4a209c2d851d0e424ee9c4c75c040b5824a77a8a2763a3d9f7b7030d9  pfd_cp.gds
f8f0572a6c7514f748df1c0a5959b73c64c51e54af4bb7a1c1e68344904979fd  erc-supply-spec.json
```

`erc-report.json`'s `provenance.input.content_hash` and
`provenance.spec.content_hash` are `sha256:` prefixed copies of exactly those
two digests — **and that pair is a build gate, not a promise**:
`layout/lib/check-layout-status-claims.sh` recomputes both on every CI run and
fails if either disagrees. The report's `file` field is the committed
repo-relative path, not a scratch path.

## The supply-continuity half: clean, with its own strength stated

```json
"erc_status": "clean",
"erc_finding_count": 0,
"erc_findings": [],
"nets": [
  { "name": "VDD", "matched_islands": 1, "expected_islands": 1, "roles": [], … },
  { "name": "VSS", "matched_islands": 1, "expected_islands": 1, "roles": [], … }
]
```

No `erc.unconnected_net`, no `erc.supply_short`, and no `erc.floating_gate`
across all 73 gate nets. (`status` is `"not_checked"`/exit 4 because the
envelope's `status` aggregates the antenna half, which cannot run without
`--pdk`; `erc_status` is the field item 11 grades, and it is `"clean"`.)

**That clean read is a weaker bound than it looks, and this block is the reason
the distinction matters.** `erc.unconnected_net` counts the islands *carrying
the declared label*, not the islands the conductor geometry forms
(klayout-tools#2497). Walking every text shape on `(34,10)` (`Metal1_Label`) of
the committed GDS finds **exactly one instance each of `VDD` and `VSS`**,
alongside eleven non-supply pin texts (`REF`, `FB`, `B0`, `B1`, `IBN`, `ICN`,
`IBP`, `ICP`, `VOUT`); `(36,10)` carries only `UP` and `DN`. With one label per
rail, a severed piece is unlabelled, is therefore not a match, and
`matched_islands` still reads `1`.

**This is not hypothetical on this block.** The n-well tap rail discussed below
— 152.01 µm² of Metal1, 46.01 µm² of Metal2 and 32.29 µm² of Metal3, spanning
x ≈ 119–279 µm — is a *genuinely separate electrical island* from the labelled
`VDD` net, and the supply-continuity check above is blind to it. What found it
was `erc.missing_tie`. That is worth stating plainly: on a one-label-per-net
block, the tie check is not a redundant extra — it is the check doing the work.

The complementary measurement (`nets[].roles` +
`unlabelled_islands`/`unlabelled_area_um2`, klayout-tools#2510) is deliberately
**not** declared here, and measured so the decision is checkable:

```
$ # the committed spec with roles: ["metal1","metal2","metal3"] added to VDD
$ klt erc --top pfd_cp --deck gf180mcu --findings-only --format json … | jq '.nets[0]'
{ "name": "VDD", "matched_islands": 1, "expected_islands": 1,
  "roles": ["metal1","metal2","metal3"],
  "unlabelled_islands": 34, "unlabelled_area_um2": 1293.2745,
  "unlabelled_bbox": { "left": -27010, "bottom": -11765, "right": 317300, "top": 55950 } }
```

34 unlabelled islands over 1293.27 µm². One of them is the tap rail below; the
other 33 are this block's unlabelled internal signal nets, which live on the
same three routing roles. Declaring that `VDD` "owns" `metal1`/`metal2`/`metal3`
outright would be false on this block, and the resulting number would invite
exactly the wrong reading — a non-zero remainder that is mostly not a supply
defect. The field is reporting-only and fails nothing either way. It is declared
only on [`lock_detector`](../lock-detector-layout/PROOF-erc.md), where the same
measurement returns **0** and the ownership claim is both true and load-bearing.

## The well-tie half: two well classes, one declarable

### What the layout actually does

This block draws **fifteen** merged `Nwell (21/0)` shapes. Deriving each one's
n-tap as `Comp (22/0) ∩ Nplus (32/0)` — the boolean gf180mcu draws an n-well
tap as, and what distinguishes it from a pfet source/drain (`Comp ∩ Pplus`) —
and asking which net each tap reaches:

```
$ python3 - <<'PY'
import klayout.db as db
ly = db.Layout(); ly.read("layout/evidence/pfd-cp-layout/pfd_cp.gds")
top, dbu = ly.top_cell(), ly.dbu
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, []))
L = lambda l, d, n: l2n.make_polygon_layer(ly.layer(l, d), n)
po, m1, m2, m3 = L(30,0,"poly2"), L(34,0,"metal1"), L(36,0,"metal2"), L(42,0,"metal3")
co, v1, v2 = L(33,0,"contact"), L(35,0,"via1"), L(38,0,"via2")
ntap = L(22,0,"comp") & L(32,0,"nplus")          # how gf180mcu draws an n-well tap
l2n.register(ntap, "ntap")
for a, b in ((co,po),(co,m1),(co,ntap),(m1,v1),(v1,m2),(m2,v2),(v2,m3)):
    l2n.connect(a, b)
for r in (po,m1,m2,m3,co,v1,v2,ntap):
    l2n.connect(r)
l2n.connect(m1, l2n.make_text_layer(ly.layer(34,10), "m1lab"))
l2n.extract_netlist()
taps = []
for c in l2n.netlist().each_circuit():
    for net in c.each_net():
        r = db.Region()
        for s in l2n.shapes_of_net(net, ntap, True).each():
            r.insert(s.polygon if hasattr(s, "polygon") else db.Polygon(s))
        if not r.is_empty():
            taps.append((net.expanded_name(), r))
for p in db.Region(db.RecursiveShapeIterator(ly, top, ly.layer(21,0))).merged().each():
    bb, pr = p.bbox(), db.Region(p)
    names = sorted({n for n, r in taps if not (r & pr).is_empty()})
    print("nwell (%.2f,%.2f)-(%.2f,%.2f) tap nets: %s"
          % (bb.left*dbu, bb.bottom*dbu, bb.right*dbu, bb.top*dbu, names))
PY
nwell (30.52,-12.25)-(93.52,-7.65) tap nets: ['VDD']
nwell (174.82,-12.25)-(225.82,-7.45) tap nets: ['VDD']
nwell (31.29,-5.75)-(48.29,0.48) tap nets: ['VDD']
nwell (71.83,-5.75)-(88.83,0.48) tap nets: ['VDD']
nwell (51.56,-1.13)-(68.56,5.10) tap nets: ['VDD']
nwell (118.82,7.75)-(169.82,12.55) tap nets: ['VDD']
nwell (176.82,7.75)-(279.82,12.55) tap nets: ['$13']        <-- not VDD
nwell (51.56,8.10)-(68.56,14.33) tap nets: ['VDD']
nwell (25.71,31.78)-(51.71,35.68) tap nets: ['VDD']
nwell (121.32,36.30)-(200.22,40.80) tap nets: ['VDD']
nwell (-17.29,37.08)-(-14.79,40.98) tap nets: ['VDD']
nwell (18.71,37.08)-(21.21,40.98) tap nets: ['VDD']
nwell (54.71,37.08)-(57.21,40.98) tap nets: ['VDD']
nwell (62.71,37.08)-(65.21,40.98) tap nets: ['VDD']
nwell (124.12,47.73)-(197.42,52.23) tap nets: ['VDD']
```

Fourteen on `VDD`; one on an **unlabelled** net. (`$13` is KLayout's synthetic
name for a net with no label text; the digits are an extraction-order artifact
and carry no meaning — reordering the `make_polygon_layer` calls above renumbers
it. What matters is that it is not `VDD`.)

That fifteenth well is **`(176.820, 7.755)`–`(279.820, 12.555)` µm**, and it is
not empty: inside it sit 192.00 µm² of p-type diffusion (`Comp ∩ Pplus`) crossed
by four poly gate polygons totalling 96.00 µm² — the gate area of **two W=48 µm,
L=1 µm pfets** — plus 61.20 µm² of n-tap.

### It is deliberate, and three independent sources say so

| Source | What it says |
|---|---|
| `design/cp_dumpbuf.sch`, design-intent header | *"MP1/MP2 have their bulk tied to their common source PSRC rather than to VDD: removing the body effect on the input pair recovers input range at the top of the window. MN1/MN2 cannot do the same — there is no isolated p-well for `nfet_03v3` — which is part of why the PMOS-input amplifier is the one carrying the bottom of the range."* |
| `lvs-clean/pfd_cp.spice` (the schematic reference) | `M_pfd_cp_xcp_xbuf_MP1` and `M_pfd_cp_xcp_xbuf_MP2`, both `pfet_03v3 L=1u W=48u`, both with source **and bulk** on `pfd_cp_xcp_xbuf_PSRC`. Two devices, matching the two pfets measured in that well. |
| `lvs-clean/pfd_cp.lvsdb` (the PDK deck's own **device-aware** extraction) | The layout net that owns that well, its n-tap and its whole Metal1/2/3 rail is paired `Match` with schematic net `PFD_CP_XCP_XBUF_PSRC`. |

The third row is the decisive one, so it is reproducible rather than described:

```
$ python3 - <<'PY'
import klayout.db as db
lvs = db.LayoutVsSchematic(); lvs.read("layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.lvsdb")
xref = lvs.xref()
for cp in xref.each_circuit_pair():
    for np_ in xref.each_net_pair(cp):
        a, b = np_.first(), np_.second()
        if a and a.expanded_name() == "$30":
            print("layout net", a.expanded_name(), "<->", b.expanded_name(), "status", np_.status())
PY
layout net $30 <-> schematic net PFD_CP_XCP_XBUF_PSRC status Match
```

and that same layout net `$30` is the one whose geometry covers the flagged
well. Walking `lvs.shapes_of_net(net, layer)` over every layer the `.lvsdb`
carries, net `$30` owns — among others — a layer whose extent is exactly
`(176820, 7755)`–`(279820, 12555)` in database units (the flagged `Nwell` shape,
the exact bbox `klt erc` reports), a layer whose extent is the n-tap inside it
`(177320, 11455)`–`(279320, 12055)`, and a layer whose extent is
`(119340, 8235)`–`(279440, 12175)` — the Metal1 rail, numerically identical to
the metal-only island measured independently above. (The deck's layer names in a
`.lvsdb` are anonymous `l<N>` indices, so the identification is by geometry, not
by name.) Two extractions built on different
connectivity models agree on the geometry and disagree only about the *name*,
which the deck supplies from the schematic pairing and `klt erc` cannot.

**The `connect_implicit('*')` caveat does not weaken this.** The gf180mcu deck
ends its connectivity setup with `connect_implicit('*')`
(`general_connections.lvs:100`), which joins nets **by name** — so an LVS
`Match` is never evidence that two same-named metal islands touch (this
repository learned that the hard way; see
[`../vco-layout/PROOF-433-vdd-island-fix.md`](../vco-layout/PROOF-433-vdd-island-fix.md)
step 3). The claim made here is the opposite shape and is immune to it: the
well's rail is a **differently**-named net, matched to a differently-named
schematic net, and `connect_implicit` can only ever *merge* same-name nets, never
split a net away from `VDD`. Had the layout mistakenly tied that well to `VDD`,
`connect_implicit` would not have separated it; had the schematic not asked for
`PSRC` there, the pairing would have been a mismatch, and this block's LVS is
168/168 devices `Match`, 88 nets `Match` + 4 `MatchWithWarning`, 0 mismatches.

### Why it cannot be declared, measured

A single `ties[]` entry grades **every** shape of the declared `well_layer`
against its own one `net`. Declaring the fourteen-well `VDD` class therefore
produces a false finding on the fifteenth. Run, so the obstacle is a
measurement rather than a prediction — this is the committed spec with the
`ties_disclosure` swapped for a `ties[]` entry, and it is **not** what is
committed:

```json
{ "rule": "erc.missing_tie",
  "description": "well/tub tap is not connected to declared net 'VDD'",
  "net": "VDD", "layer": "nwell_vdd",
  "bbox": { "left": 176820, "bottom": 7755, "right": 279820, "top": 12555 },
  "islands": null }
```

`erc_status` becomes `"violations"`, and the finding is an `erc.missing_tie`
naming a declared supply — which item 11 grades as `supply_not_continuous`. So
both available routes end `unmet`; what differs is whether the report tells a
reader a true thing.

klt 0.6.0 provides the mechanism built for exactly this shape —
**`ties[].well_requires` / `ties[].well_excludes`** (klayout-tools#2339), whose
own upstream description is a block "whose one drawn tub layer carries two
differently-biased well classes … each entry graded *every* shape of the shared
`well_layer` against its own single `net`, so whichever class was not declared
reported a false `erc.missing_tie`". It selects whole drawn well shapes by
*interaction with a marker layer*, and **this stream draws no layer that
separates the two classes.** Verified exhaustively over every one of the twelve
non-`Nwell` layers the GDS contains:

| Layers | Wells they interact with | Separates the `PSRC` well? |
|---|---|---|
| `22/0`, `30/0`, `31/0`, `32/0`, `33/0`, `34/0`, `42/0` | all 15 | no |
| `35/0`, `36/0`, `38/0` | 10 of 15, **including** the `PSRC` well | no |
| `34/10`, `36/10` | none (zero-area text only) | no |

Neither a `well_requires` nor a `well_excludes` built from any of them isolates
that well. And unlike the tap side — where a stream with no distinguishing
marker can still declare a checked tie by naming the geometry outright
(`ties[].tap_boxes`, klayout-tools#2234) — there is **no caller-assertion
counterpart on the well-selection side**. The tap here is perfectly nameable;
what cannot be named is *which wells the declaration applies to*.

### What the spec therefore declares

```json
"ties_disclosure": { "kind": "tool_limitation", "reason": "…" }
```

and the report echoes it into coverage:

```json
"erc_coverage": {
  "skipped": [],
  "inapplicable": [ { "id": "erc.missing_tie:[]",
                      "reason": "ties_disclosed_tool_limitation" } ]
}
```

That reason token is what makes the state legible to a grader. The three
zero-`ties[]` states item 11 can render are mechanically distinguishable:
`supply_spec_incomplete` (nobody asked the question),
`supply_spec_disclosed_unexpressible` (no tap to name), and
`supply_spec_disclosed_tool_limitation` — a tap, and a build that cannot be
trusted to grade it. This block is the third, and `provenance.klt_version`
(`0.6.0+gf2d249ab23d4`) pins the build the disclosure is about, so a future
reader can check whether it still applies to the `klt` in front of them.

`kind: "unexpressible"` would have been wrong: it means *nothing drawn to
narrow, affirm or bound*, and this block's taps are drawn and narrowable. The
obstacle is the well-class selection, not the tap.

**Item 11 stays `unmet` for this block, and it should.** A disclosure proves
nothing about the taps' actual connectivity. What it buys is that the remedy is
named — a well-side selection assertion, upstream — instead of a reader being
left to guess whether anybody looked.

### Why the p-substrate tie is also undeclared

Independently of the above: gf180mcu draws **no pwell/tub layer** for a
native-substrate NMOS block (this GDS's `layer_indexes()` are `{21/0, 22/0,
30/0, 31/0, 32/0, 33/0, 34/0, 34/10, 35/0, 36/0, 36/10, 38/0, 42/0}`), and the
one expressible alternative — a caller-asserted substrate region
(`well_layer: null` + `well_boxes`, klayout-tools#2255) — is graded
**degenerate** when it covers the whole top-cell extent, which a native
p-substrate does. See
[`../lock-detector-layout/PROOF-erc.md`](../lock-detector-layout/PROOF-erc.md) →
"Why the p-substrate tie is left undeclared" for the measured negative control
(reason `degenerate_well_assertion`). For this block the point is moot: `ties[]`
is empty for the reason above, so the disclosure covers both classes.

## Coverage: what the spec did and did not look at

```json
"erc_coverage": { "layers_in_stream_without_declaration": [], "nothing_checked": false }
```

**Empty** (klayout-tools#2389): every layer this GDS draws is accounted for by
the spec's `stackup`/`vias` declarations or by the `--deck gf180mcu` device
markers — including `Nwell (21/0)` and both implants, which the deck's own
device declarations cover even though no `ties[]` entry names them here. A clean
supply read is only as wide as the declaration behind it, and this one is as
wide as the stream.

`provenance.devices` is `[]` — the curated deck found no device-body marker to
carve out, because this block draws none (no poly resistors, no MiM caps;
contrast `vco_block`, where the same flag subtracts 71.6 µm² of `ppolyf_u_1k`
body from the `poly2` role). The flag is passed anyway so all four blocks'
reports come from one command shape.

## Antenna coverage: zero, declared

```json
"pdk": null,
"coverage": { "scope": "antenna", "known": true, "checked": [], "skipped": [ … 219 entries … ] }
```

**`checked: 0, skipped: 219, reason `missing_antenna_pdk` on every one.`**
`klt erc --pdk` offers a real antenna-ratio limit table for `sky130` only; there
is no gf180mcu table, so every per-gate per-level `antenna_ratio` in this report
carries `verdict: "unchecked"` and `antenna_ratio_max: null`. The ratios are
computed and committed; they are graded against nothing.

**"`klt erc` has been run on this block" must never be read as "antenna
checking passed."** Item 11 does not ask for the antenna half — it is the
structural power-delivery item, and antenna limits are klayout-tools#1994's
territory — which is why this run is still item-11 evidence.

## Upstream friction

Filed generically at `2AMLogic/klayout-tools` per CLAUDE.md's friction protocol,
described as a tool gap rather than a fact about this design: **well-side class
selection has no caller-assertion counterpart.**
`ties[].well_requires`/`well_excludes` select drawn well shapes by interaction
with a marker layer; a stream with two deliberately differently-biased well
classes and no layer that separates them cannot use it, and there is no
`well_boxes`-style literal-geometry escape hatch on the well-selection side the
way `ties[].tap_boxes` is one on the tap side. Cross-referenced from
[`../vco-layout/PROOF-erc.md`](../vco-layout/PROOF-erc.md) → "Upstream
friction", which also carries the second gap this pass found (a `ties[]` class a
spec cannot express has no disclosure path when the spec declares another
class).

## Scope

**Not settled, and named:** item 11's ERC half for this block, for the reason
above. This is the honest outcome — a correct layout, a documented deliberate
body-tie, and no declaration available today that says so.

**Also not settled, separately:** item 11 grades a *set* — a `klt erc` supply
citation **and** an `lvs` citation, the latter being the same report item 4
grades. This repository runs LVS through the PDK's own `run_lvs.py`, not through
`klt lvs`, so **no `klt lvs` envelope exists for any block here** and `klt
signoff` cannot assemble the cited set at all yet.
`signoff/block-manifest.json` therefore still cites nothing, and this record
makes no claim about `signoff/tier-report.json`.
