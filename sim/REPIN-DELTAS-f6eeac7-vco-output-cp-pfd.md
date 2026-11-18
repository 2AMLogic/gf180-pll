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

## The scope was twenty records, and this document grows by increments

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
| `vco-tuning-range` tuning grid | `20260804-162735-72883fb` | **re-qualified here** (`20261118-021803-deb4ec0`) |
| `vco-tuning-range` supply bench | `20260804-211600-f599a65` | **re-qualified here** (`20261118-023753-1b6f7c2`) |
| `vco-tuning-range` Monte Carlo family | `20260817-143524-0e9cfc9`, `20260923-084925-1655e11`, `20260927-081930-d004d5b`, `20260927-094524-b994116`, `20260927-214737-546a397`, `20260927-220631-546a397` | still owed under #826 — the six band-select-mirror Monte Carlo / negative-control records; see the vco-tuning-range section for why they are a separate increment |
| `vco-bias-current` | `20260911-172350-da0bb1e` | **re-qualified here** (`20261117-150323-f3b3e7f`) |
| `output-range` | `20260801-061907-67d7127`, `20260819-190341-70a4128` | **re-qualified here** (`20261117-174557-327ee00` and `20261117-174951-33cbd72`) — two single-point re-runs, one per predecessor; the 90-row grid under the re-pinned PDK is the already-landed `20261111-184929-73837b9` |
| `cp-compliance` | `20260801-190821-734f483`, `20260802-033728-c24ee3a`, `20260802-061841-c24ee3a` | **re-qualified here** — `20261115-025500-8da7900` (DC bench) and `20261116-180719-930fb6e` (switching bench); the third id, `20260802-033728-c24ee3a`, is the near-duplicate twin of the re-run `20260802-061841-c24ee3a`, dispositioned in the cp-compliance section below rather than silently dropped |
| `mc-cp-mismatch` | `20260731-212614-640560e`, `20260927-093235-b994116`, `20260927-102154-d004d5b` | still owed under #826 |
| `pfd-deadzone` | `20260801-234626-5b333d0`, `20260916-051356-8cedbba` | **re-qualified here** (`20261116-195826-16f19a5`, `20261116-183811-1379f1f`) |

Re-derive the supersession side of that table with
`bash sim/lib/check-record-supersession.sh`, which builds the same graph from
the records' own **Supersedes** fields.

Increments have landed since that table was first written: #967
re-qualified `output-driver` (2026-11-15), the second increment (2026-11-17,
same branch, still `Part of #826`) re-qualified both `cp-compliance` benches
and both `pfd-deadzone` manifests, the third (2026-11-17, same branch)
re-qualified `vco-bias-current`, the fourth (2026-11-17, same branch)
re-qualified both `output-range` single-point records, and the fifth
(2026-11-18, same branch) re-qualified the `vco-tuning-range` tuning grid
and supply bench. The live scope the issue's own derivation script returns
is therefore **10 records, not 20** — `6/0/0/3` plus its one `cp-compliance`
residual across the three remaining directories `vco-tuning-range`,
`cp-compliance`, `mc-cp-mismatch`. The script counts supersession from
records' own `Supersedes` fields, so its one `cp-compliance` residual,
`20260802-033728-c24ee3a`, is dispositioned in the cp-compliance section
below as fully superseded by the second increment's re-run of its
near-duplicate twin — in prose, not by any record's `Supersedes` field —
and the script will keep returning it until a record names it. Records
needing a re-run: **9** — 6/0/0/3 across those same three directories, all
still owed under #826.

## What was re-run

| campaign | superseded record | new record | grid |
|---|---|---|---|
| `output-driver` | `20260817-100354-0e9cfc9` | `20261115-130526-3be016c` | 90 pts (5 MOS bundles × 3 temps × 3 supplies × 2 band/Vctrl edge points) |
| `cp-compliance` DC bench | `20260801-190821-734f483` | `20261115-025500-8da7900` | 180 pts (45 PVT × 4 Icp trim codes) |
| `cp-compliance` switching bench | `20260802-061841-c24ee3a` | `20261116-180719-930fb6e` | 135 pts (45 PVT × 3 Vctrl) |
| `pfd-deadzone` operating-point manifest | `20260916-051356-8cedbba` | `20261116-183811-1379f1f` | 405 pts (45 PVT × 3 Vctrl × 3 phase offsets) |
| `pfd-deadzone` dead-zone bench | `20260801-234626-5b333d0` | `20261116-195826-16f19a5` | 225 pts (45 PVT × 5 phase offsets) |
| `vco-bias-current` | `20260911-172350-da0bb1e` | `20261117-150323-f3b3e7f` | 234 pts (13 bundles × 3 temps × 3 supplies × 2 band codes) |
| `output-range` lo-edge diagnostic | `20260801-061907-67d7127` | `20261117-174557-327ee00` | 1 pt (typical / 27 °C / 3.30 V, `lo` edge, band 1, N=8, seed 1.679 V) |
| `output-range` CAPPED `hi` row | `20260819-190341-70a4128` | `20261117-174951-33cbd72` | 1 pt (ff / 27 °C / 3.30 V, `hi` edge, band 7, N=32, seed 1.454 V) |
| `vco-tuning-range` tuning grid | `20260804-162735-72883fb` | `20261118-021803-deb4ec0` | 504 pts (7 bundles × 3 temps × 3 supplies × 8 band codes) |
| `vco-tuning-range` supply bench | `20260804-211600-f599a65` | `20261118-023753-1b6f7c2` | 144 pts (one shared grid — 63 static-pushing + 63 mandated-PVT transient + 12 band-sweep + 6 ripple-frequency-check points; both decks run at every point, 288 graded rows) |

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

The four charge-pump/PFD grids above (2026-11-15 … 2026-11-17) were run the
same way — `--backend batch`, clean-tree provenance at the commit each
campaign ran from, sequential with a commit between each, raw evidence
manifest-forward via `sim/lib/artifact-put.sh`. On simulator version they do
not all read the same, and this document does not assume they do: both
`pfd-deadzone` grids attribute ngspice-47 per point — their records omit the
`Executing simulator` line, which per `sim/harness/report.py` means every
point reported exactly the recording version — while both `cp-compliance`
grids disclose `Executing simulator: unattributed` on every point (all 315):
their decks printed no ngspice version banner, so ngspice-47 is *not* read
provenance there. What all four share is the batch image itself — an
identical `Simulator init` fingerprint (`sha256:d6efd5b2…`, 945/945 points),
the same fingerprint under which #967's output-driver record *does* attribute
ngspice-47 per point. The switching grid (18:07) attributed nothing; the
operating-point grid 31 minutes later (18:38) attributed 47 on all 405
points — same backend, same init hash, different banners — so per-grid
attribution is read from each record, not assumed from the way they were
run. ngspice-47 is therefore read on the two PFD grids and inferred from the
shared image on the two `cp-compliance` grids; the attribution argument
below rests on measured probe-vs-fleet numeric agreement, not on the version
string.
One earlier dead-zone-grid submission minted a DIRTY-tree record and was
deleted unread (the same discard rule as above); the landed
`20261116-195826-16f19a5` re-ran clean at commit `16f19a59`. The session
that produced these four was interrupted between that run and its commit;
the completed record and its stored artifact manifest were recovered and
landed unchanged — its provenance line names the clean tree it ran from,
which is what makes that recovery legible.

The `vco-bias-current` grid (2026-11-17) ran the same way — `--backend
batch`, clean-tree provenance at the commit each attempt started from — and
is this document's first recovery through the per-point store rather than
around it: its first submission was refused for want of fleet capacity after
42 of 234 points (12 retries across the 1800 s capacity-wait budget; the
layer's pools were held by other work), and those 42 points were already
banked per-point. The retry re-submitted under a fresh record id, adopted
the banked 42 by an identical grid fingerprint (each fetched object
sha256-verified), and simulated the remaining 192; the record discloses the
split on its face, and its provenance line names the clean tree — the
banking commit — the adopting attempt started from. The discarded
reservation `20261117-141510-2673695` stays reserved without a record and is
never reused; its per-point manifest is committed as the adoption's source
of truth. `Executing simulator: unattributed (234)` on the landed record —
this deck prints no ngspice version banner per point, so ngspice-47 there is
the shared batch image's, fingerprint-inferred (`sha256:d6efd5b2…`, 234/234
points) rather than read, the same disclosure class as the two
`cp-compliance` grids.

The `vco-tuning-range` grids (2026-11-18) ran the same way — `--backend
batch`, clean-tree provenance at the commit each attempt started from,
sequential with a commit between the two benches — and the tuning grid is
this document's second recovery through the per-point store: two earlier
submissions of the 504-point grid were interrupted (the first
capacity-refused after 257 points, the second killed mid-run with 234 fresh
points done, 491/504 total), each attempt's completed per-point logs banked
manifest-forward and committed as it stood (`8e80a309`, `deb4ec08`). The
landed record `20261118-021803-deb4ec0` started from the clean tree at the
second banking commit, adopted 496 banked points by identical grid
fingerprint (each fetched object sha256-verified, disclosed on the record's
face with `"replayed": true`), and simulated the remaining 8. The supply
bench then ran clean from the tuning grid's own commit (`1b6f7c24` →
`20261118-023753-1b6f7c2`, 144 points, no adoption needed). Both records
attribute ngspice-47 per point. The tuning grid's one acceptance-check
flip is filed as #1059; see the vco-tuning-range section below.

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

