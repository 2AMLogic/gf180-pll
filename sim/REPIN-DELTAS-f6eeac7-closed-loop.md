# Re-pin deltas: closed-loop campaigns under open_pdks `f6eeac7`

`sim/` evidence is append-only, so re-qualifying a frozen reference record
after a PDK pin change mints a *new* record that names the old one in
**Supersedes** (`sim/README.md`, "Status / supersession language"). This
document records *how much the numbers moved*. It covers the closed-loop
group of the #790 re-qualification (#828), the fleet re-pin
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` → `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(pinned by #789). Siblings:
[`REPIN-DELTAS-f6eeac7-devchar.md`](REPIN-DELTAS-f6eeac7-devchar.md),
[`REPIN-DELTAS-f6eeac7-vco-output-cp-pfd.md`](REPIN-DELTAS-f6eeac7-vco-output-cp-pfd.md),
[`REPIN-DELTAS-f6eeac7-lock-divider.md`](REPIN-DELTAS-f6eeac7-lock-divider.md).

The group is 29 cited records across seven directories and lands as
per-directory increments, each `Part of #828`. Nothing here edits a record.

| directory | live records | disposition |
|---|---|---|
| `reference-spur` | `20260816-132150-5f405e7` | **re-qualified here** (`20261118-212630-1649033`) |
| `reference-phase-transfer` | 3 | **re-qualified here** ([`20261120-151718-d0000b5`](reference-phase-transfer/records/20261120-151718-d0000b5.md)) |
| `period-jitter` | 6 | **re-qualified here** ([`20261121-184803-04533bf`](period-jitter/records/20261121-184803-04533bf.md)) |
| `supply-sensitivity` | 12 | still owed under #828 |
| `lock-time` | 5 | still owed under #828 |
| `pll-top-smoke` | `20260802-160926-8456ff3` | **re-qualified** ([`20261120-025417-fe7841e`](pll-top-smoke/records/20261120-025417-fe7841e.md)) |
| `loop-dynamics` | `20260731-202550-82af5a9` | **provenance-verified here** ([`20261111-092132-343bafa`](loop-dynamics/records/20261111-092132-343bafa.md)) |

## `reference-spur`

Five-point non-rectangular grid, the same manifest, deck and settings as the
predecessor, run on the `batch` backend (5 jobs, 5/5 ok, open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, ngspice-47 on the fleet image).
A first attempt lost one point to a Spot reclamation and was discarded
uncommitted; the committed record is the complete second run, whose
`typical` point matches the first attempt's to every printed digit.

### What changed besides the PDK

The predecessor was minted on macOS/arm64 with ngspice-46 from a dirty tree.
The re-run differs in the PDK pin, the simulator (46 → 47), the host OS and
the execution backend. This is a closed-loop transient, so the movement below
is **not attributable to the PDK alone**. The deck also carries the
nonlinear-moscap `m=` trigger of #153/#926 (6 instances in the netlist
snapshot: `cap_nmos_03v3_b` x4 in `loop_filter`, `cap_nmos_03v3` x2 in
`vco`), and per #932 a build that loads that family is not evidence that it
returns the same values. The next subsection measures one overlap point.

### Overlap point: ngspice-46 under `f6eeac7`, one corner

```bash
SIM_NGSPICE_BIN=$HOME/.local/opt/ngspice-46/bin/ngspice \
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py reference-spur --backend local \
  --corners typical --temps 27 --supply 3.3 --supply-tol 0 \
  --axis vs=vs1p795 --timeout 1800 --no-write -j 1
```

Same deck, same PDK pin (`f6eeac7`), `typical_27c_3.30v_vs1p795`, 1/1 ok,
**935.3 s wall clock** on this host. A first attempt with the harness's
default 300 s per-point timeout was killed with no output (`TIMEOUT after
300s`), so a local run of this bench needs `--timeout` raised; it is a
single-unit run and was kept local. Not minted as a record (`--no-write`).

| measurement | predecessor (ngspice-46, `c6d73a3`) | ngspice-46, `f6eeac7` | this record (ngspice-47, `f6eeac7`) |
|---|---|---|---|
| `spur_dbc` | -58.36 | -62.01 | -55.95 |
| `spur_dbc_200m` (max -55) | -55.87 PASS | -59.51 PASS | -53.45 **FAIL** |
| `spur_tie_dbc` | -56.13 | -58.12 | -53.94 |
| `spur_dbc_fit` | -57.93 | -57.65 | -56.26 |
| `tie_pk_ps` | 3.313 | 2.634 | 4.264 |
| `phi_a` (s) | 2.84424e-09 | 2.85431e-09 | 2.85737e-09 |
| `fout` (Hz) | 1.50010e+08 | 1.50003e+08 | 1.50003e+08 |
| `ferr` | 1.20245e-04 | 1.39759e-04 | 1.39842e-04 |
| `drift_q_fc` | -1.6016 | -2.3894 | -3.1740 |

Reading, at this one corner and no other:

- The simulator moves `spur_dbc` by **6.06 dB** on an identical deck and PDK
  (ngspice-46 -62.01, ngspice-47 -55.95); the PDK moves it by 3.65 dB in the
  opposite direction (-58.36 -> -62.01 at ngspice-46). The two effects partly
  cancel in the predecessor-to-record comparison, so the headline 2.4 dB
  movement understates both.
- The lock-point columns (`phi_a`, `fout`, `ferr`, `ffb`) agree to better than
  0.3 % between the two simulators; the spur columns do not. The disagreement
  is in the sideband reduction's inputs (`tie_pk_ps` 2.63 vs 4.26 ps), not in
  whether the loop locks.
- The `typical` `spur_dbc_200m` PASS -> FAIL flip below is **a simulator
  effect at this corner**: ngspice-46 under the new PDK reads -59.51 dBc and
  passes. Whether it also holds at the other four corners is not measured.
- This is an overlap point, not an equivalence proof: it shows the batch
  ngspice-47 number is not interchangeable with an ngspice-46 one for this
  campaign, which is the reason DR-028 Decision 3(a) quarantines it. Whether
  that licenses the `Supersedes:` line in the new record is for the Judge and
  the operator; the ratified -55 dBc bound is untouched either way.

### Disposition: a verdict flips, and the bound is not relaxed

The `spur_dbc_200m` check (max −55 dBc, the +2.50 dB scaling of the measured
150 MHz spur to the ratified band's 200 MHz ceiling) was already failing at
two corners in the predecessor. The re-run:

| corner | `spur_dbc_200m` old | new | verdict |
|---|---|---|---|
| `typical_27c_3.30v_vs1p795` | −55.87 (PASS) | −53.45 | **PASS → FAIL** |
| `ff_-40c_3.63v_vs2p430` | −54.88 (FAIL) | −58.42 | FAIL → PASS |
| `sf_-40c_2.97v_vs1p677` | −54.51 (FAIL) | −65.69 | FAIL → PASS |

The worst point at 200 MHz moves from −54.51 to −53.45 dBc, i.e. **1.06 dB
worse**, and moves from a cold corner to the nominal one. At the measured
150 MHz every corner still meets −55 dBc (worst −55.95 dBc, `typical`, only
0.95 dB of margin; previously −57.01). The ratified spec is unchanged; the
shortfall is routed to #1061 rather than absorbed; the overlap point above
answers that issue's control-probe option for the `typical` corner (the flip
there is the simulator, not the PDK) and for no other corner.

