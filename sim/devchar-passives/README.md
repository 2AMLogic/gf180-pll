# devchar-passives — loop-filter capacitor and resistor comparison

**Consumers**: issue #10 (loop filter), issue #17 (floorplan). Picks the
loop-filter capacitor type against the area budget and the resistor type
against tempco/spread.

## Re-running

```sh
./run.sh            # both campaigns -> results/*.csv
./run.sh --check    # nominal sections only, summaries printed to stdout
SIM_JOBS=4 ./run.sh # cap parallelism (default: host CPU count)
```

Environment pin and prerequisites: see [`../README.md`](../README.md).

## Corner axes — read this before extending the sweep

Passives in this PDK have their **own** corner sections, completely independent
of the MOS `typical/ff/ss/fs/sf` sections used by `devchar-delay` and
`devchar-cp`:

| Device family | Corner sections |
|---|---|
| MIM caps | `mimcap_typical` / `mimcap_ff` / `mimcap_ss` |
| 3.3 V MOS caps | `moscap_typical` / `moscap_ff` / `moscap_ss` |
| Poly resistors | `res_typical` / `res_ff` / `res_ss` |

A MOS-corner-only sweep would leave every passive at typical and silently
report zero spread. This runner sweeps the passive axes explicitly. Because
each device depends only on its own axis, sweeping the cap axes together at
{typical, ff, ss} still yields each device's complete min/typ/max envelope.

**Supply is not an independent axis here.** The capacitor C–V sweep spans
0 → 3.63 V, the top of the 3.3 V ±10 % range, so it already covers the
control-voltage range at every supply corner; resistors were measured to have
exactly zero voltage coefficient (below).

Temperature grid: {−40, 27, 125} °C, giving 3 sections × 3 temperatures = 9 runs
per deck.

## Capacitors — `tb_cap_cv.sp`

Ten devices, all drawn 30 µm × 30 µm (900 µm²), all driven from one shared node
through individual 0 V ammeters. A linear 0 → 3.63 V ramp in 1 µs gives
`C(V) = i / (dv/dt)` — the true differential capacitance, since `i = dq/dt`,
with **both** `i` and `dv/dt` read back from the simulated waveform. The node
is then held at 3.63 V for a further 1 µs; with `dv/dt = 0` the residual branch
current is leakage.

Results: [`results/cap_summary.csv`](results/cap_summary.csv) (90 rows),
[`results/cap_cv.csv`](results/cap_cv.csv) (full C–V curves, 1800 rows).

### Nominal corner (`mimcap_typical` / `moscap_typical`, 27 °C)

| device | family | density @3.30 V (fF/µm²) | min density 0.3–3.3 V | max density | C–V ratio | leakage @3.63 V (A) |
|---|---|---|---|---|---|---|
| `cap_mim_1f0_m2m3_noshield` | mim | 1.031 | 1.031 | 1.031 | 1.00 | 4.8e−19 |
| `cap_mim_1f5_m2m3_noshield` | mim | 1.521 | 1.521 | 1.521 | 1.00 | 7.7e−18 |
| `cap_mim_2f0_m2m3_noshield` | mim | 2.022 | 2.022 | 2.022 | 1.00 | **6.2e−15** |
| `cap_mim_1f0fF` | mim_legacy | 1.031 | 1.031 | 1.031 | 1.00 | 4.8e−19 |
| `cap_mim_1f5fF` | mim_legacy | 1.521 | 1.521 | 1.521 | 1.00 | 7.7e−18 |
| `cap_mim_2f0fF` | mim_legacy | 2.022 | 2.022 | 2.022 | 1.00 | 6.2e−15 |
| `cap_nmos_03v3` | moscap | 3.983 | 0.088 | 3.983 | **45.4** | ~0 |
| `cap_pmos_03v3` | moscap | 3.958 | 0.047 | 3.958 | **84.6** | ~0 |
| `cap_nmos_03v3_b` | moscap | 3.991 | 3.637 | 3.991 | **1.10** | ~0 |
| `cap_pmos_03v3_b` | moscap | 3.975 | 3.696 | 3.975 | **1.08** | ~0 |

### Density envelope over all corners and temperatures

| device | min (section/°C) | max (section/°C) | total spread |
|---|---|---|---|
| `cap_mim_1f0_*` | 0.9271 (ff/−40) | 1.1355 (ss/125) | 20.2 % |
| `cap_mim_1f5_*` | 1.2811 (ff/−40) | 1.7621 (ss/125) | **31.6 %** |
| `cap_mim_2f0_*` | 1.8174 (ff/−40) | 2.2260 (ss/125) | 20.2 % |
| `cap_nmos_03v3` | 3.5847 (ff) | 4.3813 (ss) | 20.0 % |
| `cap_pmos_03v3` | 3.5622 (ff) | 4.3538 (ss) | 20.0 % |
| `cap_nmos_03v3_b` | 3.5919 (ff) | 4.3901 (ss) | 20.0 % |
| `cap_pmos_03v3_b` | 3.5775 (ff) | 4.3725 (ss) | 20.0 % |

