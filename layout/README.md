# layout/ — DRC/LVS flow (gf180mcu)

This directory brings up a repeatable, `klt`-aware DRC/LVS flow against the
gf180mcu open-PDK decks (issue #16) — the entry gate to the layout phase on
this project's maturity ladder (simulation-complete -> layout DRC/LVS-clean
-> shuttle seat). It is **tool/flow bring-up**, proven on a trivial cell (a
tapped standard-cell inverter), not any PLL-block layout — see
`layout/evidence/inv-tb-proof/` for the recorded proof and "Scope" below.

```
layout/
  README.md                 this file
  run_pv.py                 CLI entry point: check-env / build / drc / lvs / bare-cell / prove
  harness/                  the harness itself
    env.py                    tool discovery: PDK, KLayout binary, PV-capable python
    cell.py                   the trivial cell (inv_tb) + its reference netlist
    drc.py                    drives the foundry DRC deck, normalises the verdict
    lvs.py                    drives the foundry LVS deck, normalises the verdict
    faults.py                 negative-control fault injection (DRC + LVS)
  tools/
    pmap                      macOS pmap(1) shim the foundry decks' logger needs (see below)
  evidence/
    inv-tb-proof/            committed proof artifacts (gds, netlist, logs, reports)
    work/                    scratch re-run tree (git-ignored)
```

## Why this isn't `klt drc` / a `klt lvs`

CLAUDE.md's PDK line names `klt` (2AMLogic/klayout-tools) as this project's
layout tool. This flow *does* use `klt` — `klt pdk find --pdk gf180mcuD` is
the quickest way to confirm which gf180mcu install and asset paths a
machine will resolve, and it is exactly what `layout/harness/env.py`
delegates to (via `sim/harness/pdk.py`'s single-sourced resolver, so the sim
and layout harnesses can never disagree about which PDK install is in use).

It does **not** use `klt drc` (and there is no `klt lvs`) for the actual
sign-off-grade checks in this flow, for two documented reasons, not an
oversight:

