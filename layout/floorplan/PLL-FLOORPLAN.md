# PLL floorplan record — VCO isolation, supply routing, loop-filter placement, matching-critical cells

Issue #17. Floorplan / critical-layout plan for the PLL, gated behind #16's
DRC/LVS flow bring-up (closed, PR #59) and #1's spec ratification (closed
2026-09-08). This is a **floorplan-level planning record**, not a
transistor-level layout signoff: `design/` currently holds leaf-cell and
block schematics for the five blocks (`vco`, `pfd_cp`, `loop_filter`,
`divider_chain`, `lock_detector`) but **no top-level physical layout view of
any of them yet** (see "Affected Files" on #17 and #9's schematic-export
note) — that per-block physical layout is downstream work this record stages
for, not something a single floorplan issue can honestly claim to deliver
whole. What this record *does* deliver, each checked against real evidence
rather than a placeholder: the isolation/substrate strategy, the supply
routing plan, the loop-filter cap placement (the one block whose physical
geometry is fully pinned by DR-006 today), the matching-critical cell list,
and a first area budget — plus a block-placement GDS skeleton that exercises
#16's DRC flow end to end (see "GDS skeleton" below).

## 1. VCO isolation (guard rings, substrate/well strategy)

**The risk this sizes against, quantified.** DR-003 Decision/Consequences:
VCO supply pushing is **−24 to −51 %/V** across the full PVT grid
(`sim/vco-tuning-range/records/20260731-100401-07f4b7b.md`), of which
**−30.3 %/V is a structural `f ∝ 1/V_swing` term of any current-starved ring
on an unregulated rail** — not a layout defect to be designed away, a floor
to isolate against. DR-003 states plainly: "a 100 mV peak-to-peak ripple
produces up to 2.5 % RMS period jitter open-loop", against a draft spec line
of < 1 %. The closed-loop supply-sensitivity re-run
(`sim/supply-sensitivity/records/20260901-155456-46b92f8.md`, the full
corrected 45-corner grid, superseding the earlier 9-point/qualified data —
see §2 below) confirms the loop absorbs this by moving `Vctrl`
**0.58–1.28 V/V** (mean 0.91) against the rail — i.e. most of the pushing
DR-003 measured open-loop shows up as control-node travel in closed loop,
which is exactly the mechanism the isolation budget below has to keep off
`VDD_VCO`/`GND_VCO`.

**Devices.** All blocks are `nfet_03v3`/`pfet_03v3` (3.3 V thick-oxide only,
DR-002 Decision 3) — gf180mcuD does not offer a deep-n-well / triple-well
isolated flavour of this device at this voltage class, so the isolation
strategy here is standard guard-ring + substrate/well tap discipline, not a
device-level isolation option. This is the same primitive #16's DRC/LVS
bring-up already proved end to end: `DF.13_MV` / `DF.14_MV` (NCOMP-in-nwell /
PCOMP-outside-nwell too far from a well/substrate tap, 15 µm cap) are real,
DRC-checked rules in this deck (`layout/evidence/inv-tb-proof/PROOF.md`'s
"tap-necessity control" reproduces both against a bare standard cell) — the
floorplan below is sized to that same 15 µm tap-pitch constraint, not a new
one invented for this record.

**Strategy:**

- **A dedicated guard ring around the whole VCO block** (ring + bias
  generator + band-select mirror + output buffer), tied to `GND_VCO` on the
  substrate side and to a local `VDD_VCO`-tied n-well tap ring on the p-well
  side — not merged into the PFD/CP or divider guard structure. `GND_VCO` is
  its own pin (see §2 — the VCO is the only block with a private ground, not
  just a private supply), so this is a real two-sided ring, not a
  substrate-only one.
- **Tap pitch ≤ 15 µm everywhere inside the VCO block**, matching the
  `DF.13_MV`/`DF.14_MV` rule #16 already exercises live — every ring stage,
  every band-mirror leg and the bias generator's degeneration resistors sit
  within one tap pitch of a ring tap, not just the block perimeter. The
  5-stage ring (`vco_stage.sch`, `vco.sch`) is the layout-critical path here:
  DR-003 Decision 2 fixed the stage count at 5 with **no fallback to 3 or
  7**, so the "28 % ceiling / 34 % floor" margin DR-003 reports **is the
  whole budget for layout parasitics** — an under-tapped ring that trips
  DRC or adds asymmetric parasitic loading to one stage eats directly into
  that number, not into slack DR-003 already spent.
- **The band-select mirror is common-centroid, not row-placed.** DR-003's own
  text: cascading (rather than paralleling weighted legs) "keeps the largest
  device ratio in any single mirror to 6.4:1 instead of 41:1, which matters
  for matching and for area" (`design/README.md`'s band-map section repeats
  this verbatim) — that headroom is only real if the mirror legs are laid
  out to exploit it. The three cascades (A: pfet 26.5 µm / 17.225 µm; B:
  nfet 5 µm / 8.6125 µm; C: pfet 12.3 µm / 78.87 µm) are each a
  common-centroid pair (always-on leg interdigitated with its switched leg),
  not three separate blobs — a mismatch between an always-on and a switched
  leg shows up directly as adjacent-band-step error, which DR-003 measured
  at a tight 27–36 % overlap band with "no coverage hole" only under the
  schematic-level (mismatch-off) assumption DR-003 states explicitly in its
  own "Everything here is schematic-level" caveat.
- **The output buffer's 3-stage taper (1.25/0.5 → 3.75/1.5 → 11.25/4.5 µm)
  sits at the VCO-block boundary, closest to the `CLK` pin**, so the largest,
  fastest-switching stage (which sinks the most crowbar/switching current) is
  physically nearest the pin it drives and farthest from the ring's own
  starved internal nodes — `design/README.md`'s own note on why the first
  stage is deliberately small (a large first inverter would "inject that
  current back into the VCO rail") is a layout-relevant statement, not just
  a sizing one: keep that current loop short and away from the ring.
- **The 22 pF on-chip decap (2× `cap_nmos_03v3` 50×50 µm) is drawn in the
  schematic already** (`vco.sch`) — the floorplan places it directly adjacent
  to the `VDD_VCO` pin/ring-tap junction, inside the VCO guard ring, so the
  decap's own return path is short. This is real, committed device area
  (5,000 µm² = 0.005 mm²), not a placeholder — see §4.

## 2. Supply routing (`VDD_VCO`/`GND_VCO` vs. digital, decap placement)

**Four separate supply domains, confirmed from the wiring facts in
`design/README.md`'s top-level section**, per DR-001 Decisions 2 and 3:
`VDD` (reference / PFD / charge pump / lock detector), `VDD_VCO` **+
`GND_VCO`** (the VCO's own domain — note it is the *only* block with a
private ground pin, not just a private supply), `VDD_DIV` (divider), and the
shared `VSS` for everything except the VCO. The floorplan routes these as
four physically separate trunks from the pad ring inward, star-connected at
the pads, never sharing a segment — the point of DR-001's domain split is
defeated if two domains share routing before they reach their blocks.

**Sized against the real closed-loop evidence, not the open-loop number
alone.** #14's closed-loop supply-sensitivity campaign has been fully
re-run at the corrected 100 ps internal-timestep bound since this issue was
last curated — `sim/supply-sensitivity/records/20260901-155456-46b92f8.md`
is the **full, unqualified 45-corner grid** (5 process bundles × 3 temps × 3
supplies), landed via #58 (closed 2026-08-31) and PR #256/#258, which
supersedes the earlier 9-point record and its 5-of-9-rows-qualified
reexamination (`sim/supply-sensitivity/records/20260801-*.md`) that #17 was
blocked citing only-4-of-9-rows-usable data from as of the 2026-08-21
curator pass. Use the newer record:

- **Control-voltage slope `dVctrl/dVdd` across the ±10 % rail: 0.5833 –
  1.282 V/V (mean 0.9107)**, most sensitive at `ss`/−40 °C, least at
  `ff`/27 °C — this is the number the decap/routing plan below sizes
  against, not DR-003's open-loop pushing directly (the two are
  cross-checked against each other in the record: `dVctrl/dVdd ≈
  −(df/dVdd)/Kvco`, and the measured range sits inside the envelope that
  cross-check predicts).
- **Settled control voltage over the whole grid: 0.983 – 2.642 V** (average),
  with **4 of 45 corners' *ripple peaks*** (not averages —
  `vctrl_min_v`/`vctrl_max_v`) outside DR-001 Decision 2's usable 0.9–2.4 V
  window (`fs`/27 °C/3.63 V, `sf`/27 °C/3.63 V, `ss`/−40 °C/3.63 V,
  `typical`/27 °C/3.63 V) — headroom is already tight at the supply rail
  extremes on the schematic-level design alone, before any layout-added IR
  drop or coupling is counted. **This is the load-bearing number for supply
  routing**: any resistive drop or switching-induced ripple this floorplan's
  routing adds to `VDD`/`VDD_VCO` directly consumes headroom that is already
  partially spent at 4 of 45 corners.
