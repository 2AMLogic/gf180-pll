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
