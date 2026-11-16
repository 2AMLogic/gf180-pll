# Curated-deck LVS on `pfd_cp` (issue #945)

Third cell to get a `klt lvs` envelope on the curated extraction deck
(`deck: gf180mcu`), applying the carry-over rule that #930's record stated
for the remaining blocks. Single-unit local run; no corner grid, no
simulator. No generator change, no layout-geometry change, and no claim that
T1 item 11 is met.

**Verdict: `status: match`, `error_count: 0`** — 92/92 nets and 168/168
devices matched, on the first attempt. Unlike #930 there was no
`plain-element` diagnostic round: this envelope applied
`reference.form: "subckt-call"` from the start, exactly as the #930
carry-over rule prescribes for a reference whose `M` cards name PDK models.
The recipe carried over as written; #930's wrong-then-right detour was not
repeated here.

## Inputs

- Layout: `../pfd_cp.gds` (unchanged), top cell `pfd_cp`.
  `sha256:212c27c4a209c2d851d0e424ee9c4c75c040b5824a77a8a2763a3d9f7b7030d9`.
- Reference: `../lvs-clean/pfd_cp.spice`, **referenced in place by relative
  path, not copied** — so it is by construction byte-identical to the
  netlist the foundry-deck run in `../lvs-clean/` matched against (that run's
  own log names this file: `Netlist file: …/lvs-clean/pfd_cp.spice` →
  `Congratulations! Netlists match.`).
  `sha256:8559f96d532888fce22b868b3af70cd25afc48b148012357c5b287e8ebf38cdb`.
  168 `M_` cards and nothing else: 84 `nfet_03v3` + 84 `pfet_03v3`, no `C`,
  `R`, `L`, `D` or `X` device, and a single `.subckt` (`pfd_cp`, 13
  terminals).
- Request: `lvs-request.json` — `layout.deck_options.poly_res: "3k"`
  (read from this block's own foundry-run log, `../lvs-clean/lvs.stdout.log`:
  `POLY_RES Selected is 3k`; it coincides with `lock_detector`'s `3k` but was
  measured here independently), `options.combine_devices: true`,
  `reference.form: "subckt-call"`. No `hints`, no `parameter_tolerance`, no
  `compare_parameters`, no `ignore_mos_bulk`.

## Which reference, and why not the other one

`../lvs-clean/` holds **two** references; this envelope pairs against
`pfd_cp.spice`, the flat one:

| | `.subckt` defs | device cards |
|---|---|---|
| `pfd_cp.spice` (used) | 1 (`pfd_cp`) | 168 `M_`, nothing else |
| `pfd_cp.schematic-export.spice` (not used) | 10 (`pfd_cp pfd cp edgedet pfdcp_inv_3v3 srlatch pfdcp_nand2_3v3 cp_leg_n cp_leg_p cp_dumpbuf`) | 0 `M_`, 34 `XM`, 57 design-subckt calls |

Two reasons, one decisive and one reinforcing:

1. The foundry-deck run that produced the `match` this envelope extends
   named the **flat** file as its reference (see the log quote under
   *Inputs*). Comparing the schematic-export file would not be the same half
   of T1 item 11 that #855 and #930 recorded.
2. The schematic-export file is **hierarchical**, not merely
   subckt-call-form: it declares 10 `.subckt` blocks of design hierarchy and
   its 57 non-`XM` `x*` cards are design cells (38 `pfdcp_inv_3v3`,
   4 `pfdcp_nand2_3v3`, 4 `cp_leg_p`, 4 `cp_leg_n`, 2 `srlatch`,
   2 `edgedet`, 1 `pfd`, 1 `cp_dumpbuf`, 1 `cp`), **not** PDK R/C devices.
   Pairing it against a flat extraction would introduce a hierarchy-matching
   variable orthogonal to what this envelope measures. A hierarchical
   compare, if wanted, is a separate issue.

**Correction carried forward rather than propagated**: #930's record says
"any reference whose `M` cards name PDK models — which is every
`lvs-clean/*.spice` in this tree". The second half is imprecise:
`pfd_cp.schematic-export.spice` has an **empty** `M`-card census (0 `M_`
cards), so it does not name PDK models on `M` cards at all. #930's operative
conclusion still holds for both files — each wants
`reference.form: "subckt-call"`, the flat one because its `M`-card model
tokens (`nfet_03v3`/`pfet_03v3`) need rewriting to the deck's class names
(`nfet`/`pfet`, via `netlist_normalize._rewrite_m_card_model`), the
schematic-export one because it is genuinely subckt-call form.

## Result (`klt 0.9.3.dev16+gdcf18e2e0c03`, KLayout 0.30.13)

```
$ klt --version
klt 0.9.3.dev16+gdcf18e2e0c03
$ klt lvs --format json lvs-request.json > lvs-report.json     # exit 0
```

- `status: match`, `error_count: 0`, `mismatch_count: 6` (six warnings,
  zero errors).
- Nets 92/92 matched, devices 168/168 matched (84 nfet + 84 pfet, both
  sides). Pins are reported as `{layout: 58, reference: 13, matched: 58}`:
  the reference `.subckt` declares its 13 external terminals, while the
  extraction promotes every *named* layout net to a pin — 58 of the 92,
  the remaining 34 being anonymous `$N` nets — and `matched` tracks the
  layout side. #930's cell happened to have all 48 of its nets named, so
  there `{48, 10, 48}` had pins equal to nets; that coincidence does not
  carry over.
