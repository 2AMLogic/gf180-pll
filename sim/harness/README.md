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
    derived.py              extension point for campaign-supplied reductions
    raw_measures.py         writes corners/<record-id>/raw_measures.csv, unconditionally
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

### ngspice-46 required for nested nonlinear moscap decks (#153)

`sm141064.ngspice` implements this PDK's decoupling/loop-filter moscap family
(`cap_nmos_03v3`, `cap_pmos_03v3`, `cap_nmos_06v0`, `cap_pmos_06v0`, and each
of those with a `_b` body-tie variant) as a *nonlinear* capacitance -- a `c=`
behavioral coefficient expression, not a fixed value. **ngspice-47** (the
current Homebrew/apt bottle as of this writing) mis-expands that construct
into a malformed internal element/node whenever it is instantiated from
*inside* another named `.subckt` -- the hierarchical instance path the error
names (`x1.xcdec1.gc_moscap`, two levels deep: the DUT copy, then the cap
nested inside `.subckt vco`) is the signature -- and every PVT point fails
with:

```
Error on line NNNN or its substitute:
  g.x1.xcdec1.gc_moscap x1.xcdec1.c_moscap_int1 0 0 nv1   1.000000000000000e+00    e9
  unknown parameter (e9)
```

**ngspice-46 composes and runs the identical deck correctly.** This is an
ngspice-47 codegen regression in the PDK's own subcircuit, not a defect in
this repo's decks, and not something a `.options` line or netlist change can
work around — see #153 for the verified reproduction (a clean ngspice-46 run
reproducing the historical `vco-tuning-range` record's frequency/Kvco range,
byte-for-byte identical deck).

