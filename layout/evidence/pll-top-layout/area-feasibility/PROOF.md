# `pll_top` area feasibility study (issue #792)

Bounded study authorised by DR-041 (issue #758): can the assembled `pll_top`
(407,776.2 um^2, 0.4078 mm^2) be brought back toward the ratified
<= 0.30 mm^2 Area row by the two cost terms `PLL-FLOORPLAN.md` section 5.16
names -- the divider chain's aspect ratio and the planning spacings? This is a
feasibility study only. No default in `floorplan/skeleton.py` or in the
assembler changes, no production layout is re-folded, and the row is not
touched.

**Verdict in one line: no combination evaluated reaches 0.30 mm^2.** The best
assembled, connectivity-clean, DRC-no-worse result is **351,275.0 um^2
(0.3513 mm^2)**, still 51,275 um^2 (17.1 %) over the row, from lever (b)
alone. Lever (a), refolding the divider, does not help (it is worth
-1,567 um^2 at best, on top of lever (b), and costs area when applied alone).
Per DR-041 any upward amendment of the row is a separate decision record; this
report files no implementation follow-ups because there is nothing to
implement toward the row.

## How it was run

```
cd layout
python3 -m harness.area_feasibility --outdir <WORK> --drc --floor 0 12 0 --report results.json
```

(`LAYOUT_PV_PYTHON` pointing at a venv with `klayout` and `docopt`, as
`python3 layout/run_pv.py check-env` describes.) The sweep calls the real
`pll_top.top_level.assemble.assemble()` once per case with the lever applied by
overriding a module constant for that case only, then runs `netcheck.check` and
the foundry DRC deck (`harness.drc.run`, `--offgrid`, deep mode -- the
configuration of `../PROOF.md`) on the written GDS. All 39 cases and their
numbers are in `results.json`; the baseline and the best case keep their
assembly report and DRC bundle (`baseline/`, `floor-b/`).

| Item | Value |
|---|---|
| Layout writer / assembler | `klayout` Python wheel 0.30.12 (the committed proof used 0.30.10) |
| DRC KLayout | 0.28.16 (`/usr/bin/klayout`), the repository pin |
| PDK | open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, `gf180mcuD` |
| Deck | variant D, 5LM, METAL_TOP 11K, MIM option B, `--offgrid`, deep mode |

**The baseline reproduces before any lever is applied:** 1317.66 x 309.47 um =
407,776.2 um^2, netcheck OK, DRC 1 violation (`MIMTM.3`, the inherited
loop-filter C2 item of #753) -- identical to `../PROOF.md`.

**Which "decks":** the existing assembled-top proof ran one deck
configuration (variant D, MIM option B, the one above); no variant-A run exists
for the top level because its 3-metal stack cannot hold this routing
(`../PROOF.md` Limitations 1). The adoption criterion is therefore applied
against that one configuration: a case is "DRC no worse" when its violation set
is exactly the baseline's `MIMTM.3`.

## Lever (b): spacings

### What sets each spacing

`DOMAIN_SPACING_UM = 40` and `VCO_GUARD_MARGIN_UM = 15` are planning values
(`floorplan/skeleton.py`, `PLL-FLOORPLAN.md` sections 1-3), not foundry rules;
the rule deck has no rule for a distance between two blocks. What the deck does
bound is the same-layer spacing of whatever sits at the two facing block edges:
Metal1 0.23 um (`M1.2a`, `metal1.drc`), Metal4/5 0.28 um (`M4.2a`/`M5.2a`,
`metal4.drc`/`metal5.drc`), COMP 0.28 um (`DF.3a_LV`, `comp.drc`), Poly2 0.24 um
(`PL.3a`, `poly2.drc`) and, between wells at different potential, Nwell 1.4 um
(`NW.2b_LV`, `nwell.drc`). All files are under
`$PDK_ROOT/gf180mcuD/libs.tech/klayout/drc/rule_decks/`. Each block's outermost
shapes sit inside its bounding box, so the deck's floor on a block-to-block gap
is a measurement of the assembled layout, not a number to read off one rule.
It was measured by running the deck.

### Measured

| Case | Gap changed | Result (um^2) | netcheck | DRC |
|---|---|---|---|---|
| `hgap-40` ... `hgap-0` | the pfd_cp-to-loop_filter and loop_filter-to-VCO gaps, 40 -> 0 um (blocks abutting); the lock_detector-to-pfd_cp gap held at 36 um | 407,776.2 at every value | OK | `MIMTM.3` only |
| `spacing-30` ... `spacing-2` | all three row gaps together | refused: *supply pad slots do not fit in the lock_detector / pfd_cp gap* | -- | -- |
| `vgap-30`, `vgap-20` | row-to-divider gap, 40 -> 30, 20 um; keep-out kept at 15 | 394,599.6; 381,423.0 | OK | `MIMTM.3` only |
| `vgap-10` | same | refused: *channel middle is full placing FB* | -- | -- |
| `guard-10`, `-5`, `-2`, `-0` | VCO keep-out, 15 -> 10 .. 0 um | 401,187.9; 394,599.6; 390,646.7; 388,169.5 | OK | `MIMTM.3` only |
| `vgap-18-g0` ... `vgap-12-g0` | row-to-divider gap with keep-out 0 | 359,180.9; 356,545.6; 353,910.3; **351,275.0** | OK | `MIMTM.3` only |
| `vgap-11-g0` ... `vgap-4-g0` | same, smaller | refused: *channel middle is full* | -- | -- |

What this says:

* **Horizontal gaps are worth nothing today.** Closing the two gaps the
  assembler allows to close (PFD/CP | loop filter, loop filter | VCO) from 40 to
  0 um moves the row 80 um left and the area does not change, because the
  divider chain, 1317.66 um wide, sets the box width and the row is already 111 um
  narrower than it. Abutting blocks add no DRC item on the deck -- but that is
  a statement about the deck, not about supply-domain isolation, which no
  extraction (#18) supports either way.
* **The lock_detector | pfd_cp gap cannot go below ~34 um in this
  assembler** -- it holds the six star supply pad slots
  (`assemble.py`: "supply pad slots do not fit"). That is a routing-plan
  constraint, not a foundry one, and it is why the uniform `spacing-*` cases
  are refused.
* **The vertical stack is where the area is.** The keep-out and the
  row-to-divider gap are the only spacings that change the box height. With the
  15 um keep-out the middle routing channel needs a >= 20 um gap (`vgap-10`
  fails); with the keep-out at 0 it routes down to **12 um** (`vgap-12-g0`),
  because the channel then starts at the row top instead of 15 um above the VCO.
  Below 12 um the channel runs out of tracks (the router's refusal, not a rule).
* **Best of lever (b): `floor-b` = horizontal gaps 0, row-to-divider gap 12 um,
  keep-out 0 -> 1317.66 x 266.59 um = 351,275.0 um^2 (0.3513 mm^2)**, netcheck
  OK, DRC exactly the baseline's `MIMTM.3`. That is -56,501.2 um^2 (-13.9 %)
  from baseline and **still 17.1 % over the row**.

**Adoption.** `floor-b` passes the adoption test above, but it is not adopted:
it does not reach the row, a 0 um VCO keep-out contradicts `PLL-FLOORPLAN.md`
section 1's noise-isolation reasoning with nothing (no extraction, no
simulation) to say it is safe, and this issue is feasibility only.
`skeleton.py` and the committed `pll_top.gds` are unchanged. No spacing was
rejected by DRC: every refusal above is the assembler's, none is a foundry
rule violation.

## Lever (a): re-folding the divider chain

Method: the committed divider GDS is cut into `k` equal-width vertical slabs
that are stacked 3 um apart (its own `ROW_GAP_Y_UM`), and that outline is fed
through the unchanged assembler. **This is an area probe, not a layout:** every
device and wire that straddles a cut is severed, so the folded block is
electrically meaningless; its netcheck (OK) and its extra DRC items
(`CO.*`, `DF.*`, `M1.*`, `PP.*`, `V4.2a` ... from the cuts) say nothing about a
real re-fold and must not be read as one. What the probe does measure is the
outline's consequence for the bounding box.

| Case | Divider outline (um) | Box (um) | Area (um^2) |
|---|---|---|---|
| baseline | 1317.66 x 41.99 | 1317.66 x 309.47 | 407,776.2 |
| `fold-2` | 658.83 x 86.98 | 1206.37 x 354.46 | 427,609.9 |
| `fold-3` | 439.22 x 131.97 | 1206.37 x 399.45 | 481,884.5 |
| `floor-b-fold2` (lever (b) at its floor) | 658.83 x 86.98 | 1122.37 x 311.58 | 349,708.0 |
| `floor-b-fold3` | 439.22 x 131.97 | 1122.37 x 356.57 | 400,203.5 |

Why a fold cannot pay: the divider is only 41.99 um tall, so it is wide and
thin; the bottom row beside it is already only 111 um (9 %) narrower. Folding
removes at most that 111 um of width (-34 k um^2 at today's height) but every
extra band adds ~45 um of height across a ~1200 um box (+54 k um^2). The width
the fold can reach is the row's, 1206.37 um at 40 um gaps and 1122.37 um with
the gaps closed, and from there only the height moves. The best fold result,
`floor-b-fold2`, is **1,567 um^2 (0.4 %) below `floor-b` without a fold** --
inside the noise of what a real fold's routing would cost, and 49,708 um^2 over
the row.

## Reachable?

| Combination | Best area (um^2) | mm^2 | vs 0.30 mm^2 |
|---|---|---|---|
| baseline | 407,776.2 | 0.4078 | +35.9 % |
| (a) fold alone | 427,609.9 (fold-2) | 0.4276 | +42.5 % |
| (b) spacings alone (`floor-b`) | 351,275.0 | 0.3513 | +17.1 % |
| (a) + (b) (`floor-b-fold2`, area probe) | 349,708.0 | 0.3497 | +16.6 % |

**<= 0.30 mm^2 is not reachable by any combination of these two levers.** Not
evaluated, and the only route the numbers leave open: a different *placement*
(packing a refolded divider into the whitespace above `lock_detector` and
`pfd_cp`, which are 80.9 um and 110.3 um shorter than the 184.6 um loop filter
row, or stacking the short blocks). The sum of the five block outlines is
193,957.6 um^2, so 0.30 mm^2 means a top-level overhead of x1.547 against
`floor-b`'s x1.811 (x2.103 baseline) -- a re-floorplan outside the two levers
this issue bounds, and with 40 um domain gaps, a 15 um keep-out and the
routing channels it would need to be measured, not argued. The alternative is
the separate decision record DR-041 already names for an upward amendment.

## Limitations

1. Fold cases are outline probes (above); no real fold was routed, extracted or
   DRC-checked, and the divider's electrical function across a fold is not
   evidenced.
2. One deck configuration only (the assembled top has never had another).
3. Spacings below the baseline were judged on layout rules and top-level
   connectivity only; no extraction or simulation (#18) says what closing a
   supply-domain gap or the VCO keep-out costs in noise or substrate coupling.
4. The study adds `assemble.GAP_OVERRIDES_UM`, empty and unused by the
   committed build, so each gap can be moved on its own; the committed GDS is
   unchanged.
