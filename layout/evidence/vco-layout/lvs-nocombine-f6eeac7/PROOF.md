# `vco_block` LVS baseline on the `f6eeac7` runset at the runset's own defaults — the fold-decomposition mismatch (issue #980)

This is **not** an LVS-clean record. It is the control run that motivates
DR-043 and the sibling `../lvs-combine-f6eeac7/` match: the same committed
GDS and the same committed reference netlist, run identically **except**
`--combine` is not passed (`layout/harness/lvs.py`'s `combine=False`), i.e.
exactly what the `f6eeac7` runset does on its own defaults.

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `vco_block` LVS, runset defaults | (demonstrates the gap) | `ERROR : Netlists don't match` | **MISMATCH — the fold decomposition, nothing else** |
| Extracted device cards | 66 (the reference's count) | **81** | 15 surplus cards |
| Deck options | `Selected SIMPLIFY option: false`, `Selected COMBINE option: false` | same | — |

The 15 surplus cards in `vco_block.cir` are exactly the drawn fold segments
the reference states as one card each: `8 x W=9.86U` (vs `W=78.87u nf=8`),
`4 x W=15U` (vs `W=60u`), `2 x W=13.25U` (vs `W=26.5u`), `2 x W=8.61U` (vs
`W=17.22u`), `2 x W=4.305U` (vs `W=8.61u`). No wiring delta appears; the
same signature the first top-level `pll_top` LVS run decomposed
(`pll-top-layout/lvs-20261116/`, open PR #981: 816 extracted MOSFETs vs 799
reference cards). Passing `--combine` merges exactly these cards on both
sides and the match returns (`../lvs-combine-f6eeac7/`).

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:53 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — off the 0.28.16 pin, disclosed in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`); deliberately at runset defaults |
| GDS / reference | identical to `../lvs-combine-f6eeac7/`'s (sha256 values in that record) |
| Invocation | as `../lvs-combine-f6eeac7/` with `combine=False`, deck run time 4.37 s |
| Artifacts | `lvs.stdout.log`, `vco_block.cir` (81 cards), `vco_block.lvsdb`, `path-normalisation.txt` |
