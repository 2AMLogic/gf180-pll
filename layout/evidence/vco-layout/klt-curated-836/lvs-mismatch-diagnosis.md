# Attribution of the 57 curated-deck LVS errors on `vco_block` (#854)

Date: 2026-10-31. `klt 0.8.1.dev965+g5d8e4f2b5009`, KLayout 0.30.12,
`--deck gf180mcu`. Diagnosis only: the reference netlist
(`../lvs-clean/vco_block.spice`), the layout (`../vco_block.gds`) and `klt` are
unchanged. The recorded report is `lvs-vco_block.json`; its context is the
2026-10-31 section of `../PROOF-836-vdd-vco-metal-continuity.md`.

## Result in one paragraph

**None of the 57 errors is attributed to the layout.** 54 come from how the
request drives the curated deck (parallel fingers not merged, resistor class
named from a whole-run option) and 3 from a reference that predates the supply
decap. With `poly_res: "3k"`, `combine_devices: true` and a reference that
carries the decap, the same GDS gives `match`, 43/43 nets, 66/66 devices
(probe D). That match does **not** verify resistor or capacitor values; see
"What probe D does not show".

## Reproduction

One `klt lvs --format json lvs-request.json` run (local, single unit)
reproduced the recorded report exactly (`mismatches` identical, 57 errors, nets
43/43/31, devices 81/65/56). `klt lvs --check lvs-vco_block.json` reports the
committed hashes consistent.

## Attribution table

Owners: **R** = reference older than layout, **E** = curated-deck extraction /
compare gap (default behaviour of the deck run, fixed by request options or a
tool change), **L** = layout.

| Category (errors) | Count | Owner | Evidence |
|---|---|---|---|
| `device.unmatched`, MOS (12 pfet, 2 nfet) | 14 | E | Fingers, below. Gone in probe B and C. |
| `device.property` (`w_um`, `as`, `ad`, `ps`, `pd`) | 30 | E | Fingers, below: 6 devices x 5 parameters. Gone in probe B and C. |
| `device.unmatched`, `cap_nmos_03v3` | 2 | R | Reference has no decap. Probe C leaves 1 (the two layout caps merge to one); probe D removes it. |
| `device.class` `ppolyf_u_1k` vs `PPOLYF_U_3K` | 3 | E | Class name follows `poly_res`, below. Gone in probe A and C. |
| `topology`, net pairs with name conflict (`GB`, `VBN1`, `VBP2`, `GA`, `GC`) | 5 | E | Nets of the split mirror devices. Gone in probe B (3 topology errors left, all class mapping). |
| `topology`, class not mapped `cap_nmos_03v3` | 1 | R | Same cause as the 2 unmatched caps. Present in probe C, absent in D. |
| `topology`, class not mapped `ppolyf_u_1k` / `PPOLYF_U_3K` | 2 | E | Same cause as the 3 `device.class` errors. Absent in probe A and C. |
| **Total** | **57** | | 54 E + 3 R + 0 L. Matches `error_count` and `category_error_counts` (3 + 30 + 16 + 8). |

The report also carries 4 warnings (3 `device.geometry_not_compared`, 1 `bjt`
class with no devices); these are not among the 57.

## Evidence per category

### Parallel fingers (14 unmatched, 30 property, 5 net pairs) -> E

`klt extract --deck gf180mcu --top vco_block` on the GDS gives 81 devices. The
layout draws six transistors of the reference as groups of identical parallel
devices (same gate, drain/source, bulk and L). Grouping the extracted MOS cards
by those keys and summing W:

| Reference device | Reference W (um) | Layout fingers | Sum (um) |
|---|---|---|---|
| `M_MB0` (nfet) | 5.0 | 2 x 2.5 | 5.0 |
| `M_MB1` (nfet) | 8.61 | 2 x 4.305 | 8.61 |
| `M_MSUM` (pfet) | 60.0 | 4 x 15.0 | 60.0 |
| `M_MA0` (pfet) | 26.5 | 2 x 13.25 | 26.5 |
| `M_MA1` (pfet) | 17.22 | 2 x 8.61 | 17.22 |
| `M_MC1` (pfet) | 78.88 | 8 x 9.86 | 78.88 |