Two campaigns currently compose a DUT that nests this family and are affected:
`sim/vco-tuning-range` (`design/netlist/vco.spice`, `cap_nmos_03v3` inside
`.subckt vco`) and `sim/reference-spur` (`design/netlist/pll_top.spice`,
both `cap_nmos_03v3` inside `.subckt vco` and `cap_nmos_03v3_b` inside
`.subckt loop_filter`). A *flat*, top-level instantiation of the same family
-- as `sim/devchar-passives`' own device-characterization deck uses, with no
enclosing `.subckt` -- has been verified NOT to trigger this on ngspice-47;
that campaign runs on either version. The harness itself checks this
automatically: `run_corners.py` prints an actionable warning to stderr (and
still attempts the run) whenever it detects a resolved DUT/fragment nesting
this family under a version whose leading `ngspice-<N>` is `47`
(`harness/runner.py`'s `nonlinear_moscap_ngspice47_warning`) — so a host
missing ngspice-46 gets the explanation up front instead of only the opaque
per-point parser error.

To obtain ngspice-46 (not the current stock `brew install ngspice`, which
tracks the latest release) on macOS, build the upstream release tarball
directly rather than relying on any local, unpublished tap:

```bash
curl -LO https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/old-releases/46/ngspice-46.tar.gz
echo "a0d1699af1940b06649276dcd6ff5a566c8c0cad01b2f7b5e99dedbb4d64c19b  ngspice-46.tar.gz" | shasum -a 256 -c -
tar xzf ngspice-46.tar.gz && cd ngspice-46
./configure --enable-xspice --disable-openmp --enable-pss --with-readline=yes
make -j"$(sysctl -n hw.ncpu 2>/dev/null || nproc)"
sudo make install     # or --prefix=$HOME/.local and adjust PATH
```

(`--enable-cider` from Homebrew's own `ngspice@46` formula is omitted here as
non-essential to this fix; the sha256 above is the upstream release tarball's
own checksum, independent of any Homebrew formula.) Point `PATH` at the
resulting `ngspice` binary before invoking `run_corners.py` for either
affected campaign, e.g.:

```bash
PATH="/path/to/ngspice-46/bin:$PATH" python3 sim/run_corners.py sim/vco-tuning-range/testbench ...
```

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
python3 sim/run_corners.py my-campaign --axis n=n64 --axis rate=f200         # thin an extra axis
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

Eight further keys are optional and default to off — `topology_groups` (record
layout), `dut` (compose a committed netlist export), `dut_export` (compose a
*per-record*, non-committed netlist export), `sweeps` + `grid` (extra sweep
axes, possibly non-rectangular), `raw_files` (a waveform the deck writes
itself), `derived` (campaign-supplied reductions) and `phases` (several decks
minted into one record). Each has its own section below.

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

A netlist-level `.measure` card is serviced by ngspice's own post-`.control`
re-run of every `analyses` line — a second full pass through the same
analyses purely to report values the `.control` block's own run already
produced (identical numbers, doubled wall clock). Whenever a manifest
declares `raw_measures`, `compose_deck()` ends the control block with `quit`
(after any `measure` entries' `let`/`print` lines, which still need the
control block's own analyses to have run) so that redundant second pass never
starts. This is a cost fix, not a correctness fix — no manifest needs to know
about it or opt in.

`checks` are evaluated after the sweep:

| Key | Applies to | Meaning |
|---|---|---|
| `min` / `max` | every point | hard limit; failure names the offending corner-id |
| `max_spread_pct` | the grid | `(max-min)/\|mean\|` must stay under the limit |
| `min_spread_pct` | the grid | must *exceed* it — asserts the sweep really moved |

`min_spread_pct` is a harness-integrity check: if `.temp` or a `.lib` section
silently failed to apply, a strongly PVT-sensitive measurement would come back
flat, and this catches that instead of reporting a suspiciously perfect result.

### Model sections no corner carries: `extra_lib_sections` (optional)

A corner is a *bundle* of model `.lib` sections, one per device family. A few
gf180mcu sections belong to no family axis and are therefore in no bundle —
`cap_mim`, the legacy-name MIM subcircuits of `sm141064.ngspice`, is the case
this key exists for. Nothing pulls that section in, so a deck instantiating
`cap_mim_1f0fF` cannot resolve the name under any corner, and a fragment may
not carry its own `.lib`.

```json
{"extra_lib_sections": ["cap_mim"]}
```

Listed sections are added **unconditionally, at every PVT point, after** the
corner's own sections, and are named in the record's *Corner matrix run*
field. They are for **corner-independent** sections only: anything that varies
by corner belongs in `harness/corners.py` as a bundle, where the sweep can see
it — putting it here would silently pin that axis, which is exactly what the
fragment `.lib` ban prevents.

### Multi-topology decks: `topology_groups` (optional)

Several of this repo's campaigns put more than one sub-circuit in a single
deck — `sim/devchar-delay` alone carries unstarved rings, current-starved
rings, an inverter chain and bare devices, with two dozen measurements between
them. Rendered flat, that is one table two dozen columns wide with no hint of
which measurement belongs to which topology.

`topology_groups` fixes the *record*, and nothing else: it does not touch how
the deck is composed, how the sweep runs, how output is parsed, or how `checks`
are evaluated. Declare it and the record's **Result** field becomes one
sub-table per topology instead of one flat table.

```json
{
  "measure": {"r1_fosc": "...", "r1_tstage": "...", "ch_tpd": "...", "dc_idn": "..."},
  "topology_groups": {
    "ring1x": {
      "description": "unstarved 5-stage self-loaded ring, 1x sizing",
      "measures": ["r1_fosc", "r1_tstage"]
    },
    "chain": ["ch_tpd"]
  }
}
```

- The key is an **object**, and JSON preserves its order — the order you write
  the topologies is the order their sub-tables appear in the record.
- Each value is either a **bare list** of measurement names (shorthand, as
  `chain` above) or an **object** with a `measures` list plus an optional
  one-line `description`, rendered as the sub-table's caption. Those are the
  only two keys accepted; anything else is rejected as a typo rather than
  silently ignored.
- Every name must be defined in `measure` or `raw_measures`. A name that is
  not is a load error, because a typo would otherwise cost the record a whole
  column without saying so.
- **Partial grouping is fine.** Anything no group claims is collected into a
  trailing `ungrouped` sub-table — measurements are never dropped for being
  unassigned. (`ungrouped` is reserved; a manifest may not use it as a
  topology name.) A measurement may appear in more than one group if it
  genuinely belongs to more than one story; it is rendered in each.
- The pass/fail column of a topology's sub-table reports only *that
  topology's* check failures — a neighbouring sub-circuit's FAIL would be
  noise there. A point that failed to simulate at all shows ERROR in every
  sub-table, and grid-level check failures are still reported once for the
  whole record. The overall verdict is unchanged.
- The **Spread across the grid** table gains a leading `topology` column and
  is ordered by group, so the per-measurement summary reads the same way.

Omit the key — as every single-topology testbench, including
`harness-selftest`, does — and the record renders exactly the flat table it
always has.

### Several decks, one record: `phases` (optional)

A manifest names exactly one `netlist`, and for almost every campaign here
that is right. It is wrong for a campaign whose **claim is a pair**.
`sim/vco-tuning-range`'s supply campaign is the case this key exists for: a
*static* supply-pushing deck (f_osc vs. vdd, seven supply points) and a
*transient* supply-jitter deck (a supply step and a supply ripple against a
quiet reference copy), run separately and reduced **together**, because the
jitter numbers are not interpretable without the pushing numbers — the record's
claim is the pair. Splitting that into two records would land evidence weaker
than the record it supersedes, which the append-only rule in `sim/README.md`
does not permit.

`phases` gives each deck its own `netlist` and measurements while everything
that makes it *one record* stays shared:

```json
{
  "params": {"vctrl": "1.8"},
  "phases": {
    "push": {
      "description": "static pushing — f_osc vs. vdd_vco",
      "netlist": "tb_vco_pushing.sp",
      "analyses": ["tran {ktstep} {ktstop}"],
      "raw_measures": {"fosc": {"analysis": "tran", "expr": "when v(clk)='vdd_val/2' rise=2"}}
    },
    "jit": {
      "description": "supply step + ripple, against a quiet reference copy",
      "netlist": "tb_vco_supply_jitter.sp",
      "params": {"arip": "0.05", "astep": "0.1"},
      "analyses": ["tran {ktstep} {ktstop}", "set wr_singlescale", "wrdata jit.dat v(clkq) v(clkr)"],
      "raw_files": {"jit.dat": {"columns": ["t", "clkq", "clkr"]}}
    }
  },
  "derived": {"module": "derive.py", "measures": ["kvdd", "tie_pp"]}
}
```

| Owned by a phase | Shared by the record |
|---|---|
| `netlist`, `description`, `measure`, `raw_measures`, `raw_files`, `analyses`, `params`, `options` | the PVT grid (`corners`, `temperatures_c`, `supply_*`), `sweeps` + `grid`, `dut` / `dut_export`, `extra_lib_sections`, `checks`, `derived`, `topology_groups`, `claim`, `methodology` |

- **Not the same thing as `dut`.** `dut` composes several files into **one**
  deck. `phases` runs several **different decks** — different stimuli, on
  different topologies — and reduces them into one record.
- **The key is an object**, and JSON preserves its order: the order you write
  the phases is the order they run and the order their sub-tables appear.
- **Each phase runs its own ngspice invocation per PVT point**, so a 45-point
  grid with two phases is 90 invocations. Its deck, log and scratch directory
  carry the phase name as the `[<kind>_]` **prefix** field of the corner-id —
  `push_ss_125c_3.63v.log`, `jit_ss_125c_3.63v.log`. That is not a new
  convention: `sim/README.md` already ratifies that prefix for "a campaign that
  runs more than one analysis over the same grid" (`dc_`/`sw_` in
  `cp-compliance`). A phase name is therefore alphanumeric with `-`, **never
  `_`**, which stays the field separator.
- **Every phase's measurements land in the same per-point row**, so their names
  must be distinct across phases (and so must their `raw_files` names). A
  collision is a load error, not a silent overwrite.
- **`derive_point()` runs once, after every phase**, over the merged
  measurements and the merged `raw_files`. That is the capability: a number
  neither deck could have produced alone (a jitter figure normalised by the
  pushing slope measured on the other deck) is expressible. Its `point.params`
  carries the *shared* `params` plus the sweep-axis params — not any one
  phase's own, since a reduction that runs after every phase has no single
  answer to "which phase's parameters?".
- **Phases stop at the first one that fails or errors.** The record's claim is
  the whole set, so continuing would only produce a point that looks
  half-measured. The point is recorded `failed`/`error` with the phase's own
  message, and everything the earlier phases banked — including a `retain`ed
  waveform — is kept.
- **The record renders one sub-table per phase**, for free: two decks in one
  record *are* two topologies' worth of the same claim, which is what
  `topology_groups` renders. Declare `topology_groups` explicitly to override
  that — e.g. to place a derived measure with the deck it belongs to; anything
  unclaimed still lands in the trailing `ungrouped` table.
- **The netlist snapshot inlines every phase's fragment**, each with its own
  sha256 plus a `composed_sha256` over the whole, and the record's **Netlist
  provenance** and **Links** fields name every deck. A record minted from two
  decks says so.
- A phase must produce *something*: at least one of `measure`, `raw_measures`
  or `raw_files`. A deck whose entire output is a waveform the reduction reads
  declares only the last — that is the jitter deck above. A manifest in which
  **every** phase is of that shape is legal too: the record's numbers then all
  come from `derived.measures` over the waveforms, which is still "at least one
  measurement, from somewhere" — the same rule a single-deck manifest gets (see
  `raw_files` below).
