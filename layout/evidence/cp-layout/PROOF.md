# `cp_output_stage` — the assembled charge-pump output stage (issue #321)

Part 3c of #294's device-layout methodology — the last of #301's three
decomposition steps (Part 3a #319, Part 3b #320, Part 3c #321), and the
evidence directory #301's own acceptance criteria named.

## What this is

One flat, standalone-DRC-clean GDS of `design/cp.sch`'s complete output
stage, minus the dump buffer:

* **`cp_array`** (#320) — the 4× `cp_leg_n` / 4× `cp_leg_p` common-centroid
  arrays and their 4×-scaled bias branches (`MBN`/`MCN`, `MBP`/`MCP`),
  placed unmodified at the block's own origin.
* **Four glue inverters** `xi_b0` / `xi_b1` / `xi_up` / `xi_dn` — four GDS
  placements of #299's already-proven `pfdcp_inv_3v3` leaf, producing
  `B0B` / `B1B` / `UPB` / `DNB`.
* **Six steering/dump switches** `MSWDN` / `MDMPDN` / `MDUMN` / `MSWUP` /
  `MDMPUP` / `MDUMP` — single `nfet_03v3` / `pfet_03v3` devices drawn with
  `devgen.mosfet()`, every W/L and every terminal net read directly off
  `design/cp.sch`'s own instance parameters and `lab_pin` labels
  (`MSW*`/`MDMP*` W=6u/L=0.3u; `MDUM*` W=3u/L=0.3u with both diffusions on
  `VOUT`).
* **The wiring `cp_array` deliberately left undone**: `B0`/`B0B`/`B1`/`B1B`
  and the `VDD`/`VSS` rails are tied across the N and P polarities here for
  the first time (Part 3b routes each side independently and says so), and
  the `DNT`/`UPT` tails reach their steering switches.

`VDUMP` is a **stub pin**: `MDMPDN`'s and `MDMPUP`'s drains meet on it and
nothing else touches it. `cp_dumpbuf` (`xbuf`) is Part 4 (#302) and wiring
`VDUMP` to it is Part 5 (#303) — out of scope here per #321's own text. The
extracted connectivity below confirms the stub is genuinely isolated rather
than accidentally wired.

Boundary pins are exactly the twelve `design/cp.sch` declares as `ipin`/
`iopin`, plus `VDUMP`: `UP`, `DN`, `B0`, `B1`, `IBN`, `ICN`, `IBP`, `ICP`,
`VOUT`, `VDD`, `VSS`, `VDUMP`.

| | |
|---|---|
| Footprint (as drawn) | **117.810 × 66.725 µm** (7,860.87 µm² ≈ 0.0079 mm²) |
| Devices | 8 composite legs + 4 bias devices (from `cp_array`) + 4 inverters (8 devices) + 6 switches |
| Top cell | `cp_output_stage`, flat |

## ✅ Inherited connectivity defect — fixed (issue #359)

**This block once shipped alongside a real, pre-existing short in the
`cp_array` sub-block it assembles. That defect is now fixed; this section
records what it was and how it was closed, for provenance.**

At landing time, running the connectivity check described further down
against **Part 3b's own standalone `cp_array` GDS** — no change from this
increment involved — reported six cross-net shorts:

```
connectivity FAILED: shorts=B0+B0B; B1+B1B+VDD+VSS
```

inherited verbatim by this block. A DRC deck could not see them: two Metal3
runs sharing one X merge into a single polygon that is legal by every
width/space rule in the deck — the same class of defect issue #322 found in
`lock_detector`, where 114 real shorts survived a clean DRC run.

**Root cause.** `cp_array.declutter_riser_x()` collapsed two riser
candidates that shared an *exact* natural X onto one column, justified by an
invariant its own docstring stated — "two risers at the literal same natural
X only ever occur here when two pads of the *same* net share an identical
local-X translation". That invariant was false twice over:

1. `cp_leg_n`/`cp_leg_p` place their `EN` and `ENB` gate-tab pads at the
   *same* local X (both hang off the same left-aligned poly end-cap, one
   above the other — confirmed directly: both pads' centres are at
   x = −0.800 µm). So `xn_t0`'s `B0` and `B0B` landed on one column.
2. The tripod places `t1b` directly above `base`, so `xn_base`'s `EN`/`ENB`
   (tied `VDD`/`VSS`) landed on `xn_t1b`'s `EN`/`ENB` (`B1`/`B1B`) — which is
   how `VDD` ended up shorted to `VSS`.

**Why the obvious one-line fix was not one.** Making the tie rule net-aware
alone did not fix it: the nudge it then applies pushes a gate-tab riser 1 µm
to the right, whose Via1 landing pad lands on the leg's own `VBN` pad
(0.07 µm of Metal1 clearance, i.e. an `M1.2a` violation *and* a different
short). It changed Part 3b's proven-DRC-clean geometry and its recorded
evidence, so it was tracked as its own issue against #320 — **#359** — per
the Builder scope rule ("do not fix pre-existing issues in other files —
file a separate issue"), rather than folded into this increment.

**The fix, as landed (issue #359).** An explicitly-allocated riser column
per net, reached by a checked Metal1 escape — the same scheme this module
already used for its own glue block (see "Riser columns are hand-placed and
proven, not decluttered" below), now ported to the array's own pads:
`cp_array.declutter_riser_x()`'s exact-tie collapse is net-aware (a same-X
tie only collapses when the two points are also the same net), every leg's
own gate-tab pins reach their riser column through an explicit escape
rather than their raw natural X, and `cp_array.check_riser_columns()` now
asserts — on every build, not just in a docstring — that the decluttered
plan never puts two nets on one column. Full account:
`cp_array.py`'s own module docstring, "EN/ENB SHARE ONE GATE-TAB COLUMN",
and `evidence/cp-array-proof/PROOF.md`'s own "Post-landing fix" section.

Re-running the same standalone `cp_array` check now reports clean (full
log: `connectivity/cp_array.netcheck.log`):

```
connectivity clean: 18 nets, no shorts, no splits
```

The defect was pinned exactly as `cp_output_stage.INHERITED_ARRAY_SHORTS`
and asserted by `layout/tests/test_cp_output_stage.py`, so it could neither
grow silently nor be forgotten — that constant is now `()`, and the test
that once asserted the six shorts now asserts there are none, exactly as
its own docstring always said it would (`layout/tests/test_cp_array.py`
additionally gained a `check_riser_columns` regression test, in scope of
this issue's own acceptance criteria, so the class of defect cannot
silently reappear).

**What was never affected**: every net this increment itself wires
(`UP`/`UPB`/`DN`/`DNB`/`VOUT`/`VDUMP`/`DNT`/`UPT`/`IBN`/`ICN`/`IBP`/`ICP`)
already came back on its own distinct extracted net, and no probed net was
*open* — the positive proof that the array↔glue link columns worked even
while the array's own internal routing did not.

## Connectivity is checked, not assumed

`layout/pll_top/pfd_cp/netcheck.py` (new here) extracts the finished GDS's
own Metal1/Via1/Metal2/Via2/Metal3 connectivity with KLayout and resolves a
set of probe points — every Metal1 landing pad the generator believes is on
each net, including the array's own pins on **both** polarities. Two nets
that come back on one extracted net are shorted; one net that comes back on
several is open.

Comp and Poly2 are deliberately excluded: a MOSFET's comp island spans
source, gate and drain, so a model that conducts through comp merges every
device's own diffusion terminals — which is why real LVS extracts devices
first. Running the real deck is `layout/run_pv.py lvs`'s job, and needs a
reference netlist this block does not yet have (see below).

```bash
python3 -m pfd_cp.cp_output_stage --outdir <workdir>   # (from layout/pll_top/)
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| Every probe point lands on real metal | yes | yes (0 unresolved) | **PASS** |
| No net is open (`splits`) | none | none | **PASS** |
| This increment's own wiring short-free | yes | yes | **PASS** |
| `VDUMP` isolated from every other net | yes | yes | **PASS** |
| Shorts present | none | none | **PASS** (fixed, issue #359 — see above) |

Full log: `connectivity/cp_output_stage.netcheck.log`.

## Standalone DRC-clean

```bash
python3 -m pfd_cp.cp_output_stage --outdir <workdir>       # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/cp_output_stage.gds \
        --top cp_output_stage --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_output_stage` DRC, table `main` (default, no `--offgrid`) | clean | `DRC clean: cp_output_stage (D), 0 violations` | **PASS** |
| `cp_output_stage` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: cp_output_stage (D), 0 violations` | **PASS** |

Every table in the `main` deck ran. Rule families this block's own new
geometry exercises on top of `cp_array`'s: `DF.3a_LV`/`DF.6_LV`/`DF.16_LV`
(comp space, gate overhang, n-well-to-NMOS clearance across the switch row's
own well boundary), `PL.4_LV`/`PL.5a_LV`/`PL.5b_LV` (poly endcap/field
spacing on the six switches' gate tabs), `CO.*`, `NP.*`/`PP.*`,
`NW.1a_LV`/`DF.4c_LV`/`DF.13_LV`/`DF.14_LV` (the switch row's substrate and
n-well tap strips — each spans its own group's full X range, per
`cp_array._tap_strip()`'s 20 µm tap-distance argument), `M1.1`/`M1.2a`
(the Metal1 escapes), `M2.1`/`M2.2a`, `M3.1`/`M3.2a` (the glue channel and
the array↔glue link columns), `V1.*`/`V2.*`.

## No LVS claim, and why

This block is a strict *subset* of `design/cp.sch` — `xbuf` (`cp_dumpbuf`)
is excluded by #321's own scope — so an LVS run against that schematic's
netlist would legitimately mismatch on the dump buffer's thirteen devices.
The complete-circuit LVS belongs to Part 5 (#303), where `xbuf` lands and
the block finally corresponds 1:1 to `cp.sch`. Until then the connectivity
check above — now clean end to end, including the array's own routing
(issue #359, see above) — is the electrical claim this evidence directory
makes.

## How this block reaches `cp_array`'s nets

`cp_array` has already mesh-routed every one of its own nets, so each of its
Metal1 pads already carries a Via1/Metal2/Via2/Metal3 stack. Landing a
*second* via stack on one of those pads — the obvious way to "connect to a
pin" — merges two via squares into one oversized shape (`V1.1`/`V2.1` make
the via size a min *and* a max) and puts two Metal2 landings a fraction of a
micron apart. Spacing rules are purely geometric; being the same net buys
nothing.

So this block reaches each array net through the **end of its Metal2 bus**
instead, which `cp_array` now reports as `CpArrayLayout.n_bus`/`p_bus`
(`net -> (track_y, x_lo, x_hi)`). That is the one change this increment makes
to Part 3b: it records coordinates the router already computed, draws no
geometry, and leaves `cp_array`'s own GDS byte-identical. Each shared net's
bus is extended sideways into empty space, this block's own glue track is
extended to the same column, and the two are joined by a plain Metal3
vertical. **N-side buses extend left and P-side right, never across each
other** — the two sides get independent channels based on their own heights,
so an N net's track and a P net's track can coincide in Y by coincidence,
and two same-Y Metal2 runs overlapping in X would be a silent short.

## Riser columns are hand-placed and proven, not decluttered

`cp_array.declutter_riser_x()` is safe *there* only under the invariant the
defect section above shows to be false. Rather than depend on it, this block
places every device in **one row** (so X is monotonic) and gives every riser
an explicitly chosen column:

* a device's gate pad and top pad already sit >1 µm apart in X, so they rise
  where they are;
* a device whose top and bottom terminals are *different* nets escapes its
  bottom pad sideways on Metal1 past its own comp — a switch's source and
  drain pads share one X by construction, which is exactly the different-net
  tie that broke the array;
* `MDUMN`/`MDUMP` (both diffusions on `VOUT`) need no escape — two risers at
  one X on *one* net is the case that really is safe;
* each glue inverter's `Y`/`VSS`/`VDD` pins escape right onto three columns
  2.0/3.5/5.0 µm from its own origin.

`cp_output_stage.check_riser_columns()` then asserts arithmetically, on every
build, that no two nets share a column and that no two columns are closer
than the 1 µm riser pitch — i.e. that running `declutter_riser_x()` over the
result would be the identity. `check_escape_clearance()` likewise asserts
that every escape landing clears the next device's own gate pad, which is
what `SWITCH_DEVICE_GAP_UM` exists to buy.

## Automated test coverage

`layout/tests/test_cp_output_stage.py` (54 tests; the whole
`layout/tests` suite is 501 tests, all passing,
`python3 -m unittest discover -s layout/tests -t layout/tests`):

* **Pure-Python, no `klayout.db` needed** — `SWITCH_DEVICES_N`/
  `SWITCH_DEVICES_P` match `design/cp.sch`'s own six instances (kind, W, L,
  and all three terminal nets each), including that schematic's own
  equal-width-not-mobility-scaled rule and the half-width dummies' both-on-
  `VOUT` diffusions; `GLUE_INVERTERS` match `xi_b0`/`xi_b1`/`xi_up`/`xi_dn`;
  the boundary/internal net split is disjoint and covers every device
  terminal (so a typo cannot invent a net); `VDUMP` is reached only by
  `MDMPDN`/`MDMPUP`; `switch_row_x()` places every device once, monotonic,
  non-overlapping, at its schematic width, with the well-boundary gap;
  `check_escape_clearance()` passes on the real row and *raises* on a
  deliberately packed one; `gate_pad_center_x()` is re-derived independently
  from `devgen`'s own constants; `check_riser_columns()` accepts a same-net
  shared column, rejects a two-net column, rejects an under-pitch pair, and
  passes on the real row's columns re-derived from the placement functions
  alone; `link_columns()`; `netcheck`'s report/probe-point surface.
* **`klayout.db`-gated** (skipped, not failed, without a PV environment) —
  the footprint encloses both the array and the glue block; the glue block
  clears the array's own routing channel by `GLUE_GAP_UM`; the boundary pin
  set is exactly the twelve declared, one pad each, with no internal net
  promoted; all six switches are drawn at their schematic W and L; all four
  inverters sit on one row at the stated pitch; the *built* block's riser
  columns need no declutter; a link column exists for every shared net on
  each side, all distinct and at least a pitch apart, outside the block;
  the trim/rail nets are linked on both polarities and the tail nets on
  their own polarity only.
* **`klayout.db`-gated connectivity** — the extracted Metal1-3 graph has no
  unresolved probe, no open net, no short anywhere (this increment's own
  wiring, and — since issue #359 — `cp_array`'s own inherited routing too),
  a genuinely isolated `VDUMP`, and an empty short set, matching
  `INHERITED_ARRAY_SHORTS` now being `()`.

`layout/tests/test_cp_array.py` additionally gains coverage of Part 3b's new
`n_bus`/`p_bus` export (one span per routed net, above its own side's block,
one track per net).

## Provenance

| | |
|---|---|
| Generated | 2026-09-09T11:48 UTC (regenerated for issue #359) |
| Invoked as | `python3 -m pfd_cp.cp_output_stage --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`, `LAYOUT_PV_PYTHON` pointed at a local venv (`klayout` + `docopt`) per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |

## Artifacts

| Path | What it is |
|---|---|
| `cp_output_stage.gds` | the assembled block (array + 4 glue inverters + 6 switches, wired, tapped) |
| `drc-clean/cp_output_stage_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/cp_output_stage.drc.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |
| `connectivity/cp_output_stage.netcheck.log` | extracted Metal1-3 connectivity of the block above |
| `connectivity/cp_array.netcheck.log` | the same check against Part 3b's *own* standalone GDS — the proof the shorts predate this issue |

Regenerate via `python3 -m pfd_cp.cp_output_stage` (from `layout/pll_top/`) +
`layout/run_pv.py drc`; do not hand-edit any file under this directory.
