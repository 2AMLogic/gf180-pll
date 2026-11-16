# Re-pin deltas: lock-detector, lock-window and divider records under open_pdks `f6eeac7`

`sim/` evidence is append-only, so re-qualifying a frozen reference record
after a PDK pin changes mints a *new* record and names the old one in
**Supersedes** (`sim/README.md`, "Status / supersession language"). That
convention records *that* a re-run happened; it does not say *how much the
numbers moved*, which on a re-qualification is the whole finding. This
document is that missing half for the lock-detector / lock-window / divider
group of the #790 re-qualification — itself the re-qualification half of the
#788 fleet re-pin
(`c6d73a35f524070e85faff4a6a9eef49553ebc2b` → `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`,
pinned by #789). It is the sibling of
[`REPIN-DELTAS-f6eeac7-devchar.md`](REPIN-DELTAS-f6eeac7-devchar.md), which
does the same job for the device-characterization group (#825).

Every table below is generated from the two committed records by
`sim/lib/record_delta.py` and is reproducible from the tree alone; the exact
command sits above each one. Nothing here edits a record.

## The scope is nine records, not thirteen

#827 states this group as "13 records", counted from the citations in
`README.md`, `sim/CHARACTERIZATION.md` and
`docs/chipalooza/challenge-5-proposal.md`, and asks for that count to be
re-derived before it is relied on. Re-derived, the **live** (not-yet-superseded)
cited records in those directories are **nine**. The other four are already
superseded by a cited successor inside the same scope, which #827's Out of
Scope section excludes:

| directory | cited record | disposition |
|---|---|---|
| `lock-detector` | `20260731-162119-0a12e6c` | already superseded by `20260802-050119-c24ee3a` → out of scope |
| `lock-detector` | `20260802-050119-c24ee3a` | already superseded by `20260916-052313-b1633b5` → out of scope |
| `lock-detector` | `20260916-122705-98c935b` | already superseded by `20260919-002812-1b12179` → out of scope |
| `divider-ratio` | `20260731-171817-0a12e6c` | already superseded by `divider-ratio-chain`'s `20260802-100727-082c879` → out of scope |
| `lock-detector` | `20260916-052313-b1633b5` | live — **not re-runnable** (§ "Two records cannot be re-run") |
| `lock-detector` | `20260919-002812-1b12179` | live — **re-qualified here** |
| `lock-window-sizing` | `20260915-202802-79c0cee` | live — **not re-runnable** (§ "Two records cannot be re-run") |
| `lock-window-trim` | `20260917-185928-8adff3d` | live — **still owed** (§ "What is still owed") |
| `lock-window-proxy` | `20260925-050022-6d57802` | live — **re-qualified here** |
| `lock-window-bisection` | `20260925-162032-e341b58` | live — **re-qualified here** |
| `divider-ratio-dff` | `20260801-125114-3f883e3` | live — **re-qualified here** |
| `divider-ratio-chain` | `20260802-100727-082c879` | live — **re-qualified here** |
| `divider-ratio-cell` | `20260801-140529-3f883e3` | live — **re-qualified here** |

Re-derive the supersession side of that table with
`bash sim/lib/check-record-supersession.sh`, which builds the same graph from
the records' own **Supersedes** fields.

## What was re-run

| campaign | superseded record | new record | grid |
|---|---|---|---|
| `lock-detector` | `20260919-002812-1b12179` | `20261114-091604-ffbc0e2` | 205 pts (PVT × phase-error ladder × trim code) |
| `divider-ratio-dff` | `20260801-125114-3f883e3` | `20261114-080736-f53d562` | 45 pts (full PVT) |
| `divider-ratio-cell` | `20260801-140529-3f883e3` | `20261114-083606-f53d562` | 90 pts (45 PVT × 2 input rates) |
| `divider-ratio-chain` | `20260802-100727-082c879` | `20261114-093804-ad9eef8` | 235 pts (N = 4…64, non-rectangular) |
| `lock-window-bisection` | `20260925-162032-e341b58` | `20261114-191343-8cb0847` | 13 pts (3 bundle blocks × phase-step ladder) |
| `lock-window-proxy` | `20260925-050022-6d57802` | `20261114-194051-c8750de` | 234 decks (2 stimulus decks × the full 13-bundle PVT grid) |

All six: open_pdks `f6eeac7`, ngspice-47, **every point executed on the batch
fleet** — the host that minted each record ran no ngspice of its own. #827's
test plan asks for the batch image's `SOURCES` stamp to be confirmed before
the grids are spent; it was, by #825's four records already on `main`, each
reporting `batch` execution under open_pdks `f6eeac7…`, so no probe grid was
paid for twice.

## Verdict

**No per-corner verdict flipped and no stated limit moved**, on any of the
822 graded per-corner rows across the six benches.

**One derived verdict did move**, on `lock-window-proxy`, and it is the single
finding this group owes under #827's third acceptance criterion: the `clk_fb`
pad-proxy *policy* row goes from `all in-band` to `OUT OF BAND somewhere`. It
is not a per-corner row and `record_delta.py` cannot see it — it lives in
`proxy_candidates.csv`, a reduction over the whole grid — so it is set out in
full in § "The one real finding" below and filed as **#951** rather than left
in a table.

| campaign | graded rows | verdict flips | limits changed | worst relative movement |
|---|---|---|---|---|
| `lock-detector` | 205 | 0 | 0 | 0.0018 % (`ld_lvl`, `ss`/125 °C/2.97 V) |
| `divider-ratio-dff` | 45 | 0 | 0 | 0.043 % (`hqc0`, `fs`/−40 °C/3.30 V) |
| `divider-ratio-cell` | 90 | 0 | 0 | 303 % (`pw_modout_s`, `fs`/125 °C/2.97 V) — edge aliasing, see below |
| `divider-ratio-chain` | 235 | 0 | 0 | 338 % (`fbpw`, `ss`/125 °C/2.97 V) — edge aliasing, see below |
| `lock-window-bisection` | 13 | 0 | 0 | see § "The bisection predecessor ran a derive module that never landed" |
| `lock-window-proxy` | 234 | 0 | 0 | 8804 % (`tcq_raw`, `all-fast`/125 °C/2.97 V) — a raw edge time that straddles zero; see § "The one real finding" |

`record_delta.py` lists six rows on `lock-window-bisection` under "per-corner
verdict flips". None of them is a flip: all six are **FAIL in both** records,
on the same check (`lock_pre min=3.2`) for the same reason — the `ff` and `ss`
bundles settle at a static offset wider than their own rule-selected window,
so `LOCK` is correctly low before the step, which the predecessor's own record
states. The comparator lists them because the failure *detail string* carries
the measured value and that value moved. Read the "old" and "new" columns of
that table, not its heading.

The load-bearing derived artifacts in this group all reproduce:

- `lock-detector`'s `window_edges` table — what `spec/pll.md`'s Lock detector
  row and `docs/chipalooza/challenge-5-proposal.md` section 5 actually cite —
  is **byte-identical** to the superseded record's at every ladder corner,
  including both load-bearing edges (`[1.14, 1.16)` ns at `fs`/−40 °C/3.63 V
  and `[1.78, 1.80)` ns at `ss`/125 °C/2.97 V). The ratified `[1, 2]` ns band
  verdict and the 1.53–1.58× PVT spread figure therefore rest on the re-pinned
  PDK unchanged.
- `divider-ratio-chain`'s `retiming_margin` table — DR-001 Decision 3's
  answer — still reads `CLOSES` on every row, with a worst movement of
  **0.03 ps**: at the corner DR-001 names (`ss`/125 °C/2.97 V, N=64, 200 MHz)
  the setup margin goes 3.0283e-10 → 3.0286e-10 s against a 5 ns VCO period.
  DR-001's named fallback (retime on the first cell's output at VCO/2) is
  still not triggered.
- `divider-ratio-chain`'s ratio criterion holds at every point
  (`ratio_pass = 1`), so the "every integer N from 4 to 64, no holes" half of
  that claim also stands.
- `lock-window-proxy`'s sixteen window columns `twin_c0`…`twin_c15` — the
  normative measurand, `delaywin_3v3`'s own ERR → ERRD delay — are
  **bit-identical** to the predecessor at every one of its 117 points, and the
  `RULE (internal t_win)` row of `proxy_candidates.csv` is unchanged in every
  field (code error 0, 1.106–1.726 ns, 1.561× spread, `all in-band`). What
  moves on that bench is the *pad-referred* observables only.
- `lock-window-bisection`'s `tier_verdict` row for the one bundle whose
  threshold the ladder actually brackets (`typical`, code 7) is unchanged to
  every printed digit: code error **−12.62 trim codes** against a ±4.04-code
  ladder resolution, Tier A **FAIL**, Tier B **FAIL**. DR-029's negative
  result — DR-022 Decision 5 route 1 does not execute the trim rule — stands
  on the re-pinned PDK, by the same margin.

## The one real finding: two `lock-window-proxy` policy rows move

`sim/lock-window-proxy` asks DR-022's question — *can a tester pick the
normative trim code from a quantity `pll_top`'s pads actually expose?* — by
scoring four pad-referred candidates and a no-measurement control against the
rule itself. The scoring lives in `proxy_candidates.csv`, one row per policy,
each row a reduction over the whole 117-point grid. Two of those rows move
under the re-pin:

| policy | worst code error | grid spread | margin to hi | verdict |
|---|---|---|---|---|
| `RULE (internal t_win)` | 0 → 0 | 1.561× → 1.561× | +13.71 % → +13.71 % | `all in-band` → `all in-band` |
| `ring_a` | 8 → 8 | 2.434× → 2.434× | −9.551 % → −9.551 % | `OUT OF BAND somewhere` (both) |
| `ring_b` | 8 → 8 | 2.434× → 2.434× | −9.551 % → −9.551 % | `OUT OF BAND somewhere` (both) |
| **`clk_fb`** | **4 → 8** | **1.735× → 2.036×** | **+2.633 % → −9.551 %** | **`all in-band` → `OUT OF BAND somewhere`** |
| **`clk_do`** | **4 → 2** | 1.697× → 1.670× | +4.757 % → +10.17 % | `all in-band` → `all in-band` |
| `NONE (untrimmed, c8)` | 5 → 5 | 1.984× → 1.984× | −3.323 % → −3.323 % | `OUT OF BAND somewhere` (both) |

Why those two and not the rule: `t_win` is the delay of a cell built only from
`nfet_03v3`/`pfet_03v3` and it does not move, while every pad-referred
candidate is read through the VCO, the divider or the retiming flop. That is
the same transistor-level timing the `divider-ratio-cell` re-run found the PDK
moving, strongest at 125 °C — so a selector calibrated at one bundle and
applied at twelve others inherits all of it. `clk_fb`'s outlier is the
transmission-gate flop's clock-to-Q at `ff`, which the predecessor already
named as what sank that candidate; the re-pin makes it worse.

**Nothing ratified is relaxed, and the campaign's answer is unchanged.**
DR-022 Tier B needs a worst code error of exactly zero and the best candidate
now sits at 2; `clk_fb` losing its band hold makes the negative answer
stronger, not weaker. What *is* stale is two sub-claims the reader-facing
documents quote from the predecessor:

- that `CLK`→`FB` "holds the band" — it no longer does;
- that `CLK`→`DIVOUT`'s "worst code error of +4 is one code outside the +3
  bound DR-022 Tier A derives" — it is now +2, inside that bound.

Filed as **#951** under #827's third acceptance criterion rather than written
into `spec/`: this is a movement in measured evidence, not a decision, and the
decision it feeds (DR-022 Decision 5, closed negative by DR-029) does not
change. Re-pointing the quoted figures is #829's scope.

## Two records in this scope cannot be re-run at all

Neither is a budget or a capacity problem. For both, the testbench #827 asks
to re-run "with the same testbench, corner grid and settings" **no longer
exists in the tree**. Running today's deck against today's DUT would change
the device under test at the same time as the PDK, which is the one thing a
re-pin delta must not do.

### `lock-detector` `20260916-052313-b1633b5` — pre-DR-014 DUT and deck

That record's netlist provenance names `design/netlist/lock_detector.spice` at
SHA-256 `20cccda9…` and the stimulus
`sim/lock-detector/testbench/tb_lock_detector_harness.sp` at `c548b110…`.
Both are the versions at commit `dc5850be` (DR-010, #402), and both were
replaced by `bfde9893` (DR-014's window trim, #418), which turned
`delaywin_3v3` from a 4-port cell into an 8-port trimmable one and re-placed
the phase-error ladder:

```bash
git show dc5850be:sim/lock-detector/testbench/tb_lock_detector_harness.sp | sha256sum   # c548b110…
sha256sum sim/lock-detector/testbench/tb_lock_detector_harness.sp                        # f4eaf5d4…
```

The record itself says as much — its refinement ladders "are retired … a
ladder that no longer brackets an edge measures nothing", and "the committed
records that used them stand as taken". Its in-tree successor for the
*current* DUT is the trimmed grid `20260919-002812-1b12179`, which **is**
re-qualified above. What still rests on `c6d73a3` is a measurement of a cell
the design no longer contains.

### `lock-window-sizing` `20260915-202802-79c0cee` — the swept cell is gone

Same cause, harder failure. This record's `XCTL` control instance is "the
COMMITTED `delaywin_3v3` subcircuit, verbatim from
`design/netlist/lock_detector.spice`", and the deck instantiates it with four
terminals. Against the current 8-port cell it does not compose at all — a
single-corner local probe (allowed by the host rules, and no fleet budget)
fails before the first timestep:

```bash
python3 sim/run_corners.py lock-window-sizing --backend local \
  --corners typical --temps 27 --supply 3.3 --supply-tol 0 \
  --axis wc=w08 --no-write -j 1
```

```
Too few parameters for subcircuit type "delaywin_3v3" (instance: xxctl)
    Simulation interrupted due to error!
Error: incomplete or empty netlist
```

This is also the record whose *conclusion* was already consumed: it is the
sizing ladder DR-010 acted on, so the cell it swept was deliberately resized
out of existence by the decision it fed. Re-qualifying it would need the
historical netlist restored under a second DUT path — a change to the tree,
not a re-run.

Both are reported rather than silently dropped, because both are still cited.
Naming their successor, or retiring the citation, is the reader-facing half of
this and belongs to the final child, #829.

## What is still owed

One of the nine is re-runnable and did not land:

| campaign | record owed a successor | grid | why it did not land |
|---|---|---|---|
| `lock-window-trim` | `20260917-185928-8adff3d` | 1872 pts (13 bundles × 3 temps × 3 supplies × 16 trim codes) | compute: ~117 s of ngspice-47 per point (measured, see below) is ~61 CPU-hours, and the submitting host's own per-job AWS transport is the throughput limit. Peak observed completion rate was ~12.6 points/min, so the grid is a multi-hour fleet campaign rather than one step's work. |

It is reported here rather than worked around: the host rules forbid falling
back to a local grid, and `--supersedes` plus a partial grid is exactly the
"partial record standing in for a full re-take" the harness refuses. It is not
blocked on anything about the design.

`lock-window-proxy` took three submissions to land, which is worth recording
because the second failure is the one a reader would otherwise mistake for a
result. It was `batch_no_capacity`, with the mandated capacity-wait budget
already spent: *"launching `gf180-pll-sim-win_ss_27c_3.63v-…` was refused for
want of capacity (a concurrency slot or vCPU budget) on all 5 attempt(s)
within the 600s capacity-wait budget; the layer's fleet-wide limits are held by
other work, not by this run's `-j`. Last refusal: no capacity in any of the 30
pools after 3 attempt(s)."* The harness refused to mint a record from the 91 of
117 points that had completed, which is the correct behaviour under
`--supersedes`. Re-submitted with `--batch-wait-for-capacity 1800` it completed
all 117. Separately, `lock-window-bisection`'s first attempt lost one job to a
Spot reclamation notice and was re-run whole.

Useful prior for whoever picks `lock-window-trim` up: its nominal corner does
not move under either variable (next section), so the expected finding is a
null result — which is a reason to schedule the grid when the fleet is quiet,
not a reason to skip it. Submit it the way the other five were submitted:

```bash
python3 sim/run_corners.py lock-window-trim \
  --backend batch --batch-apply --artifact-store \
  --supersedes 20260917-185928-8adff3d \
  --supersedes-note "<the re-qualification note, as in the five records above>" \
  -j 24 --timeout 1800 --batch-wait-for-capacity 1800
```

**#827 stays open for it** rather than being re-filed: the PR that added this
document says `Part of #827`, so the issue carries the remainder, and nothing
about the remainder is a new question. The two records in the section above
are owed nothing — they are refusals, not gaps.

## Attribution: PDK or simulator?

The fleet re-baked ngspice along with the PDK, so every new record here
differs from its predecessor in *two* variables at once
(`c6d73a3` → `f6eeac7` **and** ngspice-46 → ngspice-47) plus host OS and
execution backend. `REPIN-DELTAS-f6eeac7-devchar.md` separated them with a
single-corner local control run, and the same method applies here — this host
carries ngspice-46, the exact version every predecessor in this group ran:

```bash
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py <slug> --backend local \
  --corners typical --temps 27 --supply 3.3 --supply-tol 0 --no-write -j 1
```

Two control probes were taken, and they answer the question in opposite
directions:

| bench | control point | result |
|---|---|---|
| `lock-window-trim` | ngspice-46 under `f6eeac7`, `typical_27c_3.30v_c7` | `twin_r` 1.357890e-09 s, `twin_f` 1.340040e-09 s — **identical to the predecessor's own row to the last printed digit**. The same point under ngspice-47 returns the same two numbers, so on this bench *neither* variable moves the measurement at the nominal corner. |
| `divider-ratio-cell` | ngspice-46 under `f6eeac7`, `fs_125c_3.30v_f010` | reproduces the **new** values exactly on all eight columns checked, so holding ngspice at 46 does **not** restore the old numbers: here the mover is the PDK. Taken at 125 °C deliberately — 27 °C is the one temperature at which that bench shows no change at all, so a nominal-only probe is structurally blind to the effect. |

These are one-corner results and are stated as such: they establish the
attribution at the probed corner, not at every corner. They are evidence, not
a substitute for the grids.

### A simulator-performance note, not a result

On `lock-window-trim`'s single-point probe, ngspice-46 finished in **2.7 s**
and ngspice-47 in **116.8 s** on the same host, same deck, same PDK — a ~43×
slowdown for bit-identical output. That changes no number in this document,
but it is the reason the 1872-point trim grid is a fleet campaign rather than
an afternoon, and it is worth knowing before the remaining re-runs are
scheduled. Not filed as a tool issue here: it is an upstream simulator
property, and `sim/harness/README.md` already carries the ngspice-46/47 note
that #153 and #932 hang off.

## Why some raw edge-time columns move by hundreds of percent

`divider-ratio-cell` and `divider-ratio-chain` both show large *relative*
movements in raw edge-time columns while every graded verdict holds. Every one
of those figures is an exact multiple of one input or output period (100 ns at
`f010`, 5 ns at `f200`; one output period for the chain's `fbpw`). That is the
signature of a `.measure … when … rise=N` whose target edge sits near the
trigger window latching a *neighbouring* edge once the underlying delay shifts
at all — an index change, not a physical one. On the cell bench the shift that
causes it is 74 ps on `tcq` at `fs`/125 °C/3.30 V/`f010`. The columns the
records actually report move accordingly: `fbpw_s` by 0.4 fs (0.001 %) on the
chain, and the moduli `na`…`nf` stay within 0.0008 of an exact 2 or 3 against
limits of ±0.05.

## The bisection predecessor ran a derive module that never landed

`lock-window-bisection`'s predecessor was **taken against a dirty working
tree** (its own Environment provenance says so), and the derive module it ran
is not the one in the tree. Three differences follow, and none of them is a
PDK or simulator effect:

- The committed `testbench/derive.py` gates the threshold logic on
  `_baseline_asserted`. Its comment says the gate was "added after this
  campaign's first record", where `ff` and `ss` were labelled `upper_bound` —
  "not a small mislabel … a number where there should be a refusal". The
  re-run therefore reports those two bundles as `no_baseline_assert` / `n/a`
  instead of as an upper bound of −9.8 / −9.9 codes.
- `skew_pw` is now `_unwrap`ped. From `tup_*`/`tdn_*` raw measures that agree
  with the predecessor to 1e-11 s, the `ff` bundle's `skew_pw` reads −1.80 ns
  instead of 78.22 ns — one unwrapped reference period.
- The old `phi_drift` column is split into `phi_ss` (the steady-state skew)
  plus a true drift, so the comparator also reports a `phi_ss` column present
  in the new record only.

The raw measurements themselves reproduce: `vwin_pre`, `vwin_min`, `phi_pre`,
`phi_early`, `fout`, `nmeas`, `delta_s`/`delta_meas` and the four PFD pulse
edges all agree with the predecessor to 1e-11 or better, and `delta_err` stays
at 1e-24 s against its ±2 ps bound. And the conclusive row — `typical`,
code 7 — is unchanged, which is what makes the re-qualification meaningful
despite the derive difference.

## Per-bench tables

`limit` is the bound the record itself states for that measurement (`—` where
it states none). `max rel delta %` is relative to the superseded record's
value; a measurement whose old value is zero contributes to the absolute
column only.

## `lock-detector`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/lock-detector/records/20260919-002812-1b12179.md \
  sim/lock-detector/records/20261114-091604-ffbc0e2.md
```

### `20261114-091604-ffbc0e2` vs `20260919-002812-1b12179`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `iavg` | — | -0.000222346..-0.000114615 | -0.000222346..-0.000114615 | 0 | 0 | `—` |
| `` | `la_lvl` | — | -1.409060e-09..3.63 | -1.409060e-09..3.63 | 0 | 0 | `—` |
| `` | `lb_lvl` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `lc_lvl` | — | -5.128980e-10..5.546650e-07 | -5.128980e-10..5.546650e-07 | 0 | 0 | `—` |
| `` | `ld_lvl` | — | 2.335340e-09..5.558840e-07 | 2.335340e-09..5.558840e-07 | 2.000000e-13 | 0.001821 | `ss_125c_2.97v_e10.0n_c3` |
| `` | `le_lvl` | — | -2.221940e-09..5.597520e-07 | -2.221940e-09..5.597520e-07 | 1.000000e-16 | 0.0001067 | `all-fast_-40c_2.97v_e4.0n_c11` |
| `` | `le_pre` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `lock_pass` | — | 1..1 | 1..1 | 0 | 0 | `—` |
| `` | `ta_asrt` | — | 6.795760e-07..1.916250e-06 | 6.795760e-07..1.916250e-06 | 0 | 0 | `—` |
| `` | `tb_asrt` | — | 6.795760e-07..1.912540e-06 | 6.795760e-07..1.912540e-06 | 0 | 0 | `—` |
| `` | `te_asrt` | — | 6.795760e-07..1.912540e-06 | 6.795760e-07..1.912540e-06 | 0 | 0 | `—` |
| `` | `te_deas` | — | 2.404070e-06..2.405630e-06 | 2.404070e-06..2.405630e-06 | 0 | 0 | `—` |
| `` | `twin_f` | — | 1.084880e-09..1.721060e-09 | 1.084880e-09..1.721060e-09 | 0 | 0 | `—` |
| `` | `twin_r` | — | 1.108440e-09..1.739880e-09 | 1.108440e-09..1.739880e-09 | 0 | 0 | `—` |
| `` | `va_lvl` | — | 0.00714814..3.61732 | 0.00714814..3.61732 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 205 graded rows.

**Stated limits**: identical in both records.

## `lock-window-bisection`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/lock-window-bisection/records/20260925-162032-e341b58.md \
  sim/lock-window-bisection/records/20261114-191343-8cb0847.md
```

### `20261114-191343-8cb0847` vs `20260925-162032-e341b58`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `ground_truth` | `phi_drift` | — | -1.727400e-10..1.916000e-10 | -1.681500e-10..1.944000e-10 | 7.615500e-12 | 439.1 | `typical_27c_3.30v_c7v2p168_dp2400` |
| `ground_truth` | `phi_early` | — | 9.389750e-11..7.807930e-08 | 9.865230e-11..7.806510e-08 | 4.754800e-12 | 5.064 | `typical_27c_3.30v_c7v2p168_dp2400` |
| `ground_truth` | `phi_pre` | — | 9.216320e-11..7.825750e-08 | 8.930250e-11..7.825500e-08 | 1.215000e-11 | 11.57 | `typical_27c_3.30v_c7v2p168_dp2000` |
| `ground_truth` | `skew_pw` | — | 7.000000e-11..7.822000e-08 | -1.800000e-09..1.620000e-09 | 7.999000e-08 | 102.3 | `ff_27c_3.30v_c11v2p295_dp2000` |
| `ground_truth` | `vwin_drop` | — | -0.167956..3.28427 | -0.168042..3.28403 | 0.02142 | 4.85 | `ss_27c_3.30v_c3v1p988_d0000` |
| `ground_truth` | `vwin_min` | — | -0.0207843..3.28796 | -0.0207805..3.28795 | 0.021576 | 28.46 | `typical_27c_3.30v_c7v2p168_dm2800` |
| `ground_truth` | `vwin_pre` | — | 0.211316..3.28655 | 0.21182..3.28658 | 0.013037 | 4.412 | `ss_27c_3.30v_c3v1p988_dp2000` |
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.074559..0.141998 | 0.0744215..0.142198 | 0.0001611 | 0.216 | `typical_27c_3.30v_c7v2p168_dp2000` |
| `lock` | `ferr_fb` | min=-0.002, max=0.002 | -0.000226007..0.00021369 | -0.000225209..0.000198672 | 1.753806e-05 | 4226 | `typical_27c_3.30v_c7v2p168_dp2400` |
| `lock` | `ffb` | — | 1.249720e+07..1.250270e+07 | 1.249720e+07..1.250250e+07 | 1100 | 0.008801 | `ff_27c_3.30v_c11v2p295_d0000` |
| `lock` | `fout` | min=9.900000e+07, max=1.010000e+08 | 9.995150e+07..1.000280e+08 | 9.996400e+07..1.000280e+08 | 16900 | 0.0169 | `typical_27c_3.30v_c7v2p168_dm2000` |
| `lock` | `nmeas` | min=7.99, max=8.01 | 7.99708..8.00064 | 7.99881..8.00107 | 0.00173 | 0.02163 | `ff_27c_3.30v_c11v2p295_d0000` |
| `lock` | `vctrl_pre` | — | 1.98917..2.29455 | 1.98919..2.29457 | 0.00012 | 0.00523 | `ff_27c_3.30v_c11v2p295_d0000` |
| `procedure` | `deassert_lat_ns` | — | 80.26..1439.38 | 80.26..1440.07 | 0.69 | 0.04794 | `ff_27c_3.30v_c11v2p295_dm2000` |
| `procedure` | `deasserted` | — | 0..1 | 0..1 | 0 | 0 | `—` |
| `procedure` | `delta_err` | min=-2.000000e-12, max=2.000000e-12 | -8.271806e-24..4.549493e-24 | -8.271806e-24..4.549493e-24 | 0 | 0 | `—` |
| `procedure` | `delta_meas` | — | -2.800000e-09..2.800000e-09 | -2.800000e-09..2.800000e-09 | 0 | 0 | `—` |
| `procedure` | `delta_s` | — | -2.800000e-09..2.800000e-09 | -2.800000e-09..2.800000e-09 | 0 | 0 | `—` |
| `procedure` | `dip_ns` | — | 1042.86..1372.08 | 1031.95..1372.03 | 10.91 | 1.046 | `typical_27c_3.30v_c7v2p168_dp2400` |
| `procedure` | `lock_min` | — | -0.117577..3.3 | -0.0938125..3.3 | 0.0696322 | 99.31 | `ff_27c_3.30v_c11v2p295_dm2000` |
| `procedure` | `lock_post` | — | -6.334300e-07..3.3 | -8.880290e-08..3.3 | 0.02069 | 85.98 | `ss_27c_3.30v_c3v1p988_d0000` |
| `procedure` | `lock_pre` | min=3.2 | 5.657780e-09..3.3 | 5.726980e-09..3.3 | 3.355900e-10 | 5.931 | `ff_27c_3.30v_c11v2p295_d0000` |
| `procedure` | `t_deassert` | — | 6.040260e-06..7.399380e-06 | 6.040260e-06..7.400070e-06 | 6.900000e-10 | 0.009325 | `ff_27c_3.30v_c11v2p295_dm2000` |
| `procedure` | `t_reassert` | — | 6.832430e-06..7.412340e-06 | 6.832550e-06..7.412290e-06 | 1.089000e-08 | 0.152 | `typical_27c_3.30v_c7v2p168_dp2400` |
| `ungrouped` | `tclk20` | — | 1.999430e-07..2.000970e-07 | 1.999450e-07..2.000720e-07 | 3.500000e-11 | 0.0175 | `typical_27c_3.30v_c7v2p168_dm2000` |
| `ungrouped` | `tdn_f` | — | 5.801960e-06..5.804300e-06 | 5.801960e-06..5.804310e-06 | 2.000000e-11 | 0.0003446 | `ss_27c_3.30v_c3v1p988_d0000` |
| `ungrouped` | `tdn_r` | — | 5.800550e-06..5.878660e-06 | 5.800540e-06..5.878660e-06 | 2.000000e-11 | 0.0003447 | `ss_27c_3.30v_c3v1p988_dp2000` |
| `ungrouped` | `tfb5` | — | 3.999150e-07..4.000900e-07 | 3.999210e-07..4.000900e-07 | 3.700000e-11 | 0.009249 | `ff_27c_3.30v_c11v2p295_d0000` |
| `ungrouped` | `tref_span` | — | 7.720000e-08..8.280000e-08 | 7.720000e-08..8.280000e-08 | 0 | 0 | `—` |
| `ungrouped` | `tup_f` | — | 5.801980e-06..5.804320e-06 | 5.801980e-06..5.804330e-06 | 2.000000e-11 | 0.0003446 | `ss_27c_3.30v_c3v1p988_d0000` |
| `ungrouped` | `tup_r` | — | 5.800450e-06..5.800560e-06 | 5.800450e-06..5.800560e-06 | 1.000000e-11 | 0.0001724 | `typical_27c_3.30v_c7v2p168_dp2000` |

**Per-corner verdict flips** (each one is a finding):

| topology | corner-id | old | new |
|---|---|---|---|
| `procedure` | `ff_27c_3.30v_c11v2p295_d0000` | FAIL — lock_pre min=3.2 (got 5.657780e-09) | FAIL — lock_pre min=3.2 (got 5.993370e-09) |
| `procedure` | `ff_27c_3.30v_c11v2p295_dm2000` | FAIL — lock_pre min=3.2 (got 5.772880e-09) | FAIL — lock_pre min=3.2 (got 5.726980e-09) |
| `procedure` | `ff_27c_3.30v_c11v2p295_dp2000` | FAIL — lock_pre min=3.2 (got 6.330650e-09) | FAIL — lock_pre min=3.2 (got 6.509200e-09) |
| `procedure` | `ss_27c_3.30v_c3v1p988_d0000` | FAIL — lock_pre min=3.2 (got 5.820880e-09) | FAIL — lock_pre min=3.2 (got 5.807940e-09) |
| `procedure` | `ss_27c_3.30v_c3v1p988_dm2000` | FAIL — lock_pre min=3.2 (got 5.816810e-09) | FAIL — lock_pre min=3.2 (got 5.813660e-09) |
| `procedure` | `ss_27c_3.30v_c3v1p988_dp2000` | FAIL — lock_pre min=3.2 (got 5.792930e-09) | FAIL — lock_pre min=3.2 (got 5.772080e-09) |

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261114-191343-8cb0847` only: `ground_truth`/`phi_ss`

_6 finding(s) above need a human disposition._

## `divider-ratio-dff`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/divider-ratio-dff/records/20260801-125114-3f883e3.md \
  sim/divider-ratio-dff/records/20261114-080736-f53d562.md
```

### `20261114-080736-f53d562` vs `20260801-125114-3f883e3`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `cqa0` | — | 1.651720e-10..3.709520e-10 | 1.651720e-10..3.709520e-10 | 0 | 0 | `—` |
| `` | `cqa1` | — | 1.651730e-10..3.727260e-10 | 1.651730e-10..3.727260e-10 | 0 | 0 | `—` |
| `` | `cqa2` | — | 1.656860e-10..3.733210e-10 | 1.656860e-10..3.733210e-10 | 0 | 0 | `—` |
| `` | `cqa3` | — | 1.662080e-10..3.800580e-10 | 1.662080e-10..3.800580e-10 | 0 | 0 | `—` |
| `` | `cqa4` | — | 1.684090e-10..3.922460e-10 | 1.684090e-10..3.922460e-10 | 0 | 0 | `—` |
| `` | `cqa5` | — | 1.816850e-10..4.138560e-10 | 1.816850e-10..4.138560e-10 | 0 | 0 | `—` |
| `` | `cqa6` | — | 3.726950e-10..6.082310e-10 | 3.726950e-10..6.082310e-10 | 0 | 0 | `—` |
| `` | `cqb0` | — | 1.444680e-10..3.189530e-10 | 1.444680e-10..3.189530e-10 | 0 | 0 | `—` |
| `` | `cqb1` | — | 1.444600e-10..3.178710e-10 | 1.444600e-10..3.178710e-10 | 0 | 0 | `—` |
| `` | `cqb2` | — | 1.438910e-10..3.264260e-10 | 1.438910e-10..3.264260e-10 | 0 | 0 | `—` |
| `` | `cqb3` | — | 1.446560e-10..3.427390e-10 | 1.446560e-10..3.427390e-10 | 0 | 0 | `—` |
| `` | `cqb4` | — | 1.506570e-10..4.328510e-10 | 1.506570e-10..4.328510e-10 | 0 | 0 | `—` |
| `` | `cqb5` | — | 2.945450e-10..2.945450e-10 | 2.945450e-10..2.945450e-10 | 0 | 0 | `—` |
| `` | `hqc0` | — | 4.000540e-09..5.564370e-07 | 4.000540e-09..5.564370e-07 | 1.950000e-12 | 0.04262 | `fs_-40c_3.30v` |
| `` | `hqc1` | — | 3.823770e-09..5.564370e-07 | 3.823770e-09..5.564370e-07 | 1.000000e-14 | 0.000195 | `typical_-40c_3.63v` |
| `` | `hqc2` | — | 3.823770e-09..5.564370e-07 | 3.823770e-09..5.564370e-07 | 0 | 0 | `—` |
| `` | `hqc3` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc4` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc5` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc6` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc7` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc8` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `hqc9` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `` | `tcq_f_s` | — | 1.444680e-10..3.189530e-10 | 1.444680e-10..3.189530e-10 | 0 | 0 | `—` |
| `` | `tcq_r_s` | — | 1.651720e-10..3.709520e-10 | 1.651720e-10..3.709520e-10 | 0 | 0 | `—` |
| `` | `thold_s` | — | 1.000000e-10..1.000000e-10 | 1.000000e-10..1.000000e-10 | 0 | 0 | `—` |
| `` | `tsetup_s` | — | 2.000000e-11..5.000000e-11 | 2.000000e-11..5.000000e-11 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 45 graded rows.

**Stated limits**: identical in both records.

## `divider-ratio-cell`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/divider-ratio-cell/records/20260801-140529-3f883e3.md \
  sim/divider-ratio-cell/records/20261114-083606-f53d562.md
```

### `20261114-083606-f53d562` vs `20260801-140529-3f883e3`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `fa3` | — | 2.530130e-08..6.017570e-07 | 2.530130e-08..6.017490e-07 | 1.000430e-07 | 19.94 | `ff_125c_3.63v_f010` |
| `` | `fb3` | — | 3.530090e-08..9.017620e-07 | 3.530090e-08..9.015330e-07 | 2.000650e-07 | 28.51 | `fs_125c_3.30v_f010` |
| `` | `fmb2` | — | 2.023840e-08..6.015570e-07 | 2.023840e-08..6.015580e-07 | 1.999870e-07 | 49.8 | `sf_125c_2.97v_f010` |
| `` | `i_cell_a` | — | 6.770550e-06..0.000153406 | 6.770550e-06..0.000153406 | 1.788000e-07 | 1.406 | `fs_125c_3.63v_f010` |
| `` | `iavg` | — | -0.000920439..-4.062330e-05 | -0.000920439..-4.062330e-05 | 1.072500e-06 | 1.405 | `fs_125c_3.63v_f010` |
| `` | `na` | min=1.95, max=2.05 | 1.99966..2.00022 | 1.99966..2.0003 | 0.00062 | 0.031 | `sf_125c_3.63v_f010` |
| `` | `nb` | min=2.95, max=3.05 | 2.99946..3.00032 | 2.99946..3.00032 | 0.00047 | 0.01567 | `ss_125c_3.30v_f010` |
| `` | `nc` | min=1.95, max=2.05 | 1.99966..2.00032 | 1.99966..2.00019 | 0.00062 | 0.031 | `sf_125c_3.63v_f010` |
| `` | `nd` | min=2.95, max=3.05 | 2.99946..3.00033 | 2.99946..3.00043 | 0.00074 | 0.02466 | `ss_125c_3.63v_f010` |
| `` | `ne` | min=2.95, max=3.05 | 2.99804..3.00009 | 2.99804..3.00009 | 1.000000e-05 | 0.0003333 | `fs_125c_3.30v_f010` |
| `` | `nf` | min=2.95, max=3.05 | 2.99747..3.00221 | 2.99747..3.00221 | 0.00395 | 0.1318 | `ff_125c_2.97v_f010` |
| `` | `pw_div2_s` | — | 4.941980e-09..1.000412e-07 | 4.941980e-09..1.000412e-07 | 8.800000e-11 | 0.08797 | `sf_125c_3.63v_f010` |
| `` | `pw_div3_s` | — | 4.941800e-09..1.000340e-07 | 4.941800e-09..1.000390e-07 | 1.110000e-10 | 0.1111 | `sf_125c_3.30v_f010` |
| `` | `pw_modout_s` | — | -2.000710e-07..9.998970e-08 | -2.000720e-07..9.998970e-08 | 2.999991e-07 | 303.4 | `fs_125c_2.97v_f200` |
| `` | `pwa` | — | -1.001080e-07..1.000340e-07 | -1.001120e-07..1.000150e-07 | 2.000490e-07 | 202.3 | `ss_125c_2.97v_f200` |
| `` | `pwb` | — | -2.000790e-07..1.000340e-07 | -2.000790e-07..1.000390e-07 | 2.999996e-07 | 303.2 | `ss_125c_3.30v_f200` |
| `` | `rmb2` | — | 2.023520e-08..7.015490e-07 | 2.023520e-08..7.015560e-07 | 2.999960e-07 | 73.79 | `ff_125c_2.97v_f200` |
| `` | `ta1` | — | 5.374990e-09..2.017910e-07 | 5.374990e-09..2.017440e-07 | 1.000740e-07 | 98.57 | `fs_125c_3.30v_f010` |
| `` | `ta3` | — | 2.537500e-08..6.017740e-07 | 2.537500e-08..6.017540e-07 | 1.000850e-07 | 19.94 | `fs_125c_3.30v_f010` |
| `` | `tb1` | — | 5.375100e-09..3.017550e-07 | 5.375100e-09..3.017560e-07 | 2.000080e-07 | 196.9 | `typical_125c_3.63v_f010` |
| `` | `tb3` | — | 3.537510e-08..9.017600e-07 | 3.537510e-08..9.017590e-07 | 2.000000e-07 | 28.51 | `typical_125c_3.63v_f010` |
| `` | `tc1` | — | 5.374990e-09..2.017910e-07 | 5.374990e-09..2.017880e-07 | 1.000740e-07 | 98.57 | `fs_125c_3.30v_f010` |
| `` | `tc3` | — | 2.537500e-08..6.017770e-07 | 2.537500e-08..6.017770e-07 | 1.000450e-07 | 19.94 | `fs_125c_3.30v_f010` |
| `` | `tcq` | — | 2.761000e-10..7.914590e-10 | 2.761000e-10..7.839840e-10 | 7.844200e-11 | 14 | `fs_125c_3.30v_f010` |
| `` | `td1` | — | 5.375100e-09..3.018330e-07 | 5.375100e-09..3.018610e-07 | 2.000400e-07 | 197 | `fs_125c_3.30v_f010` |
| `` | `td3` | — | 3.537510e-08..9.017770e-07 | 3.537510e-08..9.017770e-07 | 2.000270e-07 | 28.51 | `fs_125c_2.97v_f010` |
| `` | `te1` | — | 5.353470e-09..2.346930e-07 | 5.353470e-09..2.345120e-07 | 1.334590e-07 | 132.1 | `typical_125c_3.30v_f010` |
| `` | `te3` | — | 2.535370e-08..6.346930e-07 | 2.535370e-08..6.345120e-07 | 1.334590e-07 | 26.64 | `typical_125c_3.30v_f010` |
| `` | `tf1` | — | 5.342090e-09..2.011550e-07 | 5.342090e-09..2.011680e-07 | 1.001010e-07 | 99.08 | `fs_125c_2.97v_f010` |
| `` | `tf3` | — | 2.034210e-08..5.010760e-07 | 2.034210e-08..5.011600e-07 | 9.992300e-08 | 24.91 | `fs_125c_2.97v_f010` |

**Per-corner verdicts**: unchanged on all 90 graded rows.

**Stated limits**: identical in both records.

## `divider-ratio-chain`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/divider-ratio-chain/records/20260802-100727-082c879.md \
  sim/divider-ratio-chain/records/20261114-093804-ad9eef8.md
```

### `20261114-093804-ad9eef8` vs `20260802-100727-082c879`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `fbpw` | — | -3.200060e-06..3.199970e-06 | -3.200060e-06..3.199970e-06 | 6.400000e-06 | 337.7 | `ss_125c_2.97v_f200n54` |
| `` | `fbpw_s` | — | 9.924830e-09..3.199970e-06 | 9.924800e-09..3.199970e-06 | 4.000000e-13 | 0.001001 | `ss_125c_2.97v_f200n31` |
| `` | `ffb2` | — | 4.522530e-08..1.860130e-05 | 4.522530e-08..1.860130e-05 | 3.000000e-06 | 45.55 | `fs_125c_3.63v_f200n33` |
| `` | `iavg` | — | -0.00035693..-1.071890e-05 | -0.00035588..-1.062910e-05 | 1.259000e-05 | 3.793 | `ff_27c_3.63v_f200n04` |
| `` | `n_fb` | — | 4..64 | 4..64 | 0 | 0 | `—` |
| `` | `n_target` | — | 4..64 | 4..64 | 0 | 0 | `—` |
| `` | `ndo` | — | 3.99986..64 | 3.99986..64 | 0 | 0 | `—` |
| `` | `ratio_pass` | min=1 | 1..1 | 1..1 | 0 | 0 | `—` |
| `` | `t_arr` | — | 9.551840e-10..9.998630e-08 | 9.551840e-10..9.998630e-08 | 9.000000e-14 | 0.005139 | `ff_-40c_3.63v_f200n28` |
| `` | `t_rtcq` | — | 1.684520e-10..9.998850e-08 | 1.684520e-10..9.998850e-08 | 1.700000e-14 | 0.006288 | `typical_27c_2.97v_f200n33` |
| `` | `tdo1` | — | 2.614020e-08..1.260490e-05 | 2.614020e-08..1.280490e-05 | 5.899980e-06 | 86.42 | `ss_125c_2.97v_f200n18` |
| `` | `tdo2` | — | 4.614020e-08..1.900490e-05 | 4.614020e-08..1.920490e-05 | 5.900000e-06 | 45.13 | `ss_125c_2.97v_f200n18` |
| `` | `tfb1` | — | 2.525110e-08..1.270150e-05 | 2.526070e-08..1.230140e-05 | 5.900030e-06 | 88.19 | `ss_125c_2.97v_f200n42` |
| `` | `tfb2` | — | 4.525110e-08..1.910150e-05 | 4.526070e-08..1.870140e-05 | 5.900000e-06 | 44.66 | `ss_125c_2.97v_f200n42` |

**Per-corner verdicts**: unchanged on all 235 graded rows.

**Stated limits**: identical in both records.

## `lock-window-proxy`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/lock-window-proxy/records/20260925-050022-6d57802.md \
  sim/lock-window-proxy/records/20261114-194051-c8750de.md
```

### `20261114-194051-c8750de` vs `20260925-050022-6d57802`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `proxy` | `t8p_a` | — | 8.535800e-08..2.439510e-07 | 8.536390e-08..2.440070e-07 | 1.220000e-10 | 0.1032 | `all-fast_-40c_2.97v` |
| `proxy` | `t8p_b` | — | 1.295460e-08..3.407740e-08 | 1.295840e-08..3.408860e-08 | 7.977000e-10 | 4.401 | `mimcap_ff_125c_2.97v` |
| `proxy` | `tcq_raw` | — | -1.623490e-08..6.802890e-08 | -1.623760e-08..6.806340e-08 | 5.994098e-08 | 8804 | `all-fast_125c_2.97v` |
| `proxy` | `tdo_raw` | — | -2.029630e-08..9.245580e-08 | -2.025770e-08..9.250970e-08 | 4.009912e-08 | 1895 | `mimcap_ff_125c_2.97v` |
| `window` | `twin_c0` | — | 7.670700e-10..1.519420e-09 | 7.670700e-10..1.519420e-09 | 0 | 0 | `—` |
| `window` | `twin_c1` | — | 8.034540e-10..1.589160e-09 | 8.034540e-10..1.589160e-09 | 0 | 0 | `—` |
| `window` | `twin_c10` | — | 1.113600e-09..2.210050e-09 | 1.113600e-09..2.210050e-09 | 0 | 0 | `—` |
| `window` | `twin_c11` | — | 1.151660e-09..2.284480e-09 | 1.151660e-09..2.284480e-09 | 0 | 0 | `—` |
| `window` | `twin_c12` | — | 1.183210e-09..2.350960e-09 | 1.183210e-09..2.350960e-09 | 0 | 0 | `—` |
| `window` | `twin_c13` | — | 1.221410e-09..2.425800e-09 | 1.221410e-09..2.425800e-09 | 0 | 0 | `—` |
| `window` | `twin_c14` | — | 1.256100e-09..2.496500e-09 | 1.256100e-09..2.496500e-09 | 0 | 0 | `—` |
| `window` | `twin_c15` | — | 1.294400e-09..2.571660e-09 | 1.294400e-09..2.571660e-09 | 0 | 0 | `—` |
| `window` | `twin_c2` | — | 8.361860e-10..1.654590e-09 | 8.361860e-10..1.654590e-09 | 0 | 0 | `—` |
| `window` | `twin_c3` | — | 8.731520e-10..1.725890e-09 | 8.731520e-10..1.725890e-09 | 0 | 0 | `—` |
| `window` | `twin_c4` | — | 9.034340e-10..1.789010e-09 | 9.034340e-10..1.789010e-09 | 0 | 0 | `—` |
| `window` | `twin_c5` | — | 9.408200e-10..1.861460e-09 | 9.408200e-10..1.861460e-09 | 0 | 0 | `—` |
| `window` | `twin_c6` | — | 9.745840e-10..1.929570e-09 | 9.745840e-10..1.929570e-09 | 0 | 0 | `—` |
| `window` | `twin_c7` | — | 1.012260e-09..2.002880e-09 | 1.012260e-09..2.002880e-09 | 0 | 0 | `—` |
| `window` | `twin_c8` | — | 1.041380e-09..2.066460e-09 | 1.041380e-09..2.066460e-09 | 0 | 0 | `—` |
| `window` | `twin_c9` | — | 1.079270e-09..2.140380e-09 | 1.079270e-09..2.140380e-09 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 234 graded rows.

**Stated limits**: identical in both records.

The four `proxy` rows are the pad-referred observables and the sixteen
`window` rows are the normative measurand; the policy scoring those four
produce is in § "The one real finding" above, because it is a reduction over
the grid and not a per-corner row this table can reach.