- `params` and `options` may be declared at both levels: the top-level ones
  apply to every deck and a phase's are emitted after them, so a phase
  overrides rather than restates. `analyses` is the one shared default a phase
  replaces wholesale — two decks with two different stimuli rarely run the same
  analysis line.
- **Omit the key and nothing changes.** A manifest with no `phases` is one
  implicit, unnamed phase: the same deck, the same `<corner-id>.spice` /
  `<corner-id>.log` filenames, the same flat record it has always produced.

### Composing a committed DUT export: `dut` (optional)

Most campaigns here simulate a block whose netlist `design/netlist.sh` exports
from an xschem schematic to `design/netlist/<block>.spice`. The testbench
fragment should *instantiate* that block, not contain a copy of it — a pasted
copy makes the committed fragment a generated artefact that silently goes
stale the next time the schematic changes.

`dut` names the export(s), **repo-root-relative**, composed ahead of the
fragment:

```json
{
  "dut": ["design/netlist/div23_cell.spice"],
  "netlist": "tb_div23_cell.sp"
}
```

- The generated deck `.include`s each `dut` file **before** the fragment (the
  exports define the subcircuits the fragment instantiates), so a failing
  corner can still be re-run by hand against the live sources.
- The **netlist snapshot** (`netlist-snapshots/<record-id>.spice`) inlines them
  instead: one self-contained DUT + stimulus file, each chunk headed by its
  own source path and sha256, plus a `composed_sha256` over the whole. That is
  the same self-contained artefact `sim/lib/assemble_closed_loop.sh` produces
  by concatenation — without the committed fragment ever holding a copy.
