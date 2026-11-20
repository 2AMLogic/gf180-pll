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
| `reference-phase-transfer` | 3 | still owed under #828 |
| `period-jitter` | 6 | still owed under #828 |
| `supply-sensitivity` | 12 | still owed under #828 |
| `lock-time` | 5 | still owed under #828 |
| `pll-top-smoke` | `20260802-160926-8456ff3` | **re-qualified** ([`20261120-025417-fe7841e`](pll-top-smoke/records/20261120-025417-fe7841e.md)) |
| `loop-dynamics` | 1 | still owed under #828 |

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

## `pll-top-smoke`

The [seven-check comparison](pll-top-smoke/records/20261120-025417-fe7841e.md) covers the
entire original smoke bench at 27 °C and 3.30 V. All seven checks pass on
both pins using ngspice-42 and the same frozen PLL assembly. The record
also grades the late static phase against the ratified 1 ns bound.
