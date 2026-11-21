# Antenna-table ERC on `divider_chain` (issue #1082)

Re-run of the supply-spec `klt erc` recorded in
[`../erc-report.json`](../erc-report.json) (see
[`../PROOF-erc.md`](../PROOF-erc.md)) on the CI-pinned
`klayout-tools==0.9.2`, with the gf180mcu antenna-ratio limit table
selected (`--pdk gf180mcu`, the table 2AMLogic/klayout-tools#4003
added). First antenna-graded ERC envelope for this block — and the first
in this repository to come back **`status: clean`** with the antenna half
fully graded. Single-unit local run; no corner grid.

## Why the spec copy beside this report has canonical stackup names

`klt erc` 0.9.2 resolves each level's antenna limit by **exact name**
match between the spec's own `stackup[].name` and the gf180mcu table's
canonical keys (`Metal1`..`Metal5`). The committed
[`../erc-supply-spec.json`](../erc-supply-spec.json) names its entries
`metal1`..`metal3`, so running `--pdk gf180mcu` against it verbatim
leaves every metal level `skipped` with reason `missing_antenna_limit`
while `pdk` reads `gf180mcu` in the envelope — a silent degradation filed
generically upstream as
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976).

[`erc-supply-spec.json`](erc-supply-spec.json) here is therefore a **copy
of the committed spec with only the stackup entry names mapped to the
table's canonical spelling** (`metal1`→`Metal1` 34/0, `metal2`→`Metal2`
36/0, `metal3`→`Metal3` 42/0); `vias[].between` and `ties[].connect_to`
references were renamed to match; nothing else changed. The committed
spec stays byte-unchanged at its recorded path so the
`../erc-report.json` envelope still resolves its own
`provenance.spec.content_hash`.

## Command

```
klt erc --top divider_chain --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/divider-chain-layout/divider_chain.gds \
  layout/evidence/divider-chain-layout/erc-antenna-20261120/erc-supply-spec.json \
  > layout/evidence/divider-chain-layout/erc-antenna-20261120/erc-report.json
# exit 0 (clean)
```

- klt: `0.9.2` (`klt_reinstall_spec: klayout-tools==0.9.2`, the
  `.github/workflows/ci.yml` pin), git commit `046ba74652fc096bd97071fc3237f7159dd40183`
- The klt ERC run used the KLayout Python wheel `0.30.13`. The foundry
  antenna deck ran in the standalone KLayout application `0.30.12`.
- layout input `divider_chain.gds`:
  `sha256:bb5d78a0f80130bd8fbcc766b0e71d07493c7d0e5c92edf549044f66a7704404`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:312a4515a9410eb52543ae8f8c0f0c7d0677efcbad148f14d2e4f5f8786b1a16`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`.

## Result

| field | deck-only 0.9.2 (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | **`clean`** (exit 0) |
| `erc_status` | `clean` | `clean` (0 findings) |
| `pdk` | `null` | `gf180mcu` (built-in) |
| antenna `coverage.checked` | 0 | **420** |
| antenna `coverage.skipped` | 420 (all `missing_antenna_pdk`) | **0** |
| antenna `coverage.inapplicable` | 140 | 140 (all `gate_reference_level`, expected) |
| `erc_coverage.checked` | 145 | 145 |
| `erc_coverage.inapplicable` | 0 | 0 |

Every gate net's every metal level **passes** the real limit
(`antenna_ratio_max: 400.0`, rules `ANT.16_i_ANT.2`..`ANT.4` from
google/gf180mcu-pdk `f6eeac7`). Notably, this block's own supply-tied
gate nodes — the net class that false-positive-violates under the area
model in the other four cells (see
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975))
— stay under 400 here: this block's rails are small enough that even the
whole-rail cumulative area stays within the limit.

## Foundry-deck corroboration

The PDK's own antenna deck was run on the same committed GDS (open_pdks
`gf180mcuD` `c6d73a35`, deck
`libs.tech/klayout/tech/drc/rule_decks/antenna.drc` at the commit the
klt table itself cites):

```
klayout -b -r antenna.drc -rd input=<divider_chain.gds> \
  -rd report=divider_chain.lyrdb -rd run_mode=deep -rd metal_level=5LM \
  -rd metal_top=11K -rd thr=2   # KLayout 0.30.12, the repository's
  # pin; log committed as divider_chain.stdout.log
# exit 0; divider_chain.lyrdb: 0 items
```

Full log and report database committed here
([`divider_chain.stdout.log`](divider_chain.stdout.log),
[`divider_chain.lyrdb`](divider_chain.lyrdb)). The deck and the klt
table agree on this block: no antenna violation.

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt
0.9.2) on this envelope resolves the supply spec — **reason `None`**,
supply nets `VDD_DIV`, `VSS` — so the ERC half of item 11 no longer
stops at `not_checked` for this block, and this is the cleanest ERC
half of the five (both halves clean: no disclosure, no finding). The
item stays unmet pending its paired block-level `klt lvs` envelope
(#149 / #987); the manifest is not changed by #1082.