- The record's **Netlist provenance** field names every source with its own
  sha256, so a record says exactly which export it froze.
- A `dut` export is held to the same rule as a fragment: no `.include`,
  `.lib`, `.temp`, `.control`, `.endc`, `.end`, `.measure`/`.meas`. An export
  that had picked up a `.lib` would pin every corner of every campaign that
  names it.
- A missing export is a load error naming `design/netlist.sh`, not a confusing
  "unknown subckt" thousands of lines into an ngspice log.

### Composing a per-record DUT export: `dut_export` (optional)

`design/netlist.sh` keeps a *second* export convention for a hierarchy it
deliberately does not commit — currently just `pfd_cp` (see that script's own
header comment for why: the PFD/CP is re-exported per campaign, and
committing it would be a second source of truth beside the per-record
`netlist-snapshots/<record-id>.spice` freeze `sim/README.md` already
mandates). `dut_export` is the per-record counterpart of `dut`, for exactly
that convention:

```json
{
  "dut_export": {"top": "pfd_cp"},
  "netlist": "tb_pfd_cp.sp"
}
```

- `top` is a `design/netlist.sh --top <block>` value from its PER-RECORD list
  (today, only `pfd_cp`). A manifest may declare `dut` or `dut_export`, not
  both.
- Resolving it — actually running `design/netlist.sh --top <top> <outdir>` —
  is **deferred to first use**, not done at `load()` time: the same guarantee
  the `derived` module gets ("imported lazily, never during `--list`"), for
  the same reason. Parsing or listing a manifest must never shell out to
  xschem. The first thing that actually needs the composed DUT — generating a
  deck, building provenance, or freezing the snapshot — triggers the one
  export the run needs; every PVT point after that (including ones racing it
  concurrently under `-j`) reuses the same cached, already-validated path.
- The scratch export lands at `sim/<slug>/work/dut-export/<top>/dut.spice` —
  the same already-gitignored `sim/*/work/` convention every
  `sim/lib/simenv.sh` campaign's `run.sh` already uses for this export,
  namespaced by `<top>` so a future manifest naming a second per-record top
  cannot collide with this one.
