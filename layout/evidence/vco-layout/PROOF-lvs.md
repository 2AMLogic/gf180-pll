# `vco_block` LVS — reference netlist landed, first real run finds a genuine short (issue #367)

This is **not** an LVS-clean record. It documents the first-ever attempt at
block-level LVS for the VCO (`vco_block.gds` vs a new, independently-derived
`vco_block.spice` reference), what that attempt got right (the reference
netlist itself, two disclosed device-class deviations, and a labelling fix
that was a real prerequisite), and a genuine, reproducible connectivity bug
the attempt surfaced in the assembled block's own geometry — present on
`main` before this issue, invisible to DRC and to
`block.connectivity_report()`'s own simplified metal-only extraction, and
not fixed here. Per this repo's own verification discipline: no claim
without a testbench, and no claim beyond what the testbench actually shows.

## Provenance

| | |
|---|---|
| Attempted | 2026-09-10 |
| Branch point | `origin/main` @ `78fa1b3` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.9` |
| KLayout (pip wheel, geometry generation) | `0.30.10` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D`, `--lvs_sub=GND_VCO` |

**KLayout version deviates from the `0.28.16` pin** (`KNOWN_GOOD_KLAYOUT_VERSION`
in `layout/harness/env.py`), same disclosed deviation
`divider-chain-layout/PROOF.md` records (`0.30.9`/`0.30.10` was the only
toolchain available in this environment). `layout/README.md`'s "The two
KLayouts" section names the specific risk this pin protects against — a
newer KLayout reporting a **false** mismatch on an otherwise LVS-clean
layout. That risk is **not** what is being reported below: the finding here
is a real device/net-count shortfall reproduced identically across three
independent runs (default flags, an alternate `--lvs_sub` name, and a
patched deck with `connect_implicit('*')` disabled — see "Ruling out two
suspects" below), not a topology-only near-miss the false-mismatch bug
produces.

## What this increment adds (real, and correct on its own terms)

* **`layout/pll_top/vco/block.py:reference_netlist()`** — a flat, independently-
  derived LVS reference for `vco_block`, built directly from `devices.py`'s
  own tables (ring `STAGE_FETS` x5, `BUFFER_STAGES`, `MIRROR_CASCADES`,
  `MIRROR_MUXES`, `MIRROR_LOADS`, `MIRROR_INVERTERS`, `BIAS_RESISTORS`,
  `VTOI_ALL_FETS`) — the same "flattened re-expression of the schematic,
  traced device-by-device" discipline `divider_chain.py`'s own
  `reference_netlist()` established. 65 devices: 31 `pfet_03v3` + 31
  `nfet_03v3` + 3 poly resistors.
* **A real, pre-existing net-labelling gap, fixed.** `layout/pll_top/vco/
  primitives.py`'s `Canvas` subclass labelled every net on the Metal1/Metal2
  **drawing** datatype (34/0, 36/0) via the shared `_canvas.Canvas`'s default
  `PIN_LAYER`, never overriding it to the **label/pin purpose** datatype
  (34/10, 36/10) gf180mcu's own LVS deck actually reads names from
  (`general_connections.lvs`: `connect(metal1_con, metal1_label)` /
  `connect(metal2_con, metal2_label)`) — the same citation
  `divider_chain/devgen.py` and `pfd_cp/devgen.py` already use for their own
  `PIN_LAYER = "metal1_label"`. Every net this package has ever laballed
  (five PRs' worth) was therefore extracted as an anonymous node under a
  real LVS run; this was never caught because `block.connectivity_report()`
  reads labels from the drawing layer directly (its own simplified metal-only
  KLayout API extraction, not gf180mcu's deck). Fixed: `primitives.py` now
  defines `"metal1_label": (34, 10)` / `"metal2_label": (36, 10)` and sets
  `PIN_LAYER = "metal1_label"`; the six call sites that pinned a net directly
  on Metal2 (`mirror.py`, `vtoi_core.py`, `block.py`'s own boundary pins) now
  pass `layer="metal2_label"` explicitly. `ring.py` additionally now labels
  its five internal ring-chain nets `Y1`..`Y5` (previously only
  `stage.py`'s own per-instance `"S<i>.Y"` label existed, with no
  counterpart in any reference netlist). **Confirmed not to change DRC or
  `connectivity_report()`'s own verdict** (both re-run clean after the
  change — see "Not a vacuous pass" below); it is a pure labelling change
  with zero drawn-geometry deltas (`git diff` on `ring.py`/`mirror.py`/
  `vtoi_core.py`/`primitives.py` touches only `pin()`/`LAYER`/`PIN_LAYER`
  arguments).
* **Two disclosed device-class deviations from `design/netlist/vco.spice`**,
  per this issue's own "disclose, don't silently drop" instruction:
  * `RESISTOR_LVS_MODEL = "ppolyf_u_1k"`, not the schematic's own
    `ppolyf_u_3k`. Verified directly against the PDK, not assumed: `run_lvs.py`'s
    `generate_klayout_switches()` hardcodes `switches["poly_res"] = "1k"` for
    **every** `--variant` (A/B/C/D) with no CLI override, and
    `rule_decks/res_extraction.lvs`'s own `case POLY_RES` only reaches its
    `'3k'` branch when the Ruby-level `$poly_res` variable is literally
    `'3k'` — unreachable from this repo's flow. This is a real,
    reproducible **foundry-deck** limitation (`open_pdks`'s `run_lvs.py`,
    not `klt`), confirmed empirically too: the deck's own log
    (`lvs-attempt/lvs.stdout.log`) shows `Extracting PPOLYF_U_1K device`, and
    the extracted netlist's three resistors (`R$77`/`R$78`/`R$79`) all carry
    class `ppolyf_u` at 1960/11550/11550 ohms (1000 ohm/sq x L/W), matching
    `ppolyf_u_1k`, never `ppolyf_u_3k`.
  * `DECAP_LVS_MODEL = "cap_nmos_03v3"` is **not emitted** by
    `reference_netlist()` at all. `ring.py`'s own module docstring already
    states the carried-forward 22 pF decap pair is drawn as two
    boundary-layer marker rectangles (GDS layer (0, 0), a non-DRC-referenced
    marker — confirmed here it is *also* not referenced by the LVS deck:
    `layers_definitions.lvs`'s only mention of `(0, 0)` is the dead
    `pr_bndry` variable, never `connect()`-ed to anything), not real
    `cap_nmos_03v3` device geometry — "turning it into real device geometry
    is follow-up-issue scope, not implied by 'carried forward unchanged'".
    `gf180mcu`'s own deck *does* recognize the class unconditionally when
    real geometry is present (`libs.tech/klayout/lvs/rule_decks/
    moscap_extraction.lvs`'s `cap_nmos_03v3` device, unlike the poly
    resistors, is not variant-gated) — confirmed by the deck's own log
    (`Extracting cap_nmos_03v3 device`) — so the class is not itself a
    deck limitation; the layout simply draws no such device yet, and this
    reference does not claim otherwise.

## The finding: `vco_block`'s own assembled geometry has a real, unexplained short

```bash
python3 -m layout.pll_top.vco.block --outdir <workdir>   # writes vco_block.gds
python3 -c "from layout.pll_top.vco import block; \
  open('<workdir>/vco_block.spice','w').write(block.reference_netlist())"
python3 layout/run_pv.py lvs <workdir>/vco_block.gds <workdir>/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `vco_block` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** (re-confirmed after the labelling fix above) |
| `vco_block` LVS | match | `ERROR : Netlists don't match` | **MISMATCH** |

Artifacts: `lvs-attempt/lvs.stdout.log` (full deck log), `lvs-attempt/
vco_block.cir` (extracted netlist), `lvs-attempt/vco_block.lvsdb` (LVS
database), `lvs-attempt/vco_block.spice` (the committed reference —
identical to `reference_netlist()`'s own output).

**The extracted layout netlist has 39 devices / 20 nets; the reference has
65 devices / 43 nets** (18 `pfet_03v3` + 18 `nfet_03v3` + 3 resistors
extracted, vs. 31 + 31 + 3 expected — the resistor count and class match
exactly; 13 pfets and 13 nfets are missing from the layout side). One
extracted net alone carries 43 device terminals and this alias list
(`vco_block.cir`'s own text, `SPICE_WITH_NET_NAMES=true`):

```
BUF1.NB1|BUF2.NB2|BUF3.CLK|CLK|GND_VCO|S1.Y|S2.Y|S3.Y|S4.Y|S5.Y|VBN|VBP0|VDD_VCO|Y1|Y2|Y3|Y4|Y5|Y5_CLK_IN
```

That is: the **ring's own chain nets** (`Y1`..`Y5`, and `stage.py`'s own
per-instance `S1.Y`..`S5.Y` labels on the same physical pads), the
**buffer's** internal and output nodes (`BUF1.NB1`, `BUF2.NB2`, `BUF3.CLK`,
`CLK`), the **mirror's** own output pair (`VBN`, `VBP0`), and — critically —
`VDD_VCO` and `GND_VCO` **as aliases on this one net**, even though the
extracted netlist *also* has a separate, ordinary `VDD_VCO` net (18
terminals) and a separate, ordinary `GND_VCO` net (36 terminals) elsewhere in
the same circuit. Two same-named, physically distinct nets in one extracted
circuit means at least one `VDD_VCO`- or `GND_VCO`-labelled point in this
design is **not** actually connected to the real supply/ground network it is
labelled as — some real conductor ties it instead to this
ring/buffer/mirror-output cluster. The cross-reference (`db.LayoutVsSchematic
.xref()`, queried directly against the committed `.lvsdb`) confirms this is
the *pre-comparison* extracted topology (`netlist_a()`: 20 nets / 39 devices),
not a comparison-time artifact.

**This is not attributable to anything this issue changed.** `git diff`
against `origin/main` for every file this issue touches
(`ring.py`/`mirror.py`/`vtoi_core.py`/`primitives.py`) shows label-layer and
`pin()`-argument changes only — zero drawn-geometry deltas (`rect()`/
`h_wire()`/`v_wire()`/`via1_stack()`/`m2_wire()` call sites are byte-for-byte
unchanged). The very first LVS attempt against unmodified `main` geometry
(before any of this issue's labelling changes were applied, when almost no
net had a deck-readable name at all) already showed the identical symptom:
33 extracted devices under a single named port (`GND_VCO`, from
`--lvs_sub` alone) — consistent with the same underlying merge, simply
invisible by name until this issue's labelling fix. The merge is a property
of the assembled block's own geometry, landed across #305/#313/#314/#316/
#293/#324/#336, that no DRC run or the metal-only `connectivity_report()`
(which never claimed to model comp/poly/well connectivity — see its own
docstring) was positioned to catch. This is exactly why the issue's own
"what this unblocks" reasoning names per-block LVS as necessary before
#149's full-`pll_top` run: a first real LVS pass here has found a real bug
no earlier check could.

### Ruling out two suspects

Two mechanisms could plausibly cause a broad, name-spanning merge like this,
and both were tested directly and ruled out:

1. **`--lvs_sub`'s global substrate synthesis** (`general_connections.lvs`:
   `connect_global(sub, substrate_name)`). Re-ran with
   `--lvs-sub NONEXISTENT_SUBNET` (a name absent from both netlists): the
   identical 39-device extraction and the identical merged-net alias list
   appeared, with `GND_VCO` still present as one of that net's aliases and
   `NONEXISTENT_SUBNET` appearing as its own, separate, ordinary net. Ruled
   out.
2. **`connect_implicit('*')`** (`general_connections.lvs`, under "Multifinger
   Devices" — a real candidate given every multi-finger device in this block
   is drawn as several separately-diffused, metal-tied single-finger
   instances). Patched a scratch copy of the PDK's own
   `rule_decks/general_connections.lvs` to comment that line out
   (`GF180_PDK_PATH` pointed at the patched copy for this one run only, no
   committed PDK changes) and re-ran: identical 39-device extraction,
   identical merged-net alias list. Ruled out.

Neither experiment's artifacts are committed (scratch, PDK-copy-local, not
reproducible from this repo alone) — they are reported here as the
elimination record so a future investigator does not re-spend the same
effort. What has **not** been tried: `nplus`/`pplus`-aware reconstruction of
gf180mcu's own `psd`/`nsd`/`ptap`/`ntap` derived layers (a from-scratch
`klayout.db.LayoutToNetlist` reconstruction connecting only `comp`/`poly2`/
`contact`/`metal1`/`via1`/`metal2`/`nwell` — the union of every layer this
package draws — found **zero** merged nets, meaning gf180mcu's own,
more-detailed layer derivations see a connection this simplified
reconstruction does not); querying `lvs.shapes_of_net()` for the merged net's
own geometry directly (attempted; raised `circuit != 0` from the loaded
`.lvsdb` alone, needs the original GDS re-associated to resolve).

