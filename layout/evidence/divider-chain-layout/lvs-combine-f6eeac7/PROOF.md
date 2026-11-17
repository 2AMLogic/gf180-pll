# `divider_chain` LVS re-derived on the open_pdks `f6eeac7` runset with `--combine` (issue #980)

Re-establishes the `divider_chain` block-level LVS match on the PDK revision
`sim/pdk.json` pins (open_pdks `f6eeac7`). The committed pre-re-pin records
stay untouched. Mechanism and ruling: **DR-043**; the block-level
fold-decomposition baseline and the measured width-sum rounding are recorded
on `vco_block` (`../vco-layout/lvs-{no,}combine-f6eeac7/`).

## Invocation

```bash
python3 layout/run_pv.py lvs layout/evidence/divider-chain-layout/divider_chain.gds \
  layout/evidence/divider-chain-layout/divider_chain.spice \
  --top divider_chain --run-dir <rundir>
```

(`--lvs-sub` at its `VSS` default; `--combine` is `layout/harness/lvs.py`'s
default since DR-043.)

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `divider_chain` LVS, deck verdict | match | `Congratulations! Netlists match.` | **MATCH** |
| Device cards, layout side | 452 (226 `pfet_03v3` + 226 `nfet_03v3`, the reference's count) | 452 (`divider_chain.cir`) | **MATCH** |
| Deck options | — | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` | quoted |

## Negative control

`layout/evidence/inv-tb-combine-f6eeac7/` re-runs `run_pv.py prove` with
`--combine` on; the `faults.inject_lvs_mismatch` control still mismatches.

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:52 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — **off the 0.28.16 pin**: no 0.28.16 binary exists on the capturing host; disclosed per-file in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`). The on-pin engine warrant for this block's match stays `lvs-clean/lvs.stdout.log` (`c6d73a35` deck, 0.28.16). |
| GDS | `layout/evidence/divider-chain-layout/divider_chain.gds`, sha256 `bb5d78a0f80130bd8fbcc766b0e71d07493c7d0e5c92edf549044f66a7704404` |
| Reference | `divider_chain.spice` (the committed block-root flattened reference), sha256 `c167dabb0cc31be1def3c31ee37f2a56fe85543b5d59ac47fca577041459ac7a` — unmodified |
| Deck log | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` / `Congratulations! Netlists match.`, deck run time 5.09 s |
| Artifacts | `lvs.stdout.log`, `divider_chain.cir` (452 cards), `divider_chain.lvsdb`, `path-normalisation.txt` |

## What this record does NOT claim

No `pll_top`-level claim (split to #987); no engine-pin claim (KLayout row
above); the same `--combine` blind spot DR-043 records applies.