- From there on `dut_export` behaves exactly like `dut`: the generated deck
  `.include`s the exported file before the fragment, the netlist snapshot
  inlines it (self-contained, with its own sha256 and a `composed_sha256`
  over the whole), the record's **Netlist provenance** field names it, and it
  is held to the same no-`.include`/`.lib`/`.temp`/... rule a `dut` export
  is — checked the moment it materializes, since (unlike `dut`) the file does
  not exist yet at `load()` time for an earlier check to read.
- A `design/netlist.sh` failure (no xschem, wrong `--top`, a leaf-cell
  collision) surfaces as a load-time-shaped error the first time the export is
  actually needed, including the script's own stdout/stderr — not a confusing
  ngspice failure with no netlist to point at.

### Sweeping beyond the PVT grid: `sweeps` and `grid` (optional)

Some campaigns sweep an independent variable *in addition to* process,
voltage and temperature — an input rate, a divide ratio N, a phase-error
ladder — and each point of that axis needs its own **derived** deck
parameters (a timestep of `1/(250·kf)`, a stop time of `12/kf`, a one-hot
encoding of N). One fixed `params` map cannot express that.

`sweeps` declares the axes; each point spells its own id and parameters:

```json
{
  "sweeps": {
    "rate": {
      "description": "input rate",
      "points": {
        "f200": {"params": {"kf": "200e6", "ktstep": "2e-11", "ktstop": "6e-08"}},
        "f010": {"params": {"kf": "10e6",  "ktstep": "4e-10", "ktstop": "1.2e-06"}}
      }
    }
  },
  "analyses": ["tran {ktstep} {ktstop}"]
}
```

- Each point becomes one further `_`-separated field on the corner-id, in
  axis-declaration order: `ss_125c_2.97v_f200_n64`. That is the
  `[<kind>_]<bundle>_<temp>c_<supply>v[_<extra>…]` grammar `sim/README.md`
  ratifies under "Campaigns that sweep beyond the PVT grid" — the three fixed
  fields keep their meaning and position, and a campaign that sweeps nothing
  extra is completely unaffected.
- **Point ids are written out, not derived from a value.** The convention is
  `<name><value>` with no separator (`f200`, `n64`, `e0400`), the value spelled
  exactly as the deck spells it; deriving it would silently rename evidence.
  `_` is rejected in a point id, because it is the field separator.
- A point's `params` are emitted **after** the manifest's fixed `params`, so an
  axis can override a default rather than being forced to name a disjoint
  parameter set (the N = 64 runs override the timestep chosen per rate).
- **`analyses` entries are `{name}`-substituted** from `vdd_val`, `vdd_nom`,
  `temp_c`, the manifest `params` and the point's params. This is load-bearing:
  ngspice resolves `.param` braces in a top-level `.tran` card, but *not* in
  the `.control` block the harness runs its analyses from, where the same text
  fails with "TSTEP is invalid". An unknown placeholder is left untouched.
- Every axis and its points are named in the record's **Corner matrix run**
  field, on the same terms as the PVT axes.

With `sweeps` alone the run is the full cross-product of the PVT grid and every
declared point. Real campaigns are **not** rectangular — the divider chain
sweeps N = 4…64 at two stress corners only, three N over the full 45-point
grid, and drops most of the N = 64 supply points. `grid` expresses that as the
**union of justified slices**:

```json
{
  "grid": [
    {
      "description": "every N at the two stress corners",
      "corners": ["ss", "ff"], "temperatures_c": [125], "supplies": ["low"],
      "axes": {"rate": ["f200"], "n": ["n04", "n33", "n64"]}
    },
    {
      "description": "three N over the full grid",
      "axes": {"rate": ["f200"], "n": ["n04", "n33"]}
    },
    {
      "description": "N=64 only at the binding (low) supply",
      "supplies": ["low"], "axes": {"rate": ["f200"], "n": ["n64"]}
    }
  ]
}
```

| Block key | Meaning |
|---|---|
| `description` | **required** — why this slice is run; copied verbatim into the record |
| `corners` | corner-bundle names; omit for every corner the run resolved |
| `temperatures_c` | numeric temperatures; omit for all |
| `supplies` | numbers, and/or the aliases `low` / `nom` / `high`, which track the *ends* of whatever supply list the run resolved so a rule survives `--supply` / `--supply-tol` |
| `axes` | `{axis: [point-id, …]}`; omit an axis for all of its points |

