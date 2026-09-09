# `cp_leg_n`/`cp_leg_p` -- charge pump unit-leg composite device layout (issue #319)

Part 3a of #294's device-layout methodology (a decomposition of #301, itself
Part 3 of #294, one of #292's five block sub-issues).

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean transistor-level layout of
`design/cp_leg_n.sch` and `design/cp_leg_p.sch` -- one `cp_leg_n` cell (4x
`nfet_03v3`) and one `cp_leg_p` cell (4x `pfet_03v3`), each drawn once and
proven standalone. It is **not** the common-centroid *array* of 4 legs per
polarity, the 4x-scaled bias branch, or the shared bias/enable mesh routing
between array instances (Part 3b, a sibling issue); it is **not** the glue
inverters/steering switches/output-stage assembly (Part 3c, a sibling
issue); and it does not touch `cp_dumpbuf` (Part 4, #302, already merged).

## The gap this closes: a 3-way net `devgen.build_stack_cell()` can't resolve

`layout/pll_top/pfd_cp/devgen.py`'s `build_stack_cell()` (issue #299) only
auto-wires nets that appear on exactly 1 or 2 device terminals within one
left-aligned vertical column. Each CP leg is **4 devices with a 3-way net**:
`BG` is `MDIS`'s drain, `MEN`'s drain, *and* `MBOT`/`MTOP`'s gate -- three
terminals on one net, split across two structurally independent 2-device
columns (the enable-steering pair `MDIS`/`MEN`, and the wide-swing cascode
mirror `MBOT`/`MTOP` + `MCASC`).

Per `devgen.py`'s own guidance ("compose several `build_stack_cell` columns
side by side and wire between them by hand") and `cp_dumpbuf.py`'s identical
precedent (issue #301/#302), `layout/pll_top/pfd_cp/cp_leg.py` draws both
columns directly with `devgen.mosfet()`/`devgen.Device` and hand-routes the
one net `build_stack_cell()` could not have resolved: a single Metal1 jog
from `MDIS`'s own (already-resolved) drain pad, in the steering column,
over to `MBOT`/`MTOP`'s own gate pad, in the mirror column -- reachable with
no vertical detour because this cell's fixed device geometry
(`L_steer=0.3 um`, `L_mirror=1.0 um`, both columns bottom-aligned at
`y=0.0`) places the mirror device's `gate_y_center` (always `1.0 um`,
independent of `W`) strictly inside `MDIS`'s own drain pad's Y extent
(`[0.86, 1.32] um`, also independent of `W`). See `cp_leg.py`'s own module
docstring for the full derivation, and `layout/tests/test_cp_leg_devgen.py`
for the numeric assertion (`HandRoutedBgTapGeometryTests`) plus a negative
control (`test_unreachable_bg_tap_raises`) confirming the hand-route raises
rather than silently drawing a disconnected net if that precondition ever
stops holding.

The `VSS`/`VDD` rail net is handled the same way: `MDIS`'s and
`MBOT`/`MTOP`'s own outer (source) pads are both bottom pads at the same
`y_bottom=0.0`, so they always share the exact same Y band regardless of
`W` -- a single horizontal Metal1 strap joins them, with one
substrate/n-well tap (`devgen._well_tap()`, reused directly) dropped into
the same gap between the two columns.

No `klayout-tools`/`klt` gap is re-filed here -- this module inherits issue
#299's own reproduced-and-filed gap
([2AMLogic/klayout-tools#1575](https://github.com/2AMLogic/klayout-tools/issues/1575))
without needing to re-run it; see `devgen.py`'s own module docstring for the
full worked reproduction this choice is based on.

## Standalone DRC-clean

```bash
python3 -m pfd_cp.cp_leg_n --outdir <workdir>          # (from layout/pll_top/)
python3 -m pfd_cp.cp_leg_p --outdir <workdir>
python3 layout/run_pv.py drc <workdir>/cp_leg_n.gds --top cp_leg_n --run-dir <rundir>
python3 layout/run_pv.py drc <workdir>/cp_leg_p.gds --top cp_leg_p --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_leg_n` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |
| `cp_leg_p` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

Also run with `--offgrid` during development (signoff-grade, off-grid class
included) with the identical clean result for both cells; the committed
evidence uses the harness's default (`--no_offgrid`), matching every prior
part's own recorded convention.

The one real violation this pass actually hit and fixed during development
(not present in the committed geometry): the substrate/n-well tap's own
Metal1 pad, initially centred vertically on the rail strap, landed only
0.05 um below `MBOT`/`MTOP`'s own hand-routed gate pad -- `M1.2a` (Metal1-
to-Metal1 spacing, 0.23 um min). Fixed by placing the tap's own Y position
relative to the mirror device's own drawn `gate_pad[1]` (0.35 um of
clearance, not a hand-picked constant) rather than centring it on the rail
strap's own Y band -- see `cp_leg.py`'s `_route_rail_strap_and_tap()`.

Real device rules this run actually exercised (every table in the `main`
deck ran): `DF.1a_LV`/`DF.3a_LV`/`DF.6_LV`/`DF.16_LV` (comp width/space/gate
overhang/well-edge clearance), `PL.2_LV`/`PL.4_LV`/`PL.5a_LV`/`PL.5b_LV`
(poly gate length/endcap/field spacing), `CO.1`-`CO.10` (contact size/
space/enclosure), `NP.1`/`NP.2`/`NP.3*`/`NP.5*`, `PP.1`/`PP.2`/`PP.3*`/
`PP.5*` (implant width/space/enclosure -- including the tap's own opposite-
implant clearance), `NW.1a_LV`/`DF.4c_LV`/`DF.4d_LV` (n-well enclosure,
`cp_leg_p` only), `M1.1`/`M1.2a`/`M1.3` (Metal1 width/space/area -- the rule
family the fix above targets directly).

## LVS-clean

Hand-written reference netlists (`cp_leg_n.spice`/`cp_leg_p.spice`), stated
independently of the layout -- the same "independently stated schematic"
discipline `layout/harness/cell.py`'s docstring describes -- with device
sizes/nodes read directly off `design/cp_leg_n.sch`/`design/cp_leg_p.sch`:

```spice
.subckt cp_leg_n VBN VCASCN EN ENB TAIL VSS
M_MEN BG EN VBN VSS nfet_03v3 W=1u L=0.3u
M_MDIS BG ENB VSS VSS nfet_03v3 W=1u L=0.3u
M_MBOT MID BG VSS VSS nfet_03v3 W=4u L=1u
M_MCASC TAIL VCASCN MID VSS nfet_03v3 W=4u L=1u
.ends
```

```spice
.subckt cp_leg_p VBP VCASCP EN ENB TAIL VDD
M_MEN BG ENB VBP VDD pfet_03v3 W=1u L=0.3u
M_MDIS BG EN VDD VDD pfet_03v3 W=1u L=0.3u
M_MTOP MID BG VDD VDD pfet_03v3 W=12u L=1u
M_MCASC TAIL VCASCP MID VDD pfet_03v3 W=12u L=1u
.ends
```

```bash
python3 layout/run_pv.py lvs <workdir>/cp_leg_n.gds <workdir>/cp_leg_n.spice --top cp_leg_n --run-dir <rundir>
python3 layout/run_pv.py lvs <workdir>/cp_leg_p.gds <workdir>/cp_leg_p.spice --top cp_leg_p --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `cp_leg_n` LVS (vs. the hand-written reference) | match | `Congratulations! Netlists match.` | **PASS** |
| `cp_leg_p` LVS (vs. the hand-written reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- the extracted netlists show all four devices per leg,
sizes intact, with `BG`/`MID` correctly extracted as anonymous internal
nodes (never appearing in either `.SUBCKT` port list -- matched by
topology, not name):

```spice
.SUBCKT cp_leg_n EN ENB TAIL VBN VCASCN VSS
M$1 TAIL VCASCN $6 VSS nfet_03v3 L=1U W=4U AS=2P AD=2P PS=9U PD=9U
M$2 VBN EN $2 VSS nfet_03v3 L=0.3U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
M$3 $6 $2 VSS VSS nfet_03v3 L=1U W=4U AS=2P AD=2P PS=9U PD=9U
M$4 $2 ENB VSS VSS nfet_03v3 L=0.3U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
.ENDS cp_leg_n
```

```spice
.SUBCKT cp_leg_p EN ENB TAIL VBP VCASCP VDD
M$1 VBP ENB $4 VDD pfet_03v3 L=0.3U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
M$2 $5 $4 VDD VDD pfet_03v3 L=1U W=12U AS=6P AD=6P PS=25U PD=25U
M$3 TAIL VCASCP $5 VDD pfet_03v3 L=1U W=12U AS=6P AD=6P PS=25U PD=25U
M$4 $4 EN VDD VDD pfet_03v3 L=0.3U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
.ENDS cp_leg_p
```

Uses the harness's documented `--lvs-sub=VSS` default (`layout/README.md`'s
"substrate-net gotcha") for `cp_leg_n`'s NMOS bodies' global substrate tie.
`cp_leg_p`'s PMOS bodies' n-well tie is **not** global in this deck (same
citation `devgen.py`'s own docstring gives), so `cp_leg.py` always draws and
wires a real n-well tap for it -- no `--lvs-sub` override was needed for
`cp_leg_p`'s own clean run.

## Reusable module

`layout/pll_top/pfd_cp/cp_leg.py` -- `LegSpec` (the per-polarity parameters
that differ between `cp_leg_n`/`cp_leg_p`) + `build_leg()` (the shared
topology: two `devgen.mosfet()`-drawn columns, the hand-routed `BG` tap, the
rail strap+tap). `cp_leg_n.py`/`cp_leg_p.py` are the ~50-line consumers this
issue's own two proof cells needed -- the template Part 3b (the
common-centroid array + bias branch) and Part 3c (the glue/output-stage
assembly) are expected to build on top of.

`layout/tests/test_cp_leg_devgen.py` is the smoke-test coverage this
contract needs independent of this one-off proof run: device-table
sanity against both schematics, the hand-routed `BG` tap's own geometric
precondition (asserted numerically, plus a negative-control raise),
boundary-pin promotion (`BG`/`MID` never promoted), n-well presence/absence,
and footprint sanity.

## Provenance

| | |
|---|---|
| Generated | 2026-09-09T02:05 UTC |
| Invoked as | `python3 -m pfd_cp.cp_leg_n --outdir <workdir>` / `python3 -m pfd_cp.cp_leg_p --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`/`lvs`, `LAYOUT_PV_PYTHON` pointed at a local venv (`klayout` + `docopt`) per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.30.10` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--lvs_sub=VSS` |

## Artifacts

| Path | What it is |
|---|---|
| `cp_leg_n.gds`/`cp_leg_p.gds` | the real transistor-level leaf cells (4 devices each, wired, tapped) |
| `cp_leg_n.spice`/`cp_leg_p.spice` | the hand-written, independently-stated LVS reference netlists |
| `drc-clean/cp_leg_n_main.lyrdb`/`cp_leg_p_main.lyrdb` | KLayout DRC report databases (empty violations) |
| `drc-clean/cp_leg_n.drc.stdout.log`/`cp_leg_p.drc.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |
| `lvs-clean/cp_leg_n.cir`/`cp_leg_p.cir` | the extracted netlists (four matched devices each, sizes intact) |
| `lvs-clean/cp_leg_n.lvsdb`/`cp_leg_p.lvsdb` | KLayout LVS report databases |
| `lvs-clean/cp_leg_n.lvs.stdout.log`/`cp_leg_p.lvs.stdout.log` | captured `run_lvs.py` stdout+stderr, including the match verdicts |

Regenerate via `python3 -m pfd_cp.cp_leg_n`/`python3 -m pfd_cp.cp_leg_p`
(from `layout/pll_top/`) + `layout/run_pv.py drc`/`lvs`; do not hand-edit
any file under this directory.
