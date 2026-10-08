# Batch image vs local ngspice-46: diagnosis (#533, #503)

Dated 2026-10-08. Diagnostic note, not a measurement record: nothing under
`sim/` records was written or edited, and no batch job was submitted for this
note (the job store was only read).

## What was compared

| | #533 spur pilot | #503 jitter pilot |
|---|---|---|
| job | `gf180-pll-sim-ff_-40c_3.63v_b7vs1p886-583b5b76` | `gf180-pll-sim-typical_27c_3.30v_b6vs2p417-6f01f657` |
| image | `ami-0e40e3245f1923ac8`, `c7i.8xlarge`, Spot | same image, same instance type |
| PDK path used | `/opt/pdk/gf180mcuD` (deck path substituted on the instance) | same |

Local reference: ngspice-46, PDK `gf180mcuD` from volare, open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` (also the revision stamped into
every deck header and in `~/.volare/gf180mcuD/SOURCES`). Local CPU model is
the same as the batch instance's (Xeon Platinum 8488C).

## Findings

1. **The decks are the same.** The deck the batch job executed
   (`outputs/<deck>.spice`, `pll_top.spice`, `tb_*.sp`) differs from the local
   one only in the PDK directory prefix. Re-running the batch deck locally with
   only that prefix swapped reproduces the local (not the batch) behaviour at
   DC.
2. **The divergence starts at the DC operating point, before any transient.**
   Both batch logs begin with
   `Starting dynamic gmin stepping / Dynamic gmin stepping failed / Starting
   true gmin stepping / True gmin stepping completed`. The local log of the
   same deck has none of those lines: Newton converges directly. The two
   "Initial Transient Solution" tables differ in the phase-detector
   feedback-side latch nodes (e.g. `fb` 1.79 V batch vs 3.63 V local;
   `xdut.dn` 3.63 V vs 2e-8 V; `xdut.xpfd.xpfd.sbf` flipped). The PFD
   latch is bistable, so these are two valid DC solutions; the batch run
   landed in the other one and the closed loop then evolved from a different
   initial state. That is sufficient to explain `lock_lvl` ~0 V vs 3.63 V and
   the 14 dB spur spread (#533), and it is consistent with the smaller
   #503 offsets (`tj_rms_pct` +1.7 %, `tie_rms_s` +13.5 %), whose batch log
   shows the identical gmin-stepping prologue.
   Gmin stepping by itself is not abnormal (many committed local logs show it
   for other benches); what matters is that the same deck takes a different
   DC path on the batch image.
3. **Solver and build options look the same.** Both report
   `Using SPARSE 1.3 as Direct Linear Solver` and `ngspice-46`; the local
   build has KLU, CIDER, XSPICE and OpenMP (BSIM3/4) compiled in, which is
   also what the batch image's published build recipe enables. The job
   outputs do not carry the batch banner, so this cannot be verified from
   evidence, only inferred.
4. **PDK revision: probably aligned, but unverified.** The image's PDK was
   fetched as "the newest remote gf180mcu version at bake time" rather than at
   a pinned revision, and the resolved revision lives only in a manifest file
   on the image. `volare ls-remote --pdk gf180mcu` today lists
   `c6d73a35...` first, the same revision the local tree has carried since
   2026-09-14, so an unpinned bake on 2026-10-02 most likely resolved to it.
   That is an inference: the manifest was not readable with the submit
   credential and the job outputs recorded nothing about the instance's PDK.
   A PDK revision difference therefore is **not** established, and is also not
   ruled out.
5. **Thread count is a smaller suspect.** The job did not set
   `OMP_NUM_THREADS`; the instance has 32 vCPUs against 8 locally. ngspice's
   own default thread count is small and fixed, so this is unlikely to change
   DC convergence, but it is also unrecorded.

## What this means for the campaigns

- The delta is a property of the batch execution environment, not of the deck
  and not of run-to-run noise. Neither 45-point grid should be submitted
  until a repeat of one point per campaign shows the image reaching the same
  DC state as the local run.
- The one thing that cannot be settled from existing evidence is *which*
  environment difference causes the different Newton path (PDK tree content,
  simulator binary/libm, or something else). Pinning the image's PDK revision
  is an image-definition change, not a change to this repository.

## Changes made here

`sim/harness/batch.py`: the batch job command now also writes
`ngspice.env` next to `ngspice.log`/`.rc`/`.host`, best-effort and never
failing the job. It holds the simulator `--version` banner, the `SOURCES`
stamp of the resolved PDK variant, the image manifest (if present), the CPU
model, `nproc`, and `OMP_NUM_THREADS`. It is collected into the per-job
`.batch-<job-id>/outputs/` directory and, like the other contract files, is
not published into the shared rundir. This turns the next batch run (the
single re-pilot) into a decisive comparison: if the `SOURCES` stamp matches the
local revision, the PDK is excluded and the simulator build is the remaining
suspect.

Not yet done: carrying `ngspice.env` content into the evidence record's
provenance (a report-schema change), tracked generically as
2AMLogic/klayout-tools#2834.

## Spend

No batch job was submitted. One local ngspice start of the batch deck (default
threads, local PDK path) was run only far enough to read the DC-operating-point
prologue and then stopped.
