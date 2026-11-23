# Local/batch equivalence pilot, 2026-11-14 — band-7 reference-spur deck at ff / −40 °C / 3.63 V

One point, run twice on each execution backend, to answer the one question
[#755](https://github.com/2AMLogic/gf180-pll/issues/755) and
[DR-040](../spec/decision-records/DR-040-simulator-init-file-is-repository-staged-per-job-on-both-backends.md)
leave open after the shared `.spiceinit` landed: **does
`sim/run_corners.py --backend batch` now reproduce what `--backend local`
produces, on the deck whose disagreement exposed the missing `wnflag`?**

It is a *backend-equivalence* measurement, not reference-spur evidence. The
−55 dBc line in `spec/pll.md` is not an equivalence tolerance and is not used
as one here; the spur numbers below are reported because they are part of what
has to match, not as a verdict on the spec row. The 45-point grid in
[#533](https://github.com/2AMLogic/gf180-pll/issues/533) stays gated on this
pilot and is **not** authorised by it.

## The gate this pilot is scored against

The testbench/spec owner recorded the numerical matching tolerance on #755 on
2026-10-22 (fleet decision 20261021-r1, D16). Quoted so a reader does not have
to leave this file:

1. **Same DC operating point first.** `fb` and `lock_lvl` must agree. A run
   that settles into a different loop state fails outright, whatever the spur.
2. **Then the spur, within noise.** Noise is measured, not assumed. Repeat each
   backend at least twice. The local-vs-batch difference must be no larger than
   the run-to-run spread observed within either backend. 1 mV on the
   operating-point nodes and ±0.5 dB on the spur are the **ceiling**: if the
   noise itself is larger than that, report it rather than widening the gate.
3. Record both backends' ngspice banner, the `.spiceinit` hash and the raw
   values in the pilot record.

Point 1 is a pass/fail gate on its own, scored before the spur is looked at.
Point 2 is the part worth reading carefully: the gate is **the measured
spread**, and the 1 mV / ±0.5 dB figures are its upper bound, not a band to
land inside.

## What was run

Four runs of one point — `ff` / −40 °C / 3.63 V, band 7, `op=b7vs1p886`,
`vstart` 1.886 V — two on each backend, all against
`e752ace3f06fb627fa4af9ccd41907de8b950add` with a clean tree:

| # | backend | record | executed on |
|---|---|---|---|
| L1 | `local` | `20261114-005110-e752ace` | `loom-worker-3` |
| L2 | `local` | `20261114-011803-e752ace` | `loom-worker-3` |
| B1 | `batch` | `20261114-005240-e752ace` | `ip-172-31-87-79` |
| B2 | `batch` | `20261114-005640-e752ace` | `ip-172-31-2-49` |

The two batch repeats landed on **different instances**, so B1↔B2 measures
instance-to-instance spread, not just repeat-to-repeat on one machine.

Commands (the `--subset-reason` differs only in the repeat number):

```sh
python3 sim/run_corners.py reference-spur-band-top \
  --corners ff --temps -40 --axis op=b7vs1p886 \
  --backend local --timeout 7200 -j 1 \
  --claim "#755 -> #533: does the batch backend reproduce the local reference closed-loop state at ff / -40 C / 3.63 V once both backends stage the same simulator init file?" \
  --subset-reason "single-point local/batch equivalence pilot mandated by #755 and DR-040 ..."

python3 sim/run_corners.py reference-spur-band-top \
  --corners ff --temps -40 --axis op=b7vs1p886 \
  --backend batch --batch-apply --batch-wait-for-capacity 600 \
  --timeout 7200 -j 1 \
  --claim "..." --subset-reason "..."
```

## The two environments

Both backends ran the **same ngspice build** — not merely the same version
string. The banner's creation date is the discriminator, because the patched
and the unpatched ngspice-47 both print `ngspice-47`:

| | local | batch |
|---|---|---|
| banner | `ngspice-47 : Circuit level simulation program` | same |
| `Compiled with` | `KLU Direct Linear Solver` | same |
| creation date | `Fri Nov 13 23:19:32 UTC 2026` | `Fri Nov 13 23:19:32 UTC 2026` |
| binary | `~/.local/opt/ngspice-47p1/bin/ngspice`, sha256 `e12148ba…1314` | from the job image: manifest `eda-batch-image/1`, built `2026-11-14T00:22:48Z`, source commit `2ef7e4981`, `pin_digest` `838a0d68…6e08c`, `base_ami` `ami-08b275ac6cc5dbefb`, `tools.ngspice` `ngspice-47` |
| PDK | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (`~/.ciel`) | `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (`/opt/pdk`) |
| `.spiceinit` sha256 | `d6efd5b23e4c9bcb6d97e0516269077b983e81ac453ca7ec74f412cfc0efd385` | identical |
| init marker in the deck's own output | `gf180-pll-spiceinit-applied wnflag=1` | same |
| `OMP_NUM_THREADS` | unset (build's native threading) | unset (build's native threading) |
| CPU | Intel Xeon Platinum 8488C, 16 cores, shared with other sweeps | Intel Xeon Platinum 8375C, 16 cores |

The two CPUs are *different* (8488C locally, 8375C on the instances), as are
the core allocations the two schedulers gave the run — so the agreement below
is not an artefact of running the same work on the same silicon.

The PDK revision is byte-identical to the repository pin (`sim/pdk.json`) on
**both** sides, which was not true of the ngspice-42-era image DR-028 was
written against.

Two caveats on this table, stated rather than buried:

- The source sha the operator cites for the p1 build (`69caffe6…33c3`,
  2AMLogic/2am#7262), and the launch template's AMI id, are **not verifiable
  from this repository** — neither appears in anything the job returns. What
  *is* verifiable here is the binary checksum, the banner, the creation date
  and the image manifest the job itself reports, and that the creation date
  matches on both sides; that is what is recorded above, and the operator's
  identifiers are deliberately not restated as if this repository had checked
  them.
- The local binary's checksum is a property of this worker. It is recorded so
  a future reader can tell whether they are on the same build, not as a claim
  that every worker carries it.

## Result: the two backends agree exactly

Every reported quantity is identical across all four runs, to the last digit
the harness prints. Not "within tolerance" — identical.

### Gate 1 — the DC operating point

From each run's own `Initial Transient Solution` table:

| node | L1 | L2 | B1 | B2 |
|---|---|---|---|---|
| `fb` | 3.63 | 3.63 | 3.63 | 3.63 |
| `vctrl` | 1.886 | 1.886 | 1.886 | 1.886 |
| `lock` | 3.63 | 3.63 | 3.63 | 3.63 |
| `clk` | 3.63 | 3.63 | 3.63 | 3.63 |
| solver | `SPARSE 1.3` | `SPARSE 1.3` | `SPARSE 1.3` | `SPARSE 1.3` |
| gmin stepping | none (direct Newton) | none | none | none |

This **is** the reference state the diagnosis attributes to `wnflag=1` — the
state the batch backend could not reach before the shared `.spiceinit`
(`fb` 1.79421, `lock` ≈ 5e-9 V, reached through dynamic-then-true gmin
stepping). Gate 1 passes.

### Gate 2 — the measured quantities

| measure | all four runs | within-local spread | within-batch spread | local − batch |
|---|---|---|---|---|
| `lock_lvl` (V) | 3.63 | 0 | 0 | 0 |
| `up_lvl` (V) | 0.154922 | 0 | 0 | 0 |
| `dn_lvl` (V) | 0.110885 | 0 | 0 | 0 |
| `fout` (Hz) | 2.000290e+08 | 0 | 0 | 0 |
| `ffb` (Hz) | 2.500330e+07 | 0 | 0 | 0 |
| `nmeas` | 8.00011 | 0 | 0 | 0 |
| `ferr` | −4.29204e−05 | 0 | 0 | 0 |
| `spur_dbc` (dBc) | −53.512956778089766 | 0 | 0 | 0 |
| `spur_lsb_dbc` (dBc) | −53.512956778089766 | 0 | 0 | 0 |
| `spur_usb_dbc` (dBc) | −53.825871875152664 | 0 | 0 | 0 |
| `spur_tie_dbc` (dBc) | −55.69584516965502 | 0 | 0 | 0 |
| `carrier_v` (V) | 2.3058442794905267 | 0 | 0 | 0 |
| `vctrl_ripple_mv` | 7.5575119999999885 | 0 | 0 | 0 |
| `drift_q_fc` | −0.21750508622187167 | 0 | 0 | 0 |
| `dt_int_mean` (s) | 6.342910843621866e−11 | 0 | 0 | 0 |

**The measured run-to-run spread is zero on both backends, and the
local-versus-batch difference is also zero.** `0 ≤ 0` satisfies the owner's
gate, and it satisfies it without appealing to the 1 mV / ±0.5 dB ceiling at
any point.

Reproduce the whole table from the committed evidence:

```sh
cd sim/reference-spur-band-top
for r in 20261114-005110 20261114-011803 20261114-005240 20261114-005640; do
  grep -E "Direct Linear Solver|gmin stepping|spiceinit-applied" \
    "corners/$r-e752ace/ff_-40c_3.63v_b7vs1p886.log"
  grep -E "^(fb|vctrl|lock|clk)[[:space:]]" \
    "corners/$r-e752ace/ff_-40c_3.63v_b7vs1p886.log"
  cat "corners/$r-e752ace/raw_measures.csv"
done
```

## What this does *not* establish

- **It is one point on one deck with one pair of builds.** It says nothing
  about any other campaign, corner, quantity or version pair, and it does not
  relax DR-028's cross-version comparison quarantine anywhere.
- **It is not reference-spur evidence.** All four runs record
  `spur_dbc` = −53.513 dBc against the manifest's −55 dBc check and are
  minted `FAIL` for that reason. That verdict is about `spec/pll.md`'s row,
  not about backend equivalence, and this pilot neither supports nor
  impeaches it — see the next point for why it cannot.
- **It does not re-establish, or explain the loss of, the −61.71 dBc
  figure.** `BATCH-IMAGE-DIAGNOSIS-2026-10-08.md` Addendum 4 run A measured
  −61.7103 dBc at this exact point *in this exact DC state*, on **ngspice-46**
  against open_pdks **`c6d73a35…`**. This pilot measures −53.513 dBc on
  ngspice-47p1 against open_pdks `f6eeac7d…`. **Two** variables moved — the
  simulator and the PDK revision — so nothing here attributes the ~8 dB shift
  to either, and a controlled pair would be needed to. What the pilot does
  show is that whatever moved it moved *both backends identically*, which is
  the question it was run to answer.
- **It does not authorise #533's 45-point grid.** The grid was gated on this
  pilot; the pilot passing removes that gate and no other. The ~8 dB shift
  above is a reason to settle the version/PDK question before spending the
  grid, not a reason to spend it sooner.

## Owed next

1. Quantify the ngspice-46 → ngspice-47p1 and `c6d73a35…` → `f6eeac7d…`
   shift on this deck with a controlled pair, before any −55 dBc verdict is
   read off an ngspice-47 record. Not scoped by #755.
2. `sim/run_corners.py` still prints "every point of this run is expected to
   fail" on any `ngspice-47` banner, including the patched build every point
   of this pilot completed on. The warning is keyed on a version string that
   cannot distinguish the two builds; it needs a capability probe. Filed
   separately.

## Addendum (2026-11-17, later): which rows of the environment table are re-derivable

Appended after Judge evaluation of #925 flagged that the build-identity rows of
"The two environments" cannot be checked from this repository. Everything above
this heading stays as written. No simulation was run, no batch job was submitted
and nothing was spent for this addendum; no record under `sim/*/records/` was
written; no harness file or deck was changed. It only classifies the rows of the
table above against what this repository commits.

**Run-time-observed, not re-derivable from this repository**: the banner and
`Compiled with` rows, the banner's creation date (`Fri Nov 13 23:19:32 UTC
2026`), the local binary's path and sha256 (`e12148ba…1314`), the image-manifest
fields (`pin_digest` `838a0d68…6e08c`, source commit `2ef7e4981`, `built`
`2026-11-14T00:22:48Z`, `base_ami`), the CPU models (Xeon 8488C local, Xeon
8375C batch) and `OMP_NUM_THREADS`. These values were observed at run time —
locally on the submitting worker, on batch from the per-job `ngspice.env`
capture and the ngspice banner. The capture is collected best-effort by
`sim/harness/batch.py` but deliberately not published into a point's rundir
(`CONTRACT_OUTPUT_NAMES` keeps the four contract-named files out of a possibly
shared rundir), and the committed per-corner logs begin at the `.spiceinit`
marker without the banner, so the creation date is not recoverable from the
retained evidence either. Each of the discriminating values above — the
banner creation date, the binary sha256 and the image-manifest fields — hits
only this document in the tree, as does the batch CPU model (`8375C`);
searches re-run on this branch, 2026-11-17. The one exception is the local CPU
model (`8488C`), which also appears in `sim/BATCH-IMAGE-DIAGNOSIS-2026-10-08.md`
(as both sides of an ngspice-46-era comparison) and
`.loom/docs/telemetry-overhead.md` (a fleet-host note for an unrelated tool) —
prose run-time observations from other sessions that neither record this
pilot's environment nor make its CPU row re-derivable. The CPU and
`OMP_NUM_THREADS` rows stand as non-re-derivable on the run-time-observation
ground alone: the retained per-corner logs record no CPU model and no thread
count.

**Re-derivable from committed evidence**:

- the PDK revision `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, byte-identical
  to the pin in `sim/pdk.json`;
- the `.spiceinit` sha256 `d6efd5b23e4c…f385`: the exact bytes are committed as
  `INIT_TEXT` in `sim/harness/siminit.py`, whose `INIT_SHA256` hashes to this
  value;
- the init marker `gf180-pll-spiceinit-applied wnflag=1`, printed in each of
  the four committed logs;
- the solver line (`Using SPARSE 1.3 as Direct Linear Solver`) and the Gate 1
  DC state (`fb` 3.63, `vctrl` 1.886, `lock` 3.63, `clk` 3.63, zero `gmin
  stepping` lines), read out of each of the four retained logs;
- the measured agreement itself: each of `raw_measures.csv`,
  `spectrum_worst.csv` and `spur_by_corner.csv` is one md5 across all four
  records under `sim/reference-spur-band-top/corners/*-e752ace`.

The pilot's conclusion — that the batch backend reproduces the local reference
exactly — rests only on these re-derivable rows. The attribution rows matter if
a later batch result ever disagrees with a local one: that disagreement is what
the `ngspice.env` capture exists to attribute (`sim/harness/batch.py`, citing
#533). The unbuilt remedy would be to commit the per-job env captures under the
record's own directory, so the attribution table becomes re-derivable the way
the measurements already are; that needs a rule for what is safe to publish
from a job environment and is deliberately not decided here. Tracked in #964.

## Addendum (2026-11-22): the controlled comparison to the ruling's ngspice-46 reference; #533's spend condition

Appended to discharge the one step the 2026-11-22 curation of #533 (Champion
approval 2026-11-22T12:43Z) puts between this pilot and the 45-point grid:
*"The ruling names the local ngspice-46 reference. If the current pair only
establishes 47p1-to-47p1 parity, document the controlled comparison to that
reference before treating the spend condition as met."* Everything above stays
as written. No simulation was run, no batch job was submitted and nothing was
spent for this addendum; no record was written and no harness file, deck or
spec file was changed.

### The reference the ruling names

The 2026-10-02 operator ruling gates the grid on the pilot *"matches the local
ngspice-46 run"*. The concrete ngspice-46 run at this exact point is run A of
[`BATCH-IMAGE-DIAGNOSIS-2026-10-08.md`](BATCH-IMAGE-DIAGNOSIS-2026-10-08.md)
Addendum 4: **−61.7103 dBc**, `lock_lvl` 3.63 V, in the reference
(`wnflag=1`) DC state, on the then-pinned ngspice-46 with PDK `c6d73a35…` and
the host `~/.spiceinit` (sha256 `94a971c8…`); Addendum 5 later isolated
`set wnflag=1` as the line that selects this state.

### The comparison

| | ruling's reference (Addendum 4 run A) | this pilot (L1, L2, B1, B2) |
|---|---|---|
| simulator | ngspice-46 (worker pin at the time) | ngspice-47p1, **same build on both backends** (banner creation date `Fri Nov 13 23:19:32 UTC 2026` on all four) |
| PDK | `c6d73a35…` | `f6eeac7d…` (= the `sim/pdk.json` pin) |
| simulator init | host `~/.spiceinit` `94a971c8…` | repository-staged `.spiceinit` `d6efd5b2…` (DR-040), marker in all four logs |
| DC state `fb`/`lock`/`clk` | 3.63 V | 3.63 V, all four runs |
| `vctrl` | 1.886 V | 1.886 V, all four runs |
| `lock_lvl` | 3.63 V | 3.63 V, all four runs |
| `spur_dbc` | **−61.7103 dBc** | **−53.512956778089766 dBc**, all four runs |

Scored against the owner's gate: the DC operating point — scored first — is
**identical to the reference**; the ruling's guarded failure (batch landing in
the other, gmin-stepped loop state at `lock_lvl` ≈ 5e-9 V) does not occur. The
spur differs by **8.20 dB**, and **two** toolchain variables moved between the
runs. The committed controlled decomposition that exists is the overlap point
of [`REPIN-DELTAS-f6eeac7-closed-loop.md`](REPIN-DELTAS-f6eeac7-closed-loop.md)
(a different deck and corner — 150 MHz `reference-spur`, `typical`/27 °C/
3.30 V): there, the simulator alone (ngspice-46 → 47, same PDK) moved
`spur_dbc` by 6.06 dB **in the same direction** as this shift, and the PDK
alone (`c6d73a35` → `f6eeac7`, same simulator) moved it 3.65 dB the opposite
way. The 8.20 dB shift here is consistent in sign and magnitude with that
pattern, but it is **not attributed for this deck**: no worker in the fleet
carries the ngspice-46 binary any more (the worker spec and the job image both
pin the 47p1 build), so the controlled pair this deck would need — the pilot's
own "Owed next" item 1 — remains unrun and open.

### Why the spend condition is treated as met

1. **The failure mode the ruling guarded against is identified and excluded.**
   The 2026-10-02 pilots' mismatch was the init-file/`wnflag` DC-state split
   (Addendums 4–5), since fixed for every backend by DR-040's
   repository-staged init file. On the toolchain the whole fleet now pins, the
   batch backend reproduces the local run **exactly** (measured spread 0
   within and across backends, section "Result" above).
2. **The ruling's literal reference is unrunnable today.** "The local
   ngspice-46 run" cannot be re-executed or re-matched anywhere in the fleet;
   its successor — the pinned local ngspice build, byte- and
   creation-date-identical on both backends — is what the condition can
   compare against, and it matches.
3. **The version shift is disclosed, not hidden.** The grid records carry
   ngspice-47/PDK `f6eeac7` provenance; DR-028's cross-version quarantine
   governs any comparison with ngspice-46-era figures; the open 8.20 dB
   attribution question is named here and travels with the campaign record.

Stated plainly so no reader misses it: at this pilot point the current pinned
toolchain reads **−53.513 dBc, which misses the −55 dBc line** where the
ngspice-46-era reference passed it (−61.71). The grid measures what the pinned
toolchain produces; its record reports every point's measured verdict and
names every miss against the unchanged −55 dBc target (DR-024 Decision 2),
with this addendum as the version context.
