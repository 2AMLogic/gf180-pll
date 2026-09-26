# `vco_block` structural power-delivery ERC (T1 checklist item 11, issue #427)

> **Status update (2026-09-26, issue #565): re-run on the klt version CI pins,
> with the n-well tie now actually declared and checked.** Three things about
> the record below have changed, and one has not.
>
> 1. **The `ties[]` omission is gone, because its reason was fixed upstream.**
>    The spec beside this file used to carry a free-text `_ties_omitted` key
>    whose stated reason was klayout-tools#2169 — a tie-extraction bug that
>    turned a correct `ties[]` into a false `erc.supply_short`. That issue
>    closed COMPLETED on 2026-09-20. The spec now declares a real
>    `ties[]` entry for the n-well tap, and this run reports **zero
>    `erc.missing_tie` findings** with the check landing in
>    `erc_coverage.checked` rather than in `inapplicable` — so the
>    fix is verified here, not taken on trust. See "The n-well tie is now
>    declared and checked".
> 2. **The report is no longer bound to a scratch path, and no longer comes
>    from a hand-built `klt`.** `erc-report.json`'s `file` field was
>    `/tmp/i433w/vco_block.gds` — a path no checker can read — and the run came
>    from a from-source `klt` build. Both are fixed: the run is against the
>    committed `layout/evidence/vco-layout/vco_block.gds`, on the released
>    `klayout-tools==0.6.0` wheel `.github/workflows/ci.yml` pins, and
>    `layout/lib/check-layout-status-claims.sh` now fails the build if
>    `provenance.input.content_hash` and the committed GDS ever disagree.
> 3. **The `VDD_VCO` finding is unchanged, and is now adjudicated rather than
>    merely disclosed.** Still 2 islands, and klt 0.6.0 says *where* the second
>    one is (`erc_findings[].islands[]`, klayout-tools#2194) instead of leaving
>    it to be located by hand. Item 11 stays **unmet** for this block — see
>    "Net effect", rewritten against the amended item-11 criterion.
>
> Nothing in this record was resolved by editing the spec's declarations to
> make a finding go away.

> **Status update (2026-09-20, issue #433): the 3-island `VDD_VCO` finding
> below has been investigated to a root cause, and it was two different things
> at once.** One of the three islands was a **real floating supply island** —
> `mirror.py`'s bank 0, its own n-well, its tap band and every pfet source
> rail-stubbed onto it, reachable from `VDD_VCO` by no conductor at all. It is
> fixed. The other was a **false positive** of `klt erc`'s declared-conductor
> model: `vtoi_core.py`'s bottom n-well tap band, ohmically the same node as
> the top band through the single continuous n-well both tap. No geometry was
> changed for that one, and `erc-supply-spec.json` is byte-unchanged.
> `erc-report.json` and `vco_block.gds` beside this file are the **post-fix**
> artifacts and now report **2** islands, not 3; every count, hash and quoted
> JSON below has been updated to match, with the pre-fix value kept alongside
> where it is load-bearing. Full record, evidence and negative control:
> [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md).
>
> **One conclusion in this record is withdrawn by that work** — see the
> correction inline under "Why `ties[]` is omitted" below. In short: this
> record cited `vco_block`'s clean 43/43-net LVS match as standing evidence of
> tie/connectivity correctness. It is not. The PDK's own deck ends with
> `connect_implicit('*')`, which joins nets **by name**; two `VDD_VCO` islands
> touching nothing at all still compare as one net and still print
> `Congratulations! Netlists match.` — which is exactly what was happening
> when this record was written.

This is the first `klt erc` run committed anywhere in this repo. It targets
the T1/bronze design-evidence checklist's eleventh item, *"Power delivery
(structural)"* (klayout-tools#2025,
[`docs/design-evidence-tiers.md`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/design-evidence-tiers.md)),
which is graded from a `klt erc` supply-spec run — a purely structural
question ("is the supply net connected to what it powers"), not an IR-drop or
EM analysis (those stay out of scope for this item, per the item's own text
and klayout-tools#1994).

**Result: one supply net (`GND_VCO`) is clean; the other (`VDD_VCO`) reports
a real, disclosed connectivity finding under this spec's declared stackup.**
Per this repo's own verification discipline (CLAUDE.md: "no claim without a
testbench") and issue #427's own explicit instruction, that finding is
reported here and filed as its own follow-up issue rather than tuned away —
**item 11 is therefore not yet met for this block.** (Still true after issue
#433's fix, for a now-precisely-known reason: see the status update above and
the revised "Net effect" section at the end.)

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | The `klt erc` spec: gate+conductor stackup (Poly2 through Metal5, `active_layer` = Comp for true `poly ∩ diff` gate area), the vias bridging it, the n-well `ties[]` entry, and the two declared supply nets (`VDD_VCO`, `GND_VCO`). Every `stackup`/`vias`/`nets`/`ties` entry carries an inline `_comment` justifying it, per issue #427's acceptance criteria. |
| [`erc-report.json`](erc-report.json) | `klt erc --top vco_block --deck gf180mcu --format json layout/evidence/vco-layout/vco_block.gds layout/evidence/vco-layout/erc-supply-spec.json`, run against the exact `vco_block.gds` committed alongside it — `provenance.input.content_hash` in the report matches that file's own `sha256` (verified below, and now enforced in CI). |

## Provenance

| | |
|---|---|
| Run | 2026-09-26 (issue #565); first written 2026-09-20 (issue #427/#433) |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) — matches every other committed evidence record in this directory. `klt erc` itself needs no PDK install; the `gf180mcuD` reference is for the layer numbers this spec was cross-checked against. |
| `klt` | `0.6.0+gf2d249ab23d4` — the released `klayout-tools==0.6.0` wheel, which is exactly what `.github/workflows/ci.yml`'s "Install klt (klayout-tools) for the signoff tier check" step installs |
| KLayout (Python engine) | `0.30.12` |
| `--deck` | `gf180mcu`, `content_hash` `sha256:8da880a4b42bb27d4710b3647c2157c42b32de22da51b0259c82aa2c1c3441b4` (curated extraction deck, `released: false`) |

**The run is on the version CI pins, and that is checkable, not asserted.**

```
$ klt --version
klt 0.6.0+gf2d249ab23d4
$ uvx --from 'klayout-tools==0.6.0' klt erc --top vco_block --deck gf180mcu --format json \
    layout/evidence/vco-layout/vco_block.gds \
    layout/evidence/vco-layout/erc-supply-spec.json
# byte-identical to the committed erc-report.json, provenance block included
```

Verified this pass: a run through `uvx --from 'klayout-tools==0.6.0'` — a
throwaway environment resolving the pinned release from the index, not this
host's installed tool — produces output byte-identical to the committed
report, provenance included. That is what makes the earlier "why a from-source
build" note below obsolete rather than merely out of date.

```
$ cd layout/evidence/vco-layout && sha256sum vco_block.gds erc-supply-spec.json
8c839b913756d6c31986b9d447bb8317b572a68f1dc13ccf79fffa1b4b5c47f9  vco_block.gds
0603796af00a408a9d26bbdb296c7bb37c1f61a05360a44ecd02ee66138df7d0  erc-supply-spec.json
```

`erc-report.json`'s own `provenance.input.content_hash` is
`sha256:8c839b913756d6c31986b9d447bb8317b572a68f1dc13ccf79fffa1b4b5c47f9` and
its `provenance.spec.content_hash` is
`sha256:0603796af00a408a9d26bbdb296c7bb37c1f61a05360a44ecd02ee66138df7d0` —
**both identical** to the files committed beside it, confirming the report was
run against exactly the committed layout and exactly the committed spec.
`erc-report.json`'s `file` field now reads
`layout/evidence/vco-layout/vco_block.gds` rather than the
`/tmp/i433w/vco_block.gds` scratch path it carried until 2026-09-26, so the
report names an input a reader can actually open. **This pair is now a build
gate, not a promise**: `layout/lib/check-layout-status-claims.sh` recomputes
both hashes on every CI run and fails if either disagrees, so a regenerated
GDS with a stale ERC report beside it cannot survive a push.

The spec hash changed this pass (it was
`sha256:890016efff277faebde42c2c085346cad26b0abefdb75c5550ef01fc22e8cc85`)
because the `_ties_omitted` key was replaced by a real `ties[]` declaration.
The GDS hash did **not** change: no geometry was touched by this work.

<details>
<summary>Superseded provenance note (2026-09-20): why the original run used a from-source <code>klt</code> build</summary>

The `uv tool install`ed `klt` in this environment reported `klt 0.5.0` but its
`erc.py` predated klayout-tools issue #1968 (the `status`/`provenance`
envelope fields) and issue #2036 (`provenance.spec.content_hash`) — running
it produced a JSON report with **no `status` field and no `provenance`
block at all**, even though `docs/cli/erc.md` documented both as present.
`klt` was therefore built fresh from a `git worktree` of `klayout-tools`
`origin/main` @ `d5893304` (later `f2f1d14e` for the #433 regeneration).
Two schema drifts between those two builds were visible in that report and
were disclosed rather than smoothed over: `provenance.input` no longer
carried `"role": "layout"`, and `provenance.klt_version` was the bare
`"0.5.0"` rather than a `+g<sha>` build string.

**All of that is obsolete as of 2026-09-26.** The released 0.6.0 wheel emits a
complete `status`/`provenance` envelope (and `provenance.input.role` is back),
so no source build is needed and none is used. The committed report is
reproducible by `pip install 'klayout-tools==0.6.0'` and one command.

</details>

## Stackup: verified against this repo's own PDK checkout, not assumed

Every `stackup`/`vias` layer number in `erc-supply-spec.json` was
cross-checked directly against two independent sources before being used,
not copied from issue #427's own text on faith:

1. `$PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp` (this repo's
   own pinned PDK checkout, `open_pdks` `c6d73a35f524070e85faff4a6a9eef49553ebc2b`):
   `Poly2 30/0`, `COMP 22/0`, `Contact 33/0`, `Metal1 34/0`, `Via1 35/0`,
   `Metal2 36/0`, `Via2 38/0`, `Metal3 42/0`, `Via3 40/0`, `Metal4 46/0`,
   `Via4 41/0`, `Metal5 81/0`, and the four label/pin-purpose layers
   `Metal1_Label 34/10`, `Metal2_Label 36/10`, `Poly2_Label 30/10`,
   `COMP_Label 22/10`.
2. `klayout-tools`' own curated `decks/gf180mcu.py` layer table (its module
   docstring's layer list) — identical numbers.

Both agree with issue #427's own stated "proven stackup shape" — confirmed,
not assumed.

## `label_layer`: verified against this block's own GDS, not the issue's default guess

Issue #427 names Metal1 `34/10` and Metal5 `81/10` as the *typical*
label layers for gf180mcu supply text, explicitly asking this to be
verified against the actual block rather than assumed. Doing that (via
`klayout.db`, walking every text shape on this GDS's own `(*, 10)` layers)
finds:

- **Metal1 (`34/10`) carries `VDD_VCO` and `GND_VCO` text** — **43 instances
  between the two nets** (`VDD_VCO` 15, `GND_VCO` 28), alongside this block's
  non-supply Metal1 pin text (`NC`, `NOFF`, `NVI`, `S<i>.Y`, `Y<i>`,
  `NB1`/`NB2`, `CLK`). Declared as `stackup[1].label_layer`.

  Counted directly from the committed GDS, array-aware, rather than asserted:

  ```
  $ python3 - <<'PY'
  import collections, klayout.db as db
  ly = db.Layout(); ly.read("layout/evidence/vco-layout/vco_block.gds")
  it = db.RecursiveShapeIterator(ly, ly.top_cell(), ly.layer(34, 10))
  it.shape_flags = db.Shapes.STexts
  n = collections.Counter()
  while not it.at_end():
      if it.shape().is_text(): n[it.shape().text.string] += 1
      it.next()
  print({k: n[k] for k in ("VDD_VCO", "GND_VCO")}, "total", n["VDD_VCO"] + n["GND_VCO"])
  PY
  {'VDD_VCO': 15, 'GND_VCO': 28} total 43
  ```

  (KLayout Python module `0.30.10`; `vco_block.gds`
  `sha256:b1798bf8…3b8ca5b18b`, the hash pinned under "Provenance" above.)
  Three other counting methods agree exactly — a flattened copy of the top
  cell, a non-recursive walk of the top cell's own shapes, and a sum over
  every cell definition in the file — because all 43 supply texts are drawn
  in the top cell `vco_block` itself, with no instancing or arraying to
  disagree about. **Correction (2026-09-20):** this bullet previously read
  "26 instances"; that number was not reproducible by any of the four
  methods above and has been replaced with the measured one. The conclusion
  it supports is unchanged — both supply nets do carry text on `34/10`, and
  Metal2 carries none.
- **Metal2 (`36/10`) carries text too, but never `VDD_VCO`/`GND_VCO`** — only
  bias/control net names (`VCTRL`, `VBP`, `VBN`, `B0`/`B1`/`B2`, plus
  `NC`/`NOFF`/`NVI`/`CLK` again). **Not** declared as a `label_layer`: doing
  so would not help resolve either declared supply net, and declaring it
  anyway would be assuming rather than verifying.
- **Metal5 (`81/0`/`81/10`) is entirely absent from this GDS.** `vco_block.gds`
  only draws layers up to Metal2 — confirmed directly by enumerating the
  file's own `layer_indexes()`: `{21/0, 22/0, 30/0, 31/0, 32/0, 33/0, 34/0,
  34/10, 35/0, 36/0, 36/10, 49/0, 62/0, 110/5}`, nothing at `42/*`, `46/*`,
  or `81/*` at all. Issue #427's "typically Metal1 and Metal5" guess does
  not hold for this specific block — declaring a `label_layer` there would
  have been pure fiction. `metal3`/`metal4`/`metal5` are still declared as
  `stackup` roles (see the spec's own inline comments) purely to keep this
  spec the same portable gf180mcu shape used elsewhere in this fleet — per
  `klt erc`'s own documented convention, "a stackup/vias entry naming a
  layer absent from the given layout is not itself an error."

## The n-well tie is now declared and checked

> **This section replaces "Why `ties[]` is omitted" (2026-09-26, issue #565).**
> The blocker it described is fixed upstream, so the omission it justified is
> no longer justifiable. The original text is kept below, under "Superseded:
> why `ties[]` used to be omitted", because the three standing-in checks it
> cited — and the correction to the first of them — are still the record of
> what this repo knew and when.

`erc-supply-spec.json` now declares the n-well tie outright:

```json
{
  "name": "nwell_vdd_vco",
  "well_layer": "21/0",
  "tap_layer": "22/0",
  "tap_requires": ["32/0"],
  "connect_to": "metal1",
  "net": "VDD_VCO"
}
```

`tap_layer` ∩ `tap_requires` is `Comp (22/0) ∩ Nplus (32/0)` — the boolean
gf180mcu actually draws an n-well tap as, and the thing that distinguishes it
from a pfet source/drain (`Comp ∩ Pplus`). Every one of this block's **six**
merged `Nwell` shapes must hold at least one such tap, wired up to Metal1 and
electrically reaching `VDD_VCO`.

**Result: zero `erc.missing_tie` findings, and the check is *checked*, not
skipped.** From the committed report:

```json
"erc_coverage": {
  "checked": [ "…", "erc.missing_tie:[\"nwell_vdd_vco\"]" ],
  "skipped": [],
  "inapplicable": []
}
```

Three things in that fragment are load-bearing, and each one is a state this
spec could plausibly have landed in instead:

* `erc.missing_tie:["nwell_vdd_vco"]` in **`checked`** — the work was
  performed. Before this change the same identity sat in `inapplicable` with
  reason `no_ties_declared`.
* **`skipped` is empty** — the `tap_requires` narrowing is what keeps this out
  of the `degenerate_tap_declaration` bucket (klayout-tools#2199). A tie whose
  declared tap region is indistinguishable from an ordinary source/drain
  contact is graded as skipped work rather than a passing check, and T1 item 11
  refuses to read a skipped tie as a clean verdict.
* **no `erc.supply_short`** anywhere in `erc_findings` — which is the direct
  observation that klayout-tools#2169 is fixed. That issue's signature was
  exactly a declared tie collapsing a routed design into one island and
  reporting a false short between the two supplies. On klt 0.6.0, declaring
  this tie changes the finding list not at all: the one finding before and
  after is the `VDD_VCO` island count, unrelated to ties.

### Why the p-substrate tie is left undeclared

The spec declares **one** tie, not two. The `GND_VCO`/p-substrate side is not
declared, and that is a measured limitation rather than an oversight:

1. gf180mcu draws **no pwell/tub layer** for a native-substrate NMOS block.
   This GDS's own `layer_indexes()` contain no such layer (the list is
   `{0/0, 21/0, 22/0, 30/0, 31/0, 32/0, 33/0, 34/0, 34/10, 35/0, 36/0, 36/10,
   49/0, 62/0, 110/5}`), so there is nothing to name as `well_layer`.
2. The one form `klt erc` provides for that case is the caller-asserted
   substrate region — `ties[].well_layer: null` plus `ties[].well_boxes`
   (klayout-tools#2255). But an asserted region indistinguishable from the
   whole top-cell extent is graded **degenerate**, because it would make
   `erc.missing_tie` satisfiable by any contact anywhere. A native p-substrate
   *is* the whole top-cell extent.
3. So declaring it would report strictly **less** than leaving it undeclared: a
   skipped tie lands in `erc_coverage.skipped`, which item 11's grader reads as
   `supply_spec_incomplete` — worse than the single checked n-well tie above.

**Negative control** (run on `lock_detector`, the smallest of the four blocks,
against a `well_boxes` assertion covering its exact top-cell extent
`(-0.500, -5.550)`–`(294.300, 98.200)` µm):

```json
"skipped": [ { "id": "erc.missing_tie:[\"psub_vss\"]",
               "reason": "degenerate_well_assertion" } ],
"checked_by_well_assertion": []
```

Measured, not assumed — and the reason `klt erc` itself gives is the one
predicted above. `klt erc` has no per-tie disclosure for a class a spec
deliberately leaves out *while declaring another* (`ties_disclosure` is
top-level and consulted only when `ties[]` is empty), so this section is the
disclosure. Filed upstream as a generic tool gap — see "Upstream friction".

<details>
<summary>Superseded: why <code>ties[]</code> used to be omitted (issue #427's known blocker)</summary>

`klt erc`'s `ties[]` handling had a known upstream bug
([klayout-tools#2169](https://github.com/2AMLogic/klayout-tools/issues/2169))
that collapsed a real routed design into one electrical island and reported a
**false** `erc.supply_short`. Per `klt erc`'s own documented contract
(`docs/cli/erc.md`), omitting `ties[]` entirely means `erc.missing_tie` is
simply **not computed** — not reported as a misleading zero. This spec
omitted it on purpose. **That issue closed COMPLETED on 2026-09-20, and the
fix is verified above**; what follows is the standing evidence this record
cited in its place.

**`erc.missing_tie` was therefore "not computed" for the original run.** The evidence
that stands in for it — this block's own well/substrate-tie connectivity —
already exists, independently, via three other checks:

> **Correction (2026-09-20, issue #433) — the first of the three bullets
> below does not do the job this section asks of it.** A clean net-level LVS
> match is **not** evidence that two same-named metal islands are physically
> connected, in this deck, ever. `general_connections.lvs:100` ends the
> deck's connectivity setup with `connect_implicit('*')`, which joins nets
> **by name**; when this record was written, `VDD_VCO` was two geometrically
> disjoint islands in the deck's *own* extraction (measured directly from the
> committed `.lvsdb` in
> [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md) step 3) and
> still reported 43/43 nets `Match`. The `Match` verdict below is retained
> because it is true and because devices, device parameters and every
> *differently*-named net's topology really are checked by it — but it is
> withdrawn as evidence of same-name connectivity. The second and third
> bullets (`connectivity_report()`, DRC) are unaffected; the first bullet's
> re-derived numbers were also re-measured post-fix and are unchanged
> (65/65 devices, 43/43 nets, 1 circuit pair, all `Match`).

- **`vco_block`'s own committed LVS is a full match**: **65/65 devices
  `Match` (0 `MatchWithWarning`, 0 mismatches), 43/43 nets `Match`**, deck
  verdict `Congratulations! Netlists match.`
  (`layout/evidence/vco-layout/PROOF-381-high-rs-resistor.md`, citing
  `lvs-clean/lvs.stdout.log`).

  Re-derived here from the committed cross-reference database itself, not
  copied from the prose of another document:

  ```
  $ python3 - <<'PY'
  import collections, klayout.db as db
  lvs = db.LayoutVsSchematic(); lvs.read("layout/evidence/vco-layout/lvs-clean/vco_block.lvsdb")
  xref = lvs.xref()
  dev, net = collections.Counter(), collections.Counter()
  for cp in xref.each_circuit_pair():
      for dp in xref.each_device_pair(cp): dev[str(dp.status())] += 1
      for np_ in xref.each_net_pair(cp): net[str(np_.status())] += 1
  print("devices:", dict(dev), " nets:", dict(net))
  PY
  devices: {'Match': 65}  nets: {'Match': 43}

  $ sha256sum layout/evidence/vco-layout/lvs-clean/vco_block.lvsdb
  fdc87ebcad198453c6134a931162f79605be7dc9ebc54a94355baa2c1893902d  layout/evidence/vco-layout/lvs-clean/vco_block.lvsdb
  # was a94c9a8b84e4c2777e666942f4261ec1e55c3f1cb11501ebd0b8a76ac10b4c26 pre-#433;
  # the counts printed above are identical on both databases.

  $ grep -c 'Congratulations! Netlists match.' layout/evidence/vco-layout/lvs-clean/lvs.stdout.log
  1
  ```

  The single circuit pair is `Match` as well. **Correction (2026-09-20):**
  this bullet previously read "`Match` 62, `MatchWithWarning` 3 — the
  already-disclosed `RESISTOR_LVS_MODEL` device-class deviation". That is
  the **pre-fix** state — it is exactly the "Before" column of
  [`PROOF-378-resistor-class-fix.md`](PROOF-378-resistor-class-fix.md)
  ("Devices | 65/65 paired: 62 `Match`, 3 `MatchWithWarning` | 65/65 `Match`
  (**0 warnings**)"), captured before DR-009 changed
  `block.RESISTOR_LVS_MODEL` from `ppolyf_u_1k` to `ppolyf_u`. The currently
  committed `.lvsdb` is the post-fix one and carries no `MatchWithWarning`
  at all, which is also what the cited
  [`PROOF-381-high-rs-resistor.md`](PROOF-381-high-rs-resistor.md) says
  ("65/65 `Match`, 0 warnings, 0 mismatches"). The standing-in argument
  below is strengthened, not weakened, by the correction.

  The PDK's own LVS deck extracts real
  `nplus`/`pplus`/well-tap-aware derived layers — a well/substrate tie wired
  to the wrong net, or not wired at all, would show up as a net-level
  mismatch there. It does not.
- **`vco_block.connectivity_report()` reports 18/18 `PASS`**
  (`PROOF-381-high-rs-resistor.md`) — this repo's own lighter-weight,
  metal-only connectivity probe, which specifically checks (per
  `block.py`'s `CONNECTED_PROBES`) that every n-well tap band reaches the
  block's own n-well ring, and that the outer p-type guard ring reaches
  every sub-block guard ring and bank tap strip.
- **`vco_block` DRC is clean** (`PROOF-381-high-rs-resistor.md`), so no
  spacing/enclosure rule tied to a tap/well structure is violated either.

None of these three is a literal substitute for `erc.missing_tie`'s own
per-well-shape tap-presence check — they are cited here, honestly, as the
best standing evidence this repo currently has for well/substrate-tie
correctness, not as an equivalent check.

**As of 2026-09-26 the n-well half no longer needs a stand-in** — it is
computed, and reports zero. These three remain the only evidence for the
p-substrate half, which is still undeclared for the reason given above.

</details>

## The finding: `VDD_VCO` reported 3 disconnected electrical islands (now 2)

```
$ klt erc --top vco_block --deck gf180mcu --format json \
    layout/evidence/vco-layout/vco_block.gds \
    layout/evidence/vco-layout/erc-supply-spec.json
```

*(The `--deck gf180mcu` flag is new in the 2026-09-26 re-run; the original was
run without it. See "Device bodies and coverage" below for what it changes and
what it does not.)*

`erc_finding_count: 1`, as committed beside this file **after** issue #433's
fix and unchanged by the 2026-09-26 re-run on klt 0.6.0 — which now also says
*where* each island is, via the `islands[]` payload added in
klayout-tools#2194:

```json
{
  "rule": "erc.unconnected_net",
  "description": "declared net 'VDD_VCO' resolves to 2 disconnected electrical islands (expected exactly one)",
  "net": "VDD_VCO",
  "other_net": null,
  "gate_id": null,
  "layer": null,
  "bbox": { "left": -19560, "bottom": -10640, "right": 152200, "top": 173080 },
  "islands": [
    { "bbox": { "left": -19560, "bottom": -10640, "right": 152200, "top": 173080 },
      "layer": "metal1", "shape_count": 17 },
    { "bbox": { "left": -120, "bottom": 18480, "right": 105640, "top": 19320 },
      "layer": "metal1", "shape_count": 1 }
  ]
}
```

Those are database units (`dbu = 0.001` µm), so island 2 is
`(-0.12, 18.48)`–`(105.64, 19.32)` µm, **a single Metal1 shape** — numerically
identical to the island the #433 investigation located by hand and named
`vtoi_core.plan().tap_band_bottom`. The `islands[]` field independently
reproduces a by-hand measurement from six days earlier, and `shape_count: 1`
is the extra fact it adds: the second island is one polygon, i.e. an isolated
tap strip, not a sub-block that failed to strap up. The report also carries
the graded island counts as first-class reporting fields
(`nets[]`, klayout-tools#2497/#2400):

```json
"nets": [
  { "name": "VDD_VCO", "matched_islands": 2, "expected_islands": 1, … },
  { "name": "GND_VCO", "matched_islands": 1, "expected_islands": 1, … }
]
```

`expected_islands: 1` is the *default*, not a declaration this spec makes.
`nets[].islands` (klayout-tools#2400) would let a spec declare an expected
count of 2 and turn this finding clean. **That was considered and deliberately
not done**, for the reason issue #565 states outright: this block's design
intent is one electrical node, so declaring two "deliberately separate
domains" would buy a green row by restating the criterion rather than by
proving continuity. See "Net effect".

The same command read **3** islands when this record was first written; the
third — `mirror.py`'s bank 0 — was a real floating supply island and is
fixed. The rest of this section is the original 3-island analysis, kept as
written with its own errors corrected in place below, because it is what the
follow-up investigation started from.

`status: "violations"` as a result. **`GND_VCO` reports zero findings** —
it resolves to exactly one electrical island under this same stackup, and no
`erc.supply_short` names either net.

Per this command's own connectivity model (`docs/cli/erc.md`: "no device
recognition is registered... scoped down to only the layers this spec
declares"), `klt erc`'s three `VDD_VCO` islands are traced purely through
`poly2`/`metal1`/`metal2`/`contact`/`via1` (this block draws nothing above
Metal2). Their Metal1 footprints (`klayout.db.LayoutToNetlist.shapes_of_net`,
µm, `dbu=0.001`):

| Island | Metal1 bbox (µm) | Notes |
|---|---|---|
| 1 (main) | `(-19.56, -10.64)` – `(152.20, 173.08)` | Spans nearly the entire block footprint — the guard ring, and every other supply-labelled Metal1 region this run *does* connect. |
| 2 | `(-0.12, 18.48)` – `(105.64, 19.32)` | A single, narrow (~0.84 µm tall) horizontal Metal1 strip. **Identified since:** `vtoi_core.plan().tap_band_bottom`. Still present post-#433 — a false positive, see below. |
| 3 | `(-0.12, 84.28)` – `(91.92, 90.44)` | A second, wider (~6.2 µm tall) horizontal Metal1 strip. **Identified since:** `mirror.plan().banks[0].tap_band` and everything rail-stubbed onto it. A real floating island; fixed by #433, gone from the committed report. |

~~**This directly contradicts the LVS result cited above**~~ — **withdrawn
(2026-09-20, issue #433): there was never a contradiction to explain.** The
PDK deck's `connect_implicit('*')` joins same-named nets, so a 43/43-net
`Match` says nothing about whether two `VDD_VCO` metal islands touch. Measured
on the very `.lvsdb` this record cites, the deck's *own* extraction of
`VDD_VCO` was two geometrically disjoint islands, one of them exactly island 3
above. See [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md) step 3.

**Correction (2026-09-20, issue #433) to the n-well reasoning that followed.**
This record stated that "the n-well (`21/0`) shapes underneath islands 2 and 3
are **not** part of the same merged n-well polygon as island 1's own n-well",
citing the outer guard-ring well `(-19.94, -11.02)`–`(152.58, 173.46)` as
"island 1's own n-well". That comparison was against the wrong well. Island 1
is not confined to the guard-ring well — it is the whole trunk-fed network,
and it reaches **into** the vtoi well `(-0.50, 18.10)`–`(106.02, 44.50)`
through `vtoi_core`'s *top* tap band. The six merged n-well polygons are real
and correctly counted; the conclusion drawn from them was not. Re-measured:

* **Island 2 and island 1 tap the same merged n-well polygon**
  (`(-0.50, 18.10)`–`(106.02, 44.50)`, both `vtoi_core` bands) — so continuous
  n-well conduction *does* explain island 2, and `vtoi_core.py`'s own
  `build()` says as much in a comment that predates any of this.
* **Island 3 sits alone** in `(-0.50, 80.22)`–`(92.30, 90.82)`, which nothing
  else on `VDD_VCO` touches — a real open, now fixed.

The "not yet tried" `nplus`/`pplus`-aware reconstruction this record named as
the natural next step was done in `PROOF-433-vdd-island-fix.md`, and is what
separated the two cases.

**Not resolved here, on purpose.** Per issue #427's own instruction ("If a
supply genuinely resolves to more than one electrical island, that is a real
finding... file it as its own issue rather than tuning the spec until it
passes"), this finding was reported as found and handed to a dedicated
follow-up issue rather than investigated to a root cause in this record —
see "Follow-up" below. That follow-up (#433) has since landed; the spec was
never tuned, and is byte-unchanged.

## Device bodies and coverage (both new in the 2026-09-26 re-run)

**Device bodies.** The 2026-09-26 run adds `--deck gf180mcu`, which resolves
the curated extraction deck `klt extract`/`klt lvs` already use and carves that
deck's own device-body markers out of the matching conductor role
(klayout-tools#2183/#2204). It matters for this block specifically, because
this block draws **poly resistors on the gate-role layer**: without the
carve-out, a resistor body is just poly2 conductor, and a resistor string reads
as a dead short between whatever it spans. The report records exactly what was
subtracted, so the claim is auditable rather than implicit:

```json
"provenance": { "devices": [
  { "name": "ppolyf_u_1k", "body_layer": "30/0", "on": "poly2",
    "body_area_um2": 71.6, "source": "deck", "superseded_by": null } ] }
```

71.6 µm² of `ppolyf_u_1k` body on `poly2`, auto-detected (`source: "deck"`)
rather than hand-transcribed — which is the point, since a mis-transcribed
marker layer subtracts nothing and its only signal is a zero area.

**It changes no verdict, and it does change the model.** Both halves matter:

* *No verdict moved.* The finding list is the same one finding, `gate_count` is
  28 either way, and both declared supplies' island counts
  (`VDD_VCO` 2, `GND_VCO` 1) are identical with and without the flag. So the
  `VDD_VCO` finding is **not** an artifact of how the conductor model treats
  this block's resistors — worth knowing, since resistor bodies on the
  gate-role layer were the obvious candidate explanation.
* *A false short in the model is gone.* Without the carve-out, `gates[0]` was
  the net `"GND_VCO,NC,NOFF,NVI"` — four labels on one gate net, because the
  un-carved resistor bodies bridged them. With it, `gates[0].net` is plain
  `"GND_VCO"`. That bridging was never reported as a finding (`NC`/`NOFF`/`NVI`
  are not declared `nets[]` entries, and `GND_VCO` resolved to one island
  either way), which is exactly why it is worth naming: the un-carved model was
  quietly wrong in a way no verdict in the old report showed. The per-level
  areas move with it — gate0's cumulative Metal2 antenna ratio is 647.0 in the
  committed report where the pre-deck run read 702.5.

**Coverage.** The spec's own reach over the layout is now disclosed rather than
assumed (klayout-tools#2389):

```json
"erc_coverage": { "layers_in_stream_without_declaration": [], "nothing_checked": false }
```

**Empty** — every layer this GDS draws is accounted for by the spec's
`stackup`/`vias`/`ties` declarations or by the `--deck gf180mcu` device
markers. Before this pass the same field read `["0/0", "21/0", "31/0", "32/0",
"36/10", "49/0", "62/0", "110/5"]`: the n-well and both implants (now named by
the tie), Metal2_Label, and the three resistor markers `SAB (49/0)`,
`resistor (62/0)` and `res_mk (110/5)` (now named by the deck). So a reader no
longer has to work out what a clean supply read did and did not look at.

**The antenna half of `klt erc` has still never run in this repository, and
this record does not let that hide.** From the committed report:

```json
"pdk": null,
"coverage": { "scope": "antenna", "checked": [], "skipped": [ … 140 entries … ] }
```

**`checked: 0, skipped: 140, reason `missing_antenna_pdk` on every one of
them.`** `klt erc --pdk` currently offers a real antenna-ratio limit table for
`sky130` only; there is no gf180mcu table, so every per-gate per-level
`antenna_ratio` in this report carries `verdict: "unchecked"` and
`antenna_ratio_max: null`. The ratios themselves are computed and committed
(gate0's cumulative Metal2 ratio is 647.0, for instance) — they are simply
graded against nothing. **"`klt erc` has been run on this block" must therefore
never be read as "antenna checking passed".** Item 11 does not ask for the
antenna half (it is the structural-power-delivery item; antenna limits are
klayout-tools#1994's territory), which is why this run is still item-11
evidence — but the distinction belongs in the record, not in a reader's
assumptions.

## Follow-up

- **[#433](https://github.com/2AMLogic/gf180-pll/issues/433)** (this repo):
  the `VDD_VCO` 3-island finding above, with the full reproduction command
  and this record's own investigation notes, for whoever picks up the
  root-cause work. **Resolved** —
  [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md). One of the
  three islands was a real floating supply island (fixed); one was a false
  positive of the metal-only connectivity model (no geometry changed, no spec
  changed).
- **[klayout-tools#2180](https://github.com/2AMLogic/klayout-tools/issues/2180)**
  (friction, filed per this repo's own CLAUDE.md "friction protocol"):
  `klt erc`'s connectivity model, by design, has no way to represent a
  supply net's real electrical continuity when that continuity depends
  partly on continuous diffusion/well silicon rather than a declared
  conductor stackup — and the one spec mechanism that is well-aware
  (`ties[]`) is itself documented broken for real routed designs
  (klayout-tools#2169). There is currently no working way to get a
  trustworthy multi-island verdict, via `klt erc` alone, for a full-custom
  analog block whose supply routing legitimately relies on well/diffusion
  continuity — described generically, since this is a tool-capability gap,
  not a fact about this one design.

  **Closed COMPLETED 2026-09-20 — as a documented caveat, not a model
  change.** The upstream T1 checklist now instructs a reader not to treat a
  multi-island `erc.unconnected_net` on a guard-ring/well-tap-strapped supply
  as a confirmed power-delivery defect on its own, but to cross-check it
  against an independent device-aware LVS run first — and to confirm that
  deck's own connectivity setup does not join nets by label alone (a bare
  `connect_implicit('*')`). Both halves of that cross-check are performed for
  this block; see "Net effect", below. `klt erc`'s island count itself is
  unchanged, which is why the finding is still reported and item 11 is still
  unmet.

## Upstream friction (new this pass, 2026-09-26)

Filed generically at `2AMLogic/klayout-tools` per CLAUDE.md's friction
protocol — described as tool gaps, not as facts about this design:

- **A `ties[]` class a spec cannot express has no disclosure path when the
  spec declares another class.** `ties_disclosure` is a top-level key and its
  reason is consulted only when `ties[]` is empty, so a spec that declares its
  n-well tie and genuinely cannot declare its substrate tie renders
  identically to one that never considered the substrate at all. This block is
  that case (see "Why the p-substrate tie is left undeclared"); the upstream
  checklist already names the shape for the pre-#2255 native-substrate case
  ("a `ties_disclosure` describes only *undeclared* work, so a design that
  declared its n-well tie could not even disclose the missing substrate half")
  and #2255 closed only the sub-case where an asserted region is
  non-degenerate.
- **Well-side class selection has no caller-assertion counterpart.**
  `ties[].well_requires`/`well_excludes` (klayout-tools#2339) select whole
  drawn well shapes by interaction with a *marker layer*; a stream with two
  deliberately differently-biased well classes and no layer that separates
  them cannot use it, and there is no `well_boxes`-style literal-geometry
  escape hatch on the well-selection side the way `ties[].tap_boxes`
  (klayout-tools#2234) is one on the tap side. `pfd_cp` is that case — see
  [`../pfd-cp-layout/PROOF-erc.md`](../pfd-cp-layout/PROOF-erc.md).

## Net effect on T1 checklist item 11 (structural power delivery)

**Not met for `vco_block`, honestly.** `GND_VCO` is clean; `VDD_VCO`
resolves to 3 islands under this spec and is a disclosed, filed, unresolved
finding — the pass condition ("every declared supply resolves to exactly
one electrical island") is not satisfied for both declared supplies. This
record is nonetheless the first `klt erc` supply spec and report ever
committed in this repo, and (per issue #427's own escape hatch) the correct
way to leave a genuine multi-island finding: disclosed, reproducible, and
handed to its own issue rather than tuned away.

**Revised (2026-09-20, issue #433): still not met — now for one precisely
known reason rather than an unexplained one.** `VDD_VCO` resolves to **2**
islands under this spec, not 3. The remaining island is
`vtoi_core.plan().tap_band_bottom`, which is ohmically the same node as the
band the trunk feeds through the single continuous n-well both tap — a fact
the PDK's own LVS deck models (`connect(nwell_con, ntap)`) and this spec
cannot, because `klt erc` traces only the conductors a `stackup` declares and
the one well-aware spec mechanism (`ties[]`) is upstream-broken for routed
designs (klayout-tools#2169). Under *any* model that counts the n-well,
`VDD_VCO` is exactly one electrical island — measured, post-fix, directly from
the PDK deck's own extracted database
([`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md) "Results").

So item 11's pass condition is unmet **only** under the metal-only model, and
that is now a tool-capability statement with a filed upstream issue
(klayout-tools#2180) rather than an open question about this layout.
Re-evaluate item 11 when that issue — or klayout-tools#2169 — lands a way to
declare well/diffusion continuity in a supply spec. Nothing here should be
resolved by editing `erc-supply-spec.json`.

### Revised again (2026-09-26, issue #565): adjudicated against the amended criterion, and still unmet

Two of the three reasons the paragraph above gives for re-evaluating have
since resolved, so the verdict needs restating rather than re-citing.

**What the amended criterion actually asks.** klayout-tools#2169 and #2180
both closed COMPLETED on 2026-09-20. #2169 shipped a fix (verified above: the
tie is declared and checked, with no false `erc.supply_short`). #2180 closed as
a *documented caveat*: a multi-island `erc.unconnected_net` on a
guard-ring/well-tap-strapped supply is not to be read as a confirmed
power-delivery defect on its own — the reader must cross-check it against an
independent, **device-aware** LVS run, and must confirm that deck's own
connectivity setup does not join nets by label alone (e.g. via a bare
`connect_implicit('*')`). So the question is no longer "is this a defect?" but
"has the required cross-check been done, and does it exonerate the layout?"

**Both halves of that cross-check are already on record, in this directory.**

| The caveat asks | Answer for `vco_block` | Where |
|---|---|---|
| An independent, device-aware LVS run's own island count for the supply | **1 geometric island** (post-#433; was 2 before the fix), measured by merging every shape of the deck's own extracted `VDD_VCO` net | [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md), "Results" row *"`VDD_VCO`, PDK deck's own extraction"* — verdict **PASS** |
| That the deck does not join nets by label alone | **Confirmed it does, and that the cross-check does not rely on it.** `general_connections.lvs:100` ends the gf180mcu deck's setup with `connect_implicit('*')`, so a `Match` verdict is *not* evidence of same-name connectivity — this record says so in two places already. The island count above is therefore taken from the deck's **geometry**, not from its `Match`: the union of extracted-net shapes, merged, counted. That measurement is immune to `connect_implicit`, which joins nets, not polygons. | [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md), step 3 (which reproduces the deck line) and "Results" |
| That the mechanism is real rather than assumed | `connect(nwell_con, ntap)` in the same deck: the n-well **is** a conductor in the PDK's own model, and island 2 is `vtoi_core`'s bottom tap band, which taps the same merged n-well polygon `(-0.50, 18.10)`–`(106.02, 44.50)` µm that island 1 reaches through `vtoi_core`'s *top* band. There is a regression test on exactly this: `AssembledBlockVddIslandTests`' well-aware variant (`ntap = ((comp − poly2) ∧ nplus) ∧ nwell`, `connect(nwell, ntap)`) asserts every `VDD_VCO` tap band is one node, and **fails** under a monkey-patched pre-#433 layout. | `layout/tests/test_vco_layout.py`; [`PROOF-433-vdd-island-fix.md`](PROOF-433-vdd-island-fix.md), "The regression gates added" |

**Adjudication: the remaining `VDD_VCO` island is the klayout-tools#2180
well/diffusion false positive, not a real power-delivery defect.** It is the
same class as, and physically adjacent to, the island #433 proved *was* real —
which is why this is stated as a graded cross-check rather than as a hunch. The
two were separated by measurement, one was fixed in geometry, and this one was
not, because there is nothing wrong with it.

**And item 11 is still `unmet` for this block, deliberately.** The item's pass
condition is what `klt erc` computes, not what a reader concludes from a
cross-check: `erc.unconnected_net` naming a declared supply renders
`supply_not_continuous`, full stop. Three routes to a green row were available
this pass and all three were rejected:

1. **Declare `nets[].islands: 2`** (klayout-tools#2400). Turns the finding
   clean by declaring two "deliberately separate domains". Rejected: this
   block's design intent is *one* node reached partly through well silicon, not
   two independent domains. The declaration would be false in substance while
   true in arithmetic.
2. **Declare the n-well as a `stackup` conductor role.** Would make the island
   count 1 by modelling the ohmic path directly. Rejected: `stackup` is
   fabrication-ordered and `stackup[0]` must be the gate role, so an n-well
   entry distorts every gate's antenna accumulation to buy one connectivity
   answer — and it would silently re-grade a resistive silicon path as a
   routing conductor.
3. **Narrow the declaration** — drop `VDD_VCO` from `nets[]`, or scope the
   stackup so the second island falls outside it. Rejected outright; it is the
   thing issue #427 and issue #565 both name as the wrong answer.

An unmet item with current, reproducible evidence and a precisely named cause
is the deliverable here. A green row obtained by restating the criterion is
not. **The named gap, in one sentence:** `klt erc` cannot model a supply whose
continuity runs partly through well silicon, the upstream issue for that
(klayout-tools#2180) closed as a reader-facing caveat rather than a model
change, and so a full-custom analog block that is *correct* — as this one is
shown to be by the PDK deck's own geometry — cannot reach item 11's ERC half by
any honest declaration available today.

### Scope note: the ERC half is not the whole item

Item 11 grades a **set**: a `klt erc` supply-spec citation *and* an `lvs`
citation, the latter being the same report item 4 grades, which must itself
pass. This repository runs LVS through the PDK's own `run_lvs.py` (see
`lvs-clean/lvs.stdout.log`), not through `klt lvs`, so **no `klt lvs` envelope
exists for any block here** and `klt signoff` cannot assemble item 11's cited
set at all yet — for this block or the other three. That is a separate gap from
the one adjudicated above, it is not what this record claims to close, and
`signoff/block-manifest.json` is correspondingly left citing nothing.
