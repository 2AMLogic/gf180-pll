# Antenna-table ERC on `vco_block` (issue #1082)

Re-run of the supply-spec `klt erc` recorded in [`../erc-report.json`](../erc-report.json)
(see [`../PROOF-erc.md`](../PROOF-erc.md)) on the CI-pinned
`klayout-tools==0.9.2`, with the gf180mcu antenna-ratio limit table
selected (`--pdk gf180mcu`, the table 2AMLogic/klayout-tools#4003 added).
This is the first `klt erc` run in this repository whose antenna half
actually graded something. Single-unit local run; no corner grid.

## Why the spec copy beside this report has canonical stackup names

`klt erc` 0.9.2 resolves each level's antenna limit by **exact name**
match between the spec's own `stackup[].name` and the gf180mcu table's
canonical keys (`Metal1`..`Metal5`). The committed
[`../erc-supply-spec.json`](../erc-supply-spec.json) names its entries
`metal1`..`metal5`, so running `--pdk gf180mcu` against it verbatim
leaves every metal level `skipped` with reason `missing_antenna_limit`
(measured on this cell: 145 skipped, 0 checked) while `pdk` reads
`gf180mcu` in the envelope — a silent degradation filed generically
upstream as
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976).

[`erc-supply-spec.json`](erc-supply-spec.json) here is therefore a **copy
of the committed spec with only the stackup entry names mapped to the
table's canonical spelling**, per that issue's lookup:

| committed name | canonical name | GDS layer |
|---|---|---|
| `metal1` | `Metal1` | 34/0 |
| `metal2` | `Metal2` | 36/0 |
| `metal3` | `Metal3` | 42/0 |
| `metal4` | `Metal4` | 46/0 |
| `metal5` | `Metal5` | 81/0 |

`vias[].between` and `ties[].connect_to` references were renamed to
match; nothing else changed. The committed spec stays byte-unchanged at
its recorded path so the 0.9.2 envelope in `../erc-report.json` still
resolves its own `provenance.spec.content_hash`.

## Command

```
klt erc --top vco_block --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/vco-layout/vco_block.gds \
  layout/evidence/vco-layout/erc-antenna-20261120/erc-supply-spec.json \
  > layout/evidence/vco-layout/erc-antenna-20261120/erc-report.json
# exit 3 (antenna violations; connectivity half clean)
```

- klt: `0.9.2` (`klt_reinstall_spec: klayout-tools==0.9.2`, the
  `.github/workflows/ci.yml` pin), git commit `046ba74652fc096bd97071fc3237f7159dd40183`
- The klt ERC run used the KLayout Python wheel `0.30.13`. The foundry
  antenna deck ran in the standalone KLayout application `0.30.12`.
- layout input `vco_block.gds`:
  `sha256:4f5151dfbcd2d43694bfc845a507fbd43974559f1e1f8c4a8b6064afe95deb3c`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:35534205a2a37a27b99413d4055337bf062e0f685f5094d628646676d50ae9aa`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`.

## Result

| field | 0.9.2 deck-only (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | `violations` (exit 3) |
| `erc_status` | `clean` | `clean` (0 findings) |
| `pdk` | `null` | `gf180mcu` (built-in) |
| antenna `coverage.checked` | 0 | **145** |
| antenna `coverage.skipped` | 145 (all `missing_antenna_pdk`) | **0** |
| antenna `coverage.inapplicable` | 29 | 29 (all `gate_reference_level`, expected) |
| `erc_coverage.checked` | 34 | 34 |

Antenna verdicts: 28 of 29 gate nets **pass** every level; 1 gate net
**violates**. Every level now carries a real limit and source
(`antenna_ratio_max: 400.0`, rule `ANT.16_i_ANT.2`..`ANT.6` from
google/gf180mcu-pdk `f6eeac7`).

### The one violation, and why it is not acted on as a layout defect

`gate0` (net `GND_VCO`, gate area 4.4 µm², the block's ground-tied gate
node) reports `antenna_ratio` 711.857909 against the limit 400 at every
metal level — its cumulative Metal1 area is the entire ground rail
(3132.1748 µm²), which the cumulative-connected-area model assigns whole
against one gate's area. The gf180mcu table's own module documents the
model as an approximation that **omits the deck's diode credit**; the
foundry deck's own rule for this net class is
`antenna_check(thin_gate, perimeter_only(metal1, 0.54.um), 400, [diode, 800])`
where the `[diode, 800]` credit is exactly the discharge path a ground
rail has dozens of. Corroborated against that deck (below): **zero
violations** on the same GDS. The verdict is a false positive of the
documented area approximation, owned upstream by
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976)'s
companion
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975);
no layout change is made here, per issue #1082's instruction not to
assign a layout fix a suspected physical violation does not support.

## Foundry-deck corroboration

The PDK's own antenna deck was run on the same committed GDS (open_pdks
`gf180mcuD` `c6d73a35`, deck
`libs.tech/klayout/tech/drc/rule_decks/antenna.drc` at the commit the
klt table itself cites):

```
klayout -b -r antenna.drc -rd input=<vco_block.gds> \
  -rd report=vco_block.lyrdb -rd run_mode=deep -rd metal_level=5LM \
  -rd metal_top=11K -rd thr=2   # KLayout 0.30.12, the repository's
  # pin; log committed as vco_block.stdout.log
# exit 0; vco_block.lyrdb: 0 items
```

Full log and report database committed here
([`vco_block.stdout.log`](vco_block.stdout.log), [`vco_block.lyrdb`](vco_block.lyrdb)).

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt 0.9.2)
on this envelope resolves the supply spec — **reason `None`**, supply
nets `VDD_VCO`, `GND_VCO` — so the ERC half of item 11 no longer stops
at `not_checked` for this block. The item stays unmet pending its paired
block-level `klt lvs` envelope (#149 / #987); the manifest is not changed
by #1082.
