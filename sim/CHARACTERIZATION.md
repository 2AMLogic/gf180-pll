# sim/ — aggregated characterization report

**Purpose.** `sim/README.md` documents each campaign's *methodology* and
migration status; `spec/pll.md`'s summary table states each parameter's
*target* and its overall status (measured / derived / budget / waived). Until
now, nothing pulled every campaign's *headline result* into one place with a
citation a reader can check without opening 19 directories. This report is
that aggregation: one row per `sim/*/records/` campaign directory, each
citing its own current evidence record(s) by path and content hash.

This report does not create new evidence, re-derive any number, or relax
`spec/pll.md`. It transcribes what is already committed under `sim/` and
cross-references it against `spec/pll.md`'s own "Summary table" (line 66) and
"Verification owed" table (line 879) so the two documents cannot silently
disagree about what is and is not substantiated. Where they might read as
disagreeing, that is called out explicitly below rather than resolved in
either direction.

Filed against #147 (part of #127, the T1/bronze gap tracker), per #142/#143's
finding that no such aggregated artifact existed as of this repository's
2026-08-16 T1 re-read.

## How to read this report

- **Coverage.** One entry below for every directory under `sim/` that
  contains a `records/` subdirectory, as of this report's own writing:
  **20 campaign directories, 61 evidence records** total
  (`find sim -maxdepth 1 -type d` / `find sim -path '*/records/*.md' -type f
  | wc -l`), matching `README.md`'s own "61 evidence records across 20
  verification campaigns" line (README.md:23) at the same commit.