1. **No LVS verb exists in `klt` yet.** Filed and tracked publicly at
   [2AMLogic/klayout-tools#54](https://github.com/2AMLogic/klayout-tools/issues/54)
   ("no netlist/parasitic extraction or LVS capability yet"), which this
   bring-up independently reconfirms (see "Friction log" below).
2. **`klt drc`'s gf180mcu deck is a curated ~10-rule subset** (poly2/comp/
   contact/metal1 width-space-enclosure checks), by design documented in
   `klayout_tools/decks/gf180mcu.py`'s own module docstring as "not a full
   transcription of the official rule manual". `klayout-tools`' own
   ROADMAP.md states competing with signoff tools is a non-goal ("the point
   is the agent-native surface, not competing with signoff tools") — so this
   is not a gap to file, just a scope this flow cannot rely on for a
   DRC/LVS-clean gate.

So the checks that gate this project's layout phase run the PDK's own
official decks (`libs.tech/klayout/{drc,lvs}/run_{drc,lvs}.py`) through the
standalone KLayout application binary — the foundry-authored, full-coverage
DRC/LVS-DSL scripts, not a re-implementation. `klt drc --deck gf180mcu`
remains useful as a fast, dependency-light **pre-check** during layout
iteration (seconds, not minutes) before a full deck run; it is not the gate.

## Prerequisites

| Tool | Why | Notes |
|---|---|---|
| gf180mcu PDK | DRC/LVS decks + standard-cell GDS/CDL | `pip install volare && volare enable --pdk gf180mcu <hash>` — same install `sim/` uses |
| KLayout **application** binary | runs the foundry Ruby DRC/LVS-DSL decks (`klayout -b -r deck.drc`) | **not** the `klayout` pip wheel, which has no DSL runner — see "The two KLayouts" below |
| A Python environment with `klayout` (pip) + `docopt` importable | the PDK's own `run_drc.py`/`run_lvs.py` need them | `python3 -m venv ~/opt/gf180pv-venv && ~/opt/gf180pv-venv/bin/pip install klayout docopt` |
| `klt` (optional but recommended) | fast PDK/asset discovery, and a quick pre-check DRC pass | `pip install klayout-tools` |

The harness never hardcodes any of these three paths. `layout/harness/env.py`
resolves them, in order, with an environment-variable override for each so a
CI runner or a differently-provisioned box never needs a code change:

- **PDK** — delegates entirely to `sim/harness/pdk.py` (`GF180_PDK_PATH` /
  `PDK_ROOT`+`PDK` / `sim/pdk.local.json` / `sim/pdk.json` / built-in search
  roots), so the sim and layout harnesses always agree on which gf180mcu
  install is in use.
- **KLayout binary** — `$KLAYOUT_BIN`, then `PATH`, then common per-platform
  install locations (`~/opt/klayout/...`, `/Applications/KLayout/...`, ...).
- **PV python** — `$LAYOUT_PV_PYTHON`, then the running interpreter, then
  `python3`/`python` on `PATH`, then `~/opt/gf180pv-venv/bin/python` --
  whichever first imports both `klayout` and `docopt` successfully.

```bash
python3 layout/run_pv.py check-env
```

reports all three, or an actionable install hint for whichever is missing.

### macOS: quarantine

A Homebrew-cask KLayout install (`/Applications/KLayout/klayout.app`) carries
a `com.apple.quarantine` extended attribute and is ad-hoc signed. Gatekeeper
does not just refuse it — it makes a headless `klayout -b ...` invocation
**hang** with no error, which looks like a stuck DRC run rather than a
permission problem (observed directly during bring-up: `klayout -v` under
`timeout 30` returned exit 137, i.e. killed by the timeout, only from the
quarantined app; a non-quarantined build of the same binary returns
immediately). Fix: use a KLayout build with no quarantine attribute (built
from source, or `xattr -dr com.apple.quarantine /Applications/KLayout/klayout.app`
once, interactively, after verifying the download), and point
`$KLAYOUT_BIN` at it if it isn't already the first candidate `env.py` tries.

### The two KLayouts

This flow genuinely needs **both** KLayout distributions, for different
jobs, and conflating them is the single easiest way to get stuck:

- The **pip wheel** (`pip install klayout`, imported as `klayout.db`) is a
  headless Python API with no DSL runner. `layout/harness/cell.py` uses it
  to assemble `inv_tb.gds`; `layout/harness/faults.py` uses it to inject
  faults; the PDK's own `run_drc.py`/`run_lvs.py` (the "PV python" above)
  import it too.
- The **standalone application binary** (`klayout -b -r <deck>`) is the only
  thing that can execute the foundry's Ruby DRC/LVS-DSL rule decks. There is
  no way to run a `.drc`/`.lvs` script through the pip wheel.

### The `pmap` shim (macOS/BSD)

The foundry DRC/LVS decks configure a Ruby logger whose message formatter
unconditionally shells out to `` `pmap #{Process.pid} | tail -1`[10, 40] ``
to prefix every log line with memory usage. macOS/BSD have no `pmap(1)`; the
backtick expansion returns an empty string, `""[10, 40]` is `nil`, and the
deck dies on its very first log line with
`undefined method 'strip' for nil:NilClass` — before evaluating a single
rule, for a reason that has nothing to do with the layout under test. This
was hit verbatim during bring-up. `layout/tools/pmap` is a ~20-line shim
that prints a `ps`-derived RSS in the one format `| tail -1` looks at;
`layout/harness/env.py` puts `layout/tools/` at the front of `PATH` for the
duration of a deck subprocess only. **It must keep its executable bit** —
`git update-index --chmod=+x` if a checkout ever loses it (observed once
during bring-up: an untracked copy landed `-rw-r--r--` and every deck run
failed with `Permission denied` until `chmod +x` was applied).

## The flow

```bash
python3 layout/run_pv.py check-env                     # PDK / KLayout / PV-python present?
python3 layout/run_pv.py build --outdir /tmp/pv         # assemble inv_tb.gds + inv_tb.spice
python3 layout/run_pv.py drc /tmp/pv/inv_tb.gds --top inv_tb --run-dir /tmp/pv/drc
python3 layout/run_pv.py lvs /tmp/pv/inv_tb.gds /tmp/pv/inv_tb.spice --top inv_tb --run-dir /tmp/pv/lvs
python3 layout/run_pv.py prove                          # the full proof, see below
```

Each of `drc` / `lvs` runs the foundry deck exactly once and prints a
one-line verdict plus an exit code:

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| `drc` | clean, 0 violations | violations found | PDK/KLayout/PV-python not found, or the deck itself failed to run |
| `lvs` | netlists match | netlists mismatch | environment problem, or neither verdict marker appeared |

**Reading a result**: `drc` reports a `status` (`clean`/`violations`/`error`),
a `violation_count`, and per-rule counts pulled out of the KLayout report
database (`*.lyrdb`) — not grepped from prose. `lvs` reports `match` /
`mismatch` / `error`. **Neither runner's own exit code is meaningful** — see
"Two exit-code traps" below; the harness always decides the verdict from the
deck's own log marker (`"Klayout DRC run is clean"` / `"...is not clean"`;
`"Congratulations! Netlists match"` / `"Netlists don't match"`).

