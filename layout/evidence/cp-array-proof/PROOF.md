# `cp_array` -- CP N/P common-centroid array placement + bias branch (issue #320)

Part 3b of #294's device-layout methodology (a decomposition of #301, itself
Part 3 of #294, one of #292's five block sub-issues).

## What this is, and is not

This **is** a real, DRC-clean common-centroid placement of the charge pump's
N-polarity sink array (4x `cp_leg_n`: `xn_base`, `xn_t0`, `xn_t1a`, `xn_t1b`)
and P-polarity source array (4x `cp_leg_p`: `xp_base`, `xp_t0`, `xp_t1a`,
`xp_t1b`), each built on Part 3a's already-proven-clean `cp_leg_n`/`cp_leg_p`
composite leaf cells (issue #319), plus the 4x-scaled bias-branch devices
(`MBN`/`MCN` for N, `MBP`/`MCP` for P -- single `nfet_03v3`/`pfet_03v3`
diode-connected instances, sizes/nets read directly off `design/cp.sch`),
and the Metal1/2/3 mesh routing tying each array's shared nets
(`IBN`/`ICN`/`B0`/`B0B`/`B1`/`B1B`/`DNT`/`VSS` for N;
`IBP`/`ICP`/`B0`/`B0B`/`B1`/`B1B`/`UPT`/`VDD` for P) across its own 4 legs.

It is **not** LVS-clean, and states no reference netlist -- this array's own
bias-branch devices only diode-connect to their own bias nodes here; the
real bias-generation, glue inverters, and steering/dump switches that close
the loop (Part 3c, issue #321) are what would make the full circuit
electrically complete enough for a meaningful LVS comparison. It is also
**not** the glue-logic assembly or `cp_dumpbuf` integration (Parts 3c/4/5,
issues #321/#302/#303) -- see this issue's own "Out of scope" section.

## Common-centroid placement: a tripod, not a row or a 2x2 grid

Per `PLL-FLOORPLAN.md` and this issue's own text, each array's geometric
centre (the arithmetic mean of its own 4 leg-instance centres) must coincide
with the always-on leg's own centre. Four identical-footprint *whole cells*
(not fingers) cannot satisfy that with a plain row or 2x2 grid -- the mean
of 4 evenly-spaced positions falls *between* the 2nd and 3rd in a row, and a
non-overlapping grid's own centre point sits in the gap between all four
cells, not at any one cell's own position (see `cp_array.py`'s own module
docstring, "COMMON-CENTROID PLACEMENT" section, for the full argument).

`cp_array.leg_offsets()` instead places the 3 switched legs at the vertices
of an isosceles triangle centred on the always-on leg:

```
           t1b
            |
  t0 ---- base ---- t1a
```

`t0`/`t1a` mirror left/right of `base`; `t1b` sits directly above, twice as
far -- so the three switched legs' own offsets sum to exactly zero, and
their mean (therefore the array's own mean, including `base`) coincides
with `base`'s own centre for *any* leg size, proven arithmetically by
`cp_array.check_common_centroid()` (the 2-D analog of `vco/mirror.py`'s own
`leg_centroid_um()`/`check_common_centroid()` this issue's own text asks
for -- reference only, `mirror.py` itself is not modified).

## GDS-level placement, not four redraws

Following `divider_chain.py`'s own precedent (issue #310, "SIX IDENTICAL
`div23_cell` INSTANCES"), `cp_array.py` builds `cp_leg_n`/`cp_leg_p` exactly
once each (unmodified, only consumed), places four `klayout.db.CellInstArray`
references per polarity at the tripod's own computed offsets, then flattens.
The P array's own local placement is shifted right by a *computed* amount
(`build()`'s own `shift_x`) -- clear of the N side's own rightmost extent
(array + bias branch) plus a real design margin (`N_P_GAP_UM`) -- not a
hand-tuned constant, so the non-overlap guarantee does not go stale if
either leg's own footprint changes. `build()` asserts the resulting
non-overlap explicitly as well (belt-and-suspenders on top of the
by-construction guarantee).

## Bias branch: adjacent, not inside

`MBN` (`nfet_03v3`, W=16u/L=1u, D=G=`IBN`, S=B=`VSS`) and `MCN` (W=4u/L=1u,
D=G=`ICN`, S=B=`VSS`) sit in a row below the N array, clear of all 4 legs;
`MBP` (`pfet_03v3`, W=48u/L=1u, D=G=`IBP`, S=B=`VDD`) and `MCP` (W=12u/L=1u,
D=G=`ICP`, S=B=`VDD`) sit below the P array the same way. Every size/net is
read directly off `design/cp.sch`'s own `MBN`/`MCN`/`MBP`/`MCP` instances.
Each device's own drain is diode-connected to its own gate
(`cp_array._diode_connect()`, a two-segment Metal1 jog generalizing
`cp_leg.py`'s own `_route_bg_tap()` technique to arbitrary device width).

## Mesh routing: a third, independent riser fabric -- with one real bug found and fixed

Per this package's own "each full-custom leaf-cell family owns its own
generator" convention, `cp_array.py` draws its own copy of the
Via1-Metal2-Via2-Metal3-Via2-Metal2 riser/bus fabric `cp_dumpbuf.py`
already proved out (issue #302), rather than importing it.

Three real, reproduced failures during this module's own development, all
fixed and left recorded in `cp_array.py`'s own docstrings/comments (not
silently corrected):

1. **`M1.1`** (Metal1 minimum width, 8 violations): `_diode_connect()`'s own
   two-segment jog originally stopped each segment *exactly* at the elbow's
   own centreline instead of overlapping past it, leaving a notch narrower
   than the minimum width at the outside of the turn. Fixed by extending
   each segment half a wire-width *past* the joint, guaranteeing a full
   `wire_w x wire_w` overlap square at the corner.
2. **`M3.2a`**/**`M2.2a`**/**`V2.2a`** (Metal2/3 spacing, 10 violations): a
   plain "rise at each pad's own natural X" approach let two *different*
   nets' risers land within ~0.24 um of each other -- `xp_base`'s own
   `VCASCP` pin (`ICP`) next to `MBP`'s own source pad centre (`VDD`), pure
   coincidence between a wide bias device's pad centre and a narrow leg's
   own tightly-spaced pin cluster. Fixed by `declutter_riser_x()`: a
   global-across-nets sweep (not a per-net-only proximity merge) that pushes
   any two riser candidates within `RISER_MIN_PITCH_UM` (1.0 um) apart in X,
   regardless of which nets they belong to.
3. **`V1.3a`** (Via1 enclosure, 8 violations): once `declutter_riser_x()`
   could move a riser off its own pad's natural centre onto a plain
   `METAL1_WIRE_WIDTH_UM` (0.28 um)-wide stub, that stub was too narrow to
   enclose Via1's own 0.44 um requirement. Fixed by having `_riser()` draw
   its own dedicated Metal1 landing square, independent of whatever stub
   geometry already exists at that point.
4. A closely-related **algorithmic bug** in `declutter_riser_x()` itself
   (not a DRC violation, caught by `test_cp_array.py`'s own
   `test_exact_same_net_tie_stays_tied_even_after_a_cascading_nudge`
   regression test before it could reach a DRC run): a naive "leave exact
   ties alone" rule, comparing each point only against the *running assigned*
   X, broke the moment an earlier point sharing the same natural X as a
   later one got nudged past it by an intervening different-net point --
   the later point, still comparing against its own unperturbed natural X,
   computed a negative delta and stayed behind, only a fraction of a um from
   its own nudged sibling. Fixed by comparing each point's own *natural* X
   against the *preceding* point's own natural X (not the running assigned
   one), which finds a true tie correctly regardless of any earlier nudging.

## Post-landing fix: EN/ENB riser column short (issue #359)

DRC-clean at landing time was real but incomplete: `declutter_riser_x()`'s
own net-agnostic exact-tie collapse (above) silently merged two
*different*-net risers onto one Metal3 column whenever their pads shared an
exact natural X -- invisible to DRC (two Metal3 runs at one X are one legal
polygon), caught only once `layout/pll_top/pfd_cp/netcheck.py` landed with
#321 and was run against this module's own standalone GDS: `xn_t0`'s own
`EN`/`ENB` gate-tab pads (`B0`/`B0B`) shared a column, and so did
`xn_base`'s (`VDD`/`VSS`) with `xn_t1b`'s (`B1`/`B1B`) -- the tripod places
`t1b` directly above `base`. Filed and root-caused as #359, fixed here: the
tie rule is now net-aware (a same-X tie only collapses when the two points
are also the same net), every leg's own gate-tab pins reach their riser
column through an explicit, checked Metal1 escape rather than their
un-escaped natural X (`cp_array.py`'s own module docstring, "EN/ENB SHARE
ONE GATE-TAB COLUMN"), and `check_riser_columns()` now asserts -- on every
build, not just in a docstring -- that the decluttered plan never puts two
nets on one column. See `netcheck` results below.

## Standalone DRC-clean, and connectivity

```bash
python3 -m pfd_cp.cp_array --outdir <workdir>       # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/cp_array.gds --top cp_array --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_array` DRC, table `main` (default, no `--offgrid`) | clean | `DRC clean: cp_array (D), 0 violations` | **PASS** |
| `cp_array` DRC, table `main`, `--offgrid` (signoff-grade) | clean | `DRC clean: cp_array (D), 0 violations` | **PASS** |
| `netcheck.check_gds()` (Metal1-3 connectivity, `python3 -m pfd_cp.cp_array`'s own default run) | no shorts, no splits | `connectivity clean: 18 nets, no shorts, no splits` | **PASS** |

Real device/routing rules this run actually exercised (every table in the
`main` deck ran; every family below was hit and fixed at least once during
development -- see "Mesh routing" above): `DF.1a_LV`/`DF.3a_LV`/`DF.6_LV`/
`DF.16_LV` (comp width/space/gate overhang/well-edge clearance),
`PL.2_LV`/`PL.4_LV`/`PL.5a_LV`/`PL.5b_LV` (poly gate length/endcap/field
spacing), `CO.1`-`CO.10` (contact size/space/enclosure), `NP.*`/`PP.*`
(implant width/space/enclosure), `NW.1a_LV`/`DF.4c_LV`/`DF.4d_LV`/`DF.13_LV`/
`DF.14_LV` (n-well enclosure, tap-distance -- both bias rows exceed the
20 um single-tap cap, hence `_tap_strip()`'s own continuous strip),
`M1.1`/`M1.2a`/`M1.3` (Metal1 width/space/area), `M2.1`/`M2.2a`
(Metal2 width/space), `M3.1`/`M3.2a` (Metal3 width/space), `V1.1`/`V1.3a`/
`V2.1`/`V2.2a` (Via1/Via2 size/enclosure/space).

## Automated test coverage

`layout/tests/test_cp_array.py` (40 tests, `python3 -m unittest
layout.tests.test_cp_array -v`):

* **Pure-Python, no `klayout.db` needed**: `leg_offsets()`'s tripod
  satisfies the centroid equation and clears every pairwise overlap for
  arbitrary leg dimensions; `centroid_um()`/`check_common_centroid()`
  arithmetic; `boxes_overlap()`; `declutter_riser_x()` (well-separated
  points unchanged, close different-nets pushed apart, the exact-tie
  regression above, `y` never perturbed, and a denser adversarial case
  checked pairwise-safe); `BIAS_DEVICES_N`/`BIAS_DEVICES_P` match
  `design/cp.sch`'s own `MBN`/`MCN`/`MBP`/`MCP` (sizes, diode-connected
  D==G); `N_NET_MAP`/`P_NET_MAP` (the always-on leg's own `EN`/`ENB` tie
  directly to `VDD`/`VSS`, never a trim net; `t0` uses `B0`/`B0B`; `t1a`/
  `t1b` share `B1`/`B1B`; every leg shares the bias/tail nets).
* **`klayout.db`-gated** (skipped, not failed, without a PV environment):
  `xn_base`/`xp_base` sit exactly at their own array's geometric centroid
  (re-derived independently from `build()`'s own recorded leg centres, not
  just trusting the internal `check_common_centroid()` call `build()`
  itself already makes and would have raised on); N and P sides do not
  overlap; no two legs within one polarity overlap each other; the bias
  branch does not overlap any leg of its own polarity; bias device sizes;
  every expected top-level pin is present, with the right pad count per
  side (`B0`/`B0B`/`B1`/`B1B`/`VDD`/`VSS` on both sides; `IBN`/`ICN`/`DNT`/
  `IBP`/`ICP`/`UPT` on one side only).

## Reusable module

`layout/pll_top/pfd_cp/cp_array.py` -- `leg_offsets()`/`centroid_um()`/
`check_common_centroid()`/`boxes_overlap()`/`declutter_riser_x()` (pure
Python placement/routing math), `BIAS_DEVICES_N`/`BIAS_DEVICES_P`/
`N_NET_MAP`/`P_NET_MAP` (device table + net wiring, read off
`design/cp.sch`), and `build()` (the full klayout-dependent assembly).
`cp_leg_n.py`/`cp_leg_p.py` are consumed, not modified. Part 3c (#321) is
expected to build on this module's own `CpArrayLayout.pins` (per-net Metal1
landing points) the way `divider_chain.py` builds on `div23_cell.py`'s own
`pins` dict.

## Provenance

| | |
|---|---|
| Generated | 2026-09-09T11:46 UTC (regenerated for issue #359) |
| Invoked as | `python3 -m pfd_cp.cp_array --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`, `LAYOUT_PV_PYTHON` pointed at a local venv (`klayout` + `docopt`) per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |

## Artifacts

| Path | What it is |
|---|---|
| `cp_array.gds` | the real transistor-level array block (8 leg instances + 4 bias devices, wired, tapped) |
| `drc-clean/cp_array_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/cp_array.drc.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |

Regenerate via `python3 -m pfd_cp.cp_array` (from `layout/pll_top/`) +
`layout/run_pv.py drc`; do not hand-edit any file under this directory.
