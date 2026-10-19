# Work Plan

This roadmap is generated from the repository's current GitHub label state.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#791**: feat(sim): pin open_pdks and refuse PDK trees at another revision
- **#796**: feat(loop-filter): prepare C2 as the option-B MIM (DR-042 proposed)

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#533**: sim/reference-spur-band-top: run the 45-point 200 MHz campaign on the batch backend (operator-authorized spend)
- **#755**: sim harness: stage a simulator init file (wnflag) so local and batch backends run the same configuration

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#237**: [Epic #542] 3A — gf180-pll maturation + Challenge #5 brief

## In Progress

Issues currently being built (`loom:building`).

- **#753**: Loop filter C2 is a MIM option-A device, but the repository's PV flow targets gf180mcuD (MIM option B)
- **#789**: Re-pin PDK to open_pdks f6eeac7 via ciel: code, CI, docs, hash-checked search
- **#798**: T1 items 1, 9, 10: move the grader to klt 0.7.0 and cite artifact-anchored inventory envelopes

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#791**: feat(sim): pin open_pdks and refuse PDK trees at another revision
- **#796**: feat(loop-filter): prepare C2 as the option-B MIM (DR-042 proposed)

## Proposed

Issues carrying `loom:curated`.

- **#237**: [Epic #542] 3A — gf180-pll maturation + Challenge #5 brief *(curated)*
- **#242**: Live wall-clock confirmation of #241's ngspice-OMP-pin fix on an idle host *(curated)*
- **#395**: Measure post-supply-step re-lock time instead of extrapolating it (DR-011 Decision 4) *(curated)*
- **#405**: Run the post-supply-step re-lock campaign and write DR-011 Decision 4's replacement decision record (#395 remainder) *(curated)*
- **#479**: README: embed the fleet burndown chart (one line) *(curated)*
- **#499**: sim: the Reference input contract (levels, edge rate, duty) is budget with no measurement and no owner — spec names a closed issue *(curated)*
- **#503**: sim/period-jitter-band-top: run the 45-point campaign on the batch backend (operator-authorized spend) *(curated)*
- **#533**: sim/reference-spur-band-top: run the 45-point 200 MHz campaign on the batch backend (operator-authorized spend) *(curated)*
- **#549**: sim: bound the batch-vs-pinned ngspice divergence with a cross-version overlap measurement on a shared operating point *(curated)*
- **#680**: sim: realign the batch job image to the ngspice-46 pin — it cannot converge sim/reference-input-contract's edge-rate variant, so #499's grid is unobtainable off-host *(curated)*
- **#753**: Loop filter C2 is a MIM option-A device, but the repository's PV flow targets gf180mcuD (MIM option B) *(curated)*
- **#755**: sim harness: stage a simulator init file (wnflag) so local and batch backends run the same configuration *(curated)*
- **#789**: Re-pin PDK to open_pdks f6eeac7 via ciel: code, CI, docs, hash-checked search *(curated)*
- **#798**: T1 items 1, 9, 10: move the grader to klt 0.7.0 and cite artifact-anchored inventory envelopes *(curated)*

## Proposed (Architect / Hermit)

- **#237**: [Epic #542] 3A — gf180-pll maturation + Challenge #5 brief *(architect)*
- **#731**: sim/period-jitter: migrate grid.sh fan-out to run_corners.py backends (follow-up to #712 step 1) *(architect)*
- **#740**: sim/lib/simenv.sh: refuse local multi-unit grid fan-out when the batch backend is selected *(architect)*
- **#741**: sim: migrate loop-dynamics, output-range, mc-cp-mismatch shell campaigns to harness manifests *(architect)*

## Epics

- **#127**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 2 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 2 |
| Curated | 14 |
| Architect / Hermit proposals | 4 |
| Active epics | 1 |
<!-- guide:plan-body:end -->
