# devchar-delay — 3.3 V CMOS delay-stage PVT characterization

**Consumer**: issue #8 (ring VCO). Bounds the raw, untuned frequency spread a
CMOS ring stage sees over the full corner grid, and supplies the drive-current /
switched-charge numbers needed to re-derive delay for a different fan-out or a
current-starved stage.

## Re-running

```sh
./run.sh            # full 45-point grid -> results/delay_corners.csv
./run.sh --check    # nominal corner only, printed to stdout
SIM_JOBS=4 ./run.sh # cap parallelism (default: host CPU count)
```

Environment pin and prerequisites: see [`../README.md`](../README.md). Nothing
here depends on state outside the PDK install — a clean checkout plus the pinned
PDK reproduces `results/delay_corners.csv` exactly.

## Measurement topology

`tb_delay_stage.sp` runs four independent measurements in one deck, on one
shared corner/temperature/supply setting:

| Tag | Circuit | What it yields |
|---|---|---|
| `ring1x` | 5-stage self-loaded ring, CMOS inverters `Wn=1.0 µm / Wp=2.5 µm / L=0.28 µm` | `fosc`, stage delay `tstage = 1/(2·N·fosc)`, average supply current |
| `ring4x` | identical 5-stage ring at 4× device width | how much of the stage delay is self-loading (size-invariant) vs. fixed parasitics |
| `fo1` | open 4-inverter chain, stage 3 measured (identical driver, fan-out-1 identical load) | `tpHL`, `tpLH` separately, 10–90 % output transition times |
| `idsat` | single `nfet_03v3` (W=1 µm) and `pfet_03v3` (W=2.5 µm) at `Vgs = Vds = Vdd` | peak drive current per device |

Devices are the PDK 3.3 V wrapper subcircuits `nfet_03v3` / `pfet_03v3` with
explicit `as/ad/ps/pd` from a 0.44 µm contacted-diffusion extension, so
junction capacitance is included rather than defaulted to zero.

Ring start-up uses `.ic` + `uic`; the ring frequency is taken from 8 periods
*after* start-up (2nd → 10th rising half-supply crossing), so the start-up
transient is excluded. The fan-out-1 chain measurements are windowed with `TD=`
for the same reason.

**Statistical switches are off** (`design.ngspice` defaults
`sw_stat_global = sw_stat_mismatch = 0`). These are nominal-skew corner
results, not Monte Carlo — mismatch/jitter characterization is separate work.

## Corner grid

process {`typical`, `ff`, `ss`, `fs`, `sf`} × temp {−40, 27, 125} °C × supply
{2.97, 3.30, 3.63} V = **45 points**, all run (no sampling).

## Results

Full table: [`results/delay_corners.csv`](results/delay_corners.csv) (45 rows +
provenance header naming the PDK hash, ngspice version, model sections, netlist
path and corner list).

### Per-process envelope of the 1× ring

| process | min `tstage` ps (°C/V) | max `tstage` ps (°C/V) | max `fosc` GHz | min `fosc` GHz | `Idsat` n W=1 µm min/max µA | `Idsat` p W=2.5 µm min/max µA | `cstage` fF min/max |
|---|---|---|---|---|---|---|---|
| `ff` | 30.4 (−40/3.63) | 46.9 (125/2.97) | 3.29 | 2.13 | 456 / 759 | 536 / 950 | 9.54 / 10.48 |
| `fs` | 35.7 (−40/3.63) | 56.6 (125/2.97) | 2.80 | 1.77 | 430 / 722 | 401 / 745 | 9.51 / 10.35 |
| `sf` | 36.3 (−40/3.63) | 57.4 (125/2.97) | 2.75 | 1.74 | 341 / 592 | 509 / 911 | 9.56 / 10.42 |
| `ss` | 43.1 (−40/3.63) | 69.8 (125/2.97) | 2.32 | 1.43 | 319 / 558 | 376 / 702 | 9.58 / 10.34 |
| `typical` | 35.8 (−40/3.63) | 56.7 (125/2.97) | 2.79 | 1.76 | 385 / 658 | 454 / 828 | 9.53 / 10.38 |

### Headline numbers for #8

- **Untuned 5-stage ring PVT spread**: `tstage` 30.4 ps (ff / −40 °C / 3.63 V)
  → 69.8 ps (ss / 125 °C / 2.97 V) = **2.30×**. Equivalently `fosc` 3.29 GHz →
  1.43 GHz for N = 5.
- A ring VCO must therefore carry **at least 2.3× of tuning authority** just to
  cover PVT at a fixed centre frequency, before any margin for tuning-range
  requirements, control-voltage headroom loss, or load. Stage count N and
  fan-out scale the absolute frequency but not this ratio.
- **Nominal (typical / 27 °C / 3.30 V)**: `tstage` = 44.0 ps, `fosc` = 2.27 GHz
  (N=5, FO1), `cstage` = 9.9 fF, `Idsat_n` = 520 µA (W=1 µm),
  `Idsat_p` = 623 µA (W=2.5 µm).
- **Rise/fall asymmetry** (`tpHL/tpLH`) ranges 0.86 (fs / 27 °C / 2.97 V) to
  1.37 (sf / 125 °C / 3.63 V) at the `Wp/Wn = 2.5` ratio used here. Skewed
  corners are what set duty-cycle distortion in a single-ended ring; a
  differential stage removes this sensitivity.

### Sanity anchors (test-plan checks)

| Check | Result |
|---|---|
| `ss`/125 °C delay > `ff`/−40 °C delay | 69.8 ps > 30.4 ps ✅ |
| Two independent topologies agree | mean `fo1_tpd / ring1x_tstage` = **1.0021** over all 45 corners (max deviation < 1 %) ✅ |
| Ring delay is dominated by self-loading | mean `ring1x_tstage / ring4x_tstage` = **1.015** — 4× wider devices are only 1.5 % faster, i.e. absolute width is a power/area knob, not a frequency knob at fixed fan-out ✅ |
| Corner coverage | 45 rows, every (process, temp, supply) triple present ✅ |

## Column reference (`results/delay_corners.csv`)

| Column | Meaning |
|---|---|
| `process`, `temp_c`, `vdd_v` | corner coordinates |
| `ring1x_fosc_hz`, `ring1x_tstage_s` | 1× ring oscillation frequency and per-stage delay |
| `ring1x_isupply_a` | average ring supply current (free-running) |
| `ring1x_qstage_c`, `ring1x_cstage_f` | supply charge per stage transition, and `Q/Vdd`. Includes short-circuit current, so `cstage` is an **upper bound** on the pure load capacitance |
| `ring4x_*` | same three quantities for the 4×-width ring |
| `fo1_tphl_s`, `fo1_tplh_s`, `fo1_tpd_s` | fan-out-1 stage propagation delays (falling output, rising output, mean) |
| `fo1_tfall_s`, `fo1_trise_s` | 90→10 % and 10→90 % output transition times |
| `idsat_n_1u_a`, `idsat_p_2u5_a` | device drive current at `Vgs = Vds = Vdd` |

## Known limitations

- Single-ended CMOS inverter stage only. If #3 (architecture survey) ratifies a
  current-starved or differential delay cell, re-run with that stage inserted —
  the runner and corner grid are unchanged, only the `.subckt` in the deck moves.
- Nominal skew only (no Monte Carlo / mismatch); see the statistical-switch note
  above.
- Wiring parasitics are not included (no layout yet). Real ring frequency will
  be lower; the **ratio** across corners is far less sensitive to this than the
  absolute value.
