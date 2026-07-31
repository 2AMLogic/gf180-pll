# devchar-cp — charge-pump mirror output resistance and compliance

**Consumer**: issue #9 (PFD / charge pump). Picks the CP output device stack and
shows how much of the supply rail is actually usable as VCO control voltage
before the pump loses current accuracy or output resistance.

## Re-running

```sh
./run.sh            # full 45-point grid -> results/cp_summary.csv + cp_curves.csv
./run.sh --check    # nominal corner only, summary printed to stdout
SIM_JOBS=4 ./run.sh # cap parallelism (default: host CPU count)
```

Environment pin and prerequisites: see [`../README.md`](../README.md).

## Measurement topology

`tb_cp_mirror.sp` instantiates six candidate output stacks, all biased from the
same 20 µA reference and all tied — each through its own 0 V ammeter — to a
single swept node. One DC sweep of that node from 0 V to Vdd (10 mV steps)
therefore traces the **complete** output characteristic of every stack at one
corner, through the saturation knee and into triode. Nothing is inferred from
the flat region alone.

| Stack | Topology | Role |
|---|---|---|
| `n_simple` | 2-transistor NMOS mirror | CP sink (down pulse) |
| `n_casc` | self-biased NMOS cascode (stacked diode reference) | CP sink |
| `n_ws` | wide-swing (low-voltage) NMOS cascode, W/4 bias diode | CP sink |
| `p_simple` | 2-transistor PMOS mirror | CP source (up pulse) |
| `p_casc` | self-biased PMOS cascode | CP source |
| `p_ws` | wide-swing PMOS cascode, W/4 bias diode | CP source |

Sizing: NMOS `W = 5 µm`, PMOS `W = 15 µm`, `L = 1 µm`, cascode bias diode at
1/4 aspect ratio, `Iref = 20 µA`. The widths put both polarities in **moderate
inversion** (`Vdsat` 0.17–0.29 V n, 0.20–0.29 V p over the whole grid) — the
regime a charge pump actually uses. Deep weak inversion would flatter every
compliance number in this table; deep strong inversion would waste headroom.
All four numbers (`iref`, `wm`, `wmp`, `lm`) are `.param`s at the top of the
deck.

`.option abstol=1e-16 reltol=1e-7` is set because output resistance is
extracted from ~10 pA current differences; at the ngspice default
`abstol = 1e-12` every number above ~10 MΩ would be solver noise.

### Extracted metrics

| Metric | Definition |
|---|---|
| `ro_30/50/70pct_ohm` | `dVout/dIout` (central difference on the 10 mV grid) at 30 %, 50 %, 70 % of Vdd |
| `vcomp_i1pct_v`, `vcomp_i5pct_v` | walking from mid-rail toward the rail the stack works against, the last output voltage at which `Iout` is still within ±1 % (±5 %) of its mid-rail value |
| `vcomp_ro50_v` | output voltage at which `ro` has fallen to 50 % of its mid-rail value |
| `headroom_*` | the same boundary as a distance from the stack's own rail (ground for `n_*`, Vdd for `p_*`) |

Compliance is referenced to the **mid-rail** current, not to the current at the
extreme of the sweep: a simple mirror's current never stops climbing with Vout,
so a "99 % of the value at the rail" definition would report a meaningless
number for it.

`vcomp_ro50` is the metric that matters for a cascode. A cascode keeps
delivering an accurate *current* well past the point where its *output
resistance* has already collapsed to that of a simple mirror — the current
knee alone would make a cascode look far better than it is in a loop where
CP output impedance sets the up/down current mismatch versus control voltage.

## Corner grid

process {`typical`, `ff`, `ss`, `fs`, `sf`} × temp {−40, 27, 125} °C × supply
{2.97, 3.30, 3.63} V = **45 points × 6 stacks = 270 rows**, all run.

## Results

- [`results/cp_summary.csv`](results/cp_summary.csv) — 270 rows of extracted metrics
- [`results/cp_curves.csv`](results/cp_curves.csv) — the complete `Iout(Vout)` and
  `ro(Vout)` characteristic of every stack at every corner (50 mV archive grid,
  differentiated on the raw 10 mV grid), 18 000 rows

### Nominal corner (typical / 27 °C / 3.30 V)

| stack | `ro` @ mid-rail (MΩ) | headroom, ±1 % current (V) | headroom, `ro`-50 % (V) | mirror gain |
|---|---|---|---|---|
| `n_simple` | 2.31 | 1.20 | 0.50 | 1.0177 |
| `n_casc` | 653.6 | 0.63 | 1.33 | 1.0000 |
| `n_ws` | 25.3 | 0.41 | 0.74 | 1.0017 |
| `p_simple` | 3.47 | 1.06 | 0.73 | 1.0101 |
| `p_casc` | 554.0 | 0.72 | 1.48 | 1.0000 |
| `p_ws` | 25.6 | 0.46 | 0.90 | 1.0014 |