**The charge-pump and PFD increments (2026-11-17) add zero flips.** All four
comparisons — 180 + 135 + 405 + 225 = 945 graded rows — come back
**per-corner verdicts unchanged, stated limits identical**; the comparator
reports no findings section for any of them. The `cp-compliance` DC bench is
the strongest result in this document: **every graded row of all 180 is
bit-for-bit identical** to a predecessor that ran under a different PDK pin,
a different simulator major version and a different execution backend — the
predecessor's ngspice-42 is its record's own attribution; this run's
ngspice-47 is inferred from the shared batch image, not read from it (the DC
record discloses `Executing simulator: unattributed` on all 180 points). Where the other three benches move at all, the movement is confined
to the femtocoulomb-scale charge integrals (`qnet`/`q_zero`/`qup`/`qdn`,
sub-fC absolute deltas) and the switch-timing quantities derived from them
(`wskew`, `ton_*`); the pulse widths and saturation margins that carry the
verdicts reproduce exactly. The large *relative* percentages the comparator
prints on `qnet` (up to 1.6e4 %) and `q_zero` (up to 61 %) are the same
denominator artefact as `trise`/`tfall` above — a 0.2–0.4 fC absolute move
dividing by a value of order 1e-17 C. No tolerance moved and nothing flipped,
so there is nothing to file: the four sections below are the evidence, not a
deferral.

**The `vco-bias-current` increment (2026-11-17) adds zero findings and is
this document's strongest result: bit-for-bit identical on all 936 graded
rows** (4 topologies × 234 corners, max abs delta 0 on every one of the 36
measurements the comparator grades). A predecessor that ran ngspice-46 on
this same Linux host class under `c6d73a3` is reproduced to the last printed
digit by a fleet record that ran ngspice-47 (fingerprint-inferred; the deck
prints no version banner) under `f6eeac7` on 189 execution hosts — the re-pin,
the simulator bump and the backend are each individually invisible on this
bench, which the controls below confirm one variable at a time. No tolerance
moved and nothing flipped; nothing to file.

**The `output-range` increment (2026-11-17) adds zero verdict flips and no
findings to file.** Its two comparisons grade zero shared rows in the
comparator — both predecessors are narrative investigation records that
predate the corner-id table schema — so the attribution rests on the quoted
rows and the controls above, not on a generated delta column: the `lo`
point's `vctrl_final` is 1.70267 V under ngspice-42, ngspice-46 and the
fleet build alike (0.33 mV from the pre-re-pin baseline row, FAIL verdict
unchanged), and the previously-stalled `hi` point completes under the
re-pinned PDK on every source that tried it, its verdict-bearing values
landing on the predecessor's own completed perturbed-seed control run
(1.45651 V vs 1.4565 V, mean DN 0.0339 vs 0.0339103) with FAIL and DN-guard
PASS unchanged. The one status transition, CAPPED → FAIL, is a non-verdict
becoming the verdict — the predecessor's own words — not a PASS/FAIL flip.
Nothing to file.

**The `vco-tuning-range` increment (2026-11-18) adds one curve-level
acceptance-check flip and zero per-point findings.** Both comparisons come
back **per-corner verdicts unchanged** — 504 graded rows on the tuning
grid, 288 on the supply bench — with stated limits identical and no
comparator findings section on either. In the supply bench's jitter phase
the supply-induced rows (`rip_*`, `step_*`) move ≤ 0.28 % relative — worst
`rip_tj_pp_s` at 0.2742 % — while the rows that move by tens of percent
are the quiet-copy numerical floor and the `floor_margin_x` ratio built on
it, which the record's own methodology calls solver noise, not results.
The push phase needs its own disposition: 24 of its rows move above
0.28 % relative. The pushing coefficient itself moves ≈3.3 %
(`push_norm_pct_per_v` 3.433 %, `push_slope_hz_per_v` 3.297 % — the
−54.5 → −54.6 move the `sim/CHARACTERIZATION.md` row records), the supply
currents reach `i6` 5.433 % and `i7` 4.998 %, and `push_nl_pct` — a
limit-bearing row, and the bench's largest relative mover at 141.8 % —
moves an absolute 1.542 against its `max=5` limit at
`sf_27c_3.30v_band0_r16_f100` (≈31 % of the limit budget, verdict
unchanged; the relative figure divides two small nonlinearity
percentages, 0.13..3.4 across the old range, so it reads far larger than
the absolute move). With the ngspice-46 control below reproducing the
predecessor bit-for-bit at the shared point, these push-phase moves are
host/batch-build residue, not PDK. The one flip is acceptance check 5
(f(Vctrl) monotonicity) at
`all-fast/27C/3.30V` band 1 under the batch image's ngspice-47 — a
transient-solve inversion that every other solver build tested resolves the
other way, and that the pinned local ngspice-47 cannot solve at all inside
the harness's 300 s point budget. It is filed as **#1059** with its
controls, per this issue's acceptance criteria, and the record stands as
latest evidence pending that disposition.


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

### Controls for the `cp-compliance` and `pfd-deadzone` increment (2026-11-17)

Four benches, three predecessor simulator versions (read from each record's
own provenance: ngspice-42 on the DC bench, ngspice-46 on the switching bench
and both PFD manifests — the latter three on Darwin arm64, the DC bench on
Linux x86_64). The controls hold the simulator at the predecessor's version
and run the re-pinned PDK locally, one corner at a time (`--no-write`, so
they mint nothing; note a one-corner probe fails the manifests' grid-level
`min_measured_points=45` checks by construction — the per-point values are
the evidence, the grid-level FAIL status is the subset talking):

```bash
PATH=/usr/bin:$PATH \
  python3 sim/run_corners.py cp-compliance --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 --no-write -j 2
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py cp-compliance/testbench-switching --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 --no-write -j 2
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py pfd-deadzone --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 --no-write -j 2
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py pfd-deadzone/testbench-operating-point --backend local \
  --corners typical ss --temps 27 125 --supply 3.30 --supply-tol 0 --no-write -j 2
```

| control (simulator + `f6eeac7`) | vs predecessor |
|---|---|
| DC bench, `typical_27c_3.30v` × 4 trim codes (ngspice-42) | identical to the last printed digit, every column of all 4 points |
| switching bench, `typical_27c_3.30v` × 3 Vctrl (ngspice-46) | `x0.9` and `x2.4`: identical, every column. `x1.65`: `iup_ss`/`idn_ss`/`toff_*` identical; `qup` +1.7e-17 C, `wup` +3.5 ps (0.08 %), `wskew` −1.76993e-10 → −1.728213e-10 (4.2 ps), `ton_dn` +0.1 ps on a 5.7 ps reading |
| dead-zone bench, `typical_27c_3.30v` × 5 dphi (ngspice-46) | `width_up`/`width_dn` identical to the last printed digit at all 5; `qnet` moves ≤ 0.9 fC absolute (largest at `d0`: −8.92e-16 → −8.40e-16) |
| operating-point manifest, `typical_27c_3.30v` + `ss_125c_3.30v`, 9 pts each (ngspice-46) | every width identical to the last printed digit at all 18; `qnet` identical at 14 of 18, moves ≤ 0.4 fC at the rest |

Reading the four controls together with the batch deltas below:

- **The PDK re-pin is a no-op on all four benches.** Nothing in any control
  moved in a way that scales like a device-model change — the currents that
  would move (`iup_ss`/`idn_ss`, the saturation margins) are identical
  everywhere they were probed.
- **The femtocoulomb-scale `qnet`/`q_zero` movement is platform numerics,
  not the 46→47 bump and not the PDK**: at every probed corner the
  ngspice-46 Linux probe and the batch fleet record print the *same*
  values to the last digit (dead-zone `d0` qnet −8.40045e-16 in both;
  operating-point `v1p65_d0` −9.67131e-16 in both; switching `x1.65`
  `wskew` −1.72821e-10 in both), while the ngspice-46 *Darwin* predecessor
  differs there. (On the fleet side, ngspice-47 is read per point on the
  dead-zone and operating-point grids and inferred from the shared batch
  image on the switching grid — the agreement rests on the numbers, not the
  label.) This is exactly the residue class both PFD predecessors'
  own "Cross-record comparability" bullets predict for sub-fC charge
  integrals.
- **The switching bench's mid-window `x1.65` row confirms it**: the probe's
  moved values (`wskew` −1.728213e-10, `ton_dn` 5.822562e-12) and the batch
  record's (`-1.72821e-10`, `5.82256e-12`) agree to the last printed digit —
  one ngspice-46 Linux probe and one batch fleet run land on the same
  number, so the movement was already fully present without the simulator
  bump. The switching record attributes no ngspice version per point (its
  47 is the shared image's, fingerprint-inferred), so this identification
  rests on the measured numbers, not on either side's version label. The
  window ends (`x0.9`, `x2.4`) do not move anywhere.

The DC bench predecessor already ran ngspice-42 on this Linux image, so its
control held *everything* fixed but the PDK pin — and that control is
bit-for-bit, which is why the DC bench's batch delta below comes back
bit-for-bit too: on this bench the re-pin, the simulator bump and the backend
are each individually invisible.

### Controls for the `vco-bias-current` increment (2026-11-17)

One bench, one predecessor simulator version — ngspice-46, read from the
predecessor record's own provenance (`ngspice-46 … Linux-…-aws-x86_64`, the
same host class as the prober). The control holds the simulator at 46 and
runs the re-pinned PDK locally, one corner at a time, `--no-write`; the
issue's literal ngspice-42 probe is run alongside it, so the two controls
bracket the predecessor's version from both sides:

