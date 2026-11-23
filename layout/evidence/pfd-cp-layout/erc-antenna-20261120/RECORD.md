# Antenna-table ERC on `pfd_cp` (issue #1082)

Re-run of the supply-spec `klt erc` recorded in [`../erc-report.json`](../erc-report.json)
(see [`../PROOF-erc.md`](../PROOF-erc.md)) on the CI-pinned
`klayout-tools==0.9.2`, with the gf180mcu antenna-ratio limit table
selected (`--pdk gf180mcu`, the table 2AMLogic/klayout-tools#4003 added).
First antenna-graded ERC envelope for this block. Single-unit local run;
no corner grid.

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
36/0, `metal3`→`Metal3` 42/0); `vias[].between` references were renamed
to match; nothing else changed. The committed spec stays byte-unchanged
at its recorded path so the `../erc-report.json` envelope still resolves
its own `provenance.spec.content_hash`.

## Command

```
klt erc --top pfd_cp --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/erc-antenna-20261120/erc-supply-spec.json \
  > layout/evidence/pfd-cp-layout/erc-antenna-20261120/erc-report.json
# exit 3 (antenna violations; connectivity half clean)
```

- klt: `0.9.2` (`klt_reinstall_spec: klayout-tools==0.9.2`, the
  `.github/workflows/ci.yml` pin), git commit `046ba74652fc096bd97071fc3237f7159dd40183`
- The klt ERC run used the KLayout Python wheel `0.30.13`. The foundry
  antenna deck ran in the standalone KLayout application `0.30.12`.
- layout input `pfd_cp.gds`:
  `sha256:212c27c4a209c2d851d0e424ee9c4c75c040b5824a77a8a2763a3d9f7b7030d9`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:1b9a7146ec0f6eb1e5c58cd6545a7ab871e6a3c836b1d1c6a224c9b1fa7f4dcb`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`.

## Result

| field | deck-only 0.9.2 (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | `violations` (exit 3) |
| `erc_status` | `clean` | `clean` (0 findings) |
| `pdk` | `null` | `gf180mcu` (built-in) |
| antenna `coverage.checked` | 0 | **219** |
| antenna `coverage.skipped` | 219 (all `missing_antenna_pdk`) | **0** |
| antenna `coverage.inapplicable` | 73 | 73 (all `gate_reference_level`, expected) |
| `erc_coverage.checked` | 75 | 75 |
| `erc_coverage.inapplicable` | 2 | 2 (`ties_disclosed_tool_limitation`, `substrate_isolation_undecidable`) |

Antenna verdicts: 71 of 73 gate nets **pass** every level; two gate nets
**violate** (below). Every level now carries a real limit and source
(`antenna_ratio_max: 400.0`, rules `ANT.16_i_ANT.2`..`ANT.4` from
google/gf180mcu-pdk `f6eeac7`).

### The two violations, and why neither is acted on as a layout defect

| gate | net | gate area µm² | violating levels | ratio at Metal1 |
|---|---|---|---|---|
| `gate4` | `VSS` | 0.6 | Metal1..Metal3 | 558.595333 |
| `gate11` | `VDD` | 0.6 | Metal1..Metal3 | 771.320667 |

Both are rail-tied gate nodes (a tie-cell-shaped gate on each supply),
whose cumulative metal area in the connectivity model is the block's
whole supply rail — the same net class the vco/pll_top records hit. The
gf180mcu table's own module documents the model as an approximation that
**omits the deck's diode credit**; the foundry deck's own rule for this
net class is
`antenna_check(thin_gate, perimeter_only(metal, 0.54.um), 400, [diode, 800])`,
where the `[diode, 800]` credit is exactly the discharge path a supply
rail carries everywhere. Corroborated against that deck (below): **zero
violations** on the same GDS. Both verdicts are false positives of the
documented area approximation, owned upstream by
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
klayout -b -r antenna.drc -rd input=<pfd_cp.gds> \
  -rd report=pfd_cp.lyrdb -rd run_mode=deep -rd metal_level=5LM \
  -rd metal_top=11K -rd thr=2   # KLayout 0.30.12, the repository's
  # pin; log committed as pfd_cp.stdout.log
# exit 0; pfd_cp.lyrdb: 0 items
```

Full log and report database committed here
([`pfd_cp.stdout.log`](pfd_cp.stdout.log), [`pfd_cp.lyrdb`](pfd_cp.lyrdb)).

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt 0.9.2)
on this envelope returns, verbatim:

```
supply_spec_disclosed_tool_limitation
```

with `ties_disclosure_reason` the spec's own recorded disclosure (the
one drawn Nwell carrying the VDD-tapped class and the deliberately
cp.PSRC body-tied class, no drawn layer separating them — quoted in full
in `../erc-supply-spec.json`'s `ties_disclosure`, upstream gap
[2AMLogic/klayout-tools#2540](https://github.com/2AMLogic/klayout-tools/issues/2540)).
This is no longer `not_checked` and not `supply_spec_incomplete`; the
remaining reason is the same tool limitation the committed envelope
already carried, and what would remove it is owned by
[#1085](https://github.com/2AMLogic/gf180-pll/issues/1085). The
disclosure is deliberately not relaxed or removed to get a pass; the
item stays unmet, and the manifest is not changed by #1082.
