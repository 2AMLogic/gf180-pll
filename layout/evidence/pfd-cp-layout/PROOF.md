# `pfd_cp` — the top-level PFD + charge-pump block (issue #386)

Part 5b of #294/#303's device-layout methodology: `pfd` (#300,
`layout/pll_top/pfd_cp/pfd.py`) assembled with the complete `cp` block
(#385, `layout/pll_top/pfd_cp/cp.py` — `cp_output_stage` + `cp_dumpbuf`)
into one flat, standalone-DRC-clean block matching `design/pfd_cp.sch`'s
top-level netlist. This is the increment that actually satisfies #303's and
the parent #294's own acceptance criteria — #385 (Part 5a) was a pure
prerequisite.

## What this is

`design/pfd_cp.sch` is just two component instances, `xpfd` (`pfd.sym`) and
`xcp` (`cp.sym`):

| Net | Wiring |
|---|---|
| `REF`, `FB` | external inputs, `xpfd` only |
| `UP`, `DN` | `xpfd`'s outputs feed directly into `xcp`'s `UP`/`DN` inputs (also brought to the top level "for observation only", per the schematic's own header comment — both are already top-level pins either way) |
| `B0`, `B1`, `IBN`, `ICN`, `IBP`, `ICP`, `VOUT` | external I/O, `xcp` only (straight through) |
| `VDD`, `VSS` | shared by both instances, tied together |

So this block's own boundary is exactly the thirteen `ipin`/`iopin`/`opin`
nets `design/pfd_cp.sch` itself declares (`P0`-`P12`).

| | |
|---|---|
| Footprint (as drawn) | **434.310 × 80.725 µm** (35,059.67 µm² ≈ 0.0351 mm²) |
| Sub-blocks | `pfd` (#300) at a zero offset, `cp` (#385) placed to the right |
| Top cell | `pfd_cp`, flat |

## Composition and routing

`pfd.py` does not subclass the shared `layout/pll_top/_canvas.Canvas` base
class every other block in this package does — it defines its own,
separate `rowgen.Canvas` dataclass (`.rect()`/`.label()`/`.shapes`/
`.write_gds()`, no `.pin()`, no `.at()` translation context manager). So
`vco/block.py`'s in-process composition mechanism does not apply to `pfd`
directly. This block uses the same GDS-level technique `cp.py`/
`cp_output_stage.py` already established instead: each sub-block's own GDS
is written to a scratch path, read into one fresh `devgen.Canvas`, placed
with `CellInstArray`/`Trans`, then flattened.

`pfd`'s own `PfdLayout` exposes no `.pins` dict — only `.conductors`, every
drawn conductor shape tagged by net. `layout/pll_top/pfd_cp/block.py`'s own
`_pfd_bus()`/`_pfd_rail_landing()` filter that list for `UP`/`DN` (Metal2
bus) and `VDD`/`VSS` (continuous Metal1 rail) respectively, rather than
re-deriving `pfd.py`'s internal placement/track-assignment order by hand.

Both sub-blocks are already fully mesh-routed internally, so this module
never lands a fresh via stack on a pad that already carries one (the
documented `V1.1`/`V2.1`/`M2.2a` failure mode named in `cp_output_stage.py`'s
own docstring). Concretely:

* **`UP`/`DN`**: reached via `pfd`'s own native Metal2 bus edge and `cp`'s
  own `cp_output_stage.glue_bus[net]` edge — `x_lo`, not `x_hi` (`x_hi` is
  where `cp.py`'s own build would have landed a riser had `UP`/`DN` been
  one of its six `NET_MAP` bridge nets; they are not, but `x_lo` is used
  for symmetry with `VDD`/`VSS` below, where it matters).
* **`VDD`/`VSS`**: these *are* two of `cp.py`'s own `NET_MAP` nets, and
  `cp.py`'s own build already rose a Via2 riser at `glue_bus[net]`'s `x_hi`
  edge (linking `cp_output_stage` to `cp_dumpbuf`). This block reaches in at
  the free `x_lo` edge instead. On `pfd`'s own side, `VDD`/`VSS` are
  continuous Metal1 rails with no Metal2 bus at all — any point along
  either rail is an equally valid landing point, chosen (`RAIL_LANDING_INSET_UM`)
  clear of both the periodic well/substrate taps and `pfd`'s own row-to-row
  Metal3 stitches (which already carry a via of their own).

Each of the four bridged/tied nets gets its own dedicated Metal3 riser
column on each side, joined by a Metal2 trunk on a per-net trunk row
strictly above both placed blocks' own topmost drawn edge — the same
Riser+Trunk technique `cp.py`'s own module docstring names (and the same
docstring records four earlier routing designs that failed before that one
held, for provenance).

**One real defect found and fixed during this block's own development**:
the first attempt reached `UP` via its own bus's *near-axis* edge
(`x_hi = -1.08`), which turned out to sit exactly on `pfd`'s own `NRST`
row-to-row Metal3 link column (`x` in `[-1.52, -1.08]`) — a real Metal3
short, caught by `netcheck` (`UP+pfd.NRST`), not by DRC. The fix: rise from
whichever of the bus's two native edges sits farther from the mirror axis
(`AXIS_X = 0.0`) — `pfd.py`'s own `RB`/`NRST` links both land close to the
axis, so the far edge is clear of both by construction.

## Connectivity is checked, not assumed

`layout/pll_top/pfd_cp/netcheck.py` extracts the finished GDS's own
Metal1/Via1/Metal2/Via2/Metal3 connectivity with KLayout and resolves a set
of probe points. `pfd`'s own `PfdLayout` has no `probe_pads()` — its
connectivity model is the plain `conductors` list — so `block.py`'s own
`probe_pads()` builds pfd's probe set directly from every recorded Metal1
shape, and merges it with `cp`'s own `probe_pads()` (translated into this
block's shared frame). Net names outside this block's own thirteen boundary
pins are namespaced by which sub-block drew them (`pfd.`/`cp.` prefix)
before merging: `pfd`'s own internal `UPB`/`DNB` (the SR-latch outputs) and
`cp_output_stage`'s own internal `UPB`/`DNB` (the glue-inverter outputs) are
two unrelated physical nets that happen to share a bare name — merging them
under one key would have reported a false `split` with no bearing on this
block's own wiring (reproduced during development, see above).

```bash
python3 -m pfd_cp.block --outdir <workdir>   # (from layout/pll_top/)
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| Every probe point lands on real metal | yes | yes (0 unresolved) | **PASS** |
| No net is open (`splits`) | none | none | **PASS** |
| No shorts | none | none | **PASS** |
| `UP`/`DN`/`VDD`/`VSS` each resolve to exactly one component | yes | yes (all 4) | **PASS** |
| `pfd`'s and `cp`'s own private `UPB` stay distinct nets | yes | yes (`pfd.UPB` != `cp.UPB`) | **PASS** |

Full log: `connectivity/pfd_cp.netcheck.log` (76 nets probed: the 13
boundary nets, plus every other net either sub-block's own build names,
namespaced `pfd.`/`cp.`).

## Standalone DRC-clean

```bash
python3 -m pfd_cp.block --outdir <workdir>                              # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/pfd_cp.gds --top pfd_cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfd_cp` DRC, table `main` (default, no `--offgrid`) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |

Every table in the `main` deck ran, against real assembled geometry (both
sub-blocks' own devices, plus this module's own new Metal2/Via2/Metal3
bridging routing) — not a by-construction-clean placeholder.

The committed report databases (`drc-clean/pfd_cp_main.lyrdb`,
`drc-clean-offgrid/pfd_cp_main.lyrdb`) and stdout logs both confirm zero
violations across the `main` deck's full rule table.

## No LVS claim, and why

This block corresponds 1:1 to `design/pfd_cp.sch`'s full netlist (two
component instances, wired per the net map above) — a full-circuit LVS run
is possible in principle, but building the reference netlist and running it
is not part of this issue's own scope (see the issue's "Out of scope":
integrating this block into the full `pll_top` GDS is #297, a separate
follow-up). The connectivity check above is the electrical claim this
evidence directory makes.