- **Supply step/ramp disturbance (criterion 3 of the same record) is the
  block's most literal "how much does a supply glitch cost the loop"
  number**: a 100 mV/100 ns step (`3.30 → 3.63 V`) produces up to **44.75 ns**
  peak `REF→FB` phase excursion (`ss`/−40 °C); a slower 103.1 mV/µs ramp
  produces up to **38.4 ns** (`typical`/27 °C). One of three step/ramp
  corners (`ss`/−40 °C) failed the record's own stays-locked criterion at its
  best-resolved re-run — flagged in that record as a genuine, not an
  artefact, design-margin finding, and routed to `sim/loop-dynamics` (#10)
  there. **This floorplan does not fix that finding** (it is a loop-dynamics
  question, not a layout one) but treats it as the reason the VCO/digital
  trunk separation above is non-negotiable rather than a nice-to-have: a
  digital-switching-induced supply transient riding on top of an
  already-marginal corner is exactly the failure mode #10's finding
  describes.
- **Per-domain power** (nominal corner, `typical`/27 °C/3.30 V, same record
  §4): core (PFD+CP+lock detector) 0.342 mW, VCO 0.719 mW, divider 0.408 mW,
  total 1.469 mW — well inside the < 5.0 mW draft target (0 of 45 corners
  over budget, worst case 1.98 mW at `ff`/125 °C/3.63 V). The VCO domain
  draws the most power and is the most dynamic-current-dominated
  (0.552 mW of 0.719 mW is frequency-proportional, a 77 % dynamic share) —
  consistent with routing the VCO trunk with the most decap and the
  shortest, most direct pad-to-block run of the four domains.

**Decap placement:**

- **VCO decap (22 pF, real committed devices, §1) sits at the `VDD_VCO`
  entry point inside the VCO guard ring** — already covered above.
- **`VDD`/`VDD_DIV` decap is not yet committed in any schematic** (unlike the
  VCO, `pfd_cp.sch` and `divider_chain.sch` carry no on-chip decap device
  today) — flagged as an open item for the block-level physical design pass,
  not assumed away here. The floorplan reserves routing channel width along
  both trunks for MOS or MIM decap insertion once that need is sized (the
  digital domain's 100 %/77 % dynamic-current shares on `VDD_DIV`/`VDD_VCO`
  above suggest at least the divider trunk will want some).

## 3. Loop-filter cap placement

**Fully pinned by DR-006 — the one block in this floorplan with real,
as-drawn device geometry, not an estimate.** `design/loop_filter.sch`:

| Element | Device | Drawn size | Footprint |
|---|---|---|---|
| R | 4× `ppolyf_u` in series | 2 µm × 107 µm each | ≈856 µm² (drawn resistor body) |
| C1 | 4× `cap_nmos_03v3_b` | 87 × 87 µm each | 30,276 µm² (≈0.0303 mm²) |
| C2 | 1× `cap_mim_2f0_m2m3_noshield` | 31.4 × 31.4 µm | ≈986 µm² |

**C1 is the area-dominant element of the whole block, confirmed**: 30,276 µm²
against the < 0.15 mm² (150,000 µm²) budget is **≈20.2 %** of the entire
floorplan's area on this one device group alone — **≈10.1 % of the amended
≤ 0.30 mm² row** (DR-016, #456; see §5.11), the *ratio* being the point either
way — DR-006 and #10's own
acceptance criteria already flag this; this record's job is to place it, not
re-derive it. Placement:

- **The four C1 devices are placed as a 2×2 or 1×4 array immediately
  adjacent to the charge-pump output / `VCTRL` node**, minimizing the routed
  length of the highest-impedance node in the loop (DR-001's own stated
  reason switches/parasitics on this node are a spur mechanism). C1's gate
  sits on the filter node, bulk on `VSS` (DR-006) — the array's bulk taps tie
  directly into the shared `VSS` ring, not routed through the VCO or divider
  domains.
- **C2 (MIM, `VCTRL`-referenced) sits directly on the control node between
  the C1 array and the VCO's `VCTRL` pin** — DR-006's own reasoning ("a
  voltage-dependent cap would modulate the ripple pole itself" is why MIM was
  chosen over a MOS cap here) is a placement argument too: C2 should not
  route through or near any switching node on its way to `VCTRL`.
- **R (the 4-series-`ppolyf_u` zero-setting resistor) sits between the charge
  pump output and the C1/`NZ` node**, in the same array footprint — DR-006
  states the four-way series split is "only for layout convenience;
  electrically it is one resistor", so the floorplan is free to fold it
  around the C1 array rather than route it as a long straight run.
- **The whole loop-filter cluster (R + C1 + C2) is placed at the PFD/CP↔VCO
  boundary**, not inside either block's own guard ring — it is a passive,
  two-terminal shunt network (DR-001 Decision 1: "no current-injection pin
  and nothing in series with the loop") with no supply pins of its own, so it
  does not need its own domain guard ring, only tap coverage per the DRC tap
  rule (§1) since C1's `cap_nmos_03v3_b` body-tie needs a `VSS` tap within
  the same 15 µm pitch.

## 4. Matching-critical cells

Per #15's landed mismatch-sensitivity record
(`sim/mc-cp-mismatch/records/20260731-212614-640560e.md`) and DR-005's
explicit layout note:

| Budget term | Worst \|mean\|+3σ (nominal corner) | Budget | Verdict |
|---|---|---|---|
| 1 — DC UP/DN mismatch (worst of 0.9/1.65/2.4 V) | 8.479 % | ±12 % | **PASS** (≈29 % margin) |
| 2 — Switching-time skew, whole window | 2.702e-10 s | ±3 ns | **PASS** |
| 2a — Switching-time skew, mid-window | 2.702e-10 s | ±2 ns | **PASS** |
| 3 — Residual net charge at zero phase error | 2.989e-15 C | ±20 fC | **PASS** |
| 4 — Static phase offset, `q_zero/Kd` | 5.760e-10 s | ±3 ns | **PASS** |

All four terms pass under **random mismatch alone** (statistical switches on,
systematic tail-node mechanism separately characterized and mitigated per
DR-005/#24 — not conflated with this table). Term 1 (DC mismatch) has the
least margin, ≈29 % below its ±12 % line, and is therefore the term this
floorplan's common-centroid layout is most directly protecting.

**Additional, not-yet-budget-tabled contribution**: the divider-retiming
flop's `clk→Q` mismatch — worst-direction `|mean|+3σ` = **2.388e-10 s**
(rise-capture case, n=50) — is additive, one-for-one, to term 4 at the PFD
input (same record). It has no budget line of its own, so the common-centroid
layout below treats it as consumed margin against term 4's ±3 ns line, not
as a separate pass/fail.

**Matching-critical cell list and layout treatment:**

- **Charge-pump current sources** (`cp.sch`'s unit legs — `4u/1u` N,
  `12u/1u` P, four legs per polarity): **common-centroid**, N and P arrays
  laid out separately (different device geometry, can't interdigitate with
  each other) but each array internally common-centroid across its four unit
  legs, with the always-on leg placed at the array's geometric center per
  standard current-mirror practice. Bias-branch devices (4×-scaled) sit
  adjacent to, not inside, the unit-leg array, since DR-006/`cp.sch`'s own
  note is that the bias node's own settling (not its matching) is what
  the 4× scaling protects.
- **PFD symmetry**: the two `srlatch` + `edgedet` chains (UP and DN paths)
  are laid out as **mirror-symmetric twins** about a central axis, not
  independently placed — `pfd.sch`'s tri-state PFD symmetry is what keeps
  term 1/2/2a small in the first place (the two paths share an identical
  gate-delay structure by construction; mismatch is what breaks that
  symmetry), so the layout should not introduce an asymmetry (e.g. one path
  routed longer than the other) that the schematic-level number doesn't
  already include.
- **`cp_dumpbuf`'s PMOS input pair** (DR-005, verbatim): "`MP1`/`MP2` have
  their bulk tied to their common source, so the buffer's PMOS input pair
  needs its own n-well. #17's floorplan should treat `VDUMP`, `NSRC`/`PSRC`
  and the input pair as matching-critical, and should track the post-#24
  design rather than the clamped one." Treated here as a direct instruction:
  the PMOS input pair gets its own isolated n-well (separate from the
  charge-pump's own wide-swing cascode wells) and is laid out
  common-centroid, and `VDUMP`/`NSRC`/`PSRC` are routed as matched,
  equal-length pairs into the dump node — this is the buffer that removed
  the dominant −19.4…+15.8 ns tail-node skew term (DR-005), so its own
  layout-induced mismatch should not reopen a smaller version of the same
  problem.
- **Divider-retiming flop** (`XFRT` inside `divider_chain.sch`, a
  `dff_tg_3v3`): not common-centroid (single instance, nothing to match
  against), but placed to keep its `CLK`-to-`FB` routing short and
  symmetric with the PFD's `FB` input trace, since its `clk→Q` contribution
  above is additive to a budget term that already has less margin (term 4)
  than term 1's DC mismatch.

## 5. Area budget

**Status: first estimate for this floorplan — DR-007's amendment A3 flagged
that no area estimate existed anywhere in this repo, "not even a hand calc";
this is that hand calc.** Per the repo's own precedent for early estimates
(DR-001's loop-filter sizing was explicitly labelled "disposition only" until
DR-006 replaced it with real numbers), everything below except the loop
filter row is a **rough-order-of-magnitude (ROM) hand estimate**, not a
verified layout measurement — `design/` has no top-level physical view for
`vco`, `pfd_cp`, or `divider_chain`/`lock_detector` yet, so there is nothing
to measure. This estimate is superseded the moment real per-block layout
exists; treat every non-loop-filter row as bounded, not exact.

| Block | Basis | Active-device area | ROM overhead* | Estimated footprint |
|---|---|---|---|---|
| Loop filter (R+C1+C2) | **Real, as-drawn** (DR-006, §3) | 32,118 µm² | ×1.15 (bulk taps + interconnect only — devices already include their own body-tie/guard) | **≈36,936 µm² (0.0369 mm²)** |
| VCO (ring + bias + band mirror + buffer + decap) | Decap real (5,000 µm², `vco.sch`); active-device W×L sum from `design/README.md`'s stated sizes; ROM matching/routing multiplier | ≈900–1,600 µm² devices + 5,000 µm² decap | ×3–5 on devices (common-centroid mirror legs, guard-ring tap coverage per §1) | **≈0.011–0.017 mm²** |
| PFD + charge pump (incl. `cp_dumpbuf`) | ROM from device count/sizes in `design/README.md` (~100 devices, mostly minimum-size logic + ~12 wider CP/OTA devices) | ≈3,000–3,600 µm² | ×3–5 (CP common-centroid arrays, dump-buffer isolated n-well per §4, PFD mirror symmetry) | **≈0.010–0.020 mm²** |
| Divider chain + lock detector | ROM, std-cell-row-style estimate (~94 unit-gate-equivalents at `layout/harness/cell.py`'s proven 9-track pitch class, scaled ×1.5–2 for the hand-drawn 3.3 V cells vs. the denser 5 V0 std-cell family) | ≈1,900–2,600 µm² | ×2 (digital routing/channel overhead) | **≈0.0038–0.0052 mm²** |
| **Subtotal (blocks, midpoint of ranges)** | | | | **≈0.0704 mm²** |
| **+ top-level overhead** (VCO guard ring, four-domain supply trunk routing, block-to-block spacing) | ROM | | ×1.25 | **≈0.088 mm²** |
| **Total estimate, midpoint** | | | | **≈0.088 mm²** |
| **Total estimate, conservative (high end of every range)** | | | | **≈0.099 mm²** |

*Overhead multiplier = (guard ring + well/substrate spacing + local
interconnect) / active-device area, applied per block before the top-level
pass. Subtotal = 0.0369 (loop filter) + 0.014 (VCO midpoint) + 0.015 (PFD+CP
midpoint) + 0.0045 (divider+lock midpoint) mm²; conservative = 0.0369 + 0.017
+ 0.020 + 0.0052 mm², both ×1.25 for top-level overhead.

> **The target this section is written against has been amended, and the
> fail-loud clause below now fires against the amended one.** `spec/pll.md`'s
> Area row is **≤ 0.30 mm² (300,000 µm²)** as of **DR-016** (#456), amended from
> the draft ≤ 0.15 mm² on the measured post-lever total this section's own
> revisions produced. **Read every "< 0.15 mm²", "150,000 µm²", "120,000 µm²
> pre-overhead" and "N× over" figure in §5 and §5.1–§5.10 below as historical**
> — each was correct against the target in force when it was written, and none
> is rewritten, per this record's append-only revision convention. §5.11 states
> the position DR-016 was written on: **0.2733 mm² measured against the
> 0.30 mm² row, met, with 8.9 % margin on the block sum**; §5.12 (#469) refines
> that measurement to **0.2730 mm², met, 9.0 % margin**, §5.13 (#458) to
> **0.2264 mm², met, 24.6 % margin**, and §5.14 (#473) to **0.2254 mm², met,
> 24.9 % margin** — none of them moving the row. **DR-017** (#476, §5.15) then
> holds the row at ≤ 0.30 mm² on that re-measured floor and refreshes
> `spec/pll.md#area`'s own table onto it. The fail-loud clause at the end of
> this section is restated against 0.30 mm² there, and *that* restatement is
> the live one.

**Against the draft < 0.15 mm² (150,000 µm²) target: PASS at both the
midpoint (≈0.088 mm², ≈41 % margin) and the conservative high-end estimate
(≈0.099 mm², ≈34 % margin).** The loop filter alone (the only fully-pinned
number) is ≈20 % of budget on its own, matching DR-006's own statement almost
exactly (DR-006: "≈0.030 mm² total, ~20 % of budget" for C1 alone; this
record's 0.0369 mm² for the whole R+C1+C2 cluster is ≈24.6 % of budget). The
headroom above the loop filter (0.15 − 0.0369 ≈ 0.113 mm² available for
everything else) comfortably covers the conservative ROM estimate's own
remaining-block total (≈0.062 mm², §5's three ROM rows plus overhead), but
**this is not a signoff number** — it does not include extraction parasitics,
real transistor-level layout for the VCO/PFD-CP/divider blocks, or pad-ring
area, and the biggest single lever on it (the VCO/CP matching-overhead
multipliers) is a ROM guess, not a measurement. **Fail-loud condition for a
future pass**: if real per-block layout pushes the conservative estimate's
≈34 % margin below zero, that is a budget overrun this record's own
methodology predicts is plausible (the ROM ranges above already span a
factor of ~1.4–1.5×), not a surprise — the next floorplan revision should
state the overrun explicitly rather than silently rounding the total down.

**Fail-loud condition, as it stands today (DR-016, #456; re-stated on the
current measurement by DR-017, #476 — this supersedes the paragraph above,
which is kept as written because it is the clause that fired).** The target is
**≤ 0.30 mm² (300,000 µm²)**, i.e. ≤ **240,000 µm²** of summed block footprint
against this section's ×1.25 top-level overhead. The condition is unchanged in
kind and now reads: **if the measured block sum exceeds 240,000 µm², or if an
assembled `pll_top` measures a top-level overhead above ×1.664, say so in a new
revision rather than re-deriving the budget to fit.** Measured when DR-016 was
written: **218,631 µm²**, **×1.25 → 273,289 µm² (0.2733 mm²)**, **met, 8.9 %
margin on the block sum**. Measured today, since §5.12 (#469) packed
`cp_output_stage`'s glue bus, §5.13 (#458) routed `divider_chain`'s Metal2
tracks over its own device rows and §5.14 (#473) interleaved the glue
inverters: **180,307 µm²**, **×1.25 → 225,384 µm² (0.2254 mm²)**, **met,
24.9 % margin**, the condition above holding to a top-level overhead of ×1.664
on that sum — the margin being sized to the overhead factor's own uncertainty
and nothing else, which is precisely why DR-017 **held** the row rather than
amending it down onto the smaller measurement (§5.15). This condition is also
asserted mechanically, not only in prose:
`layout/tests/test_area_audit.py::WholeChipAreaRowTests` re-derives the sum
from the committed GDS on every test run. See §5.11 – §5.15.

### 5.1 Revision: the fail-loud condition has fired (issues #293/#324, #296, #310)

**Status: the budget above is now FAILING, by ≈2.9×, and this section states
it rather than re-deriving the estimate to fit.** This is §5's own fail-loud
clause being exercised, not a new methodology. Three of the four block rows
above have since been replaced by real, DRC-clean per-block layout, and the
measurements land far outside the ROM ranges:

| Block | §5 ROM row | Real, as-drawn | Ratio | Evidence |
|---|---|---|---|---|
| Loop filter | 0.0369 mm² (already real) | 0.0369 mm² | 1.0× | DR-006, §3 |
| VCO | 0.011–0.017 mm² | **0.0312 mm²** (183.2 × 170.3 µm) | 1.8–2.8× | `layout/evidence/vco-layout/PROOF-block.md` (#293, folded at #324) |
| PFD + charge pump | 0.010–0.020 mm² | *still ROM — no assembled `pfd_cp` block yet; its **CP output stage** is now real at **0.0079 mm²** (117.81 × 66.73 µm), on its own already ≈40–79 % of the whole row's ROM range* | — | `layout/evidence/cp-layout/PROOF.md` (#321) |
| Lock detector | *(shared row below)* | **0.0075 mm²** (119.3 × 62.6 µm) | — | `layout/evidence/lock-detector-layout/PROOF.md` (#296) |
| Divider chain | *(shared row below)* | **0.2471 mm²** (2634.28 × 93.82 µm) | — | `layout/evidence/divider-chain-layout/PROOF.md` (#310) |
| **Divider chain + lock detector** | **0.0038–0.0052 mm²** | **0.2546 mm²** | **≈49–67×** | both of the above |

Re-running this section's own arithmetic with every measured number in place
of its ROM row: 0.0369 (loop filter) + 0.0312 (VCO) + 0.020 (PFD/CP, still
ROM, high end) + 0.2546 (divider + lock) = **0.3427 mm²**, i.e. **0.4283 mm²**
after this section's ×1.25 top-level overhead — against the < 0.15 mm² draft
target, a **≈2.9× overrun** where the last revision recorded ≈22 % margin.
`skeleton.py`'s `total_extent_um2()` bounding box moves the same way and
worse (~126,400 µm² → ~1.19 × 10⁶ µm²), because the divider chain is drawn
2634 µm wide — roughly 4× the rest of the skeleton put together — so its
bounding box swallows the floorplan and most of that extent is empty space.

**Where the area actually goes, measured not guessed.** The divider chain is
one row: six `div23_cell` instances at 332.14 µm each, plus 46 glue-logic
columns, placed side by side, so the block's width is the sum of every
sub-cell's width. On top of that, ≈57 % of the block's *height* is the shared
per-net Metal2 track band (≈71 top-level nets × 0.75 µm pitch ≈ 53 µm of the
93.82 µm total), and that band spans the block's full width. Two consequences
worth stating before anyone reaches for the obvious fix:

- **The #324-style row fold does not recover this.** Folding the VCO's
  band-select mirror into two banks worked because the mirror's height was
  free (the skeleton's height was set by `LOOP_FILTER`). Here each new row
  wants its own track band, so a naive fold trades width for height at
  roughly constant area. Reducing this block needs the routing fabric itself
  to change (localized per-row tracks, or a channel-router rather than
  one-global-track-per-net), and/or the diffusion-island-per-device
  convention `vco/primitives.py` documents. That is a materially larger piece
  of work than #324 and is tracked separately.
  *(Both halves of that prediction held: §5.2 changed the routing fabric
  first and §5.3 then folded the row — in that order, and the fold only paid
  off because the fabric change went first. Device density is still
  untouched.)*
- **This is not a DRC/LVS regression.** Every block above is signoff-clean on
  the PDK's own decks at the footprint quoted (the divider chain additionally
  LVS-clean against `design/netlist/divider_chain.spice`). What has failed is
  the *area budget*, which is exactly the outcome the fail-loud clause was
  written to surface rather than absorb.

**The `DIVIDER_LOCK` reconciliation is closed.** #296 and #310 each deferred
sizing the shared divider/lock region to whichever landed second; #310 landed
second and did it. `skeleton.py`'s `DIVIDER_LOCK` is now sized to contain
both real footprints (2650.28 × 212.42 µm at #310, before §5.2's reduction
below), with the two blocks stacked and separated by a full `DOMAIN_SPACING`
— they are on different supply domains (`VDD_DIV` vs. `VDD`, §2), so sharing
the region buys signal adjacency, never a shared supply segment. The 90 × 50
µm placement-plan estimate both blocks were nominally sized against is
superseded and should not be cited again.

### 5.2 Revision: issue #341 packs the divider chain's routing tracks

**Status: the overrun is smaller — ≈2.0× rather than ≈2.9× — but still real.**
§5.1 named the divider chain's shared per-net Metal2 track band (≈71 nets ×
0.75 µm pitch ≈ 53 µm of the block's 93.82 µm total height) as the single
largest area term, and named two candidate fixes without attempting either:
"localized per-row tracks, or a channel-router rather than
one-global-track-per-net". This revision is the first of those.

`devgen.py`'s `NetTracks` handed out one Metal2 track_y per net, monotonically
increasing, never reused — correct for the sibling composites in this same
package (`div23_cell`, `dff_tg_3v3`), whose nets mostly reach the full width
of their own composite regardless, but wasteful for `divider_chain.py`'s own
top-level assembly: 71 nets, many of them genuinely local, each still cost a
full, mostly-empty track. The new `devgen.pack_tracks()` reuses one track_y
across every net whose drawn Metal2 bus extent does not come within
`METAL2_TRACK_PITCH_UM − METAL2_WIRE_WIDTH_UM` (0.41 µm, the same margin
`NetTracks` already used between tracks in y) of another net's already on
that track — the standard "left-edge algorithm" channel-router track
assignment step, which is provably optimal for this 1-D interval-packing
problem. 71 nets packed onto 22 tracks (16.5 µm), against 71 (53.25 µm)
before.

| Block | §5.1 real, as-drawn | §5.2 real, as-drawn | Δ | Evidence |
|---|---|---|---|---|
| Divider chain | 0.2471 mm² (2634.28 × 93.82 µm) | **0.1503 mm² (2634.28 × 57.07 µm)** | −39 % area, height only | `layout/evidence/divider-chain-layout/PROOF-track-packing.md` (#341) |
| Divider chain + lock detector | 0.2546 mm² | **0.1578 mm²** | −38 % | both of #296's and #341's records |

Re-running §5.1's own arithmetic with the new divider-chain number: 0.0369
(loop filter) + 0.0312 (VCO) + 0.020 (PFD/CP, still ROM) + 0.1578 (divider +
lock) = **0.2459 mm²**, i.e. **0.3074 mm²** after ×1.25 top-level overhead —
against the < 0.15 mm² draft target, a **≈2.0× overrun**, down from §5.1's
≈2.9×. `skeleton.py`'s `total_extent_um2()` bounding box moves the same way:
~1.19 × 10⁶ µm² → **~1.09 × 10⁶ µm²**.

**The width is unchanged, and §5.1's fold caveat is unchanged in spirit —
narrowed, not resolved.** The divider chain is still one row of six
`div23_cell` instances plus 46 glue-logic columns, and on its own it is still
just over the entire 0.15 mm² die target. What §5.1 got right and this
revision does not undo is that a row fold only pays off once the routing
fabric stops charging one full-width band per row — which is exactly what
this revision fixed. A fold is a follow-up (issue #344), not attempted here:
re-deriving the six instances' placement grid and the glue logic's own
layout for a multi-row assembly is a materially larger piece of work than
this revision's own routing-fabric change, and #295's "six identical
instances" acceptance criterion has to be re-proved for however many rows
result. *(That fold landed at §5.3 below; the "six identical instances"
criterion re-proved clean at two rows.)*

**Still not a DRC/LVS regression.** The divider chain is signoff-clean on the
PDK's own decks at the new footprint, additionally re-proved LVS-clean
against `design/netlist/divider_chain.spice` unchanged (`layout/evidence/
divider-chain-layout/PROOF-track-packing.md`).

### 5.3 Revision: issue #344 folds the divider chain's row in two

**Status: the overrun is smaller again — ≈1.9× rather than ≈2.0× — and the
divider chain on its own now fits inside the whole-chip target for the first
time.** §5.2 left exactly one structural cause standing: the block was still
one row, so its width was the sum of every sub-cell's width. This revision is
the fold §5.1 predicted would only work *after* the routing fabric changed.

`divider_chain.py`'s new `ROW_PLAN` places three `div23_cell` instances per
row in two stacked rows, each row carrying its own independent
`devgen.pack_tracks()` band. Two placement choices carry the result, and
neither changes a single device or connection — `reference_netlist()` is
byte-for-byte what it was:

- **The glue logic moved in beside the instances it wires.** Through §5.2 all
  46 glue-logic columns sat to the right of all six instances, so every chain
  net ran the block's full width to reach them; the measured net-extent
  profile ramped monotonically to ≈20 mutually-overlapping nets at the glue
  boundary, and that peak *is* the track count. The glue is now grouped per
  divider stage and placed next to that stage's own instances.
- **The one-hot AND second stage split in two.** `XMA` consumes `T0`–`T2` and
  `XMB` consumes `T3`–`T5`, so each sits in the row holding the three stages
  that produce its own terms, keeping all six `T` nets row-local.

A net with pads in both rows still needs its two buses tied together: those
seven nets (`VSS`, `VDD_DIV`, `VCO`, `MO3`, `MB`, `DIVOUT`, `CK3`) each get a
reserved vertical Metal3 column in a left-hand spine at negative x. The two
rows use 12 and 10 tracks — 22 in total, the same number §5.2's single band
used, but now spanning half the width each.

| Block | §5.2 real, as-drawn | §5.3 real, as-drawn | Δ | Evidence |
|---|---|---|---|---|
| Divider chain | 0.1503 mm² (2634.28 × 57.07 µm) | **0.1321 mm² (1317.66 × 100.29 µm)** | −12 % | `layout/evidence/divider-chain-layout/PROOF-fold.md` (#344) |
| Divider chain + lock detector | 0.1578 mm² | **0.1396 mm²** | −12 % | both of #296's and #344's records |

Re-running §5.1's arithmetic once more: 0.0369 (loop filter) + 0.0312 (VCO) +
0.020 (PFD/CP, still ROM) + 0.1396 (divider + lock) = **0.2277 mm²**, i.e.
**0.2846 mm²** after ×1.25 top-level overhead — a **≈1.9× overrun** against
the < 0.15 mm² draft target, down from §5.2's ≈2.0× and §5.1's ≈2.9×.
`skeleton.py`'s `total_extent_um2()` moves much further, because the divider
chain stops dominating the bounding box: ~1.09 × 10⁶ µm² → **~0.61 × 10⁶
µm²**, −44 %.

**The fold reduced area, it did not merely move it.** That was the specific
failure mode §5.1 warned of, so it is worth separating the two levers this
revision pulled:

| | Width × height | Area |
|---|---|---|
| §5.2 baseline, one row | 2634.28 × 57.07 µm | 150,338 µm² |
| Folded, placement gaps unchanged at 20 µm | 1401.66 × 100.29 µm | 140,572 µm² (−6.5 %) |
| Folded, instance/glue gap re-derived to 6 µm | 1317.66 × 100.29 µm | **132,148 µm² (−12.1 %)** |

The 20 µm instance-to-instance gap #310 chose was re-derived against the
drawn cell rather than assumed: `div23_cell`'s n-well is inset 2.12 µm from
its instance box's left edge and 0.22 µm from its right, so two instances
6 µm apart have 8.34 µm between their wells — ≈6× NW.2b's 1.4 µm minimum,
and the binding rule at that boundary is plain same-layer metal spacing
(0.23–0.28 µm) rather than well spacing at all. A folded block pays this gap
several times per row, which is why it was worth re-deriving here and not
before.

**What is left is device density, not placement.** At 0.1321 mm² for 452
transistors the block spends ≈292 µm²/transistor, against `lock_detector`'s
≈187 for the same PDK and flavour — the diffusion-island-per-device
convention `vco/primitives.py` documents. That lever is shared with the VCO's
own residual overrun and is deliberately untouched by both §5.2 and §5.3.

**Still not a DRC/LVS regression.** The divider chain is signoff-clean on the
PDK's own decks at the folded footprint, and re-proved LVS-clean against
`design/netlist/divider_chain.spice` — whose flattened re-expression is
byte-for-byte unchanged by this revision (`layout/evidence/
divider-chain-layout/PROOF-fold.md`).

### 5.4 Revision: `pfd_cp` is now real (issues #385, #386)

**Status: the PFD/CP row is no longer a ROM estimate.** `pfd` (#300,
mirror-symmetric PFD layout) is assembled with the complete `cp` block
(#385, `cp_output_stage` + `cp_dumpbuf`) into one flat, standalone-DRC-clean
`pfd_cp` block matching `design/pfd_cp.sch`'s top-level netlist — the final
integration piece #303/#294 asked for (`layout/pll_top/pfd_cp/block.py`,
`layout/evidence/pfd-cp-layout/PROOF.md`).

| Block | §5's ROM row | §5.4 real, as-drawn | Δ | Evidence |
|---|---|---|---|---|
| PFD + charge pump | 0.010–0.020 mm² | **0.0351 mm² (434.31 × 80.73 µm)** | 1.76–3.5× over the ROM range | `layout/evidence/pfd-cp-layout/PROOF.md` (#386) |

Re-running §5.1's arithmetic once more, replacing the PFD/CP row's ROM
high-end estimate with the real number: 0.0369 (loop filter) + 0.0312 (VCO)
+ 0.0351 (PFD/CP, real) + 0.1396 (divider + lock) = **0.2428 mm²**, i.e.
**0.3035 mm²** after §5's own ×1.25 top-level overhead — a **≈2.0× overrun**
against the < 0.15 mm² draft target, up slightly from §5.3's ≈1.9× (the
PFD/CP row grew from its own ROM high end, 0.020 mm², to the real 0.0351
mm² — a genuine increase, not a rounding artifact).
`skeleton.py`'s `total_extent_um2()` is effectively unchanged (~0.611 × 10⁶
µm², same order as §5.3's ~0.61 × 10⁶): the divider chain, not `PFD_CP`,
sets the skeleton's overall width (`DIVIDER_LOCK.w` = 1333.66 µm, against
`PFD_CP`'s own 434.31 µm), so widening `PFD_CP` shifted `LOOP_FILTER`/
`VCO_CORE` to the right without moving the skeleton's own bounding box.

**The cause, same structural pattern as the VCO/divider-chain overruns
above:** every device in `pfd`/`cp_array`/`cp_output_stage`/`cp_dumpbuf` is
its own diffusion island wired by metal (`devgen.py`'s own module
docstring), and `pfd_cp` composes two already-wide sub-blocks
side-by-side rather than folding either — `cp` alone is 347.41 × 74.73 µm
(`layout/evidence/cp-block-layout/PROOF.md`), and placing `pfd` (80.9 ×
22.48 µm) beside it adds width, not height, since the bridging routing
(four Metal3 risers + a Metal2 trunk row above both blocks) needs no
dedicated channel of its own. No fold pass has been attempted on `pfd_cp`
the way #324/#341/#344 folded the VCO/divider chain; that lever is
deliberately untouched here, tracked as a follow-up the same way §5.3's own
"what is left is device density" note tracks the divider chain's own
residual overrun.

**Not a DRC regression.** `pfd_cp` is signoff-clean on the PDK's own `main`
deck, both the default and `--offgrid` (signoff-grade) runs, against the
real assembled geometry — `layout/evidence/pfd-cp-layout/PROOF.md`. No LVS
claim is made for the same reason `cp`'s own record states: a reference
netlist for the block is not part of this issue's own scope (see
`PROOF.md`'s "No LVS claim, and why").

### 5.5 Revision: the levers are measured, and the one this record kept naming is not one (issue #442)

**Status: the overrun is 2.03×, and for the first time every remaining lever
on it is sized rather than named.** No geometry changes in this revision —
nothing under `layout/pll_top/`, no committed GDS, no deck verdict is touched.
What changes is that §5.1–§5.4 each named their successor lever from a
*derived* quantity, and one of those namings was wrong. Full record and
reproduction: `layout/evidence/area-audit/PROOF.md`, regenerated by
`python3 layout/run_pv.py area` (no PDK, no deck — the `klayout` pip wheel
only, so it runs in CI's headless `checks` job).

**First, this record's own VCO row had drifted.** §5.1 and §5.4 both carry
0.0312 mm² (183.18 × 170.28 µm) for `vco_block`, from #324's fold. The
committed GDS is **172.52 × 184.48 µm = 0.0318 mm²** — the VCO changed after
#324 (`layout/evidence/vco-layout/PROOF-2d-fold.md`, then
`PROOF-381-high-rs-resistor.md`) and this section's arithmetic did not follow.
+634 µm², +2.0 % on that row. Every figure below is the committed GDS bounding
box, which is why the audit is now a command rather than a hand calculation.

Re-derived on that basis, and adding `lock_detector` as its own row rather
than folding it into the divider chain's:

| Block | as-drawn | Basis |
|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | DR-006 / §3 — still a calculation; no loop-filter layout exists |
| `vco_block` | **31,826 µm²** | committed GDS (was 31,192 in §5.1/§5.4) |
| `pfd_cp` | 35,281 µm² | committed GDS (footprint tuple says 35,060) |
| `divider_chain` | 132,148 µm² | committed GDS |
| `lock_detector` | 7,468 µm² | committed GDS |
| **Sum** | **243,660 µm² (0.2437 mm²)** | |
| **After §5's ×1.25** | **304,575 µm² (0.3046 mm²)** | **2.03× over the 0.15 mm² target** |

Against §5's ×1.25 factor the sum of block footprints must be ≤ **120,000
µm²**, so the gap to close is **123,660 µm²**. Each lever below is sized
against that denominator.

**Every drawn block is 61–83 % whitespace.** Devices, wells, wires and
contacts together occupy 39.2 % of `vco_block`, 27.0 % of `lock_detector`,
21.2 % of `divider_chain` and 17.1 % of `pfd_cp`. For scale inside the same
generator family, `pfd` alone — a flat Metal1/Metal2-only row of 47 leaf
instances — measures 69.0 % fill. The low numbers are a property of how these
blocks are *composed*, not of the leaf cells they are composed from.

| Lever | Sized at | Share of the 123,660 µm² gap | Verdict |
|---|---|---|---|
| **1. `pfd_cp` fold** (§5.4's lever) | 7,015 µm² | 5.7 % | Worth executing on its own merits; does not close the gap. Issue #455. |
| **2. Divider-chain shared diffusion** (§5.3's "what is left is device density") | 125 µm² | **0.10 %** | **Falsified. Not worth executing.** |
| **3. The Metal2 track band over the cells rather than above them** (unnamed until now) | 77,869 µm² | 63.0 % | This is the lever. Issues #454 (`divider_chain`) and #455 (`pfd_cp`). |

**Lever 2 is the one this record kept naming, and the measurement disposes of
it.** §5.1, §5.3 and §5.4 all reason from µm²/transistor — 132,148 µm² / 452
devices = 292, against `lock_detector`'s 187 — to "every device is its own
diffusion island". That ratio cannot tell "the islands are too big" from "the
islands are 1 % of the block and the rest is empty". Measured: the divider
chain's `comp` is **1,352.5 µm², 1.02 % of the block**; its `poly2` 0.37 %;
Σ W·L over all 452 devices 260.3 µm², 0.20 %. So even if every diffusion
island vanished outright, that is 1.09 % of the gap. Shared diffusion does not
remove diffusion, it merges adjacent islands: `divider_chain.spice` has **40**
genuine shared-diffusion candidates among its 452 devices (a node on exactly
two same-flavour source/drain terminals and no gate), and at `devgen.py`'s own
column geometry each merge frees 1.10 µm of column height over the wider
device's width — **125.4 µm² in total, 0.095 % of the block.** A generator
change across `devgen.py` and eight row-cell modules, re-proving a 452-device
block's DRC *and* its LVS match, for one part in a thousand of what has to
come out. `layout/tests/test_area_audit.py` now asserts that bound so the
conclusion fails loudly if future geometry ever falsifies it.

The same measurement retires §5.3's "that lever is shared with the VCO's own
residual overrun": `vco_block` has the *highest* comp share of any block
(13.78 %) and a 1.00 µm no-device band. Its 60.8 % whitespace is the
guard-ring and well/substrate spacing §1 sized it to be, not density.

**Lever 3 is what the whitespace actually is.** Every composite generator here
assigns each net a Metal2 `track_y` *above* the cells it has already drawn
(`devgen.NetTracks`, and `pack_tracks()` since §5.2). Composition is
hierarchical, so the bands stack — `dff_tg_3v3` above its leaf cells,
`div23_cell` above `dff_tg_3v3`, `divider_chain` above `div23_cell`. Measured
in the divider chain: **73.97 µm of the block's 100.29 µm height contains no
diffusion at all**, and the Metal2 plane over the two rows that *do* contain
diffusion is **1.0 % occupied**. Metal2 has no DRC relationship to the
diffusion beneath it; the band is above the cells because that is where
`NetTracks` puts it, not because the plane over them is unavailable. The
block's 73 distinct Metal2 tracks packed solid at the shared 0.75 µm pitch
occupy 54.75 µm against the 100.29 µm drawn.

**What the levers cannot do, which is the finding that matters.** Taking all
three to their geometric ceilings at once — every track hidden over a device
row, no jog around any Via1 landing, perfect inter-row packing, i.e. an
optimistic bound no implementation will reach:

| | Sum | After ×1.25 | vs 0.15 mm² |
|---|---|---|---|
| As drawn | 243,660 µm² | 304,575 µm² | 2.03× |
| Every lever at its ceiling | **162,145 µm²** | **202,681 µm²** | **1.35×** |

The residual is visible without any lever at all: the loop filter (36,936 µm²,
set by DR-006's C1/C2 *capacitance* at the measured 3.988 fF/µm² of
`cap_nmos_03v3_b` — a loop-dynamics change, not a layout one) plus
`vco_block` at its own ceiling (31,654 µm²) is **68,590 µm², 57.2 % of the
entire 120,000 µm² pre-overhead budget**. That leaves 51,410 µm² for
`pfd_cp` + `divider_chain` + `lock_detector`, whose combined ceiling is
93,555 µm² — **1.82× short**.

**This revision deliberately does not amend `spec/pll.md#area`.** 1.35× is a
bound derived from unexecuted levers, not a measured floor, and amending a
ratified spec row on an estimate is exactly the move this repo's own
instructions forbid ("agents do not relax the ratified spec to make results
pass"). The amendment, if the evidence ends up supporting one, is owed after
lever 3 is built and DRC/LVS-clean on at least the divider chain — the block
that is 54 % of the sum. That amendment is tracked at **#456**, blocked on
**#454** and **#455**. What this revision replaces is the state §5.4 left
behind: an overrun whose remaining lever was "tracked as a follow-up" with no
issue behind it and no number attached.

**Still not a DRC/LVS regression, trivially.** No geometry changed.

### 5.6 Correction: §5.5's `lock_detector` fill figure was measured off a stale artifact (issue #451)

§5.5 above reports "27.0 % of `lock_detector`" as that block's fill, and
`layout/evidence/area-audit/area-audit.md` carried 2,013 µm² drawn and 556.4
µm² of `comp` to match. Both were measured — correctly, from the committed
GDS — off an artifact that **its own generator had stopped producing**.
`layout/evidence/lock-detector-layout/lock_detector.gds` was committed once
at #311 (2026-09-08) and the generator changed seven times afterwards without
the file being regenerated; issue #451 found it, fixed the generator's
DRC regression and regenerated the artifact. §5.5's own §5.5-opening
paragraph makes the general point already ("this record's own VCO row had
drifted … which is why the audit is now a command rather than a hand
calculation") — this is the same failure one level down, in the *input* to
that command rather than in the hand calculation.

Re-measured against the regenerated artifact:

| | §5.5 (stale artifact) | corrected |
|---|---|---|
| `lock_detector` fill | 27.0 % | **30.2 %** |
| `lock_detector` drawn | 2,013 µm² | **2,254 µm²** |
| `lock_detector` `comp` | 556.4 µm² (7.45 %) | **580.4 µm² (7.77 %)** |
| `lock_detector` Metal2 tracks | 23 | **24** |

**Nothing else in §5 moves, and no lever is resized.** The block's bounding
box — the only `lock_detector` quantity any of §5.5's arithmetic consumes —
is **119.30 × 62.60 µm = 7,468 µm²**, identical before and after: the
generator fix changed how the riser lanes are packed, not how far the block
extends. So the 243,660 µm² sum, the 123,660 µm² gap, the three levers'
sizings and the 1.35× ceiling all stand exactly as §5.5 derived them. The
whitespace sentence's ordering ("39.2 % of `vco_block`, 27.0 % of
`lock_detector`, 21.2 % of `divider_chain` and 17.1 % of `pfd_cp`") is also
unchanged in kind — `lock_detector` is still second, now at 30.2 %.

`layout/tests/test_gds_reproducibility.py` (issue #451) now rebuilds every
committed block GDS from its generator on each test run and fails on any
difference, so the *input* to `run_pv.py area` can no longer go stale without
the suite saying so. One artifact is a known exception and is excluded by
name with its own issue: `layout/evidence/floorplan-skeleton/` does not
reproduce either (its committed file predates #354, #358 and #398) — that is
this record's own skeleton, tracked at **#461**, and §6 below should be
re-read against it once that lands.

### 5.7 Re-derivation: the skeleton artifact was six merges stale, and §5's arithmetic is unaffected (issue #461)

**Status: no figure in §5 changes.** §5.6 above closed with "`layout/evidence/
floorplan-skeleton/` does not reproduce either … §6 below should be re-read
against it once that lands". It has landed: the artifact is regenerated,
re-run through the foundry DRC deck (clean), and registered in
`layout/harness/reproduce.py`'s `BLOCKS` — 26 of 26 committed block GDS files
now reproduce, with no stale-artifact exclusion left in that map. Full
account, including the DRC provenance: `layout/evidence/floorplan-skeleton/
PROOF.md` § "Re-run, issue #461".

**How stale it was: six merges, not the three #451 and #461 both named.**
Rebuilding the skeleton at every one of the 41 commits that touched `layout/`
since the artifact was written identifies six that changed its output — PRs
#342 (issue #310), #346 (#341), #354 (#336), #358 (#344), #377 (#371) and
#398 (#386). The two the "three merges" framing missed (#310's `DIVIDER_LOCK`
reconciliation, #341's track packing) are the two largest single moves, and
one of the six (#377, a `vco/ring.py` Metal1 short fix) never touched
`skeleton.py` at all — `VCO_CORE` is `vco/block.py`'s own `footprint_um()`,
so a sub-block's height change propagates into the floorplan with no edit to
this record's generator. Auditing the floorplan by `git log --
layout/floorplan/skeleton.py` undercounts by construction.

**Which figures this re-derivation does and does not change:**

| Figure | Source | Changed by the regeneration? |
|---|---|---|
| §5's four block rows, the ×1.25 overhead, the 0.2437 mm² sum, 0.3046 mm² total, 2.03× overrun | §5.5, from each block's **own** committed GDS via `python3 layout/run_pv.py area` | **No.** The skeleton is not an input to that command. |
| §5.5's three lever sizings and the 1.35× ceiling | same | **No.** |
| §5.6's corrected `lock_detector` fill numbers | `lock_detector.gds`, regenerated at #451 | **No.** |
| §5.1–§5.4's `total_extent_um2()` figures (~1.19 → ~1.09 → ~0.61 × 10⁶ µm²) | `skeleton.py` **as code**, evaluated at each revision | **No** — and this is the reason none of the above moved. `total_extent_um2()` reads the module's own `Block` tuples, never the committed GDS, so §5.3/§5.4's ~0.61 × 10⁶ µm² has been the generator's true value since #358/#398. Re-evaluated today: **611,310 µm²**, which is §5.4's ~0.611 × 10⁶ exactly. |
| `layout/evidence/floorplan-skeleton/PROOF.md`'s "126,395 µm², ≈16 % headroom" | the **stale committed artifact** | **Yes — superseded.** The regenerated skeleton's extent is 611,310 µm², i.e. **4.08× the 0.15 mm² target**, not 16 % under it. Recorded in that file's own appended section. |

So the stale artifact never reached this record's budget arithmetic; it
reached its own evidence directory's headline number, and (through §5.6) the
repository's claim that the committed evidence tree reproduces. Both are now
corrected, and the second is enforced rather than asserted.

**Not a DRC regression, and not a new overrun.** The regenerated skeleton is
DRC-clean on the same `main` deck at variant D (clean by construction — layer
(0, 0) carries no rule in this deck, as §6 below has always stated). The
4.08× extent figure is the same overrun §5.3/§5.4 already record, now finally
also true of the committed file.

### 5.8 Revision: the first sized lever is spent — 2.03× to 1.70× (issue #454)

**Status: still over, by 1.70× rather than 2.03×.** §5.5 sized every
remaining lever without spending any; this is the first one spent, and the
first revision in this series whose number moves because geometry changed
rather than because arithmetic was corrected. Full record and reproduction:
`layout/evidence/divider-chain-layout/PROOF-macro-track-packing.md`.

`div23_cell`'s own internal Metal2 track band now uses
`devgen.pack_tracks()` instead of `devgen.NetTracks` — the identical one-line
substitution §5.2 made in `divider_chain.py` one level up, applied one level
down. 31 nets go from 31 never-reused tracks to **11**, which is the interval
graph's own clique number and therefore provably the minimum. 15.00 µm off
the macro, paid once per `ROW_PLAN` row:

| Block | §5.5 | §5.8 | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 35,281 µm² | 35,281 µm² | — (lever tracked at #455) |
| `divider_chain` | 132,148 µm² | **92,618 µm²** | **−39,530 µm², −29.9 %** |
| `lock_detector` | 7,468 µm² | 7,468 µm² | — |
| **Sum** | 243,660 µm² (0.2437 mm²) | **204,129 µm² (0.2041 mm²)** | −16.2 % |
| **After §5's ×1.25** | 304,575 µm² (0.3046 mm²) | **255,161 µm² (0.2552 mm²)** | |
| **vs the 0.15 mm² target** | **2.03×** | **1.70×** | |

The gap to close against §5's 120,000 µm² pre-overhead budget goes from
123,660 µm² to **84,129 µm²**.

**§5.5's estimate for this lever was 60,006 µm²; the outcome is 39,530 µm²,
65.9 % of it.** The shortfall is an attribution error in the estimate, not in
the execution, and it is worth recording because §5.1, §5.3 and §5.4 each made
a version of the same mistake. §5.5 measured 73.97 µm of no-diffusion band and
treated the block's 73 Metal2 tracks as one population that could be packed
into 54.75 µm. They are not one population: they live at three levels of a
hierarchy, and packing is only ever possible *within* a level, because the
outer level places the inner one as an opaque box. The real split, measured by
instrumenting every `pack_tracks()` call in one build:

| Term | Height | Share of 100.29 µm |
|---|---|---|
| devices (`comp`), both rows | 26.32 µm | 26.2 % |
| **`div23_cell`'s own band, ×2 rows** | **46.50 µm** | **46.4 %** |
| `divider_chain`'s own packed bands | 16.50 µm | 16.5 % |
| wells, taps, band base gaps, margin | 10.97 µm | 10.9 % |

The top-level band §5.5 named was only 16.50 µm of the 73.97, precisely
*because* §5.2 had already packed it. What had never been packed was the
macro's own band, and because each row's height is gated by the `div23_cell`
standing in it, the same change is worth twice as much here as it was at the
top level.

**§5.5's lever 3 survives, reduced.** What this revision did is drain the
largest band; what it did not do is §5.5's literal proposal, moving a band
into the plane *over* a device row. The block still carries 43 distinct Metal2
tracks in 43.97 µm of no-diffusion band above 26.32 µm of devices, with that
plane 1.0 % occupied — so the over-the-devices lever remains, at its own
ceiling worth 70.29 → 32.25 µm of height. It is a materially riskier change
(a bus at a device-band `track_y` can run through another net's Metal2 riser
landing square — `cp.py` records four failed routing designs in that class)
and is filed as **#458** rather than folded in, per §5.5's own one-lever-per-PR
discipline.

**`spec/pll.md#area` is still not amended, and #456's precondition is still
not met.** 1.70× is now a *measured* number for the divider chain rather than
an estimate, but `pfd_cp`'s lever (#455) and the residual over-the-devices
lever (#458) are both unexecuted, so a floor still does not exist. What §5.5 said
about not amending a ratified spec row on an estimate applies unchanged.

**DRC/LVS re-verified, not assumed.** Both changed blocks are rebuilt and
re-run: `div23_cell` and `divider_chain` are DRC clean (0 violations) and LVS
matched at the new geometry, and `divider_chain` is additionally DRC clean
under `--offgrid`, which it had not previously claimed. Both
`reference_netlist()` outputs are byte-for-byte unchanged, and `div23_cell`'s
seven pin locations and x-extent are unchanged — only each net's `track_y`
moved.

### 5.9 Revision: `lock_detector` grows ~4.1x for its own first LVS match, and the overrun moves 1.70x -> 1.89x (issue #449)

**Status: the overrun is now 1.89x, and for the first time all four PLL
sub-blocks are LVS-matched.** `lock_detector`'s drawn `delaywin_3v3` cell
predated DR-014's 4-bit static process trim (issue #411, ratified into
`design/lock_detector.sch` and `design/netlist/lock_detector.spice` on
2026-09-19) — the generator drew a fixed 4-stage delay chain with no
`LDT0`-`LDT3` trim inputs and no switched-segment network at all, so the
block's own first block-level LVS run (#440) correctly reported a mismatch
rather than a match. Issue #449 closes that gap: `cells.draw_delaywin()` now
draws every device `design/gen_delaywin.py`'s own sizing table specifies —
the always-on base load plus four binary-weighted switched segments per
stage, each gated by its own trim bit through a `T`-input inverter — and
`build_lock_detector()` routes the four new `LDT0`-`LDT3` boundary pins in
from wherever the rest of this block's boundary nets already arrive (no
floorplan route needed: `layout/floorplan/skeleton.py`'s `DIVIDER_LOCK`
region is a placement/keep-out plan with no per-signal routes of its own).
Full device-level record: `layout/evidence/lock-detector-layout/PROOF.md`
"Addendum 4"; this section is the area-budget consequence.

**This is not a placement regression — it is 72 devices the block's own
ratified schematic always specified (45 -> 117) finally being drawn**, and
the area those devices need is what buys the block's first LVS match. The
block's own bounding box grows **119.30 x 62.60 um (7,468 um²) -> 294.80 x
103.75 um (30,586 um²), ~4.1x**, driven by the same scarce resource named in
§5.5/§5.6 for the other blocks: not diffusion (`lock_detector`'s own `comp`
share actually *drops*, 7.77 % -> 2.48 %, because the added devices are
mostly minimum-width switches) but Metal3 riser-lane width — 45 devices/161
riser groups became 117/409, and `layout/pll_top/lock_detector/cells.py`'s
own `TRIM_COL_PITCH_UM` docstring records the swept pitch-vs-width tradeoff
that resolved it (issue #449). `lock_detector`'s own fill correspondingly
*drops*, 30.2 % -> 34.5 % filled by area but 2.48 % `comp` against 7.77 %
before — the new devices are individually small; there are just many more
of them, spread across proportionally more riser-lane whitespace.

Re-running §5.5's table with the regenerated evidence
(`layout/evidence/area-audit/area-audit.md`, `python3 layout/run_pv.py
area`) — the loop filter and `vco_block`/`pfd_cp` rows unchanged from
§5.5/§5.6, `divider_chain` already at §5.8's packed geometry, and only
`lock_detector`'s row moving here:

| Block | as-drawn | Basis |
|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | DR-006 / §3 — still a calculation |
| `vco_block` | 31,826 µm² | committed GDS |
| `pfd_cp` | 35,281 µm² | committed GDS |
| `divider_chain` | 92,618 µm² | committed GDS (packed at §5.8/#454) |
| `lock_detector` | **30,586 µm²** | committed GDS (was 7,468 through §5.6) |
| **Sum** | **227,247 µm² (0.2272 mm²)** | |
| **After §5's ×1.25** | **284,059 µm² (0.2841 mm²)** | **1.89× over the 0.15 mm² target** |

Against §5's ×1.25 factor the sum of block footprints must still be ≤
120,000 µm², so the gap to close grows from 84,129 µm² (§5.8, after the
divider-chain packing lever alone) to **107,247 µm²**. None of §5.5's three
named levers (the `pfd_cp` fold #455, `divider_chain` shared diffusion —
falsified — and the residual Metal2-band-over-cells lever #458, now that
§5.8 has already spent the `div23_cell` macro-band portion of that third
lever) is sized against `lock_detector`, so taking the remaining ceiling of
those and adding `lock_detector`'s new, unlevered footprint in full:

| | Sum | After ×1.25 | vs 0.15 mm² |
|---|---|---|---|
| As drawn | 227,247 µm² | 284,059 µm² | 1.89× |
| Every remaining lever at its ceiling (`lock_detector` un-levered) | **185,263 µm²** | **231,579 µm²** | **1.54×** |

**A fourth lever — sized for `lock_detector`'s own newly-measured 65.5 %
whitespace — is not named or sized here.** Per §5.5's own discipline, an
unmeasured lever is not claimed as a number; naming and sizing it is left to
whichever future pass takes it up, the same way §5.4 left "the levers are
measured" to §5.5 rather than guessing.

**This revision deliberately does not amend `spec/pll.md#area`**, for the
same reason §5.5/§5.8 gave: 1.54× is a bound derived from unexecuted levers,
not a measured floor, and every remaining named lever belongs to a different
block than the one that moved this revision.

`layout/floorplan/skeleton.py`'s own `DIVIDER_LOCK` fail-loud comment block
carries the same conclusion in the region-local (not whole-chip-table) form
it has used since #310, now also using every block's own measured GDS —
§5.8 already moved it off the ROM-era `pfd_cp` figure — so its own
arithmetic reaches the same **1.89×** this section does, and
`LOCK_DETECTOR_STANDALONE_W_UM`/`_H_UM` there are the same 294.80 x 103.75 um
this section's table sums.

`layout/tests/test_floorplan_skeleton.py`'s `total_extent_um2()` ratchet
(§5.8's context: was ~0.57e6 um² after the divider-chain packing lever
alone) is loosened from 600,000 to 650,000 um² for this revision — measured
~0.63e6 — with the same "only ever correct with a reason recorded beside
it" discipline that test's own docstring now states explicitly, so a future
placement-only regression still fails there.

**DRC/LVS status: `lock_detector` re-proven clean on both decks against the
regrown geometry** (`layout/evidence/lock-detector-layout/lock_detector.gds`,
`drc-clean/`, `lvs-clean/` — promoted from `lvs-attempt/`, which is kept
alongside it per the same convention `pfd-cp-layout/` uses for its own
superseded mismatch run). **All four PLL sub-blocks are now LVS-matched
against their own committed, ratified schematics** — the first time this has
been true of any PLL sub-block set in this repository — so `README.md` and
`docs/chipalooza/challenge-5-proposal.md` move from "3 of the 4" to "4 of the
4 are LVS-matched", checked by `layout/lib/check-layout-status-claims.sh`.

### 5.10 Revision: the second sized lever is spent, and the first one whose ceiling was measurably wrong — 1.89× to 1.82× (issue #455)

**Status: still over, by 1.82× rather than 1.89×.** §5.5 sized `pfd_cp`'s two
levers — the fold (§5.4's named lever, 7,015 µm²) and the Metal2 track band
over the cells (16,785 µm² on this block) — and paired them in one issue
because they interact. Both are now spent. Full record and reproduction:
`layout/evidence/pfd-cp-layout/PROOF-455-fold.md`.

`pfd` (80.90 × 22.48 µm) no longer sits beside `cp`; it sits **inside** `cp`'s
own 99.0 %-empty band above `cp_dumpbuf`, so the block is now exactly as wide
as the `cp` it contains. And the Metal2 trunk band above both was pitched at
`cp_array.RISER_MIN_PITCH_UM` (1.00 µm) — a minimum Metal3 *riser column* **X**
pitch, applied to a horizontal Metal2 **row** spacing — and based a full
`BACKBONE_MARGIN_UM` above a top edge that already *was* a trunk row. Both
corrected: 0.75 µm pitch (`METAL2_TRACK_PITCH_UM`, the pitch
`cp_output_stage`'s own glue bus already carries 14 Via2-landed tracks at),
and this block's four rows continue `cp`'s band rather than starting a new one.

| Block | §5.9 | §5.10 | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 35,281 µm² | **26,665 µm²** | **−8,616 µm², −24.4 %** |
| `divider_chain` | 92,618 µm² | 92,618 µm² | — |
| `lock_detector` | 30,586 µm² | 30,586 µm² | — |
| **Sum** | 227,247 µm² (0.2272 mm²) | **218,631 µm² (0.2186 mm²)** | −3.8 % |
| **After §5's ×1.25** | 284,059 µm² (0.2841 mm²) | **273,289 µm² (0.2733 mm²)** | |
| **vs the 0.15 mm² target** | **1.89×** | **1.82×** | |

The gap to close against §5's 120,000 µm² pre-overhead budget goes from
107,247 µm² to **98,631 µm²**. `cp`'s own committed block shrinks with it
(26,062 → 25,630 µm², the pitch correction), but `cp` is not a row in this
table — it is inside `pfd_cp`'s.

**§5.5's ceiling for these two levers was 14,852 µm²; the outcome is 26,665
µm², 42 % of it — and this time the shortfall is in the *ceiling*, not the
execution.** One of the two levers reached its sizing exactly: the fold
removed all 86.90 µm of width it was sized at, because 347.41 µm is `cp`'s
own width and no arrangement keeping `cp` intact is narrower. The height
lever delivered 4.25 µm of the 38.80 µm its ceiling assumed. Three measured
reasons, and the first is the mistake §5.8 already recorded for #454:

1. **The 57-track census is flat over five levels, and only 4 of the 57
   belong to `pfd_cp`.** Rebuilding each sub-block standalone and running the
   same census on each: `pfd` 5, `cp_dumpbuf` 10, `cp_output_stage` (incl.
   `cp_array`) 32, `cp`'s own backbone band 6, `pfd_cp`'s own trunk band
   **4** — 57 exactly. Composition is hierarchical, so a track can only be
   re-assigned within the level that drew it. "57 tracks packed solid into
   42.75 µm" is not a transformation any one module can perform.
2. **The fold moves the binding constraint from tracks to devices.** The
   37.18 µm device-band figure in the ceiling was measured *before* the fold,
   when `pfd`'s devices shared y-bands with `cp`'s. Giving `pfd` a band of
   its own takes the block's device bands to **49.05 µm** — above the
   42.75 µm packed-track floor. Re-derived post-fold, the same
   `max(packed, devices)` ceiling is 344.98 × 49.05 = **16,921 µm²**, −52.0 %,
   not −58 %. Lever 1 invalidated part of lever 2's sizing, which is the
   interaction #455 existed to force into one decision, sharpened into a
   number.
3. **One sub-block exceeds the ceiling height on its own.**
   `cp_output_stage`'s drawn diffusion spans 52.23 µm of y standalone (`cp`'s
   spans 54.03 µm). No arrangement of `pfd_cp` is 42.75 µm tall while
   containing a block whose own devices are 52.23 µm tall.

**What a composition-level lever *can* do, measured.** The honest denominator
for a lever at this level is what the composition costs over the blocks it
composes: `pfd_cp`'s bbox minus the `cp` bbox inside it was **9,219 µm²**; it
is now **1,035 µm²** — four trunk rows and nothing else. `pfd` itself now
costs zero block area. **−88.8 % of this level's own additive cost**, which
is what "fold the block and route its track band over its own cells" could
be worth once the 53 tracks it does not own are excluded from the claim.

**The residual is sized, and it is below this level.** Post-fold, the gap
between `pfd_cp` as drawn (26,665 µm²) and its re-derived ceiling
(16,921 µm²) is **9,744 µm², 36.5 % of the block**, living entirely inside
`cp_output_stage`/`cp_array`/`cp_dumpbuf`: `cp_output_stage`'s glue bus gives
each of 14 nets a dedicated track where the interval graph's own clique
number is 9, and `cp_dumpbuf` spends 25.87 µm of its 37.07 µm height on a
band whose 10 tracks pack into 7.50 µm. That is one change across
`cp_array._route_side` rippling through four committed GDS artifacts with
their own DRC and LVS claims, so it is filed as **#469** rather than folded
in — the same split #458 got out of #454, per §5.5's own one-lever-per-PR
discipline.

**§5.5's 1.35× ceiling should now be read as optimistic, and §5.9's 1.54×
with it.** Both are built from the same flat-track-census premise that this
block's execution just falsified, and `divider_chain`'s own 43-track census
is flat over the same kind of hierarchy. Re-running §5.9's table with
`pfd_cp`'s row at its achieved figure rather than the ceiling it will not
reach:

| | Sum | After ×1.25 | vs 0.15 mm² |
|---|---|---|---|
| As drawn | 218,631 µm² | 273,289 µm² | 1.82× |
| Every remaining lever at its ceiling (`pfd_cp` spent, counted as-drawn; `lock_detector` un-levered) | **197,076 µm²** | **246,345 µm²** | **1.64×** |

This is a *worse* projected floor than §5.9's 1.54×, and the movement is
information, not a regression: the block moved 8,616 µm² in the right
direction while the projection moved 0.10× in the wrong one, because 11,813
µm² of the projection was a ceiling that has now been measured as
unreachable. Whether #458's own ceiling survives contact the same way is not
claimed here — it is the same class of estimate, and #456 is where that has
to be settled, not this section.

**`spec/pll.md#area` is still not amended, and #456's precondition is still
not met.** #456 is blocked on #454 and #455; #454 landed at §5.8 and #455
lands here, so the *named* blockers are now clear — but what #456 needs is a
measured floor, and the residual levers on `pfd_cp` (above), `divider_chain`
(#458) and `lock_detector` (unnamed) are all unexecuted. What §5.5 said about
not amending a ratified spec row on an estimate applies unchanged, and this
revision is the second piece of direct evidence that these estimates run
optimistic.

**DRC/LVS re-verified, not assumed.** `pfd_cp` is DRC clean (0 violations) on
the `main` deck in both the default *and* the `--offgrid` signoff-grade run,
and LVS-matched against its own unchanged reference netlist (92/92 nets,
168/168 devices, the 13 declared boundary ports) — the claims #386 and
#448/#452 established, re-proved against the moved geometry rather than
inherited. `netcheck.check_gds()` reports 76 nets, no short, no split.
`cp` is DRC clean and `netcheck`-clean at its new height. The whole
`layout/tests` suite (719 tests) passes, including
`test_gds_reproducibility.py`, which rebuilds all 26 committed block GDS
files — so `pfd`, `cp_output_stage`, `cp_array`, `cp_dumpbuf` and the
`cp_leg_*`/`pfdcp_inv` leaves are proven *unchanged* rather than assumed to
be.

### 5.11 Revision: the spec row is amended, and the overrun series ends at a measurement (issue #456, DR-016)

**Status: the target is now ≤ 0.30 mm² and the block meets it at 0.2733 mm².**
This is the end state §5.5 named and §5.5, §5.8, §5.9 and §5.10 each declined to
write — "**`spec/pll.md#area` is still not amended, and #456's precondition is
still not met**" — because each of them was looking at a projection. The two
sized levers (#454, #455) are now spent and DRC/LVS-clean, so the total is a
measurement, and the decision record is **DR-016**
(`spec/decision-records/DR-016-area-budget-amended-on-measured-floor.md`).
**No geometry changes in this revision**: nothing under `layout/pll_top/`, no
committed GDS, no generator, no deck verdict is touched. What changes is the
number the fail-loud clause fires against.

Re-derived from committed geometry at `origin/main` @ `62ceb087` by
`python3 layout/run_pv.py area`, not from any estimate — and identical to
§5.10's table, because the committed `layout/evidence/area-audit/area-audit.md`
was already current:

| Block | as-drawn | Basis |
|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | DR-006 / §3 — still a calculation; no loop-filter layout exists |
| `vco_block` | 31,826 µm² | committed GDS |
| `pfd_cp` | 26,665 µm² | committed GDS (folded at §5.10/#455) |
| `divider_chain` | 92,618 µm² | committed GDS (packed at §5.8/#454) |
| `lock_detector` | 30,586 µm² | committed GDS (trim network drawn at §5.9/#449) |
| **Sum** | **218,631 µm² (0.2186 mm²)** | |
| **After §5's ×1.25** | **273,289 µm² (0.2733 mm²)** | **1.82× the draft 0.15 mm²; 91.1 % of the amended 0.30 mm²** |

**Why 0.15 mm² is unreachable, as three measured bounds rather than one
projection.** DR-016 §Context carries the full arithmetic; the shape of it is
that each bound is tighter than the last and none reaches the draft target:

| Bound | Sum | After ×1.25 | vs 0.15 mm² |
|---|---|---|---|
| As drawn | 218,631 µm² | 273,289 µm² | **1.82×** |
| Every remaining named lever at its geometric ceiling | 143,955 µm² | 179,944 µm² | **1.20×** |
| **Every Metal2 track routed at zero area cost** | **136,141 µm²** | **170,176 µm²** | **1.13×** |

The third is the one that settles it. Strike routing entirely and what is left
is each block's drawn device bands — `width × device band`, which is invariant
under folding, since a fold halves the width and doubles the band — plus the
loop filter: 31,654 + 16,921 + 34,681 + 15,949 + 36,936. Every lever this
record has ever named or sized, spent or unspent, is a Metal2-band lever, so
**1.13× is a bound on all of them at once.**

Two terms carry it, and §5.5 identified both correctly: the loop filter
(36,936 µm², set by DR-006's C1/C2 *capacitance* at 3.988 fF/µm² — a
loop-dynamics change, not a layout one) and `vco_block` at its ceiling
(31,654 µm², whose height *is* its 183.48 µm device band against a 1.00 µm
no-device band, its 60.8 % whitespace being the §1 guard-ring and 15 µm
tap-pitch spacing the foundry deck requires). 68,590 µm² between them — **57.2 %
of the 120,000 µm² a 0.15 mm² row allowed**, for two of five blocks.

**§5.9's and §5.10's projections carried a stale `divider_chain` ceiling, and
the correction moves the projection the *other* way.** §5.9 reached 185,263 µm²
as `162,145 − 7,468 + 30,586` — #442's whole-chip ceiling sum with
`lock_detector`'s row swapped — which (a) inherits `divider_chain`'s
**pre-#454** ceiling of 72,142 µm², computed on the 73-track / 100.29 µm block
§5.8 replaced with a 43-track / 70.29 µm one, and (b) subtracts `lock_detector`'s
*as-drawn* 7,468 µm² where that sum contained its 6,562 µm² ceiling, a 906 µm²
double-count. §5.10's 197,076 µm² is §5.9's figure plus 11,813 µm², so it
inherits both. Re-derived from the current audit — `max(packed-track floor,
device band) × width`, the same rule #442 defined — the ceiling is 143,955 µm²
and **1.20×, not 1.64×**. This is recorded because the direction is inconvenient
for the amendment: the projected floor is *better* than this record has been
carrying, and it is still over.

**The amendment, and what its margin is for.** `spec/pll.md#area` and summary
table row 15 now read **≤ 0.30 mm²**. That is the measured 273,289 µm² carrying
§5's ×1.25 overhead factor up to **×1.372** before the row fails — margin sized
to the one term in the product that is *not* measured, since no assembled
`pll_top` GDS exists (#17). Equivalently: ≤ 240,000 µm² of block footprint
against the 218,631 µm² drawn, **8.9 %**. It is not an allowance for block
growth, and DR-016 was deliberately **not** set at either projected bound above
— those are estimates of the class §5.8 and §5.10 each measured delivering
65.9 % and 42 % of its sizing when actually built.

**This is not the end of area reduction, and the row can still go down.** Three
levers remain open and unexecuted: **#458** (`divider_chain`'s residual
band-over-cells — the 7,814 µm² between the 1.20× and 1.13× bounds above, and
the only block where the two differ), **#469** (`cp_output_stage`'s glue bus and
`cp_dumpbuf`'s band inside `pfd_cp`, 9,744 µm² / 36.5 % of that block, §5.10),
and an **unnamed** lever against `lock_detector`'s 65.5 % whitespace (§5.9 left
it unnamed rather than guess a number, and this revision keeps that discipline).
Each landing is grounds for a successor record amending the row *downward*, on
the same standard: measured, from committed geometry, DRC/LVS-clean.

**Still not a DRC/LVS regression, trivially.** No geometry changed. The
`layout/tests` suite passes unchanged, `area-audit.md` is byte-identical to
what is committed, and every block's signoff status is what §5.10 left it.

### 5.12 Revision: the first of §5.11's three open levers is spent, and its ceiling was wrong for a third, new reason (issue #469)

§5.10 closed by sizing the 9,744 µm² residual it had measured below
`pfd_cp`'s own level, and named the larger half: `cp_output_stage`'s glue bus
gives each of 14 nets a dedicated Metal2 track "where the interval graph's own
clique number is 9", worth 3.75 µm of block height (≈1,290 µm²). §5.11 carried
it forward as **#469**, one of the three reduction levers it left open once
DR-016 had amended the row, and it is the first of those three to land. That
lever is now spent. Full record and reproduction:
`layout/evidence/pfd-cp-layout/PROOF-469-glue-bus-packing.md`.

**This revision is written against the amended row, not the draft one.**
`spec/pll.md#area` has read **≤ 0.30 mm² (300,000 µm²)** since DR-016 (#456,
§5.11); every figure below is stated against it, with the draft 0.15 mm² kept
alongside only because §5.11's three bounds are quoted in those terms.
**259 µm² is not grounds for the successor record §5.11 described.** That
standard is for a landing that moves the measured total materially, and 0.1 %
of the block sum is not one — the row stays at **≤ 0.30 mm²**, and what moves
is the measurement under it (0.2733 → 0.2730 mm², 91.1 % → 91.0 % of the row;
the overhead factor the row's margin is sized to rises ×1.372 → ×1.374).

`cp_array._route_side()` — the router `cp_array`'s two array channels and
`cp_output_stage`'s glue bus all share — now takes a `bus_reach` argument, and
a caller that supplies it gets `cp_array.pack_tracks()` (the left-edge
interval-graph track assignment `divider_chain` has carried since §5.2/#341
and reused one level down at §5.8/#454) instead of `NetTracks`. The glue bus
is the one call site that supplies it. No device, riser column, link column,
pin or pad moved; the only quantity that changed is which `track_y` each glue
net's bus sits at.

| Block | §5.11 (DR-016) | §5.12 | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 26,665 µm² | **26,406 µm²** | **−259 µm², −1.0 %** |
| `divider_chain` | 92,618 µm² | 92,618 µm² | — |
| `lock_detector` | 30,586 µm² | 30,586 µm² | — |
| **Sum** | 218,631 µm² (0.2186 mm²) | **218,372 µm² (0.2184 mm²)** | −0.1 % |
| **After §5's ×1.25** | 273,289 µm² (0.2733 mm²) | **272,965 µm² (0.2730 mm²)** | |
| **vs the amended ≤ 0.30 mm² row** | 91.1 %, **met** | **91.0 %, met** | margin on the block sum 8.9 % → **9.0 %** |
| **vs the draft 0.15 mm² target** | **1.82×** | **1.82×** | |

**The projected floor does not move at all, which is the honest summary of a
0.1 % block-level saving.** §5.11 re-derived the ceiling projection §5.9 and
§5.10 had been carrying: 143,955 µm², **179,944 µm² after the ×1.25, 1.20×**
the draft target. `pfd_cp` enters that sum at its 16,921 µm² *device-band*
ceiling either way, and this is a routing-track lever — every routing track is
already struck from that bound — so 143,955 µm² and §5.11's tighter
zero-routing 136,141 µm² (1.13×) are both unchanged by it. What narrows is the
gap between drawn and ceiling: `pfd_cp` was 9,744 µm² above its own ceiling and
is now 9,485 µm². (This section was first drafted against §5.10's 197,076 µm²
projection, which would have moved 197,076 → 196,817 µm² and stayed at 1.64×;
§5.11 established that that figure carried `divider_chain`'s pre-#454 ceiling
and a 906 µm² double-count, so the corrected bound above is the live one and
the conclusion is the same either way.)

**The lever returned 20 % of its sizing, and the shortfall is in the ceiling
again — for a reason §5.10 did not have.** §5.10's own correction was that a
*flat* track census over five hierarchy levels over-states what any one module
can pack. This one is narrower and new: **a census over a single level's own
bus spans over-states it too, when the level above draws on the same tracks.**
Six of the glue bus's fourteen nets (`VDD`, `VSS`, `B0`, `B0B`, `B1`, `B1B`)
are shared with *both* array polarities, so `cp_output_stage` extends each of
them to a left link column **and** a right one — each is live across the whole
block and can share a track with nothing. Counting those extensions, the
band's clique number is **13**, not 9:

| | clique | achievable tracks |
|---|---|---|
| bus spans only (what §5.10 measured) | 9 | 9 |
| bus spans **+ the level above's own link extensions** | **13** | **13** |
| as drawn before | — | 14 |

`pack_tracks()` achieves 13 — the clique number, provably minimal for an
interval graph — so the shortfall is not slack in the assignment. 14 → 13
tracks is 0.75 µm of `cp_output_stage`, which `cp` and then `pfd_cp` inherit
whole: 77.30 → **76.55 µm**, 26,665 → **26,406 µm²**.

**The other two candidate bands were measured, not skipped.** `cp_array`'s own
N and P channels are 9 nets each. The P channel packs 9 onto 9 — *no* saving
at all — and the N channel 9 onto 7, but the N channel's top sits 2.11 µm
below `cp_array.footprint[3]`, which the P channel sets, so it buys nothing
either. The generalisation is now stated in `cp_array.py`: **a band every one
of whose nets is reached by a parent from the same side cannot be packed**,
because every such net's extent runs out to that side's link-column region.
Packing the N channel anyway would have changed a fifth committed GDS with its
own DRC claim for zero block area, so it is not done.

**The `cp_dumpbuf` fold (§5.10's second residual target) is decided and
closed, not deferred.** #469 required the two targets to be decided together
because they are mutually exclusive, and the arithmetic resolves it: folding
`cp_dumpbuf`'s 25.87 µm routing band over its own devices wins height inside a
block that is already ~29 µm shorter than the `cp_output_stage` beside it, so
`cp`'s bbox does not move at all; it only pays in combination with relocating
`cp_dumpbuf` at `cp` level, and the band that would need is exactly where
§5.10 put `pfd` — worth 8,616 µm², 33× what this could be. It is *foreclosed*
by the fold that already landed, which is a property of the geometry rather
than of scheduling.

**What the residual is now, and where the next lever actually is.** The gap
between `pfd_cp` as drawn and its 16,921 µm² ceiling is 9,485 µm² (35.9 % of
the block), and after this pass its composition is measured rather than
estimated: 9.75 µm of glue band (at its clique number), 6.75 µm of array
channels (parent-reached from one side), 4.50 µm of `cp`'s backbone band and
3.00 µm of this block's trunk band (both all-spanning, §5.10), over 49.05 µm
of device bands. **No routing-track lever remains in this block.** The one the
measurement does expose is a *placement* lever: 7 of the glue band's 13 tracks
are a local clique caused by `cp_output_stage` putting all four glue inverters
in one row at its right-hand end, so `DN`/`DNB`/`UP`/`UPB` each run most of
the block's width from a switch on the left to an inverter on the right.
Interleaving the inverters with the switches they drive would shorten all four
— filed as **#473** per §5.5's one-lever-per-PR discipline rather than folded
in here, and filed with its own "measure the resulting clique before building,
and close it with that number if it does not improve" precondition, because
the 6 full-width nets floor it at 6 + whatever local clique survives.

**This is the third consecutive measured over-estimate in the same family, and
it should be read as a property of the estimating method.** §5.8 (#454), §5.10
(#455) and now §5.12 each sized a track-packing lever from a census and each
recovered materially less, for a different structural reason every time. §5.5's
1.35× and §5.9's 1.54× projections rest on that method; §5.10 already advised
reading them as optimistic and this adds a third data point rather than a new
caveat. **What it does *not* change is the spec row**, and that is the point of
having amended it on a measurement: DR-016 was written on the measured post-lever
total rather than on any of these projections (§5.11), so a third over-estimate
in the estimating method leaves the ≤ 0.30 mm² row exactly where it is. Of
§5.11's three open reduction levers this closes one — there is now no unexecuted
routing lever left in `pfd_cp` — and leaves `divider_chain` (#458) and the
unnamed `lock_detector` lever where §5.11 left them, alongside the new
*placement* lever #473 above.

**DRC/LVS re-verified on every changed block, not assumed.** `cp_output_stage`
and `cp` are DRC clean (0 violations, `main`); `pfd_cp` is DRC clean in both
the default *and* the `--offgrid` signoff-grade run and LVS-matched against its
own unchanged reference netlist (92/92 nets, 168/168 devices, the 13 declared
boundary ports). `netcheck.check_gds()` reports no short and no split on all
three (18 / 22 / 76 nets). The whole `layout/tests` suite (746 tests) passes,
including `test_gds_reproducibility.py`, which rebuilds all 26 committed block
GDS files — so `cp_array`, `cp_dumpbuf`, `pfd` and the `cp_leg_*`/`pfdcp_inv`
leaves are proven *unchanged* rather than assumed to be. `#448`'s inherited-label
regression was watched for specifically: all four
`_canvas.Canvas.clear_inherited_labels()` call sites are untouched, this change
draws no label, and the LVS match is the end-to-end proof.

### 5.13 Revision: §5.5's lever 3 is spent in full — 1.82× to 1.51×, and 75.5 % of the amended row (issue #458)

**Status: still over the 0.15 mm² draft target, by 1.51× rather than 1.82×;
comfortably inside the ratified ≤ 0.30 mm² row, at 75.5 % of it rather than
91.0 %.** This is the fourth sized lever spent, and the one §5.5 named as
"lever 3" and §5.8 took only half of ("§5.5's lever 3 survives, reduced"). Full record and reproduction:
`layout/evidence/divider-chain-layout/PROOF-over-device-rows.md`.

**This section is stated against §5.12, not §5.11.** #474 (issue #469) landed
`cp_output_stage`'s glue-bus packing on `main` while this work was in review,
and this revision is measured on the rebased tree that carries it — so
`pfd_cp` enters every table below at §5.12's **26,406 µm²**, not §5.11's
26,665 µm², and the whole-chip figures are the two levers *together*. The
`divider_chain` delta itself is untouched by that rebase: the two blocks share
no geometry and `area-audit.md` regenerates both from their own committed GDS.

Both of `divider_chain`'s Metal2 track populations — the top-level one §5.2
packed and the `div23_cell` one §5.8 packed — are now assigned by
`devgen.pack_tracks_over_devices()` instead of `devgen.pack_tracks()`. A track
is placed at the lowest 0.75 µm step whose drawn rectangle clears an explicit
obstacle map (every riser's Via1/Metal2 landing square, plus every placed
`div23_cell` instance's own interior Metal2, read recursively back off the
canvas), rather than at `base_y + i·pitch` in a band above the device rows.
`route_net()` and `_riser()` draw exactly what they always drew; only which
`track_y` values are legal changed.

| Block | §5.12 | §5.13 | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 26,406 µm² | 26,406 µm² | — (#469 spent at §5.12; no routing lever left) |
| `divider_chain` | 92,618 µm² | **55,329 µm²** | **−37,289 µm², −40.3 %** |
| `lock_detector` | 30,586 µm² | 30,586 µm² | — (unnamed lever, §5.9) |
| **Sum** | 218,372 µm² (0.2184 mm²) | **181,083 µm² (0.1811 mm²)** | −17.1 % |
| **After §5's ×1.25** | 272,965 µm² (0.2730 mm²) | **226,354 µm² (0.2264 mm²)** | |
| **vs the 0.15 mm² draft** | 1.82× | **1.51×** | |
| **vs the ratified ≤ 0.30 mm² row (DR-016)** | 91.0 % | **75.5 %** | |

Every figure in that table is regenerated, not carried forward: `python3
layout/run_pv.py area --out layout/evidence/area-audit/area-audit.md` on the
rebased tree reproduces the committed audit byte-for-byte, and the §5.13
column is its four block rows plus DR-006's loop-filter calculation.

The gap to close against §5's 120,000 µm² pre-overhead budget goes from
98,631 µm² (§5.11) / 98,372 µm² (§5.12) to **61,083 µm²**. `divider_chain`
stops being the chip's dominant block: at 55,329 µm² it is 1.5× the loop
filter rather than 2.5× it. The overhead factor the amended row's margin is
sized to rises ×1.374 → **×1.657**, and the margin on the block sum against
the row's implied ≤ 240,000 µm² goes 9.0 % → **24.6 %**.

**This is the first lever in the series to beat the 20 %–66 % band the
previous three landed in: 74.4 % of its own ceiling.** #458 sized itself at
1317.66 × 32.25 µm = 42,494 µm² (a 50,124 µm² saving); the outcome is
1317.66 × 41.99 µm = 55,329 µm² (37,289 µm²). The residual 12,835 µm² is
9.74 µm of height carrying the nets whose x-extent crosses a `div23_cell`
instance's own interior — they cannot drop into the channel the macro's own
tracks now occupy, and they cannot cross on Metal3 either, because the macro's
own risers are vertical Metal3 through exactly that span. Closing it needs a
fourth routing layer or a macro that reserves a through-corridor for its
parent, neither of which is a `track_y` change.

**Correction: §5.11 mis-sized this lever, and the direction is again
inconvenient.** §5.11's closing list describes #458 as "the 7,814 µm² between
the 1.20× and 1.13× bounds above". That is the residual *after* #458 reaches
its ceiling, not the lever: §5.11's own 1.20× bound already valued
`divider_chain` at its 42,494 µm² post-#458 ceiling, so the lever inside that
bound is the 50,124 µm² this revision took 74.4 % of. The 7,814 µm² is real
but unnamed — it is the distance from the ceiling to the device-band floor,
and this revision leaves 20,648 µm² of it rather than 7,814, because it landed
short of the ceiling. The 1.20× and 1.13× *bounds* themselves are unaffected;
only the sentence attributing the difference to #458 was wrong.

**#442's `max(packed-track floor, device band) × width` ceiling no longer
bounds this block, because this change is what breaks its premise.** That rule
assumes tracks occupy an exclusive band. `area-audit.md` now reports 53
distinct Metal2 tracks for `divider_chain` — *up* from 43, since the same nets
sit at more distinct y values once they are no longer all on one band's pitch
grid — for a nominal 39.75 µm "packed floor" against the 15.67 µm of no-device
band actually drawn. The formula's output is now larger than the geometry it
describes. For this block the honest floor is the device band alone,
26.32 × 1317.66 = 34,681 µm², i.e. DR-016's 1.13× term; the block is now
20,648 µm² above it rather than 57,937 µm². **The rule is still correct for
the other three blocks**, none of which routes over its own device rows, so
nothing about §5.11's whole-chip bounds is withdrawn — but a future
whole-chip ceiling sum must take `divider_chain`'s term from the device band,
not from the formula.

**`spec/pll.md#area` is not amended here, and does not need to be.** DR-016
ratified ≤ 0.30 mm²; this revision moves the measured total further *under*
that row, which requires no amendment and is not a spec change. DR-016's own
closing paragraph invites a successor record amending the row downward once a
remaining lever lands — that is a decision record's judgement (how much margin
the unmeasured ×1.25 top-level overhead still warrants with no assembled
`pll_top` GDS), not a layout PR's, and is left to one.

**The cost of that, named rather than left for a reader to trip over**:
`spec/pll.md#area`'s *measured* table reproduces DR-016's block-by-block
figures, so it now lags the committed geometry by **two** levers, not one —
#469 (§5.12) did not refresh it either, for the same reason. It still reads
`pfd_cp` at 344.98 × 77.30 µm / 0.0267 mm², `divider_chain` at
1317.66 × 70.29 µm / 0.0926 mm², the sum at 0.2186 mm² and the total at
0.2733 mm² / 91.1 % / 1.82×. Those are DR-016's measurement as ratified, not a
claim about the GDS committed today. Refreshing them is the same act as
amending the row they sit under and goes through `spec/` with a decision
record (CLAUDE.md) — filed as **#476**, whose scope covers both lagging levers.
Until that lands, **this section and
`layout/evidence/area-audit/area-audit.md` are the current measurement**, and
`area-audit.md` is regenerable from the committed GDS by `python3
layout/run_pv.py area` by anyone who wants to check.

**[Discharged at §5.15 (#476, DR-017).]** #476 has landed: `spec/pll.md#area`'s
measured table now carries the committed GDS's own figures, so the paragraph
above is history rather than a live caveat. The row it sits under is unchanged
at ≤ 0.30 mm².

**DRC/LVS re-verified, not assumed.** Both changed blocks are rebuilt and
re-run on `KLayout 0.28.16`, this repo's pinned version, so #360's
false-mismatch caveat does not arise: `div23_cell` and `divider_chain` are
each DRC clean (0 violations) **and** DRC clean under `--offgrid` **and** LVS
matched at the new geometry. Both `reference_netlist()` outputs are
byte-for-byte unchanged; `div23_cell`'s seven pin locations and x-extent are
unchanged; #295's six-identical-instances criterion is re-proved
geometrically at the new footprint; and the minimum positive edge-to-edge gap
on Metal2 and on Metal3 is 0.3100 µm in both cells both *before and after* the
change — the tracks moved, their closest approach did not. Re-verified a
second time on the rebased tree that carries #469: identical verdicts, as
expected — the two changes share no cell, and `pfd_cp`'s own committed GDS is
byte-identical to what #474 merged.

**§5.11's three open levers are now two spent and one open.** #469 closed at
§5.12 and #458 closes here; what remains from that list is the **unnamed**
`lock_detector` lever against its 65.5 % whitespace, plus the *placement*
lever §5.12 filed as **#473**. Neither is sized here, on §5.11's own
discipline of not guessing a number.

### 5.14 Revision: the *placement* half of §5.12's band — 1.51× to 1.50× (issue #473)

**Status: still over the 0.15 mm² draft target, by 1.50× rather than 1.51×;
inside the ratified ≤ 0.30 mm² row at 75.1 %.** This is the fifth sized lever
spent, the second of the two §5.12 exposed in `cp_output_stage`'s glue band,
and the smallest of the five. Full record and reproduction:
`layout/evidence/pfd-cp-layout/PROOF-473-glue-inverter-interleave.md`.

§5.12 packed that band onto 13 Metal2 tracks and proved 13 was its clique
number — the minimum *for a track assignment*. It also decomposed the 13 as
**6 structurally full-width nets + a local clique of 7**, and named the 7 as a
placement artifact: `cp_output_stage` grouped all four glue inverters past the
right-hand end of its single device row, so `DN`, `DNB`, `UP` and `UPB` each
ran most of the block's width from a switch gate to an inverter (237.6 µm of
span between them). Filed as #473 under §5.5's one-lever-per-PR discipline,
and filed with the caveat that it might measure out at zero.

It does not. Each steering pair's own inverter now sits immediately before the
switch group whose gates it feeds (`cp_output_stage.ROW_ORDER`), the four nets
come to 66.4 µm of span, and the band packs onto **10** tracks.

| Block | §5.13 | §5.14 | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 26,406 µm² | **25,630 µm²** | **−776 µm², −2.9 %** |
| `divider_chain` | 55,329 µm² | 55,329 µm² | — (#458 spent at §5.13) |
| `lock_detector` | 30,586 µm² | 30,586 µm² | — (unnamed lever, §5.9) |
| **Sum** | 181,083 µm² (0.1811 mm²) | **180,307 µm² (0.1803 mm²)** | −0.4 % |
| **After §5's ×1.25** | 226,354 µm² (0.2264 mm²) | **225,384 µm² (0.2254 mm²)** | |
| **vs the 0.15 mm² draft** | 1.51× | **1.50×** | |
| **vs the ratified ≤ 0.30 mm² row (DR-016)** | 75.5 % | **75.1 %** | |

Every figure is regenerated, not carried forward: `python3 layout/run_pv.py
area --out layout/evidence/area-audit/area-audit.md` reproduces the committed
audit, and the §5.14 column is its four block rows plus DR-006's loop-filter
calculation. The gap to §5's 120,000 µm² pre-overhead budget goes 61,083 →
**60,307 µm²**; the top-level overhead factor the amended row's margin still
holds to goes ×1.657 → **×1.664**.

**Ten tracks is a floor that is structural, not algorithmic, and this is the
first section in the series able to say so exhaustively.** `glue_riser_x()` is
a pure-arithmetic twin of the riser set `cp_output_stage.build()` draws — the
same x values, pinned to the builder's own output by a test — so a candidate
row order can be costed with the router's own `cp_array.pack_tracks()` with no
geometry drawn. All **25,920** orderings that keep both switch groups
contiguous were costed that way *before* any layout code changed, per the
issue's own "measure before building" precondition: 1,260 reach 10, none goes
below it, and the as-built order before this change is one of the 6,120 at 13.
The sweep is a unit test, so "10 is the floor" is re-derived on every run.

Why 10 and not less: `VOUT` (`MSWDN`'s drain to `MSWUP`'s) and `VDUMP`
(`MDMPDN`'s to `MDMPUP`'s) each tie the charge pump's N group to its P group
by definition and are live everywhere between them; `UPT` runs from the P
group out to its own right-hand link column; and at whichever P device is not
the one bounding `VOUT`, one of `UP`/`UPB` is live. Six full-width nets plus
those four. No placement removes any of them — which also means **this block's
glue band is finished as a lever**: both halves are spent and what remains is
structure.

**Both levers in this band landed in the same 20 %–66 % band as the rest of
the series, and the pair together are still small.** #455 sized the glue-bus
lever at 14 → 9 tracks (3.75 µm, ≈1,290 µm² of `pfd_cp`); the outcome across
#469 and #473 together is 14 → 10 (3.00 µm, 1,035 µm²), **80 % of that
sizing** — and the 20 % shortfall is the six full-width nets #455's
bus-span-only census could not see. Read as one lever, this is the closest any
of the five has come to its own ceiling; read as the two PRs it actually was,
#469 took 20 % of it and #473 the other 60 %.

**A third failure mode is now catalogued for this family, and it is a
placement one.** §5.8, §5.10 and §5.12 each recorded a track census that
over-stated what packing could recover, for a different structural reason each
time (a flat census over five levels; a census over one level's own bus spans
ignoring its parent's; the parent's own link extensions). This section records
the converse: a clique number that is *correct* and still not a floor, because
a clique is a property of the intervals, and where the intervals end is a
placement decision. "13 is the provable minimum" was true and was about the
wrong graph. Anyone reading a `pack_tracks()` result in this repository as a
floor should check what set the endpoints first.

**What is not done, and why it is not sized.** Dropping an inverter *inside* a
switch group — which would shorten `DNB` and `UP`, the two nets that still
span their own group because they gate two devices at its opposite ends — is
rejected by a new build-time invariant, `check_row_groups()`, not by
preference: each group carries one `_tap_strip()` across its whole span (whose
comp, implant and contacts would be drawn straight through an inverter's own
tap, which sits in the identical y band) and the P group one n-well (which
would enclose an interleaved inverter's NMOS). Both are defects a
spacing-based DRC deck cannot report. Splitting the strips and the well per
contiguous run is a real, bigger change; it is not sized here, because the
clique arithmetic above shows it could not take the band below 10 anyway.

**`spec/pll.md#area` still lags, now by three levers.** #476 already covers the
#469 and #458 lag; this section adds a third to the same list rather than
opening a new one. `spec/pll.md`'s measured table still reads DR-016's figures
(`pfd_cp` at 344.98 × 77.30 µm / 0.0267 mm², total 0.2733 mm² / 91.1 % /
1.82×), which are that decision record's measurement as ratified and not a
claim about the GDS committed today. Until #476 lands, this section and
`layout/evidence/area-audit/area-audit.md` are the current measurement, and
the audit is regenerable from the committed GDS by anyone who wants to check.

**[Discharged at §5.15 (#476, DR-017).]** All three lagging levers — #469,
#458 and this section's #473 — are now carried by `spec/pll.md#area`'s own
measured table, on the same `area-audit.md` figures. The row is unchanged at
≤ 0.30 mm².

**§5.11's three open levers are now all spent or unnamed.** #469 closed at
§5.12, #458 at §5.13, and the placement lever §5.12 filed as #473 closes here.
What remains from that list is the **unnamed** `lock_detector` lever against
its 65.5 % whitespace — still unsized, on §5.11's own discipline of not
guessing a number. The one class of lever this record can see that has not
been tried on `pfd_cp` is §5.13's: routing a band *over* its own device rows
rather than above them. It is not sized either, and the reason is arithmetic
rather than reticence — `cp_output_stage`'s device row is 1.3 µm tall against
`divider_chain`'s 26.32 µm, so the obstacle-free y that made that lever pay
there barely exists here.

### 5.15 Revision: the spec catches up and the row is *held* — 0.2254 mm², 75.1 % of ≤ 0.30 mm² (issue #476, DR-017)

**Status: no geometry changes here at all.** This is the spec-side counterpart
of §5.12 – §5.14: the three levers those sections landed are now carried by
`spec/pll.md#area`'s own measured table, and the ratified row above it is
**held at ≤ 0.30 mm²** rather than amended down. The record is
`spec/decision-records/DR-017-area-row-held-at-0.30-on-the-refreshed-measured-floor.md`;
the lag caveats at the end of §5.13 and §5.14 are discharged by it.

**What the spec now says, and what it said before** — every figure re-derived
from the committed GDS at `main` @ `8c6cb7f3` by `python3 layout/run_pv.py
area`, i.e. from `layout/evidence/area-audit/area-audit.md`, not copied from
any of the sections above:

| Block | §5.11 (DR-016, what the spec carried) | §5.15 (what the spec carries now) | Delta |
|---|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 µm² | 36,936 µm² | — (a calculation, not a layout) |
| `vco_block` | 31,826 µm² | 31,826 µm² | — |
| `pfd_cp` | 26,665 µm² | **25,630 µm²** | **−1,035 µm², −3.9 %** (§5.12 + §5.14) |
| `divider_chain` | 92,618 µm² | **55,329 µm²** | **−37,289 µm², −40.3 %** (§5.13) |
| `lock_detector` | 30,586 µm² | 30,586 µm² | — |
| **Sum** | 218,631 µm² (0.2186 mm²) | **180,307 µm² (0.1803 mm²)** | **−38,324 µm², −17.5 %** |
| **After §5's ×1.25** | 273,289 µm² (0.2733 mm²) | **225,384 µm² (0.2254 mm²)** | −17.5 % |
| **vs the ratified ≤ 0.30 mm² row** | 91.1 %, met, 8.9 % margin | **75.1 %, met, 24.9 % margin** | the row **does not move** |
| **vs the draft 0.15 mm² target** | 1.82× | **1.50×** | |

**Why the row is held, in one sentence** (DR-017 Decision 1): a margin sized to
an uncertainty does not shrink because the measurement it sits on top of
shrank. DR-016 Decision 2 defined this row's margin as covering §5's ×1.25
top-level overhead and nothing else, and that factor is identical today — same
ROM multiplier, same absent `pll_top` (#17), same absent loop-filter layout.
All three levers since were Metal2 routing-track levers inside already-drawn
blocks; not one of them measured the overhead or drew the loop filter. What a
≤ 0.25 mm² row would have bought, and why DR-017 rejected it: it holds the
measured total to an overhead of ×1.386 — 11 % above a ROM figure nobody has
ever checked — so a first `pll_top` measurement at ×1.4 would falsify it with
zero block growth, and the repair would be an *upward* re-amendment. The row as
held goes to **×1.664**.

**DR-016 Decision 4's trigger is replaced, and this is the section that shows
why it needed to be.** That decision made any lever landing grounds for a
downward re-amendment; §5.12 then had to argue in prose that its own 259 µm²
(0.1 % of the block sum) was "not grounds for the successor record §5.11
described", and §5.14's 776 µm² (0.4 %) is the same case. DR-017 Decision 3
narrows it to the two events that actually shrink the uncertainty: an assembled
`pll_top` (#17) turning ×1.25 into a measurement, or the loop filter being
drawn so its 36,936 µm² — **20.5 % of the block sum**, the largest single term
in it — stops being DR-006's device sum ×1.15. Block-level levers refresh the
measured table; they do not move the row.

**One arithmetic consequence of §5.13, recorded here because the spec now
states it.** DR-016 carried two bounds below the as-drawn total — 143,955 µm²
(every named lever at its geometric ceiling, 1.20×) and 136,141 µm² (all Metal2
routing free, 1.13×). #458 spent exactly the 7,814 µm² of `divider_chain` that
separated them, and §5.13 established that the `max(packed-track floor, device
band) × width` ceiling no longer applies to a block routing over its own device
rows. Re-derived with that correction, the two bounds **converge**:
31,654 + 16,921 + 34,681 + 15,949 + 36,936 = **136,141 µm²**, ×1.25 →
170,176 µm² (**0.1702 mm², 1.13×**). DR-016 Decision 3 — that 0.15 mm² is not
reachable — therefore survives on a *single* bound rather than two, and it is
the one that assumes all routing is free.

**Nothing in `layout/` changes and nothing is re-verified, because nothing
moved.** No generator, no committed GDS, no DRC or LVS run, and neither area
constant in `skeleton.py` (`AREA_BUDGET_UM2 = 300_000.0`,
`TOP_LEVEL_OVERHEAD = 1.25`) — holding the row is exactly what leaves those
untouched. `layout/evidence/area-audit/area-audit.md` was already current after
§5.14; DR-017's table *is* that file. What did change outside `spec/` is
`manifests/integrator.json`, which was one lever stale (`pfd_cp` at 26,406 µm²,
a 1.51× draft ratio) and is re-synced to the same figures, so the
machine-readable integrator view and the ratified table cannot disagree.

**The `lock_detector` lever is still open, still unnamed and still unsized** —
30,586 µm² drawn against a 15,949 µm² device-band term, 65.5 % whitespace. Per
DR-017 Decision 5 it will move the table above when it lands and will not, on
its own, move the row.

## 6. GDS skeleton

`layout/floorplan/skeleton.py` assembles a **block-placement skeleton**
implementing the layout above: one rectangle per block (loop filter, VCO,
PFD+CP, divider+lock-detector), sized to this record's area-budget
footprints (§5) and positioned per the isolation/supply-routing plan (§1–2),
plus the two real, as-drawn geometries this record can state exactly — the
loop-filter C1/C2 array footprint (§3) and the VCO's committed 22 pF decap
(§1). Every shape is drawn on the GDS `DIEAREA` layer (layer 0, datatype 0 —
confirmed by grep against every rule file in
`$PDK_ROOT/libs.tech/klayout/drc/rule_decks/*.drc` to carry **no** DRC rule
in this deck; it is used only as a boundary/reference marker, never as a
device or routing layer), so the skeleton is **necessarily** DRC-clean under
#16's flow — that is the honest characterization of what this DRC run
proves: this deck's silence about layer (0,0), not that the physical devices
inside these footprints are DRC-clean. The value of running it through
`run_pv.py drc` regardless is exercising #16's flow against a multi-block
layout instead of only the single trivial `inv_tb` cell.

**Which rectangles are now real** (this list supersedes the "they do not
exist as real geometry yet" characterization this section carried through
#17): `vco` (#293/#324), `divider_lock.divider_chain` (#310, reduced at #341
and folded at #344), `divider_lock.lock_detector` (#296), and now `pfd_cp`
(#385/#386) are the blocks' own measured as-drawn extents, and
`DIVIDER_LOCK` is sized to contain the divider-chain/lock-detector pair —
see §5.1, §5.3 and §5.4. The devices themselves are DRC-clean (and, for the
divider chain, LVS-clean) in each block's own evidence directory, not by
virtue of this skeleton's run.

**`pfd_cp`'s rectangle is real as of issue #386.** `pfd.py`, the complete
`cp` block (`cp_output_stage.py` + `cp_dumpbuf.py`, assembled at #385) and
their own bridging routing (`UP`/`DN`/`VDD`/`VSS`) are now one flat,
standalone-DRC-clean `pfd_cp` GDS matching `design/pfd_cp.sch`'s full
netlist — `layout/pll_top/pfd_cp/block.py`,
`layout/evidence/pfd-cp-layout/PROOF.md`. `skeleton.py`'s `PFD_CP` block is
now sized to that block's own measured extent rather than the 150 × 100 µm
placement-plan estimate it carried through #385 — 434.31 × 80.73 µm when
written (§5.4), 347.41 × 76.23 µm after the fold at §5.10 (#455),
347.41 × 75.48 µm after the glue-bus packing at §5.12 (#469), and
**347.41 × 73.23 µm since the glue-inverter interleave at §5.14 (#473)**. The
fold is what shifted `LOOP_FILTER`/`VCO_CORE` 86.90 µm left, without moving
the skeleton's own bounding box (`DIVIDER_LOCK`'s width still sets it);
#469's 0.75 µm and #473's 2.25 µm are height only and move nothing else.

**The committed artifact is the generator's output again, and is checked
(issue #461).** Through #398 this section's own regeneration recipe was an
ad-hoc `python3 -c "from floorplan import skeleton; skeleton.build(...)"`
one-liner, which `layout/harness/reproduce.py` could not invoke — so this was
the one committed block GDS that guard had to exclude by name, and the
committed file drifted six merges behind the placement described above
(§5.7). `skeleton.py` now exposes the same `--outdir` CLI every other
generator in this repository does, and the artifact is registered in
`BLOCKS`:

```bash
python3 -m floorplan.skeleton --outdir evidence/floorplan-skeleton   # from layout/
python3 layout/run_pv.py drc layout/evidence/floorplan-skeleton/pll_floorplan_skeleton.gds \
    --top pll_floorplan_skeleton --run-dir <run>
python3 -m harness.reproduce                                          # from layout/
```

Evidence: `layout/evidence/floorplan-skeleton/` (see `PROOF.md` there for the
DRC run's provenance and verdict).
