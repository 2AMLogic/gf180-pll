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
This repository is, at the time of writing, **schematic-level and
pre-layout** (`README.md`'s own "Status" section). This proposal documents
the block honestly at that maturity: §5's target-specification table reports
what the schematic-level `sim/` evidence shows, marks every row met or unmet
against the draft (`spec/pll.md`, itself **proposed and not yet ratified** —
see §5.0), and does not assume or forward-cite work that has not happened.
Layout, DRC/LVS closure, and post-layout re-verification are open items
(§7), each tracked by its own issue in this repository, not silently implied
by this document's existence.

---

## 1. Type of IP block

An integer-N, ring-oscillator, Type-II charge-pump phase-locked loop:
current-starved 5-stage ring VCO (8 overlapping geometric bands), a
phase-frequency detector and charge pump, a fixed passive R–C loop filter
with a 2-bit charge-pump current trim, a cascaded ÷2/3 feedback divider
(integer N = 4–64), and a digital phase-window lock detector. Architecture is
captured in
[`spec/decision-records/DR-001-pll-architecture.md`](../../spec/decision-records/DR-001-pll-architecture.md)
(status: **proposed**, like every decision record and `spec/pll.md` itself,
pending engineering ratification through issue #1 — see §5.0).

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
(`design/netlist/pll_top.spice`, `.subckt pll_top REF B0 B1 B2 CPB0 CPB1 P0
P1 P2 P3 P4 P5 SEL0 SEL1 SEL2 SEL3 SEL4 SEL5 IBN ICN IBP ICP CLK DIVOUT FB
LOCK VCTRL + VDD VDD_VCO GND_VCO VDD_DIV VSS`) is the port list this table
maps, unedited, onto the Challenge #5 budget (per Epic #542: one
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
| `P0`…`P5`, `SEL0`…`SEL5` | in | digital control input | 12 of 24 | Feedback-divider configuration: `P5..P0` is each ÷2/3 cell's per-cycle mode; `SEL5..SEL0` is a one-hot chain-length code. Together they set `N = 2^k + Σ P_j·2^j (j<k)` for one-hot `SEL_(k-1)=1`, covering the ratified N = 4–64 range. Static configuration; the loop re-locks after any change (no glitch-free on-the-fly modulus switching, DR-001 Decision 3) |
| `IBN`, `ICN`, `IBP`, `ICP` | in | **does not fit the ≤ 2 bandgap-referenced current-source budget — open item, see §7** | 4 requested vs. 2 offered | Charge-pump / bias-mirror reference currents. **Every closed-loop `sim/` record in this repository drives these from ideal current sources at 4× the unit-leg current** — the bias generator that would derive them from a single bandgap-referenced current is "a separate, unbuilt block" (every closed-loop evidence record's own Limitations field says so verbatim). This is not a Challenge-specific gap invented for this proposal; it is a standing, disclosed limitation of the design today |
| `VCTRL` | analog, iopin | shared analog line (budget ≤ 4) | 1 of 4 | Loop-filter control voltage — a slow-moving DC/low-frequency analog test point, well suited to a multiplexed line. Usable window 0.9–2.7 V (DR-003 Decision 5) |
| `CLK` | out, dedicated | dedicated pad (budget ≤ 4) | 1 of 4 | PLL output clock, 10–200 MHz continuous across the 8 bands. **Needs a low-resistance, dedicated path** — a shared-mux line's added series resistance and capacitance would degrade the measured edge rates and duty cycle (`spec/pll.md#output-duty-cycle`, `#output-levels-and-drive`) directly |
| `LOCK` | out | digital test output (budget ≤ 12) | 1 of 12 | Digital lock-status flag from the phase-window comparator (DR-002 Decision 4). See §5's Lock detector row for the two disclosed gaps in this signal's own assert/deassert behavior — it is a real, measured signal, not an idealized one |
| `DIVOUT`, `FB` | out | digital test output (budget ≤ 12) | 2 of 12 (proposed) | Divider-chain diagnostic taps: `DIVOUT` is the one-hot-muxed chain output before retiming, `FB` is the retimed signal actually fed back to the PFD. Exposing both as test outputs (rather than only `FB`) lets a bench test independently check the divider's raw ratio against the retiming flop's contribution — proposed, not load-bearing; a minimal test plan could omit `DIVOUT` |

**Totals against the Challenge #5 budget**: 0 of 1 bandgap-referenced bias
voltage (this block draws no bandgap reference of its own — see the `IBN`/
`ICN`/`IBP`/`ICP` row), **4 requested vs. 2 offered** bandgap-referenced
current sources (open item, §7), 18 of ≤ 24 digital control inputs, 1–3 of
≤ 12 digital test outputs (`LOCK` alone, or `LOCK`+`DIVOUT`+`FB`), 1 of ≤ 4
dedicated pads, 1 of ≤ 4 shared analog lines. Every category **except the
current-source count** fits inside budget with real headroom; the
current-source mismatch is the one place this design does not fit the
harness as specified, and it is stated as such rather than glossed over.

### 2.3 What's dropped, multiplexed, substituted, or new relative to this repo's own port list

- **Nothing in `design/pll_top.sch`'s port list is dropped.** Every pin the
  schematic exposes is mapped to a slot above.
- **No pin is proposed as new** relative to the schematic — `DIVOUT` and `FB`
  are both already top-level pins of the committed design, simply optional
  as *test* outputs versus load-bearing feedback.
- **`SPI control` does not apply.** This block has no addressable
  configuration register — its 18 configuration bits (`B0..B2`, `CPB0..1`,
  `P0..5`, `SEL0..5`) are static levels, not an SPI-programmed state, and
  nothing in `design/` implies an SPI interface. A harness wrapper that
  drives these 18 lines from its own SPI-to-parallel shift register (rather
  than 18 dedicated harness pins) is a harness-side integration detail, not
  a change to this proposal's I/O list.
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
**No layout exists for this block** — `layout/` currently contains only the
DRC/LVS flow's proof-of-flow test cell (a standard-cell inverter,
`layout/evidence/inv-tb-proof/PROOF.md`), proven clean on that trivial
circuit but never yet run against any PLL sub-block or the top level.

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
   (`spec/pll.md#period-jitter`) — this is the first *closed-loop* period-
   jitter measurement this design would have, since no closed-loop
   `sim/period-jitter` evidence exists yet (§5, §7).
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
**`spec/pll.md` itself is status "proposed" — pending engineering
ratification through issue #1 — not yet a ratified spec.** This table
re-derives min/typ/max directly from the underlying `sim/` evidence rather
than treating `spec/pll.md`'s own summary table as settled, and flags, row by
row, where newer full-PVT-grid closed-loop evidence postdates and updates
what `spec/pll.md`'s own table currently cites (`spec/pll.md`'s summary table
was last written 2026-07-31; the closed-loop `lock-time`, `output-range`, and
`supply-sensitivity` full-grid records below are dated 2026-08-19 through
2026-09-01 and are not yet reflected there). All evidence is
**schematic-level — no layout parasitics exist yet** (§7); everything is at
the 3.3 V digital rail only, since no 5.0 V device exists in this design
(§2.1).

| Parameter | v1 draft target | Measured / derived (3.3 V) | Verdict | Source (dated) |
|---|---|---|---|---|
| Output band | 10–200 MHz continuous | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V); ceiling 247.8 MHz (`all-slow`/−40 °C/3.63 V); 0 non-monotonic curves of 504; worst adjacent-band overlap 27 % | **MET** (open-loop characterization) | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Output band, **closed-loop** | Same, at any legal (N, band, `f_ref`) | Full 45-point PVT grid at both drawn-band edges (90 runs, `pll_top` DUT): **0 of 45 corners reach a sustained in-window PASS at either edge** | **UNMET / open finding** — closed-loop band-edge settling has not yet been demonstrated within the campaign's own measurement window at any corner | `sim/output-range/records/20260819-160843-4e32f91.md` (full grid); `sim/output-range/records/20260819-190341-70a4128.md` (supersedes that record's single `ff`/27 °C/3.30 V `hi` row only, replacing a hand-killed ERROR with a reproducible CAPPED/stall characterization — still not a PASS) |
| Multiplication ratio | N = 4–64, every integer | 61 distinct N exercised at 200 MHz, 0 ratio errors of 235 chain points; worst retiming setup margin 6.1 % of a VCO period (`ss`/125 °C/2.97 V) | **MET** | `sim/divider-ratio/records/20260731-171817-0a12e6c.md` (chain), sibling flop/cell records same date |
| Integrated RMS jitter | not spec'd (DR-002 Decision 5) | n/a by design — never presented as a spec'd figure | **N/A, by design** | `spec/pll.md#integrated-rms-jitter` |
| Period jitter (open-loop sensitivity) | ≤ 1.0 % RMS, conditional on ≤ 20 mV pp `vdd_vco` ripple | Worst 2.51 % RMS at 100 mV pp ripple (`all-slow`/−40 °C/2.97 V, band 5); implies 0.50 % RMS at the 20 mV pp budget, leaving headroom for an unmeasured random component | **derived, conditional PASS** at the stated ripple budget | `sim/vco-tuning-range/records/20260731-184845-0a12e6c.md` |
| Period jitter, **closed-loop, random/noise-driven** | Same 1.0 % RMS line | **Zero records.** `sim/period-jitter/` does not exist. Tracked at issue #13, which is itself **blocked on issue #1** (spec ratification) per #13's own tracked Dependencies | **UNMET — explicitly, not omitted.** This is the one row this proposal cannot report a number for at any maturity | issue #13 (open, `loom:blocked`) |
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
| Area | ≤ 0.15 mm² total (budget — no layout exists) | Loop filter alone: 0.0321 mm² (21.4 % of budget), measured from real device data; remaining 78.6 % (VCO, PFD/CP, divider, lock detector, routing, decap) **not estimated** | **Not evaluable — no layout drawn** (§7) | `spec/pll.md#area`, underlying `sim/loop-dynamics` and `sim/devchar-passives` |
| Lock detector | assert window ≥ 2.5 ns (T1); ≥ 2× worst static phase offset (T2); hysteresis ≥ 25 % of window (T3); deassert ≤ 1 `f_ref` period (T4); no chatter 1–25 MHz (T5) | Window measured 0.877–1.702 ns; worst deassert latency 5.45 ns; characterized at `f_ref` = 25 MHz only | **T1/T2 UNMET** (summed static phase offset up to ≈1.49 ns is comparable to the window); **T3 not separately reported**; **T4/T5 unverified below 25 MHz** — genuine, disclosed design gaps, not oversights | `sim/lock-detector/records/20260731-162119-0a12e6c.md` |
| Kvco | ≤ 150 MHz/V under the band-selection rule | Worst 115.8 MHz/V (`all-fast`/27 °C/2.97 V, B6); an adversarial band choice reaches 154.3 MHz/V, over the line, which is why the rule is normative | **MET**, conditional on the band-selection rule being followed | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Supply range | 3.3 V ± 10 %, 3.3 V devices exclusively | Every campaign above sweeps 2.97/3.30/3.63 V | **MET, as the swept independent axis of every other row** | `spec/pll.md#supply-range` |
| Supply range, **5.0 V analog rail** | Challenge #5 asks analog blocks to operate across 3.3–5.0 V | **No 5.0 V-class device exists in this design; never simulated above 3.63 V** | **UNMET / not attempted** — the single most load-bearing gap in this proposal, stated plainly per §2.1 | This proposal, §2.1 |

