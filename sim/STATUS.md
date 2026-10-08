# Campaign status narrative

Long-form status of the closed-loop and block-level verification campaigns,
moved here verbatim from the `README.md` status section so the front page can
stay a scannable summary. The summary table in [`README.md`](../README.md) is
the entry point; this page is the detail behind its "Verification" and
"Closed-loop bring-up" rows. The machine verdict of record remains
[`signoff/tier-report.json`](../signoff/tier-report.json), and each
campaign's own latest record under `sim/*/records/` is the evidence itself.

The counts and coverage figures on this page and in the README table are
graded against the tree in CI by `sim/lib/check-readme-status.sh`.

- **Done** — architecture and scope captured as numbered decision records in
  `spec/`; xschem schematics for the VCO, PFD, charge pump, feedback divider,
  lock detector, and the shared 3.3 V logic cells they are built from; a
  reproducible PVT corner harness; **106 evidence records** across 28
  verification campaigns (device characterization, VCO tuning range, PFD
  dead-zone freedom, charge-pump compliance and mismatch, divider moduli,
  lock-detector window, its sizing ladder and its trim-code map, loop
  dynamics, the closed-loop
  reference spur measured from the output spectrum, the loaded output
  driver's duty cycle and levels/drive, and a first pass at the other
  closed-loop campaigns: lock-time, output-range, supply-sensitivity, and
  period-jitter).
- **Not done** — closed-loop bring-up. `pll-top-smoke`'s latest record
  (`20260802-160926-8456ff3`, superseding the earlier FAIL) is an **overall
  PASS, 0 of 7 checks failed** at the single nominal corner (`typical` / 27 C /
  3.30 V) it is deliberately scoped to. Three of the four closed-loop
  campaigns have since taken the full PVT grid against the same assembled
  `pll_top` DUT, and the honest news is mixed: `lock-time`'s 270-run grid
  (45 corners × N ∈ {4, 16, 64} × {cold, relock}) reaches a sustained
  in-window `LOCK` PASS on 21/135 cold-start rows and 1/135 relock rows — the
  rest are read as the test window being too short, not as a broken loop, but
  that reading is not yet a closed PASS bound; `output-range`'s full 45-point
  grid reaches **0/45** sustained in-window PASS at either drawn-band edge;
  `supply-sensitivity`'s full 45-point grid (plus all three step/ramp corners)
  PASSes on power (0.99–1.98 mW, under the 5 mW draft target) but FAILs three
  of its other four criteria at real corners. Its record named
  `loop-dynamics` (#10), `lock-detector` (#11) and the post-#24 charge pump
  (#9) for each class of finding, and all three of those issues later closed,
  leaving the findings recorded but unowned (#506). DR-021 re-read each one
  against the ratified spec line — arithmetic on the same committed grid, no
  new simulation — and two of the three are not what the record's headings
  say: the frequency-vs-supply FAIL contains **no** failing frequency check
  (3.4× and 4.4× headroom), and is the static-phase finding DR-012 owns; the
  `VCTRL`-window FAIL is graded against a control window DR-003 superseded,
  while the budget the spec ratifies — never graded before — was **missed at
  9 of 15 corner cells** against its original 0.6 V figure (worst 1.41 times,
  53 mV of window left) because that figure priced half the rail excursion;
  DR-037 (#525) makes the full range govern and re-derives it as 1.2 V, met at
  15 of 15, pending two-key ratification; and
  the step+ramp FAIL is a hold ≈8 µs short of a measurably slew-limited
  recovery rather than an under-damped loop. Each now has a named open owner:
  #525, #511, #399, #437 and #405. See each campaign's own latest record under
  `sim/*/records/` for the full accounting. `period-jitter`'s
  **deterministic (control-ripple) component now covers 45 of the mandated 45
  PVT corners** — the complete 3 × 3 temperature × supply plane at all five
  MOS bundles (`typical`, `ff`, `ss`, `fs`, `sf`), ranging **0.0508 % RMS**
  (`ss` / 125 °C / 3.30 V) to **0.2691 % RMS** (`typical` / −40 °C / 3.63 V),
  every point inside the 1.0 % target with at least 3.7× margin. Two things it
  does **not** cover, stated rather than left to be inferred: the campaign's
  own Acceptance Criteria (#13) also require a **random/noise-driven** jitter
  component, which no analysis this toolchain offers can *estimate* (DR-020,
  narrowed by DR-023: the flow reports per-device noise PSDs at a bias point,
  but has no periodic-steady-state noise analysis to carry them over the ring's
  oscillation cycle). It is now **bounded** instead —
  `spec/decision-records/DR-032-random-period-jitter-bounded-over-the-grid.md`:
  `sim/period-jitter/random-bound/` injects a noise source across every device
  of the ring and output buffer, each sized at the maximum of that device's own
  noise density over the oscillation cycle, which can only over-state the
  jitter, and folds flicker in through the closed loop; it bounds the VCO's
  bias generator — the largest term — by a small-signal analysis about its DC
  point, and the loop-filter resistor separately. The
  result is **≤ 0.338 % RMS at all 45 mandated PVT corners** — an upper
  bound, not an estimate — against the 0.50 % RMS the target's own ripple
  derivation leaves for it. The charge pump, PFD, divider and lock detector,
  in-band sources this term does not inject, are bounded separately
  (`spec/decision-records/DR-033-in-band-random-period-jitter-bounded-over-the-grid.md`:
  `sim/period-jitter/in-band-bound/`, ≤ 0.0249 % RMS at all 45 points, a
  headroom of 15.8× against the margin the term above leaves) — so the whole
  random half is **≤ 0.3388 % RMS at all 45 points**, combined in quadrature.
  The impulse-sensitivity-function route to an *estimate* has its ingredients built
  and validated (`sim/period-jitter/isf-bringup/`, DR-030;
  `sim/period-jitter/sid-trajectory/`, DR-031) but not assembled, and the bound
  does not need it. The target itself is unchanged. And every one of the campaign's records is at one output
  frequency, 150 MHz — the same measurement at the 200 MHz top of the
  ratified band is declared as `sim/period-jitter-band-top`, tracked at #503,
  and carries no measured record yet. The **reference spur** is in the same
  position and matters more, because that is the frequency its ≤ −55 dBc line
  is stated at: the one closed-loop spur record is 5 of the 45 PVT corners at
  150 MHz, and scaling it to 200 MHz puts the two coldest corners 0.1–0.5 dB
  *over* the line. The binding-frequency sweep is declared as
  `sim/reference-spur-band-top` — all 45 points, none measured — tracked at
  #533, and DR-024 re-points the spec's owed line off the closed issue that
  used to hold it.
