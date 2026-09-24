# signoff/ — this block's gap to T1, graded rather than hand-read

`signoff/tier-report.json` is **this block's T1 verdict of record**. It is
machine-rendered by `klt signoff --manifest` from `signoff/block-manifest.json`
and re-checked in CI. Nothing in this repository hand-maintains a parallel
met/unmet checklist; if a sentence anywhere claims this block does or does not
clear a T1 item, the report is what settles it.

Today the verdict is **0 of 22 T1 rows met**, and that is the correct, expected
result — see "Why every row is `unmet`" below. An all-`unmet` report is an
honest machine-readable statement of the gap. It is worth more than a prose
checklist nobody re-reads, and it is the reason this directory exists before
the evidence does rather than after.

## Files

| File | What it is |
| --- | --- |
| `block-manifest.json` | The block manifest: this block's `block` name, its `kind`, and the evidence envelope cited per T1 item. Hand-edited; the only file here a human writes. |
| `tier-report.json` | `klt signoff --manifest … --format json` output. **Generated — do not edit.** Re-render with `bash signoff/run-signoff.sh`. |
| `design-evidence-tiers.md` | A pinned copy of `klayout-tools`' T1 checklist. See "Why the checklist is vendored here". |
| `run-signoff.sh` | Renders the report (`bash signoff/run-signoff.sh`) or verifies the committed one (`--check`, which is what CI runs). |

## Reproducing

```sh
pip install 'klayout-tools==0.6.0'
bash signoff/run-signoff.sh --check    # verify the committed report
bash signoff/run-signoff.sh            # re-render it after changing the manifest
```

The CI `checks` job runs `--check` on every push and pull request. That is
what stops this verdict from rotting: an evidence artifact that changes after
the manifest pinned its `content_hash` re-renders as `unmet` /
`stale_evidence`, the committed report no longer matches, and the build fails
instead of a stale green row surviving. Both halves of that are demonstrated
under "Negative controls" below.

**A local `--check` run is only meaningful against the klt version CI
currently pins.** `klt signoff --format json` output is not guaranteed
byte-stable across releases -- 0.6.0 added new provenance fields (`build`,
`build_t1_item_count`, `source_doc_content_hash`, and a per-item
`graded_by_build`) that 0.5.0 did not emit, so running `--check` on a
different local klt version than the one CI pins can report the committed
report "stale" even when no T1 verdict actually changed. The version CI
pins is always `.github/workflows/ci.yml`'s "Install klt (klayout-tools) for
the signoff tier check" step (`pip install 'klayout-tools==…'`) -- treat that
line, not this README, as the source of truth if the two ever drift, and
match your local `klt --version` against it before trusting a `--check`
failure as real.

## Block kind: `mixed-signal`, and the partition boundary

`kind: "mixed-signal"`. The checklist requires a mixed-signal claim to state
its partition boundary explicitly, so that a reviewer can tell which evidence
covers which silicon. This repo's boundary is the one
`spec/decision-records/DR-008-full-custom-digital-verification-methodology.md`
already draws (recorded status: `proposed`):

- **Digital partition** — the feedback divider (`design/divider_chain.sch`,
  `design/div23_cell.sch`), the lock detector (`design/lock_detector.sch`), and
  the shared 3.3 V static-CMOS logic library instantiated only by those two
  (`design/inv_3v3.sch`, `nand2_3v3`, `nor2_3v3`, `tgate_3v3`, `dff_tg_3v3`, …).
- **Analog partition** — everything else: the VCO and its bias
  (`design/vco.sch`, `design/vco_bias.sch`, `design/vco_stage.sch`), the PFD
  and its dedicated logic cells (`design/pfd.sch`, `design/pfdcp_*.sch`), the
  charge pump (`design/cp.sch` and its legs/dump buffer), and the loop filter
  (`design/loop_filter.sch`).

The digital partition is **full-custom**: no RTL, no synthesis, no
place-and-route, because the two open gf180mcu standard-cell libraries are
5 V-flavour and this design is 3.3 V thick-oxide-only (DR-002 Decision 3). The
checklist covers that as the "Full-custom digital sub-case" of the Digital
column — such a partition still declares `kind: "digital"` and is graded the
same way, with the Analog column's artifacts standing in for items 1, 2 and 5.
DR-008 is this repo's own statement of that substitution and predates the
checklist text adopting it.

## Why every row is `unmet`

The report's `reason` for all 22 T1 rows is `no_evidence`: the manifest cites
nothing. That single machine code covers three materially different situations,
and the difference is the point of this section.

**1. The artifact exists, but not as a `klt` JSON envelope.** There is no `klt`
`--format json` envelope of any kind committed anywhere in this repository. The
layout evidence under `layout/evidence/*/` is the foundry runset's own stdout
plus `.lyrdb`/`.lvsdb` databases; the `sim/` campaigns recorded in
`sim/CHARACTERIZATION.md` are this repo's own Markdown-plus-raw-log record
format, produced by `sim/run_corners.py`, not by `klt sim`. `klt signoff`
grades envelopes, so none of it is citable as it stands. This affects items 3,
4, 5 and 6 most directly.

**2. The artifact does not exist yet.** No PLL-block layout has been drawn.
`layout/pll_top/` holds real transistor-level layout for sub-blocks (the
assembled VCO, the PFD, divider and lock-detector leaf cells) — but T1 is
block-scoped, and a sub-block's clean DRC is not the block's item 3. Item 7
(post-layout verification) accepts only a `klt pex` report for an analog
partition, and there is neither a PEX run nor a block layout to extract one
from. Item 11 (power delivery, structural) needs a `klt erc` supply spec and
report; this repo has neither — that gap is tracked separately as #427.

