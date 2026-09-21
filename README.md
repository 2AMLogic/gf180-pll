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

Being honest about where this actually is:

- **Done** — architecture and scope captured as numbered decision records in
  `spec/`; xschem schematics for the VCO, PFD, charge pump, feedback divider,
  lock detector, and the shared 3.3 V logic cells they are built from; a
  reproducible PVT corner harness; **89 evidence records** across 24
  verification campaigns (device characterization, VCO tuning range, PFD
  dead-zone freedom, charge-pump compliance and mismatch, divider moduli,
  lock-detector window, its sizing ladder and its trim-code map, loop
  dynamics, the closed-loop
  reference spur measured from the output spectrum, the loaded output
  driver's duty cycle and levels/drive, and a first pass at the other
  closed-loop campaigns: lock-time, output-range, supply-sensitivity, and
  period-jitter).
- **Not done** — closed-loop bring-up. `pll-top-smoke`'s latest record
  (`20260802-160926-8456ff3`, superseding the earlier FAIL) is an **overall
  PASS, 0 of 7 checks failed** at the single nominal corner (`typical` / 27 C /
  3.30 V) it is deliberately scoped to. Three of the four closed-loop
  campaigns have since taken the full PVT grid against the same assembled
  `pll_top` DUT, and the honest news is mixed: `lock-time`'s 270-run grid
  (45 corners × N ∈ {4, 16, 64} × {cold, relock}) reaches a sustained
  in-window `LOCK` PASS on 21/135 cold-start rows and 1/135 relock rows — the
  rest are read as the test window being too short, not as a broken loop, but
  that reading is not yet a closed PASS bound; `output-range`'s full 45-point
  grid reaches **0/45** sustained in-window PASS at either drawn-band edge;
  `supply-sensitivity`'s full 45-point grid (plus all three step/ramp corners)
  PASSes on power (0.99–1.98 mW, under the 5 mW draft target) but FAILs three
  of its other four criteria at real corners, with one genuine design-margin
  finding routed to `loop-dynamics` (#10) and the rest to `lock-detector`
  (#11) or the post-#24 charge pump (#9) — see each campaign's own latest
  record under `sim/*/records/` for the full accounting. `period-jitter`'s
  **deterministic (control-ripple) component now covers 45 of the mandated 45
  PVT corners** — the complete 3 × 3 temperature × supply plane at all five
  MOS bundles (`typical`, `ff`, `ss`, `fs`, `sf`), ranging **0.0508 % RMS**
  (`ss` / 125 °C / 3.30 V) to **0.2691 % RMS** (`typical` / −40 °C / 3.63 V),
  every point inside the 1.0 % target with at least 3.7× margin. Two things it
  does **not** cover, stated rather than left to be inferred: the campaign's
  own Acceptance Criteria (#13) also require a **random/noise-driven** jitter
  component that no record measures (a disclosed methodology gap), and every
  one of its records is at one output frequency, 150 MHz — the same
  measurement at the 200 MHz top of the ratified band is declared as
  `sim/period-jitter-band-top` and carries no measured record yet.
- **Underway, block by block** — PLL-block layout. Issue #16 landed a
  repeatable `klt`-aware DRC/LVS flow against the gf180mcu open-PDK decks,
  proven clean (and proven to catch a deliberately injected DRC violation and
  LVS mismatch) on a trivial standard-cell inverter
  (`layout/evidence/inv-tb-proof/PROOF.md`). Real transistor-level layout has
  since been drawn against that flow: **4 of the 4 PLL sub-blocks** — the VCO
  (#293), the PFD + charge pump (#294), the divider chain (#295), and the lock
  detector (#296) — now have a committed block GDS with a DRC-clean deck log
  under `layout/evidence/`, and **2 of the 4 are LVS-matched** against an
  independently derived reference netlist (`vco_block` and `divider_chain`;
  `pfd_cp` and `lock_detector` each state in their own `PROOF.md` that they
  make a DRC-clean geometry claim only). There is **no assembled `pll_top`
  GDS** — the four blocks exist side by side, not wired into a top level, so
  no top-level DRC/LVS closure and no post-layout extracted-netlist
  re-verification exists either (#17, #18, #149). These counts are checked
  against the evidence tree in CI by
  `layout/lib/check-layout-status-claims.sh`, so this paragraph cannot
  silently go stale the way its predecessor did.
- **Not started** — silicon. `measurements/` stays empty until there is any.
  Nothing has been fabricated or measured; treat every number in this
  repository as simulation only.

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
`sim/README.md` for *how results are recorded and how to reproduce them*.

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
deterministic component now covers 45 of the mandated 45 PVT corners but its
random/noise-driven component and its 200 MHz band-top counterpart are both
still unmeasured (#13), so the proposal marks those rows **unmet** rather than
omitting them; and that layout has reached the sub-block level but not the top
level — **4 of the 4 PLL sub-blocks** are drawn and DRC-clean, **2 of the 4
are LVS-matched**, and there is **no assembled `pll_top` GDS**, hence no
top-level signoff and no post-layout re-verification.

## License

[Apache-2.0](LICENSE). Copyright 2026 2AM Logic.