### Delta table

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/reference-spur/records/20260816-132150-5f405e7.md \
  sim/reference-spur/records/20261118-212630-1649033.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.109695..0.208863 | 0.109722..0.208717 | 0.000187 | 0.1454 | `sf_-40c_2.97v_vs1p677` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 6.867679e-11..8.529698e-11 | 6.887747e-11..8.525656e-11 | 3.560100e-13 | 0.4841 | `typical_27c_3.30v_vs1p795` |
| `integration` | `up_lvl` | — | 0.202244..0.532161 | 0.191852..0.531656 | 0.010392 | 5.138 | `sf_-40c_2.97v_vs1p677` |
| `lock` | `dphi` | — | -1.244530e-09..2.908310e-10 | -1.218380e-09..3.351610e-10 | 9.955200e-11 | 16.3 | `typical_27c_3.30v_vs1p795` |
| `lock` | `drift_q_fc` | — | -1.60162..2.78074 | -3.17404..2.354 | 1.57242 | 256.4 | `sf_-40c_2.97v_vs1p677` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -5.725010e-05..0.000244986 | -6.597660e-05..0.000239839 | 1.959700e-05 | 16.3 | `typical_27c_3.30v_vs1p795` |
| `lock` | `ffb` | — | 2.498630e+07..2.500870e+07 | 2.498560e+07..2.500830e+07 | 2200 | 0.008799 | `typical_27c_3.30v_vs1p795` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499310e+08..1.500500e+08 | 1.499190e+08..1.500490e+08 | 12000 | 0.008004 | `ff_-40c_3.63v_vs2p430` |
| `lock` | `lock_lvl` | — | 5.126830e-09..2.81545 | 5.126950e-09..2.97 | 0.15455 | 5.489 | `sf_-40c_2.97v_vs1p677` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 5.99982..6.00053 | 5.99985..6.00021 | 0.00032 | 0.005333 | `ff_-40c_3.63v_vs2p430` |
| `lock` | `phi_a` | — | 1.081120e-09..5.035220e-09 | 9.538000e-10..5.013760e-09 | 1.273200e-10 | 11.78 | `sf_-40c_2.97v_vs1p677` |
| `lock` | `phi_b` | — | 8.887930e-10..3.790690e-09 | 7.518890e-10..3.795370e-09 | 1.369040e-10 | 15.4 | `sf_-40c_2.97v_vs1p677` |
| `lock` | `vctrl_ripple_mv` | — | 4.93..7.86764 | 4.90141..7.92154 | 0.0539 | 0.6851 | `ff_-40c_3.63v_vs2p430` |
| `spur` | `carrier_v` | — | 1.8847..2.30526 | 1.88487..2.30565 | 0.00039 | 0.01692 | `ff_-40c_3.63v_vs2p430` |
| `spur` | `fout_edge` | — | 1.500074e+08..1.500299e+08 | 1.500076e+08..1.500252e+08 | 4700 | 0.003133 | `ss_125c_2.97v_vs1p093` |
| `spur` | `spur_dbc` | max=-55 | -72.6594..-57.0128 | -70.4039..-55.9511 | 11.1754 | 19.6 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `spur_dbc_200m` | max=-55 | -70.1606..-54.5141 | -67.9051..-53.4523 | 11.1753 | 20.5 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `spur_dbc_first` | — | -63.2426..-52.1692 | -65.9341..-52.1428 | 3.8126 | 7.308 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `spur_dbc_fit` | — | -64.847..-57.8113 | -64.3309..-56.2599 | 2.573 | 4.395 | `ff_-40c_3.63v_vs2p430` |
| `spur` | `spur_fit_r2` | — | 0.000540186..0.161665 | 0.00590533..0.533318 | 0.48257 | 993.2 | `ff_-40c_3.63v_vs2p430` |
| `spur` | `spur_lsb_dbc` | — | -72.8403..-57.0128 | -70.4039..-55.9511 | 11.1754 | 19.6 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `spur_tie_dbc` | — | -65.2559..-51.4875 | -62.5288..-53.9366 | 7.5367 | 14.64 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `spur_usb_dbc` | — | -72.6594..-57.4456 | -70.8633..-56.0566 | 13.4177 | 23.36 | `sf_-40c_2.97v_vs1p677` |
| `spur` | `tie_pk_ps` | — | 1.15854..5.65392 | 1.5858..4.26439 | 3.2797 | 74.02 | `fs_125c_3.63v_vs1p791` |
| `ungrouped` | `tclk160` | — | 1.066310e-06..1.067160e-06 | 1.066320e-06..1.067240e-06 | 8.000000e-11 | 0.007497 | `ff_-40c_3.63v_vs2p430` |
| `ungrouped` | `tfb20` | — | 7.997220e-07..8.004370e-07 | 7.997350e-07..8.004600e-07 | 7.200000e-11 | 0.009001 | `typical_27c_3.30v_vs1p795` |

**Per-corner verdict flips** (each one is a finding):

| topology | corner-id | old | new |
|---|---|---|---|
| `spur` | `ff_-40c_3.63v_vs2p430` | FAIL — spur_dbc_200m max=-55 (got -54.8808) | PASS |
| `spur` | `sf_-40c_2.97v_vs1p677` | FAIL — spur_dbc_200m max=-55 (got -54.5141) | PASS |
| `spur` | `typical_27c_3.30v_vs1p795` | PASS | FAIL — spur_dbc_200m max=-55 (got -53.4523) |

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261118-212630-1649033` only: `lock`/`ferr_fb`

_3 finding(s) above need a human disposition._

## `reference-phase-transfer`

The paired control/step grid covers 5 of 45 mandated PVT combinations
(2 decks per point, 10 jobs). The re-run used the predecessor's manifest,
deck and settings on the `batch` backend (5/5 points completed, open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` verified from the first
completing job's `SOURCES` stamp before the grid was spent, ngspice-47 on
the fleet image built 2026-11-14). Job ids, one per deck:
`gf180-pll-sim-ctl_typical_27c_3.30v_vs1p795-4ea005e6`,
`gf180-pll-sim-stp_typical_27c_3.30v_vs1p795-e4d49ed7`,
`gf180-pll-sim-ctl_ff_-40c_3.63v_vs2p430-eb0ef707`,
`gf180-pll-sim-stp_ff_-40c_3.63v_vs2p430-cb55b4bb`,
`gf180-pll-sim-ctl_ss_125c_2.97v_vs1p093-4e7c9d84`,
`gf180-pll-sim-stp_ss_125c_2.97v_vs1p093-c2d1e37c`,
`gf180-pll-sim-ctl_fs_125c_3.63v_vs1p791-fe7de866`,
`gf180-pll-sim-stp_fs_125c_3.63v_vs1p791-db768f89`,
`gf180-pll-sim-ctl_sf_-40c_2.97v_vs1p677-8344da86`,
`gf180-pll-sim-stp_sf_-40c_2.97v_vs1p677-8e7e5003`.
A first submission lost its `ss` point to a Spot reclamation and was
discarded uncommitted; the four points it did complete reproduce the
committed run's values to every printed digit.

### What changed besides the PDK

