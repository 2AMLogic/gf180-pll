# gf180-pll

**PRIVATE — 2AM Logic proprietary IP. Canary block (wave 1).**

Integer-N ring-oscillator PLL on gf180mcu (open PDK), designed by agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source analog flow. Dual purpose, per the canary model: catalog
inventory (eventually silicon-measured) and tool forcing-function
(friction issues go to the public klayout-tools tracker).

Selection rationale: Biggest license category and the category leader (Silicon Creations) is absent from this node (matrix row 2).

## Target specification (DRAFT — engineering to ratify, see issue #1)

| Parameter | Target | Stretch |
|---|---|---|
| Ref input | 1–25 MHz | 32 kHz mode |
| Output | 10–200 MHz | 10–400 MHz |
| Period jitter (RMS) | < 1% | < 0.5% |
| Lock time | < 100 µs | < 20 µs |
| Supply | 3.3 V ±10% | 1.8-V core variant |
| Power @ 100 MHz | < 5 mW | < 2 mW |
| Area | < 0.15 mm² | — |
| Multiplier range | ×4–×64 integer-N | fractional-N later |

Maturity ladder: simulation-complete → layout DRC/LVS-clean → shuttle
seat → measured silicon over temperature.

## Layout

```
spec/          ratified spec + decision records
design/        schematics / netlists (xschem)
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```
