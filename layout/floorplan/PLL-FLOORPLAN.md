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
floorplan's area on this one device group alone — DR-006 and #10's own
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
| PFD + charge pump | 0.010–0.020 mm² | *still ROM — no assembled block yet* | — | — |
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
- **This is not a DRC/LVS regression.** Every block above is signoff-clean on
  the PDK's own decks at the footprint quoted (the divider chain additionally
  LVS-clean against `design/netlist/divider_chain.spice`). What has failed is
  the *area budget*, which is exactly the outcome the fail-loud clause was
  written to surface rather than absorb.

**The `DIVIDER_LOCK` reconciliation is closed.** #296 and #310 each deferred
sizing the shared divider/lock region to whichever landed second; #310 landed
second and did it. `skeleton.py`'s `DIVIDER_LOCK` is now sized to contain
both real footprints (2650.28 × 212.42 µm), with the two blocks stacked and
separated by a full `DOMAIN_SPACING` — they are on different supply domains
(`VDD_DIV` vs. `VDD`, §2), so sharing the region buys signal adjacency, never
a shared supply segment. The 90 × 50 µm placement-plan estimate both blocks
were nominally sized against is superseded and should not be cited again.

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
#17): `vco` (#293/#324), `divider_lock.divider_chain` (#310) and
`divider_lock.lock_detector` (#296) are the blocks' own measured as-drawn
extents, and `DIVIDER_LOCK` is sized to contain the latter two — see §5.1.
`pfd_cp` is still a §5 ROM estimate. The devices themselves are DRC-clean
(and, for the divider chain, LVS-clean) in each block's own evidence
directory, not by virtue of this skeleton's run.

Evidence: `layout/evidence/floorplan-skeleton/` (see `PROOF.md` there for the
DRC run's provenance and verdict).
