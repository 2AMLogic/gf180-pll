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

## Addendum (2026-10-08, later): active solver and a controlled local DC comparison

Appended after the re-pilot (batch job
`gf180-pll-sim-ff_-40c_3.63v_b7vs1p886-4c405660`, submitted from main at
`0d0f19d5`), which reported a "KLU vs SPARSE" solver lead. Everything above
this heading stays as written. No batch job was submitted and nothing was
spent for this addendum. The job store was only read, using the submit
credential through `sim/harness/batch.py`'s own config resolution. No record
under `sim/*/records/` was written, and the campaign inputs (`tb.json`,
`tb_reference_spur_band_top.sp`) and `spec/` were not touched.

### 1. Active solver vs build capability

| source | build capability (`--version` banner) | solver actually used (`ngspice.log`) |
|---|---|---|
| batch pilot 1, job `…-583b5b76`, `outputs/ngspice.log` (read from the job store) | not captured (the job ran before `ngspice.env` existed) | line 13: `Using SPARSE 1.3 as Direct Linear Solver` |
| batch re-pilot, job `…-4c405660`, collected `outputs/ngspice.log` + `outputs/ngspice.env` | `ngspice-46`, `Compiled with KLU Direct Linear Solver`, creation date 2026-10-01 | line 13: `Using SPARSE 1.3 as Direct Linear Solver` |
| local ngspice-46 reference (the repo's pinned build; the pilot comment names no path) | KLU-capable: `sim/lock-time/records/20260801-091429-5fd8489.md` quotes `Compiled with KLU Direct Linear Solver` for it | `Using SPARSE 1.3 as Direct Linear Solver`, per finding 3 above and in every committed local log (41,150 occurrences under `sim/`, no `Using KLU`) |

The re-pilot comment set the batch build banner ("Compiled with KLU") against
the local runtime line ("Using SPARSE 1.3"). Those lines report different
things. A like-for-like comparison shows **the same build capability (KLU
compiled in) and the same active solver (SPARSE 1.3) on both backends**. So
the logs do not show a solver-selection difference, and finding 3's "Using
SPARSE 1.3 in both" holds. The batch side is now confirmed from both
execution logs instead of being inferred. Both batch logs also contain
`Note: No compatibility mode selected!`, so neither job applied an
`ngbehavior` setting.

The two batch pilots ran byte-identical deck inputs (`ff_-40c_3.63v_b7vs1p886.spice`,
`pll_top.spice` and `tb_reference_spur_band_top.sp` compared with `cmp`). They
produced identical "Initial Transient Solution" tables, with all 448 node
values equal at printed precision.

### 2. Controlled local DC-only comparison

**Setup.** Host `loom-worker-3`, Xeon Platinum 8488C, 8 vCPU, the same CPU
model as the batch instance. Scratch directory outside the repository. Inputs
are the re-pilot's uploaded `inputs/` files with only these changes:
`@PDK_VARIANT_DIR@` set to `~/.volare/gf180mcuD` (open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, the same stamp as the image's
`/opt/pdk/gf180mcuD`), `.measure` lines dropped, `wrdata` dropped, and
`tran 2e-9 8.0e-6 2.4e-6 100e-12` cut to `tran 1e-11 1e-11`. The `.ic`
lines, `.options` and the model/DUT includes are unchanged, so the
transient's initial operating point is computed the same way and printed as
"Initial Transient Solution". In each variant, one `.options` line was
inserted before `.options rshunt=1e12`. Command:
`OMP_NUM_THREADS=2 ngspice -b dc_<variant>.spice > dc_<variant>.log`, run
once per variant, one run at a time, about 3 s each.

**Simulators available on this host.** Only `/usr/bin/ngspice`:
`ngspice-42`, Ubuntu package `42+ds-3build1`, `Compiled with KLU Direct
Linear Solver`, creation date 2024-03-31. The pinned ngspice-46
(`~/.local/bin/ngspice`, see `sim/lib/simenv.sh`) is **absent** on this
worker (`run_corners.py --check-env`: "pin … not found … resolved
/usr/bin/ngspice"). No ngspice-46 binary was available for a same-version
comparison.

| variant (ngspice-42) | solver used (log) | DC path (log) | `fb` | `xdut.dn` | `xdut.up` | `xdut.xpfd.xpfd.sbf` | `vctrl` | `lock` | node diffs vs batch (of 448) |
|---|---|---|---|---|---|---|---|---|---|
| batch pilots 1 and 2 (ngspice-46, image) | SPARSE 1.3 | dynamic gmin failed, then true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | — |
| `default` (no solver option) | SPARSE 1.3 | dynamic gmin failed, then true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | **0** |
| `.options sparse` | SPARSE 1.3 | same | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | **0** |
| `.options klu` | **KLU** | same | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | 29, all last-digit (e.g. `xed_ref.xnd.ni` 1.76867e-11 vs 1.76865e-11) |
| `.options itl1=1000` | SPARSE 1.3 | same (direct Newton still fails) | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | 0 |
| `.options klu` + `itl1=1000` | KLU | same | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 | 29 (as KLU) |
| `.options gminsteps=0` | SPARSE 1.3 | source stepping failed, then "Transient op" | 1.88e-04 | 3.63 | 9.55e-09 | **3.63** | **0.0282** | 5.14e-09 | 366 |
| local ngspice-46 reference (finding 2 above; log not on this host) | SPARSE 1.3 | direct Newton, no gmin stepping | 3.63 | ~2e-8 | — | flipped vs batch | — | — | — |

**Observations.**

- Running the identical deck with the identical PDK, a second simulator build
  on a different host (Ubuntu ngspice-42) **reproduces the batch DC state
  exactly**: the same gmin-stepping path and all 448 initial-solution values
  equal to the batch logs at printed precision. The batch state is therefore
  not specific to the batch image. It comes from this deck and PDK on two
  independent builds (image ngspice-46 and Ubuntu ngspice-42).
- **Switching the linear solver does not change the state.** Forcing KLU on
  the same binary still runs dynamic gmin (fails), then true gmin
  (completes), and lands in the same latch state. The only differences are
  last-digit differences on 29 internal nodes. Allowing more direct-Newton
  iterations (`itl1=1000`) does not make Newton converge directly, so it
  does not move the state either.
- The latch state **does** depend on the homotopy path. With gmin stepping
  disabled, ngspice-42 falls back to source stepping, which fails, and then
  to its pseudo-transient "Transient op". That run lands in a third state:
  `sbf` is flipped and `fb` is at about 0 V. However, `xdut.dn` is still
  high, and `vctrl` is not held at its `.ic` value (0.028 V instead of
  1.886 V), so it is neither the batch state nor the reference state. It
  shows that the PFD latch's DC solution depends on how convergence is
  reached. It does not reproduce the local reference.
- The run that differs is the **local ngspice-46 reference**: it converges
  by direct Newton with no gmin stepping. The batch image's ngspice-46 and
  Ubuntu's ngspice-42 both fail direct Newton on the same deck. This
  comparison mixes versions (42 vs 46), so it does not show *why* the
  reference build converges directly. It does show that the active solver
  is not the cause.

### 3. Status of the hypothesis

- **Solver hypothesis: not supported.** Both backends report SPARSE 1.3 in
  their execution logs, and forcing KLU on an available build did not
  reproduce the state split. The re-pilot's "KLU vs SPARSE" lead compared a
  build banner with a runtime line.
- **Still unresolved: why the local ngspice-46 reference converges by direct
  Newton** while the image's ngspice-46 and Ubuntu's ngspice-42 do not.
  Candidates: differences in the reference binary's build (configure flags,
  compiler and libm, source revision or patches), an init file read only on
  the reference host (`spinit`, `~/.spiceinit`, or `.spiceinit` in the
  working directory), or a harness-side difference in the local run
  (working directory or environment). None of these is established. Nothing
  here shows which of the two DC solutions is the representative one: both
  are valid solutions of a bistable latch.
- **Implication for the campaign: unchanged.** The pilot still does not match
  local ngspice-46, so per the 2026-10-02 ruling the grid stays unsubmitted.
  Nothing here supports an image change, because the image's behaviour
  matches a second independent build.

### 4. Exact next diagnostic step and owner

On the host and with the ngspice-46 binary that produced the -61.71 dBc
local pilot (by the repo's pin convention `~/.local/bin/ngspice`, or a
build relocated through `SIM_NGSPICE_BIN`; the pilot comment does not name
the path), run the same scratch
DC deck (re-pilot `inputs/` with the four edits listed in §2). Capture:
`ngspice --version`; `ldd` of the binary; its configure line (from
`config.log` in the build tree, if kept); the `spinit` it loads; any
`~/.spiceinit` or working-directory `.spiceinit`; and the "Initial
Transient Solution" table, once with no option and once with
`.options klu`. Two outcomes:

- If that binary converges by direct Newton to `fb` = 3.63 V on the scratch
  deck, the reference build (or its init files) is the outlier. The decision
  then belongs to the spec and testbench owners, not to the image: either
  pin the PFD latch's initial state explicitly in the testbench (a reviewed
  campaign-input change) or record which simulator build is the reference
  under DR-028.
