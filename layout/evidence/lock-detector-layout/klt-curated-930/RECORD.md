# Curated-deck LVS on `lock_detector` (issue #930)

Second cell to get a `klt lvs` envelope on the curated extraction deck
(`deck: gf180mcu`), following the `vco_block` recipe in
`../../vco-layout/klt-curated-836-recheck/`. Single-unit local run; no corner
grid, no simulator.

**Verdict: `status: match`, `error_count: 0`** — 48/48 nets and 117/117
devices matched. Reached only after `reference.form: "subckt-call"` was added;
the first attempt, in the default `plain-element` form, is committed alongside
as `lvs-*-plain-element.json` and diagnosed below. The recipe therefore
*does* carry over, but **not** as the issue body and curation assumed: the
`vco_block` reference workaround was load-bearing here too, for a reason that
had nothing to do with that block's supply decap.

## Inputs

- Layout: `../lock_detector.gds` (unchanged), top cell `lock_detector`.
  `sha256:799af5d7f6b8407c5efc50b7e8ef639a8aa8787eb91b47e1f31f66f1673b2c0c`.
- Reference: `../lvs-clean/lock_detector.spice`, **referenced in place by
  relative path, not copied** — so it is by construction byte-identical to the
  netlist the foundry-deck run in `../lvs-clean/` matched against.
  `sha256:a616b09c52530f481ea49e6ddaf8d68b3ab1483c36d1ca75cbb8f82ec6ba04d5`.
  117 `M_` cards and nothing else: no `C`, `R`, `X` or diode device.
- Request: `lvs-request.json` — `layout.deck_options.poly_res: "3k"`
  (matching the foundry run that produced the `match`:
  `../lvs-clean/lvs.stdout.log`, `POLY_RES Selected is 3k`),
  `options.combine_devices: true`, `reference.form: "subckt-call"`.
  No `hints`, no `parameter_tolerance`, no `compare_parameters`,
  no `ignore_mos_bulk`.

## Result (`klt 0.9.2.dev1024+g8da9718f0cb6`, KLayout 0.30.13)

```
$ klt --version
klt 0.9.2.dev1024+g8da9718f0cb6
$ klt lvs --format json lvs-request.json > lvs-report.json     # exit 0
```

- `status: match`, `error_count: 0`, `mismatch_count: 1`.
- Nets 48/48 matched, devices 117/117 matched. Pins are reported as
  `{layout: 48, reference: 10, matched: 48}`: the reference `.subckt` declares
  10 terminals while the extraction promotes every net to a pin, and `matched`
  tracks the layout side — the same shape the `vco_block` record reports
  (`{20, 7, 20}`).
- One warning, zero errors: a single `topology` entry for device class `bjt`,
  present on neither side — the extraction deck registers the class
  unconditionally and the report itself labels it "not a real topology
  mismatch". This is the same lone warning the `vco_block` record carries.
- **No `device.placeholder_value` and no `device.geometry_not_compared`
  warnings**, and `device_parameter_coverage` is empty. The `vco_block`
  record's "resistor and capacitor values are unverified" caveat does **not**
  carry over, because this cell draws no resistor or capacitor at all.

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

Both modes were run, and both exit 0. At klt 0.9.2 `--check` has these two
strengths and "checked" is ambiguous without saying which.

`provenance.klayout_version_mismatch` is `true` in this report: the resolved
KLayout engine is 0.30.13 while this klt build was tested against 0.30.12.
klt warns that *report counts* may differ on a different engine, while the
verdict is unaffected. Confirmed empirically here — re-running the committed
`vco_block` request on this engine (`klt lvs --check ... --rerun`) drifted
only on `environment.engine_version`, `provenance.deck.content_hash` and
`provenance.klayout_version_mismatch`, with **no** verdict-field drift.

## What this does and does not establish

**Does:**

- Connectivity: all 48 extracted nets correspond to the 48 reference nets.
- Device inventory: all 117 extracted MOS devices pair 1:1 with the
  reference's 117, in the right device class (40 pfet, 77 nfet).
- MOS sizing: `L` and `W` are *primary* parameters on KLayout's MOS classes,
  so they were compared on every device, with no tolerance
  (`parameter_tolerance: null`) and no exclusions
  (`compare_parameters: null`) — an unmatched `L`/`W` would have been an
  error, and there were none.

**Does not:**