## Automated test coverage

`layout/tests/test_pfdcp_block_layout.py` (21 tests) and
`layout/tests/test_floorplan_skeleton.py` (extended with the real `pfd_cp`
footprint's containment/drift checks) — the whole `layout/tests` suite runs
via `python3 -m unittest discover -s layout/tests -t layout/tests`:

* **Pure-Python, no `klayout.db` needed** — `BOUNDARY_PINS`/`BRIDGED_NETS`/
  `RAIL_NETS` match `design/pfd_cp.sch`'s own net map exactly;
  `_SHARED_PROBE_NET_NAMES` (the probe-merge namespace guard) is exactly
  `BOUNDARY_PINS`; `RAIL_LANDING_INSET_UM` gives `VDD`/`VSS` two distinct
  insets.
* **`klayout.db`-gated** — `build()`'s own footprint (positive extent,
  encloses both sub-blocks, `pfd` unmodified at a zero offset, `cp` placed
  clear of it, four pitch-separated trunk rows all strictly above both
  placed footprints), boundary pin set (exactly the thirteen declared, each
  with one landing pad) — plus `ConnectivityTests`, the finished GDS's own
  extracted Metal1-3 connectivity (no open net, no short, the bridged/tied
  nets each resolve to one component, `pfd`'s and `cp`'s own private
  `UPB` stay distinct).