### Worst case over all 45 corners

| stack | min `ro` @ mid-rail (corner) | max ±1 % headroom (corner) | max `ro`-50 % headroom (corner) |
|---|---|---|---|
| `n_simple` | 1.9 MΩ (ff/−40/2.97) | 1.43 V (ff/−40/3.63) | 0.62 V (ss/125/3.63) |
| `n_casc` | 337.8 MΩ (ss/125/2.97) | 0.76 V (ss/−40/2.97) | 1.49 V (ss/125/3.63) |
| `n_ws` | 19.4 MΩ (ff/125/2.97) | 0.53 V (sf/125/3.30) | 0.89 V (ss/125/3.63) |
| `p_simple` | 3.0 MΩ (sf/−40/2.97) | 1.20 V (ff/−40/3.63) | 0.80 V (ss/27/3.63) |
| `p_casc` | **39.7 MΩ** (ss/−40/2.97) | 0.84 V (ss/−40/3.30) | 1.62 V (ss/−40/3.63) |
| `p_ws` | 22.0 MΩ (ff/125/2.97) | 0.54 V (fs/125/3.63) | 1.00 V (ss/125/3.63) |

### Headline for #9 — worst-case usable output window

Combining the N sink and the P source of the same family gives the control
voltage range over which **both** are simultaneously in compliance,
`Vdd − headroom_N − headroom_P`, minimised over all 45 corners:

| stack family | window, ±1 % current criterion | window, full-`ro` criterion |
|---|---|---|
| simple | 0.88 V (fs/−40/2.97) | 1.70 V (ss/125/2.97) |
| self-biased cascode | 1.38 V (ss/−40/2.97) | **0.16 V** (ss/125/2.97) |
| **wide-swing cascode** | **1.90 V** (ss/125/2.97) | **1.23 V** (ss/125/2.97) |

The wide-swing cascode wins on both criteria and is the recommended starting
point for #9. Concretely:

- **The self-biased cascode is a trap.** Its 550–650 MΩ mid-rail output
  resistance is the best in the table, but it needs ~1.3–1.6 V of headroom per
  side to sustain it, so on a 2.97 V supply at ss/125 °C there is only 0.16 V of
  control range where both sides hold full `ro`. Note also `p_casc` mid-rail
  `ro` collapsing to **39.7 MΩ** at ss/2.97 V — at that supply, mid-rail *is*
  its compliance edge.
- **The simple mirror is not enough**: 1.9–3.9 MΩ output resistance, and ~1 %
  current asymmetry between the up and down sources (gain 1.010–1.028 for
  `n_simple`/`p_simple` versus 1.001–1.003 for the wide-swing stacks). Up/down
  current mismatch of that order directly sets reference spur level.
- **Wide-swing cascode**: 19–32 MΩ (≈10× the simple mirror) for 0.33–0.54 V of
  headroom per side, and mirror gain within 0.34 % of unity everywhere.
- The wide-swing stacks are biased with a textbook 1/4-aspect diode, which puts
  the lower device's `Vds` almost exactly at its own `Vdsat`. That is why their
  `ro` (≈25 MΩ) is well below the `gm·ro²` a cascode can reach: the lower
  device sits on its knee. Adding bias margin (a slightly larger bias-diode
  aspect, or a separate `Vov`-referenced bias) trades some of the 0.33–0.54 V
  headroom back for output resistance. That trade sits in #9, not here.

### Sanity anchors (test-plan checks)

| Check | Result |
|---|---|
| Mirror ratios are ≈1 at every corner | gain 0.9999–1.0279 across all 270 rows ✅ |
| `ro` drops toward the compliance edge | e.g. `n_casc` nominal: 653.6 MΩ at mid-rail → 3.79 MΩ at 30 % of Vdd ✅ |
| Curve passes *through* the knee, not just the flat region | `cp_curves.csv` starts at `Vout = 0` and ends at `Vout = Vdd` for every stack, so both the triode region and the saturation plateau are recorded ✅ |
| Cascode `ro` ≫ simple-mirror `ro` | 337–830 MΩ vs 1.9–3.9 MΩ ✅ |
| Corner coverage | 6 stacks × 45 corners = 270 summary rows, no gaps ✅ |

## Known limitations

- DC only. Switching behaviour of the CP (charge injection, clock feedthrough,
  current glitch on switch turn-on) is a #9 deliverable, not a device-level one.
- Nominal skew, no Monte Carlo — up/down current *mismatch* here is systematic
  (Vds-induced), not statistical. Random mismatch needs a separate MC campaign.
- The cascode bias branches are idealised (`Iref` from an ideal current source).
  A real bias network adds its own PVT sensitivity.
- `ro` values above ~1 GΩ approach the resolution of a 10 mV finite difference
  even at the tightened tolerances; treat anything ≥ 1 GΩ as "> 1 GΩ".
