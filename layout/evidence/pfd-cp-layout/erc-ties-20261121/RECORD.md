# Well-tie ERC on `pfd_cp` (issue #1085)

First `klt erc` run on this block that **grades the well-tie half instead of
disclosing it**. The committed [`../erc-supply-spec.json`](../erc-supply-spec.json)
declares a `ties_disclosure` of kind `tool_limitation`: with the selectors the
0.6.0 pin shipped, the block's two well classes (fourteen `VDD` device-body tubs
and the dump buffer's `cp.PSRC` body tub) could not be declared separately, and
a single `ties[]` entry would have graded a false `erc.missing_tie` onto the
PSRC tub. `klayout-tools` 0.9.2 -- the current `.github/workflows/ci.yml` pin
-- added the literal well-side selectors `well_requires_boxes` /
`well_excludes_boxes` ([2AMLogic/klayout-tools#2540](https://github.com/2AMLogic/klayout-tools/issues/2540)),
which select whole merged wells by interaction with caller-named boxes. This
envelope declares both classes with them, on the existing GDS, with no layout
edit. It replaces the disclosure **with a computed result**, and the computed
result is a finding -- the honest outcome for a body tie the tool cannot see
electrically, because no label names `PSRC` anywhere in this stream.

## Why the spec copy beside this report differs from the committed one

[`erc-supply-spec.json`](erc-supply-spec.json) here is a **copy of the committed
spec with exactly two deltas**: (1) the `ties_disclosure` is replaced by the
two-entry `ties[]` partition below; (2) the stackup entry names use the gf180mcu
antenna table's canonical spelling (`metal1`→`Metal1` 34/0, `metal2`→`Metal2`
36/0, `metal3`→`Metal3` 42/0, `vias[].between` renamed to match) so
`--pdk gf180mcu` grades the antenna half in the same run
([2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976);
the same rename issue #1082's antenna re-run uses). Nothing else changed. The
committed spec stays byte-unchanged at its recorded path so
[`../erc-report.json`](../erc-report.json) keeps resolving its own
`provenance.spec.content_hash`.

### The partition

| class | selector | wells | tap boolean | net |
|---|---|---|---|---|
| `nwell_vdd` | `well_excludes_boxes: [[180, 8, 181, 9]]` | 14 | `Comp ∩ Nplus` | `VDD` |
| `nwell_psrc` | `well_requires_boxes: [[180, 8, 181, 9]]` | 1 | `Comp ∩ Nplus` | `PSRC` |

The box `[180, 8, 181, 9]` µm lies strictly inside the fifteenth merged Nwell
`(176.820, 7.755)`–`(279.820, 12.555)` µm and interacts with no other well
(verified by erosion: the box minus the merged Nwell region is empty), so the
two entries partition all fifteen drawn Nwell shapes disjointly and
exhaustively -- 14 + 1 = the 15 merged shapes `klayout.db` counts on this GDS.
The tap is the boolean gf180mcu draws an n-well tap as, `Comp (22/0)` narrowed
by `Nplus (32/0)`, wired to `Metal1`. The p-substrate half stays undeclared for
the reason already measured in
[`../lock-detector-layout/PROOF-erc.md`](../lock-detector-layout/PROOF-erc.md)
(a caller-asserted native substrate region grades `degenerate_well_assertion`);
this spec, like the one it copies, makes no substrate claim.

## Command

```
klt erc --top pfd_cp --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/erc-ties-20261121/erc-supply-spec.json \
  > layout/evidence/pfd-cp-layout/erc-ties-20261121/erc-report.json
# exit 3 (the tie finding below; the connectivity half otherwise clean)
```

- klt: `0.9.2` (released wheel, `.github/workflows/ci.yml` pin), git commit
  `e109054112336b1ff537043a860adf120b84e49c`, run through a throwaway venv
  (`python3 -m venv && pip install klayout-tools==0.9.2`), not the host tool
- KLayout: `0.30.13` (the wheel's own dependency)
- layout input `pfd_cp.gds` (unchanged from `../erc-report.json`'s):
  `sha256:212c27c4a209c2d851d0e424ee9c4c75c040b5824a77a8a2763a3d9f7b7030d9`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:ea058c15675580190bb69310d0151ec541c2be6d24d5b75f424cea2c66bc91fc`

Both hashes verified against `erc-report.json`'s own
`provenance.input`/`provenance.spec.content_hash`, and re-verified afterwards
with `klt erc --check erc-report.json` (status `match`, all three provenance
hashes OK, exit 0).

## Result

| field | deck-only run (`../erc-report.json`) | this run |
|---|---|---|
| `status` | `not_checked` | `violations` (exit 3) |
| `erc_status` | `clean` | `violations` |
| `pdk` | `null` | `gf180mcu` (built-in) |
| `erc_coverage.checked` | 75 | 79 (adds `erc.missing_tie` x2, `erc.supply_short` + `.substrate`) |
| `erc_coverage.skipped` | 0 | **0** |
| `erc_coverage.inapplicable` | 2 | **0** |
| `checked_by_well_assertion` | (absent) | both classes |

`erc_coverage.inapplicable` drops to empty: the `ties_disclosed_tool_limitation`
entry is gone because the disclosure it described is gone, and the
`erc.supply_short`/`substrate_isolation_undecidable` entry became checked work
(`erc.supply_short`, `erc.supply_short.substrate`) under this spec. No
`erc.missing_tie` class is skipped, degenerate or disclosed, and both declared
classes appear in `erc_coverage.checked_by_well_assertion`:

```json
"checked_by_well_assertion": [
  "erc.missing_tie:[\"nwell_psrc\"]",
  "erc.missing_tie:[\"nwell_vdd\"]"
]
```

### The one finding, quoted

```json
{
 "rule": "erc.missing_tie",
 "description": "well/tub tap is not connected to declared net 'PSRC'",
 "net": "PSRC",
 "layer": "nwell_psrc",
 "bbox": { "left": 176820, "bottom": 7755, "right": 279820, "top": 12555 }
}
```

Raw database units `[176820, 7755, 279820, 12555]` (dbu 0.001 µm), i.e.
`(176.820, 7.755)`–`(279.820, 12.555)` µm -- the same fifteenth well the
block's own partition measurement names. `klt erc` matches a tie's target net
by label, this stream draws no `PSRC` text on any label layer, so the tap --
which really does tie the tub to its pfet sources -- cannot be credited
electrically and the check reports the well as untied to the declared net.
That is a computed, falsifiable result about the tool's view, not a claim that
the silicon is wrong: the physical body tie is independently established by the
PDK's own device-aware LVS extraction (the well, its tap and its metal rail
are all net `$30` in the committed [`../lvs-clean/pfd_cp.lvsdb`](../lvs-clean/pfd_cp.lvsdb),
the net [`../connectivity/pfd_cp.netcheck.log`](../connectivity/pfd_cp.netcheck.log)
names `cp.PSRC`) -- see
[`../PROOF-erc.md`](../PROOF-erc.md) → "It is deliberate, and three
independent sources say so".

### Negative control: the finding tracks the declared net, not the box

Retargeting only the `nwell_psrc` entry's `net` to `VDD` in a scratch copy of
this spec (not committed) and re-running the identical command reports the
**same rule at the same bounding box** naming `VDD`:

```json
{ "rule": "erc.missing_tie",
  "description": "well/tub tap is not connected to declared net 'VDD'",
  "net": "VDD", "layer": "nwell_psrc",
  "bbox": { "left": 176820, "bottom": 7755, "right": 279820, "top": 12555 } }
```

So the finding is computed from the declared target net at that well: the
selector picks the well, the net decides what the finding says. Exit 3, both
classes still `checked_by_well_assertion`, nothing skipped.

## Antenna half (kept enabled)

`--pdk gf180mcu` is on, so the antenna half is graded in the same run:
`coverage.checked` **219**, `skipped` 0, `inapplicable` 73 (all
`gate_reference_level`, expected). Two gate nets violate -- `gate4`/`VSS`
(ratio 558.595333 at Metal1, violating Metal1..Metal3) and `gate11`/`VDD`
(771.320667 at Metal1, Metal1..Metal3) -- the same two rail-tied gate nodes,
with identical ratios, that issue #1082's antenna re-run of this GDS records
and corroborates against the foundry deck (open PR #1088; both are documented
false positives of the table's area approximation, owned upstream by
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975)).
Declaring `ties[]` changed no antenna verdict, as the tool's own contract
guarantees.

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt 0.9.2) on
this envelope resolves the spec (2 supply nets, `tie_count: 2`) and returns,
verbatim:

```
supply_not_continuous
```

`erc.missing_tie` is one of the five rules the item-11 ERC half grades, so the
reported PSRC finding legitimately blocks the item. Item 11 therefore stays
`unmet` on this evidence -- by measurement now, not by disclosure.
