# sim/harness — the PVT corner runner

Reproducible ngspice simulation against the gf180mcu PDK. This document covers
**how to run** the harness and **how to write a testbench**.

The *output* of a run — directory layout, record-id format, the summary
record field set, and the append-only rule — is defined by
[`sim/README.md`](../README.md), not here. That convention is authoritative;
this harness exists to produce records that conform to it. Ported and
adapted from the sim-harness pattern bootstrapped in `2AMLogic/gf180-bandgap`
PR #23, per CLAUDE.md's harness-bootstrap rule (see `sim/harness/__init__.py`
for the deltas from that pattern).

```
sim/
  run_corners.py            CLI entry point (stdlib python3, no venv)
  env.sh                    `source sim/env.sh` to export the same PDK to your shell
  selftest.sh               harness acceptance test (unit tests + end-to-end PVT run)
  pdk.json                  committed PDK defaults (variant, extra search roots)
  pdk.local.json            machine-local PDK override (git-ignored, optional)
  harness/                  the runner itself (this directory)
  tests/                    harness unit tests (no PDK, no ngspice required)

  <experiment-slug>/        one per claim under test -- see sim/README.md
    testbench/              tb.json + netlist fragment      <- you write these
    netlist-snapshots/      frozen netlist per record       <- the harness writes these
    corners/<record-id>/    raw <corner-id>.log per PVT point
    records/<record-id>.md  append-only summary record
    work/                   generated ngspice decks (git-ignored, disposable)
```

## Quick start

```bash
python3 sim/run_corners.py --check-env       # is ngspice + the PDK present?
python3 sim/run_corners.py --list            # experiments, corners, corner sets
python3 sim/run_corners.py harness-selftest  # run the full PVT grid, mint a record
bash sim/selftest.sh                         # prove the harness works (writes nothing)
```

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| `ngspice` | simulation | `brew install ngspice` / `apt-get install ngspice` |
| gf180mcu PDK | device models | `pip install volare && volare enable --pdk gf180mcu <hash>` |
| `xschem` | schematic capture (optional for simulation) | `brew install xschem` / distro package |
| python3 >= 3.9 | the harness | stdlib only, no packages |

The harness never hardcodes a PDK path. It resolves one, in order:

1. `GF180_PDK_PATH` — the *variant* directory, e.g. `~/.volare/gf180mcuD`
   (the one containing `libs.tech/`).
2. `GF180_PDK_ROOT` — back-compat with the interim `sim/lib/simenv.sh` shim's
   own override (same shape as `GF180_PDK_PATH`).
3. `PDK_ROOT` (+ `PDK`, default `gf180mcuD`) — the open_pdks / OpenLane convention.
4. `sim/pdk.local.json` — machine-local, git-ignored.
5. `sim/pdk.json` — committed defaults.
6. Built-in search roots: `~/.volare`, `~/.ciel`, `/usr/share/pdk`,
   `/usr/local/share/pdk`, `~/share/pdk`, `/opt/pdk`.

If nothing is found the runner exits `3` with install instructions rather than
producing a misleading result. `sim/run_corners.py --print-env` emits the
resolved paths as shell exports; `source sim/env.sh` applies them so that an
interactive ngspice or xschem session uses the identical PDK.

## The PVT grid

CLAUDE.md requires PVT corners on every recorded result. The defaults are
baked into `harness/corners.py` and are what a testbench gets unless its
manifest says otherwise:

- **Temperature**: -40, 27, 125 °C
- **Voltage**: nominal +/-10% (3.3 V flavor -> 2.97 / 3.30 / 3.63 V)
- **Process**: see below

gf180mcu has no single global corner switch — each device family carries its
own `.lib` section in `sm141064.ngspice`. This repo's device menu (see
`sim/README.md`) is MOS plus three *independent* passive axes (no BJT/diode —
unlike the sister `gf180-bandgap` repo, no block here uses those families), so
a named corner here is a bundle of four sections (MOS, resistor, MOS cap, MIM
cap):

| Corner | Meaning |
|---|---|
| `typical` | everything typical |
| `ff` / `ss` / `fs` / `sf` | MOS skewed, passives typical |
| `res_ff` / `res_ss` | resistor sheet rho skewed, rest typical |
| `moscap_ff` / `moscap_ss` | MOS cap skewed, rest typical |
| `mimcap_ff` / `mimcap_ss` | MIM cap skewed, rest typical |
| `all-slow` / `all-fast` | every family skewed the same direction |

