# Chipalooza Challenge #5 (GF180MCU / Wafer.Space) — integer-N PLL proposal

Submission target: Open Circuit Design's Chipalooza Challenge #5 (GF180MCU
test chip fabricated through Wafer.Space), 3.3 V digital / 5.0 V analog rail
structure, same as Challenge #3 unless that challenge's own rules page states
otherwise. This repository has not observed a published, dated submission
deadline for Challenge #5 as of this document's writing — none is asserted
here; the operator submitting this proposal should confirm the current
deadline directly against the challenge's own rules page before emailing it.

**Source repository**: `2AMLogic/gf180-pll` (public, Apache-2.0 — see §8).
Every number in §5 is transcribed from this repository's own append-only
`sim/` evidence, with a dated citation to the record it came from — nothing
here is asserted without a re-runnable testbench, per `CLAUDE.md`'s "no claim
without a testbench."

This document is written to be emailed verbatim as the block's public
proposal. It contains no personal or institutional identifiers; a designer
CV and a test-equipment list, if needed, are separate attachments the
submitting operator supplies outside this repository.

**Maturity note, stated up front rather than left for a reader to discover.**
This repository is, at the time of writing, **schematic-complete and
partway through block-level layout**: **4 of the 4 PLL sub-blocks** have a
committed, DRC-clean transistor-level GDS, **4 of the 4 are LVS-matched**,
and there is **no assembled `pll_top` GDS** (§6). Every §5 number is
therefore a *schematic-level* simulation result: no extracted-netlist
post-layout re-verification exists, because there is no top level to extract.
This proposal documents the block honestly at that maturity: §5's
target-specification table reports what the schematic-level `sim/` evidence
shows, marks every row met or unmet against `spec/pll.md` (**ratified with
amendments** on 2026-09-08 via #1, with two rows explicitly carved out and
still unratified — see §5.0), and does not assume or forward-cite work that
has not happened. Top-level assembly, top-level DRC/LVS closure, and
post-layout re-verification are open items (§7), each tracked by its own
issue in this repository, not silently implied by this document's existence.

---

## 1. Type of IP block