The predecessor's five points executed on the batch image's ngspice-42
(its `Simulator:` bullet named the minting host's ngspice-46, which ran no
deck); this run executed on ngspice-47 — the same simulator transition the
`reference-spur` record above carries. The composed DUT also differs from
the predecessor's frozen snapshot in exactly two lines, both design edits
on `main` that post-date it and that the `reference-spur` re-run's snapshot
already carries: `XCF5` moves from `cap_mim_2f0_m2m3_noshield` to the
option-B `cap_mim_2f0_m4m5_noshield` (same 31.4 µm × 31.4 µm `m=1`
geometry), and `XLD`'s fourth trim pin connects to the `LDT3` port instead
of an internal `net1` (the DR-026 lock-detector MSB connection). The
stimulus deck, solver options, `.tran` line and every measurement card are
unchanged. This is a closed-loop transient, so the movement below is
**not attributable to the PDK alone**.

### Overlap point: pinned ngspice-46 under `f6eeac7`, one corner

```bash
SIM_NGSPICE_BIN=$HOME/.local/opt/ngspice-46/bin/ngspice \
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py reference-phase-transfer --backend local \
  --corners typical --temps 27 --supply 3.3 --supply-tol 0 \
  --axis vs=vs1p795 --timeout 3600 --no-write -j 2
```

Same deck, same PDK pin (`f6eeac7`), `typical_27c_3.30v_vs1p795`, 1/1 ok,
**961.9 s wall clock** on this host, both phases. Not minted as a record
(`--no-write`).

| measurement | predecessor (executing ngspice-42, `c6d73a3`) | ngspice-46, `f6eeac7` | this record (executing ngspice-47, `f6eeac7`) |
|---|---|---|---|
| `measured_gain_db` | 15.8894 | 15.5871 | 15.5326 |
| `transfer_error_db` | 0.3264 | 0.0240 | -0.0305 |
| `phi_shift` (ps) | 38.3 | 2.8 | -3.5 |
| `pair_resid` (ps) | -10.5 | -3.4 | -16.9 |
| `settle_resid` (ps) | 9.1 | -37.5 | -64.6 |
| `tracking_ratio` | 1.03829 | 1.00277 | 0.9965 |
| `fout` (Hz) | 1.500140e+08 | 1.500240e+08 | 1.500220e+08 |
| `nmeas` | 6.00012 | 6.00027 | 6.00035 |

- At `typical`, gain fell from 15.8894 to 15.5871 dB between the
  predecessor and the local overlap. The **0.3023 dB** difference combines
  the PDK change, both DUT netlist edits, ngspice-42 → 46 and the move
  from batch to local execution. The individual contributions remain unknown.
- The local overlap and successor used the same new PDK and DUT netlist.
  Gain fell from 15.5871 to 15.5326 dB, a **0.0545 dB** simulator-plus-host
  difference between local ngspice-46 and batch ngspice-47 at `typical`.
- The operating-point columns (`fout`, `ffb`, `nmeas`) agree to better than
  0.01 % across all three runs. The overlap covers only `typical`.

### Method guards and resolution of the in-band residuals

The record's overall verdict is **FAIL** on the campaign's own
method-validity guards — the first time a `reference-phase-transfer`
record has failed them since DR-027 corrected the `pair_resid` band:

| corner-id | guard | old | new | verdict |
|---|---|---|---|---|
| `ff_-40c_3.63v_vs2p430` | `pair_resid` (±50 ps, DR-027) | 16.5 ps (PASS) | 53.54 ps | **PASS → FAIL** |
| `sf_-40c_2.97v_vs1p677` | `settle_resid` (±100 ps) | -37.7 ps (PASS) | 117.52 ps | **PASS → FAIL** |

The table compares the magnitude of the reported shift at `tb` with the
pre-step pairing floor and with the movement between `tc` and `tb`.

| MOS corner | abs(`phi_shift`) (ps) | abs(`pair_resid`) (ps) | abs(`settle_resid`) (ps) | method guards |
|---|---:|---:|---:|---|
| `typical` | 3.50 | 16.90 | 64.56 | PASS |
| `ff` | 35.00 | 53.54 | 16.62 | FAIL (pairing) |
| `ss` | 5.46 | 13.03 | 56.56 | PASS |
| `fs` | 19.61 | 8.68 | 58.52 | PASS |
| `sf` | 4.77 | 1.80 | 117.52 | FAIL (settling) |

At `typical`, `ff` and `ss`, the pairing floor exceeds the observed shift.
At `fs` the shift exceeds the pairing floor, but the late readings moved by
about three times the shift. At `sf` that movement also exceeds the settling guard.
These comparisons limit the precision of the fine residual at every point.
The graded transfer, operating-point and integration checks pass at all five.

| quantity | old (min…max) | new (min…max) |
|---|---|---|
| `transfer_error_db` | -0.0345…+0.8032 dB | -0.0305…+0.2988 dB |
| `measured_gain_db` | 15.5285…16.3662 dB | 15.5326…15.8618 dB |
| `tracking_ratio` | 0.996032…1.09688 | 0.9965…1.035 |

The largest reported deviation from `20·log₁₀(6)` fell from 0.80 to
0.30 dB. The method guards above determine the record's overall FAIL.
Issue #1077 tracks both failures under the existing DR-027 bands.

### Delta table

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/reference-phase-transfer/records/20260925-080736-b722f33.md \
  sim/reference-phase-transfer/records/20261120-151718-d0000b5.md
