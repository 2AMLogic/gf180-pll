# Antenna-table ERC on `lock_detector` (issue #1082)

Re-run of the supply-spec `klt erc` recorded in
[`../erc-report.json`](../erc-report.json) (see
[`../PROOF-erc.md`](../PROOF-erc.md)) on the CI-pinned
`klayout-tools==0.9.2`, with the gf180mcu antenna-ratio limit table
selected (`--pdk gf180mcu`, the table 2AMLogic/klayout-tools#4003
added). First antenna-graded ERC envelope for this block. Single-unit
local run; no corner grid.

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
36/0, `metal3`→`Metal3` 42/0); `vias[].between`, `nets[].roles` and
`ties[].connect_to` references were renamed to match; nothing else
changed. The committed spec stays byte-unchanged at its recorded path so
the `../erc-report.json` envelope still resolves its own
`provenance.spec.content_hash`.

## Command

```
klt erc --top lock_detector --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/lock-detector-layout/lock_detector.gds \
  layout/evidence/lock-detector-layout/erc-antenna-20261120/erc-supply-spec.json \
  > layout/evidence/lock-detector-layout/erc-antenna-20261120/erc-report.json
# exit 3 (antenna violations; connectivity half clean)
```

- klt: `0.9.2` (`klt_reinstall_spec: klayout-tools==0.9.2`, the
  `.github/workflows/ci.yml` pin), git commit `046ba74652fc096bd97071fc3237f7159dd40183`
- KLayout: `0.30.13`
- layout input `lock_detector.gds`:
  `sha256:799af5d7f6b8407c5efc50b7e8ef639a8aa8787eb91b47e1f31f66f1673b2c0c`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:4129945c2de6a4571e8c868d06c48546a22bdb05b05a23cb5326eebb2dd66176`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`.

## Result

| field | deck-only 0.9.2 (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | `violations` (exit 3) |
| `erc_status` | `clean` | `clean` (0 findings) |
| `pdk` | `null` | `gf180mcu` (built-in) |
| antenna `coverage.checked` | 0 | **117** |
| antenna `coverage.skipped` | 117 (all `missing_antenna_pdk`) | **0** |
| antenna `coverage.inapplicable` | 39 | 39 (all `gate_reference_level`, expected) |
| `erc_coverage.checked` | 44 | 44 |
| `erc_coverage.inapplicable` | 0 | 0 |

Antenna verdicts: 37 of 39 gate nets **pass** every level; two gate nets
**violate** (below). Every level now carries a real limit and source
(`antenna_ratio_max: 400.0`, rules `ANT.16_i_ANT.2`..`ANT.4` from
google/gf180mcu-pdk `f6eeac7`).

### The two violations, and why neither is acted on as a layout defect

| gate | net | gate area µm² | violating level | ratio |
|---|---|---|---|---|
| `gate6` | `VSS` | 4.4 | Metal3 | 501.665818 |
| `gate12` | `XDLY_T0B` | 0.6864 | Metal3 | 420.961247 |

`VSS` is the rail-tied gate net class again (cumulative Metal3 area
2207.3296 µm² — the block's whole ground rail — against a 4.4 µm² gate;
it passes Metal1/Metal2 and crosses 400 only when Metal3's step area
lands). `XDLY_T0B` is this block's delay-chain first driven node — the
drain of its driving inverter (`M$9` in the committed LVS extraction,
AS=AD=2.5P) driving four receiver gates — a diffusion-connected net end
to end (the same net also violates at `pll_top`, where this block is
instantiated). The gf180mcu table's own module documents the model as an
approximation that **omits the deck's diode credit**; the foundry deck's
own rule for this net class is
`antenna_check(thin_gate, perimeter_only(metal, 0.54.um), 400, [diode, 800])`,
where the `[diode, 800]` credit is exactly the discharge path both nets
have. Corroborated against that deck (below): **zero violations** on the
same GDS. Both verdicts are false positives of the documented area
approximation, owned upstream by
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975)
(name-lookup companion gap:
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976));
no layout change is made here, per issue #1082's instruction not to
assign a layout fix a suspected physical violation does not support.

## Foundry-deck corroboration

The PDK's own antenna deck was run on the same committed GDS (open_pdks
`gf180mcuD` `c6d73a35`, deck
`libs.tech/klayout/tech/drc/rule_decks/antenna.drc` at the commit the
klt table itself cites):

```
klayout -b -r antenna.drc -rd input=<lock_detector.gds> \
  -rd report=lock_detector.lyrdb -rd run_mode=deep -rd metal_level=5LM \
  -rd metal_top=11K -rd thr=2   # KLayout 0.30.12, the repository's
  # pin; log committed as lock_detector.stdout.log
# exit 0; lock_detector.lyrdb: 0 items
```

Full log and report database committed here
([`lock_detector.stdout.log`](lock_detector.stdout.log),
[`lock_detector.lyrdb`](lock_detector.lyrdb)).

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt
0.9.2) on this envelope resolves the supply spec — **reason `None`**,
supply nets `VDD`, `VSS` — so the ERC half of item 11 no longer stops at
`not_checked` for this block. Together with the block-level LVS `match`
already committed in [`../klt-curated-930/`](../klt-curated-930/), this
is now a qualifying item-11 pair on its ERC-half merits; citing it in
the manifest is deliberately **not** done by #1082 (that citation, and
the LVS-half qualification rules it must satisfy first, belong to #149 /
#987, and #1082's own scope says the manifest stays as it is).