- The point set is the union of the blocks, in block order, **de-duplicated by
  corner-id** — an overlapping block re-states coverage without re-simulating
  it, and the surviving point is attributed to the block that first asked.
- **Every block must carry a `description`.** That is the structural half of
  `sim/README.md`'s "every swept variable must be named, with its points, in
  the record's corner-matrix field": a thinned axis cannot be declared without
  simultaneously writing down why.
- The mandated-PVT-matrix gate is unchanged and applies to the **union**: a
  campaign that thins its extra axis can, and does, still cover the full
  −40/27/125 °C × ±10 % × five-MOS-bundle matrix. When the extra-axis grid is
  not a full cross-product the record says so explicitly, with the block list
  and each block's justification, rather than reading as a rectangle with an
  unexplained hole.
- `--axis NAME=ID[,ID…]` narrows an axis for one invocation without editing
  the manifest. Because that *removes* declared coverage, it is treated exactly
  like a PVT subset: it needs `--subset-reason` or `--no-write`. A block the
  CLI starved of points is reported the same way, never silently dropped.
- A typo — an undeclared axis, an undeclared point id, a repeated block
  description — is a load error, not a quietly smaller run.

### Expected `.measure` failures: `optional` (optional)

For some campaigns a **failed** `.measure` is the pass condition. A lock
detector's deep-out-of-lock and frequency-error copies must *never* assert, so
their `when` measurements are expected to fail at every passing corner; a
setup/hold ladder deliberately drives copies past their timing limit so their
capture measurement fails.

Mark those measurements `optional` and an absent result becomes data:

```json
{
  "raw_measures": {
    "tb_asrt": {"analysis": "tran", "expr": "when v(lb)=1.65 rise=1"},
    "tc_asrt": {"analysis": "tran", "expr": "when v(lc)=1.65 rise=1", "optional": true}
  },
  "measure": {"vout": {"expr": "v(out)", "optional": true}},
  "checks": {"tc_asrt": {"max_measured_points": 0}}
}
```

- Only a **required** measurement's absence fails a point. Without the flag, one
  expected failure marked the whole point `failed` and the report then dropped
  *every* measurement that point took successfully.
- The absence is recorded per point (`not_measured`) and rendered as
  `not measured` in the result table, and the spread table says "not measured
  at all N completed point(s)" instead of the ambiguous "no data".
- `measure` entries take the object form `{"expr": …, "optional": true}` to
  carry the flag; the bare-string form is unchanged and remains the normal
  spelling. A misspelled key is rejected rather than silently ignored.
- Spread checks (`max_spread_pct` / `min_spread_pct`) do not apply to an
  optional measurement that never fired — that is the *expected* outcome, not a
  violation. Assert on it with the two coverage checks instead:

| Key | Meaning |
|---|---|
| `max_measured_points` | at most N points may produce this measurement — `0` is "this must never assert" |
| `min_measured_points` | at least N points must produce it — "this must always assert" |

### The deck's own waveform: `raw_files` (optional)

Both measurement mechanisms above report **scalars**. A whole class of claim
here is a *sequence*: the per-cycle period sequence that jitter/TIE actually
is, a decimated I-V curve, a threshold crossing of a quantity nothing measured.
`.measure ... when` cannot report any of those. The deck writes them itself,
from the analyses block:

```json
{
  "analyses": [
    "tran {ktstep} {ktstop}",
    "set wr_singlescale",
    "wrdata jit.dat v(clkq) v(clks) v(clkr)"
  ],
  "raw_files": {
    "jit.dat": {
      "description": "quiet / stepped / rippled VCO outputs, one row per print step",
      "columns": ["t", "clkq", "clks", "clkr"],
      "retain": false
    }
  }
}
```

`analyses` entries are arbitrary `.control` lines, so `wrdata` needs nothing
new. `raw_files` is what tells the harness the file exists — without it the
file is written into a directory shared by every point of the run and nothing
can find it again.

| Key | Meaning |
|---|---|
| *(the key itself)* | the filename **exactly as the `wrdata` line spells it** — a plain filename, no directory part |
| `description` | one line, for the reader of the manifest |
| `columns` | the column names the `wrdata` line writes, in order, so a reduction can say `raw.column("clkr")` instead of `raw.column(3)`. Optional; not validated against the file |
| `retain` | `false` (default) — scratch; `true` — committed evidence. See below |