- The six warnings, each attributed (verdict unaffected by any of them):
  - **1 × `topology`, device-class bjt** — present on neither side; the
    extraction deck registers the class unconditionally and the report
    itself labels it "not a real topology mismatch". The same lone warning
    the #930 and `vco_block` records carry.
  - **4 × `topology`, ambiguous net pairing** — `$8`↔`PFD_CP_XCP_XP_T1A_BG`,
    `$11`↔`PFD_CP_XCP_XN_T1A_BG`, `$27`↔`PFD_CP_XCP_XN_T1B_BG`,
    `$32`↔`PFD_CP_XCP_XP_T1B_BG`; the comparer resolved each structurally
    and the report suggests a `hints.same_nets` entry to pin them down.
    Cause: these are the charge-pump legs' bulk/background nets, which
    carry no name label on the layout side. Symmetry-resolved, not a
    mismatch; a `hints.same_nets` entry would silence them but was left out
    to keep this request in #930's no-hints shape.
  - **1 × `device.body_unverified`** — 2 PMOS body terminals were compared
    against an anonymous, KLayout-synthesized well net rather than a real
    schematic net (no drawn/derived well-tap geometry, or the tap-connected
    conductor carries no name label). Recorded in the report's structured
    `body_verification` block as `status: unverified`, class `pfet`,
    device_count 2. New relative to #930, whose cell did not trip it.
- **No `device.placeholder_value` and no `device.geometry_not_compared`
  warnings**, and `device_parameter_coverage` is empty — the expectation
  this record's Inputs section already states, since the cell draws no
  resistor or capacitor at all. Had they appeared despite that, they would
  have been a finding; they did not.
- `power_connectivity` is `unchecked` by design: that check exists for the
  signal-only `gate-level-verilog` form, and a SPICE reference carries its
  own supply pins and nets, which took part in the ordinary compare above.

`klt lvs --check`, both modes, quoted verbatim:

```
$ klt lvs --check lvs-report.json          # cheap mode (default): re-hash inputs
report: lvs-report.json
status: match
  [OK] environment.layout_sha256
  [OK] environment.reference_sha256
  [OK] provenance.deck.content_hash
                                           # exit 0

$ klt lvs --check lvs-report.json --rerun  # full mode: re-run compare, diff verdict fields
report: lvs-report.json
status: match
                                           # exit 0
```

Both modes were run, and both exit 0. At klt 0.9.x `--check` has these two
strengths and "checked" is ambiguous without saying which.

`provenance.klayout_version_mismatch` is `true` in this report: the resolved
KLayout engine is 0.30.13 while this klt build was tested against 0.30.12.
klt warns that *report counts* may differ on a different engine, while the
verdict is unaffected. Note the klt version itself has moved twice since
#930 recorded its envelope (`0.9.2.dev1024+g8da9718f0cb6` →
`0.9.3.dev3+gd5d57daf9a14` at #930's curation →
`0.9.3.dev16+gdcf18e2e0c03` here); the load-bearing mechanisms the
carry-over rule rests on were re-verified present on this build
(`netlist_normalize._rewrite_m_card_model` at `netlist_normalize.py:2029`,
dispatched from `:2169`; `_GEOMETRY_DISCLOSURE_CLASS_KINDS` at `lvs.py:6248`,
still scoped to resistor and capacitor classes only; `_REFERENCE_FORMS` at
`lvs.py:316`) before the run, and the verdict confirms the rule holds here.

## What this does and does not establish

**Does:**

- Connectivity: all 92 extracted nets correspond to the 92 reference nets.
- Device inventory: all 168 extracted MOS devices pair 1:1 with the
  reference's 168, in the right device class (84 pfet, 84 nfet).
- MOS sizing: `L` and `W` are *primary* parameters on KLayout's MOS classes,
  so they were compared on every device, with no tolerance
  (`parameter_tolerance: null`) and no exclusions
  (`compare_parameters: null`) — an unmatched `L`/`W` would have been an
  error, and there were none.

**Does not:**

- **MOS diffusion parasitics are not compared, and this report does not say
  so.** The reference's `ad`/`as`/`pd`/`ps`/`nrd`/`nrs` are
  *expression*-valued. They land on KLayout's *secondary* MOS parameters,
  which take no part in any default compare. klt deliberately restricts its
  `device.geometry_not_compared` / `device_parameter_coverage` disclosures
  to resistor and capacitor classes (`lvs.py`,
  `_GEOMETRY_DISCLOSURE_CLASS_KINDS`), on the stated grounds that a MOS's
  own `L`/`W` *is* compared and the diffusion terms are a narrower gap. The
  consequence for a reader of this report is that the gap is real but
  undisclosed in the JSON — hence this paragraph. klt neither errored on nor
  evaluated those expressions: they pass through the `subckt-call`
  conversion as opaque text.
- **Body connectivity for the 2 flagged PMOS devices is unverified** (the
  `device.body_unverified` warning above): those two body terminals were
  compared against a synthesized well net, not a named schematic net, so
  the `match` does not attest them the way it attests the other 166
  devices' bodies.
- It does not replace, alter, or re-grade the foundry-deck
  `Netlists match.` in `../lvs-clean/`, which is untouched and remains the
  signoff-bearing LVS result.
- **It does not establish that T1 item 11 is met.** Item 11 grades a pair
  across the whole block set; this is one cell's half of it.
- No citation was added to `signoff/block-manifest.json`.

## Friction protocol

No new tool gap surfaced: the known form-flag discoverability gap was
already filed generically as **2AMLogic/klayout-tools#5676** at #930, and
this run applied the flag from the start, so it did not re-trip. The
ambiguous-net warnings name their own remedy (`hints.same_nets`) in the
report text, which is the discoverability behaviour a tool wants — not a
gap.

## Files

| File | What |
|---|---|
| `lvs-request.json` | the request that produced the `match` |
| `lvs-report.json` | `klt lvs --format json` output; `status: match` |
