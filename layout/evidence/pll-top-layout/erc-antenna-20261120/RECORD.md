# Antenna-table ERC on `pll_top` (issue #1082)

Re-run of the supply-spec `klt erc` recorded in [`../erc-report.json`](../erc-report.json)
(see [`../PROOF-erc.md`](../PROOF-erc.md)) on the CI-pinned
`klayout-tools==0.9.2`, with the gf180mcu antenna-ratio limit table
selected (`--pdk gf180mcu`, the table 2AMLogic/klayout-tools#4003 added).
First antenna-graded ERC envelope for the assembled top level. Single-unit
local run; no corner grid.

## Why the spec copy beside this report has canonical stackup names

`klt erc` 0.9.2 resolves each level's antenna limit by **exact name**
match between the spec's own `stackup[].name` and the gf180mcu table's
canonical keys (`Metal1`..`Metal5`). The committed
[`../erc-supply-spec.json`](../erc-supply-spec.json) names its entries
`metal1`..`metal5`, so running `--pdk gf180mcu` against it verbatim
leaves every metal level `skipped` with reason `missing_antenna_limit`
while `pdk` reads `gf180mcu` in the envelope — a silent degradation filed
generically upstream as
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976).

[`erc-supply-spec.json`](erc-supply-spec.json) here is therefore a **copy
of the committed spec with only the stackup entry names mapped to the
table's canonical spelling** (`metal1`→`Metal1` 34/0, `metal2`→`Metal2`
36/0, `metal3`→`Metal3` 42/0, `metal4`→`Metal4` 46/0, `metal5`→`Metal5`
81/0); `vias[].between` references were renamed to match; nothing else
changed. The committed spec stays byte-unchanged at its recorded path so
the `../erc-report.json` envelope still resolves its own
`provenance.spec.content_hash`.

## Command

```
klt erc --top pll_top --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/pll-top-layout/pll_top.gds \
  layout/evidence/pll-top-layout/erc-antenna-20261120/erc-supply-spec.json \
  > layout/evidence/pll-top-layout/erc-antenna-20261120/erc-report.json
# exit 3 (antenna violations; connectivity half clean)
```

- klt: `0.9.2` (`klt_reinstall_spec: klayout-tools==0.9.2`, the
  `.github/workflows/ci.yml` pin), git commit `046ba74652fc096bd97071fc3237f7159dd40183`
- KLayout: `0.30.13`
- layout input `pll_top.gds`:
  `sha256:fbe4001364aa586f6bdbf1babe85cbb4d40d8fbf4560b899ee158d7f5f12b11c`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:a76f83d22e17aee84e28b2e1d1722adce3d1f4f501f0c80a1af305c8ffdeb7f2`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`. (The committed
`../erc-report.json` was itself still on klt 0.8.0 — the #1084 pin bump
only regenerated the four block reports — so this record is also the
first 0.9.2 envelope for `pll_top` of any kind.)

## Result

| field | 0.8.0 (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | `violations` (exit 3) |
| `erc_status` | `clean` | `clean` (0 findings) |
| `pdk` | `null` | `gf180mcu` (built-in) |
| antenna `coverage.checked` | 0 | **1380** |
| antenna `coverage.skipped` | 1380 (all `missing_antenna_pdk`) | **0** |
| antenna `coverage.inapplicable` | 276 | 276 (all `gate_reference_level`, expected) |
| `erc_coverage.checked` | 279 | 281 |
| `erc_coverage.inapplicable` | 0 | 2 (`ties_disclosed_tool_limitation` disclosure class) |

Antenna verdicts: all but three gate nets **pass** every level; three
gate nets **violate** (detail below). Every level now carries a real
limit and source (`antenna_ratio_max: 400.0`, rules
`ANT.16_i_ANT.2`..`ANT.6` from google/gf180mcu-pdk `f6eeac7`).

### The three violations, and why none is acted on as a layout defect

| gate | net | gate area µm² | violating levels | ratio at first violating level |
|---|---|---|---|---|
| `gate21` | `GND_VCO` | 4.4 | Metal1..Metal5 | 711.857909 |
| `gate38` | `VDD` | 0.6 | Metal1..Metal5 | 857.065333 (climbs to 4038.913333 at Metal5) |
| `gate17` | `XDLY_T0B` | 0.6864 | Metal3..Metal5 | 420.961247 |

All three are the same class: gate nets that also carry source/drain
junctions. `GND_VCO`/`VDD` are the supply rails themselves (ground-tied
and rail-tied gate nodes whose cumulative metal area is the whole rail);
`XDLY_T0B` is the lock detector delay chain's first driven node — the
drain of its driving inverter (`M$9` in the committed LVS extraction,
AS=AD=2.5P) — so the net's metal is diffusion-connected at both ends. The
gf180mcu table's own module documents the model as an approximation that
**omits the deck's diode credit**; the foundry deck's own rule for this
net class is
`antenna_check(thin_gate, perimeter_only(metal, 0.54.um), 400, [diode, 800])`,
where the `[diode, 800]` credit is exactly the discharge path each of
these nets has. Corroborated against that deck (below): **zero
violations** on the same GDS. All three verdicts are false positives of
the documented area approximation, owned upstream by
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975)
(the name-lookup companion gap is
[2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976));
no layout change is made here, per issue #1082's instruction not to
assign a layout fix a suspected physical violation does not support.

## Foundry-deck corroboration

The PDK's own antenna deck was run on the same committed GDS (open_pdks
`gf180mcuD` `c6d73a35`, deck
`libs.tech/klayout/tech/drc/rule_decks/antenna.drc` at the commit the
klt table itself cites):

```
klayout -b -r antenna.drc -rd input=<pll_top.gds> \
  -rd report=pll_top.lyrdb -rd run_mode=deep -rd metal_level=5LM \
  -rd metal_top=11K -rd thr=2   # KLayout 0.30.12, the repository's
  # pin; log committed as pll_top.stdout.log
# exit 0; pll_top.lyrdb: 0 items
```

Full log and report database committed here
([`pll_top.stdout.log`](pll_top.stdout.log), [`pll_top.lyrdb`](pll_top.lyrdb)).

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt 0.9.2)
on this envelope returns, verbatim:

```
supply_spec_disclosed_tool_limitation
```

with `ties_disclosure_reason` the spec's own recorded disclosure (the
assembled top level's one Nwell layer shared by differently-supplied
blocks, no marker layer to select each supply's wells on — quoted in
full in `../erc-supply-spec.json`'s `ties_disclosure`). This is no longer
`not_checked` and not `supply_spec_incomplete`; the remaining reason is
the same tool limitation the 0.8.0 envelope already carried, and what
would remove it is owned by
[#1085](https://github.com/2AMLogic/gf180-pll/issues/1085) (a well-class
marker layer in the layout, or the upstream well-side selector of
[2AMLogic/klayout-tools#2540](https://github.com/2AMLogic/klayout-tools/issues/2540)).
The disclosure is deliberately not relaxed or removed to get a pass; the
item stays unmet, and the manifest is not changed by #1082.