An integer-N, ring-oscillator, Type-II charge-pump phase-locked loop:
current-starved 5-stage ring VCO (8 overlapping geometric bands), a
phase-frequency detector and charge pump, a fixed passive R–C loop filter
with a 2-bit charge-pump current trim, a cascaded ÷2/3 feedback divider
(integer N = 4–64), and a digital phase-window lock detector. Architecture is
captured in
[`spec/decision-records/DR-001-pll-architecture.md`](../../spec/decision-records/DR-001-pll-architecture.md).
That record's own Status line still reads **proposed**, as almost every
decision record in this repository does — DR-007, the spec-review verdict,
is the only one re-stamped **ratified** when issue #1 closed. The target
specification those records feed, [`spec/pll.md`](../../spec/pll.md), is
itself **ratified, with amendments** (#1, closed 2026-09-08), and §5's
verdicts are stated against that ratified table rather than against the
individual records' status fields. See §5.0 for the two rows the
ratification explicitly carved out.

---

## 2. I/O list, including test ports

### 2.1 Rails: this design is 3.3 V-only and does not yet exercise the Challenge's 5.0 V rail

Per [`spec/pll.md`](../../spec/pll.md)'s "Supply range" row (target #18), this
block is built **exclusively** on gf180mcu's 3.3 V thick-oxide devices
(`nfet_03v3`/`pfet_03v3`) — DR-002 Decision 3 explicitly rejects a dual-flavor
design, and the 1.8 V core variant is deferred past v1. **No 5.0 V-class
device (`nfet_06v0`/`pfet_06v0`) appears anywhere in `design/`.** This is the
single most load-bearing disclosure in this proposal: the Challenge #5 brief
asks that "analog blocks should operate across 3.3–5.0 V," and this design,
as it exists today, does not — it would need a design extension (most
plausibly, an on-die 5.0 V→3.3 V regulation stage, or simply leaving the
analog 5.0 V rail unconnected and drawing every domain from the digital
3.3 V rail with the harness's approval) before it exercises that rail at all.
Nothing in §5 reports a measurement above 3.63 V, and no row in §5 is stated
as "met" against a 5.0 V condition it was never run at.

### 2.2 Pad table, mapped to the Challenge #5 slot budget

`design/pll_top.sch`'s exported port list
(`design/netlist/pll_top.spice`, `.subckt pll_top REF B0 B1 B2 CPB0 CPB1 LDT0
LDT1 LDT2 LDT3 P0 P1 P2 P3 P4 P5 SEL0 SEL1 SEL2 SEL3 SEL4 SEL5 IBN ICN IBP
ICP CLK DIVOUT FB LOCK VCTRL + VDD VDD_VCO GND_VCO VDD_DIV VSS`) is the port
list this table maps, unedited, onto the Challenge #5 budget (per Epic #542: one
bandgap-referenced bias voltage, up to 2 bandgap-referenced current sources,
up to 24 digital control inputs, up to 12 digital test outputs, up to 4
shared analog lines, up to 4 dedicated pads, SPI control documented in the
harness).

| Signal(s) | Dir | Challenge slot | Count used | Notes |
|---|---|---|---|---|
| `VDD`, `VSS` | supply | 3.3 V digital rail | — (rail) | PFD, charge pump, `cp_dumpbuf`, lock detector domain (`vdd_ref` in `spec/pll.md`'s naming) |
| `VDD_VCO`, `GND_VCO` | supply | 3.3 V digital rail (proposed — see §2.1) | — (rail) | VCO bias/ring/output-buffer domain, kept electrically separate from `VDD`/`VSS` by design (DR-001 Decisions 2–3) specifically so ring switching noise does not couple into the reference domain; **must not be tied to the same physical rail node as `VDD` on the harness board**, even though both are proposed at 3.3 V |
| `VDD_DIV` | supply | 3.3 V digital rail (proposed — see §2.1) | — (rail) | ÷2/3 chain, output mux, retiming flop domain — kept separate from the other two for the same reason |
| `REF` | in | digital control input (budget ≤ 24) | 1 of 24 | Reference clock, CMOS square wave, rising-edge triggered, 1–25 MHz (`spec/pll.md#reference-input`); duty cycle 30–70 % (only pulse-width margin, not sampled phase, is duty-sensitive — the PFD's edge detectors fire on the rising edge only) |
| `B0`, `B1`, `B2` | in | digital control input | 3 of 24 | VCO band select (3-bit, 8 bands). **Static configuration only** — no on-chip auto-calibration FSM exists (DR-001 Decision 2); a system must apply the [band-selection rule](../../spec/pll.md#band-selection-rule) itself |
| `CPB0`, `CPB1` | in | digital control input | 2 of 24 | Charge-pump current trim (2-bit, 4 codes). **Not discretionary** — required to be set from `f_ref` per the [Icp trim-code rule](../../spec/pll.md#icp-trim-code-rule) |
| `LDT0`…`LDT3` | in | digital control input | 4 of 24 | Lock-detector window trim (4-bit, 16 codes). **Not discretionary** — required to be set once per part at test, from that part's own measured comparator-window delay, per the normative [Lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule) (DR-014, DR-015). Same static-configuration idiom as `CPB0`/`CPB1`; nominal/unprogrammed code is 1000 (8) |
| `P0`…`P5`, `SEL0`…`SEL5` | in | digital control input | 12 of 24 | Feedback-divider configuration: `P5..P0` is each ÷2/3 cell's per-cycle mode; `SEL5..SEL0` is a one-hot chain-length code. Together they set `N = 2^k + Σ P_j·2^j (j<k)` for one-hot `SEL_(k-1)=1`, covering the ratified N = 4–64 range. Static configuration; the loop re-locks after any change (no glitch-free on-the-fly modulus switching, DR-001 Decision 3) |
| `IBN`, `ICN`, `IBP`, `ICP` | in | **does not fit the ≤ 2 bandgap-referenced current-source budget — open item, see §7** | 4 requested vs. 2 offered | Charge-pump / bias-mirror reference currents. **Every closed-loop `sim/` record in this repository drives these from ideal current sources at 4× the unit-leg current** — the bias generator that would derive them from a single bandgap-referenced current is "a separate, unbuilt block" (every closed-loop evidence record's own Limitations field says so verbatim). This is not a Challenge-specific gap invented for this proposal; it is a standing, disclosed limitation of the design today |
| `VCTRL` | analog, iopin | shared analog line (budget ≤ 4) | 1 of 4 | Loop-filter control voltage — a slow-moving DC/low-frequency analog test point, well suited to a multiplexed line. Usable window 0.9–2.7 V (DR-003 Decision 5) |
| `CLK` | out, dedicated | dedicated pad (budget ≤ 4) | 1 of 4 | PLL output clock, 10–200 MHz continuous across the 8 bands. **Needs a low-resistance, dedicated path** — a shared-mux line's added series resistance and capacitance would degrade the measured edge rates and duty cycle (`spec/pll.md#output-duty-cycle`, `#output-levels-and-drive`) directly |
| `LOCK` | out | digital test output (budget ≤ 12) | 1 of 12 | Digital lock-status flag from the phase-window comparator (DR-002 Decision 4). See §5's Lock detector row for the two disclosed gaps in this signal's own assert/deassert behavior — it is a real, measured signal, not an idealized one |
| `DIVOUT`, `FB` | out | digital test output (budget ≤ 12) | 2 of 12 (proposed) | Divider-chain diagnostic taps: `DIVOUT` is the one-hot-muxed chain output before retiming, `FB` is the retimed signal actually fed back to the PFD. Exposing both as test outputs (rather than only `FB`) lets a bench test independently check the divider's raw ratio against the retiming flop's contribution — proposed, not load-bearing; a minimal test plan could omit `DIVOUT` |

**Totals against the Challenge #5 budget**: 0 of 1 bandgap-referenced bias
voltage (this block draws no bandgap reference of its own — see the `IBN`/
`ICN`/`IBP`/`ICP` row), **4 requested vs. 2 offered** bandgap-referenced
current sources (open item, §7), 22 of ≤ 24 digital control inputs (18 without
the lock-detector trim; `LDT0`–`LDT3` add 4, leaving 2 slots of headroom — see
DR-015), 1–3 of ≤ 12 digital test outputs (`LOCK` alone, or `LOCK`+`DIVOUT`+`FB`),
1 of ≤ 4 dedicated pads, 1 of ≤ 4 shared analog lines. Every category **except
the current-source count** fits inside budget with real headroom; the
current-source mismatch is the one place this design does not fit the
harness as specified, and it is stated as such rather than glossed over.

### 2.3 What's dropped, multiplexed, substituted, or new relative to this repo's own port list

- **Nothing in `design/pll_top.sch`'s port list is dropped.** Every pin the
  schematic exposes is mapped to a slot above.
- **No pin is proposed as new** relative to the schematic — `DIVOUT` and `FB`
  are both already top-level pins of the committed design, simply optional
  as *test* outputs versus load-bearing feedback. **`LDT0`–`LDT3` are the
  same case, not a third one**: they are neither dropped nor newly added
  relative to this repo's own port list — they already exist as top-level
  `pll_top` ports (PR #418, commit `bfde9893`), mapped above in the exact
  same static-configuration-input idiom `CPB0`/`CPB1` already use (see
  DR-015).
- **`SPI control` does not apply.** This block has no addressable
  configuration register — its 21 configuration bits (`B0..B2`, `CPB0..1`,
  `LDT0..3`, `P0..5`, `SEL0..5`) are static levels, not an SPI-programmed
  state, and nothing in `design/` implies an SPI interface. A harness wrapper
  that drives these 21 lines from its own SPI-to-parallel shift register
  (rather than 21 dedicated harness pins) is a harness-side integration
  detail, not a change to this proposal's I/O list. (`REF`, the reference
  clock, is deliberately excluded from this count — it is a continuously
  toggling signal, not a static configuration level — which is why this
  count is one less than §2.2's "22 of ≤ 24 digital control inputs" total.
  The prior revision of this sentence read "18 configuration bits" for the
  17-bit set that existed before `LDT0`–`LDT3` were pins at all — an
  off-by-one that predates this change and is corrected here alongside the
  `LDT0`–`LDT3` addition.)
- **The 4-vs-2 current-source shortfall (§2.2) is the one real gap.** Closing
  it needs a bias-generator sub-block this repository has never designed —
  either a real bandgap-referenced current mirror producing all four
  polarities/magnitudes on-die from the harness's ≤ 2 supplied currents, or
  a negotiated harness accommodation. Neither exists today; see §7.

---

## 3. Functional description

`REF` (1–25 MHz CMOS) and the divider's feedback edge (`FB`) drive a
phase-frequency detector (`design/pfd.sch`) whose UP/DN outputs steer a
charge pump (`design/cp.sch`) into a fixed passive R–C loop filter
(`design/loop_filter.sch`, R ≈ 77 kΩ / C1 ≈ 121 pF / C2 ≈ 2.0 pF at typical
27 °C), producing the control voltage `VCTRL` that sets the frequency of a
5-stage current-starved ring VCO (`design/vco.sch`) across 8 overlapping
geometric bands (`B0`–`B2`) spanning 10–200 MHz at v1. The VCO's output
(`CLK`, buffered through a tapered three-stage inverter chain) also drives a
cascaded ÷2/3 feedback-divider chain (`design/divider_chain.sch`, six
identical ÷2/3 cells plus a one-hot output mux and a VCO-clocked retiming
flop) that divides the output down to `FB`, closing the loop at the
configured integer ratio N = 4–64. A digital lock detector
(`design/lock_detector.sch`) monitors the PFD's UP/DN outputs through a
phase-error window comparator and asserts `LOCK` once the error has stayed
inside a fixed window continuously long enough to charge a Schmitt-triggered
integrating node — a passive monitor, not a self-calibration mechanism. The
charge-pump current trim (`CPB0`/`CPB1`) is a required, not discretionary,
configuration input: because the loop filter is a single fixed passive
network, the trim is what lets one filter cover the full 25:1 reference-
frequency range while holding ≥ 45° phase margin (the [Icp trim-code
rule](../../spec/pll.md#icp-trim-code-rule)).

The complete top-level assembly (`design/pll_top.sch`) is verified, at one
nominal corner, to acquire and hold lock from a real frequency error
(`sim/pll-top-smoke/records/20260802-160926-8456ff3.md`, all 7 checks PASS).
Most of the circuitry described above also exists as drawn geometry: **4 of
the 4 PLL sub-blocks** the layout effort partitions this design into — VCO,
PFD + charge pump, divider chain, lock detector — have a committed,
standalone-DRC-clean transistor-level GDS, and **4 of the 4 are
LVS-matched**. No GDS exists for the assembled top level, nor for the
passive loop filter (whose area in §5 is computed from the sized devices
rather than measured off geometry); §6 gives the per-block table, the
evidence paths, and what those two absences rule out.

---

## 4. Bench test plan

All measurements below use only the pads in §2.2 — `REF`, `B0..B2`,
`CPB0..1`, `P0..5`/`SEL0..5`, `CLK`, `LOCK`, and (optionally) `DIVOUT`/`FB`;
none require the Challenge's shared analog mux beyond `VCTRL`.

1. **Bring-up / DC sanity.** Power `VDD`, `VDD_VCO`, `VDD_DIV` (all proposed
   at the Challenge's 3.3 V digital rail, §2.1) with `VSS`/`GND_VCO` tied at
   a single low-impedance ground reference. Confirm `VCTRL` sits inside its
   0.9–2.7 V usable window at a chosen static `B0..B2` code with no `REF`
   applied.
2. **Open-loop VCO characterization.** With the loop broken (or `REF` held
   static so the PFD does not drive the charge pump), sweep `VCTRL` from an
   external source across each of the 8 band codes and measure `CLK`'s
   frequency, confirming each band's range and Kvco against
   `spec/pll.md#kvco`'s per-band table.
3. **Divider ratio check.** Drive `FB`/`DIVOUT` from a known `CLK`-rate input
   (or observe them directly with the loop closed) and confirm the measured
   ratio matches the programmed `P0..5`/`SEL0..5` code, across the N = 4–64
   range.
4. **Closed-loop lock acquisition and lock time.** Apply `REF` at a chosen
   frequency with the matching `B0..B2` (band-selection rule) and `CPB0..1`
   (Icp trim-code rule) codes, release the loop from a cold start, and
   measure the time to `LOCK` assertion and to the output frequency settling
   to within the target tolerance. Compare against
   `spec/pll.md#lock-time`'s small-signal 71 µs / 43 µs-floor figures and
   against this proposal's own §5 disclosure that the closed-loop cold-start
   PVT grid has not yet demonstrated a sustained in-window PASS at most
   simulated corners.
5. **Output band, duty cycle, and levels.** Sweep every band code across the
   available supply/temperature range on the daughterboard (environmental
   chamber or temperature-controlled socket) and compare `CLK`'s frequency
   range, duty cycle, and levels against `spec/pll.md`'s Output band,
   Output duty cycle, and Output levels and drive rows.
6. **Reference spur and jitter.** With the loop locked, capture `CLK`'s
   spectrum and measure the ±`f_ref` sideband level against the −55 dBc
   target (`spec/pll.md#reference-spur`); measure period jitter directly on
   a scope/TIA against the 1.0 % RMS draft target
   (`spec/pll.md#period-jitter`) — this bench measurement would be the first
   *closed-loop, full-PVT* period-jitter data point this design has, since
   `sim/period-jitter`'s own evidence today covers the full mandated 45-point
   PVT matrix but its deterministic component only, all at band 6 / 150 MHz
   (§5, §7). Measuring at the 200 MHz top of the band is therefore of
   particular interest on silicon: no simulation in this repository bounds
   closed-loop jitter there.
7. **Lock detector window and chatter.** Perturb the loop (a small `REF`
   frequency step) and observe `LOCK`'s deassert/reassert behavior against
   `spec/pll.md#lock-detector`'s targets, particularly near the bottom of
   the 1–25 MHz reference range where the design's own evidence flags T4/T5
   as unverified.
8. **Repeat across the daughterboard's available supply/temperature range**
   and record any deviation from §5's simulated PVT grid as a genuine
   silicon finding requiring a new, dated `sim/` record — not folded
   silently into this document, per this repository's evidence-trail
   convention.

---

## 5. Target specification at the Challenge #5 rails (3.3 V; the 5.0 V rail is unexplored)

### 5.0 Citation convention and ratification status

Every row below cites a specific, dated `sim/` record from this repository.
**`spec/pll.md` is status "ratified, with amendments" (issue #1, closed
2026-09-08)** — ratified through this repository's ratification-via-PR
policy, with **two rows explicitly carved out and still unratified** per
DR-007 Amendment A1: [Lock time](../../spec/pll.md#lock-time) (row 9) and
[Lock detector](../../spec/pll.md#lock-detector) (row 16). Row 16's original
T1′/T2′ contradiction has since been resolved (#411 trims the comparator
window; see that row below), but the carve-out stands because T4/T5 remain
uncharacterized below 25 MHz and the row now also rests on a normative trim
rule. Rows marked MET/UNMET below are stated against the ratified targets
except those two, which are stated against the draft and say so. This table
re-derives
min/typ/max directly from the underlying `sim/` evidence rather than treating
`spec/pll.md`'s own summary table as settled, and flags, row by row, where
newer full-PVT-grid closed-loop evidence postdates and updates what
`spec/pll.md`'s own table cites. All evidence is **schematic-level — no
extracted layout parasitics exist yet**, because there is no assembled
top level to extract (§6, §7); everything is at the 3.3 V digital rail only,
since no 5.0 V device exists in this design (§2.1).

| Parameter | v1 draft target | Measured / derived (3.3 V) | Verdict | Source (dated) |
|---|---|---|---|---|
| Output band | 10–200 MHz continuous | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V); ceiling 247.8 MHz (`all-slow`/−40 °C/3.63 V); 0 non-monotonic curves of 504; worst adjacent-band overlap 27 % | **MET** (open-loop characterization) | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Output band, **closed-loop** | Same, at any legal (N, band, `f_ref`) | Full 45-point PVT grid at both drawn-band edges (90 runs, `pll_top` DUT): **0 of 45 corners reach a sustained in-window PASS at either edge** | **UNMET / open finding** — closed-loop band-edge settling has not yet been demonstrated within the campaign's own measurement window at any corner | `sim/output-range/records/20260819-160843-4e32f91.md` (full grid); `sim/output-range/records/20260819-190341-70a4128.md` (supersedes that record's single `ff`/27 °C/3.30 V `hi` row only, replacing a hand-killed ERROR with a reproducible CAPPED/stall characterization — still not a PASS) |
| Multiplication ratio | N = 4–64, every integer | 61 distinct N exercised at 200 MHz, 0 ratio errors of 235 chain points; worst retiming setup margin 6.1 % of a VCO period (`ss`/125 °C/2.97 V) | **MET** | `sim/divider-ratio/records/20260731-171817-0a12e6c.md` (chain), sibling flop/cell records same date |
| Integrated RMS jitter | not spec'd (DR-002 Decision 5) | n/a by design — never presented as a spec'd figure | **N/A, by design** | `spec/pll.md#integrated-rms-jitter` |
| Period jitter (open-loop sensitivity) | ≤ 1.0 % RMS, conditional on ≤ 20 mV pp `vdd_vco` ripple | Worst 2.51 % RMS at 100 mV pp ripple (`all-slow`/−40 °C/2.97 V, band 5); implies 0.50 % RMS at the 20 mV pp budget, leaving headroom for an unmeasured random component | **derived, conditional PASS** at the stated ripple budget | `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md` |
| Period jitter, **closed-loop, deterministic (control-ripple)** | Same 1.0 % RMS line | **All 45 of the mandated PVT points now measured**, at one operating point throughout (f_ref = 25 MHz, N = 6, f_out = 150 MHz, band 6, Icp code 0 — the same as `reference-spur`): the complete temperature × supply plane (−40/27/125 °C × 2.97/3.30/3.63 V) at every one of the five MOS bundles (`typical`, `ff`, `ss`, `fs`, `sf`). Range **0.0508–0.2691 % RMS** across all 45 — worst `typical`/−40 °C/3.63 V, best `ss`/125 °C/3.30 V, a 5.3× span, unchanged by the last 16 points (`fs`/`sf` span 0.0903–0.2472 % RMS, inside those bounds). Temperature is monotone at every bundle (hotter is better) — the finding from `typical`/`ff`/`ss` extends cleanly to `fs`/`sf`. The supply trend does not resolve into a clean two-valued-by-process-sign picture, though: `ff` falls and `ss` rises with supply, `fs` mostly rises (dipping slightly at −40 °C: 0.1903 → 0.1876 → 0.2097 %), and `sf` falls gently at −40 °C like `ff` (0.2472 → 0.2463 → 0.2454 %) but rises at 27 °C and dips at 125 °C — the "sign flips cleanly by process" reading from `ff`/`ss` alone does not fully generalize. One caveat is reported rather than smoothed over: one of the five records' **overall status is FAIL**, because 2 of its 18 points fail a lock gate that is not wrap-safe — both loops are demonstrably locked (`fout` within 160 ppm of target, measured N = 6.000, jitter in family with their neighbours) and the gate's phase samples wrapped by exactly one reference period. That is a measurement defect, filed as issue #273, not a jitter result | **MET at every measured corner (45/45), with a 3.7× margin at the worst of them** — but **no record of this campaign varies the output band**: every point is at band 6 / 150 MHz, so nothing here yet bounds jitter at the 200 MHz top of the ratified band — see the row immediately below | `sim/period-jitter/records/20260905-192724-a2ba48f.md` (first, `typical` only); `sim/period-jitter/records/20260906-015602-f9bef9d.md` (adds `ff`/`ss`/`fs`/`sf`); `sim/period-jitter/records/20260906-024225-12bccda.md` (adds the `typical` temperature × supply plane); `sim/period-jitter/records/20260906-063728-f3c9c23.md` (adds the `ff` and `ss` planes; overall FAIL, see #273); `sim/period-jitter/records/20260906-080511-69b36ef.md` (adds the `fs` and `sf` planes' remaining 16 points, completing the matrix; overall PASS) |
| Period jitter, **closed-loop, deterministic, at the 200 MHz band top** | Same 1.0 % RMS line | **No measured record yet — declared, not measured.** `sim/period-jitter-band-top` is the row above's measurement moved to the binding end of the ratified band: same deck structure, same solver tolerances, same reduction module (loaded, not copied), f_ref and the Icp trim code held, N 6 → 8, f_out 150 → 200 MHz. Its full 45-point grid is declared and every point's operating point is derived from the committed VCO record `20260804-162735-72883fb` under [the band-selection rule](../../spec/pll.md#band-selection-rule), re-checkable without a simulator. One result did come out of that derivation and needs no simulator: **at 200 MHz the rule does not select a single band code across the PVT grid** — band 6 at 34 of the 45 points, band 7 at the other 11 (the cold and/or high-supply points where band 6's own curve tops out below 200 MHz) — where at 150 MHz one static code covers all 45. Local Kvco at the selected points spans 74.7–117.0 MHz/V, all inside the Kvco row's 150 MHz/V bound, but the loop gain the one fixed filter sees varies 1.6× across this grid against 1.05× across the 150 MHz one | **UNMET — explicitly.** No jitter number at 200 MHz is claimed anywhere in this document. The band split above is a derivation from committed open-loop evidence, reported as such, and is not a substitute for the measurement | `sim/period-jitter-band-top/testbench/` (manifest, deck and derivation; `band_and_vstart_from_vco_record.py --check`); `sim/vco-tuning-range/records/20260804-162735-72883fb` (the f(Vctrl) table it reads); issue #13 |
| Period jitter, **closed-loop, random/noise-driven** | Same 1.0 % RMS line | **Zero records.** None of the five deterministic-component records above measures this — a disclosed methodology gap (DR-002 Decision 5; ngspice `TRANNOISE` produces no injected noise on this repo's pinned build, and turning its `trnoise()` PWL source into a credible device-noise-equivalent figure needs a noise-PSD calibration this repository has not done). Tracked at issue #13 | **UNMET — explicitly, not omitted.** This is the one row this proposal cannot report a number for at any maturity | issue #13 (open) |
| Phase noise | not spec'd (DR-002 Decision 5) | n/a by design | **N/A, by design** | `spec/pll.md#phase-noise` |
| Reference spur | ≤ −55 dBc | −57.0…−72.7 dBc measured at 150 MHz (5 spanning corners); scaled to the binding 200 MHz, the two coldest corners land at −54.5/−54.9 dBc (0.1–0.5 dB over the line) | **PASS at 150 MHz (5/5 corners); UNMET at the scaled 200 MHz binding point for 2/5 corners** — 5 of 45 PVT points measured, not the full grid | `sim/reference-spur/records/20260816-132150-5f405e7.md` |
| Loop bandwidth | 26–430 kHz over the ratified space, `f_c < f_ref/10` | 25.96–429.5 kHz measured; worst realized `f_c/f_ref` = `f_ref/13`, inside the ceiling at every point of the cross-product | **MET** | `sim/loop-dynamics/records/20260731-202550-82af5a9.md` |
| Phase margin | ≥ 45° in the contracted (trim-rule) space | Worst 47.4° at `f_ref` = 1 MHz, 4 legs; 105/140 cells pass unconditionally, all 35 failures are off-rule trim codes | **MET** (in the contracted space) | Same record |
| Lock time (small-signal settling) | < 100 µs | Worst 71 µs (`f_ref` = 1 MHz, 4 legs); structural floor ≈ 43 µs; 120/140 cells meet the line, 0/140 meet the dropped < 20 µs stretch | **MET** (settling estimate only — not cold-start) | Same record |
| Lock time, **closed-loop cold-start / worst-case re-lock** | Same < 100 µs line, cold-start basis | Full 270-run grid (45 corners × N ∈ {4,16,64} × {cold, relock}): sustained in-window `LOCK` PASS on **21/135** cold rows and **1/135** relock rows within the tested window; the remainder read as window-too-short (not necessarily non-convergent) per the record's own DN-branch integration guard (255/270 PASS, confirming the transient itself resolved correctly on those rows) | **UNMET as a closed PASS bound** — real evidence now exists where `spec/pll.md` still lists this as "budget," but it does not establish that most corners lock inside any stated time | `sim/lock-time/records/20260831-052456-effc505.md` |
| Power | < 5 mW at 100 MHz, locked | Derived total ≈ 1.98 mW at the binding corner (`all-fast`/125 °C/3.63 V) from the open-loop/interpolated basis `spec/pll.md#power` uses | **MET** (derived) | `spec/pll.md#power`, underlying `sim/vco-tuning-range` |
| Power, **closed-loop measured** | Same line | Full 45-point grid + all 3 step/ramp corners: **0.9863–1.98 mW measured directly** (not derived), all points under the 5 mW target; quiescent/dynamic split reported per corner | **MET, measured** — supersedes the derived figure above with a direct closed-loop measurement | `sim/supply-sensitivity/records/20260901-155456-46b92f8.md` |
| Standby current | waived — no power-down mode in v1 | n/a — no standby state exists | **N/A, by design** | `spec/pll.md#standby-current` |
| Supply sensitivity — AC (ripple) budget | `vdd_vco` ripple ≤ 20 mV pp | Derived from the 2.51 %/100 mV pp measured sensitivity above | **derived, conditional** | `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md` |
| Supply sensitivity — DC / closed-loop, full grid | ≤ 0.6 V of the `VCTRL` window consumed by a rail excursion; stays locked through a supply step + ramp | Full 45-point grid: **frequency-vs-supply criterion FAILs on 10/45 corners** (worst −294 ppm); **`VCTRL`-window criterion FAILs on 4/45** (worst 2.642 V, past the 2.4 V edge, at `ss`/−40 °C/3.63 V); **step+ramp criterion FAILs** at 1 of 3 sampled corners even after both settling-time escalations run to completion (`ss`/−40 °C, a genuine finding routed to `loop-dynamics`, #10) | **UNMET on 3 of 4 measured criteria** — a real, disclosed design-margin finding, not a settling-window artifact (both escalations ran to full length) | `sim/supply-sensitivity/records/20260901-155456-46b92f8.md` |
| Output duty cycle | 45–55 % at `CLK`, full band, all corners | 44.375–50.696 % measured (90 points, loaded); 7/90 points below the 45 % floor, all at the low-frequency band edge, concentrated in the `fs` process bundle | **UNMET at 7/90 points** (small excursion, 0.625 pp worst-case) | `sim/output-driver/records/20260817-100354-0e9cfc9.md` |
| Output levels and drive | V_OH ≥ 0.9·VDD_VCO, V_OL ≤ 0.1·VDD_VCO into ≤ 50 fF | V_OH 1.006–1.044·VDD_VCO, V_OL −0.040…−0.006·VDD_VCO, 90/90 points | **MET**, full 90-point grid | Same record |
| Area | ≤ **0.30 mm²** total — **amended by DR-016** (issue #456) from the draft ≤ 0.15 mm², on the measurement in the next column | **Measured at the block level, and the spec row is now amended to it.** Every sub-block's as-drawn footprint, taken from the committed GDS bounding box rather than a hand-recorded figure: loop filter 0.0369 mm² (still a calculation — the loop filter has no placed-and-routed layout yet), VCO 0.0318 mm² (172.52 × 184.48 µm), PFD + charge pump 0.0256 mm² (344.98 × 74.30 µm — it was 0.0353 mm² before the #455 fold, 0.0267 mm² before the #469 glue-bus packing and 0.0264 mm² before the #473 glue-inverter interleave), divider chain 0.0553 mm² (1317.66 × 41.99 µm — it was 0.2471 mm² as first drawn and came down 78 % through the #341 routing-track-packing, #344 row-fold, #454 macro-track-packing and #458 route-over-the-device-rows passes), lock detector 0.0306 mm² (294.80 × 103.75 µm — grown ~4.1× from 0.0075 mm² by issue #449, which drew DR-014's 4-bit trim network into `delaywin_3v3` and, with it, the block's first LVS match against its own ratified schematic). Sum **0.1803 mm²**, or **0.2254 mm²** after the floorplan's own ×1.25 top-level-overhead factor (it was 0.2186 / 0.2733 mm² when DR-016 was written; #469's glue-bus packing, #458's route-over-the-device-rows pass and #473's glue-inverter interleave have taken 38,324 µm² off since, without moving the row) | **MET against the amended row — 0.2254 mm², 75.1 % of ≤ 0.30 mm² — and 1.50× over the draft 0.15 mm² target, which is now *measured* to be unreachable rather than merely unmet.** DR-016 is the amendment and the honest reading of it is this: the draft number was never derived from anything (DR-007 Amendment A3 called it "the one `budget` row in the table with no rationale behind the number at all"), and the 78.6 % of it that had no estimate of any kind is now four committed, DRC/LVS-clean block layouts. Three measured bounds, each tighter than the last, and none reaching 0.15 mm²: as drawn **1.50×** (1.82× when DR-016 was written; #469, #458 and #473 have since landed, below); every remaining named layout lever at its geometric ceiling **1.20×**; and — the one that settles it — **every Metal2 track routed at zero area cost, 1.13×**, a bound that survives any row fold and covers every lever this design has. 57.2 % of what a 0.15 mm² row allowed is consumed by two terms no post-layout lever touches: the loop filter (set by DR-006's C1/C2 *capacitance*, so reducing it is a loop-dynamics change) and `vco_block`, whose height *is* its device band and whose 60.8 % whitespace is the guard-ring and 15 µm tap-pitch spacing the foundry deck requires. The amended row is the measured total plus margin sized to the single unmeasured factor in it (it holds for a top-level overhead up to ×1.664 on the sum as drawn today), **not** an allowance for block growth — and the reduction work stays open (an unnamed `lock_detector` lever), each *material* landing being grounds for a successor record amending the row back *down*. Three levers have landed since DR-016 and none has moved the row: #469's glue-bus packing, at 259 µm², and #473's glue-inverter interleave, at 776 µm², do not clear that bar on their own; **#458** does — it routed the divider chain's Metal2 tracks into the plane over its own device rows, 0.0926 → 0.0553 mm² (74.4 % of its sized ceiling), DRC-clean on both decks and still LVS-matched, moving the total 1.82× → 1.51× under an unchanged row. The divider-chain packing lever (#454) is already spent: packing the `div23_cell` macro's own Metal2 track band (31 nets onto 11 tracks, the provable minimum) took that block from 0.1321 to 0.0926 mm², moving the total from 2.03× to 1.70× on its own. Shared-diffusion device stacking — which this proposal previously named as *the* cause — remains worth only **0.10 %** of the (now larger) gap, falsified rather than deferred, because the divider chain's drawn diffusion is ~1 % of its own bounding box. The `pfd_cp` fold (#455) is spent as well, taking that block 0.0353 → 0.0265 mm² and the total from 1.89× to 1.82× (and #469's glue-bus packing plus #473's glue-inverter interleave have since taken it to 0.0256 mm², a further 0.5 % of the total — "Known gaps" item 8) — but it landed at **42 % of its sized ceiling**, and the shortfall was measured to be in the ceiling (a flat 57-track census over five levels of composition, of which `pfd_cp` owns 4) rather than in the execution. `lock_detector`'s own new footprint is not yet levered against at all. Earlier revisions of this row projected a post-lever floor of 1.64×, then 1.54×; both carried `divider_chain`'s pre-#454 ceiling, and re-derived from the current audit the figure is the 1.20× above — *better* than the record had been carrying, and still over (PLL-FLOORPLAN.md §5.11). §5.13 adds one caveat to that ceiling: `max(packed-track floor, device band) × width` assumes a block's tracks occupy an exclusive band, which is exactly what #458 stopped being true for `divider_chain`, so that block's term in any future ceiling sum has to come from its device band (0.0347 mm²) instead. A fourth lever, sized against `lock_detector`'s own newly-measured 65.5 % whitespace, is still not named. Note this is a **sum of block extents, not a placed-and-routed top level** — no assembled `pll_top` GDS exists, so top-level routing and inter-block spacing are not in this number, and that is exactly the uncertainty the amended row's margin is sized to | `spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md` (the amendment); `layout/evidence/area-audit/PROOF.md` (every lever's arithmetic; reproduce with `python3 layout/run_pv.py area`); `layout/floorplan/PLL-FLOORPLAN.md` §5.1–§5.14 (the re-derived budget); `layout/evidence/vco-layout/PROOF-381-high-rs-resistor.md`; `layout/evidence/pfd-cp-layout/PROOF.md` + `PROOF-455-fold.md` + `PROOF-469-glue-bus-packing.md` + `PROOF-473-glue-inverter-interleave.md`; `layout/evidence/divider-chain-layout/PROOF-macro-track-packing.md` + `PROOF-over-device-rows.md`; `layout/evidence/lock-detector-layout/PROOF.md` "Addendum 4"; `spec/pll.md#area` |
| Lock detector | assert window within **1 … 2 ns** of phase error at every PVT point (T1′/T2′, DR-010/DR-013), measured at the `lock` flag rather than at the bare delay chain; hysteresis ≥ 25 % of window (T3); deassert ≤ 1 `f_ref` period (T4); no chatter 1–25 MHz (T5). **Conditioned on the [lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule)** | Re-characterized in situ on the trimmed `delaywin_3v3` cell (DR-014, #411): window edge **[1.14, 1.16) ns** at `fs`/−40 °C/3.63 V and **[1.78, 1.80) ns** at `ss`/125 °C/2.97 V, each at the code the trim rule selects, PVT spread **1.53–1.58×** against DR-013 Decision 4's ≤ 1.65×. 0 of 205 points fail the four-check acceptance; worst deassert latency 5.63 ns. The **untrimmed** cell sat at [2.02, 2.04) ns with a 1.91–1.96× spread — outside the band at every fixed code | **T1′/T2′ MET, conditional on the trim rule** — this row supersedes this proposal's earlier "T1/T2 UNMET" reading, which predated #411. **T4/T5 still UNMET/uncharacterized below 25 MHz.** Two things a reader must not miss: an **untrimmed part is outside this specification**, and the trim code table is schematic-level and mismatch-free, so the rule is not yet proven against a real trimmed part. `spec/pll.md` keeps this row inside DR-007 Amendment A1's ratification carve-out for exactly those reasons | `sim/lock-detector/records/20260919-002812-1b12179.md` (the 205-point in-situ verdict); `sim/lock-window-trim/records/20260917-185928-8adff3d.md` (the 1872-point code map the trim rule's table comes from); `sim/lock-window-sizing/records/20260915-202802-79c0cee.md`; superseded predecessor `sim/lock-detector/records/20260731-162119-0a12e6c.md` |
| Kvco | ≤ 150 MHz/V under the band-selection rule | Worst 115.8 MHz/V (`all-fast`/27 °C/2.97 V, B6); an adversarial band choice reaches 154.3 MHz/V, over the line, which is why the rule is normative | **MET**, conditional on the band-selection rule being followed | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Supply range | 3.3 V ± 10 %, 3.3 V devices exclusively | Every campaign above sweeps 2.97/3.30/3.63 V | **MET, as the swept independent axis of every other row** | `spec/pll.md#supply-range` |
| Supply range, **5.0 V analog rail** | Challenge #5 asks analog blocks to operate across 3.3–5.0 V | **No 5.0 V-class device exists in this design; never simulated above 3.63 V** | **UNMET / not attempted** — the single most load-bearing gap in this proposal, stated plainly per §2.1 | This proposal, §2.1 |

No row above is relaxed, narrowed, or omitted to make it pass — the `period-
jitter` random/noise-driven row, the `output-range` closed-loop row, three of four
`supply-sensitivity` criteria, the lock-detector T1/T2/T4/T5 gaps, and the
5.0 V-rail row are all reported UNMET, exactly as the underlying evidence
states, per `CLAUDE.md`'s "agents do not relax the ratified spec to make
results pass."

---

## 6. Layout, DRC/LVS, and post-layout status

**Block-level layout exists; top-level layout does not.** `layout/` holds a
proven, `klt`-aware DRC/LVS flow (issue #16,
`layout/evidence/inv-tb-proof/PROOF.md`) validated on a trivial
standard-cell inverter test cell — including a demonstrated catch of a
deliberately injected DRC violation and LVS mismatch — and that flow has
since been run against this design's own sub-blocks. **4 of the 4 PLL
sub-blocks** now have a committed, standalone-DRC-clean transistor-level
GDS, and **4 of the 4 are LVS-matched** against an independently derived
reference netlist:

| Sub-block | Top cell | As-drawn footprint (committed-GDS bounding box) | DRC | LVS | Evidence |
|---|---|---|---|---|---|
| VCO (#293, folded at #324, mirror re-arrayed at #336, resistor re-shaped at #381) | `vco_block` | 172.52 × 184.48 µm (0.0318 mm²) | clean | **matched** | `layout/evidence/vco-layout/` (`PROOF-fold.md`, `PROOF-2d-fold.md`, `PROOF-lvs.md`, `PROOF-381-high-rs-resistor.md`, `PROOF-433-vdd-island-fix.md`) |
| PFD + charge pump (#294 via #299–#303, #385, #386; LVS at #440/#448; folded at #455; glue bus packed at #469, glue inverters interleaved at #473) | `pfd_cp` | 344.98 × 74.30 µm (0.0256 mm²) | clean (default **and** `--offgrid` signoff-grade) | **matched** | `layout/evidence/pfd-cp-layout/` (`PROOF.md`, including the first run's recorded mismatch and its root cause; `PROOF-455-fold.md`, `PROOF-469-glue-bus-packing.md`, `PROOF-473-glue-inverter-interleave.md`) |
| Divider chain (#295 via #306–#310, packed at #341, folded at #344, macro-track-packed at #454, routed over its device rows at #458) | `divider_chain` | 1317.66 × 41.99 µm (0.0553 mm²) | clean (also under `--offgrid`) | **matched** | `layout/evidence/divider-chain-layout/` (`PROOF.md`, `PROOF-fold.md`, `PROOF-macro-track-packing.md`, `PROOF-over-device-rows.md`) |
| Lock detector (#296; DR-014 trim network + LVS at #440/#449) | `lock_detector` | 294.80 × 103.75 µm (0.0306 mm²) | clean | **matched** | `layout/evidence/lock-detector-layout/PROOF.md` (including the first run's recorded mismatch, its DR-014-staleness root cause, and the regrown geometry's clean re-proof) |

Every DRC run above is against the PDK's own foundry signoff decks
(`$PDK_ROOT/libs.tech/klayout/drc/…`), not a curated subset, and every LVS
run is the PDK's own `run_lvs.py` reporting `Congratulations! Netlists
match.` — the recorded deck output is committed next to each GDS. These
counts are re-derived from the evidence tree in CI by
`layout/lib/check-layout-status-claims.sh`, so this section cannot silently
drift from the tree (it did once, for about five weeks: this section denied
the four sub-block layouts that were already committed — and §3 kept denying
them even in the change that corrected this section, which is why that check
now grades every absence-of-layout claim in both documents rather than a
list of three remembered sentences).

The footprint column is the **committed GDS bounding box**, re-derived in CI
by the same check from `layout/evidence/area-audit/area-audit.md` — the
audit `python3 layout/run_pv.py area` regenerates by measuring each
committed GDS — so it is the same measurement §5's Area row sums, not a
separately maintained figure. It was maintained separately once, and drifted
for exactly as long as one would expect. This table carried `vco_block` at
the extent #324's fold produced, two later geometry changes out of date
(#336's 2-D mirror array and #381's re-shaped high-Rs resistor each moved
it), and it carried `pfd_cp` at that block's `footprint` tuple — a union of
recorded sub-block extents — rather than at the drawn-shape bounding box
this column's heading promises. §5 carried the correct figure for both at
the same time, so the document stated two different sizes for the same
block. The numbers are now graded the way the prose already was; the exact
superseded figures are recorded in
`layout/evidence/area-audit/PROOF.md` and `layout/floorplan/PLL-FLOORPLAN.md`
§5.5 rather than restated here, because a check that grades a claim cannot
tell asserting it from quoting it.

**What does not exist, stated as plainly as what does:**

- **There is no assembled `pll_top` GDS.** The four blocks sit side by side
  in `layout/pll_top/` as independent generators, not wired into a top
  level. `layout/floorplan/` (issue #17) holds a block-placement skeleton —
  one `DIEAREA` rectangle per block at each block's real measured extent —
  which is a placement plan, not a routed top level.
- **Therefore no top-level DRC/LVS closure**, and **no post-layout
  extracted-netlist re-verification** (issue #18): there is nothing to
  extract. Every number in §5 is a schematic-level simulation result with
  no layout parasitics, and this proposal makes no post-layout claim.
- **All four blocks are now LVS-matched.** `lock_detector`'s own window-delay
  cell predated DR-014's 4-bit trim network through issue #440's first
  block-level LVS attempt, so it was a smaller circuit than the ratified
  schematic describes and the deck correctly refused to match the two; issue
  #449 drew that trim network and the deck now reports a match, closing the
  last gap of the four.
- **The block footprints exceed the *draft* 0.15 mm² area budget by 1.50×, and
  the spec row has since been amended to ≤ 0.30 mm² on that measurement**
  (§5's Area row, "Known gaps" item 8,
  `layout/floorplan/PLL-FLOORPLAN.md` §5.1–§5.14, and
  `spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md`).
  The draft target is unreachable by measurement, not by projection: even
  assuming every Metal2 track routes at zero area cost, the blocks' own drawn
  device bands plus the loop filter are 1.13× it. The block meets the amended
  row at 0.2254 mm² — 75.1 % of it — with the margin sized to the ×1.25
  top-level overhead factor nothing has yet measured. It was 0.2733 mm² when
  DR-016 was written; three levers have since landed — #469 packed
  `cp_output_stage`'s glue-bus track band (0.2733 → 0.2730 mm², §5.12), #458
  routed the divider chain's Metal2 tracks into the plane over its own device
  rows (0.0926 → 0.0553 mm² for that block, 0.2730 → 0.2264 mm², §5.13) and
  #473 interleaved `cp_output_stage`'s glue inverters with the switches they
  drive (0.0264 → 0.0256 mm² for `pfd_cp`, 0.2264 → 0.2254 mm², §5.14) —
  which is why the number moved *down* under an unchanged row. Reduction work
  stays open: an unnamed `lock_detector` lever (that block's footprint having
  grown ~4.1× for the LVS match above). Reported as a spec amendment on the
  record, not rounded away.

Top-level assembly and formal DRC/LVS reporting are tracked at issues #17
and #149; post-layout re-verification at #18. This proposal claims exactly
the DRC/LVS closure the table above records, and no more.

---

## 7. Open items before this proposal's evidence trail is considered complete

1. **The 5.0 V analog rail is entirely unexplored** (§2.1, §5). This design
   would need explicit design work — most plausibly an on-die 5.0 V→3.3 V
   regulation stage, or a harness accommodation to draw every domain from
   the 3.3 V digital rail — before it meaningfully exercises the Challenge's
   5.0 V rail. Nothing here should be read as implying that work has started.
2. **Closed-loop `period-jitter`'s random/noise-driven component has zero
   records; its deterministic component now covers the full mandated
   45-point PVT matrix** (§5) — the complete 3 × 3 temperature × supply
   plane is measured at all five MOS bundles (`typical`, `ff`, `ss`, `fs`,
   `sf`), and every point of it passes with at least 3.7× margin. But
   **no point of this campaign varies the output band away from band 6 /
   150 MHz** — which matters because 200 MHz, not 150 MHz, is the end of
   the ratified band that binds. Tracked at issue #13; a defect in the
   campaign's own lock gate, which reports FAIL at two demonstrably-locked
   corners, is tracked separately at issue #273 and does not affect any
   jitter number reported here. The output-band axis is a declared
   campaign of its own, `sim/period-jitter-band-top` — the same
   measurement and the same reduction code at 200 MHz, its full 45-point
   grid declared, every point's operating point derived from the committed
   VCO record under
   [`spec/pll.md`'s band-selection rule](../../spec/pll.md#band-selection-rule)
   and re-checkable without a simulator. It carries **no measured record
   yet**; that is stated here rather than left for a reader to infer from
   §5's citations. Deriving it did produce one result that needed no
   simulator and is reported in §5: at 200 MHz the band-selection rule does
   **not** select a single band code across the PVT grid (band 6 at 34 of
   45 points, band 7 at the other 11), where at 150 MHz one code covers all
   45.
3. **Closed-loop `lock-time` and `output-range` full-PVT grids exist but do
   not establish a closed PASS bound** (§5) — `lock-time` reaches a
   sustained PASS on a minority of tested corners within its own window,
   and `output-range` reaches PASS on none, at either drawn-band edge.
   Neither result has yet been root-caused to a specific mechanism the way
   `supply-sensitivity`'s findings have been (routed to #9/#10/#11 by name);
   closing that gap is separate follow-on work, not covered by this
   proposal.
4. **`supply-sensitivity`'s three FAILing criteria are disclosed design
   findings**, not settling-window artifacts (both settling-time escalations
   for the step/ramp criterion ran to full length before FAILing at one
   corner). They are already routed to their owning issues (#9, #10, #11)
   in this repository's own evidence records.
5. **The lock detector's T1′/T2′ window targets are now met, but only on a
   trimmed part, and T4/T5 are still uncharacterized below 25 MHz** (§5).
   This item previously read "does not meet its own T1/T2 targets"; #411
   closed that gap by adding a 4-bit test-set window trim and a normative
   [trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule),
   re-characterized in situ across 205 points. Three residuals a reader
   should weigh: an **untrimmed part is outside this specification** (no
   single fixed code holds the [1, 2] ns band across PVT); the code table is
   schematic-level and mismatch-free, so trim-array DNL is unquantified;
   and the detector has only ever been run at `f_ref` = 25 MHz, so T4
   (deassert latency) and T5 (no chatter) are unverified at the 1 MHz bottom
   of the reference range, where the assert hold-off is of order one
   reference period. `spec/pll.md` keeps this row inside its ratification
   carve-out for those reasons.
6. **The 4-vs-2 bandgap-current-source mismatch (§2.2) has no resolution
   today.** No bias-generator sub-block exists in this repository; every
   closed-loop simulation to date drives the four bias nodes from ideal
   current sources.
7. **No assembled `pll_top` GDS, no top-level DRC/LVS closure, and no
   post-layout re-verification exist** (§6). Block-level layout *does* —
   4 of the 4 PLL sub-blocks are drawn and standalone-DRC-clean, and, as of
   issue #449, 4 of the 4 LVS-matched — but the top level that would be
   extracted has not been assembled, so every §5 number remains
   schematic-level. Tracked at issues #17 (top-level assembly), #149
   (formal DRC/LVS reporting) and #18 (post-layout re-verification).
8. **The drawn blocks are 1.50× over the *draft* 0.15 mm² area target, that
   target is measured to be unreachable, and the spec row has been amended to
   ≤ 0.30 mm² on that measurement — which the block meets at 0.2254 mm²**
   (§5, §6; `spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md`).
   **Read that as a spec change, not as a solved area problem.** The draft
   number was never derived from anything — DR-007's own review raised it as
   Amendment A3, "the one `budget` row in the table with no rationale behind
   the number at all, not even a disposition-only hand calc" — and the 78.6 %
   of it that A3 said had no estimate of any kind is now four committed,
   DRC-clean, LVS-matched block layouts measured off GDS by a reproducible
   command. The answer is that the aspiration was 1.82× off when DR-016 was
   written (1.50× since issues #458 and #473, below), and DR-016
   records that permanently rather than letting it live as an indefinite
   "still over" in a layout file. What makes it unreachable is measured, not
   projected: strike **all** Metal2 routing — every net free, no band anywhere
   — and the blocks' own drawn device bands plus the loop filter still sum to
   0.1702 mm² (**1.13×**), a bound no row fold escapes, because folding halves
   a block's width and doubles its device band. 57.2 % of what the draft row
   allowed is the loop filter (capacitance-set by DR-006; reducing it moves
   [Loop bandwidth](../../spec/pll.md#loop-bandwidth) and
   [Phase margin](../../spec/pll.md#phase-margin), both ratified *and*
   measured) plus `vco_block`'s guard-ring and 15 µm tap-pitch spacing, which
   the foundry deck requires. The amended row's margin — 8.9 % on the sum
   DR-016 was written on, 24.9 % on the sum as drawn today — is sized to one
   thing — the ×1.25 top-level overhead factor, which no assembled `pll_top`
   has ever measured (gap 7 above) — and **not** to block growth; it holds for
   an overhead up to ×1.372 at DR-016's sum and ×1.664 at today's. Reduction
   remains open and a lower row is still the goal: what is left unnamed is a
   lever against `lock_detector`'s 65.5 % whitespace, each material landing
   being grounds for a successor record amending the row back down on the same
   standard — measured, from committed geometry, DRC/LVS-clean. **Three such
   landings have already happened and the row has not yet followed any of
   them.** #469, the first, is spent at 259 µm² (0.1 % of the sum) and does not
   clear that bar on its own (0.2733 → 0.2730 mm², PLL-FLOORPLAN.md §5.12);
   #473, the third, is the *placement* half of that same band — the glue
   inverters interleaved with the switch groups they drive, 13 → 10 tracks,
   776 µm² (0.4 %, 0.2264 → 0.2254 mm², PLL-FLOORPLAN.md §5.14) — and does not
   clear it either. #458, the second, does move the total
   materially: it made both of `divider_chain`'s Metal2 track assignments
   obstacle-aware, so its tracks sit in the plane over its own device rows
   rather than in a band above them — 0.0926 → **0.0553 mm²** for that block,
   74.4 % of its own sized ceiling, DRC-clean on both decks and still
   LVS-matched
   (`layout/evidence/divider-chain-layout/PROOF-over-device-rows.md`,
   PLL-FLOORPLAN.md §5.13). The figures, and the sequence of passes that
   produced them: **0.1803 mm² summed, 0.2254 mm²** with the floorplan's ×1.25
   top-level overhead, before any top-level routing is counted (0.2186 /
   0.2733 mm² when DR-016 was written, the difference being those three
   levers).
   The divider-chain packing lever is already
   spent: issue #454 packed the `div23_cell` macro's own Metal2 track band
   (31 nets onto 11 tracks, the provable minimum), taking that block
   0.1321 → 0.0926 mm² and the total 2.03× → 1.70× on its own, DRC- and
   LVS-clean at the new geometry
   (`layout/evidence/divider-chain-layout/PROOF-macro-track-packing.md`).
   `lock_detector` then grew ~4.1× (0.0075 → 0.0306 mm²) for its own first
   LVS match (issue #449), moving the total on to 1.89× — the first growth
   this record has stated since it began tracking a shrinking overrun at
   #341/#344/#454, and not a placement regression: it is 72 devices the
   block's own ratified schematic always specified, finally drawn. Shared-
   diffusion device stacking — which this proposal previously named as the
   cause — remains worth only **0.10 %** of the (now larger) gap, falsified
   rather than deferred, because the divider chain's drawn diffusion is
   ~1 % of its own bounding box. The `pfd_cp` fold (#455) is now spent too:
   `pfd` moved inside `cp`'s own 99.0 %-empty band above `cp_dumpbuf` and the
   Metal2 trunk band above both was re-pitched and re-based, taking that block
   0.0353 → 0.0265 mm² (−24.4 %), DRC-clean on both decks and still
   LVS-matched
   (`layout/evidence/pfd-cp-layout/PROOF-455-fold.md`). That outcome is
   **42 % of the 0.0149 mm² ceiling §5.5 sized it at**, and the shortfall is
   in the ceiling rather than the execution: the ceiling's 57-track census is
   flat over five levels of composition, of which only 4 tracks belong to
   `pfd_cp` itself, and the fold raises the block's own device-band floor
   above the packed-track floor it was measured against. That block's own
   residual routing lever (#469) is spent too, and reports the same shape of
   finding a third time: packing `cp_output_stage`'s glue bus took it to its
   interval graph's clique number — provably minimal — and that number is 13,
   not the 9 a census of the buses alone gives, because the level above
   extends six of the fourteen nets across the block's whole width. 0.0265 →
   **0.0262 mm²**, 20 % of what the lever was sized at
   (`layout/evidence/pfd-cp-layout/PROOF-469-glue-bus-packing.md`). That band
   had a second, *placement* half, and it is spent too: #473 interleaved the
   four glue inverters with the switch groups whose gates they drive, taking
   the same band 13 → 10 tracks and the block 0.0264 → **0.0256 mm²**. A
   clique number is a floor for an assignment, not for a placed-and-routed layout — where the
   intervals end is a placement decision, and 25,920 candidate row orders were
   costed against `pack_tracks()` before anything moved
   (`layout/evidence/pfd-cp-layout/PROOF-473-glue-inverter-interleave.md`).
   There is now no unexecuted routing-track *or* placement lever left in
   `pfd_cp`. A fourth lever,
   sized against `lock_detector`'s own 65.5 % whitespace, is still not
   named. (Earlier revisions of this item projected a post-lever floor of
   1.64×, then 1.54×; both carried `divider_chain`'s pre-#454 ceiling, and
   re-derived from the current audit the figure is **1.20×** — better than the
   record had been carrying, and still over. PLL-FLOORPLAN.md §5.11. #458 has
   since taken that block to 0.0553 mm², 74.4 % of the way from as-drawn to
   its own ceiling, and §5.13 records that the `max(packed-track floor, device
   band)` rule that ceiling uses no longer bounds a block which routes over
   its own device rows — for `divider_chain` the honest floor is now its
   device band alone, 0.0347 mm².)
   The decision record this history was waiting on is DR-016, written on the
   measured post-lever total once both sized levers (#454, #455) had landed
   DRC/LVS-clean — not on the bound.
9. **`spec/pll.md` is ratified with amendments, but two rows remain
   carved out and unratified** — [Lock time](../../spec/pll.md#lock-time)
   (row 9) and [Lock detector](../../spec/pll.md#lock-detector) (row 16),
   per DR-007 Amendment A1. Verdicts on those two rows in §5 are stated
   against the draft targets and say so; every other row's verdict is
   against a ratified target.

None of the above items block *submitting* this proposal — consistent with
this program's stated goal for Chipalooza proposals, the aim is to state the
design honestly at its current maturity with every claim traceable to a
dated `sim/` record, not to have already closed every open item by the
submission date.

---

## 8. Licensing and EDA flow

- **License**: this entire repository — spec, decision records, schematics,
  testbenches, and every evidence record cited above — is licensed
  [Apache-2.0](../../LICENSE), satisfying the Challenge's requirement for a
  standard open license with all modifiable sources public.
- **Flow**: fully open-source. Schematic capture and netlisting via
  [xschem](https://xschem.sourceforge.io/); simulation via
  [ngspice](https://ngspice.sourceforge.io/); layout, DRC, and LVS (once
  drawn) via [KLayout](https://www.klayout.de/) driven by
  [klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`), proven
  on the inverter test cell referenced in §6; the gf180mcu PDK (`gf180mcuD`
  variant) resolved via the standard `PDK_ROOT`/`PDK` environment convention
  this repository uses throughout. Every cited `sim/` record's own
  Environment-provenance field states the exact pinned toolchain versions
  that produced it, so any reviewer can re-run the cited evidence from a
  clean checkout (`sim/run_corners.py`, documented in `sim/README.md`).