- **"Latest record."** Record IDs are `<YYYYMMDD>-<HHMMSS>-<sha>`
  (`sim/README.md`'s naming convention), so a lexicographic sort of
  `records/*.md` gives chronological order for free. Unless noted otherwise
  under a campaign's own entry, "latest" below means the chronologically
  last record in that directory. **This is not always the same as "the
  current, citable record for a given claim"** — several campaigns mint more
  than one live record per directory (a DC bench and a switching bench, a
  raw measurement and a later re-classification, a full-grid record and a
  narrow single-corner diagnostic). Where that applies, the entry cites
  every record actually needed to state the headline result honestly and
  says so.
- **Content hash.** `sha256sum` of the record file itself (first 12 hex
  characters shown; recompute the full digest with
  `shasum -a 256 <path>` or `sha256sum <path>`). This is **not** the
  record's own `<record-id>` git-sha suffix (that names the repo commit the
  run was taken against) — it is a hash of the Markdown file's bytes,
  included so drift or tampering in a nominally append-only file is
  mechanically detectable. Records under `sim/` are never edited after
  creation (`sim/README.md`'s append-only rule), so a hash mismatch against
  this report at any later date means either this report has gone stale
  (the likely case — see "Maintenance" below) or the record's append-only
  guarantee was violated (worth investigating).
- **Status column.** Uses `spec/pll.md`'s own vocabulary where a campaign
  substantiates a numbered spec row (**measured** / **derived** / **budget**
  / **waived**), and a plain description for campaigns whose claim is a
  design-input decision rather than a spec line (`spec/pll.md`'s own
  "design-input claim" form — no ratified spec anchor, referenced by issue
  number instead).
- **What this report is not.** It does not restate every measured number —
  each campaign's record holds the full per-corner tables, raw logs, and
  methodology; this report exists to point at them, not duplicate them. Read
  the cited record for anything beyond the headline.

## Summary table

| Campaign | Latest record (path, sha256 prefix) | Headline result | Spec / issue reference | Status |
|---|---|---|---|---|
| `devchar-delay` | `sim/devchar-delay/records/20260801-084448-01b0db8.md` (`987bc2e2a231`) | Per-PVT-corner current-starved delay-cell drive/delay and ring frequency vs. starving current, 45-point grid. Overall PASS. | #4 → #8 (design-input; feeds VCO stage sizing, no spec anchor of its own) | design-input, measured |
| `devchar-cp` | `sim/devchar-cp/records/20260801-102353-79f398e.md` (`ab2c61a7368c`) | Output resistance and compliance-knee ladder for 6 candidate charge-pump mirror stacks, 45-point grid. Overall PASS. Superseded predecessor `20260731-041340-833292f` still carries one column family (`vcomp_ro50`) and a decimated-curve artifact this migrated record does not reproduce. | #4 → #9 (design-input; feeds CP mirror-stack choice, no spec anchor of its own) | design-input, measured |
| `devchar-passives` | `sim/devchar-passives/records/20260801-102454-79f398e.md` (`a3334ef1c371`) | MIM-vs-MOS-cap C–V linearity, density, and leakage comparison, full passive-corner grid. Overall PASS — feeds the loop-filter cap-type decision (`spec/pll.md#area`). | #4 → #10 (design-input; feeds loop-filter cap choice) | design-input, measured |
| `divider-ratio` *(pre-harness, superseded runner — see caveat below)* | `sim/divider-ratio/records/20260731-171817-0a12e6c.md` (`1de4c63bc587`) | 235-point chain-ratio sweep: 0 of 235 points measured a ratio other than N; 61 distinct N values exercised at 200 MHz. Retiming setup closure at N=64/200 MHz: worst margin **3.03e-10 s (6.1 % of a VCO period)** at `ss`/125 °C/2.97 V — **this is the number `spec/pll.md`'s summary table row 3 cites.** | `spec/pll.md#multiplication-ratio` (row 3); #11 → DR-001 Decision 3 | **measured** |
| `divider-ratio-dff` | `sim/divider-ratio-dff/records/20260801-125114-3f883e3.md` (`135fe22b5a86`) | `dff_tg_3v3` setup/hold/clk→Q across the full PVT grid — the retiming flop's timing-budget input joined into `divider-ratio-chain`'s margin table. Overall PASS. | #11 (design-input; migrated sibling of `divider-ratio`) | design-input, measured |
| `divider-ratio-cell` | `sim/divider-ratio-cell/records/20260801-140529-3f883e3.md` (`0e821b673dc6`) | Single `div23_cell` moduli (÷2/÷3) on both output edges and both input duty cycles, top/bottom of the band, full PVT grid. Overall PASS at every point. | #11 (design-input; migrated sibling of `divider-ratio`) | design-input, measured |
| `divider-ratio-chain` | `sim/divider-ratio-chain/records/20260802-100727-082c879.md` (`2c7911871d5f`) | Full 6-cell chain ratio + retiming setup closure, migrated onto `sim/harness`. Worst setup margin **3.0283e-10 s (6.1 %)** at `ss`/125 °C/2.97 V — reproduces the pre-migration `divider-ratio` number above; worst hold margin 2.00e-09 s. 0 of 17 evaluated points closed with negative margin. | `spec/pll.md#multiplication-ratio` (row 3, reproduces it); #11 → DR-001 Decision 3 | **measured** (migrated) |
| `lock-detector` | `sim/lock-detector/records/20260802-050119-c24ee3a.md` (`6dfe0a46b346`) | Window-comparator assert/deassert behavior at every PVT corner; assert window measured **0.877 … 1.702 ns**, max at `ss`/125 °C/2.97 V. **This is the number `spec/pll.md`'s summary table row 16 cites — the target (window ≥ 2.5 ns) is not met today.** | `spec/pll.md#lock-detector` (row 16); #11 → DR-002 Decision 4 | **measured**; target **not met** |
| `loop-dynamics` | `sim/loop-dynamics/records/20260731-202550-82af5a9.md` (`004d3ad7c9ad`) | Loop-filter component extraction, area (C1 = 0.0303 mm², 20.2 % of the 0.15 mm² budget), the Icp trim-code rule (`spec/pll.md`'s normative "Icp trim-code rule"), and small-signal lock-time estimates (71 µs at f_ref = 1 MHz, structural floor 43 µs — **the number `spec/pll.md`'s summary table row 9 cites**). **Overall: PASS on the contracted operating space, FAIL off it** (i.e. only when the Icp trim-code rule is followed). | `spec/pll.md#loop-bandwidth`, `#phase-margin`, `#lock-time` (rows 8/8a/9), `#area`; #4/#8/#9 → #10 | **measured**, conditional PASS |
| `mc-cp-mismatch` | `sim/mc-cp-mismatch/records/20260817-135712-0e9cfc9.md` (corner-combined; supersedes nothing, additive) — the nominal-only `sim/mc-cp-mismatch/records/20260731-212614-640560e.md` (`b4a7026934b3`) stands as historical evidence, not superseded. | Monte Carlo mismatch-only dispersion, now COMBINED with a 3-point PVT corner subset (`typical/27C/3.30V`, `ss/125C/2.97V`, `ff/-40C/3.63V` — see that record's Corner-matrix field for the reduced-grid justification), closing the T1/bronze checklist gap (#127 item 6) the nominal-only record left open. Worst-corner \|mean\|+3σ across all 3 corners: all 4 `design/README.md` budget-table terms still PASS (11.72 % against ±12 % — term 1's closest margin yet, at `ff/-40C/3.63V`; 303.5 ps against ±3 ns; 4.83 fC against ±20 fC; 912.7 ps against ±3 ns). Feeds the reference-spur derivation (`spec/pll.md#reference-spur`, "Statistical residual net charge" step). | #15, #146; feeds `spec/pll.md#reference-spur` (row 7, derived) | design-input / distribution claim, measured |
| `reference-spur` | `sim/reference-spur/records/20260816-132150-5f405e7.md` (`f99061a2855f`) | First **direct** closed-loop spur measurement in this repository: the ±f_ref sidebands read out of the locked `pll_top` output spectrum at 5 spanning PVT corners (all five MOS bundles, all three temperatures, all three supplies), f_ref = 25 MHz / N = 6 / f_out = 150 MHz / band 6 / Icp code 0. Measured **−57.0 dBc worst** (`sf`/−40 °C/2.97 V) to −72.7 dBc best (`fs`/125 °C/3.63 V) — **PASS against the −55 dBc target at the measured 150 MHz at every corner**; scaled by +2.50 dB to the ratified band's binding 200 MHz the two cold corners read −54.5 and −54.9 dBc and **do not clear the target**, so the overall record verdict is FAIL on that scaled check. Residual settling drift (`drift_q_fc`, −1.60…+2.78 fC against the 2.16–3.68 fC charge-pump asymmetry) is of either sign and is the dominant per-corner uncertainty; the first-to-last-window spread reaches 11 dB. **Taken against a dirty working tree** — see its Netlist provenance field. | `spec/pll.md#reference-spur` (row 7); #145 (part of #127) | **measured** (5 of 45 corners, at 150 MHz); target **not met** once scaled to the 200 MHz binding point |
| `pfd-deadzone` | `sim/pfd-deadzone/records/20260801-234626-5b333d0.md` (`b5372a13006f`) | Dead-zone-freedom criterion (ratio > 0.5 AND both UP/DN pulse at Δφ=0) — PASS at every evaluated corner. Residual net charge at zero phase error reported per corner (feeds reference-spur derivation). | #9; feeds `spec/pll.md#reference-spur` (row 7, derived) | design-input, measured |
| `output-driver` | `sim/output-driver/records/20260817-100354-0e9cfc9.md` (`5c0a60662ab2`) | First loaded (50 fF `CLK` load) duty-cycle and output-levels/edge-rate measurement in this repository, 90 points (all five MOS bundles × 3 temperatures × 3 supplies × the two band/Vctrl edge extremes). Duty cycle **44.375–50.696 %**, target not met at 7/90 points (6 `fs`-bundle, 1 `ff`-bundle, all at the `lo` edge / nominal-or-above supply) — worst 44.375 % at `fs`/27 °C/3.63 V, 0.625 pp below the 45 % floor. V_OH/V_OL **1.006–1.044·VDD_VCO / −0.040…−0.006·VDD_VCO**, PASS at all 90 points. Overall record verdict FAIL (on the duty-cycle checks only). | `spec/pll.md#output-duty-cycle`, `#output-levels-and-drive` (rows 13/14); #144 (part of #127) | **measured** (90 points); duty-cycle target **not met** at 7/90 points, levels/drive target **met** at every point |
| `pll-top-smoke` | `sim/pll-top-smoke/records/20260802-160926-8456ff3.md` (`7dec4f0210c1`) | Assembled-top-level acceptance gate: **7 of 7 checks PASS** (residual frequency error, static phase error, divide ratio, output frequency vs. N·f_ref, LOCK level, Vctrl window, PFD DN-branch integration guard) at a **single nominal corner** (`typical`/27 °C/3.30 V) by design — this is a connectivity/closed-loop-existence check, not a PVT performance claim; see the record's own justification and `sim/README.md`'s "worked example of an acceptable one-point justification." | #52 (design-input; assembly acceptance gate, not a spec row) | design-input, measured (single corner, by design) |
| `output-range` | `sim/output-range/records/20260819-160843-4e32f91.md` (`9beb97b3cc01`) — the full-grid record, **superseding** the single-corner pilot `20260731-223426-640560e`; the `lo`-edge waveform diagnostic `sim/output-range/records/20260801-061907-67d7127.md` (`380369d949c9`) is cited, not superseded (its claim is the waveform diagnosis, not a corner measurement). | Full 45-point PVT grid at both draft band edges, 90 runs, against the `pll_top` DUT (**DUT changed at #159** — not netlist-for-netlist comparable with the two predecessors): **0 of 45 corners reached a sustained in-window PASS at either edge** (83 FAIL, 4 `OUT-OF-WINDOW` where band 7/N=32 cannot reach 200 MHz anywhere inside 0.9–2.7 V Vctrl at 125 °C/2.97 V, 3 ERROR). The 2 µs window is only ~2.5 reference cycles at the `lo` edge, so a `lo` FAIL bounds nothing about eventual lock; PFD DN-branch guard 49 PASS / 0 FAIL / 38 SUSPECT / 3 ERROR. Two ERROR rows are simulator convergence aborts (`sf`/27 °C, `lo`); the third (`ff`/27 °C/3.30 V, `hi`) did not complete in 151 CPU-minutes — #168. | #12; feeds closed-loop output-band coverage (design input, no independent spec row — `spec/pll.md`'s [Output band](#output-band) row 1 is substantiated by `vco-tuning-range`'s open-loop measurement, not by this campaign) | design-input, **measured** (full grid); no lock PASS at either band edge |
| `lock-time` | `sim/lock-time/records/20260801-162534-2a81927.md` (`334ebbb27d75`) | The latest record is a **process/root-cause diagnostic** (fixes a timestep-ceiling bug that crashed the deck; confirms 3 corners run error-free at a deliberately-too-short 10 ns window, expected FAIL). **It makes no PASS/FAIL claim against the mandated 45-point × N-setting closed-loop grid** — that full run (#65 items 2–4) remains open. The lock-time *number* cited by `spec/pll.md`'s summary table row 9 (71 µs / 43 µs floor) comes from `loop-dynamics`'s small-signal estimate, not from this campaign's own closed-loop transient. | #12 / #65; `spec/pll.md#lock-time` (row 9) target owed to this campaign for cold-start acquisition | **gap** — full-grid closed-loop cold-start measurement not yet taken |
| `supply-sensitivity` | `sim/supply-sensitivity/records/20260831-133708-35c5a33.md` (`92c02f50a4a2`) — supersedes the 9-corner `sim/supply-sensitivity/records/20260801-024935-c4fe724.md` (`f72872845501`, #62) and its re-classification `20260801-114140-f87afc5.md` (`f257dbf0bddc`, #69, still cited there for the earlier record's per-row artifact/consistent split). | Full 45-point grid (5 MOS bundles × 3 temperatures × 3 supplies), run at the PFD's 100 ps closed-loop timestep bound throughout (#58). **Criterion 1 (frequency vs. supply) FAIL**: 34/45 corners meet the full lock criterion; worst frequency deviation −240 ppm (`typical`/27 °C/3.63 V). The 11 failures are NOT a settling problem — 0 corners needed the automatic 36.8 µs settling escalation, so the prior 9-corner record's 5/9 unsettled rows do not reproduce at the corrected timestep bound, and nothing here routes to `loop-dynamics` (#10) or `vco-tuning-range` (#8) as a design-margin finding. The 11 failures split as 3 static-phase-error (routes to the post-#24 charge pump, #9) and 8 `lock_detector` window misses (routes to #11, not a loop failure). **Criterion 1b (Vctrl inside DR-001's 0.9–2.4 V window) FAIL**: 4 of 45 corners' ripple peak leaves the window (worst 2.642 V at `ss`/−40 °C/3.63 V). **Criterion 3 (stays locked through a supply step + ramp) FAIL** — first measurement ever taken (#14 reported it NOT MEASURED at every corner): all 3 sampled corners (`ff`/125 °C, `ss`/−40 °C, `typical`/27 °C) show a settled-plateau residual frequency error over the 1e-3 criterion after the step, worst 0.04514 at `ss`/−40 °C, with the `lock_detector` flag briefly going negative there. **Criterion 4 (power vs. the draft <5 mW target) PASS**: 0.9865–1.98 mW across the grid (worst `ff`/125 °C/3.63 V); quiescent/dynamic power split measured for the first time (9 corners), e.g. nominal corner 0.3605 mW quiescent / 1.043 mW dynamic. Open-loop VCO supply pushing (−50.7 %/V worst-case static, cited from `vco-tuning-range`) is *not* re-derived here — this campaign measures the *closed-loop* consequence, a different quantity, and cross-checks consistent with it (§1 "Consistency with #8's open-loop pushing"). | `spec/pll.md#supply-sensitivity` (row 12, pushing figure cited from `vco-tuning-range`, not from this campaign); `spec/pll.md#power` (`vdd_ref` domain current — this record's "core" column); #58 | **measured** (full 45-point grid + step/ramp + quiescent/dynamic split); criteria 1/1b/3 **FAIL**, criterion 4 **PASS** |
| `vco-tuning-range` | `sim/vco-tuning-range/records/20260804-211600-f599a65.md` (`9b2ab6ddf83e`) — the **supply-pushing/jitter** sub-claim (see caveat: this directory now carries 4 live sub-claims from 4 manifests/decks). The **output-band/Kvco** sub-claim's current record is `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` (`6a0c337af4e1`). The **band-select mirror mismatch** sub-claim (new, #146) is `sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md`, a raw `sim/lib/simenv.sh` deck (not a `tb.json` manifest — see that record for the harness-ordering finding making a `params` override of `sw_stat_mismatch` silently ineffective). | Output band: floor 6.449 MHz (`all-fast`/125 °C/2.97 V, 36 % below the 10 MHz line), ceiling 247.8 MHz (`all-slow`/−40 °C/3.63 V, 24 % above the 200 MHz line), 0 non-monotonic curves of 504, worst adjacent-band overlap 27 %. Kvco worst 115.8 MHz/V (`all-fast`/27 °C/2.97 V, band 6) under the band-selection rule. Supply pushing: worst −54.5 %/V (`ss`/−40 °C, band 5) static; ripple sensitivity worst **2.51 % RMS period jitter** at 100 mV pp `vdd_vco` ripple (`all-slow`/−40 °C/2.97 V, band 5) — **the number `spec/pll.md`'s summary table row 5 cites**, and the basis for row 5's conditional-on-ripple-budget framing. Overall PASS on all three sub-decks. **Band-select mirror mismatch** (device-level Monte Carlo, nominal PVT, N=25/band at the two cascade extremes): band 7 (full cascade, highest bias current) disperses 15.4 % of mean (\|mean\|+3σ), comfortably under the 26.8 % worst-adjacent-overlap headroom the systematic sweep measured; band 0 (always-on legs only, lowest bias current) disperses **38.8 %**, which EXCEEDS that headroom — an honest, not-yet-formally-closed finding (order-of-magnitude proxy comparison only, not a matching-corner combined verdict) that random mismatch alone could plausibly erode band 0's coverage margin at the low end of the band plan. No numeric budget exists for this term in `design/README.md`. | `spec/pll.md#output-band`, `#kvco` (rows 1/17); `#period-jitter` (row 5, sensitivity half); `#supply-sensitivity` (row 12, pushing figure); #8, #146 | **measured**; band-select mismatch sub-claim: **measured, with an open finding at band 0** |
| `cp-compliance` | Two current sub-claims: **DC bench** — `sim/cp-compliance/records/20260801-190821-734f483.md` (`c60f07e9b9e7`); **switching-timing bench** — `sim/cp-compliance/records/20260802-061841-c24ee3a.md` (`2e973c1f6c50`). See caveat below on a third, near-duplicate switching record. | DC bench: both current sources stay in saturation across the ~0.9–2.4 V Vctrl window at every corner; UP/DN mismatch and the 2-bit Icp trim range measured (unit-leg currents 1.68–7.21 µA across codes/corners, nominal ≈5.2 µA). Switching bench: effective UP/DN pulse-width skew (`wskew`) measured per (corner, Vctrl); worst-corner asymmetry 3.68 fC (`fs`/125 °C/3.63 V, Vctrl 0.9 V) — **feeds `spec/pll.md#reference-spur`'s derivation directly.** Overall PASS on both benches. | #9; feeds `spec/pll.md#reference-spur` (row 7, derived), the Icp trim-code rule, and `mc-cp-mismatch`'s systematic baseline | design-input, measured |
| `harness-selftest` | `sim/harness-selftest/records/20260731-151931-58c52d9.md` (`b054e15b269c`) | `sim/harness`'s own acceptance testbench (real devices, real 45-point PVT grid, no design claim) — proves the harness resolves the PDK, sweeps corners, and writes a `sim/README.md`-conformant record end to end. Overall PASS. | n/a — harness self-verification, not a design or spec claim | n/a (tooling) |

## Verification-owed cross-check

`spec/pll.md`'s own "Verification owed" table (line 879) lists what the
specification asserts that `sim/` does not yet substantiate. Every row of
that table is disclosed above; this section restates the correspondence so a
reader auditing gap-coverage does not have to cross-reference by hand:

| `spec/pll.md`'s owed item | Disclosed above under | Still open as of this report |
|---|---|---|
| Period jitter — closed-loop / random (noise-driven) jitter | `vco-tuning-range` (open-loop sensitivity substitute) | **yes** — no `sim/period-jitter/` directory exists yet; `sim/README.md`'s own campaign table reserves the slug (#13) with zero records, and `README.md`'s Status section says the same. Not counted among the 18/56 above because it has no `records/` directory to cite. |
| Period jitter — band sweep at non-nominal temp/supply | `vco-tuning-range` | **yes** — the cited ripple-jitter number is one operating point, not a full grid |
| Reference spur — remaining 40 PVT points, and a direct measurement at the binding 200 MHz | `reference-spur` (the measurement itself); `cp-compliance`, `mc-cp-mismatch`, `pfd-deadzone` (the derivation's inputs) | **partially** — the closed-loop measurement now exists at 5 spanning corners at 150 MHz (#145); the other 40 points and the 200 MHz binding frequency are not measured, and the two cold corners do not clear −55 dBc once scaled to 200 MHz |
| Lock time — cold-start acquisition incl. cycle slipping | `lock-time` | **yes** — see the `lock-time` row above; only small-signal settling (via `loop-dynamics`) exists |
| Reference input — thresholds/edge-rate sweep, numeric reference-jitter limit | (no campaign directory covers this — it is an interface *condition*, not a *result*) | **yes** — no `sim/` campaign measures this; `spec/pll.md#reference-input` states it as a budget |
| Power — measured `vdd_ref` domain current, closed-loop total | `supply-sensitivity` (`vdd_ref` == its "core (PFD+CP+LD)" column, and the closed-loop total) | **no longer** — `supply-sensitivity`'s full-grid record (#58) measures both: total power 0.9865–1.98 mW (PASS against the draft <5 mW target) and the `vdd_ref`/core-domain current at every corner, plus the quiescent/dynamic split. `spec/pll.md#power` still states `vdd_ref` as budget-only and has not been updated to cite this measurement (`spec/` changes are out of scope for this report) |
| Output duty cycle — no measurement exists | `output-driver` | **partially** — the measurement now exists at 90 points (#144); the design does not meet its own 45 % floor at 7/90 points (`fs` bundle, `lo` edge, nominal-or-above supply), and post-extraction re-run / the on-die divider load are not yet added |
| Output levels and drive — loaded-output swing/edge-rate | `output-driver` | **partially** — the measurement now exists at 90 points and PASSES at every point (#144); post-extraction re-run / the on-die divider load are not yet added |
| Lock detector — T1/T2 window widening, T4/T5 below 25 MHz | `lock-detector` | **partially** — the window is measured (0.877–1.702 ns) and explicitly does not meet the ≥2.5 ns target; sub-25 MHz T4/T5 characterization is not in the cited record |
| Area — everything except the loop filter | `loop-dynamics` (loop filter only) | **yes** — no floorplan exists (#17), so no other block's drawn area is measured |
| Kvco / Output band — Monte Carlo band-select mismatch, post-extraction re-run | `vco-tuning-range` (schematic-level only) | **yes** — every VCO number cited above is schematic-level (`sim/README.md`'s "Netlist provenance" convention); no post-extraction re-run exists (#18) |
| Multiplication ratio — post-extraction retiming margin at N=64/200 MHz | `divider-ratio`, `divider-ratio-chain` | **yes** — the cited 6.1 % margin is schematic-level; #18 owes the post-layout re-take |

No item from `spec/pll.md`'s Verification-owed table is silently omitted
here; every row above traces to an explicit "still open" note in this
report, in the campaign table, or both.

## Caveats and notes

- **`divider-ratio`'s spec citation is stale relative to the migration, but
  the numbers agree.** `spec/pll.md#multiplication-ratio`'s own "Evidence"
  line still cites the pre-harness `sim/divider-ratio/` records (`#41`
  migrated the campaign onto `sim/harness` by splitting it into
  `divider-ratio-dff`/`-cell`/`-chain`, per `sim/README.md`'s "A one-directory
  experiment can outgrow one `sim/harness` manifest"). As of this report,
  the migrated `divider-ratio-chain` record reproduces the pre-migration
  retiming-margin number exactly (3.03e-10 s / 6.1 %, same binding corner),
  so the two do not disagree — but `spec/pll.md` has not been updated to
  cite the migrated sibling directories. Not fixed here (`spec/` changes are
  out of this issue's scope per its own Guardrails); noted so it does not
  read as an oversight of this report.
- **`cp-compliance` carries an apparent unreconciled duplicate.** Two
  records — `20260802-033728-c24ee3a` and `20260802-061841-c24ee3a` — both
  supersede the same predecessor (`20260731-194124-afa338c`) for the
  switching-timing bench, without either superseding the other. Their
  headline numbers agree closely (same measurement, same grid, run ~2.5
  hours apart). This report cites the later of the two
  (`20260802-061841-c24ee3a`) as current, consistent with the "latest by
  timestamp" rule used throughout, but the lack of an explicit
  Supersedes link between the pair is a minor bookkeeping gap in `sim/`
  itself, not something this report can fix without editing an append-only
  record.
- **Multi-record campaigns.** `cp-compliance` (DC + switching benches) and
  `vco-tuning-range` (output-band/Kvco, stage-count comparison, and
  supply-pushing/jitter, three manifests sharing one experiment directory
  per `sim/README.md`) each carry more than one simultaneously-current
  record. `lock-time` has a
  latest-by-date record that is a narrow diagnostic or re-classification
  rather than the broad measurement — this report cites both the diagnostic
  and the underlying measurement it refers back to in each such case, per
  `sim/README.md`'s own citation convention ("cited, not superseded").
  `output-range` and `supply-sensitivity` were in that list until their
  full-grid records (`20260819-160843-4e32f91`, #159; `20260831-133708-35c5a33`,
  #58) landed: each campaign's latest record is now the broad
  measurement, and the earlier diagnostic (`output-range`'s waveform
  diagnostic; `supply-sensitivity`'s 400 ps-bound re-classification) is the
  one cited alongside it.
- **`pll-top-smoke` and `harness-selftest` are single-corner or non-design
  campaigns by design**, not incomplete PVT sweeps — see their own rows
  above and `sim/README.md`'s "worked example of an acceptable one-point
  justification" for why a single corner is a complete answer to the
  question those two campaigns ask.
- **klayout-tools #309** — the general aggregation-tool issue this repo's
  interim report does not block on (per #147's own Scope item 2) — remains
  open as of this report. If it lands, a follow-up can consider generating
  this report's summary table mechanically instead of by hand; nothing here
  depends on that landing first.

## Maintenance

This report is **hand-maintained**, not generated. It reflects the tree as
of the commit that introduced it; every citation above should be re-checked
against the current tree before being relied on for anything beyond a
quick orientation, and definitely before being cited outside this
repository. `sim/lib/check-characterization-coverage.sh` (added alongside
this report) fails CI if a campaign directory under `sim/*/records/` exists
on disk without a corresponding entry in this report's summary table, so
the two cannot silently drift apart in the "a whole new campaign appeared
and nobody added it here" direction — it does **not** detect a stale
headline number, a hash that no longer matches its record, or a new record
inside an already-listed campaign. Catching those needs either disciplined
re-review at PR time (this report's own diff should be part of any PR that
adds a `sim/*/records/*.md` file with a materially different headline) or
the general aggregation tool tracked at klayout-tools #309, whichever lands
first.