- If it lands in the batch state, the difference lies in the local harness
  invocation (working directory, init files, environment), not in the
  binary. Compare against the local run's `ngspice.log` header.

Owner: the operator, or an agent on a worker that carries the ngspice-46 pin.
This worker (`loom-worker-3`) cannot run the step because the pin is absent.
Provisioning it is a change to the worker spec that owns `~/.local/bin`, not
a change to this repository. It was not installed here, under the
shared-host rules.

### 5. Evidence capture

`sim/harness/batch.py` was not changed. The batch side already records the
active-solver line (`ngspice.log`) and the build banner, PDK stamp and image
manifest (`ngspice.env`), and these were enough for §1. The capture still
missing is on the **local** side: a local `--backend local` run keeps no
equivalent of `ngspice.env` (binary path, banner, loaded init files), and
that is exactly what the next step needs. Recording that in evidence
provenance is the report-schema gap already filed as
2AMLogic/klayout-tools#2834.

Scratch-deck digests (sha256, scratch directory not committed):
`dc_default.spice` `b7d23861…`, `dc_klu.spice` `df3dec40…`,
`dc_sparse.spice` `c5ddd8c3…`, `dc_itl1.spice` `d93a9db9…`,
`dc_klu_itl1.spice` `1c5ed2d1…`, `dc_nogmin.spice` `1d14337e…`; inputs
`ff_-40c_3.63v_b7vs1p886.spice` `d608a5db…`, `pll_top.spice` `ce6032da…`,
`tb_reference_spur_band_top.sp` `9da0b8d6…`.