**3. The tool cannot check what the item claims, and we decline to game it.**
Items **1** (design sources), **2** (layout), **9** (testbenches shipped) and
**10** (repo hygiene) have no `klt` verb behind them. `klt signoff` grades them
on whether *some* passing envelope was cited at all, not on whether the cited
evidence has anything to do with the claim — one clean DRC report cited four
times would render four `met` rows and the tool would have no basis to object.
This repo cites nothing for them. Items 1, 9 and 10 have real artifacts behind
them (the committed schematics and the netlist-drift check in CI's
`pdk-checks`; a testbench per claimed measurement under `sim/*/testbench/`;
this repo's README and spec table), but turning those into green rows would
mean citing evidence that does not support them. Item 2 has no block-level
artifact at all. A row that goes green for the wrong reason is worse than a red
one.

Two further things the report does **not** say, which belong with any claim
made from it:

- **Item 5 needs a ratified spec.** `spec/pll.md` is ratified with amendments
  (#1, DR-007), but two rows — lock time (row 9) and lock detector (row 16) —
  are explicitly carved out and remain unratified. A future item-5 citation
  covers those two rows only when they are.
- **Items 3 and 4 report their coverage, they do not grade it.** When a DRC or
  LVS citation eventually lands here, a `met` verdict will not by itself mean
  the deck's rule-free layers or an `unchecked` `power_connectivity` were
  disclosed. Those disclosures have to be written into the claim, not inferred
  from the row.

## Why the checklist is vendored here

`run-signoff.sh` passes `--tiers-doc signoff/design-evidence-tiers.md` rather
than using the checklist bundled inside the installed `klt` wheel. The released
wheel (`klayout-tools` 0.5.0, released 2026-09-15) bundles a **ten**-item
checklist; T1 item 11 landed upstream on 2026-09-17 (klayout-tools#2025). Graded
against the bundled copy this block renders 20 rows and item 11 does not exist
at all — which is exactly the silent staleness this directory is here to
prevent. (The underlying release lag is upstream's own klayout-tools#2173, not
something this repo can close.)

`--tiers-doc` is `klt signoff`'s own documented override for this, so the
vendored copy is a bridge, not a fork. It is a byte-for-byte copy of
`2AMLogic/klayout-tools` `docs/design-evidence-tiers.md` at commit
`428951e036935d37161732adb55915049c598cc4` ("feat(signoff): add T1 item 11,
power delivery (structural) (#2057)", 2026-09-19), sha256
`275964ed6cdc3ed57566710540daa76beb26c1b67fb4b3dbf598d05b640a7ce0`. It carries
no local edits and must not acquire any: the checklist is upstream's to write,
and an edit here would be this repo grading itself against its own rules.
**Delete this file and the `--tiers-doc` flag once a released `klt` bundles an
eleven-item checklist.** Editing it is caught immediately — every item's text
is copied verbatim into `tier-report.json`, so any change re-renders the report
and fails CI's `--check`.

Two limits of the bridge, stated rather than assumed:

- Because item text is baked into the committed report, a *silent* upstream
  amendment to the checklist is not detected here — only a change to this
  pinned copy is. Re-pinning is a deliberate act, and re-reading the diff is
  part of it.
- klt 0.5.0 parses and renders item 11's row but has none of item 11's grading
  logic (its compound array-of-citations evidence entry, its `erc` /
  `place-and-route` accepted kinds). With no citation the row is `unmet` either
  way, so the verdict is correct today — but **do not cite item 11 evidence
  against 0.5.0 and read the result as graded.** Filed upstream as the friction
  issues named below.

## Negative controls

Two properties were demonstrated before this directory was committed, in the
same spirit as `layout/harness/faults.py`'s injected-violation controls: a gate
that cannot fail is not a gate.

**A pinned `content_hash` catches an artifact that changed.** A scratch
manifest citing a scratch `klt drc` envelope with a matching pinned hash graded
`met`. Changing only that envelope's `provenance.input.content_hash` — the
artifact moving on underneath a manifest that still pins the old revision —
re-graded the same row:

```
fresh : met   None            {'kind': 'drc', 'check_status': 'clean', …}
stale : unmet stale_evidence  None
```

**CI's `--check` catches a report that no longer matches its manifest.**
Editing one field of the committed `tier-report.json` and re-running
`bash signoff/run-signoff.sh --check` exits 1 and prints the diff:

```
-  "t1_met_count": 99,
+  "t1_met_count": 0,
```

## Upstream friction filed from this work

Per this repo's friction protocol (`CLAUDE.md`), tool gaps hit while wiring
this up were filed generically against `2AMLogic/klayout-tools` rather than
worked around silently:

- **klayout-tools#2175** — the tier report names the checklist it graded
  against (`source_doc`) but does not pin its content, so a committed report
  cannot be checked against a checklist that has since changed. The grader
  demands `content_hash` pinning from every citation for exactly this reason
  and does not apply it to its own governing document.
- **klayout-tools#2176** — with `--tiers-doc`, the doc's item list and the
  build's grading logic can be at different versions, and the report says
  nothing about which items the running build actually implements. An
  ungradeable row is indistinguishable from a correctly-graded `unmet` one.
- **klayout-tools#2177** — a manifest cannot record *why* an item is honestly
  uncited, so the machine verdict and its explanation live in two files that
  drift apart. Most of the section "Why every row is `unmet`" above is prose
  that wants to be manifest data.
