# `prove` re-run with `--combine` on — the negative control for DR-043 (issue #980)

DR-043 makes `layout/harness/lvs.py` pass `--combine` on every LVS run, so
the harness's own trustworthiness gate has to be re-demonstrated under the
new invocation: a check that merges parallel devices before comparison could
in principle absorb a fault it used to catch. This record is that
re-demonstration — the full four-check `run_pv.py prove`
(`layout/harness/faults.py`'s two deliberate negative controls included),
run with `--combine` on, in a fresh evidence directory. The original
bring-up proof at `../inv-tb-proof/` is untouched.

## Result

```bash
python3 layout/run_pv.py prove --work-dir <scratch>/prove-980 \
  --evidence-dir layout/evidence/inv-tb-combine-f6eeac7
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `inv_tb` DRC | clean | `Klayout DRC run is clean` (0 violations) | **PASS** |
| `inv_tb` LVS, `--combine` on | match | `LVS match: inv_tb (D)` — `Congratulations! Netlists match.` | **PASS** |
| DRC fault (`faults.inject_drc_violation`) | violations | `M1.1x1` reported | **PASS** (negative control) |
| **LVS fault (`faults.inject_lvs_mismatch`), `--combine` on** | **mismatch** | `ERROR : Netlists don't match` | **PASS — combine has not blunted the check** |

`prove` exit status: `PASS` (all four expectations held). The LVS deck log
for both LVS runs records `Selected SIMPLIFY option: false` and
`Selected COMBINE option: true`.

The injected LVS fault deletes the output net's Metal1 island
(`faults.inject_lvs_mismatch`), opening the shared drain node — a net-list
topology delta (a floating net), not a parallel-device count change, so no
combiner can absorb it, and the deck reports the mismatch. This is the
boundary DR-043 records: combine merges exactly parallel devices; opened
nets, dropped/duplicated non-parallel devices and other topology deltas
remain visible.

## Provenance

| | |
|---|---|
| Run | 2026-11-17 00:55 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — off the 0.28.16 pin, disclosed per-file in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`); `inv_tb` is cell-level disclosed there (harness bring-up proof, not a PLL block) |
| Artifacts | `inv_tb.gds` + `inv_tb.spice` (built by `prove`), `drc-clean/`, `lvs-clean/` (`inv_tb.cir`, `inv_tb.lvsdb`), `drc_fault.gds` + `drc-fault/`, `lvs_fault.gds` + `lvs-fault/` (`lvs_fault.cir`, `lvs_fault.lvsdb`), each with its deck log and `path-normalisation.txt` |