```

Each row reports the largest absolute and relative changes independently.
The last column identifies the corner with the largest relative change.

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `cdn_lvl` | min=8.900000e-04 | 0.109533..0.208704 | 0.109627..0.208713 | 9.400000e-05 | 0.08582 | `ff_-40c_3.63v_vs2p430` |
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.109416..0.208863 | 0.109617..0.208731 | 0.000201 | 0.1837 | `ff_-40c_3.63v_vs2p430` |
| `integration` | `up_lvl` | — | 0.18123..0.494493 | 0.179734..0.495692 | 0.004629 | 1.481 | `ff_-40c_3.63v_vs2p430` |
| `operating-point` | `ffb` | — | 2.500120e+07..2.500530e+07 | 2.500120e+07..2.500490e+07 | 800 | 0.0032 | `fs_125c_3.63v_vs1p791` |
| `operating-point` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.500070e+08..1.500320e+08 | 1.500040e+08..1.500300e+08 | 8000 | 0.005333 | `typical_27c_3.30v_vs1p795` |
| `operating-point` | `lock_lvl` | — | 5.124637e-09..2.97 | 5.126650e-09..2.97 | 2.275000e-12 | 0.04165 | `typical_27c_3.30v_vs1p795` |
| `operating-point` | `nmeas` | min=5.99, max=6.01 | 5.99984..6.00012 | 5.99989..6.00035 | 0.00027 | 0.0045 | `ff_-40c_3.63v_vs2p430` |
| `pairing` | `d_mid` | — | 2.345900e-11..6.287800e-11 | -1.127510e-10..7.813000e-11 | 1.465197e-10 | 433.9 | `sf_-40c_2.97v_vs1p677` |
| `pairing` | `drift_ctl` | — | -1.409533e-09..8.514300e-11 | -1.411510e-09..1.440800e-10 | 7.889900e-11 | 69.22 | `ff_-40c_3.63v_vs2p430` |
| `pairing` | `pair_resid` | min=-5.000000e-11, max=5.000000e-11 | -1.048500e-11..2.629800e-11 | -1.690000e-11..5.354000e-11 | 3.708100e-11 | 284.3 | `ss_125c_2.97v_vs1p093` |
| `pairing` | `settle_resid` | min=-1.000000e-10, max=1.000000e-10 | -5.207900e-11..7.342300e-11 | -6.456000e-11..1.175180e-10 | 1.552547e-10 | 1493 | `fs_125c_3.63v_vs1p791` |
| `phases` | `cphi_fast` | — | 1.024547e-09..4.789116e-09 | 9.013920e-10..4.808640e-09 | 1.231550e-10 | 12.02 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `cphi_mid` | — | 7.555487e-10..4.085248e-09 | 8.716260e-10..4.107410e-09 | 1.191620e-10 | 15.36 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `cphi_post` | — | 6.722134e-10..3.560114e-09 | 6.294400e-10..3.575020e-09 | 6.899200e-11 | 6.363 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `cphi_pre` | — | 1.053434e-09..4.969647e-09 | 9.480630e-10..4.986530e-09 | 1.053710e-10 | 10 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `sphi_fast` | — | 8.589610e-11..3.872757e-09 | -3.272030e-11..3.877950e-09 | 1.186164e-10 | 138.1 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `sphi_mid` | — | 7.893174e-10..4.148126e-09 | 7.588750e-10..4.169430e-09 | 9.100100e-11 | 3.857 | `sf_-40c_2.97v_vs1p677` |
| `phases` | `sphi_post` | — | 6.682454e-10..3.570913e-09 | 6.342070e-10..3.580480e-09 | 1.107870e-10 | 5.315 | `typical_27c_3.30v_vs1p795` |
| `phases` | `sphi_pre` | — | 1.079732e-09..4.962576e-09 | 9.462660e-10..4.999560e-09 | 1.334660e-10 | 12.36 | `sf_-40c_2.97v_vs1p677` |
| `rolloff` | `d_fast` | — | -9.758290e-10..-9.163590e-10 | -9.779600e-10..-9.306900e-10 | 1.433100e-11 | 1.564 | `ss_125c_2.97v_vs1p093` |
| `rolloff` | `fast_gain` | — | 0.145026..0.501846 | 0.13224..0.41586 | 0.085986 | 37.73 | `ff_-40c_3.63v_vs2p430` |
| `rolloff` | `fast_gain_db` | — | -16.7711..-5.98859 | -17.5727..-7.62106 | 2.7807 | 27.26 | `ss_125c_2.97v_vs1p093` |
| `rolloff` | `fast_rejection_db` | — | -32.6605..-21.6449 | -33.1053..-23.2314 | 3.285 | 10.77 | `ff_-40c_3.63v_vs2p430` |
| `transfer` | `measured_gain` | — | 5.97619..6.58129 | 5.979..6.21 | 0.37129 | 5.642 | `ff_-40c_3.63v_vs2p430` |
| `transfer` | `measured_gain_db` | — | 15.5285..16.3662 | 15.5326..15.8618 | 0.5044 | 3.082 | `ff_-40c_3.63v_vs2p430` |
| `transfer` | `phi_shift` | — | -3.968000e-12..9.688200e-11 | -3.500000e-12..3.500000e-11 | 6.188200e-11 | 220.1 | `sf_-40c_2.97v_vs1p677` |
| `transfer` | `target_gain_db` | — | 15.563..15.563 | 15.563..15.563 | 0 | 0 | `—` |
| `transfer` | `tracking_ratio` | min=0.9, max=1.1 | 0.996032..1.09688 | 0.9965..1.035 | 0.06188 | 5.641 | `ff_-40c_3.63v_vs2p430` |
| `transfer` | `transfer_error_db` | — | -0.0345342..0.803198 | -0.0304539..0.298807 | 0.504391 | 219.6 | `sf_-40c_2.97v_vs1p677` |
| `ungrouped` | `tclk160` | — | 1.066438e-06..1.066616e-06 | 1.066450e-06..1.066640e-06 | 5.800000e-11 | 0.005438 | `typical_27c_3.30v_vs1p795` |
| `ungrouped` | `tfb20` | — | 7.998317e-07..7.999629e-07 | 7.998420e-07..7.999620e-07 | 2.570000e-11 | 0.003213 | `fs_125c_3.63v_vs1p791` |

**Per-corner verdict flips** (each one is a finding):

| topology | corner-id | old | new |
|---|---|---|---|
| `pairing` | `ff_-40c_3.63v_vs2p430` | PASS | FAIL — pair_resid max=5.000000e-11 (got 5.354000e-11) |
| `pairing` | `sf_-40c_2.97v_vs1p677` | PASS | FAIL — settle_resid max=1.000000e-10 (got 1.175180e-10) |

**Stated limits**: identical in both records.

_2 finding(s) above need a human disposition._

## `period-jitter`

The deterministic period-jitter grid -- the full mandated 45-point PVT matrix
(five MOS bundles x -40/27/125 C x 2.97/3.30/3.63 V), one job per point on
the `batch` backend -- re-run under `f6eeac7` as a single new record,
[`20261121-184803-04533bf`](period-jitter/records/20261121-184803-04533bf.md)
(45/45 ok, **overall PASS**). The `SOURCES` stamp was verified before the
grid was spent: a one-job probe at `typical_27c_3.30v_vs1p795` (fleet job
`gf180-pll-sim-typical_27c_3.30v_vs1p795-c552a7bc`, `--no-write`, nothing
minted) returned `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` in its
collected `ngspice.env`, and only then was the 45-job grid submitted. 46
fleet jobs total, ids `gf180-pll-sim-<corner-id>-<8-hex>`; the record's
**Execution hosts** line carries the per-point host tally.

The submission was interrupted once at the submitting host: the first
attempt's driver was killed 24 points in, and the record was completed by
`--resume` under the same record id -- 23 points replayed from that
attempt's collected logs (each re-parsed to its full declared measurement
set, no simulator call), 22 re-run (the record's **Resumed run** field
carries the split and the wall-clock caveat). Nothing was minted under a
second id and no evidence was discarded. One side effect is disclosed in the
record and worth restating: the minting attempt sampled git state with
attempt 1's own untracked evidence already under `corners/`, so the record's
tree flag reads **DIRTY**; no tracked file differed from `04533bf7` -- the
flag names that resume artifact, not a tree edit.

**Supersedes: `20260906-095050-3a8a6ef`** -- the campaign's latest record,
the #273 wrap-safe-gate re-measure -- and through it the whole union: the
re-run covers every point of `20260905-192724-a2ba48f` (1),
`20260906-015602-f9bef9d` (4), `20260906-024225-12bccda` (8),
`20260906-063728-f3c9c23` (18) and `20260906-080511-69b36ef` (16) -- 47
predecessor runs at the 45 distinct points the new grid measures once each.

### What changed besides the PDK

The six predecessors executed on ngspice-46 (the first on macOS/arm64, the
rest on Linux/x86-64, all local runs); this record executed on the fleet
image's ngspice-47 (built 2026-11-14). The composed DUT differs from the
September snapshots in the same design edits the `reference-spur` re-run
carries -- `XCF5` moves to the option-B MIM (`m2m3_noshield` ->
`m4m5_noshield`, DR-042, same 31.4 um x 31.4 um `m=1` geometry) -- plus, for
this campaign's snapshots, the DR-014 lock-detector window-trim ports on
`XLD`/`delaywin_3v3` (`LDT0`-`LDT3`), which post-date them. The stimulus
deck, solver options, `.tran` line and every measurement card are unchanged.
The deck carries the nonlinear-moscap `m=` trigger of #153/#926 (4x
`cap_nmos_03v3_b` in `loop_filter`, 2x `cap_nmos_03v3` in `vco`), so per #932
the movement below is **not attributable to the PDK alone**.

### Overlap point: pinned ngspice-46 under `f6eeac7`, one corner

```bash
SIM_NGSPICE_BIN=$HOME/.local/opt/ngspice-46/bin/ngspice \
PATH=$HOME/.local/opt/ngspice-46/bin:$PATH \
  python3 sim/run_corners.py period-jitter --backend local \
  --corners typical --temps 27 --supply 3.3 --supply-tol 0 \
  --axis vs=vs1p795 --timeout 5400 --no-write -j 1