No row above is relaxed, narrowed, or omitted to make it pass — the `period-
jitter` closed-loop row, the `output-range` closed-loop row, three of four
`supply-sensitivity` criteria, the lock-detector T1/T2/T4/T5 gaps, and the
5.0 V-rail row are all reported UNMET, exactly as the underlying evidence
states, per `CLAUDE.md`'s "agents do not relax the ratified spec to make
results pass."

---

## 6. Layout, DRC/LVS, and post-layout status

**No PLL-block layout exists.** `layout/` holds a proven, `klt`-aware
DRC/LVS flow (issue #16, `layout/evidence/inv-tb-proof/PROOF.md`) validated
on a trivial standard-cell inverter test cell — including a demonstrated
catch of a deliberately injected DRC violation and LVS mismatch — but that
flow has never been run against any of this design's own sub-blocks (VCO,
PFD/charge pump, loop filter, feedback divider, lock detector) or the
assembled top level. Drawing that layout is tracked at issue #17 (floorplan:
VCO isolation, supply routing, loop-filter capacitor, guard rings), and
post-layout extracted-netlist re-verification is tracked at issue #18. Both
are, at the time of writing, **blocked on issue #1** (this repository's own
spec-ratification gate) — per #17's own tracked Dependencies, "layout-locking
work (#16, #17, #18) needs to wait on the formal ratification itself," a
constraint recorded independently of, and in addition to, #16's own
now-satisfied tooling prerequisite. This proposal does not draw layout or
claim DRC/LVS closure that has not happened.

---

## 7. Open items before this proposal's evidence trail is considered complete

1. **The 5.0 V analog rail is entirely unexplored** (§2.1, §5). This design
   would need explicit design work — most plausibly an on-die 5.0 V→3.3 V
   regulation stage, or a harness accommodation to draw every domain from
   the 3.3 V digital rail — before it meaningfully exercises the Challenge's
   5.0 V rail. Nothing here should be read as implying that work has started.
2. **Closed-loop `period-jitter` has zero records** (§5). Tracked at issue
   #13, itself blocked on issue #1 (spec ratification) per #13's own
   Dependencies section — not something this proposal, or the issue that
   produced it, can resolve directly.
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
5. **The lock detector does not meet its own T1/T2 targets** at several
   corners (§5) — a correctly locked part may fail to assert `LOCK` at the
   top of the reference range, where the required charge-pump trim code is
   smallest. The fix identified in `spec/pll.md#lock-detector` is geometric
   (widen the delay window or scale the integrating capacitor), not
   architectural, but has not been implemented.
6. **The 4-vs-2 bandgap-current-source mismatch (§2.2) has no resolution
   today.** No bias-generator sub-block exists in this repository; every
   closed-loop simulation to date drives the four bias nodes from ideal
   current sources.
7. **No layout, DRC/LVS closure, or post-layout re-verification exists**
   (§6), tracked at issues #17 and #18, both currently blocked on issue #1.
8. **This repository's own target specification (`spec/pll.md`) is not yet
   ratified** — issue #1 is open. Every "MET"/"UNMET" verdict in §5 is
   stated against the *draft* v1 targets, which remain subject to change
   through #1's ratification process.

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