## Not a vacuous pass — but not a pass

Precisely because this is not a match, the numbers above are reported as
found, not massaged: the resistor family's device count (3), class
(`ppolyf_u_1k`, matching the deck-forced variant) and per-instance values all
match the reference exactly, which the log-verified `Extracting PPOLYF_U_1K
device`/`Extracting cap_nmos_03v3 device` lines corroborate as real deck
behaviour rather than an assumption. The MOSFET mismatch is real, reproducible
across three independent runs (default, alternate substrate name, patched
deck), and unaffected by anything this issue's own diff introduces.

## What this means for #367's own acceptance criteria

* `layout/evidence/vco-layout/lvs-attempt/` (not `lvs-clean/` — that name is
  reserved for an actual match) exists with the full deck log, extracted
  `.cir`/`.lvsdb`, and the committed reference `vco_block.spice`.
* The two named device-class deviations are stated and reconciled as this
  issue's Acceptance Criteria ask (ppolyf_u_1k vs _3k; the excluded decap
  pair) — **independently of the mismatch above**, which is a different,
  newly-discovered connectivity defect, not a device-class question.
* `devices.CASCADE_B`'s own `nf` 1 -> 2 finger fold needed **no** special
  reconciliation: `reference_netlist()` states every finger-folded device's
  drawn (not schematic-literal) width via `Fet.drawn_w_um`, and
  `netlist.simplify()` (the deck's own default) folds the layout's separately
  -drawn, identically-connected fingers back into one summed-`W` device
  before comparison — the same mechanism that made the resistor and
  buffer/inverter device counts land correctly. This is unaffected by, and
  unrelated to, the mismatch documented above.
* The `Congratulations! Netlists match.` acceptance line is **not met**.
  This is reported here rather than fabricated, per this repo's own
  verification discipline (CLAUDE.md: "no claim without a testbench") and
  this issue's own explicit instruction to treat a non-passing run as a
  finding, not something to paper over.

Issue #368 tracks root-causing and fixing the short itself, now that this
increment's reference netlist and (fixed) net-labelling give that follow-up
a working LVS harness to iterate against.
