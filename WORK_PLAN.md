# Work Plan

This roadmap is generated from the repository's current GitHub label state.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#533**: sim/reference-spur-band-top: run the 45-point 200 MHz campaign on the batch backend (operator-authorized spend)
- **#755**: sim harness: stage a simulator init file (wnflag) so local and batch backends run the same configuration

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#680**: sim: realign the batch job image to the ngspice-46 pin — it cannot converge sim/reference-input-contract's edge-rate variant, so #499's grid is unobtainable off-host

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

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
- **#741**: sim: migrate loop-dynamics, output-range, mc-cp-mismatch shell campaigns to harness manifests *(curated)*
- **#755**: sim harness: stage a simulator init file (wnflag) so local and batch backends run the same configuration *(curated)*
- **#825**: Re-qualify device-characterization records under open_pdks f6eeac7 (child of #790) *(curated)*
- **#827**: Re-qualify lock-detector, lock-window and divider records under open_pdks f6eeac7 (child of #790) *(curated)*
- **#828**: Re-qualify closed-loop campaign records under open_pdks f6eeac7 (child of #790) *(curated)*

## Proposed (Architect / Hermit)

- **#237**: [Epic #542] 3A — gf180-pll maturation + Challenge #5 brief *(architect)*

## Epics

- **#127**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 15 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |
<!-- guide:plan-body:end -->