A bare list is the shorthand for "no options": `"raw_files": ["jit.dat"]`.

**A record whose every number is reduced from a waveform is a complete record.**
A manifest must still produce at least one measurement, but `measure` /
`raw_measures` are not the only source: declaring `raw_files` together with a
`derived` block whose `measures` is non-empty satisfies the requirement on its
own. A deck that only `wrdata`s and is reduced by `derive_point()` into the
record's numbers is the shape this key exists for, and (with `phases`) two such
decks reduced together is the jitter campaign. A manifest with neither an
ngspice measurement nor a `raw_files` + `derived.measures` pair is still a load
error — it would mint a record with no result.

**Per-point isolation.** Every point's deck writes the *same* filename. When a
manifest declares `raw_files`, the runner gives each point its own scratch
directory `work/<record-id>/<corner-id>.d/` and runs ngspice from there, so two
points cannot clobber each other under `-j`. The generated deck still lands at
`work/<record-id>/<corner-id>.spice`, so the reproduce-by-hand invocation is
unchanged. A manifest with no `raw_files` runs exactly where it always did.

**Reaching it from a reduction.** Each declared file arrives on the
`PointView` the `derived` hooks are handed (see the next section) as a
`RawFile` — the raw-waveform counterpart of a `join`:

```python
def derive_point(point):
    raw = point.raw("jit.dat")         # declared but unwritten is fine ...
    if not raw.exists():
        return {}                      # ... and reduces to "not measured"
    t = raw.column("t")
    clk = raw.column("clkr")
    ...
    return {"tie_pp": tie_pp}
```

| `RawFile` member | Meaning |
|---|---|
| `.path` | where the harness left it — hand it to your own reader if you'd rather parse it yourself |
| `.exists()` | did this point's deck actually write it? |
| `.rows()` | every numeric row, parsed from `wrdata`'s whitespace columns — **lazy** (a transient dump is megabytes) and cached |
| `.column(key)` | one column, by declared name or 0-based position |
| `.text()` | the file verbatim |

`derive_tables(run)` reaches the same files through `run.points[i].raw(...)`:
nothing deletes the run's work directory, so every point's file is still on
disk once the whole grid has finished.

**A file the deck never wrote is data, not a crash.** An early convergence
failure never reaches the `wrdata` line. That point's `RawFile` reports
`exists() is False` and `rows() == ()`, the reduction returns nothing, and its
derived measures are recorded **not measured** — the same treatment a ladder
that never tripped gets. The run prints how many points were affected, and the
record's per-point entry carries `raw_files_missing`, so the absence is stated
rather than silently starving the reduction.

**Is the file evidence?** Only if you say so, per file:

- **`retain: false` (default) — scratch.** The file stays in the git-ignored
  `sim/*/work/` tree. Use this when the file is the *input* to the claim rather
  than the claim: a full transient dump is megabytes per point, and the record
  cites the reduction (a `derived` table), which *is* committed.
- **`retain: true` — committed evidence.** The file is copied to
  `corners/<record-id>/<corner-id>-<name>`, alongside that point's own
  `<corner-id>.log`, under the same append-only rule as everything else there
  (`sim/README.md`) — the copy happens the moment ngspice returns, before the
  point's measurements are even judged, so a failing point still banks its
  waveform. The reduction then reads that retained copy, so the number in the
  record and the bytes in the evidence tree are the same bytes. Use this for
  the small, decimated artefact a record actually cites.

A retained file may not be named `*.raw` or `*.log`: this repo's `.gitignore`
drops those tree-wide, so the copy would sit in `corners/<record-id>/` looking
like evidence and never be committed. The loader rejects it rather than letting
that happen.

### Derived metrics: `derived` (optional)

The harness reports raw per-point measurements plus min/max/spread. Every real
campaign reports a *reduction* over those, and it is the reduction that is the
claim: a setup/hold ladder scanned for the smallest passing step, a window-edge
table over an extra axis, a `retiming_margin.csv` that joins a chain's arrival
time against a **different record's** setup/hold numbers.

Those reductions are campaign knowledge, not harness knowledge, so the harness
provides the extension point rather than the logic. A manifest names a python
module next to its `tb.json`:

```json
{
  "derived": {
    "module": "derive.py",
    "measures": ["tsetup", "thold"],
    "tables": ["retiming_margin"],
    "joins": {"dff": "divider-ratio/corners/<record-id>/dff_setup_hold.csv"}
  }
}
```

