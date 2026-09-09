# `div23_cell` -- divide-by-2/3 composite macro layout (issue #309)

Part 4 of #295. This is the second `divider_chain` **composite** built on top
of #306's leaf-cell generators and #308's own `dff_tg_3v3` composite -- 1x
`nand3_3v3` (`XN3`), 2x `nand2_3v3` (`XN2Q`, `XN2M`), 2x `inv_3v3` (`XIQ`,
`XIM`), 2x `dff_tg_3v3` (`XFQ`, `XFMO`), 1x `inv2x_3v3` (`XICKO`) -- 60
transistors total, wired exactly per `design/netlist/div23_cell.spice`'s own
`div23_cell` subckt. This is the exact macro Part 5 (`divider_chain`'s own
top-level assembly, not built here) instantiates **six times, identically**.

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean 60-transistor composite
layout, assembled as a flat macro composition of 30 columns across the 8
sub-cell instances above (including `dff_tg_3v3`'s own 10 internal
columns per instance, flattened rather than instanced) in one shared
`klayout.db` canvas -- not GDS-level `CellInstArray` placement of 8
already-built leaf/composite cells (see `div23_cell.py`'s own module
docstring, and `dff_tg_3v3.py`'s own precedent, itself citing
`layout/pll_top/lock_detector/`'s style for the same flat-macro-composition
approach generalized to `divider_chain`'s vertical-flow device convention).

## One frame for every column: the row-cell baselines, not `dff_tg_3v3`'s own

`dff_tg_3v3.py` drew its 10 columns with `devgen.draw_column()`, starting
every column at `y0=0.0` -- correct there because every one of its columns is
exactly one nfet then one pfet. This composite also includes
`nand3_3v3`/`nand2_3v3`/`inv2x_3v3` instances, whose own device tables are
not always "one nfet then one pfet" -- `nand3_3v3`'s column 0 is three series
nfets *then* one pfet, and its columns 1/2 are a single pfet each with no
nfet below it. So every column here is instead drawn with its own pulldown
branch (if any) starting at `devgen.ROW_PD_Y0` and its own pullup branch (if
any) starting at `devgen.ROW_PU_Y0` -- the same two fixed baselines
`devgen.build_row_cell()` (issue #307) already proved DRC-clean for exactly
this family's tallest branch. See `div23_cell.py`'s own module docstring
("ONE FRAME FOR EVERY COLUMN") for the full derivation.

## Two real, concretely-observed routing bugs this composite's own bring-up found

Both are beyond what `dff_tg_3v3.py`'s own 2-net-per-location fix already
covered, because this composite's own `nand3_3v3`/`nand2_3v3` instances
introduce columns with *more than 2* distinct nets sharing a natural
location. Full derivation in `div23_cell.py`'s own module docstring
("NET-COLLISION FIX"); this section summarizes the concrete failures for
this evidence record.

### Failure 1: two different nets' Metal3 risers landing 0.05 um apart

A first attempt bucketed every pad by its own *exact* natural x and offset
distinct nets within each such bucket independently -- sufficient for
`dff_tg_3v3.py`'s own columns (every net-collision there involved exactly 2
nets sharing *one* natural location), but not for this composite: a
column's own "channel" (S/D) pads span *two* natural locations (the nfet
branch's own comp-width-driven centre and the pfet branch's own, generally
different, one), and those two locations are sometimes less than one
`NET_OFFSET_STEP_UM` apart on their own (`tgate_3v3`'s 1 um nfet / 2.5 um
pfet gives centres only 0.75 um apart). A net whose own bucket-relative
offset happened to point toward the other bucket landed only 0.05 um from a
different net's own similarly-inward offset from the neighbouring bucket --
82 DRC violations (`M1.1`, `M1.2a`, `M2.2a`, `M3.2a`, `V2.2a`) on the first
build. Fixed by grouping every "channel" pad in a column into *one* combined
group (regardless of which branch/device it is physically on) and routing
every pad of a given net to the same *absolute* target x, computed from one
shared, fixed reference per role -- see `div23_cell.py`'s `CHANNEL_REF_DX_UM`.

### Failure 2: the fix's own gate-role reach crept back to `x0`

Anchoring "channel" at a fixed offset (while still anchoring "gate" at its
own *natural* pad centre, unchanged from the first attempt) resolved Failure
1 down to 14 violations (`M1.1`x4, `M3.2a`x10), all on `nand3_3v3`'s own
column 0 -- the only column with 3 distinct gate nets (`A`/`B`/`C`). With 3
nets, the worst-case rightmost gate target (`natural_centre +
NET_OFFSET_STEP_UM` = `x0 - 0.1`) lands a fraction of a micron from a
*channel* pad's own natural, un-offset left edge, which sits at `x0` itself
(a device's own comp island starts exactly at the column's `x0`) regardless
of how far right the channel anchor is. Fixed by anchoring "gate" at a fixed
offset too (`GATE_REF_DX_UM = -1.7`, not its own natural centre), keeping
the gate role's own worst-case rightmost target a full 1 um clear of `x0`.
This brought the design fully DRC-clean (0 violations).

