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
