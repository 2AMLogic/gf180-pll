# `pfdcp_inv_3v3` -- full-custom device-layout methodology proof (issue #299)

Part 1 of #294 (itself one of #292's five block sub-issues): prove out a
first, working, DRC/LVS-clean full-custom device-layout path against this
repo's own PDK install, on one representative PFD/CP leaf cell, and hand
Parts 2-4 (#300-#302: the PFD chains, the CP arrays, the dump-buffer
isolated well) a reusable Python helper module instead of each re-deriving
the same drawing/wiring pattern.

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean transistor-level layout of
`design/pfdcp_inv_3v3.sch` -- one `pfet_03v3` (W=1.5 um/L=0.3 um) + one
`nfet_03v3` (W=0.5 um/L=0.3 um), gates tied to `A`, drains tied to `Y`,
sources/bodies tied to `VDD`/`VSS` -- drawn from scratch on the PDK's own
device/interconnect layers (`comp` 22/0, `poly2` 30/0, `contact` 33/0,
`nplus` 32/0, `pplus` 31/0, `nwell` 21/0, `metal1` 34/0, plus the
34/10 Metal1 *pin* purpose the official LVS deck reads net names from --
see `layout/pll_top/pfd_cp/devgen.py`'s module docstring). It is **not**
`layout/evidence/inv-tb-proof/`'s reused PDK standard cell, and it is a
second, independent full-custom leaf-cell family alongside
`layout/pll_top/vco/`'s VCO ring (issue #293) -- this issue's own job was
proving the methodology, not extending the VCO's.

**Scope, per issue #299's own "Out of scope" note**: only this one
representative leaf cell is drawn here. The 24-inverter delay chain, the
srlatch/edgedet chains, the CP arrays, and the dump buffer are Parts 2-4's
job (#300-#302), built on the `layout/pll_top/pfd_cp/devgen.py` helper this
issue lands.

## `klt gen`/`klt gen-compose` vs. direct `klayout.db` (the acceptance
criterion's own "document the choice either way")

Issue #299's acceptance criteria named `klt gen`(`mos_array`) composed via
`klt gen-compose` as the primary path, with a documented fallback to direct
drawing if "a generator round-trip proves impractical for a single device".
Both were tried, in that order.

### What `klt gen mos_array` -> `klt gen-compose` actually did

```bash
klt gen mos_array --pdk gf180mcuD --pdk-root "$PDK_ROOT" \
  --params '{"w_um":1.5,"l_um":0.3,"rows":1,"cols":1,"dummy":0,"flavor":"pfet","gate_contact":true}' \
  --cell-name MP -o pfet.gds --format json > pfet.json
klt gen mos_array --pdk gf180mcuD --pdk-root "$PDK_ROOT" \
  --params '{"w_um":0.5,"l_um":0.3,"rows":1,"cols":1,"dummy":0,"flavor":"nfet","gate_contact":true}' \
  --cell-name MN -o nfet.gds --format json > nfet.json
```

...composed with `placement.strategy: "row"`, `blocks[].orientation:
"mirror_x"` on the second block (the exact worked "CMOS inverter" example
`docs/cli/gen-compose.md` itself ships, so the two drains face each other
instead of the router having to cross through one block's own interior),
and `connectivity[]` wiring `A` (the two gates) and `Y` (the two drains):

| Net | `gen-compose` result |
|---|---|
| `A` (gate-gate) | `status: "routed"`, exit 0 |
| `Y` (drain-drain) | `status: "routed"`, exit 0 (only after the `mirror_x` orientation fix -- without it, the same-facing-drain case `docs/cli/gen-compose.md`'s "Block orientation" section documents, `unrouted_nets: ["Y"]`, exit 3) |

The composed GDS also passed `klt drc --deck gf180mcu` (the curated,
~10-rule subset) clean.

**It did not pass gf180mcu's own foundry-authored signoff DRC deck** -- the
same `main`-table run `layout/run_pv.py drc` drives, and the actual gate for
this issue's own acceptance criterion. Even the single simplest possible
`mos_array` request (one unit device, `dummy: 0`, no `gate_contact`) failed
six real rule families on that deck:

| Rule | What it checks | Minimum (per gf180mcuD's `main` deck) |
|---|---|---|
| `DF.6_LV` | COMP extend beyond gate (source/drain overhang) | 0.24 um |
| `PL.4_LV` | Poly2 extension beyond COMP (gate endcap) | 0.22 um |
| `PL.5a_LV` | Field poly2 to unrelated COMP spacing | 0.10 um |
| `PL.5b_LV` | Field poly2 to related COMP spacing | 0.10 um |
| `CO.7` | COMP contact to Poly2-on-COMP spacing | 0.15 um |
| `DF.12` | COMP not covered by Nplus/Pplus is forbidden | (coverage) |

...and the violation count scaled with unit-device count (9 items at
`dummy: 0`, 27 at `mos_array`'s own default `dummy: 1`) -- a structural
property of the drawn geometry, not an edge effect of either setting.
`voltage_flavor="medium_voltage"` does not help (it draws gf180mcu's
`Dualgate` marker over the existing footprint with no geometry change, so
the six failures above are unaffected) and is not even the correct marker
for this design: `nfet_03v3`/`pfet_03v3` are gf180mcu's own **`_LV`**-class
3.3 V devices (confirmed directly against
`libs.tech/klayout/lvs/rule_decks/mos_extraction.lvs`'s own
`extract_devices(mos4('pfet_03v3'), {'G' => pgate_3p3v, ...})`, with no
`dualgate` term anywhere in `pgate_3p3v`'s/`ngate_3p3v`'s own derivation in
`mos_derivations.lvs`) -- requesting the marker anyway additionally failed
that marker's own (larger) `_MV`-class version of the same six rule
families (`DF.6_MV`, `PL.4_MV`, `PL.5a_MV`, `PL.5b_MV`, plus the
Dualgate-enclosure rules `DV.6`/`DV.8`).

This is a genuine, reproduced capability gap in `klt gen mos_array`'s
gf180mcu output -- not a request-shape mistake on this issue's part -- filed
generically (tool gap only, no design details) per CLAUDE.md's friction
protocol:
**[2AMLogic/klayout-tools#1575](https://github.com/2AMLogic/klayout-tools/issues/1575)**.

### The fallback: direct `klayout.db` geometry (what actually ships)

Given the gap above, this issue falls back to the documented alternative:
direct `klayout.db` construction, the same approach
`layout/pll_top/vco/primitives.py` already uses (and already proved
DRC-clean, issue #293) and `layout/README.md`'s "Why this isn't `klt drc`"
section already justifies for this whole flow. `layout/pll_top/pfd_cp/devgen.py`
generalizes that approach into a small, reusable, device-list-driven API
(`Device` + `build_stack_cell()`) rather than a copy of the VCO's own
block-specific script -- see that module's docstring for the full contract
and the DRC-citation-by-citation derivation of every margin it uses (the
same values `vco/primitives.py` already proved clean, applied to a second,
independent leaf-cell family).

Nothing about this choice is permanent: `devgen.py`'s docstring notes it
would happily be replaced by a call into a fixed `klt gen` generator once
#1575 is addressed -- this issue proves the *methodology* (schematic ->
device list -> DRC/LVS-clean GDS + reusable helper), not a commitment to one
specific drawing backend.

## Standalone DRC-clean

```bash
python3 -m pfd_cp.pfdcp_inv --outdir <workdir>          # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/pfdcp_inv_3v3.gds --top pfdcp_inv_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfdcp_inv_3v3` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

Real device rules this run actually exercised (every table in the `main`
deck ran; this is what the cell's own geometry interacts with): `DF.1a_LV`/
`DF.3a_LV`/`DF.6_LV`/`DF.16_LV` (comp width/space/gate overhang/well-edge
clearance), `PL.2_LV`/`PL.4_LV`/`PL.5a_LV`/`PL.5b_LV` (poly gate
length/endcap/field spacing), `CO.1`-`CO.10` (contact size/space/
enclosure), `NP.1`/`NP.2`/`NP.3*`/`NP.5*`, `PP.1`/`PP.2`/`PP.3*`/`PP.5*`
(implant width/space/enclosure -- including the n-well tap's/p-substrate
tap's own opposite-implant clearance, `devgen.TAP_GAP_UM`'s own citation),
`NW.1a_LV`/`DF.4c_LV`/`DF.4d_LV` (n-well enclosure), `M1.1`/`M1.2a`/`M1.3`
(Metal1 width/space/area). `klt drc --deck gf180mcu` (the curated subset)
independently confirms `status: "clean"` on the same GDS.

Also run with `--offgrid` during development (signoff-grade, off-grid class
included) with the identical clean result; the committed evidence uses the
harness's default (`--no_offgrid`, matching `layout/README.md`'s documented
`prove`/`drc` default) for wall-time parity with the rest of this repo's
recorded DRC evidence.

## LVS-clean

A hand-written reference netlist (`pfdcp_inv_3v3.spice`), stated
independently of the layout -- the same "independently stated schematic"
discipline `layout/harness/cell.py`'s docstring describes for `inv_tb` --
with device sizes/nodes read directly off `design/pfdcp_inv_3v3.sch`:

```spice
.subckt pfdcp_inv_3v3 A Y VDD VSS
M_MP Y A VDD VDD pfet_03v3 W=1.5u L=0.3u
M_MN Y A VSS VSS nfet_03v3 W=0.5u L=0.3u
.ends
```

```bash
python3 layout/run_pv.py lvs <workdir>/pfdcp_inv_3v3.gds <workdir>/pfdcp_inv_3v3.spice \
  --top pfdcp_inv_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `pfdcp_inv_3v3` LVS (vs. the hand-written reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- `lvs-clean/pfdcp_inv_3v3.cir` (the extracted netlist)
shows two real matched devices, sizes intact:

```spice
.SUBCKT pfdcp_inv_3v3 VSS VDD
M$1 VDD $1 $3 VDD pfet_03v3 L=0.3U W=1.5U AS=0.75P AD=0.75P PS=4U PD=4U
M$2 $3 $1 VSS VSS nfet_03v3 L=0.3U W=0.5U AS=0.25P AD=0.25P PS=2U PD=2U
.ENDS pfdcp_inv_3v3
```

Uses the harness's documented `--lvs-sub=VSS` default (`layout/README.md`'s
"substrate-net gotcha") for the NMOS body's global substrate tie. The PMOS
body's n-well tie is **not** global in this deck (confirmed directly:
`general_connections.lvs` only has `connect_global(sub, substrate_name)`,
with no equivalent for `nwell_con`), so `devgen.py`'s `build_stack_cell()`
always draws and wires a small n-well tap -- this is the concrete reason
`layout/pll_top/pfd_cp/devgen.py`'s module docstring gives for treating the
n-well tie as mandatory while the substrate tie is "DRC hygiene, not an
LVS requirement" for this deck. Only `VDD`/`VSS` are labelled top-level
pins in this proof (`A`/`Y` are 2-terminal nets `build_stack_cell()` wires
internally with no Metal1 label -- see `devgen.py`'s docstring); the LVS
engine matched them by netlist topology, not by name, which is exactly
what the extracted `.cir`'s anonymous `$1`/`$3` internal nodes above show.

## Reusable helper module

`layout/pll_top/pfd_cp/devgen.py` -- `Device` (flavor, `w_um`/`l_um`, three
terminal net names) + `build_stack_cell(top_name, devices)` (a
left-aligned vertical column, automatic 1-/2-terminal net resolution, a
wired-in n-well/p-substrate tie). Full contract, the supported topology's
limits, and the DRC-citation-by-citation margin derivation are in that
module's own docstring. `layout/pll_top/pfd_cp/pfdcp_inv.py` is the ~30-line
consumer this issue's own proof cell needed -- the template Parts 2-4
(#300-#302) are expected to follow for their own device tables.

`layout/tests/test_pfdcp_devgen.py` is the smoke-test coverage this
contract needs independent of this one-off proof run (device-table
sanity, net-resolution/pin-promotion behaviour, the unsupported->raises
case for a >2-terminal net).

## Friction protocol (CLAUDE.md)

One genuine, concretely-hit gap this pass, filed generically:
[2AMLogic/klayout-tools#1575](https://github.com/2AMLogic/klayout-tools/issues/1575)
-- `klt gen mos_array`'s gf180mcu output is only verified against `klt
drc`'s own curated ~10-rule subset, not the PDK's real signoff deck (see
above for the full reproduction and the six failing rule families).
Everything else this pass needed (the Metal1 pin-label datatype
34/10-vs-34/0 distinction, the nwell-vs-substrate global-tie asymmetry) is
PDK-native LVS-deck behaviour discoverable by reading the deck's own `.lvs`
sources -- not a `klayout-tools` capability gap, and out of scope for that
tracker.

## Provenance

| | |
|---|---|
| Generated | 2026-09-08T20:57 UTC |
| Invoked as | `python3 -m pfd_cp.pfdcp_inv --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`/`lvs`, `LAYOUT_PV_PYTHON` pointed at a local venv (`klayout` + `docopt`) per `layout/README.md`'s Prerequisites |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| `klt` (gap-reproduction only, not part of the shipped drawing path) | `0.3.0+gc6dbf66c53c6` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--lvs_sub=VSS` |

## Artifacts

| Path | What it is |
|---|---|
| `pfdcp_inv_3v3.gds` | the real transistor-level leaf cell (1 pfet_03v3 + 1 nfet_03v3, wired, tapped) |
| `pfdcp_inv_3v3.spice` | the hand-written, independently-stated LVS reference netlist |
| `drc-clean/pfdcp_inv_3v3_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr (full `main`-table rule list) |
| `lvs-clean/pfdcp_inv_3v3.cir` | the extracted netlist (two matched devices, sizes intact) |
| `lvs-clean/pfdcp_inv_3v3.lvsdb` | KLayout LVS report database |
| `lvs-clean/lvs.stdout.log` | captured `run_lvs.py` stdout+stderr, including the match verdict |

Regenerate via `python3 -m pfd_cp.pfdcp_inv` (from `layout/pll_top/`) +
`layout/run_pv.py drc`/`lvs`; do not hand-edit any file under this
directory.
