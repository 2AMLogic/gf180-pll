# gf180-pll

An integer-N, ring-oscillator phase-locked loop for the
[GlobalFoundries 180 nm MCU open PDK](https://github.com/google/gf180mcu-pdk)
(`gf180mcuD`), designed entirely in the open-source analog flow: **xschem** for
schematic capture, **ngspice** for simulation, and
[klayout-tools](https://github.com/2AMLogic/klayout-tools) for layout work.

This block is built by AI agents. Not "AI-assisted" — agents do the schematic
capture, write the testbenches, run the PVT corner sweeps, argue the design
decisions out in written decision records, and open the pull requests. The
verification evidence in `sim/` is the point of the repository: every claim
this project makes is meant to be backed by a testbench and a recorded corner
sweep, in a format designed so you can check that yourself.

## Status: early. Block-level layout underway, pre-top-level, pre-silicon.

Being honest about where this actually is. Every number in this repository is
simulation only; nothing has been fabricated or measured.

| Area | State | Detail |
|---|---|---|
| Spec | Architecture and scope captured as numbered decision records. | [`spec/`](spec/) |
| Schematics | VCO, PFD, charge pump, feedback divider, lock detector, and the shared 3.3 V logic cells. | [`design/`](design/) |
| Verification | **105 evidence records** across 27 verification campaigns, each run over the PVT corner matrix. | [`sim/STATUS.md`](sim/STATUS.md) |
| Closed-loop bring-up | Not done. Single-corner smoke test passes; the full-grid lock-time, output-range and supply-sensitivity campaigns do not yet show sustained lock across PVT. | [`sim/STATUS.md`](sim/STATUS.md) |
| Period jitter | Deterministic component covers 45 of the mandated 45 PVT corners; the random component is bounded, not estimated. | [`sim/STATUS.md`](sim/STATUS.md) |
| Reference spur | Closed-loop record covers 5 of the 45 PVT corners at 150 MHz; the 200 MHz band-top sweep has no measured record yet. | [`sim/STATUS.md`](sim/STATUS.md) |
| Layout | 4 of the 4 PLL sub-blocks are drawn and DRC-clean; 4 of the 4 are LVS-matched. The assembled `pll_top` GDS (all five blocks, loop filter included) is committed with one inherited DRC violation (the loop filter's `MIMTM.3`), top-level LVS still to run, and an area over the ratified row. | [`layout/STATUS.md`](layout/STATUS.md) |
| Silicon | Not started. `measurements/` stays empty until there is any. | [`measurements/`](measurements/) |

The machine verdict of record is `signoff/tier-report.json`, described in
[the evidence ladder section below](#where-this-block-stands-against-the-evidence-ladder).
The per-campaign narrative behind this table (lock-time, output range, supply
sensitivity, period jitter, reference spur, and the layout paragraph) lives in
[`sim/STATUS.md`](sim/STATUS.md) and [`layout/STATUS.md`](layout/STATUS.md).
The record, campaign, period-jitter and layout counts above are checked against
the evidence tree in CI, so they cannot silently go stale.

The maturity ladder being climbed: simulation-complete → layout DRC/LVS-clean
→ shuttle seat → measured silicon over temperature. This is partway up the
first rung: the blocks are drawn, the top level is not.

## Repository layout

```
spec/          specification + numbered decision records (DR-NNN)
design/        xschem schematics/symbols + the SPICE netlist exporter
sim/           testbenches, the PVT corner harness, and append-only evidence records
layout/        DRC/LVS flow + the four PLL sub-block layouts drawn against it
signoff/       this block's T1 evidence-tier verdict, machine-graded and CI-checked
measurements/  silicon characterization (empty until there is silicon)
```

Start with `spec/decision-records/` for *why the design is what it is*, and
`sim/README.md` for *how results are recorded and how to reproduce them*. An
integrator taking this block — top cell, port list, netlist/GDS paths,
measured area, maturity rung — reads
[`manifests/integrator.json`](manifests/integrator.json); a repo that
declares itself a consumer of this block is tracked in
[`spec/pll.md#consumers`](spec/pll.md#consumers).

## Where this block stands against the evidence ladder

The prose above is the human summary. The **machine verdict of record** is
`signoff/tier-report.json` — every item of klayout-tools'
[T1 evidence checklist](https://github.com/2AMLogic/klayout-tools/blob/main/docs/design-evidence-tiers.md)
rendered `met` or `unmet` with a reason, graded by `klt signoff --manifest`
from the evidence this repo actually cites, and re-checked in CI so it cannot
go stale. Today it reads **0 of 22 rows met**, which is the honest state of a
block with no `klt` evidence envelope committed anywhere yet.

Read `signoff/README.md` for what that verdict does and does not say — in
particular, three quite different situations all render as `no_evidence`, and
the four items the tool grades on "some passing envelope was cited" are
deliberately left uncited here rather than turned green by an unrelated report.
No hand-maintained met/unmet checklist is kept anywhere in this repository; if
a claim about T1 status conflicts with that report, the report wins.

## How verification works here

Two rules govern the repository, and most of its structure follows from them:

1. **No claim without a testbench.** A statement about the design is only
   admissible if there is a testbench that produces it, run across the PVT
   corner matrix (temperature, supply, and process corners), with the raw
   per-corner simulator logs committed alongside the summary.
2. **`sim/` is append-only evidence.** A record, once written, is never edited
   or deleted. Re-running — even to correct a mistake — mints a *new* record
   that names the record it supersedes. So the repository keeps its own
   mistakes, in order, with the corrections attached.

Each record pins the PDK version, the ngspice version, the exact DUT netlist
(by SHA-256), the repo commit, and whether the tree was dirty at run time. The
runner is `sim/run_corners.py` (stdlib Python, no virtualenv); `sim/selftest.sh`
is its acceptance test.

## Why this is public

This block is a canary. It exists partly to prove out an agent-driven analog
design flow end to end, and partly as a forcing function on the open-source
tooling: every time the layout tooling is awkward, missing a capability, or the
wrong shape for the job, that friction is filed as an issue against
[klayout-tools](https://github.com/2AMLogic/klayout-tools). Publishing the whole
record — decision records, evidence, dead ends, and the agent-authored pull
requests that produced them — is more useful than publishing a polished result,
so that is what is here.

## Chipalooza

[`docs/chipalooza/challenge-5-proposal.md`](docs/chipalooza/challenge-5-proposal.md)
is this block's proposal document for Open Circuit Design's Chipalooza
Challenge #5 (GF180MCU / Wafer.Space), re-derived from this repository's own
`sim/` evidence. It states plainly where the block does and does not meet the
brief today — including that the design is 3.3 V-only and does not yet
exercise the Challenge's 5.0 V analog rail; that `period-jitter`'s
deterministic component now covers 45 of the mandated 45 PVT corners and its
random/noise-driven component is bounded there (an upper bound, not an
estimate), but its 200 MHz band-top counterpart (#503) is still unmeasured, so
the proposal marks that row **unmet** rather than omitting it; and that layout
has reached a first assembled top level — **4 of the 4 PLL sub-blocks** are
drawn and DRC-clean, **4 of the 4 are LVS-matched**, and the assembled
`pll_top` GDS carries one inherited DRC violation, has had no top-level LVS run
and measures 0.4078 mm² against the 0.30 mm² row, so top-level signoff and
post-layout re-verification are both still ahead
([`layout/evidence/pll-top-layout/PROOF.md`](layout/evidence/pll-top-layout/PROOF.md)).

## License

[Apache-2.0](LICENSE). Copyright 2026 2AM Logic.
