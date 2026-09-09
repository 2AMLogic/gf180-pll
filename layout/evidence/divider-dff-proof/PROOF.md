# `dff_tg_3v3` -- transmission-gate master-slave flop composite layout (issue #308)

Part 3 of #295. This is the first `divider_chain` **composite** built from
#306's leaf-cell generators -- 6x `inv_3v3` + 4x `tgate_3v3`, 20 transistors
total, wired exactly per `design/netlist/dff_tg_3v3.spice`'s own
`dff_tg_3v3` subckt (a classic transmission-gate master-slave D flip-flop:
clock/clock-bar generation, then two TG-latch stages, each a feedback
inverter pair gated by a pass transistor pair). This cell is the flop every
`div23_cell` instance uses twice, and `divider_chain`'s own retiming flop
`XFRT` uses once (Part 4, not built here).

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean 20-transistor composite
layout, assembled as a flat macro composition of ten leaf-cell instances (six
`inv_3v3`, four `tgate_3v3`) in one shared `klayout.db` canvas -- not GDS-level
`CellInstArray` placement of ten already-built leaf cells (see
`dff_tg_3v3.py`'s own module docstring, and `layout/pll_top/lock_detector/`'s
precedent for the same flat-macro-composition style, generalized here to
`divider_chain`'s vertical-flow (current-flows-vertically) device convention
instead of `lock_detector`'s horizontal-flow one).

## Why a composite macro needs its own routing fabric

`devgen.build_stack_cell()` (issue #306) resolves a net by counting how many
of *that one column's own* 1-2 device terminals share its name -- correct for
a standalone leaf cell, where every net is genuinely local to that column.
Every net in this composite except each instance's own supply pins fans out
*across* instances (`CKB`/`CKBB` alone each reach four separate
transmission-gate instances) -- outside what a per-column, Metal1-only,
at-most-2-terminal resolver can wire.

The fix, added to `devgen.py` for this issue: `draw_column()` (the bare
per-instance drawing step `build_stack_cell()` already performed internally,
now exposed standalone with no per-column net resolution), plus a Metal2/3
routing fabric (`route_net()`/`NetTracks()`) -- every device pad rides its
own dedicated Metal3 riser up to a Metal2 bus unique to that net, the same
fabric `lock_detector/primitives.py` already proved out for its own
(horizontal-flow) composite macros, generalized here for
`divider_chain`'s vertical-flow columns.

## Two real, concretely-observed routing bugs this composite's own bring-up found

Both are documented in full (derivation, exact numbers, the extracted
netlist that caught each one) in `devgen.py`'s `offset_pad_x()` docstring and
`dff_tg_3v3.py`'s own module/constant docstrings; this section summarizes the
concrete failures for this evidence record.

### Failure 1: every device's own top/bottom pad pair -- and every `tgate_3v3` instance's independent gate pads -- collapsed into one shorted node

`devgen.mosfet()` places a device's *top* and *bottom* terminal pads (and, for
a column whose two devices have independent gate nets -- every `tgate_3v3`
instance) its two *gate* pads at the exact same x: current flows through one
vertical comp island, so a device's own drain/source terminals are
necessarily the same comp's top and bottom, same x by construction. That is
invisible to a *standalone* leaf cell (`build_stack_cell()` only ever wires
one net per pad, with a plain same-column Metal1 run), but a real bug for a
composite's per-pad Metal3-riser fabric: two *different* nets' risers landing
at the same x draw overlapping same-layer Metal3 -- not a DRC violation (no
via, no spacing check trips), but a silent short.

The first, unoffset attempt at this composite hit this squarely: LVS
extracted a netlist with `D`/`Q`/`QB`/`VDD`/`VSS` all merged into one node
(`D|Q|QB|VDD|VSS`), and several devices' widths summed together into
apparent single wide transistors (a Metal3-riser short manifesting as a
merged node, not a DRC-visible geometry error) -- e.g.:

```spice
.SUBCKT dff_tg_3v3 CK D|Q|QB|VDD|VSS VSS
M$1 D|Q|QB|VDD|VSS D|Q|QB|VDD|VSS D|Q|QB|VDD|VSS D|Q|QB|VDD|VSS pfet_03v3
+ L=0.28U W=22.5U ...
```

Fixed with `devgen.offset_pad_x()`: every top pad and every `pfet`'s gate pad
gets routed from a point offset 0.75 um from its own natural pad center
(extending the pad's own Metal1 -- same net, guaranteed overlap -- only when
the natural pad is not already wide enough to keep a via there fully
enclosed), leaving bottom pads and `nfet` gate pads at their natural center.
0.75 um clears M3.2a's 0.28 um minimum Metal3 spacing against the
now-distinct sibling riser with real margin (0.41 um clear).

### Failure 2: the offset fix's own reach nearly shorted a periodic n-well tap, then a next-column gate pad (two DRC-visible violations, sequentially)

A first attempt at Failure 1's fix used a larger, unconditional 1.0-1.3 um
Metal1 extension regardless of whether the pad needed it. That reached far
enough into the inter-column gap to overlap the periodic n-well tap's own
Metal1 pad by ~0.01 um -- an M1.1 (minimum metal1 width) violation from the
razor-thin sliver where the two nearly-but-not-quite-aligned rectangles met.
Fixed by making `offset_pad_x()` extend only the minimum needed to enclose
the *target* via position (nothing at all for a `pfet` pad, whose own
W=2.5 um footprint already encloses a via 0.75 um off-center; a small
extension only for the narrower `nfet` pads).

That fix in turn revealed a second, DRC-visible collision: the *next*
column's own offset `pfet` gate-pad reach and the periodic tap pair's own
offset (`VSS`'s ptap, needed for the same same-x-different-net reason as
Failure 1, between the tap pair's own ntap and ptap) closed to within 0.24 um
of each other -- 27 M3.2a (min. metal3 spacing 0.28 um) violations. Fixed by
widening `COLUMN_PITCH_UM` from 7.0 to 9.0 um and anchoring the periodic tap
pair's own x at a fixed margin past the *left* column's rightmost reach
(`_tap_positions()`), rather than the gap's geometric midpoint -- which
otherwise drifts closer to whichever side reaches furthest, exactly the
failure mode observed.

## Standalone DRC-clean

```bash
python3 -m divider_chain.dff_tg_3v3 --outdir <workdir>   # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/dff_tg_3v3.gds --top dff_tg_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `dff_tg_3v3` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

## LVS-clean

A hand-written reference netlist (`dff_tg_3v3.spice`), stated independently
of the layout, fully flattened to 20 individual `M` device lines (not 10
`X`-instance calls into `inv_3v3`/`tgate_3v3` subckts, matching this
composite's own flat, non-hierarchical GDS) -- connectivity/sizes derived by
hand-expanding `design/netlist/dff_tg_3v3.spice`'s own `X`-instance list
against its own (also flattened, in that same generated file)
`inv_3v3`/`tgate_3v3` subckt bodies. `design/netlist/dff_tg_3v3.spice` itself
is also usable directly as an LVS reference (it is self-contained -- both
subckt bodies are inlined by `design/netlist.sh`'s own expansion); this
module's own hand-written, independently-stated flat netlist is used instead
for the same "layout and reference stated independently" discipline
`inv_3v3.py`/`tgate_3v3.py` already established.

```bash
python3 layout/run_pv.py lvs <workdir>/dff_tg_3v3.gds <workdir>/dff_tg_3v3.spice \
  --top dff_tg_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `dff_tg_3v3` LVS (vs. the hand-written flat reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- the extracted netlist (`lvs-clean/dff_tg_3v3.cir`)
shows all 20 devices matched (10 `pfet_03v3` + 10 `nfet_03v3`, correct
W/L), 6 named top-level ports (`VSS`, `D`, `Q`, `QB`, `VDD`, `CK`) and **six
distinct anonymous internal nodes** (`$3`-`$8`, matching `CKB`/`CKBB`/`NM`/
`NMA`/`NMB`/`NS`) -- the exact thing Failure 1 above shows going wrong when
it isn't (there, several of these collapsed into one node).

## Row height / pitch consistency (this issue's own acceptance criterion)

Every instance is drawn from the *same* two device tables
(`inv_3v3.INV_DEVICES`/`tgate_3v3.TGATE_DEVICES`, issue #306), stacked
bottom-to-top in the same order (NMOS then PMOS) with the same gaps -- so
every instance's own NMOS/PMOS y-bands land at the identical y regardless of
which of the two device tables it uses (NMOS at y in `[0, 1.28]`, PMOS at y
in `[5.28, 6.56]`), needed for Part 4's `div23_cell` composite, which places
two of these.

## Reusable additions to `devgen.py`

- `draw_column()` -- the bare per-column drawing step, extracted from
  `build_stack_cell()` (which now calls it internally; no behaviour change,
  covered by the pre-existing `layout/tests/test_divider_devgen.py` suite
  still passing unmodified).
- `route_net()`/`NetTracks`/`pad_center()`/`bbox_union()`/`nwell_over()` --
  the Metal2/3 composite-routing fabric, generalized from
  `lock_detector/primitives.py`'s own proven-DRC-clean version for this
  package's vertical-flow (not horizontal-flow) pad convention: one riser
  per pad, unconditionally, rather than that module's own close-pad merge
  optimization (see `devgen.py`'s "Composite-macro routing fabric" docstring
  section for why the merge optimization is actually *wrong*, not just
  unnecessary, for this package's own device geometry).
- `offset_pad_x()` -- the same-x riser-collision fix (Failure 1/2 above).
- `well_tap()` -- made public (was `_well_tap`), reused directly by this
  composite's own periodic tap placement instead of `build_stack_cell()`'s
  one-tap-per-column convention.

`layout/tests/test_divider_dff.py` covers the instance table (wiring matches
the netlist), the reference netlist's own device/port counts, and
`offset_pad_x()`'s two code paths (extend vs. no-extend) at the pure-Python/
geometry level; the actual DRC/LVS-clean claim needs the PDK's own signoff
decks and is this file's job, not the unit tests'.

## Friction protocol (CLAUDE.md)

No new `klayout-tools` capability gap this pass -- both failures documented
above are this module's own composite-routing-logic bugs (found and fixed in
this repo's code via DRC/LVS iteration), not a `klt` capability gap. Per
issue #306's own acceptance criteria (inherited here), the already-known
`klt gen`/`klt gen-compose` signoff-DRC gap (2AMLogic/klayout-tools#1575,
filed via #299) is not re-filed here.

## Provenance

| | |
|---|---|
| Generated | 2026-09-09T01:10 UTC |
| Invoked as | `python3 -m divider_chain.dff_tg_3v3 --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`/`lvs` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--lvs_sub=VSS` |

## Artifacts

| Path | What it is |
|---|---|
| `dff_tg_3v3.gds` | the real 20-transistor composite layout (6x `inv_3v3` + 4x `tgate_3v3`, flat macro composition) |
| `dff_tg_3v3.spice` | the hand-written, independently-stated, fully-flattened LVS reference netlist |
| `drc-clean/dff_tg_3v3_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr |
| `lvs-clean/dff_tg_3v3.cir` | the extracted netlist (20 matched devices, 6 named ports, 6 distinct internal nodes) |
| `lvs-clean/dff_tg_3v3.lvsdb` | KLayout LVS report database |
| `lvs-clean/lvs.stdout.log` | captured `run_lvs.py` stdout+stderr, including the match verdict |

Regenerate via `python3 -m divider_chain.dff_tg_3v3 --outdir <dir>` (from
`layout/pll_top/`) + `layout/run_pv.py drc`/`lvs`; do not hand-edit any file
under this directory.
