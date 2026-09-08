# `tgate_3v3` -- full-custom device-layout methodology proof, `divider_chain` (issue #306)

Part 1 of #295. This is the topology issue #299 (Part 1 of #294, the
PFD/CP block family) did not cover: a complementary transmission gate,
whose two pass devices (`pfet_03v3`, `nfet_03v3`) share both diffusion
terminals (`A`, `Y`) but have *independent* gates (`GP`, `GN`) and bodies
tied to the supplies rather than to either diffusion terminal. See
`layout/evidence/divider-inv-proof/PROOF.md` for this issue's other cell,
`inv_3v3` -- the static-CMOS-inverter case, which needed no generator
change at all.

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean transistor-level layout of
`design/tgate_3v3.sch` -- one `pfet_03v3` (W=2.5 um/L=0.28 um) + one
`nfet_03v3` (W=1 um/L=0.28 um) pass devices, independent gates `GN`/`GP`,
shared `A`/`Y` diffusion terminals, bodies tied to `VDD`/`VSS` -- drawn from
scratch via direct `klayout.db` geometry
(`layout/pll_top/divider_chain/devgen.py`), not `klt gen`/`klt gen-compose`
(a confirmed, already-filed dead end for this whole methodology,
2AMLogic/klayout-tools#1575 -- not re-filed here per issue #306's own
acceptance criteria).

## The Curator's prediction, and what running LVS actually found

Issue #306's own Curator update predicted, from reading
`pfd_cp/devgen.py`'s `Device`/`build_stack_cell()` shape (not running it),
that a transmission gate needed **no** structural change: `gate_net` is
already independent per device, and `top_net`/`bottom_net` are already
matched by string equality. That prediction turned out to be **incomplete
on two separate points** -- both found only by actually drawing this cell
and running the real signoff LVS deck against it, not by re-reading the
dataclass. Both are documented in full, with the derivation and the exact
constants, in `layout/pll_top/divider_chain/devgen.py`'s own module
docstring ("TRANSMISSION-GATE TOPOLOGY" section); this file summarizes the
concrete, reproduced failures that section explains and the fixes that
resolved them.

### Failure 1: the PMOS body tie shorted onto a signal net (found by design review, confirmed by re-deriving the tap-wiring code path)

`build_stack_cell()`'s inherited well-tap wiring always ties the n-well tap
to the topmost pfet's own `top_net` -- correct for `inv_3v3` (the PMOS
source *is* `VDD`), but `tgate_3v3`'s PMOS pass device has no supply-net
terminal at all (`top_net`/`bottom_net` are the signal nets `Y`/`A`).
Reusing that fallback unmodified would draw a Metal1 wire physically tying
the n-well tap (and therefore the PMOS body) onto a diffusion signal net:
DRC-legal (two overlapping same-layer shapes are not a DRC violation) but a
real LVS-incorrect short. Fixed with a new optional `Device.body_net` field
(default `None`, preserving the old fallback byte-for-byte for every
existing caller) that names the net a device's body ties to, independent of
its diffusion terminals. `tgate_3v3.py`'s device table sets it explicitly:
`body_net="VDD"` for `MP`, `body_net="VSS"` for `MN`.

### Failure 2: the two diffusion nets' own wiring merged into one node (found by actually running the LVS deck -- twice)

A static inverter's two devices only ever need *one* 2-terminal net resolved
between them (`Y`); a transmission gate's two devices instead have *two*
2-terminal nets (`A` and `Y`) across the same two devices, and only one
possible net/terminal assignment lets both be wired with
`build_stack_cell()`'s existing straight-line connector: the one where the
*facing* pads (the two devices' adjacent pads across the inter-device well
gap) share a net. The other net ends up on the stack's two *outermost*,
non-facing pads -- and a naive straight-line connect between those runs
directly through the facing net's own connector and the intervening gates,
physically merging both nets into one.

This was not a hypothetical: the first working attempt at this cell's
device table used a plausible-looking, but wrong, net assignment
(`top_net="Y"`, `bottom_net="A"` on *both* devices) that put `A` and `Y` on
each device's *facing* pads for one device but not the other. It drew
DRC-clean and then **failed real LVS**, with the extracted netlist showing
both drain and source of both devices collapsed onto one node:

```spice
.SUBCKT tgate_3v3 GN GP VDD VSS
M$1 $2 GP $2 VDD pfet_03v3 L=0.28U W=2.5U ...
M$2 $2 GN $2 VSS nfet_03v3 L=0.28U W=1U ...
.ENDS tgate_3v3
```

(`$2` on both D and S of both devices -- `A` and `Y` merged into one net.)
A first fix attempt (a bypass lane routed to the *left*, clear of the gate
poly tabs) hit a second, distinct problem when actually DRC/LVS-run: this
cell's two devices have different widths (`nfet_03v3` W=1 um,
`pfet_03v3` W=2.5 um), and a device's own S/D pad can vertically overlap
that *same* device's own gate pad (they only avoid touching in the real
cell because they sit at different x, not because their y ranges are
disjoint) -- so a left-side jog reaching in at a naive y clipped the gate
pad, again merging nets that must stay separate (this time `GN`/`GP` with
the bypassed net). Both failures are captured concretely, with actual
extracted-netlist excerpts, in `devgen.py`'s own module docstring.