- **MOS diffusion parasitics are not compared, and this report does not say
  so.** The reference's `ad`/`as`/`pd`/`ps`/`nrd`/`nrs` are *expression*-valued
  (e.g. `ad='int((nf+1)/2) * W/nf * 0.18u'`). They land on KLayout's
  *secondary* MOS parameters, which take no part in any default compare. klt
  deliberately restricts its `device.geometry_not_compared` /
  `device_parameter_coverage` disclosures to resistor and capacitor classes
  (`lvs.py`, `_GEOMETRY_DISCLOSURE_CLASS_KINDS`), on the stated grounds that a
  MOS's own `L`/`W` *is* compared and the diffusion terms are a narrower gap.
  The consequence for a reader of this report is that the gap is real but
  undisclosed in the JSON — hence this paragraph. Note also that klt neither
  errored on nor evaluated those expressions: they pass through the
  `subckt-call` conversion as opaque text.
- `power_connectivity` is `unchecked` by design: that check exists for the
  signal-only `gate-level-verilog` form, and a SPICE reference carries its own
  supply pins and nets, which took part in the ordinary compare above.
- It does not replace, alter, or re-grade the foundry-deck `Netlists match.`
  in `../lvs-clean/` (KLayout 0.28.16, 2026-09-21), which is untouched and
  remains the signoff-bearing LVS result.
- **It does not establish that T1 item 11 is met.** Item 11 grades a pair
  across the whole block set; this is one cell's half of it.
- No citation was added to `signoff/block-manifest.json`.

## Why the first attempt failed: the `vco_block` workaround *does* apply here

Issue #930 and its curation both concluded that `vco_block`'s
`reference.form: "subckt-call"` was needed only to convert that block's supply
decap `C_` card, and that a cell with 117 `M_` cards and no R/C could use the
committed reference as-is in the default `plain-element` form. **That is
wrong**, and the plain-element run is committed as the evidence:

```
# lvs-request-plain-element.json  (identical, minus `"form": "subckt-call"`)
status: mismatch   mismatch_count: 335   error_count: 334
counts.devices: {layout: 117, reference: 117, matched: 0}
counts.nets:    {layout: 48,  reference: 48,  matched: 0}
category_error_counts: {device.unmatched: 234, net.unmatched: 96, topology: 4}
```

Attribution — a single cause, in the **reference form**, not in extraction and
not in the layout:

- `plain-element` reads the file straight through `kdb.NetlistSpiceReader`, so
  each reference MOS device class is named after the model token the `M` card
  carries, upper-cased: `PFET_03V3` (40) and `NFET_03V3` (77). Verified by
  reading the reference directly with KLayout's reader.
- The curated deck's extraction names its MOS classes `pfet` / `nfet`.
- Those names never pair, so no device pairs, so no net pairs. Both sides'
  device and net counts agree exactly (117/117, 48/48) with `matched: 0` —
  the signature of a naming failure, not a layout defect. The real cause
  appears only as the 4 error-severity entries among the 5 `topology` ones —
  `device class could not be mapped to a counterpart:` `'nfet'` and `'pfet'`
  (side `layout`), `'PFET_03V3'` and `'NFET_03V3'` (side `reference`) —
  buried in a 335-entry cascade.
- `reference.form: "subckt-call"` fixes it because
  `netlist_normalize.convert_reference_netlist` rewrites each `M` card's model
  token to the deck's device-class name (`pfet_03v3` -> `pfet`) — even though
  this reference contains no `X` subcircuit calls for that form to convert.
  That normalization, not the decap conversion, is what `vco_block` was also
  relying on; its reference carries `pfet_03v3`/`nfet_03v3` `M` cards too.

**Carry-over rule for the remaining blocks** (`pfd_cp`, `divider_chain`,
`loop_filter`, `pll_top`; out of scope here, see #930): any reference whose
`M` cards name PDK models — which is every `lvs-clean/*.spice` in this tree,
since they are what the foundry deck matched — needs
`reference.form: "subckt-call"` for a curated-deck compare, regardless of
whether it has an R or C device. Expect `placeholder_value` /
`geometry_not_compared` warnings only on the cells that do.

## Friction protocol

Filed generically as **2AMLogic/klayout-tools#5676** — a plain-element
reference carrying PDK model names cannot pair with a curated-deck
extraction; the only mapping is a form flag whose name describes converting
subcircuit calls, and klt detects the mirror-image form mismatch (a
subckt-call-shaped reference read as plain-element) with a named error while
this direction yields the mismatch cascade above. The issue describes the
tool gap, the two-part diagnosis/discoverability problem, and three candidate
fixes, without reference to this design.

## Files

| File | What |
|---|---|
| `lvs-request.json` | the request that produced the `match` |
| `lvs-report.json` | `klt lvs --format json` output; `status: match` |
| `lvs-request-plain-element.json` | first attempt, default reference form |
| `lvs-report-plain-element.json` | its `status: mismatch` report, kept as the diagnosis above |
