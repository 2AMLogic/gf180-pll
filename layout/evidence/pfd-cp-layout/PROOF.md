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