### Headline for #10 / #17

- **The `_b` (well-tied) MOS caps are the density winner and are usable.**
  `cap_nmos_03v3_b` gives **3.99 fF/µm²** — 2.0× the densest MIM
  (`cap_mim_2f0`, 2.02 fF/µm²) and 3.9× `cap_mim_1f0` — while varying only
  **1.10×** over a 0.3–3.3 V control excursion. For a 50 pF filter capacitor
  that is 12.5 × 10³ µm² (0.0125 mm²) versus 24.8 × 10³ µm² (0.0248 mm²) for
  2.0 fF/µm² MIM. Against the 0.15 mm² draft area budget that is 8.4 % of the
  block versus 16.5 %, bought at a 10 % capacitance nonlinearity across the
  control range.
- **The plain MOS caps are not loop-filter capacitors.** `cap_nmos_03v3` swings
  **45×** and `cap_pmos_03v3` **85×** between 0.3 V and 3.3 V (the transition
  knee sits near 0.63 V), so the loop bandwidth would move by more than an
  order of magnitude across the tuning range. They are only usable at a fixed,
  well-above-knee bias.
- **`cap_mim_1f5` has the worst corner spread** (31.6 %) because its
  `mimcap_ss/ff` factors are ±15.5 % where the 1f0 and 2f0 options are ±10 %.
  If a MIM is chosen, `cap_mim_2f0` is strictly better: denser *and* tighter.
- **Leakage is effectively not a differentiator, but not for a reassuring
  reason.** Only `cap_mim_2f0` contains a leakage element at all
  (6.2 fA over 900 µm² at 3.63 V — an equivalent shunt of 585 TΩ, utterly
  negligible against any charge-pump current). `cap_mim_1f0`/`1f5` and **all four MOS caps have no
  conductance element in their subcircuits whatsoever** — the ~5e−17 A in the
  table is solver residual, not a modelled current. A MOS-cap loop filter
  therefore **cannot** be screened for gate-leakage-driven control-voltage
  droop from these models; that needs silicon or a foundry leakage spec.
- **MIM C–V nonlinearity is not modelled either.** The `c_vcr1`/`c_vcr2`
  voltage coefficients are present in `sm141064_mim.ngspice` but the line that
  applies them is commented out in favour of a plain `.MODEL C` card, which is
  why every MIM row above reports a C–V ratio of exactly 1.0000. Treat "MIM is
  perfectly linear" as a model artefact, not a measurement. The coefficients
  themselves are small (order 10⁻⁵ /V), so the real error is minor — but it is
  not zero.
- **MOS caps have no temperature dependence at all** in these models (identical
  density at −40/27/125 °C); MIM caps move only +0.1 to +0.2 % over the same
  range via `tc1`/`tc2`. Cap corner spread is essentially all process.
- **Naming**: the `cap_mim_*fF` names quoted in most gf180 documentation live in
  the `.LIB cap_mim` section of `sm141064.ngspice`, which **no corner section
  includes**. The corner sections (`mimcap_*`) instead pull
  `sm141064_mim.ngspice`, whose devices are named
  `cap_mim_{1f0,1f5,2f0}_m{2m3,3m4,4m5,5m6}_noshield`. This deck includes both
  and confirms they are **electrically identical** (every row above matches to
  all printed digits), and all four metal-pair variants carry identical
  `c_cox`/`c_capsw`. A netlist that instantiates `cap_mim_1f5fF` without an
  explicit `.lib … cap_mim` will fail to elaborate.

## Resistors — `tb_res.sp`

Six poly resistor options, each drawn at **two lengths** (10 µm and 50 µm at
W = 1 µm; `ppolyf_u` additionally at W = 2 µm) so that sheet resistance is
extracted from the slope

```
rsh_eff = (R(50 µm) − R(10 µm)) / (squares between the two lengths)
```

which cancels the contact head resistance; the intercept is reported separately
as `r_head_ohm`. `rsh_eff` differs from the model's `rsh` parameter by
effective-width narrowing, which is exactly why it is measured rather than
quoted. A 0 → 1.0 V DC sweep across each device gives the voltage coefficient.

Results: [`results/res_summary.csv`](results/res_summary.csv) (63 rows),
[`results/res_tempco.csv`](results/res_tempco.csv) (21 rows).

### Sheet resistance spread and tempco (W = 1 µm)

