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
list this table maps, unedited, onto the Challenge #5 budget as this
repository understands it: one bandgap-referenced bias voltage, up to 2
bandgap-referenced current sources, up to 24 digital control inputs, up to 12
digital test outputs, up to 4 shared analog lines, up to 4 dedicated pads, SPI
control documented in the harness, and no transcribed line at all for
supply/ground pads. **That budget is transcribed here, not authored here** —
the challenge's own rules page is the authority, and the submitting operator
should confirm these slot counts against it in the same pass that confirms the
deadline (see this document's opening note). The rail line is written as an
*absence* rather than left out, because it is load-bearing: this block asks for
**five** supply/ground pads, and the table's own rail rows are what forbid
sharing them down — `VDD_VCO`/`GND_VCO` "must not be tied to the same physical
rail node as `VDD`", and `VDD_DIV` is "kept separate from the other two for the
same reason". A harness that budgets rails per block therefore has to be told
that number, and until this revision the totals paragraph below did not state
it at all.

| Signal(s) | Dir | Challenge slot | Count used | Notes |
|---|---|---|---|---|
| `VDD`, `VSS` | supply | supply/ground pad — 3.3 V digital rail | — (rail) | PFD, charge pump, `cp_dumpbuf`, lock detector domain (`vdd_ref` in `spec/pll.md`'s naming) |
| `VDD_VCO`, `GND_VCO` | supply | supply/ground pad — 3.3 V digital rail (proposed, see §2.1) | — (rail) | VCO bias/ring/output-buffer domain, kept electrically separate from `VDD`/`VSS` by design (DR-001 Decisions 2–3) specifically so ring switching noise does not couple into the reference domain; **must not be tied to the same physical rail node as `VDD` on the harness board**, even though both are proposed at 3.3 V |
| `VDD_DIV` | supply | supply/ground pad — 3.3 V digital rail (proposed, see §2.1) | — (rail) | ÷2/3 chain, output mux, retiming flop domain — kept separate from the other two for the same reason |
| `REF` | in | digital control input (budget ≤ 24) | 1 of 24 | Reference clock, CMOS square wave, rising-edge triggered, 1–25 MHz (`spec/pll.md#reference-input`); duty cycle 30–70 % (only pulse-width margin, not sampled phase, is duty-sensitive — the PFD's edge detectors fire on the rising edge only) |
| `B0`, `B1`, `B2` | in | digital control input | 3 of 24 | VCO band select (3-bit, 8 bands). **Static configuration only** — no on-chip auto-calibration FSM exists (DR-001 Decision 2); a system must apply the [band-selection rule](../../spec/pll.md#band-selection-rule) itself |
| `CPB0`, `CPB1` | in | digital control input | 2 of 24 | Charge-pump current trim (2-bit, 4 codes). **Not discretionary** — required to be set from `f_ref` per the [Icp trim-code rule](../../spec/pll.md#icp-trim-code-rule) |
| `LDT0`…`LDT3` | in | digital control input | 4 of 24 | Lock-detector window trim (4-bit, 16 codes). **Not discretionary** — required to be set once per part at test, from that part's own measured comparator-window delay, per the normative [Lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule) (DR-014, DR-015). Same static-configuration idiom as `CPB0`/`CPB1`; nominal/unprogrammed code is 1000 (8) |
| `P0`…`P5`, `SEL0`…`SEL5` | in | digital control input | 12 of 24 | Feedback-divider configuration: `P5..P0` is each ÷2/3 cell's per-cycle mode; `SEL5..SEL0` is a one-hot chain-length code. Together they set `N = 2^k + Σ P_j·2^j (j<k)` for one-hot `SEL_(k-1)=1`, covering the ratified N = 4–64 range. Static configuration; the loop re-locks after any change (no glitch-free on-the-fly modulus switching, DR-001 Decision 3) |
| `IBN`, `ICN`, `IBP`, `ICP` | in | **does not fit the ≤ 2 bandgap-referenced current-source budget — open item, see §7** | 4 requested vs. 2 offered | Charge-pump / bias-mirror reference currents. **Every closed-loop `sim/` record in this repository drives these from ideal current sources at 4× the unit-leg current** — the bias generator that would derive them from a single bandgap-referenced current is "a separate, unbuilt block" (quoted verbatim from the Limitations field of `sim/pll-top-smoke/records/20260802-160926-8456ff3.md` and of `sim/supply-sensitivity/records/20260901-155456-46b92f8.md`; the lock-time, output-range, period-jitter and reference-spur records drive the same ideal sources without restating why — an earlier revision attributed the phrase to all of them, which `sim/lib/check-bias-drive-claims.sh` now fails). This is not a Challenge-specific gap invented for this proposal; it is a standing, disclosed limitation of the design today |
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
1 of ≤ 4 dedicated pads, 1 of ≤ 4 shared analog lines, 5 supply/ground pads
(`VDD`, `VDD_VCO`, `VDD_DIV`, `VSS`, `GND_VCO` — three supplies the rail rows
above require be *distinct nodes* rather than one rail fanned out on the board,
plus two grounds, which §4's step 1 ties at a single low-impedance reference
off-die). Every *budgeted* category **except the
current-source count** fits inside budget with real headroom; the
current-source mismatch is the one place this design does not fit the
harness as specified, and it is stated as such rather than glossed over.

**The rails are the one line with no budget to fit inside**: the transcribed
budget above has no slot count for them, so five is a *request* — and until
this revision it was not even that, because the totals paragraph claimed to
cover every category while silently omitting the five pads without which
nothing on this die powers up. The submitting operator should confirm what the
harness offers for rails in the same pass that confirms the slot counts and the
deadline.

**Every number in that paragraph is the sum of the rows above it**,
machine-checked rather than maintained by hand:
`design/lib/check-io-list-coverage.sh` fails this repository's CI if a
category's total stops matching the pad rows carrying that slot, if a pad row's
slot is one the transcribed budget does not name, if a category the budget
names has no total, or if a "K of M" count quotes a budget M the transcription
does not have. That last class of drift is not hypothetical — this paragraph
read 18 of 24 digital control inputs against a real 22 for three days (issue
#441, DR-015), because a total is the cheapest thing in a document to leave
behind when the rows above it change.

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
  `LDT0`–`LDT3` addition.) That arithmetic is now machine-checked too:
  `design/lib/check-io-list-coverage.sh` expands the bus list in this
  sentence and fails if the stated count disagrees with what it expands to, if
  a bit named here has no pad row in §2.2, if those rows span more than one
  Challenge slot, or if a pin sharing their slot is dropped from this count
  without being named in this bullet as excluded — which is the only reason
  `REF` may be missing from it.
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
`CPB0..1`, `LDT0..3`, `P0..5`/`SEL0..5`, the four bias-reference currents
`IBN`/`ICN`/`IBP`/`ICP`, `CLK`, `LOCK`, and (optionally) `DIVOUT`/`FB`; none
require the Challenge's shared analog mux beyond `VCTRL`. **Every pin §2.2
maps is named by some step below**, which is a CI-enforced property of this
document rather than a claim (`design/lib/check-io-list-coverage.sh`) — an
earlier revision of this plan silently omitted both the bias references and
the lock-detector trim, and neither omission is one a bench operator could
work around from the rest of the text.

1. **Bring-up / DC sanity.** Power `VDD`, `VDD_VCO`, `VDD_DIV` (all proposed
   at the Challenge's 3.3 V digital rail, §2.1) with `VSS`/`GND_VCO` tied at
   a single low-impedance ground reference. **Supply the four charge-pump /
   bias-mirror reference currents from external sources before anything else
   is expected to work**: `IBN` and `ICN` are sourced *into* the die from the
   supply side, `IBP` and `ICP` are sunk *out of* the die to `VSS`, each at
   the 8 µA every closed-loop record in this repository drives them with
   (`.param iunit=8u` in the decks of `sim/period-jitter`,
   `sim/reference-spur`, `sim/supply-sensitivity` and `sim/pll-top-smoke`;
   `IUNIT=8u` in `sim/lock-time/testbench/run.sh` and
   `sim/output-range/testbench/run.sh`, which pass it to decks that set no
   value of their own; the polarity is those decks' own `iibn vdd ibn` /
   `iibp ibp 0`). Current, setting sites and polarity are all
   machine-checked against the committed decks
   (`sim/lib/check-bias-drive-claims.sh`) — an earlier revision of this step
   sent the reader to a `.param` line `tb_lock_time.sp` does not contain.
   There is no bias generator on
   this die — §2.2's 4-requested-vs-2-offered row and §7 item 6 are that
   same fact stated against the Challenge's budget — so with these four pins
   unconnected the charge pump passes no current and **no step below
   functions at all**. Confirm `VCTRL` sits inside its 0.9–2.7 V usable
   window at a chosen static `B0..B2` code with no `REF` applied.
2. **Open-loop VCO characterization.** With the loop broken (or `REF` held
   static so the PFD does not drive the charge pump), sweep `VCTRL` from an
   external source across each of the 8 band codes and measure `CLK`'s
   frequency, confirming each band's range and Kvco against
   `spec/pll.md#kvco`'s per-band table.
3. **Divider ratio check.** Drive `FB`/`DIVOUT` from a known `CLK`-rate input
   (or observe them directly with the loop closed) and confirm the measured
   ratio matches the programmed `P0..5`/`SEL0..5` code, across the N = 4–64
   range.
4. **Program the lock-detector window trim — before any step that reads
   `LOCK`.** `LDT3:LDT0` is not a margin knob: `spec/pll.md`'s normative
   [Lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule)
   (DR-014, sized by #411) requires the 4-bit code to be set **once per part
   at test** from that part's own measured comparator-window delay, and
   states in terms that **a part left untrimmed is outside this
   specification** — measured over all sixteen codes, the window's PVT spread
   at any one fixed code is 1.977…1.988× against a band only 2× wide, and
   neither of the two codes that come closest holds it (code 6 falls to
   0.9746 ns, code 7 reaches 2.0029 ns). A part powered up at the
   unprogrammed nominal code 1000 (8) and measured against §5's Lock detector
   row would therefore read as a failure it is not.

   The rule's own measurand is `t_win`, the `ERR → ERRD` propagation delay of
   the `delaywin_3v3` cell at 27 °C and 3.30 V, programmed to the code whose
   `t_win` is nearest 1.343 ns in the logarithmic sense. **`ERR` and `ERRD`
   are internal nodes with no pad in §2.2's list, and this proposal states no
   pad-referred procedure for selecting the code because there is not one** —
   which is now a measured finding rather than an unexamined gap. **DR-022**
   (#501) derives how accurate a substitute would have to be and then measures
   every candidate the pad list offers against the cell's own sixteen-code
   window map over the full 13-bundle, 117-point PVT grid
   (`sim/lock-window-proxy/records/20260925-050022-6d57802.md`):

   - **Reading `CLK`'s free-running frequency is worse than not trimming at
     all** — 2.434× window spread against 1.984× for an untrimmed part, out of
     the ratified band at both edges. The starved ring is biased through poly
     resistors, so a resistor-only process skew moves its period ∓27 % while
     the all-MOS delay chain does not move at all; and across the MOS axis the
     ring's sign is inverted, running *faster* at the corner where the window
     is *slower*.
   - **The best candidate is the `CLK`→`DIVOUT` pad-to-pad skew**, and it is
     still not sufficient: it holds the ratified [1, 2] ns band at all 117
     points, but at a 1.697× spread against DR-013 Decision 4's ≤ 1.65 ×, with
     a worst code error of +4 — so its band-holding is a property of which
     thirteen bundles the grid contains, not a bound. It is recorded as a
     **characterization aid, not a trim procedure**.

   **What a bench operator should therefore do**, stated as the posture rather
   than as a procedure this proposal cannot substantiate: set `LDT3:LDT0` to a
   deliberate, recorded value; treat that code as a property of every `LOCK`
   measurement taken from the part and report it alongside the result; and do
   not read §5's Lock detector row as met by a part whose code was chosen by
   any means other than the ratified rule. **Two things a reader must not
   miss.** The code space is complete but the *selection* is not: `pll_top`
   used to leave `LDT3` unconnected (**#515**), so only 8 of the 16 codes
   were reachable on the assembled part and the rule's own code 11 was not
   among them — **DR-026** has since connected it, and all 16 codes are
   reachable. And the one route that could have closed the selection gap
   without a design change — a symmetric `REF` phase-step bisection read at
   `LOCK` — has now been measured and **does not work**: **DR-029** (#527,
   closed) finds that the threshold in Δ is not the flag window but the
   window plus an additive time set by the detector's integrator and the
   loop's own bandwidth, **+55.5 %** at the rule's own reference condition,
   worth **−12.6 codes** of selection error on a 16-code trim. **Steps 5 and
   8 below are not valid on an untrimmed part, and no step below discharges
   the trim rule.**
5. **Closed-loop lock acquisition and lock time.** Apply `REF` at a chosen
   frequency with the matching `B0..B2` (band-selection rule) and `CPB0..1`
   (Icp trim-code rule) codes, release the loop from a cold start, and
   measure the time to `LOCK` assertion and to the output frequency settling
   to within the target tolerance. Compare against
   `spec/pll.md#lock-time`'s small-signal 71 µs / 43 µs-floor figures and
   against this proposal's own §5 disclosure that the closed-loop cold-start
   PVT grid has not yet demonstrated a sustained in-window PASS at most
   simulated corners.
6. **Output band, duty cycle, and levels.** Sweep every band code across the
   available supply/temperature range on the daughterboard (environmental
   chamber or temperature-controlled socket) and compare `CLK`'s frequency
   range, duty cycle, and levels against `spec/pll.md`'s Output band,
   Output duty cycle, and Output levels and drive rows.
7. **Reference spur and jitter.** With the loop locked, capture `CLK`'s
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
8. **Lock detector window and chatter — at a recorded trim code, which is not
   the same as a trimmed part.** With `LDT3:LDT0` set to the deliberate value
   step 4 requires, perturb the loop (a small `REF` frequency step) and
   observe `LOCK`'s deassert/reassert behavior against
   `spec/pll.md#lock-detector`'s targets, particularly near the bottom of
   the 1–25 MHz reference range where the design's own evidence flags T4/T5
   as unverified. Record the part's trim code with the result: §5's T1′/T2′
   verdict is conditional on the trim rule, so a window measured at some
   other code is not a measurement against that row — and per DR-022 no
   procedure available at these pads selects the rule's code, so **this step
   produces a characterization of the part at a known code, not a T1′/T2′
   verdict.** A related observation is worth taking while the board is set
   up, provided it is read for what it is: step `REF`'s phase by a known ±Δ
   and bisect the Δ at which `LOCK` drops, in both directions. **That
   bisection does not measure the window.** DR-029 (#527, closed)
   characterized exactly this procedure in simulation and returned a negative
   result: the threshold in Δ is the window plus an additive time set by the
   detector's integrator, its trigger threshold, the discharge device and the
   loop's bandwidth — none of them the delay chain the trim moves — so no
   fixed factor removes it. What the bench can usefully confirm is the half
   that came back clean: the deassert is observable at the `LOCK` pad
   promptly and unambiguously, one to two reference periods after the step
   rather than at the nanosecond scale `spec/pll.md`'s large-signal 5.63 ns
   figure would suggest.
9. **Repeat across the daughterboard's available supply/temperature range**
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

**This table is complete against `spec/pll.md`, and that completeness is
machine-checked rather than asserted.** Every row of that specification's
summary table appears below with an explicit verdict —
`spec/lib/check-spec-row-coverage.sh` fails this repository's CI if one does
not, and if a row is reported here under a parameter name the specification
does not have. The check was written because one row was missing: **Reference
input** had no row here at all until 2026-09-24, so its unmeasured `budget`
limits and the ideal-reference exclusion every jitter and spur number below
rests on reached no reader of this document. A row this table cannot
substantiate is reported UNMET; it is not left out.

The same check also requires that **every decision record a specification row
rests on is named by the row reporting it here**, because a row can be
present and still report a reading the specification has moved past. Three
were: until 2026-09-25 the Lock time row read a bare MET without DR-012 (the
Lock criterion it is timed to is not reached at 1 of the 45 mandated corners
at a rule-compliant configuration, with a second owed — DR-012 as since
narrowed by DR-025), the Area
row still described the re-amendment trigger DR-017 replaced, and the
Reference spur row carried neither DR-018's re-priced margin nor any owner
for its unmeasured points.

**Which PVT grid a row was measured on is stated, not assumed.** Most rows
below are stated against this repository's **45-point mandated grid** — the
five MOS bundles (`typical`/`ff`/`ss`/`fs`/`sf`) × three temperatures
(−40/27/125 °C) × three supplies (2.97/3.30/3.63 V), as
`sim/harness/corners.py` defines it. **Eleven rows are not**, and each of them
now says so in its own cell. Nine are measured on a different corner universe:

- **Output band**, **Period jitter (open-loop sensitivity)**, **Power**,
  **Kvco**, and the **Supply sensitivity — AC (ripple) budget** row derived
  from the second of those, all come from the `vco-tuning-range` campaign,
  which runs a **63-point PVT grid** — seven bundles, adding `all-slow` and
  `all-fast`, the two combined bundles that skew every device family together
  (passives included) rather than MOS alone. That is a *superset* of the
  mandated grid, so those worst cases are taken over a wider corner universe,
  and the first four each bind at an `all-slow`/`all-fast` corner the mandated
  grid does not contain.
- **Lock detector** rests on a **13-bundle, 117-point** grid — those seven
  bundles plus the six passive-only ones (`res_ff`/`res_ss`,
  `moscap_ff`/`moscap_ss`, `mimcap_ff`/`mimcap_ss`) — shared by all three
  campaigns that row cites. Unlike `vco-tuning-range`'s, this superset moves
  no number it reports, and the row states why rather than leaving the reader
  to assume it either way.
- **Loop bandwidth**, **Phase margin** and **Lock time (small-signal
  settling)** are measured on **no MOS grid at all**, because their DUT has no
  MOS device in it. `loop-dynamics` sweeps the passive loop filter over **81
  filter-impedance points** — 27 passive-corner bundles (`res` × `moscap` ×
  `mimcap`, each `typical`/`ff`/`ss`) × three temperatures — and declares the
  MOS and supply axes N/A, folding the active devices' spread in as *measured
  extremes* rather than re-simulating them: Icp from `cp-compliance`'s own 45
  PVT corners, Kvco from `vco-tuning-range`'s 63. That is a wider envelope
  than the mandated grid on the axis that sets loop stability, not a narrower
  one, but it is not the mandated grid and this table should not have implied
  it was.

The other two are sampled rather than gridded: **Multiplication ratio**'s 235
points are a deliberately non-rectangular sample of a 61 × 45 cross-product
(see that row), and **Reference spur**'s 5 points are a declared subset of the
45, which that row already said.

Until 2026-09-25 this table said almost none of that. Four rows quoted a
corner a reader could not place, in a column whose every other row meant "of
45"; that was fixed the same day, and fixing it left behind every case a
quoted corner does not reveal. A row can rest entirely on a 13-bundle
campaign and still look clean by quoting two of that campaign's MOS corners,
which is exactly what the Lock detector row did.
`sim/lib/check-pvt-coverage-claims.sh` now fails this
repository's CI if a row quotes a corner outside the mandated grid **or rests
on a record measured outside it** without naming the grid it came from, if a
row names a process bundle `sim/harness/corners.py` does not define, or if a
PVT corner count in a row is neither the mandated grid size nor a count the
cited record's committed per-corner evidence produces.

Since 2026-09-25 it also grades the **converse** claim — a row asserting it
covers the *whole* mandated grid ("Full 45-point PVT grid", "All 45 of the
mandated PVT points", "45/45") must cite records whose committed per-corner
evidence, taken in **union**, contains every one of those 45 points. That is a
point-by-point test rather than a count: 45 measured points that are not *the*
45 fail it, while a grid completed across several partial records passes — the
closed-loop period-jitter row below reached the mandated 45 across five
records covering 1, 4, 8, 18 and 16 points, none of them the grid on its own.
The rule was needed because "of 45" is a legitimate thing for a partly-measured
row to say (**Reference spur**'s "5 of 45 PVT points measured, not the full
grid" is honest and stays legal), so the count rule has to allow 45
unconditionally — leaving the strongest claim a row can make, *I measured all
of it*, as the one claim nothing verified. Thirteen rows across this document
and `sim/CHARACTERIZATION.md` make a full-coverage claim; twelve were already
backed point for point, and the thirteenth — `sim/CHARACTERIZATION.md`'s
Verification-owed cross-reference for period jitter — cited campaign
directories instead of records and now names the five its 45 points come from.

The mandated grid is
computed from the harness, not written into the check, so widening the
temperature or supply axis moves what CI enforces in the same commit. Two
more bullets above were, until **#516**, stated here on a hand check rather
than a machine one — `loop-dynamics`' non-MOS corner axis and
`divider-ratio-chain`'s non-rectangular sample. Both are now read from the
committed record rather than trusted: `sim/lib/check-pvt-coverage-claims.sh`
fails if a row restating `loop-dynamics`' "81 filter-impedance points (27
passive-corner bundles x 3 temperatures)" declaration — in full or as a bare
"81-point" echo — disagrees with the record's own sentence, and fails if a
row's restatement of `divider-ratio-chain`'s "235 points run of the 2835"
declaration, or its "61 distinct N" claim, disagrees with the record's own
declared total or the distinct divide-ratio values its committed
`corners/<record-id>/` file names actually carry. `sim/README.md`'s Summary
record format section ratifies the two sentence shapes this reads.

| Parameter | v1 draft target | Measured / derived (3.3 V) | Verdict | Source (dated) |
|---|---|---|---|---|
| Output band | 10–200 MHz continuous | Floor 6.449 MHz (`all-fast`/125 °C/2.97 V); ceiling 247.8 MHz (`all-slow`/−40 °C/3.63 V); 0 non-monotonic curves of 504; worst adjacent-band overlap 27 %. **Measured over this campaign's 63-point PVT grid, a superset of the 45-point mandated grid** (§5.0) — both binding corners are `all-fast`/`all-slow` bundles the mandated grid does not contain | **MET** (open-loop characterization) | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Output band, **closed-loop** | Same, at any legal (N, band, `f_ref`) | Full 45-point PVT grid at both drawn-band edges (90 runs, `pll_top` DUT): **0 of 45 corners reach a sustained in-window PASS at either edge** | **UNMET / open finding** — closed-loop band-edge settling has not yet been demonstrated within the campaign's own measurement window at any corner | `sim/output-range/records/20260819-160843-4e32f91.md` (full grid); `sim/output-range/records/20260819-190341-70a4128.md` (supersedes that record's single `ff`/27 °C/3.30 V `hi` row only, replacing a hand-killed ERROR with a reproducible CAPPED/stall characterization — still not a PASS) |
| Reference input | 1–25 MHz CMOS square wave into `REF`, rising-edge triggered; duty 30–70 %; V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD; edge rate ≤ 5 ns (10–90 %); **reference-source quality explicitly excluded from the jitter and spur budgets** | **The frequency axis is exercised; the electrical contract is not.** `f_ref` spans the whole ratified range: the small-signal `loop-dynamics` cross-product is evaluated at 1/2/4/8/16/25 MHz (the six reference frequencies the [Icp trim-code rule](../../spec/pll.md#icp-trim-code-rule) is stated at), and closed-loop transients run at 1.25/5/20 MHz (`lock-time`, N = 4/16/64 at f_out = 80 MHz), 6.25/12.5 MHz (`supply-sensitivity`) and 25 MHz (`period-jitter`, `reference-spur`). **No record exercises the input contract itself**: every testbench in this repository that has produced a record reporting a jitter, spur or phase-noise number drives `REF` the same way — an ideal full-rail 0 → VDD pulse, 200 ps edges, nominal 50 % duty. `grep -nE '^[vb][a-z0-9_]*\s+ref\s+0' sim/*/testbench*/*.sp sim/*/testbench*/*.spice` returns **16 decks, 13 of them that one shape** (two of the thirteen trim the width by a single edge time). The three exceptions are named, and two of them have records. `sim/reference-input-contract`'s deck, below, varies the reference *waveform* deliberately and **carries no record at all**. `sim/reference-phase-transfer`'s deck (#509, DR-027) and `sim/lock-window-bisection`'s deck (#527, DR-029) do have records, and both drive `ref` from a behavioural source rather than a `pulse()` — the former to displace the reference edge **in time** so it can move mid-run, the latter to switch between two pre-step/post-step `pulse()` trains for its own phase-step bisection — but neither reports a jitter or spur number: `reference-phase-transfer` reports the 20·log₁₀(N) transfer this row's own exclusion asserts, and `lock-window-bisection` reports the `LOCK`-pad deassert latency and trim-code viability DR-029 characterizes (a negative result for that route), which is why the scoped claim above survives both their existence. (That scoping is not a form of words: `sim/lib/check-ref-drive-claims.sh` refuses to let a deviating deck carry a record at all unless a named decision record re-argues the premise for it, and DR-027/DR-029 are those records.) So the levels, the ≤ 5 ns edge-rate budget and the 30–70 % duty range are conditions no simulation *result* has ever varied. Until 2026-09-25 this row stated that uniformity over *decks* rather than over *records*, and offered a `sim/*/testbench/*.sp` glob as the proof — a glob that could not return the one deck which contradicts it, because that deck is `.spice` and landed in the very change (#518) that wrote the sentence. `sim/lib/check-ref-drive-claims.sh` now fails this repository's CI if a command quoted as evidence has a file glob its own pattern can outreach, if an unscoped uniformity claim is false over the decks that command reaches, or if a deck that varies the reference waveform ever produces a record — the last being the one that matters, since every jitter, spur and phase number in this section is stated against an ideal reference *by construction*. `spec/pll.md` states levels and edge rate as **budget**, and duty as an argument from `design/pfd.sch` rather than a result. **A campaign for it now exists and has measured nothing**: `sim/reference-input-contract` holds the DUT at `sim/pfd-deadzone`'s operating point (`pfd_cp`, 25 MHz, Vctrl = 1.65 V, Icp code b1 b0 = 10) and sweeps the `REF` *waveform* instead — the ideal pulse above, plus 0.2·VDD – 0.8·VDD levels, 5.00 ns 10–90 % edges, 30 % and 70 % duty, and one variant at all three limits at once. Its graded quantity is the per-corner shift of the reference-path set delay `d_ref` (reference mid-rail crossing → the instant the PFD acts on it, i.e. the phase the detector sampled), against the 1 ns static-phase bound of the [Lock criterion](../../spec/pll.md#lock-time); the duty row's rising-edge-only argument is stated falsifiably as ≤ 1 % of `d_ref` between 30/50/70 % duty. Manifest, deck and reduction are committed and self-checking; **zero of the 288 declared points are measured** (45 mandated PVT corners × 6 waveform variants, plus an 18-point detector-gain slice at three corners). A campaign directory is not evidence, and no number from it appears anywhere in this document | **Range MET as a swept operating condition; levels, edge rate and duty range UNMET — budget, never measured.** The half of this row a reader must not skip is the exclusion: **every jitter and spur number in this section is the block's own contribution, measured or derived against an ideal reference.** Reference phase noise inside the loop bandwidth reaches the output multiplied by 20·log₁₀(N) — 12 dB at N = 4, 36 dB at N = 64 — so a system integrating this block must budget its own reference against that multiplication; this proposal does not do it for them. **That multiplication is now measured on this design rather than quoted from theory (DR-027, #509)** — `sim/reference-phase-transfer` applies a single known 1 ns reference phase step inside the closed loop and reads the consequence differentially against a paired control run, measuring the in-band transfer at **15.529 … 16.366 dB against the 20·log₁₀(6) = 15.563 dB the formula gives** (error −0.035 … +0.803 dB, 5/5 corners PASS at N = 6), and measuring the roll-off above the loop bandwidth at one frequency as **21.6 … 32.7 dB below** that in-band figure. So an integrator budgeting against the multiplication is budgeting against something this design has been shown to do, to about 1 dB, at one N. **Two distinct benches, and only one of them now exists.** A reference-*perturbation* bench exists and has produced that measurement; the reference-*noise* bench a numeric reference-jitter limit additionally needs — a statistical phase-noise spectrum pushed through that gain against an output jitter allocation — still does not, and is DR-020's recorded methodology gap, owned at #520 (the successor to #505, itself closed). Until 2026-09-25 this row said only "converting the exclusion into a numeric reference-jitter limit needs a reference-perturbation bench that does not exist", which conflated the two. `spec/pll.md`'s own Verification-owed line for this row used to name issue #12, which is **closed** and whose subject is closed-loop lock acquisition — so the work was, until recently, unowned. **DR-019** fixes that attribution in the ratified table: the levels/edge-rate/duty sweep is owed from **#499** (the campaign above), and the reference-jitter limit is recorded as **unowned**, sequenced behind the noise methodology at #520 (the successor to #505, itself closed) — deliberately not re-pointed at #13, which is itself closed, because naming a plausible-looking owner is what hid this obligation in the first place. DR-019 also restates the source-quality exclusion with a boundary — it excludes the *reference source's* phase noise, and does **not** license this block's own reference-input path to contribute; and it names the input-side coefficient an integrator is owed, `dtdv_worst`, the sampling-instant displacement per volt of reference amplitude noise at the worst legal reference slope, which is a deliverable of that campaign and is not covered by the 20·log₁₀(N) line. **None of the electrical-contract lines is a measurement**, and the verdict above is unchanged by any of this: the transfer measurement exercises the *exclusion*, not the levels, the edge rate or the duty range, and **DR-027 Decision 5 says so explicitly rather than letting a measurement in the neighbourhood soften a verdict.** DR-027 also re-argues, rather than re-asserts, the ideal-reference premise this whole section rests on — `sim/reference-phase-transfer` is a deck that varies the reference and *does* have records, so the surviving claim is narrower than it was: **no record that reports a jitter or spur number was measured against a varied reference** (that campaign reports a transfer, in dB, and no jitter or spur number). DR-019 Amendment A2 carries the same narrowing, and `sim/lib/check-ref-drive-claims.sh` enforces it | `spec/pll.md#reference-input` (the contract and the exclusion); DR-019 + its Amendment A2 (the owner, the exclusion's boundary, and the narrowed ideal-reference premise); **DR-027** (the measured transfer, its four named limits, and why it does not move this verdict); `sim/reference-input-contract/testbench/` (manifest, deck and reduction — declared, unmeasured); `sim/reference-phase-transfer/records/20260925-080736-b722f33.md` (the measured 20·log₁₀(N) transfer, 5/5 PASS at N = 6); `sim/loop-dynamics/records/20260731-202550-82af5a9.md` (the 1–25 MHz small-signal axis); `sim/lock-time/records/20260831-052456-effc505.md` (closed-loop `f_ref` = 1.25/5/20 MHz); issue #499 (open) |
| Multiplication ratio | N = 4–64, every integer | 61 distinct N exercised at 200 MHz, 0 ratio errors of 235 chain points; worst retiming setup margin 6.1 % of a VCO period (302.83 ps of a 5 ns period, `ss`/125 °C/2.97 V). **Those 235 points are a deliberately non-rectangular sample of the 61-N × 45-corner cross-product — 235 of its 2835 cells, not a grid** (§5.0): all 61 N run at two stress corners only — `ss`/125 °C/2.97 V and `ff`/−40 °C/3.63 V, 61 points each — while the full 45-point mandated grid runs at N ∈ {4, 33} (86 points) and, at N = 64, thinned to the 2.97 V supply that is the retiming worst case (14 points, plus 1 nominal); a 10 MHz input-rate check at N ∈ {4, 64} adds the last 12. So "every integer" is verified at the two corners where retiming is hardest, and the mandated grid is verified at three values of N — which is what the full cross-product was traded for | **MET** | `sim/divider-ratio-chain/records/20260802-100727-082c879.md` (chain — the `sim/harness`-migrated successor to `sim/divider-ratio/records/20260731-171817-0a12e6c.md`, which is where the chain bench also moved into its own campaign directory; a tooling migration, not a value correction — the superseded record's 235 points, its 61 distinct N and its 3.0283e-10 s worst setup margin at `ss`/125 °C/2.97 V are all reproduced, per that record's own numeric-agreement check), sibling flop/cell records same date |
| Integrated RMS jitter | not spec'd (DR-002 Decision 5) | n/a by design — never presented as a spec'd figure | **N/A, by design** | `spec/pll.md#integrated-rms-jitter` |
| Period jitter (open-loop sensitivity) | ≤ 1.0 % RMS, conditional on ≤ 20 mV pp `vdd_vco` ripple | Worst 2.51 % RMS at 100 mV pp ripple (`all-slow`/−40 °C/2.97 V, band 5); implies 0.50 % RMS at the 20 mV pp budget, leaving headroom for an unmeasured random component. **Measured over this campaign's 63-point PVT grid, a superset of the 45-point mandated grid** (§5.0) — the binding corner is an `all-slow` bundle the mandated grid does not contain. **That grid sweeps one ripple frequency, f_osc/16**; the same record's separate 6-point ripple-frequency sub-sweep, at 27 °C / 3.30 V / band 5 only, reaches 3.24 % RMS at f_osc/4, and the record withholds extrapolation because its quasi-static model under-predicts by 1.2–2.3× — so the binding ripple frequency is unmeasured at the binding PVT corner (§5.1) | **derived, conditional PASS** at the stated ripple budget | `sim/vco-tuning-range/records/20260804-211600-f599a65.md` — the `sim/harness`-migrated successor to `20260731-184845-0a12e6c`, which reports the same 2.51 % RMS worst case at the same corner and carries its own `migration_delta` table over the 1872 measurements the two runs share |
| Period jitter, **closed-loop, deterministic (control-ripple)** | Same 1.0 % RMS line | **All 45 of the mandated PVT points now measured**, at one operating point throughout (f_ref = 25 MHz, N = 6, f_out = 150 MHz, band 6, Icp code 0 — the same as `reference-spur`): the complete temperature × supply plane (−40/27/125 °C × 2.97/3.30/3.63 V) at every one of the five MOS bundles (`typical`, `ff`, `ss`, `fs`, `sf`). Range **0.0508–0.2691 % RMS** across all 45 — worst `typical`/−40 °C/3.63 V, best `ss`/125 °C/3.30 V, a 5.3× span, unchanged by the last 16 points (`fs`/`sf` span 0.0903–0.2472 % RMS, inside those bounds). Temperature is monotone at every bundle (hotter is better) — the finding from `typical`/`ff`/`ss` extends cleanly to `fs`/`sf`. The supply trend does not resolve into a clean two-valued-by-process-sign picture, though: `ff` falls and `ss` rises with supply, `fs` mostly rises (dipping slightly at −40 °C: 0.1903 → 0.1876 → 0.2097 %), and `sf` falls gently at −40 °C like `ff` (0.2472 → 0.2463 → 0.2454 %) but rises at 27 °C and dips at 125 °C — the "sign flips cleanly by process" reading from `ff`/`ss` alone does not fully generalize. One caveat is reported rather than smoothed over, and it has since been **closed**: one of the first five records' **overall status is FAIL**, because 2 of its 18 points fail a lock gate that is not wrap-safe — both loops are demonstrably locked (`fout` within 160 ppm of target, measured N = 6.000, jitter in family with their neighbours) and the gate's phase samples wrapped by exactly one reference period. That was a measurement defect, not a jitter result, and it was filed as issue #273 — **now fixed and closed**. The gate unwraps the phase difference into ±T_ref/2 before differentiating it and gains a wrap-free `ferr_fb` = `ffb`/`f_ref` − 1 corroboration check at ±2e-3 (the `ferr` gate itself is unchanged at ±1e-3), and a sixth record re-measures exactly those two points against it: same simulation, corrected gate — `phi_a`/`phi_b` and `tj_rms` come back identical to the digit and `ferr` reads −1.47e-06 / −1.19e-05 instead of 4.00e-2, both **PASS**. No record of this campaign now carries an unresolved FAIL | **MET at every measured corner (45/45), with a 3.7× margin at the worst of them** — but **no record of this campaign varies the output band**: every point is at band 6 / 150 MHz, so nothing here yet bounds jitter at the 200 MHz top of the ratified band — see the row immediately below | `sim/period-jitter/records/20260905-192724-a2ba48f.md` (first, `typical` only); `sim/period-jitter/records/20260906-015602-f9bef9d.md` (adds `ff`/`ss`/`fs`/`sf`); `sim/period-jitter/records/20260906-024225-12bccda.md` (adds the `typical` temperature × supply plane); `sim/period-jitter/records/20260906-063728-f3c9c23.md` (adds the `ff` and `ss` planes; overall FAIL, see #273); `sim/period-jitter/records/20260906-080511-69b36ef.md` (adds the `fs` and `sf` planes' remaining 16 points, completing the matrix; overall PASS); `sim/period-jitter/records/20260906-095050-3a8a6ef.md` (supersedes `20260906-063728-f3c9c23`'s `ferr` lock-gate verdict at its two failing points **only**, re-measured against the wrap-safe gate of #273 — 2/2 PASS; that predecessor's jitter numbers and its other 16 points stand as recorded) |
| Period jitter, **closed-loop, deterministic, at the 200 MHz band top** | Same 1.0 % RMS line | **No measured record yet — declared, not measured.** `sim/period-jitter-band-top` is the row above's measurement moved to the binding end of the ratified band: same deck structure, same solver tolerances, same reduction module (loaded, not copied), f_ref and the Icp trim code held, N 6 → 8, f_out 150 → 200 MHz. Its full 45-point grid is declared and every point's operating point is derived from the committed VCO record `20260804-162735-72883fb` under [the band-selection rule](../../spec/pll.md#band-selection-rule), re-checkable without a simulator. That VCO record itself runs the **63-point** superset grid, but the derivation reads only its five mandated MOS bundles (`MOS_BUNDLES` in `band_and_vstart_from_vco_record.py`), so what this campaign declares is the mandated grid and not the wider one it is derived from (§5.0). One result did come out of that derivation and needs no simulator: **at 200 MHz the rule does not select a single band code across the PVT grid** — band 6 at 34 of the 45 points, band 7 at the other 11 (the cold and/or high-supply points where band 6's own curve tops out below 200 MHz) — where at 150 MHz one static code covers all 45. Local Kvco at the selected points spans 74.7–117.0 MHz/V, all inside the Kvco row's 150 MHz/V bound, but the loop gain the one fixed filter sees varies 1.6× across this grid against 1.05× across the 150 MHz one | **UNMET — explicitly.** No jitter number at 200 MHz is claimed anywhere in this document. The band split above is a derivation from committed open-loop evidence, reported as such, and is not a substitute for the measurement | `sim/period-jitter-band-top/testbench/` (manifest, deck and derivation; `band_and_vstart_from_vco_record.py --check`); `sim/vco-tuning-range/records/20260804-162735-72883fb` (the f(Vctrl) table it reads); issue #503 (open) — the campaign's unrun measurement, now that #496 (closed 2026-09-25) has landed the batch backend it was waiting on |
| Period jitter, **closed-loop, random/noise-driven** | Same 1.0 % RMS line | **Zero records, and none obtainable on this toolchain** — a disclosed methodology gap, since 2026-09-25 a *located* one (DR-023). ngspice `TRANNOISE` injects nothing on this repo's pinned build, so DR-002 Decision 5's specified transient-noise method cannot be run at all. What DR-023 re-derived is that the device noise data is **not** the missing piece: `.noise` reports each device's channel-thermal and flicker generators for the gf180mcu models at a bias point. Missing is any periodic-steady-state/`pnoise` path (`pss` is not a command in this build) to weight those stationary PSDs over the ring's switching trajectory, across which they move by 46.6 dB and 95.9 dB. The probes are committed and re-runnable at `sim/period-jitter/noise-toolchain-probe/`. Tracked at issue #520 — the successor to #505, which repaired the ownership defect this row carried, and to #13, which closed on 2026-09-08 and left the gap with no owner at all for seventeen days. **Since 2026-09-26 one ingredient of the route out of this exists and is validated (DR-030)**: `sim/period-jitter/isf-bringup/` measures the ring's impulse sensitivity function from charge-injection transients — every injection phase a copy of the whole VCO inside one deck, so the perturbed and unperturbed trajectories share one adaptive timestep sequence — and shows it **converged against that timestep** at the 2 ps ceiling it runs at: ≤ 0.02 % over the last halving of the ceiling (2 ps → 1 ps) at every sampled phase including the two switching edges. The qualifier is part of the result — the *first* halving of that sweep, 8 ps → 4 ps, still moves `h` by up to 2.32 %, so 8 ps is not a converged setting and the claim is about the last step, not about every halving. That was the risk #520 named as the route's load-bearing one, and it is retired with a number rather than argued about. It changes nothing in the verdict column: the pipeline needs two more ingredients (an `S_id(V_gs, V_ds)` table per ring device class, and the ring's own bias trajectory to evaluate it along) and those are exactly where the cyclostationary weighting happens. **Since 2026-09-26 those two exist as well, and so does the bound the cheaper route owed (DR-031)**: `sim/period-jitter/sid-trajectory/` measures each ring device's channel-thermal and flicker generator at the bias it actually occupies at 24 phases of the cycle, and the trajectory it is evaluated along, at three PVT points, on the ISF bring-up's own reference deck so both sit on one phase axis (periods agree to −3.7 × 10⁻⁶); and against the `h²`-weighted average the jitter integral contains, biasing each device at its own peak-\|I_d\| phase reproduces the channel-thermal generator to **−1.15 … +1.06 dB** for all four device classes. **The verdict column still does not move**: the assembly is not built, that bound is measured at 1 of the 45 mandated corners while the unweighted cyclostationary spans move 40 dB across three, the two device classes whose ISF weight is exactly available are the ones measured on the coarsest phase grid (an effective 2.4 of 12 phases), and the flicker half is not a defined quantity until `spec/pll.md`'s Period jitter row states an observation interval — which its Verification-owed table now records as owed. So no jitter figure exists at any corner | **UNMET — explicitly, not omitted.** This is the one row this proposal cannot report a number for at any maturity. **And it is worse than one unmet row**: `spec/pll.md`'s own supply-ripple derivation allocates 0.50 % RMS of the 1.0 % target to this component, so half the jitter line is an unverified budget — DR-023 §Decision 3 now says that in the specification rather than leaving it in an arithmetic aside | issue #520 (open); `spec/decision-records/DR-023-random-period-jitter-owner-and-cyclostationary-gap.md` (re-points `spec/pll.md`'s Verification-owed row off the closed #13 and records the budget split); `sim/period-jitter/noise-toolchain-probe/` (the four probes DR-023 rests on, re-runnable) |
| Phase noise | not spec'd (DR-002 Decision 5) | n/a by design | **N/A, by design** | `spec/pll.md#phase-noise` |
| Reference spur | ≤ −55 dBc | −57.0…−72.7 dBc measured at 150 MHz (5 spanning corners); scaled to the binding 200 MHz, the two coldest corners land at −54.5/−54.9 dBc (0.1–0.5 dB over the line). **That measurement runs with charge-pump mismatch off.** The derivation it cross-checks has since been re-priced by DR-018 (#483): with the UP/DN current mismatch ("term 1") counted at its statistical 3σ instead of its systematic value, and the statistical residual refreshed to the corner-combined Monte Carlo campaign, the deliberately conservative 200 MHz stack lands at ≈ −57.0 dBc with term 1 at its measured 17.48 % and **−56.6 dBc** at its ±20 % budget — **1.6 dB inside the line**, where the older −61 dBc derivation, which left term 1 out, implied a ~6 dB reserve | **PASS at 150 MHz (5/5 corners); UNMET at the scaled 200 MHz binding point for 2/5 corners** — 5 of 45 PVT points measured, not the full grid. The derived stack including mismatch clears the line, but by 1.6 dB rather than ~6 dB (DR-018), so the reserve this row was once argued on is mostly spoken for. The owed work was handed by `spec/pll.md` to #145, which is closed. **DR-024 (#510) re-points it and restates it**: what is owed is the mandated 45 points *at the binding 200 MHz* — not 40 more at 150 MHz that would still have to be scaled by +2.50 dB. **#510 is closed** (superseded by #533, per the Curator's 2026-09-25 disposition on the Judge's review of #537 — #510's own remaining acceptance criteria, the 45-point 200 MHz grid, are exactly #533's scope, so the obligation moved rather than closing unmet) — and it is owed at **#533**, against a campaign that now exists and is declared-and-unmeasured (`sim/reference-spur-band-top`, 0 of 45 points). DR-024 also states which derived row a *mismatch-off* measurement may be read against: the systematic-only **−66.6 dBc**, not the −56.6 dBc stack above, which adds two statistical terms at their own worst corners. Read that way, the committed 150 MHz measurement already exceeds the systematic derivation by ~12 dB at the two cold corners while sitting 3.6 dB below it at the derivation's own worst corner — so the derivation does not predict the measurement's corner ordering, and the closed-loop **statistical** spur is unowned | `sim/reference-spur/records/20260816-132150-5f405e7.md`; `spec/pll.md#reference-spur` (the re-priced derivation table); `spec/decision-records/DR-018-cp-term1-mismatch-budget-derived-from-the-spur-line.md`; `sim/mc-cp-mismatch/records/20260923-095854-1655e11.md` (the Monte Carlo campaign the 17.48 % comes from — a **3-corner subset** of the mandated 45, `ff`/−40 °C/3.63 V, `typical`/27 °C/3.30 V and `ss`/125 °C/2.97 V, at n = 100 mismatch samples each); `spec/decision-records/DR-024-reference-spur-binding-point-owner-and-mismatch-relation.md`; `sim/reference-spur-band-top/testbench/tb.json` (declared, no record); issue #510 (closed); issue #533 (open) |
| Loop bandwidth | 26–430 kHz over the ratified space, `f_c < f_ref/10` | 25.96–429.5 kHz measured; worst realized `f_c/f_ref` = `f_ref/13`, inside the ceiling at every point of the cross-product. **Not measured on the MOS grid, because the DUT has no MOS device in it**: `loop-dynamics` sweeps the passive loop filter over 81 filter-impedance points (27 passive-corner bundles × 3 temperatures) and declares the MOS and supply axes N/A, folding the active devices' spread in as measured extremes — Icp from `cp-compliance`'s own 45 PVT corners, Kvco from `vco-tuning-range`'s 63 — rather than re-simulating them. That is a wider envelope than the mandated grid on the axis that sets stability, not a narrower one (§5.0) | **MET** | `sim/loop-dynamics/records/20260731-202550-82af5a9.md` |
| Phase margin | ≥ 45° in the contracted (trim-rule) space | Worst 47.4° at `f_ref` = 1 MHz, 4 legs; 105/140 cells pass unconditionally, all 35 failures are off-rule trim codes. Same 81-point filter-impedance basis as the row above (§5.0) | **MET** (in the contracted space) | Same record |
| Lock time (small-signal settling) | < 100 µs to the ratified Lock criterion (output frequency within ±0.1 % **and** static phase error at the PFD inputs ≤ 1 ns) | Worst 71 µs (`f_ref` = 1 MHz, 4 legs); structural floor ≈ 43 µs (set by `1/(2πRC1)`, a derivation rather than a grid minimum); 120/140 cells meet the line, 0/140 meet the dropped < 20 µs stretch. The settling half of this row shares the Loop bandwidth row's 81-point filter-impedance basis, not the MOS grid (§5.0); the static-phase half below is measured on the mandated 45. **But the criterion this time is measured *to* is not reached at 1 of the 45 mandated corners at the configuration the normative band-selection rule selects, with a second corner owed** (DR-012, narrowed by **DR-025**): closed-loop, the loop settles at 1.049 ns of static phase at `typical`/−40 °C/3.63 V against the ratified ≤ 1 ns — nominal skew, systematic only, before the 0.576 ns statistical mismatch term — so at that corner there is no instant for a lock time to be measured to. The **1.227 ns** at `ff`/27 °C/3.63 V is a correct measurement of **band 6**, which is not the band the rule selects there over DR-003 Decision 5's measured 0.9–2.7 V control window (it selects band 5, `VCTRL` 1.967–2.595 V); that cell has never been run closed-loop, so the corner is neither cleared nor confirmed and the count returns to 2 of 45 if it misses. The axis it is lost on is the control voltage, not the corner: at `VCTRL` = 0.90 V the charge pump's residual charge alone exceeds the whole criterion at 36 of 45 corners, open-loop — and **DR-025 measures that the band-selection rule cannot fix that**: applied across the ratified 10–200 MHz output band it still parks some corner at `VCTRL` ≤ 1.05 V at 23 of 39 output frequencies (floor 0.919 V) and still misses the criterion on DR-012 Decision 4a's summed budget at 1397 of 1628 rule-selected points, so the resolution must reduce the pump's residual charge at low `VCTRL` | **MET as a settling estimate (not cold-start) — and NOT MET at 1 of 45 corners at a rule-compliant configuration, with a 2nd corner's rule-selected configuration owed**, where the Lock criterion itself is never reached, exactly as `spec/pll.md`'s own row states it. DR-012 Decision 1 keeps the criterion unrelaxed and DR-025 Decision 1 restates it unchanged, so this is a design gap, not a spec one — and DR-025 narrows DR-012 Decision 7's four candidate loci to one (the pump's residual charge at low `VCTRL`) by eliminating the band-selection axis on measurement. Its settled value at 15 further over-bound corners is owed at #399 (open). **#511 is closed** (COMPLETED) — it is the issue DR-025 was filed against, and DR-025 discharges it by narrowing the four candidate loci to one; it did not run either closed-loop cell it named, and does not claim to. Those two runs (the rule-selected `ff`/27 °C band-5 cell, and the lowest rule-compliant parking anywhere in the output band — f_out = 135 MHz at `ss`/125 °C, `VCTRL` 0.919 V) are owed at **#540 (open)**, filed because both are multi-hour ngspice campaigns outside a Builder session's scope | `sim/loop-dynamics/records/20260731-202550-82af5a9.md` (settling); `sim/supply-sensitivity/records/20260916-051708-8cedbba.md` (the 1.227 / 1.049 ns settled static phase); `sim/supply-sensitivity/records/20260925-090649-4422f1d.md` (the band-selection re-derivation, arithmetic only, no new simulation); `spec/decision-records/DR-012-static-phase-offset-evidence.md`; `spec/decision-records/DR-025-band-selection-is-not-the-lock-criterion-resolution.md`; issue #399 (open); issue #511 (closed); issue #540 (open) |
| Lock time, **closed-loop cold-start / worst-case re-lock** | Same < 100 µs line, cold-start basis | Full 270-run grid (45 corners × N ∈ {4,16,64} × {cold, relock}): sustained in-window `LOCK` PASS on **21/135** cold rows and **1/135** relock rows within the tested window; the remainder read as window-too-short (not necessarily non-convergent) per the record's own DN-branch integration guard (255/270 PASS, confirming the transient itself resolved correctly on those rows) | **UNMET as a closed PASS bound** — real evidence now exists where `spec/pll.md` still lists this as "budget," but it does not establish that most corners lock inside any stated time | `sim/lock-time/records/20260831-052456-effc505.md` |
| Power | < 5 mW at 100 MHz, locked | Derived total ≈ 1.98 mW at the binding corner (`all-fast`/125 °C/3.63 V) from the open-loop/interpolated basis `spec/pll.md#power` uses. Its one measured term (`vdd_vco`, 318 µA) is the worst of the 159 grid points with 90 ≤ f_osc ≤ 110 MHz in that record's `vco_tuning.csv`, taken over the campaign's **63-point PVT grid, a superset of the 45-point mandated grid** (§5.0) — the binding corner is an `all-fast` bundle the mandated grid does not contain. The `vdd_div` term is an interpolation and the `vdd_ref` term is a budget, so this row is not a measurement at any grid | **MET** (derived) | `spec/pll.md#power`, whose `vdd_vco` line reads `vco_tuning.csv` from `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Power, **closed-loop measured** | Same line | Full 45-point grid + all 3 step/ramp corners: **0.9863–1.98 mW measured directly** (not derived), all points under the 5 mW target; quiescent/dynamic split reported per corner | **MET, measured** — supersedes the derived figure above with a direct closed-loop measurement | `sim/supply-sensitivity/records/20260901-155456-46b92f8.md` |
| Standby current | waived — no power-down mode in v1 | n/a — no standby state exists | **N/A, by design** | `spec/pll.md#standby-current` |
| Supply sensitivity — AC (ripple) budget | `vdd_vco` ripple ≤ 20 mV pp | Derived from the 2.51 %/100 mV pp measured sensitivity above, so it inherits that row's corner universe: this campaign's **63-point PVT grid**, a superset of the 45-point mandated one (§5.0), whose measured sensitivity binds at an `all-slow` bundle the mandated grid does not contain. The budget is therefore stated against the stricter of the two grids, not the mandated one. It also inherits that row's *ripple-frequency* limit: scaling the f_osc/4 sub-sweep's 3.24 % instead gives 0.65 % RMS at this budget rather than 0.50 %, still inside the 1.0 % line but at 1.5× margin instead of 2× (§5.1) | **derived, conditional** | Same record — `sim/vco-tuning-range/records/20260804-211600-f599a65.md` |
| Supply sensitivity — DC / closed-loop, full grid | ≤ 0.6 V of the `VCTRL` window consumed by a rail excursion (`spec/pll.md` Budget 2); stays locked through a supply step + ramp | Full 45-point grid, with each of the record's three FAILs read against the **ratified** line rather than the deck's proxy for it (**DR-021**). **(1) The frequency-vs-supply FAIL has no frequency content**: 0 of 45 corners missed either frequency check — worst deviation −294 ppm against a 1000 ppm criterion (3.4× headroom), worst residual frequency error 2.255e-4 against 1e-3 (4.4×). Its 10 failing corners are the composite lock criterion's *other* checks, 2 static-phase and 8 lock-flag, and DR-012 measured both classes against the ratified ≤ 1 ns static-phase bound: the 2 were sampled while still decaying (0.60–0.72 ns of movement across the run's own window), and the 2 settled violations — the corners that **are** over the bound once settled — are inside the 8. It is the same static-phase finding as the Lock time row above. **(2) Budget 2 is measured for the first time, and missed**: the closed loop consumes 0.385 … 0.846 V of the `VCTRL` window over the ratified 2.97–3.63 V rail — over the 0.6 V budget at **9 of the 15 (bundle, temperature) cells**, worst `ss`/−40 °C at **0.846 V** (1.41×, 47 % of the 1.8 V window). It is not an anomaly: it matches what each cell's selected band requires, from the open-loop `f(VCTRL, vdd)` table, to within 5.7 mV at every cell. The record's own "4 of 45 outside the window" FAIL is graded against DR-001's *predicted* 0.9–2.4 V window, which DR-003 Decision 5 superseded with a measured 0.9–2.7 V; against that window **0 of 45 points leave it**, by 53 mV at the tightest. **(3) The step+ramp FAIL is a hold ≈8 µs short of a slew-limited recovery, not an under-damped loop**: the retained waveform shows the control node slewing at a near-constant −20.3 mV/µs for 18.75 µs after the ramp at `ss`/−40 °C (a straight line fits it with 33 % less residual than a single exponential, in volts, on the same samples), and the model-free damping test — overshoot past the final value — does not separate that corner from the two the record calls `settles` (17.2 mV on 20.0 mV of its own ripple, against 19.5 and 22.5 mV). What separates it is that it is criterion 2's worst cell: the corner that consumes the most `VCTRL` window for a rail excursion takes longest to recover from one | **UNMET on Budget 2, at 9 of 15 cells** — and that is the sharper of two readings, not the softer one: Budget 2's own derivation prices a ±0.33 V excursion (under which 0 of 15 cells exceed it) while the row specifies the 0.66 V full range, and this proposal reports the row as written rather than the reading under which it passes. The consequence the budget guards against — re-cutting the band plan — is **not** observed, and is 53 mV away. **Every finding now has a named open owner**, which is what #506 was filed for: the excursion question and the deck's mis-graded criterion are **#525 (open)**; the static-phase finding is DR-012's, narrowed by DR-025 — **#511 is closed** (DR-025 discharged it without running either cell it named), and the two runs that would settle it are owed at **#540 (open)** — plus **#399 (open)** (the 15 corners sampled on a tail) and **#437 (open)** (the full-grid re-take at the trimmed detector window); the post-ramp settling measurement is **#405 (open)**. No recorded verdict or value changes — `sim/` is append-only | `sim/supply-sensitivity/records/20260925-044237-4ff4f65.md` (the re-reading, arithmetic only, no new simulation) over `sim/supply-sensitivity/records/20260901-155456-46b92f8.md` (the grid); `spec/decision-records/DR-021-supply-sensitivity-fail-criteria-ownership.md`; `spec/decision-records/DR-003-vco-band-map-and-kvco-contract.md` Decision 5 (the measured control window); issue #525 (open); issue #511 (closed); issue #540 (open); issue #399 (open); issue #437 (open); issue #405 (open) |
| Output duty cycle | 45–55 % at `CLK`, full band, all corners | 44.375–50.696 % measured (90 points, loaded); 7/90 points below the 45 % floor, all at the low-frequency band edge, concentrated in the `fs` process bundle | **UNMET at 7/90 points** (small excursion, 0.625 pp worst-case) | `sim/output-driver/records/20260817-100354-0e9cfc9.md` |
| Output levels and drive | V_OH ≥ 0.9·VDD_VCO, V_OL ≤ 0.1·VDD_VCO into ≤ 50 fF | V_OH 1.006–1.044·VDD_VCO, V_OL −0.040…−0.006·VDD_VCO, 90/90 points | **MET**, full 90-point grid | Same record |
| Area | ≤ **0.30 mm²** total — **amended by DR-016** (issue #456) from the draft ≤ 0.15 mm², on the measurement in the next column, and **held** there by **DR-017** (issue #476) on a floor re-measured 17.5 % lower | **Measured at the block level, and the spec row is now amended to it.** Every sub-block's as-drawn footprint, taken from the committed GDS bounding box rather than a hand-recorded figure: loop filter 0.0369 mm² (still a calculation — the loop filter has no placed-and-routed layout yet), VCO 0.0318 mm² (172.52 × 184.48 µm), PFD + charge pump 0.0256 mm² (344.98 × 74.30 µm — it was 0.0353 mm² before the #455 fold, 0.0267 mm² before the #469 glue-bus packing and 0.0264 mm² before the #473 glue-inverter interleave), divider chain 0.0553 mm² (1317.66 × 41.99 µm — it was 0.2471 mm² as first drawn and came down 78 % through the #341 routing-track-packing, #344 row-fold, #454 macro-track-packing and #458 route-over-the-device-rows passes), lock detector 0.0306 mm² (294.80 × 103.75 µm — grown ~4.1× from 0.0075 mm² by issue #449, which drew DR-014's 4-bit trim network into `delaywin_3v3` and, with it, the block's first LVS match against its own ratified schematic). Sum **0.1803 mm²**, or **0.2254 mm²** after the floorplan's own ×1.25 top-level-overhead factor (it was 0.2186 / 0.2733 mm² when DR-016 was written; #469's glue-bus packing, #458's route-over-the-device-rows pass and #473's glue-inverter interleave have taken 38,324 µm² off since, without moving the row) | **MET against the amended row — 0.2254 mm², 75.1 % of ≤ 0.30 mm² — and 1.50× over the draft 0.15 mm² target, which is now *measured* to be unreachable rather than merely unmet.** DR-016 is the amendment and the honest reading of it is this: the draft number was never derived from anything (DR-007 Amendment A3 called it "the one `budget` row in the table with no rationale behind the number at all"), and the 78.6 % of it that had no estimate of any kind is now four committed, DRC/LVS-clean block layouts. Three measured bounds, each tighter than the last, and none reaching 0.15 mm²: as drawn **1.50×** (1.82× when DR-016 was written; #469, #458 and #473 have since landed, below); every remaining named layout lever at its geometric ceiling **1.20×**; and — the one that settles it — **every Metal2 track routed at zero area cost, 1.13×**, a bound that survives any row fold and covers every lever this design has. 57.2 % of what a 0.15 mm² row allowed is consumed by two terms no post-layout lever touches: the loop filter (set by DR-006's C1/C2 *capacitance*, so reducing it is a loop-dynamics change) and `vco_block`, whose height *is* its device band and whose 60.8 % whitespace is the guard-ring and 15 µm tap-pitch spacing the foundry deck requires. The amended row is the measured total plus margin sized to the single unmeasured factor in it (it holds for a top-level overhead up to ×1.664 on the sum as drawn today), **not** an allowance for block growth. Three levers have landed since DR-016 and none has moved the row — **by decision, not by lag**: DR-017 re-measured the floor after all three and **held** the row, because a margin sized to an uncertainty does not shrink when the measurement beneath it does, and the ×1.25 top-level overhead it covers has not moved. DR-017 Decision 3 also **replaced** DR-016's original trigger (any material lever landing is grounds for a downward successor record), which fired three times in two days: the row is now re-amended *down* when the uncertainty itself shrinks — an assembled `pll_top` GDS measures the top-level overhead, or the loop filter is drawn — and a further block-level lever (an unnamed `lock_detector` one remains open) earns a measured-table refresh, not a new row. Of the three: #469's glue-bus packing, at 259 µm², and #473's glue-inverter interleave, at 776 µm², are small; **#458** is not — it routed the divider chain's Metal2 tracks into the plane over its own device rows, 0.0926 → 0.0553 mm² (74.4 % of its sized ceiling), DRC-clean on both decks and still LVS-matched, moving the total 1.82× → 1.51× under an unchanged row. The divider-chain packing lever (#454) is already spent: packing the `div23_cell` macro's own Metal2 track band (31 nets onto 11 tracks, the provable minimum) took that block from 0.1321 to 0.0926 mm², moving the total from 2.03× to 1.70× on its own. Shared-diffusion device stacking — which this proposal previously named as *the* cause — remains worth only **0.10 %** of the (now larger) gap, falsified rather than deferred, because the divider chain's drawn diffusion is ~1 % of its own bounding box. The `pfd_cp` fold (#455) is spent as well, taking that block 0.0353 → 0.0265 mm² and the total from 1.89× to 1.82× (and #469's glue-bus packing plus #473's glue-inverter interleave have since taken it to 0.0256 mm², a further 0.5 % of the total — "Known gaps" item 8) — but it landed at **42 % of its sized ceiling**, and the shortfall was measured to be in the ceiling (a flat 57-track census over five levels of composition, of which `pfd_cp` owns 4) rather than in the execution. `lock_detector`'s own new footprint is not yet levered against at all. Earlier revisions of this row projected a post-lever floor of 1.64×, then 1.54×; both carried `divider_chain`'s pre-#454 ceiling, and re-derived from the current audit the figure is the 1.20× above — *better* than the record had been carrying, and still over (PLL-FLOORPLAN.md §5.11). §5.13 adds one caveat to that ceiling: `max(packed-track floor, device band) × width` assumes a block's tracks occupy an exclusive band, which is exactly what #458 stopped being true for `divider_chain`, so that block's term in any future ceiling sum has to come from its device band (0.0347 mm²) instead. A fourth lever, sized against `lock_detector`'s own newly-measured 65.5 % whitespace, is still not named. Note this is a **sum of block extents, not a placed-and-routed top level** — no assembled `pll_top` GDS exists, so top-level routing and inter-block spacing are not in this number, and that is exactly the uncertainty the amended row's margin is sized to | `spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md` (the amendment); `layout/evidence/area-audit/PROOF.md` (every lever's arithmetic; reproduce with `python3 layout/run_pv.py area`); `spec/decision-records/DR-017-area-row-held-at-0.30-on-the-refreshed-measured-floor.md` (the hold, and the replaced trigger); `layout/floorplan/PLL-FLOORPLAN.md` §5.1–§5.15 (the re-derived budget; §5.15 is DR-017's); `layout/evidence/vco-layout/PROOF-381-high-rs-resistor.md`; `layout/evidence/pfd-cp-layout/PROOF.md` + `PROOF-455-fold.md` + `PROOF-469-glue-bus-packing.md` + `PROOF-473-glue-inverter-interleave.md`; `layout/evidence/divider-chain-layout/PROOF-macro-track-packing.md` + `PROOF-over-device-rows.md`; `layout/evidence/lock-detector-layout/PROOF.md` "Addendum 4"; `spec/pll.md#area` |
| Lock detector | assert window within **1 … 2 ns** of phase error at every PVT point (T1′/T2′, DR-010/DR-013), measured at the `lock` flag rather than at the bare delay chain; hysteresis ≥ 25 % of window (T3); deassert ≤ 1 `f_ref` period (T4); no chatter 1–25 MHz (T5). **Conditioned on the [lock-detector window trim-code rule](../../spec/pll.md#lock-detector-window-trim-code-rule)** | Re-characterized in situ on the trimmed `delaywin_3v3` cell (DR-014, #411): window edge **[1.14, 1.16) ns** at `fs`/−40 °C/3.63 V and **[1.78, 1.80) ns** at `ss`/125 °C/2.97 V, each at the code the trim rule selects, PVT spread **1.53–1.58×** against DR-013 Decision 4's ≤ 1.65×. 0 of 205 points fail the four-check acceptance; worst deassert latency 5.63 ns. The **untrimmed** cell sat at [2.02, 2.04) ns with a 1.91–1.96× spread — outside the band at every fixed code. **Measured over a 13-bundle, 117-point PVT grid** — the mandated five MOS bundles plus `all-slow`/`all-fast` and the six passive-only ones — which all three cited campaigns share, including the 1872-point trim code map (§5.0). **Unlike `vco-tuning-range`'s superset, this one moves nothing**, and that is checkable rather than asserted: the eight added bundles re-skew only the passive `.lib` sections, this DUT is an inverter-chain delay with no passive device in the measured path, and all 72 of their points reproduce their MOS twin's `twin_r`, `twin_f` and verdict to the digit in the record's own `raw_measures.csv`. Every quantity quoted here binds at a mandated-grid bundle: both window edges; the 1.1084 ns minimum bare-chain `t_win` over all 205 points, at `fs`/−40 °C/3.63 V, which the ≤ 1.62× resolution-independent bound rests on; and the 5.63 ns worst deassert at `sf`/125 °C/2.97 V | **T1′/T2′ MET, conditional on the trim rule** — this row supersedes this proposal's earlier "T1/T2 UNMET" reading, which predated #411. **T4/T5 still UNMET/uncharacterized below 25 MHz.** Three things a reader must not miss: an **untrimmed part is outside this specification**; the trim code table is schematic-level and mismatch-free, so the rule is not yet proven against a real trimmed part; and **the rule has no executable route on silicon — now measured, not merely unexamined**: its measurand is `t_win`, the `ERR → ERRD` delay of an internal cell, and neither node is a pad; **DR-022** (#501) measured all four candidates §2.2's pad list offers against the cell's own sixteen-code map over the full 13-bundle grid, and none selects the code to the accuracy this row's 1.53–1.58 × spread figure assumes — reading `CLK`'s frequency is *worse than not trimming* (2.434 × against 1.984 × untrimmed), and the best candidate, the `CLK`→`DIVOUT` skew, holds the band but lands at 1.697 × with a worst code error of +4 (§4 step 4, §7 item 11). `spec/pll.md` keeps this row inside DR-007 Amendment A1's ratification carve-out for exactly those reasons | `sim/lock-detector/records/20260919-002812-1b12179.md` (the 205-point in-situ verdict); `sim/lock-window-trim/records/20260917-185928-8adff3d.md` (the 1872-point code map the trim rule's table comes from); `sim/lock-window-proxy/records/20260925-050022-6d57802.md` (DR-022's 117-point pad-referred-candidate verdict); `sim/lock-window-sizing/records/20260915-202802-79c0cee.md`; superseded predecessors `sim/lock-detector/records/20260731-162119-0a12e6c.md` and its immediate `sim/harness`-migrated successor `sim/lock-detector/records/20260802-050119-c24ee3a.md` (a tooling migration over the same 95-point matrix, not a value correction), which the DR-010 re-characterization `sim/lock-detector/records/20260916-052313-b1633b5.md` (#393) supersedes in turn — the untrimmed `20260916-122705-98c935b` and then the DR-014-trimmed re-run cited first above carry the claim from there |
| Kvco | ≤ 150 MHz/V under the band-selection rule | Worst 115.8 MHz/V (`all-fast`/27 °C/2.97 V, B6); an adversarial band choice reaches 154.3 MHz/V, over the line, which is why the rule is normative. **Measured over this campaign's 63-point PVT grid, a superset of the 45-point mandated grid** (§5.0) — the binding corner is an `all-fast` bundle the mandated grid does not contain | **MET**, conditional on the band-selection rule being followed | `sim/vco-tuning-range/records/20260731-175947-0a12e6c.md` |
| Supply range | 3.3 V ± 10 %, 3.3 V devices exclusively | Every campaign above sweeps 2.97/3.30/3.63 V | **MET, as the swept independent axis of every other row** | `spec/pll.md#supply-range` |
| Supply range, **5.0 V analog rail** | Challenge #5 asks analog blocks to operate across 3.3–5.0 V | **No 5.0 V-class device exists in this design; never simulated above 3.63 V** | **UNMET / not attempted** — the single most load-bearing gap in this proposal, stated plainly per §2.1 | This proposal, §2.1 |

No row above is relaxed, narrowed, or omitted to make it pass. Every row the
table reports as wholly or partly not met is listed here, by its own parameter
name, with the part that is not met — exactly as the underlying evidence
states, per `CLAUDE.md`'s "agents do not relax the ratified spec to make
results pass":

- **Output band, closed-loop** — no sustained in-window PASS at either
  drawn-band edge at any of the 45 mandated corners.
- **Reference input** — the levels, edge-rate and duty-range lines are budget,
  never measured; every jitter and spur number here assumes an ideal reference.
- **Period jitter, closed-loop, deterministic, at the 200 MHz band top** —
  declared, not measured; no jitter number at 200 MHz exists.
- **Period jitter, closed-loop, random/noise-driven** — no record at any
  corner, so the half of the 1.0 % RMS line allocated to it is an unverified
  budget.
- **Reference spur** — over the line at the scaled 200 MHz binding point at 2
  of the 5 measured corners; the other 40 mandated points are unmeasured.
- **Lock time (small-signal settling)** — the Lock criterion it is timed to is
  not reached at 1 of the 45 mandated corners at a rule-compliant
  configuration, with a second corner's rule-selected run owed (DR-012,
  narrowed by DR-025).
- **Lock time, closed-loop cold-start / worst-case re-lock** — no closed PASS
  bound; most rows do not reach a sustained `LOCK` within the tested window.
- **Supply sensitivity — DC / closed-loop, full grid** — Budget 2 missed at 9
  of 15 cells; the record's other two FAILs are re-read under DR-021 as the
  static-phase finding and a slew-limited step+ramp recovery, each with an
  open owner.
- **Output duty cycle** — below the 45 % floor at the low-frequency band edge.
- **Lock detector** — T4/T5 uncharacterized below 25 MHz. T1′/T2′ are met only
  on a part trimmed to the rule, which no procedure available at this die's
  pads can perform (DR-022, DR-029).
- **Supply range, 5.0 V analog rail** — no 5.0 V-class device; never simulated
  above 3.63 V.

This list is machine-checked against the table rather than kept by hand:
`spec/lib/check-spec-row-coverage.sh` fails if a row whose Verdict says UNMET
or NOT MET has no bullet here, or if a bullet names a row that no longer says
so. Until 2026-09-26 it was a single hand-kept sentence, and it had drifted
three ways: it omitted four of the rows above outright (the 200 MHz band-top
jitter, the reference spur, the closed-loop cold-start lock time and the output
duty cycle), it still listed the lock detector's T1/T2 window as unmet after
#411's trim met it on a trimmed part, and it counted the Lock-criterion miss at
2 of 45 corners after DR-025 narrowed it to 1.

### 5.1 Value provenance: which quoted numbers CI re-derives from committed evidence

**Eleven checks grade the table above. Until 2026-09-26 none of them graded a
number.** They grade counts, citations and their supersession, spec-row and
decision-record coverage, the I/O list, the corner universe a row was measured
on, the reproduction commands, the bias-pin drive, and the forge references —
so a row could cite the current record, name the right grid, carry the right
verdict, and still quote a value that is not in that record. The largest
remaining ungraded surface was the measured value itself.

The table below closes it for the values it names. Each entry gives the
`sim/` record, the committed per-corner evidence inside it — a reduced CSV, or
the record's own per-point table where that is what the campaign committed — and
the reduction that produces the figure, and
`sim/lib/check-quoted-value-provenance.sh` fails this repository's CI if the
re-derived value does not equal the figure **rounded to the precision written**
(`247.8 MHz` against a derived 247.751 passes; against 247.6 it does not), if
the figure has drifted between §5 and this table in either direction, if an
entry reduces a record the §5 row does not itself cite, or if a §5 row is
accounted for by neither a graded value (this table or the derived-figure one
below) nor a stated reason.

The reduction language is `min`/`max`/`mean`/`sum`/`sig3`/`count` over one
committed table, optionally grouped (`max(min(fosc_hz) by bundle+temp_c+vdd_v)`
is the worst-case *guaranteed* floor: the lowest frequency each corner can
reach, taken over corners) and optionally filtered (` where col op value`, with
`~=` for substring containment on an id column). One named
filter, `on-icp-trim-rule`, is the contracted space the loop-dynamics rows are
stated over — the (f_ref, trim-code) pairing
[the Icp trim-code rule](../../spec/pll.md#icp-trim-code-rule) requires. **That
rule is read out of `spec/pll.md` by the check, never written into it**, for the
same reason `check-pvt-coverage-claims.sh` computes the mandated grid size from
the harness: if the ratified rule changes, what CI enforces changes in the same
commit.

Two figures in the Output band row are properties of an ordered *curve* rather
than reductions of cells, and the language carries a group-sequence form for
them. `count(non-monotonic(fosc_hz by vctrl_v) by bundle+temp_c+vdd_v+band)`
orders each of the 504 (corner, band) curves by control voltage and counts the
curves that are neither non-decreasing nor non-increasing — *monotonic* as this
document words it, in either direction. `min(adjacent-overlap(fosc_hz by band)
by bundle+temp_c+vdd_v)` takes, per corner, the worst
`max(f in band k) / min(f in band k+1) − 1` over every band code `k` and its
successor `k+1`, which is negative if a corner leaves a coverage hole. The
pairing is `band` with `band+1` rather than "the next band code present", so
the ordering column has to be integer-coded and spaced by exactly 1: a corner
holding bands `0, 1, 3` is **rejected** rather than examined over its one
remaining pair. **The monotonicity figure is a zero, which is the most
dangerous kind of figure to grade**: a derivation that quietly examined nothing
reports the same `0` as a clean grid. So the check treats an empty group set, a
curve with fewer than two points, and a repeated control voltage inside a curve
as failures rather than passes, and prints the number of groups it examined
(`867` here: `504` curves, `63` corners, and the `300` Monte Carlo samples of
the next paragraph) in its own OK line. A worst *overlap* is silent in the same
way about how many intervals it was the worst of, so that line also prints the
number of adjacent band pairs examined (`441` here: `7` pairs across each of
the `63` corners' `8` bands).

**One figure is a statistic rather than an extremum, and it needed the language
to grow** — the Reference spur row's term-1 mismatch figure, **17.48 %**. It is
`|mean| + 3σ` (`sig3`, with σ the *sample* standard deviation) over the
per-sample worst-magnitude of three control-voltage points, at the worst of the
campaign's three corners: three nested reductions rather than one,
`max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)`. Every level
is load-bearing, and **the two readings DR-018 priced against this one are both
smaller** — 13.2172 % with the samples folded to their magnitudes before the tail
is taken, and 10.94 % with that folding *and* the three corners pooled. That is
why **DR-018 Decision 3** names the statistic instead of describing it: the
campaign's own reported figure moved from the folded reading to this signed one
under DR-018 Amendment A1 (issue #487), *raising* term 1 from 13.22 % to 17.48 %
on the same 300 committed samples, on a design that had not changed. So the
reduction is spelled out here rather than hidden inside a verb a reader would
have to trust. §5.2's `check-mismatch-charge-derivation.sh` reduces the same
samples to the same statistic by its own arithmetic, because it needs the number
as an *ingredient* of the charge totals rather than as a figure quoted in prose;
the two are deliberately independent routes to one number, and each script's
header names the other so neither can drift quietly.

Two things this grading turned up rather than fixed silently. **`17.48 %` was
quoted in §5 and appeared in neither this table nor the ungraded list below** —
a figure nobody had graded and nobody had declared ungraded, which is exactly
the omission the fourth table exists to make visible, found in the row whose
verdict rests on a derivation. And the §5 row cited the decision record that
*interprets* the campaign without citing the campaign itself, so the
`sim/mc-cp-mismatch` record is added to that row's Source cell here. That
citation also states what the campaign is: a **3-corner subset** of the mandated
45 at n = 100 mismatch samples each, which is why this entry's Record column
names the subset rather than letting a reader assume the grid.

**Three rows were ungraded for a reason that was false, and the reason was
always the same one.** Two rows sat in the exclusion table below — Output band,
closed-loop ("the `output-range` records' `corners/` directories hold per-corner
simulator logs only; no reduced CSV was committed, so the '0 of 45 corners'
verdict cannot be re-derived without re-running the campaign") and Lock time,
closed-loop ("not a reduced per-corner CSV, so the 21/135 and 1/135 row counts
cannot be recomputed from committed evidence") — and two figures of a third,
Multiplication ratio, sat in the ungraded-figure table ("the record commits
`retiming_margin.csv` (17 rows, the margin claim) but not the per-point ratio
table"). **All three were wrong in the same way.** Each of those three records
commits its full per-point table: `sim/output-range`'s 90 closed-loop
band-edge runs with a `Status` per run, `sim/lock-time`'s 270 cold/relock runs
with a `Status` and a `DN guard` per run, and `sim/divider-ratio-chain`'s 235
chain points with the programmed `n_target`, the measured `n_fb` and
`testbench/derive.py`'s own `ratio_pass`. They are committed in the records' own
Markdown rather than in a `.csv` beside them, and **"no CSV" had been read as "no
evidence"** three times without anyone opening a record to look. Two of the
three excuses even said which files the directory *does* hold, so the reading
was never blocked by missing information — only by the assumption that evidence
means a file with a `.csv` on the end.

So the reduction language now accepts a second evidence form,
`<record-id>.md § <first column>` — the pipe table inside a record, named by its
first column. A markdown table can be elided where a CSV cannot, so that form
carries a correspondence rule a CSV does not need: **the table must have exactly
one row per committed per-corner log** — 90 rows against 90 logs, 270 against
270, 235 against 235 — and where the table's first column is the per-corner
point id (`sim/divider-ratio-chain` writes one; the other two head that column
`Corner` and split the corner across three) the row *sets* are compared too, not
merely their sizes. A truncated, summarised or hand-trimmed table fails instead
of reporting a smaller count that reads like an answer; the correspondence is
checked against the raw logs, never against the record's own declared point
count, which is the claim and not the evidence; and the check's OK line says
which tables got the stricter of the two rules, so the weaker one is never
applied silently.

Ten figures across those two formerly-excluded rows are now graded: the closed-
loop band-edge row's `45-point PVT grid`, `90 runs` and its headline
`0 of 45 corners` (`count(rows where Status == PASS)` — a **zero**, of the kind
§5.1 already treats as the most dangerous figure to grade, which is why the row
count and the corner count beside it are graded from the same table rather than
assumed), and the closed-loop lock-time row's `270-run grid`, `45 corners`, both
`135` halves, `21/135`, `1/135` and the `255/270` DN-branch guard. Grading the
numerators while trusting the denominators would have been the same half-job this
section keeps catching, so each `135` is re-derived as its own
`count(rows where Condition == …)`. One caveat that the grading makes visible
rather than fixes: the band-edge row also cites `20260819-190341-70a4128`, which
supersedes exactly one of those 90 rows (`ff`/27 °C/3.30 V `hi`, replacing a
hand-killed `ERROR` with a reproducible CAPPED/stall characterization). That
record commits one row against four logs, so it is not readable under the
correspondence rule above, and its own status — still not a `PASS` — is what
keeps the graded zero true. The zero is therefore re-derived over the 90-run
table and *reasoned* over that one superseding row, which is stated here rather
than left for a reader to notice.

The Multiplication ratio row makes three claims, and each is now graded against
its 235 points.
**Coverage** — `61 distinct N` at 200 MHz — is graded twice deliberately, once
over the *programmed* ratio (`n_target`) and once over the *measured* one
(`n_fb`): the first is what "exercised" means, the second is what the chain
actually produced, and the two agreeing at 61 is the "every integer from 4 to
64, no holes" claim that neither count carries alone. The 200 MHz restriction is
`where corner-id ~= f200` because the per-point table has no input-rate column
of its own; the twelve 10 MHz bottom-of-band points reuse N ∈ {4, 64}, so
dropping the filter would give 61 by accident today and go wrong silently the
first time a bottom-of-band point adds an N the 200 MHz sweep does not have.
**Correctness** — `0 ratio errors` — is `count(rows where ratio_pass != 1)`, the
record's own two-node criterion: the settled retimed-FB period *and* the
un-retimed DIVOUT period both within 0.05 of the programmed N, so a mis-read on
either shows up as a disagreement rather than as a period counted twice. And the
denominator, `235 chain points`, is `count(rows)`, which the one-row-per-log rule
ties to 235 simulations that ran. `check-pvt-coverage-claims.sh` already graded
`235` and its `2835`-cell cross-product against the record's *declaration*;
these are the same numbers against the per-point evidence, which is precisely
what the ungraded list said could not be done.

**Two UNMET verdicts whose own counts nothing graded.** Until this pass the
Supply sensitivity — DC row had two graded figures, `−294` and `2.255e-4`,
both frequency figures from the 45-point grid record — the half of that row
that *passes*. Its verdict, **UNMET on Budget 2, at 9 of 15 cells**, and every
figure the row's three findings rest on came from the re-reading record
`20260925-044237-4ff4f65` (DR-021), which the row cites and which commits all
three of its analyses as per-corner CSVs, and none of them was graded or
declared ungraded: the verdict's own count was the omission this section's
fourth table exists to make visible, sitting in the row it was least safe to
miss. Twenty-nine entries now grade it. (The Reference spur row had the same
hole at a smaller scale: its `−54.5` was graded, but not the `5/5 corners` and
`2/5 corners` its verdict states, nor `−54.9`, the other of the "two coldest
corners" that make that 2. All three reduce `spur_by_corner.csv` —
`spur_dbc <= -55`, `spur_dbc_at_200mhz > -55`, and the `ff`/−40 °C point — so
they are graded beside it.) Its three findings each reduce the
CSV that states them — `criterion1_verdict_classes.csv` (45 rows: the 10
failing corners and their 2 / 8 split, the frequency headroom, and DR-012's
settled grading joined per corner), `criterion1b_vctrl_budget.csv` (15 rows,
one per (bundle, temperature) cell: the `VCTRL` travel, both Budget 2
readings, the window margin) and `criterion3_end_recovery.csv` (the three
step/ramp corners) — and the two point-level window claims reduce the grid
record's own `supply_steady.csv` ripple peaks, not the cell table, because
they are stated over 45 points rather than 15 cells. Four things the grading
needed are stated rather than left in the reductions:

- **A zero stated over a disjunction is graded as one zero per disjunct.**
  "0 of 45 corners missed either frequency check" and "0 of 45 points leave"
  the 0.9–2.7 V window are each an *or*; the where-clause is conjunctive, so
  each is two entries (`fdev` and `ferr` headroom below 1; ripple floor below
  0.9 V and ripple peak above 2.7 V), and two zero counts bound the union at
  zero. The record's "4 of 45 outside" DR-001's 0.9–2.4 V window is then
  `vctrl_max_v > 2.4` alone — exact because the floor-side count beside it is
  the graded zero.
- **The step/ramp figures are pinned to their corner.** `−20.3 mV/µs`,
  `18.75 µs`, `17.2 mV`, `20.0 mV` and the hold `≈8 µs short` are
  `ss`/−40 °C's, filtered as such; unfiltered, the slope reads `−31.7` from
  the `ff` corner. `8 µs short` grades the committed 7.69 µs at the precision
  written, and it is what the row already calls it — an extrapolation at a
  measured rate, the optimistic end of a bracket, not a measurement.
- **`0.60–0.72 ns` of static-phase movement is a magnitude of a signed column**
  (`d_phi_window_ns` is −0.6048 and −0.7216 at the two phase-class corners),
  so it is graded at scale `−1`, which swaps which aggregate gives which end.
  That is safe only because the check compares the *signed* result: a
  positive value in the selection would come out negative, and a larger
  negative one would move the `0.72`, so a sign-flipped scale fails loudly
  rather than reading a mixed-sign column as a magnitude.
- **Where the row states a membership, the membership is graded, not only
  the count.** "The 2 settled violations … are inside the 8" is two entries:
  the grid holds exactly 2 settled violations of the ratified ≤ 1 ns bound,
  and 2 of them are in the lock-flag class. "The 2 were sampled while still
  decaying" is the phase class's count of DR-012 `settled == no` — the whole
  class, not a sample of it.

Four figures of the row were left out of that pass, none of them a reduction
of one column: three ratios and one two-sided magnitude bound. Two of the
three ratios — `1.41×` and `47 %`, the ones whose second ingredient is a
*ratified line* — are graded in the third table below; the other ratio and the
magnitude bound are declared in the fourth.

| §5 row | Quoted value | Record(s) | Evidence file | Reduction | Scale |
|---|---|---|---|---|---|
| Output band | `6.449 MHz` | `20260731-175947-0a12e6c` (63-point grid) | `vco_tuning.csv` | `max(min(fosc_hz) by bundle+temp_c+vdd_v)` | `1e-6` |
| Output band | `247.8 MHz` | `20260731-175947-0a12e6c` (63-point grid) | `vco_tuning.csv` | `min(max(fosc_hz) by bundle+temp_c+vdd_v)` | `1e-6` |
| Output band | `504` | `20260731-175947-0a12e6c` (63-point grid) | `kvco_by_point.csv` | `count(distinct bundle+temp_c+vdd_v+band)` | `1` |
| Output band | `0 non-monotonic curves of 504` | `20260731-175947-0a12e6c` (63-point grid) | `kvco_by_point.csv` | `count(non-monotonic(fosc_hz by vctrl_v) by bundle+temp_c+vdd_v+band)` | `1` |
| Output band | `27 %` | `20260731-175947-0a12e6c` (63-point grid) | `kvco_by_point.csv` | `min(adjacent-overlap(fosc_hz by band) by bundle+temp_c+vdd_v)` | `100` |
| Multiplication ratio | `302.83 ps` | `20260802-100727-082c879` | `retiming_margin.csv` | `min(setup_margin_s)` | `1e12` |
| Multiplication ratio | `235 chain points` | `20260802-100727-082c879` | `20260802-100727-082c879.md § corner-id` | `count(rows)` | `1` |
| Multiplication ratio | `0 ratio errors of 235 chain points` | `20260802-100727-082c879` | `20260802-100727-082c879.md § corner-id` | `count(rows where ratio_pass != 1)` | `1` |
| Multiplication ratio | `61 distinct N` | `20260802-100727-082c879` | `20260802-100727-082c879.md § corner-id` | `count(distinct n_target where corner-id ~= f200)` | `1` |
| Multiplication ratio | `61 distinct N` | `20260802-100727-082c879` | `20260802-100727-082c879.md § corner-id` | `count(distinct n_fb where corner-id ~= f200)` | `1` |
| Period jitter (open-loop sensitivity) | `2.51 %` | `20260804-211600-f599a65` (63-point grid) | `raw_measures.csv` | `max(rip_tj_rms_pct where rdiv == r16)` | `1` |
| Period jitter, closed-loop, deterministic (control-ripple) | `0.0508` | `20260905-192724-a2ba48f`, `20260906-015602-f9bef9d`, `20260906-024225-12bccda`, `20260906-063728-f3c9c23`, `20260906-080511-69b36ef`, `20260906-095050-3a8a6ef` | `period_jitter_by_corner.csv` | `min(tj_rms_pct)` | `1` |
| Period jitter, closed-loop, deterministic (control-ripple) | `0.2691` | `20260905-192724-a2ba48f`, `20260906-015602-f9bef9d`, `20260906-024225-12bccda`, `20260906-063728-f3c9c23`, `20260906-080511-69b36ef`, `20260906-095050-3a8a6ef` | `period_jitter_by_corner.csv` | `max(tj_rms_pct)` | `1` |
| Reference spur | `−57.0` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `max(spur_dbc)` | `1` |
| Reference spur | `−72.7` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `min(spur_dbc)` | `1` |
| Reference spur | `−54.5` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `max(spur_dbc_at_200mhz)` | `1` |
| Reference spur | `17.48 %` | `20260923-095854-1655e11` (3-corner subset) | `mc_cp_dc.csv` | `max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by corner)` | `1` |
| Reference spur | `−54.9` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `max(spur_dbc_at_200mhz where process == ff and temp_c == -40)` | `1` |
| Reference spur | `5/5 corners` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `count(rows where spur_dbc <= -55)` | `1` |
| Reference spur | `2/5 corners` | `20260816-132150-5f405e7` | `spur_by_corner.csv` | `count(rows where spur_dbc_at_200mhz > -55)` | `1` |
| Loop bandwidth | `25.96` | `20260731-202550-82af5a9` | `loop_margins.csv` | `min(fc_min_hz where on-icp-trim-rule)` | `1e-3` |
| Loop bandwidth | `429.5` | `20260731-202550-82af5a9` | `loop_margins.csv` | `max(fc_max_hz where on-icp-trim-rule)` | `1e-3` |
| Phase margin | `47.4°` | `20260731-202550-82af5a9` | `loop_margins.csv` | `min(pm_min_deg where on-icp-trim-rule)` | `1` |
| Phase margin | `105` | `20260731-202550-82af5a9` | `loop_margins.csv` | `count(rows where pass_pm == 1)` | `1` |
| Phase margin | `140` | `20260731-202550-82af5a9` | `loop_margins.csv` | `count(rows)` | `1` |
| Lock time (small-signal settling) | `71 µs` | `20260731-202550-82af5a9` | `loop_margins.csv` | `max(settle_max_s where on-icp-trim-rule)` | `1e6` |
| Lock time (small-signal settling) | `120` | `20260731-202550-82af5a9` | `loop_margins.csv` | `count(rows where pass_lock == 1)` | `1` |
| Power | `318 µA` | `20260731-175947-0a12e6c` (63-point grid) | `vco_tuning.csv` | `max(isupply_a where fosc_hz >= 90e6 and fosc_hz <= 110e6)` | `1e6` |
| Power | `159` | `20260731-175947-0a12e6c` (63-point grid) | `vco_tuning.csv` | `count(rows where fosc_hz >= 90e6 and fosc_hz <= 110e6)` | `1` |
| Power, closed-loop measured | `0.9863` | `20260901-155456-46b92f8` | `supply_steady.csv` | `min(p_tot_w)` | `1e3` |
| Power, closed-loop measured | `1.98` | `20260901-155456-46b92f8` | `supply_steady.csv` | `max(p_tot_w)` | `1e3` |
| Power, closed-loop measured | `45` | `20260901-155456-46b92f8` | `supply_steady.csv` | `count(rows)` | `1` |
| Supply sensitivity — AC (ripple) budget | `2.51 %` | `20260804-211600-f599a65` (63-point grid) | `raw_measures.csv` | `max(rip_tj_rms_pct where rdiv == r16)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `−294` | `20260901-155456-46b92f8` | `supply_steady.csv` | `min(fdev_ppm)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `2.255e-4` | `20260901-155456-46b92f8` | `supply_steady.csv` | `max(ferr)` | `1` |
| Output duty cycle | `44.375` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `min(duty_pct)` | `1` |
| Output duty cycle | `50.696` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `max(duty_pct)` | `1` |
| Output duty cycle | `7` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `count(rows where duty_pct < 45)` | `1` |
| Output duty cycle | `90` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `count(rows)` | `1` |
| Output levels and drive | `1.006` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `min(voh_ratio)` | `1` |
| Output levels and drive | `1.044` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `max(voh_ratio)` | `1` |
| Output levels and drive | `−0.040` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `min(vol_ratio)` | `1` |
| Output levels and drive | `−0.006` | `20260817-100354-0e9cfc9` | `raw_measures.csv` | `max(vol_ratio)` | `1` |
| Lock detector | `1.14` | `20260919-002812-1b12179` (117-point grid) | `window_edges.csv` | `min(asserted_up_to_s where process == fs and temp_c == -40.0 and vdd_v == 3.63)` | `1e9` |
| Lock detector | `1.16` | `20260919-002812-1b12179` (117-point grid) | `window_edges.csv` | `min(did_not_assert_from_s where process == fs and temp_c == -40.0 and vdd_v == 3.63)` | `1e9` |
| Lock detector | `1.78` | `20260919-002812-1b12179` (117-point grid) | `window_edges.csv` | `min(asserted_up_to_s where process == ss and temp_c == 125.0 and vdd_v == 2.97)` | `1e9` |
| Lock detector | `1.80` | `20260919-002812-1b12179` (117-point grid) | `window_edges.csv` | `min(did_not_assert_from_s where process == ss and temp_c == 125.0 and vdd_v == 2.97)` | `1e9` |
| Kvco | `154.3` | `20260731-175947-0a12e6c` (63-point grid) | `kvco_by_point.csv` | `max(kvco_hz_per_v where inside_v1_band == 1)` | `1e-6` |
| Output band, closed-loop | `45-point PVT grid` | `20260819-160843-4e32f91` | `20260819-160843-4e32f91.md § Corner` | `count(distinct Corner+Temp+VDD)` | `1` |
| Output band, closed-loop | `90 runs` | `20260819-160843-4e32f91` | `20260819-160843-4e32f91.md § Corner` | `count(rows)` | `1` |
| Output band, closed-loop | `0 of 45 corners` | `20260819-160843-4e32f91` | `20260819-160843-4e32f91.md § Corner` | `count(rows where Status == PASS)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `270-run grid` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `45 corners` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(distinct Corner+Temp+VDD)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `135` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows where Condition == cold)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `135` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows where Condition == relock)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `21/135` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows where Status == PASS and Condition == cold)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `1/135` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows where Status == PASS and Condition == relock)` | `1` |
| Lock time, closed-loop cold-start / worst-case re-lock | `255/270` | `20260831-052456-effc505` | `20260831-052456-effc505.md § Corner` | `count(rows where DN guard == PASS)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `45-point grid` | `20260901-155456-46b92f8` | `supply_steady.csv` | `count(distinct bundle+temp_c+vdd_v)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0 of 45 corners missed either frequency check` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where fdev_headroom_x < 1)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0 of 45 corners missed either frequency check` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where ferr_headroom_x < 1)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `3.4×` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `min(fdev_headroom_x)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `4.4×` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `min(ferr_headroom_x)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `10 failing corners` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where verdict != PASS)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `2 static-phase` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where failing_check == phi)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `8 lock-flag` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where failing_check == lock)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `2 were sampled while still decaying` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where failing_check == phi and settled_dr012 == no)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0.60` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `max(d_phi_window_ns where failing_check == phi)` | `-1` |
| Supply sensitivity — DC / closed-loop, full grid | `0.72 ns` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `min(d_phi_window_ns where failing_check == phi)` | `-1` |
| Supply sensitivity — DC / closed-loop, full grid | `2 settled violations` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where settled_dr012 == yes and over_ratified_1ns_dr012 == yes)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `2 settled violations` | `20260925-044237-4ff4f65` | `criterion1_verdict_classes.csv` | `count(rows where settled_dr012 == yes and over_ratified_1ns_dr012 == yes and failing_check == lock)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0.385` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `min(span_full_v)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0.846 V` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `max(span_full_v)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `9 of 15` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `count(rows where over_budget2_full_range == yes)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `15 (bundle, temperature) cells` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `count(distinct bundle+temp_c)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0 of 15 cells exceed it` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `count(rows where over_budget2_half_range == yes)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `4 of 45 outside the window` | `20260901-155456-46b92f8` | `supply_steady.csv` | `count(rows where vctrl_max_v > 2.4)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0 of 45 points leave it` | `20260901-155456-46b92f8` | `supply_steady.csv` | `count(rows where vctrl_min_v < 0.9)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `0 of 45 points leave it` | `20260901-155456-46b92f8` | `supply_steady.csv` | `count(rows where vctrl_max_v > 2.7)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `53 mV` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `min(margin_dr003_v)` | `1e3` |
| Supply sensitivity — DC / closed-loop, full grid | `−20.3 mV/µs` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `min(slope_mv_per_us where bundle == ss and temp_c == -40)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `18.75 µs` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(recovery_us where bundle == ss and temp_c == -40)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `8 µs short` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(t_to_close_phase_us where bundle == ss and temp_c == -40)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `17.2 mV` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(overshoot_mv where bundle == ss and temp_c == -40)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `20.0 mV` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(settled_ripple_pp_mv where bundle == ss and temp_c == -40)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `19.5` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(overshoot_mv where bundle == typical)` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `22.5 mV` | `20260925-044237-4ff4f65` | `criterion3_end_recovery.csv` | `max(overshoot_mv where bundle == ff)` | `1` |

**And the rows that have no re-derived value, with the reason.** This second
table is what makes the grading tables' coverage a claim rather than a sample:
every row of §5 is either graded (above, or in the derived-figure table that
follows) or given a reason here, and CI fails if one is in neither — or in
both. A row here is not a row nobody checked — it is a row whose number
is not the kind of thing committed evidence can settle. **Three rows left this
table on 2026-09-26 because their reason was false rather than superseded** —
they said no reduced evidence was committed, and it had been committed all
along (above). The wording of the reason matters accordingly: "no CSV exists"
is not a reason, because a CSV is not the only committed evidence; "no evidence
of this exists" is.

| §5 row | Why no value here is re-derived from committed evidence |
|---|---|
| Reference input | Reports a *budget* and an exclusion, not a measurement: the electrical contract (V_IL/V_IH, edge rate, duty) is unmeasured and the row says so. Its one numeric claim — the `f_ref` span exercised — is a set of stimulus settings, graded by `check-ref-drive-claims.sh` against the decks rather than by reducing an output |
| Integrated RMS jitter | N/A by design (DR-002 Decision 5). There is no number to re-derive and deliberately never will be |
| Period jitter, closed-loop, deterministic, at the 200 MHz band top | **Declared, not measured** — the campaign has no record at all, so it has no committed evidence. This is the row's own stated status, and the absence is the claim |
| Period jitter, closed-loop, random/noise-driven | Zero records, and DR-023 locates why: no periodic-steady-state path exists on the pinned toolchain. Nothing to reduce |
| Phase noise | N/A by design (DR-002 Decision 5) |
| Standby current | Waived — no power-down mode exists in v1, so there is no state to measure |
| Area | Re-derived in CI already, by `layout/lib/check-layout-status-claims.sh`, from `layout/evidence/area-audit/area-audit.md` — the GDS bounding boxes `python3 layout/run_pv.py area` measures. Its evidence is `layout/`, not `sim/`, so it is graded there and deliberately not duplicated here |
| Supply range | States the swept independent axis of every other row (2.97/3.30/3.63 V), which `check-pvt-coverage-claims.sh` grades against the harness's supply points. There is no measured quantity of its own |
| Supply range, 5.0 V analog rail | **UNMET / not attempted.** No 5.0 V-class device exists in this design and nothing was ever simulated above 3.63 V, so there is no evidence of any kind to reduce — the point of the row |

**And the figures that are a measurement divided by a ratified line.** The
first table reduces committed evidence and stops there, so a figure whose
second ingredient is a *spec line* rather than a column fell outside it. Two
did, both in the Supply sensitivity — DC row: **`1.41×`**, the worst measured
`VCTRL` travel over the 0.6 V Budget 2 allows, and **`47 %`**, the same travel
over the 1.8 V width of DR-003 Decision 5's measured control window. Until
2026-09-26 this section declined both, in the ungraded list below, for the
reason "a ratio to a spec line is arithmetic on the line, not a column of the
committed evidence." That is true about the column and wrong about the
conclusion — and §5.2 below had already shown why, for the spur derivation:
**a hand derivation is not ungradeable, because every ingredient it uses is
written down beside it.** Here there are exactly two ingredients. One is a
reduction this section already evaluates. The other is a number in `spec/pll.md`.

So a third table grades them, under the same rules as the first — the record
must resolve and be cited by the §5 row, the evidence must be committed, and
the figure must appear verbatim in the row — plus three the division needs:

- **The constant is read out of the document, never written into the check.**
  `budget2-vctrl-consumption-v` and `dr003-vctrl-window-width-v` resolve by
  reading `spec/pll.md` (and, for the window, the decision record the spec
  cites), for the same reason the Icp trim-code rule and the mandated grid size
  are read rather than asserted: when a line is re-ratified, CI has to fail in
  that same commit instead of grading the figure against the superseded line.
- **Every statement of the line must agree.** Each constant is required to be
  stated at least **twice**, independently, and the check fails if the
  statements differ. Budget 2's 0.6 V is stated in the spec table's Supply
  sensitivity target cell *and* in the heading of the section that derives it;
  the 0.9–2.7 V control window is stated in `spec/pll.md`'s ratified
  assumptions *and* in DR-003 Decision 5, which this proposal's own §5 row
  cites. A document that contradicts itself about a ratified number is a
  failure here rather than a coin toss over whichever statement the check's
  regex reached first. The **width** is then derived from the two ends rather
  than matched against the "1.8 V wide" the spec writes in passing, because the
  ends are what is ratified.
- **The table's own statement of the constant is graded too.** The Constant
  column is the reader's handle on the arithmetic — `0.846 / 0.6` is checkable
  by eye, `0.846 / budget2-vctrl-consumption-v` is not — so it is compared
  against the resolved value and is not an input to the derivation.

| §5 row | Quoted value | Record(s) | Evidence file | Derivation | Constant | Scale |
|---|---|---|---|---|---|---|
| Supply sensitivity — DC / closed-loop, full grid | `1.41×` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `max(span_full_v) / budget2-vctrl-consumption-v` | `0.6 V` | `1` |
| Supply sensitivity — DC / closed-loop, full grid | `47 %` | `20260925-044237-4ff4f65` | `criterion1b_vctrl_budget.csv` | `max(span_full_v) / dr003-vctrl-window-width-v` | `1.8 V` | `100` |

Both numerators are the same `0.846 V` graded in the first table, re-derived
rather than quoted from it, so the three figures cannot drift apart. And one
guard arrived with this table that the first one needed all along: **a range is
not a figure.** The figure parser reads the number at the front of the string,
so a quoted `0.1–0.5 dB` would have been graded as `0.1` and the other end
would never have been looked at — *grading half of a two-sided bound and
calling it the bound*, which is the defect the fourth table below exists to make
visible. A range-shaped figure is now refused outright in both tables, which is
what makes one of the entries below a declaration rather than an oversight.

**And the figures inside graded rows that are still not re-derived.** Coverage
above is per *row*, not per *number*: a row with one re-derived value is not a
fully re-derived row. This fourth table is where the remainder is declared, and
CI grades each entry — the row must exist and must be one of the graded rows,
the reason must be given, the figure may not also appear as a graded value, and
**the figure must still appear verbatim in the §5 row it is declared against**,
so that editing §5 and not this list fails the build.

That last rule exists because this list was prose until 2026-09-26, and prose
does not get graded. It named four figures and silently missed a fifth: the
Output band row's `27 %` worst adjacent-band overlap, which was neither
re-derived nor declared ungraded. It is graded above now — as is the
monotonicity count, which this list previously carried — and so is the
Reference spur row's `≈ −57.0 dBc` charge **total**, now that
`check-mismatch-charge-derivation.sh` (§5.2) reduces it from
`sim/mc-cp-mismatch`'s own committed samples rather than taking it on faith. The
two Multiplication ratio figures this list carried are graded above too, and
they came off it for a different and worse reason than the others: **the reason
they were listed was false**, not merely superseded — the per-point evidence the
entry said the record did not commit had been committed all along, in the
record's own Markdown (see above), exactly as for the two rows that left the
exclusion table in the same pass. A disclosure that cannot rot is still only as
good as the reading behind each line of it, and neither this table nor the
exclusion table above had ever been audited against the records they excuse.
**Two more came off it in the same pass for a reason of the third kind** — not
false, not superseded, but *incomplete*: `1.41×` and `47 %` were declined
because a ratio to a spec line "is arithmetic on the line, not a column of the
committed evidence," which stated a true fact about the evidence and drew the
wrong conclusion from it. They are graded in the third table above now. Their
departure sharpens what the remaining arithmetic-shaped entries have to say:
"arithmetic rather than a column" is no longer a reason by itself, so each now
names the ingredient that is genuinely missing — a second end the figure's own
shape would hide, or a divisor that is another measurement rather than a line.

What remains is five figures in four rows. One was added when grading the
closed-loop lock-time row put a disclosure obligation on it; two when grading
the Supply sensitivity — DC row did; and one when grading the Reference spur
row's two coldest corners did:

| §5 row | Figure | Why it is not re-derived |
|---|---|---|
| Kvco | `115.8 MHz/V` | Two reasons, either sufficient. Selecting the point evaluates [the band-selection rule](../../spec/pll.md#band-selection-rule) (lowest band code that reaches the target) at every corner — a derivation, and one over a rule whose control window `spec/pll.md` does not presently name, an ambiguity tracked at #542 under which the two candidate windows select different bands. And the point itself is at Vctrl = 1.54 V, which the 7-point control sweep does not sample (its neighbours are 114.93 MHz/V at 1.50 V and 120.85 at 1.80 V), so no reduction of this CSV returns it. The adversarial `154.3 MHz/V` figure the rule exists to exclude *is* graded above, which is the half that bounds the risk |
| Lock time, closed-loop cold-start / worst-case re-lock | `{4,16,64}` | A stimulus *set*, not a number: the grammar above re-derives a figure, and this one is the three divide ratios the grid was run at. Its cardinality is pinned from both sides by figures that are graded — the 270 rows, the 45 corners and the two conditions the record's own table carries, which multiply to 45 × 3 × 2 — while the membership is graded against the record's declared sweep axis by `check-pvt-coverage-claims.sh`, as the `f_ref` span is for the Reference input row |
| Reference spur | `0.1–0.5 dB` | **A two-ended range, which is not a figure.** Both ends are a distance over the −55 dBc line — `−54.9` and `−54.5`, both graded above, against a `spec/pll.md` constant — so the arithmetic is no obstacle now that the third table grades a reduction against a ratified line. What stops it is the shape: the figure parser reads the number at the front, so grading this string would grade `0.1` and never look at `0.5`. That is refused outright rather than accepted quietly, which is why this stays a declaration; closing it means §5 writing the two ends as two figures |
| Supply sensitivity — DC / closed-loop, full grid | `5.7 mV` | A *magnitude* bound — `predicted_minus_measured_v` in `criterion1b_vctrl_budget.csv` is signed and spans −0.6 … +5.7 mV over the 15 cells, and the grammar has no magnitude aggregate. `max()` would return 5.7 here only because the positive side happens to be the larger one; grading half of a two-sided bound and calling it the bound is the defect this table exists to catch, so it is declared instead |
| Supply sensitivity — DC / closed-loop, full grid | `33 %` | `1 − rms_linear_mv / rms_exponential_mv` at `ss`/−40 °C (20.54 against 30.75 mV in `criterion3_end_recovery.csv`). **Both** operands are columns of the committed evidence, which is what the third table's form does not reach: it divides one reduction by one *written-down* constant, and there is no ratified line here to read — the divisor is another measurement. Neither operand is quoted in §5 either, so grading it would have to introduce both |

Nothing mechanically enumerates "every headline figure" out of §5's prose
cells, which quote hundreds of numbers, most of them commentary on a figure
rather than a figure. So this list's *completeness* is still a reviewer's
judgement; what CI now guarantees is that it cannot rot, and that what it
declares ungraded is genuinely not graded elsewhere in this section.

**One disclosure this check produced on its first run.** Grading the open-loop
period-jitter row's `2.51 % RMS` showed that the figure is the worst case over
the ripple-frequency axis **held at f_osc/16** — the setting the full 63-point
grid runs at, hence the `where rdiv == r16` filter above. The same record also
carries a deliberate 6-point ripple-frequency sub-sweep at 27 °C / 3.30 V /
band 5, and at f_osc/4 that sub-sweep reaches **3.24 % RMS**, 29 % worse than
the gridded worst case; the record states plainly that ripple jitter "at a
ripple frequency that matters must be **measured**, not extrapolated," because
its quasi-static model under-predicts by 1.2–2.3×. So the binding ripple
frequency is not the one the PVT grid was swept at, and it has not been
measured at the binding PVT corner. Scaled to the 20 mV pp budget the way the
row's own derivation scales, 3.24 % becomes **0.65 % RMS** rather than 0.50 % —
still inside the 1.0 % line, so no verdict here changes, but the margin is
1.5× rather than 2×. Tracked as an owed measurement, not folded silently into
the existing number.

### 5.2 Derivation provenance: the derived spur figures CI re-derives arithmetically and to their own raw samples

§5.1 grades a **measured** value by reducing a committed per-corner CSV. One
row above does not rest on a measured value at all: **Reference spur**. Its
closed-loop campaign measures 5 of the 45 PVT points, every one of them at
150 MHz and with device mismatch off, so what this document tells you about the
binding 200 MHz point — **1.6 dB inside the line**, rather than the ~6 dB the
older −61 dBc figure implied — is a hand derivation: a per-event charge total
carried through C2, a recorded TIE scale point, the narrowband-FM relation
`θ = 2π·f_out·TIE`, and a `20·log₁₀(θ/2)` at the end. Five derived figures, in
two tables of `spec/pll.md`, quoted here in a third document. §5.1's own
ungraded list declined that figure because it is "not a reduction of one CSV",
which was true and incomplete: **a hand derivation is not ungradeable, because
every ingredient it uses is written down beside it.**

`spec/lib/check-spur-derivation-arithmetic.sh` re-derives it, and fails this
repository's CI if the derivation stops reproducing its own figures. It reads
the two relations out of `spec/pll.md` rather than asserting them — as
`check-quoted-value-provenance.sh` reads the Icp trim-code rule and
`check-pvt-coverage-claims.sh` computes the mandated grid size from the harness
— so a re-ratified derivation fails the check in the same commit instead of
being graded against the superseded chain. Six rules: the stated relations must
be the ones it implements; the worst-case sum must be the linear add it calls
itself; the step table's chain must follow row by row from its own displayed
figures, with the unrounded end-to-end chain agreeing within 0.1 dB so that
rounding cannot stand in for arithmetic; every charge-accounting row must
reproduce its spur from its own total ΔQ; the measured table's scaled column
must add the `20·log₁₀(200/150)` = +2.50 dB constant its own header names (the
arithmetic on which two cold corners are UNMET at 200 MHz, written out by hand
five times); and **every absolute dBc figure anywhere in this proposal must be
one the specification contains** — measured, scaled, derived, or the ratified
`≤ −55 dBc` line itself, either at the precision `spec/pll.md` writes it or at
the finer precision its own arithmetic produces (which is how the −56.95 dBc
disclosure below is allowed to be stated at all).

| Derived figure | Total ΔQ | What that total prices |
|---|---|---|
| `−66.6 dBc` | 3.68 fC | Systematic asymmetry alone — the row DR-024 says a mismatch-off measurement is comparable with |
| `−61 dBc` | 6.67 fC | The original derivation: systematic plus the nominal-only statistical residual |
| `−59.9 dBc` | 7.93 fC | Statistical residual refreshed to the corner-combined campaign, term 1 still excluded |
| `≈ −57.0 dBc` | 11.19 fC | …plus term 1 (UP/DN current mismatch) at its measured 3σ |
| `−56.6 dBc` | 11.66 fC | …plus term 1 at its ±20 % budget — the figure this row's 1.6 dB margin is stated from |

**One disclosure this produced.** `≈ −57.0 dBc` is −56.95 dBc carried through
unrounded, which rounds to −56.9 at the precision it is written to. The `≈` is
load-bearing, and the check grants a figure carrying that marker one unit of
its last written place — the only place in it that accepts a figure not
matching at the precision written. The figure is not wrong (the stack it ends
is a deliberately conservative upper bound, and the difference is 0.05 dB), and
it is not quietly re-rounded here: `spec/pll.md` is the ratified specification,
amended through a decision record rather than by an agent rounding it
differently.

**Where the charge totals themselves come from, now graded too.** The 7.93 /
11.19 / 11.66 fC totals add a corner-combined statistical residual and a
term-1 product that DR-018 derives in prose from `sim/mc-cp-mismatch`'s 300
committed samples. `spec/lib/check-mismatch-charge-derivation.sh` gives that
derivation its own machine reduction: for every (corner, seed) triple of
Vctrl points in the committed `mc_cp_dc.csv`, it selects the worst-magnitude
reading (the `cp-compliance` "worst point in window" convention), forms the
signed and folded `|mean| + 3*sd` per corner, and keeps the worst corner of
each — the same reduction `sim/mc-cp-mismatch/testbench/run.sh --restat`
implements, independently re-derived rather than trusted. It does the same
for term 3's residual net charge from `mc_pfd_cp.csv`, then chains both
through the Icp and `T_ov` figures DR-018's own Input table states (taken as
given, not re-swept from `cp-compliance`/`pfd-deadzone`'s own 45-corner
grids — the same boundary `check-spur-derivation-arithmetic.sh` draws around
C2 and the TIE scale point) into the three charge totals above, and fails CI
if any of them no longer reproduces.

**That same term-1 statistic is graded a second, independent way in §5.1**, and
that is deliberate rather than duplicated by accident. §5.1's provenance table
reduces the same committed `mc_cp_dc.csv` to the same `17.48 %` through the
reduction language — `max(sig3(worst-magnitude(mism_pct by vctrl_v) by seed) by
corner)`, which is what that language grew a `sig3` aggregate and a
`worst-magnitude` group verb for — rather than through the arithmetic this §5.2
check hard-codes. The two answer different questions: this one asks whether the
*charge totals* still follow from their samples, §5.1's asks whether the
**percentage quoted in §5's own prose** is a reduction of committed evidence at
all, which is the "quoted in §5, graded in neither accounting table" defect the
provenance section exists to catch. Because they reduce the same samples to the
same number by two routes, a change to either one that moves the statistic makes
CI disagree with itself rather than drift quietly, and each script's header names
the other so the pairing is discoverable from either end.

What is still not re-derived, stated so the narrower gap is visible rather than
implied: `Icp`, `T_ov` and the 3.68 fC systematic charge asymmetry are
worst-of-45-corners figures taken from DR-018's Input table, not independently
re-swept from `sim/cp-compliance`'s and `sim/pfd-deadzone`'s own 45-corner grids
here. That remainder is owed at **#573 (open)** — no new simulation with it,
only a reduction of campaigns already committed. Nor does either check grade the
dB *margins* stated in prose ("1.6 dB inside the line", "~12 dB at the two cold
corners"), because a bare "dB" in this document is as often a spread or a
reserve as it is a difference of two graded numbers.

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
  `layout/floorplan/PLL-FLOORPLAN.md` §5.1–§5.15,
  `spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md`, and
  `spec/decision-records/DR-017-area-row-held-at-0.30-on-the-refreshed-measured-floor.md`,
  which holds the row there).
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

Top-level assembly is tracked at issue #297, formal DRC/LVS reporting at
#149, and post-layout re-verification at #18. Earlier revisions of this
sentence named **#17** for top-level assembly; that was wrong twice over —
#17 is the *floorplan* issue (the block-placement skeleton described in the
bullet above, which it delivered), and it closed on 2026-09-08. This
proposal claims exactly the DRC/LVS closure the table above records, and no
more.

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
   the ratified band that binds. The random/noise-driven component is
   tracked at issue #520 and the 200 MHz band-top campaign at #503.
   **DR-020 recorded the disposition of the first, and DR-023 narrows its
   reason without reversing it.** DR-020 found the random component not
   obtainable from any analysis this project's toolchain offers — no device
   noise in a transient analysis, a small-signal `.noise` analysis that needs
   a DC operating point a free-running oscillator does not have, and a
   `trnoise()` source whose amplitude the deck author chooses — and deferred
   it to silicon or to a noise-referral pipeline this project has not built.
   DR-023 re-measured those claims as committed, re-runnable probes
   (`sim/period-jitter/noise-toolchain-probe/`, where DR-020 had run
   inline, uncommitted ones) and located the gap more precisely: `.noise`
   **does** report per-device channel-thermal and flicker PSDs for the
   gf180mcu models at a bias point, so the device noise data is not what is
   missing. What is missing is a periodic-steady-state / `pnoise` path (`pss`
   is not a command in this build) to weight those PSDs over the ring's
   switching trajectory, across which they move by 46.6 dB (thermal) and
   95.9 dB (flicker). An earlier revision of this item credited DR-023 with
   DR-020's broader wording, which DR-023 exists to narrow. Neither record
   relaxes the ≤ 1.0 % RMS target, and DR-023 Decision 3 states what that
   leaves: the target's own supply-ripple derivation already allocates
   **0.50 % RMS** to this component, so the line is met in simulation for its
   deterministic half only and **the other half is an unverified budget**,
   not a demonstrated margin. **DR-030 then tests the falsification condition
   DR-023 had the discipline to state.** DR-023 Decision 2 said its finding
   would be overturned "if `pss` resolves, or if an ISF pipeline demonstrates
   convergence". `pss` still does not resolve; an ISF *extraction* now does
   converge — `sim/period-jitter/isf-bringup/` retires the load-bearing risk
   #520 named, Γ's accuracy at the switching edge, at ≤ 0.02 % over the last
   halving of the internal-timestep ceiling (2 ps → 1 ps, the setting it runs
   at; *not* every halving — 8 ps → 4 ps still moves `h` by up to 2.32 %) — but
   a converging ingredient is not a
   converging pipeline, and the two ingredients that are missing are the ones
   that would do the cyclostationary weighting. **DR-031 then builds those two,
   and measures the bound the cheaper alternative route was refused for want
   of.** `sim/period-jitter/sid-trajectory/` tabulates each ring device's
   channel-thermal and flicker generator at the bias it actually occupies at 24
   phases of the oscillation, plus the trajectory it is evaluated along, at three
   PVT points — sampled out of the ISF bring-up's own reference deck, so the two
   ingredients share one phase axis by construction rather than by coincidence.
   Its bound is stated against the average the integral actually contains, not
   the one that is easy to quote: against the `h²`-weighted `S_eff = Σh²S/Σh²`,
   biasing each device at its own peak-\|I_d\| phase reproduces the
   channel-thermal generator to **−1.15 … +1.06 dB** (0.88–1.13× in jitter RMS)
   for all four device classes, where the raw cyclostationary span is 67–115 dB
   and bounds nothing. **The row still stays UNMET, and DR-031 says why in its
   own words**: the assembly is not built; the bound holds at 1 of 45 corners
   while the unweighted spans move 40 dB across three; the weighted average rests
   on an effective 2.4 of 12 sampled phases for the two device classes whose ISF
   weight is exactly available; and the flicker half is not a defined quantity
   until `spec/pll.md`'s Period jitter row states an observation interval, which
   that row's Verification-owed table now records as owed. So DR-023's clause is
   narrowed rather than fired, this row stays **UNMET**, and the unverified half
   of the jitter budget stays unverified. Until
   2026-09-25 this item handed both to **#13**, which closed on 2026-09-08,
   so for seventeen days it named a closed issue as the owner of the only
   row this document cannot report a number for. It then named **#505**,
   which was the bookkeeping issue for that ownership gap and closed
   `completed` the same day DR-020 landed naming #505 itself as owner — a
   stale reference from the moment it merged. DR-023, numbered after DR-020
   because DR-020 merged first against the same row, re-points the
   measurement at #520. A defect in the
   campaign's own lock gate, which reported FAIL at two demonstrably-locked
   corners, was tracked separately at issue #273 and never affected any
   jitter number reported here; **#273 is closed** — the gate is wrap-safe
   and those two points re-measure PASS in
   `sim/period-jitter/records/20260906-095050-3a8a6ef.md` (§5). The
   output-band axis is a declared
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
   `supply-sensitivity`'s findings have been (its record named #9/#10/#11 for
   each class of finding, all three of which later closed; DR-021 re-derived
   each finding against the ratified line and re-pointed it at an open owner —
   item 4 below); closing that gap is separate follow-on work, not covered by
   this proposal.
4. **`supply-sensitivity`'s three FAILing criteria now each have a named open
   owner, and two of the three are not the findings the record's headings say
   they are** (§5, and DR-021). The record routed each class of finding by name
   to #9 (`pfd_cp`, post-#24), #10 (`loop-dynamics`) and #11
   (`lock_detector`); all three of those issues closed, so for 24 days the
   findings were recorded with nobody holding them, and this item said instead
   that they "are already routed to their owning issues" — true when written,
   false by the time anyone read it. Re-read against the ratified spec lines
   rather than the deck's proxies for them, on arithmetic over the same
   committed grid:
   - the **frequency-vs-supply** FAIL contains **no frequency content at all**
     (0 of 45 corners missed either frequency check, with 3.4× and 4.4×
     headroom); it is the static-phase finding DR-012 already owns, narrowed
     by DR-025 — which discharged and closed **#511** without running either
     cell it named — and now read at two nodes, **#540** and **#399**, plus
     **#437**;
   - the **`VCTRL`-window** FAIL is graded against a control window DR-003
     Decision 5 superseded, and does not reproduce against the current one
     (0 of 45 points leave it, by 53 mV at the tightest) — but the budget the
     specification actually ratifies, never graded before, is **missed at 9 of
     15 cells** (worst 1.41×). Which rail excursion that budget governs is
     inconsistent inside `spec/pll.md` itself by a factor of two, and is
     **#525**;
   - the **step+ramp** FAIL is a hold ≈8 µs short of a measurably
     *slew-limited* recovery, not the under-damped loop the escalation's own
     exponential-assuming discriminant labelled it — **#405**, whose scope
     already names that classification as something its measured decay law must
     test.

   No recorded verdict or value changes, and `sim/` is append-only, so the
   record's own routing text stands as the history it is. What changed is what
   the findings are understood to be evidence of, and that nobody has to
   reconstruct it from the record again.
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
   schematic-level. Tracked at issues #297 (top-level assembly), #149
   (formal DRC/LVS reporting) and #18 (post-layout re-verification) — #297
   in place of the **#17** earlier revisions named here, which is the
   floorplan issue and closed on 2026-09-08 having delivered exactly the
   placement skeleton §6 describes.
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
   an overhead up to ×1.372 at DR-016's sum and ×1.664 at today's. A lower
   row is still the goal, but **what earns one has changed**. DR-016 made
   each material lever landing grounds for a successor record amending the row
   back down; that trigger fired three times in two days, and DR-017 (issue
   #476, `spec/decision-records/DR-017-area-row-held-at-0.30-on-the-refreshed-measured-floor.md`)
   answered all three with a **hold** and replaced it. The row now comes down
   when the uncertainty its margin is sized to shrinks — an assembled
   `pll_top` GDS measures the top-level overhead (gap 7), or the loop filter
   is drawn and its 20.5 % of the block sum stops being a calculation — and a
   further block-level lever, such as the still-unnamed one against
   `lock_detector`'s 65.5 % whitespace, earns a refresh of the spec's measured
   table rather than a new row (PLL-FLOORPLAN.md §5.15). Earlier revisions of
   this item said the three landings below were grounds the row "has not yet
   followed"; under the specification as it now stands, the row not following
   them is the decision, not a lapse. #469, the first, is spent at 259 µm²
   (0.1 % of the sum; 0.2733 → 0.2730 mm², PLL-FLOORPLAN.md §5.12);
   #473, the third, is the *placement* half of that same band — the glue
   inverters interleaved with the switch groups they drive, 13 → 10 tracks,
   776 µm² (0.4 %, 0.2264 → 0.2254 mm², PLL-FLOORPLAN.md §5.14). #458, the
   second, does move the total
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
10. **The reference input's electrical contract is unmeasured, and every
    jitter and spur number here assumes an ideal reference** (§5). The
    1–25 MHz frequency range is exercised as an operating condition of other
    campaigns, but the input levels, the ≤ 5 ns edge-rate budget and the
    30–70 % duty range are conditions no simulation has varied — every
    testbench drives `REF` with the same ideal full-rail pulse, 200 ps
    edges, nominal 50 % duty. A system integrating this block must budget its own reference
    phase noise against the loop's 20·log₁₀(N) multiplication (12 dB at
    N = 4, 36 dB at N = 64); this proposal does not do that for it.
    `spec/pll.md` named issue #12 as this row's owed verification, but #12
    is closed and is about closed-loop lock acquisition, so the work was
    newly filed as **#499**; **DR-019** has since re-pointed the
    specification's own row at it, and recorded the reference-jitter half as
    **unowned** rather than re-pointing it at #13, which is itself closed. The campaign that
    would discharge the three electrical lines now exists as a committed,
    self-checking manifest and deck — `sim/reference-input-contract` — and
    **carries no measured point**, so this gap is unchanged in substance and
    changed only in ownership.
11. **The lock-detector window trim-code rule is normative and, on this die,
    executable only in simulation** (§4 step 4; **DR-022**, closing #501).
    `spec/pll.md`'s rule is not optional — "a part left untrimmed is outside
    this specification" — yet its measurand is `t_win`, the `ERR → ERRD` delay
    of an internal cell, and neither node is a pad in §2.2's list. This item
    used to read "no *stated* route"; DR-022 replaces the absence of a
    statement with a measurement, and the measurement is negative:

    - **How accurate a substitute would have to be, derived** from the trim
      campaign's own margins: never more than 2 codes low or 3 high to hold
      the ratified [1, 2] ns band, and — the binding tier — **zero** code
      error to preserve DR-013 Decision 4's ≤ 1.65 × spread, because the
      rule's own rounding has already spent all but 2.48 % of that allowance.
    - **What the pads deliver, measured** over the full 13-bundle, 117-point
      grid (`sim/lock-window-proxy/records/20260925-050022-6d57802.md`): the free-running
      ring frequency at `CLK` is *worse than not trimming at all*, and the
      best candidate — the `CLK`→`DIVOUT` pad-to-pad skew — holds the band but
      misses the spread target at 1.697 × with a worst code error of +4.

    So the honest statement is that a part from this die is **characterized at
    a recorded trim code**, not trimmed to rule, and §5's Lock detector row's
    T1′/T2′ verdict is conditional on a trim no procedure available at these
    pads can perform. DR-022 named two routes that could still close it and
    authorized neither; **one of them has since been measured and does not
    work.** DR-029 (#527, closed) characterized the symmetric `REF`
    phase-step bisection read at `LOCK` — the route needing no design change
    — and found that the threshold in Δ is not the flag window: **+55.5 %**
    at the rule's own reference condition, **−12.6 codes** of selection error
    on a 16-code trim, failing both of DR-022's accuracy tiers by a margin no
    finer ladder reaches. The obstacle is structural rather than one of
    resolution: the flag's measurand is a *sustained* phase error, and a loop
    driven only at `REF` can be given nothing but transients. **The successor
    is DR-022's second route** — exposing `ERR`/`ERRD` through matched
    observation buffers onto two of the 9 free digital-test-output slots —
    which is a design change needing its own decision record, and which
    nothing in this repository presently owns. The precondition both routes
    shared is discharged: **DR-026** connects `LDT3` at `pll_top` (**#515**),
    so all 16 codes, including the rule's own code 11, are reachable on the
    assembled part.

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
