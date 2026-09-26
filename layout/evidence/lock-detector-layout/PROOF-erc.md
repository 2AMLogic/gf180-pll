# `lock_detector` structural power-delivery ERC (T1 checklist item 11, issue #565)

The first `klt erc` supply-spec run committed for this block. It targets the
T1/bronze design-evidence checklist's eleventh item, *"Power delivery
(structural)"* (klayout-tools#2025, bundled with klt 0.6.0 as
`docs/design-evidence-tiers.md`) — a purely structural question ("is the supply
net connected to what it powers"), not IR-drop or EM analysis.

**Result: the ERC half of item 11 is clean for this block — both declared
supplies resolve to exactly one electrical island, the n-well tie is declared
and checked with zero `erc.missing_tie` findings, and every conductor polygon on
all three routing roles is reachable from a label.** Of the four PLL sub-blocks
this is the strongest supply evidence, for a reason specific to how it is drawn
(per-segment rail labelling) rather than to how the spec is written.

Two limits on that result are stated here rather than left to be discovered:
the **antenna half of `klt erc` has never run in this repository** (see
"Antenna coverage"), and item 11 grades a *set* that also needs a `klt lvs`
citation this repository does not produce (see "Scope: what this does and does
not settle").

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | The `klt erc` spec: gate+conductor stackup (Poly2 through Metal3, `active_layer` = Comp for true `poly ∩ diff` gate area), the vias bridging it, the n-well `ties[]` entry, and the two declared supply nets (`VDD`, `VSS`) with their owned `roles[]`. Every entry carries an inline `_comment` justifying it. |
| [`erc-report.json`](erc-report.json) | The run below, against the exact `lock_detector.gds` committed alongside it. |

## Provenance

| | |
|---|---|
| Run | 2026-09-26 (issue #565) |
| `klt` | `0.6.0+gf2d249ab23d4` — the released `klayout-tools==0.6.0` wheel, exactly what `.github/workflows/ci.yml` installs for the signoff tier check |
| KLayout (Python engine) | `0.30.12` |
| `--deck` | `gf180mcu`, `content_hash` `sha256:8da880a4b42bb27d4710b3647c2157c42b32de22da51b0259c82aa2c1c3441b4` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) — the layer numbers this spec was cross-checked against. `klt erc` itself needs no PDK install. |

```
$ klt erc --top lock_detector --deck gf180mcu --format json \
    layout/evidence/lock-detector-layout/lock_detector.gds \
    layout/evidence/lock-detector-layout/erc-supply-spec.json
$ cd layout/evidence/lock-detector-layout && sha256sum lock_detector.gds erc-supply-spec.json
799af5d7f6b8407c5efc50b7e8ef639a8aa8787eb91b47e1f31f66f1673b2c0c  lock_detector.gds
194a16dd7b7e50071c2e7fded07de23bb0806ca90f6e8f35ca555c09d61662f9  erc-supply-spec.json
```

`erc-report.json`'s `provenance.input.content_hash` and
`provenance.spec.content_hash` are `sha256:` prefixed copies of exactly those
two digests, so the committed report was produced from exactly the committed
layout and exactly the committed spec — **and that pair is a build gate, not a
promise**: `layout/lib/check-layout-status-claims.sh` recomputes both on every
CI run and fails if either disagrees. The report's `file` field is the
committed repo-relative path, not a scratch path.

## The verdict

```json
"erc_status": "clean",
"erc_finding_count": 0,
"erc_findings": [],
"nets": [
  { "name": "VDD", "matched_islands": 1, "expected_islands": 1,
    "roles": ["metal1", "metal2", "metal3"],
    "unlabelled_islands": 0, "unlabelled_area_um2": 0.0, "unlabelled_bbox": null },
  { "name": "VSS", "matched_islands": 1, "expected_islands": 1,
    "roles": ["metal1", "metal2", "metal3"],
    "unlabelled_islands": 0, "unlabelled_area_um2": 0.0, "unlabelled_bbox": null }
]
```

No `erc.unconnected_net`, no `erc.supply_short`, no `erc.missing_tie`, and no
`erc.floating_gate` across all 39 gate nets.

**`status` is `"not_checked"` (exit 4), and that is not a weaker verdict than
`"clean"`.** The envelope's `status` aggregates the antenna half too, and the
antenna half cannot run without `--pdk` (see below). The field item 11's grader
reads is `erc_status`, which is `"clean"` — the same distinction the upstream
checklist makes when it says this item "does not simply require the ERC
envelope's own `status == \"clean\"`".

### Why `matched_islands: 1` is a strong statement here and not elsewhere

`erc.unconnected_net` counts the islands **carrying the declared label**, not
the islands the net's conductor geometry forms. On a block that draws one text
per net — the ordinary generated-analog pattern — a severed rail still reports
`1`, because the orphaned piece is unlabelled and therefore not a match. That
is the failure mode that hid a genuinely disconnected tap rail in `pfd_cp`
until its `erc.missing_tie` check caught it
([`../pfd-cp-layout/PROOF-erc.md`](../pfd-cp-layout/PROOF-erc.md)).

This block is not exposed to it, and the report proves that rather than
asserting it, two independent ways:

1. **Per-segment rail labelling.** Walking every text shape on `(34,10)`
   (`Metal1_Label`) of the committed GDS finds **29 instances of `VDD` and 29 of
   `VSS`, and nothing else on that layer**; `(36,10)` (`Metal2_Label`) carries
   one more of each alongside the block's internal signal texts. The rails are
   annotated along their length, not named once at a port.

   ```
   $ python3 - <<'PY'
   import collections, klayout.db as db
   ly = db.Layout(); ly.read("layout/evidence/lock-detector-layout/lock_detector.gds")
   it = db.RecursiveShapeIterator(ly, ly.top_cell(), ly.layer(34, 10))
   it.shape_flags = db.Shapes.STexts
   n = collections.Counter()
   while not it.at_end():
       if it.shape().is_text(): n[it.shape().text.string] += 1
       it.next()
   print(dict(n))
   PY
   {'VDD': 29, 'VSS': 29}
   ```

2. **`unlabelled_islands: 0` / `unlabelled_area_um2: 0.0`** (klayout-tools#2510).
   Both supplies declare `roles: ["metal1", "metal2", "metal3"]`, which makes
   `klt erc` measure the conductor on those roles reachable from **no label at
   all** — the only place an orphaned rail segment could hide from the labelled
   island count. It is zero. Not "zero supply orphans": zero unlabelled
   conductor polygons *anywhere* on all three routing roles of this block. An
   island the label count cannot see does not exist here, so `matched_islands:
   1` is a real one-island statement.

   This is why the other three blocks do **not** declare `roles[]`: the same
   measurement on `divider_chain` returns 144 unlabelled islands / 4204.31 µm²
   and on `pfd_cp` 34 islands / 1293.27 µm², dominated by unlabelled internal
   *signal* nets rather than by supply orphans. The field is reporting-only and
   changes no verdict, so a large remainder would not fail anything — but
   declaring that a supply "owns" a role whose unlabelled remainder is mostly
   somebody else's signal net would be an over-claim, and the number would
   invite exactly the wrong reading. Declared only where it is both true and
   informative.

### The n-well tie is declared and checked

```json
{ "name": "nwell_vdd", "well_layer": "21/0", "tap_layer": "22/0",
  "tap_requires": ["32/0"], "connect_to": "metal1", "net": "VDD" }
```

`tap_layer ∩ tap_requires` is `Comp (22/0) ∩ Nplus (32/0)` — the boolean
gf180mcu actually draws an n-well tap as, and what distinguishes it from a pfet
source/drain (`Comp ∩ Pplus`). This block draws a **single** merged `Nwell`
shape, which must hold at least one such tap wired up to Metal1 and reaching
`VDD`. From the report:

```json
"erc_coverage": {
  "checked": [ "…", "erc.missing_tie:[\"nwell_vdd\"]" ],
  "skipped": [], "inapplicable": [],
  "checked_by_assertion": [], "checked_by_well_assertion": []
}
```

Three states that fragment rules out, each of which item 11 treats differently
from a pass:

* the identity is in **`checked`**, not `inapplicable` — the work ran, as
  against a spec that declares no `ties[]` (`no_ties_declared`, rendering
  `supply_spec_incomplete`);
* **`skipped` is empty** — the `tap_requires` narrowing keeps this out of the
  `degenerate_tap_declaration` bucket (klayout-tools#2199), which item 11
  refuses to read as a clean tie verdict;
* both assertion lists are **empty** — the tap region is derived from drawn PDK
  implant geometry, not from caller-asserted boxes (`ties[].tap_boxes`,
  klayout-tools#2234) or an asserted substrate region
  (`ties[].well_boxes`, klayout-tools#2255). Nothing here rests on this
  record's word about where the tap is.

### Why the p-substrate tie is left undeclared

The spec declares one tie, not two. The `VSS`/p-substrate side is not
declared, and that is measured rather than overlooked:

1. gf180mcu draws **no pwell/tub layer** for a native-substrate NMOS block —
   this GDS's own `layer_indexes()` are `{21/0, 22/0, 30/0, 31/0, 32/0, 33/0,
   34/0, 34/10, 35/0, 36/0, 36/10, 38/0, 42/0}`, with nothing to name as
   `well_layer` for the substrate.
2. The one form `klt erc` provides is the caller-asserted substrate region
   (`well_layer: null` + `well_boxes`, klayout-tools#2255) — and an assertion
   indistinguishable from the whole top-cell extent is graded **degenerate**,
   because it would make `erc.missing_tie` satisfiable by any contact anywhere.
   A native p-substrate *is* the whole top-cell extent.
3. So declaring it reports strictly **less** than leaving it undeclared: a
   skipped tie lands in `erc_coverage.skipped`, which item 11's grader reads as
   `supply_spec_incomplete` — turning a clean checked n-well tie into an unmet
   item.

**Negative control, measured on this block** (a `well_boxes` assertion over its
exact top-cell extent `(-0.500, -5.550)`–`(294.300, 98.200)` µm, added as a
second tie):

```json
"checked": [ "erc.missing_tie:[\"nwell_vdd\"]" ],
"skipped": [ { "id": "erc.missing_tie:[\"psub_vss\"]",
               "reason": "degenerate_well_assertion" } ],
"checked_by_well_assertion": []
```

The prediction in (3) is what `klt erc` reports, in `klt erc`'s own words. That
run is **not** the committed one, precisely because it is worse evidence; it is
quoted so the omission is falsifiable rather than asserted. `klt erc` has no
per-tie disclosure for a class a spec leaves out while declaring another
(`ties_disclosure` is top-level and consulted only when `ties[]` is empty), so
this section is the disclosure — and the gap is filed upstream as
[klayout-tools#2541](https://github.com/2AMLogic/klayout-tools/issues/2541);
see [`../vco-layout/PROOF-erc.md`](../vco-layout/PROOF-erc.md) → "Upstream
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
body from the `poly2` role). The flag is passed anyway, so the four blocks'
reports are produced by one command shape and a future device-bearing revision
of this block is covered without anyone remembering to add it.

## Antenna coverage: zero, declared

```json
"pdk": null,
"coverage": { "scope": "antenna", "known": true, "checked": [], "skipped": [ … 117 entries … ] }
```

**`checked: 0, skipped: 117, reason `missing_antenna_pdk` on every one.`**
`klt erc --pdk` offers a real antenna-ratio limit table for `sky130` only;
there is no gf180mcu table, so every per-gate per-level `antenna_ratio` in this
report carries `verdict: "unchecked"` and `antenna_ratio_max: null`. The ratios
are computed and committed; they are graded against nothing.

**"`klt erc` has been run on this block" must never be read as "antenna
checking passed."** Item 11 does not ask for the antenna half — it is the
structural power-delivery item, and antenna limits are klayout-tools#1994's
territory — which is why this run is still item-11 evidence. The distinction
belongs in the record.

## Scope: what this does and does not settle

**Settled:** the ERC half of item 11, for this block, on the klt version CI
pins, reproducibly.

**Not settled:** item 11 itself. The item grades a *set* — a `klt erc` supply
citation **and** an `lvs` citation, the latter being the same report item 4
grades, which must itself pass. This repository runs LVS through the PDK's own
`run_lvs.py` (`lvs-clean/lvs.stdout.log`, `Congratulations! Netlists match.`),
not through `klt lvs`, so **no `klt lvs` envelope exists for any block here**
and `klt signoff` cannot assemble the cited set at all yet.
`signoff/block-manifest.json` therefore still cites nothing, and this record
makes no claim about `signoff/tier-report.json`. That gap is real, it is
separate from anything above, and it is named here rather than papered over.