| device | `rsh_eff` ff / typ / ss (Ω/sq) | spread | tempco (ppm/°C) | head R (Ω) |
|---|---|---|---|---|
| `ppolyf_u` | 295.0 / 368.7 / 442.5 | ±20 % | **−75** | 126 |
| `ppolyf_u_1k` | 822.9 / 1028.6 / 1234.3 | ±20 % | −872 | 173 |
| `ppolyf_u_2k` | 1670.0 / 2087.5 / 2505.1 | ±20 % | −1545 | 380–536 |
| `ppolyf_u_3k` | 2348.5 / 3131.3 / 3914.1 | ±25 % | −1545 | 507–799 |
| `npolyf_u` | 263.3 / 326.4 / 389.6 | ±19 % | −1324 | 84 |
| `ppolyf_s` | 1.02 / 7.46 / 15.33 | **−86 % / +106 %** | +3184 | 10 |

`ppolyf_u` at W = 2 µm gives `rsh_eff` = 287.3 / 359.1 / 430.9 Ω/sq — 2.6 %
lower than the W = 1 µm value, which is the effective-width narrowing
(`r_dw = 25.5 nm` per edge) showing up as an apparent sheet-resistance shift.
Use the width you intend to draw.

**Voltage coefficient is exactly zero** for every device (`r_vc1 = r_vc2 = 0`
in all six models), confirmed at every corner: `r_vcoef_pct_per_v` is 0 or
~1e−14 (rounding).

### Headline for #10

- **`ppolyf_u` is the loop-filter resistor.** Its **−75 ppm/°C** tempco is
  11.6× better than `ppolyf_u_1k` (−872) and 21× better than
  `ppolyf_u_2k`/`_3k` (−1545). Over the −40…125 °C range that is a 1.2 %
  resistance change versus 14 % and 25 % — and the loop's damping factor and
  zero frequency both track R directly.
- **The area penalty for choosing `ppolyf_u` is negligible.** At W = 1 µm it
  needs 2.7 µm of length per kΩ versus 1.0 µm for the 1 k option, so a 20 kΩ
  series resistor is ~54 µm² versus ~19 µm². Against a filter capacitor of
  order 10⁴ µm², that difference is noise. **Do not trade tempco for
  resistor area here.**
- Process spread is ±20 % for every unsalicided option, so the loop zero moves
  ±20 % from R alone before the capacitor's own ±10…16 % is folded in. Worst
  case `res_ss` × `mimcap_ss` (or `moscap_ss`) is the corner that sets the
  low-frequency zero; `res_ff` × `*_ff` sets the high one.
- **`ppolyf_s` (salicided) is unusable** and is included only to show why: its
  sheet resistance moves from 1.0 to 15.3 Ω/sq across `res_ff`→`res_ss` (a 15×
  spread) with a +3184 ppm/°C tempco.
- `npolyf_u` is slightly lower-sheet than `ppolyf_u` but has a 17.6× worse
  tempco (−1324 ppm/°C); there is no reason to prefer it here.

## Sanity anchors (test-plan checks)

| Check | Result |
|---|---|
| MIM density matches the model-name rating | 1.031 / 1.521 / 2.022 fF/µm² for the 1.0 / 1.5 / 2.0 fF/µm² options — the excess is the perimeter term `c_capsw` on a 30 µm × 30 µm draw ✅ |
| Extracted `rsh_eff` matches the model `rsh` parameter | `ppolyf_u` typ: 368.7 Ω/sq measured vs `rsh_ppolyf_u = 350` nominal, the +5.4 % being the 25.5 nm/edge width narrowing on a 1 µm draw ✅ |
| High-sheet options land on their nominal sheet | 1028.6 / 2087.5 / 3131.3 Ω/sq vs 1000 / 2000 / 3000 nominal ✅ |
| Head resistance matches the terminal model | `ppolyf_u` intercept 126 Ω vs 2 × 60 Ω/sq × (1 µm / 0.949 µm) modelled ✅ |
| C–V covers the full control range, not one bias | curves span 0.02–3.62 V at ~50 mV archive resolution ✅ |
| Passives swept on their own corner axes | `mimcap_*`, `moscap_*`, `res_*` all explicitly swept; MOS `tt/ff/ss/fs/sf` deliberately not used ✅ |
| Corner coverage | caps 10 devices × 3 sections × 3 temps = 90 rows; resistors 7 device/width combinations × 3 × 3 = 63 rows ✅ |

## Known limitations

- Nominal skew only (`sw_stat_global = sw_stat_mismatch = 0`). Capacitor and
  resistor **matching** (ratio accuracy between the filter's own components)
  needs a Monte Carlo campaign; the `res_statistical_par` and `mc_c_cox_*`
  hooks are present in the PDK for it.
- No layout parasitics: MIM bottom-plate-to-substrate capacitance and resistor
  substrate coupling (`fox_sub`, `c1`/`c2` in the resistor subcircuits) are in
  the models but their loading depends on the actual routing.
- Leakage and MIM C–V nonlinearity are under-modelled in this PDK — see the
  headline notes above. Any loop-filter droop budget must be flagged as
  unverifiable from models alone.
