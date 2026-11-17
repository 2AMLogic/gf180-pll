# Re-pin deltas: VCO, output, charge-pump and PFD records under open_pdks `f6eeac7`

`sim/` evidence is append-only, so re-qualifying a frozen reference record
after a PDK pin change mints a *new* record and names the old one in
**Supersedes** (`sim/README.md`, "Status / supersession language"). That
convention records *that* a re-run happened; it does not say *how much the
numbers moved*, which on a re-qualification is the whole finding. This
document is that missing half for the VCO / output / charge-pump / PFD group
of the #790 re-qualification — itself the re-qualification half of the #788
fleet re-pin
(`c6d73a35f524070e85faff4a6a9eef49553ebc2b` → `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`,
pinned by #789). It is the sibling of
[`REPIN-DELTAS-f6eeac7-devchar.md`](REPIN-DELTAS-f6eeac7-devchar.md) (#825)
and
[`REPIN-DELTAS-f6eeac7-lock-divider.md`](REPIN-DELTAS-f6eeac7-lock-divider.md)
(#827).

Every table below is generated from the two committed records by
`sim/lib/record_delta.py` and is reproducible from the tree alone; the exact
command sits above each one. Nothing here edits a record.

## The scope is twenty records, and this document grows by increments

#826 states this group as 20 live cited records across seven directories,
re-derived (not re-typed) from `origin/main` with the script quoted in that
issue's body — 8/1/2/1/3/3/2 for `vco-tuning-range`, `vco-bias-current`,
`output-range`, `output-driver`, `cp-compliance`, `mc-cp-mismatch`,
`pfd-deadzone`. The 27 the issue was originally filed with included records
already superseded by a cited successor, which its own Out of Scope excludes,
and `output-range`'s `20261111-184929-73837b9` already carries `f6eeac7`.

The clean-tree rule (one campaign at a time, each committed before the next
starts — #825 lost ~160 batch points learning it) makes the group too long
for a single landing, so it lands as per-directory increments and **#826
stays open** for the remainder. Dispositions so far:

| directory | live records | disposition |
|---|---|---|
| `output-driver` | `20260817-100354-0e9cfc9` | **re-qualified here** (`20261115-130526-3be016c`) |
| `vco-tuning-range` | `20260804-162735-72883fb`, `20260804-211600-f599a65`, `20260817-143524-0e9cfc9`, `20260923-084925-1655e11`, `20260927-081930-d004d5b`, `20260927-094524-b994116`, `20260927-214737-546a397`, `20260927-220631-546a397` | still owed under #826 |
| `vco-bias-current` | `20260911-172350-da0bb1e` | still owed under #826 |
| `output-range` | `20260801-061907-67d7127`, `20260819-190341-70a4128` | still owed under #826 |
| `cp-compliance` | `20260801-190821-734f483`, `20260802-033728-c24ee3a`, `20260802-061841-c24ee3a` | still owed under #826 |
| `mc-cp-mismatch` | `20260731-212614-640560e`, `20260927-093235-b994116`, `20260927-102154-d004d5b` | still owed under #826 |
| `pfd-deadzone` | `20260801-234626-5b333d0`, `20260916-051356-8cedbba` | still owed under #826 |

Re-derive the supersession side of that table with
`bash sim/lib/check-record-supersession.sh`, which builds the same graph from
the records' own **Supersedes** fields.

## What was re-run

| campaign | superseded record | new record | grid |
|---|---|---|---|
| `output-driver` | `20260817-100354-0e9cfc9` | `20261115-130526-3be016c` | 90 pts (5 MOS bundles × 3 temps × 3 supplies × 2 band/Vctrl edge points) |

open_pdks `f6eeac7`, **every point executed on the batch fleet** — the host
that minted the record ran no ngspice of its own (24 concurrent off-host
jobs, `--batch-wait-for-capacity 1800`; the recording host's own ngspice pin
is 47 and irrelevant to the points, each of which ran on its own execution
host). The batch image's `f6eeac7` stamp was confirmed by #825's and #827's
records already on `main` before this grid was spent. One earlier submission
of this same grid was discarded unread: its driver was killed mid-collect at
80/90, its leftover `corners/` directory dirtied the tree of the next
attempt, and that attempt was discarded too — a DIRTY-tree record is not
citable, so both were deleted before this clean-tree run. The predecessor's
own provenance was a dirty-tree run; this record upgrades it to clean.

## Verdict

**Four per-corner verdicts flipped, all four on `duty_pct` at the `fs`/`lo`
edge against spec/pll.md#output-duty-cycle's 45 % floor, and all four are
simulator-attributed (next section).** Three rows crossed FAIL→PASS and one
PASS→FAIL; four further rows stayed FAIL with moved values. The
campaign-level verdict is unchanged — the floor was already unmet at 7/90
points and remains unmet at 5/90, all `fs`/`lo` — and **no stated limit
moved**. The flips are tabulated below ("Per-corner verdict flips") and
were accepted as current evidence by operator ruling 2026-11-15.

The large relative deltas on `trise`/`tfall` (161 % / 93 %) are artefacts of
the comparator's denominator, not physical movements: both measurements
cross zero on this grid (the deck's crossing-interpolation makes sub-noise
ps-scale and occasionally negative readings possible, which the predecessor
record already carried), so a sub-nanosecond absolute move divides by a
near-zero old value. The absolute column is the meaningful one for those two
rows.

## Attribution: PDK or simulator?

The fleet re-baked ngspice along with the PDK, so the new record differs
from its predecessor in *two* variables at once (`c6d73a3` → `f6eeac7` and
ngspice-46 → ngspice-47) plus execution backend. The predecessors in this
group ran ngspice-46 (the record's own `Executing simulator` line is the
authority — read it per record, do not assume), so the control is ngspice-46
under the re-pinned PDK, run locally, one corner at a time:

```bash
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py output-driver --backend local \
  --corners <bundle> --temps <t> --supply <v> --supply-tol 0 --no-write -j 1
```

Five control points were taken, deliberately including the `fs`/27 °C row
family where every verdict flip lives:

| control point (ngspice-46 + `f6eeac7`) | vs predecessor `20260817-100354-0e9cfc9` |
|---|---|
| `typical_27c_3.30v` (`lo`, `hi`) | identical to the last printed digit, all 14 columns |
| `ss_125c_2.97v` (`lo`, `hi`) | identical to the last printed digit, all 14 columns |
| `fs_27c_2.97v_lo` | identical — `duty_pct` 45.0065 |
| `fs_27c_3.30v_lo` | identical — `duty_pct` 44.4337 |
| `fs_27c_3.63v_lo` | identical — `duty_pct` 44.375 |

Holding ngspice at 46 reproduces the predecessor bit-for-bit at every probed
corner, including the exact rows that flip under the fleet's ngspice-47. On
this bench **the PDK re-pin is a no-op and the entire old-vs-new delta,
flips included, is simulator residue** — the same attribution #825's
device-characterization group found, and the opposite of #827's
`divider-ratio-cell`, where the PDK was the mover. The simulator-version
mixture inside this group's predecessors (ngspice-42 on two `cp-compliance`
records, ngspice-46 elsewhere) means each bench re-qualified later in this
document needs its own control against its own predecessor's version.

## `output-driver`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/output-driver/records/20260817-100354-0e9cfc9.md \
  sim/output-driver/records/20261115-130526-3be016c.md
```

### `20261115-130526-3be016c` vs `20260817-100354-0e9cfc9`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `duty_pct` | min=45, max=55 | 44.375..50.6958 | 44.4142..50.6958 | 1.0333 | 2.325 | `fs_27c_3.30v_lo` |
| `` | `fosc` | min_spread_pct=5 | 3.532200e+06..4.728810e+08 | 3.533470e+06..4.728810e+08 | 35920 | 0.9562 | `typical_27c_3.63v_lo` |
| `` | `t_f1` | — | 1.606720e-08..1.653320e-06 | 1.606720e-08..1.653870e-06 | 1.630000e-09 | 0.1129 | `sf_27c_2.97v_lo` |
| `` | `t_f2` | — | 1.829330e-08..1.910460e-06 | 1.829330e-08..1.910920e-06 | 1.550000e-09 | 0.08696 | `ff_125c_3.30v_lo` |
| `` | `t_r1` | — | 1.605690e-08..1.676980e-06 | 1.605690e-08..1.677440e-06 | 1.590000e-09 | 0.1071 | `fs_27c_3.30v_lo` |
| `` | `t_r2` | — | 1.866380e-08..1.957040e-06 | 1.866380e-08..1.957080e-06 | 1.480000e-09 | 0.07969 | `typical_27c_3.63v_lo` |
| `` | `tfall` | — | -3.428550e-09..2.638650e-09 | -3.428550e-09..2.839090e-09 | 1.370310e-09 | 93.3 | `fs_125c_3.63v_lo` |
| `` | `thigh` | — | 1.015700e-09..1.284800e-07 | 1.015700e-09..1.284200e-07 | 2.740000e-09 | 2.495 | `fs_27c_3.30v_lo` |
| `` | `tperiod` | — | 2.114700e-09..2.831090e-07 | 2.114700e-09..2.830080e-07 | 2.521000e-09 | 0.947 | `typical_27c_3.63v_lo` |
| `` | `trise` | — | -2.488800e-09..1.591490e-08 | -2.488800e-09..1.591200e-08 | 1.923780e-09 | 160.9 | `ss_-40c_2.97v_lo` |
| `` | `voh` | — | 2.99966..3.76598 | 2.99966..3.766 | 0.02434 | 0.7224 | `sf_-40c_3.30v_lo` |
| `` | `voh_ratio` | min=0.9 | 1.00595..1.04403 | 1.00595..1.04145 | 0.00737 | 0.7218 | `sf_-40c_3.30v_lo` |
| `` | `vol` | — | -0.12787..-0.0218946 | -0.130686..-0.0218946 | 0.0281936 | 40.44 | `fs_-40c_3.30v_lo` |
| `` | `vol_ratio` | max=0.1 | -0.0396747..-0.00603156 | -0.0403156..-0.00603156 | 0.0085436 | 40.44 | `fs_-40c_3.30v_lo` |

**Per-corner verdict flips** (each one is a finding):

| topology | corner-id | old | new |
|---|---|---|---|
| `` | `ff_-40c_3.30v_lo` | FAIL — duty_pct min=45 (got 44.7873) | PASS |
| `` | `fs_-40c_3.30v_lo` | FAIL — duty_pct min=45 (got 44.5683) | PASS |
| `` | `fs_-40c_3.63v_lo` | FAIL — duty_pct min=45 (got 44.894) | FAIL — duty_pct min=45 (got 44.4142) |
| `` | `fs_125c_3.30v_lo` | FAIL — duty_pct min=45 (got 44.9554) | FAIL — duty_pct min=45 (got 44.941) |
| `` | `fs_125c_3.63v_lo` | FAIL — duty_pct min=45 (got 44.7828) | FAIL — duty_pct min=45 (got 44.5497) |
| `` | `fs_27c_2.97v_lo` | PASS | FAIL — duty_pct min=45 (got 44.9825) |
| `` | `fs_27c_3.30v_lo` | FAIL — duty_pct min=45 (got 44.4337) | PASS |
| `` | `fs_27c_3.63v_lo` | FAIL — duty_pct min=45 (got 44.375) | FAIL — duty_pct min=45 (got 44.7614) |

**Stated limits**: identical in both records.

_8 finding(s) above need a human disposition._

The `voh_ratio`/`vol_ratio` checks and the `fosc` integrity spread stay
inside their bounds at every point in both records; the levels/drive half of
the claim is unaffected. The eight findings the comparator lists are all the
`duty_pct` rows above plus the two crossing-zero artefact rows called out in
the Verdict section — none other.
