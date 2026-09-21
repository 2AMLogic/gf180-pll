# Area audit — sizing every remaining area lever before spending it (issue #442)

`PLL-FLOORPLAN.md` §5.1–§5.4 record a real area overrun against
`spec/pll.md#area`'s ≤ 0.15 mm² budget, pass by pass (≈2.9× → ≈2.0× → ≈1.9× →
≈2.0×). Each of those revisions arrived as a side effect of some block's own
issue, and each named the next lever from a *derived* number rather than a
measured one. Issue #442 asks for the opposite order: quantify each lever
first, with the arithmetic shown, and only then decide what is worth
executing.

**This record is that quantification, and it changes the answer.** The lever
the floorplan has named as the remaining structural cause since §5.1 —
device density, "every device is its own diffusion island wired by metal" —
is measurably worth **0.10 % of the gap**. The lever nothing had named is
worth **63 %**. And even both, plus the `pfd_cp` fold, taken to their
geometric ceilings, leave the total at **≈1.35× the target**.

Nothing here is a geometry change. No committed GDS, generator, evidence
record or DRC/LVS verdict is touched by this increment: it is measurement of
what is already committed, plus the tool that reproduces it.

## How to reproduce every number below

```
$ python3 layout/run_pv.py area
```

No PDK, no KLayout application binary, no DRC deck — only the `klayout` pip
wheel, the same dependency `layout/tests` already gates on, so this runs in
CI's headless `checks` job. The committed output of that command is
[`area-audit.md`](area-audit.md) in this directory; the module is
`layout/harness/area.py` and its known-answer tests are
`layout/tests/test_area_audit.py` (synthetic layouts whose decomposition is
arithmetic on the boxes written, because an audit that only ever runs where
its answers cannot be checked proves nothing).

**Basis: the committed block GDS bounding box**, not a generator's recorded
`footprint` tuple. Where the two differ, the GDS is what exists. Two
differences are worth stating rather than smoothing over:

| Block | Hand-recorded footprint | Committed GDS bbox | Δ |
|---|---|---|---|
| `pfd_cp` | 434.31 × 80.73 µm (35,060 µm²) | 432.66 × 81.55 µm (35,281 µm²) | +221 µm², +0.6 % |
| `vco_block` | 183.18 × 170.28 µm (31,192 µm², §5.1/§5.4 and `PROOF-fold.md`) | **172.52 × 184.48 µm (31,826 µm²)** | **+634 µm², +2.0 %** |