## Provenance

| | |
|---|---|
| Generated | 2026-09-15 |
| Invoked as | `python3 -m pfd_cp.block --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`, PDK/KLayout/PV-python resolved per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |

## Artifacts

| Path | What it is |
|---|---|
| `pfd_cp.gds` | the assembled block (`pfd` + `cp`, bridged/tied) |
| `drc-clean/pfd_cp_main.lyrdb` | KLayout DRC report database, default run (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr, default run |
| `drc-clean-offgrid/pfd_cp_main.lyrdb` | KLayout DRC report database, `--offgrid` (signoff-grade) run (empty violations) |
| `drc-clean-offgrid/drc.stdout.log` | captured `run_drc.py` stdout+stderr, `--offgrid` run |
| `connectivity/pfd_cp.netcheck.log` | captured `netcheck.check_gds()` summary and per-net component breakdown |

Regenerate via `python3 -m pfd_cp.block` (from `layout/pll_top/`) +
`layout/run_pv.py drc`; do not hand-edit any file under this directory.

## Addendum (issue #440): block-level LVS attempted — real mismatch found, superseding "No LVS claim, and why" above

The "No LVS claim, and why" section above states that building a reference
netlist and running LVS was out of scope for #386. Issue #440 closes that
gap: a reference netlist now exists and the PDK's own signoff LVS deck has
been run against it. **The result is a real mismatch, not a match** — per
this repo's own rule that "any LVS mismatch found is a result to record,
not paper over," it is recorded here rather than hidden, and this evidence
directory's own LVS claim stays "attempted, not yet clean" until the
generator defect below is fixed. This section supersedes the older one's
"is not part of this issue's own scope" framing; it does not delete it
(append-only).

### The reference netlist

`design/netlist.sh --top pfd_cp <outdir>` netlists `design/pfd_cp.sch`'s own
nine-`.subckt` hierarchy (`pfd_cp` -> `pfd`/`cp` -> `edgedet`/`srlatch`/
`cp_leg_n`/`cp_leg_p`/`cp_dumpbuf` -> `pfdcp_inv_3v3`/`pfdcp_nand2_3v3`) to
`<outdir>/dut.spice` — the per-record convention `design/netlist.sh`'s own
header comment documents for this one block (deliberately not committed as
`design/netlist/pfd_cp.spice`, which does not exist and is not meant to).
That export is frozen verbatim at `lvs-clean/pfd_cp.schematic-export.spice`
in this directory (the same "freeze the per-record export" discipline
`sim/*/netlist-snapshots/` already uses).

gf180mcu's own LVS deck does not flatten a hierarchical reference to match
a flat GDS on its own — the same finding `divider_chain.py`'s own
`reference_netlist()` already recorded for that block. `pfd_cp`'s own
`build()` draws one fully flat top cell (`canvas.top.flatten(-1, True)`,
twice — once inside `cp.py`, once again in `block.py`), so the frozen
export above needs flattening too. Rather than hand-transcribing this
168-transistor, nine-`.subckt` hierarchy in Python (the `vco_block`/
`divider_chain` precedent), `layout/harness/spice_flatten.py` (issue #440)
does it mechanically: it parses every `.subckt ... .ends` block in a SPICE
text and expands one named top recursively, qualifying every internal net
and device name by its own instance path so two instances of the same leaf
cell never collide once flattened. `layout/pll_top/pfd_cp/block.py`'s own
`reference_netlist()` calls it against the frozen export; unit tests for
the flattener itself live at `layout/tests/test_spice_flatten.py` (generic,
no PDK), and `layout/tests/test_pfdcp_block_layout.py`'s own
`ReferenceNetlistTests` checks the 168-device count and top-level port list
this specific block's flattening produces.

### The LVS run

```bash
python3 layout/run_pv.py lvs layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/lvs-attempt/pfd_cp.spice \
  --top pfd_cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfd_cp` LVS, deck verdict | match | `ERROR : Netlists don't match` | **MISMATCH — real, not yet root-caused to a specific fix** |

Artifacts: `lvs-attempt/lvs.stdout.log`, `lvs-attempt/pfd_cp.cir` (extracted),
`lvs-attempt/pfd_cp.lvsdb`, `lvs-attempt/pfd_cp.spice` (the flattened
reference this run used). Named `lvs-attempt/`, not `lvs-clean/`, per the
same convention `layout/evidence/vco-layout/PROOF-376-vbp0-fix.md` already
uses for an interim non-matching run — `layout/lib/check-layout-status-claims.sh`
only counts a block LVS-matched when its own `lvs-clean/*.log` contains the
deck's `Netlists match.` verdict line, so this attempt does not (and must
not) move this block's own count in that script or in README.md/
`docs/chipalooza/challenge-5-proposal.md`.

### What the mismatch actually is — not just "no match"

`layout/tests/test_pfdcp_block_layout.py`'s own `ConnectivityTests` (this
block's Python-level Metal1-3 probe check, `netcheck.py`) reports **no
shorts, no splits** on the same drawn GDS — and it always will, by that
module's own documented scope: it deliberately excludes comp/poly2 from
its connectivity graph (a MOSFET's own comp island spans source/gate/drain
as one shape; reproducing the gate-split the real deck's device extraction
does would be re-implementing that deck). Cross-referencing the LVS run's
own `.lvsdb` (`klayout.db.LayoutVsSchematic().xref()`, the same technique
`PROOF-376-vbp0-fix.md` uses) shows the layout-side extracted netlist has
**84 mismatched nets and 69 mismatched devices out of 168** — a large
fraction, concentrated in `pfd`'s own two mirror-symmetric branches (the
`REF`/edge-detector/latch chain and its `FB` twin) and `cp`'s own array
legs. Two things are visible in that cross-reference and are recorded here
plainly rather than rounded away:

