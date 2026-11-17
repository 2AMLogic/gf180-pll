# Width sensitivity of the `--combine` comparison on the `f6eeac7` runset (issue #980)

Two differential probes on the committed `vco_block.gds` (sha256 in
`../lvs-combine-f6eeac7/PROOF.md`), run under the DR-043 invocation
(`--combine` on, `POLY_RES 3k`), each against a **scratch copy** of the
committed reference with exactly one character of one card changed. The
layout side and the extraction are identical to the match run's — `M$21
VDD_VCO \$23 VBN VDD_VCO pfet_03v3 L=1U W=78.88U` appears verbatim in both
probes' `vco_block.cir` — so any verdict change is attributable to the
reference card's width alone.

| Probe | `M_MC1` reference card | Verdict | Meaning |
|---|---|---|---|
| `width-10nm-short/` | `W=78.87u` (10 nm below the extracted `W=78.88U`) | `ERROR : Netlists don't match` | **The comparer has no width tolerance: 10 nm mismatches.** |
| `width-onefold-short/` | `W=69.01u` (one 9.86 u fold fewer) | `ERROR : Netlists don't match` | A dropped fold finger is not absorbed either. |
| (control: unmodified reference) | `W=78.88u` | `Congratulations! Netlists match.` | `../lvs-combine-f6eeac7/` |

## What this settles, and for whom

- Issue #980's named open risk — "whether KLayout's compare tolerance
  absorbs a 10 nm sum difference (78.87u vs 78.88u) is untested" — is
  answered **in the negative**: a 10 nm width delta on one card is a
  mismatch on this deck. Nothing is absorbed; the block references match
  because they already state the deck-quantized per-fold width sum
  (`8 x 9.86u = 78.88u` — `Fet.drawn_w_um`'s convention), the same value
  the combiner produces on the extraction side.
- **Consequence for the top-level re-run (#987 / open PR #981):** the
  composed `pll_top` reference's fold cards, which the issue quotes at
  `W=78.87u`, will not match under `--combine` as written — the composer
  must state the quantized per-fold sum (`78.88u` for that card), exactly as
  the block-level generators already do. Without this probe that residual
  would have surfaced as an undiagnosed one-card mismatch in the top-level
  record.

The scratch references are not committed (single-character `sed` deltas of
the committed reference). Each run's log names the scratch netlist file it
read (`Input schematic file: .../vco_block_10nm_short.spice`) but carries no
hash of it, so the substitution itself rests on this record's statement of
it above; what the logs and the committed `vco_block.cir` do establish
independently is that the layout side and the extraction were identical to
the match run's.

## Provenance

| | |
|---|---|
| Runs | 2026-11-17 01:00 UTC |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the `sim/pdk.json` pin) |
| KLayout | `0.30.12` — off the 0.28.16 pin, disclosed in `layout/lib/check-layout-status-claims.sh` (`OFF_PIN_DISCLOSED`) |
| Invocation | `layout/harness/lvs.py` default (`--combine`), `--lvs_sub=GND_VCO`, reference = scratch `sed` copy of `decap-20261009/vco_block.spice` |
| Artifacts | per probe: `lvs.stdout.log` (verdict + `Selected SIMPLIFY option: false` / `Selected COMBINE option: true`), `vco_block.cir`, `path-normalisation.txt`. No `.lvsdb`: the extraction is identical to the committed match run's, which carries one. |