```

Same deck, same PDK pin (`f6eeac7`), `typical_27c_3.30v_vs1p795`, 1/1 ok,
**287.0 s wall clock** on this host. Not minted as a record (`--no-write`).
This is also the only corner the first record `20260905-192724-a2ba48f`
measured, read here three ways (its corner-id predates the `vs` axis):

| measurement | first record (ngspice-46, `c6d73a3`, macOS) | ngspice-46, `f6eeac7` (local) | this record (ngspice-47, `f6eeac7`, batch) |
|---|---|---|---|
| `tj_rms_pct` (max 1.0) | 0.23339 PASS | 0.218059 PASS | 0.21977 PASS |
| `tj_rms_s` | 1.555757e-11 | 1.453507e-11 | 1.464894e-11 |
| `tj_pp_s` | 6.768892e-11 | 6.768740e-11 | 7.037071e-11 |
| `fout` (Hz) | 1.500010e+08 | 1.500130e+08 | 1.500420e+08 |
| `nmeas` | 5.99987 | 5.99941 | 6.00028 |
| `dn_lvl` (min 8.9e-4) | 0.174982 | 0.174946 | 0.174987 |

- Predecessor -> local overlap: `tj_rms_pct` moves **-6.6 % relative** on an
  identical deck, combining the PDK, both DUT netlist edits and the host
  change.
- Local ngspice-46 -> batch ngspice-47 (PDK and netlist fixed): **+0.8 %**
  at this corner. The lock-point columns agree to better than 0.04 % across
  all three runs.
- One corner only; no claim is made for the other 44.

### Deltas per predecessor

**No per-corner verdict changed against current evidence, and no stated
limit moved.** The only flips the generator reports are against
`20260906-063728-f3c9c23`'s two `ferr` FAILs -- the #273 wrap-defect
verdicts `20260906-095050-3a8a6ef` already superseded with PASS; this record
agrees with `3a8a6ef` on all 8 graded rows of that pair (table below).
Headline movement across the union: `tj_rms_pct` **0.0508-0.2691 ->
0.0464-0.2795**, worst per-point move **-23.2 % relative**
(`ss`/27 C/3.63 V: 0.1732 -> 0.1331; the same re-pin moves `ff`/-40 C/3.30 V
0.2477 -> 0.1935, -21.9 %), every point inside the 1.0 % RMS line with a
worst-case margin of 3.6x. Nothing moved past a tolerance, so this increment
files no new issue or decision record.

#### vs `20260906-015602-f9bef9d` (four process-corner extremes at 27 °C/3.30 V)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260906-015602-f9bef9d.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.16218..0.212955 | 0.162163..0.212059 | 0.000896 | 0.4207 | `ss_27c_3.30v_vs1p633` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 7.358352e-11..7.644729e-11 | 7.354662e-11..7.650045e-11 | 6.423400e-13 | 0.8683 | `fs_27c_3.30v_vs1p764` |
| `integration` | `up_lvl` | — | 0.150014..0.367994 | 0.150666..0.495535 | 0.127541 | 34.66 | `ss_27c_3.30v_vs1p633` |
| `jitter` | `c2c_rms_s` | — | 1.496479e-11..2.367510e-11 | 1.460604e-11..2.217640e-11 | 4.758540e-12 | 24.57 | `fs_27c_3.30v_vs1p764` |
| `jitter` | `n_cycles` | — | 313..314 | 313..314 | 0 | 0 | `—` |
| `jitter` | `tie_pp_s` | — | 4.678269e-11..7.348412e-11 | 3.533734e-11..5.852974e-11 | 2.511759e-11 | 36.33 | `ss_27c_3.30v_vs1p633` |
| `jitter` | `tie_rms_s` | — | 9.072738e-12..1.615206e-11 | 6.984765e-12..1.067191e-11 | 7.209413e-12 | 48.29 | `ss_27c_3.30v_vs1p633` |
| `jitter` | `tj_pp_s` | — | 3.937769e-11..6.629769e-11 | 3.888072e-11..6.771119e-11 | 1.684124e-11 | 30.22 | `fs_27c_3.30v_vs1p764` |
| `jitter` | `tj_rms_pct` | max=1 | 0.133303..0.207204 | 0.133959..0.197684 | 0.034731 | 20.59 | `fs_27c_3.30v_vs1p764` |
| `jitter` | `tj_rms_s` | — | 8.886586e-12..1.381374e-11 | 8.930497e-12..1.317901e-11 | 2.315653e-12 | 20.59 | `fs_27c_3.30v_vs1p764` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -6.779880e-06..1.387370e-05 | -3.036170e-05..-3.202910e-08 | 4.423540e-05 | 318.8 | `ff_27c_3.30v_vs1p931` |
| `lock` | `ffb` | — | 2.499790e+07..2.500100e+07 | 2.499990e+07..2.500130e+07 | 3400 | 0.0136 | `ff_27c_3.30v_vs1p931` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499930e+08..1.500250e+08 | 1.499920e+08..1.500130e+08 | 21000 | 0.014 | `ss_27c_3.30v_vs1p633` |
| `lock` | `lock_lvl` | — | 5.784600e-09..3.3 | 5.784230e-09..3.3 | 3.700000e-13 | 0.006396 | `ss_27c_3.30v_vs1p633` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 6.00002..6.00151 | 5.99966..6.00019 | 0.00132 | 0.02199 | `ff_27c_3.30v_vs1p931` |
| `ungrouped` | `phi_a` | — | -7.616100e-11..1.580010e-09 | -7.798000e-11..2.879110e-09 | 1.299100e-09 | 82.22 | `ss_27c_3.30v_vs1p633` |
| `ungrouped` | `phi_b` | — | -9.003470e-11..1.574980e-09 | -4.761830e-11..2.879140e-09 | 1.304160e-09 | 82.8 | `ss_27c_3.30v_vs1p633` |
| `ungrouped` | `tclk20` | — | 1.333110e-07..1.333390e-07 | 1.333220e-07..1.333400e-07 | 1.900000e-11 | 0.01425 | `ss_27c_3.30v_vs1p633` |
| `ungrouped` | `tfb5` | — | 1.999920e-07..2.000170e-07 | 1.999900e-07..2.000010e-07 | 2.700000e-11 | 0.0135 | `ff_27c_3.30v_vs1p931` |

**Per-corner verdicts**: unchanged on all 16 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261121-184803-04533bf` only: `lock`/`dphi`
- in `20261121-184803-04533bf` only: `lock`/`ferr_fb`