| Key | Meaning |
|---|---|
| `module` | python file **inside this testbench directory** (a reduction is part of the testbench) |
| `measures` | per-point derived measurement names, produced by `derive_point()` |
| `tables` | whole-run derived table names, produced by `derive_tables()` |
| `joins` | `{alias: sim/-relative CSV}` — another record's table, for a cross-record join |

The module may define either or both hooks, which are handed read-only views
(`PointView` / `RunView` from `harness/derived.py`) rather than harness
internals:

```python
from harness.derived import DerivedTable

def derive_point(point):
    # point.get(name) is None where a .meas did not fire -- which is what makes
    # "this ladder step never captured, so it is violated" expressible at all.
    reference = point.get("cq0")
    ...
    return {"tsetup": tsetup}          # names must be declared in 'measures'

def derive_tables(run):
    dff = run.join("dff").index_by("process", "temp_c", "vdd_v")
    ...
    return [DerivedTable(name="retiming_margin", columns=(...), rows=(...))]
```

- Derived **measures** behave exactly like measured ones downstream — summary,
  `checks`, `topology_groups`, the record's result table — but are never
  treated as required: a reduction that finds nothing to reduce is recorded as
  not-measured, for the same reason an `optional` `.measure` is.
- Derived **tables** are written to `corners/<record-id>/<name>.csv` (append-only,
  like every other artefact there) and rendered into the record's **Result**
  field ahead of the raw per-point table, with a link.
- Returning an **undeclared** name, or failing to return a **declared** table,
  is an error — a record that silently omits a declared derived quantity is
  weaker than the record it replaces, and a name the record has no column for
  would be dropped without saying so.
- `--join ALIAS=PATH` supplies or overrides a join input per invocation. That
  is what makes the cross-record case workable: a committed manifest cannot
  know which record-id a given run is being closed against.
- `point.raw("<name>")` reaches a file **this point's own deck** wrote, for a
  reduction over a waveform rather than over `.measure` scalars — see
  `raw_files` above.
- The module is imported lazily (never during `--list`) and namespaced by
  experiment, so two campaigns may both call their module `derive.py`.

## What a run writes

One run mints one `<record-id>` (`<YYYYMMDD>-<HHMMSS>-<short-git-sha>`) and
writes, under `sim/<experiment-slug>/`:

| Path | Contents |
|---|---|
| `records/<record-id>.md` | the append-only summary record — every field `sim/README.md` mandates: Record ID, Claim, Netlist provenance, Environment provenance, Corner matrix run, Methodology / criteria / limitations, Statistical convention, Result, Links, Timestamp / author, Supersedes |
| `netlist-snapshots/<record-id>.spice` | verbatim frozen copy of the testbench fragment, with its sha256 — every phase's fragment, composed, for a `phases` manifest |
| `corners/<record-id>/<corner-id>.log` | raw ngspice output, one file per PVT point (per *phase* per point, as `<phase>_<corner-id>.log`, for a `phases` manifest) |
| `corners/<record-id>/raw_measures.csv` | **always written**, one row per corner point — sweep-axis fields, `corner_id`, every measurement in `tb.measure_names`, and a PASS/FAIL/ERROR `verdict` for the point as a whole. Unlike derived tables, this does not depend on the manifest declaring anything — it is the machine-readable form of the Markdown corner table every record already renders. The verdict comes from the record's own check pipeline (`report.point_verdicts`), so the wording never drifts, but it considers **every** check in the manifest; a record that declares `topology_groups` narrows each per-topology sub-table's pass/fail column to that group's own checks, so for a manifest whose checks span groups the CSV verdict is the stricter of the two by design |
| `corners/<record-id>/<name>.csv` | one per `derived.tables` entry — the reduction the record actually claims |
| `corners/<record-id>/<corner-id>-<name>` | one per PVT point per `raw_files` entry marked `retain` — the deck's own written waveform, when the file itself is the evidence |

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
A manifest that declares `raw_files` additionally gets one
`work/<record-id>/<corner-id>.d/` directory per point, holding whatever that
point's deck wrote. A manifest that declares `phases` gets one deck (and, where
that phase writes raw files, one scratch directory) per phase per point, named
`<phase>_<corner-id>` — so the reproduce-by-hand invocation names the deck of
the phase you are chasing.

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