Unmatched fingers: 1 + 1 + 3 + 1 + 1 + 7 = 14 (2 nfet, 12 pfet), the counts in
the report. The one matched finger of each group is the `device.property`
`w_um` pair in the report (2.5 vs 5.0, 4.305 vs 8.61, 15 vs 60, 13.25 vs 26.5,
8.61 vs 17.22, 9.86 vs 78.88), i.e. 6 devices; each also lists `as`, `ad`,
`ps`, `pd`, giving 6 x 5 = 30. The other 50 matched MOS devices have non-zero
layout `as`/`ad`/`ps`/`pd` against a reference that states none and raise no
property error, so those four parameters are not a separate defect; they are
listed alongside a `w_um` difference. Why the report lists them only then is
**not traced**.

Probe B (`combine_devices: true`, nothing else changed): 14 unmatched and 30
property errors disappear; 62 of 65 devices matched.

Owner: E, not L. The summed widths equal the reference exactly, so the layout
implements the reference transistor; the default compare does not merge
parallel devices and the recorded request did not turn that on. Whether a
tool default should change is the upstream issue.

### Resistor class (3 `device.class`, 2 `topology`) -> E

Layout resistors extract as `ppolyf_u_1k`; the reference rewrites to
`PPOLYF_U_3K`. The extractor's default is `poly_res=1k` (`klt extract` prints
"poly_res=1k (default)"). The layout does draw the high-sheet marker (the
extract lists `62/0` with 3 shapes as recognition-only), consistent with
`PROOF-381-high-rs-resistor.md`. Probe A (`layout.deck_options.poly_res: "3k"`
only): `device.class` goes 3 -> 0 and class-mapping `topology` errors 3 -> 1
(the remaining one is the decap). So the class name is set by the whole-run
deck option, not by what is drawn. That the committed reference's `3k` is the
correct class is not in dispute (DR-009).

### Decap (2 unmatched, 1 topology) -> R

`lvs-clean/vco_block.spice` last changed 2026-09-11 (`git log`: #381, #378);
the layout gained two `cap_nmos_03v3` devices on 2026-10-09 (`62453a83`, #759),
and `PROOF-lvs.md` already marks its own "excluded decap pair" text as
superseded. `decap-20261009/vco_block.spice` is the reference with the decap
(diff against `lvs-clean/`: the decap card and two comment lines). Probe C
(options A + B) leaves exactly these: the layout's 2 caps merge into 1 unmatched
device and 1 class-mapping error (2 errors total). Probe D adds the decap to
the reference and reaches `match`.

`klt lvs` cannot read `decap-20261009/vco_block.spice` as committed: its
`C_XCDEC1 ... cap_nmos_03v3 W=50u L=50u M=2` card fails with `Can't find a value
for a R, C or L device`. Probe D therefore uses a scratch copy,
`diagnosis-probes/probe-reference-decap-xcard.spice`, identical except the card
starts with `X_` instead of `C_`. Neither committed reference was modified.

## Probes (all single `klt lvs` runs, local)

Requests, reports and the scratch reference are in `diagnosis-probes/`. Each
report passes `klt lvs --check` (D checked explicitly).

| Probe | Change from `lvs-request.json` | Result |
|---|---|---|
| A | `layout.deck_options.poly_res: "3k"` | mismatch, 52 errors |
| B | `options.combine_devices: true` | mismatch, 7 errors |
| C | A + B | mismatch, 2 errors (the decap) |
| D | A + B + scratch reference with the decap | **match**, 43/43 nets, 66/66 devices, 0 errors |

## What probe D does not show

- Reference resistor and capacitor values are the literal 0 placeholder after
  `reference.form: "subckt-call"` conversion (`device.placeholder_value`
  warnings), and the geometry parameters `W`, `L`, `A`, `P` of resistors and
  capacitors are not compared (`device.geometry_not_compared`). The match
  verifies connectivity and MOS parameters, not poly-resistor or decap sizing.
- With `combine_devices` on, the fingers' W is checked only as a sum.
- Same-named nets are joined by the deck, so a `match` still does not exercise
  the VDD_VCO strap (as `PROOF-836` already notes).
- Probe D is diagnosis, not the re-recorded result: it uses a scratch
  reference, which is why the re-record is a separate issue.

## Follow-ups filed (not fixed here)

| Owner | Issue |
|---|---|
| R (reference older than layout), plus the request options | [#855](https://github.com/2AMLogic/gf180-pll/issues/855) |
| E (curated-deck gap), filed generically | [2AMLogic/klayout-tools#4729](https://github.com/2AMLogic/klayout-tools/issues/4729) |
| L (layout) | none: no error is attributed to the layout, so there is nothing to file |
