# `lock_detector` LVS re-derived on the open_pdks `f6eeac7` runset with `--combine` (issue #980)

Re-establishes the `lock_detector` block-level LVS match on the PDK revision
`sim/pdk.json` pins (open_pdks `f6eeac7`). The committed pre-re-pin records
stay untouched. Mechanism and ruling: **DR-043**; the block-level
fold-decomposition baseline and the measured width-sum rounding are recorded
on `vco_block` (`../vco-layout/lvs-{no,}combine-f6eeac7/`).

## Invocation

```bash
python3 layout/run_pv.py lvs layout/evidence/lock-detector-layout/lock_detector.gds \
  layout/evidence/lock-detector-layout/lvs-clean/lock_detector.spice \
  --top lock_detector --run-dir <rundir>
```

(`--lvs-sub` at its `VSS` default; `--combine` is `layout/harness/lvs.py`'s
default since DR-043.)

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `lock_detector` LVS, deck verdict | match | `Congratulations! Netlists match.` | **MATCH** |
| Device cards, layout side | 117 (the reference's count) | 117 (`lock_detector.cir`) | **MATCH** |
| Deck options | — | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` | quoted |

## Negative control

`layout/evidence/inv-tb-combine-f6eeac7/` re-runs `run_pv.py prove` with
`--combine` on; the `faults.inject_lvs_mismatch` control still mismatches.

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:52 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — **off the 0.28.16 pin**: no 0.28.16 binary exists on the capturing host; disclosed per-file in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`). The on-pin engine warrant for this block's match stays `lvs-clean/lvs.stdout.log` (`c6d73a35` deck, 0.28.16); `lvs-recheck-klayout-0.30.10/` additionally re-derived it on a second engine. |
| GDS | `layout/evidence/lock-detector-layout/lock_detector.gds`, sha256 `799af5d7f6b8407c5efc50b7e8ef639a8aa8787eb91b47e1f31f66f1673b2c0c` |
| Reference | `lvs-clean/lock_detector.spice` (the claim-bearing flattened reference), sha256 `a616b09c52530f481ea49e6ddaf8d68b3ab1483c36d1ca75cbb8f82ec6ba04d5` — unmodified |
| Deck log | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` / `Congratulations! Netlists match.`, deck run time 4.29 s |
| Artifacts | `lvs.stdout.log`, `lock_detector.cir` (117 cards), `lock_detector.lvsdb`, `path-normalisation.txt` |

## What this record does NOT claim

No `pll_top`-level claim (split to #987); no engine-pin claim (KLayout row
above); the same `--combine` blind spot DR-043 records applies.