#### vs `20260906-024225-12bccda` (the `typical` temperature x supply plane)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260906-024225-12bccda.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.148101..0.211655 | 0.14837..0.212098 | 0.000985 | 0.6463 | `typical_-40c_3.30v_vs1p999` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 6.875859e-11..8.085560e-11 | 6.897417e-11..8.080808e-11 | 5.696100e-13 | 0.7747 | `typical_-40c_2.97v_vs1p644` |
| `integration` | `up_lvl` | — | 0.325179..0.53305 | 0.318307..0.533521 | 0.053189 | 10.33 | `typical_125c_2.97v_vs1p270` |
| `jitter` | `c2c_rms_s` | — | 1.281454e-11..3.153120e-11 | 1.357541e-11..3.205192e-11 | 3.233210e-12 | 12.31 | `typical_27c_2.97v_vs1p478` |
| `jitter` | `n_cycles` | — | 314..314 | 314..314 | 0 | 0 | `—` |
| `jitter` | `tie_pp_s` | — | 3.424473e-11..1.726805e-10 | 3.606053e-11..1.658866e-10 | 7.021390e-11 | 86.12 | `typical_27c_3.63v_vs2p094` |
| `jitter` | `tie_rms_s` | — | 6.583296e-12..4.011189e-11 | 8.439930e-12..3.752954e-11 | 1.712823e-11 | 96.87 | `typical_27c_3.63v_vs2p094` |
| `jitter` | `tj_pp_s` | — | 3.535206e-11..8.070263e-11 | 3.464833e-11..8.333656e-11 | 6.896710e-12 | 10.4 | `typical_125c_3.30v_vs1p549` |
| `jitter` | `tj_rms_pct` | max=1 | 0.11114..0.269086 | 0.116654..0.279518 | 0.02777 | 11.03 | `typical_-40c_2.97v_vs1p644` |
| `jitter` | `tj_rms_s` | — | 7.407988e-12..1.793773e-11 | 7.775906e-12..1.863092e-11 | 1.851120e-12 | 11.03 | `typical_-40c_2.97v_vs1p644` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -1.488380e-05..2.979480e-05 | 6.391510e-07..3.526560e-05 | 2.775978e-05 | 518 | `typical_27c_2.97v_vs1p478` |
| `lock` | `ffb` | — | 2.499810e+07..2.500590e+07 | 2.500020e+07..2.500620e+07 | 5200 | 0.0208 | `typical_-40c_2.97v_vs1p644` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499850e+08..1.500430e+08 | 1.499760e+08..1.500390e+08 | 67000 | 0.04465 | `typical_27c_3.63v_vs2p094` |
| `lock` | `lock_lvl` | — | 4.150140e-09..5.737850e-08 | 4.064670e-09..5.734610e-08 | 3.450700e-10 | 6.397 | `typical_-40c_3.63v_vs2p330` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 5.99932..6.00066 | 5.99885..6.00032 | 0.00181 | 0.03016 | `typical_27c_3.63v_vs2p094` |
| `ungrouped` | `phi_a` | — | 1.743470e-09..3.481720e-09 | 1.666420e-09..3.308540e-09 | 6.068700e-10 | 17.43 | `typical_125c_2.97v_vs1p270` |
| `ungrouped` | `phi_b` | — | 1.743980e-09..3.454480e-09 | 1.664250e-09..3.300270e-09 | 5.909100e-10 | 17.11 | `typical_125c_2.97v_vs1p270` |
| `ungrouped` | `tclk20` | — | 1.332950e-07..1.333470e-07 | 1.332980e-07..1.333550e-07 | 6.000000e-11 | 0.04501 | `typical_27c_3.63v_vs2p094` |
| `ungrouped` | `tfb5` | — | 1.999520e-07..2.000150e-07 | 1.999500e-07..1.999980e-07 | 4.200000e-11 | 0.021 | `typical_-40c_2.97v_vs1p644` |

**Per-corner verdicts**: unchanged on all 32 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261121-184803-04533bf` only: `lock`/`dphi`
- in `20261121-184803-04533bf` only: `lock`/`ferr_fb`

#### vs `20260906-063728-f3c9c23` (the `ff` and `ss` planes)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260906-063728-f3c9c23.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.123712..0.25407 | 0.124014..0.253821 | 0.001915 | 1.15 | `ff_27c_2.97v_vs1p638` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 6.872638e-11..8.525480e-11 | 6.898498e-11..8.509980e-11 | 9.406000e-13 | 1.315 | `ff_-40c_2.97v_vs1p812` |
| `integration` | `up_lvl` | — | 0.14586..0.766845 | 0.146315..0.72952 | 0.235847 | 41.53 | `ff_-40c_3.30v_vs2p136` |
| `jitter` | `c2c_rms_s` | — | 5.942038e-12..2.909803e-11 | 5.314212e-12..2.739045e-11 | 6.074660e-12 | 25.24 | `ss_27c_3.63v_vs1p953` |
| `jitter` | `n_cycles` | — | 314..314 | 314..314 | 0 | 0 | `—` |
| `jitter` | `tie_pp_s` | — | 1.727898e-11..1.297270e-10 | 2.464492e-11..1.036310e-10 | 4.866798e-11 | 54.19 | `ss_125c_3.63v_vs1p664` |
| `jitter` | `tie_rms_s` | — | 3.101653e-12..3.217348e-11 | 5.600771e-12..2.383400e-11 | 9.821108e-12 | 89.57 | `ss_125c_2.97v_vs1p093` |
| `jitter` | `tj_pp_s` | — | 1.807482e-11..7.910367e-11 | 1.602519e-11..7.910342e-11 | 1.449913e-11 | 19.97 | `ff_-40c_3.30v_vs2p136` |
| `jitter` | `tj_rms_pct` | max=1 | 0.0507647..0.248428 | 0.0463528..0.240717 | 0.054211 | 23.19 | `ss_27c_3.63v_vs1p953` |
| `jitter` | `tj_rms_s` | — | 3.383759e-12..1.655856e-11 | 3.089687e-12..1.604607e-11 | 3.612190e-12 | 23.17 | `ss_27c_3.63v_vs1p953` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -1.078020e-05..0.0399985 | -3.803670e-05..4.140200e-05 | 0.0400083 | 1.393e+04 | `ff_-40c_2.97v_vs1p812` |
| `lock` | `ffb` | — | 2.499720e+07..2.500710e+07 | 2.499510e+07..2.500710e+07 | 6600 | 0.0264 | `ff_-40c_2.97v_vs1p812` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499760e+08..1.500540e+08 | 1.499530e+08..1.500530e+08 | 46000 | 0.03067 | `ff_125c_2.97v_vs1p431` |
| `lock` | `lock_lvl` | — | 3.772400e-09..3.63 | 3.771480e-09..3.63 | 3.63 | 7.769e+10 | `ff_-40c_3.30v_vs2p136` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 5.99923..6.00113 | 5.99882..6.00102 | 0.00134 | 0.02233 | `ff_125c_3.63v_vs1p929` |
| `ungrouped` | `phi_a` | — | -8.884970e-11..3.985710e-08 | -7.798000e-11..3.987780e-08 | 2.190690e-09 | 82.77 | `ss_27c_3.30v_vs1p633` |
| `ungrouped` | `phi_b` | — | -1.864790e-10..4.695000e-09 | -2.030200e-10..4.668750e-09 | 2.183630e-09 | 82.8 | `ss_27c_3.30v_vs1p633` |
| `ungrouped` | `tclk20` | — | 1.332860e-07..1.333550e-07 | 1.332860e-07..1.333750e-07 | 4.100000e-11 | 0.03075 | `ff_125c_2.97v_vs1p431` |
| `ungrouped` | `tfb5` | — | 1.999440e-07..2.000220e-07 | 1.999430e-07..2.000390e-07 | 5.300000e-11 | 0.0265 | `ff_-40c_2.97v_vs1p812` |

**Per-corner verdict flips** (each one is a finding):

| topology | corner-id | old | new |
|---|---|---|---|
| `lock` | `ff_27c_2.97v_vs1p638` | FAIL — ferr max=0.001 (got 0.0399985) | PASS (replayed) |
| `lock` | `ff_27c_3.63v_vs2p200` | FAIL — ferr max=0.001 (got 0.0399881) | PASS (replayed) |

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261121-184803-04533bf` only: `lock`/`dphi`
- in `20261121-184803-04533bf` only: `lock`/`ferr_fb`

