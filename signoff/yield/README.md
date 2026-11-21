# T1 item 6 yield evidence

The `klt yield` sample-set documents and envelopes this block's T1 item 6
cites, derived from the committed Monte Carlo records of the two campaigns
with per-draw CSVs — no simulation is re-run here (`sim/` is append-only;
see `signoff/README.md`, "Item 6", for which statistical rows exist and why
the period-jitter random bound is a declared gap instead of an envelope).

## The chain

```
sim/<campaign>/corners/<record>/*.csv      committed per-draw records
  └─ signoff/yield/derive.py               thin, tested step (see below)
       └─ signoff/yield/csv/*.csv          header-first long-format CSVs
       └─ signoff/yield/limits/*.json      per-measurement spec limits
            └─ klt yield-csv --format json
                 └─ signoff/yield/samples/*.json     sample-set documents
                      └─ klt yield --limits ... --format json
                           └─ signoff/yield/reports/*.json   envelopes
                                └─ signoff/block-manifest.json  citations
```

Every artifact from `csv/` down is committed, and every step is either klt
itself or `derive.py`. `signoff/tests/test_yield_evidence.py` re-derives the
CSVs and limits byte-for-byte, re-hashes the chain, and cross-checks the
derived term-1 statistic against `design/README.md`'s own committed figure.
Regenerate everything on the pinned klt (see `signoff/run-signoff.sh`'s
version-check message for how to get one):

```bash
KLT=/path/to/pinned/klt bash signoff/yield/run.sh
```

## What derive.py does — and why it is this thin

Two things the committed records have that `klt yield-csv` (0.9.2) cannot
consume directly; both are filed upstream rather than worked around beyond
the minimum:

1. **Every record CSV opens with `#` metadata lines** (campaign, record id,
   PDK hash, simulator, switch settings) and `klt yield-csv` takes the
   file's first line as its header — **klayout-tools#7019**. `derive.py`
   strips the preamble into the committed `csv/` files so the sample-set
   documents' `derivation.csv.path`/`content_hash` audit trail stays
   repo-relative.
2. **Budget term 1's per-draw value is the signed worst-magnitude mismatch
   across the three Vctrl points of one draw** — the verdict statistic
   `sim/mc-cp-mismatch/testbench/run.sh` computes (`DC term1 SIGNED
   worst-of-3`) and `design/README.md`'s budget table checks. The committed
   `mc_cp_dc.csv` carries one row per (corner, seed, Vctrl point);
   `derive.py` selects the worst-of-window sample per draw, keeping its
   sign. The other terms' value columns (`wskew_s`, `qnet0_c`,
   `t_offset_s`, `ratio`) pass through verbatim.

Grouping (one measurement per corner, or per grid point for the VCO joint
draw), the `measurements[]` shape and failed-draw handling all stay in klt.
**No local CSV-to-sample-set converter exists here** — that is the point of
`klt yield-csv` (klayout-tools#2931), and any capability it lacks is an
upstream issue, not a repo script.

## Row ids, limits, and the statistics stated

The manifest's declared row set (`spec_rows."6.analog"`) and each citation's
`rows` use short ids; the limits files tag every measurement with its row id
(`spec_row`), so the grader's derived-coverage check can match them:

| row id | source | value column | limits | per measurement |
|---|---|---|---|---|
| `cp-budget/1` | `mc_cp_dc.csv` → worst-of-window | `mism_worst_pct` | ±20 % (DR-018/DR-034) | 21 corners × n=100 |
| `cp-budget/2a` (and `2`, a fortiori) | `mc_cp_switch.csv` | `wskew_s` | ±2 ns mid-window (term 2's ±3 ns window bound is looser) | 21 corners × n=16 |
| `cp-budget/3` | `mc_pfd_cp.csv` | `qnet0_c` | ±20 fC | 21 corners × n=16 |
| `cp-budget/4` | `mc_pfd_cp.csv` | `t_offset_s` | ±3 ns | 21 corners × n=16 |
| `vco-band-coverage/adjacent-pair-ratio` | `mismatch.csv` (record `20260927-220631-546a397`, 11-point joint-draw grid) | `ratio` | ≥ 1.0 one-sided | 11 points × n=200 |

Every measurement also declares `target_sigma: 3`, which is the budget
rows' own statistic: `|mean| + 3σ ≤ limit` is exactly
`capability.sigma_to_spec ≥ 3` (one-sided for the coverage floor — the
record itself states the check as a one-sided 3σ tail). **No `target_yield`
is declared anywhere** — the spec states none, and a campaign declaring
none can never fail on one (klayout-tools#5490's honest `reported` status);
the pass/fail the envelopes do carry comes from the 3σ bounds the rows
themselves state. `target_ci_halfwidth` and `min_samples` stay at klt
yield's documented defaults; the sample-size verdicts those defaults
produce (n ≥ 183 at zero failures) are recorded results, not inputs to
tune — #1092 owns the draw-count raise.

## Sources current at derivation

`mc-cp-mismatch` record `20260927-102154-d004d5b` (the 21-corner axis, PDK
hash `c6d73a35…`) and `vco-tuning-range` record `20260927-220631-546a397`
(11-point joint-draw grid). The checklist's recorded-seed sub-criterion is
met by the records themselves: every per-draw row carries its
`.option rndseed` value in the `seed` column, which survives into the
derived CSVs (and is enforced unique per measurement by `klt yield-csv
--draw-col seed`); the records' own header comments and record docs state
the seed range and the execution host. PR #1074 re-qualifies the charge-pump records
under open_pdks `f6eeac7`; it was **open** when this evidence was derived,
so the `c6d73a35`-era records are used. When a successor record supersedes
either source, re-point the constants in `derive.py`, re-run
`bash signoff/yield/run.sh`, re-pin the manifest hashes and re-render
`signoff/tier-report.json` (`bash signoff/run-signoff.sh`) — the committed
chain is what makes that a reviewable diff.

## The digital partition

`digital/spec-rows.json` is the JSON projection of `spec/pll.md`'s ratified
row ids that `klt signoff`'s `not_applicable` form cites (generated by
`derive.py` from the spec's summary table, never hand-typed), and
`digital/item6-statement.json` is the committed statement accounting for
every row: none of the digital partition's rows is statistical (see
`signoff/README.md`, "Item 6 today", for the verdict that granted).
