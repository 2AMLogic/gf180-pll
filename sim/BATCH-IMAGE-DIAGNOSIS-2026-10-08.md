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
| local ngspice-46 reference (the repo's pinned build; the pilot comment names no path) | KLU-capable: `sim/lock-time/records/20260801-091429-5fd8489.md` quotes `Compiled with KLU Direct Linear Solver` for it | `Using SPARSE 1.3 as Direct Linear Solver`, per finding 3 above and in every committed `*.log` under `sim/` that names a solver (41,150 occurrences in 19,739 files, counted with `grep -ro --include='*.log'`; the other 16 committed logs contain no simulator output; none contains `Using KLU`) |

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
produced identical "Initial Transient Solution" tables, with all 447 node
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

| variant (ngspice-42) | solver used (log) | DC path (log) | `fb` | `xdut.dn` | `xdut.up` | `xdut.xpfd.xpfd.sbf` | `vctrl` | `lock` | node diffs vs batch (of 447) |
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
  exactly**: the same gmin-stepping path and all 447 initial-solution values
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
- **What finding 1's earlier local run adds.** Finding 1 is the closest
  existing evidence to §4, so here is what is and is not recorded about it.
  *Recorded* (finding 1 and "Spend" above): the batch deck, with only the
  PDK prefix swapped to the local tree, was started once with default
  threads, read only as far as the DC-operating-point prologue, and then
  stopped. It showed the local behaviour (no gmin-stepping lines). PR #723's
  provenance line names the host as `loom-worker-2`. *Not recorded*: the
  binary path and its `--version` banner (the note's header calls the local
  reference ngspice-46, but the run itself does not name its binary),
  whether it was a bare `ngspice -b` or a harness invocation, the working
  directory, the init files loaded, and the node values. Because only the
  prologue was read, that run does not show whether it reached `fb` =
  3.63 V. *Inferred, not verified*: a start that was stopped after the
  prologue reads like a direct simulator invocation rather than a harness
  run. If so, a harness-only cause (the second outcome in §4) is already
  less likely, and the candidates above narrow to the reference binary's
  build and the init files it reads. That run cannot settle the question:
  its binary and init files were not captured, and its deck still carried
  the full transient, `.measure` and `wrdata` lines. Those lines are not
  expected to change the operating point, but this was not tested. §4 is
  the same check with those details recorded.
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
  binary. Compare against the local run's `ngspice.log` header. Finding 1's
  earlier run makes this outcome less likely if that run was a bare
  invocation, but how it was invoked is not recorded (§3).

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

## Addendum 2 (2026-10-08, later): the section 4 step run on a host that has the ngspice-46 pin

Appended on a host that carries the pinned ngspice-46. Everything above
stays as written. No batch job was submitted and nothing was spent. No record
under `sim/*/records/` was written, and `spec/`, `tb.json` and
`tb_reference_spur_band_top.sp` were not touched. `sim/harness/batch.py` was
not changed. All files were run from a scratch directory outside the
repository.

### 1. Host and binaries

| item | value |
|---|---|
| host | `robb-pro`, Apple M5 Max, macOS 27.0.1, arm64 (not the Xeon/Linux class of the batch instance or of the earlier workers) |
| pin (`SIM_NGSPICE_BIN` unset, default per `sim/lib/simenv.sh`) | `~/.local/bin/ngspice`: `ngspice-46`, "Compiled with KLU Direct Linear Solver", "XSPICE extensions included", "X11 interface not compiled into ngspice"; Mach-O arm64, links only `libSystem` and `libc++`; sha256 `e6038926…` |
| other build on this host | `/opt/homebrew/bin/ngspice` -> Homebrew `ngspice/47`: `ngspice-47`, KLU; links ncurses, fftw, readline, X11 libs; sha256 `5845b18c…` |
| configure line / `config.log` | not discoverable: no build tree or `config.log` on this host, and the binary does not embed it. The only build facts are the `--version` banner above and the install prefix `~/.local` (visible in the `spinit` paths) |
| `spinit` loaded by the pin | `~/.local/share/ngspice/scripts/spinit` (sha256 `3c13693e…`): `set num_threads=8`, XSPICE `codemodel` lines, `unset osdi_enabled`; no solver, `gmin`, convergence or `ngbehavior` setting |
| `~/.spiceinit` | **present**: one line, `set ngbehavior=hsa`. Every default run here prints `Note: Compatibility modes selected: hs a`; the batch logs print `Note: No compatibility mode selected!` |
| working-directory `.spiceinit` | none (scratch directory was empty) |
| PDK | `~/.volare/gf180mcuD`, `SOURCES` = `open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b` (matches the stamp in the deck header and the image's) |

### 2. Deck

The job store was **not reachable** from this host (no batch provision script
or fleet env is configured here, so `sim/harness/batch.py`'s config resolution
has nothing to resolve), so the re-pilot's `inputs/` could not be read. The
deck was regenerated instead: the harness's own composer, for the same corner
and operating point (`ff`, -40 C, 3.63 V, `op=b7vs1p886`: band 7, `vstart`
1.886 V), run with a stub `ngspice` first on `PATH` that only copied the
deck and ran nothing. The included `pll_top.spice` and
`tb_reference_spur_band_top.sp` have the same sha256 prefixes as the digests
recorded in Addendum 1 (`ce6032da…`, `9da0b8d6…`). The regenerated deck itself
(`43536d49…`) was not compared byte-for-byte with the job's `inputs/` deck,
because that deck could not be read; the PDK prefix there is a placeholder, so
a direct digest comparison would differ anyway. Its parameters, `.ic`
lines and `.options` are the harness output for that point.

The four edits to make the DC-only deck are those in Addendum 1 section 2:
PDK directory is already `~/.volare/gf180mcuD` (the local harness substituted
it), `.measure` lines dropped, `wrdata` (and `set wr_singlescale`) dropped,
`tran 2e-9 8.0e-6 2.4e-6 100e-12` -> `tran 1e-11 1e-11`. The `klu` variant adds
only `.options klu` before `.options rshunt=1e12`.

### 3. Commands and results

Commands (scratch dir, one run at a time; `HOME` pointed at an empty directory
for the "no `.spiceinit`" rows):

```
HOME=<home> OMP_NUM_THREADS=2 <bin> -b dc_<variant>.spice > dc.log 2>&1
```

| build | `~/.spiceinit` read | variant | solver (log) | DC path (log) | `fb` | `xdut.dn` | `xdut.up` | `xdut.xpfd.xpfd.sbf` | `vctrl` | `lock` |
|---|---|---|---|---|---|---|---|---|---|---|
| batch pilots (Addendum 1) | n/a (`No compatibility mode`) | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin ngspice-46 | yes (`hsa`) | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin ngspice-46 | yes (`hsa`) | `.options klu` | KLU | dynamic gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin ngspice-46 | no | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin ngspice-46 | no | `.options klu` | KLU | dynamic gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| Homebrew ngspice-47 | yes or no | default and klu | - | none: aborts at parse, `g.xdut.xlf.xcf1.gc_moscap ... unknown parameter (e9)`, "no simulations run" | - | - | - | - | - | - |

- **No variant on the pin reached the reference state.** None converged by
  direct Newton: every pin run starts gmin stepping, and all of them land on the
  batch table for the six key nodes. `fb` is 1.79421 V, not 3.63 V, and
  `xdut.dn` is high.
- **`~/.spiceinit` (`ngbehavior=hsa`) is not the cause.** Removing it changed
  21 of the 447 initial-solution values (default) and 11 (klu), none of the six
  key nodes. The batch run's lack of a compatibility mode is therefore not
  what separates it from the reference.
- **Forcing KLU changes the path, not the PFD state.** KLU takes dynamic gmin
  stepping to completion (SPARSE needed true gmin stepping as well), and
  142 of 447 values differ from the SPARSE run, but they are in the divider
  chain (`divout` 5.6e-9 V vs 3.63 V, `xdut.xdiv.ck2..ck6` flipped). The six
  PFD/loop nodes are unchanged. This is new relative to Addendum 1, whose
  ngspice-42 KLU run moved only 29 last-digit values: on this build the
  divider's own DC state does depend on the solver, which is a second
  bistable block in the DUT and should be noted when a reference state is
  pinned.
- **Harness invocation on this host gives the same state.** One real
  `sim/run_corners.py reference-spur-band-top --corners ff --temps -40
  --supply 3.3 --axis op=b7vs1p886 --no-write` run (local backend, pin on
  `PATH`) printed `Compatibility modes selected: hs a`, `Dynamic gmin stepping
  failed`, `True gmin stepping completed`, and the same six key-node values.
  It then hit the harness's 300 s per-point timeout (ERROR, nothing recorded):
  this arm64 host is far slower on the transient than the 8-vCPU Xeon workers.
  So the full-transient outcome (`lock_lvl`, spur) was not measured here, and
  no figure from this run is evidence.

### 4. Conclusion (section 4 two-outcome analysis)

Neither outcome of section 4 occurred as stated, and the result is this:

- Outcome 1 ("the pinned binary converges by direct Newton to `fb` = 3.63 V, so
  the reference build is the outlier") is **not reproduced**: the pin on this
  host does not.
- Outcome 2 ("the pinned binary lands in the batch state, so the difference is
  the local harness invocation") is **not established either**. It holds for
  this host only. The harness invocation here, a bare invocation, both with
  and without `~/.spiceinit`, and the solver option all give the batch state,
  so a working-directory, init-file or solver cause is **excluded on this
  host**. But this pin is a macOS arm64 build, and the reference run that
  showed direct-Newton convergence (Addendum 1 finding 2) was made on a Linux
  worker (`loom-worker-2`, per PR #723). The pin here and the pin there are not
  shown to be the same build.

What is established: four independent runs now give the batch DC state for this
deck (batch image ngspice-46, Ubuntu ngspice-42 on x86, this host's ngspice-46
arm64 with and without KLU and `hsa`, and the harness on this host). The one
observation that differs is the recorded earlier Linux "local" run, whose
binary, init files and node values were never captured. That observation is
now the outlier, and it is the less documented one. Causality is **unverified**:
no isolated change on any host has moved the PFD latch from the batch state to
the reference state. The earlier "local -61.71 dBc / `lock_lvl` 3.63 V" is
not reproduced by this host, and nothing here shows which DC solution is the
representative one (both are valid for a bistable latch).

Implications, none of which relaxes a requirement:

- The "batch image is the outlier" framing in the earlier text is weakened,
  not reversed: the image matches every run that was captured. The grid stays
  unsubmitted, as before; -55 dBc and DR-028's restrictions are unchanged.
- No image change is supported by this evidence.
- If the reference state cannot be reproduced anywhere with captured
  artefacts, the campaign's closed-loop result depends on an unpinned DC
  solution of the PFD latch. The owner decision in section 4 outcome 1 then
  applies in substance: pin the latch state explicitly in the testbench (a
  reviewed campaign-input change, spec/testbench owners) rather than relying
  on which homotopy path a given build takes.

### 5. Exact next step and owner

On the Linux worker that produced the -61.71 dBc local pilot (`loom-worker-2`
or whichever carries the pin that did), run the same DC-only deck from this
addendum (regenerate it exactly as in section 2), capturing: the binary path,
`ngspice --version`, `file`/`ldd`, sha256 of the binary, `spinit` and any
`~/.spiceinit`, and the "Initial Transient Solution" six-node table plus the
DC-path lines, once default and once `.options klu`. If it reaches
`fb` = 3.63 V by direct Newton, the platform build (Linux x86 pin vs the macOS
arm64 pin, i.e. compiler/libm/FP behaviour) is the difference and the
decision is the testbench-owners' (latch pinning, or recording which build is
the reference). If it reproduces the batch state, the earlier local observation
was mis-recorded and the local reference should be re-derived from a captured
run. Owner: an agent or the operator on that Linux worker. Not done here
because this host cannot run it.

Scratch decks (sha256, not committed): `dc_default.spice` `57630e04…`,
`dc_klu.spice` `107920af…`; harness-composed deck `43536d49…`.

## Addendum 3 (2026-10-08, later): Addendum 2 section 5 run on the Linux x86_64 worker; the split reproduces and `set wnflag=1` isolates it

Appended after running the step Addendum 2 section 5 left open. Everything
above stays as written. No batch job was submitted and nothing was spent. No
record under `sim/*/records/` was written, and `spec/`, `tb.json` and
`tb_reference_spur_band_top.sp` were not touched. `sim/harness/batch.py` was
not changed. Every run was one single local `ngspice -b` invocation
(`OMP_NUM_THREADS=2`), one at a time, from a scratch directory outside the
repository (not committed). The grid stays unsubmitted.

### 1. Host and binary

| item | value |
|---|---|
| host | `loom-worker-2`, Linux x86_64 (the worker PR #723 names for the earlier "local" run) |
| binary | `ngspice` on `PATH` is `~/.local/bin/ngspice`, a symlink to `~/.local/ngspice/bin/ngspice` (the repo pin per `sim/lib/simenv.sh`; `run_corners.py --check-env` reports the pin as resolved) |
| `--version` | `ngspice-46`, "Compiled with KLU Direct Linear Solver", creation date Wed Aug 5 10:12:28 UTC 2026 |
| `file` | ELF 64-bit LSB pie executable, x86-64, dynamically linked, stripped, BuildID `c160d928d9759ae1f095160f89942ff90bbd998a` |
| `ldd` | `libm.so.6`, `libstdc++.so.6`, `libgomp.so.1`, `libgcc_s.so.1`, `libc.so.6` (system copies under `/lib/x86_64-linux-gnu`) |
| sha256 | `c874869b16dc8a31cfa9d37d2b90a2a9e0e5b996f8e2535db89eb82855072931` |
| `spinit` | `~/.local/ngspice/share/ngspice/scripts/spinit` (sha256 `e9cd2232…`): `set num_threads=8`, `unset osdi_enabled`, XSPICE `codemodel` lines; no solver, `gmin`, `wnflag` or `ngbehavior` setting |
| `~/.spiceinit` | **present** (sha256 `94a971c8…`), two effective lines: `set wnflag=1` and `set num_threads=1`. Its comment says it restores per-finger model binning (bin selection uses W/NF) that a locally built ngspice lacks, because a locally built ngspice does not get it implicitly the way a distro-packaged one does through `ngbehavior=hsa` |
| working-directory `.spiceinit` | none (scratch directory was empty) |
| configure line / `config.log` | not available on this host (no build tree) |
| PDK | `~/.volare/gf180mcuD`, `SOURCES` = `open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| batch log banner for comparison | `Note: No compatibility mode selected!` and no `wnflag`; a run here with `~/.spiceinit` also prints `No compatibility mode selected!`, so that line does not reveal `wnflag` |

`~/.spiceinit` is a per-host file. Nothing in the repository sets `wnflag`
(`git grep` finds no mention outside this note and a prose reference in two
supply-sensitivity records about `num_threads`), and `sim/harness/batch.py`
does not write one into the batch job.

### 2. Deck

Regenerated exactly as Addendum 2 section 2: the harness's own composer
(`sim/run_corners.py reference-spur-band-top --corners ff --temps -40 --supply
3.3 --axis op=b7vs1p886 --no-write`, a stub `ngspice` first on `PATH` that
only copied the deck and ran nothing; the working directory the harness
created was deleted). The point is `ff`/-40 C/3.63 V, band 7, `vstart` 1.886 V.
Then the same four edits: PDK prefix is already `~/.volare/gf180mcuD`,
`.measure` lines dropped, `wrdata`/`set wr_singlescale` dropped, `tran 2e-9
8.0e-6 2.4e-6 100e-12` replaced by `tran 1e-11 1e-11`; the `klu` variant adds
only `.options klu` before `.options rshunt=1e12`. Scratch-deck digests:
`dc_default.spice` `13e54081…`, `dc_klu.spice` `60aa1afb…`. The composed deck
was not compared byte-for-byte with the job's `inputs/` deck (not read from
the job store here); the 414 scalar node lines compared below come from this
deck.

### 3. Results

"Init" is whether the real `~/.spiceinit` was read. "no init" runs set `HOME`
to an empty directory. The two "isolated" rows read a `~/.spiceinit` holding
only the one named line.

| build / run | `~/.spiceinit` content | variant | solver (log) | DC path (log) | `fb` | `xdut.dn` | `xdut.up` | `xdut.xpfd.xpfd.sbf` | `vctrl` | `lock` |
|---|---|---|---|---|---|---|---|---|---|---|
| batch pilots (Addendum 1) | n/a | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin, this host | real (`wnflag=1`, `num_threads=1`) | default | SPARSE 1.3 | **no gmin-stepping lines (direct Newton)** | **3.63** | 1.99269e-08 | 1.99269e-08 | **3.63** | 1.886 | **3.63** |
| pin, this host | real | `.options klu` | KLU | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin, this host | none | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin, this host | none | `.options klu` | KLU | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | 1.99269e-08 | 9.47584e-09 | 1.886 | 5.14279e-09 |
| pin, this host, isolated | only `set wnflag=1` | default | SPARSE 1.3 | no gmin-stepping lines | **3.63** | 1.99269e-08 | not extracted (0 of 414 node values differ from the real-init run) | **3.63** | 1.886 | **3.63** |
| pin, this host, isolated | only `set num_threads=1` | default | SPARSE 1.3 | dynamic gmin failed, true gmin completed | 1.79421 | 3.63 | not extracted (0 of 414 node values differ from the no-init run) | 9.47584e-09 | 1.886 | 5.14279e-09 |

Node-level comparison of the 414 scalar lines of the "Initial Transient
Solution" table (count of nodes whose printed value differs):

- real-init default vs `wnflag`-only default: **0** (identical).
- `num_threads`-only default vs no-init default: **0** (identical, the batch state).
- real-init default vs no-init default: 206.
- real-init default vs real-init klu: 204. Real-init klu vs no-init klu: 9.
- no-init default vs no-init klu: 29 (the same size as the ngspice-42 KLU
  difference in Addendum 1; last-digit scale differences).

The `klu` runs on this host used the same DC path as the batch image. Unlike
the arm64 pin in Addendum 2, no `klu` run here completed in dynamic gmin
stepping. One no-init `klu` run printed its table and then hit the 280 s
`timeout` while the dummy `tran` ran; the table was already complete, and the
run was not repeated.

### 4. Conclusion

- **Reference state reproduced, with captured artefacts.** The Linux x86_64
  pin reaches `fb` = 3.63 V, `lock` = 3.63 V, `sbf` = 3.63 V by direct Newton
  (no gmin-stepping lines) on the regenerated DC-only deck. So the earlier
  "local" observation was not mis-recorded, and Addendum 2's reading of it as
  the less documented outlier is superseded: it is now documented, and it
  is consistent with the -61.71 dBc / `lock_lvl` 3.63 V local pilot (the
  pilot's transient was not rerun here).
- **A single isolated change moves the split on this host.** With the same
  binary, same deck, same PDK, default options and same working directory:
  adding `set wnflag=1` to the init file takes the DC solution from the batch
  state to the reference state; adding `set num_threads=1` alone does not.
  Reading no init file at all gives the batch state, identical to the batch
  logs on the six key nodes. This is a reproduction of the split by an
  isolated change at the level of one DC operating point on one host.
- **Platform/build difference vs. configuration difference.** The
  hypothesis that Addendum 2 section 5 posed, a Linux-x86 build converging
  directly by itself, does not hold: the same Linux x86 pin lands in the
  batch state when `wnflag` is unset. What differs between the two backends
  is a host-level init setting, not (shown here) the binary. Nothing
  in the repository or in `sim/harness/batch.py` sets `wnflag` for the batch
  job, and the batch logs show no sign of it (the image's own init files
  were not read, so an image-level setting is not excluded), and the batch banner `No compatibility mode
  selected!` appears with and without it, so the banner cannot be used to
  tell the two apart.
- **Causality is still unverified beyond the DC point.** The mechanism is
  not shown. `wnflag=1` changes which model bin a multi-finger or wide
  device selects, which could change the circuit's DC equations (a different
  circuit, not a different homotopy path), but this was not checked here:
  no device-by-device bin comparison was made, and no transient was run, so
  the following are not established by this addendum: that the whole -61.71
  vs -75.57 dBc spur gap is caused by `wnflag`, that the batch image, once
  given `wnflag=1`, reproduces the local pilot, and that Addendum 2's arm64
  `ngbehavior=hsa` result (batch state) is consistent with `wnflag`
  semantics. The last point in particular is open: `hsa` is described in
  `~/.spiceinit`'s own comment as giving the effect implicitly, yet the
  arm64 runs with `hsa` were in the batch state. The arm64 pin also may not
  be the same build as this one.
- **Which DC solution is representative is still not decided here.** Both
  are valid solutions of a bistable latch, and the model-bin question above
  has to be answered first: if `wnflag=1` selects the bins the PDK intends,
  the batch image (which lacks it) is simulating a different device model
  selection on some devices and its numbers are the ones needing a caveat.
  That is for the testbench and spec owners to judge, not this note.

### 5. Implications and next step (none relaxes a requirement)

- The 2026-10-02 ruling stands: the pilots still do not match, so the grid
  is not submitted. -55 dBc, the 45-point mandate and DR-028 are unchanged.
- The decision is the testbench owners', as framed in section 4 of the
  original note, with the cause narrowed: make the simulator configuration
  that the campaign depends on part of the campaign inputs (a reviewed
  change, for example setting `wnflag` and the thread count inside the
  deck's control block, or recording the init file as part of the reference
  environment under DR-028), and pin the PFD latch's initial state so the
  result does not rely on which homotopy path a build takes. Either is a
  reviewed campaign-input or spec change; neither was made here.
- A cheap, decisive follow-up that this addendum does not run: one
  single-point local run of the pilot deck with `wnflag=1` and then without
  it (full transient, `--backend local`, one point at a time, which is
  inside the host rules) to see whether the -61.71 vs -75.57 dBc gap tracks
  the init setting, and one comparison of the model bins selected for the
  nf > 1 devices with and without `wnflag`. Owner: the testbench owner or an
  agent on a Linux worker; both are single runs.
- Evidence gap restated: a local run still records no equivalent of
  `ngspice.env` (binary, banner, init files read, `wnflag`). This case
  makes that gap concrete, since the deciding input was an unrecorded
  per-host init file. Tracked generically as 2AMLogic/klayout-tools#2834.

## Addendum 4 (2026-10-08, later): the full-transient follow-up; the spur gap tracks the host init file

Appended after running the follow-up Addendum 3 section 5 left open. Everything
above stays as written. No batch job was submitted and nothing was spent. No
record under `sim/*/records/` was written (`--no-write`), and `spec/`,
`tb.json`, the deck and `sim/harness/batch.py` were not touched. Two single
local runs, one at a time, `OMP_NUM_THREADS=2`, on `loom-worker-2` with the
pinned ngspice-46 (`~/.local/bin/ngspice`) and PDK `c6d73a35…`.

### 1. Runs

Point `ff` / -40 C / 3.63 V, band 7 (`op=b7vs1p886`), via
`sim/run_corners.py reference-spur-band-top --corners ff --temps -40 --axis
op=b7vs1p886 --backend local --timeout 6000 --no-write`.

| run | init file read | `spur_dbc` | `lock_lvl` | DC state |
|---|---|---|---|---|
| A: real `~/.spiceinit` (`set wnflag=1`, `set num_threads=1`; sha256 `94a971c8…`) | yes | **-61.7103** | **3.63 V** | reference (Addendum 3) |
| B: `HOME` set to an empty directory (with `.volare` linked), no init | none | **-75.5655** | **5.12765e-9 V** | batch (Addendum 3) |
| batch pilot 1 / re-pilot (Addendum 1) | n/a | -75.57 / -75.5655 | 5.1e-9 / 5.13e-9 V | batch |

Run A wall clock was 16 min (host shared with other work). Run B's `spur_dbc`
and `lock_lvl` equal the batch re-pilot's figures to the printed digits; run
A's -61.7103 equals the earlier local pilot's -61.71.

### 2. Conclusion

- On the same binary, PDK and deck, **the complete host init file alone moves
  the closed-loop result between the two pilot values**: with the init file
  (`set wnflag=1` and `set num_threads=1`) the loop is in the locked state
  (-61.71 dBc, `lock_lvl` 3.63 V); without any init file the result is the
  batch one (-75.57 dBc, `lock_lvl` ~5e-9 V). Together with Addendum 3 (the DC
  point splits on `wnflag` alone), this makes simulator configuration, not the
  PDK, the solver or run-to-run noise, the explanation for the batch-vs-local
  gap at this point. Which of the two init lines matters in the transient was
  not isolated: the thread count is not excluded for the transient.
- Not established: that `set wnflag=1` alone (rather than `set num_threads=1`
  or the combination) suffices in the transient; Addendum 3 isolated `wnflag`
  at the DC point only, and run A used the whole file. A controlled
  full-transient pair (`wnflag`-only versus `num_threads`-only, or no init)
  would settle it and was not run. The model-bin comparison for nf > 1
  devices was not run, so which configuration selects the bins the PDK intends,
  and which state represents the design, is still undecided. That is for the
  testbench and spec owners.
- The 2026-10-02 ruling stands: the pilots do not match under the batch
  image's configuration, so the 45-point grid is not submitted. Submitting it
  needs the campaign inputs to carry the setting (a reviewed change) or the
  image to supply it, followed by a re-pilot that matches.

## Addendum 5 (2026-10-08, later): the controlled full-transient pair; `set wnflag=1` alone reproduces the local result, `set num_threads=1` alone reproduces the batch result

Appended after running the pair Addendum 4 left open. Everything above stays as
written. No batch job was submitted and nothing was spent. No record under
`sim/*/records/` was written (`--no-write`), and `spec/`, `tb.json`, the deck
and `sim/harness/batch.py` were not touched. Two single local runs, strictly
one after the other, `OMP_NUM_THREADS=2`, on `loom-worker-2`. The host init
file was not modified: each run set `HOME` to a scratch directory holding a
one-line `.spiceinit` and a link to the PDK tree (as run B of Addendum 4).

### 1. Setup

- Simulator: ngspice-46 (KLU build), binary `~/.local/bin/ngspice` ->
  `~/.local/ngspice/bin/ngspice`, sha256 `c874869b…`. The same binary as
  Addendum 4.
- PDK: gf180mcu, volare version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
- Command, as in Addendum 4: `sim/run_corners.py reference-spur-band-top
  --corners ff --temps -40 --axis op=b7vs1p886 --backend local --timeout 6000
  --no-write`.

### 2. Runs

| run | init file content (sha256) | `spur_dbc` | `lock_lvl` | wall clock |
|---|---|---|---|---|
| A (Addendum 4): real `~/.spiceinit` | `set wnflag=1` + `set num_threads=1` (`94a971c8…`) | -61.7103 | 3.63 V | 16 min |
| C: scratch `HOME` | only `set wnflag=1` (`82a66e01…`) | **-61.7103** | **3.63 V** | 863 s |
| D: scratch `HOME` | only `set num_threads=1` (`2ef8c1ce…`) | **-75.5655** | **5.12765e-9 V** | 1219 s |
| B (Addendum 4): scratch `HOME`, no init | none | -75.5655 | 5.12765e-9 V | n/a |

Run C's other reported metrics (for example `up_lvl` 0.15675, `dn_lvl`
0.110875, `vctrl_ripple_mv` 7.559) match the local state; run D's (`up_lvl`
0.280785, `dn_lvl` 0.110049, `vctrl_ripple_mv` 7.688) match the batch state of
Addendum 4 run B. The wall clocks were taken on a shared host and are not a
performance comparison.

### 3. Conclusion

- Established, for this point only (ff / -40 C / 3.63 V, band 7): on the same
  binary, PDK and deck, **`set wnflag=1` alone gives the locked-state result
  (-61.71 dBc, `lock_lvl` 3.63 V)**, identical to the full host init file to
  the printed digits, and **`set num_threads=1` alone gives the batch result
  (-75.57 dBc, `lock_lvl` ~5e-9 V)**, identical to no init file. The thread
  count does not account for the gap in this transient; `wnflag` does. This
  closes the open item in Addendum 4 section 2 and extends Addendum 3's DC-point
  isolation to the full transient.
- Not established: why `wnflag` changes the result. The model-bin selection
  mechanism described in the host init file's comment was not checked here: no
  bin-selection comparison for nf > 1 devices was run, so this addendum states
  the dependence on the setting, not its cause. Run D also completed
  without the setting, so the abort described in that comment did not occur
  for this deck at this point. Other corners, temperatures and band codes
  were not run, so the dependence is shown at one point only. Which
  configuration represents the design remains undecided; that is for the
  testbench and spec owners.
- Tool gap, already tracked: the local runs leave no recorded equivalent of
  the batch job's `ngspice.env` (the init files and `HOME` in force), which
  is how this had to be reconstructed by hand. That is covered by
  2AMLogic/klayout-tools#2834; no duplicate was filed.
- The 2026-10-02 ruling stands and the 45-point grid stays held. Submitting
  it still needs the campaign inputs to carry the setting (a reviewed change)
  or the image to supply it, followed by a re-pilot that matches. Per this
  addendum the setting that matters is `wnflag`; `num_threads` is not needed
  to reproduce the local state at this point.

## Addendum 6 (2026-10-09): `set wnflag=1` written into the campaign's `analyses` does not reproduce the local result

Appended after trying the first candidate for "the campaign inputs carry the
setting" (Addendum 5, last bullet). Everything above stays as written. No batch
job was submitted and nothing was spent. No record under `sim/*/records/` was
written (`--no-write`), and no file other than this note changed: the
`tb.json` edit that was tried was reverted.

### 1. What was tried

`set wnflag=1` was added as the first entry of `analyses` in
`sim/reference-spur-band-top/testbench/tb.json` (next to the existing
`set wr_singlescale` entry). The harness emits `analyses` verbatim inside the
`.control` block, so the composed deck contained `set wnflag=1` at deck line
84, ahead of `save` and `tran` (confirmed in the run's `.spice` file).

One local run, `loom-worker-1`, `OMP_NUM_THREADS=2`, the same command as
Addendum 5 (`sim/run_corners.py reference-spur-band-top --corners ff --temps
-40 --axis op=b7vs1p886 --backend local --timeout 6000 --no-write`), with
`HOME` set to a scratch directory holding a link to the PDK tree and an
**empty** `.spiceinit` (sha256 `e3b0c442…`), so the only source of the setting
was the deck. Simulator ngspice-46 (KLU build); the binary's sha256 on this
host begins `71db4f12`, not the `c874869b…` recorded in Addendums 4 and 5, so
this host's build is not shown to be byte-identical to that one. Because of
that difference, run F repeats run E on this same host and binary with the
setting moved into the init file, as the positive control that E alone lacks.

### 2. Result

| run | where `wnflag=1` is set | `spur_dbc` | `lock_lvl` |
|---|---|---|---|
| C (Addendum 5) | init file, read at simulator start | -61.7103 | 3.63 V |
| E (this addendum) | inside the deck's `.control` block | **-75.5655** | **5.12765e-9 V** |
| B (Addendum 4) | not set | -75.5655 | 5.12765e-9 V |

| F (this addendum, positive control) | init file holding only `set wnflag=1` (sha256 `82a66e01…`), same host, binary and command as E | **-61.7103** | **3.63 V** |

Run E matches the unset case on every metric printed (for example `up_lvl`
0.280785, `dn_lvl` 0.110049, `vctrl_ripple_mv` 7.68823).

### 3. Conclusion

- Established, for this point only, on this host's binary (run F reproduces the
  Addendum 5 locked state with the init-file setting, so the E-versus-F
  comparison is controlled): setting `wnflag` from inside the deck's
  `.control` block leaves the batch-state result unchanged. The setting that
  reproduced the local state in Addendum 5 does so when it is in place before
  the simulator reads the netlist (an init file), not when set after the
  netlist has been read.
- Not established: the mechanism. The most likely reading is that the
  per-finger model-bin choice is made while the netlist is parsed, before
  `.control` commands run, but this run did not check that and does not
  show it.
- Consequence: the campaign inputs cannot carry the setting through
  `analyses`. The remaining routes are an init file that exists on the
  executing host before the simulator starts (for the batch fleet, an image
  or job-environment change in 2AMLogic/2am, which is not in this repository)
  or a harness feature that stages a per-job init file or `HOME`. Either needs
  a reviewed decision; neither was attempted here.
- The 2026-10-02 ruling stands and the 45-point grid stays held.