```bash
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py vco-bias-current --backend local \
  --corners typical all-fast --temps 27 125 --supply 3.30 --supply-tol 0 \
  --no-write -j 2
PATH=/usr/bin:$PATH \
  python3 sim/run_corners.py vco-bias-current --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 --no-write -j 2
```

(`--supply` is single-valued per invocation; the two control corners were
taken as two runs. Each point grades 37 measurements across the four
topologies, both band codes.)

| control (simulator + `f6eeac7`) | vs predecessor `20260911-172350-da0bb1e` |
|---|---|
| `typical_27c_3.30v` × 2 band codes (ngspice-46) | identical to the last printed digit, every column of both points — witness resistors (`r3k_cg` 18188, `rsh_ratio` 8.3011), bias supply (`ibias_a_lo_ua` 34.6489 / 136.567), ring stage (`itail_a_mid_ua` 2.55705 / 76.6696, `vbn_a_mid` 0.700332 / 1.05771), 100 MHz point (`ivco_b_100m_ua` 2863.6) |
| `all-fast_125c_3.63v` × 2 band codes (ngspice-46) | identical to the last printed digit, every column — `rsh_ratio` 6.78009, `ibias_ratio_mid` 11.7229 / 8.73498, `itail_b_mid_ua` 34.8499 / 1018.4, `iring_b_mid_ua` 174.25 / 5092.01, `ivco_b_100m_ua` 3925.26 |
| `typical_27c_3.30v` × 2 band codes (ngspice-42, the issue's literal probe) | identical to the last printed digit, every column — the same values as the ngspice-46 control and the predecessor |

Reading the controls with the batch delta below: **the PDK re-pin is a no-op
on this bench, and so is the simulator bump** — ngspice-42, 46 and 47 all
print the same values at every probed corner, under either PDK pin, which is
why the 936-row batch delta comes back bit-for-bit. The predecessor itself
notes the mechanism: the claim quantities here are DC operating points of a
resistor–MOS bias network, six printed digits of headroom above solver
noise, with no charge-integral or crossing-interpolation measurement for
platform numerics to surface in.

### Controls for the `output-range` increment (2026-11-17)

Two single-point records, both predecessors ngspice-46 on Darwin arm64 (read
from each record's own provenance). The controls hold the simulator at the
predecessor's version and run the re-pinned PDK locally, one point at a time,
`--no-write`; the issue's literal ngspice-42 probe runs alongside, so the
controls again bracket the predecessor's version from both sides. Unlike the
DC benches above, this campaign's two points are ~1–2 minute transients, so
the probe costs nothing:

```bash
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py output-range --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 \
  --axis op=loin1p679 --no-write -j 1 --timeout 2400
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py output-range --backend local \
  --corners ff --temps 27 --supply 3.30 --supply-tol 0 \
  --axis op=hiin1p454 --no-write -j 1 --timeout 2400
PATH=/usr/bin:$PATH \
  python3 sim/run_corners.py output-range --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 \
  --axis op=loin1p679 --no-write -j 1 --timeout 2400
PATH=/usr/bin:$PATH \
  python3 sim/run_corners.py output-range --backend local \
  --corners ff --temps 27 --supply 3.30 --supply-tol 0 \
  --axis op=hiin1p454 --no-write -j 1 --timeout 2400
```

| control (simulator + `f6eeac7`) | `vctrl_final` | `dn_lvl` | vs predecessor / like-for-like reference |
|---|---|---|---|
| `loin1p679` (ngspice-46) | 1.70267 | -3.652520e-07 | **bit-for-bit the 20261111 grid record's row**; 0.33 mV from the pre-re-pin baseline row (`20260819-160843-4e32f91`: 1.703) |
| `loin1p679` (ngspice-42) | 1.70267 | -3.423358e-07 | `vctrl_final` bit-for-bit the same value again — three simulator builds, one number |
| `hiin1p454` (ngspice-46) | 1.4569 | 0.0322125 | **bit-for-bit the 20261111 grid record's row** (which completed where the old pin stalled) |
| `hiin1p454` (ngspice-42) | 1.45686 | 0.0325038 | 40 µV from ngspice-46, both well inside the row's 5 mV tolerance; the transient **completes on both** |

Reading the two controls together with the batch records below:

- **The PDK re-pin is a no-op on the graded `vctrl_final` at both points.**
  The `lo` point reads 1.70267 under ngspice-42, ngspice-46 and the fleet
  build alike, 0.33 mV from the pre-re-pin baseline row; the `hi` point's
  spread across all four sources (42 local, 46 local, the grid record's 46
  on the fleet, this increment's 47 on the fleet) is 0.39 mV against a 5 mV
  row tolerance. The `dn_lvl` readings move at the 1e-7 V (`lo`) and ~5 %
  (`hi`) scale across simulator builds — sub-µV and milli-volt quantities
  against a 9.9e-4 V guard floor — and the guard verdict is unchanged
  everywhere (SUSPECT at `lo`, PASS at `hi`).
- **The `hi` point's stall does not reproduce under the re-pinned PDK on any
  of the four sources** — it completed on the fleet in the already-recorded
  grid (ngspice-46), in both local controls, and in this increment's fleet
  record (ngspice-47). That is exactly what the predecessor's own null
  control predicted: a +1e-7 V seed move escaped the stall under the OLD
  pin, so the stall was one hypersensitive solver trajectory, not a
  property of the operating point. Under the re-pinned PDK the grid-seed
  trajectory completes everywhere it was tried.

### Controls for the `vco-tuning-range` increment (2026-11-18)

Two benches, both predecessors on Linux x86_64 (the supply bench's
ngspice-46 on an AWS host; the tuning grid's ngspice-46 on Darwin arm64 —
read from each record's own provenance). Controls hold the simulator at
the predecessor's version and run the re-pinned PDK locally, one point at
a time, `--no-write`:

```bash
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py sim/vco-tuning-range/testbench-supply --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 \
  --axis band=band0 --axis rdiv=r16 --axis fcal=f100 --no-write -j 1
PATH=/usr/bin:$PATH \
  python3 sim/run_corners.py sim/vco-tuning-range/testbench-supply --backend local \
  --corners typical --temps 27 --supply 3.30 --supply-tol 0 \
  --axis band=band0 --axis rdiv=r16 --axis fcal=f100 --no-write -j 1
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py vco-tuning-range --backend local \
  --corners all-fast --temps 27 --supply 3.30 --supply-tol 0 \
  --axis band=band1 --no-write -j 1
```

| control (simulator + `f6eeac7`) | vs predecessor |
|---|---|
| supply bench, `typical_27c_3.30v_band0_r16_f100` (ngspice-46) | **identical to the last printed digit, every column of both phases** — push frequencies, pushing coefficient, quiet/stepped/rippled jitter rows, `floor_margin_x` 463.746 |
| supply bench, same point (ngspice-42) | push phase identical to the last printed digit; jitter phase: supply-induced rows ≤ 2e-4 relative from the predecessor, quiet-floor rows move at the solver-noise scale |
| tuning grid, `all-fast_27c_3.30v_band1` (ngspice-46) | f5 = 1.570530e+07 → f6 = 1.760210e+07 Hz — **monotonic**, 0.05 % from the predecessor's f6 (the predecessor is a Darwin arm64 record) |
| tuning grid, same point (ngspice-42) | f6 = 1.760210e+07 Hz — monotonic, identical to the ngspice-46 probe |
| tuning grid, same point (pinned local ngspice-47) | **times out** after the harness's 300 s point budget — the batch image's 47 build returns the dipped f6 instead |

A fourth leg separates the PDK from the host on the tuning grid, which the
pinned harness cannot do (it refuses a non-pinned PDK tree, correctly): the
composed probe deck for `typical_27c_3.30v_band0` with its include paths
pointed at the retired `~/.volare` tree (`c6d73a3`), run as a single
`ngspice -b` invocation under ngspice-42 — an attribution probe only,
nothing minted — prints **exactly the same values as the same deck against
`f6eeac7`** (f4 = 6.526290e+06 Hz, `sw7hi` = 3.363994 V, to the last
digit).

Reading the controls together with the batch records below:

- **The PDK re-pin is a bit-for-bit no-op on both benches.** The supply
  bench's ngspice-46 control reproduces its Linux ngspice-46 predecessor
  exactly under the new pin; the tuning grid's old-pin/new-pin deck pair
  prints identical values, so its old-vs-new residue is host-class
  (Darwin arm64 → Linux x86_64) plus simulator, never the PDK — the same
  cross-record-comparability class `sim/README.md` reserves for exactly
  this.
- **The check-5 flip is a batch-image ngspice-47 transient-solve
  inversion**: ngspice-46 and ngspice-42 both solve the curve monotonically
  under the new pin, the local ngspice-47 build cannot solve the point at
  all in 300 s, and the batch's 47 build returns a dipped f6. Filed as
  #1059.
- **The fleet-vs-predecessor residue on the tuning grid — frequencies up to
  ~0.8 % (`f7` 0.819 %, `f5` 0.4599 %, excluding the #1059 band-1 curve),
  swing-high buffer rows ≤ 1.9 %, and the near-zero swing-low rails at
  429 % / 64.81 % relative (absolute 0.0816 V / 0.0632 V against the
  0.3 V limit, ≈27 % / ≈21 % of its budget) — is host plus
  batch-build**, not PDK and not the 46→47 version label alone: the local
  ngspice-47 probe of the supply bench's control point reproduced the
  predecessor's pushing phase bit-for-bit while the fleet's 47 build moves
  it by ~0.05 % — same version string, same staged init fingerprint
  (`sha256:d6efd5b2…`), different binary.


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

## `cp-compliance`

Regenerate the DC bench's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/cp-compliance/records/20260801-190821-734f483.md \
  sim/cp-compliance/records/20261115-025500-8da7900.md
```

### `20261115-025500-8da7900` vs `20260801-190821-734f483`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `idn_flat_pct` | — | 0.591914..1.01676 | 0.591914..1.01676 | 0 | 0 | `—` |
| `` | `idn_hi_a` | — | 1.648898e-06..7.307846e-06 | 1.648898e-06..7.307846e-06 | 0 | 0 | `—` |
| `` | `idn_lo_a` | — | 1.638604e-06..7.235820e-06 | 1.638604e-06..7.235820e-06 | 0 | 0 | `—` |
| `` | `idn_mid_a` | — | 1.646495e-06..7.272235e-06 | 1.646495e-06..7.272235e-06 | 0 | 0 | `—` |
| `` | `iup_flat_pct` | — | 0.237094..0.484518 | 0.237094..0.484518 | 0 | 0 | `—` |
| `` | `iup_hi_a` | — | 1.705404e-06..7.133040e-06 | 1.705404e-06..7.133040e-06 | 0 | 0 | `—` |
| `` | `iup_lo_a` | — | 1.712272e-06..7.154354e-06 | 1.712272e-06..7.154354e-06 | 0 | 0 | `—` |
| `` | `iup_mid_a` | — | 1.710739e-06..7.146232e-06 | 1.710739e-06..7.146232e-06 | 0 | 0 | `—` |
| `` | `mism_absmax_pct` | — | -2.67623..4.70911 | -2.67623..4.70911 | 0 | 0 | `—` |
| `` | `mism_hi_pct` | — | -2.67623..3.47602 | -2.67623..3.47602 | 0 | 0 | `—` |
| `` | `mism_lo_pct` | — | -1.43951..4.70911 | -1.43951..4.70911 | 0 | 0 | `—` |
| `` | `mism_mid_pct` | — | -2.04974..4.11748 | -2.04974..4.11748 | 0 | 0 | `—` |
| `` | `satcasc_hi_v` | — | 0.334933..1.07879 | 0.334933..1.07879 | 0 | 0 | `—` |
| `` | `satcasc_lo_v` | — | 0.671825..0.757827 | 0.671825..0.757827 | 0 | 0 | `—` |
| `` | `satchk_ncasc_hi_v` | — | 1.70036..2.25577 | 1.70036..2.25577 | 0 | 0 | `—` |
| `` | `satchk_pcasc_hi_v` | — | 0.334933..1.07879 | 0.334933..1.07879 | 0 | 0 | `—` |
| `` | `satmir_hi_v` | — | -0.0256661..-0.00764908 | -0.0256661..-0.00764908 | 0 | 0 | `—` |
| `` | `satmir_lo_v` | — | -0.0274296..-0.00690388 | -0.0274296..-0.00690388 | 0 | 0 | `—` |
| `` | `units` | — | 1..4 | 1..4 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 180 graded rows.

**Stated limits**: identical in both records.

Every graded value of all 180 rows is identical — the comparator has no
findings section. The compliance verdict (both cascode margins positive
across the window at every corner and trim code) carries over unchanged, and
this predecessor was already a clean-tree record.

Regenerate the switching bench's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/cp-compliance/records/20260802-061841-c24ee3a.md \
  sim/cp-compliance/records/20261116-180719-930fb6e.md
```

### `20261116-180719-930fb6e` vs `20260802-061841-c24ee3a`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `idn_ss` | — | -5.400147e-06..-4.950816e-06 | -5.400147e-06..-4.950816e-06 | 1.000000e-12 | 1.955e-05 | `sf_125c_3.30v_x2.4` |
| `` | `iup_ss` | — | 4.612520e-06..5.390846e-06 | 4.612520e-06..5.390846e-06 | 5.000000e-12 | 9.921e-05 | `fs_27c_3.30v_x0.9` |
| `` | `qdn` | — | -2.520884e-14..-2.163931e-14 | -2.520884e-14..-2.163931e-14 | 5.180000e-18 | 0.02113 | `fs_27c_3.30v_x0.9` |
| `` | `qup` | — | 1.989257e-14..2.312385e-14 | 1.989257e-14..2.312385e-14 | 1.965000e-17 | 0.098 | `ff_-40c_3.30v_x2.4` |
| `` | `toff_dn` | — | 3.850452e-12..4.810196e-11 | 3.850452e-12..4.810196e-11 | 1.000000e-17 | 2.76e-05 | `fs_27c_3.30v_x0.9` |
| `` | `toff_up` | — | -9.995444e-11..-9.991909e-11 | -9.995444e-11..-9.991909e-11 | 2.000000e-17 | 2.001e-05 | `typical_27c_3.30v_x1.65` |
| `` | `ton_dn` | — | -3.124155e-11..1.002974e-10 | -3.124155e-11..1.002974e-10 | 1.824020e-12 | 12.15 | `ff_-40c_3.30v_x2.4` |
| `` | `ton_skew` | — | -2.002673e-10..-6.874855e-11 | -2.002673e-10..-6.874855e-11 | 1.819660e-12 | 2.141 | `ff_-40c_3.30v_x2.4` |
| `` | `ton_up` | — | -9.999452e-11..-9.996421e-11 | -9.999555e-11..-9.996421e-11 | 2.076000e-14 | 0.02076 | `fs_27c_3.30v_x0.9` |
| `` | `wdn` | — | 4.306192e-09..5.040624e-09 | 4.306192e-09..5.040624e-09 | 9.890000e-13 | 0.02111 | `fs_27c_3.30v_x0.9` |
| `` | `wskew` | — | -6.010459e-10..-4.762387e-11 | -6.010459e-10..-4.762387e-11 | 4.171400e-12 | 2.357 | `typical_27c_3.30v_x1.65` |
| `` | `wup` | — | 3.880182e-09..4.551728e-09 | 3.876379e-09..4.551728e-09 | 3.803000e-12 | 0.09801 | `ff_-40c_3.30v_x2.4` |

**Per-corner verdicts**: unchanged on all 135 graded rows.

**Stated limits**: identical in both records.

The steady-state currents move at the 1e-4 % level (5 nA in 5 µA at worst)
and the switching-derived quantities (`wskew`, `ton_*`, `qup`/`qdn`) move by
picoseconds and attocoulombs against 4 ns widths and tens of femtocoulombs.
The largest relative row, `ton_dn` 12.15 %, is a 1.8 ps move on a reading of
order 15 ps — the crossing-interpolation granularity, not a device shift; its
absolute column is the meaningful one, as with `trise`/`tfall` in the
Verdict section. The `x1.65` worst corners are the same points the
ngspice-46 control (Attribution section) moved on, and the control's values
match this record's to the last printed digit — the residue is platform
numerics, present identically without the simulator bump.

### The near-duplicate third record: `20260802-033728-c24ee3a`

#826's scope note flags this record: it and the re-run predecessor
`20260802-061841-c24ee3a` carry the same claim, the same bench
(`testbench-switching`), the same 135-point grid and the same predecessor
(`20260731-194124-afa338c`), and neither names the other — so the
forward-scan supersession graph reads both as current, and the derivation
keeps both. Comparing them directly settles what the graph cannot: they are
the same bench run twice, ~3 hours apart on 2026-08-02 (03:37 Linux
ngspice-42, then 06:18 Darwin ngspice-46), with per-point agreement of the
same character this document's controls show — steady-state currents to
~0.1 %, `wskew` to a few picoseconds against 4 ns widths. Nothing in either
record qualifies the bench it ran (no bench qualifier in either **Supersedes**
line), which under `sim/README.md`'s supersession language is what makes a
later same-claim/same-grid record a *full* supersession of the earlier one
— the reading already applied to `vco-tuning-range`'s twin pre-migration
records in #826's scope note, and the reading the CHARACTERIZATION caveat
below has stated since #147. **Disposition: `20260802-033728-c24ee3a` is
fully superseded by `20260802-061841-c24ee3a`, which this increment
re-qualified as `20261116-180719-930fb6e`; it is not re-run separately and
no evidence is lost** — its grid adds no corner, axis or measurement the
re-qualified line does not cover. Its bytes are untouched (records are never
edited), and `sim/CHARACTERIZATION.md`'s caveat row now states this reading
explicitly.

## `pfd-deadzone`

Regenerate the operating-point manifest's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/pfd-deadzone/records/20260916-051356-8cedbba.md \
  sim/pfd-deadzone/records/20261116-183811-1379f1f.md
```

### `20261116-183811-1379f1f` vs `20260916-051356-8cedbba`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `q_zero` | — | -8.595610e-15..1.277010e-16 | -8.591680e-15..9.843190e-17 | 3.944580e-16 | 61.11 | `ff_-40c_2.97v_v1p65_d0` |
| `` | `qnet` | — | -1.509050e-14..4.639910e-15 | -1.517520e-14..4.648520e-15 | 3.944580e-16 | 61.11 | `ff_-40c_2.97v_v1p65_d0` |
| `` | `qnet2` | — | -3.018100e-14..9.279830e-15 | -3.035030e-14..9.297040e-15 | 7.889190e-16 | 61.11 | `ff_-40c_2.97v_v1p65_d0` |
| `` | `width_dn` | — | 1.096470e-09..3.616550e-09 | 1.096470e-09..3.616550e-09 | 0 | 0 | `—` |
| `` | `width_up` | — | 1.106300e-09..3.545650e-09 | 1.106300e-09..3.545650e-09 | 5.000000e-14 | 0.002228 | `ff_27c_3.63v_v1p65_d1n` |

**Per-corner verdicts**: unchanged on all 405 graded rows.

**Stated limits**: identical in both records.

`width_dn` is bit-for-bit across all 405 rows and `width_up` moves 50 fs at
one point (0.002 %). The charge rows move by at most 0.39 fC; the 61 %
relative figure is a 0.39 fC move dividing by a 0.6 fC reading near the
integration floor — the denominator artefact again, and the predecessor's own
comparability bullet names exactly this quantity as the one where
simulator/platform differences are visible. The static phase offset the
budget cites is derived from these charges through the dphi axis; its
verdict-bearing structure (the Vctrl dependence, the 36-of-45 count at
0.90 V) rests on ns-scale offsets built from ±200 ps…±1 ns phase steps, four
orders of magnitude above the 0.4 fC residue, and no per-corner verdict
moved.

Regenerate the dead-zone bench's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/pfd-deadzone/records/20260801-234626-5b333d0.md \
  sim/pfd-deadzone/records/20261116-195826-16f19a5.md
```

### `20261116-195826-16f19a5` vs `20260801-234626-5b333d0`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `q_zero` | — | -3.496690e-15..2.971210e-16 | -3.496710e-15..2.971190e-16 | 3.781130e-16 | 54.84 | `ff_-40c_3.30v_d0` |
| `` | `qnet` | — | -1.052870e-14..4.670980e-15 | -1.061400e-14..4.673830e-15 | 2.118400e-16 | 1.647e+04 | `sf_-40c_3.30v_d200p` |
| `` | `qnet2` | — | -2.105750e-14..9.341960e-15 | -2.122800e-14..9.347670e-15 | 4.236600e-16 | 1.647e+04 | `sf_-40c_3.30v_d200p` |
| `` | `width_dn` | — | 1.107980e-09..3.594920e-09 | 1.107980e-09..3.594920e-09 | 0 | 0 | `—` |
| `` | `width_up` | — | 1.106300e-09..3.515240e-09 | 1.106300e-09..3.515240e-09 | 0 | 0 | `—` |
| `` | `wmin_zero` | — | 1.116680e-09..2.583880e-09 | 1.116680e-09..2.583880e-09 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 225 graded rows.

**Stated limits**: identical in both records.

The dead-zone verdict's three quantities hold exactly where it matters:
`width_up`/`width_dn` and the reset delay `wmin_zero` are bit-for-bit across
all 225 rows, so the "both polarities pulse at Δφ = 0" half of the criterion
reproduces exactly. The near/wide gain ratio is differenced from `qnet` at
±200 ps and ±1 ns; those differences are of order 2.5–10 fC against a worst
0.21 fC absolute move (the 1.6e4 % relative figure is that move dividing by
a 1.3e-17 C reading — denominator artefact), so the ratio moves at most a
few percent against its 0.5 threshold, in the direction the ngspice-46
control already measured. This predecessor was already clean-tree; the new
record's provenance is clean at `16f19a59` as well (see What was re-run for
the interrupted session the record was recovered from).

## `vco-bias-current`

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/vco-bias-current/records/20260911-172350-da0bb1e.md \
  sim/vco-bias-current/records/20261117-150323-f3b3e7f.md
```

### `20261117-150323-f3b3e7f` vs `20260911-172350-da0bb1e`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `bias_supply_current` | `ibias_a_hi_ua` | — | 38.4408..490.443 | 38.4408..490.443 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_a_lo_ua` | — | 21.0621..256.401 | 21.0621..256.401 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_a_mid_ua` | — | 29.4061..367.342 | 29.4061..367.342 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_b_hi_ua` | — | 621.848..4240.6 | 621.848..4240.6 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_b_lo_ua` | — | 477.277..2951.99 | 477.277..2951.99 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_b_mid_ua` | — | 544.549..3597.41 | 544.549..3597.41 | 0 | 0 | `—` |
| `bias_supply_current` | `ibias_ratio_mid` | — | 6.13176..31.3217 | 6.13176..31.3217 | 0 | 0 | `—` |
| `reference_point_100mhz` | `ibias_a_100m_ua` | — | 68.7452..195.563 | 68.7452..195.563 | 0 | 0 | `—` |
| `reference_point_100mhz` | `ibias_b_100m_ua` | — | 970.396..2163.37 | 970.396..2163.37 | 0 | 0 | `—` |
| `reference_point_100mhz` | `ibias_ratio_100m` | min=5 | 7.38269..20.3571 | 7.38269..20.3571 | 0 | 0 | `—` |
| `reference_point_100mhz` | `iring_a_100m_ua` | — | 95.5004..242.131 | 95.5004..242.131 | 0 | 0 | `—` |
| `reference_point_100mhz` | `iring_b_100m_ua` | — | 997.509..1987.86 | 997.509..1987.86 | 0 | 0 | `—` |
| `reference_point_100mhz` | `itail_a_100m_ua` | — | 19.1001..48.4262 | 19.1001..48.4262 | 0 | 0 | `—` |
| `reference_point_100mhz` | `itail_b_100m_ua` | — | 199.502..397.572 | 199.502..397.572 | 0 | 0 | `—` |
| `reference_point_100mhz` | `ivco_a_100m_ua` | — | 164.246..435.63 | 164.246..435.63 | 0 | 0 | `—` |
| `reference_point_100mhz` | `ivco_b_100m_ua` | min=318 | 1995.48..4131.46 | 1995.48..4131.46 | 0 | 0 | `—` |
| `ring_stage_bias` | `ihead_a_mid_ua` | — | 1.83117..131.519 | 1.83117..131.519 | 0 | 0 | `—` |
| `ring_stage_bias` | `ihead_b_mid_ua` | — | 17.6784..998.44 | 17.6784..998.44 | 0 | 0 | `—` |
| `ring_stage_bias` | `iring_a_mid_ua` | — | 8.34948..634.504 | 8.34948..634.504 | 0 | 0 | `—` |
| `ring_stage_bias` | `iring_b_mid_ua` | — | 85.3342..5219.51 | 85.3342..5219.51 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_a_hi_ua` | — | 2.34834..175.256 | 2.34834..175.256 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_a_lo_ua` | — | 1.05398..82.3828 | 1.05398..82.3828 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_a_mid_ua` | min=1 | 1.6699..126.901 | 1.6699..126.901 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_b_hi_ua` | — | 22.7765..1312.32 | 22.7765..1312.32 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_b_lo_ua` | — | 12.2098..801.869 | 12.2098..801.869 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_b_mid_ua` | — | 17.0668..1043.9 | 17.0668..1043.9 | 0 | 0 | `—` |
| `ring_stage_bias` | `itail_ratio_mid` | — | 5.97699..12.1532 | 5.97699..12.1532 | 0 | 0 | `—` |
| `ring_stage_bias` | `vbn_a_mid` | — | 0.501466..1.22222 | 0.501466..1.22222 | 0 | 0 | `—` |
| `ring_stage_bias` | `vbn_b_mid` | — | 0.695053..2.82603 | 0.695053..2.82603 | 0 | 0 | `—` |
| `ring_stage_bias` | `vbp_a_mid` | — | 1.57714..3.01696 | 1.57714..3.01696 | 0 | 0 | `—` |
| `ring_stage_bias` | `vbp_b_mid` | — | 0.646034..2.7779 | 0.646034..2.7779 | 0 | 0 | `—` |
| `witness_resistors` | `r3k_cg` | — | 11918.4..25639.5 | 11918.4..25639.5 | 0 | 0 | `—` |
| `witness_resistors` | `r3k_off` | — | 68117.3..1.466257e+05 | 68117.3..1.466257e+05 | 0 | 0 | `—` |
| `witness_resistors` | `rsh_ratio` | min=5 | 6.78009..9.71496 | 6.78009..9.71496 | 0 | 0 | `—` |
| `witness_resistors` | `ru_cg` | — | 1757.85..2639.18 | 1757.85..2639.18 | 0 | 0 | `—` |
| `witness_resistors` | `ru_off` | — | 9825.98..14872.4 | 9825.98..14872.4 | 0 | 0 | `—` |

**Per-corner verdicts**: unchanged on all 936 graded rows.

**Stated limits**: identical in both records.

Every graded row of all 936 is bit-for-bit: the comparator's abs-delta
column reads 0 on all 36 measurements, no per-corner verdict moved, and the
stated limits are identical. The new record ran on 189 batch execution
hosts under `f6eeac7` with the fleet's shared `Simulator init` fingerprint
(`sha256:d6efd5b2…`, 234/234 points) and discloses `Executing simulator:
unattributed (234)` — this deck prints no version banner, so ngspice-47
there is the image's, fingerprint-inferred, the same disclosure class as the
two `cp-compliance` grids. Its predecessor's values are nonetheless
reproduced to the last printed digit by the ngspice-46 and ngspice-42
controls above, one variable at a time, so the bit-for-bit result is
attributed rather than assumed: nothing on this bench moves across the
re-pin, the 46→47 bump or the backend. 42 of the 234 points were simulated
by the capacity-aborted first submission and adopted from the fleet
artifact store by grid fingerprint (each fetched object sha256-verified);
the record's own Artifact-adopted-points field discloses the split and the
source attempt.

The claim's verdict structure is unchanged at every corner: the measured
3k/unmarked ratio at the drawn RCG geometry stays 6.78–9.72× (8.30× at
typical/27 °C/3.30 V, against its min=5 floor), the counterfactual
as-drawn-350 arm still exceeds the ratified 318 µA `vdd_vco` domain current
at every point of the grid on its own (`ivco_b_100m_ua` min 1995.48 µA,
7.4–20.4× the as-specified arm's 68.7–195.6 µA), and the as-specified arm's
per-stage starving current stays 19.1–48.4 µA at the 100 MHz reference
point. The record's Layout-fix reading (#381) carries over unchanged.

## `output-range`

Two single-point records, one per predecessor — and on both pairs the
comparator's shared-measurement intersection is **empty**: both predecessors
are narrative investigation records whose result tables predate the
corner-id schema `sim/lib/record_delta.py` parses (one `| Edge | … |` summary
row, one CAPPED row plus a labelled diagnostic), so the intersection of
parseable `(topology, measurement)` keys is zero and the generator prints
its explicit coverage-differs form. That empty output is the generated
table, verbatim, below; the informative comparison is then assembled by hand
from the two records' own quoted rows — the values are the records', not a
re-analysis. Both new records carry the same DUT export, stimulus fragment
and composed SHA-256 as the already-landed `20261111-184929-73837b9` grid
record (`a7daa6a7…` / `76ccb9e9…` / `99a55608…`), so the like-for-like
reference at this bench's current DUT generation is that grid — which is
also the full-matrix record under the re-pinned PDK, deliberately not
re-taken here (each new record's subset justification says so).

Regenerate the lo-edge pair's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/output-range/records/20260801-061907-67d7127.md \
  sim/output-range/records/20261117-174557-327ee00.md
```

### `20261117-174557-327ee00` vs `20260801-061907-67d7127`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|

**Per-corner verdicts**: unchanged on all 0 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261117-174557-327ee00` only: `headroom`/`vctrl_final`
- in `20261117-174557-327ee00` only: `headroom`/`vctrl_margin_hi_v`
- in `20261117-174557-327ee00` only: `headroom`/`vctrl_margin_lo_v`
- in `20261117-174557-327ee00` only: `integration`/`dn_lvl`
- in `20261117-174557-327ee00` only: `lock`/`lock_at_end`
- in `20261117-174557-327ee00` only: `lock`/`pass_lock`

The predecessor's single measured row (its own Result table, quoted): `lo`
edge, 10 MHz, band 1, N=8 — **FAIL** (lock not asserted in the 2 µs window),
`vctrl_final` **2.1116 V**, on the bench's pre-#159 assembled DUT under
`c6d73a3`, ngspice-46 on Darwin arm64. The new record's row: **FAIL**,
`vctrl_final` **1.70267 V**, `dn_lvl` -3.605620e-07 V (guard SUSPECT), on
the current `pll_top` DUT under `f6eeac7`, ngspice-47 on the batch fleet.

**The 409 mV old-vs-new movement is the DUT migration, not the re-pin**, and
saying so is the whole attribution: the predecessor chain itself changed DUT
between 2026-08-01 and 2026-08-19 (the assembled closed loop was replaced by
the `pll_top` schematic export, #159/#164; `sim/CHARACTERIZATION.md`'s
output-range row has said "not netlist-for-netlist comparable" since), so
the predecessor's 2.1116 V has no same-DUT successor to delta against. The
like-for-like comparison at the current DUT is the one that isolates the
re-pin, and it is sub-tolerance three ways: baseline grid row 1.703 V
(`c6d73a3`, same DUT generation) → grid record 1.70267 V (`f6eeac7`, fleet
ngspice-46) → this record 1.70267 V (`f6eeac7`, fleet ngspice-47), the last
two **identical to the last printed digit**, with the ngspice-46 and -42
controls above reproducing 1.70267 bit-for-bit as well. The verdict is FAIL
in both records; the acquisition-trajectory diagnosis (persistently
one-sided UP assertion raising `vctrl` from the seed toward the 10 MHz
operating point) is not re-derived here — the harness form does not carry
the predecessor's `waveform.csv` capture (#878 dropped it; its reduction
never read it), and that narrative stays with the predecessor, as the
successor's own claim field states.

Regenerate the CAPPED-row pair's table with:

```bash
python3 sim/lib/record_delta.py \
  sim/output-range/records/20260819-190341-70a4128.md \
  sim/output-range/records/20261117-174951-33cbd72.md
```

### `20261117-174951-33cbd72` vs `20260819-190341-70a4128`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|

**Per-corner verdicts**: unchanged on all 0 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261117-174951-33cbd72` only: `headroom`/`vctrl_final`
- in `20261117-174951-33cbd72` only: `headroom`/`vctrl_margin_hi_v`
- in `20261117-174951-33cbd72` only: `headroom`/`vctrl_margin_lo_v`
- in `20261117-174951-33cbd72` only: `integration`/`dn_lvl`
- in `20261117-174951-33cbd72` only: `lock`/`lock_at_end`
- in `20261117-174951-33cbd72` only: `lock`/`pass_lock`

The predecessor reported **no measurement at this point**: its campaign row
is `CAPPED` under a reproducible 2400 s wall-clock budget — a budget
termination of a trajectory whose transient stopped advancing at
t = 1.7328 ns, which that record is explicit is "not a verdict at all" —
plus a labelled diagnostic at seed +1e-7 V that completed: `vctrl_final`
**1.4565 V**, mean DN **0.0339 V**, **FAIL**, DN guard **PASS**, 173.5 CPU-s.
The new record runs the grid's own seed (1.454 V, not the perturbed one) at
the same point and **completes**: `vctrl_final` **1.45651 V**, `dn_lvl`
**0.0339103 V**, **FAIL**, DN guard **PASS**, 146.5 s wall on the fleet.

That is the increment's headline, and it is stronger than a delta table:
**the completed grid-seed trajectory under `f6eeac7` lands on the
predecessor's completed perturbed-seed trajectory** — 20 µV apart on
`vctrl_final`, identical to the diagnostic's four printed digits on `dn_lvl`
— which is the predecessor's own attribution (the stall was one
hypersensitive solver trajectory, escaped by a perturbation below the
simulator's own tolerance) now confirmed from the re-pin's side. Against the
like-for-like sources at the grid seed: the 20261111 grid row reads
1.4569 V / 0.0322125 V (fleet ngspice-46), the local controls read
1.4569 V / 0.0322125 V (ngspice-46) and 1.45686 V / 0.0325038 V
(ngspice-42); this record's 1.45651 V sits 0.39 mV from the farthest of
them, inside the 5 mV row tolerance, verdict and guard unchanged
everywhere. The `lock_at_end` samples differ at the nanovolt scale across
backends (-6.09e-09 V here, 2.12e-08 V on the local 46 control) — both read
as lock low at the end of the window, `t_lock_last_rise` not measured in
either, so the FAIL verdict is the same non-event on both sides. **CAPPED →
FAIL is not a verdict flip**: the predecessor asserts this explicitly about
its own row, and no tolerance moved, so there is nothing to file.

## `vco-tuning-range`

Two of the directory's eight live records are re-qualified in this
increment — the two harness-form benches. The remaining six (the
band-select-mirror Monte Carlo family: `20260817-143524-0e9cfc9`,
`20260923-084925-1655e11`, `20260927-081930-d004d5b`,
`20260927-094524-b994116`, `20260927-214737-546a397`,
`20260927-220631-546a397`) stay owed under #826 as a separate increment:
they are per-seed Monte Carlo campaigns whose runner is deliberately a raw
`sim/lib/simenv.sh` deck (`testbench/run_mismatch.sh`'s own header records
why a harness manifest cannot express them), so re-running them is not this
increment's batch-manifest path and needs its own campaign plan.

### Tuning grid

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/vco-tuning-range/records/20260804-162735-72883fb.md \
  sim/vco-tuning-range/records/20261118-021803-deb4ec0.md
```

### `20261118-021803-deb4ec0` vs `20260804-162735-72883fb`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `` | `f1` | min=1.000000e+05, min_spread_pct=50 | 2.957680e+06..2.749280e+08 | 2.957550e+06..2.749280e+08 | 17400 | 0.1183 | `sf_-40c_3.63v_band0` |
| `` | `f2` | — | 3.473630e+06..3.349450e+08 | 3.472820e+06..3.349450e+08 | 82900 | 0.3006 | `all-fast_27c_3.30v_band3` |
| `` | `f3` | — | 4.041550e+06..3.968140e+08 | 4.040440e+06..3.968140e+08 | 34800 | 0.2423 | `ss_125c_2.97v_band0` |
| `` | `f4` | — | 4.626740e+06..4.585300e+08 | 4.624450e+06..4.585300e+08 | 66900 | 0.3148 | `all-slow_27c_3.63v_band3` |
| `` | `f5` | — | 5.228220e+06..5.189070e+08 | 5.231170e+06..5.189070e+08 | 4.910000e+05 | 0.4599 | `fs_-40c_2.97v_band5` |
| `` | `f6` | — | 5.841090e+06..5.767760e+08 | 5.840800e+06..5.767760e+08 | 1.940800e+06 | 11.02 | `all-fast_27c_3.30v_band1` |
| `` | `f7` | min=1.000000e+05, min_spread_pct=50 | 6.461800e+06..6.319790e+08 | 6.456310e+06..6.319790e+08 | 1.988000e+05 | 0.819 | `ss_-40c_3.30v_band0` |
| `` | `fine_ratio` | — | 2.00211..2.6997 | 2.00211..2.6997 | 0.01767 | 0.827 | `ss_-40c_3.30v_band0` |
| `` | `i1` | — | 2.801730e-05..0.000479448 | 2.838100e-05..0.000479448 | 1.402100e-06 | 2.507 | `sf_27c_2.97v_band1` |
| `` | `i2` | — | 3.089600e-05..0.000552466 | 3.092610e-05..0.000552466 | 2.254200e-06 | 4.337 | `ff_-40c_3.30v_band0` |
| `` | `i3` | — | 3.435280e-05..0.000632157 | 3.396410e-05..0.000632157 | 1.949600e-06 | 3.035 | `sf_-40c_3.30v_band1` |
| `` | `i4` | — | 3.770920e-05..0.00070958 | 3.746200e-05..0.00070958 | 2.301500e-06 | 3.003 | `ff_27c_3.63v_band0` |
| `` | `i5` | — | 4.153340e-05..0.000790093 | 4.116610e-05..0.000790093 | 2.325000e-06 | 2.243 | `ff_-40c_3.63v_band2` |
| `` | `i6` | — | 4.479740e-05..0.00086893 | 4.486190e-05..0.00086893 | 3.219700e-06 | 3.325 | `ff_-40c_3.63v_band1` |
| `` | `i7` | — | 4.862400e-05..0.000947912 | 4.835320e-05..0.000947912 | 2.696000e-06 | 2.205 | `ff_-40c_3.63v_band2` |
| `` | `k1` | — | 1.719833e+06..2.000567e+08 | 1.717567e+06..2.000567e+08 | 2.580000e+05 | 1.682 | `all-fast_27c_3.30v_band3` |
| `` | `k2` | — | 1.806450e+06..2.031433e+08 | 1.804817e+06..2.031433e+08 | 91000 | 0.7776 | `all-fast_27c_3.30v_band2` |
| `` | `k3` | — | 1.921850e+06..2.059750e+08 | 1.919383e+06..2.059750e+08 | 1.126670e+05 | 1.244 | `all-slow_27c_3.63v_band3` |
| `` | `k4` | — | 1.977783e+06..2.034883e+08 | 1.984550e+06..2.034883e+08 | 7.235000e+05 | 1.781 | `all-fast_-40c_2.97v_band0` |
| `` | `k5` | — | 2.023917e+06..1.990167e+08 | 2.027250e+06..1.990167e+08 | 3.248000e+06 | 51.51 | `all-fast_27c_3.30v_band1` |
| `` | `k6` | — | 2.055967e+06..1.963800e+08 | 2.041900e+06..1.963800e+08 | 4.571700e+05 | 4.451 | `ss_-40c_3.30v_band0` |
| `` | `k7` | — | 1.868800e+06..1.947033e+08 | 1.623400e+06..1.947033e+08 | 6.401330e+06 | 98.6 | `all-fast_27c_3.30v_band1` |
| `` | `kvco_max` | — | 2.069033e+06..2.059750e+08 | 2.051700e+06..2.059750e+08 | 6.401330e+06 | 98.6 | `all-fast_27c_3.30v_band1` |
| `` | `kvco_mean` | — | 1.946733e+06..1.983617e+08 | 1.943756e+06..1.983617e+08 | 1.087200e+05 | 1.546 | `ss_-40c_3.30v_band0` |
| `` | `kvco_min` | — | 1.719833e+06..1.840100e+08 | 1.623400e+06..1.840100e+08 | 2.599733e+06 | 45.95 | `all-fast_27c_3.30v_band1` |
| `` | `kvco_over_f_max` | — | 0.558088..0.837653 | 0.558028..0.837653 | 0.011067 | 1.657 | `all-fast_27c_3.30v_band3` |
| `` | `sw1hi` | min=2.6 | 2.98137..3.78425 | 2.98372..3.7864 | 0.07121 | 1.894 | `ff_-40c_3.63v_band6` |
| `` | `sw1lo` | max=0.3 | -0.167821..-0.0114043 | -0.174464..-0.016998 | 0.0816104 | 429 | `ff_125c_3.63v_band6` |
| `` | `sw7hi` | min=2.6 | 2.99847..3.81011 | 2.99847..3.81846 | 0.05986 | 1.745 | `ss_27c_3.30v_band5` |
| `` | `sw7lo` | max=0.3 | -0.208826..-0.0298282 | -0.218849..-0.0298283 | 0.06323 | 64.81 | `all-fast_-40c_3.30v_band7` |
| `` | `tp1` | — | 1.454930e-08..1.352410e-06 | 1.454930e-08..1.352470e-06 | 1.300000e-09 | 0.1178 | `sf_-40c_3.63v_band0` |
| `` | `tp2` | — | 1.194230e-08..1.151530e-06 | 1.194230e-08..1.151800e-06 | 1.032000e-09 | 0.2999 | `all-fast_27c_3.30v_band3` |
| `` | `tp3` | — | 1.008030e-08..9.897190e-07 | 1.008030e-08..9.899920e-07 | 1.366000e-09 | 0.2428 | `ss_125c_2.97v_band0` |
| `` | `tp4` | — | 8.723530e-09..8.645390e-07 | 8.723530e-09..8.649670e-07 | 8.790000e-10 | 0.314 | `all-slow_27c_3.63v_band3` |
| `` | `tp5` | — | 7.708510e-09..7.650780e-07 | 7.708510e-09..7.646480e-07 | 1.181000e-09 | 0.4582 | `fs_-40c_2.97v_band5` |
| `` | `tp6` | — | 6.935100e-09..6.848040e-07 | 6.935100e-09..6.848370e-07 | 2.813200e-08 | 12.39 | `all-fast_27c_3.30v_band1` |
| `` | `tp7` | — | 6.329320e-09..6.190230e-07 | 6.329320e-09..6.195490e-07 | 3.856000e-09 | 0.8258 | `ss_-40c_3.30v_band0` |

**Per-corner verdicts**: unchanged on all 504 graded rows.

**Stated limits**: identical in both records.

The band-1 outlier rows (`f6`, `tp6`, `k5`/`k7`, `kvco_min`/`kvco_max`) are
all the same curve — `all-fast/27c_3.30v_band1` — through the check-5
inversion dispositioned as #1059. "Row" below means a table row — one
metric's maximum across the grid — not a single grid point: this table
reports per-metric maxima, not per-point movement. Outside the band-1
outliers the largest movers are the two swing-low buffer rails, `sw1lo`
(429 % relative at `ff_125c_3.63v_band6`) and `sw7lo` (64.81 % at
`all-fast_-40c_3.30v_band7`): both rails sit near zero, so a relative
figure there measures the floor, not the signal — in absolute terms they
move 0.0816 V and 0.0632 V against their `max=0.3` V limit, ≈27 % and
≈21 % of the limit budget, verdicts unchanged. Every other row of the
grid moved ≤ 4.46 % relative (`k6` 4.451 % at `ss_-40c_3.30v_band0`, then
`i2` 4.337 % and `i6` 3.325 %, with the other current, gain and swing-high
rows between 1.2 % and 3.1 % and the frequency/period rows ≤ 0.83 %), with
the predecessor a Darwin arm64 record and the PDK excluded by the controls
above. Check 4b's FAIL is not a flip: the
predecessor already read 154.4 MHz/V at the same adversarial
all-fast/27C/3.30V B7 point, and the new record's own caveat field carries
the same reading.

### Supply bench

Regenerate with:

```bash
python3 sim/lib/record_delta.py \
  sim/vco-tuning-range/records/20260804-211600-f599a65.md \
  sim/vco-tuning-range/records/20261118-023753-1b6f7c2.md
```

### `20261118-023753-1b6f7c2` vs `20260804-211600-f599a65`

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `jit` | `floor_margin_x` | min=10 | 135.148..2010.12 | 130.39..1893 | 197.344 | 76.75 | `typical_27c_3.30v_band5_r4_f100` |
| `jit` | `jfrip` | — | 2.829420e+05..2.883600e+07 | 2.829420e+05..2.883600e+07 | 0 | 0 | `—` |
| `jit` | `jsettle` | — | 1.415320e-08..1.325360e-06 | 1.415320e-08..1.325360e-06 | 0 | 0 | `—` |
| `jit` | `jstepon` | — | 8.963680e-08..8.393950e-06 | 8.963680e-08..8.393950e-06 | 0 | 0 | `—` |
| `jit` | `quiet_c2c_rms_s` | — | 1.780474e-13..2.161974e-11 | 1.835019e-13..2.257353e-11 | 2.012340e-12 | 31.03 | `sf_125c_2.97v_band5_r16_f100` |
| `jit` | `quiet_cycles` | min=32 | 42..123 | 42..123 | 0 | 0 | `—` |
| `jit` | `quiet_f_hz` | — | 5.064372e+06..4.036127e+08 | 5.064336e+06..4.036129e+08 | 400 | 0.000717 | `all-fast_-40c_3.30v_band0_r16_f125` |
| `jit` | `quiet_tie_pp_s` | — | 6.273077e-13..1.352343e-10 | 6.721718e-13..1.341797e-10 | 1.457336e-11 | 51.35 | `all-slow_27c_3.30v_band5_r4_f080` |
| `jit` | `quiet_tie_rms_s` | — | 1.547741e-13..2.558384e-11 | 1.464496e-13..2.842967e-11 | 3.782765e-13 | 43.42 | `typical_27c_3.30v_band5_r4_f100` |
| `jit` | `quiet_tj_pp_s` | — | 4.189079e-13..8.148669e-11 | 5.177383e-13..9.063275e-11 | 1.057691e-12 | 47.65 | `typical_27c_3.63v_band5_r16_f100` |
| `jit` | `quiet_tj_rms_s` | — | 1.146220e-13..1.715074e-11 | 1.164988e-13..1.815519e-11 | 1.104950e-12 | 26.85 | `all-fast_125c_3.30v_band5_r16_f125` |
| `jit` | `rip_c2c_rms_s` | — | 1.550078e-11..1.173484e-09 | 1.549715e-11..1.173396e-09 | 3.425000e-13 | 0.05833 | `typical_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_cycles` | min=32 | 43..123 | 43..123 | 0 | 0 | `—` |
| `jit` | `rip_f_hz` | — | 5.066246e+06..4.036023e+08 | 5.066281e+06..4.036023e+08 | 500 | 0.0008713 | `ss_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_tie_pp_pred_s` | — | 2.027070e-10..1.700522e-08 | 2.026893e-10..1.699767e-08 | 6.400000e-12 | 0.0569 | `sf_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_tie_pp_s` | — | 2.775337e-10..2.092688e-08 | 2.774209e-10..2.092330e-08 | 1.556000e-11 | 0.1259 | `all-fast_-40c_3.30v_band0_r16_f125` |
| `jit` | `rip_tie_rms_s` | — | 9.300987e-11..6.527032e-09 | 9.300529e-11..6.523197e-09 | 3.155000e-12 | 0.07012 | `typical_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_tj_pp_pred_s` | — | 8.361047e-11..5.969443e-09 | 8.360318e-11..5.966836e-09 | 2.312000e-12 | 0.05627 | `sf_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_tj_pp_s` | — | 1.085676e-10..6.501042e-09 | 1.085516e-10..6.492177e-09 | 3.585000e-12 | 0.2742 | `ss_27c_3.30v_band7_r16_f100` |
| `jit` | `rip_tj_rms_pct` | — | 0.867437..3.23505 | 0.867292..3.23548 | 0.00055 | 0.05468 | `typical_-40c_3.30v_band0_r16_f100` |
| `jit` | `rip_tj_rms_s` | — | 3.849601e-11..2.309306e-09 | 3.849408e-11..2.308856e-09 | 8.850000e-13 | 0.05444 | `typical_-40c_3.30v_band0_r16_f100` |
| `jit` | `step_df_hz` | — | -1.362042e+07..-1.371294e+05 | -1.361924e+07..-1.370832e+05 | 910 | 0.05748 | `sf_-40c_3.30v_band0_r16_f100` |
| `jit` | `step_f_post_hz` | — | 4.911273e+06..3.899964e+08 | 4.911292e+06..3.899977e+08 | 600 | 0.0009961 | `typical_-40c_3.30v_band0_r16_f100` |
| `jit` | `step_f_pre_hz` | — | 5.064376e+06..4.036169e+08 | 5.064326e+06..4.036170e+08 | 1200 | 0.0009873 | `all-slow_-40c_3.30v_band0_r16_f080` |
| `jit` | `step_kvdd_hz_per_v` | — | -1.362042e+08..-1.371294e+06 | -1.361924e+08..-1.370832e+06 | 9100 | 0.05748 | `sf_-40c_3.30v_band0_r16_f100` |
| `jit` | `step_tie_per_us_s` | — | -6.076885e-08..-2.235348e-08 | -6.076488e-08..-2.234603e-08 | 1.412000e-11 | 0.05649 | `sf_-40c_3.30v_band0_r16_f100` |
| `push` | `f1` | — | 5.746860e+06..4.584100e+08 | 5.743620e+06..4.584100e+08 | 3.770000e+05 | 0.3235 | `all-slow_-40c_3.30v_band4_r16_f080` |
| `push` | `f2` | — | 5.490450e+06..4.395430e+08 | 5.488340e+06..4.395430e+08 | 1.650500e+06 | 1.855 | `all-slow_125c_2.97v_band5_r16_f080` |
| `push` | `f3` | — | 5.256650e+06..4.210870e+08 | 5.259040e+06..4.210870e+08 | 2.590000e+05 | 2.52 | `sf_27c_3.30v_band0_r16_f100` |
| `push` | `f4` | min=1.000000e+05, min_spread_pct=50 | 5.073200e+06..4.035060e+08 | 5.068260e+06..4.035060e+08 | 4.479000e+05 | 1.113 | `fs_27c_3.30v_band0_r16_f100` |
| `push` | `f5` | — | 4.886320e+06..3.867860e+08 | 4.880770e+06..3.867860e+08 | 1.369300e+06 | 2.304 | `all-slow_-40c_2.97v_band5_r16_f080` |
| `push` | `f6` | — | 4.757680e+06..3.711660e+08 | 4.760380e+06..3.711660e+08 | 1.050000e+05 | 0.2821 | `ss_27c_3.30v_band0_r16_f100` |
| `push` | `f7` | — | 4.626680e+06..3.565950e+08 | 4.619940e+06..3.565950e+08 | 1.600000e+05 | 0.2583 | `fs_-40c_3.30v_band0_r16_f100` |
| `push` | `i1` | — | 3.799700e-05..0.000653237 | 3.787080e-05..0.000653237 | 1.197000e-06 | 2.023 | `typical_-40c_3.30v_band0_r16_f100` |
| `push` | `i2` | — | 3.901990e-05..0.000661283 | 3.869730e-05..0.000661283 | 1.723300e-06 | 2.888 | `ss_27c_3.30v_band0_r16_f100` |
| `push` | `i3` | — | 4.004930e-05..0.000675351 | 4.054940e-05..0.000675351 | 2.219300e-06 | 2.58 | `all-slow_-40c_3.30v_band4_r16_f080` |
| `push` | `i4` | — | 4.109920e-05..0.000682673 | 4.046040e-05..0.000682673 | 2.349300e-06 | 4.245 | `fs_-40c_3.30v_band0_r16_f100` |
| `push` | `i5` | — | 4.353630e-05..0.000688741 | 4.336560e-05..0.000688741 | 2.411400e-06 | 4.14 | `sf_-40c_3.30v_band0_r16_f100` |
| `push` | `i6` | — | 4.453860e-05..0.000702994 | 4.518520e-05..0.000702994 | 3.480600e-06 | 5.433 | `ff_-40c_3.30v_band0_r16_f100` |
| `push` | `i7` | — | 4.498090e-05..0.000708702 | 4.466170e-05..0.000708702 | 3.835900e-06 | 4.998 | `ff_27c_3.30v_band0_r16_f100` |
| `push` | `push_f_nom_hz` | — | 5.073200e+06..4.035060e+08 | 5.068260e+06..4.035060e+08 | 4.479000e+05 | 1.113 | `fs_27c_3.30v_band0_r16_f100` |
| `push` | `push_i_nom_a` | — | 4.109920e-05..0.000682673 | 4.046040e-05..0.000682673 | 2.349300e-06 | 4.245 | `fs_-40c_3.30v_band0_r16_f100` |
| `push` | `push_nl_pct` | max=5 | 0.148398..3.41401 | 0.127758..2.62913 | 1.54161 | 141.8 | `sf_27c_3.30v_band0_r16_f100` |
| `push` | `push_norm_pct_per_v` | max=0 | -54.5388..-24.1067 | -54.5913..-24.0205 | 0.9619 | 3.433 | `sf_27c_3.30v_band0_r16_f100` |
| `push` | `push_slope_hz_per_v` | — | -1.547078e+08..-1.477299e+06 | -1.547078e+08..-1.473643e+06 | 4.767000e+05 | 3.297 | `sf_27c_3.30v_band0_r16_f100` |
| `push` | `tp1` | — | 8.725800e-09..6.960320e-07 | 8.725800e-09..6.964250e-07 | 1.108000e-09 | 0.3245 | `all-slow_-40c_3.30v_band4_r16_f080` |
| `push` | `tp2` | — | 9.100360e-09..7.285380e-07 | 9.100360e-09..7.288180e-07 | 1.413000e-09 | 1.89 | `all-slow_125c_2.97v_band5_r16_f080` |
| `push` | `tp3` | — | 9.499220e-09..7.609400e-07 | 9.499220e-09..7.605950e-07 | 1.555100e-08 | 2.585 | `sf_27c_3.30v_band0_r16_f100` |
| `push` | `tp4` | — | 9.913110e-09..7.884570e-07 | 9.913110e-09..7.892250e-07 | 6.785000e-09 | 1.126 | `fs_27c_3.30v_band0_r16_f100` |
| `push` | `tp5` | — | 1.034160e-08..8.186120e-07 | 1.034160e-08..8.195420e-07 | 8.064000e-09 | 2.252 | `all-slow_-40c_2.97v_band5_r16_f080` |
| `push` | `tp6` | — | 1.077690e-08..8.407460e-07 | 1.077690e-08..8.402700e-07 | 1.798000e-09 | 0.2814 | `ss_27c_3.30v_band0_r16_f100` |
| `push` | `tp7` | — | 1.121720e-08..8.645510e-07 | 1.121720e-08..8.658120e-07 | 1.775000e-09 | 0.2576 | `fs_-40c_3.30v_band0_r16_f100` |

**Per-corner verdicts**: unchanged on all 288 graded rows.

**Stated limits**: identical in both records.
