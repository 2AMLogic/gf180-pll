# `vco_block` structural power-delivery ERC (T1 checklist item 11, issue #427)

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
**item 11 is therefore not yet met for this block.**

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | The `klt erc` spec: gate+conductor stackup (Poly2 through Metal5, `active_layer` = Comp for true `poly ∩ diff` gate area), the vias bridging it, and the two declared supply nets (`VDD_VCO`, `GND_VCO`). Every `stackup`/`vias`/`nets` entry carries an inline `_comment` justifying it, per issue #427's acceptance criteria. **No `ties` array is declared** — see "Why `ties[]` is omitted" below. |
| [`erc-report.json`](erc-report.json) | `klt erc --top vco_block --format json layout/evidence/vco-layout/vco_block.gds layout/evidence/vco-layout/erc-supply-spec.json`, run against the exact `vco_block.gds` committed alongside it — `provenance.input.content_hash` in the report matches that file's own `sha256` (verified below). |

## Provenance

| | |
|---|---|
| Run | 2026-09-20 |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) — matches every other committed evidence record in this directory |
| `klt` | `0.5.0+gd5893304afc2` (`klayout-tools` `origin/main` @ `d5893304`) |
| KLayout (Python engine) | `0.30.12` |

**Why a from-source `klt` build, not the locally installed `uv tool` one.**
The `uv tool install`ed `klt` in this environment reports `klt 0.5.0` but its
`erc.py` predates klayout-tools issue #1968 (the `status`/`provenance`
envelope fields) and issue #2036 (`provenance.spec.content_hash`) — running
it produces a JSON report with **no `status` field and no `provenance`
block at all**, even though `docs/cli/erc.md` (as published on
`klayout-tools` `main`) documents both as present. This is a real
version-label/behavior mismatch in the distributed package this repo's
agents otherwise rely on by default, flagged here rather than silently
worked around. Built `klt` fresh from a `git worktree` of `klayout-tools`
`origin/main` @ `d5893304` instead (`pip install <worktree>` into a clean
venv) to get a schema-complete run this document's own claims (the
input-hash match below) actually depend on. Reproducible by anyone: check
out that commit and `pip install .`.

```
$ sha256sum layout/evidence/vco-layout/vco_block.gds
b1798bf89c1eafa1a26702d7614edcd62bfadb0f561e1c9faacd9b3b8ca5b18b  layout/evidence/vco-layout/vco_block.gds
```

`erc-report.json`'s own `provenance.input.content_hash` is
`sha256:b1798bf89c1eafa1a26702d7614edcd62bfadb0f561e1c9faacd9b3b8ca5b18b` —
**identical**, confirming the committed report was run against exactly the
committed GDS, not a stale copy. `provenance.spec.content_hash` likewise
matches `erc-supply-spec.json`'s own hash
(`sha256:890016efff277faebde42c2c085346cad26b0abefdb75c5550ef01fc22e8cc85`).

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

## Why `ties[]` is omitted (issue #427's known blocker)

`klt erc`'s `ties[]` handling has a known upstream bug
([klayout-tools#2169](https://github.com/2AMLogic/klayout-tools/issues/2169))
that collapses a real routed design into one electrical island and reports a
**false** `erc.supply_short`. Per `klt erc`'s own documented contract
(`docs/cli/erc.md`), omitting `ties[]` entirely means `erc.missing_tie` is
simply **not computed** — not reported as a misleading zero. This spec
omits it on purpose.

**`erc.missing_tie` is therefore "not computed" for this run.** The evidence
that stands in for it — this block's own well/substrate-tie connectivity —
already exists, independently, via three other checks:

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
  a94c9a8b84e4c2777e666942f4261ec1e55c3f1cb11501ebd0b8a76ac10b4c26  layout/evidence/vco-layout/lvs-clean/vco_block.lvsdb

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

## The finding: `VDD_VCO` reports 3 disconnected electrical islands

```
$ klt erc --top vco_block --format json \
    layout/evidence/vco-layout/vco_block.gds \
    layout/evidence/vco-layout/erc-supply-spec.json
```

`erc_finding_count: 1`:

```json
{
  "rule": "erc.unconnected_net",
  "description": "declared net 'VDD_VCO' resolves to 3 disconnected electrical islands (expected exactly one)",
  "net": "VDD_VCO",
  "other_net": null,
  "gate_id": null,
  "layer": null,
  "bbox": null
}
```

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
| 2 | `(-0.12, 18.48)` – `(105.64, 19.32)` | A single, narrow (~0.84 µm tall) horizontal Metal1 strip. |
| 3 | `(-0.12, 84.28)` – `(91.92, 90.44)` | A second, wider (~6.2 µm tall) horizontal Metal1 strip. |

**This directly contradicts the LVS result cited above** (a clean, 43/43-net
match) — the same design, checked by two different tools at two different
levels of device awareness, disagrees on whether `VDD_VCO` is one node. One
concrete, checked data point on the "why": the n-well (`21/0`) shapes
underneath islands 2 and 3 are **not** part of the same merged n-well
polygon as island 1's own n-well — `klayout.db.Region.merged()` returns six
separate n-well polygons for this GDS, and the islands above each sit inside
a *different* one of those six (bboxes `(-0.50, 18.10)`–`(106.02, 44.50)`
and `(-0.50, 80.22)`–`(92.30, 90.82)` respectively, vs. the outer guard-ring
well's own `(-19.94, -11.02)`–`(152.58, 173.46)`) — so simple continuous-well
conduction does not explain the discrepancy either, at least not without a
mechanism this record did not have the tooling to isolate further (`klt
erc` itself has no device recognition to check this properly; a from-scratch
implant-aware reconstruction is exactly the kind of investigation
`layout/evidence/vco-layout/PROOF-368-rootcause.md` already did for a
different short in this same block).

**Not resolved here, on purpose.** Per issue #427's own instruction ("If a
supply genuinely resolves to more than one electrical island, that is a real
finding... file it as its own issue rather than tuning the spec until it
passes"), this finding is reported as found and handed to a dedicated
follow-up issue rather than investigated to a root cause in this record —
see "Follow-up" below.

## Follow-up

- **[#433](https://github.com/2AMLogic/gf180-pll/issues/433)** (this repo):
  the `VDD_VCO` 3-island finding above, with the full reproduction command
  and this record's own investigation notes, for whoever picks up the
  root-cause work.
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

## Net effect on T1 checklist item 11 (structural power delivery)

**Not met for `vco_block`, honestly.** `GND_VCO` is clean; `VDD_VCO`
resolves to 3 islands under this spec and is a disclosed, filed, unresolved
finding — the pass condition ("every declared supply resolves to exactly
one electrical island") is not satisfied for both declared supplies. This
record is nonetheless the first `klt erc` supply spec and report ever
committed in this repo, and (per issue #427's own escape hatch) the correct
way to leave a genuine multi-island finding: disclosed, reproducible, and
handed to its own issue rather than tuned away.