* **Almost none of `pfd`'s own internal nets carry a name in the drawn
  GDS.** `pfd.py` calls no `canvas.pin()` at all (`block.py` only promotes
  the block's own 13 boundary pins); every `edgedet`/`srlatch`/delay-chain
  internal node (`D1`-`D5`, `PR`, `PF`, `SBR`, `SBF`, `RB`, `NRST`,
  `RST_RAW`, `RD1`-`RD24`, `RST_DLY`, ...) is an anonymous `$N` net in the
  layout-side extraction. That starves the comparer's name-hint matching
  across most of this block's own devices — the same root cause
  `divider_chain.py`'s own `PROOF.md` names ("Every routed net is labelled,
  and that was necessary") for that block's own bring-up, not yet applied
  here.
* **At least one net-naming artifact is real, not just absent labels.**
  The `.lvsdb`'s own extracted net list shows several merged names of the
  shape `<leg-local-name>,<global-name>` (e.g. `ENB,VSS`, `EN,VDD`,
  `IBN,VBN`) — harmless: `cp_leg_n.py`/`cp_leg_p.py` each promote their own
  pins under their own *local* port names (`EN`/`ENB`/`VBN`/...) when built
  standalone for their own leaf-level LVS claim (`cp-leg-proof/`), and
  `cp_array.py`'s `CellInstArray` + `flatten()` composition carries that
  label through even after the pin is re-tied to a different global net —
  but one merged name is not: **`DN,UP`**, on a PMOS gate net inside the
  mirror-symmetric latch/switch structure. Whether that specific merge is a
  real electrical short (a `pfd`/`cp` placement or routing defect) or a
  second labelling artifact riding on an under-labelled net is not yet
  determined — narrowing it needs the same net-labelling pass `pfd.py`
  does not yet have, so today's cross-reference cannot distinguish "shorted"
  from "unlabelled and therefore mismatched by the comparer's own topology
  fallback." Tracked as a follow-up rather than guessed at here (see below).

### Disposition

Per this issue's own Acceptance Criteria and CLAUDE.md's "no claim without
a testbench" — a real mismatch is not converted into a false match, and the
layout generator is not "fixed" by guessing. The follow-up that would
actually close this block's own LVS-matched claim (labelling every `pfd`/
`cp_array` internal net for the deck's own hint matching, the way
`divider_chain.py`'s `build()` already does, and root-causing the `DN,UP`
merge specifically) is filed separately as
[issue #448](https://github.com/2AMLogic/gf180-pll/issues/448) rather than
attempted here under time pressure that would risk exactly the "two
suspiciously-clean first runs" this repo's own CLAUDE.md warns against.

### Provenance of this addendum

| | |
|---|---|
| Attempted | 2026-09-21 |
| Branch point | `origin/main` @ `387d03c6` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D` (default `--lvs_sub=VSS`) |

---

## Addendum 2 (issue #448): the mismatch above, root-caused and fixed — `pfd_cp` is now LVS-matched

The addendum above recorded a real 84-of-93-net, 69-of-168-device mismatch
and declined to guess at its cause. [Issue #448](https://github.com/2AMLogic/gf180-pll/issues/448)
carried that forward. The cause turned out to be **neither** of the two
things that addendum suspected: not missing name hints on `pfd`'s internal
nets, and not a real `UP`/`DN` short. The drawn *geometry* was correct all
along. What was wrong was the **net naming**, in two independent ways — and
in this deck one of them is not cosmetic at all.

### Root cause 1: a stray inherited label on the ground rail disconnected every n-channel bulk

`layout/README.md`'s "substrate-net gotcha" already records that this deck
synthesizes the p-substrate as a *global* net whose name comes from
`--lvs_sub` (`VSS`, the harness default). What it did not yet record is the
sharp edge on that: the global net merges into the drawn net that carries
**exactly** that name, and a drawn net that carries *two* names does not
qualify.

`cp_leg_n`/`cp_leg_p` are built standalone for their own leaf-level LVS
claim (`layout/evidence/cp-leg-proof/`), so each labels its own boundary
nets with its own **local** port names — `EN`, `ENB`, `VBN`, `VCASCN`,
`TAIL`, … . `cp_array` then composes four copies of each by reading the leg
GDS and calling `top.flatten(-1, True)`, which carries those label *shapes*
into the parent cell; and the array ties each always-on base leg's `EN`/
`ENB` permanently to a supply rail. Eight `ENB` texts therefore ended up
sitting on this block's ground rail, which extracted as the merged name
`ENB,VSS`:

```
ENB,VSS   terminals: {'S': 53, 'D': 11, 'G': 2}     <- the drawn Metal1 rail
VSS       terminals: {'B': 84}                      <- the deck's global substrate net
```

Two nets, and the bulk terminal of every one of the block's 84 n-channel
devices was on the wrong one. That single naming defect accounts for the
whole cascade: 84 mismatched nets out of 93, 69 mismatched devices out of
168. Deleting nothing but those eight `ENB` texts from the committed GDS —
no geometry change of any kind — turned the same deck run into
`Congratulations! Netlists match.`, which is how the cause was confirmed
rather than argued.

### Root cause 2: `UP`/`DN` were labelled on Metal1's pin purpose over a Metal2-only bus

`block.py` promotes `UP`/`DN` using `_pfd_bus_box()` — `pfd`'s own **Metal2**
bus for each net — but `devgen.Canvas.pin()` labels on `metal1_label`
(34/10) by default, and the deck attaches a 34/10 text to whatever *Metal1*
lies under it (`connect(metal1_con, metal1_label)`). Under both bus edges
lies `pfd`'s own row-0 `RB` bus. So `RB` collected both a `UP` and a `DN`
text and extracted as `DN,UP`, while the real `UP`/`DN` nets kept only the
labels `pfd.py` had placed for them.

This is the `DN,UP` name the first addendum flagged as "not obviously
benign … whether this is a real electrical short or a labelling artifact
cannot be told apart yet." It is the latter, definitively: `RB` has exactly
the six terminals `design/pfd.sch` gives it (driven by `xinv_rb`'s two
drains, driving four NAND gate inputs), and the block now matches a
reference netlist in which `UP`, `DN` and `RB` are three distinct nets. The
earlier caution was right to record it as unresolved rather than call it
either way.

### The fix, in the generators

Both are naming faults on correct geometry, so the fix is in how each
assembly level names what it has drawn — nothing moved.

1. **`layout/pll_top/_canvas.py`: `Canvas.clear_inherited_labels()`** (new,
   generic, unit-tested at `layout/tests/test_canvas_labels.py`). Deletes
   every text on a given pin purpose from the flattened cell. The rule it
   enforces is *the level doing the assembling owns the net names*: a
   sub-block's local port names are meaningful only inside that
   sub-block's own standalone LVS claim, and every level here already
   re-promotes its own boundary pins immediately afterwards. It is called
   right after the composing `flatten()` in `cp_array.py`,
   `cp_output_stage.py`, `cp.py` and `block.py` — all four, not just the
   one that happened to fail, because the defect is a property of the
   composition pattern rather than of any one block.
2. **`block.py` labels `UP`/`DN` on `metal2_label` (36/10)**, the purpose
   the deck connects to Metal2 (`connect(metal2_con, metal2_label)`), so
   the name lands on the bus it was measured from. `devgen.LAYER` gains
   that entry.

The reference netlist was **not** touched: it is still the mechanical
flattening of the frozen `design/pfd_cp.sch` export described in the first
addendum, byte-identical, and `layout/tests/test_pfdcp_block_layout.py`
asserts the committed `lvs-clean/pfd_cp.spice` equals what
`block.reference_netlist()` produces today.

### The clean run

```bash
python3 -m pfd_cp.block --outdir <workdir>          # (from layout/pll_top/)
python3 layout/run_pv.py lvs layout/evidence/pfd-cp-layout/pfd_cp.gds \
  layout/evidence/pfd-cp-layout/lvs-clean/pfd_cp.spice \
  --top pfd_cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfd_cp` LVS, deck verdict | match | `INFO : Congratulations! Netlists match.` | **PASS** |
| `pfd_cp` cross-reference, circuit status | `Match` | `Match` | **PASS** |
| `pfd_cp` net count, layout vs. reference | equal | 92 / 92 | **PASS** |
| `pfd_cp` device count, layout vs. reference | equal | 168 / 168 | **PASS** |
| `pfd_cp` DRC, table `main` (default) | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `pfd_cp` DRC, table `main`, `--offgrid` | clean | `DRC clean: pfd_cp (D), 0 violations` | **PASS** |
| `netcheck.check_gds()` Metal1-3 connectivity | no shorts, no splits | `connectivity clean: 76 nets, no shorts, no splits` | **PASS** |

**No device-class deviation is disclosed for this block** — unlike
`vco_block`, whose own record discloses a resistor-class deviation, every
device here extracts as the same `nfet_03v3`/`pfet_03v3` class the
reference declares. The 13 extracted top-level ports are exactly this
block's own 13 boundary pins, in the deck's own order:

```
.SUBCKT pfd_cp IBP REF IBN VSS DN FB UP B0 ICN ICP VDD B1 VOUT
```

Artifacts: `lvs-clean/lvs.stdout.log`, `lvs-clean/pfd_cp.cir` (extracted),
`lvs-clean/pfd_cp.lvsdb`, `lvs-clean/pfd_cp.spice` (the flattened reference
this run used), beside the already-frozen
`lvs-clean/pfd_cp.schematic-export.spice`. **`lvs-attempt/` is kept, not
deleted** — the mismatch this block's first block-level LVS run really
found is part of the record, and a test asserts it stays (`layout/tests/
test_pfdcp_block_layout.py::LvsEvidenceTests`).

### What else moved, and why

Because the fix removes label shapes from three intermediate blocks'
composed cells, their committed GDS changed too — *texts only, no geometry*
(`cp_array` 66 → 18 texts, `cp_output_stage` 94 → 12, `cp` 111 → 11,
`pfd_cp` 132 → 13). That this is labels-only is checked rather than
asserted: a layer-by-layer `klayout.db.Region` XOR of each block's
pre-change and post-change GDS is **empty on all 11 drawing layers** for
all four blocks (only the two label purposes, 34/10 and 36/10, differ).
Each was nonetheless regenerated and re-run through the DRC deck rather
than left stale:

| Block | Evidence | DRC re-run |
|---|---|---|
| `cp_array` | `layout/evidence/cp-array-proof/` | `DRC clean: cp_array (D), 0 violations` |
| `cp_output_stage` | `layout/evidence/cp-layout/` | `DRC clean: cp_output_stage (D), 0 violations` |
| `cp` | `layout/evidence/cp-block-layout/` | `DRC clean: cp (D), 0 violations` |

Their `connectivity/*.netcheck.log` records are unchanged and were verified
byte-identical after the rebuild, which is the expected result of a
labels-only change.

### Provenance of this addendum

| | |
|---|---|
| Run | 2026-09-21 |
| Branch point | `origin/main` @ `93e36cd7` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--variant=D` (default `--lvs_sub=VSS`) |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, variant D |
| Tests | `python3 -m unittest discover -s layout/tests -t layout/tests` — 668 tests, all passing |

---

## Addendum 3 (issue #455): the block is folded — 35,281 → 26,665 µm², −24.4 %

The footprint recorded at the top of this file (434.310 × 80.725 µm,
35,059.67 µm²) and the "`pfd` at a zero offset, `cp` placed to the right"
composition described under "Composition and routing" are **superseded**.
Issue #455 folded `pfd` into `cp`'s own 99.0 %-empty band above
`cp_dumpbuf`, so `cp` is now the block at a zero offset and `pfd` is the one
translated; and it corrected the Metal2 trunk band's pitch and base. The
block is now **347.410 × 76.225 µm (26,481.33 µm²)** on the `footprint`
tuple, **344.98 × 77.30 µm (26,665 µm²)** on the committed GDS bbox.

Every claim this file makes is re-proved against the new geometry rather
than inherited: DRC `main` clean, DRC `main --offgrid` (signoff-grade)
clean, LVS `Congratulations! Netlists match.` at 92/92 nets and 168/168
devices, `netcheck` clean at 76 nets with no short and no split. The
`drc-clean/`, `drc-clean-offgrid/`, `lvs-clean/` and `connectivity/`
artifacts in this directory are the new runs' outputs; `lvs-attempt/` (the
first block-level run's real mismatch) is untouched.

Full record, including the achieved-against-ceiling arithmetic, why the
issue's −58 % ceiling is not reachable, and the sizing of what is left:
**`PROOF-455-fold.md`** in this directory.
