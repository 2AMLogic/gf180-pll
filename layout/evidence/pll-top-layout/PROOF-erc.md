# `pll_top` structural power-delivery ERC (T1 checklist item 11, tracker #127)

First `klt erc` supply-spec run on the **assembled top level** (`pll_top.gds`,
issue #297). Until now every `klt erc` report in this repository was per block;
`PROOF.md` limitation 5 said no ERC had been run on the top level. This run asks
the structural question the per-block runs cannot: after the blocks are placed
and the top-level supply routing is drawn, does each declared supply still
resolve to one electrical island, and does any supply touch another?

**Result: `erc_status: violations`, one finding, and it is the `VDD_VCO`
two-island finding that `vco_block` already carries.** The four other supplies
(`VDD`, `VSS`, `GND_VCO`, `VDD_DIV`) each resolve to exactly one island across
the whole chip, and there is no `erc.supply_short` between any pair, including
`VSS` and `GND_VCO`. The top-level routing therefore adds no supply-continuity
defect. This does **not** meet item 11: a declared supply still has two islands,
and the well-tie half is not graded here (see "Limits").

## Artifacts

| File | What it is |
|---|---|
| [`erc-supply-spec.json`](erc-supply-spec.json) | Spec: gate+conductor stackup Poly2..Metal5 with Contact..Via4, the five supplies of `design/netlist/pll_top.spice`, and a `ties_disclosure`. Label layers 34/10, 36/10, 81/10 are declared because each was counted to carry supply text in this GDS. |
| [`erc-report.json`](erc-report.json) | The run below, against the exact `pll_top.gds` committed alongside it. |
| [`negative-control/make_cut.py`](negative-control/make_cut.py) | Builds the deliberately broken layout used as the detection control. |

## Provenance and reproduction

`klt 0.6.0` (the release `.github/workflows/ci.yml` installs), run through a
throwaway environment, not the host tool: KLayout (Python engine) 0.30.12,
`--deck gf180mcu` (`released: false`, content hash in the report).

```
$ uvx --from "klayout-tools==0.6.0" klt erc --top pll_top --deck gf180mcu --format json \
    layout/evidence/pll-top-layout/pll_top.gds \
    layout/evidence/pll-top-layout/erc-supply-spec.json > layout/evidence/pll-top-layout/erc-report.json
$ sha256sum pll_top.gds
111d9ae0760bfc5bbd31b964360ceb2890700cb3b25aea58e9f454d042d3ddeb  pll_top.gds
```

The report's `provenance.input.content_hash` is that digest and
`provenance.spec.content_hash` is the committed spec's; a second run is
byte-identical. Exit status is 3 (findings present), as for the VCO block.

## What was checked

`erc_coverage.checked` holds 281 entries: 276 `erc.floating_gate` (one per gate
net) and one `erc.net_connectivity` per declared supply (`VDD`, `VSS`,
`VDD_VCO`, `GND_VCO`, `VDD_DIV`). `erc.missing_tie` is `inapplicable`
(`no_ties_declared`); nothing is skipped or unknown in the connectivity scope.

| Supply | Islands at top level | Note |
|---|---|---|
| `VDD` | 1 | pfd_cp and lock_detector; joined only through the top-level star wiring |
| `VSS` | 1 | all blocks except the VCO |
| `GND_VCO` | 1 | |
| `VDD_DIV` | 1 | |
| `VDD_VCO` | **2** | the finding below |

### The one finding

`erc.unconnected_net`: `VDD_VCO` resolves to 2 islands, a 25-shape Poly2 island
(bbox (980.06, -21.00)-(1205.99, 184.10) um) and a
single-shape Metal1 island ((999.50, 29.50)-(1105.26, 30.34) um). It is the same
shape of finding as `../vco-layout/erc-report.json` (a 21-shape Poly2 island and
a single Metal1 island), now at the VCO's position in the top level; the
top level did not create it and the routing does not remove it. The
`PROOF-erc.md` of `../vco-layout/` records why the second island is joined to
the first through the shared n-well, which `klt erc` has no model to credit; it
is not re-diagnosed here.

## Negative control: the check does detect a broken supply

A clean result for four supplies is only informative if the same run would fail
on a real break. `negative-control/make_cut.py` subtracts the box
(1250.000, 240.000)-(1265.000, 250.000) um from Metal2..Metal5 and Via2..Via4 of
the flattened `pll_top.gds`. Same spec, same command, on the cut layout
(`klt 0.6.0`):

* `VSS` resolves to **2** islands (a Metal1 + Metal2 island and the rest), an
  `erc.unconnected_net` that the unmodified layout does not have;
* the inherited `VDD_VCO` finding is unchanged; no other supply changes.

The box was not chosen to hit `VSS`; it was aimed at the `VDD_DIV` riser and
landed on a `VSS` wire, which is why the control demonstrates `VSS` and not
`VDD_DIV`. `VDD_DIV`'s, `VDD`'s and `GND_VCO`'s detection is therefore
**not** separately demonstrated. The cut GDS (3.9 MB) is not committed; rerun
`make_cut.py` on `pll_top.gds` to regenerate it.

## Antenna coverage: zero, declared

`"pdk": null`; `coverage` (scope `antenna`) is `checked: []`, `skipped: 1380`
(276 gates x 5 levels), reason `missing_antenna_pdk` on every one. `klt erc
--pdk` offers no gf180mcu antenna-ratio table, so every ratio is computed and
graded against nothing. No antenna claim is made.

## Limits

1. **Item 11 is not met by this run.** `VDD_VCO` has two islands, and the item
   needs every declared supply on exactly one.
2. **No well-tie grading at the top level.** One `ties[]` entry grades every
   shape of its `well_layer` against one net, and the top level's single Nwell
   layer holds wells of several supplies with no marker layer to select on
   (`ties_disclosure`, `kind: tool_limitation`). Each block's own report grades
   its ties.
3. **Label-bounded island count.** Supplies are identified by label text; the
   Metal5 pins are one text per supply, a weak bound on how many islands a net
   could be split into. The negative control shows a cut is seen, not that
   every possible split is.
4. **Not LVS.** This is a structural island check. It says nothing about
   whether the devices on each net are the right ones (#149).
5. **Not IR-drop or EM.** Most supply risers are single vias (`PROOF.md`
   limitation 6); nothing here analyses them.
