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

## Status: early. Schematic-level, pre-layout, pre-silicon.

Being honest about where this actually is:

- **Done** — architecture and scope captured as numbered decision records in
  `spec/`; xschem schematics for the VCO, PFD, charge pump, feedback divider,
  lock detector, and the shared 3.3 V logic cells they are built from; a
  reproducible PVT corner harness; **54 evidence records** across 18
  verification campaigns (device characterization, VCO tuning range, PFD
  dead-zone freedom, charge-pump compliance and mismatch, divider moduli,
  lock-detector window, loop dynamics, and a first pass at the closed-loop
  campaigns: lock-time, output-range, and supply-sensitivity).
- **Not done** — closed-loop bring-up. `lock-time`, `output-range`, and
  `supply-sensitivity` each have evidence now (6, 2, and 2 records
  respectively), but the assembled loop does not yet close cleanly: the one
  `pll-top-smoke` record on file (`20260801-085349-0e5c22d`) is an **overall
  FAIL, 4 of 7 checks** — residual frequency error, static phase error,
  output-frequency accuracy, and the lock-detector flag all miss their
  criteria at the single nominal corner it covers. `period-jitter` is still
  reserved in `sim/README.md` with zero records.
- **Not started** — layout. `layout/` and `measurements/` are placeholders.
  Nothing here has been through DRC/LVS, and nothing has been fabricated or
  measured. Treat every number in this repository as simulation only.

The maturity ladder being climbed: simulation-complete → layout DRC/LVS-clean
→ shuttle seat → measured silicon over temperature. This is the first rung.

## Repository layout

```
spec/          specification + numbered decision records (DR-NNN)
design/        xschem schematics/symbols + the SPICE netlist exporter
sim/           testbenches, the PVT corner harness, and append-only evidence records
layout/        GDS + DRC/LVS reports (empty — not started)
measurements/  silicon characterization (empty until there is silicon)
```

Start with `spec/decision-records/` for *why the design is what it is*, and
`sim/README.md` for *how results are recorded and how to reproduce them*.

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

## License

[Apache-2.0](LICENSE). Copyright 2026 2AM Logic.
