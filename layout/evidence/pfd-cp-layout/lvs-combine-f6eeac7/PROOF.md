# `pfd_cp` LVS re-derived on the open_pdks `f6eeac7` runset with `--combine` (issue #980)

Re-establishes the `pfd_cp` block-level LVS match on the PDK revision
`sim/pdk.json` pins (open_pdks `f6eeac7`). The committed pre-re-pin records
stay untouched. Mechanism and ruling: **DR-043**; the block-level
fold-decomposition baseline and the measured width-sum rounding (78.87u vs
78.88u) are recorded on `vco_block`
(`../vco-layout/lvs-nocombine-f6eeac7/`, `../vco-layout/lvs-combine-f6eeac7/`).

## Invocation

```bash
python3 layout/run_pv.py lvs layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.spice \
  --top pfd_cp --run-dir <rundir>
```

(`--lvs-sub` at its `VSS` default; `--combine` is `layout/harness/lvs.py`'s
default since DR-043.)

## Result

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfd_cp` LVS, deck verdict | match | `Congratulations! Netlists match.` | **MATCH** |
| Device cards, layout side | 168 (the flattened reference's count) | 168 (`pfd_cp.cir`) | **MATCH** |
| Deck options | — | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` | quoted |

This block owns the `W=48u` folded cards the top-level decomposition called
out (`2x24u` each): the combined extraction carries four `W=48U` cards
matching their reference cards, with the width sum settled by the same
combiner behaviour measured on `vco_block`.

## Negative control

`layout/evidence/inv-tb-combine-f6eeac7/` re-runs `run_pv.py prove` with
`--combine` on; the `faults.inject_lvs_mismatch` control still mismatches.

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:52 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — **off the 0.28.16 pin**: no 0.28.16 binary exists on the capturing host; disclosed per-file in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`). The on-pin engine warrant for this block's match stays `lvs-clean/lvs.stdout.log` (`c6d73a35` deck, 0.28.16). |
| GDS | `layout/evidence/pfd-cp-layout/pfd_cp.gds`, sha256 `212c27c4a209c2d851d0e424ee9c4c75c040b5824a77a8a2763a3d9f7b7030d9` |
| Reference | `lvs-clean/pfd_cp.spice` (the claim-bearing flattened reference), sha256 `8559f96d532888fce22b868b3af70cd25afc48b148012357c5b287e8ebf38cdb` — unmodified |
| Deck log | `Selected SIMPLIFY option: false` / `Selected COMBINE option: true` / `Congratulations! Netlists match.`, deck run time 4.51 s |
| Artifacts | `lvs.stdout.log`, `pfd_cp.cir` (168 cards), `pfd_cp.lvsdb`, `path-normalisation.txt` |

## What this record does NOT claim

No `pll_top`-level claim (split to #987); no engine-pin claim (KLayout row
above); the same `--combine` blind spot DR-043 records applies.