The `pfd_cp` delta is the footprint tuple being a union of recorded
sub-block extents rather than of drawn shapes. The `vco_block` delta is not a
rounding artifact: the VCO has changed since #324's fold — `PROOF-2d-fold.md`
records 172.52 × 183.48 µm and `PROOF-381-high-rs-resistor.md` the current
172.52 × 184.48 µm — and §5.4's arithmetic, `docs/chipalooza/
challenge-5-proposal.md`'s Area row and this issue's own opening table all
still carry #324's 0.0312 mm². Hand-maintained figures drift; that is a
second reason this audit is a committed command and not a one-off.

## What the audit measures, and why each measurement

| Measurement | What it decides |
|---|---|
| Per-layer merged area | Diffusion (`comp`) area is the **whole** budget any shared-diffusion / device-stacking lever can address. If comp is 1 % of the block, so is the lever's ceiling. |
| Fill = drawn union / bbox | Its complement is whitespace — neither device, well, wire nor contact. Whitespace is what a packing lever recovers. |
| Device bands vs. no-device bands | A y-band containing no diffusion is a band spending its entire height on routing. Its height is directly comparable to the packed track floor below. |
| Metal2 track census → packed floor | Separates "this band is full of tracks" from "this band is tall for some reason other than track count". |
| Metal2 fill *inside* the device bands | Metal2 has no DRC relationship to the diffusion under it. If the plane over the cells is empty, the track band sits above them by generator convention, not by any rule — which is what turns "route over the cells" into a sized lever. |

## The measurement

| Block | Footprint (µm) | bbox (µm²) | Drawn (µm²) | Fill | `comp` share | Device band (µm) | No-device band (µm) | Metal2 tracks | Packed track floor (µm) | Metal2 over devices |
|---|---|---|---|---|---|---|---|---|---|---|
| `vco_block` | 172.52 × 184.48 | 31,826 | 12,468 | 39.2 % | 13.78 % | 183.48 | 1.00 | 46 | 34.50 | 5.9 % |
| `pfd_cp` | 432.66 × 81.55 | 35,281 | 6,030 | 17.1 % | 4.43 % | 37.18 | 44.37 | 57 | 42.75 | 0.9 % |
| `divider_chain` | 1317.66 × 100.29 | 132,148 | 27,973 | 21.2 % | 1.02 % | 26.32 | 73.97 | 73 | 54.75 | 1.0 % |
| `lock_detector` | 119.30 × 62.60 | 7,468 | 2,013 | 27.0 % | 7.45 % | 55.00 | 7.60 | 23 | 17.25 | 2.4 % |

**Every drawn block is 61–83 % whitespace, and the three composite
assemblies are 73–83 %.** Devices, wells, wires and contacts together occupy
17.1 % of `pfd_cp` and 21.2 % of the divider chain. For scale inside the same
generator family: `pfd` alone — a flat, Metal1/Metal2-only row of 47 leaf
instances — measures 69.0 % fill at 80.90 × 22.48 µm. So the low fill is a
property of how these blocks are *composed*, not of the leaf cells they are
composed from.

## The gap this has to close

`spec/pll.md#area`: ≤ 0.15 mm² (150,000 µm²) for the whole block. §5's own
×1.25 top-level overhead factor means the sum of block footprints must be
≤ **120,000 µm²**.

| Block | as-drawn (µm²) | basis |
|---|---|---|
| Loop filter (R + C1 + C2) | 36,936 | DR-006 / §3 — a calculation, not a GDS (no loop-filter layout exists) |
| `vco_block` | 31,826 | committed GDS |
| `pfd_cp` | 35,281 | committed GDS |
| `divider_chain` | 132,148 | committed GDS |
| `lock_detector` | 7,468 | committed GDS |
| **Sum** | **243,660** (0.2437 mm²) | |
| **After §5's ×1.25** | **304,575** (0.3046 mm²) | **2.03× over** |

**Gap to close: 243,660 − 120,000 = 123,660 µm².** Every lever below is
sized against that denominator.

## Lever 1 — a `pfd_cp` fold: **7,015 µm², 5.7 % of the gap**

§5.4's reading of this lever is right on its mechanism: `pfd_cp` "composes
two already-wide sub-blocks side-by-side rather than folding either". The
audit locates the dead space exactly, and it is not where a naive fold would
put `pfd`:

| Region (block frame) | Extent | Area | Drawn |
|---|---|---|---|
| `pfd`'s own full-height column, x ∈ [−40.45, 40.45] | 80.90 × 80.72 µm | 6,531 µm² | 1,370 µm² (21.0 %) |
| — `pfd` itself | 80.90 × 22.48 µm | 1,819 µm² | 1,265 µm² (69.5 %) |
| — dead space above `pfd` | 80.90 × 58.24 µm | 4,712 µm² | 106 µm² (**2.2 %**) |
| Band above `cp_dumpbuf`, right of `cp_output_stage` | 217.10 × 38.72 µm | 8,407 µm² | 86 µm² (**1.0 %**) |

`cp_dumpbuf` is 211.10 × 36.00 µm and `cp_output_stage` 130.31 × 66.73 µm, so
placing them side by side leaves a 217 × 38.7 µm region above the dump buffer
that is **99.0 % empty** — the only things in it are the top-level Metal2
trunk rows (y 65.70–71.14) and four Metal3 risers crossing it. `pfd`'s
1,819 µm² fits inside it with room to spare.

Relocating `pfd` there removes its column from the block's width:

```
434.31 x 80.725 = 35,060 um^2    (today: pfd beside cp)
347.41 x 80.725 = 28,045 um^2    (pfd inside cp's own empty band; 347.41 is
                                  cp's own recorded width, PLL-FLOORPLAN §5.4)
                  ----------
saving             7,015 um^2    = -20.0 % of pfd_cp = 5.7 % of the 123,660 um^2 gap
```

On the committed-GDS basis (432.66 × 81.55 µm) the same 86.90 µm of width is
7,084 µm²; the −20.0 % relative saving is the same on either basis, which is
why the choice does not change the verdict.

**Verdict: worth executing, and it does not close the gap.** −20 % on a block
is a real result by this repo's own precedent (#324 took the VCO's mirror
−29 %, #344 the divider chain −12 %). It is also 1/17th of what is needed. It
needs its own issue, because it is exactly the kind of work `pfd_cp`'s own
module docstrings record as hazardous — "four designs were tried before this
one held" for the `cp` bridge alone — and because `pfd_cp` now carries both a
DRC (`--offgrid`, signoff-grade) and an LVS claim (#448/#452) that a
relocation must re-prove.

## Lever 2 — divider-chain shared diffusion: **125 µm², 0.10 % of the gap**

This is the lever `PLL-FLOORPLAN.md` has named as the remaining structural
cause since §5.1, and restated at §5.3 ("what is left is device density, not
placement") and §5.4 ("the cause, same structural pattern ... every device is
its own diffusion island"). The reasoning was a ratio: 132,148 µm² / 452
transistors = 292 µm²/transistor, against `lock_detector`'s 187 for the same
PDK and flavour.

**µm²/transistor cannot distinguish "the diffusion islands are too big" from
"the diffusion islands are 1 % of the block and the rest is empty."** The
audit measures which it is:

```
divider_chain comp (diffusion), merged  :    1,352.5 um^2  =  1.02 % of the block
              poly2                     :      490.8 um^2  =  0.37 %
              contact                   :      223.7 um^2  =  0.17 %
              sum W*L over all 452 devices:     260.3 um^2  =  0.20 %
```

So an upper bound is available before any topology is examined: **even if
every diffusion island in the block vanished entirely, taking its keep-out
with it, that is 1,352.5 µm² — 1.02 % of the block and 1.09 % of the gap.**
Shared diffusion does not remove diffusion; it merges adjacent islands. Its
real value is a fraction of that fraction.

Sized from the block's own reference netlist rather than from convention.
A shared-diffusion candidate is a node touching exactly two source/drain
terminals, on two different same-flavour devices, and no gate — a series
junction carrying no other connection, so its two islands could become one
uncontacted stack. `design/netlist/divider_chain.spice`'s committed flat
re-expression has **40 such nodes among 452 devices** (34 nfet, 6 pfet — all
40 are internal `_NMID`/`_NM1`/`_NM2`/`_PMID` series nodes; the census
excludes supply rails by their own fan-out, not by name).

Per merge, from `devgen.py`'s own constants (`SD_OVERHANG_UM` = 0.5,
`COMP_GAP_UM` = 0.6, L = 0.28):

```
two separate islands : 2*(2*0.5 + 0.28) + 0.6  = 3.16 um of column height
one shared stack     :  2*0.5 + 2*0.28 + 0.5   = 2.06 um
                                                 -------
saved per merge      :                           1.10 um, over the wider device's W
```

Summed over all 40 candidates at their own device widths:

```
125.4 um^2  =  0.095 % of the 132,148 um^2 block
            =  0.10 % of the 123,660 um^2 gap
```

**Verdict: not worth executing. The hypothesis is falsified.** A generator
change touching `devgen.py` and eight row-cell modules, re-proving a
452-device block's DRC *and* its LVS match against
`design/netlist/divider_chain.spice`, to recover one part in a thousand of
what has to come out. `layout/tests/test_area_audit.py` asserts the bound
(`test_shared_diffusion_cannot_be_worth_1_percent_of_the_divider_chain`) so
that if a future geometry change ever makes it false, the failure says so
instead of this conclusion silently rotting.

The same measurement disposes of the VCO's own "residual overrun ... shared
with the divider chain" note in §5.3: `vco_block`'s comp is 13.78 % of its
bbox — the highest of any block — and its no-device band is 1.00 µm. There is
no routing band to reclaim there and no density lever either; the VCO's 60.8 %
whitespace is guard-ring and well/substrate spacing, which is what §1 sized it
to be.

## Lever 3 — the track band over the cells, not above them: **77,870 µm², 63 % of the gap**

Nothing in `PLL-FLOORPLAN.md` names this lever. It is the one the measurement
finds.

Every composite generator in `layout/pll_top/` assigns each net a Metal2
`track_y` **above** the cells it has already drawn (`devgen.NetTracks`, and
`pack_tracks()` after #341). Composition is hierarchical, so the bands stack:
`dff_tg_3v3` puts its own band above its leaf cells, `div23_cell` puts its
band above `dff_tg_3v3`, `divider_chain` puts its band above `div23_cell`.
The result, measured:

| Band (divider chain) | y | Height | comp | Metal1 | Metal2 | Metal3 |
|---|---|---|---|---|---|---|
| row 0 devices | −0.30 … 13.16 | 13.46 µm | 3.8 % | 5.8 % | **1.0 %** | 11.5 % |
| row 0 routing | 13.16 … 52.22 | 39.06 µm | 0.0 % | 0.0 % | 11.0 % | 6.7 % |
| row 1 devices | 52.22 … 65.38 | 13.16 µm | 3.9 % | 6.0 % | **1.0 %** | 12.3 % |
| row 1 routing | 65.38 … 99.99 | 34.61 µm | 0.0 % | 0.0 % | 11.1 % | 8.2 % |

**73.97 µm of the block's 100.29 µm height — 73.7 % — contains no diffusion at
all, and the Metal2 plane over the cells that do contain diffusion is 1.0 %
occupied.** Metal2 has no DRC relationship to the diffusion beneath it. The
band is above the cells because that is where `NetTracks` puts it, not
because the plane over them is unavailable.

The geometric ceiling of moving the tracks over the cells is
`max(packed track floor, device band)` for the height, at unchanged width:

| Block | Packed track floor | Device band | Height floor | Area floor | Δ |
|---|---|---|---|---|---|
| `divider_chain` | 73 × 0.75 = 54.75 µm | 26.32 µm | 54.75 µm | 1317.66 × 54.75 = 72,142 µm² | **−60,006 (−45.4 %)** |
| `pfd_cp` | 57 × 0.75 = 42.75 µm | 37.18 µm | 42.75 µm | 347.41 × 42.75 = 14,852 µm² (with lever 1) | **−20,429 (−57.9 %)** |
| `lock_detector` | 23 × 0.75 = 17.25 µm | 55.00 µm | 55.00 µm | 119.30 × 55.00 = 6,562 µm² | −906 (−12.1 %) |
| `vco_block` | 46 × 0.75 = 34.50 µm | 183.48 µm | 183.48 µm | 172.52 × 183.48 = 31,654 µm² | −173 (−0.5 %) |

`lock_detector` and `vco_block` have essentially nothing here — their
diffusion already spans their height — which is a useful check on the metric:
it does not hand out savings everywhere.

**This is a ceiling, not an estimate, and the real outcome will be worse.**
It assumes zero routing-overhead penalty: every track hides entirely under or
over a device row, no track jogs around another net's Via1 landing pad in the
device band, and the two rows' tracks pack against each other perfectly.
A real implementation pays for all three. Quoted as a ceiling because that is
what makes it decisive — if the ceiling does not close the gap, nothing
inside it does.

**Verdict: this is the lever, and it needs its own issue per block.** It is a
change to the composite routing fabric (`devgen.route_net`/`NetTracks`/
`pack_tracks`), which is shared by every cell in a block family, and every
block it touches must be re-run through DRC and — for `divider_chain`,
`vco_block` and `pfd_cp` — LVS.

## The floor, and why the target does not survive it

Taking every lever above to its geometric ceiling simultaneously:

| Block | as-drawn | ceiling | lever |
|---|---|---|---|
| Loop filter | 36,936 | 36,936 | **none.** Its area is set by DR-006's C1/C2 *capacitance*, at the measured 3.988 fF/µm² of `cap_nmos_03v3_b`. Reducing it is a loop-dynamics change, not a layout one. |
| `vco_block` | 31,826 | 31,654 | lever 3, −0.5 % |
| `pfd_cp` | 35,281 | 14,852 | levers 1 + 3 |
| `divider_chain` | 132,148 | 72,142 | lever 3 (lever 2 adds 125 µm²) |
| `lock_detector` | 7,468 | 6,562 | lever 3 |
| **Sum** | **243,660** | **162,145** | recovers 81,515 µm² = **65.9 % of the gap** |
| **After ×1.25** | **304,575** (2.03×) | **202,681** | **1.35× the 0.15 mm² target** |

Levers 1 and 3 do **not** compose additively on `pfd_cp`: lever 1 removes
86.90 µm of width, lever 3 removes 38.80 µm of height, and the width lever 1
saves no longer multiplies the tall height once lever 3 has run. So the two
together save ≈3,400 µm² less than their separate figures sum to. Lever 3
measured alone across all four blocks, each at its own as-drawn width, is
77,869 µm² = **63.0 %** of the gap; levers 1 and 3 together are 81,515 µm² =
**65.9 %**.

The residual is structural, and it is visible without any of the levers:

```
loop filter (capacitance-set, no lever)      36,936 um^2
vco_block  (at its own ceiling)              31,654 um^2
                                             ----------
                                             68,590 um^2  = 57.2 % of the entire
                                                            120,000 um^2 pre-overhead budget

leaves for pfd_cp + divider_chain + lock_detector :  51,410 um^2
their combined ceiling                            :  93,555 um^2
                                                     ---------
                                                     1.82x short
```

**So 0.15 mm² is not reachable for this design as specified, by ≈1.35×, even
granting every measured lever its geometric best case.** Two-thirds of the
pre-overhead budget is already committed to a loop-filter capacitor sized by
DR-006 and a VCO whose whitespace is the guard-ring isolation §1 requires.

## What this record does *not* conclude

**It does not amend `spec/pll.md#area`, and it should not be read as
licence to.** 1.35× is a *bound derived from unexecuted levers*, not a
measured floor. An amendment to a ratified spec row needs the real number,
and the real number needs lever 3 actually built and DRC/LVS-clean on at
least the divider chain — the block that is 54 % of the sum. Writing the
decision record first would be exactly the mistake of relaxing the ratified
spec to make a result pass, with an estimate standing in for evidence.

Recorded honestly instead: the overrun is **2.03×**, unchanged in substance
from §5.4's ≈2.0× (the 0.03 is the VCO's own drift, above); each lever is now
**sized**, so nobody has to guess again; and the levers worth executing have
owning issues rather than being parked as "tracked as a follow-up".

## Acceptance criteria this increment satisfies

| Criterion (#442) | Where |
|---|---|
| Each lever's expected saving estimated with shown arithmetic before it is spent | This record, "Lever 1/2/3"; reproducible via `layout/run_pv.py area` |
| `PLL-FLOORPLAN.md` carries a new revision section with the re-derived budget | §5.5 |
| Every block whose geometry changes is re-run through DRC/LVS | **vacuous — no geometry changes.** No GDS, generator or deck verdict is touched. The two execution issues carry this criterion. |
| Outcome is ≤ 0.15 mm² or a decision record amending the target | **Neither, deliberately** — see "What this record does not conclude". The overrun stays tracked, now with sized levers and owning issues rather than an unnamed follow-up. |
| `docs/chipalooza/challenge-5-proposal.md`'s Area row updated | Area row + "Known gaps" item 8: 2.03× on the current GDS, with the falsified device-density cause replaced by the measured one |
