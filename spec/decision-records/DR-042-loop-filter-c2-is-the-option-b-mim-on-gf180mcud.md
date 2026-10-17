# DR-042: Loop-filter C2 becomes the option-B MIM (`cap_mim_2f0_m4m5_noshield`) on gf180mcuD

- **Status**: proposed — ratified only by operator approval of the PR that carries it (the two-key ceremony in `spec/README.md`). Until then `design/` carries the change as *prepared*, not as ratified spec.
- **Date**: 2026-10-17
- **Decided by**: operator ruling (attended session of 2026-10-16, batch 10 Q3 option 1, recorded 2026-10-17 00:15 UTC on #753) selected the direction; this record was drafted by a Builder agent, issue #753
- **Supersedes (in part)**: DR-006 Decision 1, **the C2 device only**. DR-006 stays ratified and is not edited; everything in it other than the C2 device row is unchanged (see Decision 2).
- **Evidence consumed**: `sim/devchar-passives/records/20260731-041345-833292f.md` and `sim/loop-dynamics/records/20260731-202550-82af5a9.md` (the option-A baseline); `layout/evidence/loop-filter-layout/PROOF.md` (#748; the recorded variant-D `MIMTM.3` violation and variant-D LVS mismatch that motivated this record).

## Context

DR-006 ratifies C2 as `cap_mim_2f0_m2m3_noshield`, a gf180mcu **MIM option A**
device (Metal2 bottom plate, Metal3-level top plate). This repository's
process target is **gf180mcuD** (`sim/pdk.json`), whose decks select
**MIM option B** (`metal_top=11K mim_option=B metal_level=5LM`): the MIM sits
between Metal4 and Metal5 and its device is `cap_mim_2f0_m4m5_noshield`. #748
drew C2 exactly as ratified and recorded that the variant-D DRC deck reports
`MIMTM.3` on it and that the variant-D LVS deck does not recognise the MIM as a
device. #753 asked which side of that disagreement to move; the operator's
ruling keeps the process target and moves the device.

The ruling settles a **policy** question. It does not establish that the
option-B device is electrically equivalent, that the Metal4/Metal5 layout
passes physical verification, or that anything is signed off.

## Decision

**1. C2 is `cap_mim_2f0_m4m5_noshield` on gf180mcuD.** The exact contract:

| Item | Value |
|---|---|
| Device (netlist model) | `cap_mim_2f0_m4m5_noshield`, 1 instance (`XCF5`), `c_width` = `c_length` = 31.4 µm, `m` = 1 |
| Process target | gf180mcuD, unchanged (`sim/pdk.json`); no other block's process contract moves |
| Deck selection | `metal_top=11K`, `mim_option=B`, `metal_level=5LM` — the unmodified variant-D decks |
| Bottom plate | Metal4, net `VCTRL` (terminal 1) |
| Top plate | `FuseTop` under Metal5, net `VSS` (terminal 2), reached by a Via4 sea inside `FuseTop` |
| Nominal density | 2 fF/µm², the same as the option-A device |
| Terminals | unchanged: `VCTRL` / `VSS` |

The drawn size is **kept at 31.4 × 31.4 µm** because that is what DR-006's
existing electrical target (C2 ≈ 2.02 pF typical, 1.81 … 2.22 pF over the
passive corner bundles) was sized to, and no result yet says the option-B
device needs anything else. That equal nominal density makes the same drawing
the natural starting point; it is **not** evidence of equivalence (Decision 3).
Any change to the drawn size, the capacitance target, or the tolerances below
needs a further record. Nothing is adjusted here to obtain a pass.

**2. What does not change.** C1 (4 × `cap_nmos_03v3_b`, 87 × 87 µm), the
four-resistor `ppolyf_u` series chain, the fixed filter topology, the
Icp-trim-versus-`f_ref` rule of DR-006 Decision 5, and every ratified limit
(phase margin ≥ 45°, `f_c < f_ref/10`, the stability, settling and
operating-range limits, and the other spec rows) are unchanged. DR-006's C1/C2
ratio of ≈ 60 and the reasoning for it stand; they are re-checked, not
re-opened, by Decision 3.

**3. Equivalence is established only by new measurements, against tolerances
fixed here before any is taken.** Equal nominal density, a model card with the
same parameter values (the two cards for `…_m2m3_…` and `…_m4m5_…` in
`sm141064_mim.ngspice` are textually identical apart from the name — checked by
diff of the shipped file, sha256 `9b85cd00…666`), and any patched
option-A diagnostic are **insufficient**. The required new, append-only
evidence, each as its own `sim/` record that retains the old records untouched
and states plainly which device it measured:

1. *Selected-device model/PVT comparison* (`sim/devchar-passives`): the
   option-B device against the recorded option-A baseline at the drawn size,
   over the existing mandated matrix (every passive-corner bundle × the three
   temperatures of record 20260731-041345-833292f). **Tolerance: `C2_B / C2_A`
   within 1.00 ± 0.02 at every bundle × temperature point**, and the voltage
   coefficient over the 0.3 … 3.3 V window no worse than the option-A figure.
2. *Loop dynamics* (`sim/loop-dynamics`): the full DR-006 matrix (140
   `f_ref`/N/trim-code cells × 27 bundles × 3 temperatures × 5 `Vctrl` points)
   re-run on the option-B netlist. **Tolerances: (a) every ratified limit still
   holds at every cell exactly as DR-006 Decisions 3–5 state them, with the
   trim-code table unchanged; (b) no cell changes pass/fail status relative to
   record 20260731-202550-82af5a9; (c) per cell, phase margin no more than
   0.25° below the option-A value and `f_c` within ±2 %.**
3. *Failures are retained.* Any cell or point outside a tolerance is recorded
   as measured and reported against the ratified limits; it is not averaged
   away, relabelled as an option-A result, or re-toleranced after the fact.

*Why these numbers.* The narrowest ratified margin in the baseline is the
1 MHz / trim-code-4 cell at 47.44° against the 45° criterion, i.e. **2.44°**;
the baseline's own C2 sensitivity sweep (`ripple_tradeoff.csv`, model phase
margin 33.50° at the as-built 2.016 pF versus 31.61° at 4 pF) is ≈ 1°/pF in the
worse direction. A ±2 % C2 window is ≈ ±0.04 pF, i.e. a few hundredths of a
degree on that slope, and the 0.25° loop allowance is ≈ 10 % of the narrowest
ratified margin — so the tolerances protect the ratified limits with room to
spare while still being tight enough that a real change in the device shows up
as a failure. They are set from the baseline's margins, not from any
option-B result, none of which exists yet.

**4. Physical verification is on the unmodified variant-D decks.** Required:
standalone DRC and LVS of the option-B loop filter with the stock gf180mcuD
decks (`mim_option=B`), recording the PDK version (the `ciel` revision), tool
versions, source and deck hashes, and the actual verdicts, plus an
opened-link negative control that must mismatch. A deck patched to make a
result match (the two-line option-A connectivity patch recorded by #748) is a
*diagnostic* and must be filed and labelled separately; a patched option-A
match or the historical variant-A clean DRC is not variant-D signoff. The
Metal4/Metal5 drawing must also satisfy the connectivity checks in
`layout/pll_top/loop_filter/netcheck.py` (plate-aware, with its negative
controls), which this record's preparation extends to the option-B stack.

**5. Preparation, measured validation and signoff are three separate states**,
and this record claims only the first:

| State | Status at the time of this record |
|---|---|
| **Preparation** — this record, the schematic and regenerated netlist (`design/loop_filter.sch`, `design/netlist/loop_filter.spice`, `design/netlist/pll_top.spice`), the option-B drawing in the layout generator and its connectivity checks | done in the PR carrying this record |
| **Measured validation** — Decision 3 (model/PVT, loop dynamics) and Decision 4 (unmodified variant-D DRC/LVS) | **pending**; no option-B measurement exists |
| **Signoff / equivalence claim** — the substitution accepted as electrically and physically equivalent | **pending**; not claimed anywhere |

## Alternatives considered

- **Keep option A and change the PDK variant to A (or F)** — preserves the
  ratified capacitor but changes the metal-stack contract under every other
  block's existing DRC/LVS evidence, which would all need re-running, and
  leaves the recorded option-A LVS-deck connectivity defect to resolve.
  Rejected by the operator ruling.
- **Keep both and document incomplete signoff** — accepts the variant-D
  `MIMTM.3` violation and the unmatched C2 as a permanent limitation; worst for
  integration. Rejected by the operator ruling.
- **Re-size C2 now so the option-B device lands on some other target** — not
  done: no measurement says it is needed, and sizing to a pass is exactly what
  the spec rules out. If Decision 3 fails a tolerance, resizing is a new record.

## Consequences

- **Historical evidence stays valid and is not relabelled.** Every `sim/`
  record and netlist snapshot naming `cap_mim_2f0_m2m3_noshield` measured the
  option-A device and remains correct for it; so does the `#748` layout
  evidence (variant-A and variant-D runs). The layout generator keeps an
  explicit `--mim-option A` path solely so those committed artifacts, and the
  assembled `pll_top` layout built from them, stay reproducible (`layout/README.md`).
- **The `sim/` testbenches that hard-code the option-A model name**
  (`sim/devchar-passives`, `sim/loop-dynamics`) are not yet pointed at the
  option-B device. Doing that, and running Decision 3, is the follow-up
  measurement work.
- **The assembled `pll_top` layout still contains the option-A filter** and is
  therefore not consistent with `design/netlist/pll_top.spice` (which now
  names the option-B device). Re-assembling `pll_top` with the Metal4/Metal5
  loop filter, and the top-level routing and verification that implies, is
  follow-up work; the area row's status (DR-041) is not affected by this record.
- **A Metal4/Metal5 plate pair changes the parasitics on `VCTRL`** (different
  dielectric stack and plate-to-substrate geometry). Like DR-006, this record
  is schematic-level for the filter's own parasitics; post-layout simulation
  remains separate follow-up work.
- **The reference-netlist model name** for the option-B device in the LVS
  reference (`layout/pll_top/loop_filter/block.py: reference_netlist()`) is
  prepared by analogy with the option-A card and has not been run through the
  deck; whether the stock reader needs a different spelling is one of the
  things the Decision 4 run settles.
- If ratified, the DR-006 header gains a one-line pointer to this record; the
  body of DR-006 is not rewritten.
