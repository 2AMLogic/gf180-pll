# Well-tie ERC on `pll_top` (issue #1085)

First `klt erc` run on the assembled top level that **grades the well-tie
half instead of disclosing it**. The committed
[`../erc-supply-spec.json`](../erc-supply-spec.json) declares a
`ties_disclosure` of kind `tool_limitation`: the assembly's single Nwell layer
holds the differently-biased tubs of four blocks plus the loop filter's
capacitor bodies, one `ties[]` entry grades every shape of the layer against
one net, and no drawn layer separates the classes. `klayout-tools` 0.9.2 -- the
current `.github/workflows/ci.yml` pin -- added the literal well-side
selectors `well_requires_boxes` / `well_excludes_boxes`
([2AMLogic/klayout-tools#2540](https://github.com/2AMLogic/klayout-tools/issues/2540)),
so each class is now declared against its own net, selected by one
caller-named box strictly inside each of its wells. This envelope replaces the
disclosure **with computed results** on the existing GDS, with no layout edit.

## Why the spec copy beside this report differs from the committed one

[`erc-supply-spec.json`](erc-supply-spec.json) here is a **copy of the committed
spec with exactly two deltas**: (1) the `ties_disclosure` is replaced by the
five-entry `ties[]` partition below; (2) the stackup entry names use the
gf180mcu antenna table's canonical spelling (`metal1`→`Metal1` …
`metal5`→`Metal5`, `vias[].between` renamed to match) so `--pdk gf180mcu`
grades the antenna half in the same run
([2AMLogic/klayout-tools#6976](https://github.com/2AMLogic/klayout-tools/issues/6976);
the same rename issue #1082's antenna re-run uses). Nothing else changed. The
committed spec stays byte-unchanged at its recorded path so
[`../erc-report.json`](../erc-report.json) keeps resolving its own
`provenance.spec.content_hash`.

## The partition, and how it was derived

The assembly draws **forty** merged Nwell (21/0) shapes. Each class's
`well_requires_boxes` list contains one box strictly inside each well of that
class, derived by placing a probe in each child cell's own wells and applying
the placement transform (`klayout.db` on this GDS: `lock_detector` `m90`,
`pfd_cp` `m90` -- mirrored, as issue #1085 notes -- `loop_filter` `r0`,
`vco_block` `r0`, `divider_chain` `r180`), then re-reconciled against the
merged top-level geometry: every transformed probe lands in exactly one
top-level merged well, no well is hit twice, and none is left over.

| class | wells | placement | tap boolean | net |
|---|---|---|---|---|
| `nwell_vdd` | 15 | lock_detector (1) + pfd_cp (14) | `Comp ∩ Nplus` | `VDD` |
| `nwell_vdd_div` | 14 | divider_chain (r180) | `Comp ∩ Nplus` | `VDD_DIV` |
| `nwell_vdd_vco` | 6 | vco_block (r0) | `Comp ∩ Nplus` | `VDD_VCO` |
| `nwell_vss_cap_body` | 4 | loop_filter (r0) | `Comp ∩ Nplus ∩ Contact` | `VSS` |
| `nwell_psrc` | 1 | pfd_cp's PSRC tub (m90) | `Comp ∩ Nplus` | `PSRC` |
| | **40** | = every merged Nwell shape | | |

15 + 14 + 6 + 4 + 1 = 40: the partition is disjoint and exhaustive. The first
three classes are the same single-class declarations each placed block's own
committed spec already grades on its own GDS
(`../lock-detector-layout/`, `../divider-chain-layout/`, `../vco-layout/`
`erc-supply-spec.json`); the top level re-grades them in place, through the
top-level routing, at their assembled positions.

The `nwell_vss_cap_body` class needs the extra `Contact (33/0)` narrowing, and
only that class does: the loop filter's `cap_nmos_03v3_b` cells draw `Nplus`
over the **whole** `Comp` body
([`layout/pll_top/loop_filter/primitives.py`](../../../../layout/pll_top/loop_filter/primitives.py)
→ `mos_cap`), so `Comp ∩ Nplus` names no distinguishable tap inside those
wells and the pinned tool skips the class as `degenerate_tap_declaration`.
Intersecting Contact keeps exactly the physical diffusion contact columns
(`mos_cap`'s body columns) that tie each body tub to `VSS`.

## Command

```
klt erc --top pll_top --deck gf180mcu --pdk gf180mcu --format json \
  layout/evidence/pll-top-layout/pll_top.gds \
  layout/evidence/pll-top-layout/erc-ties-20261121/erc-supply-spec.json \
  > layout/evidence/pll-top-layout/erc-ties-20261121/erc-report.json
# exit 3 (the tie finding below; the connectivity half otherwise clean)
```

- klt: `0.9.2` (released wheel, `.github/workflows/ci.yml` pin), git commit
  `e109054112336b1ff537043a860adf120b84e49c`, run through a throwaway venv
  (`python3 -m venv && pip install klayout-tools==0.9.2`), not the host tool
- KLayout: `0.30.13` (the wheel's own dependency)
- layout input `pll_top.gds` (unchanged from `../erc-report.json`'s):
  `sha256:fbe4001364aa586f6bdbf1babe85cbb4d40d8fbf4560b899ee158d7f5f12b11c`
- spec input `erc-supply-spec.json` (this directory):
  `sha256:a2b60ce28bcd0f6857a81c73471da4a9ec78092d395370d48ecca24cc849f4fe`

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
| `erc_coverage.checked` | 281 | 288 (adds `erc.missing_tie` x5, `erc.supply_short` + `.substrate`) |
| `erc_coverage.skipped` | 0 | **0** |
| `erc_coverage.inapplicable` | 1 | **0** |
| `checked_by_well_assertion` | (absent) | all five classes |

No `erc.missing_tie` class is skipped, degenerate or disclosed -- in
particular the `nwell_vss_cap_body` Contact narrowing cleared the
`degenerate_tap_declaration` skip the plain two-layer tap would have produced
-- and all five declared classes appear in `erc_coverage.checked_by_well_assertion`:

```json
"checked_by_well_assertion": [
  "erc.missing_tie:[\"nwell_psrc\"]",
  "erc.missing_tie:[\"nwell_vdd\"]",
  "erc.missing_tie:[\"nwell_vdd_div\"]",
  "erc.missing_tie:[\"nwell_vdd_vco\"]",
  "erc.missing_tie:[\"nwell_vss_cap_body\"]"
]
```

### The one finding, quoted

```json
{
 "rule": "erc.missing_tie",
 "description": "well/tub tap is not connected to declared net 'PSRC'",
 "net": "PSRC",
 "layer": "nwell_psrc",
 "bbox": { "left": 372950, "bottom": 21600, "right": 475950, "top": 26400 }
}
```

Raw database units `[372950, 21600, 475950, 26400]` (dbu 0.001 µm), i.e.
`(372.950, 21.600)`–`(475.950, 26.400)` µm in top-cell coordinates -- the
placed (m90) image of the pfd_cp dump-buffer tub, whose block-level record
(`../pfd-cp-layout/erc-ties-20261121/RECORD.md`) reports the same rule on the
same well at block coordinates `(176.820, 7.755)`–`(279.820, 12.555)` µm.
`klt erc` matches a tie's target net by label, and no `PSRC` text exists
anywhere in the assembly (label layers 34/10, 36/10, 81/10 were walked), so
the tap -- which really does tie the tub to its pfet sources inside the placed
block -- cannot be credited electrically and the check reports the well as
untied to the declared net. The physical body tie is independently established
at the block level by the PDK's own LVS extraction; see
`../pfd-cp-layout/PROOF-erc.md` → "It is deliberate, and three independent
sources say so".

The four supply classes (`VDD`, `VDD_DIV`, `VDD_VCO`, `VSS` capacitor bodies)
grade **clean**: 39 of the 40 wells' taps reach exactly their declared net
through the assembly's own routing, so the class count a reader might fear was
hand-picked is corroborated by the tool finding precisely the one well that is
deliberately tied elsewhere.

## Antenna half (kept enabled)

`--pdk gf180mcu` is on, so the antenna half is graded in the same run:
`coverage.checked` **1380**, `skipped` 0, `inapplicable` 276 (all
`gate_reference_level`, expected). Three gate nets violate -- `gate17`/`XDLY_T0B`
(ratio 13.378 at Metal1), `gate21`/`GND_VCO` (711.858 at Metal1) and
`gate38`/`VDD` (857.065 at Metal1) -- the same three gate nodes, with matching
ratios (711.857909 / 857.065333), that issue #1082's antenna re-run of this
GDS records and corroborates against the foundry deck (open PR #1088; all
three are documented false positives of the table's area approximation, owned
upstream by
[2AMLogic/klayout-tools#6975](https://github.com/2AMLogic/klayout-tools/issues/6975)).
Declaring `ties[]` changed no antenna verdict, as the tool's own contract
guarantees.

## Item-11 grader (ERC half)

Calling the pinned grader
(`klayout_tools.signoff_power_delivery._resolve_erc_supply_spec`, klt 0.9.2) on
this envelope resolves the spec (5 supply nets, `tie_count: 5`) and returns,
verbatim:

```
supply_not_continuous
```

`erc.missing_tie` is one of the five rules the item-11 ERC half grades, so the
reported PSRC finding legitimately blocks the item. Item 11 therefore stays
`unmet` on this evidence -- by measurement now, not by disclosure.