## Standalone DRC-clean

```bash
python3 -m divider_chain.div23_cell --outdir <workdir>   # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/div23_cell.gds --top div23_cell --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `div23_cell` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

## LVS-clean

A hand-written reference netlist (`div23_cell.spice`), stated independently
of the layout, fully flattened to 60 individual `M` device lines (not 8
`X`-instance calls into `nand3_3v3`/`nand2_3v3`/`inv_3v3`/`dff_tg_3v3`/
`inv2x_3v3`, matching this composite's own flat, non-hierarchical GDS) --
connectivity/sizes derived by hand-expanding
`design/netlist/div23_cell.spice`'s own `X`-instance list against its own
(also flattened, in that same generated file) sub-cell subckt bodies. Each
instance's own internal-only nets (`nand3_3v3`'s `NM1`/`NM2`, each
`nand2_3v3`'s `NMID`, each `dff_tg_3v3`'s `CKB`/`CKBB`/`NM`/`NMA`/`NMB`/`NS`)
are instance-name-prefixed (e.g. `XFQ_CKB`) so the two `dff_tg_3v3`
instances' own internal nodes stay electrically distinct.

```bash
python3 layout/run_pv.py lvs <workdir>/div23_cell.gds <workdir>/div23_cell.spice \
  --top div23_cell --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `div23_cell` LVS (vs. the hand-written flat reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- the extracted netlist (`lvs-clean/div23_cell.cir`)
shows all 60 devices matched (30 `pfet_03v3` + 30 `nfet_03v3`, correct W/L)
and 7 named top-level ports (`VSS`, `MODOUT`, `CKIN`, `CKOUT`, `MODIN`, `P`,
`VDD`) -- the full set of `design/div23_cell.sch`'s own subckt ports, with
every internal net (`SB`, `DQN`, `DQ`, `Q`, `QB`, `NMO`, `DMO`, `MOB`, each
`dff_tg_3v3` instance's own 6 internal nodes, `nand3_3v3`'s `NM1`/`NM2`, and
each `nand2_3v3`'s own `NMID`) correctly extracted as a distinct anonymous
node -- had Failure 1/2 above shipped unfixed, this is exactly where several
of those would have shown up merged into one node instead.

## Footprint and pin locations (Part 5's own acceptance criterion)

Part 5's `divider_chain` top-level assembly instantiates this macro **six
times, identically** -- `design/README.md`'s own note is that keeping the
six instances identical and distinct is what makes a future single-cell
TSPC/E-TSPC swap a one-symbol substitution (see #295's own AC). This macro's
final footprint and pin locations, as built by `div23_cell.build()`
(`layout/pll_top/divider_chain/div23_cell.py`):

| Property | Value |
|---|---|
| Footprint (w x h) | 332.140 x 37.800 um (12554.9 um^2) |
| Footprint box (x0, y0, x1, y1) | (-2.62, -0.3, 329.52, 37.5) um |

| Pin | (x, y) um |
|---|---|
| `CKIN` | (65.5, 0.64) |
| `MODIN` | (-2.4, 4.4) |
| `P` | (-1.0, 2.52) |
| `CKOUT` | (179.6, 1.07) |
| `MODOUT` | (-1.7, 0.64) |
| `VDD` | (1.8, 11.07) |
| `VSS` | (2.5, 0.21) |

These are stable, non-hand-tuned outputs of `div23_cell.build()` -- no
per-instance geometry is adjusted from run to run, so Part 5 can place six
unmodified instances (translation only) rather than six hand-tweaked copies.
`layout/tests/test_divider_div23.py`'s `FootprintStabilityTests` pins these
exact values so a future change to this module that silently shifts them is
caught by CI, not discovered downstream in Part 5.

## Reused from #306/#307/#308 (issue's own acceptance criterion)

Every one of the 8 sub-cell instances is drawn from the exact same device
tables/`COLUMNS` those modules already ship and already proved DRC/LVS-clean
standalone -- `nand3_3v3.COLUMNS`, `nand2_3v3.COLUMNS` (x2, with distinct
port maps for `XN2Q`/`XN2M`), `inv_3v3.INV_DEVICES` (x2), `inv2x_3v3.COLUMNS`,
and `dff_tg_3v3.INSTANCES` (x2, with distinct boundary/internal-net maps for
`XFQ`/`XFMO`). No device geometry (W/L) is re-derived or copied by hand;
only net names are translated per instance -- see `div23_cell.py`'s own
`placements()`.

## Friction-protocol note

No new `klt` capability gap was hit building this composite -- the same gap
already filed and cited by #306/#308 (`2AMLogic/klayout-tools#1575`,
`klt gen`/`klt gen-compose` failing gf180mcu's real signoff deck rule
families) covers why this module draws direct `klayout.db` geometry instead;
nothing about this issue's own cross-role net-collision bring-up (see
"Two real, concretely-observed routing bugs" above) is a tool gap -- it is
this module's own routing-fabric logic, fixed in `div23_cell.py` itself, not
upstream.
