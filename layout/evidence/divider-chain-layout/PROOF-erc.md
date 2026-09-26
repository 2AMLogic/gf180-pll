# `divider_chain` structural power-delivery ERC (T1 checklist item 11, issue #565)

The first `klt erc` supply-spec run committed for this block. It targets the
T1/bronze design-evidence checklist's eleventh item, *"Power delivery
(structural)"* (klayout-tools#2025, bundled with klt 0.6.0 as
`docs/design-evidence-tiers.md`) — a purely structural question ("is the supply
net connected to what it powers"), not IR-drop or EM analysis.

**Result: the ERC half of item 11 is clean for this block — both declared
supplies resolve to exactly one labelled electrical island, and the n-well tie
is declared and checked with zero `erc.missing_tie` findings.** One qualifier
belongs in the headline rather than a footnote: this block labels **one text per
supply net**, so the island count is a weaker bound here than on
`lock_detector`, and the reason is stated and quantified under "The island count
is a weak bound here — how weak, measured".

Two further limits are stated rather than left to be discovered: the **antenna
half of `klt erc` has never run in this repository** (see "Antenna coverage"),
and item 11 grades a *set* that also needs a `klt lvs` citation this repository
does not produce (see "Scope").

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | The `klt erc` spec: gate+conductor stackup (Poly2 through Metal3, `active_layer` = Comp for true `poly ∩ diff` gate area), the vias bridging it, the n-well `ties[]` entry, and the two declared supply nets (`VDD_DIV`, `VSS`). Every entry carries an inline `_comment` justifying it. |
| [`erc-report.json`](erc-report.json) | The run below, against the exact `divider_chain.gds` committed alongside it. |

## Provenance

| | |
|---|---|
| Run | 2026-09-26 (issue #565) |
| `klt` | `0.6.0+gf2d249ab23d4` — the released `klayout-tools==0.6.0` wheel, exactly what `.github/workflows/ci.yml` installs for the signoff tier check |
| KLayout (Python engine) | `0.30.12` |
| `--deck` | `gf180mcu`, `content_hash` `sha256:8da880a4b42bb27d4710b3647c2157c42b32de22da51b0259c82aa2c1c3441b4` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) — the layer numbers this spec was cross-checked against. `klt erc` itself needs no PDK install. |

```
$ klt erc --top divider_chain --deck gf180mcu --format json \
    layout/evidence/divider-chain-layout/divider_chain.gds \
    layout/evidence/divider-chain-layout/erc-supply-spec.json
$ cd layout/evidence/divider-chain-layout && sha256sum divider_chain.gds erc-supply-spec.json
bb5d78a0f80130bd8fbcc766b0e71d07493c7d0e5c92edf549044f66a7704404  divider_chain.gds
1ca2683367e0e24fbde61e5e75124deb942a7f652620b897f5e386cc1eeb046c  erc-supply-spec.json
```

`erc-report.json`'s `provenance.input.content_hash` and
`provenance.spec.content_hash` are `sha256:` prefixed copies of exactly those
two digests — **and that pair is a build gate, not a promise**:
`layout/lib/check-layout-status-claims.sh` recomputes both on every CI run and
fails if either disagrees. The report's `file` field is the committed
repo-relative path, not a scratch path.

## The verdict

```json
"erc_status": "clean",
"erc_finding_count": 0,
"erc_findings": [],
"nets": [
  { "name": "VDD_DIV", "matched_islands": 1, "expected_islands": 1, "roles": [], … },
  { "name": "VSS",     "matched_islands": 1, "expected_islands": 1, "roles": [], … }
]
```

No `erc.unconnected_net`, no `erc.supply_short`, no `erc.missing_tie`, and no
`erc.floating_gate` across all 140 gate nets — this block's own DFF/mux row
logic, which is the largest gate population of the four.

**`status` is `"not_checked"` (exit 4), and that is not a weaker verdict than
`"clean"`.** The envelope's `status` aggregates the antenna half too, and the
antenna half cannot run without `--pdk` (see below). The field item 11's grader
reads is `erc_status`, which is `"clean"` — the same distinction the upstream
checklist makes when it says this item "does not simply require the ERC
envelope's own `status == \"clean\"`".

### The island count is a weak bound here — how weak, measured

`erc.unconnected_net` counts the islands **carrying the declared label**, not
the islands the net's conductor geometry forms (klayout-tools#2497). On a block
that names each net once at a port, a severed rail still reports `matched_islands:
1`, because the orphaned piece is unlabelled and therefore not a match.

**This block is such a block.** Walking every text shape on `(34,10)`
(`Metal1_Label`) of the committed GDS finds **exactly one instance each of
`VDD_DIV` and `VSS`**, among 70 Metal1 texts in total — the block labels nearly
every internal *signal* node (`MA`, `MB`, `DIVOUT`, `DIVOUTB`, `VCO`, `FB`,
`FBB`, the per-stage `MI<i>`/`MO<i>`/`SEL<i>`/`T<i>`/`P<i>`/`CK<i>` nets, the
`XM*`/`XNR*`/`XFRT*` midpoints), but each supply rail exactly once.

So the honest reading of the clean verdict above is: **no *labelled* piece of
either supply is disconnected from the rest**, and `erc.unconnected_net` on its
own cannot rule out an unlabelled orphan.

The complementary measurement exists — `nets[].roles` plus
`unlabelled_islands`/`unlabelled_area_um2` (klayout-tools#2510), the unlabelled
conductor on the roles a net declares it owns — and **this spec deliberately
does not declare it**, because on this block it would not mean what its name
suggests. Measured, so the decision is checkable rather than asserted:

```
$ # the committed spec with roles: ["metal1","metal2","metal3"] added to VDD_DIV
$ klt erc --top divider_chain --deck gf180mcu --findings-only --format json … | jq '.nets[0]'
{ "name": "VDD_DIV", "matched_islands": 1, "expected_islands": 1,
  "roles": ["metal1","metal2","metal3"],
  "unlabelled_islands": 144, "unlabelled_area_um2": 4204.3116,
  "unlabelled_bbox": { "left": 45490, "bottom": 80, "right": 1249620, "top": 35990 } }
```

144 unlabelled islands over 4204.31 µm², spanning essentially the whole
1308 µm width of the block. Those are **not** 144 orphaned supply fragments:
they are the unlabelled internal nets of a 6-stage divider's row logic sitting
on the same three routing roles. `unlabelled_islands` is reporting-only and
changes no verdict, so declaring it would fail nothing — but declaring that
`VDD_DIV` "owns" `metal1`/`metal2`/`metal3` outright would be false on this
block, and the resulting number would invite precisely the wrong reading. It is
declared only on [`lock_detector`](../lock-detector-layout/PROOF-erc.md), where
the same measurement returns **0** and the ownership claim is therefore both
true and load-bearing.

**What stands in for it here, and what does not.** This block's committed
block-level LVS is a full match (`lvs-clean/lvs.stdout.log`,
`Congratulations! Netlists match.`), and its schematic reference carries
`VDD_DIV` and `VSS` — but per the correction recorded in
[`../vco-layout/PROOF-erc.md`](../vco-layout/PROOF-erc.md), a net-level LVS
`Match` is **not** evidence that two same-named metal islands touch: the gf180mcu
deck ends its connectivity setup with `connect_implicit('*')`
(`general_connections.lvs:100`), which joins nets by name. Two disjoint
`VDD_DIV` islands would still compare as one net. So the LVS match is cited here
for what it does prove — devices, device parameters, and every differently-named
net's topology — and explicitly **not** as same-name continuity evidence. The
one check that would close the gap for this block is the same geometric,
device-aware island count `PROOF-433-vdd-island-fix.md` performs for
`vco_block`: a merge of every shape of the deck's own extracted `VDD_DIV` net,
counted. **It has not been run for this block**, and that is the honest
statement of the residual gap rather than a claim of equivalence.

### The n-well tie is declared and checked

```json
{ "name": "nwell_vdd_div", "well_layer": "21/0", "tap_layer": "22/0",
  "tap_requires": ["32/0"], "connect_to": "metal1", "net": "VDD_DIV" }
```

`tap_layer ∩ tap_requires` is `Comp (22/0) ∩ Nplus (32/0)` — the boolean
gf180mcu actually draws an n-well tap as, and what distinguishes it from a pfet
source/drain (`Comp ∩ Pplus`). All **fourteen** merged `Nwell` shapes this block
draws must each hold at least one such tap, wired up to Metal1 and reaching
`VDD_DIV`. From the report:

```json
"erc_coverage": {
  "checked": [ "…", "erc.missing_tie:[\"nwell_vdd_div\"]" ],
  "skipped": [], "inapplicable": [],
  "checked_by_assertion": [], "checked_by_well_assertion": []
}
```

The identity is in **`checked`** (the work ran, as against `no_ties_declared`),
**`skipped` is empty** (the `tap_requires` narrowing keeps it out of the
`degenerate_tap_declaration` bucket, klayout-tools#2199, which item 11 refuses
to read as a clean tie verdict), and both assertion lists are **empty** (the tap
region is derived from drawn PDK implant geometry, not from caller-asserted
boxes). Fourteen wells, fourteen taps reaching the rail: this is the half of
supply correctness that is *not* weakened by the one-label-per-net issue above,
because it is computed from geometry and connectivity rather than from label
matching.

### Why the p-substrate tie is left undeclared

The spec declares one tie, not two. The `VSS`/p-substrate side is not declared,
and that is measured rather than overlooked: gf180mcu draws **no pwell/tub
layer** for a native-substrate NMOS block (this GDS's own `layer_indexes()` are
`{21/0, 22/0, 30/0, 31/0, 32/0, 33/0, 34/0, 34/10, 35/0, 36/0, 38/0, 42/0}`),
and the one expressible alternative — a caller-asserted substrate region
(`well_layer: null` + `well_boxes`, klayout-tools#2255) — is graded
**degenerate** when it covers the whole top-cell extent, which a native
p-substrate does. Declaring it would land the tie in `erc_coverage.skipped`,
which item 11's grader reads as `supply_spec_incomplete`: strictly worse than
the clean checked n-well tie above.

That prediction is verified by a negative control run on `lock_detector` and
quoted in full in
[`../lock-detector-layout/PROOF-erc.md`](../lock-detector-layout/PROOF-erc.md) →
"Why the p-substrate tie is left undeclared" (reason
`degenerate_well_assertion`, in `klt erc`'s own words). `klt erc` has no per-tie
disclosure for a class a spec leaves out while declaring another
(`ties_disclosure` is top-level and consulted only when `ties[]` is empty), so
this section is the disclosure; the gap is filed upstream — see
[`../vco-layout/PROOF-erc.md`](../vco-layout/PROOF-erc.md) → "Upstream
friction".

## Coverage: what the spec did and did not look at

```json
"erc_coverage": { "layers_in_stream_without_declaration": [], "nothing_checked": false }
```

**Empty** (klayout-tools#2389): every layer this GDS draws is accounted for by
the spec's `stackup`/`vias`/`ties` declarations or by the `--deck gf180mcu`
device markers. A clean supply read is only as wide as the declaration behind
it, and this one is as wide as the stream.

`provenance.devices` is `[]` — the curated deck found no device-body marker to
carve out, because this block draws none (no poly resistors, no MiM caps;
contrast `vco_block`, where the same flag subtracts 71.6 µm² of `ppolyf_u_1k`
body from the `poly2` role). The flag is passed anyway so all four blocks'
reports come from one command shape.

## Antenna coverage: zero, declared

```json
"pdk": null,
"coverage": { "scope": "antenna", "known": true, "checked": [], "skipped": [ … 420 entries … ] }
```

**`checked: 0, skipped: 420, reason `missing_antenna_pdk` on every one.`**
`klt erc --pdk` offers a real antenna-ratio limit table for `sky130` only;
there is no gf180mcu table, so every per-gate per-level `antenna_ratio` in this
report carries `verdict: "unchecked"` and `antenna_ratio_max: null`. The ratios
are computed and committed; they are graded against nothing. This is the largest
skipped count of the four blocks, simply because it has the most gate nets.

**"`klt erc` has been run on this block" must never be read as "antenna
checking passed."** Item 11 does not ask for the antenna half — it is the
structural power-delivery item, and antenna limits are klayout-tools#1994's
territory — which is why this run is still item-11 evidence.

## Scope

**Settled:** the ERC half of item 11 for this block, on the klt version CI
pins, reproducibly — with the island count's own strength stated above rather
than implied.

**Not settled:** item 11 itself. The item grades a *set* — a `klt erc` supply
citation **and** an `lvs` citation, the latter being the same report item 4
grades, which must itself pass. This repository runs LVS through the PDK's own
`run_lvs.py`, not through `klt lvs`, so **no `klt lvs` envelope exists for any
block here** and `klt signoff` cannot assemble the cited set at all yet.
`signoff/block-manifest.json` therefore still cites nothing, and this record
makes no claim about `signoff/tier-report.json`.
