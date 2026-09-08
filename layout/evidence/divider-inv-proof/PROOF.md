# `inv_3v3` -- full-custom device-layout methodology proof, `divider_chain` (issue #306)

Part 1 of #295 (itself one of #292's five block sub-issues): apply the
device-layout methodology issue #299 (Part 1 of #294) already proved for the
PFD/CP block family -- `layout/pll_top/pfd_cp/devgen.py`,
`layout/evidence/pfdcp-inv-proof/` -- to `divider_chain`'s own leaf-cell set,
on this block's static-CMOS-inverter representative cell. See
`layout/evidence/divider-tgate-proof/PROOF.md` for this issue's other cell,
`tgate_3v3` -- the transmission gate, the topology #299 did not cover, and
the one that actually needed a generator change (see that file for the
full story).

## What this is, and is not

This **is** a real, DRC-clean **and** LVS-clean transistor-level layout of
`design/inv_3v3.sch` -- one `pfet_03v3` (W=2.5 um/L=0.28 um) + one
`nfet_03v3` (W=1 um/L=0.28 um), gates tied to `A`, drains tied to `Y`,
sources/bodies tied to `VDD`/`VSS` -- drawn from scratch on the PDK's own
device/interconnect layers, via direct `klayout.db` geometry
(`layout/pll_top/divider_chain/devgen.py`), **not** `klt gen`/
`klt gen-compose`. That path is a confirmed, already-filed dead end for this
whole methodology (2AMLogic/klayout-tools#1575, reproduced by issue #299 and
not re-run here per issue #306's own acceptance criteria -- see
`devgen.py`'s module docstring for the citation this module inherits
without re-deriving).

`devgen.py` itself is a sibling copy of `pfd_cp/devgen.py` (not a shared
import -- see that module's own docstring, "each full-custom leaf-cell
family owns its own generator"), generalized in this package with two new,
opt-in capabilities (`Device.body_net`, `build_stack_cell()`'s
`bypass_nets`) neither of which this cell, `inv_3v3`, actually needs -- see
`divider-tgate-proof/PROOF.md` for why `tgate_3v3` does.

## Standalone DRC-clean

```bash
python3 -m divider_chain.inv_3v3 --outdir <workdir>   # (from layout/pll_top/)
python3 layout/run_pv.py drc <workdir>/inv_3v3.gds --top inv_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `inv_3v3` DRC, table `main` | clean | `Klayout DRC run is clean. GDS has no DRC violations.` | **PASS** |

## LVS-clean

A hand-written reference netlist (`inv_3v3.spice`), stated independently of
the layout -- the same "independently stated schematic" discipline
`layout/harness/cell.py`'s docstring describes for `inv_tb`, device sizes
read directly off `design/inv_3v3.sch`:

```spice
.subckt inv_3v3 A Y VDD VSS
M_MP Y A VDD VDD pfet_03v3 W=2.5u L=0.28u
M_MN Y A VSS VSS nfet_03v3 W=1u L=0.28u
.ends
```

```bash
python3 layout/run_pv.py lvs <workdir>/inv_3v3.gds <workdir>/inv_3v3.spice \
  --top inv_3v3 --run-dir <rundir>
```

| Check | Expected | Got | Verdict |
|---|---|---|---|
| `inv_3v3` LVS (vs. the hand-written reference) | match | `Congratulations! Netlists match.` | **PASS** |

Not a vacuous pass -- the extracted netlist (`lvs-clean/inv_3v3.cir`) shows
two real matched devices, sizes intact:

```spice
.SUBCKT inv_3v3 VSS VDD
M$1 VDD $1 $3 VDD pfet_03v3 L=0.28U W=2.5U AS=1.25P AD=1.25P PS=6U PD=6U
M$2 $3 $1 VSS VSS nfet_03v3 L=0.28U W=1U AS=0.5P AD=0.5P PS=3U PD=3U
.ENDS inv_3v3
```

Uses the harness's documented `--lvs-sub=VSS` default for the NMOS body's
global substrate tie; the PMOS body's n-well tie is drawn/wired explicitly
by `devgen.py`'s `build_stack_cell()` (see that module's docstring's
"WELL/SUBSTRATE TIES" section). `A`/`Y` are not labelled top-level pins in
this proof (2-terminal nets `build_stack_cell()` wires internally with no
Metal1 label, matching `pfdcp_inv_3v3`'s own convention) -- the LVS engine
matched them by netlist topology, not by name, which is exactly what the
extracted `.cir`'s anonymous `$1`/`$3` internal nodes show.

## Reusable helper module

`layout/pll_top/divider_chain/devgen.py` -- reused/generalized from
`layout/pll_top/pfd_cp/devgen.py` (same `Device`/`build_stack_cell()` API and
DRC-proven margins), with two new opt-in fields this cell does not need
(`Device.body_net`, `build_stack_cell()`'s `bypass_nets`) that
`tgate_3v3.py` does -- see `divider-tgate-proof/PROOF.md` for the concrete
LVS mismatch that motivated each one. `layout/pll_top/divider_chain/inv_3v3.py`
is the ~30-line consumer this proof cell needed.

`layout/tests/test_divider_devgen.py` is the smoke-test coverage for this
contract (device-table sanity, net-resolution/pin-promotion behaviour,
`inv_3v3`'s and `tgate_3v3`'s device tables, the bypass-lane/body-net paths).

## Friction protocol (CLAUDE.md)

No new klayout-tools gap this pass. Per issue #306's own acceptance
criteria, the already-known `klt gen`/`klt gen-compose` signoff-DRC gap
(2AMLogic/klayout-tools#1575, filed via #299) is not re-filed here.

## Provenance

| | |
|---|---|
| Generated | 2026-09-08T23:35 UTC |
| Invoked as | `python3 -m divider_chain.inv_3v3 --outdir <workdir>` (from `layout/pll_top/`), then `python3 layout/run_pv.py drc`/`lvs` |
| PDK | `gf180mcuD`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare) |
| KLayout (application, deck runner) | `KLayout 0.28.16` |
| DRC deck | `<pdk>/libs.tech/klayout/drc/run_drc.py`, table `main`, `--variant=D` |
| LVS deck | `<pdk>/libs.tech/klayout/lvs/run_lvs.py`, `--lvs_sub=VSS` |

## Artifacts

| Path | What it is |
|---|---|
| `inv_3v3.gds` | the real transistor-level leaf cell (1 pfet_03v3 + 1 nfet_03v3, wired, tapped) |
| `inv_3v3.spice` | the hand-written, independently-stated LVS reference netlist |
| `drc-clean/inv_3v3_main.lyrdb` | KLayout DRC report database (empty violations) |
| `drc-clean/drc.stdout.log` | captured `run_drc.py` stdout+stderr |
| `lvs-clean/inv_3v3.cir` | the extracted netlist (two matched devices, sizes intact) |
| `lvs-clean/inv_3v3.lvsdb` | KLayout LVS report database |
| `lvs-clean/lvs.stdout.log` | captured `run_lvs.py` stdout+stderr, including the match verdict |

Regenerate via `python3 -m divider_chain.inv_3v3 --outdir <dir>` (from
`layout/pll_top/`) + `layout/run_pv.py drc`/`lvs`; do not hand-edit any file
under this directory.