_2 finding(s) above need a human disposition._

#### vs `20260906-080511-69b36ef` (the `fs` and `sf` planes, closing the matrix)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260906-080511-69b36ef.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.145138..0.219175 | 0.145412..0.220046 | 0.001242 | 0.6127 | `sf_-40c_2.97v_vs1p677` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 6.903044e-11..8.098954e-11 | 6.942034e-11..8.096272e-11 | 5.304000e-13 | 0.6915 | `fs_27c_2.97v_vs1p460` |
| `integration` | `up_lvl` | — | 0.194922..0.557749 | 0.19799..0.557652 | 0.016056 | 6.441 | `sf_-40c_2.97v_vs1p677` |
| `jitter` | `c2c_rms_s` | — | 1.055707e-11..2.934851e-11 | 1.101916e-11..3.009598e-11 | 3.687540e-12 | 16.2 | `sf_27c_2.97v_vs1p500` |
| `jitter` | `n_cycles` | — | 314..314 | 314..314 | 0 | 0 | `—` |
| `jitter` | `tie_pp_s` | — | 3.332403e-11..9.900831e-11 | 3.185386e-11..1.288174e-10 | 7.625410e-11 | 145.1 | `fs_-40c_2.97v_vs1p620` |
| `jitter` | `tie_rms_s` | — | 6.700826e-12..2.168357e-11 | 8.043125e-12..2.845334e-11 | 1.836281e-11 | 182 | `fs_-40c_2.97v_vs1p620` |
| `jitter` | `tj_pp_s` | — | 2.700495e-11..7.862877e-11 | 2.711186e-11..7.928264e-11 | 1.069131e-11 | 16.82 | `fs_-40c_3.63v_vs2p279` |
| `jitter` | `tj_rms_pct` | max=1 | 0.0902712..0.247217 | 0.0931676..0.269041 | 0.028652 | 13.93 | `sf_27c_2.97v_vs1p500` |
| `jitter` | `tj_rms_s` | — | 6.017011e-12..1.648005e-11 | 6.209997e-12..1.793630e-11 | 1.909580e-12 | 13.93 | `sf_27c_2.97v_vs1p500` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -1.977270e-05..3.649070e-05 | -1.398430e-05..5.300460e-05 | 2.318381e-05 | 3.486e+04 | `sf_27c_3.63v_vs2p128` |
| `lock` | `ffb` | — | 2.499760e+07..2.500770e+07 | 2.499720e+07..2.500820e+07 | 8000 | 0.03199 | `fs_27c_3.63v_vs2p055` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499710e+08..1.500550e+08 | 1.499610e+08..1.500710e+08 | 47000 | 0.03132 | `fs_27c_3.63v_vs2p055` |
| `lock` | `lock_lvl` | — | 3.865850e-09..3.63 | 3.835720e-09..3.63 | 3.63 | 6.653e+10 | `sf_-40c_3.63v_vs2p379` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 5.99892..6.00088 | 5.99912..6.00085 | 0.00121 | 0.02017 | `fs_-40c_3.63v_vs2p279` |
| `ungrouped` | `phi_a` | — | 3.942430e-10..3.315890e-09 | 4.264440e-10..3.327370e-09 | 1.927330e-10 | 17.81 | `sf_-40c_2.97v_vs1p677` |
| `ungrouped` | `phi_b` | — | 3.956290e-10..3.285290e-09 | 4.330170e-10..3.307780e-09 | 1.887620e-10 | 17.49 | `sf_-40c_2.97v_vs1p677` |
| `ungrouped` | `tclk20` | — | 1.332850e-07..1.333590e-07 | 1.332710e-07..1.333680e-07 | 4.200000e-11 | 0.03151 | `fs_27c_3.63v_vs2p055` |
| `ungrouped` | `tfb5` | — | 1.999380e-07..2.000190e-07 | 1.999340e-07..2.000220e-07 | 6.400000e-11 | 0.03201 | `fs_27c_3.63v_vs2p055` |

