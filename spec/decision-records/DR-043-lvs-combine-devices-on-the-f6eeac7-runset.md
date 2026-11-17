# DR-043: Block/top-level LVS passes the f6eeac7 runset's `--combine`; references keep one card per schematic device

- **Status**: proposed — ratified only by operator approval of the PR that carries it (the two-key ceremony in `spec/README.md`).
- **Date**: 2026-11-17
- **Decided by**: Builder agent, issue #980 (direction selected by the Curator Enhancement and Champion review recorded on that issue)
- **Evidence consumed**: `layout/evidence/vco-layout/lvs-nocombine-f6eeac7/` and `layout/evidence/vco-layout/lvs-combine-f6eeac7/` (the baseline mismatch and the combine match this record decides between, both on the pinned open_pdks `f6eeac7` runset, issue #980); `layout/evidence/pll-top-layout/lvs-20261116/` (open PR #981, the first top-level run that surfaced the fold decomposition); `layout/evidence/{pfd-cp,divider-chain,lock-detector}-layout/lvs-combine-f6eeac7/` (the other three blocks on the same invocation).

## Context

The four block-level LVS-match records (vco, pfd_cp, divider_chain, lock_detector) were captured on the `c6d73a35`-era deck, whose runset merged parallel devices in the extracted netlist before comparison (`Selected SIMPLIFY option: true` in those logs). The repo's PDK pin moved to open_pdks `f6eeac7` (`sim/pdk.json`, late-October re-qualification), whose runset defaults `Selected SIMPLIFY option: false`: each drawn fold segment of a multi-finger device now extracts as its own transistor, so a reference that states one card per schematic device (`W=78.87u nf=8`) cannot match an extraction of eight `W=9.86u` segments — 81 extracted cards vs 66 reference cards on `vco_block` alone (`lvs-nocombine-f6eeac7/lvs.stdout.log`), with every delta decomposing into exact fold segments and no wiring delta. Issue #980 asked which side moves.

## Decision

**Block- and top-level LVS runs invoke the PDK runner with `--combine`; the references are not restated per fold segment.**

`layout/harness/lvs.py` passes `--combine` by default (`combine=True`; `combine=False` runs the deck exactly as the runset defaults it). The switch is the f6eeac7 `run_lvs.py`'s own (`run_lvs.py:269-272` maps it to the `combine` klayout switch), so no deck fork, no shim, and no change to `sim/pdk.json` or to `layout/run_pv.py`'s CLI.

The deck honours `COMBINE` on **both** sides (`gf180mcu.lvs:430-432`: `netlist.combine_devices if COMBINE` *and* `schematic.combine_devices if COMBINE`). The runner's own `--combine` help text ("Enable netlist combine only in extracted netlist") understates what the deck does; this record decides on the deck's behaviour, not the help string.

Why both sides is the right semantics: it restores, on the new runset, the *shared* fold-merge the old deck's SIMPLIFY applied to the extracted side — parallel devices are combined into one summed-width device under one definition, on both sides of the comparison, before the comparer sees them. The reference keeps mirroring the schematic's device list (one card per schematic device, folded devices stated at drawn width via `Fet.drawn_w_um`, `M=2` parallel pairs), which is what makes the comparison evidence about *the design's* connectivity and device population.

## Alternatives considered

- **Restate folded cards per drawn segment in every reference generator** (vco, pfd_cp, divider_chain, lock_detector, plus the top-level composition) — keeps the runset at its defaults, but rewrites every reference so it no longer mirrors the schematic's device list, weakening what a match is evidence of, and leaves the width-sum rounding visible per segment instead of absorbing it once. Rejected by the Curator Enhancement on #980; not revisited here.
- **`--schematic_simplify`** (the flag the issue's second bullet alludes to) — sets the switch key `schematic_simplify`, while the deck reads `$simplify` (`gf180mcu.lvs:149`); by reading, it cannot turn SIMPLIFY on. Not run; traced by hand in the Curator Enhancement. Do not build on it.

## Consequences

- The four block-level LVS verdicts are re-recorded on the f6eeac7 runset under this invocation: `layout/evidence/{vco,pfd-cp,divider-chain,lock-detector}-layout/lvs-combine-f6eeac7/`, each log quoting `Selected SIMPLIFY option: false` and `Selected COMBINE option: true` and carrying `Congratulations! Netlists match.` (66 / 168 / 452 / 117 extracted device cards — exactly the reference card counts). The pre-re-pin records stay as they are: valid for the deck their own provenance tables name.
- **Width comparison is exact, measured on both sides of the rounding question** (`layout/evidence/vco-layout/lvs-combine-width-sensitivity-f6eeac7/`): the combiner sums `8 x 9.86u` into `W=78.88U`, and a reference card 10 nm short (`78.87u`) **mismatches** — the comparer has no width tolerance. The four block references match because they already state the deck-quantized per-fold sum (`Fet.drawn_w_um`'s convention), which is exactly what the combiner reproduces. Consequence carried forward: the composed `pll_top` reference (open PR #981) states that card at `78.87u` and will mismatch under `--combine` until its composer states the quantized sum — #987 must fix the composer, not the invocation.
- **What combine can no longer distinguish:** a layout drawn as N wrongly-separate-but-parallel-connected devices where the design intends one wide device (or vice versa) compares equal to the intended single card, because both sides combine parallel devices before comparison. What remains visible, each measured: a *dropped fold finger* (one fold fewer on either side — the summed width differs by a fold, and the comparer is exact, see the sensitivity probes) still mismatches; an *opened net* still mismatches — `layout/evidence/inv-tb-combine-f6eeac7/` re-runs `run_pv.py prove` with `--combine` on and its LVS fault negative control (a deleted Metal1 island opening the shared drain node) still reports `Netlists don't match`. Device-count-only errors between *non-parallel* devices remain visible (combine merges exactly parallel devices).
- The top-level `pll_top` composed-reference re-run follows the same invocation once its composer and evidence directory land (split to #987, out of scope here).
- The KLayout-pin caveat applies to the new records: they were captured on KLayout 0.30.12 (no 0.28.16 binary exists on the capturing host), and are disclosed per-file in `check-layout-status-claims.sh` `OFF_PIN_DISCLOSED`; each block keeps its on-pin (0.28.16, `c6d73a35`-deck) match log as the engine-pin warrant, so the pin rule's "at least one on-pin verdict per graded top cell" continues to hold.
