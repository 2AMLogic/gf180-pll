# DR-009: The VCO bias resistors are the high-sheet `ppolyf_u_3k` device, and the 3k poly option is a tape-out requirement

- **Status**: proposed
- **Date**: 2026-09-11
- **Decided by**: Builder agent, issue #381, drafting for operator ratification
  via PR review — the same ratification-via-PR route DR-008 records (a builder
  drafts the record on the evidence; the operator's PR approval is the
  ratifying act). Status stays `proposed` until that approval and merge.
- **Related**: #381 (this record's source issue), #378 / PR #380 (the LVS
  device-class fix that made the discrepancy visible), DR-001 Decision 3 (the
  constant-gm bias mandate and the PDK primitive menu this record narrows),
  DR-006 Decision 1 (the loop filter's *unmarked* `ppolyf_u` resistor, which
  this record does not touch), `sim/vco-bias-current/` (the measurement),
  `layout/evidence/vco-layout/PROOF-381-high-rs-resistor.md`

## Context

`design/netlist/vco.spice` declares the VCO bias generator's three resistors —
`XRCG` (the beta-multiplier reference), `XROFF` and `XRDEG` (the V→I
converter's offset and degeneration) — as **`ppolyf_u_3k`**, gf180mcu's
3000 Ω/sq high-sheet poly resistor. Every recorded `sim/` result for this block
(`vco-tuning-range` and the band map DR-003 ratifies from it, `lock-time`,
`period-jitter`, `reference-spur`, the `vdd_vco` domain current in
`spec/pll.md`'s power section) was produced against that device.

`layout/pll_top/vco/primitives.poly_resistor()` drew a different device. It
modelled the PDK pcell body `polyf_res_inst()`, which is the recipe for the
**unmarked** `ppolyf_u` class (350 Ω/sq) — it never drew GDS `(62, 0)`, the
marker both the DRC and the LVS deck use to tell the high-sheet family apart
from the unmarked one. The drawn resistors were therefore 8.3× too small:
`RCG` 2.19 kΩ instead of 18.19 kΩ, `ROFF`/`RDEG` 12.3 kΩ instead of 104 kΩ
(measured, typical/27 °C — `sim/vco-bias-current`'s witness resistors, not a
datasheet figure). Issue #378 had already corrected the *reference netlist* to
name the class the deck extracted, which made `vco_block` LVS match — on the
wrong device. Nothing in the flow could catch this: DRC passed, LVS passed, and
the schematic-level simulations never saw the layout.

Three mutually exclusive resolutions were possible, and choosing among them is
a spec decision rather than a layout fix, which is why issue #381 was filed
separately from #378 instead of being folded into it.

## Decision

**1. The VCO bias resistors are `ppolyf_u_3k`, as `design/netlist/vco.spice`
already declares. The layout is corrected to draw that device; neither the
schematic nor the drawn W/L changes.**

`primitives.poly_resistor()` now follows the PDK's own high-Rs recipe
(`draw_ppolyf_u_high_Rs_res()`): the `(62, 0)` marker over the whole resistor
poly, the p+ implant restricted to the two contact lands so the body stays
un-implanted, and the salicide block overhanging the body by 0.1 µm at each end
— the geometry `hres.drc`'s HRES.\* rules require, in place of the PRES.\*
geometry the unmarked class requires. `RCG`/`ROFF`/`RDEG` keep W = 1 µm and
L = 5.6 / 33 / 33 µm.

**2. The gf180mcu high-sheet poly-resistor process option this design requires
is `3k`.** The 1k / 2k / 3k members of that family are **one drawn device** —
identical masks, all three derived from the same `ppolyf_u_h` layer in the LVS
deck — separated only by the fab's high-sheet implant option. Selecting it is
therefore a *tape-out* requirement, not a layout choice, and it is recorded
here because nothing else in the repository could carry it. The high-Rs module
is an optional additional mask in this PDK; a shuttle that cannot offer the 3k
option cannot build this block as specified, and that is now a stated,
checkable precondition rather than an implicit assumption.

**3. Signoff LVS for any block containing these resistors is run with
`poly_res=3k`.** The PDK's own `run_lvs.py` hardcodes `poly_res="1k"` for all
four `--variant` letters and exposes no override, so `layout/harness/lvs.py`
passes the option through a shim (`_pdk_lvs_poly_res.py`) that re-uses the PDK
runner's own argument parsing and switch derivation and replaces only that one
key. `layout/run_pv.py lvs --poly-res pdk` restores the PDK default for
comparison. Under the PDK default the same unchanged geometry extracts as
`ppolyf_u_1k`; that is a run-configuration difference, not a layout defect.

**4. No ratified spec number changes.** This record ratifies the device the
spec's existing numbers were always measured against. `spec/pll.md`'s output
band, Kvco, power and jitter lines, and DR-003's band map, stand unmodified.

## Alternatives considered

- **Re-size the resistors for the unmarked 350 Ω/sq class (keep the drawn
  device, change W/L)** — rejected. `RCG` would need ≈48 squares instead of
  5.6 and `ROFF`/`RDEG` ≈283 µm of poly each instead of 33 µm, roughly an 8×
  area increase in the bias block. More importantly it is not a relabelling: the
  two classes have different temperature and process behaviour (the unmarked
  class's measured sheet resistance moves 41 % across `res_ff`/`res_ss` and
  temperature, the 3k class's 75 % — `sim/devchar-passives` record
  `20260801-085327-f7a2bfc`), so every recorded VCO corner result would have to
  be re-derived. That is relaxing the design to match a layout defect, which
  CLAUDE.md forbids ("agents do not relax the ratified spec to make results
  pass").
- **Amend the schematic to `ppolyf_u` at the drawn W/L (declare the layout
  right)** — rejected, and the most damaging of the three. It would silently
  multiply the constant-gm reference current by ≈8×: measured, the counterfactual
  bias generator draws 970–2163 µA at `spec/pll.md`'s own 100 MHz reference
  point (band 5, Vctrl 1.8 V) against 69–196 µA as specified, i.e. it exceeds the
  entire ratified 318 µA `vdd_vco` domain current at **every** point of the
  13-bundle × 3-temperature × 3-supply grid, before the ring is added. It would
  also invalidate every `sim/` record for this block.
- **Draw the marker but keep the reference netlist at the deck's hardcoded
  `ppolyf_u_1k`** — rejected as a half-measure. It fixes the silicon and leaves
  the paperwork wrong: LVS would keep reporting a device class the schematic
  does not name, which is exactly the ambiguity that let this defect survive
  #378. The shim in Decision 3 costs ~70 lines and removes the deviation
  entirely.

## Consequences

- **A process-option dependency is now explicit.** Tape-out must select the 3k
  high-sheet poly option. If a shuttle offers only 1k, this block's bias
  currents move by 3× and the decision has to be re-opened (a new record), not
  patched in the layout.
- **The bias block's DRC rule set changed.** Marked geometry is checked against
  `hres.drc` (HRES.1–12) instead of `pres.drc` (PRES.1–9). `vco_bias_resistors`
  and the assembled `vco_block` are both DRC clean under the new rule set, and
  `vco_block` LVS matches with `ppolyf_u_3k` on both sides — 65/65 devices and
  43/43 nets `Match` on direct `klayout.db.LayoutVsSchematic` cross-reference.
- **`block.RESISTOR_LVS_MODEL` is now the schematic's own class**, and
  `layout/tests/test_vco_layout.py::PolyResistorLvsClassTests` fails if the
  drawn marker, that constant, the committed schematic export and the LVS
  harness's `poly_res` switch ever disagree again. That four-way tie is the
  structural fix; the geometry change alone would not have prevented a
  recurrence.
- **No `sim/` record is invalidated.** The design the records were made against
  is unchanged; what changed is that the layout now builds it.
- **The bias block's footprint is essentially unchanged** (the marker and the
  re-shaped implant are drawn within the existing guard-ring margins), so no
  floorplan number moves.
- **A new campaign is added**, `sim/vco-bias-current/`, whose counterfactual arm
  is a *diagnostic* only. It is generated mechanically from the committed
  schematic export and must never be cited as a design alternative.
