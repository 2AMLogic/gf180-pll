# `cp` — the complete charge pump (issue #385)

Part 5a of #294/#303's device-layout methodology: `cp_output_stage`
(#321, `layout/pll_top/pfd_cp/cp_output_stage.py`) assembled with
`cp_dumpbuf` (#302, `layout/pll_top/pfd_cp/cp_dumpbuf.py`) into one flat,
standalone-DRC-clean block matching `design/cp.sch`'s full netlist
(`xbuf` included).

## What this is

`design/cp.sch`'s own `xbuf` instance (lines ~275-281) wires
`cp_dumpbuf`'s six external nets onto `cp_output_stage`'s boundary:

| `cp_dumpbuf` net | `cp_output_stage` pin | Notes |
|---|---|---|
| `VREF` | `VOUT` | stays external (loop filter) |
| `VBN` | `IBN` | stays external (shared bias) |
| `VBP` | `IBP` | stays external (shared bias) |
| `VDUMP` | `VDUMP` | becomes **fully internal** |
| `VDD` | `VDD` | tied, stays external |
| `VSS` | `VSS` | tied, stays external |

So this block's own boundary is `cp_output_stage`'s own twelve boundary
pins minus `VDUMP` — exactly the eleven `ipin`/`iopin` nets `design/cp.sch`
itself declares: `UP`, `DN`, `B0`, `B1`, `IBN`, `ICN`, `IBP`, `ICP`, `VOUT`,
`VDD`, `VSS`.

| | |
|---|---|
| Footprint (as drawn) | **347.410 × 74.725 µm** (25,960.21 µm² ≈ 0.026 mm²) |
| Sub-blocks | `cp_output_stage` (#321) at a zero offset, `cp_dumpbuf` (#302) placed to the right |
| Top cell | `cp`, flat |

Unlike `cp_output_stage` (a *subset* of `cp.sch`, `xbuf` excluded, by its
own docstring's admission), this block corresponds 1:1 to `design/cp.sch`'s
full netlist.

## Composition and routing

Both sub-blocks are built standalone (each already proven DRC-clean and
short-free — `layout/evidence/cp-layout/` and
`layout/evidence/cp-dumpbuf-layout/`), written to a scratch GDS, read back
into one fresh `devgen.Canvas`, placed with `CellInstArray`/`Trans`, then
flattened — the same technique `cp_output_stage.build()` already uses to
assemble `cp_array` + `pfdcp_inv`.

Both sub-blocks are already fully mesh-routed, so this module never lands a
fresh via directly on either side's own pad (the documented `V1.1`/`V2.1`
failure mode for doing that). The six bridging nets are instead routed as a
short Metal3 riser straight off each side's own bus, at its own native
edge, up to a dedicated per-net Metal2 trunk row far above both placed
footprints, joined by a plain Metal2 trunk. `cp.py`'s own module docstring
records four routing designs that were tried and failed before this one —
including a design that passed `netcheck` (no short) but still failed real
DRC with three `M2.2a` violations from a Metal2 "reach" run crossing too
close to unrelated internal geometry — and why each failed, for provenance.

## Connectivity is checked, not assumed

`layout/pll_top/pfd_cp/netcheck.py` extracts the finished GDS's own
Metal1/Via1/Metal2/Via2/Metal3 connectivity with KLayout and resolves a set
of probe points — every Metal1 landing pad either sub-block believes is on
each net, `cp_dumpbuf`'s own six external nets aliased onto their bridged
`cp_output_stage`-side name first (so the two sides' pads for what is now
one physical net land under one canonical key, not a spurious short).

```bash
python3 -m pfd_cp.cp --outdir <workdir>   # (from layout/pll_top/)
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| Every probe point lands on real metal | yes | yes (0 unresolved) | **PASS** |
| No net is open (`splits`) | none | none | **PASS** |
| No shorts | none | none | **PASS** |
| `VDUMP` forms exactly one connected island | yes | yes (`$33`, no other net reaches it) | **PASS** |
| Every net the `NET_MAP` bridges resolves to one component | yes | yes (all 6) | **PASS** |

Full log: `connectivity/cp.netcheck.log` (22 nets probed: the 11 boundary
nets, `VDUMP`, and the 10 internal nets either sub-block's own build already
names — `B0B`/`B1B`/`UPB`/`DNB`/`DNT`/`UPT` from `cp_output_stage`,
`NSRC`/`NDA`/`PDA`/`PSRC` from `cp_dumpbuf`).

## Standalone DRC-clean

```bash
python3 -m pfd_cp.cp --outdir <workdir>                              # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/cp.gds --top cp --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp` DRC, table `main` (default, no `--offgrid`) | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `cp` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: cp (D), 0 violations` | **PASS** |

Every table in the `main` deck ran, against real assembled geometry (both
sub-blocks' own devices, plus this module's own new Metal2/Via2/Metal3
bridging routing) — not a by-construction-clean placeholder.

The committed report database (`drc-clean/cp_main.lyrdb`) and stdout log
(`drc-clean/drc.stdout.log`) are from the default (non-`--offgrid`) run;
the `--offgrid` run was additionally verified clean but not separately
archived (same convention as `layout/evidence/cp-layout/`'s own two-row
table).

## No LVS claim, and why

Unlike `cp_output_stage`, this block *does* correspond 1:1 to
`design/cp.sch`'s full netlist (every device either sub-block draws, wired
per the net map above) — a full-circuit LVS run is now possible in
principle, but building the reference netlist and running it is not part of
this issue's own scope (see the issue's "Out of scope": wiring this block
to `pfd` is Part 5b, a separate follow-up). The connectivity check above is
the electrical claim this evidence directory makes.

## Automated test coverage

`layout/tests/test_cp_layout.py` (23 tests; the whole `layout/tests` suite
is 580 tests, all passing, `python3 -m unittest discover -s layout/tests -t
layout/tests`):

* **Pure-Python, no `klayout.db` needed** — `NET_MAP`/`BOUNDARY_PINS` match
  `design/cp.sch`'s own `xbuf` instance and `ipin`/`iopin` declarations:
  every `cp_dumpbuf` external net is bridged exactly once, `VDUMP` is not a
  boundary pin, and the four nets that stay external are all named.
* **`klayout.db`-gated** — `build()`'s own footprint (positive extent,
  encloses both sub-blocks, the two footprints do not overlap), boundary
  pin set (exactly the eleven declared, each with one landing pad, each
  byte-identical to `cp_output_stage`'s own unmodified pad), trunk-row
  layout (one per net, all pitch-separated, all strictly above both placed
  footprints) — plus `ConnectivityTests`, the finished GDS's own extracted
  Metal1-3 connectivity: no open net, no short, and `VDUMP` in particular
  checked as a distinct net of its own reaching no other net.

## Provenance

| | |
|---|---|
| Generated | 2026-09-15 |
| Invoked as | `python3 -m pfd_cp.cp --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`, `LAYOUT_PV_PYTHON` pointed at a local venv (`klayout` + `docopt`) per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.9` — newer than this repo's other evidence directories' `0.28.16`; `layout/README.md`'s "The two KLayouts" section documents that the only known version-drift regression (a false LVS mismatch on an LVS-clean layout) is DRC-unaffected, and no LVS claim is made here (see above) |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |

## Artifacts

| Path | What it is |
|---|---|
| `cp.gds` | the assembled block (`cp_output_stage` + `cp_dumpbuf`, bridged) |
| `drc-clean/cp_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |
| `connectivity/cp.netcheck.log` | captured `netcheck.check_gds()` summary and per-net component breakdown |

Regenerate via `python3 -m pfd_cp.cp` (from `layout/pll_top/`) +
`layout/run_pv.py drc`; do not hand-edit any file under this directory.

---

## Addendum (issue #448): labels-only regeneration, DRC re-run

`cp`'s composed cell used to inherit its sub-cells' own standalone pin
labels through `top.flatten(-1, True)`. Those names are local to the
sub-cell's own LVS claim and name the wrong net one level up — in
`pfd_cp`, the version of this defect that reached the top level put an
`ENB` text on the block's ground rail, which broke gf180mcu's substrate
global-net merge and mismatched all 84 n-channel bulk terminals (full
write-up: `layout/evidence/pfd-cp-layout/PROOF.md`, "Addendum 2"). The fix
is `_canvas.Canvas.clear_inherited_labels()`, called immediately after the
composing `flatten()` here, before this block promotes its own boundary
pins.

**Geometry did not change.** A layer-by-layer `klayout.db.Region` XOR of
this block's pre-change and post-change GDS is empty on all 11 drawing
layers; only the 34/10 label purpose differs. The committed `cp.gds` was
regenerated anyway so the tree matches its generator, and the DRC deck was
re-run on that exact file rather than the earlier claim being carried over:

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp` DRC, table `main` | clean | `DRC clean: cp (D), 0 violations` | **PASS** |

`drc-clean/drc.stdout.log` and `drc-clean/cp_main.lyrdb` are that run's own
output. Every `connectivity/*.netcheck.log` record in this directory is
unchanged, and was verified byte-identical after the rebuild — the expected
result of a labels-only change.

| | |
|---|---|
| Run | 2026-09-21 |
| Branch point | `origin/main` @ `93e36cd7` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout | `KLayout 0.28.16` |

---

## Addendum (issue #455): trunk-row pitch corrected — 26,062 → 25,630 µm²

`BACKBONE_PITCH_UM`, the Y pitch between two of this block's six Metal2
backbone trunk rows, was `cp_array.RISER_MIN_PITCH_UM` (1.00 µm). That
constant is `cp_array`'s minimum centre-to-centre separation between two
Metal3 *riser columns* — an **X** pitch between vertical Metal3 strips,
sized against `M3.2a`. A trunk row is a horizontal **Metal2** strip, and the
pitch two of those need is `cp_array.METAL2_TRACK_PITCH_UM` (0.75 µm), which
leaves 0.75 − 0.44 = 0.31 µm between two adjacent rows' Via2 landing pads,
above `M2.2a`'s 0.28 µm minimum. `cp_output_stage`'s own glue bus inside
this very block already stacks 14 tracks at that pitch *with* Via2 landings
on them and is signoff-clean, so this is a correction to the wrong constant
being used for the axis, not a new tolerance being claimed.

| | before | after |
|---|---|---|
| `footprint` tuple | 347.410 × 74.725 µm | **347.410 × 73.225 µm** |
| committed GDS bbox | 344.98 × 75.55 µm (26,062 µm²) | **344.98 × 74.30 µm (25,630 µm²)** |
| backbone rows | y 56.48 … 61.48 (1.00 µm pitch) | y 56.48 … 60.23 (0.75 µm pitch) |

Nothing else about this block changes: the same six nets bridge across the
same two sub-blocks by the same Riser+Trunk construction at the same X
columns, no boundary pin moves, and `cp_output_stage`/`cp_dumpbuf` are
untouched.

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp` DRC, table `main` (default) | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `netcheck.check_gds()` Metal1-3 connectivity | no shorts, no splits | `connectivity clean: 22 nets, no shorts, no splits` | **PASS** |

`drc-clean/` and `connectivity/` in this directory are the new runs'
outputs. Driven by issue #455's work on `pfd_cp`, the block that composes
this one — full record at
`layout/evidence/pfd-cp-layout/PROOF-455-fold.md`.

## Addendum (issue #469): 0.75 µm inherited from `cp_output_stage`'s packed glue bus

| | before | after |
|---|---|---|
| `footprint` tuple | 347.410 × 73.225 µm | **347.410 × 72.475 µm** |
| committed GDS bbox | 344.98 × 74.30 µm (25,630 µm²) | **344.98 × 73.55 µm (25,372 µm²)** |
| backbone rows | y 56.48 … 60.23 | y 55.73 … 59.48 |

Nothing in `cp.py` changed. Issue #469 packed `cp_output_stage`'s own glue-bus
track band from 14 tracks to 13 (`cp_array.pack_tracks()` in place of
`NetTracks`), which makes that sub-block 0.75 µm shorter and moves this
block's backbone band down with it. One of `cp_output_stage`'s tracks now
carries two nets (`DNT` and `UPB`, 9.26 µm apart in x); this module reaches
every glue bus at that bus's own edge and extends none of them, so the
invariant a packed band adds is `cp_output_stage`'s to hold — it re-proves it
on every build with `cp_array.check_track_separation()`.

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp` DRC, table `main` (default) | clean | `DRC clean: cp (D), 0 violations` | **PASS** |
| `netcheck.check_gds()` Metal1-3 connectivity | no shorts, no splits | `connectivity clean: 22 nets, no shorts, no splits` | **PASS** |

`drc-clean/` and `connectivity/` in this directory are the new runs' outputs.
Full record: `layout/evidence/pfd-cp-layout/PROOF-469-glue-bus-packing.md`.