**Per-corner verdicts**: unchanged on all 64 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261121-184803-04533bf` only: `lock`/`dphi`
- in `20261121-184803-04533bf` only: `lock`/`ferr_fb`

#### vs `20260906-095050-3a8a6ef` (the #273 wrap-safe-gate re-measure -- the superseded record)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260906-095050-3a8a6ef.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|
| `integration` | `dn_lvl` | min=8.900000e-04 | 0.166548..0.173443 | 0.168463..0.17264 | 0.001915 | 1.15 | `ff_27c_2.97v_vs1p638` |
| `integration` | `dt_int_mean` | max=1.000000e-10 | 7.175941e-11..7.571325e-11 | 7.165657e-11..7.566898e-11 | 1.028400e-13 | 0.1433 | `ff_27c_3.63v_vs2p200` |
| `integration` | `up_lvl` | — | 0.14586..0.154897 | 0.146315..0.154482 | 0.000455 | 0.3119 | `ff_27c_2.97v_vs1p638` |
| `jitter` | `c2c_rms_s` | — | 2.263701e-11..2.785439e-11 | 2.345371e-11..2.502147e-11 | 2.832920e-12 | 10.17 | `ff_27c_2.97v_vs1p638` |
| `jitter` | `n_cycles` | — | 314..314 | 314..314 | 0 | 0 | `—` |
| `jitter` | `tie_pp_s` | — | 6.300712e-11..6.898545e-11 | 5.616357e-11..8.975187e-11 | 2.076642e-11 | 30.1 | `ff_27c_2.97v_vs1p638` |
| `jitter` | `tie_rms_s` | — | 1.269751e-11..1.415247e-11 | 1.131631e-11..1.739268e-11 | 3.240210e-12 | 22.9 | `ff_27c_2.97v_vs1p638` |
| `jitter` | `tj_pp_s` | — | 6.454633e-11..6.981386e-11 | 6.735212e-11..7.007651e-11 | 2.805790e-12 | 4.347 | `ff_27c_3.63v_vs2p200` |
| `jitter` | `tj_rms_pct` | max=1 | 0.199429..0.235105 | 0.205675..0.220465 | 0.01464 | 6.227 | `ff_27c_2.97v_vs1p638` |
| `jitter` | `tj_rms_s` | — | 1.329573e-11..1.567401e-11 | 1.371187e-11..1.469816e-11 | 9.758500e-13 | 6.226 | `ff_27c_2.97v_vs1p638` |
| `lock` | `dphi` | — | 1.466790e-12..1.186040e-11 | -3.001740e-12..2.021340e-11 | 8.353000e-12 | 304.6 | `ff_27c_2.97v_vs1p638` |
| `lock` | `ferr` | min=-0.001, max=0.001 | -1.186040e-05..-1.466790e-06 | -2.021340e-05..3.001740e-06 | 8.353000e-06 | 304.6 | `ff_27c_2.97v_vs1p638` |
| `lock` | `ferr_fb` | min=-0.002, max=0.002 | -0.000110489..0.000106812 | -6.352000e-05..0.000123471 | 0.00023396 | 211.7 | `ff_27c_3.63v_vs2p200` |
| `lock` | `ffb` | — | 2.499720e+07..2.500270e+07 | 2.499840e+07..2.500310e+07 | 5900 | 0.0236 | `ff_27c_3.63v_vs2p200` |
| `lock` | `fout` | min=1.485000e+08, max=1.515000e+08 | 1.499760e+08..1.500060e+08 | 1.500080e+08..1.500120e+08 | 36000 | 0.024 | `ff_27c_3.63v_vs2p200` |
| `lock` | `lock_lvl` | — | 2.97..3.63 | 2.97..3.63 | 0 | 0 | `—` |
| `lock` | `nmeas` | min=5.99, max=6.01 | 5.99961..5.99969 | 5.99975..6.0007 | 0.00109 | 0.01817 | `ff_27c_2.97v_vs1p638` |
| `ungrouped` | `phi_a` | — | 3.981210e-08..3.985710e-08 | 3.980000e-08..3.987780e-08 | 2.070000e-11 | 0.05194 | `ff_27c_3.63v_vs2p200` |
| `ungrouped` | `phi_b` | — | -1.864790e-10..-1.310450e-10 | -2.030200e-10..-1.020140e-10 | 2.903100e-11 | 22.15 | `ff_27c_3.63v_vs2p200` |
| `ungrouped` | `tclk20` | — | 1.333280e-07..1.333550e-07 | 1.333220e-07..1.333260e-07 | 3.300000e-11 | 0.02475 | `ff_27c_3.63v_vs2p200` |
| `ungrouped` | `tfb5` | — | 1.999790e-07..2.000220e-07 | 1.999750e-07..2.000130e-07 | 4.700000e-11 | 0.0235 | `ff_27c_3.63v_vs2p200` |

**Per-corner verdicts**: unchanged on all 8 graded rows.

**Stated limits**: identical in both records.

#### vs `20260905-192724-a2ba48f` (the campaign first record: single point, pre-`vs`-axis corner-id)

Reproduce with:

```bash
python3 sim/lib/record_delta.py \
  sim/period-jitter/records/20260905-192724-a2ba48f.md \
  sim/period-jitter/records/20261121-184803-04533bf.md
```

| topology | measurement | limit | old min..max | new min..max | max abs delta | max rel delta % | worst corner |
|---|---|---|---|---|---|---|---|

**Per-corner verdicts**: unchanged on all 4 graded rows.

**Stated limits**: identical in both records.

**Measurement coverage differs between the two records:**

- in `20261121-184803-04533bf` only: `lock`/`dphi`
- in `20261121-184803-04533bf` only: `lock`/`ferr_fb`

## `pll-top-smoke`

The [seven-check comparison](pll-top-smoke/records/20261120-025417-fe7841e.md) covers the
entire original smoke bench at 27 °C and 3.30 V. All seven checks pass on
both pins using ngspice-42 and the same frozen PLL assembly. The record
also grades the late static phase against the ratified 1 ns bound.

## `loop-dynamics`

Disposition: **provenance verified, no replay needed.** The successor record
[`20261111-092132-343bafa`](loop-dynamics/records/20261111-092132-343bafa.md)
already exists on `main` — 99/99 batch points under open_pdks `f6eeac7`,
`Supersedes: 20260731-202550-82af5a9` — but its Environment provenance lists
the executing simulator as *unattributed* for all 99 points, which is why this
campaign stayed open. The archive of the batch fleet's job outputs answers it.

### What the archived worker job metadata says

Every batch job's `outputs/ngspice.env` (written by the job contract,
`sim/harness/batch.py`) carries the executing binary's own banner, the
resolved PDK's `SOURCES` stamp, the image manifest and the instance's
hostname; `outputs/ngspice.log` is the deck stdout the harness published.
Matching those archives to the committed evidence:

- **99 of 99 committed corner logs byte-match an archived fleet job** — the
  `outputs/ngspice.log` of exactly one 2026-11-11 job per corner is
  sha256-identical to `corners/20261111-092132-343bafa/<corner_id>.log`.
  The recovered mapping is committed as
  [`executing-simulator-provenance.csv`](loop-dynamics/corners/20261111-092132-343bafa/executing-simulator-provenance.csv)
  and asserted by `sim/tests/test_repin_deltas_closed_loop.py`.
- **Executing simulator: ngspice-46 on all 99 points** (the banner in every
  job's `ngspice.env`; simulator init sha256 `d6efd5b2…`, the single value
  the record already states). Same major version as the baseline
  `20260731-202550-82af5a9` (ngspice-46, Darwin arm64, pinned-local), so the
  DR-039 hazard of a batch ngspice-47 number superseding an ngspice-46 one
  does not arise here; the remaining host/OS delta is exactly what the
  record's own `baseline_comparison` pilot gate grades — 95 rows, zero
  failing, PILOT GATE = GO.
- **PDK stamp: `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` on all
  99 points**, resolved at `/opt/pdk/gf180mcuD` — the re-pinned revision
  this issue requires, on image `ami-095c25ae241a4d360` (manifest
  `built_at 2026-11-06T02:46:10Z`, `tools.ngspice ngspice-46`), uniform
  across the grid.
- The 99 executing hosts in the CSV are exactly the record's 99 named
  `ip-*` execution hosts. Nine `rtyp-mtyp-*` filter points additionally
  have earlier archived executions (2026-11-06, 2026-11-08 — the pilot
  days) whose logs are byte-identical to the committed ones, on the same
  image; they are listed in the CSV's `prior_byte_identical_jobs` column.

Method note for re-verification: the job archive is addressed by job id
under the worker-exported batch configuration (`KLT_BATCH_PROVISION_SCRIPT`
env file: bucket, region, `jobs/` prefix); job ids are
`gf180-pll-sim-<corner-run-id>-<hex8>`. The per-job facts above come from
the archived `ngspice.env`/`ngspice.host`/`status.json`; the byte-match is
recomputable from the committed CSV's sha256 column alone.

### Delta table

The old-vs-new comparison for this campaign is the record's own ratified
pilot gate (every metric against the baseline with the ratified tolerance,
none loosened): see
[`baseline_comparison.csv`](loop-dynamics/corners/20261111-092132-343bafa/baseline_comparison.csv)
(95 metrics, failing rows: none, verdicts unchanged — the `s10 verdict` row
is the identical text on both sides: **Overall: PASS on the contracted
operating space, FAIL off it**, i.e. the conditional PASS
`sim/CHARACTERIZATION.md` records, only when the Icp trim-code rule is
followed — not an unqualified pass). No generated `record_delta.py` table is
printed for this pair: the predecessor predates the harness's graded-table
record format, so there are no overlapping graded measurements to tabulate
(0 graded rows).