The fix that actually passed, in both DRC and LVS: (a) get the net
assignment right -- `MN.top_net`/`MP.bottom_net` (the true facing pair)
share `"Y"`; `MN.bottom_net`/`MP.top_net` (the stack's outer pads) share
`"A"` -- and (b) route `"A"` via `build_stack_cell()`'s new `bypass_nets`
argument, a dedicated Metal1 lane on the *right* side of the widest
device's own drawn edge (clear of every gate pad, which are exclusively on
the left, and clear of every device's own footprint regardless of width,
since nothing this module draws for any device extends past that device's
own comp/pad right edge).

## Standalone DRC-clean

```bash
python3 -m divider_chain.tgate_3v3 --outdir <workdir>   # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/tgate_3v3.gds --top tgate_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `tgate_3v3` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

(Two earlier, uncommitted attempts at this same cell -- the merged-node
device table above, and the left-side-lane fix's gate-pad clip -- are what
Failures 1/2 document; neither was ever a committed "clean" result. The
committed GDS is the version that passed both decks on the same run.)

## LVS-clean

A hand-written reference netlist (`tgate_3v3.spice`), stated independently
of the layout, device sizes read directly off `design/tgate_3v3.sch`,
written drain-gate-source-body per device (`nfet_03v3`/`pfet_03v3` are
symmetric under gf180mcu's own extraction, so LVS matches by graph
topology, not by which terminal is labelled D vs. S here):

```spice
.subckt tgate_3v3 A Y GN GP VDD VSS
M_MP Y GP A VDD pfet_03v3 W=2.5u L=0.28u
M_MN Y GN A VSS nfet_03v3 W=1u L=0.28u
.ends
```

```bash
python3 layout/run_pv.py lvs <workdir>/tgate_3v3.gds <workdir>/tgate_3v3.spice \
  --top tgate_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `tgate_3v3` LVS (vs. the hand-written reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- the extracted netlist (`lvs-clean/tgate_3v3.cir`)
shows two real matched devices with **two distinct internal nodes** for
`A`/`Y` (`$3`/`$4` below), the exact thing Failure 2 above shows going wrong
when it isn't:

```spice
.SUBCKT tgate_3v3 GN GP VDD VSS
M$1 $4 GP $3 VDD pfet_03v3 L=0.28U W=2.5U AS=1.25P AD=1.25P PS=6U PD=6U
M$2 $3 GN $4 VSS nfet_03v3 L=0.28U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
.ENDS tgate_3v3
```

`GN`/`GP` are labelled top-level pins (each is a 1-terminal net in this
device list); `A`/`Y` are not (2-terminal, wired internally, matched by
topology, same convention `inv_3v3`/`pfdcp_inv_3v3` already use).

## Reusable helper module

`layout/pll_top/divider_chain/devgen.py` -- reused/generalized from
`layout/pll_top/pfd_cp/devgen.py`, with two new opt-in additions this cell
needed and `inv_3v3.py` does not: `Device.body_net` and
`build_stack_cell()`'s `bypass_nets` (+ the new `_bypass_wire()` router).
Both default to the pre-existing behaviour when unused, so `inv_3v3`'s
generated GDS is unaffected. Full derivation, the concrete failures each
one fixes, and the exact geometry/clearance math for the bypass lane are in
that module's own docstring.

`layout/tests/test_divider_devgen.py` covers both cells' device tables
(including the facing-vs-outer net assignment this file's "Failure 2"
section is about) and the bypass-lane/body-net code paths at the
pure-Python (device-table) level; the actual DRC/LVS-clean claim needs the
PDK's own signoff decks and is this file's job, not the unit tests'.

## Friction protocol (CLAUDE.md)

No new klayout-tools gap this pass -- both failures documented above are
this module's own wiring-logic bugs (found and fixed in this repo's code),
not a `klayout-tools` capability gap. Per issue #306's own acceptance
criteria, the already-known `klt gen`/`klt gen-compose` signoff-DRC gap
(2AMLogic/klayout-tools#1575, filed via #299) is not re-filed here.

## Provenance

| | |
|---|---|
| Generated | 2026-09-08T23:36 UTC |
| Invoked as | `python3 -m divider_chain.tgate_3v3 --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`/`lvs` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--lvs_sub=VSS` |

## Artifacts

| Path | What it is |
|---|---|
| `tgate_3v3.gds` | the real transistor-level leaf cell (1 pfet_03v3 + 1 nfet_03v3 pass devices, independent gates, bypass-routed shared diffusion, tapped) |
| `tgate_3v3.spice` | the hand-written, independently-stated LVS reference netlist |
| `drc-clean/tgate_3v3_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr |
| `lvs-clean/tgate_3v3.cir` | the extracted netlist (two matched devices, two distinct A/Y internal nodes) |
| `lvs-clean/tgate_3v3.lvsdb` | KLayout LVS report database |
| `lvs-clean/lvs.stdout.log` | captured `run_lvs.py` stdout+stderr, including the match verdict |

Regenerate via `python3 -m divider_chain.tgate_3v3 --outdir <dir>` (from
`layout/pll_top/`) + `layout/run_pv.py drc`/`lvs`; do not hand-edit any file
under this directory.