Corner sets: `typical` (1), `mos` (5, the default), `passives` (6), `full`
(13 — every bundle above). Use `passives` or `full` for anything whose
accuracy rides on the loop-filter resistor or caps (a MOS-only sweep silently
leaves every passive at typical — see `sim/README.md`'s "Default corner
matrix" hazard note).

Each point becomes one `<corner-id>` — `<process>_<temp>c_<supply>v`, the
naming `sim/README.md` ratifies — and one raw log under
`corners/<record-id>/`.

Override any axis from the command line:

```bash
python3 sim/run_corners.py harness-selftest --corner-set full -j 8
python3 sim/run_corners.py harness-selftest --corners typical res_ss --temps -40 125
python3 sim/run_corners.py harness-selftest --supply 5.0 --supply-tol 0.10   # a different flavor
```

**Subsets need a reason.** `sim/README.md` requires every record's *Corner
matrix run* field to be the full mandated matrix "unless the record states why
a subset was used". The runner enforces that: if the grid you asked for is
missing a mandated temperature, a mandated supply, or one of the five MOS
process bundles, it refuses to write a record unless you supply
`--subset-reason '<why>'` (which is copied verbatim into the record), or pass
`--no-write` because you are only debugging.

```bash
# debugging: runs, records nothing
python3 sim/run_corners.py harness-selftest --corners typical --temps 27 --supply-tol 0 --no-write

# a deliberate, justified subset: runs and records, with the reason on the record
python3 sim/run_corners.py harness-selftest --corners typical --temps 27 \
    --subset-reason "nominal-only mismatch sweep; distribution claim, see Statistical convention"
```

## Writing a testbench

Create `sim/<experiment-slug>/testbench/` with a manifest and a netlist
fragment. The slug is the experiment directory from `sim/README.md`: one per
distinct claim under test, kebab-case.

`tb.json`:

```json
{
  "name": "my-experiment",
  "description": "one line, shows up in --list and in the record",
  "claim": "spec/pll.md#lock-time",
  "methodology": [
    "one bullet per methodology point -- measurement criterion, simulator",
    "settings, and any known limitation. Rendered into the record's",
    "Methodology / criteria / limitations field verbatim."
  ],
  "netlist": "my_tb.spice",
  "nominal_supply_v": 3.3,
  "supply_tolerance": 0.1,
  "temperatures_c": [-40, 27, 125],
  "corners": ["full"],
  "analyses": ["op"],
  "params": {"iload": "10u"},
  "options": ["reltol=1e-5"],
  "measure": {"vref": "v(vref)", "iq_ua": "-i(vsup)*1e6"},
  "raw_measures": {
    "tpd": {"analysis": "tran", "expr": "trig v(in) val='vdd_val/2' rise=1 td=1n targ v(out) val='vdd_val/2' fall=1 td=1n"}
  },
  "checks": {"vref": {"min": 1.15, "max": 1.25, "max_spread_pct": 2.0}}
}
```

`claim` is the default for the record's **Claim** field, in either of the two
forms `sim/README.md` accepts: a ratified spec line (`spec/pll.md#anchor`) or
a design-input question (`#4 -> #8: which ...?`). `--claim` overrides it per
run. `methodology` is the default for the record's **Methodology / criteria /
limitations** field — leaving it empty is allowed but renders an explicit
"N/A" rather than silently omitting the field.

The netlist is a **fragment**, not a complete deck. It must not contain
`.include`, `.lib`, `.temp`, `.control`, `.endc`, `.end`, or `.measure`/`.meas`
— the harness owns all of those, which is what lets one netlist sweep the
whole grid unedited (and what stops a fragment from silently pinning a
corner-varying measurement to one temperature). The loader rejects fragments
that break this rule instead of silently mis-recording every corner. The
harness hands the fragment:

| Parameter | Value |
|---|---|
| `vdd_val` | supply for this PVT point |
| `vdd_nom` | nominal supply, for ratio measurements |
| `temp_c` | temperature for this PVT point (also applied via `.temp`) |

**Two measurement mechanisms — pick the one that matches your analysis:**

- **`measure`** (post-analysis `let` expressions): each entry becomes
  `let m_<name> = <expr>` followed by `print` inside the control block,
  evaluated **once, after every analysis in the manifest has run**, against
  whichever analysis's plot is then current. This only produces a clean
  scalar for a manifest with a *single* `op` (or other single-point)
  analysis — on a `tran`/`ac`/`dc` sweep, `<expr>` evaluates to a whole
  waveform vector, not a number, and `print` emits the full trace instead of
  one line. Use `measure` for pure operating-point reads.
- **`raw_measures`** (`{name: {"analysis": ..., "expr": ...}}`): rendered as
  a literal `.measure <analysis> <name> <expr>` statement, so it gets
  ngspice's own per-analysis-type measurement engine — `trig`/`targ`,
  `when`/`rise`/`fall`, `avg`/`from`/`to`, `find`/`at`, etc. This is what
  most real campaigns need (delay chains, lock time, jitter, any transient
  measurement) and what a bare `let` expression cannot express. `analysis`
  must be one of ngspice's supported `.measure` types (`tran`, `dc`, `ac` —
  **not** `op`, which ngspice's `.measure` does not support at all) and must
  match an entry in the manifest's `analyses` list.

A manifest may declare both, but only if the `measure` entries are evaluated
against the *last* analysis to run (see above) — when in doubt, use
`raw_measures` for anything beyond a single-analysis `op` read.

`checks` are evaluated after the sweep:

| Key | Applies to | Meaning |
|---|---|---|
| `min` / `max` | every point | hard limit; failure names the offending corner-id |
| `max_spread_pct` | the grid | `(max-min)/\|mean\|` must stay under the limit |
| `min_spread_pct` | the grid | must *exceed* it — asserts the sweep really moved |

`min_spread_pct` is a harness-integrity check: if `.temp` or a `.lib` section
silently failed to apply, a strongly PVT-sensitive measurement would come back
flat, and this catches that instead of reporting a suspiciously perfect result.

## What a run writes

One run mints one `<record-id>` (`<YYYYMMDD>-<HHMMSS>-<short-git-sha>`) and
writes, under `sim/<experiment-slug>/`:

| Path | Contents |
|---|---|
| `records/<record-id>.md` | the append-only summary record — every field `sim/README.md` mandates: Record ID, Claim, Netlist provenance, Environment provenance, Corner matrix run, Methodology / criteria / limitations, Statistical convention, Result, Links, Timestamp / author, Supersedes |
| `netlist-snapshots/<record-id>.spice` | verbatim frozen copy of the testbench fragment, with its sha256 |
| `corners/<record-id>/<corner-id>.log` | raw ngspice output, one file per PVT point |

Nothing is ever overwritten: the runner refuses to write over an existing
record or snapshot, and mints a later record-id if one is somehow already
taken. Corrections and re-runs get a new record-id and reference the prior one
with `--supersedes <record-id>`. Do not edit or delete anything under
`records/`, `netlist-snapshots/` or `corners/` — see the append-only rule in
`sim/README.md`.

A run taken against a dirty working tree says so in the record's **Netlist
provenance** field and is not citable as a clean-tree result.

Exit codes: `0` pass; `1` a check failed; `2` a simulation failed or did not
converge; `3` environment problem (no ngspice, no PDK, bad manifest,
unjustified PVT subset).

Generated decks land in `sim/<experiment-slug>/work/<record-id>/`
(git-ignored, per the existing `sim/*/work/` convention), so a failing corner
can be reproduced by hand with `ngspice -b sim/<slug>/work/<record-id>/<corner-id>.spice`.

## harness-selftest

`sim/harness-selftest/` is the harness acceptance testbench, not a circuit
deliverable and not a design or spec claim for any PLL block. It runs real
gf180mcu devices (`nfet_03v3`/`pfet_03v3` diode-connected drive current,
`ppolyf_u` RC step response) across the full 63-point default+passive grid,
proving both measurement mechanisms (`raw_measures` avg and trig/targ) work
end to end against real ngspice output, that the MOS and resistor `.lib`
sections actually change the result between corners (`min_spread_pct`
checks), and that a conformant record gets written. `sim/devchar-delay` /
`sim/devchar-cp` / `sim/devchar-passives` remain the real device-
characterization evidence for #8/#9/#10.

## xschem

For testbenches whose fragment comes from an xschem schematic export, the
harness's `--print-env` sets `XSCHEM_USER_LIBRARY_PATH` to include every
`sim/<experiment-slug>/testbench/` directory plus `design/`, so gf180mcu
symbols and this repo's own symbols are on the library path:

```bash
source sim/env.sh
cd design && xschem
```

Netlist a testbench schematic without its `.control`/`.end` block (or strip
those lines after export) and point a `tb.json` at the result — the corner
runner is agnostic about whether the fragment was typed or generated.

xschem itself is not required to run any of the above; the corner runner only
needs ngspice and the PDK.
