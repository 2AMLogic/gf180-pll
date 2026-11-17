# `vco_block` LVS re-derived on the open_pdks `f6eeac7` runset with `--combine` (issue #980)

This record re-establishes the `vco_block` block-level LVS match on the PDK
revision `sim/pdk.json` currently pins (open_pdks `f6eeac7`), whose runset no
longer merges parallel devices before comparison. The committed pre-re-pin
records stay as they are — valid for the deck their own provenance tables
name. Mechanism and ruling: **DR-043**
(`spec/decision-records/DR-043-lvs-combine-devices-on-the-f6eeac7-runset.md`).

## Why the old record could not simply be re-read

The `c6d73a35`-era deck logged `Selected SIMPLIFY option: true`: its netlist
simplification merged the separately drawn, parallel-connected fold segments
of a multi-finger device back into one summed-width device before
comparison. The `f6eeac7` runset logs `Selected SIMPLIFY option: false`, so
each drawn fold segment extracts as its own transistor. This run pair shows
the consequence on this exact GDS and reference, before and after `--combine`:

| Run (`lvs.stdout.log`) | SIMPLIFY | COMBINE | Verdict | Extracted device cards |
|---|---|---|---|---|
| `../lvs-nocombine-f6eeac7/` (baseline, runset defaults) | `false` | `false` | `ERROR : Netlists don't match` | **81** vs the reference's 66 |
| this directory (`--combine`) | `false` | `true` | `Congratulations! Netlists match.` | **66** == the reference's 66 |

The baseline's 15 surplus cards decompose into exact fold segments —
`8 x W=9.86U` (the reference's `W=78.87u nf=8` card), `4 x W=15U` (`W=60u`
`nf=4`), `2 x W=13.25U` (`W=26.5u`), `2 x W=8.61U` (`W=17.22u`), `2 x
W=4.305U` (`W=8.61u`) — with no wiring delta, the same signature the first
top-level `pll_top` run reported (`pll-top-layout/lvs-20261116/`, open PR
#981). This is the block-level reproduction of issue #980's problem
statement.

## The width-sum rounding, measured (issue #980's named open risk)

`combine_devices` sums parallel widths: the eight `W=9.86U` segments combine
to `M$21 VDD_VCO \$23 VBN VDD_VCO pfet_03v3 L=1U W=78.88U` (`vco_block.cir`)
against the reference's `M_MC1 ... W=78.88u L=1.0u` card. This block's own
reference already states the deck-quantized per-fold sum (`8 x 9.86u`), the
same value the combiner produces, so the widths agree exactly — and the
differential probes in `../lvs-combine-width-sensitivity-f6eeac7/` show the
comparer enforces that exactness: a reference 10 nm short (`W=78.87u`)
**mismatches**. There is no width tolerance to rely on. The `78.87u` card
the issue quotes is the top-level composer's (open PR #981) — see the
sensitivity record for what that means for #987.

## Invocation

```bash
python3 layout/run_pv.py lvs layout/evidence/vco-layout/vco_block.gds \
  layout/evidence/vco-layout/decap-20261009/vco_block.spice \
  --top vco_block --lvs-sub GND_VCO --run-dir <rundir>
```

`--combine` is `layout/harness/lvs.py`'s default since DR-043 (the command
above needs no extra flag; `combine=False` reproduces the baseline run).

## Negative control

`layout/evidence/inv-tb-combine-f6eeac7/` re-runs the harness's own
`run_pv.py prove` (fault injection included) with `--combine` on: the
`faults.inject_lvs_mismatch` control still reports
`ERROR : Netlists don't match`. Combine has not blunted the check.

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:52 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — **off the 0.28.16 pin**: no 0.28.16 binary exists on the capturing host; disclosed per-file in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`). The on-pin engine warrant for this block's match stays `lvs-recheck-klayout-0.28.16/` (`c6d73a35` deck). |
| GDS | `layout/evidence/vco-layout/vco_block.gds`, sha256 `4f5151dfbcd2d43694bfc845a507fbd43974559f1e1f8c4a8b6064afe95deb3c3` |
| Reference | `decap-20261009/vco_block.spice`, sha256 `8a948654b05e32752a0f68d47ed6fc5d2033a25dcb19f8bab5ad192ddc93a821` — unmodified; 65 MOSFET/resistor cards + the `C_XCDEC1 ... M=2` decap card |
| Deck log | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` / `POLY_RES Selected is 3k` (DR-009's shim) / `Congratulations! Netlists match.`, deck run time 5.04 s |
| Artifacts | `lvs.stdout.log`, `vco_block.cir` (66 cards), `vco_block.lvsdb`, `path-normalisation.txt` |

## What this record does NOT claim

- No `pll_top`-level claim: the composed top-level reference re-run is split
  to #987 (its composer and evidence directory live in open PR #981).
- No engine-pin claim: see the KLayout row above.
- What `--combine` can no longer distinguish (per DR-043): a layout wrongly
  drawn as N separate-but-parallel devices where the design intends one wide
  device compares equal to the single intended card. What remains visible:
  a dropped fold finger
  (`../lvs-combine-width-sensitivity-f6eeac7/width-onefold-short/`) and an
  opened net (`../inv-tb-combine-f6eeac7/`) each still mismatch.