### Two exit-code traps

Both foundry runners' process exit status is unreliable as a pass/fail
signal, for different (and non-obvious) reasons — discovered directly during
bring-up, which is why `layout/harness/drc.py` and `layout/harness/lvs.py`
never trust it:

- **`run_drc.py`** exits non-zero both when the deck fails to run *and* (in
  this PDK snapshot) on a dirty result — so its exit code alone cannot
  distinguish "ran, found violations" from "crashed before running". The
  harness decides from the log's clean/dirty marker first, falling back to
  the exit code only to catch a run that produced neither marker.
- **`run_lvs.py`** exits **0 on a mismatch**. A naive
  `run_lvs.py ... && echo ok` reports success on a failing LVS. This is the
  more dangerous of the two, because it fails silently in the direction that
  looks like success.

### The substrate-net gotcha (LVS)

Run LVS with `--lvs_sub=VSS` (the harness's default). Without it, the
extractor names the global p-substrate net `gf180mcu_gnd` and exposes it as
an extra top-level pin — so a schematic that (correctly) ties the n-channel
bulk to `VSS` will not match, for a substrate-naming reason that has nothing
to do with whether the circuit is actually correct. `layout/harness/lvs.py`
bakes this default in; override with `--lvs-sub` if a different reference
netlist's convention needs it.

## `prove`: the full proof

```bash
python3 layout/run_pv.py prove
```

Builds `inv_tb` fresh, then runs four checks, each against an *expected*
verdict — the last two are the negative controls the issue's test plan
calls for (intentionally introduce one DRC violation and one LVS mismatch,
confirm the flow reports them):

1. `inv_tb` DRC — expected **clean**
2. `inv_tb` LVS (vs. its hand-written reference netlist) — expected **match**
3. `inv_tb` + one undersized Metal1 shape, DRC — expected **violations**
   (`Mn.1`-class width rule)
4. `inv_tb` + its output-net Metal1 island deleted, LVS — expected
   **mismatch** (open output node)

Exit codes: `0` every expectation held; `1` at least one did not (but no
negative control came back clean); `3` a negative control came back
**clean** — treated as a harness fault, not a pass, because a flow that has
only ever been shown reporting *clean* results is not evidence it can catch
a dirty one (see `layout/harness/faults.py`'s module docstring). Unless
`--evidence-dir ''` is passed, `prove` copies the GDS/netlist/report/log
artifacts from all four checks into `layout/evidence/inv-tb-proof/` (see
below); pass a `--work-dir` to control where the scratch run trees
(`main.drc` templates, per-run logs) land — default `layout/evidence/work/`,
git-ignored.

Wall time: dominated by the two full-deck DRC runs, each several minutes
against the ~50-table `main` rule deck (`--no_offgrid` by default — the
off-grid check class is skipped as a separate, slower class of rule this
flow-bring-up proof does not need; pass `--offgrid` to `drc`/`prove` for a
signoff-grade run). LVS is fast (a few seconds) by comparison.

## The trivial cell (`inv_tb`)

`layout/harness/cell.py` assembles one gf180mcu 9-track standard-cell
inverter (`gf180mcu_fd_sc_mcu9t5v0__clkinv_1`) abutted with the well/tap
cells it needs to stand alone (`endcap | filltie | clkinv_1 | filltie |
endcap`, 5.04 um row), built directly from the installed PDK's own
`libs.ref` GDS (no foundry geometry vendored into this repo). The taps are
not optional set-dressing: `layout/run_pv.py bare-cell` streams the bare
`clkinv_1` cell out on its own and DRCs it, reproducibly reproducing
`DF.13_MV` / `DF.14_MV` violations (NCOMP-in-nwell / PCOMP-outside-nwell too
far from a well/substrate tap) — a bare standard cell is not, and is not
expected to be, DRC clean by itself. The matching LVS reference netlist
(`inv_tb.spice`) is hand-written, deliberately, rather than lifted from the
PDK's CDL: the point of an LVS proof is that an *independently stated*
schematic matches the layout, using the device sizes the cell's own `.cdl`
documents (`nfet_05v0` W=0.73/L=0.6, `pfet_05v0` W=1.83/L=0.5).

## `layout/evidence/inv-tb-proof/`

Committed proof artifacts from the most recent `prove` run — the "flow
proven clean on a trivial cell" acceptance criterion, with a citable trail
rather than only a comment thread:

```
evidence/inv-tb-proof/
  PROOF.md            what was run, tool/PDK provenance, the four checks + verdicts
  inv_tb.gds / .spice           the trivial cell + its reference netlist
  drc-clean/                    clean-run DRC report db + captured deck log
  lvs-clean/                    match-run extracted netlist + LVS db + captured deck log
  drc_fault.gds  drc-fault/     the DRC negative control + its report db + log
  lvs_fault.gds  lvs-fault/     the LVS negative control + its extracted netlist/db + log
```

Re-running `prove` overwrites this directory (it is a proof-of-flow
snapshot, not per-run append-only evidence like `sim/`'s records — there is
one flow to prove, not a family of PVT campaigns) — but do not hand-edit any
file under it; regenerate via `run_pv.py prove` instead so the artifacts and
`PROOF.md` never drift apart.

## Friction log (CLAUDE.md's friction protocol)

Per CLAUDE.md, every `klayout-tools` awkwardness/gap/wrong-behavior
encountered during this bring-up gets filed generically on the public
`2AMLogic/klayout-tools` tracker — tool-gap description only, never design
details, spec values, or this repo's content.

- **No `klt lvs`.** Already tracked publicly:
  [2AMLogic/klayout-tools#54](https://github.com/2AMLogic/klayout-tools/issues/54).
  This bring-up independently reconfirms the gap (an LVS-gating flow has
  nothing to reach for in `klt` today); a confirming comment was added to
  that issue rather than filing a duplicate.
- **`klt drc`'s gf180mcu deck is a curated subset, not a signoff deck.**
  Self-documented already in that deck's own module docstring, and matches
  `klayout-tools`' stated non-goal of competing with signoff tools — not
  filed as a gap, since the project has already scoped this deliberately.
- Everything else chafed against during bring-up (the quarantine hang, the
  `pmap` crash, the two exit-code traps, the substrate-net LVS gotcha) is
  **PDK-native tooling friction** (the gf180mcu open-PDK's own
  `run_drc.py`/`run_lvs.py` and the standalone KLayout application), not a
  `klayout-tools` capability gap — out of scope for that tracker, documented
  here instead.
