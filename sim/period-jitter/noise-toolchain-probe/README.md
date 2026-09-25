# `period-jitter` noise-toolchain probe

**This directory measures the simulator, not the design.** It mints no
evidence record, it is not a verification campaign, and no number in it
describes this PLL. It exists so that
[`DR-023`](../../../spec/decision-records/DR-023-random-period-jitter-owner-and-cyclostationary-gap.md)'s
claims about what `ngspice` can and cannot do here are **reproducible** rather
than asserted — the same standard `sim/` holds design claims to.

Run it:

```sh
sim/period-jitter/noise-toolchain-probe/run.sh
```

Single-corner (`typical`/27 °C) and sub-minute by construction. A PVT sweep
would be meaningless: whether a simulator command exists does not depend on
temperature.

## Why it was written

`sim/period-jitter`'s six records measure the **deterministic**
(control-ripple) component of period jitter at all 45 mandated PVT corners.
None measures the **random** (noise-driven) component, and each says so in its
own Limitations field, citing a methodology gap: DR-002 Decision 5 specifies a
transient-noise run, `TRANNOISE` does nothing on this build, and turning
`trnoise()` into a device-noise-equivalent figure "needs a noise-PSD
calibration this repository has not done."

That last clause is the one DR-023 had to test. Read plainly it suggests the
device noise PSDs are themselves unavailable. **They are not.** Probe 3 below
found that `.noise` decomposes its result per device *and* per mechanism, and
that the gf180mcu BSIM4 models populate every one. The gap is real but it is
somewhere else, and naming the right place is what lets issue #520 be scoped
into work someone can actually start.

## The four probes and what they returned

Measured on `ngspice-46` (`/home/ubuntu/.local/bin/ngspice`) against
`gf180mcuD`, 2026-09-25. Captured output is in [`logs/`](logs/).

| # | Deck | Question | Result |
|---|---|---|---|
| 1 | [`probe_trannoise.sp`](probe_trannoise.sp) | Does `.option TRANNOISE=1` inject device noise into a `.tran`? | **No.** `v(n1)` is bit-for-bit flat over 10 µs — `vspan` is exactly `0.000000e+00` on a 100 k/100 k divider whose thermal noise would be plainly visible if injected. |
| 2 | [`probe_trnoise.sp`](probe_trnoise.sp) | Does the explicit `trnoise()` PWL source work? | **Yes.** `trnoise(1m 1n 0 0)` gives a measured 0.865 mV RMS. It synthesizes a waveform from an amplitude the deck supplies; it knows nothing about any device. |
| 3 | [`probe_device_noise.sp`](probe_device_noise.sp) | Does `.noise` give per-device, per-mechanism PSDs for gf180mcu models? | **Yes — 28 per-device vectors**, including `…m0.id` (channel thermal) and `…m0.1overf` (flicker), plus terminal-resistance noise. |
| 4 | [`probe_pss.sp`](probe_pss.sp) | Is a periodic-steady-state analysis available? | **No.** `pss: no such command available in ngspice`. No PSS ⇒ no Pnoise. |
| 3b | [`probe_sid_bias.sp.in`](probe_sid_bias.sp.in) | How much do those generators move across the bias the ring actually traverses? | **Channel thermal 46.6 dB, flicker 95.9 dB** in PSD between V_gs = 0.30 V and 3.30 V. |

Probe 3b, on the ring stage's own switching nfet (`nfet_03v3`, L = 0.28 µm,
W = 2 µm — exactly as drawn in `design/netlist/vco.spice`), at V_ds = 1.65 V,
1 MHz:

| V_gs (V) | I_d (A) | channel thermal (V/√Hz) | flicker (V/√Hz) |
|---|---|---|---|
| 0.30 | 1.479e-09 | 1.917e-14 | 7.920e-16 |
| 0.60 | 2.091e-06 | 6.296e-13 | 1.017e-12 |
| 0.90 | 4.511e-05 | 1.814e-12 | 1.053e-11 |
| 1.20 | 1.343e-04 | 2.497e-12 | 1.600e-11 |
| 1.65 | 3.005e-04 | 3.115e-12 | 2.189e-11 |
| 2.40 | 6.023e-04 | 3.699e-12 | 3.353e-11 |
| 3.30 | 9.598e-04 | 4.084e-12 | 4.946e-11 |

## The conclusion these support

Probes 3 and 4 together are the finding. The **calibration input exists** —
ngspice will hand over each device's thermal and flicker generators at a bias
point. The **bridge does not**: `.noise` linearizes about one *fixed* DC
operating point, while the ring's devices swing rail-to-rail twice per
oscillation and their generators move by tens of dB along that trajectory
(probe 3b). Weighting stationary device PSDs over a periodic large-signal
trajectory is what a PSS/Pnoise pair does, and probe 4 shows this build has
neither.

So the honest statement is not "there is no noise machinery." It is: **nothing
in this toolchain carries the device PSDs ngspice does give over the
oscillation cycle**, and bridging that is methodology development, tracked at
**#520**.

## Caveats this probe states rather than hides

- **Probe 3b sweeps V_gs at fixed V_ds.** The real device traverses a
  two-dimensional (V_gs, V_ds) trajectory. The measured spans are therefore a
  **lower bound** on the true cyclostationary variation — conservative in the
  direction DR-023 argues.
- **The spans include the subthreshold point** (V_gs = 0.30 V, I_d = 1.5 nA).
  That is deliberate: a ring stage device *is* off for much of each cycle, and
  a method that ignores the off state has assumed its answer. Across the
  conducting points alone (V_gs 0.90 → 3.30 V) the spans are smaller but still
  far from flat — 7.1 dB thermal, 13.4 dB flicker.
- **Units.** ngspice's `noise2` (integrated) vectors are in V RMS, not V². The
  runner asserts this every pass: the 1 Ω sense resistor's own
  `onoise_total_rs_thermal` must equal `sqrt(4kTR·1Hz)` = 1.2875e-10 to within
  1 %, and the run aborts if it does not. Squaring is how a PSD is obtained
  from these numbers, and the dB figures above are `20·log₁₀` of an amplitude
  ratio for that reason.
- **This is one process corner.** Absence of a simulator command is
  corner-independent; the *magnitudes* in probe 3b are not, and nothing here
  should be quoted as a device characterization. `sim/devchar-*` is where that
  would belong, and building `S_id(V_gs, V_ds)` properly is part of #520's
  alternative (A).
